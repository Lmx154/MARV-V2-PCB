# Re-sync MARV-V2-panel.kicad_pcb from the CURRENT MARV-V2.kicad_pcb; only the USB-C pocket is re-derived from J4.
# Run from the repository root. Writes build/panel/MARV-V2-panel.kicad_pcb unless --apply is given,
# which overwrites the saved MARV-V2-panel.kicad_pcb (tooling holes and fiducials are carried over from it).
from pathlib import Path
import pcbnew,sys,math,json,hashlib
sys.path.insert(0,str(Path.cwd()))
from tools.panel.sexpr import children,tokens,node,replace_node
root=Path.cwd();check=root/'build/panel';check.mkdir(parents=True,exist_ok=True)
source=root/'MARV-V2.kicad_pcb';sourcehash=hashlib.sha256(source.read_bytes()).hexdigest();src=source.read_text()
prior=(root/'MARV-V2-panel.kicad_pcb').read_text()
# USB-C pocket: J4's courtyard x-span widened by 1.0 mm on each side.
board=pcbnew.LoadBoard(str(source));j4=board.FindFootprintByReference('J4')
cy=[s.GetBoundingBox() for s in j4.GraphicalItems() if s.GetLayer()==pcbnew.F_CrtYd]
cx0=min(pcbnew.ToMM(b.GetLeft()) for b in cy);cx1=max(pcbnew.ToMM(b.GetRight()) for b in cy);cy1=max(pcbnew.ToMM(b.GetBottom()) for b in cy)
usb=(round(cx0-1.0,3),round(cx1+1.0,3));print('J4 courtyard x',cx0,cx1,'bottom',cy1,'-> pocket',usb)
edits=[]
for a,b in children(src):
 part=src[a:b];kind=tokens(part)[1]
 if kind=='gr_line' and '(layer "Edge.Cuts")' in part:edits.append((a,b,''))
assert len(edits)==4
result=src
for a,b,new in reversed(edits):result=result[:a]+new+result[b:]
extra=[]
for a,b in children(prior):
 part=prior[a:b]
 if tokens(part)[1]=='footprint':
  ref=json.loads(tokens(node(part,'property','"Reference"'))[3])
  if ref in ['TOOL1','TOOL2','TOOL3']:extra.append(part)
  elif ref in ['FID1','FID2','FID3']:
   x,y={'FID1':(69,72),'FID2':(131,72),'FID3':(69,128)}[ref]
   extra.append(replace_node(part,('at',),f'(at {x} {y})'))
assert len(extra)==6
features=pcbnew.BOARD()
def pt(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def line(a,b,layer=pcbnew.Edge_Cuts):
 o=pcbnew.PCB_SHAPE(features);o.SetShape(pcbnew.SHAPE_T_SEGMENT);o.SetStart(pt(*a));o.SetEnd(pt(*b));o.SetLayer(layer);o.SetWidth(pcbnew.FromMM(.05));features.Add(o)
def arc(a,m,b):
 o=pcbnew.PCB_SHAPE(features);o.SetShape(pcbnew.SHAPE_T_ARC);o.SetArcGeometry(pt(*a),pt(*m),pt(*b));o.SetLayer(pcbnew.Edge_Cuts);o.SetWidth(pcbnew.FromMM(.05));features.Add(o)
for a,b in zip([(64,64),(136,64),(136,136),(64,136)],[(136,64),(136,136),(64,136),(64,64)]):line(a,b)
for sx,sy in [(1,1),(-1,1),(1,-1),(-1,-1)]:
 def tr(p):return (100+sx*(p[0]-100),100+sy*(p[1]-100))
 def ln(a,b):line(tr(a),tr(b))
 def ac(a,m,b):arc(tr(a),tr(m),tr(b))
 ln((74.65,79.25),(74.65,79.75))
 ac((74.65,79.75),(73.65,80.75),(72.65,79.75))
 ln((72.65,79.75),(72.65,79.25))
 r=4/math.sqrt(2);ac((72.65,79.25),(76.65-r,79.25-r),(76.65,75.25))
 ln((76.65,75.25),(77.15,75.25))
 ac((77.15,75.25),(78.15,76.25),(77.15,77.25))
 ln((77.15,77.25),(76.65,77.25))
def capsule(x0,x1,y0,y1):
 r=(y1-y0)/2;cy=(y0+y1)/2
 line((x0+r,y0),(x1-r,y0));arc((x1-r,y0),(x1,cy),(x1-r,y1))
 line((x1-r,y1),(x0+r,y1));arc((x0+r,y1),(x0,cy),(x0+r,y0))
capsule(81.5,99.3,75.25,77.25)  # microSD overhang (J11 unchanged)
capsule(usb[0],usb[1],122.75,124.75)  # USB-C overhang (J4, re-derived)
for x in [74.55,125.45]:line((x,64),(x,136),pcbnew.User_1)
for y in [77.15,122.85]:line((64,y),(136,y),pcbnew.User_1)
for x,y in [(79.2,66.5),(120.8,66.5),(68,80),(68,120)]:
 t=pcbnew.PCB_TEXT(features);t.SetText('V-CUT');t.SetPosition(pt(x,y));t.SetTextSize(pt(1,1));t.SetTextThickness(pcbnew.FromMM(.15));t.SetLayer(pcbnew.User_1);features.Add(t)
feature_path=check/'features.kicad_pcb';pcbnew.SaveBoard(str(feature_path),features);txt=feature_path.read_text()
for a,b in children(txt):
 part=txt[a:b]
 if tokens(part)[1] in ['gr_line','gr_arc','gr_text']:extra.append(part)
end=result.rfind(')');result=result[:end]+'\n\t'+'\n\t'.join(extra)+'\n'+result[end:]
target=root/'MARV-V2-panel.kicad_pcb' if '--apply' in sys.argv else check/'MARV-V2-panel.kicad_pcb'
target.write_text(result);print('wrote',target.relative_to(root))
assert hashlib.sha256(source.read_bytes()).hexdigest()==sourcehash
print('source sha256',sourcehash)
