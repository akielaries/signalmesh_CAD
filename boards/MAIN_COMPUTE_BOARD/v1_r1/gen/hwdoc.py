import os
import re
import sys

import pcbnew

PCB, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
fps = {f.GetReference(): f for f in b.Footprints()}


def pins(ref):
    out = []
    for p in fps[ref].Pads():
        n = p.GetNetname()
        if not p.GetNumber():
            continue
        n = '-' if (not n or n.startswith('unconnected-')) else n.split('/')[-1]
        out.append((p.GetNumber(), n))
    seen, uniq = set(), []
    for k in sorted(out, key=lambda t: (len(t[0]), t[0])):
        if k[0] not in seen:
            seen.add(k[0])
            uniq.append(k)
    return uniq


def where(ref):
    f = fps[ref]
    x, y = f.GetPosition().x / 1e6 - 50, f.GetPosition().y / 1e6 - 50
    side = 'bottom side' if f.IsFlipped() else 'top'
    return 'x %.0f mm, y %.0f mm from the front-top corner, %s' % (x, y, side)


def table(ref, title, note=''):
    s = '### %s (%s)\n\n%s, `%s`. %s\n\n| pin | signal |\n|---|---|\n' % (
        title, ref, where(ref), fps[ref].GetValue(), note)
    for n, net in pins(ref):
        s += '| %s | %s |\n' % (n, net)
    return s + '\n'


def by_value(sub):
    return [r for r, f in fps.items() if sub in f.GetValue()]


doc = '''
# hardware reference

Everything a user of this open board needs to plug in, debug and bring up. Positions
are measured from the front-top corner of the card (front panel on the left, card guides
along the top and bottom edges). Generated from the board file.

## front panel (top to bottom)

| connector | ref | function |
|---|---|---|
| 5.5 x 2.1 mm barrel jack | {{JACK}} | 12 V in, centre positive. Same net as DIN a1-c2, use one source |
| SFP cage | {{SFP0}} | GTP lane 0, up to 6.25 Gb/s (1G/2.5G SFP, direct-attach cables) |
| SFP cage | {{SFP1}} | GTP lane 1 |
| RJ45 with magnetics | {{RJ45}} | 10/100 Ethernet, LAN8742A RMII to the STM32 |
| USB-A host | {{USBA}} | STM32 OTG_FS host, 5 V 0.5 A switched VBUS (USB-MIDI keyboards, storage) |
| USB-C | {{USBC}} | STM32 OTG_HS device through USB3300 ULPI PHY, 480 Mb/s (updates, UAC2, console) |

## rear

| connector | ref | function |
|---|---|---|
| DIN 41612 type C 3x32 male, right angle | {{DIN}} | backplane: power, TDM audio bus, CAN-FD. See [pinout](pinout.md) |
| VITA 57.1 HPC carrier (Samtec ASP-134486-01) | {{VITA}} | mezzanine site, top side. LPC cards fit |

## debug and programming

| header | ref | use |
|---|---|---|
| MIPI-10 1.27 mm | {{MCUMIPI}} | STM32 SWD + SWO + reset (Black Magic Probe, ST-LINK, J-Link) |
| 1x6 2.54 mm | {{MCUSWD}} | STM32 SWD on dupont wires |
| 1x6 2.54 mm FTDI order | {{MCUUART}} | STM32 console UART (USART1) |
| 1x2 2.54 mm | {{BOOT0}} | BOOT0: jumper to boot the ST system bootloader (USB DFU) |
| 2x7 2.0 mm | {{JTAG14}} | FPGA JTAG, Xilinx platform cable pinout |
| 1x6 2.54 mm | {{JTAG6}} | FPGA JTAG, Digilent HS2 order |
| MIPI-10 1.27 mm | {{SCMIPI}} | soft-core SWD on FPGA user IO (bank 15) |
| 1x6 2.54 mm FTDI order | {{SCUART}} | soft-core console UART on FPGA user IO |

All headers are 3.3 V. Pin 1 of the FTDI-order headers is GND; a 3.3 V FTDI cable plugs
in with its black wire on pin 1. VCC (pin 3) is not connected so the cable cannot back-power
the board.

## buttons and LEDs

| ref | name | function |
|---|---|---|
{{BUTTONS}}

## expansion headers

| header | ref | use |
|---|---|---|
| Pmod 2x6 socket | {{PMODA}} | FPGA bank 13, Digilent 12-pin, 3.3 V |
| Pmod 2x6 socket | {{PMODB}} | FPGA bank 13 |
| 2x20 2.54 mm | {{BRK}} | STM32 breakout: 24 GPIO (ADC, timers, SAI1, SDMMC1), I2C1, FDCAN1, NRST, 3V3, 5V |
| 1x6 2.54 mm | {{IOX}} | TCA9535 spare GPIO P14-P17 |
| 1x3 2.54 mm | {{CAN}} | CAN-FD bus (also on the DIN). Solder jumper {{CANTERM}} adds 120 R termination |

## audio and analog

| connector | ref | signal |
|---|---|---|
| u.fl | {{AUDL}} | FPGA audio left: CS4344, OPA1656 buffer (gain 1.5), 10 uF + 100 R out |
| u.fl | {{AUDR}} | FPGA audio right |
| u.fl | {{DAC1}} | STM32 DAC1 channel 1 (PA4), unbuffered |

## test points

Rails, power-goods and the FPGA/STM32 status lines are 1.5 mm pads on the bottom side,
each placed under the part that sources it and labelled on the bottom silkscreen with
what it measures. They are flat, so they respect the bottom height limit and can be
reached by a bed-of-nails fixture. Four GND loops (Keystone 5015) on the top side take a
scope ground clip: in the power corner, by the debug headers, on the STM32 side and in the
audio corner. See [bring-up](bringup.md) for the power-on order.

| label | ref | net | expect | location |
|---|---|---|---|---|
{{TESTPOINTS}}

## clocks on the board

| ref | frequency | drives |
|---|---|---|
{{CLOCKS}}

## connector pinouts

'''

