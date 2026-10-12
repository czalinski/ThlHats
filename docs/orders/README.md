# Orders

## Rev A (2026-10-11)

PCBWay: the six `hardware/fab/revA/<board>-revA-gerbers.zip` from
`tools/fab.py` (core, can-card, io-card, serial-card, can-ssr,
probe-helper). Not ordered: pic-module and can-controller (reference only).

Order lists are generated from the boards' PCBs (MPN, Manufacturer and
Value fields) by `tools/order_bom.py --rev A`; edit the parts in the
schematics, update the PCB, and rerun rather than editing the lists.

DigiKey: `digikey-revA.csv` (upload to the BOM Manager). One set = one of
each of the six boards: 121 lines, 450 parts. Customer Reference gives
board:qty. Multiply for more sets, and round cheap passives up to the next
price break.

Mouser: `mouser-revA.xlsx` (upload to the BOM tool; `mouser-revA.csv` has
the same rows for review). Columns follow Mouser's BOM template
(`MouserBomTemplate.xls`): Mfr Part Number, Mouser Part Number,
Manufacturer Name, Description, Quantity 1 and Order Quantity are filled.
`mouser-revA-simple.xlsx` has the same lines in five columns only (Mouser
Part Number, Manufacturer Part Number, Manufacturer, Quantity, Description)
for an easier column mapping on upload.
Mouser part numbers come from `tools/mouser_pn.csv`, taken from Mouser's own
BOM check; parts added since have none yet, so Mouser matches them by MPN.
Mouser spells W6100-L as W6100L. The four Amphenol T821110A1R100CEU box
headers (serial-card J20/J21/J30/J31) are left out: Mouser does not stock
them, buy from DigiKey. The Description ends in a short board:qty code:
CO core, CC can-card, IO io-card, SE serial-card, SS can-ssr,
PH probe-helper.

Both lists carry the 2026-10-12 substitutions for obsolete, unorderable and
out-of-stock parts (docs/rev-b-changes.md), so they no longer match the
`revA` tag's schematics part for part; the footprints are unchanged.
Not bought for rev A (`NOT_FITTED` in tools/order_bom.py): the can-ssr
display, U40 (MAX7219, obsolete and expensive), U41, D40/D41, R50, C43/C44.

Not in the board BOMs (order separately):

| Qty / set | Item | For |
|---|---|---|
| 1 | Phoenix MSTB 2,5/2-ST-5,08 plug | core J20 (12 V in) |
| 6 | Phoenix MC 1,5/4-ST-3,5 plug (1840382) | can-card J21-J24, can-ssr J1 (two levels) |
| 1 | Phoenix MC 1,5/5-ST-3,5 plug | can-ssr J30 (Mean Well) |
| 1 each | Phoenix FMC 1,5/8-ST-3,5, FMC 1,5/10-ST-3,5, FMC 1,5/12-ST-3,5 push-in plugs | io-card J50, J30, J40 |
| 10 | 2.54 mm jumper shunts | can-card JP1-6, io-card JP1, serial-card JP1-2, can-ssr JP1 |
| 4 | IDC10-to-DB9 ribbon cables (or the DB9 adapter PCB, not designed) | serial-card J20/J21/J30/J31 |
| 2 + cable | 10-way IDC sockets, 10-way 1.27 mm ribbon, about 15 cm | probe-helper J2 to Pi pins 31-40 |
| 2 + 2 | M2.5 spacers about 4 mm + standoffs about 16.6 mm, washers | probe-helper |
| 4 per board | M4 insulating hex standoffs (stack, docs/requirements.md 4.4) | core stack, can-ssr |
| | busbars (C110, 3.2 mm), M5 bolts, ring lugs (boards/can-ssr/README.md) | can-ssr |

Assembly: trim through-hole solder tails under the core and every card to
about 1.5 mm. The serial-card's box headers are 8.86 mm tall, which leaves
2.3 mm under the next board (boards/serial-card/README.md).
