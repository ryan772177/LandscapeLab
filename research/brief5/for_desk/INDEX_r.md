# Brief 5 REPAIR (R) — desk send-back index, 2026-09-21

**The T3 hold was re-applied, PERSISTED to disk, and PROVEN LIVE at runtime.**
Six-line summary, then the per-file table. All editor passes ended on
R-EDITOR-CLOSE (census dirty_count 0, killed, 0 editors, no PackageRestoreData).
Every new tool passed a three-round auditor gate before first execution. Offline
suite: NO FAILURES. NOT PUSHED (fence).

1. **R1 — HOLD PERSISTED.** Root cause confirmed at source: `SetLodScreenSizes`
   never marks the package dirty (StaticMeshEditorSubsystem.cpp:1020-1097), so
   T3's default `save_loaded_asset` was a clean-package no-op. Fix: `modify(True)`
   + `save_loaded_asset(only_if_is_dirty=False)`. Proven in a DIFFERENT process:
   both `.uasset` sha256+mtime changed; cold `get_lod_screen_sizes` (PID 32556 ≠
   apply 21944) = targets within 1e-4, tris 32/6, slots 5/4, auto-compute False.
2. **R2 — coloration INCONCLUSIVE (contaminated).** Overlapping boxes, no
   occlusion (ConiferPine classified index-4 yellow with 0% of its own card in
   BOTH C1 and R2). RenderData flipped matches_t3_hold False→True (persist+load,
   not runtime proof).
3. **isolated_check — scene-defeated.** Isolated cells render white offscreen; the
   dense band has no clean box. ConiferPine leaned geometry (95.5% red LOD1).
4. **R3 — HOLD TOOK AT RUNTIME (decisive).** forest_floor p90 12.645 vs v3
   pre-hold 11.048 = **+1.597 ms (99.8× noise)**; Basepass+ShadowDepths+Prepass
   **+1.131 ms (70.7× the 0.016 ms floor)** — the card→geometry conversion.
5. **R5-1 — OVER budget** (12.645 > 12.5 by 0.145 ms): T4 rungs LISTED, not run;
   hold NOT reverted.
6. **R4 — imposter override hypothesis DISCONFIRMED.** `MI_half_01_imposter_nowind`
   EXISTS at `/Game/Materials/PN_NoWind/` (C2 checked the wrong folder); shares
   base `MA_Imposter` + every scalar/vector/texture with the vendor MI; only delta
   = 2 static switches (Level 1 Bending/Wind) OFF — WPO, not frame selection. H4
   stands, resolved by R1+R3.

## Files

| path | what |
|---|---|
| `input/r1_persist.json` | R1 persist gate: sha/mtime before+after, cold distinct-process readback, PASS |
| `input/r1_apply_editor.json`, `r1_cold_editor.json` | R1 apply + cold editor records |
| `input/tree_lod_probe_cold.json` | the cold probe check_recipe_lods reads (cold_readback=True) |
| `input/r2_lod_readback.json` | R2 coloration (contaminated) + isolated_check outcome |
| `input/r2_verdict.md` | R2 two-instrument analysis, corrected per operator ruling |
| `input/r3_perf.json` | R3 per-pass deltas + runtime-control + R5-1 rulings |
| `input/imposter_defect.json` | R4 override diff + H4 resolution (R4_override_diff_result block) |
| `input/r4_imposter_read.json` | raw R4 material diff + placed HISM slots + HLOD probe |
| `input/iso_targets.json`, `iso_*_station.json` | isolated-camera search output |
| `derived/iso_lodcolor/` | isolated + control stills (iso_control_ring rendered; iso_* white) |
| `scripts/r_apply.py` | R1 driver (mtime/sha, apply, R-EDITOR-CLOSE, cold verify) |
| `scripts/r_lodcolor.py`, `r_isolated.py`, `iso_from_ring.py`, `find_isolated_instances.py`, `iso_analyze.py` | R2 + isolated_check tooling |
| `scripts/r_imposter.py` | R4 driver |
| `scripts/r3_perf.py` | R3 analyzer |
| `../scripts/check_recipe_lods.py` | now refuses any non-cold probe |
| payloads (in repo `scripts/payloads/`) | brief5_r1_apply / r1_cold / r1_probe_autoname / r4_imposter |
