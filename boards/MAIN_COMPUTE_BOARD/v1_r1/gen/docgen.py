import os
import re
import sys

import dfpga
import dstm32
import dmezz

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def w(name, text):
    open(os.path.join(OUT, name), 'w').write(text.lstrip('\n'))


w('index.md', '''
# MAIN_COMPUTE_BOARD v1_r1

General-purpose STM32H7 + Artix-7 compute card in the 3U Eurocard format (160 x 100 mm).
It is the brain for the signalmesh synth: the FPGA does the DSP and drives the on-board DAC,
and it can also drive RF or other front ends through the VITA 57.1 mezzanine.

- [power tree and sequencing](power.md)
- [pin plans: STM32, FPGA banks, connectors](pinout.md)
- [PCB: stackup, impedance, net classes, floorplan](pcb.md)
- [bring-up and firmware notes](bringup.md)
- [backplane system and Eurorack notes](system.md)
- [performance, clocks and overclocking](performance.md)
- [hardware reference: connectors, headers, buttons, LEDs](hardware.md)

## block diagram

![system block diagram](export/system.svg)

source: [system.drawio](system.drawio) (open in draw.io / diagrams.net to edit)

## key parts

| function | part | notes |
|---|---|---|
| MCU | STM32H755BIT6 (LQFP208) | LDO supply mode for VOS0 480 MHz. BIT3 is not a substitute (no VOS0) |
| FPGA | XC7A100T-2FGG484I | wire-bond plastic BGA, GTP max 6.25 Gb/s in this package |
| memory | MT41K256M16TW-107 | DDR3L x16, 800 Mb/s with internal VREF, MIG chip select disabled |
| boot/bitstream flash | 2x W25Q01JVZEIQ (WSON-8) | QUADSPI dual-flash, 8-bit, 256 MB memory mapped, shared BK1_NCS. Bottom side, under the STM32 |
| USB HS PHY | USB3300-EZK | ULPI, 24 MHz crystal |
| Ethernet PHY | LAN8742A | RMII, PHY sources the 50 MHz REF_CLK |
| audio DAC | CS4344 + OPA1656 | ported from APM v7, -5 V from LM2662 |
| mezzanine | Samtec ASP-134486-01 | VITA 57.1 HPC, LPC cards fit |
| backplane | DIN 41612 C 3x32 male R/A | provisional pinout, see [pinout](pinout.md) |
''')

