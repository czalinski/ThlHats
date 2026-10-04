#!/usr/bin/env python3
"""Create a new board project under boards/<name>/.

Generates:
  boards/<name>/hardware/<name>.kicad_pro   2-layer project with house design rules
  boards/<name>/hardware/<name>.kicad_sch   schematic (40-pin RPi header unless --no-gpio)
  boards/<name>/hardware/<name>.kicad_pcb   outline, M2.5 RPi mounting holes, header, GND pour
  boards/<name>/hardware/<name>.kicad_dru   custom DRC rules
  boards/<name>/hardware/{sym,fp}-lib-table pointing only at lib/ in this repo
  boards/<name>/firmware/README.md

Mounting holes use the Raspberry Pi pattern (58 x 49 mm, M2.5) at 3.5 mm from
the top-left corner, so a board of any size can stack on standard RPi standoffs.
The default size is the official HAT outline, 65 x 56.5 mm; the maximum is
100 x 100 mm.

Examples:
  tools/new_board.py relay-hat
  tools/new_board.py esp32-sensor --size 80x70 --mcu esp32
  tools/new_board.py pic-io --no-gpio --mcu pic --title "PIC I/O tester"
"""

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kilib  # noqa: E402
import house_rules as hr  # noqa: E402

REPO = kilib.REPO
ORIGIN = (100.0, 100.0)  # board top-left corner on the PCB canvas, mm
CORNER_R = 3.0

# Raspberry Pi 40-pin header, pin -> net. Names avoid '/' so KiCad does not
# have to escape them.
GPIO_NETS = {
    1: "+3.3V", 2: "+5V", 3: "GPIO2_SDA", 4: "+5V", 5: "GPIO3_SCL", 6: "GND",
    7: "GPIO4_GPCLK0", 8: "GPIO14_TXD", 9: "GND", 10: "GPIO15_RXD",
    11: "GPIO17", 12: "GPIO18_PCM_CLK", 13: "GPIO27", 14: "GND",
    15: "GPIO22", 16: "GPIO23", 17: "+3.3V", 18: "GPIO24",
    19: "GPIO10_MOSI", 20: "GND", 21: "GPIO9_MISO", 22: "GPIO25",
    23: "GPIO11_SCLK", 24: "GPIO8_CE0", 25: "GND", 26: "GPIO7_CE1",
    27: "ID_SD", 28: "ID_SC", 29: "GPIO5", 30: "GND", 31: "GPIO6",
    32: "GPIO12_PWM0", 33: "GPIO13_PWM1", 34: "GND", 35: "GPIO19_PCM_FS",
    36: "GPIO16", 37: "GPIO26", 38: "GPIO20_PCM_DIN", 39: "GND",
    40: "GPIO21_PCM_DOUT",
}
POWER_NETS = {"+3.3V", "+5V", "GND"}
# Header pins used by the Digilent/MCC DAQ HAT stack (see CLAUDE.md). They get
# no-connect flags so they cannot be wired by accident. I2C1 (pins 3/5) is
# shared and stays labelled.
MCC_RESERVED = {
    27: "ID_SD", 28: "ID_SC", 24: "SPI0 CE0", 26: "SPI0 CE1", 19: "SPI0 MOSI",
    21: "SPI0 MISO", 23: "SPI0 SCLK", 32: "ADDR0", 33: "ADDR1", 37: "ADDR2",
    36: "RESET", 38: "IRQ", 40: "IRQ",
}

GPIO_SYMBOL = "Connector_Generic:Conn_02x20_Odd_Even"
GPIO_FOOTPRINT = "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical"
HOLE_FOOTPRINT = "MountingHole:MountingHole_2.7mm_M2.5"
# Positions relative to the board's top-left corner (from the KiCad RPi HAT
# template / RPi mechanical drawings).
HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
GPIO_PIN1 = (8.37, 4.77)  # header is on the bottom side, rotated -90


def uid():
    return str(uuid.uuid4())


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


# ---------------------------------------------------------------- schematic

def lib_symbol_for_sch(lib_id):
    """Return a symbol definition from lib/ renamed to its lib_id, as the
    schematic's lib_symbols section expects."""
    nick, name = lib_id.split(":")
    text = (kilib.SYM_DIR / f"{nick}.kicad_sym").read_text()
    syms = kilib.top_level_symbols(text)
    s, e = syms[name]
    block = text[s:e]
    if kilib.sym_extends(block):
        sys.exit(f"{lib_id} is a derived symbol; flattening is not implemented")
    return block.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)


