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
 # U12 TPS7A20 LDO: EN (pin 3) is sequenced from PWR_GOOD, not from V5_SYS
 ('U12','1'):'V5_SYS',('U12','2'):'GND',('U12','3'):'PWR_GOOD',('U12','5'):'V3V3_ANA',
 ('J4','A5'):'USB_CC1',('J4','B5'):'USB_CC2',('J4','SH'):'GND',
 # J3: XT30PW-M. Pin 1 is the "-" pad and pin 2 the "+" pad in every AMASS footprint KiCad ships,
 # so the polarity assertion here is pin 1 = GND / pin 2 = 5V_IN, NOT "pin 1 is the positive pin".
 ('J3','1'):'GND',('J3','2'):'5V_IN',
 ('D23','1'):'5V_IN',('D23','2'):'GND',                           # SMAJ5.0A, cathode (pin 1) to 5V_IN
 ('C16','1'):'5V_IN',('C67','1'):'5V_IN',('C68','1'):'5V_IN',('C69','1'):'5V_IN',
 ('C16','2'):'GND',('C67','2'):'GND',('C68','2'):'GND',('C69','2'):'GND',
 # Peripheral ports, Pixhawk DS-009 order. UART: 1 VCC, 2 TX (board TX = module RX net), 3 RX, 4 GND.
 ('J6','1'):'V5_SYS',('J6','2'):'GPS_RX',('J6','3'):'GPS_TX',('J6','4'):'GND',
 ('J7','1'):'V5_SYS',('J7','2'):'ELRS_RX',('J7','3'):'ELRS_TX',('J7','4'):'GND',
 ('J9','1'):'V3V3_SYS',('J9','2'):'MAG_SCL',('J9','3'):'MAG_SDA',('J9','4'):'GND',
 ('C20','1'):'V5_SYS',('C21','1'):'V5_SYS',('C22','1'):'V3V3_SYS',
 # RP2354B rails (MCU sheet). ADC_AVDD (59) stays on the LDO rail; the VREG_AVDD RC filter is fed
 # from V3V3_SYS, so R20 pin 1 must be V3V3_SYS and pin 61 must still reach it only through R20.
 ('U20','5'):'V3V3_SYS',('U20','59'):'V3V3_ANA',('U20','61'):'VREG_AVDD',
 ('U20','63'):'VREG_LX',('U20','64'):'V3V3_SYS',('U20','65'):'DVDD',
 ('U20','62'):'GND',('U20','81'):'GND',('U20','68'):'V3V3_SYS',('U20','69'):'V3V3_SYS',
 ('R20','1'):'V3V3_SYS',('R20','2'):'VREG_AVDD',('L20','1'):'VREG_LX',('L20','2'):'DVDD',
 ('C40','1'):'V3V3_ANA',('C41','1'):'VREG_AVDD',
 ('U20','10'):'DVDD',('U20','32'):'DVDD',('U20','51'):'DVDD',
 # telemetry dividers: VIN_SENSE 22k/10k (full scale 10.56 V), VBUS_SENSE unchanged at 10k/15k
 ('R27','1'):'5V_IN',('R27','2'):'VIN_SENSE',('R28','1'):'VIN_SENSE',('R28','2'):'GND',
 ('C48','1'):'VIN_SENSE',
 ('R29','1'):'USB_VBUS',('R29','2'):'VBUS_SENSE',('R30','1'):'VBUS_SENSE',('R30','2'):'GND',
 # sensor chip-select pull-ups, biased to the rail the sensor VDDIO pins run from
 ('R48','1'):'V3V3_ANA',('R48','2'):'IMU_ACC_CS',('R49','1'):'V3V3_ANA',('R49','2'):'IMU_GYR_CS',
 ('R50','1'):'V3V3_ANA',('R50','2'):'BARO_CS',('R51','1'):'V3V3_ANA',('R51','2'):'HG_ACC_CS',
 ('U20','48'):'PWR_SRC_ST',                                       # GPIO39 reads the mux status pin
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
# J13 is row 2 of the actuator header: the raw J3 input, ahead of the U25 power mux
expected.update({(f'J13',str(i)):'5V_IN' for i in range(1,9)})
# U25 TPS2121 priority power mux, every pin. Pin numbers are the RUX0012A VQFN-HR-12 assignment of
# datasheet SLVSEA3F Sec 6 (Figure 6-2 / Pin Functions): 1 OUT, 2 IN2, 3 CP2, 4 OV2, 5 OV1, 6 PR1,
# 7 IN1, 8 OUT, 9 ST, 10 ILM, 11 SS, 12 GND. CP2 and OV2 are grounded ("connect to GND if not
# required"), which selects the internal-VREF priority scheme: IN1 = 5V_IN wins whenever PR1 > VREF.
expected.update({('U25','1'):'V5_SYS',('U25','2'):'USB_VBUS',('U25','3'):'GND',('U25','4'):'GND',
 ('U25','5'):'U25_OV1',('U25','6'):'U25_PR1',('U25','7'):'5V_IN',('U25','8'):'V5_SYS',
 ('U25','9'):'PWR_SRC_ST',('U25','10'):'U25_ILM',('U25','11'):'U25_SS',('U25','12'):'GND',
 ('R42','1'):'5V_IN',('R42','2'):'U25_PR1',('R43','1'):'U25_PR1',('R43','2'):'GND',
 ('R44','1'):'5V_IN',('R44','2'):'U25_OV1',('R45','1'):'U25_OV1',('R45','2'):'GND',
 ('R46','1'):'U25_ILM',('R46','2'):'GND',('R47','1'):'V3V3_SYS',('R47','2'):'PWR_SRC_ST',
 ('C70','1'):'U25_SS',('C70','2'):'GND',('C71','1'):'5V_IN',('C71','2'):'GND',
 ('C72','1'):'USB_VBUS',('C72','2'):'GND'})
for pin,net in expected.items():
 assert pin_net.get(pin)==net,(pin,net,pin_net.get(pin))
assert nets['U7_FB']=={('U7','9'),('R7','2'),('R8','1')}
assert {('J4','A4'),('J4','A9'),('J4','B4'),('J4','B9')} <= nets['USB_VBUS']
# the superseded LM66100 OR-ing pair is gone, symbol and all
assert not {'U3','U5'} & {c.get('ref') for c in ET.parse(sys.argv[1]).getroot().find('components')},'U3/U5 still present'
# every U25 programming node is exactly the two or three pins it should be, nothing else leaks in
assert nets['U25_PR1']=={('U25','6'),('R42','2'),('R43','1')},nets['U25_PR1']
assert nets['U25_OV1']=={('U25','5'),('R44','2'),('R45','1')},nets['U25_OV1']
assert nets['U25_ILM']=={('U25','10'),('R46','1')},nets['U25_ILM']
assert nets['U25_SS']=={('U25','11'),('C70','1')},nets['U25_SS']
assert nets['PWR_SRC_ST']=={('U25','9'),('R47','2'),('U20','48')},nets['PWR_SRC_ST']
# V5_SYS boundary: the mux output rail may reach the two avionics UART ports (J6/J7 VCC) and nothing
# else with a connector reference. In particular the servo row J13, the 5 V input J3 and USB J4 must
# stay off it, so servo/ESC current never crosses the mux and no source connector back-feeds it.
assert {ref for ref,pin in nets['V5_SYS'] if ref.startswith('J')}=={'J6','J7'},nets['V5_SYS']
assert not any(ref.startswith('J') for ref,pin in nets['V3V3_ANA'])
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
