#!/usr/bin/python3
"""can-controller floorplan rev 5 (2026-10-06): Ethernet, every CAN bus isolated on its own.

Domains: RACK (12 V DIN supply 0 V: 12 V input, relay outputs, CAN1 bus power),
LOGIC (floating: MCU, W6100, GPIO, AI; fed by an isolated DC-DC from 12 V) and
CAN1-CAN4 (each floating, ISOW1044 with its own isolated supply). Ethernet is
isolated by the jack's magnetics.

Draws the outline, mounting holes, the edge connectors and the large parts at
their planned positions, plus the domain boundaries and block areas, into a
scratch board, and renders it to PNG:

    floorplan_rev5.py OUT_DIR        -> OUT_DIR/floorplan_rev5.{kicad_pcb,pdf,png}

The real can-controller.kicad_pcb is not touched; placement reuses the
coordinates below. Board corner at (100, 100) mm like the other boards.
"""
import subprocess
import sys
from pathlib import Path

import pcbnew

REPO = Path(__file__).resolve().parents[3]
FP = REPO / "lib" / "footprints"
STOCK = Path("/usr/share/kicad/footprints")   # only for parts not imported yet (PhotoMOS DIP-6)

W, H, R = 97.0, 79.0, 3.0          # outline, corner radius
OX, OY = 100.0, 100.0
B_X = 71.0                         # LOGIC | CAN islands (ISOW1044s straddle it, clear of MH2/MH4)
B_Y = 50.0                         # LOGIC above | RACK below (PhotoMOS and DC-DC straddle it)
B_L = 7.5                          # RACK block left end, clear of MH3 / MH5
NOTCH = (56.0, 65.5)               # LOGIC notch around MH4 and the CAN1 isolator: x, y
CAN_TOP = [3.8, 22.4, 41.0, 59.6]  # CAN4, CAN3, CAN2, CAN1 (CAN1, the SSR bus, next to RACK)
CAN_LEN = 16.6                     # MC 1,5/4-G-3,5 courtyard along the edge; 2 mm island gaps
ISO_Y = [11.2, 26.7, 42.2, 57.7]   # ISOW1044 centres (13.4 mm courtyards, 2.1 mm island gaps)
BUS_X = W - 14.5                      # islands step here between the isolator and connector rows

HOLES = {  # Pi 58 x 49 pattern + one extra where the outline overhangs the Pi (85 x 56)
    "MH1": (3.5, 3.5), "MH2": (61.5, 3.5), "MH3": (3.5, 52.5), "MH4": (61.5, 52.5),
    "MH5": (3.5, H - 3.5),
}

mm = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def seg(board, layer, a, b, w=0.15):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(mm(w))
    board.Add(s)


def rect(board, layer, x0, y0, x1, y1, label=None, w=0.12, size=1.2):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(P(x0, y0))
    s.SetEnd(P(x1, y1))
    s.SetLayer(layer)
    s.SetWidth(mm(w))
    board.Add(s)
    if label:
        text(board, layer, (x0 + x1) / 2, (y0 + y1) / 2, label, size)


def text(board, layer, x, y, t, size=1.2):
    tx = pcbnew.PCB_TEXT(board)
    tx.SetText(t)
    tx.SetPosition(P(x, y))
    tx.SetLayer(layer)
    tx.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    tx.SetTextThickness(mm(size * 0.12))
    board.Add(tx)


