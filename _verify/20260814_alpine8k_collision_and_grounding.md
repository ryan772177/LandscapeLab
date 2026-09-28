# /Game/Alpine8K — COLLISION TRUTH AND GROUNDING, 2026-08-14

Closes the gap the session handoff named as open: **nothing had asked this world
a question through a representation other than the heightmap that built it.**
That is the exact condition under which `/Game/Alpine` rendered `v2` while
colliding `v1` for three days with every gate green.

Editor: PID 12120, node `198FE297471E71AAE3D69A9A91575846`, rule-7 verified,
full residency (1 landscape + 256 proxies, 1024 components).

## 1. DOES THE LANDSCAPE COLLIDE WHAT IT RENDERS?

`scripts/check_collision_truth.py --recipe recipes/alpine_8k.json --n 500`

    source artefact  LANDSCAPE COLLISION
    compared against terrain/alpine_8k.png
    samples          500, seed 359496323
    landscape hits   500 of 500  (100%)

    |collision - heightmap|   p50 0.010   p90 0.032   max 0.305  (m)

    PASS — p90 0.032 m against a 0.30 m bar.

## 2. ARE THE 154,018 CONIFERS ON THAT SURFACE?

`scripts/trace_grounding.py --plan foliage/alpine_8k_Conifer.json --n 500`

    samples          500, seed 7
    landscape hits   500 of 500
    sink_depth       0.12 m, as recorded in the plan

    gap = pivot_Z + sink - collision_Z      (POSITIVE = floating)
    min -0.138   p50 +0.006   p90 +0.013   p99 +0.036   max +0.095  (m)

    floating beyond 0.45 m : 0 of 500
    buried                 : 0

## 3. WHY BOTH ARE 5-7x TIGHTER THAN /Game/Alpine

    check                     /Game/Alpine (4 m)      /Game/Alpine8K (1 m)
    collision truth p90       0.159 - 0.233 m         0.032 m
    grounding gap p90         +0.068 m                +0.013 m
    grounding gap max         +0.392 m                +0.095 m

**The cause is physical, not luck.** The collision heightfield is sampled at the
landscape's own resolution, so its quantisation error shrinks with the cell. At
4 m/texel the heightfield can be a fifth of a metre away from the surface it
approximates; at 1 m/texel it cannot.

**This retires a caveat that has followed the grounding numbers for months.** The
0.392 m tail on alpine's traces was argued to be collision quantisation rather
than placement error, and the evidence was indirect — collision-vs-heightmap at
the same points disagreed by a similar amount. That argument predicted the tail
would collapse if the heightfield got finer. It has, to 0.095 m. **A prediction
that comes true on different data is stronger than the argument that produced
it.**

It is also the first quantitative benefit of the re-terrain that is not about
how it looks.

## 4. WHAT THIS DOES NOT ESTABLISH — stated plainly

- **NOT that the terrain is the RIGHT terrain.** Collision and the heightmap now
  agree with each other, and the heightmap was verified against
  `alpine_heightmap_v2` offline (correlation 0.999824, landform mae 1.41 m). But
  no instrument has compared the LIVE surface to the sweep photos' surface. The
  landform claim rests on the offline comparison of two files, not on the engine.
- **THE GROUNDING EPSILON IS NOW STALE.** `trace_grounding`'s 0.45 m bar was
  derived from ALPINE's collision quantisation. Against a measured p90 of
  0.013 m it is ~35x too loose and would not catch a subtle defect on 1 m
  terrain. It passed here on merit — max 0.095 m is far inside any reasonable
  bar — but the threshold should be re-derived before it is trusted as a GATE
  rather than read as a measurement.
- Both samples are uniform over the map, not stratified per proxy. Broad
  staleness is excluded; per-proxy completeness is not established.
