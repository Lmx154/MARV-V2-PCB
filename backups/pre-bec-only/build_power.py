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

def custom_usb_switch():
    s = ['symbol', q('TPS2553DBV'), ['in_bom','yes'], ['on_board','yes'],
         ['property',q('Reference'),q('U'),['at','0','10','0'],['effects',['font',['size','1.27','1.27']]]],
         ['property',q('Value'),q('TPS2553DBV'),['at','0','8','0'],['effects',['font',['size','1.27','1.27']]]],
         ['property',q('Footprint'),q('Package_TO_SOT_SMD:SOT-23-6'),['at','0','0','0'],['effects',['font',['size','1.27','1.27']],['hide','yes']]],
         ['property',q('Datasheet'),q('https://www.ti.com/lit/ds/symlink/tps2553.pdf'),['at','0','0','0'],['effects',['font',['size','1.27','1.27']],['hide','yes']]]]
    body=['symbol',q('TPS2553DBV_0_1'),['rectangle',['start','-7.62','7.62'],['end','7.62','-7.62'],['stroke',['width','0.254'],['type','default']],['fill',['type','background']]]]
    unit=['symbol',q('TPS2553DBV_1_1')]
    for num,name,kind,x,y,a in [('1','IN','power_in',-10.16,5.08,0),('2','GND','power_in',0,-10.16,90),('3','EN','input',-10.16,0,0),('4','~{FAULT}','open_collector',10.16,-5.08,180),('5','ILIM','passive',-10.16,-5.08,0),('6','OUT','power_out',10.16,5.08,180)]:
        unit.append(['pin',kind,'line',['at',str(x),str(y),str(a)],['length','2.54'],['name',q(name),['effects',['font',['size','1.27','1.27']]]],['number',q(num),['effects',['font',['size','1.27','1.27']]]]])
    return s+[body,unit]

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
        sym=custom_usb_switch() if libid=='MARV_Power:TPS2553DBV' else symbol('Power_Management:LM66100DCK' if libid=='MARV_Power:LM66100_OR' else libid)
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
    hv=Sheet('power_hv','POWER 1 / raw 3-6S to 5 V',2)
    hv.note('RAW PACK: 9.0-25.2 V operating target. NOT a servo supply. P0 component values require review.',15,15,2)
    hv.add('J1','Connector_Generic:Conn_01x02','RAW_PACK_3-6S',35,45,{'1':'RAW_PACK','2':'GND'},'Connector_Molex:Molex_Micro-Fit_3.0_43045-0200_2x01_P3.00mm_Horizontal')
    hv.passive('F1','Fuse','1 A / >=63 V; coordinate TVS',95,45,'RAW_PACK','RAW_FUSED')
    hv.passive('D1','D_Schottky','SS110 / 100 V',165,45,'HV_IN','RAW_FUSED')
    hv.add('D2','Device:D_Zener','SMBJ26A / clamp verification',230,45,{'1':'HV_IN','2':'GND'},'Diode_SMD:D_SMB')
    hv.note('D1: low input current makes series-diode loss modest. D2/fuse are provisional, not surge qualification.',15,75)
    hv.add('U1','Regulator_Switching:LMR36510ADDA','LMR36510ADDAR',100,120,{'1':'GND','2':'HV_IN','3':'HV_IN','4':'HV_PG','5':'HV_FB','6':'HV_VCC','7':'HV_BOOT','8':'HV_SW','9':'GND'})
    hv.passive('L1','L','22uH shielded / Isat >=3 A',180,110,'HV_SW','BUCK_5V')
    hv.passive('C1','C','2.2u / 63 V X7R',35,120,'HV_IN','GND','Capacitor_SMD:C_1210_3225Metric')
    hv.passive('C2','C','220n / 100 V X7R',35,165,'HV_IN','GND')
    hv.passive('C3','C','1u / 16 V X7R',100,175,'HV_VCC','GND')
    hv.passive('C4','C','100n / 16 V X7R',180,160,'HV_BOOT','HV_SW')
    hv.passive('C5','C','22u / 16 V X7R',260,110,'BUCK_5V','GND','Capacitor_SMD:C_1206_3216Metric')
    hv.passive('C6','C','22u / 16 V X7R',330,110,'BUCK_5V','GND','Capacitor_SMD:C_1206_3216Metric')
    hv.passive('R1','R','100k / 0.1%',260,160,'BUCK_5V','HV_FB')
    hv.passive('R2','R','24.9k / 0.1%',330,160,'HV_FB','GND')
    hv.passive('R3','R','100k',260,210,'BUCK_5V','HV_PG')
    hv.add('TP1','Connector:TestPoint','HV_PG',330,210,{'1':'HV_PG'},'TestPoint:TestPoint_Pad_D1.0mm')
    hv.note('5.016 V nominal. Follow TI 22uH / 2x22uF reference. Thermal pad -> GND copper + vias.\nPlace HV section at board edge; keep SW/BOOT copper compact and away from sensors.\nF1 / D2 MPN and surge-energy coordination remain a release gate.',15,245)

    src=Sheet('power_sources','POWER 2 / USB, 1S and source isolation',3)
    src.note('LOW-VOLTAGE SOURCES: 1S 3.0-4.2 V; BEC 4.75-5.25 V ONLY. NO RAW PACK HERE.',15,15,2)
    src.add('J2','Connector_Generic:Conn_01x02','PROTECTED_1S_CELL',35,50,{'1':'CELL_IN','2':'GND'},'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical')
    src.add('J3','Connector_Generic:Conn_01x02','REGULATED_5V_BEC',35,95,{'1':'BEC_IN','2':'GND'},'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical')
    src.passive('F2','Fuse','1 A / 16 V',105,45,'CELL_IN','CELL_FUSED')
    src.passive('F3','Fuse','0.75 A / 16 V',105,95,'BEC_IN','BEC_FUSED')
    for ref,y,net in [('U2',45,'CELL_FUSED'),('U3',95,'BEC_FUSED'),('U4',145,'BUCK_5V'),('U5',195,'USB_LIMITED')]:
        src.add(ref,'MARV_Power:LM66100_OR','LM66100DCKR',240,y,{'1':net,'2':'GND','3':'VSYS','4':None,'5':ref+'_STATUS','6':'VSYS'})
    for n,y in enumerate([45,95,145,195],14):
        src.passive('R'+str(n),'R','100k status pullup',175,y,'VSYS','U'+str(n-12)+'_STATUS')
    src.note('CE tied to VOUT for reverse-current blocking (TI Fig.13).\nNatural highest-voltage OR; no guaranteed priority.\n1S requires external cell protection / cutoff. No charging.\nBEC tolerance/transients must stay below 5.5 V.',295,40)
    src.add('J4','Connector:USB_C_Receptacle_USB2.0_16P','USB_C_PROGRAM_POWER',55,185,{'A1':'GND','A4':'USB_VBUS','A5':'USB_CC1','A6':'USB_DP','A7':'USB_DM','A8':None,'A9':'USB_VBUS','A12':'GND','B1':'GND','B4':'USB_VBUS','B5':'USB_CC2','B6':'USB_DP','B7':'USB_DM','B8':None,'B9':'USB_VBUS','B12':'GND','S1':'GND'},'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12')
    src.passive('R4','R','5.1k / 1%',120,165,'USB_CC1','GND')
    src.passive('R5','R','5.1k / 1%',120,210,'USB_CC2','GND')
    src.add('U6','MARV_Power:TPS2553DBV','TPS2553DBVR',170,255,{'1':'USB_VBUS','2':'GND','3':'USB_VBUS','4':'USB_FAULT_N','5':'USB_ILIM','6':'USB_LIMITED'})
    src.passive('R6','R','232k / 1% startup',85,255,'USB_ILIM','GND')
    src.passive('C7','C','1u / 10 V',25,255,'USB_VBUS','GND')
    src.note('USB default: low-power startup only; ILIM is fault protection, not USB permission.\nHigh-current mode and data ESD are on POWER 3. No servo rail connection.',265,245)

    out=Sheet('power_3v3','POWER 3 / 3.3 V avionics and USB interface',4)
    out.note('AVIONICS ONLY: 300 mA continuous / 500 mA short peak, provisional. NO SERVO POWER.',15,15,2)
    out.add('U7','Regulator_Switching:TPS63060','TPS63060DSCR',95,70,{'1':'BB_L1','2':'VSYS','3':'VSYS','4':'BB_MODE','5':'PWR_GOOD','6':'BB_AUX','7':'GND','8':'BB_FB','9':'V3V3','10':'BB_L2','11':'GND'})
    out.passive('L2','L','1uH shielded / Isat >=4 A',175,50,'BB_L1','BB_L2')
    for ref,x in [('C8',25),('C9',25)]:
        out.passive(ref,'C','10u / 10 V X7R',x,55 if ref=='C8' else 105,'VSYS','GND')
    out.passive('C19','C','220u / 10 V polymer, ESR ~40 mOhm',25,155,'VSYS','GND','Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D')
    for ref,x in [('C10',245),('C11',310),('C12',375)]:
        out.passive(ref,'C','22u / 16 V X7R',x,50,'V3V3','GND','Capacitor_SMD:C_1206_3216Metric')
    out.passive('C13','C','100n / 16 V',95,125,'BB_AUX','GND')
    out.passive('R7','R','560k / 0.1%',245,105,'V3V3','BB_FB')
    out.passive('R8','R','100k / 0.1%',310,105,'BB_FB','GND')
    out.passive('C14','C','10p / C0G',375,105,'V3V3','BB_FB')
    out.passive('R9','R','100k default PFM',175,120,'BB_MODE','GND')
    out.passive('R10','R','100k',245,155,'V3V3','PWR_GOOD')
    out.passive('R11','R','100k',310,155,'V3V3','USB_FAULT_N')
    out.add('J5','Connector_Generic:Conn_01x08','MCU_INTERFACE_PENDING',365,200,{'1':'V3V3','2':'GND','3':'PWR_GOOD','4':'BB_MODE','5':'USB_HIGH_CURRENT','6':'USB_FAULT_N','7':'USB_DP_MCU','8':'USB_DM_MCU'},'Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
    out.add('Q1','Transistor_FET:2N7002','2N7002',165,205,{'1':'USB_HIGH_CURRENT','2':'GND','3':'USB_ILIM_LOW'})
    out.passive('R12','R','82.5k / 1%',95,190,'USB_ILIM','USB_ILIM_LOW')
    out.passive('R13','R','100k default OFF',95,240,'USB_HIGH_CURRENT','GND')
    out.add('U8','Power_Protection:USBLC6-2SC6','USBLC6-2SC6',245,220,{'1':'USB_DP','2':'GND','3':'USB_DM','4':'USB_DM_MCU','5':'USB_VBUS','6':'USB_DP_MCU'})
    out.note('USB_HIGH_CURRENT only after host configuration / valid current advertisement.\nTarget <=80mA VBUS before enumeration; <=350mA after USB 2.0 grant.\nPFM saves idle heat; drive BB_MODE high for FPWM after measuring noise/heat.\nUSB VBUS detection, supervisor, MCU and sensor decoupling remain integration work.',15,258,1.3)
    for n,net,y in [(15,'CELL_FUSED',45),(16,'BEC_FUSED',95),(17,'BUCK_5V',145),(18,'USB_LIMITED',195)]:
        src.passive('C'+str(n),'C','100n / 16 V',135,y,net,'GND')

    periph=Sheet('power_periph','POWER 4 / peripheral ports',5)
    periph.passive('C20','C','10u / 10 V X7R',25,45,'V3V3','GND')
    periph.add('J6','Connector_Generic:Conn_01x04','UART_GPS',95,45,{'1':'V3V3','2':'GND','3':'GPS_TX','4':'GPS_RX'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C21','C','10u / 10 V X7R',25,95,'V3V3','GND')
    periph.add('J7','Connector_Generic:Conn_01x04','UART_ELRS',95,95,{'1':'V3V3','2':'GND','3':'ELRS_TX','4':'ELRS_RX'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.passive('C22','C','10u / 10 V X7R',25,145,'V3V3','GND')
    periph.add('J9','Connector_Generic:Conn_01x04','I2C_MAG',95,145,{'1':'V3V3','2':'GND','3':'MAG_SDA','4':'MAG_SCL'},'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal')

    periph.add('J8','Connector_Generic:Conn_01x07','MCU_INTERFACE_PENDING_2',175,195,{'1':'GPS_TX','2':'GPS_RX','3':'ELRS_TX','4':'ELRS_RX','5':'MAG_SDA','6':'MAG_SCL','7':'GND'},'Connector_PinHeader_2.54mm:PinHeader_1x07_P2.54mm_Vertical')

    periph.note('TX/RX naming to be fixed on the MCU sheet; ports are 3.3 V logic, 3.3 V power direct from V3V3.',15,225,1.3)

    sheets=[hv,src,out,periph]
    for sheet,net,x,y,num in [(hv,'GND',20,220,1),(hv,'HV_IN',80,220,2),(src,'CELL_FUSED',295,130,3),(src,'BEC_FUSED',355,130,4),(src,'USB_VBUS',295,180,5),(hv,'BUCK_5V',160,220,6),(src,'VSYS',355,180,7)]:
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
        for libid in ['Regulator_Switching:LMR36510ADDA','Regulator_Switching:TPS63060','Power_Management:LM66100DCK','Connector:USB_C_Receptacle_USB2.0_16P','Power_Protection:USBLC6-2SC6','Transistor_FET:2N7002']:
            print(libid,[(unquote(first(p,'number')[1]),unquote(first(p,'name')[1]),p[1]) for p in pins(symbol(libid))])
    else:
        build()
