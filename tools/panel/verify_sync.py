from pathlib import Path
import sys,json,collections
import pcbnew
sys.path.insert(0,str(Path.cwd()))
from tools.panel.sexpr import children,tokens
root=Path.cwd()
panel=Path(sys.argv[1]) if len(sys.argv)>1 else root/'MARV-V2-panel.kicad_pcb'  # panel file to check (default: the saved panel)
s=(root/'MARV-V2.kicad_pcb').read_text();p=panel.read_text()
sn=collections.Counter(s[a:b] for a,b in children(s));pn=collections.Counter(p[a:b] for a,b in children(p))
miss=sn-pn;add=pn-sn
print('source nodes missing from panel:',[(tokens(x)[1],' '.join(x.split())[:90]) for x in miss])
print('panel-only nodes:',dict(collections.Counter(tokens(x)[1] for x in add)))
S=pcbnew.LoadBoard(str(root/'MARV-V2.kicad_pcb'));P=pcbnew.LoadBoard(str(panel))
def fps(b):return {f.GetReference():(f.GetFPIDAsString(),f.GetPosition().x,f.GetPosition().y,round(f.GetOrientationDegrees(),6),f.GetLayerName(),f.m_Uuid.AsString()) for f in b.GetFootprints()}
fs,fp=fps(S),fps(P)
extra=set(fp)-set(fs);print('panel-only footprints',sorted(extra),'source-only',sorted(set(fs)-set(fp)))
diff=[r for r in fs if r in fp and fs[r]!=fp[r]];print('footprints in both:',len([r for r in fs if r in fp]),'differing:',diff)
print('source footprints',len(fs),'panel footprints',len(fp))
for name,f in [('tracks',lambda b:sum(1 for t in b.GetTracks() if t.GetClass()=='PCB_TRACK')),('vias',lambda b:sum(1 for t in b.GetTracks() if t.GetClass()=='PCB_VIA')),('zones',lambda b:len(list(b.Zones())))]:
 print(name,f(S),f(P))
def zsig(b,z):
 bb=z.GetBoundingBox();return (z.GetNetname(),b.GetLayerName(z.GetLayer()),bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom(),round(z.GetFilledArea()))
zs=collections.Counter(zsig(S,z) for z in S.Zones());zp=collections.Counter(zsig(P,z) for z in P.Zones())
print('zone (net,layer,bbox,filled area) multiset equal',zs==zp)
zsn=[x for x in sn if tokens(x)[1]=='zone'];print('zone nodes verbatim identical:',all(x in pn for x in zsn),len(zsn))
