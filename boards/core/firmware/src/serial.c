/* UART2-5 <-> TCP bridge. Both directions go through interrupt-driven rings,
 * so a slow main loop costs throughput, never bytes. Socket data is read only
 * as far as the UART ring has room: TCP flow control does the rest.
 *
 * RS-485 ports: DE goes high when the first byte is queued and low in the
 * "all characters transmitted" interrupt (UTXISEL = 01), i.e. right after the
 * last stop bit. */
#include <xc.h>
#include <sys/attribs.h>
#include <string.h>
#include "board.h"
#include "net.h"
#include "serial.h"

#define RING        1024u               /* power of two */

/* UARTx registers from UxMODE: MODE, STA, TXREG, RXREG, BRG every 0x10 bytes */
#define R_MODE      0u
#define R_STA       4u
#define R_TXREG     8u
#define R_RXREG     12u
#define R_BRG       16u
#define CLR         1u
#define SET         2u

typedef struct {
    volatile uint32_t *u;
    volatile uint32_t *iec, *ifs;       /* IECx / IFSx for this UART */
    uint32_t rx_mask, tx_mask;
    volatile uint32_t *de_lat;          /* NULL: RS-232 */
    uint32_t de_mask;
    uint32_t pbclk;
} port_hw;

static const port_hw hw[SER_PORTS] = {
    { &U2MODE, &IEC1, &IFS1, _IEC1_U2RXIE_MASK, _IEC1_U2TXIE_MASK, NULL, 0, PBCLK2_HZ },
    { &U3MODE, &IEC1, &IFS1, _IEC1_U3RXIE_MASK, 0, NULL, 0, PBCLK3_HZ },   /* U3TX is in IEC2 */
    { &U4MODE, &IEC2, &IFS2, _IEC2_U4RXIE_MASK, _IEC2_U4TXIE_MASK, &LATA, 1u << 10, PBCLK3_HZ },
    { &U5MODE, &IEC2, &IFS2, _IEC2_U5RXIE_MASK, _IEC2_U5TXIE_MASK, &LATA, 1u << 7, PBCLK3_HZ },
};

typedef struct {
    volatile uint8_t rx[RING], tx[RING];
    volatile uint32_t rx_head, rx_tail, tx_head, tx_tail;
    volatile uint32_t rx_count, tx_count, rx_overflow;
    ser_settings cfg;
    bool soft7;                         /* 7-bit data on an 8-bit frame */
    char soft_parity;                   /* 'E', 'O', or 'M' (mark: 7N2) */
} port_t;

static port_t port[SER_PORTS];

/* U3's TX enable/flag bits sit in IEC2/IFS2 while its RX bits are in IEC1 */
static void tx_irq(uint8_t i, bool on)
{
    if (i == 1u) {
        if (on) IEC2SET = _IEC2_U3TXIE_MASK; else IEC2CLR = _IEC2_U3TXIE_MASK;
    } else {
        if (on) hw[i].iec[SET] = hw[i].tx_mask; else hw[i].iec[CLR] = hw[i].tx_mask;
    }
}

static void tx_flag_clear(uint8_t i)
{
    if (i == 1u)
        IFS2CLR = _IFS2_U3TXIF_MASK;
    else
        hw[i].ifs[CLR] = hw[i].tx_mask;
}

static uint8_t parity7(uint8_t c, char mode)
{
    c &= 0x7Fu;
    if (mode == 'M')
        return c | 0x80u;               /* 7N2: the 8th bit is a second stop bit */
    uint8_t p = c;
    p ^= p >> 4;
    p ^= p >> 2;
    p ^= p >> 1;
    p &= 1u;                            /* 1 = odd number of ones */
    if (mode == 'E' ? p : !p)
        c |= 0x80u;
    return c;
}

static void isr_rx(uint8_t i)
{
    port_t *p = &port[i];
    volatile uint32_t *u = hw[i].u;
    if (u[R_STA] & _U1STA_OERR_MASK)
        u[R_STA + CLR] = _U1STA_OERR_MASK;
    while (u[R_STA] & _U1STA_URXDA_MASK) {
        uint8_t c = (uint8_t)u[R_RXREG];
        if (p->soft7)
            c &= 0x7Fu;
        uint32_t next = (p->rx_head + 1u) & (RING - 1u);
        if (next == p->rx_tail) {
            p->rx_overflow++;
            continue;
        }
        p->rx[p->rx_head] = c;
        p->rx_head = next;
        p->rx_count++;
    }
    hw[i].ifs[CLR] = hw[i].rx_mask;
}

