#!/usr/bin/env python3
"""Build reviewable KiCad power sheets using local KiCad symbols.

All file mutations write files directly. --inspect only prints pin inventories.
Generated sheets are integrated into MARV-V2; the original root is backed up. No third-party Python packages.
"""
import copy
import json
import math
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = Path('/usr/share/kicad/symbols')
NS = uuid.UUID('bd28951c-d674-40d5-9c88-90e06bd5a982')

def uid(key):
    return str(uuid.uuid5(NS, key))

def parse(text):
    toks = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack, root = [], None
    for tok in toks:
        if tok == '(':
            node = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
        elif tok == ')':
            root = stack.pop()
        else:
            stack[-1].append(tok)
    return root

def children(node, key):
    return [v for v in node if isinstance(v, list) and v and v[0] == key]

def first(node, key):
    return next((v for v in children(node, key)), None)

def unquote(s):
    return json.loads(s) if s.startswith('"') else s

def q(s):
    return json.dumps(str(s))

def dump(node):
    if isinstance(node, str):
        return node
    return '(' + ' '.join(dump(v) for v in node) + ')'

CACHE = {}
def symbol(libid):
    if libid in CUSTOM:
        return parse(CUSTOM[libid])
    lib, name = libid.split(':')
    if lib not in CACHE:
        path = LIB / (lib+'.kicad_sym')
        if not path.exists():
            path = ROOT / (lib+'.kicad_sym')
        CACHE[lib] = {unquote(v[1]): v for v in children(parse(path.read_text()), 'symbol')}
    raw = copy.deepcopy(CACHE[lib][name])
    parent = first(raw, 'extends')
    if parent:
        base = symbol(lib + ':' + unquote(parent[1]))
        base[1] = q(name)
        for v in children(base, 'symbol'):
            v[1] = q(name + '_' + unquote(v[1]).split('_')[-2] + '_' + unquote(v[1]).split('_')[-1])
        ownprops = {v[1] for v in children(raw, 'property')}
        base = [v for v in base if not (isinstance(v, list) and v[0] == 'property' and v[1] in ownprops)]
        base.extend(v for v in raw[2:] if isinstance(v, list) and v[0] not in ('extends', 'symbol'))
        raw = base
    return raw

def pins(sym):
    return [p for unit in children(sym, 'symbol') for p in children(unit, 'pin')]

# Locally authored symbols with no upstream KiCad equivalent, emitted into MARV_Power.kicad_sym verbatim.
#
# TPS2121RUX - TI TPS2121, dual-input single-output priority power mux (datasheet SLVSEA3F, Aug 2018 /
# rev F Aug 2020). Package and pin numbers are taken from Sec 6 "Pin Configuration and Functions",
# Figure 6-2 and the Pin Functions table: RUX0012A, 12-pin VQFN-HR, 2.0 x 2.5 mm, 0.5 mm pitch, and the
# package has NO separate exposed thermal pad (pads 1/8 = OUT and 2/7 = IN2/IN1 are the wide power pads).
# Pin numbers: 1 OUT, 2 IN2, 3 CP2, 4 OV2, 5 OV1, 6 PR1, 7 IN1, 8 OUT, 9 ST, 10 ILM, 11 SS, 12 GND.
# ELECTRICAL TYPES: the two OUT pins are typed passive rather than power_out for two reasons - a single
# net may carry only one power_out, and this sheet keeps the explicit V5_SYS PWR_FLAG as that rail's
# declared driver (the same convention the superseded LM66100_OR symbol used for its VOUT pin). ST is
# open_collector per Sec 10.2.3 ("The ST pin can be pulled high with a resistor"); PR1/OV1/OV2/CP2 are
# comparator inputs; ILM and SS are resistor/capacitor programming pins and are typed passive.
CUSTOM={'MARV_Power:TPS2121RUX':'''(symbol "TPS2121RUX" (exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes) (duplicate_pin_numbers_are_jumpers no)
 (property "Reference" "U" (at -10.16 16.51 0) (show_name no) (do_not_autoplace no) (effects (font (size 1.27 1.27)) (justify left)))
 (property "Value" "TPS2121RUXR" (at -10.16 13.97 0) (show_name no) (do_not_autoplace no) (effects (font (size 1.27 1.27)) (justify left)))
 (property "Footprint" "MARV_Packages:Texas_VQFN-HR-12_2x2.5mm_P0.5mm" (at 0 -19.05 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
 (property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps2121.pdf" (at 0 -21.59 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
 (property "Description" "2.8-22 V dual-input single-output priority power MUX, seamless switchover, reverse-current blocking on both inputs, adjustable OV / priority / current limit, VQFN-HR-12 (RUX0012A)" (at 0 -24.13 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
 (property "ki_keywords" "power mux ORing priority ideal diode reverse current blocking Texas Instruments" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
 (property "ki_fp_filters" "*VQFN*HR*12*" (at 0 0 0) (show_name no) (do_not_autoplace no) (hide yes) (effects (font (size 1.27 1.27))))
 (symbol "TPS2121RUX_0_1" (rectangle (start -10.16 12.7) (end 10.16 -12.7) (stroke (width 0.254) (type default)) (fill (type background))))
 (symbol "TPS2121RUX_1_1"
  (pin power_in line (at -12.7 7.62 0) (length 2.54) (name "IN1" (effects (font (size 1.27 1.27)))) (number "7" (effects (font (size 1.27 1.27)))))
  (pin power_in line (at -12.7 2.54 0) (length 2.54) (name "IN2" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
  (pin input line (at -12.7 -2.54 0) (length 2.54) (name "PR1" (effects (font (size 1.27 1.27)))) (number "6" (effects (font (size 1.27 1.27)))))
  (pin input line (at -12.7 -5.08 0) (length 2.54) (name "OV1" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
  (pin input line (at -12.7 -7.62 0) (length 2.54) (name "OV2" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
  (pin input line (at -12.7 -10.16 0) (length 2.54) (name "CP2" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 12.7 7.62 180) (length 2.54) (name "OUT" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 12.7 5.08 180) (length 2.54) (name "OUT" (effects (font (size 1.27 1.27)))) (number "8" (effects (font (size 1.27 1.27)))))
  (pin open_collector line (at 12.7 0 180) (length 2.54) (name "ST" (effects (font (size 1.27 1.27)))) (number "9" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 12.7 -5.08 180) (length 2.54) (name "ILM" (effects (font (size 1.27 1.27)))) (number "10" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 12.7 -7.62 180) (length 2.54) (name "SS" (effects (font (size 1.27 1.27)))) (number "11" (effects (font (size 1.27 1.27)))))
  (pin power_in line (at 0 -15.24 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "12" (effects (font (size 1.27 1.27)))))
 )
 (embedded_fonts no))'''}

