# MARV V2 signal trace widths

Reviewed 2026-09-21 against the saved schematic netlist and PCB pad connections.

## Installed recommendation

Use **0.15 mm (about 6 mil)** for the 55 explicitly assigned `Signal` nets below.
This is a board-specific engineering choice, not an RP2354B datasheet minimum.
Ordinary logic interconnects do not need 0.20 mm for current capacity. Their
length, edge rate, loading and return path still matter, especially for SD and
QSPI clocks. Keep those paths short over a continuous reference; this width
change is not a timing or signal-integrity qualification.

The project and managed DFM profile now contain the `Signal` class and exact net
assignments. Clearance remains **0.15 mm**, vias remain **0.60 / 0.30 mm**, and
the global track minimum remains **0.15 mm**. The width menu is now 0.15, 0.20,
0.50 and 1.00 mm, plus the netclass selector. Power and USB classes are unchanged.
The existing signal tracks have now also been resized: **511 segments across all
55 nets are 0.15 mm** (509 previously at 0.20 mm and two LED_DIN segments at
0.50 mm). Only track-width fields changed; paths, endpoints, layers, vias, pads,
zones, power/USB tracks and schematic files were preserved. A read-only DRC
reports zero unconnected items and 531 existing findings, down from 540.
Recovery copy: `.dfm-backups/signal-widths-bml1p_w8/MARV-V2.kicad_pcb`.

## Exact 0.15 mm net list

Every name in this table is an exact assignment, not a wildcard.

| Function | Nets |
| --- | --- |
| ICM SPI and interrupts | `ICM_SCK`, `ICM_MOSI`, `ICM_MISO`, `ICM_CS`, `ICM_INT1`, `ICM_INT2` |
| ADXL SPI and interrupts | `ADXL_SCK`, `ADXL_MOSI`, `ADXL_MISO`, `ADXL_CS`, `ADXL_INT1`, `ADXL_INT2` |
| Barometer I2C and interrupt | `BARO_SCL`, `BARO_SDA`, `BARO_INT` |
| External magnetometer I2C | `MAG_SCL`, `MAG_SDA` |
| UART and ESC telemetry | `GPS_RX`, `GPS_TX`, `ELRS_RX`, `ELRS_TX`, `ESC_TELEM`, `ESC_TELEM_RX` |
| Actuator control signals | `PWM1`, `PWM2`, `PWM3`, `PWM4`, `PWM5`, `PWM6`, `PWM7`, `PWM8` |
| Spare logic IO | `IO_GPIO44`, `IO_GPIO45`, `IO_GPIO46`, `IO_GPIO47` |
| SWD debug | `SWCLK`, `SWDIO` |
| microSD | `SD_CLK_MCU`, `SD_CLK`, `SD_CMD`, `SD_DAT0`, `SD_DAT1`, `SD_DAT2`, `SD_DAT3` |
| QSPI and boot select | `QSPI_SCLK`, `QSPI_SD0`, `QSPI_SD1`, `QSPI_SD2`, `QSPI_SD3`, `FLASH_CS1`, `QSPI_SS` |
| LED logic and buttons | `LED_DATA`, `LED_DIN`, `MCU_RUN`, `BOOT_BTN` |

PWM carries control signals only; no actuator supply current flows in these nets.
The spare IO recommendation assumes logic/sense use, not direct load power.
Pull-ups on data nets do not turn them into power-distribution nets. Both sides
of series resistors R54, R55 and R58 are included. The optional U24 QSPI interface
still needs timing review at its intended clock rate when populated.

## Nets kept out of the thinner class

