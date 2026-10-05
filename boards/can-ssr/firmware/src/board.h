/* can-ssr rev A: PIC18F47Q84-I/PT (TQFP-44) pin map, from the PCB netlist.
 *
 *  pin  port  net          use
 *   1   RC7   UART_RX      UART1 RX (J4, debug)
 *   2-5 RD4-7 ADDR0-3      rotary switch, closes to GND (internal pull-ups)
 *  10   RB2   CAN_TX       PPS CANTX
 *  11   RB3   CAN_RX       PPS CANRX
 *  14   RB4   CAN_STBY     MCP2562FD STBY (R4 pull-down: low = normal)
 *  19   RA0   ACS_ADC      ANA0, ACS770 output (0.5 V + 40 mV/A, R24/C22)
 *  20   RA1   BUILD_REF    ANA1, trip threshold VTH through 1k = build ID
 *  21   RA2   V12_MON      ANA2, +12V x 10k / 57k
 *  25   RE0   MW_REMOTE    TLP222A photorelay: high = Mean Well remote ON
 *  26   RE1   LED_STATUS   D4 green
 *  27   RE2   LED_FAULT    D5 red
 *  30/31 RA7/RA6 OSC1/2    16 MHz crystal (x4 PLL = 64 MHz)
 *  32   RC0   GATE_EN      high = VOM1271 LEDs on (R28 pull-down)
 *  35   RC1   TRIP_OK      high = no trip (LM393 open collector, R25 pull-up)
 *  36   RC2   TRIP_RST     high pulse resets the trip latch (R26 pull-down)
 *  37   RC3   I2C_SCL      I2C1 to ISO1640 (MCP3426 x2, MCP4725 x2)
 *  42   RC4   I2C_SDA
 *  38   RD0   DISP_SCK     MAX7219 CLK (bit-banged)
 *  39   RD1   DISP_DIN     MAX7219 DIN
 *  40   RD2   DISP_LOAD    MAX7219 LOAD
 *  44   RC6   UART_TX      UART1 TX (J4, debug)
 */
#ifndef BOARD_H
#define BOARD_H

#include <xc.h>
#include <stdint.h>

#define PIN_GATE_EN     LATCbits.LATC0
#define PIN_TRIP_OK     PORTCbits.RC1
#define PIN_TRIP_RST    LATCbits.LATC2
#define PIN_MW_REMOTE   LATEbits.LATE0
#define PIN_LED_STATUS  LATEbits.LATE1
#define PIN_LED_FAULT   LATEbits.LATE2
#define PIN_CAN_STBY    LATBbits.LATB4
#define PIN_DISP_SCK    LATDbits.LATD0
#define PIN_DISP_DIN    LATDbits.LATD1
#define PIN_DISP_LOAD   LATDbits.LATD2

/* ADCC positive channel numbers (ADPCH) */
#define ADC_CH_ACS      0x00    /* ANA0 */
#define ADC_CH_BUILD    0x01    /* ANA1 */
#define ADC_CH_V12      0x02    /* ANA2 */

/* PPS input codes: (port << 3) | bit, PORTA = 0 */
#define PPS_IN_RB3      0x0B
#define PPS_IN_RC3      0x13
#define PPS_IN_RC4      0x14
/* PPS output codes (device file PIC18F47Q84.PIC) */
#define PPS_OUT_CANTX   0x46
#define PPS_OUT_SCL1    0x37
#define PPS_OUT_SDA1    0x38

/* I2C addresses (7 bit), load side behind the ISO1640 */
#define I2C_ADC_VIN     0x68    /* MCP3426A0: CH1 VIN_DIV, CH2 PV_FB */
#define I2C_ADC_VOUT    0x69    /* MCP3426A1: CH1 VOUT_DIV, CH2 PC_FB */
#define I2C_DAC_PV      0x60    /* MCP4725A0, A0 = GND: Mean Well PV */
#define I2C_DAC_PC      0x61    /* MCP4725A0, A0 = V5_ISO: Mean Well PC */

void board_init(void);
uint8_t board_read_address(void);

#endif
