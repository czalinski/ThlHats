# CAN Controller

Primary controller for the ThlHats HASS stack: two isolated CAN FD buses plus
local GPIO, relay drive, analog in and analog out. Requirements:
[`docs/requirements.md`](../../docs/requirements.md), section 4.1.

- Board: 100 x 100 mm, 2 layers, rev A
- Mounting: 4x M2.5 on the Raspberry Pi 58 x 49 mm pattern
- Pi header: Samtec REF-182665 pass-through socket on top (stacks with MCC HATs).
  Uses no header signal pins; draws logic power from header 5 V.
- MCU: PIC32MK1024MCM064-I/PT
- Host link: USB (gs_usb for CAN, plus a control interface)

## Functional blocks

| Block | Baseline parts | Domain |
|-------|----------------|--------|
| MCU, USB | PIC32MK1024MCM064, USB-C receptacle (USB 2.0 FS device) | logic |
| CAN x4 (FD) | ISO1044BD, termination jumpers, 4-pin terminals (CANH, CANL, GND, +12 V) | crosses logic / 12 V |
| 12 V input | Keyed terminal, reverse polarity, TVS, eFuse; per-bus fuse; buck to 5 V for ISO1042 bus sides | 12 V |
| 12 V status | Optocoupler from the 12 V rail to an MCU input (reports CAN bus power present) | crosses 12 V / logic |
| GPIO x8 | PIC32 pins directly, series R + clamp per pin (survives a 24 V short), ground terminal per pin | logic |
| Relay drive x8 | ULN2803A driven through two 4-channel digital isolators (e.g. ISO6741), coils from 12 V only | 12 V |
| Analog out x2 | MCP4922 + 2.5 V reference, LM358B (gain 4), 13 V boost from header 5 V, ground terminal per output | logic |
| Analog in x4 | MCP3428, 10 MΩ / 180 kΩ dividers, 0.1 µF, ground terminal per input | logic |

## Floorplan (rev 2, variant B, 2026-10-05)

Drawn on the `Dwgs.User` layer of the PCB. Board corner at (100, 100) mm. The
board sits at the **top of the stack** (MCC HATs below), so top-entry
connectors and the area inside the HAT outline stay reachable.

| Edge | Connector (top/left first) | Length | Domain |
|------|---------------------------|--------|--------|
| Right | USB-C, GCT USB4085 (through-hole, USB 2.0) | 10 mm | logic |
| Right | CAN4, CAN3, CAN1, CAN2: Phoenix MC 1,5/4-G-3,5 (as can-ssr) | 4 x 17 mm | 12 V |
| Bottom | ANALOG: AI1-4 + 4 GND, AO1-2 + 2 GND, MC 1,5/12-G-3,5 | 45 mm | logic |
| Bottom | RELAY 1-8 + 12 V COM, MC 1,5/9-G-3,5 | 34 mm | 12 V |
| Left (below MH3) | GPIO 1-4 + 4 GND, MC 1,5/8-G-3,5 | 31 mm | logic |
| Left (MH1-MH3) | GPIO 5-8 + 4 GND, MC 1,5/8-G-3,5 | 31 mm | logic |
| Inboard | 12 V IN, top entry, Phoenix MSTBVA 2,5/2-G-5,08 | | 12 V |

- Mounting: the four Pi holes (MH1-MH4), plus M2.5 holes in the other three
  corners (MH5-MH7, a 93 x 93 mm square with MH1) for standoffs when the board
  is mounted on its own, e.g. on a second stack fed by a ribbon cable. Two DIN
  rail clip patterns (MK1, MK2: three 4.06 mm holes, 12.45 mm pitch) at
  x = 125 and 175 mm, mid-height, as on the first can-ssr layout; the clip sits
  underneath, screw heads need an 8 mm keep-out on top.
- One connector family (Phoenix MC 3.5) for all signals; the 12 V input uses a
  5.08 mm MSTB so it cannot take a signal plug. Pin counts differ by function
  (CAN 4, GPIO 8, relay 9, analog 12). A smaller plug can still go into a larger
  header, so every pin is designed to survive what a wrong plug could put on
  it: CAN cable 12 V on GPIO (24 V rated) and AO (protected), CAN lines into
  the ULN2803A outputs (harmless).
- 12 V domain: a strip x > 170 mm under the USB-C (the four CAN channels) plus
  the bottom-right block (relay drive, 12 V input, protection, buck). The
  ISO1044s straddle x = 170 between the DIN screw keep-outs; the ISO6740s and
  the 12 V-status opto straddle the block's left and top edges.
- The MCU sits top centre-right, close to USB-C and the CAN isolators.

### Density estimate (courtyard area of the planned parts)

| | Parts | Area left after edge connectors, Pi header, holes | Coverage |
|---|---|---|---|
| 2 CAN | ~3,070 mm2 | ~7,240 mm2 | ~42 % |
| 4 CAN (chosen) | ~3,580 mm2 | ~6,880 mm2 | ~52 % (less with ISO1044) |
| can-ssr logic area, for reference | | 4,200 mm2 | 78 % top + 7 % bottom |

## Parts (draft, 2026-10-05)

Library status: **stock** = in KiCad's stock libraries (import with
`tools/kilib.py`), **make** = symbol or footprint to build/import.

