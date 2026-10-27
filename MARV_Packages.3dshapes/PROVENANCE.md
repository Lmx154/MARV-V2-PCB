# MARV_Packages.3dshapes — 3D model provenance

Every STEP file in this directory: where it came from, under what terms, and what is assumed
about it. Footprints reference them as `${KIPRJMOD}/MARV_Packages.3dshapes/<name>.step` with an
identity transform (offset 0, rotation 0, scale 1), so the project is self-contained for 3D.

Every file starts with `ISO-10303-21;` and declares millimetres. Sizes and SHA256 are of the files
as committed.

## 1. Project-authored models — CC0 1.0 (2026-10-27)

Built with CadQuery 2.8 from the manufacturer's published dimensions only. No third-party CAD
model (vendor, EasyEDA/LCSC, SnapEDA, TraceParts or KiCad-generated) was used, opened as a
reference or traced. Each model is an assembly of separately coloured solids, contains no text or
logos, and is authored in the KiCad frame (origin at the footprint anchor, Z = 0 at the board top).
The one-time generator scripts are not kept; the STEP files are the editable source (FreeCAD or
any STEP editor). Terminal positions were checked numerically against the footprint pads, and
pin 1 was checked in close-up renders.

| File | Part | Dimension source | Bytes | SHA256 |
| --- | --- | --- | --- | --- |
| `USB_C_Receptacle_HRO_TYPE-C-31-M-12.step` | J4, HRO TYPE-C-31-M-12 | HRO drawing (cited by the footprint): shell 8.94 x 3.26 x 7.35, opening 8.34 x 2.56, tongue 0.70, rear tails 0.40, shell legs 1.10/0.80 long, 1.01 deep, pegs 0.50 | 800982 | `574c5a2824757118387ed9412c8515687bfa1fc8ddf1bdaf773ce567684b466e` |
| `microSD_HC_Molex_47219-2001.step` | J11, Molex 47219-2001 hinged-lid socket | Molex sales drawing 472192001: 13.60 x 14.50 x 1.90, contacts on 1.10 pitch, lock nails 8.30 apart, card slot 11.16 | 829595 | `944f8952c413a6f9af84df5879ba8ce609f4a86d42c02dda66928a3b0c8364ff` |
| `Capacitor_Panasonic_POSCAP_6TPE100MAZB_CASE-B2.step` | C19, Panasonic 6TPE100MAZB (case B2) | Panasonic TPE spec sheet `S_POSCAP_TPE_E.pdf` p.1, B2 row: 3.5 x 2.8 x 1.9, terminal S 0.8, W1 2.2 | 128198 | `e1b19c2485e9b9782abcc0909e7f50fc546f54bdf43fc18678d73abf80fd4cdc` |
| `Oscillator_HCI_1521H_2.0x1.6mm.step` | X1, HCI 1521H-32K000J18DTSL | HCI 1521H sheet, outline CS02016p4 Rev 1: 2.05 x 1.65 x 0.75, pads 0.58 x 0.48 on 1.28 x 0.98 centres, pad-1 chamfer | 211462 | `054ac20b0f492711dc55c18b1d1bd7f9ac7ace8b14f43eb091e39bde70c65773` |
| `LED_WS2812B-2020_PLCC4_2.0x2.0mm.step` | D20, Worldsemi WS2812C-2020 | WS2812C-2020 datasheet p.2 "Mechanical Dimensions": 2.20 x 2.00 x 0.84, base 0.28, terminal gap 1.13 | 481290 | `d156733354dd9285365d4fb05efebbfd302172972f8d21f78b17f31adaccd09b` |
| `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm.step` | U20, RP2354B | RP2350 datasheet Fig. 145 table: D/E 10, A 0.85, A3 0.203, b 0.20, L 0.40, e 0.40, EP 3.4 x 3.4, matte Sn; terminals flush with the body | 961541 | `dcf982ba7a8cfb17be2da64c8ec20ba64b0e92822694d8d7c1cd2fb7c1e006cd` |
| `ICM-45686.step` | U21, TDK ICM-45686 | TDK DS-000489 pp.51-52: 3.0 x 2.5 x 0.81, substrate 0.105, pads 0.475 x 0.25 inset 0.10 | 185820 | `6ab40fa41b51932e80dbc76dfca84801f37ae3179fe86bb6dd8b4873d5218b5b` |
| `BMP581.step` | U22, Bosch BMP581 | BST-BMP581-DS004 pp.68-70, Figs. 29-31: substrate 2.0 x 2.0 x 0.13, metal lid 1.85 x 1.85, 0.80 max height, port hole, pads per Fig. 30 | 177695 | `51f5f53e44be8a9bfa494afda815e451684b9c1ffa4761727cb67205a4817568` |
| `LSM6DSK320X.step` | U23, ST LSM6DSK320X | ST DS15060 p.185, Fig. 31: 3.00 x 2.50 x 0.83, pads 0.475 x 0.25 inset 0.10, pad-1 chamfer | 188639 | `dafb9adc6e29d5fcb9b4573c6237a74e61087e2eaad56347a75224a784ed8775` |

