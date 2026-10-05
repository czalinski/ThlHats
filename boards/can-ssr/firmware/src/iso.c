#include <xc.h>
#include "board.h"
#include "config.h"
#include "i2c.h"
#include "iso.h"
#include "sampling.h"

/* Defaults until calibration is stored in EEPROM.
 * Dividers 3 x 332k + 8.06k: 124.57 mV per MCP3426 count (1 mV, 12 bit, gain 1).
 * PV default: Mean Well UHP-1500-115, PV 1.0 V -> 57.5 V, 4.8 V -> 138 V. */
cal_t g_cal = {
    .vin_gain_q12  = 51024,     /* 12.457 x 4096 */
    .vout_gain_q12 = 51024,
    .pv_v0_10mv    = 3632,      /* 36.3 V */
    .pv_slope_q8   = 662,       /* 2.586 (10 mV) per code */
    .pc_full_10ma  = 1305,      /* 13.05 A at 5 V */
};

uint16_t g_vin_10mv, g_vout_10mv;
uint16_t g_pv_fb_mv, g_pc_fb_mv;
uint8_t g_iso_ok;

#define MCP3426_CH1_CONT    0x10    /* continuous, CH1, 240 SPS 12 bit, gain 1 */
#define MCP3426_CH2_CONT    0x30
#define FB_EVERY_MS         1000u   /* read the PV/PC feedback channel this often */
#define STALE_MS            100u    /* no fresh Vin/Vout for this long = ISO fault */

static uint16_t pv_code, pc_code;
static uint8_t pv_dirty, pc_dirty;
static uint8_t step;
static uint32_t last_fb, last_vin_ok, last_vout_ok;
static uint8_t fb_phase;            /* 0: normal, 1: reading feedback */

static uint8_t adc_config(uint8_t addr, uint8_t cfg)
{
    return i2c_write(addr, &cfg, 1);
}

/* returns 1 and the signed count if a new conversion is ready */
static uint8_t adc_read(uint8_t addr, int16_t *count, uint8_t *fresh)
{
    uint8_t b[3];
    if (!i2c_read(addr, b, 3)) return 0;
    *fresh = (b[2] & 0x80u) == 0;
    *count = (int16_t)(((uint16_t)b[0] << 8) | b[1]);
    return 1;
}

static uint16_t to_10mv(int16_t count, uint16_t gain_q12)
{
    if (count <= 0) return 0;
    return (uint16_t)(((uint32_t)count * gain_q12) >> 12);
}

static uint8_t dac_write(uint8_t addr, uint16_t code)
{
    uint8_t b[2] = { (uint8_t)((code >> 8) & 0x0Fu), (uint8_t)code };   /* fast mode, PD = 00 */
    return i2c_write(addr, b, 2);
}

/* MCP4725 power-on value lives in its EEPROM: make sure it is 0 so the supply
 * programming inputs come up at zero after any power cycle. */
static void dac_force_por_zero(uint8_t addr)
{
    uint8_t b[5];
    if (!i2c_read(addr, b, 5)) return;
    if ((b[3] & 0x6Fu) == 0 && b[4] == 0) return;    /* PD bits and D11..D0 already 0 */
    uint8_t w[3] = { 0x60, 0x00, 0x00 };            /* write DAC register and EEPROM */
    i2c_write(addr, w, 3);
}

void iso_init(void)
{
    dac_force_por_zero(I2C_DAC_PV);
    dac_force_por_zero(I2C_DAC_PC);
    g_iso_ok = dac_write(I2C_DAC_PV, 0) & dac_write(I2C_DAC_PC, 0)
             & adc_config(I2C_ADC_VIN, MCP3426_CH1_CONT) & adc_config(I2C_ADC_VOUT, MCP3426_CH1_CONT);
    uint32_t t = millis();
    last_fb = last_vin_ok = last_vout_ok = t;
}

void iso_set_pv(uint16_t code) { if (code > 4095u) code = 4095u; if (code != pv_code) { pv_code = code; pv_dirty = 1; } }
void iso_set_pc(uint16_t code) { if (code > 4095u) code = 4095u; if (code != pc_code) { pc_code = code; pc_dirty = 1; } }
uint16_t iso_pv_code(void) { return pv_code; }

uint16_t pv_code_for(uint16_t v10mv)
{
    int32_t d = (int32_t)v10mv - g_cal.pv_v0_10mv;
    if (d <= 0) return 0;
    d = (d << 8) / g_cal.pv_slope_q8;
    return d > 4095 ? 4095u : (uint16_t)d;
}

uint16_t pc_code_for(uint16_t i10ma)
{
    uint32_t c = ((uint32_t)i10ma * 4095u) / g_cal.pc_full_10ma;
    return c > 4095u ? 4095u : (uint16_t)c;
}

/* One I2C transaction per call, round robin. */
void iso_poll(void)
{
    int16_t count;
    uint8_t fresh, ok;
    uint32_t now = millis();

    switch (step) {
    case 0:                                     /* DAC updates first */
        if (pv_dirty) { ok = dac_write(I2C_DAC_PV, pv_code); pv_dirty = !ok; break; }
        if (pc_dirty) { ok = dac_write(I2C_DAC_PC, pc_code); pc_dirty = !ok; break; }
        step = 1;
        /* fall through */
    case 1:
        if (adc_read(I2C_ADC_VIN, &count, &fresh) && fresh) {
            if (fb_phase) g_pv_fb_mv = (uint16_t)(count > 0 ? count * 3 : 0);   /* 20k/10k divider */
            else { g_vin_10mv = to_10mv(count, g_cal.vin_gain_q12); last_vin_ok = now; }
        }
        break;
    case 2:
        if (adc_read(I2C_ADC_VOUT, &count, &fresh) && fresh) {
            if (fb_phase) g_pc_fb_mv = (uint16_t)(count > 0 ? count * 3 : 0);
            else { g_vout_10mv = to_10mv(count, g_cal.vout_gain_q12); last_vout_ok = now; }
        }
        break;
    case 3:                                     /* feedback channel once a second, ~10 ms */
        if (!fb_phase && now - last_fb >= FB_EVERY_MS) {
            fb_phase = 1; last_fb = now;
            adc_config(I2C_ADC_VIN, MCP3426_CH2_CONT);
            adc_config(I2C_ADC_VOUT, MCP3426_CH2_CONT);
        } else if (fb_phase && now - last_fb >= 10u) {
            fb_phase = 0;
            adc_config(I2C_ADC_VIN, MCP3426_CH1_CONT);
            adc_config(I2C_ADC_VOUT, MCP3426_CH1_CONT);
            last_vin_ok = last_vout_ok = now;   /* the gap is planned */
        }
        break;
    }
    step = (uint8_t)((step + 1u) & 3u);

    g_iso_ok = (now - last_vin_ok < STALE_MS) && (now - last_vout_ok < STALE_MS);
}
