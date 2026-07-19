"""Minimal libngspice driver (no ngspice binary / no pip deps needed).

KiCad bundles libngspice.so; we call it directly via ctypes. Feed a SPICE deck
string that ends with a .control block doing `wrdata <file> ...`, then read the file.
"""
import ctypes as C
import glob
import os

def _find_lib():
    for pat in ("/usr/lib/*/libngspice.so*", "/usr/lib/libngspice.so*", "/usr/local/lib/libngspice.so*"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    raise RuntimeError("libngspice.so not found (install ngspice or KiCad, which bundles it)")

_SendChar = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
_SendStat = C.CFUNCTYPE(C.c_int, C.c_char_p, C.c_int, C.c_void_p)
_Exit     = C.CFUNCTYPE(C.c_int, C.c_int, C.c_bool, C.c_bool, C.c_int, C.c_void_p)

_msgs = []
@_SendChar
def _sc(m, cid, u):
    _msgs.append(m.decode(errors="replace")); return 0
@_SendStat
def _ss(m, cid, u):
    return 0
@_Exit
def _ex(status, unload, quit_, cid, u):
    return 0

_HERE = os.path.dirname(os.path.abspath(__file__))

def run(deck_text):
    """Run a SPICE deck; return ngspice's stdout/stderr text."""
    _msgs.clear()
    lib = C.CDLL(_find_lib())
    lib.ngSpice_Init.argtypes = [_SendChar, _SendStat, _Exit, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    lib.ngSpice_Command.argtypes = [C.c_char_p]
    lib.ngSpice_Init(_sc, _ss, _ex, None, None, None, None)
    deck_path = os.path.join(_HERE, "_deck.cir")
    open(deck_path, "w").write(deck_text)
    lib.ngSpice_Command(b"source " + deck_path.encode())
    return "\n".join(_msgs)

def read_wrdata(path):
    """Read an ngspice wrdata file: returns (freqs, [col1, col2, ...]).
    wrdata writes freq,value pairs per expression, so columns are at 1,3,5,..."""
    rows = [ln.split() for ln in open(path) if ln.strip()]
    f = [float(r[0]) for r in rows]
    ncols = (len(rows[0]) - 1) // 2 + 1
    cols = [[float(r[1 + 2 * k]) for r in rows] for k in range(ncols)]
    return f, cols

def nearest(f, target, col):
    i = min(range(len(f)), key=lambda k: abs(f[k] - target))
    return col[i]
