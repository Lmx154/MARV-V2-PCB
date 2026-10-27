import csv,sys,re
import pcbnew
mm=pcbnew.ToMM
out=sys.argv[1] if len(sys.argv)>1 else 'production'  # directory holding bom.csv and positions.csv
b=pcbnew.LoadBoard('MARV-V2.kicad_pcb')
bom=list(csv.DictReader(open(out+'/bom.csv',encoding='utf-8-sig')))
pos={r['Designator']:r for r in csv.DictReader(open(out+'/positions.csv',encoding='utf-8-sig'))}
bomrefs=set()
for r in bom:
    for d in r['Designator'].split(','):bomrefs.add(d.strip())
fps={f.GetReference():f for f in b.GetFootprints()}
dnp=[r for r,f in fps.items() if f.GetAttributes()&pcbnew.FP_DNP]
print('BOM lines',len(bom),'BOM refs',len(bomrefs),'positions rows',len(pos),'source DNP parts',dnp)
top=[r for r in bomrefs if fps[r].GetLayerName()=='F.Cu']
print('BOM refs on top',len(top),'missing from positions',[r for r in top if r not in pos],'| BOM refs bottom',[r for r in bomrefs if fps[r].GetLayerName()!='F.Cu'])
print('DNP in BOM/positions',[r for r in dnp if r in bomrefs or r in pos])
print('positions not in BOM',sorted(set(pos)-bomrefs),' BOM not in positions',sorted(bomrefs-set(pos)))
print('positions on bottom',[r for r,v in pos.items() if v['Layer']!='top'])
print('tooling/fiducials in csv',[r for r in list(pos)+list(bomrefs) if r.startswith(('TOOL','FID'))])
for r in ['U20','J4','U7']:
    f=fps[r];x,y=mm(f.GetPosition().x),mm(f.GetPosition().y);p=pos[r]
    print(r,'source (%.3f,%.3f) rot %.1f'%(x,y,f.GetOrientationDegrees()),'-> csv',p['Mid X'],p['Mid Y'],p['Rotation'],p['Layer'],'| expected (x-100,100-y)= (%.3f,%.3f)'%(x-100,100-y))