| Function | Part | Package | Library | Notes |
|---|---|---|---|---|
| MCU | PIC32MK1024MCM064-I/PT | TQFP-64 0.5 mm | in lib/ | 4 x CAN FD, USB FS |
| Crystal | 12 MHz, CL 18 pF | 5032 SMD | stock | POSC HS 4-32 MHz; USB clock from the UPLL |
| 3.3 V | MCP1826S-3302E/DB | SOT-223 | stock | from header 5 V |
| USB-C | GCT USB4085-GF-A | THT | stock fp, generic symbol | 5.1k CC pull-downs, VBUS sensed only |
| USB ESD | USBLC6-2SC6 | SOT-23-6 | stock | |
| CAN transceiver x4 | **ISO1044BD** (decided 2026-10-05) | SOIC-8 | stock | CAN FD 5 Mbit/s, 3 kVrms basic isolation |
| CAN TVS x4 | NUP2105L | SOT-23 | stock | as can-ssr |
| CAN termination x4 | 120R 1206 + 2-pin jumper | | stock | |
| CAN bus supply | resettable fuse, 1812, hold ~1.1 A | 1812 | stock fp | footprint on all four buses; **fitted on CAN1 only** (the can-ssr bus). CAN2-4 (DUT buses) are DNP, so pin 4 is dead unless a fuse is fitted (decided 2026-10-05) |
| Relay isolators x2 | **ISO6740** (4 forward channels; ISO6741 is 3+1) | SOIC-16W | stock | 12 V side from the 5 V buck |
| Relay driver | ULN2803A | SOIC-18W | stock | |
| 12 V input | MSTBVA 2,5/2-G-5,08, NANO2 4 A fuse, SUD50P04-08 P-FET (reverse polarity), SMBJ15A TVS | | stock | |
| 12 V to 5 V | RECOM R-78E5.0-0.5 | SIP-3 | in lib/ | ISO1044/ISO6740 bus sides |
| 12 V status | TLP293 | SO-4 | stock | LED on the logic side |
| GPIO series R x8 | 4.7k 1206 (decided 2026-10-05, not a network) | 1206 | stock | GPIO is split over two connectors 30 mm apart; each resistor sits at its connector pin, next to its clamp |
| GPIO clamps x8 | BAT54S to 3.3 V / GND | SOT-23 | stock | 24 V short: ~4.5 mA per pin |
| AI ADC | MCP3428-E/SL | SOIC-14 | stock | not on the Pi's I2C |
| AI dividers | 10M + 130k 1206 to VMID (1.65 V), 0.1 uF, BAT54S clamp | 1206 | stock | MCP3428 cannot go below VSS, so the dividers sit on VMID and CHn- = VMID |
| AO DAC | MCP4922-E/SL (12-bit dual) + MCP1501-25 or LM4040 2.5 V | SOIC-14, SOT-23 | stock | precision reference |
| AO amp | **LM358B** (decided 2026-10-05) | SOIC-8 | stock | gain 4: 0-10 V |
| AO supply | MT3608 or TPS61040 boost to **13 V** from header 5 V | SOT-23-6/-5 | stock | LM358B swings to ~11.5 V |
| Connectors | MC 1,5/4, /8, /9, /12-G-3,5; MSTBVA 2,5/2-G-5,08 | THT | stock | |
| LEDs | 1206 | | stock | power, heartbeat, USB, CAN x4, relay x8, 12 V |

## Schematic (generated 2026-10-05)

`hardware/gen_schematic.py` wrote the root sheet and seven block sheets (MCU/USB/power,
CAN x4, 12 V input, relay drive, GPIO, analog in, analog out). Like can-ssr's
generator, it is for the first capture only: once the schematic is edited in
KiCad, stop running it. ERC: 0 violations; schematic parity clean; every net has
at least two pins; only the isolators (U10-U13, U21, U30, U31) have pins in both
domains. Footprints are parked to the right of the board for placement.

MCU pin map (PPS groups checked against DS60001519E Tables 13-1/13-2): GPIO1-8 on
the left side, I2C1 RG7/RG8, CAN1 RB4/RA4, CAN2 RE15/RA8, CAN3 RE14/RC0, CAN4
RB5/RC10, relays RC1, RC2, RC11, RE12, RE13, RD8, RB6, RB9, DAC SPI SCK1 RB7 /
SDO1 RC8 / CS RA1, UART1 RC7/RC6, V12_OK RC13, ICSP PGC1/PGD1.

MPNs to confirm before ordering: crystal (12 MHz, 5032, CL 18 pF: TBD);
Phoenix MC 1,5/8, /9, /12-G-3,5 (1844278, 1844281, 1844317 entered from the
series numbering); Littelfuse 1812L110/16DR; Bourns MF-NSMF075-2; TI LM4040A25IDBZR.

## Placement (rev 1, 2026-10-05)

First pass by `hardware/place_board.py` (run once; after hand edits in KiCad, don't rerun).
Changes from floorplan rev 2:

- The 12 V block grew upward: x 148-168, y 146-189 (was y > 166), because the
  input stage, bus 5 V module and relay drive did not fit. CAN1/CAN2 isolators
  (U10, U11) now straddle its top edge at y = 146; CAN3/CAN4 (U12, U13) straddle
  x = 168. The 12 V status opto U21 straddles the block's left edge.
- MH4 (Pi standoff) is inside the 12 V block. The hole has no copper; keep 12 V
  copper clear of the standoff (it sits at Pi ground).
- DIN clip screw heads keep 8 mm circles clear on top (footprint courtyard).
- USB4085: footprint-scoped DRC rules for its 0.15 mm pad gap and 0.45 mm drill
  spacing; confirm the drill spacing with PCBWay.

DRC: clean apart from unrouted nets and silkscreen (references not placed yet).

## Layout rules

- Connectors on the bottom and both side edges only; the header edge stays clear.
- Split copper between the logic and 12 V domains; only the isolators cross.

## Directories

- `hardware/` KiCad project
- `firmware/` firmware sources
