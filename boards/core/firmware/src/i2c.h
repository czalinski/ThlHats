/* I2C1 master on the stack bus: SCL1 RG7, SDA1 RG8, 4.7k pull-ups on the
 * core (R7/R8). 100 kHz, polled, every step with a timeout. Used by the
 * io-card's analog outputs (MCP4728 behind an ISO1540).
 * Errata DS80000898D: 2.4.1 (host tLOW out of spec at >= 400 kHz) is why
 * the bus stays at 100 kHz; 2.4.2 (client address match) does not apply. */
#ifndef I2C_H
#define I2C_H

#include <stdint.h>
#include <stdbool.h>

void i2c_init(void);
/* false: no ACK (address or data), bus collision or timeout */
bool i2c_write(uint8_t addr, const uint8_t *data, uint32_t n);
bool i2c_probe(uint8_t addr);           /* address only */

#endif
