import sys

import pcbnew
from sx import parse, find, first

import proute
import rlib

# in-place footprint swap from the schematic: replace/add the given refs (footprint, value, path, nets),
# keep the old part's position, place extras beside it, drop old stitching, re-stitch plane pads
PCB, NET, REFS = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
MM = 1e6
FPDIR = '/usr/share/kicad/footprints/'
root = parse(open(NET).read())
comps = {}
for c in find(first(root, 'components'), 'comp'):
    r = first(c, 'ref')[1]
    if r in REFS:
        props = {first(p, 'name')[1]: (first(p, 'value') or [0, ''])[1] for p in find(c, 'property')}
        sp = first(c, 'sheetpath')
        comps[r] = dict(value=first(c, 'value')[1], fp=first(c, 'footprint')[1], props=props,
                        sheet=first(sp, 'names')[1].strip('/'), spath=first(sp, 'tstamps')[1],
                        ts=first(c, 'tstamps')[1].split()[0])
pinnet = {}
for n in find(first(root, 'nets'), 'net'):
    for x in find(n, 'node'):
        if first(x, 'ref')[1] in REFS:
            pinnet[(first(x, 'ref')[1], first(x, 'pin')[1])] = first(n, 'name')[1]
b = pcbnew.LoadBoard(PCB)
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
anchor = None
old_pads = set()
for r in REFS:
    f = b.FindFootprintByReference(r)
    if f:
        anchor = anchor or (f.GetPosition(), f.GetOrientationDegrees())
        old_pads |= {key(f.Pads()[k].GetPosition()) for k in range(len(f.Pads()))}
        b.Remove(f)
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
vias, kill = set(), []
for t in items:
    if t.GetClass() != 'PCB_VIA':
        s, e = key(t.GetStart()), key(t.GetEnd())
        if s in old_pads or e in old_pads:
            kill.append(t)
            vias.add((t.GetNetname(), e if s in old_pads else s))
kill += [t for t in items if t.GetClass() == 'PCB_VIA' and (t.GetNetname(), key(t.GetPosition())) in vias]
for t in kill:
    b.Remove(t)
# 1210 parts side by side (3.4 mm pitch) centred on the old part, pads vertical
pos, rot = anchor
n = len(REFS)
for i, r in enumerate(REFS):
    c = comps[r]
    lib, name = c['fp'].split(':')
    fp = pcbnew.FootprintLoad(FPDIR + lib + '.pretty', name)
    fp.SetReference(r)
    fp.SetValue(c['value'])
    fp.SetFPIDAsString(c['fp'])
    fp.SetPath(pcbnew.KIID_PATH(c['spath'] + c['ts']))
    fp.SetSheetname(c['sheet'])
    fp.SetSheetfile(c['props'].get('Sheetfile', ''))
    for k in range(len(fp.Pads())):
        p = fp.Pads()[k]
        nn = pinnet.get((r, p.GetNumber()))
        if nn:
            p.SetNet(b.FindNet(nn))
    fp.SetAttributes(pcbnew.FP_SMD)
    b.Add(fp)
    fp.SetOrientationDegrees(90)
    fp.SetPosition(pcbnew.VECTOR2I(pos.x + int((i - (n - 1) / 2) * 3.4 * MM), pos.y))
b.Save(PCB)
bd = rlib.Board(PCB)
ok = fail = 0
for (x, y, hx, hy, nn, lays, rnd, p) in list(bd.pads):
    if p.GetParentFootprint().GetReference() not in REFS:
        continue
    st = []
    v = proute.drop_via(bd, (x, y), nn, (x, y + 1.0), st, radii=(0.6, 0.75, 0.9, 1.1, 1.3, 1.6))
    if v:
        bd.commit(st)
        ok += 1
    else:
        bd.unstage(st)
        fail += 1
bd.save()
print('swapped %s at (%.2f, %.2f); removed %d old stitch items; stitched %d pads, %d without room'
      % (REFS, pos.x / MM, pos.y / MM, len(kill), ok, fail))
