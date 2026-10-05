# CAN Controller firmware

PIC32MK1024MCM064 (MIPS32, 1 MB flash, 256 KB RAM). Suggested toolchain:
MPLAB X + XC32, with MPLAB Harmony v3 for peripheral setup, or a CMake build
calling `xc32-gcc` directly. Keep the MPLAB X project in this directory
(`nbproject/private`, `build/` and `dist/` are git-ignored).

Planned USB composite device:

- **CAN:** gs_usb protocol, 2 channels, classic CAN 2.0 or CAN FD per channel,
  bound to Linux's `gs_usb` driver through `new_id`.
- **Control:** the shared ThlHats host protocol for GPIO, relays, analog in/out,
  configuration, and the watchdog. **TBD**.
- **USB IDs:** Microchip VID 0x04D8 with a sublicensed PID. **TBD**: request it.

Failsafe: relay and GPIO outputs off at reset and when the host link is lost.
