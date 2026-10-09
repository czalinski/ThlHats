/* W6100 socket layer (datasheet v1.0.4 chapters 3-4, 6). Buffer pointers are
 * written as SPI addresses into the TX/RX buffer blocks; the chip wraps them
 * inside the 2 KB buffer itself. */
#include <xc.h>
#include <string.h>
#include "board.h"
#include "settings.h"
#include "w6100.h"
#include "net.h"

/* common registers */
#define SHAR        0x4120u
#define GAR         0x4130u
#define SUBR        0x4134u
#define SIPR        0x4138u
#define NETLCKR     0x41F5u
#define RTR         0x4200u
#define RCR         0x4204u

/* socket registers */
#define Sn_MR       0x0000u
#define Sn_CR       0x0010u
#define Sn_IR       0x0020u
#define Sn_IRCLR    0x0028u
#define Sn_SR       0x0030u
#define Sn_PORTR    0x0114u
#define Sn_DIPR     0x0120u
#define Sn_DPORTR   0x0140u
#define Sn_KPALVTR  0x0188u
#define Sn_TX_FSR   0x0204u
#define Sn_TX_WR    0x020Cu
#define Sn_RX_RSR   0x0224u
#define Sn_RX_RD    0x0228u

#define BSB_REG(s)  ((uint8_t)((s) * 4u + 1u))
#define BSB_TX(s)   ((uint8_t)((s) * 4u + 2u))
#define BSB_RX(s)   ((uint8_t)((s) * 4u + 3u))

#define MR_TCP4     0x01u
#define MR_UDP4     0x02u
#define MR_ND       0x20u               /* TCP: no delayed ACK */
#define CR_OPEN     0x01u
#define CR_LISTEN   0x02u
#define CR_DISCON   0x08u
#define CR_CLOSE    0x10u
#define CR_SEND     0x20u
#define CR_RECV     0x40u
#define IR_CON      0x01u
#define IR_TIMEOUT  0x08u
#define IR_SENDOK   0x10u
#define SR_CLOSED   0x00u
#define SR_INIT     0x13u
#define SR_LISTEN   0x14u
#define SR_ESTAB    0x17u
#define SR_CLOSE_WAIT 0x1Cu
#define SR_UDP      0x22u

#define SOCKETS     8u

static struct {
    uint16_t port;
    uint8_t mode;                       /* 0 unused */
    bool send_busy;
    bool new_conn;
    bool hold;                          /* owner still has output for a closing peer */
} sock[SOCKETS];

static bool chip_ok;
static uint8_t mac[6];
static uint8_t active_ip[4];

static bool send_done(uint8_t s);

static uint8_t sreg8(uint8_t s, uint16_t a)
{
    uint8_t v;
    w6100_read(a, BSB_REG(s), &v, 1);
    return v;
}

static void sreg8_set(uint8_t s, uint16_t a, uint8_t v)
{
    w6100_write(a, BSB_REG(s), &v, 1);
}

static uint16_t sreg16(uint8_t s, uint16_t a)
{
    uint8_t b[2];
    w6100_read(a, BSB_REG(s), b, 2);
    return (uint16_t)((b[0] << 8) | b[1]);
}

/* free/received sizes can change mid-read: read until two reads agree */
static uint16_t sreg16_stable(uint8_t s, uint16_t a)
{
    uint16_t v, w = sreg16(s, a);
    do {
        v = w;
        w = sreg16(s, a);
    } while (v != w);
    return v;
}

static void sreg16_set(uint8_t s, uint16_t a, uint16_t v)
{
    uint8_t b[2] = { (uint8_t)(v >> 8), (uint8_t)v };
    w6100_write(a, BSB_REG(s), b, 2);
}

static void command(uint8_t s, uint8_t cr)
{
    sreg8_set(s, Sn_CR, cr);
    uint32_t t0 = ticks();
    while (sreg8(s, Sn_CR) && ms_since(t0) < 10u) { }
}

