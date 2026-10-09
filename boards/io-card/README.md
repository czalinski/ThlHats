# IO card: relays, GPIO, differential AI

The "LabJack light" daughter card in the core's stack (docs/requirements.md
4.1 and 4.5). It has no MCU: the core's PIC32MK drives RLY1-4 and GPIO1-4 and
reads the analog legs on its ADC through the stack bus.

- Board: 100 x 100 mm, 2 layers, rev A.
- Mounting: 4x M4 stack holes (tools/stack_bus.py), no Pi header
  (`board.json` opts out).
- Stack: J10 logic bus (left edge) and J11 rack power (right edge), Samtec
  ESQ stacking sockets on top, as on the can-card. Every part stays under the
  next card, about 11 mm up (ESQ-120-14 body).

| Block | Circuit | Terminal |
|---|---|---|
| Relay drivers 1-4 | Drive **external** relay coils. 2 × Panasonic AQW212 PhotoMOS. The LED side runs on LOGIC: RLYn → 470R → LED. The contacts source V_RLY to OUTn, and the coil returns to 0 V next to it. Coil supply on JP1: 1-2 = rack +12 V (J11), 2-3 = external supply up to 24 V on J30 9/10. Both go through F30 (1.1 A, 33 V). Each output has a 1N4148W flyback diode and a red LED. | **J30** bottom edge, MC 1,5/10-G-3,5: 1/2 OUT1 / 0 V … 7/8 OUT4 / 0 V, 9/10 external coil supply + / 0 V |
| GPIO 1-4 | 3.3 V straight from core pins, with 330R in series and a BAT54S clamp. Not 24 V tolerant. | **J40** top edge, MC 1,5/12-G-3,5: 1/2 IO1 / GND … 7/8 IO4 / GND |
| AI 1-2 | Differential, ±116 V per input, 10 MΩ per input. Each leg is 10M / 130k to VMID, with 100 nF across the 130k and a BAT54S clamp. The core subtracts the two legs. | J40 9/10 AI1+ / AI1-, 11/12 AI2+ / AI2- |

Plugs: Phoenix FMC 1,5/10-ST-3,5 and FMC 1,5/12-ST-3,5 (push-in, 7.8 mm).
The MC headers are 7.7 mm tall. The double-level SPTD terminals from the
first schematic are 24.2 mm tall and do not fit in the stack.

## Layout

- LOGIC: the top band (J40, GPIO clamps, AI dividers) and the left side
  (J10, decoupling, relay LED resistors).
- RACK: the lower-right block (J11, JP1, F30, C70/C71, flyback diodes, LEDs,
  J30).
- K1/K2 straddle a 2 mm copper-free gap on both layers. They are the only
  LOGIC | RACK crossing (1500 Vrms, functional isolation).
- Ground pours on both layers in each domain.
- The AI terminal nets (`/AIN*`) are in net class HV, with a 0.8 mm
  clearance (IPC-2221B B4 needs 0.6 mm for 101-150 V).

## Build files

- `hardware/gen_schematic.py`: generates the schematic. Stop using it once
  the schematic is edited in KiCad.
- `hardware/place.py`: outline, holes, placement, pours and the isolation
  gap. It can be rerun and leaves tracks alone.
- `hardware/route.py pre|auto|finish|all`: ground fan-out, Freerouting, then
  finishing. **Do not rerun `pre` or `all` on a hand-edited board**: they
  start over.

## Status (2026-10-09)

Placed and routed. `tools/check_board.py` is clean: ERC, DRC and schematic
parity, with no warnings. References were tidied with `tools/silk_tidy.py`.
Next: io-card commands in the core firmware (RLY, GPIO, AI, and OA5 for
VMID).

Open items:

- Confirm the mated FMC plug height against the stack on the Phoenix
  drawing.
- There is no reverse-polarity protection on the external coil supply. If
  it is reversed, an output that is on lets its flyback diode short the
  supply through F30, which trips. Outputs that are off should block it,
  provided the AQW212 output is AC/DC type (back-to-back MOSFETs). Check
  that on the datasheet.
