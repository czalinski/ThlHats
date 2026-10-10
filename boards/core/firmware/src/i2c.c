#include <xc.h>
#include "board.h"
#include "i2c.h"

#define FSCL_HZ     100000u
#define SCL_BIT     (1u << 7)           /* RG7 */
#define SDA_BIT     (1u << 8)           /* RG8 */
#define STEP_US     1000u               /* timeout per bus step */
/* SEN, RSEN, PEN, RCEN, ACKEN: a bus action is still running */
#define CON_BUSY    0x1Fu

static bool wait_until(bool (*done)(void))
{
    uint32_t t0 = ticks();
    while (!done())
        if (ticks() - t0 > CORETIMER_HZ / 1000000u * STEP_US)
            return false;
    return true;
}

static bool idle(void)
{
    return !(I2C1CON & CON_BUSY) && !(I2C1STAT & _I2C1STAT_TRSTAT_MASK);
}

static bool start_done(void) { return !(I2C1CON & _I2C1CON_SEN_MASK); }
static bool stop_done(void) { return !(I2C1CON & _I2C1CON_PEN_MASK); }
static bool sent(void) { return !(I2C1STAT & _I2C1STAT_TRSTAT_MASK); }

static void stop(void)
{
    I2C1STATCLR = _I2C1STAT_BCL_MASK | _I2C1STAT_IWCOL_MASK;
    I2C1CONSET = _I2C1CON_PEN_MASK;
    wait_until(stop_done);
}

static bool put(uint8_t b)
{
    I2C1TRN = b;
    if (!wait_until(sent) || (I2C1STAT & (_I2C1STAT_BCL_MASK | _I2C1STAT_IWCOL_MASK)))
        return false;
    return !(I2C1STAT & _I2C1STAT_ACKSTAT_MASK);
}

bool i2c_write(uint8_t addr, const uint8_t *data, uint32_t n)
{
    if (!wait_until(idle))
        return false;
    I2C1STATCLR = _I2C1STAT_BCL_MASK | _I2C1STAT_IWCOL_MASK;
    I2C1CONSET = _I2C1CON_SEN_MASK;
    if (!wait_until(start_done) || (I2C1STAT & _I2C1STAT_BCL_MASK)) {
        stop();
        return false;
    }
    bool ok = put((uint8_t)(addr << 1));
    for (uint32_t k = 0; ok && k < n; k++)
        ok = put(data[k]);
    stop();
    return ok;
}

bool i2c_probe(uint8_t addr)
{
    return i2c_write(addr, 0, 0);
}

/* A slave reset mid-byte can hold SDA low: clock SCL until it lets go. */
static void bus_recover(void)
{
    ODCGSET = SCL_BIT;
    LATGSET = SCL_BIT;
    TRISGCLR = SCL_BIT;
    for (int k = 0; k < 9 && !(PORTG & SDA_BIT); k++) {
        LATGCLR = SCL_BIT;
        delay_us(5);
        LATGSET = SCL_BIT;
        delay_us(5);
    }
    TRISGSET = SCL_BIT;
    ODCGCLR = SCL_BIT;
}

void i2c_init(void)
{
    PMD5CLR = _PMD5_I2C1MD_MASK;
    ANSELGCLR = SCL_BIT | SDA_BIT;      /* RG7/RG8 are analog (AN18/AN17) at reset */
    TRISGSET = SCL_BIT | SDA_BIT;
    I2C1CON = 0;
    bus_recover();
    /* I2C runs from PBCLK2: BRG = PBCLK / (2 * FSCL) - 2 (about 99 kHz) */
    I2C1BRG = PBCLK2_HZ / (2u * FSCL_HZ) - 2u;
    I2C1CON = _I2C1CON_DISSLW_MASK;     /* slew-rate control is for 400 kHz */
    I2C1CONSET = _I2C1CON_ON_MASK;
}