Datasheet locations are listed in the [datasheet index](../datasheets/README.md); the Panasonic
sheet is at https://industrial.panasonic.com/content/data/CP/PDF/POSCAP/S_POSCAP_TPE_E.pdf.

Assumed or scaled values (not dimensioned in the source):

- **J4:** corner radii (outer 1.0, inner 0.7), tongue width 6.7 and its 0.65 recess, latch-window
  size. The exposed rear tails follow the drawing's 0.40 length and lie on their pads,
  with centres 0.14 mm inboard of the pad centres; each lead solid continues 0.9 mm under the
  housing, 0.52 mm of it beyond the pad's inner end. The shell legs are 1.01 deep as
  drawn and do not pass through a 1.6 mm board. The seam, top slots and laser marking are omitted.
- **J11:** lid windows, beads, entry arch and hinge ears scaled off the top view (about ±0.1 mm);
  0.12 mm housing standoff; simplified contact springs. Tails and tabs sit exactly on their pads.
- **C19:** terminal wrap height, top-edge draft and polarity-band length scaled off the drawing.
  The stock KiCad `CP_EIA-3528-21_Kemet-B` lands sit 0.19 mm further out than the Panasonic
  terminal centres; the model follows Panasonic. The anode band is over pad 1.
- **X1:** ceramic and lid heights and pin-1 dot position scaled off the drawing.
- **D20:** the lens width (1.45) and the positions of the controller IC and R/G/B dies are scaled
  off the top view. The lens is translucent (alpha 0.35). Terminal centres are 0.085 mm inboard
  of the footprint lands, which extend past the package edge.
- **U20:** A1 standoff 0.025 (midpoint of 0-0.05) and the 0.6 mm pin-1 dot. The footprint pads
  reach 0.35 mm beyond the body, so terminal centres are 0.15 mm inboard of the pad centres.
- **U21/U23:** 0.03 mm pad thickness and pin-1 dot size; the U23 substrate thickness (0.13) is read
  off the side view. Datasheet pads are smaller than the footprint lands (same centres).
- **U22:** lid radii (0.2 vertical, 0.15 top) and wall thickness. The pin-1 dot position is a
  choice; Bosch specifies only its 0.2 mm diameter.

## 2. KiCad library copies — CC-BY-SA 4.0 with the KiCad library exception

Byte-identical to `kicad-packages3d` 10.0.x, renamed or aimed at a project-local footprint.

| File | Used by | Copied from | Bytes | SHA256 |
| --- | --- | --- | --- | --- |
| `L_Changjiang_FTC404030S.step` | L2, CJIANG FTC404030S4R7MGCA | `Inductor_SMD.3dshapes/L_Changjiang_FTC404030S.step` (authored for this exact part) | 24661 | `c14952bfeafd86b5c9474e30e0b7223a28d76168a9d33542d355bbe9ec745668` |
| `PinHeader_1x14_P2.54mm_Vertical_IORow.step` | J6/J7/J8 | `Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x14_P2.54mm_Vertical.step` | 501498 | `39dfd3637dd67baea70179ebf53ac58e7a07092d0a0ea6667f885c44c4412ffa` |

These files, and the footprints vendored into `MARV_Packages.pretty/` from the KiCad library, are
licensed **CC-BY-SA 4.0 with the KiCad library exception** (https://kicad.org/libraries/license).
The exception waives article 3 for electronic designs that *use* the library data, so this board's
design files are unencumbered. It does **not** apply to redistributing library files themselves:
these copies stay under CC-BY-SA 4.0 and this attribution must travel with them.

## 3. Stock KiCad models referenced in place

Passives, SOT/TSOT/SOD packages, U24's SOIC-8, Y1's 3225 crystal, SW1/SW2 (B3U-1000P), L20 and the
J10/J17 headers use stock footprints that reference `${KICAD10_3DMODEL_DIR}` directly. Nothing is
copied into this repository for them. H1-H4, J3 (solder-pad row) and the G1-G3 graphics have no 3D
body.

## 4. Scope

This directory contains only the project-authored CC0 models and the two KiCad library copies listed
above. It holds no vendor or EasyEDA/LCSC models.
