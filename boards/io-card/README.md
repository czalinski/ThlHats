# IO card: relays, GPIO, differential AI

The "LabJack light" daughter card in the core's stack (docs/requirements.md
4.1 and 4.5). It has no MCU: the core's PIC32MK drives RLY1-4 and GPIO1-4 and
reads the analog legs on its ADC through the stack bus.

- Board: 100 x 100 mm, 2 layers, rev A.
- Mounting: 4x M4 stack holes (tools/stack_bus.py), no Pi header
  (`board.json` opts out).
- Stack: J10 logic bus and J11 rack power, Samtec ESQ stacking sockets on
  top, as on the can-card.

| Block | Circuit | Terminal |
|---|---|---|
| Relays 1-4 | 2 × Panasonic AQW212 PhotoMOS. The LED side runs on LOGIC: RLYn → 470R → LED. The contacts source +12 V (J11 → PTC F30 1.1 A) to OUTn. Each output has a 1N4148W flyback diode and a red state LED. | J30 SPTD 4-pole: lower level OUT1-4, upper level 0 V (GND_RACK) |
| GPIO 1-4 | 3.3 V straight from core pins, with 330R in series and a BAT54S clamp. Not 24 V tolerant. | J40 lower 1-4, upper GND |
| AI 1-2 | Differential, ±116 V per input, 10 MΩ per input. Each leg is 10M / 130k to VMID, with 100 nF across the 130k and a BAT54S clamp. The core subtracts the two legs. | J40 lower AI1+/AI2+, upper AI1-/AI2- |

Domains: LOGIC (+3V3 and GND, floating, from the core) and RACK (+12V and
GND_RACK). The two meet only inside K1/K2 (1500 Vrms, functional
isolation). Keep the relay block and J30 in the RACK strip next to J11, at
the right edge.

## Build files

- `hardware/gen_schematic.py`: generates the schematic. Stop using it once
  the schematic is edited in KiCad.

## Status (2026-10-09)

The schematic is generated. ERC is clean, and the stack-bus pins have been
checked against `tools/stack_bus.py`. Next: placement and routing (a
place.py/route.py pipeline as on the can-card), and io-card commands in the
core firmware (RLY, GPIO, AI, with VMID from OA5).

Open items:

- The SPTD terminal footprints have no 3D model.
- The AQW212 MPN and current figures are taken from the requirements
  (checked 2026-10-06).
