#!/usr/bin/env python3
"""Bootstrap generator for the io-card schematic ("LabJack light",
docs/requirements.md 4.1 relay drive / GPIO / analog in, 4.5 stack bus).

Circuits from boards/can-controller/hardware/gen_schematic.py (relay_sheet,
io_sheet), now fed from the stack bus (tools/stack_bus.py) instead of an MCU
on the same board; the core's PIC32MK drives RLY1-4 and GPIO1-4 and reads
AI1P/AI1N/AI2P/AI2N on its ADC against VMID (the core's OA5 follower).

  Relays   4 outputs for 12 V coil relays: 2 x AQW212 PhotoMOS sourcing +12 V
           (RACK, from J11) to OUTn; LED side from RLYn (LOGIC). Flyback diode
           and red LED per output, shared PTC.
  GPIO     4 x 3.3 V, 330R series + BAT54S clamp (not 24 V tolerant).
  AI       2 differential, +-116 V per input: 10M / 130k to VMID per leg,
           100 nF across 130k, BAT54S clamp.
  Stack    J10 logic bus, J11 rack power: Samtec ESQ stacking sockets on top.

Domains: LOGIC (+3V3/+5V/GND from the core, floating) and RACK (+12V /
GND_RACK at J11): they meet only inside K1/K2 (1500 Vrms, functional).

Writes io-card.kicad_sch from scratch: once the schematic is edited in KiCad,
stop using this script.

  python3 boards/io-card/hardware/gen_schematic.py
"""
import sys
from pathlib import Path

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import schgen  # noqa: E402
import stack_bus as sb  # noqa: E402

FP = schgen.FP
FP_PTC = "Fuse:Fuse_1812_4532Metric_Pad1.30x3.40mm_HandSolder"
FP_SPTD = "Thl_Connector:PhoenixContact_SPTD_1,5_{n}-H-3,5_2x{n:02d}_P3.5mm_Horizontal"
POWER = {"+3V3", "+5V", "+12V", "GND"}
MPN = {
    "470R": ("Yageo", "RC1206FR-07470RL"), "4.7k": ("Yageo", "RC1206FR-074K7L"),
    "330R": ("Yageo", "RC1206FR-07330RL"), "10M": ("Yageo", "RC1206FR-0710ML"),
    "130k": ("Yageo", "RC1206FR-07130KL"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),          # 0805, decoupling
    "100nF 50V X7R 1206": ("Murata", "GRM319R71H104KA01D"),     # 1206, AI filters
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
}
USED = {f"RLY{n}" for n in range(1, 5)} | {f"GPIO{n}" for n in range(1, 5)} \
    | {"VMID", "AI1P", "AI1N", "AI2P", "AI2N"} | sb.SUPPLIES


def bus_nets():
    out = {}
    for k in sb.BUS:
        name = sb.BUS[sb.socket_pin(k)]
        out[str(k)] = name if name in USED else "~"
    return out


