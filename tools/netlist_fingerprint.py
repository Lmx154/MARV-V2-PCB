#!/usr/bin/env python3
"""Connectivity fingerprint of a kicadxml netlist, independent of sheet layout.

Prints one sorted line per (ref, pin, net) and per (ref, value, footprint, LCSC, Fit)
so two netlists can be diffed to prove a schematic re-organisation changed nothing
electrical.  Usage: netlist_fingerprint.py reports/power-netlist.xml > a.txt
"""
import sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
lines = []
for c in root.iter('comp'):
    ref = c.get('ref')
    props = {p.get('name'): p.get('value') for p in c.findall('property')}
    lines.append('COMP %s value=%s fp=%s lcsc=%s fit=%s' % (
        ref, c.findtext('value'), c.findtext('footprint'),
        props.get('LCSC', ''), props.get('Fit', props.get('DNP', ''))))
for n in root.iter('net'):
    name = n.get('name')
    for node in n.findall('node'):
        lines.append('NET %s.%s -> %s' % (node.get('ref'), node.get('pin'), name))
print('\n'.join(sorted(lines)))
