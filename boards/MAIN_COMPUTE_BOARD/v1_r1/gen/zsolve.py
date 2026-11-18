import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

C0 = 299792458.0
E0 = 8.854e-12


def solve(eps, fixed, val, d):
    # finite-difference laplace, div(eps grad v) = 0, dirichlet at fixed cells, v = 0 on outer boundary
    ny, nx = eps.shape
    n = nx * ny
    idx = np.arange(n).reshape(ny, nx)
    rows, cols, data = [], [], []
    b = np.zeros(n)
    for (dy, dx) in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        ys = slice(max(0, -dy), ny - max(0, dy))
        xs = slice(max(0, -dx), nx - max(0, dx))
        yt = slice(max(0, dy), ny - max(0, -dy) if dy < 0 else ny)
        a = idx[ys, xs].ravel()
        ys2 = slice(max(0, dy), ny + min(0, dy))
        xs2 = slice(max(0, dx), nx + min(0, dx))
        nb = idx[ys2, xs2].ravel()
        e = 0.5 * (eps[ys, xs].ravel() + eps[ys2, xs2].ravel())
        rows += [a, a]
        cols += [a, nb]
        data += [-e, e]
    # boundary cells see v=0 outside: add diagonal term
    eb = np.zeros((ny, nx))
    eb[0, :] += eps[0, :]
    eb[-1, :] += eps[-1, :]
    eb[:, 0] += eps[:, 0]
    eb[:, -1] += eps[:, -1]
    rows.append(idx.ravel())
    cols.append(idx.ravel())
    data.append(-eb.ravel())
    A = sp.csr_matrix((np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    f = fixed.ravel()
    A = A.tolil()
    for i in np.nonzero(f)[0]:
        A.rows[i] = [i]
        A.data[i] = [1.0]
    A = A.tocsr()
    b[f] = val.ravel()[f]
    v = spl.spsolve(A, b).reshape(ny, nx)
    gy, gx = np.gradient(v, d)
    we = 0.5 * np.sum(eps * (gx ** 2 + gy ** 2)) * d * d * E0
    return we


def build(kind, w, s, h1, h2, t, er1, er2, mask=0.015, er_mask=3.8, d=0.004, pair=False):
    # kind: 'micro' (trace on top of dielectric h1 over ground) or 'strip' (between planes h1 above, h2 below)
    span = (2 * w + s if pair else w) + 2.0
    nx = int(span / d)
    if kind == 'micro':
        top = h1 + t + 0.6
        ny = int((top + 0.02) / d)
    else:
        ny = int((h1 + h2 + t) / d) + 2
    y = (np.arange(ny) + 0.5) * d
    x = (np.arange(nx) + 0.5) * d - span / 2
    X, Y = np.meshgrid(x, y)
    eps = np.ones((ny, nx))
    fixed = np.zeros((ny, nx), bool)
    val = np.zeros((ny, nx))
    if kind == 'micro':
        # y=0 at ground plane (outer boundary acts as ground)
        eps[Y < h1] = er1
        eps[(Y >= h1) & (Y < h1 + t + mask)] = er_mask
        ylo, yhi = h1, h1 + t
    else:
        eps[Y < h2] = er2
        eps[Y >= h2] = er1
        ylo, yhi = h2, h2 + t
        eps[(Y >= ylo) & (Y < yhi)] = er2
    cx = [(-(w + s) / 2), (w + s) / 2] if pair else [0.0]
    sign = [1.0, -1.0] if pair else [1.0]
    for c, sg in zip(cx, sign):
        m = (np.abs(X - c) <= w / 2) & (Y >= ylo) & (Y <= yhi)
        fixed |= m
        val[m] = sg
    return eps, fixed, val, d


def z(kind, w, s=0.0, pair=False, **k):
    eps, fixed, val, d = build(kind, w, s, pair=pair, **k)
    we = solve(eps, fixed, val, d)
    we0 = solve(np.ones_like(eps), fixed, val, d)
    if pair:
        c, c0 = we, we0
        return 2.0 / (C0 * np.sqrt(c * c0))
    c, c0 = 2 * we, 2 * we0
    return 1.0 / (C0 * np.sqrt(c * c0))


OUT = dict(kind='micro', h1=0.0764, h2=0, t=0.040, er1=3.91, er2=0)
INN = dict(kind='strip', h1=0.300, h2=0.2104, t=0.0152, er1=4.41, er2=4.40)

if __name__ == '__main__':
    import sys
    for name, g in (('outer', OUT), ('inner', INN)):
        for w in (0.09, 0.10, 0.11, 0.12, 0.13, 0.15, 0.18, 0.20):
            print(name, 'w=%.2f SE %.1f' % (w, z(w=w, **g)))
        sys.stdout.flush()
