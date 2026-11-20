#!/usr/bin/env python3
# build a static html gallery of board renders for github pages
#
# usage:
#   tools/gallery.py <renders_root> <site_out_dir>
#
# renders_root holds one subdir per board, each containing that board's render
# files (<base>_3d_top.png, _3d_bottom.png, _pcb.pdf, _schematic.pdf). copies
# them into the site dir and writes an index.html card grid

import html
import re
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mddoc  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def docs_dir(slug):
    # BOARD_vN_rM -> boards/BOARD/vN_rM/docs
    i = slug.rfind('_v')
    if i < 0:
        return None
    d = os.path.join(REPO, 'boards', slug[:i], slug[i + 1:], 'docs')
    return d if os.path.isdir(d) else None


def find_boards(root):
    # each immediate subdir with files is one board
    boards = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if os.path.isdir(d) and os.listdir(d):
            boards.append((name, d))
    return boards


def pick(files, suffix):
    # first file ending with suffix, else none
    for f in sorted(files):
        if f.endswith(suffix):
            return f
    return None


# stacking order for the layer viewer, bottom of the stack first
LAYER_ORDER = ['B_Mask', 'B_Silkscreen', 'B_Cu', 'In6_Cu', 'In5_Cu', 'In4_Cu', 'In3_Cu', 'In2_Cu',
               'In1_Cu', 'F_Cu', 'F_Silkscreen', 'F_Mask']


def layer_files(d):
    # <base>-<Layer>.svg in renders/layers, ordered bottom to top
    if not os.path.isdir(d):
        return []
    found = {}
    for f in os.listdir(d):
        if f.endswith('.svg') and '-' in f:
            found[f.rsplit('-', 1)[1][:-4]] = f
    order = [k for k in LAYER_ORDER if k in found] + sorted(k for k in found if k not in LAYER_ORDER)
    return [(k, found[k]) for k in order]


def pour_layers(slug):
    # copper layers that are mostly plane: zone outlines covering >= 40% of the board outline box.
    # returned as LAYER_ORDER keys (In1_Cu, ...)
    i = slug.rfind('_v')
    if i < 0:
        return set()
    d = os.path.join(REPO, 'boards', slug[:i], slug[i + 1:])
    out = set()
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if not f.endswith('.kicad_pcb'):
            continue
        txt = open(os.path.join(d, f), encoding='utf-8', errors='ignore').read()
        xs, ys = [], []
        for m in re.finditer(r'\(layer "Edge\.Cuts"\)', txt):
            blk = txt[txt.rfind('(gr_', 0, m.start()):m.start()]
            for x, y in re.findall(r'\((?:start|end|mid) ([-\d.]+) ([-\d.]+)\)', blk):
                xs.append(float(x))
                ys.append(float(y))
        if not xs:
            continue
        board = (max(xs) - min(xs)) * (max(ys) - min(ys))
        starts = [m.start() for m in re.finditer(r'\(zone\b', txt)] + [len(txt)]
        area = {}
        for s, e in zip(starts, starts[1:]):
            blk = txt[s:e]
            if '(keepout' in blk[:1500]:
                continue
            lm = re.search(r'\(layers? ((?:"[^"]+"\s*)+)\)', blk[:800])
            ps = blk.find('(polygon')
            if not lm or ps < 0:
                continue
            pe = blk.find('(filled_polygon', ps)
            outline = blk[ps:pe if pe > 0 else len(blk)]
            pts = [(float(x), float(y)) for x, y in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)', outline)]
            if len(pts) < 3:
                continue
            a = abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))) / 2
            for ly in re.findall(r'"([^"]+)"', lm.group(1)):
                if ly.endswith('.Cu'):
                    area[ly] = area.get(ly, 0) + a
        out |= {ly.replace('.', '_') for ly, a in area.items() if a >= 0.4 * board}
    return out


