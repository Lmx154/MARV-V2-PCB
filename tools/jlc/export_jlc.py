#!/usr/bin/env python3
"""Produce the two files JLCPCB's assembly order form asks for:

  build/assembly/jlc-bom.csv   Comment, Designator, Footprint, LCSC Part #
  build/assembly/jlc-cpl.csv   Designator, Mid X, Mid Y, Layer, Rotation

BOM comes from power_bom.csv grouped by (electrical spec, footprint) -- the same
grouping tools/jlc/bom_lines.py uses -- and the LCSC part number comes from the
SCHEMATIC: each selected part has an "LCSC" symbol property. KiCad CLI exports
it into build/checks/netlist.xml, and this tool reads it there.  The map is only a fallback for when the netlist is
missing or predates the property, so the numbers that get ordered are the numbers
that are in the schematic, not a second opinion derived from a value string.

Any fitted line with no LCSC part is a hard error (exit 1), reported after
writing the export files; the only permitted exceptions are the three THT
headers J6/J7/J8, which the audit ships unpopulated, and U24, which is DNP.

CPL comes from MARV-V2.kicad_pcb via pcbnew: footprint centre, orientation and
layer, in millimetres relative to the board's drill/place (aux) origin with Y
pointing up, which is the convention KiCad's own position-file export uses and
the one JLC expects.

Excluded from both: the DNP socket U24, the bare-pad pseudo-footprints (J3, J10,
TP1-TP10), the mounting holes H1-H4, and -- unless --with-tht is given -- the
2.54 mm THT headers J6/J7/J8, which the audit recommends shipping unpopulated.

  python3 tools/jlc/export_jlc.py
  python3 tools/jlc/export_jlc.py --with-tht --outdir build/assembly

ROTATION IS NOT VERIFIED. JLC's zero-degree reference for a given package is not
always KiCad's; every rotation this writes must be checked against JLC's own
preview before the order is placed. See README.md (component sourcing section).
"""
import argparse, csv, os, sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from bom_lines import load, group, spec_of          # noqa: E402

PCB = os.path.join(ROOT, "MARV-V2.kicad_pcb")
LCSC_MAP = os.path.join(HERE, "lcsc_map.csv")
NETLIST = os.path.join(ROOT, "build", "checks", "netlist.xml")

# Fitted lines that are allowed to ship without an LCSC part number.  J6/J7/J8
# are through-hole and the audit recommends ordering them unpopulated; U24 is
# DNP (and is filtered out before this ever applies).  Nothing else qualifies.
NO_PART_OK = {"J6", "J7", "J8", "U24"}

# pseudo-footprints: board features, nothing is placed on them
NO_PART_FP = {
    "MARV_Packages:MountingHole_4.0mm_Grommet_Pad_Via",
    "MARV_Packages:PadRow_1x03_P2.00mm",
    "MARV_Packages:PadRow_1x09_P2.00mm",
    "TestPoint:TestPoint_Pad_1.0x1.0mm",
}
THT_FP = {"MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow"}


