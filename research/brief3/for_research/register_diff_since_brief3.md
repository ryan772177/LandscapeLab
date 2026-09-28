# REGISTER diff since Brief 3 delivery (37a8bb1d, 2026-09-10) → 2026-09-15

New/changed REGISTER_ADDENDUM entries since Brief 3 Task 0+1 closed:

- **B3.20** Task 3 CLOSED on the player instrument (no tile repeat player-visible).
- **B3.21** Landscape HLOD runs through ULandscapeHLODBuilder unconditionally; the layer's mesh-merge settings never governed the landscape (Task 5 acceptance VOID→corrected).
- **B3.22** Rule 13 (sample count beside verdict) → CLAUDE.md standing rule.
- **B3.23** Sky light white, double-sRGB encode removed (R-SKYCOLOR).
- **B3.24** HLOD batch size is a VRAM decision (≤96 cells).
- **B3.25** One truth instrument (--truth, 20 GO props).
- **B3.26** (A-6) WB is a coupled 2×2; joint solve: white_temp 3415.7→3438.6, tint −0.0113→−0.0248; card R/G 1.0014 B/G 0.998, in band.
- **B3.27** (A-7) shade band tracks the white point AND the sun-elevation floor. In force: **2.065–2.998 @ 3438.6 K, floor D6000** (sun <30°, Hernández-Andrés 2001). Measured 2.1896 → **PASS**.
- **B3.28** (A-8) content gate models canopy porosity (pct_sky + 0.21·pct_canopy); near_ground no longer false-refused, void still caught.
- **B3.29** (A-9) hygiene batch (warm-up two mechanisms, S-7 slope note, F-4, V-5, probe controls).
- **Q17 CLOSED** (B-4) Cloud_GlobalCoverage is not a screen cloud-fraction; 0.3 is not overcast; recipe unchanged.

In-force grade/shade values now (RECIPES CURRENT VALUES, per the Pass 4 plan):
white_temp 3438.6 / white_tint −0.0248 / compensation −14.2571; shade band
2.065–2.998 @ 3438.6 K D6000; contrast 0.95 effective.
