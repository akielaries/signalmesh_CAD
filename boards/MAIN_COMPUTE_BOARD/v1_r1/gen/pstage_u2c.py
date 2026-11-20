import sys

import pslib

# chunk 4 (U2) leftovers: reconnect what the clean-up or congestion left open
PCB = sys.argv[1]
r = pslib.Router(PCB, ['U5', 'U6'])
r.keepout_courtyards(['L1', 'L2', 'L4', 'L5', 'L7'])
T = r.terms
before = {}
for net, refs in (('+1V8', {'L5', 'C32', 'C33', 'U6', 'R17', 'TP6'}), ('PG_1V8', None), ('/POWER/PG_5V', None),
                  ('/POWER/FB_1V0', None), ('/POWER/SS_1V0', None), ('+5V', {'C25', 'C26', 'U5'})):
    ts = T(net, refs)
    before[net] = len(set(r.comp(net, ts)))
r.net('+1V8', T('+1V8', {'L5', 'C32', 'C33', 'U6', 'R17', 'TP6'}), 0.2)
r.net('PG_1V8', T('PG_1V8'), 0.15, inner=('In2.Cu', 'In5.Cu'))
r.net('/POWER/PG_5V', T('/POWER/PG_5V'), 0.15, inner=('In2.Cu', 'In5.Cu'))
r.net('/POWER/FB_1V0', T('/POWER/FB_1V0'), 0.15)
r.net('/POWER/SS_1V0', T('/POWER/SS_1V0'), 0.15)
r.net('+5V', T('+5V', {'C25', 'C26', 'U5'}), 0.4)
n = r.stitch(['U2', 'C7', 'R14', 'R15', 'C25'], nets=('GND', '+12V', '+1V0'))
r.bd.save()
print('pieces before:', before)
print('stitched', n)
print('open:', r.open)
