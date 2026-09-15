#!/usr/bin/env python3
"""
Generate a simplified STEP model for:
    Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm  (TPS62913RPUR, Package_DFN_QFN.pretty)

Run headless with the FreeCAD snap:
    /snap/bin/freecad.cmd -c tools/3d/gen_rpu0010a_tps62913.py

Dimension source
-----------------
Texas Instruments TPS62913 datasheet (SLVSHR9), Section 12 "Mechanical,
Packaging, and Orderable Information" -> "PACKAGE OUTLINE, RPU0010A,
VQFN-HR - 1 mm max height" (TI drawing 4224937/A, 04/2019):
    https://www.ti.com/lit/ds/symlink/tps62913.pdf

Values read from the package-outline drawing (mm):
    Body X (B)   1.9 min / 2.1 max            -> use midpoint 2.0 mm (matches "2x2mm")
    Body Y (A)   1.9 min / 2.1 max            -> use midpoint 2.0 mm
    Height       0.8 min / 1.0 max            -> use midpoint 0.9 mm (no separate NOM given)
    Standoff A1  0.00 min / 0.05 max          -> folded into Z=0 per alignment contract
    Pin-1 ID     45 deg x 0.1 mm chamfer, top-left of the body outline

Lead frame thickness is not separately dimensioned on the excerpted pages;
0.15 mm is used as a generic QFN/VQFN leadframe-reference thickness
(consistent with the ~0.2 mm A3 REF seen on comparable TI/JEDEC QFN
drawings). This is a simplification, not a datasheet value - see report.

Pad XY geometry (10 pads, asymmetric VQFN-HR lead lengths) is copied
directly from the real KiCad footprint pad list, which is the authoritative
source for in-plane alignment to the footprint:
    /usr/share/kicad/footprints/Package_DFN_QFN.pretty/Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm.kicad_mod
Pin 1 is on the left edge; the mechanical pin-1 chamfer (F.Fab / F.SilkS) is
at the bottom-left corner of the body.

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
BODY_Y = 2.0
BODY_H = 0.9              # midpoint of 0.8/1.0 min/max
METAL_H = 0.15             # generic QFN leadframe-reference thickness (not separately dimensioned)
PIN1_DOT_R = 0.12
PIN1_DOT_DEPTH = 0.06

# (pad_num, cx, cy, sx, sy) copied verbatim from the .kicad_mod pad list.
PADS = [
    (1, -0.875, -0.25, 0.65, 0.20),
    (2, -0.700, 0.25, 1.00, 0.20),
    (3, -0.875, 0.75, 0.65, 0.20),
    (4, 0.700, 0.75, 1.00, 0.20),
    (5, 0.875, 0.25, 0.65, 0.20),
    (6, 0.700, -0.25, 1.00, 0.20),
    (7, 0.750, -0.925, 0.25, 0.55),
    (8, 0.250, -0.925, 0.25, 0.55),
    (9, -0.250, -0.925, 0.25, 0.55),
    (10, -0.750, -0.925, 0.25, 0.55),
]

OUT_NAME = "Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm.step"


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
    doc = FreeCAD.newDocument("rpu0010a")
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
