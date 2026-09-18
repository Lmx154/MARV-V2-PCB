# STEP model inspection

`bbox.py` is the reusable FreeCAD helper for inspecting model dimensions and
alignment while changing footprints or importing replacement models.

```sh
/snap/bin/freecad.cmd -c tools/3d/bbox.py -- FILE.step </dev/null
```

With no STEP arguments it inspects local models in `MARV_Packages.3dshapes/`
and its `_incoming/` directory. It prints bounding coordinates, dimensions,
centers, solid counts and face counts without changing the files.

Requires FreeCAD. Keep inputs under the repository for the snap's filesystem
access. KiCad model and footprint Y axes differ; see the script's coordinate
notes when interpreting offsets.

The four one-time package generators have been removed. Their STEP assets and
[provenance](../../MARV_Packages.3dshapes/PROVENANCE.md) remain available.

---

Original MARV V2 documentation: [CC0 1.0](../../LICENSES/CC0-1.0.txt). No attribution required; provided as-is. [Licensing and third-party exceptions](../../LICENSE.md).
