import sys
import rlib
from PIL import Image, ImageDraw

# render pads/vias/tracks of a window, one colour per layer, highlighted nets in red
pcb, x0, y0, x1, y1, out = sys.argv[1], *map(float, sys.argv[2:6]), sys.argv[6]
hl = set(sys.argv[7].split(',')) if len(sys.argv) > 7 else set()
bd = rlib.Board(pcb)
S = 40
im = Image.new('RGB', (int((x1 - x0) * S), int((y1 - y0) * S)), (20, 20, 20))
d = ImageDraw.Draw(im, 'RGBA')
X = lambda x: (x - x0) * S
Y = lambda y: (y - y0) * S
col = {'F.Cu': (220, 60, 60, 160), 'In2.Cu': (60, 200, 60, 160), 'In5.Cu': (200, 160, 40, 160), 'B.Cu': (60, 100, 230, 160)}
for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
    if x0 - 2 < x < x1 + 2 and y0 - 2 < y < y1 + 2:
        c = (255, 255, 255, 230) if n in hl else (120, 120, 120, 200)
        if rnd:
            d.ellipse([X(x - hx), Y(y - hy), X(x + hx), Y(y + hy)], fill=c)
        else:
            d.rectangle([X(x - hx), Y(y - hy), X(x + hx), Y(y + hy)], fill=c)
for (xa, ya, xb, yb, hw, n, ly) in bd.tracks:
    if min(xa, xb) < x1 and max(xa, xb) > x0 and min(ya, yb) < y1 and max(ya, yb) > y0:
        c = (255, 255, 255, 255) if n in hl else col[ly]
        d.line([X(xa), Y(ya), X(xb), Y(yb)], fill=c, width=max(1, int(hw * 2 * S)))
for (x, y, r, n) in bd.vias:
    if x0 < x < x1 and y0 < y < y1:
        d.ellipse([X(x - r), Y(y - r), X(x + r), Y(y + r)], outline=(255, 255, 255, 255) if n in hl else (180, 180, 220, 200), width=2)
im.save(out)
