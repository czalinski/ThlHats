#!/usr/bin/env python3
"""Build Thl_Connector:RJ45_Pulse_JD0-0004NL_Horizontal.

Pulse Electronics JD0-0004NL PulseJack: RJ45 with 1:1 magnetics and green /
yellow LEDs, side entry, shielded. Land pattern from the Pulse datasheet
(JD0-0004NL rev A, sheet 4 "recommended PWB layout", component side):

  pins 1-10   0.90 mm holes, two rows 2.54 mm apart, 1.27 mm stagger
              (1, 3, 5, 7, 9 on the rear row; 2, 4, 6, 8, 10 in front)
  SH x2       1.60 mm plated shield / board-lock pins, 15.70 mm apart,
              5.84 mm in front of the rear row
  pegs x2     3.25 mm NPTH, 11.43 mm apart, 8.89 mm in front of the rear row
  11-14       1.02 mm LED pins: 11 (-0.61, 13.97), 12 (1.93, 12.27),
              13 (9.50, 13.97), 14 (12.04, 12.27)
  body        15.9 x 21.35 mm; the RJ45 opening faces +y (y = 19.64)

Pin functions (sheet 2): 1/2 TX pair, 3/5 RX pair, 4 centre taps, 6 not
connected, 7-10 PoE spare-pair pins, 11/12 green LED -/+, 13/14 yellow LED -/+.
Origin at pin 1. No 3D model: Pulse supplies IGES only (repo needs STEP).

Usage: python3 lib/footprint_src/Thl_Connector/pulse_jd0_0004nl.py
"""
import uuid
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "footprints" / "Thl_Connector.pretty"
NAME = "RJ45_Pulse_JD0-0004NL_Horizontal"
X0, X1, Y0, Y1 = -2.235, 13.665, -1.71, 19.64


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


def pad(num, x, y, size, drill, kind="thru_hole", shape="circle"):
    layers = '"*.Cu" "*.Mask"'
    return (f'\t(pad "{num}" {kind} {shape}\n\t\t(at {x:g} {y:g})\n\t\t(size {size:g} {size:g})\n'
            f'\t\t(drill {drill:g})\n\t\t(layers {layers})\n\t\t(remove_unused_layers no)\n\t\t(uuid "{u()}")\n\t)\n')


def build():
    mid = (X0 + X1) / 2
    s = f'(footprint "{NAME}"\n\t(version 20241229)\n\t(generator "pulse_jd0_0004nl.py")\n\t(layer "F.Cu")\n'
    s += text("Reference", "REF**", mid, Y0 - 2.5, "F.SilkS")
    s += text("Value", NAME, mid, Y1 + 1.5, "F.Fab")
    s += text("Datasheet", "https://productfinder.pulseeng.com/doc_type/WEB301/doc_num/JD0-0004NL-01/doc_part/JD0-0004NL.pdf",
              0, 0, "F.Fab", True)
    s += ('\t(descr "Pulse JD0-0004NL RJ45 with magnetics and LEDs, 10/100BASE-TX, side entry, shielded; '
          'land pattern from datasheet rev A sheet 4")\n')
    s += '\t(tags "RJ45 magjack Pulse JD0-0004NL")\n\t(attr through_hole)\n'
    s += rect(X0, Y0, X1, Y1, "F.Fab", 0.1)
    # silk: rear edge and the sides up to the shield pins, then the sides below the pegs
    s += line(X0 - 0.11, Y0 - 0.11, X1 + 0.11, Y0 - 0.11, "F.SilkS", 0.12)
    for x in (X0 - 0.11, X1 + 0.11):
        s += line(x, Y0 - 0.11, x, 4.5, "F.SilkS", 0.12)
        s += line(x, 7.3, x, Y1 - 0.6, "F.SilkS", 0.12)
    s += line(-0.5, Y0 - 0.6, 0.5, Y0 - 0.6, "F.SilkS", 0.12)          # pin 1 mark behind pin 1
    s += rect(X0 - 0.5, Y0 - 0.5, X1 + 0.5, Y1, "F.CrtYd", 0.05)       # front face = board edge
    s += (f'\t(fp_text user "${{REFERENCE}}"\n\t\t(at {mid:g} {(Y0 + Y1) / 2:g} 0)\n\t\t(layer "F.Fab")\n'
          f'\t\t(uuid "{u()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')
    for k in range(10):
        num = k + 1
        x = k * 1.27
        y = 0.0 if num % 2 else 2.54
        s += pad(num, x, y, 1.4, 0.9, shape="rect" if num == 1 else "circle")
    for num, x, y in ((11, -0.61, 13.97), (12, 1.93, 12.27), (13, 9.50, 13.97), (14, 12.04, 12.27)):
        s += pad(num, x, y, 1.6, 1.02)
    for x in (-2.135, 13.565):
        s += pad("SH", x, 5.84, 2.4, 1.6)
    for x in (0.0, 11.43):
        s += (f'\t(pad "" np_thru_hole circle\n\t\t(at {x:g} 8.89)\n\t\t(size 3.25 3.25)\n\t\t(drill 3.25)\n'
              f'\t\t(layers "*.Cu" "*.Mask")\n\t\t(uuid "{u()}")\n\t)\n')
    s += "\t(embedded_fonts no)\n)\n"
    (LIB / f"{NAME}.kicad_mod").write_text(s)
    return NAME


if __name__ == "__main__":
    print(build())
