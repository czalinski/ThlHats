/* io-card (boards/io-card): 4 relay drivers, 4 GPIO, 2 differential analog
 * inputs, all on core PIC32 pins through the stack bus (tools/stack_bus.py).
 *
 *   RLY1-4   RB15, RG6, RG9, RA12   -> AQW212 LEDs (high = output on)
 *   GPIO1-4  RA11, RA0, RB11, RB12  3.3 V, 330R + clamp on the card
 *   AI1P/N   AN12 (RE12) / AN13 (RE13)
 *   AI2P/N   AN11 (RC11) / AN8 (RC2)
 *   VMID     OA5 unity-gain follower of VMID_REF (RA4); output RB7 = AN25
 *
 * Each AI leg is 10M / 130k to VMID on the card: Vpin = VMID + Vleg / 77.92.
 * The firmware reads both legs on the shared ADC7 (single conversions:
 * errata DS80000898D 2.3.1 makes its scan mode inaccurate) and subtracts. */
#ifndef IO_H
#define IO_H

#include <stdint.h>
#include <stdbool.h>

#define IO_GPIOS    4u
#define IO_RELAYS   4u
#define IO_AIS      2u

typedef enum { GPIO_IN, GPIO_OUT } gpio_mode;
typedef enum { PULL_NONE, PULL_UP, PULL_DOWN } gpio_pull;

typedef struct {
    int32_t diff_mv;                    /* AIn+ - AIn-, zero offset applied */
    int32_t p_mv, n_mv;                 /* each leg against the LOGIC ground */
    bool over;                          /* a leg is at the ADC rail */
} ai_reading;

void io_init(void);                     /* ADC, OA5, relay/GPIO pins; detects the card */
bool io_detect(void);
bool io_present(void);
uint16_t io_vmid_mv(void);

void io_relay_set(uint8_t n, bool on);  /* n = 1-4 */
bool io_relay_get(uint8_t n);

void io_gpio_config(uint8_t n, gpio_mode mode, gpio_pull pull, bool out);
void io_gpio_get(uint8_t n, gpio_mode *mode, gpio_pull *pull, bool *out, bool *level);

void io_ai_read(uint8_t n, ai_reading *r);      /* about 1 ms (64 samples per leg) */
int16_t io_ai_zero(uint8_t n);                  /* measure and store the offset (inputs shorted) */

#endif
