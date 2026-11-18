import pcbnew

MM = 1e6
TXT = 0.8
STROKE = 0.15
CLR = 0.2


def L(v):
    if hasattr(v, 'size'):
        return [v[i] for i in range(v.size())]
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v[i] for i in range(len(v))]


def rect_of(bb, grow=0.0):
    return (bb.GetX() / MM - grow, bb.GetY() / MM - grow, bb.GetRight() / MM + grow, bb.GetBottom() / MM + grow)


def hit(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def place_refs(board, x0, y0, x1, y1, small_prefixes=('R', 'C', 'FB'), labels=()):
    fps = L(board.Footprints())
    obst = {'F': [], 'B': []}
    for fp in fps:
        side = 'B' if fp.IsFlipped() else 'F'
        thr = any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in L(fp.Pads()))
        for p in L(fp.Pads()):
            r = rect_of(p.GetBoundingBox(), CLR)
            obst[side].append((r, fp.GetReference()))
            if thr:
                obst['B' if side == 'F' else 'F'].append((r, fp.GetReference()))
        for g in L(fp.GraphicalItems()):
            if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                gs = 'F' if g.GetLayer() == pcbnew.F_SilkS else 'B'
                obst[gs].append((rect_of(g.GetBoundingBox(), 0.12), fp.GetReference()))
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        if cy.OutlineCount():
            obst[side].append((rect_of(cy.BBox()), fp.GetReference()))
            if thr:
                obst['B' if side == 'F' else 'F'].append((rect_of(cy.BBox()), fp.GetReference()))
    texts = {'F': [], 'B': []}
    # board-level silk text (labels) are obstacles too
    for d in L(board.Drawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            texts['F' if d.GetLayer() == pcbnew.F_SilkS else 'B'].append(rect_of(d.GetBoundingBox(), CLR))
    # big parts first so their labels get the good spots; named labels before refs
    order = sorted(fps, key=lambda f: -f.GetPadCount())
    byref = {f.GetReference(): f for f in fps}
    named = set()
    fixed_anchor = set()
    free = []
    for lab in labels:
        anchors = lab[0] if isinstance(lab[0], tuple) else (lab[0],)
        named.update(anchors)
        if len(lab) >= 4:
            # fixed position label: the anchors show it instead of their refs
            fixed_anchor.update(anchors)
            tx_ = pcbnew.PCB_TEXT(board)
            tx_.SetText(lab[1])
            fp0 = [f for f in fps if f.GetReference() == anchors[0]][0]
            side = 'B' if fp0.IsFlipped() else 'F'
            tx_.SetLayer(pcbnew.B_SilkS if side == 'B' else pcbnew.F_SilkS)
            tx_.SetMirrored(side == 'B')
            tx_.SetTextSize(pcbnew.VECTOR2I(int(0.9 * MM), int(0.9 * MM)))
            tx_.SetTextThickness(int(STROKE * MM))
            tx_.SetPosition(pcbnew.VECTOR2I(int(lab[2] * MM), int(lab[3] * MM)))
            if len(lab) > 4:
                tx_.SetTextAngleDegrees(lab[4])
            board.Add(tx_)
            texts[side].append(rect_of(tx_.GetBoundingBox(), 0.06))
        else:
            free.append(lab)
    for anchor, text in free:
        fp = byref[anchor]
        side = 'B' if fp.IsFlipped() else 'F'
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        bb = rect_of(cy.BBox())
        probe = pcbnew.PCB_TEXT(board)
        probe.SetText(text)
        probe.SetTextSize(pcbnew.VECTOR2I(int(0.9 * MM), int(0.9 * MM)))
        probe.SetTextThickness(int(STROKE * MM))
        pb = probe.GetBoundingBox()
        w0 = pb.GetWidth() / MM + 0.1
        h0 = pb.GetHeight() / MM + 0.1
        cx, cyy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        done = False
        # horizontal first, then vertical alongside tall parts (long headers)
        for ang in (0, 90):
            w, h = (w0, h0) if ang == 0 else (h0, w0)
            cands = []
            for d in (0.12, 0.5, 0.9, 1.4, 2.0, 2.6, 3.2):
                cands += [(cx, bb[3] + h / 2 + d), (cx, bb[1] - h / 2 - d),
                          (bb[0] - w / 2 - d, cyy), (bb[2] + w / 2 + d, cyy)]
                for sx in (-1.5, 1.5):
                    cands += [(cx + sx, bb[3] + h / 2 + d), (cx + sx, bb[1] - h / 2 - d)]
            for tx, ty in cands:
                r = (tx - w / 2, ty - h / 2, tx + w / 2, ty + h / 2)
                if r[0] < x0 + 0.3 or r[2] > x1 - 0.3 or r[1] < y0 + 3.2 or r[3] > y1 - 3.2:
                    continue
                if any(hit(r, o) for o, _ in obst[side]) or any(hit(r, o) for o in texts[side]):
                    continue
                tx_ = pcbnew.PCB_TEXT(board)
                tx_.SetText(text)
                tx_.SetLayer(pcbnew.B_SilkS if side == 'B' else pcbnew.F_SilkS)
                tx_.SetMirrored(side == 'B')
                tx_.SetTextSize(pcbnew.VECTOR2I(int(0.9 * MM), int(0.9 * MM)))
                tx_.SetTextThickness(int(STROKE * MM))
                tx_.SetTextAngleDegrees(ang)
                tx_.SetPosition(pcbnew.VECTOR2I(int(tx * MM), int(ty * MM)))
                board.Add(tx_)
                texts[side].append((r[0] - 0.06, r[1] - 0.06, r[2] + 0.06, r[3] + 0.06))
                done = True
                break
            if done:
                break
        if not done:
            print('no room for label', text, 'at', anchor)
    stats = {'silk': 0, 'fab': 0}
    for fp in order:
        ref = fp.GetReference()
        if ref.startswith('#'):
            continue
        side = 'B' if fp.IsFlipped() else 'F'
        rf = fp.Reference()
        pre = ''.join(ch for ch in ref if ch.isalpha())
        silk = pcbnew.B_SilkS if side == 'B' else pcbnew.F_SilkS
        fab = pcbnew.B_Fab if side == 'B' else pcbnew.F_Fab
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        bb = rect_of(cy.BBox()) if cy.OutlineCount() else rect_of(fp.GetBoundingBox(False))
        rf.SetTextSize(pcbnew.VECTOR2I(int(TXT * MM), int(TXT * MM)))
        rf.SetTextThickness(int(STROKE * MM))
        rf.SetTextAngleDegrees(0)
        rf.SetMirrored(side == 'B')
        tb = rf.GetBoundingBox()
        w0 = tb.GetWidth() / MM + 0.1
        h0 = tb.GetHeight() / MM + 0.1
        cx, cyy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        best = None
        # horizontal first; vertical text only for small parts where it is the difference between
        # a ref on silk and a ref only on the fab drawing
        angles = (0, 90) if pre in small_prefixes else (0,)
        for ang in angles:
            w, h = (w0, h0) if ang == 0 else (h0, w0)
            cands = []
            for d in (0.12, 0.7):
                cands += [(cx, bb[1] - h / 2 - d), (cx, bb[3] + h / 2 + d),
                          (bb[0] - w / 2 - d, cyy), (bb[2] + w / 2 + d, cyy),
                          (bb[0] - w / 2 - d, bb[1] - h / 2 - d), (bb[2] + w / 2 + d, bb[1] - h / 2 - d),
                          (bb[0] - w / 2 - d, bb[3] + h / 2 + d), (bb[2] + w / 2 + d, bb[3] + h / 2 + d)]
            if fp.GetPadCount() > 8:
                # large parts: label may sit inside the body outline
                cands = cands + [(cx, cyy)]
            if (ref.startswith('TP') and ref in named) or ref in fixed_anchor:
                # test points show what they measure; the ref only goes to fab
                cands = []
            for (tx, ty) in cands:
                r = (tx - w / 2, ty - h / 2, tx + w / 2, ty + h / 2)
                if r[0] < x0 + 0.3 or r[2] > x1 - 0.3 or r[1] < y0 + 0.3 or r[3] > y1 - 0.3:
                    continue
                inside_own = fp.GetPadCount() > 8 and (tx, ty) == (cx, cyy)
                bad = False
                for o, oref in obst[side]:
                    if oref == ref and inside_own:
                        # own pads still forbidden, own courtyard allowed
                        continue
                    if oref == ref and not inside_own:
                        if hit(r, o) and o != bb:
                            bad = True
                            break
                        continue
                    if hit(r, o):
                        bad = True
                        break
                if not bad:
                    for o in texts[side]:
                        if hit(r, o):
                            bad = True
                            break
                if inside_own and not bad:
                    # own pads must not be under the label
                    for p in L(fp.Pads()):
                        if hit(r, rect_of(p.GetBoundingBox(), CLR)):
                            bad = True
                            break
                if not bad:
                    best = (tx, ty, r, ang)
                    break
            if best:
                break
        rf.SetTextSize(pcbnew.VECTOR2I(int(TXT * MM), int(TXT * MM)))
        rf.SetTextThickness(int(STROKE * MM))
        rf.SetTextAngleDegrees(best[3] if best else 0)
        rf.SetKeepUpright(True)
        if best:
            rf.SetLayer(silk)
            rf.SetMirrored(side == 'B')
            rf.SetPosition(pcbnew.VECTOR2I(int(best[0] * MM), int(best[1] * MM)))
            texts[side].append((best[2][0] - 0.06, best[2][1] - 0.06, best[2][2] + 0.06, best[2][3] + 0.06))
            stats['silk'] += 1
        else:
            rf.SetLayer(fab)
            rf.SetMirrored(side == 'B')
            stats['fab'] += 1
    return stats
