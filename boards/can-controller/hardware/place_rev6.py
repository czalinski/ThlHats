#!/usr/bin/env python3
"""First-pass placement for can-controller, floorplan rev 6 (2026-10-06).

Fixed parts (edge connectors, isolation crossings, MCU, W6100) go to the
floorplan positions (floorplan_rev6.py). Every other part has a target and a
domain; it lands at the nearest free spot (spiral search) whose courtyard
clears placed parts and the standoff holes and stays inside its domain.
Domains are floorplan rev 6 with each boundary pulled back 1 mm, so every
isolation gap is at least 2 mm wide; only the crossing parts straddle it.

Board coordinates are board-local mm (board corner at (100, 100) in KiCad).
Run once for the first pass; after hand edits in KiCad, don't rerun.

  python3 boards/can-controller/hardware/place_rev6.py
"""
import math
from pathlib import Path

import pcbnew

PCB = str(Path(__file__).resolve().parent / "can-controller.kicad_pcb")
O = 100.0
mm, tm = pcbnew.FromMM, pcbnew.ToMM
MARGIN = 0.2
G = 1.0                    # half isolation gap

# --- domains (floorplan rev 6), lists of rectangles in board-local mm -----------------------
B_C1, B_C1Y, B_R, B_RY, B_X = 24.0, 30.0, 33.0, 90.0, 73.0
CAN_GAPS = (39.6, 58.2)    # CAN4 | CAN3 | CAN2 on the right
DOM = {
    "L": [(B_C1 + G, 0.3, B_X - G, B_C1Y + G), (B_R + G, 0.3, B_X - G, 99.7), (11.5 + G, B_RY + G, B_X - G, 99.7)],
    "R": [(0.3, B_C1Y + G, B_R - G, B_RY - G), (0.3, B_C1Y + G, 11.5 - G, 99.7)],
    "C1": [(0.3, 0.3, B_C1 - G, B_C1Y - G)],
    "C4": [(B_X + G, 0.3, 99.7, CAN_GAPS[0] - G)],
    "C3": [(B_X + G, CAN_GAPS[0] + G, 99.7, CAN_GAPS[1] - G)],
    "C2": [(B_X + G, CAN_GAPS[1] + G, 99.7, 99.7)],
}
HOLES = [(4.5, 4.5), (95.5, 4.5), (4.5, 95.5), (95.5, 95.5)]
HOLE_R = 4.3


def cy_rel(fp):
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
        self.rects = []
        self.log = []

    def rect_of(self, ref, x, y, rot):
        f = self.fp[ref]
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(mm(O + x), mm(O + y)))
        x0, y0, x1, y1 = cy_rel(f)
        return (x + x0, y + y0, x + x1, y + y1)

    def free(self, r, dom):
        x0, y0, x1, y1 = r
        if dom and not any(a0 <= x0 and b0 <= y0 and x1 <= a1 and y1 <= b1 for a0, b0, a1, b1 in DOM[dom]):
            return False
        for a0, b0, a1, b1 in self.rects:
            if x0 < a1 + MARGIN and a0 < x1 + MARGIN and y0 < b1 + MARGIN and b0 < y1 + MARGIN:
                return False
        for cx, cy in HOLES:
            nx, ny = min(max(cx, x0), x1), min(max(cy, y0), y1)
            if math.hypot(nx - cx, ny - cy) < HOLE_R + MARGIN:
                return False
        return True

    def fixed(self, ref, rot=0, x=None, y=None, left=None, right=None, top=None, bottom=None):
        r = self.rect_of(ref, x or 0, y or 0, rot)
        dx = (left - r[0]) if left is not None else (right - r[2]) if right is not None else 0
        dy = (top - r[1]) if top is not None else (bottom - r[3]) if bottom is not None else 0
        r = self.rect_of(ref, (x or 0) + dx, (y or 0) + dy, rot)
        self.rects.append(r)
        return r

    def place(self, ref, x, y, dom, rots=(0, 90), radius=25.0, step=0.25):
        n = int(radius / step)
        pts = sorted(((i * step, j * step) for i in range(-n, n + 1) for j in range(-n, n + 1)
                      if i * i + j * j <= n * n), key=lambda p: p[0] ** 2 + p[1] ** 2)
        for dx, dy in pts:
            for rot in rots:
                r = self.rect_of(ref, x + dx, y + dy, rot)
                if self.free(r, dom):
                    self.rects.append(r)
                    if math.hypot(dx, dy) > 8:
                        self.log.append(f"{ref}: {math.hypot(dx, dy):.1f} mm from target")
                    return True
        self.log.append(f"{ref}: NO SPOT near ({x}, {y}) in {dom}")
        self.rect_of(ref, x, y, rots[0])
        return False


