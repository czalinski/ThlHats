#!/usr/bin/env python3
"""Outline, holes, placement, pours and silkscreen for the probe-helper.

Board-local mm, origin = top-left corner of the outline's bounding box (canvas
offset (100, 100)). Seen from the top in the Pi's standard view (40-pin
header at the top): x as on the Pi and the AD HAT; local y = Pi y - 22.5.

Mechanics (Waveshare High-Precision AD HAT 3D/DXF, 2026-02-26):
  - The HAT is 65 x 30.5 mm, holes 58 x 23 mm: its header-side holes are on
    the Pi's (3.5, 3.5) / (61.5, 3.5), its terminal-side holes at Pi y 26.5,
    its terminal edge at Pi y 30.0.
  - 13-way 3.5 mm screw terminal centred on the HAT (x 9.75-55.25), wire
    entries facing away from the header, face 0.49 mm inside the HAT edge
    (Pi y 29.51), screws 3.4 mm behind the face, body 6.9 mm deep, 8.8 mm
    tall.
  - This board sits above the HAT (on about 4 mm spacers at the tabs) so that
    J1, soldered on the bottom side, has its pins at the height of the wire
    entries. J1's pins (2.54 mm right-angle pins: body 1.5-4.04 mm from the
    hole, tip at 10.04 mm) reach 5 mm into the terminal: holes at Pi y 34.55.
  - Tabs (8 x 8 mm) reach over the HAT's terminal-side holes (MH1, MH2) and
    stay 1.75 mm clear of the terminal body; the notch between them is at Pi
    y 30.5 (J1's plastic bodies end there).
  - MH3/MH4 on the Pi's far holes (Pi y 52.5): standoffs to the Pi.

Rerunnable: redraws the outline, replaces the mounting holes, moves every
footprint, recreates the zones it owns ("D_") and its silkscreen texts.
Tracks stay.

  python3 boards/probe-helper/hardware/place.py
"""
import math
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
PCB = str(HW / "probe-helper.kicad_pcb")
LIB = HW.parents[2] / "lib/footprints"
O = 100.0
FM = pcbnew.FromMM
W, H = 65.0, 46.0
DY = 22.5                    # Pi y of local y = 0
TAB_W, NOTCH_Y = 8.0, 8.0    # tabs x 0-8 and 57-65, y 0-8; notch edge at y 8
E = 0.5                      # pour inset from the edge
HOLES = [(3.5, 26.5 - DY), (61.5, 26.5 - DY), (3.5, 52.5 - DY), (61.5, 52.5 - DY)]
J1_Y = 34.55 - DY            # J1 hole row
J1_X0 = 32.5 - 6 * 3.5       # J1 pin 1 (AVDD) x
TOP, BOT = 15.6, 15.6 + 10.16    # first row of vertical resistors: top / bottom pad y
TOP2 = 29.3                      # second row: top pad y

# ref: (x, y, rotation, side). Axial footprints: pad 1 at (x, y); rot 270 puts
# pad 2 below pad 1, rot 90 above.
PLACE = {
    "J1": (J1_X0, J1_Y, 0, "B"),
    # under J1: sense / IDAC leads (pad 1 at the J1 pin, pad 2 = probe node)
    "R14": (18.5, TOP, 270, "F"), "R15": (22.0, TOP, 270, "F"),    # SENSE_B, IDAC_B
    "R10": (25.5, TOP, 270, "F"), "R11": (29.0, TOP, 270, "F"),    # SENSE_A, IDAC_A
    # sources: node N on the top pads; 1.2k (pad 2 = N), reference, 47R
    "R1": (32.5, BOT, 90, "F"), "R7": (36.0, TOP, 270, "F"), "R4": (39.5, TOP, 270, "F"),
    "R2": (43.0, BOT, 90, "F"), "R8": (46.5, TOP, 270, "F"), "R5": (50.0, TOP, 270, "F"),
    "R3": (53.5, BOT, 90, "F"), "R9": (57.0, TOP, 270, "F"), "R6": (60.5, TOP, 270, "F"),
    # probe B node (left): NODE_B on the top pads
    "R17": (4.5, TOP, 270, "F"),                 # 22R: NODE_B, PROBE_B below
    "R16": (8.0, BOT, 90, "F"),                  # 470R: GPIO6 below, NODE_B on top
    "D3": (11.5, TOP + 7.62, 90, "F"),           # K (+5V) below, A (NODE_B) on top
    "D4": (15.0, TOP, 270, "F"),                 # K (NODE_B) on top, A (GND) below
    # probe A node: NODE_A on the top pads of the second row
    "D2": (22.0, TOP2, 270, "F"),                # K (NODE_A) on top, A (GND) below
    "R12": (25.5, TOP2 + 10.16, 90, "F"),        # 470R: GPIO12 below, NODE_A on top
    "R13": (29.0, TOP2, 270, "F"),               # 22R: NODE_A, PROBE_A below
    "D1": (32.5, TOP2 + 7.62, 90, "F"),          # K (+5V) below, A (NODE_A) on top
    # probe leads (entries facing the bottom edge) and the ribbon to the Pi
    "J3": (9.0, 40.6, 0, "F"),
    "J2": (42.0, 40.5, 90, "F"),
}

