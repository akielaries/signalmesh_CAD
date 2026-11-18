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
