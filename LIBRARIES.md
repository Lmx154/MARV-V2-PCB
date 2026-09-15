# MARV V2 KiCad parts

Nonstandard KiCad parts live in the project directory. Open `MARV-V2.kicad_pro` normally; KiCad reads `sym-lib-table` and `fp-lib-table` automatically, so there is nothing to install globally.

## Parts

| Part | Symbol to search for | Footprint source |
| --- | --- | --- |
| BMI088 | `BMI088` in `Sensor_Motion` | KiCad 10 official `Package_LGA` library |
| RP2354A | `RP2354A` in `MCU_RaspberryPi` | KiCad 10 official 60-pin QFN, 7 x 7 mm, 30 GPIO |
| RP2354B | `RP2354B` in `MCU_RaspberryPi` | KiCad 10 official 80-pin QFN, 10 x 10 mm, 48 GPIO |
| BMP581 | `BMP581` in `MARV_Sensors` | Project-local Bosch recommended land pattern |
| ADXL375 | `ADXL375` in `MARV_Sensors` | Project-local Analog Devices recommended land pattern |
| XT30PW-M (J3) | `Conn_01x02` in `Connector_Generic` | KiCad 10 official `Connector_AMASS` footprint; pad 1 is the "-" terminal |
| TPS2121 (U25) | `TPS2121RUX` in `MARV_Power` | KiCad 10 official `Texas_VQFN-HR-12_2x2.5mm_P0.5mm` footprint |

Both RP2354 packages contain 2 MB of stacked flash.

## Important layout notes

- The BMP581 footprint follows Bosch datasheet BST-BMP581-DS004 revision 1.13. Do not place vias or traces beneath the package, and keep solder mask and contamination away from the pressure port. Verify assembly-house solder-mask capabilities for the 0.2 mm nominal pad gaps.
- The ADXL375 footprint follows Figure 38 of the Rev. B datasheet rather than KiCad's generic 3 x 5 mm LGA footprint. Place the sensor close to a rigid PCB mounting point and keep its orientation marker visible.
- Footprint pad order matches ADI CC-14-1 top view (pin 1 top-left, 1-6 down left edge, 7 bottom tab, 8-13 up right edge, 14 top tab); confirm pin-1 corner against the ADI outline drawing in the 3D viewer before fab.
- The BMI088 and both RP2354 symbols already have official KiCad footprints assigned. Do not download duplicates from third-party library sites.

## First schematic step

Press `A` in Schematic Editor and search the symbol names above. The project-local BMP581 and ADXL375 symbols already carry their matching footprint assignments and datasheet links.
