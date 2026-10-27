#!/usr/bin/env python3
"""Run the project checks and write a static, self-contained results site to site/.

Usage: python3 tools/build_site.py

Runs the input-power ngspice simulation, the power-netlist check, KiCad DRC/ERC and
the footprint audit against the saved design, then writes site/index.html with all
data, CSS and SVG inline (no external scripts or fonts). The two board renders are
copied from images/pcb/ into site/. Needs Python 3 (standard library only), kicad-cli
and ngspice. A check that cannot run is shown as "could not run" on the page; the
script exits non-zero only if it crashes. Nothing in the design is modified.
"""
import bisect
import contextlib
import html
import io
import json
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
SITE = ROOT / 'site'
SCH = ROOT / 'MARV-V2.kicad_sch'
PCB = ROOT / 'MARV-V2.kicad_pcb'
GITHUB = 'https://github.com/Lmx154/MARV-V2-PCB/blob/master/'
MIN_INPUT = 3.8  # AP63203 specified minimum input, V
sys.path.insert(0, str(TOOLS))

esc = html.escape


def natural(text):
    return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', str(text))]


def run(cmd, timeout=180):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, cwd=ROOT)


def badge(kind, text):
    return f'<span class="badge {kind}">{esc(text)}</span>'


def table(head, rows, cls=''):
    th = ''.join(f'<th>{h}</th>' for h in head)
    body = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<div class="scroll"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def could_not_run(err):
    return f'<p class="box err">{badge("err", "COULD NOT RUN")} could not run: {esc(str(err))}</p>'


# --------------------------------------------------------------------------- charts
W, H = 560, 280
ML, MR, MT, MB = 60, 14, 14, 46
PW, PH = W - ML - MR, H - MT - MB
TMAX = 20e-3


def nice_step(span, n=4):
    raw = span / n
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 10 ** (-1 * (len(str(int(1 / raw))) if raw > 0 else 1))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def decimate(ts, ys, buckets=340):
    """Keep first/min/max/last of each horizontal pixel bucket so spikes survive."""
    keep, start = set(), 0
    n = len(ts)
    while start < n:
        b = min(buckets - 1, int(ts[start] / TMAX * buckets))
        end = start
        while end < n and min(buckets - 1, int(ts[end] / TMAX * buckets)) == b:
            end += 1
        seg = range(start, end)
        keep.update((start, end - 1, min(seg, key=ys.__getitem__), max(seg, key=ys.__getitem__)))
        start = end
    return sorted(keep)


