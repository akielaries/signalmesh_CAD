# fab readiness: MAIN_COMPUTE_BOARD

| check | state |
|---|---|
| DRC errors (excluding unconnected) | 0 |
| unconnected (DRC report, capped at 499) | 75 |
| dangling vias / track ends (leftovers to clean before fab) | 6 |
| BOM lines / parts | 137 / 514 |
| parts without an LCSC number | 512 in 136 lines |
| placed parts top / bottom | 365 / 149 |
| copper layers in gerbers | 10 (F.Cu, In1.Cu, In2.Cu, In3.Cu, In4.Cu, In5.Cu, In6.Cu, In7.Cu, In8.Cu, B.Cu) |

Rotations in the CPL are KiCad's; JLCPCB applies per-part corrections for some packages, so check their preview before ordering. Both sides are populated, so assembly is double-sided.

## BOM lines without an LCSC number

| value | footprint | qty | refs |
|---|---|---|---|
| 100nF | C_0402_1005Metric | 79 | C1,C4,C12,C48,C50,C52-C72,C79,C81,C87-C89,C92-C95,C97,C98... |
| 470nF | C_0402_1005Metric | 39 | C126-C133,C135,C136,C141-C145,C152-C155,C158-C161,C164-C1... |
| 4.7uF | C_0603_1608Metric | 29 | C43,C46,C73,C74,C96,C99,C120-C125,C138-C140,C150,C151,C15... |
| 10uF | C_0805_2012Metric | 24 | C39,C47,C49,C75,C109,C147,C191,C192,C220,C221,C232,C233,C... |
| 10k | R_0402_1005Metric | 24 | R1,R22,R35,R37,R40,R43,R44,R48,R50-R53,R61,R72,R78-R80,R8... |
| 39.2 1% | R_0402_1005Metric | 23 | R99-R121 |
| 22uF | C_0805_2012Metric | 18 | C8-C10,C16-C18,C22,C23,C27,C28,C32,C33,C37,C38,C40,C41,C2... |
| 100nF | C_0201_0603Metric | 16 | C199-C210,C212-C215 |
| 100k | R_0402_1005Metric | 15 | R3,R5,R7,R8,R10,R12,R13,R16,R19,R23,R26,R27,R32,R49,R126 |
| 1uF | C_0402_1005Metric | 14 | C3,C11,C42,C44,C45,C78,C80,C101-C103,C107,C115,C117,C241 |
| 4.7k | R_0402_1005Metric | 14 | R66,R67,R69,R70,R82-R86,R89-R93 |
| 1k | R_0402_1005Metric | 12 | R36,R38,R39,R63-R65,R71,R73-R77 |
| 600R@100MHz | L_0603_1608Metric | 8 | FB1-FB8 |
| 100nF 25V | C_0402_1005Metric | 7 | C7,C15,C21,C26,C31,C36,C253 |
| 47uF | C_1206_3216Metric | 7 | C137,C146,C149,C168,C175,C244,C248 |
| 10uF 25V | C_0805_2012Metric | 6 | C20,C25,C30,C35,C51,C252 |
| 0.1uF | C_0402_1005Metric | 5 | C254,C264,C268,C269,C272 |
| GREEN | LED_0603_1608Metric | 5 | D5,D8-D11 |
| 10uF 25V | C_1206_3216Metric | 4 | C5,C6,C13,C14 |
| 3.3nF | C_0402_1005Metric | 4 | C19,C24,C29,C34 |
| 2.2uH 4A | L_APV_ANR4020 | 4 | L3-L6 |
| 49.9 1% | R_0402_1005Metric | 4 | R56-R59 |
| 22 | R_0201_0603Metric | 4 | R129,R130,R132,R138 |
| TP GND | TestPoint_Keystone_5015_Micro_Mini | 4 | TP21-TP24 |
| TPS62130RGT | VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm_ThermalVias | 4 | U4-U7 |
| 2N7002 | SOT-23 | 3 | Q2-Q4 |
| 200k | R_0402_1005Metric | 3 | R15,R18,R21 |
| 249k | R_0402_1005Metric | 3 | R17,R20,R25 |
| 22uF 25V X5R | C_1210_3225Metric | 2 | C2,C300 |
| 2.2uF | C_0603_1608Metric | 2 | C76,C77 |
| 10pF | C_0402_1005Metric | 2 | C83,C84 |
| 8.2pF | C_0402_1005Metric | 2 | C85,C86 |
| 18pF | C_0402_1005Metric | 2 | C90,C91 |
| 15pF | C_0402_1005Metric | 2 | C105,C106 |
| 2.7nF | C_0402_1005Metric | 2 | C261,C271 |
| 47pF | C_0402_1005Metric | 2 | C262,C265 |
| SFP cage | Connector_SFP_and_Cage | 2 | J18,J19 |
| 6.8uH 6A | L_Bourns_SRP6060FA | 2 | L1,L2 |
| 110k | R_0402_1005Metric | 2 | R31,R34 |
| 2.2k | R_0402_1005Metric | 2 | R41,R42 |
| 5.1k | R_0402_1005Metric | 2 | R46,R47 |
| 100 1% | R_0402_1005Metric | 2 | R81,R98 |
| 10k 1% | R_0402_1005Metric | 2 | R122,R123 |
| 1k | R_0201_0603Metric | 2 | R127,R137 |
| 47k | R_0201_0603Metric | 2 | R128,R131 |
| 2k | R_0201_0603Metric | 2 | R133,R140 |
| 560 | R_0201_0603Metric | 2 | R134,R139 |
| 100 | R_0201_0603Metric | 2 | R135,R136 |
| LMR33630ADDA | Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias | 2 | U2,U3 |
| USBLC6-2SC6 | SOT-23-6 | 2 | U14,U16 |
| 10nF | C_0402_1005Metric | 1 | C82 |
| 100uF 10V | CP_Elec_6.3x7.7 | 1 | C104 |
| 470pF | C_0402_1005Metric | 1 | C108 |
| 330uF 2.5V polymer | CP_EIA-7343-31_Kemet-D | 1 | C119 |
| 100uF | C_1210_3225Metric | 1 | C134 |
| 100uF | C_0805_2012Metric | 1 | C267 |
| SMAJ15A | D_SMA | 1 | D1 |
| BZT52C10 | D_SOD-123 | 1 | D2 |
| RED 12V | LED_0603_1608Metric | 1 | D3 |
| GREEN 3V3 | LED_0603_1608Metric | 1 | D4 |
| BLUE | LED_0603_1608Metric | 1 | D6 |
| GREEN DONE | LED_0603_1608Metric | 1 | D7 |
| 3A hold 1812 | Fuse_1812_4532Metric | 1 | F1 |
| 1.1A hold 1206 | Fuse_1206_3216Metric | 1 | F2 |
| 12V IN 5.5x2.1 | BarrelJack_Horizontal | 1 | J1 |
| BOOT0 | PinHeader_1x02_P2.54mm_Vertical | 1 | J2 |
| MCU_SWD MIPI-10 | PinHeader_2x05_P1.27mm_Vertical_SMD | 1 | J3 |
| MCU_SWD | PinHeader_1x06_P2.54mm_Vertical | 1 | J4 |
| MCU_UART FTDI | PinHeader_1x06_P2.54mm_Vertical | 1 | J5 |
| IOX_SPARE | PinHeader_1x06_P2.54mm_Vertical | 1 | J6 |
| MCU_BREAKOUT | PinHeader_2x20_P2.54mm_Vertical | 1 | J7 |
| USB-C HS | USB_C_Receptacle_HRO_TYPE-C-31-M-12 | 1 | J8 |
| USB-A HOST MIDI | USB_A_Molex_67643_Horizontal | 1 | J9 |
| HR911105A | RJ45_Hanrun_HR911105A_Horizontal | 1 | J10 |
| CAN | PinHeader_1x03_P2.54mm_Vertical | 1 | J11 |
| FPGA_JTAG Xilinx | PinHeader_2x07_P2.00mm_Vertical | 1 | J12 |
| FPGA_JTAG 6p | PinHeader_1x06_P2.54mm_Vertical | 1 | J13 |
| SOFTCORE_SWD MIPI-10 | PinHeader_2x05_P1.27mm_Vertical_SMD | 1 | J14 |
| SOFTCORE_UART FTDI | PinHeader_1x06_P2.54mm_Vertical | 1 | J15 |
| PMODA | PinSocket_2x06_P2.54mm_Vertical | 1 | J16 |
| PMODB | PinSocket_2x06_P2.54mm_Vertical | 1 | J17 |
| VITA57.1 HPC ASP-134486-01 | Samtec_FMC_ASP-134486-01_10x40_P1.27mm_Vertical | 1 | J20 |
| DIN41612 C 3x32 BACKPLANE | DIN41612_C_3x32_Male_Horizontal_THT | 1 | J21 |
| ACM_DAC_L | U.FL_Hirose_U.FL-R-SMT-1_Vertical | 1 | J22 |
| DAC_L_PRB | U.FL_Hirose_U.FL-R-SMT-1_Vertical | 1 | J23 |
| ACM_DAC_R | U.FL_Hirose_U.FL-R-SMT-1_Vertical | 1 | J24 |
| 2.2uH 1.5A | L_1008_2520Metric | 1 | L7 |
| DMP3013SFV | Diodes_PowerDI3333-8 | 1 | Q1 |
| 10m 1W | R_Shunt_Vishay_WSK2512_6332Metric_T1.19mm | 1 | R2 |
| 15k | R_0402_1005Metric | 1 | R4 |
| 24.9k | R_0402_1005Metric | 1 | R6 |
| 43.2k | R_0402_1005Metric | 1 | R9 |
| 309k | R_0402_1005Metric | 1 | R11 |
| 49.9k | R_0402_1005Metric | 1 | R14 |
| 280k | R_0402_1005Metric | 1 | R24 |
| 150k | R_0402_1005Metric | 1 | R28 |
| 120k | R_0402_1005Metric | 1 | R29 |
| 90.9k | R_0402_1005Metric | 1 | R30 |
| 130k | R_0402_1005Metric | 1 | R33 |
| 12k 1% | R_0402_1005Metric | 1 | R45 |
| 1.5k | R_0402_1005Metric | 1 | R54 |
| 12.1k 1% | R_0402_1005Metric | 1 | R55 |
| 0 | R_0402_1005Metric | 1 | R60 |
| 120 | R_0402_1005Metric | 1 | R62 |
| 330 | R_0402_1005Metric | 1 | R68 |
| 240 1% | R_0402_1005Metric | 1 | R96 |
| MCU_RESET | SW_SPST_TL3342 | 1 | SW1 |
| MCU_USER | SW_SPST_TL3342 | 1 | SW2 |
| FPGA_PROG | SW_SPST_TL3342 | 1 | SW3 |
| FPGA_BTN0 | SW_SPST_TL3342 | 1 | SW4 |
| FPGA_BTN1 | SW_SPST_TL3342 | 1 | SW5 |
| INA219 0x40 | SOIC-8_3.9x4.9mm_P1.27mm | 1 | U1 |
| TLV62568DBV | SOT-23-5 | 1 | U8 |
| TLV75801 MGTAVCC 1V0 | SOT-23-5 | 1 | U9 |
| TLV75801 MGTAVTT 1V2 | SOT-23-5 | 1 | U10 |
| STM32H755XIH6 | TFBGA-265_14x14mm_Layout17x17_P0.8mm | 1 | U11 |
| TCA9535PWR 0x20 | TSSOP-24_4.4x7.8mm_P0.65mm | 1 | U12 |
| USB3300-EZK | QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm | 1 | U13 |
| TPS2051C | SOT-23-5 | 1 | U15 |
| LAN8742A-CZ | VQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm_ThermalVias | 1 | U17 |
| SN65HVD230 | SOIC-8_3.9x4.9mm_P1.27mm | 1 | U20 |
| MT41K256M16TW-107 | Micron_FBGA-96_8x14mm_Layout9x16_P0.8mm | 1 | U21 |
| TPS51200DRC | VSON-10-1EP_3x3mm_P0.5mm_EP1.65x2.4mm | 1 | U22 |
| LM2662M | SOIC-8_3.9x4.9mm_P1.27mm | 1 | U23 |
| CS4344 | TSSOP-10_3x3mm_P0.5mm | 1 | U24 |
| OPA1656ID | SOIC-8_3.9x4.9mm_P1.27mm | 1 | U25 |
| XC7A100T-2FGG484I | Xilinx_FGG484 | 1 | U100 |
| 24AA025E48 0x54 MAC | SOIC-8_3.9x4.9mm_P1.27mm | 1 | U200 |
| 100MHz 3V3 CMOS | Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm | 1 | X1 |
| 24.576MHz 3V3 CMOS | Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm | 1 | X2 |
| 22.5792MHz 3V3 CMOS | Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm | 1 | X3 |
| 125MHz LVDS | Oscillator_SMD_SiTime_PQFD-6L_3.2x2.5mm | 1 | X4 |
| 25MHz 8pF | Crystal_SMD_3225-4Pin_3.2x2.5mm | 1 | Y1 |
| 32.768kHz 6pF | Crystal_SMD_3215-2Pin_3.2x1.5mm | 1 | Y2 |
| 24MHz 12pF | Crystal_SMD_3225-4Pin_3.2x2.5mm | 1 | Y3 |
| 25MHz 10pF | Crystal_SMD_3225-4Pin_3.2x2.5mm | 1 | Y4 |
