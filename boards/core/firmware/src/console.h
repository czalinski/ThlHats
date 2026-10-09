/* Debug console on UART1: the host command set (PROTOCOL.md) plus MON,
 * which prints received CAN frames candump-style. */
#ifndef CONSOLE_H
#define CONSOLE_H

#include <stdbool.h>
#include "canfd.h"

void console_init(void);
void console_poll(void);
bool console_monitor(void);
void console_print_frame(uint8_t ch, const can_frame *f);

#endif
