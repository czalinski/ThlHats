/* Core board: PIC32MK1024MCM064 pin map, clocks and timing.
 *
 * Clocks: 12 MHz crystal (Y1) -> SPLL x40 / 4 = 120 MHz SYSCLK.
 * PBCLK2/3 = 60 MHz (reset default /2): UART1, SPI3. REFCLK4 = 40 MHz for the
 * CAN FD modules (DS60001519D Register 26-1 note: max 80 MHz, 40 MHz
 * recommended). The core timer runs at SYSCLK / 2.
 *
 * Pin map (hardware/gen_schematic.py, tools/stack_bus.py MCU_PINS):
 *   C1TX RB3 (RPB3R = 12)   C1RX RB2 (C1RXR = 4)
 *   C2TX RB0 (RPB0R = 12)   C2RX RA1 (C2RXR = 0)
 *   C3TX RC1 (RPC1R = 12)   C3RX RC0 (C3RXR = 6)
 *   C4TX RA8 (RPA8R = 12)   C4RX RE15 (C4RXR = 8)
 *   U1TX RF1 (J5.1)         U1RX RC6 (J5.2)
 *   W6100 on SPI3: SCK RC9, SDO RC8, SDI RC7, CS RD5, INT RD6, RST RF0
 *   Heartbeat LED D2 on RD8. */
#ifndef BOARD_H
#define BOARD_H

#include <stdint.h>
#include <stdbool.h>

#define SYSCLK_HZ       120000000u
#define PBCLK2_HZ       60000000u   /* UART1-2, SPI1-2 */
#define PBCLK3_HZ       60000000u   /* UART3-6, SPI3-6 */
#define CANCLK_HZ       40000000u   /* REFCLK4 */
#define CORETIMER_HZ    (SYSCLK_HZ / 2u)

#define FW_VERSION      "0.4"

/* LED and W6100 control lines */
#define LED_HB_TOGGLE() (LATDINV = 1u << 8)
#define ETH_CS_LOW()    (LATDCLR = 1u << 5)
#define ETH_CS_HIGH()   (LATDSET = 1u << 5)
#define ETH_RST_LOW()   (LATFCLR = 1u << 0)
#define ETH_RST_HIGH()  (LATFSET = 1u << 0)

void board_init(void);
void pps_unlock(void);
void pps_lock(void);
void board_reset(void);                 /* software reset, does not return */

/* core-timer time base (wraps every 71 s; compare differences only) */
uint32_t ticks(void);
uint32_t millis(void);                  /* ms since reset; call at least every 71 s */
uint32_t ms_since(uint32_t t0);
void delay_us(uint32_t us);
void delay_ms(uint32_t ms);

#endif