static void isr_tx(uint8_t i)
{
    port_t *p = &port[i];
    volatile uint32_t *u = hw[i].u;
    while (!(u[R_STA] & _U1STA_UTXBF_MASK) && p->tx_tail != p->tx_head) {
        u[R_TXREG] = p->tx[p->tx_tail];
        p->tx_tail = (p->tx_tail + 1u) & (RING - 1u);
        p->tx_count++;
    }
    if (p->tx_tail != p->tx_head) {
        u[R_STA + CLR] = _U1STA_UTXISEL_MASK;       /* more queued: interrupt on FIFO space */
    } else if (!hw[i].de_lat) {
        tx_irq(i, false);
    } else if (!(u[R_STA] & _U1STA_UTXISEL_MASK)) {
        /* ring empty: wait for the shift register to drain, then drop DE */
        u[R_STA + SET] = 1u << _U1STA_UTXISEL_POSITION;
    } else if (u[R_STA] & _U1STA_TRMT_MASK) {
        hw[i].de_lat[CLR] = hw[i].de_mask;
        tx_irq(i, false);
        u[R_STA + CLR] = _U1STA_UTXISEL_MASK;
    }
    tx_flag_clear(i);
}

void __ISR(_UART2_RX_VECTOR, IPL3SRS) u2rx_isr(void) { isr_rx(0); }
void __ISR(_UART3_RX_VECTOR, IPL3SRS) u3rx_isr(void) { isr_rx(1); }
void __ISR(_UART4_RX_VECTOR, IPL3SRS) u4rx_isr(void) { isr_rx(2); }
void __ISR(_UART5_RX_VECTOR, IPL3SRS) u5rx_isr(void) { isr_rx(3); }
void __ISR(_UART2_TX_VECTOR, IPL3SRS) u2tx_isr(void) { isr_tx(0); }
void __ISR(_UART3_TX_VECTOR, IPL3SRS) u3tx_isr(void) { isr_tx(1); }
void __ISR(_UART4_TX_VECTOR, IPL3SRS) u4tx_isr(void) { isr_tx(2); }
void __ISR(_UART5_TX_VECTOR, IPL3SRS) u5tx_isr(void) { isr_tx(3); }

bool ser_valid(const ser_settings *s)
{
    if (s->baud < 300u || s->baud > 1000000u)
        return false;
    if (s->parity != 'N' && s->parity != 'E' && s->parity != 'O')
        return false;
    if (s->stop != 1u && s->stop != 2u)
        return false;
    if (s->data == 8u)
        return true;
    /* 7 bits fit an 8-bit frame only with parity or two stop bits */
    return s->data == 7u && (s->parity != 'N' || s->stop == 2u);
}

static uint32_t brg_for(uint8_t i, uint32_t baud)
{
    uint32_t div = (hw[i].pbclk + 2u * baud) / (4u * baud);    /* BRGH = 1, rounded */
    return div ? div - 1u : 0u;
}

uint32_t ser_actual_baud(uint8_t p)
{
    uint8_t i = p - 1u;
    return hw[i].pbclk / (4u * (brg_for(i, port[i].cfg.baud) + 1u));
}

void ser_apply(uint8_t p, const ser_settings *s)
{
    uint8_t i = p - 1u;
    port_t *pt = &port[i];
    volatile uint32_t *u = hw[i].u;

    hw[i].iec[CLR] = hw[i].rx_mask;
    tx_irq(i, false);
    u[R_MODE + CLR] = _U1MODE_ON_MASK;
    if (hw[i].de_lat)
        hw[i].de_lat[CLR] = hw[i].de_mask;

    pt->cfg = *s;
    pt->rx_head = pt->rx_tail = pt->tx_head = pt->tx_tail = 0;
    uint32_t pdsel = 0, stsel = s->stop == 2u;
    pt->soft7 = s->data == 7u;
    if (pt->soft7) {
        /* 7E1/7O1 -> 8N1 with software parity; 7E2/7O2 -> 8N2; 7N2 -> 8N1 with bit 7 = 1 */
        pt->soft_parity = s->parity == 'N' ? 'M' : s->parity;
        if (s->parity == 'N')
            stsel = 0;
    } else {
        pdsel = s->parity == 'E' ? 1u : s->parity == 'O' ? 2u : 0u;
    }

    u[R_MODE] = _U1MODE_BRGH_MASK | (pdsel << _U1MODE_PDSEL_POSITION) | (stsel << _U1MODE_STSEL_POSITION);
    u[R_BRG] = brg_for(i, s->baud);
    u[R_STA] = _U1STA_URXEN_MASK | _U1STA_UTXEN_MASK;   /* URXISEL 0, UTXISEL 0 */
    hw[i].ifs[CLR] = hw[i].rx_mask;
    tx_flag_clear(i);
    hw[i].iec[SET] = hw[i].rx_mask;
    u[R_MODE + SET] = _U1MODE_ON_MASK;
}

