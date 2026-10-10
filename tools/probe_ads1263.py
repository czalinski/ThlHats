#!/usr/bin/env python3
"""Probe helper: Raspberry Pi + Waveshare High-Precision AD HAT (TI ADS1263).

Measures R, C and the diode drops D+ / D- between probe A (red) and probe B
(black) for tools/tptest.py (docs/probe-test.md). Wiring and parts:
docs/probe-helper-pi.md. No ICs besides the HAT: resistors, two 1N4148 per
probe, Pi GPIOs.

  python3 tools/probe_ads1263.py stream            # one line per cycle: R=.. C=.. L=- D+=.. D-=..
  python3 tools/probe_ads1263.py cal zero          # probes shorted together: lead resistance
  python3 tools/probe_ads1263.py cal open          # probes apart: lead capacitance
  python3 tools/probe_ads1263.py selftest          # ADC ID, source voltages, open-probe readings
  python3 tools/probe_ads1263.py stream --sim 1k,100n,0.6   # no hardware: simulated R, C, diode
tools/tptest.py run ... --meter ads1263 uses it directly (no serial link).

How it measures (ADS1263 with the PGA bypassed: +-2.5 V on 32 bits):
  R   One of three low-voltage sources drives A through its reference
      resistor while B returns to ground through GPIO_GND_B. A source is two
      GPIOs with a divider between them (top GPIO high, bottom GPIO low: about
      0.19 V open circuit; both as inputs: the source floats, no load). The
      ADC reads V(N)-V(A) across the reference (current) and V(A)-V(B) (the
      board): R = V(A-B) / I - lead resistance. 100 ohm, 100 kohm, 10 Mohm
      references, lowest first. The board never sees more than ~0.2 V.
  C   The same source switched on while the ADC samples V(A-B) at ~7 kSPS:
      the rise time constant tau, with the source resistance Rs and the
      board's parallel resistance Rp from the R step: C = tau (1/Rs + 1/Rp).
  D   The ADS1263's IDAC pushes 1 mA into A (D+) or B (D-) through its own
      1 kohm lead; the other probe returns to ground through its GPIO. The
      reading is taken once it stops rising (decoupling capacitors charge),
      minus 1 mA x lead resistance; above 2.0 V it is reported as inf.
  L   Not measured ("-"): joints of inductors and beads show in R.
Between steps both probes are pulled to ground (discharge).
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

# ------------------------------------------------------------------ wiring

# Waveshare High-Precision AD HAT: SPI0 plus these (its demo code's config.py)
PIN_RST, PIN_CS, PIN_DRDY = 18, 22, 17
# Ours (docs/probe-helper-pi.md). Range: (top GPIO, bottom GPIO, AIN of its
# node N, reference ohm, source resistance seen by the board for C).
RANGES = {
    "lo": (23, 5, 2, 100.0),
    "mid": (24, 6, 3, 100e3),
    "hi": (25, 12, 4, 10e6),
}
R_DIV = 45.0            # 1.2k || 47R divider + GPIO output resistance (about)
GND_A, GND_B = 26, 27   # probe ground switches, each through 470R
R_GNDSW = 470.0 + 30.0
AIN_A, AIN_B = 0, 1     # sense (1k each, no current)
AIN_IA, AIN_IB = 8, 9   # IDAC outputs (1k each to the probe nodes)
AINCOM = 10

CAL_FILE = Path.home() / ".config" / "thlhats" / "probe-cal.json"
D_LIMIT = 2.0           # V: diode compliance reported as inf
R_INF = 50e6            # above this R is reported as inf
IDAC_MA = 1.0

# ADS1263 registers and commands (datasheet SBAS661)
REG_POWER, REG_INTERFACE, REG_MODE0, REG_MODE1, REG_MODE2, REG_INPMUX = 0x01, 0x02, 0x03, 0x04, 0x05, 0x06
REG_IDACMUX, REG_IDACMAG, REG_REFMUX = 0x0D, 0x0E, 0x0F
CMD_RESET, CMD_START1, CMD_STOP1, CMD_RDATA1 = 0x06, 0x08, 0x0A, 0x12
DR = {100: 0x7, 400: 0x8, 1200: 0x9, 7200: 0xC}
SINC1, SINC4 = 0, 3
IDAC_1MA = 0x6
VREF = 2.5


# ------------------------------------------------------------------ hardware

class Hw:
    """lgpio + spidev access to the HAT and our GPIOs."""

    def __init__(self):
        import lgpio
        import spidev
        self.lg = lgpio
        self.h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self.h, PIN_RST, 1)
        lgpio.gpio_claim_output(self.h, PIN_CS, 1)
        lgpio.gpio_claim_input(self.h, PIN_DRDY)
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 2_000_000
        self.spi.mode = 1
        self.mode1 = self.mode2 = None
        self.reset()

    # GPIO: drive or float (input, no pull)
    def drive(self, pin, level):
        self.lg.gpio_claim_output(self.h, pin, level)

    def float(self, pin):
        self.lg.gpio_claim_input(self.h, pin, self.lg.SET_PULL_NONE)

    def _xfer(self, data):
        self.lg.gpio_write(self.h, PIN_CS, 0)
        r = self.spi.xfer2(list(data))
        self.lg.gpio_write(self.h, PIN_CS, 1)
        return r

    def cmd(self, c):
        self._xfer([c])

    def wreg(self, reg, val):
        self._xfer([0x40 | reg, 0x00, val & 0xFF])

    def rreg(self, reg):
        return self._xfer([0x20 | reg, 0x00, 0x00])[2]

    def reset(self):
        self.lg.gpio_write(self.h, PIN_RST, 0)
        time.sleep(0.01)
        self.lg.gpio_write(self.h, PIN_RST, 1)
        time.sleep(0.05)
        self.cmd(CMD_STOP1)
        self.wreg(REG_POWER, 0x01)          # clear RESET flag, internal 2.5 V reference on
        self.wreg(REG_INTERFACE, 0x05)      # status byte + checksum
        self.wreg(REG_REFMUX, 0x00)         # internal reference
        self.idac(None)
        self.setup(1200, SINC4, pulse=True)

    def setup(self, sps, filt, pulse):
        self.wreg(REG_MODE0, 0x40 if pulse else 0x00)
        if self.mode1 != filt << 5:
            self.mode1 = filt << 5
            self.wreg(REG_MODE1, self.mode1)
        if self.mode2 != (0x80 | DR[sps]):  # PGA bypassed: inputs may span 0 V to AVDD
            self.mode2 = 0x80 | DR[sps]
            self.wreg(REG_MODE2, self.mode2)

    def idac(self, ain):
        """1 mA out of ain (None = off)."""
        if ain is None:
            self.wreg(REG_IDACMAG, 0x00)
            self.wreg(REG_IDACMUX, 0xBB)
        else:
            self.wreg(REG_IDACMUX, 0xB0 | ain)
            self.wreg(REG_IDACMAG, IDAC_1MA)

    def ident(self):
        return self.rreg(0x00)

    def _wait_drdy(self, timeout=0.5):
        t0 = time.monotonic()
        while self.lg.gpio_read(self.h, PIN_DRDY):
            if time.monotonic() - t0 > timeout:
                raise TimeoutError("ADS1263 DRDY")

    def _read(self):
        r = self._xfer([CMD_RDATA1, 0, 0, 0, 0, 0, 0])
        d = r[2:6]
        if (sum(d) + 0x9B) & 0xFF != r[6]:
            raise IOError("ADS1263 checksum")
        return int.from_bytes(bytes(d), "big", signed=True) * VREF / 2**31

    def conv(self, p, n, sps=1200):
        """One settled conversion V(p) - V(n)."""
        self.setup(sps, SINC4, pulse=True)
        self.wreg(REG_INPMUX, p << 4 | n)
        self.cmd(CMD_START1)
        self._wait_drdy()
        return self._read()

    def stream(self, p, n, duration, on_start, done=None):
        """[(t, V(p) - V(n))] sampled as fast as possible for up to duration s;
        on_start() runs after the first sample (t = 0 there)."""
        self.setup(7200, SINC1, pulse=False)
        self.wreg(REG_INPMUX, p << 4 | n)
        self.cmd(CMD_START1)
        out, t0 = [], None
        try:
            while True:
                self._wait_drdy()
                v = self._read()
                t = time.perf_counter()
                if t0 is None:
                    t0 = t
                    out.append((0.0, v))
                    on_start()
                    continue
                out.append((t - t0, v))
                if t - t0 > duration or (done and done(out)):
                    return out
        finally:
            self.cmd(CMD_STOP1)

    def close(self):
        self.spi.close()
        self.lg.gpiochip_close(self.h)


class SimHw:
    """A board model for testing without hardware: probes across Rp || C,
    optionally with a diode (forward drop vf) in parallel."""

    def __init__(self, rp=math.inf, c=0.0, vf=None, c_lead=30e-12):
        self.rp, self.c, self.vf = rp, c + c_lead, vf
        self.pins, self.idac_on, self.v, self.t = {}, None, 0.0, time.monotonic()

    def drive(self, pin, level):
        self._advance()
        self.pins[pin] = level

    def float(self, pin):
        self._advance()
        self.pins.pop(pin, None)

    def idac(self, ain):
        self._advance()
        self.idac_on = ain

    def ident(self):
        return 0x23

    def _source(self):
        """(open-circuit volts, source resistance) driving the board, or None."""
        for name, (top, bot, ain, rref) in RANGES.items():
            if self.pins.get(top) == 1 and self.pins.get(bot) == 0:
                return 0.194, R_DIV + rref + 44 + (R_GNDSW if self.pins.get(GND_B) == 0 else 1e12), name
            if self.pins.get(top) == 0 and self.pins.get(bot) == 0:
                return 0.0, R_DIV + rref + 44 + R_GNDSW, name
        if self.pins.get(GND_A) == 0 and self.pins.get(GND_B) == 0:
            return 0.0, 2 * R_GNDSW, None
        return None

    def _target(self):
        """(final volts across the board, time constant)."""
        if self.idac_on is not None:
            vt = min(self.vf if self.vf else math.inf, IDAC_MA * 1e-3 * self.rp, 3.9)
            return vt, max(self.c * max(vt, 1e-3) / (IDAC_MA * 1e-3), 1e-7)
        src = self._source()
        if src is None:
            return self.v, math.inf
        vo, rs, _ = src
        rp = self.rp
        vt = vo * rp / (rs + rp) if not math.isinf(rp) else vo
        rpar = rs * rp / (rs + rp) if not math.isinf(rp) else rs
        if self.vf is not None:
            vt = min(vt, self.vf * 0.4)          # far below vf: the diode barely conducts
        return vt, max(self.c * rpar, 1e-7)

    def _advance(self):
        now = time.monotonic()
        vt, tau = self._target()
        if not math.isinf(tau):
            self.v = vt + (self.v - vt) * math.exp(-(now - self.t) / tau)
        self.t = now

    def _current(self):
        src = self._source()
        if src is None or self.idac_on is not None:
            return 0.0
        vo, rs, _ = src
        return (vo - self.v) / rs

    def conv(self, p, n, sps=1200):
        time.sleep(1.0 / sps)
        self._advance()
        noise = 2e-6 * (2 * ((time.perf_counter_ns() >> 3) % 7) / 6 - 1)
        i = self._current()
        if (p, n) == (AIN_A, AIN_B):
            return self.v + i * 44 + noise
        if (p, n) == (AIN_B, AIN_A):
            return self.v + noise
        for name, (top, bot, ain, rref) in RANGES.items():
            if (p, n) == (ain, AIN_A):
                return i * rref + noise
        return 0.0

    def stream(self, p, n, duration, on_start, done=None):
        out, t0 = [], time.perf_counter()
        out.append((0.0, self.conv(p, n, 7200)))
        on_start()
        while True:
            v = self.conv(p, n, 7200)
            t = time.perf_counter() - t0
            out.append((t, v))
            if t > duration or (done and done(out)):
                return out

    def close(self):
        pass


# ------------------------------------------------------------------ measurement

class Probe:
    def __init__(self, hw=None):
        self.hw = hw or Hw()
        self.cal = {"r_zero": 0.0, "c_open": 0.0}
        if CAL_FILE.exists():
            self.cal.update(json.loads(CAL_FILE.read_text()))
        self.all_off()

    # ---- switching
    def all_off(self):
        self.hw.idac(None)
        for top, bot, ain, rref in RANGES.values():
            self.hw.float(top)
            self.hw.float(bot)
        self.hw.float(GND_A)
        self.hw.float(GND_B)

    def source(self, name, on=True):
        top, bot, ain, rref = RANGES[name]
        if on:
            self.hw.drive(bot, 0)
            self.hw.drive(top, 1)
        else:
            self.hw.float(top)
            self.hw.float(bot)

    def discharge(self, s=0.005, limit=0.001, timeout=0.5):
        """Both probes to ground (A through the 100R source with both GPIOs low and
        through its switch, B through its switch) until the board holds under 1 mV."""
        self.all_off()
        top, bot, ain, rref = RANGES["lo"]
        self.hw.drive(top, 0)
        self.hw.drive(bot, 0)
        self.hw.drive(GND_A, 0)
        self.hw.drive(GND_B, 0)
        t0 = time.monotonic()
        time.sleep(s)
        while time.monotonic() - t0 < timeout and abs(self.hw.conv(AIN_A, AIN_B, 7200)) > limit:
            time.sleep(0.005)
        self.all_off()

    # ---- R
    def measure_r(self):
        """(R ohm or inf, settled). Lowest range whose reference carries a usable current."""
        self.discharge()
        r = math.inf
        for name in ("lo", "mid", "hi"):
            top, bot, ain, rref = RANGES[name]
            self.hw.drive(GND_B, 0)
            self.source(name)
            # a capacitor on the net charges first: settled when a reading matches
            # one taken a quarter of the elapsed time earlier
            t0, settled = time.monotonic(), False
            v_na = self.hw.conv(ain, AIN_A)
            while time.monotonic() - t0 < 0.5:
                time.sleep(max(0.003, 0.25 * (time.monotonic() - t0)))
                prev, v_na = v_na, self.hw.conv(ain, AIN_A)
                if abs(v_na - prev) <= 0.002 * abs(v_na) + 2e-6:
                    settled = True
                    break
            v_ab = self.hw.conv(AIN_A, AIN_B)
            self.source(name, False)
            i = v_na / rref
            if not settled:
                break                                    # still charging: no DC path at this level
            if v_na > 0.01 or name == "hi":
                if i > 0 and v_ab / i < R_INF:
                    r = max(v_ab / i - self.cal["r_zero"], 0.0)
                break
        self.all_off()
        return r

    # ---- C
    def measure_c(self, rp):
        """Farad, or None. Sources from fast to slow: lo (100R), mid (100k), hi (10M).
        Start with mid if the board's parallel resistance rp leaves it at least a
        quarter of its drive (rp >= Rs / 3), else lo; step to a larger source
        resistor if the rise is too fast to sample, to a smaller one if it is too
        small or too slow to fit. C = tau (1/Rs + 1/rp)."""
        ladder = ["lo", "mid", "hi"]
        k = 1 if rp >= (R_DIV + RANGES["mid"][3] + R_GNDSW) / 3 else 0
        tried = set()
        while 0 <= k < len(ladder) and ladder[k] not in tried:
            name = ladder[k]
            tried.add(name)
            top, bot, ain, rref = RANGES[name]
            rs = R_DIV + rref + self.cal["r_zero"] + R_GNDSW
            self.discharge()
            self.hw.drive(GND_B, 0)

            def settled(pts):
                """No change since three quarters of the elapsed time (a slow rise looks flat over a short window)."""
                if len(pts) < 40:
                    return False
                t_end, v_end = pts[-1]
                v_then = next(v for t, v in pts if t >= 0.75 * t_end)
                return abs(v_end - v_then) <= 0.002 * abs(v_end) + 5e-6
            pts = self.hw.stream(AIN_A, AIN_B, 0.6, lambda: self.source(name), settled)
            self.source(name, False)
            self.all_off()
            if len(pts) < 10:
                return None
            v0 = pts[0][1]
            vf = sum(v for t, v in pts[-10:]) / 10
            if not settled(pts):
                # still rising at the end: final value from three equally spaced points,
                # vf = (v1 v3 - v2^2) / (v1 + v3 - 2 v2); a straight ramp means far too slow
                t_end = pts[-1][0]
                v1, v2, v3 = (next(v for t, v in pts if t >= f * t_end) for f in (1 / 3, 2 / 3, 1.0))
                den = v1 + v3 - 2 * v2
                if den >= -1e-6 or not (v1 * v3 - v2 * v2) / den > v3:
                    k -= 1                                  # too slow: smaller source resistor
                    continue
                vf = (v1 * v3 - v2 * v2) / den
            span = vf - v0
            covered = (pts[-1][1] - v0) / span if span > 0 else 0.0
            if vf < 0.005 or span < 0.005 or covered < 0.5:
                k -= 1                                      # too small or too slow
                continue
            rising = [(t, v) for t, v in pts[1:] if 0.1 < (v - v0) / span < 0.8]   # fit band of the rise
            if len(rising) < 6:
                if k + 1 < len(ladder) and rp >= (R_DIV + RANGES[ladder[k + 1]][3] + R_GNDSW) / 3:
                    k += 1                                  # too fast: larger source resistor
                    continue
                if len(rising) < 3:
                    return None
            # ln(1 - (v - v0) / (vf - v0)) = -t / tau
            xs = [t for t, v in rising]
            ys = [math.log(1 - (v - v0) / span) for t, v in rising]
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            sxx = sum((x - mx) ** 2 for x in xs)
            if sxx <= 0:
                return None
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
            if slope >= 0:
                return None
            tau = -1.0 / slope
            c = tau * (1.0 / rs + (0.0 if math.isinf(rp) else 1.0 / rp)) - self.cal["c_open"]
            return max(c, 0.0)
        return None

    # ---- D
    def measure_d(self, plus):
        """Volts at 1 mA (A positive if plus), inf at the compliance limit."""
        self.discharge()
        if plus:
            self.hw.drive(GND_B, 0)
            self.hw.idac(AIN_IA)
            p, n = AIN_A, AIN_B
        else:
            self.hw.drive(GND_A, 0)
            self.hw.idac(AIN_IB)
            p, n = AIN_B, AIN_A
        # settled when a reading matches one taken a quarter of the elapsed time earlier
        t0 = time.monotonic()
        v = self.hw.conv(p, n, 400)
        while v <= D_LIMIT and time.monotonic() - t0 < 0.8:
            time.sleep(max(0.003, 0.25 * (time.monotonic() - t0)))
            prev, v = v, self.hw.conv(p, n, 400)
            if abs(v - prev) < 0.002:
                break
        self.hw.idac(None)
        self.discharge()
        v -= IDAC_MA * 1e-3 * self.cal["r_zero"]
        return math.inf if v > D_LIMIT else max(v, 0.0)

    def measure(self):
        """{'R': .., 'C': .., 'D+': .., 'D-': ..} (keys left out when not measured)."""
        out = {}
        r = self.measure_r()
        out["R"] = r
        c = self.measure_c(r)
        if c is not None:
            out["C"] = c
        out["D+"] = self.measure_d(True)
        out["D-"] = self.measure_d(False)
        return out

    def close(self):
        self.all_off()
        self.hw.close()


def line(m):
    def f(q):
        v = m.get(q)
        return "-" if v is None else ("inf" if math.isinf(v) else f"{v:.6g}")
    return f"R={f('R')} C={f('C')} L=- D+={f('D+')} D-={f('D-')}"


def make_probe(sim):
    if not sim:
        return Probe()
    parts = (sim.split(",") + ["", "", ""])[:3]

    def val(s, default):
        if not s or s == "-":
            return default
        mult = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6}
        return float(s[:-1]) * mult[s[-1]] if s[-1] in mult else float(s)
    return Probe(SimHw(rp=val(parts[0], math.inf), c=val(parts[1], 0.0), vf=val(parts[2], None)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["stream", "cal", "selftest"])
    ap.add_argument("what", nargs="?", choices=["zero", "open"])
    ap.add_argument("--sim", help="simulate a board: R,C,diode-Vf (e.g. 1k,100n,0.6; '-' for none)")
    ap.add_argument("--count", type=int, default=0, help="stream: stop after N lines")
    a = ap.parse_args()
    p = make_probe(a.sim)
    try:
        if a.cmd == "stream":
            k = 0
            while not a.count or k < a.count:
                print(line(p.measure()), flush=True)
                k += 1
        elif a.cmd == "selftest":
            print(f"ADS1263 ID register: 0x{p.hw.ident():02X} (DEV_ID in bits 7-5: 001 = ADS1263)")
            for name, (top, bot, ain, rref) in RANGES.items():
                p.source(name)
                time.sleep(0.01)
                print(f"source {name}: node N = {p.hw.conv(ain, AINCOM) * 1000:.1f} mV (expect 120-200)")
                p.source(name, False)
            print("probes as they are now:", line(p.measure()))
        elif a.cmd == "cal":
            if a.what == "zero":
                p.cal["r_zero"] = 0.0
                rs = [p.measure_r() for _ in range(5)]
                p.cal["r_zero"] = sorted(rs)[2]
                print(f"lead resistance {p.cal['r_zero']:.3f} ohm")
            elif a.what == "open":
                p.cal["c_open"] = 0.0
                cs = [c for c in (p.measure_c(math.inf) for _ in range(5)) if c is not None]
                p.cal["c_open"] = sorted(cs)[len(cs) // 2] if cs else 0.0
                print(f"open-probe capacitance {p.cal['c_open'] * 1e12:.1f} pF")
            else:
                sys.exit("cal zero | cal open")
            if not a.sim:
                CAL_FILE.parent.mkdir(parents=True, exist_ok=True)
                CAL_FILE.write_text(json.dumps(p.cal, indent=1))
    finally:
        p.close()


if __name__ == "__main__":
    main()
