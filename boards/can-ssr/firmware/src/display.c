/* MAX7219, no-decode mode, bit-banged on RD0-RD2.
 * Digits 0-3 = 4-digit display, left to right. Digit 4 drives the
 * indicators: segment A = D40 (V), segment B = D41 (A). */
#include <xc.h>
#include "board.h"
#include "display.h"

/* no-decode segment bits: DP A B C D E F G */
#define SEG_DP  0x80u
static const uint8_t font_digit[10] = {
    0x7E, 0x30, 0x6D, 0x79, 0x33, 0x5B, 0x5F, 0x70, 0x7F, 0x7B
};

static void max_write(uint8_t reg, uint8_t val)
{
    uint16_t w = ((uint16_t)reg << 8) | val;
    PIN_DISP_LOAD = 0;
    for (uint8_t i = 0; i < 16; i++) {
        PIN_DISP_SCK = 0;
        PIN_DISP_DIN = (w & 0x8000u) ? 1 : 0;
        w <<= 1;
        PIN_DISP_SCK = 1;
    }
    PIN_DISP_SCK = 0;
    PIN_DISP_LOAD = 1;
}

void display_init(void)
{
    max_write(0x0F, 0);     /* display test off */
    max_write(0x09, 0);     /* no decode */
    max_write(0x0B, 4);     /* scan digits 0-4 */
    max_write(0x0A, 8);     /* intensity 8/15 */
    for (uint8_t d = 1; d <= 5; d++) max_write(d, 0);
    max_write(0x0C, 1);     /* normal operation */
}

void display_raw(const uint8_t seg[4], uint8_t indicators)
{
    for (uint8_t d = 0; d < 4; d++) max_write((uint8_t)(d + 1u), seg[d]);
    max_write(5, indicators);
}

/* value in hundredths (10 mV or 10 mA): shows 12.34, 123.4 or 1234 */
void display_value(uint16_t hundredths, uint8_t indicators)
{
    uint8_t seg[4];
    uint16_t v;
    uint8_t dp;
    if (hundredths < 10000u) { v = hundredths; dp = 1; }            /* xx.xx */
    else { v = hundredths / 10u; dp = 2; }                          /* xxx.x, max 655.3 */
    for (int8_t d = 3; d >= 0; d--) {
        seg[d] = font_digit[v % 10u];
        v /= 10u;
    }
    if (dp < 4) seg[dp] |= SEG_DP;
    if (dp == 1 && seg[0] == font_digit[0]) seg[0] = 0;           /* blank leading zero */
    display_raw(seg, indicators);
}

/* "E" + two-digit code, e.g. E 01 */
void display_fault(uint8_t code)
{
    uint8_t seg[4] = { 0x4F, 0, font_digit[(code / 10u) % 10u], font_digit[code % 10u] };
    display_raw(seg, 0);
}

/* boot screen: build letters and node number, e.g. "St.05", "HC.12", "HV.03" */
void display_boot(uint8_t build_char0, uint8_t build_char1, uint8_t node)
{
    uint8_t seg[4] = { build_char0, (uint8_t)(build_char1 | SEG_DP),
                       font_digit[node / 10u], font_digit[node % 10u] };
    display_raw(seg, 0);
}
