# PCB

## stackup: 10 layers, 1.6 mm (1 oz outer, 0.5 oz inner)

JLCPCB does not publish its 10-layer impedance stackups on the impedance page, so this is a typical
balanced build from their materials (core er 4.6, 7628 er 4.4, 1080 er 3.91). Before ordering, pick the
closest JLCPCB 10-layer stackup in the order flow and re-check the widths below.

| layer | role | dielectric below |
|---|---|---|
| F.Cu | signal (outer) | 1080 prepreg 0.0764 mm |
| In1 | GND | core 0.15 mm |
| In2 | signal, main high-speed inner layer | 7628 prepreg 0.2104 mm |
| In3 | GND | core 0.15 mm |
| In4 | power planes, split by rail | 7628 prepreg 0.2104 mm |
| In5 | signal (In4 power plane above, In6 GND below) | core 0.15 mm |
| In6 | GND | 7628 prepreg 0.2104 mm |
| In7 | signal | core 0.15 mm |
| In8 | GND | 1080 prepreg 0.0764 mm |
| B.Cu | signal (outer) | |

All three inner signal layers sit between a 0.15 mm core and a 0.2104 mm prepreg, so they share widths.

## impedance

Widths come from a 2D finite-difference field solve of these cross sections, calibrated against
Cohn's exact stripline result.

| class | outer (F/B) | inner (In2/In5/In7) | nets |
|---|---|---|---|
| SE50 | 0.127 mm | 0.127 mm | FMC, ULPI, RMII, QSPI, clocks, I2S |
| DDR | 0.127 mm | 0.127 mm | DDR DQ/DM/addr/cmd |
| DIFF100 | 0.10 / 0.18 gap | 0.09 / 0.125 gap | VITA LA, GTP, SFP, DDR CK/DQS |
| USB90 | 0.11 / 0.127 gap | 0.11 / 0.106 gap | USB HS and FS |
| PWR | 0.4 mm min | 0.4 mm min | rails |

The inner pair geometry keeps the 0.215 mm pitch the 8-layer routing used, so existing pairs were
narrowed in place (0.115 to 0.09) with no re-routing. New inner pairs can also use 0.10 / 0.15 gap.

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

## routing status (2026-11-22)

DRC with schematic parity: no clearance, short or width errors; 75 unconnected items (the open nets with
their terminals are in the [routing guide](routing_guide.md)). Silkscreen: references moved off pads or
hidden on dense passives (hidden ones stay on the fab layer); 47 silk items left, mostly footprint
outlines over pads (clipped by the mask in the gerbers) and 6 at the board edge.

| group | state |
|---|---|
| GTP transceivers: SFP, VITA DP, reference clocks | routed, skew matched (table below) |
| DDR3 | all nets connected; 8 nets outside their length window (ODT, DQ0, A9, DM1, A3, CKE long; DQ3, A14 short) and DQS0 P/N skew 1.3 mm: see [DDR3 routing](ddr_routing.md) |
| VITA LA pairs and clocks | 30 of 36 pairs complete; 6 halves open (LA09_P, LA25_P, LA29_P/N, LA31_P, LA32_N) at the FPGA's top rows. Most pairs are routed as loosely coupled halves (0.1 mm each, about 108 R differential), 4 as coupled pairs. P/N skew: 14 pairs within 0.25 mm, the rest up to 18 mm (no room for meanders) |
| STM32 (FMC, config, ULPI, QSPI, misc) | 154 nets, about 25 open: FMC_NBL0-3, NOE, NWE (east edge of the BGA, facing away from the FPGA), FMC_A17/D2/D13, FPGA_DONE/IRQ2/IRQ5/RDWR_B, ULPI (8), QSPI_CLK/NCS/BK1_IO3, BOOT0 (J7 breakout trimmed to 6 GPIOs to free the STM32 ball field) |
| Ethernet | RMII and MDIO routed; MDI TXP/TXN/RXP routed (about 105 mm), RXN open |
| low-speed | SFP sideband (6), BP_TDM_DIN, FPGA_M1, GTP_RREF open; the rest routed |
| power | planes stitched; open: a few FPGA decaps and supply balls, +1V8 branch, buck control nets (EN_12V, SS_3V3M, SS_VADJ), VCCADC, VTT_DDR |

How the board got here, for whoever finishes it:

- the STM32 is a TFBGA265 (0.8 mm) with a full dogbone fanout. Rule areas STM32_ESC (3 mm round its
  courtyard) and FPGA_ESC (east and south strips of the FPGA) allow 0.09 mm width and clearance so
  tracks can neck down until they leave the ball fields.
- parts were moved out of the STM32-FPGA corridor (decaps, config pull-ups, crystals), so most STM32
  decaps now sit 8-12 mm north of the BGA on the bottom side. Worth pulling back closer if room appears.
- inner plane zones use 0.15 mm clearance and 0.1 mm minimum width (was 0.2 / 0.2): at 0.2 the
  planes could not fill between the vias under the FPGA and the supply balls there were isolated.
- FPGA_DONE moved to a west-side ball (PK1 -> PJ4, firmware pin change). FPGA IRQs cut from six to two
  (IRQ0 PG7, IRQ1 PG8) and the J7 breakout trimmed to six GPIOs, both to free the STM32 ball field.
- what blocks the open STM32 nets is the ball fields themselves: their balls have no free dogbone cell
  left near them, on the STM32 or at the FPGA end. Freeing them means moving several neighbouring
  vias at once (push-and-shove).

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
