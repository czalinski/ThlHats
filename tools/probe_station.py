#!/usr/bin/env python3
"""Probe station: full-screen touch UI for the probe test (docs/probe-test.md).

Runs on the probe-helper Pi (Raspberry Pi + Waveshare AD HAT, 800 x 480 touch
screen; docs/probe-helper-pi.md) and walks the same plan as tools/tptest.py:

  1. Tap the board type (every boards/<name>/test/plan.csv), and TEST or GOLDEN.
  2. TEST: enter the serial number on the keypad (or AUTO = date-time).
  3. Each step shows the board map with the two points: red probe A, black B.
     The readings and their limits are shown live; once they have been in
     bounds (TEST: against the golden mean, as tptest.py judges; GOLDEN: stable
     within 2 %) for 4 s, the step passes and the next one comes up.
     Lift the probes between steps. Steps that should read open pass once the
     probes are seen on the board (C above open air), or with OPEN.
     BACK / SKIP / FAIL (record the current reading as a failure). Tap the map
     to zoom.
  4. Summary: failures, RETEST FAILS, DONE. Results go to
     test/results/<sn>-<time>.csv (as tptest.py); GOLDEN runs are merged into
     test/golden.json.

  python3 tools/probe_station.py                  # full screen, AD HAT if it answers, else demo
  python3 tools/probe_station.py --meter demo     # simulated meter and operator (no hardware)
  python3 tools/probe_station.py --windowed       # 800 x 480 window, for development
  python3 tools/probe_station.py --kiosk          # no cursor, EXIT needs a 2 s press

--meter demo simulates readings (and, when a board has no golden.json, the
expected values). Demo runs write nothing to golden.json; their results files
start with DEMO-. Esc quits.
"""
import argparse
import csv
import json
import math
import os
import queue
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tptest  # noqa: E402
from tptest import QTY, TOL, fmt, is_open, judge, touching  # noqa: E402

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
W, H = 800, 480
HOLD_S = 4.0
STABLE_REL = 0.02
PASS_FLASH_S = 0.7
SHOWN = ("R", "C", "D+", "D-")  # L is not measured by the AD HAT helper

BG = (24, 26, 30)
PANEL = (38, 41, 48)
FG = (236, 238, 242)
DIM = (150, 155, 165)
GREEN = (46, 170, 90)
RED = (210, 50, 50)
AMBER = (225, 160, 30)
BLUE = (60, 120, 210)
BTN = (64, 70, 82)
BTN_DOWN = (95, 104, 120)
PROBE_A = (230, 30, 30)
PROBE_B = (10, 10, 10)


# ---------------------------------------------------------------- meters

class DemoMeter:
    """Simulated meter and operator: probes in the air for a moment, then on
    the points; one step in five first reads a bad joint until 'reseated'."""

    def __init__(self):
        self.truth, self.t0, self.air, self.bad = {}, time.monotonic(), 1.0, False
        self.rng = random.Random()
        self.lock = threading.Lock()

    def set_truth(self, truth):
        with self.lock:
            self.truth = dict(truth)
            self.t0 = time.monotonic()
            self.air = self.rng.uniform(0.8, 1.8)
            self.bad = self.rng.random() < 0.2

    def poll(self):
        time.sleep(0.3)
        with self.lock:
            dt = time.monotonic() - self.t0
            truth = self.truth
            if dt < self.air or not truth:
                return [(time.monotonic(), {"R": math.inf, "C": 12e-12, "D+": math.inf, "D-": math.inf})]
            m = {}
            for q, v in truth.items():
                m[q] = v if math.isinf(v) else v * self.rng.gauss(1.0, 0.004)
            if self.bad and dt < self.air + 3.0:
                if math.isinf(m.get("R", 0)):
                    m["D-"] = math.inf
                else:
                    m["R"] *= 2.6
            elif dt < self.air + 0.6 and "R" in m and not math.isinf(m["R"]):
                m["R"] *= self.rng.uniform(1.1, 1.5)  # probe settling on the pad
        return [(time.monotonic(), m)]


class MeterThread(threading.Thread):
    def __init__(self, meter):
        super().__init__(daemon=True)
        self.meter, self.q = meter, queue.Queue()

    def run(self):
        while True:
            try:
                for t, m in self.meter.poll():
                    self.q.put((t, m))
            except Exception as e:  # keep the UI alive; show the error
                self.q.put((time.monotonic(), {"error": str(e)}))
                time.sleep(1.0)


