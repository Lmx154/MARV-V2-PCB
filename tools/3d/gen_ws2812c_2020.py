"""
Generate a simplified STEP model for:
    LED_WS2812B-2020_PLCC4_2.0x2.0mm  (D20, WS2812C-2020, LED_SMD.pretty, vendored into
    MARV_Packages.pretty so it can carry a project-local model)

Run headless with the FreeCAD snap:
    /snap/bin/freecad.cmd -c tools/3d/gen_ws2812c_2020.py </dev/null

Why this model exists
----------------------
KiCad 10 ships the footprint LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm but this
install does not ship the matching LED_SMD.3dshapes/LED_WS2812B-2020_PLCC4_2.0x2.0mm.step
(only the 5050, Mini-3535 and PLCC6 bodies are present), so the footprint's
(model ...) node points at a file that does not exist and tools/audit_footprints.py
reports 3D_FILE_MISSING. Same treatment as the other seven vendored footprints.

Dimension source
-----------------
Worldsemi WS2812C-2020 datasheet, page 2 "Mechanical Dimensions (Unit: mm)",
Back View / Side View / PCB Solder Pad figures:
    http://www.world-semi.com  (copy used: https://cdn.sparkfun.com/assets/4/c/8/a/9/WS2812C-2020_Datasheet.pdf)

    Body X (Back View overall)        2.20
    Body Y (Back View overall)        2.00
    Body Z (Side View total)          0.84
    Base slab Z (Side View step)      0.28
    Terminal inner gap (X)            1.13
    Solder pad height (Y)             0.70
    Solder pad vertical gap (Y)       0.40

The pad rectangle in the KiCad footprint (0.7 x 0.7 at +/-0.915, +/-0.55) reproduces
all three published land-pattern dimensions exactly: pad height 0.70, vertical gap
0.40 (0.55 - 0.35 doubled) and inner gap 1.13 (0.915 - 0.35 doubled), so the KiCad
2020 land pattern IS the WS2812C-2020 PCB Solder Pad figure. Pin numbering in the
KiCad symbol/footprint (1 DO, 2 GND, 3 DI, 4 VDD) is the datasheet PIN Configuration
figure rotated 180 degrees, which maps the pad rectangle onto itself.

Known simplifications
----------------------
The moulded lens step is modelled as a plain smaller box on top of the base slab
(the Side View gives only the two heights, no width for the upper step; its
footprint here is scaled from the drawing, not dimensioned). The four castellated
terminals are modelled as flat pads matching the copper, not the real half-barrel
castellations. The RGB die, the polarity mark recess and the moulding draft are
not modelled. Colours are not set.

Alignment contract
-------------------
Units: mm. Origin: footprint origin (package centre). Body/terminal bottom: Z=0.
No rotation/offset needed - the vendored footprint's (model ...) node has
offset=0,0,0 and rotate=0,0,0.
"""

import os
import FreeCAD
import Part

BODY_X = 2.20
BODY_Y = 2.00
BASE_H = 0.28
TOTAL_H = 0.84
LENS_X = 1.45             # scaled from the Side View step, not a dimensioned value
LENS_Y = 1.30             # ditto
METAL_H = 0.05
PIN1_DOT_R = 0.13
PIN1_DOT_DEPTH = 0.05

# (pad_num, cx, cy, sx, sy) copied verbatim from the KiCad footprint pad list
# (footprint-file coordinates, Y down).
PADS = [
    (1, -0.915, -0.55, 0.70, 0.70),
    (2, -0.915, 0.55, 0.70, 0.70),
    (3, 0.915, 0.55, 0.70, 0.70),
    (4, 0.915, -0.55, 0.70, 0.70),
]

OUT_NAME = "LED_WS2812B-2020_PLCC4_2.0x2.0mm.step"


def make_box_centered(cx, cy, sx, sy, z0, z1):
    return Part.makeBox(sx, sy, z1 - z0, FreeCAD.Vector(cx - sx / 2.0, cy - sy / 2.0, z0))


def build():
    solids = []
    base = make_box_centered(0, 0, BODY_X, BODY_Y, 0, BASE_H)
    lens = make_box_centered(0, 0, LENS_X, LENS_Y, BASE_H, TOTAL_H)

    # pin-1 (DO) marker: a shallow blind dot in the top face above pad 1
    dot_center = FreeCAD.Vector(-LENS_X / 2.0 + 0.3, -LENS_Y / 2.0 + 0.3, TOTAL_H)
    dot = Part.makeCylinder(PIN1_DOT_R, PIN1_DOT_DEPTH + 0.01,
                            dot_center - FreeCAD.Vector(0, 0, PIN1_DOT_DEPTH),
                            FreeCAD.Vector(0, 0, 1))
    lens = lens.cut(dot)
    solids.append(base)
    solids.append(lens)

    for _num, cx, cy, sx, sy in PADS:
        solids.append(make_box_centered(cx, cy, sx, sy, 0, METAL_H))

    return Part.makeCompound(solids)


def main():
    doc = FreeCAD.newDocument("ws2812c2020")
    shape = build()
    # Authored in KiCad FOOTPRINT-FILE coordinates (Y down); KiCad's 3D frame is Y-up,
    # so mirror about the XZ plane at export. See tools/3d/README.md.
    shape = shape.mirror(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 1, 0))
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "MARV_Packages.3dshapes")
    out_path = os.path.abspath(os.path.join(out_dir, OUT_NAME))
    shape.exportStep(out_path)
    bb = shape.BoundBox
    print("BOUNDBOX %s Xmin=%.4f Xmax=%.4f Ymin=%.4f Ymax=%.4f Zmin=%.4f Zmax=%.4f" % (
        OUT_NAME, bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
    print("WROTE %s size=%d bytes" % (out_path, os.path.getsize(out_path)))
    FreeCAD.closeDocument(doc.Name)


main()
