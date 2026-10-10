# Core host protocol (draft, firmware 0.4)

The host talks to the core over Ethernet. Plain sockets only: no drivers, no
special privileges.

| What | Transport | Port (on the core) | Direction |
|---|---|---|---|
| Commands and responses (ASCII) | TCP | **5000** (two clients at a time) | host → core, one response per command |
| Serial-card port 1-4, raw bytes | TCP | **5001-5004** (one client each) | both ways |
| SSR measurement stream | UDP | from 5100 to host port **5100 + node** | core → host |

The core never starts a conversation. It only answers commands and, once the
host has asked for it with `STREAM ON`, sends the UDP stream.

## Commands (TCP 5000)

The same commands work on the debug UART (J5, 115200 8N1), so a board can
be set up and tested from a terminal or with `nc <ip> 5000`.

- A command is one line of ASCII, ended by LF. CR is ignored. Response lines
  end with CR LF. Words are
  separated by spaces. Command names and keys are case-insensitive.
- Arguments are `key=value` pairs, and their order does not matter.
- **Every command gets exactly one response.** A response is zero or more
  data lines starting with `* `, then a final line starting with `OK` or
  `ERR`. A client reads lines until it gets one that starts with `OK` or
  `ERR`.
- `OK [text]` means success. Single-line answers carry their data on the
  `OK` line.
- `ERR <code> <text>`: `400` bad command or argument, `404` no such device or
  device not connected, `409` refused by the device, `503` not available now,
  `504` device did not answer.
- Commands are executed in order. The next command is read only after the
  previous response is complete. That includes commands that wait for a CAN
  device to answer, which can take up to 1.5 s.

### General

| Command | Response |
|---|---|
| `ID` | `OK ThlHats core fw=0.4 sn=<serial> mac=<mac>` |
| `HELP` | `* ` one line per command, then `OK` |
| `STATUS` | every device, one `* ` line each, then `OK` (below) |
| `NET [ip=a.b.c.d] [mask=a.b.c.d] [gw=a.b.c.d]` | `OK NET ip=… mask=… gw=… (active ip=…)`. New values take effect after `SAVE` and `REBOOT`. |
| `SAVE` | stores the NET settings, the current SER settings and the AI zero offsets in flash as power-up defaults: `OK saved` |
| `REBOOT` | `OK rebooting`, then a reset 100 ms later |

`STATUS` example:

```
* CORE fw=0.4 up=81234 ip=192.168.1.50 link=100M-full clients=1
* CAN 1 present=1 mode=fd nominal=500000 data=2000000 state=active tec=0 rec=0 rx=81234 tx=325
* CAN 2 present=1 state=stopped
* CAN 3 present=0
* CAN 4 present=0
* SSR 3 port=5103 state=on build=STD vset=24.00 ilimit=10.00 vin=24.01 vout=23.98 iavg=1.23 ipeak=1.50 faults=0x0000 warnings=0x00 v12=12.1 timeout=1000 fw=0.2 age=4
* SER 1 type=rs232 baud=9600 data=8 parity=N stop=1 client=192.168.1.10 rx=0 tx=12
* STREAM off
* IO present=1 vmid=1.650
* RLY 1=off 2=on 3=off 4=off
* GPIO 1 mode=in pull=down out=0 level=0
* ...
* AI 1 v=12.034 p=6.020 n=-6.014 over=0
* AI 2 v=0.000 p=0.000 n=0.000 over=0
OK
```

An SSR is listed while it has sent anything in the last 2 s. `age` is the
number of ms since its last frame.

### Serial-card ports

| Command | Response |
|---|---|
| `SER <1-4> [baud=<300-1000000>] [data=<7\|8>] [parity=<N\|E\|O>] [stop=<1\|2>]` | `OK SER <n> type=… baud=… data=… parity=… stop=…` |

- Power-up default for every port: 9600 baud, 8N1, the most common
  instrument setting. `SAVE` stores other defaults.
- Any mix of settings may be given, including none. A setting that is left
  out keeps its current value.
- The response always gives the full set of settings in effect after the
  command. `baud` is the rate the UART actually runs at (its divider
  rounds).
- A command with any invalid value changes nothing and returns `ERR 400`.
- Ports 1 and 2 are RS-232 (U2, U3). Ports 3 and 4 are RS-485 half duplex
  (U4, U5). The core drives the transceiver enable (DE1/DE2) from the first
  bit sent until the last stop bit has left.
- `data=7` is done in firmware on an 8-bit UART frame: the parity bit (or
  the second stop bit for 7N2) is generated on send and removed on receive.
  This covers 7E1, the usual 7-bit setting (older instruments, scales,
  Modbus ASCII), and 7O1, 7E2, 7O2 and 7N2. 7N1 is refused: its 9-bit frame
  does not fit.
- Data goes through TCP port 5000 + n untouched, in both directions. The
  settings stay in place across connections.

