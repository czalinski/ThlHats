# can-ssr CAN protocol (draft, firmware 0.2)

Bus: 500 kbit/s nominal. The node runs its controller in CAN FD mode but sends
**classic frames of at most 8 bytes**, so it works on a classic CAN 2.0 bus and
on a CAN FD bus (2 Mbit/s data phase configured but not used yet).

## Identifiers

11-bit standard IDs: `ID = (function << 4) | node`, where `node` is the rotary
switch (0-15, read once at boot). Lower IDs win arbitration.

| Function | ID | Direction | Bytes | Content |
|---|---|---|---|---|
| `0x00` ALL_OFF | `0x000` | host → all | 0 | every node switches off now (not a fault) |
| `0x01` HOST_HB | `0x010` | host → all | 0-8 | host present: status LED only (does not feed the failsafe) |
| `0x08` FAULT | `0x08n` | node → host | 8 | on a new fault, then every 1 s while any fault is latched |
| `0x10` SET | `0x10n` | host → node | 6 or 8 | `u16 Vset`, `u16 Ilimit`, `u8 flags`, `u8 seq`, optional `u16 timeout` (ms) |
| `0x11` CLEAR | `0x11n` | host → node | 0 | clear latched faults (also resets the hardware trip latch) |
| `0x13` CAPT_READ | `0x13n` | host → node | 2 | `u16 req` = sample index (bits 13-0) + buffer (bits 15-14) |
| `0x14` INFO_REQ | `0x14n` | host → node | 0 | reply with INFO |
| `0x20` MEAS | `0x20n` | node → host | 8 | `u16 Vin`, `u16 Vout`, `u16 Iavg`, `u16 Ipeak`, every 10 ms |
| `0x21` STATUS | `0x21n` | node → host | 8 | every 1 s, see below |
| `0x22` INFO | `0x22n` | node → host | 8 | at boot and on request, see below |
| `0x23` CAPT_DATA | `0x23n` | node → host | 8 | `u16 req` echoed, 3 × `u16` samples |
| `0x24` SET_ACK | `0x24n` | node → host | 2 | `u8 seq`, `u8 result` |

Little-endian. Voltage unit **10 mV**, current unit **10 mA** (`uint16`).

A node that receives a node → host frame carrying its own node number latches
`ADDR_CONFLICT`.

### SET

- `Vset = 0` switches the output off. Otherwise the node checks the build
  limits (HC 60 V / 50 A, STD 150 V / 25 A, HV 200 V / 12 A), then runs the
  sequenced turn-on: Mean Well remote off → close the switch → set PC and PV →
  remote on → wait for Vin ≥ 90 % of Vset (2 s limit) → on. While on, PV is
  trimmed every 100 ms on the measured Vin.
- `Ilimit` sets the supply's current limit (PC) and the firmware overcurrent
  trip: average current above `Ilimit` for 20 ms latches `SW_OC`. 0 = the
  build's maximum. The hardware trip (build resistor: 60 / 35 / 15 A) is
  independent of this.
- `flags`: bit 0 `HOT` = no Mean Well remote, switch a live supply (HC/STD
  only; refused on HV); bit 1 `NO_REG` = fixed supply, don't drive PV/PC.
- `SET_ACK.result`: 0 accepted, 1 fault latched (send CLEAR), 2 voltage above
  the build limit, 3 current above the build limit, 4 hot switching refused.

### Failsafe

Firmware 0.2: the host sets the failsafe timeout in each SET (bytes 6-7, ms,
clamped to 100-60000; a 6-byte SET means 1000 ms). The value of an accepted
SET applies. While the output is requested on, **only a SET to this node**
restarts the timer. If the timeout passes without one, the node switches off
and latches `HOST_TIMEOUT`. The host repeats its SET (same values: no
re-sequencing, only Vset/Ilimit updates) well inside the timeout, typically
every timeout / 4.

HOST_HB and the other host frames only light the "host present" status LED
(1 s). They no longer keep an output on, so a broadcast cannot hide a host that
has stopped controlling one particular node.

### FAULT

`u16 faults`, `u8 first fault (bit number)`, `u8 state`, `u16 Vin`, `u16 Iavg`.

| Bit | Fault |
|---|---|
| 0 | `HW_TRIP` hardware overcurrent latch |
| 1 | `SW_OC` average current above Ilimit |
| 2 | `HOST_TIMEOUT` |
| 3 | `BUILD` build resistor reading out of band |
| 4 | `ISO_COMM` load-side ADC/DAC not answering (no fresh Vin/Vout for 100 ms) |
| 5 | `SWITCH_OPEN` on, Vin > 5 V, Vout more than 2 V below it for 200 ms |
| 6 | `SUPPLY_NO_RISE` sequenced turn-on: Vin did not reach 90 % in 2 s |
| 7 | `ADDR_CONFLICT` |
| 8 | `OVERVOLTAGE` Vin above the build maximum + 5 % |

Faults latch and the output stays off until CLEAR (which fails if the cause is
still present). The display shows `E` + (first fault bit + 1).

### STATUS

`u8 state` (0 off, 1 switch closing, 2 supply rising, 3 on, 4 stopping),
`u8 build` (0 unknown, 1 HC, 2 STD, 3 HV), `u16 faults`, `u8 warnings`,
`u8 V12` (0.1 V), `u16 Vset`.

Warnings: bit 0 cable supply below 10 V, bit 1 PV loop at a DAC limit,
bit 2 CAN error passive / bus-off seen, bit 3 off but Vout follows Vin
(shorted switch, or a charged DUT with no load).

### INFO

`u8 board type (1 = can-ssr)`, `u8 fw major`, `u8 fw minor`, `u8 build`,
`u8 node`, 3 bytes reserved (serial number, TBD).

### Fault capture

The node keeps the last 1.024 s of current (1 kHz, raw 12-bit ADC counts:
0.5 V = 410 at 0 A, 32.77 counts/A) and 1.28 s of Vin and Vout (100 Hz,
10 mV units). The first fault freezes the buffers 200 ms later. Read them
oldest first with CAPT_READ: buffer 0 = current (index 0-1023), 1 = Vin,
2 = Vout (index 0-127). Each reply carries three samples starting at the
index. CLEAR re-arms the capture.

## Bus load

One MEAS frame per node every 10 ms: about 130 bits on the wire at 500 kbit/s,
so 16 nodes use about 42 % of the bus. That is why each MEAS frame carries
all four readings: four separate frames would need four times the
arbitration and framing overhead, and the host would lose the guarantee that
the readings come from the same period.
