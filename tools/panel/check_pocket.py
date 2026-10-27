import pcbnew,math,sys
mm=pcbnew.ToMM
for name in sys.argv[1:] or ['MARV-V2-panel.kicad_pcb']:
 b=pcbnew.LoadBoard(name);print(name)
 for d in b.GetDrawings():
  if d.GetLayer()==pcbnew.Edge_Cuts and isinstance(d,pcbnew.PCB_SHAPE):
   bb=d.GetBoundingBox()
   if mm(bb.GetTop())>=122.7 and mm(bb.GetBottom())<=124.8 and mm(bb.GetLeft())>80 and mm(bb.GetRight())<101:
    print('  ',d.GetShapeStr(),round(mm(d.GetStart().x),3),round(mm(d.GetStart().y),3),'->',round(mm(d.GetEnd().x),3),round(mm(d.GetEnd().y),3))
 j4=b.FindFootprintByReference('J4');cy=[s.GetBoundingBox() for s in j4.GraphicalItems() if s.GetLayer()==pcbnew.F_CrtYd]
 l=min(mm(x.GetLeft()) for x in cy);r=max(mm(x.GetRight()) for x in cy);bt=max(mm(x.GetBottom()) for x in cy)
 print('   J4 at',mm(j4.GetPosition().x),mm(j4.GetPosition().y),'courtyard x',l,r,'bottom',bt,'overhang below y=122.75:',round(bt-122.75,3))
 # whole footprint extents incl. pads and silk (no text)
 bb=j4.GetBoundingBox(False);print('   J4 bbox (no text) x',mm(bb.GetLeft()),mm(bb.GetRight()),'y bottom',mm(bb.GetBottom()))
 # capsule check: courtyard bottom corners inside the capsule?
 pk=[(mm(d.GetBoundingBox().GetLeft()),mm(d.GetBoundingBox().GetRight())) for d in b.GetDrawings() if d.GetLayer()==pcbnew.Edge_Cuts and d.GetShapeStr()=='Arc' and mm(d.GetBoundingBox().GetTop())>=122.7 and mm(d.GetBoundingBox().GetBottom())<=124.8 and mm(d.GetBoundingBox().GetLeft())>80]
 x0=min(p[0] for p in pk);x1=max(p[1] for p in pk);print('   capsule x',round(x0,3),round(x1,3),'margin L',round(l-x0,3),'R',round(x1-r,3),'y 122.75..124.75, courtyard bottom margin',round(124.75-bt,3))
 c0=(x0+1,123.75);c1=(x1-1,123.75)
 for cx in (l,r):
  d=math.hypot(cx-(c0[0] if cx==l else c1[0]),bt-123.75);print('   courtyard corner dist to end-arc centre',round(d,3),'< radius 1 :',d<1)
