import html
import os
import sys

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

COL = {
    'mcu': ('#dae8fc', '#6c8ebf'), 'fpga': ('#d5e8d4', '#82b366'), 'pwr': ('#ffe6cc', '#d79b00'),
    'conn': ('#f5f5f5', '#666666'), 'mem': ('#e1d5e7', '#9673a6'), 'aud': ('#f8cecc', '#b85450'),
    'phy': ('#fff2cc', '#d6b656'), 'bus': ('#eeeeee', '#36393d'), 'card': ('#ffffff', '#36393d'),
}


class Diagram:
    def __init__(self, name):
        self.name = name
        self.cells = []
        self.n = 2

    def node(self, label, x, y, w, h, kind='conn', extra=''):
        cid = 'n%d' % self.n
        self.n += 1
        fill, stroke = COL[kind]
        style = ('rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor=%s;strokeColor=%s;fontSize=12;%s'
                 % (fill, stroke, extra))
        self.cells.append('<mxCell id="%s" value="%s" style="%s" vertex="1" parent="1">'
                          '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                          % (cid, html.escape(label, quote=True), style, x, y, w, h))
        return cid

    def group(self, label, x, y, w, h):
        style = ('rounded=1;whiteSpace=wrap;html=1;arcSize=3;dashed=1;fillColor=none;strokeColor=#999999;'
                 'verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;')
        cid = 'g%d' % self.n
        self.n += 1
        self.cells.insert(0, '<mxCell id="%s" value="%s" style="%s" vertex="1" parent="1">'
                             '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                             % (cid, html.escape(label, quote=True), style, x, y, w, h))
        return cid

    def edge(self, a, b, label='', both=False, thick=False, dashed=False, color='#555555', exit=None,
             entry=None, pts=()):
        cid = 'e%d' % self.n
        self.n += 1
        style = ('edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;fontSize=11;endArrow=block;endFill=1;'
                 'labelBackgroundColor=#ffffff;strokeColor=%s;strokeWidth=%d;%s%s'
                 % (color, 3 if thick else 1.5, 'startArrow=block;startFill=1;' if both else '',
                    'dashed=1;' if dashed else ''))
        if exit:
            style += 'exitX=%g;exitY=%g;exitDx=0;exitDy=0;' % exit
        if entry:
            style += 'entryX=%g;entryY=%g;entryDx=0;entryDy=0;' % entry
        geo = '<mxGeometry relative="1" as="geometry"/>'
        if pts:
            geo = ('<mxGeometry relative="1" as="geometry"><Array as="points">%s</Array></mxGeometry>'
                   % ''.join('<mxPoint x="%d" y="%d"/>' % p for p in pts))
        self.cells.append('<mxCell id="%s" value="%s" style="%s" edge="1" parent="1" source="%s" target="%s">%s'
                          '</mxCell>' % (cid, html.escape(label, quote=True), style, a, b, geo))

    def save(self):
        xml = ('<mxfile host="signalmesh-drawgen"><diagram name="%s" id="%s">'
               '<mxGraphModel grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
               'page="0" pageScale="1" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>%s'
               '</root></mxGraphModel></diagram></mxfile>\n') % (self.name, self.name, ''.join(self.cells))
        open(os.path.join(OUT, self.name + '.drawio'), 'w').write(xml)


# system block diagram
d = Diagram('system')
d.group('front panel', 0, 0, 170, 450)
j12 = d.node('12 V barrel jack', 15, 30, 140, 40, 'pwr')
sfp0 = d.node('SFP0 cage', 15, 100, 140, 40)
sfp1 = d.node('SFP1 cage', 15, 160, 140, 40)
rj = d.node('RJ45 100M', 15, 230, 140, 40)
usba = d.node('USB-A host<br>(USB-MIDI keyboards)', 15, 300, 140, 50)
usbc = d.node('USB-C HS device<br>(updates, UAC2, console)', 15, 380, 140, 50)
pwr = d.node('<b>power tree</b><br>5V, 3V3, 1V0, 1V8, 1V35,<br>VADJ, MGT, VTT, -5V', 230, 20, 160, 60, 'pwr')
eth = d.node('LAN8742A<br>RMII PHY', 230, 228, 120, 45, 'phy')
ulpi = d.node('USB3300<br>ULPI PHY', 230, 383, 120, 45, 'phy')
mcu = d.node('<b>STM32H755BIT6</b><br>M7 480 MHz + M4 240 MHz<br>LQFP208', 420, 270, 190, 90, 'mcu')
qspi = d.node('2x W25Q01JV<br>dual QSPI, 256 MB<br>firmware + bitstreams', 420, 430, 190, 60, 'mem')
dbg = d.node('debug: MIPI-10 x2, JTAG,<br>UART x2, Pmod x2, breakout', 190, 470, 190, 50)
fpga = d.node('<b>XC7A100T-2FGG484</b><br>63k LUT, 240 DSP, 4 GTP<br>soft core + DSP', 700, 250, 200, 100, 'fpga')
ddr = d.node('DDR3L 4Gb x16<br>800 Mb/s', 700, 430, 200, 50, 'mem')
aud = d.node('CS4344 DAC + OPA1656<br>L/R u.fl out', 980, 400, 170, 55, 'aud')
vita = d.node('<b>VITA 57.1 HPC</b><br>34 LA pairs, 2 GTP lanes,<br>VADJ, I2C ID', 700, 40, 200, 70, 'conn')
din = d.node('<b>DIN 41612 C 3x32</b><br>backplane: +12V, -12V, +5V,<br>TDM audio bus, CAN', 980, 170, 170, 80, 'bus')
d.edge(usbc, ulpi, '', both=True)
d.edge(ulpi, mcu, 'ULPI', both=True, entry=(0.25, 1))
d.edge(usba, mcu, 'OTG_FS', both=True, entry=(0, 0.7))
d.edge(rj, eth, '', both=True)
d.edge(eth, mcu, 'RMII', both=True, entry=(0, 0.3))
d.edge(qspi, mcu, 'QUADSPI x8', both=True)
d.edge(mcu, dbg, 'SWD / UART', dashed=True, exit=(0, 0.9), entry=(1, 0.5), pts=((400, 351), (400, 495)))
d.edge(mcu, fpga, 'FMC 32-bit sync + 6 IRQ<br>SelectMAP config', both=True, thick=True, exit=(1, 0.5), entry=(0, 0.65))
d.edge(fpga, ddr, 'MIG', both=True)
d.edge(fpga, aud, 'I2S', exit=(1, 0.85), entry=(0.5, 0), pts=((1065, 335),))
d.edge(fpga, vita, 'LA pairs + GTP 2/3', both=True)
d.edge(sfp0, fpga, 'GTP 0', both=True, entry=(0, 0.15), pts=((660, 120), (660, 265)))
d.edge(sfp1, fpga, 'GTP 1', both=True, entry=(0, 0.35), pts=((640, 180), (640, 285)))
d.edge(fpga, din, 'TDM', both=True, exit=(1, 0.3), entry=(0, 0.6))
d.edge(mcu, din, 'CAN-FD', both=True, dashed=True, exit=(0.5, 0), entry=(0.5, 0), pts=((515, 150), (1065, 150)))
d.edge(j12, pwr, '12 V', color='#d79b00', exit=(1, 0.5), entry=(0, 0.5))
d.save()

# power tree
p = Diagram('power')
inp = p.node('<b>12 V in</b><br>barrel jack or DIN a1-c2', 0, 0, 180, 50, 'pwr')
prot = p.node('3 A polyfuse, SMAJ15A,<br>reverse FET, 10 mR + INA219', 0, 80, 180, 50, 'pwr')
v12 = p.node('<b>+12V</b>', 40, 160, 100, 36, 'pwr')
r5 = p.node('LMR33630<br><b>+5V</b> 3 A', 0, 240, 130, 50, 'pwr')
r33m = p.node('TPS62130<br><b>+3V3_MEZZ</b> 3 A', 160, 240, 140, 50, 'pwr')
rvadj = p.node('TPS62130<br><b>VADJ</b> 1.8/2.5/3.3 V<br>EN by STM32', 330, 240, 150, 60, 'pwr')
r12m = p.node('1.1 A polyfuse<br><b>+12V_MEZZ</b>', 510, 240, 130, 50, 'pwr')
r33 = p.node('LMR33630<br><b>+3V3</b> 3 A<br>EN = PG_1V8', 670, 240, 130, 60, 'pwr')
r10 = p.node('TPS62130<br><b>+1V0</b> VCCINT/BRAM', 0, 340, 150, 50, 'pwr')
r18 = p.node('TPS62130<br><b>+1V8</b> VCCAUX', 0, 430, 150, 50, 'pwr')
mga = p.node('TLV75801<br><b>+1V0_MGT</b> MGTAVCC', 190, 430, 150, 50, 'pwr')
mgt = p.node('TLV75801<br><b>+1V2_MGT</b> MGTAVTT', 370, 430, 150, 50, 'pwr')
r135 = p.node('TLV62568<br><b>+1V35</b> DDR3L', 0, 520, 150, 50, 'pwr')
vtt = p.node('TPS51200<br><b>VTT / VREF</b>', 190, 520, 150, 50, 'pwr')
usbh = p.node('TPS2051<br><b>+5V_USBH</b>', 190, 340, 130, 50, 'pwr')
aud = p.node('ferrite + LM2662<br><b>+5V_AUD / -5V</b>', 350, 340, 150, 50, 'aud')
filt = p.node('ferrites<br>+3V3_AUD, VDDA,<br>SFP0/1, ETH_AVDD', 660, 350, 150, 60, 'pwr')
p.edge(inp, prot)
p.edge(prot, v12)
for t in (r5, r33m, rvadj, r12m):
    p.edge(v12, t)
p.edge(v12, r33)
p.edge(r5, r10, 'PG_5V', exit=(0.3, 1), entry=(0.43, 0))
p.edge(r10, r18, 'PG_1V0')
p.edge(r18, mga)
p.edge(mga, mgt, 'RC delay')
p.edge(r18, r135, 'PG_1V8')
p.edge(r135, vtt)
p.edge(r5, usbh, exit=(0.8, 1), entry=(0.5, 0), pts=((104, 318), (255, 318)))
p.edge(r5, aud, exit=(0.8, 1), entry=(0.5, 0), pts=((104, 318), (425, 318)))
p.edge(r33, filt)
p.save()

# backplane system (eurocard 3u subrack)
s = Diagram('backplane')
s.group('3U Eurocard subrack (IEEE 1101), 160 mm cards, front panels on the left', 0, 0, 900, 470)
bp = s.node('<b>backplane PCB</b><br>DIN 41612 C 3x32 female per slot<br><br>'
            '+12V (a1-c2)<br>-12V (a28, c28)<br>+5V (a30, c30)<br>GND<br><br>'
            'TDM audio bus<br>MCLK / BCLK / FS / DOUT / DIN<br><br>CAN-FD control bus', 640, 40, 230, 400, 'bus')
psu = s.node('<b>PSU card / module</b><br>+12V, -12V, +5V', 30, 40, 250, 60, 'pwr')
mcb = s.node('<b>MAIN_COMPUTE_BOARD</b><br>STM32H755 + XC7A100T<br>TDM master clock, CAN host', 30, 130, 250, 70, 'fpga')
fx = s.node('<b>FX board</b><br>TDM in/out, CAN', 30, 230, 250, 50, 'card')
flt = s.node('<b>filter board</b><br>analog, uses +/-12V', 30, 310, 250, 50, 'card')
mst = s.node('<b>master / mixer board</b><br>volume, outputs, CAN', 30, 390, 250, 50, 'card')
# one straight link per slot, entering the backplane at the card's height
for card, yc, lab, kw in ((psu, 70, 'power', dict(color='#d79b00', thick=True)),
                          (mcb, 165, 'slot: power + TDM + CAN', dict(both=True, thick=True)),
                          (fx, 255, 'slot', dict(both=True)), (flt, 335, 'slot', dict(both=True)),
                          (mst, 415, 'slot', dict(both=True))):
    s.edge(card, bp, lab, exit=(1, 0.5), entry=(0, (yc - 40) / 400.0), **kw)
s.save()
print('drawio sources written to', OUT)
