# MARV V2 power simulation results

RETIRED: 3 decks modeled the superseded pack-buck/mux/TPS62913 power tree and have been moved to `simulations/superseded/` (with their generated `corners/`); no active power-stage decks remain.

The 2026-09-17 BEC revision ([DESIGN_SPEC.md "Decisions"](../DESIGN_SPEC.md#decisions)) replaced the on-board AP63205 pack buck, the U25 TPS2121 priority mux and the U7 TPS62913 second-stage buck with an external BEC feeding a Q1 AO3401A / D1 1N5819WS P-FET+Schottky OR into a fixed AP63203WU-7 3.3 V buck. Nothing in the retired decks models that architecture, so `run_power_checks.py` no longer runs them rather than reporting a stale `Status: PASS`. Re-deriving decks for the current tree is separate, undecided work -- see DESIGN_SPEC.md "Open items".

Run `python3 tools/run_power_checks.py` to regenerate this file.
