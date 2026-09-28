# Streaming at mounted speed: the instrument is built, the number is not obtained — 2026-08-27

The owed item was *"PIE residency at mounted speed. The editor upper bound is
measured and fits; the runtime figure is arithmetic, not observation."*

**It is still not observation, and this records exactly why** rather than
leaving it as "not attempted" — which is what it looked like this morning.

## What was built and does work

`walk_character.py` gained two options.

**`--speed-cm-s`** overrides `MaxWalkSpeed` on the PIE pawn. PIE runs against a
duplicate world, so nothing persists and no recipe is touched. It is gated
twice, and both gates fired correctly:

| gate | what it catches | result |
|---|---|---|
| property read-back within 0.5, before the walk | the write did not land | passed |
| achieved speed from the trace ≥ 0.9 of commanded | the write landed and the pawn never moved at it | **p50 1800, max 1800 = 1.00** |

The second gate is the one that matters. `max_walk_speed` reading back 1800
proves the value reached the component; only the trace proves the character
travelled at it. Acceleration, slope, or root motion could each have capped it
while the property read perfectly — non-negotiable 8.

**`--residency-every`** samples resident `LandscapeStreamingProxy` and
`InstancedFoliageActor` counts on its own coarser cadence, deliberately not on
the 4/s movement cadence: `get_all_actors_of_class` iterates the world, and at
4/s the instrument would be a material part of the load it exists to measure.

## Why the number is not here

**The walker stalled both times, and both stalls were correct.**

    tag                   yaw   speed        travelled   stalled for
    stream_control_600     35    600 cm/s       29.2 m      291 s
    stream_mounted_1800   259   1800 cm/s       58.4 m      175 s

The first ran into the **landmark** — an 11 × 11 × 34 m tower whose centre is
1.8 m beyond where the pawn stopped, i.e. contact at its wall. That is not a
defect: `PlayerStart` is aimed at it on purpose, because it is the first thing a
player should see. A straight-line walker has no way around it.

The second used the best bearing available, and still hit a building.

## The town blocks every straight line out of it — measured, not assumed

`scripts/find_clear_heading.py` marches each bearing against the 1,446 planned
footprints, inflated by the pawn's 34 cm capsule so contact happens at the wall:

    from the PlayerStart, to 1200 m
      including street slabs      0 of 360 bearings clear   first blocker at 57 m
      excluding street slabs      9 of 360 clear (2.5%)
      widest clear arc            3.0 deg, centred on bearing 259

**A 3° arc is 2.6 m wide at 50 m.** An unsteered walker drifts more than that,
which is precisely what happened: bearing 259 was chosen from this tool and the
pawn still contacted a building at 58.4 m.

Streets are reported separately and excluded only on an explicit opt-in, because
"the walker steps onto a low slab" is a judgement about walkability that this
tool otherwise refuses to make.

## So the honest position

- The **instrument** is built, gated in both directions, and proven at 1.00 of
  commanded speed.
- The **measurement** requires a start point outside the settlement, or a walker
  with steering. Neither is a large piece of work and neither was in scope
  today.
- The residency numbers that WERE collected — 3–4 landscape proxies, 10–11
  foliage actors — are **residency at rest inside a town**. Quoting them as
  "streaming at mounted speed" would be the misleading-denominator class
  (non-negotiable 22): arithmetically true, and an answer to a question nobody
  asked. They are not the owed figure.

## What would close it

Spawn on reachable ground outside the town — the reachability lattice has
36.53 km² of it and `reachability.py` can name a row — and walk from there. The
tooling for both halves now exists; only the start point is missing.
