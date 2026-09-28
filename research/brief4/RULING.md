# BRIEF 4 PRE-RULING — R-3: lakes A/B/C, south river, waterfalls (2026-09-16, desk deputy)

**Standing:** issued under the deputy authority of `research/desk/RESEARCH_DESK_HANDOFF_2026-09-15.md` §3 and `research/audit/PRE_BRIEF4_CLOSURE_2026-09-15.md` §0/R-3. **NOTHING IS CARVED BY THIS RULING.** It exists so the carve session executes without re-litigating. **Ryan confirms or vetoes every line of it at the M-12/D-8 gate before Brief 4 opens** (`research/audit/PRE_BRIEF4_CLOSURE_2026-09-15.md:69,76`); any line he strikes reverts to OPEN, not to the desk's proposal.

## §0. Verification register (rule 9 — every number opened before use)

> **RE-VERIFIED 2026-09-16 against `research/brief4/input/hydro_amendment.json`** (desk delivery, `files (2).zip` 2026-09-17 05:03), reproduced by `research/brief4/scripts/hydro_derive.py` v2 (border-outlet fix + `level_slice()`/`pool_ladder()`; both selftests pass). **The two deputy-flagged classes below — UNVERIFIED-IN-REPO and UNDERIVABLE — are now CLOSED**; the reproduction table follows them. Instrument premise updated for the border fix. All reproductions were run against the committed input PNG (`alpine_8k_height_4x_2033.png`, sha in the sidecar) with the committed tool, so they are deterministic, not ferried.

**VERIFIED against `research/brief4/input/hydro.json`:**
- Lake A = `lake_proposals[0] "A_east_basin"`, lake_id **4893**, level 180.0 m, 125.5 ha, max depth 155.2 m, mean 56.4 m, shoreline 5.9 km, spill 196.9 m, centroid_world_cm [288391, −80918], surface_world_z_cm 18000 (hydro.json:4529–4553; parent basin row :9–32).
- Lake B = `lake_proposals[1] "B_town_tarn"`, lake_id **11877**, level 140.0 m, 13.6 ha, max depth 139.9 m, mean 45.8 m, shoreline 1.5 km, spill 197.6 m, centroid_world_cm [−200243, 185935], surface_world_z_cm 14000 (hydro.json:4554–4578; parent row :33–56).
- Lake C = `lake_proposals[2] "C_west_lake"`, lake_id **6587**, level 268.5 m **= its own spill**, 89.4 ha, max depth 65.4 m, shoreline 6.1 km, centroid_world_cm [−351343, −94483] (hydro.json:4579–4603; parent row :57–80).
- **78 waterfall candidates** (78 `drop_m` rows counted in hydro.json), **145 lakes** (`n_lakes`, hydro.json:3490), stream network 29.7 km @ ≥1 km², max contributing 15.97 km² exiting the **east** border at (2032, 625) (hydro.json:3490–3501), border outlets: S 14.82 km² @ col 1018, W 7.85 km² @ row 665, N 4.69 km² @ col 622 (hydro.json:4606–4623).
- Z convention station-verified: world_z_cm = height_m × 100, landscape actor z NOT added (`hydro.json:4605` `_z_note`; `research/brief4/input/alpine_8k_height_4x.json:50`, four station cameras +1.66 to +2.17 m above terrain).
- Town footprint bbox cols 386.5–593.3 / rows 1595.5–1829.9 (hydro.json:4518–4527 = alpine_8k_height_4x.json:82–91); town `site_centre_cm` [−210800, 278800] (`city/alpine_basin_town_plan.json`).
- Bench_ground station: loc_cm [265600, −94400, 6541.2], col_row (1680, 780) (`alpine_8k_height_4x.json:108–124`; `_station_note` :177).

