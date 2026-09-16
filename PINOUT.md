# MARV V2 pin plan (set in stone)

Changing any GPIO assignment requires editing **this file, `tools/build_power.py` (MCU_GPIO table) and the
asserts in `tools/check_power_netlist.py` together**; the checker fails otherwise.

Source: RP2350 Datasheet, Section 1.2.3, Table 3 "General Purpose Input/Output (GPIO) Bank 0 Functions"
(F1 SPI, F2 UART, F3 I2C, F4 PWM, F5 SIO, F6-F8 PIO0/1/2, F9 clock/QMI/trace, F10 USB, F11 UART aux).
ADC0-7 are GPIO40-47 on the RP2350B/RP2354B (QFN-80) only. All GPIO are 3.3 V, not 5 V tolerant.

External IO leaves the board on the J6/J7/J8 IO block (right front edge, signal/power/GND columns), plus
two solder-pad rows on the back (B.Cu): the ESC pad row J3 and the DBG pads J10.

## Table A — every GPIO

| GPIO | Net | Used as | Datasheet alternates (F1 SPI / F2 UART / F3 I2C / F4 PWM / F9-F11) | Status |
| --- | --- | --- | --- | --- |
| 0 | FLASH_CS1 | QMI CS1n (F9) | SPI0 RX, UART0 TX, I2C0 SDA, PWM0 A, USB OVCUR DET | assigned (flash/PSRAM socket U24) |
| 1 | IO_GPIO1 | GPIO | SPI0 CSn, UART0 RX, I2C0 SCL, PWM0 B, USB VBUS DET | spare, not exposed (no-connect) |
| 2 | PWM1 | PWM1 A (F4) / DShot via PIO | SPI0 SCK, UART0 CTS, I2C1 SDA, USB VBUS EN, UART0 TX (F11) | assigned (ESC M1) |
| 3 | PWM2 | PWM1 B | SPI0 TX, UART0 RTS, I2C1 SCL, USB OVCUR DET, UART0 RX (F11) | assigned (ESC M2) |
| 4 | PWM3 | PWM2 A | SPI0 RX, UART1 TX, I2C0 SDA, USB VBUS DET | assigned (ESC M3) |
| 5 | PWM4 | PWM2 B | SPI0 CSn, UART1 RX, I2C0 SCL, USB VBUS EN | assigned (ESC M4) |
| 6 | MAG_SDA | I2C1 SDA (F3) | SPI0 SCK, UART1 CTS, PWM3 A, USB OVCUR DET, UART1 TX (F11) | assigned (J6 SDA) |
| 7 | MAG_SCL | I2C1 SCL (F3) | SPI0 TX, UART1 RTS, PWM3 B, USB VBUS DET, UART1 RX (F11) | assigned (J6 SCL) |
| 8 | ELRS TX | UART1 TX (F2) | SPI1 RX, I2C0 SDA, PWM4 A, QMI CS1n, USB VBUS EN | assigned (J6 T1) |
| 9 | ELRS RX | UART1 RX (F2) | SPI1 CSn, I2C0 SCL, PWM4 B, USB OVCUR DET | assigned (J6 R1) |
| 10 | PWM5 | PWM5 A | SPI1 SCK, UART1 CTS, I2C1 SDA, USB VBUS DET, UART1 TX (F11) | assigned (servo S5) |
| 11 | PWM6 | PWM5 B | SPI1 TX, UART1 RTS, I2C1 SCL, USB VBUS EN, UART1 RX (F11) | assigned (servo S6) |
| 12 | GPS TX | UART0 TX (F2) | SPI1 RX, I2C0 SDA, PWM6 A, CLOCK GPIN0, USB OVCUR DET | assigned (J6 T0) |
| 13 | GPS RX | UART0 RX (F2) | SPI1 CSn, I2C0 SCL, PWM6 B, CLOCK GPOUT0, USB VBUS DET | assigned (J6 R0) |
| 14 | PWM7 | PWM7 A | SPI1 SCK, UART0 CTS, I2C1 SDA, CLOCK GPIN1, USB VBUS EN, UART0 TX (F11) | assigned (servo S7) |
| 15 | PWM8 | PWM7 B | SPI1 TX, UART0 RTS, I2C1 SCL, CLOCK GPOUT1, USB OVCUR DET, UART0 RX (F11) | assigned (servo S8) |
| 16 | SENS_MISO | SPI0 RX (F1) | UART0 TX, I2C0 SDA, PWM0 A, USB VBUS DET | assigned (sensors) |
| 17 | HG_ACC_CS | GPIO (ADXL375 CS) | SPI0 CSn, UART0 RX, I2C0 SCL, PWM0 B, USB VBUS EN | assigned |
| 18 | SENS_SCK | SPI0 SCK (F1) | UART0 CTS, I2C1 SDA, PWM1 A, USB OVCUR DET, UART0 TX (F11) | assigned |
| 19 | SENS_MOSI | SPI0 TX (F1) | UART0 RTS, I2C1 SCL, PWM1 B, QMI CS1n, USB VBUS DET, UART0 RX (F11) | assigned |
| 20 | IMU_CS | GPIO (ICM-45686 AP_CS) | SPI0 RX, UART1 TX, I2C0 SDA, PWM2 A, CLOCK GPIN0, USB VBUS EN | assigned |
| 21 | IO_GPIO21 | GPIO | SPI0 CSn, UART1 RX, I2C0 SCL, PWM2 B, CLOCK GPOUT0, USB OVCUR DET | spare, not exposed (no-connect) |
| 22 | BARO_CS | GPIO (BMP581 CSB) | SPI0 SCK, UART1 CTS, I2C1 SDA, PWM3 A, CLOCK GPIN1, USB VBUS DET, UART1 TX (F11) | assigned |
| 23 | IMU_INT1 | GPIO in | SPI0 TX, UART1 RTS, I2C1 SCL, PWM3 B, CLOCK GPOUT1, USB VBUS EN, UART1 RX (F11) | assigned |
| 24 | IMU_INT2 | GPIO in | SPI1 RX, UART1 TX, I2C0 SDA, PWM4 A, CLOCK GPOUT2, USB OVCUR DET | assigned |
| 25 | BARO_INT | GPIO in | SPI1 CSn, UART1 RX, I2C0 SCL, PWM4 B, CLOCK GPOUT3, USB VBUS DET | assigned |
| 26 | LED_DATA | PIO (WS2812C) | SPI1 SCK, UART1 CTS, I2C1 SDA, PWM5 A, USB VBUS EN, UART1 TX (F11) | assigned |
| 27 | IO_GPIO27 | GPIO | SPI1 TX, UART1 RTS, I2C1 SCL, PWM5 B, USB OVCUR DET, UART1 RX (F11) | spare, not exposed (no-connect) |
| 28 | IO_GPIO28 | GPIO | SPI1 RX, UART0 TX, I2C0 SDA, PWM6 A, USB VBUS DET | spare, not exposed (no-connect) |
| 29 | HG_ACC_INT | GPIO in | SPI1 CSn, UART0 RX, I2C0 SCL, PWM6 B, USB VBUS EN | assigned |
| 30 | ESC_TELEM_RX | PIO UART RX | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM7 A, USB OVCUR DET, UART0 TX (F11) | assigned (ESC TX pad) |
| 31 | IO_GPIO31 | GPIO | SPI1 TX, UART0 RTS, I2C1 SCL, PWM7 B, USB VBUS DET, UART0 RX (F11) | spare, not exposed (no-connect) |
| 32 | SD_CLK | PIO (SDIO 4-bit) | SPI0 RX, UART0 TX, I2C0 SDA, PWM8 A, USB VBUS EN | assigned |
| 33 | SD_CMD | PIO | SPI0 CSn, UART0 RX, I2C0 SCL, PWM8 B, USB OVCUR DET | assigned |
| 34 | SD_D0 | PIO | SPI0 SCK, UART0 CTS, I2C1 SDA, PWM9 A, USB VBUS DET, UART0 TX (F11) | assigned |
| 35 | SD_D1 | PIO | SPI0 TX, UART0 RTS, I2C1 SCL, PWM9 B, USB VBUS EN, UART0 RX (F11) | assigned |
| 36 | SD_D2 | PIO | SPI0 RX, UART1 TX, I2C0 SDA, PWM10 A, USB OVCUR DET | assigned |
| 37 | SD_D3 | PIO | SPI0 CSn, UART1 RX, I2C0 SCL, PWM10 B, USB VBUS DET | assigned |
| 38 | SD_DET | GPIO in | SPI0 SCK, UART1 CTS, I2C1 SDA, PWM11 A, USB VBUS EN, UART1 TX (F11) | assigned |
| 39 | PWR_SRC_ST | GPIO in (TPS2121 ST) | SPI0 TX, UART1 RTS, I2C1 SCL, PWM11 B, USB OVCUR DET, UART1 RX (F11) | assigned |
| 40 | VBAT_SENSE | ADC0 | SPI1 RX, UART1 TX, I2C0 SDA, PWM8 A, USB VBUS DET | assigned |
| 41 | VBUS_SENSE | ADC1 | SPI1 CSn, UART1 RX, I2C0 SCL, PWM8 B, USB VBUS EN | assigned |
| 42 | CURR_SENSE | ADC2 | SPI1 SCK, UART1 CTS, I2C1 SDA, PWM9 A, USB OVCUR DET, UART1 TX (F11) | assigned (ESC CURR pad) |
| 43 | IO_GPIO43 | GPIO / ADC3 | SPI1 TX, UART1 RTS, I2C1 SCL, PWM9 B, USB VBUS DET, UART1 RX (F11) | spare, not exposed (no-connect) |
| 44 | IO_GPIO44 | GPIO / ADC4 | SPI1 RX, UART0 TX, I2C0 SDA, PWM10 A, USB VBUS EN | spare, on IO block row 11 |
| 45 | IO_GPIO45 | GPIO / ADC5 | SPI1 CSn, UART0 RX, I2C0 SCL, PWM10 B, USB OVCUR DET | spare, on IO block row 12 |
| 46 | IO_GPIO46 | GPIO / ADC6 | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM11 A, USB VBUS DET, UART0 TX (F11) | spare, on IO block row 13 |
| 47 | IO_GPIO47 | GPIO / ADC7 | SPI1 TX, UART0 RTS, I2C1 SCL, PWM11 B, QMI CS1n, USB VBUS EN, UART0 RX (F11) | spare, on IO block row 14 |

