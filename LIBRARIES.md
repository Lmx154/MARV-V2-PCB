# MARV V2 KiCad parts

Nonstandard KiCad parts live in the project directory. Open `MARV-V2.kicad_pro`
normally; KiCad reads `sym-lib-table` and `fp-lib-table` automatically, so there
is nothing to install globally.

Every footprint the board uses that is not a plain passive now resolves inside
the project: `MARV_Packages.pretty/` holds the footprints, and all of them
point at a STEP file in `MARV_Packages.3dshapes/` via `${KIPRJMOD}`. Eight of those
footprints are byte-for-byte copies of official KiCad footprints, vendored so
the project carries its own 3D model (seven of them) or a courtyard/silkscreen
trimmed for a tight edge fit (the IO array); their pads are unchanged from the
KiCad originals (only `descr`, the `(model ...)` node where repointed,
courtyard/silkscreen where noted, and the per-item uuids differ). Two further
footprints are project-authored solder-pad rows (`PadRow_1x03/08_P2.00mm`, for
J3 and J10) and one is a mechanical hole (`MountingHole_4.0mm_Grommet`), which
by design carry no 3D model at all — as does `TestPoint:TestPoint_Pad_1.0x1.0mm`
(TP1-TP10), used directly from the KiCad official library rather than vendored.
Model provenance, licences and SHA256 sums:
[MARV_Packages.3dshapes/PROVENANCE.md](MARV_Packages.3dshapes/PROVENANCE.md).

## Symbols

