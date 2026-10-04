#!/usr/bin/env python3
"""Generate the Samtec REF-182665 Raspberry Pi HAT pass-through socket.

The REF-182665 is a 2x20, 2.54 mm SMT socket, 3.51 mm tall, with open-bottom
contacts. It sits on top of a HAT. The long tails of a stacking socket
(e.g. Samtec SSQ-120-03-T-D) pass up through holes in the HAT, through this
socket, and out the top into the next board. -01 has locating pegs and -03
has none; this footprint is for -03.

Pad geometry is NOT from the Samtec drawing yet. It started from a footprint
measured by hand from eBay samples and was then constrained:
  - the holes are non-plated, so solder cannot wick in and block the pins;
  - SMD pads stop 0.5 mm short of each hole;
  - at the standard HAT header position (hole rows 2.23 / 4.77 mm from the
    board edge) the outer pad edge must stay >= 0.3 mm inside the edge.
Replace the constants below with Samtec drawing values when available.

Usage: python3 lib/footprint_src/Thl_Connector/samtec_ref_182665.py
Writes lib/footprints/Thl_Connector.pretty/<NAME>.kicad_mod and
lib/3dmodels/Thl_Connector.3dshapes/<NAME>.wrl.
"""

import math
import uuid
from pathlib import Path

LIB = Path(__file__).resolve().parents[2]
NAME = "Samtec_REF-182665-03_2x20_P2.54mm_PassThrough"
MODEL_URI = f"${{KIPRJMOD}}/../../../lib/3dmodels/Thl_Connector.3dshapes/{NAME}.wrl"

P = 2.54
HOLE = 1.0               # NPTH; stacking pins are 0.64 mm square (0.9 mm diagonal)
PAD_W = 1.2              # tails are about 0.6 mm wide
PAD_IN = 1.0             # inner pad edge, from its hole centre
PAD_OUT = 3.15 - P / 2   # outer pad edge, from its hole centre (3.15 mm from connector centreline)
BODY_W, BODY_L, BODY_H = 5.0, 51.0, 3.51


def uid():
    return str(uuid.uuid4())


