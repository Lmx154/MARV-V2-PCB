#!/usr/bin/env python3
"""Build the whole MARV-V2 hierarchical schematic from one generator.

The schematic is ONE PAGE PER SUBSYSTEM: the root sheet is an index of sheet
blocks and each child page draws its IC in the centre-left with its own
decoupling, pull-ups, series resistors, test points and connectors placed next
to the pin they serve and WIRED to it.  Global labels carry only the nets that
leave a page (rails, shared buses, off-page GPIO), so a page reads the way a
hand-drawn schematic does.  See the LAYOUT ENGINE section for how a page is
written; nothing on a page is hand-placed text on a coarse grid any more.

This file overwrites the generated sheets, power_bom.csv, MARV_Power.kicad_sym
and reports/sheet-map.json: EDIT THE GENERATOR, NOT THE SHEETS.

Moving a symbol to a different page changes the sheet half of the
`/<sheet-uuid>/<symbol-uuid>` path every footprint in MARV-V2.kicad_pcb carries,
so after regenerating run

    python3 tools/relink_pcb_paths.py

which rewrites only those path strings (both halves are deterministic:
uid(sheet name) and uid(reference), see uid() below).  --inspect only prints pin
inventories.  No third-party Python packages.
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
# at or under 50 mm (DESIGN_SPEC "Envelope"), so every passive is the SMALLEST
# package its rating AND its supply chain allow rather than the smallest
# hand-solderable one; all of the packages below are JLCPCB assembly parts
# (1 % for R, X5R/X7R for C).  Package is derived from the value string, which
# always starts "<capacitance> / <voltage> V":
#
#   R   any value ................................. 0402
#   C   <= 4.7 uF, <= 16 V ........................ 0402
#   C   > 4.7 uF .. 22 uF, <= 16 V ................ 0603
#
# WHY 0402 AND NOT 0201 FOR THE RESISTORS: JLCPCB's Basic library starts at
# 0402 - it carries no 0201 resistor of any value, so every 0201 line is an
# Extended part with a per-unique-part setup fee, and the 0.1 % values the U7
# feedback divider needs do not exist in 0201 at all (reports/jlc-audit.md
# sections 1 and 6).  Moving the whole resistor set to 0402 makes 8 of the 13
# values Basic, removes that fee, and makes the divider buildable.  0402 is
# also hand-reworkable, which 0201 is not.
# A capacitor rated above 16 V (anything on VBAT, the bootstrap cap, the
# crystal load caps) or larger than 22 uF must pass an explicit foot= at the
# call site and keeps the larger body its voltage / DC-bias derating needs:
# C17/C46/C47 (50 V, 0402), C74/C75 (50 V, 0402), C73 (10u/50 V, 0805),
# C76/C77/C80 (22u/25 V, 0805), C66 (47u/6.3 V, 0805), C19 (100u/6.3 V
# polymer, EIA-3528 B case).  The two exceptions are enforced below by raising rather than
# guessing.
RES_PACKAGE='Resistor_SMD:R_0402_1005Metric'
CAP_PACKAGE=[(4.7e-6,'C_0402_1005Metric'),(22e-6,'C_0603_1608Metric')]
SI_MULT={'p':1e-12,'n':1e-9,'u':1e-6}
OTHER_PACKAGE={'L':'Inductor_SMD:L_6.3x6.3_H3','Fuse':'Fuse:Fuse_1206_3216Metric',
               'D_Schottky':'Diode_SMD:D_SMA','D_TVS':'Diode_SMD:D_SMB'}

def passive_footprint(kind,value):
    if kind=='R':
        return RES_PACKAGE
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

# ---------------------------------------------------------------------------
# LCSC part numbers.  tools/jlc/lcsc_map.csv is the single place a JLCPCB part
# choice lives (reports/jlc-audit.md section 5).  The generator reads it here
# and stamps the chosen C-number onto every symbol as a hidden "LCSC" property,
# so the schematic, the kicadxml netlist and therefore tools/jlc/export_jlc.py
# all carry the part number instead of re-deriving it from a value string.
#
# Two keys, checked in this order:
#   1. ref_override  - a comma-separated designator list on the map row; use it
#                      when one (spec, footprint) line must not share a part.
#   2. (spec, footprint) where spec is the Value string up to its first comma,
#                      which is the electrically meaningful part of it.
# A missing entry is NOT an error here (a part can be added to the schematic
# before it is sourced); export_jlc.py is what refuses to ship without one.
LCSC_MAP_PATH = ROOT / 'tools' / 'jlc' / 'lcsc_map.csv'
_LCSC_BY_KEY, _LCSC_BY_REF = {}, {}

def load_lcsc_map(path=None):
    import csv
    _LCSC_BY_KEY.clear(); _LCSC_BY_REF.clear()
    p = Path(path) if path else LCSC_MAP_PATH
    if not p.exists():
        return
    with p.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            spec = (row.get('spec') or '').strip()
            code = (row.get('lcsc') or '').strip()
            if not code or spec.startswith('#'):
                continue
            for r in (row.get('ref_override') or '').split(','):
                r = r.strip()
                if r:
                    _LCSC_BY_REF[r] = code
            fp = (row.get('footprint') or '').strip()
            if spec and fp:
                _LCSC_BY_KEY[(spec, fp)] = code

def lcsc_for(ref, value, footprint):
    if ref in _LCSC_BY_REF:
        return _LCSC_BY_REF[ref]
    return _LCSC_BY_KEY.get((value.split(',', 1)[0].strip(), footprint), '')

load_lcsc_map()

def patch_files(files):
    for name,content in files.items():
        path=ROOT/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content)

# (package pin, GPIO name, net or None for no-connect, function note)
MCU_GPIO=[
 ('77','GPIO0','FLASH_CS1','QMI CS1n, log flash select'),
 ('78','GPIO1','HG_ACC_INT','ADXL375 INT1'),
 ('79','GPIO2','IMU_INT2','ICM-45686 INT2/FSYNC/CLKIN'),
 ('80','GPIO3','LED_DATA','WS2812C-2020 data, 100 R series (R55)'),
 ('1','GPIO4','HG_ACC_CS','ADXL375 CS'),
 ('2','GPIO5','PWM8','PWM2 B -> J6 row 10 (S8)'),
 ('3','GPIO6','IMU_INT1','ICM-45686 INT1'),
 ('4','GPIO7','IMU_CS','ICM-45686 AP_CS'),
 ('6','GPIO8','SENS_MISO','SPI1 RX'),
 ('7','GPIO9',None,'unexposed spare - no connect'),
 ('8','GPIO10','SENS_SCK','SPI1 SCK'),
 ('9','GPIO11','SENS_MOSI','SPI1 TX'),
 ('11','GPIO12',None,'unexposed spare - no connect'),
 ('12','GPIO13','BARO_INT','BMP581 INT'),
 ('13','GPIO14','BARO_CS','BMP581 CSB'),
 ('14','GPIO15','PWM7','PWM7 B -> J6 row 9 (S7)'),
 ('16','GPIO16','ELRS_RX','UART0 TX -> radio RX'),
 ('17','GPIO17','ELRS_TX','UART0 RX <- radio TX'),
 ('18','GPIO18',None,'unexposed spare - no connect'),
 ('19','GPIO19','PWM6','PWM1 B -> J6 row 8 (S6)'),
 ('20','GPIO20','PWM5','PWM2 A -> J6 row 7 (S5)'),
 ('21','GPIO21',None,'unexposed spare - no connect'),
 ('22','GPIO22','MAG_SDA','I2C1 SDA'),
 ('23','GPIO23','MAG_SCL','I2C1 SCL'),
 ('25','GPIO24','GPS_RX','UART1 TX -> GPS RX'),
 ('26','GPIO25','GPS_TX','UART1 RX <- GPS TX'),
 ('27','GPIO26',None,'unexposed spare - no connect'),
 ('28','GPIO27',None,'unexposed spare - no connect'),
 ('36','GPIO28','SD_D0','microSD DAT0 (PIO, GPIOBASE 16 window)'),
 ('37','GPIO29','SD_D1','microSD DAT1 (PIO, GPIOBASE 16 window)'),
 ('38','GPIO30','SD_D2','microSD DAT2 (PIO, GPIOBASE 16 window)'),
 ('39','GPIO31','SD_D3','microSD DAT3 (PIO, GPIOBASE 16 window)'),
 ('40','GPIO32','ESC_TELEM_RX','ESC KISS telemetry in (PIO UART RX, window 16-47), 1k series R54'),
 ('42','GPIO33','SD_CLK','microSD CLK (PIO, GPIOBASE 16 window)'),
 ('43','GPIO34','SD_CMD','microSD CMD (PIO, GPIOBASE 16 window)'),
 ('44','GPIO35','SD_DET','microSD card detect'),
 ('45','GPIO36','PWM4','DShot via PIO (window 16-47)'),
 ('46','GPIO37',None,'unexposed spare - no connect (was PWR_SRC_ST; the mux is gone)'),
 ('47','GPIO38','PWM3','DShot via PIO (window 16-47)'),
 ('48','GPIO39','PWM2','DShot via PIO (window 16-47)'),
 ('49','GPIO40','VBUS_SENSE','ADC0, USB_VBUS 10k/15k divider'),
 ('52','GPIO41','VBAT_SENSE','ADC1, VBAT 100k/10k divider, 36.3 V FS'),
 ('53','GPIO42','CURR_SENSE','ADC2, ESC current sense, 1k + 100n'),
 ('54','GPIO43','PWM1','DShot via PIO (window 16-47)'),
 ('55','GPIO44','IO_GPIO44','ADC4 -> J6 row 11 (A44)'),
 ('56','GPIO45','IO_GPIO45','ADC5 -> J6 row 12 (A45)'),
 ('57','GPIO46','IO_GPIO46','ADC6 -> J6 row 13 (A46)'),
 ('58','GPIO47','IO_GPIO47','ADC7 -> J6 row 14 (A47)'),
]

# ---------------------------------------------------------------------------
# PRESERVED DESIGN NOTES.  These blocks are design documentation, not layout:
# they are reproduced verbatim from the pre-reorganisation generator and are
# parked in the margin of the page they belong to (see Sheet.note).
# ---------------------------------------------------------------------------
N_MCU_HDR = ('RP2354B, QFN-80, 2 MB in-package QSPI flash. Digital rails on V3V3_SYS, core DVDD from the on-chip buck.\n'
    'RAIL SPLIT: V3V3_ANA (TPS7A20 LDO) now feeds exactly one RP2354B pin - ADC_AVDD (pin 59, with C40). The core regulator input\n'
    'filter R20/C41 that produces VREG_AVDD is fed from V3V3_SYS instead, so the buck-converter reference current no longer flows out\n'
    'of the low-noise analog rail and the sensors do not share a rail with it; V3V3_ANA is left carrying only ADC_AVDD and the MEMS.\n'
    'Decoupling, core regulator, crystal and BOOTSEL follow the RP2350 hardware design guide; every pin net is a global label.')
N_XTAL = ('Crystal circuit per design guide Sec 4. Y1 IS TAXM12M4RFBCCT2T (LCSC C133337), 12 MHz, SMD 3225 4-pad, CL = 12 pF - the\n'
    'ABM8-272-T3 the earlier revision named is not orderable at JLCPCB in any form (reports/jlc-audit.md section 1).\n'
    'LOAD CAPS FOLLOW THE CRYSTAL, NOT THE OTHER WAY ROUND: CL = C46*C47/(C46+C47) + Cstray, so C46/C47 are 18 pF C0G each\n'
    '(2 x 18 pF in series = 9 pF, plus ~3 pF of XIN/XTAL_DRV pin and trace stray = 12 pF, matching CL exactly). They were\n'
    '15 pF against the old CL 10 pF part; leaving 15 pF on a CL 12 pF crystal gives 10.5 pF of load, i.e. an under-loaded\n'
    'oscillator running fast by roughly the trim sensitivity of the part. The ~3 pF stray is the design-guide estimate and is\n'
    'the one term here that is not a datasheet number - if the board is ever pulled for frequency, that is the term to measure.\n'
    '1 k in the XOUT leg to limit drive with a 50 ohm ESR crystal. C38 is the single design-guide decoupling exception (pins 68+69 share it).\n'
    'VREG_AVDD RC = 33 ohm + 4.7 uF (design guide Sec 2.1), taken from V3V3_SYS; VREG_FB is tied to DVDD, VREG_PGND to GND, EP to GND.')
N_PORTNAMES = ('PORT NAMING: a port label is named for the peripheral pin it comes from, so GPS_TX / ELRS_TX are module outputs\n'
    'and land on MCU UART RX pins, while GPS_RX / ELRS_RX are module inputs fed by the MCU UART TX pins. On the IO\n'
    'array (POWER 3) the UART rows are therefore 1 GPS_RX (silk T0) / 2 GPS_TX (R0) / 3 ELRS_RX (T1) / 4 ELRS_TX (R1),\n'
    'rows 5/6 are MAG_SDA / MAG_SCL, rows 7-10 the PWM5-8 servo signals and rows 11-14 the four exposed spares.\n'
    'The array is three stacked 1x14 rows: J6 SIGNAL, J7 POWER, J8 GND. All array SIGNAL pins are 3.3 V CMOS.\n'
    'GPIO37 (pin 46) is SPARE and unconnected again: it used to read PWR_SRC_ST, the open-drain status output of\n'
    'the U25 TPS2121 mux, and the mux is gone. USB presence is already readable on the VBUS_SENSE divider (GPIO40).')
N_J10 = ('J10 is a 3-pad SWD landing (SWCLK / SWDIO / GND), not a 10-pin Cortex header: solder pads are kept for the two\n'
    'ports that mate with something fixed - the ESC row J3 and this one (DESIGN_SPEC "Connection philosophy").\n'
    'The debugger reference 3V3 and the debugger-driven reset line\n'
    'of the old 2x05 header are both gone - power the board from the BEC or USB while debugging, and use SW1\n'
    '(MCU_RUN to GND) for reset. MCU_RUN is held up by R10 100k to V3V3_SYS, so RUN releases with the 3.3 V rail.\n'
    'THE PULL-UP IS NOW A PLAIN RESISTOR, not a regulator power-good output: the AP63203 has no PG pin, so the\n'
    'explicit "RUN cannot release before V3V3_SYS is in regulation" sequencing of the TPS62913 is gone. The\n'
    'RP2350 brown-out detector (always on, 8 threshold steps, design guide Sec 2.2) is what covers it instead.')
N_SPAREIO = ('SPARE IO. EXPOSED (IO array J6 signal column, POWER 3): GPIO44 row 11 (A44) | GPIO45 row 12 (A45) |\n'
    'GPIO46 row 13 (A46) | GPIO47 row 14 (A47). All four are ADC4-ADC7, which is why the silk labels are\n'
    'A44-A47 rather than IOnn; each sits next to a V3V3_SYS pin (J7) and a GND pin (J8) in the same row.\n'
    'UNEXPOSED, NO-CONNECT: GPIO9, GPIO12, GPIO18, GPIO21, GPIO26, GPIO27 carry a no-connect flag on this\n'
    'sheet - the 14-row array has no room for them once GPS/ELRS/I2C1/PWM5-8 and the four ADC spares are\n'
    'placed. They are left unconnected deliberately; exposing one means editing PINOUT.md, this generator\n'
    'and tools/check_power_netlist.py together. GPIO budget: 38 on board functions and ports, 4 spare on\n'
    'the array, 6 unconnected; none floats without a no-connect flag.')
N_MECH = ('MECHANICAL: H1-H4 are the four 4.0 mm grommet holes\n'
    'on the standard 30.5 x 30.5 mm pattern, off-centre in X,\n'
    'each now a PLATED hole with a 6.4 mm GND pad ring stitched\n'
    'by eight 0.6/0.3 mm vias, and a 6.5 mm top-side courtyard\n'
    'for the grommet flange. Pin 1 of every hole is GND, so the\n'
    'frame screws bond to the ground plane on every layer.\n'
    'See DESIGN_SPEC "Mounting and orientation".')
N_ANALOG = ('TELEMETRY AND ANALOG INPUTS (100 nF at each ADC pin).\n'
    'VBAT_SENSE: R27/R28 100k/10k scale VBAT by 1/11, so the 3.3 V ADC full scale is 36.3 V. A 6S pack at its\n'
    '25.2 V maximum reads 2.29 V and a 2S pack at 6.0 V reads 0.55 V, so the whole 2-6S window is on-scale with\n'
    'headroom; the divider draws 229 uA at 25.2 V. The old 5V_IN divider is gone with the 5 V input itself.\n'
    'CURR_SENSE: the ESC current-sense output (J3 pin 1, 12.75 mV/A, 0-3.3 V) through R53 1k into C78 100 nF at\n'
    'the pin - a 100 us RC anti-alias/ESD network, well under the RP2350 ADC source-impedance guidance.\n'
    'ESC_TELEM: the ESC KISS telemetry output (J3 pin 2, 3.3 V, 115200 baud, one-wire from the ESC) through R54\n'
    '1k into GPIO32, read by a PIO UART (GPIOBASE 16 window). The resistor is series protection only, not a level\n'
    'shifter: the ESC pad row is 3.3 V CMOS on both the telemetry and the four motor lines.\n'
    'VBUS_SENSE keeps 10k/15k, now on GPIO40 (ADC0); VBAT_SENSE moved to GPIO41 (ADC1).\n'
    'D20 WS2812C-2020: VDD on V5_SYS with C79 100 nF, DIN from GPIO3 through R55 100 R, DOUT no-connect (single\n'
    'pixel). Its DIN VIH minimum is 2.7 V (datasheet Electrical Characteristics), which 3.3 V CMOS clears - that\n'
    'is why the C variant is used rather than a 5050 WS2812B, whose VIH is 0.7 x VDD = 3.5 V.\n'
    'QSPI_* are the dedicated QSPI pads: they reach the in-package flash die AND the package pins\n'
    '(RP2350 datasheet Sec 14.3), so U24 shares the bus with GPIO0/QMI CS1n (FLASH_CS1) as its select.\n'
    'RP2354 requires QSPI_IOVDD = 3.3 V, and IOVDD = 3.3 V to run a second QSPI device (Sec 14.9).')
N_SENS_HDR = ('All three sensors run 4-wire SPI on the shared SENS_SCK / SENS_MOSI / SENS_MISO bus with one chip select each,\n'
    'and are powered from V3V3_ANA (TPS7A20 LDO). Every supply pin on this sheet gets 100 nF + 1 uF: BMP581 and\n'
    'ADXL375 because their own datasheets call for the pair, the ICM-45686 as a deliberate addition - its\n'
    'datasheet BOM (DS-000577 Rev 1.0 Table 11) lists 0.1 uF only.')
N_TESTPOINTS = ('TEST POINTS TP1-TP10 (TestPoint:TestPoint_Pad_1.0x1.0mm, 1 x 1 mm bare F.Cu pad, no 3D model by design -\n'
    'tools/audit_footprints.py --no-3d-ok covers ^TestPoint_ along with the pad rows and mounting holes).\n'
    'TP1 SENS_SCK | TP2 SENS_MOSI | TP3 SENS_MISO | TP4 IMU_CS | TP5 BARO_CS | TP6 HG_ACC_CS | TP7 IMU_INT1 |\n'
    'TP8 IMU_INT2 | TP9 BARO_INT | TP10 HG_ACC_INT. Placement: inside the sensor cluster, within 6 mm of\n'
    'U21/U22/U23 (tools/setup_pcb.py checks it). They add ten stubs to the SPI bus, which is why they are 1 mm\n'
    'pads next to the parts rather than a header somewhere else: at 10 MHz SCK a short stub is a capacitive load,\n'
    'a long one is a transmission line. No series resistors and no ground pad of their own - probe ground comes\n'
    'off a mounting hole or the J6 array.')
N_CSPULLUP = ('R48, R50, R51: 10k pull-ups to V3V3_ANA on the three SPI chip selects (IMU_CS, BARO_CS, HG_ACC_CS). R49\n'
    '(the former second IMU chip-select pull-up) is removed along with that net - the ICM-45686 has a single\n'
    'chip select. Same rationale as R35 on FLASH_CS1 (BOARD 3): every sensor is held deselected before the RP2354B\n'
    'drives the pin, so a GPIO left floating through reset, BOOTSEL or a debugger halt cannot open a\n'
    'transaction on the shared SENS_SCK / SENS_MOSI / SENS_MISO bus. They bias to V3V3_ANA, the same rail as\n'
    'every VDDIO pin on this sheet, so there is no pull-up current path into an unpowered I/O supply and no CS\n'
    'pin is pulled above its own VDDIO during rail sequencing.')
N_U21 = ('U21 ICM-45686 (TDK InvenSense DS-000577 Rev 1.0, Table 10 "Signal Descriptions" / Figure 4 pin-out, Single\n'
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
    'with U22/U23 and common flight-controller practice.')
N_U22U23 = ('U22 BMP581: CSB = BARO_CS, SDI = SENS_MOSI, SDO = SENS_MISO, SCK = SENS_SCK, INT = BARO_INT. VDDIO and VDD on\n'
    'V3V3_ANA, all three VSS pins to GND.\n'
    'U23 ADXL375: CS = HG_ACC_CS, SDA/SDI = SENS_MOSI, SDO = SENS_MISO, SCL/SCLK = SENS_SCK, INT1 = HG_ACC_INT.\n'
    'Per the pin function table, pin 3 (RESERVED) goes to VS and pin 11 (RESERVED) to GND; pin 10 (NC) and the unused\n'
    'INT2 are left open. VS and VDD I/O are both on V3V3_ANA.')
N_STOR_HDR = ('An OPTIONAL QSPI expansion socket on the shared QSPI bus with GPIO0/QMI CS1n as its chip select, and a\n'
    'latched microSD wired for 4-bit PIO (also SPI-compatible). Both on V3V3_SYS with local bulk, per the rail\n'
    'split in DESIGN_SPEC.\n'
    'U24, C62 AND C63 ARE DNP - NOT FITTED BY DEFAULT AND NOT IN THE BOM. The land is on the BACK of the board\n'
    '(B.Cu) as a user expansion: firmware and logs use the RP2354B in-package 2 MB flash and the J11 microSD.\n'
    'U24 IS A SOCKET, NOT ONE PART: the 150-mil SOIC-8 land takes either a W25Q32JVSNIQ NOR flash or an\n'
    'APS6404L-SQN-SN 8 MB QSPI PSRAM - see the U24 note below. FIT ONE PART ONLY. R35 stays POPULATED.')
N_U24 = ('U24 shares the dedicated QSPI pads with the RP2354B in-package flash die (datasheet Sec 14.3): CLK = QSPI_SCLK,\n'
    'DI/IO0 = QSPI_SD0, DO/IO1 = QSPI_SD1, WP/IO2 = QSPI_SD2, HOLD/IO3 = QSPI_SD3. Only the chip select differs -\n'
    'FLASH_CS1 comes from GPIO0 (QMI CS1n), pulled up to V3V3_SYS by R35 so the part is deselected before the MCU\n'
    'drives it. QSPI_SS (the internal die) keeps its own strap on the MCU sheet.\n'
    'U24 SOCKET - OPTIONAL PSRAM OR SECOND FLASH. FIT ONE PART ONLY: this is one land, not two positions.\n'
    'The land is Package_SO:SOIC-8_3.9x4.9mm_P1.27mm, i.e. 150 mil / 3.9 mm SOIC-8 body. THE DEFAULT FIT IS\n'
    'W25Q32JVSNIQ (Winbond, 32 Mbit = 4 MB NOR flash, LCSC C5355146) or, for PSRAM, APS6404L-SQN-SN (AP Memory,\n'
    '64 Mbit = 8 MB QSPI pseudo-SRAM, LCSC C5360304). THE 64 Mbit W25Q64JVSSIQ THE EARLIER REVISION NAMED DOES NOT\n'
    'FIT THIS LAND: Winbond package code SS is SOIC-8 208 mil (5.28 mm body), and the 150 mil member of that family\n'
    'is the SN suffix, W25Q64JVSNIQ, which is not stocked at JLCPCB. See DESIGN_SPEC "Back side" for the verified\n'
    'compatible-parts list - every entry there is package-checked, and package codes in this family are NOT\n'
    'interchangeable by capacity. The two default parts are pin-identical on\n'
    'this bus: 1 CE#/CS#, 2 SO/SIO1, 3 SIO2 (WP# on the flash), 4 VSS/GND, 5 SI/SIO0, 6 SCLK, 7 SIO3 (HOLD# on the\n'
    'flash), 8 VCC - so no board change is needed to swap them. The RP2350 QMI supports a PSRAM on CS1 with its own\n'
    'timing/chip-select registers (RP2350 datasheet Sec 12.14 QMI, M1_TIMING/M1_RFMT/M1_WFMT), which is what makes\n'
    'the alternative real rather than mechanical. Fit the flash for log space or the PSRAM for\n'
    'XIP-addressable RAM - neither is fitted at build.\n'
    'DNP / BACK SIDE. U24, C62 and C63 carry (dnp yes) + (in_bom no): the land pattern, the nets and R35 are on\n'
    'the board, the parts are not bought and not placed. The socket and its two bypass caps sit on B.Cu under\n'
    'the MCU, against U20 QSPI pads 70-75, so the QSPI stubs are the board thickness plus a via; the front stays\n'
    'a single-sided assembly because nothing DNP is reflowed. A B.SilkS legend beside the land says what fits.\n'
    'CONSEQUENCE FOR THE BUDGET: the 25 mA QSPI-flash burst is NOT in the V3V3_SYS load budget any more\n'
    '(DESIGN_SPEC "Rails and load budget"); add it back if the socket is populated.\n'
    'SYMBOL: U24 uses Memory_Flash:W25Q32JVSS, which is now the exact symbol for the default fit as well as being\n'
    'pinout-identical across the whole W25Q JV family and to the APS6404L PSRAM on this bus; the Value field\n'
    'carries the real MPN. See LIBRARIES.md.')
N_J11 = ('J11: DET_A to GND and DET_B to SD_DET with a 10k pull-up, so the input reads low with a card inserted. The\n'
    'shield goes to GND. 100 nF + 10 uF + 47 uF sit at the socket (DESIGN_SPEC "Rails": SD transients stay on the\n'
    'buck rail). 10k pull-ups on CMD and DAT0-DAT3 are the SD-standard idle bias and also keep DAT3/CD high for\n'
    '4-bit mode. VDD = V3V3_SYS.')
N_SRC_HDR = ('BOARD INPUTS: REGULATED 5 V FROM AN EXTERNAL BEC on the ESC pad row J3 pin 7 (5V_IN), and USB VBUS ~5 V (J4).\n'
    'There is no on-board pack buck any more (DESIGN_SPEC "Decisions", 2026-09-17): raw pack reaches this board only as\n'
    'the J3 pin 9 SENSE wire VBAT, which drives the R27/R28/C48 divider and nothing else - no load, no bulk, no copper zone.\n'
    '5V_IN is the servo / GPS / ELRS bus (IO block rows 1-4 and 7-10) and the drain of the Q1 OR-ing FET on POWER 2.')
N_OR = ('5 V OR - Q1 P-CHANNEL FET + D1 SCHOTTKY, NOT A MUX (DESIGN_SPEC "Decisions"). 5V_IN (external BEC) and USB_VBUS\n'
    'both reach V5_SYS, and V5_SYS feeds only the two 3.3 V regulators and the status LED.\n'
    'Q1 AO3401A (AOS, SOT-23, LCSC C15127, JLC BASIC): VDS -30 V, ID -4.0 A, RDS(on) 60 mOhm max at VGS = -4.5 V /\n'
    '85 mOhm max at -2.5 V, VGS(th) -0.45 to -1.0 V. DRAIN on 5V_IN, SOURCE on V5_SYS, GATE on USB_VBUS with R7 100k to GND.\n'
    'The intrinsic body diode of a P-channel FET points DRAIN -> SOURCE, i.e. 5V_IN -> V5_SYS, which is the direction the\n'
    'load is in - so the BEC always gets through even before the channel is enhanced.\n'
    'NO USB: R7 (helped by the R29/R30 VBUS_SENSE divider, 25k to GND) holds the gate at 0 V, so VGS = -V5_SYS ~ -5 V and\n'
    'the channel is hard on; the BEC carries both regulators through <= 60 mOhm.\n'
    'USB PRESENT: the gate sits at VBUS, so VGS = VBUS - V5_SYS >= 0 and the channel is OFF. That is the one guarantee this\n'
    'OR has to make - the host can never back-feed the BEC, the servo rows or the ESC.\n'
    'D1 1N5819WS (SOD-323, LCSC C191023, JLC BASIC): ANODE USB_VBUS, CATHODE V5_SYS. 40 V / 1 A Schottky, VF ~0.45 V at the\n'
    '~250 mA V5_SYS draws on USB, so V5_SYS is ~4.4-4.6 V from a 5 V host - above the AP63203 3.8 V minimum input with margin -\n'
    'and the diode blocks the reverse direction that Q1 no longer has to.\n'
    'BOTH PRESENT: the BEC wins whenever 5V_IN - IxRDS(on) exceeds VBUS - VF, which at these currents it always does; Q1 is\n'
    'held off in that state, so nothing flows back into the host either way.\n'
    'WHAT IS GIVEN UP against the TPS2121 this replaces: no priority comparator, no input over-voltage lockout, no current\n'
    'limit, no soft-start, no open-drain status pin (GPIO37 is a plain spare again) and no seamless make-before-break -\n'
    'the crossover is a diode, not a 100 us controlled switchover. TWO JLC BASIC PARTS INSTEAD OF ONE EXTENDED IC PLUS SIX\n'
    'RESISTORS AND THREE CAPACITORS, and no 5 V path exists that USB can drive backwards.\n'
    'C19 (100 uF polymer) IS ON 5V_IN AT THE PAD ROW, NOT ON V5_SYS: the hold-up belongs where the servo/module rows are,\n'
    'which is ahead of the OR. V5_SYS carries only C8/C9 at the AP63203 input.')
N_J3 = ('ESC PAD ROW J3 (MicoAir AM32 4-in-1 ESC, FC-connection row), NINE PADS. Pads 1-6 are the ESC silkscreen read\n'
    'left to right; pads 7-9 are this board\'s power entry, added when the on-board pack buck was removed:\n'
    '1 CURR - analog current sense from the ESC, 12.75 mV/A, 0-3.3 V -> R53/C78 -> GPIO42 (ADC2) on BOARD 1.\n'
    '2 TX   - KISS ESC telemetry, 3.3 V, 115200 baud, ESC output only -> R54 -> GPIO32 (PIO UART RX, GPIOBASE 16 window).\n'
    '3-6 M4 M3 M2 M1 - 3.3 V DShot/PWM inputs via PIO (GPIOBASE 16 window), straight from the RP2354B (PWM4..PWM1 = GPIO36, 38, 39, 43).\n'
    '7 5V   - REGULATED 5 V IN from an external BEC wired between the ESC\'s VBAT pad and this pad. It is the ONLY\n'
    '         power input besides USB, and it is the servo / GPS / ELRS bus: C19 100 uF polymer sits on it here.\n'
    '8 GND.\n'
    '9 VBAT - raw pack, 6-25.2 V (2-6S), SENSE ONLY: it reaches the R27/R28/C48 divider (GPIO41, ADC1) and nothing\n'
    '         else. No load, no bulk capacitance, no copper zone - a 100k top leg is the entire circuit on it.\n'
    'PITCH IS AN ASSUMPTION: MicoAir publishes no pad drawing, so MARV_Packages:PadRow_1x09_P2.00mm assumes\n'
    '2.00 mm. The ORDER is authoritative; confirm the pitch against the physical ESC before fab.\n'
    'THE BEC IS OFF-BOARD AND IS NOT OPTIONAL: the AM32 ESC has none, so a 2-6S BEC module (or a 1S boost) has to be\n'
    'wired from the pack to pad 7. Its output capacitance, its inrush and its transient behaviour are outside this\n'
    'board; what the board provides on 5V_IN is C19 100 uF polymer plus the IO-block bulk C20/C21.\n'
    'THERE IS NO TVS AND NO REVERSE PROTECTION ON PAD 7 OR PAD 9, by design: pad 9 carries no current, and a 5 V pad\n'
    'that a user can mis-wire to the pack is a build error the board does not try to survive.')
N_U7 = ('U7 AP63203WU-7, V5_SYS -> V3V3_SYS BUCK (Diodes DS41326 Rev. 3-2). 3.8-32 V in, FIXED 3.3 V out, 2 A,\n'
    '1.1 MHz with +/-6% frequency spread spectrum, 4 ms internal soft-start, 22 uA quiescent, TSOT26.\n'
    'It replaces the TPS62913 two-stage stage (U7 + L2 + FB1 + a 0.1 % divider + five 22 uF) at ~8 parts instead of ~25.\n'
    'PASSIVES ARE TABLE 2 "Recommended Component Selections for AP63203" (3.3 V row) and Figure 21, the AP63203/AP63205\n'
    'typical application, with one documented substitution:\n'
    '  L  3.9 uH in Table 2  -> 4.7 uH (L2). Sec 10 "Inductor" licenses it explicitly: "it is recommended to select an\n'
    '     inductor of approximately 2.2uH to 10uH with a DC current rating of at least 35% higher than the maximum load\n'
    '     current... Use a larger inductance for improved efficiency under light load conditions", and this rail is a\n'
    '     light load (~180 mA typical / ~300 mA peak). 4.7 uH is a part the board already sources.\n'
    '  C1 10 uF   -> C8, 10 uF / 25 V X5R 0603, at VIN.  C9 100 nF 0402 is an HF bypass beyond the datasheet, the same\n'
    '     addition the removed AP63205 stage carried as C74.\n'
    '  C2 2 x 22 uF -> C10 / C11, 22 uF / 10 V X5R 0603 (GRM188R61A226ME15) at the output, exactly the table value.\n'
    '  C3 100 nF  -> C13, bootstrap BST-SW.\n'
    'FB (pin 1) is a SENSE input on the fixed-output parts and goes straight to V3V3_SYS - Sec 9 "Setting the Output\n'
    'Voltage": only the adjustable AP63200/AP63201 take a divider (Eq.6). So there is no feedback divider, no 0.1 %\n'
    'resistor pair and no setpoint arithmetic on this board any more: VOUT is the part number.\n'
    'EN (pin 2): "The EN pin is a high voltage pin and can be directly connected to VIN", abs max 35 V, threshold\n'
    '1.18 V rising / 1.10 V falling, internal 1.5 uA pull-up. R52 100k from V5_SYS is that connection with a series\n'
    'element, so a UVLO divider (Eq.1/Eq.2) or a start-delay cap (Eq.3) can be added later without touching copper.\n'
    'OPERATING POINT at VIN = 5.0 V, VOUT = 3.3 V, fsw = 1.1 MHz, Eq.7: dIL = 3.3 x 1.7 / (5.0 x 4.7u x 1.1M) = 0.22 A\n'
    'pk-pk (0.27 A at the -20% inductance limit), so Eq.8 gives a 0.41 A inductor peak at the 0.3 A peak rail load.\n'
    'On USB, VIN falls to ~4.5 V behind D1 and dIL drops to 0.17 A; the part stays in CCM-adjacent light-load operation\n'
    'either way and neither case comes near the 2 A rating or the inductor.\n'
    'DERATING CAVEAT: C8 and C10/C11 are the datasheet NOMINAL values and ceramic DC-bias derating is not in them -\n'
    'a 22 uF / 10 V 0603 at 3.3 V keeps roughly 60 %, so the 44 uF of COUT is ~26 uF effective. That is still above\n'
    'the 2 x 22 uF the table asks for in nominal terms and is the same derating the removed stage carried.\n'
    'L2: CJIANG FTC404030S4R7MGCA (LCSC C39676083), the inductor the removed AP63205 stage used as L3 - 4.7 uH +/-20%,\n'
    'DCR 41 mOhm typ / 46 max, Irms 4.3 A typ / 4.0 A worst case, Isat 7.0 A typ / 6.0 A worst case, 4.1 x 4.1 x 3.0 mm\n'
    'molded metal-composite, shielded (SZ CJIANG FTC series datasheet Rev 7.0 2025/11/05, Notes 3/4/7: the usable rating\n'
    'is the LESSER of Irms and Isat, so 4.0 A). At a 0.41 A peak that is a 10x margin - enormously over-rated for this\n'
    'rail, and deliberately so: it is a part already on the BOM and on the reel, and it costs 46 mOhm x 0.3 A^2 = 4 mW.\n'
    'IF THE 4 x 4 x 3.0 mm FOOTPRINT EVER HAS TO SHRINK, the FTC303020D family (3 x 3 x 2.0, LCSC C7423318 at 2.2 uH) is\n'
    'the same library footprint family and 2.2 uH is still inside the datasheet\'s 2.2-10 uH window - at 0.47 A pk-pk ripple.')
N_VBUS_IN2 = ('USB_VBUS feeds the D1 Schottky and the Q1 gate on POWER 2 directly; no inrush or current limiting on this\n'
    'sheet, and no data ESD array any more - U8 USBLC6-2SC6 was JLC Extended and is removed (DESIGN_SPEC "Decisions"),\n'
    'so D+/D- go straight from J4 into the 27 R series pair R22/R23, as on the madflight FC3v2. The RP2354B USB pins\n'
    'carry their own on-die ESD structures; a board-level array is what this design gives up, deliberately.')
N_3V3_HDR = ('AVIONICS ONLY: 300 mA continuous / 500 mA short peak, provisional. NO SERVO POWER.')
N_PKG = ('PASSIVE PACKAGES (DESIGN_SPEC "Physical design"): resistors are 0402, ceramics <= 4.7 uF are 0402 and the\n'
    '10-22 uF ceramics are 0603. RESISTORS ARE 0402, NOT 0201: JLCPCB has no Basic 0201 resistor of any value, so\n'
    'every 0201 line carried a per-unique-part Extended setup fee - see reports/jlc-audit.md. 0402 makes most of the\n'
    'resistor values Basic and is hand-reworkable, which 0201 is not. THE 0.1 % PAIR IS GONE with the TPS62913: the\n'
    'AP63203 is a fixed-output part and has no feedback divider, so no 0.1 % thin-film line is ordered at all.\n'
    'C10/C11 (AP63203 COUT) are 22 uF / 10 V X5R 0603 (GRM188R61A226ME15): at 3.3 V DC bias an X5R 22 uF 0603 keeps\n'
    'roughly 60 % of its nominal value, so the 44 uF nominal is ~26 uF effective. Do not read the effective value\n'
    'off the BOM. The 22 uF 0603 ceramics remain machine-place parts - JLC assembles them, a bench iron will not\n'
    'rework one.\n'
    'C19, THE 5V_IN BULK, IS 100 uF / 6.3 V POLYMER IN AN EIA-3528-21 (B) CASE. It moved from V5_SYS to 5V_IN with the\n'
    'BEC decision: hold-up belongs on the rail the servo and module rows are on, which is now ahead of the OR-ing FET,\n'
    'and V5_SYS keeps only C8/C9 at the AP63203 input. ESR must stay <= 40 mOhm: Panasonic 6TPE100MAZB or a KEMET\n'
    'T520/T530 B case. 6.3 V on a 5.0 V rail is a 1.26x derating, the normal polymer figure; a tantalum electrolytic\n'
    'would need 2x and would not qualify.\n'
    'THE ngspice DECKS IN simulations/ STILL MODEL THE OLD TOPOLOGY (a TPS2121 mux fed by an on-board pack buck, and a\n'
    'TPS62913-class 3.3 V stage). They were not re-derived for the BEC + P-FET + AP63203 tree, so every number they\n'
    'produce is now history, not evidence - see DESIGN_SPEC "Open items".')
N_ANA = ('3V3_ANA feeds ICM-45686, BMP581, ADXL375 and the RP2354B ADC_AVDD pin (100 nF at each pin on the MCU sheet); VREG_AVDD is filtered\n'
    'from V3V3_SYS instead, so the analog rail carries no core-regulator current. U12 EN (pin 3) is tied to V3V3_SYS itself:\n'
    'the AP63203 has no power-good output, so the sequencing is done by the rail rather than by a status pin - the LDO enables\n'
    'when the buck output is up and drops with it, which is the same buck-before-LDO ordering PWR_GOOD used to give, at no parts.\n'
    'What is lost is the "in regulation" qualifier: EN now releases at U12\'s own ~0.9 V enable threshold on a rising V3V3_SYS,\n'
    'not at the point a comparator declares the buck settled. For a 10-20 mA sensor rail behind a 4 ms soft-start that is a\n'
    'few hundred microseconds of difference, and the sensors are held in reset by firmware for far longer than that.')
N_IO_HDR = ('IO ARRAY - ONE 3-COLUMN x 14-ROW THROUGH-HOLE BLOCK ON THE RIGHT EDGE, 2.54 mm, madflight FC3v2 style.\n'
    'It replaces the old 2x16 left-edge array AND the J12/J13/J14 servo block: every signal that leaves this board\n'
    'except the ESC row (J3) and the SWD pads (J10) now leaves on this one block.\n'
    'COLUMN RULE, from the board edge inward: GND (J8) | POWER (J7) | SIGNAL (J6). The SIGNAL column is the INNERMOST\n'
    'one, next to the MCU, so the 14 signal traces are the short ones; the two rails run down the outside where a\n'
    'plane stitch is cheap. A 3-wire module lead (signal, power, ground) plugs straight across ONE row.\n'
    'THREE Conn_01x14 SYMBOLS, not one 3x14: no 3-row generic connector symbol ships with this KiCad install, and\n'
    'three 1x14 rows with a body-trimmed courtyard abut exactly on the 2.54 mm grid (see tools/setup_pcb.py).\n'
    'DS-009 NAMING IS KEPT: a port label is named for the PERIPHERAL pin it belongs to, so GPS_RX / ELRS_RX are module\n'
    'inputs driven by the RP2354B UART TX pins (rows 1 and 3, silk T0 / T1) and GPS_TX / ELRS_TX are module outputs\n'
    'that land on the MCU UART RX pins (rows 2 and 4, silk R0 / R1).')
N_IOBULK = ('C20 / C21: 5V_IN local bulk at the array (rows 1-4 GPS/ELRS and rows 7-10 servo, the 5 V supply rows).\nC22: V3V3_SYS local bulk at the array (rows 5-6 and 11-14).')
N_IORAILS = ('RAILS ON THE ARRAY: rows 1-4 (GPS, ELRS) and rows 7-10 (servos S5-S8) take 5V_IN; rows 5-6 (magnetometer)\n'
    'and rows 11-14 (the four exposed spares) take V3V3_SYS. Every row has its own GND pin in the J8 column, so a\n'
    'signal return is never more than 2.54 mm away and no row can be mis-plugged into a neighbour\'s ground.\n'
    'THE EIGHT 5 V ROWS ARE ON 5V_IN, AHEAD OF THE OR-ING FET (DESIGN_SPEC "Decisions", 2026-09-17). 5V_IN is the\n'
    'external BEC on J3 pin 7, so servo and module current goes from the BEC straight to the rows and never crosses\n'
    'Q1: the FET carries only the two 3.3 V regulators and the status LED, and a USB host never sees the servo rows\n'
    'at all. The rows are therefore NOT powered from USB - plugging in USB alone leaves every module and servo dead,\n'
    'which is the intended bench behaviour and the reverse of the previous revision.\n'
    'CURRENT: rows 1-4 and 7-10 count against the external BEC only; rows 5-6 and 11-14 count in the V3V3_SYS budget.\n'
    'No fuse and no per-row current limit: the array is a system-integration connector, not a protected port.')
N_PWMMAP = ('PWM MAP\nPWM5 = GPIO20 (row 7, S5)\nPWM6 = GPIO19 (row 8, S6)\nPWM7 = GPIO15 (row 9, S7)\nPWM8 = GPIO5 (row 10, S8)\n\n'
    'ON THE ESC PAD ROW (J3, POWER 1)\nPWM1 = GPIO43\nPWM2 = GPIO39\nPWM3 = GPIO38\nPWM4 = GPIO36')


# ---------------------------------------------------------------------------
# LAYOUT ENGINE
#
# The pre-2026-09-16 generator had none: every sheet hardcoded (x, y) on a
# coarse grid and Sheet.add() stamped a GLOBAL LABEL on EVERY pin, so no two
# parts were ever joined by a wire and a page was a field of unrelated symbols.
# This engine places a part, hands back the SCREEN coordinate and the outward
# direction of each of its pins, and lets the page builder draw real wires
# between them.  Global labels are then only used for nets that leave the page.
#
# Coordinate conventions (verified against kicad-cli, not assumed):
#   * a symbol library point (lx, ly) lands on the sheet at (x,y) + M(XF[rot]),
#     where XF is the rotation below and M negates screen x for (mirror y) or
#     screen y for (mirror x).  The mirror is applied AFTER the rotation.
#   * a pin's outward direction (the side a wire leaves on) is the same map
#     applied to the lib-space vector PINDIR[pin angle].
#   * the sheet Y axis points DOWN, which is why XF[0] negates ly.
# ---------------------------------------------------------------------------
GRID = 1.27
PAPER = {'A4': (297.0, 210.0), 'A3': (420.0, 297.0)}
XF = {0: lambda x, y: (x, -y), 90: lambda x, y: (-y, -x),
      180: lambda x, y: (-x, y), 270: lambda x, y: (y, x)}
MF = {None: lambda x, y: (x, y), 'y': lambda x, y: (-x, y), 'x': lambda x, y: (x, -y)}
PINDIR = {0: (-1.0, 0.0), 90: (0.0, -1.0), 180: (1.0, 0.0), 270: (0.0, 1.0)}
LEFT, RIGHT, UP, DOWN = (-1, 0), (1, 0), (0, -1), (0, 1)
LABANG = {LEFT: 180, RIGHT: 0, UP: 90, DOWN: 270}
# Stroke-font metrics, measured off an SVG export of a known string: a glyph
# advance is 0.852 x the font size and the line pitch is 1.61 x it.  CHARW is
# rounded up so a reserved text box is never smaller than the text in it.
CHARW, LINEH = 0.90, 1.62
VERT = 0         # rot for a 2-pin passive drawn vertically (pin 1 at the top)
HORZ = 90        # rot for a 2-pin passive drawn horizontally (pin 1 on the left)


def snap(v):
    return round(round(v / GRID) * GRID, 4)


def xform(rot, mirror):
    f, m = XF[rot], MF[mirror]
    return lambda lx, ly: m(*f(lx, ly))


def sym_geom(sym, x, y, rot=0, mirror=None):
    """{pin number: ((sheet x, sheet y), (outward dx, outward dy))}."""
    t = xform(rot, mirror)
    out = {}
    for p in pins(sym):
        num = unquote(first(p, 'number')[1])
        at = first(p, 'at')
        ox, oy = t(float(at[1]), float(at[2]))
        dx, dy = t(*PINDIR[int(at[3])])
        out[num] = ((round(x + ox, 4), round(y + oy, 4)),
                    (int(round(dx)), int(round(dy))))
    return out


def sym_box(sym, x, y, rot=0, mirror=None):
    """Bounding box of the symbol's graphics plus its pins, in sheet coords."""
    t = xform(rot, mirror)
    pts = []

    def walk(node):
        if not isinstance(node, list) or not node:
            return
        if node[0] in ('rectangle', 'polyline', 'circle', 'arc', 'bezier'):
            for v in node:
                if isinstance(v, list) and v[0] in ('start', 'end', 'mid', 'center'):
                    pts.append(t(float(v[1]), float(v[2])))
                if isinstance(v, list) and v[0] == 'pts':
                    for w in v[1:]:
                        pts.append(t(float(w[1]), float(w[2])))
            r = first(node, 'radius')
            if r:
                c = first(node, 'center')
                rad = float(r[1])
                for sx, sy in ((-rad, -rad), (rad, rad)):
                    pts.append(t(float(c[1]) + sx, float(c[2]) + sy))
        for v in node:
            if isinstance(v, list):
                walk(v)
    walk(sym)
    for p in pins(sym):
        at = first(p, 'at')
        pts.append(t(float(at[1]), float(at[2])))
    if not pts:
        pts = [(0.0, 0.0)]
    return (round(x + min(p[0] for p in pts), 3), round(y + min(p[1] for p in pts), 3),
            round(x + max(p[0] for p in pts), 3), round(y + max(p[1] for p in pts), 3))


