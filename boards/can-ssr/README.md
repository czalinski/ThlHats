# CAN SSR

Remote CAN FD node that turns a Mean Well adjustable supply into a simple
automatable DUT supply: high-side switch with reverse blocking, V and I
readback, remote voltage/current programming, auto-off on lost heartbeat.
Requirements: [`docs/requirements.md`](../../docs/requirements.md), sections
4.2, 4.2.1 (builds and switching) and 4.2.2 (block diagram).

- Board: 100 x 100 mm, 2 layers, rev A (smaller welcome, not required)
- Mounting: 4 x M3 to a separate DIN-rail mounting plate (no Pi holes, no DIN
  clips on the board; see board.json). Load-side holes MH3/MH4 (by the S+ and L+ bolts) take nylon standoffs and screws; the plate is non-conductive.
- Off the Pi header; powered from the 4-wire CAN cable (12 V)
- MCU: PIC18F47Q84-I/PT (TQFP-44), on the CAN/logic side

## Builds (one PCB, one firmware image)

| Build | MOSFETs (4 x D2PAK) | Max supply | Continuous |
|-------|---------------------|------------|------------|
| HC  | IPB021N10NM5LF2 | 60 V  | 50 A |
| STD | IPB110N20N3LF   | 150 V | 25 A |
| HV  | IPB407N30N      | 200 V | 12 A (sequenced turn-on only) |

The only other difference is the **build resistor**, which sets the hardware
overcurrent trip threshold and is read by the PIC as the build ID.

## Functional blocks

| Block | Baseline parts | Domain |
|-------|----------------|--------|
| CAN, power, MCU | CAN FD transceiver, 12 V to 5 V buck, PIC18F47Q84-I/PT, address switch, termination jumper | CAN/logic |
| Display | MAX7219, 4-digit 7-segment LED, V/A indicators | CAN/logic |
| Overcurrent trip | Comparator + latch on the ACS770 output, threshold from the build resistor | CAN/logic |
| Barrier | 2 x VOM1271T, ACS770ECB-100U, ISO1640 I2C isolator, isolated DC-DC, photorelay | crosses |
| Power path | 4 x MOSFET (two per side, common source), gate network with slew C, freewheel diode, busbars, 4 bolts | load |
| Sense and programming | Vin/Vout dividers (~42 Hz RC), 2 x MCP3426 ADC (240 SPS each), 2 x MCP4725 DAC (Mean Well PV, PC), TLP222A remote on/off | load |

## Layout rules

- Busbar runs are mask-free top copper; four bolted ring-lug connections
  (supply +/-, load +/-).
- 250 V working clearances; about 6 mm creepage between the load side and the
  CAN/logic side. No copper pour joins the domains.

## Fabrication

- PCBWay, 2 layers, 1.6 mm. **Production boards: 2 oz outer copper**
  (decided 2026-10-05; the extra board cost is less than the extra labour
  of adding more busbar). Prototypes may use 1 oz.
- Why: the VIN bar ends beside Q2. Q1's drain tab reaches it only through
  about 15-25 mm of board copper (about 19 mm wide). With 1 oz that path is about
  0.5 mOhm: about 0.3 W at 50 A (HC build), and Q2 carries about 55 % of the
  current. 2 oz halves both. The 12 A (HV) and 25 A (STD) builds hardly notice.

## Assembly

Busbars: C110 copper flat bar, 3.2 mm (1/8") thick. VIN, VOUT_SW and VOUT are
12.7 mm (1/2") wide; the source node is 6.35 mm (1/4"). Each solders onto a
strip of mask-free top copper:

| Bar | Width | Strip (board mm, x / y) | Next to |
|-----|-------|------------------------|---------|
| VIN | 1/2" | 101-113.5 / 184-199 | S+ bolt (H1); ends beside Q2's tab |
| Source node | 1/4" | 130-136 / 159-184 | between the Q1/Q2 and Q3/Q4 source pins |
| VOUT_SW | 1/2" | 157-170 / 165-184 | right of the Q3/Q4 tabs; stops short of the ACS770 |
| VOUT | 1/2" | 180-192 / 171-199 | ACS770 output to the L+ bolt (H3) |
| Return | 1/2" | bottom side, H2 to H4 | **not soldered**: clamped by the S- and L- bolts |

The bars sit beside the MOSFETs, not over them (D2PAK body 4.4 mm, bar
3.2 mm). The D2PAK drain tab is the solder joint and is almost entirely under
the package on solid copper, so it cannot be soldered with an iron alone. Build
the power section on a hot plate **before** any bottom-side parts are fitted.
The load side has many bottom parts (C10, C32, C33, C35, C37, C38, C40, C41,
D10-D13, Q5, R10-R15, R32-R47, U33, U34), and they would otherwise sit on the plate.

1. **Power section, bare board on a hot plate.** Paste the Q1-Q4 tab and pin
   pads. Place Q1-Q4, then reflow (preheat about 150 °C,
   then up to reflow). Either paste the bar strips and reflow the bars in the same
   pass, or tin the strips now and sweat the bars on afterwards with the board
   on the plate and a 100 W+ iron. Keep the bars square to their strips and
   clear of the ACS770 leads.
2. Let the board cool. Inspect the tab fillets at the exposed tab edge and touch up
   the gate/source pins with an iron.
3. **D13** (freewheel diode, SMC, bottom side): its anode pad is in the solid
   bottom return plane. Solder it first among the bottom parts, using hot air or
   a large tip with the board preheated.
4. **Bottom side** (iron): the other load-side parts listed above, then the trip
   cluster under the display (U20, Q20-Q24, R20-R29, C20-C23, D20).
5. **Top side** (iron): logic side and load-side sense parts. The ground pours connect
   pads solid (no thermal reliefs). Use a large tip, or preheat, on through-hole
   parts in the plane (U1, U2, U35, SW1, J1-J4, J30).
6. **ACS770 (U12)**: through-hole; solder last of the power parts with a large
   tip. Its leads sit on the VOUT_SW and VOUT copper.
7. **Bolts and lugs**: M5 through bar, board and ring lug, all lugs on top.
   S- and L- also clamp the bottom return bar. MH3/MH4 (by S+ and L+) take
   **nylon** standoffs and screws only.
8. Check that the MOSFETs fitted in step 1 and the build resistor match the
   intended build (Builds table), and tick the build on the silkscreen.

## Directories

- `hardware/` KiCad project
- `firmware/` firmware sources