w('power.md', '''
# power tree

12 V comes from the barrel jack or the DIN backplane (same net, use one at a time).
Every rail below is generated on board. Sequencing is automatic and follows the
Artix-7 order in DS181 (VCCINT, VCCBRAM, VCCAUX, VCCO; MGTAVCC before MGTAVTT).

![power tree](export/power.svg)

source: [power.drawio](power.drawio)

## rails

| rail | source | enable | consumers | budget (estimate) |
|---|---|---|---|---|
| +12V | input | - | bucks, VITA 12P0V | 2.5 A peak |
| +5V | LMR33630 (400 kHz, 6.8 uH) | 12V UVLO about 9.2 V | 1V0/1V8/1V35 bucks, USB host VBUS, audio | 3 A |
| +3V3_MEZZ | TPS62130 from 12V | 12V UVLO | VITA 3P3V (up to 3 A per spec) | 3 A |
| VADJ | TPS62130 from 12V | STM32 via TCA9535 P00 | FPGA banks 16/35, VITA VADJ | 3 A |
| +1V0 | TPS62130 from 5V | PG_5V | VCCINT, VCCBRAM | 1.5-2.5 A |
| +1V8 | TPS62130 from 5V | PG_1V0 | VCCAUX, MGT LDOs, VCCADC | 0.6 A |
| +1V0_MGT | TLV75801 from 1V8 | 1V8 | MGTAVCC | 0.2 A |
| +1V2_MGT | TLV75801 from 1V8 | RC delay after 1V8 | MGTAVTT | 0.3 A |
| +1V35 | TLV62568 from 5V | PG_1V8 | DDR3L VDD/VDDQ, FPGA bank 34 | 0.5 A |
| VTT_DDR / VREF_DDR | TPS51200 | +3V3 | DDR addr/cmd termination | 0.3 A |
| +3V3 | LMR33630 | PG_1V8 | STM32, FPGA banks 0/13/14/15, PHYs, flash, SFPs | 1.5 A |
| +5V_USBH | TPS2051C | STM32 via TCA9535 P12 | USB-A host VBUS | 0.5 A |
| +5V_AUD / -5V | ferrite + LM2662 | - | OPA1656 rails | 50 mA |

## sequencing

1. 12 V rises past about 9.2 V, which enables +5V and +3V3_MEZZ.
2. +5V power-good enables +1V0 (VCCINT and VCCBRAM).
3. +1V0 power-good enables +1V8 (VCCAUX). The MGT LDOs follow 1V8, with MGTAVTT
   held back by an RC so it ramps after MGTAVCC.
4. +1V8 power-good enables +3V3 (all 3.3 V VCCO banks, the STM32) and +1V35.
   This keeps VCCO - VCCAUX inside the 2.625 V / 300 ms DS181 limit.
5. The STM32 boots, reads the mezzanine EEPROM over I2C1, sets VADJ_SEL1:0 and
   enables VADJ, then asserts PG_C2M.

## VADJ select

| VADJ_SEL1 | VADJ_SEL0 | VADJ |
|---|---|---|
| 0 | 0 | 1.8 V (default after reset) |
| 0 | 1 | 2.5 V |
| 1 | 0 | 2.6 V |
| 1 | 1 | 3.3 V |

All four codes are safe for the FPGA. 3.3 V is only valid when the mezzanine does not
need LVDS outputs (Artix-7 HR LVDS outputs need 2.5 V).
''')

# pinout: generated from the schematic data
stm = []
for pin, (net, af) in sorted(dstm32.PINMAP.items(), key=lambda kv: (kv[0][1], int(re.sub(r'\D', '', kv[0][2:]) or 0))):
    stm.append('| %s | %s | %s |' % (pin, net.lstrip('.'), af or 'GPIO'))
inv = {v: k for k, v in dfpga.BYNAME.items() if k.startswith('IO_')}
banks = {}
for ball, net in dfpga.PLAN.items():
    n = inv.get(ball)
    if not n or net == 'NC':
        continue
    b = n.rsplit('_', 1)[1]
    banks.setdefault(b, []).append((ball, n[3:-len(b) - 1], net))
vcco = {'13': '3.3 V', '14': '3.3 V', '15': '3.3 V', '16': 'VADJ', '34': '1.35 V', '35': 'VADJ'}
fpga_txt = ''
for b in sorted(banks):
    fpga_txt += '\n### bank %s (VCCO %s)\n\n| ball | pin | net |\n|---|---|---|\n' % (b, vcco[b])
    for ball, n, net in sorted(banks[b], key=lambda t: t[2]):
        fpga_txt += '| %s | %s | %s |\n' % (ball, n, net)
gtp = [(ball, net) for ball, net in dfpga.PLAN.items() if net.startswith(('GTP', 'MEZZ_DP')) and ball in
       [dfpga.BYNAME[k] for k in dfpga.BYNAME if 'MGT' in k]]
vm = dmezz.vita_map()
used = []
for pin, sig in sorted(vm.items(), key=lambda kv: (kv[0][0], int(kv[0][1:]))):
    if sig.startswith(('LA', 'CLK0', 'CLK1', 'GBTCLK0', 'DP0', 'DP1', 'SCL', 'SDA', 'PG_', 'PRSNT', 'GA', '12P0V',
                       '3P3V', 'VADJ')):
        used.append('| %s | %s |' % (pin, sig))

