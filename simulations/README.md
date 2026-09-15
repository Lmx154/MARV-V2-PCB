# Power simulations

Current integrated design: [DESIGN_SPEC.md](../DESIGN_SPEC.md) (revision P3,
5 V in, low-noise buck + analog LDO). The V3V3_SYS load budget is **500 mA
continuous / 800 mA peak <= 10 ms** (typical ~300 mA), plus <= 50 mA on
V3V3_ANA (modeled at a constant 10 mA); every voltage/load, source-handover
and thermal predicate below is evaluated at that budget. P3 is 5 V-only:
power comes from 5V_IN (J3, an external 2S-6S BEC or 1S BMS/boost module,
0.10 ohm output impedance plus a 3 A current limit) or from USB (J4, a plain
5 V rail through 0.35 ohm cable/connector resistance, no current limit),
ORed onto V5_SYS through two LM66100 paths (U3/U5). U7 TPS62913 bucks
V5_SYS to V3V3_SYS; U12 TPS7A20 is an LDO from V5_SYS to V3V3_ANA. There is
no cell/battery path and no USB current limiter (USB compliance is a
firmware/operational matter, not a modeled part). The P2 buck-boost
(TPS63060) and the P0/P1 raw-pack/cell paths are removed in P3 -- see
DESIGN_SPEC.md's revision history and the `backups/` snapshots for that
history.

Run `python3 tools/run_power_checks.py` from the repository root for a
battery of voltage/load, source-handover and thermal scenarios. See
[RESULTS.md](RESULTS.md) for measured model results and limitations.

`integrated_power.cir` models both sources feeding V5_SYS through the
LM66100 OR-paths, the TPS62913 buck and the TPS7A20 LDO together, with the
500->800->500 mA V3V3_SYS load step and a constant 10 mA V3V3_ANA load. It
is driven by `tools/run_power_checks.py`'s "Integrated source/load model"
corners (nominal, lossy_path, usb_only, bec_only; see RESULTS.md).

`source_handover.cir` is a standalone corner deck isolating the U3/U5
(LM66100) OR-path handover: one source (the SURVIVOR) is present for the
whole run while the other (the OTHER source) is removed from or inserted
into the running V5_SYS at t=15 ms, using the same hysteretic
VON/VOFF/body-diode behavioral model as `integrated_power.cir`. It is
driven by `tools/run_power_checks.py`'s "Source handover with LM66100
thresholds" and "Reverse current into the 5V_IN path" corners (see
RESULTS.md), not by an instantaneous/ideal source switch.

`enclosure_thermal.cir` is a lumped single-node board thermal model driven
by `tools/run_power_checks.py`'s "Enclosure sensitivity" corners, using the
buck+LDO conversion loss measured by `integrated_power.cir` plus the P3
load budget's electronics heat figures.

VSYS bulk in the integrated/handover decks is 2 x 10 uF ceramic (14 uF
derated) plus C19 220 uF polymer with 40 mOhm ESR (176 uF derated).
`run_power_checks.py` always rewrites RESULTS.md (with a `Status:` line)
and exits non-zero if any design predicate is violated.

`rail_load_step.cir` and `source_load_trade.cir` are older, independent
ngspice experiments (a hypothetical 3.3 V distribution rail step, and a
dedicated-vs-shared source/load trade for actuators) kept for reference;
they are not part of the current P3 power model and are not driven by
`run_power_checks.py`. `source_load_trade.cir` in particular still models a
dedicated cell source from an earlier revision.

Manufacturer references for schematic review:

- [RP2350/RP2354 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)
- [BMI088 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi088-ds001.pdf)
- [BMP581 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp581-ds004.pdf)
- [ADXL375 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ADXL375.PDF)
