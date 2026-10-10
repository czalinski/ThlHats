#!/usr/bin/env python3
"""Probe test points: a bare-copper pad on every net, on copper the net already has.

  tools/testpoints.py boards/<name> [--clear] [--dry-run]

Places Thl_TestPoint:TP_Probe_D1.0mm (1.0 mm pad, F.Cu + mask opening,
board-only: no schematic symbol, not in the BOM or the placement file) so that
no routing changes:
  - on one of the net's F.Cu tracks, on one of its vias, or inside its F.Cu
    pour (candidates in that order of preference, then by clearance margin);
  - clear of foreign copper (net class clearance), part courtyards (+0.65 mm),
    everything printed on the silkscreen (outlines, references, board texts),
    isolation-gap rule areas, the board edge and other test points (2 mm);
  - at least 0.5 mm from the net's own pads: the probe measures through the
    solder joint instead of pressing on it.
Pours refill around the new pads. Then DRC runs: a test point in any new
violation (custom rules too, e.g. high-voltage clearance or TI keep-outs) moves
to its next candidate. Ground nets (GND*) get several spread-out test points so
every probe pair has a ground nearby.

Nets with fewer than two pads are skipped. Where no test point fits (often a
short trace between two close parts), the probe point is the toe of one of
the net's SMD pads, the part of a hand-solder pad that sticks out beyond the
part (kind "pad", e.g. R71.2): the probe still measures through the joint and
no copper changes. Passives first, then the largest pad. A net with only
through-hole pads uses its first THT pad (kind "tht-pad"). Nets left over are
reported.

Reference texts a new pad lands on are moved with tools/silk_tidy.py --only.

Test points go on the side of the net's SMD parts (boards with parts on the
bottom, e.g. can-ssr, get bottom test points too), grounds on every such side.

Writes boards/<name>/test/testpoints.csv (ref, net, side, x, y, kind, ground
domain, nearest part) and tp-map-top.png / tp-map-bottom.png. Rerunnable: keeps the test
points already on the board unless --clear. The pairs to measure come from
tools/tptest.py plan.
"""
import argparse
import csv
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import miniroute as mr  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
LIB, FP_NAME = "Thl_TestPoint", "TP_Probe_D1.0mm"
R_PAD = 0.5
SPACING = 2.0           # min centre distance between test points (probe tips)
PAD_GAP = 0.5           # min edge distance from a TP to its own net's pads
CRT = 0.65              # TP courtyard (0.6) + margin, kept out of part courtyards
GROUND = re.compile(r"(^|/)(GND|VSS)", re.I)
GROUND_AREA = 1500.0    # mm^2 of pour per ground test point (1 to 6)
FM, TM, O = pcbnew.FromMM, pcbnew.ToMM, mr.ORIGIN


def is_tp(f):
    return f.GetFPID().GetLibNickname() == LIB


def board_xy(v):
    return TM(v.x) - O, TM(v.y) - O


def clearance(board, nc):
    try:
        return TM(board.GetNetInfo().GetNetItem(nc).GetNetClass().GetClearance())
    except Exception:
        return mr.CLR


def raster(win, polys):
    im = Image.new("L", (win.W, win.H), 0)
    dr = ImageDraw.Draw(im)
    for ps in polys:
        mr._draw_poly(dr, win, ps)
    return im


def poly_of(item, layer, infl):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, layer, FM(infl), FM(0.005), pcbnew.ERROR_OUTSIDE)
    return ps


SIDES = {"F": (pcbnew.F_Cu, pcbnew.F_SilkS), "B": (pcbnew.B_Cu, pcbnew.B_SilkS)}


