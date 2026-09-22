# First-boot review — 2026-09-22

Scope: the saved PCB and schematic, narrowed at the owner's request to faults
that could prevent the first prototype from powering up, booting, or being
programmed. No placement, routing, zones, schematic, project settings, or tracked
simulation outputs were changed. Checks used saved copper fills, without refill.

**Verdict: no definite first-boot blocker found.** The design looks reasonable
for a first prototype. This is a design-review result, not measured startup proof.

## Checks completed

- KiCad 10.0.6 ERC: **0 violations**.
- PCB DRC: **0 errors, 0 unconnected items, 0 schematic-parity issues**.
  There are 104 warnings; these concern pad-size assertions, silkscreen and
  missing courtyards on graphics, not reported electrical shorts or opens.
- Critical netlist checker: passed 193 pin mappings, all 48 GPIO allocations,
  power-source connections, and connector mappings. Footprint audit: 108/108 pass.
- Q1/D1 input polarity, U7 fixed-3.3-V feedback/enable, and U12 input/output/enable
  connections match the intended architecture. Regulator input/output capacitors,
  bootstrap capacitor and inductors are present and connected.
- MCU I/O, USB, core and analog supplies, exposed ground pad, core-feedback
  connection, and VREG_AVDD RC filter are connected as intended.
- The earlier core-regulator finding has been addressed: the saved In1.Cu plane
  has a cutout beneath L20/VREG_LX, and C39/C45 and PGND have a local front-layer
  return path. L20 is at approximately **(98.15, 109.60) mm**. C81 supplies the
  additional bulk decoupling on the far side of the MCU.
- RUN has its pull-up and reset switch; BOOTSEL pulls QSPI_SS down through R24.
  USB D+/D−, the two separate 5.1 kΩ CC resistors, and J10 SWCLK/GND/SWDIO are
  connected correctly. USB signal routes are continuous on the front layer.
- The specified MCU is **RP2354B**, which includes boot flash; leaving optional
  U24 unpopulated does not remove the primary boot memory.
- Y1, R21 and C46/C47 form the intended 12 MHz crystal network; no open or swapped
  clock connection was found.

## Two remaining first-boot considerations

1. **Verify L20's physical orientation in the assembly preview.** Fit the specified
   AOTA-B201610S3R3-101-T with the orientation dot toward **pad 2 / DVDD**. A generic
   two-pad footprint and CPL rotation alone do not establish the physical winding
   orientation. No evidence here proves that it is reversed.
2. **Crystal startup remains unmeasured.** Y1 is TAXM12M4RFBCCT2T, CL 12 pF, with
   two 18 pF capacitors and a 1 kΩ drive resistor. This is plausible, but is a
   different crystal from Raspberry Pi's qualified reference. If supplies and RUN
   are correct but USB BOOTSEL does not enumerate, check the oscillator early;
   SWD is available for diagnosis. This is not a demonstrated need to change parts.

Manufacturer basis: [RP2350 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf),
sections 6.3.8, 8.2.1.1 and 14.3; local [selected crystal datasheet](../datasheets/TAXM12M4RFBCCT2T.pdf).

## Input-power cross-check

The existing input-only model was run without overwriting its tracked report:

| Assumed V5_SYS demand | USB source | Lowest event-window V5_SYS |
| --- | --- | --- |
| 0.1 A | 5.0 V | 4.339 V |
| 0.5 A | 5.0 V | 4.269 V |
| 0.5 A | 4.75 V | 4.065 V |

All exceed the AP63203's 3.8 V input minimum under the model's assumptions.
These are simulations of the input OR, not evidence that either regulator output
or the assembled board has been tested. Source current limits and startup loads
are not established by this model.
Source: [AP63203 datasheet](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf).

## First prototype check

Initially leave the SD card and external modules disconnected. Verify V3V3_SYS
and V3V3_ANA near 3.3 V, DVDD near 1.1 V, and RUN high; then test USB BOOTSEL
and load a minimal program before adding peripherals.

Raw results: `build/final-review/erc.rpt`, `drc.json`, `netlist.xml`,
`geometry.json` and `power-results.json`. The read-only DFM comparison also noted
an extra 0.30 mm routing-width preset; this is not a first-boot issue.
