#!/usr/bin/env python3
"""Bootstrap generator for the pic-module schematic (POC #1, requirements 4.0).

PIC32MK1024MCM064 with its support parts, plus the can-controller power entry
(12 V input protection, TRACO TDN 5-2411WI isolated DC-DC, 3.3 V LDO), on a
module that plugs into every POC board through J3/J4 (2 x 20, 2.54 mm). The
circuits are copied from boards/can-controller/hardware/gen_schematic.py
(mcu_sheet, power_sheet); the connector pinout comes from module_pinout.py.

Domains: RACK (+12V, GND_RACK) and LOGIC (+5V, +3V3, GND, floating), crossed
only by U20.

Writes pic-module.kicad_sch from scratch: once the schematic is edited in
KiCad, stop using this script.

  python3 boards/pic-module/hardware/gen_schematic.py
"""
import sys
from pathlib import Path

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
sys.path.insert(0, str(HW))
import schgen  # noqa: E402
import module_pinout as mp  # noqa: E402

FP = schgen.FP
MPN = {
    "10k": ("Yageo", "RC1206FR-0710KL"), "1k": ("Yageo", "RC1206FR-071KL"), "4.7k": ("Yageo", "RC1206FR-074K7L"),
    "100k": ("Yageo", "RC1206FR-07100KL"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
    "1uF 50V X7R": ("Murata", "GRM31MR71H105KA88L"),
    "27pF 50V C0G": ("Murata", "GRM2165C1H270JA01D"),
}
MCU = "Thl_MCU:PIC32MK1024MCM064-IPT"
POWER = {"+3V3", "+5V", "+12V", "GND"}


def mcu_nets():
    nets = {k: v for k, v in mp.MCU_SIGNALS.items()}
    nets.update({39: "OSC1", 40: "OSC2",
                 10: "+3V3", 26: "+3V3", 38: "+3V3", 57: "+3V3", 35: "+3V3", 19: "AVDD",
                 9: "GND", 25: "GND", 41: "GND", 56: "GND", 20: "GND"})
    return {str(k): v for k, v in nets.items()}


def header_nets(conn):
    a = mp.assign()
    out = {}
    for pin in range(1, 41):
        n = a[(conn, pin)]
        out[str(pin)] = "~" if n in ("KEY", "SPACER") else n
    return out


def build():
    s = schgen.Sheet("pic-module", "PIC32MK + power module (POC)", "A", power=POWER, mpn=MPN)
    s.text("PIC32MK + power module: POC #1 (docs/requirements.md 4.0). Plugs into every POC board via J3/J4.\n"
           "RACK domain: +12V / GND_RACK (12 V input, protection). LOGIC domain (floating): +5V from U20, +3V3 from U2, GND.\n"
           "Circuits copied from the can-controller schematic (MCU and power sheets). Pinout: module_pinout.py.",
           25.4, 20.32)

    # --- 12 V input (RACK) ------------------------------------------------------
    s.part("Connector:Screw_Terminal_01x02", "J20", "12V IN", 30.48, 55.88, {"1": "V12_IN", "2": "GND_RACK"}, 0,
           "Connector_Phoenix_MSTB:PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical", "Phoenix Contact",
           "1755736", ref_at=(30.48, 49.53), value_at=(30.48, 62.23))
    s.text("J20: top entry, 1 +12 V, 2 0 V.", 22.86, 71.12, 1.0)
    s.part("Device:Fuse", "F20", "4A", 55.88, 43.18, {"1": "V12_IN", "2": "V12_F"}, 90,
           "Fuse:Fuse_Littelfuse-NANO2-451_453", "Littelfuse", "0451004.MRL", ref_at=(55.88, 39.37),
           value_at=(55.88, 46.99))
    s.part("Transistor_FET:SUD19P06-60", "Q1", "SUD50P04-08", 88.9, 45.72, {"2": "V12_F", "3": "+12V", "1": "Q1_G"},
           270, "Package_TO_SOT_SMD:TO-252-2", "Vishay", "SUD50P04-08-GE3", ref_at=(88.9, 38.1),
           value_at=(88.9, 53.34))
    s.part("Device:D_Zener", "D30", "15V", 104.14, 68.58, {"1": "+12V", "2": "Q1_G"}, 90, FP["SOD123"],
           "Diodes Incorporated", "BZT52C15-7-F", ref_at=(109.22, 67.31), value_at=(109.22, 69.85),
           value_justify="left")
    s.R("R40", "10k", 88.9, 81.28, "Q1_G", "GND_RACK")
    s.part("Device:D_Zener", "D31", "SMBJ15A", 124.46, 68.58, {"1": "+12V", "2": "GND_RACK"}, 90,
           "Diode_SMD:D_SMB_Handsoldering", "Littelfuse", "SMBJ15A", ref_at=(129.54, 67.31),
           value_at=(129.54, 69.85), value_justify="left")
    s.C("C60", "10uF 25V X7R", 142.24, 68.58, "+12V", "GND_RACK")
    s.C("C61", "10uF 25V X7R", 154.94, 68.58, "+12V", "GND_RACK")
    s.flag(167.64, 43.18); s.power("+12V", 167.64, 43.18)
    s.flag(167.64, 91.44, 180); s.llabel("GND_RACK", 167.64, 91.44, 180)
    s.led_chain("D32", "R41", "green", "LTST-C150GKT", 180.34, 50.8, "+12V", rval="4.7k", ground="GND_RACK")
    s.text("Reverse polarity: P-FET Q1 (D30 clamps Vgs). Transients: TVS D31. +12V and GND_RACK go to the\n"
           "host on J3.1-8 (2 A per contact, 4 contacts each). A host may feed +12V there instead of J20\n"
           "(unprotected). D32: 12 V present.", 22.86, 104.14, 1.0)

    # --- isolated LOGIC supply ---------------------------------------------------
    s.part("Regulator_Switching:TDN_5-0910WISM", "U20", "TDN 5-2411WI", 228.6, 55.88,
           {"1": "+12V", "2": "GND_RACK", "4": "~", "5": "~", "6": "GND", "7": "+5V"}, 0,
           "Converter_DCDC:Converter_DCDC_TRACO_TDN_5-xxxxWI_THT", "TRACO Power", "TDN 5-2411WI",
           ref_at=(228.6, 45.72), value_at=(228.6, 66.04))
    s.C("C62", "10uF 25V X7R", 205.74, 73.66, "+12V", "GND_RACK")
    s.C("C63", "10uF 25V X7R", 254.0, 73.66, "+5V", "GND")
    s.text("U20 (9-36 V in, 5 V 1 A, 1600 VDC) is the only RACK | LOGIC crossing. Remote On/Off (pin 4) open = on.\n"
           "No traces under it (TRACO). 1 A on +5V is shared by this module (~0.1 A) and the host.",
           200.66, 96.52, 1.0)

    # --- 3.3 V LDO ---------------------------------------------------------------
    s.part("Regulator_Linear:MCP1826S", "U2", "MCP1826S-3302E/DB", 314.96, 55.88,
           {"1": "+5V", "2": "GND", "3": "+3V3"}, 0, "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
           "Microchip Technology", "MCP1826S-3302E/DB", ref_at=(314.96, 48.26), value_at=(314.96, 64.77))
    s.C("C1", "10uF 25V X7R", 297.18, 71.12, "+5V", "GND")
    s.C("C2", "10uF 25V X7R", 335.28, 71.12, "+3V3", "GND")
    s.led_chain("D1", "R1", "green", "LTST-C150GKT", 360.68, 50.8, "+3V3")
    s.text("U2: 1 A. (5 - 3.3) V x 1 A = 1.7 W worst case: the host's 3.3 V load sets the tab copper needed.\n"
           "D1: 3.3 V present.", 292.1, 88.9, 1.0)

    # --- MCU ---------------------------------------------------------------------
    mx, my = 167.64, 177.8
    s.part(MCU, "U1", "PIC32MK1024MCM064-I/PT", mx, my, mcu_nets(), 0, "Package_QFP:TQFP-64_10x10mm_P0.5mm",
           "Microchip Technology", "PIC32MK1024MCM064-I/PT", ref_at=(mx + 22.86, my - 60.96),
           value_at=(mx + 22.86, my + 60.96))
    for i, x in enumerate((25.4, 40.64, 55.88, 71.12, 86.36)):
        s.C(f"C{3 + i}", "100nF 50V X7R", x, 129.54, "+3V3", "GND", decouple=True)
    s.C("C8", "10uF 25V X7R", 101.6, 129.54, "+3V3", "GND")
    s.text("C3-C6 at the four VDD pins, C7 at VUSB3V3, C8 bulk.", 25.4, 119.38, 1.0)
    s.part("Device:FerriteBead", "FB1", "HI1206P121R-10", 30.48, 152.4, {"1": "+3V3", "2": "AVDD"}, 90,
           FP["FB"], "Laird", "HI1206P121R-10", ref_at=(30.48, 148.59), value_at=(30.48, 156.21))
    s.C("C9", "100nF 50V X7R", 45.72, 165.1, "AVDD", "GND", decouple=True)
    s.C("C10", "1uF 50V X7R", 58.42, 165.1, "AVDD", "GND")
    s.flag(58.42, 152.4); s.llabel("AVDD", 58.42, 152.4, 0)
    s.text("AVDD through FB1 (ADC reference = AVDD).", 25.4, 177.8, 1.0)

    s.part("Device:Crystal", "Y1", "12MHz", 45.72, 203.2, {"1": "OSC1", "2": "OSC2"}, 0,
           "Crystal:Crystal_SMD_5032-2Pin_5.0x3.2mm_HandSoldering", "Abracon", "ABM3-12.000MHZ-B2-T",
           ref_at=(45.72, 199.39), value_at=(45.72, 208.28))
    s.C("C11", "27pF 50V C0G", 35.56, 215.9, "OSC1", "GND")
    s.C("C12", "27pF 50V C0G", 55.88, 215.9, "OSC2", "GND")
    s.text("12 MHz ABM3 (CL 18 pF, ESR 60 R max, -20..70 C): 27 pF + ~4 pF stray per side. POSC HS. Stays on the module.", 25.4, 228.6, 1.0)

    s.R("R4", "10k", 30.48, 243.84, "+3V3", "MCLR")
    s.C("C13", "100nF 50V X7R", 43.18, 256.54, "MCLR", "GND", decouple=True)
    s.R("R2", "100k", 68.58, 243.84, "USB_DP", "GND")
    s.R("R3", "100k", 81.28, 243.84, "USB_DN", "GND")
    s.R("R5", "100k", 93.98, 243.84, "VBUS", "GND")
    s.flag(106.68, 243.84); s.llabel("VBUS", 106.68, 243.84, 0)
    s.text("USB pins go to the host. With no USB on the host, R2/R3/R5 hold D+/D-/VBUS low\n"
           "(VUSB3V3 is always powered). MCLR also goes to the host (reset button).", 25.4, 271.78, 1.0)

    s.part("Connector_Generic:Conn_01x06", "J2", "ICSP", 266.7, 165.1,
           {"1": "MCLR", "2": "+3V3", "3": "GND", "4": "RB5_PGD", "5": "RB6_PGC", "6": "~"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", "Samtec", "TSW-106-07-G-S",
           ref_at=(266.7, 157.48), value_at=(266.7, 175.26))
    s.text("ICSP (PICkit / ICD / Snap): 1 MCLR, 2 VDD, 3 VSS, 4 PGD2, 5 PGC2.\n"
           "Hosts must not load RB5/RB6 while programming.", 248.92, 182.88, 1.0)
    s.part("Connector_Generic:Conn_01x03", "J5", "UART", 266.7, 200.66, {"1": "RF1_TX", "2": "RC6_RX", "3": "GND"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", "Samtec", "TSW-103-07-G-S",
           ref_at=(266.7, 195.58), value_at=(266.7, 207.01))
    s.text("Debug UART (3.3 V): 1 TX from MCU (U1TX on RF1), 2 RX to MCU (U1RX on RC6), 3 GND.", 248.92, 213.36, 1.0)
    s.led_chain("D2", "R6", "green", "LTST-C150GKT", 254.0, 228.6, "RD8_LED")
    s.text("D2 heartbeat (RD8).", 248.92, 251.46, 1.0)

    # --- host connectors -------------------------------------------------------------
    for ref, x in (("J3", 330.2), ("J4", 381.0)):
        s.part("Connector_Generic:Conn_02x20_Odd_Even", ref, f"{ref} host", x, 177.8, header_nets(ref), 0,
               "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical", "Sullins Connector Solutions",
               "PPTC202LFBN-RC", ref_at=(x + 1.27, 149.86), value_at=(x + 1.27, 205.74))
    s.text("J3/J4: 2 x 20, 2.54 mm sockets on the module BOTTOM; pin headers on the host.\n"
           "Keying: J4 sits 1 mm off the 180-degree position of J3, and J3.9 is blocked\n"
           "(cut pin glued into the socket) with no pin on the host. J3.10 is unused: it\n"
           "spaces the RACK pins (J3.1-8) from the LOGIC pins.", 307.34, 215.9, 1.0)
    return s


def main():
    (HW / "pic-module.kicad_sch").write_text(build().render())
    print("wrote pic-module.kicad_sch")


if __name__ == "__main__":
    main()
