/* Load side behind the ISO1640: two MCP3426 (Vin, Vout + DAC feedback) and
 * two MCP4725 (Mean Well PV and PC). */
#ifndef ISO_H
#define ISO_H

#include <stdint.h>

typedef struct {
    uint16_t vin_gain_q12;      /* 10 mV per ADC count x 4096 */
    uint16_t vout_gain_q12;
    int16_t  pv_v0_10mv;        /* supply output at PV code 0 (extrapolated) */
    uint16_t pv_slope_q8;       /* 10 mV per PV code x 256 */
    uint16_t pc_full_10ma;      /* supply current limit at PC code 4095 */
} cal_t;

extern cal_t g_cal;

extern uint16_t g_vin_10mv, g_vout_10mv;    /* latest, 0 if unknown */
extern uint16_t g_pv_fb_mv, g_pc_fb_mv;     /* DAC outputs read back, mV at MW_PV/PC */
extern uint8_t  g_iso_ok;                   /* all four devices answering */

void iso_init(void);
void iso_poll(void);                        /* call often; at most one I2C transaction */
void iso_set_pv(uint16_t code);
void iso_set_pc(uint16_t code);
uint16_t iso_pv_code(void);
uint16_t pv_code_for(uint16_t v10mv);
uint16_t pc_code_for(uint16_t i10ma);

#endif
