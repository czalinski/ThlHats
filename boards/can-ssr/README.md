# CAN SSR

Remote CAN FD node that turns a Mean Well adjustable supply into a simple
automatable DUT supply: high-side switch with reverse blocking, V and I
readback, remote voltage/current programming, auto-off when the host stops repeating its SET (failsafe timeout set by the host in each SET).
Requirements: [`docs/requirements.md`](../../docs/requirements.md), sections
4.2, 4.2.1 (builds and switching) and 4.2.2 (block diagram).

- Board: 100 x 100 mm, 2 layers, rev A (smaller welcome, not required)
- Mounting: stack interface (docs/requirements.md 4.4): 4 x M4 holes on a
  91 x 91 mm square, insulating (glass-filled nylon) 7 mm hex standoffs. Stacks
  up to 4 high on a can-controller, or screws to a DIN base plate on its own.
  No Pi holes, no DIN clips on the board (see board.json).
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

## Indicators and labels

- D4 (green) status, D5 (red) fault: there is no room for silkscreen labels;
  the colours identify them. D40 is the V indicator, D41 the A indicator
  (DIG4 segments A and B of the MAX7219).
- Mean Well connector J30: PV, PC, -V (supply -V / return bar), RC, RC
  (Remote ON/OFF photorelay contact, either polarity).
- One CAN pin legend above J1 covers J1 and J2 (same pinout).

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
| VIN | 1/2" | 111.65-124.35 / 186-199.2 | S+ bolt (H1, x 118); joins the VIN pour under Q1/Q2 |
| Source node | 1/4" | 130-136 / 159-184 | between the Q1/Q2 and Q3/Q4 source pins |
| VOUT_SW | 1/2" | 157-170 / 165-184 | right of the Q3/Q4 tabs; stops short of the ACS770 |
| VOUT | 1/2" | 175.65-188.35 / 171-199.2 | ACS770 output to the L+ bolt (H3, x 182) |
| Return | 1/2" | bottom side, 129.5-169.5 / 186.65-199.35, H2 (x 136) to H4 (x 163) | **not soldered**: clamped by the S- and L- bolts |

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
   S- and L- also clamp the bottom return bar. All four M4 holes take
   **insulating** standoffs only (MH3/MH4 sit in the load area).
8. Check that the MOSFETs fitted in step 1 and the build resistor match the
   intended build (Builds table), and tick the build on the silkscreen.

## Directories

- `hardware/` KiCad project
- `firmware/` firmware sources

## Stack interface rework (2026-10-06)

can-ssr stacks on a can-controller (up to 4 high) or lies side by side in a
1U/2U shelf; see docs/requirements.md 4.2 and 4.4. Done:

- MH1-MH4: `Thl_Mechanical:MountingHole_4.3mm_M4_Standoff7mm` at 4.5 mm from
  each corner. HOLE_KEEPOUT rule areas keep copper 4 mm from the load-side
  holes. A DRC rule lets MH2's standoff circle overlap U40's (empty) courtyard
  corner: U40's pin-24 lead is 4.45 mm from the hole centre, and the hex reaches 4.04 mm.
- Load bolts moved inward: S+ 18, S- 36, L- 63, L+ 82 mm (lug pitch 18 / 27 / 19
  mm, clear of the corner standoffs), with the bar strips, mask openings, the
  return bar (RETBAR), the VIN / RET top / VOUT pours, the S-/L- via rings and
  the labels. The BUILD tick boxes sit between S- and L-.
- Top-right corner: R6/D4 and R7/D5 down 2 mm, R50 and C44 left 0.85/0.8 mm;
  SEG_E, SEG_D, ISET, LED_STATUS, LED_FAULT, UART_RX, two +5V stubs and the
  C44 ground rerouted locally.

- CAN IN and CAN OUT share one double-level header, J1 = Phoenix MCDN 1,5/4-G1-3,5
  P26 THR (1953732), at the stack CAN position: left edge, pin 1 (CANH) at
  y 15.5 mm, pins down at 3.5 mm; pads n and n+4 are linked on the board (the
  +12 V link is 1 mm wide: it carries the supply for the boards further down the
  chain). Footprint `Thl_Connector:PhoenixContact_MCDN_1,5_4-G1-3,5_2x04_P3.5mm_Horizontal`
  from `lib/footprint_src/Thl_Connector/phoenix_mcdn.py`; its STEP is local-only
  (SamacSys licence). Which pin row feeds which plug level was not verified; it
  does not matter electrically, so the silkscreen just says CAN IN/OUT.
- Around it: SW1 right 3.0 mm, D2 into the old J2 space, the pin legend under
  J1; CANH, CANL, CAN_RX, V12_BUS, ADDR0-3, +5V and GND rejoined locally
  (tools/miniroute.py). The scripts that made these changes are in
  `hardware/stack_rework/` for reference (run once; do not rerun).

Still to do:

- Re-check the 12 V draw (estimate about 0.2 A at full display brightness):
  four boards share can-controller CAN1's PTC.
