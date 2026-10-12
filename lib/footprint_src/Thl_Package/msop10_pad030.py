#!/usr/bin/env python3
"""Build Thl_Package:MSOP-10_3x3mm_P0.5mm_Pad0.30 (io-card U92, MCP4728).

KiCad's stock Package_SO:MSOP-10_3x3mm_P0.5mm with the pads narrowed from
0.35 to 0.30 mm (Microchip's MSOP-10 "UN" land pattern: X1 = 0.30 mm max).
That leaves 0.20 mm between pads, enough for a solder-mask web at PCBWay
(green mask needs >= 0.19 mm; they flagged the stock 0.15 mm, order
W517176ASE106). Everything else is stock.

  python3 lib/footprint_src/Thl_Package/msop10_pad030.py
"""
import re
from pathlib import Path

LIB = Path(__file__).resolve().parents[2]
SRC = LIB / "footprints/Package_SO.pretty/MSOP-10_3x3mm_P0.5mm.kicad_mod"
NAME = "MSOP-10_3x3mm_P0.5mm_Pad0.30"
DST = LIB / f"footprints/Thl_Package.pretty/{NAME}.kicad_mod"


def main():
    s = SRC.read_text()
    s = s.replace('(footprint "MSOP-10_3x3mm_P0.5mm"', f'(footprint "{NAME}"', 1)
    s = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{NAME}"', s, count=1)
    s = re.sub(r'\(descr "([^"]*)"\)', r'(descr "\1; pads narrowed to 0.30 mm (Microchip UN land) for a 0.20 mm solder-mask web")', s, count=1)
    s, n = re.subn(r'\(size 1\.5 0\.35\)', '(size 1.5 0.3)', s)
    assert n == 10, n
    DST.write_text(s)
    print("wrote", DST)


if __name__ == "__main__":
    main()
