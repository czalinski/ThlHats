/* Power path control: build detection, sequenced turn-on through the Mean
 * Well remote input, PV closed loop on Vin, plausibility monitors. */
#include <xc.h>
#include "board.h"
#include "config.h"
#include "control.h"
#include "faults.h"
#include "iso.h"
#include "protocol.h"
#include "sampling.h"

build_t g_build = BUILD_UNKNOWN;
state_t g_state = ST_OFF;
uint16_t g_set_v, g_set_i;
uint8_t g_set_flags;

static const build_limits_t limits[4] = {
    { 0, 0, 0 },                /* unknown: nothing allowed */
    { 6000, 5000, 1 },          /* HC: 60 V, 50 A, hot switching allowed */
    { 15000, 2500, 1 },         /* STD: 150 V, 25 A */
    { 20000, 1200, 0 },         /* HV: 200 V, 12 A, sequenced only */
};

static uint32_t t_state, t_reg, t_drop, t_short;
static uint8_t oc_count;

static void delay_ms(uint16_t ms)
{
    uint32_t t = millis();
    while (millis() - t < ms) CLRWDT();
}

/* VTH = 5 V x 10k / (Rbuild + 10k), ADC raw = VTH x 4096 / 5:
 * HC 7.15k -> 2.92 V -> 2388, STD 16.2k -> 1.91 V -> 1563, HV 35.7k -> 1.10 V -> 896.
 * Bands +-12 %. While the trip is latched VTH reads ~0.3 V. */
static build_t classify(uint16_t raw)
{
    if (raw >= 2100u && raw <= 2680u) return BUILD_HC;
    if (raw >= 1375u && raw <= 1750u) return BUILD_STD;
    if (raw >= 790u && raw <= 1005u) return BUILD_HV;
    return BUILD_UNKNOWN;
}

static void trip_reset_pulse(void)
{
    PIN_GATE_EN = 0;
    PIN_TRIP_RST = 1;
    delay_ms(2);
    PIN_TRIP_RST = 0;
    delay_ms(100);              /* VTH recovers; two slow ADC slots of each channel */
}

void control_init(void)
{
    trip_reset_pulse();
    g_build = classify(sampling_build_raw());
    if (g_build == BUILD_UNKNOWN) fault_raise(FLT_BUILD);
}

void control_off(void)
{
    PIN_GATE_EN = 0;
    PIN_MW_REMOTE = 0;
    iso_set_pv(0);
    iso_set_pc(0);
    g_state = ST_OFF;
}

uint8_t control_set(uint16_t v, uint16_t i, uint8_t flags)
{
    const build_limits_t *L = &limits[g_build];
    if (v == 0) {                               /* 0 = disable */
        g_set_v = 0;
        if (g_state != ST_OFF) {
            PIN_GATE_EN = 0;
            g_state = ST_STOPPING;
            t_state = millis();
        }
        return SET_OK;
    }
    if (g_faults) return SET_REJ_FAULT;
    if (v > L->vmax_10mv) return SET_REJ_VOLTAGE;
    if (i > L->imax_10ma) return SET_REJ_CURRENT;
    if ((flags & SETF_HOT) && (!L->hot_ok || (g_build == BUILD_HV && g_vin_10mv > HOT_SWITCH_VIN_MAX_HV)))
        return SET_REJ_HOT;
    g_set_v = v;
    g_set_i = i;
    g_set_flags = flags;
    if (!(flags & SETF_NO_REG) && g_state == ST_ON) iso_set_pc(pc_code_for(i ? i : L->imax_10ma));
    return SET_OK;
}

uint8_t control_clear(void)
{
    control_off();
    if (!PIN_TRIP_OK) trip_reset_pulse();
    if (g_build == BUILD_UNKNOWN) g_build = classify(sampling_build_raw());
    fault_clear();
    if (g_build == BUILD_UNKNOWN) { fault_raise(FLT_BUILD); return 0; }
    if (!PIN_TRIP_OK) { fault_raise(FLT_HW_TRIP); return 0; }
    return 1;
}

