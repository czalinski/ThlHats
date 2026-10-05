#ifndef CAN_H
#define CAN_H

#include <stdint.h>

typedef struct {
    uint16_t id;
    uint8_t ext;
    uint8_t len;
    uint8_t data[8];
} can_frame_t;

void can_init(uint8_t node);
uint8_t can_send(uint16_t id, const uint8_t *data, uint8_t len);    /* 0 = queue full */
uint8_t can_receive(can_frame_t *f);                                /* 1 = got a frame */
uint8_t can_error_state(void);

#define CANERR_TXBO     0x20u
#define CANERR_PASSIVE  0x18u

#endif
