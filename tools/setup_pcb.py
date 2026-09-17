#!/usr/bin/env python3
"""Build the MARV V2 PCB (MARV-V2.kicad_pcb) from the schematic netlist.

WHAT IT DOES
------------
This script *regenerates the board from scratch* on every run:

  1. exports a kicadxml netlist from MARV-V2.kicad_sch with kicad-cli
     (skip with --no-netlist, override with --netlist FILE),
  2. creates an empty 4-layer board, sets the layer stack, design rules and
     net classes,
  3. loads every footprint through the project + global fp-lib-table
     (KIPRJMOD is resolved to the project directory),
  4. assigns every pad its net from the netlist,
  5. places the parts: edge-bound connectors are anchored to the board edge,
     interior parts are shelf-packed into named regions (a *coarse first
     placement*, not a final one),
  6. draws the rounded-rectangle Edge.Cuts outline and the F.SilkS labels,
  7. checks courtyard overlaps / copper-to-edge / hole keepouts itself and
     prints a report,
  8. saves MARV-V2.kicad_pcb (and, via pcbnew, the board settings inside
     MARV-V2.kicad_pro), then injects the physical stack-up into the .kicad_pcb
     and the net-class patterns into the .kicad_pro.

IDEMPOTENCY
-----------
The board is rebuilt from the netlist every run, so running the script twice
produces the same file: nothing is ever duplicated.  The flip side is that the
script *starts from a blank board*: any manual work done in pcbnew (tracks,
zones, hand placement) is DISCARDED.  As a guard, if the existing board already
contains tracks or zones the script refuses to run unless --force is given, and
it always keeps a copy of the previous board in backups/ .

RE-RUN
------
    cd /home/luis/Documents/kicad/MARV-V2
    python3 tools/setup_pcb.py                 # rebuild at the default size
    python3 tools/setup_pcb.py --width 48 --height 40    # try another envelope
    python3 tools/setup_pcb.py --dry-run       # place + check, do not write

    kicad-cli pcb drc --severity-all --exit-code-violations \
        -o reports/pcb-drc.rpt MARV-V2.kicad_pcb
    kicad-cli pcb render --side top --width 2400 --height 1600 \
        -o reports/pcb-top.png MARV-V2.kicad_pcb
    kicad-cli pcb export svg --mode-single --page-size-mode 2 \
        --layers F.Cu,F.SilkS,Edge.Cuts -o reports/pcb-top.svg MARV-V2.kicad_pcb

COORDINATES
-----------
Everything in the placement tables below is in *board coordinates*: origin at
the board centre, +X right, +Y **up**.  They are converted to KiCad's y-down
coordinates in one place (to_kicad()).

The board is a RECTANGLE (BOARD_W x BOARD_H) and the mounting square is
OFF-CENTRE in X, so there is no single half-size: self.HX and self.HY are the
half-width and half-height and every edge calculation names the one it means.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pcbnew

PRJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(PRJ, "MARV-V2.kicad_pcb")
PRO = os.path.join(PRJ, "MARV-V2.kicad_pro")
SCH = os.path.join(PRJ, "MARV-V2.kicad_sch")
NETLIST = os.path.join(PRJ, "reports", "pcb-netlist.xml")

# board centre in KiCad page coordinates
CX, CY = 100.0, 100.0

# --------------------------------------------------------------------------
# physical parameters (lead's decisions)
# --------------------------------------------------------------------------
# Envelope: the madflight FC3v2 outline (lead's decision).  Rectangular, and
# the standard 30.5 x 30.5 mm mounting square is OFF-CENTRE in X - 7.0 mm of
# margin outside the left holes (which is where the ESC pad row J3 lives) and
# 13.2 mm outside the right holes (which is where the 3-column IO block lives).
# The envelope the lead specified is 50.7 x 41.6.  This revision moved the ESC
# pad row J3, the DBG pad row J10 and TP1-TP10 to the BACK (see BACK_* below),
# which gave back the 7 mm left-edge pocket J3 used to need and the ten 1 mm
# pads that used to sit on the sensor island, so the envelope shrank again:
# the delivered board is the smallest size that still passes every placement
# rule (see the shrink study in DESIGN_SPEC "Envelope").  46.6 mm is where the
# IO block's fixed row-caption band reaches the right-hand grommet keepouts,
# 39.0 mm is where the microSD socket on the top edge reaches the top pair.
BOARD_W = 46.6           # board width  (X), mm  -- see --width
BOARD_H = 41.2           # board height (Y), mm  -- see --height
CORNER_R = 2.0           # Edge.Cuts corner radius, mm
MOUNT_PITCH = 30.5       # standard four-hole square, hole centre to hole centre
# Left margin: with J3 on the back there is nothing outboard of the left holes
# any more, so the margin is the minimum the grommet keepout itself allows -
# the O 6.5 mm flange courtyard needs 3.25 mm plus 0.5 mm to the board edge,
# i.e. a hole centre 3.75 mm in; 4.0 mm is that with 0.25 mm to spare.
MOUNT_MARGIN_L = 4.0     # left board edge to the left hole centres
MOUNT_X_L = -BOARD_W / 2.0 + MOUNT_MARGIN_L          # -19.30 at 46.6 mm
MOUNT_X_R = MOUNT_X_L + MOUNT_PITCH                  # +11.20 at 46.6 mm
MOUNT_Y = MOUNT_PITCH / 2.0                          # +-15.25, centred in Y
# MOUNT_X_L/R above are the DEFAULT-width values, quoted here because they are
# the numbers in DESIGN_SPEC; Builder recomputes both from the width actually
# asked for, so --width slides the holes and keeps the 4.0 mm left margin (and
# with it the IO block's right-hand margin) rather than eating it.
MOUNT_KEEPOUT_R = 3.25   # grommet flange courtyard radius of the H* footprint
                         # (O 6.5 mm; it was O 8.0 mm before this revision -
                         # see MARV_Packages.pretty/MountingHole_4.0mm_Grommet)
MOUNT_COPPER_R = 2.5     # the same footprint's O 5.0 mm *.Cu keepout zone.
                         # The flange courtyard above is a FRONT-side keepout
                         # for parts; this one is copper on every layer, so it
                         # is what the back-side pads have to clear.
EDGE_COPPER = 0.3        # copper-to-edge design rule, mm
PAD_EDGE_INSET = 0.5     # pad outer edge this far in from Edge.Cuts
POCKET_L = 0.9           # left board edge to the left-centre pocket.  It
                         # used to be 3.4 mm because the ESC pad row and its
                         # silk label band lived outboard of it; with J3 on
                         # the back nothing does, so it is now just
                         # copper-to-edge plus a margin, and the 2.5 mm that
                         # freed came off the board width.
BOARD_THICKNESS = 1.6

# --------------------------------------------------------------------------
# THE BACK SIDE (lead's decision)
# --------------------------------------------------------------------------
# Assembly stays SINGLE SIDED: every *component* is on F.Cu.  What moves to
# B.Cu is bare pads only - the two solder pad rows and the ten test points -
# which is what DESIGN_SPEC's "B.Cu carries routing and pads only" already
# permits.  They are placed with pcbnew's Flip, so pads, mask, silkscreen and
# courtyard all land on the B.* layers and KiCad, not this script, does the
# layer bookkeeping (LIBRARIES.md "pad rows").
#
# Why: J3 faces the ESC in the stack, so an 8-wire harness off the back runs
# straight down instead of round the edge; J10 and TP1-TP10 are bench-only and
# are reached with the stack apart.  Moving them off the front freed the 7 mm
# left-edge pocket, the bottom-right corner and ten 1 mm pads' worth of sensor
# island - the three things the envelope was standing on.
BACK_PAD_ROWS = ("J3", "J10")
# THE OPTIONAL FLASH/PSRAM EXPANSION (lead's decision A).  U24 and its two
# bypass caps C62/C63 are DNP in the schematic - `(dnp yes) (in_bom no)`, see
# tools/build_power.py Sheet.add - and their land patterns go on B.Cu, under
# the MCU against its QSPI pads.  They are the ONE exception to "the back
# carries bare pads only": a DNP land is not an assembled component, nothing
# on it is reflowed, so the front is still the single sided assembly the
# stack-up rests on.  check_back() asserts all three really do carry the DNP
# attribute, so a part that is accidentally populated fails the build rather
# than quietly appearing on the back of a reflowed board.
# R35, the FLASH_CS1 pull-up, stays POPULATED on the FRONT: GPIO0 has to be
# held deselected whether or not the socket is fitted.
BACK_DNP_PARTS = ("U24",)
# every back-side part gets a visible reference on B.SilkS: nothing else is
# there to collide with, and a bare pad with no legend is unusable on a bench.
BACK_REF_SILK = True
# J3, the ESC row: VERTICAL against the LEFT BOARD EDGE, pad 1 (CURR) at the
# top, pad outer edge PAD_EDGE_INSET in from Edge.Cuts - edge-aligned exactly
# as the DBG row J10 is against the bottom edge - and centred in Y between
# the two left grommets.  Eight pads on 2.00 mm pitch span +-7.0 mm of pad
# centres (+-7.7 mm of copper), and the grommets' O 5 mm copper keepout at
# y = +-15.25 only reaches |y| = 12.75, so the row clears both by 5 mm with
# nothing but the keepout deciding it.  Its labels go INBOARD (+x), which is
# the band nothing else on the back uses.
# Why the edge: the harness leaves the stack at the board edge instead of
# from under the middle of the board, and the left margin is dead area on
# both sides now that the front carries nothing outboard of the left holes.
# Rotation 270 is what puts pad 1 at the top of a flipped row; check_back()
# asserts it, because the flip mirrors the footprint and a wrong rotation
# silently reverses the harness order.
ESC_BACK_Y = 0.0
ESC_BACK_ROT = 270
# TP1-TP10: two columns this far right of the sensor island's left edge, on a
# 2.4 mm grid (1 x 1 mm pads, 2 x 2 mm courtyards), five rows from TP_GRID_Y
# downward - directly under U21/U22/U23, so every via is the board thickness
# and nothing else.
J10_LABEL_DY = 3.3       # J10's captions stand this far above its pads
FLASH_LEGEND_SZ = 0.60   # = RULES["min_text_height"]; the U24 legend is
FLASH_LEGEND_DY = 1.30   # three lines and has to fit the corridor between
                         # J3's label band and the J10 pads
TP_GRID_X = (0.6, 3.0)
TP_GRID_Y = 0.6
TP_GRID_DY = 2.4

# JLCPCB JLC04161H-7628, 4 layer 1.6 mm
STACKUP = [
    ("F.Cu", "copper", 0.035, None, None, None),
    ("dielectric 1", "prepreg", 0.2104, "PP-7628", 4.4, 0.02),
    ("In1.Cu", "copper", 0.0152, None, None, None),
    ("dielectric 2", "core", 1.065, "FR4", 4.6, 0.02),
    ("In2.Cu", "copper", 0.0152, None, None, None),
    ("dielectric 3", "prepreg", 0.2104, "PP-7628", 4.4, 0.02),
    ("B.Cu", "copper", 0.035, None, None, None),
]

# design rules (JLCPCB 4-layer capability)
RULES = dict(
    min_track=0.127,
    min_clearance=0.127,
    min_via_drill=0.2,
    min_via_dia=0.45,
    min_annular=0.125,     # (0.45 - 0.2) / 2
    min_hole_to_hole=0.254,
    copper_edge=EDGE_COPPER,
    min_through_hole=0.2,
    min_text_height=0.6,
    min_text_thickness=0.12,
    # outer GND pours: 0402 GND pads between dense copper can only fit one
    # thermal spoke; one spoke plus the via to the In1 plane is enough
    min_resolved_spokes=1,
    mask_min_web=0.10,
    # 0 expansion: the ICM-45686 LGA-14 has 0.15 mm pad gaps, any positive
    # expansion drops the mask web below the 0.10 mm minimum
    mask_expansion=0.0,
)

# net classes: name -> (track, clearance, via_dia, via_drill, dp_width, dp_gap,
#                       priority, [net name patterns])
#
# USB pair geometry: F.Cu over the In1.Cu GND plane, h = 0.2104 mm of 7628
# prepreg (er 4.4), t = 35 um.  Hammerstad-Jensen microstrip with the standard
# thickness correction gives Z0 = 55.5 ohm for w = 0.30 mm; the usual coupling
# factor Zdiff = 2*Z0*(1 - 0.48*exp(-0.96*s/h)) gives Zdiff = 89.5 ohm at
# s = 0.20 mm.  -> 0.30 mm / 0.20 mm.  Confirm against the fab's impedance
# calculator before release.
NETCLASSES = [
    # name        track clr   via_d via_dr dpw   dpg  prio patterns
    ("Default",   0.20, 0.15, 0.60, 0.30, 0.30, 0.20, None, []),
    # Rail3V3: the two regulated 3.3 V rails, split out of Power so they can
    # run a lighter track/via geometry than the switcher SW/VO/BST nodes.
    # Priority 5 is lower than Power's 10 (lower number wins - see
    # makeEffectiveNetclass in KiCad's NET_SETTINGS::GetEffectiveNetClass),
    # so Rail3V3 would win a pattern conflict against Power; the two lists
    # are disjoint today, but the priorities stay consistent with that rule.
    ("Rail3V3",   0.30, 0.15, 0.60, 0.30, 0.30, 0.20, 5,
     ["V3V3_SYS", "V3V3_ANA"]),
    ("Power",     0.50, 0.15, 0.80, 0.40, 0.50, 0.20, 10,
     ["VBAT", "5V_IN", "V5_SYS", "USB_VBUS",
      "U7_SW", "U7_VO", "U26_SW", "U26_BST"]),
    # USB clearance is 0.18 mm, not the 0.20 mm of the pair gap: R22/R23 are
    # 0201 series resistors and the R_0201_0603Metric land has 0.18 mm between
    # its own two pads, which are two different USB nets.  0.20 mm made that
    # intrinsic gap a DRC error.  Nothing is routed tighter for it - the pair
    # still runs at dp_gap 0.20 mm, and 0.18 mm is well above the 0.127 mm
    # board minimum and JLC's capability.
    ("USB",       0.30, 0.18, 0.60, 0.30, 0.30, 0.20, 20,
     ["USB_DP", "USB_DM", "USB_DP_MCU", "USB_DM_MCU", "USB_DP_RP",
      "USB_DM_RP"]),
    # PWM_ESC covers both actuator groups: PWM1-4 leave on the J3 ESC pad row,
    # PWM5-8 on rows 7-10 of the IO block.  Same 3.3 V logic edges into the same
    # kind of load, so they get the same 0.25 mm track and clearance.
    # FLASH_CS1 deliberately stays in Default: it is a QSPI chip select on the
    # MCU's dedicated flash pads, not an actuator signal, and none of the
    # SensorSPI "*_CS" patterns match it either.
    ("PWM_ESC",   0.25, 0.15, 0.60, 0.30, 0.25, 0.20, 30,
     ["PWM1", "PWM2", "PWM3", "PWM4", "PWM5", "PWM6", "PWM7", "PWM8",
      "ESC_TELEM", "ESC_TELEM_RX", "CURR_SENSE", "CURR_SENSE_RAW"]),
    ("SensorSPI", 0.20, 0.15, 0.60, 0.30, 0.15, 0.15, 40,
     ["SENS_*", "*_CS", "*_INT", "*_INT1", "*_INT2"]),
]

# The board is a dense single-sided assembly: only the connectors and the
# switches keep a silkscreen reference designator, the per-pad function labels
# are the silkscreen.  Every other reference stays on F.Fab (hidden on silk).
# J3/J10/TP* are not in this list because they are on the BACK: their
# references are handled by back_silk(), which never has to fight for room.
REF_ON_SILK = ("J4", "J6", "J7", "J8", "J11", "SW1", "SW2")

# --------------------------------------------------------------------------
# placement rules that are circuit requirements, checked after placement
# --------------------------------------------------------------------------
# Switcher loop components that have to end up next to their regulator.  The
# rule is measured *body to body* (courtyard gap), not centre to centre: the
# output caps of both bucks sit on the far side of a 4.6 mm inductor, so no
# layout can put their centres within 6 mm of the IC centre, while a 6 mm gap
# between the bodies is exactly the "keep the loop short" requirement.
# Seeds for the packer are in POWER_LOOP (see floorplan()).
CAP_NEAR = {"U7":  ["C8", "C10", "C11", "C12", "C23", "C24", "FB1"],
            "U26": ["C73", "C76", "C77", "C80"]}
CAP_NEAR_MM = 6.0
# no switching inductor within this distance (body to body) of a MEMS sensor
INDUCTORS = ["L2", "L3"]
SENSORS = ["U21", "U22", "U23"]
IND_SENSOR_MM = 8.0
# TP1-TP10 probe the sensor SPI bus, its chip selects and its interrupts.  A
# test point that is not at the part it probes is a stub, so each one has to
# land within this distance (body to body) of the nearest sensor.
TEST_POINTS = re.compile(r"^TP\d+$")
TP_NEAR_MM = 6.0

# THE CORRIDOR BESIDE THE QFN (lead's decision).  U20 carries 39 satellites
# and nearly all of them leave on its left and right edges, so the width of
# the lane between the package and whatever is parked beside it is what
# decides whether a 100 nF can reach its IOVDD pin at all.  At 1.07 mm to
# U25 and 0.36 mm to the sensor island there was no lane: an 0402 courtyard
# is 1.12 x 0.62 mm, so neither side could take one in any orientation and
# fifteen rows were unsatisfiable on an EMPTY board.  2.6 mm takes an 0402
# lengthwise (1.12) plus its 0.05 gaps with 1.3 mm of routing lane left
# over.  Enforced in floorplan() against every IC and connector courtyard on
# those two flanks, and the resulting gaps are printed.
U20_CORRIDOR = 2.6

# --------------------------------------------------------------------------
# SATELLITES: the passive that belongs AT a pin (lead's decision)
# --------------------------------------------------------------------------
# Shelf-packing a region from one seed puts a decoupling capacitor somewhere
# in the same neighbourhood as the IC; it does not put it at the pin, and a
# decoupling cap that is not at the pin is just a lump of capacitance on the
# plane.  Every passive whose whole job is to sit on one pin of one part is
# listed here instead of in a region, and place_satellites() drops it against
# that pad with its owner-net pad facing the pin.
#
#   ref -> (owner ref, owner pad, what it is, rank, order)
#
# The owner pad is either a pad NUMBER or ("net", NAME) - "the owner's pad
# that carries NAME", resolved against the loaded netlist in
# verify_satellites().  The second form is how a part that belongs at a
# CONNECTOR pin is written: J11's SD_CMD pin is pad 3 only until the socket
# is re-drawn, but it carries SD_CMD by definition.
#
# rank is how close it has to end up (SAT_NEAR_MM, checked in
# check_satellites(), measured PAD TO PAD - the satellite's pad on the owner's
# net to the owner's pad, which is the loop the part actually closes):
#   0  on the pin      decoupling, loop caps, series terminators
#   1  next to the pin  the second element of a chain, feedback dividers
#   2  in the neighbourhood  pull-ups, enables, the far end of a divider
#   3  on the rail       bulk reservoirs.  A 22 uF/100 uF bulk cap is not a
#      pin part at all: it holds a RAIL up over microseconds, and where on
#      that rail it sits changes nothing a millimetre of copper does not.
#      Ranked with the pin parts it was taking their cells.
# order breaks the tie inside a rank: the lower number is placed first and so
# gets the nearer slot (C17 before C8/C9, C74 before C73, C41 before R20).
#
# Every row is verified against the loaded netlist at generation time
# (verify_satellites()): the owner pad and the satellite have to share a net,
# or the build fails - the table can never drift away from the schematic.
SATELLITES = {
    # ---- U20 RP2354B (QFN-80) ----------------------------------------
    # the eight IOVDD 100 nF, one per supply pin, and the OTP supply
    "C30": ("U20", "5",  "IOVDD 100n",     0, 0),
    "C31": ("U20", "15", "IOVDD 100n",     0, 0),
    "C32": ("U20", "24", "IOVDD 100n",     0, 0),
    "C33": ("U20", "29", "IOVDD 100n",     0, 0),
    "C34": ("U20", "41", "IOVDD 100n",     0, 0),
    "C35": ("U20", "50", "IOVDD 100n",     0, 0),
    "C36": ("U20", "60", "IOVDD 100n",     0, 0),
    "C37": ("U20", "76", "IOVDD 100n",     0, 0),
    "C38": ("U20", "68", "USB_OTP 100n",   0, 0),
    # the core rail: 100 nF on each DVDD pin, the 4.7 uF reservoir beside the
    # one that also carries the regulator's own output (pin 51)
    "C42": ("U20", "10", "DVDD 100n",      0, 0),
    "C43": ("U20", "32", "DVDD 100n",      0, 0),
    "C44": ("U20", "51", "DVDD 100n",      0, 0),
    "C45": ("U20", "51", "DVDD 4u7",       1, 0),
    "C39": ("U20", "64", "VREG_VIN 4u7",   1, 0),
    "C40": ("U20", "59", "ADC_AVDD 100n",  0, 0),
    # the on-chip regulator: C41 on the AVDD pin, R20 (the 1 R feed) behind it
    "C41": ("U20", "61", "VREG_AVDD 4u7", 0, 0),
    "R20": ("U20", "61", "VREG_AVDD 33R", 1, 1),
    "L20": ("U20", "63", "VREG_LX 3u3",    1, 0),
    # USB: the 27 R series pair, one per data pin.  Owner pad resolved by net
    # (not a hard pad number): a GPIO reassignment cannot move these pins,
    # but they are wired the same way as the other signal-owned rows below.
    "R22": ("U20", ("net", "USB_DP_RP"), "USB 27R",        0, 0),
    "R23": ("U20", ("net", "USB_DM_RP"), "USB 27R",        0, 0),
    # the three ADC front ends.  The cap is the one that has to be at the pin
    # (it is what the SAR samples into); the resistors chain outward from it.
    # Owner pads are resolved BY NET, not by pad number: VBAT_SENSE/VBUS_SENSE/
    # CURR_SENSE/ESC_TELEM_RX/FLASH_CS1 sit on GPIOs whose QFN pad can move
    # with a GPIO reassignment (PINOUT.md), so a hard pad number here would
    # silently go stale the next time the pin plan changes.
    "C78": ("U20", ("net", "CURR_SENSE"), "ADC2 100n",     0, 0),
    "R53": ("U20", ("net", "CURR_SENSE"), "CURR_SENSE RC",  2, 0),
    "C48": ("U20", ("net", "VBAT_SENSE"), "ADC0 100n",     0, 0),
    "R28": ("U20", ("net", "VBAT_SENSE"), "VBAT div low",   1, 0),
    # the TOP of a divider is on the rail being measured, not at the ADC:
    # only the bottom leg and the sampling cap close the ADC's own loop
    "R27": ("U20", ("net", "VBAT_SENSE"), "VBAT div high",  3, 0),
    "C49": ("U20", ("net", "VBUS_SENSE"), "ADC1 100n",     0, 0),
    "R30": ("U20", ("net", "VBUS_SENSE"), "VBUS div low",   1, 0),
    "R29": ("U20", ("net", "VBUS_SENSE"), "VBUS div high",  3, 0),
    # the ESC telemetry series terminator, at its driver
    "R54": ("U20", ("net", "ESC_TELEM_RX"), "ESC_TELEM 100R", 1, 0),
    "R35": ("U20", ("net", "FLASH_CS1"), "FLASH_CS1 pu",   2, 0),
    # R25/R26 (I2C), R36-R41 (SD) and R55 are NOT the MCU's any more: see
    # the J6 / J11 / D20 blocks below.

    # ---- U7 TPS62913 (the 3.3 V buck) --------------------------------
    # input loop first, smallest package nearest the pin: the 2.2 nF is the
    # high-frequency bypass and owns the slot against pin 6.
    "C17": ("U7", "6", "VIN 2n2",   0, 0),
    "C8":  ("U7", "6", "VIN 10u",   0, 1),
    "C9":  ("U7", "6", "VIN 10u",   0, 2),
    # output loop: the three 22 uF on VO, then the bead, then the post-bead
    # caps on the bead's own output pad
    "C10": ("U7", "3", "VO 22u",    0, 0),
    "C11": ("U7", "3", "VO 22u",    0, 1),
    "C12": ("U7", "3", "VO 22u",    0, 2),
    "FB1": ("U7", "3", "VO bead",   1, 0),
    "C13": ("U7", "8", "NR/SS 470n", 0, 3),
    "R7":  ("U7", "9", "FB div hi", 1, 1),
    "R8":  ("U7", "9", "FB div lo", 1, 2),
    "R9":  ("U7", "10", "S-CONF",   1, 3),
    "R10": ("U7", "5", "PG pull-up", 2, 0),
    # after the bead: the V3V3_SYS side of the rail
    "C23": ("FB1", "2", "V3V3 22u",  1, 0),
    "C24": ("FB1", "2", "V3V3 22u",  1, 1),
    # rank 3 (bulk, on the rail): the microSD socket's own V3V3_SYS supply
    # pad is as valid an anchor on that rail as the bead's output pad, and
    # putting the bulk caps there instead frees FB1's own cells for C23/C24.
    "C64": ("J11", ("net", "V3V3_SYS"), "V3V3 bulk",  3, 0),
    "C65": ("J11", ("net", "V3V3_SYS"), "V3V3 bulk",  3, 1),
    "C66": ("J11", ("net", "V3V3_SYS"), "V3V3 bulk",  3, 2),

    # ---- U26 AP63205 (the 5 V buck) ----------------------------------
    "C74": ("U26", "3", "VIN 100n", 0, 0),
    "C73": ("U26", "3", "VIN 10u",  0, 1),
    "C75": ("U26", "6", "BST 100n", 0, 0),
    "C76": ("U26", "1", "VO 22u",   0, 0),
    "C77": ("U26", "1", "VO 22u",   0, 1),
    "C80": ("U26", "1", "VO 22u",   0, 2),
    "R52": ("U26", "2", "EN",       2, 0),

    # ---- U25 TPS2121 (the priority mux) ------------------------------
    "C71": ("U25", "7",  "IN1 100n",   0, 0),
    "C72": ("U25", "2",  "IN2 100n",   0, 0),
    "C70": ("U25", "11", "SS 100n",    0, 0),
    "R42": ("U25", "6",  "PR1 div hi", 1, 0),
    "R43": ("U25", "6",  "PR1 div lo", 1, 1),
    "R44": ("U25", "5",  "OV1 div hi", 1, 0),
    "R45": ("U25", "5",  "OV1 div lo", 1, 1),
    "R46": ("U25", "10", "ILIM",       2, 0),
    "R47": ("U25", "9",  "ST pull-up", 2, 0),
    # the V5_SYS bulk hangs off the mux's OUT pin, which is where the rail
    # starts.  Rank 3: it holds the rail up, not the pin, and C19 (the
    # 100 uF polymer, 8.9 x 4.9 mm) is the biggest passive on the board -
    # ranked with the decoupling it simply ate the mux's pocket.
    "C19": ("U25", "1",  "V5_SYS 100u", 3, 0),
    "C20": ("U25", "1",  "V5_SYS 10u",  3, 1),
    "C21": ("U25", "1",  "V5_SYS 10u",  3, 2),

    # ---- U12 TPS7A2033 (the analog LDO) ------------------------------
    "C25": ("U12", "1", "IN 1u",  0, 0),
    "C26": ("U12", "5", "OUT 1u", 0, 0),

    # ---- J4 USB-C ----------------------------------------------------
    # The CC pull-downs are what the host measures, so they belong on the
    # receptacle rather than at the MCU - but CC is a DC level, not an edge:
    # rank 2 is near enough, and the receptacle's own shield pegs mean there
    # is no 2 mm cell beside A5/B5 to want.
    "R4": ("J4", ("net", "USB_CC1"), "CC1 5k1", 2, 0),
    "R5": ("J4", ("net", "USB_CC2"), "CC2 5k1", 2, 0),

    # ---- J11 microSD -------------------------------------------------
    # A bus pull-up holds the line up while the card is tri-stated; it is a
    # DC part and it belongs at the SOCKET, which is the far end of the
    # stub, not at the MCU 12 mm away where it was pulling the QFN's own
    # decoupling off the package.
    "R36": ("J11", ("net", "SD_CMD"), "SD_CMD pu", 2, 0),
    "R37": ("J11", ("net", "SD_D0"),  "SD_D0 pu",  2, 1),
    "R38": ("J11", ("net", "SD_D1"),  "SD_D1 pu",  2, 2),
    "R39": ("J11", ("net", "SD_D2"),  "SD_D2 pu",  2, 3),
    "R40": ("J11", ("net", "SD_D3"),  "SD_D3 pu",  2, 4),
    "R41": ("J11", ("net", "SD_DET"), "SD_DET pu", 2, 5),

    # ---- J6 the IO block's signal row --------------------------------
    # the magnetometer I2C pull-ups: the bus leaves the board on J6, so the
    # termination sits at the connector, at the end of the line
    "R25": ("J6", ("net", "MAG_SDA"), "I2C pull-up", 2, 0),
    "R26": ("J6", ("net", "MAG_SCL"), "I2C pull-up", 2, 1),

    # ---- D20 WS2812 RGB LED ------------------------------------------
    # R55 is the series terminator.  It damps the edge at whichever end of
    # the line is short: LED_DATA (MCU to R55) is 10 mm away across the
    # board and LED_DIN (R55 to D20) is the half that must stay short, so
    # the resistor sits at the LED.  C79 is the LED's own 5 V bypass and is
    # a genuine pin part.
    "C79": ("D20", ("net", "V5_SYS"),  "LED 5V 100n", 0, 0),
    "R55": ("D20", ("net", "LED_DIN"), "LED_DATA 100R", 1, 0),
    # U21/U22/U23: the twelve sensor supply caps are resolved from the
    # schematic at generation time - see sensor_satellites().
}

# how far from its pin a satellite of each rank may end up, pad to pad
SAT_NEAR_MM = {0: 3.0, 1: 4.0, 2: 6.0, 3: 10.0}
# the part is placed this far clear of the owner's courtyard edge
SAT_CLEAR = 0.35
# A satellite blocks the grid this far OUTSIDE its own courtyard.  The
# generic packer uses 0.1 mm; a satellite uses none, because the search
# already leaves 0.05 mm of its own around every candidate and the courtyard
# is the clearance.  At 0.1 mm each 0402 ate 3.4 mm2 of grid instead of 2.4
# and the top band ran out before C23/C24 (CAP_NEAR) were placed.
SAT_GROW = 0.0
# search radius for the satellite's own slot: the second one is a fallback
# and is reported
SAT_RADIUS = (3.0, 6.0)
# The passes place_satellites() makes over the whole satellite table, as
# (search radius from the seed, only take a spot that meets the rank's
# limit).  The two closed passes come first, so a part that cannot meet its
# limit anywhere never takes the cell of one that can; the open passes then
# place what is left, nearest first, and every spot they take is reported as
# a wide search.
SAT_PASSES = ((SAT_RADIUS[0], 1.0), (SAT_RADIUS[1], 1.0),
              (SAT_RADIUS[0], None), (SAT_RADIUS[1], None), (None, None))
# which region a *new* part on a satellite's net should be packed with, so
# that taking the satellites out of the region lists does not change how an
# unlisted part votes itself a home (see floorplan())
SAT_GROUP = {"U20": "mcu_ring", "U7": "u7", "FB1": "u7", "U26": "buck5",
             "U25": "mux", "U12": "reg3v3", "J4": "usb",
             "U21": "sens", "U22": "sens", "U23": "sens",
             "J11": "sd_pu", "J6": "i2c", "D20": "led"}
# the order the owners are served in.  FB1 is itself a satellite of U7, so it
# has to be placed before its own caps are.
SAT_OWNERS = ("U20", "U7", "FB1", "U26", "U25", "U12",
              "U21", "U22", "U23", "J4", "J11", "J6", "D20")
# the order owners are served in WITHIN one rank (lead's decision, distinct
# from SAT_OWNERS above, which only orders when each owner's satellites
# become eligible at all).  place_satellites() competes satellites
# nearest-first inside one (rank, owner) class at a time, in this order;
# an owner missing from the list is served last.
SAT_OWNER_PRIORITY = ["U20", "U7", "U26", "U25", "U12", "U21", "U22", "U23",
                      "FB1", "J11", "J6", "J4", "D20"]
# Already-placed parts whose pin distance is reported but never flagged: the
# crystal group is anchored at XIN/XOUT by floorplan() and is not the
# packer's to move.
SAT_REPORT = {"Y1": ("U20", "30"), "C46": ("U20", "30"),
              "R21": ("U20", "31"), "C47": ("Y1", "3")}

SILK_TEXT = 0.8          # refdes height, mm
SILK_THICK = 0.12
LABEL_TEXT = 0.7         # per-pad label height, mm
LABEL_SMALL = 0.65       # tight blocks (J16)
LABEL_THICK = 0.12

# THE IO BLOCK (J6 signal / J7 power / J8 GND), the right edge.
# ---------------------------------------------------------------------------
# Three 1x14 through-hole rows on the 2.54 mm grid, columns running
# GND | POWER | SIGNAL from the board edge inward, so the fourteen signal
# traces are the short ones (the block sits right of the MCU) and the two
# rails run down the outside.  The stock PinHeader_1x14 courtyard is the
# plastic body + 0.5 mm on every side, which makes three abutting rows overlap
# by 1.0 mm each; the vendored copy trims the courtyard to the body across the
# row (+-1.27 mm) so they abut exactly, and drops the silkscreen outline
# because the per-row label band needs that space.  Same treatment - and the
# same reason - as the servo rows and the 2x16 array this revision replaced.
IO_SRC = ("/usr/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty/"
          "PinHeader_1x14_P2.54mm_Vertical.kicad_mod")
IO_FP = "PinHeader_1x14_P2.54mm_Vertical_IORow"
IO_REFS = ("J6", "J7", "J8")          # signal (inner), power, GND (outer)
IO_CRTYD = (-1.2, -1.78, 1.2, 34.81)     # footprint-local, y-down; +-1.2
                         # rather than the +-1.27 half-body because the
                         # 0.05 mm stroke counts in the courtyard bbox and
                         # three rows on a 2.54 mm grid would then overlap
IO_PITCH = 2.54
IO_ROWS = 14
IO_EDGE = 1.5            # outermost pad CENTRE this far in from Edge.Cuts
                         # (0.65 mm of copper-to-edge, rule is 0.3)
IO_LABEL_X = 0.35        # label band, left of the signal column pad edge
IO_LABEL_DY = 0.63       # signal label above / power label below the row
IO_LABEL_SZ = 0.60       # = RULES["min_text_height"]; see silkscreen()
IO_LABEL_CLR = 0.2       # reserved margin around a label
IO_END_TICK = 1.10       # end tick, from the first/last row centre.  The
                         # block's own footprint has no outline, so the board
                         # draws these two ticks and the end labels beyond
                         # them - see Builder.io_end_labels()

# per-pad silkscreen labels: ref -> {pad number: label}
PAD_LABELS = {
    "J3":  ["CURR", "TX", "M4", "M3", "M2", "M1", "VBAT", "GND"],
    # the IO block, row 1 (top) to row 14: the signal name and the rail its
    # power pin carries.  io_labels(), the reserved silk bands in floorplan()
    # and the netlist row table all index this same list.
    "J6":  ["T0", "R0", "T1", "R1", "SDA", "SCL", "S5", "S6", "S7", "S8",
            "A44", "A45", "A46", "A47"],
    "J7":  ["5V", "5V", "5V", "5V", "3V3", "3V3", "5V", "5V", "5V", "5V",
            "3V3", "3V3", "3V3", "3V3"],
    "J10": ["SWCLK", "SWDIO", "GND"],
}


def localize_model(txt, name):
    """Point the vendored footprint's (model ...) at a project-local STEP copy
    (MARV_Packages.3dshapes/<name>.step), copying the KiCad model there if
    missing, so the project stays self-contained like every other vendored
    footprint (see LIBRARIES.md)."""
    import shutil
    m = re.search(r'\(model "([^"]+)"', txt)
    if not m:
        return txt
    src = m.group(1).replace("${KICAD10_3DMODEL_DIR}", "/usr/share/kicad/3dmodels") \
                    .replace("${KICAD9_3DMODEL_DIR}", "/usr/share/kicad/3dmodels")
    dst_rel = "MARV_Packages.3dshapes/" + name + ".step"
    dst = os.path.join(PRJ, dst_rel)
    if not os.path.exists(dst) and os.path.exists(src):
        shutil.copyfile(src, dst)
    return txt.replace(m.group(1), "${KIPRJMOD}/" + dst_rel, 1)

def vendor_row_footprint(src, name, crtyd, descr):
    """Write MARV_Packages/<name>: a stock KiCad pin-header footprint with its
    courtyard replaced by `crtyd` (footprint-local, y-down) and its silkscreen
    outline dropped, so several rows can abut on the 2.54 mm grid and the board
    can draw the labels that would otherwise land under that outline.

    Pads, drills, fabrication layer and the 3D model reference are untouched,
    so this stays the stock part; only the two layers the board overrides are
    replaced.  The model is localized into MARV_Packages.3dshapes so the
    project remains self-contained (LIBRARIES.md).

    Generalized from the J12-J14 servo-row vendoring it replaces: same trade,
    now used once instead of twice.
    """
    txt = open(src).read()
    txt = re.sub(r'\(footprint "[^"]+"', '(footprint "%s"' % name, txt, 1)
    txt = re.sub(r'\(descr "[^"]*"', '(descr "%s"' % descr, txt, 1)

    def drop(m):
        return "" if ('F.CrtYd' in m.group(0)
                      or 'F.SilkS' in m.group(0)) else m.group(0)
    txt = re.sub(r"\n\t\(fp_\w+\n.*?\n\t\)", drop, txt, flags=re.S)
    x0, y0, x1, y1 = crtyd
    rect = ('\n\t(fp_rect\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n'
            '\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill no)\n'
            '\t\t(layer "F.CrtYd")\n\t)' % (x0, y0, x1, y1))
    i = txt.rindex("\n\t(pad ")
    txt = txt[:i] + rect + txt[i:]
    txt = localize_model(txt, name)
    out = os.path.join(PRJ, "MARV_Packages.pretty", name + ".kicad_mod")
    old = open(out).read() if os.path.exists(out) else None
    if old != txt:
        open(out, "w").write(txt)
    return "MARV_Packages:" + name


def vendor_io_footprint():
    """The one vendored footprint this board still needs: the 1x14 row of the
    J6/J7/J8 IO block (see the IO_* block above)."""
    return vendor_row_footprint(
        IO_SRC, IO_FP, IO_CRTYD,
        "Through hole straight pin header, 1x14, 2.54mm pitch, single row -- "
        "MARV V2 copy for the J6/J7/J8 IO block on the right board edge. The "
        "courtyard is trimmed to the plastic body across the row (+-1.27 mm, "
        "no side margin) so the three columns GND | POWER | SIGNAL abut "
        "exactly on the 2.54 mm grid, and the silkscreen outline is dropped "
        "because the per-row label band needs that space; the board draws the "
        "end ticks, the pin-1 mark and every label instead. Pads, drills, "
        "fabrication layer and 3D model are unchanged.")


def mm(v):
    return pcbnew.FromMM(float(v))


def tomm(v):
    return pcbnew.ToMM(v)


def to_kicad(x, y):
    """board coords (y up, origin = board centre) -> KiCad VECTOR2I"""
    return pcbnew.VECTOR2I(mm(CX + x), mm(CY - y))


# --------------------------------------------------------------------------
# netlist
# --------------------------------------------------------------------------
def export_netlist(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format",
                    "kicadxml", "-o", path, SCH], check=True,
                   stdout=subprocess.DEVNULL)


def read_netlist(path):
    root = ET.parse(path).getroot()
    comps = {}
    for c in root.find("components").findall("comp"):
        ref = c.get("ref")
        sheet = c.find("sheetpath")
        tstamps = sheet.get("tstamps") if sheet is not None else "/"
        # KiCad emits <property name="dnp"/> (and exclude_from_bom) for a
        # symbol marked DO NOT POPULATE.  It is carried onto the footprint so
        # the board file, the position files and check_back() all agree with
        # the schematic instead of restating it.
        props = {pr.get("name") for pr in c.findall("property")}
        comps[ref] = dict(ref=ref, value=c.findtext("value") or "",
                          fp=c.findtext("footprint") or "",
                          dnp="dnp" in props,
                          no_bom="exclude_from_bom" in props,
                          path=tstamps + (c.findtext("tstamps") or ""))
    nets = []
    for n in root.find("nets").findall("net"):
        nodes = [(nd.get("ref"), nd.get("pin")) for nd in n.findall("node")]
        nets.append((n.get("name"), nodes))
    return comps, nets


def read_pinfunctions(path):
    """(ref, pin) -> the pin's schematic name, from the same netlist.

    kicad-cli writes <node ref pin pinfunction pintype/>, so the board can ask
    "which pad of U21 is VDDIO?" instead of a table restating the symbol."""
    root = ET.parse(path).getroot()
    out = {}
    for n in root.find("nets").findall("net"):
        for nd in n.findall("node"):
            fn = nd.get("pinfunction")
            if fn:
                out[(nd.get("ref"), nd.get("pin"))] = fn
    return out


def norm_pin(name):
    """VDD_IO_1 / VDDIO_5 / VS_6 -> VDDIO / VDDIO / VS.  KiCad suffixes a
    duplicated pin name with its number, and the schematic writes the same
    supply as VDDIO on one part and VDD_IO on another."""
    name = re.sub(r"_\d+$", "", name)
    return name.replace("_", "").upper()


def sensor_satellites(comps, pinfunc):
    """C50-C61, the sensor supply caps, resolved from the schematic.

    Their Value strings name the pin they belong to ("100n / 16 V X7R,
    U21 VDDIO" - see imu/baro/highg.kicad_sch and tools/build_power.py), and the
    netlist names every pad, so the owner pad is looked up rather than
    written down twice.  A cap that cannot be attributed FAILS the build:
    an unattributed bypass cap is one that would have been shelf-packed
    somewhere on the island, which is the thing this table exists to stop.
    """
    out = {}
    bad = []
    for ref, c in comps.items():
        v = c.get("value", "")
        m = re.search(r"\b(U2[123])\s+([A-Z0-9_]+)\s*$", v.strip())
        if not (ref.startswith("C") and re.search(r"\bU2[123]\b", v)):
            continue
        if not m:
            bad.append("%s: cannot read an owner pin out of %r" % (ref, v))
            continue
        owner, pin = m.group(1), norm_pin(m.group(2))
        pads = [p for (r, p), fn in pinfunc.items()
                if r == owner and norm_pin(fn) == pin]
        if len(pads) != 1:
            bad.append("%s: %s has %d pins called %s"
                       % (ref, owner, len(pads), pin))
            continue
        # 100 nF goes on the pin, the 1 uF reservoir behind it
        small = v.lower().startswith("100n")
        out[ref] = (owner, pads[0], "%s %s" % (pin, "100n" if small else "1u"),
                    0 if small else 1, 0)
    if bad:
        raise SystemExit("sensor decoupling cannot be attributed:\n  "
                         + "\n  ".join(bad))
    return out


# --------------------------------------------------------------------------
# footprint libraries
# --------------------------------------------------------------------------
def parse_fp_table(path, subs, out=None):
    out = {} if out is None else out
    if not os.path.exists(path):
        return out
    txt = open(path).read()
    for m in re.finditer(r'\(lib\s+\(name\s+"([^"]+)"\)\s*\(type\s+"([^"]+)"\)'
                         r'\s*\(uri\s+"([^"]+)"\)', txt):
        name, typ, uri = m.groups()
        for k, v in subs.items():
            uri = uri.replace("${%s}" % k, v).replace("$(%s)" % k, v)
        if typ.lower() == "table":
            parse_fp_table(uri, subs, out)
        else:
            out.setdefault(name, uri)
    return out


def footprint_libs():
    subs = {"KIPRJMOD": PRJ,
            "KICAD10_FOOTPRINT_DIR": "/usr/share/kicad/footprints"}
    libs = parse_fp_table(os.path.join(PRJ, "fp-lib-table"), subs)
    home = os.path.expanduser("~/.config/kicad/10.0/fp-lib-table")
    parse_fp_table(home, subs, libs)
    return libs


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
class Geom:
    """courtyard / pad bounding boxes of a placed footprint, in board coords
    relative to the footprint origin.

    A footprint that has been flipped to the back carries its courtyard on
    B.CrtYd, so the layer is taken from the footprint rather than assumed:
    everything downstream (the packer, the overlap checks, the anchors) then
    works on a back-side part exactly as it does on a front-side one."""

    def __init__(self, fp):
        org = fp.GetPosition()
        layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
        cy = fp.GetCourtyard(layer).BBox()
        self.cy = self._rel(cy.GetLeft(), cy.GetTop(), cy.GetRight(),
                            cy.GetBottom(), org)
        xs, ys = [], []
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            xs += [bb.GetLeft(), bb.GetRight()]
            ys += [bb.GetTop(), bb.GetBottom()]
        if xs:
            self.pad = self._rel(min(xs), min(ys), max(xs), max(ys), org)
        else:
            self.pad = self.cy

    def area(self):
        return (self.cy[2] - self.cy[0]) * (self.cy[3] - self.cy[1])

    @staticmethod
    def _rel(l, t, r, b, org):
        # KiCad y-down -> board y-up, relative to the origin
        return (tomm(l - org.x), tomm(org.y - b), tomm(r - org.x),
                tomm(org.y - t))


def bbox_overlap(a, b, gap=0.0):
    return (a[0] < b[2] - gap and b[0] < a[2] - gap and
            a[1] < b[3] - gap and b[1] < a[3] - gap)


def bbox_gap(a, b):
    """shortest distance between two courtyard rectangles (0 if they touch)"""
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def rect_circle_overlap(r, cx, cy, rad):
    dx = max(r[0] - cx, 0, cx - r[2])
    dy = max(r[1] - cy, 0, cy - r[3])
    return dx * dx + dy * dy < rad * rad


# --------------------------------------------------------------------------
# the builder
# --------------------------------------------------------------------------
class Builder:
    def __init__(self, width, height):
        self.HX = width / 2.0
        self.HY = height / 2.0
        self.mx_l = -self.HX + MOUNT_MARGIN_L
        self.mx_r = self.mx_l + MOUNT_PITCH
        self.board = pcbnew.CreateEmptyBoard()
        self.fps = {}
        self.geom = {}
        self.placed = []        # (ref, courtyard rect in board coords)
        self.back = set()       # refs flipped to the back (bare pads only)
        self.texts = []         # board level silkscreen text, movable
        self.pinned = []        # board level silkscreen text, fixed position
        self.pinned_refs = set()  # refdes fixed by pin_ref(); never nudged
        self.back_texts = []    # B.SilkS text; never nudged, nothing to hit
        self.problems = []
        self.notes = []
        self.padoff = {}        # (ref, pad, rot) -> pad centre off the origin
        self.pinfunc = {}       # (ref, pin) -> the schematic's pin name
        self.sat = {}           # the verified SATELLITES table for this run
        self.satpad = {}        # satellite ref -> its pad on the owner's net

    def is_back(self, ref):
        return ref in self.back

    # ---------------- board setup ----------------
    def setup_layers(self):
        b = self.board
        b.SetCopperLayerCount(4)
        b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
        b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
        b.SetLayerName(pcbnew.In1_Cu, "GND")
        b.SetLayerName(pcbnew.In2_Cu, "PWR")
        ds = b.GetDesignSettings()
        ds.SetBoardThickness(mm(BOARD_THICKNESS))
        ds.m_TrackMinWidth = mm(RULES["min_track"])
        ds.m_MinClearance = mm(RULES["min_clearance"])
        ds.m_MinThroughDrill = mm(RULES["min_through_hole"])
        ds.m_ViasMinSize = mm(RULES["min_via_dia"])
        ds.m_MinViaAnnularWidth = mm(RULES["min_annular"])
        ds.m_HoleToHoleMin = mm(RULES["min_hole_to_hole"])
        ds.m_CopperEdgeClearance = mm(RULES["copper_edge"])
        ds.m_SolderMaskMinWidth = mm(RULES["mask_min_web"])
        ds.m_SolderMaskExpansion = mm(RULES["mask_expansion"])
        ds.m_MinSilkTextHeight = mm(RULES["min_text_height"])
        ds.m_MinSilkTextThickness = mm(RULES["min_text_thickness"])
        ds.m_MinResolvedSpokes = RULES["min_resolved_spokes"]
        ds.m_HasStackup = True
        try:
            ds.SetAuxOrigin(to_kicad(0, 0))
            ds.SetGridOrigin(to_kicad(0, 0))
        except Exception:
            pass

    def setup_netclasses(self):
        ns = self.board.GetDesignSettings().m_NetSettings
        classes = ns.GetNetclasses()
        for (name, tw, clr, vd, vdr, dpw, dpg, prio, pats) in NETCLASSES:
            if name == "Default":
                nc = ns.GetDefaultNetclass()
            else:
                nc = pcbnew.NETCLASS(name)
            nc.SetTrackWidth(mm(tw))
            nc.SetClearance(mm(clr))
            nc.SetViaDiameter(mm(vd))
            nc.SetViaDrill(mm(vdr))
            nc.SetDiffPairWidth(mm(dpw))
            nc.SetDiffPairGap(mm(dpg))
            if prio is not None:
                nc.SetPriority(prio)
            if name != "Default":
                classes[name] = nc
        ns.SetNetclasses(classes)

    # ---------------- footprints ----------------
    def load_components(self, comps, nets):
        self.nets = [(n, [(r, p) for r, p in nodes]) for n, nodes in nets]
        libs = footprint_libs()
        vendored = {r: vendor_io_footprint() for r in IO_REFS}
        for ref in sorted(comps):
            c = comps[ref]
            fpid = c["fp"]
            if ref in vendored and fpid != vendored[ref]:
                raise SystemExit("%s: schematic says %s, the board needs the "
                                 "courtyard-trimmed %s"
                                 % (ref, fpid, vendored[ref]))
            lib, name = fpid.split(":")
            if lib not in libs:
                raise SystemExit("no such footprint library: %s" % lib)
            fp = pcbnew.FootprintLoad(libs[lib], name)
            if fp is None:
                raise SystemExit("footprint not found: %s" % fpid)
            fp.SetReference(ref)
            fp.SetValue(c["value"])
            fp.SetPath(pcbnew.KIID_PATH(c["path"]))
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            self.board.Add(fp)
            fp.SetPosition(to_kicad(0, -self.HY - 40))      # parked
            ref_fld = fp.Reference()
            ref_fld.SetLayer(pcbnew.F_SilkS)
            ref_fld.SetVisible(ref in REF_ON_SILK)
            ref_fld.SetTextSize(pcbnew.VECTOR2I(mm(SILK_TEXT), mm(SILK_TEXT)))
            ref_fld.SetTextThickness(mm(SILK_THICK))
            fp.Value().SetVisible(False)
            if c.get("dnp"):
                fp.SetDNP(True)
                fp.SetExcludedFromPosFiles(True)
            if c.get("no_bom"):
                fp.SetExcludedFromBOM(True)
            # THE BACK SIDE: flip here, before any geometry is measured, so
            # Geom reads B.CrtYd and every anchor, the packer and the checks
            # see the real back-side outline.  Flipping about the footprint's
            # own origin mirrors X *inside* the footprint and leaves the
            # placement to the tables below.
            if (ref in BACK_PAD_ROWS or ref in BACK_DNP_PARTS
                    or TEST_POINTS.match(ref)):
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                ref_fld.SetVisible(BACK_REF_SILK)
                self.back.add(ref)
            self.fps[ref] = fp
        # nets
        code = 1
        for name, nodes in nets:
            ni = pcbnew.NETINFO_ITEM(self.board, name, code)
            self.board.Add(ni)
            code += 1
            for ref, pin in nodes:
                fp = self.fps.get(ref)
                if fp is None:
                    continue
                hit = False
                for pad in fp.Pads():
                    if pad.GetNumber() == pin:
                        pad.SetNet(ni)
                        hit = True
                if not hit:
                    self.problems.append("no pad %s on %s (net %s)" %
                                         (pin, ref, name))

    # ---------------- placement primitives ----------------
    def g(self, ref, rot):
        key = (ref, rot)
        if key not in self.geom:
            fp = self.fps[ref]
            fp.SetOrientationDegrees(rot)
            self.geom[key] = Geom(fp)
        return self.geom[key]

    def place(self, ref, x, y, rot=0, note=None):
        """place the footprint *origin* at board (x, y)"""
        g = self.g(ref, rot)
        fp = self.fps[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(to_kicad(x, y))
        rect = (x + g.cy[0], y + g.cy[1], x + g.cy[2], y + g.cy[3])
        self.placed.append((ref, rect))
        if note:
            self.notes.append("%-4s %s" % (ref, note))
        return rect

    def anchor(self, ref, rot, ax, ay):
        """place with per-axis anchors.

        ax/ay are (mode, value) with mode one of
          org      footprint origin at value
          cyc/padc centre of the courtyard / pad bbox at value
          cymin/cymax/padmin/padmax   that edge of the bbox at value
        """
        g = self.g(ref, rot)

        def solve(mode, val, lo, hi):
            if mode == "org":
                return val
            if mode == "cyc" or mode == "padc":
                return val - (lo + hi) / 2.0
            if mode in ("cymin", "padmin"):
                return val - lo
            if mode in ("cymax", "padmax"):
                return val - hi
            raise ValueError(mode)

        bx = g.cy if ax[0].startswith("cy") or ax[0] == "org" else g.pad
        by = g.cy if ay[0].startswith("cy") or ay[0] == "org" else g.pad
        x = solve(ax[0], ax[1], bx[0], bx[2])
        y = solve(ay[0], ay[1], by[1], by[3])
        return self.place(ref, x, y, rot)

    # ---------------- occupancy grid packer ----------------
    CELL = 0.125

    def build_grid(self, reserved):
        """occupancy grid of everything placed so far + reserved bands.

        THE GRID IS THE FRONT SIDE.  Nothing is ever packed onto the back -
        back_side() solves every back position by hand and runs before this -
        so one grid is enough, and it must hold the FRONT courtyards only.
        A back-side courtyard is not an obstacle to a front-side part: two
        courtyards on opposite sides cannot collide, which is exactly what
        check() asserts.  Blocking the back here instead black-holed the
        three places the front needs most - the island corridor under
        TP1-TP10, the pocket under the MCU under the U24 land and the left
        edge under the ESC row - and every satellite of every owner in or
        beside them fell out to the whole-board search.
        """
        self.gnx = int(round(2 * self.HX / self.CELL))
        self.gny = int(round(2 * self.HY / self.CELL))
        self.occ = np.zeros((self.gnx, self.gny), dtype=bool)
        for ref, rect in self.placed:
            if ref.startswith("H") and ref[1:].isdigit():
                continue                       # circles, handled below
            if self.is_back(ref):
                continue                       # other side of the board
            self.block_rect(rect, 0.05)
        for ref in ("H1", "H2", "H3", "H4"):
            if ref in self.fps:
                x, y = self.pos(ref)
                self.block_circle(x, y, MOUNT_KEEPOUT_R + 0.3)
        for r in reserved:
            self.block_rect(r, 0.0)

    def _ix(self, v):
        return int(math.floor((v + self.HX) / self.CELL))

    def _iy(self, v):
        return int(math.floor((v + self.HY) / self.CELL))

    def block_rect(self, rect, grow):
        i0 = max(self._ix(rect[0] - grow), 0)
        i1 = min(self._ix(rect[2] + grow) + 1, self.gnx)
        j0 = max(self._iy(rect[1] - grow), 0)
        j1 = min(self._iy(rect[3] + grow) + 1, self.gny)
        self.occ[i0:i1, j0:j1] = True

    def block_circle(self, cx, cy, r):
        ax = (np.arange(self.gnx) + 0.5) * self.CELL - self.HX
        ay = (np.arange(self.gny) + 0.5) * self.CELL - self.HY
        xx, yy = np.meshgrid(ax, ay, indexing="ij")
        self.occ |= ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r

    def free(self, rect):
        i0 = self._ix(rect[0])
        i1 = self._ix(rect[2]) + 1
        j0 = self._iy(rect[1])
        j1 = self._iy(rect[3]) + 1
        if i0 < 0 or j0 < 0 or i1 > self.gnx or j1 > self.gny:
            return False
        return not self.occ[i0:i1, j0:j1].any()

    def pos(self, ref):
        p = self.fps[ref].GetPosition()
        return tomm(p.x) - CX, CY - tomm(p.y)

    def best_spot(self, ref, seed, rots=(0, 90), step=0.25, gap=0.05,
                  bounds=None, maxrad=None):
        """the nearest free spot to seed, WITHOUT taking it: returns
        (distance from the seed, courtyard centre x, y, rotation, w, h) or
        None.  `maxrad` caps the spiral, so a caller that only wants a slot
        *at* something (place_satellites) gets None rather than a spot on the
        far side of the board."""
        best = None
        for rot in rots:
            g = self.g(ref, rot)
            cw = g.cy[2] - g.cy[0]
            ch = g.cy[3] - g.cy[1]
            pw = g.pad[2] - g.pad[0]
            ph = g.pad[3] - g.pad[1]
            lim_x = self.HX - EDGE_COPPER - pw / 2.0 - 0.05
            lim_y = self.HY - EDGE_COPPER - ph / 2.0 - 0.05
            reach = (2.2 * max(self.HX, self.HY) if maxrad is None
                     else maxrad + step / 2.0)
            # candidate courtyard centres, spiral out from the seed
            for rad in np.arange(0.0, reach, step):
                cands = self._ring(seed, rad, step)
                hit = None
                for (cx, cy) in cands:
                    if abs(cx) > lim_x or abs(cy) > lim_y:
                        continue
                    rect = (cx - cw / 2.0 - gap, cy - ch / 2.0 - gap,
                            cx + cw / 2.0 + gap, cy + ch / 2.0 + gap)
                    if bounds is not None and not any(
                            b[0] <= rect[0] and rect[2] <= b[2] and
                            b[1] <= rect[1] and rect[3] <= b[3]
                            for b in bounds):
                        continue
                    if self.free(rect):
                        d = math.hypot(cx - seed[0], cy - seed[1])
                        if hit is None or d < hit[0]:
                            hit = (d, cx, cy, rot, cw, ch)
                if hit:
                    if best is None or hit[0] < best[0]:
                        best = hit
                    break
        return best

    def spot_origin(self, ref, spot):
        """the footprint origin that puts `spot`'s courtyard where it is"""
        g = self.g(ref, spot[3])
        return (spot[1] - (g.cy[0] + g.cy[2]) / 2.0,
                spot[2] - (g.cy[1] + g.cy[3]) / 2.0)

    def commit_spot(self, ref, spot, grow=0.1):
        """take the spot best_spot() found and block the grid under it"""
        x, y = self.spot_origin(ref, spot)
        rect = self.place(ref, x, y, spot[3])
        self.block_rect(rect, grow)
        return spot[0]

    def place_near(self, ref, seed, rots=(0, 90), step=0.25, gap=0.05,
                   bounds=None):
        """nearest free spot to seed (optionally inside `bounds`, a list of
        rectangles); returns the distance from the seed, or None"""
        spot = self.best_spot(ref, seed, rots, step, gap, bounds)
        return None if spot is None else self.commit_spot(ref, spot)

    @staticmethod
    def _ring(seed, rad, step):
        """candidate points on the square ring of radius `rad` around seed"""
        sx = round(seed[0] / step) * step
        sy = round(seed[1] / step) * step
        k = int(round(rad / step))
        if k == 0:
            return [(sx, sy)]
        pts = []
        for i in range(-k, k + 1):
            pts.append((sx + i * step, sy - k * step))
            pts.append((sx + i * step, sy + k * step))
        for j in range(-k + 1, k):
            pts.append((sx - k * step, sy + j * step))
            pts.append((sx + k * step, sy + j * step))
        return pts

    def pad_pos(self, ref, num):
        for pad in self.fps[ref].Pads():
            if pad.GetNumber() == num:
                p = pad.GetPosition()
                return tomm(p.x) - CX, CY - tomm(p.y)
        raise KeyError((ref, num))

    def pad_offset(self, ref, num, rot):
        """a pad's centre relative to the footprint ORIGIN at rotation `rot`,
        in board coords.  Lets a candidate position be scored (where would
        that pad land?) without placing the part."""
        key = (ref, num, rot)
        if key not in self.padoff:
            fp = self.fps[ref]
            fp.SetOrientationDegrees(rot)
            org = fp.GetPosition()
            for pad in fp.Pads():
                if pad.GetNumber() == num:
                    p = pad.GetPosition()
                    self.padoff[key] = (tomm(p.x - org.x), tomm(org.y - p.y))
                    break
            else:
                raise KeyError((ref, num))
        return self.padoff[key]

    def net_of(self, ref, num):
        for pad in self.fps[ref].Pads():
            if pad.GetNumber() == num:
                n = pad.GetNetname()
                return n or None
        raise KeyError((ref, num))

    # ---------------- satellites (the passive that sits ON a pin) ------
    def verify_satellites(self, comps):
        """Build the satellite table for THIS netlist and prove every row.

        A row is only meaningful if the owner's pad and the satellite really
        are on the same net, so that is asserted here rather than trusted:
        a schematic change that moves a cap to another pin fails the build
        instead of quietly placing it at the wrong pin.  The pad of the
        satellite that carries the owner's net is resolved at the same time -
        it is the one that has to face the pin, and the one the distance is
        measured from."""
        self.sat = dict(SATELLITES)
        self.sat.update(sensor_satellites(comps, self.pinfunc))
        self.satpad = {}
        bad = []
        for ref, (owner, pad, klass, rank, order) in sorted(self.sat.items()):
            if ref not in self.fps:
                bad.append("%s: no such part" % ref)
                continue
            if owner not in self.fps:
                bad.append("%s: owner %s is not on the board" % (ref, owner))
                continue
            if isinstance(pad, tuple):
                # ("net", NAME): the owner's pad carrying NAME, resolved from
                # the netlist instead of being written down a second time.
                # It has to be exactly one pad - a satellite of "the owner's
                # ground" is not a satellite of anything.
                hits = sorted(p.GetNumber() for p in self.fps[owner].Pads()
                              if p.GetNetname() == pad[1])
                if len(hits) != 1:
                    bad.append("%s: %s has %d pads on %s (%s)"
                               % (ref, owner, len(hits), pad[1],
                                  ",".join(hits) or "none"))
                    continue
                pad = hits[0]
                self.sat[ref] = (owner, pad, klass, rank, order)
            try:
                net = self.net_of(owner, pad)
            except KeyError:
                bad.append("%s: %s has no pad %s" % (ref, owner, pad))
                continue
            if not net:
                bad.append("%s: %s pad %s has no net" % (ref, owner, pad))
                continue
            mine = [p.GetNumber() for p in self.fps[ref].Pads()
                    if p.GetNetname() == net]
            if not mine:
                bad.append("%s is not on %s (%s pad %s); it is on %s"
                           % (ref, net, owner, pad,
                              ",".join(sorted({p.GetNetname() or "-"
                                               for p in self.fps[ref].Pads()}))
                              ))
                continue
            if self.is_back(ref) != self.is_back(owner):
                bad.append("%s and its owner %s are on opposite sides"
                           % (ref, owner))
                continue
            self.satpad[ref] = mine[0]
        if bad:
            raise SystemExit("SATELLITES does not match the netlist:\n  "
                             + "\n  ".join(bad))
        return self.sat

    def sat_seed(self, ref, owner, pad, rot):
        """where a satellite of `owner`'s `pad` wants to be at rotation
        `rot`: straight out of the courtyard edge that pad is nearest to,
        SAT_CLEAR clear of it, the part's own body centred on that.

        Outward, not "towards the pad": a 0402 whose centre is put on the pad
        overlaps the package, and the packer would then spiral it to whatever
        side happens to be free.  Seeded outside the edge the pad belongs to,
        the first free cell it finds is the one against that pin."""
        px, py = self.pad_pos(owner, pad)
        cy = dict(self.placed)[owner]
        out = ((-1, 0, px - cy[0]), (1, 0, cy[2] - px),
               (0, -1, py - cy[1]), (0, 1, cy[3] - py))
        nx, ny, edge = min(out, key=lambda o: o[2])
        g = self.g(ref, rot)
        depth = (g.cy[2] - g.cy[0]) if nx else (g.cy[3] - g.cy[1])
        step = max(edge, 0.0) + SAT_CLEAR + depth / 2.0
        return (px + nx * step, py + ny * step), (nx, ny)

    def sat_spot(self, ref, owner, pad, maxrad, step=0.25, gap=0.05):
        """The free slot for `ref` that puts its OWNER-NET pad nearest the
        owner's pad; returns (key, spot, distance) or None.

        Scored on the pad-to-pin distance itself, not on the distance to the
        seed.  The seed is only a direction - straight out of the courtyard
        edge the pin is on - and the free cell nearest to it is not the cell
        whose pad ends up nearest the pin: a 0402 one ring further out but
        turned the other way round can be half a millimetre closer, and half
        a millimetre is the whole margin of a rank 0 row.

        Every rotation is tried.  Ties go to the rotation that leaves the
        part radial (long axis pointing away from the package), which is what
        leaves room for the next satellite along the same edge.

        The spiral stops as soon as no further ring can win: a candidate
        `rad` from the seed is at least `rad - d0` from the pin, where d0 is
        what the part would measure sitting exactly on the seed, so once
        rad > best + d0 the rest of the board cannot beat what we have.
        """
        px, py = self.pad_pos(owner, pad)
        best = None
        for rot in (0, 90, 180, 270):
            seed, n = self.sat_seed(ref, owner, pad, rot)
            g = self.g(ref, rot)
            cw, ch = g.cy[2] - g.cy[0], g.cy[3] - g.cy[1]
            pw, ph = g.pad[2] - g.pad[0], g.pad[3] - g.pad[1]
            lim_x = self.HX - EDGE_COPPER - pw / 2.0 - 0.05
            lim_y = self.HY - EDGE_COPPER - ph / 2.0 - 0.05
            # courtyard centre -> the satellite's own owner-net pad
            ox, oy = self.pad_offset(ref, self.satpad[ref], rot)
            ox -= (g.cy[0] + g.cy[2]) / 2.0
            oy -= (g.cy[1] + g.cy[3]) / 2.0
            d0 = math.hypot(seed[0] + ox - px, seed[1] + oy - py)
            long_x = cw >= ch
            radial = long_x == bool(n[0])
            reach = (2.2 * max(self.HX, self.HY) if maxrad is None
                     else maxrad + step / 2.0)
            hit = None
            for rad in np.arange(0.0, reach, step):
                if hit is not None and rad > hit[1] + d0 + step:
                    break
                for (cx, cy) in self._ring(seed, rad, step):
                    if abs(cx) > lim_x or abs(cy) > lim_y:
                        continue
                    rect = (cx - cw / 2.0 - gap, cy - ch / 2.0 - gap,
                            cx + cw / 2.0 + gap, cy + ch / 2.0 + gap)
                    if not self.free(rect):
                        continue
                    d = math.hypot(cx + ox - px, cy + oy - py)
                    if hit is None or d < hit[1]:
                        hit = ((round(d / 0.05), 0 if radial else 1, rot),
                               d, (d, cx, cy, rot, cw, ch))
            if hit is not None and (best is None or hit[0] < best[0]):
                best = (hit[0], hit[2], hit[1])
        return best

    def place_satellites(self, owners):
        """Put every satellite of every listed owner against the pin it
        serves.

        Order is the whole algorithm here, and the first cut of it got it
        wrong three different ways.

        RANK BEFORE OWNER.  Served owner by owner, the first owner's rank 2
        pull-ups are placed before the next owner's rank 0 decoupling, and
        whichever of them cannot find a cell inside its own radius escalates
        straight to the 6 mm and then to the whole-board search - squatting
        on cells the *next* owner's rank 0 parts are the only legitimate
        claimants of.  With U20's 39 parts served first that cost U25 its
        entire pocket: all twelve of its satellites ended up on a board-wide
        search, 10 to 22 mm from their pins.

        THE LIMIT BEFORE THE RANK.  A rank 0 cap on the QFN's left edge has
        a 1.07 mm corridor to sit in and cannot make its 2 mm whatever it is
        given; a rank 2 pull-up on the same edge only has to be inside 6 mm
        and can.  Letting the cap take the cell first misses both rows, so
        the first two passes only TAKE a spot that actually meets the rank's
        limit - a part that cannot meet it anywhere stands aside and is
        placed in the cleanup passes, where it can no longer cost a row that
        was winnable.  Inside a pass it is still rank order: what stands
        aside is a part that cannot be satisfied, never one that can.

        NEAREST FIRST.  Within one pass the part placed next is the one whose
        best remaining slot is CLOSEST to its pin, re-scored against the grid
        after every placement: a part that can hug its own pin uses the least
        room doing it, and the room it does not use is what the part behind
        it needs.

        AN OWNER GOES BEFORE ANY RANK.  FB1 is a satellite of U7 and the
        owner of five more; placed after U7's three 22 uF output caps it took
        the one hole they had left it and there was no room beside it for its
        own, which is how C23/C24 - which CAP_NEAR requires within 6 mm of
        U7 - ended up on a board-wide search.  A part that is itself an owner
        is placed first, whatever its rank.

        OWNER PRIORITY WITHIN A RANK.  Rank alone still groups a pass (every
        rank 0 part across every owner before any rank 1 part anywhere), but
        SAT_OWNER_PRIORITY now also splits each rank into one class per
        owner, served in that fixed order: nearest-first re-scoring, and the
        escalation through SAT_PASSES, happen inside one (rank, owner) class
        at a time, so one owner's near misses cannot spend the cells the
        next owner's own rank-mates are the only legitimate claimants of.

        Ordinary packing constraints all still apply: the spot comes out of
        the same occupancy grid, so board edge, mounting-hole keepouts,
        reserved silk bands and every courtyard already down are respected.
        """
        # class key: owners are forced into one shared (0, 0) class ahead of
        # every rank; everything else classes by (rank, SAT_OWNER_PRIORITY
        # index).  Then: rank (for SAT_NEAR_MM), owner priority again (a
        # static tie-break, redundant with the class key but harmless),
        # order in the owner, ref.
        opri = {o: i for i, o in enumerate(SAT_OWNER_PRIORITY)}

        def _opri(o):
            return opri.get(o, len(SAT_OWNER_PRIORITY))
        pool = sorted((0 if r in owners else v[3] + 1, v[3],
                       _opri(v[0]), v[4], r)
                      for r, v in self.sat.items()
                      if v[0] in owners and v[0] in self.fps)
        pris = sorted({it[0] for it in pool})
        wide = {}
        for pri in pris:
            for phase, (rad, slack) in enumerate(SAT_PASSES):
                while True:
                    # FB1 is a satellite of U7 AND an owner itself: its own
                    # caps cannot be seeded until it is down, so a part whose
                    # owner is still parked waits for the next round.
                    down = {r for r, _ in self.placed}
                    pick = None
                    for item in pool:
                        if item[0] != pri:
                            continue
                        ref = item[4]
                        owner, pad = self.sat[ref][0], self.sat[ref][1]
                        if owner not in down:
                            continue
                        lim = (None if slack is None
                               else slack * SAT_NEAR_MM[item[1]])
                        spot = self.sat_spot(ref, owner, pad, rad)
                        if spot is None or (lim is not None and
                                            spot[2] > lim + 1e-6):
                            continue
                        if pick is None or spot[2] < pick[0]:
                            pick = (spot[2], item, spot[1])
                    if pick is None:
                        break
                    ref = pick[1][4]
                    if phase:
                        wide.setdefault(self.sat[ref][0], []).append(
                            "%s@%s" % (ref, rad or "board"))
                    self.commit_spot(ref, pick[2], SAT_GROW)
                    pool.remove(pick[1])
                if not any(it[0] == pri for it in pool):
                    break
        for _, _, _, _, ref in pool:
            owner = self.sat[ref][0]
            self.problems.append("%s: no room for %s at %s pad %s"
                                 % (owner, ref, owner, self.sat[ref][1]))
            self.place(ref, -self.HX + 4,
                       -self.HY - 25 - 4 * len(self.problems), 0)
        for owner in owners:
            n = sum(1 for v in self.sat.values() if v[0] == owner)
            if not n:
                continue
            print("  sat   %-4s %2d parts%s"
                  % (owner, n, "  WIDE SEARCH: " + ",".join(wide[owner])
                     if owner in wide else ""))

    def sat_blocker(self, ref, owner, pad, lim):
        """WHY `ref` could not get within `lim` of its pin: what is sitting
        on the nearest position that would have met the limit.

        Lead's decision C - a rank 0 row that misses its 2 mm has to name the
        courtyard that took the cell, so "still over" can be read as a fact
        about the floorplan rather than as a shrug.  The search is the same
        one sat_spot() makes, with the occupancy grid ignored: the best
        position the geometry allows at all, then whatever is on it."""
        px, py = self.pad_pos(owner, pad)
        own = dict(self.placed)[owner]
        best = None
        for rot in (0, 90, 180, 270):
            seed, _ = self.sat_seed(ref, owner, pad, rot)
            g = self.g(ref, rot)
            cw, ch = g.cy[2] - g.cy[0], g.cy[3] - g.cy[1]
            pw, ph = g.pad[2] - g.pad[0], g.pad[3] - g.pad[1]
            lim_x = self.HX - EDGE_COPPER - pw / 2.0 - 0.05
            lim_y = self.HY - EDGE_COPPER - ph / 2.0 - 0.05
            ox, oy = self.pad_offset(ref, self.satpad[ref], rot)
            ox -= (g.cy[0] + g.cy[2]) / 2.0
            oy -= (g.cy[1] + g.cy[3]) / 2.0
            # the SAME 0.25 mm lattice sat_spot() searches, so the spot named
            # here is one the packer could really have taken
            for rad in np.arange(0.0, 2.0 * (lim + cw + ch), 0.25):
                for (cx, cy) in self._ring(seed, rad, 0.25):
                    d = math.hypot(cx + ox - px, cy + oy - py)
                    if best is not None and d >= best[0]:
                        continue
                    if abs(cx) > lim_x or abs(cy) > lim_y:
                        continue
                    r = (cx - cw / 2.0 - 0.05, cy - ch / 2.0 - 0.05,
                         cx + cw / 2.0 + 0.05, cy + ch / 2.0 + 0.05)
                    # reject exactly what the grid would: the owner's own
                    # courtyard, blocked 0.05 mm proud and snapped out to
                    # whole CELLs, is never a position for its satellite.
                    # Anything that survives this is a cell the part could
                    # have had on a board holding nothing but the package.
                    if (self._ix(r[0]) < self._ix(own[2] + 0.05) + 1
                            and self._ix(own[0] - 0.05) < self._ix(r[2]) + 1
                            and self._iy(r[1]) < self._iy(own[3] + 0.05) + 1
                            and self._iy(own[1] - 0.05) < self._iy(r[3]) + 1):
                        continue
                    best = (d, r)
        if best is None:
            return "no position clear of %s exists at that pin" % owner
        if best[0] > lim + 1e-6:
            return ("%s's own courtyard puts the nearest legal cell at "
                    "%.2f mm - the part cannot make the limit at that pin "
                    "on an empty board" % (owner, best[0]))
        on, near = [], []
        for r, rect in self.placed:
            if r == ref or r == owner or self.is_back(r):
                continue
            if bbox_overlap(best[1], rect, 0.001):
                on.append(r)
            elif bbox_gap(best[1], rect) <= self.CELL + 0.05 + 1e-9:
                # the occupancy grid is quantised to CELL and every courtyard
                # is blocked 0.05 mm proud of itself, so a neighbour this
                # close owns the cell even though the two boxes do not touch
                near.append(r)
        if on:
            return "%s is on the %.2f mm spot" % (", ".join(sorted(set(on))),
                                                  best[0])
        if near:
            return ("%s holds the cell of the %.2f mm spot (courtyard plus "
                    "the 0.125 mm grid)"
                    % (", ".join(sorted(set(near))), best[0]))
        if self.free(best[1]):
            return ("the %.2f mm spot is still FREE - the packer's search "
                    "missed it" % best[0])
        return ("the %.2f mm spot is clear of every courtyard - the board "
                "edge, a grommet keepout or a reserved silk band holds it"
                % best[0])

    def check_satellites(self):
        """every satellite's pad-to-pin distance, and the rows that miss the
        rank's limit - those fail the run like any other placement rule"""
        out = []
        rows = []
        for ref, (owner, pad, klass, rank, _) in self.sat.items():
            d = math.hypot(*[a - b for a, b in
                             zip(self.pad_pos(ref, self.satpad[ref]),
                                 self.pad_pos(owner, pad))])
            rows.append((owner, rank, d, ref, pad, klass,
                         SAT_NEAR_MM[rank]))
        for ref, (owner, pad) in SAT_REPORT.items():
            if ref not in self.fps or owner not in self.fps:
                continue
            mine = [p.GetNumber() for p in self.fps[ref].Pads()
                    if p.GetNetname() and
                    p.GetNetname() == self.net_of(owner, pad)]
            if not mine:
                continue
            d = math.hypot(*[a - b for a, b in
                             zip(self.pad_pos(ref, mine[0]),
                                 self.pad_pos(owner, pad))])
            rows.append((owner, 9, d, ref, pad, "anchored", None))
        print("  satellites (pad to pin, mm):")
        for owner, rank, d, ref, pad, klass, lim in sorted(rows):
            over = lim is not None and d > lim + 1e-6
            print("    %-4s %-4s pin %-3s %-14s rank %s  %5.2f%s"
                  % (ref, owner, pad, klass,
                     "-" if lim is None else rank, d,
                     "   OVER %.1f" % lim if over else ""))
            if over:
                why = ""
                if rank == 0:
                    # decision C: a rank 0 row that is still out has to say
                    # what took the cell, never just be accepted
                    why = "; " + self.sat_blocker(ref, owner, pad, lim)
                    print("      ^ %s" % why[2:])
                out.append("%s is %.2f mm from %s pin %s (rank %d limit "
                           "%.1f mm)%s"
                           % (ref, d, owner, pad, rank, lim, why))
        return out

    def loop_seed(self, pairs, out=1.4):
        """seed for a loop component: the mean of the (part, pad) positions it
        connects to, pushed `out` mm clear of those parts.  A capacitor across
        two pads of one part therefore lands next to the package edge between
        them, and an output cap given the inductor's output pad and the IC's
        ground pad lands between the two - which is the loop it closes."""
        px = sum(self.pad_pos(r, p)[0] for r, p in pairs) / len(pairs)
        py = sum(self.pad_pos(r, p)[1] for r, p in pairs) / len(pairs)
        cx = sum(self.pos(r)[0] for r, _ in pairs) / len(pairs)
        cy = sum(self.pos(r)[1] for r, _ in pairs) / len(pairs)
        dx, dy = px - cx, py - cy
        if abs(dx) >= abs(dy):
            return (px + math.copysign(out, dx or 1.0), py)
        return (px, py + math.copysign(out, dy or 1.0))

    def halo(self, refs, reach):
        """bounding box of the given placed parts, grown by `reach`"""
        rect = dict(self.placed)
        xs = [v for r in refs for v in (rect[r][0], rect[r][2])]
        ys = [v for r in refs for v in (rect[r][1], rect[r][3])]
        return [(min(xs) - reach, min(ys) - reach,
                 max(xs) + reach, max(ys) + reach)]

    def power_loop(self, name, items, bounds):
        """place the loop components of a switcher.  Each part is seeded on
        the pad of the IC (or the inductor) it belongs to and may only land
        inside `bounds`, the halo around the IC + inductor, so the input and
        output loops stay short - see CAP_NEAR, which checks the result."""
        far = []
        for ref, pairs in items:
            if ref not in self.fps:
                continue
            seed = self.loop_seed(pairs)
            d = self.place_near(ref, seed, (0, 90), bounds=bounds)
            if d is None:
                far.append(ref)
                d = self.place_near(ref, seed, (0, 90))
            if d is None:
                self.problems.append("%s: no room for %s" % (name, ref))
                self.place(ref, -self.HX + 4,
                           -self.HY - 25 - 4 * len(self.problems), 0)
        print("  loop  %-9s %2d parts%s"
              % (name, len(items),
                 "  OUTSIDE THE HALO: " + ",".join(far) if far else ""))

    def cluster(self, name, refs, seed, bounds=None, rots=(0, 90)):
        items = []
        for r in refs:
            if r not in self.fps:
                continue
            kind = 0 if r[0] in "UQD" else (1 if r[0] in "LY" or
                                            r.startswith("FB") else 2)
            items.append((r, self.g(r, 0).area(), kind))
        items.sort(key=lambda it: (it[2], -it[1]))
        far = 0.0
        strays = []
        anchor = None
        for r, _, _ in items:
            d = self.place_near(r, anchor or seed, rots, bounds=bounds)
            if anchor is None and d is not None:
                anchor = self.pos(r)            # keep the group together
            if d is None and bounds is not None:
                grown = [(b[0] - 2.5, b[1] - 2.5, b[2] + 2.5, b[3] + 2.5)
                         for b in bounds]
                d = self.place_near(r, anchor or seed, rots, bounds=grown)
                if d is None:
                    d = self.place_near(r, anchor or seed, rots)
                if d is not None:
                    strays.append("%s@%.0f!" % (r, d))
            elif d is not None and d > 9.0:
                strays.append("%s@%.0f" % (r, d))
            if d is None:
                self.problems.append("%s: no room for %s" % (name, r))
                self.place(r, -self.HX + 4,
                           -self.HY - 25 - 4 * len(self.problems), 0)
            else:
                far = max(far, d)
        print("  cluster %-9s %2d parts, seed (%6.1f,%6.1f), max spread "
              "%.1f mm%s" % (name, len(items), seed[0], seed[1], far,
                             "  FAR: " + ",".join(strays) if strays else ""))

    def mcu_pin_seed(self, ref, comps, fallback, out=3.4):
        """seed a decoupling part just outside its RP2354B pin"""
        pin = None
        m = re.search(r"pins?\s+(\d+)", comps.get(ref, {}).get("value", ""))
        if m:
            pin = m.group(1)
        else:
            for net, nodes in self.nets:
                if net == "GND" or len(nodes) > 12:
                    continue
                if (ref, "1") in nodes or (ref, "2") in nodes:
                    u20 = [p for r, p in nodes if r == "U20"]
                    if len(u20) == 1:
                        pin = u20[0]
                        break
        if pin is None:
            return fallback
        for pad in self.fps["U20"].Pads():
            if pad.GetNumber() == pin:
                p = pad.GetPosition()
                x, y = tomm(p.x) - CX, CY - tomm(p.y)
                if abs(x) > abs(y):
                    return (x + math.copysign(out, x), y)
                return (x, y + math.copysign(out, y))
        return fallback

    def segment(self, a, b, layer=None, width=0.12):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(to_kicad(*a))
        s.SetEnd(to_kicad(*b))
        s.SetLayer(pcbnew.F_SilkS if layer is None else layer)
        s.SetWidth(mm(width))
        self.board.Add(s)
        return s

    def shrink_courtyard(self, ref, x0, y0, x1, y1):
        """replace the F.CrtYd outline of a footprint instance by a rectangle
        (footprint local coordinates)."""
        fp = self.fps[ref]
        for it in list(fp.GraphicalItems()):
            if it.GetLayer() == pcbnew.F_CrtYd:
                fp.Remove(it)
        if fp.GetOrientationDegrees():
            raise RuntimeError("shrink the courtyard before rotating %s" % ref)
        org = fp.GetPosition()          # child shapes carry absolute coords
        s = pcbnew.PCB_SHAPE(fp)
        s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetLayer(pcbnew.F_CrtYd)
        s.SetWidth(mm(0.05))
        s.SetStart(pcbnew.VECTOR2I(org.x + mm(x0), org.y + mm(y0)))
        s.SetEnd(pcbnew.VECTOR2I(org.x + mm(x1), org.y + mm(y1)))
        fp.Add(s)
        try:
            fp.BuildCourtyardCaches()
        except Exception:
            pass

    # ---------------- outline & silk ----------------
    def draw_outline(self):
        HX, HY, r = self.HX, self.HY, CORNER_R
        segs = [((-HX + r, -HY), (HX - r, -HY)), ((HX, -HY + r), (HX, HY - r)),
                ((HX - r, HY), (-HX + r, HY)), ((-HX, HY - r), (-HX, -HY + r))]
        for a, b in segs:
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(to_kicad(*a))
            s.SetEnd(to_kicad(*b))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(mm(0.1))
            self.board.Add(s)
        corners = [((HX - r, -HY), (HX, -HY + r), (HX - r, -HY + r)),
                   ((HX, HY - r), (HX - r, HY), (HX - r, HY - r)),
                   ((-HX + r, HY), (-HX, HY - r), (-HX + r, HY - r)),
                   ((-HX, -HY + r), (-HX + r, -HY), (-HX + r, -HY + r))]
        for start, end, cen in corners:
            mx = cen[0] + (r / math.sqrt(2)) * (1 if cen[0] > 0 else -1)
            my = cen[1] + (r / math.sqrt(2)) * (1 if cen[1] > 0 else -1)
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_ARC)
            s.SetArcGeometry(to_kicad(*start), to_kicad(mx, my),
                             to_kicad(*end))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(mm(0.1))
            self.board.Add(s)

    # ---------------- copper zones (planes, for the autorouter) ----------
    # lead's design: five filled zones, generated fresh every run so the
    # board this script writes is always ready for Freerouting.  Every zone
    # this script owns is named "gen:<net>:<layer short name>" so the
    # tracks/zones guard in main() can tell "ours, safe to discard and
    # rebuild" from "someone's hand-drawn zone, refuse".
    ZONE_ANA_ICS = ("U12", "U21", "U22", "U23")   # LDO + the three MEMS ICs

    def _board_rect_poly(self, inset=0.0):
        """[(x_nm, y_nm), ...] of the board's rectangular envelope, inset by
        `inset` mm on every side.  Deliberately the plain rectangle, not the
        rounded Edge.Cuts shape: ZONE_FILLER always clips a zone's fill to
        the real board outline, so the extra corner area a plain rectangle
        claims outside the rounded corners is never actually filled.

        Returns plain (x, y) int tuples in KiCad nm, not a SHAPE_POLY_SET:
        the zone's own outline (zone.Outline()) is filled in-place by the
        caller, so no Python-owned polygon object is ever handed to the
        zone - a Python-owned SHAPE_POLY_SET gets garbage collected while
        the multithreaded ZONE_FILLER still holds a pointer to it, which
        segfaults."""
        HX, HY = self.HX - inset, self.HY - inset
        pts = []
        for x, y in [(-HX, -HY), (HX, -HY), (HX, HY), (-HX, HY)]:
            v = to_kicad(x, y)
            pts.append((v.x, v.y))
        return pts

    def _keyhole_poly(self, outer_pts, hole_pts, gap=0.30):
        """`outer_pts` with `hole_pts` (inflated by `gap` mm) cut out of it,
        returned as one flat [(x_nm, y_nm), ...] ring.

        Freerouting's power-plane validator rejects a dedicated power layer
        whose conduction areas overlap ("Dedicated power layer 'PWR' has
        overlapping conduction areas"), and KiCad exports one `(plane NET
        (polygon ...))` per zone *outline* - priorities, which is how the
        two In2 pours are actually kept apart when filled, are a KiCad-only
        concept that does not survive into the DSN.  So the V3V3_SYS
        outline has to be physically keyholed around the V3V3_ANA island
        rather than relying on the higher-priority island to win.

        The boolean is done on a local SHAPE_POLY_SET and only its
        *vertices* are returned; the caller copies them into the zone's own
        outline, so no Python-owned polygon is ever handed to a zone (see
        _board_rect_poly for why that segfaults).  Fracture() turns the
        outline-with-hole into a single self-touching contour (the hole is
        reached through a zero-width bridge), which is exactly the shape
        KiCad stores for a keyholed zone and exports as one polygon.
        """
        outer = pcbnew.SHAPE_POLY_SET()
        outer.NewOutline()
        for x, y in outer_pts:
            outer.Append(int(x), int(y))
        hole = pcbnew.SHAPE_POLY_SET()
        hole.NewOutline()
        for x, y in hole_pts:
            hole.Append(int(x), int(y))
        hole.Inflate(mm(gap), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS,
                     mm(0.01))
        outer.BooleanSubtract(hole)
        outer.Fracture()
        if outer.OutlineCount() != 1:
            raise SystemExit("keyhole zone: Fracture() left %d outlines, "
                             "expected 1" % outer.OutlineCount())
        chain = outer.Outline(0)
        return [(chain.CPoint(i).x, chain.CPoint(i).y)
                for i in range(chain.PointCount())]

    def _add_plane(self, layer, net_name, name, priority,
                    clearance, min_thickness, pts):
        net = self.board.FindNet(net_name)
        if net is None:
            raise SystemExit("zone %s: no such net %r" % (name, net_name))
        z = pcbnew.ZONE(self.board)
        z.SetLayer(layer)
        z.SetNetCode(net.GetNetCode())
        z.SetZoneName(name)
        z.SetAssignedPriority(priority)
        z.SetLocalClearance(mm(clearance))
        z.SetMinThickness(mm(min_thickness))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.30))
        z.SetThermalReliefSpokeWidth(mm(0.40))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        # build the outline inside the zone's own SHAPE_POLY_SET - never
        # hand the zone a Python-created polygon (see _board_rect_poly).
        ol = z.Outline()
        ol.NewOutline()
        for x, y in pts:
            ol.Append(int(x), int(y))
        self.board.Add(z)
        return z

    ZONE_ANA_CAP_RADIUS_MM = 3.0   # a V3V3_ANA cap this close to one of the
                                   # four ICs' courtyards is "on the island"

    @staticmethod
    def _point_bbox_dist(px, py, box):
        """distance from board point (px, py), KiCad nm, to the nearest
        edge of `box` (0 if the point is inside it)."""
        dx = max(box.GetLeft() - px, 0, px - box.GetRight())
        dy = max(box.GetTop() - py, 0, py - box.GetBottom())
        return math.hypot(dx, dy)

    def _analog_zone_poly(self):
        """bounding box of the V3V3_ANA island: the four analog ICs'
        courtyards (U12/U21/U22/U23, ZONE_ANA_ICS) plus every V3V3_ANA
        capacitor whose *centre* sits within ZONE_ANA_CAP_RADIUS_MM of one
        of those four courtyards - padded 1.5 mm, clipped to the board
        outline minus 0.5 mm.  A V3V3_ANA cap elsewhere on the board (e.g.
        C40, the MCU's own decoupling cap) is excluded: it is on the net
        but nowhere near the analog island, and including it would drag
        the island bbox across the board.  Read off the placed footprints
        (self.fps / self.nets) every run, never hard-coded."""
        ic_refs = list(self.ZONE_ANA_ICS)
        ic_boxes = []
        for ref in ic_refs:
            fp = self.fps.get(ref)
            if fp is None:
                raise SystemExit("V3V3_ANA zone: no footprint for %s" % ref)
            layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
            ic_boxes.append(fp.GetCourtyard(layer).BBox())

        cap_refs = set()
        for n, nodes in self.nets:
            if n == "V3V3_ANA":
                cap_refs |= {r for r, _ in nodes if r.startswith("C")}

        radius = mm(self.ZONE_ANA_CAP_RADIUS_MM)
        included, excluded = [], []
        for ref in sorted(cap_refs):
            fp = self.fps.get(ref)
            if fp is None:
                raise SystemExit("V3V3_ANA zone: no footprint for %s" % ref)
            p = fp.GetPosition()
            d = min(self._point_bbox_dist(p.x, p.y, b) for b in ic_boxes)
            (included if d <= radius else excluded).append(ref)

        print("  V3V3_ANA island: ICs %s" % ",".join(ic_refs))
        print("  V3V3_ANA island: caps included (<=%.1f mm) %s" %
              (self.ZONE_ANA_CAP_RADIUS_MM,
               ",".join(included) if included else "(none)"))
        print("  V3V3_ANA island: caps excluded (>%.1f mm) %s" %
              (self.ZONE_ANA_CAP_RADIUS_MM,
               ",".join(excluded) if excluded else "(none)"))

        boxes = list(ic_boxes)
        for ref in included:
            fp = self.fps[ref]
            layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
            boxes.append(fp.GetCourtyard(layer).BBox())

        pad = mm(1.5)
        left = min(b.GetLeft() for b in boxes) - pad
        right = max(b.GetRight() for b in boxes) + pad
        top = min(b.GetTop() for b in boxes) - pad
        bottom = max(b.GetBottom() for b in boxes) + pad

        # the island may not creep past the middle of the U20_CORRIDOR
        # (2.6 mm) MCU<->sensor lane: clip the left edge (min x, +X right)
        # to no less than U20's courtyard right edge + half that corridor.
        u20_fp = self.fps.get("U20")
        if u20_fp is None:
            raise SystemExit("V3V3_ANA zone: no footprint for U20")
        u20_layer = pcbnew.B_CrtYd if u20_fp.IsFlipped() else pcbnew.F_CrtYd
        u20_right = u20_fp.GetCourtyard(u20_layer).BBox().GetRight()
        corridor_min_left = u20_right + mm(U20_CORRIDOR / 2.0)
        if left < corridor_min_left:
            print("  V3V3_ANA island: left edge clipped %.2f -> %.2f mm "
                  "board coords (U20 courtyard right + %.2f mm; may not "
                  "cross past the middle of the %.1f mm MCU<->sensor "
                  "corridor)"
                  % (tomm(left) - CX, tomm(corridor_min_left) - CX,
                     U20_CORRIDOR / 2.0, U20_CORRIDOR))
            left = corridor_min_left

        c0 = to_kicad(-self.HX, -self.HY)
        c1 = to_kicad(self.HX, self.HY)
        inset = mm(0.5)
        board_left = min(c0.x, c1.x) + inset
        board_right = max(c0.x, c1.x) - inset
        board_top = min(c0.y, c1.y) + inset
        board_bottom = max(c0.y, c1.y) - inset

        left = max(left, board_left)
        right = min(right, board_right)
        top = max(top, board_top)
        bottom = min(bottom, board_bottom)

        print("  V3V3_ANA island bbox: (%.2f, %.2f) to (%.2f, %.2f) mm "
              "board coords, %.2f x %.2f mm"
              % (tomm(left) - CX, CY - tomm(bottom),
                 tomm(right) - CX, CY - tomm(top),
                 tomm(right - left), tomm(bottom - top)))

        return [(left, top), (right, top), (right, bottom), (left, bottom)]

    def add_zones(self):
        """the five planes: GND/In1, V3V3_SYS/In2, V3V3_ANA/In2 (analog
        island, priority 2 so it wins over the V3V3_SYS pour on the same
        layer), GND/F, GND/B.  Filled here so the saved .kicad_pcb already
        carries filled copper for Freerouting to read as planes."""
        ana = self._analog_zone_poly()
        self._add_plane(pcbnew.In1_Cu, "GND", "gen:GND:In1", 0,
                        0.20, 0.20, self._board_rect_poly())
        # keyholed around the analog island: see _keyhole_poly.  Priority 0
        # vs 2 is kept so KiCad's filler still resolves them the same way,
        # but the outlines no longer overlap, so the DSN Freerouting reads
        # has two disjoint (plane ...) polygons on PWR instead of two
        # nested ones.
        self._add_plane(pcbnew.In2_Cu, "V3V3_SYS", "gen:V3V3_SYS:In2", 0,
                        0.20, 0.20,
                        self._keyhole_poly(self._board_rect_poly(), ana))
        self._add_plane(pcbnew.In2_Cu, "V3V3_ANA", "gen:V3V3_ANA:In2", 2,
                        0.20, 0.20, ana)
        self._add_plane(pcbnew.F_Cu, "GND", "gen:GND:F", 0,
                        0.25, 0.25, self._board_rect_poly())
        self._add_plane(pcbnew.B_Cu, "GND", "gen:GND:B", 0,
                        0.25, 0.25, self._board_rect_poly())
        # the filler's island-removal test needs the board's connectivity
        # data built from the just-placed pads; without this, F.Cu/B.Cu
        # (462/81 pads apiece) come back completely unfilled (0 mm^2)
        # because the filler cannot see any pad as touching a fill region,
        # while the sparser internal layers (52 THT pads only) happen to
        # fill anyway.  A freshly-loaded board (pcbnew.LoadBoard) builds
        # connectivity as part of loading, which is why refilling after a
        # save-and-reload silently "fixes" it - the in-process board never
        # gets that call otherwise.
        self.board.BuildConnectivity()
        pcbnew.ZONE_FILLER(self.board).Fill(self.board.Zones())

    def text(self, s, x, y, rot=0, size=LABEL_TEXT, thick=LABEL_THICK,
             layer=None, just=0, pin=False, back=False):
        """board level silkscreen text.

        `back` puts it on B.SilkS *mirrored*, so it reads the right way round
        when the board is looked at from the back.  Back text is always
        CENTRE justified: a mirrored run of glyphs is reflected about its
        anchor, so only a centred box is the same box before and after the
        mirror - which is what makes back_pad_labels() able to compute where
        a back label lands without guessing how KiCad renders it.
        """
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        if back:
            layer, just = pcbnew.B_SilkS, 0
        t.SetLayer(pcbnew.F_SilkS if layer is None else layer)
        t.SetPosition(to_kicad(x, y))
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(thick))
        t.SetTextAngleDegrees(rot)
        if just:
            t.SetHorizJustify(just)
        if back:
            t.SetMirrored(True)
        self.board.Add(t)
        # a pinned label is on a grid that was computed to fit (the IO block
        # rows): silk_fix must not move it, only keep everything else off it
        if back:
            self.back_texts.append(t)
        else:
            (self.pinned if pin else self.texts).append(t)
        return t

    def text_extent(self, s, size=LABEL_TEXT, thick=LABEL_THICK):
        """(width, height) in mm of the bounding box a silk label will have"""
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(thick))
        bb = t.GetBoundingBox()
        return tomm(bb.GetWidth()), tomm(bb.GetHeight())

    def io_labels(self):
        """(text, x, y) of every IO-block row caption, RIGHT aligned on x.

        There is no room for a label beside each of the three pins: the columns
        are 2.54 mm apart and 1.7 mm pads leave 0.84 mm between them.  Every
        ROW therefore gets a two-line caption in one band on the inner side of
        the block (left of the SIGNAL column, facing the MCU) - the signal name
        above the row centreline, the rail its POWER pin carries below it - so
        the block reads as a table.  The GND column needs no per-pin label
        because every pin of it is ground; silkscreen() brackets it with a "G"
        at each end instead.

        The geometry is exact rather than searched: at 0.60 mm (the DRC text
        minimum) a label bounding box is 1.12 mm tall, two of them 1.26 mm
        apart inside a 2.54 mm row leave 0.14 mm, and the next row's caption
        another 0.16 mm.  floorplan() reserves these boxes and silkscreen()
        draws them from this same list, so the reserved area is exactly the
        silk it protects.
        """
        out = []
        sig = self.fps[IO_REFS[0]]
        xs = sorted({round(tomm(q.GetPosition().x), 3) - CX
                     for q in sig.Pads()})
        x = xs[0] - 0.85 - IO_LABEL_X
        for pad in sig.Pads():
            num = int(pad.GetNumber())
            y = CY - tomm(pad.GetPosition().y)
            out.append((PAD_LABELS["J6"][num - 1], x, y + IO_LABEL_DY))
            out.append((PAD_LABELS["J7"][num - 1], x, y - IO_LABEL_DY))
        return out

    def io_end_labels(self):
        """(text, x, y) of the IO block's two END bands, centre justified.

        The block has no silkscreen outline of its own (the vendored footprint
        drops it so the row-caption band can have the space), so its ends are
        marked here: the three reference designators above the top row, one
        over each column, and a "G" below the bottom row on the GND column -
        the one legend the ground column needs, every pin of it being ground.

        Both bands are FIXED like the row captions: floorplan() reserves them
        and silkscreen() draws them from this same list, so what the packer
        keeps clear and what is drawn cannot drift apart.  The offset is
        solved, not tabulated - the end tick is 1.10 mm out from the end row
        and the text sits clear of it - because it is one of the two things
        that bound the board HEIGHT (check_silk() fails a band that reaches
        the rounded corner).
        """
        _, h = self.text_extent("J8", IO_LABEL_SZ)
        dy = IO_END_TICK + 0.15 + h / 2.0
        out = []
        for ref in IO_REFS:
            xs = {round(tomm(q.GetPosition().x), 3) - CX
                  for q in self.fps[ref].Pads()}
            ys = sorted(round(CY - tomm(q.GetPosition().y), 3)
                        for q in self.fps[ref].Pads())
            x = xs.pop()
            out.append((ref, x, ys[-1] + dy))
            if ref == IO_REFS[2]:                 # the GND column
                out.append(("G", x, ys[0] - dy))
        return out

    def back_pad_labels(self, ref, labels, dx, dy, rot=0, size=LABEL_TEXT):
        """one mirrored B.SilkS label per pad of a back-side row.

        (dx, dy) is the offset from the pad CENTRE to the near edge of the
        label box; the label itself is centred on that box, so it is left
        aligned (dx > 0) or right aligned (dx < 0) in effect while staying
        mirror-invariant.  Nothing else is on the back, so the band beside
        the pads is reserved by construction and no nudging is needed.
        """
        fp = self.fps[ref]
        for pad in fp.Pads():
            try:
                idx = int(pad.GetNumber()) - 1
            except ValueError:
                continue
            if idx < 0 or idx >= len(labels):
                continue
            w, _ = self.text_extent(labels[idx], size)
            p = pad.GetPosition()
            x = tomm(p.x) - CX + dx + (math.copysign(w / 2.0, dx) if dx else 0)
            y = CY - tomm(p.y) + dy
            self.text(labels[idx], x, y, rot, size=size, back=True)

    def pin_ref(self, ref, x, y, size=IO_LABEL_SZ):
        """park a FRONT reference designator at a fixed spot and pin it, so
        silk_fix treats it as an obstacle instead of hunting it a place."""
        fld = self.fps[ref].Reference()
        fld.SetVisible(True)
        fld.SetPosition(to_kicad(x, y))
        fld.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        fld.SetTextThickness(mm(LABEL_THICK))
        fld.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        self.pinned.append(fld)
        self.pinned_refs.add(ref)

    def back_ref(self, ref, dx, dy):
        """park a back-side part's reference designator beside its pads"""
        fld = self.fps[ref].Reference()
        if not fld.IsVisible():
            return
        x, y = self.pos(ref)
        w, _ = self.text_extent(self.fps[ref].GetReference(), SILK_TEXT)
        fld.SetPosition(to_kicad(
            x + dx + (math.copysign(w / 2.0, dx) if dx else 0), y + dy))
        fld.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        fld.SetTextAngleDegrees(0)
        fld.SetMirrored(True)
        self.back_texts.append(fld)

    # ---------------- silkscreen de-confliction ----------------
    def silk_fix(self, clr=0.25):
        """nudge every board level silk text (and the visible reference
        designators) until it clears all copper, the board edge and the other
        silk text; hide whatever cannot be cleared."""
        pads = []
        for fp in self.fps.values():
            for pad in fp.Pads():
                if not pad.IsOnLayer(pcbnew.F_Cu):
                    continue
                bb = pad.GetBoundingBox()
                pads.append((tomm(bb.GetLeft()) - CX, CY - tomm(bb.GetBottom()),
                             tomm(bb.GetRight()) - CX, CY - tomm(bb.GetTop())))
        # footprint (and board) silkscreen graphics: rectangles contribute
        # their four edges, everything else its bounding box
        silk = []

        def add_shape(it):
            bb = it.GetBoundingBox()
            r = (tomm(bb.GetLeft()) - CX, CY - tomm(bb.GetBottom()),
                 tomm(bb.GetRight()) - CX, CY - tomm(bb.GetTop()))
            try:
                is_rect = it.GetShape() == pcbnew.SHAPE_T_RECT
            except Exception:
                is_rect = False
            if is_rect and (r[2] - r[0]) > 1.0 and (r[3] - r[1]) > 1.0:
                w = 0.2
                silk.extend([(r[0], r[1], r[2], r[1] + w),
                             (r[0], r[3] - w, r[2], r[3]),
                             (r[0], r[1], r[0] + w, r[3]),
                             (r[2] - w, r[1], r[2], r[3])])
            else:
                silk.append(r)

        for fp in self.fps.values():
            for it in fp.GraphicalItems():
                if it.GetLayer() == pcbnew.F_SilkS:
                    add_shape(it)
        for it in self.board.GetDrawings():
            if (it.GetLayer() == pcbnew.F_SilkS
                    and it.GetClass() != "PCB_TEXT"):
                add_shape(it)

        # the pinned labels never move; they are obstacles for everything else
        done = []
        for t in self.pinned:
            bb = t.GetBoundingBox()
            done.append((tomm(bb.GetLeft()) - CX - clr,
                         CY - tomm(bb.GetBottom()) - clr,
                         tomm(bb.GetRight()) - CX + clr,
                         CY - tomm(bb.GetTop()) + clr))
        items = [(t, None) for t in self.texts]
        for ref in REF_ON_SILK:
            if ref in self.pinned_refs:     # already on a fixed band
                continue
            fp = self.fps.get(ref)
            if fp is not None and fp.Reference().IsVisible():
                items.append((fp.Reference(), ref))
        hidden = []
        for obj, ref in items:
            base = obj.GetPosition()
            size0 = obj.GetTextWidth()
            ok = False
            floor = mm(RULES["min_text_height"])
            for sz in (size0, max(floor, int(size0 * 0.85)), floor):
                if sz != size0:
                    obj.SetTextSize(pcbnew.VECTOR2I(sz, sz))
                    obj.SetTextThickness(mm(LABEL_THICK))
                ok = self._try_spot(obj, base, silk, pads, done, clr)
                if ok:
                    break
            if not ok:
                obj.SetTextSize(pcbnew.VECTOR2I(size0, size0))
                obj.SetTextThickness(mm(LABEL_THICK))
            if not ok:
                obj.SetPosition(base)
                if ref is None:                 # board level text
                    self.board.Remove(obj)
                else:                           # footprint reference field
                    obj.SetVisible(False)
                hidden.append(ref or obj.GetText())
        if hidden:
            self.notes.append("silk text hidden (no clear spot): %s"
                              % ", ".join(hidden))
        print("  silkscreen: %d texts placed, %d dropped%s"
              % (len(items) - len(hidden), len(hidden),
                 " (" + ", ".join(hidden) + ")" if hidden else ""))

    def _try_spot(self, obj, base, silk, pads, done, clr):
        for dx, dy in self._offsets():
            obj.SetPosition(pcbnew.VECTOR2I(base.x + mm(dx), base.y - mm(dy)))
            bb = obj.GetBoundingBox()
            r = (tomm(bb.GetLeft()) - CX, CY - tomm(bb.GetBottom()),
                 tomm(bb.GetRight()) - CX, CY - tomm(bb.GetTop()))
            r = (r[0] - clr, r[1] - clr, r[2] + clr, r[3] + clr)
            if not self._inside_board(r):
                continue
            if any(bbox_overlap(r, q) for q in pads):
                continue
            if any(bbox_overlap(r, q) for q in silk):
                continue
            if any(bbox_overlap(r, q) for q in done):
                continue
            done.append(r)
            return True
        return False

    @staticmethod
    def _offsets(step=0.2, rings=30):
        yield (0.0, 0.0)
        for k in range(1, rings + 1):
            for a in range(0, 360, 30):
                yield (step * k * math.cos(math.radians(a)),
                       step * k * math.sin(math.radians(a)))

    def _inside_board(self, r):
        HX, HY, cr = self.HX - 0.2, self.HY - 0.2, CORNER_R
        if not (-HX <= r[0] and r[2] <= HX and -HY <= r[1] and r[3] <= HY):
            return False
        for x in (r[0], r[2]):
            for y in (r[1], r[3]):
                if abs(x) > HX - cr and abs(y) > HY - cr:
                    dx = abs(x) - (HX - cr)
                    dy = abs(y) - (HY - cr)
                    if dx * dx + dy * dy > cr * cr:
                        return False
        return True

    # ---------------- checks ----------------
    def check(self):
        out = []
        n = len(self.placed)
        holes = {"H1", "H2", "H3", "H4"}
        # The grommet FLANGE keepout is a front-side courtyard: it keeps
        # *parts* off the hole.  A back-side pad row is not a part and does
        # not see the flange - what it has to clear is the footprint's O 5 mm
        # *.Cu keepout zone, which is checked pad by pad in check_back().
        for ref in holes & set(self.fps):
            x, y = self.pos(ref)
            for rj, aj in self.placed:
                if rj in holes or self.is_back(rj):
                    continue
                if rect_circle_overlap(aj, x, y, MOUNT_KEEPOUT_R + 0.05):
                    out.append("mounting keepout %s/%s" % (ref, rj))
        for i in range(n):
            ri, ai = self.placed[i]
            if ri in holes:
                continue
            for j in range(i + 1, n):
                rj, aj = self.placed[j]
                if rj in holes:
                    continue
                # two courtyards on OPPOSITE sides of the board cannot
                # collide; the back is deliberately under the front parts
                if self.is_back(ri) != self.is_back(rj):
                    continue
                if bbox_overlap(ai, aj, gap=0.001):
                    ox = min(ai[2], aj[2]) - max(ai[0], aj[0])
                    oy = min(ai[3], aj[3]) - max(ai[1], aj[1])
                    out.append("courtyard overlap %s/%s by %.2f x %.2f mm"
                               % (ri, rj, ox, oy))
        # copper to board edge
        HX, HY = self.HX, self.HY
        for ref, fp in self.fps.items():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                l, r = tomm(bb.GetLeft()) - CX, tomm(bb.GetRight()) - CX
                t, b = CY - tomm(bb.GetTop()), CY - tomm(bb.GetBottom())
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    continue
                m = min(HX - r, l + HX, HY - t, b + HY)
                if m < EDGE_COPPER:
                    out.append("copper-to-edge %s pad %s: %.2f mm"
                               % (ref, pad.GetNumber(), m))
        out += self.check_back()
        out += self.check_silk()
        out += self.check_rules()
        out += self.check_satellites()
        return out

    # ---------------- the back side ----------------
    def pad_boxes(self, ref, clr=0.0):
        """(x0, y0, x1, y1) of every pad of `ref`, grown by `clr`"""
        out = []
        for pad in self.fps[ref].Pads():
            bb = pad.GetBoundingBox()
            out.append((tomm(bb.GetLeft()) - CX - clr,
                        CY - tomm(bb.GetBottom()) - clr,
                        tomm(bb.GetRight()) - CX + clr,
                        CY - tomm(bb.GetTop()) + clr))
        return out

    def check_back(self, clr=0.2):
        """The back side carries BARE PADS and DNP LANDS ONLY (decision A).

        Five things are asserted here, because none of them is visible in a
        front-side courtyard check:
          1. exactly the allowed refs are flipped, and every one of them
             really is - a component that drifted to B.Cu breaks the
             single-sided-assembly rule the whole stack-up rests on;
          2. every back-side part that is NOT a bare pad row or a test point
             carries the DNP attribute, and every DNP part on the board is
             one of those back-side lands.  That is what keeps "single sided
             assembly" true with a socket on the back: a DNP land is never
             populated, so nothing is reflowed on B.Cu.  A part that lost its
             `(dnp yes)` in the schematic fails the build here rather than
             turning into a back-side component nobody can assemble;
          3. J3 pin 1 (CURR) is still the TOP pad of the vertical row - the
             flip mirrors the footprint, so a wrong rotation silently
             reverses the ESC harness order;
          4. back pads clear the grommets' O 5 mm *.Cu keepout zone and every
             front-side HOLE (the IO block's 42 through pins, the USB-C shield
             pegs, the NPTH mounting holes), which pass through to B.Cu;
          5. R35, the FLASH_CS1 pull-up, is still populated on the FRONT.
        """
        out = []
        bare = set(BACK_PAD_ROWS) | {r for r in self.fps
                                     if TEST_POINTS.match(r)}
        allowed = bare | set(BACK_DNP_PARTS)
        for ref, fp in sorted(self.fps.items()):
            if fp.IsFlipped() and ref not in allowed:
                out.append("%s is on the BACK; assembly is single sided "
                           "(front only)" % ref)
            if ref in allowed and not fp.IsFlipped():
                out.append("%s should be on the back and is not" % ref)
        for ref in sorted(set(BACK_DNP_PARTS) & set(self.fps)):
            if not self.fps[ref].IsDNP():
                out.append("%s is a back-side land but is not marked DNP in "
                           "the schematic" % ref)
            if not self.fps[ref].IsExcludedFromBOM():
                out.append("%s is DNP but still in the BOM" % ref)
        for ref, fp in sorted(self.fps.items()):
            if fp.IsDNP() and ref not in BACK_DNP_PARTS:
                out.append("%s is DNP but is not one of the back-side "
                           "expansion lands" % ref)
            if ref in bare and fp.IsDNP():
                out.append("%s is a bare pad row / test point and must not "
                           "be DNP" % ref)
        if "R35" in self.fps and (self.fps["R35"].IsFlipped()
                                  or self.fps["R35"].IsDNP()):
            out.append("R35 (FLASH_CS1 pull-up) must stay populated on the "
                       "front")
        if "J3" in self.fps and self.fps["J3"].IsFlipped():
            ys = {p.GetNumber(): CY - tomm(p.GetPosition().y)
                  for p in self.fps["J3"].Pads()}
            if ys and ys.get("1") != max(ys.values()):
                out.append("J3 pad 1 (CURR) is not the top pad of the row")
        # back pads vs the grommet copper keepout
        for ref in sorted(self.back & set(self.fps)):
            for box in self.pad_boxes(ref, clr):
                for h in ("H1", "H2", "H3", "H4"):
                    if h not in self.fps:
                        continue
                    hx, hy = self.pos(h)
                    if rect_circle_overlap(box, hx, hy, MOUNT_COPPER_R):
                        out.append("%s pad in the %s copper keepout" %
                                   (ref, h))
                        break
        # back pads vs front-side holes
        drills = []
        for ref, fp in self.fps.items():
            if ref in self.back:
                continue
            for pad in fp.Pads():
                if tomm(pad.GetDrillSizeX()) <= 0:
                    continue
                bb = pad.GetBoundingBox()
                drills.append((ref, pad.GetNumber(),
                               (tomm(bb.GetLeft()) - CX,
                                CY - tomm(bb.GetBottom()),
                                tomm(bb.GetRight()) - CX,
                                CY - tomm(bb.GetTop()))))
        for ref in sorted(self.back & set(self.fps)):
            for box in self.pad_boxes(ref, clr):
                for oref, num, hole in drills:
                    if bbox_overlap(box, hole):
                        out.append("%s back pad over the %s pad %s hole"
                                   % (ref, oref, num))
        return out

    def check_silk(self, clr=0.15):
        """Silkscreen text must not sit on copper it can be read off, on the
        board edge, or on a hole - on EITHER side.

        The front labels of the IO block are FIXED (lead's decision B): they
        are never nudged and never dropped, so the only way to know the band
        still fits is to assert it here.  The back labels are fixed for the
        opposite reason - nothing is on the back to push them around - so the
        same assertion covers both.
        """
        out = []
        front_pads, back_pads = [], []
        for ref, fp in self.fps.items():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                r = (tomm(bb.GetLeft()) - CX, CY - tomm(bb.GetBottom()),
                     tomm(bb.GetRight()) - CX, CY - tomm(bb.GetTop()))
                if pad.IsOnLayer(pcbnew.F_Cu):
                    front_pads.append((ref, pad.GetNumber(), r))
                if pad.IsOnLayer(pcbnew.B_Cu):
                    back_pads.append((ref, pad.GetNumber(), r))
        items = ([(t, front_pads, "F.SilkS") for t in self.pinned] +
                 [(t, back_pads, "B.SilkS") for t in self.back_texts])
        for t, pads, layer in items:
            bb = t.GetBoundingBox()
            r = (tomm(bb.GetLeft()) - CX - clr, CY - tomm(bb.GetBottom()) - clr,
                 tomm(bb.GetRight()) - CX + clr, CY - tomm(bb.GetTop()) + clr)
            for ref, num, q in pads:
                if bbox_overlap(r, q):
                    out.append("%s label %r on %s pad %s"
                               % (layer, t.GetText(), ref, num))
            if not self._inside_board(r):
                out.append("%s label %r is off the board"
                           % (layer, t.GetText()))
        return out

    def check_rules(self):
        """the two placement rules that are circuit requirements: switcher
        loop components next to their IC, switching inductors away from the
        MEMS sensors.  Both are measured body to body (courtyard gap)."""
        out = []
        rect = dict(self.placed)
        for ic, refs in CAP_NEAR.items():
            if ic not in rect:
                continue
            worst = []
            for r in refs:
                if r not in rect:
                    continue
                d = bbox_gap(rect[r], rect[ic])
                worst.append((d, r))
                if d > CAP_NEAR_MM:
                    out.append("%s is %.1f mm from %s (limit %.1f mm)"
                               % (r, d, ic, CAP_NEAR_MM))
            if worst:
                print("  loop  %-4s caps %s" % (ic, "  ".join(
                    "%s %.1f" % (r, d) for d, r in sorted(worst))))
        for li in INDUCTORS:
            if li not in rect:
                continue
            near = []
            for s in SENSORS:
                if s not in rect:
                    continue
                d = bbox_gap(rect[li], rect[s])
                near.append((d, s))
                if d < IND_SENSOR_MM:
                    out.append("%s is only %.1f mm from %s (need %.1f mm)"
                               % (li, d, s, IND_SENSOR_MM))
            if near:
                print("  sens  %-4s to %s" % (li, "  ".join(
                    "%s %.1f" % (s, d) for d, s in sorted(near))))
        tps = sorted((r for r in rect if TEST_POINTS.match(r)),
                     key=lambda r: int(r[2:]))
        worst = []
        for r in tps:
            d = min(bbox_gap(rect[r], rect[s]) for s in SENSORS if s in rect)
            worst.append((d, r))
            if d > TP_NEAR_MM:
                out.append("%s is %.1f mm from the nearest sensor "
                           "(limit %.1f mm)" % (r, d, TP_NEAR_MM))
        if worst:
            print("  probe %2d test points, worst %s %.1f mm from a sensor"
                  % (len(worst), max(worst)[1], max(worst)[0]))
        return out

    def report_area(self):
        """Fill is the FRONT number: the front is the assembly side and the
        only one that has to hold everything.  The back's own courtyard sum is
        reported beside it so the pad rows are not invisible, but the two are
        not added - they are different sides of the same board."""
        tot = back = 0.0
        for ref, rect in self.placed:
            a = (rect[2] - rect[0]) * (rect[3] - rect[1])
            if self.is_back(ref):
                back += a
            else:
                tot += a
        area = 4 * self.HX * self.HY
        print("  board %.1f x %.1f mm = %.0f mm2, front courtyard sum %.0f "
              "mm2 (%.1f %% fill), back %.0f mm2 (%.1f %%)"
              % (2 * self.HX, 2 * self.HY, area, tot, 100 * tot / area,
                 back, 100 * back / area))


