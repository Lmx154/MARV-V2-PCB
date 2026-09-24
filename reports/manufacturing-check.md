# Manufacturing export verification — 2026-09-23

This records the original, unpanelized export. The later
[customer-supplied assembly frame](manufacturing-panel.md) supersedes its ZIP
and order handoff; source-design checks below remain applicable.

The local `production/` package was regenerated from the saved design with
KiCad 10.0.6 and the installed Fabrication Toolkit. All three files are current:

| Upload | File |
| --- | --- |
| PCB fabrication | [archived MARV-V2.zip](../build/panel-check/unpanelized-MARV-V2.zip) |
| Assembly BOM | [bom.csv](../production/bom.csv) |
| Assembly placements | [positions.csv](../production/positions.csv) |

The BOM and placement files are byte-for-byte identical to the previous
package. All 15 archive members also match after removing creation timestamps.
The ZIP passes its integrity check and contains four copper layers, front/back
mask, silk and paste, Edge.Cuts, and separate PTH/NPTH drills and drill maps.
The old outputs were preserved under `build/manufacturing-check/previous-production-*`.
Use the three `production/` upload files together; older `build/fab/` and
`build/assembly/` outputs remain superseded.

## Verification

| Check | Result |
| --- | --- |
| ERC, all severities | 0 violations |
| DRC, all severities and schematic parity | 0 errors, 104 warnings, 0 unconnected, 0 parity issues |
| Power/GPIO netlist check | Pass: 193 critical pin mappings, all 48 GPIO assignments |
| Footprint/library audit | 108 of 108 components pass |
| Assembly reference sets | PCB selection, BOM and positions agree; no duplicate placement references |
| Part selection | Every exported LCSC number matches both PCB and schematic |
| Assembly totals | 88 top-side placements, 34 distinct LCSC parts, 84 BOM rows |
| Geometry | 50.8 × 45.6 mm, four copper layers, 1.6 mm board |
| Vias | 179 through vias, all 0.60 mm diameter / 0.30 mm drill |
| Design preservation | All 39 captured design/library/settings file hashes unchanged |

The saved zones were exported without refill. No routing, placement, copper,
schematics, exclusions or rule severities were changed. Automatic component
translations and DNP exclusion were enabled, matching the saved export options;
extra layers, V-cuts, alternate outlines and all-active-layer export were disabled.

Detailed results are in `build/manufacturing-check/`: `erc.json`, `drc.json`,
`netlist.xml`, `footprint-audit.md`, `export-verification.json` and
`source-sha256.json`. Local `production/order-manifest.json` records hashes and
verification results; `production/SHA256SUMS` covers the three upload files.
These generated directories remain Git-ignored as documented in the README.

## Findings retained for review

| DRC warning | Count | Scope |
| --- | ---: | --- |
| Small SMD land review | 80 | U20 MCU lands trigger the generic 0.25 mm minimum-pad review rule; retain the package footprint and review CAM/assembly acceptance |
| Silkscreen graphic stroke | 8 | Graphic strokes below the project's 0.15 mm review threshold |
| Silkscreen overlap/clearance | 7 | Labels and graphic/footprint silk |
| Silkscreen near board edge | 6 | G2 graphic and J10 header outline; may be clipped in fabrication |
| Missing courtyard | 3 | Graphic footprints G1, G2 and G3 |

These are warning-level findings, not a warning-free signoff. The project also
retains five ignored check types: footprint filter mismatch, footprint type
mismatch, library footprint mismatch, track not centered on via, and tuning
profile track geometries. There are no individual excluded DRC markers.

`tools/dfm.py --check` reports project-setting drift. Comparing the parsed
settings shows only an additional **0.30 mm track-width preset** in the saved
project; applying the profile would remove it. Fabrication constraints are
unchanged. The owner's preset was preserved, and the profile was not applied.

## Order handoff

Keep the choices already specified in [README Ordering](../README.md#ordering):
5 PCBs, 2 assembled on the top side, 1 design, Single PCB, four layers, 1.6 mm,
green mask, white silk, HASL with lead, standard copper and 0.30 mm minimum via
holes. J6–J8/J10 remain owner-soldered, and U24 remains DNP.

Before paying, inspect the rendered board and assembly previews, especially
custom sensor rotations and L20's orientation dot toward pad 2 / DVDD. Confirm
the physical ESC pad pitch, current parts availability and quote, and CAM
acceptance of the fine-pitch lands with the selected finish. This local check
did not submit files to JLCPCB or validate its preview or inventory.

This report supersedes older reports' manufacturing-readiness counts for this
saved design. Re-run checks and regenerate the package after any design edit.
