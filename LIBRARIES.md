# Component and footprint references

Open `MARV-V2.kicad_pro` in KiCad. Project library tables reference local sensor
symbols, footprints and 3D models. Standard KiCad libraries are also required.
The schematic and [DESIGN_SPEC.md](DESIGN_SPEC.md) define the current circuit.

| Area | Where it lives |
| --- | --- |
| Sensor symbols | `MARV_Sensors.kicad_sym`: ICM-45686, BMP581, ADXL375 |
| MCU / regulators / discretes | Standard KiCad symbols; actual part numbers in schematic values |
| Project footprints | `MARV_Packages.pretty/` |
| Local STEP models | `MARV_Packages.3dshapes/` |
| Model provenance and licenses | [PROVENANCE.md](MARV_Packages.3dshapes/PROVENANCE.md) |
| Manufacturer PDFs | [datasheet index](datasheets/README.md) |
| Selected assembly parts | Schematic `LCSC` fields, exported by Fabrication Toolkit to `production/bom.csv` |

## Footprints that need project-specific attention

- U20: RP2354B QFN-80 plus exposed pad; local footprint/model.
- U21/U22/U23: project sensor LGAs. Their STEP bodies are stand-ins; use the
  manufacturer drawings to verify land patterns, orientation and pin 1.
- U7: standard TSOT-23-6 for AP63203; no TPS62913 footprint in the active design.
- L2: local `L_Changjiang_FTC404030S`, 4.7 uH in the current schematic.
- D20: `LED_WS2812B-2020_PLCC4_2.0x2.0mm` footprint and the **2020** symbol pinout
  for WS2812C-2020. The plain 5050 WS2812B symbol has a different pin order.
- J3: local 1x9 solder-pad row; assumed 2.00 mm pitch needs a physical ESC check.
- J10: local 1x3 SWD solder-pad row.
- J6/J7/J8: three local 1x14, 2.54 mm headers with trimmed courtyard/silkscreen.
- J4: local USB-C footprint/model; verify the manufacturer drawing for mechanical fit.
- J11: local Molex 47219-2001 (LCSC C164170) locking hinged-lid microSD footprint.
  Copied from KiCad 10 `Connector_Card:microSD_HC_Molex_47219-2001`; pads 1–8
  and four grounded SH tabs. No card-detect contacts. The exact-part LCSC/EasyEDA STEP model is stored locally and aligned with
  the replacement footprint. See `MARV_Packages.3dshapes/PROVENANCE.md`.
  All 107 schematic components now pass the footprint/model audit.
- H1–H4 and TP1–TP10: board features; no 3D body required.
- U24: unpopulated backside SOIC-8, **150 mil** expansion land. Documented fit options
  are W25Q32JVSNIQ flash or APS6404L-SQN-SN PSRAM; verify the exact package suffix
  before populating. C62 and R35 remain fitted on the front.

The retired power-symbol library and unused TPS2121/TPS62913/FTC303020D assets
were removed. The old 104031 SD footprint and model remain because the saved PCB
still uses that footprint; remove them after the owner transfers J11 to 47219.

## Checks and unresolved sourcing detail

```sh
python3 tools/audit_footprints.py build/checks/netlist.xml
```

This checks resolved files and pin/pad coverage, not package geometry or assembly
rotation. Inspect sensor pin 1, connector fit and JLC placement rotations before fabrication.

Existing sourcing choices retained when the duplicate CSV map was retired:

- C8/C65: C96446, 10 uF / 25 V X5R, while descriptive values still say
  10 uF / 10 V X7R.
- C7/C25/C59/C62: C52923, 1 uF / 25 V X5R, while descriptive values still say
  1 uF / 10 V X7R.
- Optional U24 fit choices remain W25Q32JVSNIQ C5355146 or APS6404L-SQN-SN
  C5360304 (150 mil SOIC/SOP-8); fit only one. U24 is currently DNP.
- Owner-soldered header sources: J6–J8 C2905490; J10 C49257.

No component was substituted during the plugin migration. Use schematic LCSC
fields for current selections, and JLC's ordering page for current stock/prices.

Previous library and placement revisions are available in Git history.

## BMP581 I2C schematic variant

`MARV_Sensors:BMP581_I2C` is a mode-specific copy of the existing BMP581 symbol,
with the same package and pad numbering. It names pins 2/4 as SCL/SDA and types
pin 5 (ADDR/SDO) as an input, matching its I2C address-strap role. The generic
BMP581 symbol remains available. CSB is tied to VDDIO and ADDR to GND in the
active schematic. This preserves ERC checking without waiving the address strap.
