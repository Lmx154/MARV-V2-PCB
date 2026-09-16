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
# every back-side part gets a visible reference on B.SilkS: nothing else is
# there to collide with, and a bare pad with no legend is unusable on a bench.
BACK_REF_SILK = True
# J3, the ESC row: VERTICAL, pad 1 (CURR) at the top, its centre this far in
# from the LEFT edge - between U26 and L3 on the
# front, so the VBAT pad lands under the buck's own input and the four PWM
# pads point at the MCU.  Rotation 270 is what puts pad 1 at the top of a
# flipped row; check_back() asserts it, because the flip mirrors the
# footprint and a wrong rotation silently reverses the harness order.
ESC_BACK_X = 9.35
ESC_BACK_Y = 0.0
ESC_BACK_ROT = 270
# TP1-TP10: two columns this far right of the sensor island's left edge, on a
# 2.4 mm grid (1 x 1 mm pads, 2 x 2 mm courtyards), five rows from TP_GRID_Y
# downward - directly under U21/U22/U23, so every via is the board thickness
# and nothing else.
J10_LABEL_DY = 3.3       # J10's captions stand this far above its pads
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
    ("Power",     0.50, 0.15, 0.80, 0.40, 0.50, 0.20, 10,
     ["VBAT", "5V_IN", "V5_SYS", "USB_VBUS", "V3V3_SYS", "V3V3_ANA",
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
    ("SensorSPI", 0.15, 0.15, 0.60, 0.30, 0.15, 0.15, 40,
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
        comps[ref] = dict(ref=ref, value=c.findtext("value") or "",
                          fp=c.findtext("footprint") or "",
                          path=tstamps + (c.findtext("tstamps") or ""))
    nets = []
    for n in root.find("nets").findall("net"):
        nodes = [(nd.get("ref"), nd.get("pin")) for nd in n.findall("node")]
        nets.append((n.get("name"), nodes))
    return comps, nets


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
            # THE BACK SIDE: flip here, before any geometry is measured, so
            # Geom reads B.CrtYd and every anchor, the packer and the checks
            # see the real back-side outline.  Flipping about the footprint's
            # own origin mirrors X *inside* the footprint and leaves the
            # placement to the tables below.
            if ref in BACK_PAD_ROWS or TEST_POINTS.match(ref):
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
        """occupancy grid of everything placed so far + reserved bands"""
        self.gnx = int(round(2 * self.HX / self.CELL))
        self.gny = int(round(2 * self.HY / self.CELL))
        self.occ = np.zeros((self.gnx, self.gny), dtype=bool)
        for ref, rect in self.placed:
            if ref.startswith("H") and ref[1:].isdigit():
                continue                       # circles, handled below
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

    def place_near(self, ref, seed, rots=(0, 90), step=0.25, gap=0.05,
                   bounds=None):
        """nearest free spot to seed (optionally inside `bounds`, a list of
        rectangles); returns the distance from the seed, or None"""
        best = None
        for rot in rots:
            g = self.g(ref, rot)
            cw = g.cy[2] - g.cy[0]
            ch = g.cy[3] - g.cy[1]
            pw = g.pad[2] - g.pad[0]
            ph = g.pad[3] - g.pad[1]
            lim_x = self.HX - EDGE_COPPER - pw / 2.0 - 0.05
            lim_y = self.HY - EDGE_COPPER - ph / 2.0 - 0.05
            # candidate courtyard centres, spiral out from the seed
            for rad in np.arange(0.0, 2.2 * max(self.HX, self.HY), step):
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
        if best is None:
            return None
        d, cx, cy, rot, cw, ch = best
        g = self.g(ref, rot)
        x = cx - (g.cy[0] + g.cy[2]) / 2.0
        y = cy - (g.cy[1] + g.cy[3]) / 2.0
        rect = self.place(ref, x, y, rot)
        self.block_rect(rect, 0.1)
        return d

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
        """The back side carries BARE PADS ONLY (lead's decision A).

        Three things are asserted here, because none of them is visible in a
        front-side courtyard check:
          1. exactly the allowed refs are flipped, and every one of them
             really is - a component that drifted to B.Cu breaks the
             single-sided-assembly rule the whole stack-up rests on;
          2. J3 pin 1 (CURR) is still the TOP pad of the vertical row - the
             flip mirrors the footprint, so a wrong rotation silently
             reverses the ESC harness order;
          3. back pads clear the grommets' O 5 mm *.Cu keepout zone and every
             front-side HOLE (the IO block's 42 through pins, the USB-C shield
             pegs, the NPTH mounting holes), which pass through to B.Cu.
        """
        out = []
        allowed = set(BACK_PAD_ROWS) | {r for r in self.fps
                                        if TEST_POINTS.match(r)}
        for ref, fp in sorted(self.fps.items()):
            if fp.IsFlipped() and ref not in allowed:
                out.append("%s is on the BACK; assembly is single sided "
                           "(front only)" % ref)
            if ref in allowed and not fp.IsFlipped():
                out.append("%s should be on the back and is not" % ref)
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
                   the IO block; U24 below the MCU; U7/L2/U12 above it;
                   U26/L3/U25/C19 in the left-centre pocket
      BACK         J3 (ESC row, vertical, CURR at the top) under the
                   left-centre power pocket, J10 (DBG) at the bottom right,
                   TP1-TP10 directly under the sensor island.  Bare pads only
                   - see back_side() and BACK_PAD_ROWS.
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
    # The bottom-edge group is anchored to the MCU, not to absolute x.  U24,
    # the flash socket, hangs off the MCU's QSPI edge directly above SW2, and
    # the MCU is pinned to the RIGHT board edge (see mcu_x); anchored to the
    # board centre - or worse, to the left edge - the two walk towards each
    # other as --width shrinks and the socket ends up inside the switch.
    # Tied to mcu_x the whole row keeps its spacing at any width, and the
    # width is taken out of the left-centre pocket, which is where the ESC
    # row's old margin went.  The offsets are the ones the 48.7 mm board had.
    B.anchor("J4", 0, ("org", mcu_x0 - 7.8), ("org", -HY + 3.65))  # USB-C
    j4 = dict(B.placed)["J4"]
    B.anchor("SW1", 0, ("cyc", mcu_x0 - 10.8), ("cymin", j4[3] + 0.4))  # RST
    B.anchor("SW2", 0, ("cyc", mcu_x0 - 5.0), ("cymin", j4[3] + 0.4))  # BOOT
    B.place("D20", mcu_x0 - 0.8, -HY + 2.2, 0)              # RGB LED
    B.place("C79", mcu_x0 - 0.8, -HY + 4.4, 0)  # WS2812 bypass, at the LED
    B.place("R55", mcu_x0 + 1.1, -HY + 4.4, 0)  # 100 R LED_DATA series R

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
    mcu_x, mcu_y = mcu_x0, 0.0
    mcu = B.place("U20", mcu_x, mcu_y, 180)
    # the crystal group is offset right of the QFN centre: at the centre its
    # left load cap runs into the microSD socket, whose own left edge is
    # already hard against the H1 grommet keepout, so on a narrower board the
    # socket is what sets it, not the QFN.
    xtal_x = max(mcu_x + 1.8, j11[2] + 3.9)
    B.place("Y1", xtal_x, 8.2, 0)               # crystal at XIN/XOUT
    B.place("C46", xtal_x - 3.0, 8.2, 90)
    B.place("C47", xtal_x + 3.0, 8.2, 90)
    B.place("R21", xtal_x, 10.7, 0)

    # The two switchers are anchored rather than packed: their loop geometry is
    # a circuit requirement (CAP_NEAR), and the grommet keepouts break the
    # interior into pockets too narrow for the packer to discover a sane
    # switcher block on its own.
    #   U26 + L3 (the VBAT buck) go in the left-centre pocket, which is now
    #   directly ABOVE the J3 VBAT pad: the row is on the back at
    #   (-HX + ESC_BACK_X, -5), so VBAT rises through the board into the buck.
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
    B.place("U26", -HX + POCKET_L + 5.95, buck_y, 0)
    B.place("L3", -HX + POCKET_L + 10.95, buck_y, 0)
    l2_x = max(mcu_x + 0.8, j11[2] + 2.6)
    B.place("L2", l2_x, HY - 3.6, 0)
    B.place("U7", l2_x + 4.5, HY - 3.6, 0)
    # U12, the analog LDO: above the MCU with the other 3.3 V regulators, but
    # at the right-hand end of that band so it is also next to the sensor
    # island it feeds.  Anchored because the U7 loop fills the band otherwise.
    B.place("U12", max(mcu_x + 8.4, xtal_x + 6.0), 10.0, 0)
    # U25, the priority mux, and C19, its 220 uF output bulk: anchored side by
    # side in the left-centre pocket, where VBAT and 5V_IN already are.
    B.place("U25", min(-HX + POCKET_L + 12.95, mcu[0] - 1.8),
            buck_y + 4.5, 0)
    # C19 is the 220 uF polymer: 8.9 x 4.9 mm of courtyard, the biggest
    # passive on the board.  Its ceiling is the microSD socket above it.  It
    # used to be nudged clear of the ESC row's silk labels; with J3 on the
    # back that band is gone and the cap sits hard against the left margin,
    # clear of the H1 flange keepout on its own courtyard.
    c19_y = j11[1] - 2.75
    B.place("C19", -HX + 5.05, c19_y, 0)
    # U8, the USB ESD array, sits beside the receptacle rather than being
    # packed: the two switches take the whole band above J4.
    B.place("U8", -HX + POCKET_L + 2.35, buck_y - 4.6, 0)
    # U24, the QSPI flash/PSRAM socket, is anchored for the same reason:
    # DESIGN_SPEC puts it "adjacent to the MCU's QSPI pads", which with U20 at
    # 180 deg is the bottom edge of the QFN.
    B.place("U24", mcu_x + 1.8, -10.2, 0)
    # THE SENSOR ISLAND is anchored, not packed.  The strip between the QFN and
    # the IO block's row-label band is 7.4 mm wide; packed from a seed the
    # three sensors scatter across it and leave slivers 1.9 mm wide, which is
    # 0.3 mm less than a 1 x 1 mm test pad needs - and TP1-TP10 have to land
    # within TP_NEAR_MM of the part they probe or they are stubs on a 10 MHz
    # bus.  Stacked against the MCU side of the strip they leave one clean
    # corridor down the block side for the pads and the gaps between them for
    # the decoupling.  Anchored BEFORE build_grid so the MCU decoupling, which
    # is packed first, packs around them.
    isl_x = mcu_x + 6.0                 # island left edge, 0.3 mm off the QFN
    B.place("U23", isl_x + 2.0, -8.5, 0)    # ADXL375, the tallest package
    B.place("U21", isl_x + 1.8, -3.0, 0)    # ICM-45686
    B.place("U22", isl_x + 1.25, 1.2, 0)    # BMP581

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
    # label bands went to the back with their pads, and the back is empty, so
    # what is left is the board name and the IO block's row captions.
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

    # ---------------- switcher loops ----------------
    u7_loop = [("C8", [("U7", "1"), ("U7", "7")]),
               ("C17", [("U7", "6"), ("U7", "7")]),
               ("FB1", [("L2", "2"), ("U7", "3")]),
               ("C10", [("L2", "2"), ("U7", "4")]),
               ("C11", [("L2", "2"), ("U7", "4")]),
               ("C12", [("L2", "2"), ("U7", "4")]),
               ("C23", [("FB1", "2"), ("U7", "4")]),
               ("C24", [("FB1", "2"), ("U7", "4")]),
               ("C9", [("U7", "6"), ("U7", "7")]),
               ("C13", [("U7", "8")]), ("R7", [("U7", "9")]),
               ("R8", [("U7", "9")]), ("R9", [("U7", "10")])]
    buck_loop = [("C74", [("U26", "3"), ("U26", "4")]),
                 ("C73", [("U26", "3"), ("U26", "4")]),
                 ("C76", [("L3", "2"), ("U26", "4")]),
                 ("C77", [("L3", "2"), ("U26", "4")]),
                 ("C80", [("L3", "2"), ("U26", "4")]),
                 ("C75", [("U26", "6")]), ("R52", [("U26", "2")])]
    B.power_loop("buck5", buck_loop, B.halo(["U26", "L3"], 5.4))
    B.power_loop("u7", u7_loop, B.halo(["U7", "L2"], 6.0))
    loop_done = {r for r, _ in u7_loop + buck_loop}

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
        "flash":    (["U24", "C62", "C63", "R35"], (mcu_x + 1.8, -14.5),
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
        "reg3v3":   (["U12", "C25", "C26", "R10"], (mcu_x + 8.4, 12.5),
                     north + ring),
        # C20/C21 are the V5_SYS local bulk "at the array" and C22 the
        # V3V3_SYS one: the array is the right edge now, so they belong in the
        # top band beside U12, not in the left pocket where the old left-edge
        # array put them.
        "v5bulk":   (["C19", "C20", "C21"], (mcu_x + 10.2, 10.0),
                     north + east + ring),
    }
    # anything the schematic gained since this table was written follows the
    # cluster its net neighbours are in
    assigned = {r: g for g, (refs, _, _) in groups.items() for r in refs}
    assigned.update({r: "u7" for r, _ in u7_loop})
    assigned.update({r: "buck5" for r, _ in buck_loop})
    groups["u7"] = ([], (6.1, 13.0), north)
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
        # the switcher loops and the anchored parts are already down
        refs = [r for r in refs if r not in loop_done and r not in fixed]
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
    """Place the three things that live on B.Cu: the ESC pad row J3, the DBG
    pad row J10 and the ten test points.  Bare pads, no components.

    Nothing here is packed.  The back is empty by construction, so each
    position is solved from the one obstacle that does reach through the
    board - the grommets' O 5 mm copper keepout and the front-side holes -
    and check_back() asserts the result rather than trusting it.
    """
    HX, HY = B.HX, B.HY

    # ---- J3, the ESC pad row -------------------------------------------
    # Under the left-centre power pocket (see ESC_BACK_*).  The row is 14 mm
    # of pads and the left grommets are 30.5 mm apart at x = -HX + 4.0, so it
    # clears both by more than 6 mm in x alone.
    B.place("J3", -HX + ESC_BACK_X, ESC_BACK_Y, ESC_BACK_ROT)

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
    # J3: the row is vertical, so each pad label sits INBOARD of its pad,
    # left aligned, in the band the row's own courtyard does not use.
    B.back_pad_labels("J3", PAD_LABELS["J3"], 2.2, 0.0)
    jx, jy = B.pos("J3")
    B.text("ESC", jx, jy + 10.6, 0, size=0.9, thick=0.15, back=True)
    B.back_ref("J3", 0.0, -10.6)
    # J10: labels above the pads, rotated 90, as on the front
    B.back_pad_labels("J10", PAD_LABELS["J10"], 0.0, J10_LABEL_DY, 90)
    B.back_ref("J10", 0.0, 6.0)
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
    print("netlist: %d components, %d nets" % (len(comps), len(nets)))

    if os.path.exists(BOARD) and not a.dry_run:
        old = open(BOARD).read()
        # top-level (board) tracks/zones only - footprints carry keepouts
        if (re.search(r"\n\t\((segment|via|arc|zone)\b", old)
                and not a.force):
            raise SystemExit("%s already has tracks/zones; re-running would "
                             "discard them.  Use --force." % BOARD)
        bdir = os.path.join(PRJ, "backups")
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(BOARD, os.path.join(bdir, "MARV-V2.kicad_pcb.prev"))

    B = Builder(a.width, a.height)
    B.setup_layers()
    B.setup_netclasses()
    B.load_components(comps, nets)
    floorplan(B, comps)
    silkscreen(B)
    back_silk(B)
    B.silk_fix()
    B.draw_outline()

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
