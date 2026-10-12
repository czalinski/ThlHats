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
| Murata GRM31CR71E106KA12L 10 uF 25 V 1206 | Samsung CL31B106KAHNNNE | all but probe-helper |
| Murata GRM31CR71H475KA12L 4.7 uF 50 V 1206 | Samsung CL31B475KBHNNNE | io-card |
| Murata BLM31KN102SN1L | Murata BLM31KN102SH1L (AEC-Q200 grade, same bead) | can-card, serial-card |
| Yageo RC1206FR-07330RL | Stackpole RMCF1206FT330R | core, io-card |
| Nexperia BAT54,215 | Diodes Inc BAT54-7-F | can-ssr |
| Nexperia BAT54S,215 | Diodes Inc BAT54S-7-F | io-card |

Also out of stock then, not changed (no equivalent without a design
change; expected back in stock): ISOW1044DFMR, ISOW1432DFMR, IPB107N20N3GATMA1,
SUD50P04-08-GE3, MCP1826S-3302E/DB, Phoenix 1844317.

## To do in rev B

- **can-ssr U40 MAX7219CWG+ is obsolete** (the pin-compatible MAX7221 is too).
  Rev A uses remaining stock. Choose a current display driver; this needs a
  schematic and layout change.
- serial-card J20/J21/J30/J31 Amphenol T821110A1R100CEU: not stocked by
  Mouser (bought from DigiKey for rev A). Consider a part Mouser carries;
  re-check the 8.86 mm height against the stack clearance.
