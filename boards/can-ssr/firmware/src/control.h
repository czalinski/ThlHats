#ifndef CONTROL_H
#define CONTROL_H

#include <stdint.h>

typedef enum { BUILD_UNKNOWN = 0, BUILD_HC = 1, BUILD_STD = 2, BUILD_HV = 3 } build_t;

typedef enum {
    ST_OFF = 0,
    ST_SEQ_GATE,        /* switch closed, supply still off */
    ST_SEQ_SUPPLY,      /* supply on, waiting for Vin */
    ST_ON,
    ST_STOPPING,        /* switch opened, supply off after a delay */
} state_t;

typedef struct {
    uint16_t vmax_10mv;
    uint16_t imax_10ma;
    uint8_t hot_ok;
} build_limits_t;

extern build_t g_build;
extern state_t g_state;
extern uint16_t g_set_v, g_set_i;
extern uint8_t g_set_flags;

void control_init(void);                /* trip reset pulse, build detection */
uint8_t control_set(uint16_t v10mv, uint16_t i10ma, uint8_t flags);     /* SET_OK or reject */
void control_off(void);                 /* immediate: switch and supply off */
void control_poll(void);                /* main loop */
void control_measurement(uint16_t iavg_10ma);   /* each MEAS period */
uint8_t control_clear(void);            /* CLEAR: trip reset + fault clear */

#endif
