# hardware reference

Everything a user of this open board needs to plug in, debug and bring up. Positions
are measured from the front-top corner of the card (front panel on the left, card guides
along the top and bottom edges). Generated from the board file.

## front panel (top to bottom)

| connector | ref | function |
|---|---|---|
| 5.5 x 2.1 mm barrel jack | J1 | 12 V in, centre positive. Same net as DIN a1-c2, use one source |
| SFP cage | J18 | GTP lane 0, up to 6.25 Gb/s (1G/2.5G SFP, direct-attach cables) |
| SFP cage | J19 | GTP lane 1 |
| RJ45 with magnetics | J10 | 10/100 Ethernet, LAN8742A RMII to the STM32 |
| USB-A host | J9 | STM32 OTG_FS host, 5 V 0.5 A switched VBUS (USB-MIDI keyboards, storage) |
| USB-C | J8 | STM32 OTG_HS device through USB3300 ULPI PHY, 480 Mb/s (updates, UAC2, console) |

## rear

| connector | ref | function |
|---|---|---|
| DIN 41612 type C 3x32 male, right angle | J21 | backplane: power, TDM audio bus, CAN-FD. See [pinout](pinout.md) |
| VITA 57.1 HPC carrier (Samtec ASP-134486-01) | J20 | mezzanine site, top side. LPC cards fit |

## debug and programming

| header | ref | use |
|---|---|---|
| MIPI-10 1.27 mm | J3 | STM32 SWD + SWO + reset (Black Magic Probe, ST-LINK, J-Link) |
| 1x6 2.54 mm | J4 | STM32 SWD on dupont wires |
| 1x6 2.54 mm FTDI order | J5 | STM32 console UART (USART1) |
| 1x2 2.54 mm | J2 | BOOT0: jumper to boot the ST system bootloader (USB DFU) |
| 2x7 2.0 mm | J12 | FPGA JTAG, Xilinx platform cable pinout |
| 1x6 2.54 mm | J13 | FPGA JTAG, Digilent HS2 order |
| MIPI-10 1.27 mm | J14 | soft-core SWD on FPGA user IO (bank 15) |
| 1x6 2.54 mm FTDI order | J15 | soft-core console UART on FPGA user IO |

All headers are 3.3 V. Pin 1 of the FTDI-order headers is GND; a 3.3 V FTDI cable plugs
in with its black wire on pin 1. VCC (pin 3) is not connected so the cable cannot back-power
the board.

## buttons and LEDs

| ref | name | function |
|---|---|---|
| D3 | RED 12V | 12 V present |
| D4 | GREEN 3V3 | 3.3 V rail up |
| D5 | GREEN | user LED, driven by MCU_LED0 |
| D6 | BLUE | user LED, driven by MCU_LED1 |
| D7 | GREEN DONE | FPGA configured (DONE high) |
| D8 | GREEN | user LED, driven by FPGA_LED0 |
| D9 | GREEN | user LED, driven by FPGA_LED1 |
| D10 | GREEN | user LED, driven by FPGA_LED2 |
| D11 | GREEN | user LED, driven by FPGA_LED3 |
| SW1 | MCU_RESET | STM32 reset (NRST) |
| SW2 | MCU_USER | STM32 user button, PC13, active high |
| SW3 | FPGA_PROG | pulls PROGRAM_B low: FPGA clears and waits to be reconfigured |
| SW4 | FPGA_BTN0 | FPGA user input, active high |
| SW5 | FPGA_BTN1 | FPGA user input, active high |

## expansion headers

| header | ref | use |
|---|---|---|
| Pmod 2x6 socket | J16 | FPGA bank 13, Digilent 12-pin, 3.3 V |
| Pmod 2x6 socket | J17 | FPGA bank 13 |
| 2x20 2.54 mm | J7 | STM32 breakout: 6 GPIO (PC10-PC12, PE2, PE5, PE6), I2C1, FDCAN1, NRST, 3V3, 5V; other signal pins NC (trimmed for layout) |
| 1x6 2.54 mm | J6 | TCA9535 spare GPIO P14-P17 |
| 1x3 2.54 mm | J11 | CAN-FD bus (also on the DIN). Solder jumper JP1 adds 120 R termination |

## audio and analog

| connector | ref | signal |
|---|---|---|
| u.fl | J22 | FPGA audio left: CS4344, OPA1656 buffer (gain 1.5), 10 uF + 100 R out |
| u.fl | J24 | FPGA audio right |
| u.fl | J23 | STM32 DAC1 channel 1 (PA4), unbuffered |

## test points

Rails, power-goods and the FPGA/STM32 status lines are 1.5 mm pads on the bottom side,
each placed under the part that sources it and labelled on the bottom silkscreen with
what it measures. They are flat, so they respect the bottom height limit and can be
reached by a bed-of-nails fixture. Four GND loops (Keystone 5015) on the top side take a
scope ground clip: in the power corner, by the debug headers, on the STM32 side and in the
audio corner. See [bring-up](bringup.md) for the power-on order.

