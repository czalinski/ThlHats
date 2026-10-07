#!/usr/bin/env python3
"""Build the host side of the PIC module interface (POC boards).

  Thl_Module:PIC32MK_Module           symbol, from lib/symbol_src/Thl_Module/PIC32MK_Module.csv
  Thl_Module:PIC32MK_Module_Host      footprint: two 2 x 20, 2.54 mm pin headers

Everything comes from boards/pic-module/hardware/module_pinout.py, so host
boards always match the module. The footprint origin is the module's top-left
corner; pads A1-A40 are the module's J3 pins, B1-B40 its J4 pins. A9 (key: the
module blocks that socket position) and A10 (creepage spacer between the RACK
pins A1-A8 and the LOGIC pins) have no pad: pull those two pins out of the
header before soldering it. Silkscreen shows the module outline; the
courtyard covers the whole module (it sits about 6 mm above the host).

Power pins: the first pin of each supply net is power_out (the module drives
+3V3, +5V, GND, +12V and GND_RACK), the others passive, so host ERC sees one
driver per net.

  python3 lib/footprint_src/Thl_Module/pic_module.py
  (then tools/make_symbol.py lib/symbol_src/Thl_Module/PIC32MK_Module.csv)
"""
import sys
import uuid
from pathlib import Path

LIB = Path(__file__).resolve().parents[2]
REPO = LIB.parent
sys.path.insert(0, str(REPO / "boards/pic-module/hardware"))
import module_pinout as mp  # noqa: E402

NAME = "PIC32MK_Module_Host"
SYM = "PIC32MK_Module"
FP_DIR = LIB / "footprints/Thl_Module.pretty"
CSV = LIB / "symbol_src/Thl_Module" / f"{SYM}.csv"
MODEL = "${KIPRJMOD}/../../../lib/3dmodels/Connector_PinHeader_2.54mm.3dshapes/PinHeader_2x20_P2.54mm_Vertical.step"
SUPPLIES = ("+12V", "GND_RACK", "+5V", "+3V3", "GND")
NO_PAD = {("J3", 9), ("J3", 10)}


def u():
    return str(uuid.uuid4())


def line(x0, y0, x1, y1, layer, w):
    return (f'\t(fp_line\n\t\t(start {x0:g} {y0:g})\n\t\t(end {x1:g} {y1:g})\n'
            f'\t\t(stroke\n\t\t\t(width {w:g})\n\t\t\t(type solid)\n\t\t)\n\t\t(layer "{layer}")\n\t\t(uuid "{u()}")\n\t)\n')


def rect(x0, y0, x1, y1, layer, w):
    return (line(x0, y0, x1, y0, layer, w) + line(x1, y0, x1, y1, layer, w) +
            line(x1, y1, x0, y1, layer, w) + line(x0, y1, x0, y0, layer, w))


def text(kind, txt, x, y, layer, hide=False, size=1.0):
    h = "\n\t\t(hide yes)" if hide else ""
    return (f'\t(property "{kind}" "{txt}"\n\t\t(at {x:g} {y:g} 0)\n\t\t(layer "{layer}"){h}\n\t\t(uuid "{u()}")\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size:g} {size:g})\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')


def user_text(txt, x, y, layer, size=1.0):
    return (f'\t(fp_text user "{txt}"\n\t\t(at {x:g} {y:g} 0)\n\t\t(layer "{layer}")\n\t\t(uuid "{u()}")\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size:g} {size:g})\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')


def pad_name(conn, pin):
    return ("A" if conn == "J3" else "B") + str(pin)


