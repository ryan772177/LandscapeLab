# ⛔ SUPERSEDED — session report, superseded by STATE.md. History only, never a source.

# MORNING REPORT 3 — 2026-08-21

**The one-line answer to the question you asked: the remaining gap is
AUTHORING, not reference.** Nothing about the hero's look is now limited by
what we can see of him. Two views are registered and measured, the Blender
round trip runs end to end without a human, and what is left is that a
custom groom's strands do not yet land on the right part of the head.

---

## THE LEAD

    _verify/20260821_blender/blender_curly_null_20260821T061140Z.png
    _verify/20260821_blender/blender_curly_donorB_20260821T061812Z.png
    _verify/20260821_blender/blender_curly_NOBINDING_20260821T062216Z.png

These are not a hero portrait, and the brief's Stage A said they would not
be: the null export is UNMODIFIED demo content and likeness was explicitly
not the test. **They are the round-trip proof, and they show it working up
to the last link.** A groom authored in Blender is on the hero's head, in
the world, rendering real strands with real shading — sitting in the wrong
place.

**Stage B never opened, so there is no score trajectory table.** Saying so
plainly rather than presenting Stage A's numbers in a shape that implies
authoring happened.

---

## STAGE A VERDICTS

| Step | Verdict |
|---|---|
| Blender discovery | **5.2.0 LTS**, default path, headless |
| `groom.blend` (Fab kit) health | **NOT A GROOM FILE AT ALL** |
| Demo `.blend` health in 5.2 | **PASS** — 39 node groups, 0 undefined nodes |
| GroomExporter headless | **PASS** — registers and exports with no UI |
| Null export | **PASS** — 81,420,036 bytes |
| Import to UE | **PASS** — GroomAsset, count verified independently |
| Bind | **PASS** mechanically — 2.67 s, curve retention 1.0 |
| **Strands seated** | **FAIL** — this is the blocker |

### The Fab kit is empty

`groom.blend` is **Blender's default startup scene** — Camera, Cube, Light,
98 KB. Not "predates 5.x and is broken": there is no hair in it. The demo
file becomes the base, which is where the brief pointed anyway.

### The demo file is healthy, and better than expected

11 Curves objects, two complete hair sets, 39 node groups with **zero**
undefined node types and nonzero evaluated strand counts throughout. Its
`head_lod0_mesh` carries **24,049 verts — exactly this project's MetaHuman
head LOD0 count**, so it is authored on the same archetype we bind against.
That fact is the reason the remaining fix looks cheap.

### The export world: fully scriptable, no attended click

The fallback the brief was braced for is not needed. Two preconditions had
to be read out of the add-on's source, and both fail like a broken add-on:

- **`node_execution=True`** gates `export_preparation()`, which is what
  SELECTS the objects. With `False` the exporter sees an empty selection and
  dies on `curvesObjects[0]`.
- **No `--factory-startup`**, or the add-on unregisters and a working
  install reports as missing.

`GetCurvesObjects(context)` reads `context.selected_objects`, so the UI had
been supplying a precondition by hand.

**Variant exclusion came free and is well-shaped.** The demo authors one
export configuration per style as a node group — `Curly hair` holds a single
Curve Selector, `Metahuman Braid Bun` holds five. Naming the group excludes
every other style, so the filter lives in the `.blend` and cannot drift out
of step with it.

---

## THE BLOCKER, AND THE CONTROL THAT LOCATED IT

R-GROOMBIND3 binds stock hair by duplicating an already-built vendor binding
and RBF-baking onto our face. It works on all 36 stock hairs. Given an
`OverrideGroom` parameter so the cargo can be a custom groom, it builds,
retains every curve, assigns — and seats the strands wrongly.

Single variable, the donor binding:

    donor Hair_L_Straight   85,107 px at 52.6x floor, crown 10%
                            a clump hanging over one eye, bald crown
    donor Hair_S_BuzzCut    completely bald
    difference              10.3% of the frame

**The donor alone decides whether and where a custom groom's strands land.**
The duplicated binding carries per-strand root correspondence belonging to
the DONOR's groom, which has a different curve count and root set. Duplicating
a donor is right for a stock groom, whose binding already matches it, and
structurally wrong for a custom one.

