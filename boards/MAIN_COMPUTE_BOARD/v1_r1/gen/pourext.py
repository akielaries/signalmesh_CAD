import sys

import pcbnew

# extend the In4 +1V35 and VADJ pours over decaps that sat outside them. the +1V35 extension is notched
# round four +3V3 stitch vias, each notch open to the main +3V3 plane so those vias keep their plane
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
zs = b.Zones()
EXT = {
    '+1V35': [(100.57, 127.6), (108.5, 127.6), (108.5, 141.5), (108.36, 141.5), (108.36, 139.4), (106.76, 139.4),
              (106.76, 141.5), (100.11, 141.5), (100.11, 139.4), (98.51, 139.4), (98.51, 141.5), (97.67, 141.5),
              (97.67, 139.4), (96.07, 139.4), (96.07, 141.5), (93.0, 141.5), (93.0, 129.1), (100.57, 129.1)],
    'VADJ': [(94.0, 53.6), (99.0, 53.6), (99.0, 62.0), (94.0, 62.0)],
}
keep = []
for net, pts in EXT.items():
    zs = b.Zones()     # re-read: adding a zone invalidates the earlier container
    src = [zs[i] for i in range(len(zs)) if zs[i].GetNetname() == net and zs[i].GetLayer() == b.GetLayerID('In4.Cu')][0]
    z = src.Duplicate(False).Cast()
    sps = pcbnew.SHAPE_POLY_SET()
    sps.NewOutline()
    for x, y in pts:
        sps.Append(int(x * MM), int(y * MM))
    z.SetOutline(sps)
    keep.append(sps)   # the zone keeps a pointer to this outline: it must outlive the loop
    z.SetZoneName(net.strip('+') + '_EXT')
    b.Add(z)
    keep.append(z)
filler = pcbnew.ZONE_FILLER(b)
zs = b.Zones()
filler.Fill([zs[i] for i in range(len(zs))])
in4 = b.GetLayerID('In4.Cu')
p3 = [zs[i] for i in range(len(zs)) if zs[i].GetNetname() == '+3V3' and zs[i].GetLayer() == in4]
ok = True
for x, y in ((96.87, 140.01), (99.31, 140.0), (107.56, 140.5), (99.77, 128.27)):
    # the via's annular ring area must touch +3V3 fill (the fill clears the drill, so probe its ring)
    hit = any(z.HitTestFilledArea(in4, pcbnew.VECTOR2I(int((x + dx) * MM), int((y + dy) * MM)))
              for z in p3 for dx, dy in ((0.45, 0), (-0.45, 0), (0, 0.45), (0, -0.45)))
    print('+3V3 via (%.2f, %.2f) still in +3V3 copper: %s' % (x, y, hit))
    ok = ok and hit
if not ok:
    raise SystemExit('a +3V3 via would be cut off: not saved')
b.Save(PCB)
print('pours extended and saved')
