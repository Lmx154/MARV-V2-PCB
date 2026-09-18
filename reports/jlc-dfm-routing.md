# MARV V2 — JLCPCB DFM and routing setup

Verified against published JLCPCB information on **2026-09-18**, using KiCad **10.0.6**.
Settings live in `MARV-V2.kicad_pro`, `MARV-V2.kicad_dru`, and the board setup.
The reusable source profile is `config/dfm/jlcpcb.json`, with custom rules in
`config/dfm/jlcpcb.kicad_dru`. Run `python3 tools/dfm.py --check` to detect drift
or `--apply` to restore those managed settings with backups. Keep owner rules
outside the marked block; rules after it may override the profile and need review.

**The constraints are installed; the existing board is not ready for fabrication.**
The saved PCB is behind the schematic and needs the owner's schematic-to-PCB
update before routing. No footprints, pads, nets, board edges, tracks or zones were
changed by this work. The only PCB-file edits are green solder-mask color metadata.

## Order configuration and cost

Use the existing **four copper layers, 1.6 mm FR-4, 1 oz outer / 0.5 oz inner
copper, green mask, ordinary tented through vias**. Keep the existing standard
7628-style stackup: 0.2104 mm prepreg between each outer layer and its adjacent
inner layer, 1.065 mm core, 0.0152 mm inner copper. The project's 0.035 mm outer
copper is nominal. JLC uses a different finished-copper thickness for impedance
modeling, so match its calculator to the actual order stackup. These are purchasing
choices as well as KiCad metadata: a Gerber upload does not place the order with
these settings automatically. [JLC stackup information](https://jlcpcb.com/help/article/multi-layer-pcb-standard-laminated-structures)

**ENIG is retained intentionally.** HASL has a lower bare-board price, but the
0.4 mm-pitch MCU and LGA sensors make planarity and bridging relevant. ENIG is the
recommended practical compromise for this already-selected component set, not a
claim that it is JLC's absolute cheapest finish. No heavy copper, microvias,
blind/buried vias, resin fill, copper capping, edge plating or custom stackup is
needed by these rules. [JLC HASL guidance](https://jlcpcb.com/blog/how-to-resolve-short-circuit-hasl)

Select **Economic PCBA, front-side population** where the quote permits it. Its
published limits include 0402 passives and 0.4 mm IC pitch; this board is at the
latter limit. Leave U24 DNP and fit the through-hole IO headers yourself if that
reduces assembly cost. Economic assembly does not require adding board fiducials
or tooling rails. Component selection, quantity, reflow compatibility and the
actual quote still determine eligibility and price; no order was submitted.
[JLC assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)

## Installed fabrication constraints

All dimensions below are **mm**, edge-to-edge unless identified otherwise. These
are the applied project limits, often deliberately more generous than JLC's
absolute process limit.

| Check | Applied value |
|---|---:|
| Track width minimum | 0.15 |
| Different-net copper clearance, including track/pad | 0.15 |
| Copper to routed outline | 0.30 |
| Via diameter / finished drill | 0.60 / 0.30 |
| Via and plated-pad annular ring | 0.15 radial |
| Drill to unrelated copper | 0.25; PTH pads 0.35 |
| Via hole to hole | 0.25 |
| Hole spacing involving drilled pads | 0.45 |
| NPTH round hole / NPTH slot minimum | 0.50 / 1.00 |
| Plated slot minimum | 0.50 |
| Drilled hole to SMD land, including same-net | 0.20 |
| Mask expansion / minimum web | 0.00 / 0.10 |
| Mask opening to neighboring copper | 0.09 |
| Silkscreen clearance / stroke / text height | 0.15 / 0.15 / 1.00 |

JLC's published multilayer trace/space floor is 0.09/0.09; SMD pad spacing is
0.15. The chosen 0.15 rules provide margin. The drill preset avoids its small-via
surcharge combinations. No universal maximum trace width is imposed: wide copper
is allowed when other clearances hold. [JLC fabrication capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)

Solder-mask openings expose solderable copper; **zero expansion does not put mask
on the pads**. Zero expansion and the 0.10 mm web were already present and are
retained. Pads keep their existing paste apertures; there is no blanket paste
shrink. Vias remain tented on both sides, with no fill or cap. Tenting is not a
substitute for filled/capped via-in-pad construction. Existing manufacturer-specific
pad or footprint overrides must be checked during the final mask/paste review.

New-zone defaults use 0.20 clearance, 0.20 minimum thickness, 0.25 thermal gap and
0.30 thermal spokes. They do not create or refill any zone. Review actual spoke
width, count, necks and return paths when the owner adds planes.

## Component spacing and limitations of DRC

There is no general trace-to-component-body clearance: a masked trace may pass
under many packages. Clearance to their **copper pads** is enforced electrically;
package-specific restrictions take precedence.

JLC's assembly spacing recommendations depend on package pairs. For example,
0402-to-0402 is 0.15, 0603-to-0603 is 0.18, SOT-to-SOT is 0.40, and QFN-to-chip is
1.00. These are component-boundary measurements, not courtyard measurements.
[JLC spacing table and measurement diagram](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)

KiCad checks **courtyard-to-courtyard** spacing. To avoid pretending these are exact
body measurements, this project uses explicit conservative targets:

| Pair includes | Required courtyard gap |
|---|---:|
| Ordinary packages | 0.18 |
| C19 or an inductor | 0.35 |
| Q1, U7 or U12 (SOT) | 0.40 |
| U24 (SOIC) | 0.50 |
| U20–U23 (QFN / LGA) | 1.00 |

The last applicable row takes precedence. LGA uses the QFN value as an engineering
proxy; JLC's table does not separately specify these exact sensors. Since a proper
courtyard already contains body/land margin, these targets are **stricter** than
component-edge requirements. A failure is a placement-review request, not proof
JLC cannot assemble it. Before moving tightly placed decouplers, compare actual
body/land spacing with the table and the IC layout recommendations. Do not shrink
courtyards merely to clear errors. New packages need review; this is a rule set
for MARV V2, not a universal JLC library. Missing courtyards produce warnings.
[KiCad custom-rule semantics](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom-design-rules)

Features still needing manual/CAM review include slots drawn as outline cutouts,
slot aspect ratio and cutter radius, narrow same-net gaps, copper slivers, filled
silkscreen shapes, stencil apertures and assembly rotations. A global same-net
physical-clearance rule is not used because intended trace junctions and pad
connections must remain possible. The board is configured for routed edges;
V-scored panel edges need separate review. DRC also cannot establish temperature,
load transients, impedance, or solder-joint yield.

## Three ordinary widths, one USB pair

Use **netclass width** in the router. Nets select their default automatically.
The width menu contains only **0.20, 0.50 and 1.00**; the differential-pair menu has
one **0.30 width / 0.20 gap** entry. All use **0.60 / 0.30 vias**. The zero entries
in the project preset arrays are KiCad's netclass/default selectors, not zero-width
copper. A deliberate 0.15 custom width remains legal for difficult short escapes.

| Netclass | Width | Nets / use |
|---|---:|---|
| Default | 0.20 | SPI, I2C, UART, SD, QSPI, PWM, SWD, crystal, ADC sense, enables, boot, U7_BST |
| LocalPower | 0.50 | USB_VBUS, V3V3_ANA, DVDD, VREG_LX, VREG_AVDD, GND |
| Power | 1.00 | 5V_IN, V5_SYS, V3V3_SYS, U7_SW |
| USB | 0.30, gap 0.20 | USB_DP/DM and their RP/MCU-side names |

PWM does not need a special thick class. VBAT is sense-only and does not need a
power width. U7_BST is a local bootstrap connection, not a supply trunk. Ground's
0.50 default is for short connections; use the intended ground plane for returns.

**Widths are routing defaults, not mandatory minimum widths on every branch.**
A 1.00 mm trunk must neck down at small pads. Use 0.20 near MCU/sensor pins and
0.50 at regulator and diode lands, widening promptly. Keep necks short and inspect
the complete load path. A small decoupler branch does not carry the whole rail
current. Avoid widening immediately beside adjacent fine-pitch pads.

Measured minimum pad dimensions from the saved board:

| Component group | Narrow pad dimension | Practical entry |
|---|---:|---|
| U20 RP2354B | 0.20 | 0.20 |
| U21 ICM-45686 | 0.35 | 0.20 |
| U22 BMP581 | 0.30 | 0.20 |
| U23 ADXL375 | 0.25 | 0.20 |
| J4 USB signal pins | 0.30 | 0.30, or short 0.20 escape |
| U7 / U12 / Q1 | 0.60 | 0.50 |
| D1 | 0.45 | 0.20 neck or carefully oriented 0.50 entry |
| L20 | 0.55 | 0.50 |

The chosen signal width fits the tightest lands and avoids extra bus-specific
presets. It is not a datasheet-mandated or universally impedance-optimal width.
J11 in the saved board is still the old 104031 socket; these settings do not
substitute for transferring the new 47219 footprint from the schematic.

## Power budget and width rationale

Owner clarification: **no servos, motors or actuators are powered through the FC**.
Possible loads are four ToF sensors, several lidar modules, GPS and ELRS.
The existing 5 V pad connections remain as drawn. External electronics use the
system rail, not the quiet onboard sensor rail. Check each module's input voltage
and simultaneous peak current once the exact models are selected.

The 2 A AP63203 rating is an upper device rating, not spare current guaranteed at
the headers. MCU, storage and modules share it. The input-only simulation's 0.5 A
V5_SYS assumption is also not a measured load budget. D1 is a 1 A-class part, so
USB input must not be treated as a 2 A source; available host current and diode
heating require their own check.

For a first-pass comparison, with 35 µm outer copper, a 50 mm straight trace and
copper resistivity 1.724e-8 ohm·m at 20 °C:

| Width | Resistance | Example drop |
|---|---:|---:|
| 0.20 | 123 mΩ | 12 mV at 0.10 A |
| 0.50 | 49 mΩ | 49 mV at 1 A |
| 1.00 | 25 mΩ | 49 mV at 2 A |

These calculations exclude pads, vias, connections and the ground return. At the
published minus-20% width tolerance, resistance increases by 25%. A legacy
IPC-2221 outer-trace estimate at 10 °C rise gives about 1.45 A for 0.50 mm and
2.39 A for 1.00 mm (about 2.03 A after that width reduction). This supports the
presets as starting points, not a thermal qualification. Do not apply the outer
trace estimate to the thinner inner copper or to bottlenecks in zones.
[JLC explanation of the estimation method](https://jlcpcb.com/blog/pcb-trace-width-guide)

Use broad copper where available for shared supply paths. Review parallel vias
for substantial rail current; one generic via is not automatically rated for the
whole 2 A rail. No thermal vias or plane stitching were added.

## Datasheet findings that matter while routing

- **RP2354B:** the core regulator is the critical layout. Follow section 6.3.8 and
  its switching-current loop drawing; keep L20 and its input/output capacitors on
  the same side, minimize VREG_LX copper, maintain the specified ground returns,
  and avoid copper immediately below L20/LX on the adjacent layer. VREG_AVDD is
  noise-sensitive. The 0.50 preset cannot enforce this topology.
  [Local RP2350 datasheet](../datasheets/RP2350.pdf)
- **USB:** RP2350 is full speed, 12 Mbps; Raspberry Pi still recommends a 90 Ω
  differential path and an uninterrupted ground reference. Keep the existing
  series resistors. The 0.30/0.20 pair is a starting geometry for the saved
  four-layer stackup, **not verified controlled impedance**. Confirm it with
  JLC's calculator using the actual stackup, finished copper and mask before
  committing the USB route. Keep connector-to-resistor and resistor-to-MCU paths
  balanced; do not assume KiCad combines their separate nets for skew checks.
  [Raspberry Pi hardware design guide, USB section](https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf)
- **AP63203:** use compact input/switch/output loops and short capacitor returns.
  Its layout section recommends 2 oz copper for a 2 A application. Keeping the
  lower-cost 1 oz process therefore requires checking temperature at the actual
  load; full 2 A continuous operation has not been demonstrated on this board.
  Use 1.00 mm/shared copper where it fits and short 0.50 mm pin entries.
  [AP63203 layout section](../datasheets/AP63203.pdf)
- **TPS7A2033:** a 300 mA sensor LDO, with close input/output capacitors and copper
  area for heat spreading. The 0.50 default is ample for its intended local
  branches; thermal dissipation still depends on voltage drop and actual load.
  [TPS7A20 section 7.4](../datasheets/TPS7A2033.pdf)
- **ICM-45686 / ADXL375 / BMP581:** ordinary 0.20 mm signal traces suffice for
  routing geometry. ICM SPI supports up to 24 MHz and ADXL SPI up to 5 MHz; short
  paths, decoupling and quiet returns matter more than making signal copper wide.
  Keep the separate SPI buses and interrupt nets from the current schematic.
  [ICM](../datasheets/ICM-45686.pdf), [ADXL](../datasheets/ADXL375.pdf)
- **BMP581 exception:** Bosch asks for 0.20 mm pad spacing, no traces/vias beneath
  the sensor, and no mask under the sensor body with 20 µm horizontal mask
  clearance. Its pad-spacing rule is installed, but its existing footprint has
  ordinary separate mask openings: **the under-body mask and keepout arrangement
  still needs a footprint review**. Do not apply global mask shrinking as a fix.
  This can affect sensor performance even when generic fab DRC passes.
  [BMP581 section 8.2](../datasheets/BMP581.pdf)
- **SD / optional QSPI:** 0.20 mm is a common pad-compatible starting point, not a
  speed guarantee. Keep clock/data over a continuous reference and avoid stubs.
  Place SD clock R58 as required by the current schematic. Socket mechanics do
  not define the card's timing budget; select clock rates after the actual path
  is known. W25Q32JV and APS6404L have different command/frequency limits and
  loads; populating U24 later requires timing review.
  [Winbond](../datasheets/W25Q32JV.pdf), [AP Memory](../datasheets/APS6404L.pdf),
  [new Molex socket](../datasheets/472192001-drawing.pdf)
- **Crystal / GPIO / LED / switches / sense dividers:** use the same 0.20 width.
  Keep crystal and high-impedance analog paths short and away from switch nodes;
  width does not replace capacitance/noise review.

## Validation and next routing steps

Run `python3 tools/dfm.py --drc` for a fresh read-only check in
`build/dfm/drc.json`. The counts below are the 2026-09-18 baseline; the full
snapshot is recoverable from commit `01a357c`. The original board
had 5 reported layout violations, 302 unconnected items and 185 schematic-parity
issues. With the installed checks it has:

| Result | Count |
|---|---:|
| Layout errors | 182 |
| Layout warnings | 206 |
| Unconnected items | 302 |
| Schematic-parity issues | 185 |

The 388 layout findings comprise 131 text-size/stroke errors, 51 conservative
courtyard-gap errors, 119 graphic-stroke warnings, 80 MCU-pad-size review warnings,
2 silk overlaps and 5 silk/edge warnings. The 80 MCU lands are below JLC's generic
0.25 mm minimum SMD-pad dimension; their manufacturer footprint and the supported
0.4 mm assembly pitch need a package-specific CAM check. **Do not enlarge the
MCU pads to make this warning disappear.**

Parity includes two missing footprints, one extra footprint, 61 net conflicts,
32 footprint/symbol mismatches and 89 field mismatches. Resolve these through
KiCad's schematic-to-PCB update before routing; the report preserves the item
references. No exclusions were added to hide errors.

A disposable synthetic board additionally verified detection of undersized vias,
annular rings, microvias, via-in-pad, drilled-pad spacing, PTH-to-copper clearance,
undersized NPTH holes and narrow tracks. This caught a condition unsupported by
the installed KiCad build, which was replaced before the final audit. Geometry
preservation was verified byte-for-byte against the board at the start of this
session after removing only the two added color entries.

Close/reopen the PCB project so an already-open editor cannot overwrite the saved
settings. In **Board Setup → Design Rules**, inspect Constraints, Net Classes,
Pre-defined Sizes and Custom Rules. Route with netclass widths and DRC avoidance
active. The owner should then update the PCB from the schematic, resolve the
reported footprint/spacing/mask issues, route, fill zones, and run DRC again.
Inspect final Gerber copper/mask/paste/drills and JLC's assembly/CAM preview before
ordering. Installed rules substantially improve coverage, but do not certify an
unfinished PCB or replace JLC's final review.

---

Original MARV V2 documentation: [CC0 1.0](../LICENSES/CC0-1.0.txt). No attribution required; provided as-is. [Licensing and third-party exceptions](../LICENSE.md).
