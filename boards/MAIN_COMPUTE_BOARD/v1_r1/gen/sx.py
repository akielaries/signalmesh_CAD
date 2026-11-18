import re

_tok = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


class Q(str):
    # quoted string atom
    pass


def parse(text):
    stack = [[]]
    for m in _tok.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        elif t[0] == '"':
            stack[-1].append(Q(t[1:-1].replace('\\"', '"').replace('\\\\', '\\')))
        else:
            stack[-1].append(t)
    return stack[0][0]


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def atom(a):
    if isinstance(a, Q):
        return q(a)
    if isinstance(a, float):
        s = ('%.4f' % a).rstrip('0').rstrip('.')
        return '0' if s in ('-0', '') else s
    return str(a)


def dump(node, ind=0):
    if not isinstance(node, list):
        return atom(node)
    if not any(isinstance(c, list) for c in node):
        return '(' + ' '.join(atom(c) for c in node) + ')'
    pad = '\t' * (ind + 1)
    head = [atom(c) for c in node if not isinstance(c, list)]
    out = '(' + ' '.join(head)
    for c in node:
        if isinstance(c, list):
            out += '\n' + pad + dump(c, ind + 1)
    return out + '\n' + '\t' * ind + ')'


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


def netlist(path):
    root = parse(open(path).read())
    nets = {}
    for n in find(first(root, 'nets'), 'net'):
        name = first(n, 'name')[1]
        nets[name] = [(first(x, 'ref')[1], first(x, 'pin')[1]) for x in find(n, 'node')]
    comps = {}
    for c in find(first(root, 'components'), 'comp'):
        ref = first(c, 'ref')[1]
        comps[ref] = (first(c, 'value')[1], (first(c, 'footprint') or [0, ''])[1])
    return nets, comps