def layers_page(name, layers, out_html):
    imgs = ''.join(f'<img data-layer="{html.escape(k)}" src="layers/{html.escape(f)}" alt="" draggable="false">'
                   for k, f in layers)
    pours = pour_layers(name)
    # pour layers start faint, else a stack of solid planes hides everything under them
    rows = ''.join(f'<div class="row"><label><input type="checkbox" value="{html.escape(k)}">'
                   f'{html.escape(k.replace("_", "."))}{" <i>(pour)</i>" if k in pours else ""}</label>'
                   f'<input class="op" type="range" min="0" max="100" value="{30 if k in pours else 100}" '
                   f'data-layer="{html.escape(k)}" title="opacity"></div>' for k, f in reversed(layers))
    page = (LAYERS_TEMPLATE.replace('{{name}}', html.escape(name)).replace('{{imgs}}', imgs)
            .replace('{{boxes}}', rows))
    with open(out_html, 'w', encoding='utf-8') as fh:
        fh.write(page)


def card(name, rel, files, has_docs=False, has_layers=False):
    top = pick(files, "_3d_top.png")
    bottom = pick(files, "_3d_bottom.png")
    pcb = pick(files, "_pcb.pdf")
    sch = pick(files, "_schematic.pdf")

    imgs = ""
    for label, f in (("top", top), ("bottom", bottom)):
        if f:
            src = html.escape(f"{rel}/{f}")
            # link the thumbnail to the full-resolution image
            imgs += (f'<figure><a href="{src}" target="_blank" rel="noopener" '
                     f'title="open full resolution">'
                     f'<img loading="lazy" src="{src}" '
                     f'alt="{html.escape(name)} {label}"></a>'
                     f'<figcaption>{label}</figcaption></figure>')

    links = ""
    for label, f in (("schematic pdf", sch), ("pcb layers pdf", pcb)):
        if f:
            href = html.escape(f"{rel}/{f}")
            links += f'<a href="{href}">{label}</a>'
    if has_layers:
        links += f'<a href="{html.escape(rel)}/layers.html">layer viewer</a>'
    if has_docs:
        links += f'<a href="{html.escape(rel)}/docs/index.html">docs</a>'

    return (f'<section class="card"><h2>{html.escape(name)}</h2>'
            f'<div class="imgs">{imgs}</div>'
            f'<div class="links">{links}</div></section>')