def pin_positions(lib_id):
    """pin number -> (x, y, angle) in symbol coordinates (y up)."""
    nick, name = lib_id.split(":")
    text = (kilib.SYM_DIR / f"{nick}.kicad_sym").read_text()
    s, e = kilib.top_level_symbols(text)[name]
    out = {}
    for m in re.finditer(r'\(pin\s+\w+\s+\w+\s+\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\).*?\(number\s+"([^"]+)"',
                         text[s:e], re.S):
        out[m.group(4)] = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    return out


class Sch:
    def __init__(self, project, title, rev):
        self.project = project
        self.root = uid()
        self.title = title
        self.rev = rev
        self.lib_ids = []
        self.items = []
        self.pwr = 0
        self.flg = 0

    def _use(self, lib_id):
        if lib_id not in self.lib_ids:
            self.lib_ids.append(lib_id)

    def symbol(self, lib_id, ref, value, x, y, rot=0, footprint="", hide_ref=False,
               hide_value=False, ref_at=None, value_at=None, value_justify=None, value_angle=0, pins=()):
        self._use(lib_id)
        u = uid()
        ref_at = ref_at or (x, y - 2.54)
        value_at = value_at or (x, y + 2.54)

        def prop(name, val, at, hidden, justify=None, angle=0):
            just = f"\n\t\t\t\t(justify {justify})" if justify else ""
            return (f"\t\t(property {q(name)} {q(val)}\n\t\t\t(at {at[0]:g} {at[1]:g} {angle:g})"
                    + ("\n\t\t\t(hide yes)" if hidden else "")
                    + f"\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){just}\n\t\t\t)\n\t\t)\n")

        s = (f"\t(symbol\n\t\t(lib_id {q(lib_id)})\n\t\t(at {x:g} {y:g} {rot:g})\n\t\t(unit 1)\n"
             "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n"
             f"\t\t(uuid {q(u)})\n")
        s += prop("Reference", ref, ref_at, hide_ref)
        s += prop("Value", value, value_at, hide_value, value_justify, value_angle)
        s += prop("Footprint", footprint, (x, y), True)
        s += prop("Datasheet", "", (x, y), True)
        s += prop("Description", "", (x, y), True)
        for p in pins:
            s += f"\t\t(pin {q(p)}\n\t\t\t(uuid {q(uid())})\n\t\t)\n"
        s += (f"\t\t(instances\n\t\t\t(project {q(self.project)}\n\t\t\t\t(path {q('/' + self.root)}\n"
              f"\t\t\t\t\t(reference {q(ref)})\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
        self.items.append(s)
        return u

    def power(self, name, x, y, rot=0):
        """Power symbol whose pin is at (x, y). Rotated symbols get their value
        text horizontal, beyond the symbol body."""
        self.pwr += 1
        # Body direction: +V symbols point "up", GND hangs "down", so the
        # same rotation sends them opposite ways.
        left = (rot == 90) != (name == "GND")
        if rot in (90, 270):
            value_at = (x - 7.62, y) if left else (x + 7.62, y)
        else:
            value_at = (x, y - 3.81) if name != "GND" else (x, y + 3.81)
        just = None
        self.symbol(f"power:{name}", f"#PWR{self.pwr:02d}", name, x, y, rot,
                    hide_ref=True, pins=("1",), value_at=value_at, value_justify=just,
                    value_angle=rot if rot in (90, 270) else 0)

    def flag(self, x, y, rot=0):
        self.flg += 1
        self.symbol("power:PWR_FLAG", f"#FLG{self.flg:02d}", "PWR_FLAG", x, y, rot,
                    hide_ref=True, hide_value=False, pins=("1",), value_at=(x, y - 3.81 if rot == 0 else y + 3.81))

    def wire(self, x1, y1, x2, y2):
        self.items.append(
            f"\t(wire\n\t\t(pts\n\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid {q(uid())})\n\t)\n")

    def no_connect(self, x, y):
        self.items.append(f"\t(no_connect\n\t\t(at {x:g} {y:g})\n\t\t(uuid {q(uid())})\n\t)\n")

    def label(self, name, x, y, rot, justify):
        self.items.append(
            f"\t(label {q(name)}\n\t\t(at {x:g} {y:g} {rot:g})\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {justify} bottom)\n\t\t)\n"
            f"\t\t(uuid {q(uid())})\n\t)\n")

    def text(self, s, x, y, size=1.27):
        self.items.append(
            f"\t(text {q(s)}\n\t\t(exclude_from_sim no)\n\t\t(at {x:g} {y:g} 0)\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size:g} {size:g})\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n"
            f"\t\t(uuid {q(uid())})\n\t)\n")

    def render(self):
        date = datetime.date.today().isoformat()
        libs = "".join("\t\t" + lib_symbol_for_sch(l).replace("\n", "\n\t") + "\n" for l in self.lib_ids)
        return (
            "(kicad_sch\n\t(version 20260101)\n\t(generator \"eeschema\")\n\t(generator_version \"10.0\")\n"
            f"\t(uuid {q(self.root)})\n\t(paper \"A4\")\n"
            f"\t(title_block\n\t\t(title {q(self.title)})\n\t\t(date {q(date)})\n\t\t(rev {q(self.rev)})\n\t)\n"
            f"\t(lib_symbols\n{libs}\t)\n"
            + "".join(self.items)
            + "\t(sheet_instances\n\t\t(path \"/\"\n\t\t\t(page \"1\")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n"
        )


def build_schematic(name, title, rev, gpio):
    sch = Sch(name, title, rev)
    gpio_uuid = None
    if gpio:
        X, Y = 63.5, 88.9  # symbol anchor, on the 1.27 mm grid
        pins = pin_positions(GPIO_SYMBOL)
        gpio_uuid = sch.symbol(GPIO_SYMBOL, "J1", "RPi_GPIO", X, Y, footprint=GPIO_FOOTPRINT,
                               ref_at=(X + 1.27, Y - 25.4), value_at=(X + 1.27, Y + 27.94),
                               pins=[str(n) for n in range(1, 41)])
        for num, net in GPIO_NETS.items():
            px, py, ang = pins[str(num)]
            sx, sy = X + px, Y - py  # schematic y grows downwards
            left = ang == 0  # pin points right, so it is on the left side
            ex = sx - 2.54 if left else sx + 2.54
            if num in MCC_RESERVED:
                sch.no_connect(sx, sy)
                sch.text(f"MCC {MCC_RESERVED[num]}", ex - 13.97 if left else ex, sy - 0.635, 1.0)
                continue
            sch.wire(sx, sy, ex, sy)
            if net in POWER_NETS:
                # Rotate power symbols so they point away from the connector.
                if net == "GND":
                    sch.power(net, ex, sy, 270 if left else 90)
                else:
                    sch.power(net, ex, sy, 90 if left else 270)
            else:
                sch.label(net, ex, sy, 180 if left else 0, "right" if left else "left")
        # PWR_FLAGs: the Pi drives these rails through the header.
        fx, fy = 30.48, 139.7
        for i, net in enumerate(["+5V", "+3.3V", "GND"]):
            x = fx + i * 12.7
            if net == "GND":
                sch.power(net, x, fy)
                sch.flag(x, fy)
            else:
                sch.power(net, x, fy)
                sch.flag(x, fy, 180)
        sch.text("Raspberry Pi 40-pin header (socket on the bottom side).\n"
                 "Pins marked MCC are used by the Digilent/MCC DAQ HAT stack: do not connect.\n"
                 "I2C1 (SDA/SCL) is shared; avoid addresses 0x20-0x27. No HAT ID EEPROM.",
                 30.48, 50.8)
        sch.text("Power is supplied by the Pi", 25.4, 128.27)
    sch.text(title, 25.4, 30.48, 2.54)
    return sch, gpio_uuid


# ---------------------------------------------------------------------- PCB

def build_pcb(path, name, title, rev, width, height, gpio, gpio_uuid, nets_by_pin):
    import pcbnew

    mm = pcbnew.FromMM

    def pt(x, y):
        return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))

    board = pcbnew.NewBoard(str(path))
    board.SetCopperLayerCount(2)
    tb = board.GetTitleBlock()
    tb.SetTitle(title)
    tb.SetRevision(rev)
    tb.SetDate(datetime.date.today().isoformat())
    ds = board.GetDesignSettings()
    ds.SetAuxOrigin(pt(0, 0))
    ds.SetGridOrigin(pt(0, 0))

    # Outline: rounded rectangle on Edge.Cuts.
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a))
        s.SetEnd(pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.05))
        board.Add(s)

    def arc(a, mid, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(pt(*a), pt(*mid), pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.05))
        board.Add(s)

    r, w, h = CORNER_R, width, height
    k = r * (1 - 0.5 ** 0.5)
    seg((r, 0), (w - r, 0))
    arc((w - r, 0), (w - k, k), (w, r))
    seg((w, r), (w, h - r))
    arc((w, h - r), (w - k, h - k), (w - r, h))
    seg((w - r, h), (r, h))
    arc((r, h), (k, h - k), (0, h - r))
    seg((0, h - r), (0, r))
    arc((0, r), (k, k), (r, 0))

    def load_fp(lib_id):
        nick, fpname = lib_id.split(":")
        fp = pcbnew.FootprintLoad(str(kilib.FP_DIR / f"{nick}.pretty"), fpname)
        fp.SetFPID(pcbnew.LIB_ID(nick, fpname))
        board.Add(fp)
        return fp

    for i, (x, y) in enumerate(HOLES, 1):
        fp = load_fp(HOLE_FOOTPRINT)
        fp.SetReference(f"MH{i}")
        fp.SetPosition(pt(x, y))
        fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        fp.Reference().SetVisible(False)
        fp.SetLocked(True)

    gnd = None
    if gpio:
        fp = load_fp(GPIO_FOOTPRINT)
        fp.SetReference("J1")
        fp.SetValue("RPi_GPIO")
        fp.SetPosition(pt(*GPIO_PIN1))
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(-90)
        fp.SetPath(pcbnew.KIID_PATH(f"/{gpio_uuid}"))
        fp.SetSheetname("/")
        fp.SetSheetfile(f"{name}.kicad_sch")
        fp.SetLocked(True)
        nets = {}
        for pad in fp.Pads():
            net_name = nets_by_pin[pad.GetNumber()]
            if net_name not in nets:
                ni = pcbnew.NETINFO_ITEM(board, net_name)
                board.Add(ni)
                nets[net_name] = ni
            pad.SetNet(nets[net_name])
        gnd = nets.get("GND")

        # Tie the duplicate supply pins together on F.Cu (the GND pour is on B.Cu).
        pads = {p.GetNumber(): p for p in fp.Pads()}

        def track(a, b, net):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(a)
            t.SetEnd(b)
            t.SetWidth(mm(0.5))
            t.SetLayer(pcbnew.F_Cu)
            t.SetNet(net)
            board.Add(t)

        p2, p4 = pads["2"].GetPosition(), pads["4"].GetPosition()
        track(p2, p4, nets["+5V"])
        p1, p17 = pads["1"].GetPosition(), pads["17"].GetPosition()
        jog = mm(2.5) if p1.y > p2.y else -mm(2.5)  # away from the other pin row
        a = pcbnew.VECTOR2I(p1.x, p1.y + jog)
        b = pcbnew.VECTOR2I(p17.x, p17.y + jog)
        track(p1, a, nets["+3.3V"])
        track(a, b, nets["+3.3V"])
        track(b, p17, nets["+3.3V"])

    if gnd is not None:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(pcbnew.B_Cu)
        zone.SetNet(gnd)
        zone.SetZoneName("GND_B")
        zone.SetLocalClearance(mm(0.3))
        zone.SetMinThickness(mm(0.25))
        ol = zone.Outline()
        ol.NewOutline()
        for x, y in [(0, 0), (w, 0), (w, h), (0, h)]:
            p = pt(x, y)
            ol.Append(p.x, p.y)
        board.Add(zone)

    txt = pcbnew.PCB_TEXT(board)
    txt.SetText(f"{name} rev ${{REVISION}}")
    txt.SetLayer(pcbnew.F_SilkS)
    txt.SetPosition(pt(w / 2, h - 2.5))
    txt.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
    txt.SetTextThickness(mm(0.18))
    board.Add(txt)

    pcbnew.SaveBoard(str(path), board)


