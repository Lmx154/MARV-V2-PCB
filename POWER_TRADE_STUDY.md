# MARV V2 power architecture trade study

Status: preliminary architecture, 2026-09-14. No regulator or connector has
been finalized, and the main schematic remains empty.

## Requirements and assumptions

Confirmed: rocket and drone use; servo and motor control; logging; external
GPS, radio, and magnetometer; support for a nominal 3.7 V single lithium-ion
cell and power supplied through an ESC or an external BEC.

The cell was described as “18680”; exact part, protection, discharge rating,
and charging limits are unknown. Use 3.0–4.2 V only as a preliminary design
window, not as a specified cell cutoff. RP2354A/B and the three sensor types
are listed in the repository; final variant and selection remain open.

## Recommendation

Make the external BEC optional for avionics and provide a separate external
actuator supply. Put a 3.3 V buck-boost converter on the controller so that
the same avionics hardware accepts either 1S or a regulated external input.
Adopt 5 V nominal external power as the initial interface proposal; support
for 6 V or higher BEC settings must be explicitly rated before implementation.

| Architecture | 1S avionics | Servos | Main tradeoff |
| --- | --- | --- | --- |
| External BEC feeding onboard 3.3 V buck/LDO | Needs an external converter that supports 1S, generally boost | External BEC can serve them if rated | Small controller, but mandatory external conversion for 1S |
| ESC BEC feeding onboard buck/LDO | Depends on the ESC and BEC input specification | Limited by ESC BEC capacity | Fewer modules, but ties avionics power to ESC behavior |
| Onboard 3.3 V buck-boost, separate actuator supply | Yes, within specified cell range | External BEC/boost or compatible actuator battery | Recommended flexibility; additional onboard switching layout work |
| Onboard avionics and high-current servo conversion | Possible with appropriately sized converters | Onboard | Greater area, heat, EMI, connector current and qualification burden |

An external BEC is not necessarily electrically cleaner or redundant. Its
quality, load capability, wiring and shared upstream battery determine the
result. An ESC BEC and separate BEC are equivalent *input interfaces* when
their voltage and transient specifications match. Not every ESC includes a
BEC: Hobbywing explicitly identifies models without one. Never treat an
unknown ESC connector as regulated 5 V. [Hobbywing documentation](https://support.hobbywingdirect.com/hc/en-us/articles/19002681842579-FlyFun-130A-160A-OPTO-V5-ESC-EXTRA-Installation-Information)

## Proposed connectivity

```text
1S cell -> cell protection / reverse-polarity protection --+
                                                        +-> source selection
5 V regulated BEC/ESC -> input protection ---------------+       |
                                                               v
                                                        3.3 V buck-boost
                                                               |
                                                  MCU + sensors + logging

Actuator-rated BEC / battery / 1S boost -> separate servo power distribution
MCU -> control signals + ground reference -> servos / external motor ESCs
Propulsion battery -----------------------> motor ESC power inputs
```

For one source at a time, a single clearly specified avionics input is
sufficient and avoids mux cost. If both sources can be connected at once,
use a priority power mux with reverse-current blocking. Prefer BEC with
cell fallback if continuity is wanted. Do not directly parallel sources or
allow the BEC to charge the cell through the avionics wiring. Charging is
a separate function; USB bench power also needs a defined protected path.

Separate servo-positive and avionics-positive nets. Use a common signal
ground with a continuous ground reference and route high actuator return
currents away from sensor/MCU supply paths. Prefer external high-current
distribution until the servo count and stall currents establish connector
and PCB requirements. Do not split ground planes under digital signals.
Separate rails sharing a cell do not remove common battery impedance.

External GPS/radio/magnetometer still need specified connector voltages,
logic levels and current budgets if this board powers them. Avoid back-power
through signals when one module is unpowered. Motor power goes through the
external ESC; the controller supplies control signals, not propulsion power.

## Candidate parts, not a final BOM

TI TPS63070 is a candidate for the avionics buck-boost: 2–16 V input and
adjustable output encompass 1S and regulated 5 V. Its 3.6 A switch rating
is not a guaranteed output rating at minimum cell voltage. Select the
inductor, effective capacitance, operating mode and thermal margin against
the actual load. The datasheet provides power-good and programmable enable
threshold support. [TI datasheet](https://www.ti.com/lit/ds/symlink/tps63070.pdf)

TI TPS2121 is a candidate for dual-source selection with reverse-current
blocking. Its datasheet specifies a 2.8 V minimum recommended input: cell
sag and path losses near discharge make it a conditional choice, not an
automatic match for all 1S operation. Select a lower-voltage mux if the
required cell window demands it. Switchover must be checked under load.
[TI datasheet](https://www.ti.com/lit/ds/symlink/tps2121.pdf)

A buck or LDO alone cannot maintain 3.3 V when its input falls below 3.3 V.
A boost alone does not provide the needed step-down operation at full cell
voltage. Do not feed a full cell directly into a 3.3 V rail. The RP2354
stacked-flash QSPI supply requires 2.97–3.63 V, reinforcing the regulated
3.3 V choice. MCU core-power circuitry remains a separate reference-design
requirement. [Raspberry Pi datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)

## Power sizing examples

These are scenario assumptions, not measured loads:

- 3.3 V at 0.5 A is 1.65 W. At 3.0 V converter input and assumed 90%
  efficiency, cell current is 0.61 A, excluding path loss and other rails.
- A 5 V, 2 A servo load adds 10 W. At 3.0 V and assumed 85% boost
  efficiency it alone needs 3.92 A. Including the example avionics load
  gives 4.53 A before further sag. Check the actual cell, protection and
  harness at low state of charge and low temperature.
- A 5 V-to-3.3 V LDO at 0.5 A dissipates 0.85 W. From 4.2 V it dissipates
  0.45 W, then eventually loses regulation as the cell discharges.

Thus a 1S avionics supply is plausible; powering all servos from that same
cell is a separate power-design decision. A conventional step-down BEC
cannot generate regulated 5 V from 1S; a boost-capable supply is needed.

## Simulation and validation

`simulations/source_load_trade.cir` compares hypothetical fixed-current
loads behind source resistances, with 470 uF effective capacitance and
30 milliohm ESR. Run:

```sh
ngspice -b -o simulations/source_load_trade.log simulations/source_load_trade.cir
```

The scenarios intentionally use different source voltages and load currents;
they illustrate coupling, not a controlled product-efficiency comparison.
The dedicated-cell scenario assumes a physically separate actuator energy
source. This model excludes battery electrochemistry, regulator loops,
constant-power input behavior, switching EMI, current limits and protection
trips. A real converter can draw more current as input voltage falls.

Before completing the schematic, establish servo count/voltage/stall current,
ESC power-pin specification, cell model, logging medium and external-module
loads. Then simulate the selected converter's startup, minimum input,
logging load steps, BEC loss/restoration and input filter interactions using
vendor models where usable. Use separate checks for reverse current and
short-circuit behavior. A generic model cannot certify those functions.

Bench verification must include simultaneous logging and actuator stalls,
cold/low-charge supply conditions, rail overshoot/undershoot and reset
behavior. Size any hold-up energy from measured shutdown time: for example,
0.5 A for 10 ms over only 0.3 V requires about 16.7 mF by C=I*t/dV,
before ESR and margin. Small decoupling capacitors do not guarantee a
microSD write can finish. Use power-fail indication, a suitable supervisor,
and a logging format/firmware strategy that tolerates interrupted writes.