w('pinout.md', '''
# pin plans

Generated from the same tables that build the schematic, so these match the design.

## STM32H755BIT6 (LQFP208)

FMC bank 1 runs as a synchronous NOR/PSRAM bus, 32-bit, non-multiplexed, with
A0-A18 (2 MB window). NL/NADV is not used: the FPGA latches the address on the
first FMC_CLK edge with NE1 low, and the address is held for the whole burst
(DS12919 fig 32/33). FMC_CLK max is 125 MHz at 3.3 V.

| pin | net | function |
|---|---|---|
''' + '\n'.join(stm) + '''

Slow controls live on the TCA9535 at I2C1 address 0x20: P00 VADJ_EN, P01/P02
VADJ_SEL0/1, P03 VADJ_PG, P04 MEZZ_PRSNT_L, P05 MEZZ_PG_M2C, P06 MEZZ_PG_C2M,
P07 PG_1V8, P10 ETH_NRST, P11 ULPI_RST, P12 USBH_VBUS_EN, P13 USBH_OC_N,
P14-P17 spare (IOX_SPARE header).

## XC7A100T-2FGG484 banks

- bank 14: FMC D0-D31 sit on the SelectMAP D00-D31 pins, so the same wires carry
  the bitstream at boot. CSI_B and RDWR_B are STM32 GPIOs.
- bank 34: DDR3L. Data bytes in T0/T1, address/command in T2/T3 with CK in T3 and
  ODT on IO_0, RESET_N on IO_25. CS_N is tied low at the DRAM. This follows the
  UG586 byte-group rules (same layout as the Arty A7-100).
- banks 35/16: VITA LA00-LA16 + CLK0_M2C on bank 35, LA17-LA33 + CLK1_M2C on bank 16.
  The CC pairs land on MRCC/SRCC pins.
''' + fpga_txt + '''
### GTP quad 216

| lane | use |
|---|---|
| 0 | SFP0 (TX/RX AC coupled on board) |
| 1 | SFP1 |
| 2 | VITA DP0 (C2M AC coupled on board, M2C on the card) |
| 3 | VITA DP1 |
| REFCLK0 | 125 MHz LVDS XO (SiT9120) |
| REFCLK1 | VITA GBTCLK0_M2C |

## VITA 57.1 HPC (connected pins)

HA, HB, DP2-DP9, CLK2/3_BIDIR and the JTAG pins are not connected. GA0/GA1 are
tied low, so the card EEPROM answers at 0x50 on I2C1.

| pin | signal |
|---|---|
''' + '\n'.join(used) + '''

## DIN 41612 backplane (provisional)

| pins | signal |
|---|---|
| a1, a2, b1, b2, c1, c2 | +12V (shared with the barrel jack) |
| a28, c28 | -12V (for analog cards, not connected on this board) |
| a30, c30 | +5V (for other cards, not connected on this board) |
| a3/b3/c3, a32/b32/c32, even b rows | GND |
| a5 | BP_TDM_MCLK |
| a7 | BP_TDM_BCLK |
| a9 | BP_TDM_FS |
| a11 | BP_TDM_DOUT |
| a13 | BP_TDM_DIN |
| c5 / c6 | BP_CANH / BP_CANL (SN65HVD230, 120R via solder jumper) |

## debug and user headers

| header | pinout |
|---|---|
| MCU_SWD MIPI-10 | 1 3V3, 2 SWDIO, 3 GND, 4 SWCLK, 5 GND, 6 SWO, 9 GND, 10 NRST |
| MCU_SWD 1x6 | 3V3, SWCLK, GND, SWDIO, NRST, SWO |
| MCU_UART 1x6 (FTDI) | GND, -, -, RX (from FTDI TXD), TX (to FTDI RXD), - |
| SOFTCORE_SWD MIPI-10 | same as MCU, driven by FPGA user IO (bank 15) |
| SOFTCORE_UART 1x6 (FTDI) | same as MCU UART |
| FPGA_JTAG 2x7 2 mm | Xilinx platform cable pinout |
| FPGA_JTAG 1x6 | VREF, GND, TCK, TDO, TDI, TMS (Digilent HS2 order) |
| PMODA / PMODB | Digilent 12-pin, 3V3, FPGA bank 13 |
| MCU_BREAKOUT 2x20 | 24 STM32 GPIO (ADC, timers, SAI1, SDMMC1 on PC8-PC12/PD2), I2C1, FDCAN1, NRST, power |
''')