def wrapnote(text, cols):
    """Soft-wrap only the lines that are wider than `cols`.  Nothing is dropped
    and every explicit newline is kept, so the tables inside the design notes
    keep their shape."""
    out = []
    for line in text.split('\n'):
        if len(line) <= cols:
            out.append(line)
            continue
        indent = '  ' + line[:len(line) - len(line.lstrip())]
        cur = ''
        for word in line.split(' '):
            trial = (cur + ' ' + word) if cur else word
            if len(trial) > cols and cur:
                out.append(cur)
                cur = indent + word
            else:
                cur = trial
        out.append(cur)
    return '\n'.join(out)


def overlap(a, b, slack=0.0):
    return (a[0] < b[2] - slack and b[0] < a[2] - slack and
            a[1] < b[3] - slack and b[1] < a[3] - slack)


_PWR = [0]
COLLISIONS = []


class Sheet:
    """One schematic page.

    Layout is written as: place the IC, read its pin coordinates out of the
    returned geometry map, then place the passives that serve each pin next to
    it and join them with route().  `manual` says which pins the page builder
    wires itself; every other pin gets the old behaviour (a stub with a global
    label on it), which is still what a bus or an off-page GPIO wants.
    """

    def __init__(self, name, title, page, paper='A4', notecols=118, notesize=1.1):
        self.name, self.title, self.page, self.paper = name, title, page, paper
        self.w, self.h = PAPER[paper]
        self.id = uid(name)
        self.libs = {}
        self.items = []
        self.bom = []
        self.n = 0
        self.wires = []
        self.conn = {}        # sheet point -> number of connectable items on it
        self.pinpts = []      # (point, ref, pin number) for the connectivity check
        self.ncpts = set()
        self.claims = []      # (point, net, what) - the net a point is supposed to be on
        self.boxes = []       # (box, kind, tag) for the collision report
        self.notecols, self.notesize = notecols, notesize

    # -- text ---------------------------------------------------------------
    def _box(self, text, x, y, size, kind, rot=0, mid=False):
        lines = text.split('\n')
        w = max(len(l) for l in lines) * CHARW * size
        h = len(lines) * LINEH * size
        y0 = y - h / 2.0 if mid else y - 0.35 * size
        box = (x, y0, x + w, y0 + h) if rot == 0 else (x - 0.35 * size, y - w, x - 0.35 * size + h, y)
        self.boxes.append((box, kind, lines[0][:40], None))
        return box

    def _text(self, text, x, y, size, kind, rot=0, just='left top'):
        box = self._box(text, x, y, size, kind, rot)
        self.n += 1
        self.items.append(
            f'(text {q(text)} (at {x} {y} {rot}) (effects (font (size {size} {size})) '
            f'(justify {just})) (uuid {uid(self.name + "note" + str(self.n))}))')
        return round(box[3] + 0.9 * size, 3)

    def note(self, text, x, y, size=None, cols=None):
        """A preserved design note, parked in the page margin.  Returns the y
        the next block may start at, so notes stack without arithmetic."""
        size = size or self.notesize
        return self._text(wrapnote(text, cols or self.notecols), x, y, size, 'note')

    def notes(self, texts, cols, y0, size=None, gap=1.6):
        """Flow the preserved design notes down the page margin.

        `cols` is [(x, bottom y), ...].  A block that runs past the bottom of a
        column is continued in the next one AT A LINE BOUNDARY, so nothing is
        dropped or reflowed away - the note is simply split where the paper
        ends.  This is what keeps the long rationale blocks on the page they
        document without them colliding with the drawing or each other."""
        size = size or self.notesize
        ci, y = 0, y0
        for text in texts:
            blk = wrapnote(text, self.notecols).split('\n')
            i = 0
            while i < len(blk):
                room = int((cols[ci][1] - y) / (LINEH * size))
                if room < 3:
                    ci += 1
                    if ci >= len(cols):
                        raise ValueError((self.name, 'notes do not fit the page',
                                          text.split('\n')[0][:40]))
                    y = y0
                    room = int((cols[ci][1] - y) / (LINEH * size))
                take = blk[i:i + room]
                y = self._text('\n'.join(take), cols[ci][0], y, size, 'note')
                i += len(take)
            y += gap
        return y

    def title_note(self, text, x=10.0, y=7.0, size=2.0):
        return self._text(text, x, y, size, 'title')

    def head(self, text, x, y, size=1.5):
        """Short heading over a group of parts ("Decoupling", "Test points")."""
        return self._text(text, x, y, size, 'head')

    # -- wires --------------------------------------------------------------
    def wire(self, a, b):
        a = (round(a[0], 4), round(a[1], 4))
        b = (round(b[0], 4), round(b[1], 4))
        if a == b:
            return b
        if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
            raise ValueError((self.name, 'diagonal wire', a, b))
        for p in (a, b):
            if any(abs(v - snap(v)) > 1e-6 for v in p):
                raise ValueError((self.name, 'wire end off the 1.27 mm grid', p))
        self.wires.append((a, b))
        return b

    def route(self, *pts):
        """Orthogonal polyline; a diagonal step becomes a horizontal-then-
        vertical elbow."""
        cur = pts[0]
        for nxt in pts[1:]:
            if abs(cur[0] - nxt[0]) > 1e-6 and abs(cur[1] - nxt[1]) > 1e-6:
                mid = (nxt[0], cur[1])
                self.wire(cur, mid)
                cur = self.wire(mid, nxt)
            else:
                cur = self.wire(cur, nxt)
        return cur

    def mark(self, pt):
        pt = (round(pt[0], 4), round(pt[1], 4))
        self.conn[pt] = self.conn.get(pt, 0) + 1

    # -- labels and power symbols -------------------------------------------
    def label(self, net, pt, d, size=1.0):
        ang = LABANG[tuple(d)]
        self.n += 1
        w = (len(net) + 2) * CHARW * size
        if d in (LEFT, RIGHT):
            box = (pt[0] - w, pt[1] - 0.8 * size, pt[0], pt[1] + 0.8 * size) if d == LEFT \
                else (pt[0], pt[1] - 0.8 * size, pt[0] + w, pt[1] + 0.8 * size)
        else:
            box = (pt[0] - 0.8 * size, pt[1] - w, pt[0] + 0.8 * size, pt[1]) if d == UP \
                else (pt[0] - 0.8 * size, pt[1], pt[0] + 0.8 * size, pt[1] + w)
        self.boxes.append((box, 'label', net, pt))
        self.items.append(
            f'(global_label {q(net)} (shape passive) (at {pt[0]} {pt[1]} {ang}) '
            f'(effects (font (size {size} {size})) (justify {"right" if ang == 180 else "left"})) '
            f'(uuid {uid(self.name + "lab" + str(self.n))}))')
        self.mark(pt)
        self.claims.append((pt, net, 'label ' + net))
        return pt

    def netlab(self, net, pt, d, length=5.08, size=1.0):
        """Stub out of a pin (or off the end of a wire) into a global label."""
        end = (round(pt[0] + d[0] * length, 4), round(pt[1] + d[1] * length, 4))
        self.wire(pt, end)
        return self.label(net, end, d, size)

    def gnd(self, pt, length=2.54, d=DOWN):
        """A power:GND symbol hung off `pt`.  Power symbols carry a '#' ref, so
        they are outside the netlist, the BOM and the board - the GND net keeps
        exactly the nodes it has today."""
        end = (round(pt[0] + d[0] * length, 4), round(pt[1] + d[1] * length, 4))
        self.wire(pt, end)
        _PWR[0] += 1
        rot = {DOWN: 0, UP: 180, LEFT: 270, RIGHT: 90}[tuple(d)]
        self.part('#PWR%03d' % _PWR[0], 'power:GND', 'GND', end[0], end[1],
                  {'1': 'GND'}, rot=rot, manual='*', fields='hide', lcsc='')
        return end

    def flag(self, net, pt, length=5.08):
        """PWR_FLAG above `pt`; its pin faces down, so it sits on top of the
        rail stub it declares."""
        top = (pt[0], round(pt[1] - length, 4))
        _PWR[0] += 1
        self.part('#FLG%03d' % _PWR[0], 'power:PWR_FLAG', 'PWR_FLAG', top[0], top[1],
                  {'1': net}, manual='*', fields='hide', lcsc='')
        self.wire(top, pt)
        return pt

    # -- symbols ------------------------------------------------------------
    def part(self, ref, libid, value, x, y, nets, rot=0, mirror=None, foot=None,
             refofs=None, valofs=None, fields='above', dnp=False, lcsc=None,
             manual=(), vlab=False, stub=5.08, fsize=1.0, valang=0):
        """Place one symbol and return {pin: ((x, y), (dx, dy))}.

        dnp=True marks the symbol DO NOT POPULATE and excludes it from the BOM:
        KiCad's own `(dnp yes)` / `(in_bom no)` symbol attributes, which ERC,
        the netlist export, the BOM and pcbnew all read.  The net list is
        unchanged - a DNP part still owns its nets and its land pattern, it is
        simply not fitted.  See the U24 flash-socket note on the QSPI page.

        lcsc= overrides the tools/jlc/lcsc_map.csv lookup for this one symbol;
        lcsc='' suppresses the property entirely (board features, THT parts the
        order ships unpopulated).  The property is hidden - it is order data,
        not schematic content.

        manual='*' or a set of pin numbers: those pins get no stub and no label
        because the page builder wires them itself.  Pins whose net is None get
        a no-connect flag; everything else keeps the stub-plus-global-label
        treatment, which is what an off-page GPIO or bus signal wants.
        """
        x, y = snap(x), snap(y)
        sym = symbol(libid)
        if libid not in self.libs:
            embedded = copy.deepcopy(sym)
            embedded[1] = q(libid)
            self.libs[libid] = embedded
        props = {unquote(p[1]): unquote(p[2]) for p in children(sym, 'property')}
        fp = foot if foot is not None else props.get('Footprint', '')
        attrs = '(in_bom no) (on_board yes) (dnp yes)' if dnp else '(in_bom yes) (on_board yes) (dnp no)'
        mir = ' (mirror %s)' % mirror if mirror else ''
        inst = f'(symbol (lib_id {q(libid)}) (at {x} {y} {rot}){mir} (unit 1) {attrs} (uuid {uid(ref)})'
        box = sym_box(sym, x, y, rot, mirror)
        hide_fields = fields == 'hide'
        if refofs is None:
            if fields == 'right':
                rx, ry = box[2] + 1.0, y - 1.9
            elif fields == 'left':
                rx, ry = box[0] - 1.0, y - 1.9
            elif fields == 'below':
                rx, ry = box[0], box[3] + 2.2
            else:
                rx, ry = box[0], box[1] - 4.4
        else:
            rx, ry = refofs
        vx, vy = valofs if valofs else (rx, ry + 2.2)
        code = lcsc if lcsc is not None else lcsc_for(ref, value, fp)
        fields_ = [('Reference', ref, rx, ry, hide_fields),
                   ('Value', value, vx, vy, hide_fields),
                   ('Footprint', fp, x, y, True),
                   ('Datasheet', props.get('Datasheet', ''), x, y, True)]
        if code:
            fields_.append(('LCSC', code, x, y, True))
        # KiCad renders a field at (field angle + symbol rotation) and flips the
        # horizontal justification of a mirrored symbol, both verified against
        # kicad-cli.  Compensate so every visible field reads horizontally,
        # left to right, starting at the coordinate asked for.
        just = 'right' if mirror == 'y' else 'left'
        for key, val, xx, yy, hide in fields_:
            want = valang if key == 'Value' else 0
            inst += (f' (property {q(key)} {q(val)} (at {xx} {yy} {(want - rot) % 360}) '
                     f'(effects (font (size {fsize} {fsize})) (justify {just}) '
                     f'{"(hide yes)" if hide else ""}))')
            if not hide and val:
                self._box(val, xx, yy, fsize, 'field', rot=want, mid=(want == 0))
        geom = sym_geom(sym, x, y, rot, mirror)
        self.boxes.append((box, 'body', ref, None))
        seen = set()
        for p in pins(sym):
            num = unquote(first(p, 'number')[1])
            if num not in nets:
                if num == 'SH' and 'S1' in nets:
                    nets[num] = nets.pop('S1')
                else:
                    raise ValueError((ref, 'missing pin', num))
            pt, d = geom[num]
            self.mark(pt)
            self.pinpts.append((pt, ref, num))
            net = nets[num]
            if net:
                self.claims.append((pt, net, '%s.%s' % (ref, num)))
            if net is None:
                self.ncpts.add(pt)
                self.items.append(f'(no_connect (at {pt[0]} {pt[1]}) (uuid {uid(ref + "nc" + num)}))')
            elif manual == '*' or num in manual:
                pass
            elif (pt, net) not in seen:
                self.netlab(net, pt, d, stub)
                seen.add((pt, net))
            inst += f' (pin {q(num)} (uuid {uid(ref + "pin" + num)}))'
        inst += f' (instances (project "MARV-V2" (path "/{uid("power-root")}/{self.id}" (reference {q(ref)}) (unit 1)))))'
        self.items.append(inst)
        self.bom.append((ref, value, fp, self.name, 'DNP' if dnp else 'populated'))
        return geom

    # -- 2-pin passives -----------------------------------------------------
    def passive(self, ref, kind, value, x, y, rot=VERT, foot=None, dnp=False,
                lcsc=None, valofs=None, refofs=None, fields=None, fsize=1.0, valang=0):
        """rot=VERT draws it upright with pin 1 at the top, rot=HORZ lays it on
        its side with pin 1 on the left.  Returns the pin geometry."""
        if foot is None:
            foot = passive_footprint(kind, value)
        if fields is None:
            fields = 'above' if rot == HORZ else 'right'
        return self.part(ref, 'Device:' + kind, value, x, y, {'1': '', '2': ''},
                         rot=rot, foot=foot, dnp=dnp, lcsc=lcsc, manual='*',
                         fields=fields, valofs=valofs, refofs=refofs, fsize=fsize,
                         valang=valang)

    def cap(self, ref, value, x, y, **kw):
        return self.passive(ref, 'C', value, x, y, **kw)

    def res(self, ref, value, x, y, **kw):
        return self.passive(ref, 'R', value, x, y, **kw)

    def ind(self, ref, value, x, y, **kw):
        return self.passive(ref, 'L', value, x, y, **kw)

    def bead(self, ref, value, x, y, **kw):
        return self.passive(ref, 'FerriteBead', value, x, y, **kw)

    def capcol(self, x_rail, y0, x_gnd, items, dy=7.62, valx=None, refdx=-3.4):
        """A column of horizontal bypass caps between a vertical supply rail at
        x_rail and a vertical ground bus at x_gnd - the shape a hand-drawn
        decoupling block has.  items = [(ref, value, kwargs)].  Returns the two
        bus segments so the caller can join them to the pin they serve."""
        xc = (x_rail + x_gnd) / 2.0
        ys = []
        for i, it in enumerate(items):
            ref, value = it[0], it[1]
            kw = dict(it[2]) if len(it) > 2 else {}
            y = y0 + i * dy
            g = self.cap(ref, value, xc, y, rot=HORZ, fields='none',
                         refofs=(snap(xc) + refdx, y - 3.6),
                         valofs=(valx if valx is not None else x_gnd + 2.5, y - 1.1), **kw)
            self.route(g['1'][0], (x_rail, g['1'][0][1]))
            self.route(g['2'][0], (x_gnd, g['2'][0][1]))
            ys.append(g['1'][0][1])
        self.wire((x_rail, ys[0]), (x_rail, ys[-1]))
        self.wire((x_gnd, ys[0]), (x_gnd, ys[-1]))
        return (x_rail, ys[0]), (x_rail, ys[-1]), (x_gnd, ys[0]), (x_gnd, ys[-1])

    # -- render -------------------------------------------------------------
    def _split_and_junction(self):
        """Break every wire at each connectable point that falls inside it, so
        a T-joint is always three wire ENDS (which KiCad joins) rather than an
        end resting on a segment (which it does not).  Then drop a junction dot
        wherever three or more ends meet."""
        pts = set(self.conn)
        for a, b in self.wires:
            pts.add(a)
            pts.add(b)
        segs = []
        for a, b in self.wires:
            if a[0] == b[0]:
                inner = sorted(p[1] for p in pts if abs(p[0] - a[0]) < 1e-6
                               and min(a[1], b[1]) - 1e-6 < p[1] < max(a[1], b[1]) + 1e-6)
                segs += [((a[0], u), (a[0], v)) for u, v in zip(inner, inner[1:]) if v - u > 1e-6]
            else:
                inner = sorted(p[0] for p in pts if abs(p[1] - a[1]) < 1e-6
                               and min(a[0], b[0]) - 1e-6 < p[0] < max(a[0], b[0]) + 1e-6)
                segs += [((u, a[1]), (v, a[1])) for u, v in zip(inner, inner[1:]) if v - u > 1e-6]
        segs = sorted(set(segs))
        deg = {}
        for a, b in segs:
            deg[a] = deg.get(a, 0) + 1
            deg[b] = deg.get(b, 0) + 1
        dangling = [p for p, d in deg.items() if d == 1 and p not in self.conn]
        if dangling:
            raise ValueError((self.name, 'dangling wire end(s)', sorted(dangling)[:8]))
        junctions = sorted(p for p, d in deg.items() if d >= 3)
        return segs, junctions

    def _check_nets(self, segs):
        """Every wire island must carry exactly one net.

        Each pin and each global label CLAIMS a net name for the point it sits
        on; the wires say which points are the same electrical node.  If one
        island collects two different claims, a wire or a ground symbol has
        landed on something it should not have - which is exactly the mistake
        that a pure-label schematic could never make and a wired one can.  It
        is caught here, with coordinates, instead of in a netlist diff."""
        parent = {}

        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        for a, b in segs:
            union(a, b)
        islands = {}
        for pt, net, what in self.claims:
            islands.setdefault(find(pt), {}).setdefault(net, []).append('%s@%s' % (what, pt))
        bad = []
        for root, names in islands.items():
            if len(names) > 1:
                bad.append('%s: %s' % (root, ' vs '.join(
                    '%s[%s]' % (n, '; '.join(w[:3])) for n, w in sorted(names.items()))))
        if bad:
            raise ValueError((self.name, 'wire island with more than one net', bad[:6]))

    def _check_pins(self):
        """Every pin must end up on a wire, on a no-connect flag, or on top of
        another pin of the same part group.  A pin that is none of those is a
        connection the page builder forgot, which would silently drop a node
        from the netlist."""
        ends = set()
        for a, b in self.wires:
            ends.add(a)
            ends.add(b)
        seen = {}
        bad = []
        for pt, ref, num in self.pinpts:
            if pt in ends or pt in self.ncpts:
                seen.setdefault(pt, []).append(ref)
                continue
            if pt in seen:
                continue
            bad.append('%s.%s at %s' % (ref, num, pt))
        if bad:
            raise ValueError((self.name, 'pin(s) with nothing attached', bad[:10]))

    def render(self):
        self._check_pins()
        segs, junctions = self._split_and_junction()
        self._check_nets(segs)
        out = []
        for i, (a, b) in enumerate(segs):
            out.append(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) '
                       f'(stroke (width 0) (type default)) (uuid {uid(self.name + "w%d" % i)}))')
        for i, p in enumerate(junctions):
            out.append(f'(junction (at {p[0]} {p[1]}) (diameter 0) (color 0 0 0 0) '
                       f'(uuid {uid(self.name + "j%d" % i)}))')
        self.collide()
        return (f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {self.id}) '
                f'(paper "{self.paper}") (title_block (title {q(self.title)}) (date "2026-09-16") '
                f'(rev "P0 - REVIEW ONLY")) (lib_symbols '
                + '\n'.join(dump(s) for s in self.libs.values()) + ')\n'
                + '\n'.join(self.items + out) + '\n(embedded_fonts no))\n')

    def collide(self):
        """Report text that lands on a symbol, a wire or other text.  Nothing
        here is fatal - it is the checklist the page layout is tuned against."""
        seg_boxes = [((min(a[0], b[0]) - 0.35, min(a[1], b[1]) - 0.35,
                       max(a[0], b[0]) + 0.35, max(a[1], b[1]) + 0.35), 'wire', '', (a, b))
                     for a, b in self.wires]
        texts = [e for e in self.boxes if e[1] in ('note', 'title', 'head', 'label', 'field')]
        solids = ([e for e in self.boxes if e[1] == 'body'] + seg_boxes
                  + [((self.w - 112.0, self.h - 42.0, self.w, self.h), 'titleblock', '', None)])
        for i, (bx, kind, tag, anchor) in enumerate(texts):
            for (by, k2, t2, a2) in solids:
                if k2 == 'wire' and anchor is not None and anchor in a2:
                    continue          # a label always touches the wire it names
                if overlap(bx, by, 0.3):
                    COLLISIONS.append('%-12s %-5s %-24s x %-5s %s' % (self.name, kind, tag[:24], k2, t2))
            for (by, k2, t2, a2) in texts[i + 1:]:
                if overlap(bx, by, 0.3):
                    COLLISIONS.append('%-12s %-5s %-24s x %-5s %s' % (self.name, kind, tag[:24], k2, t2[:24]))
        for (bx, kind, tag, _a) in self.boxes:
            if bx[0] < 4 or bx[1] < 4 or bx[2] > self.w - 4 or bx[3] > self.h - 4:
                COLLISIONS.append('%-14s %-6s %-22s OFF PAGE %s' % (self.name, kind, tag[:22], str(bx)))


