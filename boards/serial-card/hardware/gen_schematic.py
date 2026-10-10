#!/usr/bin/env python3
"""Bootstrap generator for the serial-card schematic (docs/requirements.md 4.5).

Four serial ports driven by the core's PIC32MK UARTs through the stack bus
(tools/stack_bus.py); port numbers as in boards/core/firmware/src/serial.h:

  Port 1, 2  RS-232 (U2, U3): one ST3232B (2 drivers + 2 receivers) on +3V3,
             referenced to the LOGIC ground (not isolated, decided 2026-10-09).
  Port 3, 4  RS-485 half duplex (U4 + DE1, U5 + DE2): TI ISOW1432, isolated
             with integrated DC-DC, each bus side floating (GND_485n). The
             full-duplex part runs half duplex with Y-A and Z-B tied on the
             PCB (SLLSF86D 8.1); ~RE tied to DE so the port does not hear its
             own echo; 10k holds R high while the receiver is off.

Connectors: right-angle shrouded 2x5 box headers (Amphenol T821110A1R100CEU,
low enough for the stack) in the common IDC10-to-DB9 order (header pin n ->
DB9 1, 6, 2, 7, 3, 8, 4, 9, 5, -), so a standard IDC ribbon DB9 cable or a
small adapter PCB gives a DB9: male for RS-232 (DTE: 2 RXD in, 3 TXD out,
5 GND), female for RS-485 (Profibus convention: 3 D+, 8 D-, 5 GND).

Domains: LOGIC (+3V3/+5V/GND from the core), RS485_3 and RS485_4 (floating).
J11 (rack power) only passes through.

Writes serial-card.kicad_sch from scratch: once the schematic is edited in
KiCad, stop using this script.

  python3 boards/serial-card/hardware/gen_schematic.py
"""
import sys
from pathlib import Path

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import schgen  # noqa: E402
import stack_bus as sb  # noqa: E402

FP = schgen.FP
FP_IDC = "Connector_IDC:IDC-Header_2x05_P2.54mm_Horizontal"
FP_JP = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
POWER = {"+3V3", "+5V", "GND"}
MPN = {
    "1k": ("Yageo", "RC1206FR-071KL"), "10k": ("Yageo", "RC1206FR-0710KL"), "120R": ("Yageo", "RC1206FR-07120RL"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),          # 0805, decoupling
    "100nF 50V X7R 1206": ("Murata", "GRM319R71H104KA01D"),     # 1206, charge pump
    "10nF 50V X7R": ("Murata", "GRM21BR71H103KA01L"),
    "1uF 50V X7R": ("Murata", "GRM31MR71H105KA88L"),
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
}
USED = {"U2TX", "U2RX", "U3TX", "U3RX", "U4TX", "U4RX", "U5TX", "U5RX", "DE1", "DE2"} | {"+3V3", "+5V", "GND"}
# box header pin -> DB9 pin (IDC10-to-DB9 ribbon, the common "AT" order)
IDC_DB9 = {1: 1, 2: 6, 3: 2, 4: 7, 5: 3, 6: 8, 7: 4, 8: 9, 9: 5, 10: None}


def bus_nets():
    out = {}
    for k in sb.BUS:
        name = sb.BUS[sb.socket_pin(k)]
        out[str(k)] = name if name in USED else "~"
    return out


def header(db9):
    """box header nets from {DB9 pin: net}; unused pins no-connect"""
    return {str(p): db9.get(d, "~") if d else "~" for p, d in IDC_DB9.items()}


def rs232(s):
    s.text("RS-232 ports 1 and 2 (UART2, UART3): ST3232B, 3.3 V, +-15 kV ESD on the bus pins, not isolated\n"
           "(decided 2026-10-09). 3-wire: DB9 2 RXD (in), 3 TXD (out), 5 GND (DTE, male DB9 on the adapter).\n"
           "No handshake lines: a device that needs them gets them looped in its cable.", 25.4, 22.86)
    s.part("Interface_UART:MAX232", "U1", "ST3232B", 101.6, 76.2,
           {"1": "C1P", "3": "C1N", "4": "C2P", "5": "C2N", "2": "VSP", "6": "VSN",
            "11": "U2TX", "14": "TXD1", "12": "U2RX", "13": "RXD1",
            "10": "U3TX", "7": "TXD2", "9": "U3RX", "8": "RXD2", "16": "+3V3", "15": "GND"}, 0,
           "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", "STMicroelectronics", "ST3232BDR",
           ref_at=(101.6, 45.72), value_at=(101.6, 106.68))
    s.text("U1: MAX3232-compatible pinout (symbol MAX232).", 83.82, 111.76, 1.0)
    s.C("C1", "100nF 50V X7R 1206", 45.72, 60.96, "C1P", "C1N")
    s.C("C2", "100nF 50V X7R 1206", 66.04, 60.96, "C2P", "C2N")
    s.C("C3", "100nF 50V X7R 1206", 45.72, 83.82, "VSP", "GND")
    s.C("C4", "100nF 50V X7R 1206", 66.04, 83.82, "VSN", "GND")
    s.C("C5", "100nF 50V X7R", 124.46, 35.56, "+3V3", "GND", decouple=True)
    for k, (j, tx, rx) in enumerate((("J20", "TXD1", "RXD1"), ("J21", "TXD2", "RXD2"))):
        y = 63.5 + k * 35.56
        s.part("Connector_Generic:Conn_02x05_Odd_Even", j, f"RS-232 {k + 1}", 165.1, y,
               header({2: rx, 3: tx, 5: "GND"}), 0, FP_IDC, "Amphenol", "T821110A1R100CEU",
               ref_at=(166.37, y - 10.16), value_at=(166.37, y + 10.16))
    s.text("J20/J21: right-angle 2x5 box headers; pin 3 = DB9-2 RXD, 5 = DB9-3 TXD, 9 = DB9-5 GND.",
           139.7, 132.08, 1.0)


