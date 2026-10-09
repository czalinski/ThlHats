#include <xc.h>
#include <sys/attribs.h>
#include <stdarg.h>
#include <stdio.h>
#include "board.h"
#include "uart.h"

#define BAUD        115200u
#define RX_SIZE     256u                /* powers of two */
#define TX_SIZE     4096u

static volatile uint8_t rx_buf[RX_SIZE];
static volatile uint32_t rx_head, rx_tail;
static volatile uint8_t tx_buf[TX_SIZE];
static volatile uint32_t tx_head, tx_tail;

void uart_init(void)
{
    U1MODE = 0;
    U1STA = 0;
    U1MODEbits.BRGH = 1;                            /* 4x clock, PBCLK2 */
    U1BRG = (PBCLK2_HZ / (4u * BAUD)) - 1u;         /* 129: 115385 baud, +0.16 % */
    U1STAbits.URXISEL = 0;                          /* RX interrupt: buffer not empty */
    U1STAbits.UTXISEL = 0;                          /* TX interrupt: space in the TX FIFO */
    U1STASET = _U1STA_URXEN_MASK | _U1STA_UTXEN_MASK;

    IPC9bits.U1RXIP = 2;
    IPC10bits.U1TXIP = 2;
    IFS1CLR = _IFS1_U1RXIF_MASK | _IFS1_U1TXIF_MASK;
    IEC1SET = _IEC1_U1RXIE_MASK;
    U1MODESET = _U1MODE_ON_MASK;
}

void __ISR(_UART1_RX_VECTOR, IPL2SRS) uart1_rx_isr(void)
{
    if (U1STAbits.OERR)
        U1STACLR = _U1STA_OERR_MASK;
    while (U1STAbits.URXDA) {
        uint8_t c = (uint8_t)U1RXREG;
        uint32_t next = (rx_head + 1u) & (RX_SIZE - 1u);
        if (next != rx_tail) {
            rx_buf[rx_head] = c;
            rx_head = next;
        }
    }
    IFS1CLR = _IFS1_U1RXIF_MASK;
}

void __ISR(_UART1_TX_VECTOR, IPL2SRS) uart1_tx_isr(void)
{
    while (!U1STAbits.UTXBF && tx_tail != tx_head) {
        U1TXREG = tx_buf[tx_tail];
        tx_tail = (tx_tail + 1u) & (TX_SIZE - 1u);
    }
    if (tx_tail == tx_head)
        IEC1CLR = _IEC1_U1TXIE_MASK;
    IFS1CLR = _IFS1_U1TXIF_MASK;
}

int uart_getc(void)
{
    if (rx_tail == rx_head)
        return -1;
    int c = rx_buf[rx_tail];
    rx_tail = (rx_tail + 1u) & (RX_SIZE - 1u);
    return c;
}

uint32_t uart_tx_free(void)
{
    return (tx_tail - tx_head - 1u) & (TX_SIZE - 1u);
}

void uart_putc(char c)
{
    uint32_t next = (tx_head + 1u) & (TX_SIZE - 1u);
    while (next == tx_tail) { }         /* ring full: the TX interrupt drains it */
    tx_buf[tx_head] = (uint8_t)c;
    tx_head = next;
    IEC1SET = _IEC1_U1TXIE_MASK;
}

void uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n')
            uart_putc('\r');
        uart_putc(*s++);
    }
}

void uart_printf(const char *fmt, ...)
{
    char line[256];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(line, sizeof line, fmt, ap);
    va_end(ap);
    uart_puts(line);
}
