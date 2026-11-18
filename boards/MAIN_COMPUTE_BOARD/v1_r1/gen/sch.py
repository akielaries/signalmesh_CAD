import os
import re
import uuid
from copy import deepcopy

from sx import Q, dump, find, first, parse

SYSLIB = '/usr/share/kicad/symbols'
LIBS = {}
GRID = 2.54
FONT = ['effects', ['font', ['size', 1.27, 1.27]]]

_libcache = {}
_flat = {}


NS = uuid.UUID('6f1c2b8e-5a7d-4c1e-9b3a-2d4e5f60718a')


def U(key=None):
    # stable ids for anything the pcb links to (sheets, symbols); random for the rest
    if key is not None:
        return str(uuid.uuid5(NS, key))
    return str(uuid.uuid4())


def snap(v, g=GRID):
    return round(round(v / g) * g, 4)


def _lib(nick):
    path = LIBS.get(nick, os.path.join(SYSLIB, nick + '.kicad_sym'))
    if path not in _libcache:
        root = parse(open(path).read())
        _libcache[path] = {s[1]: s for s in find(root, 'symbol')}
    return _libcache[path]


def flat(nick, name):
    key = (nick, name)
    if key in _flat:
        return _flat[key]
    s = _lib(nick)[name]
    ext = first(s, 'extends')
    if not ext:
        node = deepcopy(s)
    else:
        parent = flat(nick, ext[1])
        node = deepcopy(parent)
        cprops = {p[1]: p for p in find(s, 'property')}
        out = []
        for c in node:
            if isinstance(c, list) and c[0] == 'property' and c[1] in cprops:
                out.append(deepcopy(cprops.pop(c[1])))
            else:
                out.append(c)
        idx = max(i for i, c in enumerate(out) if isinstance(c, list) and c[0] == 'property')
        for p in cprops.values():
            idx += 1
            out.insert(idx, deepcopy(p))
        node = out
        pname = parent[1]
        for c in node:
            if isinstance(c, list) and c[0] == 'symbol':
                c[1] = Q(name + c[1][len(pname):])
    node[1] = Q(name)
    _flat[key] = node
    return node


def prop(node, key, default=''):
    for p in find(node, 'property'):
        if p[1] == key:
            return p[2]
    return default


def nunits(node):
    us = set()
    for sub in find(node, 'symbol'):
        m = re.match(r'.*_(\d+)_(\d+)$', sub[1])
        us.add(int(m.group(1)))
    us.discard(0)
    return sorted(us) or [1]


def geom(node, unit):
    pins = []
    xs, ys = [], []
    for sub in find(node, 'symbol'):
        m = re.match(r'.*_(\d+)_(\d+)$', sub[1])
        u, st = int(m.group(1)), int(m.group(2))
        if u not in (0, unit) or st not in (0, 1):
            continue
        for el in sub:
            if not isinstance(el, list):
                continue
            k = el[0]
            if k == 'rectangle':
                for kk in ('start', 'end'):
                    a = first(el, kk)
                    xs.append(float(a[1]))
                    ys.append(float(a[2]))
            elif k == 'polyline' or k == 'bezier':
                for xy in find(first(el, 'pts'), 'xy'):
                    xs.append(float(xy[1]))
                    ys.append(float(xy[2]))
            elif k == 'circle':
                c = first(el, 'center')
                r = float(first(el, 'radius')[1])
                xs += [float(c[1]) - r, float(c[1]) + r]
                ys += [float(c[2]) - r, float(c[2]) + r]
            elif k == 'arc':
                for kk in ('start', 'mid', 'end'):
                    a = first(el, kk)
                    xs.append(float(a[1]))
                    ys.append(float(a[2]))
            elif k == 'pin':
                at = first(el, 'at')
                x, y = float(at[1]), float(at[2])
                a = float(at[3]) if len(at) > 3 else 0.0
                ln = float(first(el, 'length')[1])
                hide = 'hide' in el or ['hide', 'yes'] in el
                pins.append(dict(type=el[1], x=x, y=y, ang=a, name=first(el, 'name')[1],
                                 num=first(el, 'number')[1], hide=hide,
                                 alts=[a[1] for a in find(el, 'alternate')]))
                xs.append(x)
                ys.append(y)
    if not xs:
        xs, ys = [0], [0]
    return pins, (min(xs), min(ys), max(xs), max(ys))