def chart(series, ylabel, ymin, ymax, unit, decimals, ref=None, label=''):
    """series: [(name, css class, ts, ys)]. Returns an inline SVG string."""
    def X(t):
        return ML + t / TMAX * PW

    def Y(v):
        return MT + PH * (1 - (v - ymin) / (ymax - ymin))

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">']
    out.append(f'<rect class="plot" x="{ML}" y="{MT}" width="{PW}" height="{PH}"/>')
    out.append(f'<rect class="event" x="{X(8e-3):.1f}" y="{MT}" width="{X(12e-3) - X(8e-3):.1f}" height="{PH}"><title>Measurement window 8 to 12 ms (event)</title></rect>')
    out.append(f'<text class="ax small" x="{X(10e-3):.1f}" y="{MT + 13}" text-anchor="middle">event window</text>')
    step = nice_step(ymax - ymin)
    v = ymin
    while v <= ymax + step * 1e-6:
        out.append(f'<line class="grid" x1="{ML}" x2="{ML + PW}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                   f'<text class="ax" x="{ML - 6}" y="{Y(v) + 5:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    for ms in range(0, 21, 4):
        out.append(f'<line class="grid" x1="{X(ms * 1e-3):.1f}" x2="{X(ms * 1e-3):.1f}" y1="{MT}" y2="{MT + PH}"/>'
                   f'<text class="ax" x="{X(ms * 1e-3):.1f}" y="{MT + PH + 18}" text-anchor="middle">{ms}</text>')
    out.append(f'<text class="ax" x="{ML + PW / 2}" y="{H - 6}" text-anchor="middle">time (ms)</text>')
    out.append(f'<text class="ax" transform="translate(14 {MT + PH / 2}) rotate(-90)" text-anchor="middle">{esc(ylabel)}</text>')
    if ref:
        rv, rname = ref
        out.append(f'<line class="refline" x1="{ML}" x2="{ML + PW}" y1="{Y(rv):.1f}" y2="{Y(rv):.1f}"><title>{esc(rname)}</title></line>'
                   f'<text class="refl small" x="{ML + PW - 4}" y="{Y(rv) + 15:.1f}" text-anchor="end">{esc(rname)}</text>')
    for name, cls, ts, ys in series:
        pts, last = [], None
        for i in decimate(ts, ys):
            p = f'{X(ts[i]):.1f},{Y(min(max(ys[i], ymin), ymax)):.1f}'
            if p != last:
                pts.append(p)
                last = p
        out.append(f'<polyline class="line {cls}" points="{" ".join(pts)}"><title>{esc(name)}</title></polyline>')
    for name, cls, ts, ys in series:
        for k in range(0, 41):
            t = TMAX * k / 40
            j = min(bisect.bisect_left(ts, t), len(ts) - 1)
            out.append(f'<circle class="hit" cx="{X(ts[j]):.1f}" cy="{Y(min(max(ys[j], ymin), ymax)):.1f}" r="6">'
                       f'<title>{esc(name)}&#10;t = {ts[j] * 1e3:.2f} ms&#10;{ys[j]:.{decimals}f} {unit}</title></circle>')
    out.append('</svg>')
    return ''.join(out)


def legend(items):
    lis = ''.join(f'<li><span class="sw {cls}"></span>{esc(text)}</li>' for cls, text in items)
    return f'<ul class="legend">{lis}</ul>'


# --------------------------------------------------------------------------- data
def export_netlist(work):
    netlist = work / 'netlist.xml'
    r = run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', netlist, SCH])
    if r.returncode or not netlist.exists():
        raise RuntimeError(f'kicad-cli netlist export failed: {(r.stderr or r.stdout).strip()[-300:]}')
    return netlist


def read_waveform(path):
    lines = path.read_text().splitlines()
    cols = list(zip(*[[float(x) for x in ln.split()] for ln in lines[1:] if ln.strip()]))
    return {k: list(c) for k, c in zip(('t', 'v5sys', 'n5vin', 'usbvbus', 'extdraw', 'usbdraw'), cols)}


CASE_TEXT = {
    'external_only': 'Only the external 5 V supply is connected. The load starts at 2 ms.',
    'usb_only': 'Only USB is connected. The load starts at 2 ms.',
    'both': 'External 5 V and USB are both connected from the start.',
    'usb_insert': 'External 5 V is present; USB is plugged in at 8 ms.',
    'usb_remove': 'Both connected; USB is unplugged at 8 ms and the external supply stays.',
    'external_remove': 'Both connected; the external supply is unplugged at 8 ms and USB stays.',
    'load_step': 'External 5 V only; the demand steps from 0.1 A to the chosen load at 8 ms.',
}


def section_sim():
    import simulate_power_input as sim
    args = types.SimpleNamespace(load=0.5, external_load=0.0, external_voltage=5.0, usb_voltage=5.0)
    with tempfile.TemporaryDirectory(prefix='marv-site-') as tmp:
        work = Path(tmp)
        sim.check_wiring(work)
        results = []
        for case in sim.CASES:
            name, label, m = sim.run_case(work, case, args, keep_waveforms=True)
            results.append((name, label, m, read_waveform(work / f'{name}.dat')))
    worst = min(m['event_min'] for _, _, m, _ in results)
    ok = worst >= MIN_INPUT
    head = (f'<p class="verdict">{badge("pass" if ok else "fail", "PASS" if ok else "FAIL")} '
            f'Lowest V5_SYS in any event window: <b>{worst:.3f} V</b>, against the AP63203 specified '
            f'minimum input of <b>{MIN_INPUT} V</b> (margin <b>{worst - MIN_INPUT:.3f} V</b>). '
            f'This is a <i>comparison</i> of input availability, not a pass/fail of the whole board '
            f'and not a check of the 3.3 V outputs.</p>')
    assume = (
        '<h3>Assumptions</h3><ul>'
        '<li><b>Boundary:</b> external regulated 5 V and USB, through Q1/D1, to V5_SYS. The external source '
        'stands for either the 2S&ndash;6S buck or the 1S boost <i>at its 5 V output</i>; both live off-board and are not simulated. '
        'Raw battery voltage and charging are not in the model.</li>'
        '<li><b>Load:</b> one explicit demand of <b>0.5 A at V5_SYS</b> (an assumption, not a measured budget); '
        'extra external 5 V demand 0 A. No regulator or LDO control loops are modelled.</li>'
        '<li><b>Sources:</b> external 5 V through an assumed <b>0.05 &Omega;</b>; USB 5 V through an assumed <b>0.35 &Omega;</b>. '
        'No source current limit.</li>'
        '<li><b>Timing:</b> loads start at 2 ms; source events at 8 ms; event window 8&ndash;12 ms; &ldquo;final&rdquo; is the 19&ndash;20 ms average.</li>'
        '<li><b>Models:</b> vendor AOS model for Q1, hand-fitted forward curve for D1 (temperature-dependent leakage not bounded), '
        'approximate white LED, nominal capacitors.</li>'
        '<li><b>Out of scope:</b> source current limiting, charging, cell cutoff, USB negotiation, regulator outputs, noise, '
        'layout parasitics and thermal behaviour. This simulation cannot decide whether the sensor supplies need an LDO.</li>'
        '</ul>')
    rows1, rows2 = [], []
    for name, label, m, _ in results:
        good = m['event_min'] >= MIN_INPUT
        rows1.append([f'<a href="#case-{name}">{esc(label)}</a>', f"{m['before']:.3f}", f"{m['event_min']:.3f}&ndash;{m['event_max']:.3f}",
                      f"{m['final']:.3f}", f"{m['ext_final']:.3f} / {m['usb_final']:.3f}",
                      f"{m['event_min'] - MIN_INPUT:+.3f}", badge('pass' if good else 'fail', 'PASS' if good else 'FAIL')])
        rows2.append([esc(label), f"{m['external_min']:.3f} / {m['external_final']:.3f}", f"{1000 * m['usb_reverse']:.4f}",
                      f"{1000 * m['ext_reverse']:.4f}", f"{m['q1_w']:.4f} / {m['d1_w']:.4f}"])
    t1 = table(['Case', 'Before (V)', 'Event min&ndash;max (V)', 'Final (V)', 'External / USB final (A)',
                f'Margin to {MIN_INPUT} V (V)', f'Min &ge; {MIN_INPUT} V?'], rows1, 'num')
    t2 = table(['Case', 'External 5V_IN min / final (V)', 'Peak reverse into USB node (mA)',
                'Peak reverse toward external input (mA)', 'Q1 / D1 final loss (W)'], rows2, 'num')
    cards = []
    for name, label, m, w in results:
        good = m['event_min'] >= MIN_INPUT
        vch = chart([('V5_SYS', 's-sys', w['t'], w['v5sys']), ('5V_IN (external input)', 's-ext', w['t'], w['n5vin']),
                     ('USB_VBUS', 's-usb', w['t'], w['usbvbus'])], 'voltage (V)', 0, 6, 'V', 3,
                    ref=(MIN_INPUT, f'{MIN_INPUT} V AP63203 min input'), label=f'{label}: node voltages versus time')
        allc = sorted(w['extdraw'] + w['usbdraw'])
        cmax = max(allc[int(len(allc) * 0.995)], 0.6)  # inrush spikes can be 10x the steady state
        peak = max(allc[-1], 0)
        cstep = nice_step(cmax * 1.1)
        cymax = cstep * (int(cmax * 1.1 / cstep) + 1)
        clipped = peak > cymax
        cch = chart([('External source current', 's-ext', w['t'], w['extdraw']), ('USB source current', 's-usb', w['t'], w['usbdraw'])],
                    'current (A)', 0, cymax, 'A', 4, label=f'{label}: source currents versus time')
        clip_note = (f' The axis is capped at {cymax:g} A; the brief inrush peak of {peak:.1f} A when a source connects '
                     f'to a discharged node is clipped (hover values are exact).') if clipped else ''
        cards.append(
            f'<article class="case" id="case-{name}"><header><h3>{esc(label)}</h3>'
            f'{badge("pass" if good else "fail", "PASS" if good else "FAIL")}</header>'
            f'<p>{esc(CASE_TEXT[name])}</p>'
            f'<p class="verdict">Lowest V5_SYS in the 8&ndash;12 ms event window: <b>{m["event_min"]:.3f} V</b> '
            f'(margin {m["event_min"] - MIN_INPUT:+.3f} V against the {MIN_INPUT} V reference).</p>'
            f'<div class="charts"><figure>{vch}'
            f'{legend([("l-sys", "V5_SYS"), ("l-ext", "5V_IN (external input)"), ("l-usb dot", "USB_VBUS"), ("l-ref dash", f"{MIN_INPUT} V reference")])}'
            f'<figcaption>Node voltages. Shaded band: event window.</figcaption></figure>'
            f'<figure>{cch}'
            f'{legend([("l-ext", "External source current"), ("l-usb", "USB source current")])}'
            f'<figcaption>Current delivered by each source.{clip_note}</figcaption></figure></div></article>')
    note = ('<p class="small muted">Reverse-current peaks include connection transients; they are not USB compliance limits. '
            'Losses are electrical model estimates, not temperatures. With USB present, D1 and Q1&rsquo;s body diode can share the load; '
            'unplugging USB lets the Q1 channel turn on. The numbers are produced by <code>tools/simulate_power_input.py</code> '
            '(same decks and parsing; this page does not rewrite <code>simulations/RESULTS.md</code>).</p>')
    return ok, head + assume + '<h3>Measurements</h3>' + t1 + t2 + note + '<h3>Waveforms</h3>' + ''.join(cards)


def section_netlist(netlist):
    script = TOOLS / 'check_power_netlist.py'
    buf, argv = io.StringIO(), sys.argv
    sys.argv = [str(script), str(netlist)]
    try:
        with contextlib.redirect_stdout(buf):
            g = runpy.run_path(str(script), run_name='check_power_netlist')
    except AssertionError as e:
        fr = traceback.extract_tb(e.__traceback__)[-1]
        return False, (f'<p class="verdict">{badge("fail", "FAIL")} an assertion in <code>check_power_netlist.py</code> failed '
                       f'(line {fr.lineno}: <code>{esc(fr.line or "")}</code>).</p><pre>{esc(repr(e.args))}</pre>')
    finally:
        sys.argv = argv
    expected, pinout, pads = g['expected'], g['PINOUT'], g['PAD_OF_GPIO']
    buses = g['BUS_NODES']
    summary = ' '.join(buf.getvalue().split())
    rows = [[esc(r), esc(p), esc(n)] for (r, p), n in sorted(expected.items(), key=lambda kv: (natural(kv[0][0]), natural(kv[0][1])))]
    gp = [[f'GPIO{n}', esc(pads[n]), esc(pinout[n]) if pinout[n] else '<i>no connect</i>'] for n in sorted(pinout)]
    bus = [[esc(n), esc(', '.join(f'{r}.{p}' for r, p in sorted(v, key=lambda x: (natural(x[0]), natural(x[1])))))] for n, v in buses.items()]
    return True, (
        f'<p class="verdict">{badge("pass", "PASS")} {esc(summary)}</p>'
        f'<p class="small muted">The script asserts each mapping below against the netlist exported from the saved schematic, '
        f'plus the exact node set of each rail and bus net, the absent-parts list and footprint pad coverage.</p>'
        f'<details><summary>{len(expected)} checked pin-to-net mappings</summary>{table(["Ref", "Pin", "Expected net"], rows)}</details>'
        f'<details><summary>48-GPIO pin plan (U20 pad to net)</summary>{table(["GPIO", "U20 pad", "Net"], gp)}</details>'
        f'<details><summary>{len(buses)} bus nets with exact node sets</summary>{table(["Net", "Exact nodes"], bus)}</details>')


ACCEPT_ROWS = [
    ('hole', 'hole_clearance', 18, 'GND vias placed on purpose in the RP2350 (U20) exposed pad.'),
    ('usb', 'clearance (USB)', 3, 'USB pair neck-down at the MCU pins and the connector.'),
    ('court', 'courtyards_overlap', 1, 'SW1 / J10 overlap is courtyard-only.'),
]


def classify(v):
    if v['severity'] != 'error':
        return None
    descs = [i['description'] for i in v['items']]
    if v['type'] == 'hole_clearance' and any('U20' in d for d in descs) and any(d.startswith('Via [GND]') for d in descs):
        return 'hole'
    if v['type'] == 'clearance' and "netclass 'USB'" in v['description']:
        return 'usb'
    if v['type'] == 'courtyards_overlap' and sorted(descs) == ['Footprint J10', 'Footprint SW1']:
        return 'court'
    return None


def where(v):
    it = v['items'][0] if v['items'] else None
    return f"({it['pos']['x']:.2f}, {it['pos']['y']:.2f})" if it else ''


def count_table(violations):
    types_ = sorted({(v['type'], v['severity']) for v in violations})
    rows = [[esc(t), badge('fail' if s == 'error' else 'warn', s.upper()),
             str(sum(1 for v in violations if v['type'] == t and v['severity'] == s))] for t, s in types_]
    return table(['Type', 'Severity', 'Count'], rows, 'num') if rows else '<p>No violations.</p>'


def section_drc(work):
    out = work / 'drc.json'
    r = run(['kicad-cli', 'pcb', 'drc', '--schematic-parity', '--severity-error', '--severity-warning',
             '--format', 'json', '-o', out, PCB])
    if not out.exists():
        raise RuntimeError(f'kicad-cli pcb drc failed: {(r.stderr or r.stdout).strip()[-300:]}')
    d = json.loads(out.read_text())
    vs = d['violations']
    errors = [v for v in vs if v['severity'] == 'error']
    warns = [v for v in vs if v['severity'] == 'warning']
    kinds = [classify(v) for v in errors]
    unaccepted = [v for v, k in zip(errors, kinds) if k is None]
    n_unconn, n_parity = len(d['unconnected_items']), len(d['schematic_parity'])
    clean_conn = n_unconn == 0 and n_parity == 0
    mismatch = [k for k, _, n, _ in ACCEPT_ROWS if kinds.count(k) != n]
    if unaccepted or not clean_conn:
        ok = ('fail', 'FAIL')
    elif mismatch:
        ok = ('warn', 'CHECK')
    else:
        ok = ('accepted', 'ACCEPTED')
    top = badge(*ok)
    head = (f'<p class="verdict">{top} <b>{len(errors)}</b> errors, <b>{len(warns)}</b> warnings; '
            f'<b>{n_unconn}</b> unconnected items; <b>{n_parity}</b> schematic-parity issues. '
            f'KiCad {esc(d["kicad_version"])}, <code>kicad-cli pcb drc --schematic-parity</code>.</p>')
    arows = []
    for k, label, n, why in ACCEPT_ROWS:
        got = kinds.count(k)
        arows.append([esc(label), f'{got}' + ('' if got == n else f' (owner accepted {n})'), esc(why),
                      badge('accepted' if got == n else 'warn', 'ACCEPTED' if got == n else 'COUNT CHANGED')])
    if unaccepted:
        arows.append(['other errors', str(len(unaccepted)), 'Not on the owner&rsquo;s accepted list.', badge('fail', 'NOT ACCEPTED')])
    accepted = '<h3>Accepted errors (owner&rsquo;s reasons)</h3>' + table(['Violation', 'Found', 'Reason', 'Status'], arows)
    lrows = []
    for i, (v, k) in enumerate(zip(errors, kinds), 1):
        lrows.append([str(i), esc(v['type']), badge('accepted', 'ACCEPTED') if k else badge('fail', 'NOT ACCEPTED'),
                      esc(v['description']), where(v), esc(' | '.join(it['description'] for it in v['items']))])
    elist = f'<details><summary>All {len(errors)} errors</summary>{table(["#", "Type", "Status", "Description", "At (mm)", "Items"], lrows)}</details>'
    wgroups = {}
    for v in warns:
        key = v['type']
        if key == 'assertion_failure':
            m = re.search(r"rule '([^']*)'", v['description'])
            key += f" ({m.group(1)})" if m else ''
        wgroups.setdefault(key, []).append(v)
    wdetail = ''.join(
        f'<details><summary>{esc(k)}: {len(g)}</summary>' + table(['Description', 'At (mm)', 'Items'],
        [[esc(v['description']), where(v), esc(' | '.join(it['description'] for it in v['items']))] for v in g]) + '</details>'
        for k, g in sorted(wgroups.items()))
    warn = (f'<h3>Warnings</h3><p class="small muted">{badge("warn", "WARNING")} The owner has not triaged these on this page; '
            f'they do not affect the accepted-error verdict above.</p>' + wdetail)
    return ok, head + '<h3>Counts by type and severity</h3>' + count_table(vs) + accepted + elist + warn


def section_erc(work):
    out = work / 'erc.json'
    r = run(['kicad-cli', 'sch', 'erc', '--severity-all', '--format', 'json', '-o', out, SCH])
    if not out.exists():
        raise RuntimeError(f'kicad-cli sch erc failed: {(r.stderr or r.stdout).strip()[-300:]}')
    d = json.loads(out.read_text())
    vs = [dict(v, sheet=s['path']) for s in d['sheets'] for v in s['violations']]
    errs = [v for v in vs if v['severity'] == 'error']
    warns = [v for v in vs if v['severity'] == 'warning']
    ok = ('fail', 'FAIL') if errs else (('warn', 'WARNING') if warns else ('pass', 'PASS'))
    top = badge(*ok)
    head = (f'<p class="verdict">{top} <b>{len(errs)}</b> errors, <b>{len(warns)}</b> warnings, '
            f'{len(vs) - len(errs) - len(warns)} other. KiCad {esc(d["kicad_version"])}, '
            f'<code>kicad-cli sch erc --severity-all</code>.</p>')
    rows = [[esc(v['type']), badge('fail' if v['severity'] == 'error' else 'warn', v['severity'].upper()), esc(v['description']),
             esc(', '.join(i['description'] for i in v['items'])), esc(v['sheet'])] for v in vs]
    body = count_table(vs) + (table(['Type', 'Severity', 'Description', 'Items', 'Sheet'], rows) if rows else '')
    return ok, head + body


def section_audit(netlist, work):
    out = work / 'audit.json'
    r = run([sys.executable, TOOLS / 'audit_footprints.py', netlist, '--json', out])
    if r.returncode not in (0, 1) or not out.exists():
        raise RuntimeError(f'audit_footprints.py failed (exit {r.returncode}): {(r.stderr or r.stdout).strip()[-300:]}')
    d = json.loads(out.read_text())
    comps, summ = d['components'], d['summary']
    bad = len(comps) - summ['OK']
    ok = bad == 0
    head = (f'<p class="verdict">{badge("pass" if ok else "fail", "PASS" if ok else "FAIL")} '
            f'<b>{summ["OK"]}</b> of <b>{len(comps)}</b> components OK; <b>{bad}</b> need action. '
            f'Each component is checked for an assigned footprint, a resolvable footprint file, a 3D model file '
            f'(pad-only footprints exempt) and pad count versus symbol pins.</p>')
    srows = [[esc(s), str(n)] for s, n in summ.items()]
    crows = [[esc(c['ref']), esc(c['value']), esc(c['footprint']), esc(c['fp_file_cell']), esc(c['model_cell']),
              badge('pass' if c['status'] == 'OK' else 'fail', c['status'])] for c in sorted(comps, key=lambda c: natural(c['ref']))]
    return ok, (head + table(['Status', 'Count'], srows, 'num')
                + f'<details><summary>All {len(comps)} components</summary>'
                + table(['Ref', 'Value', 'Footprint', 'Footprint file', '3D model', 'Status'], crows) + '</details>')


# --------------------------------------------------------------------------- page
CSS = """
:root{color-scheme:light dark;--bg:#f5f6f8;--card:#fff;--fg:#1b2330;--muted:#5b6678;--line:#d9dee7;--grid:#e6e9ef;--plot:#fbfcfd;
--link:#1b5fd0;--pass:#116b36;--passbg:#d9f3e2;--fail:#8f1520;--failbg:#fadadd;--acc:#14508a;--accbg:#d9e9fa;--warn:#7a5200;--warnbg:#fbeccb;
--c-sys:#1f5fd6;--c-ext:#d9660d;--c-usb:#168a5a;--ref:#c0262d;--event:rgba(80,110,160,.10)}
@media (prefers-color-scheme:dark){:root{--bg:#10141b;--card:#181e28;--fg:#e6eaf1;--muted:#9aa5b8;--line:#2b3445;--grid:#262e3c;--plot:#141a23;
--link:#7fb0ff;--pass:#7fe0a5;--passbg:#12361f;--fail:#ff9aa2;--failbg:#431821;--acc:#9cc8ff;--accbg:#172e4a;--warn:#f3cf7a;--warnbg:#3d2f10;
--c-sys:#6ea3ff;--c-ext:#ffa24d;--c-usb:#4fd69b;--ref:#ff7a80;--event:rgba(150,180,230,.10)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;overflow-wrap:break-word}
a{color:var(--link)}code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.88em}
pre{overflow:auto;background:var(--grid);padding:.6em;border-radius:6px}
main,header.top,footer{max-width:1100px;margin:0 auto;padding:0 14px}
header.top{padding-top:22px}h1{margin:0 0 4px;font-size:clamp(1.4rem,5vw,2rem)}h2{margin:0 0 6px;font-size:1.3rem}h3{margin:20px 0 6px;font-size:1.05rem}
.muted{color:var(--muted)}.small{font-size:.86rem}
.meta{display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--muted);font-size:.9rem;margin:6px 0}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:10px 0 4px}
.status{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:8px;margin:12px 0}
.status a{display:flex;justify-content:space-between;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;text-decoration:none;color:var(--fg)}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:16px 0}
.badge{display:inline-block;font-weight:700;font-size:.75rem;letter-spacing:.04em;padding:2px 8px;border-radius:999px;border:1px solid currentColor;white-space:nowrap;vertical-align:middle}
.pass{color:var(--pass);background:var(--passbg)}.fail,.err{color:var(--fail);background:var(--failbg)}
.accepted{color:var(--acc);background:var(--accbg)}.warn{color:var(--warn);background:var(--warnbg)}
.box.err{padding:10px;border-radius:8px;border:1px solid var(--fail)}
.verdict{margin:8px 0}
.scroll{overflow-x:auto;max-width:100%;border:1px solid var(--line);border-radius:8px;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:5px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--grid);position:sticky;top:0;white-space:nowrap}tr:last-child td{border-bottom:0}
table.num td:not(:first-child){font-variant-numeric:tabular-nums}
details{margin:8px 0}summary{cursor:pointer;font-weight:600;padding:4px 0}details .scroll{max-height:420px;overflow:auto}
.case{border:1px solid var(--line);border-radius:10px;padding:12px;margin:14px 0}
.case header{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}.case h3{margin:0}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:14px}
figure{margin:0;min-width:0}figcaption{font-size:.8rem;color:var(--muted)}
svg{display:block;width:100%;height:auto}
svg .plot{fill:var(--plot);stroke:var(--line)}svg .event{fill:var(--event)}svg .grid{stroke:var(--grid);stroke-width:1}
svg .ax{fill:var(--muted);font-size:13px}svg .small{font-size:12px}svg .refl{fill:var(--ref)}
svg .line{fill:none;stroke-width:2;stroke-linejoin:round}svg .refline{stroke:var(--ref);stroke-width:1.6;stroke-dasharray:6 4}
svg .s-sys{stroke:var(--c-sys);stroke-width:2.8}svg .s-ext{stroke:var(--c-ext)}svg .s-usb{stroke:var(--c-usb);stroke-dasharray:2 3;stroke-width:2.4}
@media (max-width:600px){svg .ax{font-size:20px}svg .small{font-size:17px}}
svg .hit{fill:transparent;stroke:none}svg .hit:hover{fill:var(--fg);fill-opacity:.35}
.legend{list-style:none;margin:6px 0 2px;padding:0;display:flex;flex-wrap:wrap;gap:2px 14px;font-size:.82rem}
.sw{display:inline-block;width:24px;border-top:3px solid var(--c);margin-right:6px;vertical-align:middle}
.l-sys{--c:var(--c-sys);border-top-width:4px}.l-ext{--c:var(--c-ext)}.l-usb{--c:var(--c-usb)}.l-ref{--c:var(--ref)}
.dot{border-top-style:dotted}.dash{border-top-style:dashed}
.renders{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}
.renders img{width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:#fff}
ul{padding-left:1.2em}footer{padding-bottom:30px;color:var(--muted);font-size:.85rem}
"""


def tool_versions():
    out = []
    try:
        out.append('kicad-cli ' + run(['kicad-cli', 'version']).stdout.strip())
    except Exception:
        pass
    try:
        m = re.search(r'ngspice-\d+(\.\d+)?', run(['ngspice', '-v']).stdout)
        if m:
            out.append(m.group(0))
    except Exception:
        pass
    return ', '.join(out)


def main():
    t0 = time.time()
    SITE.mkdir(exist_ok=True)
    results = []  # (anchor, title, status kind, status text, html)

    def guard(anchor, title, fn, *a):
        try:
            res = fn(*a)
            ok, body = res[0], res[1]
            kind, text = ok if isinstance(ok, tuple) else (('pass', 'PASS') if ok else ('fail', 'FAIL'))
            results.append((anchor, title, kind, text, body))
        except Exception as e:  # a check that cannot run must not stop the page
            results.append((anchor, title, 'err', 'COULD NOT RUN', could_not_run(f'{type(e).__name__}: {e}')))

    with tempfile.TemporaryDirectory(prefix='marv-site-') as tmp:
        work = Path(tmp)
        try:
            netlist = export_netlist(work)
            net_err = None
        except Exception as e:
            netlist, net_err = None, e
        guard('sim', 'Power input simulation (ngspice)', section_sim)
        if net_err:
            for anchor, title in (('netlist', 'Power netlist check'), ('audit', 'Footprint audit')):
                results.append((anchor, title, 'err', 'COULD NOT RUN', could_not_run(net_err)))
        else:
            guard('netlist', 'Power netlist check', section_netlist, netlist)
        guard('drc', 'DRC (PCB, with schematic parity)', section_drc, work)
        guard('erc', 'ERC (schematic)', section_erc, work)
        if not net_err:
            guard('audit', 'Footprint audit', section_audit, netlist, work)

    order = ['sim', 'netlist', 'drc', 'erc', 'audit']
    results.sort(key=lambda r: order.index(r[0]))
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    for name in ('front', 'back'):
        shutil.copyfile(ROOT / 'images' / 'pcb' / f'marv-v2-{name}.png', SITE / f'marv-v2-{name}.png')

    status = ''.join(f'<a href="#{a}"><span>{esc(t)}</span>{badge(k, s)}</a>' for a, t, k, s, _ in results)
    secs = ''.join(f'<section id="{a}"><h2>{esc(t)}</h2>{body}</section>' for a, t, _, _, body in results)
    docs = ' &middot; '.join(f'<a href="{GITHUB}{f}">{f}</a>' for f in ('README.md', 'DESIGN_SPEC.md', 'PINOUT.md'))
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MARV V2 design checks</title><style>{CSS}</style></head><body>
<header class="top"><h1>MARV V2 design checks</h1>
<p class="muted" style="margin:0">Results of the project checks on the saved schematic and PCB. Static page: nothing to install or run.</p>
<div class="meta"><span>Board revision 1</span>
<span>Generated {now}</span><span>{esc(tool_versions())}</span></div>
<div class="meta"><span>Docs on GitHub: {docs}</span></div>
<div class="status">{status}</div>
<nav><a href="#renders">Board renders</a>{''.join(f'<a href="#{a}">{esc(t)}</a>' for a, t, _, _, _ in results)}</nav></header>
<main>
<section id="renders"><h2>Board renders</h2>
<div class="renders"><figure><a href="marv-v2-front.png"><img src="marv-v2-front.png" alt="MARV V2 PCB, front" loading="lazy"></a><figcaption>Front</figcaption></figure>
<figure><a href="marv-v2-back.png"><img src="marv-v2-back.png" alt="MARV V2 PCB, back" loading="lazy"></a><figcaption>Back</figcaption></figure></div>
<p class="small muted">Renders of the saved PCB with its 3D models.</p></section>
{secs}
</main>
<footer>Generated by <code>python3 tools/build_site.py</code> in {time.time() - t0:.1f} s. Maintainers refresh the page by running that command and committing <code>site/</code>.</footer>
</body></html>
"""
    (SITE / 'index.html').write_text(page, encoding='utf-8')
    for a, t, k, s, _ in results:
        print(f'{t}: {s}')
    print(f'Wrote {SITE / "index.html"} ({len(page) // 1024} KiB) in {time.time() - t0:.1f} s')


if __name__ == '__main__':
    main()
