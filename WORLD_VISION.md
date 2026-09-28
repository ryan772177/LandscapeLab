# WORLD_VISION.md — north star

**The goal is an open-world RPG built in Unreal Engine 5.8.** Terrain is
phase one. It is a subsystem of the world pipeline, not the product.

Everything in this repo — the heightmap generator, the material builder,
the foliage placer, the capture loop — exists to make *worlds*
reproducible from data. When a decision is ambiguous, resolve it toward
"does this scale to a world an RPG happens in", not "does this make one
mountain look good".

> **Assumption markers.** Lines marked **[ASSUMED]** are inferred from
> the existing work, not stated by Ryan. Lines marked **[CONFIRMED
> 2026-08-02]** were ruled on explicitly and are settled — treat them as
> requirements, not guesses.

---

## Build order

Each phase depends on the one before it. The order is not arbitrary:
every phase produces the data the next one consumes.

| # | Phase | Status |
|---|---|---|
| 1 | **Terrain** — heightmap generation, erosion, import, verification | **DONE**, measured |
| 2 | **Biomes / materials / foliage** — layer bands, real surfaces, instanced foliage, GPU grass | **IN PROGRESS** — grass unresolved |
| 3 | **Traversal** — on foot (baseline), mounts (~3x speed), airship | partly built: `traversability()` measures connected components per movement profile. **Constraints encoded, implementation deferred by ruling** |
| 4 | **POIs and structures** — placed, authored locations with meaning | not started — **tripwire: before first placement, reconfirm per-region size AND the multi-region structure ruling with Ryan** |
| 5 | **Streaming** — World Partition tuned for mounted speed and airship altitude (aerial HLOD is first-class) | partial: WP is in use; not tuned |
| 6 | **Gameplay systems** — quests, encounters, factions, progression | not started |

### Why this order

Terrain first because **everything downstream is placed relative to it**.
Foliage reads the heightmap and the baked weightmap. Traversal reads
slope. POIs need somewhere to sit. A world whose terrain changes
invalidates every placement decision made against it — which is why the
pipeline is deterministic from a seed and re-runnable.

---

## Design pillars

These are inferred from how the project has actually behaved, and the
evidence is cited so you can judge them.

### 1. Data-driven, or it does not count
Every scene parameter comes from recipe JSON. Nothing is hand-placed in
the editor and left there. The test: **can the scene be destroyed and
rebuilt from `recipes/*.json` with no editor interaction?** Today, yes.

*Evidence: hard rule 2, and the standing refusal to accept MCP-authored
scene state as durable.*

### 2. "Good" is a measurement, not a taste
Traversability percentages, local relief, anisotropy ratios, triangle
counts, pivot offsets. Where a judgement could be aesthetic, this project
has consistently found a number for it instead.

*Evidence: the relief/traversability work; the anisotropy gate; the
per-level triangle verification in R5.*

### 3. Verify with a different instrument than the one that made the claim
A read-back that reads the same field the setter wrote proves only that
the value landed. The pivot was measured in Blender, again after re-read
from disk, and a third time off the imported UE asset.

*Evidence: LESSONS §23.1, §23.15, §23.17.*

### 4. Exploration at human scale — from the ground AND the air
Cameras are derived for eye height and the foliage cull is tuned for
walking pace, but **[CONFIRMED 2026-08-02, revised same day]** on-foot
is the BASELINE, not the whole story: **mounts and airship travel are
confirmed features.** Three standing constraints follow (full text in
the rulings below): the world must read well from airship altitude;
mounted speed (~3x on foot) governs POI spacing and streaming budgets;
and traversal systems themselves are NOT to be implemented yet — only
kept possible.

### 5. Runs on the hardware in the room
Intel Ultra 5 225U iGPU, 15.4 GB RAM. This is a real constraint that has
already shaped the work — a GPU TDR, an LOD chain, a low-spec config
profile. **[ASSUMED]** the shipping target is more capable than the dev
machine, so quality settings are a *profile*, not a ceiling.

---

## What phase 2 still owes

- **Grass and trees verified at ground level 2026-08-02.** Grass at 12
  tufts/m2, trees at 24.7/ha upright and grounded. Remaining asset-level
  headroom: grass_medium_02 / leafy_grass through the now-safe import
  path.
- **Vegetation is invisible from airship altitude** — see the backlog
  above. Ruling 2a is unmet.
- **Foliage density is two orders of magnitude below reality** — 4.4
  trees/ha against 200–1000 for real alpine forest. The LOD work bought
  the headroom to raise it; that is the next visible-quality step.
- **Terrain stretches on steep faces.** The landscape material samples in
  XY only; triplanar projection on the rock layer is the fix.
- **One biome exists.** `alpine.json` is the only recipe. The schema is
  biome-general; nothing has tested that claim.

---

## Aerial readability — status as of 2026-08-03

**CORRECTION. This section previously read "AERIAL READABILITY IS ZERO
... 0.00% vegetation-coloured pixels — measured, not estimated." That
figure was a BROKEN MEASUREMENT, not a finding, and stating it as
measured fact was wrong.** The metric tested green dominance in a
warm-lit scene where vegetation renders red-dominant; re-run on the
GROUND frame — which visibly contains grass and 160,448 trees — it also
returns 0.00%. See `LESSONS.md`, "THE 0.00% MEASUREMENT WAS THE DEFECT".

