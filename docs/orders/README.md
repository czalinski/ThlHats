# Orders

## Rev A (2026-10-11)

PCBWay: the six `hardware/fab/revA/<board>-revA-gerbers.zip` from
`tools/fab.py` (core, can-card, io-card, serial-card, can-ssr,
probe-helper). Not ordered: pic-module and can-controller (reference only).

DigiKey: `digikey-revA.csv` (upload to the BOM Manager). One set = one of
each of the six boards: 121 lines, 450 parts. Customer Reference gives
board:qty. Multiply for more sets, and round cheap passives up to the next
price break.

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
