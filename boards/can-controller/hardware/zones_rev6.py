#!/usr/bin/env python3
"""Copper pours and isolation keep-outs for can-controller (floorplan rev 6).

- B.Cu: one ground pour per domain: GND (LOGIC), GND_RACK (RACK), GND_CAN1-4
  (each CAN island). Each pour stays 1 mm back from the domain boundary.
- F.Cu: a +12V pour over the RACK domain (relay feed, CAN1 cable supply, U20 input).
- Rule areas on both layers along every domain boundary (2 mm wide, no tracks,
  vias or pours): only the crossing parts' own pads sit in the gap.
- Rule area under U20 (TRACO: no traces under the converter).

Board-local mm (corner at (100, 100)). Removes and recreates the zones it owns
(names starting "D_" or "GAP_"), so it can be rerun.

  python3 boards/can-controller/hardware/zones_rev6.py
"""
from pathlib import Path

import pcbnew

PCB = str(Path(__file__).resolve().parent / "can-controller.kicad_pcb")
O = 100.0
FM = pcbnew.FromMM
B_C1, B_C1Y, B_R, B_RY, B_X = 24.0, 30.0, 33.0, 90.0, 73.0
GAPS = (39.6, 58.2)
G = 1.0
E = 0.4          # pour inset from the board edge (copper-to-edge 0.3 mm + margin)

POURS = {   # name: (net, layer, polygon)
    "D_GND": ("GND", pcbnew.B_Cu, [(B_C1 + G, E), (B_X - G, E), (B_X - G, 100 - E), (11.5 + G, 100 - E),
                                     (11.5 + G, B_RY + G), (B_R + G, B_RY + G), (B_R + G, B_C1Y + G),
                                     (B_C1 + G, B_C1Y + G)]),
    "D_GND_RACK": ("GND_RACK", pcbnew.B_Cu, [(E, B_C1Y + G), (B_R - G, B_C1Y + G), (B_R - G, B_RY - G),
                                               (11.5 - G, B_RY - G), (11.5 - G, 100 - E), (E, 100 - E)]),
    "D_12V": ("+12V", pcbnew.F_Cu, [(E, B_C1Y + G), (B_R - G, B_C1Y + G), (B_R - G, B_RY - G),
                                     (11.5 - G, B_RY - G), (11.5 - G, 100 - E), (E, 100 - E)]),
    "D_GND_CAN1": ("/CAN x4/GND_CAN1", pcbnew.B_Cu, [(E, E), (B_C1 - G, E), (B_C1 - G, B_C1Y - G), (E, B_C1Y - G)]),
    "D_GND_CAN4": ("/CAN x4/GND_CAN4", pcbnew.B_Cu, [(B_X + G, E), (100 - E, E), (100 - E, GAPS[0] - G),
                                                    (B_X + G, GAPS[0] - G)]),
    "D_GND_CAN3": ("/CAN x4/GND_CAN3", pcbnew.B_Cu, [(B_X + G, GAPS[0] + G), (100 - E, GAPS[0] + G),
                                                    (100 - E, GAPS[1] - G), (B_X + G, GAPS[1] - G)]),
    "D_GND_CAN2": ("/CAN x4/GND_CAN2", pcbnew.B_Cu, [(B_X + G, GAPS[1] + G), (100 - E, GAPS[1] + G),
                                                    (100 - E, 100 - E), (B_X + G, 100 - E)]),
}


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


GAP_AREAS = {    # 2 mm strips centred on the boundaries
    "GAP_C1_L": rect(B_C1 - G, 0, B_C1 + G, B_C1Y + G),
    "GAP_C1_R": rect(0, B_C1Y - G, B_R + G, B_C1Y + G),
    "GAP_R_L": rect(B_R - G, B_C1Y - G, B_R + G, B_RY + G),
    "GAP_R_L2": rect(11.5 - G, B_RY - G, B_R + G, B_RY + G),
    "GAP_R_L3": rect(11.5 - G, B_RY - G, 11.5 + G, 100),
    "GAP_L_CAN": rect(B_X - G, 0, B_X + G, 100),
    "GAP_C4_C3": rect(B_X - G, GAPS[0] - G, 100, GAPS[0] + G),
    "GAP_C3_C2": rect(B_X - G, GAPS[1] - G, 100, GAPS[1] + G),
}


def poly(z, pts):
    o = z.Outline()
    o.RemoveAllContours()
    o.NewOutline()
    for x, y in pts:
        o.Append(FM(O + x), FM(O + y))


def main():
    b = pcbnew.LoadBoard(PCB)
    for z in list(b.Zones()):
        if z.GetZoneName().startswith(("D_", "GAP_", "U20_KEEPOUT")):
            b.Delete(z)
    for name, (net, layer, pts) in POURS.items():
        z = pcbnew.ZONE(b)
        z.SetZoneName(name)
        z.SetLayer(layer)
        ni = b.FindNet(net)
        if ni is None:
            raise SystemExit(f"net {net} not on the board")
        z.SetNet(ni)
        z.SetLocalClearance(FM(0.3))
        z.SetMinThickness(FM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FM(0.4))
        z.SetThermalReliefSpokeWidth(FM(0.5))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(1)
        poly(z, pts)
        b.Add(z)
    gap_layers = pcbnew.LSET()
    gap_layers.AddLayer(pcbnew.F_Cu)
    gap_layers.AddLayer(pcbnew.B_Cu)
    for name, pts in GAP_AREAS.items():
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetZoneName(name)
        z.SetLayerSet(gap_layers)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        poly(z, pts)
        b.Add(z)
    # no traces under the TDN converter (TRACO datasheet)
    u20 = b.FindFootprintByReference("U20")
    bb = u20.GetBoundingBox(False)
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetZoneName("U20_KEEPOUT")
    z.SetLayerSet(gap_layers)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    x0, y0 = pcbnew.ToMM(bb.GetLeft()) - O + 1.0, pcbnew.ToMM(bb.GetTop()) - O + 1.0
    x1, y1 = pcbnew.ToMM(bb.GetRight()) - O - 1.0, pcbnew.ToMM(bb.GetBottom()) - O - 1.0
    poly(z, rect(x0, y0, x1, y1))
    b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("pours", len(POURS), "gap areas", len(GAP_AREAS))


if __name__ == "__main__":
    main()