**Ruling 2a remains unmet, but for reasons that are now measured
properly rather than asserted:**

- The tree cull is **730 m** (raised from 300 m on 2026-08-03 by
  re-solving the LOD chain, at 39.6M triangles) and the grass cull is
  50 m, against a ~2000 m eye. Real instances genuinely do not reach
  airship altitude.
- The landscape material now carries a **`forest_floor` tint** over the
  tree elevation band (schema v1.11), confirmed in the graph and visible
  at ground level (terrain brightness 80.7 → 65.7, normalised green
  excess +0.0216 → +0.0249).
- **The aerial verification camera cannot currently judge any of this.**
  It is aimed at a rock-and-snow peak with half the frame in deep
  shadow; the forest band is a minority of its pixels. Re-aiming it is a
  `BACKLOG.md` item and a prerequisite for any future 2a claim.

Remaining aerial tier, none of it started:

1. **Foliage HLOD / imposters for trees.** The only way real forest
   reaches altitude; 730 m is the affordable ceiling for instances at
   40M triangles. **Biggest single item for ruling 2a.**
2. **Aerial-specific material treatment beyond the forest_floor tint** —
   macro variation, or a distance-blended canopy colour.
3. **World Partition tuning for altitude.** A 2 km viewpoint sees far
   more cells than a walking one; streaming was tuned for neither.
4. **The region boundary is a hard edge**, clearly visible at altitude.
   **If** Option A (multi-region) is ruled, this becomes a real
   authoring question: what does a region edge look like from an
   airship? Under Option B it is a seam-continuity problem instead.

## Rulings — confirmed by Ryan, 2026-08-02, RE-RATIFIED 2026-08-03

The first batch said "mounts possible later, do not design around them
yet". Ryan revised traversal and world structure within hours. The
original wording is preserved in `LESSONS.md` Division 6 with a
superseding entry; this section is current.

**Re-ratified 2026-08-03**, with one status change: ruling 3's
contiguous-vs-multi-region half is **reopened** and now awaits Ryan's
ruling (see below). Rulings 1, 2, 4, 5 and 6 stand unchanged.

1. **Combat: CONFIRMED.** Real-time action combat.
2. **Traversal: REVISED.** On-foot is the baseline; **mounts and
   airship travel are confirmed features.** Three design rulings,
   logged in `LESSONS.md`:
   - **(a) Aerial readability is first-class.** The world must read
     well from airship altitude — aerial HLOD, horizon treatment, and
     sky/cloud rendering are requirements, not polish.
   - **(b) Mounts ~3x on-foot speed.** POI spacing, path networks, and
     streaming budgets are sized against mounted speed, not walking
     speed.
   - **(c) Do not implement traversal systems yet.** Encode the
     constraints so terrain and streaming decisions do not foreclose
     them; build nothing.
3. **World structure: 8064 m is the PER-REGION size — CONFIRMED.**
   Reference class: Witcher 3 / Final Fantasy / Tales / Amalur.
   ~~**The contiguous-vs-multi-region half is an OPEN DECISION as of
   2026-08-03**~~ — **RULED BY RYAN 2026-08-15: MULTI-REGION, 2×2 ATLAS.**
   ≤2 regions co-resident, adjacent borders walkable, non-adjacent travel
   by airship. This is **Ryan's own ruling**, given in session, not a
   delegated one — see the section below for why that distinction is
   spelled out. The tripwire is lifted; region-shaped work may proceed.
4. **Single-player: CONFIRMED.**
5. **Photoreal art direction: CONFIRMED.** The Paragon / Megascans /
   MetaHuman lane. Logged as a design ruling in `LESSONS.md`:
   **all asset acquisitions filter through photoreal coherence** — an
   asset that is good but stylistically incoherent is a rejection.
6. **Biomes: alpine first, biome-general schema CONFIRMED.** Each
   future REGION is a new biome recipe, and each new recipe is a
   schema validation test. Nothing in the pipeline may hardcode
   alpine-isms.

---

## World structure — RULED BY RYAN 2026-08-15: MULTI-REGION, 2×2 ATLAS

**THE RULING, in full:** multi-region, **2×2 atlas**, **≤2 regions
co-resident**, **adjacent borders walkable**, **non-adjacent travel by
airship**. One landscape recipe per region; 8064 m stays the per-region
size; alpine is region one.

**WHY THE PROVENANCE IS STATED AND NOT JUST THE ANSWER.** This decision
has been "ruled multi-region" once before and revoked, because that
ruling was made by a delegated agent rather than by Ryan. The answer is
the same both times; **only the second one is a ruling.** It was given by
Ryan directly, in session, on 2026-08-15, against a recommendation that
named its own reasoning. A future session must not read the 2026-08-03
withdrawal as applying to this — the withdrawal was about WHO decided,
not about WHAT was decided.

