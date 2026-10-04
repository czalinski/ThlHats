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
tools/fab.py boards/<name>                 # gerbers/drill zip, BOM, JLC CPL, PDF, STEP -> hardware/fab/rev<X>/
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
  (aimed at JLCPCB/PCBWay standard 2-layer: 0.15 mm track/space, 0.3 mm min drill,
  0.6/0.3 mm vias, 0.3 mm copper-to-edge). New boards copy them; existing boards
  keep their own copies.
- The RPi header (`J1`) is a 2×20 socket on the **bottom** side; pin 1 is at
  (8.37, 4.77) mm from the board corner. Don't move J1 or the MH holes.
- Fill `LCSC` symbol fields for parts to be assembled by JLCPCB; `fab.py` puts them in the BOM.

## Firmware

Microcontrollers: Microchip PIC (MPLAB X / XC8/XC16/XC32), Espressif ESP32
(ESP-IDF or PlatformIO), ST STM32 (CubeMX-generated CMake + arm-none-eabi-gcc).
Each board's firmware lives in `boards/<name>/firmware/`.
