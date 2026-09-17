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
| 1 | HG_ACC_INT | GPIO in | SPI0 CSn, UART0 RX, I2C0 SCL, PWM0 B, USB VBUS DET | assigned |
| 2 | IMU_INT2 | GPIO in | PWM1 A, SPI0 SCK, UART0 CTS, I2C1 SDA, USB VBUS EN, UART0 TX (F11) | assigned |
| 3 | LED_DATA | PIO (WS2812C) | PWM1 B, SPI0 TX, UART0 RTS, I2C1 SCL, USB OVCUR DET, UART0 RX (F11) | assigned |
| 4 | HG_ACC_CS | GPIO (ADXL375 CS) | PWM2 A, SPI0 RX, UART1 TX, I2C0 SDA, USB VBUS DET | assigned |
| 5 | PWM8 | PWM2 B (F4) | SPI0 CSn, UART1 RX, I2C0 SCL, USB VBUS EN | assigned (servo S8) |
| 6 | IMU_INT1 | GPIO in | I2C1 SDA, SPI0 SCK, UART1 CTS, PWM3 A, USB OVCUR DET, UART1 TX (F11) | assigned |
| 7 | IMU_CS | GPIO (ICM-45686 AP_CS) | I2C1 SCL, SPI0 TX, UART1 RTS, PWM3 B, USB VBUS DET, UART1 RX (F11) | assigned |
| 8 | SENS_MISO | SPI1 RX (F1) | UART1 TX, I2C0 SDA, PWM4 A, QMI CS1n, USB VBUS EN | assigned (sensors) |
| 9 | — (unexposed spare, no-connect) | GPIO | UART1 RX, SPI1 CSn, I2C0 SCL, PWM4 B, USB OVCUR DET | spare, not exposed (no-connect) |
| 10 | SENS_SCK | SPI1 SCK (F1) | PWM5 A, UART1 CTS, I2C1 SDA, USB VBUS DET, UART1 TX (F11) | assigned |
| 11 | SENS_MOSI | SPI1 TX (F1) | PWM5 B, UART1 RTS, I2C1 SCL, USB VBUS EN, UART1 RX (F11) | assigned |
| 12 | — (unexposed spare, no-connect) | GPIO | UART0 TX, SPI1 RX, I2C0 SDA, PWM6 A, CLOCK GPIN0, USB OVCUR DET | spare, not exposed (no-connect) |
| 13 | BARO_INT | GPIO in | UART0 RX, SPI1 CSn, I2C0 SCL, PWM6 B, CLOCK GPOUT0, USB VBUS DET | assigned |
| 14 | BARO_CS | GPIO (BMP581 CSB) | PWM7 A, SPI1 SCK, UART0 CTS, I2C1 SDA, CLOCK GPIN1, USB VBUS EN, UART0 TX (F11) | assigned |
| 15 | PWM7 | PWM7 B (F4) | SPI1 TX, UART0 RTS, I2C1 SCL, CLOCK GPOUT1, USB OVCUR DET, UART0 RX (F11) | assigned (servo S7) |
| 16 | ELRS_RX | UART0 TX (F2) | SPI0 RX, I2C0 SDA, PWM0 A, USB VBUS DET | assigned (J6 R1) |
| 17 | ELRS_TX | UART0 RX (F2) | SPI0 CSn, I2C0 SCL, PWM0 B, USB VBUS EN | assigned (J6 T1) |
| 18 | — (unexposed spare, no-connect) | GPIO | SPI0 SCK, UART0 CTS, I2C1 SDA, PWM1 A, USB OVCUR DET, UART0 TX (F11) | spare, not exposed (no-connect) |
| 19 | PWM6 | PWM1 B (F4) | SPI0 TX, UART0 RTS, I2C1 SCL, QMI CS1n, USB VBUS DET, UART0 RX (F11) | assigned (servo S6) |
| 20 | PWM5 | PWM2 A (F4) | SPI0 RX, UART1 TX, I2C0 SDA, CLOCK GPIN0, USB VBUS EN | assigned (servo S5) |
| 21 | — (unexposed spare, no-connect) | GPIO | SPI0 CSn, UART1 RX, I2C0 SCL, PWM2 B, CLOCK GPOUT0, USB OVCUR DET | spare, not exposed (no-connect) |
| 22 | MAG_SDA | I2C1 SDA (F3) | SPI0 SCK, UART1 CTS, PWM3 A, CLOCK GPIN1, USB VBUS DET, UART1 TX (F11) | assigned (J6 SDA) |
| 23 | MAG_SCL | I2C1 SCL (F3) | SPI0 TX, UART1 RTS, PWM3 B, CLOCK GPOUT1, USB VBUS EN, UART1 RX (F11) | assigned (J6 SCL) |
| 24 | GPS_RX | UART1 TX (F2) | SPI1 RX, I2C0 SDA, PWM4 A, CLOCK GPOUT2, USB OVCUR DET | assigned (J6 R0) |
| 25 | GPS_TX | UART1 RX (F2) | SPI1 CSn, I2C0 SCL, PWM4 B, CLOCK GPOUT3, USB VBUS DET | assigned (J6 T0) |
| 26 | — (unexposed spare, no-connect) | GPIO | SPI1 SCK, UART1 CTS, I2C1 SDA, PWM5 A, USB VBUS EN, UART1 TX (F11) | spare, not exposed (no-connect) |
| 27 | — (unexposed spare, no-connect) | GPIO | SPI1 TX, UART1 RTS, I2C1 SCL, PWM5 B, USB OVCUR DET, UART1 RX (F11) | spare, not exposed (no-connect) |
| 28 | SD_D0 | PIO | SPI1 RX, UART0 TX, I2C0 SDA, PWM6 A, USB VBUS DET | assigned |
| 29 | SD_D1 | PIO | SPI1 CSn, UART0 RX, I2C0 SCL, PWM6 B, USB VBUS EN | assigned |
| 30 | SD_D2 | PIO | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM7 A, USB OVCUR DET, UART0 TX (F11) | assigned |
| 31 | SD_D3 | PIO | SPI1 TX, UART0 RTS, I2C1 SCL, PWM7 B, USB VBUS DET, UART0 RX (F11) | assigned |
| 32 | ESC_TELEM_RX | PIO UART RX | SPI0 RX, UART0 TX, I2C0 SDA, PWM8 A, USB VBUS EN | assigned (ESC TX pad) |
| 33 | SD_CLK | PIO (SDIO 4-bit) | SPI0 CSn, UART0 RX, I2C0 SCL, PWM8 B, USB OVCUR DET | assigned |
| 34 | SD_CMD | PIO | SPI0 SCK, UART0 CTS, I2C1 SDA, PWM9 A, USB VBUS DET, UART0 TX (F11) | assigned |
| 35 | SD_DET | GPIO in | SPI0 TX, UART0 RTS, I2C1 SCL, PWM9 B, USB VBUS EN, UART0 RX (F11) | assigned |
| 36 | PWM4 | DShot via PIO | SPI0 RX, UART1 TX, I2C0 SDA, PWM10 A, USB OVCUR DET | assigned (ESC M4) |
| 37 | PWR_SRC_ST | GPIO in (TPS2121 ST) | SPI0 CSn, UART1 RX, I2C0 SCL, PWM10 B, USB VBUS DET | assigned |
| 38 | PWM3 | DShot via PIO | SPI0 SCK, UART1 CTS, I2C1 SDA, PWM11 A, USB VBUS EN, UART1 TX (F11) | assigned (ESC M3) |
| 39 | PWM2 | DShot via PIO | SPI0 TX, UART1 RTS, I2C1 SCL, PWM11 B, USB OVCUR DET, UART1 RX (F11) | assigned (ESC M2) |
| 40 | VBUS_SENSE | ADC0 | SPI1 RX, UART1 TX, I2C0 SDA, PWM8 A, USB VBUS DET | assigned |
| 41 | VBAT_SENSE | ADC1 | SPI1 CSn, UART1 RX, I2C0 SCL, PWM8 B, USB VBUS EN | assigned |
| 42 | CURR_SENSE | ADC2 | SPI1 SCK, UART1 CTS, I2C1 SDA, PWM9 A, USB OVCUR DET, UART1 TX (F11) | assigned (ESC CURR pad) |
| 43 | PWM1 | DShot via PIO | SPI1 TX, UART1 RTS, I2C1 SCL, PWM9 B, USB VBUS DET, UART1 RX (F11) | assigned (ESC M1) |
| 44 | IO_GPIO44 | GPIO / ADC4 | SPI1 RX, UART0 TX, I2C0 SDA, PWM10 A, USB VBUS EN | spare, on IO block row 11 |
| 45 | IO_GPIO45 | GPIO / ADC5 | SPI1 CSn, UART0 RX, I2C0 SCL, PWM10 B, USB OVCUR DET | spare, on IO block row 12 |
| 46 | IO_GPIO46 | GPIO / ADC6 | SPI1 SCK, UART0 CTS, I2C1 SDA, PWM11 A, USB VBUS DET, UART0 TX (F11) | spare, on IO block row 13 |
| 47 | IO_GPIO47 | GPIO / ADC7 | SPI1 TX, UART0 RTS, I2C1 SCL, PWM11 B, QMI CS1n, USB VBUS EN, UART0 RX (F11) | spare, on IO block row 14 |

