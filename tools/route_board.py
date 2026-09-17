#!/usr/bin/env python3
"""Priority, multi-pass Freerouting pipeline for a KiCad board.

  python3 tools/route_board.py run --board B.kicad_pcb --passes-file passes.json \
      --work DIR [--out routed.kicad_pcb] [--mp 30] [--threads N] \
      [--exclude-nets GND,V3V3_SYS,V3V3_ANA] [--timeout 2400]

passes.json is an ordered list of pass definitions:

  [
    {"name": "priority", "nets": ["SENS_*", "*_CS", "*_INT*", "SD_*", "USB_*"], "lock": true},
    {"name": "rest",     "nets": ["*"], "exclude": ["GND"]}
  ]

A pass's optional "exclude" key overrides --exclude-nets for that pass only
(an empty list excludes nothing that pass); a pass without the key keeps
using the --exclude-nets default. See the --exclude-nets paragraph below.

For every pass, in order, this tool:
  1. Exports a Specctra DSN from the current board state (pass 1: --board;
     later passes: the .kicad_pcb produced by the previous pass).
  2. Rewrites the DSN so that only this pass's nets (plus nets that were
     already assigned to an earlier pass, which show up as existing wires)
     remain in the `(network ...)` section -- both the per-net `(net NAME
     (pins ...))` entries and the net lists inside every `(class ...)`.
     Nets that are dropped keep their physical pads (placement section is
     untouched) but lose their netlist entry, so Freerouting treats those
     pads as plain unrouted obstacles for this pass.
  3. Runs `freerouting` on the filtered DSN, capturing the log and parsing
     the final unrouted/violations counts from it.
  4. Imports the resulting .ses into a *copy* of the input board with
     `kicad-dsn import` (this also refills zones), then sets IsLocked(True) on
     *every* track and via on the board -- not just this pass's nets -- and
     re-saves the board (see lock_all_in_board for why).
  5. Runs `kicad-cli pcb drc --severity-error --format json` on the result
     and records the violation/unconnected counts.

--exclude-nets (default GND,V3V3_SYS,V3V3_ANA) removes the plane nets from
`(network ...)` and from every `(class ...)` in *every* pass, and with them
their `(plane ...)` entries.  Those nets are fanned out to the planes
beforehand by tools/stitch_planes.py, so the router has nothing left to do on
them; their pads, stitch tracks and stitch vias stay in the DSN as fixed,
netless obstacles (see filter_network).

At the end the last pass's board is copied to --out and a results table is
printed.

See the MUST VERIFY section of the task write-up (and the docstring of
`patch_wiring_fix_tags` below) for how track-locking is made to survive
into the next pass's Freerouting run.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_FREEROUTING = os.path.expanduser("~/.local/bin/freerouting")
DEFAULT_KICAD_DSN = os.path.expanduser("~/.local/bin/kicad-dsn")
DEFAULT_KICAD_CLI = "kicad-cli"


# --------------------------------------------------------------------------
# Minimal Specctra / generic s-expression parser & pretty-printer.
#
# The DSN format is whitespace-insensitive; the KiCad Specctra parser (and
# Freerouting's) doesn't care about line breaks or indentation, only about
# balanced parens and quoted strings ("space_in_quoted_tokens on" in the
# parser header means a quoted token may contain parens/spaces and is still
# a single atom). We round-trip the whole file through this to make the
# network/structure/wiring rewrites robust against manual regex mistakes.
# --------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Hand-rolled scanner (not a single regex) because of one Specctra
    quirk: the parser header's `(string_quote ")` declares the quote
    character by writing it *bare* (it can't quote itself before it has
    been declared) -- so a naive "everything between two quotes is one
    token" regex greedily eats everything up to the *next* real quoted
    string in the file. We special-case exactly that: a `"` immediately
    following the atom `string_quote` and immediately followed by `)` is
    the bare bootstrap atom, not the start of a quoted string.
    """
    tokens: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == "(":
            tokens.append("(")
            i += 1
            continue
        if c == ")":
            tokens.append(")")
            i += 1
            continue
        if c == '"':
            if tokens and tokens[-1] == "string_quote":
                k = i + 1
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k] == ")":
                    tokens.append('"')
                    i += 1
                    continue
            j = text.index('"', i + 1)
            tokens.append(text[i : j + 1])
            i = j + 1
            continue
        j = i
        while j < n and not text[j].isspace() and text[j] not in "()\"":
            j += 1
        tokens.append(text[i:j])
        i = j
    return tokens


