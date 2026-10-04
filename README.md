# ThlHats

Test devices in the Raspberry Pi HAT form factor: KiCad 10 PCB designs and
their firmware (PIC, ESP32, STM32).

## Design rules

- 2-layer boards, at most 100 × 100 mm
- Mount on standard Raspberry Pi M2.5 standoffs (58 × 49 mm hole pattern)
- All symbols, footprints and 3D models are kept in this repo under `lib/`.
  The KiCad projects do not use the stock or globally installed libraries.

## Requirements

- KiCad 10 (`kicad-cli` and the `pcbnew` Python module, run with the system `python3`)
- `pdftoppm` (poppler-utils), optional, for rendering schematics to images

## Quick start

```sh
# New 65 x 56.5 mm HAT with the 40-pin header, M2.5 holes, and a GND pour
tools/new_board.py my-board --title "My Board" --mcu esp32

# Bring parts into the repo libraries
tools/kilib.py symbol RF_Module:ESP32-S3-WROOM-1     # also copies footprint + 3D model
tools/kilib.py footprint Package_SO:SOIC-8_3.9x4.9mm_P1.27mm

# Parts from SnapEDA / Ultra Librarian / vendors
tools/kilib.py symbol PART --from ~/Downloads/PART.kicad_sym --lib Thl_Sensor --source "SnapEDA"
tools/kilib.py footprint PART_FP --from ~/Downloads/PART.kicad_mod --model ~/Downloads/PART.step \
    --lib Thl_Sensor --source "SnapEDA"

# Check (house rules + ERC + DRC) and produce fab files
tools/check_board.py boards/my-board
tools/fab.py boards/my-board
```

Open `boards/<name>/hardware/<name>.kicad_pro` in KiCad. Its project library
tables list only the libraries in `lib/`. After you add a new library, run
`tools/kilib.py sync`. The import commands do this for you.

## Layout

| Path | Contents |
|------|----------|
| `lib/` | Symbols, footprints, 3D models, and `SOURCES.md` (where each part came from) |
| `boards/<name>/hardware/` | KiCad project |
| `boards/<name>/firmware/` | Firmware for that board |
| `tools/` | Board generator, library importer, checker, fab-output script |

## Library licensing

Parts copied from the KiCad libraries are CC-BY-SA 4.0 with the KiCad library
exception: boards made with them are not affected by the license. Parts from
other sources keep their own licenses, which are recorded in `lib/SOURCES.md`.
