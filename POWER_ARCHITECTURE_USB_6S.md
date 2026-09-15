# MARV V2: updated power recommendation

2026-09-14. This document supersedes the input architecture in
`POWER_TRADE_STUDY.md`, adding the confirmed 3–6S ESC and USB programming /
power requirements. The study's source-impedance discussion still applies.
This is an architecture proposal; the KiCad schematic has not been populated.

## Recommendation and external BEC trade

Use onboard switching regulation for avionics and a separate external
actuator supply. Accept a protected 1S input, regulated 5 V external power,
and USB power. Add a dedicated high-voltage buck input if direct raw 3–6S
pack power is desired. This makes an external BEC optional for avionics;
the servo supply still needs its own voltage/current design.

| Choice | Advantages | Costs / limits |
| --- | --- | --- |
| External BEC or verified ESC BEC -> onboard 3.3 V buck-boost | Smaller board; supports 1S and USB through source selection | Needs external conversion if ESC offers no regulated output |
| Add onboard raw 3–6S -> 5 V buck ahead of that architecture | No external avionics BEC required; supports raw ESC battery feed | Extra area, switching loss, protection and validation |
| Add high-current servo conversion onboard too | Fewer external modules | Servo sizing unknown; larger thermal, EMI and connector burden |

Recommend the second option if direct battery/ESC VBAT input is a firm
requirement. Otherwise the first is the simpler implementation. Do not
equate an ESC's 3–6S battery rating with its accessory-output voltage.
Some ESCs have no BEC at all. [Hobbywing documentation](https://support.hobbywingdirect.com/hc/en-us/articles/19002681842579-FlyFun-130A-160A-OPTO-V5-ESC-EXTRA-Installation-Information)

For conventional cells charged to 4.2 V, 6S reaches 25.2 V before spikes.
The previously considered TPS63070 (16 V input maximum) and TPS2121
(22 V recommended input maximum) must not receive raw 6S. Higher-charge-
voltage chemistries need a revised input ceiling.
[TPS63070 datasheet](https://www.ti.com/lit/ds/symlink/tps63070.pdf),
[TPS2121 datasheet](https://www.ti.com/lit/ds/symlink/tps2121.pdf).

```text
RAW_PACK 3–6S -> protection -> HV buck 5 V -----+
External regulated 5 V BEC -> protection ------+-> protected source selection
1S cell -> protection ------------------------+              |
USB-C VBUS -> current limit + reverse blocking +              v
                                                    3.3 V buck-boost
                                                            |
                                                  MCU / sensors / logging
USB-C D+ / D- -> ESD protection -> MCU USB

External actuator supply -> servo power distribution
Propulsion battery -> external motor ESCs
MCU -> control signals + ground reference -> servos / ESCs
```

RAW_PACK and REG_5V must use distinct net names and appropriately keyed
connectors. Raw pack power must never reach the 1S input. The HV buck is
an option in this diagram, not a finalized part of the schematic.

## Switching conversion and heat

The hot AMS1117 is consistent with linear-regulator loss:
P=(Vin−Vout)*I. The old populated board is not available in this repository
to confirm its actual failure mechanism.

At 5 V input, 3.3 V output and 0.5 A, an LDO dissipates 0.85 W. A switcher
delivering the same 1.65 W at an **assumed** 90% efficiency loses about
0.18 W. A different LDO retains essentially the same conversion loss;
use a buck/buck-boost for the main rail. Small LDOs may still be appropriate
for a justified low-current sensor subrail if there is enough headroom.

LMR36510 is a candidate raw-pack buck: 4.2–65 V input, up to 1 A output.
Its voltage margin is useful but does not replace coordinated transient
protection, capacitor ratings and careful switching-loop layout. Its 1 A
output is for avionics sizing, not a promise of servo capacity.
[TI datasheet](https://www.ti.com/lit/ds/symlink/lmr36510.pdf)

TPS63070 remains an avionics buck-boost candidate downstream of the
protected low-voltage sources. A buck-boost maintains 3.3 V when the 1S
cell is above or below 3.3 V. Its switch-current rating is not the available
output current at minimum cell voltage; check actual load and efficiency
curves. Two conversion stages from raw pack cost efficiency: two hypothetical
90% stages yield 81% combined efficiency. A direct HV-to-3.3 V path ORed
with a separate 1S/USB regulator is an alternative if measured losses justify
the additional output-source coordination.

## USB and simultaneous sources

Use a USB-C USB 2.0 device interface for programming and bench power.
Provide individual 5.1 kohm Rd resistors on CC1 and CC2, ESD protection,
MCU VBUS sensing and controlled inrush. Type-C attachment is not permission
to draw arbitrary current. Observe enumeration and advertised-current
limits, including startup; use CC detection if relying on higher Type-C
current. [TI Type-C guidance](https://www.ti.com/document-viewer/lit/html/SSZTB15/GUID-9C081873-D60C-462A-ABFB-9A4E87F564F0)

Block reverse current into USB, the cell and external supplies. USB powers
avionics only and does not imply battery charging. Keep actuator supply
separate and default control outputs to inactive during startup and USB-only
operation. Independently powered servos still need explicit arming behavior;
separating positive rails does not by itself inhibit motion.

The diagram contains up to four power inputs. One two-input TPS2121 cannot
implement the complete selector. Use appropriately rated cascaded muxes or
controlled ideal-diode paths, with defined source priority and verification
of every insertion/removal combination. Prefer external flight power when
present; USB bench operation should avoid needless cell discharge. Decide
explicitly whether the cell is a backup during externally powered operation.

TPS2121 has a 2.8 V minimum recommended input. It may be unsuitable for the
desired loaded-cell minimum after protection/wiring losses; select a
lower-voltage device if needed. No mux has been finalized.

Preserve a continuous signal ground and keep servo/ESC high-current returns
out of avionics supply paths. Separate rails sharing one cell still share
the cell's impedance. External GPS/radio/magnetometer modules need specified
interface levels and power budgets if they draw power from this board.

## Simulation results and their limits

Ran `simulations/source_load_trade.cir` with ngspice 42. The circuit uses
hypothetical source resistances, fixed input currents and 470 uF effective
capacitance with 30 milliohm ESR:

| Assumed source and load | Before actuator pulse | Minimum |
| --- | --- | --- |
| 5 V BEC, 0.20 ohm, 0.5 A baseline + 3 A pulse | 4.90 V | 4.30 V |
| 3.2 V cell, 0.15 ohm, 0.6 A baseline + 4 A pulse | 3.11 V | 2.51 V |
| Independent 3.2 V avionics cell, 0.15 ohm, 0.6 A | 3.11 V | 3.11 V |

These are **input-bus voltages**, not regulated outputs or measured product
performance. The third case assumes actuators use another energy source.
The shared-cell example drops below TPS2121's recommended operating range.
Fixed-current models omit rising input current from constant-power loads,
protection trips, feedback loops and current limits. The scenarios illustrate
coupling and cannot validate the proposed HV buck, USB path or mux handover.

Reproduce from the project root:

```sh
ngspice -b -o simulations/source_load_trade.log simulations/source_load_trade.cir
```

For sizing context, 3.3 V at 0.5 A needs about 0.61 A from 3 V at assumed
90% efficiency. A 5 V, 2 A servo load alone needs about 3.92 A from 3 V at
assumed 85% efficiency, before additional path losses. A normal step-down
BEC cannot provide 5 V from 1S: that requires a boost-capable supply or
actuators explicitly rated for direct 1S operation.

The shared 3.3 V rail must satisfy every device's tolerance. For RP2354,
QSPI_IOVDD is specified at 2.97–3.63 V, while USB_OTP_VDD and VREG_AVDD
require at least 3.135 V. Use the stricter relevant limits for transient and
supervisor design, and follow the MCU's separate core-power requirements.
[Raspberry Pi datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)

Still needed for component sizing: exact ESC power-pin specification,
servo count/models/stall currents, cell model/protection, external-module
loads, and microSD versus soldered-flash logging. Keep these as trade
variables until selected. Verify logging load steps, startup, all source
handovers, worst-case cell sag, and actuator stalls with real regulator
models where available and then on hardware. The schematic remains pending
those electrical limits; none of the generic simulations proves flight readiness.
