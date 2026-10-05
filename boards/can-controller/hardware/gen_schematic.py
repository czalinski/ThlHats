#!/usr/bin/env python3
"""Bootstrap generator for the can-controller hierarchical schematic.

Root sheet + one sub-sheet per functional block. Nets between blocks use
global labels (names written with a leading "/"); nets inside a block use
local labels placed on pin ends. Power symbols: +3V3, +5V, GND (logic domain)
and +12V (12 V domain, after input protection). The 12 V domain's ground and
5 V are the global nets GND_BUS and V5_BUS (CAN bus ground, not logic ground).

This writes can-controller.kicad_sch and every sub-sheet from scratch. It is
only for the initial capture: once anyone edits the schematic in KiCad, stop
using it (or the edits are lost) and continue in KiCad.

  python3 boards/can-controller/hardware/gen_schematic.py
"""
import importlib.util
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
spec = importlib.util.spec_from_file_location("nb", REPO / "tools/new_board.py")
nb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nb)
q, uid = nb.q, nb.uid

HW = REPO / "boards/can-controller/hardware"
PROJECT = "can-controller"
ROOT_UUID = re.search(r'\(uuid "([^"]+)"\)', (HW / "can-controller.kicad_sch").read_text()).group(1)

POWER = {"+3V3", "+5V", "+12V", "GND"}

FP = {
    "R": "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder",
    "C": "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder",
    "Cd": "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder",
    "LED": "LED_SMD:LED_1206_3216Metric_Pad1.42x1.75mm_HandSolder",
    "PTC": "Fuse:Fuse_1812_4532Metric_Pad1.30x3.40mm_HandSolder",
    "SOT23": "Package_TO_SOT_SMD:SOT-23",
    "SOD123": "Diode_SMD:D_SOD-123",
    "MC": "Connector_Phoenix_MC:PhoenixContact_MC_1,5_{n}-G-3.5_1x{n:02d}_P3.50mm_Horizontal",
    "SPTD": "Thl_Connector:PhoenixContact_SPTD_1,5_{n}-H-3,5_2x{n:02d}_P3.5mm_Horizontal",
}
MPN = {
    "10k": ("Yageo", "RC1206FR-0710KL"), "1k": ("Yageo", "RC1206FR-071KL"), "4.7k": ("Yageo", "RC1206FR-074K7L"),
    "120R": ("Yageo", "RC1206FR-07120RL"), "5.1k": ("Yageo", "RC1206FR-075K1L"), "10M": ("Yageo", "RC1206FR-0710ML"),
    "130k": ("Yageo", "RC1206FR-07130KL"), "30k": ("Yageo", "RC1206FR-0730KL"), "470R": ("Yageo", "RC1206FR-07470RL"),
    "1M": ("Yageo", "RC1206FR-071ML"), "105k": ("Yageo", "RC1206FR-07105KL"), "100k": ("Yageo", "RC1206FR-07100KL"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),          # 0805, decoupling
    "100nF 50V X7R 1206": ("Murata", "GRM319R71H104KA01D"),     # 1206, filters
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
    "4.7uF 25V X7R": ("Murata", "GRM31CR71E475KA88L"),
    "27pF 50V C0G": ("Murata", "GRM2165C1H270JA01D"),
}


def pin_table(lib_id):
    nick, name = lib_id.split(":")
    text = (nb.kilib.SYM_DIR / f"{nick}.kicad_sym").read_text()
    s, e = nb.kilib.top_level_symbols(text)[name]
    out = {}
    for m in re.finditer(r'\(pin\s+\w+\s+\w+\s+\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\).*?\(number\s+"([^"]+)"',
                         text[s:e], re.S):
        out[m.group(4)] = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    return out


def rnd(v):
    return round(v * 100) / 100


