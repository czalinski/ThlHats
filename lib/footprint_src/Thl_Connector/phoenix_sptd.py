#!/usr/bin/env python3
"""Build Thl_Connector:PhoenixContact_SPTD_1,5_{n}-H-3,5_2x{n}_P3.5mm_Horizontal.

Phoenix Contact SPTD 1,5/ n-H-3,5: double-level push-in PCB terminal block,
3.5 mm pitch, horizontal wire entry, 10 A / 200 V (UL 150 V), 0.14-1.5 mm2.
Dimensions from the Phoenix datasheet drawing for 1841513 (SPTD 1,5/ 4-H-3,5):
  - body 18 mm deep, 24.2 mm tall, length a + 5 with a = (n - 1) x 3.5 mm;
  - two pin rows 9.35 mm apart; the front row (lower level) is 6.9 mm behind
    the front face (wire entry); 1.75 mm from the rear row to the back;
  - holes 1.3 mm, pins 0.6 x 1.0 mm, 3.5 mm solder pins.

Pad numbering (matches Connector_Generic:Conn_02xNN_Top_Bottom):
  1 .. n      front row = LOWER level (signal, by the ThlHats convention)
  n+1 .. 2n   rear row  = UPPER level (ground / return)
Footprint origin at pad 1; the front face (wire entry) points to +y.
No 3D model yet.

Order numbers: 3 pos 1841500, 4 pos 1841513, 5 pos 1841526, 6 pos 1841539,
8 pos 1841555.

Usage: python3 lib/footprint_src/Thl_Connector/phoenix_sptd.py
"""
import uuid
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "footprints" / "Thl_Connector.pretty"
PITCH, ROWS_DY, FRONT, BACK = 3.5, 9.35, 6.9, 1.75
DRILL, PAD = 1.3, 2.0
SIZES = {3: "1841500", 4: "1841513", 5: "1841526", 6: "1841539", 8: "1841555"}


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


def build(n, mpn):
    name = f"PhoenixContact_SPTD_1,5_{n}-H-3,5_2x{n:02d}_P3.5mm_Horizontal"
    a = (n - 1) * PITCH
    x0, x1 = -2.5, a + 2.5                    # body length a + 5
    y0, y1 = -(ROWS_DY + BACK), FRONT          # back .. front face
    s = (f'(footprint "{name}"\n\t(version 20241229)\n\t(generator "phoenix_sptd.py")\n\t(layer "F.Cu")\n')
    s += text("Reference", "REF**", a / 2, y0 - 1.5, "F.SilkS")
    s += text("Value", name, a / 2, y1 + 1.5, "F.Fab")
    s += text("Datasheet", "", 0, 0, "F.Fab", True)   # product page: phoenixcontact.com/en-pc/products/<mpn>
    s += (f'\t(descr "Phoenix Contact SPTD 1,5/ {n}-H-3,5 ({mpn}), double-level push-in PCB terminal, 3.5 mm pitch, '
          f'2x{n}; front row (pads 1-{n}) lower level, rear row (pads {n + 1}-{2 * n}) upper level")\n')
    s += f'\t(tags "Phoenix SPTD push-in double level terminal 3.5mm")\n\t(attr through_hole)\n'
    s += rect(x0, y0, x1, y1, "F.Fab", 0.1)
    s += rect(x0 - 0.11, y0 - 0.11, x1 + 0.11, y1 + 0.11, "F.SilkS", 0.12)
    s += line(-1.0, y1 + 0.6, 1.0, y1 + 0.6, "F.SilkS", 0.12)            # pin 1 mark at the front
    s += rect(x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5, "F.CrtYd", 0.05)
    s += (f'\t(fp_text user "${{REFERENCE}}"\n\t\t(at {a / 2:g} {(y0 + y1) / 2:g} 0)\n\t\t(layer "F.Fab")\n'
          f'\t\t(uuid "{u()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')
    for row, dy in ((0, 0.0), (1, -ROWS_DY)):
        for k in range(n):
            num = k + 1 + row * n
            shape = "rect" if num == 1 else "circle"
            s += (f'\t(pad "{num}" thru_hole {shape}\n\t\t(at {k * PITCH:g} {dy:g})\n\t\t(size {PAD:g} {PAD:g})\n'
                  f'\t\t(drill {DRILL:g})\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(remove_unused_layers no)\n\t\t(uuid "{u()}")\n\t)\n')
    s += "\t(embedded_fonts no)\n)\n"
    (LIB / f"{name}.kicad_mod").write_text(s)
    return name


if __name__ == "__main__":
    for n, mpn in SIZES.items():
        print(build(n, mpn))