# ---------------------------------------------------------------------------
# PAGES
#
# One page per subsystem.  On each page the IC sits in the centre-left with its
# own decoupling, pull-ups, series resistors, test points and connectors drawn
# next to the pin they serve and joined to it by wires; a global label is used
# only where a net leaves the page (rails, buses, off-page GPIO).  Every net
# keeps exactly the name it had before the reorganisation, which is what makes
# the netlist fingerprint identical.
# ---------------------------------------------------------------------------
V3 = 'V3V3_SYS'
ANA = 'V3V3_ANA'
# The IO block's 5 V rows are on 5V_IN, the external BEC rail AHEAD of the Q1
# OR-ing FET, not on V5_SYS: servo and module current must not cross the FET
# and a USB host must never see the servo rows (DESIGN_SPEC "Decisions").
V5 = '5V_IN'

# The IO array: 14 rows, three pins each.  Row n is J6 pin n (signal) / J7 pin n (power) / J8 pin n (GND).
# Row 1 is at the TOP of the block; the columns run GND | POWER | SIGNAL from the board edge inward.
IO_ROWS=[('T0','GPS_RX',V5,'UART1 TX -> GPS RX (GPIO24)'),
         ('R0','GPS_TX',V5,'UART1 RX <- GPS TX (GPIO25)'),
         ('T1','ELRS_RX',V5,'UART0 TX -> ELRS RX (GPIO16)'),
         ('R1','ELRS_TX',V5,'UART0 RX <- ELRS TX (GPIO17)'),
         ('SDA','MAG_SDA',V3,'I2C1 SDA (GPIO22), 4.7k pull-up on the MCU sheet'),
         ('SCL','MAG_SCL',V3,'I2C1 SCL (GPIO23), 4.7k pull-up on the MCU sheet'),
         ('S5','PWM5',V5,'PWM2 A (GPIO20), servo 5'),
         ('S6','PWM6',V5,'PWM1 B (GPIO19), servo 6'),
         ('S7','PWM7',V5,'PWM7 B (GPIO15), servo 7'),
         ('S8','PWM8',V5,'PWM2 B (GPIO5), servo 8'),
         ('A44','IO_GPIO44',V3,'GPIO44 = ADC4, spare'),
         ('A45','IO_GPIO45',V3,'GPIO45 = ADC5, spare'),
         ('A46','IO_GPIO46',V3,'GPIO46 = ADC6, spare'),
         ('A47','IO_GPIO47',V3,'GPIO47 = ADC7, spare')]


