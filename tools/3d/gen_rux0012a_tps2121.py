#!/usr/bin/env python3
"""
Generate a simplified STEP model for:
    Texas_VQFN-HR-12_2x2.5mm_P0.5mm  (TPS2121RUXR, Package_DFN_QFN.pretty, package RUX0012A)

Run headless with the FreeCAD snap:
    /snap/bin/freecad.cmd -c tools/3d/gen_rux0012a_tps2121.py

Dimension source
-----------------
Texas Instruments TPS2120/TPS2121 datasheet (SLVSEA3F), Section 14
"Mechanical, Packaging, and Orderable Information" -> "PACKAGE OUTLINE,
RUX0012A, VQFN-HR - 1 mm max height" (TI drawing 4224010/A, 11/2017):
    https://www.ti.com/lit/ds/symlink/tps2121.pdf

Values read from the package-outline drawing (mm):
    Body X (B)   1.9 min / 2.1 max            -> use midpoint 2.0 mm
    Body Y (A)   2.4 min / 2.6 max            -> use midpoint 2.5 mm (matches "2x2.5mm")
    Height       "1 MAX"                       -> only a max is called out; use 0.9 mm
                                                   (assumed, consistent with the 0.8/1.0
                                                   min/max range seen on the sibling
                                                   RPU0010A VQFN-HR drawing) - see report
    Standoff A1  0.00 min / 0.05 max          -> folded into Z=0 per alignment contract
    Pin-1 ID     PIN 1 INDEX AREA, top-left of the body outline

Lead frame thickness is not separately dimensioned; 0.15 mm generic
QFN/VQFN leadframe-reference thickness is used, same as the RPU0010A model.

Pad XY geometry (12 pads, asymmetric VQFN-HR lead lengths) is copied
directly from the real KiCad footprint pad list, which is the authoritative
source for in-plane alignment to the footprint:
    /usr/share/kicad/footprints/Package_DFN_QFN.pretty/Texas_VQFN-HR-12_2x2.5mm_P0.5mm.kicad_mod
The mechanical pin-1 chamfer (F.Fab / F.SilkS) is at the bottom-left corner
of the body outline.

Alignment contract
-------------------
Units: mm. Origin: footprint origin (package centre). Body/lead bottom: Z=0.
No rotation/offset needed - the footprint's (model ...) node has
offset=0,0,0 and rotate=0,0,0.
"""

import os
import FreeCAD
import Part

BODY_X = 2.0
BODY_Y = 2.5
BODY_H = 0.9              # assumed nominal, see header note ("1 MAX" only in drawing)
METAL_H = 0.15
PIN1_DOT_R = 0.12
PIN1_DOT_DEPTH = 0.06

# (pad_num, cx, cy, sx, sy) copied verbatim from the .kicad_mod pad list.
PADS = [
    (1, -0.675, -0.35, 1.05, 0.40),
    (2, -0.675, 0.35, 1.05, 0.40),
    (3, -0.750, 1.15, 0.20, 0.60),
    (4, -0.250, 1.15, 0.20, 0.60),
    (5, 0.250, 1.15, 0.20, 0.60),
    (6, 0.750, 1.15, 0.20, 0.60),
    (7, 0.675, 0.35, 1.05, 0.40),
    (8, 0.675, -0.35, 1.05, 0.40),
    (9, 0.750, -1.15, 0.20, 0.60),
    (10, 0.250, -1.15, 0.20, 0.60),
    (11, -0.250, -1.15, 0.20, 0.60),
    (12, -0.750, -1.15, 0.20, 0.60),
]

OUT_NAME = "Texas_VQFN-HR-12_2x2.5mm_P0.5mm.step"


def make_box_centered(cx, cy, sx, sy, z0, z1):
    return Part.makeBox(sx, sy, z1 - z0, FreeCAD.Vector(cx - sx / 2.0, cy - sy / 2.0, z0))


def build():
    solids = []
    half_x = BODY_X / 2.0
    half_y = BODY_Y / 2.0

    # ---- molded body, pin-1 corner chamfered -----------------------------
    body = make_box_centered(0, 0, BODY_X, BODY_Y, 0, BODY_H)
    chamfer_leg = 0.5
    p1 = FreeCAD.Vector(-half_x, -half_y, BODY_H)
    p2 = FreeCAD.Vector(-half_x + chamfer_leg, -half_y, BODY_H)
    p3 = FreeCAD.Vector(-half_x, -half_y + chamfer_leg, BODY_H)
    tri = Part.Face(Part.makePolygon([p1, p2, p3, p1]))
    chamfer_solid = tri.extrude(FreeCAD.Vector(0, 0, -BODY_H - 0.1))
    body = body.cut(chamfer_solid)

    dot_center = FreeCAD.Vector(-half_x + 0.4, -half_y + 0.4, BODY_H)
    dot = Part.makeCylinder(PIN1_DOT_R, PIN1_DOT_DEPTH + 0.01, dot_center - FreeCAD.Vector(0, 0, PIN1_DOT_DEPTH), FreeCAD.Vector(0, 0, 1))
    body = body.cut(dot)
    solids.append(body)

    # ---- leads, from the real footprint pad list -------------------------
    for _num, cx, cy, sx, sy in PADS:
        solids.append(make_box_centered(cx, cy, sx, sy, 0, METAL_H))

    return Part.makeCompound(solids)


def main():
    doc = FreeCAD.newDocument("rux0012a")
    shape = build()
    # Geometry above is authored in KiCad FOOTPRINT-FILE coordinates (Y down, as in the
    # .kicad_mod pad list). KiCad's 3D model frame is Y-up (model +Y = footprint -Y), so
    # mirror about the XZ plane at export; without this the model lands Y-mirrored on the pads.
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
