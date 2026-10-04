#!/usr/bin/env python3
"""Build Thl_Connector:Samtec_REF-182665_2x20_P2.54mm_PassThrough from the
SnapMagic (SnapEDA) download in vendor/.

The REF-182665 is a 2x20, 2.54 mm SMT socket, 3.66 mm tall, with open-bottom
contacts. It sits on top of a HAT. The long tails of a stacking socket
(e.g. Samtec SSQ-120-03-T-D) pass up through the NPTH holes, through this
socket, and out the top. -01 has two locating pegs and -03 has none; this
footprint keeps the peg holes, so it fits both.

Changes from the vendor footprint, and why:
  1. Pad numbers follow the Raspberry Pi pin that passes through each hole
     when the socket is mounted on TOP of the HAT. The vendor numbering is the
     mirror image (pins 1/2 swapped in every column), so pads are swapped
     within each column. Place at 180 deg; see tools/new_board.py.
  2. Pads are trimmed at both ends:
       - the outer edge goes from 3.56 to 3.18 mm off the centreline, so that
         at the standard HAT position (centreline 3.5 mm from the board edge)
         copper stays >= 0.3 mm from the edge;
       - the inner edge goes from 1.88 to 1.955 mm, giving 0.2 mm from the
         0.97 mm NPTH (vendor: 0.125 mm). The house .kicad_dru has a
         footprint-specific 0.2 mm NPTH rule for this.
  3. Zero-padded pad numbers ("01") become "1"; "None" holes become unnamed.
  4. Converted to the current KiCad format, with the STEP model attached.

Usage: python3 lib/footprint_src/Thl_Connector/samtec_ref_182665.py
"""

import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parents[1]
VENDOR = HERE / "vendor" / "SAMTEC_REF-182665-01.kicad_mod"
NAME = "Samtec_REF-182665_2x20_P2.54mm_PassThrough"
STEP = "Samtec_REF-182665.step"
MODEL_URI = f"${{KIPRJMOD}}/../../../lib/3dmodels/Thl_Connector.3dshapes/{STEP}"
# The SolidWorks STEP is Y-up and off-centre in X; these place it on the
# footprint (checked against the STEP vertex extents and by render).
MODEL_ROTATE = (-90, 0, 0)
MODEL_OFFSET = (4.199, 0, 0)  # STEP body is centred at x = -4.199 mm

PAD_IN, PAD_OUT = 1.955, 3.18  # pad edges, mm from the connector centreline


def convert(text):
    # 1 + 3: renumber pads, swapping the two rows of every column; 2: trim.
    def smd(m):
        n, x, y = int(m.group(1)), float(m.group(2)), float(m.group(3))
        n = n + 1 if n % 2 else n - 1
        y = (PAD_IN + PAD_OUT) / 2 * (1 if y > 0 else -1)
        return f'(pad "{n}" smd rect (at {x:g} {y:g}) (size {m.group(4)} {PAD_OUT - PAD_IN:g})'
    text, k = re.subn(r'\(pad (\d+) smd rect \(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+) [\d.]+\)', smd, text)
    if k != 40:
        sys.exit(f"expected 40 SMD pads, found {k}")
    text = text.replace("(pad None ", '(pad "" ')
    # The pin-1 dot sits beside the vendor's pin 1, which is now pin 2: move it across.
    text = re.sub(r"\(center ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\)",
                  lambda m: f"(center {m.group(1)} {-float(m.group(2)):g}) (end {m.group(3)} {-float(m.group(4)):g})",
                  text)
    return re.sub(r"^\(footprint \S+", f'(footprint "{NAME}"', text)


def main():
    import pcbnew

    with tempfile.TemporaryDirectory() as td:
        pretty = Path(td) / "tmp.pretty"
        pretty.mkdir()
        (pretty / f"{NAME}.kicad_mod").write_text(convert(VENDOR.read_text()))
        fp = pcbnew.FootprintLoad(str(pretty), NAME)
    if fp is None:
        sys.exit("KiCad could not parse the converted footprint")

    fp.SetFPID(pcbnew.LIB_ID("Thl_Connector", NAME))
    fp.SetLibDescription(
        "Samtec REF-182665-01/-03 Raspberry Pi HAT 2x20 socket, 2.54 mm, SMT bottom-entry pass-through, "
        "3.66 mm max height. From SnapMagic; renumbered for top mounting (place at 180 deg) and pads "
        "trimmed for the HAT edge and NPTH clearance. See lib/footprint_src/Thl_Connector/samtec_ref_182665.py")
    fp.SetKeywords("Samtec REF-182665 Raspberry Pi HAT GPIO 2x20 pass-through stacking SMT")
    fp.SetAttributes(pcbnew.FP_SMD)
    fp.Value().SetText(NAME)
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
            pad.SetLocalSolderMaskMargin(None)  # use the board setting, not the vendor's 0.102
    fp.Models().clear()
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = MODEL_URI
    model.m_Rotation = pcbnew.VECTOR3D(*MODEL_ROTATE)
    model.m_Offset = pcbnew.VECTOR3D(*MODEL_OFFSET)
    fp.Add3DModel(model)

    out = LIB / "footprints" / "Thl_Connector.pretty"
    out.mkdir(parents=True, exist_ok=True)
    pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(str(out), fp)
    print(f"wrote {(out / (NAME + '.kicad_mod')).relative_to(LIB.parent)}")
    if not (LIB / "3dmodels" / "Thl_Connector.3dshapes" / STEP).exists():
        print(f"warning: {STEP} missing from lib/3dmodels/Thl_Connector.3dshapes", file=sys.stderr)


if __name__ == "__main__":
    main()
