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
- mounting: four M3 holes near the card corners (front-panel side and DIN side) plus the two
  VITA standoffs, all tied to GND.
- QSPI flashes (2x W25Q01JVZEIQ, WSON-8) sit on the bottom side inside the STM32 outline,
  between its QUADSPI pins.
- kept-clear routing channels on top: FPGA to SFP (GTP), FPGA to STM32 (FMC),
  FPGA to VITA (LA pairs). FPGA and STM32 decoupling sits on the bottom side.
- power bottom-left, audio in its own bottom-right corner, mirrored L/R.

## routing status

| group | state |
|---|---|
| GTP transceivers: SFP, VITA DP, reference clocks | routed, skew matched |
| DDR3 byte lanes, address/command, CK | mostly routed, finishing by hand: see [DDR3 routing](ddr_routing.md) |
| VITA LA pairs and clocks | 10 of 36 pairs routed; the rest by hand (2.8 mm gap between the connector and the FPGA's top banks) |
| FMC and FPGA config | 49 of 73 nets routed after the pin swap; the rest by hand |
| QSPI | 4 of 10 routed (BK1_IO2/IO3, BK2_IO0/IO1); CLK, NCS, BK1_IO0/IO1, BK2_IO2/IO3 by hand |
| ULPI | USB3300 moved beside the STM32 (bottom, below it): D0, D1, D3 routed at 9-17 mm; CK, D2, D4-D7, DIR, NXT, STP, RST by hand (all short now); USB HS pair routed on In2, 116 mm |
| RMII and MDIO | LAN8742 moved beside the STM32 (bottom, under its upper right): REF_CLK 35 mm, TX_EN 22 mm, MDC 33 mm routed; CRS_DV, RXD0, RXD1, TXD0, TXD1, MDIO, NRST by hand (all short now); both MDI pairs to the RJ45 (about 105 mm, 100 R) by hand |
| low-speed and power | autorouter, then cleanup |

### PHY placement

The USB3300 and LAN8742 groups (PHY, crystal, decaps, straps, terminations) sit on the bottom side
beside the STM32, so ULPI and RMII are 10-35 mm. The long runs are differential instead: the USB HS
pair (90 R) to the USB-C and the two Ethernet MDI pairs (100 R) to the RJ45, about 105-115 mm. That
is fine for USB HS; for 100BASE-TX it is longer than the ideal (PHY within about 25 mm of the
magnetics) but works. The ESD part (U14), VBUS cap (C102) and the magnetics centre tap parts
(R60, C113) stay at their connectors.

### 12 V distribution

The input path is J1, F1, D1 (TVS), Q1 (reverse-polarity FET), then the 10 mOhm Kelvin shunt R2 (on
the bottom under Q1 and the INA219), after which the net is +12V. +12V is a B.Cu pour limited to a top
strip (y 53.6 to 60.5, wider round U4), a strip down the front side (x 76 to 82) and the bottom-left
power box (x 75 to 90, y 112 to 146), about 1460 mm2 instead of the whole layer. The rest of B.Cu is
free for signals. Loads off the pour (F2 mezzanine fuse, R35, TP2) have their own trace to a via in it.
R2's pin-out was corrected (1 and 4 force, 2 and 3 sense); before that the shunt was bypassed and the
INA219 read zero.

### GTP lanes

Coupled 100 R pairs on F.Cu (microstrip over In1 GND), In2 (stripline between In1 and In3
GND) and B.Cu (microstrip over In6 GND). In5 is not used for transceivers because it
references the split In4 power plane. Lengths run from FPGA ball to connector pad,
including both sides of the AC-coupling capacitor. Skew is total P minus N, matched with
small bumps on the shorter half. REFCLK1 is left at 1 mm (about 7 ps): there is no room
for bumps on that route, and the offset is negligible for a reference clock.

| lane | length mm | P/N skew mm | vias | layers |
|---|---|---|---|---|
| SFP0 TX | 24.4 | 0.02 | 0 | F |
| SFP0 RX | 27.9 | 0.00 | 4 | F, In2 |
| SFP1 TX | 27.2 | 0.00 | 8 | F, In2 |
| SFP1 RX | 31.4 | 0.13 | 8 | F, In2 |
| VITA DP0 C2M | 27.4 | 0.08 | 8 | F, In2 |
| VITA DP1 C2M | 47.5 | 0.06 | 8 | F, In2 |
| VITA DP0 M2C | 26.3 | 0.00 | 4 | F, In2 |
| VITA DP1 M2C | 25.8 | 0.00 | 4 | F, B |
| REFCLK1 (VITA GBTCLK0) | 28.9 | 1.00 | 8 | F, In2, B |
| REFCLK0 (125 MHz osc) | 23.6 | 0.00 | 4 | F, B |

- the DC-blocking caps sit near the receiver: at the connector for FPGA TX, at the FPGA
  for FPGA RX and the reference clocks.
- VITA DP pins sit in rows A and C of the 1.27 mm field. Each pin drops to a via next
  to the pad and the pair couples on In2 or B.Cu under the connector, uncoupled for at
  most about 2.5 mm.
- inside the FPGA ball field the two halves of a pair escape separately (1 mm pitch) and
  couple once they leave the BGA.
