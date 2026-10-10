"""Tiny two-layer grid router for local reroutes with the pcbnew API (no numpy).

Used for small rework where an autorouter is overkill: rip up a few local
tracks, move parts, then route(board, net, a, b, width, Window(...)) connects
endpoint a to b inside the window (A* on a 0.05 mm grid, house clearances,
line-of-sight pull to clean segments). An endpoint is (x, y, {"F","B"}) in
board-local mm (board corner at ORIGIN); b may be "B" to end in a via into a
bottom pour. First used for the can-ssr stack-interface rework (2026-10-06).
"""
import heapq
import math

import pcbnew
from PIL import Image, ImageDraw

ORIGIN = 100.0
G = 0.05                     # grid, mm
CLR = 0.2                    # copper clearance
NPTH_CLR = 0.3
EDGE_CLR = 0.3
VIA_D, VIA_DRILL = 0.6, 0.3
MARGIN = 0.01
VIA_COST = 25.0              # in cells (1.25 mm)
B_FACTOR = 1.15              # mild preference for the top layer

FM, TM = pcbnew.FromMM, pcbnew.ToMM
LAYER = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}


class Window:
    def __init__(self, x0, y0, x1, y1, board_w=100.0, board_h=100.0):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.W = int(round((x1 - x0) / G)) + 1
        self.H = int(round((y1 - y0) / G)) + 1
        self.bw, self.bh = board_w, board_h

    def cell(self, x, y):
        return int(round((x - self.x0) / G)), int(round((y - self.y0) / G))

    def xy(self, cx, cy):
        return self.x0 + cx * G, self.y0 + cy * G

    def px(self, x_iu, y_iu):
        return ((TM(x_iu) - ORIGIN - self.x0) / G, (TM(y_iu) - ORIGIN - self.y0) / G)


def _draw_poly(draw, win, poly):
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        pts = [win.px(o.CPoint(j).x, o.CPoint(j).y) for j in range(o.PointCount())]
        if len(pts) >= 3:
            draw.polygon(pts, fill=255)


def _inside_window(win, item, pad=3.0):
    bb = item.GetBoundingBox()
    x0, y0 = TM(bb.GetLeft()) - ORIGIN, TM(bb.GetTop()) - ORIGIN
    x1, y1 = TM(bb.GetRight()) - ORIGIN, TM(bb.GetBottom()) - ORIGIN
    return x1 > win.x0 - pad and x0 < win.x1 + pad and y1 > win.y0 - pad and y0 < win.y1 + pad


def obstacles(board, win, netcode, infl):
    """Rasters (bytes) per layer: 255 where a centreline at distance < infl from foreign copper."""
    out = {}
    for lname, lid in LAYER.items():
        im = Image.new("L", (win.W, win.H), 0)
        dr = ImageDraw.Draw(im)
        e = FM(infl)
        for t in board.GetTracks():
            if t.GetNetCode() == netcode or not _inside_window(win, t):
                continue
            if t.GetClass() == "PCB_VIA" or t.IsOnLayer(lid):
                ps = pcbnew.SHAPE_POLY_SET()
                t.TransformShapeToPolygon(ps, lid, e, FM(0.005), pcbnew.ERROR_OUTSIDE)
                _draw_poly(dr, win, ps)
        for f in board.GetFootprints():
            for p in f.Pads():
                if not _inside_window(win, p):
                    continue
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    cx, cy = win.px(p.GetPosition().x, p.GetPosition().y)
                    r = (TM(p.GetDrillSize().x) / 2 + NPTH_CLR - CLR + infl) / G
                    dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
                    continue
                if p.GetNetCode() == netcode and netcode > 0:
                    continue
                if not p.IsOnLayer(lid):
                    continue
                ps = pcbnew.SHAPE_POLY_SET()
                p.TransformShapeToPolygon(ps, lid, e, FM(0.005), pcbnew.ERROR_OUTSIDE)
                _draw_poly(dr, win, ps)
        # rule areas that forbid tracks (isolation gaps, keep-outs under modules)
        for z in board.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(lid):
                ps = pcbnew.SHAPE_POLY_SET(z.Outline())
                ps.Inflate(FM(infl - CLR), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, FM(0.005))
                _draw_poly(dr, win, ps)
        # board edge
        m = (EDGE_CLR - CLR + infl) / G
        x0, y0 = (0 - win.x0) / G, (0 - win.y0) / G
        x1, y1 = (win.bw - win.x0) / G, (win.bh - win.y0) / G
        for r in ((-10, -10, win.W + 10, y0 + m), (-10, y1 - m, win.W + 10, win.H + 10),
                  (-10, -10, x0 + m, win.H + 10), (x1 - m, -10, win.W + 10, win.H + 10)):
            if r[2] >= r[0] and r[3] >= r[1]:
                dr.rectangle(r, fill=255)
        # window border: stay inside
        dr.rectangle((0, 0, win.W - 1, win.H - 1), outline=255)
        out[lname] = im.tobytes()
    return out


DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def astar(win, obst, viaok, starts, goal_cells, goal_any_b=False):
    W, H = win.W, win.H
    N = W * H
    layers = ("F", "B")
    gx = gy = None
    if goal_cells:
        gx = sum(c[0] for c in goal_cells) / len(goal_cells)
        gy = sum(c[1] for c in goal_cells) / len(goal_cells)
    goalset = {(c[2], c[1] * W + c[0]) for c in goal_cells}

    def h(x, y):
        if gx is None:
            return 0.0
        dx, dy = abs(x - gx), abs(y - gy)
        return (dx + dy) + (1.4142 - 2) * min(dx, dy)

    INF = float("inf")
    dist = {}
    prev = {}
    pq = []
    for (x, y, L) in starts:
        k = (layers.index(L), y * W + x)
        dist[k] = 0.0
        heapq.heappush(pq, (h(x, y), 0.0, k))
    while pq:
        f, d, k = heapq.heappop(pq)
        if d > dist.get(k, INF):
            continue
        li, idx = k
        L = layers[li]
        if (L, idx) in goalset or (goal_any_b and L == "B"):
            path = [k]
            while k in prev:
                k = prev[k][0]
                path.append(k)
            return [(layers[a], b % W, b // W) for a, b in reversed(path)]
        x, y = idx % W, idx // W
        o = obst[L]
        fac = B_FACTOR if L == "B" else 1.0
        for dx, dy, c in DIRS:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            ni = ny * W + nx
            if o[ni]:
                continue
            nk = (li, ni)
            nd = d + c * fac
            if nd < dist.get(nk, INF):
                dist[nk] = nd
                prev[nk] = (k,)
                heapq.heappush(pq, (nd + h(nx, ny), nd, nk))
        # via
        if viaok["F"][idx] == 0 and viaok["B"][idx] == 0:
            nk = (1 - li, idx)
            nd = d + VIA_COST
            if obst[layers[1 - li]][idx] == 0 and nd < dist.get(nk, INF):
                dist[nk] = nd
                prev[nk] = (k,)
                heapq.heappush(pq, (nd + h(x, y), nd, nk))
    return None


def _simplify(points):
    """points: [(L, x, y)] cells -> list of runs [(L, [(x, y), ...corners])]."""
    runs = []
    cur_L = None
    pts = []
    for L, x, y in points:
        if L != cur_L:
            if pts:
                runs.append((cur_L, pts))
            cur_L, pts = L, [(x, y)]
            continue
        if len(pts) >= 2:
            (ax, ay), (bx, by) = pts[-2], pts[-1]
            if (bx - ax, by - ay) == (x - bx, y - by) or (
                    (bx - ax) * (y - by) - (by - ay) * (x - bx) == 0 and
                    (bx - ax) * (x - bx) + (by - ay) * (y - by) > 0):
                pts[-1] = (x, y)
                continue
        pts.append((x, y))
    if pts:
        runs.append((cur_L, pts))
    return runs


def _free_line(o, W, p, q):
    (x0, y0), (x1, y1) = p, q
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
    for i in range(n + 1):
        x = round(x0 + (x1 - x0) * i / n)
        y = round(y0 + (y1 - y0) * i / n)
        if o[y * W + x]:
            return False
    return True


def _pull(o, W, pts):
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not _free_line(o, W, pts[i], pts[j]):
            j -= 1
        out.append(pts[j])
        i = j
    return out


def route(board, net, a, b, width, win, verbose=True):
    """a, b: (x, y, {'F','B'}) local mm; b may be the string 'B' (end in a via to B.Cu)."""
    nc = board.GetNetInfo().GetNetItem(net).GetNetCode()
    hw = width / 2
    obst = obstacles(board, win, nc, CLR + hw + MARGIN)
    viaok = obstacles(board, win, nc, CLR + VIA_D / 2 + MARGIN)
    ax, ay = win.cell(a[0], a[1])
    starts = [(ax, ay, L) for L in a[2]]
    goal = []
    any_b = False
    if b == "B":
        any_b = True
    else:
        bx, by = win.cell(b[0], b[1])
        goal = [(bx, by, L) for L in b[2]]
    # punch the endpoints free (pads of this net are excluded already; track ends may sit
    # right next to foreign copper by design)
    obst = {L: bytearray(v) for L, v in obst.items()}
    for (x, y, L) in starts + goal:
        for ddx in range(-2, 3):
            for ddy in range(-2, 3):
                i = (y + ddy) * win.W + (x + ddx)
                if 0 <= i < len(obst[L]):
                    obst[L][i] = 0
    path = astar(win, obst, viaok, starts, goal, any_b)
    if path is None:
        if verbose:
            print("  NO ROUTE", net, a, b)
        return False
    runs = [(L, _pull(obst[L], win.W, pts)) for L, pts in _simplify(path)]
    netinfo = board.GetNetInfo().GetNetItem(net)
    first = True
    added = 0
    for ri, (L, pts) in enumerate(runs):
        coords = [win.xy(x, y) for x, y in pts]
        if ri == 0:
            coords[0] = (a[0], a[1])
        if ri == len(runs) - 1 and b != "B":
            coords[-1] = (b[0], b[1])
        for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
            if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(FM(ORIGIN + x0), FM(ORIGIN + y0)))
            t.SetEnd(pcbnew.VECTOR2I(FM(ORIGIN + x1), FM(ORIGIN + y1)))
            t.SetWidth(FM(width))
            t.SetLayer(LAYER[L])
            t.SetNet(netinfo)
            board.Add(t)
            added += 1
        if ri < len(runs) - 1:
            vx, vy = coords[-1]
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(FM(ORIGIN + vx), FM(ORIGIN + vy)))
            v.SetWidth(FM(VIA_D))
            v.SetDrill(FM(VIA_DRILL))
            v.SetNet(netinfo)
            board.Add(v)
    if verbose:
        n_via = sum(1 for _ in runs) - 1
        print(f"  routed {net}: {added} segments, {n_via} vias")
    return True


