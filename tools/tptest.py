#!/usr/bin/env python3
"""Guided probe test: touch two points, compare R / C / L with a known good board.

  tools/tptest.py plan boards/<name>
  tools/tptest.py run  boards/<name> --golden [--port /dev/ttyUSB0 | --manual]
  tools/tptest.py run  boards/<name> --sn <serial> [--port ... | --manual] [--from N]

plan  reads boards/<name>/test/testpoints.csv (tools/testpoints.py) and the PCB
      and writes boards/<name>/test/plan.csv, the probe pairs in test order:
        net-gnd   every net against the nearest ground point of its own
                  domain (the pour it sits in);
        across    across every two-pin part (R, C, L, D, ...) between two
                  signal nets, or between two grounds (a bead to an
                  isolator's own ground), not already a pair: an open joint
                  at either end of a series part shows up here;
        iso       each ground domain against the others (isolated: open);
                  grounds joined by a part count as one domain.
      Also writes test/powered.csv: supply rails (+3V3, V5_AO, VISO...) with a
      ground point of their domain and the voltage the name implies, for a DMM
      check at first power-up.
      Steps are grouped by board side and ground point, so one probe can stay
      on the ground while the other moves, and ordered by nearest neighbour.
run   walks the plan. --golden records a known good board (run it on two or
      three to learn the normal spread); otherwise each reading is compared with
      the golden mean and the result goes to test/results/<sn>-<time>.csv.
      test/current.png shows the board with the two points of the current step
      circled (an image viewer such as eog reloads it).
      Keys: Enter = take the reading now (needed for pairs that read open),
      s = skip, b = back one step, q = quit (results so far are saved).

Measurement input (--port): the probe helper (to be built: Pi HAT or ESP32)
streams one line per measurement, about 10 per second, at 115200 baud:

    R=<ohm> C=<farad> L=<henry>

Any subset of keys, each a float or "inf" (open) or "-" (no reading), e.g.
"R=330.2 C=1.2e-10 L=-". The excitation must stay below ~0.2 V so that
in-circuit diodes and IC ESD structures do not conduct: the readings are then
those of the passives and the copper. A reading is taken automatically once it
has been stable (within 2 %) for 0.5 s after the probes touched.
--manual: type the readings instead (SI suffixes: 4.7k 100n 2.2u; "-" none).

Comparison (boards/<name>/test/tolerances.json may override per step: {"12":
{"R": 0.2}} = 20 % on step 12): R within 10 % or 0.5 ohm, C within 10 % or
20 pF, L within 20 % or 0.5 uH, plus 3 x the spread seen between golden
boards. "open" (R above 10 Mohm) only matches open.
"""
import argparse
import csv
import json
import math
import re
import select
import sys
import termios
import time
import tty
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GROUND = re.compile(r"(^|/)(GND|VSS)", re.I)
R_OPEN = 10e6
TOL = {"R": (0.10, 0.5), "C": (0.10, 20e-12), "L": (0.20, 0.5e-6)}
STABLE_S, STABLE_REL = 0.5, 0.02
SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}


# ---------------------------------------------------------------- plan

def load_points(board_dir):
    with open(board_dir / "test" / "testpoints.csv") as fh:
        return list(csv.DictReader(fh))


def two_pin_parts(board_dir):
    """[(ref, net1, net2)] for footprints with exactly two connected pads."""
    import pcbnew
    b = pcbnew.LoadBoard(str(board_dir / "hardware" / f"{board_dir.name}.kicad_pcb"))
    out = []
    for f in b.GetFootprints():
        if f.GetFPID().GetLibNickname() == "Thl_TestPoint":
            continue
        nets = [p.GetNetname() for p in f.Pads() if p.GetNumber()]
        if len(nets) == 2 and all(nets) and nets[0] != nets[1] \
                and not any(n.startswith("unconnected") for n in nets):
            out.append((f.GetReference(), nets[0], nets[1]))
    return out