OUT = {0: 'W', 180: 'E', 90: 'S', 270: 'N'}
LBL_ANG = {'W': 180, 'E': 0, 'S': 270, 'N': 90}
GND_ROT = {'S': 0, 'E': 90, 'N': 180, 'W': 270}
VCC_ROT = {'N': 0, 'W': 90, 'S': 180, 'E': 270}


class Design:
    def __init__(self, project, rails):
        self.project = project
        self.rails = set(rails)
        self.sheets = []
        self.counters = {}
        self.root_uuid = U()
        self.used_refs = set()
        self.expect = {}  # (ref, pin) -> net

    def ref(self, prefix):
        n = self.counters.get(prefix, 0) + 1
        while '%s%d' % (prefix, n) in self.used_refs:
            n += 1
        self.counters[prefix] = n
        r = '%s%d' % (prefix, n)
        self.used_refs.add(r)
        return r

    def sheet(self, name, title=None, width=420):
        s = Sheet(self, name, title or name, width)
        self.sheets.append(s)
        return s


class Part:
    pass


class Sheet:
    def __init__(self, design, name, title, width):
        self.d = design
        self.name = name
        self.title = title
        self.width = width
        self.uuid = U('sheet/' + name)
        self.parts = []
        self.notes = []
        self.extra = []
        self.libs = {}

    def note(self, text):
        self.notes.append(text)

    def add(self, libid, nets, value=None, fp=None, ref=None, units=None, props=None,
            dnp=False, allow_missing=False, prefix=None, by='auto'):
        nick, name = libid.split(':', 1)
        node = flat(nick, name)
        self.libs[libid] = node
        if ref is None:
            ref = self.d.ref(prefix or prop(node, 'Reference', 'U').rstrip('?'))
        else:
            self.d.used_refs.add(ref)
        allu = nunits(node)
        units = units or allu
        nets = {str(k): v for k, v in nets.items()}
        used = set()
        for u in units:
            pins, bbox = geom(node, u)
            p = Part()
            p.libid, p.node, p.ref, p.unit = libid, node, ref, u
            p.value = value if value is not None else prop(node, 'Value', name)
            p.fp = fp if fp is not None else prop(node, 'Footprint', '')
            p.props = props or {}
            p.dnp = dnp
            p.bbox = bbox
            p.pins = []
            allnames = {q['name'] for q in pins}
            allnums = {q['num'] for q in pins}
            if by == 'auto':
                amb = [k for k in nets if k in allnames and k in allnums and
                       any(q['name'] == k and q['num'] != k for q in pins)]
                if amb:
                    raise ValueError('%s %s: ambiguous keys %s, pass by=' % (ref, libid, amb))
            for pn in pins:
                if by == 'name':
                    key = pn['name'] if pn['name'] in nets else None
                elif by == 'num':
                    key = pn['num'] if pn['num'] in nets else None
                else:
                    key = pn['num'] if pn['num'] in nets else (pn['name'] if pn['name'] in nets else None)
                net = nets.get(key) if key else None
                if net is not None:
                    used.add(key)
                if net is None:
                    if pn['type'] == 'no_connect':
                        continue
                    if allow_missing:
                        net = 'NC'
                    else:
                        raise ValueError('%s %s: pin %s (%s) unassigned' % (ref, libid, pn['num'], pn['name']))
                p.pins.append((pn, net))
                if net != 'NC':
                    self.d.expect[(ref, pn['num'])] = net
            self.parts.append(p)
        extra = set(nets) - used
        if extra and units == allu:
            raise ValueError('%s %s: unknown pins %s' % (ref, libid, sorted(extra)))
        return ref

    # layout and emission

    def _margins(self, p):
        m = {'W': 2.0, 'E': 2.0, 'N': 2.0, 'S': 2.0}
        for pn, net in p.pins:
            side = OUT[int(pn['ang']) % 360]
            if net == 'NC':
                ln = 2.0
            elif net == 'GND' or net in self.d.rails:
                ln = 6.0 if side in 'NS' else 6.0 + 1.3 * len(net) * (net != 'GND')
            else:
                ln = len(net.lstrip('.')) * 1.3 + 4.0
            m[side] = max(m[side], ln)
        return m

    def layout(self):
        x0, y0 = 20.0, 30.0 + 6.0 * len(self.notes)
        x, y, rowh = x0, y0, 0.0
        maxx = 0.0
        for p in self.parts:
            bx0, by0, bx1, by1 = p.bbox
            m = self._margins(p)
            w = (bx1 - bx0) + m['W'] + m['E'] + 6
            h = (by1 - by0) + m['N'] + m['S'] + 10
            if x + w > self.width and x > x0:
                x = x0
                y += rowh
                rowh = 0.0
            # symbol coords y up: top edge at -by1
            p.x = snap(x + m['W'] - bx0)
            p.y = snap(y + m['N'] + 4 + by1)
            x += w
            rowh = max(rowh, h)
            maxx = max(maxx, x)
        self.size = (max(maxx + 20, 297.0), max(y + rowh + 20, 210.0))

    def emit(self, page):
        d = self.d
        path = '/%s/%s' % (d.root_uuid, self.uuid)
        items = []
        libs = []
        for libid, node in self.libs.items():
            n = deepcopy(node)
            n[1] = Q(libid)
            libs.append(n)
        need_gnd = need_vcc = False
        for p in self.parts:
            items.append(self._symbol(p, path))
            seen = {}
            for pn, net in p.pins:
                px, py = p.x + pn['x'], p.y - pn['y']
                key = (round(px, 3), round(py, 3))
                if key in seen:
                    if seen[key] != net:
                        raise ValueError('%s stacked pins with different nets at %s' % (p.ref, key))
                    continue
                seen[key] = net
                side = OUT[int(pn['ang']) % 360]
                if net == 'NC':
                    items.append(['no_connect', ['at', px, py], ['uuid', Q(U())]])
                elif net == 'GND':
                    need_gnd = True
                    items.append(self._power('power:GND', 'GND', px, py, GND_ROT[side], path))
                elif net in d.rails:
                    need_vcc = True
                    items.append(self._power('power:VCC', net, px, py, VCC_ROT[side], path))
                elif net.startswith('.'):
                    items.append(self._label('label', net[1:], px, py, LBL_ANG[side]))
                else:
                    items.append(self._label('global_label', net, px, py, LBL_ANG[side]))
        items += self.extra
        if need_gnd or any('power:GND' in str(e[:3]) for e in self.extra):
            libs.append(self._plib('GND'))
        if need_vcc or self.extra:
            libs.append(self._plib('VCC'))
            libs.append(self._plib('PWR_FLAG'))
        for i, t in enumerate(self.notes):
            items.append(['text', Q(t), ['exclude_from_sim', 'no'], ['at', 20.0, 20.0 + 6.0 * i, 0],
                          ['effects', ['font', ['size', 2.0, 2.0]], ['justify', 'left', 'bottom']],
                          ['uuid', Q(U())]])
        w, h = self.size
        root = ['kicad_sch', ['version', 20260306], ['generator', Q('eeschema')],
                ['generator_version', Q('10.0')], ['uuid', Q(self.uuid)],
                ['paper', Q('User'), round(w, 1), round(h, 1)],
                ['title_block', ['title', Q(self.title)], ['rev', Q('v1_r1')],
                 ['comment', 1, Q('generated, review before release')]],
                ['lib_symbols'] + dedupe(libs)] + items + [['embedded_fonts', 'no']]
        return dump(root) + '\n'

    def _plib(self, name):
        n = deepcopy(flat('power', name))
        n[1] = Q('power:' + name)
        return n

    def _symbol(self, p, path):
        bx0, by0, bx1, by1 = p.bbox
        props = [['property', Q('Reference'), Q(p.ref), ['at', p.x + (bx0 + bx1) / 2, p.y - by1 - 2.54, 0], FONT],
                 ['property', Q('Value'), Q(p.value), ['at', p.x + (bx0 + bx1) / 2, p.y - by0 + 2.54, 0], FONT],
                 ['property', Q('Footprint'), Q(p.fp), ['at', p.x, p.y, 0], ['hide', 'yes'], FONT],
                 ['property', Q('Datasheet'), Q(prop(p.node, 'Datasheet', '')), ['at', p.x, p.y, 0], ['hide', 'yes'], FONT]]
        for k, v in p.props.items():
            props.append(['property', Q(k), Q(v), ['at', p.x, p.y, 0], ['hide', 'yes'], FONT])
        pins = [['pin', Q(pn['num']), ['uuid', Q(U())]] for pn, net in p.pins]
        sym_uuid = U('symbol/%s/%s/%d' % (self.name, p.ref, p.unit))
        return (['symbol', ['lib_id', Q(p.libid)], ['at', p.x, p.y, 0], ['unit', p.unit],
                 ['exclude_from_sim', 'no'], ['in_bom', 'no' if p.libid.startswith(('Mechanical:', 'Jumper:SolderJumper')) or (p.fp or '').startswith('TestPoint:TestPoint_Pad') else 'yes'],
                 ['on_board', 'yes'], ['dnp', 'yes' if p.dnp else 'no'], ['uuid', Q(sym_uuid)]] + props + pins +
                [['instances', ['project', Q(self.d.project), ['path', Q(path), ['reference', Q(p.ref)], ['unit', p.unit]]]]])

    def _power(self, libid, value, x, y, rot, path, prefix='#PWR'):
        ref = self.d.ref(prefix)
        return ['symbol', ['lib_id', Q(libid)], ['at', x, y, rot], ['unit', 1],
                ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                ['uuid', Q(U())],
                ['property', Q('Reference'), Q(ref), ['at', x, y, 0], ['hide', 'yes'], FONT],
                ['property', Q('Value'), Q(value), ['at', x, y, 0], FONT],
                ['property', Q('Footprint'), Q(''), ['at', x, y, 0], ['hide', 'yes'], FONT],
                ['pin', Q('1'), ['uuid', Q(U())]],
                ['instances', ['project', Q(self.d.project), ['path', Q(path), ['reference', Q(ref)], ['unit', 1]]]]]

    def _label(self, kind, net, x, y, ang):
        just = 'left' if ang in (0, 90) else 'right'
        el = [kind, Q(net)]
        if kind == 'global_label':
            el.append(['shape', 'passive'])
        el += [['at', x, y, ang], ['fields_autoplaced', 'yes'],
               ['effects', ['font', ['size', 1.27, 1.27]], ['justify', just]], ['uuid', Q(U())]]
        if kind == 'global_label':
            el.append(['property', Q('Intersheetrefs'), Q('${INTERSHEET_REFS}'), ['at', x, y, 0],
                       ['hide', 'yes'], FONT])
        return el

    def pwr_flag(self, net, x, y):
        # flag plus rail symbol stacked at one point
        path = '/%s/%s' % (self.d.root_uuid, self.uuid)
        self.extra.append(self._power('power:PWR_FLAG', 'PWR_FLAG', x, y, 0, path, prefix='#FLG'))
        if net == 'GND':
            self.extra.append(self._power('power:GND', 'GND', x, y, 0, path))
        else:
            self.extra.append(self._power('power:VCC', net, x, y, 180, path))


