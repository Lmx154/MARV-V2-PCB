#!/usr/bin/env python3
"""
Generate a simplified STEP model for:
    QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm  (RP2354B / RP2350B, Package_DFN_QFN.pretty)

Run headless with the FreeCAD snap:
    /snap/bin/freecad.cmd -c tools/3d/gen_qfn80_rp2354b.py

Dimension source
-----------------
Raspberry Pi RP2350 datasheet, "Chapter 14. Electrical and mechanical",
Section 14.2 "QFN-80 package", Figure 145 (mechanical dimension table),
PDF page 1329 (printed page footer "1329"):
    https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf
    (redirects to https://pip-assets.raspberrypi.com/categories/1214-rp2350/documents/RP-008373-DS-2-rp2350-datasheet.pdf)

Table values used (Millimetre, Min/Nom/Max):
    A  (body height)      0.800 / 0.850 / 0.900   -> use NOM = 0.85 mm
    A1 (standoff)         0.000 /  -   / 0.050     -> folded into Z=0 per alignment contract
    A3 (leadframe ref)    0.203 REF                -> used as lead/EP metal thickness
    D, E (body)           10 BSC x 10 BSC          -> matches "10x10mm" in part name
    D2, E2 (exposed pad)  3.350 / 3.400 / 3.450     -> use NOM = 3.40 mm, matches "EP3.4x3.4mm"
    b  (lead width)       0.150 / 0.200 / 0.250     -> use NOM = 0.20 mm
    e  (pitch)            0.400 BSC                -> matches "P0.4mm"
    L  (lead length)      0.350 / 0.400 / 0.450     -> use NOM = 0.40 mm (JEDEC MO-220 typical range)

Pad XY geometry (20 pads/side, 80 total + EP) is generated from the same
regular grid used by the real KiCad footprint (verified against):
    /usr/share/kicad/footprints/Package_DFN_QFN.pretty/QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm.kicad_mod
Pin 1 is at the bottom-left corner (chamfer between X=-5..-4, Y=-5..-4 in
footprint coordinates), matching the footprint's F.Fab chamfer and F.SilkS
pin-1 arrow.

Alignment contract
-------------------
Units: mm. Origin: footprint origin (package centre). Body/lead bottom: Z=0.
No rotation/offset needed - the footprint's (model ...) node has
offset=0,0,0 and rotate=0,0,0.
"""

import os
import FreeCAD
import Part

# ---------------------------------------------------------------- geometry
BODY_XY = 10.0          # D = E, BSC
BODY_H = 0.85            # A, NOM
EP_XY = 3.40              # D2 = E2, NOM
LEAD_W = 0.20             # b, NOM (pad width across the pitch direction)
LEAD_TOE = 0.80           # footprint pad length in the direction away from the body edge
                           # (matches the real .kicad_mod pad "size" long dimension, 0.8 mm)
PITCH = 0.40              # e, BSC
PINS_PER_SIDE = 20
METAL_H = 0.203           # A3 REF, used as lead/EP metal thickness above Z=0
PIN1_DOT_R = 0.35
PIN1_DOT_DEPTH = 0.12

OUT_NAME = "QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm.step"


def make_box_centered(cx, cy, sx, sy, z0, z1):
    return Part.makeBox(sx, sy, z1 - z0, FreeCAD.Vector(cx - sx / 2.0, cy - sy / 2.0, z0))


def build():
    half = BODY_XY / 2.0
    solids = []

    # ---- molded body (chamfered pin-1 corner cut away) -----------------
    body = make_box_centered(0, 0, BODY_XY, BODY_XY, 0, BODY_H)
    # Pin-1 chamfer: cut the bottom-left top corner, matching the
    # footprint's F.Fab chamfer between (-5,-4) and (-4,-5).
    chamfer_leg = 1.0
    p1 = FreeCAD.Vector(-half, -half, BODY_H)
    p2 = FreeCAD.Vector(-half + chamfer_leg, -half, BODY_H)
    p3 = FreeCAD.Vector(-half, -half + chamfer_leg, BODY_H)
    tri = Part.Face(Part.makePolygon([p1, p2, p3, p1]))
    chamfer_solid = tri.extrude(FreeCAD.Vector(0, 0, -BODY_H - 0.1))
    body = body.cut(chamfer_solid)

    # Pin-1 dot (secondary/backup marker) near the same corner.
    dot_center = FreeCAD.Vector(-half + 0.9, -half + 0.9, BODY_H)
    dot = Part.makeCylinder(PIN1_DOT_R, PIN1_DOT_DEPTH + 0.01, dot_center - FreeCAD.Vector(0, 0, PIN1_DOT_DEPTH), FreeCAD.Vector(0, 0, 1))
    body = body.cut(dot)

    solids.append(body)

    # ---- 80 perimeter leads ---------------------------------------------
    start_off = -(PINS_PER_SIDE - 1) * PITCH / 2.0  # -3.8
    pad_edge = half - 0.05  # 4.95, matches footprint pad "at" coordinate magnitude

    # side 1: left edge, pins 1-20, x = -4.95 (const), y sweeps -3.8..+3.8
    for i in range(PINS_PER_SIDE):
        y = start_off + i * PITCH
        solids.append(make_box_centered(-pad_edge, y, LEAD_TOE, LEAD_W, 0, METAL_H))

    # side 2: top edge, pins 21-40, y = +4.95 (const), x sweeps -3.8..+3.8
    for i in range(PINS_PER_SIDE):
        x = start_off + i * PITCH
        solids.append(make_box_centered(x, pad_edge, LEAD_W, LEAD_TOE, 0, METAL_H))

    # side 3: right edge, pins 41-60, x = +4.95 (const), y sweeps +3.8..-3.8
    for i in range(PINS_PER_SIDE):
        y = -(start_off + i * PITCH)
        solids.append(make_box_centered(pad_edge, y, LEAD_TOE, LEAD_W, 0, METAL_H))

    # side 4: bottom edge, pins 61-80, y = -4.95 (const), x sweeps +3.8..-3.8
    for i in range(PINS_PER_SIDE):
        x = -(start_off + i * PITCH)
        solids.append(make_box_centered(x, -pad_edge, LEAD_W, LEAD_TOE, 0, METAL_H))

    # ---- exposed pad (EP), pad 81 ---------------------------------------
    solids.append(make_box_centered(0, 0, EP_XY, EP_XY, 0, METAL_H))

    return Part.makeCompound(solids)


def main():
    doc = FreeCAD.newDocument("qfn80")
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
