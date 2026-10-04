# ThlHats requirements

Status: draft, 2026-10-04. Items marked **TBD** need a decision before
schematic work starts on that board.

## 1. Purpose

ThlHats is a small family of boards for HASS (highly accelerated stress
screening) test racks. A HASS rack needs CAN, serial and a modest amount of
general I/O. Today that means USB dongles, extra wall warts, USB cables, and
DAQ hardware that is either cumbersome (LabJack T7) or expensive and
over-provisioned (NI cards: a whole card for two analog channels).

The goal is to replace that clutter with a Raspberry-Pi-hosted stack that
needs **one host connection and one supply**, and is quick and safe to wire
under a hectic test schedule.

### Goals

- CAN, RS-232, RS-485 and "a handful" of DI, DO, relay drive, AI and AO,
  all reachable from the user's Python test framework.
- Small boards: each board carries few enough connectors to fit on its edges
  (see 4.1). An earlier all-in-one board grew too large for this reason.
- Robust against wiring mistakes, which are common during testing.
- Low cost: 2-layer boards, at most 100 × 100 mm, built by PCBWay.

### Non-goals

- Precision or high-speed measurement. The Digilent/MCC DAQ HATs
  (MCC 118, 128, 134, 152, 172) cover those cases and share the same stack.
- Duplicating functions already available as off-the-shelf HATs.

## 2. System context

- **Hosts:** Raspberry Pi 5 and Orange Pi 6. The user manages device-tree
  overlays in the Python project.
- **Shared header:** boards on the 40-pin header coexist with up to 8 MCC DAQ
  HATs. The reserved and free pins are listed in `CLAUDE.md`, under
  "Raspberry Pi header sharing". In summary:
  - Never use SPI0, BCM 12/13/16/20/21/26, or ID_SD/ID_SC.
  - Never fit a HAT ID EEPROM.
  - I2C1 is shared; keep devices off addresses 0x20–0x27.
- **Mounting:** M2.5 Raspberry Pi standoffs (58 × 49 mm hole pattern).
- **Software:** the Python test framework talks to every board through
  standard Linux interfaces where possible: SocketCAN (`can0`, `can1`, …),
  tty devices, and a common I/O protocol (section 6).

## 3. Boards

### 3.1 Primary controller: `can-controller` (on the header)

| Item | Requirement |
|------|-------------|
| MCU | PIC32MK1024MCF064-I/PT (4× CAN 2.0B, USB FS device, 12-bit ADC, 3× DAC, op amps) |
| Host link | USB to the host. Uses no header signal pins; the header supplies only 5 V/GND and mounting. |
| CAN | 2 channels, each a 4-wire bus: CANH, CANL, GND, bus supply. Switchable 120 Ω termination. |
| CAN bus supply | Feeds remote CAN nodes. Voltage: **TBD** (12 V or 24 V). Source/input connector: **TBD**. Fused/current-limited per channel. |
| Local I/O | A handful of DI, DO, relay drive, AI and AO. Counts: **TBD** (see 4.1). |
| Size | HAT (65 × 56.5 mm) if the connector budget fits, otherwise up to 100 × 100 mm |

Open: whether CAN is isolated (**TBD**); the USB connector type and where it
sits on the board (**TBD**).

### 3.2 Remote CAN node, SSR: `can-ssr` (off the header)

| Item | Requirement |
|------|-------------|
| MCU | PIC18 with on-chip CAN (e.g. PIC18F26K83 CAN 2.0B, or PIC18F26Q84 CAN FD). Part: **TBD** |
| Power | From the 4-wire CAN cable |
| Function | High-side P-MOSFET solid-state switching of DC loads up to **120 V DC** |
| Channels / current | **TBD**. The user has specific MOSFETs in mind. |
| Safety | 120 V DC is above the 60 V DC SELV limit. Needs creepage/clearance between the load and logic sections, a Vgs clamp, MOSFETs rated about 200 V, and probably isolation between the load side and CAN/logic (**TBD**). |
| Connectors | CAN in and CAN out (daisy chain), load terminals rated for the voltage and current |

This board is the first of a possible family of bus-powered CAN nodes
(relay, analog, digital), each with a single function and few connectors.
Whether to build more nodes is a later decision.

### 3.3 Serial expander: `serial-io` (on the header)