def open_meter(kind):
    """(meter, label, is_demo)"""
    if kind in ("auto", "ads1263"):
        try:
            return tptest.PiMeter(), "AD HAT meter", False
        except Exception as e:
            if kind == "ads1263":
                sys.exit(f"AD HAT meter: {e}")
            return DemoMeter(), f"DEMO meter (AD HAT: {str(e)[:40]})", True
    return DemoMeter(), "DEMO meter", True


# ---------------------------------------------------------------- boards

def demo_truth(board, step):
    """Plausible readings for a step, the same every time (demo only)."""
    r = random.Random(f"{board}:{step['step']}")
    kind, part = step["kind"], step["part"]
    if kind == "iso":
        return {"R": math.inf, "C": r.choice([22e-12, 47e-12, 68e-12]), "D+": math.inf, "D-": math.inf}
    if kind == "across":
        if part.startswith(("R", "JP")):
            return {"R": r.choice([100.0, 1e3, 4.7e3, 10e3, 33.0]), "C": r.choice([100e-12, 1e-9]),
                    "D+": math.inf, "D-": math.inf}
        if part.startswith(("FB", "L")):
            return {"R": r.choice([0.15, 0.3, 0.05]), "D+": 0.0, "D-": 0.0}
        return {"R": math.inf, "C": r.choice([100e-9, 1e-6, 10e-9]), "D+": math.inf, "D-": math.inf}
    if r.random() < 0.15:
        return {"R": r.choice([4.7e3, 10e3, 100e3]), "C": r.choice([1e-9, 100e-9]),
                "D+": r.uniform(0.9, 1.4), "D-": r.uniform(0.5, 0.7)}
    return {"R": math.inf, "C": r.choice([22e-12, 100e-12, 1e-9, 100e-9, 10e-6]),
            "D+": r.choice([math.inf, r.uniform(0.6, 1.3)]), "D-": r.uniform(0.5, 0.72)}


class Board:
    def __init__(self, d):
        self.dir, self.name = d, d.name
        with open(d / "test" / "plan.csv") as fh:
            self.steps = list(csv.DictReader(fh))
        gp = d / "test" / "golden.json"
        self.gold = json.loads(gp.read_text()) if gp.exists() else {"boards": 0, "steps": {}}
        tp = d / "test" / "tolerances.json"
        self.tols = json.loads(tp.read_text()) if tp.exists() else {}
        self.maps = {}

    def expected(self, st, demo):
        """{q: [golden values]} for a step; synthesized in demo mode when there is no golden board."""
        g = self.gold["steps"].get(st["step"])
        if g:
            return g
        if demo:
            return {q: [v] for q, v in demo_truth(self.name, st).items()}
        return {}

    def map_image(self, side):
        """(PIL image faded for markers, crop box) for 'F' / 'B', or None."""
        if side not in self.maps:
            from PIL import Image, ImageChops
            p = self.dir / "test" / ("tp-map-top.png" if side == "F" else "tp-map-bottom.png")
            if not p.exists():
                self.maps[side] = None
            else:
                im = Image.open(p).convert("RGB")
                box = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox() or (0, 0, *im.size)
                faded = Image.blend(im, Image.new("RGB", im.size, "white"), 0.55)
                self.maps[side] = (faded, box)
        return self.maps[side]


def find_boards():
    return [Board(p.parents[1]) for p in sorted(REPO.glob("boards/*/test/plan.csv"))]


def net_short(n):
    return n.rsplit("/", 1)[-1] or n


# ---------------------------------------------------------------- UI helpers

