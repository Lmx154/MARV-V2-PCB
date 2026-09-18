# MARV V2 flight controller

This repository contains the KiCad hardware design, component libraries, design
checks, sourcing and assembly helpers, and input-power simulation for MARV V2.
It contains no flight-control firmware.

Open [MARV-V2.kicad_pro](MARV-V2.kicad_pro) in KiCad. The saved schematic and PCB
are the working design; [DESIGN_SPEC.md](DESIGN_SPEC.md) records the intended
architecture and [PINOUT.md](PINOUT.md) records the GPIO assignments.

## Hardware functionality

| Area | Included in the design |
| --- | --- |
| Power input | External regulated 5 V and USB power, combined through the Q1/D1 OR into V5_SYS. External battery conversion and charging happen off-board. |
| System power | AP63203 buck supplies V3V3_SYS for the MCU, storage and external 3.3 V IO. |
| Sensor power | TPS7A2033 LDO takes V5_SYS and supplies V3V3_ANA for onboard sensors and MCU analog supply. Its enable comes from V3V3_SYS. |
| Processing | RP2354B MCU, clock, reset and boot circuitry. |
| Sensors | ADXL375 on dedicated SPI0; ICM-45686 on dedicated SPI1; BMP581 on I2C0. All five sensor interrupts have independent GPIOs. |
| Storage | Molex 47219-2001 (C164170) locking hinged-lid microSD socket, PIO + DMA native four-bit SD on GPIO26–31, with 10k CMD/data pull-ups and 22 ohm clock damping; optional, normally unpopulated QSPI expansion land. |
| External IO | GPS and ELRS UARTs, magnetometer I2C, four ESC outputs, four servo outputs and four exposed spare GPIOs. |
| Measurements | Battery voltage, USB presence and external ESC current-sense input; ESC telemetry input. |
| Debug and indicators | USB-C, SWD pads, sensor test points, addressable RGB status LED and USB power indicator. |

GPS, ELRS, magnetometer and spare IO power comes from V3V3_SYS. Servo power is
external 5V_IN, upstream of the OR. USB powers the board's 3.3 V electronics and
modules, but does not intentionally power the servo rail. Raw battery voltage
is sense-only on this PCB.

The four-layer PCB retains its component and pad placement. Existing tracks,
vias and generated copper zones were cleared for manual routing. The communication schematic revision has not been transferred to the PCB; the owner
must update its nets, add R57/R58, replace J11 with the locking connector footprint,
and remove R41 before routing. See the
[communication validation report](reports/communication-architecture.md). Peripheral
roles in the pinout describe hardware connections and intended use, not
implemented firmware.

**The owner handles PCB routing.** Agents must preserve manual design work and
must not route, autoroute, stitch planes or rebuild placement. See
[AGENTS.md](AGENTS.md).

## Repository map

| Path | Purpose |
| --- | --- |
| `MARV-V2.kicad_pro` | KiCad project, design rules and net classes. |
| `MARV-V2.kicad_sch`, subsystem `*.kicad_sch` files | Root schematic plus power, MCU, sensors, storage, USB/debug and IO sheets. |
| `MARV-V2.kicad_pcb` | Working PCB with the current component and pad placement. |
| `MARV_Packages.pretty/` | Project footprints. |
| `MARV_Sensors.kicad_sym` | Project sensor symbols. Standard KiCad libraries supply other active symbols. |
| `fp-lib-table`, `sym-lib-table` | Project library registration. |
| `MARV_Packages.3dshapes/` | Local STEP models and [provenance](MARV_Packages.3dshapes/PROVENANCE.md). |
| `datasheets/` | Offline component PDFs with a [source and page index](datasheets/README.md). |
| `power_bom.csv` | Component inventory used by BOM grouping and assembly export. |
| `tools/` | Eleven reusable checking, sourcing, export and maintenance tools, listed below. |
| `simulations/` | Active input-power deck, device models, instructions and results. |
| `reports/` | ERC/DRC reports, netlists, schematic PDF, PCB views, assembly CSVs, sourcing audit and historical sheet map. |
| `backups/` | Historical hardware, documents, BOMs and simulation summaries. Archived code has been removed. |

Reference documents:

