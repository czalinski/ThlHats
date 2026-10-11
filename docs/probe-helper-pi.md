# Probe helper: Raspberry Pi + Waveshare High-Precision AD HAT

Builds the meter for the probe test (docs/probe-test.md) from a Raspberry Pi,
the Waveshare **High-Precision AD HAT** (TI ADS1263) and a small board of
resistors and diodes (`boards/probe-helper`). There are no ICs to add. The Pi also runs the test
script:

```sh
tools/tptest.py run boards/<name> --golden --meter ads1263
tools/tptest.py run boards/<name> --sn 0042 --meter ads1263
```

Software: `tools/probe_ads1263.py`. The measurement logic was checked against
a simulated board (`--sim`). Check it against known parts on the bench before
trusting it (see Bring-up).

## Why this works without extra chips

The ADS1263 measures to 32 bits, so the small signals need no amplifier. It
also has two programmable current sources (IDACs), which give the 1 mA for
the diode mode. Everything else is switched by the Pi's GPIOs:

- **Low-voltage sources (R and C).** Each range is two GPIOs with a divider
  between them: 1.2 kΩ from the top GPIO, 47 Ω to the bottom one. The
  divider's middle point is the source node N, one per range: **N_lo, N_mid
  and N_hi** in the circuit below, each read by the ADC and feeding probe A
  through that range's reference resistor (100 Ω, 100 kΩ, 10 MΩ). With the
  top GPIO high (3.3 V) and the bottom one low, N sits at about 0.12 V
  (3.3 V × 47 / 1247) with roughly 45 Ω behind it. With both GPIOs
  set as inputs, the source floats completely: no load, no switch chip. From
  N, a reference resistor feeds probe A. The ADC reads the drop across the
  reference (the current) and across the probes (the voltage), so the GPIOs'
  own resistance cancels out. The board never sees more than about 0.15 V.
- **Ground switches.** A GPIO driven low pulls probe B (or A) to ground
  through 470 Ω. Set as an input, it lets go.
- **Diode mode.** The ADS1263's IDAC drives 1 mA into probe A or B through
  its own 1 kΩ, while the other probe's ground switch is on.

## Parts

The resistors and clamps sit on a small through-hole board,
`boards/probe-helper` (65 × 46 mm, PCBWay). It plugs into the HAT's screw
terminal and bolts to the HAT and the Pi (see Assembly).

| Qty | Part | Use |
|---|---|---|
| 1 | Raspberry Pi: Zero 2 W, 3, 4 or 5 (a Zero W works, but C readings are slower). Pi 4/5 size: the board uses the Pi's far mounting holes | runs everything |
| 1 | Waveshare High-Precision AD HAT (ADS1263), with its pass-through 40-pin header | ADC, current sources |
| 1 | probe-helper PCB with its BOM (`tools/fab.py boards/probe-helper`): 17 axial resistors, 4 × 1N4148, 2x5 box header, 2-way 5.08 mm screw terminal | sources, references, clamps |
| 13 | single right-angle pins cut from a 1x40 2.54 mm right-angle header (or 0.8 mm tinned wire bent 90°) | J1, into the HAT's terminal |
| 1 | 10-way IDC ribbon cable, socket on both ends (same-side crimp, about 15 cm) | J2 to Pi pins 31-40 on the HAT |
| 2 | M2.5 spacer about 4 mm, plus washers to adjust | tabs to the HAT's terminal-side holes |
| 2 | M2.5 standoff, HAT standoff height + about 5.6 mm (e.g. 11 mm HAT standoffs: about 16.6 mm) | board to the Pi's far holes |
| 1 pair | test leads with needle tips, red (A) and black (B) | J3 |

The 100 Ω and 100 kΩ references are 0.1 % in the BOM; 1 % works too, since
readings are compared against golden boards, not taken as absolute.

Optional: a USB foot switch that types Enter, to take a reading on pairs that
read open without putting a probe down.

