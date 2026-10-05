#ifndef DISPLAY_H
#define DISPLAY_H

#include <stdint.h>

#define IND_V   0x40u           /* digit 4 segment A: D40 */
#define IND_A   0x20u           /* digit 4 segment B: D41 */

/* letters for the boot screen (no-decode segment patterns) */
#define SEGCH_H 0x37u
#define SEGCH_C 0x4Eu
#define SEGCH_S 0x5Bu
#define SEGCH_t 0x0Fu
#define SEGCH_U 0x3Eu           /* "V" */
#define SEGCH_dash 0x01u

void display_init(void);
void display_raw(const uint8_t seg[4], uint8_t indicators);
void display_value(uint16_t hundredths, uint8_t indicators);
void display_fault(uint8_t code);
void display_boot(uint8_t c0, uint8_t c1, uint8_t node);

#endif
