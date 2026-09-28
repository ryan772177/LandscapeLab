# GAP REPORT — the two concepts against the current library

**2026-08-29.** Every row checked against the library on disk, not recalled.
Four verdicts, per the brief:

| verdict | meaning |
|---|---|
| **SERVABLE NOW** | in the project, placed or placeable today |
| **SERVABLE + INTAKE** | on disk in the vault cache, not yet crossed over — a second R-KIT run, not new work |
| **SERVABLE + MATERIAL** | geometry exists, look is wrong; needs Phase C |
| **NEEDS GENERATION** | nothing in the library and nothing in the pack |

---

## ⭐ THE HEADLINE: THE PACK ALREADY HOLDS MOST OF WHAT I EXPECTED TO AUTHOR

The 2026-08-29 intake took the dependency closure of **15 measured modules**.
The pack holds **489 static meshes**, and the folders I did *not* cross over
turn out to cover most of the concept's architecture:

    Meshes/Houses/MODULAR_ASSETS   96 meshes
    Meshes/Houses/Roofs            10 meshes
    Meshes/Houses/Thatch_Cards     26
    Meshes/Houses/Construction_Pieces 10

Names in `MODULAR_ASSETS` map almost one-to-one onto what the concepts show:
`GableFront`, `GableSet`, `HBeam_LS/MS/S` (the timber upper storey),
`BoardWall`, `BoardedWindow`, `PorchBase`, `LanternPost`, `HouseFence`,
`Outcrop`/`OutcropDoor`/`OutcropShingle`, `RoofBack`, `RoofConst*`, `Corner`,
`FacadeLarge`, `Pole`.

**So several things I would have written down as "needs authoring" are actually
"run the intake again on a wider seed".** That is a much cheaper answer and it
is only visible because the closure walker made a second intake a one-command
operation.

---

## CONCEPT 01 — THE APPROACH

| entity | verdict | evidence |
|---|---|---|
| Conifer forest | **SERVABLE NOW** | `Conifer`, `ConiferPine`, `SpruceSub`, `SpruceSapling` — 219,659 instances placed |
| Meadow grass | **SERVABLE NOW** | `Meadow` species on the grass system |
| Snow-capped peak | **SERVABLE NOW** (shape not guaranteed) | terrain spans 0–1552.5 m with snow layer; the *specific* horn silhouette is not authored and would come from camera choice or terrain work |
| Basin / open ground | **SERVABLE NOW** | the town site is already a basin |
| Terraced village on slope | **SERVABLE + MATERIAL** | 15 kit modules stand and render; look is plaster, concept is stone+timber |
| Chalet form (stone base, timber upper, wide eaves) | **SERVABLE + INTAKE** | `HBeam_*`, `BoardWall`, `Outcrop*`, `Roofs/` — all in the pack, not yet crossed |
| Church w/ onion dome | **⛔ NEEDS GENERATION** | searched the whole pack for church/chapel/dome/tower/spire/bell — **only hit is `SM_OldBellows`**, which is a blacksmith's bellows |
| Wood stacks | **⛔ NEEDS GENERATION** | see below |
| Stream | **⛔ NEEDS GENERATION** (systemic) | see below |
| Track through village | **SERVABLE + MATERIAL** | 838 street slabs exist; they need the continuous-surface re-emission and a dirt/cobble material |

## CONCEPT 02 — INSIDE THE VILLAGE

| entity | verdict | evidence |
|---|---|---|
| Two large framing chalets | **SERVABLE + INTAKE + MATERIAL** | massing from kit modules; balcony/beam/roof from `MODULAR_ASSETS`; material from Phase C |
| Church (detailed) | **⛔ NEEDS GENERATION** | as above. This is the Phase D candidate the brief predicted. |
| Dirt track + cobble patches | **SERVABLE + MATERIAL** | geometry trivial; both are material problems |
| Rivulet + water | **⛔ NEEDS GENERATION** (systemic) | see below |
| River stones | **SERVABLE + INTAKE** | `rock_scatter.py` exists and is proven — but see the finding below |
| Wildflowers | **SERVABLE + INTAKE** | grass system carries varieties; no flower asset declared yet |
| Lanterns (lit) | **SERVABLE + INTAKE** | `SM_LanternPost` is in `MODULAR_ASSETS` |
| Bench | **SERVABLE + INTAKE** | `SM_OldWoodenBench` |
| Crates / barrels | **SERVABLE + INTAKE** | `SM_BarrelOnStand`, plank and board meshes |
| Cart | **PARTIAL — INTAKE + ASSEMBLY** | `SM_WoodenWheelA/B`, `SM_WoodenWheelbarrow`. A wheelbarrow is not the painted cart in the concept; wheels plus planks could compose one, or generate it. |
| Stone arch | **SERVABLE + INTAKE** (probable) | `Outcrop*` and `Construction_Pieces` are candidates; not confirmed by eye |
| Wood stacks | **⛔ NEEDS GENERATION** | searched `stack|pile|chop|split` across 489 meshes — **only hit is `SM_PileOfChains`**. The pack has loose planks and boards but no stacked-firewood asset. |

