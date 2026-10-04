#!/usr/bin/env python3
"""Check a board against the repo's house rules, then run KiCad ERC and DRC.

House rules checked:
  - every symbol and footprint comes from a library in lib/ (no stock/global libs)
  - 3D models resolve into lib/3dmodels and are STEP files
  - lib tables in the project match lib/ (run `tools/kilib.py sync` to fix)
  - 2 copper layers
  - Edge.Cuts outline no larger than 100 x 100 mm
  - 4 x 2.7 mm holes on the Raspberry Pi 58 x 49 mm pattern, unless the
    board's boards/<name>/board.json says {"rpi_mount": false, "reason": "..."}
    (for boards that are not HATs, e.g. off-header CAN nodes)
  - no chip parts below 0805; no Y5V/Y5U/Z5U capacitors

Usage:
  tools/check_board.py boards/<name>        # one board
  tools/check_board.py --all                # every board
  tools/check_board.py boards/<name> --no-kicad   # skip ERC/DRC
Exit status is non-zero if anything fails. ERC/DRC reports are written to
boards/<name>/hardware/reports/.
"""

import argparse
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import house_rules as hr  # noqa: E402
import kilib  # noqa: E402

REPO = kilib.REPO

# ERC warnings that are expected in a fresh board (unused RPi GPIO labels).
ERC_IGNORED = {"isolated_pin_label"}


class Result:
    def __init__(self):
        self.failures = 0

    def ok(self, msg):
        print(f"  ok    {msg}")

    def fail(self, msg):
        self.failures += 1
        print(f"  FAIL  {msg}")

    def warn(self, msg):
        print(f"  warn  {msg}")


def repo_libs():
    syms = {p.stem for p in kilib.SYM_DIR.glob("*.kicad_sym")}
    fps = {p.stem for p in kilib.FP_DIR.glob("*.pretty")}
    return syms, fps


def check_libraries(hw, r):
    syms, fps = repo_libs()
    if (hw / "sym-lib-table").read_text() != kilib.sym_table() or \
       (hw / "fp-lib-table").read_text() != kilib.fp_table():
        r.fail("project lib tables are stale; run tools/kilib.py sync")
    else:
        r.ok("lib tables point only at lib/")

    bad = set()
    for sch in hw.glob("*.kicad_sch"):
        for lib_id in re.findall(r'^\t\(symbol\s*\n\t\t\(lib_id "([^"]+)"\)', sch.read_text(), re.M):
            nick, name = lib_id.split(":", 1)
            if nick not in syms or name not in kilib.top_level_symbols(
                    (kilib.SYM_DIR / f"{nick}.kicad_sym").read_text()):
                bad.add(lib_id)
    if bad:
        r.fail("symbols not in lib/: " + ", ".join(sorted(bad)))
    else:
        r.ok("all symbols come from lib/")

    pcb_text = next(hw.glob("*.kicad_pcb")).read_text()
    bad = set()
    for fp in re.findall(r'^\t\(footprint "([^"]+)"', pcb_text, re.M):
        nick, name = fp.split(":", 1) if ":" in fp else ("", fp)
        if nick not in fps or not (kilib.FP_DIR / f"{nick}.pretty" / f"{name}.kicad_mod").exists():
            bad.add(fp)
    if bad:
        r.fail("footprints not in lib/: " + ", ".join(sorted(bad)))
    else:
        r.ok("all footprints come from lib/")

    bad, absent_local = set(), set()
    local_only = local_only_models()
    for m in re.findall(r'\(model "([^"]+)"', pcb_text):
        path = m.replace("${KIPRJMOD}", str(hw))
        if not path.startswith(str(hw)) or not Path(path).resolve().is_relative_to(kilib.MODEL_DIR):
            bad.add(m)
        elif not Path(path).exists():
            rel = Path(path).resolve().relative_to(kilib.MODEL_DIR).as_posix()
            (absent_local if rel in local_only else bad).add(m)
    if bad:
        r.fail("3D models outside lib/3dmodels or missing: " + ", ".join(sorted(bad)))
    else:
        r.ok("all 3D models resolve into lib/3dmodels")
    if absent_local:
        r.warn("local-only 3D models not on this machine (see lib/3dmodels/LOCAL_ONLY.txt): "
               + ", ".join(sorted(absent_local)))
    check_models_are_step(pcb_text, r)


