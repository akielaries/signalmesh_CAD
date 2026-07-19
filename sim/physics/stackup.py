#!/usr/bin/env python3
# shared stackup constants for the APM and ACM boards (4-layer FR4).
# both boards use the identical stack, read from the kicad_pcb stackup block.

COPPER_T = 0.035e-3     # copper thickness, m (1 oz)
PREPREG_H = 0.1e-3      # outer copper to nearest inner plane, m
CORE_H = 1.24e-3        # inner plane to inner plane, m
ER = 4.5               # FR4 relative permittivity
TAN_D = 0.02           # loss tangent

# distance from an outer signal layer to the FAR inner plane
# (used only if the near inner layer is a signal, not a plane)
OUTER_TO_FAR = PREPREG_H + COPPER_T + CORE_H
