# ThlHats

KiCad 10 PCB designs plus their firmware, for small test boards that mount on
Raspberry Pi standoffs (HAT form factor).

## Hard constraints (enforced by `tools/check_board.py`)

- **2 copper layers** only.
- **Board outline ≤ 100 × 100 mm.**
- **4 × M2.5 mounting holes (2.7 mm) on the Raspberry Pi 58 × 49 mm pattern**,
  3.5 mm in from the top-left corner. Default outline is the official HAT size,
  65 × 56.5 mm with 3 mm corner radii.
- **Every symbol, footprint and 3D model comes from `lib/` in this repo**. Never
  reference the stock KiCad libraries (`${KICAD10_*}`) or the user's global lib tables.

## Layout

```
lib/symbols/<Lib>.kicad_sym      symbol libraries
lib/footprints/<Lib>.pretty/     footprint libraries
lib/3dmodels/<Lib>.3dshapes/     STEP models
lib/SOURCES.md                   provenance log for every imported part
boards/<name>/hardware/          KiCad project (<name>.kicad_pro/sch/pcb/dru, lib tables)
boards/<name>/firmware/          firmware for that board
tools/                           Python tooling (needs KiCad's `pcbnew` module: system python3)
```

Libraries copied from stock KiCad keep their stock nickname (`Device`,
`Resistor_SMD`, …) so stock symbols' Footprint fields resolve to the repo copy.
Parts from anywhere else (SnapEDA, Ultra Librarian, vendor, hand-made) go in
`Thl_<Category>` libraries, e.g. `Thl_Sensor`, `Thl_Connector`.

Project lib tables use `${KIPRJMOD}/../../../lib/...`, and footprints point their
3D models to `${KIPRJMOD}/../../../lib/3dmodels/...`, so boards must stay exactly
at `boards/<name>/hardware/`.

## Commands

```sh
tools/new_board.py <name> [--size WxH] [--no-gpio] [--mcu pic|esp32|stm32] [--title T]
tools/kilib.py symbol Lib:Name ...         # stock symbol (+ its default footprint + 3D model)
tools/kilib.py footprint Lib:Name ...      # stock footprint (+ 3D model)
tools/kilib.py library <Lib>               # whole stock symbol library
tools/kilib.py symbol <Name> --from file.kicad_sym --lib Thl_X --source "..." --license "..."
tools/kilib.py footprint <Name> --from file.kicad_mod --lib Thl_X --model file.step --source "..."
tools/kilib.py sync                        # rewrite lib tables in all boards (run after adding a new library)
tools/kilib.py list
tools/check_board.py boards/<name> | --all # house rules + ERC + DRC (with schematic parity)
tools/fab.py boards/<name>                 # gerbers/drill zip, PCBWay BOM + centroid, PDF, STEP -> hardware/fab/rev<X>/
```

Stock KiCad libraries are at `/usr/share/kicad/{symbols,footprints,3dmodels}`.

## Working on boards

- Edit `.kicad_sch` / `.kicad_pcb` as text only for small, well-understood
  changes; prefer the `pcbnew` Python API for PCB edits. After any edit, run
  `tools/check_board.py` and confirm ERC/DRC are clean.
- Render to check visually: `kicad-cli sch export pdf` + `pdftoppm -png`, and
  `kicad-cli pcb render -o x.png --side top`.
- Expected ERC warnings in a fresh board: `isolated_pin_label` on unused GPIO
  labels (filtered by the checker).
- House design rules live in `tools/house_rules.py` and `tools/house_rules.kicad_dru`
  (fab is **PCBWay**, standard 2-layer service: we use 0.15 mm track/space,
  0.3 mm min drill, 0.6/0.3 mm vias, 0.3 mm copper-to-edge — all inside PCBWay's
  no-extra-cost limits). New boards copy them; existing boards
  keep their own copies.
- The RPi header (`J1`) defaults to the **Samtec REF-182665 SMT pass-through
  socket on top** (`Thl_Connector:Samtec_REF-182665_2x20_P2.54mm_PassThrough`,
  origin at the connector centre (32.5, 3.5) mm, rotated 180°), so the board
  stacks with MCC HATs using a stacking socket such as Samtec SSQ-120-03-T-D.
  Its pin holes are 0.97 mm NPTH; the house .kicad_dru relaxes NPTH and
  hole-to-hole clearance for this footprint only. `new_board.py --header socket`
  puts a plain 2×20 socket on the bottom instead (top of stack only). RPi pin 1
  is at (8.37, 4.77) mm from the board corner. Don't move J1 or the MH holes.
