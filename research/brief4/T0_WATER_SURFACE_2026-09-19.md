# CARVE_PLAN T0 — the UE 5.8 water-implementation surface (established 2026-09-19)

**T0's question (CARVE_PLAN.md:17-20):** Water plugin vs static water meshes for the
three lakes + the cascade + the placed falls. Establish every API/property by the
reflected-surface rule before any call; the plan names none.

**DECISION: STATIC WATER MESHES** — engine primitive `/Engine/BasicShapes/Plane`
scaled to each lake bbox, material `/Game/Materials/M_SideWater`, placed as a
`StaticMeshActor` at the water-level Z. **NOT the UE Water plugin.** Drafted
recipe: `research/brief4/water_recipe_DRAFT.json`.

## What was established (live, not quoted)

**Reflected surface** — from the this-build PythonStub (`LandscapeLab/Intermediate/
PythonStub/unreal.py`, regenerated 2026-09-19 08:16) and a live read-only probe
(`scripts/payloads/_t0_water_probe.py`, rule-7 MATCH):

- **Water plugin classes ARE loadable at runtime** in this build — `WaterBodyLake`,
  `WaterBodyRiver`, `WaterZone`, `WaterBrushManager` all resolve; `WaterBodyLake`
  is a class. So the earlier stub-vs-uproject contradiction resolves to *available
  but not formally enabled*, not *absent*.
- **Maturity tier: EXPERIMENTAL v0.1** (`C:\Program Files\Epic Games\UE_5.8\Engine\
  Plugins\Experimental\Water\Water.uplugin`: `EnabledByDefault false`,
  `IsExperimentalVersion true`, `VersionName "0.1"`; deps Landmass, Niagara,
  GeometryProcessing). NOT listed in `LandscapeLab.uproject` (19 plugins, none water).
- **The plugin CARVES the landscape by default** — `WaterBody` docstring: water
  bodies "automatically create meshes, **carve landscapes**, and support physics";
  `WaterBodyComponent.affects_landscape`: "landscape will be deformed based on this
  water body". Can be set False, but that is fighting the plugin.
- **The plugin is SPLINE-AUTHORED** — `WaterBodyType.LAKE` = "a close loop spline
  around the shore"; `RIVER` = "a spline down the middle". The body's shape is a
  hand-authored `WaterSplineComponent`, i.e. editor state.
- **Static path assets, confirmed live:** `M_SideWater` = Material,
  `MD_SURFACE` / `BLEND_TRANSLUCENT` / `MSM_DEFAULT_LIT`, two_sided False (a valid
  translucent water-surface material). `/Engine/BasicShapes/Plane` = StaticMesh,
  100x100 cm quad (extent 50), centre pivot → scale_xy = extent_cm/100.
- **The placement tool already exists** (operating-loop step a): `scripts/
  spawn_water_plane_payload.txt` spawns a Plane StaticMeshActor with `M_SideWater`
  at a declared water-level Z ("water is flat"), idempotent by label, with dry-run.

## Why static meshes, not the plugin

1. **Maturity.** Enabling an Experimental v0.1 plugin (+ Niagara/Landmass deps) on a
   machine with a DEVICE_HUNG history, for a grey-box blockout, is disproportionate
   risk. (Protocol: state the maturity tier — this is the lowest.)
2. **It carves the landscape.** The plugin's default terrain deformation collides
   head-on with standing rule 4 (heightmap edited off-disk via the pipeline, never
   editor sculpt) and the CARVE_PLAN §0 premise ("lakes are fill-to-level of
   existing terrain — no carve creates their depth").
3. **It is spline-authored, so not recipe-driven.** A closed-loop shore spline is
   editor state that does not survive a deterministic rebuild — violating pipeline
   rule 2 (every scene parameter from recipe JSON) and rule 3 (idempotent rebuild).
   The lake shape must come from the terrain + level, not a hand-drawn spline.
4. **The static path is already built and recipe-shaped** — `spawn_water_plane_
   payload.txt` (Plane + `M_SideWater`, flat at a declared Z, idempotent, dry-run).
   Fill-to-level BY CONSTRUCTION. Same fidelity tier as the town (engine Cubes).
5. **The shoreline read is carried elsewhere.** The landscape material's `wet_shore`
   channel (unlocked in CARVE_PLAN T4) draws the shoreline on the terrain,
   independent of the water renderer — so the plane's lack of foam/depth-fog is not
   a shoreline gap for the blockout.

**Geometry/levels are UNCHANGED by the choice** (T0 acceptance): water renders at the
§7 levels (A@180, B@140, D@590.9, cascade pools) either way. The plane approach
places a flat quad per level; the shoreline is the terrain contour at that Z.

## Limits recorded (rule 10) — honest gaps of the static approach

- **No native waterfall.** Falls (incl. the hero D→tarn cascade, §7 #6) have no
  static-plane form that reads as *falling* water. Blockout places falls as DATA +
  minimal vertical `M_SideWater` plane placeholders; proper cascade FX (Niagara /
  WaterAdvanced) is deferred to a fidelity pass → BACKLOG.
- **Underwater view** shows through the one-sided plane (two_sided False). Acceptable
  at blockout; B's 140 m shaft is a Brief-6 hook anyway.
- **Rectangular plane vs contour — MEASURED, and the "tight bbox" assumption was
  WRONG for D (rule 10).** A plane sized to the hydro bbox over-floods: D@590.9 is
  98.7 ha over its bbox vs the true connected 49.6 ha (2x — the bbox includes the
  cascade descent below 590.9); A@180 is 134.8 vs 125.5; B@140 matches (13.6, tight).
  So T2/T3 must size/shape each water surface to the **connected component** at the
  level, not the bbox (draft recipe `_placement_MUST_clip_to_connected_component`).
  Confirmed by the shoreline preview, whose connected-component areas reproduce
  hydro EXACTLY (positive control). Evidence: `_verify/brief4/shoreline_preview_2026-09-19/`.

## T0 acceptance check (CARVE_PLAN.md:20)

- Named approach: **static water meshes** ✓
- Full API surface established LIVE (not quoted): reflected stub + live probe of the
  plugin classes, `M_SideWater` levers, and the Plane mesh ✓ (the placement API is
  `StaticMeshActor` + Plane + material — the most-proven path in this repo, the whole
  town is placed this way)
- Geometry/levels unchanged by the choice ✓

## Open for Ryan — the ONE reserved aesthetic (RULING §5.2, CARVE_PLAN OPEN CHOICES)

With static meshes the shoreline shape is **not** a free parameter — it is the terrain
contour at the fixed §7 level (A@180, B@140). A different shape would require either a
different level (fixed by §7) or carving (forbidden by the fill-to-level premise). So
the question reduces to: **preview the A@180 / B@140 shorelines before the carve
commits, or proceed?** A preview is cheap offline (a hillshade thresholded at the level
from `terrain/alpine_8k.png`) and does not need the carve. Falls-FX deferral (above) is
recorded as a blockout limit, not a blocking question.
