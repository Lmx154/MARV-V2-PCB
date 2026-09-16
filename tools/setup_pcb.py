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
    python3 tools/setup_pcb.py --size 54       # try another square board size
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
DEF_SIZE = 50.0          # square board, mm (see --size)
CORNER_R = 2.0           # Edge.Cuts corner radius, mm
MOUNT = 15.25            # mounting hole centres at (+-MOUNT, +-MOUNT)
MOUNT_KEEPOUT_R = 4.0    # grommet flange courtyard radius of the H* footprint
EDGE_COPPER = 0.3        # copper-to-edge design rule, mm
PAD_EDGE_INSET = 0.5     # pad outer edge this far in from Edge.Cuts
BOARD_THICKNESS = 1.6

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
    ("USB",       0.30, 0.20, 0.60, 0.30, 0.30, 0.20, 20,
     ["USB_DP", "USB_DM", "USB_DP_MCU", "USB_DM_MCU", "USB_DP_RP",
      "USB_DM_RP"]),
    # PWM_ESC covers both actuator groups: PWM1-4 leave on the J3 ESC pad row,
    # PWM5-8 on the J12 servo header.  Same 3.3 V logic edges into the same
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
REF_ON_SILK = ("J3", "J4", "J6", "J7", "J9", "J10", "J11", "J12", "J13",
               "J14", "J15", "J16", "SW1", "SW2")

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

SILK_TEXT = 0.8          # refdes height, mm
SILK_THICK = 0.12
LABEL_TEXT = 0.7         # per-pad label height, mm
LABEL_SMALL = 0.65       # tight blocks (J16)
LABEL_THICK = 0.12

# J12/J13/J14 form a 3x4 servo block on a 2.54 mm grid; the stock courtyard
# (+-1.815 mm across the row) would overlap the neighbouring row, so a copy
# with the courtyard trimmed to half the row pitch is vendored into
# MARV_Packages and used for those three rows.  The schematic names the same
# footprint (tools/build_power.py), so SERVO_FP below is only the guarantee
# that the file exists and stays in sync with SERVO_CRTYD; load_components()
# checks the netlist agrees rather than silently overriding it.
SERVO_SRC = ("/usr/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty/"
             "PinHeader_1x04_P2.54mm_Vertical.kicad_mod")
SERVO_FP = "PinHeader_1x04_P2.54mm_Vertical_ServoRow"
SERVO_REFS = ("J12", "J13", "J14")
SERVO_CRTYD = (-1.2, -1.815, 1.2, 9.435)

# per-pad silkscreen labels: ref -> {pad number: label}
PAD_LABELS = {
    "J3":  ["CURR", "TX", "M4", "M3", "M2", "M1", "VBAT", "GND"],
    "J6":  ["VCC", "TX", "RX", "GND"],
    "J7":  ["VCC", "TX", "RX", "GND"],
    "J9":  ["VCC", "SCL", "SDA", "GND"],
    "J10": ["SWCLK", "SWDIO", "GND"],
    "J15": ["5V", "BZ-"],
    "J12": ["S5", "S6", "S7", "S8"],
    "J16": ["3V3", "GND", "IO1", "IO21", "IO27", "IO31",
            "A43", "A44", "A45", "A46", "A47", "GND"],
}
# whole-row labels (ref, text) placed at the row end instead of per pad
ROW_LABELS = {"J13": "5V", "J14": "GND"}