# ------------------------------------------------------------------ project

def patch_project(pro_path, name):
    d = json.loads(pro_path.read_text())
    bds = d["board"]["design_settings"]
    bds["rules"].update(hr.RULES)
    bds["track_widths"] = [0.0] + hr.TRACK_WIDTHS
    bds["via_dimensions"] = [{"diameter": 0.0, "drill": 0.0}] + [
        {"diameter": a, "drill": b} for a, b in hr.VIAS]
    ns = d["net_settings"]
    template = ns["classes"][0]
    classes = []
    for nc in hr.NETCLASSES:
        c = dict(template)
        c.update(nc)
        classes.append(c)
    ns["classes"] = classes
    ns["netclass_patterns"] = [{"netclass": nc, "pattern": p} for nc, p in hr.NETCLASS_PATTERNS]
    d.setdefault("text_variables", {})
    d["meta"]["filename"] = pro_path.name
    pro_path.write_text(json.dumps(d, indent=2) + "\n")


FW_README = {
    "pic": "Microchip PIC. Suggested toolchain: MPLAB X + XC8/XC16/XC32, or the "
           "`xc8-cc` CLI with a Makefile. Keep the MPLAB X project in this directory "
           "(nbproject/private and build/dist outputs are git-ignored).",
    "esp32": "Espressif ESP32. Suggested toolchain: ESP-IDF (`idf.py build flash monitor`) "
             "or PlatformIO. `build/`, `sdkconfig.old` and `.pio/` are git-ignored; commit "
             "`sdkconfig` / `sdkconfig.defaults`.",
    "stm32": "ST STM32. Suggested toolchain: STM32CubeMX-generated CMake project built with "
             "arm-none-eabi-gcc (or STM32CubeIDE). Commit the `.ioc` file; build outputs are "
             "git-ignored.",
    "none": "No microcontroller chosen yet.",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--size", default="65x56.5", help="WxH in mm (default 65x56.5, max 100x100)")
    ap.add_argument("--no-gpio", action="store_true", help="omit the 40-pin RPi header")
    ap.add_argument("--title")
    ap.add_argument("--rev", default="A")
    ap.add_argument("--mcu", choices=sorted(FW_README), default="none")
    ap.add_argument("--force", action="store_true", help="overwrite an existing board")
    a = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", a.name):
        sys.exit("board name may contain only letters, digits, '-' and '_'")
    try:
        width, height = (float(v) for v in a.size.lower().split("x"))
    except ValueError:
        sys.exit("--size must look like 65x56.5")
    if width > hr.MAX_W or height > hr.MAX_H:
        sys.exit(f"board exceeds {hr.MAX_W:g} x {hr.MAX_H:g} mm")
    if width < 65 or height < 56.5:
        sys.exit("board must be at least 65 x 56.5 mm to fit the RPi mounting holes")
    title = a.title or a.name

    bdir = REPO / "boards" / a.name
    hw = bdir / "hardware"
    if hw.exists() and not a.force:
        sys.exit(f"{hw} exists (use --force to overwrite)")
    hw.mkdir(parents=True, exist_ok=True)
    gpio = not a.no_gpio

    sch, gpio_uuid = build_schematic(a.name, title, a.rev, gpio)
    sch_path = hw / f"{a.name}.kicad_sch"
    sch_path.write_text(sch.render())

    # Write a provisional project + lib tables so kicad-cli can resolve things.
    pro_path = hw / f"{a.name}.kicad_pro"
    kilib.sync(quiet=True)

    nets_by_pin = {}
    if gpio:
        # Ask KiCad for the real net names so the PCB matches the schematic.
        with tempfile.TemporaryDirectory() as td:
            net = Path(td) / "n.net"
            subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(net), str(sch_path)],
                           check=True, capture_output=True)
            text = net.read_text()
        for blk in re.split(r"\n\s*\(net\s", text)[1:]:
            nm = re.search(r'\(name\s+"([^"]*)"\)', blk).group(1)
            for ref, pin in re.findall(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', blk):
                if ref == "J1":
                    nets_by_pin[pin] = nm
        missing = [str(n) for n in range(1, 41) if str(n) not in nets_by_pin]
        if missing:
            sys.exit(f"netlist is missing J1 pins {missing}")

    build_pcb(hw / f"{a.name}.kicad_pcb", a.name, title, a.rev, width, height, gpio, gpio_uuid, nets_by_pin)
    patch_project(pro_path, a.name)
    shutil.copy2(kilib.REPO / "tools" / "house_rules.kicad_dru", hw / f"{a.name}.kicad_dru")
    kilib.sync(quiet=True)
    # The PRL only holds per-user view state.
    (hw / f"{a.name}.kicad_prl").unlink(missing_ok=True)

    fw = bdir / "firmware"
    fw.mkdir(exist_ok=True)
    readme = fw / "README.md"
    if not readme.exists():
        readme.write_text(f"# {title} firmware\n\n{FW_README[a.mcu]}\n")
    breadme = bdir / "README.md"
    if not breadme.exists():
        breadme.write_text(
            f"# {title}\n\n"
            f"- Board: {width:g} x {height:g} mm, 2 layers, rev {a.rev}\n"
            f"- Mounting: 4x M2.5 on the Raspberry Pi 58 x 49 mm pattern\n"
            f"- RPi 40-pin header: {'yes (socket on the bottom)' if gpio else 'no'}\n"
            f"- MCU: {a.mcu}\n\n"
            "## Layout\n\n- `hardware/` KiCad project\n- `firmware/` firmware sources\n"
        )
    print(f"created {bdir.relative_to(REPO)}")


if __name__ == "__main__":
    main()