SILK = [  # (text, x, y, size, rotation)
    ("PROBE HELPER rev A", 27.2, 44.6, 1.0, 0),
    ("ADS1263 AD HAT adapter", 46.5, 28.4, 0.8, 0),
    ("J1 ON BOTTOM", 5.2, 11.0, 0.8, 0),
    ("J2: RIBBON TO HAT PI PINS 31-40", 46.5, 30.0, 0.8, 0),
    ("J2 PIN 1 = PI PIN 31", 46.5, 31.6, 0.8, 0),
    ("A RED", 9.0, 34.4, 0.8, 0),
    ("B BLACK", 14.6, 34.4, 0.8, 0),
]
REF_AT = {"J1": (32.5, 13.9), "J2": (33.9, 39.2), "J3": (3.4, 40.6)}   # silkscreen references placed here
J1_NAMES = ["AVDD", "AVSS", "IN0", "IN1", "IN2", "IN3", "IN4", "IN5", "IN6", "IN7", "IN8", "IN9", "COM"]


def V(x, y):
    return pcbnew.VECTOR2I(FM(O + x), FM(O + y))


def outline(b):
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts or d.GetClass() == "PCB_TEXT":
            b.Delete(d)

    def seg(a, c):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a))
        s.SetEnd(V(*c))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FM(0.05))
        b.Add(s)

    def arc(a, m, c):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(V(*a), V(*m), V(*c))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FM(0.05))
        b.Add(s)

    def corner(cx, cy, r, a0, a1):
        """Arc around (cx, cy) from angle a0 to a1 (degrees, y down)."""
        pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
               for a in (a0, (a0 + a1) / 2, a1)]
        arc(*pts)

    R3, R1 = 3.0, 1.0
    L, RX = TAB_W, W - TAB_W
    # clockwise from the left tab
    corner(R3, R3, R3, 180, 270)
    seg((R3, 0), (L - R1, 0))
    corner(L - R1, R1, R1, 270, 360)
    seg((L, R1), (L, NOTCH_Y - R1))
    corner(L + R1, NOTCH_Y - R1, R1, 180, 90)          # concave
    seg((L + R1, NOTCH_Y), (RX - R1, NOTCH_Y))
    corner(RX - R1, NOTCH_Y - R1, R1, 90, 0)           # concave
    seg((RX, NOTCH_Y - R1), (RX, R1))
    corner(RX + R1, R1, R1, 180, 270)
    seg((RX + R1, 0), (W - R3, 0))
    corner(W - R3, R3, R3, 270, 360)
    seg((W, R3), (W, H - R3))
    corner(W - R3, H - R3, R3, 0, 90)
    seg((W - R3, H), (R3, H))
    corner(R3, H - R3, R3, 90, 180)
    seg((0, H - R3), (0, R3))


