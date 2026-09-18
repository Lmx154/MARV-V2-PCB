#!/usr/bin/env python3
"""Check/apply the MARV DFM profile without regenerating board geometry."""
import argparse
import copy
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'config/dfm/jlcpcb.json'
TEMPLATE = PROFILE.with_suffix('.kicad_dru')
BEGIN = '# BEGIN MANAGED MARV JLCPCB DFM'
END = '# END MANAGED MARV JLCPCB DFM'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')


def tokens(text):
    return TOKEN.findall(text)


def children(text):
    """Direct child spans, respecting escaped strings; never reserialize geometry."""
    depth = 0
    start = None
    result = []
    for match in TOKEN.finditer(text):
        if match[0] == '(':
            if depth == 1:
                start = match.start()
            depth += 1
        elif match[0] == ')':
            depth -= 1
            if depth < 0:
                raise ValueError('Unbalanced KiCad expression')
            if depth == 1 and start is not None:
                result.append((start, match.end()))
    if depth:
        raise ValueError('Unbalanced KiCad expression')
    return result


def locate(text, key):
    matches = [(a, b) for a, b in children(text)
               if tokens(text[a:b])[1:1 + len(key)] == list(key)]
    if len(matches) > 1:
        raise ValueError(f'Duplicate KiCad setting: {key}')
    return matches[0] if matches else None


def node(text, *key):
    span = locate(text, key)
    if span is None:
        raise ValueError(f'Missing KiCad setting: {key}')
    return text[slice(*span)]


def replace_node(text, key, replacement, indent='\t\t'):
    span = locate(text, key)
    if span is not None:
        old = text[slice(*span)]
        if tokens(old) == tokens(replacement):
            return text  # preserve existing formatting and mtime on no-op
        return text[:span[0]] + replacement + text[span[1]:]
    end = text.rfind(')')
    return text[:end].rstrip() + '\n' + indent + replacement + '\n' + text[end:]


def board_settings(text, profile):
    general = node(text, 'general')
    thickness = float(tokens(node(general, 'thickness'))[2])
    if abs(thickness - profile['board_thickness_mm']) > 1e-6:
        raise ValueError('Profile requires the existing 1.6 mm MARV board')
    setup = node(text, 'setup')
    stack = node(setup, 'stackup')
    copper = {}
    for a, b in children(stack):
        part = stack[a:b]
        if tokens(part)[1] != 'layer':
            continue
        if tokens(node(part, 'type'))[2] == '"copper"':
            copper[json.loads(tokens(part)[2])] = float(tokens(node(part, 'thickness'))[2])
    expected = profile['copper_mm']
    if copper.keys() != expected.keys() or any(abs(copper[k] - expected[k]) > 1e-6 for k in copper):
        raise ValueError('Copper stackup differs; review the profile instead of changing the board stackup')
    for layer in ['F.Mask', 'B.Mask']:
        key = ('layer', json.dumps(layer))
        part = node(stack, *key)
        part = replace_node(part, ('color',), f'(color {json.dumps(profile["mask_color"])})', '\t\t\t\t')
        stack = replace_node(stack, key, part)
    stack = replace_node(stack, ('copper_finish',), f'(copper_finish {json.dumps(profile["finish"])})')
    setup = replace_node(setup, ('stackup',), stack)
    for key, value in profile['setup'].items():
        setup = replace_node(setup, (key,), value)
    return replace_node(text, ('setup',), setup)


def merge(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict):
            if key not in target:
                target[key] = {}
            if not isinstance(target[key], dict):
                raise ValueError(f'Unexpected project setting type: {key}')
            merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def project_settings(text, profile):
    original = json.loads(text)
    updated = copy.deepcopy(original)
    patch = copy.deepcopy(profile['project'])
    net_patch = patch.pop('net_settings')
    merge(updated, patch)
    nets = updated.setdefault('net_settings', {})
    managed = {c['name'] for c in net_patch['classes']} | set(profile['retired_classes'])
    extra_classes = [c for c in nets.get('classes', []) if c['name'] not in managed]
    existing = {c['name']: c for c in nets.get('classes', [])}
    classes = []
    for values in net_patch['classes']:
        entry = copy.deepcopy(existing.get(values['name'], existing.get('Default', {})))
        entry.update(values)
        classes.append(entry)
    nets['classes'] = classes + extra_classes
    extra_patterns = [p for p in nets.get('netclass_patterns', []) if p['netclass'] not in managed]
    nets['netclass_patterns'] = copy.deepcopy(net_patch['netclass_patterns']) + extra_patterns
    if updated == original:
        return text
    return json.dumps(updated, indent=2) + '\n'


