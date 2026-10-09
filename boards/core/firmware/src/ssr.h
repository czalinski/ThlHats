/* can-ssr nodes on CAN1 (boards/can-ssr/firmware/PROTOCOL.md): state cache,
 * SET/CLEAR/INFO requests, HOST_HB failsafe heartbeat and the UDP stream. */
#ifndef SSR_H
#define SSR_H

#include <stdint.h>
#include <stdbool.h>
#include "canfd.h"

#define SSR_CAN         1u              /* the SSR bus */
#define SSR_NODES       16u
#define SSR_SEEN_MS     2000u           /* listed while heard within this time */
#define SSR_PORT(node)  (5100u + (node))

typedef struct {
    uint32_t last_ms;                   /* 0 = never heard */
    /* STATUS */
    uint32_t status_ms;                 /* when STATUS last arrived */
    uint8_t state, build, warnings, v12;
    uint16_t faults, vset;
    /* last SET we sent and the SSR accepted */
    uint16_t ilimit;
    /* MEAS (10 mV / 10 mA) */
    uint16_t vin, vout, iavg, ipeak;
    /* INFO */
    uint32_t info_ms;                   /* when INFO last arrived */
    uint8_t type, fw_major, fw_minor;
    /* SET_ACK */
    uint32_t ack_ms;
    uint8_t ack_seq, ack_result;
} ssr_t;

void ssr_frame(const can_frame *f);     /* every frame received on SSR_CAN */
void ssr_poll(bool host_alive);         /* heartbeat, stream */
bool ssr_connected(uint8_t node);
const ssr_t *ssr_get(uint8_t node);
const char *ssr_build_name(uint8_t build);
const char *ssr_state_name(uint8_t state);
int ssr_format(uint8_t node, char *buf, uint32_t n);    /* status line, no prefix */

bool ssr_send_set(uint8_t node, uint16_t vset, uint16_t ilimit, uint8_t flags, uint8_t *seq);
bool ssr_send_clear(uint8_t node);
bool ssr_send_info_req(uint8_t node);
bool ssr_send_all_off(void);
void ssr_note_set(uint8_t node, uint16_t ilimit);   /* remember an accepted current limit */

/* UDP stream */
typedef struct {
    bool on;
    uint8_t ip[4];
    uint8_t batch;                      /* 1-10 samples per datagram */
    bool text;
    uint32_t sent, dropped;
} stream_cfg;

extern stream_cfg ssr_stream;
void ssr_stream_reset(void);            /* after a settings change */

#endif
