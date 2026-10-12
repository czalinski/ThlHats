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
- **serial-card RS-485 and can-card CAN isolation: split transceiver and
  isolated power** (decided 2026-10-12, plan below). ISOW1432DFMR,
  ISOW1044DFMR and ISOW1044BDFMR (transceiver + DC-DC in one TI part) were
  all out of stock for the rev A order; one shortage stops a board. Rev A
  can-card and serial-card boards will not be assembled; only parts that
  rev B reuses are bought now (see "Rev A order changes" below).

## Plan: isolated channels (decided 2026-10-12)

Six isolated channels (can-card CAN1-4, serial-card RS-485 ports 3-4), each
isolated from LOGIC and from the others. Every channel gets its own copy of
one **isolated 5 V supply block** and a signal-only isolated transceiver.
All parts are hand-solderable and have second sources. Requirements
unchanged: CAN FD; RS-485 half duplex, DE from the core, up to 1 Mbaud
(`SER`), fail-safe receiver; same TVS, termination jumpers, connectors and
LEDs; parts under ~11 mm (stack).

### Isolated 5 V supply block (same on both cards, per channel)

| Ref | Part | Notes |
|---|---|---|
| U | TI SN6505BDBVR (SOT-23-6) | push-pull transformer driver, 420 kHz, from the stack +5V; EN tied to VCC, CLK to GND |
| C | 10 uF 1206 + 100 nF 0805 | at SN6505B VCC |
| T | Würth 760390014 (1:1.3, 2500 Vrms, 6.73 x 10.05 x 4.19 mm) | TI's recommended part for 5 V -> 5 V, 100 mA with LDO (SN6505B datasheet table 9-3); straddles the isolation gap. Second source: Coilcraft UA8254-AE (1CT:1.3CT, 10 x 6.8 x 4.3 mm; check its pinout, it may need its own footprint) |
| D x2 | onsemi MBR0520LT1G (SOD-123, 20 V 0.5 A Schottky) | full-wave rectifier on the center-tapped secondary; many equivalents |
| C | 10 uF 1206 | rectifier output (about 5.9 V at 80 mA from a 5 V rail) |
| C | 1 uF 1206 | at LDO input |
| U | TI LP2985A-50DBVR (SOT-23-5, 5 V 150 mA, 16 V in) | regulates the bus-side 5 V; EN tied to IN |
| C | 10 nF 0805 | LP2985 BYPASS (noise) |
| C | 10 uF 1206 | LP2985 output (needs >= 2.2 uF) |

Headroom: 5 V x 1.3 = 6.5 V, minus the diode and driver drops, about
5.6-5.9 V into the LDO (dropout about 0.2 V at 80 mA). LDO dissipation
about 0.1 W. Bus-side load per channel: transceiver plus driver into the
terminated bus, under 100 mA.

### CAN channel (can-card, x4)

| Part | Notes |
|---|---|
| **TI ISO1042DWVR** | isolated CAN FD transceiver (5 Mbps), 5 kVrms, 8-pin wide SOIC (DWV); VCC1 1.71-5.5 V from +3V3, VCC2 4.5-5.5 V from the 5 V block. ISO1042BDWVR (basic isolation) is the same part. Other vendor, not pin-compatible: NXP TJA1052i |
| 100 nF 0805 on VCC1, 100 nF 0805 on VCC2 | plus the block's 10 uF output |

Kept from rev A: NUP2105L TVS, 120R + TERM jumper, Phoenix MC 1,5/4
connectors, RX LED + 1k, F10, J10/J11, JP5/JP6, TSW headers.
Space (checked against the rev A layout): per 18 mm channel band, the
transceiver (about 11.5 x 6 mm) and transformer (about 10 x 7 mm) both
straddle the gap at x 40-44 mm; the SN6505B goes in the empty logic-side
area at x 12-21; the rectifier, LDO and capacitors take the bus-side space
the beads and ISOW capacitors used (x 49-66). Connectors, mounting and
outline do not move.

### RS-485 channel (serial-card ports 3-4, x2)

| Part | Notes |
|---|---|
| **TI ISO1430DWR** | isolated RS-485 transceiver, half duplex, 12 Mbps, 5 kVrms, 16-pin wide SOIC; VCC1 from +3V3, VCC2 from the 5 V block (5 V gives the full RS-485 output, 2.1 V min). ISO1430BDWR is the basic-isolation version. Fallback for a later rev (not pin-compatible): ADI ADM2486BRWZ (20 Mbps, 2.5 kVrms) |
| 100 nF 0805 on VCC1, 100 nF 0805 on VCC2 | plus the block's 10 uF output |

~RE tied to DE (as now), 10k RX pull-ups kept. Not usable: ISO1410 and
ADM2483 (500 kbps), ISO1412/ISO1432 (full duplex).
Kept from rev A: SM712 TVS, 120R + TERM jumpers, box headers, LEDs and
resistors, the whole RS-232 section.

Alternative supply (not chosen): an isolated SMD DC-DC module per channel
(Murata NXE1S0505MC, 1 W, 3 kVDC, about 4.4 mm tall). One part, but
unregulated and single source per footprint.

### Layout notes for rev B

- The transceiver's isolation gap and the transformer's primary/secondary
  split line up with the LOGIC | bus-side pour gap; nothing else crosses.
- SN6505B: input bypass at VCC, short loops driver -> primary and
  secondary -> diodes -> capacitor (SN6505B datasheet layout section).
- All new parts are under 5 mm tall.
- To verify at schematic time: stock (ISO1042DWVR, ISO1430DWR, SN6505BDBVR,
  760390014, LP2985A-50DBVR, MBR0520LT1G), the 760390014 pinout and land
  pattern from the Würth datasheet, and a footprint for the DWV package.

## Rev A order changes (can-card and serial-card not built as rev A)

Buy now for rev B (6 isolated channels):

| Part | Qty | For |
|---|---|---|
| TI ISO1042DWVR | 4 | can-card |
| TI ISO1430DWR | 2 | serial-card |
| TI SN6505BDBVR | 6 | both |
| Würth 760390014 | 6 | both |
| onsemi MBR0520LT1G | 12 | both |
| TI LP2985A-50DBVR | 6 | both |

Remove or reduce on the current order list (quantities are the whole
line, all boards):

| Part | Was | Now | Why |
|---|---|---|---|
| ISOW1044BDFMR | 4 | 0 | replaced by ISO1042 |
| ISOW1432DFMR | 2 | 0 | replaced by ISO1430 |
| BLM31PG391SN1L (beads) | 12 | 0 | not needed with the split supply |
| C0805C103K5RACTU 10 nF | 12 | 6 | 2 ISOW caps per channel become 1 LDO bypass |
| C1206C105K5RACTU 1 uF | 14 | 8 | 2 ISOW caps per channel become 1 LDO input |
| C0805C104K5RACTU 100 nF | 56 | 62 | one more per channel (SN6505B VCC) |

10 uF (CL31B106KAHZW6E) stays at 35: three per channel before and after.
Everything else on the can-card and serial-card lines carries into rev B
unchanged.

Sources: TI SN6505A/B datasheet SLLSEP9I (table 9-3); Coilcraft Doc
1666 (SN650x transformers); TI ISO1042 and ISO14xx (SLLSF22) datasheets and
product pages; ADI ADM2486 datasheet; TI LP2985A product data; Murata NXE1
datasheet. Stock was not checked (Mouser blocks scripted lookups).
