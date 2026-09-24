# Customer-supplied V-cut frame — 2026-09-23

The saved [MARV-V2-panel.kicad_pcb](../MARV-V2-panel.kicad_pcb) is a
**72 × 72 mm, one-board manufacturing frame** for Standard assembly. The board
is held by **four full-span V-scores, one along each straight edge**. Only the
rounded corners and the USB-C/microSD overhangs are routed. There are no side
slots, no mouse-bite holes, and no added panel silkscreen. The original MARV-V2
circuit board and schematic are unchanged.

[![Panel preview](../images/pcb/marv-v2-panel.png)](../images/pcb/marv-v2-panel.png)

KiCad's 3D render does not model V-score grooves. See the
[mechanical cut drawing](../images/pcb/marv-v2-panel-vcuts.svg) for their locations.
The four `V-CUT` labels are fabrication annotations, not printed silkscreen.

## Upload this package

| JLCPCB step | File |
| --- | --- |
| PCB fabrication | [production/MARV-V2-panel.zip](../production/MARV-V2-panel.zip) |
| Assembly parts | [production/bom.csv](../production/bom.csv) |
| Assembly placement | [production/positions.csv](../production/positions.csv) |

Select **Standard**, **Top Side**, **Edge Rails/Fiducials: Added by Customer**.
The panel contains one circuit design and one finished board. Keep the intended
quantity of 5 boards/frames manufactured, 2 assembled. BOM and position CSVs are
byte-for-byte unchanged; component coordinates and origin are unchanged.
Tooling holes and fiducials are excluded from both assembly CSVs.

Re-upload the ZIP: this version replaces the earlier two-score/slot package.
Confirm JLC's CAM preview shows four straight V-scores and the routed corner
and connector pockets. The ZIP no longer includes the drill-map drawings
(reference only), whose overlapping legends cluttered JLC's viewer.

## Mechanical details

- Frame: 72 × 72 mm, centered at (100, 100) mm (JLC's V-cut / Standard
  assembly minimum is 70 × 70 mm).
- Original board body: 50.7 × 45.5 mm between Edge.Cuts centerlines.
- V-score centerlines: **x = 74.55 and 125.45 mm, y = 77.15 and 122.85 mm**,
  each spanning the full panel. Each is **0.10 mm outside** the original edge,
  so the finished board is 50.9 × 45.7 mm with a 0.10 mm lip on each side.
- The offset exists because the inner-plane pours stop 0.30 mm from the board
  edge; 0.10 mm puts the scores at JLC's 0.40 mm copper clearance without
  touching the copper.
- Routed pockets (2 mm cutter): one at each R2 corner, one under the microSD
  overhang (top) and one under the USB-C overhang (bottom). No other routing
  touches the board.
- Three 2 mm NPTH tooling holes remain. Three top-side fiducials sit at
  (69, 72), (131, 72) and (69, 128) mm, clear of all score lines.
- `User.1` contains only the four score lines and four `V-CUT` labels.
  Fabrication Toolkit merges this layer into the outline Gerber using its
  V-cut option.

Depanel by bending each rail along its score **away from the components**
(top and bottom rails especially, where the connectors overhang the pockets).

## Verification

- Copper-to-score clearance, all four copper layers (tracks, pads, copper
  graphics, filled zones): minimum **0.4005 mm** (V3V3_SYS pour, PWR layer)
  against JLC's 0.40 mm. Axis-aligned full-span scores make the bounding-box
  extreme the exact distance.
- Panel DRC: **0 errors, 0 unconnected items**, 100 warnings. Same categories
  as the source board except `silk_edge_clearance` drops from 6 to 2, only
  because the straight edges are now score lines, which DRC does not treat as
  board edges. Silk position is unchanged.
- Source file unchanged (SHA-256 matches the manifest). The panel keeps every
  source item verbatim except the four straight Edge.Cuts segments. No zones
  were modified or refilled.
- Versus the previous export: PTH/NPTH drills, B.Cu, both inner planes, both
  paste layers, back silk and back mask are identical apart from metadata.
  F.Cu, F.Mask and F.Silkscreen differ only by the three fiducial flashes, and
  the IPC netlist only by the three fiducial positions.
- The exported outline Gerber contains all four full-span score lines.

Evidence: `build/flush-panel-check/make_vcut4.py` (panel generator) and
`build/flush-panel-check/drc.json`. The previous state is backed up in
`build/flush-panel-check/previous-*`. Review JLC's assembly preview,
particularly sensor rotations and L20 polarity, as before.

## Future exports

Open **MARV-V2-panel.kicad_pro**. Use the installed Fabrication Toolkit with
**User.1 V-cuts enabled**, automatic component translations and DNP exclusion
on, and automatic zone refill off. These options are saved in
`fabrication-toolkit-options.json`. V-cut export must remain enabled so the
score lines reach the fabrication files; annotations are not on silkscreen.
The toolkit always adds `*-drl_map.gbr` drawings. Remove them from the ZIP
before uploading.

The panel is a saved manufacturing copy, not a live link. After a circuit-board
edit, synchronize the copy, recheck copper-to-score clearance and DRC, then
regenerate the package before ordering. Do not export the unpanelized source
board when selecting customer-supplied rails.
