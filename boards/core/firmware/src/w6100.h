/* WIZnet W6100 on SPI3 (15 MHz, mode 0), VDM frames: 16-bit address,
 * control byte BSB<7:3> RWB<2> OM<1:0> = 00 (W6100 datasheet 5.1.1).
 * Bring-up only so far: reset, chip ID, PHY status. */
#ifndef W6100_H
#define W6100_H

#include <stdint.h>
#include <stdbool.h>

#define W6100_CIDR      0x0000u     /* 0x61 */
#define W6100_VER       0x0002u     /* 0x4661 */
#define W6100_PHYSR     0x3000u     /* CAB<7> MODE<5:3> DPX<2> SPD<1> LNK<0> */

bool w6100_init(void);              /* reset; true if the chip ID reads back */
void w6100_read(uint16_t addr, uint8_t bsb, uint8_t *buf, uint16_t n);
void w6100_write(uint16_t addr, uint8_t bsb, const uint8_t *buf, uint16_t n);
uint8_t w6100_read8(uint16_t addr);
uint16_t w6100_version(void);

#endif
