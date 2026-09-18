# SPDX-License-Identifier: 0BSD
# See LICENSES/0BSD.txt at the repository root; provided AS IS.
"""Preservation and failure-path tests for settings-only edits; no KiCad required."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dfm', ROOT / 'tools/dfm.py')
dfm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dfm)


class DFMTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'copy.kicad_pro'
        for suffix in ['kicad_pro', 'kicad_pcb', 'kicad_dru']:
            self.project.with_suffix('.' + suffix).write_bytes((ROOT / ('MARV-V2.' + suffix)).read_bytes())
        self.profile = json.loads(dfm.PROFILE.read_text())
        self.template = dfm.TEMPLATE.read_text()

    def plan(self):
        return dfm.plan(self.project, self.profile, self.template)

    def test_current_profile_is_noop(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        self.assertEqual(self.plan(), {})
        self.assertIsNone(dfm.apply({}, self.project))
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()})

    def test_apply_preserves_user_settings_and_geometry(self):
        p = json.loads(self.project.read_text())
        p['board']['design_settings']['rules']['min_clearance'] = 0.05
        p['board']['design_settings']['drc_exclusions'] = ['owner exclusion']
        p['text_variables']['USER_NOTE'] = 'keep me'
        p['net_settings']['classes'][0]['pcb_color'] = 'rgba(255, 0, 0, 1.000)'
        p['net_settings']['classes'][0]['wire_width'] = 9
        custom = copy.deepcopy(p['net_settings']['classes'][0])
        custom['name'] = 'UserBus'
        p['net_settings']['classes'].append(custom)
        p['net_settings']['netclass_patterns'].append({'netclass': 'UserBus', 'pattern': 'USER_*'})
        self.project.write_text(json.dumps(p))
        board = self.project.with_suffix('.kicad_pcb')
        text = board.read_text().replace('(pad_to_mask_clearance 0)', '(pad_to_mask_clearance 0.05)')
        # Representative owner geometry, including parentheses/escaped quote in text.
        text = text.rstrip()[:-1] + '\n(segment (start 10 10) (end 20 20) (width 0.25) (layer "F.Cu"))\n(gr_text "owner (note) \\"" (at 1 2))\n)\n'
        board.write_text(text)
        outside_before = text.replace(dfm.node(text, 'setup'), '<setup>')
        original = {p.name: p.read_bytes() for p in [self.project, board]}
        changes = self.plan()
        backup = dfm.apply(changes, self.project)
        self.assertEqual(self.plan(), {})
        after = board.read_text()
        self.assertEqual(outside_before, after.replace(dfm.node(after, 'setup'), '<setup>'))
        updated = json.loads(self.project.read_text())
        self.assertEqual(updated['text_variables']['USER_NOTE'], 'keep me')
        self.assertEqual(updated['net_settings']['classes'][0]['pcb_color'], 'rgba(255, 0, 0, 1.000)')
        self.assertEqual(updated['net_settings']['classes'][0]['wire_width'], 9)
        self.assertEqual(updated['board']['design_settings']['drc_exclusions'], ['owner exclusion'])
        self.assertIn(custom, updated['net_settings']['classes'])
        self.assertIn({'netclass': 'UserBus', 'pattern': 'USER_*'}, updated['net_settings']['netclass_patterns'])
        for name, contents in original.items():
            self.assertEqual((backup / name).read_bytes(), contents)

    def test_custom_rules_survive_outside_managed_block(self):
        path = self.project.with_suffix('.kicad_dru')
        extra = '\n(rule "Owner rule" (constraint clearance (min 0.4mm)))\n'
        path.write_text(path.read_text() + extra)
        self.assertEqual(self.plan(), {})
        changed = self.template.replace('(min 0.45mm)', '(min 0.46mm)')
        result = dfm.custom_rules(path.read_text(), changed)
        self.assertTrue(result.endswith(extra))
        self.assertIn('(min 0.46mm)', result)

    def test_unknown_rules_and_broken_markers_refused(self):
        for value in ['(version 1)\n(rule "Owner")', dfm.BEGIN, dfm.END + dfm.BEGIN]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                dfm.custom_rules(value, self.template)

    def test_incompatible_stackup_refused_before_writes(self):
        board = self.project.with_suffix('.kicad_pcb')
        board.write_text(board.read_text().replace('(thickness 0.035)', '(thickness 0.07)'))
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        with self.assertRaisesRegex(ValueError, 'stackup differs'):
            self.plan()
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.iterdir()})

    def test_missing_board_prevents_project_write(self):
        old = self.project.read_bytes()
        self.project.with_suffix('.kicad_pcb').unlink()
        with self.assertRaises(OSError):
            self.plan()
        self.assertEqual(self.project.read_bytes(), old)

    def test_open_editor_and_concurrent_edits_refused(self):
        new = self.project.read_text().replace('0.15', '0.16')
        changes = {self.project: (self.project.read_text(), new)}
        lock = self.root / '~copy.kicad_pcb.lck'
        lock.touch()
        with self.assertRaisesRegex(ValueError, 'Close KiCad'):
            dfm.apply(changes, self.project)
        lock.unlink()
        self.project.write_text(self.project.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'changed during review'):
            dfm.apply(changes, self.project)

    def test_partial_write_failure_rolls_back(self):
        board = self.project.with_suffix('.kicad_pcb')
        before = {p: p.read_text() for p in [self.project, board]}
        changes = {p: (old, old + '\n') for p, old in before.items()}
        real_replace = dfm.os.replace
        calls = 0

        def fail_second(src, dst):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected write failure')
            return real_replace(src, dst)

        with patch.object(dfm.os, 'replace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'injected'):
                dfm.apply(changes, self.project)
        for path, old in before.items():
            self.assertEqual(path.read_text(), old)


if __name__ == '__main__':
    unittest.main()
