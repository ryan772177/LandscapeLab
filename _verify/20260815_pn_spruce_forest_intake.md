# PN_interactiveSpruceForest — D2 intake measurement

Measured 2026-08-15 against the running editor (node
`93BE76A74609A5394E62EF9F8119B4E1`, rule-7 MATCH). Nothing placed, nothing
saved, no vendor byte written.

Raw: `Free/_measured/pn_spruce_forest.json`.
Log: 21 meshes + 2 imposter atlases, all `ok`.

## What the pack is

    total            363 files, 1.46 GB, 0 TRACKED (entirely gitignored)
    meshes            21, ALL StaticMesh -> all scatterable as foliage
    Blueprints         2  PN_GlobalUpdater, PN_Bending_Component (wind)
    imposter textures 21  = 7 trees x 3 maps (A, N, O), 4096 x 4096

**Correction to the D2 ruling's wording.** It records "21 baked 4096²
atlases", which reads as 21 imposters. It is **7 imposters, each with three
4096² maps**. The substance is unchanged — every one of the 7 base trees has
a baked imposter — but the count is a texture count, not an imposter count.

## The 21 meshes

Fourteen "big" trees (7 base forms x high/low) and seven saplings.

    mesh                  height   lods   lod0 tris   slots   lod group
    spruce_full_01        10.52 m    5      12,691      4     SmallProp
    spruce_full_02        11.91 m    5      24,237      4     NAME_None
    spruce_full_03        12.34 m    5      23,618      4     NAME_None
    spruce_full_01_low    10.64 m    5       7,373      4     SmallProp
    spruce_full_02_low    11.80 m    5      13,068      4     SmallProp
    spruce_full_03_low    12.53 m    5      12,899      4     SmallProp
    spruce_half_01        16.73 m    5      20,695      4     NAME_None
    spruce_half_02        14.65 m    5      24,183      4     NAME_None
    spruce_half_03        16.42 m    5      28,510      4     NAME_None
    spruce_half_04        15.81 m    5      23,091      4     NAME_None
    spruce_half_01_low    16.95 m    5      16,179      4     SmallProp
    spruce_half_02_low    15.08 m    5      14,091      4     SmallProp
    spruce_half_03_low    16.82 m    5      23,392      4     SmallProp
    spruce_half_04_low    16.02 m    5      19,680      4     SmallProp
    spruce_small_01        0.56 m    4          64      2     SmallProp
    spruce_small_02        1.21 m    4         133      2     SmallProp
    spruce_small_03        1.78 m    4         144      2     SmallProp
    spruce_small_04        2.56 m    4         206      2     SmallProp
    spruce_small_05        4.53 m    4       2,604      3     SmallProp
    spruce_small_06        6.35 m    4       6,408      3     SmallProp
    spruce_small_07        7.74 m    4       6,447      3     SmallProp

Height range **0.56 – 16.95 m**, which matches the ruling's 0.56–16.9 m and
delivers the sapling tier the forest entirely lacks. Pivot XY offsets are
0.010–0.293 m; the worst (`spruce_half_03`/`_low`, 0.293 m) still clears the
0.258 m limit only marginally and must be checked against
`uncorrected_pivot_errors()` if any of these ever go on the grass system.

**These are CHEAP trees.** Largest LOD0 is 28,510 triangles against the
incumbent `fir_tree_01`'s 505,494 — 17.7x lighter — and the placed
`SM_PVE_Norway_Spruce_01_A` is heavier still.

## THE HEADLINE: the imposter is LOD4, not a separate system

`measure_lod_materials.py` on `spruce_half_01`:

    slot [3]  .../MaterialInstances/imposter/high/half_01_imposter

    lod   triangles   screen   sections -> materials
    0        20,695   1.0000   trunk, branch, leaf
    1        10,347   0.9900   trunk, branch, leaf
    2         5,174   0.6000   trunk, branch, leaf
    3         2,587   0.3500   trunk, leaf          <- branch LOST
    4             6   0.1700   half_01_imposter     <- SUBSTITUTION

**The fourth material slot IS the imposter, bound as the final LOD at 4–6
triangles.** BACKLOG's aerial-readability item — "the only way real forest
reaches airship altitude past the 730 m cull" — is therefore closed by the
mesh chain itself: no imposter actor, no second scatter, no extra system, and
the cost is 4 triangles per distant tree. This is the single strongest
argument for the pack and it is now measured rather than inferred from the
folder name.

## HAZARD: one `lod_group` write destroys every imposter

`SmallProp` is declared `NumLODs=4` (`BaseEngine.ini:2685`). All 14 big trees
have **5** LODs. `UStaticMesh::SetLODGroup` calls
`SetNumSourceModels(DefaultLODCount)` unconditionally
(`StaticMesh.cpp:5605-5607`), and `SetNumSourceModels`
(`StaticMesh.cpp:5944-5974`) takes a shrink branch when `OldNum > Num`: it
clears the mesh description, empties the bulk data and removes the section
info for every LOD above the new count, then truncates.

