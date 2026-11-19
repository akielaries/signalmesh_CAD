# DDR3 routing: status and finishing guide

Generated from the board by `gen/ddrdoc.py`. Lengths are copper from the FPGA ball to the DRAM ball,
including both dogbones; the fly-by tail to each command terminator is not counted.

## rules

| item | rule |
|---|---|
| byte lane 0 | DQ0-7 and DM0 matched to the DQS0 pair, +/-1.4 mm (+/-10 ps) |
| byte lane 1 | DQ8-15 and DM1 matched to the DQS1 pair, +/-1.4 mm |
| address/command | A0-14, BA0-2, RAS_N, CAS_N, WE_N, CKE, ODT matched to the CK pair, +/-3 mm (+/-20 ps) |
| pairs | DQS0, DQS1, CK: P to N within 0.15 mm, coupled outside the ball fields (DIFF100). CK is currently 1.8 mm apart (21.73 / 23.52): add a skew bump on CK_P |
| not matched | RESET_N; the tails from DRAM ball to the 39.2 R terminators; lane-to-lane; CK to DQS (write leveling absorbs it, keep CK equal or longer if you can) |
| topology | command nets are fly-by: FPGA, then the DRAM ball, then the terminator. Take the tail from the DRAM ball via, never stub off the main run. Tail length is not matched; under about 20 mm is fine since the terminator ends the line |
| vias | 2 per net: the FPGA dogbone and the DRAM dogbone (3 at most, if a net has to change layer once). The command tail adds one more at the terminator. Keep the via count equal within a byte lane; a pair's two halves always get the same vias |
| layers | In2 (between GND planes) is preferred for data, In5 (between the 1V35 plane and GND) for command. B.Cu and F.Cu are allowed. Keep a byte lane on one layer where possible: outer-layer microstrip is about 15 percent faster per mm than stripline, so a mixed lane needs matching in ps, not mm |
| widths | In2/In5: 0.23 mm (50 ohm). F.Cu/B.Cu: 0.127 mm. Pairs inner: 0.115 mm with a 0.10 mm gap; outer: 0.10 / 0.18. Neck to 0.10 mm only inside the FPGA and DRAM ball fields (DRC rule "BGA escape") |
| spacing | 0.15 mm DDR class clearance minimum; 3x the trace width (about 0.7 mm inner) between different nets on long parallel runs and between serpentine loops |
| tuning | KiCad length tuner (single track: 7, diff pair: 8). Amplitude up to about 1 mm, spacing 3w, put meanders outside the ball fields. For ps accuracy, add the FPGA package delays (xc7a100tfgg484 package file) when available |
| don't cut | the In5 +1V0 feed pour (left of and above the DDR escape) and the VTT strip/pour around the terminators |

## references

| pair | length mm |
|---|---|
| DDR_DQS0 | open |
| DDR_DQS1 | 26.44 |
| DDR_CK | 26.15 |

## pairs

| net | FPGA ball | DRAM ball | length mm | vias / layers |
|---|---|---|---|---|
| DDR_DQS0_P | Y3 | F3 | **open** |  |
| DDR_DQS0_N | AA3 | G3 | 22.71 | 2 / F,In2 |
| DDR_DQS1_P | R3 | C7 | 26.73 | 1 / F,In2 |
| DDR_DQS1_N | R2 | B7 | 26.14 | 2 / F,In2 |
| DDR_CK_P | V9 | J7 | 26.33 | 2 / F,In5 |
| DDR_CK_N | V8 | K7 | 25.96 | 1 / F,In5 |

## byte lane 0 (to DQS0)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_DQ0 | AB2 | E3 |  | 31.88 |  | 2 / F,In2 | **tune** |
| DDR_DQ1 | AA4 | F7 |  | 23.33 |  | 2 / F,In5 | **tune** |
| DDR_DQ2 | AB3 | F2 |  | 21.30 |  | 1 / F,In5 | **tune** |
| DDR_DQ3 | AB5 | F8 |  | 18.20 |  | 1 / B,F | **tune** |
| DDR_DQ4 | AB1 | H3 |  | 21.93 |  | 2 / B,F | **tune** |
| DDR_DQ5 | Y4 | H8 |  | 18.89 |  | 2 / B,F | **tune** |
| DDR_DQ6 | AA1 | G2 |  | 24.46 |  | 2 / F,In2 | **tune** |
| DDR_DQ7 | AA5 | H7 |  | 19.34 |  | 2 / B,F | **tune** |
| DDR_DM0 | V4 | E7 |  | 23.13 |  | 2 / F,In5 | **tune** |