def dedupe(libs):
    seen, out = set(), []
    for n in libs:
        if n[1] not in seen:
            seen.add(n[1])
            out.append(n)
    return out


def write(design, outdir, extra_sheets=()):
    # extra_sheets: list of (name, filename, uuid) copied in already
    entries = []
    page = 2
    for s in design.sheets:
        s.layout()
        fn = s.name + '.kicad_sch'
        open(os.path.join(outdir, fn), 'w').write(s.emit(page))
        entries.append((s.name, fn, s.uuid, page))
        page += 1
    for name, fn, su in extra_sheets:
        entries.append((name, fn, su, page))
        page += 1
    items = []
    for i, (name, fn, su, pg) in enumerate(entries):
        x = 25.4 + (i % 4) * 60.96
        y = 38.1 + (i // 4) * 30.48
        items.append(['sheet', ['at', x, y], ['size', 45.72, 17.78], ['exclude_from_sim', 'no'],
                      ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'], ['fields_autoplaced', 'yes'],
                      ['stroke', ['width', 0.1524], ['type', 'solid']], ['fill', ['color', 0, 0, 0, 0]],
                      ['uuid', Q(su)],
                      ['property', Q('Sheetname'), Q(name), ['at', x, y - 0.7, 0],
                       ['effects', ['font', ['size', 1.27, 1.27]], ['justify', 'left', 'bottom']]],
                      ['property', Q('Sheetfile'), Q(fn), ['at', x, y + 18.4, 0],
                       ['effects', ['font', ['size', 1.27, 1.27]], ['justify', 'left', 'top']]],
                      ['instances', ['project', Q(design.project),
                                     ['path', Q('/' + design.root_uuid), ['page', Q(str(pg))]]]]])
    root = ['kicad_sch', ['version', 20260306], ['generator', Q('eeschema')], ['generator_version', Q('10.0')],
            ['uuid', Q(design.root_uuid)], ['paper', Q('A3')],
            ['title_block', ['title', Q(design.project)], ['rev', Q('v1_r1')],
             ['comment', 1, Q('STM32H755BIT6 + XC7A100T-2FGG484 main compute board')]],
            ['lib_symbols']] + items + [['sheet_instances', ['path', Q('/'), ['page', Q('1')]]],
                                        ['embedded_fonts', 'no']]
    open(os.path.join(outdir, design.project + '.kicad_sch'), 'w').write(dump(root) + '\n')
