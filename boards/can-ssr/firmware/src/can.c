/* CAN FD module (MCP2517FD-style register set), polled.
 * 500 kbit/s nominal, 2 Mbit/s data (FD frames not sent yet). The module runs
 * in normal CAN FD mode: it accepts classic and FD frames and sends classic
 * frames, so it also works on a classic-only bus.
 *
 * Message RAM (C1FIFOBA): TXQ 8 x (8 + 8) bytes, FIFO1 (RX) 16 x (8 + 8) bytes.
 * Filter 0: our node number in ID bits 3..0 (any function) -> FIFO1.
 * Filter 1: broadcast functions 0x00/0x01 with node 0 -> FIFO1. */
#include <xc.h>
#include <string.h>
#include "board.h"
#include "can.h"

#define TXQ_DEPTH   8u
#define RX_DEPTH    16u
#define OBJ_SIZE    16u             /* 8-byte header + 8-byte payload */

static uint8_t can_ram[(TXQ_DEPTH + RX_DEPTH) * OBJ_SIZE] __at(0x3580);

static void set_mode(uint8_t mode)
{
    C1CONTbits.REQOP = mode;
    while (C1CONUbits.OPMOD != mode) { }
}

static void filter_std(volatile uint8_t *obj, volatile uint8_t *mask, uint16_t id, uint16_t m)
{
    obj[0] = (uint8_t)id;           /* FLTOBJ L: SID7..0 */
    obj[1] = (uint8_t)(id >> 8) & 0x07u;
    obj[2] = 0;
    obj[3] = 0;                     /* EXIDE = 0: standard frames */
    mask[0] = (uint8_t)m;
    mask[1] = (uint8_t)(m >> 8) & 0x07u;
    mask[2] = 0;
    mask[3] = 0x40;                 /* MIDE: match EXIDE */
}

void can_init(uint8_t node)
{
    /* PPS: CANTX on RB2, CANRX from RB3 (board_init unlocks/locks PPS) */
    PIN_CAN_STBY = 0;               /* MCP2562FD normal mode */

    C1CONHbits.ON = 1;
    set_mode(4);                    /* configuration */

    C1CONLbits.CLKSEL0 = 0;         /* CAN clock = Fosc 64 MHz (check against the datasheet) */
    C1CONLbits.PXEDIS = 1;
    C1CONLbits.ISOCRCEN = 1;
    C1CONHbits.BRSDIS = 1;          /* we send classic frames only for now */
    C1CONUbits.TXQEN = 1;
    C1CONUbits.STEF = 0;
    C1CONUbits.RTXAT = 0;           /* unlimited retransmissions */

    /* nominal 500 kbit/s: BRP 2 -> 32 MHz TQ clock, 64 TQ, sample point 81 % */
    C1NBTCFGT = 1;                  /* BRP - 1 */
    C1NBTCFGU = 50;                 /* TSEG1 - 1 */
    C1NBTCFGH = 11;                 /* TSEG2 - 1 */
    C1NBTCFGL = 11;                 /* SJW - 1 */
    /* data 2 Mbit/s: BRP 2, 16 TQ, sample point 81 % */
    C1DBTCFGT = 1;
    C1DBTCFGU = 11;
    C1DBTCFGH = 2;
    C1DBTCFGL = 2;
    C1TDCU = 0x02;                  /* TDCMOD = auto */
    C1TDCH = 24;                    /* TDCO = (DTSEG1 + 1) x DBRP */

    uint32_t base = (uint32_t)(uint16_t)can_ram;
    C1FIFOBAL = (uint8_t)base;
    C1FIFOBAH = (uint8_t)(base >> 8);
    C1FIFOBAU = 0;
    C1FIFOBAT = 0;

    C1TXQCONT = (uint8_t)(TXQ_DEPTH - 1u);      /* PLSIZE 0 = 8 bytes */
    C1TXQCONU = 0x60;                           /* TXAT = unlimited, TXPRI 0 */
    C1FIFOCON1T = (uint8_t)(RX_DEPTH - 1u);
    C1FIFOCON1L = 0;                            /* RX, no timestamps */

    C1FLTCON0L = 0;                             /* disable while changing */
    C1FLTCON0H = 0;
    filter_std(&C1FLTOBJ0L, &C1MASK0L, node & 0x0Fu, 0x00Fu);
    filter_std(&C1FLTOBJ1L, &C1MASK1L, 0x000u, 0x7EFu);
    C1FLTCON0L = 0x80u | 1u;                    /* FLTEN0, -> FIFO1 */
    C1FLTCON0H = 0x80u | 1u;                    /* FLTEN1, -> FIFO1 */

    set_mode(0);                                /* normal CAN FD mode */
}

uint8_t can_send(uint16_t id, const uint8_t *data, uint8_t len)
{
    if (!C1TXQSTALbits.TXQNIF) return 0;        /* queue full */
    uint8_t *obj = (uint8_t *)(uint16_t)(((uint16_t)C1TXQUAH << 8) | C1TXQUAL);
    obj[0] = (uint8_t)id;
    obj[1] = (uint8_t)(id >> 8) & 0x07u;
    obj[2] = 0;
    obj[3] = 0;
    obj[4] = len & 0x0Fu;                       /* DLC, classic, standard ID */
    obj[5] = 0;
    obj[6] = 0;
    obj[7] = 0;
    memcpy(&obj[8], data, len);
    C1TXQCONH = 0x03;                           /* UINC + TXREQ */
    return 1;
}

uint8_t can_receive(can_frame_t *f)
{
    if (!C1FIFOSTA1Lbits.TFNRFNIF) return 0;
    const uint8_t *obj = (const uint8_t *)(uint16_t)(((uint16_t)C1FIFOUA1H << 8) | C1FIFOUA1L);
    f->id = ((uint16_t)(obj[1] & 0x07u) << 8) | obj[0];
    f->ext = (obj[4] & 0x10u) != 0;
    f->len = obj[4] & 0x0Fu;
    if (f->len > 8u) f->len = 8u;               /* FD DLCs > 8: we only use 8 bytes */
    memcpy(f->data, &obj[8], 8);
    C1FIFOCON1H = 0x01;                         /* UINC */
    return 1;
}

uint8_t can_error_state(void)
{
    return C1TRECU;                             /* EWARN, RXWARN, TXWARN, RXBP, TXBP, TXBO */
}