| Part | Symbol to search for |
| --- | --- |
| ICM-45686 (U21) | `ICM-45686` in `MARV_Sensors` |
| BMP581 (U22) | `BMP581` in `MARV_Sensors` |
| ADXL375 (U23) | `ADXL375` in `MARV_Sensors` |
| TPS2121 (U25) | `TPS2121RUX` in `MARV_Power` |
| RP2354A / RP2354B | `RP2354A` / `RP2354B` in `MCU_RaspberryPi` (KiCad 10 official; 60-pin QFN 7x7 mm / 80-pin QFN 10x10 mm, both with 2 MB stacked flash) |
| AP63205WU (U26) | `AP63205WU` in `Regulator_Switching` (KiCad 10 official, TSOT-23-6) |
| WS2812C-2020 (D20) | `WS2812B-2020` in `LED` — **use the `-2020` symbol, not plain `WS2812B`**: only the 2020 symbol has the WS2812C-2020 pin order (1 DO, 2 GND, 3 DI, 4 VDD). The 5050 `WS2812B` symbol is 1 VDD, 2 DOUT, 3 VSS, 4 DIN and would wire the part backwards. |
| W25Q64JVSSIQ / APS6404L-3SQR-SN (U24) | `W25Q32JVSS` in `Memory_Flash` — **substitute symbol**: KiCad 10 ships no W25Q64 symbol at all (`W25Q16JVSS`, `W25Q32JVSS`, `W25Q128JVE/JVP/JVS` only). The whole W25Q JV family shares one 8-pin pinout (1 CS#, 2 DO/IO1, 3 WP#/IO2, 4 GND, 5 DI/IO0, 6 CLK, 7 HOLD#/IO3, 8 VCC), which is also the APS6404L PSRAM pinout, so the symbol is electrically correct; the real MPN lives in the Value field. |
| Mounting holes (H1-H4) | `MountingHole` in `Mechanical` (no pins) |

Press `A` in the Schematic Editor and search these names. The project-local
ICM-45686, BMP581 and ADXL375 symbols already carry their matching footprint
assignments and datasheet links. Do not download duplicate RP2354 symbols from
third-party library sites.

## Footprints and 3D models

All rows below are `MARV_Packages:<name>`.

| Ref | Footprint | Footprint origin | 3D model | Model provenance |
| --- | --- | --- | --- | --- |
| U21 | `InvenSense_LGA-14_2.5x3mm_P0.5mm_ICM45686` | project-authored from TDK DS-000577 Sec 11.2 | `ICM-45686.step` | KiCad generic stand-in (`LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y.step`), not TDK's |
| U22 | `Bosch_LGA-10_2x2mm_BMP581` | project-authored from BST-BMP581-DS004 rev 1.13 | `BMP581.step`, `rotate 0 0 90` | KiCad generic stand-in (`ST_HLGA-10_2x2mm_P0.5mm_LayoutBorder3x2y.step`), not Bosch's; model pads coincide with the copper |
| U23 | `Analog_LGA-14_3x5mm_P0.8mm_ADXL375` | project-authored from ADI Rev. B Figure 38 | `ADXL375.step` | project copy of KiCad `LGA-14_3x5mm_P0.8mm_LayoutBorder1x6y.step` (dimensional stand-in) |
| U20 | `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm` | vendored KiCad official | `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm.step` | FreeCAD-generated (`tools/3d/gen_qfn80_rp2354b.py`) from the RP2350 datasheet Fig. 145 table |
| U7 | `Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm` | vendored KiCad official | `Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm.step` | FreeCAD-generated (`tools/3d/gen_rpu0010a_tps62913.py`) from TI drawing 4224937/A; **height 0.9 mm is the midpoint of the 0.8/1.0 min/max, no nominal published** |
| U25 | `Texas_VQFN-HR-12_2x2.5mm_P0.5mm` | vendored KiCad official | `Texas_VQFN-HR-12_2x2.5mm_P0.5mm.step` | FreeCAD-generated (`tools/3d/gen_rux0012a_tps2121.py`) from TI drawing 4224010/A; **height 0.9 mm is assumed — the drawing gives only "1 MAX"** |
| D20 | `LED_WS2812B-2020_PLCC4_2.0x2.0mm` | vendored KiCad official | `LED_WS2812B-2020_PLCC4_2.0x2.0mm.step` | FreeCAD-generated (`tools/3d/gen_ws2812c_2020.py`) from the WS2812C-2020 datasheet page 2; this KiCad install ships no 2020 body even though its own footprint references one |
| J3 | `PadRow_1x08_P2.00mm` | project-authored | — (pads only) | none by design |
| J10 | `PadRow_1x03_P2.00mm` | project-authored | — (pads only) | none by design |
| J6 | `PinHeader_2x16_P2.54mm_Vertical_IOArray` | vendored KiCad official (`Connector_PinHeader_2.54mm.pretty`) | `PinHeader_2x16_P2.54mm_Vertical_IOArray.step` (project copy of KiCad's PinHeader_2x16 model) | project copy of KiCad `Connector_PinHeader_2.54mm.3dshapes/PinHeader_2x16_P2.54mm_Vertical.step` |
| J12-J14 | `PinHeader_1x04_P2.54mm_Vertical_ServoRow` | vendored KiCad official (`Connector_PinHeader_2.54mm.pretty`), courtyard trimmed so three rows abut on the 2.54 mm grid | `PinHeader_1x04_P2.54mm_Vertical_ServoRow.step` | project copy of KiCad `Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x04_P2.54mm_Vertical.step` |
| TP1-TP10 | `TestPoint:TestPoint_Pad_1.0x1.0mm` | KiCad official, used directly (not vendored into `MARV_Packages.pretty`) | — (pads only) | none by design |
| H1-H4 | `MountingHole_4.0mm_Grommet` | project-authored | — (mechanical) | none by design |
| L3 | `L_Coilcraft_XxL4030` | vendored KiCad official (shared with L2) | `L_Coilcraft_XxL4030.step` | Coilcraft manufacturer model (XGL4030 series body) |
| J4 | `USB_C_Receptacle_HRO_TYPE-C-31-M-12` | vendored KiCad official | `USB_C_Receptacle_HRO_TYPE-C-31-M-12.step`, `offset 0 -1.05 0`, `rotate 0 0 180` | **EasyEDA/LCSC-contributed, not HRO's**; check against the HRO drawing before trusting it mechanically |
| J11 | `microSD_HC_Molex_104031-0811` | vendored KiCad official | `microSD_HC_Molex_104031-0811.step`, `offset 0.092 -0.3 1.4456`, `rotate -90 0 180` | Molex manufacturer model, via TraceParts |
| L2 | `L_Coilcraft_XxL4030` | vendored KiCad official | `L_Coilcraft_XxL4030.step`, `offset 0 0 0.1`, `rotate -90 0 0` | Coilcraft manufacturer model (XGL4030 series body) |

### Project-authored pad rows and the grommet hole

`PadRow_1x03/08_P2.00mm` are one family — just the two members now that the IO
array replaced the 1x04 solder-pad ports: N SMD pads, **1.4 x 2.2 mm oval,
2.00 mm pitch**, on **F.Cu and F.Mask only** (no paste — these are hand/reflow
wire-and-flex landings, not a connector land), a silkscreen box offset 0.45 mm
clear of the pads, a filled 0.5 mm silk **pin-1 dot** 0.8 mm outside pad 1, an
F.Fab copy and an F.CrtYd rectangle 0.25 mm outside everything. Overall pad field
is `(N-1) x 2.00 + 1.4` mm wide by 2.2 mm tall. They carry **no 3D model on
purpose**; `tools/audit_footprints.py --no-3d-ok` (default
`^(PadRow_|MountingHole_|TestPoint_)`) reports them OK with "pads only".
Per-pad function labels are *not* in the footprint — add them as silkscreen
text at layout, and mark pad 1, because the same footprint serves J3 (ESC,
1x08) and J10 (DBG, 1x03) — the only two ports left that mate with something
fixed and pad-shaped. The 1x04 member (`PadRow_1x04_P2.00mm`, formerly J6/J7/J9)
and the 1x02 member (`PadRow_1x02_P2.00mm`, gone with the buzzer before it) are
both retired; regenerate either from the same rules if a solder-pad row of that
size is ever needed again. Every other external signal now leaves on the J6 IO
array (`PinHeader_2x16_P2.54mm_Vertical_IOArray`, below) or the servo block
(`PinHeader_1x04_P2.54mm_Vertical_ServoRow`) instead of a solder pad row.

**J3 pitch is an assumption.** MicoAir publishes no pad drawing for the AM32
4-in-1 ESC's FC row, so 2.00 mm is a best guess. The pad **order** (CURR, TX, M4,
M3, M2, M1, VBAT, GND, left to right) is authoritative — it is the ESC
silkscreen. Confirm the pitch against the physical ESC before fab.

`MountingHole_4.0mm_Grommet`: a 4.0 mm NPTH (`np_thru_hole`, `*.Cu` + `*.Mask`,
no annular ring) for a 3 mm silicone grommet, a **5.0 mm diameter all-layer
copper keepout zone** (tracks/vias/pads/copperpour all not allowed), a 2.5 mm
radius F.Fab circle showing that keepout, a 2.0 mm radius Cmts.User circle for
the hole itself and a **4.0 mm radius (8.0 mm diameter) F.CrtYd** for the grommet
flange, which is the real top-side keep-clear. No 3D model.

### Flash / PSRAM socket (U24)

The U24 land is `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` (150 mil), which fits both
the default **W25Q64JVSSIQ** (Winbond, 8 MB NOR flash) and an
**APS6404L-3SQR-SN** (AP Memory, 8 MB QSPI PSRAM) with no board change — the two
are pin-identical on this bus. The RP2350 QMI has per-chip-select timing and
format registers on CS1, so a PSRAM there is a supported configuration, not just
a mechanical fit. Default fit is the flash.

Everything else on the board uses stock KiCad footprints (`Resistor_SMD`,
`Capacitor_SMD`, `Package_SO`, `Package_TO_SOT_SMD`,
`Diode_SMD`, `Crystal`, `Button_Switch_SMD`, ...) with their own KiCad 3D
models; `python3 tools/audit_footprints.py reports/power-netlist.xml` checks that
every component's footprint file *and* its 3D model actually resolve, and exits
non-zero if any does not.

### Alignment of the vendor STEP files

Vendor STEPs carry arbitrary origins and axis conventions, so three of them need
an `(offset ...)` / `(rotate ...)` in their footprint. `tools/3d/bbox.py` prints a
STEP's bounding box (`/snap/bin/freecad.cmd -c tools/3d/bbox.py -- FILE.step`);
the values above were derived from those boxes plus each footprint's pad list and
F.Fab outline, then **verified end-to-end** by exporting a one-footprint test
board with `kicad-cli pcb export step --include-pads` and measuring where the
model's solder features landed relative to the real copper:

- **L2 Coilcraft XGL4030** — model box 4.30 x 4.30 x 3.10 mm with its height on
  the model's Y axis and the terminations at Y = -0.1. `rotate -90 0 0` stands it
  up, `offset 0 0 0.1` puts the termination underside on the board. Checked: the
  two terminals land at x = +/-1.195, y = +/-1.625, inside the +/-1.185 x 0.98 x 3.4 mm
  pads; body top at 3.10 mm.
- **J11 Molex microSD** — model box 11.99 x 1.61 x 11.53 mm, height on Y again,
  in-plane axes both reversed relative to the footprint. `rotate -90 0 180`,
  `offset 0.092 -0.3 1.4456`. Checked: all eight contact tails land on pad
  centres x = -3.105 ... +3.495 (pad 8 is 0.05 mm off because it is the narrow
  one), the four shell tabs land on the four SH pads, nothing protrudes below the
  board, body height 1.61 mm.
- **J4 HRO USB-C** — model box 9.10 x 7.90 x 4.22 mm, already Z-up with the
  mounting pegs 0.88 mm below Z = 0, but authored in the EasyEDA 2D frame (Y
  down), which is mirrored with respect to KiCad's 3D frame. The receptacle is
  left/right symmetric, so `rotate 0 0 180` reproduces the correct solid;
  `offset 0 -1.05 0` centres it. Checked: the four shell through-hole legs sit
  centred in their barrels at (+/-4.32, -1.05) and (+/-4.32, +3.13), and the body's
  front and back faces land exactly on the F.Fab outline at y = +/-3.65.

KiCad's model frame is right-handed with Z up, so **model +Y is footprint-file
-Y**, and `(rotate (xyz 0 0 90))` turns the model *clockwise* seen from above
(it is the negative of the right-hand-rule sense). Both facts were confirmed on
this installation, not assumed: KiCad's own `ST_HLGA-10` model carries its pin-1
dimple at model (-0.75, +0.75) while its footprint puts pin 1 at file
(-0.7625, -0.25), and the `rotate 0 0 90` on `BMP581.step` came out of the STEP
export mapping (x, y) -> (y, -x).

### Visual checks to do in the 3D viewer before fab

The maths above is verified, but these are the judgement calls a rendered view
settles in seconds:

1. **J4 USB-C, opening direction.** The mating opening must face the board edge
   and the twelve solder tails must face inboard — i.e. the opening is on the
   +y side of the footprint (the side the courtyard extends to +4.15), away from
   the pad row at y = -4.045. Confirm the shell mouth, not the closed back, hangs
   over the board outline once the outline exists.
2. **J4 USB-C, mirrored marking.** The text moulded/lasered on the top face will
   read mirrored because of the 180 deg Z rotation applied to an EasyEDA-frame
   model. That is expected and cosmetic; it is not a sign of a wrong rotation.
   Do not "fix" it by changing the rotation.
3. **J11 microSD, card slot direction.** The card entrance must face the same
   edge as the eight contact pads (footprint -y, the side the F.Fab card outline
   extends to y = -9.7). In the model the shell floor stops short on that edge —
   that gap is the mouth.
4. **D20 WS2812C-2020** body is a simplified two-step block (the lens width is
   scaled, not dimensioned). Check it clears the 4.4 mm height budget — it should,
   at 0.84 mm — and that the pin-1 dot sits over pad 1 (DO).
5. **U22 BMP581 and U21 ICM-45686** both use generic KiCad LGA bodies. Check that
   the pin-1 marker on each body is at the corner the footprint's silkscreen
   triangle and F.Fab chamfer point to (BMP581: +x/-y; ICM-45686: -x/-y).
6. **U23 ADXL375** pin-1 corner against the ADI CC-14-1 outline drawing (pin 1
   top-left, 1-6 down the left edge, 7 bottom tab, 8-13 up the right edge, 14 top
   tab).

## Important layout notes

- The ICM-45686 footprint (`InvenSense_LGA-14_2.5x3mm_P0.5mm_ICM45686`) was
  computed from the package/lead dimensions in TDK InvenSense datasheet DS-000577
  Rev 1.0 Sec 11.2 (D = 2.5, E = 3, e = 0.5 mm pitch, D1 = 1.5, E1 = 1, W 0.2-0.3,
  L 0.425-0.525 mm, all BSC/nominal), per IPC-7351 nominal, and cross-checked
  against KiCad's own official `LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` generator
  output (same pitch, pad count and body size). Pin numbering runs
  counterclockwise from the top of the left edge per the DS-000577 Sec 11.2 top
  view, which is what the footprint and the stand-in 3D model both implement, so
  the model is referenced with no rotation. TDK's application note AN-000393 "IMU
  PCB Design and MEMS Assembly Guidelines" only gives the land pattern as a
  figure (no numeric table), so the pads were derived from the datasheet's
  package dimension table rather than copied from a vendor-published land
  pattern; confirm against the datasheet before fab.
- ICM-45686 decoupling: the datasheet BOM (DS-000577 Table 11) lists a single
  0.1 uF at VDD and at VDDIO. This board fits 100 nF + 1 uF at each
  (C50/C51 on VDD, C52/C53 on VDDIO), matching U22/U23 and common
  flight-controller practice. The five RESV pins (2, 3, 7, 10, 11) are left No
  Connect, matching the Single-Interface SPI typical application schematic
  (Figure 10).
- The BMP581 footprint follows Bosch datasheet BST-BMP581-DS004 revision 1.13
  (Figure 32 landing pattern, Figure 23 pin-out): pads are 0.325 mm radial × 0.30 mm tangential, 0.7625 mm from package centre, with 0.20 mm pad gaps (Bosch minimum; JLC 4-layer minimum 0.127 mm copper gap, 0.10 mm mask web, so no local mask expansion).
  Corrected 2026-09-15: the 2-pad edges were at ±0.5 mm and the corner pads overlapped; found by PCB DRC.
  Do not place vias or traces beneath the package, and keep solder mask and contamination away from the pressure port.
- The ADXL375 footprint follows Figure 38 of the Rev. B datasheet rather than
  KiCad's generic 3 x 5 mm LGA footprint. Place the sensor close to a rigid PCB
  mounting point and keep its orientation marker visible.
- J6 IO array (`PinHeader_2x16_P2.54mm_Vertical_IOArray`) is a vendored copy of
  KiCad's stock `PinHeader_2x16_P2.54mm_Vertical` (`descr` node in the
  footprint file has the full rationale). Two changes, pads/drills/fab
  layer/3D model otherwise untouched: the **courtyard is trimmed to the
  plastic body across the two pin columns** (+-0 mm side margin instead of the
  stock 0.5 mm) because the block has to fit between the board edge and the
  Ø8 mm H1/H4 grommet-flange keepouts with nothing to spare — `tools/setup_pcb.py`
  computes this as a 4.24 mm copper strip that needs `x < -19.30` mm, which the
  stock courtyard does not clear below 50 mm board size; and the **silkscreen
  outline is dropped** because the per-row labels (silk T0/R0/T1/R1/SDA/SCL/...,
  `PAD_LABELS["J6"]`) need that band — the board draws the end ticks and the
  pin-1 mark at board level instead. Its 3D model is a project copy in
  `MARV_Packages.3dshapes`, like every other vendored footprint on this page.
- U26 AP63205WU (VBAT buck): keep the C73/C74 input loop and the SW node tight —
  VIN, GND and the SW/L3 loop are the high-di/dt path, and the datasheet asks for
  vias under the input/output capacitor grounds. FB (pin 1) is a *sense* input on
  this fixed-output part and must be routed to the 5V_IN copper at the output
  capacitors, not to the SW node.
- D20 WS2812C-2020 land pattern: the KiCad `LED_WS2812B-2020_PLCC4_2.0x2.0mm`
  pads (0.7 x 0.7 at ±0.915, ±0.55) reproduce every dimension the WS2812C-2020
  datasheet's "PCB Solder Pad" figure gives — pad height 0.70, vertical gap 0.40,
  inner gap 1.13 — so the 2020 land pattern is verified, not assumed. The KiCad
  pin numbering is the datasheet PIN Configuration figure rotated 180°, which maps
  the pad rectangle onto itself.