## Table B — the ten spare GPIOs and what they can become

Instances already consumed: UART0 (12/13), UART1 (8/9), I2C1 (6/7), SPI0 (16/18/19 + CS 17/20/22).
Unused instances: **I2C0** and **SPI1**. UART alternates on spares can only be PIO UARTs.

Four of the ten are exposed today (on the IO block signal column, J6); the other six carry a no-connect
flag on U20 and reach no net at all (Rule 5). Using one of the six means wiring it to a connector first —
a documented change to this file, `build_power.py` and `check_power_netlist.py` together.

| GPIO | Advertised role | Also | Exposed | Caveat |
| --- | --- | --- | --- | --- |
| 44 | **I2C0 SDA** | ADC4, SPI1 RX, PWM10 A | yes, IO block row 11 | pairs with 45 |
| 45 | **I2C0 SCL** | ADC5, SPI1 CSn, PWM10 B | yes, IO block row 12 | pairs with 44 |
| 46 | **SPI1 SCK** | ADC6, PWM11 A | yes, IO block row 13 | |
| 47 | **SPI1 TX (MOSI)** | ADC7, PWM11 B, QMI CS1n alt | yes, IO block row 14 | |
| 43 | **ADC3** | SPI1 TX alt, PWM9 B | no (no-connect) | |
| 28 | SPI1 RX (MISO) / I2C0 SDA alt | PWM6 A (free slice) | no (no-connect) | |
| 1 | I2C0 SCL alt | SPI0 CSn (extra sensor CS), PWM0 B | no (no-connect) | |
| 21 | extra SPI0 CSn (a 4th sensor on the sensor bus) | I2C0 SCL alt, PWM2 B | no (no-connect) | PWM2 slice is the ESC M3/M4 slice |
| 27 | GPIO | SPI1 TX alt, PWM5 B | no (no-connect) | PWM5 slice is the servo S5/S6 slice — no independent PWM frequency |
| 31 | GPIO | SPI1 TX alt, PWM7 B | no (no-connect) | PWM7 slice is the servo S7/S8 slice — no independent PWM frequency |

