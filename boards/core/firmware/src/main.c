/* ThlHats core firmware: PIC32MK1024MCM064 on the core board.
 *
 * Host protocol over Ethernet (PROTOCOL.md): ASCII commands on TCP 5000,
 * serial-card ports on TCP 5001-5004, SSR measurements streamed over UDP,
 * io-card relays / GPIO / analog inputs.
 * Everything is polled from this loop except the UART rings. */
#include <xc.h>
#include <sys/attribs.h>
#include "board.h"
#include "uart.h"
#include "settings.h"
#include "canfd.h"
#include "net.h"
#include "ssr.h"
#include "serial.h"
#include "io.h"
#include "server.h"
#include "cmd.h"
#include "console.h"

#define CARD_SETTLE_MS  50u     /* ISOW1044 isolated supply start-up before detection */

int main(void)
{
    board_init();

    PRISS = 0x76543210u;                /* shadow register set n for priority n (ISRs use IPLnSRS) */
    INTCONSET = _INTCON_MVEC_MASK;
    __builtin_enable_interrupts();
    uart_init();
    settings_load();

    delay_ms(CARD_SETTLE_MS);
    can_init();
    net_init();
    ser_init();
    io_init();
    console_init();

    uint32_t hb = millis();
    for (;;) {
        net_poll();

        can_frame f;
        for (uint8_t ch = 1; ch <= CAN_CHANNELS; ch++)
            while (can_receive(ch, &f)) {
                if (ch == SSR_CAN)
                    ssr_frame(&f);
                if (console_monitor() && uart_tx_free() > 300u)
                    console_print_frame(ch, &f);
            }

        ssr_poll();
        io_poll();
        server_poll();
        ser_poll();
        console_poll();

        if (millis() - hb >= 500u) {
            hb += 500u;
            LED_HB_TOGGLE();
        }
    }
}
