# DENSITY PLAN — Brief 5 Part C

**The table the daylight brief runs on.** Every number here is sourced to a measured
artefact; nothing is estimated by feel. Reproduce the arithmetic with
`research/brief5/scripts/density_project.py` → `input/density_projection.json`.

Status: the **tree** and **HLOD** columns are complete and measured. The **clutter** column
is **OWED** — P3 proved PCG-graph authoring works but the overnight harness prevented capturing
the cost measurement (§4). A supervised session closes it in minutes.

---

## 0. What "the density upgrade" is, precisely

The upgrade Ryan defined is **density**, not a bigger planting field. The planting field
already emits **185,385 trees at ~135/ha** — that is the *field* output, not the richness
target. The desk's proposed richness lever is **one global multiplier `m` on the recipe's
existing tree-density field** (`BRIEF.md:132`), set to `m_for.p90_bin` from the canopy
measurement:

- **m = 5.48** at crown factor 0.85 (`derived/canopy_cover.json` `summary.m_for.p90_bin`).
  Sensitivity: **3.96** at crown 1.00, **8.03** at crown 0.70.
- What 5.48 buys: it makes the **densest tenth** of the forest an actual forest (reaches
  target cover 0.70 in the p90 bin) and leaves the existing density gradient toward the
  treeline intact. Today the forest is **woodland at best** — max cover 0.285, *no* forest
  bins (`canopy_cover.json summary`).

Applied globally, every location's local tree density scales by `m`, so the count of live
trees **visible at a fixed station** scales by `m` (the culling geometry does not change).
That is the lever the projection below prices.

---

## 1. The forest_floor budget — RULED 13.0 (desk revision, supersedes the same-day 12.5)

**Ryan ruled 2026-09-22 at the Daylight Density session start: R5-1 = 13.0 ms is the forest_floor
budget (the desk revision).** This SUPERSEDES an earlier same-day ruling that set 12.5 and dropped
a header 13.0; the direction is now reversed — 13.0 stands as both the pass/fail budget and the
fence abort ceiling. Consequence at 13.0: the current hold **12.645 is UNDER budget by 0.355 ms**
before a single tree is added (it busted the withdrawn 12.5 by 0.145). The density headroom at
forest_floor is small but positive; every projection below is measured against **13.0**.

---

## 2. Per-station projection at m = 5.48 (ex-clutter)

Live-tree GPU cost scales linearly at the measured **0.1003 ms per 1000 in-frustum-in-cull
trees** (`forest_cost.json`; an UPPER bound — that delta also removed grass and off-frustum
trees). HLOD is handled in §3.

| station | current hold ms | budget | visible trees now → @5.48 | live-tree Δ | proj (ex-clutter) | vs budget | vs tol |
|---|---|---|---|---|---|---|---|
| **forest_floor** | 12.645 (0.355 under) | **13.0** (RULED) | 1,844 → 10,105 | **+0.829** | **13.474** | **+0.474 OVER** | +0.474 (tol=13.0) |
| **treeline** | 7.139 | 7.0 | 0 → 0 (all HLOD) | +0.000 | **7.513** | +0.513 OVER | **−0.187 UNDER** (tol 7.7) |
| **plaza** | 9.476 | 10.5 | 903 → 4,948 | +0.406 | **9.882** | −0.618 UNDER | −1.668 (tol 11.55) |

Sources: holds — forest_floor `r3_perf.json`/STATE.md:91 (post-hold); treeline
`T11_VERIFY.md:20`; plaza `density_baseline` item1_gpu_passes. Visible counts —
`density_baseline` item1_instance_census.per_station_visible. forest_floor 1844 & 0.185 ms —
`forest_cost.json`.

**Two honesty caveats on forest_floor:**

1. **The forest_floor live-tree Δ is a LOWER bound.** The 0.1003 ms/1000 rate was measured
   in v3 *before* the T3 hold persisted (card-era). The hold added **+1.597 ms** of
   card→geometry cost on in-cull trees, and *that* cost also scales with `m` — it is not in
   the 0.1003 rate. So real forest_floor growth is larger than +0.829. A post-hold per-tree
   rate re-measure is owed before this number is treated as tight.
2. Even at the lower bound, **m = 5.48 busts the ruled 13.0 budget by 0.474** on live-tree
   cost *alone*, before clutter and before its own HLOD growth (the current hold 12.645 is
   0.355 under 13.0, so the whole overage is density-driven).

---

## 3. HLOD growth — the gating unknown

The forest beyond the 512 m cull is carried entirely by HLOD proxies. Item 8 measured the
HLOD **share** at the treeline station: **0.576 ms = 1.17 % of the MRQ 4K frame**
(`item8_share.json` `stations.treeline`), of which the part that scales with tree count is
the **instanced tree proxies (61,427 instances = 4.37 % of GPUScene)**.

- **Transfer the share fraction, not the MRQ ms** (item 8 rule-10 caveat). At treeline
  (0 live trees, all-HLOD forest), scaling the 1.17 % share by `m` on a 7.139 ms game frame
  gives **+0.374 ms** at m=5.48 → 7.513 ms, which is the treeline projection above.
- This is a **conservative over-estimate** (it scales the whole share, merged + instanced,
  when only the instanced portion truly grows), used as an upper bound.
- The naive `0.576 × (m−1) = 2.58 ms` is **MRQ-scale and must not be read as game ms.**
- **forest_floor and plaza HLOD growth is UNMEASURED** — item 8 only measured treeline and
  vista shares. Their forests beyond the cull *do* grow with `m`; the projection excludes it
  and flags it. A true in-game HLOD-share ms needs PIE-side profiling that item 8 did not
  take (its open item).