class Sheet:
    def __init__(self, name, title, page):
        self.name,self.title,self.page=name,title,page
        self.id=uid(name)
        self.libs={}
        self.items=[]
        self.bom=[]
        self.n=0
    def note(self,text,x,y,size=1.5):
        self.n+=1
        self.items.append(f'(text {q(text)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left top)) (uuid {uid(self.name+"note"+str(self.n))}))')
    def wire(self,a,b):
        self.n+=1
        self.items.append(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {uid(self.name+"wire"+str(self.n))}))')
    def label(self,net,x,y,angle=0):
        self.n+=1
        self.items.append(f'(global_label {q(net)} (shape passive) (at {x} {y} {angle}) (effects (font (size 0.9 0.9)) (justify {"right" if angle==180 else "left"})) (uuid {uid(self.name+"lab"+str(self.n))}))')
    def add(self,ref,libid,value,x,y,nets,foot=None,refofs=None,vlab=False):
        x,y=round(round(x/1.27)*1.27,5),round(round(y/1.27)*1.27,5)
        sym=symbol(libid)
        if libid not in self.libs:
            embedded=copy.deepcopy(sym); embedded[1]=q(libid)
            self.libs[libid]=embedded
        props={unquote(p[1]):unquote(p[2]) for p in children(sym,'property')}
        fp=foot if foot is not None else props.get('Footprint','')
        inst=f'(symbol (lib_id {q(libid)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)})'
        if refofs:
            rx,ry,vy=refofs[0],refofs[1],refofs[1]+2.54
        else:
            rx=x-7.62; ry=y-29.21 if ref=='J4' else y-16.51; vy=y-26.67 if ref=='J4' else y-13.97
        for key,val,xx,yy,hide in [('Reference',ref,rx,ry,False),('Value',value,rx,vy,False),('Footprint',fp,x,y,True),('Datasheet',props.get('Datasheet',''),x,y,True)]:
            inst+=f' (property {q(key)} {q(val)} (at {xx} {yy} 0) (effects (font (size 1 1)) (justify left) {"(hide yes)" if hide else ""}))'
        seen_connections=set()
        for p in pins(sym):
            num=unquote(first(p,'number')[1]); at=first(p,'at')
            px,py=round(x+float(at[1]),5),round(y-float(at[2]),5)
            if num not in nets:
                if num == "SH" and "S1" in nets:
                    nets[num] = nets.pop("S1")
                else:
                    raise ValueError((ref,"missing pin",num))
            net=nets[num]
            if net is None:
                self.items.append(f'(no_connect (at {px} {py}) (uuid {uid(ref+"nc"+num)}))')
            else:
                angle=int(at[3]); dx,dy={0:(-5.08,0),180:(5.08,0),90:(0,5.08),270:(0,-5.08)}[angle]
                end=(round(px+dx,5),round(py+dy,5))
                if (px,py,net) not in seen_connections:
                    self.wire((px,py),end)
                    self.label(net,*end,({0:180,180:0,90:270,270:90} if vlab else {0:180,180:0,90:0,270:0})[angle])
                    seen_connections.add((px,py,net))
            inst+=f' (pin {q(num)} (uuid {uid(ref+"pin"+num)}))'
        inst+=f' (instances (project "MARV-V2" (path "/{uid("power-root")}/{self.id}" (reference {q(ref)}) (unit 1)))))'
        self.items.append(inst)
        self.bom.append((ref,value,fp,self.name))
    def passive(self,ref,kind,value,x,y,a,b,foot=None):
        if foot is None:
            foot={'R':'Resistor_SMD:R_0603_1608Metric','C':'Capacitor_SMD:C_0805_2012Metric','L':'Inductor_SMD:L_6.3x6.3_H3','Fuse':'Fuse:Fuse_1206_3216Metric','D_Schottky':'Diode_SMD:D_SMA','D_TVS':'Diode_SMD:D_SMB'}[kind]
        self.add(ref,'Device:'+kind,value,x,y,{'1':a,'2':b},foot)
    def render(self):
        return f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {self.id}) (paper "A3") (title_block (title {q(self.title)}) (date "2026-09-14") (rev "P0 - REVIEW ONLY")) (lib_symbols '+ '\n'.join(dump(s) for s in self.libs.values())+')\n'+'\n'.join(self.items)+'\n(embedded_fonts no))\n'

def patch_files(files):
    for name,content in files.items():
        path=ROOT/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content)

V3='V3V3_SYS'
ANA='V3V3_ANA'

# (package pin, GPIO name, net or None for no-connect, function note)
MCU_GPIO=[
 ('77','GPIO0','FLASH_CS1','QMI CS1n, log flash select'),
 ('78','GPIO1',None,'spare'),
 ('79','GPIO2','PWM1','PWM1 A'),
 ('80','GPIO3','PWM2','PWM1 B'),
 ('1','GPIO4','PWM3','PWM2 A'),
 ('2','GPIO5','PWM4','PWM2 B'),
 ('3','GPIO6','MAG_SDA','I2C1 SDA'),
 ('4','GPIO7','MAG_SCL','I2C1 SCL'),
 ('6','GPIO8','ELRS_RX','UART1 TX -> radio RX'),
 ('7','GPIO9','ELRS_TX','UART1 RX <- radio TX'),
 ('8','GPIO10','PWM5','PWM5 A'),
 ('9','GPIO11','PWM6','PWM5 B'),
 ('11','GPIO12','GPS_RX','UART0 TX -> GPS RX'),
 ('12','GPIO13','GPS_TX','UART0 RX <- GPS TX'),
 ('13','GPIO14','PWM7','PWM7 A'),
 ('14','GPIO15','PWM8','PWM7 B'),
 ('16','GPIO16','SENS_MISO','SPI0 RX'),
 ('17','GPIO17','HG_ACC_CS','ADXL375 CS'),
 ('18','GPIO18','SENS_SCK','SPI0 SCK'),
 ('19','GPIO19','SENS_MOSI','SPI0 TX'),
 ('20','GPIO20','IMU_CS','ICM-45686 AP_CS'),
 ('21','GPIO21',None,'spare'),
 ('22','GPIO22','BARO_CS','BMP581 CSB'),
 ('23','GPIO23','IMU_INT1','ICM-45686 INT1'),
 ('25','GPIO24','IMU_INT2','ICM-45686 INT2/FSYNC/CLKIN'),
 ('26','GPIO25','BARO_INT','BMP581 INT'),
 ('27','GPIO26','LED_STAT','green status LED'),
 ('28','GPIO27','LED_WARN','red warning LED'),
 ('36','GPIO28','BUZZ_PWM','buzzer gate drive'),
 ('37','GPIO29','HG_ACC_INT','ADXL375 INT1'),
 ('38','GPIO30',None,'spare'),
 ('39','GPIO31',None,'spare'),
 ('40','GPIO32','SD_CLK','microSD CLK (PIO)'),
 ('42','GPIO33','SD_CMD','microSD CMD'),
 ('43','GPIO34','SD_D0','microSD DAT0'),
 ('44','GPIO35','SD_D1','microSD DAT1'),
 ('45','GPIO36','SD_D2','microSD DAT2'),
 ('46','GPIO37','SD_D3','microSD DAT3'),
 ('47','GPIO38','SD_DET','microSD card detect'),
 ('48','GPIO39','PWR_SRC_ST','U25 TPS2121 ST, open drain'),
 ('49','GPIO40','VIN_SENSE','ADC0, 5V_IN 22k/10k divider'),
 ('52','GPIO41','VBUS_SENSE','ADC1, USB_VBUS 10k/15k divider'),
 ('53','GPIO42',None,'ADC2 spare'),
 ('54','GPIO43',None,'ADC3 spare'),
 ('55','GPIO44',None,'ADC4 spare'),
 ('56','GPIO45',None,'ADC5 spare'),
 ('57','GPIO46',None,'ADC6 spare'),
 ('58','GPIO47',None,'ADC7 spare'),
]