def main():
    cx, cy = P / 2, 19 * P / 2  # body centre; pin 1 at the origin
    items = []

    def line(x1, y1, x2, y2, layer, w):
        items.append(f'\t(fp_line\n\t\t(start {x1:g} {y1:g})\n\t\t(end {x2:g} {y2:g})\n'
                     f'\t\t(stroke\n\t\t\t(width {w:g})\n\t\t\t(type solid)\n\t\t)\n'
                     f'\t\t(layer "{layer}")\n\t\t(uuid "{uid()}")\n\t)')

    def prop(kind, val, x, y, layer, hide=False):
        h = "\n\t\t(hide yes)" if hide else ""
        return (f'\t(property "{kind}" "{val}"\n\t\t(at {x:g} {y:g} 0)\n\t\t(layer "{layer}"){h}\n'
                f'\t\t(uuid "{uid()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
                f'\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)')

    bx1, bx2 = cx - BODY_W / 2, cx + BODY_W / 2
    by1, by2 = cy - BODY_L / 2, cy + BODY_L / 2
    pad_l = PAD_OUT - PAD_IN
    x_odd = -(PAD_IN + pad_l / 2)
    x_even = P + PAD_IN + pad_l / 2

    props = [
        prop("Reference", "REF**", cx, by1 - 1.5, "F.SilkS"),
        prop("Value", NAME, cx, by2 + 1.5, "F.Fab"),
        prop("Datasheet", "", 0, 0, "F.Fab", True),
        prop("Description", "", 0, 0, "F.Fab", True),
    ]
    items.append(f'\t(fp_text user "${{REFERENCE}}"\n\t\t(at {cx:g} {cy:g} 90)\n\t\t(layer "F.Fab")\n'
                 f'\t\t(uuid "{uid()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
                 f'\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)')

    # Fab outline with a pin-1 chamfer.
    c = 1.0
    line(bx1 + c, by1, bx2, by1, "F.Fab", 0.1)
    line(bx2, by1, bx2, by2, "F.Fab", 0.1)
    line(bx2, by2, bx1, by2, "F.Fab", 0.1)
    line(bx1, by2, bx1, by1 + c, "F.Fab", 0.1)
    line(bx1, by1 + c, bx1 + c, by1, "F.Fab", 0.1)
    # Silk: body ends only (the long sides carry pads), plus a pin-1 tick.
    o, s = 0.11, 0.12
    for y in (by1 - o, by2 + o):
        line(bx1 - o, y, bx2 + o, y, "F.SilkS", s)
    line(-PAD_OUT - 0.3, -PAD_W / 2, -PAD_OUT - 0.3, PAD_W / 2, "F.SilkS", s)
    # Courtyard: pads and body + 0.25, on a 0.05 grid.
    def lo(v):
        return math.floor(round(v * 20, 6)) / 20

    def hi(v):
        return math.ceil(round(v * 20, 6)) / 20

    l, r = lo(min(-PAD_OUT, bx1) - 0.25), hi(max(P + PAD_OUT, bx2) + 0.25)
    t, b = lo(by1 - 0.25), hi(by2 + 0.25)
    for a in ((l, t, r, t), (r, t, r, b), (r, b, l, b), (l, b, l, t)):
        line(*a, "F.CrtYd", 0.05)

    for i in range(20):
        y = i * P
        for num, x, hx in ((2 * i + 1, x_odd, 0.0), (2 * i + 2, x_even, P)):
            items.append(f'\t(pad "{num}" smd rect\n\t\t(at {x:g} {y:g})\n\t\t(size {pad_l:g} {PAD_W:g})\n'
                         f'\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n\t\t(uuid "{uid()}")\n\t)')
            items.append(f'\t(pad "" np_thru_hole circle\n\t\t(at {hx:g} {y:g})\n\t\t(size {HOLE:g} {HOLE:g})\n'
                         f'\t\t(drill {HOLE:g})\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(uuid "{uid()}")\n\t)')

    text = (f'(footprint "{NAME}"\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
            '\t(layer "F.Cu")\n'
            '\t(descr "Samtec REF-182665-03 Raspberry Pi HAT 2x20 socket, 2.54 mm, SMT bottom-entry pass-through, '
            '3.51 mm profile, no pegs. Pads provisional (hand-measured, edge-constrained); verify against the Samtec drawing. '
            'Mount on top at 90 deg so holes align with the RPi header.")\n'
            '\t(tags "Samtec REF-182665 Raspberry Pi HAT GPIO 2x20 pass-through stacking SMT")\n'
            + "\n".join(props) + "\n\t(attr smd)\n" + "\n".join(items) + "\n\t(embedded_fonts no)\n"
            f'\t(model "{MODEL_URI}"\n\t\t(offset\n\t\t\t(xyz 0 0 0)\n\t\t)\n\t\t(scale\n\t\t\t(xyz 1 1 1)\n'
            '\t\t)\n\t\t(rotate\n\t\t\t(xyz 0 0 0)\n\t\t)\n\t)\n)\n')
    fp = LIB / "footprints" / "Thl_Connector.pretty" / f"{NAME}.kicad_mod"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(text)

    # Simplified VRML body. KiCad VRML units are 0.1 in; VRML +Y is board -Y.
    k = 1 / 2.54

    def box(x, y, z, sx, sy, sz, rgb):
        return (f"Transform {{ translation {x*k:.4f} {-y*k:.4f} {z*k:.4f} children [ Shape {{ "
                f"appearance Appearance {{ material Material {{ diffuseColor {rgb} }} }} "
                f"geometry Box {{ size {sx*k:.4f} {sy*k:.4f} {sz*k:.4f} }} }} ] }}\n")

    w = f"#VRML V2.0 utf8\n# Simplified Samtec REF-182665 body {BODY_W} x {BODY_L} x {BODY_H} mm (ThlHats)\n"
    w += box(cx, cy, BODY_H / 2, BODY_W, BODY_L, BODY_H, "0.08 0.08 0.08")
    for i in range(20):
        for x in (x_odd, x_even):
            w += box(x, i * P, 0.1, pad_l * 0.8, 0.6, 0.2, "0.85 0.75 0.3")
    wrl = LIB / "3dmodels" / "Thl_Connector.3dshapes" / f"{NAME}.wrl"
    wrl.parent.mkdir(parents=True, exist_ok=True)
    wrl.write_text(w)
    print(f"wrote {fp.relative_to(LIB.parent)}\nwrote {wrl.relative_to(LIB.parent)}")


if __name__ == "__main__":
    main()
