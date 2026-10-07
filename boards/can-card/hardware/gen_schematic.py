#!/usr/bin/env python3
"""Bootstrap generator for the can-card schematic (docs/requirements.md 4.1 CAN, 4.5).

Four CAN FD channels, each isolated on its own (TI ISOW1044 with integrated
isolated DC-DC), circuit copied from boards/can-controller/hardware/
gen_schematic.py (can_sheet). Connections to the stack (tools/stack_bus.py):
J10 logic bus (C1-C4 TX/RX, +3V3, +5V, GND) and J11 rack power (+12V,
GND_RACK, only for CAN1's POWERED option). Both are Samtec ESQ stacking
sockets on the top side; KiCad's socket footprint puts pad k on bus pin
stack_bus.socket_pin(k).

Activity LEDs: one per channel from +3V3 through 1k into the ISOW1044 RXD
line (lit while the bus is dominant; RXD echoes the channel's own TX), so no
MCU pins are needed.

Domains: LOGIC (+3V3/+5V/GND from the core), CAN1-CAN4 (each floating:
GND_CANn), RACK (+12V/GND_RACK, at J11, CAN1 POWERED jumpers only).

Writes can-card.kicad_sch from scratch: once the schematic is edited in
KiCad, stop using this script.

  python3 boards/can-card/hardware/gen_schematic.py
"""
import sys
from pathlib import Path

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import schgen  # noqa: E402
import stack_bus as sb  # noqa: E402