def vendor_servo_footprint():
    """write MARV_Packages/<SERVO_FP>: the stock 1x04 header with its
    courtyard trimmed so three rows can abut on the 2.54 mm grid."""
    txt = open(SERVO_SRC).read()
    txt = re.sub(r'\(footprint "[^"]+"', '(footprint "%s"' % SERVO_FP, txt, 1)
    txt = re.sub(r'\(descr "[^"]*"',
                 '(descr "Through hole straight pin header, 1x04, 2.54mm '
                 'pitch, single row -- MARV V2 copy with the courtyard '
                 'trimmed to +-1.2 mm across the row so the J12/J13/J14 servo '
                 'block can abut on the 2.54 mm grid; the silkscreen outline is '
                 'drawn around the whole block at board level instead. Pads '
                 'and fabrication layer are unchanged."', txt, 1)
    def drop_courtyard(m):
        # the three rows abut, so their own courtyard and silk outlines would
        # overlap: both are replaced (courtyard by the rectangle below, silk
        # by a board level outline around the whole 3x4 block)
        return "" if ('F.CrtYd' in m.group(0)
                      or 'F.SilkS' in m.group(0)) else m.group(0)
    txt = re.sub(r"\n\t\(fp_\w+\n.*?\n\t\)", drop_courtyard, txt,
                 flags=re.S)
    x0, y0, x1, y1 = SERVO_CRTYD
    rect = ('\n\t(fp_rect\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n'
            '\t\t\t(width 0.05)\n\t\t\t(type solid)\n\t\t)\n\t\t(fill no)\n'
            '\t\t(layer "F.CrtYd")\n\t)' % (x0, y0, x1, y1))
    i = txt.rindex("\n\t(pad ")
    txt = txt[:i] + rect + txt[i:]
    out = os.path.join(PRJ, "MARV_Packages.pretty", SERVO_FP + ".kicad_mod")
    old = open(out).read() if os.path.exists(out) else None
    if old != txt:
        open(out, "w").write(txt)
    return "MARV_Packages:" + SERVO_FP


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
    relative to the footprint origin."""

    def __init__(self, fp):
        org = fp.GetPosition()
        cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
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
    def __init__(self, size):
        self.H = size / 2.0
        self.board = pcbnew.CreateEmptyBoard()
        self.fps = {}
        self.geom = {}
        self.placed = []        # (ref, courtyard rect in board coords)
        self.texts = []         # board level silkscreen text
        self.problems = []
        self.notes = []

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
        servo = vendor_servo_footprint()
        for ref in sorted(comps):
            c = comps[ref]
            fpid = c["fp"]
            if ref in SERVO_REFS and fpid != servo:
                raise SystemExit("%s: schematic says %s, the board needs the "
                                 "courtyard-trimmed %s" % (ref, fpid, servo))
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
            fp.SetPosition(to_kicad(0, -self.H - 40))       # parked
            ref_fld = fp.Reference()
            ref_fld.SetLayer(pcbnew.F_SilkS)
            ref_fld.SetVisible(ref in REF_ON_SILK)
            ref_fld.SetTextSize(pcbnew.VECTOR2I(mm(SILK_TEXT), mm(SILK_TEXT)))
            ref_fld.SetTextThickness(mm(SILK_THICK))
            fp.Value().SetVisible(False)
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
        H = self.H
        self.gn = int(round(2 * H / self.CELL))
        self.occ = np.zeros((self.gn, self.gn), dtype=bool)
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

    def _idx(self, v):
        return int(math.floor((v + self.H) / self.CELL))

    def block_rect(self, rect, grow):
        i0 = max(self._idx(rect[0] - grow), 0)
        i1 = min(self._idx(rect[2] + grow) + 1, self.gn)
        j0 = max(self._idx(rect[1] - grow), 0)
        j1 = min(self._idx(rect[3] + grow) + 1, self.gn)
        self.occ[i0:i1, j0:j1] = True

    def block_circle(self, cx, cy, r):
        i = (np.arange(self.gn) + 0.5) * self.CELL - self.H
        xx, yy = np.meshgrid(i, i, indexing="ij")
        self.occ |= ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r

    def free(self, rect):
        i0 = self._idx(rect[0])
        i1 = self._idx(rect[2]) + 1
        j0 = self._idx(rect[1])
        j1 = self._idx(rect[3]) + 1
        if i0 < 0 or j0 < 0 or i1 > self.gn or j1 > self.gn:
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
            lim_x = self.H - EDGE_COPPER - pw / 2.0 - 0.05
            lim_y = self.H - EDGE_COPPER - ph / 2.0 - 0.05
            # candidate courtyard centres, spiral out from the seed
            for rad in np.arange(0.0, 2.2 * self.H, step):
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
                self.place(ref, -self.H + 4,
                           -self.H - 25 - 4 * len(self.problems), 0)
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
                self.place(r, -self.H + 4, -self.H - 25 - 4 * len(self.problems), 0)
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
        H, r = self.H, CORNER_R
        segs = [((-H + r, -H), (H - r, -H)), ((H, -H + r), (H, H - r)),
                ((H - r, H), (-H + r, H)), ((-H, H - r), (-H, -H + r))]
        for a, b in segs:
            s = pcbnew.PCB_SHAPE(self.board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(to_kicad(*a))
            s.SetEnd(to_kicad(*b))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(mm(0.1))
            self.board.Add(s)
        k = r * (1 - math.sqrt(0.5))
        corners = [((H - r, -H), (H, -H + r), (H - r, -H + r)),
                   ((H, H - r), (H - r, H), (H - r, H - r)),
                   ((-H + r, H), (-H, H - r), (-H + r, H - r)),
                   ((-H, -H + r), (-H + r, -H), (-H + r, -H + r))]
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
             layer=None, just=0):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        t.SetLayer(pcbnew.F_SilkS if layer is None else layer)
        t.SetPosition(to_kicad(x, y))
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(thick))
        t.SetTextAngleDegrees(rot)
        if just:
            t.SetHorizJustify(just)
        self.board.Add(t)
        self.texts.append(t)
        return t

    def pad_labels(self, ref, labels, dx, dy, rot, just=0):
        """put one silk label per pad, offset (dx, dy) from the pad centre."""
        fp = self.fps[ref]
        org = fp.GetPosition()
        for pad in fp.Pads():
            num = pad.GetNumber()
            try:
                idx = int(num) - 1
            except ValueError:
                continue
            if idx < 0 or idx >= len(labels):
                continue
            p = pad.GetPosition()
            x = tomm(p.x) - CX
            y = CY - tomm(p.y)
            self.text(labels[idx], x + dx, y + dy, rot, just=just)

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

        items = [(t, None) for t in self.texts]
        for ref in REF_ON_SILK:
            fp = self.fps.get(ref)
            if fp is not None and fp.Reference().IsVisible():
                items.append((fp.Reference(), ref))
        done = []
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
        H, cr = self.H - 0.2, CORNER_R
        if not (-H <= r[0] and r[2] <= H and -H <= r[1] and r[3] <= H):
            return False
        for cx, cy in ((H - cr, H - cr), (H - cr, -H + cr),
                       (-H + cr, H - cr), (-H + cr, -H + cr)):
            px = max(min(r[0], r[2], key=abs), 0) if False else None
        for x in (r[0], r[2]):
            for y in (r[1], r[3]):
                if abs(x) > H - cr and abs(y) > H - cr:
                    dx = abs(x) - (H - cr)
                    dy = abs(y) - (H - cr)
                    if dx * dx + dy * dy > cr * cr:
                        return False
        return True

    # ---------------- checks ----------------
    def check(self):
        out = []
        n = len(self.placed)
        holes = {"H1", "H2", "H3", "H4"}
        for ref in holes & set(self.fps):
            x, y = self.pos(ref)
            for rj, aj in self.placed:
                if rj in holes:
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
                if bbox_overlap(ai, aj, gap=0.001):
                    ox = min(ai[2], aj[2]) - max(ai[0], aj[0])
                    oy = min(ai[3], aj[3]) - max(ai[1], aj[1])
                    out.append("courtyard overlap %s/%s by %.2f x %.2f mm"
                               % (ri, rj, ox, oy))
        # copper to board edge
        H = self.H
        for ref, fp in self.fps.items():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                l, r = tomm(bb.GetLeft()) - CX, tomm(bb.GetRight()) - CX
                t, b = CY - tomm(bb.GetTop()), CY - tomm(bb.GetBottom())
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    continue
                m = min(H - r, l + H, H - t, b + H)
                if m < EDGE_COPPER:
                    out.append("copper-to-edge %s pad %s: %.2f mm"
                               % (ref, pad.GetNumber(), m))
        out += self.check_rules()
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
        return out

    def report_area(self):
        tot = 0.0
        for ref, rect in self.placed:
            tot += (rect[2] - rect[0]) * (rect[3] - rect[1])
        print("  board %.0f x %.0f mm = %.0f mm2, courtyard sum %.0f mm2 "
              "(%.1f %% fill)" % (2 * self.H, 2 * self.H, 4 * self.H * self.H,
                                  tot, 100 * tot / (4 * self.H * self.H)))


# --------------------------------------------------------------------------
# the actual floorplan
# --------------------------------------------------------------------------
def floorplan(B, comps):
    H = B.H
    E = H - PAD_EDGE_INSET          # SMD pad outer edge line
    TH = H - 0.4 - 0.85             # THT pad centre limit (1.7 mm pad)

    # ---------------- mounting holes ----------------
    for ref, sx, sy in (("H1", -1, 1), ("H2", 1, 1), ("H3", 1, -1),
                        ("H4", -1, -1)):
        B.place(ref, sx * MOUNT, sy * MOUNT, 0)
        B.fps[ref].SetLocked(True)

    # ---------------- BOTTOM edge ----------------
    # J3: ESC pad row, pin 1 (CURR) to the left, pads 0.5 mm in from the edge
    B.anchor("J3", 0, ("padc", -9.0), ("padmin", -E))
    # servo block: three 1x4 rows on a 2.54 mm grid (vendored footprint with
    # a trimmed courtyard, see vendor_servo_footprint)
    servo_x = 5.6
    B.anchor("J14", 90, ("padc", servo_x), ("padc", -TH))            # GND
    B.anchor("J13", 90, ("padc", servo_x), ("padc", -TH + 2.54))     # 5 V
    B.anchor("J12", 90, ("padc", servo_x), ("padc", -TH + 5.08))     # signal

    # ---------------- LEFT edge ----------------
    # 1x4 pad rows, pin 1 (VCC) at the top of each row
    for ref, y in (("J6", 12.0), ("J7", 0.6), ("J9", -10.8)):
        B.anchor(ref, 270, ("padmin", -E), ("padc", y))

    # ---------------- RIGHT edge ----------------
    # microSD: card opening towards +X, contacts 0.3 mm in from the edge
    B.anchor("J11", 270, ("padmax", H - EDGE_COPPER - 0.1),
             ("cymax", MOUNT - MOUNT_KEEPOUT_R - 0.35))
    j11 = dict(B.placed)["J11"]
    # spare IO 2x6, rotated so the 6 pin direction runs along X
    B.anchor("J16", 90, ("padmax", E), ("cymax", j11[1] - 0.7))
    j16 = dict(B.placed)["J16"]

    # ---------------- TOP edge ----------------
    B.anchor("J4", 180, ("org", 0.0), ("org", H - 3.65))   # USB-C, face flush
    B.anchor("SW1", 0, ("org", -8.6), ("cymax", H - 0.1))  # RESET
    B.anchor("SW2", 0, ("org", 8.6), ("cymax", H - 0.1))   # BOOTSEL
    B.anchor("J10", 0, ("padc", -H + 9.5), ("padmax", E))  # DBG
    B.anchor("J15", 0, ("padc", H - 9.0), ("padmax", E))   # buzzer
    B.place("D20", 8.6, H - 7.2, 0)                        # RGB LED

    # ---------------- fixed interior ----------------
    B.place("U20", 0.0, 0.0, 0)                            # RP2354B
    # crystal tight to XIN/XOUT (QFN pins 30/31, bottom centre at rot 0)
    B.place("Y1", 0.0, -7.9, 0)
    B.place("C46", -3.0, -7.9, 90)
    B.place("C47", 3.0, -7.9, 90)
    B.place("R21", 0.0, -10.5, 0)

    # The two switchers are anchored rather than packed: their loop geometry
    # is a circuit requirement (CAP_NEAR), and below ~54 mm the four Ø8 mm
    # grommet keepouts break the interior into strips too narrow for the
    # packer to discover a sane switcher block on its own.
    #   U26 + L3 go in the bottom pocket between the H4 keepout and the servo
    #   block, next to the J3 VBAT pad (DESIGN_SPEC "Edge allocation"), L3
    #   above U26 on its SW side.
    #   U7 + L2 go one step further from the ESC row in the left column, with
    #   L2 to the *left* of U7 because the TPS62913's SW (pad 2) and VO
    #   (pad 3) are both on that side of the RPU package.
    B.place("U26", -8.5, -H + 8.2, 0)
    B.place("L3", -8.5, -H + 13.2, 0)
    l2x = -H + 8.6
    B.place("L2", l2x, -7.2, 0)
    B.place("U7", l2x + 4.5, -7.2, 0)

    j12 = dict(B.placed)["J12"]

    # ---------------- reserved bands (silk pad labels) ----------------
    reserved = [
        (-18.5, -H + 3.4, -0.5, -H + 6.2),          # J3 labels
        (-H + 3.4, 8.0, -H + 5.9, 16.0),            # J6 labels
        (-H + 3.4, -3.4, -H + 5.9, 4.6),            # J7 labels
        (-H + 3.4, -14.8, -H + 5.9, -6.8),          # J9 labels
        (-H + 4.5, H - 6.2, -H + 14.5, H - 3.4),    # J10 labels
        (H - 14.5, H - 6.2, H - 4.5, H - 3.4),      # J15 labels
        (-0.5, j12[3] - 0.1, 12.0, j12[3] + 3.0),   # servo signal row labels
        (10.5, j16[1] - 3.8, H - 1.0, j16[1] - 0.2),  # J16 pin labels
        (11.3, -H + 0.5, 14.5, -H + 5.5),           # J13/J14 row labels
        (-H + 2.8, -H + 1.5, -H + 10.2, -H + 5.4),  # board name / ESC label
    ]
    B.build_grid(reserved)

    # ---------------- switcher loops ----------------
    # Packed before every other group so the loop components get the space
    # next to their regulator.  (part, the already placed part whose pad seeds
    # it, pad number): input caps on the VIN pin, output caps on the inductor's
    # output pad, the post-bead caps on the bead's output pad.
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
    # U26 first: its pocket (between the H4 grommet keepout, the J3 label band
    # and the servo block) is the tightest space on the board, and three 22 uF
    # 1206 output caps have to fit in it.
    B.power_loop("buck5", buck_loop, B.halo(["U26", "L3"], 5.4))
    B.power_loop("u7", u7_loop, B.halo(["U7", "L2"], 4.8))
    loop_done = {r for r, _ in u7_loop + buck_loop}

    # ---------------- clusters ----------------
    # (refs, seed, bounding boxes the cluster may use)
    ring = [(-9.3, -9.8, 9.3, 9.8)]
    ring_w = [(-9.3, -9.8, -5.6, 9.8)]
    north = [(-9.2, 8.8, 10.5, H - 9.2)]
    north_w = [(-12.5, 8.8, -1.5, H - 9.2)]
    # the sensors keep IND_SENSOR_MM away from L2, which is at y = -6.5 in the
    # same column, so their region starts above it rather than at y = 1.2
    left_up = [(-H + 6.1, 4.0, -9.2, 19.5), (-H + 6.1, 19.5, -13.6, H - 3.4)]
    left_mid = [(-H + 6.1, -9.5, -9.2, 3.8)]
    left_lo = [(-H + 6.1, -H + 8.2, -9.2, -9.0)]
    south = [(-11.5, -H + 8.2, 11.2, -11.0)]
    south_e = south
    east = [(9.2, -2.2, j11[0] - 0.4, 11.0),
            (12.6, -H + 1.0, H - 1.5, -10.8),
            (9.2, -10.8, 12.4, -2.2)]
    groups = {
        "mcu_ring": (["C30", "C31", "C32", "C33", "C34", "C35", "C36", "C37",
                      "C38", "C39", "C40", "C41", "C42", "C43", "C44", "C45",
                      "C48", "C49", "C78", "R53", "L20", "R20", "R24",
                      "C22"],
                     (0.0, 0.0),
                     ring),
        "i2c":      (["R25", "R26"], (-11.0, -7.0), left_mid + left_lo),
        "flash":    (["U24", "C62", "C63", "R35"], (-1.0, 12.0), north),
        "usb":      (["U8", "R22", "R23", "R4", "R5", "C7"], (3.5, 15.5),
                     north),
        "led":      (["C79", "R55"], (7.0, H - 10.5),
                     [(3.0, 11.0, 12.0, H - 5.0)]),
        # the buzzer driver follows J15 on the top edge, but below ~54 mm the
        # H2 grommet keepout takes the whole top right corner, so the region
        # reaches down past it to the strip above the microSD socket
        "buzz":     (["Q20", "D22", "R33", "R34"], (H - 9.0, H - 9.5),
                     [(10.5, 6.0, H - 1.5, H - 3.6)]),
        "sd_byp":   (["C64", "C65", "C66"], (12.4, 4.0), east[:1] + east[2:]),
        "sd_pu":    (["R36", "R37", "R38", "R39", "R40", "R41"],
                     (14.5, -13.0), east[1:] + east[:1]),
        "adc_div":  (["R27", "R28", "R29", "R30"], (8.5, -12.0),
                     [(5.5, -19.0, 12.2, -2.2)]),
        "buck5":    (["R54"], (-6.0, -H + 10.0), south),
        "mux":      (["U25", "C70", "C71", "C72", "R42", "R43", "R44", "R45",
                      "R46", "R47"], (-13.0, -2.0),
                     left_mid + ring_w + left_lo),
        # the analog island: the three MEMS sensors, their decoupling and the
        # LDO that feeds them (DESIGN_SPEC: "U12 and the sensors on the
        # ground-referenced analog island"), kept IND_SENSOR_MM clear of L2/L3
        "sens":     (["U21", "U22", "U23", "U12", "C25", "C26", "C50", "C51",
                      "C52", "C53", "C54", "C55", "C56", "C57", "C58", "C59",
                      "C60", "C61", "R48", "R50", "R51"],
                     (-15.0, 7.0), left_up + north_w),
        "u7":       (["R10"], (-9.0, -3.0), left_mid + ring),
        "v5bulk":   (["C19", "C20", "C21"], (8.5, -H + 10.0),
                     south + east[1:]),
    }
    # anything the schematic gained since this table was written follows the
    # cluster its net neighbours are in
    assigned = {r: g for g, (refs, _, _) in groups.items() for r in refs}
    assigned.update({r: "u7" for r, _ in u7_loop})
    assigned.update({r: "buck5" for r, _ in buck_loop})
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
        for nm, rects in (("ring", ring), ("north", north),
                          ("left_up", left_up), ("left_lo", left_lo),
                          ("south", south), ("south_e", south_e),
                          ("east", east)):
            tot = fr = 0.0
            for r in rects:
                i0, i1 = B._idx(r[0]), B._idx(r[2])
                j0, j1 = B._idx(r[1]), B._idx(r[3])
                sub = B.occ[i0:i1, j0:j1]
                tot += sub.size * B.CELL ** 2
                fr += (~sub).sum() * B.CELL ** 2
            print("  region %-8s %6.0f mm2 total, %6.0f mm2 free"
                  % (nm, tot, fr))

    # order matters: the groups that have only one place to go come first
    order = ["mcu_ring", "sens", "flash", "usb", "mux", "i2c",
             "buck5", "u7", "v5bulk", "adc_div", "led", "buzz",
             "sd_byp", "sd_pu"]
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
                    B.place(r, -B.H + 4, -B.H - 30, 0)
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
                              ("left_up", left_up), ("left_lo", left_lo),
                              ("south", south), ("south_e", south_e),
                              ("east", east)):
                f = 0.0
                for r in rects:
                    sub = B.occ[B._idx(r[0]):B._idx(r[2]),
                                B._idx(r[1]):B._idx(r[3])]
                    f += (~sub).sum() * B.CELL ** 2
                fr[nm] = f
            print("      free after %-8s %s" % (name, " ".join(
                "%s=%.0f" % (k, v) for k, v in fr.items())))
        if os.environ.get("SETUP_PCB_MAP") == name:
            step = 4
            for j in range(B.gn - 1, -1, -step):
                row = ""
                for i in range(0, B.gn, step):
                    row += "#" if B.occ[i:i + step, j - step + 1:j + 1].any() \
                        else "."
                print("   |" + row)


def silkscreen(B):
    H = B.H
    E = H - PAD_EDGE_INSET
    B.text("MARV V2", -H + 6.5, -H + 2.4, 0, size=1.2, thick=0.2)
    B.text("ESC", -H + 6.5, -H + 4.6, 0, size=1.0, thick=0.15)
    # bottom edge: labels above the pads, rotated 90 deg
    B.pad_labels("J3", PAD_LABELS["J3"], 0.0, 2.9, 90)
    B.pad_labels("J12", PAD_LABELS["J12"], 0.0, 2.2, 0)
    # outline around the 3x4 servo block (open at the board edge side)
    rs = [r for ref, r in B.placed if ref in ("J12", "J13", "J14")]
    x0 = min(r[0] for r in rs) - 0.3
    x1 = max(r[2] for r in rs) + 0.3
    y1 = max(r[3] for r in rs) + 0.3
    y0 = -H + 0.45
    for a, b in (((x0, y0), (x0, y1)), ((x0, y1), (x1, y1)),
                 ((x1, y1), (x1, y0))):
        ln = pcbnew.PCB_SHAPE(B.board)
        ln.SetShape(pcbnew.SHAPE_T_SEGMENT)
        ln.SetStart(to_kicad(*a))
        ln.SetEnd(to_kicad(*b))
        ln.SetLayer(pcbnew.F_SilkS)
        ln.SetWidth(mm(0.12))
        B.board.Add(ln)
    for ref in ("J13", "J14"):
        fp = B.fps[ref]
        pads = sorted(fp.Pads(), key=lambda p: p.GetPosition().x)
        p = pads[-1].GetPosition()
        B.text(ROW_LABELS[ref], tomm(p.x) - CX + 1.6, CY - tomm(p.y), 0,
               just=-1)
    # left edge: labels to the right of the pads
    for ref in ("J6", "J7", "J9"):
        B.pad_labels(ref, PAD_LABELS[ref], 1.6, 0.0, 0, just=-1)
    # top edge: labels below the pads
    B.pad_labels("J10", PAD_LABELS["J10"], 0.0, -2.9, 90)
    B.pad_labels("J15", PAD_LABELS["J15"], 0.0, -2.4, 90)
    # right edge: spare IO block - 12 pins on a 2.54 mm grid leave no room
    # between the pads, so the labels go in two rows under the block, the
    # nearer row belonging to the nearer pin row
    fp = B.fps["J16"]
    pads = list(fp.Pads())
    ys = sorted({round(tomm(p.GetPosition().y), 2) for p in pads})
    block = min(r[1] for ref, r in B.placed if ref == "J16")
    for pad in pads:
        idx = int(pad.GetNumber()) - 1
        px = tomm(pad.GetPosition().x) - CX
        py = round(tomm(pad.GetPosition().y), 2)
        row = 0 if py == ys[-1] else 1      # ys[-1] = lowest on the board
        B.text(PAD_LABELS["J16"][idx], px - 1.3, block - 1.3 - 1.5 * row, 0,
               size=LABEL_SMALL)


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
    ap.add_argument("--size", type=float, default=DEF_SIZE)
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

    B = Builder(a.size)
    B.setup_layers()
    B.setup_netclasses()
    B.load_components(comps, nets)
    floorplan(B, comps)
    silkscreen(B)
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
