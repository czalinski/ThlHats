# PIC32MK + power module (POC #1)

Plug-in module for the proof-of-concept boards (docs/requirements.md 4.0): the
can-controller's MCU and power entry, hand-soldered once and moved between POC
boards.

- Board: 56 x 74 mm, 2 layers, rev A. No mounting holes (`board.json`).
- U1 PIC32MK1024MCM064-I/PT (TQFP-64), 12 MHz crystal, decoupling, AVDD bead,
  MCLR network, ICSP (J2, PICkit/Snap pinout), debug UART (J5), heartbeat LED
  on RD8. Crystal Y1: Abracon ABM3-12.000MHZ-B2-T (12 MHz, 5.0 x 3.2 mm,
  CL 18 pF, ESR 60 ohm max, -20 to 70 C) with 27 pF C0G load caps; same part
  for the final board.
- Power entry copied from can-controller: J20 12 V in, F20 4 A, reverse-polarity
  P-FET Q1, TVS D31, TRACO TDN 5-2411WI (U20, isolated, 5 V 1 A), MCP1826S 3.3 V
  LDO (U2, 1 A).
- Two domains: RACK (+12V, GND_RACK) on the top strip, LOGIC (+5V, +3V3, GND,
  floating) below. U20 is the only crossing; a 2 mm copper-free gap separates
  them on both layers.

## Host interface

J3/J4 are 2 x 20, 2.54 mm sockets on the module's **bottom** (Sullins
PPTC202LFBN-RC, or any 2.54 mm stock); the host carries pin headers (Sullins
PRPC020DAAN-RC, or cut breakaway strip), via
the library part `Thl_Module:PIC32MK_Module` / footprint
`Thl_Module:PIC32MK_Module_Host` (origin = module top-left corner).

Keying:
1. J4 is placed so that a module turned 180 degrees lands 1.24 mm (half a pitch)
   off the host pins.
2. J3.9 is blocked on the module (glue a cut-off pin into that socket
   position); the host has no pin there. J3.10 is unused on both sides: it
   spaces the RACK pins from the LOGIC pins.

Pull pins 9 and 10 (row 5 of header A) out of the host's header before
soldering it; the host footprint has no pads there.

The pinout is generated: `hardware/module_pinout.py` matches the MCU pins to
header positions clockwise around the chip, so the module's fan-out has no
crossings. Host pin names are the PIC port names; a suffix says what the
module itself hangs on that pin:

- `RB5_PGD`, `RB6_PGC`: ICSP (J2). Keep host loads off them, or isolate them
  while programming.
- `RF1_TX`, `RC6_RX`: debug UART J5 (U1TX/U1RX by PPS).
- `RD8_LED`: heartbeat LED D2 (1 k to GND through the LED).
- `MCLR`: 10 k pull-up and 100 nF on the module; a host may add a reset button.
- `USB_DP`, `USB_DN`, `VBUS`: 100 k pull-downs on the module (USB unused unless
  a host wires a connector).

Supplies on the header: +12V x4 and GND_RACK x4 (J3.1-8, RACK, after the
input protection; a host may feed +12V here instead of using J20, without
protection), +5V x3, +3V3 x5, GND x11 (LOGIC). +5V is limited by U20 (1 A
total, of which the module uses about 0.1 A); +3V3 by U2 (1 A, mind the LDO's
dissipation: (5 - 3.3) V x I).

| J3 odd | J3 even | | J4 odd | J4 even |
|---|---|---|---|---|
| 1 +12V | 2 +12V | | 1 +5V | 2 GND |
| 3 +12V | 4 +12V | | 3 RG9 | 4 MCLR |
| 5 GND_RACK | 6 GND_RACK | | 5 RG8 | 6 RG7 |
| 7 GND_RACK | 8 GND_RACK | | 7 RG6 | 8 RB15 |
| 9 (key: no pin) | 10 (no pin) | | 9 +3V3 | 10 GND |
| 11 GND | 12 GND | | 11 RB14 | 12 RA7 |
| 13 RA12 | 14 RA11 | | 13 RA10 | 14 RB13 |
| 15 RA0 | 16 RA1 | | 15 RB12 | 16 RB11 |
| 17 RB0 | 18 RB1 | | 17 RB10 | 18 RF1_TX |
| 19 +3V3 | 20 GND | | 19 +3V3 | 20 GND |
| 21 RB2 | 22 RB3 | | 21 RF0 | 22 RC9 |
| 23 RC0 | 24 RC1 | | 23 RD6 | 24 RD5 |
| 25 RC2 | 26 RC11 | | 25 RC8 | 26 RC7 |
| 27 +5V | 28 GND | | 27 RC6_RX | 28 RB9 |
| 29 RE12 | 30 RE13 | | 29 +5V | 30 GND |
| 31 RE14 | 32 RE15 | | 31 RB8 | 32 RC13 |
| 33 RA8 | 34 RB4 | | 33 RB7 | 34 RC10 |
| 35 +3V3 | 36 GND | | 35 RB6_PGC | 36 RB5_PGD |
| 37 RA4 | 38 USB_DP | | 37 RD8_LED | 38 VBUS |
| 39 USB_DN | 40 GND | | 39 +3V3 | 40 GND |

## Changing the pinout

Edit `hardware/module_pinout.py`, then regenerate the module
(`gen_schematic.py`, `tools/sync_pcb.py`, `place.py`, reroute) and the host
part (`python3 lib/footprint_src/Thl_Module/pic_module.py` and
`tools/make_symbol.py lib/symbol_src/Thl_Module/PIC32MK_Module.csv`), and
update every host board.

## Build files

- `hardware/gen_schematic.py`: schematic (bootstrap; stop using it once the
  schematic is edited in KiCad).
- `hardware/place.py`: outline, placement, pours (GND both layers in LOGIC,
  GND_RACK / +12V in RACK, a +3V3 island under U1), isolation gap keep-outs
  (rerunnable; leaves tracks alone).
- `hardware/route.py`: pre-routing (not rerunnable): U1 VDD pins get inward
  stubs into the +3V3 island, VSS pins inward vias to the GND plane, every
  other SMD ground pad a fanout via.
- Autorouting: `tools/freeroute.py` (Freerouting 1.9.0 under xvfb, top layer
  preferred, bottom = GND plane), command in `route.py`'s docstring.
- Rev A was then finished by hand (2026-10-06): `miniroute.complete_net` for
  the last few nets, AVDD (U1.19) escaped inward to a via, RC11 kept on top
  past J3, `miniroute.stitch_pads` for header GND pins cut off from the pour,
  `tools/silk_tidy.py` for the references. Rerunning `place.py` is safe;
  rerunning `route.py`/the autorouter starts over and loses those fixes.
- U20 (TRACO: no traces under the converter) is enforced by a rule in
  `pic-module.kicad_dru`: only its own nets under its courtyard.
- Board setup accepts one thermal spoke (`min_resolved_spokes` 1): header GND
  pins between fan-out tracks often get only one.

## Open items

- Verify the Sullins socket/header MPNs (or use stock 2.54 mm parts) and the
  mated height against parts under the module on the host.
- No STEP models for U20 (TRACO TDN 5WI) and F20 (NANO2 fuse).