def parse_sexpr(text: str):
    tokens = tokenize(text)
    pos = [0]

    def parse_one():
        tok = tokens[pos[0]]
        pos[0] += 1
        if tok == "(":
            lst = []
            while tokens[pos[0]] != ")":
                lst.append(parse_one())
            pos[0] += 1  # consume ')'
            return lst
        if tok == ")":
            raise ValueError("unbalanced parens in DSN")
        return tok

    result = parse_one()
    if pos[0] != len(tokens):
        raise ValueError(f"trailing tokens after top-level form ({len(tokens) - pos[0]} left)")
    return result


def dumps_sexpr(node, indent: int = 0, out: list[str] | None = None) -> str:
    """Serialize back to DSN text.

    Leading atoms (the tag and any bare-atom "arguments", e.g. `layer
    F.Cu`, `net GPS_RX`, `class kicad_default A B C`) are kept on the
    opening line, matching the pretty-printing Freerouting's own Specctra
    reader was tested against; sub-lists are indented on their own lines.
    A list made up entirely of atoms (e.g. `(pins A B C)`) collapses onto
    a single line. This is not just cosmetics: Freerouting's DSN reader
    (unlike KiCad's) silently fails to parse otherwise-valid whitespace
    when every child -- including the scope name right after a tag like
    `(layer` -- is pushed onto its own line; a failed parse makes it fall
    back to a bundled demo board without erroring out, which is worth
    knowing when trusting its output.
    """
    top = out is None
    if out is None:
        out = []
    pad = "  " * indent
    if isinstance(node, list):
        if not node:
            out.append(pad + "()")
        else:
            i = 0
            head_parts = []
            while i < len(node) and not isinstance(node[i], list):
                head_parts.append(str(node[i]))
                i += 1
            rest = node[i:]
            line = pad + "(" + " ".join(head_parts)
            if not rest:
                out.append(line + ")")
            else:
                out.append(line)
                for child in rest:
                    dumps_sexpr(child, indent + 1, out)
                out.append(pad + ")")
    else:
        out.append(pad + str(node))
    return "\n".join(out) if top else ""


def unquote(atom: str) -> str:
    if len(atom) >= 2 and atom.startswith('"') and atom.endswith('"'):
        return atom[1:-1]
    return atom


def find_child(tree: list, tag: str):
    """Return the first direct child list of `tree` whose head atom == tag."""
    for child in tree:
        if isinstance(child, list) and child and child[0] == tag:
            return child
    return None


# --------------------------------------------------------------------------
# DSN rewriting
# --------------------------------------------------------------------------


def collect_net_names(network_node: list) -> list[str]:
    names = []
    for child in network_node[1:]:
        if isinstance(child, list) and child and child[0] == "net":
            names.append(unquote(child[1]))
    return names


def filter_network(network_node: list, keep_nets: set[str]) -> tuple[list, list[str], int]:
    """Rewrite the `(network ...)` node in place-equivalent (returns a new node).

    Returns (new_node, dropped_net_names, dropped_class_count).

    What happens to a dropped net's copper, and why the excluded plane nets are
    safe to drop: the `(placement ...)`/`(library ...)` sections are untouched,
    so the pads are still there, and the `(wiring ...)` section still carries
    every stitch track/via with `(type fix)`.  Freerouting resolves the `(net
    NAME)` of a wire/via through Wiring.read_wire_scope/read_via_scope ->
    getSubnets(netId, rules), which looks the name up in the nets it built from
    `(network ...)`.  A name that is not there yields an empty net array and
    the item is inserted with *no* net, i.e. as a fixed obstacle; the reader
    then calls tryCorrectNet(), which only adopts a net from a touching item
    that has exactly one net -- and the pads of a dropped net have none either,
    so the stitch copper stays netless.  (Verified statically against the
    installed freerouting-executable.jar: Wiring.class references getSubnets,
    calcFixed, tryCorrectNet/assignNetNo exactly as described; no live routing
    run was made from this tool.)
    """
    new_children = [network_node[0]]
    dropped_nets = []
    dropped_classes = 0
    for child in network_node[1:]:
        if isinstance(child, list) and child and child[0] == "net":
            name = unquote(child[1])
            if name in keep_nets:
                new_children.append(child)
            else:
                dropped_nets.append(name)
            continue
        if isinstance(child, list) and child and child[0] == "class":
            # child = ["class", classname, net1, net2, ..., [sublist...], ...]
            new_class = [child[0], child[1]]
            kept_any = False
            for el in child[2:]:
                if isinstance(el, list):
                    new_class.append(el)
                elif unquote(el) in keep_nets:
                    new_class.append(el)
                    kept_any = True
                # else: drop this net name from the class
            if kept_any:
                new_children.append(new_class)
            else:
                dropped_classes += 1
            continue
        new_children.append(child)
    return new_children, dropped_nets, dropped_classes


