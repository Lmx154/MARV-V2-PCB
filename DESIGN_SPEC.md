# MARV V2: intended circuit

The goal is a simple flight controller for rockets/drones, using a purchased power
converter and familiar flight-controller circuitry. The supplied madflight
FC3v2 reference is a simplicity/layout reference, not a requirement to copy every
component.

## Power architecture

```text
ESC V (raw battery) → J3.7 / VBAT → J17.3 VIN → module → J17.1 / 5V_IN
                                    ↓ Q1
USB VBUS ──────────────────── D1 ──→ V5_SYS
                                      ├─ AP63203 buck → V3V3_SYS
                                      │                  ├─ MCU, microSD, optional QSPI
                                      │                  ├─ GPS/ELRS/MAG and spare IO
                                      │                  └─ LDO enable
                                      ├─ TPS7A2033 LDO → V3V3_ANA → onboard sensors / ADC_AVDD
                                      └─ RGB status LED

Converter VIN / J17.3 (VBAT) → 100k / 10k divider → MCU voltage measurement
```

The design uses a purchased converter module on a standard
1x03, 2.54 mm pin interface. J17 is **1 OUT+ / 5V_IN, 2 GND, 3 IN+ / VBAT**;
the unused EN contact is omitted. The assigned standard header footprint covers its pins,
not the module body; check body/underside clearance during manual placement.
J17 is placed and routed on the PCB.
ESC V carries raw battery voltage into J3.7, on the VBAT net shared with converter
VIN / J17.3 and the voltage divider. J3 has eight pads; pad 7 is VBAT, labeled VIN.
Only converter VOUT / J17.1 supplies the regulated 5V_IN rail.
The selected DROK listing is rated 24 V maximum input, so **it does not support
fully charged 6S (25.2 V)**. A suitably rated converter is required for 6S.
Set and verify 5 V output before fitting the module. The proposed 1S boost's
mechanical compatibility and current capability are still unverified.
See [converter review](reports/converter-module-review.md).

The analog LDO takes its **input from V5_SYS**, not from the 3.3 V buck.
Its **enable** comes from V3V3_SYS. This retains headroom for a regulated 3.3 V
sensor supply. The owner chose to retain this small stage after considering a
passive filter. External daughterboard demand stays off the analog rail.

No discrete pack-converter circuit, battery charger, battery current shunt,
power mux IC, or custom regulator-control simulation is required. Battery
charging and protection/cutoff belong to the external system.

## Sources and loads

| Item | Agreed boundary |
| --- | --- |
| Multi-cell option | ESC V supplies raw battery via J3.7 to converter VIN / J17.3. Purchased buck supplies regulated 5 V via J17.1. DROK's 24 V maximum excludes fully charged 6S; its 3 A claim is a maximum with cooling qualifications. |
| 1S option | Boost supplies regulated 5 V. The cell is not wired directly to the OR. The suggested 480 mA module's low-cell output capability, transients and fit at J17 remain unverified. |
| 18650, owner-provided specifications | 4.2 V charged / 3.6 V nominal / 2.5 V discharge cutoff; charge 3 A standard / 9 A maximum with 60 °C cutoff; discharge 30 A continuous with 80 °C cutoff / 36 A maximum rating. These are external-system specifications, not functions implemented by this PCB. |
| USB | VBUS supplies the FC through D1. USB current availability must cover the attached electronics; the simulation does not implement negotiation or a host current limit. |
| System 3.3 V | MCU, storage and external module/IO power. The AP63203 is a 2 A regulator; that rating is not a measured board load budget. |
| Sensor 3.3 V | ICM-45686, its 32.000 kHz CLKIN oscillator X1 (HCI 1521H-32K000J18DTSL; Vcc and E/D), BMP581, LSM6DSK320X and MCU ADC_AVDD, supplied by U12. |
| Actuators | No servos, motors or actuators are powered from FC pads. Only their PWM/control signals use the FC. No actuator current is included in the FC trace budget. |

The simulation uses an explicit **0.5 A combined demand at V5_SYS** as a
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
A lower V5_SYS when USB is connected is consistent with this circuit; it should
not be expected that the BEC always wins through Q1's low-resistance channel.

The USB-only path does not intentionally feed external 5V_IN. 5V_IN reaches no
header row: all fourteen J7 power pins are V3V3_SYS, so every IO block module can
operate on USB alone. Model leakage is
not a guarantee of zero reverse current under every temperature and source condition.

## Connectors

J3 pads 1–8: **CURR, TX, M4, M3, M2, M1, VIN / VBAT, GND**.
ESC V enters at J3.7 and feeds converter VIN / J17.3; VBAT also feeds the battery divider. ESC current is read from its analog output; the FC has no
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

## Battery monitoring

