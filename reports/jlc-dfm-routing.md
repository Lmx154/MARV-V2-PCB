# MARV V2 — JLCPCB DFM and routing setup

Capability figures were verified against published JLCPCB information on
**2026-09-18**; checks are run with KiCad **10.0.7**. The constraints live in
`MARV-V2.kicad_pro`, `MARV-V2.kicad_dru` and the board setup (the panel copy
`MARV-V2-panel.kicad_pro` / `.kicad_dru` carries the same rules); the saved project
settings are authoritative. The rules are tuned for JLCPCB's ordinary four-layer
process, with no paid options.

## Manufacturing precheck

The board's features fit JLCPCB's nominal capabilities. **The BOM requires Standard
PCBA.**

| Item | Saved board |
| --- | --- |
| Board body | 50.7 × 45.5 mm between Edge.Cuts centerlines |
| Construction | Four layers, nominal 1.6 mm FR-4, green mask, ENIG; 0.035 mm outer / 0.0152 mm inner copper in stackup |
| Tracks | 867 segments; minimum width 0.10 mm (Signal netclass) |
| Routing vias | 200: 151 at 0.60 mm copper / 0.30 mm drill, 47 at 0.45 / 0.30 (Signal netclass), 2 at 0.80 / 0.40 (Power netclass) |
| Assembly | 90 top-side placements and nothing on the bottom, 34 distinct LCSC parts; the J17 converter line has no LCSC number and is hand-fitted |
| Packages | 0402 passives; U20 QFN-80 at 0.4 mm pitch, narrowest land dimension 0.20 mm |
| Mask | Global pad expansion zero, minimum mask width 0.10 mm, vias tented both sides |

JLC's nominal capabilities permit these feature sizes. Copper setbacks differ for
routed edges (0.20 mm) and V-scores (0.40 mm); the panel's measured copper-to-score
distance is in [manufacturing-panel.md](manufacturing-panel.md). [PCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities/)

Standard PCBA lists 0.35 mm minimum IC pitch, a 70 × 70 mm minimum assembly envelope,
rails and fiducials, and V-cut support. The 72 × 72 mm frame has three tooling holes
and three fiducials. [Assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)

### Standard assembly is required by the selected sensors