## Circuit

```
   GPIO13 ──1.2k──┬──47R── GPIO19     lo source, node N_lo
                  ├─────── IN4
                  └──100R──────┐
   GPIO16 ──1.2k──┬──47R── GPIO26     mid source, node N_mid
                  ├─────── IN6
                  └──100k──────┤
   GPIO20 ──1.2k──┬──47R── GPIO21     hi source, node N_hi
                  ├─────── IN8
                  └──10M───────┤
                               │
   IN3 (IDAC A) ──1k───────────┤
   IN2 (sense A) ──1k──────────┤
   GPIO12 ──470R───────────────┤      ground switch A
                            NODE A ──22R── probe A (red)
                               │
                 1N4148 NODE A → +5 V (AVDD), 1N4148 GND → NODE A

   IN1 (IDAC B) ──1k───────────┐
   IN0 (sense B) ──1k──────────┤
   GPIO6 ──470R────────────────┤      ground switch B
                            NODE B ──22R── probe B (black)
                 1N4148 NODE B → +5 V (AVDD), 1N4148 GND → NODE B

   COM, AVSS ── GND      IN5, IN7, IN9 not connected
```

Schematic: `boards/probe-helper/hardware/probe-helper.kicad_sch`.

**Why these AIN inputs.** The HAT filters every input: 47 Ω in series, 47 pF
to ground, and **100 nF across each pair** IN0/IN1, IN2/IN3, IN4/IN5,
IN6/IN7, IN8/IN9 (Waveshare schematic, "Input Filtering"). So a probe's
sense and IDAC leads share a pair: both end at the same probe node, so the
100 nF sees no signal and does not slow the readings. Each source node pairs
with an unused input, so no two of our nodes are coupled through 100 nF.

**GPIOs.** The HAT's header passes all 40 pins through. A 10-way IDC socket
on Pi pins 31-40 (socket pin 1 on Pi pin 31, flush with the end of the
header) carries 8 GPIOs and 2 GND to J2 on the board (J2 pin n = Pi pin
30 + n):

| J2 / Pi pin | Signal | J2 / Pi pin | Signal |
|---|---|---|---|
| 1 / 31 | GPIO6: ground switch B | 2 / 32 | GPIO12: ground switch A |
| 3 / 33 | GPIO13: lo top | 4 / 34 | GND |
| 5 / 35 | GPIO19: lo bottom | 6 / 36 | GPIO16: mid top |
| 7 / 37 | GPIO26: mid bottom | 8 / 38 | GPIO20: hi top |
| 9 / 39 | GND | 10 / 40 | GPIO21: hi bottom |

The HAT's own P4 sensor header also carries GPIO 6, 13, 19 and 26: leave it
empty.

### Check against your HAT

- **Terminal order.** Seen from the top with the terminal at the top edge,
  the HAT reads COM, IN9 … IN0, AVSS, AVDD from left to right. J1's
  silkscreen (AVDD … COM, seen from the board's top with the tabs at the
  top) must face the same terminals when the board is in place.
- **Pins the HAT uses.** Waveshare's demo code uses SPI0 (GPIO 9, 10, 11),
  **CS = GPIO22, DRDY = GPIO17, RESET = GPIO18**. The board's GPIOs avoid
  those. If your HAT's wiki or silkscreen says otherwise, change `PIN_RST`,
  `PIN_CS` and `PIN_DRDY` at the top of `tools/probe_ads1263.py`.
- **Supply.** The ADS1263 needs AVDD = 5 V (fed from the Pi's 5 V through a
  0 Ω on the HAT). Keep the reference on the internal 2.5 V (the default).
- **COM-GND jumper.** Leave it on (interface header, INCOM to AVSS); COM is
  also grounded on the board.
- **RTD resistors.** R14, R16, R19 and R21 ("0R/NC", RTD section) must not
  be fitted: R16 would join IN3 (IDAC A) to IN6 (N_mid).