| Group | Nets | Treatment |
| --- | --- | --- |
| Main power | `5V_IN`, `V5_SYS`, `V3V3_SYS`, `U7_SW` | Existing Power default, 1.00 mm |
| Local power and ground | `USB_VBUS`, `V3V3_ANA`, `DVDD`, `VREG_LX`, `VREG_AVDD`, `GND` | Existing LocalPower default, 0.50 mm |
| USB data | `USB_DP`, `USB_DM`, `USB_DP_RP`, `USB_DM_RP` (also reserved `_MCU` names) | Existing USB default, 0.30 mm width / 0.20 mm gap; verify actual impedance |
| Crystal | `XIN`, `XOUT`, `XTAL_DRV` | Keep Default 0.20 mm; separate oscillator layout review |
| Analog/sense | `VBAT`, `VBAT_SENSE`, `VBUS_SENSE`, `CURR_SENSE_RAW`, `CURR_SENSE` | Keep Default 0.20 mm; possible later thinning after noise/layout review |
| Other | `U7_BST`, `U7_EN`, `USB_CC1`, `USB_CC2`, `USB_LED_A` | Keep Default 0.20 mm; outside this digital-signal change |

Defaults in this table are not measurements of existing copper. Existing power
branches include 0.20, 0.30 and 0.50 mm widths and were preserved. A short 0.30 mm
MCU supply branch is a different case from a shared supply trunk: assess current,
length, voltage drop and decoupling together. The LX switching loop needs the
manufacturer's layout treatment regardless of its netclass width.

USB is data, but it is deliberately excluded from blanket thinning. Raspberry
Pi recommends approximately **90 ohm differential impedance** and an uninterrupted
ground reference. Its example geometry belongs to its example board, not this
four-layer stackup. The existing 0.30/0.20 setting is not verified impedance.
[Raspberry Pi hardware design guide, section 5.1](https://pip-assets.raspberrypi.com/categories/1214-rp2350/documents/RP-008280-DS-1-hardware-design-with-rp2350.pdf?disposition=inline)

## How much thinner is practical?

| Width | Recommendation for this board |
| --- | --- |
| 0.20 mm (~8 mil) | Conservative previous signal default |
| **0.15 mm (~6 mil)** | Installed signal default; already within project rules |
| 0.125 mm (~5 mil) | Possible candidate for specific tight escapes; would require a deliberate rule revision and layout review |
| 0.10 mm (~4 mil) | Fabrication-capable with the specified copper, but not the chosen general default |

JLC publishes a 0.09 mm minimum width/space for four-or-more-layer FR4 with
0.5/1 oz copper. That manufacturing floor does not establish electrical suitability
or require using it. These recommendations assume the saved 1 oz outer / 0.5 oz
inner copper; heavier copper has different limits.
[JLC copper-weight and trace/space table](https://jlcpcb.com/help/article/jlcpcb-copper-weight)

Going from 0.20 to 0.15 mm reduces copper width by **25%**. At unchanged 0.15 mm
clearance, parallel-track center pitch falls from 0.35 to 0.30 mm: approximately
**14% less pitch**, not 25% less routing area. Ten parallel tracks occupy 3.35 mm
versus 2.85 mm between their outside edges, saving 0.50 mm. Vias and pad escapes
may still set the bottleneck; their sizes and clearances have not changed.

## Using the defaults in KiCad

Open the project again and use **netclass width** while routing. Disable automatic
inheritance of the starting track width if continuing an existing 0.20 mm segment
causes the router to keep that width.

Netclass width is a routing default, not a hard maximum and not an automatic
conversion of existing tracks. The owner subsequently requested conversion,
and the 511 existing signal segments have now been changed explicitly. A wider signal segment is not inherently a DRC
error. The owner can use **Edit Track & Via Properties** filtered to the `Signal`
netclass to change existing signal tracks to 0.15 mm, with only tracks selected
and vias excluded. Inspect the result and run DRC after changing copper. Avoid
an unfiltered board-wide width change because power and USB must keep their own
geometry. That track-only conversion has now been performed at the owner's explicit request; it did not move or reroute anything.
[KiCad PCB Editor documentation](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html)

The managed settings source is `config/dfm/jlcpcb.json`; `python3 tools/dfm.py
--check` verifies agreement with the project. A future profile application will
retain these signal assignments.
