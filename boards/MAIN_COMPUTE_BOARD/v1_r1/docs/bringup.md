# bring-up and firmware notes

## first power-up

Every rail and power-good has a labelled test point; the table with expected readings is in
the [hardware reference](hardware.md#test-points).

1. unpowered: measure each rail test point to a GND loop on the ohms range. Nothing
   should read below about 10 R. The 1V0 core rail reads lowest, since the FPGA core
   loads it.
2. power from a bench supply at 12 V with the current limit at 0.5 A, through the barrel
   jack or the DIN. Expect roughly 150-300 mA at 12 V with an unconfigured FPGA (estimate, not yet measured).
3. check the rails in sequence order. Each stage enables the next, so the first missing
   rail is the fault:

| step | rail (test point) | enabled by |
|---|---|---|
| 1 | 12VIN, 12V | input; 12V is after the fuse, reverse-polarity FET and current shunt |
| 2 | 5V, 3V3M | 12V through the 100k/15k EN divider (5V starts at about 9.4 V input) |
| 3 | 1V0 | PG5V |
| 4 | 1V8, MGTAVCC | PG1V0; the MGTAVCC LDO is enabled from 1V8 |
| 5 | 3V3, 1V35, MGTAVTT | PG1V8; MGTAVTT is RC-delayed after MGTAVCC (DS181 order) |
| 6 | VTT, VREF | 3V3 |
| 7 | VADJ | firmware: VADJ_EN on the IO expander, after reading the mezzanine EEPROM |

4. with all rails good, the 3V3 LED is on. INIT goes high once the FPGA has cleared its
   configuration memory. DONE stays low until a bitstream is loaded over SelectMAP or JTAG.
5. raise the current limit to 2 A before configuring the FPGA or plugging in SFPs or a
   mezzanine.

## STM32

- select LDO supply in PWR_CR3 before raising the clock (SDEN=0, LDOEN=1). VOS0 is
  reached from VOS1 by setting ODEN in SYSCFG_PWRCR. VOS0 (480 MHz) needs a
  suffix-6 part.
- set USB33DEN before using either USB controller (VDD33USB is supplied externally).
- QUADSPI runs dual-flash (DFM=1). Both flashes share BK1_NCS, so single-flash access
  (DFM=0 with FSEL) is not possible on this board. W25Q01JV: check the status register
  handling in the driver, it differs a little from Macronix parts.

## Ethernet MAC address

- read the 6-byte EUI-48 from the 24AA025E48 (U200) on I2C1, device address 0x54, memory
  address 0xFA-0xFF, and program it into the ETH MAC address registers. It is factory-written
  and read-only.
- 0x00-0x7F of the same chip is free EEPROM (board serial, calibration). Device addresses
  0x50-0x53 are left for a VITA module's EEPROM.

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
- the bank 34 plan is pin-swapped for layout: FPGA byte group T0 carries the DRAM upper
  byte (DQ8-15, UDQS, UDM) and T1 the lower byte. DQ bits are reordered within each byte, and
  address/command nets are reordered among the address/command balls. DQS, CK, DM, ODT and RESET
  keep their original pins, so the MIG rules still hold. Use the plan in pinout.md for the XDC,
  not the original MIG default.

## mezzanine

- read the card EEPROM at 0x50 (I2C1), set VADJ_SEL, enable VADJ, wait VADJ_PG,
  then drive MEZZ_PG_C2M high.
