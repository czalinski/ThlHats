/* can-ssr CAN protocol (see ../PROTOCOL.md).
 *
 * 11-bit identifiers: ID = (function << 4) | node, node = rotary switch 0-15.
 * Lower ID wins arbitration, so emergency/faults sort first and bulk data last.
 * Every frame is at most 8 bytes and sent as classic CAN, so the node works
 * on a classic CAN 2.0 bus and on a CAN FD bus. Multi-byte fields are
 * little-endian. Voltage unit 10 mV, current unit 10 mA (uint16).
 */
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define CAN_ID(func, node)      ((uint16_t)(((uint16_t)(func) << 4) | ((node) & 0x0Fu)))
#define CAN_FUNC(id)            ((uint8_t)((id) >> 4))
#define CAN_NODE(id)            ((uint8_t)((id) & 0x0Fu))

/* host -> all nodes (node field 0) */
#define F_ALL_OFF       0x00    /* 0 bytes: every node switches off now */
#define F_HOST_HB       0x01    /* 0-8 bytes: host present (status LED only; does not feed the failsafe) */

/* node -> host */
#define F_FAULT         0x08    /* on a new fault, then every FAULT_REPEAT_MS while active */

/* host -> node */
#define F_SET           0x10    /* u16 Vset (0 = off), u16 Ilimit, u8 flags, u8 seq[, u16 failsafe timeout ms] */
#define F_CLEAR         0x11    /* 0 bytes: clear latched faults (resets the trip latch) */
#define F_CAPT_READ     0x13    /* u16 index, u8 which (0 = current, 1 = voltages) */
#define F_INFO_REQ      0x14    /* 0 bytes: reply with INFO */

/* node -> host */
#define F_MEAS          0x20    /* u16 Vin, u16 Vout, u16 Iavg, u16 Ipeak (one period) */
#define F_STATUS        0x21    /* see protocol.c */
#define F_INFO          0x22    /* board type, fw version, build, node, serial */
#define F_CAPT_DATA     0x23    /* u16 index, 3 x u16 samples */
#define F_SET_ACK       0x24    /* u8 seq, u8 result (0 = accepted, else reject code) */

/* SET flags */
#define SETF_HOT        0x01    /* no Mean Well remote: switch a live supply (HC/STD only) */
#define SETF_NO_REG     0x02    /* don't drive PV/PC (fixed supply) */

/* SET_ACK result codes */
#define SET_OK              0
#define SET_REJ_FAULT       1   /* a fault is latched: send CLEAR first */
#define SET_REJ_VOLTAGE     2   /* above this build's maximum */
#define SET_REJ_CURRENT     3   /* above this build's maximum */
#define SET_REJ_HOT         4   /* hot switching not allowed on this build / Vin too high */

#endif
