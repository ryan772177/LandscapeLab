# Brief-4 CARVE_PLAN T6 — reachable re-measure (2026-09-19b)

The two spec MEASUREMENT figures re-measured post-water (RULING §4.3).

## z-span + walkable (offline 1 m instrument, reproduces baseline first)
`research/brief4/scripts/remeasure_reachable_water.py`:
- **z-span 0–1552.485 m** (carve sub-decimetre; unchanged).
- **walkable 47.77 km²** (was 49.27; water −1.50). Offline 1 m quad
  instrument reproduces the 49.27 baseline before subtracting water (rule 13).
- walkable_submerged 1.5 km²; reachable-lost-to-water (BFS bound) 1.49 km².

## reachable (NAVMESH lattice, R-NAVGRID step 9 — editor path query)
Editor relaunched offscreen (rule 11: confirmed /Game/Alpine8K.Alpine8K;
rule 7 MATCH). `scripts/city_reachable_lattice_payload.txt`, box
±406400 cm, step 6000 cm, 18496 cells, 64 nav-chunk actors resident.

**Post-water reachable = 9810 of 18496 cells = 35.32 km²** (was 36.53).
Reduction **336 cells = 1.21 km²** for the water — within the ≤1.5 target
(walkable_submerged 1.5). projecting 15068 (baseline 15573); controls:
seed reachable True, 50 km control unreachable.

## THE ANOMALY, ROOT-CAUSED (rule 10/13 — a wrong first read, not hidden)

The FIRST lattice run read **reachable 2802 / projecting 11375** — a 72%
collapse that does NOT reproduce the 36.53 baseline, so it was REFUSED as
a measurement (rule 13), not recorded.

**Root cause (measured):** the lattice ground trace hit `WorldPartitionHLOD`
proxy collision instead of the landscape. The HLOD proxies gained collision
in the 2026-09-14 4096 rebuild; the 2026-08-27 nav baseline (10146) predates
it, so the original payload did not ignore them. A trace stopping on the
proxy returns a wrong ground height, and `project_point_to_navigation`
(extent 500 cm) then misses the navmesh below it — coverage AND connectivity
both read low. Diagnostics: `nav_diag.json` (points hitting WorldPartitionHLOD
as ground), `nav_conn.json`.

**Fix:** ignore `WorldPartitionHLOD` actors in the lattice ground trace
(the landscape is kept resident by `load_all_world_partition_regions`).
With them ignored: **reachable 2802 → 9810, projecting 11375 → 15068** —
reproduces the baseline minus the water delta. Folded into
`scripts/city_reachable_lattice_payload.txt`; the navmesh itself was never
defective — only the measurement instrument, corrupted by a world change
(HLOD collision) unrelated to the carve.

Evidence: `reachable_lattice_postwater.json` (2802, HLOD-corrupted, kept as
the refused first read), `reachable_lattice_nohlod.json` + the regenerated
canonical `city/alpine_basin_reachable_lattice.json` (9810), `nav_diag.json`,
`nav_conn.json`.

## Editor
Measurement-only session — NO scene mutation, NO save (dirty census 0).
Rule 4 capture NOT required (the water capture was taken in the T5 editor
phase). Editor closed on the R-EDITOR-CLOSE kill path (census 0 + RSS flat
18,068 MB + PackageRestoreData absent after kill).
