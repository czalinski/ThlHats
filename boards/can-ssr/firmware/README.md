# CAN SSR firmware

Microchip PIC. Suggested toolchain: MPLAB X + XC8/XC16/XC32, or the `xc8-cc` CLI with a Makefile. Keep the MPLAB X project in this directory (nbproject/private and build/dist outputs are git-ignored).

Target: PIC18F47Q84 (TQFP-44, 128 KB flash, CAN FD), XC8.

- **One image for all builds.** Read the build resistor on an ADC pin at boot;
  enforce that build's voltage, current and hot-switch limits. A reading
  outside the three bands is a fault: switch off, report over CAN. Never store
  the build in flash (flash holds calibration data only).
- **Failsafe:** switch off and Mean Well remote off at reset and when the CAN
  heartbeat stops; the hardware overcurrent latch can only be reset after the
  fault is read.
- **Turn-on:** sequenced through the Mean Well remote input by default; hot
  turn-on only on HC/STD and only within the limits in requirements 4.2.1.
- **Supply programming:** PV/PC through the isolated I2C DACs, closed loop on
  the measured input voltage.
- **Sampling:** each MCP3426 converts one voltage continuously at 240 SPS
  (12 bit); current from the PIC ADC at kHz rates. Report at a configurable
  rate (10 Hz default, up to 100 Hz) with current average and peak per period.
  Later: fault capture (rolling ~1 s buffer sent around a trip or anomaly).
