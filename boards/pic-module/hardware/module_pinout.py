"""PIC module geometry and connector pinout (single source of truth).

Used by gen_schematic.py and place.py here, and by
lib/footprint_src/Thl_Module/pic_module.py, which builds the host-side symbol
and footprint every POC board uses. Changing anything here changes the
module/host interface: regenerate all three and update every host board.

Module-local mm, origin at the module's top-left corner, seen from the top
(component side). The host footprint uses the same coordinates.

  J3, J4   2 x 20, 2.54 mm sockets on the module's BOTTOM side (pin headers on
           the host). J3 on the left edge, J4 on the right edge, J4 offset so a
           module turned 180 deg lands half a pitch off (keying 1).
  J3.9     key: socket position blocked on the module, pin absent on the
           host (keying 2). J3.10 is absent too: it is the creepage spacer
           between the RACK pins (J3.1-8) and the LOGIC pins.

Pin order inside J3/J4: odd pins in one column, even pins in the other,
row r = pins 2r-1 and 2r, rows 2.00 mm apart going down.
"""
import math

W, H = 56.0, 74.0                       # module outline
PITCH = 2.54
J3_PIN1 = (2.6, 3.0)                    # odd column x = 2.6 (outer), even x = 5.14
J4_PIN1 = (50.86, 21.5)                 # odd column x = 50.86 (inner), even x = 53.4
EVEN_DX = 2.54                          # even column = odd column + 2.54 mm in x
# 180-degree check: J3 rows span y 3.0-51.26, turned they land at H - y = 22.74-71.0;
# J4 spans 21.5-69.76, 1.24 mm (half a pitch) off.

MCU_AT = (28.0, 46.0)                   # TQFP-64 centre
MCU_ROT = 270                           # KiCad degrees: pins 1-16 face up, 33-48 face down

# Domain boundary (RACK above, LOGIC below), as the 2 mm gap strips between them
GAP_H = (0.0, 12.0, 8.3, 14.0)         # beside J3: key row y = 13.16 sits in it
GAP_V = (6.3, 12.0, 8.3, 19.0)         # down the inside of J3's logic rows
GAP_H2 = (6.3, 17.0, W, 19.0)          # across the board above the logic area

POWER_PINS = {
    "J3": {1: "+12V", 2: "+12V", 3: "+12V", 4: "+12V",
           5: "GND_RACK", 6: "GND_RACK", 7: "GND_RACK", 8: "GND_RACK",
           9: "KEY", 10: "SPACER",
           11: "GND", 12: "GND", 19: "+3V3", 20: "GND", 27: "+5V", 28: "GND",
           35: "+3V3", 36: "GND", 40: "GND"},
    "J4": {1: "+5V", 2: "GND", 9: "+3V3", 10: "GND", 19: "+3V3", 20: "GND",
           29: "+5V", 30: "GND", 39: "+3V3", 40: "GND"},
}

# MCU signal pins brought out: pin -> net name (port name; suffix = what the
# module itself also hangs on it). OSC1/OSC2 (39/40) stay on the module.
MCU_SIGNALS = {
    1: "RA7", 2: "RB14", 3: "RB15", 4: "RG6", 5: "RG7", 6: "RG8", 7: "MCLR", 8: "RG9",
    11: "RA12", 12: "RA11", 13: "RA0", 14: "RA1", 15: "RB0", 16: "RB1",
    17: "RB2", 18: "RB3", 21: "RC0", 22: "RC1", 23: "RC2", 24: "RC11",
    27: "RE12", 28: "RE13", 29: "RE14", 30: "RE15", 31: "RA8", 32: "RB4",
    33: "RA4", 34: "VBUS", 36: "USB_DN", 37: "USB_DP",
    42: "RD8_LED", 43: "RB5_PGD", 44: "RB6_PGC", 45: "RC10", 46: "RB7", 47: "RC13", 48: "RB8",
    49: "RB9", 50: "RC6_RX", 51: "RC7", 52: "RC8", 53: "RD5", 54: "RD6", 55: "RC9",
    58: "RF0", 59: "RF1_TX", 60: "RB10", 61: "RB11", 62: "RB12", 63: "RB13", 64: "RA10",
}

SWAPS = [(("J3", 38), ("J4", 38))]     # keeps USB_DP next to USB_DN (J3.38/39), VBUS to J4.38


def header_pos(conn, pin):
    x0, y0 = J3_PIN1 if conn == "J3" else J4_PIN1
    row = (pin - 1) // 2
    return (x0 + (EVEN_DX if pin % 2 == 0 else 0.0), y0 + row * PITCH)


def mcu_pad(pin):
    """Pad centre of TQFP-64 pin in module coordinates."""
    k = pin
    if k <= 16:
        x, y = -5.6625, -3.75 + 0.5 * (k - 1)
    elif k <= 32:
        x, y = -3.75 + 0.5 * (k - 17), 5.6625
    elif k <= 48:
        x, y = 5.6625, 3.75 - 0.5 * (k - 33)
    else:
        x, y = 3.75 - 0.5 * (k - 49), -5.6625
    t = math.radians(MCU_ROT)
    return (MCU_AT[0] + x * math.cos(t) + y * math.sin(t), MCU_AT[1] - x * math.sin(t) + y * math.cos(t))


def _cw_angle(p):
    """Clockwise angle on screen from straight up, 0..2pi, around the MCU."""
    dx, dy = p[0] - MCU_AT[0], p[1] - MCU_AT[1]
    return math.atan2(dx, -dy) % (2 * math.pi)


def assign():
    """{(conn, pin): net} for every header position.

    Signal pins and free header positions are both sorted clockwise around
    the MCU and matched in order, so the fan-out has no crossings in
    principle. Within a header row the inner column comes first.
    """
    out = {}
    free = []
    for conn in ("J3", "J4"):
        for pin in range(1, 41):
            if pin in POWER_PINS[conn]:
                out[(conn, pin)] = POWER_PINS[conn][pin]
            else:
                free.append((conn, pin))
    if len(free) != len(MCU_SIGNALS):
        raise SystemExit(f"{len(free)} free positions for {len(MCU_SIGNALS)} signals")
    inner_x = {"J3": J3_PIN1[0] + EVEN_DX, "J4": J4_PIN1[0]}

    def pos_key(cp):
        conn, pin = cp
        x, y = header_pos(conn, pin)
        a = _cw_angle((inner_x[conn], y))           # one angle per row
        return (a, 0 if x == inner_x[conn] else 1)

    free.sort(key=pos_key)
    pins = sorted(MCU_SIGNALS, key=lambda k: _cw_angle(mcu_pad(k)))
    for cp, k in zip(free, pins):
        out[cp] = MCU_SIGNALS[k]
    for a, b in SWAPS:
        out[a], out[b] = out[b], out[a]
    return out


if __name__ == "__main__":
    a = assign()
    for conn in ("J3", "J4"):
        print(conn)
        for r in range(20):
            print(f"  {2 * r + 1:2d} {a[(conn, 2 * r + 1)]:9s} {2 * r + 2:2d} {a[(conn, 2 * r + 2)]}")
