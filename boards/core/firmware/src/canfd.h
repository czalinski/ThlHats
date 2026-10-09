/* The four CAN FD modules of the PIC32MK, wired to the can-card through the
 * stack bus (C1TX/C1RX .. C4TX/C4RX, tools/stack_bus.py).
 *
 * Detection: the can-card's ISOW1044 transceivers drive RXD high while their
 * bus is recessive. With the module off and a pull-down on the RX pin, a
 * channel whose RX pin reads mostly high has a transceiver behind it; with no
 * card the pin sits low. A present channel on a bus stuck dominant reads as
 * absent. The TX pin is never pulled down (a card's TXD would see dominant)
 * and is only driven once the channel is detected and started.
 *
 * Channels are numbered 1-4 as on the card (CAN1 = CFD1). */
#ifndef CANFD_H
#define CANFD_H

#include <stdint.h>
#include <stdbool.h>

#define CAN_CHANNELS    4u

/* can_frame.flags */
#define CAN_EXT         0x01u           /* 29-bit identifier */
#define CAN_FDF         0x02u           /* CAN FD frame */
#define CAN_BRS         0x04u           /* bit rate switch (FD only) */
#define CAN_RTR         0x08u           /* remote frame (classic only) */
#define CAN_ESI         0x10u           /* error state indicator (FD, received) */

typedef struct {
    uint32_t id;
    uint8_t len;                        /* 0-8 classic; 0-8, 12, 16, 20, 24, 32, 48, 64 FD */
    uint8_t flags;
    uint8_t data[64];
} can_frame;

typedef enum {
    CAN_MODE_FD,                        /* normal CAN FD: classic and FD frames */
    CAN_MODE_CLASSIC,                   /* normal CAN 2.0: error frames on FD frames */
    CAN_MODE_LISTEN,                    /* listen only, never drives the bus */
    CAN_MODE_LOOPBACK,                  /* internal loopback, pins untouched */
} can_mode;

typedef struct {
    bool present;                       /* transceiver found by can_detect() */
    bool running;
    can_mode mode;
    uint32_t nominal;                   /* bit/s */
    uint32_t data;                      /* bit/s, FD data phase */
    uint8_t tec, rec;
    bool error_passive, bus_off;
    uint32_t rx_frames, tx_frames;
    uint32_t rx_overflows, tx_full;
} can_status;

#define CAN_DEFAULT_NOMINAL 500000u     /* matches the can-ssr bus */
#define CAN_DEFAULT_DATA    2000000u

void can_init(void);                    /* detect, then start present channels at the defaults */
uint8_t can_detect(void);               /* re-detect stopped channels; returns the present mask (bit 0 = CAN1) */
bool can_start(uint8_t ch, can_mode mode, uint32_t nominal, uint32_t data);
void can_stop(uint8_t ch);
bool can_send(uint8_t ch, const can_frame *f);     /* false: TX FIFO full or channel stopped */
bool can_receive(uint8_t ch, can_frame *f);        /* false: nothing received */
void can_get_status(uint8_t ch, can_status *s);
bool can_selftest(uint8_t ch);          /* internal loopback, restores the previous state */
bool can_timing_ok(uint32_t nominal, uint32_t data);

uint8_t can_len_to_dlc(uint8_t len);    /* rounds up to the next valid FD length */
uint8_t can_dlc_to_len(uint8_t dlc);

#endif
