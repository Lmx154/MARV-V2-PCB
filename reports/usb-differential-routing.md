# USB differential routing settings

The `MARV-V2` project has a **0.36 mm track width / 0.20 mm
edge-to-edge gap** USB differential-pair preset. The USB netclass uses the same
values; its ordinary track width is also 0.36 mm. Copper clearance is
0.18 mm, differential via gap 0.25 mm, and vias are 0.60/0.30 mm.

## Manufacturer guidance

Raspberry Pi's [Hardware design with RP2350, §5.1, USB](https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf)
calls for approximately 90 ohm differential impedance, uninterrupted ground
directly beneath the pair, and 27 ohm series resistors close to the MCU. The
guide's 0.8 mm width / 0.15 mm gap example is for a different, 1 mm board and
must not be copied onto this four-layer board.

U20 is the RP2354B member of the RP2350 family. R22 and R23 are the series
resistors. They are 22 ohm (JLC Basic part C25092, shared with R58) rather than
27 ohm to avoid Extended-part fees; 22 ohm keeps the full-speed driver within the
USB impedance range. No numerical skew or uncoupled-length limit is imposed: the cited
guide does not specify one. Keep both paths short and symmetrical, including
the short MCU-to-resistor portions.

## Geometry calculation and limits

The saved stackup has 0.2104 mm of PP-7628, relative permittivity 4.4, between
F.Cu and In1.Cu (GND), with 0.035 mm outer copper. Using the official
[KiCad 10 coupled-microstrip calculator implementation](https://github.com/KiCad/kicad-source-mirror/blob/10.0/common/transline_calculations/coupled_microstrip.cpp)
at 12 MHz, with an open upper half-space, gives:

| Width | Gap | Calculated differential impedance |
| --- | --- | --- |
| 0.30 mm (not used) | 0.20 mm | 98.97 ohm |
| Selected 0.36 mm | 0.20 mm | 90.27 ohm |

This is a nominal microstrip estimate, not a controlled-impedance fabrication
guarantee. The model does not include solder mask, nearby same-layer copper,
etched trace shape or manufacturing tolerances. At 0.045 mm copper with the
other inputs unchanged, the selected geometry gives 89.86 ohm. Confirm actual
finished copper, dielectric and mask with the fabricator before ordering.

Use this geometry on **F.Cu over continuous In1.Cu GND**. Do not assume it is
valid on an inner layer or on B.Cu, whose adjacent layer is the power layer.
Inspect the ground reference along the complete route; a netclass cannot
enforce uninterrupted ground or calculate impedance. Keep pours and unrelated
signals away from the pair where practical, minimize vias, and allow short
symmetrical neck-downs at pads instead of moving components.

## KiCad pair recognition and routing

[KiCad recognizes pairs by matching names ending in +/− or P/N](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#routing-differential-pairs).
Plain DP/DM names would not be recognized as complementary pairs, so the
schematic global labels, PCB net names and netclass assignments use +/- names:

| Portion | D+ net | D− net |
| --- | --- | --- |
| J4 to R22/R23 | `USB_D+` | `USB_D-` |
| R22/R23 to U20 | `USB_RP_D+` | `USB_RP_D-` |

The reserved MCU netclass patterns are `USB_MCU_D+` / `USB_MCU_D-`. The MCU symbol
pin names (USB_DP, USB_DM) are the RP2354B function names and are unchanged.

Select the 0.36/0.20 mm
differential preset (or the USB netclass values), choose F.Cu, then press **6**
over either member of the desired pair to start Route Differential Pairs.
Route the connector and MCU portions separately because the resistors split
them into different nets.

## Validation

Read-only KiCad DRC on the saved board (`kicad-cli pcb drc --schematic-parity`)
reports 0 unconnected items and 0 schematic-parity findings. Three of its 22 errors
are `clearance` findings on the USB nets, against the 0.18 mm USB netclass
clearance: two between the D+ and D- tracks (0.14 mm actual) and one between a
USB_RP_D+ track and the V3V3_SYS pad 68 of U20 (0.168 mm actual). The full
violation breakdown is in [jlc-dfm-routing.md](jlc-dfm-routing.md).