def patch_layer_types(structure_node: list) -> list[str]:
    """Force inner-layer `(type signal)` -> `(type power)` if pcbnew ever emits
    an inner copper layer as signal. Returns human-readable notes.

    Empirically (KiCad 10.0.6, this board) In1.Cu/In2.Cu are user-named
    "GND"/"PWR" and pcbnew's ExportSpecctraDSN already emits them as
    `(type power)` -- so this is normally a no-op, kept as a safety net.
    """
    notes = []
    layer_entries = [c for c in structure_node[1:] if isinstance(c, list) and c and c[0] == "layer"]
    if len(layer_entries) <= 2:
        return notes
    inner = layer_entries[1:-1]
    for layer in inner:
        name = unquote(layer[1])
        type_node = find_child(layer, "type")
        if type_node is None:
            continue
        current = type_node[1]
        if current == "signal":
            type_node[1] = "power"
            notes.append(f"layer {name}: forced (type signal) -> (type power)")
        else:
            notes.append(f"layer {name}: already (type {current})")
    return notes


def drop_planes_of_dropped_nets(structure_node: list, keep_nets: set[str]) -> list[str]:
    """Remove `(plane NET ...)` for every NET this pass filtered out of
    `(network ...)`.

    pcbnew exports each filled zone as a Specctra `(plane NET (polygon
    LAYER ...))`.  filter_network() removes the nets this pass is not
    routing from `(network ...)`, but the planes stayed behind, and
    Freerouting then *invents* a net for a plane whose name it cannot find
    in the network -- and promptly reports the areas of that invented net
    as unconnected.

    That, and not the crystal routing, was the "2 unrouted" in the pass-1
    log.  This board has three GND zones (F.Cu, B.Cu, In1.Cu) and GND is not
    a pass-1 net, so Freerouting saw three disjoint GND conduction areas and
    wanted two connections between them.  Measured on the pass-1 DSN, the
    count is exactly (number of GND planes - 1):

        3 GND planes -> 2 unrouted     (as exported)
        2 GND planes -> 1 unrouted     (either outer plane removed)
        1 GND plane  -> 0 unrouted
        0 GND planes -> 0 unrouted

    while the routed result is unchanged: the `(network_out ...)` of the
    as-exported DSN and of the plane-free DSN are byte-identical, all three
    crystal nets fully routed on F.Cu in both.  So the planes were never a
    routing obstacle here -- they were corrupting the pipeline's only
    success metric, the unrouted count parsed out of the log.

    Keying the removal on `keep_nets` rather than on the layer keeps the
    planes of nets this pass *is* routing (pass 6's V3V3_SYS/V3V3_ANA, a
    trailing "*" pass's GND): for those the plane is real copper the router
    is supposed to reach, and an unrouted count against it is meaningful.
    Dropping the rest only changes the router's view -- the zones stay in
    the .kicad_pcb and `kicad-dsn import` refills them around whatever
    tracks came back, which is the normal "route first, pour afterwards"
    order.

    Returns human-readable notes.
    """
    notes: list[str] = []
    kept = [structure_node[0]]
    dropped: dict[str, int] = {}
    for child in structure_node[1:]:
        if isinstance(child, list) and child and child[0] == "plane":
            net = unquote(child[1])
            if net not in keep_nets:
                dropped[net] = dropped.get(net, 0) + 1
                continue
        kept.append(child)
    structure_node[:] = kept
    for net, n in sorted(dropped.items()):
        notes.append(f"dropped {n} (plane {net}) -- net not routed this pass")
    return notes


