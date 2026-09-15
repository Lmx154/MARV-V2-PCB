#!/usr/bin/env python3
"""
Generate a simplified STEP model for:
    AMASS_XT30PW-M_1x02_P2.50mm_Horizontal  (Connector_AMASS.pretty)

Run headless with the FreeCAD snap:
    /snap/bin/freecad.cmd -c tools/3d/gen_xt30pw_m.py

Dimension source
-----------------
UNKNOWN / approximate - the manufacturer/distributor mechanical drawing
could not be fetched. The footprint's own description cites:
    https://www.tme.eu/Document/6eb2005a51a52592b3f19e8a450c54c8/XT30PW-M.pdf
but that URL (and the equivalent LCSC C431092 / JLCPCB-hosted / Octopart /
componentsearchengine mirrors) all returned HTTP 403 to automated fetches
during this session. In-plane (X/Y) geometry below is instead taken
directly from the real KiCad footprint's F.Fab outline and pad list, which
*is* traced from that datasheet by the footprint's author:
    /usr/share/kicad/footprints/Connector_AMASS.pretty/AMASS_XT30PW-M_1x02_P2.50mm_Horizontal.kicad_mod
        F.Fab outline bounding box: X -9.15..4.15 mm, Y -13.1..-4.1 mm
        pad "1" (+, keyed/roundrect): (0, 0) mm, size 3.5x3.5 mm, drill 1.9 mm
        pad "2" (-, circle):          (-5, 0) mm, size 3.5x3.5 mm, drill 1.9 mm

The housing height above the board (Z) and pin diameter are NOT derivable
from the 2D footprint and are UNKNOWN from an authoritative source in this
session; the values below are generic/typical for the Amass XT30 series
(cross-referenced against public secondary sources, e.g. a widely
republished "8.5 x 7.0 mm housing cross-section" figure for XT30-family
connectors) and should be treated as approximate placeholders:
    HOUSING_H = 7.0 mm   (typical XT30-series housing height above PCB)
    PIN_DIA   = 1.5 mm   (typical round male pin, less than the 1.9 mm
                          footprint drill to leave annular clearance)

Simplification
---------------
Per task instructions a simplified housing block + 2 pins is acceptable.
The housing block uses the real F.Fab footprint outline bounding box
(so its footprint/courtyard alignment is exact); the two pins are simple
cylinders located at the real pad centres. There is a genuine gap between
the pin cylinders (at Y=0, where they exit the board) and the housing
block (Y -13.1..-4.1, the mating shroud) on the real part - the pins bend
90 degrees inside the connector base, which is not modelled here.

Alignment contract
-------------------
Units: mm. Origin: footprint origin. Bottom of housing / pin exit: Z=0.
No rotation/offset needed - the footprint's (model ...) node has
offset=0,0,0 and rotate=0,0,0.
"""

import os
import FreeCAD
import Part

# ---- housing (real F.Fab outline bounding box) ----
BODY_XMIN, BODY_XMAX = -9.15, 4.15
BODY_YMIN, BODY_YMAX = -13.1, -4.1
HOUSING_H = 7.0            # UNKNOWN/typical, see header note

# ---- pins (real pad centres) ----
PIN1_XY = (0.0, 0.0)       # "+" / keyed pad
PIN2_XY = (-5.0, 0.0)      # "-" pad
PIN_DIA = 1.5               # UNKNOWN/typical, see header note
PIN_Z0 = -3.0               # solder tail below the board
PIN_Z1 = 3.0                # stub above the board into the connector base

PIN1_DOT_R = 0.5
PIN1_DOT_DEPTH = 0.3

OUT_NAME = "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal.step"


def make_box_centered(cx, cy, sx, sy, z0, z1):
    return Part.makeBox(sx, sy, z1 - z0, FreeCAD.Vector(cx - sx / 2.0, cy - sy / 2.0, z0))


def build():
    solids = []

    # ---- housing block ----------------------------------------------------
    body = Part.makeBox(
        BODY_XMAX - BODY_XMIN,
        BODY_YMAX - BODY_YMIN,
        HOUSING_H,
        FreeCAD.Vector(BODY_XMIN, BODY_YMIN, 0),
    )

    # Pin-1 (+) marker dot on top of the housing, near pin 1's X location
    # and the front (pin-side) edge of the housing.
    dot_x = PIN1_XY[0]
    dot_y = BODY_YMAX - 0.5
    dot_center = FreeCAD.Vector(dot_x, dot_y, HOUSING_H)
    dot = Part.makeCylinder(PIN1_DOT_R, PIN1_DOT_DEPTH + 0.01, dot_center - FreeCAD.Vector(0, 0, PIN1_DOT_DEPTH), FreeCAD.Vector(0, 0, 1))
    body = body.cut(dot)
    solids.append(body)

    # ---- 2 pins -------------------------------------------------------------
    for x, y in (PIN1_XY, PIN2_XY):
        pin = Part.makeCylinder(PIN_DIA / 2.0, PIN_Z1 - PIN_Z0, FreeCAD.Vector(x, y, PIN_Z0), FreeCAD.Vector(0, 0, 1))
        solids.append(pin)

    return Part.makeCompound(solids)


def main():
    doc = FreeCAD.newDocument("xt30pw_m")
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