const ser_settings *ser_get(uint8_t p)
{
    return &port[p - 1u].cfg;
}

bool ser_rs485(uint8_t p)
{
    return hw[p - 1u].de_lat != NULL;
}

void ser_counters(uint8_t p, uint32_t *rx, uint32_t *tx)
{
    *rx = port[p - 1u].rx_count;
    *tx = port[p - 1u].tx_count;
}

void ser_init(void)
{
    /* serial pins out of their idle pull-downs; TX idles high, DE low */
    CNPDCCLR = (1u << 10) | (1u << 13);
    CNPDECLR = 1u << 14;
    CNPDBCLR = (1u << 1) | (1u << 4) | (1u << 8) | (1u << 10) | (1u << 14);
    CNPDACLR = (1u << 7) | (1u << 10);
    LATCSET = 1u << 10;  TRISCCLR = 1u << 10;           /* U2TX RC10 */
    LATESET = 1u << 14;  TRISECLR = 1u << 14;           /* U3TX RE14 */
    LATBSET = (1u << 1) | (1u << 10);                   /* U4TX RB1, U5TX RB10 */
    TRISBCLR = (1u << 1) | (1u << 10);
    LATACLR = (1u << 7) | (1u << 10);                   /* DE2 RA7, DE1 RA10 */
    TRISACLR = (1u << 7) | (1u << 10);

    pps_unlock();
    RPC10R = 2;                         /* U2TX */
    U2RXR = 4;                          /* RPB8 */
    RPE14R = 1;                         /* U3TX */
    U3RXR = 2;                          /* RPB4 */
    RPB1R = 2;                          /* U4TX */
    U4RXR = 0;                          /* RPB14 */
    RPB10R = 11;                        /* U5TX */
    U5RXR = 9;                          /* RPC13 */
    pps_lock();

    IPC14bits.U2RXIP = 3; IPC14bits.U2TXIP = 3;
    IPC15bits.U3RXIP = 3; IPC16bits.U3TXIP = 3;
    IPC16bits.U4RXIP = 3; IPC16bits.U4TXIP = 3;
    IPC17bits.U5RXIP = 3; IPC17bits.U5TXIP = 3;

    for (uint8_t p = 1; p <= SER_PORTS; p++)
        ser_apply(p, &settings.ser[p - 1u]);
}

static uint32_t rx_used(const port_t *p)
{
    return (p->rx_head - p->rx_tail) & (RING - 1u);
}

static uint32_t tx_free(const port_t *p)
{
    return (p->tx_tail - p->tx_head - 1u) & (RING - 1u);
}

void ser_poll(void)
{
    uint8_t buf[256];
    for (uint8_t i = 0; i < SER_PORTS; i++) {
        port_t *p = &port[i];
        uint8_t s = SOCK_SER(i + 1u);

        if (tcp_new_connection(s))
            p->rx_tail = p->rx_head;    /* no stale bytes for a new client */
        if (!tcp_connected(s)) {
            p->rx_tail = p->rx_head;    /* nobody listening: discard */
            continue;
        }

        /* socket -> UART */
        uint32_t room = tx_free(p);
        if (room > sizeof buf)
            room = sizeof buf;
        uint16_t n = room ? tcp_recv(s, buf, (uint16_t)room) : 0;
        if (n) {
            for (uint16_t k = 0; k < n; k++) {
                uint8_t c = p->soft7 ? parity7(buf[k], p->soft_parity) : buf[k];
                p->tx[p->tx_head] = c;
                p->tx_head = (p->tx_head + 1u) & (RING - 1u);
            }
            if (hw[i].de_lat)
                hw[i].de_lat[SET] = hw[i].de_mask;
            tx_irq(i, true);
        }

        /* UART -> socket: contiguous part of the ring per call */
        uint32_t used = rx_used(p);
        if (used) {
            uint16_t r = tcp_tx_room(s);
            uint32_t tail = p->rx_tail;
            uint32_t chunk = RING - tail;
            if (chunk > used) chunk = used;
            if (chunk > r) chunk = r;
            if (chunk && tcp_send(s, (const uint8_t *)&p->rx[tail], (uint16_t)chunk))
                p->rx_tail = (tail + chunk) & (RING - 1u);
        }
    }
}
