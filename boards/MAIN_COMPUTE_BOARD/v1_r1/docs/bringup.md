# bring-up and firmware notes

## STM32

- select LDO supply in PWR_CR3 before raising the clock (SDEN=0, LDOEN=1). VOS0 is
  reached from VOS1 by setting ODEN in SYSCFG_PWRCR. VOS0 (480 MHz) needs a
  suffix-6 part.
- set USB33DEN before using either USB controller (VDD33USB is supplied externally).
- QUADSPI runs dual-flash (DFM=1). Both flashes share BK1_NCS, so single-flash access
  (DFM=0 with FSEL) is not possible on this board. W25Q01JV: check the status register
  handling in the driver, it differs a little from Macronix parts.

## FPGA configuration (slave SelectMAP, M[2:0]=110)

1. drive PROGRAM_B low, release, wait for INIT_B high.
2. hold RDWR_B low and CSI_B low for the whole load. If RDWR_B is high while CSI_B is
   low the FPGA drives the data bus, and toggling RDWR_B with CSI_B low aborts.
3. clock the bitstream on FMC D0-D15 with CCLK (STM32 GPIO). Speed is not critical.
4. wait for DONE high, then release CSI_B/RDWR_B. The FMC pins become user IO.

JTAG stays available at all times on the 2x7 and 1x6 headers.

## DDR3 (MIG)

- chip select disabled (CS_N is tied low at the DRAM), internal VREF, 800 Mb/s max.
- sys_clk comes from the 100 MHz oscillator through an MMCM ("no buffer" option).
- re-run MIG pin validation in Vivado with the bank 34 plan in [pinout](pinout.md).

## mezzanine

- read the card EEPROM at 0x50 (I2C1), set VADJ_SEL, enable VADJ, wait VADJ_PG,
  then drive MEZZ_PG_C2M high.
