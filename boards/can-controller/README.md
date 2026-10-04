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
| MCU, USB | PIC32MK1024GPK064, USB connector (**TBD**) | logic |
| CAN x2 (FD) | ISO1042BQDWVRQ1, termination jumpers, 4-pin terminals (CANH, CANL, GND, +12 V) | crosses logic / 12 V |
| 12 V input | Keyed terminal, reverse polarity, TVS, eFuse; per-bus fuse; buck to 5 V for ISO1042 bus sides | 12 V |
| GPIO x8 | MCP23017 (PIC32 I2C), series R + clamp per pin, ground terminal per pin | logic |
| Relay drive x8 | ULN2803A via isolated drivers, coils from 12 V | 12 V |
| Analog out x2 | MCP4912 or PIC32 CDAC, MC34072 (gain about 3), boost to about 15 V, ground terminal per output | logic |
| Analog in x4 | MCP3428, 10 MΩ / 180 kΩ dividers, 0.1 µF, ground terminal per input | logic |

## Layout rules

- Connectors on the bottom and both side edges only; the header edge stays clear.
- Split copper between the logic and 12 V domains; only the isolators cross.

## Directories

- `hardware/` KiCad project
- `firmware/` firmware sources