def relays(s):
    s.text("RELAY DRIVE (requirements 4.1): four outputs for standard 12 V coil relays. 2 x AQW212 PhotoMOS (2 Form A,\n"
           "60 V, 0.5 A, 2.5 R max per channel). LED side LOGIC: RLYn (core PIC32 pin, 3.3 V) -> 470R -> LED -> GND,\n"
           "(3.3 - 1.5 V) / 470R >= 3.8 mA against 3 mA max operate. Output side RACK: +12V (J11, after the core's\n"
           "input protection) -> F30 -> V12_RLY -> contact -> OUTn; the coil returns to GND_RACK on the same\n"
           "terminal pair. D40-D43 catch the coil kick; red LEDs D44-D47 show the real output state.",
           25.4, 25.4)
    s.part("Device:Polyfuse", "F30", "1.1A", 152.4, 60.96, {"1": "+12V", "2": "V12_RLY"}, 90, FP_PTC,
           "Littelfuse", "1812L110/16DR", ref_at=(152.4, 57.15), value_at=(152.4, 64.77))
    s.C("C70", "10uF 25V X7R", 172.72, 76.2, "V12_RLY", "GND_RACK")
    s.C("C71", "10uF 25V X7R", 139.7, 76.2, "+12V", "GND_RACK")
    s.flag(185.42, 55.88); s.llabel("V12_RLY", 185.42, 55.88, 0)
    for k in range(2):
        y = 101.6 + k * 45.72
        a, b = 2 * k + 1, 2 * k + 2
        s.part("Thl_Isolator:AQW212", f"K{1 + k}", "AQW212", 127.0, y,
               {"1": f"RLED{a}", "2": "GND", "3": f"RLED{b}", "4": "GND",
                "8": "V12_RLY", "7": f"OUT{a}", "6": "V12_RLY", "5": f"OUT{b}"}, 0,
               "Package_DIP:DIP-8_W7.62mm", "Panasonic", "AQW212", ref_at=(127.0, y - 12.7), value_at=(127.0, y + 12.7))
        for ch, dy in ((a, -7.62), (b, 10.16)):
            s.R(f"R{50 + ch}", "470R", 88.9, y + dy, f"RLY{ch}", f"RLED{ch}", rot=90)
    s.text("AQW212: 1/2 LED1, 3/4 LED2, 8-7 output 1, 6-5 output 2. K1/K2 are the only LOGIC | RACK crossing.",
           76.2, 177.8, 1.0)
    conn = {}
    for ch in range(1, 5):
        x = 200.66 + (ch - 1) * 20.32
        s.part("Device:D", f"D{39 + ch}", "1N4148W", x, 106.68, {"1": f"OUT{ch}", "2": "GND_RACK"}, 90,
               FP["SOD123"], "Diodes Incorporated", "1N4148W-7-F",
               ref_at=(x + 5.08, 105.41), value_at=(x + 5.08, 107.95), value_justify="left")
        s.led_chain(f"D{43 + ch}", f"R{54 + ch}", "red", "LTST-C150KRKT", x, 132.08, f"OUT{ch}", rval="4.7k",
                    ground="GND_RACK")
        conn[str(ch)] = f"OUT{ch}"
        conn[str(4 + ch)] = "GND_RACK"
    s.part("Connector_Generic:Conn_02x04_Top_Bottom", "J30", "RELAY", 302.26, 106.68, conn, 0, FP_SPTD.format(n=4),
           "Phoenix Contact", "1841513", ref_at=(302.26, 96.52), value_at=(302.26, 118.11))
    s.text("J30 (SPTD 1,5/4-H-3,5, double-level push-in): lower level 1-4 = OUT1-4 (+12 V when on),\n"
           "upper level 5-8 = 0 V (GND_RACK). Coils up to about 100 mA each; F30 1.1 A hold for all four.",
           271.78, 124.46, 1.0)


def gpio(s):
    s.text("GPIO (requirements 4.1): four 3.3 V lines straight from core PIC32 pins (in or out). 330R in series and a\n"
           "BAT54S clamp to +3V3/GND at the card: ESD and a brief 5 V short only, NOT 24 V tolerant.",
           25.4, 190.5)
    conn = {}
    for ch in range(1, 5):
        x = 33.02 + (ch - 1) * 33.02
        s.R(f"R{70 + ch}", "330R", x, 213.36, f"GPIO{ch}", f"IO{ch}")
        s.part("Diode:BAT54S", f"D{50 + ch}", "BAT54S", x + 12.7, 233.68,
               {"1": "GND", "2": "+3V3", "3": f"GPIO{ch}"}, 90, FP["SOT23"], "Nexperia", "BAT54S,215",
               ref_at=(x + 17.78, 231.14), value_at=(x + 17.78, 236.22), value_justify="left")
        conn[str(ch)] = f"IO{ch}"
        conn[str(6 + ch)] = "GND"
    return conn