def mcu_sheet():
    s=Sheet('mcu','BOARD 1 / RP2354B',5)
    s.note('RP2354B, QFN-80, 2 MB in-package QSPI flash. Digital rails on V3V3_SYS, core DVDD from the on-chip buck.\n'
           'RAIL SPLIT: V3V3_ANA (TPS7A20 LDO) now feeds exactly one RP2354B pin - ADC_AVDD (pin 59, with C40). The core regulator input\n'
           'filter R20/C41 that produces VREG_AVDD is fed from V3V3_SYS instead, so the buck-converter reference current no longer flows out\n'
           'of the low-noise analog rail and the sensors do not share a rail with it; V3V3_ANA is left carrying only ADC_AVDD and the MEMS.\n'
           'Decoupling, core regulator, crystal and BOOTSEL follow the RP2350 hardware design guide; every pin net is a global label.',15,10,1.6)
    nets={}
    for pin in ('5','15','24','29','41','50','60','76'): nets[pin]=V3     # IOVDD (stacked in the symbol)
    nets.update({'68':V3,'69':V3,'64':V3})                               # USB_OTP_VDD, QSPI_IOVDD, VREG_VIN
    nets.update({'59':ANA,'61':'VREG_AVDD'})                             # ADC_AVDD, VREG_AVDD (through R20)
    nets.update({'10':'DVDD','32':'DVDD','51':'DVDD','63':'VREG_LX','65':'DVDD','62':'GND','81':'GND'})
    nets.update({'30':'XIN','31':'XOUT','33':'SWCLK','34':'SWDIO','35':'PWR_GOOD'})
    nets.update({'66':'USB_DM_RP','67':'USB_DP_RP'})
    nets.update({'70':'QSPI_SD3','71':'QSPI_SCLK','72':'QSPI_SD0','73':'QSPI_SD2','74':'QSPI_SD1','75':'QSPI_SS'})
    nets.update({pin:net for pin,gpio,net,fn in MCU_GPIO})
    s.add('U20','MCU_RaspberryPi:RP2354B','RP2354B',200,150,nets,'MARV_Packages:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm',refofs=(152,234),vlab=True)

    left=[(25+35*c,40+28*r) for r in range(8) for c in range(4)]
    for i in range(8):
        s.passive('C%d'%(30+i),'C','100n / 16 V X7R, IOVDD pin %s'%('5 15 24 29 41 50 60 76'.split()[i]),*left[i],V3,'GND')
    s.passive('C38','C','100n / 16 V X7R, pins 68+69',*left[8],V3,'GND')
    s.passive('C39','C','4.7u / 10 V X7R, VREG_VIN',*left[9],V3,'GND')
    s.passive('C40','C','100n / 16 V X7R, ADC_AVDD',*left[10],ANA,'GND')
    s.passive('R20','R','33 / 1%, VREG_AVDD filter',*left[11],V3,'VREG_AVDD')
    s.passive('C41','C','4.7u / 10 V X7R, VREG_AVDD',*left[12],'VREG_AVDD','GND')
    s.passive('L20','L','3.3u, 0806 AOTA-B201610S3R3',*left[13],'VREG_LX','DVDD',foot='Inductor_SMD:L_Murata_DFE201610P')
    s.passive('C42','C','100n / 16 V X7R, DVDD pin 10',*left[14],'DVDD','GND')
    s.passive('C43','C','100n / 16 V X7R, DVDD pin 32',*left[15],'DVDD','GND')
    s.passive('C44','C','100n / 16 V X7R, DVDD pin 51',*left[16],'DVDD','GND')
    s.passive('C45','C','4.7u / 10 V X7R, DVDD bulk',*left[17],'DVDD','GND')
    s.passive('R22','R','27 / 1%, USB D+ series',*left[18],'USB_DP_MCU','USB_DP_RP')
    s.passive('R23','R','27 / 1%, USB D- series',*left[19],'USB_DM_MCU','USB_DM_RP')
    s.passive('R21','R','1k / 1%, crystal drive limit',*left[20],'XOUT','XTAL_DRV')
    s.passive('C46','C','15p / 50 V C0G',*left[21],'XIN','GND',foot='Capacitor_SMD:C_0402_1005Metric')
    s.add('Y1','Device:Crystal_GND24','12 MHz ABM8-272-T3, CL 10 pF',*left[22],{'1':'XIN','2':'GND','3':'XTAL_DRV','4':'GND'},'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm')
    s.passive('C47','C','15p / 50 V C0G',*left[23],'XTAL_DRV','GND',foot='Capacitor_SMD:C_0402_1005Metric')
    s.passive('R24','R','1k, BOOTSEL strap',*left[24],'QSPI_SS','BOOT_BTN')
    s.passive('R25','R','4.7k, I2C1 SDA pull-up',*left[25],V3,'MAG_SDA')
    s.passive('R26','R','4.7k, I2C1 SCL pull-up',*left[26],V3,'MAG_SCL')
    s.add('SW1','Switch:SW_Push','RESET (RUN to GND)',*left[27],{'1':'PWR_GOOD','2':'GND'},'Button_Switch_SMD:SW_SPST_B3U-1000P')
    s.add('SW2','Switch:SW_Push','BOOTSEL (via R24)',40,left[28][1],{'1':'BOOT_BTN','2':'GND'},'Button_Switch_SMD:SW_SPST_B3U-1000P')
    s.note('Crystal circuit per design guide Sec 4: ABM8-272-T3, 15 pF each side (7.5 pF series + ~3 pF stray = 10.5 pF vs CL 10 pF),\n'
           '1 k in the XOUT leg to limit drive with a 50 ohm ESR crystal. C38 is the single design-guide decoupling exception (pins 68+69 share it).\n'
           'VREG_AVDD RC = 33 ohm + 4.7 uF (design guide Sec 2.1), taken from V3V3_SYS; VREG_FB is tied to DVDD, VREG_PGND to GND, EP to GND.',15,247,1.3)

    s.note('PORT NAMING: a port label is named for the peripheral pin it comes from, so GPS_TX / ELRS_TX are module outputs\n'
           'and land on MCU UART RX pins, while GPS_RX / ELRS_RX are module inputs fed by the MCU UART TX pins. On J6/J7\n'
           '(POWER 3, Pixhawk DS-009 order 1 VCC / 2 TX / 3 RX / 4 GND) pin 2 is therefore GPS_RX / ELRS_RX.\n'
           'J6 and J7 VCC are on V5_SYS; J9 VCC stays on V3V3_SYS. All port SIGNAL pins remain 3.3 V CMOS.\n'
           'GPIO39 (pin 48) is no longer spare: it reads PWR_SRC_ST, the open-drain ST output of U25 (TPS2121), which is\n'
           'high while 5V_IN (IN1) powers V5_SYS and low while USB VBUS (IN2) does.',155,233,1.3)
    rows=['%-7s %3s  %-12s %s'%(g,p_,n or '(no connect)',f) for p_,g,n,f in MCU_GPIO]
    s.note('GPIO MAP (pin = QFN-80 pin)\n'+'\n'.join(rows[:24]),250,14,1.3)
    s.note('\n'+'\n'.join(rows[24:]),338,14,1.3)

    s.add('J10','Connector_Generic:Conn_02x05_Odd_Even','SWD, Cortex-M 10-pin 1.27 mm',270,92,
          {'1':V3,'2':'SWDIO','3':'GND','4':'SWCLK','5':'GND','6':None,'7':None,'8':None,'9':'GND','10':'PWR_GOOD'},
          'Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD')
    s.note('J10 pin 1 is 3V3 OUT for debugger reference only - never power the board from it. Pin 10 is the\n'
           'debugger reset line on PWR_GOOD/RUN; pins 6-8 (SWO, KEY, NC) unused. RUN is held by the TPS62913\n'
           'power-good pull-up on POWER 2, so the MCU cannot run before V3V3_SYS is in regulation.',250,106,1.3)

    right=[(265+35*c,140+28*r) for r in range(2) for c in range(4)]
    s.passive('R27','R','22k / 1%, 5V_IN top',*right[0],'5V_IN','VIN_SENSE')
    s.passive('R28','R','10k / 1%, 5V_IN bottom',*right[1],'VIN_SENSE','GND')
    s.passive('C48','C','100n / 16 V X7R, ADC0',*right[2],'VIN_SENSE','GND')
    s.passive('R29','R','10k / 1%, VBUS top',*right[3],'USB_VBUS','VBUS_SENSE')
    s.passive('R30','R','15k / 1%, VBUS bottom',*right[4],'VBUS_SENSE','GND')
    s.passive('C49','C','100n / 16 V X7R, ADC1',*right[5],'VBUS_SENSE','GND')
    s.passive('R31','R','1k, green status LED',*right[6],'LED_STAT','LED1_A')
    s.passive('R32','R','1k, red warning LED',*right[7],'LED_WARN','LED2_A')
    s.add('D20','Device:LED','green, status',270,196,{'1':'GND','2':'LED1_A'},'LED_SMD:LED_0603_1608Metric')
    s.add('D21','Device:LED','red, warning',335,196,{'1':'GND','2':'LED2_A'},'LED_SMD:LED_0603_1608Metric')
    s.passive('R33','R','1k, gate series',265,222,'BUZZ_PWM','BUZZ_G')
    s.passive('R34','R','100k, gate pull-down',300,222,'BUZZ_G','GND')
    s.add('Q20','Transistor_FET:2N7002','2N7002',345,222,{'1':'BUZZ_G','2':'GND','3':'BUZZ_D'},'Package_TO_SOT_SMD:SOT-23')
    s.add('BZ1','Device:Buzzer','5 V active buzzer',390,205,{'1':'V5_SYS','2':'BUZZ_D'},'Buzzer_Beeper:Buzzer_12x9.5RM7.6')
    s.add('D22','Device:D_Schottky','flyback across BZ1',390,240,{'1':'V5_SYS','2':'BUZZ_D'},'Diode_SMD:D_SOD-123')
    s.note('Telemetry dividers, 100 nF at each ADC pin. VIN_SENSE (R27/R28 22k/10k) scales by 10/32 = 0.3125, so the 3.3 V\n'
           'ADC full scale is 10.56 V: 1.56 V at 5.00 V in, 1.72 V at 5.50 V, and a 2S mis-plug at 8.4 V still reads on-scale\n'
           '(2.63 V) instead of pinning the input, which is the point of the wider divider. VBUS_SENSE keeps 10k/15k.\n'
           'Buzzer runs from V5_SYS (avionics OR output), never from the servo bus; D22 clamps the coil kick.\n'
           'QSPI_* are the dedicated QSPI pads: they reach the in-package flash die AND the package pins\n'
           '(RP2350 datasheet Sec 14.3), so U24 shares the bus with GPIO0/QMI CS1n (FLASH_CS1) as its select.\n'
           'RP2354 requires QSPI_IOVDD = 3.3 V, and IOVDD = 3.3 V to run a second QSPI device (Sec 14.9).',15,258,1.3)
    return s

