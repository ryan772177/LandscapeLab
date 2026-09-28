I said the only remaining instrument was authoring a real quest against the schema. I can run that in output without writing to disk, and I should have run it two turns ago instead of writing about it. Running it now.

## The authoring pass — `alpine_lost_surveyor`, end to end

```json
{
  "schema_version": 1, "quest_id": "alpine_lost_surveyor", "region_id": "alpine_8k",
  "kind": "side", "arc_band": "foothill",
  "title_key": "QUEST.LOST_SURVEYOR.TITLE", "summary_key": "QUEST.LOST_SURVEYOR.SUMMARY",
  "gate": { "all_of": [ { "key": "alpine.surveyor.met", "op": "==", "value": true } ] },
  "objectives": [
    { "objective_id": "find_camp", "text_key": "…OBJ.FIND_CAMP", "requires": [],
      "completion": { "key": "alpine.surveyor.camp_found", "op": "==", "value": true },
      "anchor": "poi_east_basin_camp" },
    { "objective_id": "cull_wolves", "text_key": "…OBJ.CULL", "requires": ["find_camp"],
      "completion": { "key": "alpine.wolves_culled", "op": ">=", "value": 6 },
      "progress_bar": { "key": "alpine.wolves_culled", "target": 6 },
      "anchor": null, "excludes": ["spare_the_pack"] },
    { "objective_id": "spare_the_pack", "text_key": "…OBJ.SPARE", "requires": ["find_camp"],
      "completion": { "key": "alpine.surveyor.pack_spared", "op": "==", "value": true },
      "anchor": null, "optional": true, "excludes": ["cull_wolves"] }
  ],
  "outcomes": [ … ], "fail_conditions": [ … ]
}
```

It did not survive. Six structural defects, none of which four rounds of re-reading found.

## What the authoring pass broke

**1. The schema cannot express who writes a key — and it is usually not a quest.** `alpine.surveyor.camp_found` is written by a trigger volume. `alpine.wolves_culled` by combat, on wolf death. `alpine.surveyor.dead` by NPC death. Three of my six keys have **no quest writer at all**, and `owner_quest` admits only "a quest" or `null`. Gate 4 as specified refuses the entire quest. This is the mandatory-field defect one more time, in the single declaration itself: `owner_quest` asserts a quest owns every key, and most world facts are not owned by one.

Correction: replace `owner_quest` with `writers: []`, entries namespaced — `"quest:alpine_lost_surveyor"`, `"world:trigger_east_basin_camp"`, `"system:combat"`. Gate 4 becomes: every write site declares itself, and a write from an undeclared source is refused. `[]` means read-only-by-design, and the validator refuses any write to it.

**2. `excludes` is two lists that must agree.** `cull_wolves` lists `spare_the_pack` and vice versa. I flagged that pattern as a defect elsewhere in this same document and then committed it. Replace with one quest-level `exclusive_groups: [["cull_wolves","spare_the_pack"]]`.

**3. `excludes` on objectives does not make outcomes exclusive, which is what I claimed it did.** The completion predicates are independent facts about the blackboard. A player can kill six wolves and *then* take the sparing dialogue; both predicates are now true and both outcomes fire. Objective exclusion is a UI affordance; it is not an interlock. Outcomes need explicit ordered priority with a first-match rule, and a runtime assertion that exactly one fired.

**4. `progress_bar.target: 6` duplicates `completion.value: 6`.** Same defect as 2. `progress_bar` should be `{"key": "…"}` only, with the target derived from the completion predicate.

**5. Dialogue does not say when side effects commit.** `greet_first` writes `alpine.surveyor.met`, and the entry-point selector reads it. If the player walks away mid-node, has it been written? On entry or on exit? Unspecified, and the two give visibly different behaviour on the very next interaction. Must be declared per node: `"commit": "on_enter" | "on_exit"`.

**6. `arc_band: "foothill"` was a guess.** The camp is in the east basin, the wolves range upslope. One quest, two bands. The field assumes a quest occupies one, and I typed the one the quest *starts* in — exactly the invented-value behaviour the rule predicts. Either it is a range, or it is a property of the objective rather than the quest.

## What this says about the previous four passes

One authoring attempt produced six structural defects; four rounds of re-reading produced eight mostly-cosmetic ones. Same document, same reader, different instrument — and the difference is that authoring forces a value into every field, so an inapplicable field has to announce itself. That is the whole content of the rule, demonstrated on me rather than quoted by me.

It also retracts my turn-four framing again: the schema was not "under-specified", it was **wrong about who owns world state**, and that is a design error rather than a documentation gap. Defect 1 is the load-bearing one — the blackboard's ownership model was built around quests when most writers are world and systems.

## Handoff

The design's engine findings are unmoved across five passes and remain the part I would build on: `FActorInstanceGuid::GetActorGuids` as the only identity accessor valid in both editor and cooked builds; `CommonConversation` rejected as an authoring format on the UncookedOnly-compiler grounds; the save enumeration and its exclusion of landscape and foliage.

The quest schema needs defect 1 resolved before anything is authored against it, and that is a design ruling about ownership, not a field rename. I am not running a sixth self-audit; the next evidence comes from authoring a **second** quest — a chained one — against the corrected schema, because chain gating is the one structure this pass did not exercise.