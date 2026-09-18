#!/usr/bin/env python3
"""Simulate only power arrival at the Q1/D1 OR. See simulations/README.md."""
import argparse
import math
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / 'simulations'
ON, OFF = 'DC 1', 'DC 0'
INSERT = 'PWL(0 0 8m 0 8.001m 1 20m 1)'
REMOVE = 'PWL(0 1 8m 1 8.001m 0 20m 0)'
CASES = [
    ('external_only', 'External 5 V only', ON, OFF),
    ('usb_only', 'USB only', OFF, ON),
    ('both', 'Both connected', ON, ON),
    ('usb_insert', 'USB plugged in; external stays', ON, INSERT),
    ('usb_remove', 'USB unplugged; external stays', ON, REMOVE),
    ('external_remove', 'External unplugged; USB stays', REMOVE, ON),
    ('load_step', 'External only; 0.1 A to chosen load', ON, OFF),
]
MEASUREMENTS = ('before event_min event_max final ext_final usb_final '
                'external_min external_final usb_reverse ext_reverse q1_w d1_w').split()


def check_wiring(work):
    """Check the actual saved schematic, not a potentially stale report."""
    netlist = work / 'netlist.xml'
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
                    '-o', str(netlist), str(ROOT / 'MARV-V2.kicad_sch')],
                   check=True, capture_output=True, text=True)
    root = ET.parse(netlist).getroot()
    pins = {(p.get('ref'), p.get('pin')): n.get('name')
            for n in root.find('nets') for p in n.findall('node')}
    expected = {
        ('J3', '7'): '5V_IN', ('Q1', '3'): '5V_IN',
        ('Q1', '1'): 'USB_VBUS', ('Q1', '2'): 'V5_SYS',
        ('D1', '2'): 'USB_VBUS', ('D1', '1'): 'V5_SYS',
        ('C19', '1'): '5V_IN', ('C19', '2'): 'GND',
        ('U7', '3'): 'V5_SYS', ('U12', '1'): 'V5_SYS',
        ('U12', '3'): 'V3V3_SYS',
    }
    for pin, net in expected.items():
        if pins.get(pin) != net:
            raise RuntimeError(f'Schematic changed: {pin} is {pins.get(pin)}, model expects {net}')
    values = {c.get('ref'): c.findtext('value', '') for c in root.find('components')}
    for ref, prefix in {'Q1': 'AO3401A', 'D1': '1N5819WS', 'U7': 'AP63203',
                        'U12': 'TPS7A2033', 'C19': '100u', 'C7': '1u',
                        'C8': '10u', 'C25': '1u', 'C79': '100n'}.items():
        if not values.get(ref, '').startswith(prefix):
            raise RuntimeError(f'{ref} changed; update the input model before running')


