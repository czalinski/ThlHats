#!/usr/bin/env python3
"""Routing pipeline for the io-card (same scheme as boards/can-card/hardware/route.py).

  python3 boards/io-card/hardware/route.py pre      ground fanout (not rerun-safe)
  python3 boards/io-card/hardware/route.py auto     Freerouting (tools/freeroute.py)
  python3 boards/io-card/hardware/route.py finish   join what is left, stitch grounds
  python3 boards/io-card/hardware/route.py all      delete tracks, place.py, pre, auto, finish
  python3 boards/io-card/hardware/route.py ao       analog-out parts only (added 2026-10-10 to the
                                                    routed board): locks the existing tracks, fans
                                                    out the new ground pads, autoroutes, unlocks

Grounds are pours on both layers per domain (GND on LOGIC, GND_RACK on RACK,
place.py); every SMD pad on a ground net gets a via into its pour first.
The AI terminal nets (/AIN*) are in net class HV (0.8 mm clearance), which
Freerouting honours. The MCP4728's nets (MSOP-10, 0.5 mm pitch) are in net
class Fine (0.2 mm track, 0.15 mm clearance), so tracks can enter its pads.
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
    return 0.5 if "Power" in cls else 0.3 if "HV" in cls else 0.2 if "Fine" in cls else 0.25


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


AO_REFS = {"U90", "U91", "U92", "U93", "J50", "C90", "C91", "C92", "C93", "C94", "C95", "R90", "R91"} \
    | {f"{p}{n}" for n in range(92, 104) for p in ("R",)} | {f"C{n}" for n in range(96, 100)} \
    | {f"D{n}" for n in range(90, 94)}


def track(b, net, layer, pts, w):
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(place.O + x0), pcbnew.FromMM(place.O + y0)))
        t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(place.O + x1), pcbnew.FromMM(place.O + y1)))
        t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(layer)
        t.SetNet(b.FindNet(net))
        b.Add(t)


def dac_fanout(b):
    """U92 (MSOP-10, rotated 90: pins 1-5 along the bottom, 10-6 along the top)
    to C94 next to it: both GND_RACK pins (10 top, 4 bottom) run under the body
    to C94 pad 2 (which has its own via), VDD (pin 1) to C94 pad 1. Then the
    four outputs to U93 (Freerouting does not get them through the 0.5 mm pitch
    reliably)."""
    f, c = b.FindFootprintByReference("U92"), b.FindFootprintByReference("C94")
    pad = {p.GetNumber(): (pcbnew.ToMM(p.GetPosition().x) - place.O, pcbnew.ToMM(p.GetPosition().y) - place.O)
           for p in f.Pads()}
    cg = next((pcbnew.ToMM(p.GetPosition().x) - place.O, pcbnew.ToMM(p.GetPosition().y) - place.O)
              for p in c.Pads() if p.GetNumber() == "2")
    cv = next((pcbnew.ToMM(p.GetPosition().x) - place.O, pcbnew.ToMM(p.GetPosition().y) - place.O)
              for p in c.Pads() if p.GetNumber() == "1")
    (x10, y10), (x4, y4), (x1, y1) = pad["10"], pad["4"], pad["1"]
    track(b, "/GND_RACK", pcbnew.F_Cu, [(x10, y10), (x10, cg[1]), cg], 0.25)
    track(b, "/GND_RACK", pcbnew.F_Cu, [(x4, y4), (x4, y4 - 1.9), (x10 + 0.26, cg[1]), (x10, cg[1])], 0.25)
    track(b, "/V5_AO", pcbnew.F_Cu, [(x1, y1), (x1 - 1.44, y1), cv], 0.2)
    # outputs to U93's + inputs (rotation 0: pins 1-7 left, 8-14 right, pin 4/11 at its centre y).
    # DAC3/DAC4 (pins 8/9) straight up under U93's body to the inner ends of pins 10/12;
    # DAC1/DAC2 (pins 6/7) cross them on B.Cu to pins 3/5 on the left.
    u = {p.GetNumber(): (pcbnew.ToMM(p.GetPosition().x) - place.O, pcbnew.ToMM(p.GetPosition().y) - place.O)
         for p in b.FindFootprintByReference("U93").Pads()}
    track(b, "/DAC3", pcbnew.F_Cu, [pad["8"], (pad["8"][0], u["10"][1]), u["10"]], 0.2)
    track(b, "/DAC4", pcbnew.F_Cu, [pad["9"], (pad["9"][0], u["12"][1]), u["12"]], 0.2)
    xl = u["3"][0] - 2.6                                  # B.Cu legs left of U93's left pads
    # net, DAC pin, U93 pin, stub length up from the DAC pad, via offset (dx, dy) from the stub end, B.Cu column x
    for net, pin, tgt, stub, (dx, dy), x_out in (("/DAC1", "6", "3", 0.9, (0.8, -0.8), xl),
                                                 ("/DAC2", "7", "5", 1.5, (0.3, -0.9), xl + 0.8)):
        px, py = pad[pin]
        vx, vy = px + dx, py - stub + dy
        ty = u[tgt][1]
        track(b, net, pcbnew.F_Cu, [(px, py), (px, py - stub), (vx, vy)], 0.2)
        track(b, net, pcbnew.B_Cu, [(vx, vy), (x_out, vy), (x_out, ty)], 0.2)
        track(b, net, pcbnew.F_Cu, [(x_out, ty), u[tgt]], 0.2)
        for x, y in ((vx, vy), (x_out, ty)):
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(place.O + x), pcbnew.FromMM(place.O + y)))
            v.SetWidth(pcbnew.FromMM(0.6))
            v.SetDrill(pcbnew.FromMM(0.3))
            v.SetNet(b.FindNet(net))
            b.Add(v)


def ao():
    """Route the analog-out block without touching the reviewed routing:
    existing tracks, then the ground fanout and dac_fanout, are locked
    (exported to Freerouting as protected) and unlocked afterwards."""
    b = pcbnew.LoadBoard(PCB)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    win = mr.Window(0, 0, W, H, W, H)
    mr.ground_fanout(b, list(GROUNDS), win, verbose=False, refs=AO_REFS - {"U92"})
    dac_fanout(b)
    held = [t for t in b.GetTracks() if not t.IsLocked()]
    for t in held:
        t.SetLocked(True)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    auto()
    finish()
    b = pcbnew.LoadBoard(PCB)
    ids = {(t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) for t in held}
    new = []
    for t in b.GetTracks():
        if (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) in ids:
            t.SetLocked(False)
        else:
            new.append(t)
    print("removed", clean_new(b, new), "stray tracks")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)


def clean_new(b, new):
    """Freerouting re-imports the protected tracks unchanged but also leaves
    fragments on nets that were already routed. Drop new tracks on nets with
    no analog-out pad, zero-length ones, ones lying on another track of the
    same net, then dangling ones until none is left. (SWIG returns a new
    wrapper per call: compare items by UUID, not identity.)"""
    ao_nets = {p.GetNetCode() for f in b.GetFootprints() if f.GetReference() in AO_REFS for p in f.Pads()}
    uid = lambda t: t.m_Uuid.AsString()  # noqa: E731
    new = {uid(t) for t in new}
    gone = 0

    def drop(t):
        nonlocal gone
        new.discard(uid(t))
        b.Delete(t)
        gone += 1

    def fresh():
        return [t for t in b.GetTracks() if uid(t) in new]

    def others(t):
        return [o for o in b.GetTracks() if uid(o) != uid(t) and o.GetNetCode() == t.GetNetCode()
                and o.IsOnLayer(t.GetLayer())]

    for t in fresh():
        if t.GetNetCode() not in ao_nets or (t.GetClass() == "PCB_TRACK" and t.GetLength() < pcbnew.FromMM(0.01)):
            drop(t)
    for t in fresh():
        if t.GetClass() == "PCB_TRACK" and any(o.GetClass() == "PCB_TRACK" and o.HitTest(t.GetStart(), 1)
                                               and o.HitTest(t.GetEnd(), 1) for o in others(t)):
            drop(t)

    def touches(t, pt):
        # copper overlap counts: Freerouting may stop a track end just short of a pad edge
        r = t.GetWidth() // 2
        return any(p.GetNetCode() == t.GetNetCode() and p.IsOnLayer(t.GetLayer()) and p.HitTest(pt, r)
                   for p in b.GetPads()) or any(o.HitTest(pt, r) for o in others(t))

    while True:
        dangling = [t for t in fresh() if t.GetClass() == "PCB_TRACK"
                    and not (touches(t, t.GetStart()) and touches(t, t.GetEnd()))]
        if not dangling:
            return gone
        for t in dangling:
            drop(t)

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
    if cmd == "ao":
        ao()


if __name__ == "__main__":
    main()
