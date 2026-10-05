/* Fault bits. A fault latches; outputs stay off until the host sends CLEAR
 * and the cause is gone. Warnings are reported but do not switch off. */
#ifndef FAULTS_H
#define FAULTS_H

#include <stdint.h>

#define FLT_HW_TRIP         0x0001u /* hardware overcurrent latch (TRIP_OK low) */
#define FLT_SW_OC           0x0002u /* average current above the SET limit */
#define FLT_HOST_TIMEOUT    0x0004u /* no host frame within HOST_TIMEOUT_MS */
#define FLT_BUILD           0x0008u /* build resistor reading out of band */
#define FLT_ISO_COMM        0x0010u /* load-side I2C (ADC/DAC) not answering */
#define FLT_SWITCH_OPEN     0x0020u /* on, but Vout far below Vin */
#define FLT_SUPPLY_NO_RISE  0x0040u /* sequenced turn-on: Vin did not come up */
#define FLT_ADDR_CONFLICT   0x0080u /* another node uses our address */
#define FLT_OVERVOLTAGE     0x0100u /* Vin above this build's maximum */

#define WRN_V12_LOW         0x01u   /* CAN cable supply below 10 V */
#define WRN_REG_LIMIT       0x02u   /* PV loop at a DAC limit */
#define WRN_CAN_ERR         0x04u   /* CAN error passive or recovered from bus-off */
#define WRN_VOUT_LIVE       0x08u   /* off for 1 s with a live input, yet Vout follows Vin:
                                       shorted switch, or a charged DUT with no load */

extern volatile uint16_t g_faults;      /* latched faults */
extern uint8_t g_warnings;
extern uint8_t g_first_fault;           /* bit number of the first fault since CLEAR */

void fault_raise(uint16_t f);
uint8_t fault_clear(void);              /* returns 1 if all cleared */

#endif
