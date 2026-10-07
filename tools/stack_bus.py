"""Daughter-card stack bus: core + can-card / io-card / serial-card.

Single source of truth for the stack connectors (docs/requirements.md 4.5).
Board generators import this module, so every card agrees with the core.

  BUS     2 x 20, 2.54 mm (Samtec ESQ-120 stacking socket; plain 2 x 20
          headers/sockets for prototypes). LOGIC domain only.
  PWR12   2 x 3, 2.54 mm (Samtec ESQ-103) at the opposite edge: the RACK
          domain (+12V after the core's input protection, GND_RACK), kept
          away from the logic bus for isolation.

Stack order: the **core is on top** (decided 2026-10-06): its RJ45, 12 V
input, ICSP and LEDs stay reachable and nothing sits above its tall parts.
The core carries 2 x 20 / 2 x 3 pin headers on its underside; every card
carries ESQ stacking sockets (top side, tails through to the card below).
The bottom card's tails plug into nothing (trim, or fit SSQ sockets).

Geometry, board-local mm seen from the top (origin = top-left corner of the
100 x 100 mm outline), identical on every board:
  BUS pin n:   x = BUS_PIN1.x (odd) or + 2.54 (even), y = BUS_PIN1.y + 2.54 * row
  PWR12 pin n: same scheme from PWR12_PIN1
  Stack holes: 4 x M4 (4.3 mm) on a 91 x 91 mm square, 4.5 mm in (4.4).
Placement scripts must put pad n exactly there. On the core the headers are
flipped (underside): use underside() to map its pads to bus pins.

Pin n: row (n + 1) // 2, odd pins in one column, even in the other.
Signal names are from the MCU's side: CnTX / UnTX are MCU outputs.
Each card type uses its own block, so a card may sit at any height in the
stack, one card of each type per stack.
"""

BUS = {
    1: "+5V", 2: "+5V",
    3: "GND", 4: "GND",
    5: "C1TX", 6: "C1RX",          # can-card
    7: "C2TX", 8: "C2RX",
    9: "C3TX", 10: "C3RX",
    11: "C4TX", 12: "C4RX",
    13: "GND", 14: "+3V3",
    15: "SCL", 16: "SDA",          # shared I2C1 (pull-ups on the core)
    17: "U2TX", 18: "U2RX",        # serial-card
    19: "U3TX", 20: "U3RX",
    21: "U4TX", 22: "U4RX",
    23: "U5TX", 24: "U5RX",
    25: "DE1", 26: "DE2",          # serial-card RS-485 driver enables
    27: "RLY1", 28: "RLY2",        # io-card
    29: "RLY3", 30: "RLY4",
    31: "GPIO1", 32: "GPIO2",
    33: "GPIO3", 34: "GPIO4",
    35: "GND", 36: "VMID",         # io-card analog: VMID (1.65 V) from the core's OA5 follower
    37: "AI1P", 38: "AI1N",
    39: "AI2P", 40: "AI2N",
}

PWR12 = {1: "+12V", 2: "+12V", 3: "+12V", 4: "GND_RACK", 5: "GND_RACK", 6: "GND_RACK"}

SUPPLIES = {"+5V", "+3V3", "GND", "+12V", "GND_RACK"}

PITCH = 2.54
BOARD = (100.0, 100.0)
HOLES = [(4.5, 4.5), (95.5, 4.5), (4.5, 95.5), (95.5, 95.5)]
BUS_PIN1 = (5.0, 26.0)        # left edge; rows run down to y = 74.26
PWR12_PIN1 = (92.46, 47.46)   # right edge, RACK side; even column at x = 95.0


def pin_pos(origin, n):
    """(x, y) of pin n of a 2-row connector whose pin 1 is at origin."""
    row = (n - 1) // 2
    return (origin[0] + (PITCH if n % 2 == 0 else 0.0), origin[1] + row * PITCH)


def underside(k):
    """Bus pin served by pad k of a connector mounted on the underside (the
    core's J10/J11). Flipping mirrors the footprint, so the odd and even
    columns swap: pad k sits where bus pin k + 1 (k odd) or k - 1 is."""
    return k + 1 if k % 2 else k - 1


def bus_pos(n):
    return pin_pos(BUS_PIN1, n)


def pwr12_pos(n):
    return pin_pos(PWR12_PIN1, n)


# Core MCU (PIC32MK1024MCM064, TQFP-64) pin -> bus signal. PPS groups checked
# against DS60001519E Tables 13-1/13-2 (output group / input group):
#   C1TX RPB3 O1, C1RX RPB2 I3; C2TX RPB0 O4, C2RX RPA1 I2; C3TX RPC1 O3,
#   C3RX RPC0 I1; C4TX RPA8 O2, C4RX RPE15 I4 (as on the can-controller);
#   U2TX RPC10 O4, U2RX RPB8 I2 (input-only pin); U3TX RPE14 O3, U3RX RPB4 I1;
#   U4TX RPB1 O2, U4RX RPB14 I4; U5TX RPB10 O4, U5RX RPC13 I3 (input-only pin).
# SCL1/SDA1 are fixed on RG7/RG8; AI on AN12/AN13 (RE12/RE13), AN8/AN11 (RC2/RC11).
# JTAG must be disabled (RA7, RA8, RA10, RB9 are in use).
MCU_PINS = {
    18: "C1TX", 17: "C1RX", 15: "C2TX", 14: "C2RX", 22: "C3TX", 21: "C3RX", 31: "C4TX", 30: "C4RX",
    5: "SCL", 6: "SDA",
    45: "U2TX", 48: "U2RX", 29: "U3TX", 32: "U3RX", 16: "U4TX", 2: "U4RX", 60: "U5TX", 47: "U5RX",
    64: "DE1", 1: "DE2",
    3: "RLY1", 4: "RLY2", 8: "RLY3", 11: "RLY4",
    12: "GPIO1", 13: "GPIO2", 61: "GPIO3", 62: "GPIO4",
    46: "VMID", 49: "VMID",
    27: "AI1P", 28: "AI1N", 24: "AI2P", 23: "AI2N",
}
