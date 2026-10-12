#!/usr/bin/env python3
"""Build Thl_Connector:Amphenol_T821110A1R100CEU_2x05_P2.54mm_Horizontal.

Amphenol T821 right-angle shrouded 2x5 box header (serial-card J20/J21/J30/
J31). Pads, outline and courtyard are KiCad's stock
Connector_IDC:IDC-Header_2x05_P2.54mm_Horizontal (it matches Amphenol's land
pattern: same pin grid, body front 1.84 vs 1.70 mm past the second row); only
the 3D model changes. The stock model is 11.1 mm tall; the vendor one
(SamacSys LIB_T821110A1R100CEU.zip, IPC name SHDRRA10W64P254X254_2X5_2032X900X915P)
is 8.86 mm, which is what decides the fit under the next card in the stack.

The vendor STEP may not be redistributed (SamacSys licence): it stays local,
git-ignored and listed in lib/3dmodels/LOCAL_ONLY.txt. Placement: the vendor
footprint has pin 2 at (0, -2.54) and its model at (5.11, 4.24, 4.46) mm; the
stock footprint has pin 2 at (2.54, 0), so the model turns 90 degrees (KiCad rotates by the negative angle).

  python3 lib/footprint_src/Thl_Connector/amphenol_t821.py
"""
import re
from pathlib import Path

LIB = Path(__file__).resolve().parents[2]
SRC = LIB / "footprints/Connector_IDC.pretty/IDC-Header_2x05_P2.54mm_Horizontal.kicad_mod"
NAME = "Amphenol_T821110A1R100CEU_2x05_P2.54mm_Horizontal"
DST = LIB / f"footprints/Thl_Connector.pretty/{NAME}.kicad_mod"
MODEL = "${KIPRJMOD}/../../../lib/3dmodels/Thl_Connector.3dshapes/Amphenol_T821110A1R100CEU.step"


def main():
    s = SRC.read_text()
    s = s.replace('(footprint "IDC-Header_2x05_P2.54mm_Horizontal"', f'(footprint "{NAME}"', 1)
    s = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{NAME}"', s, count=1)
    s = re.sub(r'\(descr "[^"]*"\)', '(descr "Amphenol T821110A1R100CEU right-angle shrouded box header 2x5, '
               '2.54 mm (stock IDC-Header_2x05_P2.54mm_Horizontal pads, vendor 3D model)")', s, count=1)
    model = (f'\t(model "{MODEL}"\n\t\t(offset\n\t\t\t(xyz 4.24 -5.11 4.46)\n\t\t)\n\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n'
             '\t\t(rotate\n\t\t\t(xyz 0 0 90)\n\t\t)\n\t)\n')
    s = re.sub(r'\t\(model "[^"]*"\n(?:\t\t.*\n)*?\t\)\n', model, s, count=1)
    DST.write_text(s)
    print("wrote", DST)


if __name__ == "__main__":
    main()
