#!/usr/bin/env python3
"""Placement rev 3 for can-controller: logic side rebuilt around an MCU that can fan out.

U1 turns 90 deg so each side faces what it drives (pin map in gen_schematic.py MCU_NETS):
GPIO left, CAN isolators right, USB / crystal / ICSP / UART top, DAC / I2C / 12 V status
bottom. The relays go over I2C1 to an MCP23008 (U33) right under the MCU; the relay
isolators U30/U31 move to the top edge of the 12 V block below it, inputs up, with the
ULN2803A below them, so the relay path runs straight down: MCU -> U33 -> U30/U31 -> U32 -> J30.
The 12 V block's top-left corner moves from x = 140 to x = 134. The 12 V status opto U21
moves to the top of the CAN strip, next to the input stage it watches.

Everything not listed here keeps its position (edge connectors, CAN isolators and the
rest of the 12 V block). Parts in FIXED go to exact positions; the others take the
nearest free spot to their target (place_board.Placer spiral search).

  python3 boards/can-controller/hardware/place_rev3.py
"""
import pcbnew

import place_board as pb

# ---- domains (rev 3): 12 V = strip right of x 168 below the USB-C, plus the block x > 134, y > 160
pb.DOM["B"] = [(168.6, 118.6, 199.6, 199.6), (134.6, 160.6, 199.6, 199.6)]
pb.DOM["L"] = [(100.4, 100.4, 199.6, 118.0), (100.4, 100.4, 167.4, 159.4), (100.4, 100.4, 133.4, 199.6)]

# exact positions: ref -> (x, y, rot)
FIXED = {
    "U1": (148.0, 131.0, 90),
    # top band: ICSP header (pin 1 right, PGD/PGC above U1 pins 43/44), crystal over pins 39/40,
    # UART header and heartbeat LED for pins 45-47
    "J2": (147.62, 109.6, 270),
    "Y1": (148.5, 119.3, 180),
    "J3": (132.4, 114.0, 270),
    "R7": (142.3, 113.6, 180),
    "D2": (137.2, 113.6, 0),
    # decoupling right at VDD/VSS pin pairs 56/57 (left), 25/26 and 19/20 (right)
    "C3": (139.9, 131.0, 90),
    "C5": (156.0, 130.4, 270),
    "C8": (156.0, 134.6, 90),
    # relay path: expander outputs down onto the isolator inputs, ULN2803A under the isolators
    "U33": (146.1, 144.6, 270),
    "U30": (140.0, 160.0, 270),
    "U31": (151.0, 160.0, 270),
    "U32": (145.5, 175.0, 270),
    "C40": (145.5, 153.0, 0),
    "C41": (144.4, 167.6, 0),
    "C43": (155.5, 167.6, 0),
    # 12 V status opto stands across the top edge of the CAN strip (LED side in the strip, by the input stage)
    "U21": (170.5, 115.8, 90),
    "U50": (136.3, 146.5, 0),
    "F1": (122.5, 109.2, 0),
    # CAN LEDs at the strip edge: CAN4 above U13, CAN3 between U13 and U12, CAN2 below U11
    # (CAN4 LED row right of x 157: the USB lines turn right under the crystal and climb at x 155-157)
    "R27": (159.5, 120.3, 0), "D27": (164.6, 120.3, 180),
    # status LEDs: power top left, USB link under the GPIO rows (pin 59)
    "D1": (127.5, 109.6, 0), "R1": (122.5, 113.4, 0), "D3": (122.0, 145.6, 0), "R8": (127.4, 145.6, 180),
    "R26": (159.5, 130.75, 0), "D26": (164.6, 130.75, 180),
    "D24": (157.0, 149.5, 90),
    "D25": (161.0, 158.2, 180),
}
for k in range(8):                       # GPIO rows, 7 mm lower than rev 2 to make room above
    y = 117.6 + 3.5 * k
    FIXED[f"R{51 + k}"] = (122.0, y, 180)          # pin 1 (MCU side) toward the MCU
    FIXED[f"D{51 + k}"] = (127.5, y, 0) if k % 2 == 0 else (131.5, y, 90)
FIXED["D58"] = (128.0, 142.3, 0)         # last row: left slot, clear of the ADC

