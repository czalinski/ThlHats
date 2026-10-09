#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "board.h"
#include "uart.h"
#include "canfd.h"
#include "w6100.h"
#include "console.h"

#define LINE_MAX    160u
#define MAX_ARGS    6u

static char line[LINE_MAX];
static uint32_t line_len;
static bool monitor = true;
static bool eth_ok;

static const char *const mode_name[] = {
    [CAN_MODE_FD] = "fd", [CAN_MODE_CLASSIC] = "classic",
    [CAN_MODE_LISTEN] = "listen", [CAN_MODE_LOOPBACK] = "loopback",
};

bool console_monitor(void)
{
    return monitor;
}

void console_print_frame(uint8_t ch, const can_frame *f)
{
    char buf[16 + 64 * 3 + 24];
    char *p = buf;
    static const char hex[] = "0123456789ABCDEF";

    /* candump style: can1  123   [4]  DE AD BE EF */
    uart_printf((f->flags & CAN_EXT) ? "can%u  %08lX  " : "can%u  %03lX  ", ch, (unsigned long)f->id);
    if (f->flags & CAN_FDF)
        uart_printf("[%02u] ", f->len);
    else
        uart_printf(" [%u] ", f->len);
    for (uint8_t k = 0; k < f->len; k++) {
        *p++ = ' ';
        *p++ = hex[f->data[k] >> 4];
        *p++ = hex[f->data[k] & 15u];
    }
    *p = 0;
    uart_puts(buf);
    if (f->flags & CAN_RTR)
        uart_puts("  remote");
    if (f->flags & CAN_FDF)
        uart_printf("  (FD%s%s)", (f->flags & CAN_BRS) ? ",BRS" : "", (f->flags & CAN_ESI) ? ",ESI" : "");
    uart_puts("\n");
}

static void print_status(uint8_t ch)
{
    can_status s;
    can_get_status(ch, &s);
    uart_printf("can%u  %-7s ", ch, s.present ? "present" : "absent");
    if (!s.running) {
        uart_puts("stopped\n");
        return;
    }
    uart_printf("%-8s %4lu k", mode_name[s.mode], (unsigned long)(s.nominal / 1000u));
    if (s.data)
        uart_printf(" / %4lu k", (unsigned long)(s.data / 1000u));
    else
        uart_puts("         ");
    uart_printf("  %s  TEC %3u REC %3u  rx %lu tx %lu", s.bus_off ? "BUS-OFF" : s.error_passive ? "passive" : "active ",
                s.tec, s.rec, (unsigned long)s.rx_frames, (unsigned long)s.tx_frames);
    if (s.rx_overflows || s.tx_full)
        uart_printf("  rx-overflow %lu tx-full %lu", (unsigned long)s.rx_overflows, (unsigned long)s.tx_full);
    uart_puts("\n");
}

static void print_present(uint8_t mask)
{
    uart_printf("can-card: %s (", mask ? "found" : "not found");
    for (uint8_t i = 0; i < CAN_CHANNELS; i++)
        uart_printf("%sCAN%u %s", i ? ", " : "", i + 1u, (mask & (1u << i)) ? "yes" : "no");
    uart_puts(")\n");
}

static uint8_t present_mask(void)
{
    uint8_t mask = 0;
    for (uint8_t ch = 1; ch <= CAN_CHANNELS; ch++) {
        can_status s;
        can_get_status(ch, &s);
        if (s.present)
            mask |= 1u << (ch - 1u);
    }
    return mask;
}

