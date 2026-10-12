# PCG Shape Grammar trial: one block (2026-10-10, Ryan: "go ahead with the 5.8.3 update and the Shape Grammar trial")

Status: DESIGN, pre-review. Nothing built. Source of the idea: `C:\Users\Admin\UE58_TownFrom2D\docs\RESEARCH_PLAYBOOK.md`
§6.1-6.6. Its claims are [V] verified or [I] inferred; every node and property name below is to be read from the 5.8.3
stub or headers before use (docs/ue58-api-protocol.md), never from the playbook.

## The question the trial answers

**Does a PCG Shape Grammar facade, driven from OUR kit, beat the current Python-assembled kit houses on building
variety, enough to justify an editor-coupled PCG stage in a pipeline that is otherwise offline, deterministic and
recipe-driven?** The answer is a yes or no with evidence, not a migration.

Today: `town_kit_plan.py` / `town_kit_manifest.py` assemble every house from 17 modules. Each storey is a ring of
2 m courses, plus corners, one door and a fitted whole roof. Every house has the same rhythm, and the stills read as
near-identical boxes.

## Kit vocabulary available (on disk, `/Game/Megascans/3D_Assets`, measured in `Free/_measured/kit_medievalvillage_v2.json`)

| role | modules |
|---|---|
| walls | Wall1x2MA, Wall1x2MB, Wall15x2M, Wall2x2MD, Wall2x2MG, Wall2x2MH, Wall3x2M |
| doors | Door1x2M, Door15x2M, Door2x2MA, Door2x2MB, Door3x2M |
| corner, gable | CornerWall1x2M; Gable4, Gable4M |
| beams | SupportBeamA/B/D/E, WoodenBeam, WornWoodenBeamA (jetty brackets, eave beams) |
| roofs | House02/03/07/08 roofs (whole), Shingles |

Not in the kit: dedicated window or shopfront modules. The 2x2 wall variants carry their own openings, so
"variety" means the sequence and the choice of variant, storey count, jetties and roof choice. It does not mean new
geometry.

## The trial

**Level.** A NEW scratch level `/Game/Scratch/SG_Trial`, a flat plane under the Alpine8K lighting recipe.
- Never `/Game/Alpine8K`, and nothing is saved into the world.

**Block.** One street front of 8 footprints taken verbatim from the shipped plan: the 8 houses nearest the
`street_lane_s` camera, so the comparison has a real reference frame.
- Same footprints (W x D, yaw), same doors, laid flat. The trial tests facades, not terrain.

**Arm A (control).** The current kit builder, the same pieces as the manifest rows for those 8 houses.

**Arm B (grammar).** PCG Primitives' Shape Grammar on the same footprints. The playbook's route (§6.3, option 1)
is `Assign_ShapeGrammarDefinition` with BP_ShapeGrammarRule / BP_ShapeGrammarDefinition data assets, started from
`SGD_Bldg_Demo`.
- **Modules.** Ours, sizes from `get_bounds` (Epic skill rule: "always call get_bounds before setting size").
- **Ground floor (front).** `C,{[W2D]:2,[W2G]:1,[W2H]:1}*,[DOOR],{[W2D]:2,[W2G]:1,[W2H]:1}*,C`
- **Upper floor.** The same weights, plus a jetty variant: storey 2 offset outward by one beam depth, with
  SupportBeam brackets.
- **Side walls.** `C,{[W1A]:1,[W1B]:2,[W15]:1}*,C`
- **Storeys.** 2-3 by a seeded weight; roof = the current fitted whole roof (PCG ships no pitched roof, §6.5).
- **Determinism.** The grammar output is baked (`clear_pcg_link` or a static ISM bake) and read back as an instance
  list. Two generations with the same seed must give the same instance list. This is the determinism gate the
  rest of the pipeline already holds.

**Measured, both arms.**
- Distinct module sequences per facade.
- Facade-rhythm entropy.
- Instance and triangle counts.
- Build time.
- The same-pose still (Arm A vs Arm B, 8 houses, 2 views).
- Determinism: two runs give byte-identical instance lists.
- Recipe-drivability: every grammar string and weight comes from a recipe JSON block, set through
  Python/PCGToolset, and no hand-edited asset.
- Editor coupling: which steps need the editor UI, if any.

**Not in scope.** Any change to Alpine8K; Polygon2D lots; street-facing lot generation (that is the next step if
the trial wins); new geometry; image-to-3D.

## AI-input licence

The kit is AI-restricted (`recipes/ai_restrictions.json`). Grammar assembly involves no AI model, so the trial is
clean. The trial stills show the kit, so they are refused by the guard and must never be sent to a model, and the
guard's render_globs gain `_verify/sg_trial/**`.

