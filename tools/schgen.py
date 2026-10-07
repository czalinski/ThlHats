"""Helpers for generating flat KiCad schematics from Python (POC boards).

Extracted from boards/can-controller/hardware/gen_schematic.py. A board's
generator builds one `Sheet`, places parts with `part()` (nets given per pin
number; each pin end gets a label, power symbol or no-connect) and writes
`render()` to <board>.kicad_sch. Net names: "~" = no-connect, names in
`power` = power symbols, anything else = a local label.

    import schgen
    s = schgen.Sheet("pic-module", "PIC module", "A", power={"+3V3", "GND"}, mpn=MPN)
    s.R("R1", "10k", 50.8, 50.8, "+3V3", "MCLR")
    open("pic-module.kicad_sch", "w").write(s.render())
"""
import importlib.util
import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("nb", REPO / "tools/new_board.py")
nb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nb)
q, uid = nb.q, nb.uid

FP = {
    "R": "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder",
    "C": "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder",
    "Cd": "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder",
    "LED": "LED_SMD:LED_1206_3216Metric_Pad1.42x1.75mm_HandSolder",
    "FB": "Inductor_SMD:L_1206_3216Metric_Pad1.22x1.90mm_HandSolder",
    "SOD123": "Diode_SMD:D_SOD-123",
    "SOT23": "Package_TO_SOT_SMD:SOT-23",
}


def rnd(v):
    return round(v * 100) / 100


class Sheet(nb.Sch):
    """Flat A3 schematic with net-labelled pin ends."""

    def __init__(self, project, title, rev, power=("+3V3", "+5V", "GND"), mpn=None):
        super().__init__(project, title, rev)
        self.power_nets = set(power)
        self.mpn = mpn or {}

    def pin_end(self, lib_id, x, y, rot, num):
        px, py, ang = nb.pin_positions(lib_id)[num]
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        rx, ry = px * c - py * s, px * s + py * c
        out = (ang + rot + 180) % 360
        return rnd(x + rx), rnd(y - ry), out

    def llabel(self, name, x, y, out):
        rot = {0: 0, 90: 90, 180: 180, 270: 270}[out]
        self.label(name, x, y, rot, "left" if out in (0, 90) else "right")

    def pwrsym(self, name, x, y, out):
        dx, dy = {0: (2.54, 0), 180: (-2.54, 0), 90: (0, -2.54), 270: (0, 2.54)}[out]
        ex, ey = rnd(x + dx), rnd(y + dy)
        self.wire(x, y, ex, ey)
        gnd = name.startswith("GND")
        rot = ({270: 0, 90: 180, 180: 270, 0: 90} if gnd else {90: 0, 270: 180, 180: 90, 0: 270})[out]
        self.power(name, ex, ey, rot)

    def net(self, name, x, y, out):
        if name == "":
            return
        if name == "~":
            self.no_connect(x, y)
        elif name in self.power_nets:
            self.pwrsym(name, x, y, out)
        else:
            self.llabel(name, x, y, out)

    def part(self, lib_id, ref, value, x, y, nets, rot=0, footprint="", mfr=None, mpn=None, **kw):
        pins = nb.pin_positions(lib_id)
        fields = {"Manufacturer": mfr, "MPN": mpn} if mpn else {}
        fields.update(kw.pop("fields", {}) or {})
        dnp = kw.pop("dnp", False)
        self.symbol(lib_id, ref, value, x, y, rot, footprint, pins=list(pins), fields=fields, **kw)
        if dnp:
            self.items[-1] = self.items[-1].replace("(dnp no)", "(dnp yes)", 1)
        for num, n in nets.items():
            px, py, out = self.pin_end(lib_id, x, y, rot, num)
            self.net(n, px, py, out)

    def R(self, ref, value, x, y, n1, n2, rot=0):
        mfr, mpn = self.mpn[value]
        if rot == 90:
            at = dict(ref_at=(x, y - 2.54), value_at=(x, y + 2.54))
        else:
            at = dict(ref_at=(x + 2.54, y - 1.27), value_at=(x + 2.54, y + 1.27), value_justify="left")
        self.part("Device:R", ref, value, x, y, {"1": n1, "2": n2}, rot, FP["R"], mfr, mpn, **at)

    def C(self, ref, value, x, y, n1, n2, decouple=False):
        mfr, mpn = self.mpn[value]
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
        return super().render().replace('(paper "A4")', '(paper "A3")')


class SubSheet(Sheet):
    """One sub-sheet of a hierarchical schematic (A3). Nets named "/X" become
    global labels "X" (shared between sheets); others stay local labels."""

    def __init__(self, project, root_uuid, file, name, page, title, rev, power=("+3V3", "+5V", "GND"), mpn=None):
        super().__init__(project, title, rev, power, mpn)
        self.root_uuid = root_uuid
        self.file, self.name, self.page = file, name, page
        self.sheet_uuid = uid()
        self.own_uuid = uid()
        self.pwr = self.flg = 100 * page      # #PWR/#FLG references unique across sheets

    def symbol(self, lib_id, ref, value, x, y, rot=0, footprint="", **kw):
        root = self.root
        self.root = self.root_uuid + "/" + self.sheet_uuid
        u = super().symbol(lib_id, ref, value, x, y, rot, footprint, **kw)
        self.root = root
        return u

    def glabel(self, name, x, y, out, shape="bidirectional"):
        rot = {0: 0, 90: 90, 180: 180, 270: 270}[out]
        just = "left" if out in (0, 90) else "right"
        self.items.append(
            f"\t(global_label {q(name)}\n\t\t(shape {shape})\n\t\t(at {x:g} {y:g} {rot})\n"
            f"\t\t(fields_autoplaced yes)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {just})\n\t\t)\n\t\t(uuid {q(uid())})\n"
            f"\t\t(property \"Intersheetrefs\" \"${{INTERSHEET_REFS}}\"\n\t\t\t(at {x:g} {y:g} 0)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n\t)\n")

    def net(self, name, x, y, out):
        if name.startswith("/") and name not in self.power_nets:
            self.glabel(name[1:], x, y, out)
        else:
            super().net(name, x, y, out)

    def render(self):
        text = super().render()
        text = text.replace(f'(uuid {q(self.root)})', f'(uuid {q(self.own_uuid)})', 1)
        return re.sub(r'\t\(sheet_instances.*?\n\t\)\n', '', text, flags=re.S)


def root_sheet(project, root_uuid, sheets, title, rev, notes=""):
    """Root schematic text: title, notes and one sheet symbol per SubSheet."""
    sch = nb.Sch(project, title, rev)
    sch.root = root_uuid
    sch.text(title, 25.4, 30.48, 2.54)
    if notes:
        sch.text(notes, 25.4, 38.1)
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
            f"\t\t(instances\n\t\t\t(project {q(project)}\n\t\t\t\t(path {q('/' + root_uuid)}\n\t\t\t\t\t(page {q(str(sh.page))})\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
    sch.items.extend(blocks)
    return sch.render()