/* "1".."4" -> that channel; "all" -> 0 */
static int parse_ch(const char *a)
{
    if (!a)
        return -1;
    if (!strcmp(a, "all"))
        return 0;
    if (a[0] >= '1' && a[0] <= '0' + (int)CAN_CHANNELS && !a[1])
        return a[0] - '0';
    return -1;
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    c = (char)toupper((unsigned char)c);
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/* cansend syntax: <id>#<data>, <id>#R, <id>##<flags><data> (flags: 1 = BRS);
 * 3 hex digits = standard, 8 = extended id; data hex bytes, '.' allowed */
static bool parse_frame(const char *s, can_frame *f)
{
    const char *hash = strchr(s, '#');
    if (!hash)
        return false;
    memset(f, 0, sizeof *f);
    uint32_t idlen = (uint32_t)(hash - s);
    if (idlen != 3u && idlen != 8u)
        return false;
    for (uint32_t k = 0; k < idlen; k++) {
        int v = hexval(s[k]);
        if (v < 0)
            return false;
        f->id = (f->id << 4) | (uint32_t)v;
    }
    if (idlen == 8u) {
        f->flags |= CAN_EXT;
        if (f->id > 0x1FFFFFFFu) return false;
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
        if (*p == '.') { p++; continue; }
        int hi = hexval(p[0]), lo = p[1] ? hexval(p[1]) : -1;
        if (hi < 0 || lo < 0 || f->len >= max)
            return false;
        f->data[f->len++] = (uint8_t)((hi << 4) | lo);
        p += 2;
    }
    if ((f->flags & CAN_FDF) && can_dlc_to_len(can_len_to_dlc(f->len)) != f->len) {
        uart_printf("note: FD length %u padded to %u with zeros\n", f->len,
                    can_dlc_to_len(can_len_to_dlc(f->len)));
        f->len = can_dlc_to_len(can_len_to_dlc(f->len));
    }
    return true;
}

static void cmd_help(void)
{
    uart_puts("info                          firmware, clocks, W6100, card detection\n"
              "scan                          detect transceivers on stopped channels\n"
              "can                           channel status\n"
              "start <ch|all> [fd|classic|listen] [nominal] [data]   (default fd 500000 2000000)\n"
              "stop <ch|all>\n"
              "tx <ch> <id>#<data>           classic frame, e.g. tx 1 123#DEADBEEF, 1ABCDEF0#, 100#R\n"
              "tx <ch> <id>##<f><data>       FD frame, f = 1 for bit rate switch, e.g. tx 2 123##1112233\n"
              "mon [on|off]                  print received frames\n"
              "test <ch|all>                 internal loopback self-test (no bus traffic)\n");
}

static void cmd_info(void)
{
    uart_printf("ThlHats core firmware %s (%s %s)\n", FW_VERSION, __DATE__, __TIME__);
    uart_printf("SYSCLK %lu MHz, CAN clock %lu MHz\n", (unsigned long)(SYSCLK_HZ / 1000000u),
                (unsigned long)(CANCLK_HZ / 1000000u));
    if (eth_ok) {
        uint8_t physr = w6100_read8(W6100_PHYSR);
        uart_printf("W6100: version %04X, link %s", w6100_version(), (physr & 1u) ? "up" : "down");
        if (physr & 1u)
            uart_printf(" %s %s", (physr & 2u) ? "10M" : "100M", (physr & 4u) ? "half" : "full");
        uart_puts("\n");
    } else {
        uart_puts("W6100: not responding\n");
    }
    print_present(present_mask());
}

static void cmd_start(int argc, char **argv)
{
    int ch = parse_ch(argc > 1 ? argv[1] : NULL);
    if (ch < 0) {
        uart_puts("usage: start <ch|all> [fd|classic|listen] [nominal] [data]\n");
        return;
    }
    can_mode mode = CAN_MODE_FD;
    int a = 2;
    if (argc > a && isalpha((unsigned char)argv[a][0])) {
        if (!strcmp(argv[a], "fd")) mode = CAN_MODE_FD;
        else if (!strcmp(argv[a], "classic")) mode = CAN_MODE_CLASSIC;
        else if (!strcmp(argv[a], "listen")) mode = CAN_MODE_LISTEN;
        else {
            uart_puts("mode: fd, classic or listen\n");
            return;
        }
        a++;
    }
    uint32_t nominal = argc > a ? strtoul(argv[a++], NULL, 0) : CAN_DEFAULT_NOMINAL;
    uint32_t data = argc > a ? strtoul(argv[a++], NULL, 0) : CAN_DEFAULT_DATA;
    if (!can_timing_ok(nominal, data)) {
        uart_printf("bit rates %lu / %lu not possible from %lu MHz\n", (unsigned long)nominal,
                    (unsigned long)data, (unsigned long)(CANCLK_HZ / 1000000u));
        return;
    }
    for (uint8_t c = 1; c <= CAN_CHANNELS; c++) {
        if (ch && c != ch)
            continue;
        can_status s;
        can_get_status(c, &s);
        if (!s.present) {
            if (ch)
                uart_printf("can%u: no transceiver (run scan)\n", c);
            continue;
        }
        if (!can_start(c, mode, nominal, data))
            uart_printf("can%u: start failed (bus stuck dominant?)\n", c);
        print_status(c);
    }
}

static void cmd_stop(int argc, char **argv)
{
    int ch = parse_ch(argc > 1 ? argv[1] : NULL);
    if (ch < 0) {
        uart_puts("usage: stop <ch|all>\n");
        return;
    }
    for (uint8_t c = 1; c <= CAN_CHANNELS; c++)
        if (!ch || c == ch)
            can_stop(c);
}

static void cmd_tx(int argc, char **argv)
{
    int ch = parse_ch(argc > 1 ? argv[1] : NULL);
    can_frame f;
    if (ch <= 0 || argc < 3 || !parse_frame(argv[2], &f)) {
        uart_puts("usage: tx <ch> <id>#<data> | <id>##<flags><data> | <id>#R\n");
        return;
    }
    can_status s;
    can_get_status((uint8_t)ch, &s);
    if (!s.running)
        uart_printf("can%d: not running\n", ch);
    else if (s.mode == CAN_MODE_CLASSIC && (f.flags & CAN_FDF))
        uart_printf("can%d: classic mode, FD frame refused\n", ch);
    else if (!can_send((uint8_t)ch, &f))
        uart_printf("can%d: TX FIFO full\n", ch);
}

static void cmd_test(int argc, char **argv)
{
    int ch = parse_ch(argc > 1 ? argv[1] : NULL);
    if (ch < 0) {
        uart_puts("usage: test <ch|all>\n");
        return;
    }
    for (uint8_t c = 1; c <= CAN_CHANNELS; c++)
        if (!ch || c == ch)
            uart_printf("can%u loopback: %s\n", c, can_selftest(c) ? "pass" : "FAIL");
}

static void execute(char *s)
{
    char *argv[MAX_ARGS];
    int argc = 0;
    for (char *tok = strtok(s, " \t"); tok && argc < (int)MAX_ARGS; tok = strtok(NULL, " \t"))
        argv[argc++] = tok;
    if (!argc)
        return;

    if (!strcmp(argv[0], "help") || !strcmp(argv[0], "?"))
        cmd_help();
    else if (!strcmp(argv[0], "info"))
        cmd_info();
    else if (!strcmp(argv[0], "scan"))
        print_present(can_detect());
    else if (!strcmp(argv[0], "can"))
        for (uint8_t c = 1; c <= CAN_CHANNELS; c++)
            print_status(c);
    else if (!strcmp(argv[0], "start"))
        cmd_start(argc, argv);
    else if (!strcmp(argv[0], "stop"))
        cmd_stop(argc, argv);
    else if (!strcmp(argv[0], "tx"))
        cmd_tx(argc, argv);
    else if (!strcmp(argv[0], "mon")) {
        if (argc > 1)
            monitor = !strcmp(argv[1], "on");
        uart_printf("monitor %s\n", monitor ? "on" : "off");
    } else if (!strcmp(argv[0], "test"))
        cmd_test(argc, argv);
    else
        uart_printf("unknown command '%s' (help)\n", argv[0]);
}

void console_init(void)
{
    eth_ok = w6100_init();
    uart_puts("\n");
    cmd_info();
    for (uint8_t c = 1; c <= CAN_CHANNELS; c++)
        print_status(c);
    uart_puts("> ");
}

void console_poll(void)
{
    int c;
    while ((c = uart_getc()) >= 0) {
        if (c == '\r' || c == '\n') {
            uart_puts("\n");
            line[line_len] = 0;
            execute(line);
            line_len = 0;
            uart_puts("> ");
        } else if (c == 8 || c == 127) {
            if (line_len) {
                line_len--;
                uart_puts("\b \b");
            }
        } else if (c >= ' ' && line_len < LINE_MAX - 1u) {
            line[line_len++] = (char)c;
            uart_putc((char)c);
        }
    }
}
