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
 # RP2354B rails (MCU sheet)
 ('U20','5'):'V3V3_SYS',('U20','59'):'V3V3_ANA',('U20','61'):'VREG_AVDD',
 ('U20','63'):'VREG_LX',('U20','64'):'V3V3_SYS',('U20','65'):'DVDD',
 ('U20','62'):'GND',('U20','81'):'GND',('U20','68'):'V3V3_SYS',('U20','69'):'V3V3_SYS',
 ('R20','1'):'V3V3_ANA',('R20','2'):'VREG_AVDD',('L20','1'):'VREG_LX',('L20','2'):'DVDD',
 ('U20','10'):'DVDD',('U20','32'):'DVDD',('U20','51'):'DVDD',
 # sensor supplies on the analog rail
 ('U21','3'):'V3V3_ANA',('U21','11'):'V3V3_ANA',('U22','1'):'V3V3_ANA',('U22','10'):'V3V3_ANA',
 ('U23','1'):'V3V3_ANA',('U23','6'):'V3V3_ANA',('U23','3'):'V3V3_ANA',('U23','11'):'GND',
 ('U21','7'):'GND',
 # logging supplies on the system rail
 ('U24','8'):'V3V3_SYS',('U24','4'):'GND',('J11','4'):'V3V3_SYS',('J11','6'):'GND',('J11','SH'):'GND',
 # port naming: the module TX lands on an MCU UART RX pin, the module RX on an MCU TX pin
 ('U20','12'):'GPS_TX',('U20','11'):'GPS_RX',('U20','7'):'ELRS_TX',('U20','6'):'ELRS_RX',
 ('U20','3'):'MAG_SDA',('U20','4'):'MAG_SCL',
}
# J13 is row 2 of the actuator header: the raw J3 input, ahead of the LM66100 OR-ing
expected.update({(f'J13',str(i)):'5V_IN' for i in range(1,9)})
for ref,source in [('U3','5V_IN'),('U5','USB_VBUS')]:
 expected.update({(ref,'1'):source,(ref,'3'):'V5_SYS',(ref,'6'):'V5_SYS'})
for pin,net in expected.items():
 assert pin_net.get(pin)==net,(pin,net,pin_net.get(pin))
assert nets['U7_FB']=={('U7','9'),('R7','2'),('R8','1')}
assert {('J4','A4'),('J4','A9'),('J4','B4'),('J4','B9')} <= nets['USB_VBUS']
assert not any(ref.startswith('J') for ref,pin in nets['V5_SYS'])
# the RP2354B analog rail reaches VREG_AVDD only through the 33 ohm design-guide filter
assert nets['VREG_AVDD']=={('U20','61'),('R20','2'),('C41','1')},nets['VREG_AVDD']
assert ('U20','61') not in nets['V3V3_ANA']
# the log flash shares the dedicated QSPI pads and takes its select from GPIO0/QMI CS1n
for mcu,flash in [('71','6'),('72','5'),('74','2'),('73','3'),('70','7')]:
    assert pin_net[('U20',mcu)]==pin_net[('U24',flash)],(mcu,flash)
assert nets['FLASH_CS1']=={('U20','77'),('U24','1'),('R35','2')},nets['FLASH_CS1']
# microSD 4-bit bus and card detect
for mcu,sd in [('40','5'),('42','3'),('43','7'),('44','8'),('45','1'),('46','2'),('47','9')]:
    assert pin_net[('U20',mcu)]==pin_net[('J11',sd)],(mcu,sd)
# shared sensor SPI: one MISO, one MOSI, one clock, four distinct chip selects
assert {('U21','15'),('U21','10'),('U22','5'),('U23','12'),('U20','16')} <= nets['SENS_MISO']
assert {('U21','9'),('U22','4'),('U23','13'),('U20','19')} <= nets['SENS_MOSI']
assert {('U21','8'),('U22','2'),('U23','14'),('U20','18')} <= nets['SENS_SCK']
assert len({pin_net[p] for p in [('U21','14'),('U21','5'),('U22','6'),('U23','7')]})==4
components={c.get('ref'):c for c in root.find('components')}
# the temporary MCU-interface headers are gone
assert not {'J5','J8'} & set(components),'J5/J8 still present'
FPLIBS=[Path('/usr/share/kicad/footprints'),Path(__file__).resolve().parents[1]]
for ref,c in components.items():
 fp=c.findtext('footprint')
 assert fp,(ref,'missing footprint')
 lib,name=fp.split(':')
 path=next((d/(lib+'.pretty')/(name+'.kicad_mod') for d in FPLIBS if (d/(lib+'.pretty')/(name+'.kicad_mod')).exists()),None)
 assert path,(ref,'missing footprint file',fp)
 pads={unquote(p[1]) for p in children(parse(path.read_text()),'pad') if unquote(p[1])}
 used={pin for rr,pin in pin_net if rr==ref}
 assert used<=pads,(ref,fp,'pins absent in footprint',used-pads)
print(f'PASS: {len(expected)} critical pin mappings, the FB divider, USB supply pins, V5_SYS boundary and footprint coverage for {len(components)} components.')
