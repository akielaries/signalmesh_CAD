import sys

import pcbnew

import pslib

# power stage of U2 (LMR33630, 12 V -> +5V). U2 moves next to its inductor L1 (12 V is a full-board
# B.Cu pour, so the regulator can sit anywhere; +5V then starts right at its loads). its 12 V input
# caps come down from the top right to the VIN/PGND pins. to make room, U5's fb divider, soft-start
# cap and input caps move to the bottom under U5, and pull-ups in the way shuffle aside
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
U2G = ['U2', 'C3', 'C4', 'C5', 'C6', 'C7', 'R5', 'R6']
U5G = ['R14', 'R15', 'C24', 'C25', 'C26']
n = P.rip(U2G + U5G,
          nets={'/POWER/SW_5V', '/POWER/BOOT_5V', '/POWER/VCC_5V', '/POWER/FB_5V', '/POWER/FB_1V0', '/POWER/SS_1V0'})
print('ripped %d items' % n)

# U2 at L1's switch side; anything else in its new courtyard moves aside first
u2 = P.fps['U2']
u2.SetOrientationDegrees(0)
u2.SetPosition(pslib.V(89.0, 118.5))
box = P.crt(u2)
for r5 in U5G:
    P.fps[r5].SetPosition(pslib.V(60.0, 60.0))     # parked, placed below
moved = {}
for ref, f in list(P.fps.items()):
    if ref in U2G + U5G or f.IsFlipped():
        continue
    c = P.crt(f)
    if c[0] < box[2] + 0.15 and c[2] > box[0] - 0.15 and c[1] < box[3] + 0.15 and c[3] > box[1] - 0.15:
        x, y = f.GetPosition().x / 1e6, f.GetPosition().y / 1e6
        moved[ref] = P.place(ref, x, y, rmax=8.0, ignore=('U2',) if False else ())
print('shuffled aside:', moved)
if not P.ok(u2):
    # say what U2 is close to
    import math
    for k in range(len(u2.Pads())):
        p = u2.Pads()[k]
        px, py = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
        for vx, vy, vr, vn in P.vias:
            if vn != p.GetNetname() and math.hypot(px - vx, py - vy) < 1.0:
                print('  U2 pad %s %s near via %s at (%.2f, %.2f)' % (p.GetNumber(), p.GetNetname(), vn, vx, vy))
    for ref, f in P.fps.items():
        if ref != 'U2' and not f.IsFlipped():
            c = P.crt(f)
            if c[0] < box[2] + 0.15 and c[2] > box[0] - 0.15 and c[1] < box[3] + 0.15 and c[3] > box[1] - 0.15:
                print('  U2 courtyard near', ref, c)
u = P.pads('U2')
l1 = P.pads('L1')
print('U2 pins', {k: u[k] for k in '12345678'}, 'L1', l1)

got = {}


def place_any(ref, x, y, rmax=6.0):
    # top first, else bottom (input caps under the VIN side are fine)
    try:
        return P.place(ref, x, y, rmax=rmax)
    except SystemExit:
        return P.place(ref, x, y, bottom=True, rmax=rmax)



# input caps west of VIN (2) / PGND (1): the 100 nF closest
got['C7'] = place_any('C7', u['2'][0] - 1.5, (u['1'][1] + u['2'][1]) / 2)
got['C5'] = place_any('C5', u['2'][0] - 3.0, u['2'][1])
got['C6'] = place_any('C6', u['2'][0] - 3.0, u['2'][1] + 2.2)
# boot cap between BOOT (7) and SW (8), vcc cap at pin 6, divider at FB (5)
got['C4'] = place_any('C4', u['8'][0], u['8'][1] - 1.6)
got['C3'] = place_any('C3', u['6'][0] + 0.5, u['6'][1] + 2.4)
got['R6'] = place_any('R6', u['5'][0], u['5'][1] + 2.0)
got['R5'] = place_any('R5', u['5'][0] + 1.2, u['5'][1] + 2.4)
# U5's fb divider / soft-start under U5 (bottom), its input caps as close to PVIN as room allows
u5 = P.pads('U5')
got['R14'] = P.place('R14', u5['5'][0] - 0.6, u5['5'][1] + 1.2, bottom=True)
got['R15'] = P.place('R15', u5['5'][0] - 1.6, u5['5'][1] + 1.2, bottom=True)
got['C24'] = P.place('C24', u5['9'][0], u5['9'][1] + 1.6, bottom=True)
got['C26'] = P.place('C26', u5['11'][0] + 0.6, u5['11'][1] + 2.4, bottom=True)
got['C25'] = P.place('C25', u5['11'][0] + 0.6, u5['11'][1] + 4.0, bottom=True)
for k, v in got.items():
    print('  %-4s at (%.2f, %.2f) rot %d, %.2f mm from target%s' % ((k,) + v[:3] + (v[3], ' (bottom)' if P.fps[k].IsFlipped() else '')))
b.Save(PCB)
