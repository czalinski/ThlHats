/* I2C1 host (PIC18 Q84 I2C module, not MSSP), blocking with a timeout.
 * 100 kHz: the bus runs through the ISO1640 to the load side. */
#include <xc.h>
#include "board.h"
#include "i2c.h"

#define I2C_SPIN_LIMIT  20000u          /* ~5 ms at 64 MHz per wait */

void i2c_init(void)
{
    I2C1CON0 = 0;
    I2C1CON1 = 0;
    I2C1CON2 = 0;
    I2C1CON0bits.MODE = 0b100;          /* host, 7-bit address */
    I2C1CON1bits.ACKCNT = 1;            /* NACK the last byte read (CNT = 0) */
    I2C1CON2bits.ABD = 0;               /* address from I2C1ADB1 */
    I2C1CLK = 0x00;                     /* Fosc/4 = 16 MHz (check CLK table) */
    I2C1BAUD = 31;                      /* 16 MHz / (5 x 32) = 100 kHz */
    I2C1CON0bits.EN = 1;
}

static uint8_t wait_flag(volatile unsigned char *reg, uint8_t mask)
{
    uint16_t n = I2C_SPIN_LIMIT;
    while (!(*reg & mask)) {
        if (I2C1ERRbits.NACKIF || I2C1ERRbits.BCLIF || I2C1ERRbits.BTOIF) return 0;
        if (--n == 0) return 0;
    }
    return 1;
}

static uint8_t finish(uint8_t ok)
{
    uint16_t n = I2C_SPIN_LIMIT;
    if (ok) {
        while (!I2C1PIRbits.PCIF && --n) { }   /* auto stop when CNT reaches 0 */
        ok = n != 0;
    }
    if (!ok || I2C1ERRbits.NACKIF || I2C1ERRbits.BCLIF || I2C1ERRbits.BTOIF) {
        ok = 0;
        I2C1CON0bits.EN = 0;            /* reset the module after an error */
        I2C1ERR = 0;
        I2C1CON0bits.EN = 1;
    }
    I2C1PIR = 0;
    I2C1STAT1bits.CLRBF = 1;
    return ok;
}

uint8_t i2c_write(uint8_t addr, const uint8_t *data, uint8_t len)
{
    I2C1PIR = 0;
    I2C1ERR = 0;
    I2C1STAT1bits.CLRBF = 1;
    I2C1ADB1 = (uint8_t)(addr << 1);
    I2C1CNTL = len;
    I2C1CNTH = 0;
    I2C1TXB = data[0];
    I2C1CON0bits.S = 1;
    for (uint8_t i = 1; i < len; i++) {
        if (!wait_flag(&I2C1STAT1, _I2C1STAT1_TXBE_MASK)) return finish(0);
        I2C1TXB = data[i];
    }
    return finish(1);
}

uint8_t i2c_read(uint8_t addr, uint8_t *data, uint8_t len)
{
    I2C1PIR = 0;
    I2C1ERR = 0;
    I2C1STAT1bits.CLRBF = 1;
    I2C1ADB1 = (uint8_t)((uint8_t)(addr << 1) | 1u);
    I2C1CNTL = len;
    I2C1CNTH = 0;
    I2C1CON0bits.S = 1;
    for (uint8_t i = 0; i < len; i++) {
        if (!wait_flag(&I2C1STAT1, _I2C1STAT1_RXBF_MASK)) return finish(0);
        data[i] = I2C1RXB;
    }
    return finish(1);
}
