# MARV V2 GPIO reference

The schematic records the wiring. Keep this reference and `tools/check_power_netlist.py` aligned
when changing GPIOs. Power assignments
for the IO block are in [DESIGN_SPEC.md](DESIGN_SPEC.md).

Source: RP2350 Datasheet, Section 1.2.3, Table 3 "General Purpose Input/Output (GPIO) Bank 0 Functions"
(F1 SPI, F2 UART, F3 I2C, F4 PWM, F5 SIO, F6-F8 PIO0/1/2, F9 clock/QMI/trace, F10 USB, F11 UART aux).
ADC0-7 are GPIO40-47 on the RP2350B/RP2354B (QFN-80) only. All GPIO are 3.3 V, not 5 V tolerant.

External IO leaves the board on the J6/J7/J8 IO block (right front edge, signal/power/GND columns), plus
two solder-pad rows on the back (B.Cu): the ESC pad row J3 and the DBG pads J10. The four spare GPIOs that are not
on J6 (GPIO1, 26, 27, 35) are no-connect.

## Table A — every GPIO

| GPIO | Net | Used as | Datasheet alternates (F1 SPI / F2 UART / F3 I2C / F4 PWM / F9-F11) | Status |
| --- | --- | --- | --- | --- |
| 0 | FLASH_CS1 | QMI CS1n (F9) | SPI0 RX, UART0 TX, I2C0 SDA, PWM0 A, USB OVCUR DET | assigned (flash/PSRAM socket U24) |
| 1 | NC | GPIO (spare, no-connect) | SPI0 CSn, UART0 RX, I2C0 SCL, PWM0 B, USB VBUS DET | spare, no-connect |
| 2 | PWM8 | PWM1 A (F4) | SPI0 SCK, UART0 CTS, I2C1 SDA, USB VBUS EN, UART0 TX (F11) | assigned (servo S8, J6 row 10) |
| 3 | PWM7 | PWM1 B (F4) | SPI0 TX, UART0 RTS, I2C1 SCL, USB OVCUR DET, UART0 RX (F11) | assigned (servo S7, J6 row 9) |
| 4 | PWM6 | PWM2 A (F4) | SPI0 RX, UART1 TX, I2C0 SDA, USB VBUS DET | assigned (servo S6, J6 row 8) |
| 5 | PWM5 | PWM2 B (F4) | SPI0 CSn, UART1 RX, I2C0 SCL, USB VBUS EN | assigned (servo S5, J6 row 7) |
| 6 | IMU2_INT2 | GPIO input (LSM6DSK320X INT2) | SPI0 SCK, UART1 CTS, I2C1 SDA, PWM3 A, USB OVCUR DET, UART1 TX (F11) | assigned |
| 7 | IMU2_INT1 | GPIO input (LSM6DSK320X INT1) | SPI0 TX, UART1 RTS, I2C1 SCL, PWM3 B, USB VBUS DET, UART1 RX (F11) | assigned |
| 8 | IMU2_MISO | SPI1 RX (F1) | UART1 TX, I2C0 SDA, PWM4 A, QMI CS1n, USB VBUS EN | assigned |
| 9 | IMU2_CS | SPI1 CSn (F1) | UART1 RX, I2C0 SCL, PWM4 B, USB OVCUR DET | assigned (hardware CSn, R51 10k pull-up) |
| 10 | IMU2_SCK | SPI1 SCK (F1) | UART1 CTS, I2C1 SDA, PWM5 A, USB VBUS DET, UART1 TX (F11) | assigned |
| 11 | IMU2_MOSI | SPI1 TX (F1) | UART1 RTS, I2C1 SCL, PWM5 B, USB VBUS EN, UART1 RX (F11) | assigned |
| 12 | MAG_SDA | I2C0 SDA (F3) | SPI1 RX, UART0 TX, PWM6 A, CLOCK GPIN0, USB OVCUR DET | assigned (J6 row 5, R25 4.7k pull-up) |
| 13 | MAG_SCL | I2C0 SCL (F3) | SPI1 CSn, UART0 RX, PWM6 B, CLOCK GPOUT0, USB VBUS DET | assigned (J6 row 6, R26 4.7k pull-up) |
| 14 | GPS_RX | UART0 TX (F11 aux; GPS RX in) | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM7 A, CLOCK GPIN1, USB VBUS EN | assigned (J6 row 3); hardware UART0 TX, pairs with GPIO17 |
| 15 | ICM_INT1 | GPIO input (ICM INT1) | SPI1 TX, UART0 RTS, I2C1 SCL, PWM7 B, CLOCK GPOUT1, USB OVCUR DET, UART0 RX (F11) | assigned |
| 16 | ICM_MISO | SPI0 RX (F1) | UART0 TX, I2C0 SDA, PWM0 A, USB VBUS DET | assigned |
| 17 | GPS_TX | UART0 RX (F2; GPS TX in) | SPI0 CSn, I2C0 SCL, PWM0 B, USB VBUS EN | assigned (J6 row 4); hardware UART0 RX, pairs with GPIO14 |
| 18 | ICM_SCK | SPI0 SCK (F1) | UART0 CTS, I2C1 SDA, PWM1 A, USB OVCUR DET, UART0 TX (F11) | assigned |
| 19 | ICM_MOSI | SPI0 TX (F1) | UART0 RTS, I2C1 SCL, PWM1 B, QMI CS1n, USB VBUS DET, UART0 RX (F11) | assigned |
| 20 | ICM_CS | GPIO (ICM CS) | SPI0 RX, UART1 TX, I2C0 SDA, PWM2 A, CLOCK GPIN0, USB VBUS EN | assigned (R48 10k pull-up) |
| 21 | BARO_INT | GPIO input (BMP581 INT) | SPI0 CSn, UART1 RX, I2C0 SCL, PWM2 B, CLOCK GPOUT0, USB OVCUR DET | assigned |
| 22 | BARO_SDA | I2C1 SDA (F3) | SPI0 SCK, UART1 CTS, PWM3 A, CLOCK GPIN1, USB VBUS DET, UART1 TX (F11) | assigned (R57 4.7k pull-up) |
| 23 | BARO_SCL | I2C1 SCL (F3) | SPI0 TX, UART1 RTS, PWM3 B, CLOCK GPOUT1, USB VBUS EN, UART1 RX (F11) | assigned (R50 4.7k pull-up) |
| 24 | ELRS_RX | UART1 TX (F2) | SPI1 RX, I2C0 SDA, PWM4 A, CLOCK GPOUT2, USB OVCUR DET | assigned (J6 row 1) |
| 25 | ELRS_TX | UART1 RX (F2) | SPI1 CSn, I2C0 SCL, PWM4 B, CLOCK GPOUT3, USB VBUS DET | assigned (J6 row 2) |
| 26 | NC | GPIO (spare, no-connect) | SPI1 SCK, UART1 CTS, I2C1 SDA, PWM5 A, USB VBUS EN, UART1 TX (F11) | spare, no-connect |
| 27 | NC | GPIO (spare, no-connect) | SPI1 TX, UART1 RTS, I2C1 SCL, PWM5 B, USB OVCUR DET, UART1 RX (F11) | spare, no-connect |
| 28 | SD_DAT0 | PIO native SD DAT0 | SPI1 RX, UART0 TX, I2C0 SDA, PWM6 A, USB VBUS DET | assigned |
| 29 | SD_DAT1 | PIO native SD DAT1 | SPI1 CSn, UART0 RX, I2C0 SCL, PWM6 B, USB VBUS EN | assigned |
| 30 | SD_DAT2 | PIO native SD DAT2 | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM7 A, USB OVCUR DET, UART0 TX (F11) | assigned |
| 31 | SD_DAT3 | PIO native SD DAT3 | SPI1 TX, UART0 RTS, I2C1 SCL, PWM7 B, USB VBUS DET, UART0 RX (F11) | assigned |
| 32 | SD_CLK_MCU | PIO native SD clock, through R58 to SD_CLK | SPI0 RX, UART0 TX, I2C0 SDA, PWM8 A, USB VBUS EN | assigned |
| 33 | SD_CMD | PIO native SD command | SPI0 CSn, UART0 RX, I2C0 SCL, PWM8 B, USB OVCUR DET | assigned |
| 34 | ESC_TELEM_RX | PIO UART RX | SPI0 SCK, UART0 CTS, I2C1 SDA, PWM9 A, USB VBUS DET, UART0 TX (F11) | assigned (ESC TX pad) |
| 35 | NC | GPIO (spare, no-connect) | SPI0 TX, UART0 RTS, I2C1 SCL, PWM9 B, USB VBUS EN, UART0 RX (F11) | spare, no-connect |
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

