#!/usr/bin/env python3
"""Generate fabrication outputs for a board.

Writes boards/<name>/hardware/fab/rev<REV>/:
  gerbers/                Gerbers + Excellon drill (Protel extensions)
  <name>-rev<REV>-gerbers.zip   upload this to the fab
  <name>-bom.csv          BOM in PCBWay's assembly template layout
  <name>-centroid.csv     pick-and-place (centroid) file for PCBWay assembly
  <name>-schematic.pdf
  <name>.step             3D model of the assembled board

The board is checked with tools/check_board.py first; pass --force to build
outputs anyway. The revision comes from the PCB title block (--rev overrides).

Usage:
  tools/fab.py boards/<name> [--rev B] [--force]
"""

import argparse
import csv
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_board  # noqa: E402

LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"


def run(*args):
    r = subprocess.run(["kicad-cli", *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"kicad-cli {' '.join(args)} failed:\n{r.stdout}{r.stderr}")


def write_bom(pcb, path):
    """BOM in PCBWay's assembly template column order, grouped by part.

    Built from the PCB (symbol fields are copied to footprints by Update PCB
    from Schematic) so the SMD/THT type comes from the footprint attributes.
    """
    import pcbnew
    board = pcbnew.LoadBoard(str(pcb))
    groups = {}
    for fp in board.GetFootprints():
        attrs = fp.GetAttributes()
        if attrs & pcbnew.FP_BOARD_ONLY or fp.IsExcludedFromBOM() or fp.IsDNP():
            continue

        def field(n):
            return fp.GetFieldText(n) if fp.HasField(n) else ""

        kind = "SMD" if attrs & pcbnew.FP_SMD else "THT" if attrs & pcbnew.FP_THROUGH_HOLE else "Other"
        key = (field("Manufacturer"), field("MPN"), fp.GetValue(),
               fp.GetFPID().GetLibItemName().wx_str(), kind)
        groups.setdefault(key, []).append(fp.GetReference())

    def refkey(r):
        m = re.match(r"([A-Za-z#]+)(\d*)", r)
        return (m.group(1), int(m.group(2) or 0))

    rows = sorted(groups.items(), key=lambda kv: refkey(min(kv[1], key=refkey)))
    missing = [refs for (mfr, mpn, *_), refs in rows if not mpn]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Item #", "Designator", "Qty", "Manufacturer", "Mfg Part #",
                    "Description / Value", "Package/Footprint", "Type", "Your Instructions / Notes"])
        for i, ((mfr, mpn, value, footprint, kind), refs) in enumerate(rows, 1):
            refs.sort(key=refkey)
            w.writerow([i, ",".join(refs), len(refs), mfr, mpn, value, footprint, kind, ""])
    if missing:
        print("warning: no MPN for " + "; ".join(",".join(r) for r in missing), file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--rev")
    ap.add_argument("--force", action="store_true", help="skip the board check")
    a = ap.parse_args()

    bdir = Path(a.board).resolve()
    hw = bdir / "hardware"
    pro = next(hw.glob("*.kicad_pro"), None)
    if not pro:
        sys.exit(f"no KiCad project in {hw}")
    name = pro.stem
    pcb, sch = pro.with_suffix(".kicad_pcb"), pro.with_suffix(".kicad_sch")

    if not a.force and check_board.check(bdir) != 0:
        sys.exit("board check failed; fix it or use --force")

    rev = a.rev
    if not rev:
        m = re.search(r'\(title_block.*?\(rev "([^"]*)"\)', pcb.read_text(), re.S)
        rev = m.group(1) if m else "A"
    out = hw / "fab" / f"rev{rev}"
    if out.exists():
        shutil.rmtree(out)
    gerb = out / "gerbers"
    gerb.mkdir(parents=True)

    run("pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask",
        "--use-drill-file-origin", "--check-zones", "-o", str(gerb), str(pcb))
    run("pcb", "export", "drill", "--format", "excellon", "--drill-origin", "plot",
        "--excellon-units", "mm", "--excellon-separate-th", "--generate-map",
        "--map-format", "gerberx2", "-o", str(gerb) + "/", str(pcb))
    zpath = out / f"{name}-rev{rev}-gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gerb.iterdir()):
            z.write(f, f.name)

    write_bom(pcb, out / f"{name}-bom.csv")

    raw_pos = out / "pos-raw.csv"
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
        "--use-drill-file-origin", "--exclude-dnp", "-o", str(raw_pos), str(pcb))
    with raw_pos.open() as fi, (out / f"{name}-centroid.csv").open("w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["Designator", "Mid X(mm)", "Mid Y(mm)", "Layer", "Rotation"])
        for row in csv.DictReader(fi):
            w.writerow([row["Ref"], row["PosX"], row["PosY"],
                        "Top" if row["Side"] == "top" else "Bottom", row["Rot"]])
    raw_pos.unlink()

    run("sch", "export", "pdf", "-o", str(out / f"{name}-schematic.pdf"), str(sch))
    run("pcb", "export", "step", "--force", "--subst-models", "--drill-origin",
        "-o", str(out / f"{name}.step"), str(pcb))

    print(f"fab outputs in {out.relative_to(check_board.REPO)}")
    for f in sorted(out.iterdir()):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
