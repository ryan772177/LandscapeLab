# Audit + Brief 4 — completion summary to current state (2026-09-19)

**Status: both landed.** The 2026-09-14 pipeline audit is closed through Pass 5,
Pass 3 reading, and Pass 2; the Brief 4 water carve is FULLY LANDED (all thirteen
tasks T0–T12), R-WATER-CARVE is LOCKED, the editor is closed, the working tree is
clean, and `run_offline_suite.py` reports **no failures across 31 checks**.

This document is a human-readable roll-up of what was completed. It does not
replace `STATE.md` (the live block, 2026-09-19c), the audit ledgers under
`research/audit/`, or `research/brief4/CARVE_PLAN.md` — it collects them.

---

## Part 1 — The pipeline audit (2026-09-14 → 2026-09-17)

### What the audit was

A read-only corpus of the entire pipeline — every recipe, script, doc, register,
brief, plan, skill, commit message, plus the git history as text — was extracted
into `research/audit/` (four `pipeline_full_2026-09-14_part{1..4}.zip`) and mined
by generator tools into ledgers: `claims_ledger.json`, `findings_ledger.json`,
`lever_inventory.json`, `api_inventory.json`, `script_claims.json`,
`tools_of_record.json`. The prose report is
`CONTRADICTIONS_AND_DEAD_WEIGHT.md`. Its §0 precision statement measures the
contradiction finder against five known contradictions and rediscovers two of the
five, so every downstream count is stated as a floor, not a census.

Nothing in the audit folder changed the pipeline; it is evidence. The fixes
happened in the passes below, each committed one script at a time, with the
offline suite re-run green at every batch boundary.

### Passes completed

| Pass | Scope | Result |
|---|---|---|
| **Pass 5 (Q5)** | Every finding in the findings ledger ruled | **405 / 405 ruled** — 381 OBSOLETE, 24 APPLY, 0 WRONG. Every APPLY implemented or its `applied_where` recorded. A positional resume pointer that would have silently skipped 17 findings was caught and fixed structurally (`pass5_extract --skip-ruled`). |
| **Pass 3 reading (Q6)** | Read every pipeline script end-to-end against its own claims | **178 / 178 scripts done (n_pending 0).** ~648 claims-vs-behaviour defects CONFIRMED-at-source and fixed, 41 of them HIGH severity, commit per script. |
| **Pass 2 (Q7)** | 306 engine property levers vs the live 5.8 reflected surface | **Zero live defects** (AUDIT §11). |
| **Suite (Q8 / E-4)** | `run_offline_suite.py` | First fully green suite — **no failures across 29 checks** (now 31 after Brief 4). Consumed-field freshness reconciled; 13 dead-world plans archived to `foliage/_archive/`. |
| **Perf-stall (Q9 / D-5)** | XGE / IncrediBuild dispatcher wedge | Root cause named from both sides: IncrediBuild stopped consuming XGE tasks; the engine dispatcher has no timeout/fallback. `-noxgecontroller` deployed in both consumers; the project is immune via `r.ShaderCompiler.AllowDistributedCompilation=0` (read back on 5 launches). |
| **Status tags (Q11)** | STATUS-tag pass from the Pass-5 rulings | 21 keyed rows, 17 applied, 0 refused. |

### Representative HIGH-severity defects fixed

- NN13 zero-sample fail-opens (checks that returned "agree" over 0 compared values).
- rule-12 read-back gaps (a value written to a structure and never re-read from the engine, reported as controlled).
- Read-back probes that reported `ok:true` over a missing material, zero samples, or empty groups.
- A `set_color_gamma` that read the delivered product back but never compared it.
- A `prove_gaea_reader` whose negative controls passed on ANY crash.
- Two TRELLIS mesh scripts that printed "OK" over an unverified or empty write.
- An HLOD save-cost pilot (`hlod_setup_layers.py`) that had never actually saved.

### Two generated artefacts regenerated with their code fixes

- **`Free/manifest.json`** — `make_asset_manifest` was silently bucketing every unmatched file as "preview"; the fix surfaces 205 files the ambientCG-suffix matcher does not classify.
- **`refs/MANIFEST.md`** — `gen_manifest` hardcoded counts, now derived.

### O-7 HLOD save-cost pilot (2026-09-19, `3440bfc5`)

The Pass-3-fixed `hlod_setup_layers.py` saved 79 packages across all three
classes, 0 failed. Measured per-package save: props ~12 ms (n=17), foliage
~11.5 ms (n=41), landscape proxy ~0.56 s (n=21); whole-world projects to ~3 min,
proxy-dominated. **Locked conclusion: the 2026-09-07 90-minute hang was the BULK
save call, not per-package cost** — one-at-a-time is affordable. The pilot's 79
assignments were fully reverted and the byte-churned OFPA `.uasset` restored, so
the world stayed byte-identical to HEAD. Evidence:
`_verify/hlod/save_cost_pilot_2026-09-19/RESULTS.md`; locked in R-HLOD.

