import math
import re
import sys

import pcbnew

import pslib

# swap the STM32 from LQFP208 to TFBGA265 in place. the new part goes at (CX, CY) rotated ROT; copper
# that belonged to the old pin ring is ripped (STM32 signal nets inside the old footprint area, plane
# stitching next to old pins), every item inside the new part's keep area is cleared (its via field goes
# through all layers), and bottom-side parts under the new part are moved to the nearest free spot.
# usage: bgaswap.py <board> <netlist>
PCB, NET = sys.argv[1:3]
CX, CY, ROT = 158.0, 99.0, 270
LIB = '/usr/share/kicad/footprints/Package_BGA.pretty'
NAME = 'TFBGA-265_14x14mm_Layout17x17_P0.8mm'
MM = 1e6
V = lambda x, y: pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))
keep = []

t = re.sub(r'\s+', ' ', open(NET).read())
pinnet = {}
for n in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]*)"\)(.*?)(?=\(net \(code|$)', t):
    for nd in re.finditer(r'\(node \(ref "U11"\) \(pin "([^"]+)"', n.group(2)):
        pinnet[nd.group(1)] = n.group(1)

b = pcbnew.LoadBoard(PCB)
zs = b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs))} | {'GND'}
old = b.FindFootprintByReference('U11')
oc = old.GetCourtyard(pcbnew.F_CrtYd).BBox()
R = (oc.GetLeft() / MM - 1, oc.GetTop() / MM - 1, oc.GetRight() / MM + 1, oc.GetBottom() / MM + 1)
oldpads = [(old.Pads()[k].GetNetname(), old.Pads()[k].GetPosition().x / MM, old.Pads()[k].GetPosition().y / MM)
           for k in range(len(old.Pads()))]
signal = {n for n, _, _ in oldpads if n and n not in planes and not n.startswith('unconnected')}
path, props = old.GetPath(), {f.GetName(): f.GetText() for f in old.GetFields()}
sheetname, sheetfile = old.GetSheetname(), old.GetSheetfile()
b.Remove(old)
keep.append(old)

new = pcbnew.FootprintLoad(LIB, NAME)
new.SetReference('U11')
new.SetValue('STM32H755XIH6')
new.SetFPID(pcbnew.LIB_ID('Package_BGA', NAME))
new.SetPath(path)
new.SetSheetname(sheetname)
new.SetSheetfile(sheetfile)
new.SetPosition(V(CX, CY))
new.SetOrientationDegrees(ROT)
b.Add(new)
keep.append(new)
missing = 0
for k in range(len(new.Pads())):
    p = new.Pads()[k]
    nn = pinnet.get(p.GetNumber())
    if nn is None:
        missing += 1
        continue
    ni = b.FindNet(nn)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(b, nn)
        b.Add(ni)
        keep.append(ni)
    p.SetNet(ni)
nc = new.GetCourtyard(pcbnew.F_CrtYd).BBox()
K = (nc.GetLeft() / MM - 1.5, nc.GetTop() / MM - 1.5, nc.GetRight() / MM + 1.5, nc.GetBottom() / MM + 1.5)
inbox = lambda x, y, r: r[0] < x < r[2] and r[1] < y < r[3]

ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
kill = []
for it in items:
    n = it.GetNetname()
    pts = ([(it.GetPosition().x / MM, it.GetPosition().y / MM)] if it.GetClass() == 'PCB_VIA'
           else [(it.GetStart().x / MM, it.GetStart().y / MM), (it.GetEnd().x / MM, it.GetEnd().y / MM)])
    if any(inbox(x, y, K) for x, y in pts):
        kill.append(it)
    elif n in signal and any(inbox(x, y, R) for x, y in pts):
        kill.append(it)
    elif n in planes and any(math.hypot(x - px, y - py) < 1.0 for x, y in pts for pn, px, py in oldpads if pn == n):
        kill.append(it)
for it in kill:
    b.Remove(it)
keep += kill
print('pads without a net in the netlist: %d; ripped %d tracks/vias' % (missing, len(kill)))



class KeepPlacer(pslib.Placer):
    # bottom parts must also stay out of the keep area under the bga (its vias go through every layer)
    def ok(self, f, gap=0.15, ignore=()):
        c = self.crt(f)
        if f.IsFlipped() and c[0] < K[2] and c[2] > K[0] and c[1] < K[3] and c[3] > K[1]:
            return False
        return pslib.Placer.ok(self, f, gap, ignore)


pl = KeepPlacer(b)
under = [r for r, f in pl.fps.items() if f.IsFlipped() and r != 'U11'
         and (lambda c: c[0] < K[2] and c[2] > K[0] and c[1] < K[3] and c[3] > K[1])(pl.crt(f))]
pl.rip(under)
moved = []
for r in sorted(under, key=lambda r: -len(pl.fps[r].Pads())):
    f = pl.fps[r]
    x, y = f.GetPosition().x / MM, f.GetPosition().y / MM
    # push out through the nearest edge of the keep area, then search from there
    d = {'L': x - K[0], 'R': K[2] - x, 'T': y - K[1], 'B': K[3] - y}
    e = min(d, key=d.get)
    tx, ty = {'L': (K[0] - 1.5, y), 'R': (K[2] + 1.5, y), 'T': (x, K[1] - 1.5), 'B': (x, K[3] + 1.5)}[e]
    # park it far away first so its own old spot does not count as free
    f.SetPosition(V(10, 10))
    try:
        got = pl.place(r, tx, ty, bottom=True, rmax=12.0) + ('B',)
    except SystemExit:
        # the old lqfp ring on top is free now: big parts that find no room below go there
        got = pl.place(r, tx, ty, bottom=False, rmax=12.0) + ('F',)
    moved.append((r, got))
b.Save(PCB)
print('new U11 at (%.1f, %.1f) rot %d, keep area %s' % (CX, CY, ROT, tuple(round(v, 1) for v in K)))
print('moved %d bottom parts out from under it:' % len(moved))
for r, g in moved:
    print('  %-5s -> %s (%.2f, %.2f) rot %d, %.1f mm from target' % (r, g[4], g[0], g[1], g[2], g[3]))
