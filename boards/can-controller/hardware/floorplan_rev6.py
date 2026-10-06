#!/usr/bin/python3
"""can-controller floorplan rev 6 (2026-10-06): 100 x 100 mm stack interface with can-ssr.

Domains: RACK (12 V DIN supply 0 V: 12 V input, relay outputs, CAN1 bus power),
LOGIC (floating: MCU, W6100, GPIO, AI; fed by an isolated DC-DC from 12 V) and
CAN1-CAN4 (each floating, ISOW1044 with its own isolated supply). Ethernet is
isolated by the jack's magnetics. Stack interface (docs/requirements.md 4.4):
4 x M4 holes on a 91 x 91 mm square, CAN1 at the stack CAN position on the
left edge (pin 1 at y 15.5, 3.5 mm pitch) under each can-ssr's CAN IN/OUT header.

Draws the outline, mounting holes, the edge connectors and the large parts at
their planned positions, plus the domain boundaries and block areas, into a
scratch board, and renders it to PNG:

    floorplan_rev6.py OUT_DIR        -> OUT_DIR/floorplan_rev6.{kicad_pcb,pdf,png}

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

W, H, R = 100.0, 100.0, 3.0        # stack interface outline, corner radius
OX, OY = 100.0, 100.0
CAN_POS = 12.45                    # stack CAN position: pin 1 at y 15.5 -> MC 4-pole courtyard top
CAN_LEN = 16.6                     # MC 1,5/4-G-3,5 courtyard along the edge
B_C1 = 24.0                        # CAN1 island | LOGIC (CAN1's ISOW1044 straddles it)
B_C1Y = 30.0                       # CAN1 island | RACK (POWERED jumper straddles it)
B_R = 33.0                         # RACK | LOGIC (PhotoMOS and DC-DC straddle it)
B_RY = 90.0                        # RACK bottom (LOGIC below, to the J40 corner)
B_X = 75.0                         # LOGIC | CAN2-CAN4 islands (ISOW1044s straddle it)
CAN_R_TOP = [22.0, 40.6, 59.2]     # CAN4, CAN3, CAN2 on the right edge, 2 mm island gaps

HOLES = {"MH1": (4.5, 4.5), "MH2": (95.5, 4.5), "MH3": (4.5, 95.5), "MH4": (95.5, 95.5)}  # 91 x 91

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
        put(board, "Thl_Mechanical", "MountingHole_4.3mm_M4_Standoff7mm", ref, x=x, y=y)
        

    can = "PhoenixContact_MC_1,5_4-G-3.5_1x04_P3.50mm_Horizontal"
    soic20 = "SOIC-20W_7.5x12.8mm_P1.27mm"

    # --- CAN1 at the stack CAN position (left edge), its own island ----------------
    put(board, "Connector_Phoenix_MC", can, "J11", -90, left=0, top=CAN_POS)
    put(board, "Package_SO", soic20, "U11", 180, x=B_C1, y=CAN_POS + CAN_LEN / 2)
    rect(board, D, 11.6, CAN_POS + 0.5, B_C1 - 6.2, CAN_POS + CAN_LEN - 0.5, "CAN1\nbus", size=0.7)
    put(board, "Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical", "JP10", 0,
        x=15.0, y=B_C1Y - 1.27)                 # POWERED: CAN1 ground to RACK 0 V
    put(board, "Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical", "JP11", 0,
        x=19.0, y=B_C1Y - 1.27)                 # POWERED: +12 V through the PTC to pin 4

    # --- RACK (left side): relays, 12 V input, DC-DC to LOGIC -----------------------
    relay = "PhoenixContact_SPTD_1,5_4-H-3,5_2x04_P3.5mm_Horizontal"
    put(board, "Thl_Connector", relay, "J30", -90, left=0, top=33.0)
    for i in range(2):   # dual PhotoMOS: contacts in RACK, LED pins in LOGIC
        put(board, "Package_DIP", "DIP-8_W7.62mm", f"K{i + 1}", 0, x=B_R - 3.81, y=36.0 + 12.0 * i,
            stock=True)
    rect(board, D, 19.8, 32.0, B_R - 5.5, 51.0, "flyback\nLEDs\nPTC", size=0.7)
    put(board, "Connector_Phoenix_MSTB", "PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical",
        "J20", 90, left=0.5, top=56.0)
    put(board, "Package_TO_SOT_SMD", "TO-252-2", "Q1", 0, x=20.0, y=63.0)
    rect(board, D, 11.0, 54.0, B_R - 1.0, B_RY - 2.0, None)
    text(board, D, 21.0, 80.0, "fuse, TVS,\nrev. FET,\nCAN1 PTC", 0.7)
    put(board, "Converter_DCDC", "Converter_DCDC_TRACO_TDN_5-xxxxWI_THT", "U20", 90, x=B_R - 2.55,
        y=72.0, stock=True)                     # in pins in RACK, out pins in LOGIC

    # --- CAN2-CAN4 (right edge), each its own island --------------------------------
    for i, top in enumerate(CAN_R_TOP):
        n = 4 - i
        put(board, "Connector_Phoenix_MC", can, f"J1{n}", 90, right=W, top=top)
        put(board, "Package_SO", soic20, f"U1{n}", 0, x=B_X, y=top + CAN_LEN / 2)
        rect(board, D, B_X + 6.2, top + 0.5, W - 11.2, top + CAN_LEN - 0.5, f"CAN{n}\nbus", size=0.7)
        if i:
            seg(board, C, (B_X, top - 1.0), (W, top - 1.0), 0.4)

    # --- LOGIC ------------------------------------------------------------------------
    put(board, "Thl_Connector", "RJ45_Pulse_JD0-0004NL_Horizontal", "J4", 180, left=40.0, top=0)
    put(board, "Package_QFP", "LQFP-48_7x7mm_P0.5mm", "U3", 0, x=50.0, y=30.0, stock=True)
    text(board, D, 50.0, 36.5, "W6100, 25 MHz", 0.7)
    put(board, "Package_QFP", "TQFP-64_10x10mm_P0.5mm", "U1", 0, x=55.0, y=50.0)
    rect(board, D, 46.0, 41.0, 64.0, 59.0, None)
    text(board, D, 55.0, 60.2, "MCU, crystal", 0.7)
    put(board, "Package_TO_SOT_SMD", "SOT-223-3_TabPin2", "U2", 0, x=42.0, y=63.5)
    put(board, "Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical", "J2", 90, x=64.0,
        y=6.0)
    io = "PhoenixContact_SPTD_1,5_6-H-3,5_2x06_P3.5mm_Horizontal"
    put(board, "Thl_Connector", io, "J40", 0, left=45.0, bottom=H)
    rect(board, D, 45.0, 68.0, 70.0, H - 20.5, "GPIO R/ESD, AI dividers, VMID", size=0.7)
    rect(board, D, 66.0, 20.0, 69.5, 66.0, "CAN\nLEDs", size=0.7)
    rect(board, D, 26.5, 9.0, 32.5, 28.0, "CAN1\nLED", size=0.6)

    # --- domain boundaries (Cmts.User) ----------------------------------------------
    for a, c in [((B_C1, 0), (B_C1, B_C1Y)), ((0, B_C1Y), (B_R, B_C1Y)), ((B_R, B_C1Y), (B_R, B_RY)),
                 ((B_R, B_RY), (11.5, B_RY)), ((11.5, B_RY), (11.5, H)),
                 ((B_X, 0), (B_X, H))]:
        seg(board, C, a, c, 0.4)
    text(board, C, 12.0, 2.5, "CAN1", 1.0)
    text(board, C, 6.0, 52.0, "RACK", 1.0)
    text(board, C, 55.0, 66.0, "LOGIC (floating)", 1.0)
    text(board, C, 87.0, 12.0, "CAN4", 1.0)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    out.mkdir(parents=True, exist_ok=True)
    board = pcbnew.BOARD()
    build(board)
    pcb = out / "floorplan_rev6.kicad_pcb"
    board.Save(str(pcb))
    pdf = out / "floorplan_rev6.pdf"
    subprocess.run(["kicad-cli", "pcb", "export", "pdf", "-o", str(pdf), "--layers",
                    "Edge.Cuts,F.Courtyard,F.Fab,Dwgs.User,Cmts.User", str(pcb)], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-png", "-r", "300", "-singlefile", "-cropbox", str(pdf),
                    str(out / "floorplan_rev6")], check=True)
    png = out / "floorplan_rev6.png"
    from PIL import Image, ImageOps            # crop the A4 page to the drawing
    im = Image.open(png).convert("RGB")
    x0, y0, x1, y1 = ImageOps.invert(im).getbbox()
    im.crop((x0 - 20, y0 - 20, x1 + 20, y1 + 20)).save(png)
    print(png)


if __name__ == "__main__":
    main()
