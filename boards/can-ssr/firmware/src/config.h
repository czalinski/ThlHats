/* Fixed firmware settings. Units on the bus: voltage 10 mV, current 10 mA. */
#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

#define FW_VERSION_MAJOR        0
#define FW_VERSION_MINOR        2
#define BOARD_TYPE_CAN_SSR      0x01    /* ThlHats board type code */

#define FOSC_HZ                 64000000UL

/* Failsafe: while the output is requested on, it switches off when no SET for
 * this node arrives within the timeout carried by the last SET (bytes 6-7).
 * A SET without them (6-byte frame) uses the default. */
#define HOST_TIMEOUT_MS         1000u   /* default */
#define HOST_TIMEOUT_MIN_MS     100u
#define HOST_TIMEOUT_MAX_MS     60000u
#define HOST_LINK_MS            1000u   /* status LED: host seen (any host frame, HOST_HB) */

#define MEAS_PERIOD_MS          10u     /* 100 Hz MEAS frames */
#define STATUS_PERIOD_MS        1000u   /* STATUS frame */
#define FAULT_REPEAT_MS         1000u   /* FAULT frame repeat while a fault is active */
#define DISPLAY_TOGGLE_MS       2000u   /* V / A alternation */
#define REGULATE_PERIOD_MS      100u    /* PV closed loop on measured Vin */

/* Current sampling (PIC ADC, ACS770): 2 kHz, every 40th slot reads a slow channel */
#define ISAMPLE_HZ              2000u
#define SLOW_SLOT_EVERY         40u

/* Fault capture: 1 kHz current history and 100 Hz voltages, frozen shortly
 * after a fault so the window holds ~0.8 s before and ~0.2 s after it. */
#define CAPTURE_I_LEN           1024u   /* 1.024 s at 1 kHz */
#define CAPTURE_V_LEN           128u    /* 1.28 s at 100 Hz */
#define CAPTURE_POST_MS         200u

/* Sequenced turn-on timing */
#define SEQ_GATE_SETTLE_MS      50u     /* switch closed, supply still off */
#define SEQ_SUPPLY_RISE_MS      2000u   /* Vin must reach 90 % of the set point */
#define SEQ_OFF_SUPPLY_DELAY_MS 20u     /* switch opened before supply off */

/* Plausibility checks while on */
#define SWITCH_DROP_MAX_10MV    200u    /* Vin - Vout above 2 V for ... */
#define SWITCH_DROP_TIME_MS     200u    /* ... this long: switch failed open */
#define SW_OC_TIME_MS           20u     /* average current above limit this long */
#define HOT_SWITCH_VIN_MAX_HV   2000u   /* HV build: refuse hot turn-on above 20 V */

#endif
