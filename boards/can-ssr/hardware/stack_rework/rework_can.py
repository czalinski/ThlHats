"""can-ssr stack-interface rework, step 3: CAN IN/OUT -> one MCDN double-level header
at the stack CAN position (pin 1 at y 15.5, 3.5 mm pitch down the left edge).
Rips up only copper that conflicts with the new header / moved parts, then joins
the broken nets with miniroute.complete_net.
rework_can.py PCB LIBDIR ROUTERDIR"""
import sys

import pcbnew

sys.path.insert(0, sys.argv[3])
import miniroute as mr

PCB, LIB = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
FM, TM = pcbnew.FromMM, pcbnew.ToMM
O = 100.0
PIN1_Y = 15.5
SW_DX = 3.0


def P(x, y):
    return pcbnew.VECTOR2I(FM(O + x), FM(O + y))


def L(v):
    return (TM(v.x) - O, TM(v.y) - O)


def near(p, q, tol=0.03):
    return abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol


def netinfo(name):
    for k, v in b.GetNetsByName().items():
        if str(k) == name or str(k).endswith("/" + name):
            return v
    raise KeyError(name)


def short(t):
    return t.GetNetname().split("/")[-1]


# --- 1. rip up only what conflicts -----------------------------------------------------------
def in_zone(p):          # new header pads (x 8.2-13.9, y 14.4-27.1) and D2's new spot
    return p[0] < 14.3 and 8.9 < p[1] < 41.5


n = 0
for t in list(b.GetTracks()):
    nm = short(t)
    s, e = L(t.GetStart()), L(t.GetEnd())
    if nm in ("CANH", "CANL", "V12_BUS", "CAN_RX") and (in_zone(s) or in_zone(e)):
        b.Delete(t); n += 1
    elif nm == "GND" and (any(near(p, q) for p in (s, e) for q in
                              ((14.3, 14.6), (13.8, 17.4), (14.5, 15.8), (14.3, 16.9),
                               (23.6, 27.7), (22.1, 27.7), (21.9, 27.63)))):
        b.Delete(t); n += 1
    elif nm == "ADDR1" and (near(s, (20.12, 32.08)) or near(e, (20.12, 32.08)) or
                            near(s, (22.9, 29.3)) or near(e, (22.9, 29.3))):
        b.Delete(t); n += 1
    elif nm == "ADDR3" and ((near(s, (21.5, 27.0)) and near(e, (20.12, 27.0))) or
                            (near(e, (21.5, 27.0)) and near(s, (20.12, 27.0)))):
        b.Delete(t); n += 1
print("ripped", n)

# --- 2. connector: J1 -> MCDN, J2 out ----------------------------------------------------
old = b.FindFootprintByReference("J1")
path = pcbnew.KIID_PATH(old.GetPath().AsString())
sheet, sfile = str(old.GetSheetname()), str(old.GetSheetfile())
mfr = old.GetFieldText("Manufacturer") if old.HasField("Manufacturer") else "Phoenix Contact"
b.Delete(old)
b.Delete(b.FindFootprintByReference("J2"))
FPN = "PhoenixContact_MCDN_1,5_4-G1-3,5_2x04_P3.5mm_Horizontal"
f = pcbnew.FootprintLoad(LIB + "/Thl_Connector.pretty", FPN)
f.SetFPID(pcbnew.LIB_ID("Thl_Connector", FPN))
f.SetReference("J1")
f.SetValue("CAN IN/OUT")
f.SetPath(path)
f.SetSheetname(sheet)
f.SetSheetfile(sfile)
f.SetField("Manufacturer", mfr)
f.SetField("MPN", "1953732")
for fld in f.GetFields():
    if fld.GetName() in ("Manufacturer", "MPN"):
        fld.SetVisible(False)
f.SetOrientationDegrees(-90)
f.SetPosition(P(12.8, PIN1_Y))          # pad 1 (rear row); mating face at x = 0
b.Add(f)
NETS = {1: "CANH", 2: "CANL", 3: "GND", 4: "V12_BUS"}
for p in f.Pads():
    p.SetNet(netinfo(NETS[(int(p.GetNumber()) - 1) % 4 + 1]))
f.Reference().SetPosition(P(7.0, PIN1_Y - 4.6))
f.Reference().SetTextAngleDegrees(0)

# --- 3. moves -----------------------------------------------------------------------------------
sw = b.FindFootprintByReference("SW1")
sw.Move(pcbnew.VECTOR2I(FM(SW_DX), 0))
swp = {p.GetNumber(): L(p.GetPosition()) for p in sw.Pads()}


def move_ends(net, old_pt, new_pt):
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or short(t) != net:
            continue
        if near(L(t.GetStart()), old_pt):
            t.SetStart(P(*new_pt))
        if near(L(t.GetEnd()), old_pt):
            t.SetEnd(P(*new_pt))