def patch_wiring_fix_tags(wiring_node: list, locked_nets: set[str]) -> int:
    """Safety net for the MUST VERIFY requirement.

    pcbnew's ExportSpecctraDSN already emits `(type fix)` on `(wire ...)` and
    `(via ...)` entries whose track/via has IsLocked()==True (verified: see
    report). This function is a defensive fallback in case a wire for a
    net that a previous pass locked comes through *without* a fix/protect
    tag (e.g. board round-tripped through a path that dropped the locked
    flag) -- it adds `(type fix)` itself. Returns the number of entries it
    had to patch (expected: 0, given the native mechanism above).
    """
    if wiring_node is None:
        return 0
    patched = 0
    for child in wiring_node[1:]:
        if not (isinstance(child, list) and child and child[0] in ("wire", "via")):
            continue
        net_node = find_child(child, "net")
        if net_node is None:
            continue
        name = unquote(net_node[1])
        if name not in locked_nets:
            continue
        type_node = find_child(child, "type")
        if type_node is not None and type_node[1] in ("fix", "protect"):
            continue
        if type_node is not None:
            type_node[1] = "fix"
        else:
            child.append(["type", "fix"])
        patched += 1
    return patched


def build_pass_dsn(raw_dsn_text: str, keep_nets: set[str], locked_nets: set[str]):
    """Parse raw_dsn_text, filter nets, patch layer types & fix tags.

    Returns (filtered_text, all_net_names, dropped_nets, dropped_classes,
             layer_notes, fix_patches).
    """
    tree = parse_sexpr(raw_dsn_text)
    pcb = tree
    structure = find_child(pcb, "structure")
    network = find_child(pcb, "network")
    wiring = find_child(pcb, "wiring")

    all_net_names = collect_net_names(network) if network else []

    layer_notes = patch_layer_types(structure) if structure else []
    if structure is not None:
        layer_notes += drop_planes_of_dropped_nets(structure, keep_nets)

    dropped_nets: list[str] = []
    dropped_classes = 0
    if network is not None:
        new_network, dropped_nets, dropped_classes = filter_network(network, keep_nets)
        idx = pcb.index(network)
        pcb[idx] = new_network

    fix_patches = patch_wiring_fix_tags(wiring, locked_nets)

    return dumps_sexpr(pcb), all_net_names, dropped_nets, dropped_classes, layer_notes, fix_patches


# --------------------------------------------------------------------------
# Freerouting log parsing
# --------------------------------------------------------------------------

_UNROUTED_RE = re.compile(r"\((\d+)\s+unrouted\s+and\s+(\d+)\s+violations\)")


def parse_freerouting_log(log_text: str):
    matches = _UNROUTED_RE.findall(log_text)
    if not matches:
        return None, None
    unrouted, violations = matches[-1]
    return int(unrouted), int(violations)


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


TIMEOUT_RC = 124  # same convention as coreutils timeout(1)


def run_cmd(cmd, log_path=None, cwd=None, timeout=None):
    """Run `cmd`, capture output, optionally enforce a wall-clock timeout.

    On timeout the child is killed, whatever it had written so far is kept in
    the log, and TIMEOUT_RC is returned -- callers distinguish that from a real
    non-zero exit, because a freerouting that ran out of time has usually
    written no .ses at all and the run must be reported as a failed pass rather
    than as "0 unrouted".
    """
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        rc, text = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        err = e.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        rc = TIMEOUT_RC
        text = out + err + f"\n[route_board] TIMEOUT after {timeout} s: {' '.join(map(str, cmd))}\n"
    if log_path:
        Path(log_path).write_text(text)
    return rc, text


def ensure_project_sibling(board_path: Path, master_pro: Path):
    """kicad-dsn/kicad-cli look for a <stem>.kicad_pro next to the board."""
    dest = board_path.with_suffix(".kicad_pro")
    if not dest.exists():
        shutil.copyfile(master_pro, dest)


def match_nets(patterns: list[str], net_names: list[str]) -> set[str]:
    matched = set()
    for pat in patterns:
        for name in net_names:
            if fnmatch.fnmatchcase(name, pat):
                matched.add(name)
    return matched


