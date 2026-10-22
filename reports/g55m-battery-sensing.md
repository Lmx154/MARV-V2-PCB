# G55M analog battery sensing

The original analog sensing circuit is restored. No INA226, extra shunt, or
J12 sense connector is fitted. The PCB was not edited during this restoration;
placement, routing and final PCB checks remain with the owner.

## Connections

Connect by signal name: our J3 pad order is not the G55M's pad order.

| G55M / source | FC connection | Circuit / MCU |
| --- | --- | --- |
| C, analog current output | J3.1 CURR | R53 1k, C78 100n → GPIO41/ADC1, U20 pin 52 |
| T, telemetry output | J3.2 TX | R54 → GPIO34, U20 pin 43 |
| Motor inputs 4, 3, 2, 1 | J3.3, .4, .5, .6 | PWM4, PWM3, PWM2, PWM1 |
| External converter regulated 5 V | J3.7 5V_IN | Existing FC power input |
| G / common ground | J3.8 GND | Common signal and power reference |
| V / raw battery voltage | J3.9 VBAT | R27 100k / R28 10k, C48 100n → GPIO42/ADC2, U20 pin 53 |

G55M V is battery voltage, not regulated 5 V. Do not connect it to J3.7.
Battery/motor current stays on the ESC. Any separate battery-fed converter or
other branch outside its sensed current path will not be included in its reading.

## Firmware and input limits

Read CURR_SENSE with the FC ADC, then apply calibrated scale and zero-current
offset. Integrating amps over time gives consumed mAh. The C signal is separate
from AM32 digital telemetry on T; valid current telemetry is not assumed.

The reviewed Flywoo information did not establish an exact C-output sensitivity,
maximum output voltage or accuracy specification. Verify the output remains
within the MCU's 0–3.3 V ADC range and calibrate it against a suitable reference.
R53/C78 filter the signal; they are not a voltage divider or overvoltage clamp.
Do not use the earlier 12.75 mV/A assumption for this ESC without evidence.

The battery divider gives VBAT/11, approximately 2.29 V for a 25.2 V 6S pack.
USB VBUS monitoring remains on GPIO40/ADC0. GPIO35 and GPIO26/27 remain spare;
I2C1 remains GPIO22/23 for MAG, with no reassignment.

The FC supply design supports 1S–6S through the appropriate external converter.
Flywoo specifies the G55M ESC itself for 3S–6S.

Sources: [Flywoo G55M product and wiring images](https://www.flywoo.net/products/goku-g55m-32bit-128k-3-6s-45a-esc-30.5x30.5-),
[ADC current-monitor calibration](https://betaflight.com/docs/wiki/guides/current/Battery),
[AM32 telemetry support](https://am32.ca/).

## Restoration verification — 2026-10-22

- Exported component references and all pin-to-net assignments match the saved
  pre-INA226 schematic.
- Project checker passes all 48 GPIO assignments, 193 critical connections and
  footprint pin coverage for 108 components.
- ERC: no errors; one unchanged warning about the cached BMP581_I2C symbol being
  absent from the MARV_Sensors library.
- PCB file hash unchanged before/after this restoration.