Eight GPIOs are spare. Four are exposed on J6 rows 11–14 (GPIO44–47). Four are no-connect
(GPIO1, GPIO26, GPIO27, GPIO35). All other GPIOs have assigned functions.

| GPIO | Exposed | Useful alternates | Constraint |
| --- | --- | --- | --- |
| 44 | J6 row 11 | ADC4, PWM10 A, UART0 TX | SPI1 and I2C0 already serve onboard sensors |
| 45 | J6 row 12 | ADC5, PWM10 B, UART0 RX | UART0 is used by GPS on GPIO14/17; do not use this UART0 pair |
| 46 | J6 row 13 | ADC6, PWM11 A | PWM11 A is shared with GPIO38 |
| 47 | J6 row 14 | ADC7, PWM11 B | PWM11 B is shared with GPIO39 |
| 1 | No-connect | SPI0 CSn, UART0 RX, I2C0 SCL, PWM0 B, GPIO | Free GPIO; no schematic part attached |
| 26 | No-connect | SPI1 SCK, I2C1 SDA, PWM5 A, UART1 TX (F11 aux) | UART1 is used by ELRS on GPIO24/25; F11 UART1 TX here is not usable alongside it |
| 27 | No-connect | SPI1 TX, I2C1 SCL, PWM5 B, UART1 RX (F11 aux) | UART1 is used by ELRS on GPIO24/25; F11 UART1 RX here is not usable alongside it |
| 35 | No-connect | PWM9 B, PIO, UART0 RX (F11 aux), GPIO | Free GPIO; PIO window 16–47 |