R = {'JACK': by_value('12V IN')[0], 'SFP0': sorted(by_value('SFP cage'))[0], 'SFP1': sorted(by_value('SFP cage'))[1],
     'RJ45': by_value('HR911105A')[0], 'USBA': by_value('USB-A')[0], 'USBC': by_value('USB-C')[0],
     'DIN': by_value('DIN41612')[0], 'VITA': by_value('VITA57')[0], 'MCUMIPI': by_value('MCU_SWD MIPI')[0],
     'MCUSWD': [r for r in by_value('MCU_SWD') if 'MIPI' not in fps[r].GetValue()][0],
     'MCUUART': by_value('MCU_UART')[0], 'BOOT0': by_value('BOOT0')[0], 'JTAG14': by_value('FPGA_JTAG Xilinx')[0],
     'JTAG6': by_value('FPGA_JTAG 6p')[0], 'SCMIPI': by_value('SOFTCORE_SWD')[0], 'SCUART': by_value('SOFTCORE_UART')[0],
     'PMODA': by_value('PMODA')[0], 'PMODB': by_value('PMODB')[0], 'BRK': by_value('MCU_BREAKOUT')[0],
     'IOX': by_value('IOX_SPARE')[0], 'CAN': [r for r in by_value('CAN') if fps[r].GetValue() == 'CAN'][0],
     'CANTERM': by_value('CAN_TERM')[0], 'AUDL': by_value('ACM_DAC_L')[0], 'AUDR': by_value('ACM_DAC_R')[0],
     'DAC1': by_value('DAC_L_PRB')[0]}

btn = {'MCU_RESET': 'STM32 reset (NRST)', 'MCU_USER': 'STM32 user button, PC13, active high',
       'FPGA_PROG': 'pulls PROGRAM_B low: FPGA clears and waits to be reconfigured',
       'FPGA_BTN0': 'FPGA user input, active high', 'FPGA_BTN1': 'FPGA user input, active high'}