# --------------------------------------------------------------------------
# the actual floorplan
# --------------------------------------------------------------------------
def floorplan(B, comps):
    """Place everything.  Board coordinates, origin at the board centre.

    THE ARRANGEMENT (lead's decision, madflight FC3v2 layout):
      right edge   J6/J7/J8, one 3-column x 14-row 2.54 mm block, full height,
                   columns GND | POWER | SIGNAL from the edge inward
      left edge    nothing: the ESC pad row moved to the back this revision,
                   so the margin is only what the grommet keepout needs
      bottom edge  J4 USB-C left of centre, SW1/SW2 just above it, D20 beside
                   it
      top edge     J11 microSD, card ejecting +Y, left of centre
      interior     U20 right of centre; the sensor island between the MCU and
                   the IO block; U7/L2/U12 above it; U26/L3/U25/C19 in the
                   left-centre pocket
      BACK         J3 (ESC row, vertical, CURR at the top) hard against the
                   LEFT EDGE, J10 (DBG) at the bottom right, TP1-TP10
                   directly under the sensor island, and the DNP flash/PSRAM
                   expansion U24 + C62/C63 under the MCU's QSPI pads.  Bare
                   pads and unpopulated lands only - see back_side(),
                   BACK_PAD_ROWS and BACK_DNP_PARTS.
    """
    HX, HY = B.HX, B.HY

    # ---------------- mounting holes ----------------
    # OFF-CENTRE in X: 7.0 mm of margin on the left (the ESC pad row lives
    # there), the rest on the right (the IO block lives there).
    mx_l, mx_r = B.mx_l, B.mx_r
    for ref, x, y in (("H1", mx_l, MOUNT_Y), ("H2", mx_r, MOUNT_Y),
                      ("H3", mx_r, -MOUNT_Y), ("H4", mx_l, -MOUNT_Y)):
        B.place(ref, x, y, 0)
        B.fps[ref].SetLocked(True)

    # ---------------- RIGHT edge: the IO block ----------------
    # Three 1x14 rows abutting on the 2.54 mm grid.  J8 (GND) is the outermost
    # column, then J7 (POWER), then J6 (SIGNAL) innermost, next to the MCU:
    # the fourteen signals are what has to be routed, the two rails are plane
    # stitches.  Pin 1 of every row is at the TOP (rotation 0 of the stock
    # 1x14 footprint already gives that), the block is centred in Y.
    io_x = {}
    for i, ref in enumerate(reversed(IO_REFS)):          # J8, J7, J6
        io_x[ref] = HX - IO_EDGE - i * IO_PITCH
        B.anchor(ref, 0, ("padc", io_x[ref]), ("padc", 0.0))
    io_blk = [dict(B.placed)[r] for r in IO_REFS]

    # ---------------- LEFT edge: nothing ----------------
    # The ESC pad row J3 used to own the 7 mm margin outboard of H1/H4.  It is
    # on the BACK now (back_side() below), so the left margin is only what the
    # grommet flange keepout needs - MOUNT_MARGIN_L, 4.0 mm - and the 3 mm
    # that freed came straight off the board width.

    # ---------------- BOTTOM edge ----------------
    # mcu_x0 is the MCU's x (see "fixed interior" below, where the QFN is
    # actually placed): the bottom-edge row is anchored to it, and it is only
    # named here because the row is placed first.
    mcu_x0 = HX - 24.55
    # The bottom-edge group is anchored to the MCU, not to absolute x: the
    # MCU is pinned to the RIGHT board edge (see mcu_x), so anchored to the
    # board centre - or worse, to the left edge - the row and the QFN walk
    # towards each other as --width shrinks and the switches end up under the
    # package.
    # Tied to mcu_x the whole row keeps its spacing at any width, and the
    # width is taken out of the left-centre pocket, which is where the ESC
    # row's old margin went.  The offsets are the ones the 48.7 mm board had.
    B.anchor("J4", 0, ("org", mcu_x0 - 7.8), ("org", -HY + 3.65))  # USB-C
    j4 = dict(B.placed)["J4"]
    B.anchor("SW1", 0, ("cyc", mcu_x0 - 10.8), ("cymin", j4[3] + 0.4))  # RST
    B.anchor("SW2", 0, ("cyc", mcu_x0 - 5.0), ("cymin", j4[3] + 0.4))  # BOOT
    B.place("D20", mcu_x0 - 0.8, -HY + 2.2, 0)              # RGB LED
    # C79 (the LED's 5 V bypass) and R55 (the data series terminator) are NOT
    # anchored here any more: both are satellites of D20 itself (SATELLITES),
    # C79 on its VDD pad and R55 on its DIN pad, so the packer puts them
    # against the pins instead of merely in the same corner.

    # ---------------- TOP edge ----------------
    # microSD, card ejecting +Y (upward), left of centre and above the left
    # mounting hole, as on the FC3v2.  It cannot sit *over* H1: at 13.8 mm of
    # courtyard its left edge is what the H1 keepout limits.
    # hard against the H1 keepout on its left: at 13.8 mm of courtyard the
    # socket is the widest thing on the top edge and the keepout is what says
    # how far left it can start, so anchoring it to the hole (not to a fixed
    # x) keeps the arrangement when --width moves the hole.
    B.anchor("J11", 0, ("cymin", mx_l + MOUNT_KEEPOUT_R + 0.4),
             ("cymax", HY - 0.6))
    j11 = dict(B.placed)["J11"]

    # ---------------- fixed interior ----------------
    # U20 is ROTATED 180 deg.  At rotation 0 the QFN-80 has its QSPI pads
    # (70-75) on the top edge and XIN/XOUT (30/31) on the bottom one, and the
    # sensor bus (16-25), both UARTs, I2C1 and PWM5-8 all leave on the LEFT
    # side of the package.  Turned round, the QSPI pads face DOWN - towards
    # U24, which this floorplan puts below the MCU - and the twenty-odd pins
    # that have to reach the sensor island and the IO block face RIGHT,
    # towards both.  The crystal follows XIN/XOUT to the top.
    # x is as far right as the sensor island allows, which is less far than it
    # looks.  The island is the strip between the QFN and the IO block's
    # row-label band; the band starts 2.3 mm inboard of the signal column, so
    # the strip runs from mcu_x + 5.67 to 15.27 and has to hold three MEMS
    # packages, their decoupling and ten 1 x 1 mm test pads in a corridor wide
    # enough for a 2.18 mm pad plus its gap.  At mcu_x = 2.0 the corridor takes
    # six of the ten test points and the other four have nowhere to go.
    # The island runs from the QFN to the IO block's row-label band, and the
    # band's inner edge is a fixed offset from the board's right edge, so the
    # MCU's x is pinned to HX: move the edge and the island, not the island's
    # width.  ISLAND_W is what the three MEMS packages, their decoupling and a
    # corridor wide enough for a 2.18 mm test pad actually need.
    mcu_x, mcu_y = mcu_x0, -1.0
    mcu = B.place("U20", mcu_x, mcu_y, 180)
    # the crystal group is offset right of the QFN centre: at the centre its
    # left load cap runs into the microSD socket, whose own left edge is
    # already hard against the H1 grommet keepout, so on a narrower board the
    # socket is what sets it, not the QFN.  Its y is hard-coded rather than
    # derived from mcu_y, so it is shifted by the same amount as the QFN to
    # keep its 0.76 mm gap to XIN/XOUT.
    xtal_x = max(mcu_x + 1.8, j11[2] + 3.9)
    xtal_y = mcu_y + 8.2
    B.place("Y1", xtal_x, xtal_y, 0)               # crystal at XIN/XOUT
    B.place("C46", xtal_x - 3.0, xtal_y, 90)
    B.place("C47", xtal_x + 3.0, xtal_y, 90)
    B.place("R21", xtal_x, xtal_y + 2.5, 0)

    # ---------------- the corridor beside the QFN (U20_CORRIDOR) --------
    # THE SENSOR ISLAND MOVES AS ONE BLOCK.  U21/U22/U23 and the LDO that
    # feeds them are the right flank of the MCU, and at their old x the
    # widest gap any of them left the QFN was 0.36 mm - a corridor no 0402
    # fits in, in any orientation, which is why a third of U20's decoupling
    # was landing on the far side of the board.  The shift is the largest
    # any ONE of the four needs and is applied to all four, so the layout
    # inside the island - and with it every TP_NEAR_MM test point under it,
    # which back_side() solves from isl_x - is unchanged.
    isl_x0 = mcu_x + 6.0                    # island left edge, as drawn
    u12_x0 = max(mcu_x + 8.4, xtal_x + 6.0)
    ISLAND = (("U23", isl_x0 + 2.0, -8.5),  # ADXL375, the tallest package
              ("U21", isl_x0 + 1.8, -3.0),  # ICM-45686
              ("U22", isl_x0 + 1.25, 1.2),  # BMP581
              ("U12", u12_x0, 6.6))         # the analog LDO
    isl_dx = max([0.0] + [mcu[2] + U20_CORRIDOR - (x + B.g(r, 0).cy[0])
                          for r, x, _ in ISLAND])
    isl_x = isl_x0 + isl_dx

    # The two switchers are anchored rather than packed: their loop geometry is
    # a circuit requirement (CAP_NEAR), and the grommet keepouts break the
    # interior into pockets too narrow for the packer to discover a sane
    # switcher block on its own.
    #   U26 + L3 (the VBAT buck) go in the left-centre pocket, just inboard
    #   of the J3 VBAT pad: the row is on the back against the left edge with
    #   its pad 7 (VBAT) at y = -5, so VBAT crosses about 5 mm of board and
    #   one via into the buck's own input.
    #   U7 + L2 (the 3.3 V buck) go in the top band above the MCU, with L2 to
    #   the LEFT of U7 because the TPS62913's SW (pad 2) and VO (pad 3) are
    #   both on that side of the RPU package.  L2 is the reason the band is at
    #   the top: IND_SENSOR_MM keeps it 8 mm clear of the sensor island, and
    #   the island is the strip between the MCU and the IO block.
    # the left-pocket chain is pinned to the LEFT edge (the ESC row is there
    # and VBAT comes in on it), the top band to the TOP edge
    # y is measured from the BOTTOM edge: the two switches sit on a band just
    # above the USB-C receptacle and that band rises as the board gets shorter,
    # so a fixed y walks the buck into SW1.
    buck_y = -HY + 15.8
    # POCKET_L below is why these are 2.5 mm further left than they were:
    # the ESC row and its label band used to own the first 3.4 mm of the
    # left edge and now nothing does.
    # The mux's x is solved first (U20_CORRIDOR: it has to stand clear of the
    # QFN's LEFT flank), because the buck and its inductor only follow it
    # left if it would otherwise land on them - which, at 0.4 mm of vertical
    # clearance between the two rows, it does not.
    u25_y = buck_y + 4.5
    g25 = B.g("U25", 0)
    u25_x = min(-HX + POCKET_L + 12.95, mcu[0] - U20_CORRIDOR - g25.cy[2])
    u25_box = (u25_x + g25.cy[0], u25_y + g25.cy[1],
               u25_x + g25.cy[2], u25_y + g25.cy[3])
    pocket_dx = 0.0
    for r, rx in (("U26", 5.95), ("L3", 10.95)):
        g = B.g(r, 0)
        box = (-HX + POCKET_L + rx + g.cy[0], buck_y + g.cy[1],
               -HX + POCKET_L + rx + g.cy[2], buck_y + g.cy[3])
        if bbox_overlap(u25_box, box, 0.001):
            pocket_dx = min(pocket_dx, u25_box[0] - 0.25 - box[2])
    B.place("U26", -HX + POCKET_L + 5.95 + pocket_dx, buck_y, 0)
    B.place("L3", -HX + POCKET_L + 10.95 + pocket_dx, buck_y, 0)
    l2_x = max(mcu_x + 0.8, j11[2] + 2.6)
    B.place("L2", l2_x, HY - 3.6, 0)
    B.place("U7", l2_x + 4.5, HY - 3.6, 0)
    # U12, the analog LDO: at the right-hand end of the band above the MCU,
    # where the sensor island starts.  Anchored because the U7 loop fills the
    # band otherwise.  It sits at the TOP OF THE ISLAND rather than up beside
    # U7: DESIGN_SPEC "Heat and interference" puts U12 on the analog island
    # with the sensors and away from both switchers, and the 3.4 mm this
    # frees under U7 is where the post-bead output caps C23/C24 go - at the
    # old y = 10.0 they were the two parts CAP_NEAR could not satisfy (C24
    # was 7.2 mm out), because the H2 grommet keepout owns the middle of the
    # band from y = 11.7 up and the microSD socket owns everything left of
    # L2.  The clearance above is C47's courtyard, the crystal's right load
    # capacitor, which is the one anchored part in the way.
    # It moves right with the rest of the island (isl_dx, U20_CORRIDOR).
    B.place("U12", u12_x0 + isl_dx, 6.6, 0)
    # U25, the priority mux: anchored in the left-centre pocket, where VBAT
    # and 5V_IN already are, U20_CORRIDOR clear of the QFN's left flank.
    B.place("U25", u25_x, u25_y, 0)
    # C19, the 100 uF polymer - 8.9 x 4.9 mm of courtyard, the biggest passive
    # on the board - used to be anchored in the top left corner, three
    # centimetres of rail away from the pin it holds up.  It is a satellite of
    # the mux's OUT pad now (SATELLITES), placed before the two 10 uF beside
    # it because it is the one that needs the room.
    # U8, the USB ESD array, sits beside the receptacle rather than being
    # packed: the two switches take the whole band above J4.
    B.place("U8", -HX + POCKET_L + 2.35, buck_y - 4.6, 0)
    # U24, the QSPI flash/PSRAM socket, is NOT on the front any more: it is a
    # DNP expansion land on the BACK, against the same QSPI pads - see
    # back_side() and BACK_DNP_PARTS.  The pocket under the MCU that it used
    # to fill went back to the MCU decoupling.
    # THE SENSOR ISLAND is anchored, not packed.  The strip between the QFN and
    # the IO block's row-label band is 7.4 mm wide; packed from a seed the
    # three sensors scatter across it and leave slivers 1.9 mm wide, which is
    # 0.3 mm less than a 1 x 1 mm test pad needs - and TP1-TP10 have to land
    # within TP_NEAR_MM of the part they probe or they are stubs on a 10 MHz
    # bus.  Stacked against the MCU side of the strip they leave one clean
    # corridor down the block side for the pads and the gaps between them for
    # the decoupling.  Anchored BEFORE build_grid so the MCU decoupling, which
    # is packed first, packs around them.
    # isl_x / isl_dx and the ISLAND table are solved beside the crystal above
    # (U20_CORRIDOR); U12 is the fourth member and is already down.
    for r, x, y in ISLAND:
        if r != "U12":
            B.place(r, x + isl_dx, y, 0)

    # ---- the corridors this opened (lead's decision A) ------------------
    # Every IC, connector and inductor courtyard that overlaps the QFN's own
    # y band, with its horizontal gap to the package: the narrowest of these
    # is the lane U20's decoupling has to live in.
    flank = {"left": [], "right": [], "above": [], "below": []}
    for ref, rect in B.placed:
        if ref == "U20" or B.is_back(ref) or \
                not re.match(r"^(U|J|L|Y|SW|D)\d+$", ref):
            continue
        if rect[1] < mcu[3] and mcu[1] < rect[3]:       # beside the package
            if rect[2] <= mcu[0]:
                flank["left"].append((mcu[0] - rect[2], ref))
            elif rect[0] >= mcu[2]:
                flank["right"].append((rect[0] - mcu[2], ref))
        if rect[0] < mcu[2] and mcu[0] < rect[2]:       # over or under it
            if rect[1] >= mcu[3]:
                flank["above"].append((rect[1] - mcu[3], ref))
            elif rect[3] <= mcu[1]:
                flank["below"].append((mcu[1] - rect[3], ref))
    for side in ("left", "right", "above", "below"):
        # U20_CORRIDOR is the lead's decision for the LEFT and RIGHT flanks
        # only; above and below are reported, not enforced - the crystal
        # group, the microSD socket, the USB receptacle, the buttons and the
        # LED are all anchored parts this floorplan may not move.  An
        # inductor is not an IC or a connector and does not bind either.
        print("  corr  U20 %-5s %s" % (side, "  ".join(
            "%s %.2f%s" % (r, d, " (inductor)" if r.startswith("L") else
                           ("" if d >= U20_CORRIDOR - 1e-6 or
                            side in ("above", "below") else " UNDER"))
            for d, r in sorted(flank[side])[:5]) or "clear"))

    # ---------------- the back side ----------------
    # Bare pads only (see BACK_PAD_ROWS).  Nothing is packed here: the back is
    # empty by construction, so every one of these is a solved position rather
    # than a search, and check_back() asserts they clear the grommets' copper
    # keepout and every front-side hole.  Placed HERE, before the reserved
    # bands and the packer's `fixed` snapshot, so the cluster sweep below
    # treats J3/J10/TP* as already placed instead of packing them onto the
    # front - which is exactly what the snapshot is for.
    back_side(B, isl_x, mx_r)

    # ---------------- reserved bands (silk pad labels) ----------------
    # Only the front silk needs reserving.  The ESC row's and the DBG row's
    # label bands and the U24 expansion legend are all on the back with their
    # pads, and the back is empty, so what is left on the front is the board
    # name and the IO block's row captions.
    reserved = [
        (-HX + 0.4, -HY + 0.4, -HX + 6.6, -HY + 2.2),   # board name
    ]
    # the IO block row captions: 28 small boxes (a signal name and a rail name
    # per row) rather than one slab, so the sensor island keeps every cell the
    # labels do not actually use.  Together they span the FULL height of the
    # block, and silkscreen() draws every one of them at exactly the position
    # reserved here: the labels are FIXED (lead's decision B), so a part that
    # would collide with one simply cannot be placed there.
    for s, lx, ly in B.io_labels():
        w, h = B.text_extent(s, IO_LABEL_SZ)
        reserved.append((lx - w - IO_LABEL_CLR, ly - h / 2 - 0.05,
                         lx + IO_LABEL_CLR, ly + h / 2 + 0.05))
    # the block's two end bands (J6/J7/J8 above the top row, "G" below the
    # bottom one), from the same list silkscreen() draws them from
    for s, lx, ly in B.io_end_labels():
        w, h = B.text_extent(s, IO_LABEL_SZ)
        reserved.append((lx - w / 2 - IO_LABEL_CLR, ly - h / 2 - 0.05,
                         lx + w / 2 + IO_LABEL_CLR, ly + h / 2 + 0.05))
    B.build_grid(reserved)

    # ---------------- satellites: the passives that sit ON a pin ----------
    # Every part in SATELLITES is placed here, against the pad it serves,
    # before a single region is packed - so the decoupling, the dividers, the
    # series terminators and the switcher loops take the cells next to their
    # pins and the region packing gets what is left, rather than the other way
    # round.  This includes both switcher loops: place_satellites() seeds on
    # the IC pad and scores candidates by the PAD-TO-PIN distance, which is
    # strictly tighter than power_loop()'s "somewhere inside the halo", so
    # power_loop() is no longer used by this floorplan (CAP_NEAR still checks
    # the result).
    #
    # It has to run after build_grid(): the grid is what holds the anchored
    # parts, the mounting-hole keepouts and the reserved silk bands, and a
    # satellite obeys all three like any other packed part.
    B.verify_satellites(comps)
    B.place_satellites([o for o in SAT_OWNERS if o in B.fps])

    # ---------------- clusters ----------------
    # (refs, seed, bounding boxes the cluster may use)
    ring = [(mcu[0] - 4.4, mcu[1] - 4.4, mcu[2] + 4.4, mcu[3] + 4.4)]
    # the left-centre pocket: everything between the ESC row and the MCU.
    # It stops short of |y| = 11.4 because the H1/H4 keepouts start there.
    # capped at y = 2.4 on the right: the band above that and under the
    # microSD socket belongs to the socket's own bypass and pull-ups (nw), and
    # the left-pocket clusters are packed first, so if west reached into it
    # they would take it.
    west = [(-HX + POCKET_L, -11.4, mcu[0] - 0.3, 2.4),
            (-HX + POCKET_L, 2.4, -HX + POCKET_L + 9.0, 11.4)]
    # bottom left, around the USB-C receptacle
    sw = [(-HX + POCKET_L, -HY + 0.4, -HX + POCKET_L + 8.0, -6.0),
          (mcu_x - 13.1, -11.7, mcu_x - 2.5, -6.0)]
    # around the microSD socket: the strip below it and the corner left of it
    nw = [(-HX + 12.55, 2.4, j11[2] - 0.3, j11[1] - 0.3)]
    # the top band, above the MCU and right of the microSD: U7/L2 are already
    # in it, this is for their loop, U12 and the LED bypass
    north = [(j11[2] + 0.1, 9.6, HX - 7.95, HY - 0.4)]
    # THE SENSOR ISLAND: the strip between the MCU and the IO block's label
    # band.  Its ceiling is what keeps IND_SENSOR_MM to L2 in the top band.
    east = [(mcu[2] + 0.25, -11.6, HX - 10.05, 8.2)]
    # below the MCU, around U24
    south = [(mcu[0] + 1.2, -HY + 3.6, mcu[2] + 1.8, mcu[1] - 0.3)]
    groups = {
        "mcu_ring": (["C30", "C31", "C32", "C33", "C34", "C35", "C36", "C37",
                      "C38", "C39", "C40", "C41", "C42", "C43", "C44", "C45",
                      "C48", "C49", "C78", "R53", "L20", "R20", "R24",
                      "C22"],
                     (mcu_x, mcu_y), ring + south + west),
        "i2c":      (["R25", "R26"], (mcu_x + 7.0, 4.5),
                     east + ring + north),
        # the ESC telemetry series resistor belongs at the J3 TX pad
        # U24/C62/C63 are on the BACK (back_side(), BACK_DNP_PARTS) and are
        # already in `fixed` by the time this table is used, so the only
        # front-side member left is R35, the FLASH_CS1 pull-up - which is
        # exactly the part that stays populated.  The three DNP refs are kept
        # in the list so that anything new on their nets still votes itself
        # into this group rather than into mcu_ring.
        "flash":    (["U24", "C62", "C63", "R35"], (mcu_x + 1.8, -12.0),
                     south),
        "usb":      (["U8", "R22", "R23", "R4", "R5", "C7"], (-14.5, -6.5),
                     sw + west + ring),
        "led":      (["C79", "R55"], (-1.0, -15.6), south),
        "sd_byp":   (["C64", "C65", "C66"], (j11[2] - 3.0, j11[1] - 2.0),
                     nw + ring),
        "sd_pu":    (["R36", "R37", "R38", "R39", "R40", "R41"],
                     (j11[2] - 1.0, j11[1] - 2.0), nw + ring),
        "adc_div":  (["R27", "R28", "R29", "R30"],
                     (-HX + POCKET_L + 2.1, -2.0),
                     west + sw),
        "buck5":    (["R54"], (-HX + POCKET_L + 3.45, 8.2), west),
        "mux":      (["U25", "C70", "C71", "C72", "R42", "R43", "R44", "R45",
                      "R46", "R47"], (-HX + POCKET_L + 14.45, -0.5), west),
        # The analog island: the three MEMS sensors, their decoupling and the
        # LDO that feeds them, kept IND_SENSOR_MM clear of L2/L3.  The ten test
        # points that used to share this strip are on the back now, so the
        # decoupling has the whole island to itself - see back_side().
        "sens":     (["C50", "C51",
                      "C52", "C53", "C54", "C55", "C56", "C57", "C58", "C59",
                      "C60", "C61", "R48", "R50", "R51"],
                     (isl_x + 1.5, -3.0), east + south),
        # C25/C26 are U12's own input and output caps and belong beside it on
        # the island; R10 is the PG pull-up and can sit anywhere on the band.
        "reg3v3":   (["U12", "C25", "C26", "R10"], (mcu_x + 9.4, 6.6),
                     east + north + ring),
        # C20/C21 are the V5_SYS local bulk "at the array" and C22 the
        # V3V3_SYS one: the array is the right edge now, so they belong in the
        # top band beside U12, not in the left pocket where the old left-edge
        # array put them.
        "v5bulk":   (["C19", "C20", "C21"], (mcu_x + 10.2, 10.0),
                     north + east + ring),
    }
    # anything the schematic gained since this table was written follows the
    # cluster its net neighbours are in.  `assigned` is taken BEFORE the
    # satellites are struck out of the region lists below, so a new part still
    # votes itself into the region its neighbours belong to even though those
    # neighbours are no longer packed with it.
    assigned = {r: g for g, (refs, _, _) in groups.items() for r in refs}
    assigned.update({r: SAT_GROUP[v[0]] for r, v in B.sat.items()
                     if v[0] in SAT_GROUP})
    groups["u7"] = ([], (6.1, 13.0), north)
    # THE SATELLITES ARE ALREADY DOWN (see above): strike them out of the
    # region lists so the regions hold what is actually left to pack.  They
    # are in `fixed` as well, which is the belt to this braces.
    for refs, _, _ in groups.values():
        refs[:] = [r for r in refs if r not in B.sat]
    # everything anchored so far, including the whole back side, is off limits
    # to the cluster sweep below
    fixed = {r for r, _ in B.placed}
    for ref in sorted(B.fps):
        if ref in assigned or ref in fixed:
            continue
        votes = {}
        for net, nodes in B.nets:
            if net == "GND" or len(nodes) > 14:
                continue
            if any(r == ref for r, _ in nodes):
                for r, _ in nodes:
                    if r in assigned:
                        votes[assigned[r]] = votes.get(assigned[r], 0) + 1
        g = max(votes, key=votes.get) if votes else "mcu_ring"
        groups[g][0].append(ref)
        B.notes.append("%s was not in the placement table, packed with %s"
                       % (ref, g))

    if os.environ.get("SETUP_PCB_REGIONS"):
        for nm, rects in (("ring", ring), ("north", north), ("west", west),
                          ("sw", sw), ("nw", nw), ("south", south),
                          ("east", east)):
            tot = fr = 0.0
            for r in rects:
                i0, i1 = B._ix(r[0]), B._ix(r[2])
                j0, j1 = B._iy(r[1]), B._iy(r[3])
                sub = B.occ[i0:i1, j0:j1]
                tot += sub.size * B.CELL ** 2
                fr += (~sub).sum() * B.CELL ** 2
            print("  region %-8s %6.0f mm2 total, %6.0f mm2 free"
                  % (nm, tot, fr))

    # Groups whose parts have exactly one sane home come before the ones that
    # can spill: the sensor decoupling can sit anywhere near its own package,
    # but U24's two bypass caps have only the pocket under the MCU, and the
    # microSD's only the band under the socket.  Packed the other way round the
    # island's spill took both pockets and left C62/C63 23 mm from U24.
    order = ["mcu_ring", "mux", "sd_byp", "sd_pu", "usb", "flash", "sens",
             "reg3v3", "i2c", "v5bulk", "adc_div", "buck5", "u7", "led"]
    for name in order:
        refs, seed, bounds = groups[name]
        # the satellites and the anchored parts are already down
        refs = [r for r in refs if r not in fixed]
        if not refs:
            continue
        if name == "mcu_ring":
            for r in sorted(refs, key=lambda r: -B.g(r, 0).area()):
                sd = B.mcu_pin_seed(r, comps, seed)
                d = B.place_near(r, sd, (0, 90), bounds=bounds)
                if d is None:
                    d = B.place_near(r, sd, (0, 90))
                if d is None:
                    B.problems.append("mcu_ring: no room for %s" % r)
                    B.place(r, -B.HX + 4, -B.HY - 30, 0)
            print("  cluster mcu_ring  %2d parts, seeded on their QFN pins"
                  % len(refs))
        else:
            B.cluster(name, refs, seed, bounds)
        if os.environ.get("SETUP_PCB_BOX") == name:
            bx = [float(v) for v in os.environ["SETUP_PCB_BOXR"].split(",")]
            for ref, rect in B.placed:
                if bbox_overlap(rect, tuple(bx)):
                    print("      in box: %-5s [%6.2f %6.2f %6.2f %6.2f]"
                          % (ref, rect[0], rect[1], rect[2], rect[3]))
        if os.environ.get("SETUP_PCB_FREE"):
            fr = {}
            for nm, rects in (("ring", ring), ("north", north),
                              ("west", west), ("sw", sw), ("nw", nw),
                              ("south", south), ("east", east)):
                f = 0.0
                for r in rects:
                    sub = B.occ[B._ix(r[0]):B._ix(r[2]),
                                B._iy(r[1]):B._iy(r[3])]
                    f += (~sub).sum() * B.CELL ** 2
                fr[nm] = f
            print("      free after %-8s %s" % (name, " ".join(
                "%s=%.0f" % (k, v) for k, v in fr.items())))
        if os.environ.get("SETUP_PCB_MAP") == name:
            step = 4
            for j in range(B.gny - 1, -1, -step):
                row = ""
                for i in range(0, B.gnx, step):
                    row += "#" if B.occ[i:i + step, j - step + 1:j + 1].any() \
                        else "."
                print("   |" + row)


