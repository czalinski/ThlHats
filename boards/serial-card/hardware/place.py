#!/usr/bin/env python3
"""Outline, stack holes, placement, pours, isolation gaps and TI keep-outs for
the serial-card.

Board-local mm (origin = top-left corner, canvas offset (100, 100)).
Floorplan (docs/requirements.md 4.5), parts below the next card (~11 mm):
  - LOGIC: the left side (x < GAP_X - 1). J10 on the left edge; ST3232B (U1)
    in the middle; RS-232 headers J20 on the top edge and J21 on the bottom
    edge (two 21 mm headers do not fit on one edge left of the gap); activity
    LEDs in a column; the logic half of each ISOW1432.
  - RS485_3 (top right) and RS485_4 (bottom right): each ISOW1432 straddles
    the vertical gap at GAP_X; its bus side follows the can-card pattern
    (10 nF / 1 uF / 10 uF rails from pins 12/11, beads), then the SM712, the
    termination jumper and resistor, and the right-angle header on the right
    edge (plug from the right).
  - The band around J11 (rack +12 V passing through from the other cards) has
    no copper: kept away from both isolated sides and LOGIC.
TI SLLSF86D 9.4.1: no copper within 4 mm of VISOOUT (12) / GND2 (11) except
the port's own supply parts: KO_ISO rule areas (no fill) plus the track rule
in serial-card.kicad_dru.

Rerunnable: redraws the outline, replaces the mounting holes, moves every
footprint and recreates the zones it owns ("D_", "GAP_", "KO_"). Tracks stay.

  python3 boards/serial-card/hardware/place.py
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import stack_bus as sb  # noqa: E402

PCB = str(HW / "serial-card.kicad_pcb")
LIB = HW.parents[2] / "lib/footprints"
O = 100.0
FM = pcbnew.FromMM
W, H = sb.BOARD
R = 3.0
E = 0.6                      # pour inset from the board edge
G = 1.0                      # half gap width
GAP_X = 50.0                 # LOGIC | RS-485 boundary (ISOW1432 centre line)
GAP_Y3, GAP_Y4 = 43.0, 57.0  # RS485_3 above GAP_Y3, RS485_4 below GAP_Y4, no copper between (J11)
PORTS = {3: 22.0, 4: 78.0}   # ISOW1432 centre y per port
HDR_X = 85.9                 # right-edge header pin-1 column (mating face at the edge)

PLACE = {
    "J10": (sb.BUS_PIN1[0] + sb.PITCH, sb.BUS_PIN1[1], 0),
    "J11": (sb.PWR12_PIN1[0] + sb.PITCH, sb.PWR12_PIN1[1], 0),
    # RS-232: headers on the top (rot 90, body up) and bottom (rot 270, body down) edges
    "J20": (15.0, 14.1, 90),
    "J21": (25.5, 85.9, 270),
    "U1": (26.0, 50.0, 0),
    "C1": (18.0, 46.8, 90), "C2": (18.0, 52.6, 90),      # charge pump C1+/C1-, C2+/C2-
    "C3": (21.0, 41.0, 0), "C4": (21.0, 58.8, 0),        # VS+, VS-
    "C5": (31.0, 44.0, 90),                              # VCC
    "C6": (14.0, 38.0, 90), "C7": (14.0, 30.0, 90),      # bulk +3V3, +5V at J10
}

# activity LEDs: R (left) and LED (right) per line, a column between U1 and the ISOWs
for _k in range(8):
    _y = 33.0 + 4.3 * _k
    PLACE[f"R{1 + _k}"] = (35.5, _y, 0)
    PLACE[f"D{1 + _k}"] = (41.5, _y, 0)


def port(n):
    """Parts of RS-485 port n relative to its ISOW1432 (logic left, bus right)."""
    i = n - 3
    x, yc = GAP_X, PORTS[n]
    return {
        f"U{10 + i}": (x, yc, 0),
        # logic side: VIO 100 nF at pin 1, VDD 10 nF at pins 9/10, then 1 uF, 10 uF; R pull-up
        f"C{20 + 10 * i}": (x - 7.6, yc - 5.0, 90),
        f"C{21 + 10 * i}": (x - 7.6, yc + 4.9, 270),
        f"C{22 + 10 * i}": (x - 11.0, yc + 4.9, 270),
        f"C{23 + 10 * i}": (x - 14.4, yc + 4.9, 270),
        f"R{20 + i}": (x - 11.5, yc - 1.2, 0),
        # bus side: VISOOUT/GND2 rails from pins 12/11 (10 nF, 1 uF, 10 uF, beads) as on the can-card
        f"C{24 + 10 * i}": (x + 7.4, yc + 5.0, 270),
        f"C{25 + 10 * i}": (x + 10.6, yc + 5.0, 270),
        f"C{26 + 10 * i}": (x + 14.0, yc + 5.0, 270),
        f"FB{10 + 2 * i}": (x + 19.0, yc + 2.0, 90),     # VISO -> V485, pad 1 on the VISO rail
        f"FB{11 + 2 * i}": (x + 21.0, yc + 6.56, 0),     # GND2 -> GND_485, pad 1 on the GND2 rail
        f"C{27 + 10 * i}": (x + 7.6, yc, 90),            # VISOIN (16) / GISOIN (15) 100 nF
        f"C{28 + 10 * i}": (x + 23.1, yc + 0.34, 0),     # 10 uF at the bead's V485 output
        f"D{10 + i}": (x + 27.0, yc - 4.0, 0),           # SM712 on D+/D-
        f"JP{1 + i}": (x + 31.5, yc - 9.5, 0),           # TERM
        f"R{30 + i}": (x + 31.5, yc - 2.5, 90),          # 120R
        f"J{30 + i}": (HDR_X, yc - 7.5, 0),              # right-angle 2x5, pins 5/6 = D+/D-
    }


for _n in PORTS:
    PLACE.update(port(_n))


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
        if f.GetReference().startswith(("MH", "H")) and not any(p.GetNetname() for p in f.Pads()):
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


def rule_area(b, name, pts, tracks=True):
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetLayerSet(ls)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(tracks)
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
        if z.GetZoneName().startswith(("D_", "GAP_", "KO_")):
            b.Delete(z)
    lx, rx = GAP_X - G, GAP_X + G
    for lay, tag in ((pcbnew.B_Cu, ""), (pcbnew.F_Cu, "_F")):
        zone(b, "D_GND" + tag, "GND", lay, rect(E, E, lx - G, H - E))
        zone(b, "D_GND_485_3" + tag, "/GND_485_3", lay, rect(rx + G, E, W - E, GAP_Y3 - 2 * G))
        zone(b, "D_GND_485_4" + tag, "/GND_485_4", lay, rect(rx + G, GAP_Y4 + 2 * G, W - E, H - E))
    rule_area(b, "GAP_LOGIC", rect(lx, 0, rx, H))
    rule_area(b, "GAP_J11", rect(rx, GAP_Y3 - G, W, GAP_Y4 + G))     # rack +12 V pass-through band
    for n in PORTS:
        u = b.FindFootprintByReference(f"U{10 + n - 3}")
        pads = [p for p in u.Pads() if p.GetNumber() in ("11", "12")]
        xs = [pcbnew.ToMM(p.GetPosition().x) - O for p in pads]
        ys = [pcbnew.ToMM(p.GetPosition().y) - O for p in pads]
        rule_area(b, f"KO_ISO{n}", rect(min(xs) - 4.0, min(ys) - 4.0, max(xs) + 4.0, max(ys) + 4.0), tracks=False)

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("placed", len(PLACE))


if __name__ == "__main__":
    main()
