# MARV V2 GPIO reference

The schematic records the wiring. Keep this reference and `tools/check_power_netlist.py` aligned
when changing GPIOs. Power assignments
for the IO block are in [DESIGN_SPEC.md](DESIGN_SPEC.md).

Source: RP2350 Datasheet, Section 1.2.3, Table 3 "General Purpose Input/Output (GPIO) Bank 0 Functions"
(F1 SPI, F2 UART, F3 I2C, F4 PWM, F5 SIO, F6-F8 PIO0/1/2, F9 clock/QMI/trace, F10 USB, F11 UART aux).
ADC0-7 are GPIO40-47 on the RP2350B/RP2354B (QFN-80) only. All GPIO are 3.3 V, not 5 V tolerant.

External IO leaves the board on the J6/J7/J8 IO block (right front edge, signal/power/GND columns), plus
two solder-pad rows on the back (B.Cu): the ESC pad row J3 and the DBG pads J10.

## Table A — every GPIO

| GPIO | Net | Used as | Datasheet alternates (F1 SPI / F2 UART / F3 I2C / F4 PWM / F9-F11) | Status |
| --- | --- | --- | --- | --- |
| 0 | FLASH_CS1 | QMI CS1n (F9) | SPI0 RX, UART0 TX, I2C0 SDA, PWM0 A, USB OVCUR DET | assigned (flash/PSRAM socket U24) |
| 1 | ADXL_INT1 | GPIO input (ADXL INT1) | SPI0 CSn, UART0 RX, I2C0 SCL, PWM0 B, USB VBUS DET | assigned |
| 2 | ADXL_SCK | SPI0 SCK (F1) | PWM1 A, SPI0 SCK, UART0 CTS, I2C1 SDA, USB VBUS EN, UART0 TX (F11) | assigned |
| 3 | ADXL_MOSI | SPI0 TX (F1) | PWM1 B, SPI0 TX, UART0 RTS, I2C1 SCL, USB OVCUR DET, UART0 RX (F11) | assigned |
| 4 | ADXL_MISO | SPI0 RX (F1) | PWM2 A, SPI0 RX, UART1 TX, I2C0 SDA, USB VBUS DET | assigned |
| 5 | PWM8 | PWM2 B (F4) | SPI0 CSn, UART1 RX, I2C0 SCL, USB VBUS EN | assigned (servo S8) |
| 6 | ICM_INT1 | GPIO input (ICM INT1) | I2C1 SDA, SPI0 SCK, UART1 CTS, PWM3 A, USB OVCUR DET, UART1 TX (F11) | assigned |
| 7 | ICM_CS | GPIO (ICM CS) | I2C1 SCL, SPI0 TX, UART1 RTS, PWM3 B, USB VBUS DET, UART1 RX (F11) | assigned |
| 8 | ICM_MISO | SPI1 RX (F1) | UART1 TX, I2C0 SDA, PWM4 A, QMI CS1n, USB VBUS EN | assigned |
| 9 | BARO_SCL | I2C0 SCL (F3) | UART1 RX, SPI1 CSn, I2C0 SCL, PWM4 B, USB OVCUR DET | assigned |
| 10 | ICM_SCK | SPI1 SCK (F1) | PWM5 A, UART1 CTS, I2C1 SDA, USB VBUS DET, UART1 TX (F11) | assigned |
| 11 | ICM_MOSI | SPI1 TX (F1) | PWM5 B, UART1 RTS, I2C1 SCL, USB VBUS EN, UART1 RX (F11) | assigned |
| 12 | BARO_SDA | I2C0 SDA (F3) | UART0 TX, SPI1 RX, I2C0 SDA, PWM6 A, CLOCK GPIN0, USB OVCUR DET | assigned |
| 13 | BARO_INT | GPIO in | UART0 RX, SPI1 CSn, I2C0 SCL, PWM6 B, CLOCK GPOUT0, USB VBUS DET | assigned |
| 14 | ADXL_CS | GPIO (ADXL CS) | PWM7 A, SPI1 SCK, UART0 CTS, I2C1 SDA, CLOCK GPIN1, USB VBUS EN, UART0 TX (F11) | assigned |
| 15 | PWM7 | PWM7 B (F4) | SPI1 TX, UART0 RTS, I2C1 SCL, CLOCK GPOUT1, USB OVCUR DET, UART0 RX (F11) | assigned (servo S7) |
| 16 | ELRS_RX | UART0 TX (F2) | SPI0 RX, I2C0 SDA, PWM0 A, USB VBUS DET | assigned (J6 R1) |
| 17 | ELRS_TX | UART0 RX (F2) | SPI0 CSn, I2C0 SCL, PWM0 B, USB VBUS EN | assigned (J6 T1) |
| 18 | ICM_INT2 | GPIO input (ICM INT2) | SPI0 SCK, UART0 CTS, I2C1 SDA, PWM1 A, USB OVCUR DET, UART0 TX (F11) | assigned |
| 19 | PWM6 | PWM1 B (F4) | SPI0 TX, UART0 RTS, I2C1 SCL, QMI CS1n, USB VBUS DET, UART0 RX (F11) | assigned (servo S6) |
| 20 | PWM5 | PWM2 A (F4) | SPI0 RX, UART1 TX, I2C0 SDA, CLOCK GPIN0, USB VBUS EN | assigned (servo S5) |
| 21 | ADXL_INT2 | GPIO input (ADXL INT2) | SPI0 CSn, UART1 RX, I2C0 SCL, PWM2 B, CLOCK GPOUT0, USB OVCUR DET | assigned |
| 22 | MAG_SDA | I2C1 SDA (F3) | SPI0 SCK, UART1 CTS, PWM3 A, CLOCK GPIN1, USB VBUS DET, UART1 TX (F11) | assigned (J6 SDA) |
| 23 | MAG_SCL | I2C1 SCL (F3) | SPI0 TX, UART1 RTS, PWM3 B, CLOCK GPOUT1, USB VBUS EN, UART1 RX (F11) | assigned (J6 SCL) |
| 24 | GPS_RX | UART1 TX (F2) | SPI1 RX, I2C0 SDA, PWM4 A, CLOCK GPOUT2, USB OVCUR DET | assigned (J6 R0) |
| 25 | GPS_TX | UART1 RX (F2) | SPI1 CSn, I2C0 SCL, PWM4 B, CLOCK GPOUT3, USB VBUS DET | assigned (J6 T0) |
| 26 | — (unexposed spare, no-connect) | GPIO | SPI1 SCK, UART1 CTS, I2C1 SDA, PWM5 A, USB VBUS EN, UART1 TX (F11) | spare, not exposed (no-connect). Was SD_CLK_MCU; the SD bus moved to GPIO28–33 so it meets J11 from the MCU's top-left corner |
| 27 | — (unexposed spare, no-connect) | GPIO | SPI1 TX, UART1 RTS, I2C1 SCL, PWM5 B, USB OVCUR DET, UART1 RX (F11) | spare, not exposed (no-connect). Was SD_CMD |
| 28 | SD_DAT0 | PIO native SD DAT0 | SPI1 RX, UART0 TX, I2C0 SDA, PWM6 A, USB VBUS DET | assigned |
| 29 | SD_DAT1 | PIO native SD DAT1 | SPI1 CSn, UART0 RX, I2C0 SCL, PWM6 B, USB VBUS EN | assigned |
| 30 | SD_DAT2 | PIO native SD DAT2 | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM7 A, USB OVCUR DET, UART0 TX (F11) | assigned |
| 31 | SD_DAT3 | PIO native SD DAT3 | SPI1 TX, UART0 RTS, I2C1 SCL, PWM7 B, USB VBUS DET, UART0 RX (F11) | assigned |
| 32 | SD_CLK_MCU | PIO native SD clock, through R58 to SD_CLK | SPI0 RX, UART0 TX, I2C0 SDA, PWM8 A, USB VBUS EN | assigned |
| 33 | SD_CMD | PIO native SD command | SPI0 CSn, UART0 RX, I2C0 SCL, PWM8 B, USB OVCUR DET | assigned |
| 34 | ESC_TELEM_RX | PIO UART RX | SPI0 SCK, UART0 CTS, I2C1 SDA, PWM9 A, USB VBUS DET, UART0 TX (F11) | assigned (ESC TX pad) |
| 35 | — (unexposed spare, no-connect) | GPIO | SPI0 TX, UART0 RTS, I2C1 SCL, PWM9 B, USB VBUS EN, UART0 RX (F11) | spare, not exposed (no-connect) |
| 36 | PWM4 | DShot via PIO | SPI0 RX, UART1 TX, I2C0 SDA, PWM10 A, USB OVCUR DET | assigned (ESC M4) |
| 37 | PWM3 | DShot via PIO | SPI0 CSn, UART1 RX, I2C0 SCL, PWM10 B, USB VBUS DET | assigned (ESC M3) |
| 38 | PWM2 | DShot via PIO | SPI0 SCK, UART1 CTS, I2C1 SDA, PWM11 A, USB VBUS EN, UART1 TX (F11) | assigned (ESC M2) |
| 39 | PWM1 | DShot via PIO | SPI0 TX, UART1 RTS, I2C1 SCL, PWM11 B, USB OVCUR DET, UART1 RX (F11) | assigned (ESC M1) |
| 40 | VBUS_SENSE | ADC0 | SPI1 RX, UART1 TX, I2C0 SDA, PWM8 A, USB VBUS DET | assigned |
| 41 | CURR_SENSE | ADC1 | SPI1 CSn, UART1 RX, I2C0 SCL, PWM8 B, USB VBUS EN | assigned (ESC CURR pad) |
| 42 | VBAT_SENSE | ADC2 | SPI1 SCK, UART1 CTS, I2C1 SDA, PWM9 A, USB OVCUR DET, UART1 TX (F11) | assigned |
| 43 | LED_DATA | PIO (WS2812C, window 16–47) | SPI1 TX, UART1 RTS, I2C1 SCL, PWM9 B, USB VBUS DET, UART1 RX (F11) | assigned |
| 44 | IO_GPIO44 | GPIO / ADC4 | SPI1 RX, UART0 TX, I2C0 SDA, PWM10 A, USB VBUS EN | spare, on IO block row 11 |
| 45 | IO_GPIO45 | GPIO / ADC5 | SPI1 CSn, UART0 RX, I2C0 SCL, PWM10 B, USB OVCUR DET | spare, on IO block row 12 |
| 46 | IO_GPIO46 | GPIO / ADC6 | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM11 A, USB VBUS DET, UART0 TX (F11) | spare, on IO block row 13 |
| 47 | IO_GPIO47 | GPIO / ADC7 | SPI1 TX, UART0 RTS, I2C1 SCL, PWM11 B, QMI CS1n, USB VBUS EN, UART0 RX (F11) | spare, on IO block row 14 |


