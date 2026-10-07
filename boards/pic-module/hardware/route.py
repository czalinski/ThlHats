#!/usr/bin/env python3
"""Pre-routing for pic-module, before the autorouter:

- U1 VDD pins (+3V3): 0.3 mm stubs straight inward into the +3V3 island
  under the chip (zone D_3V3_CORE, place.py).
- Ground fanout: every SMD pad on GND / GND_RACK gets a via into its B.Cu
  pour (tools/miniroute.ground_fanout); U1's VSS pins go inward, under the chip.

Not rerun-safe: rerun place.py on a PCB without these tracks first.

  python3 boards/pic-module/hardware/route.py
  tools/freeroute.py boards/pic-module --skip GND /GND_RACK --keep-plane +3V3 \
      --keepout F.Cu:23.7,41.7,32.3,50.3
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
sys.path.insert(0, str(HW))
import miniroute as mr  # noqa: E402
import module_pinout as mp  # noqa: E402

PCB = str(HW / "pic-module.kicad_pcb")


def main():
    b = pcbnew.LoadBoard(PCB)
    u1 = b.FindFootprintByReference("U1")
    c = u1.GetPosition()
    for p in u1.Pads():
        if p.GetNetname() != "+3V3":
            continue
        q = p.GetPosition()
        dx, dy = q.x - c.x, q.y - c.y
        inward = pcbnew.VECTOR2I(q.x - int(dx * 0.27), q.y) if abs(dx) > abs(dy) else \
            pcbnew.VECTOR2I(q.x, q.y - int(dy * 0.27))
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(q)
        t.SetEnd(inward)
        t.SetWidth(pcbnew.FromMM(0.3))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(p.GetNet())
        b.Add(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    mr.ground_fanout(b, ["GND", "/GND_RACK"], mr.Window(0, 0, mp.W, mp.H, mp.W, mp.H), qfp_inward=True)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)


if __name__ == "__main__":
    main()
