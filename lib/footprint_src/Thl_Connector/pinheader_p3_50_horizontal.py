#!/usr/bin/env python3
"""Build Thl_Connector:PinHeader_1x13_P3.50mm_Horizontal.

Thirteen right-angle pins at 3.5 mm pitch that plug into the wire entries of a
13-way 3.5 mm screw terminal (Waveshare High-Precision AD HAT, probe-helper
board). There is no common unshrouded 3.5 mm right-angle header (the Phoenix
MC 1,5-G-3,5 headers are shrouded), so the part is single pins cut from a
2.54 mm right-angle strip: each plastic body is 2.5 mm wide and fits the
3.5 mm pitch. 0.8 mm solid wire bent 90 degrees also fits the 1.0 mm holes.

Geometry per pin as KiCad's PinHeader_1x01_P2.54mm_Horizontal, turned so
that the pins point to +y: plastic body from y = 1.5 to 4.04, pin tip at
y = 10.04. Pad 1 (rectangular) at the origin, pads along +x. Meant for the
bottom side: flipped top/bottom, the pins point to -y with pad 1 still on the
left (seen from the top). The 3D model is the stock single pin, placed 13
times.

  python3 lib/footprint_src/Thl_Connector/pinheader_p3_50_horizontal.py
"""
import uuid
from pathlib import Path

LIB = Path(__file__).resolve().parents[2]
N, P = 13, 3.5
NAME = f"PinHeader_1x{N}_P3.50mm_Horizontal"
FP_DIR = LIB / "footprints/Thl_Connector.pretty"
MODEL = "${KIPRJMOD}/../../../lib/3dmodels/Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x01_P2.54mm_Horizontal.step"


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


def footprint():
    w = (N - 1) * P
    s = f'(footprint "{NAME}"\n\t(version 20241229)\n\t(generator "pinheader_p3_50_horizontal.py")\n\t(layer "F.Cu")\n'
    s += text("Reference", "REF**", w / 2, -2.5, "F.SilkS")
    s += text("Value", NAME, w / 2, 12.0, "F.Fab")
    s += text("Datasheet", "", 0, 0, "F.Fab", True)
    s += (f'\t(descr "{N} single right-angle pins (cut from a 2.54 mm right-angle header) at 3.5 mm pitch, '
          'to plug into the wire entries of a 3.5 mm screw terminal; pins point to +y (mount on the bottom side)")\n')
    s += '\t(tags "pin header right angle 3.5mm screw terminal adapter")\n\t(attr through_hole)\n'
    for k in range(N):
        x = k * P
        s += rect(x - 1.27, 1.5, x + 1.27, 4.04, "F.Fab", 0.1)       # plastic body
        s += rect(x - 0.32, 4.04, x + 0.32, 10.04, "F.Fab", 0.1)     # pin
        s += line(x, 0, x, 1.5, "F.Fab", 0.1)
        s += rect(x - 1.38, 1.39, x + 1.38, 3.7, "F.SilkS", 0.12)
        shape = "rect" if k == 0 else "circle"
        s += (f'\t(pad "{k + 1}" thru_hole {shape}\n\t\t(at {x:g} 0)\n\t\t(size 1.8 1.8)\n'
              f'\t\t(drill 1)\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(remove_unused_layers no)\n\t\t(uuid "{u()}")\n\t)\n')
    s += rect(-1.77, -1.15, w + 1.77, 10.54, "F.CrtYd", 0.05)
    s += (f'\t(fp_text user "${{REFERENCE}}"\n\t\t(at {w / 2:g} 2.77 0)\n\t\t(layer "F.Fab")\n\t\t(uuid "{u()}")\n'
          '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')
    for k in range(N):
        s += (f'\t(model "{MODEL}"\n\t\t(offset\n\t\t\t(xyz {k * P:g} 0 0)\n\t\t)\n\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n'
              f'\t\t(rotate\n\t\t\t(xyz 0 0 90)\n\t\t)\n\t)\n')
    s += "\t(embedded_fonts no)\n)\n"
    FP_DIR.mkdir(parents=True, exist_ok=True)
    (FP_DIR / f"{NAME}.kicad_mod").write_text(s)


if __name__ == "__main__":
    footprint()
    print("wrote", FP_DIR / f"{NAME}.kicad_mod")
