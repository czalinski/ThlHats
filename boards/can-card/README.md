# CAN card: 4 isolated CAN FD

Daughter card in the core's stack (docs/requirements.md 4.5).

- Board: 100 x 100 mm, 2 layers, rev A
- Mounting: 4x M4 stack holes (tools/stack_bus.py), no Pi header
- Stack: J10 logic bus (C1-C4 TX/RX, +3V3, +5V, GND), J11 rack power (+12V,
  GND_RACK, only for CAN1 POWERED); Samtec ESQ stacking sockets on top
- Channels: TI ISOW1044 each (integrated isolated DC-DC), every bus ground
  floating; MC 1,5/4 terminals: 1 CANH, 2 CANL, 3 GND, 4 +12 V (CAN1 only)
- Jumpers: JP1-JP4 120 R termination; JP5 + JP6 CAN1 POWERED (ties GND_CAN1
  to GND_RACK, feeds +12 V through F10)
- MCU: none (the core's PIC32MK drives the CAN lines)

## Layout

- `hardware/` KiCad project
  - `gen_schematic.py` bootstrap schematic generator (stop once edited in KiCad)
  - `place.py` outline, holes, placement, domain pours, isolation gaps, TI keep-outs
  - `route.py` routing pipeline (`all` = delete tracks, place, pre, Freerouting, finish)
- `firmware/` none (no MCU on this card)