**The presence gate called the bad render PRESENT at 52.6x the floor.**
Present, real, reproducible, and hanging over an eye.

---

## THE NAMED MORNING FIX

Advisor-ruled, bounded, and it is a C++ change plus one rebuild (~20 s) and
an editor restart:

> Construct a **fresh** `UGroomBindingAsset` with `SourceSkeletalMesh` = the
> **archetype head** and `TargetSkeletalMesh` = the fitted face, and **drop
> the RBF re-bake** on that path. With a correctly sourced binding, `Build()`
> owns the deformation; baking on top would deform twice.

The 24,049-vertex match says the custom groom's roots are plausibly already
in archetype space, which is exactly what such a binding expects.

**Why it was not attempted tonight.** The advisor attached a condition: run a
zero-rebuild diagnostic first — assign the groom with **no binding** and
render. Coherent strands on the scalp would confirm archetype-space roots and
justify the rebuild; a displaced clump would kill it.

**The render came back completely bald — neither branch.** An unbound groom
on a MetaHuman GroomComponent draws nothing at all, so the test's premise
does not hold on this component and its outcome carries no information about
the groom. That is *"I could not look"*, not *"I looked and the groom is
wrong"*, and treating it as a verdict would have been the third wrong root
cause on this problem. The condition for attempt 3 was never met, so the
track is parked at two attempts exactly as the brief specifies.

---

## STEP 0 — THE REAR REFERENCE IS REGISTERED

Adopted at hash equality (`ebbe21b7…`) into
`hero/reference/hero_example_pic_rear.jpg`, declared in
`characters/registry.json` beside the frontal, and scoped: **the frontal
stays primary; the rear governs only what the frontal cannot see.** Neither
is a colour target — colour stays anchored to the ruled durable-surface
values.

Constraints measured **once** and recorded, by a new `rear_metrics.py` that
is deliberately **one implementation for both the reference and the render**
(a rubric with a separate path per side is two lists that must agree):

    taper_ratio     0.5533   the nape is 55% of the crown width
    edge_roughness  27.9648  perimeter / sqrt(area), dimensionless
    width profile   0.38 -> 1.00 over the upper half, 0.42 at the nape

`taper_ratio` is the metric worth having: a blunt bottom edge reads near
1.0, so it separates *short at the back* from *tapered at the back* — the
distinction the brief names and the one an eye judges badly. Every metric is
scale-free or normalised by head height, because the reference is a
1375×768 portrait and our renders are 2048×2048. **The mask was dumped as a
PNG and looked at before any number was used.**

---

## RUBRIC CAVEATS, RANKED BY SUSPECTED DIVERGENCE

Stage B did not run, so these are caveats on the rubric as built rather than
on any score it produced:

1. **`edge_roughness` conflates styling with strand count.** A denser groom
   of the same shape will score rougher. Against a reference that is a
   generated portrait, not a photograph of strands, this is the number most
   likely to reward the wrong thing.
2. **`taper_ratio` depends on the mask's bottom edge**, which is exactly
   where hair meets collar and shadow. It is the most robust of the three on
   the reference and the least robust on an in-world render with a dark
   forest behind the nape.
3. **Colour is deliberately outside the rubric** and must stay there. Both
   references are portrait-graded.

---

## A DEFECT IN MY OWN TOOLING, WORTH KNOWING

When the named destination did not exist, my import payload resolved the
imported groom "by TYPE" — it scanned the directory for a GroomAsset. After a
**failed** import it found an unrelated pre-existing groom and reported its
75,005 curves as the import's result. Only the independent curve count caught
it, by a factor of 2.4.

It now snapshots the directory before importing, considers only NEW assets,
and refuses rather than choosing when more than one appears. **A fallback
that searches by type will eventually find something, and finding something
is not finding the thing.**

---

## SEPARATELY — A HARD-FLOOR HAZARD FOUND EARLIER TONIGHT

The groom bind **dirties vendor content**: 48 dirty packages after a
catalogue run, all 48 under `/MetaHumanCharacter/Optional` — the source
grooms' own cards and helmet static meshes, which `DuplicateObject` does not
deep-copy.