def holes(b):
    for f in list(b.GetFootprints()):
        if f.GetReference().startswith("MH"):
            b.Delete(f)
    for i, (x, y) in enumerate(HOLES, 1):
        f = pcbnew.FootprintLoad(str(LIB / "MountingHole.pretty"), "MountingHole_2.7mm_M2.5")
        f.SetFPID(pcbnew.LIB_ID("MountingHole", "MountingHole_2.7mm_M2.5"))
        f.SetReference(f"MH{i}")
        f.SetPosition(V(x, y))
        b.Add(f)


def zone(b, name, net, layer, pts):
    z = pcbnew.ZONE(b)
    z.SetZoneName(name)
    z.SetLayer(layer)
    z.SetNet(b.FindNet(net))
    z.SetLocalClearance(FM(0.4))
    z.SetMinThickness(FM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FM(0.5))
    z.SetThermalReliefSpokeWidth(FM(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.RemoveAllContours()
    o.NewOutline()
    for x, y in pts:
        o.Append(FM(O + x), FM(O + y))
    b.Add(z)


def text(b, s, x, y, size, rot=0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetPosition(V(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(FM(size), FM(size)))
    t.SetTextThickness(FM(0.15 if size >= 0.8 else 0.12))
    t.SetTextAngleDegrees(rot)
    b.Add(t)


def main():
    b = pcbnew.LoadBoard(PCB)
    outline(b)
    holes(b)
    for ref, (x, y, rot, side) in PLACE.items():
        f = b.FindFootprintByReference(ref)
        if f is None:
            raise SystemExit(f"{ref} not on the board (run tools/sync_pcb.py)")
        if (side == "B") != f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        f.SetOrientationDegrees(rot)
        f.SetPosition(V(x, y))
        if ref[0] in "RD":   # reference inside the body outline, along the body
            pads = list(f.Pads())
            c = (pads[0].GetPosition() + pads[1].GetPosition()) / 2
            t = f.Reference()
            t.SetPosition(pcbnew.VECTOR2I(int(c.x), int(c.y)))
            t.SetTextAngleDegrees(90 if rot in (90, 270) else 0)
            t.SetTextSize(pcbnew.VECTOR2I(FM(0.8), FM(0.8)))
            t.SetTextThickness(FM(0.15))
        if ref in REF_AT:
            t = f.Reference()
            t.SetPosition(V(*REF_AT[ref]))
            t.SetTextAngleDegrees(0)
        if ref[0] == "D":   # the cathode band marks polarity; the "K" text collides with the next column
            for g in f.GraphicalItems():
                if g.GetClass() == "PCB_TEXT" and g.GetText() == "K" and g.GetLayer() == pcbnew.F_SilkS:
                    g.SetLayer(pcbnew.F_Fab)
    missing = [f.GetReference() for f in b.GetFootprints()
               if f.GetReference() not in PLACE and not f.GetReference().startswith(("MH", "TP"))]
    if missing:
        print("not placed:", missing)
    # J1: pad k at x = J1_X0 + 3.5 (k - 1), pins pointing to the HAT (-y)
    j1 = b.FindFootprintByReference("J1")
    for p in j1.Pads():
        x = pcbnew.ToMM(p.GetPosition().x) - O
        ex = J1_X0 + 3.5 * (int(p.GetNumber()) - 1)
        if abs(x - ex) > 0.01:
            raise SystemExit(f"J1.{p.GetNumber()} at x {x:.2f}, expected {ex:.2f}")
    crt = j1.GetCourtyard(pcbnew.B_CrtYd).BBox()
    if pcbnew.ToMM(crt.GetY()) - O > J1_Y - 5:
        raise SystemExit("J1 pins do not point to -y")

    for z in list(b.Zones()):
        if z.GetZoneName().startswith("D_"):
            b.Delete(z)
    body = [(E, NOTCH_Y + E), (W - E, NOTCH_Y + E), (W - E, H - E), (E, H - E)]
    zone(b, "D_GND", "GND", pcbnew.B_Cu, body)
    zone(b, "D_GND_F", "GND", pcbnew.F_Cu, body)

    for s, x, y, size, rot in SILK:
        text(b, s, x, y, size, rot)
    for i, name in enumerate(J1_NAMES):
        text(b, name, J1_X0 + 3.5 * i, J1_Y - 2.2, 0.8, 0)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("placed", len(PLACE))


if __name__ == "__main__":
    main()