Use the GOKU G55M ESC's **C analog current output** on J3.1. R53 1k and C78
100n filter it into GPIO41/ADC1 (MCU pin 52). R27/R28 100k/10k and C48 100n
sense VBAT on GPIO42/ADC2 (MCU pin 53). USB VBUS sensing remains ADC0.
There is no extra shunt, sense-pad row or additional I2C device.
Current scale/offset and the G55M output range need verification; do not reuse
an assumed 12.75 mV/A sensitivity from a different ESC. G55M is rated 3S–6S;
the FC's 1S–6S supply capability does not extend the ESC's input range.
See [G55M sensing and wiring](reports/g55m-battery-sensing.md).

## Sensor and storage communication

The LSM6DSK320X secondary IMU (U23, high-g) has exclusive
hardware SPI1 (SCK GPIO10, MOSI GPIO11, MISO GPIO8, CSn GPIO9). Its nets are IMU2_*.
ICM-45686 has exclusive hardware SPI0 (SCK GPIO18, MOSI GPIO19, MISO GPIO16, CS GPIO20).
Both selects have 10k pull-ups to the sensors' V3V3_ANA supply. Clock and data
signals have no pull resistors. LSM6DSK320X INT1/INT2 (nets IMU2_INT1/2) use GPIO7/6; ICM INT1 uses
GPIO15. ICM pin 9 is its CLKIN, driven by the 32.000 kHz oscillator X1 (HCI 1521H-32K000J18DTSL, Vcc and E/D on
V3V3_ANA, 100 nF on Vcc, net ICM_CLKIN), so the ICM interrupts on INT1 only and INT2 does not reach the MCU. All
interrupt nets remain independent.

BMP581 uses I2C1 (SDA GPIO22, SCL GPIO23), each with a 4.7k pull-up to V3V3_ANA.
CSB is tied to VDDIO and SDO/ADDR to GND, selecting I2C address 0x46. BARO_INT
uses GPIO21. Existing sensor decoupling and power circuitry are retained.
The external magnetometer uses I2C0 (SDA GPIO12, SCL GPIO13) with 4.7k pull-ups to V3V3_SYS,
ELRS uses UART1 (TX GPIO24, RX GPIO25) and GPS uses hardware UART0 on GPIO14 (TX, F11 aux) / GPIO17 (RX).
The servo outputs are PWM5–8 on GPIO5/4/3/2.

microSD uses PIO + DMA native four-bit SD: DAT0–DAT3 GPIO28–31, CLK GPIO32,
CMD GPIO33, on the MCU's top-left corner facing J11. All six signals need the
PIO GPIO16–47 window, which the LED and ESC PIO signals already require. CMD
and all four data lines have 10k external pull-ups to V3V3_SYS. GPIO32 drives
SD_CLK through R58, 22 ohm nominal (0–33 ohm tuning range), to be placed next
to the MCU pin. There is no clock pull resistor. J11 is the Molex 47219-2001 / C164170 locking hinged-lid connector. It has no
card-detect switch, so there is no R41.
LED_DATA is on GPIO43. The ESC signals are ordered on the MCU's left edge to
match J3 top to bottom: ESC_TELEM_RX GPIO34, PWM4–PWM1 GPIO36–39, then
CURR_SENSE on ADC1 (GPIO41) and VBAT_SENSE on ADC2 (GPIO42); VBUS_SENSE stays
on ADC0. GPIO1, GPIO26, GPIO27 and GPIO35 are spares with no-connect flags. External connector
assignments are retained. See [PINOUT.md](PINOUT.md) for every GPIO and routing priorities.

This is a hardware allocation; no firmware is implemented. The board carries
these nets and parts as routed.

## Board and validation scope

