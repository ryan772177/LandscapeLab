FIRST, before Orient: save this entire prompt verbatim as
research/brief7/BRIEF7_THE_LOOK.md, and add R-LOOK-1 and R-ROCKS-BACK
(one line each, as stated under NEW SINCE LAST PROMPT) to the STATE.md
live block, so the DESK_HANDOFF pointer resolves. Commit on main:
"brief7: the look — spec + rulings".

BRANCH RULE for this brief: Phase 0 runs on main as written. Any script
change in Phase 1 (make_landscape_material.py, recipe schema, grass
types) is authored on branch look-p1-material, pushed, PR opened — then
STOP and report the PR number; do not run it against the world until
Ryan says "merged, go." Same for Phase 3's regen/PCG driver on branch
look-p3-driver. Ryan runs an external review on each PR in between.BRIEF 7 — THE LOOK. Target: Electric Dreams-grade alpine environment
(Ryan's stated goal: FF16 / FF7 Remake-level look). Fresh session.
Phase 0 tonight with a stop; Phases 1–4 as an overnight queue with a
checkpoint tag per phase; stop at the morning stills.

════════════════════════════════════════════════════════════════════
ORIENT (before any write)
Read STATE.md, LESSONS.md, REGISTER.md, BACKLOG.md,
research/synthesis/INDEX_synthesis.md + SYNTHESIS.md,
research/forensics/spikes.md, research/census/ (Electric Dreams values),
research/DESK_HANDOFF.md and research/DESK_HANDOFF_2026-09-10.md if
present (if absent, note it and continue), git log --oneline -15,
git status. Write an 8–10 line "state as I understand it" into the log.
Contradiction with the files → stop and report.

════════════════════════════════════════════════════════════════════
NEW SINCE LAST PROMPT
- Rulings in force: R-AESTHETIC-1 (ms budgets suspended; perf recorded,
  not gated; visual gate = Ryan on stills). NEW R-LOOK-1: the bench PPV,
  bench profile and benchmark.json are untouched; the game gets its own
  PPV_Look and a Look profile, graded, judged on stills; the two never
  share an actor. NEW R-ROCKS-BACK: "minus the rocks" is rescinded; the
  August rock species return. Hard stops that remain: VRAM 13,312 MiB,
  DEVICE_HUNG protocol, persist protocol, tag-before-write, fence.
- Desk read the full research/ tree + recipe. Facts from the recipe: all
  rock species were removed at the 8K re-terrain; GroundClutter was
  removed in the same edit by CC's call, not Ryan's; displacement
  amplitude_m 0.4 predates the Brief 3 16-bit height maps; R-TILE tile
  sizes (Rock 1.80 / Scree 2.00 / ForestFloor 2.14) are in the recipe
  but never reached the material graph.
- CORRECTION to SYNTHESIS.md §0: the pre-exposure warning is a LIVE
  DEFECT, not a misread. The 9/12 "pre-exposure 4→16 bit-identical" null
  ran at exposure −4.1 EV; the A-6 solve moved the scene to −14.2571.
  Record it as a regression-class defect owned by this brief.
- Doc-derived changes (dev.epicgames.com): Local Exposure is to be set up
  whenever Lumen GI is used; height-blend on every layer produces black
  holes, so one layer stays weight-blend; side-lit volumetric light
  shafts need scattering distribution near 0.

════════════════════════════════════════════════════════════════════
LEVERS CHECKED — every row verified against dev.epicgames.com (5.8
unless marked); local 5.8 header wins on any contradiction; FILL =
header:line CC supplies before that phase runs

| lever | source | verdict |
|---|---|---|
| r.EyeAdaptation.CachedLightingPreExposure (live 4; scene EV 14.3; warning names Lumen/sky-capture clipping) | header:line FILL; doc: auto-exposure-in-unreal-engine | P0 — raise so the cached range covers EV 14–15; warning must clear in -game |
| PPV_Look Exposure: Manual metering kept, comp from the sun rule; ADD Local Exposure (Lens > Local Exposure) | doc: auto-exposure-in-unreal-engine ("Local Exposure … should always be set up when using Lumen Global Illumination") | P0 |
| PPV_Look Color Grading: white_temp / white_tint, contrast (ColorContrast xyz=1, w=value per B3.13), saturation; ACES filmic tonemapper unchanged | doc: color-grading-and-the-filmic-tonemapper-in-unreal-engine; names: python-api/class/PostProcessSettings (5.7 page — confirm in live stub) | P0 — start WB = sun K + ~1000 (ED 5600), contrast 0.87–0.92 |
| PPV_Look Bloom: Convolution method, bloom_convolution_intensity, dirt mask | python-api/class/PostProcessSettings (bloom_convolution_*) | P0 — 0.4, dirt low |
| PPV_Look film grain, vignette | same page | P0 — grain ≤ 0.5, vignette ≤ 0.4 |
| DirectionalLight light shafts (bloom + occlusion) | property names FILL from live stub; component header:line FILL | P0 |
| ExponentialHeightFog: volumetric ON, scattering distribution 0.1–0.3, extinction ~1.0, view distance ≥ 6 km, start 0; inscattering colours stay black (atmosphere-coupled, AUDIT P1-3 CONFIRMED) | doc: exponential-height-fog-in-unreal-engine (Volumetric Fog table) | P0 |
| VolumetricCloud: layer_bottom_altitude 2.0 km, layer_height 1.5 km, coverage 0.1 with read-back (owed since Brief 2) | doc: volumetric-cloud-component-properties-in-unreal-engine; python-api/class/VolumetricCloudComponent | P0 |
| Landscape displacement PER LAYER: Magnitude + Center on each layer's height input; ground scans 0.03–0.06 m, Rock 0.15–0.25 m, Snow 0.02 m; tessellation stays ON; r.Nanite.MaxPixelsPerEdge unchanged | doc: using-nanite-with-landscapes-in-unreal-engine + nanite-virtualized-geometry-in-unreal-engine; Magnitude/Center semantics per API NaniteUtilities FDisplacementMap (5.6 page) — header FILL | P1 — recipe gains displacement.per_layer; the global 0.4 retired |
| LandscapeLayerBlend: Rock / Scree / ForestFloor / Snow = LB_HeightBlend with each layer's 16-bit height; Meadow (remainder) = LB_WeightBlend | doc: landscape-materials-in-unreal-engine (blend types + black-spot warning); API: ELandscapeLayerBlendType | P1 |
| R-TILE tiles into the graph via LandscapeLayerCoords Mapping Scale per layer | doc: landscape-material-expressions-in-unreal-engine | P1 |
| GroundClutter LandscapeGrassType on the Grass output: boulder_small 0.6 / river_rock 0.4, 10 per 10 m², cull 40 m, AlignToSurface, contact shadow ON | API: FGrassVariety (LandscapeGrassType.h); doc: grass-quick-start-in-unreal-engine; RECIPES.md §6d (ratified 08-08) | P1 |
| Nanite on rock/cliff/talus static meshes, verified by Nanite DATA not the flag | doc: API/Editor/StaticMeshEditor/UStaticMeshEditorSubsystem (5.5 page); nanite-virtualized-geometry | P2 |
| Rock species on the deposition field: Boulder / CliffOutcrop(B) / CliffFace / TalusField A–C / TalusChannel / TreeStump | RECIPES.md rocks section + rock_scatter.py (project source of record) | P2 |
| Fab/Megascans cliff + boulder assets, only where the August meshes fail the still | ASSETS.md licence row required first | P2 |
| Density lift plaza (cap 2.157), treeline/vista uncapped; forest_floor m=1 | zone_map.py + t4_recalibration.json | P3 — visual-gated, VRAM only |
| PCG runtime hierarchical grid: meadow grass to 512 m; clutter on three grid sizes; Nanite clutter cull 0 (ED) | docs: runtime-hierarchical-generation, using-pcg-generation-modes, pcg-biome-core reference + quick start (5.8, per PCG_NOTES v3) | P3 |
| Lumen Far Field for the HLOD band (r.LumenScene.FarField), ray tracing on proxies; Software RT stays | doc: lumen-technical-details + lumen-performance-guide; cvar header:line FILL | P4 — one vista A/B still |
| HLOD rebuild, changed cells only | doc: world-partition---hierarchical-level-of-detail-in-unreal-engine | P4 |
| Look profile: sg.* Cinematic/Epic at 4K, TSR; bench profile untouched | doc: scalability-reference (5.8, per Brief 5 baseline audit) | all phases |

Fill every FILL from local 5.8 headers / the live Python stub before its
phase. Header contradicts doc → header wins, skip that lever, report.

════════════════════════════════════════════════════════════════════
FENCE
Tag `pre-look` before the first write. Each phase commits and tags
`look-p<N>`. May write: Config/DefaultEngine.ini (the pre-exposure line
only); a NEW PPV_Look actor + Look profile; DirectionalLight / fog /
cloud fields named above; landscape material + weightmap + grass types
(with `_SRC` duplicates per R5-3); recipe; rock species + placements;
foliage plans + __ExternalActors__; PCG assets; HLOD; research/brief7/;
.gitignore (Phase 0 only); LESSONS / STATE / REGISTER / BACKLOG.
May NEVER: touch the bench PPV, bench profile or benchmark.json; delete
`_SRC`; rewrite git history; exceed VRAM 13,312 (auto-revert to the last
look-p tag); continue after a second DEVICE_HUNG. `R-EDITOR-CLOSE` after
every editor pass.

════════════════════════════════════════════════════════════════════
PHASE 0 — housekeeping, read-backs, light. (tonight, ~2 h) → ASK L0

0a Evidence (10 min). If not already tracked: remove from .gitignore
   research/brief5/derived/d3_verdict.json, .../d3_run.log,
   _verify/perf/standalone_2026-09-22/*.csv; git add; commit
   "evidence: track D3 verdict, run log, raw perf CSVs". Write the D3
   editor-peak VRAM (5,211 MiB) to a JSON under research/brief5/.../input/
   or mark it U in REGISTER. REGISTER: min_detectable is per build
   (forest_floor 0.074 on dcc664f3; 0.016 on v3).
0b Read-backs (20 min, live editor, no save) → research/brief7/p0_readback.md:
   every PostProcessVolume (metering, compensation, min/max EV100,
   unbound, priority); every DirectionalLight (enabled, lux, K —
   the 8/27 "four suns" question: how many exist now); SkyLight
   intensity + colour; fog density/falloff/start; Mie; cloud coverage;
   the landscape material as built: layer list, per-layer Mapping Scale
   vs recipe tiling_m, displacement inputs per layer (texture,
   Magnitude, Center), GrassOutput types bound (names, varieties,
   densities, cull). Table per item: ruled | current | match.
0c Pre-exposure (10 min). Set r.EyeAdaptation.CachedLightingPreExposure
   so the cached range covers EV 14–15; persist protocol on the ini; one
   -game launch: acceptance = the on-screen clip warning is GONE.
0d PPV_Look (60 min). New unbound PPV, priority above the bench PPV,
   enabled only under the Look profile: Manual metering, comp from the
   sun rule; Local Exposure ON (highlight/shadow contrast ~0.8); WB =
   sun K + ~1000 with tint 0; contrast 0.90 (xyz=1, w=0.90); Convolution
   bloom 0.4 + low dirt; grain 0.3; vignette 0.3. Sun: light shafts
   bloom + occlusion ON. Fog: volumetric ON, scattering distribution
   0.2, extinction 1.0, view distance 6 km, start 0. Clouds: 2.0 km /
   1.5 km, coverage 0.1, read back. Persist protocol on every actor.
0e Stills (20 min). Player instrument, judge camera: near_ground + vista
   + the slope station from the 9/22 screenshot, each as bench-profile
   vs Look-profile pairs. research/brief7/stills/p0/. Commit, tag
   look-p0. STOP → ASK L0: Ryan rules warmer/cooler, more/less contrast,
   shafts yes/no, in one line each. Carry his lines into P1–P4.

════════════════════════════════════════════════════════════════════
PHASE 1 — ground. (overnight block 1)
- Recipe: replace material.displacement.amplitude_m 0.4 with
  displacement.per_layer {Snow 0.02, Rock 0.20, Scree 0.06, ForestFloor
  0.04, Meadow 0.03} + center 0.5 (schema bump, validator refuses the
  old global key). make_landscape_material.py rebuild: R-TILE Mapping
  Scale per layer; LB_HeightBlend on Rock/Scree/ForestFloor/Snow with
  their 16-bit heights, Meadow LB_WeightBlend; GroundClutter grass type
  back on the Grass output per §6d; existing Meadow + Blueberry types
  preserved. `_SRC` first. Persist protocol (mtime + sha + cold readback
  in a second editor process; the make_foliage_material empty-name
  lesson applies — read back against the dirty-package census).
- Build Texture Streaming.
- Stills: slope station + near_ground + a forest-floor crop, Look
  profile. Acceptance: no per-vertex shards on the slope; scree and rock
  read as mass; small rocks visible in the meadow; no black seams at
  layer boundaries (the height-blend failure). Any acceptance fails →
  revert that one asset from `_SRC`, record, continue.
- Commit, tag look-p1. Log forest_floor ms once, unremarked.

════════════════════════════════════════════════════════════════════
PHASE 2 — rocks. (overnight block 2)
- Re-enable the August rock species in the recipe (R-ROCKS-BACK):
  Boulder, CliffOutcrop, CliffOutcropB, CliffFace, TalusField A/B/C,
  TalusChannel, TreeStump, at their last ratified densities, on the
  deposition field; water + settlement exclusions applied; pivot gate
  (base-centred) on every mesh; RNG-by-index hazard noted (LESSONS
  08-08) — placements are new, so no re-roll issue.
- Nanite on all rock meshes, verified by Nanite DATA (triangle counts in
  the built data), not the flag. Note the Aug-9 lesson: Nanite replaces
  LOD0 with a reduced fallback — confirm r.Nanite is on in the Look
  profile.
- Fab/Megascans cliff + boulder assets ONLY if the August meshes read
  worse than the target on the still; licence row in ASSETS.md before
  import.
- Stills: vista + a cliff station + talus at 30 m, Look profile.
  Acceptance: cliffs read as rock at the vista; talus sits on the
  deposition field, not a slope band.
- Commit, tag look-p2. VRAM peak logged.

════════════════════════════════════════════════════════════════════
PHASE 3 — forest + dressing. (overnight block 3)
- Density: zone map with forest_floor cap 1.0 (m=1), plaza cap 2.157,
  treeline/vista uncapped at the global target; dry-run counts; regen
  via the existing D3 driver with the VRAM guard only (no ms gate).
- PCG runtime hierarchical graph: meadow grass to 512 m on the fine
  grid; clutter three classes (large rocks/deadwood, mid shrubs, small
  stones) at Electric Dreams-style densities, forest zones first, Nanite
  clutter cull 0. Halve the smallest class if -game forest_floor exceeds
  40 ms or the editor viewport stutters on orbit (subjective; log it).
- Stills: forest_floor + plaza + treeline, Look profile.
- Commit, tag look-p3. VRAM peaks + one perf number per station logged.

════════════════════════════════════════════════════════════════════
PHASE 4 — far field, HLOD, package. (morning)
- Lumen Far Field on, ray tracing on HLOD proxies: ONE vista A/B still;
  keep if the far slopes gain shading, drop if not.
- HLOD rebuild for changed cells (count first; batches ≤ 96 per S-9).
- Five stations + slope + cliff, `pre-look` vs `look-p4`, Look profile.
- research/brief7/INDEX_look.md leading with: what changed per phase,
  VRAM peaks, one perf number per station, what was skipped and why,
  every FILL that stayed FILL. LESSONS two-altitude. STATE live block.
  BACKLOG: town (wall-course kit, needs house meshes), hero groom/outfit
  (parked with their handoffs), caves.
- Push main + tags. STOP → ASK L4.

The bench never changes in this brief. Any bench measurement taken
before and after must agree; if one moves, stop and report.
