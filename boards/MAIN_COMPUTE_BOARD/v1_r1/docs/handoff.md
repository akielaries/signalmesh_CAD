# Layout handoff: MAIN_COMPUTE_BOARD v1_r1

Where the automated layout stopped and what is left to finish by hand in KiCad.

## State

| check | value |
|---|---|
| unconnected items (KiCad DRC) | 45 (in 35 nets) |
| DRC rule errors | 0 |
| schematic parity | clean, 0 footprint errors |
| layers | 10 (F / GND / sig / GND / PWR / sig / GND / sig / GND / B), stackup in [pcb.md](pcb.md) |
| last good board | `checkpoints/board_45.kicad_pcb` (identical to the working board) |

Earlier checkpoints, newest first: `board_49` (48 unconnected), `board_50`, `localrip_51`, `localrip_53`, `irqtrim`, `j7trim`,
`final_ddr8`. Each one passed DRC with 0 errors when it was saved.

No automated run is active and no sleep inhibitor is held; the board is yours. Open the project
(`MAIN_COMPUTE_BOARD.kicad_pro`), not the bare `.kicad_pcb`: saving a bare board wipes the net classes.
If you start one of the gen/ scripts, run only one at a time and stop it by pid, never with `pkill -f`.

## Design changes made during layout

| change | why | follow-up |
|---|---|---|
| J7 breakout trimmed to 6 GPIO (PC10-PC12, PE2, PE5, PE6) plus FDCAN1, I2C1, NRST; 18 pins NC | freed the STM32 ball field (978 mm of track) | [hardware.md](hardware.md) J7 table updated |
| FPGA IRQs cut from 6 to 2 (IRQ0 PG7 / AB20, IRQ1 PG8 / V19) | freed 4 STM32 and 4 FPGA balls | gateware ORs its sources onto the two lines; cause register over FMC ([bringup.md](bringup.md)) |
| FPGA_DONE moved PK1 -> PJ4 | west-side ball | firmware pin change |
| DDR flight paths re-routed | 12 -> 8 nets out of window | see length matching below |
| C132, C68 moved 4-5 mm | no via spot at the old place | slightly weaker decoupling for those two |
| +12V F.Cu patch at U4 pin 7 removed | it joined nothing after the U4 re-route | +12V reaches U4 on 0.3 mm tracks |

The generators (`gen/dstm32.py`, `gen/dfpga.py`) carry the J7 and IRQ changes, so a schematic rebuild
keeps them.

## Open items (45)

Coordinates are board mm. U11 is the STM32 (158, 99), U100 the FPGA, U13 the USB PHY (bottom),
J20 the VITA connector, J18/J19 the SFP cages.

### FMC (6)

| net | from | to | note |
|---|---|---|---|
| FMC_NBL0 | U11 C4 (162.8, 95.0) | U100 T19 (129.5, 96.5) | east-edge STM32 ball, faces away from the FPGA |
| FMC_NBL1 | U11 B4 (163.6, 95.0) | U100 P20 (130.5, 94.5) | same |
| FMC_NBL3 | U11 A3 (164.4, 94.2) | U100 N15 (125.5, 93.5) | same |
| FMC_NOE | U11 A12 (164.4, 101.4) | U100 Y21 (131.5, 100.5) | same, south half |
| FMC_A17 | U11 R16 (153.2, 104.6) | U100 G16 (126.5, 87.5) | |
| FMC_D13 | U11 U16 (151.6, 104.6) | U100 Y22 (132.5, 100.5) | dogbone exists at the STM32 end |

The east-edge four have to wrap round the north or south side of the STM32 on In2 or In7. The FPGA
ends sit on flexible bank 14/15 IO, so their balls can be swapped (update `gen/dfpga.py` and the xdc to
match).

### ULPI (6)

ULPI_CK, D0, D3, D4, D5, NXT: STM32 north-west balls (x 151.6-154, y 93-103) to U13 on the bottom
(x 154-158, y 117-122). Run them down the west side of the STM32 on In5/In7 and drop to B.Cu at U13.
Keep them about the same length (60 MHz, not critical).

### VITA LA halves (6)

MEZZ_LA09_P, LA25_P, LA29_P, LA29_N, LA31_P, LA32_N: single halves from the FPGA's top rows
(y 81.5-88.5) to J20 (y 67-73). The other half of each pair is routed. Route next to its partner and
match P/N afterwards. LA29 is open on both halves.

### SFP sideband (6)

SFP0_SCL, SFP0_TX_DIS, SFP1_LOS, SFP1_SDA, SFP1_TX_DIS, SFP1_TX_FAULT: low-speed. The cage ends are
already routed most of the way (tracks end near x 87). What is missing is the escape out of the FPGA's
bank 13 balls (x 121-126, y 96-100) and the run west to those track ends.

### FPGA control and misc (7)

