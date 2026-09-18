# Sensor and native SD schematic update

Validated 2026-09-17 using KiCad 10.0.6. Hardware/schematic only; no firmware or
PCB edits. Open the saved `MARV-V2.kicad_sch` project hierarchy; generated PDF/netlist
snapshots have been removed and can be re-exported from KiCad. The full GPIO reference is [PINOUT.md](../PINOUT.md).

## Electrical allocation

| Interface | Net | RP2354B GPIO | MCU pad | Device pin |
| --- | --- | --- | --- | --- |
| ADXL375, hardware SPI0 | ADXL_SCK | 2 | 79 | U23.14 SCL/SCLK |
| | ADXL_MOSI | 3 | 80 | U23.13 SDA/SDI |
| | ADXL_MISO | 4 | 1 | U23.12 SDO |
| | ADXL_CS | 14 | 13 | U23.7 CS |
| | ADXL_INT1 | 1 | 78 | U23.8 INT1 |
| | ADXL_INT2 | 21 | 21 | U23.9 INT2 |
| ICM-45686, hardware SPI1 | ICM_SCK | 10 | 8 | U21.13 AP_SCLK |
| | ICM_MOSI | 11 | 9 | U21.14 AP_SDI |
| | ICM_MISO | 8 | 6 | U21.1 AP_SDO |
| | ICM_CS | 7 | 4 | U21.12 AP_CS |
| | ICM_INT1 | 6 | 3 | U21.4 INT1 |
| | ICM_INT2 | 18 | 18 | U21.9 INT2/FSYNC/CLKIN |
| BMP581, hardware I2C0 | BARO_SCL | 9 | 7 | U22.2 SCL |
| | BARO_SDA | 12 | 11 | U22.4 SDA |
| | BARO_INT | 13 | 12 | U22.7 INT |
| microSD, PIO + DMA native four-bit SD | SD_CLK_MCU → R58 → SD_CLK | 26 | 27 | J11.5 CLK |
| | SD_CMD | 27 | 28 | J11.3 CMD |
| | SD_DAT0 | 28 | 36 | J11.7 DAT0 |
| | SD_DAT1 | 29 | 37 | J11.8 DAT1 |
| | SD_DAT2 | 30 | 38 | J11.1 DAT2 |
| | SD_DAT3 | 31 | 39 | J11.2 DAT3 |
| Card detect | None on Molex 47219-2001 | 35 unconnected | 44 | No detect pins |

The SD data GPIOs are consecutive and all six bus signals fit in GPIO26–31,
inside the GPIO16–31 overlap of both PIO windows. SPI0 serves ADXL375 only;
SPI1 serves ICM-45686 only. No sensor or microSD clock/data net is shared.

## Bias, mode selection and damping

| Nets | Resistors | Value | Supply |
| --- | --- | --- | --- |
| ADXL_CS, ICM_CS | R51, R48 | 10k each | V3V3_ANA |
| BARO_SCL, BARO_SDA | R50, R57 | 4.7k each | V3V3_ANA |
| SD_CMD, SD_DAT0–SD_DAT3 | R36–R40 | 10k each | V3V3_SYS |
| SD_CLK_MCU to SD_CLK | R58 | 22 ohm series; tuning range 0–33 ohm | No pull resistor |

BMP581 CSB (U22.6) is hard-wired to VDDIO/V3V3_ANA and ADDR/SDO (U22.5) to
GND, selecting I2C with 7-bit address 0x46. Its new `BMP581_I2C` symbol variant
models the address pin as an input; the generic symbol is preserved. There are
no pulls on either sensor SPI clock/data bus, no clock pull on SD, and no bus
pull-downs. All five sensor interrupt signals terminate at distinct MCU GPIOs.

R50 is repurposed from the former 10k barometer CS pull-up to a 4.7k SCL pull-up.
R57 and R58 are new 0402 parts. TP5 now probes BARO_SDA. Sensor decoupling,
sensor/system power separation and card decoupling are retained. The subsequent
locking-connector update removes the old card-detect circuit.

## Validation