GPS uses hardware UART0 on GPIO14 (TX, F11 aux) / GPIO17 (RX, F2); no PIO UART is used for GPS. SPI0 (ICM-45686), SPI1 (LSM6DSK320X), I2C0 (MAG),
I2C1 (BMP581) and UART1 (ELRS) are all in use. Pin alternate functions do not create extra controllers.

## Table C — peripheral ledger

| Peripheral | GPIOs | Device / hardware requirement |
| --- | --- | --- |
| SPI0 | SCK 18, MOSI/TX 19, MISO/RX 16; CS 20 (GPIO) | ICM-45686 only (U21), four-wire SPI; R48 10k CS pull-up to V3V3_ANA |
| SPI1 | SCK 10, MOSI/TX 11, MISO/RX 8, CSn 9 | LSM6DSK320X only (U23; nets IMU2_*); R51 10k CS pull-up to V3V3_ANA |
| I2C0 | SDA 12, SCL 13 | MAG on J6 rows 5/6; R25/R26 4.7k pull-ups to V3V3_SYS |
| I2C1 | SDA 22, SCL 23 | BMP581 only; R57/R50 4.7k to V3V3_ANA; address 0x46 |
| Native four-bit SD, PIO + DMA | DAT0–DAT3 28–31, CLK 32, CMD 33 | J11 only; R58 22 ohm between SD_CLK_MCU and SD_CLK; R36–R40 10k CMD/data pull-ups to V3V3_SYS |
| Sensor interrupts | BARO INT 21; ICM INT1 15; LSM6DSK320X INT1 7 / INT2 6 | Four separate nets and GPIOs; no combining. ICM pin 9 is CLKIN, driven by the 32.000 kHz oscillator X1 (HCI 1521H-32K000J18DTSL, net ICM_CLKIN, on V3V3_ANA); the ICM interrupts on INT1 only, so there is no ICM INT2 on the MCU |
| Card detect | — | Molex 47219-2001 has no detect switch; no GPIO is used |
| UART0 | TX 14 (F11 aux, GPS_RX), RX 17 (F2, GPS_TX) | GPS on J6 rows 1/2; hardware UART, no PIO UART for GPS |
| UART1 | TX 24, RX 25 | ELRS on J6 rows 3/4 |
| Servo PWM | S5 GPIO5 (slice 2 B), S6 GPIO4 (slice 2 A), S7 GPIO3 (slice 1 B), S8 GPIO2 (slice 1 A) | PWM5–8 nets, J6 rows 7–10, unchanged external connections; S5/S6 share slice 2, S7/S8 share slice 1 |
| ESC outputs | 39, 38, 37, 36 | PWM1–4 in J3 pad order; intended PIO DShot, unchanged external connections |
| ADC | 40, 41, 42 | VBUS (ADC0), ESC current (ADC1), battery voltage (ADC2) |
| Other PIO | ESC telemetry RX 34; RGB LED 43 | GPIO16–47 window |
| QMI CS1 | 0 | Optional U24 expansion, unchanged |
| Spare no-connect | 1, 26, 27, 35 | No-connect flags on U20 |
| USB, SWD | Dedicated pins | J4, J10, unchanged |

