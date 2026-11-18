import re, os
from sx import parse, find, first

LIBDIR = '/usr/share/kicad/symbols'
_cache = {}


def _lib(lib):
    if lib not in _cache:
        path = lib if lib.endswith('.kicad_sym') else os.path.join(LIBDIR, lib + '.kicad_sym')
        txt = open(path).read()
        blocks = {}
        # top-level symbol blocks by text span
        for m in re.finditer(r'^\t\(symbol "([^"]+)"', txt, re.M):
            blocks[m.group(1)] = m.start()
        names = sorted(blocks, key=lambda k: blocks[k])
        spans = {}
        for i, n in enumerate(names):
            end = blocks[names[i + 1]] if i + 1 < len(names) else txt.rfind(')')
            spans[n] = txt[blocks[n]:end].rstrip()
        _cache[lib] = spans
    return _cache[lib]


def raw(lib, name):
    return _lib(lib)[name]


def tree(lib, name):
    return parse(raw(lib, name))


def pins(lib, name):
    # returns list of dict(unit, num, name, type, x, y, ang, alts)
    t = tree(lib, name)
    ext = first(t, 'extends')
    if ext:
        t = tree(lib, ext[1])
    out = []
    for sub in find(t, 'symbol'):
        m = re.match(r'.*_(\d+)_(\d+)$', sub[1])
        unit = int(m.group(1))
        for p in find(sub, 'pin'):
            at = first(p, 'at')
            out.append(dict(unit=unit, num=first(p, 'number')[1], name=first(p, 'name')[1],
                            type=p[1], x=float(at[1]), y=float(at[2]), ang=float(at[3]) if len(at) > 3 else 0.0,
                            length=float(first(p, 'length')[1]),
                            alts=[a[1] for a in find(p, 'alternate')]))
    return out
