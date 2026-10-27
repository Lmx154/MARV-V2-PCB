#!/usr/bin/env python3
"""Check critical power connections and footprint pad coverage in a KiCad XML export."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from audit_footprints import parse_sexpr, unquote

root=ET.parse(sys.argv[1]).getroot()
nets={n.get('name'):{(p.get('ref'),p.get('pin')) for p in n.findall('node')} for n in root.find('nets')}
pin_net={pin:name for name,ps in nets.items() for pin in ps}

def netof(pin):
    """The net a pin is really on, or None if it is unconnected.  KiCad names
    the single-node net of a pin carrying a no-connect flag
    'unconnected-(U20-GPIO1-Pad78)'; that is not a net, it is the absence of
    one.  Only the four no-connect spare GPIOs have no net."""
    n = pin_net.get(pin)
    return None if n is None or n.startswith('unconnected-') else n

# Expected GPIO connections, maintained alongside the saved schematic and PINOUT.md.
# GPIO0-27 and GPIO35 follow the GPIO tables in PINOUT.md:
# GPIO1/26/27/35 are the four spares; they carry no-connect flags (None below).
PINOUT={
 0:'FLASH_CS1', 1:None, 2:'PWM8', 3:'PWM7', 4:'PWM6', 5:'PWM5',
 6:'IMU2_INT2', 7:'IMU2_INT1', 8:'IMU2_MISO', 9:'IMU2_CS', 10:'IMU2_SCK', 11:'IMU2_MOSI',
 12:'MAG_SDA', 13:'MAG_SCL', 14:'GPS_RX', 15:'ICM_INT1', 16:'ICM_MISO', 17:'GPS_TX',
 18:'ICM_SCK', 19:'ICM_MOSI', 20:'ICM_CS', 21:'BARO_INT', 22:'BARO_SDA', 23:'BARO_SCL',
 24:'ELRS_RX', 25:'ELRS_TX', 26:None, 27:None, 28:'SD_DAT0', 29:'SD_DAT1',
 30:'SD_DAT2', 31:'SD_DAT3', 32:'SD_CLK_MCU', 33:'SD_CMD', 34:'ESC_TELEM_RX', 35:None,
 36:'PWM4', 37:'PWM3', 38:'PWM2', 39:'PWM1', 40:'VBUS_SENSE', 41:'CURR_SENSE',
 42:'VBAT_SENSE', 43:'LED_DATA', 44:'IO_GPIO44', 45:'IO_GPIO45', 46:'IO_GPIO46', 47:'IO_GPIO47',
}

# RP2354B GPIO-to-package-pad mapping.
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
 ('C8','1'):'V5_SYS',('C8','2'):'GND',
 ('C10','1'):'V3V3_SYS',('C10','2'):'GND',('C11','1'):'V3V3_SYS',('C11','2'):'GND',
 ('R52','1'):'V5_SYS',('R52','2'):'U7_EN',
 # U12 TPS7A20 LDO: EN (pin 3) is tied to V3V3_SYS itself.  The AP63203 has no power-good output,
 # so the rail does the buck-before-LDO sequencing instead of a status pin.
 ('U12','1'):'V5_SYS',('U12','2'):'GND',('U12','3'):'V3V3_SYS',('U12','5'):'V3V3_ANA',
 ('J4','A5'):'USB_CC1',('J4','B5'):'USB_CC2',('J4','SH'):'GND',
 # J3 is the FC ESC interface, EIGHT pads. Connect the G55M by signal name, not pad position.
 # FC pins 1-6: CURR, TX, M4, M3, M2, M1; pin 3 is PWM4 and pin 6 is PWM1.
 # Pad 7 is raw battery VIN from ESC V; pad 8 is GND. VIN feeds converter J17.3
 # and the voltage divider. Regulated 5V_IN comes only from converter J17.1.
 ('J3','1'):'CURR_SENSE_RAW',('J3','2'):'ESC_TELEM',('J3','3'):'PWM4',('J3','4'):'PWM3',
 ('J3','5'):'PWM2',('J3','6'):'PWM1',('J3','7'):'VBAT',('J3','8'):'GND',
 # Purchased converter module, 1x03 2.54 mm; no EN contact.
 ('J17','1'):'5V_IN',('J17','2'):'GND',('J17','3'):'VBAT',
 # The 5 V OR: Q1 AO3401A (SOT-23, 1 G / 2 S / 3 D) and D1 1N5819WS (SOD-323, 1 K / 2 A).
 # Drain on 5V_IN, source on V5_SYS, gate on USB_VBUS with R7 100k to GND; the diode's ANODE is on
 # USB_VBUS and its CATHODE on V5_SYS. A reversed diode or a drain/source swap would put the body
 # diode the wrong way round and let USB back-feed the BEC, so all six pins are asserted.
 ('Q1','1'):'USB_VBUS',('Q1','2'):'V5_SYS',('Q1','3'):'5V_IN',
 ('D1','1'):'V5_SYS',('D1','2'):'USB_VBUS',
 ('R7','1'):'USB_VBUS',('R7','2'):'GND',
 ('C19','1'):'5V_IN',('C19','2'):'GND',
 # RUN: R10 100k pull-up to V3V3_SYS and SW1 to GND; nothing else loads it (no PWR_GOOD net).
 ('R10','1'):'V3V3_SYS',('R10','2'):'MCU_RUN',('SW1','1'):'MCU_RUN',('SW1','2'):'GND',
 # ESC analog current sense and one-wire KISS telemetry, both conditioned by a 1k series resistor
 ('R53','1'):'CURR_SENSE_RAW',('R53','2'):'CURR_SENSE',('C78','1'):'CURR_SENSE',('C78','2'):'GND',
 ('U20','52'):'CURR_SENSE',                                       # GPIO41 = ADC1
 ('R54','1'):'ESC_TELEM',('R54','2'):'ESC_TELEM_RX',('U20','43'):'ESC_TELEM_RX',   # GPIO34, PIO UART RX
 # WS2812C-2020 (LED:WS2812B-2020 symbol): 1 DOUT (no connect), 2 VSS, 3 DIN, 4 VDD
 ('R55','1'):'LED_DATA',('R55','2'):'LED_DIN',('U20','54'):'LED_DATA',
 ('D20','2'):'GND',('D20','3'):'LED_DIN',('D20','4'):'V5_SYS',('C79','1'):'V5_SYS',('C79','2'):'GND',
 # SWD header, Raspberry Pi Debug Probe order (SWCLK, GND, SWDIO)
 ('J10','1'):'SWCLK',('J10','2'):'GND',('J10','3'):'SWDIO',
 # the RP2354B end of the four spare GPIOs that leave on the IO block (rows 11-14)
 ('U20','55'):'IO_GPIO44',('U20','56'):'IO_GPIO45',('U20','57'):'IO_GPIO46',
 ('U20','58'):'IO_GPIO47',
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
 ('C48','1'):'VBAT_SENSE',('U20','53'):'VBAT_SENSE',
 ('R29','1'):'USB_VBUS',('R29','2'):'VBUS_SENSE',('R30','1'):'VBUS_SENSE',('R30','2'):'GND',
 # sensor chip-select pull-ups, biased to the rail the sensor VDDIO pins run from. There is no R49
 # (a second IMU chip-select pull-up): the ICM-45686 (U21) has a single chip select.
 ('R48','1'):'V3V3_ANA',('R48','2'):'ICM_CS',
 ('R50','1'):'V3V3_ANA',('R50','2'):'BARO_SCL',('R51','1'):'V3V3_ANA',('R51','2'):'IMU2_CS',
 # sensor supplies on the analog rail. U21 is the ICM-45686 (LGA-14): VDDIO=5, VDD=8, GND=6.
 ('U21','5'):'V3V3_ANA',('U21','8'):'V3V3_ANA',('U22','1'):'V3V3_ANA',('U22','10'):'V3V3_ANA',
 # U23 is the LSM6DSK320X (ST DS15060 Table 2 mode 1): VDDIO=5, VDD=8, GND=6/7,
 # SDx (2) to VDDIO and SCx (3) to GND; OCS_aux (10) and SDO_aux (11) unconnected.
 ('U23','5'):'V3V3_ANA',('U23','8'):'V3V3_ANA',('U23','2'):'V3V3_ANA',('U23','3'):'GND',
 ('U23','6'):'GND',('U23','7'):'GND',
 ('U21','6'):'GND',
 # Sensor decoupling is DATASHEET-ONLY and is ONE CAP PER SUPPLY PIN (DESIGN_SPEC "Design decisions"):
 # U21 C50 on VDD (pin 8) and C52 on VDDIO (pin 5), 100 nF each, exactly its Table 11 BOM;
 # U22 C54 on VDD (pin 10) and C56 on VDDIO (pin 1), 100 nF each (the BMP581 datasheet asks for none);
 # U23 LSM6DSK320X: C59 on VDD (pin 8) and C60 on VDDIO (pin 5), 100 nF each (DS15060 Figure 27).
 # A second cap per pin (C51/C53/C55/C57 and C58/C61) is asserted absent below; a re-added cap would have to come back into this table with a datasheet line.
 ('C50','1'):'V3V3_ANA',('C50','2'):'GND',('C52','1'):'V3V3_ANA',('C52','2'):'GND',
 ('C54','1'):'V3V3_ANA',('C54','2'):'GND',('C56','1'):'V3V3_ANA',('C56','2'):'GND',
 ('C59','1'):'V3V3_ANA',('C59','2'):'GND',('C60','1'):'V3V3_ANA',('C60','2'):'GND',
 # U21 CLKIN oscillator X1 (HCI 1521H-32K000J18DTSL, 32.000 kHz CMOS; 1521H family sheet pad function table):
 # E/D (1, tri-state enable, always enabled) and Vcc (4) both on V3V3_ANA, GND (2), OUT (3) on ICM_CLKIN
 # (BUS_NODES); C1 on Vcc, 100 nF.
 ('X1','1'):'V3V3_ANA',('X1','4'):'V3V3_ANA',('X1','2'):'GND',
 ('C1','1'):'V3V3_ANA',('C1','2'):'GND',
 # THE USB POWER INDICATOR: USB_VBUS -> R56 1k -> USB_LED_A -> D21 anode (Device:LED
 # pin 2), cathode (pin 1) to GND.  Both pins are asserted because a reversed LED is a part that never
 # lights and never fails anything else.
 ('R56','1'):'USB_VBUS',('R56','2'):'USB_LED_A',('D21','2'):'USB_LED_A',('D21','1'):'GND',
 # logging supplies on the system rail
 ('U24','8'):'V3V3_SYS',('U24','4'):'GND',('J11','4'):'V3V3_SYS',('J11','6'):'GND',('J11','SH'):'GND',
 # port naming: the module TX lands on an MCU UART RX pin, the module RX on an MCU TX pin
 # (UART1 on GPIO24/25 carries ELRS; GPS is hardware UART0 on GPIO14 TX / GPIO17 RX)
 ('U20','17'):'GPS_TX',('U20','13'):'GPS_RX',('U20','26'):'ELRS_TX',('U20','25'):'ELRS_RX',
 ('U20','11'):'MAG_SDA',('U20','12'):'MAG_SCL',
}
# THE IO BLOCK, 3 columns x 14 rows, EVERY PIN. Row n is J6 pin n (signal, innermost column),
# J7 pin n (power) and J8 pin n (GND, at the board edge). This is the single connector that carries
# GPS, ELRS, the magnetometer bus, the four servo outputs and the four exposed spares, so it is the
# one table that catches a mis-wired port, a signal on the wrong rail, or a 5 V pin on a 3.3 V row.
IO_ROWS=[('ELRS_RX','V3V3_SYS'),('ELRS_TX','V3V3_SYS'),('GPS_RX','V3V3_SYS'),('GPS_TX','V3V3_SYS'),
         ('MAG_SDA','V3V3_SYS'),('MAG_SCL','V3V3_SYS'),('PWM5','V3V3_SYS'),('PWM6','V3V3_SYS'),
         ('PWM7','V3V3_SYS'),('PWM8','V3V3_SYS'),('IO_GPIO44','V3V3_SYS'),('IO_GPIO45','V3V3_SYS'),
         ('IO_GPIO46','V3V3_SYS'),('IO_GPIO47','V3V3_SYS')]
for _i,(_sig,_pwr) in enumerate(IO_ROWS):
    expected[('J6',str(_i+1))]=_sig
    expected[('J7',str(_i+1))]=_pwr
    expected[('J8',str(_i+1))]='GND'
for pin,net in expected.items():
 assert pin_net.get(pin)==net,(pin,net,pin_net.get(pin))
assert {pin for ref,pin in pin_net if ref == 'J17'} == {'1','2','3'}, 'J17 must have only three connected pins'
assert {pin for ref,pin in pin_net if ref == 'J3'} == set(map(str, range(1,9))), 'J3 must have only eight pins'
assert {('J4','A4'),('J4','A9'),('J4','B4'),('J4','B9')} <= nets['USB_VBUS']
# parts that are not on the board must be absent from the netlist, symbol and all:
# U3/U5 the LM66100 OR-ing pair; an XT30 input network D23/C16/C67/C68/C69 (J3 is the ESC pad row);
# R31/R32, series resistors of discrete status LEDs (the status LED is one WS2812C).  D21 is the USB
# power indicator on the usb_debug sheet (asserted above) and is not in this set.  BZ1 the
# through-hole buzzer, and with it the whole buzzer driver - J15 pads, Q20 gate, D22 flyback, R33/R34
# gate network - must be absent.
# J9 (MAG pad row), J16 (the 2x6 spare-IO block) and the J12/J13/J14 servo block are absent: PWM5-8
# are rows 7-10 of the IO block.  J7 and J8 are the power and GND columns of that block.
_absent = {'U3','U5','D23','C16','C67','C68','C69','R31','R32','BZ1',
            'J15','Q20','D22','R33','R34','J9','J16','J12','J13','J14',
            # Absent by design (DESIGN_SPEC "Design decisions"): the on-board pack buck
            # (U26/L3/C73/C74/C75/C76/C77/C80/R52-as-VBAT-EN), the TPS2121 priority mux
            # (U25/R42-R47/C70/C71/C72), the TPS62913 3.3 V stage's second half (FB1, C12,
            # C17, C23, C24 and the 0.1 % divider R8/R9) and the USB ESD array U8 must all be absent.
            # R52, R7 and R10 are live designators and are NOT in this set.
            'U8','U25','U26','L3','FB1','C12','C17','C23','C24','C70','C71','C72',
            'C73','C74','C75','C76','C77','C80','R8','R9','R42','R43','R44','R45','R46','R47'}
_refs = {c.get('ref') for c in root.find('components')}
assert not _absent & _refs, sorted(_absent & _refs)
assert not {'R59','C82'} & _refs, 'INA226 support parts must be absent'
assert not {'SHUNT_P','SHUNT_N','BAT_INT'} & nets.keys(), 'INA226 nets must be absent'
# and no net of the buzzer driver may exist either (BUZZ_PWM / BUZZ_G / BUZZ_D / BUZZER*)
assert not [n for n in nets if n.upper().startswith('BUZZ')], sorted(
    n for n in nets if n.upper().startswith('BUZZ'))
assert {'H1','H2','H3','H4'} <= _refs, 'mounting-hole group missing'
# DO NOT POPULATE: the QSPI flash/PSRAM socket is an OPTIONAL back-side expansion, so U24 -- and U24
# alone -- carries KiCad's (dnp yes) + (in_bom no) attributes -- which the kicadxml export emits as
# <property name="dnp"/> and <property name="exclude_from_bom"/>.  Their NETS still exist and every
# U24 pin mapping above is still checked: a DNP part owns its land pattern and its nets, it is simply
# not fitted.  C62, its bypass, IS fitted, is the whole bypass, and is a 1 uF: the LAND IS BUILT
# PSRAM-READY.  The APS6404L PSRAM option REQUIRES a low-ESR 1 uF on VDD (its datasheet Sec 16.4) and
# the W25Q32JV flash names no supply capacitor at all, so one 1 uF serves both fits and nothing has to
# be swapped when the socket is populated; there is no second 1 uF beside C62.
# R35, the FLASH_CS1 pull-up, is NOT DNP -- GPIO0 must be held deselected whether or not
# the socket is populated. U24 is the only DNP component in the current design.
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
# POWER CHAIN BOUNDARY (owner-requested module interface, 2026-10-22):
#     ESC V -> J3.7 -> converter VIN / J17.3 (VBAT) [5 V converter] J17.1 -> 5V_IN
#     5V_IN -> Q1 -> V5_SYS -> U7/U12; USB_VBUS -> D1 -> V5_SYS
# 1. ESC raw battery feeds converter VIN; VBAT sensing remains on J17.3.
assert {ref for ref,pin in nets['VBAT'] if ref.startswith('J')}=={'J3','J17'},nets['VBAT']
assert not {(ref,pin) for ref,pin in nets['VBAT'] if ref.startswith('U')},nets['VBAT']
assert nets['VBAT']=={('J3','7'),('R27','1'),('J17','3')},nets['VBAT']
# 2. 5V_IN receives the regulated J17 output. J3.7 must never be on this rail.
#    It carries C19 and reaches exactly one semiconductor - Q1's DRAIN. It feeds no IO header row: the
#    IO block power column (J7) is V3V3_SYS on all 14 rows (owner, 2026-09-21: no servo/actuator
#    power from FC pads).
assert {(ref,pin) for ref,pin in nets['5V_IN'] if ref.startswith('J')}=={('J17','1')},nets['5V_IN']
assert {(ref,pin) for ref,pin in nets['5V_IN'] if ref[0] in 'UQD'}=={('Q1','3')},nets['5V_IN']
assert nets['5V_IN']=={('Q1','3'),('C19','1'),('J17','1')},nets['5V_IN']
# 3. V5_SYS is the OR output. It reaches no connector directly. Every IO block
#    row, GPS/ELRS included, is powered through the system buck. Its only loads are the two 3.3 V regulators and the WS2812 status LED (D20/C79,
#    <=60 mA, kept here deliberately so the LED works on USB-only bench power).
assert not {(ref,pin) for ref,pin in nets['V5_SYS'] if ref.startswith('J')},nets['V5_SYS']
assert nets['V5_SYS']=={('Q1','2'),('D1','1'),('U7','3'),('U12','1'),('R52','1'),
                        ('C8','1'),('C25','1'),('D20','4'),('C79','1')},nets['V5_SYS']
# 3z. The OR itself: the gate is USB_VBUS (so USB turns Q1 OFF), the diode anode is USB_VBUS, and
#     nothing else may sit on the gate node except the pull-down and the VBUS sense divider.
assert {('Q1','1'),('D1','2'),('R7','1'),('R29','1'),('R56','1')} <= nets['USB_VBUS'],nets['USB_VBUS']
# 3x. The USB power indicator is a two-part branch and nothing else may join it: R56 to the LED anode.
assert nets['USB_LED_A']=={('R56','2'),('D21','2')},nets['USB_LED_A']
assert nets['U7_SW']=={('U7','5'),('L2','1'),('C13','2')},nets['U7_SW']
assert nets['U7_BST']=={('U7','6'),('C13','1')},nets['U7_BST']
assert nets['U7_EN']=={('U7','2'),('R52','2')},nets['U7_EN']
assert nets['MCU_RUN']=={('U20','35'),('SW1','1'),('R10','2')},nets['MCU_RUN']
# 3y. Nets of the absent on-board pack buck, priority mux and 3.3 V stage must not exist.
assert not [n for n in nets if n in ('PWR_GOOD','PWR_SRC_ST','U7_VO','U7_FB','U7_SS','U7_SCONF',
                                     'U26_SW','U26_BST','U26_EN','U25_PR1','U25_OV1','U25_ILM',
                                     'U25_SS','USB_DP_MCU','USB_DM_MCU')],sorted(nets)
# 3a. V3V3_SYS supplies all fourteen IO power pins (J7 rows 1-14) and the
#     microSD socket; no other connector may carry the system rail.
assert {(ref,pin) for ref,pin in nets['V3V3_SYS'] if ref.startswith('J')}=={
    ('J7',str(p)) for p in range(1,15)} | {('J11','4')},nets['V3V3_SYS']
# 3b. The GND column is all ground, every pin of it, so every row has its own return.
assert {(ref,pin) for ref,pin in nets['GND'] if ref=='J8'}=={
    ('J8',str(_p)) for _p in range(1,15)},sorted(p for p in nets['GND'] if p[0]=='J8')
# 4. D+/D- run straight from the receptacle into the 27 R series pair: U8, the USBLC6 ESD array, is
#    gone, so each data net is exactly two receptacle pins plus one resistor end.
for _d,_r in (('USB_D-','R23'),('USB_D+','R22')):
    assert nets[_d]=={('J4','A%s'%('7' if _d=='USB_D-' else '6')),
                      ('J4','B%s'%('7' if _d=='USB_D-' else '6')),(_r,'1')},nets[_d]
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
# Dedicated sensor buses and native SD. Exact node sets reject shared buses,
# hidden pull resistors, extra devices, shorts and unterminated branches.
_U20=lambda g:('U20',PAD_OF_GPIO[g])
BUS_NODES = {
 'IMU2_SCK': {_U20(10),('U23','13')},
 'IMU2_MOSI': {_U20(11),('U23','14')},
 'IMU2_MISO': {_U20(8),('U23','1')},
 'IMU2_CS': {_U20(9),('U23','12'),('R51','2')},
 'IMU2_INT1': {_U20(7),('U23','4')},
 'IMU2_INT2': {_U20(6),('U23','9')},
 'ICM_SCK': {_U20(18),('U21','13')},
 'ICM_MOSI': {_U20(19),('U21','14')},
 'ICM_MISO': {_U20(16),('U21','1')},
 'ICM_CS': {_U20(20),('U21','12'),('R48','2')},
 'ICM_INT1': {_U20(15),('U21','4')},
 # ICM pin 9 (INT2/FSYNC/CLKIN) is the 32.000 kHz clock input driven by X1; it never reaches the MCU.
 'ICM_CLKIN': {('U21','9'),('X1','3')},
 'BARO_SCL': {_U20(23),('U22','2'),('R50','2')},
 'BARO_SDA': {_U20(22),('U22','4'),('R57','2')},
 'BARO_INT': {_U20(21),('U22','7')},
 'MAG_SDA': {_U20(12),('J6','5'),('R25','2')},
 'MAG_SCL': {_U20(13),('J6','6'),('R26','2')},
 'ELRS_RX': {_U20(24),('J6','1')},
 'ELRS_TX': {_U20(25),('J6','2')},
 'GPS_TX': {_U20(17),('J6','4')},
 'GPS_RX': {_U20(14),('J6','3')},
 'SD_CLK_MCU': {('U20','40'),('R58','1')},
 'SD_CLK': {('R58','2'),('J11','5')},
 'SD_CMD': {('U20','42'),('J11','3'),('R36','2')},
 'SD_DAT0': {('U20','36'),('J11','7'),('R37','2')},
 'SD_DAT1': {('U20','37'),('J11','8'),('R38','2')},
 'SD_DAT2': {('U20','38'),('J11','1'),('R39','2')},
 'SD_DAT3': {('U20','39'),('J11','2'),('R40','2')},
}
for name, nodes in BUS_NODES.items():
    assert nets.get(name) == nodes, (name, nodes, nets.get(name))
assert pin_net[('U22','6')] == 'V3V3_ANA', 'BMP581 CSB must select I2C'
assert pin_net[('U22','5')] == 'GND', 'BMP581 address must be 0x46'
assert not any(n.startswith(('SENS_', 'HG_ACC_', 'IMU_')) or n == 'BARO_CS' for n in nets)
# RP2354B Table 3 / RP2350 Table 645: SPI0 RX16/SCK18/TX19 (ICM-45686), SPI1 RX8/CSn9/SCK10/TX11
# (LSM6DSK320X), I2C0 SDA12/SCL13 (MAG), I2C1 SDA22/SCL23 (BMP581), UART1 TX24/RX25 (ELRS),
# UART0 TX14 (F11 aux)/RX17 (F2) (GPS, hardware UART; no PIO UART for GPS). SD DAT pins increase
# consecutively; all six SD signals, the LED and the ESC PIO signals sit in the GPIO16-47 PIO window
# (GPIOBASE = 16).
assert [PINOUT[g] for g in (16,18,19)] == ['ICM_MISO','ICM_SCK','ICM_MOSI']
assert [PINOUT[g] for g in (8,10,11,9)] == ['IMU2_MISO','IMU2_SCK','IMU2_MOSI','IMU2_CS']
assert [PINOUT[g] for g in (12,13)] == ['MAG_SDA','MAG_SCL']
assert [PINOUT[g] for g in (22,23)] == ['BARO_SDA','BARO_SCL']
assert [PINOUT[g] for g in (24,25)] == ['ELRS_RX','ELRS_TX']
assert [PINOUT[g] for g in (14,17)] == ['GPS_RX','GPS_TX']
NC_SPARES = (1, 26, 27, 35)
assert [PINOUT[g] for g in NC_SPARES] == [None]*4
# UART function per RP2350 Table 645: GPS = UART0 (GPIO14 TX via F11 aux, GPIO17 RX via F2), ELRS = UART1 (GPIO24 TX, GPIO25 RX)
UART_FUNC = {14: ('UART0', 'TX', 11), 17: ('UART0', 'RX', 2), 24: ('UART1', 'TX', 2), 25: ('UART1', 'RX', 2)}
assert {PINOUT[g]: UART_FUNC[g][:2] for g in (14, 17)} == {'GPS_RX': ('UART0', 'TX'), 'GPS_TX': ('UART0', 'RX')}
assert {PINOUT[g]: UART_FUNC[g][:2] for g in (24, 25)} == {'ELRS_RX': ('UART1', 'TX'), 'ELRS_TX': ('UART1', 'RX')}
assert UART_FUNC[14][2] == 11 and UART_FUNC[17][2] == 2
# servo PWM: GPIO5/4 = slice 2 B/A (PWM5/PWM6 nets), GPIO3/2 = slice 1 B/A (PWM7/PWM8 nets)
assert [(g//2)%8 for g in (5,4,3,2)] == [2,2,1,1]
assert [PINOUT[g] for g in (5,4,3,2)] == ['PWM5','PWM6','PWM7','PWM8']
sd_data_gpio = [next(g for g,n in PINOUT.items() if n == f'SD_DAT{i}') for i in range(4)]
assert sd_data_gpio == list(range(sd_data_gpio[0], sd_data_gpio[0]+4))
sd_gpio = sd_data_gpio + [next(g for g,n in PINOUT.items() if n == s)
                         for s in ('SD_CMD','SD_CLK_MCU')]
assert all(16 <= g <= 47 for g in sd_gpio), sd_gpio
pio_gpio = sd_gpio + [next(g for g,n in PINOUT.items() if n == s)
                      for s in ('LED_DATA','ESC_TELEM_RX','PWM1','PWM2','PWM3','PWM4')]
assert all(16 <= g <= 47 for g in pio_gpio), pio_gpio
components={c.get('ref'):c for c in root.find('components')}
assert components['J17'].findtext('footprint') == 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical'
assert components['J3'].findtext('footprint') == 'MARV_Packages:PadRow_1x08_P2.00mm'
# External pull-up resistance and rail, independent of any MCU internal pulls.
for ref, value, rail in [('R48','10k','V3V3_ANA'),('R51','10k','V3V3_ANA'),
                         ('R50','4.7k','V3V3_ANA'),('R57','4.7k','V3V3_ANA')] + [
                         (f'R{r}','10k','V3V3_SYS') for r in range(36,41)]:
    assert components[ref].findtext('value').split(',')[0].strip() == value, (ref, value)
    assert pin_net[(ref,'1')] == rail, (ref, rail)
assert components['R58'].findtext('value') == '22', 'SD source damping must be 22 ohm'
assert 'ICM_INT2' not in nets, 'ICM pin 9 is CLKIN; there is no ICM_INT2 net'
assert components['X1'].findtext('footprint') == 'MARV_Packages:Oscillator_SMD_HCI_1521H-4Pin_2.0x1.6mm'
assert components['X1'].findtext('value').startswith('1521H-32K000J18DTSL 32.000kHz')
assert any(f.get('name') == 'LCSC' and f.text == 'C19674133' for f in components['X1'].findall('./fields/field'))
assert components['C1'].findtext('value').startswith('100n'), components['C1'].findtext('value')
assert 'C2' not in components, 'C2 must be absent: the HCI part has no VIO pin to decouple'
# Locking Molex 47219-2001 has eight card contacts and a shield, no detect switch.
assert 'R41' not in components and 'SD_DET' not in nets
assert {pin for ref,pin in pin_net if ref == 'J11'} == set(map(str, range(1,9))) | {'SH'}
assert pin_net[('J11','SH')] == 'GND'
assert components['J11'].findtext('footprint') == 'MARV_Packages:microSD_HC_Molex_47219-2001'
assert any(f.get('name') == 'LCSC' and f.text == 'C164170'
           for f in components['J11'].findall('./fields/field'))
# the temporary MCU-interface headers are gone
assert 'J5' not in components,'J5 (temporary MCU-interface header) still present'
FPLIBS=[Path('/usr/share/kicad/footprints'),Path(__file__).resolve().parents[1]]
for ref,c in components.items():
 fp=c.findtext('footprint')
 assert fp,(ref,'missing footprint')
 lib,name=fp.split(':')
 path=next((d/(lib+'.pretty')/(name+'.kicad_mod') for d in FPLIBS if (d/(lib+'.pretty')/(name+'.kicad_mod')).exists()),None)
 assert path,(ref,'missing footprint file',fp)
 pads={unquote(p[1]) for p in parse_sexpr(path.read_text())
       if isinstance(p, list) and p and p[0] == 'pad' and unquote(p[1])}
 used={pin for rr,pin in pin_net if rr==ref}
 assert used<=pads,(ref,fp,'pins absent in footprint',used-pads)

# Validate the 48-GPIO pin plan: every GPIO must be on the expected net per PINOUT.  No GPIO is left
# unconnected except the four no-connect spares GPIO1/26/27/35.
for gpio_num in range(48):
 pad = PAD_OF_GPIO[gpio_num]
 expected_net = PINOUT[gpio_num]
 actual_net = netof(('U20', pad))
 assert (expected_net is None) == (gpio_num in NC_SPARES), f"GPIO{gpio_num} no-connect plan mismatch"
 assert actual_net == expected_net, \
  f"PINOUT.md violated: GPIO{gpio_num} (U20 pad {pad}) is on {actual_net}, plan says {expected_net}; update PINOUT.md and this table together"

# Validate the spare GPIO split: FOUR spares are exposed on the IO block signal column (rows 11-14)
# and FOUR carry no-connect flags (GPIO1, 26, 27, 35).  Moving one means editing PINOUT.md and this
# table together.
EXPOSED_SPARES = {44, 45, 46, 47}
assert not (EXPOSED_SPARES & set(NC_SPARES))
spare_nets = {'IO_GPIO44', 'IO_GPIO45', 'IO_GPIO46', 'IO_GPIO47'}
assert {PINOUT[g] for g in EXPOSED_SPARES} == spare_nets, \
 f"Exposed spare nets mismatch: {{PINOUT[g] for g in EXPOSED_SPARES}} vs {spare_nets}"
for gpio_num in sorted(EXPOSED_SPARES):
 net_name = PINOUT[gpio_num]
 j6_nodes = {(ref, pin) for ref, pin in nets[net_name] if ref == 'J6'}
 assert j6_nodes, f"Exposed spare GPIO {gpio_num} ({net_name}) does not appear on J6"
# KiCad names the single-node net of a pin with a no-connect flag 'unconnected-(U20-...)'.
for gpio_num in NC_SPARES:
 pin = ('U20', PAD_OF_GPIO[gpio_num])
 nc_net = pin_net.get(pin)
 assert nc_net and nc_net.startswith('unconnected-'), (gpio_num, nc_net)
 assert nets[nc_net] == {pin}, (gpio_num, nc_net, nets[nc_net])
assert not [r for r in components if r.startswith('TP')], 'test points are absent'
assert not [n for n in nets if n.startswith('SPARE_GPIO')], 'spare GPIOs are no-connect, not nets'
# the MAG bus pull-ups follow the MAG nets (V3V3_SYS), the BMP581 pull-ups follow BARO (V3V3_ANA)
assert pin_net[('R25','1')] == 'V3V3_SYS' and pin_net[('R26','1')] == 'V3V3_SYS'
assert components['R25'].findtext('value').split(',')[0].strip() == '4.7k'
assert components['R26'].findtext('value').split(',')[0].strip() == '4.7k'
# ... and no IO_GPIO net survives for any other GPIO
assert not [n for n in nets if n in ('IO_GPIO9','IO_GPIO12','IO_GPIO18','IO_GPIO21','IO_GPIO26','IO_GPIO27')], \
 sorted(n for n in nets if n.startswith('IO_GPIO'))
# no GPIO pad of U20 other than the four no-connect spares is left unconnected
assert [g for g in range(48) if pin_net.get(('U20', PAD_OF_GPIO[g]), 'unconnected-').startswith('unconnected-')] == list(NC_SPARES)

print(f'PASS: 48-GPIO pin plan (GPS on hardware UART0 GPIO14/17, ELRS on UART1 GPIO24/25, 4 exposed spares on J6, 4 no-connect spares GPIO1/26/27/35, no other unconnected GPIO), {len(expected)} critical pin mappings,\n'
      f'      USB supply pins, the BEC -> 5V_IN -> Q1/D1 -> V5_SYS -> U7 -> V3V3_SYS boundary and the\n'
      f'      VBAT module-feed/sense boundary, J17 pinout, the ESC pad-row order,\n'
      f'      the U21 CLKIN oscillator X1 (HCI 1521H-32K000J18DTSL 32.000 kHz: Vcc and E/D on V3V3_ANA with C1, OUT on ICM_CLKIN, no ICM INT2),\n'
      f'      J6/J7/J8 IO-block row map, the PWM1-4 / PWM5-8 split, the {len(_DNP)} DNP\n'
      f'      flash-expansion socket (U24; the PSRAM-ready 1 uF C62 and R35 fitted) and footprint coverage for {len(components)} components.')
