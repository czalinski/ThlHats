#!/usr/bin/env python3
"""Generate Vishay_SOP-4_4.4x4.9mm_P2.54mm_HandSolder.kicad_mod (VOM1271 etc.).

From the VOM1271 datasheet (doc 83469 rev 1.6) package drawing: body
4.42 x 4.92 mm max, pitch 2.54 mm, lead tips 6.95 mm. Recommended land:
0.9 x 1.15 mm pads, 5.1 mm inner / 7.4 mm outer edge. Hand-solder version
extends each pad 0.65 mm outwards (pad 0.9 x 1.8 mm, outer edge 8.7 mm).
Pins: 1 LED anode, 2 LED cathode, 3 output -, 4 output +.

  python3 vishay_sop4.py > Vishay_SOP-4_4.4x4.9mm_P2.54mm_HandSolder.kicad_mod
"""
import uuid

NAME = "Vishay_SOP-4_4.4x4.9mm_P2.54mm_HandSolder"
PX = (5.1 / 2) + 1.8 / 2  # pad centre: inner edge 2.55 + half length
PAD = (1.8, 0.9)
# pin -> (x, y). Datasheet top view: pins 1,2 on one edge (LED), 4 opposite 1,
# 3 opposite 2. KiCad orientation: 1 top-left, 2 bottom-left, 3 bottom-right, 4 top-right.
PINS = {"1": (-PX, -1.27), "2": (-PX, 1.27), "3": (PX, 1.27), "4": (PX, -1.27)}
BX, BY = 4.92 / 2, 4.57 / 2  # body half sizes: 4.92 max along the pin row (y), 4.57 along the leads (x)


def u():
    return str(uuid.uuid4())


def line(x1, y1, x2, y2, layer, w):
    return (f'\t(fp_line\n\t\t(start {x1:g} {y1:g})\n\t\t(end {x2:g} {y2:g})\n\t\t(stroke\n\t\t\t(width {w:g})\n'
            f'\t\t\t(type solid)\n\t\t)\n\t\t(layer "{layer}")\n\t\t(uuid "{u()}")\n\t)\n')


def rect(x1, y1, x2, y2, layer, w):
    return "".join(line(*a, layer, w) for a in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)))


out = [f'(footprint "{NAME}"\n\t(version 20241229)\n\t(generator "vishay_sop4.py")\n\t(layer "F.Cu")\n'
       '\t(descr "Vishay SOP-4, 4.4x4.9 mm body, 2.54 mm pitch, hand-solder pads (VOM1271, doc 83469)")\n'
       '\t(tags "SOP-4 VOM1271 photovoltaic optocoupler")\n']
for name, val, y, lay in (("Reference", "REF**", -3.6, "F.SilkS"), ("Value", NAME, 3.6, "F.Fab")):
    out.append(f'\t(property "{name}" "{val}"\n\t\t(at 0 {y:g} 0)\n\t\t(layer "{lay}")\n\t\t(uuid "{u()}")\n'
               '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')
out.append('\t(attr smd)\n')
out.append(rect(-BY, -BX, BY, BX, "F.Fab", 0.1))  # body
out.append(line(-BY + 0.12, -BX - 0.12, BY - 0.12, -BX - 0.12, "F.SilkS", 0.12))
out.append(line(-BY + 0.12, BX + 0.12, BY - 0.12, BX + 0.12, "F.SilkS", 0.12))
out.append(line(-PX - 0.9, -2.4, -BY - 0.12, -2.4, "F.SilkS", 0.12))  # pin 1 marker
cx = PX + PAD[0] / 2 + 0.25
out.append(rect(-cx, -BX - 0.25, cx, BX + 0.25, "F.CrtYd", 0.05))
for n, (x, y) in PINS.items():
    out.append(f'\t(pad "{n}" smd roundrect\n\t\t(at {x:g} {y:g})\n\t\t(size {PAD[0]:g} {PAD[1]:g})\n'
               f'\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n\t\t(roundrect_rratio 0.25)\n\t\t(uuid "{u()}")\n\t)\n')
out.append('\t(embedded_fonts no)\n)\n')
print("".join(out), end="")