- [DESIGN_SPEC.md](DESIGN_SPEC.md): architecture, power connections and remaining hardware work.
- [PINOUT.md](PINOUT.md): GPIO assignments, peripheral allocation and spare-pin constraints.
- [LIBRARIES.md](LIBRARIES.md): component, footprint, model and sourcing details.
- [PROJECT_AUDIT.md](PROJECT_AUDIT.md): simplification history and known tool limitations.

## Requirements

- KiCad 10 and its standard symbol/footprint libraries; `kicad-cli` for checks and exports.
- Python 3. Most scripts use only the standard library.
- KiCad's `pcbnew` Python module for `tools/jlc/export_jlc.py`. Use the Python
  interpreter that has that module installed; on this workstation it is `/usr/bin/python3`.
- ngspice for the input-power simulation.
- FreeCAD for STEP inspection with `tools/3d/bbox.py`.
- Network access for uncached JLC catalogue queries. Cached queries reuse local responses.
- Optional `pdftotext` and `pdfinfo` for inspecting local datasheets.

Run the commands below from the repository root.

## Electrical and footprint checks

| Tool | Function | Output / effect |
| --- | --- | --- |
| [check_power_netlist.py](tools/check_power_netlist.py) | Checks critical pin connections, power boundaries, all 48 GPIO assignments, IO rows, sensor/storage buses, test points, DNP status and footprint pad coverage. | Reads an exported XML netlist; prints pass/failure. |
| [audit_footprints.py](tools/audit_footprints.py) | Checks footprint resolution, files, referenced 3D assets and symbol-pin versus footprint-pad counts. | Prints a report; optional `--json PATH` writes structured results. |
| [netlist_fingerprint.py](tools/netlist_fingerprint.py) | Produces sorted connectivity and component records for comparing schematic revisions independently of drawing layout. | Prints records including values, footprints, LCSC numbers and fit status. |

Export a fresh netlist before running checks that read it:

```sh
kicad-cli sch erc --severity-all --exit-code-violations -o reports/power-erc.rpt MARV-V2.kicad_sch
kicad-cli sch export netlist --format kicadxml -o reports/power-netlist.xml MARV-V2.kicad_sch
python3 tools/check_power_netlist.py reports/power-netlist.xml
python3 tools/audit_footprints.py reports/power-netlist.xml
kicad-cli pcb drc --severity-all --exit-code-violations -o reports/pcb-drc.rpt MARV-V2.kicad_pcb
```

KiCad ERC checks electrical rules; DRC checks PCB geometry and connectivity
against the project's rules. The project retains net classes for power, 3.3 V
rails, USB, sensor SPI and motor/servo signals. An unrouted board will report
unconnected items.

These are manufacturing aids, not a dedicated manufacturer DFM approval tool.
Footprint file availability does not establish package fit or assembly rotation.
See [LIBRARIES.md](LIBRARIES.md) for the physical checks still required.

## Component sourcing and assembly exports

| Tool / data | Function | Output / effect |
| --- | --- | --- |
| [jlc_api.py](tools/jlc/jlc_api.py) | Searches JLC's public catalogue by keyword or LCSC number; retrieves attributes, package, library class, stock and price tiers. | Prints results or raw JSON; writes a response cache. `--refresh` bypasses the cache. |
| [find_part.py](tools/jlc/find_part.py) | Filters candidates by package, attributes, voltage, tolerance, description and stock; ranks Basic, Preferred, then Extended. | Prints candidates; does not replace components. |
| [bom_lines.py](tools/jlc/bom_lines.py) | Groups `power_bom.csv` by specification and footprint; separates purchased, DNP and board-feature entries. | Prints quantities and solder-joint totals; optional `--json PATH`. |
| [audit.py](tools/jlc/audit.py) | Checks mapped LCSC parts against catalogue data and totals component costs, library classes, placements and estimated setup fees. | Prints text or `--md` output. Supports `--refresh`. |
| [export_jlc.py](tools/jlc/export_jlc.py) | Generates assembly BOM and CPL/position files from BOM data, schematic LCSC fields and existing PCB placement. | Writes `reports/jlc-bom.csv` and `reports/jlc-cpl.csv`; does not place or move components. |
| [lcsc_map.csv](tools/jlc/lcsc_map.csv) | Records selected LCSC parts by specification and footprint. | Selection data used by the sourcing tools and as an export fallback. |

Example commands:

```sh
python3 tools/jlc/jlc_api.py C1525 --raw
python3 tools/jlc/find_part.py --q "100nF 0402" --pkg 0402 --attr Capacitance=100nF --min-volt 16 --min-stock 1000
python3 tools/jlc/bom_lines.py
python3 tools/jlc/audit.py --md
/usr/bin/python3 tools/jlc/export_jlc.py --netlist reports/power-netlist.xml
```

The API cache defaults to `~/.cache/jlcparts/api`; `JLC_CACHE` overrides its
location. Cached responses do not expire automatically. Prices, solder-joint
counts and setup fees are estimates: joint counts use a footprint table and
fees are coded assumptions, not a complete manufacturing quote.

Assembly export excludes DNP parts, bare pads, holes and normally the J6–J8
through-hole headers. `--with-tht` includes those headers; `--outdir PATH`
changes the output location. The current CPL workflow is for front-side assembly.
Verify every rotation in JLC's assembly preview. Missing fitted LCSC numbers
cause failure after files have been written; BOM/CPL designator mismatches
print warnings.

When changing components, keep the saved schematic, `power_bom.csv`, schematic
`LCSC` properties and `tools/jlc/lcsc_map.csv` aligned. Export a fresh schematic
netlist before generating assembly files. No schematic generator maintains
these records automatically.

## Input-power simulation

[simulate_power_input.py](tools/simulate_power_input.py) runs the single active
[SPICE deck](simulations/power_input.cir). It first exports the saved schematic
and checks the key input-network connections and component assumptions.

The seven cases are external power only, USB only, both connected, USB
insertion, USB removal, external removal and an external-powered load step.
Measurements include V5_SYS dips and final voltage, source sharing, reverse
current and estimated Q1/D1 electrical losses.

```sh
python3 tools/simulate_power_input.py
python3 tools/simulate_power_input.py --load 0.5 --external-load 1.0
```

Options are `--load`, `--external-load`, `--external-voltage` and
`--usb-voltage`. Default demand is an assumed 0.5 A at V5_SYS.
`--external-load` adds demand on 5V_IN upstream of the OR.

The runner overwrites [simulations/RESULTS.md](simulations/RESULTS.md) and keeps
exact decks, logs, waveforms and the exported netlist in a printed temporary
directory. It fails if the measured event-window voltage falls below its
3.8 V input threshold, or if wiring checks or the solver fail.

This models power arriving at V5_SYS. It does not simulate external converters,
regulator control loops or outputs, charging, USB negotiation, PCB parasitics,
sensor noise or temperatures. Read [simulation scope and assumptions](simulations/README.md)
before interpreting results.

## Design maintenance and mechanical inspection

| Tool | Function | Output / effect |
| --- | --- | --- |
| [relink_pcb_paths.py](tools/relink_pcb_paths.py) | Repairs footprint-to-schematic identity paths after sheet reorganization; checks for unmatched references. | Default rewrites PCB identity paths. `--dry-run` inspects without writing. |
| [bbox.py](tools/3d/bbox.py) | Reads STEP geometry and reports bounding coordinates, dimensions, centers, solids and faces to assist model alignment. | Prints measurements; does not change the STEP or footprint files. |

```sh
python3 tools/relink_pcb_paths.py --dry-run
/snap/bin/freecad.cmd -c tools/3d/bbox.py </dev/null
pdftotext datasheets/AP63203.pdf -
```

The STEP helper accepts individual files after `--`; without them it inspects
the local model directories. See [tools/3d/README.md](tools/3d/README.md).
Existing STEP assets and their provenance remain available; one-time model
generators have been removed.

## KiCad exports and project status

Installed KiCad CLI commands also provide Gerber and drill output, position
files, IPC-2581, ODB++, IPC-D-356 netlists, board statistics, PDF/SVG drawings,
STEP and other 3D formats, and PCB rendering. These are standard KiCad tools;
this repository does not contain an automated fabrication-release pipeline.

Reports and renders are derived snapshots. Regenerate the relevant outputs
after changes; older PNG renders and archived documents may describe previous
board states. A passing schematic check or input simulation does not mean the
board is ready to manufacture.

Legacy schematic generators, routing and placement utilities, one-time STEP
generators, obsolete simulation code and archived Python scripts have been
removed. Historical documents under `backups/` can mention deleted commands;
they are not instructions for the current workflow.