---

## ⛔ THREE REAL GAPS, RANKED BY WHAT THEY COST

### 1. The onion-dome church — NEEDS GENERATION, and it is the focal anchor

Confirmed absent: a search for `church|chapel|dome|tower|spire|bell` across all
489 meshes returns `SM_OldBellows` and nothing else. It is the **focal anchor of
both concepts** — the thing the eye lands on in 01 and the subject of 02.

**This is the Phase D candidate**, exactly as the brief anticipated. It is also
the *right* test case for the forge: highly specific, non-modular, one-off, and
useless to buy generically. If generation cannot serve this, it is hard to say
what it is for.

### 2. Wood stacks — NEEDS GENERATION, and they are cheaper and more valuable than they look

The single most repeated object in concept 02: at least four distinct piles, in
the undercroft, beside the church, on the right. **They are what makes the place
read as inhabited rather than merely built.**

Nothing in the pack. But a stacked woodpile is *geometrically trivial* — a
lattice of cylinders — and could be authored in headless Blender in an
afternoon, or composed procedurally from the pack's existing plank meshes.
**I would not spend a generation slot on this.** It is the strongest candidate
for the authored-module route, and it is a good second forge test precisely
because it is easy: if the forge cannot beat "author a woodpile in Blender",
that is a useful negative result.

### 3. Water — NEEDS A SYSTEM, NOT AN ASSET

Both concepts carry running water. **This project has never used water.** The
engine supports it (`WaterBody` classes are in the 5.8 stub, 256 references),
but there is no water in any recipe, no shoreline handling, no interaction with
the landscape material or the navmesh.

**This is a system-shaped unit, not an asset-shaped one**, and it should not be
smuggled into the concept loop as though it were a prop. It deserves its own
brief. Concept 01 can be built without it (the stream is a minor background
element); concept 02 cannot be fully matched without it.

---

## ⚠ A FINDING THAT IS NOT A CONCEPT GAP, AND IT SURPRISED ME

**`recipes/alpine_8k.json` declares NO rock scatter species — the list is
empty.** `rock_scatter.py` is built, proven and has a talus-deposition field;
`recipes/alpine.json` (the pre-8K world) declares ten species. The 8K world
inherited the machinery and none of the content.

So the river stones, scree and boulders the concepts show are **not "servable
now"** as I first assumed — the tool is ready and the recipe is empty. That is a
declaration gap, cheap to close, and it would have been invisible if I had
answered from the tooling instead of opening the recipe.

---

## WHAT THIS MEANS FOR PHASE B

The loop can build concept 01 today at greybox-plus fidelity: terrain, forest,
meadow and a terraced village of kit modules, with **two** counted stand-ins —
the church and the wood stacks. That is a real test of the loop rather than a
formality, because the delta list will be dominated by *material* and *scale*,
which are exactly the fixable-by-recipe categories the loop is meant to shrink.

Concept 02 should **not** be the loop's first subject. It is the detail view;
its delta would be dominated by the church and by water, both blocked on
Phase D and on a system that does not exist. It is the right *second* subject,
once the forge has produced a church.

## OWED BEFORE PHASE B STARTS

1. **A second kit intake** on a wider seed — `MODULAR_ASSETS`, `Roofs`,
   `Construction_Pieces`. One command; the closure walker already exists.
2. **A ruling on rock species for the 8K world** — the empty list above.
3. **Your sign-off on the reading**, which is Gate A.
