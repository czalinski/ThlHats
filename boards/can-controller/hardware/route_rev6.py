#!/usr/bin/env python3
"""Routing driver for can-controller (first pass on floorplan rev 6 placement).

  route_rev6.py fanout          ground vias: every SMD pad on a ground net gets a
                                short stub to a via inside its own domain's pour
  route_rev6.py nets N1 N2 ...  join each net's islands (tools/miniroute.complete_net)
  route_rev6.py all             fanout, then every net in ORDER, then the rest

Board-local mm (corner at (100, 100)). Not rerun-safe for "fanout" (it would add
a second set of vias); "nets" only joins islands, so it can be repeated.
"""
import math
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import miniroute as mr  # noqa: E402

PCB = str(HERE / "can-controller.kicad_pcb")
O = 100.0
FM, TM = pcbnew.FromMM, pcbnew.ToMM
GROUNDS = ("GND", "GND_RACK", "/CAN x4/GND_CAN1", "/CAN x4/GND_CAN2", "/CAN x4/GND_CAN3",
           "/CAN x4/GND_CAN4", "/CAN x4/GND2_1", "/CAN x4/GND2_2", "/CAN x4/GND2_3", "/CAN x4/GND2_4")
WIDTH = {"+12V": 0.8, "/Relay drive/V12_RLY": 0.8, "+5V": 0.6, "+3V3": 0.25, "/MCU, logic power/AVDD": 0.25,
         "/Ethernet/1V2D": 0.25, "/Ethernet/1V2A": 0.25, "/Ethernet/3V3A": 0.25, "GND": 0.25}
ORDER_PREFIX = ["/Ethernet/TX", "/Ethernet/RX", "/Ethernet/XSC", "/MCU, logic power/OSC", "/Ethernet/1V2",
                "/Ethernet/3V3A", "/Ethernet/JCT", "+3V3", "+5V", "/MCU, logic power/AVDD", "VMID",
                "/CAN x4/VISO", "/CAN x4/VCAN", "/CAN x4/CAN", "/C", "/ETH", "+12V", "/Relay drive/"]


def width_of(net):
    for k, w in WIDTH.items():
        if net == k or net.endswith(k):
            return w
    if "/CAN x4/VISO" in net or "/CAN x4/VCAN" in net:
        return 0.5
    if net.startswith("/Relay drive/RLYOUT") or "V12_" in net:
        return 0.6
    return 0.2           # signals: fits between 0.5 mm-pitch QFP pins


def net_window(b, net, pad=8.0):
    xs, ys = [], []
    nc = b.GetNetInfo().GetNetItem(net).GetNetCode()
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == nc:
                xs.append(TM(p.GetPosition().x) - O)
                ys.append(TM(p.GetPosition().y) - O)
    for t in b.GetTracks():
        if t.GetNetCode() == nc:
            for q in (t.GetStart(), t.GetEnd()):
                xs.append(TM(q.x) - O)
                ys.append(TM(q.y) - O)
    if not xs:
        return None
    return mr.Window(max(0.0, min(xs) - pad), max(0.0, min(ys) - pad), min(100.0, max(xs) + pad),
                     min(100.0, max(ys) + pad))