| Item | Requirement |
|------|-------------|
| UARTs | 2× SC16IS752 dual UART on shared I2C1, at addresses 0x48 and up. Linux `sc16is7xx` driver gives `/dev/ttySC*`. |
| Ports | 2× RS-232, 2× RS-485. RS-485 direction controlled automatically through RTS. |
| Header pins | I2C1 (pins 3/5) plus 1–2 IRQ GPIOs from the free list. Exact pins: **TBD**, after checking on the Orange Pi 6. |
| RS-485 | Switchable termination and failsafe bias. Half or full duplex: **TBD**. |
| Throughput | Console and Modbus rates. Four ports streaming at 115200 at once exceeds what 400 kHz I2C can carry; this is accepted. |
| Connectors | **TBD** (DB9 for RS-232 versus pluggable terminals) |

## 4. Requirements common to all boards

### 4.1 Connector budget

Connectors sit on board edges, and edge length is the binding size constraint.
Budget each board's connectors before starting the schematic:

- On a 65 mm HAT edge: about 17 positions of 3.5 mm pluggable terminals, or about 12 at 5.08 mm.
- The Pi header occupies one long edge's interior, and the standoffs take the corners.
- At 100 × 100 mm: two to three usable edges of roughly 90 mm each.

### 4.2 Field wiring protection (all external connections)

Wiring mistakes are common under test-schedule pressure, so every
field-facing pin must survive the likely mistakes:

- **Keyed, pluggable connectors** on every external connection, so fixtures
  are swapped by unplugging rather than rewiring. Use different connector
  families or keying for different functions where practical, so a CAN plug
  cannot go into an I/O socket.
- **ESD/TVS protection** on every external pin.
- **Series resistance or PTC** on signal I/O. Inputs must survive a short to
  the highest voltage present on the rack: 24 V (**TBD**: confirm the rack's
  maximum control voltage).
- **Reverse-polarity and overvoltage protection** on every supply input.
- **Current limiting or fusing** on every supply output, including the CAN
  bus supply and any sensor supply.
- **Outputs default to off** at power-up, at reset, and when the host link is
  lost (firmware watchdog with a defined failsafe state).

### 4.3 Usability

- A status LED per channel where practical, plus power and heartbeat/host-link LEDs.
- Clear silkscreen: the signal name at every terminal, the board name and revision, and the address/termination setting.
- Configuration (termination, address) by jumper or switch that is visible without disassembly.

### 4.4 I/O signal ranges (TBD)

To be filled in from rack experience:

| Type | Range / level | Notes |
|------|---------------|-------|
| DI | **TBD** (e.g. 3.3–24 V, threshold about 2.5 V) | Dry contact support? |
| DO | **TBD** (open-drain sinking, 24 V / 100 mA?) | |
| Relay drive | **TBD** (coil voltage, flyback on board) | |
| AI | **TBD** (0–10 V? ±10 V? 4–20 mA?) | Low accuracy OK; protect to 24 V |
| AO | **TBD** (0–5 V or 0–10 V, mA drive) | Short-circuit tolerant |

### 4.5 Part selection

- Boards are mostly hand assembled; larger parts beat cost and density.
- Chip R/C: 1206 where possible; decoupling capacitors 0805; nothing smaller.
- Ceramic capacitors: X5R/X7R or better (C0G/NP0); never Y5V/Y5U/Z5U.
- Prefer SOIC/SOT/TQFP over leadless packages where there is a choice.

## 5. Mechanical and manufacturing

- 2 layers, at most 100 × 100 mm, rounded corners, M2.5 holes on the Pi 58 × 49 mm pattern.
- Header boards: 2×20 socket on the bottom side, at HAT position. Must stack with MCC HATs; check component height against the stacking header.
- PCBWay standard service. House rules are in `tools/house_rules.py`.
- Every part carries `Manufacturer` and `MPN` fields (BOM for ordering, and for PCBWay assembly when used).

## 6. Firmware and host software

- One **host protocol** shared by all boards, defined before the controller
  firmware: discovery and identification (board type, revision, serial
  number), I/O read/write, configuration, and the watchdog. **TBD**.
- Controller over USB: a composite device presenting the two CAN channels so
  the host gets SocketCAN (e.g. two CDC-ACM channels running slcan, brought up
  by `slcand`), plus a control channel for local I/O.
- Remote CAN nodes: an application protocol on CAN for I/O and configuration,
  with a heartbeat. **TBD**.
- Each board's firmware lives in `boards/<name>/firmware/`.
