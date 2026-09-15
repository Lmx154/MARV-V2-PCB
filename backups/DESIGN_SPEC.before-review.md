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
| V3V3 | 3.3 V nominal; provisional 300 mA continuous / 500 mA peak for <=10 ms |
| USB operation | Reduced startup load; enable higher current only after host grant; see USB gate below |
| Servo/propulsion power | External BEC/boost/ESC distribution; never from V3V3 or USB |

External modules drawing board power count toward the avionics budget.
The board is not rated for arbitrary BEC voltages or raw battery input on
J2/J3. A 3–6S ESC rating does not establish its accessory-output voltage.
The cell model and its protection cutoff must be selected before release.

## Implemented power topology

J1 -> F1 -> D1 reverse-polarity diode -> U1 high-voltage buck -> BUCK_5V.
J2, J3, BUCK_5V and current-limited USB each feed a separate U2–U5 ideal
diode into VSYS. U7 converts VSYS to V3V3. Common signal ground; no galvanic
isolation. Multiple sources can remain connected without intentional charging.

U1 is LMR36510ADDAR, using the manufacturer's 5 V starting circuit:
22 uH and two 22 uF output capacitors. R1/R2 give approximately 5.016 V.
U7 is TPS63060DSCR: 1 uH, three 22 uF output capacitors, and a 560k/100k
feedback divider for nominal 3.3 V. A 10 pF feed-forward capacitor is included.
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
tolerance; it is **not a guaranteed 100 mA ceiling**. Startup current and
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
complete reset/power-fail supervisor. The RP2354 USB and regulator analog
supplies require at least 3.135 V; the provisional post-startup simulation
window is 3.135–3.60 V pending all sensor tolerances. PFM positioning and
load/line tolerance must fit inside it.
[MCU supply requirements](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf).

Fuses, TVS pulse-energy coordination, exact capacitor/inductor MPNs and
connector keying/current ratings remain release gates. A fuse does not
provide battery undervoltage protection; a TVS does not make indefinite
overvoltage safe. D2 uses a unidirectional avalanche-diode symbol with cathode at HV_IN;
verify the selected SMBJ26A's clamp voltage against pulse current and input ratings.

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
