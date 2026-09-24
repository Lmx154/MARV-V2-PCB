# MARV V2 standard fabrication cost audit

Historical audit of the 2026-09-21 layout. The error counts below are retained
as history; see the [2026-09-23 manufacturing check](manufacturing-check.md) for
the current saved design and order files.

Reviewed 2026-09-21. The owner wants the budget spent on components rather than
precision PCB fabrication. The selected dimensions use ordinary four-layer
technology, but the current saved layout still has clearance violations and is
not ready for fabrication. The initial audit did not alter geometry. At the
owner's subsequent request, 511 existing signal segments were resized to
0.15 mm; their paths and every non-width PCB field were preserved.

## Keep these fabrication choices

| Feature | Required choice / saved state |
| --- | --- |
| Construction | Four-layer, 1.6 mm FR-4, existing standard 7628-style stackup |
| Copper | 1 oz outer, 0.5 oz inner; no heavy copper |
| Signals | 0.15 mm width, 0.15 mm minimum copper clearance |
| Vias | 0.60 mm diameter / 0.30 mm drill, ordinary through vias only |
| Via treatment | Ordinary mask treatment; no epoxy/resin fill or copper cap |
| Finish and mask | HASL with lead, green solder mask, as already selected |
| Special features | No requested blind/buried/microvias, backdrilling, gold fingers, edge plating, castellations or custom controlled-depth milling |
| Assembly | Front-side assembly; confirm Economic PCBA eligibility and actual component charges in the quote |

JLC explicitly describes 3.5 mil trace/space on four/six layers as available
without extra cost. Our 0.15 mm is about 5.9 mil, comfortably coarser.
[JLC standard routing guidance](https://jlcpcb.com/blog/complete-pcb-layout-guide)
Its copper table identifies 3 mil as an extra-cost option; this project does not
use it. [JLC copper and minimum feature table](https://jlcpcb.com/help/article/jlcpcb-copper-weight)

JLC's quote help identifies holes at least 0.30 mm with diameters at least
0.40 mm as having no small-via surcharge. This board uses 0.30/0.60, retaining
the owner's chosen 0.15 mm radial ring. Do not select the smaller-hole option
in the cart, even where another published combination is described as free:
the owner's previous quote added fees when selecting 0.20 mm holes.
[JLC quote help](https://cart.jlcpcb.com/quote/?fromDemo=yes)

The order form, rather than KiCad, selects resin filling, inspection/test options,
delivery speed and other chargeable services. Ordinary solder-mask plugging is
not the same process as resin-filled, copper-capped via-in-pad. The saved board
has tenting enabled and filling/capping disabled. Match the standard via
mask treatment to the actual order without requesting a paid fill/cap process.

## Saved geometry checks

- **172 vias:** all through vias, all 0.60/0.30 mm.
- **1,007 track segments after conversion:** 511 at 0.15 mm, 226 at 0.20 mm,
  28 at 0.30 mm, 226 at 0.50 mm, and 16 at 1.00 mm.
- Smallest drilled pad hole: **0.30 mm**, in the mounting-hole footprints.
  No pad uses a smaller drill hidden inside a footprint.
- USB plated slots: **0.60 mm wide**, with lengths 1.20/1.70 mm. These are
  ordinary through slots, above the project's 0.50 mm plated-slot minimum.
- USB nonplated locating holes: **0.65 mm**. Header holes are 1.00 mm;
  the four main mounting holes are 4.00 mm.
- Managed settings check passes. After the requested track conversion, every
  PCB field except the 511 selected widths is unchanged. Schematics and custom
  rules are unchanged.

## Existing problems that must be resolved before ordering

The initial read-only KiCad DRC returned **460 errors and 80 warnings**.
After the requested signal-track conversion it returned **451 errors and 80
warnings**, with zero unconnected items. Copper-clearance findings decreased
from 363 to 354; other category counts were unchanged. The table below records
the initial audit:

| Finding | Count |
| --- | ---: |
| Copper clearance | 363 |
| Hole clearance | 14 |
| Solder-mask bridges | 5 |
| Courtyard spacing | 78 |
| Small MCU land review warnings | 80 |

There were zero reported unconnected items. This run did not check schematic
parity, refill zones or save the board. Of the 363 copper-clearance reports,
239 involve existing filled zones; the owner should refill after layout edits
and recheck. The other 124 reports involve non-zone copper. Counts can repeat
the same physical conflict on multiple layers and are not unique defect counts.

One concrete example is the `BARO_SCL` via at (104.991623, 101.770024) and
`ICM_MISO` via at (104.474729, 102.074694): their reported copper separation is
approximately **0.000002 mm**, effectively touching relative to manufacturing
tolerances. Reducing signal-track width cannot fix this via-to-via gap. The
owner must resolve such conflicts using ordinary clearances, rather than
specifying a precision fabrication process. Existing tracks and placements
were preserved as required by AGENTS.md.

The 80 MCU warnings concern the generic minimum-pad review rule versus the
RP2354B footprint's 0.20 mm-wide lands. Do not enlarge or replace those lands
merely to silence warnings. The existing 0.4 mm-pitch package and LGA sensors
still require assembly/CAM acceptance with the selected HASL finish. A fine-pitch
component does not by itself establish a PCB precision surcharge, nor does a
basic PCB process guarantee the cheapest assembly option.

The initial report is `build/dfm/fabrication-cost-audit-drc.json`; the report
after conversion is `build/dfm/signal-widths-applied-drc.json`. Zones were not
refilled in either run.

## What is not guaranteed by this audit

No Gerbers were submitted and no current order-specific quote was obtained.
Standard dimensions avoid the identified small-trace/small-drill triggers;
they cannot guarantee the total bill or acceptance of the present layout.
Confirm the final CAM files and itemized quote after routing cleanup.

There is also a cost condition independent of geometry: JLC's quote help says
that selecting its **Aerospace** product category for a four-layer board requires
FR4 Tg155 and a four-wire Kelvin test. Because this design is a rocket/drone
controller, confirm the applicable classification with JLC at ordering time;
do not assume that all such fees would be caused by a small drill. No category
was selected or changed by this audit.
[JLC product-type requirements](https://cart.jlcpcb.com/quote/?fromDemo=yes)
