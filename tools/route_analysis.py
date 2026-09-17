#!/usr/bin/env python3
"""route_analysis.py - read-only ratsnest length/crossing analysis for the U20 MCU nets.

Usage:
  python3 tools/route_analysis.py dump
  python3 tools/route_analysis.py score [--assign assign.json] [--json] [--w 10]
                                         [--star] [--ignore-refs REGEX]
  python3 tools/route_analysis.py optimize --groups groups.json [--iters N]
                                            [--restarts N] [--out best.json]
                                            [--w-cross 10] [--w-angle 5] [--seed 42]
                                            [--star] [--ignore-refs REGEX]
  python3 tools/route_analysis.py report --assign best.json [--groups groups.json]
                                          [--star] [--ignore-refs REGEX]

Reads MARV-V2.kicad_pcb only (via pcbnew if importable, else a built-in
S-expression parser whose coordinate transform was cross-checked against
pcbnew, see _sexp_load_board). Never writes to any .kicad_* file - only to
stdout and to whatever path --out/--groups/--assign point at (JSON reports).
Coordinates are always reported in millimetres. Default net model is a
Euclidean MST over all pads of the net (like KiCad's ratsnest); --star opts
back into the old "all endpoints direct from the U20 pad" model.
"""
import sys
import os
import re
import json
import math
import argparse
import random
import itertools
from collections import namedtuple, defaultdict

BOARD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "MARV-V2.kicad_pcb")
POWER_NETS = {"GND", "VBAT", "5V_IN", "V5_SYS", "USB_VBUS", "V3V3_SYS", "V3V3_ANA"}
MCU_VALUE_HINT = "RP2354"
EPS = 1e-7

# Fixed RP2354B GPIO -> U20 pad-number map (lead-supplied). Verified below in
# verify_gpio_map() against a plausibility sample read from the real board.
GPIO_TO_PAD = {
    0: 77, 1: 78, 2: 79, 3: 80, 4: 1, 5: 2, 6: 3, 7: 4, 8: 6, 9: 7, 10: 8,
    11: 9, 12: 11, 13: 12, 14: 13, 15: 14, 16: 16, 17: 17, 18: 18, 19: 19,
    20: 20, 21: 21, 22: 22, 23: 23, 24: 25, 25: 26, 26: 27, 27: 28, 28: 36,
    29: 37, 30: 38, 31: 39, 32: 40, 33: 42, 34: 43, 35: 44, 36: 45, 37: 46,
    38: 47, 39: 48, 40: 49, 41: 52, 42: 53, 43: 54, 44: 55, 45: 56, 46: 57,
    47: 58,
}
PAD_TO_GPIO = {pad: gpio for gpio, pad in GPIO_TO_PAD.items()}
_GPIO_MAP_PLAUSIBILITY = {16: "SENS_MISO", 40: "SD_CLK", 49: "VBAT_SENSE"}

Pad = namedtuple("Pad", "ref num x y net back")


# --------------------------------------------------------------------------
# Board loading: pcbnew preferred, pure s-expression parser as fallback.
# --------------------------------------------------------------------------

def _pcbnew_load_board(path):
    import pcbnew  # may raise ImportError - caller handles it

    board = pcbnew.LoadBoard(path)
    pads = []
    mcu_ref = None
    for fp in board.GetFootprints():
        if MCU_VALUE_HINT in fp.GetValue():
            mcu_ref = fp.GetReference()
        back = fp.IsFlipped()
        for p in fp.Pads():
            num = p.GetNumber()
            if not num:
                continue
            pos = p.GetPosition()
            pads.append(Pad(fp.GetReference(), num, pos.x / 1e6, pos.y / 1e6, p.GetNetname(), back))
    if mcu_ref is None:
        raise RuntimeError(f'no footprint with value containing "{MCU_VALUE_HINT}" found')
    return pads, mcu_ref, "pcbnew"