- That footprint is built from the SnapMagic download in
  `lib/footprint_src/Thl_Connector/vendor/` by `samtec_ref_182665.py`, which
  renumbers it for top mounting and trims the pads; read its docstring before
  changing it.
- **3D models are STEP** (`check_board.py` fails non-STEP models and warns on
  missing ones). Keep vendor STEP files in `lib/3dmodels/<Lib>.3dshapes/`.
  The repo is public: a model whose license forbids redistribution (e.g.
  SamacSys) stays local: git-ignore it and list it in
  `lib/3dmodels/LOCAL_ONLY.txt` (the checker then only warns when it is absent).
- `transfer/` is a temporary drop box for files from the user's Windows
  machine. Import what's there into `lib/` (recording the source in
  `lib/SOURCES.md`) and remove it from `transfer/` in the same commit.
- Give every part to be assembled `Manufacturer` and `MPN` symbol fields;
  `fab.py` puts them in the PCBWay BOM.

## Part selection (hand assembly)

Boards are mostly **hand assembled**. Cost and density are not the main
drivers, so choose parts that are easy to solder by hand:

- Resistors and capacitors: **1206** wherever possible. Decoupling capacitors:
  **0805**. Nothing smaller than 0805 (`check_board.py` fails 0603 and below).
- Use the KiCad `_HandSolder` footprint variants (longer pads); `lib/` only
  carries those for chip R/C/LED.
- Ceramic capacitors: **X-rated dielectric (X5R, X7R, X7S, …) or better (C0G/NP0)**.
  Never Y5V/Y5U/Z5U (`check_board.py` fails these if they appear in Value/MPN).
  Put the dielectric and voltage in the Value, e.g. `100nF 50V X7R`.
- Prefer leaded or large packages (SOIC, SOT-223, TQFP at 0.5 mm or coarser)
  over QFN/BGA/DFN when a choice exists, and leave room around parts for an iron.

## Raspberry Pi header sharing (MCC DAQ HATs)

These boards are HASS test fixtures. Any board on the 40-pin header shares it
with a stack of Digilent/MCC DAQ HATs (MCC 118, 128, 134, 152, 172; up to 8,
addressed by jumpers). Pins the MCC HATs use, from the `daqhats` library source
(github.com/mccdaq/daqhats, `lib/util.c`, `mcc128.c`, `mcc172.c`, `mcc152*.c`):

| BCM | Pin | MCC use |
|-----|-----|---------|
| 0, 1 | 27, 28 | ID EEPROMs (ID_SD/ID_SC). **Never fit a HAT ID EEPROM on our boards.** |
| 7, 8 | 26, 24 | SPI0 CE1 (MCC 152 DAC), CE0 (all) |
| 9, 10, 11 | 21, 19, 23 | SPI0 MISO/MOSI/SCLK |
| 12, 13, 26 | 32, 33, 37 | Board address A0, A1, A2 |
| 16 | 36 | Reset (MCC 128/172) |
| 20 | 38 | IRQ (MCC 128/172) |
| 21 | 40 | IRQ (MCC 118/134/152) |
| 2, 3 | 3, 5 | I2C1, **shared**: MCC 152 DIO expanders at 0x20–0x27. We may add I2C devices at other addresses. |

Free for our boards: BCM 4, 5, 6, 14, 15, 17, 18, 19, 22, 23, 24, 25, 27, plus I2C1
(outside 0x20–0x27). UART0 is on BCM 14/15; Pi 4 uart3 / Pi 5 uart2 is on BCM 4/5.

Hosts: **Raspberry Pi 5 and Orange Pi 6**. Pick header pins by physical position
and check them on both; the Orange Pi 6 maps functions to pins differently and
needs overlays. Prefer interfaces that use no header signal pins (e.g. USB).

## Firmware

Microcontrollers: Microchip PIC (MPLAB X / XC8/XC16/XC32), Espressif ESP32
(ESP-IDF or PlatformIO), ST STM32 (CubeMX-generated CMake + arm-none-eabi-gcc).
Each board's firmware lives in `boards/<name>/firmware/`.
