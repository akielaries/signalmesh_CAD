# FX panels — POPULATED (2026-08-03), Option B

## Layout (all 4 cells populated)
- MASTER (bottom-left) | FILTER (top-right) | DRIVE=FX_CHAIN (top-left FX-A) | CHORUS (bottom-right FX-B)
- Chorus put in the taller FX-B (70x75) because of its big through-hole DIP-8 ICs; drive in FX-A.
- Phaser kept OFF this panel (its own board) per Option B.

## State
- 68 FX footprints placed headless (pcbnew import + occupancy, pad-level no-overlap): 0 SHORTS.
- Linked to schematic (path /SHEETUUID/SYMUUID), correct values + footprint identifiers (lib-prefixed).
- Interface + power isolated per cell (chorus->FXB_*, drive->FXA_*), fed by the stub connectors + pours.
- DRC 81 (cosmetic: courtyard-overlap from tight FX packing, lib-mismatch, silk-edge). 0 shorts, 0 invalid-outline.

## Remaining (not blocking; normal next steps)
1. ROUTING - the whole board is unrouted (447 airwires) since the panel restructure invalidated the old
   routing. Master + filter + both FX cells need routing. This is the big remaining task.
2. FX_CHAIN pre-existing quirks (~24 parity): LM13700 DIODE_BIAS pins 2/15 need no_connect (benign, same
   as the master OTAs); tremolo-tap junction bridges (R722/R723/R732/R733) - the recovered "prestrip"
   sheet predates the bridge fix documented in memory. Apply the generator bridge fix + no_connects.
3. Recovered FX sheets are pre-grid-fix (~236 off-grid ERC) - per-sheet grid-fix (net-count-guarded).

Backups: .fx_placed (this state), .pre_fxplace (pre-FX clean), .pre_fx (schematic).