class Sheet(nb.Sch):
    """Sub-sheet: A3, symbol instance paths below the root sheet."""

    def __init__(self, file, name, page, title):
        super().__init__(PROJECT, title, "A")
        self.file, self.name, self.page = file, name, page
        self.sheet_uuid = uid()
        self.own_uuid = uid()

    def symbol(self, lib_id, ref, value, x, y, rot=0, footprint="", **kw):
        root = self.root
        self.root = ROOT_UUID + "/" + self.sheet_uuid
        u = super().symbol(lib_id, ref, value, x, y, rot, footprint, **kw)
        self.root = root
        return u

    def pin_end(self, lib_id, x, y, rot, num):
        px, py, ang = pin_table(lib_id)[num]
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        rx, ry = px * c - py * s, px * s + py * c
        out = (ang + rot + 180) % 360
        return rnd(x + rx), rnd(y - ry), out

    def glabel(self, name, x, y, out, shape="bidirectional"):
        rot = {0: 0, 90: 90, 180: 180, 270: 270}[out]
        just = "left" if out in (0, 90) else "right"
        self.items.append(
            f"\t(global_label {q(name)}\n\t\t(shape {shape})\n\t\t(at {x:g} {y:g} {rot})\n"
            f"\t\t(fields_autoplaced yes)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {just})\n\t\t)\n\t\t(uuid {q(uid())})\n"
            f"\t\t(property \"Intersheetrefs\" \"${{INTERSHEET_REFS}}\"\n\t\t\t(at {x:g} {y:g} 0)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n\t)\n")

    def llabel(self, name, x, y, out):
        rot = {0: 0, 90: 90, 180: 180, 270: 270}[out]
        self.label(name, x, y, rot, "left" if out in (0, 90) else "right")

    def pwrsym(self, name, x, y, out):
        dx, dy = {0: (2.54, 0), 180: (-2.54, 0), 90: (0, -2.54), 270: (0, 2.54)}[out]
        ex, ey = rnd(x + dx), rnd(y + dy)
        self.wire(x, y, ex, ey)
        gnd = name == "GND"
        rot = ({270: 0, 90: 180, 180: 270, 0: 90} if gnd else {90: 0, 270: 180, 180: 90, 0: 270})[out]
        self.power(name, ex, ey, rot)

    def net(self, name, x, y, out):
        if name == "":
            return
        if name == "~":
            self.no_connect(x, y)
        elif name in POWER:
            self.pwrsym(name, x, y, out)
        elif name.startswith("/"):
            self.glabel(name[1:], x, y, out)
        else:
            self.llabel(name, x, y, out)

    def part(self, lib_id, ref, value, x, y, nets, rot=0, footprint="", mfr=None, mpn=None,
             unit=1, dnp=False, **kw):
        pins = pin_table(lib_id)
        fields = {"Manufacturer": mfr, "MPN": mpn} if mpn else {}
        fields.update(kw.pop("fields", {}) or {})
        multi = kw.pop("multi", False) or unit != 1
        self.symbol(lib_id, ref, value, x, y, rot, footprint, pins=list(nets) if multi else list(pins),
                    fields=fields, **kw)
        if unit != 1:
            self.items[-1] = self.items[-1].replace("(unit 1)", f"(unit {unit})")
        if dnp:
            self.items[-1] = self.items[-1].replace("(dnp no)", "(dnp yes)", 1)
        for num, n in nets.items():
            px, py, out = self.pin_end(lib_id, x, y, rot, num)
            self.net(n, px, py, out)

    def R(self, ref, value, x, y, n1, n2, rot=0):
        mfr, mpn = MPN[value]
        if rot == 90:
            at = dict(ref_at=(x, y - 2.54), value_at=(x, y + 2.54))
        else:
            at = dict(ref_at=(x + 2.54, y - 1.27), value_at=(x + 2.54, y + 1.27), value_justify="left")
        self.part("Device:R", ref, value, x, y, {"1": n1, "2": n2}, rot, FP["R"], mfr, mpn, **at)

    def C(self, ref, value, x, y, n1, n2, decouple=False):
        mfr, mpn = MPN[value]
        fp = FP["Cd"] if (decouple or "pF" in value) else FP["C"]
        shown = value.replace(" 1206", "")
        self.part("Device:C", ref, shown, x, y, {"1": n1, "2": n2}, 0, fp, mfr, mpn,
                  ref_at=(x + 2.54, y - 1.27), value_at=(x + 2.54, y + 1.27), value_justify="left")

    def LED(self, ref, colour, x, y, anode, cathode, mpn):
        self.part("Device:LED", ref, f"LED {colour}", x, y, {"2": anode, "1": cathode}, 90, FP["LED"], "Lite-On", mpn,
                  ref_at=(x + 2.54, y - 1.27), value_at=(x + 2.54, y + 1.27), value_justify="left", hide_value=True)

    def led_chain(self, lref, rref, colour, mpn, x, y, drive, rval="1k", ground="GND"):
        """drive -> R -> LED -> ground, vertical at x."""
        self.R(rref, rval, x, y, drive, f"{lref}_A")
        self.LED(lref, colour, x, y + 10.16, f"{lref}_A", ground, mpn)

    def render(self):
        text = super().render()
        text = text.replace('(paper "A4")', '(paper "A3")')
        text = text.replace(f'(uuid {q(self.root)})', f'(uuid {q(self.own_uuid)})', 1)
        text = re.sub(r'\t\(sheet_instances.*?\n\t\)\n', '', text, flags=re.S)
        return text


