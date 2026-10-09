#include <string.h>
#include <ctype.h>
#include "board.h"
#include "uart.h"
#include "canfd.h"
#include "cmd.h"
#include "console.h"

#define LINE_MAX    160u

static char line[LINE_MAX];
static uint32_t line_len;
static bool monitor;
static bool prompt_due;
static int last_c;

static void uart_write(session *s, const char *text)
{
    (void)s;
    uart_puts(text);
}

static session con = { .write = uart_write, .is_uart = true };

bool console_monitor(void)
{
    return monitor;
}

void console_print_frame(uint8_t ch, const can_frame *f)
{
    static const char hex[] = "0123456789ABCDEF";
    char buf[16 + 64 * 3 + 24];
    char *p = buf;

    /* candump style: can1  123   [4]  DE AD BE EF */
    uart_printf((f->flags & CAN_EXT) ? "can%u  %08lX  " : "can%u  %03lX  ", ch, (unsigned long)f->id);
    if (f->flags & CAN_FDF)
        uart_printf("[%02u] ", f->len);
    else
        uart_printf(" [%u] ", f->len);
    for (uint8_t k = 0; k < f->len; k++) {
        *p++ = ' ';
        *p++ = hex[f->data[k] >> 4];
        *p++ = hex[f->data[k] & 15u];
    }
    *p = 0;
    uart_puts(buf);
    if (f->flags & CAN_RTR)
        uart_puts("  remote");
    if (f->flags & CAN_FDF)
        uart_printf("  (FD%s%s)", (f->flags & CAN_BRS) ? ",BRS" : "", (f->flags & CAN_ESI) ? ",ESI" : "");
    uart_puts("\n");
}

static bool local_command(char *s)
{
    while (*s == ' ')
        s++;
    if (!str_ieq_n(s, "MON", 3) || (s[3] && s[3] != ' '))
        return false;
    s += 3;
    while (*s == ' ')
        s++;
    if (str_ieq(s, "ON"))
        monitor = true;
    else if (str_ieq(s, "OFF"))
        monitor = false;
    else if (*s) {
        uart_puts("ERR 400 usage: MON [ON|OFF]\n");
        return true;
    }
    uart_printf("OK MON %s\n", monitor ? "on" : "off");
    return true;
}

void console_init(void)
{
    char id[] = "ID", status[] = "STATUS";
    uart_puts("\nThlHats core: debug console (HELP; MON ON prints CAN frames)\n");
    cmd_execute(&con, id);
    cmd_execute(&con, status);
    uart_puts("> ");
}

void console_poll(void)
{
    cmd_poll(&con);
    if (cmd_busy(&con))
        return;
    if (prompt_due) {
        prompt_due = false;
        uart_puts("> ");
    }
    int c;
    while ((c = uart_getc()) >= 0) {
        int prev = last_c;
        last_c = c;
        if (c == '\n' && prev == '\r')
            continue;                   /* CR LF from the terminal: one line end */
        if (c == '\r' || c == '\n') {
            uart_puts("\n");
            line[line_len] = 0;
            line_len = 0;
            if (!local_command(line))
                cmd_execute(&con, line);
            if (cmd_busy(&con)) {
                prompt_due = true;
                return;
            }
            uart_puts("> ");
        } else if (c == 8 || c == 127) {
            if (line_len) {
                line_len--;
                uart_puts("\b \b");
            }
        } else if (c >= ' ' && line_len < LINE_MAX - 1u) {
            line[line_len++] = (char)c;
            uart_putc((char)c);
        }
    }
}
