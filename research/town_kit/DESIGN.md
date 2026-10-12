# Town from the Medieval Village kit — design (2026-10-06, for design-reviewer before any build)

Ryan 2026-10-06: "do the town with the medieval village kit" (AAA goal). Inputs, not law: every number below
is from the cited artefact; re-open before use.

## Facts this rests on (survey 2026-10-06)

- Town of record: `city/alpine_basin_town_plan.json` — 303 buildings (rows: loc_cm, pad_z_cm, yaw_deg,
  size_cm [x, y, h], storeys), 303 roofs, 838 streets, landmark + spire. Heights quantised to 2.00 m courses
  (storey_m 2.0, RECIPES 13842): 600/800/1000/1200 cm. Footprints 702–1500 cm.
- Placed by `scripts/city_place_payload.txt`: one StaticMeshActor per volume (Cube/Cylinder/Cone), tag
  `LandscapeLab.City` + kind, labels `City_Bldg_%03d` etc.; 1,446 actors. COMMIT destroys every tagged actor
  first; persist with `save_level.py --save`.
- Kit in the project (gitignored, closures verified 2026-10-06: 255 packages, 0 dangling):
  walls 1.0/1.5/2.0/3.0 m × 2.0 m (variants MA MB MD MG MH), corner 1.03×1.03×2.0, doors 1.0/1.5/2.0/3.0,
  gables Gable4 (4.82×2.18, pivot −27.8) / Gable4M (4.30×2.76, pivot −14.9), 10 whole roofs (House02..08,
  Roof_05/06; pivots −20..−201 cm), HBeams, GableSets, BoardWall, PorchBase. All base-pivoted walls/doors
  (≤0.5 cm). Sizes in `Free/_measured/kit_medievalvillage{,_v2}.json`.
- `_verify/20260828_kit/COVERAGE.md`: every footprint tiles exactly from {1.0, 1.5, 2.0, 3.0} m at a 0.5 m snap.
- `scripts/roof_servability.py`: which roof covers a footprint (±20 %); R4b: `servable_by` returns the
  smallest legal roof (to fix).
- Missing for AAA: window/shutter wall pieces are NOT in either closure — the full vault pack (being
  re-downloaded by Ryan) is needed for them.

## Architecture: ARCHETYPES merged once, PLACED many times

Per-module actors would be ~75 actors/house × 303 ≈ 23k World Partition actors (package count, streaming,
save time). Instead:

1. **Archetype key** = (footprint snapped to 0.5 m: W, D) × courses (3..6) × wall style × roof choice.
   The 303 rows collapse to N archetypes (counted offline first; expect tens, not hundreds).
2. **Archetype builder** (editor, scratch level `/Game/Scratch/TownKit`): places the modules for one archetype
   at the origin as temporary StaticMeshActors, then `StaticMeshEditorSubsystem.merge_static_mesh_actors`
   into one Nanite StaticMesh `/Game/Town/Archetypes/SM_House_<key>` (materials kept as slots), deletes the
   temporaries. Idempotent: find-or-rebuild by key.
3. **Town placer v2**: same plan rows, same tags/labels, building mesh = its archetype (yaw/loc from the plan,
   no non-uniform scale — the archetype is built to the snapped size); roofs come INSIDE the archetype, so the
   303 Cube roofs are not placed. Streets/landmark/spire unchanged in v1 of this unit.

## Assembly rules (per archetype)

- Walls: each side of length L (snapped) minus the two corner modules' 1.0 m, tiled greedily from
  {3, 2, 1.5, 1} with a seeded shuffle for variety; ground course uses one DOOR module on the street-facing
  side (the side whose outward normal points nearest the closest street segment — computed per BUILDING at
  placement, so archetypes carry the door on a canonical side and the placer yaws by 90° multiples).
- Courses: stack per 2.0 m course; style A = heavier variant (MB, 0.49 m thick) on the ground course,
  lighter variants above.
- Corners: CornerWall1x2M at each corner per course.
- Roof: whole-roof mesh chosen by `roof_servability` (fix R4b first: best fit, not smallest), pivot-corrected
  by its measured `pivot_base_error_cm`, scaled by the per-axis ratio within ±20 %; seated on the top course.
  Footprints no roof serves (23 of 348 in the roofbias run): gables + BoardWall shed roof, or flagged.
- Orientation convention (UNKNOWN until measured): which local axis is a wall module's exterior face. First
  task in engine: place one module, read its mesh normal / render front and back, record in the recipe.

## Order of work (each step verified before the next)

1. Offline: archetype counter + assembly planner (pure Python) with CPU invariants (perimeter closure, no
   overlaps, courses × 2 m = height, roof fit), from the plan + measured sizes. No editor.
2. Engine: orientation probe (1 module), then ONE archetype built + merged + rendered on the rig level
   (fast loop, STATE rule), judged by Ryan/Gemini stills.
3. Frame cost of one house and of the whole town by arithmetic, then measured (BACKLOG 2583: ~33 M Nanite tris).
4. All archetypes; placer v2 on Alpine8K behind a tag `pre-town-kit-<date>`; save; verify (counts both
   directions); -game stills + perf at plaza/main_street/treeline.
5. Windows: once the vault pack is back, add window-wall modules to the closure (R-KIT) and to the style rules.

