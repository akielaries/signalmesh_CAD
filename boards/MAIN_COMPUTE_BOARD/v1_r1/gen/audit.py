import collections
import math
import re
import sys

import pcbnew

# read-only routing audit: gtp lane skew, qspi/rmii/ulpi lengths, long detours, open nets by group.
# usage: audit.py board drc_report (drc run with --schematic-parity)
PCB, RPT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
ts = b.Tracks()
length, nvias = collections.Counter(), collections.Counter()
for i in range(len(ts)):
    t = ts[i]
    if t.GetClass() == 'PCB_VIA':
        nvias[t.GetNetname()] += 1
    else:
        length[t.GetNetname()] += t.GetLength() / 1e6
pads = collections.defaultdict(list)
fs = b.Footprints()
for i in range(len(fs)):
    f = fs[i]
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        if p.GetNetname():
            pads[p.GetNetname()].append((f.GetReference(), p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))
# nets with a missing connection, from the drc report
openn = collections.Counter()
lines = open(RPT).read().split('\n')
for i, ln in enumerate(lines):
    if ln.startswith('[unconnected_items]'):
        m = re.search(r'\[([^\]]+)\]', lines[i + 2])
        if m:
            openn[m.group(1)] += 1


def span(n):
    pp = pads[n]
    return max((math.hypot(a[1] - c[1], a[2] - c[2]) for a in pp for c in pp), default=0.0)


def st(n):
    return 'OPEN' if n in openn else ('unrouted' if not length[n] else 'ok')


print('== GTP / SFP / VITA DP lanes (P vs N, through the AC caps; target 0.15 mm)')
LANES = [('SFP0 TX', ('GTP0_TX', 'SFP0_TD')), ('SFP0 RX', ('GTP0_RX', 'SFP0_RD')),
         ('SFP1 TX', ('GTP1_TX', 'SFP1_TD')), ('SFP1 RX', ('GTP1_RX', 'SFP1_RD')),
         ('VITA DP0 C2M', ('GTP2_TX', 'MEZZ_DP0_C2M')), ('VITA DP1 C2M', ('GTP3_TX', 'MEZZ_DP1_C2M')),
         ('VITA DP0 M2C', ('MEZZ_DP0_M2C',)), ('VITA DP1 M2C', ('MEZZ_DP1_M2C',)),
         ('REFCLK1 (VITA)', ('GTP_REFCLK1', 'MEZZ_GBTCLK0_M2C')), ('REFCLK0 (osc)', ('GTP_REFCLK0', '/FPGA_GTP/REFCLK0_OSC'))]
for name, legs in LANES:
    lp = sum(length[l + '_P'] for l in legs)
    lnn = sum(length[l + '_N'] for l in legs)
    o = [l + s for l in legs for s in ('_P', '_N') if l + s in openn]
    v = sum(nvias[l + s] for l in legs for s in ('_P', '_N'))
    state = 'OPEN %s' % o if o else ('ok' if abs(lp - lnn) <= 0.2 else 'SKEW')
    print('  %-15s P %6.2f  N %6.2f  skew %5.2f  vias %2d  %s' % (name, lp, lnn, abs(lp - lnn), v, state))


def group(title, nets, ref=None, tol=None):
    print('== ' + title + (' (vs %s, window +/-%.0f mm)' % (ref, tol) if ref else ''))
    rl = length[ref] if ref else None
    for n in nets:
        if n not in pads:
            continue
        d = ''
        if ref and length[n] and rl:
            d = '%+6.1f %s' % (length[n] - rl, '' if abs(length[n] - rl) <= tol else 'SKEW')
        print('  %-16s %6.1f mm  span %5.1f  vias %d  %-8s %s' % (n, length[n], span(n), nvias[n], st(n), d))


group('QSPI (dual flash, up to 133 MHz)', ['QSPI_CLK', 'QSPI_NCS'] + ['QSPI_BK%d_IO%d' % (k, i) for k in (1, 2) for i in range(4)],
      'QSPI_CLK', 10)
group('RMII (50 MHz)', ['ETH_REF_CLK', 'ETH_CRS_DV', 'ETH_RXD0', 'ETH_RXD1', 'ETH_TXD0', 'ETH_TXD1', 'ETH_TX_EN',
                        'ETH_MDC', 'ETH_MDIO'], 'ETH_REF_CLK', 30)
group('ULPI (60 MHz)', ['ULPI_CK', 'ULPI_DIR', 'ULPI_STP', 'ULPI_NXT'] + ['ULPI_D%d' % i for i in range(8)])
eth = sorted(n for n in pads if n.startswith('/MCU_IO/ETH_'))
group('Ethernet PHY local (MDI pairs, crystal, straps)', eth)

print('== long detours (routed length > 1.6x pad span and > 25 mm, signal nets)')
PWR = re.compile(r'^(GND|\+|VTT|VADJ|ETH_AVDD|ETH_VDDCR|/.*V[0-9])')
rows = []
for n, L in length.items():
    if not n or PWR.match(n) or n not in pads or len(pads[n]) < 2:
        continue
    s = span(n)
    if L > 25 and s > 0 and L / s > 1.6:
        rows.append((L / s, n, L, s))
for r, n, L, s in sorted(rows, reverse=True)[:25]:
    print('  %-26s %6.1f mm  span %5.1f  x%.1f  %s' % (n, L, s, r, st(n)))

print('== open nets by group (%d nets, %d missing connections)' % (len(openn), sum(openn.values())))
G = [('DDR', r'^DDR_'), ('FMC/FPGA cfg', r'^(FMC_|FPGA_)'), ('VITA LA', r'^MEZZ_(LA|CLK)'), ('GTP/VITA DP', r'^(GTP|MEZZ_DP|MEZZ_GBT|SFP)'),
     ('QSPI', r'^QSPI_'), ('RMII', r'^ETH_'), ('ULPI', r'^(ULPI_|/MCU_IO/ULPI)'), ('ETH PHY local', r'^/MCU_IO/ETH_'),
     ('power/GND', r'^(GND|\+|VTT|VADJ|ETH_AVDD|ETH_VDDCR)')]
seen = set()
for title, rx in G:
    ns = sorted(n for n in openn if re.match(rx, n) and n not in seen)
    seen |= set(ns)
    if ns:
        print('  %-14s %3d  %s' % (title, len(ns), ' '.join(ns[:14]) + (' ...' if len(ns) > 14 else '')))
rest = sorted(n for n in openn if n not in seen)
print('  %-14s %3d  %s' % ('other', len(rest), ' '.join(rest[:30]) + (' ...' if len(rest) > 30 else '')))
