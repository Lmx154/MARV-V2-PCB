#!/usr/bin/env python3
"""Group power_bom.csv into unique purchase lines keyed by (spec, footprint).

The Value column carries "<electrical spec>, <positional comment>"; only the part
before the first comma is electrically meaningful, so that is the grouping key.
Mechanical-only refs (H*, TP*) and the DNP socket are split out.
Run:  python3 tools/jlc/bom_lines.py [--json OUT]
"""
import csv, json, re, sys, os, collections

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOM = os.path.join(ROOT, "power_bom.csv")

# joints = physical numbered solder pads, measured from MARV-V2.kicad_pcb
JOINTS = {
    "Button_Switch_SMD:SW_SPST_B3U-1000P": 2,
    "Capacitor_SMD:C_0402_1005Metric": 2,
    "Capacitor_SMD:C_0603_1608Metric": 2,
    "Capacitor_SMD:C_0805_2012Metric": 2,
    "Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B": 2,
    "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm": 4,
    "Inductor_SMD:L_0603_1608Metric": 2,
    "Inductor_SMD:L_Changjiang_FTC303020D": 2,
    "Inductor_SMD:L_Changjiang_FTC404030S": 2,
    "Inductor_SMD:L_Murata_DFE201610P": 2,
    "LED_SMD:LED_0603_1608Metric": 2,
    "MARV_Packages:Analog_LGA-14_3x5mm_P0.8mm_ADXL375": 14,
    "MARV_Packages:Bosch_LGA-10_2x2mm_BMP581": 10,
    "MARV_Packages:InvenSense_LGA-14_2.5x3mm_P0.5mm_ICM45686": 14,
    "MARV_Packages:LED_WS2812B-2020_PLCC4_2.0x2.0mm": 4,
    "MARV_Packages:MountingHole_4.0mm_Grommet_Pad_Via": 0,
    "Diode_SMD:D_SOD-323": 2,
    "MARV_Packages:PadRow_1x03_P2.00mm": 0,
    "MARV_Packages:PadRow_1x09_P2.00mm": 0,
    "MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow": 14,
    "MARV_Packages:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm": 81,
    "MARV_Packages:Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm": 10,
    "MARV_Packages:Texas_VQFN-HR-12_2x2.5mm_P0.5mm": 12,
    "MARV_Packages:USB_C_Receptacle_HRO_TYPE-C-31-M-12": 20,
    "MARV_Packages:microSD_HC_Molex_104031-0811": 14,
    "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm": 8,
    "Package_TO_SOT_SMD:SOT-23": 3,
    "Package_TO_SOT_SMD:SOT-23-5": 5,
    "Package_TO_SOT_SMD:SOT-23-6": 6,
    "Package_TO_SOT_SMD:TSOT-23-6": 6,
    "Resistor_SMD:R_0402_1005Metric": 2,
    "TestPoint:TestPoint_Pad_1.0x1.0mm": 0,
}

# refs that are board features, not purchased parts
NOT_PURCHASED_PREFIX = ("H", "TP")
NOT_PURCHASED_FP = {
    "MARV_Packages:MountingHole_4.0mm_Grommet_Pad_Via",
    "MARV_Packages:PadRow_1x03_P2.00mm",
    "MARV_Packages:PadRow_1x09_P2.00mm",
    "TestPoint:TestPoint_Pad_1.0x1.0mm",
}


def spec_of(value: str) -> str:
    """Electrical spec = the Value string up to the first comma."""
    return value.split(",", 1)[0].strip()


def refkey(r):
    m = re.match(r"([A-Za-z]+)(\d+)", r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


def load():
    with open(BOM, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group(rows):
    lines = collections.OrderedDict()
    for r in rows:
        key = (spec_of(r["Value"]), r["Footprint"])
        e = lines.setdefault(key, dict(
            spec=key[0], footprint=key[1], refs=[], qty=0, sheets=set(),
            fit=r["Fit"], joints_each=JOINTS.get(key[1], 0),
            purchased=not (r["Reference"][0:2].rstrip("0123456789") in NOT_PURCHASED_PREFIX
                           or key[1] in NOT_PURCHASED_FP),
        ))
        e["refs"].append(r["Reference"])
        e["qty"] += 1
        e["sheets"].add(r["Sheet"])
        if r["Fit"] == "DNP":
            e["fit"] = "DNP"
    for e in lines.values():
        e["refs"].sort(key=refkey)
        e["sheets"] = sorted(e["sheets"])
        e["joints_total"] = e["joints_each"] * e["qty"]
    return lines


def main():
    rows = load()
    lines = group(rows)
    purch = [e for e in lines.values() if e["purchased"] and e["fit"] != "DNP"]
    dnp = [e for e in lines.values() if e["fit"] == "DNP"]
    mech = [e for e in lines.values() if not e["purchased"]]
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(list(lines.values()), open(out, "w"), indent=1)
        print("wrote", out)
    print(f"BOM rows: {len(rows)}")
    print(f"unique purchased lines : {len(purch)}  (qty {sum(e['qty'] for e in purch)}, "
          f"joints {sum(e['joints_total'] for e in purch)})")
    print(f"unique DNP lines       : {len(dnp)}  -> {[e['refs'] for e in dnp]}")
    print(f"board-feature lines    : {len(mech)}  (no part bought)")
    print()
    for e in sorted(purch, key=lambda e: (e["footprint"], e["spec"])):
        print(f"{e['qty']:>3}x {e['spec'][:58]:58} | {e['footprint'][:48]:48} "
              f"| j={e['joints_total']:<4} {','.join(e['refs'])[:40]}")
    print("\n-- board features / DNP --")
    for e in mech + dnp:
        print(f"{e['qty']:>3}x {e['spec'][:58]:58} | {e['footprint'][:48]:48} | {e['fit']}")


if __name__ == "__main__":
    main()