def run_case(work, case, args):
    name, label, external, usb = case
    low = 0.1 if name == 'load_step' else args.load
    load = f'PWL(0 0 2m 0 2.1m {low} 8m {low} 8.01m {args.load} 20m {args.load})'
    fields = dict(MODELS=str(SIM / 'models'), VEXT=args.external_voltage,
                  VUSB=args.usb_voltage, REXT=0.05, RUSB=0.35,
                  EXT_CONTROL=external, USB_CONTROL=usb, LOAD=load,
                  EXTERNAL_LOAD=args.external_load, WAVEFORM=str(work / f'{name}.dat'))
    deck = (SIM / 'power_input.cir').read_text()
    for key, value in fields.items():
        deck = deck.replace(f'@{key}@', str(value))
    if re.search(r'@[A-Z_]+@', deck):
        raise RuntimeError('Unfilled deck field')
    path, logpath = work / f'{name}.cir', work / f'{name}.log'
    path.write_text(deck)
    result = subprocess.run(['ngspice', '-b', '-o', str(logpath), str(path)],
                            capture_output=True, text=True, timeout=60)
    log = logpath.read_text()
    if result.returncode or re.search(r'(?im)error:|fatal error|aborted', log):
        raise RuntimeError(f'{name}: ngspice failed; see {logpath}\n{log[-1000:]}')
    m = {k: float(v) for k, v in re.findall(r'^([a-z][a-z0-9_]*)\s*=\s*([-+\d.eE]+)', log, re.M)}
    if any(k not in m or not math.isfinite(m[k]) for k in MEASUREMENTS):
        raise RuntimeError(f'{name}: missing measurements; see {logpath}')
    return name, label, m


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--load', type=float, default=0.5, help='combined V5_SYS input demand in A')
    ap.add_argument('--external-load', type=float, default=0, help='additional external electronics demand on 5V_IN in A')
    ap.add_argument('--external-voltage', type=float, default=5.0)
    ap.add_argument('--usb-voltage', type=float, default=5.0)
    args = ap.parse_args()
    if any(not math.isfinite(v) or v < 0 for v in vars(args).values()):
        ap.error('All values must be finite and nonnegative')
    if min(args.external_voltage, args.usb_voltage) <= 0:
        ap.error('Source voltages must be positive')
    work = Path(tempfile.mkdtemp(prefix='marv-input-power-'))
    check_wiring(work)
    results = [run_case(work, case, args) for case in CASES]
    lines = ['# Input-power simulation results', '',
             'Generated from the saved schematic by `python3 tools/simulate_power_input.py`.', '',
             f'External source {args.external_voltage:g} V / assumed 0.05 ohm; '
             f'USB {args.usb_voltage:g} V / assumed 0.35 ohm. '
             f'Combined V5_SYS load {args.load:g} A; extra external 5 V load {args.external_load:g} A.', '',
             'The external source represents either the 2S–6S buck or the 1S boost **at its 5 V output**. '
             'The source converter itself is not simulated. Loads start at 2 ms; source events at 8 ms.', '',
             '| Case | Before (V) | Event min–max (V) | Final (V) | External / USB final (A) |',
             '| --- | ---: | ---: | ---: | ---: |']
    for _, label, m in results:
        lines.append(f"| {label} | {m['before']:.3f} | {m['event_min']:.3f}–{m['event_max']:.3f} | "
                     f"{m['final']:.3f} | {m['ext_final']:.3f} / {m['usb_final']:.3f} |")
    worst = min(m['event_min'] for _, _, m in results)
    lines += ['', f'Lowest measured voltage in the event windows: **{worst:.3f} V**. '
              f'AP63203 specified input minimum: **3.8 V**; margin **{worst - 3.8:.3f} V**. '
              'This checks input availability, not the actual 3.3 V outputs.', '',
              '| Case | External 5V_IN min / final (V) | Peak reverse into USB node (mA) | Peak reverse toward external input (mA) | Q1 / D1 final loss (W) |',
              '| --- | ---: | ---: | ---: | ---: |']
    for _, label, m in results:
        lines.append(f"| {label} | {m['external_min']:.3f} / {m['external_final']:.3f} | {1000*m['usb_reverse']:.4f} | {1000*m['ext_reverse']:.4f} | "
                     f"{m['q1_w']:.4f} / {m['d1_w']:.4f} |")
    lines += ['', 'Reverse-current peaks include connection transients; they are not USB compliance limits. '
              'Losses are electrical model estimates, not temperatures.', '',
              'USB drives Q1’s gate. With USB present, do not assume the low-resistance BEC path wins: '
              'D1 and Q1’s body diode can share the load. Unplugging USB lets the Q1 channel turn on.', '',
              '**Limits:** vendor Q1 model; fitted D1 forward curve; approximate white LED; nominal capacitors. '
              'No regulator control loops, source current limits, battery chemistry, charging, converter cutoff, '
              'USB negotiation, PCB parasitics, noise or thermal simulation. D1 leakage at temperature is not bounded. '
              'The default 0.5 A is an explicit input-load assumption, not a measured board budget.', '',
              f'Exact decks, waveforms, logs and exported netlist: `{work}`.', '']
    (SIM / 'RESULTS.md').write_text('\n'.join(lines))
    print('\n'.join(lines[:17]))
    print(f'\nWrote simulations/RESULTS.md; raw waveforms and logs: {work}')
    return 1 if worst < 3.8 else 0


if __name__ == '__main__':
    raise SystemExit(main())
