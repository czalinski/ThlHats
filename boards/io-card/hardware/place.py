#!/usr/bin/env python3
"""Outline, stack holes, placement, pours and isolation gap for the io-card.

Board-local mm (origin = top-left corner, canvas offset (100, 100)).
Floorplan (docs/requirements.md 4.5), stack parts below the next card (about
11 mm, ESQ-120-14 body):
  - J10 (logic bus) on the left edge, J11 (rack power) on the right edge, at
    the tools/stack_bus.py positions.
  - LOGIC: the top band and the left side. J40 (MC 1,5/12, I/O) on the TOP
    edge with the GPIO clamps and AI dividers behind it; the 10M resistors
    sit right at the AI terminals (high-voltage nets kept short, 0.8 mm
    clearance in io-card.kicad_dru).
  - RACK: the lower-right block (x > GAP_X, y > GAP_Y) with J11, the coil
    supply (JP1, F30, C70/C71) beside J11 and J30 (MC 1,5/10, relay
    outputs) on the BOTTOM edge, each output's flyback diode and LED in a
    column behind its terminal pair.
  - K1/K2 (AQW212) straddle the vertical gap: LED pins 1-4 LOGIC, contact
    pins 5-8 RACK. The 2 mm gap is copper-free on both layers.
J30 does not fit on the right edge: between J11 and the corner standoff it
is 0.2 mm too long.

Rerunnable: redraws the outline, replaces the mounting holes, moves every
footprint and recreates the zones it owns ("D_", "GAP_"). Tracks stay.

  python3 boards/io-card/hardware/place.py
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import stack_bus as sb  # noqa: E402

PCB = str(HW / "io-card.kicad_pcb")
LIB = HW.parents[2] / "lib/footprints"
O = 100.0
FM = pcbnew.FromMM
W, H = sb.BOARD
R = 3.0
E = 0.6                      # pour inset from the board edge
G = 1.0                      # half gap width
GAP_X, GAP_Y = 46.0, 41.0    # RACK = x > GAP_X and y > GAP_Y
EDGE_PIN = 8.8               # MC header pin row from the board edge (body front at the edge)

KX = GAP_X - 3.81            # AQW212 pin-1 column: the gap runs between the pin columns
J30_X1 = 53.0                # J30 pad 1 x (bottom edge, pads to the right)
J40_X1 = 56.0                # J40 pad 1 x (top edge, rotated 180: pads to the left)

PLACE = {
    "J10": (sb.BUS_PIN1[0] + sb.PITCH, sb.BUS_PIN1[1], 0),      # pad 1 = bus pin 2 (socket_pin)
    "J11": (sb.PWR12_PIN1[0] + sb.PITCH, sb.PWR12_PIN1[1], 0),
    "J30": (J30_X1, H - EDGE_PIN, 0),
    "J40": (J40_X1, EDGE_PIN, 180),
    "K1": (KX, 47.0, 0),
    "K2": (KX, 60.0, 0),
    # LED resistors on the LOGIC side, in line with K pins 1 and 3
    "R51": (35.5, 47.0, 0), "R52": (35.5, 52.08, 0),
    "R53": (35.5, 60.0, 0), "R54": (35.5, 65.08, 0),
    # coil supply next to J11: +12V -> JP1 (1-2 rack / 2-3 external) -> F30 -> V_RLY
    "C71": (86.5, 44.5, 0),
    "JP1": (80.5, 46.0, 0),
    "F30": (72.5, 48.54, 180),
    "C70": (64.0, 48.54, 0),
    # logic decoupling at J10's +3V3 pin
    "C1": (12.5, 44.0, 90), "C2": (15.5, 44.0, 90),
}

for _n in range(1, 5):
    xc = J30_X1 + 7.0 * (_n - 1) + 1.75          # between OUTn and its 0 V pad
    PLACE[f"D{39 + _n}"] = (xc - 2.0, 79.0, 90)  # flyback, pad 1 (OUTn) towards J30
    PLACE[f"R{54 + _n}"] = (xc + 1.6, 72.0, 270)
    PLACE[f"D{43 + _n}"] = (xc + 1.6, 79.0, 90)  # LED: anode up (R), cathode down (GND_RACK)
    # GPIO n: pads 2n-1 (IOn) / 2n (GND) of J40, x decreasing (rotated 180)
    xio = J40_X1 - 7.0 * (_n - 1)
    PLACE[f"R{70 + _n}"] = (xio, 15.0, 90)       # pad 2 (IOn) up to the terminal
    PLACE[f"D{50 + _n}"] = (xio - 1.5, 21.0, 0)

# AI: 10M at the terminal (pads 9-12, staggered for the high-voltage spacing), then
# per leg 130k + 100 nF to VMID and the BAT54S clamp in a row behind the GPIO block
for _i in range(4):
    xa = J40_X1 - 3.5 * (8 + _i)
    PLACE[f"R{80 + _i}"] = (xa, 15.0 if _i % 2 == 0 else 19.5, 270)   # pad 1 (AINxx) up
    bx = 13.0 + 10.5 * (3 - _i)                 # leg blocks in the same order as their 10M
    PLACE[f"R{84 + _i}"] = (bx, 31.0, 90)
    PLACE[f"C{80 + _i}"] = (bx + 3.0, 31.0, 90)
    PLACE[f"D{55 + _i}"] = (bx + 7.0, 31.0, 0)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def poly(z, pts):
    o = z.Outline()
    o.RemoveAllContours()
    o.NewOutline()
    for x, y in pts:
        o.Append(FM(O + x), FM(O + y))


def outline(b):
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts or d.GetClass() == "PCB_TEXT":
            b.Delete(d)

    def seg(a, c):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(FM(O + a[0]), FM(O + a[1])))
        s.SetEnd(pcbnew.VECTOR2I(FM(O + c[0]), FM(O + c[1])))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FM(0.05))
        b.Add(s)

    def arc(c, start):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(pcbnew.VECTOR2I(FM(O + c[0]), FM(O + c[1])))
        s.SetStart(pcbnew.VECTOR2I(FM(O + start[0]), FM(O + start[1])))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FM(0.05))
        b.Add(s)

    seg((R, 0), (W - R, 0)); seg((W, R), (W, H - R)); seg((W - R, H), (R, H)); seg((0, H - R), (0, R))
    arc((W - R, R), (W - R, 0)); arc((W - R, H - R), (W, H - R))
    arc((R, H - R), (R, H)); arc((R, R), (0, R))


def holes(b):
    for f in list(b.GetFootprints()):
        if f.GetReference().startswith(("MH", "H")) and not f.GetReference().startswith("HS") \
                and not any(p.GetNetname() for p in f.Pads()):
            b.Delete(f)
    for i, (x, y) in enumerate(sb.HOLES, 1):
        f = pcbnew.FootprintLoad(str(LIB / "Thl_Mechanical.pretty"), "MountingHole_4.3mm_M4_Standoff7mm")
        f.SetFPID(pcbnew.LIB_ID("Thl_Mechanical", "MountingHole_4.3mm_M4_Standoff7mm"))
        f.SetReference(f"MH{i}")
        f.SetPosition(pcbnew.VECTOR2I(FM(O + x), FM(O + y)))
        b.Add(f)


def zone(b, name, net, layer, pts):
    z = pcbnew.ZONE(b)
    z.SetZoneName(name)
    z.SetLayer(layer)
    z.SetNet(b.FindNet(net))
    z.SetLocalClearance(FM(0.3))
    z.SetMinThickness(FM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FM(0.4))
    z.SetThermalReliefSpokeWidth(FM(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    poly(z, pts)
    b.Add(z)


def rule_area(b, name, pts):
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    poly(z, pts)
    b.Add(z)


def main():
    b = pcbnew.LoadBoard(PCB)
    outline(b)
    holes(b)
    for ref, (x, y, rot) in PLACE.items():
        f = b.FindFootprintByReference(ref)
        if f is None:
            raise SystemExit(f"{ref} not on the board (run tools/sync_pcb.py)")
        if f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(FM(O + x), FM(O + y)))
    missing = [f.GetReference() for f in b.GetFootprints()
               if f.GetReference() not in PLACE and not f.GetReference().startswith("MH")]
    if missing:
        print("not placed:", missing)
    for ref, pos in (("J10", sb.bus_pos), ("J11", sb.pwr12_pos)):
        for p in b.FindFootprintByReference(ref).Pads():
            x, y = pcbnew.ToMM(p.GetPosition().x) - O, pcbnew.ToMM(p.GetPosition().y) - O
            ex, ey = pos(sb.socket_pin(int(p.GetNumber())))
            if abs(x - ex) > 0.01 or abs(y - ey) > 0.01:
                raise SystemExit(f"{ref}.{p.GetNumber()} at ({x:.2f}, {y:.2f}), stack_bus says ({ex:.2f}, {ey:.2f})")

    for z in list(b.Zones()):
        if z.GetZoneName().startswith(("D_", "GAP_")):
            b.Delete(z)
    gx0, gx1, gy0, gy1 = GAP_X - G, GAP_X + G, GAP_Y - G, GAP_Y + G
    logic = [(E, E), (W - E, E), (W - E, gy0), (gx0, gy0), (gx0, H - E), (E, H - E)]
    rack = rect(gx1, gy1, W - E, H - E)
    for lay, tag in ((pcbnew.B_Cu, ""), (pcbnew.F_Cu, "_F")):
        zone(b, "D_GND" + tag, "GND", lay, logic)
        zone(b, "D_GND_RACK" + tag, "/GND_RACK", lay, rack)
    rule_area(b, "GAP_V", rect(gx0, gy0, gx1, H))
    rule_area(b, "GAP_H", rect(gx0, gy0, W, gy1))

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("placed", len(PLACE))


if __name__ == "__main__":
    main()