## Hardware constraints

- SD DAT0–DAT3 are consecutive in ascending GPIO order (a PIO `in pins` requirement).
  All six SD signals use GPIO28–33 on the MCU's top-left corner facing J11, which
  puts the SD state machine in the GPIO16–47 PIO window. The LED and ESC PIO
  signals require the same window, so every PIO user shares GPIOBASE = 16. These are hardware
  allocation constraints; this change supplies no PIO or DMA firmware.
- BMP581 CSB is hard-wired to V3V3_ANA (its VDDIO), and SDO/ADDR to GND for
  7-bit address 0x46. The BMP581_I2C symbol models pin 5 as an address input.
- Sensor pulls use the sensor supply, V3V3_ANA. SD pulls and the MAG I2C pull-ups R25/R26 use V3V3_SYS
  (the MAG module is on the J6 V3V3_SYS rail). No pulls are fitted on either sensor SPI clock/data bus or on SD_CLK.
- Place R58 next to U20 GPIO32 (pin 40) during the owner's PCB update. Its nominal value
  is 22 ohm; the intended tuning range is 0–33 ohm. Keep the MCU-to-resistor stub short.
- Routing priority: ICM SPI, LSM6DSK320X SPI, SD clock/native bus, then BMP581 I2C.
  GPIO0–27 on the MCU's right side are grouped by destination (top to bottom: servo PWM GPIO2–5 to J6 rows 7–10,
  LSM6DSK320X GPIO6–11, MAG I2C GPIO12–13, ICM-45686 GPIO15–20, BMP581 GPIO21–23, ELRS GPIO24–25; GPS is on GPIO14/17 and leaves on an inner layer to J6 rows 1–2)
  so each group can leave the MCU in straight runs; the spare pads GPIO1/26/27/35 sit between the groups.
  Keep signals short over continuous GND. Avoid split references, switching-node
  copper, long parallel runs beside servo/pyro power, unnecessary vias and long stubs.
- PWM frequency is shared per slice. Servo S5/S6 share slice 2 and S7/S8 share slice 1; the ESC hardware-PWM
  fallback puts M4/M3 on slice 10 (shared with IO_GPIO44/45) and M2/M1 on slice 11
  (shared with IO_GPIO46/47). PIO DShot does not use those PWM slices.
- GPIO1, GPIO26, GPIO27 and GPIO35 are the only unconnected GPIOs; each carries a no-connect flag on U20. Update this document and the netlist checker together if any GPIO moves.
  J6 row order and external connector pin assignments are retained.

## Final-state notes

- The analog sensing circuit is the only battery-monitor path: J3.1 CURR feeds GPIO41/ADC1 (MCU pin 52)
  via R53/C78, and VBAT feeds GPIO42/ADC2 (MCU pin 53) via R27/R28/C48. There is no INA226, U25, R59, C82
  or J12. I2C1 (GPIO22/23) serves the BMP581 only; the external magnetometer is on I2C0. See
  [G55M wiring](reports/g55m-battery-sensing.md).
- The converter interface J17 is 1x03 2.54 mm: 1 = OUT+ / 5V_IN, 2 = GND, 3 = IN+ / VBAT; there is no EN
  contact. ESC V supplies raw battery via J3.7 (VIN) to J17.3 and the voltage-divider sense net. J3 has
  eight pads.
- The sensor and external GPIOs are grouped by destination on the MCU's right side (Table A, Table C):
  LSM6DSK320X on SPI1, ICM-45686 on SPI0, the magnetometer on I2C0, BMP581 on I2C1, ELRS on UART1, and
  GPS on hardware UART0 at GPIO14 (GPS_RX, TX, F11 aux) / GPIO17 (GPS_TX, RX, F2); no PIO UART is used for
  GPS. GPIO1, GPIO26, GPIO27 and GPIO35 are no-connect spares. ICM pin 9 is CLKIN, driven by the HCI 1521H
  32.000 kHz oscillator X1 (net ICM_CLKIN), so the ICM interrupts on INT1 only and INT2 does not reach the
  MCU. Left-side GPIO28-47, net names and J6 row order are as in the tables above.

References: [RP2350 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf),
[BMP581 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp581-ds004.pdf).
