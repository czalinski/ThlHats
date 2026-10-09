/* Power-up settings, stored in the last 4 KB page of program flash
 * (0x9D0FF000). Written only by the SAVE command; checked by a CRC, so an
 * erased or corrupt page gives the defaults. */
#ifndef SETTINGS_H
#define SETTINGS_H

#include <stdint.h>
#include <stdbool.h>

#define SER_PORTS   4u

typedef struct {
    uint32_t baud;
    uint8_t data;           /* 7 or 8 */
    char parity;            /* 'N', 'E', 'O' */
    uint8_t stop;           /* 1 or 2 */
    uint8_t reserved;
} ser_settings;

typedef struct {
    uint32_t magic;
    uint32_t version;
    uint8_t ip[4], mask[4], gw[4];
    ser_settings ser[SER_PORTS];
    uint32_t crc;           /* CRC-32 of everything before it */
} settings_t;

extern settings_t settings;         /* as loaded at power-up; NET edits go here */

void settings_load(void);           /* flash -> settings, or the defaults */
bool settings_save(void);           /* settings -> flash */
bool settings_from_flash(void);     /* were the saved settings valid at power-up? */

#endif
