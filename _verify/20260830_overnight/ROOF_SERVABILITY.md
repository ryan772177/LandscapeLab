# Ruling 4 — roof servability as a planner constraint

## THE RESULT

| | BEFORE (uniform 7–15 m) | AFTER (biased) |
|---|---|---|
| buildings | 303 | **348** |
| servable by ONE kit roof | **132 (43.6%)** | **325 (93.4%)** |
| footprint X mean / sd | 10.90 / **2.30** | 9.17 / **1.39** |
| footprint Y mean / sd | 11.78 / **2.88** | 9.32 / **1.66** |

**+49.8 percentage points of servability.** The plan's own per-building
`roof_servable` record agrees with an independent audit — 325 both ways, from
two different code paths.

## ⚠ THE COST, MEASURED RATHER THAN GLOSSED

**Size variety falls ~40%** (sd 2.30 → 1.39 in X, 2.88 → 1.66 in Y) and the
mean footprint shrinks 1.7 m. That is not incidental — **every servable target
is 7.5–10.2 m**, because only five of the ten roof pieces fall inside the
recipe's own 7–15 m range at all. A full bias would erase the 10–15 m end of
the town entirely.

`bias: 0.85` is why some variety survives. It is a dial, and the number above
is what it currently buys.

**The town also grew from 303 to 348 buildings** — smaller footprints pack more
densely, so fewer are rejected for overlap. More houses, each slightly smaller.

## THE REMAINDER, SPLIT AS RULED

    23 of 348 not servable by a single piece
     6 may COMPOSE a roof from other kit pieces  (landmark_compose_max)
    17 stay COUNTED GREYBOX

The six composition candidates are the largest — all at or near the 15 m cap,
where composing is most worth the effort:

    11.28 x 15.00      10.47 x 15.00      11.60 x 15.00
    11.04 x 15.00       9.84 x 15.00      14.27 x 15.00

The greybox remainder spans 11.84–15.00 m on its longest axis.

## ⛔ THE NEW PLAN IS **NOT** THE PLACED TOWN — and that is a gated decision

Written to **`city/alpine_basin_town_plan_roofbias.json`**, deliberately *not*
over the canonical path. The town standing in `/Game/Alpine8K` was placed from
the previous plan, and that world is behind the live-town gate.

So there are now two plans, and the divergence is explicit rather than silent:

- `city/alpine_basin_town_plan.json` — **describes what is actually placed**
- `city/alpine_basin_town_plan_roofbias.json` — describes what the ruled
  constraint produces

**Promoting the new plan and re-placing the town needs your go-ahead**, because
it replaces 303 standing buildings with 348 different ones in the live world.
The planner change itself — recipe field, code, audit — is done and permanent
regardless.

## ONE DECLARATION OF THE FIT TEST

`scripts/roof_servability.py` owns "±20% on both axes, a roof may rotate 90°"
and both the planner and the audit call it. Previously the audit carried its
own copy, which is the two-lists-one-badly-stored defect that has already cost
this project twice this week.

---

# ⚠ RULING 4 IS NOT FINISHED: THE ±20% BAR PASSES A VISIBLE MISFIT (2026-08-30, from the iter0 render)

**Ruling 4 made roof servability a planner constraint and the number moved
43.6% → 93.4%. The concept render then showed that "servable" and "seats
correctly" are not the same question, and only the second one is visible.**

## THE EVIDENCE

The concept stage builds 16 chalets at `chalet_footprint_m` 10.0 × 8.0 m and
roofs them with `SM_House02_Roof`. In the frame every roof reads as a drooping
flap rather than a seated gable. Measured against this module's own test:

    SM_House02_Roof span      8.99 x 9.17 m   (Free/_measured/, native)
    chalet footprint         10.00 x 8.00 m
    ratio span / footprint     x 0.90    y 1.15

    X: the roof is 1.01 m NARROWER than the walls  -- recessed ~0.50 m a side
    Y: the roof is 1.17 m WIDER   than the walls  -- overhangs ~0.58 m a side

    roof_servability.fits(10.0, 8.0, (8.99, 9.17), 0.20)  ->  True

**A roof narrower than its house on one axis and wider on the other is exactly
the splayed silhouette, and the bar passes it.** ±20% independently on each
axis admits a 10% shortfall and a 15% overhang *at the same time*, and the two
compound visually instead of cancelling.

**This is the servability question failing at the seating step, not a separate
defect** — which is why it belongs to ruling 4's implementation rather than to
the concept loop. The planner that biases footprints toward servable roofs is
the same code that must seat a roof to its wall bounds.

## THE THREE THINGS TO FIX, IN ORDER OF WHAT THEY COST

1. **The tolerance is per-axis and unsigned, so it cannot see this.** A
   pairing that is short one way and proud the other passes every check while
   looking wrong. Candidate: bound the SIGNED residuals jointly — an overhang
   and a shortfall on perpendicular axes should not both be spent in full.
   The number wants deriving from renders, not choosing; ±20% was never
   validated against a picture.

2. **`servable_by` returns the FIRST fit from a list sorted ascending by max
   span** (`roof_spans` sorts by `max(x, y)`), so it systematically selects the
   *smallest* roof that passes rather than the best-fitting one. As a boolean —
   which is all `plan_city.py:430` currently needs for `roof_servable` — that
   is correct. But it also records `roof_candidate`, and the moment anything
   PLACES that candidate it will place the most undersized legal roof every
   time. **Forward hazard, not yet a live defect**, because the town is still
   engine primitives. Fix before the kit town is placed: return the minimum
   residual, not the first match.

3. **`concept_build_payload.txt` never asks this module anything.** It takes a
   hardcoded `roof_package` and spawns it at native scale on a box scaled to
   the recipe footprint (`_r2` gets no `set_actor_scale3d`; wall and roof do
   share yaw, so this is not a rotation fault). Either drive the roof choice
   through `servable_by` or scale the roof to the wall bounds — but the
   concept stage should not be the one place that answers the fit question its
   own way.

## WHAT THIS SAYS ABOUT THE MEASUREMENT

`roof_servability.py` is a correct single declaration of a test that is
**weaker than it reads**. The audit and the planner agree with each other —
325 both ways, from two code paths — and both agree with a bar that a rendered
frame disagrees with. **Two instruments sharing a definition are one
measurement** (non-negotiable 0), and here the shared thing was the tolerance
itself. The frame was the independent instrument, and it took a picture to
find it.
