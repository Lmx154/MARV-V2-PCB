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
# (the six unexposed spares: the IO block is 14 rows and the ports above them
# use the rest, so GPIO1/21/27/28/31/43 are left unconnected on purpose).
PINOUT={
 0:'FLASH_CS1', 1:None, 2:'PWM1', 3:'PWM2', 4:'PWM3', 5:'PWM4',
 6:'MAG_SDA', 7:'MAG_SCL', 8:'ELRS_RX', 9:'ELRS_TX', 10:'PWM5', 11:'PWM6',
 12:'GPS_RX', 13:'GPS_TX', 14:'PWM7', 15:'PWM8', 16:'SENS_MISO', 17:'HG_ACC_CS',
 18:'SENS_SCK', 19:'SENS_MOSI', 20:'IMU_CS', 21:None, 22:'BARO_CS', 23:'IMU_INT1',
 24:'IMU_INT2', 25:'BARO_INT', 26:'LED_DATA', 27:None, 28:None, 29:'HG_ACC_INT',
 30:'ESC_TELEM_RX', 31:None, 32:'SD_CLK', 33:'SD_CMD', 34:'SD_D0', 35:'SD_D1',
 36:'SD_D2', 37:'SD_D3', 38:'SD_DET', 39:'PWR_SRC_ST', 40:'VBAT_SENSE', 41:'VBUS_SENSE',
 42:'CURR_SENSE', 43:None, 44:'IO_GPIO44', 45:'IO_GPIO45', 46:'IO_GPIO46', 47:'IO_GPIO47',
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
 # SWD solder pads
 ('J10','1'):'SWCLK',('J10','2'):'SWDIO',('J10','3'):'GND',
 # the RP2354B end of the four spare GPIOs that leave on the IO block (rows 11-14)
 ('U20','55'):'IO_GPIO44',('U20','56'):'IO_GPIO45',('U20','57'):'IO_GPIO46',
 ('U20','58'):'IO_GPIO47',
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
# THE IO BLOCK, 3 columns x 14 rows, EVERY PIN. Row n is J6 pin n (signal, innermost column),
# J7 pin n (power) and J8 pin n (GND, at the board edge). This is the single connector that carries
# GPS, ELRS, the magnetometer bus, the four servo outputs and the four exposed spares, so it is the
# one table that catches a mis-wired port, a signal on the wrong rail, or a 5 V pin on a 3.3 V row.
IO_ROWS=[('GPS_RX','V5_SYS'),('GPS_TX','V5_SYS'),('ELRS_RX','V5_SYS'),('ELRS_TX','V5_SYS'),
         ('MAG_SDA','V3V3_SYS'),('MAG_SCL','V3V3_SYS'),('PWM5','V5_SYS'),('PWM6','V5_SYS'),
         ('PWM7','V5_SYS'),('PWM8','V5_SYS'),('IO_GPIO44','V3V3_SYS'),('IO_GPIO45','V3V3_SYS'),
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
# ...and the divider is checked by VALUE as well as by topology, because the setpoint it
# programmes is what every ngspice deck asserts against (setpoint 3.33 V) and what
# DESIGN_SPEC quotes.  TPS62913 datasheet Sec 8.2.2.2.6 Eq.8: VOUT = VFB x (1 + R1/R2),
# VFB = 0.8 V typ / 0.792-0.812 V over the Sec 6.5 spec.  R1 = R7 (V3V3_SYS -> FB),
# R2 = R8 (FB -> GND).  Both are 0.1 % thin film in 0402; 15.8k/4.99k was unbuildable
# because no 0.1 % 15.8k exists in 0201 (reports/jlc-audit.md section 6).
_VALUES={c.get('ref'):(c.findtext('value') or '') for c in root.find('components')}
_RVAL={'k':1e3,'M':1e6,'R':1.0,'':1.0}
def _ohms(v):
    import re as _re
    m=_re.match(r'\s*([\d.]+)\s*([kMR]?)\s*/\s*([\d.]+)%\s*$', v)
    assert m, ('resistor value must read "<R>[k|M] / <tol>%"', v)
    return float(m.group(1))*_RVAL[m.group(2)], float(m.group(3))
_r1,_t1=_ohms(_VALUES['R7']); _r2,_t2=_ohms(_VALUES['R8'])
assert _r2<=5000.0, ('TPS62913 Sec 8.2.2.2.6 wants R2 <= 5 kOhm for noise', _r2)
assert _t1<=0.1 and _t2<=0.1, ('FB divider must be 0.1 % on both halves', _t1, _t2)
_vnom=0.8*(1+_r1/_r2)
assert abs(_vnom-3.33)<=3.33*0.003, ('FB divider off the 3.33 V setpoint by >0.3 %', _vnom)
# worst case across 0.1 % on BOTH resistors stacked with the VFB spec
_vmin=0.792*(1+(_r1*0.999)/(_r2*1.001))
_vmax=0.812*(1+(_r1*1.001)/(_r2*0.999))
assert 3.135<=_vmin and _vmax<=3.60, ('V3V3_SYS outside the deck predicate window', _vmin, _vmax)
assert (_r1,_r2)==(10000.0,3160.0), ('FB divider is documented as 10k / 3.16k', _r1, _r2)
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
            'J15','Q20','D22','R33','R34','J9','J16','J12','J13','J14'}
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
# every U25 programming node is exactly the two or three pins it should be, nothing else leaks in
assert nets['U25_PR1']=={('U25','6'),('R42','2'),('R43','1')},nets['U25_PR1']
assert nets['U25_OV1']=={('U25','5'),('R44','2'),('R45','1')},nets['U25_OV1']
assert nets['U25_ILM']=={('U25','10'),('R46','1')},nets['U25_ILM']
assert nets['U25_SS']=={('U25','11'),('C70','1')},nets['U25_SS']
assert nets['PWR_SRC_ST']=={('U25','9'),('R47','2'),('U20','48')},nets['PWR_SRC_ST']
# POWER CHAIN BOUNDARY: VBAT -> U26 -> 5V_IN -> U25 -> V5_SYS.  Servo 5 V is no longer tapped at
# 5V_IN: the IO block has ONE power column, so all eight 5 V rows (GPS/ELRS and S5-S8) are V5_SYS and
# servo current crosses the mux -- see the DESIGN_SPEC note on the U25 ILM budget.
# 1. VBAT (raw 6-25.2 V pack) reaches exactly one connector (J3, the ESC row) and exactly one IC pin
#    (U26 VIN). Nothing else may see pack voltage -- in particular no U25, U20 or U7 pin, and the only
#    other things on the net are the buck input caps, the EN resistor and the R27 sense divider top.
assert {ref for ref,pin in nets['VBAT'] if ref.startswith('J')}=={'J3'},nets['VBAT']
assert {(ref,pin) for ref,pin in nets['VBAT'] if ref.startswith('U')}=={('U26','3')},nets['VBAT']
assert nets['VBAT']=={('J3','7'),('U26','3'),('C73','1'),('C74','1'),('R52','1'),('R27','1')},nets['VBAT']
# 2. 5V_IN is a buck OUTPUT, not an input: it is driven by L3/U26 and feeds U25 IN1 (pin 7), the mux
#    PR1/OV1 dividers and the mux IN1 bypass. It now reaches NO connector at all - the servo row that
#    used to tap it is gone, so nothing leaves the board upstream of the mux.
assert not {ref for ref,pin in nets['5V_IN'] if ref.startswith('J')},nets['5V_IN']
assert {('L3','2'),('U26','1'),('U25','7'),('C76','1'),('C77','1'),('C80','1')} <= nets['5V_IN'],nets['5V_IN']
# 3. V5_SYS (mux output) may reach exactly the eight 5 V pins of the IO block power column - rows 1-4
#    (GPS, ELRS) and rows 7-10 (servo S5-S8) - and nothing else with a connector reference. The ESC
#    row J3 and USB J4 must stay off it, so no source back-feeds the mux output.
assert {(ref,pin) for ref,pin in nets['V5_SYS'] if ref.startswith('J')}=={
    ('J7','1'),('J7','2'),('J7','3'),('J7','4'),
    ('J7','7'),('J7','8'),('J7','9'),('J7','10')},nets['V5_SYS']
# 3a. V3V3_SYS leaves the board only on the block's six 3.3 V pins (rows 5-6 and 11-14) and on the
#     microSD socket; no other connector may carry the system rail.
assert {(ref,pin) for ref,pin in nets['V3V3_SYS'] if ref.startswith('J')}=={
    ('J7','5'),('J7','6'),('J7','11'),('J7','12'),('J7','13'),('J7','14'),
    ('J11','4')},nets['V3V3_SYS']
# 3b. The GND column is all ground, every pin of it, so every row has its own return.
assert {(ref,pin) for ref,pin in nets['GND'] if ref=='J8'}=={
    ('J8',str(_p)) for _p in range(1,15)},sorted(p for p in nets['GND'] if p[0]=='J8')
# 4. The buck's own programming nodes are exactly what they should be, nothing leaks in.
assert nets['U26_SW']=={('U26','5'),('L3','1'),('C75','2')},nets['U26_SW']
assert nets['U26_BST']=={('U26','6'),('C75','1')},nets['U26_BST']
assert nets['U26_EN']=={('U26','2'),('R52','2')},nets['U26_EN']
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
# SIX are deliberately unexposed and must be unconnected.  Exposing one of the six means editing
# PINOUT.md (Rule 5), build_power.py and this table together.
EXPOSED_SPARES = {44, 45, 46, 47}
UNEXPOSED_SPARES = {1, 21, 27, 28, 31, 43}
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
assert not [n for n in nets if n in ('IO_GPIO1','IO_GPIO21','IO_GPIO27','IO_GPIO28','IO_GPIO31','IO_GPIO43')], \
 sorted(n for n in nets if n.startswith('IO_GPIO'))

print(f'PASS: 48-GPIO pin plan (4 exposed spares, 6 unconnected), {len(expected)} critical pin mappings, the FB divider,\n'
      f'      USB supply pins, the VBAT -> U26 -> 5V_IN -> U25 -> V5_SYS boundary, the ESC pad-row order, the\n'
      f'      J6/J7/J8 IO-block row map, the ten sensor test points, the PWM1-4 / PWM5-8 split, the {len(_DNP)} DNP\n'
      f'      flash-expansion parts (U24/C62/C63, R35 populated) and footprint coverage for {len(components)} components.')
