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
  Y2 Abracon ABM3-25.000MHZ-D2Y-T (CL 18 pF, ±20 ppm, ESR 30 R) with 27 pF
  load caps C30/C31, the same as Y1's. A catalogue 5032 two-pad part with the
  W6100's typical 12 pF was not found. Gain margin is fine (gm 16.7 mA/V
  against about 1.9 mA/V critical). The estimated drive level is about
  80 uW against the ABM3's 100 uW max, so measure it on the first board.
  The fallback is NDK NX5032GA-25.000M LN-CD-1 (CL 8 pF, 500 uW, ±50 ppm)
  with about 8 pF caps.
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

Fully routed (last five connections by hand in KiCad), `tools/check_board.py`
clean: ERC, DRC and schematic parity without errors. Remaining warnings:

- no STEP models for U20 (TRACO TDN 5WI), F20 (NANO2) and J4 (Pulse
  JD0-0004NL: IGES only);
- silkscreen clipped by the board edge: J2/J5 (right-angle headers) and J20
  overhang the edge on purpose.

Clean-up after the hand routing: two +3V3 vias 0.48 mm apart merged, a
dangling +5V stub removed, a B.Cu GND sliver between J10 pins suppressed
(rule area GAP_SLIVER_J10 in place.py), mounting holes re-linked to
Thl_Mechanical, references tidied (`tools/silk_tidy.py`; 12 small parts keep
their reference on the Fab layer only, U1/U3/Y2 labelled on the body).

Parts chosen 2026-10-09: Y2 ABM3-25.000MHZ-D2Y-T, C30/C31 27 pF C0G
(GRM2165C1H270JA01D), C29 3.3 uF 25 V X7R 1206 (Samsung CL31B335KAHVPNE).

Open before ordering: mated stack height check against the cards.

Firmware: `firmware/` (bring-up console, can-card detection, CAN FD).