## byte lane 1 (to DQS1)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_DQ8 | T1 | D7 |  | 27.05 | +0.62 | 2 / F,In2 | ok |
| DDR_DQ9 | Y1 | C3 |  | 22.64 | -3.80 | 1 / F,In2 | **tune** |
| DDR_DQ10 | U2 | C8 |  | 22.43 | -4.01 | 2 / F,In5 | **tune** |
| DDR_DQ11 | W1 | C2 |  | 25.89 | -0.55 | 2 / B,F | ok |
| DDR_DQ12 | W2 | A7 |  | 30.40 | +3.96 | 2 / B,F | **tune** |
| DDR_DQ13 | Y2 | A2 |  | 24.32 | -2.12 | 1 / F,In5 | **tune** |
| DDR_DQ14 | V2 | B8 |  | 24.10 | -2.34 | 1 / B,F | **tune** |
| DDR_DQ15 | U1 | A3 |  | 27.75 | +1.31 | 2 / F,In5 | ok |
| DDR_DM1 | U3 | D3 |  | 35.35 | +8.92 | 2 / F,In5 | **tune** |

## address / command (to CK)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_A0 | Y9 | N3 | R99 (tail 13.4 mm) | 24.93 | -1.21 | 2 / F,In2 | ok |
| DDR_A1 | V5 | P7 | R100 (tail 18.6 mm) | 23.20 | -2.95 | 1 / F,In2 | ok |
| DDR_A2 | Y6 | P3 | R101 (tail 11.7 mm) | 24.28 | -1.86 | 1 / B,F | ok |
| DDR_A3 | W6 | N2 | R102 (tail 19.6 mm) | 32.92 | +6.77 | 2 / F,In5 | **tune** |
| DDR_A4 | T6 | P8 | R103 (tail **open**) | 26.24 | +0.10 | 2 / F,In5 | ok |
| DDR_A5 | AA6 | P2 | R104 (tail 15.0 mm) | 22.78 | -3.37 | 1 / B,F | **tune** |
| DDR_A6 | R4 | R8 | R105 (tail 13.7 mm) | 29.72 | +3.58 | 2 / F,In5 | **tune** |
| DDR_A7 | V7 | R2 | R106 (tail 14.7 mm) | 27.87 | +1.72 | 1 / B,F | ok |
| DDR_A8 | U6 | T8 | R107 (tail **open**) |  |  |  | **open** |
| DDR_A9 | W7 | R3 | R108 (tail 9.9 mm) | 36.18 | +10.03 | 2 / F,In2 | **tune** |
| DDR_A10 | W9 | L7 | R109 (tail 17.5 mm) | 25.88 | -0.27 | 1 / B,F | ok |
| DDR_A11 | U5 | R7 | R110 (tail **open**) |  |  |  | **open** |
| DDR_A12 | T5 | N7 | R111 (tail 28.9 mm) | 25.56 | -0.58 | 2 / F,In2 | ok |
| DDR_A13 | AB6 | T3 | R112 (tail 11.1 mm) | 22.75 | -3.40 | 2 / F | **tune** |
| DDR_A14 | W5 | T7 | R113 (tail 15.4 mm) | 22.78 | -3.37 | 2 / B,F | **tune** |
| DDR_BA0 | Y7 | M2 | R114 (tail 20.4 mm) |  |  |  | **open** |
| DDR_BA1 | T4 | N8 | R115 (tail 15.3 mm) | 23.85 | -2.30 | 2 / F,In2 | ok |
| DDR_BA2 | Y8 | M3 | R116 (tail **open**) | 25.52 | -0.62 | 2 / F,In2 | ok |
| DDR_RAS_N | AB7 | J3 | R117 (tail **open**) | 21.92 | -4.22 | 2 / B,F | **tune** |
| DDR_CAS_N | AA8 | K3 | R118 (tail **open**) |  |  |  | **open** |
| DDR_WE_N | AB8 | L3 | R119 (tail 22.7 mm) |  |  |  | **open** |
| DDR_CKE | R6 | K9 | R120 (tail **open**) | 31.65 | +5.50 | 2 / F | **tune** |
| DDR_ODT | T3 | K1 | R121 (tail **open**) | 39.67 | +13.52 | 1 / B,F | **tune** |

## reset (not matched)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_RESET_N | U7 | T2 |  |  |  |  | **open** |

`open` = no copper path between the two balls yet (end vias and dogbones are in place). `tune` =
routed, but outside its window: positive is too long (re-route shorter), negative is too short (add
a serpentine). Command nets also need their tail from the DRAM ball via to the listed terminator.