## Table B — the ten spare GPIOs and what they can become

Instances already consumed: UART0 (16/17, ELRS), UART1 (24/25, GPS), I2C1 (22/23, MAG). SPI1 (8/10/11 + CS
4/7/14) now carries the sensor bus — SPI0 is fully free after this revision (it carried the sensor bus before).
Unused instances: **I2C0** and **SPI0**. UART alternates on spares can only be PIO UARTs.

Four of the ten are exposed today (on the IO block signal column, J6); the other six carry a no-connect
flag on U20 and reach no net at all (Rule 5). Using one of the six means wiring it to a connector first —
a documented change to this file, `build_power.py` and `check_power_netlist.py` together.

| GPIO | Advertised role | Also | Exposed | Caveat |
| --- | --- | --- | --- | --- |
| 44 | **I2C0 SDA** | ADC4, SPI1 RX, PWM10 A | yes, IO block row 11 | pairs with 45 |
| 45 | **I2C0 SCL** | ADC5, SPI1 CSn, PWM10 B | yes, IO block row 12 | pairs with 44 |
| 46 | **SPI1 SCK** | ADC6, PWM11 A | yes, IO block row 13 | |
| 47 | **SPI1 TX (MOSI)** | ADC7, PWM11 B, QMI CS1n alt | yes, IO block row 14 | |
| 9 | **I2C0 SCL** | SPI1 CSn alt (extra sensor CS), PWM4 B (free slice) | no (no-connect) | pairs with 12 |
| 12 | **I2C0 SDA** | SPI1 RX alt (extra sensor-bus route), PWM6 A, CLOCK GPIN0 | no (no-connect) | pairs with 9 |
| 18 | SPI0 SCK (bus is free) | PWM1 A, UART0 TX alt (F11) | no (no-connect) | no SPI0 RX/TX/CS on any spare, so this alone cannot build a new bus |
| 21 | extra SPI0 CSn / I2C0 SCL alt | PWM2 B | no (no-connect) | PWM2 slice pairs with GPIO20 (servo S5, PWM2 A) — no longer the ESC M3/M4 slice |
| 26 | extra SPI1 SCK alt (sensor bus already on GPIO10) | I2C1 SDA alt, PWM5 A (free slice) | no (no-connect) | pairs with 27 on PWM slice 5 — both free |
| 27 | extra SPI1 TX alt (sensor bus already on GPIO11) | I2C1 SCL alt, PWM5 B (free slice) | no (no-connect) | pairs with 26 on PWM slice 5 — both free |

