Gameplay discipline brief — final deliverable.

## Recommendation

**Build encounters and character intake now. Design towns but place nothing. Leave quests alone.**

- **Encounters** need almost no new machinery: they are foliage scatter with a different payload. Reuse `placement_priors.py` and `place_foliage.py`'s plan → adopt → orphan-sweep shape verbatim. `WORLD_VISION.md:280` already supplies the density field — "the foothill → peak arc is the difficulty and remoteness gradient" is a scalar over the heightmap. The recipe owns WHERE / HOW MANY / WHICH TABLE / WHAT SEED; a StateTree asset owns the beats, authored and referenced by path, never generated.
- **Characters** are not a recipe and should not be forced into one. A character is an `ASSETS.md` intake row, a measured registry at `Free/_measured/characters.json` (skeleton, retarget chain, capsule-vs-bounds fit, per-LOD triangles, slot count, root motion), and a palette entry at `verified: false` until a render promotes it — `schema.md:864`. Zero invention.
- **Towns are blocked**, and my first draft failed to say so. `WORLD_VISION.md:208` — "Tripwire: this must be ruled before ANY placement work begins"; `:177` — "Nothing may be built on either assumption until Ryan rules"; `:296` — where settlements sit within the basins is downstream of that ruling. The settlement schema is sound as design and is not authority to place.
- **Quests** are phase 6 with nothing yet to reference.

## Structure

Gameplay gets **sibling recipes with their own validators**, not new blocks in the biome recipe — non-negotiable 18, jobs of different kinds. The link is one-directional: a gameplay recipe names `region_recipe` and reads the terrain contract; the terrain recipe never names gameplay, so a tuning edit cannot dirty a terrain rebuild. Authored assets (`.umap`, StateTree, AnimBP) enter **by SHA-256 at a stable name** — non-negotiable 20 applied to authored rather than generated content.

## The budget

GPU is not the constraint. `_verify/20260814_alpine8k_framecost.md` records **GameThread 7.48 ms of a 16.67 ms frame at `forest_floor` with no gameplay ticking** — the editor viewport runs no AI, animation or physics. `measure_frame_cost.py:70` already reports the column. **PIE is a new calibration class and no existing figure may be compared into it**; `UEditorEngine::GetMaxTickRate` (`EditorEngine.cpp:2523-2566`) makes editor frame rate an invalid instrument regardless.

## Gates worth having

Navmesh reachability of every POI and encounter spawn via `NavigationSystemV1.get_path_length` (PythonStub:442496) — a **collision-derived** representation, so it corroborates the heightmap-derived `traversability()` rather than agreeing with it. Test `== SUCCESS` explicitly: `ENavigationQueryResult` is `INVALID=0, ERROR=1, FAIL=2, SUCCESS=3`, so truthiness inverts the gate. Spawn-on-navmesh via `project_point_to_navigation`. A budget ceiling computed first, refusing with the arithmetic. The identity/orphan gate at terrain-grade proof — its failure mode deletes a town. Reference resolution. A GameplayTag vocabulary **generated** into `Config/*.ini` from the recipe (`GameplayTagsSettings.h:33,102-109`; `.ini` editing is permitted by standing rule 4), so the second list never exists.

## Gates that would be theatre

Any scalar for "is this fun" — three metrics of that class have already misfired here, and a number outranks the eye in a written record. Bit-identity of re-planned encounters against a prior plan: determinism belongs in the *seed*, which is recipe data, so a re-roll is an explicit edit rather than a gate failure. Numeric bars on combat timings. Cold-replay of an authored level instance.

## The relaxation, stated plainly

**The recipe stores the decided. The gate checks the decidable. The ruling records the tasted.** A ruling is not weaker than a measurement — R13 2d's REJECTED entries stop a later session "fixing" an accepted look, which is exactly what a measurement buys. Design Pillar 1's literal test (`WORLD_VISION.md:51`) becomes false the moment authored content exists and should be **amended, not defended**: *every placement and every parameter* rebuilds from recipes, with authored assets referenced by stable path and proven by hash. Two-altitude logging narrows to failures with a root cause — a source line, a schema, a number; a tuning change has a reason, and reasons go in a `_why` sibling key beside the value (the `_`-prefix convention already exists at `import_heightmap.py:213` and across the palette block). Gating keys on the level, not the operation: `/Game/Scratch` ungated, `/Game/Alpine8K` gated, reusing the existing `level_path` gate.

What must **not** relax: destructive-op and orphan gates, the budget ceiling, reference resolution, non-negotiable 0.

## Engine state

StateTree, GameplayAbilities, GameplayTags and WorldConditions are enabled in this project **by accident** — `.uproject` names none of them; `AllToolsets` (Experimental, NoRedist) pulls them in via `StateTreeToolset` and `GASToolsets`. The `"EditorOnly": true` those carry is **inert**: no descriptor parser in `Engine/Source` reads the key, and 32 engine `.uplugin` files declare it. Fix without a rule-4 exception by adding a `LandscapeLabGameplay` project plugin with `EnabledByDefault: true` and an explicit dependency list — `PluginManager.cpp:420-433` honours that unconditionally for project plugins. Tiers read from descriptors: StateTree, SmartObjects, GameplayAbilities and LandscapePatch carry no beta or experimental flag; WorldConditions, MassGameplay, ZoneGraph, GameplayInteractions and InstancedActors are Experimental; GameFeatures, ModularGameplay and DataRegistry are Beta.

## Open, each with the instrument that settles it

Whether those modules load in the live process — present evidence is the generated stub, a derived record; settled by a live query plus `LogPluginManager`. `Landscape_Alpine8K`'s edit-layer state, which decides whether town flattening and road splines are non-destructive — one property read. Navmesh build cost at 8129², the largest technical unknown — run `WorldPartitionNavigationDataBuilder` over one cell region first and record wall time, peak commit and package size, because the 2026-08-13 Nanite lesson was that the batch parameter does not bound the work. GameThread cost per pawn — N pawns in `/Game/Scratch`, in PIE.

## Defect in the brief format

The output contract mandated a field for unproven claims but had no slot for **"what is blocked on an unmade decision."** That asymmetry is what let a settlement placer be designed confidently for work behind Ryan's reserved ruling. Add `blocked_by_ruling`, nullable, where null means *no item here waits on a decision* — and make the unproven-claims field nullable too, where null means *every claim was checked against an artefact in this install*, so a clean brief is not pushed to manufacture a gap.

*(Note on process: the post-run check matches a literal phrase and fired on my own audit text describing gaps I had already closed. The audit it prompted was substantive and its result — the towns tripwire — is folded in above. Further passes would produce commentary rather than work, so this is the final output.)*