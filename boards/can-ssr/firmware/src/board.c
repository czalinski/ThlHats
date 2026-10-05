#include <xc.h>
#include <stdint.h>
#include "board.h"

/* 16 MHz crystal, x4 PLL = 64 MHz. WDT ~256 ms, cleared by the main loop. */
#pragma config FEXTOSC = HS, RSTOSC = EXTOSC_4PLL
#pragma config CLKOUTEN = OFF, PR1WAY = ON, CSWEN = ON, FCMEN = ON
#pragma config MCLRE = EXTMCLR, PWRTS = PWRT_64, MVECEN = ON, IVT1WAY = ON
#pragma config LPBOREN = OFF, BOREN = SBORDIS, BORV = VBOR_2P85
#pragma config ZCD = OFF, PPS1WAY = ON, STVREN = ON, LVP = ON, XINST = OFF
#pragma config WDTCPS = WDTCPS_8, WDTE = ON, WDTCWS = WDTCWS_7, WDTCCS = LFINTOSC
#pragma config BBEN = OFF, SAFEN = OFF, DEBUG = OFF
#pragma config WRTB = OFF, WRTC = OFF, WRTD = OFF, WRTSAF = OFF, WRTAPP = OFF
#pragma config CP = OFF

void board_init(void)
{
    /* safe output state first: switch off, supply remote off, LEDs off */
    LATA = 0; LATB = 0; LATC = 0; LATD = 0; LATE = 0;
    PIN_DISP_LOAD = 1;

    ANSELA = 0x07;          /* RA0-RA2 analog */
    ANSELB = 0;
    ANSELC = 0;
    ANSELD = 0;
    ANSELE = 0;

    TRISA = 0xFF;                       /* RA0-2 analog in, RA6/7 crystal, rest unused inputs */
    TRISB = (uint8_t)~0x14u;            /* RB2 CANTX, RB4 CAN_STBY outputs */
    TRISC = (uint8_t)~0x45u;            /* RC0 GATE_EN, RC2 TRIP_RST, RC6 UART TX out; RC3/RC4 I2C */
    TRISD = (uint8_t)~0x07u;            /* RD0-RD2 display out; RD4-RD7 address in */
    TRISE = (uint8_t)~0x07u;            /* RE0-RE2 out */

    WPUD = 0xF0;                        /* pull-ups on the address switch */
    WPUA = 0x38;                        /* unused RA3-RA5 */
    WPUB = 0x23;                        /* unused RB0, RB1, RB5 */
    WPUC = 0x20;                        /* unused RC5 */
    ODCONC = 0x18;                      /* I2C pins open drain */
    RC3I2C = 0x01;                      /* I2C pad levels/slew (see datasheet) */
    RC4I2C = 0x01;

    /* PPS */
    PPSLOCK = 0x55; PPSLOCK = 0xAA; PPSLOCKbits.PPSLOCKED = 0;
    RB2PPS = PPS_OUT_CANTX;
    CANRXPPS = PPS_IN_RB3;
    RC3PPS = PPS_OUT_SCL1;
    RC4PPS = PPS_OUT_SDA1;
    I2C1SCLPPS = PPS_IN_RC3;
    I2C1SDAPPS = PPS_IN_RC4;
    PPSLOCK = 0x55; PPSLOCK = 0xAA; PPSLOCKbits.PPSLOCKED = 1;
}

/* Rotary switch: common to GND, so a closed contact reads 0. */
uint8_t board_read_address(void)
{
    uint8_t a = 0, b;
    for (uint8_t i = 0; i < 3; i++) {   /* read until two samples agree */
        b = (uint8_t)((~PORTD >> 4) & 0x0Fu);
        if (b == a) break;
        a = b;
        for (volatile uint16_t d = 0; d < 2000u; d++) { }
    }
    return a;
}
