# Usage (repository root): copper_clearance.py [panel.kicad_pcb] > build/panel/copper-clearance.json
# Full-span axis-aligned scores,
# conservative copper bounding boxes on all four copper layers (tracks, vias, pads, copper graphics, filled zones).
import pcbnew,json,sys
mm=pcbnew.ToMM
board=pcbnew.LoadBoard(sys.argv[1] if len(sys.argv)>1 else 'MARV-V2-panel.kicad_pcb');scores={'x':[74.55,125.45],'y':[77.15,122.85]}
layers=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu];items=[]
def add(desc,layer,bb):items.append((desc,board.GetLayerName(layer),mm(bb.GetLeft()),mm(bb.GetTop()),mm(bb.GetRight()),mm(bb.GetBottom())))
for t in board.GetTracks():
 for l in layers:
  if t.IsOnLayer(l) or (t.GetClass()=='PCB_VIA' and t.FlashLayer(l)):add(f'{t.GetClass()} {t.GetNetname()}',l,t.GetBoundingBox())
for fp in board.GetFootprints():
 for p in fp.Pads():
  for l in layers:
   if p.IsOnLayer(l):add(f'pad {fp.GetReference()}.{p.GetNumber()}',l,p.GetBoundingBox())
 for g in fp.GraphicalItems():
  if g.GetLayer() in layers:add(f'fp graphic {fp.GetReference()}',g.GetLayer(),g.GetBoundingBox())
for g in board.GetDrawings():
 if g.GetLayer() in layers:add('board graphic',g.GetLayer(),g.GetBoundingBox())
def zones():
 for z in board.Zones():yield z
 for fp in board.GetFootprints():
  for z in fp.Zones():yield z
for z in zones():
 for l in layers:
  if z.IsOnLayer(l):
   fp=z.GetFilledPolysList(l)
   if fp.OutlineCount():add(f'filled zone {z.GetNetname()}',l,fp.BBox())
res=[]
for axis,vals in scores.items():
 for s in vals:
  d=[]
  for desc,layer,l,t,r,b in items:
   lo,hi=(l,r) if axis=='x' else (t,b)
   if desc.split()[1].startswith(('TOOL','FID')):continue
   if (s<100 and hi<=s) or (s>100 and lo>=s):continue
   # distance from score to bbox (only meaningful for the side of the board it faces)
   dist=(lo-s) if s<100 else (s-hi)
   d.append((dist,desc,layer,lo if s<100 else hi))
  d.sort();res.append({'score_'+axis+'_mm':s,'minimum_conservative_copper_clearance_mm':d[0][0],'nearest_items':[[round(x[0],4),x[1],x[2],round(x[3],4)] for x in d[:6]]})
out={'method':'Minimum separation from full-span score to conservative copper bounding boxes on all four copper layers (tracks, vias, pads, copper graphics, filled zones)','results':res,'minimum_overall_mm':min(r['minimum_conservative_copper_clearance_mm'] for r in res),'items_checked':len(items)}
print(json.dumps(out,indent=1))
