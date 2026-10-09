/* PIC32MK CAN FD driver, polled. The module register set is the MCP2517FD's
 * with 0x10 spacing (CLR/SET/INV at +4/+8/+C); all four modules are handled
 * through one offset table. Message objects as in DS60001519D 26.x / the
 * MCP2517FD: T0/R0 = SID<10:0> EID<28:11> SID11<29>; T1/R1 = DLC<3:0> IDE<4>
 * RTR<5> BRS<6> FDF<7> ESI<8>; payload follows (no RX timestamps).
 *
 * Per channel: FIFO1 = TX, 8 x 64-byte objects; FIFO2 = RX, 16 x 64-byte
 * objects; filter 0 accepts everything into FIFO2. No TXQ, no TEF.
 * Clock: REFCLK4 = 40 MHz (board.c). Bit timing: one TQ clock (BRP = 0) for
 * both phases where possible, sample point 80 %, automatic TDC. */
#include <xc.h>
#include <sys/kmem.h>
#include <string.h>
#include "board.h"
#include "canfd.h"

/* register offsets in 32-bit words from CFDxCON */
#define R_CON       (0x000u / 4u)
#define R_NBTCFG    (0x010u / 4u)
#define R_DBTCFG    (0x020u / 4u)
#define R_TDC       (0x030u / 4u)
#define R_TREC      (0x0D0u / 4u)
#define R_BDIAG1    (0x0F0u / 4u)
#define R_FIFOBA    (0x130u / 4u)
#define R_TXQCON    (0x140u / 4u)
#define R_FIFOCON(n) ((0x170u + ((n) - 1u) * 0x30u) / 4u)
#define R_FIFOSTA(n) ((0x180u + ((n) - 1u) * 0x30u) / 4u)
#define R_FIFOUA(n)  ((0x190u + ((n) - 1u) * 0x30u) / 4u)
#define R_FLTCON0   (0x740u / 4u)
#define R_FLTOBJ0   (0x7C0u / 4u)
#define R_MASK0     (0x7D0u / 4u)
#define CLR         1u                  /* word offsets of the CLR/SET registers */
#define SET         2u

/* CFDxCON */
#define CON_CLKSEL0     (1u << 7)
#define CON_ISOCRCEN    (1u << 5)
#define CON_ON          (1u << 15)
#define CON_REQOP_POS   24u
#define CON_REQOP_MASK  (7u << 24)
#define CON_OPMOD_POS   21u
#define OPMOD_NORMAL_FD 0u
#define OPMOD_LOOPBACK  2u
#define OPMOD_LISTEN    3u
#define OPMOD_CONFIG    4u
#define OPMOD_CLASSIC   6u

/* FIFOCONn / FIFOSTAn */
#define FIFO_TXEN       (1u << 7)
#define FIFO_UINC       (1u << 8)
#define FIFO_TXREQ      (1u << 9)
#define FIFO_FRESET     (1u << 10)
#define FIFO_TXAT_UNLIM (3u << 21)
#define FIFO_FSIZE(n)   (((n) - 1u) << 24)
#define FIFO_PLSIZE_64  (7u << 29)
#define STA_TFNRFNIF    (1u << 0)       /* TX: not full / RX: not empty */
#define STA_RXOVIF      (1u << 3)

#define TX_FIFO     1u
#define RX_FIFO     2u
#define TX_DEPTH    8u
#define RX_DEPTH    16u
#define OBJ_SIZE    (8u + 64u)
#define RAM_SIZE    ((TX_DEPTH + RX_DEPTH) * OBJ_SIZE)

static uint32_t can_ram[CAN_CHANNELS][RAM_SIZE / 4u] __attribute__((coherent, aligned(16)));

static volatile uint32_t *const cfd[CAN_CHANNELS] = { &CFD1CON, &CFD2CON, &CFD3CON, &CFD4CON };

/* port pins; registers addressed as {reg, reg CLR, reg SET} */
typedef struct {
    volatile uint32_t *tris, *port, *lat, *cnpu, *cnpd;
    uint32_t mask;
} pin_t;

#define PIN(P, n) { &TRIS##P, &PORT##P, &LAT##P, &CNPU##P, &CNPD##P, 1u << (n) }

