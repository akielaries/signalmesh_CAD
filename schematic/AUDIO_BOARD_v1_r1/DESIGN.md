# AUDIO_BOARD_v1_r1 - analog audio front-end

## Decisions (locked)
- Supply: **dual-rail +/-5V** (+5V in, -5V generated on-board by a charge-pump inverter)
- Scope v1_r1: **front-end only** - buffer + reconstruction filter + output driver + jack
- Channels: **stereo** (L + R, identical paths)
- Filter/FX (VCF, OTA/CV-controlled): **deferred to v1_r2**

## Signal path (per channel), all OPA1678, ref to 0V (dual supply)
`U.FL in -> AC-couple -> Sallen-Key reconstruction LPF (~20kHz) -> output buffer -> 100R -> jack`

## Component list

### Power (shared)
| Ref | Value / Part | Notes |
|-----|--------------|-------|
| J1  | PinHeader 1x02 | +5V, GND in (from system) |
| U1  | ICL7660S (charge-pump inverter) | +5V -> -5V |
| C1  | 10uF | +5V input reservoir (U1.8) |
| C2  | 10uF | flying cap, U1.CAP+ (2) <-> U1.CAP- (4) |
| C3  | 10uF | -5V reservoir (U1.5) |
| C4/C5 | 10uF each | +5V / -5V bulk |

ICL7660 pins: 8=V+ (+5V in), 2=CAP+, 4=CAP-, 5=VOUT (-5V), 3=GND.

### Left channel
| Ref | Value | Role |
|-----|-------|------|
| J2  | U.FL_Hirose_U.FL-R-SMT-1_Vertical | AUDIO_L_IN (center), shield=GND |
| C6  | 1uF   | input AC-couple (strip DAC DC offset) |
| R1  | 100k  | input bias to 0V |
| U2  | OPA1678 (dual) | A=SK filter, B=output buffer |
| R2,R3 | 10k each | Sallen-Key series R |
| C7  | 1nF   | SK feedback cap (U2A out -> R2/R3 node) |
| C8  | 560pF | SK cap (+in to GND) |
| R4  | 100R  | output series |
| C9,C10 | 0.1uF | U2 decoupling (+5V, -5V) |

Sallen-Key (unity gain, Butterworth ~20kHz): in -> R2 -> R3 -> U2A.+IN; C7 from U2A.OUT to R2/R3 node; C8 from U2A.+IN to GND; U2A.OUT -> U2A.-IN (unity). U2B: +IN from U2A.OUT, -IN->OUT (buffer) -> R4 -> jack tip.

### Right channel (mirror of Left)
| J3 U.FL AUDIO_R_IN | C11 1uF | R5 100k | U3 OPA1678 | R6,R7 10k | C12 1nF | C13 560pF | R8 100R | C14,C15 0.1uF |

### Output
| Ref | Part | Notes |
|-----|------|-------|
| J4  | 3.5mm TRS jack | Tip=L (R4), Ring=R (R8), Sleeve=GND |

## Key nets
- +5V: J1.1, U1.8, C1, C4, U2.8, U3.8
- -5V: U1.5, C3, C5, U2.4, U3.4
- GND: J1.2, J2/J3 shields, R1, R5, C8, C13, U1.3, J4 sleeve, all decouple caps
- AUDIO_L_IN: J2 center -> C6 -> R1/U2A input node
- AUDIO_R_IN: J3 center -> C11 -> R5/U3A input node

## Notes
- Reconstruction fc ~20kHz (R=10k, C1=1nF, C2=560pF). If you oversample the DAC (96k+),
  this filter can be gentler.
- Output ~2Vrms possible on +/-5V. Add series R for cable safety.
- v1_r2 adds the OTA (LM13700) CV-controlled VCF between the filter and output, plus CV inputs.