def lock_all_in_board(board_path: Path) -> tuple[int, int]:
    """Lock every track and via on the board. Returns (locked_now, total).

    This is the fix for the carry-over leak.  The pipeline used to lock only
    `this_pass_nets`, but Freerouting does not confine itself to the nets a
    pass asked for: it re-routes and re-shapes *any* wire it is given that is
    not marked `(type fix)`, and it hands the result back in the .ses.  KiCad's
    ImportSpecctraSES then replaces the board's tracks with the session's --
    so a track on a carried-over net that came back changed (or did not come
    back at all) was silently dropped.  Measured across p7 -> p8 of the 8-pass
    run: 12 V3V3_SYS segments lost.

    Locking everything after every import closes that: pcbnew exports a locked
    track/via as `(type fix)`, Freerouting treats fixed wires as immovable, and
    the next .ses returns them unchanged.  It also means a pass's `"lock":
    false` no longer disables locking -- the flag is kept in the pass file and
    reported, but it is now advisory only.
    """
    import pcbnew  # imported lazily; only needed for the lock step

    board = pcbnew.LoadBoard(str(board_path))
    try:
        tracks = list(board.GetTracks())
    except TypeError:
        tracks = []
    newly = 0
    for t in tracks:
        if not t.IsLocked():
            t.SetLocked(True)
            newly += 1
    pcbnew.SaveBoard(str(board_path), board)
    return newly, len(tracks)


def count_locked_in_board(board_path: Path, nets: set[str] | None = None):
    import pcbnew

    board = pcbnew.LoadBoard(str(board_path))
    try:
        tracks = board.GetTracks()
    except TypeError:
        tracks = []
    segs = []
    for t in tracks:
        if nets is not None and t.GetNetname() not in nets:
            continue
        segs.append((t.GetNetname(), t.IsLocked(), t.GetStart(), t.GetEnd(), t.GetLayerName()))
    return segs


def print_dry_run_pass(tag, p, this_pass_nets, excluded_here, dropped_nets, dropped_classes,
                       layer_notes, fix_patches, raw_dsn, filtered_dsn):
    nets_sorted = sorted(this_pass_nets)
    print(f"=== [DRY RUN] pass {tag}  (patterns={p['nets']!r}, lock={bool(p.get('lock'))}) ===")
    print(f"  nets routed this pass ({len(nets_sorted)}): {', '.join(nets_sorted) if nets_sorted else '(none)'}")
    print(f"  excluded plane nets matched by this pass ({len(excluded_here)}): "
          f"{', '.join(sorted(excluded_here)) if excluded_here else '(none)'}")
    print(f"  nets removed from network/classes: {len(dropped_nets)}  (dropped empty classes: {dropped_classes})")
    if layer_notes:
        print("  layer notes: " + "; ".join(layer_notes))
    print(f"  fix-tag safety patches applied: {fix_patches}")
    print(f"  unfiltered DSN written: {raw_dsn}")
    print(f"  filtered DSN written:   {filtered_dsn}")
    print(f"  (no freerouting call, no SES import -- dry run)")