static const pin_t tx_pin[CAN_CHANNELS] = { PIN(B, 3), PIN(B, 0), PIN(C, 1), PIN(A, 8) };
static const pin_t rx_pin[CAN_CHANNELS] = { PIN(B, 2), PIN(A, 1), PIN(C, 0), PIN(E, 15) };

static volatile uint32_t *const tx_rpor[CAN_CHANNELS] = { &RPB3R, &RPB0R, &RPC1R, &RPA8R };
#define RPOR_CTX    12u                 /* CnTX output code in every output group */

static struct {
    bool present, running;
    can_mode mode;
    uint32_t nominal, data;
    uint32_t rx_frames, tx_frames, rx_overflows, tx_full;
} chan[CAN_CHANNELS];

static const uint8_t dlc_len[16] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64 };

uint8_t can_dlc_to_len(uint8_t dlc)
{
    return dlc_len[dlc & 15u];
}

uint8_t can_len_to_dlc(uint8_t len)
{
    uint8_t dlc = 0;
    while (dlc < 15u && dlc_len[dlc] < len)
        dlc++;
    return dlc;
}

/* ------------------------------------------------------------------ pins */

static void pin_input(const pin_t *p, bool pull_up, bool pull_down)
{
    p->tris[SET] = p->mask;
    if (pull_up) p->cnpu[SET] = p->mask; else p->cnpu[CLR] = p->mask;
    if (pull_down) p->cnpd[SET] = p->mask; else p->cnpd[CLR] = p->mask;
}

static void pins_release(uint8_t i)
{
    pps_unlock();
    *tx_rpor[i] = 0;
    pps_lock();
    pin_input(&tx_pin[i], true, false);     /* recessive if a card is there */
    pin_input(&rx_pin[i], false, !chan[i].present);
}

static void pins_drive(uint8_t i)
{
    pin_input(&rx_pin[i], false, false);
    tx_pin[i].cnpu[CLR] = tx_pin[i].mask;
    tx_pin[i].lat[SET] = tx_pin[i].mask;
    tx_pin[i].tris[CLR] = tx_pin[i].mask;
    pps_unlock();
    *tx_rpor[i] = RPOR_CTX;
    pps_lock();
}

static void rx_map(void)
{
    pps_unlock();
    C1RXR = 4;                          /* RPB2 */
    C2RXR = 0;                          /* RPA1 */
    C3RXR = 6;                          /* RPC0 */
    C4RXR = 8;                          /* RPE15 */
    pps_lock();
}

/* ------------------------------------------------------------------ detection */

#define DETECT_SAMPLES  200u            /* every 10 us: 2 ms */

uint8_t can_detect(void)
{
    uint8_t mask = 0;
    uint16_t high[CAN_CHANNELS] = { 0 };

    for (uint8_t i = 0; i < CAN_CHANNELS; i++)
        if (!chan[i].running) {
            pps_unlock();
            *tx_rpor[i] = 0;
            pps_lock();
            pin_input(&tx_pin[i], true, false);
            pin_input(&rx_pin[i], false, true);
        }
    delay_us(200);

    for (uint32_t n = 0; n < DETECT_SAMPLES; n++) {
        for (uint8_t i = 0; i < CAN_CHANNELS; i++)
            if (*rx_pin[i].port & rx_pin[i].mask)
                high[i]++;
        delay_us(10);
    }

    for (uint8_t i = 0; i < CAN_CHANNELS; i++) {
        if (!chan[i].running) {
            /* idle bus: RXD high nearly all the time; even a fully loaded
             * bus is recessive for well over 10 % of the bits */
            chan[i].present = high[i] >= DETECT_SAMPLES / 10u;
            pin_input(&rx_pin[i], false, !chan[i].present);
        }
        if (chan[i].present)
            mask |= 1u << i;
    }
    return mask;
}

/* ------------------------------------------------------------------ bit timing */

typedef struct { uint32_t nbtcfg, dbtcfg, tdc; } timing_t;

