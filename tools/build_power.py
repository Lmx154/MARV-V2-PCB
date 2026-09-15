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

# Locally derived symbols: (upstream symbol, {pin: new electrical type}). Emitted into MARV_Power.kicad_sym.
# LM66100_OR: VOUT/CE tie makes pin 6 passive. BMI088_SPI: SDO2 is retyped passive so the accelerometer and
# gyroscope data outputs, which are high-Z while deselected, can share one MISO net without an ERC conflict.
DERIVED={'MARV_Power:LM66100_OR':('Power_Management:LM66100DCK',{'6':'passive'}),
         'MARV_Power:BMI088_SPI':('Sensor_Motion:BMI088',{'10':'passive'})}

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
        source,retype=DERIVED.get(libid,(libid,None))
        sym=symbol(source)
        if retype:
            for p in pins(sym):
                if unquote(first(p,'number')[1]) in retype: p[1]=retype[unquote(first(p,'number')[1])]
            name,base=libid.split(':')[1],source.split(':')[1]
            for unit in children(sym,'symbol'):
                unit[1]=q(unquote(unit[1]).replace(base,name))
            sym[1]=q(name)
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
 ('20','GPIO20','IMU_ACC_CS','BMI088 CSB1'),
 ('21','GPIO21','IMU_GYR_CS','BMI088 CSB2'),
 ('22','GPIO22','BARO_CS','BMP581 CSB'),
 ('23','GPIO23','IMU_ACC_INT','BMI088 INT1'),
 ('25','GPIO24','IMU_GYR_INT','BMI088 INT3'),
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
 ('48','GPIO39',None,'spare'),
 ('49','GPIO40','VIN_SENSE','ADC0, 5V_IN 10k/15k divider'),
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
    s.note('RP2354B, QFN-80, 2 MB in-package QSPI flash. Digital rails on V3V3_SYS, analog rails on V3V3_ANA, core DVDD from the on-chip buck.\n'
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
    s.add('U20','MCU_RaspberryPi:RP2354B','RP2354B',200,150,nets,'Package_DFN_QFN:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm',refofs=(152,234),vlab=True)

    left=[(25+35*c,40+28*r) for r in range(8) for c in range(4)]
    for i in range(8):
        s.passive('C%d'%(30+i),'C','100n / 16 V X7R, IOVDD pin %s'%('5 15 24 29 41 50 60 76'.split()[i]),*left[i],V3,'GND')
    s.passive('C38','C','100n / 16 V X7R, pins 68+69',*left[8],V3,'GND')
    s.passive('C39','C','4.7u / 10 V X7R, VREG_VIN',*left[9],V3,'GND')
    s.passive('C40','C','100n / 16 V X7R, ADC_AVDD',*left[10],ANA,'GND')
    s.passive('R20','R','33 / 1%, VREG_AVDD filter',*left[11],ANA,'VREG_AVDD')
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
           'VREG_AVDD RC = 33 ohm + 4.7 uF (design guide Sec 2.1); VREG_FB is tied to DVDD, VREG_PGND to GND, EP (pin 81) to GND.',15,247,1.3)

    s.note('PORT NAMING: a port label is named for the peripheral pin it comes from, so GPS_TX / ELRS_TX are module outputs\n'
           'and land on MCU UART RX pins, while GPS_RX / ELRS_RX are module inputs fed by the MCU UART TX pins.\n'
           'J6/J7/J9 (POWER 3) are 3.3 V logic powered directly from V3V3_SYS.',155,238,1.3)
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
    s.passive('R27','R','10k / 1%, 5V_IN top',*right[0],'5V_IN','VIN_SENSE')
    s.passive('R28','R','15k / 1%, 5V_IN bottom',*right[1],'VIN_SENSE','GND')
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
    s.note('Telemetry dividers: 10k/15k gives 3.00 V at 5.00 V in, 3.15 V at 5.25 V; 100 nF at each ADC pin.\n'
           'Buzzer runs from V5_SYS (avionics OR output), never from the servo bus; D22 clamps the coil kick.\n'
           'QSPI_* are the dedicated QSPI pads: they reach the in-package flash die AND the package pins\n'
           '(RP2350 datasheet Sec 14.3), so U24 shares the bus with GPIO0/QMI CS1n (FLASH_CS1) as its select.\n'
           'RP2354 requires QSPI_IOVDD = 3.3 V, and IOVDD = 3.3 V to run a second QSPI device (Sec 14.9).',15,258,1.3)
    return s

