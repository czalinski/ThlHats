#!/usr/bin/env python3
"""Manage the repo-local KiCad libraries in lib/.

All symbols, footprints and 3D models used by boards in this repo live under
lib/. Parts are copied in from the stock KiCad install or from downloaded files
(SnapEDA, Ultra Librarian, vendor sites, ...). Every import is logged to
lib/SOURCES.md.

Libraries copied from the stock KiCad libs keep their stock nickname
(e.g. "Device", "Resistor_SMD") so the Footprint fields of stock symbols
resolve to the repo copy. Parts from other sources go into a "Thl_*" library.

Examples:
  tools/kilib.py library power                      # copy a whole stock symbol lib
  tools/kilib.py symbol MCU_Espressif:ESP32-S3      # one stock symbol (+ its footprint)
  tools/kilib.py footprint Package_SO:SOIC-8_3.9x4.9mm_P1.27mm
  tools/kilib.py symbol MyPart --from ~/Downloads/x.kicad_sym --lib Thl_Sensor \\
        --source "SnapEDA" --license "CC-BY-SA"
  tools/kilib.py footprint MyFp --from ~/Downloads/x.kicad_mod --lib Thl_Sensor \\
        --model ~/Downloads/x.step --source "SnapEDA"
  tools/kilib.py search 'PIC16F18.*SS' --kind symbol  # find stock parts
  tools/kilib.py sync                               # rewrite lib tables in every board
  tools/kilib.py list
"""

import argparse
import datetime
import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "lib"
SYM_DIR = LIB / "symbols"
FP_DIR = LIB / "footprints"
MODEL_DIR = LIB / "3dmodels"
SOURCES = LIB / "SOURCES.md"
BOARDS = REPO / "boards"

# Boards live at boards/<name>/hardware/, three levels below the repo root.
LIB_FROM_PROJECT = "${KIPRJMOD}/../../../lib"

KICAD_SHARE = Path(os.environ.get("KICAD_SHARE", "/usr/share/kicad"))
STOCK_SYM = Path(os.environ.get("KICAD10_SYMBOL_DIR", KICAD_SHARE / "symbols"))
STOCK_FP = Path(os.environ.get("KICAD10_FOOTPRINT_DIR", KICAD_SHARE / "footprints"))
STOCK_3D = Path(os.environ.get("KICAD10_3DMODEL_DIR", KICAD_SHARE / "3dmodels"))

EMPTY_SYM_LIB = (
    "(kicad_symbol_lib\n"
    "\t(version 20251024)\n"
    '\t(generator "kicad_symbol_editor")\n'
    '\t(generator_version "10.0")\n'
    ")\n"
)


# --------------------------------------------------------------------------
# Minimal s-expression helpers (string-aware paren matching on raw text, so
# imported text is copied byte-for-byte).