**Tripwire LIFTED.** `WORLD_ARCHITECTURE.md`'s recommendation is now the
ruled architecture rather than a recommendation. The five `.terrain`
files in `terrain/regions/` were authored against this shape and are no
longer speculative. Settlements, POIs and region-edge treatment are
unblocked as far as this decision is concerned — they have their own
separate blockers (an architecture kit, and `PHASE2_PLAN.md` ruling 13).

*Kept below, unedited, as the record of what was proposed and on what
grounds:*

**STATUS CHANGED 2026-08-03. This was previously recorded as "RULED:
MULTI-REGION, by delegated decision". Ryan has taken the decision back:
it is now an OPEN DECISION pending his ruling.** The delegated ruling is
withdrawn — not because the analysis was wrong, but because the call is
his to make. Nothing may be built on the assumption of either option.

What is settled: **8064 m is the PER-REGION size** (reference class
Witcher 3 / Final Fantasy / Tales / Amalur), and **alpine is region
one**. What is open: contiguous world vs multi-region connected by
airship.

**The proposal Ryan asked for is below, both options with pipeline
implications.** Ryan's stated lean is multi-region, one landscape recipe
per region. The agent's recommendation agrees, for the reasons in the
next section. **Neither constitutes a ruling.**

~~**Tripwire: this must be ruled before ANY placement work begins.**
Tracked in `BACKLOG.md`.~~ **DISCHARGED 2026-08-15 by Ryan's ruling above.**

### Option A — MULTI-REGION connected by airship (recommended)

- **It is what the pipeline already is.** One recipe → one level →
  deterministic rebuild. Region two is a new `recipes/<region>.json`
  and nothing else changes. Contiguous would be a new architecture;
  multi-region is the current one, continued.
- **Region boundaries are authored, not stitched.** No cross-region
  heightmap continuity constraint, no seam blending, no obligation for
  neighbouring recipes to agree at their edges. Every region stays
  independently regenerable — the idempotent-rebuild rule survives.
- **World Partition stays at proven scale.** One 8064 m region already
  defines this hardware's ceiling — the editor has saturated at
  exactly this scale. N regions in one world multiplies actor counts,
  save scope, and HLOD cost past anything verified.
- **Airship travel IS the region connector.** A region transition
  behind a sky sequence is cheap, robust, and what the reference class
  does — Witcher 3's Velen, Skellige and Toussaint are separate maps.
- **Lower regret in both directions.** Island regions can later be
  joined with authored transition zones if contiguity is ever wanted;
  splitting an already-stitched world is far worse.

### Option B — CONTIGUOUS world (what it would cost)

- Either one giant heightmap — four regions is 16k+ resolution against
  a pipeline verified at 2017, quadrupling bakes and memory — or
  stitched landscapes with a permanent edge-continuity constraint on
  every regional recipe.
- Cross-region rebuilds perturb neighbours at the seams: per-recipe
  determinism breaks.
- One coordinate space for everything pressures float precision at the
  far corners and forces a single World Partition world to hold it all.

### Consequences IF Option A is ruled

These are contingent, not standing, until Ryan rules.

- `recipes/<biome>.json` would be understood as a **region definition**.
  Alpine is region one either way.
- The world map would be a **graph of regions connected by airship
  routes**, not a plane. POI planning happens per region.
- Airship altitude readability (ruling 2a) would apply **per region**:
  each region must hold up from its own sky.

### What holds either way

- 8064 m per region, alpine first.
- Biome-general schema; nothing hardcodes alpine-isms.
- Aerial readability is a requirement, because airship travel is
  confirmed regardless of how regions are connected.

---

## The alpine region's terrain reading — RULED 2026-08-03

The alpine region's landform is **not decoration**. Its shape is the
region's design, and every later placement pass builds against this
reading rather than re-inventing one.

Approved structure: **two massifs, with an east and a southwest foothill
basin.** Composited in Pass 1 from the StampIT catalogue; the exact
placements are `stamps.placements` in `recipes/alpine.json` and the
procedure is `RECIPES.md` R-STAMP.

### What each landform MEANS

| Landform | Design role |
|---|---|
| **The two foothill basins** (east, southwest) | The region's **settlement and POI zones**. Towns, roads and points of interest go here. Low, open, traversable ground is where people live. |
| **The inter-massif corridor** | The **primary traversal route**. The way through the region on foot or mounted; the axis a player moves along by default. |
| **The foothill → peak arc** | The **difficulty and remoteness gradient**. Distance up the arc is distance from safety. Encounter density, resource value and hazard scale with it. |

### Why this is written here and not only in the recipe

The recipe records WHAT the terrain is. This records WHY, and the why is
what a future pass needs in order not to contradict it. A settlement
placed on a peak, a road routed over an arête, or a beginner encounter at
the top of the arc would each be individually defensible and would each
break the region's reading.

**This is the same rule as non-negotiable 19 one level up:** the terrain's
meaning is a fact both the terrain pass and every placement pass depend
on, so it is stated once, here, and both read it.

### What is NOT yet decided
- Where within the basins settlements sit. That is blocked on the world
  structure ruling above.
- Whether the corridor carries a built road or only a natural route.
- Treeline elevation as a gameplay boundary versus a purely visual one.