def sensors_sheet():
    s=Sheet('sensors','BOARD 2 / IMU, barometer, high-g',6)
    s.note('All three sensors run 4-wire SPI on the shared SENS_SCK / SENS_MOSI / SENS_MISO bus with one chip select each,\n'
           'and are powered from V3V3_ANA (TPS7A20 LDO) with 100 nF + 1 uF at every supply pin per datasheet.',15,10,1.6)
    s.add('U21','MARV_Power:BMI088_SPI','BMI088 6-axis IMU',90,85,
          {'1':None,'2':'GND','3':ANA,'4':'GND','5':'IMU_GYR_CS','6':'GND','7':'GND','8':'SENS_SCK',
           '9':'SENS_MOSI','10':'SENS_MISO','11':ANA,'12':'IMU_GYR_INT','13':None,'14':'IMU_ACC_CS',
           '15':'SENS_MISO','16':'IMU_ACC_INT'},
          'Package_LGA:Bosch_LGA-16_4.5x3mm_P0.5mm_LayoutBorder7x1y_ClockwisePinNumbering',refofs=(75,120),vlab=True)
    s.add('U22','MARV_Sensors:BMP581','BMP581 barometer',220,85,
          {'1':ANA,'2':'SENS_SCK','3':'GND','4':'SENS_MOSI','5':'SENS_MISO','6':'BARO_CS','7':'BARO_INT',
           '8':'GND','9':'GND','10':ANA},None,refofs=(205,120),vlab=True)
    s.add('U23','MARV_Sensors:ADXL375','ADXL375 high-g accelerometer',345,85,
          {'1':ANA,'2':'GND','3':ANA,'4':'GND','5':'GND','6':ANA,'7':'HG_ACC_CS','8':'HG_ACC_INT',
           '9':None,'10':None,'11':'GND','12':'SENS_MISO','13':'SENS_MOSI','14':'SENS_SCK'},
          None,refofs=(330,120),vlab=True)
    grid=[(x,y) for y in (170,198) for x in (30,65,160,195,290,325)]
    for ref,(x,y),val in zip(
        ['C50','C51','C54','C55','C58','C59','C52','C53','C56','C57','C60','C61'],grid,
        ['100n / 16 V X7R, U21 VDD','1u / 10 V X7R, U21 VDD','100n / 16 V X7R, U22 VDD','1u / 10 V X7R, U22 VDD',
         '100n / 16 V X7R, U23 VS','1u / 10 V X7R, U23 VS','100n / 16 V X7R, U21 VDDIO','1u / 10 V X7R, U21 VDDIO',
         '100n / 16 V X7R, U22 VDDIO','1u / 10 V X7R, U22 VDDIO','100n / 16 V X7R, U23 VDD_IO','1u / 10 V X7R, U23 VDD_IO']):
        s.passive(ref,'C',val,x,y,ANA,'GND')
    s.note('U21 BMI088 (datasheet Sec 6.2): PS tied to GND selects SPI. CSB1 = accelerometer (IMU_ACC_CS), CSB2 = gyroscope\n'
           '(IMU_GYR_CS); SDO1 is the accelerometer data output and SDO2 the gyroscope one, both high-Z while deselected, so\n'
           'they share SENS_MISO (the symbol is Sensor_Motion:BMI088 with SDO2 retyped passive so ERC accepts that). INT1 = accelerometer interrupt, INT3 = gyroscope interrupt; INT2 and INT4 are unused and\n'
           'left open. VDD and VDDIO are both on V3V3_ANA; GNDA and GNDIO are the same board ground.',15,225,1.3)
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
           '9':'SD_DET','10':'GND','SH':'GND'},'Connector_Card:microSD_HC_Molex_104031-0811',refofs=(88,150))
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
    s.note('Row 2 is SERVO_5V = the 5V_IN net, i.e. the J3 input BEFORE U3 (the LM66100 ideal diode). Servo and ESC current\n'
           'therefore never crosses the board rails, V5_SYS or the OR-ing devices; it returns through the row 3 ground pins.\n'
           'Nothing on this sheet loads V3V3_SYS or USB_VBUS.',15,140,1.3)
    note='No 3-row generic connector symbol or 2.54 mm 3x08 footprint ships with this KiCad install, so the header is drawn\n'
    note+='as three stacked Conn_01x08 symbols (J12 signal, J13 SERVO_5V, J14 GND) with three 1x08 footprints. Place them on\n'
    note+='2.54 mm centres to form the usual 3x8 servo block; column n is J12 pin n / J13 pin n / J14 pin n.'
    s.note(note,15,165,1.3)
    s.note('PWM MAP\nPWM1 = GPIO2   PWM5 = GPIO10\nPWM2 = GPIO3   PWM6 = GPIO11\nPWM3 = GPIO4   PWM7 = GPIO14\nPWM4 = GPIO5   PWM8 = GPIO15',15,195,1.3)
    return s

