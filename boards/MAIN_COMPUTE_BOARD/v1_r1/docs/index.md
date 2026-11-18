# MAIN_COMPUTE_BOARD v1_r1

General-purpose STM32H7 + Artix-7 compute card in the 3U Eurocard format (160 x 100 mm).
It is the brain for the signalmesh synth: the FPGA does the DSP and drives the on-board DAC,
and it can also drive RF or other front ends through the VITA 57.1 mezzanine.

- [power tree and sequencing](power.md)
- [pin plans: STM32, FPGA banks, connectors](pinout.md)
- [PCB: stackup, impedance, net classes, floorplan](pcb.md)
- [bring-up and firmware notes](bringup.md)

## block diagram

```mermaid
flowchart LR
  subgraph FRONT[front panel]
    J12V[12V barrel]
    SFP0[SFP0]
    SFP1[SFP1]
    RJ45[RJ45 100M]
    USBA[USB-A host MIDI]
    USBC[USB-C HS device]
  end
  MCU[STM32H755BIT6<br/>M7 480 MHz + M4]
  FPGA[XC7A100T-2FGG484<br/>63k LUT, 4 GTP]
  DDR[DDR3L 4Gb x16]
  QSPI[2x W25Q01 1Gb<br/>dual QSPI]
  VITA[VITA 57.1 HPC<br/>34 LA pairs, 2 lanes]
  DIN[DIN 41612 C 3x32<br/>backplane]
  AUD[CS4344 DAC + OPA1656<br/>L/R u.fl]
  USBC --- PHY[USB3300 ULPI] --- MCU
  USBA --- MCU
  RJ45 --- ETH[LAN8742A RMII] --- MCU
  QSPI --- MCU
  MCU <-->|FMC 32-bit sync, 6 IRQ| FPGA
  MCU -->|SelectMAP x16 config| FPGA
  FPGA --- DDR
  FPGA ---|GTP lanes 0/1| SFP0 & SFP1
  FPGA ---|LA pairs, GTP 2/3| VITA
  FPGA -->|I2S| AUD
  FPGA ---|TDM bus| DIN
  MCU ---|CAN-FD| DIN
  J12V --> PWR[power tree]
  DIN --> PWR
```

## key parts

| function | part | notes |
|---|---|---|
| MCU | STM32H755BIT6 (LQFP208) | LDO supply mode for VOS0 480 MHz. BIT3 is not a substitute (no VOS0) |
| FPGA | XC7A100T-2FGG484I | wire-bond plastic BGA, GTP max 6.25 Gb/s in this package |
| memory | MT41K256M16TW-107 | DDR3L x16, 800 Mb/s with internal VREF, MIG chip select disabled |
| boot/bitstream flash | 2x W25Q01JVSFIQ | QUADSPI dual-flash, 8-bit, 256 MB memory mapped, shared BK1_NCS |
| USB HS PHY | USB3300-EZK | ULPI, 24 MHz crystal |
| Ethernet PHY | LAN8742A | RMII, PHY sources the 50 MHz REF_CLK |
| audio DAC | CS4344 + OPA1656 | ported from APM v7, -5 V from LM2662 |
| mezzanine | Samtec ASP-134486-01 | VITA 57.1 HPC, LPC cards fit |
| backplane | DIN 41612 C 3x32 male R/A | provisional pinout, see [pinout](pinout.md) |
