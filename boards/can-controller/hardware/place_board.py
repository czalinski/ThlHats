#!/usr/bin/env python3
"""First-pass placement for can-controller (floorplan rev 2, variant B).

Fixed parts (edge connectors, MCU, isolators) go to exact positions. Every
other part gets a target point, candidate rotations and a domain (logic or
12 V); it lands at the nearest free spot (spiral search) where its courtyard
plus a margin clears placed parts, keep-outs (DIN clip screws, mounting
holes, Pi header) and stays inside its domain.

Board coordinates in mm, board corner at (100, 100). Run once for the first
pass; after hand edits in KiCad, don't rerun (it overwrites positions).

  python3 boards/can-controller/hardware/place_board.py
"""
import math
import pcbnew

PCB = "/home/c_zal/projects/ThlHats/boards/can-controller/hardware/can-controller.kicad_pcb"
mm, tm = pcbnew.FromMM, pcbnew.ToMM
MARGIN = 0.15          # free space added around every courtyard (courtyards already include clearance)

# ---- domains: lists of rectangles (x0, y0, x1, y1) -------------------------
# 12 V: strip right of x = 168 below the USB-C, and the block x > 140, y > 160 (relay terminal on the bottom edge)
D12 = [(168.6, 118.6, 199.6, 199.6), (140.6, 160.6, 199.6, 199.6)]
DLOG = [(100.4, 100.4, 199.6, 118.0), (100.4, 100.4, 167.4, 159.4), (100.4, 100.4, 139.4, 199.6)]
DANY = [(100.4, 100.4, 199.6, 199.6)]
DOM = {"L": DLOG, "B": D12, "*": DANY}

# ---- keep-outs: circles (x, y, r) --------------------------------------------
KEEP_C = []     # DIN clips dropped 2026-10-05 (3D-printed mount on the M2.5 holes instead)
KEEP_C += [(x, y, 3.2) for x, y in ((103.5, 103.5), (161.5, 103.5), (103.5, 152.5), (161.5, 152.5),
                                    (196.5, 103.5), (103.5, 196.5), (196.5, 196.5))]  # M2.5 holes


def cy_rel(fp):
    """courtyard bbox relative to the footprint position at its current rotation."""
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayerName() in ("F.Courtyard", "B.Courtyard"):
            bb = g.GetBoundingBox()
            xs += [tm(bb.GetX()), tm(bb.GetRight())]
            ys += [tm(bb.GetY()), tm(bb.GetBottom())]
    if not xs:
        bb = fp.GetBoundingBox(False)
        xs, ys = [tm(bb.GetX()), tm(bb.GetRight())], [tm(bb.GetY()), tm(bb.GetBottom())]
    px, py = tm(fp.GetPosition().x), tm(fp.GetPosition().y)
    return min(xs) - px, min(ys) - py, max(xs) - px, max(ys) - py


class Placer:
    def __init__(self, board):
        self.b = board
        self.fp = {f.GetReference(): f for f in board.GetFootprints()}
        self.rects = []      # occupied rectangles
        self.log = []

    def rect_of(self, ref, x, y, rot):
        f = self.fp[ref]
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        x0, y0, x1, y1 = cy_rel(f)
        return (x + x0, y + y0, x + x1, y + y1)

    def free(self, r, dom):
        x0, y0, x1, y1 = r
        if not any(a0 <= x0 and b0 <= y0 and x1 <= a1 and y1 <= b1 for a0, b0, a1, b1 in DOM[dom]):
            return False
        for a0, b0, a1, b1 in self.rects:
            if x0 < a1 + MARGIN and a0 < x1 + MARGIN and y0 < b1 + MARGIN and b0 < y1 + MARGIN:
                return False
        for cx, cy, cr in KEEP_C:
            nx, ny = min(max(cx, x0), x1), min(max(cy, y0), y1)
            if math.hypot(nx - cx, ny - cy) < cr + MARGIN:
                return False
        return True

    def fixed(self, ref, x, y, rot=0, keep=True):
        r = self.rect_of(ref, x, y, rot)
        if keep:
            self.rects.append(r)
        return r

    def occupy(self, r):
        self.rects.append(r)

    def place(self, ref, x, y, rots=(0, 90), dom="L", radius=30.0, step=0.25):
        best = None
        n = int(radius / step)
        pts = sorted(((dx * step, dy * step) for dx in range(-n, n + 1) for dy in range(-n, n + 1)
                      if dx * dx + dy * dy <= n * n), key=lambda p: p[0] ** 2 + p[1] ** 2)
        for dx, dy in pts:
            for rot in rots:
                r = self.rect_of(ref, x + dx, y + dy, rot)
                if self.free(r, dom):
                    best = (x + dx, y + dy, rot, r)
                    break
            if best:
                break
        if not best:
            self.log.append(f"{ref}: NO SPOT near ({x}, {y})")
            self.rect_of(ref, x, y, rots[0])
            return False
        bx, by, rot, r = best
        self.rect_of(ref, bx, by, rot)
        self.rects.append(r)
        d = math.hypot(bx - x, by - y)
        if d > 6:
            self.log.append(f"{ref}: {d:.1f} mm from target")
        return True


