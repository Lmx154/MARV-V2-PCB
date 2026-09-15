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
 ('U1','2'):'HV_IN',('U1','7'):'HV_BOOT',('U1','8'):'HV_SW',
 ('D1','1'):'HV_IN',('D1','2'):'RAW_FUSED',('D2','1'):'HV_IN',('D2','2'):'GND',
 ('U7','2'):'VSYS',('U7','9'):'V3V3',('U7','8'):'BB_FB',
 ('L2','1'):'BB_L1',('L2','2'):'BB_L2',
 ('U6','1'):'USB_VBUS',('U6','6'):'USB_LIMITED',('U6','5'):'USB_ILIM',
 ('Q1','1'):'USB_HIGH_CURRENT',('Q1','2'):'GND',('Q1','3'):'USB_ILIM_LOW',
 ('J4','A5'):'USB_CC1',('J4','B5'):'USB_CC2',('J4','SH'):'GND',
 ('J6','1'):'V3V3',('J6','2'):'GND',
 ('J7','1'):'V3V3',('J7','2'):'GND',
 ('J9','1'):'V3V3',('J9','2'):'GND',
}
for ref,source in [('U2','CELL_FUSED'),('U3','BEC_FUSED'),('U4','BUCK_5V'),('U5','USB_LIMITED')]:
 expected.update({(ref,'1'):source,(ref,'3'):'VSYS',(ref,'6'):'VSYS'})
for pin,net in expected.items():
 assert pin_net.get(pin)==net,(pin,net,pin_net.get(pin))
assert nets['HV_FB']=={('U1','5'),('R1','2'),('R2','1')}
assert nets['BB_FB']=={('U7','8'),('R7','2'),('R8','1'),('C14','2')}
assert {('J4','A4'),('J4','A9'),('J4','B4'),('J4','B9')} <= nets['USB_VBUS']
assert not any(ref.startswith('J') for ref,pin in nets['VSYS'])

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
print(f'PASS: {len(expected)} critical pin mappings, both feedback dividers, USB supply pins, VSYS boundary and footprint coverage for {len(components)} components.')
