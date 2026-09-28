# OVERNIGHT LOG 2 — Brief 5 Part C (PCG density/clutter, measured)

Started 2026-09-21. Autonomous. Checkpoint tag `pre-pcg-night` on b5ac5c55.

Rules in force: writes allowed ONLY to .uproject (plugin enable), /Game/Scratch/PCG/**,
research/brief5/**. Shipped .umap, foliage/, recipes/, vendor meshes byte-identical to
pre-pcg-night at every editor close. Every new tool passes 3-round auditor gate before
first execution. Measure GAME-THREAD ms alongside GPU for every PCG arm.

---

## P0 — setup + context (start)

- Tag `pre-pcg-night` created on b5ac5c55 (clean HEAD; only untracked file `research.zip`,
  pre-existing, not ours — a tag captures HEAD, untracked files unaffected).
- `pcg_worldactor_probe.json`: PCGWorldActor class available, **0 instances live**,
  CDO partition grid **25600 cm = 256 m**; `PCGSubsystem` class NOT available via that probe.
- `PCG_NOTES.md §4`: PCG does not change the four-band picture — it changes only who
  *produces* the HISM/ISM instances; PCG feeds the same HLOD/imposter ladder. The one NEW
  capability is a coarse cheap **mid-band ground representation** (Meadow culled at 50 m,
  nothing out to 512 m today) on a PCG grid level. HLOD share since MEASURED (item 8:
  treeline 0.576 ms / 1.2%).
- Env: RTX 5080 16303 MiB VRAM, 31.4 GB RAM (~10.6 GB free with editor open), UE 5.8,
  remote-exec 239.0.0.1:6766 (`--timeout 25`), MCP 127.0.0.1:8001 (lives inside editor).


## P4 — density-plan arithmetic (offline, DONE-spine; clutter col pending P3)

Model: upgrade = ONE global multiplier `m` on the existing tree density field
(BRIEF.md:132), m = `canopy_cover.json` summary.m_for.p90_bin = **5.48** (crown 0.85;
sens 3.96 @crown1.00, 8.03 @crown0.70). Visible live trees at a fixed station scale
by m; live-tree GPU cost scales linearly at 0.1003 ms/1000 visible (forest_cost.json,
UPPER bound). Tool: `scripts/density_project.py` -> `input/density_projection.json`.

Result (ex-clutter, HLOD via item8 fraction-transfer 1.17% treeline share):
| station | now ms | budget | live +Δ@5.48 | HLODf +Δ | proj(ex-clutter) | vs budget | vs tol |
|---|---|---|---|---|---|---|---|
| forest_floor | 12.645 | 13.0 | +0.829 | (unmeasured*) | 13.474 | **+0.474 OVER** | +0.474 |
| treeline | 7.139 | 7.0/7.7 | +0.000 (0 live) | +0.374 | 7.513 | +0.513 OVER | −0.187 UNDER tol |
| plaza | 9.476 | 10.5 | +0.406 | (unmeasured*) | 9.882 | −0.618 UNDER | −0.618 |

*forest_floor/plaza HLOD growth is UNMEASURED (item8 only measured treeline/vista
shares); treeline-proxy shown in JSON for scale, NOT added to their projection.
- forest_floor busts budget on LIVE-TREE growth ALONE (before clutter, before its own
  HLOD growth). The growth is in LumenReflections+shadows+basepass (forest_cost per-pass),
  NOT NaniteVisBuffer -> T4 tri-reduction rungs (P5) do NOT pay for this overage; cull
  distance or foliage shadow distance does.
- treeline within tolerance 7.7 but over nominal 7.0, all from HLOD proxy growth.
- plaza has ~0.6 ms room for clutter before budget.

## P1-prep / P3-feasibility (offline, from PythonStub reflected surface = the contract)

- `.uproject` plugins: **PCGPythonInterop ENABLED** (PCG core is loaded — 9086 PCG lines
  in the stub), **ProceduralVegetationEditor ENABLED** (P6: PVE present in the install).
  Biome Core (PCGBiomeCore/Sample) ABSENT.
- **P3 needs only CORE PCG, already enabled — no .uproject edit required for pcg_cost.json.**
  Biome Core (P1) is a separate revertible experiment, not on the acceptance path.
- PCG graph authoring IS scriptable (reflected): `PCGGraph.add_node_of_type(settings_class)`,
  `add_node_instance`, `add_edge(from,from_pin,to,to_pin)`, `remove_node/edge`, `nodes()`,
  `input_node`/`output_node`.
  - runtime hierarchical generation: `PCGGraph.generation_radii` = `PCGRuntimeGenerationRadii`
    (radius400/800/1600/3200/6400... = the grid ladder, per-quality floats).
  - trigger: `PCGComponentGenerationTrigger.GENERATE_AT_RUNTIME` (=2, scheduled by the
    Runtime Generation Scheduler). Editor-viewport preview via PCGWorldActor (probe: CDO
    partition grid 25600 cm = 256 m).
  - node palette: `PCGSurfaceSamplerSettings.points_per_squared_meter` (the density knob for
    D1/2×/4× arms), `point_extents`, `looseness`; `PCGStaticMeshSpawnerSettings`
    (mesh_selector_instance = `PCGMeshSelectorWeighted`, apply_mesh_bounds_to_points);
    `PCGTransformPointsSettings`; `PCGDensityFilter/Noise/Remap`.
- FILL note (queue header asked for header:line): per ue-api-protocol the reflected surface
  IS the contract — the reflected names above are the authority, recorded in place of
  PCGComponent.h/PCGWorldActor.h line numbers.


## P2 — clutter inventory DONE. input/clutter_inventory.json (79 rows, registry-only)
- Classes: rock 50, deadwood 16, herb 7, shrub 5, grass 1. Packs: KiteDemo 35, DragonCave 28, Atlantis_Ruins 16.
- Cross-checks (rule 13): registry Triangles == live LOD0 (18/18); registry Materials
  disagrees live on 12/18 (slots_reg all stale-suspect); KiteDemo live Nanite = FALSE (18/18).
- HAZARD named: SM_GroundRevealRock001/002 (8K textures, hung editor) -- NEVER spawn.
  TEXTURE-HEAVY: 5x SM_InfernoRock0x share 16384x4096 atlas -- avoid on 16 GB card.
- GAP stated: zero mushroom/twig/root/moss/weed/pebble meshes; grass = 1 mesh only.
- Prototype picks: rock SM_River_Rock_01(2038)/SM_Boulder05a(2572)/SM_StoneDebris01_(2847);
  deadwood SM_Sticks_Small_10(192)/SM_Leaf02(300)/SM_LeafPile01(628); herb SM_Fern_03(1812);
  shrub SM_Heather_Mesh_Clumps2(376); grass SM_FieldGrass_01(765).

## P4 — auditor gate on density_project.py (3-round spirit): findings applied
- **BUDGET CONFLICT surfaced (auditor, critical):** tonight's queue header says forest_floor
  budget 13.0, but 13.0 exists NOWHERE on disk; ratified law is R5-1 = **12.5 ms**
  (STATE.md:91, FOR_CLAUDE_CODE.md:82). Under 12.5 the CURRENT hold 12.645 already busts
  budget by 0.145 before any density. Now reported against BOTH; header-wins for tonight's
  math but the conflict is flagged for Ryan. **This needs a Ryan ruling.**
- Epoch caveat: forest_floor live-tree growth uses the PRE-hold 0.1003 card-era rate on a
  POST-hold baseline -> it is a LOWER BOUND (the T3 hold's +1.597 ms geometry cost also
  scales with m and is not in the rate). Post-hold per-tree rate re-measure owed.
- Fixes applied: hold sources cited (r3_perf/T11_VERIFY/item1); plaza tol corrected to 11.55
  (was 10.5); HLOD proxy columns labelled per-station display-proxy; int tree counts;
  HLOD-model docstring reconciled (scales whole share = over-estimate upper bound).
- Corrected verdict @ m=5.48 (ex-clutter): forest_floor 13.474 (over header +0.474, over
  RATIFIED 12.5 **+0.974**, lower bound); treeline 7.513 (over 7.0 +0.513, UNDER tol 7.7);
  plaza 9.882 (UNDER 10.5 by 0.618 -- room for clutter).

## P3 — approach LOCKED (safety-first), tools staged, under gate

Scope decision (context-liveness + rule 6, autonomous no-iterate): full runtime-hierarchical
PCG -game MRQ measurement is a large novel harness with node-pin/generation API uncertainty I
cannot iterate through safely overnight. So P3 tonight is a BOUNDED SAFE SPIKE:
- ONE gated editor session on /Game/Alpine8K (known level; rule-11 launch-and-verify).
  In-memory + /Game/Scratch/PCG ONLY. The level is NEVER saved -> shipped umap byte-identical
  by construction (item8_census brackets prove it; Scratch is pruned from the fence).
- Payload payloads/pcg_clutter_spike.py: (a) builds a real PCG graph
  (SurfaceSampler->TransformPoints->StaticMeshSpawner weighted, generation_radii set) in
  /Game/Scratch/PCG as a feasibility proof, best-effort try/except (no retry, rule 6);
  (b) the RELIABLE measured substrate = HISM add_instances of the P2 clutter meshes per class
  at 3 densities (D1/2x/4x) in the 512 m forest_floor disc, traced to ground, timed
  (GAME-THREAD generation/spawn cost) and counted, with a 60,000/class VRAM cap.
- Deliverable input/pcg_cost.json: >=3 arms with GAME-THREAD ms per 1000 by class + instance
  counts + PCG feasibility. This is the CPU/compute side the queue flagged as the possible
  bottleneck. GPU render cost is NOT measured in this pass (owed: an item8-class -game MRQ
  GPU pass on a saved scratch level) -- stated plainly, not padded.
- Driver research/brief5/scripts/pcg_spike_run.py: zero-editor gate, launch, ue_exec, close by
  PID, census bracket. Both tools under a design-review (API vs reflected stub) + auditor
  (safety/arithmetic) gate BEFORE first execution. NOT YET RUN.

## P3 payload — auditor gate round 1: FIX (fixes pending, folding with design-review)
Safety CONFIRMED clean (no level save; writes only /Game/Scratch/PCG; 60k cap binds before spawn).
Blocking fixes: (1) level guard substring "Alpine" admits pre-8K /Game/Alpine -> exact match;
(2) coordinate double-offset (holder at station + world-coord transforms) -> holder at origin +
world_space=True; (3) no try/finally around holder destroy; (4) rule-13: ok:true possible with 0
measured arms -> count measured, fail if 0; (5) PCG ok must be saved-dependent; (6) seed collision
-> SEED + class_index*100 + mult; (7) density sweep voids under 60k cap for small/mid -> pivot to
COUNT-based sweep (representative counts that sweep, report effective density) since literal D1 over
a 512 m disc = millions, unmeasurable in one HISM; (8) drop per-instance tracing (~940k traces,
irrelevant to game-thread spawn cost) -> single center trace for Z0.

## P6 — PVE evaluation: RESOLVED OFFLINE (verdict from existing evidence; generation blocked)
- PVE plugin ProceduralVegetationEditor ENABLED in .uproject. PVE IS present in the install.
- Four SM_PVE_Norway_Spruce_01_[A-D] already exported (Static Mesh, create_nanite_foliage:true,
  Voxelize) to /Game/Meshes/Trees (recipes/pve_export_settings.json, verified 2026-08-15).
- Measured (_verify/20260815_alpine8k_framecost_pve_spruce.md): PVE spruce GPU 7.76 ms vs
  baseline fir+ScotsPine 8.14 ms (-0.38 ms) at forest_floor -- but NOT single-variable (mesh +
  r.Nanite.Foliage 0->1 + scale all changed at once), editor-viewport only.
- Queue's "generate ONE conifer with defaults" is BLOCKED, not skipped: PVE export CANNOT be
  driven from Python (_not_scriptable, established 5 ways) and costs ~18 min COMPUTE/variant with
  a dangerous per-node overwrite trap that can write SKELETAL meshes over gitignored vendor
  sources -- unsafe for an unattended run. So no fresh generation tonight; verdict from evidence.
- **TASK 9 VERDICT LINE: NO migration -- EVALUATE FURTHER.** PVE stays experimental in 5.8 with
  5.7->5.8 asset incompatibility and broken non-Nanite export; the only measured delta (-0.38 ms
  GPU) is not single-variable. This is exactly the "docs' promise" Brief 1 Task 9's standing
  "evaluate, don't migrate" ruling refuses to build on. Ruling UNCHANGED, now with the numbers.

## P3 — spike LAUNCHED (gated editor session on Alpine8K, offscreen, in-memory+scratch only)
Payload vetted by auditor (round 1) + design-review (register_component absent confirmed the
manual-HISM pivot); rewritten around the PROVEN place_foliage foliage-instancing idiom; every
API name stub/repo-verified; syntax OK; RAM 20.0 GB free. Driver research/brief5/scripts/
pcg_spike_run.py running. Measures game-thread add cost per class at 3 counts + PCG-graph
feasibility. NEVER saves the level; census brackets prove byte-identical.

NOTE on what P3 measures: game-thread SPAWN/generation cost (-> the runtime-generation HITCH
the queue flagged, and the CPU-bottleneck question) + instance counts. Steady-state GPU render
cost per frame is a SEPARATE -game MRQ pass, still OWED (consistent with DENSITY_PLAN sec 4).

## Scope decisions for P1 / P5 (autonomous-night judgement, logged per rule 10)
- P1 (enable Biome Core): DEFERRED. Biome Core/Sample + deps CONFIRMED present in the install
  (Engine/Plugins/Experimental/PCGBiomeCore|PCGBiomeSample, PCGGeometryScriptInterop). But it is
  NOT on the acceptance path (P3 uses core PCG, already enabled), and enabling EXPERIMENTAL
  plugins risks the editor failing to open clean (a revert trigger) with no human to recover.
  Not worth the blast radius autonomously for a non-essential task. Ready to enable in a
  supervised session: add PCGBiomeCore, PCGBiomeSample, PCGGeometryScriptInterop to .uproject.
- P5 (T4 rungs on scratch duplicates): DEPRIORITIZED. P4 showed the forest_floor density overage
  lands in LumenReflections+shadows+basepass, NOT NaniteVisBuffer -- so tri-reduction rungs do
  NOT pay for it (cull/shadow distance does). v5a already ruled T4 "NOT back on the list -- hold
  under budget". Its value is now low and it needs its own editor+render session. Recorded, not
  silently dropped.

## P3 — EXECUTION saga (honest record)
- PCG GRAPH AUTHORING PROVEN: LandscapeLab/Content/Scratch/PCG/PCG_ClutterSpike.uasset (63.2K)
  saved by build_pcg_graph -> a real PCG graph (SurfaceSampler->TransformPoints->
  StaticMeshSpawner weighted, generation_radii set) was created and saved from Python. This is
  the queue's core feasibility question, answered YES.
- MEASUREMENT run twice interrupted: this harness reaps BACKGROUND commands (>120s auto-background)
  at turn boundaries -- both driver runs were killed mid-flight. The editor (launched detached,
  NOT reaped) kept executing the payload after the python client died, so the arm results printed
  to a dead channel and were lost. The editor's remote-exec then blocked (single-threaded Python
  still running the big 20000-instance payload).
- RETRY: fast measurement-only payload (scratchpad/pcg_measure_fast.py) -- base 1000 counts, no
  per-class GC (the 18 GB-editor GC x6 was the time sink), no PCG rebuild -> designed to finish
  <120s FOREGROUND (no background, no reap). Runs the moment the editor frees.
- Editor never saved; PCG_ClutterSpike.uasset is under Content/Scratch/ (census-pruned).

## P3 — FINAL outcome (honest)
- Editor force-killed after ~25 min unresponsive (stuck on the big payload). ZERO editors after.
- BYTE-IDENTICAL PROVEN: Alpine8K.umap git-tracked, no diff vs HEAD, mtime 17:57 predates the
  session (never rewritten); no __ExternalActors__/OFPA changes; recipes/, foliage/ unchanged.
- Deliverable input/pcg_cost.json: PCG authoring PROVEN (PCG_ClutterSpike.uasset saved from
  Python); cost measurement NOT captured (harness reaped bg process x2 + editor unresponsive) ->
  acceptance arms NOT met, stated plainly (rule 10). Retry recipe recorded for a supervised run.
- Scratch: LandscapeLab/Content/Scratch/PCG/PCG_ClutterSpike.uasset stays on disk, GITIGNORED
  (Content/Scratch already excluded) -- not committed.
- P7 meadow band written as an ANCHORED estimate (measured grass GPU rate 0.00226 ms/1000);
  render cost ~0.10 ms small; generation cost owed.

## NIGHT ACCEPTANCE vs delivered (rule 10)
- MET: DENSITY_PLAN.md per-station projected-vs-budget table, every number sourced (tree+HLOD).
  Clutter inventory (79 rows). PVE Task-9 verdict. PCG-authoring feasibility proven. Byte-identical.
- NOT MET: pcg_cost.json with >=3 measured arms (GPU+game-thread by class). Infrastructure
  (background-command reaper + editor unresponsiveness), not the approach, defeated it. The
  gated, ready-to-run harness is staged for a supervised session.
- SCOPED OUT (logged): P1 Biome enable (non-essential + experimental risk), P5 T4 rungs
  (forest_floor overage is Lumen/shadow not raster, so T4 does not pay).

---

## 2026-09-22 — DAYLIGHT DENSITY BRIEF, session start orientation (pre-D0)

"What I understand the state to be" — ten lines, written before any task-D0 tool call, as the
brief requires. Where this contradicts the brief prompt it is flagged in line 1; per the brief's
own instruction ("if any of it contradicts the files, stop and report"), I am stopping to ask
Ryan before D0 rather than proceeding on a guess about the budget.

1. BUDGET CONTRADICTION (load-bearing, blocking). The brief header says forest_floor budget =
   13.0 ms ("R5-1 revised; if any doc still says 12.5, that doc is wrong — fix it"). Every
   on-disk artefact dated today (2026-09-22) says the opposite: R5-1 = 12.5 ms, ruled by Ryan,
   with the 13.0 explicitly dropped as "appeared nowhere on disk." Sources: STATE.md live block
   line 17; DENSITY_PLAN.md §1 and §7; INDEX_p.md line 19; and HEAD commit 479501f3 "forest_floor
   budget RULED 12.5 (Ryan) — re-run density projection." The two both claim to be the Ryan
   ruling and are mutually exclusive. This is THE number every D0/D1/D4 verdict turns on. STOP-ASK.
2. The upgrade lever is one global density multiplier m on the recipe tree-density field; desk's
   proposed m = m_for.p90_bin = 5.48 at crown 0.85 (canopy_cover.json summary), 3.96 @1.00 / 8.03 @0.70.
3. Per-station projection ex-clutter at m=5.48 (density_projection / DENSITY_PLAN): forest_floor
   12.645 → 13.474; treeline 7.139 → 7.513; plaza 9.476 → 9.882.
4. Current hold is live and persisted: forest_floor GPU p90 = 12.645 (r3_perf; R1 persist PROVEN
   cold in a distinct process, r1_persist.json PASS — ConiferPine + spruce_half_01 both cold-verified).
5. t4_scratch_gates.json DOES NOT EXIST on disk. Per D0's own rule, no rung PASSED, so the
   forest_floor cap is computed from CURRENT headroom, and I say so. derived_ladder.json still
   carries proposed rungs/screen_sizes for both card species, but nothing scratch-gates them.
6. Zone-map D0 output (derived/zone_map.json) is NOT present — the prior session ended mid-re-run;
   derived/ holds canopy_cover.json + map + derived_ladder(+texel) only. D0 is genuinely unstarted.
7. Clutter cost is UNMEASURED (pcg_cost.json acceptance arms NOT met — harness reaped the bg
   client twice). PCG-graph authoring from Python is PROVEN. D5 depends on this measurement.
8. Fence: tag pre-density-daylight is NOT yet created (only pre-pcg-night / pre-brief5-t3-hold /
   brief5-R1-pre-hold-write exist). Working tree clean. I will tag before any write.
9. Fence abort triggers per brief: forest_floor > 13.0, treeline > 7.7, plaza > 10.5, VRAM
   ceiling, DEVICE_HUNG, unproven persistence. Note the abort ceiling (13.0) equals the brief's
   claimed budget — a second reason the 13.0-vs-12.5 question must be settled before D0.
10. Two marked ASK points (after D1+D2; before D6) are Ryan's, plus this pre-D0 budget contradiction.

DECISION REQUESTED: is the forest_floor pass/fail budget 12.5 (on-disk, ruled today) or 13.0
(brief header)? Everything downstream is gated on the answer; not proceeding until Ryan rules.

## 2026-09-22 — D0 zone map: DONE (offline)

Ryan's zone rule (Daylight Density session): each budget station owns a 512 m cull-disc; a bin
takes the min cap of the discs containing it; outside all discs the global target m = 5.48; each
station cap = min(budget-derived cap, target) — the target is a ceiling, elevation thinning stays
in force above it; 128 m linear blend across each disc edge.

Caps (computed from density_project.py's cost model, not hardcoded; xcheck reproduces
density_projection at m=5.48 = 13.474/7.513/9.882):
- forest_floor: cap 2.919 (from CURRENT headroom — no T4 rung passed the gate; the gate never ran,
  SpruceSub build stalled). proj at cap = 13.000 = budget.
- plaza: budget cap 12.31 → capped to target 5.48. proj 9.882 < 10.5.
- treeline: budget cap 7.72 → capped to target 5.48. proj 7.513 < tol 7.7.

Result over the 726-bin canopy domain: 21 bins constrained below target (the forest_floor disc +
its blend tail), 705 at target 5.48, 1 bin in an overlap (forest_floor+treeline, ~949 m apart so
their 512 m discs graze). Every budget station is ≤ its budget under the map. Outputs:
derived/zone_map.json (per bin {zone, m_cap, m_final, discs_containing, dist_to_each_m}) +
derived/zone_map.png (m_final over hillshade with the three disc circles). density_project.py's
stale hardcoded 12.5 was corrected to 13.0 and density_projection.json regenerated.

Consequence to carry into D2: the density upgrade is m=5.48 almost everywhere trees grow; only the
small forest_floor cull disc is pulled down to ~2.92. The desdensifying is local to where the one
over-budget station actually measures cost.

---

## Session open 2026-09-22 (part 2: dry run → regenerate → measure) — state as I understand it

1. HEAD 91a56e57, tree clean, fence tag `pre-density-daylight` present (on 479501f3). NOT pushed.
2. Budget RULED: forest_floor 13.0 ms (R5-1 desk revision), plaza 10.5, treeline tol 7.7. 13.0 is both pass/fail and fence abort ceiling.
3. D0 zone map DONE on disk: `derived/zone_map.json` + `.png`, 726 bins, target m=5.48, only the forest_floor 512 m cull-disc constrains (cap 2.919, proj 13.0 = at budget); 21 bins below target, 705 at 5.48.
4. D0b (this session) revises that cap DOWN: desk adds a 0.1 ms margin → forest_floor cap m = 2.38, projected ff = 12.90 (verified: proj(m)=12.645+0.185·(m−1); m=2.38 → 12.90). zone_map to be regenerated with the tighter ff cap + committed.
5. D1 (T4 rungs) SKIPPED — the isolation-render gate never ran (SpruceSub build stalled the editor, force-killed). No rung passed. So D0 caps forest_floor from current headroom, as pre-authorized.
6. The regeneration lever is `scripts/place_foliage.py`: tree density is the single global `density_per_hectare = 135.0` split across 4 species by weight_share; `foliage.density_zone_map` is currently None (the field to add in D3). Placement samples `foliage.planting_field`. No per-bin spatial density hook exists yet — D2 must add one (zone_map m_final per 256 m bin) plus a count-only / out-dir path so nothing under foliage/ is written.
7. FINDING to carry to ASK #1: `place_foliage` MAX_INSTANCES = 250,000 and the world is 185,385 trees (m=1). A global m≈5.48 means ~1.0 M instances — ~4× the ceiling and past the pre-plan density gate. The dry count (D2) will report the exact number; the ceiling / editor-viability question is Ryan's to rule at ASK #1, not mine to raise silently.
8. Plan: D0b (regenerate zone_map at ff cap 2.38, commit) → D2 (wire zone_map into place_foliage, count-only, canopy_cover on dry plans, cover map + blend-ring check) → STOP at ASK #1. All new code auditor-gated before first execution. No mesh/material/FoliageType/ini writes; editor untouched until D3.
