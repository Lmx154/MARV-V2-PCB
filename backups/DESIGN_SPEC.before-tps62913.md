# MARV V2 design specification — revision P2 (BEC-fed)

This is the current specification. Revision history: P0 (integrated raw-pack
buck, four-way OR-ing, USB current limiter) and P1 (flight-controller loads,
peripheral rails) are preserved as backups/DESIGN_SPEC.before-*.md and in
backups/pre-*/ schematic snapshots. POWER_*.md files are trade-study history.
P2 supersedes both: the user chose the simplest customary flight-controller
power arrangement.

## Purpose and scope

Flight controller for rockets and drones. MCU is **RP2354B** (QFN-80, in-
package flash). Onboard sensors from the repository libraries: BMI088,
BMP581, ADXL375. Logging: QSPI NOR flash plus a **latched (push-push)
microSD socket**. External modules on generic ports: GPS (UART), ELRS radio
module (UART), magnetometer (I2C). GPS, radio and magnetometer are external
daughterboards that take care of themselves; this board never implements a
module's own circuitry.

Rule adopted for all remaining work: the simplest, most basic form of what
the user states; for unspecified electrical details, do what flight
controllers in the wild do.

P2 implements power and ports only. MCU, sensor decoupling, reset/supervisor,
firmware, servo interfaces and PCB layout are not done. Do not manufacture or
fly this revision.

## Power sources and interfaces

| Interface | Requirement |
| --- | --- |
| J3 BEC in | External 2S–6S BEC, regulated 5 V, 3 A (established fact, off-board). Must stay below 5.5 V including transients. The ESC is 3S–6S; only its BEC output reaches this board. |
| J4 USB-C | USB 2.0 programming/data and bench power, 5 V; no USB PD; no on-board current limiter (standard FC practice); startup budget is a firmware matter. |
| J2 1S cell | Optional configuration: BMS-protected 1S Li-ion, 3.0–4.2 V at the connector; the BMS provides all cell protection; the board adds nothing. |
| VSYS | OR-ed source rail, 3.0–5.25 V. |
| V3V3 | 3.3 V; budget **500 mA continuous / 800 mA peak <= 10 ms** (typical ~300 mA). |
| Peripheral ports | J6 UART_GPS, J7 UART_ELRS, J9 I2C_MAG: identical 4-pin JST-GH, pins 3V3, GND, signal, signal; power is V3V3 direct with a local 10 uF. |
| Servo / propulsion power | External (ESC, BEC distribution); never from V3V3 or USB. |

## Implemented topology

J3, J4 and J2 each feed one **LM66100** ideal diode (U3, U5, U2; CE tied to
VOUT for reverse-current blocking) into VSYS, which carries C8/C9 (2 x 10 uF
ceramic) and C19 (220 uF / 10 V polymer, ~40 mOhm). **U7 TPS63060** buck-boost
converts VSYS to 3.3 V: 1 uH, 3 x 22 uF out, 560k/100k divider, 10 pF
feed-forward, PS/SYNC pulled low (power-save) with BB_MODE available for
fixed-frequency comparison, PG pulled up to V3V3 as PWR_GOOD. This is the
only converter; the buck-boost is what lets the 1S configuration share the
same rail without any extra circuit. USB D+/D- pass through U8 USBLC6; CC1
and CC2 have separate 5.1 kOhm pull-downs. No LDO on any main rail. Common
signal ground; no isolation. Temporary headers J5 (power_3v3) and J8
(power_periph) expose the pending MCU signals until the MCU sheet exists.

Sheets: power_sources (J2/J3/J4, U2/U3/U5, VSYS), power_3v3 (U7, U8, J5),
power_periph (J6/J7/J9, J8). Generator: tools/build_power.py (overwrites
sheets — preserve manual edits first).

## Load budget

| Load | Typical | Peak | Source |
| --- | --- | --- | --- |
| RP2354B, 150 MHz dual core, USB, XIP | 80 mA (assumption, measure) | 100 mA | RP2350 DS 14.9.7 gives only per-block uA/MHz |
| BMI088 + BMP581 + ADXL375 | 6 mA | 7 mA | BMI088 gyro 5 mA; others sub-mA |
| QSPI NOR flash program/erase | 25 mA burst | 25 mA | vendor class figure |
| microSD write | 100 mA | 200 mA | SD spec default/high-speed class |
| ELRS module (SX1262 TX +22 dBm 118 mA + its MCU) | 60 mA | 170 mA | SX1262 DS; no external PA |
| GPS (NEO-M9N class) | 36–50 mA | 100 mA | u-blox DS: IPEAK 100 mA |
| Magnetometer module | <= 1 mA | 1 mA | module supplies its own core rail if it needs one |
| Coincident worst case | ~300 mA | ~600 mA | |