- KiCad ERC: **0 errors, 0 warnings**. Re-run the README check commands for current results.
- Freshly exported netlist: all 48 GPIO assignments and every bus's
  exact endpoint set pass `tools/check_power_netlist.py`. The checks include
  chip-select pull-ups, I2C pull-up values and rail, I2C mode/address straps,
  consecutive SD data GPIOs, PIO window, independent interrupts, and the clock
  resistor's two separate nets with no pull or bypass.
- Fault injection into temporary netlists confirmed that the checker rejects
  a clock pull resistor, shared SPI data, a missing SD pull-up, a wrong I2C
  pull-up value, and combined sensor interrupt lines.
- `tools/audit_footprints.py`: **107 components OK**, including the new J11 model.
- Compared every pre-existing pin against the starting netlist: each connection
  is unchanged or matches an explicitly intended bus/GPIO reassignment. Existing component UUID paths are retained. The bus revision added R57/R58;
  the locking-connector revision changes the J11 footprint and removes R41.
- Power, external IO, USB/debug and root schematic files remain byte-identical
  to the starting workspace. QSPI sheet changes are annotation-only, removing
  its obsolete description of the microSD interface.
- Rendered MCU, ICM, ADXL, BMP581 and microSD pages were visually reviewed.
- PCB file is byte-identical to the starting workspace. SHA-256:
  `2b4a53d8f419f890fc76ce7563b38e38ff1111ec8dd953fc5a8fe4f6d3b97b4e`.

## PCB handoff

The owner must update the PCB from the schematic, add R57/R58 and route it.
The PCB still contains the previous communication connections. Place R58
physically next to U20 GPIO26 with a short source stub.

Routing priority: ICM SPI, ADXL SPI, SD clock/native bus, BMP581 I2C. Keep these
signals short and direct over continuous ground, away from switching-node
copper and external power wiring. Avoid unnecessary vias
and long stubs. The current DFM profile uses the common 0.20 mm signal class for these buses.

LED_DATA moved GPIO3 → GPIO33; ICM_INT2 moved GPIO2 → GPIO18; ADXL_CS moved
GPIO4 → GPIO14. SD clock/command moved GPIO33/34 → GPIO26/27. ADXL_INT2 now
uses GPIO21. GPIO34, GPIO35 and GPIO37 remain unconnected; GPIO44–47 remain exposed
spares. External connector assignments are unchanged.

Manufacturing exports and earlier PCB reports remain tied to the old PCB and
must be regenerated after the owner's layout update. The current schematic
component inventory is `power_bom.csv`.

## Manufacturer references

- [RP2350 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf):
  Section 1.2.3 GPIO alternate functions and PIO GPIOBASE (0 or 16).
- [BMP581 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp581-ds004.pdf):
  Sections 5.1, 5.6 and 6.2.3, I2C protocol selection, address strap and wiring.
- Offline sensor datasheets and source index: [datasheets/README.md](../datasheets/README.md).

## Locking microSD connector update

J11 is now Molex 47219-2001 / LCSC C164170, a hinged socket with a lid that
slides to lock. The manufacturer datasheet is saved at
[datasheets/472192001.pdf](../datasheets/472192001.pdf), with its
[mechanical drawing](../datasheets/472192001-drawing.pdf).
The connector has no detect switch: R41 and SD_DET are removed and GPIO35
becomes an unconnected spare. Native SD CLK/CMD/DAT0–DAT3, power, shield
ground and the required pulls/damping are unchanged.

Latest checks: ERC zero violations; all 48 GPIO and exact bus-net checks pass;
107 components have matching footprint pads. An exact-part LCSC/EasyEDA 3D model is now stored locally and attached to
the new footprint. All 107 components pass the footprint/model audit.

The PCB is unchanged. Replace its J11 footprint and remove R41 when updating
from the schematic; the locking connector is not footprint-compatible with
the old socket. Provide lid-opening access and verify the lid is slid fully
into the locked position. This replacement does not establish a measured
rocket-flight shock/vibration qualification.

Subsequent 3D update: J11 now displays the locking-socket model on the PCB.
Only its model reference/transform changed; PCB pads, nets and placement
remain as before. Use KiCad's 3D viewer for a current preview; model appearance does not validate pad compatibility.