## Prerequisites (operator and tooling)

1. **Engine 5.8.3** (operator, Epic Launcher). Fixes Polygon Operation losing Data-domain attributes and integer
   attribute drift in spline sampling (playbook §1); neither is in this trial's path, but the update is the
   ruled baseline.
2. **PCGPrimitives enabled for the project.** It is not EnabledByDefault. The .uproject is written by the ENGINE
   via the new `LandscapeLabTools.SetProjectPluginEnabled` (standing rule 4). Then restart, and read back with
   `PluginBlueprintLibrary.is_plugin_mounted("PCGPrimitives")`.
3. **Post-update smoke.**
   - LandscapeLabEditor rebuilt against 5.8.3;
   - bootstrap identity;
   - `run_offline_suite.py`;
   - Alpine8K opens (which_level);
   - one same-pose still compared with `townkit_flat01`.

## Questions for the design reviewer

1. Is a Shape Grammar driven from 2 m wall courses expressible with these modules, given that the corner module
   is 1 m and the walls are 1, 1.5, 2 and 3 m? Footprint widths come from the plan in 50 cm snaps. Does the grammar's
   "as many as fit" plus a fallback leave gaps, and how does PCG report a gap?
2. Which 5.8.3 reflected surface (Python, or the PCGToolset tools exposed over Unreal MCP) can create and set
   BP_ShapeGrammarRule/Definition data assets and run a PCG graph to completion? `generate_local` is asynchronous
   (playbook §7.6).
3. Is the jetty expressible within the grammar (a per-floor offset), or does it need a second spline per storey?
4. Is baking to static output deterministic across two generations, and which call does it?

## Design review 2026-10-10: GO-WITH-CHANGES (12 changes), and how each lands

- **Q1.** The grammar parses (PCGGrammarParser.cpp:24-49; Weight is int8).
  - The fill is greedy-random with NO backtracking (PCGSubdivisionBase.h:179-444), so it can strand 0.5 m where
    `town_kit_plan.tile()`'s exact DP cannot.
  - A grammar that does not fit, or an incomplete fill (accept_incomplete_subdivision false, the default), emits
    ZERO points for that segment, with a warning (PCGSubdivideSegment.cpp:83-99).
- **Q2.** `unreal.PCGToolset` has ZERO Python methods: its functions are AICallable and MCP-only.
  - The native reflected surface is complete: PCGGraph.add_node_of_type / add_edge, PCGSubdivideSegmentSettings,
    PCGGrammarSelection, PCGSubdivisionSubmodule, PCGMeshSelectorByAttribute, PCGComponent.generate_local +
    generation_in_progress, get_generated_graph_output, clear_pcg_link.
  - BP_ShapeGrammarRule/Definition assets are built from unreflected user-defined structs, so they are NOT
    Python-drivable.
- **Q3.** A jetty cannot live in the grammar. It is a storey-keyed Transform Points, or a pre-offset storey-2
  segment.
- **Q4.** Generation is seeded per (component seed, node, per-point seed). The bake is
  `PCGComponent.clear_pcg_link()`.
  - Without use_seed_attribute, equal-width houses get IDENTICAL facades.
  - ISM order stability is unproven.
- **(e) Correction to this doc.** "every house has the same rhythm" is overstated: `town_kit_plan.py` already tiles
  exactly with a seeded shuffle and random 2 m variants (:64-84, :141). What reads identical is uniform variant
  frequency, no jetties, no storey treatment and the same whole roofs.

1. **Changes 1-2.** Arm B = native nodes; option 1 is demoted to "read SGD_Bldg_Demo for ideas". PCGToolset is
   not a criterion (MCP-only).
2. **Change 3.** Cite LESSONS 2026-09-21 :36904:
   - the graph Input/Output pins are not "In"/"Out";
   - AddEdge is non-raising, so the edge list is read back after wiring.

   The prior ruling this trial re-tests is "skip PCG, editor-coupled" (LESSONS :13802, :38211).
3. **Change 4.** The kit sizes come from `Free/_measured/kit_medievalvillage.json` (the SM_MedievalModular
   intake), not `_v2.json`.
4. **Change 5.** `modules_info` uses NOMINAL sizes (100/150/200/300 cm), as town_kit_plan does, because the
   measured bounds overlap the trim (Door15x2M 150.96 cm). This deliberately departs from the quoted Epic "always
   get_bounds" rule.
5. **Change 6.** Every stochastic group carries 1 and 1.5 m symbols, plus a `<[W15],[W1]>` tail fallback.
   `accept_incomplete_subdivision` = false (loud: a missing facade). The fit warnings are counted and reported
   beside the verdict.