def analog(s, conn):
    s.text("ANALOG IN (requirements 4.1): two differential channels, about +-116 V per input, 10 Mohm per input.\n"
           "Each leg: 10M / 130k to VMID (1.65 V, the core's OA5 follower on bus pin 36), 100 nF across 130k\n"
           "(fc ~ 12 Hz), BAT54S clamp. The core reads both legs and subtracts: VMID and the common mode cancel.\n"
           "CMRR is set by divider matching (1 %: up to ~0.5 V error at 50 V common mode; calibrate or fit 0.1 %).\n"
           "R80-R83: RC1206 working voltage 200 V; keep the legs within the +-116 V range.",
           162.56, 190.5)
    legs = (("AI1P", "AIN1P"), ("AI1N", "AIN1N"), ("AI2P", "AIN2P"), ("AI2N", "AIN2N"))
    for i, (bus, ext) in enumerate(legs):
        x = 165.1 + i * 35.56
        s.R(f"R{80 + i}", "10M", x, 220.98, ext, bus, rot=90)
        s.R(f"R{84 + i}", "130k", x + 5.08, 236.22, bus, "VMID")
        s.C(f"C{80 + i}", "100nF 50V X7R 1206", x + 20.32, 236.22, bus, "VMID")
        s.part("Diode:BAT54S", f"D{55 + i}", "BAT54S", x + 12.7, 254.0, {"1": "GND", "2": "+3V3", "3": bus},
               90, FP["SOT23"], "Nexperia", "BAT54S,215", ref_at=(x + 17.78, 251.46), value_at=(x + 17.78, 256.54),
               value_justify="left")
    conn.update({"5": "AIN1P", "6": "AIN2P", "11": "AIN1N", "12": "AIN2N"})
    s.part("Connector_Generic:Conn_02x06_Top_Bottom", "J40", "IO", 132.08, 251.46, conn, 0, FP_SPTD.format(n=6),
           "Phoenix Contact", "1841539", ref_at=(132.08, 238.76), value_at=(132.08, 266.7))
    s.text("J40 (SPTD 1,5/6-H-3,5): lower level 1-4 IO1-4, 5 AI1+, 6 AI2+;\n"
           "upper level 7-10 GND (one per GPIO), 11 AI1-, 12 AI2-.", 101.6, 275.59, 1.0)


def stack(s):
    s.part("Connector_Generic:Conn_02x20_Odd_Even", "J10", "STACK BUS", 368.3, 101.6, bus_nets(), 0,
           "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical", "Samtec", "ESQ-120-14-G-D",
           ref_at=(369.57, 73.66), value_at=(369.57, 129.54))
    pwr = {str(k): sb.PWR12[sb.socket_pin(k)] for k in sb.PWR12}
    s.part("Connector_Generic:Conn_02x03_Odd_Even", "J11", "RACK 12V", 368.3, 162.56, pwr, 0,
           "Connector_PinSocket_2.54mm:PinSocket_2x03_P2.54mm_Vertical", "Samtec", "ESQ-103-14-G-D",
           ref_at=(369.57, 154.94), value_at=(369.57, 170.18))
    s.flag(393.7, 152.4, 180); s.llabel("GND_RACK", 393.7, 152.4, 0)
    for i, name in enumerate(("+3V3", "+5V", "+12V")):
        x = 337.82 + 17.78 * i
        s.flag(x, 63.5); s.power(name, x, 63.5)
    s.flag(391.16, 63.5, 180); s.power("GND", 391.16, 63.5)
    s.C("C1", "100nF 50V X7R", 342.9, 190.5, "+3V3", "GND", decouple=True)
    s.C("C2", "10uF 25V X7R", 363.22, 190.5, "+3V3", "GND")
    s.text("C1/C2 at J10: the clamp diodes return ESD current into +3V3.\n"
           "J10/J11: Samtec ESQ stacking sockets (top side, tails through to the card below). Pad k\n"
           "carries bus pin stack_bus.socket_pin(k) (KiCad socket columns are mirrored). Signals this\n"
           "card does not use pass through the connector. +5V is not used on this card.",
           330.2, 205.74, 1.0)


def build():
    s = schgen.Sheet("io-card", "IO card: relays, GPIO, differential AI", "A", power=POWER, mpn=MPN)
    relays(s)
    analog(s, gpio(s))
    stack(s)
    return s


def main():
    (HW / "io-card.kicad_sch").write_text(build().render())
    print("wrote io-card.kicad_sch")


if __name__ == "__main__":
    main()
