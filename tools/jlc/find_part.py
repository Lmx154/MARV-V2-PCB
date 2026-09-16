#!/usr/bin/env python3
"""Parametric candidate finder on top of jlc_api.py.

JLC's keyword search is a loose full-text match over a whole series, so the
results must be filtered on the structured `attributes` block before they mean
anything. This does that and ranks Basic > Preferred-extended > extended, then
by stock.

  python3 tools/jlc/find_part.py --q "2.2nF 0402" --pkg 0402 \
      --attr Capacitance=2.2nF --attr-in "Temperature Coefficient=X7R,X5R" \
      --min-volt 50 --min-stock 1000
"""
import argparse, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jlc_api

MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
        "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "R": 1.0}


def val(s):
    """'4.7uF' / '10kΩ' / '±20%' / '25V' -> float in base units, or None."""
    if not s:
        return None
    s = s.strip().replace("Ω", "").replace("ohm", "").replace("%", "")
    s = s.replace("±", "").replace("V", "").replace("F", "").replace("H", "")
    m = re.match(r"^([0-9.]+)\s*([pnuµμmkKMGR]?)$", s)
    if m:
        return float(m.group(1)) * MULT.get(m.group(2), 1.0)
    m = re.match(r"^([0-9]*)([pnuµμmkKMGR])([0-9]+)$", s)      # 4u7 / 1R5
    if m:
        return float(f"{m.group(1) or 0}.{m.group(3)}") * MULT[m.group(2)]
    try:
        return float(s)
    except ValueError:
        return None


def close(a, b, rel=0.02):
    return a is not None and b is not None and abs(a - b) <= rel * max(abs(b), 1e-18)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--q", required=True, action="append", help="keyword (repeatable)")
    p.add_argument("--pkg", action="append", default=[], help="allowed package string")
    p.add_argument("--attr", action="append", default=[], help="Name=exact value")
    p.add_argument("--attr-val", action="append", default=[],
                   help="Name=value, compared numerically (2% tolerance)")
    p.add_argument("--attr-in", action="append", default=[],
                   help="Name=v1,v2 (any of)")
    p.add_argument("--min-volt", type=float, default=None,
                   help="'Voltage Rating' >= this many volts")
    p.add_argument("--max-tol", type=float, default=None,
                   help="'Tolerance' <= this percent")
    p.add_argument("--desc-re", default=None)
    p.add_argument("--min-stock", type=int, default=0)
    p.add_argument("--pages", type=int, default=4)
    p.add_argument("--size", type=int, default=50)
    p.add_argument("--all-libs", action="store_true",
                   help="also query the unfiltered library (default: base+pref+expand)")
    p.add_argument("--limit", type=int, default=10)
    a = p.parse_args()

    seen, cands = set(), []
    plans = [("base", None), (None, True), (None, None)]
    for kw in a.q:
        for lt, pref in plans:
            try:
                for r in jlc_api.search(kw, library_type=lt, preferred=pref,
                                        pages=a.pages, size=a.size):
                    if r["lcsc"] not in seen:
                        seen.add(r["lcsc"])
                        cands.append(r)
            except Exception as e:                               # noqa: BLE001
                print(f"! {kw} {lt} {pref}: {e}", file=sys.stderr)

    def keep(r):
        if r["stock"] < a.min_stock:
            return False
        if a.pkg and r["pkg"].lower() not in [x.lower() for x in a.pkg]:
            return False
        at = r["attrs"]
        for spec in a.attr:
            k, v = spec.split("=", 1)
            if at.get(k, "").strip().lower() != v.strip().lower():
                return False
        for spec in a.attr_val:
            k, v = spec.split("=", 1)
            if not close(val(at.get(k)), val(v)):
                return False
        for spec in a.attr_in:
            k, vs = spec.split("=", 1)
            if at.get(k, "").strip().lower() not in [x.strip().lower()
                                                     for x in vs.split(",")]:
                return False
        if a.min_volt is not None:
            v = val(at.get("Voltage Rating") or at.get("Voltage-Supply(Max)"))
            if v is None or v < a.min_volt - 1e-9:
                return False
        if a.max_tol is not None:
            t = val(at.get("Tolerance"))
            if t is None or t > a.max_tol + 1e-9:
                return False
        if a.desc_re and not re.search(a.desc_re, r["desc"], re.I):
            return False
        return True

    res = [r for r in cands if keep(r)]
    res.sort(key=lambda r: (r["lib"] != "base", not r["preferred"], -r["stock"]))
    print(f"# {len(cands)} fetched, {len(res)} pass", file=sys.stderr)
    for r in res[:a.limit]:
        flag = "BASIC" if r["lib"] == "base" else ("PREF" if r["preferred"] else "ext")
        pr = f"{r['price10']:.4f}" if r["price10"] is not None else "  -   "
        print(f"{r['lcsc']:<11} {flag:<5} {r['stock']:>9} {pr:>8} {r['pkg'][:12]:<12} "
              f"{r['mfr'][:24]:<24} {r['desc'][:56]}")


if __name__ == "__main__":
    main()