def power_vbat_sheet():
    s = Sheet('power_vbat', 'POWER 1 / ESC pad row, 5 V input and analog sense', 2, 'A3')
    s.title_note('POWER 1 - ESC PAD ROW J3 (NINE PADS), 5 V INPUT FROM AN EXTERNAL BEC, VBAT SENSE, ANALOG SENSE.\n'
                 'Regulated 5 V arrives on J3 pin 7 as 5V_IN; pin 9 brings raw pack VBAT in as a SENSE wire only.')

    # --- J3, the ESC pad row, with its two analog inputs conditioned here -----
    s.head('ESC pad row', 25.4, 53.34, 1.27)
    j3 = s.part('J3', 'Connector_Generic:Conn_01x09',
                'ESC pads (CURR TX M4 M3 M2 M1 5V GND VBAT)',
                38.1, 76.2, {'1': 'CURR_SENSE_RAW', '2': 'ESC_TELEM', '3': 'PWM4', '4': 'PWM3',
                             '5': 'PWM2', '6': 'PWM1', '7': '5V_IN', '8': 'GND', '9': 'VBAT'},
                foot='MARV_Packages:PadRow_1x09_P2.00mm', mirror='y',
                manual=('1', '2', '7', '8'), stub=10.16, refofs=(25.4, 58.42), fsize=0.9)
    s.gnd(j3['8'][0], 7.62, RIGHT)

    # --- pad 7: the 5 V input rail, with the board's only bulk on it ---------
    s.head('5 V in from the external BEC', 66.04, 104.14, 1.27)
    rail = s.route(j3['7'][0], (60.96, j3['7'][0][1]), (60.96, 116.84), (99.06, 116.84))
    s.flag('5V_IN', (74.93, 116.84))
    s.label('5V_IN', rail, RIGHT)
    c19 = s.cap('C19', '100u / 6.3 V polymer, ESR <= 40 mOhm (e.g. Panasonic 6TPE100MAZB or KEMET T520/T530 B case), 5V_IN bulk at the pad row',
                88.9, 127.0, foot='Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B',
                valofs=(91.44, 128.27), fsize=0.7)
    s.wire((88.9, 116.84), c19['1'][0])
    s.gnd(c19['2'][0], 3.81)

    s.head('ESC current sense and KISS telemetry conditioning', 120.65, 20.32, 1.27)
    pt = s.route(j3['1'][0], (66.04, j3['1'][0][1]), (66.04, 45.72))
    r53 = s.res('R53', '1k / 1%, CURR series', 86.36, 45.72, rot=HORZ,
                refofs=(81.28, 41.91), valofs=(81.28, 51.44), fsize=0.85)
    s.wire(pt, r53['1'][0])
    s.label('CURR_SENSE_RAW', s.wire((74.93, 45.72), (74.93, 39.37)), UP)
    node = s.route(r53['2'][0], (104.14, 45.72))
    c78 = s.cap('C78', '100n / 16 V X7R, ADC2 filter', 104.14, 55.88,
                valofs=(106.68, 57.15), fsize=0.85)
    s.wire(node, c78['1'][0])
    s.gnd(c78['2'][0], 3.81)
    s.label('CURR_SENSE', s.wire(node, (127, 45.72)), RIGHT)

    pt = s.route(j3['2'][0], (73.66, j3['2'][0][1]), (73.66, 31.75))
    r54 = s.res('R54', '1k, ESC telemetry series', 86.36, 31.75, rot=HORZ,
                refofs=(81.28, 27.94), valofs=(95.25, 27.94), fsize=0.85)
    s.wire(pt, r54['1'][0])
    s.label('ESC_TELEM', s.wire((78.74, 31.75), (78.74, 25.4)), UP)
    s.label('ESC_TELEM_RX', s.wire(r54['2'][0], (109.22, 31.75)), RIGHT)

    # --- VBAT_SENSE divider --------------------------------------------------
    s.head('VBAT_SENSE divider - 1/11, 36.3 V full scale', 325.12, 26.67, 1.27)
    r27 = s.res('R27', '100k / 1%, VBAT top', 335.28, 53.34, valofs=(337.82, 54.61), fsize=0.85)
    s.label('VBAT', s.wire(r27['1'][0], (335.28, 41.91)), UP)
    # VBAT reaches no driver pin any more (J3 pin 9 is a connector pad and both
    # divider legs are passive), so this is the flag that makes it a net ERC
    # will accept.  It used to sit on the U26 buck input.
    s.flag('VBAT', (335.28, 46.99))
    r28 = s.res('R28', '10k / 1%, VBAT bottom', 335.28, 73.66, valofs=(337.82, 74.93), fsize=0.85)
    s.wire(r27['2'][0], r28['1'][0])
    s.gnd(r28['2'][0], 3.81)
    c48 = s.cap('C48', '100n / 16 V X7R, ADC1', 358.14, 73.66, valofs=(360.68, 74.93), fsize=0.85)
    s.route((335.28, 63.5), (358.14, 63.5), c48['1'][0])
    s.gnd(c48['2'][0], 3.81)
    s.label('VBAT_SENSE', s.wire((358.14, 63.5), (381, 63.5)), RIGHT)

    # GND needs exactly one PWR_FLAG for ERC; it is declared here.
    s.head('GND declared (ERC power flag)', 325.12, 140.97, 1.27)
    s.flag('GND', (340.36, 153.67))
    s.gnd((340.36, 153.67), 5.08)

    s.notes([N_SRC_HDR, N_J3, N_ANALOG], [(10, 292), (140, 292), (270, 250)], 178)
    return s


