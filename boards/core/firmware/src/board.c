/* Core board bring-up: configuration words, clock switch, ports, PPS for
 * UART1 and SPI3. CAN pins are set up by canfd.c after card detection. */
#include <xc.h>
#include "board.h"

/* DEVCFG3: USB unused (VBUSON/USBID pins are GPIO); PPS/PMD may be changed
 * more than once (canfd.c maps the CAN pins after card detection). */
#pragma config USERID = 0xffff
#pragma config FUSBIDIO2 = OFF, FVBUSIO2 = OFF, FUSBIDIO1 = OFF, FVBUSIO1 = OFF
#pragma config PGL1WAY = OFF, PMDL1WAY = OFF, IOL1WAY = OFF

/* DEVCFG2: SPLL = POSC 12 MHz / 1 x 40 / 4 = 120 MHz (also written to SPLLCON in clock_init) */
#pragma config FPLLIDIV = DIV_1, FPLLRNG = RANGE_8_16_MHZ, FPLLICLK = PLL_POSC
#pragma config FPLLMULT = MUL_40, FPLLODIV = DIV_4
#pragma config BORSEL = HIGH, UPLLEN = OFF

/* DEVCFG1: start on FRC and switch to SPLL in software (errata DS80000898D
 * 2.1.1: FNOSC selection in hardware may not work). SOSC off: its pins carry
 * U2RX (RB8) and U5RX (RC13). */
#pragma config FNOSC = FRC, IESO = OFF, FCKSM = CSECMD
#pragma config POSCMOD = HS, OSCIOFNC = OFF, FSOSCEN = OFF
#pragma config FWDTEN = OFF, WDTPS = PS1048576, WDTSPGM = STOP, WINDIS = NORMAL, FWDTWINSZ = WINSZ_25
#pragma config FDMTEN = OFF, DMTINTV = WIN_127_128, DMTCNT = DMT31

/* DEVCFG0: JTAG off (RA7, RA8, RA10, RB9 are used), debug on PGEC2/PGED2 */
#pragma config DEBUG = OFF, JTAGEN = OFF, ICESEL = ICS_PGx2, TRCEN = OFF
#pragma config BOOTISA = MIPS32, FECCCON = ECC_DECC_DISABLE_ECCON_WRITABLE
#pragma config FSLEEP = OFF, DBGPER = PG_ALL, SMCLR = MCLR_NORM
#pragma config SOSCGAIN = G3, SOSCBOOST = ON
#pragma config POSCGAIN = G3, POSCBOOST = ON, POSCFGAIN = G3
#pragma config POSCAGCDLY = AGCRNG_x_25ms, POSCAGCRNG = ONE_X, POSCAGC = Automatic
#pragma config EJTAGBEN = NORMAL, CP = OFF

/* stack-bus pins of the cards that have no firmware yet (serial-card,
 * io-card): inputs with pull-downs until their drivers exist */
#define IDLE_A  ((1u << 0) | (1u << 7) | (1u << 10) | (1u << 11) | (1u << 12))
#define IDLE_B  ((1u << 1) | (1u << 4) | (1u << 8) | (1u << 10) | (1u << 11) | (1u << 12) | (1u << 14) | (1u << 15))
#define IDLE_C  ((1u << 10) | (1u << 13))
#define IDLE_E  (1u << 14)
#define IDLE_G  ((1u << 6) | (1u << 9))

static void sys_unlock(void)
{
    SYSKEY = 0;
    SYSKEY = 0xAA996655u;
    SYSKEY = 0x556699AAu;
}

static void sys_lock(void)
{
    SYSKEY = 0x33333333u;
}

void pps_unlock(void)
{
    sys_unlock();
    CFGCONbits.IOLOCK = 0;
    sys_lock();
}

void pps_lock(void)
{
    sys_unlock();
    CFGCONbits.IOLOCK = 1;
    sys_lock();
}

