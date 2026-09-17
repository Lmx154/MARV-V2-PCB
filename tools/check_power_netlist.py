#!/usr/bin/env python3
"""Check critical power connections and footprint pad coverage in a KiCad XML export."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from build_power import parse, children, unquote

root=ET.parse(sys.argv[1]).getroot()
nets={n.get('name'):{(p.get('ref'),p.get('pin')) for p in n.findall('node')} for n in root.find('nets')}
pin_net={pin:name for name,ps in nets.items() for pin in ps}

def netof(pin):
    """The net a pin is really on, or None if it is unconnected.  KiCad names
    the single-node net of a pin carrying a no-connect flag
    'unconnected-(U20-GPIO1-Pad78)'; that is not a net, it is the absence of
    one, and the six unexposed spare GPIOs are checked against None."""
    n = pin_net.get(pin)
    return None if n is None or n.startswith('unconnected-') else n

# PINOUT dictionary mapping GPIO number to expected net name. Extracted from MCU_GPIO tuples in build_power.py;
# those tuples are authoritative and mirror the actual generator assignments.
# None = the pin carries a KiCad no-connect flag and must reach no net at all
# (the seven unexposed spares: the IO block is 14 rows and the ports above them
# use the rest; GPIO37 joined them when the TPS2121 mux -- whose status pin it
# read -- was removed).
PINOUT={
 0:'FLASH_CS1', 1:'HG_ACC_INT', 2:'IMU_INT2', 3:'LED_DATA', 4:'HG_ACC_CS', 5:'PWM8',
 6:'IMU_INT1', 7:'IMU_CS', 8:'SENS_MISO', 9:None, 10:'SENS_SCK', 11:'SENS_MOSI',
 12:None, 13:'BARO_INT', 14:'BARO_CS', 15:'PWM7', 16:'ELRS_RX', 17:'ELRS_TX',
 18:None, 19:'PWM6', 20:'PWM5', 21:None, 22:'MAG_SDA', 23:'MAG_SCL',
 24:'GPS_RX', 25:'GPS_TX', 26:None, 27:None, 28:'SD_D0', 29:'SD_D1',
 30:'SD_D2', 31:'SD_D3', 32:'ESC_TELEM_RX', 33:'SD_CLK', 34:'SD_CMD', 35:'SD_DET',
 36:'PWM4', 37:None, 38:'PWM3', 39:'PWM2', 40:'VBUS_SENSE', 41:'VBAT_SENSE',
 42:'CURR_SENSE', 43:'PWM1', 44:'IO_GPIO44', 45:'IO_GPIO45', 46:'IO_GPIO46', 47:'IO_GPIO47',
}

# PAD_OF_GPIO mapping GPIO number to U20 pad number. Extracted from MCU_GPIO tuples in build_power.py.
PAD_OF_GPIO={
 0:'77', 1:'78', 2:'79', 3:'80', 4:'1', 5:'2', 6:'3', 7:'4', 8:'6', 9:'7', 10:'8', 11:'9',
 12:'11', 13:'12', 14:'13', 15:'14', 16:'16', 17:'17', 18:'18', 19:'19', 20:'20', 21:'21',
 22:'22', 23:'23', 24:'25', 25:'26', 26:'27', 27:'28', 28:'36', 29:'37', 30:'38', 31:'39',
 32:'40', 33:'42', 34:'43', 35:'44', 36:'45', 37:'46', 38:'47', 39:'48', 40:'49', 41:'52',
 42:'53', 43:'54', 44:'55', 45:'56', 46:'57', 47:'58',
}
expected={
 # U7 AP63203WU-7, FIXED 3.3 V / 2 A synchronous buck, TSOT26 (Diodes DS41326 Rev. 3-2 Pin
 # Descriptions): 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 BST.  FB is a SENSE input on the fixed-output
 # parts (Sec 9 "Setting the Output Voltage"), so ('U7','1') must be V3V3_SYS itself and NOT a
 # divider node - there is no divider on this board any more.
 ('U7','1'):'V3V3_SYS',('U7','2'):'U7_EN',('U7','3'):'V5_SYS',('U7','4'):'GND',
 ('U7','5'):'U7_SW',('U7','6'):'U7_BST',
 ('L2','1'):'U7_SW',('L2','2'):'V3V3_SYS',
 ('C13','1'):'U7_BST',('C13','2'):'U7_SW',                        # bootstrap cap, BST to SW
 ('C8','1'):'V5_SYS',('C8','2'):'GND',('C9','1'):'V5_SYS',('C9','2'):'GND',
 ('C10','1'):'V3V3_SYS',('C10','2'):'GND',('C11','1'):'V3V3_SYS',('C11','2'):'GND',
 ('R52','1'):'V5_SYS',('R52','2'):'U7_EN',
 # U12 TPS7A20 LDO: EN (pin 3) is tied to V3V3_SYS itself.  The AP63203 has no power-good output,
 # so the rail does the buck-before-LDO sequencing instead of a status pin.
 ('U12','1'):'V5_SYS',('U12','2'):'GND',('U12','3'):'V3V3_SYS',('U12','5'):'V3V3_ANA',
 ('J4','A5'):'USB_CC1',('J4','B5'):'USB_CC2',('J4','SH'):'GND',
 # J3 is the MicoAir AM32 4-in-1 ESC pad row, NINE pads. Pads 1-6 are the ESC silkscreen read left
 # to right: CURR, TX, M4, M3, M2, M1 -- so pin 3 is PWM4 and pin 6 is PWM1, NOT the other way round.
 # Pads 7-9 are this board's power entry: 7 is the external BEC's regulated 5 V, 8 is GND and 9 is
 # the raw-pack SENSE wire. This assertion is the one that catches a reversed motor row or a 5 V pad
 # swapped with the VBAT sense pad, which is why every pin is listed.
 ('J3','1'):'CURR_SENSE_RAW',('J3','2'):'ESC_TELEM',('J3','3'):'PWM4',('J3','4'):'PWM3',
 ('J3','5'):'PWM2',('J3','6'):'PWM1',('J3','7'):'5V_IN',('J3','8'):'GND',('J3','9'):'VBAT',
 # The 5 V OR: Q1 AO3401A (SOT-23, 1 G / 2 S / 3 D) and D1 1N5819WS (SOD-323, 1 K / 2 A).
 # Drain on 5V_IN, source on V5_SYS, gate on USB_VBUS with R7 100k to GND; the diode's ANODE is on
 # USB_VBUS and its CATHODE on V5_SYS. A reversed diode or a drain/source swap would put the body
 # diode the wrong way round and let USB back-feed the BEC, so all six pins are asserted.
 ('Q1','1'):'USB_VBUS',('Q1','2'):'V5_SYS',('Q1','3'):'5V_IN',
 ('D1','1'):'V5_SYS',('D1','2'):'USB_VBUS',
 ('R7','1'):'USB_VBUS',('R7','2'):'GND',
 ('C19','1'):'5V_IN',('C19','2'):'GND',
 # RUN: R10 100k pull-up to V3V3_SYS and SW1 to GND. It used to hang on the TPS62913's open-drain
 # PWR_GOOD output; that net no longer exists.
 ('R10','1'):'V3V3_SYS',('R10','2'):'MCU_RUN',('SW1','1'):'MCU_RUN',('SW1','2'):'GND',
 # ESC analog current sense and one-wire KISS telemetry, both conditioned by a 1k series resistor
 ('R53','1'):'CURR_SENSE_RAW',('R53','2'):'CURR_SENSE',('C78','1'):'CURR_SENSE',('C78','2'):'GND',
 ('U20','53'):'CURR_SENSE',                                       # GPIO42 = ADC2
 ('R54','1'):'ESC_TELEM',('R54','2'):'ESC_TELEM_RX',('U20','40'):'ESC_TELEM_RX',   # GPIO32, PIO UART RX
 # WS2812C-2020 (LED:WS2812B-2020 symbol): 1 DOUT (no connect), 2 VSS, 3 DIN, 4 VDD
 ('R55','1'):'LED_DATA',('R55','2'):'LED_DIN',('U20','80'):'LED_DATA',
 ('D20','2'):'GND',('D20','3'):'LED_DIN',('D20','4'):'V5_SYS',('C79','1'):'V5_SYS',('C79','2'):'GND',
 # SWD solder pads
 ('J10','1'):'SWCLK',('J10','2'):'SWDIO',('J10','3'):'GND',
 # the RP2354B end of the four spare GPIOs that leave on the IO block (rows 11-14)
 ('U20','55'):'IO_GPIO44',('U20','56'):'IO_GPIO45',('U20','57'):'IO_GPIO46',
 ('U20','58'):'IO_GPIO47',
 ('C20','1'):'5V_IN',('C21','1'):'5V_IN',('C22','1'):'V3V3_SYS',
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
 ('C48','1'):'VBAT_SENSE',('U20','52'):'VBAT_SENSE',
 ('R29','1'):'USB_VBUS',('R29','2'):'VBUS_SENSE',('R30','1'):'VBUS_SENSE',('R30','2'):'GND',
 # sensor chip-select pull-ups, biased to the rail the sensor VDDIO pins run from. R49 (the former
 # second IMU chip-select pull-up) is removed: the ICM-45686 (U21) has a single chip select.
 ('R48','1'):'V3V3_ANA',('R48','2'):'IMU_CS',
 ('R50','1'):'V3V3_ANA',('R50','2'):'BARO_CS',('R51','1'):'V3V3_ANA',('R51','2'):'HG_ACC_CS',
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
 ('U20','26'):'GPS_TX',('U20','25'):'GPS_RX',('U20','17'):'ELRS_TX',('U20','16'):'ELRS_RX',
 ('U20','22'):'MAG_SDA',('U20','23'):'MAG_SCL',
}
# THE IO BLOCK, 3 columns x 14 rows, EVERY PIN. Row n is J6 pin n (signal, innermost column),
# J7 pin n (power) and J8 pin n (GND, at the board edge). This is the single connector that carries
# GPS, ELRS, the magnetometer bus, the four servo outputs and the four exposed spares, so it is the
# one table that catches a mis-wired port, a signal on the wrong rail, or a 5 V pin on a 3.3 V row.
IO_ROWS=[('GPS_RX','5V_IN'),('GPS_TX','5V_IN'),('ELRS_RX','5V_IN'),('ELRS_TX','5V_IN'),
         ('MAG_SDA','V3V3_SYS'),('MAG_SCL','V3V3_SYS'),('PWM5','5V_IN'),('PWM6','5V_IN'),
         ('PWM7','5V_IN'),('PWM8','5V_IN'),('IO_GPIO44','V3V3_SYS'),('IO_GPIO45','V3V3_SYS'),
         ('IO_GPIO46','V3V3_SYS'),('IO_GPIO47','V3V3_SYS')]
for _i,(_sig,_pwr) in enumerate(IO_ROWS):
    expected[('J6',str(_i+1))]=_sig
    expected[('J7',str(_i+1))]=_pwr
    expected[('J8',str(_i+1))]='GND'
# TEST POINTS: the whole sensor SPI interface is probeable. TP1-TP3 are the shared bus, TP4-TP6 the
# three chip selects, TP7-TP10 the four interrupts. Each must land on its net and nowhere else.
TESTPOINTS={'TP1':'SENS_SCK','TP2':'SENS_MOSI','TP3':'SENS_MISO','TP4':'IMU_CS','TP5':'BARO_CS',
            'TP6':'HG_ACC_CS','TP7':'IMU_INT1','TP8':'IMU_INT2','TP9':'BARO_INT','TP10':'HG_ACC_INT'}
expected.update({(_r,'1'):_n for _r,_n in TESTPOINTS.items()})
for pin,net in expected.items():
 assert pin_net.get(pin)==net,(pin,net,pin_net.get(pin))
assert {('J4','A4'),('J4','A9'),('J4','B4'),('J4','B9')} <= nets['USB_VBUS']
# parts retired by earlier revisions and by this one must be gone, symbol and all:
# U3/U5 the LM66100 OR-ing pair; J3's XT30 input network D23/C16/C67/C68/C69 (the 5 V input itself is
# gone, J3 is now the ESC pad row); D21/R31/R32 the two discrete status LEDs (one WS2812C now); BZ1 the
# through-hole buzzer, and with it the whole buzzer driver - J15 pads, Q20 gate, D22 flyback, R33/R34
# gate network - deleted in this revision, which is what frees GPIO28 for J16 pin 12.
# The IO-array revision retired J9 (MAG pad row) and J16 (the 2x6 spare-IO block).  THIS revision
# retires the J12/J13/J14 servo block as well: PWM5-8 are rows 7-10 of the IO block now.  J7 and J8
# are LIVE again -- they are the power and GND columns of that block, not the old ELRS pad row and
# the old MCU-interface header.
_retired = {'U3','U5','D23','C16','C67','C68','C69','D21','R31','R32','BZ1',
            'J15','Q20','D22','R33','R34','J9','J16','J12','J13','J14',
            # THE BEC REVISION (DESIGN_SPEC "Decisions", 2026-09-17): the on-board pack buck
            # (U26/L3/C73/C74/C75/C76/C77/C80/R52-as-VBAT-EN), the TPS2121 priority mux
            # (U25/R42-R47/C70/C71/C72), the TPS62913 3.3 V stage's second half (FB1, C12,
            # C17, C23, C24 and the 0.1 % divider R8/R9) and the USB ESD array U8 are all gone.
            # R52, R7 and R10 survive as designators on new jobs and are NOT in this set.
            'U8','U25','U26','L3','FB1','C12','C17','C23','C24','C70','C71','C72',
            'C73','C74','C75','C76','C77','C80','R8','R9','R42','R43','R44','R45','R46','R47'}
_refs = {c.get('ref') for c in root.find('components')}
assert not _retired & _refs, sorted(_retired & _refs)
# and no net of the deleted driver survives either (BUZZ_PWM / BUZZ_G / BUZZ_D / BUZZER*)
assert not [n for n in nets if n.upper().startswith('BUZZ')], sorted(
    n for n in nets if n.upper().startswith('BUZZ'))
assert {'H1','H2','H3','H4'} <= _refs, 'mounting-hole group missing'
# DO NOT POPULATE: the QSPI flash/PSRAM socket is an OPTIONAL back-side expansion, so U24 and its two
# bypass caps carry KiCad's (dnp yes) + (in_bom no) attributes -- which the kicadxml export emits as
# <property name="dnp"/> and <property name="exclude_from_bom"/>.  Their NETS still exist and every
# U24 pin mapping above is still checked: a DNP part owns its land pattern and its nets, it is simply
# not fitted.  R35, the FLASH_CS1 pull-up, is NOT DNP -- GPIO0 must be held deselected whether or not
# the socket is populated -- and nothing else on the board may be DNP either, because tools/setup_pcb.py
# uses exactly this attribute to decide what is allowed on B.Cu (check_back()).
_DNP = {'U24'}
_props = {c.get('ref'): {p.get('name') for p in c.findall('property')}
          for c in root.find('components')}
for _r in sorted(_DNP):
    assert _r in _props, (_r, 'DNP part missing from the netlist')
    assert 'dnp' in _props[_r], (_r, 'must carry (dnp yes)')
    assert 'exclude_from_bom' in _props[_r], (_r, 'must carry (in_bom no)')
_unexpected = sorted(r for r, p in _props.items() if 'dnp' in p)
assert _unexpected == sorted(_DNP), ('unexpected DNP parts', _unexpected)
assert 'dnp' not in _props.get('R35', set()), 'R35 (FLASH_CS1 pull-up) must stay populated'
# POWER CHAIN BOUNDARY (DESIGN_SPEC "Decisions", 2026-09-17):
#     external BEC -> J3 pin 7 -> 5V_IN -> (Q1 P-FET) -> V5_SYS -> U7 -> V3V3_SYS -> U12 -> V3V3_ANA
#                     USB_VBUS -> (D1 Schottky) ----^
# and, separately, raw pack -> J3 pin 9 -> VBAT -> R27, a SENSE wire that carries no load.
# 1. VBAT reaches exactly one connector (J3, the ESC row), NO IC pin at all, and nothing but the top
#    leg of the sense divider. Two nodes is the whole net: any third node means pack voltage has
#    found a load, which is the failure this assertion exists to catch.
assert {ref for ref,pin in nets['VBAT'] if ref.startswith('J')}=={'J3'},nets['VBAT']
assert not {(ref,pin) for ref,pin in nets['VBAT'] if ref.startswith('U')},nets['VBAT']
assert nets['VBAT']=={('J3','9'),('R27','1')},nets['VBAT']
# 2. 5V_IN is an INPUT now, not a buck output: it arrives on J3 pin 7 from an off-board BEC, feeds the
#    eight 5 V rows of the IO block power column (rows 1-4 GPS/ELRS and 7-10 servo S5-S8), carries the
#    C19 hold-up and the C20/C21 array bulk, and reaches exactly one semiconductor - Q1's DRAIN.
assert {(ref,pin) for ref,pin in nets['5V_IN'] if ref.startswith('J')}=={
    ('J3','7'),('J7','1'),('J7','2'),('J7','3'),('J7','4'),
    ('J7','7'),('J7','8'),('J7','9'),('J7','10')},nets['5V_IN']
assert {(ref,pin) for ref,pin in nets['5V_IN'] if ref[0] in 'UQD'}=={('Q1','3')},nets['5V_IN']
assert nets['5V_IN']=={('J3','7'),('Q1','3'),('C19','1'),('C20','1'),('C21','1')} | {
    ('J7',str(p)) for p in (1,2,3,4,7,8,9,10)},nets['5V_IN']
# 3. V5_SYS is the OR output. It reaches NO connector pin at all: the servo/module rows moved ahead of
#    the FET to 5V_IN, so nothing downstream of the OR leaves the board and a USB host can never drive
#    the pad row. Its only loads are the two 3.3 V regulators and the WS2812 status LED (D20/C79,
#    <=60 mA, kept here deliberately so the LED works on USB-only bench power).
assert not {(ref,pin) for ref,pin in nets['V5_SYS'] if ref.startswith('J')},nets['V5_SYS']
assert nets['V5_SYS']=={('Q1','2'),('D1','1'),('U7','3'),('U12','1'),('R52','1'),
                        ('C8','1'),('C9','1'),('C25','1'),('D20','4'),('C79','1')},nets['V5_SYS']
# 3z. The OR itself: the gate is USB_VBUS (so USB turns Q1 OFF), the diode anode is USB_VBUS, and
#     nothing else may sit on the gate node except the pull-down and the VBUS sense divider.
assert {('Q1','1'),('D1','2'),('R7','1'),('R29','1')} <= nets['USB_VBUS'],nets['USB_VBUS']
assert nets['U7_SW']=={('U7','5'),('L2','1'),('C13','2')},nets['U7_SW']
assert nets['U7_BST']=={('U7','6'),('C13','1')},nets['U7_BST']
assert nets['U7_EN']=={('U7','2'),('R52','2')},nets['U7_EN']
assert nets['MCU_RUN']=={('U20','35'),('SW1','1'),('R10','2')},nets['MCU_RUN']
# 3y. Nets the BEC revision deleted must not come back under their old names.
assert not [n for n in nets if n in ('PWR_GOOD','PWR_SRC_ST','U7_VO','U7_FB','U7_SS','U7_SCONF',
                                     'U26_SW','U26_BST','U26_EN','U25_PR1','U25_OV1','U25_ILM',
                                     'U25_SS','USB_DP_MCU','USB_DM_MCU')],sorted(nets)
# 3a. V3V3_SYS leaves the board only on the block's six 3.3 V pins (rows 5-6 and 11-14) and on the
#     microSD socket; no other connector may carry the system rail.
assert {(ref,pin) for ref,pin in nets['V3V3_SYS'] if ref.startswith('J')}=={
    ('J7','5'),('J7','6'),('J7','11'),('J7','12'),('J7','13'),('J7','14'),
    ('J11','4')},nets['V3V3_SYS']
# 3b. The GND column is all ground, every pin of it, so every row has its own return.
assert {(ref,pin) for ref,pin in nets['GND'] if ref=='J8'}=={
    ('J8',str(_p)) for _p in range(1,15)},sorted(p for p in nets['GND'] if p[0]=='J8')
# 4. D+/D- run straight from the receptacle into the 27 R series pair: U8, the USBLC6 ESD array, is
#    gone, so each data net is exactly the four receptacle pins plus one resistor end.
for _d,_r in (('USB_DM','R23'),('USB_DP','R22')):
    assert nets[_d]=={('J4','A%s'%('7' if _d=='USB_DM' else '6')),
                      ('J4','B%s'%('7' if _d=='USB_DM' else '6')),(_r,'1')},nets[_d]
# 5. PWM1-4 leave the board ONLY on the ESC pad row; PWM5-8 leave ONLY on the servo block.
for n in range(1,5):
    assert {ref for ref,pin in nets['PWM%d'%n] if ref.startswith('J')}=={'J3'},nets['PWM%d'%n]
for n in range(5,9):
    assert {ref for ref,pin in nets['PWM%d'%n] if ref.startswith('J')}=={'J6'},nets['PWM%d'%n]
assert not any(ref.startswith('J') for ref,pin in nets['V3V3_ANA'])
# the RP2354B analog rail reaches VREG_AVDD only through the 33 ohm design-guide filter
assert nets['VREG_AVDD']=={('U20','61'),('R20','2'),('C41','1')},nets['VREG_AVDD']
assert ('U20','61') not in nets['V3V3_ANA']
# the log flash shares the dedicated QSPI pads and takes its select from GPIO0/QMI CS1n
for mcu,flash in [('71','6'),('72','5'),('74','2'),('73','3'),('70','7')]:
    assert pin_net[('U20',mcu)]==pin_net[('U24',flash)],(mcu,flash)
assert nets['FLASH_CS1']=={('U20','77'),('U24','1'),('R35','2')},nets['FLASH_CS1']
# microSD 4-bit bus and card detect
for mcu,sd in [('42','5'),('43','3'),('36','7'),('37','8'),('38','1'),('39','2'),('44','9')]:
    assert pin_net[('U20',mcu)]==pin_net[('J11',sd)],(mcu,sd)
# shared sensor SPI: one MISO, one MOSI, one clock, three distinct chip selects (ICM-45686 has a
# single chip select, unlike the two-CS BMI088 it replaced)
assert {('U21','1'),('U22','5'),('U23','12'),('U20','6')} <= nets['SENS_MISO']
assert {('U21','14'),('U22','4'),('U23','13'),('U20','9')} <= nets['SENS_MOSI']
assert {('U21','13'),('U22','2'),('U23','14'),('U20','8')} <= nets['SENS_SCK']
assert len({pin_net[p] for p in [('U21','12'),('U22','6'),('U23','7')]})==3
components={c.get('ref'):c for c in root.find('components')}
# the temporary MCU-interface headers are gone
assert 'J5' not in components,'J5 (temporary MCU-interface header) still present'
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

# Validate the 48-GPIO pin plan: every GPIO must be on the expected net per PINOUT, and a GPIO whose
# plan entry is None must reach NO net at all (it carries a no-connect flag in the generator).
for gpio_num in range(48):
 pad = PAD_OF_GPIO[gpio_num]
 expected_net = PINOUT[gpio_num]
 actual_net = netof(('U20', pad))
 assert actual_net == expected_net, \
  f"PINOUT.md violated: GPIO{gpio_num} (U20 pad {pad}) is on {actual_net}, plan says {expected_net}; update PINOUT.md, build_power.py and this table together"

# Validate the spare GPIO split: FOUR spares are exposed on the IO block signal column (rows 11-14),
# SEVEN are deliberately unexposed and must be unconnected.  Exposing one of them means editing
# PINOUT.md (Rule 5), build_power.py and this table together.
EXPOSED_SPARES = {44, 45, 46, 47}
UNEXPOSED_SPARES = {9, 12, 18, 21, 26, 27, 37}
assert not (EXPOSED_SPARES & UNEXPOSED_SPARES)
spare_nets = {'IO_GPIO44', 'IO_GPIO45', 'IO_GPIO46', 'IO_GPIO47'}
assert {PINOUT[g] for g in EXPOSED_SPARES} == spare_nets, \
 f"Exposed spare nets mismatch: {{PINOUT[g] for g in EXPOSED_SPARES}} vs {spare_nets}"
for gpio_num in sorted(EXPOSED_SPARES):
 net_name = PINOUT[gpio_num]
 j6_nodes = {(ref, pin) for ref, pin in nets[net_name] if ref == 'J6'}
 assert j6_nodes, f"Exposed spare GPIO {gpio_num} ({net_name}) does not appear on J6"
for gpio_num in sorted(UNEXPOSED_SPARES):
 assert PINOUT[gpio_num] is None, f"GPIO{gpio_num} is listed unexposed but PINOUT gives it a net"
 assert netof(('U20', PAD_OF_GPIO[gpio_num])) is None, \
  f"GPIO{gpio_num} (U20 pad {PAD_OF_GPIO[gpio_num]}) is unexposed but reaches {netof(('U20', PAD_OF_GPIO[gpio_num]))}"
# ... and no IO_GPIO net survives for any of them
assert not [n for n in nets if n in ('IO_GPIO9','IO_GPIO12','IO_GPIO18','IO_GPIO21','IO_GPIO26','IO_GPIO27')], \
 sorted(n for n in nets if n.startswith('IO_GPIO'))

print(f'PASS: 48-GPIO pin plan (4 exposed spares, 7 unconnected), {len(expected)} critical pin mappings,\n'
      f'      USB supply pins, the BEC -> 5V_IN -> Q1/D1 -> V5_SYS -> U7 -> V3V3_SYS boundary and the\n'
      f'      VBAT sense-only rule, the ESC pad-row order, the\n'
      f'      J6/J7/J8 IO-block row map, the ten sensor test points, the PWM1-4 / PWM5-8 split, the {len(_DNP)} DNP\n'
      f'      flash-expansion parts (U24/C62/C63, R35 populated) and footprint coverage for {len(components)} components.')
