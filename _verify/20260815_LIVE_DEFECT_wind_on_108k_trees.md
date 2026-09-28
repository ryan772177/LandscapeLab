# LIVE DEFECT — 108,417 placed trees are rendering with WIND ON

Found 2026-08-15 by an adversarial recipe-drafting agent that checked this
project's own artefacts instead of trusting them. **It outranks every other
finding of the session, and it invalidates a conclusion already committed.**

## The defect

`SpruceSub` (55,004) and `SpruceSapling` (53,413) = **108,417 instances**
are standing in `/Game/Alpine8K` on their **VENDOR** materials, which carry
the `Level 1/2/3 Wind` and `Level 1/2/3 Bending` static switches.

The wind-off child MIs were built and verified. They are simply **not
applied to anything**:

    Free/_measured/pn_nowind_overrides.json   the 7 MIs exist
    recipes/alpine_8k.json                    override_materials appears ONLY
                                              on the 8 Blueberry GRASS varieties
    import_heightmap.py:476-479  _VEG         does NOT admit override_materials,
                                              so an instanced species CANNOT
                                              declare it
    place_foliage.py                          ZERO occurrences of
                                              override_material — it sets only
                                              `mesh` and `cull_distance`

And the capability exists: `FoliageType_InstancedStaticMesh.override_materials`
is in the 5.8 stub at `PythonStub:394542` with its property at `:394610`.

**So the fix is three small changes** — admit the key in `_VEG`, declare it
per species in the recipe, and set it on the FoliageType in `place_foliage`
— plus a re-apply. It is NOT a re-scatter: the transforms are correct and
unaffected.

## Why it was not caught

Every check that ran was true and none of them asked this question.

- The wind-off MIs were verified **structurally** (all six switches read
  back false) and **by render** — but the render test applied the overrides
  by hand to a scratch actor via `--apply-in-open-level`. That proved the
  MATERIALS work. It never proved anything about the PLACEMENT PATH.
- `make_nowind_material_instances.py` writes an override map and its own
  output says the consumer "must hand it to `FoliageType.override_materials`
  unchanged". **No consumer was ever written.** The tool told the truth about
  a thing that did not exist.
- The D2 write-up says "each mesh scattered later needs its own overrides
  from the same tool" — which reads as satisfied once the MIs exist, and is
  not.

This is the project's own gap-between-artefact-and-claim class, and the
specific shape is: **a capability was built, verified in isolation, and never
wired to the thing it was built for.**

## WHAT IT INVALIDATES — and this is the serious part

`_verify/20260815_alpine8k_noise_floor_per_station.md` and
`_verify/20260815_alpine8k_animation_check.md` conclude that the elevated
per-station floor (`forest_floor` 2.99x, `trunk_base` 6.65x, `sweep_2000`
5.51x) is **renderer temporal accumulation, not motion**.

That conclusion rests on material probes of `MA_Foliage_Trees` and
`ScotsPine_01_Leaves_Mat` — the **two PRE-D4 species**. Those probes were run
BEFORE the PN trees existed in the world. The animation check itself ran at
14:0x; D4 placed 108,417 PN trees at ~15:07; the floor artefact was committed
at 15:27, **after**, and re-used the earlier attribution.

**So the elevated floor may be actual WIND from 108,417 animating trees, not
temporal accumulation.** The two hypotheses predict the same statistic and
were never separated on the post-D4 world.

**The discriminator is cheap and was not run:** the per-station floors were
measured on the CURRENT world, so simply re-measuring `trunk_base` and
`forest_floor` after applying the wind-off overrides settles it. If the floor
collapses toward 0.003, it was wind. If it does not, the temporal-accumulation
reading stands.

Note what does NOT change: the pre-D4 measurement showing that removing the
grass left variance unchanged, and that neither pre-D4 tree material declares
a wind parameter. Those remain true of the world as it was then.

## Status

**NOT FIXED.** Recorded, not repaired, because the fix touches the placement
path and wants its own verified run rather than a rushed one.

Everything else about D4 stands: 219,659 planned == counted, grounding closed
by two representations, GPU 7.92 ms against an 11 ms bar. The trees are in
the right places wearing the wrong materials.
