# MARV V2 Rev 1: JLCPCB order record

This folder records exactly how Rev 1 was ordered from JLCPCB: the files
that were uploaded and every PCB and PCBA option that was selected. The
settings below are transcribed from the owner's JLCPCB order page and are
authoritative for Rev 1. If they conflict with the general ordering notes in
the top-level [README](../../README.md#ordering), follow this record.

**To reorder Rev 1, upload the archived files in this folder and set every
option exactly as listed below. Do not regenerate the files.**

## Files

| File | Use |
| --- | --- |
| `MARV-V2-panel.zip` | PCB fabrication upload: Gerbers and drills for the 72 × 72 mm frame with the board inside it |
| `bom.csv` | PCBA "Bill of Materials" upload (Fabrication Toolkit export) |
| `positions.csv` | PCBA "Pick and Place / CPL" upload (Fabrication Toolkit export) |
| `SHA256SUMS` | Checksums of the three upload files |
| `order-manifest.json` | Export record: KiCad 10.0.7, Fabrication Toolkit options, SHA-256 of every source design file, DRC/ERC counts |
| `jlc-order-bom.xls` | JLCPCB's BOM as ordered, downloaded from the order (original file) |
| `jlc-order-bom.csv` | The same BOM converted to CSV: part matched to each line, quantity bought and price |

Check the upload files before using them:

```sh
cd orders/rev1 && sha256sum -c SHA256SUMS
```

The SHA-256 values in `order-manifest.json` (`source_sha256`,
`panel_source_sha256`) match the committed KiCad design files of this
revision, except the per-user `.kicad_prl` files, which are not tracked.

## PCB options (Product Detail, as shown on the order page)

| Option | Value |
| --- | --- |
| Gerber file | MARV-V2-panel_Y12 (JLC's name for the uploaded `MARV-V2-panel.zip`) |
| Build Time | 3 days (PCBA Only) |
| Base Material | FR-4 |
| Layers | 4 |
| Dimension | 72 mm × 72 mm |
| PCB Qty | 5 |
| Product Type | Industrial/Consumer electronics |
| Different Design | 1 |
| Delivery Format | Panel by Customer |
| Panel Format | Column:1 × Row:1 |
| PCB Thickness | 1.6mm |
| Specify Stackup | no No requirement |
| Layer Sequence | (blank) |
| PCB Color | Green |
| Silkscreen | White |
| Material Type | FR4 TG135 |
| Via Covering | Plugged |
| Surface Finish | ENIG, Gold Thickness: 1U" |
| Deburring/Edge rounding | No |
| Outer Copper Weight | 1 oz |
| Inner Copper Weight | 0.5 oz |
| Gold Fingers | No |
| Electrical Test | Flying Probe Fully Test |
| Castellated Holes | no |
| Press-Fit Hole | No |
| Edge Plating | No |
| Mark on PCB | Remove Mark |
| Blind Slot | No |
| Min via hole size/diameter | 0.3mm/(0.4/0.45mm) |
| Via Plating Method | Not Specified |
| 4-Wire Kelvin Test | No |
| Paper between PCBs | No |
| Appearance Quality | IPC Class 2 Standard |
| Confirm Production file | Yes |
| Silkscreen Technology | Ink-jet Printing Silkscreen |
| X-out board | Accept |
| Package Box | With JLCPCB logo |
| Inspection Report | No |
| Board Outline Tolerance | ±0.2mm(Regular) |
| Impedance Test Report | No |
| UL Marking | No |
| Countersink Hole | No |
| Backdrill | No |
| Shortage Preference | Require Full Quantity |
| Weight (JLC estimate) | 0.34kg |

## PCBA options (PCBA Parameters, as shown on the order page)

| Option | Value |
| --- | --- |
| PCBA Type | Standard |
| Assembly Side | Top Side |
| PCBA Qty | 2 |
| Edge Rails/Fiducials | Added by Customer |
| Confirm Parts Placement | Yes |
| Bake Components | Yes. Remark: "Bake Components" |
| Photo Confirmation | No |
| Board Cleaning | No |
| Conformal Coating (cleaning included) | No |
| Packaging | Antistatic bubble film |
| Special stencil | No |
| Depanel boards & edge rail before delivery | No |
| Solder Paste | High temp. |
| Flying Probe Test | No |
| Nitrogen reflow soldering | No |
| Function test | No |
| Assembly remark | Yes. Remark: "X1, Y1 orientation check please. inductor pins n…" (cut off on the order page; full text not recorded) |
| File provided as | Complete File, just proceed with my own files |
| Panel Format | 1 × 1 |
| Build Time | 6 - 7 days (add 2 days) |
| Stencil Storage | No |
| Fixture Storage | No |
| Product Description | Reserch\Education\DIY\Entertainment/Development Board - HS Code 847330 (JLC's own spelling) |
| Weight (JLC estimate) | 0.15kg |

## Parts as ordered

`jlc-order-bom.csv` holds JLC's 34 matched lines. Each line's designators
and JLCPCB part number are identical to `bom.csv`, so no part was
substituted at ordering. `Qty` is the quantity JLC bought for the two
assembled boards, including its attrition and minimums; `Ext.Price($)` is
that line's parts cost. Parts total: **$66.51**. This excludes PCB,
assembly, setup and shipping charges.

- **U20 RP2354B (C39843328) is listed at $0.00.** That suggests the part
  came from the owner's JLC parts inventory (the order's "My Inventory
  Usage" tab), but this record does not confirm it. On a reorder, check
  that inventory covers U20 or buy it.
- **J17** (5 V converter header) is in `bom.csv` without an LCSC number
  and is not in `positions.csv`. Leave it unselected; it is hand-fitted.
- Not assembled by JLC (excluded from both CSVs): J3 ESC pad row,
  J6–J8 and J10 headers (hand-soldered by the owner), H1–H4 mounting holes,
  and U24 (optional QSPI memory, DNP).

The result is 90 top-side placements using 34 distinct LCSC parts per
board.

## Placement review

"Confirm Parts Placement" was Yes. In JLC's placement preview, check:

- X1 (1521H-32K000J18DTSL 32 kHz oscillator) and Y1 (12 MHz crystal)
  orientation. This is
  the subject of the Rev 1 assembly remark.
- L20: orientation dot toward pad 2 / DVDD.
- The custom sensor footprints U21 (ICM-45686), U22 (BMP581) and
  U23 (LSM6DSK320X).

## Design reference

- Panel construction, V-scores and verification:
  [reports/manufacturing-panel.md](../../reports/manufacturing-panel.md).
- How these files were generated:
  [tools/panel/README.md](../../tools/panel/README.md). This is needed only
  for a new revision, not for a Rev 1 reorder.
