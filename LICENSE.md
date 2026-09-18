# MARV V2 licensing

Use, modify, build, sell, and share the original MARV V2 work. No attribution
or publication of your changes is required.

| Original material | License |
| --- | --- |
| Hardware designs, schematics, PCB layouts, original library assets, artwork, data, project settings, and documentation | [CC0 1.0 Universal](LICENSES/CC0-1.0.txt) |
| Software, Python tools/tests, SPICE decks, and project-authored SPICE models | [Zero-Clause BSD (0BSD)](LICENSES/0BSD.txt) |

The original authors dedicate the CC0-covered work to the public domain under
CC0, including its fallback license, and license original code under 0BSD.
These grants apply only to rights the authors own. Third-party exceptions below
take precedence. CC0 does not waive or license patent or trademark rights.

## Warranty and liability

TO THE FULLEST EXTENT PERMITTED BY APPLICABLE LAW, THE ORIGINAL MARV V2 WORK,
INCLUDING HARDWARE DESIGNS, DOCUMENTATION AND SOFTWARE, IS PROVIDED "AS IS",
WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. THE AUTHORS AND
CONTRIBUTORS DISCLAIM LIABILITY FOR CLAIMS, DAMAGES OR OTHER LIABILITY ARISING
FROM OR IN CONNECTION WITH THE WORK, ITS USE, MODIFICATION, MANUFACTURE OR
DISTRIBUTION, WHETHER IN CONTRACT, TORT OR OTHERWISE.

This supplements the license disclaimers without adding conditions on reuse.
It does not exclude liability that applicable law does not allow to be excluded.

## Third-party exceptions

Manufacturer datasheets in `datasheets/`, the Alpha & Omega Semiconductor
`simulations/models/AO3401A.mod`, and downloaded Molex/TraceParts and EasyEDA/LCSC
CAD models retain their original rights and terms. They are not relicensed as
CC0 or 0BSD. No explicit per-model license was attached to the EasyEDA/LCSC
models; this release grants no additional rights to them. Sources and terms are
recorded in the [datasheet index](datasheets/README.md) and
[model provenance](MARV_Packages.3dshapes/PROVENANCE.md).

Copied/adapted KiCad library files remain **CC-BY-SA 4.0 with the KiCad library
exception**, credited to the KiCad library contributors. The
[upstream notice](LICENSES/KiCad-Library-License.md) and
[full license](LICENSES/CC-BY-SA-4.0.txt) are retained. The exception permits
independent licensing of this board design, but does not relicense redistributed
library files. Existing upstream attribution and notices remain applicable.
The five KiCad STEP models and two original CC0 STEP models are identified in
the provenance record. The copied/adapted footprints are listed below.

| Local footprint | Upstream KiCad footprint |
| --- | --- |
| `InvenSense_LGA-14_2.5x3mm_P0.5mm_ICM45686` | `Package_LGA.pretty/LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` |
| `LED_WS2812B-2020_PLCC4_2.0x2.0mm` | `LED_SMD.pretty/LED_WS2812B-2020_PLCC4_2.0x2.0mm` |
| `L_Changjiang_FTC404030S` | `Inductor_SMD.pretty/L_Changjiang_FTC404030S` |
| `PinHeader_1x14_P2.54mm_Vertical_IORow` | `Connector_PinHeader_2.54mm.pretty/PinHeader_1x14_P2.54mm_Vertical` |
| `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm` | `Package_DFN_QFN.pretty/QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm` |
| `USB_C_Receptacle_HRO_TYPE-C-31-M-12` | `Connector_USB.pretty/USB_C_Receptacle_HRO_TYPE-C-31-M-12` |
| `microSD_HC_Molex_104031-0811` | `Connector_Card.pretty/microSD_HC_Molex_104031-0811` |
| `microSD_HC_Molex_47219-2001` | `Connector_Card.pretty/microSD_HC_Molex_47219-2001` |

These footprint copies have project-local names, descriptions and/or 3D model
paths. The IO-row header also has trimmed courtyard and silkscreen, as recorded
in its description. Upstream: [KiCad footprints](https://gitlab.com/kicad/libraries/kicad-footprints)
and [KiCad 3D models](https://gitlab.com/kicad/libraries/kicad-packages3D).