static void clock_init(void)
{
    /* flash: 2 wait states + address wait state above 110 MHz, prefetch for
     * CPU instructions (DS60001519D Register 10-1) */
    CHECON = (CHECON & ~(_CHECON_PFMWS_MASK | _CHECON_PREFEN_MASK))
           | (2u << _CHECON_PFMWS_POSITION) | (1u << _CHECON_PREFEN_POSITION) | _CHECON_PFMAWSEN_MASK;

    sys_unlock();
    SPLLCON = (2u << _SPLLCON_PLLRANGE_POSITION)     /* 8-16 MHz input */
            | (0u << _SPLLCON_PLLICLK_POSITION)      /* POSC */
            | (0u << _SPLLCON_PLLIDIV_POSITION)      /* /1 */
            | (39u << _SPLLCON_PLLMULT_POSITION)     /* x40: VCO 480 MHz */
            | (2u << _SPLLCON_PLLODIV_POSITION);     /* /4 */
    OSCCONbits.NOSC = 1;                             /* SPLL */
    OSCCONSET = _OSCCON_OSWEN_MASK;
    sys_lock();
    while (OSCCONbits.OSWEN) { }

    /* REFCLK4 = SYSCLK / 3 = 40 MHz for CAN FD: RODIV 1 + ROTRIM 256/512
     * (the datasheet's recipe, Register 26-1 note) */
    REFO4CON = 0;
    REFO4TRIM = 256u << 23;
    REFO4CON = (1u << _REFO4CON_RODIV_POSITION) | (0u << _REFO4CON_ROSEL_POSITION);
    REFO4CONSET = _REFO4CON_ON_MASK;
}

static void ports_init(void)
{
    /* digital where used as digital; AI/VMID/OSC pins stay analog */
    ANSELACLR = (1u << 0) | (1u << 1) | (1u << 8) | (1u << 11) | (1u << 12);
    ANSELBCLR = (1u << 0) | (1u << 1) | (1u << 2) | (1u << 3);
    ANSELCCLR = (1u << 0) | (1u << 1) | (1u << 10);
    ANSELECLR = (1u << 14) | (1u << 15);
    ANSELGCLR = (1u << 6) | (1u << 7) | (1u << 8) | (1u << 9);

    CNPDASET = IDLE_A;
    CNPDBSET = IDLE_B;
    CNPDCSET = IDLE_C;
    CNPDESET = IDLE_E;
    CNPDGSET = IDLE_G;

    LATBCLR = 1u << 13;                 /* RB13 unused: drive low */
    TRISBCLR = 1u << 13;

    LATDCLR = 1u << 8;                  /* heartbeat LED */
    TRISDCLR = 1u << 8;

    LATDSET = 1u << 5;                  /* W6100: CS high, held in reset */
    TRISDCLR = 1u << 5;
    LATFCLR = 1u << 0;
    TRISFCLR = 1u << 0;

    LATFSET = 1u << 1;                  /* U1TX idles high */
    TRISFCLR = 1u << 1;
    TRISCCLR = (1u << 8) | (1u << 9);   /* SDO3, SCK3 */

    pps_unlock();
    RPF1R = 1;                          /* U1TX -> RF1 */
    U1RXR = 5;                          /* U1RX <- RC6 */
    RPC8R = 14;                         /* SDO3 -> RC8 */
    RPC9R = 14;                         /* SCK3 -> RC9 */
    SDI3R = 5;                          /* SDI3 <- RC7 */
    pps_lock();
}

void board_init(void)
{
    CFGCONbits.JTAGEN = 0;
    clock_init();
    ports_init();
}

uint32_t ticks(void)
{
    return _CP0_GET_COUNT();
}

uint32_t ms_since(uint32_t t0)
{
    return (ticks() - t0) / (CORETIMER_HZ / 1000u);
}

void delay_us(uint32_t us)
{
    uint32_t t0 = ticks();
    uint32_t n = us * (CORETIMER_HZ / 1000000u);
    while (ticks() - t0 < n) { }
}

void delay_ms(uint32_t ms)
{
    while (ms--)
        delay_us(1000);
}
