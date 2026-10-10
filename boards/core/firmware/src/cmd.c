#include <xc.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "board.h"
#include "canfd.h"
#include "net.h"
#include "serial.h"
#include "settings.h"
#include "server.h"
#include "ssr.h"
#include "io.h"
#include "cmd.h"

#define MAX_ARGS        10
#define SET_ACK_MS      500u
#define INFO_MS         500u
#define CLEAR_MS        1500u           /* wait for the next STATUS (sent every 1 s) */
#define REBOOT_MS       200u
#define OFF_TIMEOUT_MS  1000u           /* failsafe timeout sent with SSR OFF (irrelevant while off) */

enum { P_NONE, P_SET, P_CLEAR, P_INFO, P_REBOOT };

/* ------------------------------------------------------------------ output */

static void out(session *s, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void out(session *s, const char *fmt, ...)
{
    char buf[384];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf - 1u, fmt, ap);
    va_end(ap);
    if (n < 0)
        return;
    if ((uint32_t)n > sizeof buf - 2u)
        n = sizeof buf - 2;
    buf[n] = '\n';
    buf[n + 1] = 0;
    s->write(s, buf);
}

#define OK(s, ...)          out(s, "OK" __VA_ARGS__)
#define ERR(s, code, ...)   out(s, "ERR " #code " " __VA_ARGS__)

/* ------------------------------------------------------------------ argument helpers */

typedef struct {
    int argc;
    char *argv[MAX_ARGS];
} args_t;

bool str_ieq(const char *a, const char *b)
{
    while (*a && *b)
        if (tolower((unsigned char)*a++) != tolower((unsigned char)*b++))
            return false;
    return *a == *b;
}

bool str_ieq_n(const char *a, const char *b, uint32_t n)
{
    while (n--) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b))
            return false;
        if (!*a)
            return true;
        a++;
        b++;
    }
    return true;
}

#define ieq str_ieq

/* value of key=... among argv[from..], NULL if absent */
static const char *kv(const args_t *a, int from, const char *key)
{
    size_t n = strlen(key);
    for (int k = from; k < a->argc; k++) {
        const char *eq = strchr(a->argv[k], '=');
        if (eq && (size_t)(eq - a->argv[k]) == n) {
            char tmp[16];
            if (n >= sizeof tmp)
                continue;
            memcpy(tmp, a->argv[k], n);
            tmp[n] = 0;
            if (ieq(tmp, key))
                return eq + 1;
        }
    }
    return NULL;
}

/* every argv[from..] must be key=value with a key from the list */
static bool only_keys(session *s, const args_t *a, int from, const char *const *keys)
{
    for (int k = from; k < a->argc; k++) {
        const char *eq = strchr(a->argv[k], '=');
        bool ok = false;
        if (eq) {
            for (const char *const *key = keys; *key && !ok; key++) {
                size_t n = strlen(*key);
                if ((size_t)(eq - a->argv[k]) == n && str_ieq_n(a->argv[k], *key, n))
                    ok = true;
            }
        }
        if (!ok) {
            ERR(s, 400, "unexpected argument '%s'", a->argv[k]);
            return false;
        }
    }
    return true;
}

static bool parse_uint(const char *v, uint32_t lo, uint32_t hi, uint32_t *out_v)
{
    char *end;
    if (!v || !*v || !isdigit((unsigned char)*v))
        return false;
    unsigned long x = strtoul(v, &end, 10);
    if (*end || x < lo || x > hi)
        return false;
    *out_v = (uint32_t)x;
    return true;
}

/* "12", "12.3", "12.345" -> hundredths, rounded half up */
static bool parse_centi(const char *v, uint32_t max, uint16_t *out_v)
{
    uint32_t whole = 0, frac = 0, digits = 0;
    const char *p = v;
    if (!v || !isdigit((unsigned char)*p))
        return false;
    while (isdigit((unsigned char)*p)) {
        whole = whole * 10u + (uint32_t)(*p++ - '0');
        if (whole > 100000u)
            return false;
    }
    if (*p == '.') {
        p++;
        while (isdigit((unsigned char)*p)) {
            if (digits < 3u) {
                frac = frac * 10u + (uint32_t)(*p - '0');
                digits++;
            }
            p++;
        }
    }
    if (*p)
        return false;
    while (digits < 3u) {
        frac *= 10u;
        digits++;
    }
    uint32_t c = whole * 100u + (frac + 5u) / 10u;
    if (c > max)
        return false;
    *out_v = (uint16_t)c;
    return true;
}

static bool parse_ip(const char *v, uint8_t ip[4])
{
    if (!v)
        return false;
    for (int k = 0; k < 4; k++) {
        uint32_t x = 0, digits = 0;
        while (isdigit((unsigned char)*v) && digits < 4u) {
            x = x * 10u + (uint32_t)(*v++ - '0');
            digits++;
        }
        if (!digits || x > 255u || *v != (k < 3 ? '.' : 0))
            return false;
        ip[k] = (uint8_t)x;
        if (k < 3)
            v++;
    }
    return true;
}