w('pcb.md', '''
# PCB

## stackup: JLC08161H-1080 (8 layers, 1.6 mm, 1 oz outer, 0.5 oz inner)

| layer | role | dielectric below |
|---|---|---|
| F.Cu | signal (outer) | 1080 prepreg 0.0764 mm, er 3.91 |
| In1 | GND | core 0.30 mm, er 4.41 |
| In2 | signal, main high-speed inner layer | 7628 prepreg 0.2104 mm, er 4.40 |
| In3 | GND | core 0.30 mm |
| In4 | power planes, split by rail | 7628 prepreg 0.2104 mm |
| In5 | signal, slower inner layer | core 0.30 mm |
| In6 | GND | 1080 prepreg 0.0764 mm |
| B.Cu | signal (outer) | |

## impedance

Widths come from a 2D finite-difference field solve of these exact cross sections
(checked against Cohn's exact stripline and Hammerstad microstrip results).

| class | outer (F/B) | inner (In2/In5) | nets |
|---|---|---|---|
| SE50 | 0.127 mm | 0.23 mm | FMC, ULPI, RMII, QSPI, clocks, I2S |
| DDR | 0.127 mm | 0.23 mm | DDR DQ/DM/addr/cmd |
| DIFF100 | 0.10 / 0.18 gap | 0.115 / 0.10 gap | VITA LA, GTP, SFP, DDR CK/DQS |
| USB90 | 0.11 / 0.127 gap | - | USB HS and FS |
| PWR | 0.4 mm min | 0.4 mm min | rails |

Per-layer widths are enforced in `MAIN_COMPUTE_BOARD.kicad_dru`. Under the FPGA and
DDR BGAs the clearance drops to 0.09 mm for escape routing (JLC 8-layer minimum).

## floorplan

- front panel (left 100 mm edge), top to bottom: barrel jack, SFP0, SFP1, RJ45, USB-A, USB-C.
  Body gaps are 2.75 mm or more. Fronts sit 1.55 mm proud of the edge.
- rear: DIN 41612 type C 3x32, the 19 inch subrack / VME backplane connector
  (IEC 60603-2). Not Eurorack.
- 3 mm card-guide strips along the long edges are keepouts.
- FPGA in the middle with its GTP corner facing the SFPs. DDR3 on the bank-34 side,
  STM32 on the bank-14/15 side, VITA connector above.
- kept-clear routing channels on top: FPGA to SFP (GTP), FPGA to STM32 (FMC),
  FPGA to VITA (LA pairs). FPGA and STM32 decoupling sits on the bottom side.
- power bottom-left, audio in its own bottom-right corner, mirrored L/R.
''')