Owner cost requirement: keep ordinary four-layer fabrication and
spend the budget on components. Retain 0.15 mm minimum traces/clearance
(exception: the Signal netclass — sensor buses, SD, QSPI/flash, LED,
PWM/ESC telemetry, GPS/ELRS UARTs, IO and spare GPIOs, SWD, RUN/BOOT and USB CC — uses
0.10 mm width / 0.10 mm clearance; USB D+/D- pairs, crystal, analog sense and power keep
their classes; inside JLC's standard 0.09/0.09 multilayer
capability; V3V3_ANA has its own Analog3V3 class, 0.30 mm trunk),
0.60/0.30 mm through vias (Signal-netclass vias 0.45/0.30 mm, still
JLC's free 0.3 mm-hole tier), standard 1.6 mm FR-4 and copper weights, green mask,
and an ENIG finish (flat pads for the 0.4 mm QFN and LGA sensors). Do not introduce precision drills, HDI vias,
resin-filled/capped vias or other paid fabrication upgrades to resolve routing
congestion. The netclass rules live in `MARV-V2.kicad_pro` and `MARV-V2.kicad_dru`. Final CAM acceptance
and the actual quote remain required; project settings alone cannot guarantee price.

RP2354B MCU; ICM-45686 IMU; BMP581 barometer; LSM6DSK320X secondary IMU with high-g channel;
microSD; optional unpopulated backside QSPI expansion. Four copper layers,
front-side SMT assembly, with backside solder pads and the DNP
expansion land. The owner placed and routed the board manually in KiCad. Agents must not route,
autoroute, stitch planes or rebuild the layout.

The active simulation checks **power arriving at V5_SYS only**. It does not
predict sensor noise, regulator-loop stability, enclosure temperature or flight
performance. See [simulation results](simulations/RESULTS.md).

Placement and routing are done. The saved board has 206 DRC violations
(22 accepted errors: 3 USB-pair clearance, 1 SW1/J10 courtyard overlap and 18 U20
ground-pad via hole clearances; 184 warnings), 0 unconnected items and 0
schematic-parity issues; ERC reports 0 violations. Open items for the builder:
connect the G55M by signal name rather than
assuming pad-row order or pitch matches J3; select the
external converters and compatible 3.3 V modules; review JLC assembly rotations
in the ordering preview; then measure source transitions, supply noise during
module/SD activity, and temperatures on hardware. These checks do not mandate
additional circuit features unless they reveal an actual problem.

## Design decisions

Each of these was a choice with alternatives. The reasons are recorded so they
are not re-litigated by accident.

**Purchased 5 V converter, mounted on the FC for simplicity.** The converter
is bought, not designed in, and plugs onto J17 so it rides on the flight
controller: the FC and converter mount as one unit, as on the madflight FC3v2
reference. J17 provides OUT+, GND, IN+ in that order on 2.54 mm
pitch. ESC V supplies raw battery via
J3.7 VIN to J17.3 and the battery divider. J3 has eight pads. Regulated 5V_IN comes from J17.1 VOUT. The selected
DROK's 24 V maximum excludes fully charged 6S. The proposed 1S boost still needs
fit and load validation. Battery charging, protection and cutoff belong to the external system.

**Q1/D1 OR for USB and external power — honestly specified.** A P-FET with its
gate on VBUS plus a Schottky lets the board run on the bench from USB alone and
in the air from the BEC. It does *not* guarantee that the BEC "wins" when both
are present: with USB connected the sources share through D1 and Q1's body
diode and V5_SYS sits lower. That is the circuit's real behaviour, it is what the
simulation shows, and the design accepts it rather than adding a priority mux.

**A separate LDO for the sensors, fed from 5 V.** The inertial sensors and the
barometer see a rail that is not the one the MCU, SD card and IO modules are
switching on. The TPS7A2033 takes its input from V5_SYS (headroom that a 3.3 V →
3.3 V filter cannot give) and its enable from V3V3_SYS, so the sensor rail comes
up after the digital rail. A passive filter was considered and rejected.

**Native four-bit SD over PIO instead of SPI mode.** Logging at flight rates
wants the bandwidth of four data lines and the standard SD command set, and the
RP2354B's PIO can run that bus without touching either hardware SPI block — so
SPI0 stays exclusive to the ICM-45686 and SPI1 to the LSM6DSK320X. The cost is six
GPIOs that must sit inside the PIO window (GPIO28–33), five 10 k pull-ups and a
22 Ω series damping resistor on the clock placed at the MCU pin.

**A locking microSD socket ("the latch").** J11 is a hinged-lid connector that is
closed and slid into a locked position over the card: a push-push socket can
eject a card under the shock and vibration of a launch or a hard landing, and a
lost log is the one failure a flight recorder must not have. The trade is that
this socket has no card-detect switch, so there is no detect pin or pull-up
and firmware probes for the card.

**Core-regulator layout by the datasheet.** The RP2354B's 1.1 V core switcher
follows RP2350 datasheet §6.3.8 Figures 23–24: CIN/COUT (C39/C45) in a column
with the LX trace passing between their pads (0402 lands narrowed to a 0.50 mm
gap for that), the inductor's high-current loop closed on the top layer with one
ground connection through two adjacent vias, a copper cutout on In1 under the
inductor and LX net only, the AVDD RC filter, the recommended second 4.7 µF on
the core rail (C81) on the far side of the package, and the polarity-marked
Abracon inductor the datasheet specifies (orientation dot toward pad 2 / DVDD).

**Ordinary four-layer fabrication; spend the budget on components.** 0.15 mm
track/clearance (Signal netclass 0.10 mm), 0.60 / 0.30 mm vias (Signal netclass 0.45 / 0.30 mm), ENIG, standard copper. The single
exception is a local 0.12 mm clearance rule around C39/C45 so LX can pass the
capacitor pads; that is still inside JLC's 3.5 mil four-layer capability and
costs nothing. No HDI, no filled vias, no impedance control: the USB link is
full-speed, and nothing else on the board is fast enough to need it.

**Through-hole headers shipped unpopulated.** J6–J8 (IO block) and J10 (SWD) are
2.54 mm headers the owner solders; JLC assembles the front SMT side only. J10 is
wired SWCLK–GND–SWDIO to match the Raspberry Pi Debug Probe's 3-pin cable.

**Four spare GPIOs left no-connect.** GPIO1, 26, 27 and 35 carry no-connect flags
so the IO block keeps a clean four-spare layout (GPIO44–47). GPS uses hardware UART0 on GPIO14/17,
not a PIO UART. The netlist checker enforces the assignment.
