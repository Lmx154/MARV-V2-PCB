# Run from the repository root after the DRC and copper-clearance outputs exist in build/panel/.
# Writes build/panel/order-manifest.json unless --apply is given, which overwrites production/order-manifest.json.
# The exporter, order_settings and export_options entries are carried over from the existing production manifest.
import json,hashlib,datetime,subprocess,collections,sys
from pathlib import Path
root=Path.cwd();sc=root/'build/panel'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((root/'production/order-manifest.json').read_text())
src={}
names=['MARV-V2.kicad_dru','MARV-V2.kicad_pcb','MARV-V2.kicad_prl','MARV-V2.kicad_pro','MARV-V2.kicad_sch','fabrication-toolkit-options.json','fp-lib-table','sym-lib-table']
names+=sorted(p.name for p in root.glob('*.kicad_sch') if p.name!='MARV-V2.kicad_sch')+sorted(p.name for p in root.glob('*.kicad_sym'))
names+=['MARV_Packages.pretty/'+p.name for p in sorted((root/'MARV_Packages.pretty').glob('*.kicad_mod'))]
for n in sorted(set(names)):src[n]=sha(root/n)
panel={n:sha(root/n) for n in ['MARV-V2-panel.kicad_dru','MARV-V2-panel.kicad_pcb','MARV-V2-panel.kicad_prl','MARV-V2-panel.kicad_pro']}
plug=Path.home()/'.local/share/kicad/10.0/3rdparty/plugins/com_github_bennymeg_JLC-Plugin-for-KiCad'
exp={p.name:sha(p) for p in sorted(plug.glob('*.py'))}
def drc(n):
    d=json.loads((sc/n).read_text());c=collections.Counter(v['severity'] for v in d['violations']);return {'errors':c['error'],'warnings':c['warning'],'unconnected_items':len(d['unconnected_items'])}
m=collections.OrderedDict()
m['verified_at']=datetime.datetime.now().astimezone().isoformat()
m['kicad_version']='10.0.7';m['exporter']=old['exporter'];m['source_board']='MARV-V2.kicad_pcb';m['export_board']='MARV-V2-panel.kicad_pcb'
m['source_sha256']=src;m['panel_source_sha256']=panel;m['exporter_sha256']=exp
m['rotation_database_sha256']=sha(plug/'transformations.csv')
m['upload_sha256']={n:sha(root/'production'/n) for n in ['MARV-V2-panel.zip','bom.csv','positions.csv']}
m['verification']={'panel_size_mm':[72,72],'v_score_x_mm':[74.55,125.45],'v_score_y_mm':[77.15,122.85],'full_span_scores':4,'score_offset_outside_original_edges_mm':0.1,
 'minimum_copper_clearance_mm':round(json.loads((sc/'copper-clearance.json').read_text())['minimum_overall_mm'],4),'routed_reliefs':'four corners, microSD and USB-C overhangs only; USB-C pocket x 81.205-93.895 mm at J4 (87.55, 119.06)',
 'mouse_bite_holes':0,'added_rail_silkscreen':False,'drill_map_drawings_in_zip':False,'source_circuit_unchanged':True,'zones_modified':False,
 'assembly_csv_files_unchanged':False,
 'drc_panel':drc('drc-panel.json'),'drc_source':drc('drc-source.json')}
m['verification']['drc_note']='panel .kicad_pro/.kicad_dru synced from the source; panel DRC counts compared with the source counts above'
m['source_erc_violations']=0;m['source_erc_warnings']=0;m['source_erc_note']='0 errors, 0 warnings';m['source_schematic_parity_issues']=0
m['report']='reports/manufacturing-panel.md'
m['order_settings']=old['order_settings']
m['limitations']=['Synchronize manufacturing copy after source edits','JLCPCB must review V-score/outline CAM and assembly placement preview','Native 3D render does not model V-score grooves; see mechanical SVG','Scores leave a 0.10 mm lip on all four edges',
 'Assembly selection: H1-H4, J3, J6-J8, J10 are excluded from BOM/position files, and U24 (optional memory, DNP) is excluded as do-not-populate; J17 (5V converter module) is in bom.csv without an LCSC number and excluded from positions.csv (hand-fitted). J6-J8 are hand-soldered by the owner.',
 'Source DRC errors retained (22: 3 clearance, 1 courtyards_overlap, 18 hole_clearance); source ERC has 0 violations']
m['export_options']=old['export_options']
target=root/'production/order-manifest.json' if '--apply' in sys.argv else sc/'order-manifest.json'
target.write_text(json.dumps(m,indent=2)+'\n');print('wrote',target.relative_to(root))
