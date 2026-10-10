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
- `--manual` takes typed readings (`330 120p -`) until the helper exists.

## Probe helper (to be built)

A Pi HAT or an ESP32 with an RCL front end, connected to the PC over USB
serial. Requirements from `tools/tptest.py`:

- Stream one line per measurement, about 10 per second, 115200 baud:
  `R=<ohm> C=<farad> L=<henry>` (any subset; `inf` = open, `-` = no reading).
- Excitation below about 0.2 V, so in-circuit diodes and IC ESD structures do
  not conduct and the readings are those of the passives and the copper.
- Useful ranges: R 0.1 Ω to 10 MΩ (above that, report `inf`), C 10 pF to
  100 µF, L 1 µH to 10 mH.

Limits: at low voltage an open IC pin changes little more than a few pF on its
net, so IC joints are covered mainly by the `across` steps of the parts
around them. A later diode-signature mode (about 1 mA, both polarities,
reporting each pin's ESD diode drop) would catch open IC pins directly.
