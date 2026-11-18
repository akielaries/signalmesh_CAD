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
