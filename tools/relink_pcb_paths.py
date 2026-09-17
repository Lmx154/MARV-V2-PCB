#!/usr/bin/env python3
"""Re-point every footprint in MARV-V2.kicad_pcb at the symbol it now belongs to.

pcbnew links a footprint to its schematic symbol by the hierarchical path

    (path "/<sheet-uuid>/<symbol-uuid>")

so MOVING A SYMBOL TO A DIFFERENT SHEET orphans its footprint: the symbol uuid
is unchanged (tools/build_power.py derives it from the reference designator) but
the sheet half now names a sheet the symbol is no longer on.  A stale path is
not a loud failure - pcbnew simply treats the footprint as "not in the
schematic" on the next update, and offers to delete it.

This script reads the REGENERATED sheets (not the generator's internals, so it
is an independent check of them), builds reference -> "/sheet/symbol", and
rewrites ONLY the path string of each footprint whose Reference matches.  A byte
diff of the board therefore shows nothing but path lines.

It refuses, with a non-zero exit, if any reference is in the board but not the
schematic or the other way round - that mismatch means the board and the
schematic have genuinely diverged and a blind rewrite would hide it.

Usage:  python3 tools/relink_pcb_paths.py [--dry-run]
Standard library only.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PCB = ROOT / 'MARV-V2.kicad_pcb'
ROOT_SCH = ROOT / 'MARV-V2.kicad_sch'

SYM = re.compile(r'\(symbol\s+\(lib_id\s', re.S)
FP = re.compile(r'\(footprint\s')
UUID = re.compile(r'\(uuid\s+"?([0-9a-fA-F-]{36})"?\s*\)')
REF_PROP = re.compile(r'\(property\s+"Reference"\s+"([^"]*)"')
PATH_PROP = re.compile(r'\(path\s+"([^"]*)"\s*\)')


def block(text, start):
    """Source slice of the s-expression that begins at `start`."""
    depth, i, n = 0, start, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1], i + 1
        i += 1
    raise ValueError('unbalanced s-expression at %d' % start)


def sheet_files():
    """The child sheets the root actually instantiates, in page order."""
    text = ROOT_SCH.read_text()
    return re.findall(r'\(property\s+"Sheetfile"\s+"([^"]+)"', text)


def schematic_paths():
    """reference -> "/<sheet uuid>/<symbol uuid>" for every real symbol."""
    out, dupes = {}, []
    for name in sheet_files():
        text = (ROOT / name).read_text()
        sheet_uuid = UUID.search(text).group(1)          # the sheet's own uuid
        for m in SYM.finditer(text):
            src, _ = block(text, m.start())
            ref = REF_PROP.search(src)
            uid = UUID.search(src)
            if not ref or not uid:
                continue
            ref = ref.group(1)
            if ref.startswith('#'):                      # power symbols, PWR_FLAG
                continue
            if ref in out:
                dupes.append(ref)
            out[ref] = '/%s/%s' % (sheet_uuid, uid.group(1))
    if dupes:
        sys.exit('duplicate reference(s) in the schematic: %s' % ', '.join(sorted(set(dupes))))
    return out


def main():
    dry = '--dry-run' in sys.argv
    want = schematic_paths()
    text = PCB.read_text()
    edits, board_refs, unmatched = [], set(), []
    pos = 0
    while True:
        m = FP.search(text, pos)
        if not m:
            break
        src, pos = block(text, m.start())
        ref = REF_PROP.search(src)
        pm = PATH_PROP.search(src)
        if not ref or not pm:
            unmatched.append('footprint at offset %d has no Reference or no (path ...)' % m.start())
            continue
        ref = ref.group(1)
        board_refs.add(ref)
        if ref not in want:
            continue
        old = pm.group(1)
        if old != want[ref]:
            edits.append((m.start() + pm.start(1), m.start() + pm.end(1), ref, old, want[ref]))
    missing_sch = sorted(board_refs - set(want))
    missing_pcb = sorted(set(want) - board_refs)
    if unmatched or missing_sch or missing_pcb:
        for line in unmatched:
            print('ERROR: ' + line, file=sys.stderr)
        if missing_sch:
            print('ERROR: on the board but not in the schematic: %s'
                  % ', '.join(missing_sch), file=sys.stderr)
        if missing_pcb:
            print('ERROR: in the schematic but not on the board: %s'
                  % ', '.join(missing_pcb), file=sys.stderr)
        return 1
    for start, end, ref, old, new in reversed(edits):
        text = text[:start] + new + text[end:]
    if not dry:
        PCB.write_text(text)
    print('%d footprints, %d relinked, 0 unmatched%s'
          % (len(board_refs), len(edits), ' (dry run)' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
