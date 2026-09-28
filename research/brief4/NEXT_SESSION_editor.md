# Brief 4 CARVE_PLAN — THE EDITOR PHASE (T5–T12) — session prompt of record

> Handoff prompt for the 2026-09-19 editor-phase session, committed for
> provenance. The contract of record for per-task read-backs and acceptance
> remains `research/brief4/CARVE_PLAN.md`; this file carries the locked
> decisions so the session does not re-litigate them.

T0–T4 + T8-detection are DONE and committed; this session executes the editor
cascade that places the water.

## Start-up (context-loading protocol)

1. Read CLAUDE.md (operating loop + standing rules), then STATE.md — the LIVE
   block is the "2026-09-19 (T4)" one at the top, with the CARVE SESSION block
   below it. Then read research/brief4/CARVE_PLAN.md — it is THE CONTRACT for
   T5–T12 (each task's read-backs + acceptance + the restore tag). Grep
   RECIPES.md before inventing any procedure (operating loop step a; scripts/
   is a SEARCH, not a recall). Load docs/environment.md (the two ROOTS) and
   docs/ue58-api-protocol.md before any editor/API call.
2. State the session goal in one line before touching anything.

## The two gates that bite this phase — do not skip

- Rule 11: wait for ZERO editors, launch ONE clean offscreen editor, then
  CONFIRM the loaded level is /Game/Alpine8K before any shot or mutation. A
  plausible artefact from the wrong level passes every tonal check.
- Rule 7: verify the connected editor matches UE_PROJECT_ROOT
  (C:\Users\Admin\UE5LandscapePipeline\LandscapeLab) before any remote exec.
- Rule 4 (no direct .uasset/.umap writes — editor-side via the UE Python API),
  rule 8 (dry-run destructive ops; identify by property signature, labels
  collide — two landscapes share proxy labels), rules 12/13 (a declared value
  is prose until APPLIED and READ BACK; every comparison reports its sample
  count and a zero count REFUSES).

## Decisions already locked — do NOT re-derive

- STATIC WATER MESHES (engine Plane /Engine/BasicShapes/Plane.Plane +
  /Game/Materials/M_SideWater at the water-level Z), via the
  scripts/spawn_water_plane_payload.txt pattern. NOT the UE Water plugin
  (T0 decision, research/brief4/T0_WATER_SURFACE_2026-09-19.md). T0 established
  the surface live (scripts/payloads/_t0_water_probe.py).
- Water set (recipes/water.json, schema water-1.0): A@180 id4893 (closed),
  B@140 id11877 (ENDORHEIC, 180 m never-exceed — the town sits in its full-fill
  footprint), D@590.9 id8377; north cascade D→tarn B (hero landmark); 11 placed
  falls in the 10–15 cap. Lake C (6587) is DEFERRED — not placed.
- CLIP each water surface to the CONNECTED COMPONENT, not the bbox — the bbox
  over-floods (D reads 98.7 ha over bbox vs 49.6 connected). Footprint masks:
  hydro_derive.level_slice on the committed 4x heightmap; the T4 evidence dir
  (_verify/brief4/t4_wetshore_2026-09-19/) and water_derive reproduce the areas.
- The carve is DONE: terrain/alpine_8k.png carved (T3, 47 px, sub-decimetre).
- Water level Z world_cm = level_m * 100 (do NOT add landscape_location z; that
  spelling is superseded/WRONG — water.json _placement).

## The cascade (open CARVE_PLAN.md for each task's exact read-backs + acceptance)

- T5  Re-import the carved heightmap; place the water plane meshes (clip to
      connected component); re-apply material; run scripts/capture.py (pipeline
      rule 4 — capture after a scene change).
- T6  Navmesh rebuild (water non-walkable) + reachability re-measure (z-span
      0–1552.5 m and 36.53 km² BOTH go stale) + T8 removal/re-freeze: 12
      encounters sit inside Lake A's §7 footprint (all scavenger, 11 below 180 m;
      #308 borderline shoal 180.7 m) — remove/re-freeze, add a `water` exclusion
      to encounters.json + the placer. Detection evidence:
      _verify/brief4/encounters_in_water_2026-09-19/.
- T7  Re-station Bench_ground on A's 180 m shore.
- T9  Foliage regen — re-derive the ±2%/−20% band for the post-water world
      FIRST. NOTE: regenerating the weightmap here (derive_layer_weights.py) will
      produce a NON-ZERO wet_shore for the first time in the shipped w8b; the T4
      code + --expand handle it (wet_shore folds into the remainder, shipped PNG
      byte-identical), but downstream consumers (derive_planting_field,
      ground-station tools, check_layer_acceptance) will read the new channel —
      re-verify them.
- T10 Freshness reconciliation (town plan re-rule/restamp) — this CLEARS the one
      suite red (currently 30/31: the T2/T3 cascade against terrain/alpine_8k.png
      + alpine_8k.json hashes). Reconcile against the FINAL post-cascade hashes.
- T11 Perf, 4 zones, with -noxgecontroller (R-XGE).
- T12 RECORD the dirtied HLOD cells — do NOT rebuild.

## Cross-cutting

- Any new/changed code goes to the auditor BEFORE first execution, and the audit
  request MUST state REPO_ROOT (C:\Users\Admin\UE5LandscapePipeline) and
  UE_PROJECT_ROOT (…\LandscapeLab) at the top — the auditor blocks without them.
- Two-altitude logging on every failure (LESSONS narrative + RECIPES REJECTED),
  in the same commit, before the retry.
- OWED: lock R-WATER-CARVE in RECIPES.md once the whole carve lands.

## Done means

The carved heightmap is live, water planes placed and captured, navmesh +
reachability re-measured, T8 encounters resolved, Bench_ground re-stationed,
foliage regenerated, the suite GREEN (T10), perf recorded, HLOD dirtied-cells
recorded, R-WATER-CARVE locked, STATE.md updated, tree committed clean.
