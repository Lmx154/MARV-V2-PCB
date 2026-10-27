# Converter module mounting and system LDO review

J17 is the mount for a purchased 5 V buck converter on the FC, as on madflight
FC3v2. It is a 1x03 2.54 mm vertical pin-header footprint that uses only the
module's three used contacts and omits the unused EN contact. The owner has
physically confirmed standard 2.54 mm pins on the buck. J17 is hand-fitted and is
in the BOM without an LCSC number.

The converter is the owner-supplied [Amazon ASIN B0CYZBPKKT](https://www.amazon.com/dp/B0CYZBPKKT).
The Amazon page could not be retrieved directly; a mechanical drawing and a
definite match to DROK SKU 2001708006 are not established. Module body clearance
and boost interchangeability are open fit questions.

## Electrical interface

J17 three-position interface, retaining the DROK module's first three terminals:

| Position | Module terminal | FC connection |
| --- | --- | --- |
| 1 | VO+ | `5V_IN`, upstream of Q1 and at the existing C19 input reservoir |
| 2 | GND | GND |
| 3 | IN+ | `VBAT` / ESC raw battery from J3.7 VIN; shared with the voltage divider |

The module's EN terminal has no mating contact on the FC and remains open for
the module's documented default-on operation.

Retain Q1/D1 USB OR, AP63203 system buck, and separate TPS7A2033 sensor LDO.
Do not connect converter output directly to `V5_SYS`, bypassing the existing OR.
Configure and verify 5 V output before connecting the FC. Use the module's fixed
5 V selection according to its instructions.

ESC V carries full battery voltage: ESC V -> J3.7 (VIN) -> J17.3 / converter VIN
and R27.1 (battery-sense divider), all on net `VBAT`. J3 is an eight-pad row
(`PadRow_1x08_P2.00mm`); battery connects directly to the converter, so there is no
separate battery pad. The feed and return must support converter current.
Propulsion current remains off the FC. Regulated `5V_IN` comes from J17.1 VOUT
(-> C19 / Q1), not from the ESC pad row.

The [DROK 2001708006 manual](https://m.media-amazon.com/images/I/919NnVqz1zL.pdf)
lists 2.54 mm terminal pitch, 4.5–24 V input, adjustable/fixed outputs, and
3 A maximum with cooling qualifications. It permits EN to remain unconnected.
The owner's ASIN is not matched to that SKU, and the photos do not
establish the board outline, hole diameter, pin-to-edge offsets, or underside
clearance. The assigned standard header footprint defines pins only; its
courtyard does not establish clearance for the complete module body.

## Battery and module compatibility

- **2S:** A buck is the appropriate topology for 5 V provided its input remains
  above the headroom needed at the selected load. The advertised 4.5 V minimum
  does not mean it can maintain 5 V output at 4.5 V input.
- **Higher cell counts:** A 6S pack charged to 4.2 V/cell reaches 25.2 V,
  exceeding this module's 24 V maximum. Even for packs below that limit, account
  for input transients; nominal pack voltage alone does not establish suitability.
- **1S:** The pictured 0.9–5 V input / 5 V output device is a boost-only converter.
  A conventional 1S cell stays below 5 V, so boost-only is sufficient in principle.
  Buck-boost is needed when the required input range crosses the output voltage.
- **Interchangeability:** The boost's VO/GND/VI signal order matches the first
  three buck terminals; it has no EN terminal. Its pitch, dimensions, orientation,
  and mounting clearance are not verified. It is not yet a verified drop-in option.
- **Boost capacity:** The supplied 480 mA maximum is not a guaranteed continuous
  rating across cell voltage. It is below the project's assumed 500 mA combined
  `V5_SYS` test load, which itself is not a measured requirement. At 5 V/480 mA
  and the seller's typical 85% efficiency, calculated battery current is about
  0.76 A at 3.7 V or 1.13 A at 2.5 V. These are illustrative calculations, not
  evidence that this module can deliver that output at either voltage. Startup,
  SD/peripheral load steps, and low-cell output capability remain unverified.

The [madflight FC3v2 documentation](https://madflight.com/Board-FC3/) supports the
mounting concept, but describes its converter as 6.5–20 V input, 5 V/2 A continuous,
3 A peak, 20 × 10 × 5 mm. Those dimensions and ratings cannot be transferred to
an unidentified DROK variant.

## Replacing the system buck with an LDO

An LDO is possible if the total system rail demand and thermal design support it.
That demand includes RP2354B, microSD, populated QSPI, and all J7 peripherals,
not only GPS/compass/buzzer. Exact modules and simultaneous peaks are unknown.

At 5 V input and 3.3 V output, neglecting quiescent current:

| System output current | LDO dissipation |
| --- | --- |
| 100 mA | 0.17 W |
| 200 mA | 0.34 W |
| 300 mA | 0.51 W |
| 500 mA | 0.85 W |

Efficiency is approximately 66%. For comparison only, a 90%-efficient buck
would draw about 220 mA from 5 V for a 3.3 V/300 mA load, versus approximately
300 mA for an LDO. The 90% value is illustrative, not a measured AP63203 result.
Switching to an LDO increases demand on the small 1S boost.

The existing [TPS7A20](https://www.ti.com/lit/ds/symlink/tps7a20.pdf) is rated
300 mA. Its SOT-23 DBV thermal resistance is 187.1 °C/W on the datasheet test
board: 0.51 W implies roughly 95 °C junction rise under those test conditions.
Actual rise depends on PCB copper and ambient temperature. A second copy is
therefore not an established system-rail solution. A higher-current LDO still
needs sufficient heat dissipation and load-step performance.

The design retains the
[AP63203](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf)
system buck and separate sensor LDO. An LDO would be reconsidered only after
the total continuous/peak load is bounded and its package can meet the thermal
requirement; no measured load budget or thermal test exists.

The maximum battery configuration and physical clearances, including SD lid
access, must be confirmed with the actual module. The input-only simulation does
not validate these converter modules or a replacement 3.3 V regulator.

## Interface checks

The schematic is checked with ERC (0 violations) and `tools/check_power_netlist.py`
on a KiCad XML netlist export, which verifies the critical power pin mappings and
footprint pad coverage. J3.7 is on `VBAT` (labelled VIN), J17.1 is on `5V_IN`,
J17.2 on GND and J17.3 on `VBAT`; the input-only simulation's wiring guard models
the regulated voltage at J17.1. The saved PCB has zero schematic-parity findings
and no unconnected items; J17 is placed and routed.
