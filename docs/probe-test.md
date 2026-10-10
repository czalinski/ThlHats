# Probe test: test points and the golden-board check

Hand-soldered SMD parts fail by open or bridged joints. Every board gets a
probe point on every net, and a guided test compares resistance, capacitance
and inductance between pairs of points with readings from a known good board.

## Test points

`tools/testpoints.py boards/<name>` (after routing; rerunnable, `--clear` to
start over):

- 1.0 mm bare-copper pads (`Thl_TestPoint:TP_Probe_D1.0mm`), no silkscreen,
  board-only (no schematic symbol; not in the BOM or the placement file).
- Placed only on copper the net already has (a track, a via or its pour), so
  no routing changes. Clear of other copper, part courtyards, all silkscreen,
  isolation gaps and each other (2 mm); 0.5 mm or more from the net's own pads,
  so the probe measures through the solder joint.
- Where nothing fits, the net's probe point is the toe of one of its SMD pads
  (e.g. `R71.2`: the end of the hand-solder pad beyond the part), which still
  measures through the joint.
- Nets whose SMD parts are on the bottom (can-ssr) get bottom test points.
  Grounds get several per domain.
- Output: `boards/<name>/test/testpoints.csv` and `tp-map-top.png` /
  `tp-map-bottom.png` (the bottom drawn as seen from below), coloured by ground
  domain.

## Test plan and run

```sh
tools/tptest.py plan boards/<name>                       # test/plan.csv, test/powered.csv
tools/tptest.py run  boards/<name> --golden --port /dev/ttyUSB0   # known good board(s)
tools/tptest.py run  boards/<name> --sn 0042 --port /dev/ttyUSB0  # board under test
```

- **net-gnd:** every net against a ground point of its own domain.
- **across:** across each two-pin part between signal nets (and beads between
  grounds), so an open joint on a series part shows.
- **iso:** isolated ground domains against each other (should read open).
- `test/powered.csv`: supply rails with a ground point and the expected
  voltage, for a DMM check at first power-up.
- `run --golden` on two or three good boards records the readings and their
  spread in `test/golden.json`. A normal run flags readings outside
  10 % (R, C) / 20 % (L) or the absolute floor, plus 3 x the golden spread.
  Per-step overrides go in `test/tolerances.json`.
- `test/current.png` shows the two points of the current step. Keys: Enter =
  take the reading now (pairs that read open), `s` skip, `b` back, `q` quit.
- `--manual` takes typed readings (`R C L D+ D-`, e.g. `330 120p - 0.61 0.58`;
  `-` for none) until the helper exists.

## Probe helper (to be built)

A Pi HAT or an ESP32 with an RCL front end and a diode-test source,
connected to the PC over USB serial. Two probes: **A (red)** goes on the
step's first point, **B (black)** on the second (`test/current.png` circles
them in red and black). Requirements from `tools/tptest.py`:

### Output

One line per measurement cycle, about 10 per second, 115200 baud 8N1:

```
R=<ohm> C=<farad> L=<henry> D+=<volt> D-=<volt>
```

Any subset of keys, in any order. Each value is a float, `inf` (open, or the
compliance limit was reached) or `-` (not measured). Example:
`R=330.2 C=1.2e-10 L=- D+=0.612 D-=inf`.

### RCL mode (R, C, L)

- Excitation below about 0.2 V peak, so in-circuit diodes and IC ESD
  structures do not conduct: the readings are those of the passives and the
  copper.
- Ranges: R 0.1 Ω to 10 MΩ (report `inf` above), C 10 pF to 100 µF, L 1 µH
  to 10 mH. About 1 % repeatability is plenty: the test compares against a
  golden board, not against nominal values.

### Diode mode (D+, D-)

Finds open IC pins, which the low-voltage RCL readings barely see.

- A current source of about **1 mA**, with a compliance limit of **2.0 V**.
- **D+:** probe A driven positive with respect to B. **D-:** probe A driven
  negative. Both are reported as positive magnitudes, in volts, with about
  1 mV resolution. Report `inf` when the voltage reaches the limit (no
  conduction).
- On a net-to-ground step, D- forward-biases the ESD diode from ground to
  every IC pin on the net (about 0.5-0.7 V), and D+ the diode from the pin to
  the IC's supply (in series with whatever the rail looks like). A pin that
  is not soldered drops out of that parallel set, and the voltage rises. A
  net whose only IC pin is open reads `inf`.
- Settle before reading: decoupling capacitors on the net charge at 1 mA
  (100 µF takes about 60 ms to reach 0.6 V). Report a D value only once it
  has stopped rising, or report `-` until then.
- Discharge the probes, shorting A to B through about 100 Ω for a few ms,
  after each diode measurement and before the next RCL measurement. Charge
  left on the board's capacitors would otherwise upset the low-voltage
  readings.
- One cycle can run RCL, D+ and D- in turn and report all five keys. A
  slower cycle is fine; the PC waits for 0.5 s of stable readings.

### Safety

The helper is only for **unpowered** boards. Its inputs should survive
touching a charged capacitor up to the board's highest rail (24 V, or about
120 V on can-ssr's load side if its bulk capacitors were not discharged).
Use series resistance and clamps on the probe inputs.

### Tolerances on the PC side

D+ and D- pass within 50 mV of the golden mean (plus 3 x the golden spread).
`inf` only matches `inf`.