## Table B — spare GPIOs

Four exposed GPIOs remain on J6 rows 11–14: GPIO44–47. GPIO26, GPIO27 and GPIO35 are
unexposed and have no-connect flags. All other GPIOs have assigned functions.

| GPIO | Exposed | Useful alternates | Constraint |
| --- | --- | --- | --- |
| 44 | J6 row 11 | ADC4, PWM10 A, UART0 TX | SPI1 and I2C0 already serve onboard sensors |
| 45 | J6 row 12 | ADC5, PWM10 B, UART0 RX | Hardware UART0 already serves ELRS |
| 46 | J6 row 13 | ADC6, PWM11 A | PWM11 A is shared with GPIO38 |
| 47 | J6 row 14 | ADC7, PWM11 B | PWM11 B is shared with GPIO39 |
| 26 | No | PWM5 A, SPI1 SCK, PIO, GPIO | Needs a schematic connection before use |
| 27 | No | PWM5 B, SPI1 TX, PIO, GPIO | Needs a schematic connection before use |
| 35 | No | PWM9 B, PIO, GPIO, UART0 RX (F11) | Needs a schematic connection before use |

SPI0 and SPI1 are dedicated to ADXL375 and ICM-45686 respectively. I2C0 serves
BMP581; I2C1 serves the external magnetometer. No unused hardware SPI, I2C or UART
controller remains. Pin alternate functions do not create extra controllers.