def local_only_models():
    """Paths (relative to lib/3dmodels) of models that are git-ignored for
    license reasons; see lib/3dmodels/LOCAL_ONLY.txt."""
    f = kilib.MODEL_DIR / "LOCAL_ONLY.txt"
    if not f.exists():
        return set()
    return {line.split("|")[0].strip() for line in f.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")}


def check_models_are_step(pcb_text, r):
    """House policy: every placed part has a STEP model, so STEP exports and
    stack-height checks see the whole board. Board-only items (mounting holes,
    logos) are exempt."""
    not_step, missing = set(), set()
    for m in re.finditer(r'^\t\(footprint "([^"]+)"', pcb_text, re.M):
        body = pcb_text[m.start():kilib._block_end(pcb_text, m.start())]
        if "(attr board_only" in body or re.search(r"\(attr[^)]*board_only", body):
            continue
        models = re.findall(r'\(model "([^"]+)"', body)
        if not models:
            missing.add(m.group(1))
        not_step.update(x for x in models if not x.lower().endswith((".step", ".stp")))
    if not_step:
        r.fail("3D models that are not STEP: " + ", ".join(sorted(not_step)))
    if missing:
        r.warn("footprints without a 3D model: " + ", ".join(sorted(missing)))
    if not not_step and not missing:
        r.ok("every part has a STEP model")


def check_parts(pcb_path, r):
    """Hand-assembly part rules (see CLAUDE.md, "Part selection")."""
    import pcbnew
    board = pcbnew.LoadBoard(str(pcb_path))
    small, bad_diel = [], []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        name = fp.GetFPID().GetLibItemName().wx_str()
        m = re.match(r"(R|C|L|LED|D|F)_(\d{4})_", name)
        if m and m.group(2) in hr.TOO_SMALL_CHIP_SIZES:
            small.append(f"{ref} ({m.group(2)})")
        if re.match(r"C\d", ref):
            text = " ".join(fp.GetFieldText(f) for f in ("Value", "MPN", "Description") if fp.HasField(f))
            if re.search(hr.BANNED_DIELECTRICS, text, re.I):
                bad_diel.append(ref)
    if small:
        r.fail("chip parts smaller than 0805 (hand assembly): " + ", ".join(sorted(small)))
    if bad_diel:
        r.fail("capacitors with Y5V/Y5U/Z5U-class dielectric: " + ", ".join(sorted(bad_diel)))
    if not small and not bad_diel:
        r.ok("part sizes and capacitor dielectrics")


def board_config(hw):
    """Per-board exceptions to the house rules: boards/<name>/board.json."""
    f = hw.parent / "board.json"
    return json.loads(f.read_text()) if f.exists() else {}


def check_geometry(pcb_path, r, cfg=None):
    import pcbnew
    cfg = cfg or {}
    board = pcbnew.LoadBoard(str(pcb_path))
    to = pcbnew.ToMM

    n = board.GetCopperLayerCount()
    (r.ok if n == hr.COPPER_LAYERS else r.fail)(f"{n} copper layers")

    outline = pcbnew.SHAPE_POLY_SET()
    if board.GetBoardPolygonOutlines(outline, False) and outline.OutlineCount():
        box = outline.BBox()
    else:
        r.fail("Edge.Cuts outline is not a single closed shape")
        box = board.GetBoardEdgesBoundingBox()
    w, h = to(box.GetWidth()), to(box.GetHeight())
    if w > hr.MAX_W + 0.01 or h > hr.MAX_H + 0.01:
        r.fail(f"outline {w:.2f} x {h:.2f} mm exceeds {hr.MAX_W:g} x {hr.MAX_H:g} mm")
    elif w == 0 or h == 0:
        r.fail("no board outline on Edge.Cuts")
    else:
        r.ok(f"outline {w:.2f} x {h:.2f} mm")

    if not cfg.get("rpi_mount", True):
        r.ok("RPi mounting holes not required: " + cfg.get("reason", "board.json rpi_mount = false"))
        return
    holes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            d = pad.GetDrillSize()
            if abs(to(d.x) - hr.RPI_HOLE_DRILL) < 0.15 and d.x == d.y:
                p = pad.GetPosition()
                holes.append((to(p.x), to(p.y)))
    sx, sy = hr.RPI_HOLE_SPACING
    found = False
    for combo in itertools.combinations(holes, 4):
        xs = sorted({round(x, 2) for x, _ in combo})
        ys = sorted({round(y, 2) for _, y in combo})
        if len(xs) == 2 and len(ys) == 2 and abs(xs[1] - xs[0] - sx) < 0.05 and abs(ys[1] - ys[0] - sy) < 0.05:
            found = True
            break
    (r.ok if found else r.fail)("RPi 58 x 49 mm M2.5 mounting holes" + ("" if found else " not found"))


def run_erc(hw, sch, r):
    out = hw / "reports" / "erc.json"
    out.parent.mkdir(exist_ok=True)
    subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all",
                    "-o", str(out), str(sch)], capture_output=True)
    data = json.loads(out.read_text())
    counts = {}
    for sheet in data.get("sheets", []):
        for v in sheet.get("violations", []):
            if v.get("excluded"):
                continue
            key = (v["severity"], v["type"])
            counts[key] = counts.get(key, 0) + 1
    errors = {k: c for k, c in counts.items() if k[0] == "error"}
    warns = {k: c for k, c in counts.items() if k[0] != "error" and k[1] not in ERC_IGNORED}
    for (sev, typ), c in sorted(errors.items()):
        r.fail(f"ERC {typ} x{c}")
    for (sev, typ), c in sorted(warns.items()):
        r.warn(f"ERC {typ} x{c}")
    if not errors:
        r.ok("ERC: no errors")


