# Saved-board electrical review — 2026-09-21

Reviewed the PCB saved at 21:05:34 local time after the owner's via-clearance
cleanup. Read-only design review: no routes, placements, zones, schematic content
or project rules were changed. Checks used existing zone fills; no refill was run.

No definite fatal wiring fault was found. This is not a guarantee of startup,
regulator stability, signal integrity or assembly yield. The core regulator below
is the main issue to resolve before fabrication.

## Verified results

- Schematic ERC: **0 violations**.
- PCB DRC: **0 unconnected items; 0 schematic-parity issues**. No reported copper
  shorts, copper-clearance errors, hole-clearance errors or solder-mask bridges.
- Remaining DRC: **78 courtyard-spacing errors and 80 small-MCU-land warnings**.
  This run reported no silkscreen violations.
- Every courtyard finding reports a positive gap (smallest 0.0221 mm between
  courtyards). These violate additional project spacing margins, not reported
  physical courtyard intersections. They still need assembly review; do not
  move decouplers away from ICs solely to satisfy excessive spacing margins.
- The project's connection checker passed 193 critical pin mappings, all 48 GPIO
  allocations, power/USB polarity, connector assignments and pad coverage for
  107 components. It checks intended connections, not analog performance.
- RP2354B power/ground, RC-filtered VREG_AVDD, RUN pull-up/reset, BOOTSEL path,
  USB D+/D- and both USB-C CC resistors have the intended connections.
- The optional U24 remains DNP; RP2354B has internal flash, so an unpopulated
  U24 is not a missing boot-memory fault. SWD is available on J10.
- Sensor buses and pull-ups, native SD mapping/pull-ups and its clock resistor
  match the saved schematic and intended allocation.
- The MCU has the expected 0.4 mm pitch and 3.4 mm exposed ground pad. Its
  0.20 mm-wide peripheral lands trigger a generic 0.25 mm review threshold;
  Raspberry Pi's recommended footprint itself uses 0.22 mm lands. These generic
  warnings are not evidence that the package cannot be manufactured. Final
  HASL/fine-pitch assembly and orientation still need the assembly preview.

## 1. Core regulator: resolve before fabrication

**Confirmed deviation:** the filled In1.Cu ground plane is present immediately
under L20 and the VREG_LX route. There is no local plane cutout or rule area.
Copper occupancy was checked at (98.05,109.15), (97.55,109.15), (97.30,108.00)
and (97.80,106.50) mm. L20 is centered at (98.05,109.15).

Raspberry Pi explicitly calls for removing copper immediately below the inductor
and switching node on the adjacent layer of a multilayer board. This is a local
cutout around the regulator, not a reason to remove ground under unrelated signals.

The complete C39/L20/C45 return loop also merits comparison against the reference:
C39 GND returns via (100.60,110.25); C45 GND via (98.194518,106.961548);
VREG_PGND via (97.30,105.15). The high-current ground returns are distributed
through the plane rather than the reference's compact common-ground arrangement.
Connectivity is correct; parasitic impedance and coupling remain unverified.
Do not simply widen LX everywhere: the manufacturer also asks to minimize its
copper/parasitics. Keep C41's analog filter return separate from switching current.

**Consequence:** possible unstable/noisy core supply or load-dependent resets;
not proof that the board will fail to boot. This is the highest-priority layout
risk found in the review. Follow the reference layout locally and verify L20's
winding-dot orientation in the actual assembly preview. A generic two-pad inductor
footprint and zero-degree placement do not prove the physical dot orientation.
No claim is made that the present assembled orientation is definitely reversed.

Source: [RP2350 datasheet](../datasheets/RP2350.pdf), section 6.3.8 and figures
23–24 (printed pages 454–455; PDF pages 455–456).
[Abracon inductor drawing and polarity marking](https://abracon.com/datasheets/AOTA-B201610S3R3-101-T.pdf)

## 2. Crystal: startup qualification remains open

Y1 is TAXM12M4RFBCCT2T (12 MHz, CL 12 pF, ESR at most 60 ohms), with C46/C47
18 pF and R21 1 kilohm. XIN/XOUT connectivity is correct. Two 18 pF capacitors
provide 9 pF series load before board/pin parasitics; that is plausible for a
12 pF crystal, but it does not establish oscillation margin or drive level.

This is an alternative to Raspberry Pi's validated ABM8-272-T3 network. Either
use the recommended crystal with its recommended network, or establish startup
and drive-level margins for this exact alternative across supply and temperature.
Do not blindly change the capacitors to another board's values.

**Consequence:** a nonstarting oscillator could prevent normal USB BOOTSEL and
application startup. No evidence was found that this particular crystal is
certain to fail; it is a qualification risk, not a confirmed wiring defect.

Sources: [selected crystal datasheet](../datasheets/TAXM12M4RFBCCT2T.pdf);
[Raspberry Pi crystal recommendation](https://www.raspberrypi.com/news/rp2350-now-available-at-jlcpcb/).

## 3. Barometer: sensor-performance concern, not a dead-board fault

U22 uses ordinary per-pad mask openings; no footprint graphic opens the whole
under-body mask area. Bosch recommends no solder mask beneath BMP581 and warns
that material contacting the body can affect performance. Its landing-pattern
section also discourages under-body tracks and vias.

Review U22's mask/landing pattern against Bosch section 8.2 before assembly.
This does not imply the MCU or the rest of the board will be dead, but pressure
measurement quality matters for this controller.
Source: [BMP581 datasheet](../datasheets/BMP581.pdf), section 8.2.

## Other observations and limits

USB has the correct nets, CC resistors and 27-ohm series resistors. The actual
MCU-side routes are about 11.9/12.0 mm long at 0.20 mm width. The series resistors
are nearer the connector than the MCU; Raspberry Pi recommends them near the MCU.
This is a signal-integrity departure, not a demonstrated 12 Mbps USB failure.
Neither differential impedance nor USB compliance was measured here.

The 5 V input and 3.3 V rails have not been load/transient tested, and no final
external-module current budget was supplied. ERC/DRC do not validate those limits.
The existing input-only simulation does not test either regulator's real stability.
No new circuitry or performance promises are inferred from it.

Full local check results: `build/review/electrical-drc.json` and
`build/review/electrical-erc.json`. The owner's PCB geometry was preserved.
