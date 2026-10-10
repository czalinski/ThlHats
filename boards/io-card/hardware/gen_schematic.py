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