| net | gap |
|---|---|
| FPGA_DONE | U100 G11 (121.5, 87.5) to U11 U7 (151.6, 97.4), and G11 to the TP26/R68 track end (122.7, 76.8) |
| FPGA_M1 | R64 (115.5, 76.0) to U100 U10 (120.5, 97.5) |
| FPGA_RDWR_B | U100 AA19 (129.5, 101.5) to a track end at (149.5, 103.0) |
| QSPI_CLK | U11 L3 (156.4, 94.2) to U18 pin 6 (163.8, 111.2) |
| QSPI_NCS | two track ends 4.4 mm apart at (159.9, 109.0) and (159.6, 104.6), B.Cu |
| GTP_RREF | FPGA ball fanout (118.5, 86.5) to R81 (82.2, 114.5) (low-speed reference resistor) |
| ETH_AVDD | track end (166.9, 86.7) to R60 (74.0, 107.7) (consider a closer local filter instead) |

### Power and GND (13)

| net | gap | suggested fix |
|---|---|---|
| +1V0 | C122 pad 1 (117.0, 86.0) to C128 pad 1 (116.5, 84.2) and to a track end (115.0, 86.5); C130 pad 1 (118.8, 94.0) | decaps under the FPGA with no via spot nearby; move the cap or hand-place a via |
| +1V8 | C144 pad 1 (122.8, 84.0) to FB5 (118.2, 76.0) and to a track end (124.6, 87.9) | C144's pad is a junction on the +1V8 feed: restore the link FB5 to the FPGA |
| +3V3 | In5 track (118.2, 75.3) and via (124.0, 89.0) to the F.Cu stub at (122.5, 86.5); B.Cu track ends (159.9, 79.5) and (158.4, 77.7) near C160 | short stubs to the In4 plane |
| +1V35 | track end (93.5, 129.2) to U22 pin 2 (96.0, 127.5) | DDR supply at the VTT regulator |
| VTT_DDR | zones VTT_BOT (B.Cu) and VTT_STRIP (F.Cu) at (95.4, 126.4) | one stitching via where they overlap |
| GND | C145 pad 2 (126.2, 84.8), C142 pad 2 (124.0, 93.0), track end (113.8, 89.5) | GND stitching vias (all under the FPGA) |

## Length matching (do after routing is complete)

- **DDR3:** 8 nets outside their window: ODT, DQ0, A9, DM1, A3 and CKE too long; DQ3 and A14 too short.
  DQS0 P/N skew is 1.3 mm and CK P/N is 1.8 mm. Details and targets in [ddr_routing.md](ddr_routing.md).
  `gen/ddr_tune.py <board>` adds meanders where there is room, and `gen/ddrfix.py <board>` re-routes the
  flight path of an out-of-window net. Both report what they changed.
- **VITA LA:** 14 of 36 pairs are within 0.25 mm P/N; the rest are up to 18 mm apart.
  `gen/skewtune.py <board> U100 J20 '^MEZZ_LA'` adds skew bumps.

## Before fab

1. 0 unconnected, 0 DRC errors, schematic parity clean.
2. Clean up 7 dangling vias / track ends (`gen/cleanup.py <board>` removes them, but it keeps BGA
   dogbones on purpose).
3. Silkscreen: 54 items (references over pads or the board edge); `gen/silkfix.py <board>` moves or hides them.
4. LCSC numbers: 512 parts in 136 BOM lines have none. See [fab/READINESS.md](../fab/READINESS.md).
5. Confirm the 10-layer stackup and impedance widths with JLCPCB (SE50 0.127 mm, DIFF100 inner
   0.09 / 0.125 gap, USB90 inner 0.11).
6. Double-sided assembly; check JLCPCB's CPL rotation preview.
7. `python3 gen/fab.py MAIN_COMPUTE_BOARD.kicad_pcb MAIN_COMPUTE_BOARD.kicad_sch fab` regenerates the
   gerbers, drill, BOM, CPL and READINESS.md.

## Tools in gen/ (run with the KiCad Python, e.g. `~/.venvs/mcb/bin/python`)

All of them edit the board in place. Run one at a time, on a copy first, and check DRC afterwards.

| script | does |
|---|---|
| `routeguide.py <board> docs/routing_guide.md` | lists every open net with its pads |
| `drcpairs.py <board> [net regex]` | routes the missing connections KiCad DRC reports |
| `localfix.py <board>` | routes short missing connections one at a time, narrowing the track as needed |
| `localrip.py <board>` | rips the copper round a blocked short hop, routes it, reconnects the rest, keeps only if DRC improves |
| `pinfree.py <board> NET...` | rip-up and retry round blocked pins, judged by DRC |
| `planestitch.py <board> --all` | stitches plane-net pads to their planes |
| `decapmove.py <board> REF...` | moves decaps to the nearest spot where both pads can be stitched |
| `viamerge.py`, `cleanup.py` | merge stacked same-net vias; remove dangling copper |
| `ddr_tune.py`, `ddrfix.py`, `ddrdoc.py` | DDR length tuning and the DDR report |
| `skewtune.py` | P/N skew bumps for pairs |
| `fab.py` | fab outputs and readiness report |

Pitfalls: keep removed SWIG items referenced until the board is saved (otherwise pcbnew crashes), loop by
index over SWIG containers, and in zsh split a net list with `${=NETS}`.
