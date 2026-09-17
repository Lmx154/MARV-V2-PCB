#!/usr/bin/env python3
"""route_report.py - read-only routing-quality report for a ROUTED .kicad_pcb.

Usage:
  python3 tools/route_report.py BOARD.kicad_pcb [--json out.json] [--top N]
                                                 [--nets GLOB,...]

Loads BOARD via pcbnew.LoadBoard() only. Never calls any Save*/Write* API,
so the board file (and nothing else) is ever modified.

Per net with >=2 pads this reports: routed length (sum of track/arc lengths
in mm, plus via_count * VIA_NOMINAL_MM), segment count, via count, copper
layers used, the Euclidean MST length over the net's pad centres (Prim's
algorithm - the same helper tools/route_analysis.py's build_edges() uses,
imported from that module when importable, else a local reimplementation
of the identical algorithm), the detour ratio routed/MST, and a "fully
connected" flag.

The "fully connected" flag is computed with a local union-find over exact
integer-nanometre pad/segment/via geometry rather than
pcbnew.CONNECTIVITY_DATA's per-net accessors: CONNECTIVITY_DATA.GetConnectedPads()
was empirically found to return an empty PADS_VEC on this pcbnew build (10.0.6)
even for a synthetic two-pad net directly joined by a single track (verified
with a scratch in-memory BOARD), and RN_NET (the type GetRatsnestForNet()
returns) is not usable from Python (it comes back as a bare SwigPyObject with
no bound methods). CONNECTIVITY_DATA.GetUnconnectedCount() (board-wide, not
per-net) DID behave correctly in that same scratch test, so it is reported
once, board-wide, in the totals block as the authoritative pcbnew number;
the per-net flag is this script's own geometric reachability check (pads,
track/arc endpoints, and vias unioned on exact (x, y, copper-layer) keys;
a via unions every copper layer it spans, using the board's real stackup
order from BOARD.GetEnabledLayers().CuStack()). Caveat: two same-net
segments that happen to cross at an identical coordinate on two different
copper layers with no via there would be (incorrectly) treated as joined;
this is a rare coincidence and does not affect length/ratio numbers, only
the fully_connected flag.

Board totals: net counts (all / eligible >=2-pad / routed / unrouted),
the unrouted net list, total track length, total via count, vias per net
class, track count per copper layer, the pcbnew board-wide unconnected
count, and the --top worst detour ratios (restricted to nets with MST
length >= 5 mm) and --top longest nets by routed length.

A compact table for a named set of "critical" nets is always printed
(default: XIN,XOUT,XTAL_DRV,USB_D*,SENS_*,*_CS,*_INT*,SD_*,U7_SW,U26_SW,
U26_BST,U7_VO; override with --nets GLOB,...). Any matched net whose name
matches XIN, XOUT, XTAL_DRV or USB_D* is flagged with "!" if it has any
via or a detour ratio > 1.5.

Exits 0 unconditionally (errors go to stderr with a non-zero-looking
"FAIL:" prefix but the process still exits 0, per spec). --json writes the
full report to the given new path; no existing file is ever touched.
"""
import argparse
import fnmatch
import json
import math
import os
import sys
import traceback

VIA_NOMINAL_MM = 1.6
DEFAULT_CRITICAL = "XIN,XOUT,XTAL_DRV,USB_D*,SENS_*,*_CS,*_INT*,SD_*,U7_SW,U26_SW,U26_BST,U7_VO"
FLAG_GLOBS = ("XIN", "XOUT", "XTAL_DRV", "USB_D*")


# --------------------------------------------------------------------------
# MST helper: reuse tools/route_analysis.py's Prim's-algorithm implementation
# when importable (same module directory), else reimplement it locally.
# --------------------------------------------------------------------------

def _load_mst_impl():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import route_analysis as ra  # noqa: local sibling script
        return ra.dist, ra._prim_mst, "route_analysis"
    except Exception:
        def dist(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])

        def prim_mst(nodes):
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

        return dist, prim_mst, "local-reimplementation"


