#!/usr/bin/env python3
"""Outline, stack holes, placement, pours and keep-outs for the core board.

Board-local mm (origin = top-left corner, canvas offset (100, 100)). Floorplan
(docs/requirements.md 4.5): stack bus J10 on the left edge and rack power J11
on the right edge at the positions in tools/stack_bus.py (pin headers on the
underside: the core is the top of the stack), RACK strip x > RACK_X on the
right (12 V entry, U20 input side), RJ45 on the bottom edge, right-angle ICSP
and debug UART on the top edge.

Rerunnable: redraws the outline, replaces the mounting holes, moves every
footprint to the position below and recreates the zones it owns (names
starting "D_" or "GAP_"). Tracks are left alone.

  python3 boards/core/hardware/place.py
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import stack_bus as sb  # noqa: E402

PCB = str(HW / "core.kicad_pcb")
LIB = HW.parents[2] / "lib/footprints"
O = 100.0
FM = pcbnew.FromMM
W, H = sb.BOARD
R = 3.0                       # corner radius
E = 0.6                       # pour inset from the board edge
RACK_X = 74.0                 # centre of the RACK | LOGIC gap (2 mm wide)
G = 1.0
MCU_AT = (30.0, 46.0)
CORE = 4.3                    # +3V3 island under U1 (pad inner ends at 4.89)
CORE3 = 2.8                   # 1V2D island under U3, the W6100 (LQFP-48 pad inner ends at about 3.4)

# ref: (x, y, rot, side)
PLACE = {
    # stack connectors (underside); pad 1 lands on stack_bus positions (checked in main)
    "J10": (sb.BUS_PIN1[0] + sb.PITCH, sb.BUS_PIN1[1], 180, "B"),      # pad 1 = bus pin 2 (underside)
    "J11": (sb.PWR12_PIN1[0] + sb.PITCH, sb.PWR12_PIN1[1], 180, "B"),
    # RACK: J20 -> F20 -> Q1 -> +12V (D31, C60-C62) -> J11 and U20
    "J20": (89.4, 19.0, 90, "F"),
    "F20": (81.0, 18.0, 90, "F"),
    "Q1": (88.0, 32.0, 90, "F"),
    "D30": (84.0, 47.0, 0, "F"),
    "R40": (84.0, 51.0, 0, "F"),
    "D31": (84.0, 41.5, 0, "F"),
    "C60": (80.0, 58.0, 90, "F"),
    "C61": (84.0, 58.0, 90, "F"),
    "C62": (77.5, 25.0, 0, "F"),
    "R41": (80.0, 66.0, 0, "F"),
    "D32": (85.0, 66.0, 180, "F"),
    "U20": (76.5, 30.0, 270, "F"),     # input column x 76.5 (RACK), output column x 71.42 (LOGIC)
    # LOGIC supply
    "C63": (65.5, 33.0, 90, "F"),
    "U2": (62.0, 24.0, 0, "F"),
    "C1": (60.0, 32.0, 90, "F"),
    "C2": (55.5, 25.0, 90, "F"),
    "R1": (57.0, 17.0, 0, "F"),
    "D1": (62.0, 17.0, 180, "F"),
    # MCU (rot 270: pins 17-32 face the bus on the left, 49-64 (SPI) face the W6100)
    "U1": (*MCU_AT, 270, "F"),
    "C3": (39.0, 45.5, 90, "F"),        # VDD 57 / VSS 56 (right side)
    "C4": (21.0, 46.5, 90, "F"),        # VDD 26 / VSS 25 (left side)
    "C5": (24.0, 55.5, 0, "F"),         # VDD 38 / VSS 41 (bottom side; OSC 39/40 sit between them)
    "C6": (30.5, 37.5, 0, "F"),         # VDD 10 / VSS 9 (top side)
    "C7": (20.0, 55.5, 0, "F"),       # VUSB3V3 35
    "C8": (35.5, 35.0, 0, "F"),        # bulk
    "FB1": (17.5, 39.0, 90, "F"),
    "C9": (21.0, 41.0, 90, "F"),
    "C10": (14.5, 39.0, 90, "F"),
    "Y1": (29.5, 58.5, 90, "F"),
    "C11": (25.0, 59.5, 90, "F"),
    "C12": (33.8, 60.5, 90, "F"),
    "R4": (25.0, 35.0, 90, "F"),
    "C13": (22.0, 35.0, 90, "F"),
    "R2": (37.5, 56.0, 90, "F"),
    "R3": (40.5, 56.0, 90, "F"),
    "J2": (20.0, 8.0, 90, "F"),        # ICSP, right-angle, pins over the top edge
    "J5": (41.0, 8.0, 90, "F"),        # debug UART
    "R6": (50.0, 13.0, 0, "F"),
    "D2": (55.0, 13.0, 180, "F"),
    "R7": (16.0, 20.0, 90, "F"),
    "R8": (19.0, 20.0, 90, "F"),
    "R60": (14.0, 51.5, 90, "F"),
    "R61": (17.0, 51.5, 90, "F"),
    "C84": (20.0, 51.5, 90, "F"),
    # Ethernet (W6100 above the RJ45 on the bottom edge)
    "U3": (52.0, 62.0, 90, "F"),
    "J4": (38.0, 80.36, 0, "F"),
    "R10": (44.0, 57.0, 90, "F"),
    "R11": (60.5, 52.0, 90, "F"),
    "R12": (63.5, 52.0, 90, "F"),
    "R13": (57.5, 52.0, 90, "F"),
    "FB2": (63.0, 44.0, 0, "F"),
    "FB3": (63.0, 47.5, 0, "F"),
    "C20": (45.5, 66.5, 90, "F"),
    "C21": (58.5, 66.5, 90, "F"),
    "C22": (52.0, 69.0, 0, "F"),
    "C23": (52.0, 55.0, 0, "F"),
    "C24": (45.5, 61.5, 90, "F"),
    "C25": (58.5, 58.5, 90, "F"),
    "C26": (48.0, 53.5, 0, "F"),
    "C27": (61.5, 62.0, 90, "F"),
    "C28": (64.5, 62.0, 90, "F"),
    "C29": (67.5, 62.0, 90, "F"),
    "R14": (62.0, 70.5, 0, "F"),
    "R15": (67.5, 70.5, 0, "F"),
    "Y2": (62.0, 75.0, 0, "F"),
    "R16": (62.0, 79.0, 0, "F"),
    "C30": (56.0, 76.0, 90, "F"),
    "C31": (68.0, 76.0, 90, "F"),
    "R17": (31.0, 70.0, 0, "F"),
    "R18": (31.0, 73.0, 0, "F"),
    "C32": (26.0, 71.5, 90, "F"),
    "R19": (37.0, 70.0, 0, "F"),
    "R20": (37.0, 73.0, 0, "F"),
    "C33": (42.0, 72.0, 90, "F"),
    "FB4": (24.0, 78.0, 0, "F"),
    "R21": (24.0, 81.5, 0, "F"),
    "C34": (20.0, 78.0, 90, "F"),
    "C35": (17.0, 78.0, 90, "F"),
    "R22": (62.0, 86.0, 0, "F"),
    "R23": (62.0, 90.0, 0, "F"),
    "C36": (30.0, 90.0, 90, "F"),
}


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


def zone(b, name, net, layer, pts, prio=0, full=False, clr=0.3):
    z = pcbnew.ZONE(b)
    z.SetZoneName(name)
    z.SetLayer(layer)
    z.SetNet(b.FindNet(net))
    z.SetLocalClearance(FM(clr))
    z.SetMinThickness(FM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if full else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FM(0.4))
    z.SetThermalReliefSpokeWidth(FM(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(prio)
    poly(z, pts)
    b.Add(z)


def rule_area(b, name, pts, fills=True):
    both = pcbnew.LSET()
    both.AddLayer(pcbnew.F_Cu)
    both.AddLayer(pcbnew.B_Cu)
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetLayerSet(both)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(fills)
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
    missing = [f.GetReference() for f in b.GetFootprints()
               if f.GetReference() not in PLACE and not f.GetReference().startswith(("MH", "TP"))]
    if missing:
        print("not placed:", missing)
    # the stack connectors must land exactly on stack_bus positions
    for ref, pos in (("J10", sb.bus_pos), ("J11", sb.pwr12_pos)):
        for p in b.FindFootprintByReference(ref).Pads():
            x, y = pcbnew.ToMM(p.GetPosition().x) - O, pcbnew.ToMM(p.GetPosition().y) - O
            ex, ey = pos(sb.underside(int(p.GetNumber())))
            if abs(x - ex) > 0.01 or abs(y - ey) > 0.01:
                raise SystemExit(f"{ref}.{p.GetNumber()} at ({x:.2f}, {y:.2f}), stack_bus says ({ex:.2f}, {ey:.2f})")

    for z in list(b.Zones()):
        if z.GetZoneName().startswith(("D_", "GAP_")):
            b.Delete(z)
    lo, hi = RACK_X - G, RACK_X + G
    zone(b, "D_GND", "GND", pcbnew.B_Cu, rect(E, E, lo - G, H - E))
    zone(b, "D_GND_F", "GND", pcbnew.F_Cu, rect(E, E, lo - G, H - E))
    zone(b, "D_GND_RACK", "GND_RACK", pcbnew.B_Cu, rect(hi + G, E, W - E, H - E))
    zone(b, "D_12V", "+12V", pcbnew.F_Cu, rect(hi + G, E, W - E, H - E))
    cx, cy = MCU_AT
    zone(b, "D_3V3_CORE", "+3V3", pcbnew.F_Cu, rect(cx - CORE, cy - CORE, cx + CORE, cy + CORE),
         prio=2, full=True, clr=0.25)
    ux, uy = PLACE["U3"][:2]
    zone(b, "D_1V2D_CORE", "/Ethernet/1V2D", pcbnew.F_Cu, rect(ux - CORE3, uy - CORE3, ux + CORE3, uy + CORE3),
         prio=2, full=True, clr=0.25)
    rule_area(b, "GAP_RACK", rect(lo, 0, hi, H))
    # B.Cu GND sliver between J10 pins (hung on a 0.035 mm neck after routing)
    sliver = pcbnew.ZONE(b)
    sliver.SetIsRuleArea(True)
    sliver.SetZoneName("GAP_SLIVER_J10")
    sliver.SetLayer(pcbnew.B_Cu)
    sliver.SetDoNotAllowTracks(False)
    sliver.SetDoNotAllowVias(False)
    sliver.SetDoNotAllowZoneFills(True)
    sliver.SetDoNotAllowPads(False)
    sliver.SetDoNotAllowFootprints(False)
    poly(sliver, rect(8.0, 55.0, 8.9, 56.2))
    b.Add(sliver)

    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("placed", len(PLACE))


if __name__ == "__main__":
    main()
