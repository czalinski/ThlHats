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

    def part(self, lib_id, ref, value, x, y, nets, rot=0, footprint="", mfr=None, mpn=None, glob=(), **kw):
        """Place a symbol and attach a net to each pin: '~' = no connect,
        names starting with + or GND = power symbol, names in glob = global label."""
        pins = pin_table(lib_id)
        fields = {}
        if mpn:
            fields = {"Manufacturer": mfr, "MPN": mpn}
        self.symbol(lib_id, ref, value, x, y, rot, footprint, pins=list(pins), fields=fields, **kw)
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

    def C(self, ref, value, x, y, n1, n2, decouple=False, glob=()):
        mfr, mpn = MPN[value]
        self.part("Device:C", ref, value, x, y, {"1": n1, "2": n2}, 0, FP["Cd" if decouple or "pF" in value else "C"],
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
        "2": "/ACS_OUT", "3": "/BUILD_REF", "4": "V12_MON", "5": "~", "6": "~", "7": "~",
        "13": "OSC1", "14": "OSC2",
        "8": "/MW_REMOTE", "9": "LED_STATUS", "10": "LED_FAULT", "1": "MCLR",
        "19": "/DISP_SCK", "20": "/DISP_DIN", "21": "/DISP_LOAD", "22": "~",
        "27": "ADDR0", "28": "ADDR1", "29": "ADDR2", "30": "ADDR3",
        "33": "~", "34": "~", "35": "CAN_TX", "36": "CAN_RX", "37": "CAN_STBY", "38": "~",
        "39": "ICSPCLK", "40": "ICSPDAT",
        "15": "/GATE_EN", "16": "/TRIP_N", "17": "/TRIP_RST", "18": "/I2C_SCL",
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


SHEETS = [can_logic]


def main():
    sheets = [f() for f in SHEETS]
    for sh in sheets:
        (HW / sh.file).write_text(sh.render())
    (HW / "can-ssr.kicad_sch").write_text(root_sheet(sheets, "CAN SSR"))
    print("wrote", [sh.file for sh in sheets])


if __name__ == "__main__":
    main()
