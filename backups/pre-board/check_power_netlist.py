#!/usr/bin/env python3
"""Check critical power connections and footprint pad coverage in a KiCad XML export."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from build_power import parse, children, unquote

root=ET.parse(sys.argv[1]).getroot()
nets={n.get('name'):{(p.get('ref'),p.get('pin')) for p in n.findall('node')} for n in root.find('nets')}
pin_net={pin:name for name,ps in nets.items() for pin in ps}
expected={
 ('U7','1'):'V5_SYS',('U7','2'):'U7_SW',('U7','3'):'U7_VO',('U7','4'):'GND',
 ('U7','5'):'PWR_GOOD',('U7','6'):'V5_SYS',('U7','7'):'GND',('U7','8'):'U7_SS',
 ('U7','9'):'U7_FB',('U7','10'):'U7_SCONF',
 ('L2','1'):'U7_SW',('L2','2'):'U7_VO',
 ('FB1','1'):'U7_VO',('FB1','2'):'V3V3_SYS',
 ('U12','1'):'V5_SYS',('U12','2'):'GND',('U12','3'):'V5_SYS',('U12','5'):'V3V3_ANA',
 ('J4','A5'):'USB_CC1',('J4','B5'):'USB_CC2',('J4','SH'):'GND',
 ('J6','1'):'V3V3_SYS',('J6','2'):'GND',
 ('J7','1'):'V3V3_SYS',('J7','2'):'GND',
 ('J9','1'):'V3V3_SYS',('J9','2'):'GND',
}
for ref,source in [('U3','5V_IN'),('U5','USB_VBUS')]:
 expected.update({(ref,'1'):source,(ref,'3'):'V5_SYS',(ref,'6'):'V5_SYS'})
for pin,net in expected.items():
 assert pin_net.get(pin)==net,(pin,net,pin_net.get(pin))
assert nets['U7_FB']=={('U7','9'),('R7','2'),('R8','1')}
assert {('J4','A4'),('J4','A9'),('J4','B4'),('J4','B9')} <= nets['USB_VBUS']
assert not any(ref.startswith('J') for ref,pin in nets['V5_SYS'])

components={c.get('ref'):c for c in root.find('components')}
for ref,c in components.items():
 fp=c.findtext('footprint')
 assert fp,(ref,'missing footprint')
 lib,name=fp.split(':')
 path=Path('/usr/share/kicad/footprints')/(lib+'.pretty')/(name+'.kicad_mod')
 assert path.exists(),(ref,'missing footprint file',fp)
 pads={unquote(p[1]) for p in children(parse(path.read_text()),'pad') if unquote(p[1])}
 used={pin for rr,pin in pin_net if rr==ref}
 assert used<=pads,(ref,fp,'pins absent in footprint',used-pads)
print(f'PASS: {len(expected)} critical pin mappings, the FB divider, USB supply pins, V5_SYS boundary and footprint coverage for {len(components)} components.')
