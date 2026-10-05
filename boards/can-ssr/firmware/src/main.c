/* can-ssr firmware: CAN-controlled high-side switch for a Mean Well supply.
 * See ../README.md and ../PROTOCOL.md. */
#include <xc.h>
#include <string.h>
#include "board.h"
#include "can.h"
#include "config.h"
#include "control.h"
#include "display.h"
#include "faults.h"
#include "i2c.h"
#include "iso.h"
#include "protocol.h"
#include "sampling.h"

static uint8_t node;
static uint32_t t_host, t_meas, t_status, t_fault, t_disp, t_led;
static uint8_t host_seen;
static uint16_t last_iavg;
static uint16_t faults_sent;

static void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static uint16_t get16(const uint8_t *p) { return (uint16_t)(p[0] | ((uint16_t)p[1] << 8)); }

static void send_fault(void)
{
    uint8_t d[8];
    put16(&d[0], g_faults);
    d[2] = g_first_fault;
    d[3] = (uint8_t)g_state;
    put16(&d[4], g_vin_10mv);
    put16(&d[6], last_iavg);
    can_send(CAN_ID(F_FAULT, node), d, 8);
}

static void send_status(void)
{
    uint8_t d[8];
    uint32_t v12 = ((uint32_t)sampling_v12_raw() * 285u) >> 12;   /* 0.1 V: x5/4096 x 57/10 x 10 */
    uint8_t ce = can_error_state();
    if (ce & (CANERR_TXBO | CANERR_PASSIVE)) g_warnings |= WRN_CAN_ERR;
    if (v12 < 100u) g_warnings |= WRN_V12_LOW; else g_warnings &= (uint8_t)~WRN_V12_LOW;
    d[0] = (uint8_t)g_state;
    d[1] = (uint8_t)g_build;
    put16(&d[2], g_faults);
    d[4] = g_warnings;
    d[5] = v12 > 255u ? 255u : (uint8_t)v12;
    put16(&d[6], g_set_v);
    can_send(CAN_ID(F_STATUS, node), d, 8);
}

static void send_info(void)
{
    uint8_t d[8] = { BOARD_TYPE_CAN_SSR, FW_VERSION_MAJOR, FW_VERSION_MINOR, (uint8_t)g_build, node, 0, 0, 0 };
    can_send(CAN_ID(F_INFO, node), d, 8);
}

static void send_capture(uint16_t req)
{
    uint8_t d[8];
    uint16_t idx = req & 0x3FFFu;
    uint8_t which = (uint8_t)(req >> 14);
    put16(&d[0], req);
    for (uint8_t k = 0; k < 3; k++) {
        uint16_t s;
        if (which == 0) s = capt_i[(capt_i_head + idx + k) & (CAPTURE_I_LEN - 1u)];
        else if (which == 1) s = capt_vin[(capt_v_head + idx + k) & (CAPTURE_V_LEN - 1u)];
        else s = capt_vout[(capt_v_head + idx + k) & (CAPTURE_V_LEN - 1u)];
        put16(&d[2 + 2 * k], s);
    }
    can_send(CAN_ID(F_CAPT_DATA, node), d, 8);
}

static void handle_frame(const can_frame_t *f, uint32_t now)
{
    if (f->ext) return;
    uint8_t fn = CAN_FUNC(f->id), nd = CAN_NODE(f->id);

    if (fn == F_ALL_OFF && nd == 0) { control_set(0, 0, 0); control_off(); return; }
    if (fn == F_HOST_HB && nd == 0) { t_host = now; host_seen = 1; return; }
    if (nd != node) return;

    switch (fn) {
    case F_SET:
        if (f->len >= 5) {
            uint8_t ack[2];
            ack[0] = f->len >= 6 ? f->data[5] : 0;
            ack[1] = control_set(get16(&f->data[0]), get16(&f->data[2]), f->data[4]);
            can_send(CAN_ID(F_SET_ACK, node), ack, 2);
        }
        t_host = now; host_seen = 1;
        break;
    case F_CLEAR:
        control_clear();
        t_host = now; host_seen = 1;
        break;
    case F_CAPT_READ:
        if (f->len >= 2) send_capture(get16(&f->data[0]));
        t_host = now;
        break;
    case F_INFO_REQ:
        send_info();
        t_host = now;
        break;
    case F_FAULT: case F_MEAS: case F_STATUS: case F_INFO: case F_CAPT_DATA: case F_SET_ACK:
        fault_raise(FLT_ADDR_CONFLICT);         /* another node sends with our number */
        break;
    default:
        break;
    }
}