def back_side(B, isl_x, mx_r):
    """Place what lives on B.Cu: the ESC pad row J3, the DBG pad row J10, the
    ten test points, and the DNP flash/PSRAM expansion U24 + C62/C63.

    Bare pads and unpopulated lands only - nothing here is assembled, so the
    front is still the single-sided assembly side; check_back() asserts both
    halves of that (what is flipped, and that everything flipped which is not
    a pad row or a test point carries the DNP attribute).

    Nothing here is packed.  The back is empty by construction, so each
    position is solved from the one obstacle that does reach through the
    board - the grommets' O 5 mm copper keepout and the front-side holes -
    and check_back() asserts the result rather than trusting it.
    """
    HX, HY = B.HX, B.HY

    # ---- J3, the ESC pad row -------------------------------------------
    # AGAINST THE LEFT EDGE (see ESC_BACK_*), vertical, pad 1 (CURR) at the
    # top: the pad OUTER edge sits PAD_EDGE_INSET in from Edge.Cuts, exactly
    # as J10 sits against the bottom edge, and the row is centred in Y
    # between the two left grommets.  Both anchors are solved rather than
    # tabulated so --width/--height keep the alignment.  0.5 mm of copper to
    # the edge is 0.2 mm above the EDGE_COPPER rule, and the row's +-7.7 mm
    # of copper stops 5.05 mm short of the grommets' O 5 mm copper keepout,
    # which reaches only |y| = 12.75; check_back() asserts both.
    B.anchor("J3", ESC_BACK_ROT, ("padmin", -HX + PAD_EDGE_INSET),
             ("padc", ESC_BACK_Y))

    # ---- J10, the DBG landing ------------------------------------------
    # Bottom edge, as far RIGHT as the H3 grommet lets it go.  On the front
    # the limit was the flange courtyard; on the back it is the O 5 mm copper
    # keepout, which is 0.75 mm smaller in radius, so the row sits further
    # right than it used to.  Solved, not tabulated, so --height stays
    # meaningful: as the board gets shorter the pad row climbs towards the
    # keepout and the usable x shrinks with it.
    # Two things stick out to the right and both have to clear the circle: the
    # pad row itself, and the "GND" caption standing above its last pad - the
    # caption is narrower but reaches 3.3 mm further up, which is *towards*
    # the hole centre, so it is the binding one at the wider board sizes.
    pad_lo, pad_hi = -HY + PAD_EDGE_INSET, -HY + PAD_EDGE_INSET + 2.2
    lw, lh = B.text_extent(PAD_LABELS["J10"][-1])
    lab_c = (pad_lo + pad_hi) / 2.0 + J10_LABEL_DY
    boxes = [(2.0 + 0.7, pad_lo, pad_hi),                      # the pads
             (2.0 + lh / 2.0, lab_c - lw / 2.0, lab_c + lw / 2.0)]
    r = MOUNT_COPPER_R + 0.35
    x_max = min(mx_r - math.sqrt(max(r * r - max(
        0.0, -MOUNT_Y - hi, lo + MOUNT_Y) ** 2, 0.0)) - out
        for out, lo, hi in boxes)
    B.anchor("J10", 0, ("org", x_max), ("padmin", pad_lo))

    # ---- U24 + C62/C63, the OPTIONAL flash/PSRAM expansion ---------------
    # DNP parts, not bare pads (see BACK_DNP_PARTS).  Placed against U20's
    # QSPI pads 70-75, which face DOWN because the QFN is at 180 deg, so the
    # six QSPI nets drop straight through the board into the socket and the
    # stubs are one via plus the board thickness.  Solved from the pads, not
    # tabulated: the MCU moves with --width.
    QSPI = ("70", "71", "72", "73", "74", "75")
    qx = sum(B.pad_pos("U20", n)[0] for n in QSPI) / len(QSPI)
    qy = min(B.pad_pos("U20", n)[1] for n in QSPI)
    # x: the socket's RIGHT courtyard edge stops clear of the left test-point
    # column's mirrored TPnn caption, which stands 1.1 mm left of that column
    # and is the widest thing on the back between the two.  The land is
    # 7.5 mm wide and the six QSPI pads span 2.0 mm, so the pad row still
    # sits over the socket with room to spare - the island, not the QFN, is
    # what bounds this.
    # y: courtyard 1.05 mm below the QSPI pad row.  Front and back courtyards
    # may overlap, but keeping the socket off the package keeps the back
    # readable and every QSPI via reachable.
    x_max = isl_x + TP_GRID_X[0] - 1.1 - B.text_extent("TP10", SILK_TEXT)[0] \
        - 0.45
    u24 = B.anchor("U24", 0, ("cymax", min(qx + 3.75, x_max)),
                   ("cymax", qy - 1.05))
    # The two bypass caps in a row directly under the socket (u24 is its
    # courtyard rect, so this is solved from the land, not from a table), on
    # its RIGHT half: J4's four through-hole shield pegs and its two USB
    # mounting holes come through to B.Cu under the bottom-left of the board,
    # and the caps' own mirrored captions hang below them.
    ucx = (u24[0] + u24[2]) / 2.0
    for ref, dx in (("C62", 0.55), ("C63", 2.95)):
        B.place(ref, ucx + dx, u24[1] - 0.75, 0)

    # ---- TP1-TP10 -------------------------------------------------------
    # A fixed 2 x 5 grid under the sensor island.  owner = the sensor whose
    # net this pad carries (the three shared bus nets touch all three, and
    # those go to the IMU); each pad then takes the free slot NEAREST its
    # owner, so the six IMU pads fill the middle of the grid and the
    # barometer's and the high-g part's take the ends.  check_rules() still
    # holds every one within TP_NEAR_MM of a sensor.
    tps = sorted((r for r in B.fps if TEST_POINTS.match(r)),
                 key=lambda r: int(r[2:]))
    own_of = {}
    for ref in tps:
        owner = SENSORS[0]
        for net, nodes in B.nets:
            if (ref, "1") in nodes:
                own = [s for s in SENSORS if any(n == s for n, _ in nodes)]
                if len(own) == 1:
                    owner = own[0]
                break
        own_of[ref] = owner
    slots = [(isl_x + sx, TP_GRID_Y - row * TP_GRID_DY)
             for row in range(5) for sx in TP_GRID_X]
    far = 0.0
    for ref in tps:
        if not slots:
            B.problems.append("testpoints: no back-side slot for %s" % ref)
            continue
        ox, oy = B.pos(own_of[ref])
        d, i = min((math.hypot(sx - ox, sy - oy), i)
                   for i, (sx, sy) in enumerate(slots))
        sx, sy = slots.pop(i)
        B.place(ref, sx, sy, 0)
        far = max(far, d)
    print("  back  %2d test points on a %.1f mm grid under the island, "
          "worst %.1f mm from its own sensor"
          % (len(tps), TP_GRID_DY, far))


