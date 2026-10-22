# USB differential routing settings — 2026-10-21

The active `MARV-V2` project now has a **0.36 mm track width / 0.20 mm
edge-to-edge gap** USB differential-pair preset. The USB netclass uses the same
values; its ordinary track width is also 0.36 mm. Copper clearance remains
0.18 mm, differential via gap remains 0.25 mm, and vias remain 0.60/0.30 mm.
These settings supersede the USB starting geometry in older routing reports.

## Manufacturer guidance

Raspberry Pi's [Hardware design with RP2350, §5.1, USB](https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf)
calls for approximately 90 ohm differential impedance, uninterrupted ground
directly beneath the pair, and 27 ohm series resistors close to the MCU. The
guide's 0.8 mm width / 0.15 mm gap example is for a different, 1 mm board and
must not be copied onto this four-layer board.

U20 is the RP2354B member of the RP2350 family. R22 and R23 already provide the
27 ohm series resistors. No component values, placements or copper geometry
were changed. No numerical skew or uncoupled-length limit was added: the cited
guide does not specify one. Keep both paths short and symmetrical, including
the short MCU-to-resistor portions.

## Geometry calculation and limits

The saved stackup has 0.2104 mm of PP-7628, relative permittivity 4.4, between
F.Cu and In1.Cu (GND), with 0.035 mm outer copper. Using the official
[KiCad 10 coupled-microstrip calculator implementation](https://github.com/KiCad/kicad-source-mirror/blob/10.0/common/transline_calculations/coupled_microstrip.cpp)
at 12 MHz, with an open upper half-space, gives:

| Width | Gap | Calculated differential impedance |
| --- | --- | --- |
| Previous 0.30 mm | 0.20 mm | 98.97 ohm |
| Selected 0.36 mm | 0.20 mm | 90.27 ohm |

This is a nominal microstrip estimate, not a controlled-impedance fabrication
guarantee. The model does not include solder mask, nearby same-layer copper,
etched trace shape or manufacturing tolerances. At 0.045 mm copper with the
other inputs unchanged, the selected geometry gives 89.86 ohm. Confirm actual
finished copper, dielectric and mask with the fabricator before ordering.
No stackup or fabrication-service options were changed.

Use this geometry on **F.Cu over continuous In1.Cu GND**. Do not assume it is
valid on an inner layer or on B.Cu, whose adjacent layer is the power layer.
Inspect the ground reference along the complete route; a netclass cannot
enforce uninterrupted ground or calculate impedance. Keep pours and unrelated
signals away from the pair where practical, minimize vias, and allow short
symmetrical neck-downs at pads instead of moving components.

## KiCad pair recognition and routing

[KiCad recognizes pairs by matching names ending in +/− or P/N](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#routing-differential-pairs).
The former DP/DM names were not recognized as complementary pairs.
The schematic global labels, PCB net names and netclass assignments now agree:

| Portion | D+ net | D− net |
| --- | --- | --- |
| J4 to R22/R23 | `USB_D+` (was `USB_DP`) | `USB_D-` (was `USB_DM`) |
| R22/R23 to U20 | `USB_RP_D+` (was `USB_DP_RP`) | `USB_RP_D-` (was `USB_DM_RP`) |

The unused reserved MCU netclass patterns were also normalized to
`USB_MCU_D+` / `USB_MCU_D-`. MCU symbol pin names/functions remain unchanged.

Reopen the saved project/board to load the settings. Select the 0.36/0.20 mm
differential preset (or the USB netclass values), choose F.Cu, then press **6**
over either member of the desired pair to start Route Differential Pairs.
Route the connector and MCU portions separately because the resistors split
them into different nets. Existing tracks keep their original widths and paths.

## Validation

Validation compares the files and read-only KiCad DRC against a snapshot taken
immediately before this change, preserving the owner's existing local edits.
Before and after DRC have identical findings after normalizing the renamed nets:
226 DRC violations, 12 unconnected items and 19 schematic-parity findings.
No new findings were introduced; the existing board is not DRC-clean.
The PCB and both schematic files are byte-identical to the snapshot apart from
the intended net/label substitutions. The custom rules are unchanged. Project
settings differ only in USB widths, the new preset and the USB name assignments.
