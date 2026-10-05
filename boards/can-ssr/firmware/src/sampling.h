/* 2 kHz timer interrupt: millisecond clock, ACS770 current sampling with
 * average/peak per report period, slow ADC channels, and the 1 kHz capture. */
#ifndef SAMPLING_H
#define SAMPLING_H

#include <stdint.h>
#include "config.h"

typedef struct {
    uint32_t sum;           /* sum of raw 12-bit samples */
    uint16_t count;
    uint16_t peak;          /* raw */
} isample_acc_t;

void sampling_init(void);
uint32_t millis(void);
void sampling_take_period(isample_acc_t *out);  /* atomically take and restart */
uint16_t sampling_build_raw(void);              /* latest BUILD_REF reading, raw */
uint16_t sampling_v12_raw(void);                /* latest V12_MON reading, raw */

/* capture buffers (raw 12-bit current at 1 kHz; voltages pushed by the main loop at 100 Hz) */
extern uint16_t capt_i[CAPTURE_I_LEN];
extern uint16_t capt_vin[CAPTURE_V_LEN];
extern uint16_t capt_vout[CAPTURE_V_LEN];
extern volatile uint16_t capt_i_head;
extern uint8_t capt_v_head;
extern volatile uint8_t capt_frozen;
void capture_push_v(uint16_t vin, uint16_t vout);
void capture_freeze_after(uint16_t ms);
void capture_service(void);                     /* main loop: counts down to freeze */
void capture_rearm(void);

/* raw ADC <-> engineering units (ratiometric to the 5 V supply) */
uint16_t current_raw_to_10ma(uint16_t raw);

#endif
