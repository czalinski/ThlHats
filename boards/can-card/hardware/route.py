#!/usr/bin/env python3
"""Routing pipeline for the can-card (same scheme as boards/core/hardware/route.py).

  python3 boards/can-card/hardware/route.py pre      pre-routing (not rerun-safe)
  python3 boards/can-card/hardware/route.py auto     Freerouting (tools/freeroute.py)
  python3 boards/can-card/hardware/route.py finish   join what is left, stitch grounds
  python3 boards/can-card/hardware/route.py all      delete tracks, place.py, pre, auto, finish

pre:
- ISOW1044 GISOIN pin 15 sits inside the TI 4 mm keep-out (no pour there):
  a stub joins it to pin 16 just above.
- VISOOUT / GND2 rails (TI SLLSFF7B 9.4.1): pin 12 + 13 -> 10 nF -> 1 uF ->
  10 uF -> bead FB(2i+10) on top, pin 11 -> the same caps -> bead FB(2i+11)
  below it, side by side on F.Cu, so the router never comes near pins 11/12.
- VCAN: pin 20 -> 100 nF on F.Cu, then over the CANH/CANL pair on B.Cu (via
  above the cap, via above the bead) to bead FB(2i+10) and the 10 uF beside it.
- Ground fanout: every SMD pad on a ground net gets a via into its pour.
auto: Freerouting; grounds are pours (both layers per domain, place.py).
finish: every net still in pieces is joined by miniroute.complete_net, then
  ground pads cut off from their pour get stubs (miniroute.stitch_pads).
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

PCB = str(HW / "can-card.kicad_pcb")
FM = pcbnew.FromMM
W, H = sb.BOARD
GROUNDS = ("GND", "/GND_RACK", "/GND_CAN1", "/GND_CAN2", "/GND_CAN3", "/GND_CAN4")


def gisoin_stubs(b):
    for i in range(4):
        u = b.FindFootprintByReference(f"U{10 + i}")
        p15, p16 = (next(p for p in u.Pads() if p.GetNumber() == n) for n in ("15", "16"))
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(p15.GetPosition())
        t.SetEnd(p16.GetPosition())
        t.SetWidth(FM(0.4))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(p15.GetNet())
        b.Add(t)


def pad(b, ref, num):
    return next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == str(num))


def chain(b, pads, width=0.5):
    for a, c in zip(pads, pads[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(a.GetPosition())
        t.SetEnd(c.GetPosition())
        t.SetWidth(FM(width))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(a.GetNet())
        b.Add(t)


def iso_rails(b):
    for i in range(4):
        u = f"U{10 + i}"
        caps = (f"C{62 + 5 * i}", f"C{63 + 5 * i}", f"C{42 + 4 * i}")
        chain(b, [pad(b, u, 13), pad(b, u, 12)] + [pad(b, c, 1) for c in caps] + [pad(b, f"FB{10 + 2 * i}", 1)])
        chain(b, [pad(b, u, 11)] + [pad(b, c, 2) for c in caps] + [pad(b, f"FB{11 + 2 * i}", 1)])


def via(b, net, x, y):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(x, y))
    v.SetWidth(FM(0.6))
    v.SetDrill(FM(0.3))
    v.SetNet(net)
    b.Add(v)
    return v


def track(b, net, a, c, layer, width=0.5):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(a)
    t.SetEnd(c)
    t.SetWidth(FM(width))
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)


def vcan(b):
    for i in range(4):
        c43, fb = pad(b, f"C{43 + 4 * i}", 1), pad(b, f"FB{10 + 2 * i}", 2)
        chain(b, [pad(b, f"U{10 + i}", 20), c43])
        chain(b, [fb, pad(b, f"C{64 + 5 * i}", 1)])
        net = c43.GetNet()
        p, q = c43.GetPosition(), fb.GetPosition()
        v1 = pcbnew.VECTOR2I(p.x, p.y - FM(1.3))
        v2 = pcbnew.VECTOR2I(q.x, q.y - FM(1.6))
        via(b, net, *v1)
        via(b, net, *v2)
        track(b, net, p, v1, pcbnew.F_Cu)
        track(b, net, v1, v2, pcbnew.B_Cu)
        track(b, net, v2, q, pcbnew.F_Cu)


def pre():
    b = pcbnew.LoadBoard(PCB)
    gisoin_stubs(b)
    iso_rails(b)
    vcan(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    win = mr.Window(0, 0, W, H, W, H)
    mr.ground_fanout(b, list(GROUNDS), win, verbose=False)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)


def auto():
    cmd = [sys.executable, str(REPO / "tools/freeroute.py"), str(HW.parent), "--skip", *GROUNDS,
           "--timeout", "900", "--passes", "60", "--threads", "1"]
    subprocess.run(cmd, check=True)


def width_of(b, net):
    return 0.5 if "Power" in str(b.FindNet(net).GetNetClassName()) else 0.25


def finish():
    b = pcbnew.LoadBoard(PCB)
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
    freeroute.fix_vias(b)
    for g in GROUNDS:
        left += mr.stitch_pads(b, g, win, verbose=False)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
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
