/* Debug console on UART1 (J5: 1 TX, 2 RX, 3 GND; 3.3 V), 115200 8N1.
 * Interrupt driven, ring buffers both ways. */
#ifndef UART_H
#define UART_H

#include <stdint.h>
#include <stdbool.h>

void uart_init(void);
int uart_getc(void);                    /* -1 if nothing received */
void uart_putc(char c);                 /* blocks while the TX ring is full */
void uart_puts(const char *s);          /* "\n" -> "\r\n" */
void uart_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
uint32_t uart_tx_free(void);

#endif