def sensors_sheet():
    s=Sheet('sensors','BOARD 2 / IMU, barometer, high-g',6)
    s.note('All three sensors run 4-wire SPI on the shared SENS_SCK / SENS_MOSI / SENS_MISO bus with one chip select each,\n'
           'and are powered from V3V3_ANA (TPS7A20 LDO). Every supply pin on this sheet gets 100 nF + 1 uF: BMP581 and\n'
           'ADXL375 because their own datasheets call for the pair, the ICM-45686 as a deliberate addition - its\n'
           'datasheet BOM (DS-000577 Rev 1.0 Table 11) lists 0.1 uF only.',15,10,1.6)
    s.add('U21','MARV_Sensors:ICM-45686','ICM-45686 6-axis IMU',90,85,
          {'1':'SENS_MISO','2':None,'3':None,'4':'IMU_INT1','5':ANA,'6':'GND','7':None,'8':ANA,
           '9':'IMU_INT2','10':None,'11':None,'12':'IMU_CS','13':'SENS_SCK','14':'SENS_MOSI'},
          None,refofs=(75,120),vlab=True)
    s.add('U22','MARV_Sensors:BMP581','BMP581 barometer',220,85,
          {'1':ANA,'2':'SENS_SCK','3':'GND','4':'SENS_MOSI','5':'SENS_MISO','6':'BARO_CS','7':'BARO_INT',
           '8':'GND','9':'GND','10':ANA},None,refofs=(205,120),vlab=True)
    s.add('U23','MARV_Sensors:ADXL375','ADXL375 high-g accelerometer',345,85,
          {'1':ANA,'2':'GND','3':ANA,'4':'GND','5':'GND','6':ANA,'7':'HG_ACC_CS','8':'HG_ACC_INT',
           '9':None,'10':None,'11':'GND','12':'SENS_MISO','13':'SENS_MOSI','14':'SENS_SCK'},
          None,refofs=(330,120),vlab=True)
    for ref,(x,y),val in zip(
        ['C50','C51','C54','C55','C58','C59','C52','C53','C56','C57','C60','C61'],
        [(30,170),(65,170),(160,170),(195,170),(290,170),(325,170),
         (30,198),(65,198),(160,198),(195,198),(290,198),(325,198)],
        ['100n / 16 V X7R, U21 VDD','1u / 10 V X7R, U21 VDD','100n / 16 V X7R, U22 VDD','1u / 10 V X7R, U22 VDD',
         '100n / 16 V X7R, U23 VS','1u / 10 V X7R, U23 VS','100n / 16 V X7R, U21 VDDIO','1u / 10 V X7R, U21 VDDIO',
         '100n / 16 V X7R, U22 VDDIO','1u / 10 V X7R, U22 VDDIO','100n / 16 V X7R, U23 VDD_IO','1u / 10 V X7R, U23 VDD_IO']):
        s.passive(ref,'C',val,x,y,ANA,'GND')
    for ref,(x,y),net in zip(['R48','R50','R51'],[(100,170),(100,198),(130,198)],
                             ['IMU_CS','BARO_CS','HG_ACC_CS']):
        s.passive(ref,'R','10k, %s pull-up'%net,x,y,ANA,net)
    s.note('R48, R50, R51: 10k pull-ups to V3V3_ANA on the three SPI chip selects (IMU_CS, BARO_CS, HG_ACC_CS). R49\n'
           '(the former second IMU chip-select pull-up) is removed along with that net - the ICM-45686 has a single\n'
           'chip select. Same rationale as R35 on FLASH_CS1 (BOARD 3): every sensor is held deselected before the RP2354B\n'
           'drives the pin, so a GPIO left floating through reset, BOOTSEL or a debugger halt cannot open a\n'
           'transaction on the shared SENS_SCK / SENS_MOSI / SENS_MISO bus. They bias to V3V3_ANA, the same rail as\n'
           'every VDDIO pin on this sheet, so there is no pull-up current path into an unpowered I/O supply and no CS\n'
           'pin is pulled above its own VDDIO during rail sequencing.',230,225,1.3)
    s.note('U21 ICM-45686 (TDK InvenSense DS-000577 Rev 1.0, Table 10 "Signal Descriptions" / Figure 4 pin-out, Single\n'
           'Interface SPI mode, Figure 10): AP_CS (pin 12) = IMU_CS, AP_SCLK (13) = SENS_SCK, AP_SDA/AP_SDIO/AP_SDI (14)\n'
           '= SENS_MOSI, AP_SDO/AP_AD0 (1) = SENS_MISO. INT1 (4) = IMU_INT1. INT2/FSYNC/CLKIN (9) = IMU_INT2 - typed\n'
           'bidirectional because FSYNC/CLKIN are host-driven inputs while INT2 is a chip output; only the INT2\n'
           'function is used here. VDD (8) and VDDIO (5) are both on V3V3_ANA; GND (6) is the only ground pin. Pins 2,\n'
           '3, 7, 10 and 11 (RESV) are all left No Connect: Table 10 allows No Connect / VDDIO / GND for every RESV\n'
           'pin, and the Single-Interface SPI typical application schematic (Figure 10) shows all five left unterminated\n'
           '(internal pull enabled by default, per the per-pin notes in Table 10); they are only needed for the AUX1 or\n'
           'I2C-master dual-interface modes, neither of which this board uses. C50 (VDD) and C52 (VDDIO) are the 100 nF\n'
           'X7R of Table 11 "Bill of Materials" (C1/C2 in the datasheet); C51 (VDD) and C53 (VDDIO) add 1 uF on top of\n'
           'them. The datasheet BOM lists 0.1 uF only; this board keeps 100 nF + 1 uF per supply pin for consistency\n'
           'with U22/U23 and common flight-controller practice.',15,225,1.3)
    s.note('U22 BMP581: CSB = BARO_CS, SDI = SENS_MOSI, SDO = SENS_MISO, SCK = SENS_SCK, INT = BARO_INT. VDDIO and VDD on\n'
           'V3V3_ANA, all three VSS pins to GND.\n'
           'U23 ADXL375: CS = HG_ACC_CS, SDA/SDI = SENS_MOSI, SDO = SENS_MISO, SCL/SCLK = SENS_SCK, INT1 = HG_ACC_INT.\n'
           'Per the pin function table, pin 3 (RESERVED) goes to VS and pin 11 (RESERVED) to GND; pin 10 (NC) and the unused\n'
           'INT2 are left open. VS and VDD I/O are both on V3V3_ANA.',15,255,1.3)
    return s

