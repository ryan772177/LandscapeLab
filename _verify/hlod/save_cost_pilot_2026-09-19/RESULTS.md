# HLOD per-package save-cost pilot — RESULTS (2026-09-19)

**Goal.** Measure the real per-package SAVE cost of assigning HLOD layers to
World-Partition (OFPA) actors, the number missing since the 2026-09-07 whole-world
attempt hung for 90 minutes on the save. This is the "one cell first" the
2026-09-07 lesson demanded before any wider HLOD assignment/build.

**Instrument.** `scripts/payloads/hlod_setup_layers.py` (Pass-3-fixed: it now
actually saves each touched actor package one at a time, timed, and re-reads),
driven by `scripts/ue_exec.py --set CENTRE_CM=… --set RADIUS_M=… --set DRY_RUN=…`.

**Editor.** Fresh launch PID 9648 via `scripts/launch_editor.ps1` (offscreen),
`/Game/Alpine8K`, rule-7 gate MATCH (project=LandscapeLab). World fully loaded —
readiness probe read 4337 level actors: 1093 InstancedFoliageActor,
257 landscape (256 LandscapeStreamingProxy + 1 Landscape), 1449 StaticMeshActor,
matching the historical world (≈2799 target-class actors ≈ the 2,796 of 09-07).

## Measured per-package save cost (EditorLoadingAndSavingUtils.save_packages, one at a time)

| class | n | mean | min | max | read-back layer |
|---|---|---|---|---|---|
| StaticMeshActor (props) | 17 | 0.012 s | ~0.010 | 0.027 | Instanced ✓ |
| InstancedFoliageActor | 41 | 0.0115 s | 0.009 | 0.014 | FoliageApprox ✓ |
| LandscapeStreamingProxy | 21 | 0.564 s | 0.457 | 0.832 | Landscape ✓ |

All 79 packages saved OK, 0 failed, across every run. Per-package times were
STABLE within each class (no upward drift with count), which is the evidence for
linearity used in the projection below.

**Runs (each `ue_exec … --timeout 25/40`):**
- 50 m @ town centre `[-210800, 278800]`, DRY_RUN=0 → 17 props, total 0.203 s, max 0.027 s.
- 400 m @ interior `[-100000, -100000]`, DRY_RUN=0 → 1 foliage (0.013) + 1 proxy (0.849).
- 1200 m @ interior, DRY_RUN=0 → 40 foliage (total 0.460, max 0.014) + 20 proxies (total 11.278, mean 0.564, max 0.832).
- Preview DRY_RUN=1 runs (150 m town: 306 props + 1 foliage, 0 proxies; 400 m / 1200 m interior) sized the bounds.

## Whole-world projection (counts × class mean; NOT a full-world measurement)

    props     1449 × 0.012  s ≈  17.4 s
    foliage   1093 × 0.0115 s ≈  12.6 s
    proxies    256 × 0.564  s ≈ 144.4 s   (worst-case × 0.832 ≈ 213 s)
    landscape    1 × ~0.6   s ≈   0.6 s
    ------------------------------------------------
    TOTAL                     ≈ 175 s ≈ ~3 min   (worst case ~4 min)

## Conclusion

1. **The save path WORKS.** Per STATE it had never actually saved before the
   Pass-3 fix; here it persisted 79 packages across all three classes, 0 failures,
   verified on disk (save return) and by property read-back.
2. **The 2026-09-07 90-minute hang was the BULK save call** (save all ~2,796 in
   one operation), **not the intrinsic per-package cost.** One-package-at-a-time,
   the whole world projects to ~3 min, dominated by the 256 landscape proxies
   (~0.56 s each ≈ 65× a prop/foliage package).
3. **Caveat (rule 10):** the full-world per-package run was NOT executed, so ~3 min
   is a PROJECTION resting on the measured per-class means and observed linearity,
   not a whole-world measurement. The assignment POLICY is also unsettled
   (`_Landscape` ruled REDUNDANT, STATE 3c; FoliageApprox-for-all-foliage), so the
   full assignment deserves its own session with a named restore tag before it runs.

## Footprint

The pilot's assignments were fully REVERTED (`scripts/payloads/_o7_pilot_revert.py`):
79 cleared (17 props + 41 foliage + 21 proxies), all saved, whole-world re-scan
confirmed **0 target-class actors still layered** — the world returned to its
uniform `hlod_layer=None` baseline. The 60 byte-churned OFPA `.uasset` were then
`git checkout`-restored to HEAD (editor closed, so no disk/memory desync), leaving
zero tracked-package change. Editor closed on the R-EDITOR-CLOSE kill path after
census-clean (0 dirty) + RSS-flat (1.2 MB/40 s) + responsive; PackageRestoreData
absent after close.