DIST, PRIM_MST, MST_SOURCE = _load_mst_impl()


def mst_length_mm(points):
    if len(points) < 2:
        return 0.0
    return sum(DIST(points[i], points[j]) for i, j in PRIM_MST(points))


# --------------------------------------------------------------------------
# Union-find for the local per-net "fully connected" geometric check.
# --------------------------------------------------------------------------

class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


# --------------------------------------------------------------------------
# Board analysis.
# --------------------------------------------------------------------------

def analyze(board_path):
    import pcbnew

    board = pcbnew.LoadBoard(board_path)
    cu_stack = list(board.GetEnabledLayers().CuStack())
    layer_name = {l: board.GetLayerName(l) for l in cu_stack}
    net_info = board.GetNetInfo()

    pad_points = {}       # net -> [(x_mm, y_mm), ...] one per pad
    pad_layer_nodes = {}  # net -> [[(x, y, layer), ...] per pad]
    uf_by_net = {}

    def uf_for(net):
        return uf_by_net.setdefault(net, UnionFind())

    for fp in board.GetFootprints():
        for p in fp.Pads():
            net = p.GetNetname()
            if not net:
                continue
            pos = p.GetPosition()
            x, y = pos.x / 1e6, pos.y / 1e6
            pad_points.setdefault(net, []).append((x, y))
            ls = p.GetLayerSet()
            pad_cu = [l for l in cu_stack if ls.Contains(l)]
            if not pad_cu:
                pad_cu = [cu_stack[0]]
            nodes = [(x, y, l) for l in pad_cu]
            pad_layer_nodes.setdefault(net, []).append(nodes)
            uf = uf_for(net)
            for other in nodes[1:]:
                uf.union(nodes[0], other)

    seg_length_mm = {}
    seg_count = {}
    via_count = {}
    layers_used = {}
    layer_track_count = {l: 0 for l in cu_stack}
    total_track_length_mm = 0.0
    total_vias = 0

    for t in board.GetTracks():
        net = t.GetNetname()
        if not net:
            continue
        uf = uf_for(net)
        if isinstance(t, pcbnew.PCB_VIA):
            via_count[net] = via_count.get(net, 0) + 1
            total_vias += 1
            pos = t.GetPosition()
            vx, vy = pos.x / 1e6, pos.y / 1e6
            top, bot = t.TopLayer(), t.BottomLayer()
            try:
                i0, i1 = cu_stack.index(top), cu_stack.index(bot)
            except ValueError:
                i0, i1 = 0, len(cu_stack) - 1
            lo, hi = min(i0, i1), max(i0, i1)
            span = cu_stack[lo:hi + 1]
            layers_used.setdefault(net, set()).update(span)
            first = (vx, vy, span[0])
            for l in span[1:]:
                uf.union(first, (vx, vy, l))
        else:
            layer = t.GetLayer()
            length_mm = t.GetLength() / 1e6
            seg_length_mm[net] = seg_length_mm.get(net, 0.0) + length_mm
            seg_count[net] = seg_count.get(net, 0) + 1
            layers_used.setdefault(net, set()).add(layer)
            if layer in layer_track_count:
                layer_track_count[layer] += 1
            total_track_length_mm += length_mm
            s, e = t.GetStart(), t.GetEnd()
            uf.union((s.x / 1e6, s.y / 1e6, layer), (e.x / 1e6, e.y / 1e6, layer))

    nets_report = {}
    for net, pads in pad_points.items():
        if len(pads) < 2:
            continue
        routed_mm = seg_length_mm.get(net, 0.0) + via_count.get(net, 0) * VIA_NOMINAL_MM
        mst_mm = mst_length_mm(pads)
        if mst_mm > 1e-9:
            ratio = routed_mm / mst_mm
        else:
            ratio = math.inf if routed_mm > 1e-9 else 0.0
        uf = uf_by_net.get(net)
        roots = set()
        if uf is not None:
            for nodes in pad_layer_nodes[net]:
                if nodes:
                    roots.add(uf.find(nodes[0]))
        fully_connected = len(roots) <= 1
        nets_report[net] = {
            "net": net,
            "pads": len(pads),
            "segments": seg_count.get(net, 0),
            "vias": via_count.get(net, 0),
            "routed_mm": routed_mm,
            "mst_mm": mst_mm,
            "ratio": ratio,
            "layers": sorted(layer_name.get(l, str(l)) for l in layers_used.get(net, ())),
            "fully_connected": fully_connected,
            "netclass": net_info.GetNetItem(net).GetNetClassName() if net_info.GetNetItem(net) else "",
        }

    vias_per_class = {}
    for net, n in via_count.items():
        ni = net_info.GetNetItem(net)
        cls = ni.GetNetClassName() if ni else "?"
        vias_per_class[cls] = vias_per_class.get(cls, 0) + n

    unconnected_overall = board.GetConnectivity().GetUnconnectedCount(False)

    return {
        "board_path": board_path,
        "mst_source": MST_SOURCE,
        "cu_stack": [layer_name[l] for l in cu_stack],
        "nets": nets_report,
        "all_net_count": len(pad_points),
        "total_track_length_mm": total_track_length_mm,
        "total_vias": total_vias,
        "vias_per_class": vias_per_class,
        "layer_track_count": {layer_name[l]: c for l, c in layer_track_count.items()},
        "unconnected_overall": unconnected_overall,
    }