def build(root, out):
    boards = find_boards(root)
    os.makedirs(out, exist_ok=True)

    cards = []
    for name, renders in boards:
        rel = name
        dst = os.path.join(out, rel)
        os.makedirs(dst, exist_ok=True)
        files = []
        for f in os.listdir(renders):
            src = os.path.join(renders, f)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(dst, f), dirs_exist_ok=True)
            else:
                shutil.copy2(src, os.path.join(dst, f))
                files.append(f)
        layers = layer_files(os.path.join(dst, 'layers'))
        if layers:
            layers_page(name, layers, os.path.join(dst, 'layers.html'))
        dd = docs_dir(name)
        if dd:
            n = mddoc.build_docs(dd, os.path.join(dst, 'docs'), name)
            print(f"gallery: {name} docs, {n} page(s)")
        cards.append(card(name, rel, files, has_docs=bool(dd), has_layers=bool(layers)))

    body = "\n".join(cards) if cards else "<p>no renders found</p>"
    page = TEMPLATE.replace("{{cards}}", body).replace("{{count}}", str(len(boards)))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"gallery: {len(boards)} board(s) -> {out}/index.html")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>signalmesh CAD renders</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2rem 1.25rem 4rem;
    font: 16px/1.5 system-ui, sans-serif;
    background: #0d1117; color: #e6edf3;
  }
  @media (prefers-color-scheme: light) {
    body { background: #f6f8fa; color: #1f2328; }
  }
  header { max-width: 1200px; margin: 0 auto 2rem; }
  h1 { margin: 0 0 .25rem; font-size: 1.5rem; }
  .sub { opacity: .65; font-size: .9rem; }
  .grid {
    max-width: 1400px; margin: 0 auto;
    display: grid; gap: 2rem;
    grid-template-columns: repeat(auto-fill, minmax(560px, 1fr));
  }
  @media (max-width: 620px) {
    .grid { grid-template-columns: 1fr; }
  }
  .card {
    border: 1px solid #30363d; border-radius: 12px;
    padding: 1.25rem; background: #161b22;
  }
  @media (prefers-color-scheme: light) {
    .card { border-color: #d0d7de; background: #fff; }
  }
  .card h2 { margin: 0 0 1rem; font-size: 1.15rem; }
  .imgs { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  @media (max-width: 480px) {
    .imgs { grid-template-columns: 1fr; }
  }
  figure { margin: 0; }
  figure a { display: block; }
  figure img {
    width: 100%; height: auto; border-radius: 8px; cursor: zoom-in;
    border: 1px solid transparent; transition: border-color .12s;
    background: repeating-conic-gradient(#8883 0% 25%, transparent 0% 50%) 50% / 16px 16px;
  }
  figure a:hover img { border-color: #4493f8; }
  figcaption { font-size: .75rem; opacity: .6; text-align: center; margin-top: .25rem; }
  .links { margin-top: .75rem; display: flex; gap: .75rem; flex-wrap: wrap; }
  .links a { font-size: .85rem; color: #4493f8; text-decoration: none; }
  .links a:hover { text-decoration: underline; }
  /* lightbox */
  .lb { position: fixed; inset: 0; z-index: 50; background: rgba(0,0,0,.93);
        display: grid; place-items: center; overflow: auto; }
  .lb[hidden] { display: none; }
  .lb img { max-width: 96vw; max-height: 92vh; cursor: zoom-in; }
  .lb img.full { max-width: none; max-height: none; cursor: zoom-out; }
  .lb-close { position: fixed; top: .5rem; right: 1rem; z-index: 51;
        font-size: 2.5rem; line-height: 1; color: #fff; background: none;
        border: 0; cursor: pointer; }
</style>
</head>
<body>
<header>
  <h1>signalmesh CAD renders</h1>
  <div class="sub">{{count}} board(s) - auto-generated by ci - click any render for full resolution</div>
</header>
<main class="grid">
{{cards}}
</main>
<div id="lb" class="lb" hidden>
  <button id="lbClose" class="lb-close" aria-label="close">&times;</button>
  <img id="lbImg" alt="">
</div>
<script>
(function () {
  var lb = document.getElementById('lb');
  var img = document.getElementById('lbImg');
  function open(src) {
    img.classList.remove('full');
    img.src = src;
    lb.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  function close() {
    lb.hidden = true;
    img.src = '';
    document.body.style.overflow = '';
  }
  // intercept thumbnail clicks; href stays as a no-js / new-tab fallback
  document.querySelectorAll('.imgs a').forEach(function (a) {
    a.addEventListener('click', function (e) {
      if (e.metaKey || e.ctrlKey || e.button === 1) { return; }
      e.preventDefault();
      open(a.getAttribute('href'));
    });
  });
  // toggle fit-to-screen vs actual 100% size (pan by scrolling the overlay)
  img.addEventListener('click', function () { img.classList.toggle('full'); });
  document.getElementById('lbClose').addEventListener('click', close);
  lb.addEventListener('click', function (e) { if (e.target === lb) { close(); } });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { close(); }
  });
})();
</script>
</body>
</html>
"""


LAYERS_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{name}} layers</title>
<style>
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { margin: 0; font: 14px/1.4 system-ui, sans-serif; background: #0d1117; color: #e6edf3;
         display: grid; grid-template-columns: 260px 1fr; }
  aside { padding: 1rem; border-right: 1px solid #30363d; overflow: auto; }
  aside h1 { font-size: 1rem; margin: 0 0 .5rem; overflow-wrap: anywhere; }
  aside a { color: #4493f8; text-decoration: none; font-size: .85rem; }
  .sec { margin-top: .9rem; font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; opacity: .6; }
  .row { display: grid; grid-template-columns: 1fr 80px; align-items: center; gap: .4rem; padding: .1rem 0; }
  .row label { cursor: pointer; white-space: nowrap; }
  .row i { opacity: .55; font-style: normal; font-size: .75rem; }
  .row input[type=checkbox] { margin-right: .45rem; }
  input[type=range] { width: 100%; accent-color: #4493f8; }
  .btns { display: flex; flex-wrap: wrap; gap: .35rem; margin: .4rem 0; }
  button, select { background: #21262d; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px;
           padding: .25rem .55rem; cursor: pointer; font-size: .8rem; }
  button:hover, select:hover { border-color: #4493f8; }
  .ctl { display: grid; grid-template-columns: 70px 1fr; align-items: center; gap: .4rem; margin: .3rem 0; font-size: .85rem; }
  .hint { font-size: .75rem; opacity: .55; margin-top: .75rem; }
  main { position: relative; overflow: hidden; background: #000; cursor: grab; touch-action: none; }
  main.drag { cursor: grabbing; }
  #stack { position: absolute; left: 0; top: 0; }
  #stack img { position: absolute; left: 0; top: 0; width: 100%; height: auto; user-select: none; }
  #stack img:first-child { position: relative; }
  #stack.add img { mix-blend-mode: lighten; }
  #stack img.off { visibility: hidden; }
  #zl { position: absolute; right: .75rem; bottom: .6rem; font-size: .8rem; opacity: .7; pointer-events: none; }
  @media (max-width: 760px) { body { grid-template-columns: 1fr; grid-template-rows: auto 70vh; }
    aside { border-right: 0; border-bottom: 1px solid #30363d; } }
</style>
</head>
<body>
<aside>
  <h1>{{name}}</h1>
  <a href="../index.html">back to gallery</a>
  <div class="sec">show</div>
  <div class="btns">
    <button data-set="F_Cu">top</button>
    <button data-set="B_Cu">bottom</button>
    <button data-set="_Cu">all copper</button>
    <button data-set="In">inner</button>
    <button data-set="*">all</button>
    <button data-set="">none</button>
  </div>
  <div class="sec">layers (checkbox, opacity)</div>
  {{boxes}}
  <div class="sec">view</div>
  <div class="ctl">opacity <input id="gop" type="range" min="5" max="100" value="100"></div>
  <div class="ctl">blend <select id="blend"><option value="normal">normal</option><option value="add">additive</option></select></div>
  <div class="btns"><button id="zin">zoom +</button><button id="zout">zoom -</button><button id="fit">fit</button></div>
  <div class="hint">wheel to zoom at the cursor, drag to pan, pinch on touch, double-click to zoom in, f to fit</div>
</aside>
<main id="view"><div id="stack">{{imgs}}</div><div id="zl"></div></main>
<script>
(function () {
  var view = document.getElementById('view'), st = document.getElementById('stack');
  var imgs = st.querySelectorAll('img'), boxes = document.querySelectorAll('.row input[type=checkbox]');
  var ops = document.querySelectorAll('.row input.op'), gop = document.getElementById('gop');
  var s = 1, x = 0, y = 0, baseW = 1000, aspect = 0.625, moved = false;

  function opacity() {
    var g = gop.value / 100, per = {};
    ops.forEach(function (o) { per[o.dataset.layer] = o.value / 100; });
    imgs.forEach(function (i) { i.style.opacity = g * per[i.dataset.layer]; });
  }
  function apply() {
    var on = {};
    boxes.forEach(function (b) { on[b.value] = b.checked; });
    imgs.forEach(function (i) { i.classList.toggle('off', !on[i.dataset.layer]); });
  }
  function preset(p) {
    boxes.forEach(function (b) { b.checked = p === '*' ? true : (p === '' ? false : b.value.indexOf(p) >= 0); });
    apply();
  }
  function draw() {
    // resize instead of css scale so the svgs re-render sharp at every zoom
    st.style.width = (baseW * s) + 'px';
    st.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    document.getElementById('zl').textContent = Math.round(s * 100) + '%';
  }
  function fit() {
    var r = view.getBoundingClientRect(), pad = 16;
    var h = baseW * aspect;
    s = Math.min((r.width - 2 * pad) / baseW, (r.height - 2 * pad) / h);
    x = (r.width - baseW * s) / 2; y = (r.height - h * s) / 2;
    draw();
  }
  function zoomAt(f, cx, cy) {
    var ns = Math.min(40, Math.max(0.05, s * f));
    f = ns / s;
    x = cx - (cx - x) * f; y = cy - (cy - y) * f; s = ns; moved = true;
    draw();
  }
  function centre() { var r = view.getBoundingClientRect(); return [r.width / 2, r.height / 2]; }

  view.addEventListener('wheel', function (e) {
    e.preventDefault();
    var r = view.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  view.addEventListener('dblclick', function (e) {
    var r = view.getBoundingClientRect();
    zoomAt(2, e.clientX - r.left, e.clientY - r.top);
  });
  // drag to pan, two pointers to pinch
  var pts = {}, last = null, pinch = null;
  view.addEventListener('pointerdown', function (e) {
    view.setPointerCapture(e.pointerId); pts[e.pointerId] = [e.clientX, e.clientY];
    view.classList.add('drag');
  });
  view.addEventListener('pointermove', function (e) {
    if (!pts[e.pointerId]) { return; }
    var prev = pts[e.pointerId]; pts[e.pointerId] = [e.clientX, e.clientY];
    var ids = Object.keys(pts);
    if (ids.length === 1) {
      x += e.clientX - prev[0]; y += e.clientY - prev[1]; moved = true; draw();
    } else if (ids.length === 2) {
      var a = pts[ids[0]], b = pts[ids[1]], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      var r = view.getBoundingClientRect();
      if (pinch) { zoomAt(d / pinch, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top); }
      pinch = d;
    }
  });
  function up(e) { delete pts[e.pointerId]; pinch = null; if (!Object.keys(pts).length) { view.classList.remove('drag'); } }
  view.addEventListener('pointerup', up); view.addEventListener('pointercancel', up);

  document.getElementById('zin').addEventListener('click', function () { var c = centre(); zoomAt(1.5, c[0], c[1]); });
  document.getElementById('zout').addEventListener('click', function () { var c = centre(); zoomAt(1 / 1.5, c[0], c[1]); });
  document.getElementById('fit').addEventListener('click', function () { moved = false; fit(); });
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') { return; }
    var c = centre();
    if (e.key === 'f') { moved = false; fit(); } else if (e.key === '+' || e.key === '=') { zoomAt(1.5, c[0], c[1]); }
    else if (e.key === '-') { zoomAt(1 / 1.5, c[0], c[1]); }
  });
  document.getElementById('blend').addEventListener('change', function (e) { st.classList.toggle('add', e.target.value === 'add'); });
  boxes.forEach(function (b) { b.addEventListener('change', apply); });
  ops.forEach(function (o) { o.addEventListener('input', opacity); });
  gop.addEventListener('input', opacity);
  document.querySelectorAll('button[data-set]').forEach(function (b) {
    b.addEventListener('click', function () { preset(b.dataset.set); });
  });
  // refit on resize only until the user has zoomed or panned (mobile toolbars fire resize)
  window.addEventListener('resize', function () { if (!moved) { fit(); } });
  var first = imgs[0];
  function ready() { if (first.naturalWidth) { aspect = first.naturalHeight / first.naturalWidth; } fit(); }
  if (first.complete) { ready(); } else { first.addEventListener('load', ready); }
  preset('F_Cu'); opacity();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: tools/gallery.py <renders_root> <site_out_dir>", file=sys.stderr)
        sys.exit(2)
    build(sys.argv[1], sys.argv[2])