def main():
    b = pcbnew.LoadBoard(PCB)
    P = Placer(b)
    # existing fixed items: Pi header, holes, DIN clips (their top keep-outs are circles)
    for ref in ("J1",):
        f = P.fp[ref]
        x0, y0, x1, y1 = cy_rel(f)
        px, py = tm(f.GetPosition().x), tm(f.GetPosition().y)
        P.occupy((px + x0, py + y0, px + x1, py + y1))

    # ---- edge connectors (front flush with the board edge) -------------------
    # right edge: rot 90 puts the plug side at +x; pin 1 lowest, pins go up
    P.fixed("J4", 190.87, 115.68, 90)                                  # USB-C
    for ref, y0 in (("J13", 118.5), ("J12", 135.5), ("J10", 152.5), ("J11", 169.5)):   # CAN4, CAN3, CAN1, CAN2
        P.fixed(ref, 191.48, y0 + 13.48, 90)
    # SPTD double-level push-in terminals (courtyard 3.0 beyond the end pins, front 7.4, back 11.6)
    P.fixed("J40", 107.4, 107.6 + 3.0, 270)                            # GPIO, left edge, top
    P.fixed("J50", 107.4, 166.0 + 3.0, 270)                            # ANALOG, left edge, bottom
    P.fixed("J30", 150.5 + 3.0, 192.6, 0)                              # RELAY, bottom edge

    # ---- MCU and isolators -------------------------------------------------------
    P.fixed("U1", 150.0, 117.5, 0)
    # ISO1044 (all four) straddle x = 168, logic pins 1-4 left, between y 121 and 158
    P.fixed("U13", 168.0, 125.0, 0)        # CAN4
    P.fixed("U12", 168.0, 136.5, 0)        # CAN3
    P.fixed("U10", 168.0, 146.0, 0)        # CAN1
    P.fixed("U11", 168.0, 157.0, 0)        # CAN2 (clear of the MH4 standoff)
    P.fixed("U21", 143.5, 160.0, 90)       # 12 V status opto on the block's top edge, LED pins down
    P.fixed("U30", 140.0, 170.0, 0)        # ISO6740 RLY1-4 on the block's left edge
    P.fixed("U31", 140.0, 181.5, 0)        # ISO6740 RLY5-8
    P.fixed("U20", 143.1, 191.0, 270)      # R-78E bus 5 V, in the corner under U31, left of the relay terminal

    pl = P.place
    # ---- analog: HV 10M and AO output parts right beside J50 (front row x 107.4, pins 169..186.5) --
    for n in range(4):
        y = 169.0 + 3.5 * n
        pl(f"R{64 + n}", 122.0, y, (0,), dom="L", radius=2)      # 10M at its AI pin
        pl(f"R{68 + n}", 128.5, y, (0,), dom="L", radius=4)      # 130k
        pl(f"C{52 + n}", 121.5 + 3.4 * n, 193.5, (90,), dom="L", radius=6)   # 0.1 uF, below
    for n in range(4):
        pl(f"D{61 + n}", 134.5 if n % 2 == 0 else 130.5, 168.0 + 3.6 * n, (0, 90), dom="L", radius=8)   # clamps
    pl("R81", 122.0, 183.0, (0,), radius=3)        # AO1 470R at its pin
    pl("R85", 122.0, 186.5, (0,), radius=3)        # AO2 470R
    pl("D71", 128.5, 183.0, (0,), radius=4)        # AO1 Zener
    pl("D72", 128.5, 186.5, (0,), radius=4)        # AO2 Zener
    pl("C42", 133.0, 182.0, (90, 0), radius=4)     # U31 logic decoupling
    pl("C40", 133.0, 170.0, (90, 0), radius=6)     # U30 logic decoupling
    # ---- MCU support --------------------------------------------------------------
    for ref, x, y in (("C3", 141.6, 118.25), ("C4", 150.75, 125.7), ("C5", 158.3, 118.75), ("C6", 149.75, 109.6),
                      ("C9", 158.3, 122.5), ("C8", 146.5, 125.7)):
        pl(ref, x, y, (90, 0), radius=6)
    pl("FB1", 142.5, 125.7, (0, 90), radius=6)
    pl("C7", 140.6, 112.8, (90, 0), radius=6)
    pl("Y1", 162.6, 117.7, (90,), radius=4)
    pl("C10", 166.3, 114.6, (0, 90), radius=5)
    pl("C11", 166.3, 120.8, (0, 90), radius=5)
    pl("R2", 139.0, 122.0, (90, 0), radius=6)
    pl("C12", 141.5, 129.0, (90, 0), radius=6)
    # logic power left of the MCU; ICSP and UART headers in the gap between the left-edge terminals
    pl("U2", 137.5, 113.0, (90, 0), radius=6)
    pl("F1", 136.0, 108.6, (0,), radius=6)
    pl("C1", 136.0, 120.5, (0, 90), radius=6)
    pl("C2", 140.6, 122.5, (90, 0), radius=6)
    pl("J2", 110.5, 141.0, (0,), radius=4)
    pl("J3", 110.5, 158.0, (0,), radius=4)
    # USB, CC, VBUS sense; status LEDs in a row along the top edge (logic)
    for ref, x, y, rots in (("U3", 185.0, 113.0, (90, 0)), ("R3", 188.0, 107.5, (90,)), ("R4", 185.0, 107.5, (90,)),
                            ("R5", 181.0, 111.5, (90,)), ("R6", 178.0, 111.5, (90,))):
        pl(ref, x, y, rots, radius=8)
    for k, (d, r) in enumerate((("D1", "R1"), ("D2", "R7"), ("D3", "R8"))):
        x = 168.0 + 4.0 * k
        pl(d, x, 108.5, (90,), radius=8)
        pl(r, x, 103.0, (90,), radius=8)

    # ---- CAN channels -------------------------------------------------------------
    can = {1: ("U10", 152.5), 2: ("U11", 169.5), 3: ("U12", 135.5), 4: ("U13", 118.5)}
    for n, (iso, y0) in can.items():
        yc = y0 + 8.3
        i = n - 1
        iso_x, iso_y = tm(P.fp[iso].GetPosition().x), tm(P.fp[iso].GetPosition().y)
        pl(f"C{20 + 2 * i}", iso_x - 6.5, iso_y - 2.0, (90, 0), dom="L", radius=8)
        pl(f"C{21 + 2 * i}", iso_x + 2.6, iso_y + (4.1 if n == 4 else -4.1), (0,), dom="B", radius=3)
        pl(f"D{20 + i}", 182.0, yc - 3.5, (0, 90), dom="B", radius=8)                    # NUP2105L
        pl(f"JP{1 + i}", 186.5, yc - 4.0, (0,), dom="B", radius=8)                       # TERM jumper
        pl(f"R{20 + i}", 182.5, yc + 1.5, (90, 0), dom="B", radius=8)                    # 120R
        pl(f"F{10 + i}", 185.5, yc + 4.5, (0, 90), dom="B", radius=8)                    # cable fuse
    # CAN activity LEDs: a column on the logic side at the strip edge, top to bottom CAN4, CAN3, CAN1, CAN2
    for k, n in enumerate((4, 3, 1, 2)):
        y = 124.0 + 9.5 * k
        pl(f"D{23 + n}", 160.0, y, (0,), dom="L", radius=8)
        pl(f"R{23 + n}", 160.0, y + 3.0, (0,), dom="L", radius=8)

    # ---- 12 V block: relay LEDs right behind the relay terminal, ULN, input stage ---------
    for i in range(1, 9):
        pl(f"D{30 + i}", 153.5 + 3.5 * (i - 1), 178.3, (90,), dom="B", radius=1)   # relay LED behind its pin
    pl("Q1", 175.7, 150.0, (90,), dom="B", radius=20)                 # reverse-polarity FET: strip column first
    pl("C41", 147.6, 163.0, (90, 0), dom="B", radius=4)               # U30 bus-side decoupling
    pl("U32", 149.0, 169.6, (90, 0), dom="B", radius=6)               # ULN2803A
    pl("J20", 163.0, 168.0, (90, 270, 0, 180), dom="B", radius=8)     # 12 V IN, top entry
    pl("C32", 148.0, 186.0, (90, 0), dom="B", radius=6)
    pl("C43", 147.6, 179.0, (90, 0), dom="B", radius=4)               # U31 bus-side decoupling
    # strip column x 172..179: input stage, relay LED resistors, 12 V LED
    for ref, x, y in (("F20", 175.5, 124.0), ("D11", 175.5, 143.0), ("D10", 175.5, 150.0),
                      ("R30", 175.5, 153.5), ("C30", 175.5, 157.0), ("C31", 175.5, 160.5), ("F30", 175.5, 165.0),
                      ("C44", 175.5, 169.0), ("R31", 175.5, 172.0), ("D12", 175.5, 175.0), ("R32", 147.6, 162.0)):
        pl(ref, x, y, (90, 0), dom="B", radius=30)
    for i in range(1, 9):
        pl(f"R{40 + i}", 175.5, 178.0 + 2.8 * i, (0, 90), dom="B", radius=40)

    # 12 V status: logic side of the opto
    pl("R33", 141.0, 155.0, (0, 90), dom="L", radius=10)
    pl("R34", 145.0, 155.0, (0, 90), dom="L", radius=10)

    # ---- GPIO: series R + clamp per channel beside J40 ---------------------------------
    for ch in range(1, 9):
        y = 110.6 + 3.5 * (ch - 1)
        pl(f"R{50 + ch}", 122.0, y, (0,), dom="L", radius=4)
        pl(f"D{50 + ch}", 127.5 if ch % 2 else 131.5, y, (0, 90), dom="L", radius=6)

    # ---- DAC + reference: middle column -----------------------------------------------
    pl("U60", 137.5, 129.5, (90, 0), radius=8)
    pl("C60", 132.5, 128.5, (0, 90), radius=6)
    pl("U61", 132.5, 132.0, (0, 90), radius=8)
    pl("R80", 142.5, 128.5, (90, 0), radius=8)
    pl("C61", 132.5, 135.5, (0, 90), radius=8)
    # ---- ADC, VMID, I2C pull-ups: middle column between the DIN screw columns ------------
    pl("U50", 137.5, 152.0, (0, 90), radius=8)
    pl("C50", 132.5, 148.0, (0, 90), radius=6)
    for ref, x, y in (("R60", 132.5, 152.0), ("R61", 132.5, 155.0), ("R62", 142.5, 149.0), ("R63", 142.5, 152.0),
                      ("C51", 142.5, 155.0)):
        pl(ref, x, y, (90, 0), radius=12)
    # ---- analog out: op amp + gain set above the ADC -------------------------------------
    pl("U62", 137.5, 140.0, (0, 90), radius=8)
    pl("C62", 133.0, 140.0, (90, 0), radius=6)
    for ref, x, y in (("R82", 142.5, 137.0), ("R83", 142.5, 140.0), ("R86", 142.5, 143.0), ("R87", 132.5, 144.0)):
        pl(ref, x, y, (90, 0), radius=14)
    # ---- 13 V boost --------------------------------------------------------------------
    for ref, x, y in (("U63", 157.0, 130.0), ("L60", 157.0, 135.0), ("D73", 157.0, 140.0), ("C64", 153.0, 128.0),
                      ("R90", 156.0, 145.0), ("R91", 156.0, 148.0), ("C63", 157.0, 143.0)):
        pl(ref, x, y, (0, 90), radius=20)

    b.Save(PCB)
    print("\n".join(P.log) or "all placed")


if __name__ == "__main__":
    main()
