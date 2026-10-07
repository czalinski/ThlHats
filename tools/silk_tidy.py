#!/usr/bin/env python3
"""Move reference designators off pads, other silkscreen and the board edge.

  tools/silk_tidy.py boards/<name> [--dry-run]

For every footprint whose Reference text (on F/B.Silkscreen) overlaps a pad
or via (incl. 0.15 mm), another footprint's silkscreen or reference, or comes
within 0.3 mm of the board edge, tries positions around its courtyard (above,
below, left, right, then the corners; horizontal, then vertical for
left/right) and takes the first clear one. References that find no spot are
hidden on silkscreen (they stay on the Fab layer) and listed.

Bounding boxes only: good enough for small chip parts; check the render.
"""
import argparse
import sys
from pathlib import Path

import pcbnew

FM, TM = pcbnew.FromMM, pcbnew.ToMM
PAD_CLR = 0.15
EDGE_CLR = 0.3


def box(b, grow=0.0):
    g = FM(grow)
    return (b.GetLeft() - g, b.GetTop() - g, b.GetRight() + g, b.GetBottom() + g)


def hit(a, c):
    return a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pcb = str(next((Path(a.board) / "hardware").glob("*.kicad_pcb")))
    b = pcbnew.LoadBoard(pcb)
    edge = box(b.GetBoardEdgesBoundingBox(), -EDGE_CLR)
    fps = list(b.GetFootprints())

    def silk_layer(f):
        return pcbnew.B_SilkS if f.IsFlipped() else pcbnew.F_SilkS

    copper = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    for f in fps:
        for p in f.Pads():
            for sl, cu in ((pcbnew.F_SilkS, pcbnew.F_Cu), (pcbnew.B_SilkS, pcbnew.B_Cu)):
                if p.IsOnLayer(cu):
                    copper[sl].append(box(p.GetBoundingBox(), PAD_CLR))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            for sl in copper:
                copper[sl].append(box(t.GetBoundingBox(), PAD_CLR))

    def graphics(f, sl):
        return [box(g.GetBoundingBox(), 0.1) for g in f.GraphicalItems()
                if g.GetLayer() == sl and g.GetClass() != "PCB_TEXT"]

    placed = {}            # ref -> (layer, box) of reference texts as they end up
    for f in fps:
        r = f.Reference()
        if r.GetLayer() == silk_layer(f) and r.IsVisible():
            placed[f.GetReference()] = (r.GetLayer(), box(r.GetBoundingBox()))

    def clear(f, bx, sl):
        if bx[0] < edge[0] or bx[1] < edge[1] or bx[2] > edge[2] or bx[3] > edge[3]:
            return False
        if any(hit(bx, c) for c in copper[sl]):
            return False
        for g in fps:
            if g is f:
                continue
            if any(hit(bx, c) for c in graphics(g, sl)):
                return False
            o = placed.get(g.GetReference())
            if o and o[0] == sl and hit(bx, box_grow(o[1], 0.1)):
                return False
        return True

    def box_grow(bx, d):
        return (bx[0] - FM(d), bx[1] - FM(d), bx[2] + FM(d), bx[3] + FM(d))

    moved, hidden = [], []
    for f in fps:
        r = f.Reference()
        sl = silk_layer(f)
        if r.GetLayer() != sl or not r.IsVisible():
            continue
        if clear(f, box(r.GetBoundingBox()), sl):
            continue
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
        if cy.GetWidth() == 0:
            cy = f.GetBoundingBox(False)
        cx, cyc = cy.GetCenter().x, cy.GetCenter().y
        old_pos, old_ang = r.GetPosition(), r.GetTextAngle()
        ok = False
        for ang in (0, 90):
            r.SetTextAngle(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
            tb = r.GetBoundingBox()
            hw, hh = tb.GetWidth() // 2, tb.GetHeight() // 2
            gap = FM(0.15)
            spots = [(cx, cy.GetTop() - hh - gap), (cx, cy.GetBottom() + hh + gap),
                     (cy.GetLeft() - hw - gap, cyc), (cy.GetRight() + hw + gap, cyc),
                     (cy.GetLeft() - hw, cy.GetTop() - hh - gap), (cy.GetRight() + hw, cy.GetTop() - hh - gap),
                     (cy.GetLeft() - hw, cy.GetBottom() + hh + gap), (cy.GetRight() + hw, cy.GetBottom() + hh + gap)]
            for x, y in spots:
                r.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                if clear(f, box(r.GetBoundingBox()), sl):
                    ok = True
                    break
            if ok:
                break
        if ok:
            placed[f.GetReference()] = (sl, box(r.GetBoundingBox()))
            moved.append(f.GetReference())
        else:
            r.SetPosition(old_pos)
            r.SetTextAngle(old_ang)
            r.SetVisible(False)
            placed.pop(f.GetReference(), None)
            hidden.append(f.GetReference())
    print("moved:", " ".join(moved) or "-")
    print("hidden (no clear spot):", " ".join(hidden) or "-")
    if not a.dry_run:
        b.Save(pcb)


if __name__ == "__main__":
    sys.exit(main())
