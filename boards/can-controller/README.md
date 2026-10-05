# CAN Controller

Primary controller for the ThlHats HASS stack: two isolated CAN FD buses plus
local GPIO, relay drive, analog in and analog out. Requirements:
[`docs/requirements.md`](../../docs/requirements.md), section 4.1.

- Board: 100 x 100 mm, 2 layers, rev A
- Mounting: 4x M2.5 on the Raspberry Pi 58 x 49 mm pattern
- Pi header: Samtec REF-182665 pass-through socket on top (stacks with MCC HATs).
  Uses no header signal pins; draws logic power from header 5 V.
- MCU: PIC32MK1024GPK064-I/PT
- Host link: USB (gs_usb for CAN, plus a control interface)

## Functional blocks

| Block | Baseline parts | Domain |
|-------|----------------|--------|
| MCU, USB | PIC32MK1024GPK064, USB-C receptacle (USB 2.0 FS device) | logic |
| CAN x2 (FD) | ISO1042BQDWVRQ1, termination jumpers, 4-pin terminals (CANH, CANL, GND, +12 V) | crosses logic / 12 V |
| 12 V input | Keyed terminal, reverse polarity, TVS, eFuse; per-bus fuse; buck to 5 V for ISO1042 bus sides | 12 V |
| 12 V status | Optocoupler from the 12 V rail to an MCU input (reports CAN bus power present) | crosses 12 V / logic |
| GPIO x8 | PIC32 pins directly, series R + clamp per pin (survives a 24 V short), ground terminal per pin | logic |
| Relay drive x8 | ULN2803A driven through two 4-channel digital isolators (e.g. ISO6741), coils from 12 V only | 12 V |
| Analog out x2 | MCP4912 or PIC32 CDAC, MC34072 (gain about 3), boost to about 15 V, ground terminal per output | logic |
| Analog in x4 | MCP3428, 10 MΩ / 180 kΩ dividers, 0.1 µF, ground terminal per input | logic |

## Floorplan (draft 2026-10-05)

Drawn on the `Dwgs.User` layer of the PCB. Board corner at (100, 100) mm.

| Edge | Connector (top/left first) | Footprint length | Domain |
|------|---------------------------|------------------|--------|
| Right | USB-C, GCT USB4085 (through-hole, USB 2.0) | 10 mm | logic |
| Right | 12 V IN, Phoenix MSTBA 2,5/2-G-5,08 | 13 mm | 12 V |
| Right | CAN1, CAN2: Phoenix MC 1,5/4-G-3,5 (as can-ssr) | 2 x 17 mm | 12 V |
| Bottom | RELAY 1-8 + 2 x 12 V COM, MC 1,5/10-G-3,5 | 38 mm | 12 V |
| Bottom | ANALOG: AI1-4 + 4 GND, AO1-2 + 2 GND, MC 1,5/12-G-3,5 | 45 mm | logic |
| Left (below MH3) | GPIO 1-4 + 4 GND, MC 1,5/8-G-3,5 | 31 mm | logic |
| Left (MH1-MH3) | GPIO 5-8 + 4 GND, MC 1,5/8-G-3,5 | 31 mm | logic, under the MCC HAT outline |

- One connector family (Phoenix MC 3.5) for all signals, as on can-ssr; the
  12 V input uses a 5.08 mm MSTB so it cannot take a signal plug. Pin counts
  differ by function (CAN 4, GPIO 8, relay 10, analog 12). A smaller plug can
  still go into a larger header, so every pin is designed to survive what a
  wrong plug could put on it: CAN cable 12 V on GPIO (24 V rated) and AO
  (protected), CAN lines into the ULN2803A outputs (harmless).
- 12 V domain: the bottom-right block (x > 150, y > 133). Isolators straddle
  the boundary: 2 x ISO1042 on the top edge, 2 x ISO6741 and the 12 V-status
  opto on the left edge.
- The MCU sits top right, close to USB-C and the ISO1042 logic sides. The
  USB-C on the right edge is right above the Pi's USB-A ports, so the cable is short.
- CAN3/CAN4: no edge room is left in this variant (A, `Dwgs.User`). The spare
  controllers would go to an unpopulated logic-side header for a future add-on.

### Variant B: four CAN channels (`Cmts.User` layer)

- Right edge below the USB-C: CAN4, CAN3, CAN1, CAN2, all MC 3.5 horizontal
  (76 mm of the 94 mm edge). The 12 V input moves inboard to a top-entry
  MSTBV 5.08 header (this board is the top of the stack, so it stays reachable).
- 12 V domain: a strip x > 168 mm under the USB-C plus the bottom-right block.
  The four ISO1042s straddle x = 168 (spaced to clear the MH4 hole); fuse,
  TVS and termination jumper sit between each isolator and its connector.
- Bottom and left edges unchanged. The tight spot is the 12 V input
  protection and buck next to CAN2.

### Density estimate (courtyard area of the planned parts)

| | Parts | Area left after edge connectors, Pi header, holes | Coverage |
|---|---|---|---|
| 2 CAN (A) | ~3,070 mm2 | ~7,240 mm2 | ~42 % |
| 4 CAN (B) | ~3,580 mm2 | ~6,880 mm2 | ~52 % |
| can-ssr logic area, for reference | | 4,200 mm2 | 78 % top + 7 % bottom |

## Layout rules

- Connectors on the bottom and both side edges only; the header edge stays clear.
- Split copper between the logic and 12 V domains; only the isolators cross.

## Directories

- `hardware/` KiCad project
- `firmware/` firmware sources