def add_track(net, a, c, w=0.25, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(FM(w)); t.SetLayer(layer)
    t.SetNet(netinfo(net)); b.Add(t)


# ADDR0: the stub from pin 1 shifts with it
move_ends("ADDR0", (12.5, 27.0), swp["1"])
move_ends("ADDR0", (12.5, 25.72), (swp["1"][0], 25.72))
move_ends("ADDR0", (12.95, 25.27), (swp["1"][0] + 0.45, 25.27))
# ADDR2: diagonal from pin 4 becomes a dog-leg
for t in b.GetTracks():
    if t.GetClass() == "PCB_TRACK" and short(t) == "ADDR2":
        s, e = L(t.GetStart()), L(t.GetEnd())
        if near(e, (12.5, 32.08)) or near(s, (12.5, 32.08)):
            top = s if near(e, (12.5, 32.08)) else e
            knee = (top[0], swp["4"][1] - (top[0] - swp["4"][0]))     # 45 deg down to pin 4
            if near(e, (12.5, 32.08)):
                t.SetEnd(P(*knee))
            else:
                t.SetStart(P(*knee))
            add_track("ADDR2", knee, swp["4"])
            break
# ADDR3: diagonal now ends on the moved pin 8
move_ends("ADDR3", (21.5, 27.0), swp["8"])

d2 = b.FindFootprintByReference("D2")
d2.SetPosition(P(9.35, 34.2))
d2.SetOrientationDegrees(90)
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT":
        legend = {"1 CANH": 0, "2 CANL": 1, "3 GND": 2, "4 +12V": 3}
        if d.GetText() in legend:
            d.SetPosition(P(1.9, 29.9 + 1.1 * legend[d.GetText()]))
            d.SetTextSize(pcbnew.VECTOR2I(FM(0.8), FM(0.8))); d.SetTextThickness(FM(0.15))
        elif d.GetText() == "ADDR":
            d.SetPosition(P(21.6, 24.5))


def pad(ref, num):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            return L(p.GetPosition())


# IN/OUT links: pad n <-> pad n+4 (3.5 mm apart, same column)
add_track("CANH", pad("J1", "1"), pad("J1", "5"), 0.5)
add_track("CANL", pad("J1", "2"), pad("J1", "6"), 0.5)
add_track("GND", pad("J1", "3"), pad("J1", "7"), 0.5)
add_track("V12_BUS", pad("J1", "4"), pad("J1", "8"), 1.0)

# --- 3b. rip foreign copper that collides with the placed parts, then prune stubs ------------
CLR_IU = FM(0.2)
moved = [b.FindFootprintByReference(r) for r in ("J1", "SW1", "D2")]
affected = {"CANH", "CANL", "CAN_RX", "V12_BUS", "ADDR0", "ADDR1", "ADDR2", "ADDR3"}
for t in list(b.GetTracks()):
    hit = False
    for fp in moved:
        for p in fp.Pads():
            if p.GetNetCode() == t.GetNetCode():
                continue
            for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
                if t.IsOnLayer(lid) and p.IsOnLayer(lid) and                         t.GetEffectiveShape(lid).Collide(p.GetEffectiveShape(lid), CLR_IU):
                    hit = True
        if hit:
            break
    if hit:
        affected.add(short(t))
        print("  conflict rip", short(t), L(t.GetStart()), L(t.GetEnd()))
        b.Delete(t)


def connected_end(t, pt, net):
    v = P(*pt)
    for o in b.GetTracks():
        if o.m_Uuid.AsString() == t.m_Uuid.AsString() or o.GetNetCode() != net:
            continue
        if o.GetClass() == "PCB_VIA":
            if o.HitTest(v, 0):
                return True
        elif near(L(o.GetStart()), pt, 0.01) or near(L(o.GetEnd()), pt, 0.01) or o.HitTest(v, 0):
            return True
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == net and p.HitTest(v):
                return True
    return False


print("affected", sorted(affected))

# --- 4. join the broken nets ----------------------------------------------------------------------
win = mr.Window(0.0, 0.0, 34.0, 41.9)
ok = True
for net in sorted(affected - {"GND"}):
    w = 0.5 if net in ("V12_BUS", "+5V") else 0.25
    ok &= mr.complete_net(b, netinfo(net).GetNetname(), w, win)
x, y = pad("D2", "2")
ok &= mr.route(b, "GND", (x, y, {"F"}), "B", 0.4, win)
for t in list(b.GetTracks()):        # orphaned GND stitch left by the SW1 move
    if short(t) == "GND" and t.GetClass() == "PCB_VIA" and near(L(t.GetPosition()), (25.31, 30.9)):
        b.Delete(t)
        continue
    if short(t) == "GND" and (near(L(t.GetStart()), (25.31, 30.9)) and near(L(t.GetEnd()), (23.65, 30.85)) or
                              near(L(t.GetEnd()), (25.31, 30.9)) and near(L(t.GetStart()), (23.65, 30.85))):
        b.Delete(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
cs = sorted((L(p.GetPosition()) for p in sw.Pads() if p.GetNumber() == "C"), key=lambda q: q[0])
ok &= mr.route(b, "GND", (cs[0][0], cs[0][1], {"F", "B"}), (cs[1][0], cs[1][1], {"F", "B"}), 0.4, win)

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print("saved, all joined" if ok else "saved, SOME NETS NOT JOINED")
