#!/usr/bin/env python3
"""Bootstrap generator for the probe-helper schematic (docs/probe-helper-pi.md).

Adapter board for the probe meter: a Raspberry Pi with the Waveshare
High-Precision AD HAT (TI ADS1263) runs tools/probe_ads1263.py. This board
carries the resistors and clamps of docs/probe-helper-pi.md "Circuit", all
through-hole:

- J1: 13 right-angle pins at 3.5 mm pitch, plugged into the HAT's 13-way screw
  terminal (Pi standard view, header on top: AVDD AVSS IN0 ... IN9 COM from
  left to right; J1 pin 1 = AVDD). Every terminal gets a pin for strength;
  IN5, IN7 and IN9 are not connected.
- J2: 2x5 box header, ribbon cable to an IDC socket on the HAT's pass-through
  Pi header, pins 31-40 (J2 pin n = Pi pin 30 + n): 8 GPIOs and 2 GND.
- J3: probe leads A (red) and B (black).

AIN assignment: the HAT filters each input (47R series, 47 pF to GND) and puts
100 nF across each pair AIN0/1, 2/3, 4/5, 6/7, 8/9. Sense and IDAC lead of the
same probe share a pair (both end at the probe node, so the 100 nF sees no
signal); each source node pairs with an unused input.

Writes probe-helper.kicad_sch from scratch: once the schematic is edited in
KiCad, stop using this script.

  python3 boards/probe-helper/hardware/gen_schematic.py
"""
import sys
from pathlib import Path

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import schgen  # noqa: E402

FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
FP_D = "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal"
FP_J1 = "Thl_Connector:PinHeader_1x13_P3.50mm_Horizontal"
FP_J2 = "Connector_IDC:IDC-Header_2x05_P2.54mm_Vertical"
FP_J3 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
POWER = {"+5V", "GND"}
MPN = {
    "1.2k": ("Yageo", "MFR-25FBF52-1K2"), "47R": ("Yageo", "MFR-25FBF52-47R"),
    "100R 0.1%": ("Yageo", "MFP-25BRD52-100R"), "100k 0.1%": ("Yageo", "MFP-25BRD52-100K"),
    "10M": ("Yageo", "MFR-25FBF52-10M"), "470R": ("Yageo", "MFR-25FBF52-470R"),
    "1k": ("Yageo", "MFR-25FBF52-1K"), "22R": ("Yageo", "MFR-25FBF52-22R"),
}

# HAT screw terminal, J1 pin -> net (pin 1 = AVDD, 13 = COM)
J1_NETS = {
    "1": "+5V", "2": "GND", "3": "SENSE_B", "4": "IDAC_B", "5": "SENSE_A", "6": "IDAC_A",
    "7": "N_LO", "8": "~", "9": "N_MID", "10": "~", "11": "N_HI", "12": "~", "13": "GND",
}
J1_NAMES = ["AVDD", "AVSS", "IN0", "IN1", "IN2", "IN3", "IN4", "IN5", "IN6", "IN7", "IN8", "IN9", "COM"]
# ribbon to Pi header pins 31-40: J2 pin -> net
J2_NETS = {
    "1": "GPIO6", "2": "GPIO12", "3": "GPIO13", "4": "GND", "5": "GPIO19",
    "6": "GPIO16", "7": "GPIO26", "8": "GPIO20", "9": "GND", "10": "GPIO21",
}
# range: (top GPIO via 1.2k, bottom GPIO via 47R, node, reference to NODE_A)
RANGES = {
    "lo": ("GPIO13", "GPIO19", "N_LO", "100R 0.1%"),
    "mid": ("GPIO16", "GPIO26", "N_MID", "100k 0.1%"),
    "hi": ("GPIO20", "GPIO21", "N_HI", "10M"),
}


def R(s, ref, value, x, y, n1, n2):
    mfr, mpn = MPN[value]
    s.part("Device:R", ref, value, x, y, {"1": n1, "2": n2}, 0, FP_R, mfr, mpn,
           ref_at=(x + 2.54, y - 1.27), value_at=(x + 2.54, y + 1.27), value_justify="left")


def D(s, ref, x, y, anode, cathode):
    # vertical, cathode (pin 1) at the top, anode (pin 2) at the bottom
    s.part("Device:D", ref, "1N4148", x, y, {"1": cathode, "2": anode}, 270, FP_D, "onsemi", "1N4148",
           ref_at=(x + 3.81, y - 1.27), value_at=(x + 3.81, y + 1.27), value_justify="left")