def storage_sheet():
    s=Sheet('storage','BOARD 3 / log flash and microSD',7)
    s.note('Log flash on the shared QSPI bus with GPIO0/QMI CS1n as its chip select, and a latched microSD wired for\n'
           '4-bit PIO (also SPI-compatible). Both on V3V3_SYS with local bulk, per the rail split in DESIGN_SPEC.',15,10,1.6)
    s.add('U24','Memory_Flash:W25Q128JVS','W25Q128JVSIQ, 128 Mbit QSPI NOR',95,75,
          {'1':'FLASH_CS1','2':'QSPI_SD1','3':'QSPI_SD2','4':'GND','5':'QSPI_SD0','6':'QSPI_SCLK','7':'QSPI_SD3','8':V3},
          'Package_SO:SOIC-8_5.3x5.3mm_P1.27mm',refofs=(85,100),vlab=True)
    s.passive('R35','R','10k, FLASH_CS1 pull-up',170,75,V3,'FLASH_CS1')
    s.passive('C62','C','100n / 16 V X7R, U24 VCC',210,75,V3,'GND')
    s.passive('C63','C','1u / 10 V X7R, U24 VCC',250,75,V3,'GND')
    s.add('J11','Connector:Micro_SD_Card_Det2','microSD, Molex 104031-0811 push-push',110,175,
          {'1':'SD_D2','2':'SD_D3','3':'SD_CMD','4':V3,'5':'SD_CLK','6':'GND','7':'SD_D0','8':'SD_D1',
           '9':'SD_DET','10':'GND','SH':'GND'},'MARV_Packages:microSD_HC_Molex_104031-0811',refofs=(88,150))
    grid=[(x,y) for y in (150,185) for x in (215,250,285)]
    for ref,(x,y),net in zip(['R36','R37','R38','R39','R40','R41'],grid,
                             ['SD_CMD','SD_D0','SD_D1','SD_D2','SD_D3','SD_DET']):
        s.passive(ref,'R','10k, %s pull-up'%net,x,y,V3,net)
    s.passive('C64','C','100n / 16 V X7R, at the socket',215,225,V3,'GND')
    s.passive('C65','C','10u / 10 V X7R, at the socket',250,225,V3,'GND',foot='Capacitor_SMD:C_1206_3216Metric')
    s.passive('C66','C','47u / 6.3 V X5R, at the socket',285,225,V3,'GND',foot='Capacitor_SMD:C_1210_3225Metric')
    s.note('U24 shares the dedicated QSPI pads with the RP2354B in-package flash die (datasheet Sec 14.3): CLK = QSPI_SCLK,\n'
           'DI/IO0 = QSPI_SD0, DO/IO1 = QSPI_SD1, WP/IO2 = QSPI_SD2, HOLD/IO3 = QSPI_SD3. Only the chip select differs -\n'
           'FLASH_CS1 comes from GPIO0 (QMI CS1n), pulled up to V3V3_SYS by R35 so the part is deselected before the MCU\n'
           'drives it. QSPI_SS (the internal die) keeps its own strap on the MCU sheet.',15,245,1.3)
    s.note('J11: DET_A to GND and DET_B to SD_DET with a 10k pull-up, so the input reads low with a card inserted. The\n'
           'shield goes to GND. 100 nF + 10 uF + 47 uF sit at the socket (DESIGN_SPEC "Rails": SD transients stay on the\n'
           'buck rail). 10k pull-ups on CMD and DAT0-DAT3 are the SD-standard idle bias and also keep DAT3/CD high for\n'
           '4-bit mode. VDD = V3V3_SYS.',15,268,1.3)
    return s

