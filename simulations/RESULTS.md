# Input-power simulation results

Generated from the saved schematic by `python3 tools/simulate_power_input.py`.

External source 5 V / assumed 0.05 ohm; USB 5 V / assumed 0.35 ohm. Combined V5_SYS load 0.5 A; extra external 5 V load 0 A.

The external source represents either the 2S–6S buck or the 1S boost **at its 5 V output**. The source converter itself is not simulated. Loads start at 2 ms; source events at 8 ms.

| Case | Before (V) | Event min–max (V) | Final (V) | External / USB final (A) |
| --- | ---: | ---: | ---: | ---: |
| External 5 V only | 4.952 | 4.952–4.952 | 4.952 | 0.500 / 0.000 |
| USB only | 4.315 | 4.315–4.315 | 4.315 | 0.000 / 0.502 |
| Both connected | 4.352 | 4.352–4.352 | 4.352 | 0.065 / 0.437 |
| USB plugged in; external stays | 4.952 | 4.352–4.952 | 4.352 | 0.065 / 0.437 |
| USB unplugged; external stays | 4.352 | 4.269–4.940 | 4.946 | 0.500 / 0.000 |
| External unplugged; USB stays | 4.352 | 4.315–4.352 | 4.315 | 0.000 / 0.502 |
| External only; 0.1 A to chosen load | 4.990 | 4.952–4.990 | 4.952 | 0.500 / 0.000 |

Lowest measured voltage in the event windows: **4.269 V**. AP63203 specified input minimum: **3.8 V**; margin **0.469 V**. This checks input availability, not the actual 3.3 V outputs.

| Case | External 5V_IN min / final (V) | Peak reverse into USB node (mA) | Peak reverse toward external input (mA) | Q1 / D1 final loss (W) |
| --- | ---: | ---: | ---: | ---: |
| External 5 V only | 4.974 / 4.974 | 0.0053 | 0.0000 | 0.0112 / 0.0000 |
| USB only | 0.000 / 0.000 | 0.0000 | 0.0000 | 0.0000 / 0.2544 |
| Both connected | 4.997 / 4.997 | 0.0000 | 0.0000 | 0.0421 / 0.2151 |
| USB plugged in; external stays | 4.974 / 4.997 | 0.0053 | 0.0000 | 0.0421 / 0.2151 |
| USB unplugged; external stays | 4.973 / 4.974 | 0.0057 | 0.0000 | 0.0141 / 0.0000 |
| External unplugged; USB stays | 4.841 / 4.813 | 0.0000 | 0.0000 | 0.0001 / 0.2542 |
| External only; 0.1 A to chosen load | 4.974 / 4.974 | 0.0053 | 0.0000 | 0.0112 / 0.0000 |

Reverse-current peaks include connection transients; they are not USB compliance limits. Losses are electrical model estimates, not temperatures.

USB drives Q1’s gate. With USB present, do not assume the low-resistance BEC path wins: D1 and Q1’s body diode can share the load. Unplugging USB lets the Q1 channel turn on.

**Limits:** vendor Q1 model; fitted D1 forward curve; approximate white LED; nominal capacitors. No regulator control loops, source current limits, battery chemistry, charging, converter cutoff, USB negotiation, PCB parasitics, noise or thermal simulation. D1 leakage at temperature is not bounded. The default 0.5 A is an explicit input-load assumption, not a measured board budget.

Exact decks, waveforms, logs and exported netlist: `/tmp/marv-input-power-qkgsqbbq`.

---

Original MARV V2 documentation: [CC0 1.0](../LICENSES/CC0-1.0.txt). No attribution required; provided as-is. [Licensing and third-party exceptions](../LICENSE.md).