/* ntq = TQ per bit at BRP; fields are encoded minus one */
static bool phase(uint32_t rate, uint32_t max_ntq, uint32_t max_tseg1, uint32_t max_tseg2,
                  uint32_t *brp, uint32_t *tseg1, uint32_t *tseg2)
{
    if (rate == 0)
        return false;
    for (uint32_t b = 1; b <= 256u; b++) {
        if (CANCLK_HZ % (b * rate))
            continue;
        uint32_t ntq = CANCLK_HZ / (b * rate);
        if (ntq > max_ntq)
            continue;
        if (ntq < 5u)
            return false;
        uint32_t t1 = ntq * 8u / 10u - 1u;     /* TQ after sync up to the sample point */
        uint32_t t2 = ntq - 1u - t1;
        if (t1 > max_tseg1 || t2 > max_tseg2)
            continue;
        *brp = b - 1u;
        *tseg1 = t1 - 1u;
        *tseg2 = t2 - 1u;
        return true;
    }
    return false;
}

static bool timing(uint32_t nominal, uint32_t data, bool fd, timing_t *t)
{
    uint32_t brp, ts1, ts2;
    if (!phase(nominal, 1u + 256u + 128u, 256u, 128u, &brp, &ts1, &ts2))
        return false;
    /* SJW = TSEG2 */
    t->nbtcfg = (brp << 24) | (ts1 << 16) | (ts2 << 8) | ts2;
    t->dbtcfg = 0;
    t->tdc = 0;
    if (!fd)
        return true;
    if (!phase(data, 1u + 32u + 16u, 32u, 16u, &brp, &ts1, &ts2) || data < nominal)
        return false;
    t->dbtcfg = (brp << 24) | (ts1 << 16) | (ts2 << 8) | ts2;
    /* automatic TDC, TDCO = (DBRP + 1) * (DTSEG1 + 1) CAN clocks (Microchip's
     * MCP25xxFD recommendation, e.g. 15 at 2 Mbit/s from 40 MHz) */
    t->tdc = (2u << 16) | ((((brp + 1u) * (ts1 + 1u)) & 0x7Fu) << 8);
    return true;
}

bool can_timing_ok(uint32_t nominal, uint32_t data)
{
    timing_t t;
    return timing(nominal, data, true, &t);
}

/* ------------------------------------------------------------------ mode control */

static bool request_mode(volatile uint32_t *r, uint32_t mode, uint32_t timeout_ms)
{
    r[R_CON] = (r[R_CON] & ~CON_REQOP_MASK) | (mode << CON_REQOP_POS);
    uint32_t t0 = ticks();
    while (((r[R_CON] >> CON_OPMOD_POS) & 7u) != mode)
        if (ms_since(t0) > timeout_ms)
            return false;
    return true;
}

static void module_off(uint8_t i)
{
    volatile uint32_t *r = cfd[i];
    if (r[R_CON] & CON_ON)
        request_mode(r, OPMOD_CONFIG, 20);
    r[R_CON + CLR] = CON_ON;
}

bool can_start(uint8_t ch, can_mode mode, uint32_t nominal, uint32_t data)
{
    if (ch < 1u || ch > CAN_CHANNELS)
        return false;
    uint8_t i = ch - 1u;
    volatile uint32_t *r = cfd[i];
    bool fd = mode != CAN_MODE_CLASSIC;
    timing_t t;

    if (!timing(nominal, data, fd, &t))
        return false;
    if (mode != CAN_MODE_LOOPBACK && !chan[i].present)
        return false;

    can_stop(ch);

    r[R_CON] = (OPMOD_CONFIG << CON_REQOP_POS) | CON_CLKSEL0 | CON_ISOCRCEN;
    r[R_CON + SET] = CON_ON;
    if (!request_mode(r, OPMOD_CONFIG, 20)) {
        r[R_CON + CLR] = CON_ON;
        return false;
    }

    r[R_NBTCFG] = t.nbtcfg;
    r[R_DBTCFG] = t.dbtcfg;
    r[R_TDC] = t.tdc;

    memset(can_ram[i], 0, sizeof can_ram[i]);
    r[R_FIFOBA] = KVA_TO_PA(can_ram[i]);
    r[R_TXQCON] = 0;
    r[R_FIFOCON(TX_FIFO)] = FIFO_TXEN | FIFO_TXAT_UNLIM | FIFO_FSIZE(TX_DEPTH) | FIFO_PLSIZE_64;
    r[R_FIFOCON(RX_FIFO)] = FIFO_FSIZE(RX_DEPTH) | FIFO_PLSIZE_64;

    /* filter 0: everything (mask 0, standard and extended) -> RX FIFO */
    r[R_FLTCON0] = 0;
    r[R_FLTOBJ0] = 0;
    r[R_MASK0] = 0;
    r[R_FLTCON0] = RX_FIFO | (1u << 7);

    if (mode != CAN_MODE_LOOPBACK)
        pins_drive(i);

    static const uint8_t opmod[] = {
        [CAN_MODE_FD] = OPMOD_NORMAL_FD, [CAN_MODE_CLASSIC] = OPMOD_CLASSIC,
        [CAN_MODE_LISTEN] = OPMOD_LISTEN, [CAN_MODE_LOOPBACK] = OPMOD_LOOPBACK,
    };
    /* normal modes wait for 11 recessive bits (bus integration) */
    if (!request_mode(r, opmod[mode], 50)) {
        module_off(i);
        pins_release(i);
        return false;
    }

    chan[i].running = true;
    chan[i].mode = mode;
    chan[i].nominal = nominal;
    chan[i].data = fd ? data : 0;
    chan[i].rx_frames = chan[i].tx_frames = chan[i].rx_overflows = chan[i].tx_full = 0;
    return true;
}