def power_or_sheet():
    s = Sheet('power_or', 'POWER 2 / 5 V OR - BEC P-FET and USB Schottky', 3, 'A3')
    s.title_note('POWER 2 - Q1 AO3401A P-FET + D1 1N5819WS SCHOTTKY.  5V_IN (external BEC, J3 pin 7) OR USB_VBUS -> V5_SYS.\n'
                 'USB present turns Q1 OFF, so a host can never back-feed the BEC, the servo rows or the ESC.')

    # Q1: drain (pad 3) faces UP to 5V_IN, source (pad 2) DOWN to V5_SYS, gate
    # (pad 1) LEFT to USB_VBUS.  A P-channel body diode points drain->source,
    # i.e. the way the load current already wants to go.
    s.head('BEC path - Q1 P-channel FET, drain 5V_IN, source V5_SYS', 133.35, 40.64)
    q1 = s.part('Q1', 'Transistor_FET:AO3401A', 'AO3401A', 177.8, 88.9,
                {'1': 'USB_VBUS', '2': 'V5_SYS', '3': '5V_IN'}, manual='*',
                foot='Package_TO_SOT_SMD:SOT-23',
                refofs=(185.42, 85.09), valofs=(185.42, 87.63), fsize=0.9)

    # --- 5V_IN in at the drain ------------------------------------------------
    s.label('5V_IN', s.route(q1['3'][0], (180.34, 55.88), (114.3, 55.88)), LEFT)

    # --- the gate, and its pull-down -----------------------------------------
    s.head('Gate on USB_VBUS - USB present = Q1 off', 71.12, 74.93, 1.27)
    gate = s.route(q1['1'][0], (114.3, 88.9))
    s.label('USB_VBUS', gate, LEFT)
    r7 = s.res('R7', '100k / 1%, Q1 gate pull-down', 140.97, 96.52,
               valofs=(143.51, 97.79), fsize=0.85)
    s.wire((140.97, 88.9), r7['1'][0])
    s.gnd(r7['2'][0], 3.81)

    # --- USB path: D1, anode USB_VBUS, cathode V5_SYS ------------------------
    s.head('USB path - D1 Schottky, the only way USB reaches V5_SYS', 106.68, 128.27, 1.27)
    d1 = s.part('D1', 'Device:D_Schottky', '1N5819WS', 152.4, 116.84,
                {'1': 'V5_SYS', '2': 'USB_VBUS'}, rot=180, manual='*',
                foot='Diode_SMD:D_SOD-323',
                refofs=(147.32, 110.49), valofs=(158.75, 118.11), fsize=0.85)
    s.route(d1['2'][0], (127, 116.84), (127, 88.9))

    # --- V5_SYS out -----------------------------------------------------------
    s.head('V5_SYS - the two 3.3 V regulators and the status LED, nothing else', 198.12, 133.35, 1.27)
    out = s.route(q1['2'][0], (180.34, 116.84), (241.3, 116.84))
    s.wire(d1['1'][0], (180.34, 116.84))
    s.flag('V5_SYS', (215.9, 116.84))
    s.label('V5_SYS', out, RIGHT)

    s.notes([N_OR, N_VBUS_IN2], [(10, 292), (140, 292), (270, 250)], 150)
    return s


def power_3v3_sheet():
    s = Sheet('power_3v3', 'POWER 3 / 3.3 V system buck and analog LDO', 4, 'A3')
    s.title_note('POWER 3 - U7 AP63203WU-7 FIXED 3.3 V BUCK (V5_SYS -> V3V3_SYS) AND U12 TPS7A20 LDO (-> V3V3_ANA)\n'
                 'AVIONICS ONLY: 300 mA continuous / 500 mA short peak, provisional. NO SERVO POWER.')

    s.head('V5_SYS input bulk at the pin', 71.12, 16.51, 1.27)
    s.capcol(20.32, 34.29, 36.83,
             [('C8', '10u / 10 V X7R 0603, VIN bulk (AP63203 Table 2 C1)', {'fsize': 0.8}),
              ('C9', '100n / 16 V X7R, VIN HF bypass', {'fsize': 0.8})], valx=39.37)
    s.gnd((36.83, 41.91), 3.81)
    s.route((20.32, 34.29), (20.32, 24.13), (104.14, 24.13))
    s.label('V5_SYS', s.wire((60.96, 24.13), (60.96, 20.32)), UP)

    # U7, the AP63203: 1 FB (sense, straight to the output), 2 EN, 3 VIN,
    # 4 GND, 5 SW, 6 BST.  There is no divider and no S-CONF resistor: the
    # output voltage is the part number (datasheet Sec 9).
    s.head('3.3 V system buck - fixed output, no divider', 111.76, 60.96)
    u7 = s.part('U7', 'Regulator_Switching:AP63203WU', 'AP63203WU-7', 127, 88.9,
                {'1': 'V3V3_SYS', '2': 'U7_EN', '3': 'V5_SYS', '4': 'GND',
                 '5': 'U7_SW', '6': 'U7_BST'},
                foot='Package_TO_SOT_SMD:TSOT-23-6', manual='*',
                refofs=(116.84, 71.12))
    s.gnd(u7['4'][0], 5.08)
    s.route(u7['3'][0], (104.14, 86.36), (104.14, 24.13))

    # EN through R52 to VIN: "the EN pin ... can be directly connected to VIN"
    # (Sec 3), with a series 100k so a UVLO divider or a start-delay cap can
    # be added later without touching copper.
    r52 = s.res('R52', '100k / 1%, EN to VIN', 78.74, 38.1, valofs=(81.28, 39.37),
                fsize=0.85)
    s.wire((78.74, 24.13), r52['1'][0])
    s.route(r52['2'][0], (78.74, 109.22), (110.49, 109.22), (110.49, 91.44), u7['2'][0])
    s.label('U7_EN', s.wire((95.25, 109.22), (95.25, 114.3)), DOWN)

    # SW leaves upward, turns over the top of the package and comes back down
    # into L2; C13, the bootstrap cap, sits inside that loop between BST and
    # SW so neither wire has to cross the other.
    s.head('Bootstrap and inductor', 196.85, 74.93, 1.27)
    sw = s.route(u7['5'][0], (139.7, 86.36), (139.7, 76.2), (161.29, 76.2))
    s.label('U7_SW', s.wire((139.7, 81.28), (133.35, 81.28)), LEFT)
    c13 = s.cap('C13', '100n / 16 V X7R, bootstrap BST-SW (AP63203 Table 2 C3)',
                149.86, 81.28, rot=HORZ, fields='none', refofs=(146.05, 74.93),
                valofs=(127, 55.88), fsize=0.8)
    s.route(u7['6'][0], (142.24, 88.9), (142.24, 81.28), c13['1'][0])
    s.label('U7_BST', s.wire((142.24, 83.82), (147.32, 83.82)), RIGHT)
    s.wire(c13['2'][0], (153.67, 81.28))
    s.wire((153.67, 81.28), (153.67, 76.2))
    l2 = s.ind('L2', '4.7u, Isat 6.0 A (30 %), DCR 46 mOhm max (CJIANG FTC404030S4R7MGCA)',
               165.1, 86.36, rot=HORZ, foot='MARV_Packages:L_Changjiang_FTC404030S',
               refofs=(168.91, 66.04), valofs=(168.91, 68.58), fsize=0.85)
    s.wire((161.29, 76.2), l2['1'][0])

    v3 = s.route(l2['2'][0], (266.7, 86.36))
    s.flag('V3V3_SYS', (241.3, 86.36))
    s.label('V3V3_SYS', v3, RIGHT)

    # FB (pin 1) is a SENSE input on the fixed-output part: it goes straight
    # to V3V3_SYS, taken at the far end of the output capacitors.
    s.route(u7['1'][0], (140.97, 91.44), (140.97, 127), (215.9, 127), (215.9, 86.36))

    s.head('Output capacitors (Table 2: 2 x 22 uF)', 198.12, 133.35, 1.27)
    s.capcol(177.8, 99.06, 194.31,
             [('C10', '22u / 10 V X5R 0603 GRM188R61A226ME15, COUT (~40% DC-bias loss at 3.3 V)', {'fsize': 0.7}),
              ('C11', '22u / 10 V X5R 0603 GRM188R61A226ME15, COUT (~40% DC-bias loss at 3.3 V)', {'fsize': 0.7})],
             valx=218.44, refdx=-6.2)
    s.gnd((194.31, 106.68), 3.81)
    s.route((177.8, 86.36), (177.8, 99.06))

    # U12 TPS7A20 analog LDO
    s.head('Analog LDO -> V3V3_ANA', 30.48, 135.89, 1.4)
    u12 = s.part('U12', 'Regulator_Linear:TPS7A20xxxDBV', 'TPS7A2033PDBVR', 76.2, 152.4,
                 {'1': 'V5_SYS', '2': 'GND', '3': 'V3V3_SYS', '4': None, '5': 'V3V3_ANA'},
                 manual=('1', '2', '3', '5'), refofs=(68.58, 140.97))
    s.gnd(u12['2'][0], 5.08)
    vin = s.route(u12['1'][0], (48.26, 149.86))
    s.label('V5_SYS', vin, LEFT)
    c25 = s.cap('C25', '1u / 10 V X7R 0402, LDO input', 55.88, 157.48, valofs=(38.1, 163.83),
                fsize=0.85)
    s.wire((55.88, 149.86), c25['1'][0])
    s.gnd(c25['2'][0], 3.81)
    # EN straight to V3V3_SYS: the AP63203 has no power-good pin, so the rail
    # itself does the buck-before-LDO sequencing, at no parts (see N_ANA).
    en = s.route(u12['3'][0], (60.96, 152.4), (60.96, 170.18), (40.64, 170.18))
    s.label('V3V3_SYS', en, LEFT)
    out = s.route(u12['5'][0], (109.22, 149.86))
    s.label('V3V3_ANA', out, RIGHT)
    c26 = s.cap('C26', '1u / 10 V X7R 0402, LDO output, ESR <=100 mOhm', 95.25, 157.48,
                valofs=(97.79, 158.75))
    s.wire((95.25, 149.86), c26['1'][0])
    s.gnd(c26['2'][0], 3.81)

    s.notes([N_U7, N_ANA, N_PKG], [(10, 292), (140, 292), (270, 250)], 190)
    return s


