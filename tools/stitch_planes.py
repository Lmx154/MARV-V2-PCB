#!/usr/bin/env python3
"""stitch_planes.py - deterministic plane fanout for a KiCad board.

  python3 tools/stitch_planes.py BOARD [--out OUT] [--nets V3V3_ANA,V3V3_SYS,GND]
                                       [--report r.json] [--dry-run]

Every SMD pad on a plane net gets its own via down to the plane, placed here,
in KiCad, instead of by Freerouting.  Freerouting cannot place plane-connection
vias for this board (it left 43 V3V3_* connections dead in every late pass), so
the plane nets are fanned out first and then removed from the router's netlist
(see tools/route_board.py --exclude-nets): the pads are already on the plane
through these vias, and the router only sees signal nets.

--nets is a comma-separated list and IS ORDER-SIGNIFICANT: nets are stitched
in the order given, earlier nets claiming board space (vias, tracks) before
later ones look for it.  The default, V3V3_ANA,V3V3_SYS,GND, puts the two
tight power nets first and GND last: GND already owns the widest, least
constrained copper (In1 plus F.Cu/B.Cu), so giving it first pick starves the
V3V3_SYS pads that share the crowded U20 corridor with it (observed: 17
V3V3_SYS pads on U20 going unreachable, all "clearance conflict with an
already-placed GND stitch via/track", when GND ran first).

For each target pad:

  * one via of the pad net's *net class* size (via diameter / drill read from
    BOARD_DESIGN_SETTINGS.m_NetSettings.GetEffectiveNetClass(netname)), plus a
    track of the class track width from the pad centre to the via, on the pad's
    own copper layer;
  * candidate via positions are tried in the spec'd order - radially outward
    from the footprint's pad centroid through the pad, then the two tangential
    directions, then inward - each at distance
        support(pad, dir) + via_radius + clearance + 0.05 mm
    from the pad centre, then in +0.25 mm steps up to +1.5 mm (GND) or
    +2.5 mm (V3V3_SYS/V3V3_ANA only - see EXTENDED_MAX_EXTRA_NETS: those two
    nets' plane pours are the most keyholed/fragmented, so pads need a wider
    search before being called unreachable; --max-extra still raises the
    floor for every net, GND included, if passed larger);
  * a candidate is accepted when it is DRC-clean (see checks below) *and* it
    lands in copper of its own net on a layer other than the pad's, i.e. it
    actually reaches a plane.  A via that lands in a plane keyhole would be an
    isolated dangling via, so such pads are reported unreachable instead.

DRC-clean, checked against a uniform-grid index of all board copper:
  - via annulus vs. every other-net pad/track/via copper, at the larger of the
    two net classes' clearances (>= board min clearance);
  - via hole vs. other-net copper at min_hole_clearance, and hole-to-hole
    against every other hole on the board at min_hole_to_hole (+0.05 margin);
  - rule areas that disallow vias, if the board carries any (the grommet
    holes no longer do - they are grounded pad-and-via rings now) - the
    via disc must not intersect them - and rule areas that disallow tracks for
    the fanout track;
  - the board outline deflated by (radius + copper-to-edge clearance);
  - the fanout track vs. other-net copper on its own layer, same clearances.

Two same-net pads whose centres are within --share-dist (default 1.2 mm) share
one via when the second pad can reach the first pad's via with a clean track;
that is preferred over a second via (adjacent GND pads of two caps, etc.).

A large exposed pad (both sides >= --thermal-min, default 2.0 mm; on this board
exactly U20's pad 81) is not fanned out radially: it gets an array of vias on a
1.0 mm grid, drill 0.3 / diameter 0.6, entirely inside the pad shrunk by a
0.4 mm margin, and no tracks.

Everything created is SetLocked(True) so a later Specctra round-trip exports it
as `(type fix)` and KiCad's SES import will not delete it.  After placing,
BuildConnectivity() + ZONE_FILLER().Fill() run so the planes close around the
new vias, and the board is written to --out (--dry-run: no file is written).

Never modifies BOARD in place: the board is loaded, mutated in memory and saved
to --out (default: BOARD with a .stitched.kicad_pcb suffix).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict

import pcbnew

MM = 1000000.0

# V3V3_SYS and V3V3_ANA get a wider search radius than GND before a pad is
# called unreachable (see module docstring); GND keeps --max-extra (1.5 mm).
EXTENDED_MAX_EXTRA_MM = 2.5
EXTENDED_MAX_EXTRA_NETS = frozenset({"V3V3_SYS", "V3V3_ANA"})


def mm(v: float) -> int:
    return int(round(v * MM))


def to_mm(v: int) -> float:
    return v / MM


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def pad_support(pad, dx: float, dy: float) -> float:
    """Half-extent of the pad along the unit direction (dx, dy), in nm.

    Exact for rectangular pads (support function of a rotated rectangle) and
    for circles/ovals (support function of the bounding ellipse); a slight
    over-estimate for roundrect/chamfered pads, which only pushes the via
    outward by at most the corner radius -- the safe direction.
    """
    ang = pad.GetOrientation().AsRadians()
    ca, sa = math.cos(ang), math.sin(ang)
    # direction in the pad's local frame
    lx = dx * ca + dy * sa
    ly = -dx * sa + dy * ca
    hx = pad.GetSizeX() / 2.0
    hy = pad.GetSizeY() / 2.0
    shape = pad.GetShape(pad.GetPrincipalLayer()) if _PAD_SHAPE_TAKES_LAYER else pad.GetShape()
    if shape in (pcbnew.PAD_SHAPE_CIRCLE, pcbnew.PAD_SHAPE_OVAL):
        return math.hypot(hx * lx, hy * ly)
    return abs(hx * lx) + abs(hy * ly)


def _probe_pad_shape_signature() -> bool:
    b = pcbnew.BOARD()
    fp = pcbnew.FOOTPRINT(b)
    p = pcbnew.PAD(fp)
    try:
        p.GetShape()
        return False
    except TypeError:
        return True


_PAD_SHAPE_TAKES_LAYER = _probe_pad_shape_signature()


def copper_layers(item) -> list:
    ls = item.GetLayerSet()
    return [l for l in ls.CuStack()]


def hole_record(item):
    """(ax, ay, bx, by, radius) for a pad/via hole, or None.

    A drill is a SHAPE_SEGMENT (a point for round drills, a segment for slots);
    holes are compared numerically rather than through SHAPE::Collide because
    the SWIG wrapper only exposes Collide(SEG) on the concrete SHAPE_SEGMENT /
    SHAPE_CIRCLE classes -- the generic Collide(SHAPE) overload is reachable
    only from an opaque `SHAPE` handle such as GetEffectiveShape() returns.
    """
    try:
        hs = item.GetEffectiveHoleShape()
    except Exception:
        return None
    if hs is None:
        return None
    try:
        seg = hs.GetSeg()
        return (seg.A.x, seg.A.y, seg.B.x, seg.B.y, hs.GetWidth() // 2)
    except Exception:
        return None


def _pt_seg_dist2(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    l2 = vx * vx + vy * vy
    if l2 == 0:
        dx, dy = px - ax, py - ay
        return dx * dx + dy * dy
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return dx * dx + dy * dy


def seg_seg_dist(a, b):
    """Distance between two segments given as (ax, ay, bx, by)."""
    a0x, a0y, a1x, a1y = a
    b0x, b0y, b1x, b1y = b
    d = min(
        _pt_seg_dist2(a0x, a0y, b0x, b0y, b1x, b1y),
        _pt_seg_dist2(a1x, a1y, b0x, b0y, b1x, b1y),
        _pt_seg_dist2(b0x, b0y, a0x, a0y, a1x, a1y),
        _pt_seg_dist2(b1x, b1y, a0x, a0y, a1x, a1y),
    )
    return math.sqrt(d)


def bbox_of(shape_bbox, margin: int):
    return (
        shape_bbox.GetLeft() - margin,
        shape_bbox.GetTop() - margin,
        shape_bbox.GetRight() + margin,
        shape_bbox.GetBottom() + margin,
    )


class Grid:
    """Uniform-grid spatial index over axis-aligned boxes (nm)."""

    def __init__(self, cell: int = mm(1.0)):
        self.cell = cell
        self.cells = defaultdict(list)

    def _keys(self, box):
        x0, y0, x1, y1 = box
        for i in range(x0 // self.cell, x1 // self.cell + 1):
            for j in range(y0 // self.cell, y1 // self.cell + 1):
                yield (i, j)

    def add(self, box, obj):
        for k in self._keys(box):
            self.cells[k].append(obj)

    def query(self, box):
        seen = set()
        out = []
        for k in self._keys(box):
            for obj in self.cells.get(k, ()):
                if id(obj) not in seen:
                    seen.add(id(obj))
                    out.append(obj)
        return out


class Item:
    """A piece of board copper: shapes (one per copper layer it exists on),
    an optional hole, its net code and its copper layer set."""

    __slots__ = ("net", "layers", "shapes", "hole", "box", "desc")

    def __init__(self, net, layers, shapes, hole, box, desc):
        self.net = net
        self.layers = layers
        self.shapes = shapes
        self.hole = hole
        self.box = box
        self.desc = desc


# ---------------------------------------------------------------------------
# board model
# ---------------------------------------------------------------------------


class Stitcher:
    def __init__(self, board, args):
        self.board = board
        self.args = args
        self.ds = board.GetDesignSettings()
        self.ns = self.ds.m_NetSettings
        self.min_clearance = self.ds.m_MinClearance
        self.hole_clearance = getattr(self.ds, "m_HoleClearance", mm(0.25))
        self.hole_to_hole = self.ds.m_HoleToHoleMin
        self.edge_clearance = self.ds.m_CopperEdgeClearance
        self.eps = mm(0.005)

        self._class_cache = {}
        self.grid = Grid()
        self.items = []
        self.new_items = []
        self.keepout_vias = []
        self.keepout_tracks = []
        self.net_fill = {}       # netname -> {layer: SHAPE_POLY_SET}
        self.outline = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(self.outline, True)
        self._deflated = {}

        self._index_copper()
        self._index_keepouts()
        self._index_fills()

    # -- net class ---------------------------------------------------------
    def netclass(self, netname):
        if netname not in self._class_cache:
            self._class_cache[netname] = self.ns.GetEffectiveNetClass(netname)
        return self._class_cache[netname]

    def clearance_between(self, net_a, net_b):
        c = self.min_clearance
        for n in (net_a, net_b):
            if n:
                c = max(c, self.netclass(n).GetClearance())
        return c

    # -- indexing ----------------------------------------------------------
    def _add_item(self, item):
        self.items.append(item)
        self.grid.add(item.box, item)

    def _index_copper(self):
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                layers = copper_layers(pad)
                hole = hole_record(pad) if pad.GetDrillSizeX() > 0 else None
                if not layers and hole is None:
                    continue  # paste-/mask-only aperture pad: no copper, no hole
                # One effective shape per copper layer; a via spans every layer,
                # so it is checked against all of them regardless of layer.
                shapes = [pad.GetEffectiveShape(l) for l in layers]
                item = Item(
                    pad.GetNetCode(),
                    set(layers),
                    shapes,
                    hole,
                    bbox_of(pad.GetBoundingBox(), mm(2.0)),
                    f"{fp.GetReference()}.{pad.GetNumber()}",
                )
                self._add_item(item)

        for t in self.board.GetTracks():
            layers = copper_layers(t)
            hole = hole_record(t) if t.GetClass() == "PCB_VIA" else None
            self._add_item(
                Item(
                    t.GetNetCode(),
                    set(layers),
                    [t.GetEffectiveShape()],
                    hole,
                    bbox_of(t.GetBoundingBox(), mm(2.0)),
                    f"{t.GetClass()}@{to_mm(t.GetStart().x):.2f},{to_mm(t.GetStart().y):.2f}",
                )
            )

    def _index_keepouts(self):
        zones = list(self.board.Zones())
        for fp in self.board.GetFootprints():
            zones.extend(list(fp.Zones()))
        for z in zones:
            if not z.GetIsRuleArea():
                continue
            outline = z.Outline()
            if z.GetDoNotAllowVias():
                self.keepout_vias.append(outline)
            if z.GetDoNotAllowTracks():
                self.keepout_tracks.append(outline)

    def _index_fills(self):
        for z in self.board.Zones():
            if z.GetIsRuleArea():
                continue
            name = z.GetNetname()
            for l in z.GetLayerSet().CuStack():
                polys = z.GetFilledPolysList(l)
                if polys.OutlineCount() == 0:
                    continue
                self.net_fill.setdefault(name, {})[l] = polys

    # -- checks ------------------------------------------------------------
    def inside_outline(self, pt, margin):
        key = margin
        if key not in self._deflated:
            p = pcbnew.SHAPE_POLY_SET(self.outline)
            p.Deflate(margin, pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, mm(0.005))
            self._deflated[key] = p
        return self._deflated[key].Contains(pt)

    def plane_reach(self, pt, netname, pad_layer, via_r):
        """True when a via at `pt` actually lands on its own plane.

        The test is not "centre inside the fill" but "same-net fill copper comes
        within (via_radius - overlap) of the centre", i.e. the annulus overlaps
        the plane by at least `overlap`: the zone filler does not carve anything
        out around a same-net via, so a via sitting slightly over the edge of a
        plane keyhole is still solidly connected, and being strict there costs
        real pads (three V3V3_SYS pads sit 0.05-0.10 mm outside the keyholed
        plane).  A via that reaches no same-net plane at all would be a dangling
        via that leaves the pad unconnected, which is why this is a hard
        requirement rather than a preference.
        """
        overlap = min(mm(0.15), via_r // 2)
        for l, polys in self.net_fill.get(netname, {}).items():
            if l == pad_layer:
                continue
            if polys.Collide(pt, max(0, via_r - overlap)):
                return True
        return False

    def plane_distance_mm(self, pt, netname, pad_layer):
        best = None
        for l, polys in self.net_fill.get(netname, {}).items():
            if l == pad_layer:
                continue
            for c in range(50, 20001, 50):
                if polys.Collide(pt, c * 1000):
                    d = c / 1000.0
                    best = d if best is None else min(best, d)
                    break
        return best

    def net_name_of(self, netcode):
        if not netcode:
            return None
        net = self.board.FindNet(netcode)
        return net.GetNetname() if net else None

    def via_clear(self, pt, dia, drill, netcode, netname, ignore=()):
        """All the DRC checks a candidate via has to pass."""
        r = dia // 2
        hr = drill // 2
        circle = pcbnew.SHAPE_CIRCLE(pt, r)
        hole_circle = pcbnew.SHAPE_CIRCLE(pt, hr)
        my_hole = (pt.x, pt.y, pt.x, pt.y, hr)

        if not self.inside_outline(pt, r + self.edge_clearance):
            return "board edge"
        for ko in self.keepout_vias:
            if ko.Collide(pt, r):
                return "via keepout"

        reach = r + mm(1.5)
        box = (pt.x - reach, pt.y - reach, pt.x + reach, pt.y + reach)
        for it in self.grid.query(box):
            if it in ignore:
                continue
            if it.net != netcode:
                clr = self.clearance_between(netname, self.net_name_of(it.net))
                for sh in it.shapes:
                    if sh.Collide(circle, clr + self.eps):
                        return f"clearance to {it.desc}"
                    if sh.Collide(hole_circle, self.hole_clearance + self.eps):
                        return f"my hole to copper of {it.desc}"
                if it.hole is not None:
                    d = seg_seg_dist(my_hole[:4], it.hole[:4])
                    if d < it.hole[4] + r + self.hole_clearance + self.eps:
                        return f"their hole to my copper, {it.desc}"
            if it.hole is not None:
                d = seg_seg_dist(my_hole[:4], it.hole[:4])
                if d < it.hole[4] + hr + self.hole_to_hole + self.eps:
                    return f"hole-to-hole to {it.desc}"
        return None

    def track_clear(self, a, b, width, layer, netcode, netname, ignore=()):
        if a.x == b.x and a.y == b.y:
            return None
        seg_shape = pcbnew.SHAPE_SEGMENT(a, b, width)
        my_seg = (a.x, a.y, b.x, b.y)
        for ko in self.keepout_tracks:
            if ko.Collide(pcbnew.SEG(a, b), width // 2):
                return "track keepout"
        x0, x1 = sorted((a.x, b.x))
        y0, y1 = sorted((a.y, b.y))
        m = width // 2 + mm(1.5)
        box = (x0 - m, y0 - m, x1 + m, y1 + m)
        for it in self.grid.query(box):
            if it in ignore or it.net == netcode:
                continue
            if layer not in it.layers and it.hole is None:
                continue
            clr = self.clearance_between(netname, self.net_name_of(it.net))
            if layer in it.layers:
                for sh in it.shapes:
                    if sh.Collide(seg_shape, clr + self.eps):
                        return f"track clearance to {it.desc}"
            if it.hole is not None:
                d = seg_seg_dist(my_seg, it.hole[:4])
                if d < it.hole[4] + width // 2 + self.hole_clearance + self.eps:
                    return f"track to hole of {it.desc}"
        return None

    # -- placement ---------------------------------------------------------
    def add_via(self, pt, dia, drill, netcode, netname, desc):
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(pt)
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetWidth(dia)
        via.SetDrill(drill)
        via.SetNetCode(netcode)
        via.SetLocked(True)
        self.board.Add(via)
        item = Item(
            netcode,
            set(copper_layers(via)),
            [via.GetEffectiveShape()],
            (pt.x, pt.y, pt.x, pt.y, drill // 2),
            bbox_of(via.GetBoundingBox(), mm(2.0)),
            desc,
        )
        self._add_item(item)
        self.new_items.append(item)
        return via, item

    def add_track(self, a, b, width, layer, netcode, desc):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(a)
        t.SetEnd(b)
        t.SetWidth(width)
        t.SetLayer(layer)
        t.SetNetCode(netcode)
        t.SetLocked(True)
        self.board.Add(t)
        item = Item(
            netcode,
            {layer},
            [t.GetEffectiveShape()],
            None,
            bbox_of(t.GetBoundingBox(), mm(2.0)),
            desc,
        )
        self._add_item(item)
        self.new_items.append(item)
        return t


# ---------------------------------------------------------------------------
# main algorithm
# ---------------------------------------------------------------------------


def collect_targets(board, netnames, thermal_min):
    """-> (normal_pads, thermal_pads); both lists of (footprint, pad)."""
    normal, thermal = [], []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() not in netnames:
                continue
            if pad.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN):
                continue
            if not copper_layers(pad):
                continue
            if min(pad.GetSizeX(), pad.GetSizeY()) >= thermal_min:
                thermal.append((fp, pad))
            else:
                normal.append((fp, pad))
    return normal, thermal


def pad_layer_of(pad):
    layers = copper_layers(pad)
    if pcbnew.F_Cu in layers:
        return pcbnew.F_Cu
    if pcbnew.B_Cu in layers:
        return pcbnew.B_Cu
    return layers[0]


def footprint_centroid(fp):
    xs, ys, n = 0, 0, 0
    for p in fp.Pads():
        if not copper_layers(p):
            continue
        xs += p.GetX()
        ys += p.GetY()
        n += 1
    if n == 0:
        pos = fp.GetPosition()
        return pos.x, pos.y
    return xs / n, ys / n


def directions_for(fp, pad, extra_angles=16):
    """Candidate directions, in the order they are tried.

    Spec order is radial-outward, the two tangential directions, then inward.
    One refinement: for an elongated pad (a QFN/SOIC lead) the primary
    direction is the pad's own long axis, signed away from the footprint
    centroid, and the tangentials are perpendicular to *that* -- i.e. the
    normal fanout direction for a fine-pitch lead.  Pure radial on a corner
    lead of a 0.4 mm-pitch QFN aims the track diagonally across its two
    neighbours and fails the clearance check for no reason (measured: 3 of
    U20's GND/V3V3 leads).  The pure-radial set is still tried right after,
    so nothing that used to be placed moves.

    After the spec'd directions, `extra_angles` evenly spaced directions are
    swept as a last resort (they only ever turn an unreachable pad into a
    placed via; a pad that succeeds earlier never gets here).
    """
    cx, cy = footprint_centroid(fp)
    dx, dy = pad.GetX() - cx, pad.GetY() - cy
    norm = math.hypot(dx, dy)
    if norm < mm(0.001):
        ang = pad.GetOrientation().AsRadians()
        rx, ry = math.cos(ang), math.sin(ang)
    else:
        rx, ry = dx / norm, dy / norm

    dirs = []
    sx, sy = pad.GetSizeX(), pad.GetSizeY()
    if max(sx, sy) >= 1.3 * min(sx, sy):
        ang = pad.GetOrientation().AsRadians()
        if sx >= sy:
            ax, ay = math.cos(ang), math.sin(ang)
        else:
            ax, ay = -math.sin(ang), math.cos(ang)
        if ax * rx + ay * ry < 0:
            ax, ay = -ax, -ay
        dirs += [("axis", ax, ay), ("axis-tan+", -ay, ax), ("axis-tan-", ay, -ax)]
    dirs += [("out", rx, ry), ("tan+", -ry, rx), ("tan-", ry, -rx), ("in", -rx, -ry)]
    if dirs and dirs[0][0] == "axis":
        dirs.append(("axis-in", -dirs[0][1], -dirs[0][2]))
    for k in range(extra_angles):
        a = 2 * math.pi * k / extra_angles
        ca, sa = math.cos(a), math.sin(a)
        dirs.append((f"sweep{k}", rx * ca - ry * sa, rx * sa + ry * ca))
    return dirs


def stitch(board, args):
    st = Stitcher(board, args)
    netnames = [n.strip() for n in args.nets.split(",") if n.strip()]
    normal, thermal = collect_targets(board, set(netnames), mm(args.thermal_min))

    stats = {n: dict(pads=0, vias=0, shared=0, unreachable=[], tracks=0) for n in netnames}
    placed_by_net = defaultdict(list)   # netname -> [(pad_x, pad_y, via_pos, item)]
    report_vias = []

    # deterministic order: net (in the --nets order given - see module
    # docstring, this is significant), then position
    net_rank = {n: i for i, n in enumerate(netnames)}
    normal.sort(key=lambda t: (net_rank[t[1].GetNetname()], t[1].GetY(), t[1].GetX(),
                               t[0].GetReference(), t[1].GetNumber()))

    for fp, pad in normal:
        net = pad.GetNetname()
        nc = st.netclass(net)
        dia, drill, tw = nc.GetViaDiameter(), nc.GetViaDrill(), nc.GetTrackWidth()
        # Stub on fine-pitch pads: 0.3 mm width on 0.2 mm-wide 0.4 mm-pitch QFN pad breaks clearance
        stub_width = max(pcbnew.FromMM(0.127), min(tw, min(pad.GetSizeX(), pad.GetSizeY())))
        netcode = pad.GetNetCode()
        layer = pad_layer_of(pad)
        pos = pad.GetPosition()
        desc = f"{fp.GetReference()}.{pad.GetNumber()}"
        stats[net]["pads"] += 1

        pad_items = [it for it in st.grid.query((pos.x - mm(0.1), pos.y - mm(0.1), pos.x + mm(0.1), pos.y + mm(0.1)))
                     if it.desc == desc]

        # (1) share an existing same-net via whose owner pad is within share-dist
        shared = None
        for (ox, oy, vpos, item, owner) in sorted(
            placed_by_net[net], key=lambda e: math.hypot(e[2].x - pos.x, e[2].y - pos.y)
        ):
            if math.hypot(ox - pos.x, oy - pos.y) > mm(args.share_dist):
                continue
            if st.track_clear(pos, vpos, stub_width, layer, netcode, net, ignore=pad_items + [item]) is None:
                shared = (vpos, item)
                break
        if shared is not None:
            vpos, item = shared
            st.add_track(pos, vpos, stub_width, layer, netcode, f"stitch {desc}")
            stats[net]["shared"] += 1
            stats[net]["tracks"] += 1
            report_vias.append(dict(net=net, pad=desc, x=to_mm(vpos.x), y=to_mm(vpos.y), shared=True))
            continue

        # (2) own via
        reasons = []
        done = False
        max_extra_mm = (max(args.max_extra, EXTENDED_MAX_EXTRA_MM)
                         if net in EXTENDED_MAX_EXTRA_NETS else args.max_extra)
        for dname, dx, dy in directions_for(fp, pad, args.extra_angles):
            base = pad_support(pad, dx, dy) + dia / 2 + st.clearance_between(net, net) + mm(0.05)
            step = 0
            while step <= mm(max_extra_mm) + 1:
                dist = base + step
                pt = pcbnew.VECTOR2I(int(round(pos.x + dx * dist)), int(round(pos.y + dy * dist)))
                step += mm(0.25)
                if not st.plane_reach(pt, net, layer, dia // 2):
                    reasons.append("no same-net plane copper under the via")
                    continue
                why = st.via_clear(pt, dia, drill, netcode, net, ignore=pad_items)
                if why:
                    reasons.append(why)
                    continue
                why = st.track_clear(pos, pt, stub_width, layer, netcode, net, ignore=pad_items)
                if why:
                    reasons.append(why)
                    continue
                via, item = st.add_via(pt, dia, drill, netcode, net, f"stitchvia {desc}")
                st.add_track(pos, pt, stub_width, layer, netcode, f"stitch {desc}")
                placed_by_net[net].append((pos.x, pos.y, pt, item, desc))
                stats[net]["vias"] += 1
                stats[net]["tracks"] += 1
                report_vias.append(dict(net=net, pad=desc, x=to_mm(pt.x), y=to_mm(pt.y), dir=dname,
                                        dist_mm=round(to_mm(dist), 3), shared=False))
                done = True
                break
            if done:
                break
        if not done:
            top = defaultdict(int)
            for r in reasons:
                top[r] += 1
            ranked = sorted(top.items(), key=lambda kv: -kv[1])
            reason = "; ".join(f"{r} x{n}" for r, n in ranked[:2]) if ranked else "no candidate"
            if any(r.startswith("no same-net plane") for r, _ in ranked):
                d = st.plane_distance_mm(pos, net, layer)
                if d is not None:
                    reason += f" (nearest {net} plane copper {d:.2f} mm from the pad)"
            stats[net]["unreachable"].append(dict(pad=desc, reason=reason,
                                                  candidates=sum(top.values()),
                                                  x=to_mm(pos.x), y=to_mm(pos.y)))

    # (3) exposed / thermal pads: via array on a 1 mm grid
    for fp, pad in thermal:
        net = pad.GetNetname()
        netcode = pad.GetNetCode()
        layer = pad_layer_of(pad)
        desc = f"{fp.GetReference()}.{pad.GetNumber()}"
        stats[net]["pads"] += 1
        dia, drill = mm(args.thermal_via_dia), mm(args.thermal_via_drill)
        pos = pad.GetPosition()
        ang = pad.GetOrientation().AsRadians()
        ca, sa = math.cos(ang), math.sin(ang)
        pad_items = [it for it in st.grid.query((pos.x - mm(0.1), pos.y - mm(0.1), pos.x + mm(0.1), pos.y + mm(0.1)))
                     if it.desc == desc]
        placed = 0
        for hx, hy, pitch in ((pad.GetSizeX() / 2.0, pad.GetSizeY() / 2.0, mm(args.thermal_pitch)),):
            ax = hx - mm(args.thermal_margin) - dia / 2
            ay = hy - mm(args.thermal_margin) - dia / 2
            nx = int(ax // pitch)
            ny = int(ay // pitch)
            for i in range(-nx, nx + 1):
                for j in range(-ny, ny + 1):
                    lx, ly = i * pitch, j * pitch
                    pt = pcbnew.VECTOR2I(int(round(pos.x + lx * ca - ly * sa)),
                                         int(round(pos.y + lx * sa + ly * ca)))
                    if not st.plane_reach(pt, net, layer, dia // 2):
                        stats[net]["unreachable"].append(
                            dict(pad=f"{desc}[{i},{j}]", reason="no same-net plane copper under the via",
                                 x=to_mm(pt.x), y=to_mm(pt.y)))
                        continue
                    why = st.via_clear(pt, dia, drill, netcode, net, ignore=pad_items)
                    if why:
                        stats[net]["unreachable"].append(
                            dict(pad=f"{desc}[{i},{j}]", reason=why, x=to_mm(pt.x), y=to_mm(pt.y)))
                        continue
                    st.add_via(pt, dia, drill, netcode, net, f"thermalvia {desc}")
                    placed += 1
                    stats[net]["vias"] += 1
                    report_vias.append(dict(net=net, pad=desc, x=to_mm(pt.x), y=to_mm(pt.y),
                                            dir=f"array[{i},{j}]", shared=False))
        if placed == 0:
            stats[net]["unreachable"].append(dict(pad=desc, reason="thermal array: no clean position",
                                                  x=to_mm(pos.x), y=to_mm(pos.y)))

    return st, stats, report_vias


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--out", default=None)
    ap.add_argument("--nets", default="V3V3_ANA,V3V3_SYS,GND",
                    help="comma-separated, ORDER-SIGNIFICANT: stitched in the "
                         "order given, earlier nets first (see module "
                         "docstring); default puts GND last")
    ap.add_argument("--report", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--share-dist", type=float, default=1.2,
                    help="two same-net pads this close (mm, centre to centre) may share one via")
    ap.add_argument("--max-extra", type=float, default=1.5,
                    help="how far past the first candidate distance to keep stepping (mm) "
                         "for GND; V3V3_SYS/V3V3_ANA use max(this, %.1f mm) - see "
                         "EXTENDED_MAX_EXTRA_NETS" % EXTENDED_MAX_EXTRA_MM)
    ap.add_argument("--thermal-min", type=float, default=2.0,
                    help="pads with both sides >= this (mm) get the via array instead of a fanout via")
    ap.add_argument("--thermal-pitch", type=float, default=1.0)
    ap.add_argument("--thermal-margin", type=float, default=0.4)
    ap.add_argument("--thermal-via-dia", type=float, default=0.6)
    ap.add_argument("--thermal-via-drill", type=float, default=0.3)
    ap.add_argument("--extra-angles", type=int, default=16,
                    help="last-resort directions swept after the spec'd four (0 disables)")
    ap.add_argument("--no-fill", action="store_true", help="skip the zone refill (debug only)")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.board)
    st, stats, report_vias = stitch(board, args)

    out = args.out or args.board.replace(".kicad_pcb", ".stitched.kicad_pcb")
    filled = False
    if not args.dry_run:
        board.BuildConnectivity()
        if not args.no_fill:
            filler = pcbnew.ZONE_FILLER(board)
            filled = filler.Fill(board.Zones())
        pcbnew.SaveBoard(out, board)

    hdr = f"{'net':<12}{'pads':>6}{'vias':>6}{'shared':>8}{'tracks':>8}{'unreachable':>12}"
    print(hdr)
    print("-" * len(hdr))
    for net, s in stats.items():
        print(f"{net:<12}{s['pads']:>6}{s['vias']:>6}{s['shared']:>8}{s['tracks']:>8}{len(s['unreachable']):>12}")
    tot_v = sum(s["vias"] for s in stats.values())
    tot_t = sum(s["tracks"] for s in stats.values())
    tot_u = sum(len(s["unreachable"]) for s in stats.values())
    print("-" * len(hdr))
    print(f"{'TOTAL':<12}{sum(s['pads'] for s in stats.values()):>6}{tot_v:>6}"
          f"{sum(s['shared'] for s in stats.values()):>8}{tot_t:>8}{tot_u:>12}")
    for net, s in stats.items():
        if s["unreachable"]:
            print(f"\nunreachable on {net} ({len(s['unreachable'])}):")
            for u in s["unreachable"]:
                print(f"  {u['pad']:<12} @ {u['x']:.2f},{u['y']:.2f}  {u['reason']}")
    print(f"\nzones refilled: {filled}")
    print(f"{'(dry run, no board written)' if args.dry_run else 'board written: ' + out}")

    if args.report:
        data = dict(
            board=args.board,
            out=None if args.dry_run else out,
            nets=args.nets.split(","),
            zones_refilled=bool(filled),
            summary={n: dict(pads=s["pads"], vias=s["vias"], shared=s["shared"],
                             tracks=s["tracks"], unreachable=len(s["unreachable"]))
                     for n, s in stats.items()},
            unreachable={n: s["unreachable"] for n, s in stats.items() if s["unreachable"]},
            vias=report_vias,
        )
        with open(args.report, "w") as fh:
            json.dump(data, fh, indent=1)
        print(f"report written: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
