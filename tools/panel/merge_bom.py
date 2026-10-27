#!/usr/bin/env python3
"""Merge BOM lines that share an LCSC part number.

The Fabrication Toolkit groups by Value, and our Values carry per-part notes,
so one LCSC part can appear on many lines. JLCPCB's BOM matcher then leaves the
repeated lines unselected with quantity 0, and those parts are not placed.
This rewrites production/bom.csv (or the given file) with one line per LCSC
part. Lines without an LCSC number are kept as they are.
"""
import csv
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "production/bom.csv"
with open(path, encoding="utf-8-sig", newline="") as fh:
    reader = csv.DictReader(fh)
    fields = reader.fieldnames
    rows = list(reader)

merged, order = {}, []
for row in rows:
    key = row["LCSC Part #"].strip() or ("__none__", row["Designator"])
    if key not in merged:
        merged[key] = {**row, "Designator": [], "Quantity": 0}
        order.append(key)
    entry = merged[key]
    if entry["Footprint"] != row["Footprint"]:
        sys.exit(f"{key}: footprint differs ({entry['Footprint']} vs {row['Footprint']})")
    entry["Designator"] += [d.strip() for d in row["Designator"].split(",")]
    entry["Quantity"] += int(row["Quantity"])

out = []
for key in order:
    entry = merged[key]
    refs = entry["Designator"]
    if len(refs) != entry["Quantity"]:
        sys.exit(f"{key}: {len(refs)} designators but quantity {entry['Quantity']}")
    if sum(1 for r in rows if r["LCSC Part #"].strip() == key) > 1:
        entry["Value"] = entry["Value"].split(",")[0].strip()
    entry["Designator"] = ", ".join(refs)
    out.append(entry)

with open(path, "w", encoding="utf-8-sig", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    writer.writerows(out)
print(f"{path}: {len(rows)} lines -> {len(out)} lines, "
      f"{sum(e['Quantity'] for e in out)} parts")
