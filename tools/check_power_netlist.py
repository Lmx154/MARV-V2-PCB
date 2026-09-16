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
 # J3 is the MicoAir AM32 4-in-1 ESC pad row. The order is the ESC silkscreen read left to right:
 # CURR, TX, M4, M3, M2, M1, VBAT, GND -- so pin 3 is PWM4 and pin 6 is PWM1, NOT the other way round.
 # This assertion is the one that catches a reversed motor row, which is why every pin is listed.
 ('J3','1'):'CURR_SENSE_RAW',('J3','2'):'ESC_TELEM',('J3','3'):'PWM4',('J3','4'):'PWM3',
 ('J3','5'):'PWM2',('J3','6'):'PWM1',('J3','7'):'VBAT',('J3','8'):'GND',
 # U26 AP63205WU-7, fixed 5 V / 2 A buck, TSOT-23-6 (Diodes DS41326 Rev. 2-2 Pin Descriptions):
 # 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 BST. FB is a sense input on the fixed-output parts and goes
 # straight to the output, so ('U26','1') must be 5V_IN and not a divider node.
 ('U26','1'):'5V_IN',('U26','2'):'U26_EN',('U26','3'):'VBAT',('U26','4'):'GND',
 ('U26','5'):'U26_SW',('U26','6'):'U26_BST',
 ('L3','1'):'U26_SW',('L3','2'):'5V_IN',
 ('C75','1'):'U26_BST',('C75','2'):'U26_SW',                      # bootstrap cap, BST to SW
 ('C73','1'):'VBAT',('C73','2'):'GND',('C74','1'):'VBAT',('C74','2'):'GND',
 ('C76','1'):'5V_IN',('C76','2'):'GND',('C77','1'):'5V_IN',('C77','2'):'GND',('C80','1'):'5V_IN',('C80','2'):'GND',
 ('R52','1'):'VBAT',('R52','2'):'U26_EN',
 # ESC analog current sense and one-wire KISS telemetry, both conditioned by a 1k series resistor
 ('R53','1'):'CURR_SENSE_RAW',('R53','2'):'CURR_SENSE',('C78','1'):'CURR_SENSE',('C78','2'):'GND',
 ('U20','53'):'CURR_SENSE',                                       # GPIO42 = ADC2
 ('R54','1'):'ESC_TELEM',('R54','2'):'ESC_TELEM_RX',('U20','38'):'ESC_TELEM_RX',   # GPIO30, PIO UART RX
 # WS2812C-2020 (LED:WS2812B-2020 symbol): 1 DOUT (no connect), 2 VSS, 3 DIN, 4 VDD
 ('R55','1'):'LED_DATA',('R55','2'):'LED_DIN',('U20','27'):'LED_DATA',
 ('D20','2'):'GND',('D20','3'):'LED_DIN',('D20','4'):'V5_SYS',('C79','1'):'V5_SYS',('C79','2'):'GND',
 # buzzer solder pads replace the through-hole buzzer; D22 still clamps across them
 ('J15','1'):'V5_SYS',('J15','2'):'BUZZ_D',('Q20','3'):'BUZZ_D',('D22','1'):'V5_SYS',('D22','2'):'BUZZ_D',
 # SWD solder pads
 ('J10','1'):'SWCLK',('J10','2'):'SWDIO',('J10','3'):'GND',
 # spare-IO block: 3.3 V, two grounds and the nine GPIOs no on-board function claims
 ('J16','1'):'V3V3_SYS',('J16','2'):'GND',('J16','3'):'IO_GPIO1',('J16','4'):'IO_GPIO21',
 ('J16','5'):'IO_GPIO27',('J16','6'):'IO_GPIO31',('J16','7'):'IO_GPIO43',('J16','8'):'IO_GPIO44',
 ('J16','9'):'IO_GPIO45',('J16','10'):'IO_GPIO46',('J16','11'):'IO_GPIO47',('J16','12'):'GND',
 ('U20','78'):'IO_GPIO1',('U20','21'):'IO_GPIO21',('U20','28'):'IO_GPIO27',('U20','39'):'IO_GPIO31',
 ('U20','54'):'IO_GPIO43',('U20','55'):'IO_GPIO44',('U20','56'):'IO_GPIO45',('U20','57'):'IO_GPIO46',
 ('U20','58'):'IO_GPIO47',
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
 # telemetry dividers: VBAT_SENSE 100k/10k (full scale 36.3 V), VBUS_SENSE unchanged at 10k/15k
 ('R27','1'):'VBAT',('R27','2'):'VBAT_SENSE',('R28','1'):'VBAT_SENSE',('R28','2'):'GND',
 ('C48','1'):'VBAT_SENSE',('U20','49'):'VBAT_SENSE',
 ('R29','1'):'USB_VBUS',('R29','2'):'VBUS_SENSE',('R30','1'):'VBUS_SENSE',('R30','2'):'GND',
 # sensor chip-select pull-ups, biased to the rail the sensor VDDIO pins run from. R49 (the former
 # second IMU chip-select pull-up) is removed: the ICM-45686 (U21) has a single chip select.
 ('R48','1'):'V3V3_ANA',('R48','2'):'IMU_CS',
 ('R50','1'):'V3V3_ANA',('R50','2'):'BARO_CS',('R51','1'):'V3V3_ANA',('R51','2'):'HG_ACC_CS',
 ('U20','48'):'PWR_SRC_ST',                                       # GPIO39 reads the mux status pin
 # sensor supplies on the analog rail. U21 is the ICM-45686 (LGA-14): VDDIO=5, VDD=8, GND=6.
 ('U21','5'):'V3V3_ANA',('U21','8'):'V3V3_ANA',('U22','1'):'V3V3_ANA',('U22','10'):'V3V3_ANA',
 ('U23','1'):'V3V3_ANA',('U23','6'):'V3V3_ANA',('U23','3'):'V3V3_ANA',('U23','11'):'GND',
 ('U21','6'):'GND',
 # U21 decoupling caps: C50/C51 on VDD (pin 8), C52/C53 on VDDIO (pin 5)
 ('C50','1'):'V3V3_ANA',('C50','2'):'GND',('C51','1'):'V3V3_ANA',('C51','2'):'GND',
 ('C52','1'):'V3V3_ANA',('C52','2'):'GND',('C53','1'):'V3V3_ANA',('C53','2'):'GND',
 # logging supplies on the system rail
 ('U24','8'):'V3V3_SYS',('U24','4'):'GND',('J11','4'):'V3V3_SYS',('J11','6'):'GND',('J11','SH'):'GND',
 # port naming: the module TX lands on an MCU UART RX pin, the module RX on an MCU TX pin
 ('U20','12'):'GPS_TX',('U20','11'):'GPS_RX',('U20','7'):'ELRS_TX',('U20','6'):'ELRS_RX',
 ('U20','3'):'MAG_SDA',('U20','4'):'MAG_SCL',
}
# J13 is row 2 of the servo block: 5V_IN, the U26 buck output, ahead of the U25 power mux.
# Only four channels now -- PWM1-4 leave on the ESC pad row, so J12/J13/J14 are 1x04 rows.
expected.update({('J13',str(i)):'5V_IN' for i in range(1,5)})
expected.update({('J12',str(i)):'PWM%d'%(i+4) for i in range(1,5)})
expected.update({('J14',str(i)):'GND' for i in range(1,5)})
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
# parts retired by earlier revisions and by this one must be gone, symbol and all:
# U3/U5 the LM66100 OR-ing pair; J3's XT30 input network D23/C16/C67/C68/C69 (the 5 V input itself is
# gone, J3 is now the ESC pad row); D21/R31/R32 the two discrete status LEDs (one WS2812C now); BZ1 the
# through-hole buzzer (J15 solder pads now).
_refs = {c.get('ref') for c in root.find('components')}
assert not {'U3','U5','D23','C16','C67','C68','C69','D21','R31','R32','BZ1'} & _refs, sorted(
    {'U3','U5','D23','C16','C67','C68','C69','D21','R31','R32','BZ1'} & _refs)
