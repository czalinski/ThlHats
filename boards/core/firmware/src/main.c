/* ThlHats core firmware: PIC32MK1024MCM064 on the core board.
 *
 * So far: clocks, debug console (UART1, J5), W6100 bring-up check, can-card
 * detection and the four CAN FD channels. Next: the host protocol over
 * Ethernet (W6100 sockets). */
#include <xc.h>
#include <sys/attribs.h>
#include "board.h"
#include "uart.h"
#include "canfd.h"
#include "console.h"

#define CARD_SETTLE_MS  50u     /* ISOW1044 isolated supply start-up before detection */

int main(void)
{
    board_init();

    PRISS = 0x76543210u;                /* shadow register set n for priority n (ISRs use IPLnSRS) */
    INTCONSET = _INTCON_MVEC_MASK;
    __builtin_enable_interrupts();
    uart_init();

    delay_ms(CARD_SETTLE_MS);
    can_init();
    console_init();

    uint32_t hb = ticks();
    for (;;) {
        can_frame f;
        for (uint8_t ch = 1; ch <= CAN_CHANNELS; ch++)
            while (can_receive(ch, &f))
                if (console_monitor() && uart_tx_free() > 300u)
                    console_print_frame(ch, &f);
        console_poll();
        if (ms_since(hb) >= 500u) {
            hb = ticks();
            LED_HB_TOGGLE();
        }
    }
}
