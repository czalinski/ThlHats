#!/usr/bin/env python3
"""Autoroute a board's signal nets with Freerouting (headless).

  tools/freeroute.py boards/<name> [--skip NET ...] [--timeout S] [--threads N]

1. Exports the PCB to Specctra DSN (pcbnew.ExportSpecctraDSN).
2. Drops every copper pour ("plane") except the --keep-plane nets, and
   empties the pin lists of the --skip nets: poured grounds are joined by
   pours and fanout vias (miniroute.ground_fanout), not by the router.
   Adds Freerouting layer costs so signals prefer F.Cu (--bottom-cost).
3. Runs Freerouting and imports the session (pcbnew.ImportSpecctraSES),
   restores the 0.15 mm via annular ring, refills the zones and saves.

Freerouting: ~/tools/freerouting/freerouting-1.9.0.jar under xvfb-run (1.9
is GUI-only, needs a JRE with AWT (~/tools/jre21: Temurin 21; the system
OpenJDK is headless), honours the pass limit -mp and saves a partial result).
--jar 2.1.0 selects the headless 2.1.0 (2.2+ needs Java 25), which ignores
pass limit and timeout and writes the .ses only once every connection is
routed. Telemetry is off in ~/.config/freerouting/freerouting.json.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

JARS = Path.home() / "tools/freerouting"
EDGE_BAND = 0.6   # router keep-out along the board edge (Freerouting ignores edge clearance)


def drop_blocks(s, head, pred):
    out, i, n = [], 0, 0
    while True:
        j = s.find(head, i)
        if j < 0:
            out.append(s[i:])
            break
        d, k = 0, j
        while True:
            c = s[k]
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    break
            k += 1
        if pred(s[j:k + 1]):
            out.append(s[i:j])
            n += 1
        else:
            out.append(s[i:k + 1])
        i = k + 1
    return "".join(out), n


def dsn_name(net):
    return f'"{net}"' if re.search(r'[\s()"]', net) else net


def strip(s, skip, keep_planes=()):
    """Drop every plane and empty the pin lists of the skip nets. The nets
    stay defined, so their fanout vias remain as fixed obstacles (and
    Freerouting 1.9 shows no warning dialog), but there is nothing to route."""
    names = {dsn_name(n) for n in skip}

    def net_name(b):
        r = b[len("(net "):].lstrip()
        return r[:r.index('"', 1) + 1] if r.startswith('"') else r.split()[0].rstrip(")")

    keep = {dsn_name(k) for k in keep_planes}
    s, _ = drop_blocks(s, "(plane ", lambda b: net_name(b.replace("(plane", "(net", 1)) not in keep)
    out, i, n = [], 0, 0
    while True:
        j = s.find("(net ", i)
        if j < 0:
            out.append(s[i:])
            break
        d, k = 0, j
        while True:
            if s[k] == "(":
                d += 1
            elif s[k] == ")":
                d -= 1
                if d == 0:
                    break
            k += 1
        blk = s[j:k + 1]
        if "(pins" in blk and net_name(blk) in names:
            out.append(s[i:j] + f"(net {net_name(blk)} (pins))")
            n += 1
        else:
            out.append(s[i:k + 1])
        i = k + 1
    return "".join(out), n


def autoroute_settings(bottom):
    """Freerouting's own DSN block: layer costs steer signals to F.Cu."""
    rule = ("    (layer_rule {l}\n      (active on)\n      (preferred_direction {d})\n"
            "      (preferred_direction_trace_costs {p:g})\n      (against_preferred_direction_trace_costs {q:g})\n    )\n")
    return ("    (autoroute_settings\n    (fanout off)\n    (autoroute on)\n    (postroute on)\n    (vias on)\n"
            "    (via_costs 50)\n    (plane_via_costs 5)\n    (start_ripup_costs 100)\n    (start_pass_no 1)\n"
            + rule.format(l="F.Cu", d="horizontal", p=1.0, q=1.2)
            + rule.format(l="B.Cu", d="vertical", p=bottom, q=bottom * 1.2)
            + "    )\n")


def keepout(spec):
    """DSN keepout from 'F.Cu:x0,y0,x1,y1' (board-local mm; DSN is um, y up)."""
    layer, box = spec.split(":")
    x0, y0, x1, y1 = (float(v) for v in box.split(","))
    X = lambda x: round((100 + x) * 1000)  # noqa: E731
    Y = lambda y: -round((100 + y) * 1000)  # noqa: E731
    return (f"    (keepout \"\" (polygon {layer} 0  {X(x0)} {Y(y0)}  {X(x1)} {Y(y0)}  {X(x1)} {Y(y1)}"
            f"  {X(x0)} {Y(y1)}  {X(x0)} {Y(y0)}))\n")