| label | ref | net | expect | location |
|---|---|---|---|---|
| 12VIN | TP1 | +12V_JACK | 12 V (input, before protection) | x 24 mm, y 8 mm, bottom side |
| 12V | TP2 | +12V | 12 V (after fuse, reverse FET and shunt) | x 138 mm, y 18 mm, bottom side |
| 5V | TP3 | +5V | 5.0 V | x 43 mm, y 67 mm, bottom side |
| 3V3 | TP4 | +3V3 | 3.3 V | x 40 mm, y 75 mm, bottom side |
| 1V0 | TP5 | +1V0 | 1.00 V | x 42 mm, y 57 mm, bottom side |
| 1V8 | TP6 | +1V8 | 1.80 V | x 46 mm, y 57 mm, bottom side |
| 1V35 | TP7 | +1V35 | 1.35 V | x 52 mm, y 70 mm, bottom side |
| VADJ | TP8 | VADJ | 0 V until enabled, then 1.8/2.5/2.6/3.3 V per VADJ_SEL | x 60 mm, y 6 mm, bottom side |
| 3V3M | TP9 | +3V3_MEZZ | 3.3 V | x 131 mm, y 13 mm, bottom side |
| 12VM | TP10 | +12V_MEZZ | 12 V | x 117 mm, y 28 mm, bottom side |
| MGTAVCC | TP11 | +1V0_MGT | 1.00 V | x 54 mm, y 51 mm, bottom side |
| MGTAVTT | TP12 | +1V2_MGT | 1.20 V | x 50 mm, y 52 mm, bottom side |
| 5VA | TP13 | +5V_AUD | 5.0 V | x 135 mm, y 77 mm, bottom side |
| 3V3A | TP14 | +3V3_AUD | 3.3 V | x 132 mm, y 69 mm, bottom side |
| VTT | TP28 | VTT_DDR | 0.675 V | x 46 mm, y 74 mm, bottom side |
| VREF | TP29 | VREF_DDR | 0.675 V | x 57 mm, y 70 mm, bottom side |
| PG5V | TP15 | PG_5V | high (5 V) when 5V is good | x 37 mm, y 62 mm, bottom side |
| PG1V0 | TP16 | PG_1V0 | high (5 V) when 1V0 is good | x 39 mm, y 68 mm, bottom side |
| PG1V8 | TP17 | PG_1V8 | high (5 V) when 1V8 is good | x 47 mm, y 67 mm, bottom side |
| PG3V3 | TP18 | PG_3V3 | high (5 V) when 3V3 is good | x 34 mm, y 94 mm, bottom side |
| PG3V3M | TP19 | PG_3V3M | high (5 V) when 3V3_MEZZ is good | x 131 mm, y 9 mm, bottom side |
| PGVADJ | TP20 | VADJ_PG | high (3.3 V) when VADJ is good | x 49 mm, y 9 mm, bottom side |
| DONE | TP26 | FPGA_DONE | high after the FPGA is configured | x 72 mm, y 27 mm, bottom side |
| INIT | TP27 | FPGA_INIT_B | high once the FPGA has cleared its memory | x 72 mm, y 58 mm, bottom side |
| NRST | TP25 | NRST | 3.3 V, low while the STM32 is in reset | x 98 mm, y 50 mm, bottom side |
| GND | TP21 | GND | 0 V | x 47 mm, y 94 mm |
| GND | TP22 | GND | 0 V | x 133 mm, y 64 mm |
| GND | TP23 | GND | 0 V | x 133 mm, y 58 mm |
| GND | TP24 | GND | 0 V | x 135 mm, y 88 mm |

## clocks on the board

| ref | frequency | drives |
|---|---|---|
| X1 | 100MHz 3V3 CMOS | SYSCLK_100M |
| X2 | 24.576MHz 3V3 CMOS | AUD_CLK_48K |
| X3 | 22.5792MHz 3V3 CMOS | AUD_CLK_44K |
| X4 | 125MHz LVDS | REFCLK0_OSC_N, REFCLK0_OSC_P |
| Y1 | 25MHz 8pF | HSE_IN, HSE_OUT |
| Y2 | 32.768kHz 6pF | LSE_IN, LSE_OUT |
| Y3 | 24MHz 12pF | ULPI_XI, ULPI_XO |
| Y4 | 25MHz 10pF | ETH_XI, ETH_XO |

## connector pinouts

### STM32 SWD, MIPI-10 (J3)

x 99 mm, y 93 mm from the front-top corner, top, `MCU_SWD MIPI-10`. Key pin 7 removed.

| pin | signal |
|---|---|
| 1 | +3V3 |
| 2 | SWDIO |
| 3 | GND |
| 4 | SWCLK |
| 5 | GND |
| 6 | SWO |
| 7 | - |
| 8 | - |
| 9 | GND |
| 10 | NRST |

### soft-core SWD, MIPI-10 (J14)

x 107 mm, y 93 mm from the front-top corner, top, `SOFTCORE_SWD MIPI-10`. 

