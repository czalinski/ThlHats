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
# 12 V: strip right of x = 168 below the USB-C, and the block x 148..168, y 146..189 (+ under the relay plug)
D12 = [(168.6, 118.6, 199.6, 199.6), (148.6, 146.6, 199.6, 188.6), (155.1, 146.6, 199.6, 199.6)]
DLOG = [(100.4, 100.4, 199.6, 118.0), (100.4, 100.4, 167.4, 145.4), (100.4, 100.4, 147.4, 199.6),
        (100.4, 189.2, 154.0, 199.6)]
DANY = [(100.4, 100.4, 199.6, 199.6)]
DOM = {"L": DLOG, "B": D12, "*": DANY}

# ---- keep-outs: circles (x, y, r) --------------------------------------------
KEEP_C = [(x, y, 4.0) for x in (125.0, 175.0) for y in (137.554, 150.0, 162.446)]     # DIN clip screw heads (M4 pan, 7 mm)
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
    # left edge: rot 270, plug side at -x, pins go down
    P.fixed("J41", 108.52, 109.5 + 3.08, 270)                          # GPIO 5-8
    P.fixed("J40", 108.52, 156.0 + 3.08, 270)                          # GPIO 1-4
    # bottom edge: rot 0, plug side at +y, pins go right
    P.fixed("J50", 107.5 + 3.08, 191.48, 0)                            # ANALOG
    P.fixed("J30", 157.0 + 3.08, 191.48, 0)                            # RELAY

    # ---- MCU and isolators -------------------------------------------------------
    P.fixed("U1", 150.0, 117.5, 0)
    # ISO1044 CAN3/CAN4: straddle x = 168 (logic pins 1-4 left); CAN1/CAN2: straddle y = 146 (logic up)
    P.fixed("U13", 168.0, 124.7, 0)        # CAN4
    P.fixed("U12", 168.0, 143.0, 0)        # CAN3, between the DIN screws
    P.fixed("U11", 152.0, 145.0, 270)      # CAN2
    P.fixed("U10", 158.2, 145.0, 270)      # CAN1
    P.fixed("U21", 148.0, 152.0, 180)      # 12 V status opto: LED pins right (12 V), transistor left
    P.fixed("U30", 148.0, 167.2, 0)        # ISO6740 RLY1-4
    P.fixed("U31", 148.0, 180.0, 0)        # ISO6740 RLY5-8

    pl = P.place
    # ---- analog in columns and AO output parts first: tight space above the analog plug ---
    for n in range(4):
        x = 123.5 + 3.3 * n
        pl(f"R{64 + n}", x, 185.0, (90,), dom="L", radius=3)       # 10M
        pl(f"R{68 + n}", x, 179.3, (90,), dom="L", radius=3)       # 130k
        pl(f"C{52 + n}", x, 173.6, (90,), dom="L", radius=3)       # 0.1 uF
        pl(f"D{61 + n}", 123.5 + 4.0 * n, 168.8, (90,), dom="L", radius=4)   # clamps
    pl("R81", 136.8, 184.0, (90,), radius=3)       # AO1 470R
    pl("D71", 136.8, 178.4, (90,), radius=3)       # AO1 Zener
    pl("R85", 144.6, 187.3, (0,), radius=3)        # AO2 470R, between U31 and the analog plug
    pl("D72", 140.3, 178.4, (90,), radius=3)       # AO2 Zener
    pl("C42", 140.3, 173.4, (90, 0), radius=4)     # U31 logic decoupling
    pl("C40", 140.3, 163.5, (90, 0), radius=4)     # U30 logic decoupling
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
    # logic power, ICSP, UART
    pl("F1", 113.0, 109.0, (0,), radius=5)
    pl("U2", 130.0, 112.0, (0,), radius=6)
    pl("C1", 124.5, 112.0, (90, 0), radius=6)
    pl("C2", 135.6, 112.0, (90, 0), radius=6)
    pl("J2", 126.0, 119.8, (90,), radius=6)
    pl("J3", 128.0, 125.2, (90,), radius=6)
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
        if n in (3, 4):
            pl(f"C{20 + 2 * i}", iso_x - 6.0, iso_y - 4.0, (0, 90), dom="L", radius=8)
            pl(f"C{21 + 2 * i}", iso_x + 6.5, iso_y - 4.0, (90, 0), dom="B", radius=8)
        else:
            pl(f"C{20 + 2 * i}", iso_x, iso_y - 6.5, (0, 90), dom="L", radius=8)
            pl(f"C{21 + 2 * i}", iso_x, iso_y + 6.5, (0, 90), dom="B", radius=8)
        pl(f"D{20 + i}", 181.5, yc - 3.5, (0, 90), dom="B", radius=8)                    # NUP2105L
        pl(f"JP{1 + i}", 186.5, yc - 4.0, (0,), dom="B", radius=8)                       # TERM jumper
        pl(f"R{20 + i}", 182.5, yc + 1.5, (90, 0), dom="B", radius=8)                    # 120R
        pl(f"F{10 + i}", 185.5, yc + 5.0, (0, 90), dom="B", radius=8)                    # cable fuse
    # CAN activity LEDs: a row of four at the top edge, after the status LEDs
    for n in (1, 2, 3, 4):
        x = 168.0 + 4.0 * (n + 2)
        if x > 184:
            x = 156.0 + 4.0 * (n - 3)
        pl(f"D{23 + n}", x, 108.5, (90,), dom="L", radius=10)
        pl(f"R{23 + n}", x, 103.0, (90,), dom="L", radius=10)

    # ---- 12 V block: input, bus 5 V, relay drive -------------------------------------
    pl("C43", 155.6, 176.6, (90,), dom="B", radius=2)                 # U31 bus-side decoupling, at its VCC2 pin
    pl("C41", 155.6, 163.6, (90,), dom="B", radius=3)                 # U30 bus-side decoupling
    pl("U32", 163.1, 182.4, (0,), dom="B", radius=4)                  # ULN2803A
    pl("U20", 152.5, 154.0, (0, 180), dom="B", radius=12)             # R-78E bus 5 V
    pl("J20", 160.0, 169.0, (0, 180), dom="B", radius=10)             # 12 V IN, top entry
    pl("Q1", 174.5, 172.5, (90, 270, 0), dom="B", radius=10)
    pl("F20", 166.0, 160.0, (90, 0), dom="B", radius=12)
    pl("D11", 176.0, 180.5, (90, 0), dom="B", radius=12)
    for ref, x, y in (("C30", 171.0, 179.0), ("C31", 171.0, 182.0), ("D10", 178.0, 168.0), ("R30", 171.0, 185.0),
                      ("C32", 160.0, 159.0), ("R31", 166.0, 152.0), ("D12", 166.0, 155.0), ("R32", 154.0, 160.0),
                      ("F30", 167.5, 176.0), ("C44", 167.5, 180.0)):
        pl(ref, x, y, (0, 90), dom="B", radius=30)
    # 12 V status: logic side of the opto
    pl("R33", 141.0, 151.0, (0, 90), dom="L", radius=8)
    pl("R34", 141.0, 154.0, (0, 90), dom="L", radius=8)
    # relay LEDs: two rows of four, middle logic area right of MK1
    for i in range(1, 9):
        x = 131.0 + ((i - 1) % 4) * 4.0
        y = 129.0 if i <= 4 else 140.0
        pl(f"R{40 + i}", x, y, (90,), dom="L", radius=8)
        pl(f"D{30 + i}", x, y + 5.3, (90,), dom="L", radius=8)

    # ---- GPIO: series R and clamp per channel, next to the connector pin ------------
    for k, (jref, y1) in enumerate((("J40", 159.08), ("J41", 112.58))):
        for j in range(4):
            ch = (1 if jref == "J40" else 5) + j
            y = y1 + 7.0 * j
            pl(f"R{50 + ch}", 114.5, y, (0,), dom="L", radius=6)
            pl(f"D{50 + ch}", 119.5, y, (0, 90), dom="L", radius=6)

    # ---- DAC + reference: left of MK1 ------------------------------------------------
    pl("U60", 116.5, 146.0, (0, 90), radius=8)
    pl("C60", 116.5, 139.5, (0, 90), radius=6)
    pl("U61", 116.5, 153.0, (0, 90), radius=6)
    pl("R80", 120.0, 153.0, (90, 0), radius=6)
    pl("C61", 113.0, 153.0, (90, 0), radius=6)
    # ---- ADC, VMID, I2C pull-ups, opto pull-up: below the relay LEDs -----------------
    pl("U50", 135.0, 155.0, (0, 90), radius=8)
    pl("C50", 139.5, 152.0, (90, 0), radius=6)
    for ref, x, y in (("R60", 130.0, 150.5), ("R61", 133.5, 150.5), ("R62", 140.0, 157.0), ("R63", 143.0, 157.0),
                      ("C51", 141.5, 161.5), ("R33", 142.0, 147.0), ("R34", 143.5, 151.5)):
        pl(ref, x, y, (90, 0), radius=20)
    # ---- analog out: op amp + gain set near the ADC; output R/Zener next to the AO pins ---
    pl("U62", 146.0, 140.5, (0, 90), radius=10)
    pl("C62", 150.5, 140.5, (90, 0), radius=8)
    for ref, x, y in (("R82", 141.0, 136.0), ("R83", 141.0, 141.0), ("R86", 151.0, 136.0), ("R87", 151.0, 145.0)):
        pl(ref, x, y, (90, 0), radius=20)
    # ---- 13 V boost: below the CAN isolators' logic caps -------------------------------
    for ref, x, y in (("U63", 152.0, 133.0), ("L60", 157.0, 133.0), ("D73", 162.0, 133.0), ("C64", 147.5, 133.0),
                      ("R90", 157.0, 128.5), ("R91", 162.0, 128.5), ("C63", 152.0, 128.5)):
        pl(ref, x, y, (0, 90), radius=20)

    b.Save(PCB)
    print("\n".join(P.log) or "all placed")


if __name__ == "__main__":
    main()
