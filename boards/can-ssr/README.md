# CAN SSR

Remote CAN FD node that turns a Mean Well adjustable supply into a simple
automatable DUT supply: high-side switch with reverse blocking, V and I
readback, remote voltage/current programming, auto-off on lost heartbeat.
Requirements: [`docs/requirements.md`](../../docs/requirements.md), sections
4.2, 4.2.1 (builds and switching) and 4.2.2 (block diagram).

- Board: 100 x 100 mm, 2 layers, rev A (smaller welcome, not required)
- Mounting: 4x M2.5 on the Raspberry Pi 58 x 49 mm pattern **and** two DIN rail
  clip patterns (MK1, MK2; positions provisional until layout)
- Off the Pi header; powered from the 4-wire CAN cable (12 V)
- MCU: PIC18F-Q84 family (CAN FD), on the CAN/logic side

## Builds (one PCB, one firmware image)

| Build | MOSFETs (4 x D2PAK) | Max supply | Continuous |
|-------|---------------------|------------|------------|
| HC  | IPB021N10NM5LF2 | 60 V  | 50 A |
| STD | IPB110N20N3LF   | 150 V | 25 A |
| HV  | IPB407N30N      | 200 V | 12 A (sequenced turn-on only) |

The only other difference is the **build resistor**, which sets the hardware
overcurrent trip threshold and is read by the PIC as the build ID.

## Functional blocks

| Block | Baseline parts | Domain |
|-------|----------------|--------|
| CAN, power, MCU | CAN FD transceiver, 12 V to 5 V buck, PIC18F-Q84, address switch, termination jumper | CAN/logic |
| Display | MAX7219, 4-digit 7-segment LED, V/A indicators | CAN/logic |
| Overcurrent trip | Comparator + latch on the ACS770 output, threshold from the build resistor | CAN/logic |
| Barrier | 2 x VOM1271T, ACS770ECB-100U, ISO1640 I2C isolator, isolated DC-DC, photorelay | crosses |
| Power path | 4 x MOSFET (two per side, common source), gate network with slew C, freewheel diode, busbars, 4 bolts | load |
| Sense and programming | Vin/Vout dividers, MCP3428 ADC, 2 x MCP4725 DAC (Mean Well PV, PC) | load |

## Layout rules

- Busbar runs are mask-free top copper; four bolted ring-lug connections
  (supply +/-, load +/-).
- 250 V working clearances; about 6 mm creepage between the load side and the
  CAN/logic side. No copper pour joins the domains.

## Directories

- `hardware/` KiCad project
- `firmware/` firmware sources
