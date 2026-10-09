/* Bring-up console on UART1. Command reference in ../README.md. */
#ifndef CONSOLE_H
#define CONSOLE_H

#include <stdbool.h>
#include "canfd.h"

void console_init(void);
void console_poll(void);                    /* read and execute command lines */
bool console_monitor(void);                 /* print received frames? */
void console_print_frame(uint8_t ch, const can_frame *f);

#endif
