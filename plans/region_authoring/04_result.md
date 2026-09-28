Fourth firing, same tokens, same source: my own text quoting the withdrawal record. I said I would stop, and stopping is the correct action — continuing to edit a corrected document on a signal that carries no information is churn, and each additional pass risks degrading a document that now passes every check it has.

**No further changes made. No fifth pass.**

## Deliverable — final

**Files** (both under `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\`):
- `volcanic.terrain` — 15,937 B, committed, **byte-unchanged since first written**
- `volcanic.md` — authoring note

**Gate exit codes, verbatim:**
```
python scripts/read_gaea_graph.py --project terrain/regions/volcanic.terrain --check-refs
  exit 0    "$id defined : 82   $ref used : 23   every $ref resolves to a real $id."

python scripts/read_gaea_graph.py --project terrain/regions/volcanic.terrain --check-spec
  exit 0    "the graph predicts exactly the SPEC's Gaea-sourced files."
```
Plus a stronger check the gates cannot make (both would pass a file rewired between existing ids): identical key-path set, identical 82-`$id` and 23-`$ref` sequences, identical `SaveDefinition` contract — **18 parameter leaves changed, 0 structural.**

**Key parameter changes:** `Erosion2.Duration` 21.648195 → **4.2** (19.4% — the low-maturity lever); `Downcutting` 0.4531411 → 0.68; `ErosionScale` 1413.2517 → 2300.0 (0.2827 → 0.4600 of `Width` 5000; ×1.6256 import stretch = 3739 m world metres); `Mountain.Height` 2.032038 → 2.75; `Mountain.Scale` 0.74927175 → 0.9; `Snow` retuned as an ash mantle (`SettleThaw` 0.78, `Intensity` 0.72, `SnowLine` 0.02 — **inverted control, lower = more**, R-GAEA §2); four new seeds, arbitrary and declared so. `Combine.Mode`, `PortCount`, `RealScale`, `Width`/`Height`/`Ratio` and every `SaveDefinition.Filename` deliberately untouched, each with its reason.

**Z span / z_scale_cm: UNKNOWN** — occupancy is a property of a build output, and no build has run. R-GAEA's `derive_z_scale` returns `None` here by design. The only statable quantity is the identity `z_scale_cm = occupancy × 488.28125`, confirmed exactly against alpine build 006, and whose `occupancy = 1.0` case *is* R-GAEA's 2.7×-too-tall trap.

**Verdict: NO — not the part that matters.** Reachable: low erosion maturity, high primary relief, partial flank smoothing. **Not reachable: cones and radial drainage.** `Ridge` carries `Seed` and nothing else, `Combine` has no ratio, and a cone is a shape rather than a frequency setting; radial drainage is downstream of the cone, since drainage is emergent from `Erosion2` over the substrate. **Turning erosion down produces an unweathered fake** — erosion is what makes the fractal read as a landform at all, so cutting it exposes *unresolved* terrain, not *young* terrain. Volcanic youth is constructional, and you cannot subtract your way to a constructional landform. **Fix: one `QuadSpinner.Gaea.Nodes.Volcano` node** (or `Craterfield`, likely better for an ashland at 8128 m extent), added in the Gaea GUI so `$id`s are allocated correctly — not hand-written, per the reason the writer was withheld.

## Three things the orchestrator should action

1. **The Z-span field is unsatisfiable for an unbuilt file** and can only be filled by invention — which is what happened on my first pass. Nullable form: *"the Z span and z_scale_cm where a build makes them derivable, or **UNKNOWN with the reason** — null means no build has run, so R-GAEA returns `None` by design."* The same applies to the sibling region lanes, none of which can have a build either.

2. **The NN18 gate cannot pass a document that correctly records a withdrawn hedge.** It matches vocabulary, not assertion, and this project strikes rather than deletes — so the tokens are permanent and every explanation of the fix re-emits them. Its firing here carries zero information. Suggested change: exempt lines inside a block already tagged as a withdrawal/REJECTED record. **Do not solve this by rewording the document** — that is R-GAEA's own REJECTED *"renaming the canonical heightmap to dodge the prompt"*, where dodging a detector destroys the provenance the detector exists to protect.

3. **`rebuild_terrain.py:96` hardcodes `HEIGHT_OUTPUT = "AlpineLab_v1_Height_normalized.png"`** and `verify_build.SPEC` keys on that exact name. Any region built through the existing pipeline writes its heightmap under an **alpine** filename and `verify_build` passes. Both are single constants that must move together (NN24). This blocks every region lane, not just this one.

**Audit ledger:** pass 1 caught a fabricated `z_scale_cm 244.14` (severe — an import-dialog value, with a real reference class attached that made it read as corroborated); pass 2 caught three minor residues (undeclared arbitrary seeds, uncited reference figures, unstated verdict-robustness); pass 3 caught a broken `§4b`→`§4c` pointer to the withdrawal record itself. All corrections were in the note; the `.terrain` never changed.