- [BMP581 / C5362283](https://jlcpcb.com/partdetail/BoschSensortec-BMP581/C5362283): **Standard only; X-ray required**.
- [RP2354B / C39843328](https://jlcpcb.com/partdetail/RaspberryPi-RP2354B/C39843328), [ICM-45686 / C22459454](https://jlcpcb.com/partdetail/TDKInvenSense-ICM45686/C22459454), and [L20 / C42411119](https://jlcpcb.com/partdetail/AbraconLlc-AOTA_B201610S3R3_101T/C42411119) are also catalogued for assembly.

Catalogue eligibility does not reserve stock; live quantities are confirmed at quote
time.

### Process choices

ENIG is used for QFN/LGA pad planarity; it is a recommendation, not a claim that
Standard PCBA universally prohibits HASL. [Finish guidance](https://jlcpcb.com/help/article/jlcpcb-surface-finish)

Vias are tented on both sides in the saved board. JLC's plugging guidance has a
separate 0.35 mm condition near mask openings, so the project's 0.20 mm hole-to-land
rule is not by itself proof of plugging compatibility; the published wording and
final mask geometry require CAM interpretation. Mask-ink plugging is not the same
as epoxy-filled/capped via-in-pad, which this board does not use. [Via covering](https://jlcpcb.com/help/article/pcb-via-covering)

The check sequence is: refilled KiCad DRC with schematic parity (actual clearances,
connections, courtyards, mask slivers, paste apertures); the panel scripts in
[tools/panel/README.md](../tools/panel/README.md) for score clearance and file-set
consistency; then JLC's CAM and assembly previews (pad 1, polarized parts, sensor
rotations, stencil apertures), finish, via covering, stock and quote.

## Order configuration and cost

Use the **four copper layers, 1.6 mm FR-4, 1 oz outer / 0.5 oz inner
copper, green mask, ordinary tented through vias**. The standard
7628-style stackup is 0.2104 mm prepreg between each outer layer and its adjacent
inner layer, 1.065 mm core, 0.0152 mm inner copper. The project's 0.035 mm outer
copper is nominal. JLC uses a different finished-copper thickness for impedance
modeling, so match its calculator to the actual order stackup. These are purchasing
choices as well as KiCad metadata: a Gerber upload does not place the order with
these settings automatically. [JLC stackup information](https://jlcpcb.com/help/article/multi-layer-pcb-standard-laminated-structures)

**Surface finish is ENIG.** HASL has a lower bare-board price, but the
0.4 mm-pitch MCU and LGA sensors make planarity and bridging relevant. ENIG is the
recommended practical compromise for this component set, not a
claim that it is JLC's absolute cheapest finish. No heavy copper, microvias,
blind/buried vias, resin fill, copper capping, edge plating or custom stackup is
needed by these rules. [JLC HASL guidance](https://jlcpcb.com/blog/how-to-resolve-short-circuit-hasl)

Assembly is **Standard, top side** (see above); U24 is DNP and the through-hole IO
headers are fitted by hand. Component selection, quantity, reflow compatibility and
the actual quote determine eligibility and price.
[JLC assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities)

## Installed fabrication constraints

All dimensions below are **mm**, edge-to-edge unless identified otherwise. These
are the applied project limits, often deliberately more generous than JLC's
absolute process limit.

| Check | Applied value |
|---|---:|
| Track width minimum | 0.15 (Signal netclass 0.10) |
| Different-net copper clearance, including track/pad | 0.15 (Signal netclass 0.10) |
| Copper to routed outline | 0.30 |
| Via diameter / finished drill | 0.60 / 0.30; Signal netclass 0.45 / 0.30 (JLC free tier "0.3mm/(0.4/0.45mm)", recommended 0.15 mm ring) |
| Via annular ring / plated-pad annular ring | 0.15 (Signal netclass vias 0.075) / 0.15 radial |
| Drill to unrelated copper | 0.25 (JLC via minimum 0.20 plus margin); PTH pads 0.35 |
| Via hole to hole | 0.25 |
| Hole spacing involving drilled pads | 0.45 |
| NPTH round hole / NPTH slot minimum | 0.50 / 1.00 |
| Plated slot minimum | 0.50 |
| Drilled hole to SMD land, including same-net | 0.20 (J3 exempt) |
| Mask expansion / minimum web | 0.00 / 0.10 |
| Silkscreen graphic stroke minimum | 0.15 (warning) |

JLC's published multilayer trace/space floor is 0.09/0.09; SMD pad spacing is
0.15. The chosen rules (0.15 mm; Signal netclass 0.10 mm) stay above that floor. The via presets use JLC's free via tier: the order form prices by the
smallest hole, and selecting 0.2 mm added ~$38 of high-precision extras on a
2026-09-21 quote regardless of pad size, so 0.3 mm holes are the floor here. No universal maximum trace width is imposed: wide copper
is allowed when other clearances hold. [JLC fabrication capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)

One local exception: pad clearance on C39 and C45 is 0.12 mm so the RP2350
VREG_LX trace can pass between their pads, still above JLC's 0.09 mm floor.

Silkscreen on the board is normalised for JLC rather than in the source libraries:
silk text is 1.0 mm / 0.15 mm, 0402 passives and L2
carry no silk outline. The
resulting library-mismatch warnings are therefore expected.

Solder-mask openings expose solderable copper; **zero expansion does not put mask
on the pads**. Pads keep their existing paste apertures; there is no blanket paste
shrink. Vias are tented on both sides, with no fill or cap. Tenting is not a
substitute for filled/capped via-in-pad construction. Manufacturer-specific
pad or footprint overrides must be checked during the final mask/paste review.

## Component spacing and limitations of DRC

There is no general trace-to-component-body clearance: a masked trace may pass
under many packages. Clearance to their **copper pads** is enforced electrically;
package-specific restrictions take precedence.

JLC's assembly spacing recommendations depend on package pairs. For example,
0402-to-0402 is 0.18, 0603-to-0603 is 0.25, SOT-23 to SOT-23 is 0.40, and QFN-to-QFN is
1.00. These are component-boundary measurements, not courtyard measurements.
[JLC spacing table and measurement diagram](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)

KiCad checks **courtyard-to-courtyard** spacing. The KiCad courtyards already carry
0.21–0.41 mm (0402) or 0.25 mm (SOT/SOIC/QFN) of margin per part, so two
non-overlapping courtyards already exceed every chip/SOT/SOIC figure above. Only
IC-to-IC spacing needs extra courtyard gap:

| Pair includes | Required courtyard gap |
|---|---:|
| Ordinary packages, C19, Q1, U7, U12, U24 | 0 (courtyards must not overlap) |
| U20–U23 (QFN / LGA) against another IC (U*, Q*) | 0.50 (1.00 body-to-body less 2 × 0.25 margin) |

The RP2350 core-regulator parts must sit against the MCU, so chip passives and
inductors next to U20–U23 use the ordinary row. LGA uses the QFN value as an
engineering proxy; JLC's table does not separately specify these exact sensors.
A courtyard failure is a placement-review request, not proof
JLC cannot assemble it. Do not shrink courtyards merely to clear errors. New
packages need review; this is a rule set for MARV V2, not a universal JLC library.
Missing courtyards are ignored by the rule severities.
[KiCad custom-rule semantics](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom-design-rules)

Features needing manual/CAM review include slots drawn as outline cutouts,
slot aspect ratio and cutter radius, narrow same-net gaps, copper slivers, filled
silkscreen shapes, stencil apertures and assembly rotations. A global same-net
physical-clearance rule is not used because intended trace junctions and pad
connections must remain possible. The board is configured for routed edges;
V-scored panel edges are checked separately by the panel scripts. DRC also cannot
establish temperature, load transients, impedance, or solder-joint yield.

## Signal and power widths, one USB pair

Use **netclass width** in the router. Nets select their default automatically.
The width menu contains **0.10, 0.15, 0.20, 0.25, 0.30, 0.36 and 0.50**; the differential-pair menu has
one **0.36 width / 0.20 gap** entry. The via presets are **0.45 / 0.30** (Signal class) and
**0.60 / 0.30** (all other classes except Power, which uses 0.80 / 0.40). The zero entries
in the project preset arrays are KiCad's netclass/default selectors, not zero-width
copper. The Signal class sits above JLC's 0.09 / 0.09 multilayer floor.

| Netclass | Width | Nets / use |
|---|---:|---|
| Signal | 0.10, clearance 0.10 | Sensor buses (ICM_*, IMU2_*, BARO_*, MAG_*), SD, QSPI/flash, LED data, PWM*, ESC_TELEM*, GPS_*, ELRS_*, IO_GPIO*, SPARE_GPIO*, SWD, MCU_RUN, BOOT_BTN and USB CC |
| Default | 0.20 | Crystal, regulator control/bootstrap, indicator current and unclassified nets |
| Rail3V3 | 0.20 | V3V3_SYS |
| CoreDVDD | 0.20 | DVDD |
| Analog3V3 | 0.30 | V3V3_ANA |
| PWM_ESC | 0.25 | CURR_SENSE, CURR_SENSE_RAW |
| Power | 0.50, vias 0.80 / 0.40 | VBAT, 5V_IN, V5_SYS, USB_VBUS, U7_SW, U7_VO, U26_SW, U26_BST |
| USB | 0.36, gap 0.20, clearance 0.18 | USB_D+/D- and their MCU/RP-side names |

PWM does not need a special thick class. J3.7 VIN to J17.3 and the ground return
must support converter input current; the VBAT branch to the voltage divider
carries only sense current. U7_BST is
a local bootstrap connection, not a supply trunk. Ground's
0.50 default is for short connections; use the intended ground plane for returns.

**Widths are routing defaults, not mandatory minimum widths on every branch.**
A wide trunk must neck down at small pads. Use 0.20 near MCU/sensor pins and
0.50 at regulator and diode lands, widening promptly. Keep necks short and inspect
the complete load path. A small decoupler branch does not carry the whole rail
current. Avoid widening immediately beside adjacent fine-pitch pads.

Measured minimum pad dimensions from the saved board:

| Component group | Narrow pad dimension | Practical entry |
|---|---:|---|
| U20 RP2354B | 0.20 | 0.20 |
| U21 ICM-45686 | 0.35 | 0.20 |
| U22 BMP581 | 0.30 | 0.20 |
| U23 LSM6DSK320X | 0.35 | 0.20 |
| J4 USB signal pins | 0.30 | 0.30, or short 0.20 escape |
| U7 / U12 / Q1 | 0.60 | 0.50 |
| D1 | 0.45 | 0.20 neck or carefully oriented 0.50 entry |
| L20 | 0.55 | 0.50 |

The 0.20 entries are the general-purpose choice; the listed Signal-class nets use
0.10 mm, including entries at those pads. Power pad
entries are as tabulated. Neither width is datasheet-mandated or universally
impedance-optimal.

## Power budget and width rationale

No servos, motors or actuators are powered through the FC. Possible loads are four
ToF sensors, several lidar modules, GPS and ELRS. External electronics use the
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

Use broad copper where available for shared supply paths. Parallel vias are needed
for substantial rail current; one generic via is not automatically rated for the
whole 2 A rail.

## Datasheet findings that matter while routing

Datasheets are listed with their manufacturer Source URLs in
[datasheets/README.md](../datasheets/README.md).

- **RP2354B:** the core regulator is the critical layout. Follow section 6.3.8 of the
  [RP2350 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)
  and its switching-current loop drawing; keep L20 and its input/output capacitors on
  the same side, minimize VREG_LX copper, maintain the specified ground returns,
  and avoid copper immediately below L20/LX on the adjacent layer. VREG_AVDD is
  noise-sensitive. The 0.50 preset cannot enforce this topology.
- **USB:** RP2350 is full speed, 12 Mbps; Raspberry Pi still recommends a 90 Ω
  differential path and an uninterrupted ground reference. Keep the existing
  series resistors. The 0.36/0.20 pair (USB netclass) is a starting geometry for the saved
  four-layer stackup, **not verified controlled impedance**. Confirm it with
  JLC's calculator using the actual stackup, finished copper and mask. Keep
  connector-to-resistor and resistor-to-MCU paths
  balanced; do not assume KiCad combines their separate nets for skew checks.
  [Raspberry Pi hardware design guide, USB section](https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf)
- **AP63203:** use compact input/switch/output loops and short capacitor returns.
  Its layout section recommends 2 oz copper for a 2 A application. The
  lower-cost 1 oz process therefore requires checking temperature at the actual
  load; full 2 A continuous operation has not been demonstrated on this board.
  Use 1.00 mm/shared copper where it fits and short 0.50 mm pin entries.
  [AP63203 datasheet](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf)
- **TPS7A2033:** a 300 mA sensor LDO, with close input/output capacitors and copper
  area for heat spreading. The 0.50 default is ample for its intended local
  branches; thermal dissipation still depends on voltage drop and actual load.
  [TPS7A20 section 7.4](https://www.ti.com/lit/ds/symlink/tps7a20.pdf)
- **ICM-45686 / LSM6DSK320X / BMP581:** ordinary Signal-class traces (0.10 mm) are the
  default for routing geometry. ICM SPI supports up to 24 MHz; short paths,
  decoupling and quiet returns matter more than making signal copper wide.
  The separate SPI buses (ICM on SPI0, LSM6DSK320X on SPI1) and interrupt nets
  follow the schematic. ICM pin 9 (CLKIN, net ICM_CLKIN) is driven by the
  32.000 kHz oscillator X1 on V3V3_ANA (C1 100 nF); the ICM interrupts on INT1 only.
  [ICM](https://www.lcsc.com/datasheet/lcsc_datasheet_2411220643_TDK-InvenSense-ICM-45686_C22459454.pdf), [LSM6DSK320X](https://www.st.com/resource/en/datasheet/lsm6dsk320x.pdf)
- **BMP581 exception:** Bosch asks for 0.20 mm pad spacing, no traces/vias beneath
  the sensor, and no mask under the sensor body with 20 µm horizontal mask
  clearance. The pad-spacing rule is installed. The footprint has
  ordinary separate mask openings, so the under-body mask and keepout arrangement
  is a footprint/CAM review item. Global mask shrinking is not used as a fix.
  This can affect sensor performance even when generic fab DRC passes.
  [BMP581 section 8.2](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp581-ds004.pdf)
- **SD / optional QSPI:** the Signal class (0.10 mm) is the chosen starting point, not a
  speed guarantee. Keep clock/data over a continuous reference and avoid stubs.
  SD clock damping resistor R58 sits as drawn in the schematic. Socket mechanics do
  not define the card's timing budget; select clock rates after the actual path
  is known. W25Q32JV and APS6404L have different command/frequency limits and
  loads; populating U24 later requires timing review.
  [Winbond](https://www.winbond.com/resource-files/W25Q32JV%20RevJ%2012242024%20Plus.pdf), [AP Memory](https://www.apmemory.com/tw/downloadFiles/0324112120g3605268),
  [Molex 47219-2001 drawing](https://cdn.promelec.ru/upload/items/2020/09/01/472192001_sd.pdf)
- **Crystal / GPIO / LED / switches / sense dividers:** the explicit logic and
  MCU-button nets use the Signal class; crystal, analog sense and LED supply/current nets
  use the Default class. See `MARV-V2.kicad_pro` for the assignments.
  Keep crystal and high-impedance analog paths short and away from switch nodes;
  width does not replace capacitance/noise review.

## Validation

Run `kicad-cli pcb drc --schematic-parity MARV-V2.kicad_pcb` for a read-only check.
The saved board reports 206 violations (22 errors and 184 warnings), 0 unconnected
items and 0 schematic-parity issues; the panel copy reports the same violations. The ERC
reports 0 violations. The violations are:

| Finding | Count | Severity |
|---|---:|---|
| `clearance` on the USB pair (netclass 0.18 mm; two pair-to-pair at 0.14 mm, one D+ to a U20 V3V3_SYS pad at 0.168 mm) | 3 | error |
| `courtyards_overlap` SW1 / J10 | 1 | error |
| `hole_clearance` ("holes outside SMD lands"): GND vias inside U20's ground pad | 18 | error |
| `assertion_failure`: small SMD land review (80 U20 lands, below JLC's generic 0.25 mm minimum SMD-pad dimension) and silkscreen graphic stroke (28) | 108 | warning |
| `lib_footprint_mismatch` | 70 | warning |
| `silk_over_copper`, `via_dangling`, `silk_overlap` | 3 / 2 / 1 | warning |

The 80 MCU lands follow the manufacturer footprint at the 0.4 mm pitch that JLC
supports; they need a package-specific CAM check. **The MCU pads are not enlarged to
make this warning disappear.** No DRC exclusions are used to hide errors.

In **Board Setup → Design Rules**, Constraints, Net Classes, Pre-defined Sizes and
Custom Rules hold the settings above; close and reopen the PCB project so an
already-open editor cannot overwrite them. Route with netclass widths and DRC
avoidance active. Inspect the final Gerber copper/mask/paste/drills and JLC's
assembly/CAM preview before ordering; the installed rules improve coverage but do
not replace JLC's final review.