### CAN channels

| Command | Response |
|---|---|
| `CAN SCAN` | detects transceivers on stopped channels: `OK CAN present=1,2,3,4` |
| `CAN <1-4> START [mode=fd\|classic\|listen] [nominal=<bit/s>] [data=<bit/s>]` | `OK CAN <n> mode=… nominal=… data=…`. Defaults: fd, 500000, 2000000. |
| `CAN <1-4> STOP` | `OK CAN <n> stopped` |
| `CAN <1-4> TX <id>#<data>` | sends a classic frame (`cansend` syntax: `123#DEADBEEF`, `1ABCDEF0#`, `100#R`): `OK` |
| `CAN <1-4> TX <id>##<f><data>` | sends an FD frame, `f` = 1 for bit rate switch: `OK` |
| `CAN <1-4> TEST` | internal loopback self-test, no bus traffic: `OK pass` or `ERR 409 fail` |

The SSRs are on CAN1 and the core runs it, so CAN1 should normally stay at
the default settings.

### SSR (can-ssr nodes on CAN1)

An SSR is addressed by its node number (0-15), which is set on its rotary
switch.

| Command | Response |
|---|---|
| `SSR <node>` | that node's status line (as in `STATUS`) without the `* `: `OK SSR 3 port=5103 state=…` |
| `SSR <node> SET v=<volts> i=<amps> hot=<0\|1> noreg=<0\|1> timeout=<ms>` | `OK SSR <node> v=… i=… hot=… noreg=… timeout=…`: the values the SSR accepted |
| `SSR <node> OFF` | same as `SET v=0 i=0 hot=0 noreg=0 timeout=1000` |
| `SSR ALL OFF` | broadcast ALL_OFF to every node: `OK` |
| `SSR <node> CLEAR` | clears latched faults: `OK SSR <node> faults=0x…`, taken from the node's next STATUS (≤ 1.5 s); non-zero means a cause is still present |
| `SSR <node> INFO` | asks the node for INFO: `OK SSR <node> type=can-ssr fw=0.2 build=STD` |

- **`SET` is all or nothing.** All five values are required, and a `SET`
  with any of them missing or out of range returns `ERR 400` without
  sending anything.