### Assembly

1. Solder the resistors, diodes (bands as on the silkscreen), J2 and J3 on
   the top side.
2. Fit the board to the HAT: tabs over the HAT's terminal-side holes on the
   4 mm spacers, the far holes on standoffs to the Pi. The board sits above
   the HAT so that J1's pins, soldered on the **bottom** side, are at the
   height of the wire entries.
3. Push the 13 single right-angle pins through J1's holes from below,
   plastic bodies under the board, pins pointing at the HAT, and slide them
   into the terminal's wire entries (about 5 mm deep). Adjust the spacers
   with washers until the pins enter straight, then tighten the terminal
   screws and solder the pins from the top. Every terminal gets a pin, even
   the unused ones, for strength.
4. Plug the ribbon into J2 and onto Pi pins 31-40 on the HAT.

Keep the board as it is: N_hi, the 10 MΩ and node A carry nanoamps at the
high range.

## Pi setup

```sh
sudo raspi-config nonint do_spi 0                 # enable SPI
sudo apt install python3-spidev python3-lgpio python3-pil git
git clone <this repo> && cd ThlHats
python3 tools/probe_ads1263.py selftest           # ADC ID, the three source voltages
```

The test plans (`boards/*/test/plan.csv`) and maps are in the repo. `plan`
needs KiCad and runs on the PC; `run` needs only Python. To see
`test/current.png` (the two points to touch), use a monitor, or open it over
the network from the PC (e.g. `sshfs`, or `eog` with X forwarding).

## Bring-up

1. `selftest`: the ID register should report an ADS1263, and each source
   node should read 100-150 mV (3.3 V × 47 / 1247 = 124 mV, less a little for
   the GPIO output resistance).
2. `cal zero` with the probe tips pressed together: stores the lead
   resistance (about 44 Ω: two 22 Ω resistors plus the leads) in
   `~/.config/thlhats/probe-cal.json`.
3. `cal open` with the probes apart: stores the leads' own capacitance.
4. `stream` and touch known parts:
   - 10 Ω, 1 kΩ, 100 kΩ and 1 MΩ resistors should read within a few %.
   - 1 nF, 100 nF and 10 µF capacitors should read within about 10 %.
   - A 1N4148 should give D+ about 0.6 V and D- inf (or the reverse, with
     the probes swapped).
   - With the probes open, every reading should be inf or "-". A finite R
     at the high range with the probes open is leakage into node A, most
     likely the clamps (1N4148: a few nA at 5 V). Fit low-leakage DO-35
     diodes (1N3595, BAS45A) for D1/D2 then.
5. Then run `tptest.py run --golden --meter ads1263` on two or three good
   boards.

## What it measures, and its limits

| Reading | Range | Notes |
|---|---|---|
| R | about 0.1 Ω to 50 MΩ, at ≤ 0.15 V | lowest range that carries a usable current. A net that is only capacitive (no DC path) reads inf. |
| C | about 50 pF to 100 µF | from the rise time constant, with the parallel R from the R step taken into account. "-" when the rise is too fast to sample (a few kΩ in parallel with ≥ 1 µF), or too small. |
| D+ / D- | 0 to 2.0 V at 1 mA, inf above | probe A positive (D+) or negative (D-). The value is taken once it stops rising. |
| L | not measured | joints of inductors and beads show in R. |

- One cycle takes about 0.3 s, or up to about 2 s on nets with large
  capacitors. The test takes a reading once two cycles agree.
- Readings are compared against golden boards, so absolute accuracy matters
  less than repeatability. Keep the same probes and leads, and redo
  `cal zero` / `cal open` after changing them.
- **Unpowered boards only.** The clamps and 22 Ω resistors survive brushing a
  small charged capacitor, not a powered 24 V rail or can-ssr's 120 V side.
  Discharge boards before testing.