w('bringup.md', '''
# bring-up and firmware notes

## STM32

- select LDO supply in PWR_CR3 before raising the clock (SDEN=0, LDOEN=1). VOS0 is
  reached from VOS1 by setting ODEN in SYSCFG_PWRCR. VOS0 (480 MHz) needs a
  suffix-6 part.
- set USB33DEN before using either USB controller (VDD33USB is supplied externally).
- QUADSPI runs dual-flash (DFM=1). Both flashes share BK1_NCS, so single-flash access
  (DFM=0 with FSEL) is not possible on this board. W25Q01JV: check the status register
  handling in the driver, it differs a little from Macronix parts.

## FPGA configuration (slave SelectMAP, M[2:0]=110)

1. drive PROGRAM_B low, release, wait for INIT_B high.
2. hold RDWR_B low and CSI_B low for the whole load. If RDWR_B is high while CSI_B is
   low the FPGA drives the data bus, and toggling RDWR_B with CSI_B low aborts.
3. clock the bitstream on FMC D0-D15 with CCLK (STM32 GPIO). Speed is not critical.
4. wait for DONE high, then release CSI_B/RDWR_B. The FMC pins become user IO.

JTAG stays available at all times on the 2x7 and 1x6 headers.

## DDR3 (MIG)

- chip select disabled (CS_N is tied low at the DRAM), internal VREF, 800 Mb/s max.
- sys_clk comes from the 100 MHz oscillator through an MMCM ("no buffer" option).
- re-run MIG pin validation in Vivado with the bank 34 plan in [pinout](pinout.md).

## mezzanine

- read the card EEPROM at 0x50 (I2C1), set VADJ_SEL, enable VADJ, wait VADJ_PG,
  then drive MEZZ_PG_C2M high.
''')
w('system.md', '''
# backplane system and Eurorack notes

![backplane system](export/backplane.svg)

source: [backplane.drawio](backplane.drawio)

## Eurocard, not Eurorack

This board is a 3U **Eurocard** (IEC 60297 / IEEE 1101): 100 x 160 mm, slides into card
guides in a 19 inch subrack, and plugs into a backplane through the DIN 41612 connector
on its rear edge. Eurorack (Doepfer A-100) grew out of the same 3U subrack height, so
panel height and rails are shared, but the rest differs:

| | this board (Eurocard) | Eurorack module |
|---|---|---|
| depth | 160 mm card | typical cases 40-90 mm deep |
| power | backplane DIN 41612 (or barrel jack) | 10/16-pin ribbon: +12V, -12V, optional +5V |
| interconnect | backplane buses (TDM audio, CAN) | patch cables (CV, gate, audio) |
| panel | 100 mm front edge, 3U | width in HP (5.08 mm) |

It only fits extra-deep Eurorack cases and has no Eurorack power header, so it is not
Eurorack compatible as built.

## recommended system

A 3U subrack with a custom DIN 41612 backplane, one slot per card:

- **power:** +12V on a1-c2, -12V on a28/c28 and +5V on a30/c30 (analog cards such as
  the filter board need +/-12V), GND on rows 3/32 and the even b pins.
- **audio:** a TDM bus (MCLK, BCLK, FS, DOUT, DIN). The compute board is the clock master,
  so every card runs sample-locked.
- **control:** CAN-FD for presets, parameters and MIDI-style events.

To mix in real Eurorack modules, build a small Eurorack-format bridge module (CV/gate in
and out, ribbon power) cabled to the subrack, or a mezzanine with CV I/O on the VITA site.
''')
w('performance.md', '''
# performance and clocking

Datasheet limits for the parts on this board and the clock plan the board is built around.
Sources: STM32H755 datasheet DS12919 rev 3 and RM0399 rev 5, Artix-7 DS180/DS181 v1.27,
UG470, UG482. "Board" columns are what this design is set up to run, not just the silicon limit.

## STM32H755BIT6 (dual core)

| item | limit | notes |
|---|---|---|
| Cortex-M7 | 480 MHz at VOS0 | 1027 DMIPS (2.14 DMIPS/MHz). VOS0 needs the LDO (this board's supply mode) and Tj under 105 C. VOS1 400 MHz, VOS2 300, VOS3 200 |
| Cortex-M4 | 240 MHz | 300 DMIPS |
| AXI / AHB | 240 MHz | APB 120 MHz |
| M7 caches | 16 KB I + 16 KB D | |
| TCM | 64 KB ITCM + 128 KB DTCM, 0 wait state | |
| SRAM | 864 KB (AXI 512 + SRAM1-4) + 192 KB TCM + 4 KB backup | |
| flash | 2 x 1 MB | 4 wait states at 240 MHz ACLK (RM0399 table 16) |
| PLLs | 3 | wide VCO 192-960 MHz, input 2-16 MHz after DIVM |

### clock sources on the board

| source | part | use |
|---|---|---|
| HSE | 25 MHz crystal (Y1, 8 pF) | PLL1 reference: /5 = 5 MHz, x192 = 960 MHz VCO, /2 = 480 MHz M7 |
| LSE | 32.768 kHz crystal (Y2) | RTC |
| HSI48 | internal 48 MHz | USB OTG_FS (with clock recovery from SOF) |
| ULPI | 60 MHz from the USB3300 (24 MHz crystal Y3) | USB OTG_HS |
| RMII REF_CLK | 50 MHz from the LAN8742A (25 MHz crystal Y4) | Ethernet MAC |

### interfaces

| interface | silicon limit | board setup | throughput |
|---|---|---|---|
| FMC to FPGA | FMC_CLK 125 MHz (sync NOR/PSRAM, 2.7-3.6 V, 20 pF), kernel 300 MHz at VOS0 | 32-bit, kernel 240-250 MHz / 2 = 120-125 MHz | 480-500 MB/s peak, roughly 200-300 MB/s with MDMA bursts |
| QUADSPI (2x W25Q01JV, dual-flash) | 133 MHz SDR, 100 MHz DDR | 8 bits wide, SDR | 133 MB/s read; writes limited by the flash (page program ~1-2 MB/s) |
| USB OTG_HS | 480 Mb/s via ULPI | USB-C device | ~35-45 MB/s practical |
| USB OTG_FS | 12 Mb/s | USB-A host | MIDI, keyboards, storage |
| Ethernet | 10/100 Mb/s RMII | RJ45 | ~11 MB/s |
| SPI1-3 | 100 MHz master, 100 MHz slave RX | on the breakout | |
| SPI4-6 | 50 MHz master | | |
| USART | up to 12.5 Mb/s | console on USART1 | |
| I2C | 1 Mb/s (Fm+) | I2C1: expander, INA219, MAC EEPROM, VITA EEPROM | |
| FDCAN | classic + FD | SN65HVD230 to the backplane | the transceiver limits FD data rate (about 1 Mb/s class) |
| SAI | up to 192 kHz audio | SAI1 on the breakout | |
| SDMMC1 | 133 MHz | PC8-PC12/PD2 on the breakout | |
| ADC | 16-bit 3.6 MSPS, 12-bit 5.5 MSPS | breakout pins PA0, PA6, PC2, PC3, PF11 | |
| DAC | 12-bit, 1 MHz update | DAC1 ch1 (PA4) to u.fl | |
| HRTIM | 480 MHz, 2.1 ns resolution | | |
| GPIO | 133 MHz at 30 pF, 220 MHz at 10 pF (fastest speed setting) | | |

## XC7A100T-2FGG484

| resource | count |
|---|---|
| logic cells | 101,440 |
| slices (4 LUT6 + 8 FF each) | 15,850 (63,400 LUT, 126,800 FF) |
| distributed RAM | 1,188 Kb |
| block RAM | 135 x 36 Kb = 4,860 Kb |
| DSP48E1 | 240 |
| clock management tiles | 6 (MMCM + PLL each) |
| user IO in FGG484 | 285 (all HR banks) |
| GTP transceivers | 4 |
| XADC | 1, 12-bit 1 MSPS, on-die temperature and supply sensors |

### -2 speed grade limits (DS181)

| item | limit |
|---|---|
| global clock (BUFG) | 628 MHz |
| MMCM | input 10-800 MHz, VCO 600-1440 MHz, output up to 800 MHz |
| PLL | input 19-800 MHz, VCO 800-1866 MHz, output up to 800 MHz |
| block RAM | 460 MHz (no ECC), 365 MHz with ECC |
| DSP48E1 | 550 MHz fully pipelined |
| LVDS (HR banks) | 1250 Mb/s DDR per pair, 680 Mb/s SDR |
| IDELAY | 78 ps taps at 200 MHz ref, 52 ps at 300 MHz, 39 ps at 400 MHz |
| DDR3L (MIG, 4:1) | 800 Mb/s; internal VREF also caps at 800 Mb/s |
| GTP line rate | 0.5-6.25 Gb/s in this wire-bond package (6.6 Gb/s only in flip-chip packages) |
| GTP refclk | 60-660 MHz |
| configuration CCLK | 100 MHz (slave SelectMAP, master modes) |
| JTAG TCK | 66 MHz |
| junction temperature | 0-85 C commercial, -40-100 C industrial |

### FPGA clocks on the board

| clock | source | typical use |
|---|---|---|
| SYSCLK_100M | 100 MHz CMOS XO (X1), bank 15 MRCC | MMCM input for fabric, soft core, MIG (no buffer) |
| AUD_CLK_48K | 24.576 MHz XO (X2) | 48/96/192 kHz audio, MCLK = 512/256/128 x fs |
| AUD_CLK_44K | 22.5792 MHz XO (X3) | 44.1/88.2/176.4 kHz audio |
| GTP REFCLK0 | 125 MHz LVDS XO (X4) | SFP: 1.25 Gb/s 1000BASE-X, 2.5 Gb/s, up to 6.25 Gb/s links |
| GTP REFCLK1 | VITA GBTCLK0_M2C | clock from the mezzanine card |
| VITA CLK0/1_M2C | mezzanine | sample clocks from ADC/DAC cards |
| FMC_CLK | STM32 | FMC slave logic |

### data paths

| path | peak |
|---|---|
| FPGA DDR3L, x16 at 800 Mb/s | 1.6 GB/s |
| VITA LA pairs, 34 x 1.25 Gb/s | 42.5 Gb/s aggregate |
| GTP, 4 lanes x 6.25 Gb/s | 25 Gb/s line rate (about 20 Gb/s payload with 8b/10b) |
| STM32 to FPGA FMC | 480-500 MB/s peak |
| bitstream load, SelectMAP x16 at 100 MHz | 30.6 Mbit in about 20 ms |
| bitstream load, slave serial at 100 MHz | about 0.31 s |
| audio DAC (CS4344) | 24-bit up to 192 kHz |

## overclocking and headroom

- **STM32:** 480 MHz is the ceiling. The datasheet says PLL outputs "must be limited to the
  maximum frequency due to the product limitation (480 MHz for VOS0)". People have run H7s
  faster at room temperature, but that is outside the spec and not something to build a
  product on. The free headroom is elsewhere: run the FMC and QUADSPI kernels off PLL2/PLL3
  so they sit exactly at their limits (125 MHz FMC_CLK, 133 MHz QSPI) independent of the
  CPU clock, and keep hot code and buffers in ITCM/DTCM.
- **FPGA:** there is no fixed clock to overclock. You pick every clock with the MMCM/PLLs
  and Vivado's timing analysis tells you what the design closes at. Clocking above the
  timing-closed frequency works on some parts at room temperature but is not guaranteed;
  pipelining (more register stages in DSP/BRAM paths) is the supported way to go faster.
  The -2 grade already gives ~15-20% more than -1 (DSP 550 vs 464 MHz, BUFG 628 vs 464).
- **Interfaces with hard limits:** GTP 6.25 Gb/s (package), DDR3L 800 Mb/s (speed grade and
  internal VREF), FMC_CLK 125 MHz, QSPI 133 MHz SDR, USB HS 480 Mb/s. These are set by the
  silicon or the standard, not by clock settings.
- **Soft core:** an in-order ARM-ISA soft core on Artix-7 -2 typically closes around
  100-200 MHz depending on pipeline depth. The M7 stays the fast core; the soft core is for
  deterministic control next to the DSP.
''')
print('docs written to', OUT)