static const char *ipstr(const uint8_t ip[4], char *buf)
{
    sprintf(buf, "%u.%u.%u.%u", ip[0], ip[1], ip[2], ip[3]);
    return buf;
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    c = (char)toupper((unsigned char)c);
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/* cansend syntax: <id>#<data>, <id>#R, <id>##<flags><data> (flags: 1 = BRS) */
static bool parse_frame(const char *str, can_frame *f)
{
    const char *hash = strchr(str, '#');
    if (!hash)
        return false;
    memset(f, 0, sizeof *f);
    uint32_t idlen = (uint32_t)(hash - str);
    if (idlen != 3u && idlen != 8u)
        return false;
    for (uint32_t k = 0; k < idlen; k++) {
        int v = hexval(str[k]);
        if (v < 0)
            return false;
        f->id = (f->id << 4) | (uint32_t)v;
    }
    if (idlen == 8u) {
        f->flags |= CAN_EXT;
        if (f->id > 0x1FFFFFFFu)
            return false;
    } else if (f->id > 0x7FFu) {
        return false;
    }
    const char *p = hash + 1;
    if (*p == 'R' || *p == 'r') {
        f->flags |= CAN_RTR;
        return p[1] == 0;
    }
    if (*p == '#') {
        int fl = hexval(p[1]);
        if (fl < 0)
            return false;
        f->flags |= CAN_FDF | ((fl & 1) ? CAN_BRS : 0);
        p += 2;
    }
    uint8_t max = (f->flags & CAN_FDF) ? 64u : 8u;
    while (*p) {
        if (*p == '.') {
            p++;
            continue;
        }
        int hi = hexval(p[0]), lo = p[1] ? hexval(p[1]) : -1;
        if (hi < 0 || lo < 0 || f->len >= max)
            return false;
        f->data[f->len++] = (uint8_t)((hi << 4) | lo);
        p += 2;
    }
    if (f->flags & CAN_FDF)
        f->len = can_dlc_to_len(can_len_to_dlc(f->len));    /* padded with zeros */
    return true;
}

/* ------------------------------------------------------------------ status lines */

static const char *const mode_name[] = {
    [CAN_MODE_FD] = "fd", [CAN_MODE_CLASSIC] = "classic",
    [CAN_MODE_LISTEN] = "listen", [CAN_MODE_LOOPBACK] = "loopback",
};

static void serial_number(char *buf)
{
    sprintf(buf, "%08lX%08lX", (unsigned long)DEVSN1, (unsigned long)DEVSN0);
}

static void line_core(session *s, const char *prefix)
{
    char ip[16];
    uint8_t a[4];
    net_active_ip(a);
    uint8_t phy = net_physr();
    const char *link = !net_ok() ? "no-chip" : !(phy & 1u) ? "down"
                     : (phy & 2u) ? ((phy & 4u) ? "10M-half" : "10M-full")
                                  : ((phy & 4u) ? "100M-half" : "100M-full");
    out(s, "%sCORE fw=%s up=%lu ip=%s link=%s clients=%u",
        prefix, FW_VERSION, (unsigned long)millis(), ipstr(a, ip), link, server_clients());
}

static void line_can(session *s, const char *prefix, uint8_t ch)
{
    can_status c;
    can_get_status(ch, &c);
    if (!c.present && !c.running) {
        out(s, "%sCAN %u present=0", prefix, ch);
        return;
    }
    if (!c.running) {
        out(s, "%sCAN %u present=1 state=stopped", prefix, ch);
        return;
    }
    out(s, "%sCAN %u present=%u mode=%s nominal=%lu data=%lu state=%s tec=%u rec=%u rx=%lu tx=%lu rx_overflow=%lu tx_full=%lu",
        prefix, ch, c.present, mode_name[c.mode], (unsigned long)c.nominal, (unsigned long)c.data,
        c.bus_off ? "bus-off" : c.error_passive ? "passive" : "active", c.tec, c.rec,
        (unsigned long)c.rx_frames, (unsigned long)c.tx_frames,
        (unsigned long)c.rx_overflows, (unsigned long)c.tx_full);
}

static void line_ser(session *s, const char *prefix, uint8_t p)
{
    const ser_settings *c = ser_get(p);
    uint32_t rx, tx;
    char ip[16] = "none";
    uint8_t a[4];
    ser_counters(p, &rx, &tx);
    if (tcp_connected(SOCK_SER(p))) {
        tcp_peer(SOCK_SER(p), a);
        ipstr(a, ip);
    }
    out(s, "%sSER %u type=%s baud=%lu data=%u parity=%c stop=%u client=%s rx=%lu tx=%lu",
        prefix, p, ser_rs485(p) ? "rs485" : "rs232", (unsigned long)ser_actual_baud(p),
        c->data, c->parity, c->stop, ip, (unsigned long)rx, (unsigned long)tx);
}

static void line_stream(session *s, const char *prefix)
{
    char ip[16];
    if (!ssr_stream.on)
        out(s, "%sSTREAM off", prefix);
    else
        out(s, "%sSTREAM on ip=%s batch=%u fmt=%s sent=%lu dropped=%lu", prefix, ipstr(ssr_stream.ip, ip),
            ssr_stream.batch, ssr_stream.text ? "text" : "bin",
            (unsigned long)ssr_stream.sent, (unsigned long)ssr_stream.dropped);
}

static void line_ssr(session *s, const char *prefix, uint8_t node)
{
    char buf[320];
    ssr_format(node, buf, sizeof buf);
    out(s, "%s%s", prefix, buf);
}

/* ------------------------------------------------------------------ commands */

static void cmd_help(session *s)
{
    static const char *const lines[] = {
        "ID",
        "STATUS",
        "NET [ip=a.b.c.d] [mask=a.b.c.d] [gw=a.b.c.d]   (SAVE + REBOOT to apply)",
        "SAVE",
        "REBOOT",
        "SER <1-4> [baud=<n>] [data=7|8] [parity=N|E|O] [stop=1|2]",
        "CAN SCAN",
        "CAN <1-4> START [mode=fd|classic|listen] [nominal=<bit/s>] [data=<bit/s>]",
        "CAN <1-4> STOP | TX <id>#<data> | TX <id>##<f><data> | TEST",
        "SSR <node> [SET v=<V> i=<A> hot=0|1 noreg=0|1 timeout=<ms> | OFF | CLEAR | INFO]",
        "SSR ALL OFF",
        "STREAM [ON [ip=a.b.c.d] [batch=1-10] [fmt=bin|text] | OFF]",
        "IO SCAN",
        "RLY [1-4|all=on|off ...] [timeout=<ms>]",
        "GPIO [<1-4> [mode=in|out] [pull=none|up|down] [out=0|1]]",
        "AI [<1-2> [ZERO]]",
    };
    for (unsigned k = 0; k < sizeof lines / sizeof lines[0]; k++)
        out(s, "* %s", lines[k]);
    OK(s);
}

static void line_io(session *s, const char *prefix);
static void line_rly(session *s, const char *prefix);
static void line_gpio(session *s, const char *prefix, uint8_t n);
static void line_ai(session *s, const char *prefix, uint8_t n);

static void cmd_status(session *s)
{
    line_core(s, "* ");
    for (uint8_t ch = 1; ch <= CAN_CHANNELS; ch++)
        line_can(s, "* ", ch);
    for (uint8_t n = 0; n < SSR_NODES; n++)
        if (ssr_connected(n))
            line_ssr(s, "* ", n);
    for (uint8_t p = 1; p <= SER_PORTS; p++)
        line_ser(s, "* ", p);
    line_stream(s, "* ");
    line_io(s, "* ");
    if (io_present()) {
        line_rly(s, "* ");
        for (uint8_t k = 1; k <= IO_GPIOS; k++)
            line_gpio(s, "* ", k);
        for (uint8_t k = 1; k <= IO_AIS; k++)
            line_ai(s, "* ", k);
    }
    OK(s);
}

static void cmd_id(session *s)
{
    char sn[20];
    uint8_t m[6];
    serial_number(sn);
    net_mac(m);
    OK(s, " ThlHats core fw=%s sn=%s mac=%02X:%02X:%02X:%02X:%02X:%02X", FW_VERSION, sn,
       m[0], m[1], m[2], m[3], m[4], m[5]);
}

static void cmd_net(session *s, const args_t *a)
{
    static const char *const keys[] = { "ip", "mask", "gw", NULL };
    uint8_t ip[4], mask[4], gw[4], act[4];
    char b1[16], b2[16], b3[16], b4[16];
    if (!only_keys(s, a, 1, keys))
        return;
    memcpy(ip, settings.ip, 4);
    memcpy(mask, settings.mask, 4);
    memcpy(gw, settings.gw, 4);
    const char *v;
    if ((v = kv(a, 1, "ip")) && !parse_ip(v, ip)) { ERR(s, 400, "bad ip"); return; }
    if ((v = kv(a, 1, "mask")) && !parse_ip(v, mask)) { ERR(s, 400, "bad mask"); return; }
    if ((v = kv(a, 1, "gw")) && !parse_ip(v, gw)) { ERR(s, 400, "bad gw"); return; }
    memcpy(settings.ip, ip, 4);
    memcpy(settings.mask, mask, 4);
    memcpy(settings.gw, gw, 4);
    net_active_ip(act);
    OK(s, " NET ip=%s mask=%s gw=%s (active ip=%s)", ipstr(ip, b1), ipstr(mask, b2), ipstr(gw, b3), ipstr(act, b4));
}

static void cmd_save(session *s)
{
    for (uint8_t p = 1; p <= SER_PORTS; p++)
        settings.ser[p - 1u] = *ser_get(p);
    if (settings_save())
        OK(s, " saved");
    else
        ERR(s, 503, "flash write failed");
}

static void cmd_ser(session *s, const args_t *a)
{
    static const char *const keys[] = { "baud", "data", "parity", "stop", NULL };
    uint32_t p, v;
    if (a->argc < 2 || !parse_uint(a->argv[1], 1, SER_PORTS, &p)) {
        ERR(s, 400, "usage: SER <1-4> [baud=] [data=] [parity=] [stop=]");
        return;
    }
    if (!only_keys(s, a, 2, keys))
        return;
    ser_settings c = *ser_get((uint8_t)p);
    const char *val;
    if ((val = kv(a, 2, "baud"))) {
        if (!parse_uint(val, 300, 1000000u, &v)) { ERR(s, 400, "baud must be 300-1000000"); return; }
        c.baud = v;
    }
    if ((val = kv(a, 2, "data"))) {
        if (!parse_uint(val, 7, 8, &v)) { ERR(s, 400, "data must be 7 or 8"); return; }
        c.data = (uint8_t)v;
    }
    if ((val = kv(a, 2, "parity"))) {
        char pc = (char)toupper((unsigned char)val[0]);
        if (val[0] == 0 || val[1] != 0 || (pc != 'N' && pc != 'E' && pc != 'O')) { ERR(s, 400, "parity must be N, E or O"); return; }
        c.parity = pc;
    }
    if ((val = kv(a, 2, "stop"))) {
        if (!parse_uint(val, 1, 2, &v)) { ERR(s, 400, "stop must be 1 or 2"); return; }
        c.stop = (uint8_t)v;
    }
    if (!ser_valid(&c)) {
        ERR(s, 400, "data=7 needs parity=E/O or stop=2");
        return;
    }
    if (memcmp(&c, ser_get((uint8_t)p), sizeof c))
        ser_apply((uint8_t)p, &c);
    out(s, "OK SER %lu type=%s baud=%lu data=%u parity=%c stop=%u", (unsigned long)p,
        ser_rs485((uint8_t)p) ? "rs485" : "rs232", (unsigned long)ser_actual_baud((uint8_t)p),
        c.data, c.parity, c.stop);
}

static void cmd_can(session *s, const args_t *a)
{
    uint32_t ch;
    if (a->argc == 2 && ieq(a->argv[1], "SCAN")) {
        uint8_t m = can_detect();
        char list[16] = "";
        for (uint8_t i = 0; i < CAN_CHANNELS; i++)
            if (m & (1u << i))
                sprintf(list + strlen(list), "%s%u", list[0] ? "," : "", i + 1u);
        OK(s, " CAN present=%s", list[0] ? list : "none");
        return;
    }
    if (a->argc < 3 || !parse_uint(a->argv[1], 1, CAN_CHANNELS, &ch)) {
        ERR(s, 400, "usage: CAN SCAN | CAN <1-4> START|STOP|TX|TEST");
        return;
    }
    const char *op = a->argv[2];
    can_status st;
    can_get_status((uint8_t)ch, &st);

    if (ieq(op, "START")) {
        static const char *const keys[] = { "mode", "nominal", "data", NULL };
        if (!only_keys(s, a, 3, keys))
            return;
        can_mode mode = CAN_MODE_FD;
        uint32_t nominal = CAN_DEFAULT_NOMINAL, data = CAN_DEFAULT_DATA;
        const char *v;
        if ((v = kv(a, 3, "mode"))) {
            if (ieq(v, "fd")) mode = CAN_MODE_FD;
            else if (ieq(v, "classic")) mode = CAN_MODE_CLASSIC;
            else if (ieq(v, "listen")) mode = CAN_MODE_LISTEN;
            else { ERR(s, 400, "mode must be fd, classic or listen"); return; }
        }
        if ((v = kv(a, 3, "nominal")) && !parse_uint(v, 10000u, 1000000u, &nominal)) { ERR(s, 400, "bad nominal"); return; }
        if ((v = kv(a, 3, "data")) && !parse_uint(v, 10000u, 8000000u, &data)) { ERR(s, 400, "bad data"); return; }
        if (!can_timing_ok(nominal, data)) {
            ERR(s, 400, "bit rates %lu/%lu not possible from %lu MHz", (unsigned long)nominal,
                (unsigned long)data, (unsigned long)(CANCLK_HZ / 1000000u));
            return;
        }
        if (!st.present) {
            ERR(s, 404, "CAN %lu: no transceiver (CAN SCAN)", (unsigned long)ch);
            return;
        }
        if (!can_start((uint8_t)ch, mode, nominal, data)) {
            ERR(s, 503, "CAN %lu: start failed (bus stuck dominant?)", (unsigned long)ch);
            return;
        }
        out(s, "OK CAN %lu mode=%s nominal=%lu data=%lu", (unsigned long)ch, mode_name[mode],
            (unsigned long)nominal, mode == CAN_MODE_CLASSIC ? 0ul : (unsigned long)data);
    } else if (ieq(op, "STOP") && a->argc == 3) {
        can_stop((uint8_t)ch);
        out(s, "OK CAN %lu stopped", (unsigned long)ch);
    } else if (ieq(op, "TX") && a->argc == 4) {
        can_frame f;
        if (!parse_frame(a->argv[3], &f)) {
            ERR(s, 400, "frame: <id>#<data>, <id>##<f><data> or <id>#R");
            return;
        }
        if (!st.running)
            ERR(s, 503, "CAN %lu not running", (unsigned long)ch);
        else if (st.mode == CAN_MODE_LISTEN)
            ERR(s, 503, "CAN %lu is listen-only", (unsigned long)ch);
        else if (st.mode == CAN_MODE_CLASSIC && (f.flags & CAN_FDF))
            ERR(s, 400, "CAN %lu is in classic mode", (unsigned long)ch);
        else if (!can_send((uint8_t)ch, &f))
            ERR(s, 503, "CAN %lu TX FIFO full", (unsigned long)ch);
        else
            OK(s);
    } else if (ieq(op, "TEST") && a->argc == 3) {
        if (can_selftest((uint8_t)ch))
            OK(s, " pass");
        else
            ERR(s, 409, "fail");
    } else {
        ERR(s, 400, "usage: CAN <1-4> START|STOP|TX|TEST");
    }
}

static bool ssr_ready(session *s, uint8_t node)
{
    can_status c;
    can_get_status(SSR_CAN, &c);
    if (!c.running || c.mode == CAN_MODE_LISTEN) {
        ERR(s, 503, "CAN %u not running", SSR_CAN);
        return false;
    }
    if (!ssr_connected(node)) {
        ERR(s, 404, "SSR %u not connected", node);
        return false;
    }
    return true;
}

static void start_set(session *s, uint8_t node, uint16_t v, uint16_t i, uint8_t flags, uint16_t timeout)
{
    uint8_t seq;
    if (!ssr_ready(s, node))
        return;
    if (!ssr_send_set(node, v, i, flags, timeout, &seq)) {
        ERR(s, 503, "CAN %u TX FIFO full", SSR_CAN);
        return;
    }
    s->pend = P_SET;
    s->pend_t0 = millis();
    s->pend_node = node;
    s->pend_seq = seq;
    s->pend_v = v;
    s->pend_i = i;
    s->pend_flags = flags;
    s->pend_timeout = timeout;
}

static void cmd_ssr(session *s, const args_t *a)
{
    uint32_t node;
    if (a->argc == 3 && ieq(a->argv[1], "ALL") && ieq(a->argv[2], "OFF")) {
        can_status c;
        can_get_status(SSR_CAN, &c);
        if (!c.running || !ssr_send_all_off())
            ERR(s, 503, "CAN %u not running", SSR_CAN);
        else
            OK(s);
        return;
    }
    if (a->argc < 2 || !parse_uint(a->argv[1], 0, SSR_NODES - 1u, &node)) {
        ERR(s, 400, "usage: SSR <0-15> [SET|OFF|CLEAR|INFO] | SSR ALL OFF");
        return;
    }
    uint8_t n = (uint8_t)node;

    if (a->argc == 2) {
        char buf[320];
        if (!ssr_connected(n)) {
            ERR(s, 404, "SSR %u not connected", n);
            return;
        }
        ssr_format(n, buf, sizeof buf);
        out(s, "OK %s", buf);
        return;
    }
    const char *op = a->argv[2];
    if (ieq(op, "SET")) {
        static const char *const keys[] = { "v", "i", "hot", "noreg", "timeout", NULL };
        uint16_t v, i;
        uint32_t hot, noreg, timeout;
        if (!only_keys(s, a, 3, keys))
            return;
        const char *sv = kv(a, 3, "v"), *si = kv(a, 3, "i"), *sh = kv(a, 3, "hot"), *sn = kv(a, 3, "noreg");
        const char *st = kv(a, 3, "timeout");
        if (!sv || !si || !sh || !sn || !st) {
            ERR(s, 400, "SET needs all of v= i= hot= noreg= timeout=");
            return;
        }
        if (!parse_centi(sv, 65535u, &v)) { ERR(s, 400, "v must be 0-655.35"); return; }
        if (!parse_centi(si, 65535u, &i)) { ERR(s, 400, "i must be 0-655.35"); return; }
        if (!parse_uint(sh, 0, 1, &hot)) { ERR(s, 400, "hot must be 0 or 1"); return; }
        if (!parse_uint(sn, 0, 1, &noreg)) { ERR(s, 400, "noreg must be 0 or 1"); return; }
        if (!parse_uint(st, 100, 60000u, &timeout)) { ERR(s, 400, "timeout must be 100-60000 ms"); return; }
        start_set(s, n, v, i, (uint8_t)(hot | (noreg << 1)), (uint16_t)timeout);
    } else if (ieq(op, "OFF") && a->argc == 3) {
        start_set(s, n, 0, 0, 0, OFF_TIMEOUT_MS);
    } else if (ieq(op, "CLEAR") && a->argc == 3) {
        if (!ssr_ready(s, n))
            return;
        if (!ssr_send_clear(n)) {
            ERR(s, 503, "CAN %u TX FIFO full", SSR_CAN);
            return;
        }
        s->pend = P_CLEAR;
        s->pend_t0 = millis();
        s->pend_node = n;
    } else if (ieq(op, "INFO") && a->argc == 3) {
        if (!ssr_ready(s, n))
            return;
        if (!ssr_send_info_req(n)) {
            ERR(s, 503, "CAN %u TX FIFO full", SSR_CAN);
            return;
        }
        s->pend = P_INFO;
        s->pend_t0 = millis();
        s->pend_node = n;
    } else {
        ERR(s, 400, "usage: SSR <node> [SET v= i= hot= noreg= timeout= | OFF | CLEAR | INFO]");
    }
}

static void cmd_stream(session *s, const args_t *a)
{
    if (a->argc == 1) {
        line_stream(s, "OK ");
        return;
    }
    if (ieq(a->argv[1], "OFF") && a->argc == 2) {
        ssr_stream.on = false;
        OK(s, " STREAM off");
        return;
    }
    if (!ieq(a->argv[1], "ON")) {
        ERR(s, 400, "usage: STREAM [ON [ip=] [batch=] [fmt=] | OFF]");
        return;
    }
    static const char *const keys[] = { "ip", "batch", "fmt", NULL };
    if (!only_keys(s, a, 2, keys))
        return;
    stream_cfg c = ssr_stream;
    uint32_t b;
    const char *v;
    if ((v = kv(a, 2, "ip"))) {
        if (!parse_ip(v, c.ip)) { ERR(s, 400, "bad ip"); return; }
    } else if (s->is_uart) {
        ERR(s, 400, "ip= needed on the debug UART");
        return;
    } else {
        memcpy(c.ip, s->peer, 4);
    }
    if ((v = kv(a, 2, "batch"))) {
        if (!parse_uint(v, 1, 10, &b)) { ERR(s, 400, "batch must be 1-10"); return; }
        c.batch = (uint8_t)b;
    }
    if ((v = kv(a, 2, "fmt"))) {
        if (ieq(v, "bin")) c.text = false;
        else if (ieq(v, "text")) c.text = true;
        else { ERR(s, 400, "fmt must be bin or text"); return; }
    }
    c.on = true;
    ssr_stream = c;
    ssr_stream_reset();
    char ip[16];
    OK(s, " STREAM on ip=%s batch=%u fmt=%s", ipstr(c.ip, ip), c.batch, c.text ? "text" : "bin");
}

/* ------------------------------------------------------------------ io-card */

static const char *const pull_name[] = { [PULL_NONE] = "none", [PULL_UP] = "up", [PULL_DOWN] = "down" };

static bool io_ready(session *s)
{
    if (!io_present()) {
        ERR(s, 404, "io-card not detected (IO SCAN)");
        return false;
    }
    return true;
}

static void mv_str(int32_t mv, char *buf)
{
    sprintf(buf, "%s%ld.%03ld", mv < 0 ? "-" : "", (long)((mv < 0 ? -mv : mv) / 1000),
            (long)((mv < 0 ? -mv : mv) % 1000));
}

static void line_rly(session *s, const char *prefix)
{
    char exp[16] = "";
    for (uint8_t n = 1; n <= IO_RELAYS; n++)
        if (io_relay_expired(n))
            sprintf(exp + strlen(exp), "%s%u", exp[0] ? "," : "", n);
    out(s, "%sRLY 1=%s 2=%s 3=%s 4=%s timeout=%lu,%lu,%lu,%lu expired=%s", prefix,
        io_relay_get(1) ? "on" : "off", io_relay_get(2) ? "on" : "off",
        io_relay_get(3) ? "on" : "off", io_relay_get(4) ? "on" : "off",
        (unsigned long)io_relay_timeout(1), (unsigned long)io_relay_timeout(2),
        (unsigned long)io_relay_timeout(3), (unsigned long)io_relay_timeout(4), exp[0] ? exp : "none");
}

static void line_gpio(session *s, const char *prefix, uint8_t n)
{
    gpio_mode m;
    gpio_pull pl;
    bool o, lv;
    io_gpio_get(n, &m, &pl, &o, &lv);
    out(s, "%sGPIO %u mode=%s pull=%s out=%u level=%u", prefix, n, m == GPIO_OUT ? "out" : "in",
        pull_name[pl], o, lv);
}

static void line_ai(session *s, const char *prefix, uint8_t n)
{
    ai_reading r;
    char d[16], p[16], q[16];
    io_ai_read(n, &r);
    mv_str(r.diff_mv, d);
    mv_str(r.p_mv, p);
    mv_str(r.n_mv, q);
    out(s, "%sAI %u v=%s p=%s n=%s over=%u", prefix, n, d, p, q, r.over);
}

static void line_io(session *s, const char *prefix)
{
    uint16_t v = io_vmid_mv();
    out(s, "%sIO present=%u vmid=%u.%03u", prefix, io_present(), v / 1000u, v % 1000u);
}

static void cmd_io(session *s, const args_t *a)
{
    if (a->argc == 2 && ieq(a->argv[1], "SCAN")) {
        io_detect();
        line_io(s, "OK ");
    } else if (a->argc == 1) {
        line_io(s, "OK ");
    } else {
        ERR(s, 400, "usage: IO [SCAN]");
    }
}

static bool parse_onoff(const char *v, bool *on)
{
    if (ieq(v, "on") || ieq(v, "1")) { *on = true; return true; }
    if (ieq(v, "off") || ieq(v, "0")) { *on = false; return true; }
    return false;
}

/* RLY [1=on|off] [2=..] [3=..] [4=..] [all=on|off] [timeout=<ms>]: the named outputs
 * change (all= first, then the numbered ones) and get the failsafe timeout; no
 * timeout = no failsafe. A bare RLY reports without touching the timers. */
static void cmd_rly(session *s, const args_t *a)
{
    static const char *const keys[] = { "1", "2", "3", "4", "all", "timeout", NULL };
    bool set[IO_RELAYS], on[IO_RELAYS], all_on = false, any = false;
    uint32_t timeout = 0;
    const char *v;
    if (!io_ready(s) || !only_keys(s, a, 1, keys))
        return;
    if ((v = kv(a, 1, "timeout")) && !parse_uint(v, 100, 3600000u, &timeout)) {
        ERR(s, 400, "timeout must be 100-3600000 ms");
        return;
    }
    bool all = false;
    if ((v = kv(a, 1, "all"))) {
        if (!parse_onoff(v, &all_on)) { ERR(s, 400, "all must be on or off"); return; }
        all = true;
    }
    for (uint8_t n = 1; n <= IO_RELAYS; n++) {
        char key[2] = { (char)('0' + n), 0 };
        set[n - 1u] = all;
        on[n - 1u] = all_on;
        if ((v = kv(a, 1, key))) {
            if (!parse_onoff(v, &on[n - 1u])) { ERR(s, 400, "relay %u must be on or off", n); return; }
            set[n - 1u] = true;
        }
        any |= set[n - 1u];
    }
    if (!any && a->argc > 1) {
        ERR(s, 400, "no relay given (1= .. 4= or all=)");
        return;
    }
    for (uint8_t n = 1; n <= IO_RELAYS; n++)
        if (set[n - 1u])
            io_relay_set(n, on[n - 1u], timeout);
    line_rly(s, "OK ");
}

static void cmd_gpio(session *s, const args_t *a)
{
    uint32_t n;
    if (!io_ready(s))
        return;
    if (a->argc == 1) {
        for (uint8_t k = 1; k <= IO_GPIOS; k++)
            line_gpio(s, "* ", k);
        OK(s);
        return;
    }
    if (!parse_uint(a->argv[1], 1, IO_GPIOS, &n)) {
        ERR(s, 400, "usage: GPIO [<1-4> [mode=in|out] [pull=none|up|down] [out=0|1]]");
        return;
    }
    static const char *const keys[] = { "mode", "pull", "out", NULL };
    if (!only_keys(s, a, 2, keys))
        return;
    gpio_mode m;
    gpio_pull pl;
    bool o, lv;
    uint32_t ov;
    const char *v;
    io_gpio_get((uint8_t)n, &m, &pl, &o, &lv);
    if ((v = kv(a, 2, "mode"))) {
        if (ieq(v, "in")) m = GPIO_IN;
        else if (ieq(v, "out")) m = GPIO_OUT;
        else { ERR(s, 400, "mode must be in or out"); return; }
    }
    if ((v = kv(a, 2, "pull"))) {
        if (ieq(v, "none")) pl = PULL_NONE;
        else if (ieq(v, "up")) pl = PULL_UP;
        else if (ieq(v, "down")) pl = PULL_DOWN;
        else { ERR(s, 400, "pull must be none, up or down"); return; }
    }
    if ((v = kv(a, 2, "out"))) {
        if (!parse_uint(v, 0, 1, &ov)) { ERR(s, 400, "out must be 0 or 1"); return; }
        o = ov;
    }
    io_gpio_config((uint8_t)n, m, pl, o);
    delay_us(5);                        /* let the pin settle before reading the level */
    line_gpio(s, "OK ", (uint8_t)n);
}

static void cmd_ai(session *s, const args_t *a)
{
    uint32_t n;
    if (!io_ready(s))
        return;
    if (a->argc == 1) {
        for (uint8_t k = 1; k <= IO_AIS; k++)
            line_ai(s, "* ", k);
        OK(s);
        return;
    }
    if (!parse_uint(a->argv[1], 1, IO_AIS, &n)) {
        ERR(s, 400, "usage: AI [<1-2> [ZERO]]");
        return;
    }
    if (a->argc == 2) {
        line_ai(s, "OK ", (uint8_t)n);
    } else if (a->argc == 3 && ieq(a->argv[2], "ZERO")) {
        int16_t z = io_ai_zero((uint8_t)n);
        char d[16];
        mv_str((int32_t)((int64_t)z * 3300 * 10130 / ((int64_t)4096 * 64 * 130)), d);
        OK(s, " AI %lu zero=%s (SAVE to keep)", (unsigned long)n, d);
    } else {
        ERR(s, 400, "usage: AI [<1-2> [ZERO]]");
    }
}

void cmd_execute(session *s, char *line)
{
    args_t a = { 0 };
    for (char *tok = strtok(line, " \t"); tok; tok = strtok(NULL, " \t")) {
        if (a.argc == MAX_ARGS) {
            ERR(s, 400, "too many arguments");
            return;
        }
        a.argv[a.argc++] = tok;
    }
    if (!a.argc)
        return;                         /* empty line: no response */

    const char *c = a.argv[0];
    if (ieq(c, "ID") && a.argc == 1)            cmd_id(s);
    else if (ieq(c, "HELP") || ieq(c, "?"))     cmd_help(s);
    else if (ieq(c, "STATUS") && a.argc == 1)   cmd_status(s);
    else if (ieq(c, "NET"))                     cmd_net(s, &a);
    else if (ieq(c, "SAVE") && a.argc == 1)     cmd_save(s);
    else if (ieq(c, "REBOOT") && a.argc == 1) {
        OK(s, " rebooting");
        s->pend = P_REBOOT;
        s->pend_t0 = millis();
    }
    else if (ieq(c, "SER"))                     cmd_ser(s, &a);
    else if (ieq(c, "CAN"))                     cmd_can(s, &a);
    else if (ieq(c, "SSR"))                     cmd_ssr(s, &a);
    else if (ieq(c, "STREAM"))                  cmd_stream(s, &a);
    else if (ieq(c, "IO"))                      cmd_io(s, &a);
    else if (ieq(c, "RLY"))                     cmd_rly(s, &a);
    else if (ieq(c, "GPIO"))                    cmd_gpio(s, &a);
    else if (ieq(c, "AI"))                      cmd_ai(s, &a);
    else                                        ERR(s, 400, "unknown command '%s' (HELP)", c);
}

static const char *ack_reason(uint8_t r)
{
    switch (r) {
    case 1: return "fault latched (SSR CLEAR first)";
    case 2: return "voltage above build limit";
    case 3: return "current above build limit";
    case 4: return "hot switching refused";
    default: return "refused";
    }
}

void cmd_poll(session *s)
{
    if (!s->pend)
        return;
    uint32_t now = millis(), age = now - s->pend_t0;
    const ssr_t *r = ssr_get(s->pend_node);

    switch (s->pend) {
    case P_SET:
        if (r->ack_ms && r->ack_seq == s->pend_seq) {
            s->pend = P_NONE;
            if (r->ack_result == 0) {
                ssr_note_set(s->pend_node, s->pend_i, s->pend_timeout);
                out(s, "OK SSR %u v=%u.%02u i=%u.%02u hot=%u noreg=%u timeout=%u", s->pend_node,
                    s->pend_v / 100u, s->pend_v % 100u, s->pend_i / 100u, s->pend_i % 100u,
                    s->pend_flags & 1u, (s->pend_flags >> 1) & 1u, s->pend_timeout);
            } else {
                ERR(s, 409, "SSR %u: %s", s->pend_node, ack_reason(r->ack_result));
            }
        } else if (age > SET_ACK_MS) {
            s->pend = P_NONE;
            ERR(s, 504, "SSR %u: no SET_ACK", s->pend_node);
        }
        break;
    case P_CLEAR:
        if (r->status_ms && (int32_t)(r->status_ms - s->pend_t0) > 0) {
            s->pend = P_NONE;
            out(s, "OK SSR %u faults=0x%04X", s->pend_node, r->faults);
        } else if (age > CLEAR_MS) {
            s->pend = P_NONE;
            ERR(s, 504, "SSR %u: no STATUS after CLEAR", s->pend_node);
        }
        break;
    case P_INFO:
        if (r->info_ms) {
            s->pend = P_NONE;
            out(s, "OK SSR %u type=%s fw=%u.%u build=%s", s->pend_node,
                r->type == 1u ? "can-ssr" : "unknown", r->fw_major, r->fw_minor, ssr_build_name(r->build));
        } else if (age > INFO_MS) {
            s->pend = P_NONE;
            ERR(s, 504, "SSR %u: no INFO", s->pend_node);
        }
        break;
    case P_REBOOT:
        if (age > REBOOT_MS)
            board_reset();
        break;
    default:
        s->pend = P_NONE;
        break;
    }
}

bool cmd_busy(const session *s)
{
    return s->pend != P_NONE;
}