def main():
    b = pcbnew.LoadBoard(PCB)
    p = Placer(b)
    for ref, (x, y) in zip(("MH1", "MH2", "MH3", "MH4"), HOLES):
        p.rects.append((x - HOLE_R, y - HOLE_R, x + HOLE_R, y + HOLE_R))

    # --- edge connectors and crossings (floorplan rev 6) ----------------------------------
    p.fixed("J11", -90, left=0, top=12.45)                 # CAN1: pin 1 at y 15.5 (stack CAN position)
    for ref, top in (("J14", 22.0), ("J13", 40.6), ("J12", 59.2)):
        p.fixed(ref, 90, right=100, top=top)
    p.fixed("U10", 180, x=B_C1, y=12.45 + 7.3)             # ISOW1044 CAN1: logic side faces right
    for ref, top in (("U13", 22.0), ("U12", 40.6), ("U11", 59.2)):
        p.fixed(ref, 0, x=B_X, y=top + 8.3)
    p.fixed("J30", -90, left=0, top=34.5)                  # relays
    p.fixed("K1", 180, x=B_R + 3.81, y=40.0)               # AQW212: LED pins 1-4 in LOGIC, contacts in RACK
    p.fixed("K2", 180, x=B_R + 3.81, y=52.0)
    p.fixed("J20", 90, left=0.5, top=56.0)                 # 12 V in
    p.fixed("U20", 90, x=B_R - 2.55, y=72.0)               # TDN 5-2411WI: input row RACK, output row LOGIC
    p.fixed("JP5", 0, x=15.0, y=B_C1Y - 1.27)              # CAN1 POWERED: GND_CAN1 | GND_RACK
    p.fixed("JP6", 180, x=19.5, y=B_C1Y + 1.27)            #               V12_F10 (RACK) | V12_CAN1
    p.fixed("J4", 180, left=40.0, top=0)                   # RJ45
    p.fixed("J40", 0, left=34.0, bottom=100)               # GPIO / AI (AI dividers to its right)
    p.fixed("U3", 0, x=46.0, y=30.0)                       # W6100
    p.fixed("U1", 90, x=57.0, y=52.0)                      # MCU, CAN pins (17-32) face the right-hand isolators
    p.fixed("J2", 90, x=64.0, y=6.0)                       # ICSP

    # --- MCU first: decoupling and crystal right at its pins ------------------------------------
    mx, my = 57.0, 52.0
    for ref in ("C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "FB1", "Y1", "C11", "C12"):
        p.place(ref, mx, my, "L", rots=(0, 90), radius=14)
    for ref in ("R60", "R61", "C84", "R4", "C13", "R2", "R3", "R5", "D2"):
        p.place(ref, mx, my, "L", rots=(0, 90), radius=20)

    # --- CAN channels -------------------------------------------------------------------------
    chans = {1: ("U10", "C1", -1), 2: ("U11", "C2", 1), 3: ("U12", "C3", 1), 4: ("U13", "C4", 1)}
    for n, (u, dom, side) in chans.items():
        i = n - 1
        ux, uy = tm(p.fp[u].GetPosition().x) - O, tm(p.fp[u].GetPosition().y) - O
        bx = ux + side * 9.0
        lx = ux - side * 9.0
        for ref in (f"FB{10 + 2 * i}", f"FB{11 + 2 * i}", f"C{42 + 4 * i}", f"C{43 + 4 * i}",
                    f"D{10 + i}", f"JP{1 + i}", f"R{30 + i}"):
            p.place(ref, bx, uy, dom, rots=(0, 90, 180, 270), radius=16)
        for ref in (f"C{40 + 4 * i}", f"C{41 + 4 * i}", f"R{34 + i}", f"D{20 + i}"):
            p.place(ref, lx, uy, "L", rots=(0, 90), radius=16)
    p.place("F10", 12.0, 36.0, "R", rots=(0, 90))

    # --- RACK: relays (diodes at the PhotoMOS outputs, LEDs below J30), 12 V input -------------
    p.place("F30", 24, 33, "R", rots=(0, 90))
    p.place("C70", 26, 38, "R", rots=(0, 90))
    for ch in range(1, 5):
        p.place(f"D{39 + ch}", 24, 41 + (ch - 1) * 3, "R", rots=(0, 180, 90))
        x = 3 + (ch - 1) * 4.5
        p.place(f"D{43 + ch}", x, 54.0, "R", rots=(90, 270))
        p.place(f"R{54 + ch}", x, 58.0, "R", rots=(90, 270))
    for ref, (x, y) in {"F20": (12, 64), "Q1": (21, 64), "D30": (26, 70), "R40": (18, 72), "D31": (14, 76),
                        "C60": (22, 78), "C61": (16, 82), "C62": (26, 82), "D32": (6, 84), "R41": (6, 88)}.items():
        p.place(ref, x, y, "R", rots=(0, 90, 180, 270))

    # --- LOGIC: supply, Ethernet, I/O ------------------------------------------------------------
    p.place("C63", 40, 74, "L")
    for ref, (x, y) in {"U2": (42, 66), "C1": (38, 61), "C2": (48, 66), "R1": (16, 94), "D1": (21, 94)}.items():
        p.place(ref, x, y, "L", rots=(0, 90, 180, 270))
    for ch in range(1, 5):
        p.place(f"R{50 + ch}", 40, 37 + (ch - 1) * 3, "L", rots=(0, 180))
    for ref in ("Y2", "C30", "C31", "R16"):                       # crystal at XSCI/XSCO (left side, low)
        p.place(ref, 38, 34, "L", rots=(90, 0), radius=12)
    for ref in ("R17", "R18", "R19", "R20", "C32", "C33"):          # MDI termination toward the jack
        p.place(ref, 42, 24, "L", rots=(0, 90), radius=22)
    for ref in ("C20", "C21", "C22", "C23", "C24", "C25", "C26", "C27", "C28", "C29", "FB2", "FB3"):
        p.place(ref, 46, 30, "L", rots=(0, 90), radius=22)
    for ref in ("R10", "R11", "R12", "R13", "R14", "R15"):
        p.place(ref, 52, 34, "L", rots=(0, 90), radius=24)
    for ref in ("FB4", "R21", "C34", "C35", "R22", "R23", "C36"):  # jack centre tap, LEDs, shield
        p.place(ref, 56, 22, "L", rots=(0, 90), radius=20)
    p.place("J3", 32, 8, "L", rots=(90, 0), radius=15)
    for ch in range(1, 5):
        p.place(f"R{70 + ch}", 36 + (ch - 1) * 3.5, 77, "L", rots=(90, 0))
        p.place(f"D{50 + ch}", 36 + (ch - 1) * 3.5, 72, "L", rots=(0, 90))
    for i in range(4):
        for ref in (f"R{80 + i}", f"R{84 + i}", f"C{80 + i}", f"D{55 + i}"):
            p.place(ref, 63 + (i % 2) * 6, 86 + (i // 2) * 6, "L", rots=(90, 0), radius=22)

    b.Save(PCB)
    print("\n".join(p.log) or "all placed near their targets")


if __name__ == "__main__":
    main()
