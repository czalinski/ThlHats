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
        self.symbol(lib_id, ref, value, x, y, rot, footprint, pins=list(pins), fields=fields, **kw)
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