def back_silk(B):
    """The B.SilkS legend: mirrored, so it reads from the back.

    Nothing is fixed up here.  The back carries bare pads only, so every band
    beside a pad is free by construction and the labels are simply drawn where
    they belong; check_silk() asserts they cleared the copper anyway.
    """
    # J3: the row is vertical against the LEFT edge, so each pad label sits
    # INBOARD (+x) of its pad, in the band nothing else on the back uses.
    B.back_pad_labels("J3", PAD_LABELS["J3"], 2.2, 0.0)
    jx, jy = B.pos("J3")
    # 10.6 mm out, not 9.6: the pad row's own silkscreen box reaches 9.3 mm
    # from the row centre along the row, and a label on it is a DRC
    # silk_overlap as well as unreadable.
    B.text("ESC", jx + 1.0, jy + 10.6, 0, size=0.9, thick=0.15, back=True)
    B.back_ref("J3", 1.0, -10.6)
    # J10: labels above the pads, rotated 90, as on the front
    B.back_pad_labels("J10", PAD_LABELS["J10"], 0.0, J10_LABEL_DY, 90)
    B.back_ref("J10", 0.0, 6.0)
    # U24, the OPTIONAL flash/PSRAM expansion: the legend is the whole point
    # of a DNP land - a bare SOIC-8 with no legend tells a user nothing about
    # what fits in it.  Three lines under the socket, mirrored like
    # everything else on the back, plus an explicit pin-1 marker beside pin 1
    # (the footprint's own pin-1 dot came round with the flip, but a DNP land
    # is hand-soldered, so the orientation is spelled out).
    if "U24" in B.fps:
        ux, uy = B.pos("U24")
        crt = dict(B.placed)["U24"]
        # The MPN line is split in two: the corridor ABOVE the socket - the
        # only clear one, J4's through-hole shield pegs owning the back of
        # the bottom edge and J3's label band the left - is 18 mm wide and
        # one line of both part numbers is 18.2 mm at the 0.6 mm DRC text
        # minimum.  Four short lines fit with margin; one long one does not.
        lines = ["FLASH", "SOIC-8"]
        w = max(B.text_extent(t, FLASH_LEGEND_SZ)[0] for t in lines)
        # centred over the socket, pulled left of the test-point column - of
        # its mirrored TPnn CAPTIONS, which stand 1.1 mm left of the pads and
        # reach further left than the pads do
        tp_left = (min(B.pos(r)[0] for r in B.back if TEST_POINTS.match(r))
                   - 1.1 - B.text_extent("TP10", SILK_TEXT)[0])
        lx = min(ux, tp_left - 0.6 - w / 2.0)
        for i, t in enumerate(lines):
            B.text(t, lx, crt[3] + 1.6 + (len(lines) - 1 - i)
                   * FLASH_LEGEND_DY, 0, size=FLASH_LEGEND_SZ,
                   thick=LABEL_THICK, back=True)
        # pin 1 is outboard on the row the flip put it on, so the marker goes
        # beside it in x, where nothing else on the back is
        p1x, p1y = B.pad_pos("U24", "1")
        B.text("1", p1x + math.copysign(1.9, p1x - ux), p1y, 0,
               size=FLASH_LEGEND_SZ, thick=LABEL_THICK, back=True)
        B.back_ref("U24", (crt[0] - ux) - 1.2, 0.0)
        # below their own pads: the socket is directly above them and J4's
        # shield pegs come through to the left
        for ref in ("C62", "C63"):
            B.back_ref(ref, 0.0,
                       -(B.text_extent(ref, SILK_TEXT)[1] / 2.0 + 0.7))
    # the test points: the reference IS the label.  The left column reads
    # outward to the left and the right column outward to the right, so no
    # label ever crosses the other column's pads.
    tps = sorted((r for r in B.back if TEST_POINTS.match(r)),
                 key=lambda r: int(r[2:]))
    if tps:
        right = max(B.pos(r)[0] for r in tps)
        for ref in tps:
            B.back_ref(ref, 1.1 if B.pos(ref)[0] > right - 0.01 else -1.1,
                       0.0)


