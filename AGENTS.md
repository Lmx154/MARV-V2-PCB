# MARV V2 working rules

- The owner routes the PCB. Do not route, autoroute, run plane stitching, or
  rebuild/re-place the PCB. Routing and placement scripts have been removed.
- Preserve manual schematic and PCB work. Legacy design generators and one-time
  scripts have been removed; edit the saved design intentionally in KiCad.
- Follow the owner's simple architecture in `DESIGN_SPEC.md`: external 5 V
  conversion, Q1/D1 USB OR, system buck for digital/external IO, separate sensor LDO.
- Do not add circuitry, change GPIOs or resize the board just to improve a
  simulation predicate, sourcing score or placement/routing optimization score.
- The active simulation is input-only: `tools/simulate_power_input.py`.
  Archived documents describe previous designs, not requirements.

---

Original MARV V2 documentation: [CC0 1.0](LICENSES/CC0-1.0.txt). No attribution required; provided as-is. [Licensing and third-party exceptions](LICENSE.md).