def build():
    src=Sheet('power_sources','POWER 1 / 5 V in, USB, source isolation',2)
    src.note('5 V INPUTS ONLY: BEC/boost 4.75-5.25 V (J3), USB VBUS ~5 V (J4). NO RAW CELL INPUT ON THIS BOARD.',15,15,2)
    src.add('J3','Connector_Generic:Conn_01x02','5 V in: 2S-6S BEC or 1S BMS/boost module, 3 A',35,95,{'1':'5V_IN','2':'GND'},'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical')
    for ref,y,net in [('U3',95,'5V_IN'),('U5',145,'USB_VBUS')]:
        src.add(ref,'MARV_Power:LM66100_OR','LM66100DCKR',240,y,{'1':net,'2':'GND','3':'V5_SYS','4':None,'5':ref+'_STATUS','6':'V5_SYS'})
    for rref,uref,y in [('R15','U3',95),('R17','U5',145)]:
        src.passive(rref,'R','100k status pullup',175,y,'V5_SYS',uref+'_STATUS')
    src.note('CE tied to VOUT for reverse-current blocking (TI Fig.13).\nNatural highest-voltage OR; no guaranteed priority.\nBEC/boost tolerance and transients must stay below 5.5 V.',295,40)
    src.add('J4','Connector:USB_C_Receptacle_USB2.0_16P','USB_C_PROGRAM_POWER',55,185,{'A1':'GND','A4':'USB_VBUS','A5':'USB_CC1','A6':'USB_DP','A7':'USB_DM','A8':None,'A9':'USB_VBUS','A12':'GND','B1':'GND','B4':'USB_VBUS','B5':'USB_CC2','B6':'USB_DP','B7':'USB_DM','B8':None,'B9':'USB_VBUS','B12':'GND','S1':'GND'},'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12')
    src.passive('R4','R','5.1k / 1%',120,165,'USB_CC1','GND')
    src.passive('R5','R','5.1k / 1%',120,210,'USB_CC2','GND')
    src.passive('C7','C','1u / 10 V',25,255,'USB_VBUS','GND')
    src.note('USB_VBUS feeds U5 directly; no inrush/current limiting on this sheet.\nData ESD protection is on POWER 2. No servo rail connection.',265,245)

    out=Sheet('power_3v3','POWER 2 / 3.3 V system buck and analog LDO',3)
    out.note('AVIONICS ONLY: 300 mA continuous / 500 mA short peak, provisional. NO SERVO POWER.',15,15,2)
    out.add('U7','Regulator_Switching:TPS62913','TPS62913RPUR',95,70,{'1':'V5_SYS','2':'U7_SW','3':'U7_VO','4':'GND','5':'PWR_GOOD','6':'V5_SYS','7':'GND','8':'U7_SS','9':'U7_FB','10':'U7_SCONF'})
    out.passive('L2','L','2.2u / Isat 7 A, DCR 13.5 mOhm (Coilcraft XGL4030-222MEC or equiv)',175,50,'U7_SW','U7_VO',foot='Inductor_SMD:L_Coilcraft_XxL4030')
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
    out.add('U12','Regulator_Linear:TPS7A20xxxDBV','TPS7A2033PDBVR',95,200,{'1':'V5_SYS','2':'GND','3':'V5_SYS','4':None,'5':'V3V3_ANA'})
    out.passive('C25','C','1u / 10 V X7R, LDO input',55,195,'V5_SYS','GND')
    out.passive('C26','C','1u / 10 V X7R, LDO output, ESR <=100 mOhm',150,195,'V3V3_ANA','GND')
    out.note('3V3_ANA feeds BMI088, BMP581, ADXL375, RP2354 ADC_AVDD and VREG_AVDD (100 nF at each pin on the MCU sheet).',15,240,1.3)
    out.add('U8','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',245,220,{'1':'USB_DP','2':'GND','3':'USB_DM','4':'USB_DM_MCU','5':'USB_VBUS','6':'USB_DP_MCU'})
    src.passive('C16','C','100n / 16 V',135,95,'5V_IN','GND')

    periph=Sheet('power_periph','POWER 3 / peripheral ports',4)
    periph.passive('C20','C','10u / 10 V X7R',25,45,'V3V3_SYS','GND')
    periph.add('J6','Connector_Generic:Conn_01x04','UART_GPS',95,45,{'1':'V3V3_SYS','2':'GND','3':'GPS_TX','4':'GPS_RX'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C21','C','10u / 10 V X7R',25,95,'V3V3_SYS','GND')
    periph.add('J7','Connector_Generic:Conn_01x04','UART_ELRS',95,95,{'1':'V3V3_SYS','2':'GND','3':'ELRS_TX','4':'ELRS_RX'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C22','C','10u / 10 V X7R',25,145,'V3V3_SYS','GND')
    periph.add('J9','Connector_Generic:Conn_01x04','I2C_MAG',95,145,{'1':'V3V3_SYS','2':'GND','3':'MAG_SDA','4':'MAG_SCL'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')


    mcu=mcu_sheet(); sens=sensors_sheet(); sto=storage_sheet(); act=actuators_sheet()
    sheets=[src,out,periph,mcu,sens,sto,act]
    for sheet,net,x,y,num in [(src,'GND',400,20,1),(src,'5V_IN',355,130,2),(src,'USB_VBUS',295,180,3),(src,'V5_SYS',355,180,4),
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
