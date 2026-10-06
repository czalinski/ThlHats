#!/usr/bin/env python3
"""Bootstrap generator for the can-controller hierarchical schematic.

Root sheet + one sub-sheet per functional block. Nets between blocks use
global labels (names written with a leading "/"); nets inside a block use
local labels placed on pin ends. Power symbols: +3V3, +5V, GND (LOGIC domain,
floating, fed by the isolated DC-DC) and +12V (RACK domain, after input
protection). The RACK ground is the global net GND_RACK; each CAN bus has its
own floating ground GND_CANn (sheet-local). Scope of 2026-10-06 (requirements 4.1).

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
    "FB": "Inductor_SMD:L_1206_3216Metric_Pad1.22x1.90mm_HandSolder",
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
    "330R": ("Yageo", "RC1206FR-07330RL"), "49.9R": ("Yageo", "RC1206FR-0749R9L"), "12k": ("Yageo", "RC1206FR-0712KL"),
    "300R": ("Yageo", "RC1206FR-07300RL"), "0R": ("Yageo", "RC1206JR-070RL"),
    "1uF 50V X7R": ("Murata", "GRM31MR71H105KA88L"),
    "3.3uF 25V X7R": ("TBD", "TBD (3.3 uF 25 V X7R 1206)"),
    "8pF 50V C0G": ("TBD", "TBD (8 pF 50 V C0G 0805, to suit the 25 MHz crystal)"),
    "1nF 2kV X7R": ("KEMET", "C1206C102KGRACTU"),
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
    sch.text("Requirements: docs/requirements.md 3 and 4.1. Floorplan and parts: boards/can-controller/README.md.\n"
             "Six domains: RACK (12 V DIN supply, GND_RACK), LOGIC (floating: +5V/+3V3/GND), CAN1-CAN4 (each floating).\n"
             "Crossings: TDN 5-2411WI (RACK->LOGIC power), ISOW1044 x4 (LOGIC->CANn), AQW212 x2 (LOGIC->RACK relays),\n"
             "Ethernet magnetics (LOGIC->host), CAN1 POWERED jumpers JP5/JP6 (RACK->CAN1, optional).", 25.4, 38.1)
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

# PIC32MK1024MCM064 pin map (TQFP-64), scope of 2026-10-06 (Ethernet, ISOW1044, PhotoMOS relays).
# PPS groups per DS60001519E Tables 13-1 / 13-2:
#   C1RX RPB2 (in grp 3) / C1TX RPB3 (out grp 1), C2RX RPA1 (in 2) / C2TX RPB0 (out 4),
#   C3RX RPC0 (in 1) / C3TX RPC1 (out 3), C4RX RPE15 (in 4) / C4TX RPA8 (out 2),
#   SPI3: SCK3 RPC9 (out 4), SDO3 RPC8 (out 2), SDI3 RPC7 (in 1); U1TX RPF1 (out 1), U1RX RPC6 (in 3).
# OA5 follower: IN+ RA4 (33) from the VMID divider, IN- RB9 (49) tied to OUT RB7 (46) = VMID = AN25.
# Firmware: disable JTAG (RA7/RA8/RB9/RA10), ICESEL = PGx2, drive unused pins low.
MCU_NETS = {
    "1": "~", "2": "/RLY1", "3": "/RLY2", "4": "/RLY3", "5": "/RLY4",
    "6": "/LED_CAN1", "7": "MCLR", "8": "/LED_CAN2", "11": "/LED_CAN3", "12": "/LED_CAN4",
    "13": "~", "14": "/C2RX", "15": "/C2TX", "16": "~", "17": "/C1RX", "18": "/C1TX",
    "21": "/C3RX", "22": "/C3TX", "23": "/AI2N", "24": "/AI2P", "27": "/AI1P", "28": "/AI1N",
    "29": "~", "30": "/C4RX", "31": "/C4TX", "32": "~", "33": "/VMID_REF",
    "34": "GND", "36": "USB_DN", "37": "USB_DP", "39": "OSC1", "40": "OSC2", "42": "LED_HB",
    "43": "PGD2", "44": "PGC2", "45": "~", "46": "/VMID", "47": "~", "48": "~", "49": "/VMID",
    "50": "U1RX", "51": "/ETH_MISO", "52": "/ETH_MOSI", "53": "/ETH_CS", "54": "/ETH_INT", "55": "/ETH_SCK",
    "58": "/ETH_RST", "59": "U1TX", "60": "/GPIO1", "61": "/GPIO2", "62": "/GPIO3", "63": "/GPIO4", "64": "~",
    # power: VUSB3V3 to VDD and VBUS to VSS (USB unused, DS60001519E Table 1-x)
    "10": "+3V3", "26": "+3V3", "38": "+3V3", "57": "+3V3", "35": "+3V3", "19": "AVDD",
    "9": "GND", "25": "GND", "41": "GND", "56": "GND", "20": "GND",
}


def mcu_sheet():
    s = Sheet("mcu.kicad_sch", "MCU, logic power", 2, "CAN controller: MCU and logic power")
    s.text("LOGIC DOMAIN (floating). +5V from the isolated DC-DC (power sheet) -> 3.3 V LDO.\n"
           "USB is not used: VUSB3V3 to VDD, VBUS to VSS, D+/D- through 10k to VSS (DS60001519E).", 25.4, 25.4)

    # --- 3.3 V LDO ------------------------------------------------------------
    s.part("Regulator_Linear:MCP1826S", "U2", "MCP1826S-3302E/DB", 63.5, 60.96,
           {"1": "+5V", "2": "GND", "3": "+3V3"}, 0, "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
           "Microchip Technology", "MCP1826S-3302E/DB", ref_at=(63.5, 53.34), value_at=(63.5, 69.85))
    s.C("C1", "10uF 25V X7R", 45.72, 76.2, "+5V", "GND")
    s.C("C2", "10uF 25V X7R", 83.82, 76.2, "+3V3", "GND")
    s.text("Load about 0.4 A worst case (W6100 up to 265 mA on a 10 Mbit link):\n"
           "(5 - 3.3) V x 0.4 A = 0.7 W in the SOT-223; give the tab copper.", 40.64, 91.44, 1.0)
    s.led_chain("D1", "R1", "green", "LTST-C150GKT", 101.6, 60.96, "+3V3")
    s.text("D1: 3.3 V present.", 96.52, 83.82, 1.0)

    # --- MCU --------------------------------------------------------------------
    mx, my = 254.0, 139.7
    s.part(MCU, "U1", "PIC32MK1024MCM064-I/PT", mx, my, MCU_NETS, 0, "Package_QFP:TQFP-64_10x10mm_P0.5mm",
           "Microchip Technology", "PIC32MK1024MCM064-I/PT", ref_at=(mx + 22.86, my - 50.8),
           value_at=(mx + 22.86, my + 50.8))
    for i, x in enumerate((152.4, 167.64, 182.88, 198.12, 213.36)):
        s.C(f"C{3 + i}", "100nF 50V X7R", x, 45.72, "+3V3", "GND", decouple=True)
    s.C("C8", "10uF 25V X7R", 228.6, 45.72, "+3V3", "GND")
    s.text("C3-C6 at the four VDD pins, C7 at VUSB3V3, C8 bulk.", 152.4, 33.02, 1.0)
    # AVDD filter: the ADC now measures the analog inputs
    s.part("Device:FerriteBead", "FB1", "HI1206P121R-10", 101.6, 116.84, {"1": "+3V3", "2": "AVDD"}, 90,
           FP["FB"], "Laird", "HI1206P121R-10", ref_at=(101.6, 113.03), value_at=(101.6, 120.65))
    s.C("C9", "100nF 50V X7R", 116.84, 129.54, "AVDD", "GND", decouple=True)
    s.C("C10", "1uF 50V X7R", 129.54, 129.54, "AVDD", "GND")
    s.text("AVDD through FB1 (ADC reference = AVDD).", 96.52, 142.24, 1.0)
    s.flag(129.54, 116.84); s.llabel("AVDD", 129.54, 116.84, 0)

    # crystal
    s.part("Device:Crystal", "Y1", "12MHz", 345.44, 116.84, {"1": "OSC1", "2": "OSC2"}, 0,
           "Crystal:Crystal_SMD_5032-2Pin_5.0x3.2mm_HandSoldering", "TBD", "TBD (12 MHz, 5032, CL 18 pF)",
           ref_at=(345.44, 113.03), value_at=(345.44, 121.92))
    s.C("C11", "27pF 50V C0G", 335.28, 129.54, "OSC1", "GND")
    s.C("C12", "27pF 50V C0G", 355.6, 129.54, "OSC2", "GND")
    s.text("12 MHz, CL 18 pF (POSC HS).", 332.74, 104.14, 1.0)

    # USB unused
    s.R("R2", "10k", 345.44, 162.56, "USB_DP", "GND")
    s.R("R3", "10k", 360.68, 162.56, "USB_DN", "GND")

    # MCLR + ICSP
    s.R("R4", "10k", 63.5, 162.56, "+3V3", "MCLR")
    s.C("C13", "100nF 50V X7R", 76.2, 175.26, "MCLR", "GND", decouple=True)
    s.part("Connector_Generic:Conn_01x06", "J2", "ICSP", 38.1, 177.8,
           {"1": "MCLR", "2": "+3V3", "3": "GND", "4": "PGD2", "5": "PGC2", "6": "~"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", "Samtec", "TSW-106-07-G-S",
           ref_at=(38.1, 170.18), value_at=(38.1, 187.96))
    s.text("ICSP (PICkit / ICD / Snap): 1 MCLR, 2 VDD, 3 VSS, 4 PGD2, 5 PGC2. Firmware updates load here.",
           25.4, 195.58, 1.0)

    # debug UART
    s.part("Connector_Generic:Conn_01x03", "J3", "UART", 38.1, 218.44, {"1": "U1TX", "2": "U1RX", "3": "GND"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", "Samtec", "TSW-103-07-G-S",
           ref_at=(38.1, 213.36), value_at=(38.1, 224.79))
    s.text("Debug UART (3.3 V): 1 TX from MCU, 2 RX to MCU, 3 GND.", 25.4, 233.68, 1.0)

    s.led_chain("D2", "R5", "green", "LTST-C150GKT", 360.68, 50.8, "LED_HB")
    s.text("D2 heartbeat.", 355.6, 76.2, 1.0)
    return s


def eth_sheet():
    s = Sheet("ethernet.kicad_sch", "Ethernet", 3, "CAN controller: Ethernet (W6100)")
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
    # supplies
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
    # bias, crystal
    s.R("R14", "12k", 228.6, 157.48, "RSET", "RSET2")
    s.R("R15", "300R", 228.6, 175.26, "RSET2", "GND")
    s.part("Device:Crystal", "Y2", "25MHz", 254.0, 190.5, {"1": "XSCI", "2": "XSCO"}, 0,
           "Crystal:Crystal_SMD_5032-2Pin_5.0x3.2mm_HandSoldering", "TBD", "TBD (25 MHz, 5032, CL 12 pF)",
           ref_at=(254.0, 186.69), value_at=(254.0, 195.58))
    s.R("R16", "1M", 254.0, 205.74, "XSCI", "XSCO", rot=90)
    s.C("C30", "8pF 50V C0G", 243.84, 213.36, "XSCI", "GND")
    s.C("C31", "8pF 50V C0G", 264.16, 213.36, "XSCO", "GND")
    # MDI termination
    s.R("R17", "49.9R", 279.4, 116.84, "TXP", "TXCT")
    s.R("R18", "49.9R", 279.4, 134.62, "TXCT", "TXN")
    s.C("C32", "100nF 50V X7R", 294.64, 129.54, "TXCT", "GND", decouple=True)
    s.R("R19", "49.9R", 279.4, 160.02, "RXP", "RXCT")
    s.R("R20", "49.9R", 279.4, 177.8, "RXCT", "RXN")
    s.C("C33", "100nF 50V X7R", 294.64, 172.72, "RXCT", "GND", decouple=True)
    s.text("R17-R20 and C32/C33 right at the W6100 MDI pins.", 269.24, 190.5, 1.0)
    # jack
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


def can_sheet():
    s = Sheet("can.kicad_sch", "CAN x4", 4, "CAN controller: four isolated CAN FD channels")
    s.text("Four CAN FD channels, each isolated on its own (TI ISOW1044, integrated isolated DC-DC).\n"
           "Logic side: VIO +3V3, VDD +5V, GND. Bus side n: GND_CANn floats (no assumption about the DUT).\n"
           "Per TI: VISOOUT/VSIN -> bead -> VISOIN, GND2 -> bead -> GISOIN (CISPR 32 class B on 2 layers).\n"
           "Connector pinout as every ThlHats board: 1 CANH, 2 CANL, 3 GND (bus), 4 +12 V cable supply.\n"
           "CAN1 (the can-ssr bus) has the POWERED jumpers: JP5 ties GND_CAN1 to GND_RACK, JP6 feeds +12 V\n"
           "through F10. Without them CAN1 floats like the others. CAN2-4 pin 4 is not connected.", 25.4, 25.4)
    term = FP["MC"].format(n=4)
    for i in range(4):
        n = i + 1
        y0 = 50.8 + i * 55.88
        x0 = 50.8
        s.text(f"CAN{n}", x0 - 25.4, y0 - 5.08, 2.0)
        nets = {"1": "+3V3", "2": "~", "3": f"/C{n}TX", "4": "GND", "5": f"/C{n}RX", "6": "GND", "7": "~",
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
               {"1": f"CANH{n}", "2": f"TERM{n}"}, 0, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
               "Samtec", "TSW-102-07-G-S", ref_at=(x0 + 190.5, y0 - 1.27), value_at=(x0 + 190.5, y0 + 6.35))
        s.R(f"R{30 + i}", "120R", x0 + 205.74, y0 + 12.7, f"TERM{n}", f"CANL{n}")
        pin4 = "V12_CAN1" if n == 1 else "~"
        s.part("Connector:Screw_Terminal_01x04", f"J{10 + n}", f"CAN{n}", x0 + 254.0, y0 + 12.7,
               {"1": f"CANH{n}", "2": f"CANL{n}", "3": f"GND_CAN{n}", "4": pin4}, 0, term,
               "Phoenix Contact", "1844236", ref_at=(x0 + 254.0, y0 + 5.08), value_at=(x0 + 254.0, y0 + 21.59))
        s.led_chain(f"D{20 + i}", f"R{34 + i}", "yellow", "LTST-C150YKT", x0 - 12.7, y0 + 7.62, f"/LED_CAN{n}")
    # CAN1 powered-bus option
    s.part("Jumper:Jumper_2_Open", "JP5", "POWERED GND", 381.0, 66.04, {"1": "GND_CAN1", "2": "/GND_RACK"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "Samtec", "TSW-102-07-G-S",
           ref_at=(381.0, 62.23), value_at=(381.0, 69.85))
    s.part("Device:Polyfuse", "F10", "2A", 355.6, 45.72, {"1": "+12V", "2": "V12_F10"}, 90, FP["PTC"],
           "Bourns", "MF-MSMF200/16X-2", ref_at=(355.6, 41.91), value_at=(355.6, 49.53))
    s.part("Jumper:Jumper_2_Open", "JP6", "POWERED 12V", 381.0, 45.72, {"1": "V12_F10", "2": "V12_CAN1"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "Samtec", "TSW-102-07-G-S",
           ref_at=(381.0, 41.91), value_at=(381.0, 49.53))
    s.text("CAN1 POWERED: fit JP5 + JP6 together on the can-ssr bus\n"
           "(up to 4 can-ssr at ~0.2 A each; F10 2 A hold).\n"
           "F10 and JP5/JP6 sit at the RACK | CAN1 boundary on the board.", 340.36, 78.74, 1.0)
    s.text("JP1-JP4: fit the shunt (Samtec SNT-100-BK-G) only where this board is a bus end.\n"
           "Activity LEDs D20-D23 are on the logic side, driven by the MCU.", 25.4, 271.78, 1.0)
    return s


def power_sheet():
    s = Sheet("power.kicad_sch", "12 V input, logic supply", 5, "CAN controller: 12 V input and isolated logic supply")
    s.text("RACK DOMAIN: external 12 V DIN supply (floating output); its 0 V is GND_RACK. Reverse polarity: P-FET Q1.\n"
           "Transients: TVS D31. Fuse F20. Feeds the relay outputs, the CAN1 cable supply and U20.\n"
           "U20 (TRACO TDN 5-2411WI, 9-36 V in, 5 V 1 A, 1600 VDC) makes the floating LOGIC +5V / GND.", 25.4, 25.4)
    s.part("Connector:Screw_Terminal_01x02", "J20", "12V IN", 38.1, 71.12, {"1": "V12_IN", "2": "/GND_RACK"}, 0,
           "Connector_Phoenix_MSTB:PhoenixContact_MSTBVA_2,5_2-G-5,08_1x02_P5.08mm_Vertical", "Phoenix Contact",
           "1755736", ref_at=(38.1, 64.77), value_at=(38.1, 77.47))
    s.text("J20: top entry, 1 +12 V, 2 0 V.", 25.4, 86.36, 1.0)
    s.part("Device:Fuse", "F20", "4A", 63.5, 58.42, {"1": "V12_IN", "2": "V12_F"}, 90,
           "Fuse:Fuse_Littelfuse-NANO2-451_453", "Littelfuse", "0451004.MRL", ref_at=(63.5, 54.61),
           value_at=(63.5, 62.23))
    s.part("Transistor_FET:SUD19P06-60", "Q1", "SUD50P04-08", 96.52, 60.96, {"2": "V12_F", "3": "+12V", "1": "Q1_G"},
           270, "Package_TO_SOT_SMD:TO-252-2", "Vishay", "SUD50P04-08-GE3", ref_at=(96.52, 53.34),
           value_at=(96.52, 68.58))
    s.part("Device:D_Zener", "D30", "15V", 111.76, 83.82, {"1": "+12V", "2": "Q1_G"}, 90, FP["SOD123"],
           "Diodes Incorporated", "BZT52C15-7-F", ref_at=(116.84, 82.55), value_at=(116.84, 85.09),
           value_justify="left")
    s.R("R40", "10k", 96.52, 96.52, "Q1_G", "/GND_RACK")
    s.part("Device:D_Zener", "D31", "SMBJ15A", 132.08, 83.82, {"1": "+12V", "2": "/GND_RACK"}, 90,
           "Diode_SMD:D_SMB_Handsoldering", "Littelfuse", "SMBJ15A", ref_at=(137.16, 82.55),
           value_at=(137.16, 85.09), value_justify="left")
    s.C("C60", "10uF 25V X7R", 149.86, 83.82, "+12V", "/GND_RACK")
    s.C("C61", "10uF 25V X7R", 162.56, 83.82, "+12V", "/GND_RACK")
    s.flag(172.72, 58.42); s.power("+12V", 172.72, 58.42)
    s.flag(172.72, 106.68, 180); s.glabel("GND_RACK", 172.72, 106.68, 180)
    s.led_chain("D32", "R41", "green", "LTST-C150GKT", 187.96, 63.5, "+12V", rval="4.7k", ground="/GND_RACK")
    s.text("D32: 12 V present (rack side).", 182.88, 86.36, 1.0)
    # isolated logic supply
    s.part("Regulator_Switching:TDN_5-0910WISM", "U20", "TDN 5-2411WI", 238.76, 71.12,
           {"1": "+12V", "2": "/GND_RACK", "4": "~", "5": "~", "6": "GND", "7": "+5V"}, 0,
           "Converter_DCDC:Converter_DCDC_TRACO_TDN_5-xxxxWI_THT", "TRACO Power", "TDN 5-2411WI",
           ref_at=(238.76, 60.96), value_at=(238.76, 81.28))
    s.C("C62", "10uF 25V X7R", 215.9, 88.9, "+12V", "/GND_RACK")
    s.C("C63", "10uF 25V X7R", 264.16, 88.9, "+5V", "GND")
    s.text("U20 crosses RACK | LOGIC. Remote On/Off (pin 4) open = on. No traces under it (TRACO).\n"
           "LOGIC budget: about 0.65 A typical, 0.8 A with all four CAN buses dominant (1 A rating).",
           210.82, 106.68, 1.0)
    return s


def relay_sheet():
    s = Sheet("relay.kicad_sch", "Relay drive", 6, "CAN controller: relay drive")
    s.text("Four relay outputs for standard 12 V coil relays. 2 x AQW212 PhotoMOS (2 Form A): the LED side is LOGIC,\n"
           "driven from MCU pins through 470R (~4.5 mA, operate <= 3 mA); the contact sources +12 V (V12_RLY, fused by F30)\n"
           "to OUTn. Coil between OUTn and 0 V (GND_RACK) on the same terminal pair. D40-D43 catch the coil kick.\n"
           "Red LEDs D44-D47 on the rack side show the real output state.", 25.4, 25.4)
    s.part("Device:Polyfuse", "F30", "1.1A", 152.4, 60.96, {"1": "+12V", "2": "V12_RLY"}, 90, FP["PTC"],
           "Littelfuse", "1812L110/16DR", ref_at=(152.4, 57.15), value_at=(152.4, 64.77))
    s.C("C70", "10uF 25V X7R", 172.72, 76.2, "V12_RLY", "/GND_RACK")
    for k in range(2):
        y = 106.68 + k * 60.96
        a, b = 2 * k + 1, 2 * k + 2
        s.part("Thl_Isolator:AQW212", f"K{1 + k}", "AQW212", 127.0, y,
               {"1": f"RLED{a}", "2": "GND", "3": f"RLED{b}", "4": "GND",
                "8": "V12_RLY", "7": f"RLYOUT{a}", "6": "V12_RLY", "5": f"RLYOUT{b}"}, 0,
               "Package_DIP:DIP-8_W7.62mm", "Panasonic", "AQW212", ref_at=(127.0, y - 12.7), value_at=(127.0, y + 12.7))
        for ch, dy in ((a, -2.54), (b, 5.08)):
            s.R(f"R{50 + ch}", "470R", 88.9, y + dy, f"/RLY{ch}", f"RLED{ch}", rot=90)
    s.text("AQW212 pins: 1/2 LED1, 3/4 LED2, 8-7 output 1, 6-5 output 2.", 101.6, 190.5, 1.0)
    conn = {}
    for ch in range(1, 5):
        x = 190.5 + (ch - 1) * 25.4
        s.part("Device:D", f"D{39 + ch}", "S1G", x, 129.54, {"1": f"RLYOUT{ch}", "2": "/GND_RACK"}, 90,
               "Diode_SMD:D_SMA_Handsoldering", "Diodes Incorporated", "S1G-13-F",
               ref_at=(x + 5.08, 128.27), value_at=(x + 5.08, 130.81), value_justify="left")
        s.led_chain(f"D{43 + ch}", f"R{54 + ch}", "red", "LTST-C150KRKT", x, 154.94, f"RLYOUT{ch}", rval="4.7k",
                    ground="/GND_RACK")
        conn[str(ch)] = f"RLYOUT{ch}"
        conn[str(4 + ch)] = "/GND_RACK"
    s.part("Connector_Generic:Conn_02x04_Top_Bottom", "J30", "RELAY", 330.2, 129.54, conn, 0, FP["SPTD"].format(n=4),
           "Phoenix Contact", "1841513", ref_at=(330.2, 119.38), value_at=(330.2, 140.97))
    s.text("J30 (SPTD 1,5/4-H-3,5): lower level 1-4 = OUT1-4 (+12 V when on), upper level 5-8 = 0 V.\n"
           "Coil current up to about 100 mA each; 0.5 A per AQW212 channel, F30 1.1 A total.", 299.72, 152.4, 1.0)
    return s


def io_sheet():
    s = Sheet("io.kicad_sch", "GPIO, analog in", 7, "CAN controller: GPIO and differential analog inputs")
    s.text("Four 3.3 V GPIO (MCU pins): 330R series + BAT54S clamp, ESD protection only (not 24 V tolerant).\n"
           "Two differential analog inputs, about +-116 V per input, 10 Mohm per input: each leg 10M / 130k to VMID,\n"
           "0.1 uF across 130k (fc ~ 12 Hz), BAT54S clamp; the PIC32 ADC reads both legs and firmware subtracts.\n"
           "VMID = 1.65 V: R60/R61 divider into OA5 IN+ (pin 33), OA5 follower output on pin 46 (= AN25).",
           25.4, 25.4)
    conn = {}
    for ch in range(1, 5):
        x = 63.5 + (ch - 1) * 45.72
        s.R(f"R{70 + ch}", "330R", x, 63.5, f"/GPIO{ch}", f"GPIO{ch}_EXT")
        s.part("Diode:BAT54S", f"D{50 + ch}", "BAT54S", x + 10.16, 86.36,
               {"1": "GND", "2": "+3V3", "3": f"/GPIO{ch}"}, 0, FP["SOT23"], "Nexperia", "BAT54S,215",
               ref_at=(x + 15.24, 83.82), value_at=(x + 15.24, 88.9))
        conn[str(ch)] = f"GPIO{ch}_EXT"
        conn[str(6 + ch)] = "GND"
    legs = (("AI1P", "/AI1P"), ("AI1N", "/AI1N"), ("AI2P", "/AI2P"), ("AI2N", "/AI2N"))
    for i, (ext, adc) in enumerate(legs):
        y = 127.0 + i * 38.1
        s.R(f"R{80 + i}", "10M", 76.2, y, f"{ext}_EXT", adc, rot=90)
        s.R(f"R{84 + i}", "130k", 101.6, y + 12.7, adc, "/VMID")
        s.C(f"C{80 + i}", "100nF 50V X7R 1206", 116.84, y + 12.7, adc, "/VMID")
        s.part("Diode:BAT54S", f"D{55 + i}", "BAT54S", 137.16, y + 12.7, {"1": "GND", "2": "+3V3", "3": adc},
               0, FP["SOT23"], "Nexperia", "BAT54S,215", ref_at=(142.24, y + 8.89), value_at=(142.24, y + 16.51))
    conn.update({"5": "AI1P_EXT", "6": "AI2P_EXT", "11": "AI1N_EXT", "12": "AI2N_EXT"})
    s.part("Connector_Generic:Conn_02x06_Top_Bottom", "J40", "IO", 304.8, 101.6, conn, 0, FP["SPTD"].format(n=6),
           "Phoenix Contact", "1841539", ref_at=(304.8, 88.9), value_at=(304.8, 116.84))
    s.text("J40 SPTD double-level push-in: lower level 1-4 GPIO1-4, 5 AI1+, 6 AI2+;\n"
           "upper level 7-10 GND, 11 AI1-, 12 AI2-.", 276.86, 129.54, 1.0)
    # VMID reference
    s.R("R60", "10k", 228.6, 175.26, "+3V3", "/VMID_REF")
    s.R("R61", "10k", 228.6, 193.04, "/VMID_REF", "GND")
    s.C("C84", "100nF 50V X7R", 243.84, 193.04, "/VMID_REF", "GND", decouple=True)
    s.text("VMID_REF -> MCU pin 33 (OA5 IN+). The MCU ties OA5 IN- (49) to OUT (46) = VMID.", 213.36, 210.82, 1.0)
    return s


SHEETS = [mcu_sheet, eth_sheet, can_sheet, power_sheet, relay_sheet, io_sheet]


def main():
    for old in ("power12.kicad_sch", "gpio.kicad_sch", "ain.kicad_sch", "aout.kicad_sch"):
        if (HW / old).exists():
            (HW / old).unlink()
    sheets = [f() for f in SHEETS]
    for sh in sheets:
        (HW / sh.file).write_text(sh.render())
    (HW / "can-controller.kicad_sch").write_text(root_sheet(sheets, "CAN Controller"))
    print("wrote", [sh.file for sh in sheets])


if __name__ == "__main__":
    main()