def read_map():
    if not os.path.exists(LCSC_MAP):
        sys.exit(f"missing {LCSC_MAP} -- see README.md (component sourcing section)")
    m = {}
    with open(LCSC_MAP, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("spec", "").startswith("#"):
                continue
            m[(r["spec"].strip(), r["footprint"].strip())] = r
    return m


def read_netlist_lcsc(path):
    """{ref: LCSC} from the hidden "LCSC" symbol property in the kicadxml netlist."""
    if not os.path.exists(path):
        return None
    out = {}
    for comp in ET.parse(path).getroot().find("components"):
        for prop in comp.findall("property"):
            if prop.get("name") == "LCSC" and (prop.get("value") or "").strip():
                out[comp.get("ref")] = prop.get("value").strip()
    return out


def write_bom(path, with_tht, netlist=NETLIST):
    lines = group(load())
    lut = read_map()
    net = read_netlist_lcsc(netlist)
    rows, missing, notes = [], [], []
    if net is None:
        notes.append(f"! {netlist} not found -- LCSC numbers taken from the map only; "
                     f"re-run kicad-cli sch export netlist to use the schematic's own")
    for (spec, fp), e in lines.items():
        if fp in NO_PART_FP or e["fit"] == "DNP":
            continue
        if fp in THT_FP and not with_tht:
            continue
        hit = lut.get((spec, fp)) or {}
        fallback = (hit.get("lcsc") or "").strip()
        # one BOM row per distinct part number, so a ref_override in the map
        # genuinely splits a line instead of silently ordering the wrong part
        by_code = {}
        for ref in e["refs"]:
            code = (net or {}).get(ref, fallback) if net is not None else fallback
            by_code.setdefault(code, []).append(ref)
        if len(by_code) > 1:
            notes.append(f"  split ({spec!r}, {fp.split(':')[-1]}) across "
                         + ", ".join(f"{c or '<none>'}={'+'.join(r)}" for c, r in by_code.items()))
        for code, refs in by_code.items():
            if not code:
                missing.append((spec, fp, ",".join(refs)))
                continue
            rows.append({
                "Comment": hit.get("comment") or spec,
                "Designator": ",".join(refs),
                "Footprint": hit.get("jlc_package") or fp.split(":", 1)[-1],
                "LCSC Part #": code,
            })
    rows.sort(key=lambda r: r["Designator"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["Comment", "Designator", "Footprint", "LCSC Part #"])
        w.writeheader()
        w.writerows(rows)
    return rows, missing, notes


def write_cpl(path, with_tht):
    import pcbnew
    b = pcbnew.LoadBoard(PCB)
    aux = b.GetDesignSettings().GetAuxOrigin()
    ox, oy = pcbnew.ToMM(aux.x), pcbnew.ToMM(aux.y)
    rows, skipped = [], []
    for fp in b.GetFootprints():
        ref, fid = fp.GetReference(), fp.GetFPIDAsString()
        why = None
        if fp.IsDNP():
            why = "DNP"
        elif fid in NO_PART_FP:
            why = "board feature (bare pad / hole)"
        elif fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES:
            why = "exclude_from_pos"
        elif fp.IsFlipped() or fp.GetLayerName() != "F.Cu":
            why = "not on F.Cu (single-sided assembly)"
        elif fid in THT_FP and not with_tht:
            why = "THT header, shipped unpopulated"
        if why:
            skipped.append((ref, why))
            continue
        p = fp.GetPosition()
        rows.append({
            "Designator": ref,
            "Mid X": f"{pcbnew.ToMM(p.x) - ox:.4f}",
            "Mid Y": f"{-(pcbnew.ToMM(p.y) - oy):.4f}",
            "Layer": "Bottom" if fp.IsFlipped() else "Top",
            "Rotation": f"{fp.GetOrientationDegrees() % 360:.2f}",
        })
    rows.sort(key=lambda r: r["Designator"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writeheader()
        w.writerows(rows)
    return rows, skipped, (ox, oy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join(ROOT, "build", "assembly"))
    ap.add_argument("--with-tht", action="store_true",
                    help="include J6/J7/J8 (only if JLC is to solder them)")
    ap.add_argument("--netlist", default=NETLIST,
                    help="kicadxml netlist carrying the LCSC symbol property")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    bp = os.path.join(a.outdir, "jlc-bom.csv")
    cp = os.path.join(a.outdir, "jlc-cpl.csv")

    brows, missing, notes = write_bom(bp, a.with_tht, a.netlist)
    print(f"{bp}: {len(brows)} BOM lines, "
          f"{sum(len(r['Designator'].split(',')) for r in brows)} placements")
    for n in notes:
        print(n)
    fatal = []
    for s, fp, refs in missing:
        bad = [r for r in refs.split(",") if r not in NO_PART_OK]
        print(f"  {'!' if bad else '-'} no LCSC part for ({s!r}, {fp}) -> {refs}"
              + ("" if bad else "   [permitted: THT / DNP]"))
        fatal += bad

    crows, skipped, origin = write_cpl(cp, a.with_tht)
    print(f"{cp}: {len(crows)} placements, origin = drill/place origin "
          f"at board mm ({origin[0]}, {origin[1]}), Y up")
    for ref, why in sorted(skipped):
        print(f"  - skipped {ref}: {why}")

    bset = {d for r in brows for d in r["Designator"].split(",")}
    cset = {r["Designator"] for r in crows}
    if bset != cset:
        print(f"  ! BOM-only designators: {sorted(bset - cset)}")
        print(f"  ! CPL-only designators: {sorted(cset - bset)}")
    print("\nROTATION UNVERIFIED: check every angle in JLC's assembly preview.")
    if fatal:
        sys.exit(f"FAILED: {len(fatal)} fitted part(s) have no LCSC number: "
                 f"{sorted(set(fatal))}. Update the schematic LCSC properties and "
                 f"tools/jlc/lcsc_map.csv, export a fresh schematic XML netlist, "
                 f"then rerun this exporter.")


if __name__ == "__main__":
    main()
