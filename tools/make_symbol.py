#!/usr/bin/env python3
"""Build a KiCad symbol from a pin table and add it to a library in lib/.

Pin tables live in lib/symbol_src/<Lib>/<Symbol>.csv so a symbol can be
reviewed against its datasheet and regenerated. Format:

  # key: value header lines (all optional)
  # name: PIC16F17146-ISO          symbol name (default: file stem); no '/'
  # mpn: PIC16F17146-I/SO          MPN field (default: name)
  # manufacturer: Microchip
  # reference: U
  # footprint: Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm
  # datasheet: https://...
  # description: ...
  # keywords: ...
  # fp_filters: SOIC*7.5x12.8mm*P1.27mm*
  # aliases: PIC16F17144-ISO=PIC16F17144-I/SO, ...   derived symbols (name=mpn)
  pin,name,type,side
  1,VDD,power_in,top
  2,RA5,bidirectional,left
  ...

type is a KiCad electrical type (input, output, bidirectional, tri_state,
passive, free, unspecified, power_in, power_out, open_collector,
open_emitter, no_connect). side is left/right/top/bottom; pins are placed in
table order down each side (left to right along top/bottom). A blank row, i.e.
",,,left", leaves a one-pin gap on that side.

Usage:
  tools/make_symbol.py lib/symbol_src/Thl_MCU/PIC16F17146-ISO.csv
  tools/make_symbol.py --all
"""

import argparse
import csv
import datetime
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kilib  # noqa: E402

SRC = kilib.LIB / "symbol_src"
GRID = 2.54
PIN_LEN = 2.54
CHAR_W = 1.0  # approx. width of a 1.27 mm KiCad font character


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def snap(v):
    return math.ceil(v / GRID) * GRID


def read_table(path):
    meta, pins = {}, []
    lines = path.read_text().splitlines()
    body = []
    for ln in lines:
        m = re.match(r"#\s*(\w+)\s*:\s*(.*)", ln)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
        elif ln.strip() and not ln.lstrip().startswith("#"):
            body.append(ln)
    for row in csv.DictReader(body):
        pins.append({k: (v or "").strip() for k, v in row.items()})
    return meta, pins


def prop(name, value, x, y, hide=False, justify=None):
    j = f"\n\t\t\t\t(justify {justify})" if justify else ""
    h = "\n\t\t\t(hide yes)" if hide else ""
    return (f"\t\t(property {q(name)} {q(value)}\n\t\t\t(at {x:g} {y:g} 0){h}\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){j}\n\t\t\t)\n\t\t)\n")


def build(name, meta, pins):
    sides = {s: [] for s in ("left", "right", "top", "bottom")}
    seen = set()
    for p in pins:
        side = p["side"].lower()
        if side not in sides:
            sys.exit(f"{name}: bad side {p['side']!r} for pin {p['pin']}")
        if p["pin"]:
            if p["pin"] in seen:
                sys.exit(f"{name}: duplicate pin number {p['pin']}")
            seen.add(p["pin"])
        sides[side].append(p)

    def longest(lst):
        return max((len(p["name"]) for p in lst if p["pin"]), default=0)

    # Body size: left/right pin names sit inside the body, facing each other.
    n_lr = max(len(sides["left"]), len(sides["right"]), 1)
    n_tb = max(len(sides["top"]), len(sides["bottom"]), 0)
    width = snap(max((longest(sides["left"]) + longest(sides["right"])) * CHAR_W + 4 * GRID,
                     (n_tb + 1) * GRID))
    # Top/bottom names are drawn vertically inside the body.
    tb_depth = max(longest(sides["top"]), longest(sides["bottom"])) * CHAR_W
    height = snap(n_lr * GRID + 2 * (tb_depth + GRID if n_tb else 0) + GRID)
    if width / GRID % 2:
        width += GRID
    if height / GRID % 2:
        height += GRID
    x0, x1, y0, y1 = -width / 2, width / 2, height / 2, -height / 2  # y up

    out = []

    def pin(p, x, y, ang):
        if not p["pin"]:
            return
        out.append(
            f"\t\t\t(pin {p['type'] or 'bidirectional'} line\n\t\t\t\t(at {x:g} {y:g} {ang})\n"
            f"\t\t\t\t(length {PIN_LEN:g})\n"
            f"\t\t\t\t(name {q(p['name'])}\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n"
            f"\t\t\t\t(number {q(p['pin'])}\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n"
            "\t\t\t)\n")

    def column(lst):
        n = len(lst)
        top = (n - 1) * GRID / 2
        top = math.floor(top / GRID) * GRID if n % 2 == 0 else top
        return [top - i * GRID for i in range(n)]

    for p, y in zip(sides["left"], column(sides["left"])):
        pin(p, x0 - PIN_LEN, y, 0)
    for p, y in zip(sides["right"], column(sides["right"])):
        pin(p, x1 + PIN_LEN, y, 180)
    for p, x in zip(sides["top"], [-v for v in column(sides["top"])]):
        pin(p, x, y0 + PIN_LEN, 270)
    for p, x in zip(sides["bottom"], [-v for v in column(sides["bottom"])]):
        pin(p, x, y1 - PIN_LEN, 90)

    ref = meta.get("reference", "U")
    s = (f"\t(symbol {q(name)}\n\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)\n"
         "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n")
    s += prop("Reference", ref, x0, y0 + 1.27, justify="left bottom")
    s += prop("Value", name, x1, y0 + 1.27, justify="right bottom")
    s += prop("Footprint", meta.get("footprint", ""), 0, 0, hide=True)
    s += prop("Datasheet", meta.get("datasheet", ""), 0, 0, hide=True)
    s += prop("Description", meta.get("description", ""), 0, 0, hide=True)
    if "manufacturer" in meta:
        s += prop("Manufacturer", meta["manufacturer"], 0, 0, hide=True)
    s += prop("MPN", meta.get("mpn", name), 0, 0, hide=True)
    if meta.get("keywords"):
        s += prop("ki_keywords", meta["keywords"], 0, 0, hide=True)
    if meta.get("fp_filters"):
        s += prop("ki_fp_filters", meta["fp_filters"], 0, 0, hide=True)
    s += (f"\t\t(symbol {q(name + '_0_1')}\n\t\t\t(rectangle\n\t\t\t\t(start {x0:g} {y0:g})\n"
          f"\t\t\t\t(end {x1:g} {y1:g})\n\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n"
          "\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n")
    s += f"\t\t(symbol {q(name + '_1_1')}\n" + "".join(out) + "\t\t)\n"
    s += "\t\t(embedded_fonts no)\n\t)\n"
    return s


