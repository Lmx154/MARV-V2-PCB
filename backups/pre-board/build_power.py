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
        CACHE[lib] = {unquote(v[1]): v for v in children(parse((LIB / (lib+'.kicad_sym')).read_text()), 'symbol')}
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
    def add(self,ref,libid,value,x,y,nets,foot=None):
        x,y=round(round(x/1.27)*1.27,5),round(round(y/1.27)*1.27,5)
        sym=symbol('Power_Management:LM66100DCK' if libid=='MARV_Power:LM66100_OR' else libid)
        if libid=='MARV_Power:LM66100_OR':
            for p in pins(sym):
                if unquote(first(p,'number')[1])=='6': p[1]='passive'
            for unit in children(sym,'symbol'):
                unit[1]=q(unquote(unit[1]).replace('LM66100DCK','LM66100_OR'))
            sym[1]=q('LM66100_OR')
        if libid not in self.libs:
            embedded=copy.deepcopy(sym); embedded[1]=q(libid)
            self.libs[libid]=embedded
        props={unquote(p[1]):unquote(p[2]) for p in children(sym,'property')}
        fp=foot if foot is not None else props.get('Footprint','')
        inst=f'(symbol (lib_id {q(libid)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {uid(ref)})'
        for key,val,xx,yy,hide in [('Reference',ref,x-7.62,y-29.21 if ref=='J4' else y-16.51,False),('Value',value,x-7.62,y-26.67 if ref=='J4' else y-13.97,False),('Footprint',fp,x,y,True),('Datasheet',props.get('Datasheet',''),x,y,True)]:
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
                    self.label(net,*end,180 if angle==0 else 0)
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
    out.add('J5','Connector_Generic:Conn_01x06','MCU_INTERFACE_PENDING',365,200,{'1':'V3V3_SYS','2':'V3V3_ANA','3':'GND','4':'PWR_GOOD','5':'USB_DP_MCU','6':'USB_DM_MCU'},'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical')
    out.add('U8','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',245,220,{'1':'USB_DP','2':'GND','3':'USB_DM','4':'USB_DM_MCU','5':'USB_VBUS','6':'USB_DP_MCU'})
    out.note('USB VBUS detection, supervisor, MCU and sensor decoupling remain integration work.',15,258,1.3)
    src.passive('C16','C','100n / 16 V',135,95,'5V_IN','GND')

    periph=Sheet('power_periph','POWER 3 / peripheral ports',4)
    periph.passive('C20','C','10u / 10 V X7R',25,45,'V3V3_SYS','GND')
    periph.add('J6','Connector_Generic:Conn_01x04','UART_GPS',95,45,{'1':'V3V3_SYS','2':'GND','3':'GPS_TX','4':'GPS_RX'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C21','C','10u / 10 V X7R',25,95,'V3V3_SYS','GND')
    periph.add('J7','Connector_Generic:Conn_01x04','UART_ELRS',95,95,{'1':'V3V3_SYS','2':'GND','3':'ELRS_TX','4':'ELRS_RX'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C22','C','10u / 10 V X7R',25,145,'V3V3_SYS','GND')
    periph.add('J9','Connector_Generic:Conn_01x04','I2C_MAG',95,145,{'1':'V3V3_SYS','2':'GND','3':'MAG_SDA','4':'MAG_SCL'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.add('J8','Connector_Generic:Conn_01x07','MCU_INTERFACE_PENDING_2',175,195,{'1':'GPS_TX','2':'GPS_RX','3':'ELRS_TX','4':'ELRS_RX','5':'MAG_SDA','6':'MAG_SCL','7':'GND'},'Connector_PinHeader_2.54mm:PinHeader_1x07_P2.54mm_Vertical')

    periph.note('TX/RX naming to be fixed on the MCU sheet; ports are 3.3 V logic, 3.3 V power direct from V3V3_SYS.',15,225,1.3)

    sheets=[src,out,periph]
    for sheet,net,x,y,num in [(src,'GND',400,20,1),(src,'5V_IN',355,130,2),(src,'USB_VBUS',295,180,3),(src,'V5_SYS',355,180,4)]:
        sheet.add('#FLG'+str(num),'power:PWR_FLAG','PWR_FLAG',x,y,{'1':net})
    root=['(kicad_sch (version 20250114) (generator "eeschema") (uuid '+uid('power-root')+') (paper "A4") (title_block (title "MARV integrated power - preliminary") (date "2026-09-14") (rev "P0 - NOT FOR FAB")) (lib_symbols)']
    root.append('(text "Integrated low-heat power draft. See DESIGN_SPEC.md.\nPower only: MCU / sensors / actuator interfaces pending.\nNo PCB placement or routing has been performed." (at 20 20 0) (effects (font (size 1.8 1.8)) (justify left top)) (uuid '+uid('root-note')+'))')
    for i,s in enumerate(sheets):
        y=55+i*38
        root.append(f'(sheet (at 25 {y}) (size 235 25) (fields_autoplaced yes) (stroke (width 0.1524) (type default)) (fill (color 0 0 0 0.0000)) (uuid {s.id}) (property "Sheetname" {q(s.title)} (at 25 {y-1} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" "{s.name}.kicad_sch" (at 25 {y+26} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "MARV-V2" (path "/{uid("power-root")}" (page "{s.page}")))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n')
    files={'MARV-V2.kicad_sch':'\n'.join(root).replace('(fields_autoplaced yes)', '(fields_autoplaced)').replace('DESIGN_SPEC.md.\nPower', 'DESIGN_SPEC.md.\\nPower').replace('pending.\nNo PCB', 'pending.\\nNo PCB')}
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
