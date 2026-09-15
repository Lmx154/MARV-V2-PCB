# Power partition decision — latest requirements

This decision supersedes the onboard-converter recommendation in
`POWER_ARCHITECTURE_USB_6S.md` and `POWER_TRADE_STUDY.md`. The user wants
interference-heavy components external or explicitly isolated from the
flight-controller sensors, and previously used Schottky source isolation.

## Preferred implementation: separate power module

```text
External power module (switching/high-current area)
  3–6S raw pack -> protected HV buck -> regulated intermediate supply --+
  ESC/external BEC regulated output -> protection ---------------------+
  protected 1S cell --------------------------------------------------+-> source OR
  USB VBUS from main board -> current limit ---------------------------+     |
                                                                          v
                                                               3.3 V buck-boost
                                                                          |
Main controller board                                                     v
  USB-C data -> ESD -> MCU                           regulated 3.3 V input
  USB-C VBUS -> dedicated connection to power module       |
                                            MCU / sensors / logging

Actuator supply / BEC -> external servo distribution
Propulsion battery -> motor ESCs
Controller -> control signals with ground reference -> servos / ESCs
```

The raw-pack buck, 1S buck-boost, source protection and high-current servo
distribution stay off the controller board. The controller still needs local
decoupling, ground planes, interface protection and MCU core-power circuitry
required by its reference design; externalizing main conversion does not
eliminate those requirements or all onboard switching noise.

USB programming and USB power remain supported with the power module
attached: VBUS travels to the module and regulated power returns. USB data
stays on the controller board. **The bare controller board would not operate
from USB alone without that module.** If standalone USB operation is needed,
use an optional local USB buck in a clearly separated power section; this is
an explicit alternative, not part of the external-module baseline. It also
requires coordinated output OR-ing with the external regulated supply.

Provide a ground-referenced power harness with local bulk capacitance and
short supply/return paths. Separate switching inductors/hot loops physically
from IMUs and pressure sensors. Filters need impedance/stability checks;
do not add an undamped LC filter blindly. Do not split ground planes beneath
signals. Actuator return currents must avoid the avionics harness/ground
paths. This is physical and electrical partitioning, not galvanic isolation.

## Schottky source isolation

An OR diode on each input blocks normal reverse current into the other
supplies. It does not guarantee exactly one conducting source: sources with
similar effective voltages may share current. The highest voltage after
diode drop usually dominates. Therefore diode OR-ing is acceptable only if
this natural priority is acceptable. USB and a nominal 5 V BEC have no
guaranteed priority relative to one another.

Put the OR network **before** final 3.3 V regulation. A diode after a nominal
3.3 V supply can pull the MCU rail below specification. Check diode reverse
voltage, leakage, current and hot forward drop, not just nominal values.

Illustrative losses, not a selected-diode model:

- 0.30 V forward drop at 0.60 A dissipates 0.18 W.
- A loaded 3.0 V cell minus 0.30 V leaves 2.70 V before other path losses.
- At 1 A the same assumed drop dissipates 0.30 W.

Choose the final buck-boost and UVLO against the loaded-cell voltage *after*
the diode and harness. If this loses too much usable cell range, use an
ideal-diode circuit on the external module. If exactly one active source or
deterministic priority is required, use a priority mux or exclusive source
selector; ideal-diode OR-ing alone also does not guarantee exclusivity.

Diodes are not substitutes for cell protection, input fusing/current limits,
reverse-polarity protection or a charger. USB must also meet its current and
inrush constraints. Keep actuator power off USB.

## Effect on the BEC trade

For drones, use a verified regulated ESC BEC if adequate, or an external BEC
for a raw 3–6S source. For 1S avionics, use the external buck-boost power
module. For USB, the same module supplies regulated avionics power. The
module can be reusable across configurations; populate its high-voltage
front end only where raw-pack support is needed.

Servo power remains a separate load budget. A 1S source may need a separate
high-current boost for servos. Splitting modules does not prevent voltage
sag if actuators and avionics share the same cell. An independent avionics
cell improves energy-source separation but adds mass, charging and monitoring.

No schematic changes have been made yet. Existing ngspice experiments test
assumed source impedance only; they do not validate diode handover, the
external module, switching interference or the actual voltage at the MCU.
Next circuit-level work should use the selected cell, ESC accessory output,
servo load and logging medium, plus actual diode and converter models.