led = {'RED 12V': '12 V present', 'GREEN 3V3': '3.3 V rail up', 'GREEN DONE': 'FPGA configured (DONE high)'}
lines = []
for r in sorted(fps, key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r)))):
    v = fps[r].GetValue()
    if r.startswith('SW') and v in btn:
        lines.append('| %s | %s | %s |' % (r, v, btn[v]))
    if r.startswith('D') and (v in led or v in ('GREEN', 'BLUE')):
        nets = [n for _, n in pins(r) if n not in ('GND', '-')]
        drv = re.sub(r'_LED$', '', nets[0]) if nets else ''
        lines.append('| %s | %s | %s |' % (r, v, led.get(v, 'user LED, driven by %s' % drv)))
clk = []
for r in sorted(fps):
    if re.match(r'^[XY]\d', r):
        nets = [n for _, n in pins(r) if n not in ('GND', '+3V3', '-')]
        clk.append('| %s | %s | %s |' % (r, fps[r].GetValue(), ', '.join(sorted(set(nets)))))
EXPECT = {'12VIN': '12 V (input, before protection)', '12V': '12 V (after fuse, reverse FET and shunt)', '5V': '5.0 V',
          '3V3': '3.3 V', '1V0': '1.00 V', '1V8': '1.80 V', '1V35': '1.35 V',
          'VADJ': '0 V until enabled, then 1.8/2.5/2.6/3.3 V per VADJ_SEL', '3V3M': '3.3 V', '12VM': '12 V',
          'MGTAVCC': '1.00 V', 'MGTAVTT': '1.20 V', '5VA': '5.0 V', '3V3A': '3.3 V', 'VTT': '0.675 V',
          'VREF': '0.675 V', 'PG5V': 'high (5 V) when 5V is good', 'PG1V0': 'high (5 V) when 1V0 is good',
          'PG1V8': 'high (5 V) when 1V8 is good', 'PG3V3': 'high (5 V) when 3V3 is good',
          'PG3V3M': 'high (5 V) when 3V3_MEZZ is good', 'PGVADJ': 'high (3.3 V) when VADJ is good',
          'DONE': 'high after the FPGA is configured', 'INIT': 'high once the FPGA has cleared its memory',
          'NRST': '3.3 V, low while the STM32 is in reset', 'GND': '0 V', 'DAC_L': 'STM32 DAC1 output'}
order = list(EXPECT)
tps = []
for r, f in fps.items():
    if r.startswith('TP') and f.GetValue().startswith('TP '):
        lab = f.GetValue()[3:]
        net = [n for _, n in pins(r)][0]
        tps.append((order.index(lab) if lab in order else 99, int(re.sub(r'\D', '', r)), lab, r, net))
tp_lines = []
for _, _, lab, r, net in sorted(tps):
    loc = where(r).replace(' from the front-top corner', '')
    if 'top' in loc:
        loc = loc.replace(', top', '')
    tp_lines.append('| %s | %s | %s | %s | %s |' % (lab, r, net, EXPECT.get(lab, ''), loc))
R['TESTPOINTS'] = '\n'.join(tp_lines)
R['BUTTONS'] = '\n'.join(lines)
R['CLOCKS'] = '\n'.join(clk)
for k, v in R.items():
    doc = doc.replace('{{' + k + '}}', v)
for v, title, note in (('MCU_SWD MIPI', 'STM32 SWD, MIPI-10', 'Key pin 7 removed.'),
                       ('SOFTCORE_SWD', 'soft-core SWD, MIPI-10', ''),
                       ('FPGA_JTAG Xilinx', 'FPGA JTAG 2x7', ''), ('FPGA_JTAG 6p', 'FPGA JTAG 1x6', ''),
                       ('MCU_UART', 'STM32 console UART', 'Pin 4 is the STM32 RX (connect FTDI TXD).'),
                       ('SOFTCORE_UART', 'soft-core UART', ''), ('PMODA', 'Pmod A', 'Socket pin numbering: odd row is Pmod pins 1-6.'),
                       ('PMODB', 'Pmod B', ''), ('MCU_BREAKOUT', 'STM32 breakout 2x20', ''),
                       ('IOX_SPARE', 'expander spare', ''), ('BOOT0', 'BOOT0', '')):
    r = by_value(v)[0] if v != 'MCU_SWD MIPI' else by_value(v)[0]
    doc += table(r, title, note)
open(os.path.join(OUT, 'hardware.md'), 'w').write(doc.lstrip('\n'))
print('hardware.md written')
