# Third-party material

The CC0 / 0BSD release in [LICENSE.md](LICENSE.md) covers original MARV V2 work.
It does not change other authors' rights or replace their notices.

## KiCad libraries

Copied and adapted KiCad library assets remain **CC-BY-SA 4.0 with the KiCad
library exception**, credited to the KiCad library contributors. The unmodified
[KiCad license notice](LICENSES/KiCad-Library-License.md) and full
[CC-BY-SA 4.0 text](LICENSES/CC-BY-SA-4.0.txt) are included here.

The exception allows this board design to use those libraries without imposing
the library's attribution/share-alike requirements on the board design. It does
not relicense separately redistributed library files. Existing upstream notices
remain applicable to embedded or copied library content.

The copied/adapted footprints are identified in
[the footprint library notice](MARV_Packages.pretty/README.md). The five KiCad
STEP models and their original paths are listed in section 3 of
[PROVENANCE.md](MARV_Packages.3dshapes/PROVENANCE.md).
Upstream libraries: https://gitlab.com/kicad/libraries/kicad-footprints and
https://gitlab.com/kicad/libraries/kicad-packages3D.

## Manufacturer documents and models

- `datasheets/*.pdf`: manufacturer/publisher documents, subject to their original
  rights and terms. Sources are recorded in [the index](datasheets/README.md).
- `simulations/models/AO3401A.mod`: Alpha & Omega Semiconductor vendor SPICE
  model. The file records its source; no additional reuse permission is granted
  by this project's licenses.
- `MARV_Packages.3dshapes/microSD_HC_Molex_104031-0811.step`: Molex/TraceParts
  model, subject to the source terms recorded in the provenance document.
- `MARV_Packages.3dshapes/USB_C_Receptacle_HRO_TYPE-C-31-M-12.step` and
  `microSD_HC_Molex_47219-2001.step` in the same directory: EasyEDA/LCSC library
  models. No explicit per-model license was attached; their source terms remain
  applicable. Public availability is not a CC0 dedication or a 0BSD grant.

The two project-generated STEP models identified in section 2 of the provenance
record are original MARV V2 work and are covered by CC0.

---

Original MARV V2 documentation: [CC0 1.0](LICENSES/CC0-1.0.txt). No attribution required; provided as-is. [Licensing and third-party exceptions](LICENSE.md).
