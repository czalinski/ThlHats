# Serial card: 2 × RS-232, 2 × isolated RS-485

Daughter card in the core's stack (docs/requirements.md 4.5). It has no MCU:
the core's PIC32MK UART2-5 drive the ports through the stack bus, bridged to
TCP 5001-5004 (boards/core/firmware/PROTOCOL.md, `SER` command).

- Board: 100 x 100 mm, 2 layers, rev A.
- Mounting: 4x M4 stack holes (tools/stack_bus.py), no Pi header
  (`board.json` opts out).
- Stack: J10 logic bus and J11 rack power (pass-through only), Samtec ESQ
  stacking sockets on top.

| Port | UART | Interface | Header |
|---|---|---|---|
| 1 | U2 | RS-232 through ST3232B (U1), 3.3 V, not isolated | J20 |
| 2 | U3 | RS-232 through ST3232B (U1) | J21 |
| 3 | U4 + DE1 | RS-485 half duplex, TI ISOW1432 (U10), isolated with integrated DC-DC | J30 |
| 4 | U5 + DE2 | RS-485 half duplex, TI ISOW1432 (U11), isolated | J31 |

## Decisions (2026-10-09)

- **Connectors.** Right-angle shrouded 2x5 box headers (Amphenol
  T821110A1R100CEU). A DB9 (about 12.5 mm) does not fit under the next card
  (about 11 mm). The headers follow the common IDC10-to-DB9 order (header
  pin n → DB9 1, 6, 2, 7, 3, 8, 4, 9, 5), so either a standard IDC ribbon
  DB9 cable or a small adapter PCB gives the DB9.
  - RS-232 (male DB9, DTE): header 3 = DB9-2 RXD in, 5 = DB9-3 TXD out,
    9 = DB9-5 GND. Three-wire, with no handshake lines; loop them in the
    cable if a device needs them.
  - RS-485 (female DB9, Profibus convention): header 5 = DB9-3 D+ (TI A/Y),
    6 = DB9-8 D- (TI B/Z), 9 = DB9-5 isolated GND.
- **Isolation on RS-485 only.** RS-232 is short and point to point. Each
  RS-485 bus side floats (GND_485_3, GND_485_4) and gets its power from the
  ISOW1432's own converter (5 V mode: VDD from +5V, MODE = VISOOUT).
- **Half duplex, no jumpers.** The ISOW1432 is a full-duplex part; Y-A and
  Z-B are tied on the PCB (SLLSF86D 8.1). ~RE is tied to DE, so the port
  does not hear its own transmission. A 10k pull-up holds RX high while the
  receiver is off. ISOW1432 rather than ISOW1412 (same pinout), because it
  runs to 12 Mbps and `SER` allows up to 1 Mbaud.
- **Per RS-485 port:** an SM712 TVS on the bus pins and a 120R termination
  jumper (JP1/JP2, fit only at a bus end). The ISOW receiver is fail-safe,
  so there are no bias resistors.
- **LEDs:** a TX and an RX LED per port on the logic side, lit while the
  line is low.

## Layout notes (for placement)

- ISOW1432: the same supply-pin layout as the can-card's ISOW1044. 10 nF
  within 1 mm of VDD and VISOOUT, symmetric VISOOUT/GND2 rails, beads to
  VISOIN/GISOIN. **No copper within 4 mm of pins 11/12** except their own
  parts (SLLSF86D 9.4.1). Reuse the can-card's place/route approach.
- Each RS-485 bus side is its own pour island, separated from LOGIC by the
  isolation gap under its ISOW1432.
- The right-angle headers sit at the board edges, with plugs entering from
  outside.

## Build files

- `hardware/gen_schematic.py`: generates the schematic. Stop using it once
  the schematic is edited in KiCad.

## Status (2026-10-09)

The schematic is generated. ERC is clean. The stack-bus pins and the port
map have been checked against `tools/stack_bus.py` and the core firmware.
Next: placement and routing, then the DB9 adapter PCB if wanted.

Open items:

- Confirm the T821110A1R100CEU height and its fit with the KiCad
  `IDC-Header_2x05_P2.54mm_Horizontal` footprint against the Amphenol
  drawing.
