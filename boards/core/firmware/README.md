# Core firmware: PIC32MK1024MCM064

Firmware for the core board. It runs the host protocol over Ethernet
(**[PROTOCOL.md](PROTOCOL.md)**) and drives the can-card's four CAN FD
channels, the SSRs on CAN1, the serial-card ports and the io-card's relay
outputs, GPIO and analog inputs.

## Build

MPLAB XC32 v5.00 in `~/microchip/xc32/v5.00` and the PIC32MK-MC device pack
1.13.270 in `~/microchip/packs/Microchip/PIC32MK-MC_DFP/1.13.270` (next to XC8):

```sh
make            # build/core.hex, memory report
make clean
```

Program `build/core.hex` over ICSP (J2: PICkit 4/5, ICD 4 or Snap with MPLAB
IPE). The debug UART is J5 (1 TX, 2 RX, 3 GND, 3.3 V), 115200 8N1.

## Host side

`../host/thlcore.py` uses the Python standard library only. It is a
reference client and a test tool:

```sh
host/thlcore.py 192.168.1.50 STATUS
host/thlcore.py 192.168.1.50 SSR 3 SET v=24 i=5 hot=0 noreg=0 timeout=1000
host/thlcore.py 192.168.1.50 --stream       # decoded SSR samples, one line each
host/thlcore.py 192.168.1.50 --serial 1     # dump serial port 1
nc 192.168.1.50 5000                        # type commands by hand
```

## Modules

| File | What it does |
|---|---|
| `board.c` | Config words; software clock switch to 120 MHz (silicon errata DS80000898D 2.1.1); REFCLK4 40 MHz CAN clock; ports; time base |
| `canfd.c` | The four CAN FD modules: card detection, bit timing, TX/RX FIFOs, loopback self-test |
| `w6100.c`, `net.c` | SPI3 driver and sockets: TCP servers on 5000 (×2) and 5001-5004, UDP stream socket. Keep-alive 5 s |
| `cmd.c` | The ASCII command set, shared by TCP and the debug UART |
| `server.c` | TCP command sessions. A session reads the next command only once the previous response has been handed to the W6100 |
| `ssr.c` | can-ssr nodes on CAN1: status cache, SET/CLEAR/INFO (SET carries the host's failsafe timeout), HOST_HB presence frame, batched UDP stream |
| `serial.c` | UART2-5 ↔ TCP 5001-5004 through interrupt rings; RS-485 DE timing; 7-bit framing done in firmware |
| `io.c` | io-card: card detection, relay outputs, GPIO (mode, pull, level), differential AI on the shared ADC7 (single conversions; errata 2.3.1 rules out scan mode), OA5 VMID follower (low-power unity gain) |
| `settings.c` | `NET`/`SER` power-up settings in the last flash page, CRC-checked |
| `console.c` | Debug UART: the same commands plus `MON ON/OFF` (candump-style CAN frame printing) |

## Card detection

The can-card's ISOW1044 transceivers drive RXD high while the bus is idle.
With the CAN module off, the firmware pulls each CnRX pin down and samples it
for 2 ms. A channel that reads high in at least 10 % of the samples is
present. Detection runs at boot, 50 ms after power-up, and again on
`CAN SCAN`. A TX pin is never pulled down and is only driven once its
channel is started.

A channel whose bus is stuck dominant reads as absent.

## First-board checklist

1. The console prints `ID` and `STATUS` at boot, and D2 blinks at 1 Hz. If
   the output is garbled, SYSCLK is wrong: check that the crystal is
   running.
2. `CAN 1 TEST` through `CAN 4 TEST` pass with or without the can-card.
   This proves the CAN clock, message RAM and bit timing.
3. With the can-card fitted, `STATUS` shows all four channels present.
   Without it, it shows none.
4. `STATUS` shows `link=100M-full` with a switch plugged in, and
   `nc <ip> 5000` answers `ID`. Out of the box the address is
   192.168.1.50/24. Set your own with `NET ip=… mask=… gw=…`, then `SAVE`
   and `REBOOT`.
5. With an SSR on CAN1 (can-ssr firmware 0.2), it shows up in `STATUS`.
   `SSR <n> SET v=… i=… hot=0 noreg=0 timeout=1000` switches it on, and
   `thlcore.py --stream` shows samples every 10 ms. If the SET is not
   repeated, the output switches off after 1 s with `HOST_TIMEOUT`.
6. `SAVE` survives a power cycle: check with `NET` after reboot. Flash
   writes are not verified on hardware yet.
7. Measure the 25 MHz crystal drive level (Y2, ABM3 rated 100 µW).
8. io-card fitted: `IO` shows `present=1 vmid=1.650`. Then check:
   - `RLY 1=on` lights the card's red LED 1 and puts V_RLY on J30.1.
   - `GPIO 1 mode=out out=1` gives 3.3 V on J40.1.
   - `AI 1` reads a known voltage. Short the inputs and run `AI 1 ZERO`,
     then `SAVE`.
   - Without the card, `IO SCAN` shows `present=0`.
9. **VMID stability.** OA5 is specified for at most 32 pF of load
   (DS60001519D 27.6). The io-card isolates it with R88 1k and C85 100 nF;
   scope VMID on the core side with the card fitted.
10. `RLY 1=on timeout=1000` switches output 1 on. With nothing repeating it,
    the output switches off after 1 s and the reply shows `expired=1`.

## Not done yet

- Raw CAN traffic for non-SSR devices over the network. Today it is only
  `CAN n TX` and `MON` on the debug UART.
- Serial-card hardware. The RS-232/RS-485 port split and the DE pins
  follow the plan in `serial.h` and must be checked against the card once
  it is drawn.
