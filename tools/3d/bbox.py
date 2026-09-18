#!/usr/bin/env python3
# SPDX-License-Identifier: 0BSD
# See LICENSES/0BSD.txt at the repository root; provided AS IS.
"""
Print the axis-aligned bounding box of one or more STEP files.

Used to align vendor-supplied STEP models (which carry arbitrary vendor
origins) to a KiCad footprint frame: the numbers printed here are what the
`(offset (xyz ...))` / `(rotate (xyz ...))` values in the footprint's
`(model ...)` node are derived from.

Run headless with the FreeCAD snap (the snap cannot see /tmp - keep both
the script and the STEP files under the repo):

    /snap/bin/freecad.cmd -c tools/3d/bbox.py -- FILE.step [FILE.step ...]

With no file arguments it falls back to every `*.step` in
`MARV_Packages.3dshapes/` and `MARV_Packages.3dshapes/_incoming/`.

Output, one block per file:

    BBOX <path>
      X  min .. max   (size)
      Y  min .. max   (size)
      Z  min .. max   (size)
      centre  (cx, cy, cz)
      solids=<n>  faces=<n>

Notes
-----
* FreeCAD's STEP importer honours the file's LENGTH_UNIT, so the numbers
  are millimetres for every model in this project (all were checked to
  carry `SI_UNIT(.MILLI.,.METRE.)`).
* KiCad's 3D model offset frame is right-handed while the footprint file's
  Y axis points down, so a model offset of +Y moves the body towards
  NEGATIVE Y in the .kicad_mod coordinates. Keep that in mind when turning
  a bounding box into an `(offset ...)`.
* Rotation in KiCad is applied about the model origin BEFORE the offset,
  and `(rotate (xyz a b c))` is a clockwise rotation about each axis
  (i.e. the negative of the usual right-hand-rule sense).
"""

import glob
import os
import sys

import FreeCAD
import Part

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SHAPES = os.path.join(REPO, "MARV_Packages.3dshapes")


def argv_files():
    args = list(sys.argv[1:])
    if "--" in args:
        args = args[args.index("--") + 1:]
    files = [a for a in args if a.lower().endswith((".step", ".stp"))]
    if files:
        return [f if os.path.isabs(f) else os.path.join(REPO, f) for f in files]
    return sorted(glob.glob(os.path.join(SHAPES, "*.step")) +
                  glob.glob(os.path.join(SHAPES, "_incoming", "*.step")))


def report(path):
    if not os.path.exists(path):
        print("MISSING %s" % path)
        return
    shape = Part.Shape()
    shape.read(path)
    bb = shape.BoundBox
    print("BBOX %s" % path)
    for axis, lo, hi in (("X", bb.XMin, bb.XMax), ("Y", bb.YMin, bb.YMax), ("Z", bb.ZMin, bb.ZMax)):
        print("  %s  %10.4f .. %10.4f   (size %9.4f)" % (axis, lo, hi, hi - lo))
    print("  centre  (%.4f, %.4f, %.4f)" % (bb.XLength / 2.0 + bb.XMin,
                                            bb.YLength / 2.0 + bb.YMin,
                                            bb.ZLength / 2.0 + bb.ZMin))
    print("  solids=%d  faces=%d" % (len(shape.Solids), len(shape.Faces)))
    sys.stdout.flush()


def main():
    for path in argv_files():
        report(path)


main()