**Consequence:** the treeline verdict (within tolerance 7.7, over nominal 7.0) rests
entirely on this HLOD estimate. If forest_floor's unmeasured HLOD growth is anything like
treeline's, forest_floor is worse than §2 shows.

---

## 4. Clutter — MEASUREMENT OWED (P3 captured feasibility, not cost)

The clutter cost column requires measured **ms per 1000 instances by class**, GPU and
game-thread. **P3 this session PROVED PCG-graph authoring works from Python**
(`pcg_cost.json`: `PCG_ClutterSpike.uasset` built + saved — SurfaceSampler → TransformPoints
→ StaticMeshSpawner) **but did NOT capture the cost measurement** — the overnight harness
reaped the measurement's background process twice, the editor then held its Python thread and
went unresponsive, and it was force-killed (shipped world proven byte-identical). So:

- **Clutter cost is UNMEASURED.** Two numbers are owed, both from a supervised session:
  the **game-thread add/generation cost** (`scratchpad/pcg_measure_fast.py`, minutes) and the
  **steady-state GPU render cost** (a -game MRQ pass on a saved scratch level).
- Do **not** substitute a tri-scaled guess: at these counts clutter GPU cost is
  shadow/overdraw-dominated, not triangle-dominated, so tri-count scaling from the grass
  anchor would manufacture a false number. The honest state is "owed", not "estimated".
- The P2 inventory (`clutter_inventory.json`) fixes the spawn set and LOD chains, so the
  measurement is a short, well-scoped run once an editor is available interactively.

Headroom for clutter after trees (ex-HLOD-growth), ruled budgets:
- forest_floor: **negative** (proj 13.474 vs 13.0, over by 0.474) — no clutter headroom; needs a cull/shadow lever or a reduced multiplier first.
- treeline: −0.187 to tol 7.7 — ~0.19 ms for clutter before tolerance.
- plaza: −0.618 to budget 10.5 — ~0.6 ms for clutter.

---

## 5. Where it goes over, and which lever pays (each with a source number)

**forest_floor — over the ruled 13.0 budget by 0.474, from live-tree growth.**
The growth lands in **LumenReflections (+0.324 ms), ShadowProjection (+0.105), Basepass
(+0.086)** — *not* NaniteVisBuffer (−0.008) (`forest_cost.json` per_pass_delta).
Therefore:
- **T4 tri-reduction rungs (P5) do NOT pay for this overage** — the cost is Lumen + shadow,
  not Nanite raster. Reducing triangles moves the wrong pass.
- **The levers that pay are cull distance and foliage shadow distance** (fewer visible
  instances / fewer shadow casters). Halving the visible live count recovers ~0.41 ms
  (half of the +0.829 growth), and the overage at 13.0 is 0.474, so a cull/shadow cut alone
  is close to sufficient at forest_floor — a modest multiplier cap there closes the rest.
  Quantifying the exact cull needs a cull-sweep measure; the direction is fixed by the
  per-pass data.

**treeline — over nominal 7.0 by 0.513, all HLOD proxy growth; within tol 7.7.**
The lever is **HLOD range / imposter transition**, not live foliage (there are 0 live trees
here). If tolerance 7.7 is the real bar, no lever is needed. If 7.0 is firm, pulling the
HLOD/imposter transition inward reduces the instanced-proxy count that grows with `m`.

**plaza — under budget by 0.618; no lever needed** unless clutter (P3) exceeds ~0.6 ms.

---

## 6. Meadow mid-band (P7) — a PCG grass band 50 m → 300 m

The recipe already flags the gap: meadow grass culls at **50 m** and nothing represents the
ground out to the 512 m cull. A PCG grid could place a coarse mid-band grass representation
there. **P3's small-grid measurement was not captured** (§4), so this is an *anchored estimate*
from the one measured grass rate, not a measured figure. Anchor: item2 measured plaza
ground-cover at **0.286 ms GPU for 126,386 grass instances** (`density_baseline.json`) =
**≈0.00226 ms per 1000** grass instances (GPU, plaza class). A 50→300 m annulus at the meadow
station is π(300²−50²) ≈ **274,900 m²**; a *sparse* mid-band grass at ~0.5/m² over the
frustum-visible fraction (~a third of the annulus at 90° hFOV) is on the order of **45–50 k
visible instances**, i.e. **≈0.10 ms GPU** at the grass anchor rate — cheap, consistent with
"live foliage instancing is near-free on this GPU" (item2 headline). The **game-thread
generation cost** of producing that band via runtime PCG is the number P3 was to measure and is
**owed** (the queue's flag that runtime generation is CPU work that can bottleneck). Verdict: the
band's *render* cost is small and affordable at the meadow station; its *generation* cost must be
measured before a runtime-hierarchical grass band is committed.

## 7. Bottom line for the daylight brief

- The desk's **m = 5.48 global multiplier busts forest_floor** at the ruled 13.0 by 0.474 on
  live-tree cost alone, and the true cost is higher (pre-hold lower bound + unmeasured HLOD
  growth). forest_floor cannot take the full multiplier without a cull/shadow lever.
- **treeline** survives within tolerance but is entirely HLOD-limited; the verdict is only
  as good as the item-8 share transfer.
- **plaza** has genuine headroom (~0.6 ms) for both density and clutter.
- Two measurements are owed before this is tight: a **post-hold per-tree rate** at
  forest_floor, and an **in-game HLOD share** (PIE) at forest_floor/plaza.
- Ruling (Ryan 2026-09-22, Daylight Density session): forest_floor budget = **13.0** (R5-1 desk
  revision), superseding the earlier same-day 12.5. 13.0 is both the pass/fail budget and the
  fence abort ceiling.