def outline(board):
    L = pcbnew.Edge_Cuts
    for a, b in [((R, 0), (W - R, 0)), ((W, R), (W, H - R)), ((W - R, H), (R, H)), ((0, H - R), (0, R))]:
        seg(board, L, a, b, 0.05)
    for cx, cy, sa in [(R, R, 180), (W - R, R, 270), (W - R, H - R, 0), (R, H - R, 90)]:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(P(cx, cy))
        s.SetStart(P(cx + R * [1, 0, -1, 0][sa // 90], cy + R * [0, 1, 0, -1][sa // 90]))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        s.SetLayer(L)
        s.SetWidth(mm(0.05))
        board.Add(s)


def put(board, lib, name, ref, rot=0, x=None, y=None, left=None, right=None, top=None, bottom=None,
        stock=False):
    """Place a footprint; position by its origin (x, y) or by its courtyard edges."""
    path = (STOCK if stock else FP) / f"{lib}.pretty"
    f = pcbnew.FootprintLoad(str(path), name)
    f.SetReference(ref)
    f.Value().SetVisible(False)
    f.SetOrientationDegrees(rot)
    f.SetPosition(P(x or 0, y or 0))
    board.Add(f)
    cy = f.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
    dx = dy = 0
    if left is not None:
        dx = mm(OX + left) - bb.GetLeft()
    if right is not None:
        dx = mm(OX + right) - bb.GetRight()
    if top is not None:
        dy = mm(OY + top) - bb.GetTop()
    if bottom is not None:
        dy = mm(OY + bottom) - bb.GetBottom()
    f.Move(pcbnew.VECTOR2I(dx, dy))
    return f


def build(board):
    D, C = pcbnew.Dwgs_User, pcbnew.Cmts_User
    outline(board)
    for ref, (x, y) in HOLES.items():
        put(board, "MountingHole", "MountingHole_2.7mm_M2.5", ref, x=x, y=y)

    # --- CAN islands down the right edge: ISOW1044 straddling x = B_X ------------
    can = "PhoenixContact_MC_1,5_4-G-3.5_1x04_P3.50mm_Horizontal"
    for i, top in enumerate(CAN_TOP):
        n = 4 - i
        put(board, "Connector_Phoenix_MC", can, f"J1{n}", 90, right=W, top=top)
        put(board, "Package_SO", "SOIC-20W_7.5x12.8mm_P1.27mm", f"U1{n}", 0, x=B_X, y=ISO_Y[i])
        rect(board, D, BUS_X - 3.0, max(top, ISO_Y[i] - 6.2) + 0.5, W - 11.2,
             min(top + CAN_LEN, ISO_Y[i] + 6.2) - 0.5, f"CAN{n}\nTVS\nterm\nbeads", size=0.7)
        if i:   # island gap: under the isolators, then step to the connector gap
            gi = (ISO_Y[i - 1] + ISO_Y[i]) / 2
            gc = top - 1.0
            for a_, c_ in [((B_X, gi), (BUS_X, gi)), ((BUS_X, gi), (BUS_X, gc)), ((BUS_X, gc), (W, gc))]:
                seg(board, C, a_, c_, 0.4)
    text(board, C, 85.0, 1.6, "CAN4", 1.0)

    # --- RACK block (bottom): relays, 12 V input, DC-DC to LOGIC, CAN1 power ------
    relay = "PhoenixContact_SPTD_1,5_4-H-3,5_2x04_P3.5mm_Horizontal"
    put(board, "Thl_Connector", relay, "J30", 0, left=B_L + 1.5, bottom=H)
    for i in range(2):   # dual PhotoMOS: LED pins in LOGIC, contacts in RACK
        put(board, "Package_DIP", "DIP-8_W7.62mm", f"K{i + 1}", 90, x=24.0 + 12.0 * i, y=B_Y,
            stock=True)
    rect(board, D, 27.5, B_Y + 4.0, 46.0, H - 14.0, "flyback, LEDs,\nrelay PTC", size=0.8)
    put(board, "Connector_Phoenix_MSTB", "PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical",
        "J20", 0, left=30.0, bottom=H - 0.5)
    put(board, "Package_TO_SOT_SMD", "TO-252-2", "Q1", 0, x=52.0, y=69.0)
    rect(board, D, 46.5, NOTCH[1] + 0.5, B_X - 0.5, H - 1.0, None)
    text(board, D, 62.0, 67.5, "fuse, TVS, rev. FET,\nCAN1 PTC, POWERED", 0.6)
    put(board, "Converter_DCDC", "Converter_DCDC_TRACO_TDN_5-xxxxWI_THT", "U20", 180, x=51.5,
        y=B_Y + 2.55, stock=True)              # in pins in RACK, out pins in LOGIC
    put(board, "Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical", "JP10", 0,
        x=B_X - 1.27, y=H - 7.0)                # CAN1 POWERED: ground tie, straddles RACK | CAN1

    # --- LOGIC ------------------------------------------------------------------
    put(board, "Connector_RJ", "RJ45_Hanrun_HR911105A_Horizontal", "J4", 180, left=8.0, top=0,
        stock=True)
    put(board, "Package_QFP", "LQFP-48_7x7mm_P0.5mm", "U3", 0, x=34.0, y=11.0, stock=True)
    rect(board, D, 28.5, 5.5, 40.0, 20.0, None)
    text(board, D, 34.0, 21.2, "W6100, 25 MHz", 0.7)
    put(board, "Package_QFP", "TQFP-64_10x10mm_P0.5mm", "U1", 0, x=49.0, y=28.0)
    rect(board, D, 41.0, 18.0, 57.0, 38.0, None)
    text(board, D, 49.0, 39.2, "MCU, crystal", 0.7)
    put(board, "Package_TO_SOT_SMD", "SOT-223-3_TabPin2", "U2", 90, x=34.5, y=27.5)
    put(board, "Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical", "J2", 90, x=41.0,
        y=3.0)
    io = "PhoenixContact_SPTD_1,5_6-H-3,5_2x06_P3.5mm_Horizontal"
    put(board, "Thl_Connector", io, "J40", -90, left=0, top=24.0)
    rect(board, D, 19.5, 24.0, 29.0, 47.5, "GPIO R/ESD\nAI dividers\nVMID", size=0.7)
    rect(board, D, 58.0, 8.0, 64.0, 48.0, "CAN\nLEDs", size=0.7)

    # --- domain boundaries (Cmts.User) ----------------------------------------------
    seg(board, C, (B_X, 0), (B_X, H), 0.4)
    b = [(B_X, NOTCH[1]), (NOTCH[0], NOTCH[1]), (NOTCH[0], B_Y), (B_L, B_Y), (B_L, H)]
    for a, c in zip(b, b[1:]):
        seg(board, C, a, c, 0.4)
    text(board, C, 30.0, 2.0, "LOGIC (floating)", 1.0)
    text(board, C, 14.0, 56.0, "RACK\n12 V", 1.0)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    out.mkdir(parents=True, exist_ok=True)
    board = pcbnew.BOARD()
    build(board)
    pcb = out / "floorplan_rev5.kicad_pcb"
    board.Save(str(pcb))
    pdf = out / "floorplan_rev5.pdf"
    subprocess.run(["kicad-cli", "pcb", "export", "pdf", "-o", str(pdf), "--layers",
                    "Edge.Cuts,F.Courtyard,F.Fab,Dwgs.User,Cmts.User", str(pcb)], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "300", "-singlefile", "-cropbox", str(pdf),
                    str(out / "floorplan_rev5")], check=True)
    png = out / "floorplan_rev5.png"
    from PIL import Image, ImageOps            # crop the A4 page to the drawing
    im = Image.open(png).convert("RGB")
    x0, y0, x1, y1 = ImageOps.invert(im).getbbox()
    im.crop((x0 - 20, y0 - 20, x1 + 20, y1 + 20)).save(png)
    print(png)


if __name__ == "__main__":
    main()
