# can-ssr stack-interface rework (2026-10-06)

One-off scripts that converted the rev A layout to the can-controller stack
interface (docs/requirements.md 4.4). Kept as a record; they match the
geometry of the board before the rework and must not be rerun.

1. `stack_bottom.py PCB LIBDIR`: M4 holes, load bolts inward with bars, pours,
   return bar, keep-outs and labels.
2. `rework_tr.py PCB LIBDIR`: standoff holes at 4.5 mm inset, top-right corner
   (LED column, R50/C44) and local reroutes.
3. `rework_can.py PCB LIBDIR TOOLSDIR`: J1/J2 -> one MCDN double-level header,
   SW1/D2 moves, conflict rip-up and net rejoining.
4. `prune_dangling.py PCB DRC_JSON x0 y0 x1 y1`: delete what KiCad DRC reports
   as dangling inside a window; repeated until nothing is left.

Router: `tools/miniroute.py`.
