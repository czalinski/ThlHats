#!/usr/bin/env python3
"""Routing pipeline for the io-card (same scheme as boards/can-card/hardware/route.py).

  python3 boards/io-card/hardware/route.py pre      ground fanout (not rerun-safe)
  python3 boards/io-card/hardware/route.py auto     Freerouting (tools/freeroute.py)
  python3 boards/io-card/hardware/route.py finish   join what is left, stitch grounds
  python3 boards/io-card/hardware/route.py all      delete tracks, place.py, pre, auto, finish

Grounds are pours on both layers per domain (GND on LOGIC, GND_RACK on RACK,
place.py); every SMD pad on a ground net gets a via into its pour first.
The AI terminal nets (/AIN*) are in net class HV (0.8 mm clearance), which
Freerouting honours.
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

PCB = str(HW / "io-card.kicad_pcb")
W, H = sb.BOARD
GROUNDS = ("GND", "/GND_RACK")


def pre():
    b = pcbnew.LoadBoard(PCB)
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
    cls = str(b.FindNet(net).GetNetClassName())
    return 0.5 if "Power" in cls else 0.3 if "HV" in cls else 0.25


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