**So assigning any 4-LOD group to these meshes deletes LOD4 — the imposter.**

The engine's own comment at `StaticMesh.cpp:5604` says the opposite:
*"Set the number of LODs to at least the default. If there are already LODs
they will be preserved"*. The code three lines below it does not preserve
them. This is the project's prose-claims-rot class, in engine source.

**The trap is that the obvious tidy-up is the destructive act.** 15 of 21
meshes carry `SmallProp` and 6 carry `NAME_None`, inconsistently — the same
tree at `high` and `low` differs. The natural response is to normalise the
group. Doing so on any of the 14 big trees destroys its imposter.

**RULING: the LOD groups are NOT normalised. The inconsistency is cosmetic;
the fix is not.** Recorded here so a later session does not "clean it up".

Not currently firing: the meshes have 5 LODs *with* `SmallProp` already set,
so nothing is re-applying the group today. This is latent, not active.

## SECOND FINDING: the branch material is lost mid-chain, before the imposter

Every mesh tested drops its `_branch` material at LOD2 or LOD3 — a genuine
composition change, not the imposter substitution:

    spruce_full_01       branch lost at LOD2 (screen 0.30)
    spruce_full_02_low   branch lost at LOD2 and LOD3
    spruce_half_01       branch lost at LOD3 (screen 0.35)
    spruce_half_04_low   branch lost at LOD3

Trunk and leaf survive. For a conifer whose branches are largely occluded by
needles this is plausibly benign, but it is a real transition and it is
recorded rather than waved through. **The render A/B decides**, per the
project's standing rule that coverage/geometry statistics do not settle a
look question.

## Imposter atlases

    full_01_imposter_A_unlit   4096x4096   albedo [ 59, 56,  1]
    half_01_imposter_A         4096x4096   albedo [ 86, 77, 30]

Both report alpha CONSTANT (1 level), and `measure_tree_packs` correctly
refused to publish a coverage percentage for them. That is right and not a
defect: opacity ships as a **separate `_O` map**, so the albedo texture
carries no mask. Naming differs between sets (`_A_unlit` for `full`, `_A` for
`half`) — vendor inconsistency, no functional consequence.

## Tool changes made while measuring

- `measure_rock_meshes.py` — payload now reads `lod_group`
  (`StaticMesh.lod_group`, a `Name`; PythonStub:387388, enclosing class
  resolved rather than recalled). Unreadable stays `None` and is never
  collapsed into "no group", because those are opposite obligations.
- `measure_tree_packs.py` — reports lod group and slots per mesh, spelling
  out which of the three states was read.
- `measure_lod_materials.py` — **separates SUBSTITUTION from LOSS.** It
  previously exited 4 on all 14 big trees and advised "stop the chain before
  the loss", which would have discarded the imposters. A LOD that drops
  materials *and binds one LOD0 never had* is a replacement representation;
  one that drops without replacing is simplifier loss. Only the latter fails.
  Verified both directions on real meshes: the imposter LOD reports as a
  substitution and the `_branch` loss still exits 4.

## What is NOT measured yet

- **`MA_Imposter` compilability in 5.8** — the reason the pack was chosen is
  unproven until it compiles. Scratch scene, not the world.
- **The wind dependency.** `PN_GlobalUpdater` / `PN_Bending_Component` are
  runtime Blueprints and the masters carry `PN_WindAnimation` / `PN_Bending`.
  Whether wind is an overridable parameter or hard-wired is unread.
- **Nothing has been rendered.** Every number here is a property read. No
  claim about how these trees LOOK is supported yet.

---

## Addendum 2026-08-15 — the imposter RENDERED against LOD0

Single variable: .ForceLOD 0 -> 4, set and read back both times, same
parked camera (`spread_wide`, 35 m), same lighting, nothing else touched.

    frame            mean     std
    LOD0            0.7673   0.1463
    imposter (LOD4) 0.7742   0.1368

    mae 0.01277   6.91% of pixels moved >2%   max 0.8039
    tree-ish pixel coverage   LOD0 3.916%  imposter 3.212%  ratio 0.820
    silhouette IoU                                          0.6892

**THIS IS A HARDER TEST THAN REALITY AND IT PASSES.** LOD4 is selected at
screen size 0.10-0.17, roughly 100 m+ for a 16.7 m tree. This comparison
forces it at **35 m**, where it is rendered several times larger than it
would ever legitimately appear. The imposter is being judged well outside
its design range.