def silkscreen(B):
    HX, HY = B.HX, B.HY
    B.text("MARV V2", -HX + 0.7, -HY + 1.3, 0, size=1.1, thick=0.18, just=-1)
    # The ESC row's and the DBG row's legends are on B.SilkS with their pads
    # (back_silk()).  What is left on the front is the IO block's row
    # captions, the board name and the reference designators.

    # RIGHT edge, the IO block.  Every ROW gets a two-line caption in the band
    # on the inner side of the block (see Builder.io_labels): the signal name
    # above the row centreline, the rail its power pin carries below it.  The
    # GND column needs no per-pin label (every pin of it is ground) and there
    # is no room for one anyway: 1.7 mm pads on a 2.54 mm grid leave 0.84 mm
    # between columns and 0.65 mm to the board edge.  It is bracketed with a
    # "G" at each end.  The vendored footprint has no silkscreen outline of its
    # own (it would eat the label band), so the board draws the end ticks here;
    # row 1's own caption already says which end pin 1 is at, so there is no
    # separate pin-1 dot to land on the pad's copper.
    #
    # EVERY ONE OF THESE LABELS IS FIXED (lead's decision B).  The old code
    # unpinned whichever captions reached a mounting hole's copper and let
    # silk_fix hunt them a spot; at the last board size that dropped A47 and a
    # 3V3 outright, and a dropped IO label is a mis-wired servo.  Now the band
    # is part of the envelope instead: floorplan() reserves exactly these
    # boxes so no part can be packed into them, check_silk() fails the build
    # if one of them lands on copper, a hole or the board edge, and the
    # board WIDTH is what has to give - which is what set BOARD_W.
    for s, lx, ly in B.io_labels():
        B.text(s, lx, ly, 0, size=IO_LABEL_SZ, just=1, pin=True)
    # the two end bands: the three reference designators above the top row and
    # the "G" of the GND column below the bottom one.  Fixed, like the rows -
    # the refdes is the real field, moved onto the band and pinned, not a copy
    # of its text, so pcbnew still shows J6/J7/J8 where the plot does.
    for s, lx, ly in B.io_end_labels():
        if s in IO_REFS:
            B.pin_ref(s, lx, ly)
        else:
            B.text(s, lx, ly, 0, size=IO_LABEL_SZ, thick=LABEL_THICK,
                   pin=True)
    sig = B.fps[IO_REFS[0]]
    xs = sorted({round(tomm(q.GetPosition().x), 3) - CX
                 for r in IO_REFS for q in B.fps[r].Pads()})
    ys = sorted({round(CY - tomm(q.GetPosition().y), 3) for q in sig.Pads()})
    for y in (ys[-1] + IO_END_TICK, ys[0] - IO_END_TICK):
        B.segment((xs[0] - 0.85, y), (xs[-1] + 0.85, y))


