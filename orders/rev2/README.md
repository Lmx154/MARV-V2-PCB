# MARV V2 Rev 2: JLCPCB order package

This folder holds the files to upload for Rev 2 and the PCB and PCBA options
to select. **Rev 2 has not been ordered yet** (2026-11-12). The owner's
instruction is to order Rev 2 with the same manufacturing settings as Rev 1,
so the two option tables below are the Rev 1 rows copied from
[orders/rev1/README.md](../rev1/README.md), the record transcribed from the
Rev 1 order page. Only rows that JLC fills in itself (its name for the
uploaded Gerber file and its weight estimates) are left out, and the assembly
remark is listed separately because the Rev 1 remark named a part that no
longer exists.

**If the board or schematic changes, regenerate these files with the
sequence in [tools/panel/README.md](../../tools/panel/README.md) and replace
them here before ordering.** Once Rev 2 is ordered, add JLC's BOM as ordered
and any option that ended up different, as the Rev 1 record does.

## Files

| File | Use |
| --- | --- |
| `MARV-V2-panel.zip` | PCB fabrication upload: Gerbers and drills for the 72 × 72 mm frame with the board inside it |
| `bom.csv` | PCBA "Bill of Materials" upload (Fabrication Toolkit export) |
| `positions.csv` | PCBA "Pick and Place / CPL" upload (Fabrication Toolkit export) |
| `SHA256SUMS` | Checksums of the three upload files |
| `order-manifest.json` | Export record: KiCad 10.0.8, Fabrication Toolkit options, SHA-256 of every source design file, DRC/ERC counts |

Check the upload files before using them:

```sh
cd orders/rev2 && sha256sum -c SHA256SUMS
```

The files were generated on 2026-11-11. The SHA-256 values in
`order-manifest.json` (`source_sha256`, `panel_source_sha256`) match the
committed KiCad design files of this revision, except the per-user
`.kicad_prl` files, which are not tracked. The Fabrication Toolkit export
options and the order settings recorded in the manifest are identical to
Rev 1's (automatic translations on, DNP exclusion on, automatic zone fill
off, User.1 V-cuts on).

## PCB options (select the same as Rev 1)

| Option | Value |
| --- | --- |
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

## PCBA options (select the same as Rev 1)

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
| File provided as | Complete File, just proceed with my own files |
| Panel Format | 1 × 1 |
| Build Time | 6 - 7 days (add 2 days) |
| Stencil Storage | No |
| Fixture Storage | No |
| Product Description | Reserch\Education\DIY\Entertainment/Development Board - HS Code 847330 (JLC's own spelling) |

**Assembly remark.** Rev 1's remark began "X1, Y1 orientation check please.
inductor pins n…" (cut off on the order page). X1 does not exist in Rev 2, so
write a new remark and do not mention X1. Ask for an orientation check of Y1,
U24 and L20.

## Parts

`bom.csv` has 35 lines: 34 distinct LCSC parts plus the J17 line.
`positions.csv` has 89 placements, all on the top side.

- **Changes from the Rev 1 BOM:** the 32 kHz oscillator X1 (C19674133) and
  its capacitor C1 are gone. U24 is now fitted: APS6404L-3SQN-SN, LCSC
  C3028887, the 3 V PSRAM. Do not accept APS6404L-SQN-SN (C5360304) as a
  substitute: it is the 1.8 V family and U24 is on the 3.3 V rail.
- **U20 RP2354B (C39843328)** was listed at $0.00 on the Rev 1 order, which
  suggests it came from the owner's JLC parts inventory. Check that
  inventory covers U20 for this order or buy it.
- **J17** (5 V converter header) is in `bom.csv` without an LCSC number
  and is not in `positions.csv`. Leave it unselected; it is hand-fitted.
- Not assembled by JLC (excluded from both CSVs): J3 ESC pad row,
  J6–J8 and J10 headers (hand-soldered by the owner) and H1–H4 mounting
  holes.

## Placement review

Keep "Confirm Parts Placement" at Yes. In JLC's placement preview, check:

- U24 (APS6404L-3SQN-SN): pin 1. This is the first time U24 is assembled.
- Y1 (12 MHz crystal) orientation.
- L20: orientation dot toward pad 2 / DVDD.
- The custom sensor footprints U21 (ICM-45686), U22 (BMP581) and
  U23 (LSM6DSK320X).

## Design reference

- Panel construction, V-scores and verification:
  [reports/manufacturing-panel.md](../../reports/manufacturing-panel.md).
- How these files were generated:
  [tools/panel/README.md](../../tools/panel/README.md).