def build():
    s = schgen.Sheet("probe-helper", "Probe helper: ADS1263 HAT adapter", "A", power=POWER, mpn=MPN)
    s.text("Probe helper (docs/probe-helper-pi.md, tools/probe_ads1263.py). Plugs into the Waveshare High-Precision\n"
           "AD HAT's 13-way 3.5 mm screw terminal (J1) and takes 8 Pi GPIOs over a 10-way ribbon from the HAT's\n"
           "pass-through header (J2). Each range is a GPIO divider: top GPIO high + bottom GPIO low puts its node\n"
           "N at 3.3 V x 47 / 1247 = 0.12 V behind ~45 R; both GPIOs as inputs (no pull) float it. The ADC reads\n"
           "N and both probe nodes; IDAC 1 mA out of IN3 (A) or IN1 (B) for the diode test.", 25.4, 22.86)
    # J1: HAT screw terminal
    s.part("Connector_Generic:Conn_01x13", "J1", "AD HAT terminal", 50.8, 76.2, J1_NETS, 0, FP_J1,
           "Sullins Connector Solutions", "PRPC040SBAN-M71RC", ref_at=(50.8, 58.42), value_at=(50.8, 93.98))
    for i, name in enumerate(J1_NAMES):
        s.text(name, 55.88, 61.34 + 2.54 * i, 1.0)
    s.text("J1: 13 single pins cut from a 2.54 mm right-angle\nstrip, soldered at 3.5 mm pitch on the bottom side.\n"
           "Order (Pi standard view): AVDD left ... COM right.", 30.48, 101.6, 1.0)
    # J2: ribbon to Pi pins 31-40
    s.part("Connector_Generic:Conn_02x05_Odd_Even", "J2", "Pi pins 31-40", 50.8, 139.7, J2_NETS, 0, FP_J2,
           "Wurth Elektronik", "61201021621", ref_at=(52.07, 129.54), value_at=(52.07, 149.86))
    s.text("J2 pin n = Pi pin 30 + n: 10-way IDC ribbon (same-side crimp)\n"
           "to an IDC socket on the AD HAT's pass-through pins 31-40\n"
           "(socket pin 1 on Pi pin 31).", 30.48, 157.48, 1.0)
    s.flag(91.44, 63.5, 180)
    s.power("+5V", 91.44, 63.5)
    s.flag(101.6, 63.5)
    s.power("GND", 101.6, 63.5)
    # sources: top 1.2k, bottom 47R, reference to NODE_A
    for i, (name, (top, bot, node, ref)) in enumerate(RANGES.items()):
        x = 129.54 + 25.4 * i
        s.text(f"{name} range", x - 5.08, 45.72, 1.27)
        R(s, f"R{1 + i}", "1.2k", x, 58.42, top, node)
        R(s, f"R{4 + i}", "47R", x, 78.74, node, bot)
        R(s, f"R{7 + i}", ref, x + 10.16, 99.06, node, "NODE_A")
    # probe A node
    R(s, "R10", "1k", 129.54, 127.0, "SENSE_A", "NODE_A")
    R(s, "R11", "1k", 142.24, 127.0, "IDAC_A", "NODE_A")
    R(s, "R12", "470R", 154.94, 127.0, "GPIO12", "NODE_A")
    R(s, "R13", "22R", 167.64, 127.0, "NODE_A", "PROBE_A")
    D(s, "D1", 203.2, 116.84, "NODE_A", "+5V")
    D(s, "D2", 203.2, 144.78, "GND", "NODE_A")
    # probe B node
    R(s, "R14", "1k", 129.54, 162.56, "SENSE_B", "NODE_B")
    R(s, "R15", "1k", 142.24, 162.56, "IDAC_B", "NODE_B")
    R(s, "R16", "470R", 154.94, 162.56, "GPIO6", "NODE_B")
    R(s, "R17", "22R", 167.64, 162.56, "NODE_B", "PROBE_B")
    D(s, "D3", 218.44, 157.48, "NODE_B", "+5V")
    D(s, "D4", 218.44, 185.42, "GND", "NODE_B")
    s.text("D1-D4 clamp the probe nodes to GND and +5 V (AVDD). At the 10 M range\n"
           "the clamps' leakage adds to the nA signal: if R reads finite with the\n"
           "probes open, fit low-leakage DO-35 diodes (1N3595, BAS45A) for D1/D2.", 124.46, 187.96, 1.0)
    s.part("Connector:Screw_Terminal_01x02", "J3", "PROBE A B", 251.46, 139.7, {"1": "PROBE_A", "2": "PROBE_B"}, 0,
           FP_J3, "Phoenix Contact", "1715721", ref_at=(251.46, 133.35), value_at=(251.46, 146.05))
    s.text("J3: 1 = probe A (red), 2 = probe B (black).\nAny 5.0/5.08 mm 2-way terminal fits.", 238.76, 152.4, 1.0)
    return s


def main():
    (HW / "probe-helper.kicad_sch").write_text(build().render())
    print("wrote probe-helper.kicad_sch")


if __name__ == "__main__":
    main()
