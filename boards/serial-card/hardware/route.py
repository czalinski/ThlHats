#!/usr/bin/env python3
"""Routing pipeline for the serial-card (same scheme as boards/can-card/hardware/route.py).

  python3 boards/serial-card/hardware/route.py pre      pre-routing (not rerun-safe)
  python3 boards/serial-card/hardware/route.py auto     Freerouting (tools/freeroute.py)
  python3 boards/serial-card/hardware/route.py finish   join what is left, stitch grounds
  python3 boards/serial-card/hardware/route.py all      delete tracks, place.py, pre, auto, finish

pre:
- ISOW1432 stubs: MODE (13) to VISOOUT (12) for the 5 V bus side, IN (14) to
  GISOIN (15); both sit inside the TI 4 mm keep-out around pins 11/12.
- VISOOUT / GND2 rails (SLLSF86D 9.4.1 items 2-4): pin 12 -> 10 nF -> 1 uF ->
  10 uF -> bead FB(2i+10), pin 11 -> the same caps -> bead FB(2i+11), side by
  side on F.Cu, so the router never comes near pins 11/12.
- Ground fanout: every SMD pad on a ground net gets a via into its pour.
auto: Freerouting; grounds are pours (both layers per domain, place.py).
finish: nets still in pieces are joined by miniroute.complete_net, then
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

PCB = str(HW / "serial-card.kicad_pcb")
FM = pcbnew.FromMM
W, H = sb.BOARD
GROUNDS = ("GND", "/GND_485_3", "/GND_485_4")


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


def isow(b):
    for i in range(2):
        u = f"U{10 + i}"
        chain(b, [pad(b, u, 13), pad(b, u, 12)], 0.3)          # MODE -> VISOOUT (5 V bus side)
        chain(b, [pad(b, u, 14), pad(b, u, 15)], 0.3)          # IN -> GISOIN
        caps = (f"C{24 + 10 * i}", f"C{25 + 10 * i}", f"C{26 + 10 * i}")
        chain(b, [pad(b, u, 12)] + [pad(b, c, 1) for c in caps] + [pad(b, f"FB{10 + 2 * i}", 1)])
        chain(b, [pad(b, u, 11)] + [pad(b, c, 2) for c in caps] + [pad(b, f"FB{11 + 2 * i}", 1)])


def pre():
    b = pcbnew.LoadBoard(PCB)
    isow(b)
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
