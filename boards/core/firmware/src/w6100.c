#include <xc.h>
#include "board.h"
#include "w6100.h"

static uint8_t spi_xfer(uint8_t b)
{
    SPI3BUF = b;
    while (SPI3STATbits.SPIRBE) { }
    return (uint8_t)SPI3BUF;
}

static void frame(uint16_t addr, uint8_t bsb, bool write)
{
    spi_xfer((uint8_t)(addr >> 8));
    spi_xfer((uint8_t)addr);
    spi_xfer((uint8_t)((bsb << 3) | (write ? 1u << 2 : 0)));
}

void w6100_read(uint16_t addr, uint8_t bsb, uint8_t *buf, uint16_t n)
{
    ETH_CS_LOW();
    frame(addr, bsb, false);
    while (n--)
        *buf++ = spi_xfer(0);
    ETH_CS_HIGH();
}

void w6100_write(uint16_t addr, uint8_t bsb, const uint8_t *buf, uint16_t n)
{
    ETH_CS_LOW();
    frame(addr, bsb, true);
    while (n--)
        spi_xfer(*buf++);
    ETH_CS_HIGH();
}

uint8_t w6100_read8(uint16_t addr)
{
    uint8_t v;
    w6100_read(addr, 0, &v, 1);
    return v;
}

uint16_t w6100_version(void)
{
    uint8_t v[2];
    w6100_read(W6100_VER, 0, v, 2);
    return (uint16_t)((v[0] << 8) | v[1]);
}

bool w6100_init(void)
{
    SPI3CON = 0;
    (void)SPI3BUF;
    SPI3BRG = (PBCLK3_HZ / (2u * 15000000u)) - 1u;     /* 15 MHz */
    SPI3STATCLR = _SPI3STAT_SPIROV_MASK;
    SPI3CON = _SPI3CON_MSTEN_MASK | _SPI3CON_CKE_MASK | _SPI3CON_ENHBUF_MASK;  /* mode 0, 8 bit */
    SPI3CONSET = _SPI3CON_ON_MASK;

    ETH_RST_LOW();                  /* RSTn low >= 1 us (held since board_init) */
    delay_us(10);
    ETH_RST_HIGH();
    delay_ms(70);                   /* 60 ms PLL/crystal start (datasheet 7.1) */

    return w6100_read8(W6100_CIDR) == 0x61u;
}
