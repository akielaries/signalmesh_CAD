import sys
import pcbnew
from PIL import Image, ImageDraw

# courtyard occupancy map of one side, with keepouts, refs for big parts and a 10 mm grid
pcb, side, out = sys.argv[1], sys.argv[2], sys.argv[3]
b = pcbnew.LoadBoard(pcb)
S = 8
im = Image.new('RGB', (160 * S, 100 * S), (245, 245, 245))
d = ImageDraw.Draw(im, 'RGBA')
X = lambda x: (x - 50) * S
Y = lambda y: (y - 50) * S
lay = pcbnew.F_CrtYd if side == 'F' else pcbnew.B_CrtYd
fs = b.Footprints()
for i in range(len(fs)):
    f = fs[i]
    on = (not f.IsFlipped()) == (side == 'F')
    cy = f.GetCourtyard(pcbnew.F_CrtYd if not f.IsFlipped() else pcbnew.B_CrtYd)
    if not cy.OutlineCount():
        continue
    bb = cy.BBox()
    tht = any(f.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH for k in range(len(f.Pads())))
    if not on and not tht:
        continue
    c = (200, 60, 60, 120) if f.GetReference().startswith('TP') else (60, 60, 60, 110 if on else 50)
    d.rectangle([X(bb.GetLeft() / 1e6), Y(bb.GetTop() / 1e6), X(bb.GetRight() / 1e6), Y(bb.GetBottom() / 1e6)], fill=c)
    if on and (bb.GetWidth() > 4e6 or f.GetReference().startswith('TP')):
        d.text((X(bb.GetLeft() / 1e6) + 2, Y(bb.GetTop() / 1e6) + 2), f.GetReference(), fill=(0, 0, 200))
zs = b.Zones()
for i in range(len(zs)):
    z = zs[i]
    if z.GetIsRuleArea():
        bb = z.GetBoundingBox()
        d.rectangle([X(bb.GetLeft() / 1e6), Y(bb.GetTop() / 1e6), X(bb.GetRight() / 1e6), Y(bb.GetBottom() / 1e6)], outline=(0, 150, 0), width=2)
for g in range(50, 211, 10):
    d.line([X(g), 0, X(g), 100 * S], fill=(0, 0, 255, 40))
    d.text((X(g) + 2, 2), str(g), fill=(0, 0, 255))
for g in range(50, 151, 10):
    d.line([0, Y(g), 160 * S, Y(g)], fill=(0, 0, 255, 40))
    d.text((2, Y(g) + 2), str(g), fill=(0, 0, 255))
im.save(out)