def actuators_sheet():
    s=Sheet('actuators','BOARD 4 / PWM outputs',8)
    s.note('Eight PWM outputs on a 3-row 2.54 mm block: signal / SERVO_5V / GND. No series resistors - 3.3 V logic straight\n'
           'from the RP2354B, which is what servos and ESCs expect.',15,10,1.6)
    s.add('J12','Connector_Generic:Conn_01x08','PWM signals, row 1',95,70,
          {str(i+1):'PWM%d'%(i+1) for i in range(8)},'Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
    s.add('J13','Connector_Generic:Conn_01x08','SERVO_5V pass-through, row 2',165,70,
          {str(i+1):'5V_IN' for i in range(8)},'Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
    s.add('J14','Connector_Generic:Conn_01x08','GND, row 3',235,70,
          {str(i+1):'GND' for i in range(8)},'Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
    s.note('3.3 V logic; servo/ESC power is the external BEC bus, 3 A limit is the BEC\'s.',15,120,1.6)
    s.note('Row 2 is SERVO_5V = the 5V_IN net, i.e. the J3 input BEFORE U25 (the TPS2121 priority power mux). Servo and ESC\n'
           'current therefore never crosses the board rails, V5_SYS or the mux; in particular it is not counted against the\n'
           'mux ILM current limit (1.49 A, set by R46). It returns through the row 3 ground pins.\n'
           'Nothing on this sheet loads V3V3_SYS or USB_VBUS.',15,140,1.3)
    note='No 3-row generic connector symbol or 2.54 mm 3x08 footprint ships with this KiCad install, so the header is drawn\n'
    note+='as three stacked Conn_01x08 symbols (J12 signal, J13 SERVO_5V, J14 GND) with three 1x08 footprints. Place them on\n'
    note+='2.54 mm centres to form the usual 3x8 servo block; column n is J12 pin n / J13 pin n / J14 pin n.'
    s.note(note,15,165,1.3)
    s.note('PWM MAP\nPWM1 = GPIO2   PWM5 = GPIO10\nPWM2 = GPIO3   PWM6 = GPIO11\nPWM3 = GPIO4   PWM7 = GPIO14\nPWM4 = GPIO5   PWM8 = GPIO15',15,195,1.3)
    return s

def build():
    src=Sheet('power_sources','POWER 1 / 5 V in, USB, priority power mux',2)
    src.note('5 V INPUTS ONLY: BEC/boost 4.75-5.5 V (J3), USB VBUS ~5 V (J4). NO RAW CELL INPUT ON THIS BOARD.',15,15,2)
    # J3 is an XT30 right-angle male. PIN NUMBERING IS NOT THE POLARITY: in every AMASS footprint that
    # ships with KiCad (XT30PW-M/F, XT30U-M, XT60PW-M) pad 1 carries the "-" silkscreen marker and pad 2
    # the "+" marker, so pin 1 = GND and pin 2 = +5 V. Verified in
    # /usr/share/kicad/footprints/Connector_AMASS.pretty/AMASS_XT30PW-M_1x02_P2.50mm_Horizontal.kicad_mod
    # (pad 1 at x=0 next to the "-" text at x=+3; pad 2 at x=-5 next to the "+" text at x=-8).
    # That footprint (and six others - see LIBRARIES.md) is vendored byte-for-byte into
    # MARV_Packages.pretty/ with only its (model ...) node repointed at a project-local STEP, so the
    # project is self-contained for layout; the pads/courtyard are unchanged from the KiCad original.
    src.add('J3','Connector_Generic:Conn_01x02','5 V IN, 4.75-5.5 V, XT30 (BEC/BMS/boost module)',35,95,{'1':'GND','2':'5V_IN'},'MARV_Packages:AMASS_XT30PW-M_1x02_P2.50mm_Horizontal')
    src.add('D23','Diode:SMAJ5.0A','SMAJ5.0A, 5.0 V standoff uni-directional TVS',40,50,{'1':'5V_IN','2':'GND'},'Diode_SMD:D_SMA')
    src.passive('C16','C','100n / 16 V X7R, J3 HF bypass',30,140,'5V_IN','GND')
    src.passive('C67','C','4.7u / 10 V X7R, J3 bulk',65,140,'5V_IN','GND')
    src.passive('C68','C','4.7u / 10 V X7R, J3 bulk',100,140,'5V_IN','GND')
    src.passive('C69','C','100u / 10 V polymer, J3 bulk',135,140,'5V_IN','GND','Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D')

    # U25 TPS2121 priority power mux: IN1 = 5V_IN (priority), IN2 = USB_VBUS, OUT = V5_SYS.
    src.passive('R42','R','32.4k / 1%, PR1 top (5V_IN)',185,50,'5V_IN','U25_PR1')
    src.passive('R43','R','10k / 1%, PR1 bottom',185,85,'U25_PR1','GND')
    src.passive('R44','R','45.3k / 1%, OV1 top (5V_IN)',220,50,'5V_IN','U25_OV1')
    src.passive('R45','R','10k / 1%, OV1 bottom',220,85,'U25_OV1','GND')
    src.add('U25','MARV_Power:TPS2121RUX','TPS2121RUXR',270,90,
            {'7':'5V_IN','2':'USB_VBUS','6':'U25_PR1','5':'U25_OV1','4':'GND','3':'GND',
             '1':'V5_SYS','8':'V5_SYS','9':'PWR_SRC_ST','10':'U25_ILM','11':'U25_SS','12':'GND'},
            'MARV_Packages:Texas_VQFN-HR-12_2x2.5mm_P0.5mm')
    src.passive('C71','C','100n / 16 V X7R, IN1 bypass at U25',315,45,'5V_IN','GND')
    src.passive('C72','C','100n / 16 V X7R, IN2 bypass at U25',355,45,'USB_VBUS','GND')
    src.passive('R46','R','80.6k / 1%, ILM -> 1.49 A',315,85,'U25_ILM','GND')
    src.passive('R47','R','10k / 1%, ST pull-up (open drain)',355,85,'V3V3_SYS','PWR_SRC_ST')
    src.passive('C70','C','100n / 16 V X7R, SS soft-start',315,125,'U25_SS','GND')

    src.add('J4','Connector:USB_C_Receptacle_USB2.0_16P','USB_C_PROGRAM_POWER',55,215,{'A1':'GND','A4':'USB_VBUS','A5':'USB_CC1','A6':'USB_DP','A7':'USB_DM','A8':None,'A9':'USB_VBUS','A12':'GND','B1':'GND','B4':'USB_VBUS','B5':'USB_CC2','B6':'USB_DP','B7':'USB_DM','B8':None,'B9':'USB_VBUS','B12':'GND','S1':'GND'},'MARV_Packages:USB_C_Receptacle_HRO_TYPE-C-31-M-12')
    src.passive('R4','R','5.1k / 1%',120,195,'USB_CC1','GND')
    src.passive('R5','R','5.1k / 1%',120,240,'USB_CC2','GND')
    src.passive('C7','C','1u / 10 V',25,275,'USB_VBUS','GND')

    src.note('U25 TPS2121 PRIORITY POWER MUX (TI SLVSEA3F). IN1 = 5V_IN is the priority source, IN2 = USB_VBUS the fallback; OUT = V5_SYS.\n'
             'Reverse-current blocking is always on for BOTH channels (Sec 9.3.6, IRCB 0.2/1/2 A, tRCB 10 us, VRCB 0/25/50 mV), so neither input\n'
             'can be back-fed from V5_SYS or from the other input. RON 56 mOhm typ / 100 mOhm max over temperature (Sec 7.5, VINx >= 5 V).\n'
             'PR1 (Sec 10.2.4.1 Eq.5, VPR1 = VIN1 x Rb/(Rt+Rb) compared with VREF): R42 32.4k / R43 10k -> IN1 released when 5V_IN falls to\n'
             '1.04 V / 0.23585 = 4.410 V typ and re-selected at 1.06 V / 0.23585 = 4.494 V typ (4.20-4.62 V / 4.28-4.66 V over the VREF spec).\n'
             'The divider is centred on the RISING edge, not the falling one: the binding corner is a 5V_IN at its 4.75 V minimum meeting a\n'
             'VREF at its 1.10 V maximum, and 4.664 V worst-case rising keeps IN1 selected everywhere inside the declared 4.75-5.5 V window.\n'
             'OV1 (Sec 9.3.5 / 10.2.4.2 Eq.6, same divider form): R44 45.3k / R45 10k -> IN1 rejected at 1.06 V / 0.180832 = 5.862 V typ\n'
             '(5.585-6.083 V over the VREF spec, so it can never trip inside the declared 4.75-5.5 V input window). OV2 is tied to GND: the USB\n'
             'channel has no overvoltage cut-off ("Connect to GND if not required", Sec 6). CP2 is tied to GND, which selects the internal-VREF\n'
             'priority scheme of Table 9-3 - that is the mode PR1-vs-VREF describes, and it costs the TPS2121 fast-switchover path: the applicable\n'
             'spec is tSW = 100 us typ (Sec 7.5), not the 5 us tFSW that needs CP2 >= VREF.\n'
             'ILM (Sec 9.3.2 Eq.2, ILM = 65.2 / RILM^0.861 with RILM in kOhm, valid 18-100 kOhm): R46 80.6k -> 1.49 A typ; the datasheet\n'
             'characterises RILM = 80k as 1.0 / 1.5 / 2.0 A min/typ/max. Fast-trip OCP is 2.4 x ILM (Sec 9.3.3).\n'
             'SS (Sec 9.3.1 / Table 9-1): C70 100 nF -> 780 V/s at 5 V, so the ~240 uF on V5_SYS draws ~190 mA of inrush and OUT ramps in ~6.4 ms.\n'
             'ST (Sec 6, Sec 10.2.3) is an open-drain status output: HIGH when IN1 (or neither input) drives OUT, LOW when IN2 does. R47 10k to\n'
             'V3V3_SYS is inside the RST = 6-20 kOhm recommended operating range of Sec 7.3; PWR_SRC_ST lands on RP2354B GPIO39 (pin 48).\n'
             'Sec 11 gives no numeric minimum COUT, only "increase the capacitance on OUT to avoid output voltage drop"; C19 220 uF + C8/C9\n'
             '2 x 10 uF on POWER 2 already exceed the 100-200 uF the datasheet design examples use, so no extra output capacitor is added here.',150,150,1.3)
    src.note('J3 INPUT NETWORK: C16 100 nF + C67/C68 2 x 4.7 uF X7R + C69 100 uF polymer, and D23 SMAJ5.0A (DO-214AC/SMA) clamping 5V_IN to GND.\n'
             'D23 is a UNI-directional TVS: its KiCad symbol inherits the generic A1/A2 pin names from the SM6T family, but the graphic and the\n'
             'DO-214AC band both put the CATHODE on pin 1, so pin 1 goes to 5V_IN and pin 2 (anode) to GND. 5.0 V standoff / 6.4 V VBR min\n'
             'sits above the 5.5 V input maximum and below the TPS2121 5.585 V worst-case OV1 trip, so the clamp and the mux do not fight.\n'
             'J3 is XT30PW-M: pad 1 is the "-" terminal and pad 2 the "+" terminal in the KiCad footprint - see the comment in tools/build_power.py.',150,215,1.3)
    src.note('USB_VBUS feeds U25 IN2 directly; no inrush/current limiting on this sheet.\nData ESD protection is on POWER 2. No servo rail connection.',150,245)

    out=Sheet('power_3v3','POWER 2 / 3.3 V system buck and analog LDO',3)
    out.note('AVIONICS ONLY: 300 mA continuous / 500 mA short peak, provisional. NO SERVO POWER.',15,15,2)
    out.add('U7','Regulator_Switching:TPS62913','TPS62913RPUR',95,70,{'1':'V5_SYS','2':'U7_SW','3':'U7_VO','4':'GND','5':'PWR_GOOD','6':'V5_SYS','7':'GND','8':'U7_SS','9':'U7_FB','10':'U7_SCONF'},
            'MARV_Packages:Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm')
    out.passive('L2','L','2.2u / Isat 7 A, DCR 13.5 mOhm (Coilcraft XGL4030-222MEC or equiv)',175,50,'U7_SW','U7_VO',foot='MARV_Packages:L_Coilcraft_XxL4030')
    out.passive('FB1','FerriteBead','8.5 ohm @100MHz / 4 mOhm DCR / 5 A (MuRata BLE18PS080SN1 or equiv)',175,90,'U7_VO','V3V3_SYS',foot='Inductor_SMD:L_0603_1608Metric')
    for ref,x in [('C8',25),('C9',25)]:
        out.passive(ref,'C','10u / 10 V X7S',x,55 if ref=='C8' else 105,'V5_SYS','GND')
    out.passive('C17','C','2.2n / 50 V X7R, VIN-PGND HF bypass',55,60,'V5_SYS','GND',foot='Capacitor_SMD:C_0402_1005Metric')
    out.passive('C19','C','220u / 10 V polymer, ESR ~40 mOhm',25,155,'V5_SYS','GND','Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D')
    for ref,x in [('C10',245),('C11',310),('C12',375)]:
        out.passive(ref,'C','22u / 10 V X7S, 1st-stage COUT',x,50,'U7_VO','GND',foot='Capacitor_SMD:C_0805_2012Metric')
    for ref,x in [('C23',245),('C24',310)]:
        out.passive(ref,'C','22u / 10 V X7S, 2nd-stage Cf (post-bead)',x,75,'V3V3_SYS','GND',foot='Capacitor_SMD:C_0805_2012Metric')
    out.passive('C13','C','470n / 16 V, NR/SS soft-start + noise filter (5 ms)',95,125,'U7_SS','GND')
    out.passive('R7','R','15.8k / 0.1%',245,105,'V3V3_SYS','U7_FB')
    out.passive('R8','R','4.99k / 0.1%',310,105,'U7_FB','GND')
    out.passive('R9','R','6.04k / 1%, S-CONF: 2.2 MHz + triangle SSM, discharge off, no sync',175,120,'U7_SCONF','GND')
    out.passive('R10','R','100k',245,155,'V3V3_SYS','PWR_GOOD')
    out.note('V3V3_SYS feedback (TPS62913 datasheet Sec 8.2.2.2.6, Eq.8): VOUT = VFB x (1 + R1/R2); VFB = 0.8 V typ, 0.792-0.812 V spec (Sec 6.5).\nR2 = 4.99 kOhm (<=5 kOhm per datasheet noise guidance). R1 = R2 x (VOUT/VFB - 1) = 4.99k x (3.3/0.8 - 1) = 4.99k x 3.125 = 15.59 kOhm -> nearest 1% E96 = 15.8 kOhm.\nActual VOUT = 0.8 V x (1 + 15.8k/4.99k) = 3.33 V nominal (3.30-3.38 V across VFB tolerance).',15,180,1.3)
    out.note('S-CONF = 6.04 kOhm to GND (Table 7-1): 2.2 MHz switching, triangle spread-spectrum ON, output discharge OFF, no external sync.\n2.2 MHz + 2.2uH matches the VIN=5V/VOUT<=3.3V design table (Table 8-2). TPS62913 runs fixed-frequency PWM at all loads, no light-load skip mode (Sec 7.4.1) -- forced PWM is inherent; there is no separate MODE pin on this device.\nVO (pin 3) senses the node between L1 and the ferrite bead (device internal loop); the FB divider senses V3V3_SYS after the bead for low-noise remote regulation (Sec 7.1 / 8.2.2.2.4).',15,215,1.3)
    out.add('U12','Regulator_Linear:TPS7A20xxxDBV','TPS7A2033PDBVR',95,200,{'1':'V5_SYS','2':'GND','3':'PWR_GOOD','4':None,'5':'V3V3_ANA'})
    out.passive('C25','C','1u / 10 V X7R, LDO input',55,195,'V5_SYS','GND')
    out.passive('C26','C','1u / 10 V X7R, LDO output, ESR <=100 mOhm',150,195,'V3V3_ANA','GND')
    out.note('3V3_ANA feeds ICM-45686, BMP581, ADXL375 and the RP2354B ADC_AVDD pin (100 nF at each pin on the MCU sheet); VREG_AVDD is filtered\n'
             'from V3V3_SYS instead, so the analog rail carries no core-regulator current. U12 EN (pin 3) is on PWR_GOOD rather than V5_SYS:\n'
             'the analog rail therefore starts only once the TPS62913 declares V3V3_SYS in regulation, and drops with it, which removes the\n'
             'window where the sensors were biased from an unregulated V5_SYS while the MCU was still held in reset.',15,240,1.3)
    out.add('U8','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',245,220,{'1':'USB_DP','2':'GND','3':'USB_DM','4':'USB_DM_MCU','5':'USB_VBUS','6':'USB_DP_MCU'})

    periph=Sheet('power_periph','POWER 3 / peripheral ports',4)
    periph.note('PIXHAWK DS-009 PIN ORDER. UART ports (J6, J7): 1 VCC, 2 TX, 3 RX, 4 GND. I2C port (J9): 1 VCC, 2 SCL, 3 SDA, 4 GND.\n'
                'Pin 2 of a UART port is the BOARD TX, i.e. the RP2354B UART TX output, which lands on the module RX input - that is the\n'
                'GPS_RX / ELRS_RX net, because a port label is named for the peripheral pin it belongs to (see the MCU sheet). Pin 3 is the\n'
                'board RX, fed by the module TX: GPS_TX / ELRS_TX.',15,15,1.4)
    periph.passive('C20','C','10u / 10 V X7R',25,55,'V5_SYS','GND')
    periph.add('J6','Connector_Generic:Conn_01x04','UART_GPS (DS-009: VCC/TX/RX/GND)',95,55,{'1':'V5_SYS','2':'GPS_RX','3':'GPS_TX','4':'GND'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C21','C','10u / 10 V X7R',25,105,'V5_SYS','GND')
    periph.add('J7','Connector_Generic:Conn_01x04','UART_ELRS (DS-009: VCC/TX/RX/GND)',95,105,{'1':'V5_SYS','2':'ELRS_RX','3':'ELRS_TX','4':'GND'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C22','C','10u / 10 V X7R',25,155,'V3V3_SYS','GND')
    periph.add('J9','Connector_Generic:Conn_01x04','I2C_MAG (DS-009: VCC/SCL/SDA/GND)',95,155,{'1':'V3V3_SYS','2':'MAG_SCL','3':'MAG_SDA','4':'GND'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.note('RAILS: J6 and J7 VCC are on V5_SYS - GNSS and ELRS modules are 5 V-powered with their own on-module regulators, and their\n'
                'C20 / C21 10 uF local bulk moved to V5_SYS with them. Their SIGNAL pins stay 3.3 V CMOS straight from the RP2354B, which is\n'
                'what both module families expect. J9 VCC stays on V3V3_SYS: the magnetometer bus is 3.3 V and its pull-ups (R25/R26 on the\n'
                'MCU sheet) bias to V3V3_SYS, so a 5 V port pin there would fight them. J9 pin 2 = MAG_SCL, pin 3 = MAG_SDA.',15,200,1.4)


    mcu=mcu_sheet(); sens=sensors_sheet(); sto=storage_sheet(); act=actuators_sheet()
    sheets=[src,out,periph,mcu,sens,sto,act]
    for sheet,net,x,y,num in [(src,'GND',395,55,1),(src,'5V_IN',395,80,2),(src,'USB_VBUS',395,105,3),(src,'V5_SYS',395,130,4),
                              (mcu,'V3V3_SYS',155,262,5),(mcu,'VREG_AVDD',185,262,6),(mcu,'DVDD',215,262,7)]:
        sheet.add('#FLG'+str(num),'power:PWR_FLAG','PWR_FLAG',x,y,{'1':net})
    root=['(kicad_sch (version 20250114) (generator "eeschema") (uuid '+uid('power-root')+') (paper "A3") (title_block (title "MARV integrated power - preliminary") (date "2026-09-14") (rev "P0 - NOT FOR FAB")) (lib_symbols)']
    root.append('(text '+q('Integrated draft: power chain (sheets 2-4) and board stage (sheets 5-8). See DESIGN_SPEC.md.\n'
                            'Rails: V5_SYS from the 5 V inputs, V3V3_SYS from the TPS62913 buck, V3V3_ANA from the TPS7A20 LDO.\n'
                            'No PCB placement or routing has been performed.')+' (at 20 20 0) (effects (font (size 1.8 1.8)) (justify left top)) (uuid '+uid('root-note')+'))')
    for i,s in enumerate(sheets):
        x,y=20+200*(i//4),60+38*(i%4)
        root.append(f'(sheet (at {x} {y}) (size 180 25) (fields_autoplaced yes) (stroke (width 0.1524) (type default)) (fill (color 0 0 0 0.0000)) (uuid {s.id}) (property "Sheetname" {q(s.title)} (at {x} {y-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" "{s.name}.kicad_sch" (at {x} {y+26} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "MARV-V2" (path "/{uid("power-root")}" (page "{s.page}")))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n')
    files={'MARV-V2.kicad_sch':'\n'.join(root).replace('(fields_autoplaced yes)', '(fields_autoplaced)')}
    files.update({s.name+'.kicad_sch':s.render() for s in sheets})
    files['power_bom.csv']='Reference,Value,Footprint,Sheet\n'+'\n'.join(','.join(q(v) for v in row) for s in sheets for row in s.bom if not row[0].startswith('#'))+'\n'
    backup=ROOT/'backups/MARV-V2.before-power.kicad_sch'
    if not backup.exists():
        files['backups/MARV-V2.before-power.kicad_sch']=(ROOT/'MARV-V2.kicad_sch').read_text()
    custom=[]
    for sheet in sheets:
        for lid,s in sheet.libs.items():
            if lid.startswith('MARV_Power:') and not any(unquote(c[1])==lid.split(':')[1] for c in custom):
                c=copy.deepcopy(s);c[1]=q(lid.split(':')[1]);custom.append(c)
    files['MARV_Power.kicad_sym']=dump(['kicad_symbol_lib',['version','20250114'],['generator','kicad_symbol_editor']]+custom)+'\n'
    table=(ROOT/'sym-lib-table').read_text()
    if 'MARV_Power' not in table:
        files['sym-lib-table']=table.rstrip()[:-1]+'\n  (lib (name \"MARV_Power\") (type \"KiCad\") (uri \"${KIPRJMOD}/MARV_Power.kicad_sym\") (options \"\") (descr \"Power symbols; OR output electrically passive\"))\n)\n'
    patch_files(files)

if __name__=='__main__':
    if '--inspect' in sys.argv:
        for libid in ['Regulator_Switching:LMR36510ADDA','Regulator_Switching:TPS62913','Regulator_Linear:TPS7A20xxxDBV','Power_Management:LM66100DCK','Connector:USB_C_Receptacle_USB2.0_16P','Power_Protection:USBLC6-2SC6','Transistor_FET:2N7002']:
            print(libid,[(unquote(first(p,'number')[1]),unquote(first(p,'name')[1]),p[1]) for p in pins(symbol(libid))])
    else:
        build()
