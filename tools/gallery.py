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


def layers_page(name, layers, out_html):
    imgs = ''.join(f'<img data-layer="{html.escape(k)}" src="layers/{html.escape(f)}" alt="">' for k, f in layers)
    boxes = ''.join(f'<label><input type="checkbox" value="{html.escape(k)}">{html.escape(k.replace("_", "."))}</label>'
                    for k, f in reversed(layers))
    page = (LAYERS_TEMPLATE.replace('{{name}}', html.escape(name)).replace('{{imgs}}', imgs)
            .replace('{{boxes}}', boxes))
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
  body { margin: 0; font: 14px/1.4 system-ui, sans-serif; background: #0d1117; color: #e6edf3;
         display: grid; grid-template-columns: 220px 1fr; height: 100vh; }
  aside { padding: 1rem; border-right: 1px solid #30363d; overflow: auto; }
  aside h1 { font-size: 1rem; margin: 0 0 .75rem; overflow-wrap: anywhere; }
  aside a { color: #4493f8; text-decoration: none; font-size: .85rem; }
  label { display: block; padding: .15rem 0; cursor: pointer; }
  input { margin-right: .5rem; }
  .btns { display: flex; flex-wrap: wrap; gap: .35rem; margin: .75rem 0; }
  button { background: #21262d; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px;
           padding: .25rem .5rem; cursor: pointer; font-size: .8rem; }
  button:hover { border-color: #4493f8; }
  .zoom { margin-top: .75rem; font-size: .8rem; }
  .zoom input { width: 100%; }
  main { overflow: auto; background: #000; }
  #stack { position: relative; margin: 1rem; }
  #stack img { position: absolute; inset: 0; width: 100%; height: auto; mix-blend-mode: screen; }
  #stack img:first-child { position: relative; }
  #stack img.off { visibility: hidden; }
  @media (max-width: 700px) { body { grid-template-columns: 1fr; height: auto; }
    aside { border-right: 0; border-bottom: 1px solid #30363d; } }
</style>
</head>
<body>
<aside>
  <h1>{{name}}</h1>
  <a href="../index.html">back to gallery</a>
  <div class="btns">
    <button data-set="F_Cu">top</button>
    <button data-set="B_Cu">bottom</button>
    <button data-set="_Cu">all copper</button>
    <button data-set="In">inner</button>
    <button data-set="*">all</button>
    <button data-set="">none</button>
  </div>
  {{boxes}}
  <div class="zoom">zoom <input id="zoom" type="range" min="100" max="800" step="25" value="100"></div>
</aside>
<main><div id="stack">{{imgs}}</div></main>
<script>
(function () {
  var imgs = document.querySelectorAll('#stack img');
  var boxes = document.querySelectorAll('aside input[type=checkbox]');
  function apply() {
    var on = {};
    boxes.forEach(function (b) { on[b.value] = b.checked; });
    imgs.forEach(function (i) { i.classList.toggle('off', !on[i.dataset.layer]); });
  }
  function preset(p) {
    boxes.forEach(function (b) {
      b.checked = p === '*' ? true : (p === '' ? false : b.value.indexOf(p) >= 0);
    });
    apply();
  }
  boxes.forEach(function (b) { b.addEventListener('change', apply); });
  document.querySelectorAll('button[data-set]').forEach(function (b) {
    b.addEventListener('click', function () { preset(b.dataset.set); });
  });
  var z = document.getElementById('zoom'), st = document.getElementById('stack');
  z.addEventListener('input', function () { st.style.width = 'calc(' + z.value + '% - 2rem)'; });
  st.style.width = 'calc(100% - 2rem)';
  preset('F_Cu');
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
