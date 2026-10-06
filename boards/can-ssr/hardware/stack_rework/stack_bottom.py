"""can-ssr: stack-interface rework, step 1 (holes and load bolt row). Run once."""
import math, sys
import pcbnew

PCB = sys.argv[1]
LIB = sys.argv[2]                      # lib/footprints
b = pcbnew.LoadBoard(PCB)
mm, FM = pcbnew.ToMM, pcbnew.FromMM
O = 100.0
def P(x, y): return pcbnew.VECTOR2I(FM(O + x), FM(O + y))
def L(v): return (mm(v.x) - O, mm(v.y) - O)

# 1. M3 holes out, M4 stack-interface holes in
for r in ("MH1", "MH2", "MH3", "MH4"):
    b.Delete(b.FindFootprintByReference(r))
for r, (x, y) in {"MH1": (5, 5), "MH2": (95, 5), "MH3": (5, 95), "MH4": (95, 95)}.items():
    f = pcbnew.FootprintLoad(LIB + "/MountingHole.pretty", "MountingHole_4.3mm_M4")
    f.SetReference(r); f.SetPosition(P(x, y)); b.Add(f)

# 2. bolts, with their via rings (vias within 6 mm of the old centre)
MOVE = {"H1": (8, 18), "H2": (29, 36), "H4": (71, 63), "H3": (86, 82)}
vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
for ref, (x0, x1) in MOVE.items():
    f = b.FindFootprintByReference(ref)
    f.Move(pcbnew.VECTOR2I(FM(x1 - x0), 0))
    for v in vias:
        vx, vy = L(v.GetPosition())
        if math.hypot(vx - x0, vy - 93) < 6.0:
            v.Move(pcbnew.VECTOR2I(FM(x1 - x0), 0))

# 3. zone and rule-area outlines
def outline(z, pts):
    o = z.Outline(); o.RemoveAllContours(); o.NewOutline()
    for x, y in pts: o.Append(FM(O + x), FM(O + y))
def rect(x0, y0, x1, y1): return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
SHAPES = {
    "VIN": [(0.5, 58.5), (19.4, 58.5), (19.4, 86.0), (25.0, 86.0), (25.0, 99.5), (0.5, 99.5)],
    "VOUT": [(72.4, 58.6), (88.6, 58.6), (88.6, 70.0), (99.5, 70.0), (99.5, 99.5), (75.0, 99.5),
             (75.0, 85.0), (72.4, 85.0)],
    "RET top": rect(26.5, 86.0, 73.5, 99.5),
    "BAR_VIN": rect(11.65, 86.0, 24.35, 99.2),
    "BAR_VOUT": rect(75.65, 71.0, 88.35, 99.2),
    "RETBAR": rect(29.5, 86.65, 69.5, 99.35),
}
for z in b.Zones():
    if z.GetZoneName() in SHAPES:
        outline(z, SHAPES[z.GetZoneName()])

# 4. mask openings that match the bars
for d in b.GetDrawings():
    if d.GetLayerName() in ("F.Mask", "B.Mask") and d.GetClass() == "PCB_SHAPE":
        x0, y0 = L(d.GetBoundingBox().GetOrigin())
        if d.GetLayerName() == "B.Mask":
            d.SetStart(P(29.5, 86.65)); d.SetEnd(P(69.5, 99.35))
        elif x0 < 5:
            d.SetStart(P(11.65, 86.0)); d.SetEnd(P(24.35, 99.2))
        elif x0 > 79:
            d.SetStart(P(75.65, 71.0)); d.SetEnd(P(88.35, 99.2))

# 5. copper keep-out around the bottom (load-side) holes: hole edge + 4 mm
for x, y in ((5, 95), (95, 95)):
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True); z.SetZoneName("HOLE_KEEPOUT")
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(True)
    z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowFootprints(False)
    outline(z, [(x + 6.15 * math.cos(a * math.pi / 16), y + 6.15 * math.sin(a * math.pi / 16))
                for a in range(32)])
    b.Add(z)

# 6. silkscreen
dx_build = 49.5 - (44.43 + 59.85) / 2
for d in list(b.GetDrawings()):
    if d.GetLayerName() != "F.Silkscreen":
        continue
    t = d.GetText() if d.GetClass() == "PCB_TEXT" else None
    x, y = L(d.GetPosition()) if t is not None else L(d.GetBoundingBox().GetCenter())
    if t == "NYLON":
        b.Delete(d)
    elif t == "SUPPLY +":
        d.SetPosition(P(18.0, 84.6))
    elif t == "SUPPLY -":
        d.SetPosition(P(36.0, 85.6))
    elif t == "LOAD -":
        d.SetPosition(P(63.0, 85.6))
    elif t == "LOAD +":
        d.SetPosition(P(94.0, 84.0))
    elif t == "BUILD:":
        d.SetPosition(P(49.5, 89.6))
    elif t in ("HC", "STD", "HV") or (t is None and y > 92 and 44 < x < 58):
        d.Move(pcbnew.VECTOR2I(FM(dx_build), 0))

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(PCB)
print("saved")
