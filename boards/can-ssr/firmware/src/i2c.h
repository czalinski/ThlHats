#ifndef I2C_H
#define I2C_H

#include <stdint.h>

void i2c_init(void);
uint8_t i2c_write(uint8_t addr, const uint8_t *data, uint8_t len);   /* 1 = ok */
uint8_t i2c_read(uint8_t addr, uint8_t *data, uint8_t len);          /* 1 = ok */

#endif