def fanout(b):
    zones = {z.GetNetname(): z for z in b.Zones() if not z.GetIsRuleArea() and z.GetLayer() == pcbnew.B_Cu}
    win = mr.Window(0, 0, 100, 100)
    added = missed = 0
    for net in GROUNDS:
        ni = b.GetNetInfo().GetNetItem(net)
        if ni is None or ni.GetNetCode() <= 0:
            continue
        zone = zones.get(net)
        if zone is None:                      # GND2_n: no pour; joined through its bead later
            continue
        nc = ni.GetNetCode()
        viaok = mr.obstacles(b, win, nc, mr.CLR + mr.VIA_D / 2 + mr.MARGIN)
        trk_wide = mr.obstacles(b, win, nc, mr.CLR + 0.25 + mr.MARGIN)     # 0.5 mm stubs
        trk_thin = mr.obstacles(b, win, nc, mr.CLR + 0.1 + 0.01)           # 0.2 mm QFP escapes
        placed = [(TM(t.GetPosition().x) - O, TM(t.GetPosition().y) - O) for t in b.GetTracks()
                  if t.GetClass() == "PCB_VIA" and t.GetNetCode() == nc]
        for f in b.GetFootprints():
            fx, fy = TM(f.GetPosition().x) - O, TM(f.GetPosition().y) - O
            for p in f.Pads():
                if p.GetNetCode() != nc or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                    continue
                px, py = TM(p.GetPosition().x) - O, TM(p.GetPosition().y) - O
                half = max(TM(p.GetSize().x), TM(p.GetSize().y)) / 2
                away = math.atan2(py - fy, px - fx) if (px, py) != (fx, fy) else 0.0
                qfp = "QFP" in f.GetFPIDAsString()
                if qfp:                         # escape along the outward normal of the pin's side
                    dx, dy = px - fx, py - fy
                    away = (0.0 if dx > 0 else math.pi) if abs(dx) > abs(dy) else (math.pi / 2 if dy > 0 else -math.pi / 2)
                stub = 0.2 if qfp else 0.5
                trk = trk_thin if qfp else trk_wide
                # QFP: check the escape from the pad tip, not its centre (the pad itself is own copper)
                tip = (px + half * math.cos(away), py + half * math.sin(away)) if qfp else (px, py)
                done = False
                dists = (half + 1.0, half + 1.5, half + 2.0, half + 2.6, half + 3.2) if qfp else \
                    (half + 0.55, half + 0.9, half + 1.3, half + 1.8)
                for d in dists:
                    angles = [away] if qfp else \
                        [away] + [away + sgn * j * math.pi / 8 for j in range(1, 9) for sgn in (1, -1)]
                    for a in angles:
                        vx, vy = px + d * math.cos(a), py + d * math.sin(a)
                        cx, cy = win.cell(vx, vy)
                        if not (0 <= cx < win.W and 0 <= cy < win.H):
                            continue
                        i = cy * win.W + cx
                        if viaok["F"][i] or viaok["B"][i]:
                            continue
                        if any(math.hypot(vx - qx, vy - qy) < 1.0 for qx, qy in placed):
                            continue
                        if not zone.HitTestFilledArea(pcbnew.B_Cu, pcbnew.VECTOR2I(FM(O + vx), FM(O + vy)), 0):
                            continue
                        if not mr._free_line(trk["F"], win.W, win.cell(*tip), (cx, cy)):
                            continue
                        t = pcbnew.PCB_TRACK(b)
                        t.SetStart(p.GetPosition())
                        t.SetEnd(pcbnew.VECTOR2I(FM(O + vx), FM(O + vy)))
                        t.SetWidth(FM(stub))
                        t.SetLayer(pcbnew.F_Cu)
                        t.SetNet(ni)
                        b.Add(t)
                        v = pcbnew.PCB_VIA(b)
                        v.SetPosition(pcbnew.VECTOR2I(FM(O + vx), FM(O + vy)))
                        v.SetWidth(FM(mr.VIA_D))
                        v.SetDrill(FM(mr.VIA_DRILL))
                        v.SetNet(ni)
                        b.Add(v)
                        placed.append((vx, vy))
                        added += 1
                        done = True
                        break
                    if done:
                        break
                if not done:
                    missed += 1
                    print(f"  no fanout via for {f.GetReference()}.{p.GetNumber()} ({net})")
        # vias block later candidates of the same net only by spacing; other nets see them on refill
    print(f"fanout: {added} vias, {missed} pads without one")


def route_nets(b, nets):
    bad = []
    for net in nets:
        win = net_window(b, net)
        if win is None:
            continue
        ok = mr.complete_net(b, net, width_of(net), win, verbose=False)
        if not ok:
            win = net_window(b, net, pad=20.0)
            ok = mr.complete_net(b, net, width_of(net), win, verbose=False)
        print(f"  {'ok  ' if ok else 'FAIL'} {net}")
        if not ok:
            bad.append(net)
    return bad


def all_nets(b):
    names = sorted({str(k) for k in b.GetNetsByName().keys()} - {""} - set(GROUNDS))
    names = [n for n in names if not n.startswith("unconnected-")]
    first = []
    for pre in ORDER_PREFIX:
        first += [n for n in names if n.startswith(pre) and n not in first]
    return first + [n for n in names if n not in first]


def main():
    b = pcbnew.LoadBoard(PCB)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("fanout", "all"):
        fanout(b)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    if cmd == "nets":
        bad = route_nets(b, sys.argv[2:])
    elif cmd in ("all", "route"):
        bad = route_nets(b, all_nets(b))
        bad += route_nets(b, [g for g in GROUNDS if "GND2_" in g])
        # the poured grounds are joined by fanout + pours; leftovers are handled one pin at a time
    else:
        bad = []
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    if bad:
        print("not joined:", " ".join(bad))


if __name__ == "__main__":
    main()