def _block_end(text, start):
    """Return index one past the ')' closing the '(' at text[start]."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced s-expression")


def top_level_symbols(text):
    """Map symbol name -> (start, end) for the top-level symbols of a lib."""
    out = {}
    root = text.index("(kicad_symbol_lib")
    i = root + 1
    end = _block_end(text, root) - 1
    while i < end:
        c = text[i]
        if c == '"':
            i = text.index('"', i + 1) + 1  # names never contain escaped quotes here
            continue
        if c == "(":
            j = _block_end(text, i)
            m = re.match(r'\(symbol\s+"((?:[^"\\]|\\.)*)"', text[i:j])
            if m:
                out[m.group(1)] = (i, j)
            i = j
            continue
        i += 1
    return out


def sym_property(block, name):
    m = re.search(r'\(property\s+"%s"\s+"((?:[^"\\]|\\.)*)"' % re.escape(name), block)
    return m.group(1) if m else None


def sym_extends(block):
    m = re.search(r'\(extends\s+"((?:[^"\\]|\\.)*)"\)', block)
    return m.group(1) if m else None


# --------------------------------------------------------------------------

def log_source(kind, item, lib, source, license_):
    if not SOURCES.exists():
        SOURCES.write_text(
            "# Library sources\n\n"
            "Provenance of every part in `lib/`. Appended by `tools/kilib.py`.\n\n"
            "| Date | Kind | Library | Item | Source | License |\n"
            "|------|------|---------|------|--------|---------|\n"
        )
    date = datetime.date.today().isoformat()
    with SOURCES.open("a") as f:
        f.write(f"| {date} | {kind} | {lib} | {item} | {source} | {license_} |\n")


def stock_license():
    return "CC-BY-SA-4.0 w/ KiCad exception"


def split_spec(spec):
    if ":" in spec:
        lib, name = spec.split(":", 1)
        return lib, name
    return None, spec


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def suggest(name, candidates):
    """A '; similar: ...' hint for a name that was not found."""
    key = _norm(name)
    for n in (len(key), 8, 6):
        close = [c for c in candidates if _norm(c).startswith(key[:n])]
        if close:
            return f"; similar: {', '.join(close[:12])}" + (" ..." if len(close) > 12 else "")
    return ""


def search(pattern, kind):
    """Search the stock KiCad libraries by regex."""
    rx = re.compile(pattern, re.I)
    hits = 0
    if kind in ("all", "symbol"):
        # Stock libs are KiCad-formatted: top-level symbols start at one tab.
        head = re.compile(r'^\t\(symbol "((?:[^"\\]|\\.)*)"', re.M)
        for lib in sorted(STOCK_SYM.glob("*.kicad_sym")):
            text = lib.read_text()
            starts = [(m.start(), m.group(1)) for m in head.finditer(text)]
            for i, (pos, name) in enumerate(starts):
                end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
                desc = sym_property(text[pos:end], "Description") or ""
                if rx.search(name) or rx.search(desc):
                    print(f"symbol    {lib.stem}:{name}    {desc[:70]}")
                    hits += 1
    if kind in ("all", "footprint"):
        for lib in sorted(STOCK_FP.glob("*.pretty")):
            for f in sorted(lib.glob("*.kicad_mod")):
                if rx.search(f.stem):
                    print(f"footprint {lib.stem}:{f.stem}")
                    hits += 1
    if not hits:
        print("no matches")


def set_property(block, name, value):
    return re.sub(r'(\(property\s+"%s"\s+)"(?:[^"\\]|\\.)*"' % re.escape(name),
                  lambda m: m.group(1) + '"' + value + '"', block, count=1)


def import_symbol(spec, src_file=None, lib=None, with_fp=True, source=None,
                  license_=None, rename=None, footprint=None):
    src_lib, name = split_spec(spec)
    if src_file:
        src_path = Path(src_file).expanduser()
        lib = lib or src_lib
        if not lib:
            sys.exit("--lib is required when importing from a file")
        source = source or str(src_path.name)
    else:
        if not src_lib:
            sys.exit(f"stock symbol must be given as Lib:Name, got {spec!r}")
        src_path = STOCK_SYM / f"{src_lib}.kicad_sym"
        lib = lib or src_lib
        source = source or f"KiCad {src_lib}.kicad_sym"
        license_ = license_ or stock_license()
    if not src_path.exists():
        sys.exit(f"no such library file: {src_path}")

    src_text = src_path.read_text()
    src_syms = top_level_symbols(src_text)
    if name not in src_syms:
        sys.exit(f"symbol {name!r} not in {src_path}" + suggest(name, src_syms))

    # Collect the symbol and the chain of parents it derives from.
    chain = []
    cur = name
    while cur:
        if cur not in src_syms:
            sys.exit(f"parent symbol {cur!r} missing from {src_path}")
        s, e = src_syms[cur]
        block = src_text[s:e]
        chain.append((cur, block))
        cur = sym_extends(block)

    if rename:
        if len(chain) > 1:
            sys.exit("--rename is not supported for derived (extends) symbols")
        old = chain[0][1]
        new = re.sub(r'^\(symbol\s+"%s"' % re.escape(name), f'(symbol "{rename}"', old)
        new = re.sub(r'\(symbol\s+"%s_(\d+_\d+)"' % re.escape(name), rf'(symbol "{rename}_\1"', new)
        chain[0] = (rename, new)

    if footprint:
        chain[0] = (chain[0][0], set_property(chain[0][1], "Footprint", footprint))
    fp_field = sym_property(chain[0][1], "Footprint") or ""
    if src_file and fp_field:
        fp_lib, _, fp_name = fp_field.partition(":")
        if not (FP_DIR / f"{fp_lib}.pretty" / f"{fp_name}.kicad_mod").exists():
            print(f"warning: Footprint field {fp_field!r} is not in lib/; "
                  "import it or pass --set-footprint Lib:Name", file=sys.stderr)

    dst = SYM_DIR / f"{lib}.kicad_sym"
    dst_text = dst.read_text() if dst.exists() else EMPTY_SYM_LIB
    dst_syms = top_level_symbols(dst_text)

    added = []
    # Parents must precede children in the file.
    for sym_name, block in reversed(chain):
        if sym_name in dst_syms:
            continue
        insert_at = dst_text.rstrip().rfind(")")
        dst_text = dst_text[:insert_at] + "\t" + block + "\n" + dst_text[insert_at:]
        dst_syms = top_level_symbols(dst_text)
        added.append(sym_name)
    dst.write_text(dst_text)

    for sym_name in added:
        print(f"symbol    {lib}:{sym_name}")
        log_source("symbol", sym_name, lib, source, license_ or "unknown")
    if not added:
        print(f"symbol    {lib}:{chain[0][0]} already present")

    if with_fp and not src_file:
        fp = sym_property(chain[0][1], "Footprint")
        if fp and ":" in fp:
            fp_lib, fp_name = fp.split(":", 1)
            if (STOCK_FP / f"{fp_lib}.pretty" / f"{fp_name}.kicad_mod").exists():
                import_footprint(fp)
            else:
                print(f"warning: footprint {fp} not found in stock libs", file=sys.stderr)
        else:
            filt = sym_property(chain[-1][1], "ki_fp_filters") or ""
            print(f"note: {chain[0][0]} has no default footprint"
                  + (f" (filters: {filt})" if filt else "")
                  + "; import one with `kilib.py footprint`", file=sys.stderr)
    return lib


def import_footprint(spec, src_file=None, lib=None, model=None, source=None,
                     license_=None, with_models=True):
    src_lib, name = split_spec(spec)
    if src_file:
        src_path = Path(src_file).expanduser()
        lib = lib or src_lib
        if not lib:
            sys.exit("--lib is required when importing from a file")
        source = source or src_path.name
        if not name:
            name = src_path.stem
    else:
        if not src_lib:
            sys.exit(f"stock footprint must be given as Lib:Name, got {spec!r}")
        src_path = STOCK_FP / f"{src_lib}.pretty" / f"{name}.kicad_mod"
        lib = lib or src_lib
        source = source or f"KiCad {src_lib}.pretty"
        license_ = license_ or stock_license()
    if not src_path.exists():
        hint = suggest(name, [f.stem for f in src_path.parent.glob("*.kicad_mod")]) \
            if src_path.parent.exists() else ""
        sys.exit(f"no such footprint file: {src_path}{hint}")

    dst_dir = FP_DIR / f"{lib}.pretty"
    dst = dst_dir / f"{name}.kicad_mod"
    if dst.exists():
        print(f"footprint {lib}:{name} already present")
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    text = src_path.read_text()
    if src_file:
        # Make the footprint's own name match its file name.
        text = re.sub(r'^\((footprint|module)\s+("[^"]*"|\S+)', rf'(\1 "{name}"', text, count=1)

    model_dir = MODEL_DIR / f"{lib}.3dshapes"

    def fix_model(m):
        path = m.group(1)
        expanded = re.sub(r"\$\{KICAD\d*_3DMODEL_DIR\}", str(STOCK_3D), path)
        srcm = Path(expanded)
        candidates = [srcm.with_suffix(".step"), srcm.with_suffix(".stp"), srcm]
        if model:
            candidates.insert(0, Path(model).expanduser())
        for c in candidates:
            if with_models and c.exists():
                model_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(c, model_dir / c.name)
                return f'(model "{LIB_FROM_PROJECT}/3dmodels/{lib}.3dshapes/{c.name}"'
        print(f"warning: 3D model not copied for {lib}:{name} ({path})", file=sys.stderr)
        return m.group(0)

    text = re.sub(r'\(model\s+"([^"]+)"', fix_model, text)
    if model and "(model " not in text:
        mp = Path(model).expanduser()
        model_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mp, model_dir / mp.name)
        insert_at = text.rstrip().rfind(")")
        text = (text[:insert_at]
                + f'\t(model "{LIB_FROM_PROJECT}/3dmodels/{lib}.3dshapes/{mp.name}"\n'
                + "\t\t(offset (xyz 0 0 0))\n\t\t(scale (xyz 1 1 1))\n\t\t(rotate (xyz 0 0 0))\n\t)\n"
                + text[insert_at:])
    dst.write_text(text)
    print(f"footprint {lib}:{name}")
    log_source("footprint", name, lib, source, license_ or "unknown")


def import_library(nick):
    """Copy a whole stock symbol library."""
    src = STOCK_SYM / f"{nick}.kicad_sym"
    if not src.exists():
        sys.exit(f"no stock symbol library {nick}")
    dst = SYM_DIR / f"{nick}.kicad_sym"
    if dst.exists():
        # Merge: add any symbols not present yet.
        for name in top_level_symbols(src.read_text()):
            import_symbol(f"{nick}:{name}", with_fp=False)
        return
    shutil.copy2(src, dst)
    print(f"library   {nick} ({len(top_level_symbols(dst.read_text()))} symbols)")
    log_source("symbol library", "(all)", nick, f"KiCad {nick}.kicad_sym", stock_license())


# --------------------------------------------------------------------------

def sym_table():
    lines = ["(sym_lib_table", "\t(version 7)"]
    for p in sorted(SYM_DIR.glob("*.kicad_sym")):
        lines.append(f'\t(lib (name "{p.stem}") (type "KiCad") '
                     f'(uri "{LIB_FROM_PROJECT}/symbols/{p.name}") (options "") (descr ""))')
    lines.append(")")
    return "\n".join(lines) + "\n"


def fp_table():
    lines = ["(fp_lib_table", "\t(version 7)"]
    for p in sorted(FP_DIR.glob("*.pretty")):
        lines.append(f'\t(lib (name "{p.stem}") (type "KiCad") '
                     f'(uri "{LIB_FROM_PROJECT}/footprints/{p.name}") (options "") (descr ""))')
    lines.append(")")
    return "\n".join(lines) + "\n"


def project_dirs():
    return sorted(p.parent for p in BOARDS.glob("*/hardware/*.kicad_pro"))


def sync(quiet=False):
    st, ft = sym_table(), fp_table()
    for d in project_dirs():
        (d / "sym-lib-table").write_text(st)
        (d / "fp-lib-table").write_text(ft)
        if not quiet:
            print(f"synced    {d.relative_to(REPO)}")


def list_libs():
    for p in sorted(SYM_DIR.glob("*.kicad_sym")):
        print(f"sym  {p.stem:40s} {len(top_level_symbols(p.read_text())):5d} symbols")
    for p in sorted(FP_DIR.glob("*.pretty")):
        print(f"fp   {p.stem:40s} {len(list(p.glob('*.kicad_mod'))):5d} footprints")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("symbol", help="import symbol(s) (stock Lib:Name, or Name with --from)")
    s.add_argument("spec", nargs="+")
    s.add_argument("--from", dest="src")
    s.add_argument("--lib")
    s.add_argument("--rename", help="store under a different symbol name")
    s.add_argument("--set-footprint", metavar="LIB:NAME", help="set the symbol's Footprint field")
    s.add_argument("--no-footprint", action="store_true", help="do not import the default footprint")
    s.add_argument("--source")
    s.add_argument("--license")

    f = sub.add_parser("footprint", help="import footprint(s) (stock Lib:Name, or Name with --from)")
    f.add_argument("spec", nargs="+")
    f.add_argument("--from", dest="src")
    f.add_argument("--lib")
    f.add_argument("--model", help="3D model (.step) to copy and attach")
    f.add_argument("--no-models", action="store_true")
    f.add_argument("--source")
    f.add_argument("--license")

    l = sub.add_parser("library", help="copy whole stock symbol libraries")
    l.add_argument("nick", nargs="+")

    se = sub.add_parser("search", help="search stock KiCad libs (regex on name/description)")
    se.add_argument("pattern")
    se.add_argument("--kind", choices=["all", "symbol", "footprint"], default="all")

    sub.add_parser("sync", help="write lib tables into every board project")
    sub.add_parser("list", help="list repo libraries")

    a = ap.parse_args()
    SYM_DIR.mkdir(parents=True, exist_ok=True)
    FP_DIR.mkdir(parents=True, exist_ok=True)

    if a.cmd == "symbol":
        for spec in a.spec:
            import_symbol(spec, a.src, a.lib, not a.no_footprint, a.source, a.license, a.rename,
                          a.set_footprint)
        sync(quiet=True)
    elif a.cmd == "footprint":
        for spec in a.spec:
            import_footprint(spec, a.src, a.lib, a.model, a.source, a.license, not a.no_models)
        sync(quiet=True)
    elif a.cmd == "library":
        for n in a.nick:
            import_library(n)
        sync(quiet=True)
    elif a.cmd == "search":
        search(a.pattern, a.kind)
    elif a.cmd == "sync":
        sync()
    elif a.cmd == "list":
        list_libs()


if __name__ == "__main__":
    main()