6. **Change 7.** Per-house seed through use_seed_attribute.
7. **Change 8.** Corners are placed from Python, as in arm A. The grammar runs over L - 2 x corner arm.
8. **Change 9.** The jetty is a pre-offset storey-2 segment plus a SupportBeam bracket spawner branch, recorded as
   living outside the grammar string.
9. **Change 10.** The determinism gate compares sorted transform lists (scripts/read_instance_transforms.py on the
   clear_pcg_link actor) and reports the counts.
10. **Change 11.** The plugin enable chains 5 plugins: PCGPrimitives, PCGGeometryScriptInterop, PCGBiomeCore,
    PCGBiomeSample, PCGExternalDataInterop. All 5 mounts are read back after the restart.
11. **Change 12.** The editor is detached. Payloads run in the foreground for less than 120 s, and
    generation_in_progress is polled across calls.
12. **ARM C, ADOPTED.** The Python kit builder gains:
    - weighted variants from recipes/town_kit.json;
    - per-storey sequence policies;
    - a jetty (upper courses offset by beam depth, plus SupportBeam brackets);
    - storey weighting.

    The verdict then measures PCG's MARGINAL value over the improvable baseline. Arm C needs no editor until the
    stills.

### Build decisions after the review (2026-10-10)

- **Level.** Arms A and C are placed on the town_kit gallery RIG (`/Game/LookDevMtn`, recipes/town_kit.json probe
  block), not on a new `/Game/Scratch/SG_Trial` level. A level from `new_level` is unlit (R-AL8129 REJECTED), and
  the rig is the proven kit stage. It is never saved; labels SGTrial_00..07 are shared, so arm C replaces arm A
  house for house. Every shot starts from a FRESH editor session, so gallery actors (same probe tag, different
  labels) cannot occlude the row.
- **Jetty brackets: DEFERRED.** The arm C jetty is unsupported in this run's stills (recipes/sg_trial.json
  `_brackets_DEFERRED`).
- **Licence.** The AI guard's render_globs now cover `_verify/sg_trial/**` and `_verify/lookdev/sg_trial*/**`.

## VERDICT (2026-10-11): PCG Shape Grammar NOT adopted for the town's rectangular houses; ARM C adopted as the next step

Stills are in `_verify/lookdev/sg_trial01` ({a,b,c}_{front,oblique}); they are AI-restricted (kit). The metrics are
in `_verify/sg_trial/metrics.json`.

| arm | facades filled | distinct sequences | 2 m variant entropy | instances | fit failures | determinism |
|---|---|---|---|---|---|---|
| A (shipped builder) | 96 of 96 | 27 | 1.566 bits | 462 | 0 | yes (pure) |
| C (builder + style) | 80 of 80 | 34 | 1.530 bits | 432 | 0 | yes, 2 passes |
| B (PCG SubdivideSegment) | 66 of 96 | 41 (see note) | 0.426 bits | 475 | **30 of 96 (31 %)** | yes, 2 runs, 193 symbols |

Note: B's "distinct sequences" is inflated by fragmentary 1 m-module fills; the stills show them as busier, not
richer.

- **B fails on the trial's own ground.** The greedy-random fill with no backtracking (PCGSubdivisionBase.h:179-444)
  strands a remainder on 31 % of runs, and `accept_incomplete_subdivision=false` then emits ZERO points for those
  runs, so whole facades are missing in the stills. Where it fills, the 1 m modules dominate and the variant mix
  collapses (MD 21, MH 2, MG 0). Python's exact DP tiling (`town_kit_plan.tile`) cannot strand.
  - Remedies exist (a scalable filler with texture stretch, `accept_incomplete=true` with visible holes, tuned
    weights). None gives anything the Python builder lacks on RECTANGULAR footprints.
  - Each remedy adds editor coupling: an async generate, the 5.8 PointArrayData read-back, a selector setter that
    lies.
- **C improves A, with no editor coupling.** Jettied upper storeys over the door side, 2- vs 3-storey skylines and
  distinct ground and upper bands read in the stills.
  - **Limit 1:** the roofs and the wall vocabulary are unchanged, so the houses still read as kit boxes.
  - **Limit 2:** the jetty is unsupported; brackets are deferred.
- **Where PCG would still earn its place:** spline or polygon footprints and Polygon2D lots (PCGSubdivideSpline,
  PCGDuplicateCrossSections). That is the non-rectangular town core, out of this trial's scope. This verdict
  re-confirms, with measurements, the 2026-09 "skip PCG for the deterministic pipeline" ruling for rectangles.
- **Next town-quality steps** (not started):
  1. Wire arm C's `style` into the town manifest, behind a recipe switch.
  2. Add jetty brackets (probe SupportBeam bounds first).
  3. Roof variety: the stills say the whole roofs are now the dominant sameness.
