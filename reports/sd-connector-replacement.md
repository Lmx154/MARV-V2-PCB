# J11 locking microSD replacement

J11 now selects Molex 47219-2001 (472192001), LCSC C164170: hinged metal lid,
closed and slid into the locked position. The change is schematic/library/BOM
only; a subsequent 3D update changes just J11's PCB model node, retaining
all PCB pads, nets and placement.

- [Manufacturer datasheet](../datasheets/472192001.pdf), 3 pages, generated
  2025-04-07; retrieved from https://www.es.co.th/Schemetic/PDF/472192001.PDF.
- [Manufacturer mechanical drawing](../datasheets/472192001-drawing.pdf),
  SD-47219-001 Rev. G, 1 page; retrieved from
  https://cdn.promelec.ru/upload/items/2020/09/01/472192001_sd.pdf.
- [Molex locking sequence and part listing](https://www.content.molex.com/dxdam/literature/987651-8263.pdf).

The local footprint is copied from KiCad 10.0.6's
`Connector_Card:microSD_HC_Molex_47219-2001`, retaining its geometry and
numbering. The drawing's recommended pattern was checked: eight 0.8 × 1.5 mm
contact pads on 1.1 mm pitch, four 1.45 × 2.0 mm shield/mounting pads,
13.75 mm between side mounting-pad centers and 8.30 mm between rows.
All four mounting pads use SH and connect to GND. The KiCad footprint is
rotated 180 degrees relative to the drawing's land-pattern view.

Card pins remain 1 DAT2, 2 DAT3, 3 CMD, 4 VDD, 5 CLK, 6 VSS, 7 DAT0, 8 DAT1.
The PIO native four-bit SD bus stays on GPIO26–31 with all five 10k pull-ups,
R58 22 ohm clock damping and C64/C65 decoupling retained.

This connector has no card-detect switch. The schematic removes R41 and
SD_DET, and marks U20 GPIO35 unconnected. GPIO34/35/37 are now unexposed
spares. All other electrical connections are preserved.

Validation: zero ERC violations; 48-GPIO and exact bus-net checks pass; all
107 components have assigned, resolved footprints with matching symbol pads.
The footprint/model audit now reports all 107 components OK. An exact-part
LCSC/EasyEDA STEP model was retrieved and attached; see the model provenance
record for source and alignment. The old connector model is no longer displayed.

PCB handoff: update J11 to the new footprint and remove R41. It is not a
land-pattern-compatible substitution. Provide clearance and access to lift
and slide the lid. The owner retains control of placement and routing.

Inspect the current model in KiCad's 3D viewer. The PCB
footprint pads still require the owner's update from the schematic.

---

Original MARV V2 documentation: [CC0 1.0](../LICENSES/CC0-1.0.txt). No attribution required; provided as-is. [Licensing and third-party exceptions](../LICENSE.md).
