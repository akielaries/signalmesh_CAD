import os
import re
import subprocess
import sys
from collections import defaultdict

import sch
import mklib
from sx import Q, dump, find, first, parse, netlist

OUT = sys.argv[1]
PROJECT = 'MAIN_COMPUTE_BOARD'
APM_AUDIO = '/home/akiel/trunk/pub/signalmesh_CAD/boards/APM/v7_r1/AUDIO_APM.kicad_sch'
FPDIR = '/usr/share/kicad/footprints'

RAILS = ['+12V_JACK', '+12V', '+12V_MEZZ', '+5V', '+5V_AUD', '+5V_USBH', '+3V3', '+3V3_AUD', '+3V3_MEZZ',
         '+3V3_VDDA', '+3V3_SFP0', '+3V3_SFP1', '+1V0', '+1V8', '+1V35', '+1V0_MGT', '+1V2_MGT', 'VADJ',
         'VTT_DDR', 'GTP_RREF', 'VCCADC', 'GNDADC', 'VBUS_HS', 'ETH_VDDCR', 'ETH_AVDD']

libpath = os.path.join(OUT, PROJECT + '.kicad_sym')
mklib.build(libpath)
sch.LIBS['MCB'] = libpath
open(os.path.join(OUT, 'sym-lib-table'), 'w').write(
    '(sym_lib_table\n\t(version 7)\n\t(lib (name "MCB") (type "KiCad") (uri "${KIPRJMOD}/%s.kicad_sym") '
    '(options "") (descr "main compute board custom symbols"))\n)\n' % PROJECT)

import dpower, dstm32, dmcuio, dfpga, dddr, dmezz  # noqa: E402

d = sch.Design(PROJECT, RAILS)
import json
d.root_uuid = json.load(open(os.path.join(OUT, PROJECT + '.kicad_pro')))['schematic']['top_level_sheets'][0]['uuid']
dpower.build(d)
_, unused = dstm32.build(d)
dmcuio.build(d)
dfpga.build_cfg(d)
dfpga.build_banks(d)
dfpga.build_io(d)
dfpga.build_gtp(d)
dddr.build(d)
dmezz.build(d)


def import_audio(d):
    t = parse(open(APM_AUDIO).read())
    su = sch.U('sheet/AUDIO')
    path = '/%s/%s' % (d.root_uuid, su)
    first(t, 'uuid')[1] = Q(su)
    refmap = {}
    out = []
    dead_wires = {((69.85, 52.07), (69.85, 36.83)), ((69.85, 36.83), (59.69, 36.83))}
    for el in t:
        if isinstance(el, list) and el and el[0] == 'wire':
            pts = tuple((float(x[1]), float(x[2])) for x in find(first(el, 'pts'), 'xy'))
            if pts in dead_wires:
                continue
        if isinstance(el, list) and el and el[0] == 'symbol':
            ref0 = [p for p in find(el, 'property') if p[1] == 'Reference'][0][2]
            at0 = (float(first(el, 'at')[1]), float(first(el, 'at')[2]))
            if ref0 in ('J7', 'TP2') or (first(el, 'lib_id')[1] == 'power:GND' and at0 == (69.85, 57.15)):
                continue
        if isinstance(el, list) and el and el[0] == 'symbol':
            lid = first(el, 'lib_id')[1]
            props = {p[1]: p for p in find(el, 'property')}
            old = props['Reference'][2]
            if old.startswith('#'):
                new = d.ref('#PWR' if old.startswith('#PWR') else '#FLG')
            else:
                if old not in refmap:
                    pre = re.match(r'[A-Za-z]+', old).group(0)
                    refmap[old] = d.ref(pre)
                new = refmap[old]
            props['Reference'][2] = Q(new)
            if lid.startswith('power:'):
                v = props['Value']
                v[2] = Q({'5V_APM': '+5V_AUD', '3V3_APM': '+3V3_AUD'}.get(v[2], v[2]))
            if old == 'U14':
                props['Value'][2] = Q('LM2662M')
            if lid == 'Connector:TestPoint':
                first(el, 'in_bom')[1] = 'no'
            inst = first(el, 'instances')
            unit = first(first(first(inst, 'project'), 'path'), 'unit')
            inst[1:] = [['project', Q(PROJECT), ['path', Q(path), ['reference', Q(new)], unit]]]
        elif isinstance(el, list) and el and el[0] == 'global_label':
            el[1] = Q(el[1].replace('ACM_DAC_', 'AUD_DAC_'))
        elif isinstance(el, list) and el and el[0] == 'hierarchical_label':
            if el[1] == 'DAC_L_IN':
                el[0] = 'global_label'
                el[1] = Q('STM32_DAC1_OUT1')
                at = first(el, 'at')
                el.append(['property', Q('Intersheetrefs'), Q('${INTERSHEET_REFS}'), ['at', at[1], at[2], 0],
                           ['hide', 'yes'], sch.FONT])
            else:
                continue
        out.append(el)
    for x, y in ((237.49, 132.08), (237.49, 137.16)):
        out.append(['no_connect', ['at', x, y], ['uuid', Q(sch.U())]])
    t[:] = out
    for el in t:
        if isinstance(el, list) and el and el[0] == 'title_block':
            el[1:] = [['title', Q('Audio out: FPGA -> CS4344 -> OPA1656, STM32 DAC1 (from APM v7)')],
                      ['rev', Q('v1_r1')]]
    open(os.path.join(OUT, 'AUDIO.kicad_sch'), 'w').write(dump(t) + '\n')
    return su, refmap


sch.write.__defaults__  # keep linters quiet
# write generated sheets first so refs are allocated, then audio
su, refmap = import_audio(d)
import json as _json
_json.dump(refmap, open(os.path.join(OUT, 'audio_refmap.json'), 'w'))
sch.write(d, OUT, extra_sheets=[('AUDIO', 'AUDIO.kicad_sch', su)])

# footprint existence
missing = set()
for s in d.sheets:
    for p in s.parts:
        if p.fp:
            lib, name = p.fp.split(':')
            if not os.path.exists(os.path.join(FPDIR, lib + '.pretty', name + '.kicad_mod')):
                missing.add(p.fp)
        else:
            missing.add('(none) ' + p.ref + ' ' + p.libid)
print('missing footprints:', sorted(missing))
print('stm32 unused pins:', unused)
print('audio refmap:', refmap)

# erc and netlist
sch_file = os.path.join(OUT, PROJECT + '.kicad_sch')
subprocess.run(['kicad-cli', 'sch', 'erc', '--severity-all', '-o', os.path.join(OUT, 'erc.rpt'), sch_file],
               check=False, capture_output=True)
subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '-o', os.path.join(OUT, 'out.net'), sch_file],
               check=True, capture_output=True)
nets, comps = netlist(os.path.join(OUT, 'out.net'))
where = {}
for n, nodes in nets.items():
    for r, p in nodes:
        where[(r, p)] = n
groups = defaultdict(set)
for k, n in d.expect.items():
    groups[n].add(k)
errs = 0
for n, ks in groups.items():
    got = {where.get(k) for k in ks}
    if len(got) != 1 or None in got:
        errs += 1
        print('SPLIT', n, sorted(got, key=str)[:6])
        continue
    g = got.pop()
    others = {k for k in nets[g] if k in d.expect and d.expect[k] != n}
    if others:
        errs += 1
        print('MERGED', n, 'with', sorted({d.expect[k] for k in others})[:6])
print('expected nets:', len(groups), 'errors:', errs, 'components:', len(comps))
