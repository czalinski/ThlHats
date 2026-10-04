#!/usr/bin/env python3
"""Update a board's PCB from its schematic (KiCad "Update PCB from Schematic").

  tools/sync_pcb.py boards/<name> [--dry-run]

- Exports the netlist with kicad-cli.
- Adds footprints for symbols that have none on the board yet (parked in a
  grid to the right of the outline), linked to their symbols by path so
  schematic parity holds.
- Updates value, footprint fields (Manufacturer, MPN, ...) and pad nets of
  every linked footprint. Existing footprints keep their position.
- Never deletes anything: footprints without a symbol (mounting holes, DIN
  clips, logos) are left alone; stale ones are listed.
Footprints load from lib/ only (the lib nickname maps to lib/footprints/<nick>.pretty).
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FP_DIR = REPO / "lib/footprints"


def parse_sexpr(text):
    """Minimal s-expression parser: lists, bare atoms and quoted strings."""
    stack, cur, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "(":
            stack.append(cur)
            cur = []
            i += 1
        elif c == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    j += 1
                buf.append(text[j])
                j += 1
            cur.append("".join(buf))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()':
                j += 1
            cur.append(text[i:j])
            i = j
    return cur[0]


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key, default=None):
    f = find(node, key)
    return f[0] if f else default


def read_netlist(sch):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "net.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(sch)],
                       check=True, capture_output=True)
        tree = parse_sexpr(out.read_text())
    comps = {}
    for c in find(first(tree, "components"), "comp"):
        ref = first(c, "ref")[1]
        fields = {f[1][1]: (f[2] if len(f) > 2 else "") for f in find(first(c, "fields", []), "field")}
        sheet = first(c, "sheetpath")
        comps[ref] = {
            "value": first(c, "value")[1],
            "footprint": (first(c, "footprint") or [None, ""])[1],
            "fields": {k: v for k, v in fields.items() if k not in ("Footprint", "Datasheet", "Description")},
            "path": first(sheet, "tstamps")[1] + first(c, "tstamps")[1],
            "sheetname": first(sheet, "names")[1],
        }
    nets = {}  # (ref, pin) -> net name
    for net in find(first(tree, "nets"), "net"):
        name = first(net, "name")[1]
        for node in find(net, "node"):
            nets[(first(node, "ref")[1], first(node, "pin")[1])] = name
    return comps, nets


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    hw = Path(a.board) / "hardware"
    name = Path(a.board).name
    sch, pcb_path = hw / f"{name}.kicad_sch", hw / f"{name}.kicad_pcb"

    import pcbnew

    comps, nets = read_netlist(sch)
    board = pcbnew.LoadBoard(str(pcb_path))
    by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    netinfo = {}

    def net(nm):
        if nm not in netinfo:
            ni = board.FindNet(nm)
            if ni is None:
                ni = pcbnew.NETINFO_ITEM(board, nm)
                board.Add(ni)
            netinfo[nm] = ni
        return netinfo[nm]

    bb = board.GetBoardEdgesBoundingBox()
    park_x, park_y, col = pcbnew.ToMM(bb.GetRight()) + 20, pcbnew.ToMM(bb.GetTop()), 0
    added, changed = [], []
    for ref, c in sorted(comps.items()):
        if not c["footprint"]:
            continue
        nick, fpname = c["footprint"].split(":", 1)
        fp = by_ref.get(ref)
        if fp is not None and fp.GetFPIDAsString() != c["footprint"]:
            print(f"warning: {ref} footprint differs (board {fp.GetFPIDAsString()}, schematic {c['footprint']}); "
                  "left as is", file=sys.stderr)
        if fp is None:
            lib = FP_DIR / f"{nick}.pretty"
            fp = pcbnew.FootprintLoad(str(lib), fpname)
            if fp is None:
                sys.exit(f"{ref}: footprint {c['footprint']} not found in {lib}")
            fp.SetFPIDAsString(c["footprint"])
            fp.SetReference(ref)
            x = park_x + (col % 10) * 25
            y = park_y + (col // 10) * 25
            col += 1
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
            board.Add(fp)
            added.append(ref)
        fp.SetPath(pcbnew.KIID_PATH(c["path"]))
        fp.SetSheetname(c["sheetname"])
        if fp.GetValue() != c["value"]:
            fp.SetValue(c["value"])
            changed.append(ref)
        for k, v in c["fields"].items():
            if k in ("Reference", "Value"):
                continue
            new = not fp.HasField(k)
            fp.SetField(k, v)
            if new:
                f = fp.GetField(k)
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
        for pad in fp.Pads():
            nm = nets.get((ref, pad.GetNumber()))
            if nm:
                pad.SetNet(net(nm))
            elif pad.GetNumber():
                pad.SetNetCode(0)
    stale = sorted(r for r, fp in by_ref.items() if r not in comps and fp.GetPath().AsString() not in ("", "/"))
    print(f"added {len(added)}, value updates {len(changed)}, nets {len(set(nets.values()))}")
    if stale:
        print("footprints whose symbol is gone (not removed): " + ", ".join(stale))
    if not a.dry_run:
        board.Save(str(pcb_path))


if __name__ == "__main__":
    main()