# --------------------------------------------------------------------------
# post-processing of the saved files
# --------------------------------------------------------------------------
def inject_stackup(path):
    txt = open(path).read()
    if "(stackup" in txt:
        txt = re.sub(r"\n\t\t\(stackup.*?\n\t\t\)", "", txt, flags=re.S)
    lines = ['\t\t(stackup',
             '\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))',
             '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))',
             '\t\t\t(layer "F.Mask" (type "Top Solder Mask") '
             '(thickness 0.01))']
    for name, typ, th, mat, er, lt in STACKUP:
        parts = ['(layer "%s"' % name, '(type "%s")' % typ,
                 '(thickness %s)' % th]
        if mat:
            parts.append('(material "%s")' % mat)
        if er:
            parts.append('(epsilon_r %s)' % er)
        if lt:
            parts.append('(loss_tangent %s)' % lt)
        lines.append('\t\t\t' + ' '.join(parts) + ')')
    lines += ['\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") '
              '(thickness 0.01))',
              '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))',
              '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))',
              '\t\t\t(copper_finish "ENIG")',
              '\t\t\t(dielectric_constraints no)',
              '\t\t)']
    block = "\n".join(lines)
    txt = txt.replace("\t(setup\n", "\t(setup\n" + block + "\n", 1)
    open(path, "w").write(txt)