**~~UNVERIFIED-IN-REPO~~ → CLOSED 2026-09-16.** The deputy flagged the south river's cut profile and the "17% in depressions" figure as the desk's word only. Both now reproduce:
- **Depression fraction = 0.1723** (amendment `verified_figures.depression_fraction`), reproduced exactly as `(hf − h > 0.05 m).mean()` over the 2033² grid. The handoff's "17%" was right.
- **The south river is re-traced, not handoff-only.** The amendment carries the full route (1323 cells) and its cut statistics, produced by `pool_ladder()` from the south border outlet. **The route is 6.3 km, not the handoff's 5.3 km** — the difference is the border-outlet fix (pre-fix routing let border cells collect flow laterally); the cut statistics are unchanged (mean 9.66 m, max 46.68 m, 721 cells cut >2 m). The 5.3 / 10 / 47 handoff numbers are superseded by the re-traced 6.3 km / 9.66 / 46.68. The `acc_km2.npy` / `fill_depth_m.npy` arrays are still not committed, but the figures reproduce deterministically from the committed tool + PNG, which is stronger than ferrying them.

**~~UNDERIVABLE FROM REPO ARTEFACTS~~ → DERIVED 2026-09-16.** The `lake_proposals` rows (level-sliced areas, bboxes, centroids, `shoreline_km`) were desk post-processing. They now reproduce **exactly** — every field, not merely to the ha — from `hydro_derive.level_slice(lab, h, lake_id, level_m, cell)`. The `centroid_world_cm`, `surface_world_z_cm` and `spill_level_m` fields also reproduce (world transform on the unrounded centroid; `level_m × 100`; basin fill surface `hf[lab==id].max()`). See the reproduction table.

