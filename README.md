# signalmesh CAD files
- KICAD schematic and PCB files
- renders of the schematics, PCB layers, and 3D view
- freeCAD render of the integrated signalmesh synthesizer

## layout

```
boards/<BOARD>/<vN_rM>/    one kicad project per version/revision
boards/_archive/           pre-split signalmesh v1-v4 dumps, not maintained
sim/                       spice + signal-integrity sim toolkit
tools/                     render, gallery, and fmc parity scripts
3d_assembly/               freeCAD assembly
```

boards today: 7SDD, ACM, AFFM, APM, AUDIO_BOARD, COMPUTE_BOARD, OSC_CTRL.

only the newest revision of each active board is rendered in ci. the allowlist
lives in `tools/render.sh` (`RENDER_BOARDS`) and doubles as the github actions
render matrix, so adding a board or bumping a revision is a one-line change.
