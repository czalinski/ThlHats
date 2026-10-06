"""Delete the items KiCad's DRC reports as dangling inside a window.
prune_dangling.py PCB DRC_JSON x0 y0 x1 y1 -> prints how many were deleted"""
import json
import sys

import pcbnew

pcb, rep = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
d = json.load(open(rep))
uu = []
for v in d["violations"]:
    if v["type"] in ("track_dangling", "via_dangling"):
        for it in v["items"]:
            x, y = it["pos"]["x"] - 100, it["pos"]["y"] - 100
            if x0 <= x <= x1 and y0 <= y <= y1:
                uu.append(it["uuid"])
b = pcbnew.LoadBoard(pcb)
n = 0
for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in uu:
        b.Delete(t)
        n += 1
if n:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(pcb)
print(n)
