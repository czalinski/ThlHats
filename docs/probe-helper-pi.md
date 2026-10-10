# Probe helper: Raspberry Pi + Waveshare High-Precision AD HAT

Builds the meter for the probe test (docs/probe-test.md) from a Raspberry Pi,
the Waveshare **High-Precision AD HAT** (TI ADS1263) and a handful of
resistors and diodes. There are no ICs to add. The Pi also runs the test
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
  between them. With the top GPIO high and the bottom one low, the divider
  node N sits at about 0.19 V with roughly 45 Ω behind it. With both GPIOs
  set as inputs, the source floats completely: no load, no switch chip. From
  N, a reference resistor feeds probe A. The ADC reads the drop across the
  reference (the current) and across the probes (the voltage), so the GPIOs'
  own resistance cancels out. The board never sees more than about 0.2 V.
- **Ground switches.** A GPIO driven low pulls probe B (or A) to ground
  through 470 Ω. Set as an input, it lets go.
- **Diode mode.** The ADS1263's IDAC drives 1 mA into probe A or B through
  its own 1 kΩ, while the other probe's ground switch is on.

## Parts

| Qty | Part | Use |
|---|---|---|
| 1 | Raspberry Pi: Zero 2 W, 3, 4 or 5 (a Zero W works, but C readings are slower) | runs everything |
| 1 | Waveshare High-Precision AD HAT (ADS1263) | ADC, current sources |
| 1 | 2x20 stacking header, or wires soldered to the Pi's header pins | reach the GPIOs under the HAT |
| 3 | 1.2 kΩ 1 % | source dividers, top |
| 3 | 47 Ω 1 % | source dividers, bottom |
| 1 | 100 Ω 0.1 % (1 % works: the readings are compared, not absolute) | low-range reference |
| 1 | 100 kΩ 0.1 % (or 1 %) | mid-range reference |
| 1 | 10 MΩ 1 % | high-range reference |
| 2 | 470 Ω | probe ground switches |
| 4 | 1 kΩ | ADC sense leads (2), IDAC leads (2) |
| 2 | 22 Ω | probe series resistors (limit surge) |
| 4 | 1N4148 | probe clamps to GND and +5 V |
| 1 pair | test leads with needle tips, red (A) and black (B) | |
| | perfboard or a terminal strip, short wires | |

Optional: a USB foot switch that types Enter, to take a reading on pairs that
read open without putting a probe down.

## Circuit

```
                      Pi GPIO23 ──1.2k──┬──47R── GPIO5      (lo source; node N_lo)
                                         ├───────────────── AIN2
                                         └──100R────────┐
                      Pi GPIO24 ──1.2k──┬──47R── GPIO6      (mid source; node N_mid)
                                         ├───────────────── AIN3
                                         └──100k────────┤
                      Pi GPIO25 ──1.2k──┬──47R── GPIO12     (hi source; node N_hi)
                                         ├───────────────── AIN4
                                         └──10M─────────┤
                                                         │
   AIN8 (IDAC) ──1k─────────────────────────────────────┤
   AIN0 (sense) ──1k────────────────────────────────────┤
   GPIO26 ──470R────────────────────────────────────────┤   (ground switch A)
                                                     NODE A ──22R── probe A (red)
                                                         │
                                          1N4148 to GND ─┤├─ 1N4148 to +5V
                                                     (cathode to +5V, anode to GND side)

   AIN9 (IDAC) ──1k─────────────────────────────────────┐
   AIN1 (sense) ──1k────────────────────────────────────┤
   GPIO27 ──470R────────────────────────────────────────┤   (ground switch B)
                                                     NODE B ──22R── probe B (black)
                                          1N4148 to GND ─┤├─ 1N4148 to +5V

   AINCOM ── GND (HAT ground)
```

Wiring table:

| From | Through | To |
|---|---|---|
| GPIO23 (pin 16) | 1.2 kΩ | N_lo |
| N_lo | 47 Ω | GPIO5 (pin 29) |
| N_lo | wire | AIN2 |
| N_lo | 100 Ω | node A |
| GPIO24 (pin 18) | 1.2 kΩ | N_mid |
| N_mid | 47 Ω | GPIO6 (pin 31) |
| N_mid | wire | AIN3 |
| N_mid | 100 kΩ | node A |
| GPIO25 (pin 22) | 1.2 kΩ | N_hi |
| N_hi | 47 Ω | GPIO12 (pin 32) |
| N_hi | wire | AIN4 |
| N_hi | 10 MΩ | node A |
| AIN0 | 1 kΩ | node A |
| AIN8 | 1 kΩ | node A |
| GPIO26 (pin 37) | 470 Ω | node A |
| node A | 22 Ω | probe A (red) |
| node A | 1N4148 (anode at A) | +5 V |
| GND | 1N4148 (anode at GND) | node A |
| AIN1 | 1 kΩ | node B |
| AIN9 | 1 kΩ | node B |
| GPIO27 (pin 13) | 470 Ω | node B |
| node B | 22 Ω | probe B (black) |
| node B, GND | 1N4148 each, as for A | +5 V, GND |
| AINCOM | wire | GND |

Keep N_hi, the 10 MΩ and node A short and away from the GPIO wires: at the
high range they carry nanoamps.

### Check against your HAT

- **Pins the HAT uses.** Waveshare's demo code uses SPI0 (GPIO 9, 10, 11),
  **CS = GPIO22, DRDY = GPIO17, RESET = GPIO18**. The GPIOs above avoid those
  and the I2C/UART pins. If your HAT's wiki or silkscreen says otherwise,
  change `PIN_RST`, `PIN_CS` and `PIN_DRDY` at the top of
  `tools/probe_ads1263.py`.
- **Supply jumper.** The ADS1263 needs AVDD = 5 V. Keep the HAT's supply
  jumper on 5 V and its reference on the internal 2.5 V (the defaults).
- **AINCOM to GND.** Wire it if your HAT does not already.
- **Reaching the GPIOs.** The HAT covers the header. Use a stacking header,
  or solder the eight GPIO wires and a ground to the Pi's header pins from
  below.

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
   node should read 120-200 mV.
2. `cal zero` with the probe tips pressed together: stores the lead
   resistance (about 44 Ω: two 22 Ω resistors plus the leads) in
   `~/.config/thlhats/probe-cal.json`.
3. `cal open` with the probes apart: stores the leads' own capacitance.
4. `stream` and touch known parts:
   - 10 Ω, 1 kΩ, 100 kΩ and 1 MΩ resistors should read within a few %.
   - 1 nF, 100 nF and 10 µF capacitors should read within about 10 %.
   - A 1N4148 should give D+ about 0.6 V and D- inf (or the reverse, with
     the probes swapped).
   - With the probes open, every reading should be inf or "-".
5. Then run `tptest.py run --golden --meter ads1263` on two or three good
   boards.

## What it measures, and its limits

| Reading | Range | Notes |
|---|---|---|
| R | about 0.1 Ω to 50 MΩ, at ≤ 0.2 V | lowest range that carries a usable current. A net that is only capacitive (no DC path) reads inf. |
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