void can_stop(uint8_t ch)
{
    if (ch < 1u || ch > CAN_CHANNELS)
        return;
    uint8_t i = ch - 1u;
    module_off(i);
    if (chan[i].running && chan[i].mode != CAN_MODE_LOOPBACK)
        pins_release(i);
    chan[i].running = false;
}

/* ------------------------------------------------------------------ frames */

static volatile uint32_t *fifo_obj(volatile uint32_t *r, uint32_t n)
{
    return (volatile uint32_t *)PA_TO_KVA1(r[R_FIFOUA(n)]);
}

bool can_send(uint8_t ch, const can_frame *f)
{
    if (ch < 1u || ch > CAN_CHANNELS)
        return false;
    uint8_t i = ch - 1u;
    volatile uint32_t *r = cfd[i];

    if (!chan[i].running || chan[i].mode == CAN_MODE_LISTEN)
        return false;
    if (!(r[R_FIFOSTA(TX_FIFO)] & STA_TFNRFNIF)) {
        chan[i].tx_full++;
        return false;
    }

    bool fd = (f->flags & CAN_FDF) && chan[i].mode != CAN_MODE_CLASSIC;
    uint8_t len = f->len > (fd ? 64u : 8u) ? (fd ? 64u : 8u) : f->len;
    uint8_t dlc = can_len_to_dlc(len);
    len = can_dlc_to_len(dlc);

    volatile uint32_t *o = fifo_obj(r, TX_FIFO);
    if (f->flags & CAN_EXT)
        o[0] = ((f->id >> 18) & 0x7FFu) | ((f->id & 0x3FFFFu) << 11);
    else
        o[0] = f->id & 0x7FFu;
    o[1] = dlc
         | ((f->flags & CAN_EXT) ? 1u << 4 : 0)
         | ((!fd && (f->flags & CAN_RTR)) ? 1u << 5 : 0)
         | ((fd && (f->flags & CAN_BRS)) ? 1u << 6 : 0)
         | (fd ? 1u << 7 : 0);
    for (uint8_t k = 0; k < len; k += 4u) {
        uint32_t w = 0;
        for (uint8_t b = 0; b < 4u; b++) {
            uint8_t idx = k + b;
            w |= (uint32_t)(idx < f->len ? f->data[idx] : 0) << (8u * b);
        }
        o[2u + k / 4u] = w;
    }
    r[R_FIFOCON(TX_FIFO) + SET] = FIFO_UINC | FIFO_TXREQ;
    chan[i].tx_frames++;
    return true;
}