TPS63060 delivers >= 1.5 A at VIN 3.0 V; modelled conversion loss ~0.11 W at
300 mA and ~0.18 W at 500 mA (buck-boost only; the BEC's loss is off-board).

1S-only operation: a 3.0 V cell behind a realistic path (~0.55 Ohm harness,
BMS, LM66100) cannot deliver 800 mA at 3.3 V. Policy: the full 800 mA peak is
guaranteed on 1S only while the cell is >= 3.4 V under load; below a firmware
threshold the board reduces its own demand (stop SD logging, lower radio TX
power over the link, lower MCU clock) to 500 mA continuous. MCU, sensors and
actuator outputs keep priority; the radio link is the last thing degraded.

## Heat and interference

- Enclosed installation, no forced airflow; qualification ambient 60 C;
  junctions below 100 C. Only one converter remains on-board; simulated
  enclosure scenarios are in simulations/RESULTS.md. Sustained 500 mA in a
  poorly coupled enclosure still exceeds the target: treat 500 mA as a burst
  ceiling until the real enclosure is measured.
- 4-layer stack-up SIG-GND-PWR-SIG: solid ground on L2, L3 split pours for
  VSYS/V3V3 with ground fill, the buck-boost and its inductor at the J3/J4
  edge with the SW loop over L2 ground, sensors at the far end, no inductor
  under the IMU/barometer, sensor and ADC supplies on a ferrite-isolated
  island. Shielded inductor; feedback trace away from SW. Keep servo/ESC
  return currents off the sensor ground. The magnetometer is external — mount
  it away from power leads, the inductor and the ESC.
- BB_MODE lets firmware compare power-save vs fixed-frequency noise on the
  sensors; neither is assumed quieter.

## Source behaviour (LM66100, CE = VOUT) — known properties

- Turn-on only after VOUT < VIN - VON (80–250 mV), tON 40 us; turn-off when
  VOUT > VIN + VOFF (0–80 mV), tOFF 2 us; body diode 0.5–1.1 V while off.
  Natural voltage priority; near-equal sources share.
- Handover: removing BEC or USB while the 1S cell is the fallback leaves VSYS
  on the body diode for ~36 us. C19 (>= 110 uF effective needed; 176 uF at
  -20 %) keeps VSYS above the TPS63060 2.5 V floor in every simulated case at
  0.8 A with worst-case timing. Results in RESULTS.md.
- Reverse current below VOFF/RON (~0.5–0.7 A) is not blocked. A stiff 5 V
  source lifts VSYS past the trip point in microseconds (negligible charge
  into the cell). A source that cannot supply load + VOFF/RON would trickle
  into the cell instead; with USB now unlimited this is bounded only by the
  USB port and cable — bench sessions with the 1S cell attached should be
  short, or the cell disconnected. Cell-voltage sensing belongs on the MCU
  sheet (battery telemetry) and lets firmware detect the condition.
- Insert inrush: a cell or BEC inserted into a discharged VSYS drives a
  source-impedance-limited pulse (~15–19 A peak modelled at 0.2 Ohm) through
  the LM66100 body diode and FET, lengthened by C19 (~160 us above 1.5 A).
  Bench-check against the BMS overcurrent delay and the LM66100 pulse rating.

## Open items and gates

- Servo count / signal voltage; actuator interface sheet.
- MCU sheet: RP2354B decoupling per datasheet, VBUS sense, reset/power-fail
  supervision (PWR_GOOD reflects the TPS63060 control loop, not a voltage
  threshold), cell-voltage divider, I2C pull-ups, UART TX/RX naming, QSPI
  flash and the latched microSD socket, USB series termination.
- Exact MPNs for capacitors, inductor (saturation >= 4 A), connectors.
- Hardware validation: source insert/remove with logging active, low cell,
  max load, no-airflow soak, USB enumeration on a real host.

## Validation

kicad-cli ERC (0 errors, 0 warnings), netlist export + tools/check_power_
netlist.py, tools/run_power_checks.py (behavioral ngspice; writes
simulations/RESULTS.md with a Status line and exits non-zero on any violated
predicate), PDF export to reports/. The models are architectural: they do not
prove loop stability, EMI, USB compliance or enclosure temperature.