def root_sheet(sheets, title):
    sch = nb.Sch(PROJECT, title, "A")
    sch.root = ROOT_UUID
    sch.text(title, 25.4, 30.48, 2.54)
    sch.text("Requirements: docs/requirements.md 4.1. Floorplan and parts: boards/can-controller/README.md.\n"
             "Two domains: LOGIC (Pi ground, header 5 V, 3.3 V) and 12 V (CAN bus ground GND_BUS, from the DIN supply).\n"
             "Only the isolators cross: ISO1044 (CAN), ISO6740 (relay drive), TLP293 (12 V status).", 25.4, 38.1)
    blocks = []
    for i, sh in enumerate(sheets):
        x, y, w, h = 30.48 + (i % 4) * 60.96, 60.96 + (i // 4) * 40.64, 50.8, 25.4
        blocks.append(
            f"\t(sheet\n\t\t(at {x:g} {y:g})\n\t\t(size {w:g} {h:g})\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n"
            f"\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(fields_autoplaced yes)\n"
            f"\t\t(stroke\n\t\t\t(width 0.1524)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill\n\t\t\t(color 0 0 0 0.0000)\n\t\t)\n"
            f"\t\t(uuid {q(sh.sheet_uuid)})\n"
            f"\t\t(property \"Sheetname\" {q(sh.name)}\n\t\t\t(at {x:g} {y - 0.7:g} 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left bottom)\n\t\t\t)\n\t\t)\n"
            f"\t\t(property \"Sheetfile\" {q(sh.file)}\n\t\t\t(at {x:g} {y + h + 0.6:g} 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(justify left top)\n\t\t\t)\n\t\t)\n"
            f"\t\t(instances\n\t\t\t(project {q(PROJECT)}\n\t\t\t\t(path {q('/' + ROOT_UUID)}\n\t\t\t\t\t(page {q(str(sh.page))})\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
    sch.items.extend(blocks)
    return sch.render()


# ------------------------------------------------------------------ blocks

MCU = "Thl_MCU:PIC32MK1024MCM064-IPT"

# PIC32MK1024MCM064 pin map (TQFP-64). PPS groups per DS60001519E Table 13-1/13-2:
# C1TX grp1 / C1RX grp3, C2TX grp4 / C2RX grp2, C3TX grp3 / C3RX grp1, C4TX grp2 / C4RX grp4,
# U1TX grp1 / U1RX grp3, SDO1 grp1-2, SCK1 fixed RB7.
MCU_NETS = {
    # left side: GPIO (connectors on the left edge), I2C1, DAC chip select
    "1": "/GPIO8", "2": "/GPIO7", "3": "/GPIO6", "4": "/GPIO5",
    "5": "/I2C_SCL", "6": "/I2C_SDA", "7": "MCLR", "8": "/GPIO4",
    "11": "/GPIO3", "12": "/GPIO2", "13": "/GPIO1", "14": "/DAC_CS", "15": "~", "16": "~",
    # bottom: ICSP, CAN, relays
    "17": "PGC1", "18": "PGD1", "21": "/C3RX", "22": "/RLY1", "23": "/RLY2", "24": "/RLY3",
    "27": "/RLY4", "28": "/RLY5", "29": "/C3TX", "30": "/C2TX", "31": "/C2RX", "32": "/C1TX",
    # right: CAN, USB, crystal, SPI clock, 12 V status
    "33": "/C1RX", "34": "VBUS", "36": "USB_DN", "37": "USB_DP", "39": "OSC1", "40": "OSC2",
    "42": "/RLY6", "43": "/C4TX", "44": "/RLY7", "45": "/C4RX", "46": "/DAC_SCK", "47": "/V12_OK", "48": "~",
    # top: UART, SPI data, LEDs, relay 8
    "49": "/RLY8", "50": "U1RX", "51": "U1TX", "52": "/DAC_SDI", "53": "/LED_CAN1", "54": "/LED_CAN2",
    "55": "/LED_CAN3", "58": "/LED_CAN4", "59": "LED_HB", "60": "LED_USB", "61": "~", "62": "~", "63": "~", "64": "~",
    # power
    "10": "+3V3", "26": "+3V3", "38": "+3V3", "57": "+3V3", "19": "AVDD", "35": "+3V3",
    "9": "GND", "25": "GND", "41": "GND", "56": "GND", "20": "GND",
}


def mcu_sheet():
    s = Sheet("mcu.kicad_sch", "MCU, USB, power", 2, "CAN controller: MCU, USB, logic power")
    s.text("LOGIC DOMAIN. Pi header 5 V -> 3.3 V LDO. The board never drives the header 5 V.", 25.4, 25.4)

    # --- Pi header: 5 V and GND only ---------------------------------------
    hdr = "Connector_Generic:Conn_02x20_Odd_Even"
    nets = {str(n): "~" for n in range(1, 41)}
    nets.update({"2": "V5_PI", "4": "V5_PI"})
    for n in (6, 9, 14, 20, 25, 30, 34, 39):
        nets[str(n)] = "GND"
    s.part(hdr, "J1", "RPi_GPIO", 50.8, 88.9, nets, 0,
           "Thl_Connector:Samtec_REF-182665_2x20_P2.54mm_PassThrough", "Samtec", "REF-182665-01",
           ref_at=(50.8, 60.96), value_at=(50.8, 118.11))
    s.text("Samtec REF-182665 pass-through socket. Uses no header signal pins\n"
           "(MCC DAQ HATs share the header). Pi 3.3 V (pins 1, 17) not used.", 30.48, 127.0, 1.0)
    s.part("Device:Polyfuse", "F1", "0.75A", 86.36, 60.96, {"1": "V5_PI", "2": "+5V"}, 90,
           "Fuse:Fuse_1206_3216Metric_Pad1.42x1.75mm_HandSolder", "Bourns", "MF-NSMF075-2",
           ref_at=(86.36, 57.15), value_at=(86.36, 64.77))
    s.flag(78.74, 55.88); s.llabel("V5_PI", 78.74, 55.88, 180)
    s.flag(99.06, 55.88); s.power("+5V", 99.06, 55.88)
    s.flag(99.06, 76.2, 180); s.power("GND", 99.06, 76.2)
    s.text("Header 5 V budget: <= 1 A for all of our boards (requirements 3.1).", 76.2, 71.12, 1.0)

    # --- 3.3 V LDO ------------------------------------------------------------
    s.part("Regulator_Linear:MCP1826S", "U2", "MCP1826S-3302E/DB", 124.46, 60.96,
           {"1": "+5V", "2": "GND", "3": "+3V3"}, 0, "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
           "Microchip Technology", "MCP1826S-3302E/DB", ref_at=(124.46, 53.34), value_at=(124.46, 69.85))
    s.C("C1", "10uF 25V X7R", 109.22, 76.2, "+5V", "GND")
    s.C("C2", "10uF 25V X7R", 142.24, 76.2, "+3V3", "GND")
    s.led_chain("D1", "R1", "green", "LTST-C150GKT", 157.48, 63.5, "+3V3")
    s.text("D1: 3.3 V present.", 154.94, 86.36, 1.0)

    # --- MCU --------------------------------------------------------------------
    mx, my = 254.0, 129.54
    s.part(MCU, "U1", "PIC32MK1024MCM064-I/PT", mx, my, MCU_NETS, 0, "Package_QFP:TQFP-64_10x10mm_P0.5mm",
           "Microchip Technology", "PIC32MK1024MCM064-I/PT", ref_at=(mx + 22.86, my - 50.8), value_at=(mx + 22.86, my + 50.8))
    s.part("Device:FerriteBead_Small", "FB1", "600R@100MHz", 287.02, 40.64, {"1": "+3V3", "2": "AVDD"}, 90,
           "Inductor_SMD:L_0805_2012Metric_Pad1.05x1.20mm_HandSolder", "Murata", "BLM21PG601SN1D",
           ref_at=(287.02, 36.83), value_at=(287.02, 44.45))
    for i, x in enumerate((172.72, 190.5, 208.28, 226.06)):
        s.C(f"C{3 + i}", "100nF 50V X7R", x, 45.72, "+3V3", "GND", decouple=True)
    s.C("C7", "10uF 25V X7R", 243.84, 45.72, "+3V3", "GND")
    s.C("C8", "100nF 50V X7R", 314.96, 50.8, "AVDD", "GND", decouple=True)
    s.C("C9", "100nF 50V X7R", 261.62, 45.72, "+3V3", "GND", decouple=True)
    s.text("C3-C6 at the four VDD pins, C9 at VUSB3V3, C7 bulk; C8 + FB1 for AVDD.", 172.72, 33.02, 1.0)

    # crystal
    s.part("Device:Crystal", "Y1", "12MHz", 340.36, 116.84, {"1": "OSC1", "2": "OSC2"}, 0,
           "Crystal:Crystal_SMD_5032-2Pin_5.0x3.2mm_HandSoldering", "TBD", "TBD (12 MHz, 5032, CL 18 pF)",
           ref_at=(340.36, 113.03), value_at=(340.36, 121.92))
    s.C("C10", "27pF 50V C0G", 330.2, 129.54, "OSC1", "GND")
    s.C("C11", "27pF 50V C0G", 350.52, 129.54, "OSC2", "GND")
    s.text("12 MHz, CL 18 pF (POSC HS 4-32 MHz).\nSystem clock and the 48 MHz USB clock (UPLL) from it.", 325.12, 104.14, 1.0)

    # MCLR + ICSP
    s.R("R2", "10k", 106.68, 152.4, "+3V3", "MCLR")
    s.C("C12", "100nF 50V X7R", 119.38, 165.1, "MCLR", "GND", decouple=True)
    s.part("Connector_Generic:Conn_01x06", "J2", "ICSP", 76.2, 165.1,
           {"1": "MCLR", "2": "+3V3", "3": "GND", "4": "PGD1", "5": "PGC1", "6": "~"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", "Samtec", "TSW-106-07-G-S",
           ref_at=(76.2, 157.48), value_at=(76.2, 175.26))
    s.text("ICSP (PICkit / ICD / Snap): 1 MCLR, 2 VDD, 3 VSS, 4 PGD1, 5 PGC1.", 55.88, 182.88, 1.0)

    # debug UART
    s.part("Connector_Generic:Conn_01x03", "J3", "UART", 76.2, 205.74, {"1": "U1TX", "2": "U1RX", "3": "GND"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", "Samtec", "TSW-103-07-G-S",
           ref_at=(76.2, 200.66), value_at=(76.2, 212.09))
    s.text("Debug UART (3.3 V): 1 TX from MCU, 2 RX to MCU, 3 GND.", 55.88, 220.98, 1.0)

    # --- USB-C ------------------------------------------------------------------
    usb = "Connector:USB_C_Receptacle_USB2.0_16P"
    s.part(usb, "J4", "USB-C", 342.9, 190.5,
           {"A4": "VBUS_C", "A9": "VBUS_C", "B4": "VBUS_C", "B9": "VBUS_C",
            "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
            "A5": "CC1", "B5": "CC2", "A6": "USB_DP_C", "B6": "USB_DP_C", "A7": "USB_DN_C", "B7": "USB_DN_C",
            "A8": "~", "B8": "~"}, 0, "Connector_USB:USB_C_Receptacle_GCT_USB4085", "GCT", "USB4085-GF-A",
           ref_at=(342.9, 162.56), value_at=(342.9, 218.44))
    s.R("R3", "5.1k", 309.88, 228.6, "CC1", "GND")
    s.R("R4", "5.1k", 297.18, 228.6, "CC2", "GND")
    s.part("Power_Protection:USBLC6-2P6", "U3", "USBLC6-2SC6", 287.02, 190.5,
           {"1": "USB_DP_C", "6": "USB_DP", "3": "USB_DN_C", "4": "USB_DN", "5": "VBUS_C", "2": "GND"}, 0,
           "Package_TO_SOT_SMD:SOT-23-6", "STMicroelectronics", "USBLC6-2SC6",
           ref_at=(287.02, 180.34), value_at=(287.02, 200.66))
    s.R("R5", "1k", 271.78, 213.36, "VBUS_C", "VBUS", rot=90)
    s.R("R6", "100k", 261.62, 226.06, "VBUS", "GND")
    s.flag(254.0, 205.74); s.llabel("VBUS", 254.0, 205.74, 180)
    s.flag(302.26, 35.56); s.llabel("AVDD", 302.26, 35.56, 0)
    s.text("USB 2.0 full speed, device only. CC 5.1k pull-downs. VBUS is sensed (1k series,\n"
           "100k pull-down), never used for power: the board runs from the Pi header.\n"
           "USBLC6 pass-through: pins 1/6 D+, 3/4 D- (route straight through).", 254.0, 254.0, 1.0)

    # --- status LEDs --------------------------------------------------------------
    s.led_chain("D2", "R7", "green", "LTST-C150GKT", 360.68, 50.8, "LED_HB")
    s.led_chain("D3", "R8", "green", "LTST-C150GKT", 375.92, 50.8, "LED_USB")
    s.text("D2 heartbeat, D3 USB host link.", 355.6, 76.2, 1.0)
    return s


def can_sheet():
    s = Sheet("can.kicad_sch", "CAN x4", 3, "CAN controller: four isolated CAN FD channels")
    s.text("Four isolated CAN FD channels (ISO1044BD). Logic side +3V3/GND, bus side V5_BUS/GND_BUS (12 V domain).\n"
           "Connector pinout as every ThlHats board: 1 CANH, 2 CANL, 3 GND_BUS, 4 +12 V (cable supply).\n"
           "CAN1 = can-ssr bus: F10 fitted. CAN2-4 = DUT buses: F11-F13 DNP, so pin 4 is dead unless fitted.",
           25.4, 25.4)
    term = FP["MC"].format(n=4)
    for i in range(4):
        n = i + 1
        y0 = 50.8 + i * 58.42
        x0 = 50.8
        s.text(f"CAN{n}", x0 - 20.32, y0 - 5.08, 2.0)
        # ISO1044: logic side left, bus side right
        s.part("Interface_CAN_LIN:ISO1044BD", f"U{10 + i}", "ISO1044BD", x0 + 60.96, y0 + 10.16,
               {"1": "+3V3", "2": f"/C{n}TX", "3": f"/C{n}RX", "4": "GND",
                "5": f"CANL{n}", "6": f"CANH{n}", "7": "/GND_BUS", "8": "/V5_BUS"}, 0,
               "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Texas Instruments", "ISO1044BDR",
               ref_at=(x0 + 66.04, y0 - 2.54), value_at=(x0 + 66.04, y0 + 22.86))
        s.C(f"C{20 + 2 * i}", "100nF 50V X7R", x0 + 30.48, y0 + 5.08, "+3V3", "GND", decouple=True)
        s.C(f"C{21 + 2 * i}", "100nF 50V X7R", x0 + 91.44, y0 + 5.08, "/V5_BUS", "/GND_BUS", decouple=True)
        # ESD, termination
        s.part("Power_Protection:NUP2105L", f"D{20 + i}", "NUP2105L", x0 + 129.54, y0 + 10.16,
               {"1": f"CANH{n}", "2": f"CANL{n}", "3": "/GND_BUS"}, 0, FP["SOT23"], "onsemi", "NUP2105LT1G",
               ref_at=(x0 + 134.62, y0 + 6.35), value_at=(x0 + 134.62, y0 + 13.97))
        s.part("Jumper:Jumper_2_Open", f"JP{1 + i}", "TERM", x0 + 152.4, y0 + 2.54,
               {"1": f"CANH{n}", "2": f"TERM{n}"}, 0, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
               "Samtec", "TSW-102-07-G-S", ref_at=(x0 + 152.4, y0 - 1.27), value_at=(x0 + 152.4, y0 + 6.35))
        s.R(f"R{20 + i}", "120R", x0 + 167.64, y0 + 10.16, f"TERM{n}", f"CANL{n}")
        # cable supply fuse and connector
        s.part("Device:Polyfuse", f"F{10 + i}", "1.1A", x0 + 190.5, y0 + 22.86, {"1": "+12V", "2": f"V12_CAN{n}"}, 90,
               FP["PTC"], "Littelfuse", "1812L110/16DR", dnp=(n != 1),
               ref_at=(x0 + 190.5, y0 + 19.05), value_at=(x0 + 190.5, y0 + 26.67))
        s.part("Connector:Screw_Terminal_01x04", f"J{10 + i}", f"CAN{n}", x0 + 223.52, y0 + 10.16,
               {"1": f"CANH{n}", "2": f"CANL{n}", "3": "/GND_BUS", "4": f"V12_CAN{n}"}, 0, term,
               "Phoenix Contact", "1844236", ref_at=(x0 + 223.52, y0 + 2.54), value_at=(x0 + 223.52, y0 + 19.05))
        # activity LED (logic side)
        s.led_chain(f"D{24 + i}", f"R{24 + i}", "yellow", "LTST-C150YKT", x0 + 7.62, y0 + 20.32, f"/LED_CAN{n}")
    s.text("JP1-JP4: fit the shunt (Samtec SNT-100-BK-G) only where this board is a bus end.\n"
           "Activity LEDs D24-D27 are driven by the MCU (logic side).", 76.2, 279.4, 1.0)
    return s


def power12_sheet():
    s = Sheet("power12.kicad_sch", "12 V input", 4, "CAN controller: 12 V input, bus-side 5 V, 12 V status")
    s.text("12 V DOMAIN. External 12 V DIN supply with a floating output; its 0 V is the CAN bus ground GND_BUS,\n"
           "never connected to logic GND. Reverse polarity: P-FET Q1. Overvoltage/transients: TVS D10. Fuse F1x.",
           25.4, 25.4)
    s.part("Connector:Screw_Terminal_01x02", "J20", "12V IN", 38.1, 63.5, {"1": "V12_IN", "2": "/GND_BUS"}, 0,
           "Connector_Phoenix_MSTB:PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical", "Phoenix Contact",
           "1755736", ref_at=(38.1, 57.15), value_at=(38.1, 69.85))
    s.text("J20: top entry, 1 +12 V, 2 0 V.", 25.4, 78.74, 1.0)
    s.part("Device:Fuse", "F20", "4A", 63.5, 50.8, {"1": "V12_IN", "2": "V12_F"}, 90,
           "Fuse:Fuse_Littelfuse-NANO2-451_453", "Littelfuse", "0451004.MRL", ref_at=(63.5, 46.99), value_at=(63.5, 54.61))
    s.part("Transistor_FET:SUD19P06-60", "Q1", "SUD50P04-08", 96.52, 53.34, {"2": "V12_F", "3": "+12V", "1": "Q1_G"}, 270,
           "Package_TO_SOT_SMD:TO-252-2", "Vishay", "SUD50P04-08-GE3",
           ref_at=(96.52, 45.72), value_at=(96.52, 60.96))
    s.part("Device:D_Zener", "D10", "15V", 111.76, 76.2, {"1": "+12V", "2": "Q1_G"}, 90, FP["SOD123"],
           "Diodes Incorporated", "BZT52C15-7-F", ref_at=(116.84, 74.93), value_at=(116.84, 77.47), value_justify="left")
    s.R("R30", "10k", 96.52, 88.9, "Q1_G", "/GND_BUS")
    s.text("Q1 reverse-polarity P-FET (body diode conducts first, then the channel).\nD10 keeps Vgs under 15 V.",
           81.28, 101.6, 1.0)
    s.part("Device:D_Zener", "D11", "SMBJ15A", 132.08, 76.2, {"1": "+12V", "2": "/GND_BUS"}, 90,
           "Diode_SMD:D_SMB_Handsoldering", "Littelfuse", "SMBJ15A", ref_at=(137.16, 74.93), value_at=(137.16, 77.47),
           value_justify="left")
    s.C("C30", "10uF 25V X7R", 149.86, 76.2, "+12V", "/GND_BUS")
    s.C("C31", "10uF 25V X7R", 162.56, 76.2, "+12V", "/GND_BUS")
    s.flag(172.72, 50.8); s.power("+12V", 172.72, 50.8)
    s.flag(172.72, 99.06, 180); s.glabel("GND_BUS", 172.72, 99.06, 180)

    # bus-side 5 V
    s.part("Converter_DCDC:R-78E5.0-0.5", "U20", "R-78E5.0-0.5", 210.82, 63.5, {"1": "+12V", "2": "/GND_BUS", "3": "/V5_BUS"},
           0, "Converter_DCDC:Converter_DCDC_RECOM_R-78E-0.5_THT", "RECOM", "R-78E5.0-0.5",
           ref_at=(210.82, 55.88), value_at=(210.82, 73.66))
    s.C("C32", "10uF 25V X7R", 233.68, 76.2, "/V5_BUS", "/GND_BUS")
    s.text("V5_BUS: ISO1044 and ISO6740 bus sides (about 300 mA worst case).", 195.58, 91.44, 1.0)
    s.led_chain("D12", "R31", "green", "LTST-C150GKT", 254.0, 63.5, "+12V", rval="4.7k", ground="/GND_BUS")
    s.text("D12: 12 V present.", 248.92, 86.36, 1.0)

    # 12 V status to the MCU
    s.part("Isolator:TLP291", "U21", "TLP293", 205.74, 132.08,
           {"1": "OPTO_A", "2": "/GND_BUS", "4": "V12_OK_C", "3": "GND"}, 0, "Package_SO:SOIC-4_4.55x2.6mm_P1.27mm",
           "Toshiba", "TLP293(TPL,E", ref_at=(205.74, 124.46), value_at=(205.74, 139.7))
    s.R("R32", "10k", 177.8, 124.46, "+12V", "OPTO_A")
    s.R("R33", "10k", 233.68, 119.38, "+3V3", "V12_OK_C")
    s.part("Device:R", "R34", "1k", 248.92, 132.08, {"1": "V12_OK_C", "2": "/V12_OK"}, 90, FP["R"], "Yageo", "RC1206FR-071KL",
           ref_at=(248.92, 128.27), value_at=(248.92, 135.89))
    s.text("V12_OK low = 12 V present (opto on). LED ~1 mA, CTR >= 50 %.", 172.72, 152.4, 1.0)
    return s


def relay_sheet():
    s = Sheet("relay.kicad_sch", "Relay drive", 5, "CAN controller: relay drive")
    s.text("Eight relay outputs: MCU -> ISO6740 (x2) -> ULN2803A (12 V domain). Coils from +12 V only (COM).\n"
           "Each output has its own +12 V terminal and a 12 V-side LED right behind it.", 25.4, 25.4)
    for k in range(2):
        y = 63.5 + k * 71.12
        ins = {"3": "INA", "4": "INB", "5": "INC", "6": "IND"}
        outs = {"14": "OUTA", "13": "OUTB", "12": "OUTC", "11": "OUTD"}
        nets = {"1": "+3V3", "2": "GND", "8": "GND", "7": "~", "9": "/GND_BUS", "15": "/GND_BUS", "16": "/V5_BUS",
                "10": "/V5_BUS"}
        for j, (pi, po) in enumerate(zip(ins, outs)):
            ch = 4 * k + j + 1
            nets[pi] = f"/RLY{ch}"
            nets[po] = f"RLYD{ch}"
        s.part("Isolator:ISO6740", f"U{30 + k}", "ISO6740", 101.6, y, nets, 0, "Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm",
               "Texas Instruments", "ISO6740DWR", ref_at=(101.6, y - 17.78), value_at=(101.6, y + 17.78))
        s.C(f"C{40 + 2 * k}", "100nF 50V X7R", 71.12, y - 15.24, "+3V3", "GND", decouple=True)
        s.C(f"C{41 + 2 * k}", "100nF 50V X7R", 132.08, y - 15.24, "/V5_BUS", "/GND_BUS", decouple=True)
    s.text("EN2 tied high: outputs always enabled. Default output state with VCC1 off: low (relays off).",
           76.2, 210.82, 1.0)
    uln = {str(i): f"RLYD{i}" for i in range(1, 9)}
    uln.update({"9": "/GND_BUS", "10": "V12_RLY"})
    for i in range(1, 9):
        uln[str(19 - i)] = f"RLYO{i}"
    s.part("Transistor_Array:ULN2803A", "U32", "ULN2803A", 190.5, 99.06, uln, 0, "Package_SO:SOIC-18W_7.5x11.6mm_P1.27mm",
           "Texas Instruments", "ULN2803ADWR", ref_at=(190.5, 81.28), value_at=(190.5, 116.84))
    s.part("Device:Polyfuse", "F30", "1.1A", 213.36, 63.5, {"1": "+12V", "2": "V12_RLY"}, 90, FP["PTC"],
           "Littelfuse", "1812L110/16DR", ref_at=(213.36, 59.69), value_at=(213.36, 67.31))
    s.C("C44", "10uF 25V X7R", 228.6, 76.2, "V12_RLY", "/GND_BUS")
    rly = {str(i): f"RLYO{i}" for i in range(1, 9)}
    rly.update({str(8 + i): "V12_RLY" for i in range(1, 9)})
    s.part("Connector_Generic:Conn_02x08_Top_Bottom", "J30", "RELAY", 271.78, 99.06, rly, 0, FP["SPTD"].format(n=8),
           "Phoenix Contact", "1841555", ref_at=(271.78, 83.82), value_at=(271.78, 116.84))
    s.text("J30 (SPTD 1,5/8-H-3,5, double-level push-in): lower level 1-8 = OUT1-8 (ULN2803A low side),\n"
           "upper level 9-16 = +12 V coil supply (F30). Each relay coil goes between OUTn and the +12 V\n"
           "terminal right above it. Max about 300 mA per output, 1.1 A total (F30).", 213.36, 127.0, 1.0)
    for i in range(1, 9):
        x = 50.8 + (i - 1) * 15.24
        s.led_chain(f"D{30 + i}", f"R{40 + i}", "red", "LTST-C150KRKT", x, 233.68, "V12_RLY", rval="4.7k",
                    ground=f"RLYO{i}")
    s.text("Relay LEDs D31-D38 on the 12 V side, right behind their terminals: +12 V -> 4.7k -> LED -> OUTn,\n"
           "lit (~2 mA) when the ULN2803A output is on. Shows the real output state.", 50.8, 264.16, 1.0)
    return s


def gpio_sheet():
    s = Sheet("gpio.kicad_sch", "GPIO", 6, "CAN controller: GPIO")
    s.text("Eight 3.3 V GPIO (MCU pins). Each: 4.7k series + BAT54S clamp to +3V3/GND on the MCU side,\n"
           "so a 24 V short draws ~4.5 mA and the pin stays inside its rails.\n"
           "J40 SPTD double-level push-in: lower level = GPIO1-8, upper level = GND (one ground per channel).",
           25.4, 25.4)
    conn = {}
    for ch in range(1, 9):
        conn[str(ch)] = f"GPIO{ch}_EXT"
        conn[str(8 + ch)] = "GND"
        x = 76.2 + ((ch - 1) % 4) * 30.48
        y = 60.96 + ((ch - 1) // 4) * 101.6
        s.R(f"R{50 + ch}", "4.7k", x, y, f"/GPIO{ch}", f"GPIO{ch}_EXT")
        s.part("Diode:BAT54S", f"D{50 + ch}", "BAT54S", x + 10.16, y + 20.32,
               {"1": "GND", "2": "+3V3", "3": f"/GPIO{ch}"}, 0, FP["SOT23"], "Nexperia", "BAT54S,215",
               ref_at=(x + 15.24, y + 17.78), value_at=(x + 15.24, y + 22.86))
    s.part("Connector_Generic:Conn_02x08_Top_Bottom", "J40", "GPIO", 238.76, 116.84, conn, 0, FP["SPTD"].format(n=8),
           "Phoenix Contact", "1841555", ref_at=(238.76, 101.6), value_at=(238.76, 134.62))
    s.text("J40 lower level: 1 GPIO1 ... 8 GPIO8; upper level 9-16: GND.", 210.82, 143.51, 1.0)
    return s


def ain_sheet():
    s = Sheet("ain.kicad_sch", "Analog in", 7, "CAN controller: analog inputs")
    s.text("Four analog inputs, about +-116 V full scale, 10 Mohm input. MCP3428 (16 bit, I2C 0x68) on the MCU's I2C1.\n"
           "The MCP3428 cannot take inputs below its VSS, so each divider is referenced to VMID (~1.65 V) and CHn- = VMID:\n"
           "CHn+ - CHn- = Vin x 130k / 10.13M (+-1.49 V at +-116 V; PGA range +-2.048 V). VMID cancels in the difference.\n"
           "10M is a 1206 rated 200 V. 0.1 uF across 130k: fc ~ 12 Hz.", 25.4, 25.4)
    adc = {"1": "AIN1", "2": "VMID", "3": "AIN2", "4": "VMID", "11": "AIN3", "12": "VMID", "13": "AIN4", "14": "VMID",
           "5": "GND", "6": "+3V3", "7": "/I2C_SDA", "8": "/I2C_SCL", "9": "GND", "10": "GND"}
    s.part("Analog_ADC:MCP3428x-xSL", "U50", "MCP3428-E/SL", 304.8, 106.68, adc, 0, "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
           "Microchip Technology", "MCP3428-E/SL", ref_at=(304.8, 86.36), value_at=(304.8, 127.0))
    s.C("C50", "100nF 50V X7R", 330.2, 76.2, "+3V3", "GND", decouple=True)
    s.R("R60", "4.7k", 345.44, 99.06, "+3V3", "/I2C_SCL")
    s.R("R61", "4.7k", 358.14, 99.06, "+3V3", "/I2C_SDA")
    s.text("Adr0/Adr1 low: address 0x68. I2C1 pull-ups R60/R61.", 325.12, 134.62, 1.0)
    # VMID
    s.R("R62", "10k", 345.44, 162.56, "+3V3", "VMID")
    s.R("R63", "10k", 345.44, 180.34, "VMID", "GND")
    s.C("C51", "10uF 25V X7R", 360.68, 180.34, "VMID", "GND")
    s.text("VMID = 1.65 V, 5k + 10 uF.", 337.82, 198.12, 1.0)
    for i in range(4):
        n = i + 1
        y = 63.5 + i * 50.8
        s.R(f"R{64 + i}", "10M", 101.6, y, f"/AI{n}_EXT", f"AIN{n}", rot=90)
        s.R(f"R{68 + i}", "130k", 127.0, y + 12.7, f"AIN{n}", "VMID")
        s.C(f"C{52 + i}", "100nF 50V X7R 1206", 142.24, y + 12.7, f"AIN{n}", "VMID")
        s.part("Diode:BAT54S", f"D{50 + 10 + n}", "BAT54S", 162.56, y + 12.7, {"1": "GND", "2": "+3V3", "3": f"AIN{n}"},
               0, FP["SOT23"], "Nexperia", "BAT54S,215", ref_at=(167.64, y + 8.89), value_at=(167.64, y + 16.51))
    s.text("Analog connector J50 is on the analog-out sheet (AI1-4 + GND, AO1-2 + GND).", 76.2, 266.7, 1.0)
    return s


def aout_sheet():
    s = Sheet("aout.kicad_sch", "Analog out", 8, "CAN controller: analog outputs, analog connector")
    s.text("Two 0-10 V outputs. MCP4922 (SPI, 12 bit) with an LM4040 2.5 V reference -> LM358B, gain 4.\n"
           "Op-amp supply V13 = 13 V from a TPS61040 boost on the header 5 V (logic side; no third supply).\n"
           "Output: 470R + 15 V Zener at the terminal, feedback taken after the 470R, so a 24 V short (or the\n"
           "CAN cable 12 V from a wrong plug) puts < 20 mA into the Zener and the output recovers.", 25.4, 25.4)
    dac = {"1": "+3V3", "2": "~", "3": "/DAC_CS", "4": "/DAC_SCK", "5": "/DAC_SDI", "6": "~", "7": "~", "8": "GND",
           "9": "+3V3", "10": "DACB", "11": "VREF", "12": "GND", "13": "VREF", "14": "DACA"}
    s.part("Analog_DAC:MCP4922-EP", "U60", "MCP4922-E/SL", 71.12, 88.9, dac, 0, "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
           "Microchip Technology", "MCP4922-E/SL", ref_at=(71.12, 71.12), value_at=(71.12, 106.68))
    s.C("C60", "100nF 50V X7R", 50.8, 124.46, "+3V3", "GND", decouple=True)
    s.text("LDAC low: outputs update on CS rising. SHDN high.", 50.8, 137.16, 1.0)
    s.part("Reference_Voltage:LM4040DBZ-2.0", "U61", "LM4040-2.5", 116.84, 139.7, {"1": "VREF", "2": "GND", "3": "~"},
           90, FP["SOT23"], "Texas Instruments", "LM4040A25IDBZR", ref_at=(121.92, 138.43), value_at=(121.92, 140.97),
           value_justify="left")
    s.R("R80", "1k", 116.84, 119.38, "+3V3", "VREF")
    s.C("C61", "100nF 50V X7R", 132.08, 139.7, "VREF", "GND", decouple=True)
    # op amp, two channels
    for k, (ain, ch) in enumerate((("DACA", 1), ("DACB", 2))):
        unit = 1 + k
        pins = {1: ("3", "2", "1"), 2: ("5", "6", "7")}[unit]
        y = 76.2 + k * 50.8
        s.part("Amplifier_Operational:LM2904", "U62", "LM358B", 182.88, y,
               {pins[0]: ain, pins[1]: f"FB{ch}", pins[2]: f"OA{ch}"}, 0, "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
               "Texas Instruments", "LM358BIDR", unit=unit, multi=True, ref_at=(182.88, y - 7.62), value_at=(182.88, y + 7.62))
        s.R(f"R{81 + 4 * k}", "470R", 215.9, y, f"OA{ch}", f"AO{ch}_EXT", rot=90)
        s.R(f"R{82 + 4 * k}", "30k", 203.2, y + 17.78, f"AO{ch}_EXT", f"FB{ch}", rot=90)
        s.R(f"R{83 + 4 * k}", "10k", 177.8, y + 22.86, f"FB{ch}", "GND")
        s.part("Device:D_Zener", f"D{70 + ch}", "15V", 233.68, y + 12.7, {"1": f"AO{ch}_EXT", "2": "GND"}, 90, FP["SOD123"],
               "Diodes Incorporated", "BZT52C15-7-F", ref_at=(238.76, y + 11.43), value_at=(238.76, y + 13.97),
               value_justify="left")
    s.part("Amplifier_Operational:LM2904", "U62", "LM358B", 182.88, 182.88, {"8": "V13", "4": "GND"}, 0,
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Texas Instruments", "LM358BIDR", unit=3, multi=True,
           ref_at=(185.42, 175.26), value_at=(185.42, 190.5))
    s.C("C62", "100nF 50V X7R", 198.12, 182.88, "V13", "GND", decouple=True)
    s.text("Gain 1 + 30k/10k = 4: 0-2.5 V -> 0-10 V at the terminal.", 160.02, 160.02, 1.0)

    # 13 V boost
    s.part("Regulator_Switching:TPS61041DDC", "U63", "TPS61040", 116.84, 220.98,
           {"5": "+5V", "4": "+5V", "2": "GND", "1": "SW", "3": "BFB"}, 0, "Package_TO_SOT_SMD:SOT-23-5",
           "Texas Instruments", "TPS61040DBVR", ref_at=(116.84, 210.82), value_at=(116.84, 231.14))
    s.part("Device:L", "L60", "10uH", 116.84, 198.12, {"1": "+5V", "2": "SW"}, 90, "Inductor_SMD:L_Bourns-SRN4018",
           "Bourns", "SRN4018-100M", ref_at=(116.84, 194.31), value_at=(116.84, 201.93))
    s.part("Device:D_Schottky", "D73", "MBR0530", 147.32, 205.74, {"2": "SW", "1": "V13"}, 0, FP["SOD123"],
           "onsemi", "MBR0530T1G", ref_at=(147.32, 201.93), value_at=(147.32, 209.55))
    s.R("R90", "1M", 165.1, 215.9, "V13", "BFB")
    s.R("R91", "105k", 165.1, 233.68, "BFB", "GND")
    s.C("C63", "4.7uF 25V X7R", 180.34, 223.52, "V13", "GND")
    s.C("C64", "10uF 25V X7R", 86.36, 223.52, "+5V", "GND")
    s.text("V13 = 1.233 V x (1 + 1M/105k) = 13.0 V. About 50 mA from the header 5 V at full AO load.", 101.6, 248.92, 1.0)
    s.flag(175.26, 205.74); s.llabel("V13", 175.26, 205.74, 0)

    # analog connector: AI1-4 + GND, AO1-2 + GND
    conn = {"1": "/AI1_EXT", "2": "/AI2_EXT", "3": "/AI3_EXT", "4": "/AI4_EXT", "5": "AO1_EXT", "6": "AO2_EXT"}
    conn.update({str(6 + k): "GND" for k in range(1, 7)})
    s.part("Connector_Generic:Conn_02x06_Top_Bottom", "J50", "ANALOG", 304.8, 101.6, conn, 0, FP["SPTD"].format(n=6),
           "Phoenix Contact", "1841539", ref_at=(304.8, 88.9), value_at=(304.8, 116.84))
    s.text("J50 SPTD double-level push-in: lower level 1-4 AI1-AI4, 5 AO1, 6 AO2;\nupper level 7-12 GND.",
           276.86, 134.62, 1.0)
    return s


SHEETS = [mcu_sheet, can_sheet, power12_sheet, relay_sheet, gpio_sheet, ain_sheet, aout_sheet]


def main():
    sheets = [f() for f in SHEETS]
    for sh in sheets:
        (HW / sh.file).write_text(sh.render())
    (HW / "can-controller.kicad_sch").write_text(root_sheet(sheets, "CAN Controller"))
    print("wrote", [sh.file for sh in sheets])


if __name__ == "__main__":
    main()
