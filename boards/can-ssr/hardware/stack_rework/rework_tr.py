"""can-ssr stack-interface rework, step 2: M4 standoff holes at 4.5 mm inset and the
top-right corner (LED column, R50/C44, SEG_D/SEG_E/ISET/UART_RX/LED reroutes).
Run on the board produced by stack_bottom.py:  rework_tr.py PCB LIBDIR"""
import math
import sys

import pcbnew

sys.path.insert(0, sys.argv[3] if len(sys.argv) > 3 else "tools")
import miniroute as mr

PCB, LIB = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
FM, TM = pcbnew.FromMM, pcbnew.ToMM
O = 100.0


def P(x, y):
    return pcbnew.VECTOR2I(FM(O + x), FM(O + y))


def L(v):
    return (TM(v.x) - O, TM(v.y) - O)


def near(p, q, tol=0.02):
    return abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol


# --- 1. holes: Thl standoff footprint, 4.5 mm inset (91 x 91 mm square) ---------------
HOLES = {"MH1": (4.5, 4.5), "MH2": (95.5, 4.5), "MH3": (4.5, 95.5), "MH4": (95.5, 95.5)}
for r in HOLES:
    b.Delete(b.FindFootprintByReference(r))
for r, (x, y) in HOLES.items():
    f = pcbnew.FootprintLoad(LIB + "/Thl_Mechanical.pretty", "MountingHole_4.3mm_M4_Standoff7mm")
    f.SetReference(r)
    f.SetPosition(P(x, y))
    b.Add(f)
for z in b.Zones():                          # bottom copper keep-outs follow the holes
    if z.GetZoneName() == "HOLE_KEEPOUT":
        c = z.GetBoundingBox().GetCenter()
        cx, cy = L(c)
        nx = 4.5 if cx < 50 else 95.5
        z.Move(pcbnew.VECTOR2I(FM(nx - cx), FM(95.5 - cy)))

# --- 2. rip-up list (exact segments / vias, board-local mm) -----------------------------
RIP = [
    # SEG_E around the old corner
    ((93.12, 12.33), (94.05, 11.4)), ((94.05, 11.4), (94.05, 6.13)), ((94.05, 6.13), (88.94, 1.02)),
    # SEG_D under R50
    ((89.91, 5.12), (89.91, 7.51)), ((89.91, 7.51), (92.19, 9.78)), ((86.48, 1.69), (89.91, 5.12)),
    # ISET
    ((92.84, 15.94), (94.94, 15.94)), ((91.05, 5.01), (92.99, 6.96)), ((94.94, 15.94), (95.08, 16.08)),
    ((95.08, 16.08), (95.68, 16.08)), ((92.99, 6.96), (92.99, 13.4)), ((92.99, 13.4), (95.68, 16.08)),
    (92.99, 6.96), (95.68, 16.08),
    # +5V stubs to R50 pad 1 and C44 pad 1
    ((86.17, 6.95), (87.95, 5.18)), ((82.74, 4.5), (82.74, 5.49)), ((82.74, 5.49), (84.1, 6.85)),
    # GND stub + via at C44 pad 2
    ((85.86, 4.5), (86.46, 5.54)), (86.46, 5.54),
    # LED_STATUS from the column to via (89.47, 21.52)
    ((95.05, 12.75), (95.3, 12.5)), ((95.3, 12.5), (95.3, 11.05)), (95.05, 12.75),
    ((95.05, 14.47), (95.05, 12.75)), ((96.3, 15.72), (95.05, 14.47)), ((96.3, 16.37), (96.3, 15.72)),
    ((91.15, 21.52), (96.3, 16.37)), ((89.47, 21.52), (91.15, 21.52)),
    # LED_FAULT from R7 to (93.75, 21.85)
    ((95.3, 17.55), (95.3, 20.3)), ((95.3, 20.3), (93.75, 21.85)),
    # UART_RX from via (88.63, 13.05) to J4 pin 2
    ((88.63, 13.05), (91.08, 15.49)), ((91.08, 15.49), (94.33, 15.49)), ((94.33, 15.49), (94.38, 15.44)),
    ((94.38, 15.44), (96.01, 15.44)), ((96.01, 15.44), (96.51, 15.94)), ((96.51, 15.94), (96.51, 24.53)),
    ((96.51, 24.53), (93.0, 28.04)),
]
gone = 0
for t in list(b.GetTracks()):
    s, e = L(t.GetStart()), L(t.GetEnd())
    for r in RIP:
        if isinstance(r[0], tuple):
            if t.GetClass() == "PCB_TRACK" and ((near(s, r[0]) and near(e, r[1])) or
                                                (near(s, r[1]) and near(e, r[0]))):
                b.Delete(t); gone += 1; break
        elif t.GetClass() == "PCB_VIA" and near(s, r):
            b.Delete(t); gone += 1; break
print("ripped", gone, "of", len(RIP))

# --- 3. moves -----------------------------------------------------------------------------
COL = ("R6", "D4", "R7", "D5")
for r in COL:
    b.FindFootprintByReference(r).Move(pcbnew.VECTOR2I(0, FM(2.0)))
for t in b.GetTracks():                       # column vias and the two anode links ride along
    s = L(t.GetStart())
    if (t.GetClass() == "PCB_VIA" and (near(s, (99.04, 12.09)) or near(s, (99.04, 18.09)))) or \
       t.GetNetname() in ("Net-(D4-A)", "Net-(D5-A)"):
        t.Move(pcbnew.VECTOR2I(0, FM(2.0)))
b.FindFootprintByReference("R50").Move(pcbnew.VECTOR2I(FM(-0.85), 0))
b.FindFootprintByReference("C44").Move(pcbnew.VECTOR2I(FM(-0.8), 0))


def pad(ref, num):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            x, y = L(p.GetPosition())
            lay = {"F"} if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD else {"F", "B"}
            return (x, y, lay)
    raise KeyError(ref + num)


def net_of(ref, num):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            return p.GetNetname()


win = mr.Window(74.0, 0.0, 100.0, 31.0)
F, FB = {"F"}, {"F", "B"}
JOBS = [  # (net, a, b, width), most constrained first
    (net_of("U40", "21"), pad("U40", "21"), (88.94, 1.02, F), 0.25),        # SEG_E
    (net_of("U40", "23"), pad("U40", "23"), (86.48, 1.69, F), 0.25),        # SEG_D
    (net_of("U40", "18"), pad("R50", "2"), pad("U40", "18"), 0.25),         # ISET
    ("+5V", pad("R50", "1"), (86.17, 6.95, F), 0.5),
    ("+5V", pad("C44", "1"), (84.1, 6.85, FB), 0.5),
    (net_of("R6", "1"), pad("R6", "1"), (89.47, 21.52, FB), 0.25),          # LED_STATUS
    (net_of("R7", "1"), pad("R7", "1"), (93.75, 21.85, F), 0.25),           # LED_FAULT
    (net_of("J4", "2"), (88.63, 13.05, FB), pad("J4", "2"), 0.25),          # UART_RX
]
ok = True
for net, a, c, w in JOBS:
    ok &= mr.route(b, net, a, c, w, win)

ok &= mr.route(b, "GND", pad("C44", "2"), "B", 0.35, win)       # C44 pad 2 into the bottom pour

for z in b.Zones():
    if z.GetZoneName() == "HOLE_KEEPOUT":
        z.SetDoNotAllowPads(False)
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetText() == "SUPPLY +":
        d.SetPosition(P(6.2, 87.6))

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print("saved, all routed" if ok else "saved, SOME NETS NOT ROUTED")