def footprint():
    W, H = mp.W, mp.H
    s = f'(footprint "{NAME}"\n\t(version 20241229)\n\t(generator "pic_module.py")\n\t(layer "F.Cu")\n'
    s += text("Reference", "REF**", W / 2, -1.5, "F.SilkS")
    s += text("Value", NAME, W / 2, H / 2 + 4, "F.Fab")
    s += text("Datasheet", "", 0, 0, "F.Fab", True)
    s += ('\t(descr "Host side of the ThlHats PIC32MK + power module (boards/pic-module): two 2x20 2.54 mm pin '
          'headers, A9/A10 omitted (key/spacer); origin = module top-left corner")\n')
    s += '\t(tags "PIC32MK module POC header 2.54mm")\n\t(attr through_hole)\n'
    s += rect(0, 0, W, H, "F.Fab", 0.1)
    s += rect(-0.12, -0.12, W + 0.12, H + 0.12, "F.SilkS", 0.12)
    s += rect(-0.25, -0.25, W + 0.25, H + 0.25, "F.CrtYd", 0.05)
    s += user_text("${REFERENCE}", W / 2, H / 2, "F.Fab")
    s += user_text("PIC MODULE", W / 2, H / 2 - 4, "F.SilkS", 1.5)
    s += user_text("RACK", 9.5, 6.0, "F.SilkS", 0.8)
    kx, ky = mp.header_pos("J3", 9)
    s += user_text("KEY", kx + 5.0, ky, "F.SilkS", 0.8)
    for conn in ("J3", "J4"):
        for pin in range(1, 41):
            if (conn, pin) in NO_PAD:
                continue
            x, y = mp.header_pos(conn, pin)
            shape = "rect" if pin == 1 else "circle"
            s += (f'\t(pad "{pad_name(conn, pin)}" thru_hole {shape}\n\t\t(at {x:g} {y:g})\n\t\t(size 1.7 1.7)\n'
                  f'\t\t(drill 1)\n\t\t(layers "*.Cu" "*.Mask")\n\t\t(remove_unused_layers no)\n\t\t(uuid "{u()}")\n\t)\n')
        x1, y1 = mp.header_pos(conn, 1)
        s += (f'\t(model "{MODEL}"\n\t\t(offset\n\t\t\t(xyz {x1:g} {-y1:g} 0)\n\t\t)\n\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n'
              f'\t\t(rotate\n\t\t\t(xyz 0 0 0)\n\t\t)\n\t)\n')
    s += "\t(embedded_fonts no)\n)\n"
    FP_DIR.mkdir(parents=True, exist_ok=True)
    (FP_DIR / f"{NAME}.kicad_mod").write_text(s)


def symbol_csv():
    a = mp.assign()
    seen = set()
    rows = []
    for conn, side in (("J3", "left"), ("J4", "right")):
        for pin in range(1, 41):
            if (conn, pin) in NO_PAD:
                rows.append(f",,,{side}")
                continue
            net = a[(conn, pin)]
            if net in SUPPLIES:
                typ = "passive" if net in seen else "power_out"
                seen.add(net)
            else:
                typ = "bidirectional"
            rows.append(f"{pad_name(conn, pin)},{net},{typ},{side}")
    head = [
        f"# name: {SYM}",
        "# mpn: PRPC020DAAN-RC",
        "# manufacturer: Sullins Connector Solutions",
        "# reference: M",
        f"# footprint: Thl_Module:{NAME}",
        "# description: ThlHats PIC32MK1024MCM064 + power module (boards/pic-module), host side. Pins A1-A40 = module "
        "J3, B1-B40 = module J4 (A9 key and A10 spacer have no pin). The module supplies +12V/GND_RACK (RACK) and "
        "+5V/+3V3/GND (LOGIC, floating). Generated by lib/footprint_src/Thl_Module/pic_module.py from "
        "boards/pic-module/hardware/module_pinout.py. MPN is one 2x20 2.54 mm header: fit two.",
        "# keywords: PIC32MK module POC header 2.54mm",
        "# fp_filters: PIC32MK_Module_Host*",
        "pin,name,type,side",
    ]
    CSV.parent.mkdir(parents=True, exist_ok=True)
    CSV.write_text("\n".join(head + rows) + "\n")


if __name__ == "__main__":
    footprint()
    symbol_csv()
    print("wrote", FP_DIR / f"{NAME}.kicad_mod", CSV)
