#!/usr/bin/env python3
"""Audit every component in the KiCad XML netlist for PCB-layout readiness.

For each <comp> in a `kicad-cli sch export netlist --format kicadxml` export,
checks: footprint assigned, footprint resolvable (via the project and global
fp-lib-table, following nested "Table" type entries such as KiCad 10's
default global table), .kicad_mod file present, referenced 3D model(s)
present, and footprint pad count vs. symbol pin count (from the netlist's
<libparts> section). Pads with a non-numeric designator (mounting/shield
pads like "MP", "SH", "SHIELD") only count toward the pin-count comparison
if the symbol has a pin with that same designator; otherwise they're
mechanical, not electrical, and are excluded from the comparison (the raw,
unfiltered pad count is still available in --json output).

Usage:
    python3 tools/audit_footprints.py [NETLIST_XML] [--json OUT.json] [--no-fail]

    NETLIST_XML defaults to reports/power-netlist.xml (relative to the
    current directory). Regenerate it first, e.g. into a scratch location
    while the schematic is in flux:

        kicad-cli sch export netlist MARV-V2.kicad_sch --format kicadxml -o /path/to/scratch/netlist.xml
        python3 tools/audit_footprints.py /path/to/scratch/netlist.xml

Prints a markdown table (Ref | Value | Symbol | Footprint | FP file | 3D
model | Status) sorted by status then reference, a per-status summary count,
and a deduplicated list of footprints needing action with the refs that use
them. Exits non-zero if any component is not OK, unless --no-fail is given.
Standard library only; no third-party packages.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STATUS_ORDER = ['OK', 'NO_FOOTPRINT', 'FP_NOT_FOUND', 'NO_3D_REF', '3D_FILE_MISSING', 'PIN_MISMATCH']
# Severity order used to pick a single Status per row when more than one issue applies.
STATUS_PRIORITY = ['NO_FOOTPRINT', 'FP_NOT_FOUND', '3D_FILE_MISSING', 'NO_3D_REF', 'PIN_MISMATCH', 'OK']

MPN_FIELDS = {'mpn'}
MANUFACTURER_FIELDS = {'manufacturer', 'mfr', 'mfg'}
PARTNUM_FIELDS = {'part number', 'partnumber', 'part_number', 'manufacturer part number',
                   'manufacturer_part_number', 'mfr part number', 'mfr_pn'}

GLOBAL_FP_LIB_TABLE_CANDIDATES = [
    Path.home() / '.config/kicad/10.0/fp-lib-table',
    Path.home() / '.config/kicad/9.0/fp-lib-table',
]

DEFAULT_ENV_FALLBACKS = {
    'KICAD10_FOOTPRINT_DIR': '/usr/share/kicad/footprints',
    'KICAD10_3DMODEL_DIR': '/usr/share/kicad/3dmodels',
    'KICAD9_FOOTPRINT_DIR': '/usr/share/kicad/footprints',
    'KICAD9_3DMODEL_DIR': '/usr/share/kicad/3dmodels',
}

# ---- minimal s-expression reader, shared by fp-lib-table and .kicad_mod parsing ----

TOKEN_RE = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')


def parse_sexpr(text):
    toks = TOKEN_RE.findall(text)
    stack, root = [], None
    for tok in toks:
        if tok == '(':
            node = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
        elif tok == ')':
            root = stack.pop()
        else:
            stack[-1].append(tok)
    return root


def unquote(s):
    return json.loads(s) if s.startswith('"') else s


def first(node, key):
    return next((v for v in node if isinstance(v, list) and v and v[0] == key), None)


def walk(node):
    if isinstance(node, list):
        yield node
        for child in node:
            yield from walk(child)


def natural_key(ref):
    m = re.match(r'^([A-Za-z_#]*)(\d+)?(.*)$', ref or '')
    if not m:
        return (ref or '', -1, '')
    prefix, num, rest = m.groups()
    return (prefix, int(num) if num else -1, rest)


# ---- environment / fp-lib-table resolution ----

def build_env():
    env = dict(os.environ)
    env['KIPRJMOD'] = str(ROOT)
    for var, default in DEFAULT_ENV_FALLBACKS.items():
        env.setdefault(var, default)
    return env


def expand_vars(text, env):
    def repl(m):
        return env.get(m.group(1), m.group(0))
    return re.sub(r'\$\{([^}]+)\}', repl, text)


def merge_fp_lib_table(path, dest, visited, env):
    """Merge lib nickname -> expanded directory URI into dest. Entries whose
    type is "Table" point at another fp-lib-table file; that file's entries
    are merged inline under their own names (not nested under the parent
    entry's nickname), matching how KiCad 10's default global table is a
    single "Table" entry pointing at the real ~150-library list."""
    if path is None or not path.exists():
        return
    resolved = path.resolve()
    if resolved in visited:
        return
    visited.add(resolved)
    try:
        tree = parse_sexpr(path.read_text())
    except (OSError, UnicodeDecodeError):
        return
    if tree is None:
        return
    for node in walk(tree):
        if not (node and node[0] == 'lib'):
            continue
        name_node, type_node, uri_node = first(node, 'name'), first(node, 'type'), first(node, 'uri')
        if not name_node or not uri_node:
            continue
        name = unquote(name_node[1])
        typ = unquote(type_node[1]) if type_node else ''
        uri = expand_vars(unquote(uri_node[1]), env)
        if typ.strip().lower() == 'table':
            merge_fp_lib_table(Path(uri), dest, visited, env)
        elif name not in dest:
            dest[name] = uri


def load_fp_lib_table(env):
    dest = {}
    visited = set()
    # Project table takes priority over the global table on name collisions.
    merge_fp_lib_table(ROOT / 'fp-lib-table', dest, visited, env)
    for candidate in GLOBAL_FP_LIB_TABLE_CANDIDATES:
        if candidate.exists():
            merge_fp_lib_table(candidate, dest, visited, env)
            break
    return dest


# ---- .kicad_mod inspection ----

FP_CACHE = {}


def inspect_footprint(fp_path, env):
    """Return (pad_numbers set, [(model_path, exists), ...]) for a .kicad_mod file."""
    key = str(fp_path)
    if key in FP_CACHE:
        return FP_CACHE[key]
    try:
        tree = parse_sexpr(fp_path.read_text())
    except (OSError, UnicodeDecodeError):
        result = (set(), [])
        FP_CACHE[key] = result
        return result
    pads = set()
    models = []
    if tree is not None:
        for node in walk(tree):
            if node and node[0] == 'pad' and len(node) > 1 and isinstance(node[1], str):
                num = unquote(node[1])
                if num != '':
                    pads.add(num)
            elif node and node[0] == 'model' and len(node) > 1 and isinstance(node[1], str):
                raw = unquote(node[1])
                model_path = Path(expand_vars(raw, env))
                models.append((str(model_path), model_path.exists()))
    result = (pads, models)
    FP_CACHE[key] = result
    return result


# ---- netlist parsing ----

def get_field(fields, candidates):
    for name, value in fields.items():
        if name.strip().lower() in candidates and value:
            return value
    return ''


def parse_netlist(xml_path):
    root = ET.parse(xml_path).getroot()
    components_el = root.find('components')
    if components_el is None:
        raise SystemExit(f'{xml_path}: no <components> section (not a kicadxml netlist export?)')

    libpart_pins = {}
    libparts_el = root.find('libparts')
    if libparts_el is not None:
        for lp in libparts_el.findall('libpart'):
            key = (lp.get('lib'), lp.get('part'))
            nums = set()
            pins_el = lp.find('pins')
            if pins_el is not None:
                for pin in pins_el.findall('pin'):
                    num = pin.get('num')
                    if num:
                        nums.add(num)
            libpart_pins[key] = nums

    comps = []
    for c in components_el.findall('comp'):
        ref = c.get('ref')
        value_el = c.find('value')
        value = (value_el.text or '') if value_el is not None else ''
        fp_el = c.find('footprint')
        footprint = (fp_el.text or '').strip() if fp_el is not None else ''
        libsource = c.find('libsource')
        lib = libsource.get('lib') if libsource is not None else ''
        part = libsource.get('part') if libsource is not None else ''
        sheet = ''
        for prop in c.findall('property'):
            if prop.get('name') == 'Sheetname':
                sheet = prop.get('value', '')
                break
        fields = {}
        fields_el = c.find('fields')
        if fields_el is not None:
            for f in fields_el.findall('field'):
                fields[f.get('name', '')] = (f.text or '').strip()
        comps.append({
            'ref': ref,
            'value': value.strip(),
            'lib': lib,
            'part': part,
            'symbol': f'{lib}:{part}',
            'footprint': footprint,
            'sheet': sheet,
            'mpn': get_field(fields, MPN_FIELDS),
            'manufacturer': get_field(fields, MANUFACTURER_FIELDS),
            'part_number': get_field(fields, PARTNUM_FIELDS),
            'pin_count': len(libpart_pins.get((lib, part), set())) if (lib, part) in libpart_pins else None,
        })
    return comps, libpart_pins


# ---- per-component resolution ----

def md_escape(text):
    return (text or '').replace('|', '\\|').replace('\n', ' ')


def resolve_component(comp, fp_table, env, pin_nums):
    """pin_nums is the symbol's set of pin numbers (from <libparts>), or None
    if no libpart data is available for this component's lib:part."""
    row = dict(comp)
    row['fp_file_cell'] = '—'
    row['model_cell'] = '—'
    row['fp_path'] = None
    row['fp_resolved'] = False
    row['pad_count'] = None
    row['pad_count_raw'] = None
    row['models'] = []
    issues = set()

    footprint = comp['footprint']
    if not footprint:
        issues.add('NO_FOOTPRINT')
        row['status'] = 'NO_FOOTPRINT'
        return row

    if ':' not in footprint:
        issues.add('FP_NOT_FOUND')
        row['fp_file_cell'] = "malformed footprint field (no 'lib:name')"
        row['status'] = 'FP_NOT_FOUND'
        return row

    fp_lib, fp_name = footprint.split(':', 1)
    lib_dir = fp_table.get(fp_lib)
    if lib_dir is None:
        issues.add('FP_NOT_FOUND')
        row['fp_file_cell'] = f"library '{fp_lib}' not in fp-lib-table"
        row['status'] = 'FP_NOT_FOUND'
        return row

    fp_path = Path(lib_dir) / f'{fp_name}.kicad_mod'
    if not fp_path.exists():
        issues.add('FP_NOT_FOUND')
        row['fp_file_cell'] = f'{fp_lib}.pretty/{fp_name}.kicad_mod not found'
        row['status'] = 'FP_NOT_FOUND'
        return row

    row['fp_path'] = str(fp_path)
    row['fp_resolved'] = True
    pads, models = inspect_footprint(fp_path, env)
    row['pad_count_raw'] = len(pads)
    # Pads with a purely numeric designator always count. Pads with a
    # non-numeric designator (mounting/shield pads like "MP", "SH",
    # "SHIELD") only count toward the mismatch check if the symbol itself
    # has a pin with that same designator; otherwise they're mechanical,
    # not electrical, and are excluded. When no libpart pin data is
    # available at all, fall back to the raw pad count unfiltered.
    if pin_nums is None:
        effective_pads = pads
    else:
        effective_pads = {p for p in pads if p.isdigit() or p in pin_nums}
    row['pad_count'] = len(effective_pads)
    row['models'] = [{'path': p, 'exists': e} for p, e in models]

    pin_count = comp['pin_count']
    pin_note = f' / {pin_count} pins' if pin_count is not None else ''
    row['fp_file_cell'] = f'{fp_name}.kicad_mod ({len(effective_pads)} pads{pin_note})'

    if not models:
        issues.add('NO_3D_REF')
        row['model_cell'] = '(no 3D model referenced)'
    else:
        missing = [p for p, e in models if not e]
        if missing:
            issues.add('3D_FILE_MISSING')
            row['model_cell'] = ', '.join(
                f'{Path(p).name} MISSING' if not e else Path(p).name for p, e in models)
        else:
            row['model_cell'] = ', '.join(Path(p).name for p, _ in models)

    if pin_count is not None and pin_count != len(effective_pads):
        issues.add('PIN_MISMATCH')

    row['status'] = next(s for s in STATUS_PRIORITY if s in issues) if issues else 'OK'
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('netlist', nargs='?', default='reports/power-netlist.xml',
                     help='kicadxml netlist export (default: reports/power-netlist.xml)')
    ap.add_argument('--json', metavar='PATH', help='also write machine-readable results to PATH')
    ap.add_argument('--no-fail', action='store_true', help='exit 0 even if issues are found')
    args = ap.parse_args()

    xml_path = Path(args.netlist)
    if not xml_path.exists():
        print(f'error: netlist not found: {xml_path}', file=sys.stderr)
        sys.exit(2)

    env = build_env()
    fp_table = load_fp_lib_table(env)
    comps, libpart_pins = parse_netlist(xml_path)
    rows = [resolve_component(c, fp_table, env, libpart_pins.get((c['lib'], c['part'])))
            for c in comps]
    rows.sort(key=lambda r: (STATUS_ORDER.index(r['status']), natural_key(r['ref'])))

    print('| Ref | Value | Symbol | Footprint | FP file | 3D model | Status |')
    print('| --- | --- | --- | --- | --- | --- | --- |')
    for r in rows:
        print('| {} | {} | {} | {} | {} | {} | {} |'.format(
            md_escape(r['ref']), md_escape(r['value']), md_escape(r['symbol']),
            md_escape(r['footprint']) or '\u2014', md_escape(r['fp_file_cell']),
            md_escape(r['model_cell']), r['status']))

    counts = {s: 0 for s in STATUS_ORDER}
    for r in rows:
        counts[r['status']] += 1
    print()
    print('## Summary')
    print()
    print('| Status | Count |')
    print('| --- | --- |')
    for s in STATUS_ORDER:
        print(f'| {s} | {counts[s]} |')
    print()
    total_issues = len(rows) - counts['OK']
    print(f'Total components: {len(rows)}; OK: {counts["OK"]}; needing action: {total_issues}')

    needing_action = {}
    for r in rows:
        if r['status'] == 'OK':
            continue
        key = r['footprint'] if r['footprint'] else f"(no footprint \u2014 symbol {r['symbol']})"
        needing_action.setdefault(key, []).append(r['ref'])

    print()
    print('## Footprints needing action')
    print()
    if not needing_action:
        print('None.')
    else:
        for fp in sorted(needing_action):
            refs = sorted(needing_action[fp], key=natural_key)
            print(f'- `{fp}`: {", ".join(refs)}')

    if args.json:
        json_path = Path(args.json)
        json_path.write_text(json.dumps({
            'netlist': str(xml_path),
            'components': rows,
            'summary': counts,
            'footprints_needing_action': needing_action,
        }, indent=2))
        print(f'\nJSON written to {json_path}', file=sys.stderr)

    if total_issues and not args.no_fail:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
