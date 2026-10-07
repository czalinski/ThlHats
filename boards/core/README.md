# Core: PIC32MK, 12 V power, Ethernet

Top board of the daughter-card stack (docs/requirements.md 4.0, 4.5).

- Board: 100 x 100 mm, 2 layers, rev A. 4 x M4 stack holes on a 91 x 91 mm
  square (`board.json` opts out of the Pi holes). No Pi header.
- U1 PIC32MK1024MCM064-I/PT, 12 MHz Abracon ABM3-12.000MHZ-B2-T, ICSP J2 and
  debug UART1 J5 (right-angle, top edge), heartbeat LED, VMID reference for
  the io-card.
- Power: J20 12 V in (side-entry MSTBA, right edge), F20, reverse-polarity
  Q1, TVS D31, TRACO TDN 5-2411WI (U20, the only RACK | LOGIC crossing),
  MCP1826S 3.3 V LDO.
- Ethernet: W6100 (U3) + Pulse JD0-0004NL RJ45 (bottom edge). 25 MHz crystal
  MPN still TBD.
- Stack: J10 2 x 20 logic bus and J11 2 x 3 rack power, **pin headers on the
  underside** (the core sits on top of the cards). Pinout and positions in
  `tools/stack_bus.py`; underside mounting swaps the pad columns
  (`stack_bus.underside`).

## Build files

- `hardware/gen_schematic.py`: schematic (bootstrap; stop using it once the
  schematic is edited in KiCad).
- `hardware/place.py`: outline, holes, placement, pours, +3V3 island under U1
  and 1V2D island under U3, RACK gap (rerunnable; leaves tracks alone).
- `hardware/route.py pre|auto|finish|all`: routing pipeline. **Do not rerun
  `pre` or `all` on the routed board**: they start over and erase hand routing.

## Status (2026-10-07)

Routed except for 5 connections, to finish by hand in KiCad:

- GND: U1 pins 20 and 25 (left side, beside the AVDD escape and a VDD stub).
- GND: U1 pin 9 (its via under the chip is pocketed on B.Cu).
- /Ethernet/TXP: U3.3 to R17 / J4.1 (route with TXN, short and parallel).
- SCL: U1.5 to the SCL track toward R7.
- /Ethernet/LNKn: U3.17 to J4.11 (B.Cu under the jack body is free).

Plus DRC: two +3V3 vias 0.48 mm apart near (145.7, 154.0) canvas, and a
narrow neck in the B.Cu GND pour. Silkscreen not tidied yet
(`tools/silk_tidy.py`).