def _sensor_rail(s, pins_up, bus_y, cap_x, y0, gnd_x, items, valx, label_x, dy=7.62):
    """The supply block every sensor page shares: the part's supply pins rise to
    one V3V3_ANA node above the chip, the 100 nF + 1 uF pairs hang off it in a
    ladder, and the rail itself arrives as a global label."""
    xs = sorted(p[0] for p in pins_up)
    for p in pins_up:
        s.route(p, (p[0], bus_y))
    s.wire((min(xs), bus_y), (max(xs), bus_y))
    s.wire((cap_x, bus_y), (min(xs), bus_y))
    s.wire((cap_x, bus_y), (cap_x, y0))
    s.label(ANA, s.wire((cap_x, bus_y), (label_x, bus_y)), LEFT)
    s.capcol(cap_x, y0, gnd_x, items, dy=dy, valx=valx)
    s.gnd((gnd_x, y0 + (len(items) - 1) * dy), 3.81)


def imu_sheet():
    s = Sheet('imu', 'BOARD 2 / ICM-45686 six-axis IMU', 7, 'A4')
    s.title_note('BOARD 2 - U21 ICM-45686 6-AXIS IMU on the shared sensor SPI bus, powered from V3V3_ANA.')
    s.head('Supply decoupling', 30.48, 26.67, 1.27)
    u21 = s.part('U21', 'MARV_Sensors:ICM-45686', 'ICM-45686 6-axis IMU', 149.86, 68.58,
                 {'1': 'SENS_MISO', '2': None, '3': None, '4': 'IMU_INT1', '5': ANA, '6': 'GND',
                  '7': None, '8': ANA, '9': 'IMU_INT2', '10': None, '11': None, '12': 'IMU_CS',
                  '13': 'SENS_SCK', '14': 'SENS_MOSI'},
                 manual=('5', '6', '8', '12'), stub=7.62, refofs=(137.16, 45.72))
    s.gnd(u21['6'][0], 5.08)
    _sensor_rail(s, [u21['5'][0], u21['8'][0]], 40.64, 30.48, 45.72, 46.99,
                 [('C50', '100n / 16 V X7R, U21 VDD', {'fsize': 0.8}),
                  ('C51', '1u / 10 V X7R 0402, U21 VDD', {'fsize': 0.8}),
                  ('C52', '100n / 16 V X7R, U21 VDDIO', {'fsize': 0.8}),
                  ('C53', '1u / 10 V X7R 0402, U21 VDDIO', {'fsize': 0.8})],
                 49.53, 20.32)
    # chip select, with its idle pull-up on the way to the bus
    s.head('CS idle pull-up', 88.9, 96.52, 1.27)
    cs = s.route(u21['12'][0], (124.46, 68.58), (124.46, 101.6), (95.25, 101.6))
    s.label('IMU_CS', cs, LEFT)
    r48 = s.res('R48', '10k, IMU_CS pull-up', 114.3, 90.17, valofs=(116.84, 91.44), fsize=0.85)
    s.wire(r48['2'][0], (114.3, 101.6))
    s.label(ANA, s.route(r48['1'][0], (114.3, 82.55), (99.06, 82.55)), LEFT)

    s.head('Sensor bus test points', 30.48, 114.3, 1.27)
    for i, (ref, net) in enumerate([('TP1', 'SENS_SCK'), ('TP2', 'SENS_MOSI'), ('TP3', 'SENS_MISO'),
                                    ('TP4', 'IMU_CS'), ('TP7', 'IMU_INT1'), ('TP8', 'IMU_INT2')]):
        x = 33.02 + 25.4 * i
        tp = s.part(ref, 'Connector:TestPoint', 'TP %s' % net, x, 125.73, {'1': net},
                    foot='TestPoint:TestPoint_Pad_1.0x1.0mm', manual='*',
                    refofs=(x - 3.81, 120.65), valofs=(x - 3.81, 118.11), fsize=0.85)
        s.netlab(net, tp['1'][0], DOWN, 5.08)

    s.notes([N_SENS_HDR, N_U21, N_CSPULLUP, N_TESTPOINTS], [(10, 206), (160, 164)], 143)
    return s


def baro_sheet():
    s = Sheet('baro', 'BOARD 2 / BMP581 barometer', 8, 'A4')
    s.title_note('BOARD 2 - U22 BMP581 BAROMETER on the shared sensor SPI bus, powered from V3V3_ANA.')
    s.head('Supply decoupling', 30.48, 26.67, 1.27)
    u22 = s.part('U22', 'MARV_Sensors:BMP581', 'BMP581 barometer', 149.86, 71.12,
                 {'1': ANA, '2': 'SENS_SCK', '3': 'GND', '4': 'SENS_MOSI', '5': 'SENS_MISO',
                  '6': 'BARO_CS', '7': 'BARO_INT', '8': 'GND', '9': 'GND', '10': ANA},
                 manual=('1', '3', '6', '8', '9', '10'), stub=7.62, refofs=(139.7, 50.8))
    s.route(u22['3'][0], (147.32, 87.63), (152.4, 87.63))
    s.route(u22['8'][0], (149.86, 87.63))
    s.route(u22['9'][0], (152.4, 87.63))
    s.gnd((149.86, 87.63), 5.08)
    _sensor_rail(s, [u22['1'][0], u22['10'][0]], 43.18, 30.48, 48.26, 46.99,
                 [('C54', '100n / 16 V X7R, U22 VDD', {'fsize': 0.8}),
                  ('C55', '1u / 10 V X7R 0402, U22 VDD', {'fsize': 0.8}),
                  ('C56', '100n / 16 V X7R, U22 VDDIO', {'fsize': 0.8}),
                  ('C57', '1u / 10 V X7R 0402, U22 VDDIO', {'fsize': 0.8})],
                 49.53, 20.32)
    s.head('CSB idle pull-up', 88.9, 96.52, 1.27)
    cs = s.route(u22['6'][0], (128.27, 73.66), (128.27, 101.6), (95.25, 101.6))
    s.label('BARO_CS', cs, LEFT)
    r50 = s.res('R50', '10k, BARO_CS pull-up', 114.3, 90.17, valofs=(116.84, 91.44), fsize=0.85)
    s.wire(r50['2'][0], (114.3, 101.6))
    s.label(ANA, s.route(r50['1'][0], (114.3, 82.55), (99.06, 82.55)), LEFT)

    s.head('Test points', 30.48, 114.3, 1.27)
    for i, (ref, net) in enumerate([('TP5', 'BARO_CS'), ('TP9', 'BARO_INT')]):
        x = 33.02 + 25.4 * i
        tp = s.part(ref, 'Connector:TestPoint', 'TP %s' % net, x, 125.73, {'1': net},
                    foot='TestPoint:TestPoint_Pad_1.0x1.0mm', manual='*',
                    refofs=(x - 3.81, 120.65), valofs=(x - 3.81, 118.11), fsize=0.85)
        s.netlab(net, tp['1'][0], DOWN, 5.08)

    s.notes(['\n'.join(N_U22U23.split('\n')[:2])], [(10, 206)], 150)
    return s


def highg_sheet():
    s = Sheet('highg', 'BOARD 2 / ADXL375 high-g accelerometer', 9, 'A4')
    s.title_note('BOARD 2 - U23 ADXL375 HIGH-G ACCELEROMETER on the shared sensor SPI bus, from V3V3_ANA.')
    s.head('Supply decoupling', 30.48, 26.67, 1.27)
    u23 = s.part('U23', 'MARV_Sensors:ADXL375', 'ADXL375 high-g accelerometer', 149.86, 71.12,
                 {'1': ANA, '2': 'GND', '3': ANA, '4': 'GND', '5': 'GND', '6': ANA,
                  '7': 'HG_ACC_CS', '8': 'HG_ACC_INT', '9': None, '10': None, '11': 'GND',
                  '12': 'SENS_MISO', '13': 'SENS_MOSI', '14': 'SENS_SCK'},
                 manual=('1', '2', '3', '4', '5', '6', '7', '11'), stub=7.62, refofs=(137.16, 45.72))
    s.route(u23['2'][0], (147.32, 90.17), (152.4, 90.17))
    s.route(u23['4'][0], (149.86, 90.17))
    s.route(u23['5'][0], (152.4, 90.17))
    s.gnd((149.86, 90.17), 5.08)
    s.route(u23['11'][0], (172.72, 78.74), (172.72, 90.17))
    s.gnd((172.72, 90.17), 5.08)
    _sensor_rail(s, [u23['1'][0], u23['6'][0]], 43.18, 30.48, 48.26, 46.99,
                 [('C58', '100n / 16 V X7R, U23 VS', {'fsize': 0.8}),
                  ('C59', '1u / 10 V X7R 0402, U23 VS', {'fsize': 0.8}),
                  ('C60', '100n / 16 V X7R, U23 VDD_IO', {'fsize': 0.8}),
                  ('C61', '1u / 10 V X7R 0402, U23 VDD_IO', {'fsize': 0.8})],
                 49.53, 20.32)
    # pin 3 RESERVED goes to VS per the pin function table
    s.label(ANA, s.route(u23['3'][0], (177.8, 76.2), (177.8, 62.23), (191.77, 62.23)), RIGHT)
    s.head('CS idle pull-up', 88.9, 96.52, 1.27)
    cs = s.route(u23['7'][0], (125.73, 73.66), (125.73, 101.6), (95.25, 101.6))
    s.label('HG_ACC_CS', cs, LEFT)
    r51 = s.res('R51', '10k, HG_ACC_CS pull-up', 114.3, 90.17, valofs=(116.84, 91.44), fsize=0.85)
    s.wire(r51['2'][0], (114.3, 101.6))
    s.label(ANA, s.route(r51['1'][0], (114.3, 82.55), (99.06, 82.55)), LEFT)

    s.head('Test points', 30.48, 114.3, 1.27)
    for i, (ref, net) in enumerate([('TP6', 'HG_ACC_CS'), ('TP10', 'HG_ACC_INT')]):
        x = 33.02 + 25.4 * i
        tp = s.part(ref, 'Connector:TestPoint', 'TP %s' % net, x, 125.73, {'1': net},
                    foot='TestPoint:TestPoint_Pad_1.0x1.0mm', manual='*',
                    refofs=(x - 3.81, 120.65), valofs=(x - 3.81, 118.11), fsize=0.85)
        s.netlab(net, tp['1'][0], DOWN, 5.08)

    s.notes(['\n'.join(N_U22U23.split('\n')[2:])], [(10, 206)], 150)
    return s


def sd_sheet():
    s = Sheet('sd', 'BOARD 3 / microSD socket', 10, 'A4')
    s.title_note('BOARD 3 - J11 MICROSD, LATCHED PUSH-PUSH, WIRED FOR 4-BIT PIO (also SPI-compatible).\n'
                 'VDD = V3V3_SYS with 100 nF + 10 uF + 47 uF at the socket; 10k idle pull-ups on CMD, DAT0-3 and card detect.')
    j11 = s.part('J11', 'Connector:Micro_SD_Card_Det2', 'microSD, Molex 104031-0811 push-push',
                 199.39, 78.74, {'1': 'SD_D2', '2': 'SD_D3', '3': 'SD_CMD', '4': V3, '5': 'SD_CLK',
                                 '6': 'GND', '7': 'SD_D0', '8': 'SD_D1', '9': 'SD_DET',
                                 '10': 'GND', 'SH': 'GND'},
                 foot='MARV_Packages:microSD_HC_Molex_104031-0811',
                 manual=('1', '2', '3', '4', '6', '7', '8', '9', '10', 'SH'),
                 stub=7.62, refofs=(176.53, 48.26))
    px = j11['1'][0][0]
    s.gnd(j11['6'][0], 7.62, LEFT)
    s.route(j11['10'][0], (px - 12.7, j11['10'][0][1]), (px - 12.7, 100.33))
    s.gnd((px - 12.7, 100.33), 3.81)
    s.route(j11['SH'][0], (231.14, 91.44), (231.14, 100.33))
    s.gnd((231.14, 100.33), 3.81)
    s.label(V3, s.route(j11['4'][0], (px - 7.62, 76.2), (px - 7.62, 46.99), (154.94, 46.99)), LEFT)

    # the six idle pull-ups, each in the line it biases
    s.head('Idle pull-ups to V3V3_SYS', 60.96, 34.29, 1.27)
    rail = 43.18
    pull = [('R39', 'SD_D2', '1'), ('R40', 'SD_D3', '2'), ('R36', 'SD_CMD', '3'),
            ('R37', 'SD_D0', '7'), ('R38', 'SD_D1', '8'), ('R41', 'SD_DET', '9')]
    lanes = []
    for i, (ref, net, pin) in enumerate(pull):
        lane = 165.1 - 15.24 * i
        lanes.append(lane)
        pt = j11[pin][0]
        end = s.route(pt, (lane, pt[1]))
        s.label(net, end, LEFT)
        r = s.res(ref, '10k, %s pull-up' % net, lane, 55.88, valang=90,
                  refofs=(lane - 5.72, 50.8), valofs=(lane + 1.9, 49.53), fsize=0.85)
        s.wire(r['1'][0], (lane, rail))
        s.wire(r['2'][0], end)
    s.wire((min(lanes), rail), (max(lanes), rail))
    s.label(V3, s.wire((min(lanes), rail), (min(lanes) - 15.24, rail)), LEFT)

    # bulk at the socket
    s.head('Bulk at the socket', 30.48, 106.68, 1.27)
    s.capcol(78.74, 120.65, 95.25, [('C64', '100n / 16 V X7R, at the socket', {'fsize': 0.85}),
                                    ('C65', '10u / 10 V X7R 0603, at the socket', {'fsize': 0.85}),
                                    ('C66', '47u / 6.3 V X5R 0805, at the socket',
                                     {'foot': 'Capacitor_SMD:C_0805_2012Metric', 'fsize': 0.85})],
             valx=97.79)
    s.gnd((95.25, 135.89), 3.81)
    s.label(V3, s.route((78.74, 120.65), (78.74, 113.03), (63.5, 113.03)), LEFT)

    s.notes([N_J11], [(10, 206)], 152)
    return s