def fix_vias(b):
    """SES import gives vias the drill of their net class padstack; keep the
    house 0.15 mm annular ring (0.6/0.3, 0.8/0.4 ...)."""
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            w = t.GetWidth(pcbnew.F_Cu)
            if w - t.GetDrillValue() < pcbnew.FromMM(0.3):
                t.SetDrill(w - pcbnew.FromMM(0.3))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--passes", type=int, default=100, help="max passes (1.9.0 only)")
    ap.add_argument("--jar", default="1.9.0", help="Freerouting version in ~/tools/freerouting")
    ap.add_argument("--bottom-cost", type=float, default=5.0,
                    help="B.Cu trace cost relative to F.Cu (house style: bottom = ground plane)")
    ap.add_argument("--keep-plane", nargs="*", default=[],
                    help="pours to keep as Freerouting planes (e.g. a supply island under a QFP)")
    ap.add_argument("--keepout", nargs="*", default=[], metavar="LAYER:X0,Y0,X1,Y1",
                    help="router-only keep-out rectangle, board-local mm (e.g. over a supply island)")
    ap.add_argument("--keep", help="directory to keep the DSN/SES/log in")
    a = ap.parse_args()
    hw = Path(a.board) / "hardware"
    pcb = next(hw.glob("*.kicad_pcb"))
    work = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="freeroute-"))
    work.mkdir(parents=True, exist_ok=True)
    b = pcbnew.LoadBoard(str(pcb))
    full, dsn, ses, log = work / "full.dsn", work / "board.dsn", work / "board.ses", work / "freerouting.log"
    if not pcbnew.ExportSpecctraDSN(b, str(full)):
        sys.exit("DSN export failed")
    s, n = strip(full.read_text(), a.skip, a.keep_plane)
    if n != len(a.skip):
        print(f"warning: dropped {n} of {len(a.skip)} --skip nets (names not found?)")
    k = s.index("(boundary", s.index("(structure"))
    k = s.rindex("\n", 0, k) + 1
    bb = b.GetBoardEdgesBoundingBox()
    bx0, by0 = pcbnew.ToMM(bb.GetLeft()) - 100, pcbnew.ToMM(bb.GetTop()) - 100
    bx1, by1 = pcbnew.ToMM(bb.GetRight()) - 100, pcbnew.ToMM(bb.GetBottom()) - 100
    e = EDGE_BAND
    edges = [f"{l}:{r}" for l in ("F.Cu", "B.Cu") for r in (
        f"{bx0},{by0},{bx1},{by0 + e}", f"{bx0},{by1 - e},{bx1},{by1}",
        f"{bx0},{by0},{bx0 + e},{by1}", f"{bx1 - e},{by0},{bx1},{by1}")]
    s = s[:k] + autoroute_settings(a.bottom_cost) + "".join(keepout(r) for r in a.keepout + edges) + s[k:]
    dsn.write_text(s)
    ses.unlink(missing_ok=True)
    jar = JARS / f"freerouting-{a.jar}.jar"
    if a.jar.startswith("1."):
        cmd = ["xvfb-run", "-a", str(Path.home() / "tools/jre21/bin/java"), "-jar", str(jar), "-de", str(dsn), "-do", str(ses),
               "-mp", str(a.passes), "-mt", str(a.threads)]
    else:
        cmd = ["java", "-jar", str(jar), "-de", str(dsn), "-do", str(ses), "-mt", str(a.threads)]
    print("running Freerouting, up to", a.timeout, "s; log:", log)
    with open(log, "w") as fh:
        try:
            subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=a.timeout, cwd=work)
        except subprocess.TimeoutExpired:
            pass
    passes = re.findall(r"pass #(\d+) .*?\((\d+) unrouted\)", log.read_text())
    if passes:
        best = min(int(u) for _, u in passes)
        print(f"{len(passes)} passes, best {best} unrouted")
    if not ses.exists():
        sys.exit("no session file: Freerouting did not finish (see log)")
    if not pcbnew.ImportSpecctraSES(b, str(ses)):
        sys.exit("SES import failed")
    fix_vias(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(str(pcb))
    print("imported", ses)


if __name__ == "__main__":
    main()