FP = schgen.FP
FP_MC4 = "Connector_Phoenix_MC:PhoenixContact_MC_1,5_4-G-3.5_1x04_P3.50mm_Horizontal"
FP_PTC = "Fuse:Fuse_1812_4532Metric_Pad1.30x3.40mm_HandSolder"
FP_JP = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
POWER = {"+3V3", "+5V", "+12V", "GND"}
MPN = {
    "1k": ("Yageo", "RC1206FR-071KL"), "120R": ("Yageo", "RC1206FR-07120RL"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
    "1uF 50V X7R": ("Murata", "GRM31MR71H105KA88L"),
    "10nF 50V X7R": ("Murata", "GRM21BR71H103KA01L"),
}
USED = {"C1TX", "C1RX", "C2TX", "C2RX", "C3TX", "C3RX", "C4TX", "C4RX"} | sb.SUPPLIES


def bus_nets():
    out = {}
    for k in sb.BUS:
        name = sb.BUS[sb.socket_pin(k)]
        out[str(k)] = name if name in USED else "~"
    return out


def build():
    s = schgen.Sheet("can-card", "CAN card: 4 isolated CAN FD", "A", power=POWER, mpn=MPN)
    s.text("CAN card (docs/requirements.md 4.5): four CAN FD channels, each isolated on its own (TI ISOW1044,\n"
           "integrated isolated DC-DC). Logic side: VIO +3V3, VCC1 +5V, GND from the stack bus J10.\n"
           "Bus side n: GND_CANn floats (no assumption about the DUT). Per TI: VISOOUT -> bead -> VISOIN,\n"
           "GND2 -> bead -> bus ground (CISPR 32 class B on 2 layers). Decoupling per TI SLLSFF7B 9.3: 10 nF at VDD\n"
           "and VISOOUT (< 1 mm, 0805 here, TI uses 0402), then 1 uF + 10 uF; 100 nF + 10 uF on VISOIN; 100 nF on VIO.\n"
           "Beads: TI uses 0402 BLM15EX331SN1; this board 1206 BLM31KN102SN1L (hand assembly). Layout: no copper\n"
           "within 4 mm of VISOOUT (12) / GND2 (11) except their own parts. Connector pinout as every ThlHats board:\n"
           "1 CANH, 2 CANL, 3 GND (bus), 4 +12 V cable supply (CAN1 POWERED only; CAN2-4 pin 4 not connected).",
           25.4, 22.86)
    for i in range(4):
        n = i + 1
        y0 = 50.8 + i * 55.88
        x0 = 50.8
        s.text(f"CAN{n}", x0 - 25.4, y0 - 5.08, 2.0)
        nets = {"1": "+3V3", "2": "~", "3": f"C{n}TX", "4": "GND", "5": f"C{n}RX", "6": "GND", "7": "~",
                "8": "~", "9": "+5V", "10": "GND", "11": f"GND2_{n}", "12": f"VISO{n}", "13": f"VISO{n}",
                "14": "~", "15": f"GND_CAN{n}", "16": f"GND_CAN{n}", "17": f"GND_CAN{n}", "18": f"CANL{n}",
                "19": f"CANH{n}", "20": f"VCAN{n}"}
        s.part("Interface_CAN_LIN:ISOW1044", f"U{10 + i}", "ISOW1044", x0 + 60.96, y0 + 12.7, nets, 0,
               "Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm", "Texas Instruments", "ISOW1044DFMR",
               ref_at=(x0 + 66.04, y0 - 7.62), value_at=(x0 + 66.04, y0 + 33.02))
        s.C(f"C{40 + 4 * i}", "100nF 50V X7R", x0 + 12.7, y0 + 30.48, "+3V3", "GND", decouple=True)
        s.C(f"C{41 + 4 * i}", "10uF 25V X7R", x0 + 25.4, y0 + 30.48, "+5V", "GND")
        s.C(f"C{42 + 4 * i}", "10uF 25V X7R", x0 + 99.06, y0 + 30.48, f"VISO{n}", f"GND2_{n}")
        s.C(f"C{43 + 4 * i}", "100nF 50V X7R", x0 + 142.24, y0 + 30.48, f"VCAN{n}", f"GND_CAN{n}", decouple=True)
        # TI SLLSFF7B 9.3/9.4: 10 nF within 1 mm of VDD and VISOOUT, then 1 uF + 10 uF; 10 uF on VISOIN
        s.C(f"C{60 + 5 * i}", "10nF 50V X7R", x0 + 12.7, y0 + 45.72, "+5V", "GND", decouple=True)
        s.C(f"C{61 + 5 * i}", "1uF 50V X7R", x0 + 25.4, y0 + 45.72, "+5V", "GND")
        s.C(f"C{62 + 5 * i}", "10nF 50V X7R", x0 + 86.36, y0 + 45.72, f"VISO{n}", f"GND2_{n}", decouple=True)
        s.C(f"C{63 + 5 * i}", "1uF 50V X7R", x0 + 99.06, y0 + 45.72, f"VISO{n}", f"GND2_{n}")
        s.C(f"C{64 + 5 * i}", "10uF 25V X7R", x0 + 142.24, y0 + 45.72, f"VCAN{n}", f"GND_CAN{n}")
        s.part("Device:FerriteBead", f"FB{10 + 2 * i}", "BLM31KN102SN1L", x0 + 116.84, y0 + 2.54,
               {"1": f"VISO{n}", "2": f"VCAN{n}"}, 90, FP["FB"], "Murata", "BLM31KN102SN1L",
               ref_at=(x0 + 116.84, y0 - 1.27), value_at=(x0 + 116.84, y0 + 6.35))
        s.part("Device:FerriteBead", f"FB{11 + 2 * i}", "BLM31KN102SN1L", x0 + 116.84, y0 + 15.24,
               {"1": f"GND2_{n}", "2": f"GND_CAN{n}"}, 90, FP["FB"], "Murata", "BLM31KN102SN1L",
               ref_at=(x0 + 116.84, y0 + 11.43), value_at=(x0 + 116.84, y0 + 19.05))
        s.flag(x0 + 129.54, y0 - 2.54); s.llabel(f"VCAN{n}", x0 + 129.54, y0 - 2.54, 0)
        s.flag(x0 + 129.54, y0 + 22.86); s.llabel(f"GND_CAN{n}", x0 + 129.54, y0 + 22.86, 0)
        s.part("Power_Protection:NUP2105L", f"D{10 + i}", "NUP2105L", x0 + 167.64, y0 + 12.7,
               {"1": f"CANH{n}", "2": f"CANL{n}", "3": f"GND_CAN{n}"}, 0, FP["SOT23"], "onsemi", "NUP2105LT1G",
               ref_at=(x0 + 172.72, y0 + 8.89), value_at=(x0 + 172.72, y0 + 16.51))
        s.part("Jumper:Jumper_2_Open", f"JP{1 + i}", "TERM", x0 + 190.5, y0 + 2.54,
               {"1": f"CANH{n}", "2": f"TERM{n}"}, 0, FP_JP, "Samtec", "TSW-102-07-G-S",
               ref_at=(x0 + 190.5, y0 - 1.27), value_at=(x0 + 190.5, y0 + 6.35))
        s.R(f"R{30 + i}", "120R", x0 + 205.74, y0 + 12.7, f"TERM{n}", f"CANL{n}")
        pin4 = "V12_CAN1" if n == 1 else "~"
        s.part("Connector:Screw_Terminal_01x04", f"J{20 + n}", f"CAN{n}", x0 + 254.0, y0 + 12.7,
               {"1": f"CANH{n}", "2": f"CANL{n}", "3": f"GND_CAN{n}", "4": pin4}, 0, FP_MC4,
               "Phoenix Contact", "1844236", ref_at=(x0 + 254.0, y0 + 5.08), value_at=(x0 + 254.0, y0 + 21.59))
        s.led_chain(f"D{20 + i}", f"R{34 + i}", "yellow", "LTST-C150YKT", x0 - 12.7, y0 + 7.62, "+3V3",
                    ground=f"C{n}RX")
    # CAN1 powered-bus option
    s.part("Jumper:Jumper_2_Open", "JP5", "POWERED GND", 381.0, 66.04, {"1": "GND_CAN1", "2": "GND_RACK"}, 0,
           FP_JP, "Samtec", "TSW-102-07-G-S", ref_at=(381.0, 62.23), value_at=(381.0, 69.85))
    s.part("Device:Polyfuse", "F10", "2A", 355.6, 45.72, {"1": "+12V", "2": "V12_F10"}, 90, FP_PTC,
           "Bourns", "MF-MSMF200/16X-2", ref_at=(355.6, 41.91), value_at=(355.6, 49.53))
    s.part("Jumper:Jumper_2_Open", "JP6", "POWERED 12V", 381.0, 45.72, {"1": "V12_F10", "2": "V12_CAN1"}, 0,
           FP_JP, "Samtec", "TSW-102-07-G-S", ref_at=(381.0, 41.91), value_at=(381.0, 49.53))
    s.text("CAN1 POWERED: fit JP5 + JP6 together on the can-ssr bus\n"
           "(up to 4 can-ssr at ~0.2 A each; F10 2 A hold).\n"
           "F10 and JP5/JP6 sit at the RACK | CAN1 boundary on the board.", 340.36, 78.74, 1.0)
    s.text("JP1-JP4: fit the shunt (Samtec SNT-100-BK-G) only where this card is a bus end.\n"
           "D20-D23: CAN activity (lit while RXD is low = bus dominant; RXD echoes our own TX).", 25.4, 271.78, 1.0)
    # stack connectors
    s.part("Connector_Generic:Conn_02x20_Odd_Even", "J10", "STACK BUS", 355.6, 165.1, bus_nets(), 0,
           "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical", "Samtec", "ESQ-120-14-G-D",
           ref_at=(356.87, 137.16), value_at=(356.87, 193.04))
    pwr = {str(k): sb.PWR12[sb.socket_pin(k)] for k in sb.PWR12}
    s.part("Connector_Generic:Conn_02x03_Odd_Even", "J11", "RACK 12V", 355.6, 223.52, pwr, 0,
           "Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical", "Samtec", "ESQ-103-14-G-D",
           ref_at=(356.87, 215.9), value_at=(356.87, 231.14))
    s.flag(381.0, 213.36, 180); s.llabel("GND_RACK", 381.0, 213.36, 0)
    # supplies come from the core through J10/J11
    for i, name in enumerate(("+3V3", "+5V", "+12V")):
        x = 330.2 + 12.7 * i
        s.flag(x, 129.54); s.power(name, x, 129.54)
    s.flag(368.3, 129.54, 180); s.power("GND", 368.3, 129.54)
    s.text("J10/J11: Samtec ESQ stacking sockets (top side, tails through to the card below). Pad k carries\n"
           "bus pin stack_bus.socket_pin(k) (KiCad socket footprint columns are mirrored). Signals this card\n"
           "does not use pass through the connector itself.", 325.12, 241.3, 1.0)
    return s


def main():
    (HW / "can-card.kicad_sch").write_text(build().render())
    print("wrote can-card.kicad_sch")


if __name__ == "__main__":
    main()
