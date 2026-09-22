# MARV V2: intended circuit

The goal is a simple flight controller for rockets/drones, using external power
conversion and familiar flight-controller circuitry. The supplied madflight
FC3v2 reference is a simplicity/layout reference, not a requirement to copy every
component. Owner-confirmed decisions in this document supersede older design notes.

## Power architecture

```text
2S–6S pack → external 5 V / 3 A buck ─┐  alternative external sources
1S 18650 → external 5 V boost ────────┘
                                    ↓
                              J3.7 / 5V_IN (BEC input only; no header row)
                                    ↓ Q1
USB VBUS ──────────────────── D1 ──→ V5_SYS
                                      ├─ AP63203 buck → V3V3_SYS
                                      │                  ├─ MCU, microSD, optional QSPI
                                      │                  ├─ GPS/ELRS/MAG and spare IO
                                      │                  └─ LDO enable
                                      ├─ TPS7A2033 LDO → V3V3_ANA → onboard sensors / ADC_AVDD
                                      └─ RGB status LED

Raw battery → J3.9 / VBAT → 100k / 10k divider → MCU voltage measurement
```

The analog LDO takes its **input from V5_SYS**, not from the 3.3 V buck.
Its **enable** comes from V3V3_SYS. This retains headroom for a regulated 3.3 V
sensor supply. The owner chose to retain this small stage after considering a
passive filter. External daughterboard demand stays off the analog rail.

No onboard pack buck, battery charger, battery current shunt, power mux IC, or
custom regulator-control simulation is required. Battery charging and converter
protection/cutoff belong to the external system.

## Sources and loads

| Item | Agreed boundary |
| --- | --- |
| 2S–6S option | External buck supplies regulated 5 V, rated 3 A. The FC receives its output. |
| 1S option | External boost supplies regulated 5 V. The cell is not wired directly to the OR. Boost output rating and transient behavior are not yet specified. |
| 18650, owner-provided specifications | 4.2 V charged / 3.6 V nominal / 2.5 V discharge cutoff; charge 3 A standard / 9 A maximum with 60 °C cutoff; discharge 30 A continuous with 80 °C cutoff / 36 A maximum rating. These are external-system specifications, not functions implemented by this PCB. |
| USB | VBUS supplies the FC through D1. USB current availability must cover the attached electronics; the simulation does not implement negotiation or a host current limit. |
| System 3.3 V | MCU, storage and external module/IO power. The AP63203 is a 2 A regulator; that rating is not a measured board load budget. |
| Sensor 3.3 V | ICM-45686, BMP581, ADXL375 and MCU ADC_AVDD, supplied by U12. |
| Actuators | Owner clarified 2026-09-18: no servos, motors or actuators are powered from FC pads. Only their PWM/control signals use the FC. Existing 5V_IN pad connections remain, but no actuator current is included in the FC trace budget. |

The new simulation uses an explicit **0.5 A combined demand at V5_SYS** as a
starting assumption. This is neither 0.5 A on each downstream rail nor a demand
for the external converter to deliver its full 3 A rating. Choose actual module
loads before assigning a final system/USB budget. A daughterboard having its own
LDO does not by itself establish that its power input accepts 3.3 V; that input
range remains a module-selection requirement.

Expected external electronics may include four ToF sensors, several lidar modules,
GPS and an ELRS radio. Their exact voltage requirements and simultaneous peak
current remain to be established. The routing defaults and fabrication constraints
are documented in [JLCPCB DFM and routing](reports/jlc-dfm-routing.md).

## OR behavior

Q1 is an AO3401A: drain on 5V_IN, source on V5_SYS, gate on USB_VBUS.
D1 is a 1N5819WS: anode on USB_VBUS, cathode on V5_SYS. C19 is 100 uF
on the external input, upstream of Q1.

With USB absent, Q1's gate discharges and its channel carries the external supply.
With USB present, Q1 can be off and the sources can share through D1 and Q1's
body diode. **There is no guaranteed BEC priority or lossless switchover.**
A lower V5_SYS when USB is connected is consistent with this circuit; the old
expectation that the BEC always wins through Q1's low-resistance channel was wrong.

The USB-only path does not intentionally feed external 5V_IN. 5V_IN reaches no
header row: all fourteen J7 power pins are V3V3_SYS, so every IO block module can
operate on USB alone. Model leakage is
not a guarantee of zero reverse current under every temperature and source condition.

## Connectors

J3 pads 1–9: **CURR, TX, M4, M3, M2, M1, 5V_IN, GND, VBAT**.
VBAT is sense-only. ESC current is read from its analog output; the FC has no
propulsion-current pass-through or shunt. J10 is the SWD 1x03 2.54 mm header (SWCLK, GND, SWDIO — Debug Probe order).

