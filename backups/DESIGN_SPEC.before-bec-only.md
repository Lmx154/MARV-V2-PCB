# MARV V2 design specification — revision P0

This is the current specification. It supersedes the architecture choices in
POWER_TRADE_STUDY.md, POWER_ARCHITECTURE_USB_6S.md and
POWER_PARTITION_DECISION.md; those files retain the trade-study history.

## Purpose and scope

General robotics controller, including rockets and drones. Integrated
avionics power is authorized. Servo/motor control and logging are required;
GPS, radio and magnetometer are external. RP2354 and the repository's sensor
libraries are the starting candidates; MCU variant, sensor population,
logging medium, servo count and peripheral currents remain unconfirmed.

P0 implements **power circuitry only**. MCU, sensor decoupling, reset/
supervisor, firmware, servo interfaces and PCB layout are not complete.
Do not manufacture or fly this revision.

## Electrical interfaces and provisional budgets

| Interface | P0 requirement |
| --- | --- |
| J1 raw pack | 9.0–25.2 V normal input, conventional 3–6S Li-ion/LiPo; separate connector |
| J2 cell | Externally protected 1S; 3.0–4.2 V at connector under load; no onboard charger |
| J3 external BEC | Regulated 4.75–5.25 V; must remain below 5.5 V including transients |
| J4 USB-C | USB 2.0 programming/data and standalone avionics power; no USB PD |
| V3V3 | 3.3 V nominal; budget 500 mA continuous / 800 mA peak for <=10 ms (typical ~300 mA); see "Load budget (P1)" |
| Peripheral ports | Three generic 4-pin JST-GH ports on direct V3V3: UART_GPS, UART_ELRS, I2C_MAG (3V3, GND, two signals); loads count toward the V3V3 budget |
| USB operation | Reduced startup load; enable higher current only after host grant; see USB gate below |
| Servo/propulsion power | External BEC/boost/ESC distribution; never from V3V3 or USB |

External modules drawing board power count toward the avionics budget.
The board is not rated for arbitrary BEC voltages or raw battery input on
J2/J3. A 3–6S ESC rating does not establish its accessory-output voltage.
The cell model and its protection cutoff must be selected before release.

## Load budget (P1) and peripheral rails

MCU is RP2354B (QFN-80, in-package flash). The board is a flight controller
and also powers external modules, as is customary: an ELRS radio module
(Semtech SX1262 + RP2354A, no external PA, <= +22 dBm), a u-blox NEO-M9N GPS
and a Bosch BMM350 magnetometer. Logging uses both QSPI NOR flash and microSD.

| Load | Typical | Peak | Source |
| --- | --- | --- | --- |
| RP2354B, 150 MHz dual core, USB, XIP | 80 mA (assumption, measure) | 100 mA | RP2350 DS 14.9.7 gives only per-block uA/MHz |
| BMI088 + BMP581 + ADXL375 | 6 mA | 7 mA | BST-BMI088 Table 10 (gyro 5 mA), BMP581, ADXL375 |
| QSPI NOR flash program/erase | 25 mA burst | 25 mA | Winbond class figure, verify MPN |
| microSD write | 100 mA | 200 mA | SD spec default/high-speed class |
| ELRS module: SX1262 TX +22 dBm 118 mA + RP2354A ~50 mA | 60 mA | 170 mA | SX1262 DS Table 5 |
| NEO-M9N | 36-50 mA acquisition, 28-36 tracking | 100 mA | NEO-M9N DS: IPEAK 100 mA, IVCC 50/43/36 mA |
| BMM350 | 0.2 mA | 1 mA | BST-BMM350-DS001; VDD 1.72-1.98 V, VDDIO 1.72-3.6 V |
| Coincident worst case | ~300 mA | ~600 mA | sum of peaks with SD write + ELRS TX + GPS acquisition |

Budget adopted: **500 mA continuous, 800 mA peak <= 10 ms** on V3V3. The
TPS63060 delivers >= 1.5 A at VIN 3.0 V, so the converter has margin; the
modelled conversion loss rises to ~0.43 W at 500 mA (0.26 W at 300 mA), and
onboard dissipation at a sustained 500 mA is ~1.7 W. The lumped enclosure
scenarios at 60 C ambient then give a board node of 77 C (10 K/W), 95 C
(20 K/W) and 129 C (40 K/W) after an hour, against 73/86/112 C at 300 mA.
Consequence: 500 mA is a budget ceiling for peaks and short logging bursts,
not a sustained operating point, unless the measured assembly thermal
resistance is below ~20 K/W; the typical ~300 mA case must be confirmed by
measurement in the real enclosure before any flight in still air. An external PA (>= 250 mW) is out of this budget and must
have its own regulator from VSYS or the pack.

