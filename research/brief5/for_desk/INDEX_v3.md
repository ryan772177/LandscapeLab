# Brief 5 baseline v3 — send-back to the research desk

**2026-09-20.** Response to `BRIEF5_BASELINE_AUDIT.md`. The two headline v2
conclusions were re-measured; neither survives as v2 stated it. All work
read-only against the world (standalone `-game` runs restored by process exit;
one offscreen read-only editor pass, closed clean, world byte-identical to HEAD).

## Read these first
| file | what |
|---|---|
| `BASELINE.md` | v3, ordered MEASURED → MEASURED-NEGLIGIBLE → INCONCLUSIVE, each with its control; closing "what the desk may / may not derive"; levers table with header:line. |
| `input/density_baseline.json` | machine-readable; `_v3` note; blocks `task1_noise_floor`, `task3_forest_cost`, `task4_editor_census`, `item3_editor_readbacks.hlod_gpu_share`. Reproducible from `scripts/assemble_baseline_v2.py` (idempotent). |

## How each audit finding was answered
| audit | v3 disposition |
|---|---|
| **A1** HLOD "nearest 2.2–3.5 km" an artefact | CONFIRMED + fixed. `input/hlod_share.json` + `editor_census_v3.json hlod_cell_distance_m`: distances derived from the grid index (`centre=(idx+0.5)·cellsize`), not the degenerate Instanced-HLOD bounds. Distances now vary per cell/station. |
| **A2** editor A/B no positive control | CONFIRMED. The v2 0.015 ms null is the control *failing* (proxies hidden at full residency). Verdict → INCONCLUSIVE. |
| **A3** `wp.Runtime.HLOD` is a command | CONFIRMED at header: FAutoConsoleCommand, HLODRuntimeSubsystem.cpp:149. `input/hlod_task2_gamepath.md`. |
| **A4** density measured off-frustum | CONFIRMED. Re-measured at a forest station. `input/forest_cost.json`. |
| **A5** treeline delta inside noise | CONFIRMED + quantified. Noise floor `input/noise_floor.json`; GPUScene deterministic (refutes "streaming variance"). |
| **A6** pass table can't say "not the forest" | Addressed: per-pass **delta** table (as-is − hidden) at the forest station. `input/forest_cost.json per_pass_delta_ms`. |
| **A7** what the far forest is, not read back | READ BACK. `editor_census_v3.json hlod_layers`: Instanced=INSTANCING (lowest-LOD ISM), Merged=MESH_APPROXIMATE. |
| **A8** billboard switch hidden by "detail band" | Quantified. `input/switch_distances.json`: cards engage 88–128 m, all above the 40 px floor. |
| **B1** self-contradiction on the open question | Reconciled to INCONCLUSIVE throughout. |
| **B2** JSON not reproducible from assembler | Fixed: assembler reads HLOD from `hlod_share.json`, computes per-10k from inputs; byte-identical on re-run. |
| **B3** DensityScale wrong tool | READ BACK: all four FoliageTypes `enable_density_scaling=False` → the lever is inert on these trees. |
| **B4/B5/B6** PCG_NOTES | Fixed in `PCG_NOTES.md` v3 (stages un-swapped; flags 1/2/4 resolved; gen-sources + cvars added; cites repointed). |
| **C** hygiene (census tuple crash, `visible` rename, probe date, dolly pairs) | Fixed: `scripts/density_census.py` (segment test + selftest), probe re-run today, `dolly_manifest.json` 267 usable pairs. |

## The numbers
- **Noise floor** (min_detectable = 2·sd GPU p90): treeline 0.060, plaza 0.040, forest 0.016 ms.
- **Forest foliage cost**: 0.185 ms p90, **11.4× min_detectable**; LumenReflections +0.324 / ShadowProjection +0.105 / Basepass +0.086 (not NaniteVisBuffer); **0.100 ms / 1000 in-frustum-in-cull trees** (upper bound). Station has 1844 in-frustum trees (max at 90° hFOV; 5000 unreachable on this ~0.005 trees/m² forest).
- **HLOD proxy GPU share**: **INCONCLUSIVE** (both `-game` and editor controls fail in-fence). Composition measured (INSTANCING lowest-LOD + MESH_APPROXIMATE), rendering beyond 512 m.
- **Density lever**: inert (`enable_density_scaling=False`).

## What the desk may now derive Brief 5 from
On-frustum forest foliage cost (0.185 ms / 0.100 ms per 1000 visible trees, with noise floor + per-pass split); the per-species representation ladder + switch distances; the HLOD proxy composition; density lever inert.

## What it still may not
Treat the HLOD proxy GPU **share** / live pixel fraction as measured — INCONCLUSIVE, needs a `-game` MRQ HLOD-toggle (item 8). Do not read the forest number as a precise per-visible-tree cost (upper bound: the delta also removed grass + off-frustum trees). Do not extrapolate density past the authored count (lever cannot test it).

## Manifest (files in this package)
- `BASELINE.md`, `PCG_NOTES.md`, `for_desk/INDEX_v3.md`
- `input/`: `density_baseline.json`, `noise_floor.json`, `forest_station.json`, `forest_cost.json`, `switch_distances.json`, `editor_census_v3.json`, `hlod_share.json`, `hlod_task2_gamepath.md`, `levers_verified.md`, `_census_stations.json`, `dolly_manifest.json`, `reference_coverage.json`, `replay_inventory.json`, `pcg_worldactor_probe.json`, `live_proxy_observation_STATUS.md`
- `scripts/`: `assemble_baseline_v2.py`, `density_census.py`, `noise_floor.py`, `derive_forest_station.py`, `forest_cost.py`, `switch_distances.py`
- fresh LOD probe: `_verify/bench/2026-09-20/tree_lod_probe_v3.json` (referenced; also copied into `input/`)