/* called every MEAS period with that period's average current */
void control_measurement(uint16_t iavg)
{
    if (g_state == ST_ON && g_set_i && iavg > g_set_i) {
        if (++oc_count >= SW_OC_TIME_MS / MEAS_PERIOD_MS) fault_raise(FLT_SW_OC);
    } else {
        oc_count = 0;
    }
}

static void monitors(uint32_t now)
{
    if (!PIN_TRIP_OK) fault_raise(FLT_HW_TRIP);
    if (!g_iso_ok) fault_raise(FLT_ISO_COMM);
    if (g_build != BUILD_UNKNOWN && g_vin_10mv > limits[g_build].vmax_10mv + limits[g_build].vmax_10mv / 20u)
        fault_raise(FLT_OVERVOLTAGE);

    /* switch failed open: on, Vin present, Vout well below it */
    if (g_state == ST_ON && g_vin_10mv > 500u && g_vin_10mv > g_vout_10mv + SWITCH_DROP_MAX_10MV) {
        if (now - t_drop >= SWITCH_DROP_TIME_MS) fault_raise(FLT_SWITCH_OPEN);
    } else {
        t_drop = now;
    }
    /* off for a while, live input, output follows it: a shorted switch, or a
     * charged DUT capacitor with no load (1 mF on the 1 MOhm divider holds for
     * minutes), so this is a warning, not a fault */
    if (g_state == ST_OFF && !PIN_GATE_EN && g_vin_10mv > 1000u && g_vout_10mv + 200u > g_vin_10mv) {
        if (now - t_short >= 1000u) g_warnings |= WRN_VOUT_LIVE;
    } else {
        t_short = now;
        g_warnings &= (uint8_t)~WRN_VOUT_LIVE;
    }
}

void control_poll(void)
{
    uint32_t now = millis();
    monitors(now);

    if (g_faults && g_state != ST_OFF) {
        control_off();
        return;
    }

    switch (g_state) {
    case ST_OFF:
        if (g_set_v && !g_faults) {
            if (g_set_flags & SETF_HOT) {
                PIN_MW_REMOTE = 1;              /* harmless if no remote is wired */
                PIN_GATE_EN = 1;
                g_state = ST_ON;
            } else {
                PIN_MW_REMOTE = 0;
                PIN_GATE_EN = 1;                /* close the switch with no voltage on it */
                g_state = ST_SEQ_GATE;
            }
            t_state = t_reg = now;
        }
        break;

    case ST_SEQ_GATE:
        if (now - t_state >= SEQ_GATE_SETTLE_MS) {
            if (!(g_set_flags & SETF_NO_REG)) {
                iso_set_pc(pc_code_for(g_set_i ? g_set_i : limits[g_build].imax_10ma));
                iso_set_pv(pv_code_for(g_set_v));
            }
            PIN_MW_REMOTE = 1;
            g_state = ST_SEQ_SUPPLY;
            t_state = now;
        }
        break;

    case ST_SEQ_SUPPLY:
        if ((uint32_t)g_vin_10mv * 10u >= (uint32_t)g_set_v * 9u) {
            g_state = ST_ON;
            t_reg = now;
        } else if (now - t_state >= SEQ_SUPPLY_RISE_MS) {
            fault_raise(FLT_SUPPLY_NO_RISE);
        }
        break;

    case ST_ON:
        if (!(g_set_flags & SETF_NO_REG) && now - t_reg >= REGULATE_PERIOD_MS) {
            /* integral step: a quarter of the error converted to PV codes */
            int32_t err = (int32_t)g_set_v - (int32_t)g_vin_10mv;
            int32_t step = (err << 6) / (int32_t)g_cal.pv_slope_q8;     /* err/slope/4 */
            int32_t code = (int32_t)iso_pv_code() + step;
            g_warnings &= (uint8_t)~WRN_REG_LIMIT;
            if (code < 0) { code = 0; g_warnings |= WRN_REG_LIMIT; }
            if (code > 4095) { code = 4095; g_warnings |= WRN_REG_LIMIT; }
            iso_set_pv((uint16_t)code);
            t_reg = now;
        }
        break;

    case ST_STOPPING:
        if (now - t_state >= SEQ_OFF_SUPPLY_DELAY_MS) control_off();
        break;
    }
}
