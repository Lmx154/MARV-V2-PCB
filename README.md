# MARV V2 flight controller

A small RP2354B flight controller for rockets and drones: a 6-axis IMU, a high-g
accelerometer and a barometer on their own buses, native four-bit microSD
logging, USB-C, and an IO block for GPS, ELRS, a magnetometer and servos. Power
conversion from the pack stays **off the board**; the FC takes regulated 5 V (or
USB) and makes its own 3.3 V rails.

**License:** hardware/docs CC0, code 0BSD, no attribution required. Provided
as-is; see [LICENSE.md](LICENSE.md).

Open [MARV-V2.kicad_pro](MARV-V2.kicad_pro) in **KiCad 10**. The repository holds
the schematic and routed board, local footprints and 3D models, offline
datasheets, the checking/sourcing tools, and the input-power simulation. There
is no firmware here.

**Status (2026-09-22): order-ready.** ERC 0, DRC 0 errors / 0 unconnected /
0 schematic-parity issues; fabrication and assembly exports regenerate from the
saved design (see [Ordering](#ordering)).

[Design specification](DESIGN_SPEC.md) · [GPIO pinout](PINOUT.md) ·
[Libraries](LIBRARIES.md) · [Datasheets](datasheets/README.md) ·
[JLCPCB DFM and routing](reports/jlc-dfm-routing.md) · [Working rules](AGENTS.md)

## The board

| | |
|---|---|
| MCU | RP2354B (QFN-80, 2 MB in-package flash), 12 MHz crystal, USB-C device port, WS2812C status LED, RESET and BOOTSEL buttons, SWD header |
| Size / stack | 50.8 × 45.6 mm, four layers: F.Cu signals · In1 solid GND · In2 V3V3_SYS plane · B.Cu signals. 1.6 mm FR-4, 1 oz outer / 0.5 oz inner, green mask, HASL |
| Rules | 0.15 mm minimum track and clearance, one via size 0.60 / 0.30 mm, no blind/buried/micro vias — JLCPCB's standard four-layer tier with no paid options |
| Assembly | Front side SMT at JLCPCB (88 placements, 34 unique parts). Back side: ESC pad row J3, SWD header J10, unpopulated QSPI expansion socket U24, test points |
| Mounting | Four M3 grommet holes (4.0 mm) with GND rings |
| Connectors | J3 ESC pads (current, telemetry, PWM1–4, 5 V in, GND, VBAT), J4 USB-C, J6/J7/J8 IO block (14 rows × signal / power / GND), J10 SWD, J11 locking microSD |

## Sensor suite

Every sensor has its own bus; no clock or data net is shared between devices, so
each can be driven at its own rate and no transaction blocks another.

| Ref | Part | What it measures | Bus | Interrupts |
|---|---|---|---|---|
| U21 | InvenSense ICM-45686 | 6-axis IMU (gyro + accel), primary attitude source | hardware **SPI1**, exclusive | INT1, INT2 |
| U23 | Analog Devices ADXL375 | ±200 g accelerometer for launch / impact / hard landings | hardware **SPI0**, exclusive | INT1, INT2 |
| U22 | Bosch BMP581 | barometric altitude and temperature | hardware **I2C0**, address 0x46 | INT |
| J11 | Molex 47219-2001 microSD | flight log | PIO + DMA, native **four-bit SD** | — |

The three sensors run from the dedicated V3V3_ANA rail with their chip-select
and I²C pull-ups referenced to it, and all five interrupt lines land on
independent GPIOs. Layout follows the makers' notes: the BMP581 has no copper or
solder mask under its body (Bosch §8.2), and the inertial sensors sit close to
the MCU with short SPI runs. Exact GPIO numbers are in [PINOUT.md](PINOUT.md).

## Power architecture

```text
2S–6S pack → external 5 V / 3 A buck ─┐
1S 18650   → external 5 V boost ──────┘
                                      ↓ J3 5V_IN            USB-C VBUS
                                      Q1 (AO3401A)           D1 (1N5819WS)
                                      └────────── V5_SYS ────┘
                                                    ├─ AP63203 buck → V3V3_SYS  (MCU, microSD, IO block, LDO enable)
                                                    ├─ TPS7A2033 LDO → V3V3_ANA (ICM-45686, ADXL375, BMP581, ADC_AVDD)
                                                    └─ status LED
RP2354B on-chip switcher: V3V3_SYS → 1.1 V core (laid out per RP2350 datasheet §6.3.8)
Raw pack → J3 VBAT → 100k / 10k divider → ADC (sense only)
```

Nothing that moves is powered through the FC. Motors, servos and ESCs get only
their signal pins; the raw pack voltage arrives for measurement, not for use.
The full boundary table is in [DESIGN_SPEC.md](DESIGN_SPEC.md#sources-and-loads).

## Design decisions

Each of these was a choice with alternatives. The reasons are recorded so they
are not re-litigated by accident.

**External 5 V conversion, no onboard pack buck.** A 2S–6S buck or a 1S boost
already exists in every airframe this board goes into, and an onboard one would
add the hottest, noisiest, most layout-sensitive circuit to a 50 mm board.
The FC takes regulated 5 V and does nothing with the pack except measure it.
Battery charging, protection and cutoff belong to the external system.

**Q1/D1 OR for USB and external power — honestly specified.** A P-FET with its
gate on VBUS plus a Schottky lets the board run on the bench from USB alone and
in the air from the BEC. It does *not* guarantee that the BEC "wins" when both
are present: with USB connected the sources share through D1 and Q1's body
diode and V5_SYS sits lower. That is the circuit's real behaviour, it is what the
simulation shows, and the design accepts it rather than adding a priority mux.

**A separate LDO for the sensors, fed from 5 V.** The inertial sensors and the
barometer see a rail that is not the one the MCU, SD card and IO modules are
switching on. The TPS7A2033 takes its input from V5_SYS (headroom that a 3.3 V →
3.3 V filter cannot give) and its enable from V3V3_SYS, so the sensor rail comes
up after the digital rail. A passive filter was considered and rejected.

**Native four-bit SD over PIO instead of SPI mode.** Logging at flight rates
wants the bandwidth of four data lines and the standard SD command set, and the
RP2354B's PIO can run that bus without touching either hardware SPI block — so
SPI0 stays exclusive to the ADXL375 and SPI1 to the ICM-45686. The cost is six
GPIOs that must sit inside the PIO window (GPIO28–33), five 10 k pull-ups and a
22 Ω series damping resistor on the clock placed at the MCU pin.

**A locking microSD socket ("the latch").** J11 is a hinged-lid connector that is
closed and slid into a locked position over the card: a push-push socket can
eject a card under the shock and vibration of a launch or a hard landing, and a
lost log is the one failure a flight recorder must not have. The trade is that
this socket has no card-detect switch, so the former detect pin and its pull-up
were removed and firmware probes for the card.

**Core-regulator layout by the datasheet.** The RP2354B's 1.1 V core switcher
follows RP2350 datasheet §6.3.8 Figures 23–24: CIN/COUT (C39/C45) in a column
with the LX trace passing between their pads (0402 lands narrowed to a 0.50 mm
gap for that), the inductor's high-current loop closed on the top layer with one
ground connection through two adjacent vias, a copper cutout on In1 under the
inductor and LX net only, the AVDD RC filter, the recommended second 4.7 µF on
the core rail (C81) on the far side of the package, and the polarity-marked
Abracon inductor the datasheet specifies (orientation dot toward pad 2 / DVDD).

**Ordinary four-layer fabrication; spend the budget on components.** 0.15 mm
track/clearance, one 0.60 / 0.30 mm via, HASL, standard copper. The single
exception is a local 0.12 mm clearance rule around C39/C45 so LX can pass the
capacitor pads; that is still inside JLC's 3.5 mil four-layer capability and
costs nothing. No HDI, no filled vias, no impedance control: the USB link is
full-speed, and nothing else on the board is fast enough to need it.

**Through-hole headers shipped unpopulated.** J6–J8 (IO block) and J10 (SWD) are
2.54 mm headers the owner solders; JLC assembles the front SMT side only. J10 is
wired SWCLK–GND–SWDIO to match the Raspberry Pi Debug Probe's 3-pin cable.

**Three GPIOs deliberately unexposed.** GPIO26, 27 and 35 are left unconnected
so the IO block keeps a clean four-spare layout (GPIO44–47); the netlist checker
enforces that they stay that way.

## Validating the power input with simulation

The one thing the board cannot control is how power arrives, so that is the one
thing simulated. `tools/simulate_power_input.py` builds an ngspice deck from the
**saved schematic** (it checks the Q1/D1/C19 wiring before running) and drives
V5_SYS through seven cases: external 5 V only; USB only; both present; USB
plugged in while external stays; USB unplugged; external unplugged; and an
external-only load step. The pass criterion is explicit: the lowest V5_SYS seen
in any event window must stay above the AP63203's 3.8 V input minimum, or the
script exits 1.

```sh
python3 tools/simulate_power_input.py                       # default 0.5 A at V5_SYS
python3 tools/simulate_power_input.py --load 0.3 --usb-voltage 4.75
python3 tools/simulate_power_input.py --load 0.5 --external-load 1.0
```

Latest result ([simulations/RESULTS.md](simulations/RESULTS.md)): lowest event
voltage **4.269 V** during USB removal, margin 0.47 V over the floor; USB-only
operation settles at 4.32 V through D1. Assumptions are stated, not hidden:
0.05 Ω external source, 0.35 Ω USB source, a 0.5 A combined demand that is a
starting point rather than a measured budget, the vendor AO3401A model and a
hand-fitted 1N5819WS curve. It does **not** simulate the downstream regulators,
USB negotiation, sensor noise, layout parasitics or temperature — see
[simulations/README.md](simulations/README.md) for the boundary. Anything
beyond the OR is validated on hardware, not in SPICE.

## Verifying the design

Requirements: Python 3, KiCad 10 with its standard libraries, ngspice. The
assembly exporter needs KiCad's `pcbnew` module (`/usr/bin/python3` here).

```sh
mkdir -p build/checks
kicad-cli sch erc --severity-all --exit-code-violations -o build/checks/erc.rpt MARV-V2.kicad_sch
kicad-cli sch export netlist --format kicadxml -o build/checks/netlist.xml MARV-V2.kicad_sch
python3 tools/check_power_netlist.py build/checks/netlist.xml   # rails, all 48 GPIOs, bus endpoints, pull-ups, retired refs
python3 tools/audit_footprints.py build/checks/netlist.xml     # footprint/model availability and pin coverage
python3 tools/dfm.py --check                                   # JLC profile drift (read-only)
kicad-cli pcb drc --schematic-parity --severity-error --severity-warning --format json -o build/dfm/drc.json MARV-V2.kicad_pcb
python3 -m unittest discover -s tests -v                       # DFM tool preservation tests
```

The JLCPCB profile (`config/dfm/jlcpcb.json` and the managed block in
`MARV-V2.kicad_dru`) is applied with `python3 tools/dfm.py --apply` with the PCB
editor closed; it edits only managed settings and never touches placement or
copper. Extra rules live outside the managed block. Netclasses: Signal 0.15 mm,
Default 0.20 mm, LocalPower 0.50 mm, Power 1.0 mm, USB 0.30 mm / 0.20 mm gap.

## Ordering

```sh
kicad-cli pcb export gerbers --no-x2 --subtract-soldermask \
  --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts \
  -o build/fab/ MARV-V2.kicad_pcb
kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-zeros-format decimal \
  --drill-origin absolute --generate-map --map-format gerberx2 -o build/fab/ MARV-V2.kicad_pcb
(cd build/fab && zip ../MARV-V2-gerbers.zip MARV-V2-*.g* MARV-V2.drl MARV-V2-job.gbrjob)
/usr/bin/python3 tools/jlc/export_jlc.py --netlist build/checks/netlist.xml --outdir build/assembly
python3 tools/jlc/audit.py            # live stock / price / extended-part count per line
```

Upload `build/MARV-V2-gerbers.zip` for the PCB and `build/assembly/jlc-bom.csv` +
`jlc-cpl.csv` for front-side assembly. Review every rotation in JLC's preview
and add the remark **"L20: orientation dot toward pad 2 / DVDD"**. Headers are
excluded unless `--with-tht`. `power_bom.csv`, the schematic `LCSC` fields and
`tools/jlc/lcsc_map.csv` are maintained together; the exporter takes part
numbers from the schematic. `build/` is generated and untracked.

## Repository map

| Location | Content |
|---|---|
| `MARV-V2.kicad_*`, `*.kicad_sch` | Project, routed board, custom rules, and the schematic sheets (power OR / 3V3 / VBAT, MCU, IMU, high-g, baro, SD, USB & debug, IO block, QSPI expansion) |
| `DESIGN_SPEC.md`, `PINOUT.md` | Intended circuit and boundaries; every GPIO with its alternates |
| `config/dfm/` | Reviewed JLCPCB profile and custom-rule template |
| `tools/` | Netlist checker, footprint audit, DFM tool, input-power simulation, sheet relinker, netlist fingerprint |
| `tools/jlc/` | Part search, BOM grouping, live catalogue audit, BOM/CPL export |
| `tests/` | Unit tests for the DFM tool's preservation guarantees |
| `simulations/` | The input-power SPICE deck, its README and the generated results |
| `MARV_Packages.pretty/`, `MARV_Packages.3dshapes/` | Local footprints and STEP models with provenance |
| `datasheets/` | Manufacturer PDFs and a source index |
| `reports/` | Decision and review records — see below |
| `build/`, `.dfm-backups/`, `backups/` | Generated output and recovery copies; untracked |

Reports, newest first:

| Report | What it records |
|---|---|
| [electrical-review.md](reports/electrical-review.md) | Review of the saved board before the core-regulator rework |
| [fabrication-cost-audit.md](reports/fabrication-cost-audit.md) | Why the board fits JLC's standard four-layer tier with no upcharges |
| [signal-trace-widths.md](reports/signal-trace-widths.md) | The 55 nets in the 0.15 mm Signal class |
| [jlc-dfm-routing.md](reports/jlc-dfm-routing.md) | JLC capability sources behind every installed constraint |
| [sd-connector-replacement.md](reports/sd-connector-replacement.md) | The locking microSD socket decision and what it removed |
| [communication-architecture.md](reports/communication-architecture.md) | The sensor/SD bus allocation as first made. Its GPIO numbers predate the later pin reorder; [PINOUT.md](PINOUT.md) is authoritative |

Git history keeps the obsolete revisions (onboard pack buck, power mux, buzzer,
earlier connectors); the cleanup baseline is commit `eafe903`. Placement and
routing are done by hand in KiCad and are never regenerated — see
[AGENTS.md](AGENTS.md).
