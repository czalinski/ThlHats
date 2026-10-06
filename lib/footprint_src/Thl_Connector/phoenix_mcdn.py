#!/usr/bin/env python3
"""Build Thl_Connector:PhoenixContact_MCDN_1,5_4-G1-3,5_2x04_P3.5mm_Horizontal.

Phoenix Contact MCDN 1,5/ 4-G1-3,5 P26 THR (item 1953732): double-level PCB
header for MC 1,5 plugs, 3.5 mm pitch, 2 x 4, horizontal, 8 A / 160 V (III/2).
can-ssr uses it as CAN IN + CAN OUT in one footprint (stack interface,
docs/requirements.md 4.4); both levels carry the same four nets.

Geometry from the Phoenix data (width 15.4 mm, length 13.3 mm, 1.4 mm holes,
3.5 mm pitch, rows 3.5 mm apart) as laid out in Phoenix's SamacSys CAD
package for 1953732 (user download, 2026-10-06). That package's licence forbids
redistribution as a library component, so this file is our own drawing of the
same dimensions, and the STEP model stays local (lib/3dmodels/LOCAL_ONLY.txt).

  pads 1-4  rear row  (pad 1 square)
  pads 5-8  front row, 3.5 mm toward the mating face
  pad n and pad n+4 are the same column.
Footprint origin at pad 1; the mating face points to +y (y = 12.8 mm) and goes
at the board edge. Which row feeds which level is not verified here: on can-ssr
both levels are paralleled, so it does not matter electrically.

Usage: python3 lib/footprint_src/Thl_Connector/phoenix_mcdn.py
"""
import uuid
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "footprints" / "Thl_Connector.pretty"
NAME = "PhoenixContact_MCDN_1,5_4-G1-3,5_2x04_P3.5mm_Horizontal"
MODEL = "${KIPRJMOD}/../../../lib/3dmodels/Thl_Connector.3dshapes/PhoenixContact_MCDN_1,5_4-G1-3,5.step"
PITCH, ROWS_DY = 3.5, 3.5
DRILL, PAD = 1.4, 2.1
X0, X1, Y0, Y1 = -2.45, 12.95, -0.5, 12.8      # body: 15.4 wide, 13.3 long; front face at Y1


def u():
    return str(uuid.uuid4())


def line(x0, y0, x1, y1, layer, w):
    return (f'\t(fp_line\n\t\t(start {x0:g} {y0:g})\n\t\t(end {x1:g} {y1:g})\n'
            f'\t\t(stroke\n\t\t\t(width {w:g})\n\t\t\t(type solid)\n\t\t)\n\t\t(layer "{layer}")\n\t\t(uuid "{u()}")\n\t)\n')


def rect(x0, y0, x1, y1, layer, w):
    return (line(x0, y0, x1, y0, layer, w) + line(x1, y0, x1, y1, layer, w) +
            line(x1, y1, x0, y1, layer, w) + line(x0, y1, x0, y0, layer, w))


def text(kind, txt, x, y, layer, hide=False):
    h = "\n\t\t(hide yes)" if hide else ""
    return (f'\t(property "{kind}" "{txt}"\n\t\t(at {x:g} {y:g} 0)\n\t\t(layer "{layer}"){h}\n\t\t(uuid "{u()}")\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')


def build():
    mid = (X0 + X1) / 2
    s = f'(footprint "{NAME}"\n\t(version 20241229)\n\t(generator "phoenix_mcdn.py")\n\t(layer "F.Cu")\n'
    s += text("Reference", "REF**", mid, Y0 - 1.5, "F.SilkS")
    s += text("Value", NAME, mid, Y1 + 1.5, "F.Fab")
    s += text("Datasheet", "", 0, 0, "F.Fab", True)
    s += ('\t(descr "Phoenix Contact MCDN 1,5/ 4-G1-3,5 P26 THR (1953732), double-level PCB header for MC 1,5 '
          'plugs, 3.5 mm pitch, 2x4, horizontal; pads 1-4 rear row, 5-8 front row (same columns)")\n')
    s += '\t(tags "Phoenix MCDN double level header 3.5mm")\n\t(attr through_hole)\n'
    s += rect(X0, Y0, X1, Y1, "F.Fab", 0.1)
    # sides only: the pads overhang the rear of the body, and the front face is the board edge
    s += line(X0 - 0.11, 1.4, X0 - 0.11, Y1 - 0.6, "F.SilkS", 0.12)
    s += line(X1 + 0.11, 1.4, X1 + 0.11, Y1 - 0.6, "F.SilkS", 0.12)
    s += line(X0 - 0.11, Y1 - 0.6, X0 + 1.2, Y1 - 0.6, "F.SilkS", 0.12)      # pin 1 mark: front corner
    s += rect(X0 - 0.25, Y0 - 0.25, X1 + 0.25, Y1, "F.CrtYd", 0.05)
    s += (f'\t(fp_text user "${{REFERENCE}}"\n\t\t(at {mid:g} {(Y0 + Y1) / 2:g} 0)\n\t\t(layer "F.Fab")\n'
          f'\t\t(uuid "{u()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')
    for row in (0, 1):
        for k in range(4):
            num = k + 1 + row * 4
            shape = "rect" if num == 1 else "circle"
            s += (f'\t(pad "{num}" thru_hole {shape}\n\t\t(at {k * PITCH:g} {row * ROWS_DY:g})\n\t\t(size {PAD:g} {PAD:g})\n'
                  f'\t\t(drill {DRILL:g})\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(remove_unused_layers no)\n\t\t(uuid "{u()}")\n\t)\n')
    # Model placement copied from Phoenix's package (not checked by render)
    s += (f'\t(model "{MODEL}"\n\t\t(offset\n\t\t\t(xyz 2.33 -19.82 -2.32)\n\t\t)\n\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n'
          f'\t\t(rotate\n\t\t\t(xyz -90 0 -90)\n\t\t)\n\t)\n')
    s += "\t(embedded_fonts no)\n)\n"
    (LIB / f"{NAME}.kicad_mod").write_text(s)
    return NAME


if __name__ == "__main__":
    print(build())