static void update_display(uint32_t now)
{
    if (g_faults) {
        display_fault((uint8_t)(g_first_fault + 1u));
    } else if ((now / DISPLAY_TOGGLE_MS) & 1u) {
        display_value(last_iavg, IND_A);
    } else {
        display_value(g_state == ST_OFF ? g_vin_10mv : g_vout_10mv, IND_V);
    }
}

static void update_leds(uint32_t now)
{
    uint8_t link = host_seen && (now - t_host < HOST_TIMEOUT_MS);
    if (g_state == ST_ON) PIN_LED_STATUS = 1;
    else if (link) PIN_LED_STATUS = (now % 1000u) < 500u;      /* slow blink: idle, host present */
    else PIN_LED_STATUS = (now % 2000u) < 50u;                  /* short flash: no host */
    if (g_faults) PIN_LED_FAULT = 1;
    else PIN_LED_FAULT = g_warnings ? (now % 500u) < 250u : 0;
}

void __interrupt(irq(default), base(8)) default_isr(void) { }

void main(void)
{
    board_init();
    sampling_init();
    INTCON0bits.GIE = 1;

    node = board_read_address();
    display_init();
    control_off();
    control_init();                             /* trip reset, build detection (~100 ms) */

    static const uint8_t bch[4][2] = {
        { SEGCH_dash, SEGCH_dash }, { SEGCH_H, SEGCH_C }, { SEGCH_S, SEGCH_t }, { SEGCH_H, SEGCH_U }
    };
    display_boot(bch[g_build][0], bch[g_build][1], node);

    i2c_init();
    iso_init();
    can_init(node);
    send_info();

    uint32_t now = millis();
    t_host = t_meas = t_status = t_fault = t_led = now;
    t_disp = now + 1500u;                       /* keep the boot screen up */

    for (;;) {
        CLRWDT();
        now = millis();

        can_frame_t f;
        while (can_receive(&f)) handle_frame(&f, now);

        /* failsafe: only armed while the output is requested on */
        if ((g_set_v || g_state != ST_OFF) && now - t_host >= HOST_TIMEOUT_MS) {
            fault_raise(FLT_HOST_TIMEOUT);
            g_set_v = 0;
        }

        iso_poll();
        control_poll();
        capture_service();

        if (now - t_meas >= MEAS_PERIOD_MS) {
            t_meas += MEAS_PERIOD_MS;
            isample_acc_t a;
            sampling_take_period(&a);
            uint16_t avg = a.count ? (uint16_t)(a.sum / a.count) : 0;
            last_iavg = current_raw_to_10ma(avg);
            control_measurement(last_iavg);
            capture_push_v(g_vin_10mv, g_vout_10mv);
            uint8_t d[8];
            put16(&d[0], g_vin_10mv);
            put16(&d[2], g_vout_10mv);
            put16(&d[4], last_iavg);
            put16(&d[6], current_raw_to_10ma(a.peak));
            can_send(CAN_ID(F_MEAS, node), d, 8);
        }

        if (g_faults != faults_sent || (g_faults && now - t_fault >= FAULT_REPEAT_MS)) {
            if (g_faults) send_fault();
            faults_sent = g_faults;
            t_fault = now;
        }

        if (now - t_status >= STATUS_PERIOD_MS) {
            t_status = now;
            send_status();
        }

        if ((int32_t)(now - t_disp) >= 0) {
            t_disp = now + 250u;
            update_display(now);
        }
        update_leds(now);
    }
}
