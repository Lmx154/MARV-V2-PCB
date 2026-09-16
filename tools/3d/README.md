# tools/3d - simplified STEP model generators

FreeCAD Python scripts that generate simplified, dimensionally-correct STEP
3D models for footprints that have no publicly downloadable model. Each
script is standalone and reproducible: run it, it writes one `.step` file
into `MARV_Packages.3dshapes/` and prints the resulting bounding box.

## Requirements

FreeCAD 1.1 (snap), headless console mode. The snap's CLI entry point is
`freecad.cmd` (see `snap info freecad` -> Apps/Commands). Note: snap
confinement blocks writes under `/tmp`; these scripts only read their own
directory and write under the repo (`MARV_Packages.3dshapes/`), which is
allowed under the `home` interface.

## Run

From the repo root:

```sh
/snap/bin/freecad.cmd -c tools/3d/gen_qfn80_rp2354b.py </dev/null
/snap/bin/freecad.cmd -c tools/3d/gen_rpu0010a_tps62913.py </dev/null
/snap/bin/freecad.cmd -c tools/3d/gen_rux0012a_tps2121.py </dev/null
/snap/bin/freecad.cmd -c tools/3d/gen_ws2812c_2020.py </dev/null
```

Run the generators with stdin closed (e.g. `</dev/null`), because FreeCADCmd
otherwise stays in its interactive console after the script finishes.

Each invocation exits once the script finishes. Each script prints a line like:

```
BOUNDBOX <file>.step Xmin=... Xmax=... Ymin=... Ymax=... Zmin=... Zmax=...
WROTE <path> size=<bytes> bytes
```

To regenerate all four in one go:

```sh
for f in gen_qfn80_rp2354b.py gen_rpu0010a_tps62913.py gen_rux0012a_tps2121.py gen_ws2812c_2020.py; do
    /snap/bin/freecad.cmd -c "tools/3d/$f" </dev/null
done
```

## Coordinate frame

The generators are authored in KiCad footprint-file coordinates, where Y points
downward. KiCad's 3D model frame is Y-up (model +Y corresponds to footprint -Y),
so each generator mirrors the finished shape about the XZ plane at export. Without
this mirror, the models render Y-mirrored on their pads — an artifact found in
render checks during development. The mirror is applied by each script before
calling `exportStep`.

## Alignment contract (applies to all four generators)

- Units: mm.
- Origin: the footprint origin (package centre for the QFN/VQFN parts).
- Z=0: bottom of the body / leads (component sits on top of the board).
- No rotation or offset is applied by the corresponding `.kicad_mod`
  `(model ...)` node (`offset 0 0 0`, `rotate 0 0 0`), so the geometry below
  is built directly in the footprint's own XY coordinate frame.
- In-plane (X/Y) pad positions are taken from the real KiCad system
  footprints in `/usr/share/kicad/footprints/` (`Package_DFN_QFN.pretty`,
  `LED_SMD.pretty`) so the generated models line up with the
  footprints already used in this project's schematics/BOM.
- A pin-1 corner chamfer (QFN/VQFN parts) or a small top-face dot marker
  (all four parts) marks pin 1.

## Per-model dimension sources

| Script | Output | Dimension source |
| --- | --- | --- |
| `gen_qfn80_rp2354b.py` | `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm.step` | RP2350 datasheet, Ch. 14.2 "QFN-80 package", Figure 145 dimension table, PDF page 1329 ( https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf ) |
| `gen_rpu0010a_tps62913.py` | `Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm.step` | TPS62913 datasheet (SLVSHR9), package outline RPU0010A, TI dwg 4224937/A ( https://www.ti.com/lit/ds/symlink/tps62913.pdf ) |
| `gen_rux0012a_tps2121.py` | `Texas_VQFN-HR-12_2x2.5mm_P0.5mm.step` | TPS2120/TPS2121 datasheet (SLVSEA3F), package outline RUX0012A, TI dwg 4224010/A ( https://www.ti.com/lit/ds/symlink/tps2121.pdf ) |
| `gen_ws2812c_2020.py` | `LED_WS2812B-2020_PLCC4_2.0x2.0mm.step` | Worldsemi WS2812C-2020 datasheet, page 2 "Mechanical Dimensions (Unit: mm)" - Back View 2.20 x 2.00, Side View 0.84 total / 0.28 base, PCB Solder Pad 0.70 / 0.40 / 1.13. The upper moulding step has no dimensioned width and is scaled from the drawing. See script docstring. |

Full dimension tables, JEDEC/TI drawing numbers, and exact values used are
documented in each script's module docstring - read the script before
trusting a number blindly.

## Known simplifications

- Leads/pads are modelled as flat rectangular boxes (QFN/VQFN) or plain
  cylinders (Amass pins), not the true gull-wing/lead-frame profile.
- The exposed pad (QFN-80 only) is a flat rectangular plate.
- The WS2812C-2020 body is a base slab plus a plain smaller box for the
  moulded lens; the castellated terminals are modelled as flat pads matching
  the copper, and the RGB die and polarity-mark recess are not modelled.
- Colours are not set (default FreeCAD/STEP material).