def _sexp_tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            tokens.append("(")
            i += 1
        elif c == ")":
            tokens.append(")")
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(("a", "".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n()":
                j += 1
            tokens.append(("a", text[i:j]))
            i = j
    return tokens


def _sexp_parse(tokens):
    pos = [0]

    def expr():
        tok = tokens[pos[0]]
        if tok == "(":
            pos[0] += 1
            items = []
            while tokens[pos[0]] != ")":
                items.append(expr())
            pos[0] += 1
            return items
        pos[0] += 1
        return tok[1]

    out = []
    while pos[0] < len(tokens):
        out.append(expr())
    return out


def _find(children, key):
    for c in children:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def _find_all(children, key):
    return [c for c in children if isinstance(c, list) and c and c[0] == key]


def _rot_cw(x, y, theta_deg):
    """Rotate (x, y) by theta_deg using the same sense KiCad stores in files.

    Empirically cross-checked against pcbnew.LoadBoard() absolute pad
    positions for every uniquely-numbered pad on this board (479/479 exact,
    including a back-side SOIC-8 at theta=0 and a back-side pad row at
    theta=-90, plus front-side parts at theta=90/180): the stored local pad
    "at" coordinates for back-side (mirrored) footprints already encode the
    mirror, so absolute = footprint_at + rot_cw(pad_local_at, footprint_theta)
    with NO separate x-negation step for back-side footprints.
    """
    th = math.radians(theta_deg)
    c, s = math.cos(th), math.sin(th)
    return x * c + y * s, -x * s + y * c


def _sexp_load_board(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    tree = _sexp_parse(_sexp_tokenize(text))
    root = tree[0]
    fps = _find_all(root[1:], "footprint")

    pads = []
    mcu_ref = None
    for fp in fps:
        body = fp[1:]
        layer_node = _find(body, "layer")
        back = bool(layer_node) and layer_node[1].startswith("B.")
        at_node = _find(body, "at")
        fx, fy = float(at_node[1]), float(at_node[2])
        ftheta = float(at_node[3]) if len(at_node) > 3 else 0.0

        ref = None
        value = None
        for prop in _find_all(body, "property"):
            if len(prop) > 2 and prop[1] == "Reference":
                ref = prop[2]
            if len(prop) > 2 and prop[1] == "Value":
                value = prop[2]
        if value and MCU_VALUE_HINT in value:
            mcu_ref = ref

        for p in _find_all(body, "pad"):
            num = p[1]
            if not num:
                continue
            pbody = p[2:]
            pat = _find(pbody, "at")
            lx, ly = float(pat[1]), float(pat[2])
            net_node = _find(pbody, "net")
            net = net_node[2] if net_node and len(net_node) > 2 else ""
            rx, ry = _rot_cw(lx, ly, ftheta)
            pads.append(Pad(ref, num, fx + rx, fy + ry, net, back))

    if mcu_ref is None:
        raise RuntimeError(f'no footprint with value containing "{MCU_VALUE_HINT}" found')
    return pads, mcu_ref, "sexp-fallback"


def load_board(path):
    try:
        return _pcbnew_load_board(path)
    except Exception as e_pcbnew:
        try:
            return _sexp_load_board(path)
        except Exception as e_sexp:
            print(
                f"FAIL: pcbnew load failed ({e_pcbnew!r}); sexp fallback also failed ({e_sexp!r})",
                file=sys.stderr,
            )
            sys.exit(2)


# --------------------------------------------------------------------------
# Board model: pad ring, net -> peripheral endpoints.
# --------------------------------------------------------------------------

class BoardModel:
    def __init__(self, path=BOARD_FILE):
        self.pads, self.mcu_ref, self.parser = load_board(path)

        self.u20_pad_by_num = {}   # int pad number -> Pad (of the MCU)
        self.u20_center = None
        mcu_xs, mcu_ys = [], []
        for p in self.pads:
            if p.ref == self.mcu_ref:
                mcu_xs.append(p.x)
                mcu_ys.append(p.y)
                if p.num.isdigit():
                    self.u20_pad_by_num[int(p.num)] = p
        if mcu_xs:
            # Centre of the pad ring's bounding box approximates the QFN body centre.
            self.u20_center = ((min(mcu_xs) + max(mcu_xs)) / 2.0, (min(mcu_ys) + max(mcu_ys)) / 2.0)

        # net -> list of non-MCU Pad endpoints
        self.net_endpoints = defaultdict(list)
        for p in self.pads:
            if p.ref != self.mcu_ref:
                self.net_endpoints[p.net].append(p)

        # net -> MCU pad number currently carrying it (only numeric, real nets)
        self.net_to_pad = {}
        for num, p in self.u20_pad_by_num.items():
            if p.net:
                self.net_to_pad[p.net] = num

    def is_power_or_skip(self, net):
        if net in POWER_NETS:
            return True
        if net.startswith("unconnected-"):
            return True
        return False

    def signal_nets(self):
        """MCU nets that are not power/GND and have >=1 peripheral endpoint."""
        out = []
        for net, pad_num in self.net_to_pad.items():
            if self.is_power_or_skip(net):
                continue
            if not self.net_endpoints.get(net):
                continue
            out.append(net)
        return sorted(out)

    def qfn_normal(self, pad_num):
        """Outward normal (unit-ish vector) of the QFN side that pad_num sits on."""
        p = self.u20_pad_by_num[pad_num]
        cx, cy = self.u20_center
        dx, dy = p.x - cx, p.y - cy
        if abs(dx) >= abs(dy):
            return (1.0 if dx >= 0 else -1.0, 0.0)
        return (0.0, 1.0 if dy >= 0 else -1.0)


def verify_gpio_map(board):
    """Plausibility-check GPIO_TO_PAD against the real board; FAIL loudly on mismatch."""
    bad = []
    for pad, expected_net in _GPIO_MAP_PLAUSIBILITY.items():
        actual = board.u20_pad_by_num.get(pad)
        actual_net = actual.net if actual else None
        if actual_net != expected_net:
            bad.append((pad, expected_net, actual_net))
    if bad:
        print("FAIL: GPIO->pad map plausibility check failed against the real board:", file=sys.stderr)
        for pad, expected_net, actual_net in bad:
            print(f"  pad {pad}: expected net {expected_net!r}, board has {actual_net!r}", file=sys.stderr)
        sys.exit(3)


# --------------------------------------------------------------------------
# Geometry: length, proper segment crossing test, Euclidean MST (Prim's).
# --------------------------------------------------------------------------

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def proper_cross(p1, p2, p3, p4):
    """True iff segment p1-p2 and p3-p4 cross strictly in both interiors.

    Shared endpoints (or a T-touch where one endpoint lies on the other
    segment) yield a zero cross product and are correctly excluded.
    """
    d1 = _orient(p3, p4, p1)
    d2 = _orient(p3, p4, p2)
    d3 = _orient(p1, p2, p3)
    d4 = _orient(p1, p2, p4)
    return (d1 * d2 < -EPS) and (d3 * d4 < -EPS)


def _prim_mst(nodes):
    """Euclidean MST over `nodes` (list of (x,y)); returns list of (i, j) edges."""
    n = len(nodes)
    if n <= 1:
        return []
    in_tree = [False] * n
    in_tree[0] = True
    best_dist = [dist(nodes[i], nodes[0]) for i in range(n)]
    best_from = [0] * n
    edges = []
    for _ in range(n - 1):
        u, ud = -1, math.inf
        for i in range(n):
            if not in_tree[i] and best_dist[i] < ud:
                ud, u = best_dist[i], i
        in_tree[u] = True
        edges.append((best_from[u], u))
        for i in range(n):
            if not in_tree[i]:
                d = dist(nodes[i], nodes[u])
                if d < best_dist[i]:
                    best_dist[i], best_from[i] = d, u
    return edges


# --------------------------------------------------------------------------
# Net-topology model (star or MST) + scoring.
# --------------------------------------------------------------------------

Edge = namedtuple("Edge", "net p1 p2 incident_u20")


def build_assignment(board, override=None):
    """net -> U20 pad number, using board defaults overridden by `override`."""
    assignment = {}
    for net in board.signal_nets():
        assignment[net] = board.net_to_pad[net]
    if override:
        for net, pad in override.items():
            if net not in assignment:
                print(f"WARNING: assign.json net {net!r} is not a routable MCU signal net; ignoring", file=sys.stderr)
                continue
            assignment[net] = int(pad)
        used = defaultdict(list)
        for net, pad in assignment.items():
            used[pad].append(net)
        for pad, nets in used.items():
            if len(nets) > 1:
                print(f"WARNING: pad {pad} is assigned to multiple nets: {nets}", file=sys.stderr)
    return assignment


def build_edges(board, assignment, model="mst", ignore_re=None):
    """net -> list[Edge]. model is "mst" (default) or "star"."""
    edges_by_net = defaultdict(list)
    for net, pad_num in assignment.items():
        origin_pad = board.u20_pad_by_num.get(pad_num)
        if origin_pad is None:
            print(f"WARNING: pad {pad_num} (net {net!r}) does not exist on {board.mcu_ref}; skipping", file=sys.stderr)
            continue
        origin = (origin_pad.x, origin_pad.y)
        eps = board.net_endpoints.get(net, [])
        if ignore_re is not None:
            eps = [ep for ep in eps if not ignore_re.search(ep.ref)]
        if not eps:
            continue

        if model == "star":
            for ep in eps:
                edges_by_net[net].append(Edge(net, origin, (ep.x, ep.y), True))
        else:
            nodes = [origin] + [(ep.x, ep.y) for ep in eps]
            for i, j in _prim_mst(nodes):
                edges_by_net[net].append(Edge(net, nodes[i], nodes[j], i == 0 or j == 0))
    return edges_by_net


def score_assignment(board, assignment, model="mst", ignore_re=None):
    edges_by_net = build_edges(board, assignment, model, ignore_re)
    all_edges = [e for edges in edges_by_net.values() for e in edges]

    per_net_length = {}
    total_length = 0.0
    for net, edges in edges_by_net.items():
        length = sum(dist(e.p1, e.p2) for e in edges)
        per_net_length[net] = length
        total_length += length

    # Pairwise proper crossings between edges of different nets.
    pair_counts = defaultdict(int)
    n = len(all_edges)
    for i in range(n):
        ei = all_edges[i]
        for j in range(i + 1, n):
            ej = all_edges[j]
            if ei.net == ej.net:
                continue
            if proper_cross(ei.p1, ei.p2, ej.p1, ej.p2):
                a, b = sorted((ei.net, ej.net))
                pair_counts[(a, b)] += 1
    crossings = sum(pair_counts.values())

    # Angle penalty: evaluated only on edge(s) incident to the U20 pad; net
    # flagged once if any such edge points back into the chip body (negative
    # dot product with the pad's outward normal).
    angle_flagged = []
    for net, pad_num in assignment.items():
        if pad_num not in board.u20_pad_by_num:
            continue
        nx, ny = board.qfn_normal(pad_num)
        origin = (board.u20_pad_by_num[pad_num].x, board.u20_pad_by_num[pad_num].y)
        flagged = False
        for e in edges_by_net.get(net, []):
            if not e.incident_u20:
                continue
            other = e.p2 if dist(e.p1, origin) < 1e-9 else e.p1
            vx, vy = other[0] - origin[0], other[1] - origin[1]
            if vx * nx + vy * ny < -EPS:
                flagged = True
                break
        if flagged:
            angle_flagged.append(net)

    crossing_pairs = sorted(pair_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    return {
        "nets": len(assignment),
        "per_net_length_mm": per_net_length,
        "total_length_mm": total_length,
        "crossings": crossings,
        "crossing_pairs": crossing_pairs,
        "angle_penalty": len(angle_flagged),
        "angle_flagged_nets": sorted(angle_flagged),
    }


def combined_score(result, w):
    return result["crossings"] * w + result["total_length_mm"]


def optimize_cost(result, w_cross, w_angle):
    return w_cross * result["crossings"] + result["total_length_mm"] + w_angle * result["angle_penalty"]


def compile_ignore_refs(pattern):
    return re.compile(pattern) if pattern else None


# --------------------------------------------------------------------------
# Commands: dump, score.
# --------------------------------------------------------------------------

def cmd_dump(board, args):
    print(f"# parser={board.parser} mcu_ref={board.mcu_ref} pads={len(board.u20_pad_by_num)}")
    print(f"\n== {board.mcu_ref} pad ring ({len(board.u20_pad_by_num)} pads) ==")
    for num in sorted(board.u20_pad_by_num):
        p = board.u20_pad_by_num[num]
        print(f"  pad {num:>3}  ({p.x:9.4f}, {p.y:9.4f})  {p.net}")

    nets = board.signal_nets()
    print(f"\n== MCU signal nets ({len(nets)}, power/GND/unconnected excluded) ==")
    for net in nets:
        pad_num = board.net_to_pad[net]
        origin = board.u20_pad_by_num[pad_num]
        eps = board.net_endpoints[net]
        ep_str = " ".join(
            f"{ep.ref}.{ep.num}@({ep.x:.4f},{ep.y:.4f})/{'back' if ep.back else 'front'}" for ep in eps
        )
        print(f"{net:<16} {board.mcu_ref}.{pad_num:<3}@({origin.x:.4f},{origin.y:.4f})  ->  {ep_str}")


def cmd_score(board, args):
    override = None
    if args.assign:
        with open(args.assign, "r", encoding="utf-8") as f:
            override = json.load(f)
    model = "star" if args.star else "mst"
    ignore_re = compile_ignore_refs(args.ignore_refs)
    assignment = build_assignment(board, override)
    result = score_assignment(board, assignment, model, ignore_re)
    edges_by_net = build_edges(board, assignment, model, ignore_re)

    if args.json:
        out = dict(result)
        out["crossing_pairs"] = [{"a": a, "b": b, "count": c} for (a, b), c in result["crossing_pairs"][:30]]
        out["assignment"] = assignment
        out["model"] = model
        out["combined_score_w"] = args.w
        out["combined_score"] = combined_score(result, args.w)
        print(json.dumps(out, indent=2, sort_keys=True))
        return

    print(f"# model={model} ignore_refs={args.ignore_refs!r}")
    print(f"{'net':<16}{'pad':>5}{'length_mm':>12}{'edges':>7}")
    for net in sorted(assignment):
        edges = edges_by_net.get(net, [])
        print(f"{net:<16}{assignment[net]:>5}{result['per_net_length_mm'].get(net, 0.0):>12.4f}{len(edges):>7}")

    print(
        f"\nSUMMARY nets={result['nets']} total_length_mm={result['total_length_mm']:.4f} "
        f"crossings={result['crossings']} angle_penalty={result['angle_penalty']} "
        f"combined(w={args.w})={combined_score(result, args.w):.4f}"
    )
    if result["angle_flagged_nets"]:
        print(f"angle_penalty nets: {', '.join(result['angle_flagged_nets'])}")

    print(f"\nTop crossing pairs (of {len(result['crossing_pairs'])}), max 30:")
    for (a, b), c in result["crossing_pairs"][:30]:
        print(f"  {a} x {b}: {c}")


# --------------------------------------------------------------------------
# groups.json loading: free groups + bundle groups, with GPIO unit conversion
# and the global "each pad used at most once" constraint.
# --------------------------------------------------------------------------

class FreeGroup:
    def __init__(self, name, nets, pads):
        self.name, self.nets, self.pads = name, nets, pads


class BundleGroup:
    def __init__(self, name, nets, options):
        self.name, self.nets, self.options = name, nets, options


def _convert_units(values, unit):
    if unit == "gpio":
        out = []
        for v in values:
            g = int(v)
            if g not in GPIO_TO_PAD:
                raise ValueError(f"no GPIO->pad mapping for GPIO {g}")
            out.append(GPIO_TO_PAD[g])
        return out
    return [int(v) for v in values]


def load_groups(board, path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    uses_gpio = any(g.get("unit") == "gpio" for g in raw)
    if uses_gpio:
        verify_gpio_map(board)

    free_groups, bundle_groups = [], []
    for g in raw:
        name = g["name"]
        nets = list(g["nets"])
        unit = g.get("unit", "pad")
        if "options" in g:
            options = [tuple(_convert_units(opt, unit)) for opt in g["options"]]
            for opt in options:
                if len(set(opt)) != len(opt):
                    print(f"FAIL: bundle group {name!r} option {opt} has duplicate pads", file=sys.stderr)
                    sys.exit(3)
                if len(opt) != len(nets):
                    print(f"FAIL: bundle group {name!r} option {opt} does not match {len(nets)} nets", file=sys.stderr)
                    sys.exit(3)
            bundle_groups.append(BundleGroup(name, nets, options))
        elif "pads" in g:
            pads = _convert_units(g["pads"], unit)
            if len(set(pads)) < len(nets):
                print(f"FAIL: free group {name!r} has fewer distinct pads ({len(set(pads))}) than nets ({len(nets)})", file=sys.stderr)
                sys.exit(3)
            free_groups.append(FreeGroup(name, nets, pads))
        else:
            print(f"FAIL: group {name!r} has neither 'pads' nor 'options'", file=sys.stderr)
            sys.exit(3)
    return free_groups, bundle_groups


def _drop_fixed_pads(free_groups, bundle_groups, fixed_pads):
    """Remove globally-fixed pads from every pool; a fixed pad is never available."""
    for fg in free_groups:
        before = len(fg.pads)
        fg.pads = [p for p in fg.pads if p not in fixed_pads]
        if len(fg.pads) < len(fg.nets):
            print(f"FAIL: free group {fg.name!r} pool shrank to {len(fg.pads)} pads (< {len(fg.nets)} nets) "
                  f"after removing {before - len(fg.pads)} fixed pad(s)", file=sys.stderr)
            sys.exit(3)
    for bg in bundle_groups:
        before = len(bg.options)
        bg.options = [opt for opt in bg.options if fixed_pads.isdisjoint(opt)]
        if not bg.options:
            print(f"FAIL: bundle group {bg.name!r} has no options left after removing "
                  f"{before} option(s) that used a fixed pad", file=sys.stderr)
            sys.exit(3)


# --------------------------------------------------------------------------
# Search state for `optimize`.
# --------------------------------------------------------------------------

class SearchState:
    __slots__ = ("bundle_choice", "free_choice")

    def __init__(self, bundle_choice, free_choice):
        self.bundle_choice = bundle_choice          # {bundle_name: option_index}
        self.free_choice = free_choice              # {free_name: {net: pad}}

    def clone(self):
        return SearchState(dict(self.bundle_choice), {k: dict(v) for k, v in self.free_choice.items()})

    def used_pads(self, bundle_groups, free_groups):
        used = set()
        for bg in bundle_groups:
            used.update(bg.options[self.bundle_choice[bg.name]])
        for fg in free_groups:
            used.update(self.free_choice[fg.name].values())
        return used

    def assignment(self, fixed_assignment, bundle_groups, free_groups):
        a = dict(fixed_assignment)
        for bg in bundle_groups:
            opt = bg.options[self.bundle_choice[bg.name]]
            for net, pad in zip(bg.nets, opt):
                a[net] = pad
        for fg in free_groups:
            a.update(self.free_choice[fg.name])
        return a


def _try_build_initial_state(rng, bundle_groups, free_groups):
    used = set()
    bundle_choice = {}
    order = list(bundle_groups)
    rng.shuffle(order)
    for bg in order:
        idxs = list(range(len(bg.options)))
        rng.shuffle(idxs)
        chosen = next((oi for oi in idxs if used.isdisjoint(bg.options[oi])), None)
        if chosen is None:
            return None
        bundle_choice[bg.name] = chosen
        used.update(bg.options[chosen])

    free_choice = {}
    order2 = list(free_groups)
    rng.shuffle(order2)
    for fg in order2:
        avail = [p for p in fg.pads if p not in used]
        if len(avail) < len(fg.nets):
            return None
        rng.shuffle(avail)
        chosen_pads = avail[: len(fg.nets)]
        free_choice[fg.name] = dict(zip(fg.nets, chosen_pads))
        used.update(chosen_pads)

    return SearchState(bundle_choice, free_choice)


def build_initial_state(bundle_groups, free_groups, rng, attempts=500):
    for _ in range(attempts):
        st = _try_build_initial_state(rng, bundle_groups, free_groups)
        if st is not None:
            return st
    return None


def _propose_bundle_change(rng, state, bg, bundle_groups, free_groups):
    other_bundle_used = set()
    for other in bundle_groups:
        if other.name != bg.name:
            other_bundle_used.update(other.options[state.bundle_choice[other.name]])
    candidates = [oi for oi, opt in enumerate(bg.options) if other_bundle_used.isdisjoint(opt)]
    if not candidates:
        return None
    oi = rng.choice(candidates)
    new_opt_pads = set(bg.options[oi])

    new_state = state.clone()
    # Free nets currently sitting on a pad the new option will occupy must be re-homed.
    displaced = []
    for fg in free_groups:
        for net, pad in new_state.free_choice[fg.name].items():
            if pad in new_opt_pads:
                displaced.append((fg, net))

    used = set(new_opt_pads) | other_bundle_used
    for fg in free_groups:
        for net, pad in new_state.free_choice[fg.name].items():
            if (fg, net) not in displaced:
                used.add(pad)

    for fg, net in displaced:
        avail = [p for p in fg.pads if p not in used]
        if not avail:
            return None  # cannot re-home -> reject the whole move
        newpad = rng.choice(avail)
        new_state.free_choice[fg.name][net] = newpad
        used.add(newpad)

    new_state.bundle_choice[bg.name] = oi
    return new_state


def _propose_free_swap(rng, state, fg):
    if len(fg.nets) < 2:
        return None
    n1, n2 = rng.sample(fg.nets, 2)
    new_state = state.clone()
    m = new_state.free_choice[fg.name]
    m[n1], m[n2] = m[n2], m[n1]
    return new_state


def _propose_free_move(rng, state, fg, bundle_groups, free_groups):
    net = rng.choice(fg.nets)
    used_elsewhere = state.used_pads(bundle_groups, free_groups) - {state.free_choice[fg.name][net]}
    avail = [p for p in fg.pads if p not in used_elsewhere]
    if not avail:
        return None
    new_state = state.clone()
    new_state.free_choice[fg.name][net] = rng.choice(avail)
    return new_state


def propose_move(rng, state, bundle_groups, free_groups):
    move_types = []
    if bundle_groups:
        move_types.append("bundle")
    if any(len(fg.nets) >= 2 for fg in free_groups):
        move_types.append("free_swap")
    if free_groups:
        move_types.append("free_move")
    if not move_types:
        return None
    kind = rng.choice(move_types)
    if kind == "bundle":
        return _propose_bundle_change(rng, state, rng.choice(bundle_groups), bundle_groups, free_groups)
    if kind == "free_swap":
        eligible = [fg for fg in free_groups if len(fg.nets) >= 2]
        return _propose_free_swap(rng, state, rng.choice(eligible))
    return _propose_free_move(rng, state, rng.choice(free_groups), bundle_groups, free_groups)


def _enum_free_groups(free_groups, used, idx=0, current=None):
    if current is None:
        current = {}
    if idx == len(free_groups):
        yield dict(current)
        return
    fg = free_groups[idx]
    avail = [p for p in fg.pads if p not in used]
    for perm in itertools.permutations(avail, len(fg.nets)):
        mapping = dict(zip(fg.nets, perm))
        current.update(mapping)
        yield from _enum_free_groups(free_groups, used | set(perm), idx + 1, current)
    for net in fg.nets:
        current.pop(net, None)


def exhaustive_search(bundle_groups, free_groups, fixed_assignment, board, model, ignore_re, w_cross, w_angle):
    best_state, best_result, best_cost = None, None, math.inf
    bundle_idx_ranges = [range(len(bg.options)) for bg in bundle_groups]
    for bundle_choice_tuple in itertools.product(*bundle_idx_ranges):
        bundle_used = set()
        conflict = False
        for bg, oi in zip(bundle_groups, bundle_choice_tuple):
            opt = bg.options[oi]
            if not bundle_used.isdisjoint(opt):
                conflict = True
                break
            bundle_used.update(opt)
        if conflict:
            continue
        bundle_choice = {bg.name: oi for bg, oi in zip(bundle_groups, bundle_choice_tuple)}
        for free_choice_flat in _enum_free_groups(free_groups, bundle_used):
            free_choice = {}
            for fg in free_groups:
                free_choice[fg.name] = {net: free_choice_flat[net] for net in fg.nets}
            state = SearchState(bundle_choice, free_choice)
            candidate = state.assignment(fixed_assignment, bundle_groups, free_groups)
            result = score_assignment(board, candidate, model, ignore_re)
            cost = optimize_cost(result, w_cross, w_angle)
            if cost < best_cost:
                best_state, best_result, best_cost = state, result, cost
    return best_state, best_result, best_cost


def annealing_search(bundle_groups, free_groups, fixed_assignment, board, model, ignore_re,
                      w_cross, w_angle, iters, restarts, seed):
    best_state, best_result, best_cost = None, None, math.inf
    for r in range(restarts):
        rng = random.Random(f"{seed}:{r}")
        state = build_initial_state(bundle_groups, free_groups, rng)
        if state is None:
            print(f"FAIL: could not construct a feasible initial assignment for groups.json "
                  f"(restart {r}); pools/options are too constrained", file=sys.stderr)
            sys.exit(3)
        candidate = state.assignment(fixed_assignment, bundle_groups, free_groups)
        result = score_assignment(board, candidate, model, ignore_re)
        cost = optimize_cost(result, w_cross, w_angle)
        cur_state, cur_result, cur_cost = state, result, cost
        if cur_cost < best_cost:
            best_state, best_result, best_cost = cur_state, cur_result, cur_cost

        t0, tend = 1.0, 0.001
        per_restart = max(iters // max(restarts, 1), 1)
        for i in range(per_restart):
            t = t0 * (tend / t0) ** (i / max(per_restart - 1, 1))
            new_state = propose_move(rng, cur_state, bundle_groups, free_groups)
            if new_state is None:
                continue
            candidate = new_state.assignment(fixed_assignment, bundle_groups, free_groups)
            result = score_assignment(board, candidate, model, ignore_re)
            cost = optimize_cost(result, w_cross, w_angle)
            delta = cost - cur_cost
            if delta <= 0 or rng.random() < math.exp(-delta / max(t, 1e-9)):
                cur_state, cur_result, cur_cost = new_state, result, cost
                if cur_cost < best_cost:
                    best_state, best_result, best_cost = cur_state, cur_result, cur_cost
    return best_state, best_result, best_cost


def cmd_optimize(board, args):
    model = "star" if args.star else "mst"
    ignore_re = compile_ignore_refs(args.ignore_refs)
    free_groups, bundle_groups = load_groups(board, args.groups)

    base_assignment = build_assignment(board, None)
    grouped_nets = set()
    for g in free_groups + bundle_groups:
        for net in g.nets:
            if net in grouped_nets:
                print(f"WARNING: net {net!r} appears in more than one group", file=sys.stderr)
            grouped_nets.add(net)
            if net not in base_assignment:
                print(f"WARNING: group {g.name!r} net {net!r} is not a routable MCU signal net", file=sys.stderr)

    fixed_assignment = {n: p for n, p in base_assignment.items() if n not in grouped_nets}
    fixed_pads = set(fixed_assignment.values())
    _drop_fixed_pads(free_groups, bundle_groups, fixed_pads)

    before_result = score_assignment(board, base_assignment, model, ignore_re)
    before_cost = optimize_cost(before_result, args.w_cross, args.w_angle)

    bundle_combo = 1
    for bg in bundle_groups:
        bundle_combo *= max(len(bg.options), 1)
    free_combo = 1
    for fg in free_groups:
        free_combo *= max(math.perm(len(fg.pads), len(fg.nets)), 1)
    est_combos = bundle_combo * free_combo

    if est_combos <= 50000:
        print(f"# exhaustive search, upper-bound estimate {est_combos} combinations", file=sys.stderr)
        best_state, best_result, best_cost = exhaustive_search(
            bundle_groups, free_groups, fixed_assignment, board, model, ignore_re, args.w_cross, args.w_angle
        )
        if best_state is None:
            print("FAIL: no globally-valid (pad-unique) combination exists for this groups.json", file=sys.stderr)
            sys.exit(3)
    else:
        iters = args.iters or 20000
        restarts = args.restarts or 6
        print(f"# simulated annealing with restarts, estimate {est_combos} > 50000, "
              f"iters={iters} restarts={restarts} seed={args.seed}", file=sys.stderr)
        best_state, best_result, best_cost = annealing_search(
            bundle_groups, free_groups, fixed_assignment, board, model, ignore_re,
            args.w_cross, args.w_angle, iters, restarts, args.seed
        )

    best_assignment = best_state.assignment(fixed_assignment, bundle_groups, free_groups)

    # Uniqueness guard (belt-and-suspenders on top of the search's own invariant).
    grouped_pads = [best_assignment[n] for n in grouped_nets]
    assert len(grouped_pads) == len(set(grouped_pads)), "INTERNAL: pad used twice in best_assignment"

    print(f"BEFORE: cost={before_cost:.4f} total_length_mm={before_result['total_length_mm']:.4f} "
          f"crossings={before_result['crossings']} angle_penalty={before_result['angle_penalty']}")
    print(f"AFTER:  cost={best_cost:.4f} total_length_mm={best_result['total_length_mm']:.4f} "
          f"crossings={best_result['crossings']} angle_penalty={best_result['angle_penalty']}")
    print(f"(cost = w_cross*crossings + length_mm + w_angle*angle_penalty, "
          f"w_cross={args.w_cross}, w_angle={args.w_angle})")

    print("\nDIFF (net: old pad(gpio) -> new pad(gpio)):")
    changed = False
    for net in sorted(grouped_nets):
        old_pad = base_assignment.get(net)
        new_pad = best_assignment.get(net)
        if old_pad != new_pad:
            changed = True
            og, ng = PAD_TO_GPIO.get(old_pad, "-"), PAD_TO_GPIO.get(new_pad, "-")
            print(f"  {net}: {old_pad}({og}) -> {new_pad}({ng})")
    if not changed:
        print("  (no change - base assignment already optimal within the searched groups)")

    if args.out:
        out = {
            "assign": best_assignment,
            "gpio": {n: PAD_TO_GPIO[p] for n, p in best_assignment.items() if p in PAD_TO_GPIO},
            "score": best_result,
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
        print(f"\nwrote best assignment to {args.out}")


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def cmd_report(board, args):
    model = "star" if args.star else "mst"
    ignore_re = compile_ignore_refs(args.ignore_refs)

    with open(args.assign, "r", encoding="utf-8") as f:
        data = json.load(f)
    assign_after = data.get("assign", data)

    base_assignment = build_assignment(board, None)
    full_after = dict(base_assignment)
    for net, pad in assign_after.items():
        if net in base_assignment:
            full_after[net] = int(pad)

    net_group = {}
    if args.groups:
        free_groups, bundle_groups = load_groups(board, args.groups)
        for g in free_groups + bundle_groups:
            for net in g.nets:
                net_group[net] = g.name

    def grp(net):
        return net_group.get(net, "(fixed)")

    before_edges = build_edges(board, base_assignment, model, ignore_re)
    after_edges = build_edges(board, full_after, model, ignore_re)
    before_len = {n: sum(dist(e.p1, e.p2) for e in before_edges.get(n, [])) for n in base_assignment}
    after_len = {n: sum(dist(e.p1, e.p2) for e in after_edges.get(n, [])) for n in full_after}

    rows = sorted(set(base_assignment) | set(full_after), key=lambda n: (grp(n), n))
    print(f"# model={model}")
    print(f"{'group':<16} {'net':<16}{'gpio_before':>11}{'gpio_after':>11}{'pad_before':>11}"
          f"{'pad_after':>10}{'len_before':>11}{'len_after':>11}")
    for net in rows:
        pb, pa = base_assignment.get(net), full_after.get(net)
        gb = PAD_TO_GPIO.get(pb, "-") if pb is not None else "-"
        ga = PAD_TO_GPIO.get(pa, "-") if pa is not None else "-"
        lb, la = before_len.get(net, 0.0), after_len.get(net, 0.0)
        marker = " *" if pb != pa else ""
        print(f"{grp(net):<16} {net:<16}{str(gb):>11}{str(ga):>11}{str(pb):>11}{str(pa):>10}"
              f"{lb:>11.4f}{la:>11.4f}{marker}")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default=BOARD_FILE, help="path to .kicad_pcb (default: MARV-V2.kicad_pcb)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("dump")

    sp = sub.add_parser("score")
    sp.add_argument("--assign", help="JSON dict net -> U20 pad number")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--w", type=float, default=10.0)
    sp.add_argument("--star", action="store_true", help="use the old direct-star model instead of the MST")
    sp.add_argument("--ignore-refs", help="regex; drop peripheral pads whose footprint ref matches (what-if)")

    op = sub.add_parser("optimize")
    op.add_argument("--groups", required=True)
    op.add_argument("--iters", type=int, default=0, help="annealing iterations across all restarts (default 20000)")
    op.add_argument("--restarts", type=int, default=0, help="annealing restarts (default 6)")
    op.add_argument("--out")
    op.add_argument("--w-cross", type=float, default=10.0, dest="w_cross")
    op.add_argument("--w-angle", type=float, default=5.0, dest="w_angle")
    op.add_argument("--seed", type=int, default=42)
    op.add_argument("--star", action="store_true")
    op.add_argument("--ignore-refs")

    rp = sub.add_parser("report")
    rp.add_argument("--assign", required=True, help="flat net->pad JSON, or optimize's {assign,gpio,score} JSON")
    rp.add_argument("--groups", help="optional groups.json, used only to label/sort rows by group")
    rp.add_argument("--star", action="store_true")
    rp.add_argument("--ignore-refs")

    args = ap.parse_args()
    board = BoardModel(args.board)

    if args.cmd == "dump":
        cmd_dump(board, args)
    elif args.cmd == "score":
        cmd_score(board, args)
    elif args.cmd == "optimize":
        cmd_optimize(board, args)
    elif args.cmd == "report":
        cmd_report(board, args)


if __name__ == "__main__":
    main()
