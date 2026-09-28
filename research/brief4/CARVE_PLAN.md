# BRIEF 4 CARVE PLAN — the water carve, ordered with read-backs (deputy, read-only, 2026-09-16)

**Standing.** Written by the read-only desk deputy from `research/brief4/RULING.md` §4 (consequences register), §6 (amendment) and §7 (Ryan's gate decisions). **This plan carves nothing.** It is the ordered contract the *carve session* executes. Every engine-touching task is gated by standing rule 11 (zero editors, then confirm the loaded level) and rule 7 (project match). **This plan names NO engine API** — the Water-plugin-vs-meshes choice is the carve session's, and its first task (T0) is to establish the 5.8 surface via `docs/ue58-api-protocol.md` and the reflected-surface rule.

**The water set is FIXED by §7** (nothing here re-opens it): carve **A @ 180 m** (id 4893), **B @ 140 m endorheic/closed** (id 11877), **D @ 590.9 m** (id 8377); build the **north cascade D→tarn** (§6.4, every lip a fall by construction); add **inflow falls for A and B** (§3 coupling + the mandatory elevation test); **C is NOT carved** (deferred to the region-edge ruling). Total placed falls stay inside the **10–15** cap. **Tarn B has no outlet — the 17 m Option II notch is struck**, so there is **no cut at the (913,1899) lip**; the south river is only the reach *below* the lip, fed by its own catchment.

**Restore discipline (RISKY-OP CHECKPOINT).** The named restore tag is **`pre-brief4-water-carve`**, set at a green-suite commit BEFORE T3 (T1). This is the archetype the checkpoint rule was written for (`CLAUDE.md` RISKY-OP CHECKPOINT; standing rule 3).

**Heavy-op law.** Every editor/GPU task logs free RAM first (`scripts/resource_guard.py`, RECIPES R10), runs one at a time (pipeline rule 5), and launches with `-noxgecontroller` (R-XGE; the perf-stall cause, PROGRESS Q9). Heightmap is edited **through the pipeline off-disk, never by editor sculpt** (standing rule 4); the `.png` is a 16-bit single-channel write (texture-conversion skill: the 16-bit trap).

---

## THE ORDERED TASKS

Each task: **what → read-back (rule 12: applied AND read back from the engine/artefact) → acceptance (rule 13: sample count beside the verdict)**.

### T0 — Establish the 5.8 water-implementation surface (FIRST; §4.6)
- **What:** decide Water plugin vs static water meshes for the three lakes + the cascade + the placed falls. Open `docs/ue58-api-protocol.md` and the 5.8 water docs; establish every API/property by the reflected-surface rule before any call. **This plan names none.**
- **Read-back:** the chosen approach recorded with its doc citation and the reflected-surface enumeration that proves each name exists in *this* 5.8 build.
- **Acceptance:** a named approach whose full API surface is established live (not quoted); the geometry/levels below are unchanged by the choice (water surfaces are rendered at the §7 levels regardless).

### T1 — Restore checkpoint (RISKY-OP; standing rule 3)
- **What:** with the offline suite green, `git tag pre-brief4-water-carve` at HEAD; commit any pending work first.
- **Read-back:** `git tag --list pre-brief4-water-carve` resolves to the green commit; `git show` confirms the SHA.
- **Acceptance:** tag present, points at a commit where `scripts/run_offline_suite.py` has NO FAILURES (or only the known-allowed plan-freshness red, which T10 clears).

### T2 — Water recipe block (NEW-ELEMENT RULE; §4.6; pipeline rule 2)
- **What:** author the water recipe (in `recipes/alpine_8k.json` or a new `recipes/water.json` referenced from it) carrying EVERY level/extent from JSON, none hardcoded: A id4893 @180, B id11877 @140 (flag **endorheic/closed, no outlet**), D id8377 @590.9; the north-cascade route + pool lips + per-lip `notch_m` (from `research/brief4/input/hydro_amendment.json` `south_river_ladder`/`north_cascade`); the A/B inflow-fall placements; the **10–15 fall cap**; and the **~180 m never-exceed ceiling for basin 11877** (§1 LAKE B hard constraint — a future "raise the water" tweak past it floods 303 buildings). Add the new element's recipe per template (import/compression/LOD/collision if meshes; surface params if plugin).
- **Read-back:** re-load the written recipe and assert each level/extent equals its `hydro_amendment.json` / RULING §7 source to the value.
- **Acceptance:** validates against `recipes/schema.md`; re-running the authoring step is idempotent (pipeline rule 3); the 11877 ceiling field is present and machine-readable (not prose — §1).

### T3 — The carve (heightmap edit via the pipeline; §4.6; standing rule 4)
- **What:** off-disk 16-bit edit of `terrain/alpine_8k.png` applying ONLY the recipe's cuts: the north-cascade pool-lip notches (`notch_m`, metres) and any fall-lip notches within the cap. **No 17 m town-lip notch (endorheic).** The lakes are **fill-to-level of existing terrain — no carve creates their depth** (§0 instrument premise); their surfaces are water, not excavation. Near B's ~0.12 m floor a lip notch has essentially no downward headroom (§4.6) — clamp, do not underflow.
- **Read-back:** re-read the edited PNG; assert `mode I;16`/16-bit (texture-conversion trap); diff against the pre-carve PNG and assert the changed-pixel set ⊆ the recipe's notch cells; assert `min height ≥ 0` and `max ≤ 2560 m` (16-bit encodable span, `alpine_8k_height_4x.json:30-33`).
- **Acceptance:** PNG sha256 changes; changed pixels are exactly the declared notches (count reported); measured z-span re-read and within the encodable span; every cascade/fall lip present. Restore tag T1 is the undo.

### T4 — Weightmap re-derivation + wet_shore unlock + the `--expand` amendment (SAME COMMIT; §4.4)
- **What:** run `scripts/derive_layer_weights.py` with the new water levels so **wet_shore** (within 4 m of a water level) becomes non-zero and the RESERVED **flow** channel gains meaning (`textures/alpine_8k_w8_sidecar.json:5,58`); **dirt_path stays 0** (its gate is the path network, not water — sidecar:59). **In the same commit**, amend the `--expand` refusal (`RECIPES.md:19471` — the deputy's §4 cited 19459; line drifted, re-locate by the `wet_shore or dirt_path` string) so non-zero wet_shore no longer refuses, while non-zero dirt_path still does.
- **Read-back:** re-read the weightmap; assert wet_shore>0 pixels lie only within 4 m of a §7 water level; assert dirt_path==0 everywhere; run `--expand` three directions (non-zero wet_shore → PASS; non-zero dirt_path → REFUSE; both zero → prior behaviour).
- **Acceptance:** weights come from ONE derivation (NN24, no re-implementation); sidecar updated with the non-zero wet_shore reason replacing the "needs Brief 4's water level" zero; the `--expand` amendment proven in the same commit (3 directions, sample counts reported).

### T5 — Material re-apply → capture (§4.5; pipeline rule 4)
- **What:** re-apply `M_Alpine8K` against the new weightmap; run `scripts/capture.py`.
- **Read-back:** the four ratified station captures render; wet_shore reads at A/B shorelines in-frame.
- **Acceptance:** capture succeeds at near_ground/mid_slope/vista + Bench_ground; no tonal regression vs the A-6 baseline at the ratified stations (deltas reported).

### T6 — Navmesh rebuild + reachability re-measure (§4.5, §4.3)
- **What:** rebuild the 72 navmesh bounds volumes against the new water (water non-walkable); re-run the BFS reachability measurement.
- **Read-back:** navmesh rebuilt (component count read back); reachable km² and z-span re-measured off the post-water surface.
- **Acceptance:** the two spec MEASUREMENT figures (**z-span 0–1552.5 m**, **36.53 km² reachable**) are re-measured and the one-screen spec updated with the new numbers (both go stale by construction — §4.3); no NaN.

### T7 — Bench_ground re-station (X-6; §4.1)
- **What:** Bench_ground (`col_row (1680,780)`, z 65.4 m) is ~115 m under lake A. Derive a replacement on A's 180 m shoreline — a derived location (puts non-zero wet_shore in the surface-metrics frame, curing X-6's Snow/ForestFloor-0px complaint in the same move), not an aesthetic pick. Before reusing the A-6 "zero" baseline capture (`STATE.md` Block D-1 item 6), confirm which station it belongs to.
- **Read-back:** the new station loc re-read from terrain — sits above the 180 m surface and on/near A's shore; the A-6 zero-baseline station identity confirmed from the capture record.
- **Acceptance:** station derived (method recorded, not aesthetic), written to `alpine_8k_height_4x.json` stations + the bench station files with provenance; every Bench_ground-keyed series is marked "ends at the carve" (§4.1).

### T8 — Encounter re-verification (§4.3 — the SILENT GAP; a named task, not an assumption)
- **What:** `encounters/alpine_8k_verified.json` stamps FROZEN evidence (`_verify/20260827_navcalib/encounter_rows.json`), so the E-4 freshness machinery will **never** flag it — yet the 317 encounters were placed on the pre-water surface and some plausibly sit inside A/B/D/pool footprints. Compute which of the 317 fall inside a §7 water footprint; relocate or remove them.
- **Read-back:** count of encounters inside each water footprint (A@180, B@140, D@590.9, cascade pools), reported with the total (rule 13 — a zero count must be a measured zero, not an unrun check).
- **Acceptance:** drowned encounters resolved (relocated/removed per `recipes/encounters.json` density+separation+settlement-exclusion); the verified set re-frozen with a new evidence stamp; the 317 figure re-stated.

### T9 — Foliage regeneration (X-1; §4.2 — AFTER the carve)
- **What:** re-derive the **±2% of 219,659** acceptance and the **−20% floor** for the POST-water world FIRST (~140 ha of plantable ground goes under water, so the ruled count moves down and the unamended gate misfires both ways — handoff:76-79); then regenerate through the D-4 planting-field contract (`scripts/derive_planting_field.py`; the `place_foliage` rewire "happens with the Brief-4 water carve", its docstring:45-49). The FLOOR gate reads the ACTUAL placed count (`place_foliage.py:1210`), not the request.
- **Read-back:** post-water plantable area measured; the re-derived count band read back; FLOOR/SLOT gates evaluated against the actual placed count.
- **Acceptance:** floor/slot refusal gates green on the NEW band (not the stale 219,659 band); the 4 live foliage plans (`foliage/alpine_8k_Conifer.json`, `_ConiferPine.json`, `_SpruceSub.json`, `_SpruceSapling.json`) re-stamped — their DIFFERS resolved BY the regeneration itself, not by 1b waivers (§4.3).

### T10 — Freshness reconciliation (§4.3; E-4 / R-PLANSTALE as amended)
- **What:** the carve moves `terrain/alpine_8k.png`'s hash. Run `scripts/check_plan_freshness.py --reproduce`. The **town plan** (`city/alpine_basin_town_plan.json`) stamps the heightmap and is DIVERGENT-BY-RULING — that binding "expires the moment either hash moves" (R-PLANSTALE 1d) → re-rule or restamp THIS session. The 4 foliage plans DIFFER → resolved by T9.
- **Read-back:** freshness verdict per consumer read back from the checker.
- **Acceptance:** `scripts/run_offline_suite.py` green post-carve (or every red is a ruled, recorded waiver); the town-plan divergence re-ruled or restamped in-session (not left expired).

### T11 — Perf (§4.7; R-PERFBUDGET)
- **What:** water surfaces are new GPU cost on a machine with a DEVICE_HUNG history. Run R-PERFBUDGET, all four zones, `-noxgecontroller` mandatory (R-XGE).
- **Read-back:** per-zone frame cost read from the standalone perf run (residency + FOV + exposure applied AND read back — rule 12).
- **Acceptance:** all four zones PASS R-PERFBUDGET (per-zone numbers + the budget reported); VRAM peak logged against the abort ceiling.

### T12 — HLOD (§4.5 — folded, NOT rebuilt now)
- **What:** the carve re-dirties the freshly-rebuilt 4096 L2 cells it touches. Per R-O1 / X-2 this folds into the SINGLE post-Brief-5 rebuild; it is **not** rebuilt in the carve session. Safe for the bench because proxies never render in bench frames (B-1, `STATE.md:107-112`).
- **Read-back:** the set of dirtied cells recorded (which cells the notches touch).
- **Acceptance:** recorded as owed to the post-Brief-5 rebuild; NOT rebuilt now; the record names the cells so the later rebuild is complete.

---

## CONSEQUENCES REGISTER → TASK MAP (every §4 line has a home)

| §4 consequence | Task |
|---|---|
| 1. Bench_ground re-station (X-6) | **T7** |
| 2. Foliage regeneration sequencing (X-1) | **T9** (band re-derive first) |
| 3. Freshness cascade (4 foliage DIFFER, town DIVERGENT expires) | **T10** (+ T9 for foliage) |
| 3. Silent gap: frozen encounters, stale z-span/reachable | **T8** (encounters), **T6** (figures) |
| 4. wet_shore unlocks; dirt_path does not; `--expand` amend | **T4** |
| 5. weightmap → material → capture → navmesh; HLOD folds | **T4→T5→T6**, **T12** |
| 6. process law: recipe block, JSON levels, pipeline edit, named tag, encodable span, engine choice | **T2, T3, T1, T0** |
| 7. perf after water, four zones | **T11** |

## OPEN CHOICES LEFT TO THE CARVE SESSION (not decided here)

- **Engine implementation** (Water plugin vs static water meshes) — **T0**, under `docs/ue58-api-protocol.md`. This plan decides geometry and levels only and names no API (RULING §4.6).
- **Lake A's exact shoreline shape at 180 m** and B at 140 m — Ryan reserved the SHAPE as an aesthetic he may want rendered (§5.2); the LEVELS are fixed (§7). If he asks to see alternates, render before finalising T2's extents.
- **B's "bottomless tarn" character** — the 140 m shaft is kept as a Brief-6 cave/underwater hook (§5.4, and endorheic makes the underground outflow its lore); shallowing it is a later call, nothing downstream depends on it yet.

## FENCES THAT STOP THIS SESSION (not this plan)

- **Rule 11 / O-5:** any editor-touching task (T5, T6, T11, and T0 if it live-probes) is BLOCKED while a leftover editor runs — the PID-4452 UnrealEditor (OPEN.md O-5) must be resolved by Ryan first. T2/T3/T4/T8 are off-disk and unblocked.
- **Disk:** an HLOD rebuild (T12, deferred) needs the C:\UnrealDDC headroom the closure list tracks; T12 is folded to post-Brief-5 precisely to avoid paying it now.

*Filed by the read-only desk deputy, 2026-09-16. Sources opened: `research/brief4/RULING.md` §4/§6/§7, `research/brief4/input/hydro_amendment.json`, `textures/alpine_8k_w8_sidecar.json`, `RECIPES.md` (`--expand` refusal), `scripts/derive_layer_weights.py`, `scripts/derive_planting_field.py`, `scripts/check_plan_freshness.py`, `scripts/place_foliage.py`, `scripts/capture.py`, `scripts/resource_guard.py`, `encounters/alpine_8k_verified.json`, `city/alpine_basin_town_plan.json`, `research/brief4/input/alpine_8k_height_4x.json`. No heightmap touched; no engine API named.*