static void open_socket(uint8_t s)
{
    command(s, CR_CLOSE);
    sreg8_set(s, Sn_IRCLR, 0xFF);
    sreg8_set(s, Sn_MR, sock[s].mode == MR_TCP4 ? (MR_TCP4 | MR_ND) : sock[s].mode);
    sreg16_set(s, Sn_PORTR, sock[s].port);
    if (sock[s].mode == MR_TCP4)
        sreg8_set(s, Sn_KPALVTR, 1);    /* keep-alive after 5 s idle */
    command(s, CR_OPEN);
    if (sock[s].mode == MR_TCP4 && sreg8(s, Sn_SR) == SR_INIT)
        command(s, CR_LISTEN);
    sock[s].send_busy = false;
}

static void make_mac(void)
{
    /* locally administered unicast: 02:54:48 ("TH") + 24 bits of the serial number */
    uint32_t h = DEVSN0 ^ (DEVSN1 * 2654435761u) ^ (DEVSN2 << 7) ^ DEVSN3;
    mac[0] = 0x02;
    mac[1] = 0x54;
    mac[2] = 0x48;
    mac[3] = (uint8_t)(h >> 16);
    mac[4] = (uint8_t)(h >> 8);
    mac[5] = (uint8_t)h;
}

bool net_init(void)
{
    chip_ok = w6100_init();
    if (!chip_ok)
        return false;
    make_mac();
    memcpy(active_ip, settings.ip, 4);

    uint8_t v = 0x3A;                   /* unlock network configuration */
    w6100_write(NETLCKR, 0, &v, 1);
    w6100_write(SHAR, 0, mac, 6);
    w6100_write(GAR, 0, settings.gw, 4);
    w6100_write(SUBR, 0, settings.mask, 4);
    w6100_write(SIPR, 0, settings.ip, 4);
    v = 0xC5;
    w6100_write(NETLCKR, 0, &v, 1);

    /* 200 ms retransmission timeout, 5 retries: a dead peer is dropped in
     * about 20 s together with the keep-alive */
    uint8_t rtr[2] = { 0x07, 0xD0 };
    w6100_write(RTR, 0, rtr, 2);
    v = 5;
    w6100_write(RCR, 0, &v, 1);

    sock[SOCK_CMD0] = (typeof(sock[0])){ .port = PORT_CMD, .mode = MR_TCP4 };
    sock[SOCK_CMD1] = (typeof(sock[0])){ .port = PORT_CMD, .mode = MR_TCP4 };
    for (uint8_t n = 1; n <= 4u; n++)
        sock[SOCK_SER(n)] = (typeof(sock[0])){ .port = (uint16_t)PORT_SER(n), .mode = MR_TCP4 };
    sock[SOCK_STREAM] = (typeof(sock[0])){ .port = PORT_STREAM, .mode = MR_UDP4 };
    for (uint8_t s = 0; s < SOCKETS; s++)
        if (sock[s].mode)
            open_socket(s);
    return true;
}

bool net_ok(void)
{
    return chip_ok;
}

void net_mac(uint8_t m[6])
{
    memcpy(m, mac, 6);
}

void net_active_ip(uint8_t ip[4])
{
    memcpy(ip, active_ip, 4);
}

uint8_t net_physr(void)
{
    return chip_ok ? w6100_read8(W6100_PHYSR) : 0x80;
}