def rs485(s, i):
    n = 3 + i                           # port number
    u, de = f"U{4 + i}", f"DE{1 + i}"   # UART4/DE1, UART5/DE2
    y0 = 139.7 + i * 76.2
    x0 = 50.8
    s.text(f"RS-485 PORT {n} ({u}, {de}): isolated, half duplex", x0 - 25.4, y0 - 7.62, 2.0)
    nets = {"1": "+3V3", "9": "+5V", "2": f"{u}TX", "3": de, "5": de, "4": f"{u}RX", "6": "GND", "10": "GND",
            "8": "+3V3", "7": "~", "12": f"VISO{n}", "16": f"V485_{n}", "20": f"DP{n}", "17": f"DP{n}",
            "19": f"DN{n}", "18": f"DN{n}", "13": f"VISO{n}", "14": f"GND_485_{n}", "11": f"GND2_{n}",
            "15": f"GND_485_{n}"}
    s.part("Thl_Interface:ISOW1432", f"U{10 + i}", "ISOW1432", x0 + 63.5, y0 + 20.32, nets, 0,
           "Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm", "Texas Instruments", "ISOW1432DFMR",
           ref_at=(x0 + 63.5, y0 - 2.54), value_at=(x0 + 63.5, y0 + 45.72))
    s.R(f"R{20 + i}", "10k", x0 + 7.62, y0 + 17.78, "+3V3", f"{u}RX")
    # logic side: VIO 100 nF; VDD 10 nF (< 1 mm), 1 uF, 10 uF (SLLSF86D 9.2, 9.4)
    s.C(f"C{20 + 10 * i}", "100nF 50V X7R", x0 + 0.0, y0 + 50.8, "+3V3", "GND", decouple=True)
    s.C(f"C{21 + 10 * i}", "10nF 50V X7R", x0 + 17.78, y0 + 50.8, "+5V", "GND", decouple=True)
    s.C(f"C{22 + 10 * i}", "1uF 50V X7R", x0 + 35.56, y0 + 50.8, "+5V", "GND")
    s.C(f"C{23 + 10 * i}", "10uF 25V X7R", x0 + 53.34, y0 + 50.8, "+5V", "GND")
    # bus side: VISOOUT 10 nF, 1 uF, 10 uF to GND2; beads to VISOIN / GISOIN; VISOIN 100 nF + 10 uF
    s.C(f"C{24 + 10 * i}", "10nF 50V X7R", x0 + 76.2, y0 + 50.8, f"VISO{n}", f"GND2_{n}", decouple=True)
    s.C(f"C{25 + 10 * i}", "1uF 50V X7R", x0 + 93.98, y0 + 50.8, f"VISO{n}", f"GND2_{n}")
    s.C(f"C{26 + 10 * i}", "10uF 25V X7R", x0 + 111.76, y0 + 50.8, f"VISO{n}", f"GND2_{n}")
    s.part("Device:FerriteBead", f"FB{10 + 2 * i}", "BLM31KN102SN1L", x0 + 127.0, y0 + 2.54,
           {"1": f"VISO{n}", "2": f"V485_{n}"}, 90, FP["FB"], "Murata", "BLM31KN102SN1L",
           ref_at=(x0 + 127.0, y0 - 1.27), value_at=(x0 + 127.0, y0 + 6.35))
    s.part("Device:FerriteBead", f"FB{11 + 2 * i}", "BLM31KN102SN1L", x0 + 127.0, y0 + 15.24,
           {"1": f"GND2_{n}", "2": f"GND_485_{n}"}, 90, FP["FB"], "Murata", "BLM31KN102SN1L",
           ref_at=(x0 + 127.0, y0 + 11.43), value_at=(x0 + 127.0, y0 + 19.05))
    s.C(f"C{27 + 10 * i}", "100nF 50V X7R", x0 + 129.54, y0 + 50.8, f"V485_{n}", f"GND_485_{n}", decouple=True)
    s.C(f"C{28 + 10 * i}", "10uF 25V X7R", x0 + 147.32, y0 + 50.8, f"V485_{n}", f"GND_485_{n}")
    s.flag(x0 + 139.7, y0 - 2.54); s.llabel(f"V485_{n}", x0 + 139.7, y0 - 2.54, 0)
    s.flag(x0 + 139.7, y0 + 22.86); s.llabel(f"GND_485_{n}", x0 + 139.7, y0 + 22.86, 0)
    s.part("Diode:SM712_SOT23", f"D{10 + i}", "SM712", x0 + 172.72, y0 + 20.32,
           {"1": f"DP{n}", "2": f"DN{n}", "3": f"GND_485_{n}"}, 0, FP["SOT23"], "Semtech", "SM712.TCT",
           ref_at=(x0 + 177.8, y0 + 16.51), value_at=(x0 + 177.8, y0 + 24.13))
    s.part("Jumper:Jumper_2_Open", f"JP{1 + i}", "TERM", x0 + 195.58, y0 + 7.62,
           {"1": f"DP{n}", "2": f"TERM{n}"}, 0, FP_JP, "Samtec", "TSW-102-07-G-S",
           ref_at=(x0 + 195.58, y0 + 3.81), value_at=(x0 + 195.58, y0 + 11.43))
    s.R(f"R{30 + i}", "120R", x0 + 210.82, y0 + 17.78, f"TERM{n}", f"DN{n}")
    s.part("Connector_Generic:Conn_02x05_Odd_Even", f"J{30 + i}", f"RS-485 {n}", x0 + 246.38, y0 + 20.32,
           header({3: f"DP{n}", 8: f"DN{n}", 5: f"GND_485_{n}"}), 0, FP_IDC, "Amphenol", "T821110A1R100CEU",
           ref_at=(x0 + 247.65, y0 + 10.16), value_at=(x0 + 247.65, y0 + 30.48))
    s.text(f"J{30 + i}: pin 5 = DB9-3 D+ (TI A/Y), 6 = DB9-8 D- (TI B/Z), 9 = DB9-5 GND_485_{n}.\n"
           f"JP{1 + i}: 120R termination, fit only at a bus end. U{10 + i}: MODE = VISOOUT (5 V bus side,\n"
           "VDD from +5V); no copper within 4 mm of pins 11/12 except their own parts (SLLSF86D 9.4.1).",
           x0 + 172.72, y0 + 38.1, 1.0)