def inject_netclass_patterns(path):
    d = json.load(open(path))
    pats = []
    for (name, tw, clr, vd, vdr, dpw, dpg, prio, nets) in NETCLASSES:
        for p in nets:
            pats.append({"netclass": name, "pattern": p})
    d.setdefault("net_settings", {})["netclass_patterns"] = pats
    json.dump(d, open(path, "w"), indent=2)


def board_has_foreign_copper(text):
    """True if a saved .kicad_pcb `text` has manual work the rebuild would
    discard: any top-level track/via/arc, or a top-level zone that is not
    one of ours.  Every zone add_zones() writes is named "gen:...", so a
    zone whose name is missing or does not start with "gen:" is someone's
    hand-drawn zone and still blocks the rebuild; ours never do."""
    if re.search(r"\n\t\((segment|via|arc)\b", text):
        return True
    for m in re.finditer(r"\n\t\(zone\b.*?\n\t\)\n", text, flags=re.S):
        nm = re.search(r'\(name "([^"]*)"\)', m.group(0))
        if not (nm and nm.group(1).startswith("gen:")):
            return True
    return False


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=float, default=BOARD_W)
    ap.add_argument("--height", type=float, default=BOARD_H)
    ap.add_argument("--netlist", default=NETLIST)
    ap.add_argument("--no-netlist", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if not a.no_netlist:
        export_netlist(a.netlist)
    comps, nets = read_netlist(a.netlist)
    pinfunc = read_pinfunctions(a.netlist)
    print("netlist: %d components, %d nets" % (len(comps), len(nets)))

    if os.path.exists(BOARD) and not a.dry_run:
        old = open(BOARD).read()
        # top-level (board) tracks/zones only - footprints carry keepouts.
        # Our own "gen:*" zones (see add_zones()) do not count: every run
        # regenerates them, so they must not block the next run.
        if board_has_foreign_copper(old) and not a.force:
            raise SystemExit("%s already has tracks/zones; re-running would "
                             "discard them.  Use --force." % BOARD)
        bdir = os.path.join(PRJ, "backups")
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(BOARD, os.path.join(bdir, "MARV-V2.kicad_pcb.prev"))

    B = Builder(a.width, a.height)
    B.setup_layers()
    B.setup_netclasses()
    B.load_components(comps, nets)
    B.pinfunc = pinfunc
    floorplan(B, comps)
    silkscreen(B)
    back_silk(B)
    B.silk_fix()
    B.draw_outline()
    B.add_zones()

    seen = [r for r, _ in B.placed]
    dup = sorted({r for r in seen if seen.count(r) > 1})
    miss = sorted(set(B.fps) - set(seen))
    if dup:
        B.problems.append("placed more than once: %s" % ",".join(dup))
    if miss:
        B.problems.append("never placed: %s" % ",".join(miss))

    print("placement:")
    B.report_area()
    errs = B.check()
    for p in B.problems:
        print("  FIT:  " + p)
    for e in errs:
        print("  CHK:  " + e)
    for n in B.notes:
        print("  NOTE: " + n)
    print("  %d fit problems, %d geometry problems" % (len(B.problems),
                                                       len(errs)))
    if a.dry_run:
        return 1 if (B.problems or errs) else 0

    pcbnew.SaveBoard(BOARD, B.board)
    inject_stackup(BOARD)
    inject_netclass_patterns(PRO)
    print("wrote %s and board settings in %s" % (BOARD, PRO))
    return 1 if (B.problems or errs) else 0


if __name__ == "__main__":
    sys.exit(main())