RAIL = re.compile(r"(^|/)(\+\d|V[A-Z_]*\d|VCC|VDD|VISO|VBUS|VIN|V_)", re.I)


def rail_volts(name):
    """'+3V3' -> '3.3', '+12V' -> '12', 'V5_AO' -> '5'; '' when the name does not say."""
    m = re.search(r"(\d+)V(\d+)", name) or re.search(r"\+(\d+(?:\.\d+)?)V", name) \
        or re.search(r"(?:^|/)V(\d+)(?:_|$)", name)
    if not m:
        return ""
    return f"{m.group(1)}.{m.group(2)}" if m.lastindex == 2 else m.group(1)


def dist(a, b):
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def plan(board_dir):
    pts = load_points(board_dir)
    by_net = {}
    for p in pts:
        by_net.setdefault(p["net"], []).append(p)
    grounds = {n for n in by_net if GROUND.search(n)}

    def ground_point(p, g):
        cands = by_net.get(g) or [q for n in grounds for q in by_net[n]]
        same = [q for q in cands if q["side"] == p["side"]] or cands
        return min(same, key=lambda q: dist(p, q))

    def probe(net, near=None):
        cands = by_net[net]
        if near is not None:
            same = [q for q in cands if q["side"] == near["side"]] or cands
            return min(same, key=lambda q: dist(near, q))
        return cands[0]

    steps, seen = [], set()
    for net, ps in sorted(by_net.items()):
        if net in grounds:
            continue
        a = ps[0]
        g = a["ground"] or (sorted(grounds)[0] if grounds else "")
        if not g:
            continue
        steps.append(("net-gnd", "", a, ground_point(a, g)))
        seen.add(frozenset((net, g)))
    parts = sorted(two_pin_parts(board_dir))
    for ref, n1, n2 in parts:
        # a part from a net to its ground is already in that net's net-gnd step;
        # one between two grounds (a bead to an isolator's own ground) is checked here
        if (n1 in grounds) != (n2 in grounds) or n1 not in by_net or n2 not in by_net:
            continue
        if frozenset((n1, n2)) in seen:
            continue
        a = probe(n1)
        steps.append(("across", ref, a, probe(n2, a)))
        seen.add(frozenset((n1, n2)))
    # isolation: one ground per domain (grounds joined by a part are one domain)
    dom = {g: g for g in grounds}

    def root(g):
        while dom[g] != g:
            g = dom[g]
        return g
    for ref, n1, n2 in parts:
        if n1 in grounds and n2 in grounds:
            dom[root(n1)] = root(n2)
    reps = {}
    for g in sorted(grounds, key=lambda g: -len(by_net.get(g, []))):
        if g in by_net:
            reps.setdefault(root(g), g)
    gl = sorted(reps.values())
    for i, g1 in enumerate(gl):
        for g2 in gl[i + 1:]:
            a = probe(g1)
            steps.append(("iso", "", a, probe(g2, a)))

    # order: side, then per ground point a nearest-neighbour walk
    ordered = []
    for side in ("F", "B"):
        groups = {}
        for s in steps:
            if s[2]["side"] == side:
                groups.setdefault(s[3]["ref"], []).append(s)
        here = {"x": "0", "y": "0"}
        for gref in sorted(groups, key=lambda r: (groups[r][0][0] != "net-gnd", r)):
            todo = groups[gref]
            while todo:
                nxt = min(todo, key=lambda s: dist(here, s[2]))
                todo.remove(nxt)
                ordered.append(nxt)
                here = nxt[2]
    out = board_dir / "test" / "plan.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["step", "kind", "part", "side", "a_ref", "a_net", "a_x", "a_y", "b_ref", "b_net", "b_x", "b_y"])
        for k, (kind, part, a, b) in enumerate(ordered, 1):
            w.writerow([k, kind, part, a["side"], a["ref"], a["net"], a["x"], a["y"],
                        b["ref"], b["net"], b["x"], b["y"]])
    # powered check (DMM): supply rails against their ground, expected volts from the name
    rails = [n for n in by_net if n not in grounds and RAIL.search(n)]
    with open(board_dir / "test" / "powered.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["net", "expect_V", "side", "ref", "x", "y", "gnd_ref", "gnd_net"])
        for n in sorted(rails):
            a = by_net[n][0]
            g = ground_point(a, a["ground"]) if (a["ground"] or grounds) else {"ref": "", "net": ""}
            w.writerow([n, rail_volts(n), a["side"], a["ref"], a["x"], a["y"], g["ref"], g["net"]])
    counts = {k: sum(s[0] == k for s in ordered) for k in ("net-gnd", "across", "iso")}
    print(f"{board_dir.name}: {len(ordered)} steps ({', '.join(f'{v} {k}' for k, v in counts.items())}) -> {out}")


# ---------------------------------------------------------------- readings

def parse_value(v):
    v = v.strip()
    if v in ("", "-", "nan"):
        return None
    if v.lower() in ("inf", "open", "ol"):
        return math.inf
    m = re.fullmatch(r"([-+]?[\d.]+(?:e[-+]?\d+)?)\s*([pnuµmkKMG]?)[a-zA-ZΩ]*", v)
    if not m:
        raise ValueError(v)
    return float(m.group(1)) * SI.get(m.group(2), 1.0)


def parse_line(line):
    """'R=330 C=1e-10 L=-' -> {'R': 330.0, 'C': 1e-10}"""
    out = {}
    for k, v in re.findall(r"\b([RCL])=(\S+)", line):
        try:
            x = parse_value(v)
        except ValueError:
            continue
        if x is not None:
            out[k] = x
    return out


def fmt(q, x):
    if x is None:
        return "-"
    if math.isinf(x):
        return "open"
    unit = {"R": "Ω", "C": "F", "L": "H"}[q]
    for s, f in (("G", 1e9), ("M", 1e6), ("k", 1e3), ("", 1), ("m", 1e-3), ("u", 1e-6), ("n", 1e-9), ("p", 1e-12)):
        if abs(x) >= f or s == "p":
            return f"{x / f:.3g}{s}{unit}"
    return f"{x:g}{unit}"


def is_open(r):
    return r is not None and r >= R_OPEN


def stable(hist):
    if len(hist) < 2 or hist[-1][0] - hist[0][0] < STABLE_S:
        return False
    for q in ("R", "C"):
        vals = [h[1].get(q) for h in hist]
        if any(v is None for v in vals) or any(math.isinf(v) for v in vals):
            if not all(v is None or math.isinf(v) for v in vals):
                return False
            continue
        lo, hi = min(vals), max(vals)
        if hi - lo > STABLE_REL * max(abs(hi), 1e-15):
            return False
    return True


def touching(m, idle):
    """Probes on the board: anything finite on R, or C clearly above the open-air value."""
    if "R" in m and not math.isinf(m["R"]) and m["R"] < R_OPEN:
        return True
    return "C" in m and m["C"] > idle.get("C", 0.0) + 10e-12


class Meter:
    """Latest readings from the helper's serial stream."""

    def __init__(self, port, baud):
        import serial
        self.s = serial.Serial(port, baud, timeout=0)
        self.buf = b""

    def poll(self):
        """New readings since the last call: [(t, {q: value})]."""
        out = []
        self.buf += self.s.read(4096)
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            m = parse_line(line.decode(errors="replace"))
            if m:
                out.append((time.monotonic(), m))
        return out


def key_pressed(timeout):
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    return sys.stdin.read(1) if r else None


def measure_serial(meter, idle, show):
    """Wait for contact + a stable reading (or a key). Returns (reading | None, key)."""
    hist, last = [], {}
    lifted = not touching(idle, {})
    while True:
        k = key_pressed(0.05)
        for t, m in meter.poll():
            last = m
            if not touching(m, idle):
                lifted = True
                hist = []
                continue
            if lifted:
                hist.append((t, m))
                hist = [h for h in hist if t - h[0] <= STABLE_S + 0.2]
        show(last)
        if k in ("\n", "\r"):
            return last, None
        if k:
            return None, k
        if lifted and stable(hist):
            return hist[-1][1], None


def measure_manual(prompt):
    while True:
        s = input(prompt + "  R C L (e.g. '330 120p -', Enter = open, s/b/q): ").strip()
        if s in ("s", "b", "q"):
            return None, s
        parts = (s.split() + ["-", "-", "-"])[:3] if s else ["open", "-", "-"]
        try:
            vals = [parse_value(v) for v in parts]
        except ValueError:
            print("  could not read that")
            continue
        return {q: v for q, v in zip("RCL", vals) if v is not None}, None


# ---------------------------------------------------------------- compare

def judge(m, gold, tol):
    """(ok, notes) for reading m against golden {q: [values]}."""
    ok, notes = True, []
    for q in ("R", "C", "L"):
        g = [v for v in gold.get(q, []) if v is not None]
        if not g or q not in m:
            continue
        if q == "R" and (any(is_open(v) for v in g) or is_open(m[q])):
            if all(is_open(v) for v in g) != is_open(m[q]):
                ok = False
                notes.append(f"R {fmt('R', m[q])} vs {fmt('R', g[0])}")
            continue
        mean = sum(g) / len(g)
        spread = (max(g) - min(g)) / 2 if len(g) > 1 else 0.0
        rel, absol = tol.get(q, TOL[q][0]), TOL[q][1]
        lim = max(rel * abs(mean), absol) + 3 * spread
        if abs(m[q] - mean) > lim:
            ok = False
            notes.append(f"{q} {fmt(q, m[q])} vs {fmt(q, mean)} (±{fmt(q, lim)})")
    return ok, notes


def current_png(board_dir, step, px_mm=12, m=4):
    """test/current.png: the side's map with the step's two points circled."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return
    side = step["side"]
    src = board_dir / "test" / ("tp-map-top.png" if side == "F" else "tp-map-bottom.png")
    if not src.exists():
        return
    im = Image.open(src).convert("RGB")
    dr = ImageDraw.Draw(im)
    w_mm = im.size[0] / px_mm - 2 * m
    for key, col in (("a", (255, 0, 0)), ("b", (0, 0, 0))):
        x, y = float(step[f"{key}_x"]), float(step[f"{key}_y"])
        if side == "B":
            x = w_mm - x
        cx, cy = (x + m) * px_mm, (y + m) * px_mm
        for r in (2.0, 2.4):
            dr.ellipse((cx - r * px_mm, cy - r * px_mm, cx + r * px_mm, cy + r * px_mm), outline=col, width=4)
    dr.text((10, im.size[1] - 30), f"step {step['step']}: {step['a_ref']} {step['a_net']}  <->  "
            f"{step['b_ref']} {step['b_net']}", fill="black")
    tmp = board_dir / "test" / ".current.png"
    im.save(tmp)
    tmp.replace(board_dir / "test" / "current.png")


def run(board_dir, golden, sn, port, baud, manual, start):
    with open(board_dir / "test" / "plan.csv") as fh:
        steps = list(csv.DictReader(fh))
    gpath = board_dir / "test" / "golden.json"
    gold = json.loads(gpath.read_text()) if gpath.exists() else {"boards": 0, "steps": {}}
    tpath = board_dir / "test" / "tolerances.json"
    tols = json.loads(tpath.read_text()) if tpath.exists() else {}
    if not golden and not gold["steps"]:
        sys.exit("no golden readings yet: run with --golden on a known good board first")
    meter = None if manual else Meter(port, baud)
    results, new_gold = {}, {}
    old = termios.tcgetattr(sys.stdin) if not manual else None
    idle = {}
    try:
        if not manual:
            tty.setcbreak(sys.stdin.fileno())
            print("probes in the air for the open-air reading ...")
            t0 = time.monotonic()
            while time.monotonic() - t0 < 1.0:
                for t, m in meter.poll():
                    idle = m
            print("open air:", " ".join(f"{q}={fmt(q, v)}" for q, v in idle.items()) or "(no data: check the port)")
        k = start - 1
        while k < len(steps):
            st = steps[k]
            current_png(board_dir, st)
            what = f"across {st['part']}" if st["kind"] == "across" else st["kind"]
            head = (f"[{st['step']}/{len(steps)}] {'TOP' if st['side'] == 'F' else 'BOTTOM'}  "
                    f"{st['a_ref']} {st['a_net']}  <->  {st['b_ref']} {st['b_net']}   ({what})")
            g = gold["steps"].get(st["step"], {})
            exp = "  expect " + " ".join(f"{q}={fmt(q, sum(v) / len(v))}" for q, v in g.items() if v) if g else ""
            print("\n" + head + exp)
            if manual:
                m, key = measure_manual("  ")
            else:
                def show(last):
                    sys.stdout.write("\r  " + " ".join(f"{q}={fmt(q, v):>9}" for q, v in last.items()) + "   ")
                    sys.stdout.flush()
                m, key = measure_serial(meter, idle, show)
                print()
            if key == "q":
                break
            if key == "b":
                k = max(0, k - 1)
                continue
            if key == "s" or m is None:
                results[st["step"]] = (st, None, False, ["skipped"])
                k += 1
                continue
            if golden:
                new_gold[st["step"]] = m
                print("  recorded", " ".join(f"{q}={fmt(q, v)}" for q, v in m.items()), "\a")
            else:
                ok, notes = judge(m, g, tols.get(st["step"], {}))
                results[st["step"]] = (st, m, ok, notes)
                print("  PASS" if ok else "  FAIL  " + "; ".join(notes), "" if ok else "\a\a")
            k += 1
    finally:
        if old:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
    if golden:
        for s, m in new_gold.items():
            e = gold["steps"].setdefault(s, {})
            for q, v in m.items():
                e.setdefault(q, []).append(v)
        gold["boards"] += 1
        gpath.write_text(json.dumps(gold, indent=1))
        print(f"golden readings from {gold['boards']} board(s) in {gpath}")
        return
    rdir = board_dir / "test" / "results"
    rdir.mkdir(exist_ok=True)
    rpath = rdir / f"{sn}-{datetime.now():%Y%m%d-%H%M%S}.csv"
    with open(rpath, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["step", "a_ref", "a_net", "b_ref", "b_net", "R", "C", "L", "result", "notes"])
        for s, (st, m, ok, notes) in sorted(results.items(), key=lambda kv: int(kv[0])):
            m = m or {}
            w.writerow([s, st["a_ref"], st["a_net"], st["b_ref"], st["b_net"],
                        *(m.get(q, "") for q in "RCL"), "PASS" if ok else ("SKIP" if notes == ["skipped"] else "FAIL"),
                        "; ".join(notes)])
    fails = [r for r in results.values() if not r[2] and r[3] != ["skipped"]]
    print(f"\n{len(results)} steps, {len(fails)} FAIL -> {rpath}")
    for st, m, ok, notes in fails:
        print(f"  step {st['step']}: {st['a_ref']} {st['a_net']} <-> {st['b_ref']} {st['b_net']}: {'; '.join(notes)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("board")
    r = sub.add_parser("run")
    r.add_argument("board")
    r.add_argument("--golden", action="store_true", help="record a known good board")
    r.add_argument("--sn", default="board", help="serial number for the results file")
    r.add_argument("--port", default="/dev/ttyUSB0")
    r.add_argument("--baud", type=int, default=115200)
    r.add_argument("--manual", action="store_true", help="type the readings in")
    r.add_argument("--from", dest="start", type=int, default=1, help="start at this step")
    a = ap.parse_args()
    bd = Path(a.board).resolve()
    if a.cmd == "plan":
        plan(bd)
    else:
        run(bd, a.golden, a.sn, a.port, a.baud, a.manual, a.start)


if __name__ == "__main__":
    main()