def custom_rules(text, template):
    version = '(version 1)'
    if not template.startswith(version):
        raise ValueError('Expected version 1 custom-rule template')
    body = template[len(version):].strip()
    block = BEGIN + '\n' + body + '\n' + END
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
            raise ValueError('Malformed managed custom-rule markers')
        a, b = text.index(BEGIN), text.index(END) + len(END)
        return text[:a] + block + text[b:]
    if not text.strip() or text.strip() == template.strip():
        return version + '\n\n' + block + '\n'
    # Never discard an unrecognized rules file. Adopt it only after manual review.
    raise ValueError('Unmanaged custom rules exist; retain them outside a reviewed managed block')


def plan(project, profile, template):
    files = {project: project_settings, project.with_suffix('.kicad_pcb'): board_settings}
    changes = {}
    for path, transform in files.items():
        old = path.read_text()
        new = transform(old, profile)
        if new != old:
            changes[path] = (old, new)
    path = project.with_suffix('.kicad_dru')
    old = path.read_text() if path.exists() else ''
    new = custom_rules(old, template)
    if new != old:
        changes[path] = (old, new)
    return changes


def apply(changes, project):
    if not changes:
        return None
    for suffix in ['kicad_pro', 'kicad_pcb']:
        lock = project.parent / f'~{project.stem}.{suffix}.lck'
        if lock.exists():
            raise ValueError(f'Close KiCad before applying settings: {lock.name}')
    # Preflight every input before any writes; retain complete recovery copies.
    for path, (old, _) in changes.items():
        if (path.read_text() if path.exists() else '') != old:
            raise ValueError(f'File changed during review: {path}')
        if path.is_symlink():
            raise ValueError(f'Refusing to replace symlink: {path}')
    backup_root = project.parent / '.dfm-backups'
    backup_root.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='apply-', dir=backup_root))
    existed = {path: path.exists() for path in changes}
    for path in changes:
        if existed[path]:
            shutil.copy2(path, backup / path.name)
    replaced = []
    try:
        for path, (_, new) in changes.items():
            fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
            try:
                with os.fdopen(fd, 'w') as stream:
                    stream.write(new)
                os.chmod(temporary, path.stat().st_mode & 0o777 if existed[path] else 0o644)
                os.replace(temporary, path)
                replaced.append(path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    except OSError:
        for path in reversed(replaced):
            if existed[path]:
                shutil.copy2(backup / path.name, path)
            else:
                path.unlink()
        raise
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='read-only drift check (default)')
    mode.add_argument('--apply', action='store_true', help='apply managed settings with backups')
    parser.add_argument('--project', type=Path, default=ROOT / 'MARV-V2.kicad_pro')
    parser.add_argument('--diff', action='store_true', help='show proposed file diffs')
    parser.add_argument('--drc', action='store_true', help='also run DRC/parity; violations fail')
    args = parser.parse_args(argv)
    try:
        project = args.project.absolute()
        if project.suffix != '.kicad_pro':
            raise ValueError('--project must name a .kicad_pro file')
        profile = json.loads(PROFILE.read_text())
        changes = plan(project, profile, TEMPLATE.read_text())
        for path, (old, new) in changes.items():
            print(f'Settings differ: {path.name}')
            if args.diff:
                print(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                                 fromfile=str(path), tofile=str(path))), end='')
        if changes and not args.apply:
            print('Run --apply after reviewing differences. No files changed.')
            return 1
        if args.apply:
            backup = apply(changes, project)
            if backup:
                print(f'Applied {len(changes)} file(s). Recovery copies: {backup}')
        print('Managed DFM settings match. This does not certify the PCB.')
        if args.drc:
            out = project.parent / 'build/dfm'
            out.mkdir(parents=True, exist_ok=True)
            return subprocess.run(['kicad-cli', 'pcb', 'drc', '--schematic-parity',
                                   '--severity-all', '--exit-code-violations', '--format', 'json',
                                   '-o', str(out / 'drc.json'),
                                   str(project.with_suffix('.kicad_pcb'))], check=False).returncode
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f'DFM: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