class Placer:
    """Candidate search on one side ("F" or "B")."""

    def __init__(self, board, side="F"):
        self.b = board
        self.side = side
        self.cu, self.silk = SIDES[side]
        bb = board.GetBoardEdgesBoundingBox()
        self.W, self.H = TM(bb.GetWidth()), TM(bb.GetHeight())
        self.win = mr.Window(0, 0, self.W, self.H, self.W, self.H)
        crt = []
        for f in board.GetFootprints():
            if is_tp(f):
                continue
            # this side's courtyard: parts on this side, and through-hole parts and
            # mounting holes on the other side that have one here too
            c = f.GetCourtyard(self.cu)
            if c.OutlineCount():
                c = pcbnew.SHAPE_POLY_SET(c)
                c.Inflate(FM(CRT), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, FM(0.01))
                crt.append(c)
            # printed outlines and markers that reach outside the courtyard
            for g in f.GraphicalItems():
                if g.GetLayer() == self.silk and g.GetClass() != "PCB_TEXT":
                    crt.append(poly_of(g, self.silk, R_PAD + 0.15))
            r = f.Reference()               # keep references readable for assembly
            if r.IsVisible() and r.GetLayer() == self.silk:
                crt.append(poly_of(r, self.silk, R_PAD + 0.15))
        for d in board.GetDrawings():       # board texts and graphics on the silkscreen
            if d.GetLayer() == self.silk:
                crt.append(poly_of(d, self.silk, R_PAD + 0.15))
        self.crt = raster(self.win, crt)
        self.blocked = {}               # netcode -> [(x, y)] rejected by DRC

    def free(self, im, x, y):
        cx, cy = self.win.cell(x, y)
        if not (0 <= cx < self.win.W and 0 <= cy < self.win.H):
            return False
        return im.getpixel((cx, cy)) == 0

    def tps(self):
        """Test points on this side."""
        return [(board_xy(f.GetPosition()), f) for f in self.b.GetFootprints()
                if is_tp(f) and f.IsFlipped() == (self.side == "B")]

    def candidates(self, nc):
        """(x, y, kind) on the net's own copper on this side."""
        out = []
        for t in self.b.GetTracks():
            if t.GetNetCode() != nc:
                continue
            if t.GetClass() == "PCB_VIA":
                out.append((*board_xy(t.GetPosition()), "via"))
            elif t.GetClass() == "PCB_TRACK" and t.GetLayer() == self.cu:
                (x0, y0), (x1, y1) = board_xy(t.GetStart()), board_xy(t.GetEnd())
                n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 0.1))
                out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n, "track") for k in range(n + 1)]
        for z in self.b.Zones():
            if z.GetIsRuleArea() or z.GetNetCode() != nc or not z.IsOnLayer(self.cu):
                continue
            fill = z.GetFilledPolysList(self.cu)
            bb = z.GetBoundingBox()
            x0, y0 = board_xy(bb.GetOrigin())
            x1, y1 = board_xy(bb.GetEnd())
            y = y0
            while y <= y1:
                x = x0
                while x <= x1:
                    if fill.Contains(pcbnew.VECTOR2I(FM(x + O), FM(y + O))):
                        out.append((x, y, "pour"))
                    x += 0.5
                y += 0.5
        return out

    def options(self, nc):
        """Free candidates, best first: [(score, x, y, kind)]."""
        cands = self.candidates(nc)
        if not cands:
            return []
        clr = clearance(self.b, nc)
        obst = Image.frombytes("L", (self.win.W, self.win.H),
                               mr.obstacles(self.b, self.win, nc, clr + R_PAD + mr.MARGIN)[self.side])
        own = raster(self.win, [poly_of(p, self.cu, R_PAD + PAD_GAP)
                                for p in self.b.GetPads() if p.GetNetCode() == nc and p.IsOnLayer(self.cu)
                                and not is_tp(p.GetParentFootprint())])
        others = [xy for xy, f in self.tps()]
        blocked = self.blocked.get(nc, [])
        rank = {"track": 2, "via": 1, "pour": 0}
        out = []
        for x, y, kind in cands:
            if not (self.free(obst, x, y) and self.free(self.crt, x, y) and self.free(own, x, y)):
                continue
            if any(math.hypot(x - a, y - c) < SPACING for a, c in others + blocked):
                continue
            # margin: how much of a ring 0.25 / 0.5 mm further out is also clear
            ring = sum(self.free(obst, x + r * math.cos(a), y + r * math.sin(a))
                       for r in (0.25, 0.5) for a in [k * math.pi / 4 for k in range(8)])
            out.append((ring * 3 + rank[kind], x, y, kind))
        out.sort(key=lambda o: -o[0])
        return out

    def add(self, nc, x, y, kind):
        f = pcbnew.FootprintLoad(str(REPO / "lib/footprints" / f"{LIB}.pretty"), FP_NAME)
        f.SetFPID(pcbnew.LIB_ID(LIB, FP_NAME))
        f.SetReference("TP?")
        f.SetPosition(pcbnew.VECTOR2I(FM(x + O), FM(y + O)))
        f.SetValue(kind)
        for p in f.Pads():
            p.SetNet(self.b.GetNetInfo().GetNetItem(nc))
        self.b.Add(f)
        if self.side == "B":            # flip once on the board: Flip on a loose footprint crashes pcbnew
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        return f


