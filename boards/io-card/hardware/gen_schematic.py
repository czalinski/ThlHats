#!/usr/bin/env python3
"""Bootstrap generator for the io-card schematic ("LabJack light",
docs/requirements.md 4.1 relay drive / GPIO / analog in, 4.5 stack bus).

Circuits from boards/can-controller/hardware/gen_schematic.py (relay_sheet,
io_sheet), now fed from the stack bus (tools/stack_bus.py) instead of an MCU
on the same board; the core's PIC32MK drives RLY1-4 and GPIO1-4 and reads
AI1P/AI1N/AI2P/AI2N on its ADC against VMID (the core's OA5 follower).

  Relays   4 drivers for EXTERNAL relay coils: 2 x AQW212 PhotoMOS sourcing
           V_RLY to OUTn; LED side from RLYn (LOGIC). V_RLY = rack +12V (J11)
           or an external coil supply up to 24 V (J30 pos. 5), chosen by JP1,
           then the shared PTC. Flyback diode and red LED per output.
  GPIO     4 x 3.3 V, 330R series + BAT54S clamp (not 24 V tolerant).
  AI       2 differential, +-116 V per input: 10M / 130k to VMID per leg,
           100 nF across 130k, BAT54S clamp.
  AO       4 x 0-10 V, 10 mA, RACK domain (rack +12 V, 0 V = GND_RACK): I2C1
           from the bus through an ISO1540, MCP4728 quad DAC (0x60, 4.096 V
           internal reference), OPA4171 x 2.5 with 47R inside the loop.
  Stack    J10 logic bus, J11 rack power: Samtec ESQ stacking sockets on top.

Domains: LOGIC (+3V3/+5V/GND from the core, floating) and RACK (+12V /
GND_RACK at J11): they meet only inside K1/K2 (1500 Vrms, functional) and
U90 (ISO1540, 2500 Vrms).

Writes io-card.kicad_sch from scratch: once the schematic is edited in KiCad,
stop using this script.

  python3 boards/io-card/hardware/gen_schematic.py
"""
import re
import sys
from pathlib import Path

HW = Path(__file__).resolve().parent
sys.path.insert(0, str(HW.parents[2] / "tools"))
import schgen  # noqa: E402
import stack_bus as sb  # noqa: E402

FP = schgen.FP
FP_PTC = "Fuse:Fuse_1812_4532Metric_Pad1.30x3.40mm_HandSolder"
FP_MC = "Connector_Phoenix_MC:PhoenixContact_MC_1,5_{n}-G-3.5_1x{n:02d}_P3.50mm_Horizontal"
POWER = {"+3V3", "+5V", "+12V", "GND"}
MPN = {
    "470R": ("Yageo", "RC1206FR-07470RL"), "4.7k": ("Yageo", "RC1206FR-074K7L"),
    "330R": ("Yageo", "RC1206FR-07330RL"), "10M": ("Yageo", "RC1206FR-0710ML"),
    "130k": ("Yageo", "RC1206FR-07130KL"), "1k": ("Yageo", "RC1206FR-071KL"),
    "100nF 50V X7R": ("Murata", "GRM21BR71H104KA01L"),          # 0805, decoupling
    "100nF 50V X7R 1206": ("Murata", "GRM319R71H104KA01D"),     # 1206, AI filters
    "10uF 25V X7R": ("Murata", "GRM31CR71E106KA12L"),
    "4.7uF 50V X7R": ("Murata", "GRM31CR71H475KA12L"),
    "47R": ("Yageo", "RC1206FR-0747RL"),
    "10k 0.1%": ("Yageo", "RT1206BRD0710KL"), "15k 0.1%": ("Yageo", "RT1206BRD0715KL"),
    "1nF 50V C0G": ("Murata", "GRM3195C1H102JA01D"),
}
USED = {f"RLY{n}" for n in range(1, 5)} | {f"GPIO{n}" for n in range(1, 5)} \
    | {"VMID", "AI1P", "AI1N", "AI2P", "AI2N", "SCL", "SDA"} | sb.SUPPLIES