def derived(name, parent, meta, mpn):
    """A symbol that extends `parent` with only its own Value/MPN."""
    s = f"\t(symbol {q(name)}\n\t\t(extends {q(parent)})\n"
    s += prop("Reference", meta.get("reference", "U"), 0, 0)
    s += prop("Value", name, 0, 0)
    s += prop("Footprint", meta.get("footprint", ""), 0, 0, hide=True)
    s += prop("Datasheet", meta.get("datasheet", ""), 0, 0, hide=True)
    s += prop("Description", meta.get("description", ""), 0, 0, hide=True)
    if "manufacturer" in meta:
        s += prop("Manufacturer", meta["manufacturer"], 0, 0, hide=True)
    s += prop("MPN", mpn, 0, 0, hide=True)
    if meta.get("keywords"):
        s += prop("ki_keywords", meta["keywords"], 0, 0, hide=True)
    if meta.get("fp_filters"):
        s += prop("ki_fp_filters", meta["fp_filters"], 0, 0, hide=True)
    s += "\t\t(embedded_fonts no)\n\t)\n"
    return s


def install(lib, name, block):
    dst = kilib.SYM_DIR / f"{lib}.kicad_sym"
    text = dst.read_text() if dst.exists() else kilib.EMPTY_SYM_LIB
    syms = kilib.top_level_symbols(text)
    if name in syms:
        s, e = syms[name]
        # text[:s] ends with the block's leading tab; text[e:] starts with its newline.
        text = text[:s] + block[1:-1] + text[e:]
        verb = "updated"
    else:
        at = text.rstrip().rfind(")")
        text = text[:at] + block + text[at:]
        verb = "added"
    dst.write_text(text)
    print(f"{verb:8s} {lib}:{name}")


def make(path):
    path = Path(path).resolve()
    lib = path.parent.name
    meta, pins = read_table(path)
    name = meta.get("name") or path.stem
    if "/" in name:
        sys.exit(f"{path}: symbol names cannot contain '/'; put the real part number in '# mpn:'")
    install(lib, name, build(name, meta, pins))
    for alias in filter(None, (a.strip() for a in meta.get("aliases", "").split(","))):
        aname, _, ampn = alias.partition("=")
        install(lib, aname.strip(), derived(aname.strip(), name, meta, ampn.strip() or aname.strip()))
    if not any(r for r in kilib.SOURCES.read_text().splitlines() if f"| {lib} | {name} |" in r):
        kilib.log_source("symbol", name, lib, f"generated from lib/symbol_src/{lib}/{path.name}",
                         "repo (MIT)")
    return lib


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tables", nargs="*")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    tables = sorted(SRC.glob("*/*.csv")) if a.all else a.tables
    if not tables:
        ap.error("give pin tables or --all")
    for t in tables:
        make(t)
    kilib.sync(quiet=True)


if __name__ == "__main__":
    main()