def run_drc(hw, pcb, r):
    out = hw / "reports" / "drc.json"
    out.parent.mkdir(exist_ok=True)
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "--schematic-parity", "--refill-zones", "-o", str(out), str(pcb)],
                   capture_output=True)
    data = json.loads(out.read_text())
    groups = {"violations": "DRC", "unconnected_items": "unconnected", "schematic_parity": "parity"}
    errs = 0
    for key, label in groups.items():
        counts = {}
        for v in data.get(key, []):
            if v.get("excluded"):
                continue
            k = (v["severity"], v["type"])
            counts[k] = counts.get(k, 0) + 1
        for (sev, typ), c in sorted(counts.items()):
            if sev == "error":
                errs += 1
                r.fail(f"{label} {typ} x{c}")
            else:
                r.warn(f"{label} {typ} x{c}")
    if not errs:
        r.ok("DRC + schematic parity: no errors")


def check(board_dir, kicad=True):
    hw = Path(board_dir).resolve() / "hardware"
    pros = list(hw.glob("*.kicad_pro"))
    if not pros:
        print(f"{board_dir}: no KiCad project in {hw}")
        return 1
    pro = pros[0]
    print(f"{hw.parent.relative_to(REPO)}:")
    r = Result()
    check_libraries(hw, r)
    pcb = pro.with_suffix(".kicad_pcb")
    check_geometry(pcb, r, board_config(hw))
    check_parts(pcb, r)
    if kicad:
        run_erc(hw, pro.with_suffix(".kicad_sch"), r)
        run_drc(hw, pcb, r)
    return r.failures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("boards", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-kicad", action="store_true", help="skip ERC/DRC")
    a = ap.parse_args()
    boards = [p.parent for p in kilib.project_dirs()] if a.all else [Path(b) for b in a.boards]
    if not boards:
        ap.error("give board directories or --all")
    failures = sum(check(b, not a.no_kicad) for b in boards)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
