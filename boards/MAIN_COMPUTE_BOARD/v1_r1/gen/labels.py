# silkscreen labels shared by pcbbuild and resilk
#   (anchor refs, text) placed by silkplace next to the part
#   (anchor refs, text, x, y[, angle]) placed at a fixed board position; the anchors' refs go to fab

# header field: labels sit in the gaps between the aligned rows
HDR_FIXED = [
    (('FPGA_JTAG 6p', 'FPGA_JTAG Xilinx'), 'FPGA JTAG', 118.0, 131.25),
    (('MCU_SWD',), 'MCU SWD', 140.35, 131.25),
    (('BOOT0',), 'BOOT0', 152.3, 131.25),
    (('MCU_UART FTDI',), 'MCU UART', 134.75, 137.1),
    (('SOFTCORE_UART FTDI',), 'SC UART', 161.25, 134.3, 90),
    (('MCU_SWD MIPI-10',), 'MCU SWD', 148.75, 137.55),
    (('SOFTCORE_SWD MIPI-10',), 'SC SWD', 157.25, 137.55),
    (('PMODA',), 'PMOD A', 118.85, 139.55),
    (('PMODB',), 'PMOD B', 135.85, 139.55),
]
NEAR = {'MCU_BREAKOUT': 'MCU BREAKOUT', 'IOX_SPARE': 'IOX', 'CAN': 'CAN'}
BTN = [('FPGA_PROG', 'PROG'), ('FPGA_BTN0', 'BTN0'), ('FPGA_BTN1', 'BTN1'), ('MCU_RESET', 'RESET'), ('MCU_USER', 'USER')]


def build(byvalue, audio_named):
    # byvalue: value -> ref
    out = [(byvalue[v], lab) for v, lab in BTN] + list(audio_named)
    for item in HDR_FIXED:
        vals, rest = item[0], item[1:]
        out.append((tuple(byvalue[v] for v in vals),) + tuple(rest))
    out += [(byvalue[v], lab) for v, lab in NEAR.items() if v in byvalue]
    out += [(r, v[3:]) for v, r in byvalue.items() if r.startswith('TP') and v.startswith('TP ') and v != 'TP GND']
    # gnd loops share a value, so they are listed by ref
    return out
