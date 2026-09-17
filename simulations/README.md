# Input-power simulation

Run `python3 tools/simulate_power_input.py` from the project root. Results are in
[RESULTS.md](RESULTS.md). Requires Python, KiCad CLI and ngspice; no Python packages.

The boundary is external regulated 5 V plus USB, through Q1/D1, to V5_SYS.
External power is either a 2S–6S-to-5 V, 3 A buck or a 1S-18650-to-5 V boost.
Both converters live off-board. Neither raw battery voltage nor charging enters this model.

One deck, [power_input.cir](power_input.cir), runs seven cases: external only,
USB only, both present, USB insertion, USB removal, external removal, and an
external-powered load step. It checks the saved schematic's key power connections
before running. Downstream electronics are one explicit current demand at V5_SYS;
the simulation does not implement fictional buck or LDO control loops.

Default demand is **0.5 A at V5_SYS**, an assumption that can be changed:

```sh
python3 tools/simulate_power_input.py --load 0.3
python3 tools/simulate_power_input.py --load 0.5 --external-load 1.0
python3 tools/simulate_power_input.py --usb-voltage 4.75
```

`--external-load` is additional servo demand on 5V_IN, before the OR.
The external source's 3 A rating is its capacity, not the board's assumed draw.
Source resistances are explicitly assumed: external 0.05 ohm, USB 0.35 ohm.
The external boost's output rating and both converters' transient behavior need
actual module specifications or measurements; cell current ratings do not supply those.

The report shows V5_SYS voltage and source/reverse currents. The 3.8 V comparison
is the AP63203's specified minimum input, not a pass/fail test for the whole board.
Exit 1 means a simulated event falls below that input range. Solver/check errors
also fail the command. Exact generated decks, logs and waveform tables stay in a
printed temporary directory; they do not multiply tracked project files.

Q1 uses the existing AOS model. D1 uses the existing hand-fitted forward curve;
its temperature-dependent leakage is not bounded. Capacitors are nominal and the
white LED curve is approximate. Source current limiting, charging, cell cutoff,
USB negotiation, regulator outputs, noise, layout and thermal behavior are outside scope.
In particular, this simulation cannot decide whether sensor supplies need an LDO.

Previous simulation documentation and result summaries remain in
`backups/pre-input-power-refresh/simulations/` as historical records. Obsolete
runners, decks, model copies and generated logs have been removed.