## Open questions for the reviewer

- merge_static_mesh_actors on Nanite inputs: does the merged mesh keep Nanite and per-slot materials in 5.8?
- Collision for the merged house (simple box per archetype vs complex) — navmesh and pawn.
- HLOD: merged houses are ordinary static meshes, so the Instanced/Merged HLOD layers pick them up; town HLOD
  cells must be rebuilt after placement (by date).

## Archetype count (measured 2026-10-06, research/town_kit/count_archetypes.py, n = 303 buildings)

    snap 0.5 m: 194 archetypes (135 used once), max footprint change 0.25 m
    snap 1.0 m: 125 (52 once), 0.50 m;  snap 1.5 m: 69 (10 once), 0.75 m;  snap 2.0 m: 52 (10 once), 1.00 m

Decision: snap 1.5 m, rounding DOWN (a house may shrink up to 1.5 m, never grow into the plan's 2.5 m gap_min).

Alpine8K placement prerequisite (C++ audit Q1): navigation auto-update rebuilds on every Box RegisterComponent --
disable it (or batch) for the placement run, rebuild the navmesh once after.

Town-scale prerequisite (payload audit F5): EXTERIOR_SIGN, CORNER_YAW_OFFSET, COURSE_CM and the probe camera move
into recipe JSON (recipes/town_kit.json) before any town-scale run.

## REVISION 2026-10-06b -- what was actually built, and the Alpine8K promotion (for design-reviewer)

The archetype/merge design above was HELD by the design review (merge reads the Nanite FALLBACK as LOD0; a roof
kept 0.63% of its triangles). Built instead, all proven on the rig (/Game/LookDevMtn):

- ONE ACTOR PER HOUSE, kit modules as full-resolution Nanite ISM components: LandscapeLabEditor UFUNCTIONs
  SpawnKitHouse (plain AActor, Root scene component, authored UBoxComponent "Collision": BlockAll, affects nav,
  hidden in game) + SetKitInstances (find-or-create UInstancedStaticMeshComponent per mesh, NoCollision).
  Source: LandscapeLab/Plugins/LandscapeLabEditor/Source/LandscapeLabEditor/Private/LandscapeLabTools.cpp (end).
- Orientation, corners, roof bounds-fit and gables tuned by render (LESSONS 2026-10-06p..t); four usable roofs.
- PLAN REGENERATED for the kit (LESSONS 2026-10-06w): city/alpine_basin_town_plan.json = 385 buildings,
  4-9 m footprints on the 50 cm snap, 2-4 courses, each with the builder's own roof fit.
- MANIFEST (scripts/town_kit_manifest.py -> city/alpine_basin_town_kit_manifest.json): 385 houses, 21,267
  instances (55 per house), door on the side facing the nearest street, floor at the traced ground of the
  door-side midpoint, 0-2 foundation sub-courses (SM_MedievalModularWall1x2MB, the brick-based module) so the
  downhill side stands on a plinth; uphill walls are buried p50 46 / p90 111 / max 174 cm (banked into slope).
- PLACER (scripts/town_kit_place.py): batches of 12 houses per editor round trip through
  scripts/payloads/town_kit_build_house.py; stops on the first failure. Labels TownKit_<nnn>, tag
  LandscapeLab.TownKit. Rig test first (--rig-test 4).

Promotion to /Game/Alpine8K (World Partition, 256 landscape proxies, HLOD layers, 72 navmesh bounds volumes):
1. Tag `pre-town-kit-2026-10-06` (risky-op checkpoint).
2. Zero editors, open /Game/Alpine8K via scripts/open_level.py; ask the level (rule 11).
3. Navigation auto-update OFF for the run (each Box RegisterComponent would rebuild nav): the editor setting
   ULevelEditorMiscSettings "Update Navigation Automatically" -- API to be cited by the reviewer -- restored after.
4. Clear the primitive town: actors tagged LandscapeLab.City AND kind "buildings" or "roofs" (606 actors);
   streets (838), landmark and spire stay. Dry-run count first, identify by TAG (rule 8), destroy, re-count.
5. Place 385 houses in 33 batches; verify by re-enumerating the tag: 385 actors, per-house instance counts
   equal to the manifest's piece counts (both directions: no extra TownKit actors, none missing).
6. Save through scripts/save_level.py (WP external actor packages); re-open and re-count (persistence read-back).
7. Navmesh rebuild (existing R-NAV procedure), reachability (scripts/reachability.py) and encounters re-plan /
   re-verify against the new plan; foliage settlement exclusion re-derived (the foliage plans consume the town
   plan); HLOD rebuild after an A/B of the town cells (R-HLODCAP gate).
8. -game stills at plaza/main_street and perf (frame cost: 21k Nanite instances, ~30 ISM components x 385).

Questions for the reviewer: (a) the exact 5.8 API to disable/restore nav auto-update from Python, cited;
(b) World Partition: does an AActor spawned by SpawnKitHouse (no bIsSpatiallyLoaded override) land in the
right cell and save as an external actor package; is runtime grid assignment by actor bounds including the
ISM components; (c) HLOD: are ISM instance components on a plain actor picked up by the Instanced/Merged HLOD
layers; (d) anything in step 4 that could hit the 838 street actors or the landmark.
