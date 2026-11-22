import math
import os
import sys
import time

import pcbnew

import negroute
import proute
import pslib
import rlib

# rip or re-route a list of nets with negotiated congestion on all five signal layers.
#   rip:   remove every track/via of the nets except the dogbones at U100/U11 balls (ball stub + via)
#   route: join each net's terminals (pads, kept dogbones) by a minimum spanning tree of via-to-via legs
# usage: reroute.py <board> rip|route NET [NET ...]
PCB, STEP, NETS = sys.argv[1], sys.argv[2], sys.argv[3:]
LAYERS = tuple(os.environ.get('LAYERS', 'In2.Cu,In7.Cu,In5.Cu,B.Cu,F.Cu').split(','))
CLR = float(os.environ.get('CLR', '0.127'))
WIDTH = float(os.environ.get('WIDTH', '0.127'))
COST = ({ly: 1.0 for ly in ('In2.Cu', 'In7.Cu', 'In5.Cu', 'B.Cu', 'F.Cu')} if os.environ.get('FLAT_COST') else
        {'In2.Cu': 1.0, 'In7.Cu': 1.0, 'In5.Cu': 1.05, 'B.Cu': 1.15, 'F.Cu': 1.2})
ESC = 3.0
t0 = time.time()


def router():
    rr = pslib.Router(PCB, os.environ.get('ESC_REFS', 'U11,U100,U21').split(','))
    rr.clr = CLR
    c = rr.bd.b.FindFootprintByReference('U11').GetCourtyard(pcbnew.F_CrtYd).BBox()
    rlib.BGA_RECTS.append((c.GetLeft() / 1e6 - ESC, c.GetTop() / 1e6 - ESC, c.GetRight() / 1e6 + ESC,
                           c.GetBottom() / 1e6 + ESC, 0.09))
    for q in os.environ.get('EXTRA_ESC', '').split(';'):
        if q:
            rlib.BGA_RECTS.append(tuple(float(v) for v in q.split(',')) + (0.10,))
    proute.ESC[:] = [q[:4] for q in rlib.BGA_RECTS]
    return rr


r = router()
bd = r.bd
b = bd.b
nets = set(NETS)
ballxy = {}
for ref in ('U11', 'U100'):
    f = b.FindFootprintByReference(ref)
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        if p.GetNetname() in nets:
            ballxy.setdefault(p.GetNetname(), []).append((p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))

if STEP == 'rip':
    ts = b.Tracks()
    items = [ts[i] for i in range(len(ts))]
    dog = set()
    for it in items:
        n = it.GetNetname()
        if n in nets and it.GetClass() == 'PCB_VIA':
            v = (it.GetPosition().x / 1e6, it.GetPosition().y / 1e6)
            if any(math.hypot(v[0] - x, v[1] - y) < 0.95 for x, y in ballxy.get(n, [])):
                dog.add((n, round(v[0], 3), round(v[1], 3)))
    kill = []
    for it in items:
        n = it.GetNetname()
        if n not in nets:
            continue
        if it.GetClass() == 'PCB_VIA':
            if (n, round(it.GetPosition().x / 1e6, 3), round(it.GetPosition().y / 1e6, 3)) not in dog:
                kill.append(it)
            continue
        a = (it.GetStart().x / 1e6, it.GetStart().y / 1e6)
        z = (it.GetEnd().x / 1e6, it.GetEnd().y / 1e6)
        ob = lambda p: any(math.hypot(p[0] - x, p[1] - y) < 0.02 for x, y in ballxy.get(n, []))
        od = lambda p: (n, round(p[0], 3), round(p[1], 3)) in dog
        if not (it.GetLayer() == pcbnew.F_Cu and ((ob(a) and od(z)) or (ob(z) and od(a)))):
            kill.append(it)
    for it in kill:
        b.Remove(it)
    graveyard = kill
    bd.save()
    print('ripped %d items of %d nets (dogbones kept: %d)' % (len(kill), len(nets), len(dog)))
    sys.exit(0)

T = r.terms
vias = {}
for (vx, vy, vr, vn) in bd.vias:
    vias.setdefault(vn, []).append((vx, vy))


