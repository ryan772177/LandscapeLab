# BLENDER_HANDOFF.md — authoring a custom groom for a LandscapeLab character

---

## ⭐ STATUS 2026-08-21 — THE ROUND TRIP HAS NOW BEEN RUN. READ THIS FIRST.

Everything below this block was written before an `.abc` had ever been put
through the pipeline. It has now been done end to end, so the parts that were
predictions are replaced by measurements here.

### The Alembic import is no longer unexercised

    export   Blender 5.2 headless -> 81 MB .abc, NO attended click needed
    import   HairStrandsFactory
    count    Blender 31,570 evaluated curves vs UE 31,267 -- 0.96%
    bind     2.67 s, curve retention 1.0
    SEATING  WRONG -- the one remaining blocker

### The two files you were given, measured

**`groom.blend` (the Fab starter kit) is Blender's DEFAULT STARTUP SCENE** —
Camera, Cube, Light, 98 KB. There is no hair in it. Do not spend time on it.

**`Groom_Test_26_06_28_vfull_52.blend` (the exporter author's demo) is the
base**, and it is healthy in 5.2: 14 objects, 11 Curves, 39 node groups with
**zero undefined node types**, nonzero evaluated strand counts throughout.

Its `head_lod0_mesh` carries **24,049 verts — exactly the MetaHuman archetype
head LOD0 count this project already uses**, so it is authored on the same
head we bind against.

### THE ACTUAL NODE SURFACE — this is the party hair API

Full machine-readable dump:
`_verify/20260821_rear/blender_kit_surface_demo.json`, produced by
`scripts/blender/enumerate_groom_blend.py`.

Two authoring stacks exist. The guide-based sets (`Ponytail`,
`Ponytail_braids`, `buns_braids`, `curly_ear`, `curly_strands_top_bun`) all
carry the same five modifiers:

    Set Hair Curve Profile        6 inputs   Replace Radius, Radius, Shape,
                                             Factor Min, Factor Max
    Add Guide Object              3 inputs   Object, Radius
    Shrinkwrap Hair Curves        9 inputs   Factor, Offset Distance,
                                             Above Surface, Smoothing Steps,
                                             Lock Roots, Surface
    Attach Hair Curves to Surface 10 inputs  Surface Object/Geometry,
                                             Surface UV Map, Snap to Surface,
                                             Blend along Curve,
                                             Align to Surface Normal
    Merge Guide and Weight it     3 inputs   Curves_Guides, Radius_guide

The interpolated groom (`Metahuman Curly Hair`, 303 guides -> 31,570 strands)
swaps the last two for `Surface Deform`, `GroomExporter Curly Hair`
(`Radius_guide`) and `voxelyze hair for AO` (`Object`, `AO_debug_material`,
`Exponent`).

**Values that are NOT defaults on the shipped file** — worth knowing before
you change anything: `Radius` 0.1 against a 0.01 default, `Above Surface`
0.0 against 0.5, voxelyze `Exponent` 2.0 against 4.0.

### READING AND WRITING THOSE VALUES IN BLENDER 5.x

This cost four wrong guesses. In 4.x a Geometry Nodes modifier's inputs were
ID properties read as `mod["Socket_2"]`. In 5.2 that raises **"this type
doesn't support IDProperties" for every socket**. The chain is:

    mod["id"]                     TypeError, no IDProperties
    mod.properties                GeometryNodesModifierInterface
    mod.properties.keys()         TypeError, same
    mod.properties.inputs         GeometryNodesInterfaceInputs, NOT iterable
    mod.properties.inputs[ident]  IDPropertyGroup -- no bl_rna, no .value
    ....to_dict()                 THE VALUES

Identifiers come from `mod.node_group.interface.items_tree` (`Input_2`,
`Input_3`, …). The display NAME is not addressable and two sockets may share
one.

### EXPORTING: two preconditions, both of which fail like a broken add-on

**`bpy.ops.groom.buttonexport` is fully scriptable — no UI, no click.**

1. **`node_execution=True`.** `AlembicGroomExporter.execute` gates
   `export_preparation()` on it, and that is what SELECTS the objects.
   `GetCurvesObjects(context)` reads `context.selected_objects`, which is
   empty headless, so with `False` the exporter dies on `curvesObjects[0]`
   with a bare `IndexError`.
2. **Never pass `--factory-startup`.** The add-on installs via user
   Preferences; factory startup unregisters it and a working install then
   reports as missing.

**Variant exclusion is free and lives in the `.blend`.** One export
configuration per style is authored as a node group — `Curly hair` holds a
single Curve Selector, `Metahuman Braid Bun` holds five. Naming the group
excludes every other style, so the filter cannot drift out of step with the
file. Use `scripts/blender/export_groom_abc.py`.

### THE ONE THING STILL BROKEN, so you do not chase it

A custom groom's strands **seat wrongly** on the character. It is not your
authoring and not the export: the binding recipe duplicates a vendor binding
that carries per-strand root correspondence for a DIFFERENT groom. Proven by
a single-variable control over the donor (85,107 px with a clump over one eye
versus a completely bald render, 10.3% of frame apart). Fix is named in
`MORNING_REPORT_3.md`. **Until it lands, judge your Blender work in Blender.**

---

**Status: THE UE HALF IS UNBLOCKED as of 2026-08-20.** The binding step works —
`RECIPES.md` R-GROOMBIND3, ~15 s per groom via
`LandscapeLabTools.build_groom_binding_for_mesh`. The blocker sections below
are now HISTORY; the authoring guidance is unchanged and still correct.
**What remains genuinely unexercised is the ALEMBIC IMPORT itself** — no `.abc`
has ever been put through this pipeline, so your first groom is also its first
real test.

**Superseded status line, kept so the change is visible:** the UE half is NOT
yet proven end to end. Read
[the honest state](#the-honest-state-of-the-ue-half) before spending an
evening in Blender. The authoring guidance below is sound and standard; what
is unproven is the ingest step that takes your `.abc` and puts it on a
character, and that is a UE-side problem, not a Blender one.

Written 2026-08-19 (overnight #2). Companion recipe: `RECIPES.md`
R-GROOMBIND (**retracted — read the retraction**), narrative in `LESSONS.md`
2026-08-19 (overnight #2).

---

## WHY A CUSTOM GROOM AT ALL

The stock MetaHuman wardrobe has 38 hairs and none of them is the reference.
Measured against `hero/reference/hero_example_pic.jpg` across four rendered
trials: the reference is a **shaggy medium** — volume on top, a fringe across
the brow with the brows still visible, ears covered, length to the jaw.

    M_Layered           long, straight, sleek to the chest        too long
    M_SideSweptFringe   fringe, ears covered, jaw length, FLAT    closest
    S_Messy             short crop, ears bare, no fringe          too short
    M_BobMessy          right mass, curtains the brows            gate FAILS

Volume and visible-brows are in tension across the stock set. The reference
threads that needle because it is authored hair. That is the gap a custom
groom closes.

---

## THE AUTHORING CHECKLIST

### 1. Author against the ARCHETYPE head, not against our hero's face

Every stock MetaHuman groom is authored against `SKM_Groom_Head_Legacy01` (or
`Legacy02`) — verified by reading the vendor bindings, which record
`source_skeletal_mesh == target_skeletal_mesh == SKM_Groom_Head_Legacy01`. The
per-character fit is then done by the binding.

**So author on the archetype head and let the fit happen in UE.** Export the
archetype head from UE as the scalp/emitter you groom against.

> **Conditional, and it is load-bearing:** this holds as long as ingest goes
> through the MetaHuman assemble, which is the only route currently proven to
> produce a correct binding. If a future session gets a hand-built binding to
> finish building, authoring directly against the hero's own face mesh becomes
> possible and probably better. Do not silently switch — the two produce
> different grooms.

### 2. Scale: UE is centimetres, Blender defaults to metres

Author at **1 Blender unit = 1 cm**, or apply a **100x** scale on export.
A groom exported at metre scale arrives 100x too large and reads as a
catastrophic explosion rather than as a scale error, which wastes a cycle.

### 3. Hide the emitter before export

Export the CURVES only. An exported emitter mesh arrives as extra geometry in
the groom asset and shows up as a translucent skull-cap over the scalp.

### 4. Groom schema attributes — use the GroomExporter add-on

UE's Alembic groom importer expects the groom schema (`groom_guide`,
`groom_group_id`, and the width/root attributes). Blender's stock Alembic
exporter does not write them. Use the **GroomExporter** add-on so the curves
carry the attributes; without them the import produces a groom with no guides
and the binding has nothing to interpolate.

### 5. GPU Skin Cache — VERIFIED ON THIS PROJECT, 2026-08-19

Groom binding to a skeletal mesh requires the GPU skin cache.

    LandscapeLab/Config/DefaultEngine.ini:48   r.SkinCache.CompileShaders=True

**Checked and recorded rather than assumed** — it is already on, so this is
one thing you do NOT need to change. Note the standing rule that a config file
records what was OVERRIDDEN and not what is in EFFECT; if grooms ever stop
binding, re-verify this against the running editor rather than against this
line.

---

## THE HANDOFF, CONCRETELY

Deliver to `characters/AlpineHero/grooms/source/`:

    <Char>_<Style>_v<N>.abc        the groom
    <Char>_<Style>_v<N>.blend      the authoring file
    notes.md                       what you were going for, in one paragraph

Then `ingest_groom.py --character AlpineHero --slot Hair --style <Style>
--version <N> --abc <path>` — **once the ingest route below is fixed.**

The tool already writes a provenance sidecar recording the `.abc` sha256, the
import settings, the binding target and the colour params, so a party
character's hair is re-derivable from a record rather than from memory.

---

## THE HONEST STATE OF THE UE HALF

**`ingest_groom.py` exists and its Alembic import path is UNEXERCISED** — no
`.abc` has ever been put through it. More importantly, its BINDING step is
refuted:

`GroomLibrary.create_new_groom_binding_asset_with_path` creates a binding
asset that reports every property correctly and **whose build never
completes** — `LogHairStrands: Waiting for groom bindings to be ready 0/1`,
observed on all eight bindings built tonight, with no error and no later
line. The result renders a **bald crown with a clump of strands hanging at
the jaw**: only the free-hanging ends draw, because the roots have nothing to
attach to.

**The only proven route to a correct groom on a character is wardrobe select
-> MetaHuman assemble**, which builds the binding itself.

So the ingest design ruled by the advisor is: import the `.abc` to a
GroomAsset in project content, **duplicate an existing `WI_Hair_*` wardrobe
item and repoint its groom reference at the imported asset**, then wardrobe
select and assemble. Whether that repoint is reachable from Python is
**untested**. If it is not, the honest fallback is: this tool imports and
validates the groom, and the wardrobe-item step is done by hand in the editor,
documented — not papered over.

**What to do first next session:** find out whether a groom binding build can
be forced to completion (a build/rebuild call, a save-and-reload, or a
different creation entry point). That single answer decides whether groom
ingest is a two-second operation or a twelve-minute assemble, for every party
character from here on.
