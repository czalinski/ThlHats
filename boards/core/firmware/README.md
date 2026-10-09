# Core firmware: PIC32MK1024MCM064

Bring-up firmware for the core board: clocks, debug console, W6100 check,
can-card detection and the four CAN FD channels. The host protocol over
Ethernet comes next.

## Build

MPLAB XC32 v5.00 in `~/microchip/xc32/v5.00` and the PIC32MK-MC device pack
1.13.270 in `~/microchip/packs/Microchip/PIC32MK-MC_DFP/1.13.270` (next to XC8):

```sh
make            # build/core.hex, memory report
make clean
```

Program `build/core.hex` over ICSP (J2: PICkit 4/5, ICD 4 or Snap with MPLAB
IPE). The debug UART is J5 (1 TX, 2 RX, 3 GND, 3.3 V), 115200 8N1.

## What it does

- **Clocks.** The 12 MHz crystal drives the SPLL (×40 / 4), giving a 120 MHz
  SYSCLK. The chip starts on FRC and the firmware switches clocks in
  software, because of silicon errata DS80000898D 2.1.1 (the FNOSC fuse may
  not select the clock). PBCLK2/3 run at 60 MHz. REFCLK4 is SYSCLK / 3 =
  40 MHz and clocks the CAN FD modules. The datasheet (DS60001519D,
  Register 26-1) sets the limit at 80 MHz and recommends 40 MHz.
- **Card detection.** Each ISOW1044 on the can-card drives RXD high while
  its bus is idle. With the CAN module off, the firmware pulls each CnRX pin
  down and samples it for 2 ms. A channel that reads high in at least 10 % of
  the samples is "present". Detection runs once at boot, 50 ms after
  power-up, and again on `scan` for stopped channels.
- **TX pins are not driven until a channel is started.** Their pin is not
  mapped to the CAN module, and a pull-up keeps a card's TXD recessive.
  Limitation: a channel whose bus is stuck dominant reads as absent.
- **CAN FD.** At boot, every present channel starts in CAN FD mode at
  500 kbit/s nominal and 2 Mbit/s data. This matches the can-ssr bus, and
  classic and FD frames can both be received. Bit timing comes from the
  40 MHz clock, with an 80 % sample point and automatic transmitter delay
  compensation. Each channel has a TX FIFO (8 × 64 bytes) and an RX FIFO
  (16 × 64 bytes), and accepts all IDs. Polled from the main loop.
- **W6100.** Reset, then a read of the chip ID (0x61) and PHY status, both
  shown in `info`. No sockets yet.
- **Unused bus pins.** The serial-card and io-card pins (U2-U5, DE, RLY,
  GPIO) stay inputs with pull-downs until those cards have drivers.

## Console

```
info                          firmware, clocks, W6100, card detection
scan                          detect transceivers on stopped channels
can                           channel status (mode, bit rates, TEC/REC, counters)
start <ch|all> [fd|classic|listen] [nominal] [data]
stop <ch|all>
tx <ch> <id>#<data>           classic frame: tx 1 123#DEADBEEF, tx 1 1ABCDEF0#, tx 1 100#R
tx <ch> <id>##<f><data>       FD frame, f = 1 for bit rate switch: tx 2 123##1112233
mon [on|off]                  print received frames (candump style)
test <ch|all>                 internal loopback self-test, no bus traffic
```

Frame syntax follows Linux `cansend`: 3 hex digits for a standard ID,
8 for an extended ID. Received frames print like `candump`:
`can1  123   [4]  DE AD BE EF`.

## First-board checklist

1. The console prints `info` at boot, and D2 blinks at 1 Hz. If the UART
   output is garbled, SYSCLK is wrong: check that the crystal is running.
2. `test all` passes with or without the can-card. This proves the CAN
   clock, message RAM and bit timing.
3. With the can-card fitted, `info` shows all four channels present.
   Without it, it shows none.
4. With a terminated bus (JP1-JP4) and a second node, check that `tx`
   frames arrive and the counters stay at TEC/REC 0. To check the can-ssr
   protocol, send `tx 1 010#` (HOST_HB) and watch for its MEAS frames
   (0x20n).
5. `info` reads W6100 version 4661, and the link comes up when a switch is
   plugged in.
