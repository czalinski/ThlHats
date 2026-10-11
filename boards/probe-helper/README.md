# Probe helper: ADS1263 HAT adapter

Resistor/clamp board for the probe meter: Raspberry Pi + Waveshare
High-Precision AD HAT (TI ADS1263), run by `tools/probe_ads1263.py`.
Circuit, parts, assembly and bring-up: `docs/probe-helper-pi.md`.

- Board: 65 x 46 mm, 2 layers, rev A, all through-hole (hand assembly)
- J1: 13 right-angle pins at 3.5 mm on the **bottom** side, into the HAT's
  13-way screw terminal (AVDD ... COM)
- J2: 2x5 box header, ribbon to the HAT's pass-through Pi pins 31-40
- J3: probe leads A (red) and B (black)
- Mounting (`board.json`: not on the HAT pattern): tabs MH1/MH2 over the HAT's
  terminal-side holes (about 4 mm spacers), MH3/MH4 on the Pi's far holes
  (Pi y 52.5). The board sits above the HAT.

## Layout

- `hardware/gen_schematic.py` schematic generator (bootstrap)
- `hardware/place.py` outline, holes, placement, pours, silkscreen (rerunnable)
- routing: `tools/freeroute.py boards/probe-helper --skip GND`
- `firmware/`: none; the Pi runs `tools/probe_ads1263.py`