### Audit follow-ups deliberately left open (not defects — scoped work)

- `hlod_build_batched.py` per-batch "did nothing" test uses a whole-world stale metric and can halt a clean batch (OPEN O-7). The section-scoped fix needs a GUID→package map and a live editor.
- `scatter_alpinelab` bare `--clear` does not remove placed instances (only `--place` clears).
- `make_asset_manifest` role matcher covers only ambientCG lowercase suffixes (PolyHaven / Quixel files fall through).
- O-6 (ruling-19 gate) filed then RETRACTED — it was a verifier lag, not a recipe-data decision; `verify_walkable_profile.py` now compares agent vs pawn.

---

## Part 2 — Brief 4 water carve (2026-09-19, FULLY LANDED)

### The gate that preceded it

Ryan ruled every line of the water plan (`research/brief4/RULING.md` §7):
Lake A adopt 180 m, Lake B adopt 140 m, C defer, **D adopt 590.9 m** (top of the
hero cascade), **tarn B ENDORHEIC** (cut 0 m, the 17 m notch struck), hero
landmark = the D-to-tarn stair, waterfall cap 10–15. `CARVE_PLAN.md` turned that
into thirteen ordered tasks T0–T12, each with a read-back and an acceptance,
under restore tag `pre-brief4-water-carve`.

### Tasks, as completed

| Task | What landed | Commit(s) |
|---|---|---|
| **T0** | 5.8 water surface established → **static water meshes** (engine Plane + `M_SideWater`), NOT the UE Water plugin (Experimental, carves landscape by default). Shoreline preview: connected-component areas reproduce hydro exactly. **Finding:** a plane over the hydro bbox over-floods, so each surface clips to the CONNECTED COMPONENT. | `fd77d069`, `38113b8b`, `d03226fe` |
| **T1** | Risky-op checkpoint tag `pre-brief4-water-carve` (green suite, 31 checks). | — |
| **T2** | `recipes/water.json` (schema `water-1.0`); the reserved `water` key lifted with `_validate_water` (endorheic never-exceed ceiling machine-readable); `alpine_8k.json` top-level `water` pointer. All 14 level/extent read-backs exact vs RULING §7. **B inflow = none by MEASUREMENT** (0 of 12 candidates drain into the endorheic tarn). | `c82a3698` |
| **T3** | Carved the 10 north-cascade pool-lip notches into `terrain/alpine_8k.png` (8129², I;16). 47 changed px ⊆ 130 notch cells, 0 raised, z-span 0..1552.485 m. **Finding (rule 10/13): the lips already sit at/near outlet levels — total cut 0.32 m, max 0.20 m.** No town-lip cut (B endorheic). Auditor FIX applied before the write. | `fa7fcebb`, `dc2034be`, `d0475dc9` |
| **T4** | `wet_shore` implemented in `derive_layer_weights.py` (was hardcoded zero): the damp shoreline ring per placed lake, NOT a global elevation band. Positive control reproduces `water.json` areas exactly. `--expand` amended same commit. **Selftest 24/24 + real-data proof; auditor PASS** (4 findings fixed). | `225a2c8c`, `48d46e3d`, `58f46b23` |
| **T5** | Carved 8129 heightmap re-imported (verified 1280 samples worst 0.00; first push died in the transport window, settled UNKNOWN then re-run at 120 s). 288 water actors spawned (277 surface planes clipped to connected components + 11 fall placeholders). Material renders; capture shows lakes at ruled levels. `save_level`: 544 packages, all clean. `check_collision_truth` could-not-measure (~50%) — HLOD proxies intercept the trace (pre-existing, not a carve fault). | `1af43231`, `53170ba3`, `99619184`, `88bd6ea6` |
| **T6** | Navmesh water-carve: 277 NavArea_Null `NavModifierVolume` over all 12 water footprints, saved clean; **navmesh rebuilt** (wall 154 s, peak 29.5 GB, maxTiles 401,843 = R-NAVGRID baseline). Reachability re-measured: **35.32 km²** (navmesh lattice 9810/18496; was 36.53, −1.21 for the water, ≤1.5 target). z-span 0–1552.485, walkable 47.77. **The first read collapsed to 2802 — HLOD proxy collision intercepting the ground trace, REFUSED per rule 13, root-caused, fixed by ignoring `WorldPartitionHLOD` in the trace. The navmesh was never defective — only the instrument.** | `72f6b33b`, `23af1e83`, `b6ca4f0b`, `9b4e30fc`, `baa828ca`, `e51ffb56` |
| **T7** | Bench_ground re-stationed (old station was 115 m under Lake A) → loc [373600, 269600, 77988], bands 354/246 ≥ 160. **Lake A's shore cannot host it** (basin rim fails concavity, best rise 21.4 m) — the ruling wins. An audit found a cm/m + grid bug in the new `--near-*` filter; the committed station used the un-bugged `--exclude-water` path, the filter is fixed and re-verified. | `54178b19`, `b7ba066f` |
| **T8** | Drowned encounters removed: verified set re-frozen **317 → 305** (12 scavengers in Lake A). A derived `water` exclusion npz (191 ha) + `plan_encounters.WaterMask` stop a regen re-drowning. | `ac0dc772`, `19399bd6` |
| **T9** | Foliage regenerated through the planting-field contract + water exclusion. Post-water count re-derived and **RULED: keep density 135/ha, accept the planting field's honest output — 185,385 instances** (was 217,102; the old count was feedback-distorted). Placed + saved: 185,385 counted-in-world == planned, 1094 packages clean. Render weightmap regenerated: **`wet_shore` non-zero for the first time (0.02%)**, 3 lakes reproduce `water.json` exactly, `check_layer_acceptance` PASS. | `d25c6646`, `8c003fe1`, `1b8caeed` |
| **T10** | Freshness reconciled — **`run_offline_suite` no failures across 31 checks.** `restamp_consumed.py` extended for the three carve-induced hash moves. The suite runs `check_plan_freshness --reproduce` (stricter than plain); three residual reds resolved (foliage PRODUCER-REFUSES mapped to benign CANNOT REPRODUCE, `_all` DIFFERS given a `_divergence_note`, `_verified` re-restamped). Now 8 fresh + 2 DIVERGENT-BY-RULING (town_plan, `_all`). Idempotent. | `828e42fa`, `56b9e9d7` |
| **T11** | Perf, 4 zones, all PASS R-PERFBUDGET GPU/Game/Frame p90 (+10% tol); treeline 7.139 ms the only zone over raw budget (7.0), inside tolerance. VRAM peak 5116 MiB vs 13312 abort (+8196 headroom), all zones. `perf_standalone.py` amended to capture VRAM + residency (nvidia-smi + `r.GPUCsvStatsEnable` cross-check + WP streaming-active). | `d2987b5f`, `828e42fa`, `b996a39a`, `e065140a` |
| **T12** | Dirtied HLOD RECORDED, not rebuilt: the re-import re-saved all 256 proxies (landscape HLOD source-stale); 288 water actors dirty the Instanced cells over 191 ha. **Folded into the post-Brief-5 HLOD rebuild.** | recorded in `54178b19` |