def endpoint_via(n, q):
    name, p, lays = q[0], q[1], q[2]
    if name.startswith('VIA') or set(rlib.LAYERS) <= set(lays):
        return p
    for (vx, vy) in vias.get(n, []):
        if math.hypot(vx - p[0], vy - p[1]) < 3.5 and len(set(r.comp(n, [q[:4], r.via_term((vx, vy))]))) == 1:
            return (vx, vy)
    st = []
    # ball/pin grids: a dogbone at one of the four diagonal cell centres first
    ref = name.split(':')[0]
    h = {'U100': 0.5, 'U11': 0.4, 'U21': 0.4, 'J20': 0.635}.get(ref)
    if h:
        ly = r.side(lays)
        for sx in (-1, 1):
            for sy in (-1, 1):
                q = (p[0] + sx * h, p[1] + sy * h)
                if proute.via_spot_exact(bd, q[0], q[1], n) and bd.path(ly, p, q, 0.05, {n}, 0.09, margin=0.6, half_in=0.05):
                    bd.stage_track([p, q], 0.1, n, ly, st)
                    bd.stage_via(q[0], q[1], n, st, d=0.4)
                    bd.commit(st)
                    vias.setdefault(n, []).append(q)
                    return q
    v = proute.drop_via(bd, p, n, (p[0], p[1] + 1.0), st, w=0.15, radii=(0.5, 0.65, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 3.5), layer=r.side(lays))
    if v:
        bd.commit(st)
        return v
    bd.unstage(st)
    return None


legs, nolink = [], []
for n in sorted(nets):
    tt = T(n)
    if len(tt) < 2 or len(set(r.comp(n, tt))) == 1:
        continue
    ends, pins = [], {}
    for q in tt:
        v = endpoint_via(n, q)
        if v is None and os.environ.get('R3D') and len(q[2]) == 1:
            # no via spot: the 3d router may end on the pad itself, on its own layer
            v = q[1]
            pins[v] = list(q[2])[0]
        if v is None:
            nolink.append((n, q[0]))
        else:
            ends.append(v)
    if len(ends) < 2:
        continue
    vt = [r.via_term(v) for v in ends]
    used, edges = {0}, []
    while len(used) < len(vt):
        bst = min(((math.hypot(vt[i][1][0] - vt[j][1][0], vt[i][1][1] - vt[j][1][1]), i, j)
                   for i in used for j in range(len(vt)) if j not in used))
        edges.append(bst[1:])
        used.add(bst[2])
    for i, j in edges:
        if len(set(r.comp(n, [vt[i], vt[j]]))) > 1:
            leg = {'net': n, 'a': vt[i][1], 'b': vt[j][1]}
            if ends[i] in pins:
                leg['la'] = pins[ends[i]]
            if ends[j] in pins:
                leg['lb'] = pins[ends[j]]
            legs.append(leg)
print('legs %d; terminals without a via spot: %s' % (len(legs), nolink or 'none'), flush=True)
if legs:
    ax = [l['a'][0] for l in legs] + [l['b'][0] for l in legs]
    ay = [l['a'][1] for l in legs] + [l['b'][1] for l in legs]
    win = (max(50.5, min(ax) - 6), max(53.6, min(ay) - 6), min(190.6, max(ax) + 6), min(146.9, max(ay) + 6))
    if os.environ.get('R3D'):
        import negroute3d
        negroute3d.negotiate3d(bd, legs, win, {ly: WIDTH for ly in LAYERS}, {ly: COST.get(ly, 1.0) for ly in LAYERS}, via_cost=float(os.environ.get('VIA_COST', '1.2')), margin=float(os.environ.get('MARGIN', '4')),
                               iters=int(os.environ.get('NEG_ITERS', '20')), clr=CLR, log=lambda s: print(s, flush=True))
    else:
        negroute.negotiate(bd, legs, win, {ly: WIDTH for ly in LAYERS}, {ly: COST.get(ly, 1.0) for ly in LAYERS},
                           iters=int(os.environ.get('NEG_ITERS', '20')), clr=CLR, log=lambda s: print(s, flush=True))
bd.save()
r2 = pslib.Router(PCB, [])
done = [n for n in nets if len(r2.terms(n)) > 1 and len(set(r2.comp(n, r2.terms(n)))) == 1]
print('rerouted nets complete: %d of %d; open: %s (%.0f s)' % (len(done), len(nets), ' '.join(sorted(nets - set(done))) or 'none', time.time() - t0))
