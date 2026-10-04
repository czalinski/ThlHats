#!/usr/bin/env python3
"""Bootstrap generator for the can-ssr hierarchical schematic.

Root sheet + one sub-sheet per functional block. Nets between blocks use
global labels; nets inside a block use local labels placed on pin ends.

This writes can-ssr.kicad_sch and every sub-sheet from scratch. It is only
for the initial capture, block by block: once anyone edits the schematic in
KiCad, stop using it (or the edits are lost) and continue in KiCad.

  python3 boards/can-ssr/hardware/gen_schematic.py
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

HW = REPO / "boards/can-ssr/hardware"
PROJECT = "can-ssr"
ROOT_UUID = re.search(r'\(uuid "([^"]+)"\)', (HW / "can-ssr.kicad_sch").read_text()).group(1)

FP = {
    "R": "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder",
    "C": "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder",
    "Cd": "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder",
    "LED": "LED_SMD:LED_1206_3216Metric_Pad1.42x1.75mm_HandSolder",
}
MPN = {
    "10k": ("Yageo", "RC1206FR-0710KL"), "1k": ("Yageo", "RC1206FR-071KL"),
    "120R": ("Yageo", "RC1206FR-07120RL"), "47k": ("Yageo", "RC1206FR-0747KL"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
    "27pF 50V C0G": ("Murata", "GRM2165C1H270JA01D"),
    "10R": ("Yageo", "RC1206FR-0710RL"), "1M": ("Yageo", "RC1206FR-071ML"), "10M": ("Yageo", "RC1206FR-0710ML"),
    "68nF 630V X7R": ("TDK", "C3225X7R2J683K250AA"),
    "100R": ("Yageo", "RC1206FR-07100RL"), "100k": ("Yageo", "RC1206FR-07100KL"),
    "16.2k": ("Yageo", "RC1206FR-0716K2L"), "4.7k": ("Yageo", "RC1206FR-074K7L"),
    "332k": ("Yageo", "RC1206FR-07332KL"), "8.06k": ("Yageo", "RC1206FR-078K06L"), "20k": ("Yageo", "RC1206FR-0720KL"),
    "680R": ("Yageo", "RC1206FR-07680RL"), "1nF 50V C0G": ("Murata", "GRM2165C1H102JA01D"),
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
        self.refs = []

    # instance path for symbols on this sheet
    def symbol(self, lib_id, ref, value, x, y, rot=0, footprint="", **kw):
        root = self.root
        self.root = ROOT_UUID + "/" + self.sheet_uuid
        u = super().symbol(lib_id, ref, value, x, y, rot, footprint, **kw)
        self.root = root
        if not ref.startswith("#"):
            self.refs.append(ref)
        return u

    def pin_end(self, lib_id, x, y, rot, num):
        px, py, ang = pin_table(lib_id)[num]
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        rx, ry = px * c - py * s, px * s + py * c
        out = (ang + rot + 180) % 360  # direction away from the body (y up)
        return rnd(x + rx), rnd(y - ry), out

    def junction(self, x, y):
        self.items.append(f"\t(junction\n\t\t(at {x:g} {y:g})\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n"
                          f"\t\t(uuid {q(uid())})\n\t)\n")

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
        """Power symbol on a 2.54 mm stub leaving the pin in direction out."""
        dx, dy = {0: (2.54, 0), 180: (-2.54, 0), 90: (0, -2.54), 270: (0, 2.54)}[out]
        ex, ey = rnd(x + dx), rnd(y + dy)
        self.wire(x, y, ex, ey)
        gnd = name.startswith("GND")
        rot = ({270: 0, 90: 180, 180: 270, 0: 90} if gnd else {90: 0, 270: 180, 180: 90, 0: 270})[out]
        self.power(name, ex, ey, rot)

    def part(self, lib_id, ref, value, x, y, nets, rot=0, footprint="", mfr=None, mpn=None, glob=(),
             fields_extra=None, unit=1, **kw):
        """Place a symbol and attach a net to each pin: '~' = no connect,
        names starting with + or GND = power symbol, names in glob = global label."""
        pins = pin_table(lib_id)
        fields = {}
        if mpn:
            fields = {"Manufacturer": mfr, "MPN": mpn}
        fields.update(fields_extra or {})
        multi = kw.pop("multi", False) or unit != 1  # multi-unit: list only this unit's pins
        self.symbol(lib_id, ref, value, x, y, rot, footprint, pins=list(nets) if multi else list(pins),
                    fields=fields, **kw)
        if unit != 1:
            self.items[-1] = self.items[-1].replace("(unit 1)", f"(unit {unit})")
        for num, net in nets.items():
            px, py, out = self.pin_end(lib_id, x, y, rot, num)
            if net == "":
                continue
            if net == "~":
                self.no_connect(px, py)
            elif net.startswith("+") or net.startswith("GND"):
                self.pwrsym(net, px, py, out)
            elif net in glob or net.startswith("/"):
                self.glabel(net.lstrip("/"), px, py, out)
            else:
                self.llabel(net, px, py, out)

    def R(self, ref, value, x, y, n1, n2, rot=0, glob=()):
        mfr, mpn = MPN[value]
        if rot == 90:
            at = dict(ref_at=(x, y - 2.54), value_at=(x, y + 2.54))
        else:
            at = dict(ref_at=(x + 2.54, y - 1.27), value_at=(x + 2.54, y + 1.27), value_justify="left")
        self.part("Device:R", ref, value, x, y, {"1": n1, "2": n2}, rot, FP["R"], mfr, mpn, glob, **at)

    def C(self, ref, value, x, y, n1, n2, decouple=False, glob=(), fp=None):
        mfr, mpn = MPN[value]
        self.part("Device:C", ref, value, x, y, {"1": n1, "2": n2}, 0, fp or FP["Cd" if decouple or "pF" in value else "C"],
                  mfr, mpn, glob, ref_at=(x + 2.54, y - 1.27), value_at=(x + 2.54, y + 1.27), value_justify="left")

    def render(self):
        text = super().render()
        text = text.replace('(paper "A4")', '(paper "A3")')
        text = text.replace(f'(uuid {q(self.root)})', f'(uuid {q(self.own_uuid)})', 1)
        # sub-sheets carry no sheet_instances
        text = re.sub(r'\t\(sheet_instances.*?\n\t\)\n', '', text, flags=re.S)
        return text


def root_sheet(sheets, title):
    sch = nb.Sch(PROJECT, title, "A")
    sch.root = ROOT_UUID
    sch.text(title, 25.4, 30.48, 2.54)
    sch.text("Requirements: docs/requirements.md 4.2. One PCB, three builds (HC/STD/HV): only the four\n"
             "MOSFETs and the build resistor differ. See boards/can-ssr/README.md.", 25.4, 38.1)
    blocks = []
    for i, sh in enumerate(sheets):
        x, y, w, h = 30.48 + (i % 3) * 60.96, 55.88 + (i // 3) * 40.64, 50.8, 25.4
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

def can_logic():
    s = Sheet("can_logic.kicad_sch", "CAN, power, MCU", 2, "CAN SSR: CAN, power, MCU")

    # --- CAN connectors (daisy chain) ---------------------------------
    s.text("CAN bus: 4-wire, daisy chain. Pin 1 CANH, 2 CANL, 3 GND (CAN bus ground), 4 +12 V.\n"
           "Mating plug: Phoenix Contact 1840382 (MC 1,5/4-ST-3,5), two per board.", 25.4, 30.48)
    term = "Connector_Phoenix_MC:PhoenixContact_MC_1,5_4-G-3.5_1x04_P3.50mm_Horizontal"
    s.part("Connector:Screw_Terminal_01x04", "J1", "CAN IN", 38.1, 50.8,
           {"1": "CANH", "2": "CANL", "3": "GND", "4": "V12_BUS"}, 0, term, "Phoenix Contact", "1844236",
           ref_at=(38.1, 44.45), value_at=(38.1, 58.42))
    s.part("Connector:Screw_Terminal_01x04", "J2", "CAN OUT", 38.1, 76.2,
           {"1": "CANH", "2": "CANL", "3": "GND", "4": "V12_BUS"}, 0, term, "Phoenix Contact", "1844236",
           ref_at=(38.1, 69.85), value_at=(38.1, 83.82))

    # --- CAN transceiver, ESD, termination ----------------------------
    s.part("Interface_CAN_LIN:MCP2562-E-P", "U2", "MCP2562FD-E/P", 101.6, 60.96,
           {"1": "CAN_TX", "2": "GND", "3": "+5V", "4": "CAN_RX", "5": "+5V", "6": "CANL", "7": "CANH", "8": "CAN_STBY"},
           0, "Package_DIP:DIP-8_W7.62mm_LongPads", "Microchip Technology", "MCP2562FD-E/P",
           ref_at=(104.14, 48.26), value_at=(104.14, 74.93))
    s.C("C4", "100nF 50V X7R", 88.9, 40.64, "+5V", "GND", decouple=True)
    s.R("R4", "10k", 76.2, 76.2, "CAN_STBY", "GND")
    s.text("STBY pulled low: transceiver active\nunless firmware selects standby.", 66.04, 86.36, 1.0)
    s.part("Power_Protection:NUP2105L", "D3", "NUP2105L", 134.62, 60.96,
           {"1": "CANH", "2": "CANL", "3": "GND"}, 0, "Package_TO_SOT_SMD:SOT-23", "onsemi", "NUP2105LT1G",
           ref_at=(139.7, 57.15), value_at=(139.7, 64.77))
    s.part("Jumper:Jumper_2_Open", "JP1", "TERM", 132.08, 81.28, {"1": "CANH", "2": "TERM_A"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "Samtec", "TSW-102-07-G-S",
           ref_at=(132.08, 77.47), value_at=(132.08, 85.09))
    s.R("R5", "120R", 147.32, 86.36, "TERM_A", "CANL")
    s.text("120 R termination: fit the shunt (Samtec SNT-100-BK-G)\nonly on the two end nodes of the bus.", 124.46, 96.52, 1.0)

    # --- 12 V tap and 5 V supply ---------------------------------------
    s.text("Node power from the CAN cable. Reverse-polarity diode and TVS on the tap;\n"
           "the bus +12 V passes J1 -> J2 unswitched.", 25.4, 106.68)
    s.part("Device:D_Zener", "D2", "SMBJ15A", 38.1, 127.0, {"1": "V12_BUS", "2": "GND"}, 90,
           "Diode_SMD:D_SMB_Handsoldering", "Littelfuse", "SMBJ15A", ref_at=(43.18, 125.73), value_at=(43.18, 128.27),
           value_justify="left")
    s.part("Device:D_Schottky", "D1", "B340A", 58.42, 116.84, {"2": "V12_BUS", "1": "+12V"}, 0,
           "Diode_SMD:D_SMA_Handsoldering", "Diodes Incorporated", "B340A-13-F",
           ref_at=(58.42, 113.03), value_at=(58.42, 121.92))
    s.C("C1", "10uF 25V X7R", 78.74, 127.0, "+12V", "GND")
    s.part("Converter_DCDC:R-78E5.0-0.5", "U1", "R-78E5.0-1.0", 101.6, 124.46,
           {"1": "+12V", "2": "GND", "3": "+5V"}, 0, "Converter_DCDC:Converter_DCDC_RECOM_R-78E-0.5_THT",
           "RECOM", "R-78E5.0-1.0", ref_at=(101.6, 116.84), value_at=(101.6, 134.62))
    s.C("C2", "10uF 25V X7R", 121.92, 127.0, "+5V", "GND")
    s.R("R1", "47k", 142.24, 119.38, "+12V", "")
    s.R("R2", "10k", 142.24, 132.08, "", "GND")
    s.C("C3", "100nF 50V X7R", 157.48, 132.08, "", "GND", decouple=True)
    s.wire(142.24, 123.19, 142.24, 128.27)
    s.wire(142.24, 125.73, 157.48, 125.73)
    s.wire(157.48, 125.73, 157.48, 128.27)
    s.junction(142.24, 125.73)
    s.llabel("V12_MON", 157.48, 125.73, 0)
    s.text("12 V monitor: 47k/10k -> 2.1 V at 12 V (5 V at 28 V).", 134.62, 147.32, 1.0)
    s.flag(30.48, 116.84)
    s.llabel("V12_BUS", 30.48, 116.84, 180)
    s.flag(68.58, 147.32, 180); s.power("+12V", 68.58, 147.32, 0)
    s.flag(55.88, 147.32); s.power("GND", 55.88, 147.32)

    # --- MCU ---------------------------------------------------------
    mcu = "Thl_MCU:PIC18F47Q84-IP"
    nets = {
        "11": "", "32": "", "12": "", "31": "",
        "2": "/ACS_ADC", "3": "/BUILD_REF", "4": "V12_MON", "5": "~", "6": "~", "7": "~",
        "13": "OSC1", "14": "OSC2",
        "8": "/MW_REMOTE", "9": "LED_STATUS", "10": "LED_FAULT", "1": "MCLR",
        "19": "/DISP_SCK", "20": "/DISP_DIN", "21": "/DISP_LOAD", "22": "~",
        "27": "ADDR0", "28": "ADDR1", "29": "ADDR2", "30": "ADDR3",
        "33": "~", "34": "~", "35": "CAN_TX", "36": "CAN_RX", "37": "CAN_STBY", "38": "~",
        "39": "ICSPCLK", "40": "ICSPDAT",
        "15": "/GATE_EN", "16": "/TRIP_OK", "17": "/TRIP_RST", "18": "/I2C_SCL",
        "23": "/I2C_SDA", "24": "~", "25": "UART_TX", "26": "UART_RX",
    }
    s.part(mcu, "U3", "PIC18F47Q84-I/P", 254.0, 106.68, nets, 0, "Package_DIP:DIP-40_W15.24mm_Socket_LongPads",
           "Microchip Technology", "PIC18F47Q84-I/P", ref_at=(271.78, 77.47), value_at=(271.78, 139.7))
    for a, b, net in (("11", "32", "+5V"), ("12", "31", "GND")):
        ax, ay, _ = s.pin_end(mcu, 254.0, 106.68, 0, a)
        bx, by, _ = s.pin_end(mcu, 254.0, 106.68, 0, b)
        dy = -5.08 if net == "+5V" else 5.08
        s.wire(ax, ay, ax, ay + dy); s.wire(bx, by, bx, by + dy); s.wire(ax, ay + dy, bx, by + dy)
        s.power(net, bx, by + dy, 0)
    s.text("Pin map (PPS): CANTX RB2, CANRX RB3, SCL1 RC3, SDA1 RC4, SPI1 SCK RD0 / SDO RD1, CS RD2,\n"
           "UART1 TX RC6 / RX RC7 (debug). RA0..RA2 analog. Address RD4..RD7 with weak pull-ups.\n"
           "Socket: 40-pin 600 mil DIP socket, e.g. Mill-Max 110-43-640-41-001000 (in BOM separately).",
           205.74, 165.1, 1.0)
    for ref, x in (("C5", 223.52), ("C6", 246.38)):
        s.C(ref, "100nF 50V X7R", x, 60.96, "+5V", "GND", decouple=True)
    s.C("C7", "10uF 25V X7R", 269.24, 60.96, "+5V", "GND")
    s.text("C5, C6 at the two VDD pins; C7 bulk.", 223.52, 72.39, 1.0)

    # crystal
    s.part("Device:Crystal", "Y1", "16MHz", 200.66, 50.8, {"1": "OSC1", "2": "OSC2"}, 0,
           "Crystal:Crystal_HC49-U_Vertical", "ECS Inc.", "ECS-160-18-4X", ref_at=(200.66, 46.99), value_at=(200.66, 55.88))
    s.C("C8", "27pF 50V C0G", 187.96, 60.96, "OSC1", "GND")
    s.C("C9", "27pF 50V C0G", 205.74, 60.96, "OSC2", "GND")
    s.text("16 MHz HC-49/U, CL 18 pF.\n4x PLL -> 64 MHz Fosc,\nalso the CAN FD clock.", 185.42, 38.1, 1.0)

    # MCLR + ICSP
    s.R("R3", "10k", 307.34, 63.5, "+5V", "MCLR")
    s.part("Connector_Generic:Conn_01x06", "J3", "ICSP", 322.58, 78.74,
           {"1": "MCLR", "2": "+5V", "3": "GND", "4": "ICSPDAT", "5": "ICSPCLK", "6": "~"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", "Samtec", "TSW-106-07-G-S",
           ref_at=(322.58, 71.12), value_at=(322.58, 88.9))
    s.text("ICSP (MPLAB PICkit / ICD / Snap):\n1 MCLR, 2 VDD, 3 VSS, 4 PGD, 5 PGC, 6 n/c", 302.26, 96.52, 1.0)

    # debug UART header
    s.part("Connector_Generic:Conn_01x03", "J4", "UART", 322.58, 116.84,
           {"1": "UART_TX", "2": "UART_RX", "3": "GND"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", "Samtec", "TSW-103-07-G-S",
           ref_at=(322.58, 111.76), value_at=(322.58, 123.19))
    s.text("Debug UART (5 V logic): 1 TX from MCU, 2 RX to MCU, 3 GND", 302.26, 130.81, 1.0)

    # address switch
    s.part("Switch:SW_Coded_SH-7010", "SW1", "ADDR", 190.5, 175.26,
           {"C": "GND", "1": "ADDR0", "2": "ADDR1", "4": "ADDR2", "8": "ADDR3"}, 0,
           "Button_Switch_THT:Nidec_Copal_SH-7010C", "Nidec Copal", "SH-7010C",
           ref_at=(190.5, 166.37), value_at=(190.5, 184.15))
    s.text("CAN node address, hex rotary. Common to GND, MCU weak pull-ups;\nfirmware inverts (closed = 0).", 175.26, 190.5, 1.0)

    # LEDs
    for ref, rref, net, col, mpn, x in (("D4", "R6", "LED_STATUS", "LED green", "LTST-C150GKT", 241.3),
                                         ("D5", "R7", "LED_FAULT", "LED red", "LTST-C150KRKT", 261.62)):
        y = 170.18
        s.R(rref, "1k", x, y, net, "")
        s.wire(x, y + 3.81, x, y + 6.35)
        s.part("Device:LED", ref, col, x, y + 10.16, {"2": "", "1": "GND"}, 90, FP["LED"],
               "Lite-On", mpn, ref_at=(x + 2.54, y + 8.89), value_at=(x + 2.54, y + 11.43), value_justify="left", hide_value=True)
    s.text("D4 status (green), D5 fault (red), about 3 mA.", 236.22, 196.85, 1.0)
    return s


def power_path():
    s = Sheet("power_path.kicad_sch", "Power path", 3, "CAN SSR: power path")
    s.text("LOAD SIDE (referenced to GND_LOAD = RET, the return bar = supply -V). Up to 200 V: keep 250 V working clearances;\n"
           "about 6 mm creepage to anything on the CAN/logic side. Heavy nets (VIN, SRC, VOUT_SW, VOUT, RET)\n"
           "are busbar runs: mask-free top copper with a soldered copper bar.", 25.4, 30.48)

    # --- bolts -----------------------------------------------------------
    for i, (ref, val, net, y) in enumerate((("H1", "SUPPLY +", "/VIN", 60.96), ("H2", "SUPPLY -", "/GND_LOAD", 81.28),
                                             ("H3", "LOAD +", "/VOUT", 101.6), ("H4", "LOAD -", "/GND_LOAD", 121.92))):
        s.part("Mechanical:MountingHole_Pad", ref, val, 35.56, y, {"1": net}, 0,
               "MountingHole:MountingHole_5.3mm_M5_Pad", ref_at=(40.64, y - 3.81), value_at=(40.64, y - 1.27),
               value_justify="left")
    s.text("M5 bolt + ring lug per terminal, on the busbar.\nH2 and H4 share the return bar (unswitched).", 25.4, 134.62, 1.0)

    # --- MOSFETs: Q1/Q2 input side, Q3/Q4 output side, common source ----
    fet = "Transistor_FET:STB15N80K5"
    build = {"Build": "HC: IPB021N10NM5LF2 / STD: IPB110N20N3LF / HV: IPB407N30N (all Infineon D2PAK)"}
    for ref, gnet, dnet, x in (("Q1", "G1", "/VIN", 96.52), ("Q2", "G2", "/VIN", 116.84),
                               ("Q3", "G3", "VOUT_SW", 165.1), ("Q4", "G4", "VOUT_SW", 185.42)):
        s.part(fet, ref, "IPB110N20N3LF", x, 76.2, {"1": gnet, "2": dnet, "3": "SRC"}, 0,
               "Package_TO_SOT_SMD:TO-263-2", "Infineon", "IPB110N20N3LFATMA1",
               ref_at=(x + 5.08, 73.66), value_at=(x + 5.08, 78.74), value_justify="left", fields_extra=build)
    s.text("Q1 || Q2 (input side) and Q3 || Q4 (output side), sources tied: off = blocks both directions.\n"
           "Fitted MOSFET depends on the build (see Build field); the build resistor on the trip sheet\n"
           "must match.", 96.52, 50.8, 1.0)
    for ref, net, x in (("R10", "G1", 96.52), ("R11", "G2", 116.84), ("R12", "G3", 165.1), ("R13", "G4", 185.42)):
        s.R(ref, "10R", x - 12.7, 101.6, "GATE", net)

    # --- gate network ----------------------------------------------------
    s.R("R14", "10M", 223.52, 101.6, "GATE", "SRC")
    s.part("Device:D_Zener", "D10", "SMAZ15", 241.3, 101.6, {"1": "GATE", "2": "SRC"}, 90,
           "Diode_SMD:D_SMA_Handsoldering", "Vishay", "SMAZ15-E3/61", ref_at=(245.11, 100.33),
           value_at=(245.11, 102.87), value_justify="left")
    s.text("Gate clamp 15 V; 10M defines the off state.", 218.44, 116.84, 1.0)

    # turn-off accelerator
    s.part("Device:D", "D11", "1N4148W", 223.52, 139.7, {"2": "VOM_P", "1": "GATE"}, 0,
           "Diode_SMD:D_SOD-123", "Diodes Incorporated", "1N4148W-7-F", ref_at=(223.52, 135.89), value_at=(223.52, 143.51))
    s.part("Transistor_BJT:Q_PNP_BEC", "Q5", "MMBT2907A", 254.0, 139.7, {"1": "VOM_P", "2": "GATE", "3": "SRC"}, 0,
           "Package_TO_SOT_SMD:SOT-23", "onsemi", "MMBT2907ALT1G", ref_at=(259.08, 137.16), value_at=(259.08, 142.24),
           value_justify="left")
    s.text("Turn-off: when the VOM1271 output collapses, Q5 dumps the gate into SRC (a few us).", 213.36, 152.4, 1.0)

    # slew limiter for hot turn-on
    s.C("C10", "68nF 630V X7R", 223.52, 177.8, "/VIN", "SLEW", fp="Capacitor_SMD:C_1210_3225Metric_Pad1.33x2.70mm_HandSolder")
    s.part("Device:D", "D12", "ES1J", 241.3, 190.5, {"2": "GATE", "1": "SLEW"}, 0,
           "Diode_SMD:D_SMA_Handsoldering", "Vishay", "ES1J-E3/61T", ref_at=(241.3, 186.69), value_at=(241.3, 194.31))
    s.R("R15", "1M", 259.08, 190.5, "SLEW", "GATE", rot=90)
    s.text("Hot turn-on slew limit: C10 from VIN to the gate (via D12) diverts the VOM1271 current,\n"
           "about 30 uA at IF 20 mA -> ~0.45 V/ms; 1 mF load draws ~0.45 A. D12 keeps C10 out of the\n"
           "turn-off path; R15 resets C10 after turn-off. No DC path: C10 blocks.", 205.74, 203.2, 1.0)

    # --- photovoltaic drivers (cross the barrier) ------------------------
    vom = "Thl_Isolator:VOM1271T"
    s.part(vom, "U10", "VOM1271T", 304.8, 76.2, {"1": "/VOM_LED_A", "2": "LED_MID", "4": "VOM_P", "3": "VOM_MID"}, 0,
           "Thl_Package:Vishay_SOP-4_4.4x4.9mm_P2.54mm_HandSolder", "Vishay", "VOM1271T",
           ref_at=(304.8, 68.58), value_at=(304.8, 83.82))
    s.part(vom, "U11", "VOM1271T", 304.8, 101.6, {"1": "LED_MID", "2": "/VOM_LED_K", "4": "VOM_MID", "3": "SRC"}, 0,
           "Thl_Package:Vishay_SOP-4_4.4x4.9mm_P2.54mm_HandSolder", "Vishay", "VOM1271T",
           ref_at=(304.8, 93.98), value_at=(304.8, 109.22))
    s.text("Two VOM1271T: LEDs in series (driven from the trip sheet, ~20 mA), outputs in series\n"
           "for ~16 V gate drive. LED side = CAN/logic domain; output side = load domain.", 287.02, 121.92, 1.0)

    # --- current sensor and freewheel -------------------------------------
    s.part("Sensor_Current:ACS756xCB-050B-PFF", "U12", "ACS770ECB-100U-PFF-T", 304.8, 167.64,
           {"1": "+5V", "2": "GND", "3": "/ACS_OUT", "4": "VOUT_SW", "5": "/VOUT"}, 0,
           "Sensor_Current:Allegro_CB_PFF", "Allegro MicroSystems", "ACS770ECB-100U-PFF-T",
           ref_at=(309.88, 157.48), value_at=(309.88, 180.34), value_justify="left")
    s.C("C11", "100nF 50V X7R", 330.2, 160.02, "+5V", "GND", decouple=True)
    s.text("ACS770: primary (IP+/IP-) in the load path; VCC/GND/VIOUT are CAN/logic side\n"
           "(+5V, GND). ~40 mV/A, 0.5 V at 0 A (unidirectional, ratiometric).", 287.02, 190.5, 1.0)
    s.part("Device:D", "D13", "ES3J", 152.4, 152.4, {"1": "/VOUT", "2": "/GND_LOAD"}, 90,
           "Diode_SMD:D_SMC_Handsoldering", "Vishay", "ES3J-E3/57T", ref_at=(156.21, 151.13), value_at=(156.21, 153.67),
           value_justify="left")
    s.text("Freewheel diode, output to return:\nclamps inductive kick from DUT wiring.", 142.24, 165.1, 1.0)
    return s


def trip():
    s = Sheet("trip.kicad_sch", "Overcurrent trip, gate drive", 4, "CAN SSR: overcurrent trip and gate drive")
    s.text("CAN/LOGIC SIDE. Hardware overcurrent trip, independent of firmware: the comparator latches\n"
           "and removes the VOM1271 LED current. Firmware can reset the latch (TRIP_RST) but not override it.",
           25.4, 30.48)

    # --- build resistor / threshold ------------------------------------
    s.part("Device:R", "R20", "16.2k", 50.8, 66.04, {"1": "+5V", "2": "VTH"}, 0, FP["R"], "Yageo", "RC1206FR-0716K2L",
           ref_at=(53.34, 64.77), value_at=(53.34, 67.31), value_justify="left",
           fields_extra={"Build": "HC 7.15k (RC1206FR-077K15L) / STD 16.2k (RC1206FR-0716K2L) / "
                                  "HV 35.7k (RC1206FR-0735K7L), 1 %"})
    s.R("R21", "10k", 50.8, 81.28, "VTH", "GND")
    s.C("C20", "100nF 50V X7R", 66.04, 81.28, "VTH", "GND", decouple=True)
    s.llabel("VTH", 50.8, 73.66, 180)
    s.wire(50.8, 69.85, 50.8, 77.47)
    s.R("R22", "1k", 78.74, 73.66, "VTH", "/BUILD_REF", rot=90)
    s.text("BUILD RESISTOR R20 (only part besides the MOSFETs that differs per build).\n"
           "Vth = 5 V x 10k / (R20 + 10k); ACS770-100U: 0.5 V + 40 mV/A.\n"
           "  HC  7.15k -> 2.92 V -> trip 60 A\n  STD 16.2k -> 1.91 V -> trip 35 A\n  HV  35.7k -> 1.10 V -> trip 15 A\n"
           "R20 open -> Vth 0 -> always tripped (cannot turn on). PIC reads VTH (BUILD_REF) as the build ID;\n"
           "out-of-band reading = fault. While latched VTH reads ~0.3 V (see D20).", 25.4, 106.68, 1.0)

    # --- ACS770 filtering -------------------------------------------------
    s.R("R23", "1k", 129.54, 55.88, "/ACS_OUT", "CMP_IN", rot=90)
    s.C("C21", "1nF 50V C0G", 142.24, 63.5, "CMP_IN", "GND")
    s.R("R24", "1k", 129.54, 152.4, "/ACS_OUT", "/ACS_ADC", rot=90)
    s.C("C22", "100nF 50V X7R", 144.78, 160.02, "/ACS_ADC", "GND", decouple=True)
    s.text("R23/C21: comparator filter ~1 us. R24/C22: ADC filter ~100 us (firmware samples at 20 Hz).", 116.84, 172.72, 1.0)

    # --- comparator + latch -------------------------------------------------
    cmp_ = "Comparator:LM2903"
    s.part(cmp_, "U20", "LM393B", 180.34, 63.5, {"3": "VTH", "2": "CMP_IN", "1": "/TRIP_OK"}, 0,
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Texas Instruments", "LM393BIDR", multi=True,
           ref_at=(180.34, 55.88), value_at=(180.34, 71.12))
    s.part(cmp_, "U20", "LM393B", 180.34, 99.06, {"5": "GND", "6": "VTH", "7": "~"}, 0,
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Texas Instruments", "LM393BIDR", unit=2,
           ref_at=(180.34, 91.44), value_at=(180.34, 106.68))
    s.part(cmp_, "U20", "LM393B", 210.82, 99.06, {"8": "+5V", "4": "GND"}, 0,
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Texas Instruments", "LM393BIDR", unit=3,
           ref_at=(215.9, 96.52), value_at=(215.9, 101.6))
    s.C("C23", "100nF 50V X7R", 226.06, 99.06, "+5V", "GND", decouple=True)
    s.R("R25", "10k", 205.74, 50.8, "+5V", "/TRIP_OK")
    s.part("Device:D_Schottky", "D20", "BAT54", 205.74, 76.2, {"1": "/TRIP_OK", "2": "VTH"}, 0,
           "Package_TO_SOT_SMD:SOT-23", "Nexperia", "BAT54,215", ref_at=(205.74, 72.39), value_at=(205.74, 80.01))
    s.text("Latch: on overcurrent the open-collector output pulls TRIP_OK low and D20 drags VTH to ~0.3 V,\n"
           "below the 0.5 V zero-current output, so it stays tripped. Unit B unused (output open).", 167.64, 116.84, 1.0)

    # reset
    s.part("Transistor_FET:Q_NMOS_GSD", "Q20", "2N7002", 154.94, 76.2, {"1": "/TRIP_RST", "2": "GND", "3": "CMP_IN"}, 0,
           "Package_TO_SOT_SMD:SOT-23", "onsemi", "2N7002LT1G", ref_at=(160.02, 74.93), value_at=(160.02, 77.47),
           value_justify="left")
    s.R("R26", "100k", 137.16, 93.98, "/TRIP_RST", "GND")
    s.text("Reset: TRIP_RST high pulls CMP_IN low, the output releases and VTH recovers; if the\n"
           "overcurrent persists it re-trips. Q23/Q24 hold the gate drive off during the reset.", 116.84, 127.0, 1.0)

    # --- VOM1271 LED drive: GATE_EN AND TRIP_OK ------------------------------
    s.R("R27", "100R", 271.78, 55.88, "+5V", "/VOM_LED_A")
    s.part("Transistor_FET:Q_NMOS_GSD", "Q21", "2N7002", 271.78, 81.28, {"1": "/GATE_EN", "2": "EN_MID", "3": "/VOM_LED_K"}, 0,
           "Package_TO_SOT_SMD:SOT-23", "onsemi", "2N7002LT1G", ref_at=(276.86, 80.01), value_at=(276.86, 82.55),
           value_justify="left")
    s.part("Transistor_FET:Q_NMOS_GSD", "Q22", "2N7002", 271.78, 101.6, {"1": "/TRIP_OK", "2": "EN_MID2", "3": "EN_MID"}, 0,
           "Package_TO_SOT_SMD:SOT-23", "onsemi", "2N7002LT1G", ref_at=(276.86, 100.33), value_at=(276.86, 102.87),
           value_justify="left")
    s.R("R28", "100k", 254.0, 91.44, "/GATE_EN", "GND")
    s.part("Transistor_FET:Q_NMOS_GSD", "Q23", "2N7002", 271.78, 121.92, {"1": "RST_INH", "2": "GND", "3": "EN_MID2"}, 0,
           "Package_TO_SOT_SMD:SOT-23", "onsemi", "2N7002LT1G", ref_at=(276.86, 120.65), value_at=(276.86, 123.19),
           value_justify="left")
    s.R("R29", "10k", 246.38, 114.3, "+5V", "RST_INH")
    s.part("Transistor_FET:Q_NMOS_GSD", "Q24", "2N7002", 233.68, 132.08, {"1": "/TRIP_RST", "2": "GND", "3": "RST_INH"}, 0,
           "Package_TO_SOT_SMD:SOT-23", "onsemi", "2N7002LT1G", ref_at=(238.76, 130.81), value_at=(238.76, 133.35),
           value_justify="left")
    s.text("VOM1271 LEDs (two in series, on the power-path sheet): +5V -> R27 -> LEDs -> Q21 -> Q22 -> Q23 -> GND.\n"
           "Current flows only when GATE_EN (firmware) AND TRIP_OK (hardware) are high AND TRIP_RST is low:\n"
           "~21 mA ((5 - 2 x 1.4) V / 100 R), giving ~30 uA gate drive. R28 holds GATE_EN low at reset.\n"
           "Q23/Q24/R29: while TRIP_RST is high (trip blinded during reset), the gate drive is forced off in\n"
           "hardware, so a reset can never coincide with an enabled switch.", 226.06, 154.94, 1.0)
    return s


def load_side():
    s = Sheet("load_side.kicad_sch", "Load-side sense and supply control", 5, "CAN SSR: load-side sense and Mean Well control")
    s.text("Isolated load-side domain, referenced to GND_LOAD (return bar RET = supply -V). Powered and reached only\n"
           "through reinforced parts: U30 (UCC12050 DC/DC) and U31 (ISO1640 I2C). Keep ~6 mm creepage across them.",
           25.4, 30.48)

    # --- isolated power -------------------------------------------------
    u = "Thl_Isolator:UCC12050DVE"
    s.part(u, "U30", "UCC12050DVE", 63.5, 71.12,
           {"3": "+5V", "1": "+5V", "4": "GND", "5": "~", "2": "GND", "6": "GND", "7": "GND", "8": "GND",
            "14": "V5_ISO", "13": "V5_ISO", "15": "/GND_LOAD", "9": "/GND_LOAD", "16": "/GND_LOAD", "10": "/GND_LOAD", "11": "/GND_LOAD",
            "12": "/GND_LOAD"}, 0, "Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm", "Texas Instruments", "UCC12050DVE",
           ref_at=(63.5, 55.88), value_at=(63.5, 90.17))
    s.C("C30", "10uF 25V X7R", 30.48, 106.68, "+5V", "GND")
    s.C("C31", "100nF 50V X7R", 43.18, 106.68, "+5V", "GND", decouple=True)
    s.C("C32", "10uF 25V X7R", 83.82, 106.68, "V5_ISO", "/GND_LOAD")
    s.C("C33", "100nF 50V X7R", 96.52, 106.68, "V5_ISO", "/GND_LOAD", decouple=True)
    s.text("SEL tied to VISO -> 5.0 V. EN high (always on), SYNC to GNDP (internal oscillator).\n"
           "Load-side current ~10 mA of the 100 mA available.", 25.4, 120.65, 1.0)
    s.flag(119.38, 114.3); s.glabel("GND_LOAD", 119.38, 114.3, 0)

    # --- I2C isolator -----------------------------------------------------
    iso = "Thl_Isolator:ISO1640DWR"
    s.part(iso, "U31", "ISO1640DWR", 63.5, 157.48,
           {"3": "+5V", "5": "/I2C_SDA", "6": "/I2C_SCL", "1": "GND", "7": "GND",
            "14": "V5_ISO", "12": "SDA_ISO", "11": "SCL_ISO", "9": "/GND_LOAD", "16": "/GND_LOAD",
            "2": "~", "4": "~", "8": "~", "10": "~", "13": "~", "15": "~"}, 0,
           "Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm", "Texas Instruments", "ISO1640DWR",
           ref_at=(63.5, 142.24), value_at=(63.5, 175.26))
    s.C("C34", "100nF 50V X7R", 30.48, 190.5, "+5V", "GND", decouple=True)
    s.C("C35", "100nF 50V X7R", 96.52, 190.5, "V5_ISO", "/GND_LOAD", decouple=True)
    s.R("R30", "4.7k", 22.86, 142.24, "+5V", "/I2C_SDA")
    s.R("R31", "4.7k", 33.02, 142.24, "+5V", "/I2C_SCL")
    s.R("R32", "4.7k", 96.52, 142.24, "V5_ISO", "SDA_ISO")
    s.R("R33", "4.7k", 106.68, 142.24, "V5_ISO", "SCL_ISO")
    s.text("I2C on the load side: MCP3428 0x68, MCP4725 0x60 (PV) and 0x61 (PC).", 25.4, 203.2, 1.0)

    # --- ADC + dividers -------------------------------------------------------
    s.part("Analog_ADC:MCP3428x-xSL", "U32", "MCP3428-E/SL", 182.88, 71.12,
           {"1": "VIN_DIV", "2": "/GND_LOAD", "3": "VOUT_DIV", "4": "/GND_LOAD", "11": "PV_FB", "12": "/GND_LOAD",
            "13": "PC_FB", "14": "/GND_LOAD", "5": "/GND_LOAD", "6": "V5_ISO", "7": "SDA_ISO", "8": "SCL_ISO",
            "9": "/GND_LOAD", "10": "/GND_LOAD"}, 0, "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "Microchip Technology",
           "MCP3428-E/SL", ref_at=(185.42, 55.88), value_at=(185.42, 90.17))
    s.C("C36", "100nF 50V X7R", 205.74, 50.8, "V5_ISO", "/GND_LOAD", decouple=True)
    s.text("MCP3428: 4 differential channels, +/-2.048 V, 16 bit at 15 SPS.\n"
           "CH1 Vin, CH2 Vout, CH3 PV readback, CH4 PC readback. Adr0/Adr1 low -> 0x68.", 160.02, 101.6, 1.0)
    for i, (net, top, ref0, y) in enumerate((("VIN_DIV", "/VIN", 34, 132.08), ("VOUT_DIV", "/VOUT", 38, 172.72))):
        x0 = 147.32
        s.R(f"R{ref0}", "332k", x0, y, top, "", rot=90)
        s.R(f"R{ref0 + 1}", "332k", x0 + 15.24, y, "", "", rot=90)
        s.R(f"R{ref0 + 2}", "332k", x0 + 30.48, y, "", "", rot=90)
        for k in range(3):  # chain: R pin 2 (x+3.81) to next R pin 1 (x+15.24-3.81), last to the tap
            xs = x0 + 15.24 * k + 3.81
            s.wire(xs, y, xs + 7.62, y)
        tap = x0 + 45.72
        s.wire(x0 + 30.48 + 3.81 + 7.62, y, tap + 12.7, y)
        s.junction(tap, y)
        s.wire(tap, y, tap, y + 3.81)
        s.wire(tap + 12.7, y, tap + 12.7, y + 3.81)
        s.llabel(net, tap + 12.7, y, 0)
        s.R(f"R{ref0 + 3}", "8.06k", tap, y + 7.62, "", "/GND_LOAD")
        s.C(f"C{37 + i}", "100nF 50V X7R", tap + 12.7, y + 7.62, "", "/GND_LOAD", decouple=True)
    s.text("Dividers: 3 x 332k (1206, 200 V each) over 8.06k = 1/124.6: 250 V -> 2.0 V full scale.\n"
           "100 nF -> fc ~200 Hz anti-aliasing (sampled at 20 Hz, averaged). MCP3428 input loading\n"
           "(~2 MOhm differential) is removed by calibration.", 139.7, 198.12, 1.0)

    # --- DACs for Mean Well PV / PC --------------------------------------------
    dac = "Analog_DAC:MCP4725xxx-xCH"
    for ref, a0, out, tnet, fb, rs, rt, rb, cref, y in (
            ("U33", "/GND_LOAD", "PV_DAC", "MW_PV", "PV_FB", "R42", "R44", "R45", "C40", 63.5),
            ("U34", "V5_ISO", "PC_DAC", "MW_PC", "PC_FB", "R43", "R46", "R47", "C41", 106.68)):
        s.part(dac, ref, "MCP4725A0T-E/CH", 271.78, y,
               {"1": out, "2": "/GND_LOAD", "3": "V5_ISO", "4": "SDA_ISO", "5": "SCL_ISO", "6": a0}, 0,
               "Package_TO_SOT_SMD:SOT-23-6", "Microchip Technology", "MCP4725A0T-E/CH",
               ref_at=(274.32, 53.34 + y - 63.5), value_at=(274.32, 73.66 + y - 63.5))
        s.C(cref, "100nF 50V X7R", 254.0, y - 15.24, "V5_ISO", "/GND_LOAD", decouple=True)
        s.R(rs, "1k", 294.64, y, out, tnet, rot=90)
        s.R(rt, "20k", 309.88, y + 7.62, tnet, fb)
        s.R(rb, "10k", 309.88, y + 20.32, fb, "/GND_LOAD")
    s.text("PV/PC: 0-5 V DAC outputs (rail-to-rail, VDD = V5_ISO), 1k series to the terminal.\n"
           "20k/10k readback into the ADC confirms the voltage at the terminal (open/short wiring).\n"
           "Firmware closes the loop on the measured Vin, so DAC accuracy does not matter.", 248.92, 142.24, 1.0)

    # --- Mean Well remote ON/OFF ------------------------------------------------
    s.part("Relay_SolidState:TLP222A", "U35", "TLP222A", 271.78, 175.26,
           {"1": "RLY_A", "2": "GND", "3": "MW_RC_B", "4": "MW_RC_A"}, 0, "Package_DIP:DIP-4_W7.62mm_LongPads",
           "Toshiba", "TLP222A(F)", ref_at=(271.78, 167.64), value_at=(271.78, 182.88))
    s.R("R48", "680R", 248.92, 172.72, "/MW_REMOTE", "RLY_A", rot=90)
    s.R("R49", "100k", 236.22, 185.42, "/MW_REMOTE", "GND")
    s.text("Remote ON/OFF: TLP222A contact closes the Mean Well's Remote to its +12V-AUX (60 V, 500 mA).\n"
           "LED ~5.7 mA from MW_REMOTE; R49 keeps it off at reset -> supply off.", 226.06, 198.12, 1.0)

    # --- control connector -------------------------------------------------------
    s.part("Connector:Screw_Terminal_01x05", "J30", "MEAN WELL", 345.44, 116.84,
           {"1": "MW_PV", "2": "MW_PC", "3": "/GND_LOAD", "4": "MW_RC_A", "5": "MW_RC_B"}, 0,
           "Connector_Phoenix_MC:PhoenixContact_MC_1,5_5-G-3.5_1x05_P3.50mm_Horizontal", "Phoenix Contact", "1844249",
           ref_at=(345.44, 109.22), value_at=(345.44, 127.0))
    s.text("J30 to the Mean Well control connector: 1 PV, 2 PC, 3 GND(signal) = -V,\n"
           "4/5 dry contact to Remote and +12V-AUX (polarity free).\nPlug: Phoenix Contact 1840395.", 325.12, 137.16, 1.0)
    return s


SHEETS = [can_logic, power_path, trip, load_side]


def main():
    sheets = [f() for f in SHEETS]
    for sh in sheets:
        (HW / sh.file).write_text(sh.render())
    (HW / "can-ssr.kicad_sch").write_text(root_sheet(sheets, "CAN SSR"))
    print("wrote", [sh.file for sh in sheets])


if __name__ == "__main__":
    main()
