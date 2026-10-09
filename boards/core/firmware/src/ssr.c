#include <stdio.h>
#include <string.h>
#include "board.h"
#include "canfd.h"
#include "net.h"
#include "ssr.h"

/* CAN identifiers: (function << 4) | node */
#define F_ALL_OFF   0x00u
#define F_HOST_HB   0x01u
#define F_FAULT     0x08u
#define F_SET       0x10u
#define F_CLEAR     0x11u
#define F_INFO_REQ  0x14u
#define F_MEAS      0x20u
#define F_STATUS    0x21u
#define F_INFO      0x22u
#define F_SET_ACK   0x24u

#define HB_MS       250u
#define BATCH_MAX   10u

typedef struct {
    uint32_t t;
    uint16_t vin, vout, iavg, ipeak;
} sample_t;

static ssr_t node_state[SSR_NODES];
static sample_t pending[SSR_NODES][BATCH_MAX];
static uint8_t pending_n[SSR_NODES];
static uint32_t stream_seq[SSR_NODES];
static uint8_t set_seq;
static uint32_t hb_ms;

stream_cfg ssr_stream = { .batch = 5 };

static uint16_t u16le(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

static void put16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}

static void put32(uint8_t *p, uint32_t v)
{
    put16(p, (uint16_t)v);
    put16(p + 2, (uint16_t)(v >> 16));
}

static void stream_flush(uint8_t node)
{
    uint8_t n = pending_n[node];
    if (!n)
        return;
    pending_n[node] = 0;
    if (!ssr_stream.on)
        return;

    uint8_t buf[12 + 12 * BATCH_MAX];
    char *txt = (char *)buf;
    uint16_t len = 0;
    const ssr_t *s = &node_state[node];

    if (ssr_stream.text) {
        static char line[64 * BATCH_MAX];
        txt = line;
        for (uint8_t k = 0; k < n; k++) {
            const sample_t *p = &pending[node][k];
            len += (uint16_t)snprintf(line + len, sizeof line - len, "%u %lu %u.%02u %u.%02u %u.%02u %u.%02u\n",
                                      node, (unsigned long)p->t, p->vin / 100u, p->vin % 100u,
                                      p->vout / 100u, p->vout % 100u, p->iavg / 100u, p->iavg % 100u,
                                      p->ipeak / 100u, p->ipeak % 100u);
        }
    } else {
        buf[0] = 0x53;
        buf[1] = 1;
        buf[2] = node;
        buf[3] = n;
        put32(buf + 4, stream_seq[node]);
        buf[8] = s->state;
        buf[9] = 0;
        put16(buf + 10, s->faults);
        for (uint8_t k = 0; k < n; k++) {
            const sample_t *p = &pending[node][k];
            uint8_t *q = buf + 12 + 12 * k;
            put32(q, p->t);
            put16(q + 4, p->vin);
            put16(q + 6, p->vout);
            put16(q + 8, p->iavg);
            put16(q + 10, p->ipeak);
        }
        len = (uint16_t)(12 + 12 * n);
    }
    stream_seq[node]++;
    if (udp_sendto(SOCK_STREAM, ssr_stream.ip, (uint16_t)SSR_PORT(node), (const uint8_t *)txt, len))
        ssr_stream.sent++;
    else
        ssr_stream.dropped++;
}

void ssr_stream_reset(void)
{
    memset(pending_n, 0, sizeof pending_n);
    memset(stream_seq, 0, sizeof stream_seq);
    ssr_stream.sent = ssr_stream.dropped = 0;
}

void ssr_frame(const can_frame *f)
{
    if (f->flags & (CAN_EXT | CAN_RTR))
        return;
    uint8_t fn = (uint8_t)(f->id >> 4), node = f->id & 15u;
    ssr_t *s = &node_state[node];
    const uint8_t *d = f->data;
    uint32_t now = millis();

    switch (fn) {
    case F_MEAS:
        if (f->len < 8u)
            return;
        s->vin = u16le(d);
        s->vout = u16le(d + 2);
        s->iavg = u16le(d + 4);
        s->ipeak = u16le(d + 6);
        if (ssr_stream.on) {
            sample_t *p = &pending[node][pending_n[node]++];
            *p = (sample_t){ now, s->vin, s->vout, s->iavg, s->ipeak };
            if (pending_n[node] >= ssr_stream.batch)
                stream_flush(node);
        }
        break;
    case F_STATUS:
        if (f->len < 8u)
            return;
        s->state = d[0];
        s->build = d[1];
        s->faults = u16le(d + 2);
        s->warnings = d[4];
        s->v12 = d[5];
        s->vset = u16le(d + 6);
        s->status_ms = now ? now : 1u;
        break;
    case F_FAULT:
        if (f->len < 8u)
            return;
        s->faults = u16le(d);
        s->state = d[3];
        break;
    case F_INFO:
        if (f->len < 4u)
            return;
        s->type = d[0];
        s->fw_major = d[1];
        s->fw_minor = d[2];
        s->build = d[3];
        s->info_ms = now ? now : 1u;
        break;
    case F_SET_ACK:
        if (f->len < 2u)
            return;
        s->ack_seq = d[0];
        s->ack_result = d[1];
        s->ack_ms = now ? now : 1u;
        break;
    default:
        return;                         /* host -> node functions, other traffic */
    }
    s->last_ms = now ? now : 1u;
}

