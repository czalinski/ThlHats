#!/usr/bin/env python3
"""Routing pipeline for the core board.

  python3 boards/core/hardware/route.py pre      pre-routing (not rerun-safe)
  python3 boards/core/hardware/route.py auto     Freerouting (tools/freeroute.py)
  python3 boards/core/hardware/route.py finish   join what is left, stitch grounds
  python3 boards/core/hardware/route.py all      delete tracks, place.py, pre, auto, finish

pre:
- U1 VDD pins (+3V3): 0.3 mm stubs straight inward into the +3V3 island
  under the chip (zone D_3V3_CORE, place.py); U3 (W6100) 1V2D pins likewise
  into D_1V2D_CORE.
- Escapes to vias (miniroute.pin_escape) for single pins the autorouter
  cannot reach from outside: U1.19 (AVDD), U1.9 (VSS beside a VDD stub),
  U3.4 (1V2A), U3.8 and U3.15 (3V3A).
- Ground fanout: every SMD pad on GND / GND_RACK gets a via into its B.Cu
  pour (miniroute.ground_fanout); QFP VSS pins go inward.
auto: Freerouting with the islands kept as planes and fenced off.
finish: every net still in pieces is joined by miniroute.complete_net with
  temporary keep-outs over the islands (so nothing cuts them), then ground
  pads cut off from their pour get stubs (miniroute.stitch_pads).
"""
import subprocess
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parent
REPO = HW.parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HW))
import miniroute as mr  # noqa: E402
import stack_bus as sb  # noqa: E402
import freeroute  # noqa: E402
import place  # noqa: E402

PCB = str(HW / "core.kicad_pcb")
FM = pcbnew.FromMM
W, H = sb.BOARD
ISLANDS = {   # net: island rectangle (board-local mm), from place.py
    "+3V3": (place.MCU_AT[0] - place.CORE, place.MCU_AT[1] - place.CORE,
             place.MCU_AT[0] + place.CORE, place.MCU_AT[1] + place.CORE),
    "/Ethernet/1V2D": (place.PLACE["U3"][0] - place.CORE3, place.PLACE["U3"][1] - place.CORE3,
                       place.PLACE["U3"][0] + place.CORE3, place.PLACE["U3"][1] + place.CORE3),
}
ESCAPES = (("U1", 19), ("U1", 9), ("U3", 4), ("U3", 8), ("U3", 15))
GROUNDS = ("GND", "GND_RACK")


def vdd_stubs(b, ref, net, frac, width):
    u = b.FindFootprintByReference(ref)
    c = u.GetPosition()
    for p in u.Pads():
        if p.GetNetname() != net:
            continue
        q = p.GetPosition()
        dx, dy = q.x - c.x, q.y - c.y
        end = pcbnew.VECTOR2I(q.x - int(dx * frac), q.y) if abs(dx) > abs(dy) else \
            pcbnew.VECTOR2I(q.x, q.y - int(dy * frac))
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(q)
        t.SetEnd(end)
        t.SetWidth(FM(width))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(p.GetNet())
        b.Add(t)


def pre():
    b = pcbnew.LoadBoard(PCB)
    vdd_stubs(b, "U1", "+3V3", 0.27, 0.3)
    vdd_stubs(b, "U3", "/Ethernet/1V2D", 0.42, 0.25)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    win = mr.Window(0, 0, W, H, W, H)
    for ref, pin in ESCAPES:
        mr.pin_escape(b, ref, pin, win)
    mr.ground_fanout(b, list(GROUNDS), win, qfp_inward=True, verbose=False)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)


def auto():
    keepouts = ["F.Cu:{:.2f},{:.2f},{:.2f},{:.2f}".format(*r) for r in ISLANDS.values()]
    cmd = [sys.executable, str(REPO / "tools/freeroute.py"), str(HW.parent), "--skip", *GROUNDS,
           "--keep-plane", *ISLANDS, "--keepout", *keepouts, "--timeout", "1400", "--passes", "80",
           "--threads", "1"]
    subprocess.run(cmd, check=True)


def width_of(b, net):
    nc = str(b.FindNet(net).GetNetClassName())
    return 0.5 if "Power" in nc and "QFP" not in nc else 0.25 if "QFP" in nc else 0.2


def finish():
    b = pcbnew.LoadBoard(PCB)
    tmp = []
    for x0, y0, x1, y1 in ISLANDS.values():
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetZoneName("TMP_ISLAND")
        z.SetLayer(pcbnew.F_Cu)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(False)
        z.SetDoNotAllowZoneFills(False)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(FM(100 + x), FM(100 + y))
        b.Add(z)
        tmp.append(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    mr.MARGIN = 0.02
    win = mr.Window(0, 0, W, H, W, H)
    names = sorted(str(n) for n in b.GetNetsByName().keys())
    todo = [n for n in names if n and not n.startswith("unconnected") and n not in GROUNDS
            and len(mr._islands(b, b.FindNet(n).GetNetCode())) > 1]
    left = []
    for n in todo:
        ok = mr.complete_net(b, n, width_of(b, n), win, verbose=False)
        print(f"  {'ok  ' if ok else 'FAIL'} {n}", flush=True)
        if not ok:
            left.append(n)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    for z in tmp:
        b.Remove(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    freeroute.fix_vias(b)
    for g in GROUNDS:
        left += mr.stitch_pads(b, g, win, verbose=False)
    b.Save(PCB)
    print("not joined:", " ".join(left) or "-")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "all":
        b = pcbnew.LoadBoard(PCB)
        for t in list(b.GetTracks()):
            b.Delete(t)
        b.Save(PCB)
        place.main()
    if cmd in ("pre", "all"):
        pre()
    if cmd in ("auto", "all"):
        auto()
    if cmd in ("finish", "all"):
        finish()


if __name__ == "__main__":
    main()