def _islands(board, netcode):
    """Connected clusters of a net (tracks, vias, pads), via pcbnew connectivity."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    items = [t for t in board.GetTracks() if t.GetNetCode() == netcode]
    items += [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetCode() == netcode]
    items += [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == netcode]
    seen, out = set(), []
    for it in items:
        k = it.m_Uuid.AsString()
        if k in seen:
            continue
        cl = [it] + [x for x in conn.GetConnectedItems(it)
                     if x.GetNetCode() == netcode]
        ks = {x.m_Uuid.AsString() for x in cl}
        seen |= ks
        out.append(cl)
    return out


def _raster_items(win, items):
    cells = {"F": set(), "B": set()}
    for lname, lid in LAYER.items():
        im = Image.new("L", (win.W, win.H), 0)
        dr = ImageDraw.Draw(im)
        for it in items:
            if not it.IsOnLayer(lid) and it.GetClass() != "PCB_VIA":
                continue
            if it.GetClass() == "ZONE":
                _draw_poly(dr, win, it.GetFilledPolysList(lid))
                continue
            ps = pcbnew.SHAPE_POLY_SET()
            it.TransformShapeToPolygon(ps, lid, 0, FM(0.005), pcbnew.ERROR_INSIDE)
            _draw_poly(dr, win, ps)
        data = im.tobytes()
        cells[lname] = {i for i, v in enumerate(data) if v}
    return cells


def _free_ends(board, island):
    """Track ends of an island that touch nothing else (where a rip-up cut the net)."""
    out = []
    tracks = [t for t in island if t.GetClass() == "PCB_TRACK"]
    others = [x for x in island]
    for t in tracks:
        for pt in (t.GetStart(), t.GetEnd()):
            hit = False
            for o in others:
                if o.m_Uuid.AsString() == t.m_Uuid.AsString():
                    continue
                if o.GetClass() == "PCB_TRACK":
                    if (abs(o.GetStart().x - pt.x) < 10000 and abs(o.GetStart().y - pt.y) < 10000) or \
                       (abs(o.GetEnd().x - pt.x) < 10000 and abs(o.GetEnd().y - pt.y) < 10000) or o.HitTest(pt, 0):
                        hit = True
                elif o.GetClass() == "ZONE":
                    continue
                elif o.HitTest(pt):
                    hit = True
                if hit:
                    break
            if not hit:
                L_ = "F" if t.GetLayer() == pcbnew.F_Cu else "B"
                out.append((TM(pt.x) - ORIGIN, TM(pt.y) - ORIGIN, L_))
    return out


def complete_net(board, net, width, win, verbose=True, max_rounds=400):
    """Join the islands of a net: route each smaller island to the largest one.
    Islands that cannot be reached are skipped; returns True only if the net ends whole."""
    netinfo = board.GetNetInfo().GetNetItem(net)
    nc = netinfo.GetNetCode()
    skip = set()
    for _ in range(max_rounds):
        isl = _islands(board, nc)
        if len(isl) <= 1:
            return True
        isl.sort(key=len)
        dst = isl[-1]
        cands = [i for i in isl[:-1] if frozenset(x.m_Uuid.AsString() for x in i) not in skip]
        if not cands:
            return False
        src = cands[0]
        key = frozenset(x.m_Uuid.AsString() for x in src)
        hw = width / 2
        obst = obstacles(board, win, nc, CLR + hw + MARGIN)
        viaok = obstacles(board, win, nc, CLR + VIA_D / 2 + MARGIN)
        s_free = [e for e in _free_ends(board, src) if win.x0 <= e[0] <= win.x1 and win.y0 <= e[1] <= win.y1]
        d_free = [e for e in _free_ends(board, dst) if win.x0 <= e[0] <= win.x1 and win.y0 <= e[1] <= win.y1]
        if s_free:
            starts = [win.cell(x, y) + (L,) for x, y, L in s_free]
        else:
            s_cells = _raster_items(win, src)
            starts = [(i % win.W, i // win.W, L) for L in ("F", "B") for i in s_cells[L]]
        if d_free:
            goals = [win.cell(x, y) + (L,) for x, y, L in d_free]
        else:
            d_cells = _raster_items(win, dst)
            goals = [(i % win.W, i // win.W, L) for L in ("F", "B") for i in d_cells[L]]
        if not starts or not goals:
            if verbose:
                print("  island outside window", net)
            skip.add(key)
            continue
        obst = {k: bytearray(v) for k, v in obst.items()}
        for (x, y, L) in (starts if s_free else []) + (goals if d_free else []):
            for ddx in range(-2, 3):           # a cut end may sit right next to foreign copper
                for ddy in range(-2, 3):
                    i = (y + ddy) * win.W + (x + ddx)
                    if 0 <= i < len(obst[L]):
                        obst[L][i] = 0
        path = astar(win, obst, viaok, starts, goals)
        if path is None and (s_free or d_free):
            s_cells, d_cells = _raster_items(win, src), _raster_items(win, dst)
            starts = [(i % win.W, i // win.W, L) for L in ("F", "B") for i in s_cells[L]]
            goals = [(i % win.W, i // win.W, L) for L in ("F", "B") for i in d_cells[L]]
            s_free = d_free = []
            path = astar(win, obst, viaok, starts, goals)
        if path is None:
            if verbose:
                print("  NO ROUTE between islands of", net)
            skip.add(key)
            continue
        runs = [(L, _pull(obst[L], win.W, pts)) for L, pts in _simplify(path)]

        def snap(pt, ends):
            best = min(ends, key=lambda e: (e[0] - pt[0]) ** 2 + (e[1] - pt[1]) ** 2)
            return (best[0], best[1]) if (best[0] - pt[0]) ** 2 + (best[1] - pt[1]) ** 2 < 0.01 else pt
        for ri, (L, pts) in enumerate(runs):
            coords = [win.xy(x, y) for x, y in pts]
            if ri == 0 and s_free:
                coords[0] = snap(coords[0], s_free)
            if ri == len(runs) - 1 and d_free:
                coords[-1] = snap(coords[-1], d_free)
            for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(FM(ORIGIN + x0), FM(ORIGIN + y0)))
                t.SetEnd(pcbnew.VECTOR2I(FM(ORIGIN + x1), FM(ORIGIN + y1)))
                t.SetWidth(FM(width)); t.SetLayer(LAYER[L]); t.SetNet(netinfo)
                board.Add(t)
            if ri < len(runs) - 1:
                vx, vy = coords[-1]
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(FM(ORIGIN + vx), FM(ORIGIN + vy)))
                v.SetWidth(FM(VIA_D)); v.SetDrill(FM(VIA_DRILL)); v.SetNet(netinfo)
                board.Add(v)
        if verbose:
            print(f"  joined an island of {net}: {sum(len(p) - 1 for _, p in runs)} segments, {len(runs) - 1} vias")
    return len(_islands(board, nc)) <= 1


def ground_fanout(board, nets, win, verbose=True, qfp_inward=False, refs=None):
    """Give every SMD pad on `nets` a short F.Cu stub to a via inside that net's
    B.Cu pour (the pours must exist and be filled). QFP pads escape straight
    out along their side with a 0.2 mm stub (with qfp_inward, first straight in,
    under the package); other pads try 17 directions with a 0.5 mm stub. Not rerun-safe: a second call adds a second set of vias.
    refs: only these footprints (for parts added to a routed board).
    Returns the number of pads left without a via."""
    import math
    zones = {z.GetNetname(): z for z in board.Zones() if not z.GetIsRuleArea() and z.GetLayer() == pcbnew.B_Cu}
    added = missed = 0
    for net in nets:
        ni = board.GetNetInfo().GetNetItem(net)
        zone = zones.get(net)
        if ni is None or ni.GetNetCode() <= 0 or zone is None:
            continue
        nc = ni.GetNetCode()
        viaok = obstacles(board, win, nc, CLR + VIA_D / 2 + MARGIN)
        trk_wide = obstacles(board, win, nc, CLR + 0.25 + MARGIN)
        trk_thin = obstacles(board, win, nc, CLR + 0.1 + 0.01)
        placed = [(TM(t.GetPosition().x) - ORIGIN, TM(t.GetPosition().y) - ORIGIN) for t in board.GetTracks()
                  if t.GetClass() == "PCB_VIA" and t.GetNetCode() == nc]
        for f in board.GetFootprints():
            if refs is not None and f.GetReference() not in refs:
                continue
            fx, fy = TM(f.GetPosition().x) - ORIGIN, TM(f.GetPosition().y) - ORIGIN
            layer = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
            for p in f.Pads():
                if p.GetNetCode() != nc or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                    continue
                px, py = TM(p.GetPosition().x) - ORIGIN, TM(p.GetPosition().y) - ORIGIN
                half = max(TM(p.GetSize().x), TM(p.GetSize().y)) / 2
                away = math.atan2(py - fy, px - fx) if (px, py) != (fx, fy) else 0.0
                qfp = "QFP" in f.GetFPIDAsString()
                if qfp:
                    dx, dy = px - fx, py - fy
                    away = (0.0 if dx > 0 else math.pi) if abs(dx) > abs(dy) else \
                        (math.pi / 2 if dy > 0 else -math.pi / 2)
                stub = 0.2 if qfp else 0.5
                trk = trk_thin if qfp else trk_wide
                tip = (px + half * math.cos(away), py + half * math.sin(away)) if qfp else (px, py)
                done = False
                dists = (half + 1.0, half + 1.5, half + 2.0, half + 2.6, half + 3.2) if qfp else \
                    (half + 0.55, half + 0.9, half + 1.3, half + 1.8)
                for d in dists:
                    angles = ([away + math.pi, away] if qfp_inward else [away]) if qfp else \
                        [away] + [away + sgn * j * math.pi / 8 for j in range(1, 9) for sgn in (1, -1)]
                    for a in angles:
                        if qfp:
                            tip = (px + half * math.cos(a), py + half * math.sin(a))
                        vx, vy = px + d * math.cos(a), py + d * math.sin(a)
                        cx, cy = win.cell(vx, vy)
                        if not (0 <= cx < win.W and 0 <= cy < win.H):
                            continue
                        i = cy * win.W + cx
                        if viaok["F"][i] or viaok["B"][i]:
                            continue
                        if any(math.hypot(vx - qx, vy - qy) < 1.0 for qx, qy in placed):
                            continue
                        if not zone.HitTestFilledArea(pcbnew.B_Cu, pcbnew.VECTOR2I(FM(ORIGIN + vx), FM(ORIGIN + vy)), 0):
                            continue
                        side = "B" if layer == pcbnew.B_Cu else "F"
                        if not _free_line(trk[side], win.W, win.cell(*tip), (cx, cy)):
                            continue
                        t = pcbnew.PCB_TRACK(board)
                        t.SetStart(p.GetPosition())
                        t.SetEnd(pcbnew.VECTOR2I(FM(ORIGIN + vx), FM(ORIGIN + vy)))
                        t.SetWidth(FM(stub))
                        t.SetLayer(layer)
                        t.SetNet(ni)
                        board.Add(t)
                        v = pcbnew.PCB_VIA(board)
                        v.SetPosition(pcbnew.VECTOR2I(FM(ORIGIN + vx), FM(ORIGIN + vy)))
                        v.SetWidth(FM(VIA_D))
                        v.SetDrill(FM(VIA_DRILL))
                        v.SetNet(ni)
                        board.Add(v)
                        placed.append((vx, vy))
                        added += 1
                        done = True
                        break
                    if done:
                        break
                if not done:
                    missed += 1
                    if verbose:
                        print(f"  no fanout via for {f.GetReference()}.{p.GetNumber()} ({net})")
    if verbose:
        print(f"fanout: {added} vias, {missed} pads without one")
    return missed


def stitch_pads(board, net, win, width=0.3, verbose=True):
    """Join pads of `net` that are not in its main cluster (the connectivity
    island holding the most pour area) with a short straight stub: 16
    directions, 0.8-3 mm, either layer, ending inside any fill of the net.
    Each candidate is kept only if, after a refill, the pad has joined the
    main cluster. Returns the pads left unjoined."""
    import math
    ni = board.FindNet(net)
    nc = ni.GetNetCode()
    filler = pcbnew.ZONE_FILLER(board)

    def main_ids():
        isl = _islands(board, nc)
        main = max(isl, key=lambda cl: sum(abs(x.GetFilledArea()) for x in cl if x.GetClass() == "ZONE"))
        return {x.m_Uuid.AsString() for x in main}

    def in_fill(lay, pt):
        for z in board.Zones():
            if not z.GetIsRuleArea() and z.GetNetCode() == nc and z.GetLayer() == lay:
                if z.GetFilledPolysList(lay).Contains(pt):
                    return True
        return False

    filler.Fill(board.Zones())
    ids = main_ids()
    todo = [p for f in board.GetFootprints() for p in f.Pads()
            if p.GetNetCode() == nc and p.m_Uuid.AsString() not in ids]
    left = []
    for p in todo:
        name = f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}"
        if p.m_Uuid.AsString() in main_ids():
            continue
        obst = obstacles(board, win, nc, CLR + width / 2 + MARGIN)
        layers = [l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if p.IsOnLayer(l)]
        px, py = TM(p.GetPosition().x) - ORIGIN, TM(p.GetPosition().y) - ORIGIN
        done = False
        for d in (0.8, 1.2, 1.6, 2.0, 2.5, 3.0):
            for k in range(16):
                a = k * math.pi / 8
                ex, ey = px + d * math.cos(a), py + d * math.sin(a)
                end = pcbnew.VECTOR2I(FM(ORIGIN + ex), FM(ORIGIN + ey))
                for lay in layers:
                    side = "F" if lay == pcbnew.F_Cu else "B"
                    cx, cy = win.cell(ex, ey)
                    if not (0 <= cx < win.W and 0 <= cy < win.H) or obst[side][cy * win.W + cx]:
                        continue
                    if not in_fill(lay, end) or not _free_line(obst[side], win.W, win.cell(px, py), (cx, cy)):
                        continue
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(p.GetPosition())
                    t.SetEnd(end)
                    t.SetWidth(FM(width))
                    t.SetLayer(lay)
                    t.SetNet(ni)
                    board.Add(t)
                    filler.Fill(board.Zones())
                    if p.m_Uuid.AsString() in main_ids():
                        done = True
                        break
                    board.Delete(t)
                    filler.Fill(board.Zones())
                if done:
                    break
            if done:
                break
        if verbose:
            print(f"  {name}: {'stub' if done else 'NOT joined'}")
        if not done:
            left.append(name)
    return left


def pin_escape(board, ref, pin, win, inward=True, width=0.2, verbose=True):
    """Escape one QFP pin to a via: a stub straight along the pin's normal
    (inward under the package, or outward), optionally ending in a 45-degree
    jog sideways, and a via there. Candidates are checked against all other
    copper (tracks, pads, vias, keep-outs) on both layers. Returns the via
    position (board-local mm) or None."""
    import math
    f = board.FindFootprintByReference(ref)
    p = [q for q in f.Pads() if q.GetNumber() == str(pin)][0]
    nc = p.GetNetCode()
    fx, fy = TM(f.GetPosition().x) - ORIGIN, TM(f.GetPosition().y) - ORIGIN
    px, py = TM(p.GetPosition().x) - ORIGIN, TM(p.GetPosition().y) - ORIGIN
    dx, dy = px - fx, py - fy
    nx, ny = ((1.0 if dx > 0 else -1.0), 0.0) if abs(dx) > abs(dy) else (0.0, (1.0 if dy > 0 else -1.0))
    if inward:
        nx, ny = -nx, -ny
    tx, ty = -ny, nx                                   # along the pad row
    half = max(TM(p.GetSize().x), TM(p.GetSize().y)) / 2
    viaok = obstacles(board, win, nc, CLR + VIA_D / 2 + MARGIN)
    trk = obstacles(board, win, nc, CLR + width / 2 + MARGIN)
    tip = (px + nx * half, py + ny * half)
    for d in (1.3, 1.6, 2.0, 2.4, 2.8):
        for lat in (0.0, 0.8, -0.8, 1.2, -1.2):
            bend = (px + nx * (d - abs(lat)), py + ny * (d - abs(lat)))
            via = (bend[0] + nx * abs(lat) + tx * lat, bend[1] + ny * abs(lat) + ty * lat)
            cx, cy = win.cell(*via)
            if not (0 <= cx < win.W and 0 <= cy < win.H):
                continue
            i = cy * win.W + cx
            if viaok["F"][i] or viaok["B"][i]:
                continue
            pts = [tip, bend, via] if lat else [tip, via]
            if not all(_free_line(trk["F"], win.W, win.cell(*a), win.cell(*c)) for a, c in zip(pts, pts[1:])):
                continue
            chain = [(px, py)] + pts[1:]
            for a, c in zip(chain, chain[1:]):
                if math.hypot(c[0] - a[0], c[1] - a[1]) < 1e-6:
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(FM(ORIGIN + a[0]), FM(ORIGIN + a[1])))
                t.SetEnd(pcbnew.VECTOR2I(FM(ORIGIN + c[0]), FM(ORIGIN + c[1])))
                t.SetWidth(FM(width))
                t.SetLayer(pcbnew.F_Cu)
                t.SetNet(p.GetNet())
                board.Add(t)
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(FM(ORIGIN + via[0]), FM(ORIGIN + via[1])))
            v.SetWidth(FM(VIA_D))
            v.SetDrill(FM(VIA_DRILL))
            v.SetNet(p.GetNet())
            board.Add(v)
            if verbose:
                print(f"  {ref}.{pin} ({p.GetNetname()}): via at ({via[0]:.2f}, {via[1]:.2f})")
            return via
    if verbose:
        print(f"  {ref}.{pin} ({p.GetNetname()}): no escape found")
    return None
