#!/usr/bin/env python3
# SPDX-License-Identifier: 0BSD
# See LICENSES/0BSD.txt at the repository root; provided AS IS.
"""Verify tools/jlc/lcsc_map.csv against JLC's live catalogue and total the board.

For every unique BOM line it re-queries the chosen LCSC number and prints the
library type (Basic / Preferred-extended / Extended), stock, the unit price in
the tier that contains qty 10, the package JLC ships it in, and the joint count
taken from MARV-V2.kicad_pcb. Then it totals: unique lines, unique parts,
Basic/Preferred/Extended counts, the extended-part setup-fee estimate, the
component cost per board at the 10-piece tier, and total joints.

  python3 tools/jlc/audit.py                # table + sums
  python3 tools/jlc/audit.py --md           # markdown table for the report
  python3 tools/jlc/audit.py --refresh      # bypass the response cache

Responses are cached (see jlc_api.py), so a re-run is offline and instant.
"""
import argparse, csv, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import jlc_api                                             # noqa: E402
from bom_lines import JOINTS                               # noqa: E402

EXT_FEE = 3.00          # USD per unique extended part -- ESTIMATE, confirm at quote
QTY_TIER = 10


def lookup(code, refresh=False):
    """Fetch one part by its C-number. The keyword search matches it exactly."""
    for r in jlc_api.search(code, size=10, refresh=refresh):
        if r["lcsc"].upper() == code.upper():
            return r
    return None


def klass(r):
    if r["lib"] == "base":
        return "Basic"
    return "Preferred" if r["preferred"] else "Extended"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--map", default=os.path.join(HERE, "lcsc_map.csv"))
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.map, newline="", encoding="utf-8")))
    out, cache = [], {}
    for m in rows:
        code, qty = m["lcsc"].strip(), int(m["qty"])
        joints = JOINTS.get(m["footprint"], 0) * qty
        rec = None
        if code:
            if code not in cache:
                cache[code] = lookup(code, a.refresh)
            rec = cache[code]
        out.append(dict(m, qty=qty, joints=joints, rec=rec,
                        cls=klass(rec) if rec else "NOT FOUND"))

    dnp = [o for o in out if "DNP" in o["note"] or o["refs"] == "U24"]
    tht = [o for o in out if "UNPOPULATED" in o["note"]]
    fitted = [o for o in out if o not in dnp and o not in tht]

    hdr = ("Refs", "Unique line", "LCSC", "Class", "Stock", "$@10", "Qty", "Joints", "Note")
    if a.md:
        print("| " + " | ".join(hdr) + " |")
        print("|" + "|".join("---" for _ in hdr) + "|")
    for o in out:
        r = o["rec"]
        cells = (o["refs"], f'{o["spec"]} [{o["footprint"].split(":")[-1]}]',
                 o["lcsc"] or "-", o["cls"],
                 f'{r["stock"]:,}' if r else "-",
                 f'{r["price10"]:.4f}' if r and r["price10"] is not None else "-",
                 str(o["qty"]), str(o["joints"]), o["note"])
        if a.md:
            print("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        else:
            print(f'{cells[0][:24]:24} {cells[1][:52]:52} {cells[2]:<11} '
                  f'{cells[3]:<10} {cells[4]:>11} {cells[5]:>8} x{cells[6]:<3} '
                  f'j={cells[7]:<4} {cells[8][:40]}')

    # ---- sums over the parts actually assembled -------------------------------
    parts = {}
    for o in fitted:
        if o["lcsc"]:
            parts.setdefault(o["lcsc"], o["rec"])
    cls = collections.Counter(klass(r) for r in parts.values() if r)
    n_ext = cls["Extended"]
    cost = 0.0
    unpriced = []
    for o in fitted:
        r = o["rec"]
        if r and r["price10"] is not None:
            cost += r["price10"] * o["qty"]
        else:
            unpriced.append(o["refs"])
    joints_fitted = sum(o["joints"] for o in fitted)

    print()
    print(f"unique BOM lines (fitted)        : {len(fitted)}")
    print(f"unique LCSC parts (fitted)       : {len(parts)}"
          f"  [+{len([o for o in fitted if not o['lcsc']])} with no part found]")
    print(f"  Basic                          : {cls['Basic']}")
    print(f"  Preferred extended             : {cls['Preferred']}")
    print(f"  Extended                       : {n_ext}")
    print(f"extended-part setup fee ESTIMATE : {n_ext} x ${EXT_FEE:.2f} = "
          f"${n_ext * EXT_FEE:.2f}   (per-unique-part, Preferred assumed waived)")
    print(f"  worst case if Preferred is not waived: "
          f"${(n_ext + cls['Preferred']) * EXT_FEE:.2f}")
    print(f"component cost per board @10-tier: ${cost:.4f}"
          + (f"   (unpriced: {unpriced})" if unpriced else ""))
    print(f"total solder joints (fitted SMT) : {joints_fitted}")
    print(f"SMT placements per board         : {sum(o['qty'] for o in fitted)}")
    print()
    print(f"excluded: DNP {[o['refs'] for o in dnp]}; "
          f"THT shipped unpopulated {[o['refs'] for o in tht]} "
          f"({sum(o['joints'] for o in tht)} joints if JLC solders them)")
    print("Prices are the JLC catalogue tier containing qty 10 and exclude "
          "JLC's per-part minimum purchase / attrition.")


if __name__ == "__main__":
    main()
