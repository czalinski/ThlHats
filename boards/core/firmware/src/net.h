/* W6100 sockets: IPv4 TCP servers and a UDP sender, polled.
 *
 * Socket map (8 sockets, 2 KB TX + 2 KB RX each):
 *   0, 6   command server, TCP 5000 (two clients)
 *   1-4    serial-card ports, TCP 5001-5004
 *   5      SSR stream, UDP from 5100
 *   7      spare (DHCP / discovery later) */
#ifndef NET_H
#define NET_H

#include <stdint.h>
#include <stdbool.h>

#define SOCK_CMD0       0u
#define SOCK_CMD1       6u
#define SOCK_SER(n)     (n)             /* n = 1..4 */
#define SOCK_STREAM     5u

#define PORT_CMD        5000u
#define PORT_SER(n)     (5000u + (n))
#define PORT_STREAM     5100u

bool net_init(void);                    /* W6100 reset, addresses from settings, sockets open */
bool net_ok(void);                      /* W6100 answered at init */
void net_poll(void);                    /* keeps the servers listening */
uint8_t net_physr(void);
void net_mac(uint8_t mac[6]);
void net_active_ip(uint8_t ip[4]);

bool tcp_connected(uint8_t s);
bool tcp_new_connection(uint8_t s);     /* true once per accepted connection */
void tcp_hold(uint8_t s, bool hold);    /* keep a closing (CLOSE_WAIT) connection until output is sent */
void tcp_peer(uint8_t s, uint8_t ip[4]);
uint16_t tcp_rx_avail(uint8_t s);
uint16_t tcp_recv(uint8_t s, uint8_t *buf, uint16_t max);
uint16_t tcp_tx_room(uint8_t s);        /* 0 while the previous SEND is in progress */
bool tcp_send(uint8_t s, const uint8_t *buf, uint16_t len);   /* len <= tcp_tx_room() */

bool udp_sendto(uint8_t s, const uint8_t ip[4], uint16_t port, const uint8_t *buf, uint16_t len);
                                        /* false: previous datagram still going out (dropped) */

#endif