def net_pads(board):
    """netcode -> (pad count, sides with SMD pads ("F"/"B" set)), test points excluded."""
    out = {}
    for f in board.GetFootprints():
        if is_tp(f):
            continue
        for p in f.Pads():
            nc = p.GetNetCode()
            if nc <= 0:
                continue
            n, smd = out.get(nc, (0, set()))
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                smd = smd | {"B" if f.IsFlipped() else "F"}
            out[nc] = (n + 1, smd)
    return out


def drc(pcb_path):
    """{(type, description, items...)}: every DRC violation and unconnected item."""
    with tempfile.TemporaryDirectory() as d:
        rpt = Path(d) / "drc.json"
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "-o", str(rpt), pcb_path],
                       check=True, capture_output=True)
        data = json.loads(rpt.read_text())
    out = []
    for v in data.get("violations", []) + data.get("unconnected_items", []):
        out.append((v["type"], v["description"], tuple(i["description"] for i in v.get("items", []))))
    return out


def tp_refs(items):
    return {m.group(1) for d in items for m in re.finditer(r"\b(?:of|Footprint) (TP\d+|TP\?)", d)}


def pad_probe(board, nc):
    """(ref.pad, x, y, kind, side) on an existing pad of the net: the toe of an SMD
    pad (outer end, away from the part centre), passives first; else a THT pad."""
    best = None
    for f in board.GetFootprints():
        if is_tp(f):
            continue
        sd = "B" if f.IsFlipped() else "F"
        two = len([p for p in f.Pads() if p.GetNumber()]) == 2
        fx, fy = board_xy(f.GetPosition())
        for p in f.Pads():
            if p.GetNetCode() != nc:
                continue
            px, py = board_xy(p.GetPosition())
            sx, sy = TM(p.GetSize().x), TM(p.GetSize().y)
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                d = math.hypot(px - fx, py - fy) or 1.0
                off = max(0.0, max(sx, sy) / 2 - 0.35)
                x, y = px + (px - fx) / d * off, py + (py - fy) / d * off
                score = (2, two, sx * sy)
                kind = "pad"
            elif p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                x, y, score, kind = px, py, (1, False, sx * sy), "tht-pad"
            else:
                continue
            if best is None or score > best[0]:
                best = (score, f"{f.GetReference()}.{p.GetNumber()}", x, y, kind, sd if kind == "pad" else "F")
    return best[1:] if best else None


def ground_of(board, x, y, grounds):
    """The ground domain at (x, y): the ground pour (B.Cu first) whose outline holds the point."""
    pt = pcbnew.VECTOR2I(FM(x + O), FM(y + O))
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        best = None
        for z in board.Zones():
            if z.GetIsRuleArea() or z.GetNetname() not in grounds or not z.IsOnLayer(layer):
                continue
            if z.Outline().Contains(pt):
                if best is None or z.GetAssignedPriority() > best.GetAssignedPriority():
                    best = z
        if best:
            return best.GetNetname()
    return ""


def nearest_part(board, x, y):
    best, ref = 1e9, ""
    for f in board.GetFootprints():
        if is_tp(f) or not any(p.GetNetCode() > 0 for p in f.Pads()):
            continue
        fx, fy = board_xy(f.GetPosition())
        d = math.hypot(fx - x, fy - y)
        if d < best:
            best, ref = d, f.GetReference()
    return ref