bool can_receive(uint8_t ch, can_frame *f)
{
    if (ch < 1u || ch > CAN_CHANNELS)
        return false;
    uint8_t i = ch - 1u;
    volatile uint32_t *r = cfd[i];

    if (!chan[i].running)
        return false;
    uint32_t sta = r[R_FIFOSTA(RX_FIFO)];
    if (sta & STA_RXOVIF) {
        chan[i].rx_overflows++;
        r[R_FIFOSTA(RX_FIFO) + CLR] = STA_RXOVIF;
    }
    if (!(sta & STA_TFNRFNIF))
        return false;

    volatile uint32_t *o = fifo_obj(r, RX_FIFO);
    uint32_t r0 = o[0], r1 = o[1];
    f->flags = 0;
    if (r1 & (1u << 4)) {
        f->flags |= CAN_EXT;
        f->id = ((r0 & 0x7FFu) << 18) | ((r0 >> 11) & 0x3FFFFu);
    } else {
        f->id = r0 & 0x7FFu;
    }
    if (r1 & (1u << 5)) f->flags |= CAN_RTR;
    if (r1 & (1u << 6)) f->flags |= CAN_BRS;
    if (r1 & (1u << 7)) f->flags |= CAN_FDF;
    if (r1 & (1u << 8)) f->flags |= CAN_ESI;
    uint8_t dlc = r1 & 15u;
    f->len = (f->flags & CAN_FDF) ? can_dlc_to_len(dlc) : (dlc > 8u ? 8u : dlc);
    if (f->flags & CAN_RTR)
        f->len = 0;
    for (uint8_t k = 0; k < f->len; k += 4u) {
        uint32_t w = o[2u + k / 4u];
        for (uint8_t b = 0; b < 4u && k + b < f->len; b++)
            f->data[k + b] = (uint8_t)(w >> (8u * b));
    }
    r[R_FIFOCON(RX_FIFO) + SET] = FIFO_UINC;
    chan[i].rx_frames++;
    return true;
}

void can_get_status(uint8_t ch, can_status *s)
{
    memset(s, 0, sizeof *s);
    if (ch < 1u || ch > CAN_CHANNELS)
        return;
    uint8_t i = ch - 1u;
    s->present = chan[i].present;
    s->running = chan[i].running;
    s->mode = chan[i].mode;
    s->nominal = chan[i].nominal;
    s->data = chan[i].data;
    s->rx_frames = chan[i].rx_frames;
    s->tx_frames = chan[i].tx_frames;
    s->rx_overflows = chan[i].rx_overflows;
    s->tx_full = chan[i].tx_full;
    if (chan[i].running) {
        uint32_t trec = cfd[i][R_TREC];
        s->rec = (uint8_t)trec;
        s->tec = (uint8_t)(trec >> 8);
        s->error_passive = (trec & ((1u << 19) | (1u << 20))) != 0;
        s->bus_off = (trec & (1u << 21)) != 0;
    }
}

/* ------------------------------------------------------------------ self-test */

static bool loop_one(uint8_t ch, const can_frame *tx)
{
    can_frame rx;
    if (!can_send(ch, tx))
        return false;
    uint32_t t0 = ticks();
    while (!can_receive(ch, &rx))
        if (ms_since(t0) > 10u)
            return false;
    return rx.id == tx->id && rx.len == tx->len && (rx.flags & ~CAN_ESI) == tx->flags
        && memcmp(rx.data, tx->data, tx->len) == 0;
}

bool can_selftest(uint8_t ch)
{
    if (ch < 1u || ch > CAN_CHANNELS)
        return false;
    uint8_t i = ch - 1u;
    bool was_running = chan[i].running;
    can_mode mode = chan[i].mode;
    uint32_t nominal = chan[i].nominal, data = chan[i].data;

    bool ok = can_start(ch, CAN_MODE_LOOPBACK, CAN_DEFAULT_NOMINAL, CAN_DEFAULT_DATA);
    if (ok) {
        can_frame f = { .id = 0x123, .len = 8, .flags = 0 };
        for (uint8_t k = 0; k < 8u; k++)
            f.data[k] = (uint8_t)(0xA0u + k);
        ok = loop_one(ch, &f);

        can_frame g = { .id = 0x1ABCDE5u, .len = 64, .flags = CAN_EXT | CAN_FDF | CAN_BRS };
        for (uint8_t k = 0; k < 64u; k++)
            g.data[k] = (uint8_t)(k * 7u + ch);
        ok = ok && loop_one(ch, &g);
    }
    can_stop(ch);
    if (was_running)
        can_start(ch, mode, nominal, data ? data : CAN_DEFAULT_DATA);
    return ok;
}

/* ------------------------------------------------------------------ init */

void can_init(void)
{
    for (uint8_t i = 0; i < CAN_CHANNELS; i++)
        module_off(i);
    rx_map();
    can_detect();
    for (uint8_t ch = 1; ch <= CAN_CHANNELS; ch++)
        if (chan[ch - 1u].present)
            can_start(ch, CAN_MODE_FD, CAN_DEFAULT_NOMINAL, CAN_DEFAULT_DATA);
}
