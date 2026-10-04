"""House design rules for every board in this repo.

Targets low-cost 2-layer prototype fabs (JLCPCB / PCBWay / OSH Park standard
service). Values are deliberately a little conservative relative to the fab
minimums so boards are cheap and robust. Used by new_board.py (to seed the
project) and check_board.py (to verify it).
"""

MAX_W = 100.0  # mm
MAX_H = 100.0  # mm
COPPER_LAYERS = 2

# Raspberry Pi mounting pattern (M2.5, 2.7 mm hole), relative to the first hole.
RPI_HOLE_SPACING = (58.0, 49.0)
RPI_HOLE_DRILL = 2.7

# kicad_pro board.design_settings.rules (mm)
RULES = {
    "min_clearance": 0.15,
    "min_track_width": 0.15,
    "min_connection": 0.15,
    "min_via_annular_width": 0.13,
    "min_via_diameter": 0.55,
    "min_through_hole_diameter": 0.3,
    "min_hole_to_hole": 0.5,
    "min_hole_clearance": 0.25,
    "min_copper_edge_clearance": 0.3,
    "min_silk_clearance": 0.0,
    "min_text_height": 0.8,
    "min_text_thickness": 0.15,
    "allow_blind_buried_vias": False,
    "allow_microvias": False,
}

TRACK_WIDTHS = [0.2, 0.25, 0.3, 0.4, 0.5, 0.8, 1.0]
VIAS = [(0.6, 0.3), (0.8, 0.4), (1.0, 0.5)]  # (diameter, drill)

NETCLASSES = [
    {"name": "Default", "clearance": 0.2, "track_width": 0.25,
     "via_diameter": 0.6, "via_drill": 0.3, "priority": 2147483647},
    {"name": "Power", "clearance": 0.2, "track_width": 0.5,
     "via_diameter": 0.8, "via_drill": 0.4, "priority": 0},
]
NETCLASS_PATTERNS = [
    ("Power", "GND"),
    ("Power", "+*"),
    ("Power", "VBUS*"),
    ("Power", "VIN*"),
]
