# INDEX_p — Overnight Queue 2 (PCG density/clutter), morning summary

**Night of 2026-09-21. Autonomous. Checkpoint `pre-pcg-night` on b5ac5c55. NOT PUSHED at
write time (pushed at close).**

## 10-line MORNING SUMMARY

1. **Plugin state:** core PCG already enabled (`PCGPythonInterop`); **PVE already enabled**.
   Biome Core/Sample + deps confirmed present in the install but **NOT enabled** — deferred
   (non-essential + experimental-open risk under autonomy).
2. **The density lever** is one global multiplier `m` on the tree-density field; the desk's
   `m_for.p90_bin = 5.48` (crown 0.85) makes the densest tenth a real forest.
3. **Cost table (ex-clutter, per station @ m=5.48):** forest_floor 12.645→**13.474**;
   treeline 7.139→**7.513**; plaza 9.476→**9.882**. Every number sourced
   (`input/density_projection.json`, `for_desk/DENSITY_PLAN.md`).
4. **Per-station verdicts:** forest_floor **OVER the ruled 13.0 by 0.474** (a *lower bound*) on
   live-tree growth alone — the current hold 12.645 is 0.355 UNDER 13.0; treeline over
   nominal 7.0 but **UNDER tolerance 7.7**; plaza **UNDER** with ~0.6 ms room for clutter.
5. **Budget RULED (Ryan 2026-09-22, Daylight Density session): R5-1 = 13.0 ms (desk revision),
   superseding the earlier same-day 12.5.** 13.0 is both the pass/fail budget and the fence abort
   ceiling. forest_floor headroom at 13.0 is small but positive before density; taking m=5.48
   there still busts by 0.474, so it needs a cull/shadow lever or a reduced multiplier.
6. **The paying lever** at forest_floor is **cull / foliage-shadow distance**, NOT T4
   tri-reduction — the growth is in Lumen+shadows+basepass, not Nanite raster (per-pass sourced).
7. **P3 clutter cost: NOT MEASURED — acceptance arms not met (stated plainly, rule 10).** The
   harness reaped the measurement's background process twice; the editor then held its Python
   thread and went unresponsive; force-killed (world byte-identical). Owed: game-thread add cost
   (`scratchpad/pcg_measure_fast.py`, minutes supervised) + GPU render cost (-game MRQ pass).
8. **PCG feasibility: PROVEN.** A real PCG graph (SurfaceSampler→TransformPoints→
   StaticMeshSpawner weighted) was authored AND saved from Python
   (`Content/Scratch/PCG/PCG_ClutterSpike.uasset`). The reliable clutter substrate is the proven
   `InstancedFoliageActor.add_instances` idiom (place_foliage.py).
9. **What's clean:** shipped `Alpine8K.umap` (git-tracked, no diff vs HEAD, mtime predates
   session), `foliage/`, `recipes/`, vendor meshes byte-identical to `pre-pcg-night`. No
   regeneration, no HLOD build, no shipped-mesh edits, no history ops. Scratch: the PCG graph
   asset stays on disk, **gitignored** (Content/Scratch is already excluded) — not committed.
10. **PVE (Task 9) verdict:** **no migration — evaluate further.** Experimental in 5.8,
    5.7→5.8 asset breakage, broken non-Nanite export, only a non-single-variable −0.38 ms delta.

## Deliverables
- `input/clutter_inventory.json` — 79 ground-clutter meshes (P2).
- `input/density_projection.json` + `scripts/density_project.py` — P4 arithmetic.
- `for_desk/DENSITY_PLAN.md` — the per-station projected-vs-budget table (P4).
- `input/pcg_cost.json` — P3: PCG-authoring feasibility PROVEN; cost measurement owed (honest).
- `scripts/payloads/pcg_clutter_spike.py` + `pcg_measure_fast.py` (scratchpad) — the ready-to-run,
  gated measurement harness for a supervised session.
- `for_desk/OVERNIGHT_LOG_2.md` — the two-altitude night log.
- Tools: `scripts/payloads/pcg_clutter_spike.py`, `scripts/pcg_spike_run.py` (gated).

## What needs Ryan
- ~~forest_floor budget ruling~~ **CLOSED 2026-09-22: R5-1 = 13.0 (desk revision), superseding the earlier same-day 12.5.**
- Whether to accept `m=5.48` globally (busts forest_floor at 13.0 by 0.474) or cap it / apply the
  cull-shadow lever there while taking the full multiplier at plaza (which has room).

## Owed measurements (for a supervised session)
- Steady-state **GPU render cost** of clutter per 1000 by class (a -game MRQ pass on a saved
  scratch level).
- A **post-hold per-tree rate** at forest_floor (the current projection is a pre-hold lower bound).
- An **in-game HLOD share** at forest_floor/plaza (item 8 measured only treeline/vista).
