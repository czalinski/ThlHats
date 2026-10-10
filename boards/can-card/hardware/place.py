#!/usr/bin/env python3
"""Outline, stack holes, placement, pours and keep-outs for the can-card.

Board-local mm (origin = top-left corner, canvas offset (100, 100)).
Floorplan (docs/requirements.md 4.5): J10 (logic bus) on the left edge and
J11 (rack power) on the right edge at the tools/stack_bus.py positions;
LOGIC strip on the left (x < GAP_X - 1); four isolated CAN bands on the right,
top to bottom CAN4, CAN3, the small RACK band around J11 (F10, JP5/JP6), CAN1,
CAN2; each band's ISOW1044 straddles the LOGIC | CAN gap at x = GAP_X and its
MC 1,5/4 terminal sits on the right edge.

TI SLLSFF7B 9.4: no copper within 4 mm of VISOOUT (pin 12) / GND2 (pin 11)
except the channel's own VISO/GND2 parts: a no-fill rule area per channel here
plus a track rule in can-card.kicad_dru.

Rerunnable: redraws the outline, replaces the mounting holes, moves every
footprint and recreates the zones it owns (names starting "D_", "GAP_" or
"KO_"). Tracks are left alone.

  python3 boards/can-card/hardware/place.py
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import stack_bus as sb  # noqa: E402

PCB = str(HW / "can-card.kicad_pcb")
LIB = HW.parents[2] / "lib/footprints"
O = 100.0
FM = pcbnew.FromMM
W, H = sb.BOARD
R = 3.0
E = 0.6                      # pour inset from the board edge
G = 1.0                      # half gap width
GAP_X = 42.0                 # LOGIC | CAN boundary (ISOW1044 centre line)
ISO_X = GAP_X                # ISOW1044 centre x
TERM_X = 91.2                # MC terminal pin column (body to the right edge)
# channel: (ISOW centre y, terminal pin-1 y, band top, band bottom)
BANDS = {4: (15.0, 22.4, 0.0, 25.5), 3: (34.5, 39.3, 25.5, 43.5),
         1: (66.0, 71.3, 57.0, 74.8), 2: (84.0, 88.0, 74.8, 100.0)}
RACK = (43.5, 57.0)          # RACK band (y) on the CAN side, around J11

PLACE = {
    "J10": (sb.BUS_PIN1[0] + sb.PITCH, sb.BUS_PIN1[1], 0, "F"),      # pad 1 = bus pin 2 (socket_pin)
    "J11": (sb.PWR12_PIN1[0] + sb.PITCH, sb.PWR12_PIN1[1], 0, "F"),
    "F10": (84.0, 47.5, 0, "F"),
    "JP6": (70.0, 55.6, 0, "F"),     # V12_F10 (RACK) pin 1 above the gap, V12_CAN1 pin 2 below
    "JP5": (66.0, 58.14, 180, "F"),  # GND_RACK pin 2 above the gap, GND_CAN1 pin 1 below
}


def channel(n):
    """Parts of channel n relative to its ISOW1044 (logic side left, bus side right)."""
    i = n - 1
    yc, ty, _, _ = BANDS[n]
    x = ISO_X
    return {
        f"U{10 + i}": (x, yc, 0),
        # logic side: VIO 100 nF at pin 1, VDD 10 nF at pins 9/10, then 1 uF and 10 uF
        f"C{40 + 4 * i}": (x - 7.6, yc - 5.0, 90),
        f"C{60 + 5 * i}": (x - 7.6, yc + 4.9, 270),
        f"C{61 + 5 * i}": (x - 11.0, yc + 4.9, 270),
        f"C{41 + 4 * i}": (x - 14.4, yc + 4.9, 270),
        # activity LED: +3V3 -> R -> LED -> CnRX
        f"R{34 + i}": (x - 16.0, yc - 3.5, 0),
        f"D{20 + i}": (x - 16.0, yc - 0.5, 180),
        # bus side: VISOOUT/GND2 10 nF at pins 12/11, then 1 uF, 10 uF, beads; VISO pads up and
        # GND2 pads down like the pins, so the two rails run side by side (TI 9.4.1 item 3)
        f"C{62 + 5 * i}": (x + 7.4, yc + 5.0, 270),
        f"C{63 + 5 * i}": (x + 10.6, yc + 5.0, 270),
        f"C{42 + 4 * i}": (x + 14.0, yc + 5.0, 270),
        f"FB{10 + 2 * i}": (x + 19.0, yc + 2.0, 90),     # VISO -> VCAN, pad 1 on the VISO rail
        f"FB{11 + 2 * i}": (x + 21.0, yc + 6.56, 0),     # GND2 -> GND_CAN, pad 1 on the GND2 rail
        # VISOIN 100 nF in line with pin 20 (VCAN pad left, GND_CAN right), clear of the
        # CANH/CANL pins 19/18 just below; the 10 uF sits at the bead's VCAN output
        f"C{43 + 4 * i}": (x + 8.0, yc - 5.715, 0),
        f"C{64 + 5 * i}": (x + 23.1, yc + 0.34, 0),
        f"D{10 + i}": (x + 29.0, yc - 3.5, 0),           # NUP2105L at the bus lines
        f"JP{1 + i}": (x + 34.5, yc - 5.5, 0),           # TERM jumper
        f"R{30 + i}": (x + 39.0, yc - 3.5, 90),          # 120R
        f"J{20 + n}": (TERM_X, ty, 90),                  # MC 1,5/4 (pins vertical, plug from the right)
    }


for _n in BANDS:
    PLACE.update({k: (*v, "F") for k, v in channel(_n).items()})


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
        if f.GetReference().startswith("MH"):
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


def rule_area(b, name, pts, tracks=True, layers=(pcbnew.F_Cu, pcbnew.B_Cu)):
    ls = pcbnew.LSET()
    for lay in layers:
        ls.AddLayer(lay)
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
    for ref, (x, y, rot, side) in PLACE.items():
        f = b.FindFootprintByReference(ref)
        if f is None:
            raise SystemExit(f"{ref} not on the board (run tools/sync_pcb.py)")
        if (side == "B") != f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(FM(O + x), FM(O + y)))
    # JP5 pin 1 (GND_CAN1) reaches its pour only from below the RACK | CAN1 gap: solid, not 1 spoke
    for p in b.FindFootprintByReference("JP5").Pads():
        if p.GetNumber() == "1":
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    missing = [f.GetReference() for f in b.GetFootprints()
               if f.GetReference() not in PLACE and not f.GetReference().startswith(("MH", "TP"))]
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
    lx = GAP_X - G
    rx = GAP_X + G
    for lay, tag in ((pcbnew.B_Cu, ""), (pcbnew.F_Cu, "_F")):
        zone(b, "D_GND" + tag, "GND", lay, rect(E, E, lx - G, H - E))
        for n, (_, _, top, bot) in BANDS.items():
            zone(b, f"D_GND_CAN{n}{tag}", f"/GND_CAN{n}", lay,
                 rect(rx + G, max(top + G, E) if top else E, W - E, min(bot - G, H - E) if bot < H else H - E))
    zone(b, "D_GND_RACK", "/GND_RACK", pcbnew.B_Cu, rect(rx + G, RACK[0] + G, W - E, RACK[1] - G))
    zone(b, "D_12V", "+12V", pcbnew.F_Cu, rect(rx + G, RACK[0] + G, W - E, RACK[1] - G))
    # isolation gaps: LOGIC | CAN (full height), and between the bands on the CAN side
    rule_area(b, "GAP_LOGIC", rect(lx, 0, rx, H))
    for y in (BANDS[4][3], RACK[0], RACK[1], BANDS[1][3]):
        rule_area(b, f"GAP_{y:g}", rect(rx, y - G, W, y + G))
    # TI: no foreign copper within 4 mm of VISOOUT / GND2 (pins 12/11); fills kept out here,
    # tracks of other nets by the rule in can-card.kicad_dru
    for n in BANDS:
        u = b.FindFootprintByReference(f"U{10 + n - 1}")
        pads = [p for p in u.Pads() if p.GetNumber() in ("11", "12")]
        xs = [pcbnew.ToMM(p.GetPosition().x) - O for p in pads]
        ys = [pcbnew.ToMM(p.GetPosition().y) - O for p in pads]
        rule_area(b, f"KO_ISO{n}", rect(min(xs) - 4.0, min(ys) - 4.0, max(xs) + 4.0, max(ys) + 4.0), tracks=False)

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("placed", len(PLACE))


if __name__ == "__main__":
    main()