def run_pipeline(args):
    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)

    board_in = Path(args.board).resolve()
    passes_file = Path(args.passes_file).resolve()
    passes = json.loads(passes_file.read_text())

    master_pro = board_in.with_suffix(".kicad_pro")
    if not master_pro.exists():
        sys.exit(f"project file not found next to board: {master_pro}")

    # Seed the pipeline with a private copy of the input board so we never
    # touch the caller's file.
    current_board = work / "00_input.kicad_pcb"
    shutil.copyfile(board_in, current_board)
    ensure_project_sibling(current_board, master_pro)

    kicad_dsn = args.kicad_dsn
    freerouting = args.freerouting
    kicad_cli = args.kicad_cli
    default_exclude_patterns = [n.strip() for n in (args.exclude_nets or "").split(",") if n.strip()]
    if default_exclude_patterns:
        print(f"[route_board] excluded by default: {', '.join(default_exclude_patterns)} "
              f"(plane nets; fanned out by tools/stitch_planes.py, kept as fixed obstacles) -- "
              f"a pass with its own \"exclude\" key overrides this default for that pass only")

    cumulative_routed: set[str] = set()
    cumulative_locked: set[str] = set()

    results = []

    for i, p in enumerate(passes, start=1):
        name = p["name"]
        tag = f"{i:02d}_{name}"
        t0 = time.time()

        # 1. export DSN from current board state
        raw_dsn = work / f"{tag}.raw.dsn"
        rc, log = run_cmd([sys.executable, kicad_dsn, "export", str(current_board), str(raw_dsn)])
        if rc != 0 or not raw_dsn.exists():
            sys.exit(f"[{tag}] DSN export failed (rc={rc}):\n{log}")

        raw_text = raw_dsn.read_text()

        # figure out which nets this pass matches (against the *current*
        # netlist, which never changes across passes but we recompute
        # defensively) and which nets are "already routed" (matched by an
        # earlier pass).
        #
        # `matched_nets` is the raw glob match against the *whole* board
        # netlist -- for a late "*" pass this is every net on the board,
        # including ones an earlier pass already claimed. `this_pass_nets`
        # subtracts those out: it is what this pass is newly responsible
        # for (reported in the summary table, used for locking), so a
        # carryover net someone already routed doesn't get double-counted
        # as "routed" again just because a later pass's pattern also
        # happens to match it. The filtered DSN's `keep_nets` still uses
        # the union (matched_nets | cumulative_routed, same set either way)
        # so carryover nets keep their wires/net entries in this pass's DSN.
        #
        # `excluded_nets` (--exclude-nets, default the plane nets) is
        # subtracted from both, in *every* pass: those nets are already fanned
        # out to the planes by tools/stitch_planes.py, so they must never enter
        # `(network ...)`, never enter a `(class ...)` net list, and -- through
        # keep_nets -- never keep a `(plane ...)`.
        #
        # A pass may carry its own `"exclude": [...]` key, which replaces
        # --exclude-nets for that pass only (an empty list means "exclude
        # nothing this pass"); every other pass keeps using the
        # --exclude-nets default.  Typical use: an early pass that must
        # route the plane nets' own fan-out stitching (e.g. the In2 nets)
        # sets `"exclude": []` for them, while the trailing "*" pass keeps
        # excluding GND so its plane's copper stays a fixed obstacle.
        exclude_patterns = p["exclude"] if "exclude" in p else default_exclude_patterns
        pcb_tmp = parse_sexpr(raw_text)
        network_tmp = find_child(pcb_tmp, "network")
        all_nets = collect_net_names(network_tmp) if network_tmp else []
        excluded_nets = match_nets(exclude_patterns, all_nets) if exclude_patterns else set()
        matched_nets = match_nets(p["nets"], all_nets) - excluded_nets
        excluded_here = match_nets(p["nets"], all_nets) & excluded_nets
        this_pass_nets = matched_nets - cumulative_routed
        keep_nets = (matched_nets | cumulative_routed) - excluded_nets

        # The excluded nets' own wires/vias must stay `(type fix)` even though
        # the nets are gone from the network -- see filter_network.
        filtered_text, _, dropped_nets, dropped_classes, layer_notes, fix_patches = build_pass_dsn(
            raw_text, keep_nets, cumulative_locked | excluded_nets
        )
        filtered_dsn = work / f"{tag}.dsn"
        filtered_dsn.write_text(filtered_text)

        if args.dry_run:
            # Everything up to here (export the unfiltered DSN, resolve this
            # pass's glob patterns against the board's real net names, build
            # the filtered DSN) is identical to a real run. What we skip is
            # exactly the two steps that touch the router / mutate a board:
            # the `freerouting` call and the .ses import. No pass_board is
            # produced, so `current_board` is left pointing at the same
            # (still-unrouted-by-us) input for the next iteration -- later
            # passes only differ in which nets are kept, not in placement or
            # wiring, which is why they're skipped by default.
            print_dry_run_pass(tag, p, this_pass_nets, excluded_here, dropped_nets, dropped_classes,
                               layer_notes, fix_patches, raw_dsn, filtered_dsn)
            cumulative_routed |= this_pass_nets
            cumulative_locked |= this_pass_nets
            results.append(dict(name=name, nets_routed=len(this_pass_nets),
                                excluded=len(excluded_here), dropped_nets=len(dropped_nets)))
            if not args.all_passes:
                print(f"\n[dry run] stopped after pass 1 of {len(passes)} (use --all-passes to process the rest)")
                return results
            continue

        # 3. run freerouting
        ses_path = work / f"{tag}.ses"
        log_path = work / f"{tag}.log"
        # --gui.enabled=false is not cosmetic, it is what makes the .ses
        # actually appear.  With the GUI enabled (the default in
        # ~/.config/freerouting/freerouting.json) batch mode saves through
        # BoardExportActions, whose last log line is "Saving '<file>'..." and
        # which reports the *outcome* only to the Swing status bar; the JVM
        # frequently exits before that writer has flushed, leaving a 0-byte
        # .ses and an exit code of 0.  Measured on one fixed DSN: 10 runs of
        # the GUI path produced 7 empty files and 3 good ones (and the 3 good
        # ones differed in size, 9659/9661/9667 -- the result was not even
        # stable), while 14 runs of the headless path produced 14 identical
        # 9679-byte files.  The headless path logs "Saving output file ...
        # (SES)..." / "Successfully saved output file ... (N bytes)" and
        # writes synchronously.
        #
        # -mt 1 is likewise not optional: with more than one thread
        # Freerouting itself logs "Multi-threaded route optimization is
        # broken and it is known to generate clearance violations".
        fr_cmd = [freerouting, "--gui.enabled=false",
                  "-de", str(filtered_dsn), "-do", str(ses_path),
                  "-mp", str(args.mp), "-mt", str(args.threads)]
        rc, fr_log = run_cmd(fr_cmd, log_path=log_path, timeout=args.timeout)
        unrouted, violations = parse_freerouting_log(fr_log)
        if rc == TIMEOUT_RC:
            sys.exit(
                f"[{tag}] PASS FAILED: freerouting exceeded --timeout {args.timeout} s and was killed "
                f"(last parsed progress: {unrouted} unrouted, {violations} violations). "
                f"No .ses was accepted and no board was written for this pass; the pipeline stops here "
                f"so the previous pass's board ({current_board}) stays the newest good state. "
                f"Raise --timeout or lower --mp; log: {log_path}"
            )

        # 4. import SES into a copy of the *pre-pass* board
        pass_board = work / f"{tag}.kicad_pcb"
        # Belt and braces for the truncated-.ses failure described above:
        # freerouting exits 0 whether or not the file was written, so the
        # exit code proves nothing.  Check the file itself.
        if ses_path.exists() and ses_path.stat().st_size == 0:
            sys.exit(
                f"[{tag}] freerouting wrote a 0-byte .ses and still exited {rc} "
                f"(log says {unrouted} unrouted, {violations} violations). "
                f"The unflushed-writer race should be ruled out by "
                f"--gui.enabled=false; see {log_path}"
            )
        if ses_path.exists():
            rc, imp_log = run_cmd(
                [sys.executable, kicad_dsn, "import", str(current_board), str(ses_path), "--out", str(pass_board)]
            )
            if rc != 0 or not pass_board.exists():
                sys.exit(f"[{tag}] SES import failed (rc={rc}):\n{imp_log}")
        else:
            sys.exit(f"[{tag}] freerouting produced no .ses (rc={rc}); see {log_path}")
        ensure_project_sibling(pass_board, master_pro)

        # Lock EVERYTHING, not just this pass's nets: see lock_all_in_board.
        locked_count, locked_total = lock_all_in_board(pass_board)
        cumulative_locked |= this_pass_nets | excluded_nets

        # 5. DRC
        drc_json = work / f"{tag}.drc.json"
        rc, drc_log = run_cmd(
            [kicad_cli, "pcb", "drc", "--severity-error", "--format", "json", "-o", str(drc_json), str(pass_board)]
        )
        drc_violations = drc_unconnected = None
        if drc_json.exists():
            try:
                data = json.loads(drc_json.read_text())
                # kicad-cli json schema: top-level {"violations":[{...}], "unconnected_items":[...]}
                drc_violations = len(data.get("violations", []))
                drc_unconnected = len(data.get("unconnected_items", []))
            except Exception as e:
                drc_log += f"\n[warn] could not parse {drc_json}: {e}"

        elapsed = time.time() - t0
        results.append(
            dict(
                name=name,
                nets_routed=len(this_pass_nets),
                excluded=len(excluded_here),
                dropped_nets=len(dropped_nets),
                dropped_classes=dropped_classes,
                unrouted=unrouted,
                fr_violations=violations,
                drc_violations=drc_violations,
                drc_unconnected=drc_unconnected,
                locked=locked_count,
                locked_total=locked_total,
                drc_json=str(drc_json),
                layer_notes=layer_notes,
                fix_patches=fix_patches,
                elapsed=elapsed,
                board=str(pass_board),
            )
        )

        cumulative_routed |= this_pass_nets
        current_board = pass_board

    if args.dry_run:
        print(f"\n[dry run] processed all {len(passes)} pass(es); no freerouting/.ses import ran, no board was written")
        return results

    out_path = Path(args.out).resolve() if args.out else (work / "routed.kicad_pcb")
    shutil.copyfile(current_board, out_path)
    ensure_project_sibling(out_path, master_pro)

    print_report(results, out_path)
    return results


