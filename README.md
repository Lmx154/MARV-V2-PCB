# MARV V2 robotics controller

Open **MARV-V2.kicad_pro** in KiCad 10. The first power-system draft is now
connected through seven hierarchical sheets: 5 V-in/USB source OR-ing,
TPS62913 low-noise 3.3 V buck + TPS7A20 analog LDO, generic GPS/ELRS/mag
ports, RP2354B MCU, sensors (BMI088/BMP581/ADXL375), log flash + latched
microSD, and eight PWM outputs.
Power is 5 V only: an external 2S–6S BEC or a 1S BMS/boost module, or USB.
MCU is RP2354B; V3V3_SYS budget 500 mA continuous / 800 mA peak. Firmware and PCB layout are
still to be done; the PCB is empty.

- [Current specification](DESIGN_SPEC.md): 5 V-in power, low-noise system buck plus
  analog LDO, load budget, ports and known behaviours.
- [Power schematic PDF](reports/MARV-V2-power.pdf).
- [Simulation results and limitations](simulations/RESULTS.md). Its `Status:` line is the pass/fail summary; `run_power_checks.py` exits non-zero on any violated predicate.
- [Preliminary BOM](power_bom.csv): not a purchase-ready component list.
- [ERC report](reports/power-erc.rpt).

The older POWER_*.md documents are trade-study history, superseded by the
current specification. The original empty root schematic is backed up in
`backups/MARV-V2.before-power.kicad_sch`.

## Reproduce checks

```sh
kicad-cli sch erc MARV-V2.kicad_sch --exit-code-violations -o reports/power-erc.rpt
kicad-cli sch export netlist MARV-V2.kicad_sch --format kicadxml -o reports/power-netlist.xml
python3 tools/check_power_netlist.py reports/power-netlist.xml
python3 tools/run_power_checks.py
kicad-cli sch export pdf MARV-V2.kicad_sch -o reports/MARV-V2-power.pdf
```

`python3 tools/build_power.py` regenerates power sheets using installed KiCad
symbols and local pin definitions. It overwrites generated sheets: preserve
manual edits first. Python tools use the standard library; ngspice and
kicad-cli must be installed.

The models are architectural and generic switching experiments, not vendor
regulator macromodels. Their results do not establish loop stability, USB
compliance, thermal performance or flight readiness. See the spec's open
integration and hardware-validation gates.