For the IO block, each row has J6 = signal, J7 = power, J8 = ground:

| Rows | Signals | J7 supply |
| --- | --- | --- |
| 1–2 | GPS UART | V3V3_SYS |
| 3–4 | ELRS UART | V3V3_SYS |
| 5–6 | Magnetometer I2C | V3V3_SYS |
| 7–10 | PWM5–8, servo signals only | V3V3_SYS |
| 11–14 | GPIO44–47, spare IO | V3V3_SYS |

All signal IO is 3.3 V logic. J3 carries PWM1–4 to the ESC.
See [PINOUT.md](PINOUT.md) for individual MCU assignments.

## Sensor and storage communication

ADXL375 has exclusive hardware SPI0 (SCK GPIO2, MOSI GPIO3, MISO GPIO4, CS GPIO14).
ICM-45686 has exclusive hardware SPI1 (SCK GPIO10, MOSI GPIO11, MISO GPIO8, CS GPIO7).
Both selects have 10k pull-ups to the sensors' V3V3_ANA supply. Clock and data
signals have no pull resistors. ADXL INT1/INT2 use GPIO1/21; ICM INT1/INT2 use
GPIO6/18. All interrupt nets remain independent.

BMP581 uses I2C0 (SCL GPIO9, SDA GPIO12), each with a 4.7k pull-up to V3V3_ANA.
CSB is tied to VDDIO and SDO/ADDR to GND, selecting I2C address 0x46. BARO_INT
uses GPIO13. Existing sensor decoupling and power circuitry are retained.

microSD uses PIO + DMA native four-bit SD: DAT0–DAT3 GPIO28–31, CLK GPIO32,
CMD GPIO33, on the MCU's top-left corner facing J11. All six signals need the
PIO GPIO16–47 window, which the LED and ESC PIO signals already require. CMD
and all four data lines have 10k external pull-ups to V3V3_SYS. GPIO32 drives
SD_CLK through R58, 22 ohm nominal (0–33 ohm tuning range), to be placed next
to the MCU pin. There is no clock pull resistor. J11 is the Molex 47219-2001 / C164170 locking hinged-lid connector. It has no
card-detect switch; R41 is removed.
LED_DATA is on GPIO43. The ESC signals are ordered on the MCU's left edge to
match J3 top to bottom: ESC_TELEM_RX GPIO34, PWM4–PWM1 GPIO36–39, then
CURR_SENSE on ADC1 (GPIO41) and VBAT_SENSE on ADC2 (GPIO42); VBUS_SENSE stays
on ADC0. GPIO26, GPIO27 and GPIO35 are the unexposed spares. External connector
assignments are retained. See [PINOUT.md](PINOUT.md) for every GPIO and routing priorities.

This is a hardware allocation; no firmware is implemented. The board carries
these nets and parts as routed (2026-09-22).

## Board and validation scope

Owner cost requirement (2026-09-21): keep ordinary four-layer fabrication and
spend the budget on components. Retain 0.15 mm minimum traces/clearance,
0.60/0.30 mm through vias, standard 1.6 mm FR-4 and copper weights, green mask,
and the selected HASL finish. Do not introduce precision drills, HDI vias,
resin-filled/capped vias or other paid fabrication upgrades to resolve routing
congestion. See [signal widths](reports/signal-trace-widths.md) and the
[fabrication cost audit](reports/fabrication-cost-audit.md). Final CAM acceptance
and the actual quote remain required; project settings alone cannot guarantee price.

RP2354B MCU; ICM-45686 IMU; BMP581 barometer; ADXL375 high-g sensor;
microSD; optional unpopulated backside QSPI expansion. Four copper layers,
front-side SMT assembly, with backside solder pads/test points and the DNP
expansion land. Existing placement is retained. The owner will route the board manually in KiCad. Agents must not route,
autoroute, stitch planes or rebuild the layout.

The active simulation checks **power arriving at V5_SYS only**. It does not
predict sensor noise, regulator-loop stability, enclosure temperature or flight
performance. See [simulation results](simulations/RESULTS.md).

Routing and DRC are complete (2026-09-22: 0 errors, 0 unconnected, 0 parity).
Remaining work is off the board: confirm physical ESC pad pitch; select the
external converters and compatible 3.3 V modules; review JLC assembly rotations
in the ordering preview; then measure source transitions, supply noise during
module/SD activity, and temperatures on hardware. These checks do not mandate
additional circuit features unless they reveal an actual problem.