def print_report(results, out_path):
    # "nets" is nets routed this pass = glob matches minus carry-over minus the
    # --exclude-nets plane nets; "excl" is how many of this pass's matches were
    # excluded plane nets.
    hdr = (f"{'pass':<12}{'nets':>6}{'excl':>6}{'unrouted':>10}{'fr_viol':>9}"
           f"{'drc_viol':>9}{'drc_unc':>9}{'locked':>8}{'time(s)':>9}")
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(
            f"{r['name']:<12}{r['nets_routed']:>6}{r.get('excluded', 0):>6}{str(r['unrouted']):>10}"
            f"{str(r['fr_violations']):>9}"
            f"{str(r['drc_violations']):>9}{str(r['drc_unconnected']):>9}{r['locked']:>8}{r['elapsed']:>9.1f}"
        )
    print()
    for r in results:
        if r["layer_notes"]:
            print(f"[{r['name']}] layer types: " + "; ".join(r["layer_notes"]))
        print(f"[{r['name']}] dropped nets from network: {r['dropped_nets']}, dropped empty classes: {r['dropped_classes']}, fix-tag safety patches: {r['fix_patches']}")
        print(f"[{r['name']}] locked after import: {r['locked']} newly locked of {r.get('locked_total')} tracks+vias on the board")
    last = results[-1] if results else {}
    print(
        f"\nfinal DRC ({last.get('drc_json')}): "
        f"{last.get('drc_violations')} violations, {last.get('drc_unconnected')} unconnected items"
    )
    print(f"final board: {out_path}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the multi-pass routing pipeline")
    r.add_argument("--board", required=True)
    r.add_argument("--passes-file", required=True)
    r.add_argument("--work", required=True)
    r.add_argument("--out", default=None)
    r.add_argument("--mp", type=int, default=30)
    r.add_argument(
        "--threads",
        type=int,
        default=1,
        help="value for freerouting's -mt. Default 1; >1 enables the optimizer's "
        "multi-threaded path, which freerouting itself warns is broken.",
    )
    r.add_argument(
        "--exclude-nets",
        default="GND,V3V3_SYS,V3V3_ANA",
        help="comma-separated net names/globs removed from (network)/(class)/(plane) in EVERY "
        "pass; their pads and (fixed) stitch copper stay in the DSN as netless obstacles. "
        "Pass an empty string to disable.",
    )
    r.add_argument(
        "--timeout",
        type=int,
        default=2400,
        help="wall-clock limit in seconds for each freerouting call; exceeding it fails the pass",
    )
    r.add_argument("--freerouting", default=DEFAULT_FREEROUTING)
    r.add_argument("--kicad-dsn", default=DEFAULT_KICAD_DSN)
    r.add_argument("--kicad-cli", default=DEFAULT_KICAD_CLI)
    r.add_argument(
        "--dry-run",
        action="store_true",
        help="export & filter DSNs only; skip the freerouting call and the .ses import entirely",
    )
    r.add_argument(
        "--all-passes",
        action="store_true",
        help="with --dry-run, process every pass instead of stopping after the first "
        "(later passes have no routed wires in a dry run, so they're identical in shape)",
    )

    args = p.parse_args()
    if args.cmd == "run":
        run_pipeline(args)


if __name__ == "__main__":
    main()