Complete extra buses that do not conflict with anything on the board (44/45/46/47 are already exposed; 9/12
would need exposing first):
- **I2C0** on 44 (SDA) / 45 (SCL) — needs external pull-ups (none on the board) — or on 9 (SCL) / 12 (SDA)
  once exposed.
- **SPI1** extras (46 SCK / 47 TX) are already covered by the sensor bus at 8/10/11; a genuinely new SPI0 bus
  cannot be built from spares alone (only SCK on 18 and CSn on 21 are available; RX/TX are not).
- **ADC3-7** on 43-47 whenever those pins are not used digitally (43 is no longer a spare in this revision —
  see Table A).

## Table C — peripheral ledger

| Peripheral | Pins | Status |
| --- | --- | --- |
| SPI0 | — | free (Table B); carried the sensor bus before this revision |
| SPI1 | SCK 10, TX 11, RX 8; CS 7 (ICM-45686), 14 (BMP581), 4 (ADXL375); INT 6, 2, 13, 1 | used (sensors, V3V3_ANA, 10k CS pull-ups) |
| I2C0 | — | free (Table B) |
| I2C1 | SDA 22, SCL 23 (4.7k pull-ups R25/R26) | used (MAG on J6) |
| UART0 | TX 16, RX 17 | used (ELRS on J6) |
| UART1 | TX 24, RX 25 | used (GPS on J6) |
| PWM slices | 2 (20 A servo S5 / 5 B servo S8) and 11 (38 A ESC M3 / 39 B ESC M2) fully used, both channels shared across different connector rows now; 1 (19 B servo S6), 7 (15 B servo S7), 9 (43 B ESC M1), 10 (36 A ESC M4) half-used, partner channel idle; 0, 3, 4, 5, 6, 8 fully free | motor outputs normally run DShot on PIO, PWM slices are only the hardware-PWM fallback |
| ADC | 0 VBUS_SENSE (40), 1 VBAT_SENSE (41), 2 CURR_SENSE (42); 3 no longer a spare — GPIO43 is digital PWM1 now; 4-7 on the IO block spare rows (11-14) | |
| PIO | microSD 4-bit SDIO 28-31/33-34 (GPIOBASE 16 window; DET 35 stays plain GPIO), ESC telemetry RX 32, WS2812 3, ESC DShot on 36/38/39/43 | three PIO blocks available |
| QMI CS1 | GPIO0 | flash/PSRAM socket U24 (alternates 8, 19, 47 unused) |
| USB, SWD | dedicated pins | J4, J10 |

