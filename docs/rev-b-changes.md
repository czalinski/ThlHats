# Rev B changes

Rev A (git tag `revA`) went to PCBWay on 2026-10-12 for core, can-card,
io-card, serial-card, can-ssr and probe-helper. Those six boards are now
rev B; rev A design files stay as tagged. Rule: once a revision is sent for
manufacture, further design changes go into the next revision.

## Done in rev B (fields only, no layout change)

These parts are also what was bought for the rev A boards
(docs/orders/*-revA.csv).

Obsolete, end of life or not recommended for new designs (Mouser BOM check,
2026-10-12), or not orderable:

| Was | Now | Boards |
|---|---|---|
| IPB110N20N3LFATMA1 (discontinued) | IPB107N20N3GATMA1; STD build is sequenced-only (fw 0.3) | can-ssr |
| CC56-12SRWA | Kingbright CC56-12SURKWA | can-ssr |
| TLP222A(F) | Toshiba TLP240A(F) (Toshiba's successor) | can-ssr |
| ACS770ECB-100U-PFF-T (not a valid part) | ACS770LCB-100U-PFF-T (same 40 mV/A, wider temperature range) | can-ssr |
| LTST-C150GKT | Lite-On LTST-C150KGKT | core, serial-card, can-ssr |
| Murata GRM21BR71H104KA01L 100 nF 0805 | KEMET C0805C104K5RACTU | all |
| Murata GRM21BR71H103KA01L 10 nF 0805 | KEMET C0805C103K5RACTU | can-card, serial-card |
| Murata GRM2165C1H270JA01D 27 pF C0G 0805 | KEMET C0805C270J5GACTU | core, can-ssr |
| Murata GRM3195C1H102JA01D 1 nF C0G 1206 | KEMET C1206C102J5GACTU | io-card, can-ssr |
| Murata GRM319R71H104KA01D 100 nF 1206 | KEMET C1206C104K5RACTU | io-card, serial-card |
| Murata GRM31MR71H105KA88L 1 uF 1206 | KEMET C1206C105K5RACTU | core, can-card, serial-card |
| Murata GRM31MR71H474KA01L 470 nF 1206 | KEMET C1206C474K5RACTU | can-ssr |
| TDK C3225X7R2J683K250AA 68 nF 630 V 1210 | KEMET C1210C683KBRACTU | can-ssr |
| Vishay ES1J-E3/61T, ES3J-E3/57T | onsemi ES1J, ES3J | can-ssr |
| Vishay SMAZ15-E3/61 | Diodes Inc SMAZ15-13-F | can-ssr |
| Sullins PRPC040SBAN-M71RC | Amphenol FCI 68016-136HLF | probe-helper |
| SH-7010C | SH-7010MC (orderable part number) | can-ssr |
| Yageo MFR-25FBF52-10M | Stackpole RNF14FTD10M0 | probe-helper |

Out of stock at Mouser on 2026-10-12 (active parts; swapped for in-stock
equivalents, review for rev B whether to keep the swap or go back):

| Was | Now | Boards |
|---|---|---|
| Murata GRM31CR71E106KA12L 10 uF 25 V 1206 | Samsung CL31B106KAHZW6E (CL31B106KAHNNNE was on backorder too) | all but probe-helper |
| Murata GRM31CR71H475KA12L 4.7 uF 50 V 1206 | Samsung CL31B475KBHNNNE | io-card |
| Murata BLM31KN102SN1L | Murata BLM31PG391SN1L (390 Ω @ 100 MHz, 2 A; TI uses 330 Ω; 1 kΩ beads on backorder) | can-card, serial-card |
| Yageo RC1206FR-07330RL | Stackpole RMCF1206FT330R | core, io-card |
| Nexperia BAT54,215 | Diodes Inc BAT54-7-F | can-ssr |
| Nexperia BAT54S,215 | Diodes Inc BAT54S-7-F | io-card |
| TI ISOW1044DFMR (reinforced isolation) | TI ISOW1044BDFMR: same part and pinout, basic isolation; the CAN buses are low-voltage, isolated against ground loops, not for safety | can-card |

Also out of stock then, not changed (no equivalent without a design
change; expected back in stock): ISOW1432DFMR, IPB107N20N3GATMA1,
SUD50P04-08-GE3, MCP1826S-3302E/DB, Phoenix 1844317.

## To do in rev B

- **can-ssr display: replace the MAX7219CWG+** (obsolete and expensive; the
  pin-compatible MAX7221 is obsolete too). Rev A boards are built without
  U40, U41 (display), D40/D41 (V/A LEDs), R50 and C43/C44: no local readout,
  everything else works (readings go over CAN; firmware only writes to the
  driver). Options, decide before the rev B layout:
  - I2C OLED (user's preference, 2026-10-12). The 2026-10-04 decision was
    "no OLED: burn-in on long runs", so it needs burn-in handling in
    firmware: blank after a timeout and wake on a button or a change, and/or
    shift the text a few pixels periodically.
  - Holtek HT16K33 (I2C, active) driving the existing 0.56 in 7-segment
    display and V/A LEDs.
  Either way: schematic, layout and firmware (display.c) change.
- serial-card J20/J21/J30/J31 Amphenol T821110A1R100CEU: not stocked by
  Mouser (bought from DigiKey for rev A). Consider a part Mouser carries;
  re-check the 8.86 mm height against the stack clearance.
- **serial-card RS-485 isolation: split transceiver and isolated power**
  (decided 2026-10-12, plan below: ISO1430DW + SN6505B / Würth 750315371 /
  3.3 V LDO per port). ISOW1432DFMR (transceiver + DC-DC in one TI part) was out
  of stock for rev A; one shortage stops the board.
- **can-card, same problem:** ISOW1044DFMR and ISOW1044BDFMR were both out
  of stock (2026-10-12). The user wants a similar change for CAN; to be
  discussed (board space is the concern: four channels). Likely the same split: TI ISO1042 or ISO1044 isolated CAN FD
  transceiver plus the power block below, except CAN needs a regulated 5 V
  bus side (ISO1042 VCC2 is 4.5-5.5 V), so pick the transformer ratio for
  a 5 V LDO (see the SN6505B datasheet table).

## Plan: serial-card RS-485 isolation (decided 2026-10-12)

Per port (ports 3 and 4 stay isolated from LOGIC and from each other), a
signal isolator/transceiver and a separate isolated supply, each available
from more than one vendor and easy to hand-solder. Requirements unchanged:
half duplex, DE from the core, up to 1 Mbaud (`SER`), fail-safe receiver,
SM712 TVS and 120R jumper, parts under ~11 mm (stack).

### Transceiver (isolated, no integrated power)

| Part | Vendor | Duplex | Rate | Isolation | Package | Bus-side supply |
|---|---|---|---|---|---|---|
| **ISO1430DW** (recommended) | TI | half | 12 Mbps | 5 kVrms (ISO1430B: basic) | SOIC-16 wide | 3.0-5.5 V |
| ADM2486BRWZ (alternate) | ADI | half | 20 Mbps | 2.5 kVrms | SOIC-16 wide | 5 V |

Not usable: ISO1410 and ADM2483 (500 kbps, below `SER`'s 1 Mbaud); ISO1432
and ISO1412 are full duplex. The two candidates are not pin-compatible:
pick one at schematic time (check stock then); the other is the fallback
for a later rev. ISO1430 runs its bus side from 3.0 V, which suits the
supply below.

### Isolated supply

**Recommended: TI SN6505B push-pull transformer driver + Würth 750315371
+ LDO, one set per port.**

- SN6505B (SOT-23-6, 5 V in from the stack +5V) drives a center-tapped
  transformer; two Schottky diodes and a capacitor rectify; an LDO
  regulates.
- Würth 750315371: 1:1.1, 2.5 kVrms, SMD, about 9.3 x 8.3 mm, 4.1 mm tall.
  TI pairs it with the SN6505B. From 5 V it gives about 5 V unregulated,
  too little headroom for a 5 V LDO, so regulate to **3.3 V** (e.g.
  TLV75533P, SOT-23-5) and run the ISO1430 bus side at 3.3 V.
- Every part is a commodity with second sources (other push-pull drivers
  and transformers from Würth, Coilcraft, Bourns), so no single shortage
  stops the board.
- To verify before layout: ISO1430 differential output at VCC2 = 3.3 V
  into 54 ohm (the datasheet spec found was 2.1 V min at 5 V; RS-485 needs
  1.5 V); bus-side load per port (transceiver + driver into terminations,
  well under 100 mA); transformer pinout and footprint from the Würth
  datasheet.

**Alternative: an isolated SMD DC-DC module per port**, e.g. Murata
NXE1S0503MC (5 V to 3.3 V, 1 W, 3 kVDC, about 4.4 mm tall; NXE1S0505MC for
5 V out). One part instead of five, but the output is unregulated (up to
about 13 % load regulation, no-load voltage not specified in what was
found), so check the light-load voltage against the transceiver's 5.5 V
maximum, or add a minimum load. Single source per footprint.

### Layout notes for rev B

- Same keep-out discipline as now: the transceiver's isolation gap and the
  transformer's (or module's) primary/secondary split line up with the
  LOGIC | GND_485_n pour gap; nothing crosses it except those parts.
- SN6505B: input bypass close to VCC, short loops between the driver, the
  transformer primary and the rectifier; see the SN6505B datasheet layout
  section.
- Heights: all parts above are under 5 mm.

Sources: TI ISO14xx datasheet (SLLSF22) and product pages (ISO1410,
ISO1430); ADI ADM2486 datasheet; TI SN6505A/B datasheet (SLLSEP9) and EVM;
Würth 750315371 listings (DigiKey, RS); Murata NXE1 datasheet. Stock was not
checked (Mouser blocks scripted lookups): check SN6505B, ISO1430DW,
750315371 and the LDO before committing the schematic.