### Close-out

LESSONS (HLOD-trace nav corruption + restamp ordering + the owed editor-phase
failures), RECIPES REJECTED (4 entries), R-WATER-CARVE OWED → CLOSED → status
FULLY LANDED, R-NAVGRID HLOD-trace note, doc TOCs regenerated. Throwaway variants
moved to `_trash/brief4_t6_2026-09-19/`. Editor closed on the R-EDITOR-CLOSE kill
path (census 0 + RSS flat + PackageRestoreData absent).

---

## Current spec, post-Brief-4

| Field | Value | Change from pre-Brief-4 |
|---|---|---|
| Terrain Z span | 0–1552.485 m | carve sub-decimetre |
| Walkable | 47.77 km² | was 49.27 (water −1.50) |
| Reachable (navmesh) | 35.32 km² | was 36.53 (water −1.21) |
| Encounters (verified) | 305 | was 317 (12 drowned removed) |
| Foliage instances | 185,385 | was 217,102 (planting-field contract, water-excluded) |
| Water | 288 actors, live + saved on /Game/Alpine8K | new |
| Offline suite | no failures across 31 checks | was 30/31 during the carve |

---

## Forward residuals (parked — NOT blockers)

1. **HLOD proxy collision** — the 2026-09-14 4096 rebuild gave HLOD proxies collision that intercepts vertical ground traces (it corrupted the T6 nav lattice until the payload was taught to ignore `WorldPartitionHLOD`). Deeper resolution is the post-Brief-5 HLOD rebuild (the T12 fold); the dirtied cells are recorded. Any new nav-vs-ground trace on this world must ignore HLOD proxies (R-NAVGRID step 9).
2. **`perf_standalone.py` exposure** — VRAM/residency now captured; exposure read-back still not (small rule-12 residual, non-gating).
3. **REPLAY_BURNDOWN** — 13 UNPROVEN recipes; cold replay is a Brief 5 acceptance.
4. **The town** — the biggest gap remains: 762 engine primitives; the Medieval Village kit is a component kit on disk (2.00 m wall courses, no whole-house meshes).
