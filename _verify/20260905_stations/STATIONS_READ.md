# The benchmark stations, rendered — and three of four do not show what they claim

**2026-09-05.** Rendered on request, so briefs are scored against real frames.

## FIRST: THERE ARE FOUR, NOT THREE

There is no artefact anywhere in the repo called a "benchmark camera". The
closest thing — and I believe the intended thing — is the **perf spline** in
`recipes/perf_budgets.json`: a FIXED, DERIVED route of **four** stations that
exists so numbers are comparable across sessions.

    plaza        [-210800.0, 278800.0]  yaw -12.8  pitch -2.0
    main_street  [-204847.3, 278048.0]  yaw -12.9  pitch -2.0
    treeline     [-153506.0, 265800.0]  yaw -12.8  pitch -2.0
    vista        [-329971.0, 305839.0]  yaw -12.8  pitch -4.0

    eye_height_cm 175.0     level /Game/Alpine8K

Ground traced with `perf_flythrough.py --dry-run`, which is the tool that
derives them; the heightmap agrees with the trace to **0.4 cm** at plaza and
19.7 cm at main_street (the street slab sits 19.7 cm proud of terrain).

**No renders existed at these stations.** The 2026-08-29 baseline is numbers
only — 300 frames per station, GPUTime/GameThread p90 — so these five frames
are the first pictures of the route.

## ⛔ AND FOV AND RESOLUTION ARE DECLARED NOWHERE

Not in the spline, not in `perf_flythrough.py`, not in the baseline JSON. The
stations declare xy, yaw, pitch and eye height — and not the two parameters
that most directly determine how much geometry is in frame.

**So the ratified budgets are not reproducible from the record.** A GPUTime
p90 at 90° horizontal is not the same measurement as one at 60°, and nothing
says which was taken.

These frames were rendered at **2560×1440, FOV 90 horizontal**. The resolution
is the declared target; **the FOV is my choice and is declared here because it
had to be chosen.** They are therefore NOT guaranteed to match the conditions
the budgets were measured under.

## WHAT THE FRAMES SHOW

| station | frame | verdict |
|---|---|---|
| `plaza` | `station_plaza.png` | ✅ **USABLE.** Town centre: untextured grey/tan boxes with gable roofs, conifers, meadow, peak visible between buildings. This is the "762 engine Cubes" gap, seen plainly. |
| `main_street` | `station_main_street.png` | ⛔ **UNUSABLE.** A dark blue dithered field — the camera is inside geometry. |
| `treeline` | `station_treeline.png` | ⚠ **NOT WHAT IT CLAIMS.** Its `_what` says *"in full-density forest"*. The frame is a near-vertical ROCK FACE filling ~85% of it, with a few trunks top-left. The camera is pressed against terrain. |
| `vista` | `station_vista.png` | ⚠ **NOT WHAT IT CLAIMS.** Its `_what` says *"looking back over the town to the peak — the long-range readability case"*. The frame shows near-field conifers and rock. **Neither the town nor the peak is visible.** |

**One station in four delivers the view its own description promises.**

## WHY THIS MATTERS BEYOND THE PICTURES

The four stations carry **ratified perf budgets** (`gates.ratified: true`,
enforced by `check_perf.py`):

    GPUTime p90 ms   plaza 12.0   main_street 8.0   treeline 10.0   vista 12.5

**`main_street` has the lowest GPU budget of the four**, and its camera cannot
see out. A camera inside geometry renders almost nothing, which is exactly
what a low GPU cost looks like. The same doubt applies to `treeline`, framed
into a cliff. Those budgets may be measuring occlusion rather than the zones
they name.

I am **not** claiming the budgets are wrong — the baseline may have been
captured at a different FOV where these framings differ. I am claiming they
cannot be checked, because the FOV is unrecorded.

## main_street: WHAT IT IS NOT

Root cause **not established**. Ruled out by measurement:

* **Not inside a building.** Exact oriented-rectangle test against all 303
  plan footprints: outside every one. (My first pass used a half-diagonal
  circle and wrongly said INSIDE; the exact test refuted it.)
* **Not under a roof.** Same test against all 303 roof footprints.
* **Not underground.** Heightmap gives terrain 18695.6; the traced street top
  is 18715.3; the eye is 18890.3 — **1.95 m above ground.**
* **Not fixed by height.** Re-shot 15 m higher
  (`station_main_street_raised.png`): still enclosed, now flat grey-tan with a
  hard diagonal edge.
* Nearest town actors in the LIVE level are `City_Bldg_021` / `City_Roof_021`,
  between 0 and 25 m away — consistent with the plan's 8.2 m.

**Leading remaining candidate: a foliage instance.** The two
`InstancedFoliageActor` bounds contain the point, the world carries 219,659
instances, and the plaza frame shows conifers growing between the buildings. A
trunk would explain enclosure at 1.95 m *and* at 16.95 m. The flat grey-tan
with a straight edge argues against it, so this is a candidate and not a
conclusion.

**One probe would settle it:** query foliage instance transforms within ~5 m
of the station. Not run — the editor was closed first.

⚠ A standing caveat that cuts the other way: `city/alpine_basin_town_plan.json`
is the repo's **known-divergent** artefact, carrying a `_divergence_note` and
failing `--reproduce`. Every "not inside a building/roof" result above is
computed from **that plan**, so it describes the plan's town, not necessarily
the live one. The live-level probes agree so far, but the plan is not
authority here.

## WHAT I RECOMMEND

1. **Declare FOV and render resolution in the spline** and re-baseline. Until
   then no perf number is reproducible.
2. **Re-derive `treeline` and `vista`** so they show what they are named for,
   or rename them for what they actually frame. Bearings were computed, never
   traced — occlusion has never been checked on this route, which is the same
   gap the concept loop lists under `NOT_MEASURED`.
3. **Settle `main_street`** with the foliage probe before trusting its 8.0 ms.