class Ui:
    def __init__(self, surf):
        self.s = surf
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        self.paths = {False: path if os.path.exists(path) else None, True: bold if os.path.exists(bold) else None}
        self.fonts = {}
        self.buttons, self.pressed = [], None

    def font(self, size, bold=False):
        if (size, bold) not in self.fonts:
            self.fonts[size, bold] = pygame.font.Font(self.paths[bold], size)
        return self.fonts[size, bold]

    def text(self, s, pos, size=18, col=FG, bold=False, anchor="topleft", maxw=None):
        font = self.font(size, bold)
        if maxw:
            while font.size(s)[0] > maxw and len(s) > 2:
                s = s[:-2] + "…"
        img = font.render(s, True, col)
        r = img.get_rect(**{anchor: pos})
        self.s.blit(img, r)
        return r

    def button(self, rect, label, cb, col=BTN, size=22, enabled=True, sub=None, hold=0.0):
        rect = pygame.Rect(rect)
        down = self.pressed is not None and self.pressed[0] == rect and enabled
        c = BTN_DOWN if down else col
        if not enabled:
            c = (48, 50, 56)
        pygame.draw.rect(self.s, c, rect, border_radius=10)
        if down and hold:
            frac = min(1.0, (time.monotonic() - self.pressed[1]) / hold)
            pygame.draw.rect(self.s, AMBER, (rect.x, rect.bottom - 6, rect.w * frac, 6), border_radius=3)
        fg = FG if enabled else (100, 104, 112)
        if sub:
            self.text(label, (rect.centerx, rect.centery - 12), size, fg, True, "center", rect.w - 12)
            self.text(sub, (rect.centerx, rect.centery + 18), 16, DIM if enabled else fg, False, "center", rect.w - 12)
        else:
            self.text(label, rect.center, size, fg, True, "center", rect.w - 8)
        if enabled:
            self.buttons.append((rect, cb, hold))


# ---------------------------------------------------------------- app