Complete extra buses that do not conflict with anything on the board (44/45/46/47 are already exposed; 28/1/21
would need exposing first):
- **I2C0** on 44 (SDA) / 45 (SCL) — needs external pull-ups (none on the board).
- **SPI1** on 46 (SCK) / 47 (TX) / 28 (RX) with 45 (CSn) — or 44 as RX if I2C0 is not used.
- Both at once: I2C0 on 44/45, SPI1 on 46/47/28 with CS on 1 or 21 as plain GPIO.
- **ADC3-7** on 43-47 whenever those pins are not used digitally (43 would need exposing first).

## Table C — peripheral ledger

| Peripheral | Pins | Status |
| --- | --- | --- |
| SPI0 | SCK 18, TX 19, RX 16; CS 17 (ADXL375), 20 (ICM-45686), 22 (BMP581); INT 23, 24, 25, 29 | used (sensors, V3V3_ANA, 10k CS pull-ups) |
| SPI1 | — | free (Table B) |
| I2C0 | — | free (Table B) |
| I2C1 | SDA 6, SCL 7 (4.7k pull-ups R25/R26) | used (MAG on J6) |
| UART0 | TX 12, RX 13 | used (GPS on J6) |
| UART1 | TX 8, RX 9 | used (ELRS on J6) |
| PWM slices | 1 (2/3 M1/M2), 2 (4/5 M3/M4), 5 (10/11 S5/S6), 7 (14/15 S7/S8) used; 0, 3, 4, 6, 8, 9, 10, 11 free | motor outputs normally run DShot on PIO, PWM slices are the fallback |
| ADC | 0 VBAT_SENSE (40), 1 VBUS_SENSE (41), 2 CURR_SENSE (42); 3 unexposed (no-connect); 4-7 on the IO block spare rows (11-14) | |
| PIO | microSD 4-bit SDIO 32-38, ESC telemetry RX 30, WS2812 26, DShot on 2-5 | three PIO blocks available |
| QMI CS1 | GPIO0 | flash/PSRAM socket U24 (alternates 8, 19, 47 unused) |
| USB, SWD | dedicated pins | J4, J10 |

## Rules

1. ADC only on GPIO40-47. PIO can drive any GPIO.
2. The sensor bus is SPI0 and stays on 16-25; changing it means re-routing the analog island.
3. PWM frequency is per slice: a spare that shares a slice with a motor/servo output (21, 27, 31) cannot run PWM at another rate.
4. I2C pins need pull-ups; I2C1 has R25/R26, I2C0 on 44/45 would need external ones.
5. The six unexposed spares (GPIO1, 21, 27, 28, 31, 43) carry a no-connect flag on U20 and reach no net at
   all — left unconnected on purpose, safe under the RP2350's default pulls. Exposing one is a documented
   change to this file, `build_power.py` and `check_power_netlist.py` together.
6. Nothing on the board is 5 V logic: the J6 power column carries 5 V only as a supply for GPS/ELRS modules, their signal pins are 3.3 V.

## Conflicts found

None: every assigned pin offers the function it is used for in Table 3 (UART0 TX/RX on 12/13, UART1 TX/RX on
8/9, I2C1 SDA/SCL on 6/7, SPI0 RX/SCK/TX on 16/18/19, PWM on 2-5/10/11/14/15, QMI CS1n on 0, ADC on 40-42).
