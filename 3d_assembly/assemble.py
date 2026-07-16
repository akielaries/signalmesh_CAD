import Part, FreeCAD as App
from FreeCAD import Vector, Placement, Rotation
P="/tmp/claude-1000/-home-akiel-trunk/4602618b-0541-43b7-a65c-53932c60a61e/scratchpad/assembly/"
log=open(P+"assemble.txt","w")
def L(s): log.write(s+"\n"); log.flush()

# --- STEP coord convention (verified): STEP(x,y,z) = (kicad_x, -kicad_y, z), F.Cu at z~0 ---
def K(x,y): return Vector(x,-y,0)   # kicad xy -> step xy (z set separately)

# connector centroids in KiCad coords
APM_J1=(103.17,142.69); APM_J3=(89.21,142.69)     # APM plugs, B.Cu
ACM_J5=(135.83,101.48); ACM_J6=(149.78,101.48)    # ACM sockets, B.Cu (mate J5<->J1, J6<->J3)
ACM_TANG=(142.80,101.48)                           # ACM top J1/J2 centroid (Tang mates here)

# assumed mechanical params (EDIT to match datasheet)
T_APM=1.6      # APM board thickness mm
T_ACM=1.6      # ACM board thickness mm
H_STACK=2.0    # DF40 mated stack height mm (board-gap) -- SET FROM HIROSE DATASHEET
H_TANG=2.0     # Tang<->ACM DF40 stack height mm

# --- ACM transform: 180 deg about Y (negates x,z: B.Cu faces up, rows run same dir), then translate ---
# after R: (x,y,z)->(-x,y,-z). Solve T so ACM_J5(step) lands on APM_J1(step).
sx5,sy5=ACM_J5[0],-ACM_J5[1]      # step coords of ACM.J5 pre-transform
ax1,ay1=APM_J1[0],-APM_J1[1]      # step coords of APM.J1
tx = ax1 - (-sx5)                  # -x after rot
ty = ay1 - ( sy5)
# Z: place ACM below APM. APM bottom ~ z=-T_APM ; ACM mating face after flip sits H below it.
tz = -(T_APM + H_STACK + T_ACM)
acm_rot=Rotation(Vector(0,1,0),180)
acm_pl=Placement(Vector(tx,ty,tz),acm_rot)

# validate: transform ACM.J5 and J6, check they land on APM.J1/J3
def apply(pl,x,y,z):
    v=pl.multVec(Vector(x,y,z)); return (v.x,v.y,v.z)
for nm,(kx,ky),(tgtx,tgty) in [("J5->J1",ACM_J5,APM_J1),("J6->J3",ACM_J6,APM_J3)]:
    gx,gy,gz=apply(acm_pl,kx,-ky,0)
    L("check %s: ACM lands (%.2f,%.2f) target APM (%.2f,%.2f)  dxy=(%.2f,%.2f)"%(nm,gx,gy,tgtx,-tgty,gx-tgtx,gy-(-tgty)))

# --- load shapes ---
L("loading boards...")
apm=Part.Shape(); apm.read(P+"APM.step")
acm=Part.Shape(); acm.read(P+"ACM.step"); acm.Placement=acm_pl
# Tang: center its bbox over the transformed ACM tang-connector area, below the ACM
tang=Part.Shape(); tang.read(P+"tang/Tang_Primer_25K_Step.step")
tb=tang.BoundBox
tgx,tgy,tgz=apply(acm_pl, ACM_TANG[0],-ACM_TANG[1],0)
# move tang so its bbox center sits under that point, gap below ACM
tang_pl=Placement(Vector(tgx-tb.Center.x, tgy-tb.Center.y, (tz - T_ACM - H_TANG) - tb.ZMax), Rotation())
tang.Placement=tang_pl
L("Tang bbox size %.1f x %.1f x %.1f (native)"%(tb.XLength,tb.YLength,tb.ZLength))

# --- interference check: bbox overlap ACM(placed) vs APM ---
def bb(s): b=s.BoundBox; return b
ba,bp=bb(acm),bb(apm)
zov = min(ba.ZMax,bp.ZMax)-max(ba.ZMin,bp.ZMin)
L("ACM placed Z[%.2f,%.2f]  APM Z[%.2f,%.2f]  z-overlap=%.2f (neg=clear gap)"%(ba.ZMin,ba.ZMax,bp.ZMin,bp.ZMax,zov))

# --- export combined ---
comp=Part.Compound([apm,acm,tang])
comp.exportStep(P+"STACK_ACM_APM_TANG.step")
L("wrote STACK_ACM_APM_TANG.step")
bc=comp.BoundBox
L("stack bbox %.1f x %.1f x %.1f"%(bc.XLength,bc.YLength,bc.ZLength))
log.close()
