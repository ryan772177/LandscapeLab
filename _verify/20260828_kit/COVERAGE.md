> # ⛔ CORRECTION, 2026-08-29 — THE HEIGHT RULING BELOW RESTS ON A FALSE PREMISE
>
> **Read this before acting on §"THE RULING THIS NEEDS".** That section says
> changing `storey_m` to 2.00 *"visibly shortens the town: 2/3/4-storey buildings
> go from 6.4 / 9.6 / 12.8 m to 4 / 6 / 8 m"* — a 33% cut across 303 buildings.
>
> **That assumes the planner preserves STOREY COUNT. It does not.**
> `scripts/plan_city.py:392-395` computes a **continuous** height from the
> falloff and then snaps it to a storey multiple:
>
>     f  = d / R_cm
>     h  = (hc + (he - hc) * f) * 100          # continuous, 14.0 m -> 6.5 m
>     storeys = max(1, int(round(h / (storey_m * 100))))
>     h  = storeys * storey_m * 100            # snapped
>
> So `storey_m` is a **quantisation step**, not a floor height that multiplies a
> fixed storey count. Changing it re-snaps the same continuous heights to a
> finer grid. Measured on the shipped plan, 2026-08-29:
>
>     positive control   heights reconstructed from building positions
>                        reproduce the shipped plan EXACTLY, 0 mismatches of 303
>
>     storey_m 3.2 (now)   6.4 / 9.6 / 12.8 m      51 / 164 / 88
>     storey_m 2.0         6 / 8 / 10 / 12 m       19 / 73 / 113 / 98
>
>     mean height        9.99 m  ->  9.91 m        -0.8%,  NOT -33%
>     max snap error     1.59 m  ->  1.00 m        it gets MORE faithful
>     distinct heights   3       ->  4
>
> **The change is nearly free and lands every building on a whole number of
> 2.00 m wall courses.** It is still the operator's call because 303 silhouettes
> move, but the cost being weighed is −0.8% mean height, not −33%.
>
> Everything else in this file — the footprint tiling result, the module
> measurements, the gable-pivot trap — is unaffected and stands. The body below
> is left verbatim as the record of what was believed on 2026-08-28.

---

# The coverage gate cannot run as specified — and here is what it was asking

**2026-08-28.** Ruling 2's gate: *full kit vs the 303 buildings at ±20% / ±35% /
±50%, stop and report below 60% at ±20%.*

**It has no denominator here.** The gate asks how many planned buildings a KIT
MESH fits within a tolerance. The Medieval Village Megascans Sample contains **no
whole-house meshes** — confirmed by two independent listings, the OneDrive
project skeleton's folder names and the vault cache's actual assets. Every
architectural asset is a wall, door, gable, roof piece, beam, porch or shutter.
`Content/Meshes/Houses/House1/` holds exactly one asset and it is
`SM_Plank_Base1`, a part.

So there is nothing to fit. The question the gate exists to answer — *must the
town re-form?* — still has an answer, and it is a better one.

## What the modules actually are, measured live

    walls    1.00 · 1.50 · 2.00 · 3.00 m wide,  ALL 2.00 m tall,  0.16-0.22 thick
    corner   1.03 x 1.03 x 2.00
    doors    1.00 · 1.51 · 2.00 · 3.00 m wide,  2.00 m tall
    gables   4.82 x 2.18  and  4.30 x 2.76

Full table with triangle counts and pivots: `ASSETS.md` and
`Free/_measured/kit_medievalvillage.json`.

## COVERAGE, in the terms a modular kit actually has

A footprint is not MATCHED to a mesh, it is BUILT from modules. So the two
questions separate, and they get opposite answers.

### Footprint: 303 of 303 — 100%

Snapped to 0.5 m and tiled from {1.0, 1.5, 2.0, 3.0}:

    exactly tileable on BOTH axes    303 of 303   (100.0%)

Every planned footprint from 7.03 m to 14.95 m can be built exactly. This is not
a near-miss tolerance like ±20%; it is exact, because 1.0 and 1.5 together reach
every half-metre.

### Height: 0 of 303 — and this is the whole finding

    planned height   count   courses at 2.00 m      verdict
      6.40 m           51        3.20               OFF GRID
      9.60 m          164        4.80               OFF GRID
     12.80 m           88        6.40               OFF GRID

    recipe storey_m  3.20        module height  2.00

**Not one building height is a whole number of courses.** The cause is a single
recipe field: `buildings.storey_m` is 3.20 m and the kit's wall course is
2.00 m, so every height the planner emits is off-grid by construction.

## ⛔ THE RULING THIS NEEDS, AND WHY I DID NOT TAKE IT

Making heights land on the grid means changing `storey_m` to 2.00 (or a multiple),
and that **visibly shortens the town**: 2/3/4-storey buildings go from
6.4 / 9.6 / 12.8 m to 4 / 6 / 8 m. Every roof, eaves line and silhouette moves.

Whether that is right is a judgement about the world, not a measurement:

- **2.00 m is plausible as a medieval wall course** — floor-to-ceiling in
  vernacular building of that period is commonly 2.0–2.5 m, and 3.2 m is a
  modern storey. The kit's own dimension is evidence about the architecture it
  depicts.
- **But it is the operator's town**, and a 33% height reduction across 303
  buildings is exactly the kind of change the coverage gate existed to put in
  front of you before it happened.

Three readings, none taken:

1. **`storey_m` → 2.00.** Heights become 4 / 6 / 8 m. Kit-native, shortest town.
2. **`storey_m` → 2.00 but add a course**, so 3/4/5 courses give 6 / 8 / 10 m —
   closer to the current silhouette while staying on grid.
3. **Keep 3.2 and let the top course overhang or be cut.** Rigid modules make
   this ugly; recorded because it is an option, not because it is a good one.

## What else is owed before the planner is written

- **The gables' pivots are NOT base-centred** (−27.8 and −14.9 cm), correctly,
  because a roof-end piece seats at eaves height. Anything that assumes uniform
  base-centred pivots will place them 15–28 cm wrong.
- **Materials and textures have not been migrated.** Only 15 meshes crossed, as
  a measurement probe. The remaining intake is ~800 MB for these alone.
- **No frame cost has been measured.** Arithmetic only: ~9 modules per house at
  ~12k Nanite triangles ≈ 110k per house, ≈ 33M across 303. Nanite's territory,
  but unmeasured.
