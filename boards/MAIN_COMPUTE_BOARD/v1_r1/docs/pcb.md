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
DDR BGAs the clearance drops to 0.09 mm for escape routing (JLC 8-layer minimum). Inside
the VITA connector footprint it drops to 0.10 mm, so pairs can leave the 1.27 mm pin field.

## floorplan

- front panel (left 100 mm edge), top to bottom: barrel jack, SFP0, SFP1, RJ45, USB-A, USB-C.
  Body gaps are 2.75 mm or more. Fronts sit 1.55 mm proud of the edge.
- rear: DIN 41612 type C 3x32, the 19 inch subrack / VME backplane connector
  (IEC 60603-2). Not Eurorack.
- 3 mm card-guide strips along the long edges are keepouts.
- FPGA in the middle with its GTP corner facing the SFPs. DDR3 on the bank-34 side,
  STM32 on the bank-14/15 side, VITA connector above.
- VITA 57.1 site: connector centre at (100, 19.5) mm from the front-top corner. A
  single-width module (78.8 x 69 mm, regions 2+3) then covers x 65.5-134.5, y 3.1-81.9:
  3 mm inside the top edge, clear of the card guide. Two M2.5 standoffs sit at the
  connector ends (2.0 mm toward the module, +-31.5 mm along it) for 10 mm spacers.
  The far-end standoff pair is not fitted, because it would land on the audio DAC.
- with a module fitted, everything under that outline is covered, including the button
  and LED rows and the dupont duplicate headers. The debug headers you need with a card
  fitted (Xilinx JTAG, both UARTs, both MIPI-10 SWD) are in the bottom header field,
  outside the outline.
- header field along the bottom edge, three aligned rows with pin 1 on the left and
  silkscreen labels: row a has the FPGA JTAG 1x6, MCU SWD 1x6 and BOOT0; row b has the
  Xilinx JTAG 2x7, MCU UART and SC UART; row c has PMOD A, PMOD B and the two MIPI-10s
  side by side. The 2x20 MCU breakout runs along the DIN.
- mounting: four M3 holes (top and bottom corners of the free area) plus the two VITA
  standoffs, all tied to GND.
- kept-clear routing channels on top: FPGA to SFP (GTP), FPGA to STM32 (FMC),
  FPGA to VITA (LA pairs). FPGA and STM32 decoupling sits on the bottom side.
- power bottom-left, audio in its own bottom-right corner, mirrored L/R.

## routing status

| group | state |
|---|---|
| GTP transceivers: SFP, VITA DP, reference clocks | routed, skew matched |
| DDR3 byte lanes, address/command, CK | next |
| VITA LA pairs and clocks | planned |
| FMC, ULPI, RMII, QSPI | planned |
| low-speed and power | autorouter, then cleanup |

### GTP lanes

Coupled 100 R pairs on F.Cu (microstrip over In1 GND), In2 (stripline between In1 and In3
GND) and B.Cu (microstrip over In6 GND). In5 is not used for transceivers because it
references the split In4 power plane. Lengths run from FPGA ball to connector pad,
including both sides of the AC-coupling capacitor. Skew is total P minus N, matched with
small bumps on the shorter half.

| lane | length mm | P/N skew mm | vias | layers |
|---|---|---|---|---|
| SFP0 TX | 24.4 | 0.02 | 0 | F |
| SFP0 RX | 27.9 | 0.00 | 4 | F, In2 |
| SFP1 TX | 27.2 | 0.00 | 8 | F, In2 |
| SFP1 RX | 31.4 | 0.13 | 8 | F, In2 |
| VITA DP0 C2M | 32.8 | 0.04 | 8 | F, In2 |
| VITA DP1 C2M | 51.2 | 0.07 | 8 | F, In2 |
| VITA DP0 M2C | 34.6 | 0.00 | 4 | F, In2 |
| VITA DP1 M2C | 34.6 | 0.00 | 4 | F, B |
| REFCLK1 (VITA GBTCLK0) | 33.2 | 0.00 | 8 | F, In2, B |
| REFCLK0 (125 MHz osc) | 23.6 | 0.00 | 4 | F, B |

- the DC-blocking caps sit near the receiver: at the connector for FPGA TX, at the FPGA
  for FPGA RX and the reference clocks.
- VITA DP pins sit in rows A and C of the 1.27 mm field. Each pin drops to a via next
  to the pad and the pair couples on In2 or B.Cu under the connector, uncoupled for at
  most about 2.5 mm.
- inside the FPGA ball field the two halves of a pair escape separately (1 mm pitch) and
  couple once they leave the BGA.
