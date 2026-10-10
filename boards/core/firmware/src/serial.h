/* Serial-card ports 1-4 bridged to TCP 5001-5004.
 *   1 U2 RS-232 (TX RC10, RX RB8)     2 U3 RS-232 (TX RE14, RX RB4)
 *   3 U4 RS-485 (TX RB1, RX RB14, DE1 RA10)
 *   4 U5 RS-485 (TX RB10, RX RC13, DE2 RA7)
 * Matches boards/serial-card (ST3232B for 1-2; ISOW1432 half duplex for 3-4,
 * ~RE tied to DE so the receiver is off while DE is high). */
#ifndef SERIAL_H
#define SERIAL_H

#include <stdint.h>
#include <stdbool.h>
#include "settings.h"

void ser_init(void);                    /* applies settings.ser[] */
void ser_poll(void);                    /* moves bytes between sockets and UARTs */
bool ser_valid(const ser_settings *s);
void ser_apply(uint8_t port, const ser_settings *s);    /* port 1-4, s must be valid */
const ser_settings *ser_get(uint8_t port);
uint32_t ser_actual_baud(uint8_t port);
bool ser_rs485(uint8_t port);
void ser_counters(uint8_t port, uint32_t *rx, uint32_t *tx);

#endif
