import csv
import io
import os
import re
import shutil
import subprocess
import sys
import zipfile

# fabrication outputs: gerbers (all copper in the stackup + mask, paste, silk, edge), excellon drill (pth and
# npth apart), jlcpcb-style bom and cpl, plus a readiness report (drc errors, open nets, parts without an
# lcsc number). usage: fab.py <board.kicad_pcb> <schematic.kicad_sch> <out_dir>
PCB, SCH, OUT = sys.argv[1:4]
name = os.path.splitext(os.path.basename(PCB))[0]
ger = os.path.join(OUT, 'gerbers')
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(ger)


def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True)
    if p.returncode:
        raise SystemExit('failed: %s\n%s' % (' '.join(a), p.stderr[-800:]))
    return p.stdout


txt = open(PCB, encoding='utf-8').read()
blk = txt[txt.index('\t(layers'):]
copper = re.findall(r'"([A-Za-z0-9.]*\.Cu)"', blk[:blk.index('\n\t)')])
layers = copper + ['F.Paste', 'B.Paste', 'F.Silkscreen', 'B.Silkscreen', 'F.Mask', 'B.Mask', 'Edge.Cuts']
run('kicad-cli', 'pcb', 'export', 'gerbers', PCB, '-o', ger + '/', '--layers', ','.join(layers), '--subtract-soldermask')
run('kicad-cli', 'pcb', 'export', 'drill', PCB, '-o', ger + '/', '--excellon-separate-th', '--generate-map',
    '--map-format', 'gerberx2')
zpath = os.path.join(OUT, name + '_gerbers.zip')
with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(ger)):
        z.write(os.path.join(ger, f), f)

# bom: one line per value + footprint + lcsc, jlcpcb columns
bomf = os.path.join(OUT, 'bom_raw.csv')
run('kicad-cli', 'sch', 'export', 'bom', SCH, '-o', bomf, '--exclude-dnp',
          '--fields', 'Value,Reference,Footprint,LCSC,QUANTITY', '--labels', 'Comment,Designator,Footprint,LCSC,Qty',
          '--group-by', 'Value,Footprint,LCSC')
rows = list(csv.DictReader(open(bomf, newline='')))
os.remove(bomf)
with open(os.path.join(OUT, name + '_bom_jlc.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for r in rows:
        w.writerow([r['Comment'], r['Designator'], r['Footprint'].split(':')[-1], r.get('LCSC', '')])
# cpl from the position file
posf = os.path.join(OUT, 'pos_raw.csv')
run('kicad-cli', 'pcb', 'export', 'pos', PCB, '-o', posf, '--format', 'csv', '--units', 'mm', '--side', 'both',
    '--exclude-dnp')
prow = list(csv.DictReader(open(posf, newline='')))
os.remove(posf)
with open(os.path.join(OUT, name + '_cpl_jlc.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for r in prow:
        w.writerow([r['Ref'], r['PosX'] + 'mm', r['PosY'] + 'mm', 'Top' if r['Side'] == 'top' else 'Bottom', r['Rot']])

# readiness
drc = os.path.join(OUT, 'drc.rpt')
subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--schematic-parity', '--severity-error', '-o', drc, PCB],
               capture_output=True)
d = open(drc).read()
errs = [ln for ln in d.split('\n') if ln.startswith('[') and not ln.startswith(('[unconnected_items', '[via_dangling', '[track_dangling'))]
dang = sum(1 for ln in d.split('\n') if ln.startswith(('[via_dangling', '[track_dangling')))
m = re.search(r'Found (\d+) unconnected', d)
nolcsc = [r for r in rows if not r.get('LCSC')]
nparts = sum(int(r['Qty']) for r in rows)
missing = sum(int(r['Qty']) for r in nolcsc)
bottom = sum(1 for r in prow if r['Side'] != 'top')
rep = ['# fab readiness: %s' % name, '',
       '| check | state |', '|---|---|',
       '| DRC errors (excluding unconnected) | %d |' % len(errs),
       '| unconnected (DRC report, capped at 499) | %s |' % (m.group(1) if m else '?'),
       '| dangling vias / track ends (leftovers to clean before fab) | %d |' % dang,
       '| BOM lines / parts | %d / %d |' % (len(rows), nparts),
       '| parts without an LCSC number | %d in %d lines |' % (missing, len(nolcsc)),
       '| placed parts top / bottom | %d / %d |' % (len(prow) - bottom, bottom),
       '| copper layers in gerbers | %d (%s) |' % (len(copper), ', '.join(copper)), '',
       'Rotations in the CPL are KiCad\'s; JLCPCB applies per-part corrections for some packages, so check '
       'their preview before ordering. Both sides are populated, so assembly is double-sided.', '']
if errs:
    rep += ['## DRC errors', ''] + ['- ' + e for e in errs[:40]] + ['']
rep += ['## BOM lines without an LCSC number', '', '| value | footprint | qty | refs |', '|---|---|---|---|']
for r in sorted(nolcsc, key=lambda r: -int(r['Qty'])):
    refs = r['Designator']
    rep.append('| %s | %s | %s | %s |' % (r['Comment'], r['Footprint'].split(':')[-1], r['Qty'],
                                        refs if len(refs) < 60 else refs[:57] + '...'))
open(os.path.join(OUT, 'READINESS.md'), 'w').write('\n'.join(rep) + '\n')
print('wrote %s: gerbers zip, drill, bom (%d lines), cpl (%d parts); %d DRC errors, %s unconnected, '
      '%d parts without LCSC' % (OUT, len(rows), len(prow), len(errs), m.group(1) if m else '?', missing))
