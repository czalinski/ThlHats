/* Each session reads one command line at a time and takes the next one only
 * after the previous response has been handed to the W6100 completely, so a
 * response never has to be dropped or interleaved. */
#include <string.h>
#include "board.h"
#include "net.h"
#include "cmd.h"
#include "server.h"

#define OUT_SIZE    8192u               /* longest response: STATUS, about 5 KB */
#define LINE_SIZE   256u

typedef struct {
    session s;                          /* first: the write callback casts back */
    uint8_t sock;
    uint8_t in[256];                    /* bytes read from the socket, not yet parsed */
    uint16_t in_pos, in_len;
    char line[LINE_SIZE];
    uint32_t line_len;
    bool overlong;
    char out[OUT_SIZE];
    uint32_t out_len;
    bool overflow;
} tcp_session;

static void tcp_write(session *s, const char *text);

static tcp_session sessions[2];        /* set up on the first poll: keeps 16 KB out of .data */

static void tcp_write(session *s, const char *text)
{
    tcp_session *t = (tcp_session *)s;
    for (; *text; text++) {
        if (*text == '\n') {
            if (t->out_len + 2u > OUT_SIZE) {
                t->overflow = true;
                return;
            }
            t->out[t->out_len++] = '\r';
        } else if (t->out_len + 1u > OUT_SIZE) {
            t->overflow = true;
            return;
        }
        t->out[t->out_len++] = *text;
    }
}

static void flush(tcp_session *t)
{
    if (!t->out_len)
        return;
    uint16_t room = tcp_tx_room(t->sock);
    uint32_t n = t->out_len < room ? t->out_len : room;
    if (n && tcp_send(t->sock, (const uint8_t *)t->out, (uint16_t)n)) {
        memmove(t->out, t->out + n, t->out_len - n);
        t->out_len -= n;
    }
}

static void session_poll(tcp_session *t)
{
    if (tcp_new_connection(t->sock)) {
        t->line_len = 0;
        t->out_len = 0;
        t->in_pos = t->in_len = 0;
        t->overlong = false;
        t->s.pend = 0;
        tcp_peer(t->sock, t->s.peer);
    }
    if (!tcp_connected(t->sock)) {
        t->s.pend = 0;
        t->out_len = 0;
        t->in_pos = t->in_len = 0;
        tcp_hold(t->sock, false);
        return;
    }

    cmd_poll(&t->s);
    flush(t);

    /* next command only when the previous response is out */
    while (!cmd_busy(&t->s) && !t->out_len) {
        if (t->in_pos == t->in_len) {
            t->in_pos = 0;
            t->in_len = tcp_recv(t->sock, t->in, sizeof t->in);
            if (!t->in_len)
                break;
        }
        uint8_t c = t->in[t->in_pos++];
        if (c == '\r')
            continue;
        if (c == '\n') {
            if (t->overlong) {
                t->s.write(&t->s, "ERR 400 line too long\n");
            } else {
                t->line[t->line_len] = 0;
                t->overflow = false;
                cmd_execute(&t->s, t->line);
            }
            t->line_len = 0;
            t->overlong = false;
            flush(t);
        } else if (t->line_len < LINE_SIZE - 1u) {
            t->line[t->line_len++] = (char)c;
        } else {
            t->overlong = true;
        }
    }
    tcp_hold(t->sock, t->out_len || cmd_busy(&t->s) || t->in_pos < t->in_len);
}

static void setup(void)
{
    if (!sessions[0].s.write) {
        sessions[0].s.write = sessions[1].s.write = tcp_write;
        sessions[0].sock = SOCK_CMD0;
        sessions[1].sock = SOCK_CMD1;
    }
}

void server_poll(void)
{
    setup();
    for (unsigned k = 0; k < sizeof sessions / sizeof sessions[0]; k++)
        session_poll(&sessions[k]);
}

uint8_t server_clients(void)
{
    uint8_t n = 0;
    setup();
    for (unsigned k = 0; k < sizeof sessions / sizeof sessions[0]; k++)
        if (tcp_connected(sessions[k].sock))
            n++;
    return n;
}