They are dirty **in memory** and clean on disk: all 1,387 vendor groom
uassets still carry their 2026-08-15 install mtime. They survived because
every editor close in this run happened to be a discard, and the last was a
**force-kill**, normally the outcome you apologise for. A clean shutdown
would have offered to save engine plugin content in Program Files.

**Posture, now written into the recipe: DISCARD on every close while that
call is in the code.** A C++ comment of mine claimed the opposite and has
been corrected in place.

---

## THE PARKED EYE-COLOUR CHECK: STILL UNVERIFIED, AND NOW WITH THE REASON

I took the opportunity of a render with a clearly lit, open eye and measured
the iris. **It cannot be measured at this lighting**, and the crop
(`_verify/20260821_blender/eye_crop.png`) shows why: the upper lid casts a
hard shadow across the entire eye opening, so the darkest 5% of that region
reads **(0.0, 0.0, 0.0)** — pure black. That is the shadow, not an iris.
Reference iris is **(26, 20, 17)**, which is dark enough that shadow and
target are not separable here at all.

**Confirmed on a SECOND, independent framing.** The close catalogue frames
(dist 60) put the eye large and well within frame — the contact sheet tiles
show it clearly — and the iris is *still* under the lid shadow, with only the
sclera catching light (`eye_crop4.png`). Two framings, same answer, so this
is a property of the sun angle and not of one camera.

**So the blocker on eye colour is the LIGHTING, not the asset and not the
parameter.** It needs the presentation lighting rig that is already on the
board as its own item, or a capture at a sun angle that puts light in the
eye. Recorded as could-not-measure rather than left as a vague open item —
and specifically NOT recorded as "the eye is black", which is the number a
broken measurement would have produced.

## THE CATALOGUE NOW HAS ITS SECOND SHEET

    _verify/20260820_catalogue/hair_catalogue.png        wide, dist 110
    _verify/20260820_catalogue_close/hair_catalogue_close.png   dist 60

24 short styles re-shot at the framing that resolves them. The close sheet
confirms the gate rather than contradicting it: `BaldingStubble` (crown 32%)
and `RecedeMessy` (**SCALP-BALD, crown 10%**) both show genuinely bald domes,
so the crown check is describing those styles correctly — a *receding* style
reading SCALP-BALD is the metric working, not failing.

**A third instance of the same defect turned up in the sheet builder.** Its
`CROP = (430, 60, 1620, 1420)` is tuned for the wide framing; applied blind
to a dist-60 frame it crops into the forehead, and the first close sheet came
out a catalogue of *hairlines*. Rows now carry their framing and the crop
asks. Same shape as the hardcoded distance, one layer up: **a constant that
silently assumes a framing nobody told it about.**

## BLENDER_HANDOFF.md IS REWRITTEN TO THE MEASURED NODE SURFACE

It led with "the Alembic import is genuinely unexercised", which stopped
being true tonight. It now opens with the measured round trip, the real
modifier stacks and their non-default values, the Blender-5.x path for
reading and writing Geometry Nodes inputs (four wrong guesses' worth), the
two export preconditions, and a warning not to chase the seating bug from
the Blender side. Old sections kept beneath, so the change is visible.

## THE SINGLE RECOMMENDED NEXT RULING

**Authorise the fresh-binding route and, with it, one deliberate decision
about what the custom groom is FOR.**

The mechanism question is answered and bounded. The open question is scope:
the round trip currently justifies itself on a demo curly hair nobody wants
on this character. Before Stage B's authoring loop is worth its cost, rule
whether the target is (a) reproduce the reference cut in Blender from
scratch, or (b) use the round trip only to fix what stock hair cannot do.
The rear reference now makes either judgeable — which it was not yesterday.

---

## COMMITS

    7ae43e5f  the 38-hair catalogue, and what opening it found
    6eb36478  the twenty bald styles were my framing
    f5ad92ee  Stage A: rear reference, both .blends, the 5.x knob API
    a34f6ad9  the Blender export runs headlessly
    61337b2c  the round trip closes except for where the hair lands

Tree clean at every track switch. Master never written. Both `.blend` files
and both reference images untouched — every read is read-only by
construction, and the export script contains no save call.