**REPRODUCTION TABLE (rule 13 — sample count beside every verdict; a different instrument than the desk's).** Instrument: `hydro_derive.py` v2 on `alpine_8k_height_4x_2033.png`.

| Figure | Amendment | Reproduced | Instrument call | n compared | Verdict |
|---|---|---|---|---|---|
| Lake A (id 4893, 180 m) | 125.5 ha … | identical | `level_slice(…,4893,180.0)` | 6 geom fields | EXACT |
| Lake B (id 11877, 140 m) | 13.6 ha … | identical | `level_slice(…,11877,140.0)` | 6 geom fields | EXACT |
| Lake C (id 6587, 268.5 m) | 89.4 ha … | identical | `level_slice(…,6587,268.5)` | 6 geom fields | EXACT |
| hydro.json A/B/C full rows | on disk | identical | `level_slice` + world/spill | 12 fields × 3 | EXACT (regen delta = 0) |
| depression fraction | 0.1723 | 0.1723 | `(hf−h>0.05).mean()` | 1 | EXACT |
| south river route length | 6307.0 m | 6307.0 m | `pool_ladder` profile | 1 | EXACT |
| head / outlet elev | 589.81 / 156.25 m | 589.81 / 156.25 m | `pool_ladder` profile | 2 | EXACT |
| full-carve mean / max cut | 9.66 / 46.68 m | 9.66 / 46.68 m | `pool_ladder` profile | 2 | EXACT |
| cells cut >2 m | 721 | 721 | `pool_ladder` profile | 1 | EXACT |
| route cell count | 1323 | 1323 | `pool_ladder` route | 1 | EXACT |
| border outlets E/S/W/N | 15.97/14.82/7.85/4.69 km² | same km² + col_row | argmax acc per edge | 4 (km²+cell) | EXACT (4/4) |

**One consistency caveat, not a defect (same class as the old lake_proposals note):** the amendment's `south_river_ladder.pools_over_2m` is a **curated 14-pool view** — each entry annotated with `segments` (absorbed riffle-runs), `lip_world_cm`, `in_town_basin` — selected over `pool_ladder()`'s **56 raw pools** (21 of which have max_depth > 2 m; `riffles_dropped`=42). The route, cut statistics and total notch reproduce from `pool_ladder()`; the riffle-merge selection that yields exactly 14 is desk post-processing not emitted by the function. Reported as consistent, not as a per-pool re-derivation.

**Instrument premise** (`research/brief4/scripts/hydro_derive.py`): priority-flood fill (`fill_sinks`) + D8 flow (`d8_receivers`/`flow_accumulation`) on the 4 m/px downsample, selftested on a bowl-with-spillway (`--selftest`) and a two-bowl ladder (`selftest_ladder`). Lakes are fill-to-level of the EXISTING terrain — no carve creates their depth; `level_slice()` re-slices a labelled basin at a chosen level; `pool_ladder()` walks one channel and reports pools at natural spill with a `notch_m` cut. **Border fix 2026-09-16:** every border cell is now an outlet (`rec[0,:]=rec[-1,:]=rec[:,0]=rec[:,-1]=-1`); pre-fix, border cells collected flow laterally and biased the traces (this is why the south route grew 5.3 → 6.3 km). Features narrower than ~2 cells (8 m) are invisible, and the 1-px border is biased inward (`alpine_8k_height_4x.json:24`) — which touches lake C (bbox col 4).

## §1. The lakes

### LAKE A (east basin, id 4893, 180.0 m, 125.5 ha) — **ADOPT**

The east foothill basin is the ruled settlement/POI zone of the region's landform reading (`WORLD_VISION.md:299-305`), and it currently contains nothing but a bench station. A 125.5 ha lake with **5.9 km of playable shoreline**, held **16.9 m below its spill** (180.0 vs 196.9 — closed, no outlet to carve), fed by the map's largest channel (15.97 km² exiting east at row 625, immediately north of A's bbox rows 642–1011), anchors the east basin as a destination ~5 km from the town — the far, low end of the difficulty arc, exactly where a "reward" landmark belongs. The drowned-station consequence is already priced: Bench_ground sits at (1680, 780), z 65.4 m, **inside A's bbox and ~115 m under the proposed surface** — and closure item X-6 already schedules its re-station "in Brief 4 (lake A)" (`research/audit/PRE_BRIEF4_CLOSURE_2026-09-15.md:86`). Adopting A is what the closure list assumed; rejecting it would reopen X-6.

### LAKE B (town tarn, id 11877, 140.0 m, 13.6 ha) — **ADOPT**

Measured, not asserted: B's wet bbox at 140 m (cols 462–574, rows 1422–1542, hydro.json:4565–4570) sits **~214 m north of the town footprint's north edge** (rows 1595.5–1829.9), centroid ~935 m from `site_centre_cm` [−210800, 278800]. The tarn is **beside the town, not in it** — a 46.5 m-deep overlook walk from the plaza (plaza terrain ~186.5 m, from near_ground z 188.47 m minus eye height). This is the town-adjacent water the fantasy needs at near-zero cost: 13.6 ha, 1.5 km shoreline, and the terrain already holds the pit (the basin floor is ~0.12 m — the map's minimum lives here), so B is a water level, not a carve. The 139.9 m-deep shaft under a 13.6 ha surface is a Brief-6 caves/hero-location hook for free.

**Hard constraint the carve session must encode:** the town stands INSIDE basin 11877's full-fill footprint — the plaza is **11 m below the basin's 197.6 m spill** (town bbox contained in lake 11877's spill-level bbox cols 421–957 / rows 1396–1956, hydro.json:44–49). 140.0 m carries 46.5 m of freeboard under the town floor; **the recipe must record ~180 m as the never-exceed ceiling for this basin**, because any future "raise the water" tweak floods 303 committed buildings. This constraint goes in the water recipe block, not in prose.

### LAKE C (west lake, id 6587, 268.5 m, 89.4 ha) — **DEFER** (not reject)

C is proposed **at its own spill** (level = spill = 268.5, hydro.json:4582,4602), i.e. an overflowing lake whose outflow runs to the **west border outlet** (row 665, 7.85 km², hydro.json:4614–4618 — inside C's bbox rows 625–973), and its wet bbox reaches **col 4, ~16 m from the region edge** (also inside the downsample's soft 1-px border). Under the ratified 2×2 atlas, the west border is a walkable adjacent-region boundary (`WORLD_VISION.md:191-196`), and region-edge treatment is explicitly an open authoring question (`WORLD_VISION.md:142-145`). Adopting C now creates the project's **first cross-region continuity obligation** — a shoreline and an outflow the future west region's recipe must agree with, precisely the constraint Option A was chosen to avoid (`WORLD_VISION.md:243-246`). C serves no committed system (no station, no settlement, mid-arc difficulty), so it waits on the region-edge ruling / west-region authoring with nothing lost: it is a fill, not a carve, and can land in any later session. The derivation stands; only the timing is refused.

## §2. The south river — **CHAIN-OF-POOLS** (desk recommendation ADOPTED), full carve REJECTED, with a delivery condition

1. **The carve branch is currently unspecifiable from the repo.** The 5.3 km / 10 m mean / 47 m max profile was never ferried (§0 UNVERIFIED-IN-REPO). A pre-ruling cannot adopt a cut whose geometry no repo artefact describes.
2. **What the carve would do to committed content:** the town plan **stamps `terrain/alpine_8k.png` as a consumed input** (verified in `city/alpine_basin_town_plan.json` input keys), and its 303 buildings / 838 streets hold z-values sampled from the current surface. A continuous re-grade of a 5.3 km corridor "past the town", reaching 47 m of incision, strands or buries every committed placement near its banks, expires the town plan's DIVERGENT-BY-RULING binding the moment the fresh hash moves (R-PLANSTALE 1d, `RECIPES.md:17290-17299`), and — with no bridge assets in existence (the town is still engine primitives; the kit is a component kit) — **bisects the 36.53 km² BFS-reachable surface** along 5.3 km with an uncrossable gorge. That reachability figure is a ruled measurement of the shipped world.
3. **Chain-of-pools fits the terrain the instrument actually measured:** the map is depression-rich (145 fill-lakes ≥ 0.4 ha, hydro.json:3490; the handoff's 17% figure is consistent but repo-unverified), so stepped pools use existing hollows, the cut is confined to pool lips (metres, not tens of metres), each lip is a waterfall by construction, pools are swimmable rather than severing, and the town keeps the ground its plan was measured against. Through the RPG lens, a stepped alpine cascade past a town reads as landscape; a uniform 47 m trench reads as a moat.

**CONDITION (blocks the carve session, not this ruling):** the desk delivers the pool ladder — pool surface levels, lip positions, notch depths, and the route trace — as a hydro.json amendment, derived and cited, before the carve session executes. The 5.3 km / 10 / 47 figures are retained only as the rejected branch's cost estimate, labelled handoff-only.

## §3. Waterfalls — POLICY, not 78 calls

- **By construction:** every lip of the adopted chain-of-pools ladder is a fall. These are not selected; they are the river.
- **By coupling:** inflow falls for adopted lakes A and B only — candidates from the 78 within ~500 m upslope of an adopted shoreline **with elevation above the adopted surface**. The elevation test is mandatory: candidate (1642, 711), drop 18.9 m, sits at 157 m INSIDE A's bbox (hydro.json:3555–3567) and is **submerged at 180 m** — the candidate list predates the lake levels and must be filtered against them. B has a natural inflow candidate at (696, 1493), drop 8.1 m, elev 254.8 m (hydro.json:4491–4490 region), ~720 m east of the tarn.
- **One hero cascade:** the three-step stair at (1276,1272)/(1288,1281)/(1295,1288), drops 34.0/33.9/25.7 m between 638 m and 820 m (hydro.json:3503–3541), is the map's largest vertical water feature and a candidate for the aerial-readability landmark ruling 2a keeps demanding (`WORLD_VISION.md:162-165`). Which cascade is the landmark is **Ryan's** (§5).
- **Cap:** order 10–15 placed falls total in Brief 4. The remaining candidates stay rows in hydro.json — data, not content.

## §4. THE CONSEQUENCES REGISTER (binds the carve session)

1. **Bench_ground re-stations (X-6).** Its location is ~115 m under lake A. The replacement is derived, not aesthetic — A's shoreline is the natural candidate and would put non-zero `wet_shore` pixels in the surface-metrics frame, curing X-6's Snow/ForestFloor-0-px complaint in the same move. Every Bench_ground-keyed series ends at the carve; the session must check which station the A-6 "zero" baseline capture (`STATE.md` Block D-1 item 6) belongs to before reusing it.
2. **Foliage regeneration sequencing (X-1).** Water carves BEFORE regeneration (handoff:110). Regeneration goes through the D-4 planting-field contract — `scripts/derive_planting_field.py` exists exactly for this (spec: `recipes/schema.md` v1.17), and its docstring (:45–49) says the `place_foliage` rewire "happens with the Brief-4 water carve, not here". **The ±2% of 219,659 acceptance and the −20% floor (handoff:76-79) must be re-derived for the post-water world first**: ~140 ha of plantable ground goes under water, so the ruled count moves down and the unamended gate would misfire in both directions.
3. **Freshness (E-4 machinery, R-PLANSTALE as amended 2026-09-16, `RECIPES.md:17266-17299`).** The carve moves `terrain/alpine_8k.png`'s hash. Verified consumers: the **4 live foliage plans** (`foliage/alpine_8k_Conifer.json`, `_ConiferPine.json`, `_SpruceSub.json`, `_SpruceSapling.json` all stamp it) → DIFFERS → resolved by the regeneration itself, not by 1b waivers; the **town plan** stamps it → its DIVERGENT-BY-RULING binding expires (1d: "expiring the moment either hash moves") → the carve session re-runs `scripts/check_plan_freshness.py --reproduce` and re-rules or restamps in the same session. **Silent gap the machinery will NOT catch:** `encounters/alpine_8k_verified.json` stamps the frozen `_verify/20260827_navcalib/encounter_rows.json` — frozen evidence never goes stale, yet the 317 encounters and the 36.53 km² BFS were measured on the pre-water surface, and some encounters plausibly sit inside A/B/pool footprints. **Encounter re-verification is a named Brief-4 task, not an assumption.** The spec's two MEASUREMENT figures (z-span 0–1552.5 m, 36.53 km² reachable) both go stale and are re-measured.
4. **wet_shore unlocks; dirt_path does NOT.** `scripts/derive_layer_weights.py:36,:443` and `textures/alpine_8k_w8_sidecar.json:58,67` declare wet_shore zero "needs Brief 4's water level" — this ruling supplies the levels (180.0, 140.0, pool surfaces), so within-4-m-of-water becomes derivable and the RESERVED `flow` channel (sidecar:5) gains meaning. dirt_path's gate is the path network, not water; it stays zero, and `--expand`'s refusal on non-zero wet_shore/dirt_path (`RECIPES.md:19459`) must be amended in the same commit as the weight re-derivation.
5. **Derived-surface cascade:** weightmap re-derivation → material re-apply → `scripts/capture.py` (pipeline rule 4) → navmesh (72 bounds volumes) rebuild. Landscape HLOD: the carve re-dirties the freshly-rebuilt 4096 L2 cells it touches; per R-O1/X-2 the rebuild folds into the single post-Brief-5 rebuild — safe for the bench because proxies never render in bench frames (B-1 finding, `STATE.md:107-112`).
6. **Process law:** water is a new element TYPE → recipe block same session (NEW-ELEMENT RULE); all levels/extents from recipe JSON (pipeline rule 2); heightmap edit via the pipeline, never editor sculpt (standing rule 4); **named tag/branch before the carve** (RISKY-OP CHECKPOINT — this is the archetype); carve depths stay inside the 16-bit 0–2560 m encodable span (`alpine_8k_height_4x.json:30-33`; B's floor is already at ~0.12 m, so lip notches near it have essentially no downward headroom). Engine implementation (Water plugin vs meshes) is the carve session's call under `docs/ue58-api-protocol.md` — this ruling decides geometry and levels only, and names no engine API.
7. **Perf:** water surfaces are new GPU cost on a machine with a DEVICE_HUNG history; R-PERFBUDGET (handoff:70) runs after water lands, all four zones.

## §5. WHAT STAYS RYAN'S AT M-12/D-8

1. **The veto over every line above** — A adopt, B adopt, C defer, chain-of-pools, the waterfall cap. Confirm-or-veto at the M-12/D-8 gate before Brief 4 opens; a struck line reverts to OPEN.
2. **Lake A's exact level** within (floor at the drowned-bench relief, ceiling well under spill 196.9): 180.0 is the desk's proposal, and shoreline SHAPE at other levels is an aesthetic he may want to see rendered before confirming. Same for B within its hard ~180 m town-safety ceiling.
3. **The hero cascade** — which of the placed falls is the region's aerial landmark is taste, not derivation.
4. **B's "bottomless tarn" character** — keep the 140 m shaft as a Brief-6 cave/underwater hook, or shallow it. Nothing downstream depends on the answer yet.
5. **C's eventual fate** is genuinely coupled to his region-edge treatment ruling; the deferral above is scheduling, but the seam aesthetic is his.

## §6. AMENDMENT 2026-09-16 — the pool ladder, the town-basin conflict, lake D, the north cascade

The §2 delivery condition is met: the desk shipped `hydro_amendment.json` (route, pool ladder, verified figures) and it reproduces (§0 table). Tracing the ladder surfaced one thing the pre-ruling did not have — a conflict the natural-spill ladder creates with the committed town — plus a headwater lake and a full north cascade. **Nothing here is decided; the option and lake D are Ryan's at M-12/D-8 (§5).**

### 6.1 The town-basin conflict — the natural-spill ladder is INVALID inside basin 11877

The traced south river crosses **basin 11877 (the town basin) for ~2.6 km of its 6.3 km**. The basin's natural spill is **197.6 m** (at lip `(913, 1899)`, terrain elev 194.03 m there, world_cm `[−41200, 353200]`); the **town floor is 145 m** and the never-exceed ceiling is **~180 m** (§1 LAKE B hard constraint). A chain-of-pools **at natural spill** would pool basin 11877 to 197.6 m and **put the town under ~11 m of water**. So the §2 "pools at natural spill" recipe **cannot be applied inside basin 11877** — it must be resolved by one of the two options below.

**Basin sink (reproduced):** at every level 170–180 m the basin's only large pool is **tarn B itself**, growing from 13.6 ha @ 140 m to **21.9 ha @ 177 m** (centroid `(519, 1478)`, ≥148 m from the town edge, **0 town cells wet**). The water the basin holds is the tarn, not the town.

### 6.2 The two options — RYAN'S CHOICE (nothing decided)

- **Option I — endorheic (cut 0 m). DESK RECOMMENDATION.** No cut anywhere in the town basin. The north cascade (6.4) terminates in **tarn B as a closed alpine lake** — outflow is underground, which *is* the "bottomless tarn" Brief-6 hook §5.4 already keeps open. The south river becomes the reach **below** the lip, fed by its own catchment (south-reach pools 14451, 14393, 14369). Tarn stays at **140 m by ruling**. Nothing committed moves.
- **Option II — one notch (cut 17 m at the lip `(913, 1899)`).** Lower the basin outlet to **177 m** so the river is continuous through the basin. The tarn then rises to **177 m: 21.9 ha, max depth 176.9 m, mean 58.2 m, shoreline 1.9 km** (centroid `(519.4, 1477.9)`, bbox `[449, 1400, 602, 1557]`), leaving **3 m of freeboard** under the 180 m ceiling and **152 m from the town edge**. It buys a continuous river and a gorge outlet feature at the cost of a 17 m cut and a 3 m safety margin on 303 committed buildings.

Both tarn figures reproduce exactly from `level_slice(lab, h, 11877, level)`. **The choice is Ryan's at M-12/D-8**; the desk recommends Option I (zero cut, zero risk to the town, and it feeds the bottomless-tarn hook).

### 6.3 New candidate — LAKE D (headwater basin 8377) — RYAN'S to adopt

The cascade trace surfaced a headwater basin the deputy did not have. Basin **8377** fills to 591.9 m (50.3 ha, 38 m by natural fill); the desk proposes a level of **590.9 m** (1 m under spill), which `level_slice` gives as **49.6 ha, max depth 134.0 m, mean 41.8 m** (my re-slice 41.9 — a 0.1 m boundary-rounding difference), **shoreline 4.2 km**, centroid `(660, 1079)`, bbox `[543, 908, 812, 1206]`, lip `(632, 1201)`. A high alpine lake at the **top** of the cascade — the far, high end of the difficulty arc. **Whether to adopt D is Ryan's** (same class as C's deferral); the derivation stands.

### 6.4 The north cascade ladder

Between **lake D (~592 m)** and the **town-basin rim (~198 m)** the route drops **394 m over ~2 km through eight pools of 2–10 m depth**; **every lip is a fall by construction** (this is §3's "by construction" policy realised as the actual ladder, not 78 calls). The steepest reach is the **327 → 198 m step** (basin 12017 down to the town rim). Pool ids along it (`north_cascade.pools_ids`): 12017, 11868, 11796, 11696, 11556, 11471, 11171, 11074, 10980, 8377. Under Option I this cascade **terminates in tarn B**; under Option II it continues through the 177 m notch into the south reach.

*Amendment filed by the read-only desk deputy, 2026-09-16, against `research/brief4/input/hydro_amendment.json` and reproduced by `hydro_derive.py` v2 (§0 table). The option and lake D are Ryan's at the M-12/D-8 gate; this amendment decides nothing.*

---

*Filed by the read-only desk deputy, 2026-09-16. Sources opened: `research/brief4/input/hydro.json` (rows cited), `research/brief4/scripts/hydro_derive.py`, `research/brief4/input/alpine_8k_height_4x.json`, `research/desk/RESEARCH_DESK_HANDOFF_2026-09-15.md`, `research/audit/PRE_BRIEF4_CLOSURE_2026-09-15.md`, `STATE.md`, `WORLD_VISION.md`, `RECIPES.md` R-PLANSTALE (+2026-09-16 amendment), `scripts/derive_planting_field.py`, `scripts/derive_layer_weights.py`, `scripts/check_plan_freshness.py`, `city/alpine_basin_town_plan.json`, `encounters/alpine_8k_all.json`, `encounters/alpine_8k_verified.json`, `foliage/alpine_8k_*.json` stamps, `textures/alpine_8k_w8_sidecar.json`, and (2026-09-16 amendment) `research/brief4/input/hydro_amendment.json`. The items §0 had marked UNVERIFIED-IN-REPO / UNDERIVABLE are CLOSED — the pool-ladder amendment landed and reproduces (§0 table, §6).*

---

## §7. RYAN'S GATE DECISIONS — recorded 2026-09-16 (deputy filing; NOTHING CARVED)

Ryan ruled every open line of this pre-ruling and its amendment at the M-12/D-8 gate. Recorded here as DECIDED by the read-only deputy; **no heightmap is touched by this record** — the decisions become the carve session's contract (`research/brief4/CARVE_PLAN.md`). Each line cites the section it closes.

| # | Decision | Level / value | Closes | Was it the desk's proposal? |
|---|---|---|---|---|
| 1 | **Lake A — ADOPT** | 180.0 m | §1 LAKE A, §5.1/§5.2 | yes |
| 2 | **Lake B (town tarn) — ADOPT** | 140.0 m | §1 LAKE B, §5.2 | yes |
| 3 | **Lake C — DEFER** to the region-edge ruling | — | §1 LAKE C, §5.5 | yes (scheduling only) |
| 4 | **Lake D — ADOPT** (top of the hero cascade) | 590.9 m | §6.3 | yes (D was RYAN'S to adopt) |
| 5 | **Tarn B — ENDORHEIC** (Option I): cascade ends in it, no outlet, **cut 0 m** | tarn stays 140 m | §6.1/§6.2 | yes — the desk's recommendation |
| 6 | **Hero cascade landmark = the D-to-tarn stair** | the north cascade (§6.4) | §3 "one hero cascade", §5.3 | **NO — supersedes §3's candidate** |
| 7 | **Waterfall cap 10–15** placed falls | 10–15 total | §3 cap | yes |

**What decision 5 (endorheic) fixes for the carve session:** basin 11877 is a **closed lake** — the north cascade terminates in tarn B, whose outflow is underground (the Brief-6 bottomless-tarn hook, §5.4 kept). **No notch is cut at the (913,1899) lip; the 17 m Option II is struck.** The south river is only the reach **below** the lip, fed by its own catchment (south-reach pools 14451, 14393, 14369). The town keeps 46.5 m of freeboard under its 197.6 m basin spill with zero cut anywhere near it.

**What decision 6 (hero landmark) fixes:** the region's aerial-readability landmark is the **D-to-tarn stair** (§6.4: lake D ~592 m → tarn B ~140 m via the eight-pool north cascade, every lip a fall), **not** the §3 three-step stair at (1276,1272)/(1288,1281)/(1295,1288). That §3 stair reverts to an ordinary candidate within the 10–15 cap. This is taste exercised, exactly as §5.3 reserved it.

**The Brief-4 water set is therefore fixed:** carve **A@180, B@140 (endorheic/closed), D@590.9**; build the **north cascade D→tarn** (its lips are the hero falls by construction); add **inflow falls for A and B** per §3's coupling+elevation test; **C is NOT carved** (deferred). Total placed falls stay inside the **10–15** cap. Everything else in §4's consequences register binds unchanged.

*Recorded by the read-only desk deputy, 2026-09-16, from Ryan's gate answers. Nothing is carved by this record; it is the input to `CARVE_PLAN.md`.*