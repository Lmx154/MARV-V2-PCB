# MARV V2 flight controller

Open [MARV-V2.kicad_pro](MARV-V2.kicad_pro) in **KiCad 10**. This repository
contains the hardware design, local libraries, offline datasheets, checking and
sourcing tools, and the input-power simulation. It contains no firmware.

[Design specification](DESIGN_SPEC.md) · [Pinout](PINOUT.md) ·
[JLCPCB DFM and routing guide](reports/jlc-dfm-routing.md) ·
[Component libraries](LIBRARIES.md) · [Datasheets](datasheets/README.md)

## Hardware and current status

External regulated 5 V and USB feed the Q1/D1 OR. An AP63203 buck powers digital
and external IO at 3.3 V; a separate TPS7A2033 LDO powers onboard sensors.
The RP2354B connects to ICM-45686 and ADXL375 on independent SPI buses, BMP581
on I2C, and a locking Molex 47219-2001 microSD socket on native four-bit SD.
GPS, ELRS, magnetometer and spare IO connect through the external headers.

**No motors, servos or actuators draw power through the FC.** PWM/control signals
are provided; possible powered electronics include ToF/lidar sensors, GPS and
ELRS. Check their voltage requirements and combined peak demand against the
shared system supply. Raw battery voltage is sense-only.

**The PCB is not ready to manufacture.** The saved schematic is ahead of the
board: update nets, add R57/R58, replace J11's footprint and remove R41 before
routing. The locking-socket 3D model is already visible, but the old PCB lands
remain. Existing DRC findings include silkscreen, conservative component-spacing
checks and package-specific mask/land-pattern reviews.

The owner performs PCB placement and routing. Preserve manual edits; do not
route, autoroute, stitch planes or regenerate the design. [Working rules](AGENTS.md)

## Apply or check the JLCPCB settings

The profile targets this four-layer, 1.6 mm board with standard copper
(1 oz outer / 0.5 oz inner), green mask and ENIG for its fine-pitch packages.
It is MARV-specific: its rail assignments and package rules are not a universal
profile for unrelated boards. Source values and remaining limitations are in the
[DFM guide](reports/jlc-dfm-routing.md).

```sh
python3 tools/dfm.py --check         # read-only; exits 1 if managed settings differ
python3 tools/dfm.py --apply         # apply settings, backing up files that change
python3 tools/dfm.py --drc           # check settings and run KiCad DRC/parity
python3 -m unittest discover -s tests -v
```

Close the PCB editor before applying; reopen it afterward. The tool edits only
managed project settings, the managed custom-rule block and board setup metadata.
It preserves schematic files, placements, pads, nets, copper geometry and unrelated
settings. Reapplying an unchanged profile does nothing. Backups go to
`.dfm-backups/`; generated DRC output goes to `build/dfm/`, both ignored by Git.
Use `--project PATH.kicad_pro` for a copied MARV project and `--diff` to inspect
pending changes. Keep additional custom rules outside the marked managed block.

The router picks widths automatically from the netclass:

| Use | Width |
|---|---:|
| Signals: SPI, I2C, UART, SD, PWM, SWD, ADC | 0.20 mm |
| Local power branches | 0.50 mm |
| Shared power trunks | 1.00 mm |
| USB pair, provisional until impedance verification | 0.30 mm / 0.20 mm gap |

One via preset: **0.60 mm diameter / 0.30 mm drill**. Minimum track/clearance:
**0.15 mm**. Short pad escapes may be narrower than the power trunk; inspect the
whole current path. These checks do not certify thermal performance or replace
JLC's final CAM/assembly review. DRC currently returns failure for known unfinished
board work; a clean tooling check is not a clean PCB DRC.

## Check the saved design

Requirements: Python 3 and KiCad 10 with standard libraries; ngspice for power
simulation. Assembly placement export also needs KiCad's `pcbnew` Python module
(`/usr/bin/python3` on this workstation). FreeCAD is optional for STEP inspection.

Run from the repository root:

```sh
mkdir -p build/checks
kicad-cli sch erc --severity-all --exit-code-violations -o build/checks/erc.rpt MARV-V2.kicad_sch
kicad-cli sch export netlist --format kicadxml -o build/checks/netlist.xml MARV-V2.kicad_sch
python3 tools/check_power_netlist.py build/checks/netlist.xml
python3 tools/audit_footprints.py build/checks/netlist.xml
python3 tools/dfm.py --drc
```

The netlist checker verifies power boundaries, all 48 GPIO assignments, exact
sensor/SD bus endpoints, pull-ups and footprint pad coverage. The footprint audit
checks library/model availability and pin counts, not physical fit.
`tools/netlist_fingerprint.py` compares connectivity independently of sheet layout.
See the [communication handoff](reports/communication-architecture.md) and
[locking-socket handoff](reports/sd-connector-replacement.md) for pending PCB work.

## Source parts and export assembly files

```sh
python3 tools/jlc/find_part.py --q "100nF 0402" --pkg 0402 --attr Capacitance=100nF --min-volt 16 --min-stock 1000
python3 tools/jlc/bom_lines.py
python3 tools/jlc/audit.py --md
/usr/bin/python3 tools/jlc/export_jlc.py --netlist build/checks/netlist.xml --outdir build/assembly
```

Generate assembly files only after synchronizing schematic and PCB. The exporter
reads existing placement; it does not place components. Review every rotation in
JLC's preview. DNP parts, board features and normally J6–J8 headers are excluded;
`--with-tht` includes the headers. The exporter can write files before reporting
missing LCSC numbers and only warns about BOM/CPL mismatches, so do not treat
file creation as validation.

Maintain `power_bom.csv`, schematic `LCSC` fields and `tools/jlc/lcsc_map.csv`
together when changing components. Catalogue queries use `tools/jlc/jlc_api.py`;
`--refresh` bypasses the cache at `~/.cache/jlcparts/api` (`JLC_CACHE` overrides).
Cached prices and hardcoded joint/setup estimates are not a current assembly quote.
Stale BOM/CPL and price-report snapshots have been removed.

## Input-power simulation and maintenance

```sh
python3 tools/simulate_power_input.py
python3 tools/relink_pcb_paths.py --dry-run
```

The [input-power simulation](simulations/README.md) checks seven source/load
cases at V5_SYS and writes `simulations/RESULTS.md`. Its default 0.5 A load is an
assumption, not the external-module budget. It does not simulate downstream
regulators, USB negotiation, sensor noise or temperature.

The relinking helper repairs schematic identity paths after sheet moves; its
`--dry-run` is read-only and it refuses mismatched reference sets. It is not a
substitute for updating the PCB from the schematic. [STEP inspection](tools/3d/README.md)
uses FreeCAD for model dimensions.

## Repository contents

| Location | Maintained content |
|---|---|
| Root `*.kicad_*`, library tables | Saved design and project settings |
| `config/dfm/` | Reviewed DFM profile and custom-rule template |
| `tools/`, `tests/` | Reusable design tools and DFM preservation tests |
| `MARV_Packages.pretty/`, `MARV_Packages.3dshapes/` | Referenced footprints/models and provenance |
| `datasheets/` | Manufacturer documents and source index |
| `reports/` | Human-readable design/routing handoffs |
| `simulations/` | Active input deck, models and results |
| `build/`, `.dfm-backups/` | Local generated output and recovery copies; untracked |

Git history retains obsolete design revisions and deleted assets. The cleanup
baseline is commit `eafe903`; use `git show eafe903:path/to/file` to inspect a
removed file. Historical generators, placement/routing automation and duplicate
backup trees do not belong in the active workflow.
