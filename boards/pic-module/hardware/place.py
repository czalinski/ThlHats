#!/usr/bin/env python3
"""Outline, placement, pours and keep-outs for pic-module.

Module-local mm (origin = top-left corner, canvas offset (100, 100)); J3/J4
positions come from module_pinout.py. Reruns are safe: it redraws the outline,
moves every footprint to the position below and recreates the zones it owns
(names starting "D_" or "GAP_", plus the old "U20_KEEPOUT"; D_3V3_CORE is
the +3V3 island under U1). Tracks are left alone.

  python3 boards/pic-module/hardware/place.py
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW))
import module_pinout as mp  # noqa: E402

PCB = str(HW / "pic-module.kicad_pcb")
O = 100.0
FM = pcbnew.FromMM
W, H, R = mp.W, mp.H, 2.0
E = 0.6                      # pour inset from the board edge (edge clearance 0.5 mm)
CORE = 4.3                   # half-size of the +3V3 island under U1 (pad inner ends at 4.89)

# ref: (x, y, rot, side)   side "B" = bottom
PLACE = {
    "J3": (*mp.J3_PIN1, 180, "B"),
    "J4": (*mp.J4_PIN1, 180, "B"),
    # RACK: 12 V in -> F20 -> Q1 -> +12V (D31, C60, C61) -> J3.1-8 and U20
    "J20": (20.5, 5.5, 180, "F"),
    "F20": (29.5, 3.0, 0, "F"),
    "Q1": (40.0, 4.5, 180, "F"),
    "D30": (43.0, 11.0, 0, "F"),
    "R40": (43.0, 14.6, 0, "F"),
    "D31": (51.5, 6.5, 90, "F"),
    "C60": (48.5, 14.0, 90, "F"),
    "C61": (52.5, 14.0, 90, "F"),
    "C62": (23.0, 14.2, 90, "F"),
    "R41": (13.0, 13.2, 0, "F"),
    "D32": (18.2, 13.2, 180, "F"),
    "U20": (27.0, 15.2, 0, "F"),         # input row y 15.2 (RACK), output row y 20.28 (LOGIC)
    # LOGIC power
    "C63": (37.5, 21.6, 0, "F"),
    "U2": (41.5, 27.5, 0, "F"),
    "C1": (35.0, 29.0, 90, "F"),
    "C2": (46.0, 34.0, 90, "F"),
    "R1": (13.0, 23.0, 0, "F"),
    "D1": (18.2, 23.0, 180, "F"),
    # MCU and its parts
    "U1": (*mp.MCU_AT, mp.MCU_ROT, "F"),
    "C3": (27.5, 37.2, 0, "F"),          # VDD 10 / VSS 9 (top)
    "C4": (19.3, 46.5, 90, "F"),         # VDD 26 / VSS 25 (left)
    "C5": (36.7, 46.0, 90, "F"),         # VDD 57 / VSS 56 (right)
    "C6": (23.5, 54.75, 90, "F"),         # VDD 38 / VSS 41 (bottom)
    "C7": (20.2, 54.75, 90, "F"),         # VUSB3V3 35
    "C8": (26.5, 34.0, 0, "F"),          # bulk
    "FB1": (15.5, 37.0, 0, "F"),
    "C9": (19.3, 42.5, 90, "F"),
    "C10": (15.5, 42.5, 90, "F"),
    "Y1": (29.5, 56.5, 0, "F"),
    "C11": (27.0, 60.3, 0, "F"),
    "C12": (32.0, 60.3, 0, "F"),
    "R4": (12.5, 52.0, 90, "F"),
    "C13": (15.5, 52.0, 90, "F"),
    "R2": (10.5, 56.0, 0, "F"),
    "R3": (10.5, 59.2, 0, "F"),
    "R5": (40.5, 59.0, 90, "F"),
    "J2": (11.0, 71.0, 90, "F"),          # ICSP, pins along the bottom edge
    "J5": (33.5, 71.0, 90, "F"),         # UART
    "R6": (43.0, 52.0, 0, "F"),
    "D2": (43.0, 55.0, 180, "F"),
}

POURS = {   # name: (net, layer, polygon)
    "D_GND_RACK": ("/GND_RACK", pcbnew.B_Cu, None),
    "D_12V": ("+12V", pcbnew.F_Cu, None),
    "D_GND": ("GND", pcbnew.B_Cu, None),
    "D_GND_F": ("GND", pcbnew.F_Cu, None),
}


def rack_poly(g):
    """RACK region shrunk by g from the gap strips."""
    return [(E, E), (W - E, E), (W - E, mp.GAP_H2[1] - g), (mp.GAP_V[2] + g, mp.GAP_H2[1] - g),
            (mp.GAP_V[2] + g, mp.GAP_H[1] - g), (E, mp.GAP_H[1] - g)]


def logic_poly(g):
    return [(E, mp.GAP_H[3] + g), (mp.GAP_V[0] - g, mp.GAP_H[3] + g), (mp.GAP_V[0] - g, mp.GAP_H2[3] + g),
            (W - E, mp.GAP_H2[3] + g), (W - E, H - E), (E, H - E)]


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

    def arc(c, start, end):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(pcbnew.VECTOR2I(FM(O + c[0]), FM(O + c[1])))
        s.SetStart(pcbnew.VECTOR2I(FM(O + start[0]), FM(O + start[1])))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FM(0.05))
        b.Add(s)

    seg((R, 0), (W - R, 0)); seg((W, R), (W, H - R)); seg((W - R, H), (R, H)); seg((0, H - R), (0, R))
    arc((W - R, R), (W - R, 0), None); arc((W - R, H - R), (W, H - R), None)
    arc((R, H - R), (R, H), None); arc((R, R), (0, R), None)


def main():
    b = pcbnew.LoadBoard(PCB)
    for f in list(b.GetFootprints()):
        if f.GetReference().startswith("MH"):
            b.Delete(f)
    outline(b)
    for ref, (x, y, rot, side) in PLACE.items():
        f = b.FindFootprintByReference(ref)
        if f is None:
            raise SystemExit(f"{ref} not on the board (run tools/sync_pcb.py)")
        if (side == "B") != f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        f.SetOrientationDegrees(rot)
        f.SetPosition(pcbnew.VECTOR2I(FM(O + x), FM(O + y)))
    missing = [f.GetReference() for f in b.GetFootprints() if f.GetReference() not in PLACE]
    if missing:
        print("not placed:", missing)

    for z in list(b.Zones()):
        if z.GetZoneName().startswith(("D_", "GAP_", "U20_KEEPOUT")):
            b.Delete(z)
    shapes = {"D_GND_RACK": rack_poly(1.0), "D_12V": rack_poly(1.0), "D_GND": logic_poly(1.0),
              "D_GND_F": logic_poly(1.0)}
    for name, (net, layer, _) in POURS.items():
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
        poly(z, shapes[name])
        b.Add(z)
    # +3V3 island under U1, inside its pad ring: VDD pins reach it by short inward stubs (route.py)
    z = pcbnew.ZONE(b)
    z.SetZoneName("D_3V3_CORE")
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(b.FindNet("+3V3"))
    z.SetLocalClearance(FM(0.25))
    z.SetMinThickness(FM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetAssignedPriority(2)
    cx, cy = mp.MCU_AT
    poly(z, rect(cx - CORE, cy - CORE, cx + CORE, cy + CORE))
    b.Add(z)
    both = pcbnew.LSET()
    both.AddLayer(pcbnew.F_Cu)
    both.AddLayer(pcbnew.B_Cu)

    def rule_area(name, pts, fills=True):
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

    rule_area("GAP_H", rect(0, mp.GAP_H[1], mp.GAP_H[2], mp.GAP_H[3]))
    rule_area("GAP_V", rect(*mp.GAP_V))
    rule_area("GAP_H2", rect(*mp.GAP_H2))
    # U20 (TRACO: no traces under the converter): pic-module.kicad_dru allows only its own nets there
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("placed", len(PLACE))


if __name__ == "__main__":
    main()
