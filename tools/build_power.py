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

# Passive package policy.  The board is a single-sided square that has to stay
# at or under 50 mm (DESIGN_SPEC "Envelope"), so every passive is now the
# SMALLEST package its rating allows rather than the smallest hand-solderable
# one; all of the packages below are JLCPCB assembly parts (1 % for R,
# X5R/X7R for C).  Package is derived from the value string, which always
# starts "<capacitance> / <voltage> V":
#
#   R   any value ................................. 0201
#   C   <= 4.7 uF, <= 16 V ........................ 0402
#   C   > 4.7 uF .. 22 uF, <= 16 V ................ 0603
#
# REWORK: 0201 resistors (0.6 x 0.3 mm) and 22 uF 0603 ceramics are machine
# placement only - JLC assembles them, a bench iron does not rework them.
# That is the deliberate trade for the 50 mm single-sided envelope.
# A capacitor rated above 16 V (anything on VBAT, the bootstrap cap, the
# crystal load caps) or larger than 22 uF must pass an explicit foot= at the
# call site and keeps the larger body its voltage / DC-bias derating needs:
# C17/C46/C47 (50 V, 0402), C74/C75 (50 V, 0402), C73 (10u/50 V, 0805),
# C76/C77/C80 (22u/25 V, 0805), C66 (47u/6.3 V, 0805), C19 (100u/6.3 V
# polymer, EIA-3528 B case).  The two exceptions are enforced below by raising rather than
# guessing.
CAP_PACKAGE=[(4.7e-6,'C_0402_1005Metric'),(22e-6,'C_0603_1608Metric')]
SI_MULT={'p':1e-12,'n':1e-9,'u':1e-6}
OTHER_PACKAGE={'L':'Inductor_SMD:L_6.3x6.3_H3','Fuse':'Fuse:Fuse_1206_3216Metric',
               'D_Schottky':'Diode_SMD:D_SMA','D_TVS':'Diode_SMD:D_SMB'}

