# J11 locking microSD socket

J11 is a Molex 47219-2001 (472192001), LCSC C164170: hinged metal lid,
closed and slid into the locked position.

- [Manufacturer datasheet](https://www.es.co.th/Schemetic/PDF/472192001.PDF), 3 pages, generated
  2025-04-07.
- [Manufacturer mechanical drawing](https://cdn.promelec.ru/upload/items/2020/09/01/472192001_sd.pdf),
  SD-47219-001 Rev. G, 1 page.
- [Molex locking sequence and part listing](https://www.content.molex.com/dxdam/literature/987651-8263.pdf).

The local footprint is copied from KiCad 10.0.6's
`Connector_Card:microSD_HC_Molex_47219-2001`, retaining its geometry and
numbering. The drawing's recommended pattern was checked: eight 0.8 × 1.5 mm
contact pads on 1.1 mm pitch, four 1.45 × 2.0 mm shield/mounting pads,
13.75 mm between side mounting-pad centers and 8.30 mm between rows.
All four mounting pads use SH and connect to GND. The KiCad footprint is
rotated 180 degrees relative to the drawing's land-pattern view.

Card pins: 1 DAT2, 2 DAT3, 3 CMD, 4 VDD, 5 CLK, 6 VSS, 7 DAT0, 8 DAT1.
The PIO native four-bit SD bus is on GPIO28–33, with all five 10k pull-ups,
R58 22 ohm clock damping and C64/C65 decoupling.

This connector has no card-detect switch, so there is no SD_DET net and no
detect pull-up; U20 GPIO35 is a no-connect spare.

Validation: zero ERC violations; the 48-GPIO and exact bus-net checks pass; all
101 components have assigned, resolved footprints with matching symbol pads, and
the footprint/model audit reports all 101 components OK. J11's 3D model is
project-authored (CC0); see the model provenance record
(`MARV_Packages.3dshapes/PROVENANCE.md`).

The socket needs clearance and access to lift and slide the lid.
