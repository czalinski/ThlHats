#include <xc.h>
#include "board.h"
#include "sampling.h"

uint16_t capt_i[CAPTURE_I_LEN];
uint16_t capt_vin[CAPTURE_V_LEN];
uint16_t capt_vout[CAPTURE_V_LEN];
volatile uint16_t capt_i_head;
uint8_t capt_v_head;
volatile uint8_t capt_frozen;
static uint16_t capt_freeze_in;         /* ms until freeze, 0 = not counting */
static uint32_t capt_freeze_at;

static volatile uint32_t ms_count;
static volatile uint8_t half_ms;
static volatile isample_acc_t acc;
static volatile uint16_t build_raw, v12_raw;
static uint8_t slot;
static uint8_t slow_sel;
static uint8_t cur_ch;                  /* channel converted by the conversion in flight */
static uint16_t pair_first;             /* first of two 2 kHz samples, for the 1 kHz capture */

void sampling_init(void)
{
    /* ADCC: right-justified, FRC clock, VDD/VSS references, basic mode */
    ADCON0 = 0;
    ADCON0bits.FM = 1;
    ADCON0bits.CS = 1;
    ADCON1 = 0;
    ADCON2 = 0;
    ADCON3 = 0;
    ADREF = 0;
    ADACQ = 16;                         /* ~16 us acquisition (R24 1k + C22 source) */
    ADPCH = ADC_CH_ACS;
    cur_ch = ADC_CH_ACS;
    ADCON0bits.ON = 1;

    /* TMR0: Fosc/4 = 16 MHz, 1:64 -> 250 kHz, 8-bit period 125 -> 2 kHz */
    T0CON0 = 0;
    T0CON1 = 0;
    T0CON1bits.CS = 0b010;              /* Fosc/4 */
    T0CON1bits.CKPS = 0b0110;           /* 1:64 */
    TMR0H = 124;
    TMR0L = 0;
    PIR3bits.TMR0IF = 0;
    PIE3bits.TMR0IE = 1;
    T0CON0bits.EN = 1;
    ADCON0bits.GO = 1;
}

void __interrupt(irq(TMR0), base(8)) tmr0_isr(void)
{
    PIR3bits.TMR0IF = 0;
    uint16_t r = ((uint16_t)ADRESH << 8) | ADRESL;  /* conversion started 500 us ago */

    if (cur_ch == ADC_CH_ACS) {
        acc.sum += r;
        acc.count++;
        if (r > acc.peak) acc.peak = r;
        if (!capt_frozen) {
            if (half_ms) {
                capt_i[capt_i_head] = (uint16_t)((pair_first + r) >> 1);
                capt_i_head = (capt_i_head + 1u) & (CAPTURE_I_LEN - 1u);
            } else {
                pair_first = r;
            }
        }
    } else if (cur_ch == ADC_CH_BUILD) {
        build_raw = r;
    } else {
        v12_raw = r;
    }

    /* next conversion: current, except one slow slot every SLOW_SLOT_EVERY */
    if (++slot >= SLOW_SLOT_EVERY) {
        slot = 0;
        slow_sel ^= 1u;
        cur_ch = slow_sel ? ADC_CH_BUILD : ADC_CH_V12;
    } else {
        cur_ch = ADC_CH_ACS;
    }
    ADPCH = cur_ch;
    ADCON0bits.GO = 1;

    if (half_ms) ms_count++;
    half_ms ^= 1u;
}

uint32_t millis(void)
{
    uint32_t t;
    PIE3bits.TMR0IE = 0;
    t = ms_count;
    PIE3bits.TMR0IE = 1;
    return t;
}

void sampling_take_period(isample_acc_t *out)
{
    PIE3bits.TMR0IE = 0;
    out->sum = acc.sum;
    out->count = acc.count;
    out->peak = acc.peak;
    acc.sum = 0;
    acc.count = 0;
    acc.peak = 0;
    PIE3bits.TMR0IE = 1;
}

uint16_t sampling_build_raw(void)
{
    uint16_t v;
    PIE3bits.TMR0IE = 0;
    v = build_raw;
    PIE3bits.TMR0IE = 1;
    return v;
}

uint16_t sampling_v12_raw(void)
{
    uint16_t v;
    PIE3bits.TMR0IE = 0;
    v = v12_raw;
    PIE3bits.TMR0IE = 1;
    return v;
}

void capture_push_v(uint16_t vin, uint16_t vout)
{
    if (capt_frozen) return;
    capt_vin[capt_v_head] = vin;
    capt_vout[capt_v_head] = vout;
    capt_v_head = (uint8_t)((capt_v_head + 1u) & (CAPTURE_V_LEN - 1u));
}

void capture_freeze_after(uint16_t ms)
{
    if (capt_frozen || capt_freeze_in) return;      /* keep the first event */
    capt_freeze_in = ms ? ms : 1u;
    capt_freeze_at = millis() + ms;
}

void capture_service(void)
{
    if (capt_freeze_in && (int32_t)(millis() - capt_freeze_at) >= 0) {
        capt_frozen = 1;
        capt_freeze_in = 0;
    }
}

void capture_rearm(void)
{
    capt_freeze_in = 0;
    capt_frozen = 0;
}

/* ACS770ECB-100U: 0.5 V at 0 A, 40 mV/A, ratiometric to 5 V.
 * raw = 4096 * V / 5 -> 0 A = 409.6 counts, 32.768 counts/A = 0.32768 counts per 10 mA. */
uint16_t current_raw_to_10ma(uint16_t raw)
{
    if (raw <= 410u) return 0;
    return (uint16_t)(((uint32_t)(raw - 410u) * 6250u) >> 11);  /* x 3.0518 */
}