static bool send(uint8_t fn, uint8_t node, const uint8_t *data, uint8_t len)
{
    can_frame f = { .id = (uint32_t)((fn << 4) | node), .len = len, .flags = 0 };
    if (len)
        memcpy(f.data, data, len);
    return can_send(SSR_CAN, &f);
}

void ssr_poll(bool host_alive)
{
    uint32_t now = millis();
    can_status cs;
    can_get_status(SSR_CAN, &cs);
    if (host_alive && cs.running && cs.mode != CAN_MODE_LISTEN && now - hb_ms >= HB_MS) {
        hb_ms = now;
        send(F_HOST_HB, 0, NULL, 0);
    }
    /* a node that went quiet keeps no half-filled datagram */
    for (uint8_t n = 0; n < SSR_NODES; n++)
        if (pending_n[n] && !ssr_connected(n))
            stream_flush(n);
}

bool ssr_connected(uint8_t node)
{
    const ssr_t *s = &node_state[node & 15u];
    return s->last_ms && millis() - s->last_ms < SSR_SEEN_MS;
}

const ssr_t *ssr_get(uint8_t node)
{
    return &node_state[node & 15u];
}

const char *ssr_build_name(uint8_t build)
{
    static const char *const names[] = { "unknown", "HC", "STD", "HV" };
    return build < 4u ? names[build] : "unknown";
}

const char *ssr_state_name(uint8_t state)
{
    static const char *const names[] = { "off", "closing", "rising", "on", "stopping" };
    return state < 5u ? names[state] : "unknown";
}

int ssr_format(uint8_t node, char *buf, uint32_t n)
{
    const ssr_t *s = &node_state[node & 15u];
    int k = snprintf(buf, n, "SSR %u port=%u state=%s build=%s vset=%u.%02u ilimit=%u.%02u "
                     "vin=%u.%02u vout=%u.%02u iavg=%u.%02u ipeak=%u.%02u faults=0x%04X warnings=0x%02X "
                     "v12=%u.%u",
                     node, (unsigned)SSR_PORT(node), ssr_state_name(s->state), ssr_build_name(s->build),
                     s->vset / 100u, s->vset % 100u, s->ilimit / 100u, s->ilimit % 100u,
                     s->vin / 100u, s->vin % 100u, s->vout / 100u, s->vout % 100u,
                     s->iavg / 100u, s->iavg % 100u, s->ipeak / 100u, s->ipeak % 100u,
                     s->faults, s->warnings, s->v12 / 10u, s->v12 % 10u);
    if (s->info_ms && k > 0 && (uint32_t)k < n)
        k += snprintf(buf + k, n - (uint32_t)k, " fw=%u.%u", s->fw_major, s->fw_minor);
    if (k > 0 && (uint32_t)k < n)
        k += snprintf(buf + k, n - (uint32_t)k, " age=%lu", (unsigned long)(millis() - s->last_ms));
    return k;
}

bool ssr_send_set(uint8_t node, uint16_t vset, uint16_t ilimit, uint8_t flags, uint8_t *seq)
{
    uint8_t d[6];
    put16(d, vset);
    put16(d + 2, ilimit);
    d[4] = flags;
    d[5] = ++set_seq;
    *seq = set_seq;
    node_state[node & 15u].ack_ms = 0;
    return send(F_SET, node & 15u, d, 6);
}

void ssr_note_set(uint8_t node, uint16_t ilimit)
{
    node_state[node & 15u].ilimit = ilimit;
}

bool ssr_send_clear(uint8_t node)
{
    return send(F_CLEAR, node & 15u, NULL, 0);
}

bool ssr_send_info_req(uint8_t node)
{
    node_state[node & 15u].info_ms = 0;
    return send(F_INFO_REQ, node & 15u, NULL, 0);
}

bool ssr_send_all_off(void)
{
    return send(F_ALL_OFF, 0, NULL, 0);
}