def place(board_dir, clear=False, dry_run=False):
    hw = board_dir / "hardware"
    pcb = hw / f"{board_dir.name}.kicad_pcb"
    b = pcbnew.LoadBoard(str(pcb))
    if clear:
        for f in [f for f in b.GetFootprints() if is_tp(f)]:
            b.Delete(f)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    if not dry_run:
        b.Save(str(pcb))
    baseline = set(drc(str(pcb))) if not dry_run else set()

    bottom = any(f.IsFlipped() and not is_tp(f) and any(p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD for p in f.Pads())
                 for f in b.GetFootprints())
    pls = {"F": Placer(b, "F")}
    if bottom:
        pls["B"] = Placer(b, "B")
    pads = net_pads(b)
    covered = {f.Pads()[0].GetNetCode() for f in b.GetFootprints() if is_tp(f)}
    names = {nc: b.GetNetInfo().GetNetItem(nc).GetNetname() for nc in pads}
    grounds = {n for n in names.values() if GROUND.search(n)}
    todo = sorted((nc for nc, (n, smd) in pads.items()
                   if n >= 2 and nc not in covered and not names[nc].startswith("unconnected")),
                  key=lambda nc: (names[nc] in grounds, names[nc]))

    def sides(nc):
        """Where to look: the side of the net's SMD parts first. Grounds go on every side."""
        if names[nc] in grounds:
            return list(pls)
        order = ["B", "F"] if pads[nc][1] == {"B"} else ["F", "B"]
        return [sd for sd in order if sd in pls]

    def place_on(nc, pl):
        opts = pl.options(nc)
        if not opts:
            return 0
        if names[nc] not in grounds:
            s, x, y, kind = opts[0]
            pl.add(nc, x, y, kind)
            return 1
        # grounds: spread several over the pour by farthest-point sampling
        area = sum(z.GetFilledArea() for z in b.Zones() if z.GetNetCode() == nc and not z.GetIsRuleArea()) / 1e12
        want = max(1, min(6, round(area / GROUND_AREA)))
        good = [o for o in opts if o[0] >= opts[0][0] - 6]
        chosen = [good[0]]
        while len(chosen) < want:
            nxt = max(good, key=lambda o: min(math.hypot(o[1] - c[1], o[2] - c[2]) for c in chosen))
            if min(math.hypot(nxt[1] - c[1], nxt[2] - c[2]) for c in chosen) < 15.0:
                break
            chosen.append(nxt)
        for s, x, y, kind in chosen:
            pl.add(nc, x, y, kind)
        return len(chosen)

    def place_net(nc):
        n = 0
        for sd in sides(nc):
            n += place_on(nc, pls[sd])
            if n and names[nc] not in grounds:
                break
        return n

    missing = []
    for nc in todo:
        if not place_net(nc):
            missing.append(nc)
    if dry_run:
        renumber(b)
        print(f"would place test points on {len(todo) - len(missing)} of {len(todo)} nets")
    else:
        # DRC loop: move test points that cause new violations
        for rnd in range(6):
            renumber(b)
            pcbnew.ZONE_FILLER(b).Fill(b.Zones())
            b.Save(str(pcb))
            new = [v for v in drc(str(pcb)) if v not in baseline]
            hard = [v for v in new if not v[0].startswith("silk")]
            bad = set()
            for v in hard:
                bad |= tp_refs(v[2])
            other = [v for v in hard if not tp_refs(v[2])]
            if not bad:
                for v in other:
                    print("  new DRC item without a test point:", v[0], v[1], *v[2])
                break
            redo = set()
            for f in [f for f in b.GetFootprints() if is_tp(f) and f.GetReference() in bad]:
                nc = f.Pads()[0].GetNetCode()
                pls["B" if f.IsFlipped() else "F"].blocked.setdefault(nc, []).append(board_xy(f.GetPosition()))
                redo.add(nc)
                b.Delete(f)
            print(f"  DRC round {rnd + 1}: moving {len(bad)} test points")
            for nc in sorted(redo):
                if not any(is_tp(f) and f.Pads()[0].GetNetCode() == nc for f in b.GetFootprints()) \
                        and not place_net(nc):
                    missing.append(nc)
        renumber(b)
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.Save(str(pcb))

    rows = []
    for f in sorted((f for f in b.GetFootprints() if is_tp(f)), key=lambda f: int(f.GetReference()[2:])):
        x, y = board_xy(f.GetPosition())
        nc = f.Pads()[0].GetNetCode()
        rows.append({"ref": f.GetReference(), "net": names.get(nc, f.Pads()[0].GetNetname()),
                     "side": "B" if f.IsFlipped() else "F", "x": f"{x:.2f}", "y": f"{y:.2f}", "kind": f.GetValue(),
                     "ground": ground_of(b, x, y, grounds), "near": nearest_part(b, x, y)})
    have = {r["net"] for r in rows}
    fallback, no_room = [], []
    for nc in sorted(set(missing), key=lambda nc: names[nc]):
        if names[nc] in have:
            continue
        probe = pad_probe(b, nc)
        if probe:
            ref, x, y, kind, sd = probe
            rows.append({"ref": ref, "net": names[nc], "side": sd, "x": f"{x:.2f}", "y": f"{y:.2f}", "kind": kind,
                         "ground": ground_of(b, x, y, grounds), "near": ref.split(".")[0]})
            fallback.append(names[nc])
        else:
            no_room.append(names[nc])
    tp_rows = [r for r in rows if r["ref"].startswith("TP")]
    nb = sum(r["side"] == "B" for r in tp_rows)
    print(f"{board_dir.name}: {len(tp_rows)} test points ({nb} on the bottom) on {len({r['net'] for r in tp_rows})} "
          f"nets; {len(fallback)} nets probed on a pad")
    if no_room:
        print("  NO ROOM (SMD nets without a test point):", " ".join(no_room))
    if dry_run:
        return
    out = board_dir / "test"
    out.mkdir(exist_ok=True)
    with open(out / "testpoints.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, ["ref", "net", "side", "x", "y", "kind", "ground", "near"])
        w.writeheader()
        w.writerows(rows)
    for old in out.glob("tp-map*.png"):
        old.unlink()
    draw_map(b, [r for r in rows if r["side"] == "F"], out / "tp-map-top.png", "F")
    if any(r["side"] == "B" for r in rows):
        draw_map(b, [r for r in rows if r["side"] == "B"], out / "tp-map-bottom.png", "B")
    # move only the reference texts a test point landed on; the rest stay as reviewed
    refs = set()
    for kind, desc, items in drc(str(pcb)):
        if kind.startswith("silk") and tp_refs(items):
            refs |= {m.group(1) for d in items for m in re.finditer(r"Reference field of (\S+)", d)}
    if refs:
        subprocess.run([sys.executable, str(REPO / "tools/silk_tidy.py"), str(board_dir), "--only", *sorted(refs)],
                       check=True)


def renumber(b):
    """TP1.. in reading order (10 mm bands top to bottom, left to right), the top
    side first, then the bottom (read as seen from below: right to left)."""
    def key(f):
        x, y = board_xy(f.GetPosition())
        return (f.IsFlipped(), int(y // 10), -x if f.IsFlipped() else x)
    tps = sorted((f for f in b.GetFootprints() if is_tp(f)), key=key)
    for k, f in enumerate(tps, 1):
        f.SetReference(f"TP{k}")


def draw_map(b, rows, path, side="F", px_mm=12):
    """Board map of one side: part courtyards grey, test points coloured by ground
    domain, labelled. The bottom is drawn as seen from below (mirrored)."""
    bb = b.GetBoardEdgesBoundingBox()
    W, H = TM(bb.GetWidth()), TM(bb.GetHeight())
    m = 4
    im = Image.new("RGB", (int((W + 2 * m) * px_mm), int((H + 2 * m) * px_mm)), "white")
    dr = ImageDraw.Draw(im)

    def P(x, y):
        if side == "B":
            x = W - x
        return ((x + m) * px_mm, (y + m) * px_mm)

    dr.rectangle((m * px_mm, m * px_mm, (W + m) * px_mm, (H + m) * px_mm), outline="black", width=2)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", int(px_mm * 1.1))
        small = ImageFont.truetype("DejaVuSans.ttf", int(px_mm * 0.9))
    except OSError:
        font = small = ImageFont.load_default()
    for f in b.GetFootprints():
        if is_tp(f) or f.IsFlipped() != (side == "B"):
            continue
        c = f.GetCourtyard(SIDES[side][0])
        for i in range(c.OutlineCount()):
            o = c.Outline(i)
            pts = [P(TM(o.CPoint(j).x) - O, TM(o.CPoint(j).y) - O) for j in range(o.PointCount())]
            if len(pts) >= 3:
                dr.polygon(pts, outline=(170, 170, 170))
        x, y = board_xy(f.GetPosition())
        dr.text(P(x, y), f.GetReference(), fill=(150, 150, 150), font=small, anchor="mm")
    palette = [(200, 0, 0), (0, 120, 0), (0, 0, 200), (170, 0, 170), (0, 140, 140), (200, 110, 0), (90, 90, 90)]
    domains = sorted({r["ground"] for r in rows})
    for r in rows:
        x, y = float(r["x"]), float(r["y"])
        col = palette[domains.index(r["ground"]) % len(palette)]
        rr = 0.5 * px_mm
        if r["kind"] in ("pad", "tht-pad"):
            dr.rectangle((P(x, y)[0] - rr, P(x, y)[1] - rr, P(x, y)[0] + rr, P(x, y)[1] + rr), outline=col, width=2)
        else:
            dr.ellipse((P(x, y)[0] - rr, P(x, y)[1] - rr, P(x, y)[0] + rr, P(x, y)[1] + rr), fill=col)
        dr.text((P(x, y)[0] + rr + 2, P(x, y)[1]), r["ref"], fill=col, font=font, anchor="lm")
    dr.text((10, 10), "TOP" if side == "F" else "BOTTOM (seen from below)", fill="black", font=font)
    for k, d in enumerate(domains):
        dr.text((10, 10 + (k + 1) * px_mm * 1.4), f"domain {d or '?'}", fill=palette[k % len(palette)], font=font)
    im.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--clear", action="store_true", help="remove all test points first")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    place(Path(a.board).resolve(), a.clear, a.dry_run)


if __name__ == "__main__":
    main()