def passive_footprint(kind,value):
    if kind=='R':
        return 'Resistor_SMD:R_0201_0603Metric'
    if kind!='C':
        return OTHER_PACKAGE[kind]
    # a DNP part carries its fit state in the Value field (see Sheet.add);
    # the package is still chosen from the capacitance behind that prefix,
    # because an unpopulated part still needs a correct land pattern.
    m=re.match(r'\s*(?:DNP:\s*)?([\d.]+)\s*([pnu])\s*/\s*([\d.]+)\s*V',value)
    if not m:
        raise ValueError((value,'capacitor value must start "<C> / <V> V"'))
    farads=float(m.group(1))*SI_MULT[m.group(2)]
    if float(m.group(3))>16:
        raise ValueError((value,'capacitor rated > 16 V needs an explicit footprint'))
    for limit,pkg in CAP_PACKAGE:
        if farads<=limit*1.001:          # tolerance: 100*1e-9 > 100e-9 in binary floats
            return 'Capacitor_SMD:'+pkg
    raise ValueError((value,'capacitor above 22 uF needs an explicit footprint'))

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
    def add(self,ref,libid,value,x,y,nets,foot=None,refofs=None,vlab=False,dnp=False):
        """dnp=True marks the symbol DO NOT POPULATE and excludes it from the
        BOM: KiCad's own `(dnp yes)` / `(in_bom no)` symbol attributes, which
        ERC, the netlist export, the BOM and pcbnew all read.  The net list is
        unchanged - a DNP part still owns its nets and its land pattern, it is
        simply not fitted.  See the U24 flash-socket note on BOARD 3."""
        x,y=round(round(x/1.27)*1.27,5),round(round(y/1.27)*1.27,5)
        sym=symbol(libid)
        if libid not in self.libs:
            embedded=copy.deepcopy(sym); embedded[1]=q(libid)
            self.libs[libid]=embedded
        props={unquote(p[1]):unquote(p[2]) for p in children(sym,'property')}
        fp=foot if foot is not None else props.get('Footprint','')
        attrs='(in_bom no) (on_board yes) (dnp yes)' if dnp else '(in_bom yes) (on_board yes) (dnp no)'
        inst=f'(symbol (lib_id {q(libid)}) (at {x} {y} 0) (unit 1) {attrs} (uuid {uid(ref)})'
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
        self.bom.append((ref,value,fp,self.name,'DNP' if dnp else 'populated'))
    def passive(self,ref,kind,value,x,y,a,b,foot=None,dnp=False):
        if foot is None:
            foot=passive_footprint(kind,value)
        self.add(ref,'Device:'+kind,value,x,y,{'1':a,'2':b},foot,dnp=dnp)
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
 ('78','GPIO1',None,'unexposed spare - no connect'),
 ('79','GPIO2','PWM1','PWM1 A'),
 ('80','GPIO3','PWM2','PWM1 B'),
 ('1','GPIO4','PWM3','PWM2 A'),
 ('2','GPIO5','PWM4','PWM2 B'),
 ('3','GPIO6','MAG_SDA','I2C1 SDA'),
 ('4','GPIO7','MAG_SCL','I2C1 SCL'),
 ('6','GPIO8','ELRS_RX','UART1 TX -> radio RX'),
 ('7','GPIO9','ELRS_TX','UART1 RX <- radio TX'),
 ('8','GPIO10','PWM5','PWM5 A -> J6 row 7 (S5)'),
 ('9','GPIO11','PWM6','PWM5 B -> J6 row 8 (S6)'),
 ('11','GPIO12','GPS_RX','UART0 TX -> GPS RX'),
 ('12','GPIO13','GPS_TX','UART0 RX <- GPS TX'),
 ('13','GPIO14','PWM7','PWM7 A -> J6 row 9 (S7)'),
 ('14','GPIO15','PWM8','PWM7 B -> J6 row 10 (S8)'),
 ('16','GPIO16','SENS_MISO','SPI0 RX'),
 ('17','GPIO17','HG_ACC_CS','ADXL375 CS'),
 ('18','GPIO18','SENS_SCK','SPI0 SCK'),
 ('19','GPIO19','SENS_MOSI','SPI0 TX'),
 ('20','GPIO20','IMU_CS','ICM-45686 AP_CS'),
 ('21','GPIO21',None,'unexposed spare - no connect'),
 ('22','GPIO22','BARO_CS','BMP581 CSB'),
 ('23','GPIO23','IMU_INT1','ICM-45686 INT1'),
 ('25','GPIO24','IMU_INT2','ICM-45686 INT2/FSYNC/CLKIN'),
 ('26','GPIO25','BARO_INT','BMP581 INT'),
 ('27','GPIO26','LED_DATA','WS2812C-2020 data, 100 R series (R55)'),
 ('28','GPIO27',None,'unexposed spare - no connect'),
 ('36','GPIO28',None,'unexposed spare - no connect'),
 ('37','GPIO29','HG_ACC_INT','ADXL375 INT1'),
 ('38','GPIO30','ESC_TELEM_RX','ESC KISS telemetry in (PIO UART RX), 1k series R54'),
 ('39','GPIO31',None,'unexposed spare - no connect'),
 ('40','GPIO32','SD_CLK','microSD CLK (PIO)'),
 ('42','GPIO33','SD_CMD','microSD CMD'),
 ('43','GPIO34','SD_D0','microSD DAT0'),
 ('44','GPIO35','SD_D1','microSD DAT1'),
 ('45','GPIO36','SD_D2','microSD DAT2'),
 ('46','GPIO37','SD_D3','microSD DAT3'),
 ('47','GPIO38','SD_DET','microSD card detect'),
 ('48','GPIO39','PWR_SRC_ST','U25 TPS2121 ST, open drain'),
 ('49','GPIO40','VBAT_SENSE','ADC0, VBAT 100k/10k divider, 36.3 V FS'),
 ('52','GPIO41','VBUS_SENSE','ADC1, USB_VBUS 10k/15k divider'),
 ('53','GPIO42','CURR_SENSE','ADC2, ESC current sense, 1k + 100n'),
 ('54','GPIO43',None,'ADC3, unexposed spare - no connect'),
 ('55','GPIO44','IO_GPIO44','ADC4 -> J6 row 11 (A44)'),
 ('56','GPIO45','IO_GPIO45','ADC5 -> J6 row 12 (A45)'),
 ('57','GPIO46','IO_GPIO46','ADC6 -> J6 row 13 (A46)'),
 ('58','GPIO47','IO_GPIO47','ADC7 -> J6 row 14 (A47)'),
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
    s.passive('C39','C','4.7u / 10 V X5R 0402, VREG_VIN',*left[9],V3,'GND')
    s.passive('C40','C','100n / 16 V X7R, ADC_AVDD',*left[10],ANA,'GND')
    s.passive('R20','R','33 / 1%, VREG_AVDD filter',*left[11],V3,'VREG_AVDD')
    s.passive('C41','C','4.7u / 10 V X5R 0402, VREG_AVDD',*left[12],'VREG_AVDD','GND')
    s.passive('L20','L','3.3u, 0806 AOTA-B201610S3R3',*left[13],'VREG_LX','DVDD',foot='Inductor_SMD:L_Murata_DFE201610P')
    s.passive('C42','C','100n / 16 V X7R, DVDD pin 10',*left[14],'DVDD','GND')
    s.passive('C43','C','100n / 16 V X7R, DVDD pin 32',*left[15],'DVDD','GND')
    s.passive('C44','C','100n / 16 V X7R, DVDD pin 51',*left[16],'DVDD','GND')
    s.passive('C45','C','4.7u / 10 V X5R 0402, DVDD bulk',*left[17],'DVDD','GND')
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
           'and land on MCU UART RX pins, while GPS_RX / ELRS_RX are module inputs fed by the MCU UART TX pins. On the IO\n'
           'array (POWER 3) the UART rows are therefore 1 GPS_RX (silk T0) / 2 GPS_TX (R0) / 3 ELRS_RX (T1) / 4 ELRS_TX (R1),\n'
           'rows 5/6 are MAG_SDA / MAG_SCL, rows 7-10 the PWM5-8 servo signals and rows 11-14 the four exposed spares.\n'
           'The array is three stacked 1x14 rows: J6 SIGNAL, J7 POWER, J8 GND. All array SIGNAL pins are 3.3 V CMOS.\n'
           'GPIO39 (pin 48) is no longer spare: it reads PWR_SRC_ST, the open-drain ST output of U25 (TPS2121), which is\n'
           'high while 5V_IN (IN1) powers V5_SYS and low while USB VBUS (IN2) does.',155,233,1.3)
    rows=['%-7s %3s  %-12s %s'%(g,p_,n or '(no connect)',f) for p_,g,n,f in MCU_GPIO]
    s.note('GPIO MAP (pin = QFN-80 pin)\n'+'\n'.join(rows[:24]),250,14,1.3)
    s.note('\n'+'\n'.join(rows[24:]),338,14,1.3)

    s.add('J10','Connector_Generic:Conn_01x03','DBG pads (SWCLK SWDIO GND)',250,92,
          {'1':'SWCLK','2':'SWDIO','3':'GND'},'MARV_Packages:PadRow_1x03_P2.00mm')
    s.note('J10 is a 3-pad SWD landing (SWCLK / SWDIO / GND), not a 10-pin Cortex header: solder pads are kept for the two\n'
           'ports that mate with something fixed - the ESC row J3 and this one (DESIGN_SPEC "Connection philosophy").\n'
           'The debugger reference 3V3 and the debugger-driven reset line\n'
           'of the old 2x05 header are both gone - power the board from VBAT or USB while debugging, and use SW1 (RUN via\n'
           'PWR_GOOD) for reset. RUN is still held by the TPS62913 power-good pull-up on POWER 2, so the MCU cannot run\n'
           'before V3V3_SYS is in regulation.',180,104,1.3)

    # Ten GPIOs have no on-board function.  FOUR of them (GPIO44-47 = ADC4-ADC7) are exposed on the IO
    # array (POWER 3), rows 11-14 of the J6 signal column.  The other SIX (GPIO1, 21, 27, 28, 31, 43)
    # are NOT exposed: the array is 14 rows and the six ports/functions above it use the rest, so those
    # pins carry an explicit KiCad no-connect flag here instead of floating.  Exposing one of them is a
    # documented change (PINOUT.md Rule 5), not a wiring detail.
    s.note('SPARE IO. EXPOSED (IO array J6 signal column, POWER 3): GPIO44 row 11 (A44) | GPIO45 row 12 (A45) |\n'
           'GPIO46 row 13 (A46) | GPIO47 row 14 (A47). All four are ADC4-ADC7, which is why the silk labels are\n'
           'A44-A47 rather than IOnn; each sits next to a V3V3_SYS pin (J7) and a GND pin (J8) in the same row.\n'
           'UNEXPOSED, NO-CONNECT: GPIO1, GPIO21, GPIO27, GPIO28, GPIO31, GPIO43 carry a no-connect flag on this\n'
           'sheet - the 14-row array has no room for them once GPS/ELRS/I2C1/PWM5-8 and the four ADC spares are\n'
           'placed. They are left unconnected deliberately; exposing one means editing PINOUT.md, this generator\n'
           'and tools/check_power_netlist.py together. GPIO budget: 38 on board functions and ports, 4 spare on\n'
           'the array, 6 unconnected; none floats without a no-connect flag.',300,92,1.3)

    right=[(250+35*c,140+28*r) for r in range(3) for c in range(4)]
    s.passive('R27','R','100k / 1%, VBAT top',*right[0],'VBAT','VBAT_SENSE')
    s.passive('R28','R','10k / 1%, VBAT bottom',*right[1],'VBAT_SENSE','GND')
    s.passive('C48','C','100n / 16 V X7R, ADC0',*right[2],'VBAT_SENSE','GND')
    s.passive('R29','R','10k / 1%, VBUS top',*right[3],'USB_VBUS','VBUS_SENSE')
    s.passive('R30','R','15k / 1%, VBUS bottom',*right[4],'VBUS_SENSE','GND')
    s.passive('C49','C','100n / 16 V X7R, ADC1',*right[5],'VBUS_SENSE','GND')
    s.passive('R53','R','1k / 1%, CURR series',*right[6],'CURR_SENSE_RAW','CURR_SENSE')
    s.passive('C78','C','100n / 16 V X7R, ADC2 filter',*right[7],'CURR_SENSE','GND')
    s.passive('R54','R','1k, ESC telemetry series',*right[8],'ESC_TELEM','ESC_TELEM_RX')
    s.passive('R55','R','100 / 1%, WS2812 data series',*right[9],'LED_DATA','LED_DIN')
    s.passive('C79','C','100n / 16 V X7R, D20 VDD',*right[10],'V5_SYS','GND')
    s.add('D20','LED:WS2812B-2020','WS2812C-2020 RGB',375,196,
          {'1':None,'2':'GND','3':'LED_DIN','4':'V5_SYS'},'MARV_Packages:LED_WS2812B-2020_PLCC4_2.0x2.0mm')
    # MECHANICAL GROUP: four Mechanical:MountingHole symbols, no pins and no nets - they exist so the
    # 30.5 x 30.5 mm grommet pattern of DESIGN_SPEC "Physical design" lands in the netlist and therefore in
    # the PCB, and so tools/audit_footprints.py checks the footprint file resolves.
    for i,ref in enumerate(['H1','H2','H3','H4']):
        s.add(ref,'Mechanical:MountingHole','M3 grommet hole, 4.0 mm NPTH',170+25*i,258,{},
              'MARV_Packages:MountingHole_4.0mm_Grommet',refofs=(165+25*i,264))
    s.note('MECHANICAL: H1-H4 are the four 4.0 mm NPTH grommet\n'
           'holes on the standard 30.5 x 30.5 mm pattern, centred\n'
           'on the board, each with a 5.0 mm copper keepout and an\n'
           '8.0 mm top-side courtyard for the grommet flange. No\n'
           'pins, no nets. See DESIGN_SPEC "Physical design".',170,270,1.3)
    s.note('TELEMETRY AND ANALOG INPUTS (100 nF at each ADC pin).\n'
           'VBAT_SENSE: R27/R28 100k/10k scale VBAT by 1/11, so the 3.3 V ADC full scale is 36.3 V. A 6S pack at its\n'
           '25.2 V maximum reads 2.29 V and a 2S pack at 6.0 V reads 0.55 V, so the whole 2-6S window is on-scale with\n'
           'headroom; the divider draws 229 uA at 25.2 V. The old 5V_IN divider is gone with the 5 V input itself.\n'
           'CURR_SENSE: the ESC current-sense output (J3 pin 1, 12.75 mV/A, 0-3.3 V) through R53 1k into C78 100 nF at\n'
           'the pin - a 100 us RC anti-alias/ESD network, well under the RP2350 ADC source-impedance guidance.\n'
           'ESC_TELEM: the ESC KISS telemetry output (J3 pin 2, 3.3 V, 115200 baud, one-wire from the ESC) through R54\n'
           '1k into GPIO30, read by a PIO UART. The resistor is series protection only, not a level shifter: the ESC pad\n'
           'row is 3.3 V CMOS on both the telemetry and the four motor lines.\n'
           'VBUS_SENSE keeps 10k/15k on GPIO41.\n'
           'D20 WS2812C-2020: VDD on V5_SYS with C79 100 nF, DIN from GPIO26 through R55 100 R, DOUT no-connect (single\n'
           'pixel). Its DIN VIH minimum is 2.7 V (datasheet Electrical Characteristics), which 3.3 V CMOS clears - that\n'
           'is why the C variant is used rather than a 5050 WS2812B, whose VIH is 0.7 x VDD = 3.5 V.\n'
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
        ['100n / 16 V X7R, U21 VDD','1u / 10 V X7R 0402, U21 VDD','100n / 16 V X7R, U22 VDD','1u / 10 V X7R 0402, U22 VDD',
         '100n / 16 V X7R, U23 VS','1u / 10 V X7R 0402, U23 VS','100n / 16 V X7R, U21 VDDIO','1u / 10 V X7R 0402, U21 VDDIO',
         '100n / 16 V X7R, U22 VDDIO','1u / 10 V X7R 0402, U22 VDDIO','100n / 16 V X7R, U23 VDD_IO','1u / 10 V X7R 0402, U23 VDD_IO']):
        s.passive(ref,'C',val,x,y,ANA,'GND')
    for ref,(x,y),net in zip(['R48','R50','R51'],[(100,170),(100,198),(130,198)],
                             ['IMU_CS','BARO_CS','HG_ACC_CS']):
        s.passive(ref,'R','10k, %s pull-up'%net,x,y,ANA,net)
    # TEST POINTS. TP1-TP10 are 1.0 x 1.0 mm bare F.Cu pads on the shared sensor SPI bus, its three chip
    # selects and its four interrupts: the whole sensor interface is probeable without lifting a package.
    # They are the only place these nets are reachable - the sensors are LGA/LGA-like parts with no
    # accessible leads, so a logic analyser has nowhere else to land.
    TESTPOINTS=[('TP1','SENS_SCK'),('TP2','SENS_MOSI'),('TP3','SENS_MISO'),
                ('TP4','IMU_CS'),('TP5','BARO_CS'),('TP6','HG_ACC_CS'),
                ('TP7','IMU_INT1'),('TP8','IMU_INT2'),('TP9','BARO_INT'),('TP10','HG_ACC_INT')]
    for i,(ref,net) in enumerate(TESTPOINTS):
        s.add(ref,'Connector:TestPoint','TP %s'%net,30+38*i,148,{'1':net},
              'TestPoint:TestPoint_Pad_1.0x1.0mm',refofs=(25+38*i,136))
    s.note('TEST POINTS TP1-TP10 (TestPoint:TestPoint_Pad_1.0x1.0mm, 1 x 1 mm bare F.Cu pad, no 3D model by design -\n'
           'tools/audit_footprints.py --no-3d-ok covers ^TestPoint_ along with the pad rows and mounting holes).\n'
           'TP1 SENS_SCK | TP2 SENS_MOSI | TP3 SENS_MISO | TP4 IMU_CS | TP5 BARO_CS | TP6 HG_ACC_CS | TP7 IMU_INT1 |\n'
           'TP8 IMU_INT2 | TP9 BARO_INT | TP10 HG_ACC_INT. Placement: inside the sensor cluster, within 6 mm of\n'
           'U21/U22/U23 (tools/setup_pcb.py checks it). They add ten stubs to the SPI bus, which is why they are 1 mm\n'
           'pads next to the parts rather than a header somewhere else: at 10 MHz SCK a short stub is a capacitive load,\n'
           'a long one is a transmission line. No series resistors and no ground pad of their own - probe ground comes\n'
           'off a mounting hole or the J6 array.',15,160,1.3)

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
    s.note('An OPTIONAL QSPI expansion socket on the shared QSPI bus with GPIO0/QMI CS1n as its chip select, and a\n'
           'latched microSD wired for 4-bit PIO (also SPI-compatible). Both on V3V3_SYS with local bulk, per the rail\n'
           'split in DESIGN_SPEC.\n'
           'U24, C62 AND C63 ARE DNP - NOT FITTED BY DEFAULT AND NOT IN THE BOM. The land is on the BACK of the board\n'
           '(B.Cu) as a user expansion: firmware and logs use the RP2354B in-package 2 MB flash and the J11 microSD.\n'
           'U24 IS A SOCKET, NOT ONE PART: the 150-mil SOIC-8 land takes either a W25Q64JVSSIQ NOR flash or an\n'
           'APS6404L-3SQR-SN 8 MB QSPI PSRAM - see the U24 note below. R35 stays POPULATED.',15,10,1.6)
    s.add('U24','Memory_Flash:W25Q32JVSS','DNP: W25Q64JVSSIQ, 64 Mbit QSPI NOR (optional back-side expansion)',95,75,
          {'1':'FLASH_CS1','2':'QSPI_SD1','3':'QSPI_SD2','4':'GND','5':'QSPI_SD0','6':'QSPI_SCLK','7':'QSPI_SD3','8':V3},
          'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',refofs=(85,100),vlab=True,dnp=True)
    # R35 stays POPULATED on the front: it is the FLASH_CS1 idle pull-up, and
    # GPIO0 has to be held deselected whether or not the socket is fitted.
    s.passive('R35','R','10k, FLASH_CS1 pull-up',170,75,V3,'FLASH_CS1')
    s.passive('C62','C','100n / 16 V X7R, U24 VCC (fitted; socket is optional)',210,75,V3,'GND')
    s.passive('C63','C','1u / 10 V X7R 0402, U24 VCC (fitted; socket is optional)',250,75,V3,'GND')
    s.add('J11','Connector:Micro_SD_Card_Det2','microSD, Molex 104031-0811 push-push',110,175,
          {'1':'SD_D2','2':'SD_D3','3':'SD_CMD','4':V3,'5':'SD_CLK','6':'GND','7':'SD_D0','8':'SD_D1',
           '9':'SD_DET','10':'GND','SH':'GND'},'MARV_Packages:microSD_HC_Molex_104031-0811',refofs=(88,150))
    grid=[(x,y) for y in (150,185) for x in (215,250,285)]
    for ref,(x,y),net in zip(['R36','R37','R38','R39','R40','R41'],grid,
                             ['SD_CMD','SD_D0','SD_D1','SD_D2','SD_D3','SD_DET']):
        s.passive(ref,'R','10k, %s pull-up'%net,x,y,V3,net)
    s.passive('C64','C','100n / 16 V X7R, at the socket',215,225,V3,'GND')
    s.passive('C65','C','10u / 10 V X7R 0603, at the socket',250,225,V3,'GND')
    s.passive('C66','C','47u / 6.3 V X5R 0805, at the socket',285,225,V3,'GND',foot='Capacitor_SMD:C_0805_2012Metric')
    s.note('U24 shares the dedicated QSPI pads with the RP2354B in-package flash die (datasheet Sec 14.3): CLK = QSPI_SCLK,\n'
           'DI/IO0 = QSPI_SD0, DO/IO1 = QSPI_SD1, WP/IO2 = QSPI_SD2, HOLD/IO3 = QSPI_SD3. Only the chip select differs -\n'
           'FLASH_CS1 comes from GPIO0 (QMI CS1n), pulled up to V3V3_SYS by R35 so the part is deselected before the MCU\n'
           'drives it. QSPI_SS (the internal die) keeps its own strap on the MCU sheet.\n'
           'U24 SOCKET - OPTIONAL PSRAM OR SECOND FLASH. The land is Package_SO:SOIC-8_3.9x4.9mm_P1.27mm (150 mil), which\n'
           'fits BOTH the default W25Q64JVSSIQ (Winbond, 64 Mbit = 8 MB NOR flash, SOIC-8 150 mil) and the\n'
           'APS6404L-3SQR-SN (AP Memory, 64 Mbit = 8 MB QSPI pseudo-SRAM, SOP-8 150 mil). The two are pin-identical on\n'
           'this bus: 1 CE#/CS#, 2 SO/SIO1, 3 SIO2 (WP# on the flash), 4 VSS/GND, 5 SI/SIO0, 6 SCLK, 7 SIO3 (HOLD# on the\n'
           'flash), 8 VCC - so no board change is needed to swap them. The RP2350 QMI supports a PSRAM on CS1 with its own\n'
           'timing/chip-select registers (RP2350 datasheet Sec 12.14 QMI, M1_TIMING/M1_RFMT/M1_WFMT), which is what makes\n'
           'the alternative real rather than mechanical. Fit the W25Q64 flash for log space or the PSRAM for\n'
           'XIP-addressable RAM - neither is fitted at build.\n'
           'DNP / BACK SIDE. U24, C62 and C63 carry (dnp yes) + (in_bom no): the land pattern, the nets and R35 are on\n'
           'the board, the parts are not bought and not placed. The socket and its two bypass caps sit on B.Cu under\n'
           'the MCU, against U20 QSPI pads 70-75, so the QSPI stubs are the board thickness plus a via; the front stays\n'
           'a single-sided assembly because nothing DNP is reflowed. A B.SilkS legend beside the land says what fits.\n'
           'CONSEQUENCE FOR THE BUDGET: the 25 mA QSPI-flash burst is NOT in the V3V3_SYS load budget any more\n'
           '(DESIGN_SPEC "Rails and load budget"); add it back if the socket is populated.\n'
           'SYMBOL SUBSTITUTION: KiCad 10 ships no W25Q64JVSS symbol (Memory_Flash has W25Q16JVSS, W25Q32JVSS, W25Q128JV*\n'
           'only). U24 therefore uses Memory_Flash:W25Q32JVSS, whose pinout is identical across the whole W25Q JV family;\n'
           'the Value field carries the real MPN. See LIBRARIES.md.',15,245,1.3)
    s.note('J11: DET_A to GND and DET_B to SD_DET with a 10k pull-up, so the input reads low with a card inserted. The\n'
           'shield goes to GND. 100 nF + 10 uF + 47 uF sit at the socket (DESIGN_SPEC "Rails": SD transients stay on the\n'
           'buck rail). 10k pull-ups on CMD and DAT0-DAT3 are the SD-standard idle bias and also keep DAT3/CD high for\n'
           '4-bit mode. VDD = V3V3_SYS.',15,268,1.3)
    return s