**What holds:** silhouette, canopy density, colour and trunk all read
correctly on the mature trees. Side by side at this size the substitution is
visible but not wrong -- it reads as the same tree, which is the criterion
measure_lod_materials.py names.

**What does NOT hold, stated plainly:**

1. **CAST SHADOWS ARE LARGELY LOST.** The long raked shadows the R13 12-deg
   sun throws across the ground in the LOD0 frame are mostly absent in the
   imposter frame. A camera-facing billboard cannot cast a tree-shaped
   shadow. At true imposter range the shadow is small and the sun is low, so
   this is a distant-terrain shading difference rather than a foreground
   one -- but it is a real difference and it is NOT captured by the mae.
2. **The 0.56-2.56 m saplings degrade badly**, reading as dark blocky
   clumps. They are sub-pixel at any distance where LOD4 is selected, so this
   costs nothing in practice -- but it means the imposter tier is a
   BIG-TREE feature, and a sapling species should be culled outright rather
   than imposter'd.
3. The imposter is ~18% thinner by pixel coverage (ratio 0.820, IoU 0.689),
   which is the usual alpha-tested-billboard fringe loss.

Frames: _verify/20260815_pn_lod0.png, _verify/20260815_pn_imposter_lod4.png.

**Still not measured:** the imposter at its ACTUAL selection distance
against a full forest, and the 4-vs-3 material-slot cost. Both belong with
the D4 scatter, where a real stand exists to measure.

---

## Addendum — the two species added to `recipes/alpine_8k.json`

Added 2026-08-15. **Nothing is scattered yet.** The recipe now describes a
forest the world does not contain; D4's single re-scatter is what reconciles
them. That divergence is deliberate -- the ruling says ONE re-scatter
combined with D2's mix, because every mass re-scatter re-rolls every
position and doing it twice would invalidate all positions for an
intermediate state with no measurement value.

    species          share   cull      scale        resulting height
    Conifer          0.32    730 m   0.60-1.15      17.6 - 33.7 m   canopy
    ConiferPine      0.23    730 m   0.60-1.05      canopy
    SpruceSub        0.25    730 m   0.70-1.15      11.7 - 19.2 m   sub-canopy
    SpruceSapling    0.20    180 m   0.60-1.60       2.7 -  7.2 m   regeneration

Instanced `weight_share` totals exactly 1.0, asserted before writing.
Conifer and ConiferPine were REBALANCED from 0.60/0.40 -- the new tiers take
their share from the canopy rather than being added on top of a full budget.

**Why these two meshes.** `spruce_half_01` (16.73 m) sits UNDER the placed
29.31 m Conifer, so the two read as different height classes rather than as
noise on one; WORLD_VISION's complaint about the old forest was UNIFORMITY as
much as sparseness. `spruce_small_05` (4.53 m) is the regeneration tier the
forest has never had at all.

**Why the culls differ, and it is not a style choice.** `SpruceSub` affords
730 m *because* its mesh carries a baked imposter at LOD4 for 4-6 triangles.
`spruce_small_05` has NO imposter -- its chain ends in real geometry -- and
a 4.5 m sapling subtends roughly 1.5 px at 730 m on a 1080-line frame, so the
far 550 m would buy sub-pixel specks at full instance cost. 180 m instead.

**`SpruceSapling` takes 28 deg of slope where the mature tiers take 24.**
The constraint on a 20 m conifer is root-plate stability; a 4 m sapling does
not have one yet and establishes on ground that will not hold a mature tree.

**Nanite is FALSE on both and MUST STAY FALSE.** They render through the
classic LOD chain, and LOD4 *is* the imposter. Enabling Nanite bypasses it.

### TWO GATES FIRED ON THE FIRST ATTEMPT AND BOTH WERE RIGHT

1. `unknown key in foliage.species[3]: _what`. The vegetation key set is
   CLOSED and does not admit underscore-prefixed notes, unlike
   `capture.cameras` which does. That is deliberate -- the schema refuses
   an inert field on a species because an inert field reads like a setting.
   All seven note keys were stripped; the rationale lives here instead,
   which is where prose belongs.
2. `has no VERIFIED row in the normalisation report`. Every foliage mesh
   must carry measured pivot/base provenance. These are vendor `.uasset`
   files that cannot go through `normalize_asset.py` -- there is no FBX,
   and the pack is gitignored with 0 tracked files so it must not be
   rewritten. That is exactly the case `Free/_measured/engine_derived.json`
   exists for. Registered under `pn_interactive_spruce_forest`, values
   COPIED FROM the 2026-08-15 measurement rather than retyped:

       spruce_half_01    pivot 0.0645 m   base -0.0024 m   (contract 1.0 / 0.25)
       spruce_small_05   pivot 0.2307 m   base -0.0002 m

   Both inside contract. Recipe now validates with **0 foliage errors**.