def qspi_sheet():
    s = Sheet('qspi_expansion', 'BOARD 3 / optional QSPI expansion socket (DNP)', 11, 'A4')
    s.title_note('BOARD 3 - U24 OPTIONAL QSPI EXPANSION SOCKET, DNP, ON THE BACK (B.Cu).\n'
                 'One 150-mil SOIC-8 land: fit EITHER a W25Q32JVSNIQ NOR flash OR an APS6404L-SQN-SN PSRAM. R35 stays populated.')
    u24 = s.part('U24', 'Memory_Flash:W25Q32JVSS',
                 'DNP: W25Q32JVSNIQ, 32 Mbit QSPI NOR or APS6404L-SQN-SN 8 MB PSRAM (optional back-side expansion)',
                 165.1, 78.74, {'1': 'FLASH_CS1', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND',
                                '5': 'QSPI_SD0', '6': 'QSPI_SCLK', '7': 'QSPI_SD3', '8': V3},
                 foot='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', dnp=True,
                 manual=('1', '4', '8'), stub=7.62, refofs=(154.94, 53.34), fsize=0.85)
    s.gnd(u24['4'][0], 5.08)
    s.head('Socket bypass (fitted; the socket itself is not)', 30.48, 26.67, 1.27)
    vcc = s.route(u24['8'][0], (165.1, 43.18), (60.96, 43.18))
    s.label(V3, s.wire(vcc, (53.34, 43.18)), LEFT)
    # C62/C63 are NOT DNP: the socket is optional, its two bypass caps are fitted.
    s.capcol(60.96, 50.8, 77.47, [('C62', '100n / 16 V X7R, U24 VCC (fitted; socket is optional)',
                                   {'fsize': 0.8}),
                                  ('C63', '1u / 10 V X7R 0402, U24 VCC (fitted; socket is optional)',
                                   {'fsize': 0.8})],
             valx=80.01)
    s.wire((60.96, 43.18), (60.96, 50.8))
    s.gnd((77.47, 58.42), 3.81)
    s.head('FLASH_CS1 idle pull-up (populated)', 60.96, 96.52, 1.27)
    cs = s.route(u24['1'][0], (130.81, 71.12), (130.81, 101.6), (105.41, 101.6))
    s.label('FLASH_CS1', cs, LEFT)
    r35 = s.res('R35', '10k, FLASH_CS1 pull-up', 124.46, 90.17, valofs=(127, 91.44), fsize=0.85)
    s.wire(r35['2'][0], (124.46, 101.6))
    s.label(V3, s.route(r35['1'][0], (124.46, 82.55), (105.41, 82.55)), LEFT)

    s.notes([N_STOR_HDR, N_U24], [(10, 206), (160, 164)], 118)
    return s


def io_block_sheet():
    s = Sheet('io_block', 'BOARD 4 / IO array, status LED, mounting holes', 12, 'A3')
    s.title_note('BOARD 4 - THE 3 x 14 IO BLOCK (J6 SIGNAL / J7 POWER / J8 GND), THE WS2812C STATUS LED\n'
                 'AND THE FOUR M3 GROMMET HOLES. Every signal that leaves the board except the ESC row J3 and the DBG pads J10 leaves here.')
    s.head('IO array - one row per module lead', 78.74, 29.21)
    j6 = s.part('J6', 'Connector_Generic:Conn_01x14', 'IO array signal column (innermost)',
                121.92, 78.74, {str(i + 1): sig for i, (silk, sig, pwr, fn) in enumerate(IO_ROWS)},
                foot='MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow',
                stub=7.62, refofs=(109.22, 53.34))
    j7 = s.part('J7', 'Connector_Generic:Conn_01x14', 'IO array power column (5V / 3V3 per row)',
                187.96, 78.74, {str(i + 1): pwr for i, (silk, sig, pwr, fn) in enumerate(IO_ROWS)},
                foot='MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow',
                stub=7.62, refofs=(175.26, 53.34))
    j8 = s.part('J8', 'Connector_Generic:Conn_01x14', 'IO array GND column (board edge)',
                254, 78.74, {str(i + 1): 'GND' for i in range(14)},
                foot='MARV_Packages:PinHeader_1x14_P2.54mm_Vertical_IORow',
                manual='*', refofs=(241.3, 53.34))
    bus = 238.76
    for i in range(14):
        s.route(j8[str(i + 1)][0], (bus, j8[str(i + 1)][0][1]))
    s.wire((bus, j8['1'][0][1]), (bus, j8['14'][0][1]))
    s.gnd((bus, j8['14'][0][1]), 5.08)

    s.head('Local bulk at the array', 292.1, 22.86, 1.27)
    s.capcol(297.18, 41.91, 313.69, [('C20', '10u / 10 V X7R 0603', {'fsize': 0.85}),
                                     ('C21', '10u / 10 V X7R 0603', {'fsize': 0.85})],
             valx=316.23)
    s.gnd((313.69, 49.53), 3.81)
    s.label(V5, s.wire((297.18, 41.91), (297.18, 34.29)), UP)
    c22 = s.cap('C22', '10u / 10 V X7R 0603', 349.25, 46.99, valofs=(351.79, 48.26), fsize=0.85)
    s.label(V3, s.wire(c22['1'][0], (349.25, 34.29)), UP)
    s.gnd(c22['2'][0], 3.81)

    s.head('WS2812C status LED', 292.1, 106.68)
    d20 = s.part('D20', 'LED:WS2812B-2020', 'WS2812C-2020 RGB', 332.74, 130.81,
                 {'1': None, '2': 'GND', '3': 'LED_DIN', '4': 'V5_SYS'},
                 foot='MARV_Packages:LED_WS2812B-2020_PLCC4_2.0x2.0mm',
                 manual=('2', '3', '4'), refofs=(325.12, 113.03))
    s.gnd(d20['2'][0], 5.08)
    s.label('V5_SYS', s.route(d20['4'][0], (332.74, 115.57), (317.5, 115.57)), LEFT)
    c79 = s.cap('C79', '100n / 16 V X7R, D20 VDD', 347.98, 121.92, valofs=(350.52, 123.19),
                fsize=0.85)
    s.route((332.74, 115.57), (347.98, 115.57), c79['1'][0])
    s.gnd(c79['2'][0], 3.81)
    r55 = s.res('R55', '100 / 1%, WS2812 data series', 302.26, 130.81, rot=HORZ,
                refofs=(297.18, 127), valofs=(297.18, 137.16), fsize=0.85)
    s.wire(r55['2'][0], d20['3'][0])
    s.label('LED_DATA', s.wire(r55['1'][0], (289.56, 130.81)), LEFT)
    s.label('LED_DIN', s.wire((314.96, 130.81), (314.96, 125.73)), UP)

    s.head('Mechanical', 78.74, 152.4, 1.27)
    # Grounded mounting holes: MountingHole_Pad (one pin) on the 6.4 mm GND
    # pad-and-via ring footprint, so each frame screw bonds to the ground
    # plane instead of sitting in a copper keepout.  Fields go ABOVE the
    # symbol now - the GND power symbol hangs off the pin below it.
    for i, ref in enumerate(['H1', 'H2', 'H3', 'H4']):
        h = s.part(ref, 'Mechanical:MountingHole_Pad', 'M3 grommet hole, 4.0 mm, GND ring',
                   88.9 + 27.94 * i, 165.1, {'1': 'GND'}, manual='*',
                   foot='MARV_Packages:MountingHole_4.0mm_Grommet_Pad_Via',
                   refofs=(83.82 + 27.94 * i, 156.21), valofs=(83.82 + 27.94 * i, 158.75),
                   fsize=0.85)
        s.gnd(h['1'][0], 2.54)

    s.notes([N_IO_HDR, N_IORAILS, N_MECH,
             'IO ARRAY ROW MAP (row n = J6 pin n signal | J7 pin n power | J8 pin n GND)\n'
             + '\n'.join('%2d  %-4s %-11s | %-9s | GND  %s' % (i + 1, silk, sig, pwr, fn)
                          for i, (silk, sig, pwr, fn) in enumerate(IO_ROWS)),
             N_IOBULK, N_PWMMAP], [(10, 292), (140, 292), (270, 250)], 185)
    return s


def usb_debug_sheet():
    s = Sheet('usb_debug', 'BOARD 5 / USB-C, D+/D- series pair, SWD pads', 6, 'A4')
    s.title_note('BOARD 5 - J4 USB-C 2.0 RECEPTACLE, THE 27 R D+/D- SERIES PAIR, THE VBUS SENSE DIVIDER\n'
                 'AND THE J10 SWD LANDING PADS.  NO ON-BOARD USB ESD ARRAY - U8 USBLC6 was removed.')
    s.head('USB-C receptacle', 33.02, 40.64)
    j4 = s.part('J4', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB_C_PROGRAM_POWER', 50.8, 88.9,
                {'A1': 'GND', 'A4': 'USB_VBUS', 'A5': 'USB_CC1', 'A6': 'USB_DP', 'A7': 'USB_DM',
                 'A8': None, 'A9': 'USB_VBUS', 'A12': 'GND', 'B1': 'GND', 'B4': 'USB_VBUS',
                 'B5': 'USB_CC2', 'B6': 'USB_DP', 'B7': 'USB_DM', 'B8': None, 'B9': 'USB_VBUS',
                 'B12': 'GND', 'S1': 'GND'},
                foot='MARV_Packages:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
                manual='*', refofs=(38.1, 46.99))
    # VBUS (A4/A9/B4/B9 are one point on the symbol) out to the right
    vb = s.route(j4['A4'][0], (114.3, 73.66))
    s.label('USB_VBUS', vb, RIGHT)
    s.flag('USB_VBUS', (99.06, 73.66))
    c7 = s.cap('C7', '1u / 10 V X7R 0402', 107.95, 83.82, valofs=(110.49, 85.09), fsize=0.85)
    s.wire((107.95, 73.66), c7['1'][0])
    s.gnd(c7['2'][0], 3.81)
    # shell and GND pins
    s.route(j4['A1'][0], (50.8, 121.92))
    s.route(j4['SH'][0], (43.18, 121.92), (50.8, 121.92))
    s.gnd((50.8, 121.92), 5.08)
    # CC pull-downs
    s.head('CC pull-downs', 33.02, 130.81, 1.27)
    cc1 = s.route(j4['A5'][0], (76.2, 78.74), (76.2, 116.84))
    r4 = s.res('R4', '5.1k / 1%', 76.2, 124.46, valofs=(78.74, 125.73), fsize=0.85)
    s.wire(cc1, r4['1'][0])
    s.gnd(r4['2'][0], 3.81)
    s.label('USB_CC1', s.wire((76.2, 99.06), (86.36, 99.06)), RIGHT)
    cc2 = s.route(j4['B5'][0], (71.12, 81.28), (71.12, 116.84), (60.96, 116.84))
    r5 = s.res('R5', '5.1k / 1%', 60.96, 124.46, valofs=(31.75, 125.73), fsize=0.85)
    s.wire(cc2, r5['1'][0])
    s.gnd(r5['2'][0], 3.81)
    s.label('USB_CC2', s.wire((66.04, 116.84), (66.04, 123.19)), DOWN)
    # D- and D+ from the receptacle straight into the 27 R series pair.  U8,
    # the USBLC6-2SC6 ESD array, is REMOVED (DESIGN_SPEC "Decisions": JLC
    # Extended, dropped), and with it the one crossover this page used to
    # have - the two pairs no longer cross anywhere.
    s.head('D+/D- series pair - no ESD array', 116.84, 60.96, 1.27)
    s.route(j4['A7'][0], (81.28, 86.36), (81.28, 88.9))
    s.route(j4['B7'][0], (81.28, 88.9))
    s.route((81.28, 86.36), (104.14, 86.36), (104.14, 104.14), (146.05, 104.14))
    s.label('USB_DM', s.wire((95.25, 86.36), (95.25, 81.28)), UP)
    s.route(j4['A6'][0], (86.36, 91.44), (86.36, 93.98))
    s.route(j4['B6'][0], (86.36, 93.98))
    s.route((86.36, 93.98), (99.06, 93.98), (99.06, 123.19), (146.05, 123.19))
    s.label('USB_DP', s.wire((113.03, 123.19), (113.03, 128.27)), DOWN)
    r23 = s.res('R23', '27 / 1%, USB D- series', 149.86, 104.14, rot=HORZ,
                refofs=(144.78, 100.33), valofs=(144.78, 96.52), fsize=0.85)
    s.label('USB_DM_RP', s.wire(r23['2'][0], (168.91, 104.14)), RIGHT)
    r22 = s.res('R22', '27 / 1%, USB D+ series', 149.86, 123.19, rot=HORZ,
                refofs=(144.78, 119.38), valofs=(144.78, 129.54), fsize=0.85)
    s.label('USB_DP_RP', s.wire(r22['2'][0], (168.91, 123.19)), RIGHT)

    # VBUS sense divider
    s.head('VBUS_SENSE divider (10k / 15k)', 196.85, 33.02, 1.27)
    r29 = s.res('R29', '10k / 1%, VBUS top', 209.55, 60.96, valofs=(212.09, 62.23), fsize=0.85)
    s.label('USB_VBUS', s.wire(r29['1'][0], (209.55, 49.53)), UP)
    r30 = s.res('R30', '15k / 1%, VBUS bottom', 209.55, 81.28, valofs=(212.09, 82.55), fsize=0.85)
    s.wire(r29['2'][0], r30['1'][0])
    s.gnd(r30['2'][0], 3.81)
    c49 = s.cap('C49', '100n / 16 V X7R, ADC0', 240.03, 81.28, valofs=(242.57, 82.55), fsize=0.85)
    s.route((209.55, 71.12), (240.03, 71.12), c49['1'][0])
    s.gnd(c49['2'][0], 3.81)
    s.label('VBUS_SENSE', s.wire((233.68, 71.12), (233.68, 62.23)), UP)

    # SWD landing pads
    s.head('SWD landing pads', 196.85, 113.03, 1.27)
    j10 = s.part('J10', 'Connector_Generic:Conn_01x03', 'DBG pads (SWCLK SWDIO GND)',
                 209.55, 130.81, {'1': 'SWCLK', '2': 'SWDIO', '3': 'GND'},
                 foot='MARV_Packages:PadRow_1x03_P2.00mm', mirror='y',
                 manual=('3',), stub=7.62, refofs=(201.93, 120.65))
    s.gnd(j10['3'][0], 7.62, RIGHT)

    s.notes([N_J10, N_VBUS_IN2], [(10, 206)], 148)
    return s