- `v` is the output voltage (0 switches off). `i` is the current limit
  (0 = the build's maximum). The units on the wire are 10 mV and 10 mA, so
  the values are rounded to those steps. `hot=1` switches a live supply
  without the Mean Well remote (HC/STD builds only). `noreg=1` is for a
  fixed supply: do not drive PV/PC.
- The core sends the SSR's SET frame and waits up to 500 ms for its SET_ACK.
  The response gives the values sent, rounded, once the SSR has accepted
  them. If the SSR refuses, the response is `ERR 409` with its reason
  (`fault latched`, `voltage above build limit`, `current above build
  limit`, `hot switching refused`). With no answer it is `ERR 504`, and with
  the node not seen in the last 2 s it is `ERR 404`.
- **Failsafe: the host owns the timeout.** `timeout` (100-60000 ms) goes to
  the SSR inside its SET frame, and the SSR enforces it. While its output
  is on, the SSR must receive another SET within `timeout`. Otherwise it
  switches off and latches `HOST_TIMEOUT`, which `SSR <node> CLEAR` clears.
  The host keeps an output on by repeating the same `SET`. A repeated SET
  with the same values does not restart the turn-on sequence; changed `v`
  or `i` values are applied in place. Pick `timeout` at about 4× the
  repeat interval, e.g. repeat every 250 ms with `timeout=1000`.
- The check is end to end: a hung host program, a dropped TCP connection, a
  rebooted core and a broken CAN cable all end the repeated SETs. The core
  never sends anything that keeps an output on. Its HOST_HB frame (every
  250 ms on CAN1) only lights the SSR's "host present" LED.
- This needs can-ssr firmware 0.2. Firmware 0.1 ignores the timeout and
  uses a fixed 1 s, which also HOST_HB refreshes.

### io-card

The io-card is detected at boot from its analog inputs: each leg sits on
100 nF and 130k to VMID, so a short pull-up and pull-down barely move it.
Re-detect with `IO SCAN`. While no card is detected, `RLY`, `GPIO` and `AI`
return `ERR 404`.

| Command | Response |
|---|---|
| `IO` / `IO SCAN` | `OK IO present=0\|1 vmid=<V>`. VMID is the 1.65 V reference from the core's OA5. |
| `RLY [1=on\|off] [2=…] [3=…] [4=…] [all=on\|off] [timeout=<ms>]` | `OK RLY 1=… 2=… 3=… 4=… timeout=<t1>,<t2>,<t3>,<t4> expired=none\|<list>` |
| `GPIO` | one `* GPIO n …` line per pin, then `OK` |
| `GPIO <1-4> [mode=in\|out] [pull=none\|up\|down] [out=0\|1]` | `OK GPIO <n> mode=… pull=… out=… level=…` |
| `AI` | `* AI 1 …` and `* AI 2 …`, then `OK` |
| `AI <1-2>` | `OK AI <n> v=<V> p=<V> n=<V> over=0\|1` |
| `AI <1-2> ZERO` | with the inputs shorted: stores the offset, `OK AI <n> zero=<V> (SAVE to keep)` |

- **RLY** drives the four relay outputs, which feed **external** relay
  coils (rack 12 V, or an external supply up to 24 V chosen by the jumper on
  the card). Any mix of outputs may be given, `all=` first and then the
  numbered ones. The response always shows all four. All outputs are off
  at power-up.
- **Relay failsafe:** `timeout` (100-3600000 ms) applies to the outputs
  named in that command.
  - An output switched on with a timeout switches off by itself unless
    another `RLY` naming it arrives within `timeout`. The host keeps it on
    by repeating the command, about every timeout / 4, as with the SSRs.
  - Without `timeout`, those outputs have no failsafe and stay as set.
  - A plain `RLY` only reports and does not restart any timer.
  - The response lists each output's timeout (0 = none). `expired` lists
    the outputs the failsafe switched off; an output leaves the list when
    it is next commanded.
  - The failsafe is enforced on the core, so a core reset also leaves all
    outputs off.
- **GPIO** settings are partial like `SER`: keys left out keep their value.
  `out` is the level driven in `mode=out`, and `level` is the pin as read
  back. The default at power-up is `mode=in pull=down`. The pins are 3.3 V
  and **not 24 V tolerant**. Pull-ups and pull-downs are the PIC32's weak
  internal ones, enough for a dry contact to GND or +3.3 V.
- **AI**:
  - `v` is AIn+ minus AIn-, in volts, after the `ZERO` offset.
  - `p` and `n` are the two legs against the LOGIC ground. Each must stay
    within about ±116 V, and `over=1` means a leg hit the ADC limit.
  - The resolution is 63 mV per count. Each reading averages 64
    conversions per leg and takes about 1 ms.
  - The core measures VMID ahead of the card's 1k isolation resistor. With
    all four legs near ±116 V, `p` and `n` can therefore be off by up to
    about 3.6 V. `v` is not affected, because both legs see the same
    VMID.
  - Common-mode error depends on the 1 % divider match. `ZERO` removes the
    offset, and `SAVE` keeps it.

### UDP measurement stream

| Command | Response |
|---|---|
| `STREAM ON [ip=a.b.c.d] [batch=<1-10>] [fmt=bin\|text]` | `OK STREAM on ip=… batch=… fmt=…` |
| `STREAM OFF` | `OK STREAM off` |
| `STREAM` | `OK STREAM on ip=… batch=… fmt=… sent=… dropped=…` or `OK STREAM off` |

- With `STREAM ON`, every MEAS frame (one per SSR every 10 ms) is
  forwarded as a UDP datagram to the host's port **5100 + node**. The
  destination is `ip`, or the address of the client that sent `STREAM ON`.
- `batch` samples go in one datagram. The default is 5, which is 20
  datagrams per second per SSR and up to 50 ms of delay. A lost datagram is
  simply lost: nothing is resent.
- The stream stays on until `STREAM OFF` or a reboot.

Binary datagram (`fmt=bin`, the default), little-endian:

| Offset | Type | Field |
|---|---|---|
| 0 | u8 | magic `0x53` (`S`) |
| 1 | u8 | format version, 1 |
| 2 | u8 | node |
| 3 | u8 | sample count n |
| 4 | u32 | datagram sequence number (per node; gaps = lost datagrams) |
| 8 | u8 | state (as STATUS: 0 off, 1 closing, 2 rising, 3 on, 4 stopping) |
| 9 | u8 | reserved |
| 10 | u16 | latched faults |
| 12 + 12k | u32 | sample k: core time in ms when the MEAS frame arrived |
| 16 + 12k | u16 | Vin, 10 mV |
| 18 + 12k | u16 | Vout, 10 mV |
| 20 + 12k | u16 | Iavg, 10 mA |
| 22 + 12k | u16 | Ipeak, 10 mA |

With `fmt=text`, each datagram is one line per sample,
`<node> <ms> <vin> <vout> <iavg> <ipeak>`, in volts and amps with two
decimals. You can watch it with `nc -ul 5103`.

## Network setup

- The default address is 192.168.1.50/24 with gateway 192.168.1.1.
  Change it with `NET` + `SAVE` + `REBOOT`, over TCP or the debug UART.
- The MAC address is locally administered, 02:54:48:xx:xx:xx, and is made
  from the PIC32 serial number.
- IPv4 only, static addresses. No DHCP: a rack always gets a fixed
  address saved in flash. Set it up on a direct cable at the default
  address, or over the debug UART.
- Reprogramming the PIC with a chip erase also erases the saved settings.
  They then go back to the defaults.