## Table C — peripheral ledger

| Peripheral | GPIOs | Device / hardware requirement |
| --- | --- | --- |
| SPI0 | SCK 2, MOSI/TX 3, MISO/RX 4; CS 14 | ADXL375 only, four-wire SPI; R51 10k CS pull-up to V3V3_ANA |
| SPI1 | SCK 10, MOSI/TX 11, MISO/RX 8; CS 7 | ICM-45686 only; R48 10k CS pull-up to V3V3_ANA |
| I2C0 | SCL 9, SDA 12 | BMP581 only; R50/R57 4.7k to V3V3_ANA; address 0x46 |
| I2C1 | SDA 22, SCL 23 | MAG on J6, existing R25/R26 4.7k to V3V3_SYS |
| Native four-bit SD, PIO + DMA | DAT0–DAT3 28–31, CLK 32, CMD 33 | J11 only; R58 22 ohm between SD_CLK_MCU and SD_CLK; R36–R40 10k CMD/data pull-ups to V3V3_SYS |
| Sensor interrupts | ADXL INT1 1 / INT2 21; ICM INT1 6 / INT2 18; BARO INT 13 | Five separate nets and GPIOs; no combining |
| Card detect | — | Molex 47219-2001 has no detect switch; no GPIO is used |
| UART0 | TX 16, RX 17 | ELRS on J6 |
| UART1 | TX 24, RX 25 | GPS on J6 |
| Servo PWM | 20, 19, 15, 5 | PWM5–8, unchanged external connections |
| ESC outputs | 39, 38, 37, 36 | PWM1–4 in J3 pad order; intended PIO DShot, unchanged external connections |
| ADC | 40, 41, 42 | VBUS (ADC0), ESC current (ADC1), battery voltage (ADC2) |
| Other PIO | ESC telemetry RX 34; RGB LED 43 | GPIO16–47 window |
| QMI CS1 | 0 | Optional U24 expansion, unchanged |
| USB, SWD | Dedicated pins | J4, J10, unchanged |