| pin | signal |
|---|---|
| 1 | +3V3 |
| 2 | SC_SWDIO |
| 3 | GND |
| 4 | SC_SWCLK |
| 5 | GND |
| 6 | SC_SWO |
| 7 | - |
| 8 | - |
| 9 | GND |
| 10 | SC_NRST |

### FPGA JTAG 2x7 (J12)

x 62 mm, y 86 mm from the front-top corner, top, `FPGA_JTAG Xilinx`. 

| pin | signal |
|---|---|
| 1 | GND |
| 2 | +3V3 |
| 3 | GND |
| 4 | FPGA_TMS |
| 5 | GND |
| 6 | FPGA_TCK |
| 7 | GND |
| 8 | FPGA_TDO |
| 9 | GND |
| 10 | FPGA_TDI |
| 11 | GND |
| 12 | - |
| 13 | GND |
| 14 | - |

### FPGA JTAG 1x6 (J13)

x 67 mm, y 78 mm from the front-top corner, top, `FPGA_JTAG 6p`. 

| pin | signal |
|---|---|
| 1 | +3V3 |
| 2 | GND |
| 3 | FPGA_TCK |
| 4 | FPGA_TDO |
| 5 | FPGA_TDI |
| 6 | FPGA_TMS |

### STM32 console UART (J5)

x 78 mm, y 84 mm from the front-top corner, top, `MCU_UART FTDI`. Pin 4 is the STM32 RX (connect FTDI TXD).

| pin | signal |
|---|---|
| 1 | GND |
| 2 | - |
| 3 | - |
| 4 | CONSOLE_RX |
| 5 | CONSOLE_TX |
| 6 | - |

### soft-core UART (J15)

x 96 mm, y 84 mm from the front-top corner, top, `SOFTCORE_UART FTDI`. 

| pin | signal |
|---|---|
| 1 | GND |
| 2 | - |
| 3 | - |
| 4 | SC_UART_RX |
| 5 | SC_UART_TX |
| 6 | - |

### Pmod A (J16)

x 62 mm, y 92 mm from the front-top corner, top, `PMODA`. Socket pin numbering: odd row is Pmod pins 1-6.

| pin | signal |
|---|---|
| 1 | PMODA_IO1 |
| 2 | PMODA_IO5 |
| 3 | PMODA_IO2 |
| 4 | PMODA_IO6 |
| 5 | PMODA_IO3 |
| 6 | PMODA_IO7 |
| 7 | PMODA_IO4 |
| 8 | PMODA_IO8 |
| 9 | GND |
| 10 | GND |
| 11 | +3V3 |
| 12 | +3V3 |

### Pmod B (J17)

x 80 mm, y 92 mm from the front-top corner, top, `PMODB`. 

| pin | signal |
|---|---|
| 1 | PMODB_IO1 |
| 2 | PMODB_IO5 |
| 3 | PMODB_IO2 |
| 4 | PMODB_IO6 |
| 5 | PMODB_IO3 |
| 6 | PMODB_IO7 |
| 7 | PMODB_IO4 |
| 8 | PMODB_IO8 |
| 9 | GND |
| 10 | GND |
| 11 | +3V3 |
| 12 | +3V3 |

### STM32 breakout 2x20 (J7)

x 137 mm, y 24 mm from the front-top corner, top, `MCU_BREAKOUT`. 

| pin | signal |
|---|---|
| 1 | +3V3 |
| 2 | +5V |
| 3 | NC |
| 4 | NC |
| 5 | NC |
| 6 | NC |
| 7 | NC |
| 8 | NC |
| 9 | GND |
| 10 | GND |
| 11 | NC |
| 12 | NC |
| 13 | NC |
| 14 | NC |
| 15 | NC |
| 16 | NC |
| 17 | NC |
| 18 | NC |
| 19 | GND |
| 20 | GND |
| 21 | MCU_PC10 |
| 22 | MCU_PC11 |
| 23 | MCU_PC12 |
| 24 | NC |
| 25 | MCU_PE2 |
| 26 | NC |
| 27 | NC |
| 28 | MCU_PE5 |
| 29 | GND |
| 30 | GND |
| 31 | MCU_PE6 |
| 32 | NC |
| 33 | I2C1_SCL |
| 34 | I2C1_SDA |
| 35 | FDCAN1_TX |
| 36 | FDCAN1_RX |
| 37 | NRST |
| 38 | GND |
| 39 | +3V3 |
| 40 | +5V |

### expander spare (J6)

x 114 mm, y 70 mm from the front-top corner, top, `IOX_SPARE`. 

| pin | signal |
|---|---|
| 1 | IOX_P14 |
| 2 | IOX_P15 |
| 3 | IOX_P16 |
| 4 | IOX_P17 |
| 5 | +3V3 |
| 6 | GND |

### BOOT0 (J2)

x 101 mm, y 78 mm from the front-top corner, top, `BOOT0`. 

| pin | signal |
|---|---|
| 1 | BOOT0 |
| 2 | +3V3 |