# spiral-placed: ref -> (x, y, rotations, domain)
TARGETS = [
    # MCU support
    # C4/C6/C9 cannot sit at VDD pins 10/38/35 (I2C/DAC and USB lines leave there); the VDD pins are tied
    # together under U1, so these decouple +3V3 nearby
    ("C9", 157.0, 141.0, (0, 90), "L"), ("C6", 158.0, 136.5, (0, 90), "L"), ("C4", 154.0, 144.0, (0, 90), "L"),
    ("C26", 161.5, 123.5, (0, 90), "L"),
    ("C10", 150.4, 115.8, (90,), "L"), ("C11", 146.6, 115.8, (90,), "L"),
    ("R2", 152.6, 109.3, (0,), "L"), ("C12", 156.8, 109.3, (0,), "L"),
    ("C45", 153.5, 141.0, (90, 0), "L"),
    ("R34", 162.0, 115.5, (0,), "L"), ("R33", 166.5, 115.5, (90, 0), "L"),
    ("C42", 155.5, 152.6, (0,), "L"),
    # CAN logic side
    ("C24", 162.0, 133.3, (0,), "L"), ("C20", 162.5, 141.0, (0,), "L"), ("C22", 159.5, 155.5, (0, 90), "L"),
    ("R24", 160.0, 145.0, (90, 0), "L"), ("R25", 157.5, 154.5, (0, 90), "L"),
    # left column: logic LDO and the 13 V boost (header 5 V comes down the left board edge)
    ("U2", 112.0, 142.8, (0, 90), "L"), ("C1", 108.6, 148.3, (90, 0), "L"), ("C2", 117.8, 142.8, (90, 0), "L"),
    ("C7", 117.8, 148.3, (90, 0), "L"), ("C64", 111.8, 148.3, (90, 0), "L"),
    ("U63", 112.5, 153.0, (0, 90), "L"), ("L60", 109.6, 158.6, (0, 90), "L"), ("D73", 116.0, 157.5, (0, 90), "L"),
    ("C63", 116.5, 162.2, (0, 90), "L"), ("R90", 116.8, 152.5, (90, 0), "L"), ("R91", 110.0, 163.0, (0, 90), "L"),
    # under the GPIO rows: DAC + reference, op amp
    ("U60", 126.0, 151.5, (90, 0), "L"), ("C60", 121.8, 146.0, (0, 90), "L"), ("U61", 131.0, 146.0, (0, 90), "L"),
    ("R80", 131.0, 150.0, (90, 0), "L"), ("C61", 131.0, 153.5, (0, 90), "L"),
    ("U62", 125.5, 159.5, (0, 90), "L"), ("C62", 121.0, 156.5, (0, 90), "L"), ("R83", 131.0, 157.5, (90, 0), "L"),
    ("R87", 131.0, 161.5, (90, 0), "L"),
    # analog outputs at J50 pins 1-2 (y 169, 172.5), inputs at pins 3-6 (y 176 .. 186.5)
    ("R81", 122.0, 169.0, (180,), "L"), ("R85", 122.0, 172.5, (180,), "L"),
    ("R82", 128.0, 165.5, (0,), "L"), ("R86", 128.5, 169.0, (0,), "L"),
    ("D71", 128.5, 172.5, (0,), "L"), ("D72", 131.0, 165.5, (90, 0), "L"),
    ("R64", 122.0, 176.0, (0,), "L"), ("R65", 122.0, 179.5, (0,), "L"), ("R66", 122.0, 183.0, (0,), "L"),
    ("R67", 122.0, 186.5, (0,), "L"),
    ("R68", 128.5, 176.0, (0,), "L"), ("R69", 128.5, 179.5, (0,), "L"), ("R70", 128.5, 183.0, (0,), "L"),
    ("R71", 128.5, 186.5, (0,), "L"),
    # filter caps, clamps and VMID under the inputs
    ("C52", 110.0, 192.5, (90,), "L"), ("C53", 113.4, 192.5, (90,), "L"), ("C54", 116.8, 192.5, (90,), "L"),
    ("C55", 120.2, 192.5, (90,), "L"),
    ("D61", 124.0, 191.0, (0, 90), "L"), ("D62", 128.0, 191.0, (0, 90), "L"), ("D63", 124.0, 196.0, (0, 90), "L"),
    ("D64", 128.0, 196.0, (0, 90), "L"),
    ("R62", 132.0, 192.0, (90, 0), "L"), ("R63", 112.0, 197.5, (0,), "L"), ("C51", 118.0, 197.5, (0,), "L"),
    # ADC next to the expander (both on I2C), its decoupling, the I2C pull-ups by the expander
    ("C50", 136.3, 140.5, (0,), "L"), ("R60", 153.5, 138.8, (0, 90), "L"), ("R61", 157.5, 138.8, (0, 90), "L"),
    # 12 V side
    ("R32", 174.0, 119.8, (0, 90), "B"),
]


def main():
    b = pcbnew.LoadBoard(pb.PCB)
    P = pb.Placer(b)
    moving = set(FIXED) | {t[0] for t in TARGETS}
    for f in b.GetFootprints():                          # everything else stays and blocks space
        if f.GetReference() not in moving:
            x0, y0, x1, y1 = pb.cy_rel(f)
            px, py = pb.tm(f.GetPosition().x), pb.tm(f.GetPosition().y)
            if px < 200:                                 # skip anything still parked off-board
                P.occupy((px + x0, py + y0, px + x1, py + y1))
    for ref, (x, y, rot) in FIXED.items():
        P.fixed(ref, x, y, rot)
    for ref, x, y, rots, dom in TARGETS:
        if ref in FIXED:
            continue
        P.place(ref, x, y, rots, dom=dom, radius=14)
    b.Save(pb.PCB)
    print("\n".join(P.log) or "all placed")


if __name__ == "__main__":
    main()
