#!/usr/bin/env python3
"""Bootstrap generator for the core board schematic (docs/requirements.md 4.0, 4.5).

Core of the daughter-card stack: PIC32MK1024MCM064, the 12 V power entry and
isolated logic supply, Ethernet (W6100), and the two stack connectors:
J10 logic bus (2 x 20) and J11 rack power (2 x 3), both from tools/stack_bus.py.
Circuits copied from boards/pic-module (MCU, power) and boards/can-controller
(Ethernet, VMID reference).

Sheets: power, MCU, Ethernet, stack. Nets named "/X" are global labels shared
between sheets; bus signals keep their stack_bus names. Domains: RACK (+12V,
GND_RACK) and LOGIC (+5V, +3V3, GND, floating), crossed only by U20.

Writes core.kicad_sch and the sub-sheets from scratch: once the schematic is
edited in KiCad, stop using this script.

  python3 boards/core/hardware/gen_schematic.py
"""
import re
import sys
from pathlib import Path

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import schgen  # noqa: E402
import stack_bus as sb  # noqa: E402

PROJECT = "core"
ROOT_UUID = re.search(r'\(uuid "([^"]+)"\)', (HW / "core.kicad_sch").read_text()).group(1)
REV = "A"
FP = schgen.FP
POWER = {"+3V3", "+5V", "+12V", "GND"}
MPN = {
    "10k": ("Yageo", "RC1206FR-0710KL"), "1k": ("Yageo", "RC1206FR-071KL"), "4.7k": ("Yageo", "RC1206FR-074K7L"),
    "330R": ("Yageo", "RC1206FR-07330RL"), "49.9R": ("Yageo", "RC1206FR-0749R9L"), "12k": ("Yageo", "RC1206FR-0712KL"),
    "300R": ("Yageo", "RC1206FR-07300RL"), "0R": ("Yageo", "RC1206JR-070RL"), "1M": ("Yageo", "RC1206FR-071ML"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
    "1uF 50V X7R": ("Murata", "GRM31MR71H105KA88L"),
    "27pF 50V C0G": ("Murata", "GRM2165C1H270JA01D"),
    "8pF 50V C0G": ("TBD", "TBD (8 pF 50 V C0G 0805, to suit the 25 MHz crystal)"),
    "3.3uF 25V X7R": ("TBD", "TBD (3.3 uF 25 V X7R 1206)"),
    "1nF 2kV X7R": ("KEMET", "C1206C102KGRACTU"),
}


def sheet(file, name, page, title):
    return schgen.SubSheet(PROJECT, ROOT_UUID, file, name, page, title, REV, power=POWER, mpn=MPN)


def g(net):
    """Bus/inter-sheet nets as global labels; supplies stay power symbols."""
    return net if net in POWER else "/" + net


# ------------------------------------------------------------------ power

def power_sheet():
    s = sheet("power.kicad_sch", "12 V input, logic supply", 2, "Core: 12 V input and isolated logic supply")
    s.text("RACK DOMAIN: external 12 V DIN supply; its 0 V is GND_RACK. Reverse polarity: P-FET Q1 (D30 clamps Vgs).\n"
           "Transients: TVS D31. Fuse F20. +12V/GND_RACK go up the stack on J11 (stack sheet).\n"
           "U20 (TRACO TDN 5-2411WI, 9-36 V in, 5 V 1 A, 1600 VDC) makes the floating LOGIC +5V / GND.", 25.4, 20.32)
    s.part("Connector:Screw_Terminal_01x02", "J20", "12V IN", 30.48, 55.88, {"1": "V12_IN", "2": "/GND_RACK"}, 0,
           "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_2-G-5,08_1x02_P5.08mm_Horizontal", "Phoenix Contact",
           "1757242", ref_at=(30.48, 49.53), value_at=(30.48, 62.23))
    s.text("J20: side entry (MSTBA horizontal, wires from the right edge), 1 +12 V, 2 0 V.", 22.86, 71.12, 1.0)
    s.part("Device:Fuse", "F20", "4A", 55.88, 43.18, {"1": "V12_IN", "2": "V12_F"}, 90,
           "Fuse:Fuse_Littelfuse-NANO2-451_453", "Littelfuse", "0451004.MRL", ref_at=(55.88, 39.37),
           value_at=(55.88, 46.99))
    s.part("Transistor_FET:SUD19P06-60", "Q1", "SUD50P04-08", 88.9, 45.72, {"2": "V12_F", "3": "+12V", "1": "Q1_G"},
           270, "Package_TO_SOT_SMD:TO-252-2", "Vishay", "SUD50P04-08-GE3", ref_at=(88.9, 38.1),
           value_at=(88.9, 53.34))
    s.part("Device:D_Zener", "D30", "15V", 104.14, 68.58, {"1": "+12V", "2": "Q1_G"}, 90, FP["SOD123"],
           "Diodes Incorporated", "BZT52C15-7-F", ref_at=(109.22, 67.31), value_at=(109.22, 69.85),
           value_justify="left")
    s.R("R40", "10k", 88.9, 81.28, "Q1_G", "/GND_RACK")
    s.part("Device:D_Zener", "D31", "SMBJ15A", 124.46, 68.58, {"1": "+12V", "2": "/GND_RACK"}, 90,
           "Diode_SMD:D_SMB_Handsoldering", "Littelfuse", "SMBJ15A", ref_at=(129.54, 67.31),
           value_at=(129.54, 69.85), value_justify="left")
    s.C("C60", "10uF 25V X7R", 142.24, 68.58, "+12V", "/GND_RACK")
    s.C("C61", "10uF 25V X7R", 154.94, 68.58, "+12V", "/GND_RACK")
    s.flag(167.64, 43.18); s.power("+12V", 167.64, 43.18)
    s.flag(167.64, 91.44, 180); s.glabel("GND_RACK", 167.64, 91.44, 180)
    s.led_chain("D32", "R41", "green", "LTST-C150GKT", 180.34, 50.8, "+12V", rval="4.7k", ground="/GND_RACK")
    s.text("D32: 12 V present (rack side).", 175.26, 73.66, 1.0)

    s.part("Regulator_Switching:TDN_5-0910WISM", "U20", "TDN 5-2411WI", 228.6, 55.88,
           {"1": "+12V", "2": "/GND_RACK", "4": "~", "5": "~", "6": "GND", "7": "+5V"}, 0,
           "Converter_DCDC:Converter_DCDC_TRACO_TDN_5-xxxxWI_THT", "TRACO Power", "TDN 5-2411WI",
           ref_at=(228.6, 45.72), value_at=(228.6, 66.04))
    s.C("C62", "10uF 25V X7R", 205.74, 73.66, "+12V", "/GND_RACK")
    s.C("C63", "10uF 25V X7R", 254.0, 73.66, "+5V", "GND")
    s.text("U20 is the only RACK | LOGIC crossing. Remote On/Off (pin 4) open = on. No traces under it (TRACO).\n"
           "LOGIC budget 1 A at 5 V: core about 0.4 A (W6100 up to 265 mA), the rest for the cards (ISOW1044 x4).",
           200.66, 96.52, 1.0)

    s.part("Regulator_Linear:MCP1826S", "U2", "MCP1826S-3302E/DB", 314.96, 55.88,
           {"1": "+5V", "2": "GND", "3": "+3V3"}, 0, "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
           "Microchip Technology", "MCP1826S-3302E/DB", ref_at=(314.96, 48.26), value_at=(314.96, 64.77))
    s.C("C1", "10uF 25V X7R", 297.18, 71.12, "+5V", "GND")
    s.C("C2", "10uF 25V X7R", 335.28, 71.12, "+3V3", "GND")
    s.led_chain("D1", "R1", "green", "LTST-C150GKT", 360.68, 50.8, "+3V3")
    s.text("U2: 1 A. (5 - 3.3) V x I: about 0.7 W at 0.4 A; give the tab copper. D1: 3.3 V present.",
           292.1, 88.9, 1.0)
    return s


# ------------------------------------------------------------------ MCU

MCU = "Thl_MCU:PIC32MK1024MCM064-IPT"


def mcu_nets():
    n = {k: g(v) for k, v in sb.MCU_PINS.items()}
    n.update({
        7: "MCLR", 39: "OSC1", 40: "OSC2", 42: "LED_HB", 43: "PGD2", 44: "PGC2",
        50: "U1RX", 59: "U1TX", 33: "VMID_REF",
        51: "/ETH_MISO", 52: "/ETH_MOSI", 53: "/ETH_CS", 54: "/ETH_INT", 55: "/ETH_SCK", 58: "/ETH_RST",
        63: "~",
        34: "GND", 36: "USB_DN", 37: "USB_DP",
        10: "+3V3", 26: "+3V3", 38: "+3V3", 57: "+3V3", 35: "+3V3", 19: "AVDD",
        9: "GND", 25: "GND", 41: "GND", 56: "GND", 20: "GND",
    })
    return {str(k): v for k, v in n.items()}


def mcu_sheet():
    s = sheet("mcu.kicad_sch", "MCU", 3, "Core: PIC32MK1024MCM064")
    s.text("Stack bus pin map: tools/stack_bus.py (MCU_PINS, PPS groups checked against DS60001519E 13-1/13-2).\n"
           "Firmware: disable JTAG (RA7/RA8/RA10/RB9 used), ICESEL = PGx2, drive unused RB13 low.\n"
           "USB unused: VUSB3V3 to VDD, VBUS to VSS, D+/D- 10k to VSS.", 25.4, 20.32)
    mx, my = 167.64, 165.1
    s.part(MCU, "U1", "PIC32MK1024MCM064-I/PT", mx, my, mcu_nets(), 0, "Package_QFP:TQFP-64_10x10mm_P0.5mm",
           "Microchip Technology", "PIC32MK1024MCM064-I/PT", ref_at=(mx + 22.86, my - 60.96),
           value_at=(mx + 22.86, my + 60.96))
    for i, x in enumerate((25.4, 40.64, 55.88, 71.12, 86.36)):
        s.C(f"C{3 + i}", "100nF 50V X7R", x, 55.88, "+3V3", "GND", decouple=True)
    s.C("C8", "10uF 25V X7R", 101.6, 55.88, "+3V3", "GND")
    s.text("C3-C6 at the four VDD pins, C7 at VUSB3V3, C8 bulk. On the PCB: +3V3 island under U1.", 25.4, 45.72, 1.0)
    s.part("Device:FerriteBead", "FB1", "HI1206P121R-10", 30.48, 81.28, {"1": "+3V3", "2": "AVDD"}, 90,
           FP["FB"], "Laird", "HI1206P121R-10", ref_at=(30.48, 77.47), value_at=(30.48, 85.09))
    s.C("C9", "100nF 50V X7R", 45.72, 93.98, "AVDD", "GND", decouple=True)
    s.C("C10", "1uF 50V X7R", 58.42, 93.98, "AVDD", "GND")
    s.flag(58.42, 81.28); s.llabel("AVDD", 58.42, 81.28, 0)
    s.text("AVDD through FB1 (ADC reference = AVDD; the io-card AI uses the ADC).", 25.4, 106.68, 1.0)

    s.part("Device:Crystal", "Y1", "12MHz", 45.72, 132.08, {"1": "OSC1", "2": "OSC2"}, 0,
           "Crystal:Crystal_SMD_5032-2Pin_5.0x3.2mm_HandSoldering", "Abracon", "ABM3-12.000MHZ-B2-T",
           ref_at=(45.72, 128.27), value_at=(45.72, 137.16))
    s.C("C11", "27pF 50V C0G", 35.56, 144.78, "OSC1", "GND")
    s.C("C12", "27pF 50V C0G", 55.88, 144.78, "OSC2", "GND")
    s.text("12 MHz ABM3 (CL 18 pF, ESR 60 R max): 27 pF + ~4 pF stray per side. POSC HS.", 25.4, 157.48, 1.0)

    s.R("R4", "10k", 30.48, 175.26, "+3V3", "MCLR")
    s.C("C13", "100nF 50V X7R", 43.18, 187.96, "MCLR", "GND", decouple=True)
    s.R("R2", "10k", 68.58, 175.26, "USB_DP", "GND")
    s.R("R3", "10k", 81.28, 175.26, "USB_DN", "GND")
    s.part("Connector_Generic:Conn_01x06", "J2", "ICSP", 38.1, 220.98,
           {"1": "MCLR", "2": "+3V3", "3": "GND", "4": "PGD2", "5": "PGC2", "6": "~"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Horizontal", "Samtec", "TSW-106-08-G-S-RA",
           ref_at=(38.1, 213.36), value_at=(38.1, 231.14))
    s.text("ICSP (PICkit / ICD / Snap): 1 MCLR, 2 VDD, 3 VSS, 4 PGD2, 5 PGC2.", 25.4, 238.76, 1.0)
    s.part("Connector_Generic:Conn_01x03", "J5", "UART", 38.1, 256.54, {"1": "U1TX", "2": "U1RX", "3": "GND"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Horizontal", "Samtec", "TSW-103-08-G-S-RA",
           ref_at=(38.1, 251.46), value_at=(38.1, 262.89))
    s.text("Debug UART1 (3.3 V): 1 TX from MCU, 2 RX to MCU, 3 GND.", 25.4, 271.78, 1.0)

    s.led_chain("D2", "R6", "green", "LTST-C150GKT", 284.48, 50.8, "LED_HB")
    s.text("D2 heartbeat (RD8).", 279.4, 73.66, 1.0)
    s.R("R7", "4.7k", 309.88, 50.8, "+3V3", "/SCL")
    s.R("R8", "4.7k", 322.58, 50.8, "+3V3", "/SDA")
    s.text("I2C1 pull-ups for the stack bus (cards: expanders, ID EEPROMs).", 304.8, 66.04, 1.0)
    s.R("R60", "10k", 342.9, 50.8, "+3V3", "VMID_REF")
    s.R("R61", "10k", 342.9, 68.58, "VMID_REF", "GND")
    s.C("C84", "100nF 50V X7R", 358.14, 68.58, "VMID_REF", "GND", decouple=True)
    s.text("VMID_REF -> OA5 IN+ (pin 33); firmware ties OA5 IN- (49) to OUT (46) = VMID 1.65 V\n"
           "for the io-card's differential AI dividers (stack bus J10.36).", 335.28, 83.82, 1.0)
    return s


# ------------------------------------------------------------------ Ethernet

def eth_sheet():
    s = sheet("ethernet.kicad_sch", "Ethernet", 4, "Core: Ethernet (W6100)")
    s.text("W6100 in SPI mode (MOD[3:0] = 0000) on SPI3. Support circuit per WIZnet W6100_Ref_Schematic_V110_use_mag:\n"
           "2 x 49.9R + 0.1 uF per pair at the MDI pins, jack centre taps to 3V3A, beads 3V3D->3V3A and 1V2D->1V2A,\n"
           "RSET_BG 12k + 300R (12.3k 1 %), 25 MHz crystal with 8 pF and 1M. The jack's magnetics isolate the host.",
           25.4, 25.4)
    w = {"29": "/ETH_CS", "30": "/ETH_SCK", "32": "/ETH_MOSI", "33": "/ETH_MISO", "47": "/ETH_INT", "48": "/ETH_RST",
         "25": "MOD", "26": "MOD", "27": "MOD", "28": "MOD", "34": "+3V3", "35": "+3V3",
         "3": "TXP", "2": "TXN", "6": "RXP", "5": "RXN", "9": "RSET", "12": "XSCI", "11": "XSCO",
         "17": "LNKn", "18": "~", "19": "~", "20": "ACTn", "21": "~",
         "24": "+3V3", "36": "+3V3", "8": "3V3A", "15": "3V3A", "14": "1V2D", "13": "1V2D", "22": "1V2D",
         "31": "1V2D", "45": "1V2D", "4": "1V2A", "10": "GND", "23": "GND", "46": "GND", "1": "GND", "7": "GND",
         "16": "GND"}
    w.update({str(n): "~" for n in range(37, 45)})
    s.part("Thl_Interface:W6100-L", "U3", "W6100-L", 165.1, 139.7, w, 0, "Package_QFP:LQFP-48_7x7mm_P0.5mm",
           "WIZnet", "W6100-L", ref_at=(165.1, 101.6), value_at=(165.1, 177.8))
    s.text("MOD[3:0] low (SPI). RDn/WRn high. DAT[7:0] open in SPI mode.", 101.6, 190.5, 1.0)
    s.R("R10", "10k", 101.6, 157.48, "MOD", "GND")
    s.R("R11", "10k", 88.9, 116.84, "+3V3", "/ETH_RST")
    s.R("R12", "10k", 76.2, 116.84, "+3V3", "/ETH_INT")
    s.R("R13", "10k", 63.5, 116.84, "+3V3", "/ETH_CS")
    s.text("Pull-ups: CS (deselected at reset), INT, RST (MCU drives RST low >= 1 us, then 60 ms init).",
           50.8, 104.14, 1.0)
    s.part("Device:FerriteBead", "FB2", "HI1206P121R-10", 101.6, 55.88, {"1": "+3V3", "2": "3V3A"}, 90,
           FP["FB"], "Laird", "HI1206P121R-10", ref_at=(101.6, 52.07), value_at=(101.6, 59.69))
    s.part("Device:FerriteBead", "FB3", "HI1206P121R-10", 101.6, 76.2, {"1": "1V2D", "2": "1V2A"}, 90,
           FP["FB"], "Laird", "HI1206P121R-10", ref_at=(101.6, 72.39), value_at=(101.6, 80.01))
    s.flag(116.84, 50.8); s.llabel("3V3A", 116.84, 50.8, 0)
    s.flag(116.84, 71.12); s.llabel("1V2A", 116.84, 71.12, 0)
    for i, (net, x) in enumerate((("1V2D", 127.0), ("1V2D", 139.7), ("1V2D", 152.4), ("1V2D", 165.1),
                                  ("1V2A", 177.8), ("+3V3", 190.5), ("+3V3", 203.2), ("3V3A", 215.9),
                                  ("3V3A", 228.6))):
        s.C(f"C{20 + i}", "100nF 50V X7R", x, 55.88, net, "GND", decouple=True)
    s.C("C29", "3.3uF 25V X7R", 241.3, 55.88, "1V2D", "GND")
    s.text("C20-C23 at 1V2D (13/22/31/45), C24 at 1V2A, C25/C26 at 3V3D, C27/C28 at 3V3A, C29 on 1V2O.\n"
           "1V2O (pin 14) feeds 1V2D only; it must not supply anything else.", 127.0, 43.18, 1.0)
    s.R("R14", "12k", 228.6, 157.48, "RSET", "RSET2")
    s.R("R15", "300R", 228.6, 175.26, "RSET2", "GND")
    s.part("Device:Crystal", "Y2", "25MHz", 254.0, 190.5, {"1": "XSCI", "2": "XSCO"}, 0,
           "Crystal:Crystal_SMD_5032-2Pin_5.0x3.2mm_HandSoldering", "TBD", "TBD (25 MHz, 5032, CL 12 pF)",
           ref_at=(254.0, 186.69), value_at=(254.0, 195.58))
    s.R("R16", "1M", 254.0, 205.74, "XSCI", "XSCO", rot=90)
    s.C("C30", "8pF 50V C0G", 243.84, 213.36, "XSCI", "GND")
    s.C("C31", "8pF 50V C0G", 264.16, 213.36, "XSCO", "GND")
    s.R("R17", "49.9R", 279.4, 116.84, "TXP", "TXCT")
    s.R("R18", "49.9R", 279.4, 134.62, "TXCT", "TXN")
    s.C("C32", "100nF 50V X7R", 294.64, 129.54, "TXCT", "GND", decouple=True)
    s.R("R19", "49.9R", 279.4, 160.02, "RXP", "RXCT")
    s.R("R20", "49.9R", 279.4, 177.8, "RXCT", "RXN")
    s.C("C33", "100nF 50V X7R", 294.64, 172.72, "RXCT", "GND", decouple=True)
    s.text("R17-R20 and C32/C33 right at the W6100 MDI pins.", 269.24, 190.5, 1.0)
    j = {"1": "TXP", "2": "TXN", "3": "RXP", "5": "RXN", "4": "JCT", "6": "~", "7": "~", "8": "~", "9": "~",
         "10": "~", "12": "LEDG_A", "11": "LNKn", "14": "LEDY_A", "13": "ACTn", "SH": "CHASSIS"}
    s.part("Thl_Connector:JD0-0004NL", "J4", "JD0-0004NL", 345.44, 139.7, j, 0,
           "Thl_Connector:RJ45_Pulse_JD0-0004NL_Horizontal", "Pulse Electronics", "JD0-0004NL",
           ref_at=(345.44, 116.84), value_at=(345.44, 167.64))
    s.part("Device:FerriteBead", "FB4", "HI1206P121R-10", 314.96, 205.74, {"1": "3V3A", "2": "JCT"}, 90,
           FP["FB"], "Laird", "HI1206P121R-10", ref_at=(314.96, 201.93), value_at=(314.96, 209.55), dnp=True)
    s.R("R21", "0R", 314.96, 218.44, "3V3A", "JCT", rot=90)
    s.C("C34", "100nF 50V X7R", 330.2, 228.6, "JCT", "GND", decouple=True)
    s.C("C35", "1uF 50V X7R", 342.9, 228.6, "JCT", "GND")
    s.text("Centre taps (J4 pin 4) to 3V3A through R21 (0R); FB4 is an optional bead in its place (DNP).",
           304.8, 241.3, 1.0)
    s.R("R22", "330R", 370.84, 129.54, "+3V3", "LEDG_A")
    s.R("R23", "330R", 370.84, 152.4, "+3V3", "LEDY_A")
    s.text("Jack LEDs: green = link (LNKn), yellow = activity (ACTn).", 360.68, 172.72, 1.0)
    s.C("C36", "1nF 2kV X7R", 345.44, 205.74, "CHASSIS", "GND")
    s.text("Shield: 1 nF / 2 kV to GND (W6100 reference C5).", 335.28, 195.58, 1.0)
    return s


# ------------------------------------------------------------------ stack connectors

def stack_sheet():
    s = sheet("stack.kicad_sch", "Stack connectors", 5, "Core: stack bus J10 and rack power J11")
    s.text("Daughter-card stack (docs/requirements.md 4.5, tools/stack_bus.py). The core is the TOP of the stack:\n"
           "J10/J11 are pin headers on its underside, plugged into the top card's Samtec ESQ stacking sockets.\n"
           "Underside mounting mirrors the pad columns: pad k = bus pin k+1 (k odd) / k-1 (stack_bus.underside).\n"
           "J10 is LOGIC only. J11 (opposite board edge) carries RACK +12V / GND_RACK for relays and CAN1 bus power.",
           25.4, 20.32)
    # underside-mounted (core on top of the stack): pad k carries bus pin sb.underside(k)
    bus = {str(k): g(sb.BUS[sb.underside(k)]) for k in sb.BUS}
    s.part("Connector_Generic:Conn_02x20_Odd_Even", "J10", "STACK BUS", 101.6, 139.7, bus, 0,
           "Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical", "Samtec", "TSW-120-07-G-D",
           ref_at=(102.87, 111.76), value_at=(102.87, 167.64))
    pwr = {str(k): g(sb.PWR12[sb.underside(k)]) for k in sb.PWR12}
    s.part("Connector_Generic:Conn_02x03_Odd_Even", "J11", "RACK 12V", 254.0, 139.7, pwr, 0,
           "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical", "Samtec", "TSW-103-07-G-D",
           ref_at=(255.27, 132.08), value_at=(255.27, 147.32))
    s.text("J11: 1-3 +12V (after F20/Q1), 4-6 GND_RACK. Mates with ESQ-103 (5.7 A per contact).", 228.6, 160.02, 1.0)
    return s


SHEETS = [power_sheet, mcu_sheet, eth_sheet, stack_sheet]


def main():
    sheets = [f() for f in SHEETS]
    for sh in sheets:
        (HW / sh.file).write_text(sh.render())
    notes = ("Requirements: docs/requirements.md 4.0 and 4.5. Stack bus: tools/stack_bus.py.\n"
             "Domains: RACK (12 V DIN supply, +12V / GND_RACK) and LOGIC (floating +5V / +3V3 / GND from U20).")
    (HW / "core.kicad_sch").write_text(schgen.root_sheet(PROJECT, ROOT_UUID, sheets,
                                                         "Core: PIC32MK, 12 V power, Ethernet", REV, notes))
    print("wrote", [sh.file for sh in sheets])


if __name__ == "__main__":
    main()