class App:
    def __init__(self, surf, meter, meter_label, demo, kiosk=False):
        self.ui = Ui(surf)
        self.s = surf
        self.meter, self.meter_label, self.demo, self.kiosk = meter, meter_label, demo, kiosk
        self.thread = MeterThread(meter)
        self.thread.start()
        self.boards = find_boards()
        self.mode = "test"
        self.screen = "home"
        self.board = None
        self.sn = ""
        self.dialog = None
        self.last, self.last_t, self.error = {}, 0.0, ""
        self.quit = False
        self.map_cache = {}

    # ------------------------------------------------ run control
    def start(self, board):
        self.board = board
        self.screen = "serial" if self.mode == "test" else "step"
        self.sn = ""
        if self.mode == "golden":
            self.begin_run(board.steps)

    def begin_run(self, steps, keep=False):
        self.steps, self.k = steps, 0
        if not keep:
            self.results, self.new_gold = {}, {}
            self.stamp = datetime.now()
            self.rpath = None
        self.idle, self.phase = None, "idle"  # first reading = open air
        self.screen = "step"
        self.enter_step()

    def enter_step(self):
        self.hold, self.ref, self.lifted, self.zoom = None, None, False, False
        self.passed_at = None
        st = self.steps[self.k]
        self.exp = self.board.expected(st, self.demo)
        if self.demo:
            truth = {q: v[0] for q, v in self.exp.items() if v}
            self.meter.set_truth(truth if self.phase != "idle" else {})

    def record(self, m, ok, notes):
        st = self.steps[self.k]
        if self.mode == "golden":
            if m is not None:
                self.new_gold[st["step"]] = m
        else:
            self.results[st["step"]] = (st, m, ok, notes)
        self.next_step()

    def next_step(self):
        self.k += 1
        if self.k >= len(self.steps):
            self.finish()
        else:
            self.enter_step()

    def finish(self):
        b = self.board
        if self.mode == "golden":
            if not self.demo and self.new_gold:
                for s, m in self.new_gold.items():
                    e = b.gold["steps"].setdefault(s, {})
                    for q, v in m.items():
                        e.setdefault(q, []).append(v)
                b.gold["boards"] += 1
                (b.dir / "test" / "golden.json").write_text(json.dumps(b.gold, indent=1))
                self.saved = f"golden board {b.gold['boards']} -> test/golden.json"
            else:
                self.saved = "demo: golden.json not changed" if self.demo else "nothing recorded"
        else:
            rdir = b.dir / "test" / "results"
            rdir.mkdir(exist_ok=True)
            if self.rpath is None:
                sn = ("DEMO-" if self.demo else "") + (self.sn or "board")
                self.rpath = rdir / f"{sn}-{self.stamp:%Y%m%d-%H%M%S}.csv"
            with open(self.rpath, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["step", "a_ref", "a_net", "b_ref", "b_net", *QTY, "result", "notes"])
                for s, (st, m, ok, notes) in sorted(self.results.items(), key=lambda kv: int(kv[0])):
                    m = m or {}
                    w.writerow([s, st["a_ref"], st["a_net"], st["b_ref"], st["b_net"],
                                *(m.get(q, "") for q in QTY),
                                "PASS" if ok else ("SKIP" if notes == ["skipped"] else "FAIL"), "; ".join(notes)])
            self.saved = f"-> {self.rpath.relative_to(b.dir)}"
        self.screen = "summary"

    # ------------------------------------------------ readings
    def on_reading(self, t, m):
        if "error" in m:
            self.error = m["error"]
            return
        self.error = ""
        self.last, self.last_t = m, time.monotonic()
        if self.screen != "step" or self.passed_at:
            return
        if self.phase == "idle":
            self.idle, self.phase = m, "step"
            self.enter_step()
            return
        if not touching(m, self.idle):
            self.lifted, self.hold, self.ref = True, None, None
            return
        if not self.lifted:
            return
        good = self.stable(m) if self.mode == "golden" else self.in_bounds(m)
        if good:
            if self.hold is None:
                self.hold = time.monotonic()
        else:
            self.hold = None

    def stable(self, m):
        if self.ref is None:
            self.ref = m
            return True
        for q in SHOWN:
            a, b = self.ref.get(q), m.get(q)
            if (a is None) != (b is None):
                break
            if a is None:
                continue
            if math.isinf(a) or math.isinf(b):
                if math.isinf(a) != math.isinf(b):
                    break
                continue
            if abs(a - b) > STABLE_REL * max(abs(a), 1e-15):
                break
        else:
            return True
        self.ref = m
        return False

    def tol(self):
        return self.board.tols.get(self.steps[self.k]["step"], {})

    def in_bounds(self, m):
        if not self.exp:
            return False
        if any(v and q not in m for q, v in self.exp.items()):
            return False
        return judge(m, self.exp, self.tol())[0]

    def expect_open(self):
        return bool(self.exp) and all(all(is_open(q, x) for x in v) for q, v in self.exp.items() if v)

    def tick(self):
        while True:
            try:
                t, m = self.thread.q.get_nowait()
            except queue.Empty:
                break
            self.on_reading(t, m)
        now = time.monotonic()
        if self.screen == "step" and self.passed_at and now - self.passed_at >= PASS_FLASH_S:
            self.passed_at = None
            self.record(self.pass_m, True, [])
        elif self.screen == "step" and self.hold is not None and not self.passed_at \
                and now - self.hold >= HOLD_S:
            self.pass_m, self.passed_at, self.hold = self.last, now, None

    # ------------------------------------------------ input
    def press(self, pos):
        for rect, cb, hold in reversed(self.ui.buttons):
            if rect.collidepoint(pos):
                self.ui.pressed = (rect, time.monotonic(), hold, cb)
                return
        self.ui.pressed = None
        if self.screen == "step" and not self.dialog and MAP.collidepoint(pos):
            self.zoom = not self.zoom

    def release(self, pos):
        p, self.ui.pressed = self.ui.pressed, None
        if p and p[0].collidepoint(pos) and time.monotonic() - p[1] >= p[2]:
            p[3]()

    # ------------------------------------------------ drawing
    def draw(self):
        self.ui.buttons = []
        self.s.fill(BG)
        getattr(self, "draw_" + self.screen)()
        if self.dialog:
            self.draw_dialog()

    def header(self, title, sub=""):
        u = self.ui
        pygame.draw.rect(self.s, PANEL, (0, 0, W, 40))
        r = u.text(title, (12, 20), 22, FG, True, "midleft")
        if sub:
            u.text(sub, (r.right + 12, 21), 16, DIM, False, "midleft")
        if self.demo:
            u.text("DEMO", (W - 116, 20), 18, AMBER, True, "midright")

    def draw_home(self):
        u = self.ui
        self.header("Probe test", "touch the board type")
        u.button((W - 104, 4, 98, 32), "EXIT", self.ask_exit, size=16, hold=2.0 if self.kiosk else 0.0)
        for i, (m, lab) in enumerate((("test", "TEST"), ("golden", "GOLDEN"))):
            u.button((12 + i * 150, 52, 140, 50), lab, (lambda m=m: setattr(self, "mode", m)),
                     col=(BLUE if self.mode == m else BTN))
        u.text("compare with golden boards" if self.mode == "test" else "record a known good board",
               (320, 77), 18, DIM, anchor="midleft")
        cols, bw, bh, gap = 3, 252, 112, 10
        for i, b in enumerate(self.boards):
            x, y = 12 + (i % cols) * (bw + gap), 116 + (i // cols) * (bh + gap)
            ng = b.gold["boards"]
            ok = self.mode == "golden" or ng > 0 or self.demo
            sub = f"{len(b.steps)} steps · " + (f"golden ×{ng}" if ng else ("demo values" if self.demo else "no golden"))
            u.button((x, y, bw, bh), b.name, (lambda b=b: self.start(b)), size=30, enabled=ok, sub=sub)
        pygame.draw.rect(self.s, PANEL, (0, H - 34, W, 34))
        u.text("⚠ Unpowered boards only: discharge first", (12, H - 17), 16, AMBER, anchor="midleft")
        u.text(self.meter_label + (f": {self.error[:40]}" if self.error else ""), (W - 12, H - 17), 16,
               RED if self.error else DIM, anchor="midright", maxw=380)

    def draw_serial(self):
        u = self.ui
        self.header(self.board.name, "serial number")
        u.button((W - 104, 4, 98, 32), "BACK", self.go_home, size=16)
        pygame.draw.rect(self.s, PANEL, (40, 70, 320, 80), border_radius=10)
        u.text(self.sn or "—", (200, 110), 48, FG if self.sn else DIM, True, "center")
        u.text("Type the board's serial number,", (40, 180), 18, DIM)
        u.text("or AUTO to use the date and time.", (40, 204), 18, DIM)
        u.button((40, 300, 150, 80), "AUTO", self.auto_sn, size=24)
        u.button((210, 300, 150, 80), "START", self.serial_ok, col=GREEN, size=24, enabled=bool(self.sn))
        keys = "123456789⌫0✓"
        for i, k in enumerate(keys):
            x, y = 430 + (i % 3) * 120, 56 + (i // 3) * 104
            if k == "⌫":
                cb, col = (lambda: setattr(self, "sn", self.sn[:-1])), BTN
            elif k == "✓":
                cb, col = self.serial_ok, GREEN
            else:
                cb, col = (lambda k=k: setattr(self, "sn", (self.sn + k)[:10])), BTN
            u.button((x, y, 110, 96), k, cb, col=col, size=34, enabled=(k != "✓" or bool(self.sn)))

    def auto_sn(self):
        self.sn = datetime.now().strftime("%m%d%H%M")

    def serial_ok(self):
        self.begin_run(self.board.steps)

    def go_home(self):
        self.screen, self.dialog = "home", None
        if self.demo:
            self.meter.set_truth({})

    def ask_exit(self):
        self.dialog = ("Close the probe station?", lambda: setattr(self, "quit", True))

    def ask_quit_run(self):
        msg = "End this run? Results so far are saved." if self.mode == "test" else \
            "End this run? A partial golden board is not saved." if not self.demo else "End this run?"
        self.dialog = (msg, self.quit_run)

    def quit_run(self):
        self.dialog = None
        if self.mode == "golden":
            self.go_home()
        else:
            self.finish()

    def draw_dialog(self):
        u = self.ui
        u.buttons = []
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        self.s.blit(shade, (0, 0))
        r = pygame.Rect(150, 130, 500, 220)
        pygame.draw.rect(self.s, PANEL, r, border_radius=14)
        u.text(self.dialog[0], (r.centerx, r.y + 60), 22, FG, True, "center", r.w - 30)
        u.button((r.x + 30, r.bottom - 100, 200, 76), "NO", lambda: setattr(self, "dialog", None), size=26)
        u.button((r.right - 230, r.bottom - 100, 200, 76), "YES", self.dialog[1], col=RED, size=26)

    # ------------------------------------------------ step screen
    def draw_step(self):
        u = self.ui
        st = self.steps[self.k]
        nfail = sum(1 for r in self.results.values() if not r[2] and r[3] != ["skipped"]) if self.mode == "test" else 0
        npass = sum(1 for r in self.results.values() if r[2]) if self.mode == "test" else len(self.new_gold)
        sub = ("TEST  SN " + (self.sn or "-")) if self.mode == "test" else "GOLDEN"
        self.header(self.board.name, sub)
        u.text(f"✓ {npass}", (W - 330, 20), 22, GREEN, True, "midleft")
        if self.mode == "test":
            u.text(f"✗ {nfail}", (W - 250, 20), 22, RED if nfail else DIM, True, "midleft")
        u.button((W - 104, 4, 98, 32), "END", self.ask_quit_run, size=16)

        self.draw_map(st)

        x0, pw = PX, W - PX - 8
        if self.phase == "idle":
            u.text("Hold the probes apart", (x0, 70), 26, FG, True)
            u.text("reading open air …", (x0, 110), 18, DIM)
            return
        u.text(f"Step {self.k + 1}", (x0, 50), 30, FG, True)
        u.text(f"/ {len(self.steps)}", (x0 + u.font(30, True).size(f"Step {self.k + 1}")[0] + 8, 62), 18, DIM)
        kind = {"net-gnd": "net to ground", "iso": "isolation"}.get(st["kind"], f"across {st['part']}")
        side = "TOP" if st["side"] == "F" else "BOTTOM"
        u.text(f"{kind} · {side}", (W - 12, 64), 16, AMBER if side == "BOTTOM" else DIM, anchor="topright")
        for i, (key, col, name) in enumerate((("a", PROBE_A, "A"), ("b", PROBE_B, "B"))):
            y = 104 + i * 40
            pygame.draw.circle(self.s, col, (x0 + 14, y + 14), 14)
            pygame.draw.circle(self.s, FG, (x0 + 14, y + 14), 14, 2)
            u.text(name, (x0 + 14, y + 15), 16, FG, True, "center")
            r = u.text(st[f"{key}_ref"], (x0 + 38, y), 26, FG, True)
            u.text(net_short(st[f"{key}_net"]), (r.right + 10, y + 6), 18, DIM, maxw=x0 + pw - r.right - 10)

        # readings table
        y = 190
        u.text("expect", (x0 + 60, y), 14, DIM)
        u.text("reading", (x0 + 230, y), 14, DIM)
        y += 20
        tol = self.tol()
        rows = [q for q in SHOWN if self.exp.get(q) or (self.mode == "golden" and q in self.last)]
        for q in rows:
            g = [v for v in self.exp.get(q, []) if v is not None]
            m = self.last.get(q)
            if g and any(is_open(q, v) for v in g):
                e = "open"
            elif g:
                mean = sum(g) / len(g)
                spread = (max(g) - min(g)) / 2 if len(g) > 1 else 0.0
                lim = max(tol.get(q, TOL[q][0]) * abs(mean), TOL[q][1]) + 3 * spread
                e = f"{fmt(q, mean)} ±" + (f"{lim * 1e3:.0f}mV" if q.startswith("D") else fmt(q, lim))
            else:
                e = "—"
            live = self.touch_now()
            if m is None or not live:
                col = DIM
            elif self.mode == "golden" or not g:
                col = FG
            else:
                col = GREEN if judge({q: m}, {q: g}, tol)[0] else RED
            pygame.draw.rect(self.s, PANEL, (x0, y, pw, 30), border_radius=6)
            u.text(q, (x0 + 10, y + 15), 18, FG, True, "midleft")
            u.text(e, (x0 + 60, y + 15), 18, DIM, anchor="midleft", maxw=165)
            u.text(fmt(q, m) if m is not None else "—", (x0 + pw - 10, y + 15), 22, col, True, "midright")
            y += 34

        # status banner
        now = time.monotonic()
        r = pygame.Rect(x0, 352, pw, 44)
        if self.passed_at:
            pygame.draw.rect(self.s, GREEN, r, border_radius=8)
            u.text("✓ PASS" if self.mode == "test" else "✓ RECORDED", r.center, 26, FG, True, "center")
        elif self.hold is not None:
            frac = min(1.0, (now - self.hold) / HOLD_S)
            pygame.draw.rect(self.s, PANEL, r, border_radius=8)
            pygame.draw.rect(self.s, GREEN, (r.x, r.y, r.w * frac, r.h), border_radius=8)
            u.text(f"HOLD  {max(0.0, HOLD_S - (now - self.hold)):.1f} s", r.center, 24, FG, True, "center")
        else:
            if not self.lifted:
                msg, col = "LIFT THE PROBES", BTN
            elif not self.touch_now():
                msg, col = "PROBE A → B", BTN
            elif self.mode == "test" and not self.exp:
                msg, col = "NO GOLDEN READING", AMBER
            elif self.mode == "test":
                msg, col = "OUT OF RANGE", RED
            else:
                msg, col = "STEADY …", AMBER
            pygame.draw.rect(self.s, col, r, border_radius=8)
            u.text(msg, r.center, 22, FG, True, "center")

        # buttons
        by, bw = 404, (pw - 3 * 8) // 4
        u.button((x0, by, bw, 70), "BACK", self.step_back, enabled=self.k > 0)
        u.button((x0 + bw + 8, by, bw, 70), "SKIP", self.step_skip)
        if self.mode == "test":
            u.button((x0 + 2 * (bw + 8), by, bw, 70), "FAIL", self.step_fail, col=RED)
        u.button((x0 + 3 * (bw + 8), by, bw, 70), "OPEN", self.step_open,
                 col=BLUE if self.expect_open() or self.mode == "golden" else BTN)

    def touch_now(self):
        return bool(self.last) and self.idle is not None and touching(self.last, self.idle) \
            and time.monotonic() - self.last_t < 3.0

    def step_back(self):
        if self.k > 0:
            self.k -= 1
            self.enter_step()

    def step_skip(self):
        if self.mode == "golden":
            self.next_step()
        else:
            self.record(None, False, ["skipped"])

    def step_fail(self):
        m = self.last if self.touch_now() else {}
        notes = judge(m, self.exp, self.tol())[1] if m else []
        self.record(m or None, False, notes or ["failed by operator"])

    def step_open(self):
        """Take the reading as open (pairs that should read open, probes on the points)."""
        m = {q: math.inf for q in ("R", "D+", "D-")}
        if "C" in self.last:
            m["C"] = self.last["C"]
        if self.mode == "golden":
            self.record(m, True, [])
        else:
            ok, notes = judge(m, self.exp, self.tol()) if self.exp else (False, ["no golden reading"])
            self.record(m, ok, notes)

    def draw_map(self, st):
        pygame.draw.rect(self.s, (255, 255, 255), MAP)
        mi = self.board.map_image(st["side"])
        if not mi:
            self.ui.text("no map", MAP.center, 22, DIM, anchor="center")
            return
        img, box = mi
        px, mrg = 12, 4
        w_mm = img.size[0] / px - 2 * mrg
        pts = []
        for key in ("a", "b"):
            x, y = float(st[f"{key}_x"]), float(st[f"{key}_y"])
            if st["side"] == "B":
                x = w_mm - x
            pts.append(((x + mrg) * px, (y + mrg) * px))
        if self.zoom:
            cx, cy = (pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2
            span = max(abs(pts[0][0] - pts[1][0]), abs(pts[0][1] - pts[1][1])) * 1.5 + 30 * px
            span = min(span, box[2] - box[0], box[3] - box[1])
            x0 = min(max(cx - span / 2, box[0]), box[2] - span)
            y0 = min(max(cy - span / 2, box[1]), box[3] - span)
            box = (x0, y0, x0 + span, y0 + span)
        key = (self.board.name, st["side"], tuple(round(v) for v in box))
        if key not in self.map_cache:
            from PIL import Image
            bw, bh = box[2] - box[0], box[3] - box[1]
            sc = min(MAP.w / bw, MAP.h / bh)
            crop = img.crop(tuple(round(v) for v in box)).resize((max(1, round(bw * sc)), max(1, round(bh * sc))),
                                                                 Image.LANCZOS)
            surf = pygame.image.frombuffer(crop.tobytes(), crop.size, "RGB").convert()
            if len(self.map_cache) > 12:
                self.map_cache.clear()
            self.map_cache[key] = (surf, sc)
        surf, sc = self.map_cache[key]
        ox = MAP.x + (MAP.w - surf.get_width()) // 2
        oy = MAP.y + (MAP.h - surf.get_height()) // 2
        self.s.set_clip(MAP)
        self.s.blit(surf, (ox, oy))
        sp = [(ox + (x - box[0]) * sc, oy + (y - box[1]) * sc) for x, y in pts]
        pygame.draw.line(self.s, (120, 120, 120), sp[0], sp[1], 2)
        pulse = 4 * (1 + math.sin(time.monotonic() * 6))
        for (x, y), col, name in zip(sp, (PROBE_A, PROBE_B), ("A", "B")):
            pygame.draw.circle(self.s, col, (x, y), 15 + pulse, 4)
            pygame.draw.circle(self.s, col, (x, y), 5)
            tag = pygame.Rect(0, 0, 26, 24)
            tag.midbottom = (x, y - 20 - pulse)
            pygame.draw.rect(self.s, col, tag, border_radius=5)
            self.ui.text(name, tag.center, 16, (255, 255, 255), True, "center")
        self.s.set_clip(None)
        self.ui.text("tap to zoom" if not self.zoom else "tap: whole board", (MAP.x + 6, MAP.bottom - 4), 14,
                     (120, 120, 120), anchor="bottomleft")

    # ------------------------------------------------ summary
    def draw_summary(self):
        u = self.ui
        self.header(self.board.name, "GOLDEN" if self.mode == "golden" else f"SN {self.sn or '-'}")
        if self.mode == "golden":
            u.text(f"Recorded {len(self.new_gold)} of {len(self.board.steps)} steps", (24, 70), 30, FG, True)
            u.text(self.saved, (24, 120), 18, DIM)
            u.button((W - 224, H - 100, 200, 80), "DONE", self.go_home, col=BLUE, size=26)
            return
        res = list(self.results.values())
        fails = [r for r in res if not r[2] and r[3] != ["skipped"]]
        skips = [r for r in res if r[3] == ["skipped"]]
        npass = len(res) - len(fails) - len(skips)
        missing = len(self.board.steps) - len(res)
        good = not fails and not skips and not missing
        r = pygame.Rect(16, 52, W - 32, 70)
        pygame.draw.rect(self.s, GREEN if good else RED if fails else AMBER, r, border_radius=10)
        u.text("BOARD PASSED" if good else f"{len(fails)} FAILED" if fails else "INCOMPLETE", r.center, 34, FG, True,
               "center")
        u.text(f"✓ {npass} pass   ✗ {len(fails)} fail   {len(skips)} skipped   {missing} not done", (24, 134), 20, FG)
        u.text(self.saved, (24, 162), 16, DIM)
        y = 194
        for st, m, ok, notes in sorted(fails + skips, key=lambda r: int(r[0]["step"]))[:6]:
            u.text(f"{st['step']:>3}  {st['a_ref']} {net_short(st['a_net'])} ↔ {st['b_ref']} "
                   f"{net_short(st['b_net'])}", (24, y), 16, FG, maxw=420)
            u.text("; ".join(notes), (450, y), 16, RED if notes != ["skipped"] else AMBER, maxw=W - 470)
            y += 26
        if len(fails) + len(skips) > 6:
            u.text(f"… {len(fails) + len(skips) - 6} more in the results file", (24, y), 16, DIM)
        redo = [r[0] for r in sorted(fails + skips, key=lambda r: int(r[0]["step"]))]
        u.button((24, H - 100, 260, 80), "RETEST FAILS", lambda: self.begin_run(redo, keep=True),
                 col=AMBER, size=24, enabled=bool(redo))
        u.button((W - 224, H - 100, 200, 80), "DONE", self.go_home, col=BLUE, size=26)


MAP = pygame.Rect(4, 44, 432, 432)
PX = MAP.right + 10


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meter", choices=["auto", "ads1263", "demo"], default="auto")
    ap.add_argument("--windowed", action="store_true", help="800 x 480 window instead of full screen")
    ap.add_argument("--kiosk", action="store_true", help="hide the cursor; EXIT needs a 2 s press")
    a = ap.parse_args()
    meter, label, demo = open_meter(a.meter)
    pygame.init()
    if a.windowed:
        win = pygame.display.set_mode((W, H))
    else:
        win = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Probe test")
    if a.kiosk:
        pygame.mouse.set_visible(False)
    canvas = win if win.get_size() == (W, H) else pygame.Surface((W, H))
    app = App(canvas, meter, label, demo, a.kiosk)
    sx, sy = win.get_width() / W, win.get_height() / H

    def to_canvas(pos):
        return int(pos[0] / sx), int(pos[1] / sy)
    clock = pygame.time.Clock()
    while not app.quit:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                app.quit = True
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                app.press(to_canvas(ev.pos))
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                app.release(to_canvas(ev.pos))
        app.tick()
        app.draw()
        if canvas is not win:
            pygame.transform.smoothscale(canvas, win.get_size(), win)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    main()
