/* TCP command sessions on port 5000 (sockets SOCK_CMD0, SOCK_CMD1). */
#ifndef SERVER_H
#define SERVER_H

#include <stdint.h>

void server_poll(void);
uint8_t server_clients(void);           /* connected command clients */

#endif
