#!/usr/bin/python3
"""can-controller floorplan rev 4 (2026-10-06): reduced scope, no Pi header.

Draws the outline, mounting holes, the edge connectors and the large parts at
their planned positions, plus the domain boundary and block areas, into a
scratch board, and renders it to PNG:

    floorplan_rev4.py OUT_DIR        -> OUT_DIR/floorplan_rev4.{kicad_pcb,pdf,png}

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

W, H, R = 88.0, 76.0, 3.0          # outline, corner radius
OX, OY = 100.0, 100.0
B_X = 66.0                         # 12 V strip boundary (CAN isolators straddle it)
B_Y = 46.0                         # 12 V bottom block boundary (PhotoMOS straddle it)
B_L = 7.5                          # ... left end, clear of MH3 / MH6
NOTCH = (57.0, 58.0)               # boundary steps around MH4 at (61.5, 52.5): x, y

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

    # --- 12 V strip: CAN1-4 down the right edge, ISO1044 straddling x = B_X ----
    can = "PhoenixContact_MC_1,5_4-G-3.5_1x04_P3.50mm_Horizontal"
    iso_y = [10.0, 22.0, 34.0, 46.0]          # all above MH4; CAN4 bus runs down the strip
    for i, top in enumerate([4.5, 22.1, 39.7, 57.3]):
        put(board, "Connector_Phoenix_MC", can, f"J1{i}", 90, right=W, top=top)
        put(board, "Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", f"U1{i}", 0, x=B_X, y=iso_y[i])
        rect(board, D, B_X + 3.8, top + 0.3, W - 11.2, top + 16.3, f"CAN{i + 1}\nbus", size=0.9)

    # --- 12 V bottom block: relays (left) and 12 V input (middle) -----------------
    relay = "PhoenixContact_SPTD_1,5_4-H-3,5_2x04_P3.5mm_Horizontal"
    j30 = put(board, "Thl_Connector", relay, "J30", 0, left=B_L + 1.5, bottom=H)
    for i in range(2):   # dual PhotoMOS: LED pins on the logic side, contacts on the 12 V side
        put(board, "Package_DIP", "DIP-8_W7.62mm", f"K{i + 1}", 90, x=11.0 + 12.0 * i, y=B_Y + 3.8,
            stock=True)
    rect(board, D, B_L + 1.0, B_Y + 5.0, 34.0, H - 19.4, "flyback, LEDs, PTC", size=0.8)
    put(board, "Connector_Phoenix_MSTB", "PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical",
        "J20", 0, left=38.0, bottom=H - 0.5)
    put(board, "Package_TO_SOT_SMD", "TO-252-2", "Q1", 0, x=59.0, y=66.0)
    put(board, "Converter_DCDC", "Converter_DCDC_RECOM_R-78E-0.5_THT", "U20", 0, x=42.0, y=B_Y + 9.0)
    rect(board, D, 35.5, B_Y + 1.0, NOTCH[0] - 0.5, H - 10.5, None)
    rect(board, D, NOTCH[0] - 0.5, NOTCH[1] + 1.0, B_X - 1.0, H - 10.5, None)
    text(board, D, 46.0, H - 12.0, "12 V in: fuse, TVS,\nrev. FET, buck", 0.8)
    put(board, "Package_SO", "SOIC-4_4.55x2.6mm_P1.27mm", "U21", 90, x=50.0, y=B_Y)   # 12 V status

    # --- logic ------------------------------------------------------------------
    put(board, "Connector_USB", "USB_C_Receptacle_GCT_USB4085", "J4", 180, left=20.0, top=0)
    put(board, "Package_TO_SOT_SMD", "SOT-223-3_TabPin2", "U2", 0, x=36.0, y=6.0)
    put(board, "Package_QFP", "TQFP-64_10x10mm_P0.5mm", "U1", 0, x=42.0, y=25.0)
    rect(board, D, 31.0, 14.0, 53.0, 36.0, None)
    text(board, D, 42.0, 37.5, "MCU, crystal, decoupling", 0.8)
    put(board, "Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical", "J2", 90, x=35.0,
        y=41.5)
    io = "PhoenixContact_SPTD_1,5_6-H-3,5_2x06_P3.5mm_Horizontal"
    put(board, "Thl_Connector", io, "J40", -90, left=0, top=10.0)
    rect(board, D, 19.5, 10.0, 29.5, 34.0, "GPIO R/clamps\nAI dividers\nVMID", size=0.8)
    rect(board, D, 54.5, 8.0, 61.0, 40.0, "CAN\nLEDs", size=0.8)

    # --- domain boundary (Cmts.User) -----------------------------------------------
    b = [(B_X, 0), (B_X, NOTCH[1]), (NOTCH[0], NOTCH[1]), (NOTCH[0], B_Y), (B_L, B_Y), (B_L, H)]
    for a, c in zip(b, b[1:]):
        seg(board, C, a, c, 0.4)
    text(board, C, 75.5, 2.0, "12 V", 1.2)
    text(board, C, 40.0, 44.0, "LOGIC (USB)", 1.2)
    text(board, C, 46.0, 72.0, "12 V", 1.2)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    out.mkdir(parents=True, exist_ok=True)
    board = pcbnew.BOARD()
    build(board)
    pcb = out / "floorplan_rev4.kicad_pcb"
    board.Save(str(pcb))
    pdf = out / "floorplan_rev4.pdf"
    subprocess.run(["kicad-cli", "pcb", "export", "pdf", "-o", str(pdf), "--layers",
                    "Edge.Cuts,F.Courtyard,F.Fab,Dwgs.User,Cmts.User", str(pcb)], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "300", "-singlefile", "-cropbox", str(pdf),
                    str(out / "floorplan_rev4")], check=True)
    png = out / "floorplan_rev4.png"
    from PIL import Image, ImageOps            # crop the A4 page to the drawing
    im = Image.open(png).convert("RGB")
    x0, y0, x1, y1 = ImageOps.invert(im).getbbox()
    im.crop((x0 - 20, y0 - 20, x1 + 20, y1 + 20)).save(png)
    print(png)


if __name__ == "__main__":
    main()