def leds(s):
    s.text("ACTIVITY LEDs: +3V3 -> 1k -> LED -> UART line, lit while the line is low (start bit / data).",
           228.6, 22.86, 1.0)
    lines = ("U2TX", "U2RX", "U3TX", "U3RX", "U4TX", "U4RX", "U5TX", "U5RX")
    for k, net in enumerate(lines):
        x = 233.68 + (k % 4) * 15.24
        y = 33.02 + (k // 4) * 27.94
        colour, mpn = ("green", "LTST-C150GKT") if net.endswith("TX") else ("yellow", "LTST-C150YKT")
        s.led_chain(f"D{1 + k}", f"R{1 + k}", colour, mpn, x, y, "+3V3", ground=net)


def stack(s):
    s.part("Connector_Generic:Conn_02x20_Odd_Even", "J10", "STACK BUS", 368.3, 101.6, bus_nets(), 0,
           "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical", "Samtec", "ESQ-120-14-G-D",
           ref_at=(369.57, 73.66), value_at=(369.57, 129.54))
    s.part("Connector_Generic:Conn_02x03_Odd_Even", "J11", "RACK 12V", 368.3, 162.56,
           {str(k): "~" for k in sb.PWR12}, 0,
           "Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical", "Samtec", "ESQ-103-14-G-D",
           ref_at=(369.57, 154.94), value_at=(369.57, 170.18))
    for i, name in enumerate(("+3V3", "+5V")):
        x = 337.82 + 17.78 * i
        s.flag(x, 63.5); s.power(name, x, 63.5)
    s.flag(391.16, 63.5, 180); s.power("GND", 391.16, 63.5)
    s.C("C6", "10uF 25V X7R", 342.9, 190.5, "+3V3", "GND")
    s.C("C7", "10uF 25V X7R", 363.22, 190.5, "+5V", "GND")
    s.text("J10/J11: Samtec ESQ stacking sockets (top side, tails through to the card below). Pad k carries\n"
           "bus pin stack_bus.socket_pin(k). J11 (+12V / GND_RACK) only passes through this card.",
           330.2, 205.74, 1.0)


def build():
    s = schgen.Sheet("serial-card", "Serial card: 2 x RS-232, 2 x isolated RS-485", "A", power=POWER, mpn=MPN)
    rs232(s)
    rs485(s, 0)
    rs485(s, 1)
    leds(s)
    stack(s)
    return s


def main():
    (HW / "serial-card.kicad_sch").write_text(build().render())
    print("wrote serial-card.kicad_sch")


if __name__ == "__main__":
    main()