## Rules

1. ADC only on GPIO40-47. PIO can drive any GPIO.
2. The sensor bus is SPI1 and stays on 1/2/4/6/7/8/10/11/13/14; changing it means re-routing the analog island.
3. PWM frequency is per slice: a spare that shares a slice with a motor/servo output (21) cannot run PWM at
   another rate. Slice 2 (servo S5/S8) and slice 11 (ESC M2/M3) are now fully claimed across two channels
   each — a change from the previous revision, where slice-sharing only ever paired signals on the same
   connector row (M1/M2, M3/M4, S5/S6, S7/S8).
4. I2C pins need pull-ups; I2C1 has R25/R26, I2C0 on 44/45 (or 9/12 once exposed) would need external ones.
5. The six unexposed spares (GPIO9, 12, 18, 21, 26, 27) carry a no-connect flag on U20 and reach no net at
   all — left unconnected on purpose, safe under the RP2350's default pulls. Exposing one is a documented
   change to this file, `build_power.py` and `check_power_netlist.py` together.
6. Nothing on the board is 5 V logic: the J6 power column carries 5 V only as a supply for GPS/ELRS modules, their signal pins are 3.3 V.

## Conflicts found

None: every assigned pin offers the function it is used for in Table 3 (UART0 TX/RX on 16/17, UART1 TX/RX on
24/25, I2C1 SDA/SCL on 22/23, SPI1 RX/SCK/TX on 8/10/11, PWM on 5/15/19/20 (servos, hardware) and
36/38/39/43 (ESC, PIO DShot primary), QMI CS1n on 0, ADC on 40-42).
NOTED (not a violation): PWM hardware slice 2 is now shared between servo outputs S5 (GPIO20) and S8 (GPIO5),
and slice 11 between ESC outputs M3 (GPIO38) and M2 (GPIO39) — see Rule 3. Both pairs normally run DShot via
PIO, which is not affected by hardware-PWM slice frequency sharing; the constraint only bites if either pair
ever falls back to plain hardware PWM.
