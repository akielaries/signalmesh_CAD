import re
import sys

# keep only the low-speed nets in a specctra dsn for freerouting: drop the (net ...) entries and the
# (class ...) blocks of the excluded net classes. existing wiring stays (exported as fixed)
SRC, DST = sys.argv[1], sys.argv[2]
DROP_CLASSES = {'PWR', 'DDR', 'DIFF100', 'USB90', 'SE50'}
DROP_NAMES = re.compile(r'^(SYSCLK_100M|GTP_RREF|/POWER/SW_.*)$')
t = open(SRC).read()


def children(s, start):
    # (start, end) spans of the direct child lists of the list opening at s[start]
    out, depth, q, i, cs = [], 0, False, start, None
    while i < len(s):
        c = s[i]
        if c == '"':
            q = not q
        elif not q and c == '(':
            depth += 1
            if depth == 2:
                cs = i
        elif not q and c == ')':
            if depth == 2:
                out.append((cs, i + 1))
            depth -= 1
            if depth == 0:
                return out, i + 1
        i += 1
    raise SystemExit('unbalanced')


def tokens(s):
    return re.findall(r'"[^"]*"|[^\s()]+', s)


ns = t.index('(network')
kids, ne = children(t, ns)
drop = set()
for a, z in kids:
    tk = tokens(t[a:z])
    if tk[0] == 'class' and set(tk[1].split(',')) & DROP_CLASSES:
        names = []
        for x in tk[2:]:
            if x in ('circuit', 'rule', 'use_via'):
                break
            names.append(x)
        drop |= set(names)
keep_parts, last, nkept, ndrop = [], ns, 0, 0
out = t[:ns]
cur = ns
for a, z in kids:
    tk = tokens(t[a:z])
    name = tk[1].strip('"')
    gone = (tk[0] == 'net' and (name in drop or DROP_NAMES.match(name))) or \
           (tk[0] == 'class' and set(tk[1].split(',')) & DROP_CLASSES)
    out += t[cur:a]
    if gone:
        ndrop += tk[0] == 'net'
    else:
        out += t[a:z]
        nkept += tk[0] == 'net'
    cur = z
out += t[cur:]

# pours on routable layers (e.g. the In5 +1V0 VCCINT pour, the B.Cu +12V pour) are exported as planes,
# which freerouting will happily route other nets across, splitting the pour. add a wire keepout with the
# same outline for each one (vias stay allowed, so escapes through the region still work)
SIGNAL = {'F.Cu', 'In2.Cu', 'In5.Cu', 'B.Cu'}
ss = out.index('(structure')
skids, _ = children(out, ss)
keeps, last = [], None
for a, z in skids:
    blk = out[a:z]
    if not blk.startswith('(plane'):
        continue
    last = z
    m = re.match(r'\(plane\s+("[^"]*"|\S+)\s+\(polygon\s+(\S+)', blk)
    if m and m.group(2) in SIGNAL:
        keeps.append('\n    (wire_keepout "" ' + blk[blk.index('(polygon'):])
if keeps and last:
    out = out[:last] + ''.join(keeps) + out[last:]
open(DST, 'w').write(out)
print('nets kept %d, dropped %d; wire keepouts over %d pours on routable layers' % (nkept, ndrop, len(keeps)))
