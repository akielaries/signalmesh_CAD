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
| DDR_DQS0 | 22.00 |
| DDR_DQS1 | 25.69 |
| DDR_CK | 22.62 |

## pairs

| net | FPGA ball | DRAM ball | length mm | vias / layers |
|---|---|---|---|---|
| DDR_DQS0_P | Y3 | F3 | 22.00 | 2 / F,In2 |
| DDR_DQS0_N | AA3 | G3 | 22.00 | 2 / F,In2 |
| DDR_DQS1_P | R3 | C7 | 25.69 | 2 / F,In2 |
| DDR_DQS1_N | R2 | B7 | 25.69 | 2 / F,In2 |
| DDR_CK_P | V9 | J7 | 21.73 | 2 / F,In5 |
| DDR_CK_N | V8 | K7 | 23.52 | 2 / F,In5 |

## byte lane 0 (to DQS0)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_DQ0 | AB2 | E3 |  | 21.61 | -0.39 | 2 / B,F | ok |
| DDR_DQ1 | AA4 | F7 |  | 19.47 | -2.53 | 2 / F,In5 | **tune** |
| DDR_DQ2 | AB3 | F2 |  | 22.70 | +0.70 | 2 / F,In5 | ok |
| DDR_DQ3 | AB5 | F8 |  | 19.64 | -2.36 | 2 / B,F | **tune** |
| DDR_DQ4 | AA1 | H3 |  | 22.77 | +0.77 | 2 / F,In2 | ok |
| DDR_DQ5 | Y4 | H8 |  | 21.50 | -0.50 | 2 / B,F | ok |
| DDR_DQ6 | AB1 | G2 |  | 22.00 | -0.00 | 2 / B,F | ok |
| DDR_DQ7 | AA5 | H7 |  | 19.22 | -2.78 | 2 / F,In5 | **tune** |
| DDR_DM0 | V4 | E7 |  | 21.24 | -0.76 | 2 / F,In5 | ok |

## byte lane 1 (to DQS1)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_DQ8 | T1 | D7 |  | 24.83 | -0.86 | 2 / F,In2 | ok |
| DDR_DQ9 | Y1 | C3 |  | 25.45 | -0.25 | 2 / F | ok |
| DDR_DQ10 | U2 | C8 |  | 24.25 | -1.45 | 2 / B,F | **tune** |
| DDR_DQ11 | W1 | C2 |  | 25.69 | -0.00 | 2 / F,In5 | ok |
| DDR_DQ12 | W2 | A7 |  | 25.45 | -0.25 | 2 / B,F | ok |
| DDR_DQ13 | Y2 | A2 |  | 25.88 | +0.18 | 2 / F,In2 | ok |
| DDR_DQ14 | V2 | B8 |  | 25.45 | -0.25 | 2 / F,In5 | ok |
| DDR_DQ15 | U1 | A3 |  | 25.83 | +0.14 | 2 / F,In2 | ok |
| DDR_DM1 | U3 | D3 |  | 26.05 | +0.35 | 2 / F,In2 | ok |

## address / command (to CK)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_A0 | AA6 | N3 | R99 (tail 7.1 mm) | 21.22 | -1.40 | 2 / B,F | ok |
| DDR_A1 | U6 | P7 | R100 (tail 15.3 mm) | 23.76 | +1.14 | 2 / F,In5 | ok |
| DDR_A2 | Y6 | P3 | R101 (tail 5.6 mm) | 22.11 | -0.51 | 2 / F,In2 | ok |
| DDR_A3 | V5 | N2 | R102 (tail 13.5 mm) |  |  |  | **open** |
| DDR_A4 | T5 | P8 | R103 (tail 16.6 mm) | 22.39 | -0.23 | 2 / F,In2 | ok |
| DDR_A5 | W5 | P2 | R104 (tail 9.7 mm) | 28.80 | +6.18 | 2 / F,In2 | **tune** |
| DDR_A6 | T6 | R8 | R105 (tail 10.0 mm) | 22.62 | +0.00 | 2 / F,In2 | ok |
| DDR_A7 | W6 | R2 | R106 (tail 8.8 mm) | 28.34 | +5.72 | 2 / B,F | **tune** |
| DDR_A8 | R6 | T8 | R107 (tail 9.6 mm) | 24.41 | +1.79 | 2 / F,In5 | ok |
| DDR_A9 | U5 | R3 | R108 (tail 4.7 mm) |  |  |  | **open** |
| DDR_A10 | Y9 | L7 | R109 (tail 11.7 mm) | 19.86 | -2.77 | 2 / F,In5 | ok |
| DDR_A11 | V7 | R7 | R110 (tail 18.5 mm) | 20.17 | -2.45 | 2 / B,F | ok |
| DDR_A12 | T4 | N7 | R111 (tail **open**) |  |  |  | **open** |
| DDR_A13 | W7 | T3 | R112 (tail 4.4 mm) | 22.23 | -0.39 | 2 / F,In2 | ok |
| DDR_A14 | W9 | T7 | R113 (tail 13.2 mm) |  |  |  | **open** |
| DDR_BA0 | Y7 | M2 | R114 (tail **open**) | 24.10 | +1.48 | 2 / F,In2 | ok |
| DDR_BA1 | R4 | N8 | R115 (tail 11.5 mm) | 23.58 | +0.96 | 2 / B,F | ok |
| DDR_BA2 | Y8 | M3 | R116 (tail 8.5 mm) | 24.59 | +1.97 | 2 / B,F | ok |
| DDR_RAS_N | AB8 | J3 | R117 (tail 9.9 mm) |  |  |  | **open** |
| DDR_CAS_N | AB7 | K3 | R118 (tail 9.5 mm) | 22.62 | +0.00 | 2 / B,F | ok |
| DDR_WE_N | AB6 | L3 | R119 (tail 18.6 mm) | 21.72 | -0.91 | 2 / F,In2 | ok |
| DDR_CKE | AA8 | K9 | R120 (tail **open**) | 18.64 | -3.98 | 2 / F | **tune** |
| DDR_ODT | T3 | K1 | R121 (tail **open**) |  |  |  | **open** |

## reset (not matched)

| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |
|---|---|---|---|---|---|---|---|
| DDR_RESET_N | U7 | T2 |  | 29.13 |  | 2 / F,In2 | routed |

`open` = no copper path between the two balls yet (end vias and dogbones are in place). `tune` =
routed, but outside its window: positive is too long (re-route shorter), negative is too short (add
a serpentine). Command nets also need their tail from the DRAM ball via to the listed terminator.