1S-only operation: a 3.0 V cell (protection-cutoff level) behind a realistic
derated path (harness, F2, protection FETs, LM66100: ~0.55 Ohm) cannot deliver
800 mA at 3.3 V; the model solves VSYS to ~2.24 V, below the TPS63060 floor.
Policy adopted: the full 800 mA peak is guaranteed on 1S only while the cell
is >= 3.4 V under load; below a firmware threshold (provisionally 3.4 V, above
the protection cutoff) firmware reduces board consumption (stop SD logging,
lower radio TX power, drop MCU clock) so the demand falls to 500 mA continuous, which the 3.0 V corner meets with ~90 mV
margin. Shedding order is a firmware decision; MCU, sensors and actuator
outputs keep priority and the radio link is the last thing degraded. On raw
pack, BEC or USB there is no such limit. The simulations carry both corners
(low_cell_only_3v4 at 500/800 mA and low_cell_only_3v0_shed at 300/500 mA).

Peripheral ports (sheet power_periph): three identical 4-pin JST-GH
connectors, J6 UART_GPS, J7 UART_ELRS, J9 I2C_MAG, each pinned 3V3, GND and
two signals, fed directly from V3V3 with a local 10 uF. The user chose the
simplest, customary flight-controller arrangement over switched
current-limited rails (rejected alternative, recorded here: one or two
TPS2553 switches would have given hardware cable-short isolation and a
hardware USB-startup budget; the cost was two ICs and MCU control lines). No
chip-specific circuitry is on the board: any 3.3 V GPS, radio or magnetometer
module with its own regulator/level needs connects to these ports. The
consequences of the direct-rail choice are firmware and operating rules, not
hardware: a cable short is limited only by the TPS63060 current limit and
will brown out the MCU; the USB-only startup budget is met by keeping module
power draw low in firmware (modules are always powered when the board is);
and the 1S load-shed policy below is executed by reducing the board's own
consumption (logging off, radio told to reduce TX power over the link)
rather than by switching rails. Signal pins reach temporary header J8 until
the MCU sheet exists; TX/RX naming is fixed there. I2C pull-ups belong on the
MCU sheet.

Interference and heat with these loads: the radio and GPS are external, so
their RF-side supply cleanliness is theirs to filter locally, but this board
must keep V3V3 ripple low (TPS63060 fixed-frequency mode is available via
BB_MODE for comparison) and must not route switching nodes near the connector
edge that carries them. Planned stack-up is 4 layers, SIG-GND-PWR-SIG: solid
ground on L2 under everything, L3 split pours for VSYS/V3V3/BUCK_5V with
ground fill, converters and inductors at the J1/J4 edge with SW loops on L1
over L2 ground, sensors on the far end, no inductor under the IMU/barometer,
and ADC_AVDD / sensor supplies on a ferrite-isolated island. The BMM350 must
be mounted away from power leads, inductors and the ESC.

## Implemented power topology

J1 -> F1 -> D1 reverse-polarity diode -> U1 high-voltage buck -> BUCK_5V.
J2, J3, BUCK_5V and current-limited USB each feed a separate U2–U5 ideal
diode into VSYS. U7 converts VSYS to V3V3. Common signal ground; no galvanic
isolation. Multiple sources can remain connected without intentional charging.