def build():
    src=Sheet('power_sources','POWER 1 / ESC pad row, VBAT buck, USB, priority power mux',2)
    src.note('BOARD INPUTS: VBAT 6-25.2 V (2-6S) from the ESC pad row J3, and USB VBUS ~5 V (J4). U26 (AP63205WU) makes\n'
             '5V_IN from VBAT; 5V_IN is the priority input of the U25 power mux and also the servo 5 V bus.',15,15,2)
    # J3 is the MicoAir AM32 4-in-1 ESC's FC-connection pad row, left to right as printed on the ESC:
    # CURR, TX, M4, M3, M2, M1, VBAT, GND. The ORDER is authoritative (it is what the ESC silkscreen reads);
    # the pitch is an assumption - MicoAir publishes no pad drawing - so PadRow_1x08_P2.00mm uses 2.00 mm and
    # must be confirmed against the physical ESC before fab. See DESIGN_SPEC "Physical design".
    src.add('J3','Connector_Generic:Conn_01x08','ESC pads (CURR TX M4 M3 M2 M1 VBAT GND)',40,172,
            {'1':'CURR_SENSE_RAW','2':'ESC_TELEM','3':'PWM4','4':'PWM3','5':'PWM2','6':'PWM1','7':'VBAT','8':'GND'},
            'MARV_Packages:PadRow_1x08_P2.00mm')

    # U26 AP63205WU: 3.8-32 V in, fixed 5.0 V / 2 A synchronous buck, TSOT-23-6 (Diodes DS41326 Rev. 2-2).
    # Values are Table 3 "Recommended Component Selections for AP63205" / Figure 21 verbatim:
    # L 4.7 uH, C1 10 uF, C2 3 x 22 uF (C76/C77/C80; datasheet minimum is 2 x 22 uF), C3 100 nF. FB is a sense input on the fixed-output parts and goes
    # straight to the output (Sec 9 "Setting the Output Voltage"); there is no external divider.
    src.add('U26','Regulator_Switching:AP63205WU','AP63205WU-7',75,100,
            {'1':'5V_IN','2':'U26_EN','3':'VBAT','4':'GND','5':'U26_SW','6':'U26_BST'})
    src.passive('C73','C','10u / 50 V X5R 0805 GRM21BR61H106KE43, VIN bulk',30,50,'VBAT','GND',foot='Capacitor_SMD:C_0805_2012Metric')
    src.passive('C74','C','100n / 50 V X7R 0402, VIN HF bypass',65,50,'VBAT','GND',foot='Capacitor_SMD:C_0402_1005Metric')
    src.passive('R52','R','100k / 1%, EN to VIN',100,50,'VBAT','U26_EN')
    src.passive('C75','C','100n / 50 V X7R 0402, bootstrap',135,50,'U26_BST','U26_SW',foot='Capacitor_SMD:C_0402_1005Metric')
    src.passive('L3','L','4.7u, Isat 4.4 A, DCR 31.5 mOhm max (Coilcraft XGL4030-472MEC)',125,100,'U26_SW','5V_IN',
                foot='MARV_Packages:L_Coilcraft_XxL4030')
    src.passive('C76','C','22u / 25 V X5R 0805 GRM21BR61E226ME44, buck COUT',30,140,'5V_IN','GND',foot='Capacitor_SMD:C_0805_2012Metric')
    src.passive('C77','C','22u / 25 V X5R 0805 GRM21BR61E226ME44, buck COUT',65,140,'5V_IN','GND',foot='Capacitor_SMD:C_0805_2012Metric')
    src.passive('C80','C','22u / 25 V X5R 0805 GRM21BR61E226ME44, buck COUT (3rd: >=44 uF after DC-bias derating, AP63205 EVB guide)',100,140,'5V_IN','GND',foot='Capacitor_SMD:C_0805_2012Metric')

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
    src.passive('C7','C','1u / 10 V X7R 0402',25,275,'USB_VBUS','GND')

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
             'SS (Sec 9.3.1 / Table 9-1): C70 100 nF -> 780 V/s at 5 V, so the ~120 uF on V5_SYS draws ~94 mA of inrush and OUT ramps in ~6.4 ms.\n'
             'ST (Sec 6, Sec 10.2.3) is an open-drain status output: HIGH when IN1 (or neither input) drives OUT, LOW when IN2 does. R47 10k to\n'
             'V3V3_SYS is inside the RST = 6-20 kOhm recommended operating range of Sec 7.3; PWR_SRC_ST lands on RP2354B GPIO39 (pin 48).\n'
             'Sec 11 gives no numeric minimum COUT, only "increase the capacitance on OUT to avoid output voltage drop"; C19 100 uF + C8/C9\n'
             '2 x 10 uF on POWER 2 give 120 uF nominal, inside the 100-200 uF the datasheet design examples use, so no extra output capacitor\n'
             'is added here. C19 was a 220 uF / 10 V D case until the handover decks were re-run at 100 uF and every predicate still passed.\n'
             'WHAT CHANGED WITH THE ON-BOARD BUCK: IN1 is no longer an external BEC of unknown quality, it is U26\'s regulated 5.00 V +/-1% output.\n'
             'PR1 therefore sits far above its 4.494 V rising threshold whenever the pack is connected, so IN1 selection is unconditional in normal\n'
             'operation, and OV1 (5.862 V typ, 5.585 V worst case) can only trip on a U26 failure - it is now a backstop against a shorted high-side\n'
             'FET pushing VBAT onto 5V_IN, not the mis-plug guard it used to be. The mis-plug case itself is gone: there is no 5 V input connector\n'
             'left to mis-plug, and VBAT does not reach V5_SYS by any path. The divider values are kept as they are because they still bound both\n'
             'ends of the window and cost nothing.',150,150,1.25)
    src.note('ESC PAD ROW J3 (MicoAir AM32 4-in-1 ESC, FC-connection row). Order is the ESC silkscreen read left to right:\n'
             '1 CURR - analog current sense from the ESC, 12.75 mV/A, 0-3.3 V -> R53/C78 -> GPIO42 (ADC2) on BOARD 1.\n'
             '2 TX   - KISS ESC telemetry, 3.3 V, 115200 baud, ESC output only -> R54 -> GPIO30 (PIO UART RX).\n'
             '3-6 M4 M3 M2 M1 - 3.3 V DShot/PWM inputs, straight from the RP2354B (PWM4..PWM1 = GPIO5, 4, 3, 2).\n'
             '7 VBAT - raw pack, 6-25.2 V (2-6S), the only board power input besides USB.  8 GND.\n'
             'PITCH IS AN ASSUMPTION: MicoAir publishes no pad drawing, so MARV_Packages:PadRow_1x08_P2.00mm assumes\n'
             '2.00 mm. The ORDER is authoritative; confirm the pitch against the physical ESC before fab.\n'
             'The ESC-side low-ESR electrolytic on VBAT is MANDATORY: this board carries ceramic input capacitance only\n'
             '(C73 10 uF + C74 100 nF), and a ceramic-only pack connection rings to roughly twice pack voltage on hot\n'
             'plug. There is no TVS on VBAT by design - nothing that clamps below 32 V survives a 6S pack.',150,205,1.25)
    src.note('U26 AP63205WU-7 VBAT BUCK (Diodes DS41326 Rev. 2-2). 3.8-32 V in, FIXED 5.0 V out (4.95/5.00/5.05 V,\n'
             'Electrical Characteristics VFB row), 2 A, 1.1 MHz with +/-6% frequency spread spectrum, 4 ms internal\n'
             'soft-start, 22 uA quiescent, TSOT-23-6. VIN abs max 35 V DC / 40 V for 400 ms vs a 25.2 V 6S pack.\n'
             'Component values are Table 3 "Recommended Component Selections for AP63205" and Figure 21 verbatim:\n'
             'L 4.7 uH (L3), C1 10 uF (C73), C2 3 x 22 uF (C76/C77/C80; datasheet minimum is 2 x 22 uF), C3 100 nF bootstrap BST-SW (C75).\n'
             'FB (pin 1) is a SENSE input on the fixed-output parts and goes straight to the 5 V output - Sec 9 "Setting\n'
             'the Output Voltage": only the adjustable AP63200/AP63201 take a divider. FB abs max 6.0 V.\n'
             'EN (pin 2): "The EN pin is a high voltage pin and can be directly connected to VIN" (Sec 3 "Enable"), abs\n'
             'max 35 V, threshold 1.18 V rising / 1.10 V falling, internal 1.5 uA pull-up. R52 100k from VBAT is that\n'
             'connection with a series element, so a VBAT transient reaches the EN clamp through 100k rather than\n'
             'directly, and so a UVLO divider (Eq.1/Eq.2) or a start-delay cap (Eq.3) can be added later without\n'
             'touching the VBAT copper. Device UVLO is 3.5 V typ rising regardless.\n'
             'L3: Coilcraft XGL4030-472MEC, 4.7 uH +/-20%, DCR 31.5 mOhm max, Isat 3.2 A at 20% / 4.4 A at 30% drop,\n'
             'Irms 4.8 A at 20 C rise (Coilcraft Doc 1575-1). Isat(20%) clears the AP63205 high-side peak current limit\n'
             'at its 3.1 A maximum, so the inductor does not saturate even in a current-limit or hiccup event; DCR is\n'
             'inside the datasheet\'s "less than 100 mOhm" guidance. 4.0 x 4.0 x 3.1 mm. THIS ONE CANNOT SHRINK THE\n'
             'WAY L2 DID: L2 is now an XGL3020 (3.0 x 3.0 x 2.0) because the TPS62913 runs it at ~1 A, but L3 has to\n'
             'clear the AP63205 3.1 A high-side limit, and Isat(20%) = 3.2 A is the floor that sets the 4 x 4 body.\n'
             'If height ever has to come out of here, the XGL4020 series shares this land pattern at 2.0 mm tall -\n'
             'but a 2.0 mm core stores less energy, so its 4.7 uH Isat is lower: check it against the 3.1 A limit\n'
             'from the XGL4020 datasheet before making that swap.\n'
             'Ripple at 25.2 V in / 2 A out is 0.78 A pk-pk (Eq.7), peak 2.39 A (Eq.8).\n'
             'DERATING CAVEAT: C73 and C76/C77/C80 are the datasheet nominal values, and ceramic DC-bias derating is NOT\n'
             'in them - a 10 uF/50 V 0805 at 25 V and a 22 uF/25 V 0805 at 5 V both lose roughly half. The EVB user\n'
             'guide asks for >= 44 uF of COUT (nominal 66 uF: all three 22 uF fitted) and the board fits the third 22 uF (C80).\n'
             'PACKAGES: C73 is a 10 uF/50 V X5R 0805 (GRM21BR61H106KE43) and C76/C77/C80 are 22 uF/25 V X5R 0805\n'
             '(GRM21BR61E226ME44) - down from 1206 for the 50 mm single-sided envelope; C74/C75 are 50 V X7R 0402.\n'
             'Same capacitance, same voltage rating, smaller body: the DC-bias loss above is the 0805 figure and is\n'
             'not made worse by the package change at these ratings, but none of these parts is bench-reworkable.',150,238,1.25)
    src.note('USB_VBUS feeds U25 IN2 directly; no inrush or current limiting on this sheet.\nData ESD protection is on POWER 2. No servo rail connection.',330,130,1.2)

    out=Sheet('power_3v3','POWER 2 / 3.3 V system buck and analog LDO',3)
    out.note('AVIONICS ONLY: 300 mA continuous / 500 mA short peak, provisional. NO SERVO POWER.',15,15,2)
    out.add('U7','Regulator_Switching:TPS62913','TPS62913RPUR',95,70,{'1':'V5_SYS','2':'U7_SW','3':'U7_VO','4':'GND','5':'PWR_GOOD','6':'V5_SYS','7':'GND','8':'U7_SS','9':'U7_FB','10':'U7_SCONF'},
            'MARV_Packages:Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm')
    out.passive('L2','L','2.2u / Isat 2.2 A (20 %), DCR 30.5 mOhm (Coilcraft XGL3020-222MEC)',175,50,'U7_SW','U7_VO',
                foot='MARV_Packages:L_Coilcraft_XGL3020')
    out.passive('FB1','FerriteBead','8.5 ohm @100MHz / 4 mOhm DCR / 5 A (MuRata BLE18PS080SN1 or equiv)',175,90,'U7_VO','V3V3_SYS',foot='Inductor_SMD:L_0603_1608Metric')
    for ref,x in [('C8',25),('C9',25)]:
        out.passive(ref,'C','10u / 10 V X7S 0603',x,55 if ref=='C8' else 105,'V5_SYS','GND')
    out.passive('C17','C','2.2n / 50 V X7R, VIN-PGND HF bypass',55,60,'V5_SYS','GND',foot='Capacitor_SMD:C_0402_1005Metric')
    out.passive('C19','C','100u / 6.3 V polymer, ESR <= 40 mOhm (e.g. Panasonic 6TPE100MAZB or KEMET T520/T530 B case)',
                25,155,'V5_SYS','GND','Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B')
    for ref,x in [('C10',245),('C11',310),('C12',375)]:
        out.passive(ref,'C','22u / 10 V X5R 0603 GRM188R61A226ME15, 1st-stage COUT (~40% DC-bias loss at 3.3 V)',x,50,'U7_VO','GND')
    for ref,x in [('C23',245),('C24',310)]:
        out.passive(ref,'C','22u / 10 V X5R 0603 GRM188R61A226ME15, 2nd-stage Cf post-bead (~40% DC-bias loss at 3.3 V)',x,75,'V3V3_SYS','GND')
    out.passive('C13','C','470n / 16 V X7R 0402, NR/SS soft-start + noise filter (5 ms)',95,125,'U7_SS','GND')
    out.passive('R7','R','15.8k / 0.1%',245,105,'V3V3_SYS','U7_FB')
    out.passive('R8','R','4.99k / 0.1%',310,105,'U7_FB','GND')
    out.passive('R9','R','6.04k / 1%, S-CONF: 2.2 MHz + triangle SSM, discharge off, no sync',175,120,'U7_SCONF','GND')
    out.passive('R10','R','100k',245,155,'V3V3_SYS','PWR_GOOD')
    out.note('PASSIVE PACKAGES (DESIGN_SPEC "Physical design"): resistors are 0201, ceramics <= 4.7 uF are 0402 and the\n'
             '10-22 uF ceramics are 0603. C10/C11/C12 (1st-stage COUT) and C23/C24 (post-bead Cf) are 22 uF / 10 V X5R\n'
             '0603 (GRM188R61A226ME15): at 3.3 V DC bias an X5R 22 uF 0603 keeps roughly 60 % of its nominal value, so\n'
             'the 66 uF nominal of the first stage is ~40 uF effective and the 44 uF post-bead stage is ~26 uF. The\n'
             'ngspice decks still carry the NOMINAL 66 uF (simulations/*.cir COUT), so the modelled rail is optimistic\n'
             'by that margin - an open item, not a result. Do not read the effective value off the BOM either.\n'
             '0201 resistors and 22 uF 0603 ceramics are machine-place parts - JLC assembles them, a bench iron does not.\n'
             'C19, THE V5_SYS BULK, IS 100 uF / 6.3 V POLYMER IN AN EIA-3528-21 (B) CASE, down from 220 uF / 10 V in an EIA-7343-31 (D)\n'
             'case: 8.9 x 4.9 mm of courtyard became 4.3 x 3.2 mm. The handover decks (simulations/source_handover.cir CPOLY, and the\n'
             'integrated deck) were re-run at 100 uF nominal / 80 uF derated and every predicate still passes - V5_SYS holds well above\n'
             'the 3.5 V floor across the 100 us TPS2121 switchover - which is what licenses the smaller case. ESR must stay <= 40 mOhm\n'
             '(the value modelled): Panasonic 6TPE100MAZB or a KEMET T520/T530 B case. 6.3 V on a 5.0 V rail is a 1.26x derating, the\n'
             'normal polymer figure; a tantalum electrolytic would need 2x and would not qualify.',245,163,1.25)
    out.note('V3V3_SYS feedback (TPS62913 datasheet Sec 8.2.2.2.6, Eq.8): VOUT = VFB x (1 + R1/R2); VFB = 0.8 V typ, 0.792-0.812 V spec (Sec 6.5).\nR2 = 4.99 kOhm (<=5 kOhm per datasheet noise guidance). R1 = R2 x (VOUT/VFB - 1) = 4.99k x (3.3/0.8 - 1) = 4.99k x 3.125 = 15.59 kOhm -> nearest 1% E96 = 15.8 kOhm.\nActual VOUT = 0.8 V x (1 + 15.8k/4.99k) = 3.33 V nominal (3.30-3.38 V across VFB tolerance).',15,180,1.3)
    out.note('S-CONF = 6.04 kOhm to GND (Table 7-1): 2.2 MHz switching, triangle spread-spectrum ON, output discharge OFF, no external sync.\n2.2 MHz + 2.2uH matches the VIN=5V/VOUT<=3.3V design table (Table 8-2). TPS62913 runs fixed-frequency PWM at all loads, no light-load skip mode (Sec 7.4.1) -- forced PWM is inherent; there is no separate MODE pin on this device.\nVO (pin 3) senses the node between L1 and the ferrite bead (device internal loop); the FB divider senses V3V3_SYS after the bead for low-noise remote regulation (Sec 7.1 / 8.2.2.2.4).',15,215,1.3)
    out.add('U12','Regulator_Linear:TPS7A20xxxDBV','TPS7A2033PDBVR',95,200,{'1':'V5_SYS','2':'GND','3':'PWR_GOOD','4':None,'5':'V3V3_ANA'})
    out.passive('C25','C','1u / 10 V X7R 0402, LDO input',55,195,'V5_SYS','GND')
    out.passive('C26','C','1u / 10 V X7R 0402, LDO output, ESR <=100 mOhm',150,195,'V3V3_ANA','GND')
    out.note('3V3_ANA feeds ICM-45686, BMP581, ADXL375 and the RP2354B ADC_AVDD pin (100 nF at each pin on the MCU sheet); VREG_AVDD is filtered\n'
             'from V3V3_SYS instead, so the analog rail carries no core-regulator current. U12 EN (pin 3) is on PWR_GOOD rather than V5_SYS:\n'
             'the analog rail therefore starts only once the TPS62913 declares V3V3_SYS in regulation, and drops with it, which removes the\n'
             'window where the sensors were biased from an unregulated V5_SYS while the MCU was still held in reset.',15,240,1.3)
    out.note('L2 INDUCTOR - Coilcraft XGL3020-222MEC, 3.0 x 3.0 x 2.0 mm (Coilcraft Doc 1776 Rev. 02/19/26): 2.2 uH +/-20%,\n'
             'DCR 30.5 mOhm typ / 36.5 max, Isat 1.5 A at 10% / 2.2 A at 20% / 2.85 A at 30% inductance drop, Irms 5.0 A at 20 C rise.\n'
             'It replaces the XGL4030-222MEC (4.0 x 4.0 x 3.1 mm, Isat 7 A): same 2.2 uH, 1.1 mm shorter, 7 mm2 less board, and L2\n'
             'is no longer the tallest part. OPERATING POINT: dIL = VOUT x (1 - VOUT/VIN)/(L x fsw) = 3.3 x 0.34/(2.2u x 2.2M)\n'
             '= 0.23 A pk-pk nominal, 0.29 A at the -20% inductance limit, so at the 0.8 A design load the peak inductor current\n'
             'is ~0.95 A and stays under ~1.05 A with VIN/fsw/L tolerances stacked. Isat(20%) = 2.2 A is ~2.1x that, and Irms\n'
             '5.0 A is far above the 0.8 A DC: saturation is the constraint here, not self-heating.\n'
             'THE FAULT CASE IS DELIBERATELY NOT COVERED. The TPS62913 high-side current limit is ~4.5 A, ABOVE Isat(30%) = 2.85 A,\n'
             'so a hard short on V3V3_SYS does drive this inductor into saturation before the IC limits - the opposite of the rule\n'
             'used for L3/U26, where Isat(20%) clears the AP63205 limit. Accepted, for two reasons: the XGL is a moulded COMPOSITE\n'
             'core that SOFT-saturates (the datasheet quotes 10/20/30% inductance-drop currents, not a knee, because the roll-off is\n'
             'gradual), so there is no ferrite-style collapse and the cycle-by-cycle limit still acts, just on a larger ripple; and\n'
             'this rail is 300 mA continuous / 500 mA peak, an order below that limit. Sizing L2 for a 4.5 A fault means carrying a\n'
             '4 x 4 x 3.1 mm part to survive a condition that is already a board failure. RE-CHECK IF THE 3.3 V BUDGET EVER EXCEEDS\n'
             '~1.5 A CONTINUOUS: the operating peak then approaches Isat(10%) and L2 has to go back up to the XGL4030.\n'
             'ORIENTATION: MARV_Packages:L_Coilcraft_XGL3020 pad 1 is the terminal-start (short-lead) side - the bar next to the C\n'
             'in the part marking. PUT U7_SW ON PAD 1: the datasheet asks for the high dv/dt node on the start lead (EMI).',15,250,1.2)
    out.add('U8','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',245,220,{'1':'USB_DP','2':'GND','3':'USB_DM','4':'USB_DM_MCU','5':'USB_VBUS','6':'USB_DP_MCU'})

    periph=Sheet('power_periph','POWER 3 / IO array',4)
    periph.note('IO ARRAY - ONE 3-COLUMN x 14-ROW THROUGH-HOLE BLOCK ON THE RIGHT EDGE, 2.54 mm, madflight FC3v2 style.\n'
                'It replaces the old 2x16 left-edge array AND the J12/J13/J14 servo block: every signal that leaves this board\n'
                'except the ESC row (J3) and the SWD pads (J10) now leaves on this one block.\n'
                'COLUMN RULE, from the board edge inward: GND (J8) | POWER (J7) | SIGNAL (J6). The SIGNAL column is the INNERMOST\n'
                'one, next to the MCU, so the 14 signal traces are the short ones; the two rails run down the outside where a\n'
                'plane stitch is cheap. A 3-wire module lead (signal, power, ground) plugs straight across ONE row.\n'
                'THREE Conn_01x14 SYMBOLS, not one 3x14: no 3-row generic connector symbol ships with this KiCad install, and\n'
                'three 1x14 rows with a body-trimmed courtyard abut exactly on the 2.54 mm grid (see tools/setup_pcb.py).\n'
                'DS-009 NAMING IS KEPT: a port label is named for the PERIPHERAL pin it belongs to, so GPS_RX / ELRS_RX are module\n'
                'inputs driven by the RP2354B UART TX pins (rows 1 and 3, silk T0 / T1) and GPS_TX / ELRS_TX are module outputs\n'
                'that land on the MCU UART RX pins (rows 2 and 4, silk R0 / R1).',15,10,1.35)
    periph.passive('C20','C','10u / 10 V X7R 0603',25,60,'V5_SYS','GND')
    periph.passive('C21','C','10u / 10 V X7R 0603',25,85,'V5_SYS','GND')
    periph.passive('C22','C','10u / 10 V X7R 0603',25,110,'V3V3_SYS','GND')
    periph.note('C20 / C21: V5_SYS local bulk at the array (rows 1-4 GPS/ELRS and rows 7-10 servo, the 5 V supply rows).\nC22: V3V3_SYS local bulk at the array (rows 5-6 and 11-14).',15,130,1.3)
    # The IO array: 14 rows, three pins each.  Row n is J6 pin n (signal) / J7 pin n (power) / J8 pin n (GND).
    # Row 1 is at the TOP of the block; the columns run GND | POWER | SIGNAL from the board edge inward.
    IO_ROWS=[('T0','GPS_RX','V5_SYS','UART0 TX -> GPS RX (GPIO12)'),
             ('R0','GPS_TX','V5_SYS','UART0 RX <- GPS TX (GPIO13)'),
             ('T1','ELRS_RX','V5_SYS','UART1 TX -> ELRS RX (GPIO8)'),
             ('R1','ELRS_TX','V5_SYS','UART1 RX <- ELRS TX (GPIO9)'),
             ('SDA','MAG_SDA',V3,'I2C1 SDA (GPIO6), 4.7k pull-up on the MCU sheet'),
             ('SCL','MAG_SCL',V3,'I2C1 SCL (GPIO7), 4.7k pull-up on the MCU sheet'),
             ('S5','PWM5','V5_SYS','PWM5 A (GPIO10), servo 5'),
             ('S6','PWM6','V5_SYS','PWM5 B (GPIO11), servo 6'),
             ('S7','PWM7','V5_SYS','PWM7 A (GPIO14), servo 7'),
             ('S8','PWM8','V5_SYS','PWM7 B (GPIO15), servo 8'),
             ('A44','IO_GPIO44',V3,'GPIO44 = ADC4, spare'),
             ('A45','IO_GPIO45',V3,'GPIO45 = ADC5, spare'),
             ('A46','IO_GPIO46',V3,'GPIO46 = ADC6, spare'),
             ('A47','IO_GPIO47',V3,'GPIO47 = ADC7, spare')]
    periph.add('J6','Connector_Generic:Conn_01x14','IO array signal column (innermost)',150,130,
               {str(i+1):sig for i,(silk,sig,pwr,fn) in enumerate(IO_ROWS)},
               'MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow',refofs=(136,100))
    periph.add('J7','Connector_Generic:Conn_01x14','IO array power column (5V / 3V3 per row)',215,130,
               {str(i+1):pwr for i,(silk,sig,pwr,fn) in enumerate(IO_ROWS)},
               'MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow',refofs=(201,100))
    periph.add('J8','Connector_Generic:Conn_01x14','IO array GND column (board edge)',280,130,
               {str(i+1):'GND' for i in range(14)},
               'MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow',refofs=(266,100))
    periph.note('IO ARRAY ROW MAP (row n = J6 pin n signal | J7 pin n power | J8 pin n GND)\n'
                +'\n'.join('%2d  %-4s %-11s | %-9s | GND  %s'%(i+1,silk,sig,pwr,fn)
                           for i,(silk,sig,pwr,fn) in enumerate(IO_ROWS)),15,150,1.3)
    periph.note('RAILS ON THE ARRAY: rows 1-4 (GPS, ELRS) and rows 7-10 (servos S5-S8) take V5_SYS; rows 5-6 (magnetometer)\n'
                'and rows 11-14 (the four exposed spares) take V3V3_SYS. Every row has its own GND pin in the J8 column, so a\n'
                'signal return is never more than 2.54 mm away and no row can be mis-plugged into a neighbour\'s ground.\n'
                'SERVO 5 V NOW COMES FROM V5_SYS, NOT 5V_IN. The old J13 servo row tapped 5V_IN directly at the U26 buck\n'
                'output, ahead of the U25 priority mux, so servo current was outside the mux current limit. With one power\n'
                'column the array cannot carry two different 5 V nets under one "5V" silk label, so all eight 5 V rows are\n'
                'V5_SYS: servo current now crosses U25 and counts against its ILM limit (1.49 A, R46) and against the U26\n'
                'buck. Budget servo current against BOTH - see DESIGN_SPEC "Rails and load budget".\n'
                'CURRENT: rows 1-4 and 7-10 count against the U26 buck through the mux; rows 5-6 and 11-14 count in the\n'
                'V3V3_SYS budget. No fuse and no per-row current limit: the array is a system-integration connector, not a\n'
                'protected port.',15,215,1.35)
    periph.note('PWM MAP\nPWM5 = GPIO10 (row 7, S5)\nPWM6 = GPIO11 (row 8, S6)\nPWM7 = GPIO14 (row 9, S7)\nPWM8 = GPIO15 (row 10, S8)\n\n'
                'ON THE ESC PAD ROW (J3, POWER 1)\nPWM1 = GPIO2\nPWM2 = GPIO3\nPWM3 = GPIO4\nPWM4 = GPIO5',330,150,1.3)

    mcu=mcu_sheet(); sens=sensors_sheet(); sto=storage_sheet()
    sheets=[src,out,periph,mcu,sens,sto]
    for sheet,net,x,y,num in [(src,'GND',400,190,1),(src,'5V_IN',400,215,2),(src,'USB_VBUS',400,240,3),(src,'V5_SYS',400,265,4),
                              (src,'VBAT',400,165,8),
                              (mcu,'V3V3_SYS',155,262,5),(mcu,'VREG_AVDD',185,262,6),(mcu,'DVDD',215,262,7)]:
        sheet.add('#FLG'+str(num),'power:PWR_FLAG','PWR_FLAG',x,y,{'1':net})
    root=['(kicad_sch (version 20250114) (generator "eeschema") (uuid '+uid('power-root')+') (paper "A3") (title_block (title "MARV integrated power - preliminary") (date "2026-09-14") (rev "P0 - NOT FOR FAB")) (lib_symbols)']
    root.append('(text '+q('Integrated draft: power chain (sheets 2-4) and board stage (sheets 5-8). See DESIGN_SPEC.md.\n'
                            'Inputs: VBAT 6-25.2 V (2-6S) from the MicoAir AM32 ESC pad row J3, and USB VBUS.\n'
                            'Rails: 5V_IN from the U26 AP63205 buck, V5_SYS from the U25 TPS2121 mux, V3V3_SYS from the\n'
                            'TPS62913 buck, V3V3_ANA from the TPS7A20 LDO. Servo 5 V is 5V_IN, upstream of the mux.\n'
                            'No PCB placement or routing has been performed.')+' (at 20 20 0) (effects (font (size 1.8 1.8)) (justify left top)) (uuid '+uid('root-note')+'))')
    for i,s in enumerate(sheets):
        x,y=20+200*(i//4),60+38*(i%4)
        root.append(f'(sheet (at {x} {y}) (size 180 25) (fields_autoplaced yes) (stroke (width 0.1524) (type default)) (fill (color 0 0 0 0.0000)) (uuid {s.id}) (property "Sheetname" {q(s.title)} (at {x} {y-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" "{s.name}.kicad_sch" (at {x} {y+26} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "MARV-V2" (path "/{uid("power-root")}" (page "{s.page}")))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n')
    files={'MARV-V2.kicad_sch':'\n'.join(root).replace('(fields_autoplaced yes)', '(fields_autoplaced)')}
    files.update({s.name+'.kicad_sch':s.render() for s in sheets})
    files['power_bom.csv']='Reference,Value,Footprint,Sheet,Fit\n'+'\n'.join(','.join(q(v) for v in row) for s in sheets for row in s.bom if not row[0].startswith('#'))+'\n'
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