assert {'H1','H2','H3','H4'} <= _refs, 'mounting-hole group missing'
# every U25 programming node is exactly the two or three pins it should be, nothing else leaks in
assert nets['U25_PR1']=={('U25','6'),('R42','2'),('R43','1')},nets['U25_PR1']
assert nets['U25_OV1']=={('U25','5'),('R44','2'),('R45','1')},nets['U25_OV1']
assert nets['U25_ILM']=={('U25','10'),('R46','1')},nets['U25_ILM']
assert nets['U25_SS']=={('U25','11'),('C70','1')},nets['U25_SS']
assert nets['PWR_SRC_ST']=={('U25','9'),('R47','2'),('U20','48')},nets['PWR_SRC_ST']
# POWER CHAIN BOUNDARY: VBAT -> U26 -> 5V_IN -> U25 -> V5_SYS, with servo 5 V tapped at 5V_IN.
# 1. VBAT (raw 6-25.2 V pack) reaches exactly one connector (J3, the ESC row) and exactly one IC pin
#    (U26 VIN). Nothing else may see pack voltage -- in particular no U25, U20 or U7 pin, and the only
#    other things on the net are the buck input caps, the EN resistor and the R27 sense divider top.
assert {ref for ref,pin in nets['VBAT'] if ref.startswith('J')}=={'J3'},nets['VBAT']
assert {(ref,pin) for ref,pin in nets['VBAT'] if ref.startswith('U')}=={('U26','3')},nets['VBAT']
assert nets['VBAT']=={('J3','7'),('U26','3'),('C73','1'),('C74','1'),('R52','1'),('R27','1')},nets['VBAT']
# 2. 5V_IN is now a buck OUTPUT, not an input: it is driven by L3/U26 and feeds U25 IN1 (pin 7), the
#    mux PR1/OV1 dividers, the mux IN1 bypass and the servo row J13. No source connector sits on it.
assert {ref for ref,pin in nets['5V_IN'] if ref.startswith('J')}=={'J13'},nets['5V_IN']
assert {('L3','2'),('U26','1'),('U25','7'),('C76','1'),('C77','1'),('C80','1')} <= nets['5V_IN'],nets['5V_IN']
# 3. V5_SYS (mux output) may reach the two avionics UART ports (J6/J7 VCC) and the buzzer pads (J15),
#    and nothing else with a connector reference. The servo row J13, the ESC row J3 and USB J4 must
#    stay off it, so servo/ESC current never crosses the mux and no source connector back-feeds it.
assert {ref for ref,pin in nets['V5_SYS'] if ref.startswith('J')}=={'J6','J7','J15'},nets['V5_SYS']
# 4. The buck's own programming nodes are exactly what they should be, nothing leaks in.
assert nets['U26_SW']=={('U26','5'),('L3','1'),('C75','2')},nets['U26_SW']
assert nets['U26_BST']=={('U26','6'),('C75','1')},nets['U26_BST']
assert nets['U26_EN']=={('U26','2'),('R52','2')},nets['U26_EN']
# 5. PWM1-4 leave the board ONLY on the ESC pad row; PWM5-8 leave ONLY on the servo block.
for n in range(1,5):
    assert {ref for ref,pin in nets['PWM%d'%n] if ref.startswith('J')}=={'J3'},nets['PWM%d'%n]
for n in range(5,9):
    assert {ref for ref,pin in nets['PWM%d'%n] if ref.startswith('J')}=={'J12'},nets['PWM%d'%n]
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
# shared sensor SPI: one MISO, one MOSI, one clock, three distinct chip selects (ICM-45686 has a
# single chip select, unlike the two-CS BMI088 it replaced)
assert {('U21','1'),('U22','5'),('U23','12'),('U20','16')} <= nets['SENS_MISO']
assert {('U21','14'),('U22','4'),('U23','13'),('U20','19')} <= nets['SENS_MOSI']
assert {('U21','13'),('U22','2'),('U23','14'),('U20','18')} <= nets['SENS_SCK']
assert len({pin_net[p] for p in [('U21','12'),('U22','6'),('U23','7')]})==3
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
print(f'PASS: {len(expected)} critical pin mappings, the FB divider, USB supply pins, the VBAT -> U26 -> 5V_IN -> U25 -> V5_SYS\n'
      f'      boundary, the ESC pad-row order, the PWM1-4 / PWM5-8 split and footprint coverage for {len(components)} components.')
