# MARV V2 KiCad parts

This project keeps its nonstandard KiCad parts in the project directory. Open
`MARV-V2.kicad_pro` normally; KiCad reads `sym-lib-table` and `fp-lib-table`
automatically, so there is nothing to install globally.

## Parts

| Part | Symbol to search for | Footprint source |
| --- | --- | --- |
| BMI088 | `BMI088` in `Sensor_Motion` | KiCad 10 official `Package_LGA` library |
| RP2354A | `RP2354A` in `MCU_RaspberryPi` | KiCad 10 official 60-pin QFN, 7 x 7 mm |
| RP2354B | `RP2354B` in `MCU_RaspberryPi` | KiCad 10 official 80-pin QFN, 10 x 10 mm |
| BMP581 | `BMP581` in `MARV_Sensors` | Project-local Bosch recommended land pattern |
| ADXL375 | `ADXL375` in `MARV_Sensors` | Project-local Analog Devices recommended land pattern |

RP2354 is available in two packages. Use RP2354A for 30 GPIO in a 60-pin 7 x 7
mm QFN, or RP2354B for 48 GPIO in an 80-pin 10 x 10 mm QFN. Both contain 2 MB
of stacked flash.

## Important layout notes

- The BMP581 footprint follows Bosch datasheet BST-BMP581-DS004 revision 1.13.
  Do not place vias or traces beneath the package, and keep solder mask and
  contamination away from the pressure port. Verify assembly-house solder-mask
  capabilities for the 0.2 mm nominal pad gaps.
- The ADXL375 footprint follows Figure 38 of the Rev. B datasheet rather than
  KiCad's generic 3 x 5 mm LGA footprint. Place the sensor close to a rigid PCB
  mounting point and keep its orientation marker visible.
- The BMI088 and both RP2354 symbols already have official KiCad footprints
  assigned. Do not download duplicates from third-party library sites.

## First schematic step

In Schematic Editor press `A`, then search the symbol names in the table above.
The project-local BMP581 and ADXL375 symbols already carry their matching
footprint assignments and datasheet links.