void net_poll(void)
{
    if (!chip_ok)
        return;
    for (uint8_t s = 0; s < SOCKETS; s++) {
        if (!sock[s].mode)
            continue;
        uint8_t sr = sreg8(s, Sn_SR);
        switch (sr) {
        case SR_CLOSED:
            open_socket(s);
            break;
        case SR_INIT:
            if (sock[s].mode == MR_TCP4)
                command(s, CR_LISTEN);
            break;
        case SR_ESTAB: {
            uint8_t ir = sreg8(s, Sn_IR);
            if (ir & IR_CON) {
                sreg8_set(s, Sn_IRCLR, IR_CON);
                sock[s].new_conn = true;
                sock[s].send_busy = false;
            }
            break;
        }
        case SR_CLOSE_WAIT:
            /* peer closed its side: finish reading and answering, then close ours */
            if (!sreg16_stable(s, Sn_RX_RSR) && send_done(s) && !sock[s].hold)
                command(s, CR_DISCON);
            break;
        case SR_UDP:
            if (sreg16_stable(s, Sn_RX_RSR)) {
                /* nothing listens on the stream socket: discard */
                uint16_t rd = sreg16(s, Sn_RX_RD);
                sreg16_set(s, Sn_RX_RD, (uint16_t)(rd + sreg16_stable(s, Sn_RX_RSR)));
                command(s, CR_RECV);
            }
            break;
        default:
            break;                      /* SYN/FIN transients */
        }
    }
}

bool tcp_connected(uint8_t s)
{
    if (!chip_ok)
        return false;
    uint8_t sr = sreg8(s, Sn_SR);
    return sr == SR_ESTAB || sr == SR_CLOSE_WAIT;
}

void tcp_hold(uint8_t s, bool hold)
{
    sock[s].hold = hold;
}

bool tcp_new_connection(uint8_t s)
{
    bool n = sock[s].new_conn;
    sock[s].new_conn = false;
    return n;
}

void tcp_peer(uint8_t s, uint8_t ip[4])
{
    w6100_read(Sn_DIPR, BSB_REG(s), ip, 4);
}

uint16_t tcp_rx_avail(uint8_t s)
{
    return sreg16_stable(s, Sn_RX_RSR);
}

uint16_t tcp_recv(uint8_t s, uint8_t *buf, uint16_t max)
{
    uint16_t n = tcp_rx_avail(s);
    if (n > max)
        n = max;
    if (!n)
        return 0;
    uint16_t rd = sreg16(s, Sn_RX_RD);
    w6100_read(rd, BSB_RX(s), buf, n);
    sreg16_set(s, Sn_RX_RD, (uint16_t)(rd + n));
    command(s, CR_RECV);
    return n;
}

static bool send_done(uint8_t s)
{
    if (!sock[s].send_busy)
        return true;
    uint8_t ir = sreg8(s, Sn_IR);
    if (ir & (IR_SENDOK | IR_TIMEOUT)) {
        sreg8_set(s, Sn_IRCLR, ir & (IR_SENDOK | IR_TIMEOUT));
        sock[s].send_busy = false;
    }
    return !sock[s].send_busy;
}

uint16_t tcp_tx_room(uint8_t s)
{
    if (!send_done(s))
        return 0;
    return sreg16_stable(s, Sn_TX_FSR);
}

static void send_buf(uint8_t s, const uint8_t *buf, uint16_t len)
{
    uint16_t wr = sreg16(s, Sn_TX_WR);
    w6100_write(wr, BSB_TX(s), buf, len);
    sreg16_set(s, Sn_TX_WR, (uint16_t)(wr + len));
    command(s, CR_SEND);
    sock[s].send_busy = true;
}

bool tcp_send(uint8_t s, const uint8_t *buf, uint16_t len)
{
    if (!len || !tcp_connected(s) || tcp_tx_room(s) < len)
        return false;
    send_buf(s, buf, len);
    return true;
}

bool udp_sendto(uint8_t s, const uint8_t ip[4], uint16_t port, const uint8_t *buf, uint16_t len)
{
    if (!chip_ok || !send_done(s) || sreg16_stable(s, Sn_TX_FSR) < len)
        return false;
    w6100_write(Sn_DIPR, BSB_REG(s), ip, 4);
    sreg16_set(s, Sn_DPORTR, port);
    send_buf(s, buf, len);
    return true;
}
