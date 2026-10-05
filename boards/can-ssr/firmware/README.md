# CAN SSR firmware

Target: PIC18F47Q84 (TQFP-44; 128 KB flash, 12,800 bytes RAM, 1 KB EEPROM,
CAN FD), 16 MHz crystal x 4 PLL = 64 MHz. Compiler: MPLAB XC8 v4.00 with the
PIC18F-Q DFP 1.31.492.

```sh
make          # build/can-ssr.hex (and .elf), prints the memory summary
make clean
```

`XC8` and `DFP` in the Makefile default to the install under `~/microchip`.
To program and debug, open the sources in an MPLAB X project in this directory
(`nbproject/private`, `build/` and `dist/` are git-ignored), or flash
`build/can-ssr.hex` with MPLAB IPE.

CAN messages: [`PROTOCOL.md`](PROTOCOL.md).

## Status

Version 0.1 compiles cleanly. **It has not run on hardware yet.** Items to
check on the first board:

- CAN clock source (`C1CONL.CLKSEL0 = 0` assumed to be Fosc, 64 MHz) and the
  500 kbit/s / 2 Mbit/s bit timing.
- I2C1 clock selection (`I2C1CLK = 0` assumed Fosc/4) and the 100 kHz rate.
  Also check that the Q84 I2C host sequence (count register, auto stop)
  talks to the MCP3426/MCP4725 through the ISO1640.
- MAX7219 digit order (DIG0 = leftmost digit assumed) and segment wiring.
- Mean Well remote polarity: photorelay closed = supply on (UHP-1500: RC
  shorted to +12V-AUX = on).
- Rotary switch reads 0-15 the right way round (closed contact = 0 bit,
  inverted in firmware).

## Structure

| File | Role |
|---|---|
| `board.c/h` | config bits, pin map (from the PCB netlist), PPS, address switch |
| `sampling.c/h` | 2 kHz TMR0 interrupt: millisecond clock, ACS770 current (average/peak per period), BUILD_REF and V12_MON slots, 1 kHz fault capture |
| `iso.c/h` | load side over I2C: MCP3426 (Vin, Vout, PV/PC feedback), MCP4725 (PV, PC); forces the DACs' power-on value to 0 |
| `control.c/h` | build detection, sequenced turn-on, PV loop, monitors |
| `can.c/h` | CAN FD module: TX queue, one RX FIFO, two filters |
| `display.c/h` | MAX7219 (bit-banged): V/A alternation, fault code, boot screen |
| `faults.c/h` | latched faults and warnings |
| `main.c` | message handling, failsafe timeout, periodic messages, LEDs |

Behaviour:

- **Boot:** outputs off, read the address switch once, pulse the trip reset,
  read the build resistor (HC 7.15k, STD 16.2k, HV 35.7k; out of band = `BUILD`
  fault, which never clears), show e.g. `St.05` (build, node) for 1.5 s, send INFO.
- **Display:** Vin while off, Vout while on, alternating with the current every
  2 s, with the V or A indicator lit. Fault: `E` + code.
- **LEDs:** status (green) is on while the output is on, blinks at 1 Hz when
  idle with a host present, and flashes briefly every 2 s with no host. Fault
  (red) is on while a fault is latched and blinks for warnings.
- **Watchdog:** about 256 ms, cleared by the main loop.

## Memory (XC8 v4.00, -O2, firmware 0.1)

| | Used | Of | |
|---|---|---|---|
| Flash | 10.5 KB | 128 KB | 8 % (12.8 KB at -O0) |
| RAM | 3.2 KB | 12.5 KB | 25 % |
| EEPROM | 0 | 1 KB | |

RAM breakdown: fault capture 2.5 KB (1024 x 2 B current + 2 x 128 x 2 B
voltages), CAN message RAM 384 B (TX queue 8 + RX FIFO 16 objects of 8 bytes),
everything else about 260 B.

Room for growth: CAN FD 64-byte payloads would take the CAN RAM to about
1.9 KB. Capturing current at the full 2 kHz instead of 1 kHz adds 2 KB. A
bootloader needs 4-8 KB of flash. Even with all three, RAM stays near 60 % and
flash under 20 %.