def mcu_sheet():
    s = Sheet('mcu', 'BOARD 1 / RP2354B', 5, 'A3')
    s.title_note('BOARD 1 - RP2354B, QFN-80, 2 MB IN-PACKAGE QSPI FLASH.  Digital rails on V3V3_SYS, core DVDD\n'
                 'from the on-chip buck.  Supply pins fan out on the left into one decoupling group per rail.')
    nets = {}
    for pin in ('5', '15', '24', '29', '41', '50', '60', '76'):
        nets[pin] = V3
    nets.update({'68': V3, '69': V3, '64': V3})
    nets.update({'59': ANA, '61': 'VREG_AVDD'})
    nets.update({'10': 'DVDD', '32': 'DVDD', '51': 'DVDD', '63': 'VREG_LX', '65': 'DVDD',
                 '62': 'GND', '81': 'GND'})
    nets.update({'30': 'XIN', '31': 'XOUT', '33': 'SWCLK', '34': 'SWDIO', '35': 'MCU_RUN'})
    nets.update({'66': 'USB_DM_RP', '67': 'USB_DP_RP'})
    nets.update({'70': 'QSPI_SD3', '71': 'QSPI_SCLK', '72': 'QSPI_SD0', '73': 'QSPI_SD2',
                 '74': 'QSPI_SD1', '75': 'QSPI_SS'})
    nets.update({pin: net for pin, gpio, net, fn in MCU_GPIO})
    hand = ('5', '15', '24', '29', '41', '50', '60', '76', '68', '69', '64', '59', '61',
            '10', '32', '51', '63', '65', '62', '81', '30', '31', '35', '75', '22', '23')
    u20 = s.part('U20', 'MCU_RaspberryPi:RP2354B', 'RP2354B', 241.3, 149.86, nets,
                 foot='MARV_Packages:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm',
                 manual=hand, stub=7.62, refofs=(220.98, 88.9), fsize=0.9)
    s.route(u20['62'][0], (238.76, 213.36), (241.3, 213.36))
    s.route(u20['81'][0], (241.3, 213.36))
    s.gnd((241.3, 213.36), 5.08)

    # --- supply pins fan out to the left, one lane each, one group per rail ---
    s.head('Supply rails and decoupling', 12.7, 60.96)
    lanes = [('61', 91.44, 180.34), ('68', 88.9, 154.94), ('59', 86.36, 129.54),
             ('69', 83.82, 104.14), ('5', 81.28, 45.72), ('64', 78.74, 12.7)]
    turn = {}
    for pin, lane, x in lanes:
        turn[pin] = s.route(u20[pin][0], (u20[pin][0][0], lane), (x, lane), (x, 104.14))

    # VREG_VIN: 4.7 uF at the core-regulator input
    c39 = s.cap('C39', '4.7u / 10 V X5R 0402, VREG_VIN', 12.7, 118.11,
                valofs=(15.24, 119.38), fsize=0.8)
    s.wire(turn['64'], c39['1'][0])
    s.gnd(c39['2'][0], 3.81)
    s.label(V3, s.wire((12.7, 106.68), (25.4, 106.68)), RIGHT)

    # IOVDD: the design-guide 100 nF per pin, one ladder
    s.capcol(45.72, 113.03, 62.23,
             [('C%d' % (30 + i), '100n / 16 V X7R, IOVDD pin %s' % p, {'fsize': 0.8})
              for i, p in enumerate('5 15 24 29 41 50 60 76'.split())], valx=64.77)
    s.wire(turn['5'], (45.72, 113.03))
    s.gnd((62.23, 166.37), 3.81)
    s.label(V3, s.wire((45.72, 106.68), (58.42, 106.68)), RIGHT)

    # USB_OTP_VDD and QSPI_IOVDD share C38 (design-guide exception)
    c38 = s.cap('C38', '100n / 16 V X7R, pins 68+69', 104.14, 118.11,
                valofs=(106.68, 119.38), fsize=0.8)
    s.wire(turn['69'], c38['1'][0])
    s.gnd(c38['2'][0], 3.81)
    s.label(V3, s.wire((104.14, 106.68), (116.84, 106.68)), RIGHT)
    s.label(V3, s.wire(turn['68'], (167.64, 104.14)), RIGHT)

    # ADC_AVDD, the only pin left on the analog rail
    c40 = s.cap('C40', '100n / 16 V X7R, ADC_AVDD', 129.54, 118.11,
                valofs=(132.08, 119.38), fsize=0.8)
    s.wire(turn['59'], c40['1'][0])
    s.gnd(c40['2'][0], 3.81)
    s.label(ANA, s.wire((129.54, 106.68), (142.24, 106.68)), RIGHT)

    # VREG_AVDD: 33 R + 4.7 uF from V3V3_SYS (design guide Sec 2.1)
    r20 = s.res('R20', '33 / 1%, VREG_AVDD filter', 180.34, 114.3, rot=180,
                valofs=(145.03, 113.03), fsize=0.75)
    s.wire(turn['61'], r20['2'][0])
    s.label(V3, s.route(r20['1'][0], (180.34, 125.73), (167.64, 125.73)), LEFT)
    s.route(turn['61'], (180.34, 101.6), (170.18, 101.6))
    c41 = s.cap('C41', '4.7u / 10 V X5R 0402, VREG_AVDD', 170.18, 109.22,
                valofs=(140.97, 129.54), fsize=0.75)
    s.wire((170.18, 101.6), c41['1'][0])
    s.gnd(c41['2'][0], 3.81)
    s.flag('VREG_AVDD', (175.26, 101.6))
    s.label('VREG_AVDD', s.wire((180.34, 96.52), (193.04, 96.52)), RIGHT)

    # --- core regulator: VREG_LX -> L20 -> DVDD, on the right ---
    s.head('On-chip core regulator', 290.83, 26.67)
    rl = [('63', 86.36, 299.72), ('65', 88.9, 320.04), ('10', 91.44, 340.36)]
    rt = {}
    for pin, lane, x in rl:
        rt[pin] = s.route(u20[pin][0], (u20[pin][0][0], lane), (x, lane), (x, 55.88))
    l20 = s.ind('L20', '3.3u, 0806 AOTA-B201610S3R3', 307.34, 55.88, rot=HORZ,
                foot='Inductor_SMD:L_Murata_DFE201610P', refofs=(303.53, 41.91),
                valofs=(296.33, 44.45), fsize=0.8)
    s.wire(rt['63'], l20['1'][0])
    s.label('VREG_LX', s.wire((299.72, 68.58), (287.02, 68.58)), LEFT)
    dv = s.route(l20['2'][0], (350.52, 55.88))
    s.wire(rt['65'], (320.04, 55.88))
    s.wire(rt['10'], (340.36, 55.88))
    s.label('DVDD', s.wire((330.2, 55.88), (330.2, 48.26)), UP)
    s.flag('DVDD', (345.44, 55.88))
    s.capcol(350.52, 66.04, 367.03,
             [('C42', '100n / 16 V X7R, DVDD pin 10', {'fsize': 0.8}),
              ('C43', '100n / 16 V X7R, DVDD pin 32', {'fsize': 0.8}),
              ('C44', '100n / 16 V X7R, DVDD pin 51', {'fsize': 0.8}),
              ('C45', '4.7u / 10 V X5R 0402, DVDD bulk', {'fsize': 0.8})], valx=369.57)
    s.wire(dv, (350.52, 66.04))
    s.gnd((367.03, 88.9), 3.81)

    # --- RUN / BOOTSEL switches, right at the pins they strap ---
    s.head('Reset and BOOTSEL', 168.91, 140.97, 1.27)
    sw1 = s.part('SW1', 'Switch:SW_Push', 'RESET (RUN to GND)', 193.04, 116.84,
                 {'1': 'MCU_RUN', '2': 'GND'}, foot='Button_Switch_SMD:SW_SPST_B3U-1000P',
                 mirror='y', manual='*',
                 refofs=(185.42, 109.22), valofs=(185.42, 111.76), fsize=0.8)
    s.wire(sw1['1'][0], u20['35'][0])
    s.gnd(sw1['2'][0], 5.08, LEFT)
    s.label('MCU_RUN', (205.74, 111.76), RIGHT)
    # RUN pull-up.  It used to be the TPS62913's open-drain PWR_GOOD output
    # through this same 100k, which held RUN down until the buck declared
    # V3V3_SYS in regulation; the AP63203 has no PG pin, so R10 is a plain
    # pull-up to V3V3_SYS now and the RP2350's always-on brown-out detector
    # is what holds the core in reset below the rail (design guide Sec 2.2).
    r10 = s.res('R10', '100k, RUN pull-up', 205.74, 104.14,
                refofs=(196.85, 100.33), valofs=(190.5, 107.95), fsize=0.8)
    s.wire((205.74, 116.84), r10['2'][0])
    s.label(V3, s.wire(r10['1'][0], (205.74, 96.52)), UP)
    r24 = s.res('R24', '1k, BOOTSEL strap', 204.47, 134.62, rot=270,
                refofs=(199.39, 130.81), valofs=(186.69, 143.51), fsize=0.8)
    s.wire(r24['1'][0], u20['75'][0])
    s.label('QSPI_SS', s.wire((212.09, 134.62), (212.09, 129.54)), UP)
    sw2 = s.part('SW2', 'Switch:SW_Push', 'BOOTSEL (via R24)', 185.42, 134.62,
                 {'1': 'BOOT_BTN', '2': 'GND'}, foot='Button_Switch_SMD:SW_SPST_B3U-1000P',
                 mirror='y', manual='*',
                 refofs=(177.8, 127), valofs=(177.8, 129.54), fsize=0.8)
    s.wire(r24['2'][0], sw2['1'][0])
    s.gnd(sw2['2'][0], 5.08, LEFT)
    s.label('BOOT_BTN', s.wire((195.58, 134.62), (195.58, 129.54)), UP)

    # --- crystal ---
    s.head('12 MHz crystal', 152.4, 160.02, 1.27)
    y1 = s.part('Y1', 'Device:Crystal_GND24', '12 MHz TAXM12M4RFBCCT2T, CL 12 pF',
                168.91, 175.26, {'1': 'XIN', '2': 'GND', '3': 'XTAL_DRV', '4': 'GND'},
                foot='Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm', mirror='y', manual='*',
                refofs=(157.48, 166.37), valofs=(157.48, 168.91), fsize=0.8)
    s.route(u20['30'][0], (190.5, 154.94), (190.5, 175.26), y1['1'][0])
    s.label('XIN', s.wire((190.5, 161.29), (180.34, 161.29)), LEFT)
    s.gnd(y1['2'][0], 5.08)
    c46 = s.cap('C46', '18p / 50 V C0G', 177.8, 185.42, foot='Capacitor_SMD:C_0402_1005Metric',
                valofs=(180.34, 186.69), fsize=0.8)
    s.route((177.8, 175.26), c46['1'][0])
    s.gnd(c46['2'][0], 3.81)
    r21 = s.res('R21', '1k / 1%, crystal drive limit', 190.5, 201.93, rot=270,
                refofs=(185.42, 198.12), valofs=(172.72, 207.01), fsize=0.8)
    s.route(u20['31'][0], (196.85, 165.1), (196.85, 201.93), r21['1'][0])
    s.label('XOUT', s.wire((196.85, 168.91), (186.69, 168.91)), LEFT)
    s.route(r21['2'][0], (152.4, 201.93), (152.4, 175.26), y1['3'][0])
    s.label('XTAL_DRV', s.wire((152.4, 196.85), (163.83, 196.85)), RIGHT)
    c47 = s.cap('C47', '18p / 50 V C0G', 143.51, 193.04, foot='Capacitor_SMD:C_0402_1005Metric',
                valofs=(127, 194.31), fsize=0.8)
    s.route((152.4, 185.42), (143.51, 185.42), c47['1'][0])
    s.gnd(c47['2'][0], 3.81)

    # --- I2C1 pull-ups, past the GPIO label column ---
    s.head('I2C1 pull-ups', 355.6, 140.97, 1.27)
    sda = s.route(u20['22'][0], (322.58, 157.48))
    s.label('MAG_SDA', sda, RIGHT)
    r25 = s.res('R25', '4.7k, I2C1 SDA pull-up', 309.88, 147.32, valofs=(312.42, 148.59),
                fsize=0.8)
    s.wire(r25['2'][0], (309.88, 157.48))
    s.label(V3, s.wire(r25['1'][0], (309.88, 138.43)), UP)
    scl = s.route(u20['23'][0], (345.44, 160.02))
    s.label('MAG_SCL', scl, RIGHT)
    r26 = s.res('R26', '4.7k, I2C1 SCL pull-up', 332.74, 147.32, valofs=(335.28, 148.59),
                fsize=0.8)
    s.wire(r26['2'][0], (332.74, 160.02))
    s.label(V3, s.wire(r26['1'][0], (332.74, 138.43)), UP)

    rows = ['%-7s %3s  %-12s %s' % (g, p_, n or '(no connect)', f) for p_, g, n, f in MCU_GPIO]
    s.note('GPIO MAP (pin = QFN-80 pin)\n' + '\n'.join(rows[:24]), 10, 222, 0.85)
    s.note('\n' + '\n'.join(rows[24:]), 63.5, 222, 0.85)
    s.notes([N_MCU_HDR, N_PORTNAMES, N_SPAREIO, N_XTAL], [(140, 292), (265, 250)], 222)
    return s


PAGES = [('power_vbat', power_vbat_sheet), ('power_or', power_or_sheet),
         ('power_3v3', power_3v3_sheet), ('mcu', mcu_sheet), ('usb_debug', usb_debug_sheet),
         ('imu', imu_sheet), ('baro', baro_sheet), ('highg', highg_sheet), ('sd', sd_sheet),
         ('qspi_expansion', qspi_sheet), ('io_block', io_block_sheet)]

ROOT_NOTE = ('MARV V2 flight controller - schematic index.  One page per subsystem; on each page the IC is drawn\n'
             'with its own decoupling, pull-ups, series resistors, test points and connectors wired to it, and a\n'
             'global label is used only where a net leaves the page.  See DESIGN_SPEC.md for the design itself.\n'
             '\n'
             'Inputs: regulated 5 V from an EXTERNAL BEC on the MicoAir AM32 ESC pad row J3 pin 7, and USB VBUS.\n'
             'J3 pin 9 brings raw pack VBAT in as a SENSE wire only - no load, no bulk, no copper zone.\n'
             'Rails: 5V_IN is the BEC rail and the servo/module bus; V5_SYS is 5V_IN OR USB through the Q1/D1 OR and\n'
             'feeds only the two 3.3 V regulators and the status LED; V3V3_SYS from the AP63203 buck, V3V3_ANA from\n'
             'the TPS7A20 LDO.')


def build():
    sheets = [fn() for name, fn in PAGES]
    root = ['(kicad_sch (version 20250114) (generator "eeschema") (uuid ' + uid('power-root')
            + ') (paper "A3") (title_block (title "MARV-V2 - schematic index") (date "2026-09-16") '
              '(rev "P0 - NOT FOR FAB")) (lib_symbols)']
    root.append('(text ' + q(ROOT_NOTE) + ' (at 15 14 0) (effects (font (size 1.6 1.6)) '
                '(justify left top)) (uuid ' + uid('root-note') + '))')
    for i, sh in enumerate(sheets):
        x, y = 15 + 135 * (i // 4), 50 + 40 * (i % 4)
        root.append(
            f'(sheet (at {x} {y}) (size 120 28) (fields_autoplaced yes) '
            f'(stroke (width 0.1524) (type default)) (fill (color 0 0 0 0.0000)) (uuid {sh.id}) '
            f'(property "Sheetname" {q(sh.title)} (at {x} {y - 1} 0) (effects (font (size 1.27 1.27)) '
            f'(justify left bottom))) (property "Sheetfile" "{sh.name}.kicad_sch" (at {x} {y + 29} 0) '
            f'(effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project "MARV-V2" (path "/{uid("power-root")}" (page "{sh.page}")))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n')
    files = {'MARV-V2.kicad_sch': '\n'.join(root).replace('(fields_autoplaced yes)', '(fields_autoplaced)')}
    files.update({sh.name + '.kicad_sch': sh.render() for sh in sheets})
    files['power_bom.csv'] = ('Reference,Value,Footprint,Sheet,Fit\n'
                              + '\n'.join(','.join(q(v) for v in row)
                                          for sh in sheets for row in sh.bom
                                          if not row[0].startswith('#')) + '\n')
    backup = ROOT / 'backups/MARV-V2.before-power.kicad_sch'
    if not backup.exists():
        files['backups/MARV-V2.before-power.kicad_sch'] = (ROOT / 'MARV-V2.kicad_sch').read_text()
    custom = []
    for sheet in sheets:
        for lid, sy in sheet.libs.items():
            if lid.startswith('MARV_Power:') and not any(unquote(c[1]) == lid.split(':')[1] for c in custom):
                c = copy.deepcopy(sy)
                c[1] = q(lid.split(':')[1])
                custom.append(c)
    files['MARV_Power.kicad_sym'] = dump(['kicad_symbol_lib', ['version', '20250114'],
                                          ['generator', 'kicad_symbol_editor']] + custom) + '\n'
    table = (ROOT / 'sym-lib-table').read_text()
    if 'MARV_Power' not in table:
        files['sym-lib-table'] = table.rstrip()[:-1] + '\n  (lib (name \"MARV_Power\") (type \"KiCad\") (uri \"${KIPRJMOD}/MARV_Power.kicad_sym\") (options \"\") (descr \"Power symbols; OR output electrically passive\"))\n)\n'
    patch_files(files)
    # Sheets from the pre-reorganisation page set are no longer part of the
    # hierarchy; leaving them on disk would give a reader two versions of the
    # same circuit.
    keep = {'MARV-V2.kicad_sch'} | {sh.name + '.kicad_sch' for sh in sheets}
    stale = sorted(p.name for p in ROOT.glob('*.kicad_sch') if p.name not in keep)
    for name in stale:
        (ROOT / name).unlink()
    refmap = {}
    for sh in sheets:
        for row in sh.bom:
            if not row[0].startswith('#'):
                refmap[row[0]] = sh.name
    (ROOT / 'reports' / 'sheet-map.json').write_text(
        json.dumps({'root': uid('power-root'),
                    'sheets': {sh.name: sh.id for sh in sheets},
                    'refs': refmap}, indent=1, sort_keys=True) + '\n')
    print('sheets: %d  parts: %d  removed stale: %s'
          % (len(sheets), len(refmap), ', '.join(stale) or 'none'))
    if COLLISIONS:
        print('LAYOUT COLLISIONS (%d):' % len(COLLISIONS))
        for c in COLLISIONS:
            print('   ' + c)
    else:
        print('LAYOUT: no text/symbol/wire collisions')


if __name__ == '__main__':
    if '--inspect' in sys.argv:
        for libid in ['Regulator_Switching:TPS62913', 'Regulator_Linear:TPS7A20xxxDBV',
                      'Connector:USB_C_Receptacle_USB2.0_16P', 'Power_Protection:USBLC6-2SC6']:
            print(libid, [(unquote(first(p, 'number')[1]), unquote(first(p, 'name')[1]), p[1])
                          for p in pins(symbol(libid))])
    else:
        build()
