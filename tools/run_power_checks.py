#!/usr/bin/env python3
"""Run reproducible architectural SPICE corners for the CURRENT power tree only.

The pre-2026-09-17 power tree (on-board AP63205 pack buck -> U25 TPS2121
priority mux -> U7 TPS62913 two-stage 3.3 V buck) was replaced by an external
BEC -> Q1 AO3401A / D1 1N5819WS P-FET+Schottky OR -> fixed AP63203WU-7 3.3 V
buck (DESIGN_SPEC.md "Decisions", 2026-09-17). The decks that modeled the
removed tree were RETIRED, not re-derived, per the lead's decision:
simulations/superseded/ (integrated_power.cir, source_handover.cir,
enclosure_thermal.cir, and their generated corners/). Nothing in this script
runs those decks any more, so a stale PASS can no longer be reported for a
power tree the board does not have.

Re-deriving decks for the BEC + Q1/D1 + AP63203 tree is separate, undecided
work -- see DESIGN_SPEC.md "Open items". LIVE_DECKS below is where such decks
would be registered; it is empty today, so this script has nothing to run.
"""
import sys
from pathlib import Path
from build_power import patch_files

ROOT = Path(__file__).resolve().parents[1]
SUPERSEDED_DIR = ROOT / 'simulations' / 'superseded'
SUPERSEDED_DECKS = ['integrated_power.cir', 'source_handover.cir', 'enclosure_thermal.cir']

# Decks that model the CURRENT power tree (external BEC -> Q1/D1 OR ->
# AP63203) and that this script should run. Empty: none have been written
# yet. Do not add entries here without also writing and validating the deck;
# retiring the superseded decks is not the same as re-deriving them.
LIVE_DECKS = []

RESULTS_HEADER = '# MARV V2 power simulation results\n\n'


def retired_results_text(n_superseded):
    return (RESULTS_HEADER +
      f"RETIRED: {n_superseded} decks modeled the superseded pack-buck/mux/TPS62913 power tree "
      "and have been moved to `simulations/superseded/` (with their generated `corners/`); "
      "no active power-stage decks remain.\n\n"
      "The 2026-09-17 BEC revision ([DESIGN_SPEC.md \"Decisions\"](../DESIGN_SPEC.md#decisions)) "
      "replaced the on-board AP63205 pack buck, the U25 TPS2121 priority mux and the U7 TPS62913 "
      "second-stage buck with an external BEC feeding a Q1 AO3401A / D1 1N5819WS P-FET+Schottky OR "
      "into a fixed AP63203WU-7 3.3 V buck. Nothing in the retired decks models that architecture, "
      "so `run_power_checks.py` no longer runs them rather than reporting a stale `Status: PASS`. "
      "Re-deriving decks for the current tree is separate, undecided work -- see DESIGN_SPEC.md "
      "\"Open items\".\n\n"
      "Run `python3 tools/run_power_checks.py` to regenerate this file.\n")


def main():
    n_superseded = sum(1 for d in SUPERSEDED_DECKS if (SUPERSEDED_DIR / d).exists())

    if not LIVE_DECKS:
        status = (f"RETIRED: {n_superseded} decks model the superseded pack-buck/mux/TPS62913 tree "
          "(simulations/superseded/); no active power-stage decks")
        print(status)
        patch_files({'simulations/RESULTS.md': retired_results_text(n_superseded)})
        sys.exit(0)

    # No live decks exist today (see module docstring); this branch is
    # intentionally unreachable until decks are added to LIVE_DECKS.
    print('ERROR: LIVE_DECKS is non-empty but no runner is implemented for it', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    main()