## Hardware constraints

- SD DAT0–DAT3 are consecutive in ascending GPIO order (a PIO `in pins` requirement).
  All six SD signals use GPIO28–33 on the MCU's top-left corner facing J11, which
  puts the SD state machine in the GPIO16–47 PIO window. The LED and ESC PIO
  signals require the same window, so every PIO user shares GPIOBASE = 16. These are hardware
  allocation constraints; this change supplies no PIO or DMA firmware.
- BMP581 CSB is hard-wired to V3V3_ANA (its VDDIO), and SDO/ADDR to GND for
  7-bit address 0x46. The BMP581_I2C symbol models pin 5 as an address input.
- Sensor pulls use the sensor supply, V3V3_ANA. SD pulls use V3V3_SYS.
  No pulls are fitted on either sensor SPI clock/data bus or on SD_CLK.
- Place R58 next to U20 GPIO32 (pin 40) during the owner's PCB update. Its nominal value
  is 22 ohm; the intended tuning range is 0–33 ohm. Keep the MCU-to-resistor stub short.
- Routing priority: ICM SPI, ADXL SPI, SD clock/native bus, then BMP581 I2C.
  Keep signals short over continuous GND. Avoid split references, switching-node
  copper, long parallel runs beside servo/pyro power, unnecessary vias and long stubs.
- PWM frequency is shared per slice. Servo S5/S8 share slice 2; the ESC hardware-PWM
  fallback puts M4/M3 on slice 10 (shared with IO_GPIO44/45) and M2/M1 on slice 11
  (shared with IO_GPIO46/47). PIO DShot does not use those PWM slices.
- GPIO26, GPIO27 and GPIO35 remain unconnected; update this document and the netlist
  checker together if either is assigned. External connector pin assignments are retained.

## Revision boundary

This communication update changes the schematic only. The PCB retains its previous
nets and placement until the owner updates it from the schematic. R57 and R58 are
new parts; R50 changes from 10k on BARO_CS to 4.7k on BARO_SCL. TP5 now probes BARO_SDA.
To free GPIO2/3/4 for SPI0, ICM_INT2 moves from GPIO2 to GPIO18, LED_DATA from GPIO3
to GPIO33, and ADXL_CS from GPIO4 to GPIO14. The SD clock and command move from
GPIO33/34 to GPIO26/27. ADXL_INT2 is newly connected to GPIO21.

References: [RP2350 datasheet, GPIO function table and PIO GPIOBASE](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf),
[BMP581 datasheet, protocol selection and I2C wiring](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp581-ds004.pdf).

The locking-connector revision selects Molex 47219-2001 / LCSC C164170 for J11.
R41 and SD_DET are removed because this connector has no detect switch.
The eight card contacts and native SD GPIO26–31 connections are unchanged.

Pin-order revision (2026-09-20): GPIOs on the MCU's left and top-left edges are
re-ordered so traces meet J3 and J11 without detours. J3 top to bottom is now
ESC_TELEM_RX GPIO34, PWM4–PWM1 GPIO36–39, CURR_SENSE ADC1 (GPIO41), VBAT_SENSE
ADC2 (GPIO42). The SD bus is DAT0–DAT3 GPIO28–31, CLK GPIO32, CMD GPIO33; LED_DATA
is GPIO43; GPIO26, GPIO27 and GPIO35 become the no-connect spares. No connector
pinout, net name or part changes; the owner updates the PCB from the schematic.