def bus_nets():
    out = {}
    for k in sb.BUS:
        name = sb.BUS[sb.socket_pin(k)]
        out[str(k)] = name if name in USED else "~"
    return out


def relays(s):
    s.text("RELAY DRIVE (requirements 4.1): four drivers for EXTERNAL relay coils. 2 x AQW212 PhotoMOS (2 Form A, 60 V,\n"
           "0.5 A, 2.5 R max per channel). LED side LOGIC: RLYn (core PIC32 pin, 3.3 V) -> 470R -> LED -> GND,\n"
           "(3.3 - 1.5 V) / 470R >= 3.8 mA against 3 mA max operate. Output side RACK: V_RLY -> contact -> OUTn;\n"
           "the coil returns to GND_RACK on the same terminal pair. Coil supply by JP1: 1-2 rack +12V (J11),\n"
           "2-3 external supply on J30 position 9 (up to 24 V; its 0 V on position 10 = GND_RACK). F30 (33 V)\n"
           "fuses either. D40-D43 catch the coil kick; red LEDs D44-D47 show the real output state.",
           25.4, 25.4)
    s.part("Jumper:Jumper_3_Open", "JP1", "COIL SUPPLY", 114.3, 60.96,
           {"1": "+12V", "2": "V_COIL_SEL", "3": "V_COIL_EXT"}, 0,
           "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", "Samtec", "TSW-103-07-G-S",
           ref_at=(114.3, 55.88), value_at=(114.3, 68.58))
    s.part("Device:Polyfuse", "F30", "1.1A 33V", 152.4, 60.96, {"1": "V_COIL_SEL", "2": "V_RLY"}, 90, FP_PTC,
           "Littelfuse", "1812L110/33MR", ref_at=(152.4, 57.15), value_at=(152.4, 64.77))
    s.C("C70", "4.7uF 50V X7R", 172.72, 76.2, "V_RLY", "GND_RACK")
    s.C("C71", "10uF 25V X7R", 96.52, 76.2, "+12V", "GND_RACK")
    s.flag(185.42, 55.88); s.llabel("V_RLY", 185.42, 55.88, 0)
    s.flag(124.46, 76.2, 180); s.llabel("V_COIL_EXT", 124.46, 76.2, 0)
    for k in range(2):
        y = 101.6 + k * 45.72
        a, b = 2 * k + 1, 2 * k + 2
        s.part("Thl_Isolator:AQW212", f"K{1 + k}", "AQW212", 127.0, y,
               {"1": f"RLED{a}", "2": "GND", "3": f"RLED{b}", "4": "GND",
                "8": "V_RLY", "7": f"OUT{a}", "6": "V_RLY", "5": f"OUT{b}"}, 0,
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
        conn[str(2 * ch - 1)] = f"OUT{ch}"
        conn[str(2 * ch)] = "GND_RACK"
    conn["9"] = "V_COIL_EXT"
    conn["10"] = "GND_RACK"
    s.part("Connector:Screw_Terminal_01x10", "J30", "RELAY", 302.26, 106.68, conn, 0, FP_MC.format(n=10),
           "Phoenix Contact", "1844294", ref_at=(302.26, 91.44), value_at=(302.26, 123.19))
    s.text("J30 (MC 1,5/10-G-3,5 header, 7.7 mm: fits under the next card; plug FMC 1,5/10-ST-3,5 push-in):\n"
           "1/2 OUT1 / 0 V, 3/4 OUT2 / 0 V, 5/6 OUT3 / 0 V, 7/8 OUT4 / 0 V (OUTn = coil +, V_RLY when on),\n"
           "9/10 external coil supply + / 0 V (0 V = GND_RACK). Coils up to about 100 mA each; F30 1.1 A hold\n"
           "for all four. LEDs: 2 mA at 12 V, 4.7 mA at 24 V.",
           266.7, 129.54, 1.0)


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
        conn[str(2 * ch - 1)] = f"IO{ch}"
        conn[str(2 * ch)] = "GND"
    return conn


def analog(s, conn):
    s.text("ANALOG IN (requirements 4.1): two differential channels, about +-116 V per input, 10 Mohm per input.\n"
           "Each leg: 10M / 130k to VMID (1.65 V, the core's OA5 follower on bus pin 36), 100 nF across 130k\n"
           "(fc ~ 12 Hz), BAT54S clamp. The core reads both legs and subtracts: VMID and the common mode cancel.\n"
           "CMRR is set by divider matching (1 %: up to ~0.5 V error at 50 V common mode; calibrate or fit 0.1 %).\n"
           "R80-R83: RC1206 working voltage 200 V; keep the legs within the +-116 V range.\n"
           "VMID arrives through R88 1k + C85 100 nF (VMID_F): the core's OA5 is rated for 32 pF of load\n"
           "(DS60001519D 27.6); R88 isolates it from the stack wiring and the dividers. Both legs see the same\n"
           "VMID_F, so the drop on R88 (<= 46 uA x 1k) cancels in the difference.",
           162.56, 187.96)
    s.R("R88", "1k", 320.04, 220.98, "VMID", "VMID_F", rot=90)
    s.C("C85", "100nF 50V X7R", 335.28, 231.14, "VMID_F", "GND", decouple=True)
    legs = (("AI1P", "AIN1P"), ("AI1N", "AIN1N"), ("AI2P", "AIN2P"), ("AI2N", "AIN2N"))
    for i, (bus, ext) in enumerate(legs):
        x = 165.1 + i * 35.56
        s.R(f"R{80 + i}", "10M", x, 220.98, ext, bus, rot=90)
        s.R(f"R{84 + i}", "130k", x + 5.08, 236.22, bus, "VMID_F")
        s.C(f"C{80 + i}", "100nF 50V X7R 1206", x + 20.32, 236.22, bus, "VMID_F")
        s.part("Diode:BAT54S", f"D{55 + i}", "BAT54S", x + 12.7, 254.0, {"1": "GND", "2": "+3V3", "3": bus},
               90, FP["SOT23"], "Nexperia", "BAT54S,215", ref_at=(x + 17.78, 251.46), value_at=(x + 17.78, 256.54),
               value_justify="left")
    conn.update({"9": "AIN1P", "10": "AIN1N", "11": "AIN2P", "12": "AIN2N"})
    s.part("Connector:Screw_Terminal_01x12", "J40", "IO", 137.16, 251.46, conn, 0, FP_MC.format(n=12),
           "Phoenix Contact", "1844317", ref_at=(137.16, 233.68), value_at=(137.16, 269.24))
    s.text("J40 (MC 1,5/12-G-3,5, plug FMC 1,5/12-ST-3,5): 1/2 IO1 / GND, 3/4 IO2 / GND,\n"
           "5/6 IO3 / GND, 7/8 IO4 / GND, 9/10 AI1+ / AI1-, 11/12 AI2+ / AI2-.", 96.52, 276.86, 1.0)


def hpart(s, lib_id, ref, value, x, y, n1, n2, fp):
    """Horizontal two-pin part (pin 1 left), fields above and below, upright text."""
    mfr, mpn = s.mpn[value]
    s.part(lib_id, ref, value.replace(" 1206", ""), x, y, {"1": n1, "2": n2}, 90, fp, mfr, mpn,
           ref_at=(x, y - 2.54), value_at=(x, y + 2.54))
    s.items[-1] = re.sub(r'(\(property "(?:Reference|Value)" "[^"]*"\n\t\t\t\(at [-\d.]+ [-\d.]+ )0\)', r"\g<1>90)",
                         s.items[-1])


def ao_channel(s, n, pins, x, y):
    """One output stage drawn with wires: amplifier at (x, y), feedback below it."""
    pp, pm, po = pins
    s.part("Amplifier_Operational:LM2902", "U93", "OPA4171", x, y, {pp: f"DAC{n}", pm: "", po: ""}, 0,
           "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", "Texas Instruments", "OPA4171AIDR", unit=n,
           ref_at=(x + 2.54, y - 6.35), value_at=(x, y + 5.08), hide_value=True)
    fb, a, o = x - 10.16, x + 10.16, x + 21.59         # feedback node, amplifier output, terminal side of Rs
    yc, yf = y + 10.16, y + 17.78                       # Cf and Rf rows
    s.wire(x - 7.62, y + 2.54, fb, y + 2.54); s.wire(fb, y + 2.54, fb, yf)
    s.wire(x + 7.62, y, x + 11.43, y)
    hpart(s, "Device:R", f"R{99 + n}", "47R", x + 15.24, y, "", "", FP["R"])
    s.wire(x + 19.05, y, x + 43.18, y)
    s.llabel(f"AO{n}", x + 43.18, y, 0)
    s.wire(a, y, a, yc)
    hpart(s, "Device:C", f"C{95 + n}", "1nF 50V C0G", x + 6.35, yc, "", "", FP["C"])
    s.wire(fb, yc, x + 2.54, yc)
    s.wire(o, y, o, yf)
    hpart(s, "Device:R", f"R{95 + n}", "15k 0.1%", x + 6.35, yf, "", "", FP["R"])
    s.wire(fb, yf, x + 2.54, yf); s.wire(x + 10.16, yf, o, yf)
    s.R(f"R{91 + n}", "10k 0.1%", fb, yf + 3.81, "", "GND_RACK")
    for jx, jy in ((fb, yc), (fb, yf), (a, y), (o, y)):
        s.junction(jx, jy)
    # clamp under the output line: common pin up to it, +12V left, GND_RACK right
    s.part("Diode:BAT54S", f"D{89 + n}", "BAT54S", x + 35.56, y + 5.08, {"1": "GND_RACK", "2": "+12V", "3": ""},
           180, FP["SOT23"], "Nexperia", "BAT54S,215", ref_at=(x + 35.56, y + 8.89), value_at=(x + 35.56, y + 11.43))
    s.junction(x + 35.56, y)


def analog_out(s):
    """Bottom band of the (A2) sheet, below the A3-sized original."""
    s.text("ANALOG OUT: four 0-10 V outputs, 10 mA each, in the RACK domain: powered from rack +12V, 0 V = GND_RACK\n"
           "(the relay 0 V; all outputs share it). I2C1 from the stack bus crosses through U90 (ISO1540, 2500 Vrms,\n"
           "the core's 4.7k pull-ups on side 1; its side-1 low is up to 0.8 V, so no other ISO15xx side 1 on the bus).\n"
           "U92 MCP4728 at 0x60 (address bits 000), internal 2.048 V reference x 2 = 4.096 V, ~LDAC low: outputs\n"
           "update on each write. U93 OPA4171 (36 V, rail-to-rail out, +25 mA short-circuit limit, continuous to\n"
           "GND for one channel) x (1 + 15k/10k) = 2.5: 10.24 V full scale. Feedback from the terminal side of the\n"
           "47R (no load error); the 1 nF from the amplifier output keeps it stable into cable capacitance.\n"
           "BAT54S clamps to +12V / GND_RACK: ESD only. Needs rack +12 V >= 11 V for 10 V at 10 mA.",
           25.4, 299.72)
    s.part("Isolator:ISO1540", "U90", "ISO1540", 50.8, 345.44,
           {"1": "+3V3", "2": "SDA", "3": "SCL", "4": "GND",
            "8": "V5_AO", "7": "AO_SDA", "6": "AO_SCL", "5": "GND_RACK"}, 0,
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Texas Instruments", "ISO1540DR",
           ref_at=(50.8, 337.82), value_at=(50.8, 353.06))
    s.R("R90", "4.7k", 76.2, 345.44, "V5_AO", "AO_SDA")
    s.R("R91", "4.7k", 88.9, 345.44, "V5_AO", "AO_SCL")
    s.C("C90", "100nF 50V X7R", 33.02, 365.76, "+3V3", "GND", decouple=True)
    s.C("C91", "100nF 50V X7R", 63.5, 365.76, "V5_AO", "GND_RACK", decouple=True)
    s.part("Regulator_Linear:MC78L05_SOT89", "U91", "MC78L05", 50.8, 388.62,
           {"3": "+12V", "1": "V5_AO", "2": "GND_RACK"}, 0, "Package_TO_SOT_SMD:SOT-89-3",
           "onsemi", "MC78L05ACHT1G", ref_at=(50.8, 383.54), value_at=(53.34, 394.97), value_justify="left")
    s.C("C92", "100nF 50V X7R", 33.02, 391.16, "+12V", "GND_RACK", decouple=True)
    s.C("C93", "10uF 25V X7R", 66.04, 391.16, "V5_AO", "GND_RACK")
    s.part("Analog_DAC:MCP4728", "U92", "MCP4728", 129.54, 350.52,
           {"1": "V5_AO", "2": "AO_SCL", "3": "AO_SDA", "4": "GND_RACK", "5": "~",
            "6": "DAC1", "7": "DAC2", "8": "DAC3", "9": "DAC4", "10": "GND_RACK"}, 0,
           "Package_SO:MSOP-10_3x3mm_P0.5mm", "Microchip", "MCP4728-E/UN",
           ref_at=(132.08, 340.36), value_at=(132.08, 364.49), value_justify="left")
    s.C("C94", "100nF 50V X7R", 104.14, 375.92, "V5_AO", "GND_RACK", decouple=True)
    amp = "Amplifier_Operational:LM2902"
    so14 = "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm"
    s.part(amp, "U93", "OPA4171", 129.54, 391.16, {"4": "+12V", "11": "GND_RACK"}, 0, so14,
           "Texas Instruments", "OPA4171AIDR", unit=5, ref_at=(132.08, 389.89), value_at=(132.08, 392.43),
           value_justify="left")
    s.C("C95", "100nF 50V X7R", 152.4, 391.16, "+12V", "GND_RACK", decouple=True)
    for n, pins in enumerate((("3", "2", "1"), ("5", "6", "7"), ("10", "9", "8"), ("12", "13", "14")), 1):
        ao_channel(s, n, pins, 203.2 + 76.2 * ((n - 1) % 2), 322.58 + 40.64 * ((n - 1) // 2))
    conn = {}
    for n in range(1, 5):
        conn[str(2 * n - 1)] = f"AO{n}"
        conn[str(2 * n)] = "GND_RACK"
    s.part("Connector:Screw_Terminal_01x08", "J50", "ANALOG OUT", 360.68, 365.76, conn, 0, FP_MC.format(n=8),
           "Phoenix Contact", "1844278", ref_at=(360.68, 350.52), value_at=(360.68, 381.0))
    s.text("J50 (MC 1,5/8-G-3,5, plug FMC 1,5/8-ST-3,5):\n1/2 AO1 / 0 V, 3/4 AO2 / 0 V,\n"
           "5/6 AO3 / 0 V, 7/8 AO4 / 0 V (0 V = GND_RACK).", 340.36, 388.62, 1.0)


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
    s = schgen.Sheet("io-card", "IO card: relays, GPIO, differential AI, analog out", "A", power=POWER, mpn=MPN)
    relays(s)
    analog(s, gpio(s))
    analog_out(s)
    stack(s)
    return s


def main():
    # A2: the A3-sized original plus the analog-out band below it
    (HW / "io-card.kicad_sch").write_text(build().render().replace('(paper "A3")', '(paper "A2")'))
    print("wrote io-card.kicad_sch")


if __name__ == "__main__":
    main()
