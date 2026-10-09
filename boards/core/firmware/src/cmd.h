/* ASCII command interpreter (PROTOCOL.md), shared by the TCP command
 * sessions and the debug UART. Commands that wait for a CAN device leave the
 * session busy; cmd_poll() finishes them. */
#ifndef CMD_H
#define CMD_H

#include <stdint.h>
#include <stdbool.h>

typedef struct session session;
struct session {
    void (*write)(session *s, const char *text);   /* text uses "\n" line ends */
    bool is_uart;
    uint8_t peer[4];                    /* client address (TCP) */
    /* pending command */
    uint8_t pend;
    uint32_t pend_t0;
    uint8_t pend_node, pend_seq, pend_flags;
    uint16_t pend_v, pend_i, pend_timeout;
};

void cmd_execute(session *s, char *line);
void cmd_poll(session *s);
bool cmd_busy(const session *s);
bool str_ieq(const char *a, const char *b);                 /* case-insensitive compare */
bool str_ieq_n(const char *a, const char *b, uint32_t n);

#endif