# --------------------------------------------------------------------------
# Reporting / CLI.
# --------------------------------------------------------------------------

def match_any(name, globs):
    return any(fnmatch.fnmatch(name, g) for g in globs)


def print_report(result, top_n, critical_globs, json_path):
    nets = result["nets"]
    eligible = sorted(nets.values(), key=lambda r: r["net"])
    routed = [r for r in eligible if r["routed_mm"] > 1e-9]
    unrouted = [r["net"] for r in eligible if r["routed_mm"] <= 1e-9]
    not_fully_connected = [r["net"] for r in eligible if not r["fully_connected"]]

    print(f"# board={result['board_path']} mst_source={result['mst_source']} "
          f"cu_stack={'/'.join(result['cu_stack'])}")

    print("\n== BOARD TOTALS ==")
    print(f"all_nets(>=1 pad)={result['all_net_count']} eligible(>=2 pads)={len(eligible)} "
          f"routed={len(routed)} unrouted={len(unrouted)}")
    print(f"total_track_length_mm={result['total_track_length_mm']:.3f} "
          f"total_vias={result['total_vias']}")
    vpc = ", ".join(f"{k}={v}" for k, v in sorted(result["vias_per_class"].items())) or "(none)"
    print(f"vias_per_netclass: {vpc}")
    ltc = ", ".join(f"{k}={v}" for k, v in result["layer_track_count"].items())
    print(f"tracks_per_layer: {ltc}")
    print(f"unconnected_count (pcbnew, board-wide, GetUnconnectedCount)={result['unconnected_overall']}")
    print(f"not_fully_connected (local geometric check, per-net)={len(not_fully_connected)}")

    print(f"\n== UNROUTED NETS ({len(unrouted)}) ==")
    if unrouted:
        print(", ".join(unrouted[:max(top_n, 1) * 5]) +
              (" ..." if len(unrouted) > max(top_n, 1) * 5 else ""))
    else:
        print("(none)")

    worst = [r for r in eligible if r["mst_mm"] >= 5.0]
    worst.sort(key=lambda r: r["ratio"], reverse=True)
    print(f"\n== WORST DETOUR RATIOS (MST >= 5 mm), top {top_n} ==")
    print(f"{'net':<20}{'layers':<16}{'vias':>5}{'routed_mm':>11}{'mst_mm':>9}{'ratio':>8}")
    for r in worst[:top_n]:
        ratio_s = "inf" if math.isinf(r["ratio"]) else f"{r['ratio']:.2f}"
        print(f"{r['net']:<20}{'+'.join(r['layers']) or '-':<16}{r['vias']:>5}"
              f"{r['routed_mm']:>11.3f}{r['mst_mm']:>9.3f}{ratio_s:>8}")

    longest = sorted(eligible, key=lambda r: r["routed_mm"], reverse=True)
    print(f"\n== LONGEST NETS (routed length), top {top_n} ==")
    print(f"{'net':<20}{'layers':<16}{'vias':>5}{'routed_mm':>11}{'mst_mm':>9}{'ratio':>8}")
    for r in longest[:top_n]:
        ratio_s = "inf" if math.isinf(r["ratio"]) else f"{r['ratio']:.2f}"
        print(f"{r['net']:<20}{'+'.join(r['layers']) or '-':<16}{r['vias']:>5}"
              f"{r['routed_mm']:>11.3f}{r['mst_mm']:>9.3f}{ratio_s:>8}")

    print(f"\n== CRITICAL NETS ({', '.join(critical_globs)}) ==")
    print(f"{'net':<20}{'layers':<16}{'vias':>5}{'routed_mm':>11}{'mst_mm':>9}{'ratio':>8}  flag")
    all_names = sorted(result["nets"].keys())
    matched = [n for n in all_names if match_any(n, critical_globs)]
    if not matched:
        print("(no net names on this board match --nets)")
    for net in matched:
        r = nets.get(net)
        if r is None:
            print(f"{net:<20}{'(<2 pads or not on board)':<45}")
            continue
        ratio_s = "inf" if math.isinf(r["ratio"]) else f"{r['ratio']:.2f}"
        flagged = match_any(net, FLAG_GLOBS) and (r["vias"] > 0 or (not math.isinf(r["ratio"]) and r["ratio"] > 1.5))
        flag_s = "!" if flagged else ""
        print(f"{net:<20}{'+'.join(r['layers']) or '-':<16}{r['vias']:>5}"
              f"{r['routed_mm']:>11.3f}{r['mst_mm']:>9.3f}{ratio_s:>8}  {flag_s}")

    if json_path:
        out = {
            "board_path": result["board_path"],
            "mst_source": result["mst_source"],
            "cu_stack": result["cu_stack"],
            "totals": {
                "all_nets": result["all_net_count"],
                "eligible_nets": len(eligible),
                "routed_nets": len(routed),
                "unrouted_nets": unrouted,
                "total_track_length_mm": result["total_track_length_mm"],
                "total_vias": result["total_vias"],
                "vias_per_netclass": result["vias_per_class"],
                "tracks_per_layer": result["layer_track_count"],
                "unconnected_count_overall": result["unconnected_overall"],
            },
            "worst_detour_ratios": [
                {**r, "ratio": (None if math.isinf(r["ratio"]) else r["ratio"])} for r in worst[:top_n]
            ],
            "longest_nets": [
                {**r, "ratio": (None if math.isinf(r["ratio"]) else r["ratio"])} for r in longest[:top_n]
            ],
            "critical_nets": [
                {**nets[n], "ratio": (None if math.isinf(nets[n]["ratio"]) else nets[n]["ratio"])}
                for n in matched if n in nets
            ],
            "all_nets": [
                {**r, "ratio": (None if math.isinf(r["ratio"]) else r["ratio"])} for r in eligible
            ],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, sort_keys=True)
        print(f"\nwrote {json_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board", help="path to a .kicad_pcb file (read-only; never written)")
    ap.add_argument("--json", help="also write the full report as JSON to this new path")
    ap.add_argument("--top", type=int, default=10, help="size of the worst-ratio/longest-net lists (default 10)")
    ap.add_argument("--nets", default=DEFAULT_CRITICAL,
                     help=f"comma-separated globs for the critical-nets table (default: {DEFAULT_CRITICAL!r})")
    args = ap.parse_args()

    try:
        critical_globs = [g for g in args.nets.split(",") if g]
        result = analyze(args.board)
        print_report(result, args.top, critical_globs, args.json)
    except Exception as e:
        print(f"FAIL: {e!r}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