U1 is LMR36510ADDAR, using the manufacturer's 5 V starting circuit:
22 uH and two 22 uF output capacitors. R1/R2 give approximately 5.016 V.
U7 is TPS63060DSCR: 1 uH, three 22 uF output capacitors, and a 560k/100k
feedback divider for nominal 3.3 V. A 10 pF feed-forward capacitor is included.
VSYS carries C8/C9 (2 x 10 uF ceramic) plus C19, a 220 uF / 10 V polymer-
aluminium bulk capacitor (ESR about 40 mOhm) added after the P0 review; see
"Source handover" below for why. Its MPN is preliminary like the other passives.
Capacitor values are nominal; verify effective capacitance after bias,
tolerance and temperature. Inductor footprints and ratings are preliminary
until exact shielded parts and saturation curves are selected.
[U1 reference](https://www.ti.com/lit/ds/symlink/lmr36510.pdf),
[U7 reference](https://www.ti.com/lit/ds/symlink/tps63060.pdf).

U2–U5 are LM66100 ideal diodes, CE tied to VOUT for reverse-current
blocking. This preserves the intent of Schottky OR-ing with reduced
conduction loss, especially for 1S. Natural voltage priority applies;
near-equal supplies can share. Reverse-current blocking has finite response
time and leakage, not perfect mathematical isolation.

Datasheet handover figures (LM66100, CE tied to VOUT): the pass FET turns on
only when VOUT < VIN - VON with VON = 80-250 mV, in tON = 40 us; it turns off
when VOUT > VIN + VOFF with VOFF = 0-80 mV, in tOFF = 2 us; while off, the body
diode conducts at 0.5 V typical (1.1 V max); reverse current may reach the
0.5-1 A activation level before blocking completes. Consequences: a source
takes over only after VSYS has sagged VON below it, so a handover to a low
cell dips VSYS by more than the source difference; near-equal sources (BEC vs
BUCK_5V) share hysteretically rather than switching cleanly. RON is 110 mOhm
max at 5 V and about 150 mOhm at a 3.0 V cell, giving VSYS ~2.93 V at 0.5 A.

### Source handover (P0 review finding and C19 decision)

With the dead band modelled at datasheet limits, removing a 5 V source while a
3.0 V cell is the fallback leaves VSYS on the LM66100 body diode for the 36-40 us
turn-on delay. With only C8/C9 (20 uF) the model showed VSYS at about 2.49 V for
18-28 us (2.0 V in the derated BEC-removal corner, inside the TPS63060 1.8-2.2 V
UVLO band) and the 3.3 V rail coasting to 2.99-3.09 V, below the RP2354 3.135 V
floor. Pass predicate adopted: VSYS never below the TPS63060 recommended-
operating floor of 2.5 V in any handover case at 500 mA with worst-case LM66100
timing. The binding case is BEC or USB removal (no other bulk in parallel);
it needs at least 110 uF effective on VSYS. C19 = 220 uF polymer (176 uF at
-20 %) gives zero time below 2.5 V in every worst-case row, VSYS minimum
2.626 V (worst case, 0.5 A) / 2.732 V (typical), and both integrated corners
back inside the 3.135-3.60 V window. Polymer was chosen because it has no
DC-bias derating; the ESR is immaterial to a 36 us charge-balance event.
Sizing for a 2.6 V minimum (about 270 uF ceramic / 210 uF polymer) was
rejected: 9 mV of margin against an arbitrary target for ~50 % longer USB
charge time and inrush exposure.

Reverse current below the blocking threshold (found in P1 review). The
LM66100 turns its FET off only when VOUT exceeds VIN by VOFF (0-80 mV); while
the FET is on, a reverse current smaller than VOFF/RON (about 0.53 A at a
3.0 V cell with RON 150 mOhm, about 0.73 A at 4.2 V with 110 mOhm; the
datasheet's IRCB "reverse activation current" of 0.5-1 A says the same) is
not blocked at all. Two situations follow. (1) Transient: when a stronger
source appears while the cell FET is on, up to that current flows into the
cell until the source lifts VSYS past the trip point; a stiff BEC or the
5 V buck does so in microseconds, so the charge is negligible. (2) Standing:
if the stronger source is current-limited below load + VOFF/RON it never
reaches the trip point and the excess flows into the cell indefinitely. The
USB path is exactly such a source: on the bench with a 1S cell attached and a
light load, USB at its 100-137 mA limit (or 284-364 mA after the grant) can
trickle-charge the cell at (limit - load) for as long as the session lasts,
uncontrolled except by the cell's protection board. This contradicts the
"no intentional charging" statement in spirit even though no charger exists.
Simulated magnitudes (RESULTS.md, "Standing reverse current"): USB at a
100 mA limit with a 3.6 V cell and 50 mA load pushes a standing 49 mA into
the cell with the cell FET fully on; a stiff 5.25 V BEC inserted onto a
4.2 V cell at worst-case VOFF gives a 0.52 A reverse pulse for 15 us and then
blocks, i.e. about 8 uC, negligible.
Mitigations, in increasing cost: firmware detects the condition (requires a
cell-voltage ADC divider on CELL_FUSED, which the MCU sheet must add anyway
for battery telemetry) and warns or raises the USB load; a power mux with
source priority on the cell path (e.g. TPS2116, break-before-make, external
power preferred over battery) instead of the LM66100, which replaces
"natural voltage priority" with an explicit priority order and is therefore a
requirement change for the user to decide; or an operational rule that the
cell is disconnected during USB bench sessions. Raw-pack (LMR36510, 1.3 A
valley limit) and BEC sources are stiff enough to trip the block and are not
affected in the model.

Costs recorded as gates, not solved:
- Insert inrush. A 4.2 V cell or 5.25 V BEC inserted into a discharged VSYS
  drives a source-impedance-limited pulse through the LM66100 body diode then
  FET: modelled 15-19 A peak with 0.2 Ohm total source impedance, independent
  of capacitance, exceeding the LM66100 2.5 A / 0.1 ms body-diode pulse rating
  even before C19. C19 lengthens it: about 160 us above 1.5 A and 117 us above
  2.5 A on cell insert, I2t about 7 mA2s (cell) / 12 mA2s (BEC). Before
  release: confirm F2/F3 I2t is at least 10x these figures, confirm the chosen
  1S protection board's overcurrent delay exceeds 0.5 ms, and bench-measure the
  pulse. If the LM66100 or the cell protection cannot tolerate it, the fallback
  is an inrush-controlled path (power mux / eFuse with dV/dt control or a
  series NTC on J2/J3), which is a topology change and needs a new decision.
- USB insertion. At the TPS2553 minimum limit (100 mA) charging C19 takes
  about 12 ms unloaded / 17 ms at 30 mA idle, past the 7.5 ms typical FAULT
  deglitch. TPS2553DBV is the constant-current variant (the -1 suffix latches
  off), so VSYS still charges, but USB_FAULT_N will pulse low at insertion.
  Firmware must mask USB_FAULT_N for about 25 ms after VBUS rises; do not treat
  the first pulse as an overcurrent event.
[Power-path reference](https://www.ti.com/lit/ds/symlink/lm66100.pdf).

The local LM66100_OR symbol models VOUT as a passive switched power path
so valid OR connections can be checked by ERC; the physical pinout is
unchanged. VSYS has one explicit power flag. TPS2553DBV is also a local
symbol checked against its datasheet. No ERC errors have been waived to
declare a regulated-voltage or thermal result.

## Low heat and interference requirements

- No main-rail LDO. Low-current analog LDOs require a specific noise benefit
  and an explicit dissipation budget.
- Design for an enclosed installation with **no forced airflow**. Provisional
  qualification ambient: 60 C inside the enclosure; replace if mission
  requirements are more severe. Target regulator junction temperatures below
  100 C, retaining at least 25 C to the lowest selected regulator's 125 C
  operating limit. Thermal shutdown is not an operating strategy.
- Preliminary power-conversion loss targets: <=0.35 W typical and <=0.50 W
  sensitivity-case at 300 mA output, excluding the MCU/sensor load power.
  These are design targets, not measurements or guaranteed efficiencies.
- At 300 mA, the load itself consumes about 0.99 W. Enclosure heating must
  include that power, regulator losses and every other onboard device.
- Use exposed-pad thermal vias and ground copper as heat paths; do not rely
  on ventilation. Final copper area and enclosure coupling need thermal tests.
- Put switching converters near input connectors, away from IMUs/barometer.
  Keep SW/BOOT loops small, use shielded inductors, keep feedback traces
  away from switching nodes, and follow manufacturer placement guidance.
- Maintain continuous ground reference. Keep high-current servo/ESC return
  currents out of sensor/MCU paths. No undamped input LC filters without
  stability and ringing checks.
- U7 defaults to power-save operation to limit idle heat. BB_MODE permits
  fixed-frequency operation for sensor-noise comparisons. It is not assumed
  that fixed-frequency operation is always quieter or cooler.

## USB and integration gates

J4 includes separate CC pull-downs. U6 limits USB current; Q1 and the ILIM
resistors provide a firmware-controlled higher-current option. A default
232k resistor gives roughly a 0.1 A-class threshold with substantial
tolerance; it is **not a guaranteed 100 mA ceiling**. Using the datasheet
equations (IOSmin = 25230/R^1.016, IOSnom = 23950/R^0.977, IOSmax =
22980/R^0.94, R in kOhm, before resistor tolerance): 232k gives 100/117/137 mA
min/nom/max; 232k || 82.5k = 60.9k gives 388/433/483 mA. Startup current and
inrush must be verified against USB requirements. If firmware cannot meet
the startup budget, revise this path before connecting a host.

The higher-current option uses 232k in parallel with 82.5k (about 60.9k),
chosen below a 500 mA maximum-limit target using the datasheet equations;
resistor and device corners still need review. Budget <=350 mA at VBUS,
with USB-only avionics limited to 300 mA continuous / 400 mA short peak.
The higher-current option must stay off until a valid grant. Firmware should
budget below the *minimum* limiter threshold, not just a typical value.
USB suspend, VBUS sensing while externally powered, boot-ROM behavior,
inrush and resistor-limit tolerances remain explicit integration tests.
If the boot ROM's request is insufficient for the actual load, keep optional
loads disabled or revise the source policy. USBLC6 protects D+/D-; MCU-side
series termination and VBUS detection belong on the future MCU sheet.
[USB switch reference](https://www.ti.com/lit/ds/symlink/tps2553.pdf).

PWR_GOOD is available for MCU sequencing, but does not yet implement a
complete reset/power-fail supervisor. Note that the TPS63060 PG output
reflects the current-control loop (it drops when the converter cannot hold
regulation), not a voltage threshold; it is not an undervoltage detector. The RP2354 USB and regulator analog
supplies require at least 3.135 V; the provisional post-startup simulation
window is 3.135–3.60 V pending all sensor tolerances. PFM positioning and
load/line tolerance must fit inside it.
[MCU supply requirements](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf).

Fuses, TVS pulse-energy coordination, exact capacitor/inductor MPNs and
connector keying/current ratings remain release gates. A fuse does not
provide battery undervoltage protection; a TVS does not make indefinite
overvoltage safe. D2 uses a unidirectional avalanche-diode symbol with cathode at HV_IN;
verify the selected SMBJ26A's clamp voltage against pulse current and input ratings.

## P0 review record (2026-09-14)

Independent review of the three power sheets against the LMR36510, LM66100,
TPS2553, TPS63060, USBLC6 and SMBJ26A datasheets and the exported netlist:
no schematic defects found. Confirmed: all IC pinouts and local symbol pin
maps; HV divider 1.0 V x (1 + 100k/24.9k) = 5.016 V; 3.3 V divider 0.5 V x
(1 + 560k/100k) = 3.30 V; D1/D2 orientation; LMR36510 VIN is rated 4.2-65 V
operating / 70 V absolute maximum, so the SMBJ26A 42.1 V clamp has margin;
TPS63060 DSC has VAUX (bypassed by C13), not a VINA pin; separate 5.1k CC
pull-downs; one PWR_FLAG on VSYS. ERC re-run with the four project-default
"ignore" rules (single_global_label, four_way_junction, footprint_filter,
simulation_model_issue) promoted to warnings yields one cosmetic warning
(J1 Micro-Fit footprint vs the generic Conn_01x02 filter). Simulation
findings: the LM66100 turn-on delay was not modelled (the first model let the
FET conduct exponentially from t=0); corrected to a 36 us dead band + 4 us
ramp, which exposed the handover dip and led to C19. The simulation runner
now always writes RESULTS.md with a Status line and exits non-zero on any
violated predicate instead of aborting before the report. Automated checker
coverage excludes EN strategy, exposed pads, TVS margin, CC pull-downs and
USBLC6 pins; those were reviewed manually this pass only.

## Validation and project files

Open MARV-V2.kicad_pro normally. Its root now links power_hv.kicad_sch,
power_sources.kicad_sch and power_3v3.kicad_sch. The original empty root is
preserved at backups/MARV-V2.before-power.kicad_sch. power_bom.csv is a
preliminary BOM, not a purchase list. Regeneration uses tools/build_power.py
and overwrites generated sheets: preserve manual edits before rerunning it.

Run electrical checks, inspect exported connectivity, and review PDFs.
Simple ngspice simulations test architectural assumptions and switching
passive values; they do not substitute for vendor control-loop models,
transient protection tests, EMI tests or thermal measurements in the enclosure.
Test all source insert/remove combinations with logging active, low cell,
maximum load, actuator disturbances and no airflow before release.
