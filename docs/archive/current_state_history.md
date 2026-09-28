# ARCHIVE — THE CURRENT STATE HISTORY

> # ⛔ HISTORY. NOTHING HERE IS LIVE.
> **Decisions citing this file are errors.** Every block below was the live
> `CURRENT STATE` of `CLAUDE.md` on its date and has since been superseded.
> They are kept verbatim because this project never deletes a record — but a
> session that reasons from them is reasoning about a world that no longer
> exists. **The live block is the one in `CLAUDE.md`, and there is exactly
> one.**
>
> Read this file only when investigating HISTORY — why a decision was taken,
> what a number used to be, when a defect appeared. Never to decide what to
> do next.

Split out of `CLAUDE.md` on 2026-08-29 by the doc-consolidation unit.
**44 blocks, newest first**, byte-identical to their originals.
⚠ GAP: the 2026-09-07 and 2026-09-08 blocks were superseded without being
archived here; they exist only in `CLAUDE.md`'s git history (noticed
2026-09-10 while archiving the 09-09 block).

---

# CURRENT STATE — 2026-09-10e (BRIEF 3: RANGE RULED TO 512; CARD SET THE WHITE POINT) — **SUPERSEDED by the 2026-09-11 block.**

**Brief 3 Tasks 0+1 complete on branch brief3-task0-range768 (merged);
editor closed gracefully; zero processes; tree clean.**

## TASK 0 — THE PERF GATE DECIDED THE RANGE (R-RANGE LOCKED AT 512)

768 m RED'd: treeline GPU p90 7.86 vs 7.0 (+12.3% vs 10% tol); every
game/frame cell held. The PRE-COMMITTED fallback executed: **512 m
LIVE**, instanced HLOD 2 km, merged declared-unchanged. 512 sweep:
**check_perf PASS every zone** (treeline 7.52 +7.4% tol, vista 8.82
+3.7% tol — and treeline only dropped 0.34 ms from 768, so much of its
rise belongs to the 2 km INSTANCED layer). Residency missing 0 at BOTH
ranges once the expectation was fixed TWICE at the rim (LESSONS
2026-09-10f): the engine's range is a 3D SPHERE (2D-XY expectation
inverted its own premise), and container-class desc bounds are 256 m
cell boxes (expected = farthest-corner-inside; rim = NO VERDICT).
First-ever missing-0 target near_ground — the eternal straggler was a
rim actor. Boundary at 512: vista landscape 742 m / foliage 585 m;
near_ground 857/681. Re-raising to 768 is a RULING with R-RANGE's
tables (margin: 0.16 ms past tolerance at one zone).

## TASK 1 — TWO CARD STEPS, RULED CAP, HONESTLY SHORT OF THE BAND

    WB 5200   R/G 1.2623  B/G 0.7429
    WB 4026   R/G 1.1070  B/G 0.9322   (Planck-derived, audited)
    WB 3751   R/G 1.0584  B/G 0.9547   highlight band PASS both steps;
                                        card band 0.97-1.03 NOT reached

Each step removes ~45% of the residual (the chain is not a blackbody
von-Kries — BRIEF 3.7's one-step claim measured optimistic). Converged
neutral extrapolates to **~3,500-3,600 K, UNAPPLIED** — a ruling's
number. TemperatureType PINNED white_balance (was unset since the grade
existed); white_tint 0 (green common factor 1.016); warmth_bias_k 0.

## PROCESS

apply_streaming_range built+audited PASS clean (signature-identified
grids; exact-case names — the class has no Python wrapper); the range
applier, apply_lighting and the bench all self-commit their packages.
perf_standalone's hardcoded artefact date fixed. Desk tools verified
(tiling selftest PASS; b2b meadow peak 0.025 = no repeat, per BRIEF 0.2).

## OPEN

    Brief 3 Task 2 next: layer set + derived weights (offline first)
    Card neutral ~3.5-3.6k K unapplied; card band unmet at the 2-step cap
    Clouds 0.1 capture; Brief 2c (both BACKLOG'd, ruled)
    0-dirty close wedge (open question; 5 clean closes since)
    Q6/Q9/Q10/Q11 unchanged

## NEXT — NEEDS RYAN

The 768-vs-512 range ruling (R-RANGE tables); whether to take the
extrapolated ~3.55k K neutral or hold at 3751. Then Brief 3 Task 2.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED

# CURRENT STATE — 2026-09-10d (GREY CARD LIVE; SHADOW BAND PASSES; HLOD LADDER MEASURED) — **SUPERSEDED by the 2026-09-10e block.**

**Editor closed gracefully (first attempt, again); zero processes; tree
clean. Five rulings executed.**

## THE RULINGS, DONE

    1 band     shadow_tint_B re-derived 1.10-1.60 (neutral WB). Brief
               2b's 1.1243 PASSES, verified live. shadow_tint follows
    2 card     R-GREYCARD LOCKED: 3 cards placed+saved, regions
               projected from read-back, mask verified both directions
               (masked scene value IDENTICAL to the card-free frame)
    3 relabel  Lumen far-field = Brief 2c (REGISTER + BACKLOG)
    4 clouds   coverage 0.3 = near-total overcast, LOGGED (R-CLOUDS
               REJECTED: the parameter is not a sky fraction). Next: 0.1
               with read-back + vista sky luma. NOT run, per ruling
    5 ladder   MEASURED (hlod_ladder_vista.json): main range 25600 cm
               (RuntimePartition.cpp:27, confirmed by behaviour); HLOD
               ladder = parent x2 (:34): instanced 512 m, merged 1024 m.
               Vista-measured resident bounds-centres: real content to
               640 m, instanced HLOD to 742 m, merged to 1506 m. No
               HLOD visualize mode exists in 5.8 (VERIFIED). Brief 3 is
               written with these numbers

## ⭐ THE CARD'S FIRST READING IS THE NEXT WB QUESTION

near_ground card (uniform, sunlit): **highlight_tint R 1.2170 / B 0.7162
(FAIL 0.85-1.15); WB ratios R/G 1.2623, B/G 0.7429.** A sunlit NEUTRAL
reads warm at WB = sun 5200 because the card sees the GROUND-LEVEL sun —
the atmosphere reddens it below its source temperature
(atmosphere_sun_light true, 12° elevation) — so WB at source temperature
under-corrects BY CONSTRUCTION. The card's ratios are the direct
correction input; whether to chase neutral or keep the warmth is a
LOOK decision — Ryan's, with a real instrument behind it now.

## AUDITS (both altitudes logged)

greycard/HLOD changeset: FIX, 7 findings, all applied (exact-shape
refusal both directions; per-station projection guard; band cited;
BaseColor read-back-or-refuse on reuse; error-string bool trap;
occlusion variance ceiling — provisional 0.10, first measured std
0.0146). The refusal-printer fix (2026-09-10e) printed its first live
refusal detail correctly.

## OPEN

    0-dirty close wedge   BACKLOG'd open question; did NOT recur in
                          either close since
    clouds 0.1 capture    BACKLOG'd (ruling 4)
    Brief 2c              Lumen far-field, ruling-gated, relabelled
    Q6/Q9/Q10/Q11 unchanged

## NEXT

Brief 3 (surface) against `target_b2b/near_ground.png`, written with the
measured streaming ladder. The card's WB reading awaits a look ruling.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED

# CURRENT STATE — 2026-09-10c (BRIEF 2b MEASURED; PERF LAW RE-RATIFIED) — **SUPERSEDED by the 2026-09-10d block.**

**Editor closed GRACEFULLY (first attempt — the wedge did not recur);
zero processes; tree clean. Send-back updated:
`research/brief2/for_research/` (TINTS_brief2b, REGISTER_DIFF, 2 stills).**

## BRIEF 2b — SUN 5200 K, ONE ATTEMPT, MEASURED

Sun 7800 → 5200 K (low alpine sun, 4500–5500 K), WB 5200 by R-GRADE's
rule. Applied, saved, committed (9455524f); sun 5200.0 and WT 5200.0
read back from the engine. Target-class capture (residency missing 1/2,
the class's constant): **both clauses FAIL** —

    shadow_tint_B   1.1243   (band 1.3-1.7)
    highlight_tint  R 1.3817 / B 0.2653   (band 0.85-1.15)

**The finding**: the only shadow PASS ever (1.4456) had WB 1300 K BELOW
its sun. Under neutral WB the band may be unreachable from temperature
at ANY sun value (7800/7800 → 1.258 truth; 5200/5200 → 1.124 target).
The remaining shadow-blue lever is the SKY-LIGHT side, not WB.
highlight_tint measures the meadow's albedo (2026-09-09e) — the
acceptance needs a neutral reference surface or a different station.
Full table: R-GRADE + TINTS_brief2b.json. Brief 3 (surface) is written
against `_verify/bench/2026-09-10/target_b2b/near_ground.png`.

## PERF LAW — RE-RATIFIED FROM THE STANDALONE CLASS (R-PERFBUDGET)

From E3 standalone 4K p90 ONLY: GPU 10.5 / 7.5 / 7.0 / 8.5 (1.2×,
rounded up to 0.5), game 6.0 flat, frame 16.6. Editor-derived budgets
REJECTED (the game thread tracked the 60 Hz clamp, EditorEngine.cpp:
2523-2566); the standing plaza-Game RED CLOSED as instrument artefact;
"game thread binds" RETIRED with the class — the GPU binds everywhere.
`check_perf` refuses non-STANDALONE artefacts (exit 6; selftest 12/12);
treeline/vista basis_invalidated lifted (standalone ran at the current
cameras); frame budget judged; current verdict PASS all zones. Audited
FIX → all findings applied.

## OPEN

    0-dirty close wedge  RULED open question, BACKLOG'd, NOT investigated
                         (did not recur this close)
    sky-light lever for shadow_tint_B under neutral WB (NEW, from 2b)
    REGISTER "Brief 2b" name collision: register's B2.12 (Lumen
                         far-field, Task 7, NOT RUN) vs the sun-temp 2b
                         executed today — flagged in REGISTER_DIFF
    Q6/Q9/Q10/Q11 unchanged
    bench_capture refusal printer KeyError FIXED (2026-09-10e) — it had
                         truncated every refused derived run's detail

## NEXT

Ryan reads TINTS_brief2b + REGISTER_DIFF. Brief 3 (surface: ground,
rock, forest floor, snow by aspect, tiling) against the post-2b
near_ground frame. The sky-light question is the tint successor if the
shade still reads dead.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED

# CURRENT STATE — 2026-09-10b (BRIEF 2 COMPLETE: T0–T6, RULINGS EXECUTED) — **SUPERSEDED by the 2026-09-10c block.**

**All five 2026-09-10 rulings executed. Editor CLOSED, zero processes,
tree clean. Send-back delivered: `research/brief2/for_research/`
(SENDBACK_2026-09-10.json + 3 new truth-mode stills).**

## THE RULINGS, DONE

    1 WB       recipe 8800 -> 7800 K (= the sun, never above). 8800
               REJECTED in R-GRADE. Sun 7800 K suspect -> Brief 2b (BACKLOG)
    2 save     apply_lighting saves + COMMITS its own packages after
               read-back (R-LIGHTSAVE; audited FIX->PASS). Crash lesson at
               both altitudes: LESSONS 2026-09-10
    3 restore  world matches recipe on EVERY axis (fog 0.00416/0.019324/
               0/18674, sky 1.0, mie 0.01, WT 7800); 0 dirty; pkgs in git
    4 sky mask depth split live (R-DEPTHBIN, audited). T1-T5 re-judged
               offline, all 15 rows
    5 clouds   T6 run as specified. R-CLOUDS LOCKED, both clauses PASS

## BRIEF 2 — FINAL

    T0 PASS   T1 dE FAILS (band not fog)   T2 R-FOG LOCKED   T3 PASS
    T4 3/4    T5 measured at 7800 K        T6 clouds PASS 2/2

    shadow_tint_B  1.0866 (8800) -> 1.2580 (7800): +0.17 toward band,
                   0.042 BELOW 1.3 floor. Lever: Brief 2b sun temp
    highlight_tint toward neutral; 0.9-1.1 UNREACHABLE at near_ground
                   (green grass, LESSONS 2026-09-09e). Truth vs target
                   frames are different calibration classes — R-GRADE

## THE DEPTH RE-JUDGE REWROTE Q15

mid_slope geometric sky STABLE 0.728–0.758 across T1–T5; the 0.79
"non-sky band" was ~0.72 MISCLASSIFIED SKY (true non-sky flat 0.033).
Colour mask was NEVER valid at mid_slope (T2 blue-sky era: 0.255 colour
vs 0.744 depth). Vista dE under depth FELL 0.224 -> 0.194 task-over-task
— desaturation converged fog toward sky; colour reported the inverse.
Clouds land in featureless-SKY (0.144 -> 0.366), geometric sky invariant.

## PROCESS FINDINGS (both altitudes logged)

LESSONS 12.10 RECURRED (payload dot-p-y trap, via RECIPE PROSE): guard
moved to the compose point (apply_lighting._run). LESSONS 2026-09-10c.
R-EDITOR-CLOSE FOURTH OCCURRENCE: deadlocks at 0-DIRTY too — window
destroyed, process wedged idle; kill per original step 4 was clean,
EMPTY restore data. Rule unchanged. LESSONS 2026-09-10d.

## OPEN

    Q6/Q9/Q10/Q11 unchanged (cores, shard, -BuildHLODs, survey shots)
    Q15 CLOSED-AS-REWRITTEN above; residual non-sky flat is ~3 pts

## NEXT

Ryan reads the send-back. Then: Brief 2b (sun temperature, one variable,
one capture — white_temp follows by rule); Brief 3 (surface) is written
against the post-Task-5 near_ground frame. Perf-budget ruling (60 Hz cap)
and ground cover below its cull still pending.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED

# CURRENT STATE — 2026-09-10 (CRASH RECOVERY: WORLD LOST BRIEF 2) — **SUPERSEDED by the 2026-09-10b block.**

## THE CRASH, AUDITED

Machine died AFTER `0a04be1c` (22:52): no torn files, tree clean. It killed
the DEADLOCKED R-EDITOR-CLOSE, so **the 4 dirty lighting packages never
saved** (preserved: `_trash/autosaves_launch_20260910161826/`).

**LIVE WORLD vs RECIPE — every Brief-2 value is GONE** (read back, 0
dirty): fog 0.0015/0.03431/150000cm vs recipe 0.00416/0.019324/0, Z 10100
not 18674 (T2); sky 1.8 not 1.0 (T3); mie 0.003996 not 0.01 (T4);
white_temp 6500 not 8800 (T5, unruled).
**The recipe is truth; the world is stale.** T1–T5 `_verify` evidence stays
valid (captured pre-crash). NOT reapplied — T5's unruled 8800 K is inside
`apply_lighting.py`'s run, so reapply WAITS ON THE RULING. Editor left
OPEN, clean.

## BRIEF 2 — ATMOSPHERE

    T0 void test    PASS (skyline IoU 0.970, MRQ truth)
    T1 fog coupling MEASURED. dE FAILS -- the band is NOT fog
    T2 fog derived  MEASURED. R-FOG LOCKED
    T3 sky light    PASS. shadow_tint_B 1.7527 -> 1.4456
    T4 Mie 0.01     3 of 4 clauses PASS
    T5 grade        ⛔ FAILS -- NEEDS RYAN. No longer applied (crash)
    T6 clouds       NEVER STARTED

## ⛔ TASK 5 NEEDS A RULING — LESSONS 2026-09-09e

**The WB rule contradicts its citation**: BRIEF §3 says `white_temp = sun +
~1000 K`; its own example ("sun 6500 / WB 5600") is 900 K BELOW → 6800 K.
Scene.h:1505: WhiteTemp is what the scene considers WHITE, so 8800 K on
a 7800 K sun renders it WARM — highlight_tint 1.3748/0.1895 (want 0.9–1.1),
shadow_tint_B 0.9829, breaking Task 3's band. `TemperatureType` unset; the
modes are INVERSE. **R-GRADE NOT LOCKED.**

## ⛔ SKY CLASSIFIER ERODING — LESSONS 2026-09-09e

`SKY_BAND` keys on colour (`b-r >= 0.06`); Brief 2 desaturates the sky BY
DESIGN (mid_slope sky sat T2 0.3462 → T5 0.0000), four metrics stand on
it. **Replace with the depth split.** T5 mid_slope rows not comparable.

## WHAT IS PROVEN

**R-FOG LOCKED** (shader-verified base 2), mid_slope `haze_rise` PASS;
near_ground STRUCK (rows aren't depth). **Truth runs through MRQ**:
`truth.grid` `MainGrid` → `MainPartition` (override was ALWAYS a no-op);
residency missing 0, PASS; "PIE cannot be force-loaded" RETIRED. **Depth
pass** `/Game/Bench/M_SceneDepth`, geometry-validated — `bench_capture
--depth`. **Q12 CLOSED** (resident, 12 km).

## OPEN

    Q6/Q9/Q10/Q11 unchanged (cores, shard, -BuildHLODs, survey shots)
    Q15 mid_slope band: ~18 pts proxy flatness (BRIEF 3) + ~22 pts
        residual, BRIGHTER than sky so NOT fog

## NEXT — NEEDS RYAN

Task 5's WB direction — THEN one `apply_lighting.py` run restores the
world (T1–T4 are ruled). Also: perf-budget ruling (60 Hz cap); ground
cover below its cull. Send-back delivered.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED

# CURRENT STATE — 2026-09-09 (BRIEF 2: TASKS 0–5 DONE, TASK 5 NEEDS A RULING) — **SUPERSEDED by the 2026-09-10 block.**

**Phase E CLOSED.** Editor closed (R-EDITOR-CLOSE); tree clean.

## BRIEF 2 — ATMOSPHERE

    T0 void test    CLOSED, PASS. Not void. skyline IoU 0.970 (MRQ truth)
    T1 fog coupling APPLIED. dE FAILS -- the band is NOT fog
    T2 fog derived  APPLIED. R-FOG LOCKED on the derivation
    T3 sky light    PASS. shadow_tint_B 1.7527 -> 1.4456, lit_luma +0.6%
    T4 Mie 0.01     3 of 4 clauses PASS
    T5 grade        ⛔ FAILS -- NEEDS RYAN, left applied
    T6 clouds       NOT RUN (stopped on the ruling)

## ⛔ TASK 5 NEEDS A RULING

**The WB rule contradicts its citation.** BRIEF §3 says `white_temp = sun +
~1000 K` and cites "ED: sun 6500 / WB 5600" — 900 K **below**. `Scene.h:1505`:
WhiteTemp is what "the scene considers as white light", so 8800 K on a 7800 K
sun renders it WARM.

    highlight_tint  R 1.3005 -> 1.3748, B 0.2431 -> 0.1895 (want 0.9-1.1)
    shadow_tint_B   1.4456 -> 0.9829  -- broke Task 3's band

The citation gives **6800 K**. The rule change is Ryan's; nothing tuned, 8800
K still applied. `TemperatureType` (Scene.h:1503) is unset and picks White
Balance vs Color Temperature — INVERSE. **R-GRADE NOT LOCKED.**

## ⛔ THE SKY CLASSIFIER IS ERODING — LESSONS 2026-09-09e

`SKY_BAND` keys on colour (`b-r >= 0.06`); Brief 2 desaturates the sky by
design:

    mid_slope sky   T2 0.3462 -> T4 0.1676 -> T5 0.0000
    vista sky       T3 0.4240 -> T4 0.3660 -> T5 0.2468

Four metrics stand on it, and the failure CORRELATES with what is measured:
sky read as non-sky inflates the band §0.3 explains. **Replace with the depth
split.** T5 mid_slope non-sky is not comparable with earlier rows.

## WHAT IS PROVEN

**R-FOG LOCKED** on the derivation (fog_budget, shader-verified base 2),
mid_slope `haze_rise` PASS. near_ground's lines STRUCK: rows aren't depth.

**Truth runs through MRQ.** `truth.grid` was `MainGrid` (SpatialHash); this
world is HashSet → `MainPartition`, so the override had ALWAYS been a no-op.
Corrected: residency **missing 0**, first PASS. 2026-09-06's "PIE cannot be
force-loaded" is RETIRED.

**Depth pass**: no depth class in 5.8; authored `/Game/Bench/M_SceneDepth`
emitting log2 depth. Pass is sRGB — validated against geometry, 3.28 vs
3.36 m. Use `bench_capture --depth`.

**Q12 CLOSED**: those actors are resident at 12 km.

## OPEN

    Q6/Q9/Q10/Q11 unchanged (cores, shard, -BuildHLODs, survey shots)
    Q15 mid_slope band = ~18 pts proxy flatness (BRIEF 3) + ~22 pts
        residual at FULL residency, BRIGHTER than sky so NOT fog

## NEXT — NEEDS RYAN

Task 5's WB direction; the perf-budget ruling (60 Hz cap); ground cover
below its cull. Send-back `research/brief2/for_research/`.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED

# CURRENT STATE — 2026-09-06 (residency measured: the world was never there; HLOD is the blocker) — **SUPERSEDED by the 2026-09-07 block.**

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Editor CLOSED** (0 dirty). Brief 1,
`research/brief/brief1_distance_as_angle/brief1/`. Detail in LESSONS +
R-BENCHCAPTURE / R-BENCHSTATION.

## RESIDENCY: DECLARED, APPLIED, READ BACK FROM INSIDE PIE

`bench_residency_probe.py` runs on the PIE game thread via MRQ's
`end_console_commands` (`py`); remote exec cannot reach that thread. First
measurement:

    near_ground 12/1024 components (2,781 foliage)   mid_slope 16/1024 (265)
    vista 16/1024 (265)

**1.2–1.6%. Every bench frame ever taken here was rendered on a world that was
essentially absent** — `near_ground`'s 2026-09-05 "confirmed by render" is
**WITHDRAWN**.

## FORCE-LOAD: THREE LEVERS, NONE MOVED IT

Warm-up 180/300 frames; `OverrideRuntimeLoadingRange` 12 km (log confirms it
executed); `load_all_world_partition_regions()` took the EDITOR to 1024/1024,
256 proxies, 217,102 instances — **PIE still reported 16/1024, so PIE does not
inherit editor region loading.** **UNEXPLAINED.**

## ⛔ HLOD IS THE BLOCKER, AND THE ANSWER

`Alpine8K_HLODLayer_*` exist as layer DEFINITIONS and **not one built
`WorldPartitionHLOD` actor package exists**. Beyond the ~1 km streaming range WP
shows a proxy if built and nothing if not — exactly what `mid_slope`/`vista`
are. **Q4: Task 7 ahead of imposters** is the precondition. **Q5: Task 4 before
budget re-ratification.**

## THE DOLLY RENDERED; THE SCORE IS NOT A BASELINE

180 frames, `temporal_stability` = **0.66877**, but mean luma drifts
0.3486→0.2749 over 8.4 m — auto-exposure, which survives the tool's local Weber
normalisation and buries any pop. Now profile cvars
`r.DefaultFeature.AutoExposure 0` + `r.EyeAdaptationQuality 0`. NOT VERIFIED.

**MY OWN ERROR, LEFT REFUSING:** `near_field.expect_components_within_radius: 16`
was the whole-world count in a field meaning something else; the capture measured
**8 within 600 m**. Changing it to 8 is indistinguishable from widening a
tolerance.

## ARTEFACTS `_verify/bench/2026-09-06/` (158 MB)

`residency_dev*.jsonl`, `bench_run_dev*.json` ×5, `dolly_stability_dev.json`,
`dev*/` stills, `dev_dolly/dolly/` **18 frames (every 10th)**.

## OPEN / NEXT

    HLOD        Task 7 FIRST. Until built, nothing beyond ~1 km can be
                judged; mid_slope/vista stay UNCONFIRMED.
    exposure    re-capture the dolly, show the drift gone, THEN score.
    force-load  unexplained; fix DumpWorldPartitions output first.
    near-field  re-declare from a near-field measurement, as a tripwire.
    Task 4      standalone -game frame time, BEFORE re-ratification.
    budgets     treeline+vista basis_invalidated; check_perf NO VERDICT

## RPG MAINLINE

Unchanged: town GATED, church BLOCKED, hero PARKED

---

# CURRENT STATE — 2026-09-05 (Brief 1: culls from pixels; the bench passed OK on an empty frame) — **SUPERSEDED by the 2026-09-05 block.**

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Editor CLOSED.** Brief 1, `research/brief/brief1_distance_as_angle/brief1/`.
Forge (09-04b) parked. Detail in LESSONS + three new R- recipes.

## COMMITTED — T1, T2, T3 (partial)

**T1 — every authored cull deletes an object the eye still reads.** px at cull,
4K, typical scale: Conifer **62.9**, Sapling **53.0**, ConiferPine **48.0**,
SpruceSub **40.7** — all four trees above the 40 px DETAIL line; ground species
14.9–21.8. A conifer hits 1.5 px at 30.6 km in an 8.129 km world: **no tree can
be culled to nothing inside it.**

**T2 — `ue_screen_size` was 2x too large.** Source-verified:
`ScreenSize = R/(D·tan(vFOV/2))`, sphere DIAMETER over screen HEIGHT. T1
unaffected.

**T3 — stations re-derived by traced occlusion; rig built; renders.** Old
`treeline` measured 90.6% near terrain / 0% sky; old `vista` 84.2% under 100 m.

    near_ground  -210800,278800  pitch -2.0 yaw -12.8   KEPT (plaza)
    mid_slope    -190000,100000  pitch -2.0 yaw 105.0   was treeline
    vista        -216400, 63600  pitch -4.0 yaw  60.0   was vista

3 CameraActors (FOV 90.0, read back), 4 Level Sequences, `bench_capture.py`,
dev stills 2560x1440. Z TRACED, never heightmap (gap to 1.33 m).

## ⛔ THE BENCH IS NOT USABLE YET

`mid_slope.png` is a **white void**, `vista.png` has a void band — World
Partition cells 2 km+ out never streamed. **The capture printed OK**:
resolution, 11/11 cvars and luma all correct, none looking at CONTENT. New gate
`featureless_fraction` vs predicted sky (mid_slope **93.8/56.4 VOID**) exits 7.
`measure_frame_cost` long refused undeclared residency; the capture tool
did not.

**PROVEN:** px-at-cull, band boundaries, the formula vs SOURCE, the old
stations' failure, read-backs, that the rig renders. **Confirmed by render:
near_ground ONLY. UNBUILT:** `perception` + `cull_cm` (T6), ladder (T7).
**No recipe changed.**

## VERIFY RESULTS THAT DIFFER FROM THE HANDOFF

- **§0a's heights: none of seven survived** (Conifer 14.7→27.317, ConiferPine
  `<h>`→22.10); six of seven UNDERSTATE the defect.
- **`SystemLibrary.get_viewport_size` DOES NOT EXIST in 5.8.** Perf artefacts'
  `viewport_size: null` was a swallowed AttributeError, not editor overhead as
  §6/REGISTER claim. Real: `UnrealEditorSubsystem.get_level_viewport_size()` →
  **[1321, 1421]**, 1.88 vs 3.69 Mpx: **the ratified GPU budgets were measured
  at ~half the judged pixel count.**
- Also: Boulder is not in the mainline; two of three trees already ship the
  shape-band imposter the cull discards; `CVars` is ScriptNoExport;
  `mrq.temporal_samples` is not a cvar. Rest in the recipes.

Artefacts in `_verify/bench/2026-09-05/`: heights, budgets, derivations,
scans, `bench_run_dev.json`, `dev/*.png`

## OPEN / NEXT

    residency   THE BLOCKER. Warm-up frames or a per-shot streaming flush,
                then re-capture and re-check the content gate. Until then no
                dolly, no determinism run, no target profile; mid_slope and
                vista stay UNCONFIRMED
    ss-readback OUTSTANDING T2 acceptance: a mesh's LOD ScreenSize read from
                a live editor. SOURCE-verified, NOT engine-verified.
    budgets     treeline+vista basis_invalidated; check_perf gives NO
                VERDICT. Untouched — need YOUR re-ratification.
    Q3/T4-T9    PerInstanceFadeAmount UNVERIFIED; T4-9 unstarted.

## RPG MAINLINE

Unchanged: town GATED, church BLOCKED, hero PARKED; extras as before.

---

# CURRENT STATE — 2026-09-04b (forge serve: the forge as one web page; fifth world through the API; dist 0.4.0) — **SUPERSEDED by the 2026-09-05 block.**

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Editor CLOSED** (R-EDITOR-CLOSE, three for three on the retry).

## SINCE THE LAST BLOCK (overnight directive: full automation, marketable state)

- **The Layout Author is the keyless front end**: the operator's
  three.js UI + export_digest + import_layout (forge-layout/1 ->
  gated schema). Proven on **uistarter, the THIRD world**, polished
  to **+0.028 EV** (details: MORNING_REPORT addendum 8).
- **The forge applies its own prescriptions now**: cli auto-raises the
  camera once when every sightline blockage carries the gate's
  camera_height_to_clear_m (fired live: 170 -> 317.9 m, after THREE
  builds died on hand-guessed cameras); brief_loop's SITE SCOUT
  relocates a MAX flat site on the flank-above-band refusal (rings
  0.5-3 box-widths, one move per check, lint re-run, brief+recipe
  persisted together — 6 audit findings fixed pre-execution).
- **New CLI legs**: `forge doctor` (preflight, 0 FAIL here), `forge
  polish` (measured-slope EV convergence; stops honestly on an
  INVERTED response — a clamp must not swallow a sign). `forge.bat`
  launcher. **`forge serve`** (operator ask, audited PRE-exec, 9
  findings applied): the Layout Author + a Forge panel on 127.0.0.1 —
  author, click Forge, live log, render + UE-project zip download.
  Localhost-bound is not origin-bound: X-Forge header (CSRF), Host
  allow-list (DNS rebinding), no state change on GET. servetest (5th
  world) forged+polished entirely through the API; zip proven against
  the dist tree. **dist/forge-0.4.0** (321 files): keyless path FINAL —
  `forge author` opens the UI with the real 11-stamp catalogue BAKED
  IN (export_digest --inject, byte-idempotent), packaging gates BOTH
  stamp doors (page + digest) against the live catalogue and REFUSES
  rather than repairs; README rewritten (doctor-first, three input
  paths); vendored selftests pass inside the dist (brief_loop 27/27).
- 12 audit findings across 2 rounds, all fixed; import_layout's
  KeyError-not-Refuse class closed with shape-before-content
  validation (7-refusal battery). MORNING_REPORT addendum 8.

## OPEN / NEXT

    T1          CLOSED BY RULING (operator, 2026-09-04: "finalize a
                tool without one"): the vision leg is an optional
                EXPERIMENTAL extra, labelled untested at every surface
                (CLI refusal, doctor, README); the keyless Layout
                Author path IS the product and is fully proven.
                forge build <image> alone refuses pre-filesystem with
                the two standard commands; doctor: 0 fail 0 warn keyless
    scout-live  PROVEN: fired twice on scoutproof (4th world), village
                relocated 353 m off the flank, PASS ever after. The
                same build turned the auto-raise into a bounded
                FIXPOINT loop (a prescription that changes its own
                measurement must be iterated) and exposed the
                slope/elev two-rules-one-knob oscillation — cycle
                judge BACKLOGGED, evidence _trash/scoutproof_oscillated
    dressing    forge v1 ships terrain+material+lighting+water only —
                foliage/city need a shippable asset base
    ui-polish   the Layout Author UI itself is v1 operator code; its
                digest/import contract is now load-bearing — changes
                on either side must keep export_digest/import_layout
                in step

## RPG MAINLINE (unchanged)

Town re-placement GATED; church texturing BLOCKED; hero PARKED.
Side-project extras (rivers, talus, exposure mechanism) as before.

---

# CURRENT STATE — 2026-08-29c (Gate A approved; perf baseline measured, AT GATE E) — **SUPERSEDED by the 2026-08-30 block.**

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Tree clean. AN EDITOR IS RUNNING** on `/Game/Alpine8K`, rule-7 verified.
**`M_GlobalRGB_Blend` is DIRTY in memory and must NOT be saved** — saving
rewrites bytes the kit manifest SHA-256'd. Restore points:
`pre-doc-consolidation-20260829`, `pre-storey-m-2.0-20260829`.

## ✅ GATE A APPROVED — rulings recorded

One site / two views ratified as **the standard for future concept pairs**.
`azimuth_unsolved` accepted as a legal value. Re-intake `MODULAR_ASSETS` on the
wider seed: approved. Church stays the Phase D candidate; **wood stacks are the
second forge candidate**. Water: roadmap, not authorised. Empty rock-scatter
list: logged, intake 2–3 Megascans stones in a later unit, not now.

## ⛔ AT GATE E — baseline measured, budgets PROPOSED not law

`_verify/perf/20260829_baseline.json`, 300 frames per station, 1024 components
resident, editor viewport.

    zone          GPU p90   Game p90   proposed GPU / Game
    plaza            8.84       9.67        12.0 / 12.0
    main_street      5.73      10.26         8.0 / 13.0
    treeline         7.44      10.80        10.0 / 13.5
    vista            9.24      10.20        12.5 / 13.0

**⭐ THE GAME THREAD IS THE BINDING THREAD AT ALL FOUR ZONES, NOT THE GPU.**
This recipe originally declared a GPU-only budget; it would have policed the
wrong number and reported green while the real constraint tightened.
`per_zone_game_ms` exists *because* of the measurement — which is what
"measured first, then declared" is for. It also corroborates `PHASE2_PLAN`'s
headline risk from a completely different instrument.

**Method:** budget = measured p90 × a stated allowance (GPU 1.35, game 1.25),
plus 10% tolerance. **A regression tripwire, not an aspirational ceiling** —
"8K fidelity dies silently, one asset at a time."

**`nanite_triangles`, `texture_memory_mb` and `draw_calls` are still `null` and
UNMEASURED.** The CSV profiler captures five thread/GPU columns and nothing
else; those three need extra CSV categories or a `stat rhi` path that does not
exist. Declared unmeasured rather than guessed.

**Nothing is law until you flip `gates.ratified`.** `check_perf` prints every
comparison and then exits 3 — a declared FINDING — so the suite cannot report
green over a law nobody agreed to. The suite carries it with a **retire-on-
ratification** note, because a finding code left declared after its finding is
fixed excuses the next genuine breach.

## BUILT THIS PHASE

    recipes/perf_budgets.json    stations DERIVED (peak found as the heightmap
                                 argmax at world (100800, 208100), 3195 m from
                                 the plaza on bearing -12.8 deg)
    scripts/perf_flythrough.py   DRIVES measure_frame_cost per station rather
                                 than reimplementing it (non-negotiable 4a)
    scripts/check_perf.py        offline; --self-test proves 5 of 5 refusals

Suite: **18 checks, NO FAILURES**, 1 declared finding.

## THREE DEFECTS IN MY OWN TOOLING, ALL CAUGHT BY RUNNING IT

1. **The first flythrough reimplemented `measure_frame_cost`**, camera payload
   and all, before I noticed `--camera` already existed. Step (a) failing in
   miniature: the toolbox is ground truth, memory of it is a derived record.
2. **`argparse` ate a negative coordinate.** All four stations exited 2 on a
   usage error. This project recorded the rule — *use `--flag=value`* — on
   2026-08-17 and I walked straight into it.
3. **My wrapper captured stderr and never printed it**, so the reason was
   invisible and four stations reported a bare "exit 2". A wrapper that hides
   its child's error turns a one-line fix into a diagnosis.

## ⚠ STILL OPEN FROM GATE A

**`recipes/alpine_8k.json` declares NO rock scatter species — the list is
EMPTY.** Machinery proven, content absent. Logged, not fixed, per your ruling.

## NEXT, IN ORDER

1. **Your Gate E ratification** (or corrections to the numbers).
2. **⛔ C0 IS BLOCKED ON ONE ANSWER FROM YOU** — I have the five-step
   procedure, the donor fingerprint, and "keep original stone + floor", but
   **not your explicit role-mapping table**: which of the five staged textures
   binds to which of the ~10 `Material_001–009` slots. I can infer it; you asked
   me to say so rather than guess.
3. **C0**, then the second kit intake, then **Phase B loop on concept 01**.

## CARRIED

Kit verified in engine. `storey_m` 2.0 — **the placed town still stands at old
heights**; re-emission resolves it. Concept 01 is the right first loop subject,
not 02.

# CURRENT STATE — 2026-08-29b (concept pipeline: Phase 0 + A done, AT GATE A) — **SUPERSEDED by the 2026-08-29c block.**

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Tree clean. AN EDITOR IS RUNNING** on `/Game/Alpine8K`, rule-7 verified, idle.
**`M_GlobalRGB_Blend` is DIRTY in memory and must NOT be saved** — saving
rewrites bytes the kit manifest SHA-256'd. Restore points:
`pre-doc-consolidation-20260829`, `pre-storey-m-2.0-20260829`.

## ⛔ WAITING ON GATE A — where you check I read the images as you do

Deliverables, in the order made:

    _verify/20260829_concepts/READING.md   plain language, written FIRST
    recipes/scene_grammar.md               schema v1.0-concept
    recipes/concepts/alpine_village_0{1,2}.json  approach / interior
    _verify/20260829_concepts/GAP_REPORT.md  library coverage, 4 verdicts

## ⭐ THE FINDING THAT SHAPED THE SCHEMA: ONE PLACE, TWO CAMERAS

The concepts are the **same village** — same horn peak, same onion-dome church,
same stone-base/timber-upper vocabulary, same firewood. 01 is the approach
across a meadow; 02 is standing in the street.

So the schema separates **`site_id` (the PLACE)** from **`camera` (the VIEW)**,
and both share `site_id: alpine_village`. **Two views of one site are a
CROSS-CHECK, not a duplication:** build once, solve both cameras, and a wrong
village-to-peak relationship fails in one view while passing in the other — a
single view cannot detect it at all. Had each image become its own scene, the
pipeline would have built the village twice, incompatibly, each verifying
perfectly against its own image.

## MEASURED vs READ — kept apart

    MEASURED  warm light / cool shadow (01: R-B +0.133 vs -0.067, contrast
              5.5x); haze in 02, far saturation 0.145 -> near 0.252, so the
              far world keeps ~58% of near saturation
    READ      sun LOW and behind-left; one place two cameras; the vocabulary
    REFUSED   a sun AZIMUTH as a number

**The refusal is the honest part.** The image-space shadow bearing came back at
coherence **0.156 / 0.181** — near-isotropic, because the meadow's tussock
texture is as linear as the shadows. Evidence-free, and a *world* azimuth needs
the camera solve anyway, so `azimuth_unsolved: true` is legal. **The haze number
is the first tuning target this project's fog has had** — "applied and
rendering, never tuned" since 2026-08-06.

## ⛔ THREE REAL GAPS — the pack covers less and more than expected

**MORE than expected.** The intake crossed 15 modules; the pack holds **489
static meshes**, and `MODULAR_ASSETS` (96) + `Roofs` (10) map almost one-to-one
onto the concepts — `HBeam_*` (timber upper storey), `BoardWall`, `GableSet`,
`PorchBase`, `LanternPost`, `Outcrop*`, a bench, wheels. **Much of what I would
have called "needs authoring" is "intake again on a wider seed."**

**LESS than expected — the real gaps:**

1. **Onion-dome church — NEEDS GENERATION.** `church|dome|tower|spire|bell`
   across 489 meshes returns only `SM_OldBellows`. **Focal anchor of both
   concepts** and the right Phase D test: specific, non-modular, useless to buy.
2. **Wood stacks — NEEDS GENERATION, but I would NOT spend a generation slot.**
   Only `SM_PileOfChains` matched. Most repeated object in 02 and what makes the
   place read *inhabited* — but a woodpile is a lattice of cylinders, so it is
   the authored-module candidate, and a good forge test *because* beatable.
3. **Water — A SYSTEM, NOT AN ASSET.** Both concepts carry running water and
   **this project has never used water.** Its own brief, not a prop slot.

## ⚠ ONE SURPRISE THAT IS NOT A CONCEPT GAP

**`recipes/alpine_8k.json` declares NO rock scatter species — the list is
EMPTY.** `rock_scatter.py` is proven and `alpine.json` declares ten; the 8K
world inherited the machinery and none of the content. River stones and scree
are **not** "servable now" as I assumed — invisible had I answered from the
tooling instead of opening the recipe.

## OWED BEFORE PHASE B

1. **Your Gate A sign-off.**
2. **A second kit intake** on a wider seed (`MODULAR_ASSETS`, `Roofs`,
   `Construction_Pieces`) — one command; the closure walker exists.
3. **A ruling on rock species for the 8K world.**
4. **Concept 01 is the right first loop subject, not 02** — 02's delta would be
   dominated by the church and water, blocked on Phase D and on a nonexistent
   system. It is the right *second* subject.

## CARRIED

Kit verified in engine. `storey_m` 2.0 — **the placed town still stands at old
heights**; re-emission resolves it. Frame cost unmeasured. Phase E not started;
the warm editor makes a baseline cheap. **Phase C0 (donor-house texture swap) is
briefed and waiting on your `refs/textures_v1/`.**

# CURRENT STATE — 2026-08-29 (CLAUDE.md became an index; `storey_m` ruled to the kit's course) — **SUPERSEDED by the 2026-08-29b block.**

> **⭐ THIS IS THE ONLY `# CURRENT STATE` BLOCK, AND `scripts/check_docs.py`
> ENFORCES IT.** The 31 superseded blocks are in
> `docs/archive/current_state_history.md` — ⛔ history, and may not drive a
> decision. You no longer need to work out which block is newest.

**Tree clean. NO EDITOR IS RUNNING** — `bootstrap.py` found no nodes; all this
work was offline by design. Restore points:
**`pre-doc-consolidation-20260829`**, **`pre-storey-m-2.0-20260829`**. Every
phase is a separate commit, revertable alone.

## WHAT CHANGED

    CLAUDE.md      492,079 -> under 25,000, enforced   -95%
    CURRENT STATE  31 headings -> 1, enforced
    moved          6 pre-8K docs -> docs/archive/pre8k/, banner-marked
    extracted      3 LIVE doctrine files + THE AUDIT -- one hop, NOT dead
    TOCs           RECIPES 166, LESSONS 480 entries -- 0 deletions
    new checks     check_docs, gen_doc_tocs, verify_doc_conservation
    storey_m       3.2 -> 2.0 RULED; plan re-derived, world not re-placed
    kit            106 pkgs, 942.7 MB, 0 dangling refs (R-KIT)

**BYTE CONSERVATION PROVEN: `MISSING 0`.** `verify_doc_conservation.py` finds
every block and head section of the tagged `CLAUDE.md` verbatim, and classes 145
other `.md` UNCHANGED / EXTENDED / MOVED. **Three rewritten lines are DECLARED
each run.** `_verify/20260829_docs/`.

## SIX DEFECTS FOUND — IN MY OWN WORK AND THE REPO'S

1. **The 2026-08-28 session wrote no handoff** — for a day the newest heading
   described a world where the kit had not been found. Rebuilt post-hoc from
   disk, not from its commit narrative.
2. **`COVERAGE.md`'s storey ruling rested on a false premise** — it called
   `storey_m` 3.20 → 2.00 a 33% cut; the planner snaps a **continuous** falloff,
   so it re-quantises. **That unblocked the ruling.** Control: heights rebuilt
   from positions reproduced the shipped plan, 0 of 303 wrong.
3. **`landmark.spire_mesh` is INERT** — `city_place_payload.txt:77` hardcodes
   the same path, so nothing looks broken; change the recipe and the spire will
   not move. A **recurrence**. Annotated in `recipes/city.json`, with (4).
4. **Five gate booleans are decorative mirrors** — read by nothing, beside
   three that ARE read. Setting one false changes nothing.
5. **My own TOC generator was not idempotent and mis-tagged live doctrine** —
   it grew a newline per run, and its `[historic]` rule marked R0/R2/R4/R6/R8
   dead for *mentioning* the pre-8K world. Caught by testing, not reading.
6. **`check_plan_freshness --reproduce` compared RAW BYTES** and called a
   reproducing plan `DIFFERS` — CRLF vs LF. **Latent since the repo existed;
   any fresh clone hits it.** Fixed, controlled three ways. And it said "record
   why the artefact is kept" with nowhere to record it, so `_stamp_waiver` now
   exists, **proven to refuse four ways.**

**SIZE BUDGET.** `check_docs.py` caps this file at **25,000 chars** and it sits
close. The live block is the variable part — archiving this one and writing
yours, keep it under ~4 K or trim the index.

## OPEN, RANKED

1. **⚠ THE PLACED TOWN NOW DISAGREES WITH ITS PLAN, AND THAT IS EXPECTED.**
   `storey_m` was **RULED 3.2 → 2.0** and the plan regenerated: heights
   6/8/10/12 m (19/73/113/98), mean 9.99 → 9.91 m, snap error halved. **The 303
   buildings in the world still stand at 6.4/9.6/12.8** — placement needs an
   editor and the town is due to re-emit from the kit. `city_verify_payload`
   will report a mismatch until then; **that is correct, not a defect.**
2. **✅ THE KIT IS IN AND VERIFIED IN ENGINE.** 106 packages, 942.7 MB, 0
   dangling refs, hash-proven (R-KIT). Master **compiles with 0 errors**, 15 of
   15 bound to their own MI, **0 bound to a default**, and the pixels show
   plaster and timber. Frames in `_verify/20260829_kit/`. Nothing saved — the
   recompile dirties the master and saving it would break the manifest hashes;
   all 106 re-verified after, 0 mismatches. **Still open: FRAME COST**, and the
   non-uniform vendor data — two modules ship `_R` not `_MRF`, and
   **`Wall2x2MH` has NO NORMAL MAP.**
3. **`spire_mesh` and the five decorative gate flags** — in `BACKLOG.md`. The
   fix is in a payload that mutates the world, so it wants an editor.
4. **932 overlapping street pairs**, fixed when the network re-emits.
5. **PIE residency at mounted speed** — owed; the town encloses the spawn.
6. **Retire the sidecar's `_stamp_waiver`** — WAIVED, not re-verified, because
   `recipes/city.json` moved. Needs an editor.
7. Carried: **ambientCG licence rows** missing while those surfaces ship;
   **`save_foliage_actors.py`** folds into `save_tagged_actors.py`; **unit 10
   clause 2** waits on unit 12's pawn.

## LEFT LIVE-BUT-FLAGGED — your ruling, not mine

- **`plans/characters_brief.md`** — skeleton ruling partly superseded by
  MetaHuman; its 102-animation inventory is current. Split, archive, leave?
- **The three `plans/*_lanes/` dirs** (31 files) — indexed as historic, not
  quarantined: inputs whose outputs are live.

# CURRENT STATE — 2026-08-28 (the kit is REAL, and it is a COMPONENT kit) — **SUPERSEDED by the 2026-08-29 block.**

> **⭐ THIS IS THE ONLY `# CURRENT STATE` BLOCK IN THIS FILE, AND THAT IS NOW
> ENFORCED** by `scripts/check_docs.py`. The 30 superseded blocks that used to
> stack below it live in `docs/archive/current_state_history.md`, which is ⛔
> history and may not drive a decision. **You no longer need to check whether
> you are reading the newest block; there is only one.**

> **⚠ THIS BLOCK WAS WRITTEN POST-HOC ON 2026-08-29, AND SAYS SO BECAUSE THE
> GAP IS THE FINDING.** The 2026-08-28 session ended without one: commit
> `47f4ceab` touched `.gitignore`, `ASSETS.md`,
> `Free/_measured/kit_medievalvillage.json` and `_verify/20260828_kit/COVERAGE.md`
> — and **not this file** — so for a day the newest heading in `CLAUDE.md`
> described a world where the kit had not been found. **A session that reads
> the first block and trusts it would have re-run the search that already
> succeeded.** Reconstructed from that commit and **re-verified against disk**,
> not from its narrative: the vault cache directory exists, 15 probe meshes are
> in `LandscapeLab/Content/Kit/MedievalVillage/_probe/`, and the measurement
> JSON holds 15 rows with `error: null`.

**Tree clean. NO EDITOR IS RUNNING** — checked 2026-08-29 with `bootstrap.py`,
which found no nodes. The 27d block said one was; process state is the fastest
thing in a handoff to go stale. Restore point: `pre-plaza-clear-20260827`.

## ⭐ THE KIT IS FOUND — 22.6 GB, AND BOTH EARLIER FACTS WERE TRUE AT ONCE

    C:/ProgramData/Epic/EpicGamesLauncher/VaultCache/MedievalGame_5.3
      9,777 files   22.6 GB   9,685 uasset   pack built for UE 5.3

The OneDrive path that 27d spent a session on was the empty **project skeleton**
the launcher would have created FROM this cache — same folder names, zero files.
**Neither reading was wrong; they were about different artefacts**, and the
7,949-folder skeleton was a faithful inventory of a pack that was sitting in the
vault the whole time.

## ⛔ IT IS A COMPONENT KIT. THERE IS NOT ONE WHOLE HOUSE IN IT.

    Content/Meshes/Houses/       387 uasset
      MODULAR_ASSETS             259   Gable Porch Shingles VerticalPosts
                                       HorizontalBeams RoofConst01-03
                                       WindowShutter Outcrop Facade Forge
      Roofs                       56
      Thatch_Cards                61
      Construction_Pieces         10
      House1                       1   <- and it is SM_Plank_Base1, a PART

Confirmed twice by listings that share no source: the OneDrive skeleton's folder
NAMES, and the vault cache's actual ASSETS.

## ⭐ 15 MODULES MEASURED LIVE — `Free/_measured/kit_medievalvillage.json`

    walls    1.00 1.50 2.00 3.00 m wide, ALL 2.00 m tall, 0.16-0.22 thick
    corner   1.03 x 1.03 x 2.00
    doors    1.00 1.51 2.00 3.00 m wide, 2.00 m tall
    gables   4.82 x 2.18  and  4.30 x 2.76

Nanite **ALREADY ENABLED** on all 15, so "Nanite on unless a measured reason
says otherwise" needed no decision. One material slot each, 4–8 LODs, Nanite
tris 10.1k–19.7k.

**⚠ PIVOTS ARE BASE-CENTRED TO WITHIN 0.5 cm ON EVERY WALL AND DOOR — EXCEPT THE
TWO GABLES AT −27.8 AND −14.9 cm**, which is correct for a roof-end piece
seating at eaves height, and is a trap for anything assuming uniform pivots.

Both densities recorded: `fallback_tris_by_lod` is what draws with Nanite OFF,
`nanite_tris` is what actually draws. R-TREECOLLIDE was bitten once by reading a
Nanite fallback and calling it the source mesh.

**A 5.4 MB MESH-ONLY PROBE ANSWERED ALL OF THIS.** Bounds and triangle counts
are intrinsic to a mesh and unaffected by a missing material, so the ~800 MB of
textures for these 15 was not needed to decide anything. Nothing else crossed
over: no materials, no maps, no lights, no foliage, no config.

## THREE API NAMES CORRECTED AT THE STUB

`EditorStaticMeshLibrary.get_number_triangles` **does not exist** — it is
`StaticMesh.get_num_triangles`, and `measure_rock_meshes.py:149` was already
using the right one, so our own proven code contradicted the guess.
`get_num_nanite_triangles` / `get_num_nanite_vertices` are the Nanite-side pair.

## NOT DONE

- **Materials and textures have not been migrated.** Only 15 meshes crossed, as
  a measurement probe. ~800 MB remains for these alone.
- **No frame cost measured.** Arithmetic only: ~9 modules per house at ~12k
  Nanite tris ≈ 110k per house, ≈ 33M across 303. Nanite's territory, unmeasured.
- **The kit planner is unwritten**, and so is street re-emission.
- **932 overlapping street pairs** — unchanged.

## OPEN, RANKED

1. **⛔ RULING OWED — `buildings.storey_m` 3.20 against a 2.00 m wall course.**
   Every planned height is off-grid. Three readings in
   `_verify/20260828_kit/COVERAGE.md`; **none chosen.**
   **⚠ AND ITS PREMISE IS WRONG.** COVERAGE.md frames the fix as a 33% height
   cut; `plan_city.py:392-395` snaps a CONTINUOUS falloff, so it is not. Do not
   rule from COVERAGE.md until it is corrected.
2. **The kit intake proper** — materials, textures, an `ASSETS.md` licence row,
   and a frame-cost measurement before 303 buildings are re-emitted.
3. **932 overlapping street pairs**, fixed when the network is re-emitted.
4. **PIE residency at mounted speed** — owed; blocked by the town enclosing the
   spawn.
5. **The ambientCG licence rows** are missing and those surfaces ship.
6. **`save_foliage_actors.py` folds into `save_tagged_actors.py`** — the
   remaining half of the 4a promotion.
7. **Unit 10's second clause** stays untestable until unit 12's enemy pawn.
8. **49 streets unreachable, 11 buildings orphaned.** Declared, small.

---

# CURRENT STATE — 2026-08-27d (the kit path holds 7,949 folders and zero files — and it is a MODULAR WALL KIT) — **SUPERSEDED by the 2026-08-28 block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries THIRTY
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K`, verified against
`UE_PROJECT_ROOT`. Restore point: `pre-plaza-clear-20260827`.

## ⛔⛔ THE KIT PATH EXISTS, HOLDS 7,949 DIRECTORIES AND NOT ONE FILE

    C:\Users\Admin\OneDrive\Documents\Unreal Projects\MedievalVillageMegascansS
      directories  7,949
      files             0     not one, not even the .uproject
      created      2026-08-10 17:20 — EIGHTEEN DAYS AGO, not tonight

**It is NOT the OneDrive placeholder hazard**, and the control that settles that
is the sibling: **`ProjectTitan` sits in the SAME reparse-pointed folder with
3,086 files.** Hydration works there. Nor is it disk — 193 GB free. Nor is it
placeholder invisibility: `Get-ChildItem -Force` sees zero file entries, and the
offline/recall attribute count is zero *because there are no file entries to
carry it*.

**Nothing anywhere on this machine was created or modified in the last 14
hours**, and only four `.uproject` files exist, the newest from 2026-08-10. So
the "Create Project" run produced nothing on disk at any location.

## ⭐ BUT THE DIRECTORY NAMES ARE AN INVENTORY, AND THEY CHANGE RULING 1

7,949 folder names survive with no files, and they are unmistakably the right
pack — `Content/Maps/DataLayers/MedievalVillage_P_WP`,
`Content/Megascans/3D_Assets/Medieval*`. 129 `3D_Assets` entries; the
architectural ones are:

    walls    MedievalModularWall  1x2MA 1x2MB 15x2M 2x2MD 2x2MG 2x2MH 3x2M
    corner   MedievalModularCornerWall1x2M
    doors    MedievalModularDoor  1x2M 15x2M 2x2MA 2x2MB 3x2M
    gables   MedievalModularGable4, MedievalModularGable4M

**THIS IS A MODULAR WALL KIT, NOT A SET OF HOUSE MESHES.** The naming reads as
`<width>x<height>M`: 2 m tall modules in 1, 1.5, 2 and 3 m widths.

**That makes the coverage gate as specified the wrong instrument.** It compares
whole-building meshes against 303 footprints at ±20%; a modular kit has no
building meshes and a footprint is BUILT to size rather than matched. On the
recipe's own numbers — footprints 7.03–14.95 m — 1 m and 1.5 m modules tile any
length to within 0.5 m, so footprint coverage would be near-total by
construction. **The real question moves to height: 2 m modules against the
recipe's 3.2 m `storey_m`.**

**⚠ STATED AS WHAT IT IS:** read from DIRECTORY NAMES in a file-less skeleton.
Evidence about what the pack contains; **NOT measured geometry**. No dimension
here has been verified against a mesh. The coverage gate is UNRUN and the
planner work is untouched.

## ⭐ THE PLAYER NO LONGER SPAWNS FACING A TRUNK

    dry run    16 instances inside the disc
               Norway spruce 5 · Scots pine 3 · spruce_half 4 · spruce_small 4
    committed  removed 16 · mismatches [] · still_inside_after 0
    on disk    exactly ONE package changed — all four components live in the
               single foliage actor covering the plaza

The conifer 3–4 m in front of the PlayerStart was never a candidate: the clear
tests against BUILDINGS, STREETS and the LANDMARK, and the plaza is defined as
ground with no structures on it.

**A DISC IS RIGHT HERE AND THE RECIPE SAYS THE OPPOSITE.** Its warning — *"IT
FOLLOWS THE TOWN'S SHAPE, NOT A RADIUS"* — is about the town EXTENT, where a
circle drew a bald ring the terrain had no part in. It does not transfer:
**the plaza IS a declared circle.** Both readings now sit side by side in the
recipe.

**The margin is added to the plan's own radius, never re-declared** — which
required `plan_city` to emit `plaza_radius_cm`, a value it already used and did
not record. The payload REFUSES if the plan lacks it rather than assuming one.
Plan regenerated: that key added, **every other key IDENTICAL**, so nothing was
re-placed.

## ⭐ VERIFIED BY TRACE, NOT BY RENDER

`scripts/spawn_cone_payload.txt` — 61 rays, ±45°, 30 m, at eye height, on the
PlayerStart's own yaw:

    CLEAR            48 of 61
    blocked          13, ALL the same actor
    that actor       City_Landmark — confirmed by label and tags, not inferred
    nearest block    25.5 m  (the tower's near face; centre at 29.2 m)
    FOLIAGE HITS     ZERO

The only thing in the forward cone is the landmark the spawn is aimed at by
design. **25 s, against ~840 s plus a ~630 s wedge for a render**, and re-runnable
after any foliage change.

Controls: margin 0.0 removes nothing (the shipped clear is idempotent);
landscape hits are counted separately so rising terrain cannot inflate the
blocked count; it refuses unless there is exactly ONE PlayerStart.

## VERIFIED THIS SESSION

    live actors      city 1446 · encounters 317 · total 3266
    disk             3266 external actor packages — EXACT MATCH, no orphans
    foreign suns     3 found, all affects_world False; STILL AFFECTING: 0
    plan freshness   all 19 checkable plans fresh
    offline suite    13 checks, NO FAILURES

## NOT DONE

- **The whole kit unit** — intake, measurement, coverage gate, kit planner,
  street re-emission, corner-gap re-measure. All blocked on files that do not
  exist.
- **No renders this session, deliberately.** R-CITYSHOT's rule is measurements
  first and renders last; with the kit blocked there were no kit buildings to
  photograph, and a render would have cost the editor's remote-exec channel for
  ~630 s for nothing. The eye-level plaza frame from 27c stands and its
  buildings are still near-black.
- **932 overlapping street pairs** — unchanged, fixed when the network is
  re-emitted.

## OPEN, RANKED

1. **⛔ GET THE KIT'S FILES ONTO DISK.** The folder skeleton is real and correct;
   the payload never arrived. Worth checking, in order: whether the cloud copy
   itself has files (open the OneDrive web view — if it is folders-only, the
   original creation never completed); "Always keep on this device" on that
   folder; and failing both, re-create the project **outside OneDrive**. A UE
   project inside a synced folder is a hazard regardless — 20 GB of packages
   round-tripping to the cloud, with Files On-Demand able to dehydrate a
   `.uasset` under the editor.
2. **RULING OWED — the kit is MODULAR, so what does "coverage" mean?** The
   ±20% mesh-fit gate does not apply to wall segments. Two candidate readings:
   footprint coverage is near-total by tiling, and the binding constraint is
   the 2 m module height against `storey_m` 3.2. **Nothing was decided.**
3. **932 overlapping street pairs.**
4. **PIE residency at mounted speed** — owed; blocked by the town enclosing the
   spawn.
5. **The ambientCG licence rows** are missing and those surfaces ship.
6. **`save_foliage_actors.py` folds into `save_tagged_actors.py`** — the
   remaining half of the 4a promotion. It was used again this session.
7. **Unit 10's second clause** stays untestable until unit 12's enemy pawn.
8. **49 streets unreachable, 11 buildings orphaned.** Declared, small.
9. Everything in the 2026-08-22 groom block below is untouched.

---
# CURRENT STATE — 2026-08-27c (the kit is still not here; the slabs are proven by picture) — **SUPERSEDED by the 2026-08-27d block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-NINE
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (PID 26492) but is
**WEDGED** — see below. Nothing is in flight. No restore point was needed this
session; nothing destructive ran.

## ⛔⛔ THE QUIXEL MEDIEVAL VILLAGE SAMPLE IS STILL NOT IN THE PROJECT

The operator reported adding it via the launcher. **Four independent
representations say it did not land**, and none of them is the asset registry
alone:

    1  asset registry     414 static meshes; THREE architecture-like names, all
                          pre-existing (2 FabEval scratch, 1 engine stair).
                          No MedievalVillage folder. /Game/Fab holds 1 mesh:
                          a tree branch.
    2  filesystem         newest dir under Content is Scratch, 2026-08-25.
                          Nothing new since 2026-08-26 but Content itself.
    3  machine-wide       NO Medieval/Village folder anywhere under Documents,
                          Downloads, Program Files\Epic Games, Dev or
                          AppData\Local. Also checked the two OTHER .uproject
                          files on this box (`LandscapeLab 5.8`, `MyProject`)
                          in case the launcher targeted the wrong project --
                          both untouched since 2026-08-10.
    4  the launcher's own log   its `get-installed-apps-response` enumerates
                          exactly THREE products: UE_5.8 installed,
                          **FabPlugin_5.8 isInstalled FALSE**, and
                          **QuixelBridge_5.8 isInstalled FALSE**. Snapshot
                          taken 2026-08-27 16:44, this evening.

**⭐ AND THAT LAST ROW IS PROBABLY THE REASON.** Neither the Fab launcher plugin
nor Quixel Bridge is installed, so the launcher-side "add to project" route for
a Megascans sample has no delivery mechanism on this machine.

**THE IN-EDITOR ROUTE IS AVAILABLE AND IS THE RECOMMENDATION.** Read from the
LIVE editor (non-negotiable 17, not from `.uproject`): 347 plugins enabled,
including **`Fab`** and **`Bridge`**. So the pack can be browsed and added from
inside the running editor's Fab panel without installing anything in the
launcher.

**RULINGS 1 AND 2 REMAIN BLOCKED.** Nothing was built against a guessed kit —
the coverage gate exists to show the operator a number before the town
re-forms, and inventing the input to that decision would defeat it.

## ⭐ THE PROOF OWED FROM 27b IS DELIVERED: THE SLABS ARE SEATED, BY PICTURE

`_verify/20260827_kit/PLAZA_eyelevel.png` + `PLAZA_slab_edge_crop.png` +
`WHAT_THE_RENDER_SHOWS.md`. The slabs lie flat on the grass and TILT WITH THE
GROUND; **no daylight under the edges**, grass overlapping the margins. That
closes a fix that had been established by measurement only (corner gap
p50 67.9 → 10.9 cm).

**The nav wireframes are gone** — `ShowFlag.Volumes 0` works and every future
editor render of this world needs it.

## ⛔ AND THE SAME FRAME MAKES THREE DEFECTS PLAIN

1. **The 932 overlapping street pairs are VISIBLE.** Consecutive slabs meet at a
   lip: each is tilted to its own local ground plane and adjacent planes differ.
   **Seating each slab correctly is exactly what makes the joins wrong.** The
   fix is emitting the network as a continuous surface with shared edge heights,
   which belongs with the kit re-plan.
2. **The buildings are NOT materialed.** Asked directly: no. Engine `Cube`
   default, near-black at eye level exactly as at range. The kit answers it.
3. **A conifer stands ~3–4 m directly in front of the PlayerStart.** Press Play
   and the first thing you see is a trunk. **This is not a bug in the tree
   clear** — the clear works on structure footprints and the plaza is defined as
   ground with no structures, so nothing there was ever a candidate.
   **Re-running against kit footprints will NOT fix it.** The plaza needs its
   own clear radius.

## ⛔ A REPRODUCIBLE CAPTURE FAULT: HighResShot WEDGES THIS EDITOR

Both renders this session, and the one last session, ended the same way: the
frame completes, then the editor drops to **0.01–0.02 CPU-seconds per
wall-second** with `Responding=False` and **no modal** — every visible window
enumerated all three times, finding only `UnrealWindow` and the console. Remote
execution stops answering.

It is not a stall in the render: the frames landed. **It recovers on its own
after 630 SECONDS**, measured this session by polling until remote execution
answered. An earlier draft said "after some hours", inferred from one PID being
healthy at the start of a later session — that is an interval containing the
recovery, not a measurement of it. **10.5 minutes is the number**, and it turns
the fault from a session-ender into a wait.

**CPU per wall-second is the discriminator, not responsiveness.** Today the same
`Responding=False` has meant 6.04 (working, delivered its frame 841 s in), 1.02
(busy, answered next try) and 0.01–0.02 (wedged).

**Consequence: the post-render editor checks this session could not run.** The
live actor census and the foreign-sun re-check are OWED, not done. They are
listed below rather than assumed.

## VERIFIED THIS SESSION

    offline suite        13 checks, NO FAILURES
    disk package census  3266 external actor packages under Alpine8K, matching
                         the 3266 live actors counted in 27b -- NO ORPHANS
    Fab plugin state     read from the LIVE editor, not .uproject
    ground under camera  traced before the ad-hoc shot: 18671.8 cm at the
                         PlayerStart, so the camera was correctly sited

## NOT DONE, NOT VERIFIED

- **The whole kit unit.** Blocked, above.
- ~~**Live actor census and the foreign-sun gate re-check**~~ **BOTH DONE.** The
  editor recovered **630 seconds** after the wedge -- a measured number, not the
  "some hours" the first write-up guessed -- and both carry-over checks then ran
  clean:

        live actors   city 1446 · encounters 317 · total 3266
        disk          3266 external actor packages   EXACT MATCH, no orphans
        foreign suns  3 found, all affects_world=False and atmosphere_sun=False
                      FOREIGN LIGHTS STILL AFFECTING THE WORLD: 0
- **The eye-level frame is a GREYBOX town**, not kit buildings. It answers the
  seated-slab question and the materials question; it cannot answer anything
  about a kit that is not here.

## OPEN, RANKED

1. **⛔ ADD THE PACK FROM INSIDE THE EDITOR.** The `Fab` plugin is enabled in
   the running editor; the launcher-side Fab plugin and Quixel Bridge are NOT
   installed, which is very likely why the launcher route produced nothing. This
   is the single blocker on rulings 1 and 2, and those are the biggest gap in
   the project.
2. **A conifer in front of the spawn.** Cheap, visible, and independent of the
   kit: give the plaza its own foliage clear radius.
3. **932 overlapping street pairs**, now seen as well as counted. Fix by
   emitting the network as a continuous surface when it is re-planned.
4. **The wedge-after-capture fault.** Every render currently costs the editor's
   remote-exec channel for an unknown period. Worth a bounded investigation
   before the next render-heavy session.
5. **PIE residency at mounted speed** — still owed, still blocked by the town
   enclosing the spawn (0 of 360 bearings clear to 1200 m).
6. **The ambientCG licence rows** are missing and those surfaces ship.
7. **`save_foliage_actors.py` folds into `save_tagged_actors.py`** — the
   remaining half of the 4a promotion.
8. **Unit 10's second clause** stays untestable until unit 12's enemy pawn.
9. **49 streets unreachable, 11 buildings orphaned.** Declared, small.
10. Everything in the 2026-08-22 groom block below is untouched.

---
# CURRENT STATE — 2026-08-27b (four suns, 1,447 orphan packages, and the streets sit down) — **SUPERSEDED by the 2026-08-27c block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-EIGHT
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K`, verified against
`UE_PROJECT_ROOT`. Restore points: `pre-second-sun-fix-20260827`,
`pre-encounter-place-20260827`, `pre-hero-dedupe-20260827`,
`pre-street-seat-20260827`, `pre-street-reseat-20260827`.

## ⛔⛔ THE HEADLINE IS TWO SILENT FAULTS, AND EITHER WOULD HAVE POISONED THE NEXT SESSION

**1. THERE WERE FOUR SUNS.** Not two.

    label                    lux      K     pitch   yaw    atmos_sun idx prio
    Lighting_alpine_8k_Sun  130000  7800    -12.0  -75.0     True     0   0
    HeroStage_Key            25000  6500    -22.0 -120.0     True     0   0
    HeroStage_Fill            7500  6500     -8.0  -45.0     True     0   0
    HeroStage_Rim            11250  6500     -5.0   90.0     True     0   0

All four claimed atmosphere sun index 0 at priority 0 — **43,750 foreign lux
from three directions at a different colour temperature, 33.7% on top of the
declaration.** They are R-HEROCAP's flat-lit face rig, built in the game world
instead of a scratch level and swept in by the city save (`84b992ba`,
2026-08-24). **Every render proof taken since then was under an undefined sun**,
including unit 11's Rock/Grass separation render.

Disabled via `affects_world` (not deleted — that would leave a half-removed
rig), identified by AGREEMENT WITH THE RECIPE, and the gate proven to refuse
in both directions before it acted.

**2. 1,447 PACKAGES WERE ABOUT TO DOUBLE THE TOWN.**

    packages on disk   4713          actors in world   3266
    after save_level    3266                            3266

Destroying an actor leaves its package. A cold boot would have loaded 4,713
actors and drawn the city and every encounter marker **twice**.
`get_dirty_content_packages()` returned **0** throughout — it does not report
packages pending DELETION. `save_level.py` was the only instrument that saw
them, and named all 1,447.

## ⭐ 317 ENCOUNTERS ARE PLACED. THE POI TRIPWIRE IS DISCHARGED.

    placed 317   counted_in_world 317   scavenger 210 · raider_camp 81 · beast 26
    filesystem   317 external actor packages written

The negative control still refuses: handed the RAW plan, the placer declines
because it carries no `_adopted_by`/`_verified_against`.

**AND THE PLACER REPORTED `ok:true` OVER NOTHING ON DISK** — the fourth instance
of the not-dirty class, which is why `scripts/save_tagged_actors.py` now exists
(non-negotiable 4a). It selects by TAG or CLASS, `set_dirty_flag` +
`save_loaded_assets(..., only_if_is_dirty=False)`, and **takes its verdict from
`git status`, not from the editor's reply** — refusing if the editor says saved
and no file moved. Proven to refuse on an empty selection and on a wrong
`--expect`. Declared debt: `save_foliage_actors.py` is the earlier
single-purpose copy and is not yet folded in.

## ⭐ UNIT 10'S FIRST CLAUSE PASSES

    steps 14 · marker-observations 14 · markers WITHOUT nav 0 · floor 8

`verify_marker_streaming.py`. The source is TELEPORTED between placed markers,
which is stricter than mounted speed — World Partition gets less warning.

**Its first two runs were not passes though one said PASS.** v1 flew between the
cloud's corners at 838 m up and reported PASS with ONE marker resident;
streaming is distance-based in 3D. **Then the floor I added to catch that was
also wrong** — it gated on peak CONCURRENCY and called a clean run INCONCLUSIVE
at 1, but markers are ~460 m apart and one at a time is correct. Power
accumulates in (marker, step) PAIRS.

**DECLARED:** unit 10's second clause — *spawning must refuse when navmesh
projection fails* — is NOT testable. The director spawns nothing until unit 12.

## ⭐ THE STREETS SIT ON THE GROUND

    over all 838 streets    centre gap        worst corner gap
    before                  p50   0.3 cm      p50 67.9  p90 141.5  max 442.0
    after                   p50  -0.0 cm      p50 10.9  p90  55.9  max 185.9
    corners over 50 cm      558  ->  107

The operator's screenshot and the verifier's `max 0.0 cm` were both right: **a
centre trace cannot see a flat slab lifting at its ends.** `plan_city.street_seat()`
fits a plane through the four corners; ONE helper, both branches.

**THE ROTATION CONVENTION WAS MEASURED, NOT REASONED** — all four sign
combinations applied to the placed actors and re-traced:

    p+ r-  p50  10.9   <- adopted     p+ r+  p50  60.0
    p- r-  p50  85.6                  p- r+  p50 130.6     flat  p50 67.9

**Roll is negated at the ENGINE BOUNDARY, not in the plan**: the plan stores the
ground plane (a physical fact), the placer speaks UE's left-handed convention.

**And my first instrument could not have seen the fix** — it computed corner
heights from the plan's centre Z, a quantity invariant under rotating the slab,
and returned byte-identical numbers before and after.

## ⛔ RULING 2 IS BLOCKED ON ONE CLICK, AND I STOPPED RATHER THAN WORK AROUND IT

**The Quixel "Medieval Village Megascans Sample" is NOT in the project.**
Measured, not assumed: `/Game/Fab` holds **one** static mesh and it is a tree
branch. `/Game/Fab/Megascans` carries surfaces and nothing architectural. Not
downloaded anywhere on disk; `%LOCALAPPDATA%\FabPlugins` holds only settings.

**Fab is not drivable from Python** (the only `fab` names in the stub are FABRIK
rig units), so this needs the operator to add it via the launcher / Fab plugin.
Per the brief: said, and stopped.

**Consequently RULING 1 (kit-driven planner) is also blocked** — its coverage
gate needs kit dimensions that do not exist yet. Nothing was built against a
guessed kit.

**For scale, the one house we DO have** (`SM_medieval_house_10`, free sample,
measured live at 8.3 × 7.5 × 8.5 m) covers **29 of 303 buildings at ±20%**,
70 at ±35%, 93 at ±50%; worst building needs +100% stretch on one axis. Its
licence is **NOT RECORDED** and it stays evaluation-only.

## ⭐ RULINGS 3, 5, 6, 7 LANDED

- **3 — `CREDITS.md` exists**, discharging Blenderust's CC BY 4.0 into a file
  that can ship. **And writing it found a worse gap: I asserted the ambientCG
  surfaces were CC0 from memory.** No record in `ASSETS.md`, no licence file on
  disk. Corrected in place — those five are load-bearing in the shipped
  landscape material, so that gap outranks the evaluation-only rows.
- **5 — prose keys PERMITTED in planner recipes**, schema.md v1.6, enforced by
  `check_prose_keys.py`. **Its first run proved my own rule wrong twice**: three
  "violations" were recorded measurements inside documentation blocks, and the
  fourth was a WRITE misread as a read. Rule 1 turns out not to be
  machine-checkable at all.
- **6 — `max_orphan_building_fraction` RATIFIED at 0.05**, kept struck in
  RECIPES so that it was chosen post-hoc stays visible.
- **7 — the duplicate `HeroInWorld` is gone**, identified by property signature
  (same class, location to 0.01 cm, yaw, and the same two mesh objects). Its
  package could not be moved to `_trash/` — the editor held it open — and went
  out with the 1,447 deletions instead; `_trash/hero_duplicate_20260827/` keeps
  the hash and the account.

## ⚠ THE RENDER: ONE FRAME OBTAINED, ONE SKIPPED

`_verify/20260827_kit/CITY_oblique_seated.png` + `WHAT_THE_RENDER_SHOWS.md`.
**The town reads as a town** — gabled roofs, a spire, clustered in a clearing.
**The buildings are near-black** (engine Cube default material, answered by the
kit and not by the sun). **Trees still stand among the houses.** **Orange
wireframes across the sky are the 72 nav volumes drawing in the viewport** —
`ShowFlag.Volumes 0` clears it and every future editor render needs it.

**The eye-level plaza shot was NOT obtained.** The editor went to **0.01 CPU-s
per wall-second** with no modal (every window enumerated). That is a genuine
stall, and the distinction is the day's lesson: the same `Responding=False` came
earlier with **6.04** and **1.02** CPU-s per wall-second while the editor was
working and delivered late. **CPU is the discriminator, not responsiveness.**

## MEASURED AND NOT FIXED

- **932 overlapping street pairs.** The plaza z-fighting is real and is a
  PLANNER property — ring and spoke segments overlap where they meet. Belongs
  with the kit re-plan that will re-emit the network.
- **The 3 recorded measurements inside prose blocks** are listed by
  `check_prose_keys.py` every run, deliberately.

## VERIFIED THIS SESSION

    city verify        ok true · 1446 by kind · mismatch {} · grounding max 0.0 cm
    plan reproduces    13ad8ee53319ffac across three runs
    plan freshness     all 19 checkable plans fresh
    offline suite      11 checks, NO FAILURES
    prose rule         holds; self-test passes 4 of 4

## OPEN, RANKED

1. **⛔ ADD THE QUIXEL MEDIEVAL VILLAGE SAMPLE TO THE PROJECT.** One click in
   the launcher / Fab plugin. It blocks rulings 1 and 2 entirely, and those are
   the biggest remaining gap: 36.5 km² of walkable ground and a town of engine
   primitives.
2. **The eye-level plaza render.** Needs an editor that is not stalled. It is
   the frame that would show the seated street slabs, which are currently
   proven by measurement alone.
3. **932 overlapping street pairs**, to be fixed when the network is re-emitted.
4. **PIE residency at mounted speed** — still owed, and still blocked by the
   town enclosing the spawn (0 of 360 bearings clear to 1200 m). Needs a start
   outside the settlement.
5. **The ambientCG licence rows** are missing and those surfaces ship.
6. **`save_foliage_actors.py` folds into `save_tagged_actors.py`** — the
   remaining half of the 4a promotion.
7. **Unit 10's second clause** waits on unit 12's enemy pawn.
8. **49 streets unreachable, 11 buildings orphaned.** Declared, small.
9. Everything in the 2026-08-22 groom block below is untouched.

---
# CURRENT STATE — 2026-08-27 (the basin opens, the world becomes walkable) — **SUPERSEDED by the 2026-08-27b block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-SEVEN
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K`, verified against
`UE_PROJECT_ROOT` this session. Autonomous run under full delegated authority.
Restore points: `pre-reachability-reauthor-20260827`,
`pre-foliage-replan-20260827`, `pre-plan-stamp-20260826`.

## ⭐⭐ THE WORLD IS WALKABLE: 1.5 km2 -> 36.5 km2, AND 317 ENCOUNTERS STAND IN IT

Full navmesh coverage. 72 volumes from ONE recipe declaration, 64 chunk actors.

    region lattice, 60 m, grid BFS from the spawn
    cells        18,496 over 66.06 km2
    projecting   15,573  (84.2%)
    REACHABLE    10,146  (54.9%)  = 36.53 km2

    relay sweep, 12 bearings     before      after
    furthest                     1050 m     2540 m
    median                        600 m     1260 m

Of 49.27 km2 of walkable terrain, 36.53 is connected to the player. The rest is
walkable ground not in the player's component — ledges above cliffs, isolated
shelves — a TERRAIN boundary, which is honest. Yesterday the boundary was an
artefact of where a volume happened to stop.

**The ruling was fable's, under the operator's standing delegation**, and it
found the decision had already been taken: `PHASE2_PLAN:250` says the other 63
chunks are "a decision, not a plan", and unit 8 ruled the navigable region is
authored, versioned recipe data. `scripts/plan_navmesh_tiles.py` is that
derivation.

    volumes    nav MB    wall s    peak GB    chunk actors
       2        35.18      36.0      20.0        10
       3        48.14      42.0      20.4        12
       9       116.01      46.0      20.6        16
      72       756.58     110.0      22.2        64

**Calibrated before committing to it.** The 2-volume figures came from the two
least representative tiles — basin-flat and tree-CLEARED. One full-density
forest tile (6,782 trees) was built first: +12.96 MB, +6 s, +0.4 GB, and
**+0.76 km2 of reachable ground from a 1.08 km2 tile.** Predictions from the
9-volume point held: ~830 MB predicted / 756.58 actual, bars 2.5 GB, 30 min,
90 GB, all cleared with room.

**THE BUILDER IS NOT INCREMENTAL** — 13 packages created, 10 DELETED. Per-tile
cost is not additive across runs; batching bounds RISK, not peak memory.

**Two independent tile-count calculations agreed:** the recipe's budget check
says 388,622, the engine's own warning says 401,843 — 3.4% apart, 38% of the
1,048,576 hard limit.

**Residency measured BEFORE it could become a problem**
(`_verify/20260827_navcalib/RESIDENCY.md`): editor holding every region, all 64
chunks, 219,659 trees — working set 14.65 GB, RAM free 6.12 of 31.43, commit
37.01 of 223.43. **It fits.** Stated as an editor UPPER BOUND, not a shipping
number; no PIE reading was taken and unit 10 is still owed.

## ⭐ ENCOUNTERS: 320 PLANNED, 317 VERIFIED, NONE PLACED

    available   109,307 of 256,027 cells (42.69%) = 27.87 km2 -> target 320
    placed      320   scavenger 210, raider_camp 82, highland_beast 28
    VERIFIED    317 reachable; the adopted set re-verifies ALL 317

**⛔ AND THE VERIFIER REFUSED TWICE, THE SECOND TIME INSTRUCTIVELY.** At the
shipped 60 m proximity radius 7 of 440 projected but were unreachable;
tightening to 30 m gave 3 of 320 — and one survivor sits **8.1 m from a
reachable lattice cell**. That is not a resolution problem: they are genuine
small pockets across a gap the agent will not cross, and no radius separates
them without discarding most of the region.

**So the navmesh's verdict feeds FORWARD rather than the prefilter guessing
harder.** `adopt_verified_encounters.py`, non-negotiable 20's pattern:

    encounters/alpine_8k_all.json        THE PLAN, byte-reproducible, untouched
    encounters/alpine_8k_verified.json   THE ADOPTED SET, stamped against BOTH
                                         its sources

Editing the plan in place would break the reproducibility
`check_plan_freshness --reproduce` exists to test. **A placer reads the verified
file.**

**NOTHING WAS PLACED** — generation is mine, placement of wilderness content
stays behind the operator's POI tripwire (`WORLD_VISION` item 4).

## ⭐ THE STAMPS CAUGHT A CROSS-CUTTING CHANGE, WHICH IS WHAT THEY ARE FOR

Adding 72 volumes to `recipes/alpine_8k.json` moved an input of the town plan,
four foliage plans and the lattice. Every one reported **STAMP DIFFERS** naming
that file. All were regenerated and compared field by field against a backup:

    CONTENT THAT MOVED: NOTHING. Only the stamps.

303 buildings, 838 streets, 219,659 trees — byte-identical.

**And `reachability.py`'s binding check caught real staleness the same day:** the
new region lattice was measured at 64 chunk actors and the town sidecar at 10,
and the module REFUSED to merge two navmesh builds. The town sidecar was
re-measured; both now describe the same build.

    All 19 checkable plans are fresh.   Suite: NO FAILURES across 8 checks.

## ⛔⛔ THE HEADLINE IS A RETRACTION: THE BASIN WAS NEVER SEALED

**The barrier was the PATH QUERY, not the world.** `get_path_length` has a
finite search budget and returns FAIL when it exhausts it, which from one call
is indistinguishable from ground you cannot walk to.

    plaza  -> 520 m    FAIL      (and it reports a partial length, 424 m)
    350 m  -> 520 m    SUCCESS   189 m
    plaza  -> 350 m    SUCCESS   373 m

The walk is the second leg after the first. **A NEGATIVE RESULT FROM A SEARCH IS
A STATEMENT ABOUT THE SEARCH.**

**It was believed because it REPRODUCED** — across sampling intervals, 24
bearings and two navmesh builds. Consistency is what a budget produces, because
the answer was a property of the query. Six measurements already pointed at it
and each was explained away; the loudest was the uniform 24-bearing profile,
which I read as evidence of a uniform WALL. **A roughly circular limit centred
on the query START is the shape a budget makes, not the shape terrain makes.**

**The operator had already ruled CUT THE RAMP on this finding. It is moot and no
terrain was touched.**

## ⭐ THE TOWN, RE-MEASURED BY TRANSITIVE CLOSURE

    method      seed from the PlayerStart, then grow by RELAY from the nearest
                already-reachable row, to a FIXED POINT
    rounds      2   gained 887, +188, 0   CONVERGED
    streets     789 of 838   (was 653)
    buildings   303 of 303   (was 253)   ZERO unreachable

**EVERY BUILDING IN THE TOWN IS REACHABLE.** 789 is corroborated by a second
route sharing no code: relaying each unreachable row off its nearest neighbour
recovered 136 of 185, and 653 + 136 = 789.

## ⭐ SUPERSEDED — UNIT 9 AT SIX ENCOUNTERS, kept as the record of the first pass (now 317, see above)

    available   6191 of 8646 cells (71.61%) = 1.5490 km2 -> target 6
    placed      6 scavenger, 3 rejected in_settlement
    VERIFIED    total 6, failed_projection 0, unreachable 0, controls_ok
                ALL 6 ENCOUNTERS REACHABLE

**The missing piece was the SAMPLE, not the world.** The sidecar's rows are all
INSIDE the settlement, so "outside the settlement AND near reachable ground" was
unsatisfiable by construction — and I had written that zero up as a fact about
the basin, with a `WORLD_VISION` citation explaining why it was desirable. **A
satisfying explanation for a measurement is not evidence the measurement is
right.**

`city_reachable_lattice_payload.txt` — grid BFS over the whole built navmesh,
every query between ADJACENT cells so none approaches the budget:

    cells 1431 at 40 m over 2.163 km2   projecting 1423   REACHABLE 1261
    path queries 1557

The encounter area was widened to the UNION of both nav volumes, bounds READ
from the world recipe and contiguity ASSERTED (shared edge x=-158400, identical
y extents).

## ⭐ SUPERSEDED — THE PLAYABLE WORLD WAS BOUNDED BY NAVMESH. It is not any more: full coverage was built the same day. Kept because it is the measurement that motivated the build.

Corrected relay sweep, 12 bearings to 1500 m:

    furthest 1050 m   median 600 m   min 350 m

and almost every ray stops **exactly on a NavBounds volume edge** — bearing 0 at
x −1598 against an east edge of −1588; bearing 90 at y 3308 against a north edge
of 3308; bearing 150 at x −2628 against a west edge of −2628.

**That is the live constraint and it is fixable by building more volume.**
R-NAVBUILD costs ~36 s and ~20 GB peak per 1040 m volume.

## ⭐ EVERY PLAN IN THE REPO IS STAMPED — 19 OF 19

`scripts/plan_stamp.py` holds `INPUT_KEYS` once; `plan_city`, `plan_encounters`,
`place_foliage` and `rock_scatter` all stamp from it, and
`check_plan_freshness` reads it. `scripts/stamp_plan.py` covers artefacts made
by in-editor payloads.

**The re-plan is proven to have moved nothing:** all 15 foliage plans compared
field-by-field against a backup — instances IDENTICAL 15 of 15, 390,728
instances total, no other value moved. The placed worlds are untouched.

**`stamp_plan` REFUSES to invent provenance.** An artefact declaring no inputs
is skipped, never given a guessed one — a stamp asserting inputs nobody measured
verifies clean and is worse than none.

## ⛔ FIVE INSTRUMENT DEFECTS FOUND TODAY — read before trusting a nav number

1. **A "ground" trace that excludes only foliage measures the ROOF.** 17 streets
   traced 12.9 m high onto buildings. Exclude `LandscapeLab.City` too.
2. **A single query from a fixed anchor is not a reachability test.** Relay.
3. **A verifier can inherit the defect it verifies** — the encounter verifier
   said all 6 unreachable using the same single query.
4. **A relay path length is only the last leg**, so it is short by construction;
   `path_len_m` read 15–60 m for encounters outside a 940 m town. Every row now
   records which leg answered.
5. **The offline slope model was wrong twice, both permissive** — per-axis
   (understates by up to √2) and `np.gradient`'s central differences (halves a
   one-cell step). Use forward differences per QUAD, gradient MAGNITUDE.

## ⭐ UNIT 10, FIRST HALF: THE MARKER AND DIRECTOR EXIST — AND THE AUDIT MADE THEM HONEST

`AEncounterMarker` + `UEncounterDirectorSubsystem`. Built clean first try in
16.4 s; verified on a **COLD BOOT**, not from the `.uplugin`.

    EncounterMarker      reflected, CDO reachable, 7 of 7 properties read back
    is_spatially_loaded  true — the flag the whole streaming design rests on
    Director             reflected, 6 of 6 CONFIG properties
    hysteresis           activate 12000 < deactivate 20000  OK
    negative control     a class that should NOT resolve, does not

**⛔⛔ THE AUDIT GATE PAID FOR ITSELF BEFORE FIRST COMPILATION** — 7 findings,
3 major, and the sharpest was about my prose. The header said the subsystem
*"owns the spawn and despawn of encounter pawns"*. **It spawned nothing.** There
is no enemy pawn class yet (unit 12), and two counters tallied refusals of
spawns that could never happen. **A header written before the implementation
describes the design; a header left unedited after a smaller implementation
describes a lie.**

The two logic defects came from one wrong model — I wrote the director as if a
marker were a stable object, when spatial loading is the entire point of the
class. Discovery was single-shot (every marker streaming in later was invisible
FOREVER) and active state was keyed on a pointer that changes identity across a
cell reload. Identity is now `(PlanId, PlanRowIndex)` — the durable key the
marker already carried and I had not used for the one thing that needed it.

**Zero compile or link defects.** Every API name was confirmed at engine source.
The design was buildable and the reasoning was wrong.

Full audit row in Division 3.

## ⭐ THE ENCOUNTER PLACER EXISTS AND HAS NOT BEEN RUN

`scripts/encounter_place_payload.txt`. Dry run: 317 to place, 0 prior, destroys
nothing. **Negative control: handed the RAW plan it REFUSES**, because those
rows were never navmesh-verified and the two filenames differ by one word in the
middle of a long path.

**NOTHING IS PLACED.** Placement of wilderness content is behind
`WORLD_VISION` item 4's POI tripwire, which reserves reconfirmation to the
operator. Generation was delegated; placement was not.

## ⭐ UNIT 11: THE CPU KNOWS WHAT YOU ARE STANDING ON — WITH ONE GAP, DECLARED

    Snow 21.38%   Rock 37.30%   Grass 41.32%
    genuine blend boundary (dominance < 16): 1.04% of the map
    positive control  20000 of 20000 re-derived from the weightmap agree
    negative control  the lookup shifted one row — 9.86% disagree
    selftest          4 of 4, including a TAMPERED sha256 REFUSED

`bake_surface_lookup.py` → `textures/alpine_8k_surface.png` →
`surface_query.py`. It reads **the same weightmap the material samples** —
non-negotiable 19, and the plan's own warning not to get this by painting
landscape layers is the same rule from the other side.

**⛔ AND THE ACCEPTANCE CRITERION WAS NOT MET.** Unit 11 asks that the query
agree with **the material's own layer CHOICE**; what was measured is that it
agrees with the material's **INPUT**. If the material's blend logic disagrees
with a plain argmax, every check above still passes — they all read the
weightmap, and non-negotiable 0 says instruments sharing a source are one
measurement. The independent representation is a render and two attempts
produced no frame. `_verify/20260827_surface/WHAT_IS_NOT_PROVEN.md` says what
would close it. **`surface_query` is faithful to the weightmap and unverified
against the pixels.**

## ⛔ THE STRAIGHT-LINE WALK TEST HAS OUTLIVED ITS SPAWN

    yaw  30    27.3 m of 1500 requested    yaw 260    57.5 m of 200
    is_falling 0.1% in BOTH — THE GROUND HOLDS

Unit 5's instrument drives a straight line with no steering, and the PlayerStart
is now in a plaza ringed by 303 buildings. **65 of 72 headings are blocked
within 100 m; the best is 156 m.** A 1 km straight walk from this spawn is
impossible in every direction. That is the test's property, not the world's —
R-WALKTEST said so before a town existed here.

**The world's traversability is proven better elsewhere** (36.5 km² by path
query). What these walks prove is the narrower thing they can: the ground holds.

**And a prefilter was wrong, then CALIBRATED.** `find_walk_heading.py` first
read only the heightmap and the city plan, called yaw 260 clear for 238 m, and
the character stalled at 57.5. Its own docstring predicted it — it could not see
the ~3,700 trees left in the town's gaps, which are query-collidable by design.
With 219,659 tree positions added it predicts both measured stalls
conservatively: yaw 30 → 22 m against 27.3, yaw 260 → 42 m against 57.5.
`--no-foliage` is kept so the difference is measurable rather than asserted.

## ⚠ RENDERS ARE THE STANDING OBSTACLE

Three separate captures stalled today. The editor throttles below 1 fps the
moment it is not foreground, and **every command issued to check on it takes
focus back**. One shot did land — one second after the watcher's 600 s deadline,
which is now a 240 s grace pass rather than a verdict. Two others produced
nothing in ~25 minutes and were skipped and recorded.

**One was my own error:** `ue_exec --timeout 900`. That is the DISCOVERY window
and it is spent IN FULL — a lesson already in `LESSONS.md` and in the tool's own
help, which says use 12–25.

## THE OFFLINE SUITE — ONE COMMAND, no editor, survives a cold replay

    python scripts/run_offline_suite.py          10 checks, ~150 s
    python scripts/run_offline_suite.py --self-test   proves it can report FAIL

**NO FAILURES across 8 checks, ZERO findings.** It separates FAILURES from
FINDINGS and the distinction is ENCODED, not remembered; the two finding
declarations that existed were RETIRED when the finding was fixed, because a
declaration left in place excuses the next genuine failure in the same tool.

## OPEN, RANKED

1. ~~**Extend the navmesh.**~~ **DONE — full region coverage, 72 volumes.**
2. **An architecture kit.** The town is 762 engine Cubes and a Cylinder. The
   operator is buying `medieval_house_10`. **CC BY 4.0 for Blenderust is an
   OPEN obligation** — it survives modification and there is no credits screen.
   **This is now the biggest single gap in the project:** the world is 36.5 km²
   of walkable ground with 317 verified encounter sites and one town made of
   engine primitives.
3. **RULING — MAY THE 317 ENCOUNTER MARKERS BE PLACED?** The placer is built and
   dry-run proven; the plan is verified; the marker class is reflected. **The
   only thing missing is the operator's word**, because placing wilderness
   content is behind `WORLD_VISION` item 4's POI tripwire. One yes unblocks
   unit 10's acceptance test as well, which needs markers in the world and is
   blocked on nothing technical.
4. ~~**Unit 11's acceptance criterion is UNMET**~~ **MET on the third render
   attempt** — Snow separates from Rock by +0.0638 and from Grass by +0.0763 in
   the drawn pixels, against a 0.02 bar. **⛔ ROCK AGAINST GRASS IS STILL NOT
   SEPARATED** (0.0124 apart inside a 0.10-0.12 sigma), so that distinction
   rests on provenance alone and would need chroma or a flat-lit rig.
5. **PIE residency at mounted speed (unit 10)** is STILL owed — but the reason
   is now MEASURED rather than "not attempted", and the instrument is built.
   `_verify/20260827_streaming/WHY_THE_MOUNTED_FIGURE_IS_NOT_HERE.md`.
   **⛔ A STRAIGHT-LINE WALK CANNOT LEAVE THE TOWN.** From the PlayerStart, to
   1200 m: **0 of 360 bearings clear** counting street slabs, 9 of 360 without
   them, widest clear arc **3.0°** — which is 2.6 m at 50 m, and an unsteered
   walker drifts more. Both runs stalled correctly, at 29.2 m into the
   **landmark the spawn is deliberately aimed at** and at 58.4 m on the best
   measured bearing. `scripts/find_clear_heading.py` is that measurement.
   **The speed override IS proven: achieved p50 1800, max 1800 = 1.00 of
   commanded**, gated on the trace and not only on the property read-back.
   **The residency that WAS collected — 3-4 proxies, 10-11 foliage actors — is
   residency AT REST inside a town and is NOT the owed figure.** Quoting it as
   mounted-speed streaming would be non-negotiable 22. Closing it needs a start
   on reachable ground outside the settlement; both halves of the tooling exist.
6. **49 streets still unreachable** (was 185) and 11 buildings orphaned from the
   street network. Both are now small and both are declared.
7. **RULING — prose keys in `city.json` / `encounters.json`.** Options written
   out at the end of `recipes/schema.md`; nothing changed.
8. **RULING — `max_orphan_building_fraction`** is 0.05 against a measured 3.6%,
   a bar chosen to pass the number it first saw. The machinery is proven; the
   VALUE is unratified.
9. **Two `HeroInWorld` actors are duplicates.** Cosmetic.
10. Everything in the 2026-08-22 groom block below is untouched.

---
# CURRENT STATE — 2026-08-26 (a beginning, a navmesh, and a basin that turned out NOT to be sealed -- see the block above) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-SIX
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K`. Autonomous session
under full delegated authority; design rulings taken by the **fable model**, as
instructed. Restore points: `pre-town-navmesh-20260826`,
`pre-town-foliage-clear-20260826`, `pre-city-roofs-20260825`.

## ⭐ PRESS PLAY AND YOU STAND IN A TOWN, ON NAVMESH

    PlayerStart   (-210800, 278800, 18791.8)  yaw 35, facing the landmark
    was           (354600, -321400)           8,245 m away in a forest
    PIE           LandscapeLabCharacter, 90.3 cm above traced ground
    navmesh       projects at 0.0 cm lateral

The old start was **instrument scaffolding** from the 2026-08-15 walk test, not
a design decision. `WORLD_VISION` already ruled the basins are where people
live and the foothill→peak arc is distance from safety, so starting 8 km out
inverted the world's difficulty reading from the first minute. ONE start, not
two — UE picks among multiple starts unpredictably.

## ⭐ THE TOWN HAS A NAVMESH, AND THE AGENT WAS WRONG FOR A WEEK

    NavBounds_Town   1040 m square, centred on the town, z measured by 625 traces
    build            8 chunk actors, 21.59 MB, 34 s, 19.9 GB peak
    warnings         ZERO RegistrationFailed_AgentNotValid

**⛔ RULING 19 WAS COMPARING THE WRONG TWO THINGS.** It required the navmesh
agent to be no steeper than `world.primary_movement_mode` (`mount`, 35°). Its
own error text says the failure it prevents is *"the navmesh would grant paths
onto ground the character slides off"* — and the thing that slides is the PAWN,
which is `climb` at 70°. So the town's navmesh was built for a horse.

Now `walk` (44.765°), derived from the pawn. Proven in four directions: `air` 90
REFUSED, `climb` 70 allowed at equality, `walk` allowed, `mount` allowed.

**Two agents is NOT achievable and do not try it:** `AgentMaxSlope` is not part
of `FNavDataConfig`, and per-actor writes revert via `PostLoad`
(`RecastNavMesh.cpp:963-1015`). Two `+SupportedAgents` differ in
radius/height/step and are IDENTICAL in slope.

## ⛔ SUPERSEDED — "THE TOWN IS 78% REACHABLE" WAS A SEARCH-BUDGET ARTEFACT

**At least 94.2%, measured by relay — see the retraction block below.** The
figures here came from single plaza queries. Kept as the record.

    streets    653 of 838 reachable (77.9%)     0 failed projection
    buildings  253 of 303 at the doorstep (83.5%)
    artefact   city/alpine_basin_town_reachable.json

    ring_m      50   100  150  200  250  300  350  400
    mount      4/6   6/6  7/7  8/8 10/12  4/7  1/7  1/7
    walk       4/6   6/6  7/7  8/8 12/12  5/7  2/7  1/7

The walk agent recovered only 4 of 19. **The outer districts are genuinely cut
off by the basin rim** (186.7 → 333 m). The town's extent was drawn by
PER-STRUCTURE gates — cut/fill and pad slope, each building alone — and
per-element gates say nothing about whole-network traversability. Same shape as
the street-segment defect one level down.

**The unreachable districts are DECLARED, not hidden.** The sidecar is bound to
the agent, chunk count, PlayerStart and query extent it was measured with.

## ⭐ 2,541 TREES CLEARED FROM THE TOWN; ~3,700 REMAIN IN THE GAPS

Per-structure oriented rectangles + margin, never a radius — a radial clear
leaves a circular bald patch. Idempotent; a second pass finds zero.
**The save wrote NOTHING until forced**: 0 foliage packages were dirty after
removing 2,541 instances. `save_foliage_actors.py --go` exists for exactly that.

## ⭐ UNIT 9 EXISTS AND ITS GATES WORK. THE PLAN IS REFUSED, CORRECTLY.

`recipes/encounters.json` → `scripts/plan_encounters.py`, offline, seeded,
byte-identical across runs. Separation gate positive-controlled per-pair.

**THE BASIN CANNOT HOLD ENCOUNTERS, AND THAT IS THE RULING WORKING:**

    prior 40 m    0.69% of the box available = 0.0074 km2
    prior 60 m    2.59%                      = 0.0281 km2
    prior 100 m   8.49%                      = 0.0919 km2

At the ruled 4.68/km² even the most generous prior yields **0.43 encounters**.
An encounter must be OUTSIDE the settlement and NEAR reachable ground, and in
this basin those are the SAME GROUND. `WORLD_VISION:305` rules density scales
with remoteness and this is the least remote place in the world — **the starting
basin is SAFE BY DESIGN.** Widening needs navmesh BEYOND the town volume, not a
smaller margin.

## ⛔ FOUR MEASUREMENTS THAT WERE ABOUT THE INSTRUMENT — read before trusting a nav number

1. **`project_point_to_navigation` takes FIVE args** `(world, point, nav_data,
   filter_class, query_extent)`. Four puts the extent into `filter_class` and
   leaves the extent `[0,0,0]`. Gave 0/40 streets. **The positive control is the
   only reason it was not written up as "the town has no navmesh."**
2. **A LARGE QUERY EXTENT CHANGES THE ANSWER**, it does not merely widen the
   search. At 120 m the plaza "projects" 116.7 m away; at 500 cm, 0.0 cm.
3. **`get_path_length` needs BOTH endpoints projected.** Wrong z → `(ERROR, 0.0)`;
   projected z → `(SUCCESS, 5702.7)`. Compare `== SUCCESS` — truthiness inverts
   it (INVALID=0, ERROR=1, FAIL=2, SUCCESS=3).
4. **Querying a building's CENTRE** projects into the solid it is carved around
   → 0/303. Sample the DOORSTEP → 253/303.

## ⚠ RENDERS: FOREGROUND THE EDITOR OR THEY NEVER LAND

Three consecutive renders produced no file at multiplier 2 AND 1. The engine log
showed **no screenshot entry for 83 minutes** and frames advancing under 1 fps.
Foregrounding took the editor from **1.06 → 5.96 CPU-s per wall-second** and the
pending shot completed in seconds. `city_shot_payload.txt` now takes `MULT`.

## THE ARCHITECTURE EVALUATION — VERDICTS IN

    alps_chalet         DISCARD         580 tris, 9 boxes
    alps_barn           DISCARD         3,740 tris
    alps_church_tower   REFERENCE ONLY  32,204 tris, 74% of the whole pack
    medieval_house_10   WORTH KEEPING   12,151 tris, detail holds at eye level

**CC BY 4.0 for Blenderust is an OPEN obligation** — it survives modification,
so the split derivatives owe it too, and there is no credits screen yet. The
Dubiniec licence is **not recorded**: both archives held only an FBX and PNGs.
**Fab is not drivable from Python** (the only 7 `fab` names are FABRIK rig
units); adding the Megascans pack needs a click. But `InterchangeMegascansPipeline`
exists, so importing it once on disk IS scriptable.

## ⭐ THE 4a ESCALATION LANDED: ONE REACHABILITY MODULE, AND IT REFUSES

`scripts/reachability.py`. Per-element gates failing to compose reached its
SECOND tool in a week (street segments, then town extent) and a THIRD was
already forming — `plan_encounters` had grown a private `near_reachable`
reading the sidecar directly. **Non-negotiable 4a promotes on the second
without waiting for the third**, so the private copy was deleted, not patched.

**What the module adds that the copies did not is a BINDING CHECK THAT FAILS
CLOSED.** A reachability claim is true for exactly ONE navmesh build, so the
sidecar records the agent it was measured at and the module REFUSES a caller
declaring a different one rather than silently answering from stale data.

    walk sidecar loads                     OK   653 reachable street rows
    mount against a walk-measured sidecar  REFUSED
    missing sidecar                        REFUSED   (not "empty")
    proximity: on a row True, 50 km False  OK

Re-measured from a fresh editor run afterwards: streets **653/838** and
buildings **253/303**, matching the prior numbers exactly, 0 failed projections.

**⛔ AND THREE-QUARTERS OF THAT BINDING WAS NEVER ENFORCED.** `_bound_to`
records the agent, the PlayerStart, the query extent and
`nav_chunk_actors_resident`; only the agent refused. **The east extension took
the world 8 → 10 chunks and the sidecar went on declaring 8.** Non-negotiable
25, in the module written to stop exactly this.

**Re-measured against the 10-chunk navmesh — and ZERO of 1141 rows flipped.**
Exactly one field differs in the whole 175 KB file, `8 → 10`. **That is a
second, independent confirmation that coverage is not connectivity:** adding
13.6 MB of navmesh moved not one reachability answer. The enforcement now exists
and refuses both directions — and its limit is stated at the check, because an
OFFLINE caller cannot supply the live chunk count, so `expect_nav_chunks=None`
means UNCHECKED, not verified.

## ⛔ THE EAST EXTENSION BUILT, AND COVERAGE IS NOT CONNECTIVITY

`NavBounds_TownEast`, another 1040 m square sharing its western edge with
`NavBounds_Town` so the pair is contiguous. **East was measured, not picked** —
the offline walkable-component prefilter closed at 440–780 m on bearings
165–285 and ran open eastward.

    chunk actors   10 (was 8)      size 35.18 MB (was 21.59)
    wall clock     36.0 s          bar 30 min
    peak commit    20.0 GB         bar 200 GB
    RegistrationFailed_AgentNotValid   ZERO

    directed probe, bearing 0, every 50 m to 1400 m
      projects    True at ALL 28 points
      reachable   True to 300 m, False for the remaining 22

**The extension is navigable ground the player cannot walk to.** Projection says
a polygon is underfoot; only a path query says you can get there.

**AND THE OFFLINE PREFILTER WAS WRONG AGAIN, IN THE PREDICTED DIRECTION** — it
claimed the component reached 2480 m and covered 95.2% of a 5 km box; the built
navmesh reaches 300 m. It is labelled PREFILTER and its OPEN verdicts are not
trusted; its CLOSED verdicts still ruled out the western half, and that is all
it was used for.

## ⛔⛔ RETRACTED — THE BASIN IS NOT SEALED. THE BARRIER WAS THE QUERY.

**Read this before the block below it, which is kept as the record of the
error.** Every "unreachable" verdict came from ONE `get_path_length` call from
the plaza. A path query has a finite SEARCH BUDGET and returns FAIL when it
exhausts it — indistinguishable, from one call, from ground you cannot walk to.

    A  plaza  -> 520 m    FAIL      (and it reports a partial length, 424 m)
    B  350 m  -> 520 m    SUCCESS   189 m
    C  plaza  -> 350 m    SUCCESS   373 m

**The walk is C then B.** `scripts/city_path_chain_payload.txt`.

**AND THE TOWN IS NOT 78% REACHABLE.** Re-testing each unreachable street from
the NEAREST reachable row: **136 of 185 recovered**, 39 still out, 10 fail
projection. **653 → at least 789 of 838, 77.9% → 94.2%.** Positive control 10 of
10; negative control, a point 50 km away, still does not project.

**SIX MEASUREMENTS ALREADY SAID SO AND I EXPLAINED EACH AWAY** — terrain 93.0%
walkable with no continuous steep band; erosion to 2.0 m does not disconnect it;
919 of 925 points project; `nav_dz` p50 12.4 vs 13.4 cm, same surface same
datum; the model scoring 91.5% on PROJECTS and 48.9% on REACHABLE; and the
uniform 24-bearing profile, **which is the shape a BUDGET makes, not the shape
terrain makes.** I read that uniformity as evidence of a uniform wall.

**It was believed because it REPRODUCED** — across sampling intervals, bearings
and two navmesh builds. Consistency is what a budget produces.

**INVALIDATES:** the ramp ruling (moot, no terrain touched); the reachable
sidecar and every consumer; "the basin cannot hold encounters"; and the east
extension's "navigable ground the player cannot walk to".

---

## ⛔ SUPERSEDED — THE BASIN IS SEALED: A 1.25 m STEP AT 51°, AND NO PASS ON 24 BEARINGS

`_verify/20260826_basin_rim.md`. Resolved at 0.5 m: last reachable **322.0 m**,
flip at 322.5, gradients **51.34° and 51.33°** at 323.5–324.0 m against a
44.765° agent bar and a 45 cm step height. **Navmesh projects at every point**,
so it is neither a coverage gap nor a `MinRegionArea` artefact.

**THE DENOMINATOR DECIDED THE DIAGNOSIS.** At 5 m spacing that same place reads
**35.71°** — under the bar, i.e. "not a slope problem". At 0.5 m it reads 51.34.
Recast evaluates at `CellSize` ≈ 19 cm. A gradient without its denominator is
not a slope.

    24 rays at 15 deg, 4 m sampling to 700 m, furthest reachable per bearing
    furthest overall 504 m (bearing 90)   median 360 m   min 252 m

**THERE IS NO NATURAL PASS.** A pass would show as one bearing running far
beyond its neighbours with nothing over the bar before it; the profile is
uniform and the best bearing is 1.4x the median. **But the rim is not uniformly
thick:** bearing **315° has 2 samples over the bar** and **285° has 4**, against
19 at bearing 195. If a pass is ever authored, that is where the least earth has
to move.

**This supersedes my own six-bearing figures** — those reported the FIRST FLIP
along each ray, which moves with sampling (bearing 0 read 244 m at 2 m spacing
and 322 m at 0.5 m, because the coarse probe stopped at an isolated dropout).
The sweep takes the FURTHEST reachable point, which no single dropout can move.

**AND IT CORRECTS THE EAST-EXTENSION COMMIT'S OWN OPTIMISM** — that entry called
the barrier "a local step, not a wall" from 50 m samples. It is a wall, all the
way round.

## THE DEBT SWEEP — TWO LESSONS ENCODED RATHER THAN RECORDED

Swept 35 commits for diagnoses whose fix was not in the code. Five had been
closed by the session's own work; two were live.

**1. THE CAMERA GROUND GUARD**, "named and NOT built" the day before, had
already cost a 10-minute render of the terrain's UNDERSIDE with trees hanging
downward. **The transform assertion passed perfectly** — the camera WAS where it
was asked to be, so no read-back could have caught it. The request was wrong.
`fix_camera_z.py` covers RECIPE cameras; an ad-hoc `--set LOC` passes no guard,
and the ad-hoc path is the one a person reaches for. The guard now lives in the
shot payload, the one place every camera must pass, and refuses BEFORE the
output directory is created. An unreadable ground trace reports COULD NOT LOOK.

**2. `plan_city`'s WHOLE-NETWORK GATE** — 292 of 303 buildings within 40 m of
the connected street network, 11 orphaned (3.6%).

## FOLIAGE MARGINS MEASURED AT 5 / 10 / 15 m — REPORT ONLY, NOTHING REMOVED

Dry runs at `COMMIT=False`; no instance removed, no package touched. These are
ADDITIONAL to the 2,541 already cleared at the shipped 3 m / 2 m margins.

    margin   additional   cumulative   remaining of the original 6,244
     5.0 m          960        3,501                     ~2,743
    10.0 m        2,259        4,800                     ~1,444
    15.0 m        2,873        5,414                       ~830

**NO RULING TAKEN; the shipped margin stays 3 m / 2 m.** At 15 m the town
becomes open ground with a few specimen trees rather than houses in a wood —
an art call, not a measurement.

**Separately: 16 conifers stand within 22 m of the plaza**, which is the first
thing a player sees. Not a defect in the clear — the clear is PER-STRUCTURE and
the plaza is defined as ground with no structures on it, so nothing there was
ever a candidate for removal.

## ⛔ A COMMITTED PLAN ITS OWN PRODUCER NOW REFUSES

`encounters/alpine_8k_all.json` carries **five encounters** and the planner that
wrote it now generates **zero**. The availability denominator was corrected
after it was committed — the artefact says `target_count: 5`, the corrected
method computes 0 — and the stale plan kept sitting at exactly the path a placer
would read, looking current.

**Nothing was checking, because nothing in this repo re-checked a plan.** And it
could not be checked FROM the file: plans carry their inputs' PATHS, not their
HASHES, which is non-negotiable 20's live pointer.

`scripts/check_plan_freshness.py` — offline, read-only, two instruments that do
not share a source:

    city/alpine_basin_town_plan.json   STALE by HISTORY  ->  ok REPRODUCES
                                       65ab655ed1a0 both ways
    encounters/alpine_8k_all.json      STALE by HISTORY  ->  !! PRODUCER REFUSES
    16 further plans                   UNSTAMPED -- CANNOT CHECK, not "fresh"

**The city plan is the discriminating row.** Three of its four inputs were
committed after it and the output is byte-identical. **A commit that touches a
producer is not a change to its output** — history answers "could this have
changed", only re-derivation answers "did it".

**NOTHING WAS MOVED OR DELETED.** The stale plan is dangerous only when
something consumes it and no encounter placer exists. Its disposal is a ruling.

**⭐ AND PLANS NOW CARRY THEIR INPUTS' HASHES**, so staleness is a fact on disk
rather than a re-derivation. `scripts/plan_stamp.py` — ONE declaration of
`INPUT_KEYS`, written by both planners and read by the checker, because a key
set checked in two places is non-negotiable 24. It REFUSES to stamp around an
input it cannot read.

    city plan   STALE by HISTORY   a suspicion
                STAMP MATCHES      a fact on disk about the INPUTS
                REPRODUCES         decisive about the OUTPUT

**The ranking is written down deliberately.** The stamp outranks HISTORY — a
commit touching a producer is not a change to its output, a changed hash IS a
change to its input — and does NOT outrank REPRODUCE, because a producer that
depends on something it does not declare will still drift.

**THE TOWN DID NOT MOVE, DEMONSTRATED NOT ASSERTED:** strip the stamp key from
the regenerated plan, re-serialise both, `47abfa61 == 47abfa61`. Every consumer
re-run afterwards, including the live world (`ok true`, grounding max 0.0 cm).
Restore point `pre-plan-stamp-20260826`.

**Proven to refuse, positive control first:** corrupted hash → DIFFERS naming
the input; stamp removed → UNSTAMPED; stamped input deleted → UNREADABLE, not
MATCHES; stamping with a missing input → REFUSED.

**⚠ AND THE TOOL DIED AT EXACTLY THE MOMENT IT HAD A FAILURE TO REPORT** —
`UnicodeEncodeError` on cp1252 stdout from an emoji that appeared only on the
failure branch. Every `ok` row printed; the first bad one killed the process
before the summary. **A tool that cannot print its own worst verdict reports
success by omission.** ASCII markers now, asserted.

## ⭐ plan_city's FOUR GATES HAD ONLY EVER SEEN THE TOWN THAT PASSES THEM

`scripts/prove_city_gates.py`, offline. All four refuse under mutation, the
positive control still passes, and **every refusal is asserted to have WRITTEN
NOTHING** — an exit code cannot tell "refused before writing" from "wrote, then
refused", and the second leaves the refused plan where the placer reads it.

**The prover is itself positive-controlled** (`--self-test`) against a copy of
`plan_city.py` with one gate made unsatisfiable, and the discrimination is
sharp: exactly the two cases routed through the dead gate fail, the other three
still refuse, the positive control still passes.

**⛔ AND THE FIRST VERSION OF THAT CONTROL WAS INVALID IN THE WORST WAY —
it produced the EXPECTED verdict for the WRONG reason.** The broken copy was
written outside `scripts/`; `plan_city` derives its repo root from its own
`__file__`, so it died before reaching a gate and all five cases "refused",
which is indistinguishable from five working gates. **What caught it was the
POSITIVE control failing too** — the broken-gate hypothesis does not predict
that. A control that fails EVERYWHERE is an instrument fault until proven
otherwise.

## OPEN, RANKED

1. ~~**RULING — HOW DOES THE PLAYER LEAVE THE BASIN?**~~ **CLOSED — the
   question was wrong.** The basin is not sealed; the barrier was the path
   query's search budget. The operator's ruling to CUT THE RAMP is moot and no
   terrain was touched. The live work is re-deriving everything that read the
   bad sidecar.
2. **An architecture kit.** The town is 762 engine Cubes and a Cylinder. Only a
   purchase fixes it; `medieval_house_10` is the evidence the paid pack is worth
   looking at. **CC BY 4.0 for Blenderust is an OPEN obligation** — it survives
   modification, so the split derivatives owe it too, and there is no credits
   screen yet.
3. **RULING — prose keys in `city.json` / `encounters.json`.** The character
   recipe's convention is "no prose keys, the recipe is data"; roughly half the
   keys in these two are `_why_…` / `_what_…`. Three options are written out at
   the end of `recipes/schema.md`, nothing changed. Note the landscape validator
   DOES refuse unknown keys (it rejected `_extension_note` on 2026-08-26), so
   the question is only open for recipes it does not read.
4. **RULING — `max_orphan_building_fraction`.** Set provisionally at 0.05
   against a measured 3.6%. A bar chosen to pass the number it first saw is
   non-negotiable 2's untested gate. The machinery is now proven to work
   (`prove_city_gates.py` refuses at 0.0); the VALUE is still unratified.
5. **RULING — the stale `encounters/alpine_8k_all.json`.** Regenerate it (it
   will refuse until item 1 is settled), move it to `_trash/`, or keep it
   labelled as the record of the pre-correction method. Nothing consumes it
   today; `check_plan_freshness.py` now makes it impossible to consume by
   accident.
6. ~~**OWED — stamp every plan with its inputs' SHA-256**~~ **DONE** for the
   city and encounter planners (`scripts/plan_stamp.py`). **16 plans are still
   UNSTAMPED and declared so** — every `foliage/*.json` and the reachable
   sidecar, produced by in-editor payloads or by `place_foliage`. Extending it
   there is the remainder.
7. **The 11 orphaned buildings and the 50 unreachable ones** are DECLARED, not
   hidden, and both are consequences of item 1, not separate defects.
8. **Two `HeroInWorld` actors are duplicates** at identical coordinates. They no
   longer sit on the spawn, so this is cosmetic.
9. Everything in the 2026-08-22 groom block below is untouched.

## ⭐ AND `plan_encounters` HAD NEVER ONCE WRITTEN A PLAN

It has been correct all day and only ever REFUSED — the right answer for a basin
that cannot hold an encounter. **So the gates were well tested and the half that
produces output had never run**, which is the class the first calls of
`create_landscape_from_heightmap` and `build_landscape_nanite` were in.

`scripts/prove_encounter_plan.py`, in a **SYNTHETIC** 3 km world (a COPY of the
recipe; the real basin's refusal is still the correct answer):

    placed        66, target 66   scavenger 43, raider_camp 17, beast 6
    separation    tightest pair 10924 cm against a required 10500, PER PAIR
    settlement    0 of 66 inside the town's 1142 oriented rectangles
    spawn         nearest row 322 m out, bar 150 m
    determinism   byte-identical across two runs
    negative ctrl separation x60 -> REFUSED, wrote nothing

**Every invariant is re-derived from the OUTPUT by code that did not place the
rows** — the planner asserting its own invariants and then reporting success is
a read-back of the field the writer wrote.

**A refusal that named the wrong bar, fixed:** `need = max(floor, ceil(frac ×
target))` always blamed the fraction, so on a target of 0 it printed *"below 80%
of target (need 3)"* — 80% of 0 is 0, the FLOOR was binding, and the reader was
pointed at the wrong knob. Both branches are now exercised: the real basin takes
the floor branch, the prover's control takes the fraction branch.

## ⭐ THE TOWN VERIFIES AGAINST THE LIVE WORLD — AND ITS ALARM WAS A ROOF

`city_verify_payload.txt` against the committed plan, the different-representation
check nobody had made since the roofs landed:

    ok      true    buildings 303  roofs 303  streets 838  landmark 1  spire 1
    grounding over the 1142 ground-sitting actors
            p50 -0.0   min -0.0   MAX 0.0 cm   60 traces, 0 misses

**It first REFUSED a correct town.** It summed three hardcoded terms; roofs and
a spire were added to the planner afterwards, and the plan's own `counts` had
been declaring both all along. **Non-negotiable 24** — and the fix is not
"add roofs to the list", which reproduces it one kind later. The expectation is
now DERIVED from the plan's own geometry: a section carrying `loc_cm` is a
placement. The next kind is covered the day it is planned.

**Its other alarm, `base_above_ground max 883.1 cm`, was a ROOF measuring the
height of the building under it.** Roofs and spires sit on other actors by
design. Conditioned on the kinds that are supposed to be on the ground, the max
is **0.0 cm** — the same town, a different denominator (non-negotiable 22).

**PROVEN IN BOTH DIRECTIONS.** A mutated COPY of the plan (one building removed,
the whole `spire` section deleted) against the unchanged world refuses with
*"buildings planned 302, in world 303; spire planned None, in world 1"* — it
catches a MISSING KIND, which a hardcoded sum cannot.

## THE OFFLINE SUITE — ONE COMMAND, no editor, survives a cold replay

    python scripts/run_offline_suite.py          10 checks, ~150 s
    python scripts/run_offline_suite.py --self-test   proves it can report FAIL

**It separates FAILURES from FINDINGS, and that distinction is ENCODED rather
than remembered.** `check_plan_freshness` exits 3 when a plan is stale — which
is the tool WORKING — so the expected code and its reason are declared per
check. A blanket "ignore non-zero" would hide a real regression in the same
tool; teaching people to ignore non-zero exits is worse than the exit itself.

**Proven to classify all three outcomes**, including the two that matter: an
exit code DIFFERENT from the declared finding code is NOT excused, and a missing
script FAILS rather than being skipped.

Individually, if you want one:

    prove_gates.py                    the recipe/gate corpus
    prove_city_gates.py               plan_city's four refusals, and that they
                                      write nothing  (--self-test proves it can fail)
    prove_encounter_plan.py           the encounter SUCCESS path, re-verified
                                      independently in a SYNTHETIC world
    plan_encounters.py --selftest     separation + settlement units
    check_plan_freshness.py --reproduce   every plan vs its inputs, three
                                      ranked instruments  (--self-test proves
                                      the stamp refuses)
    measure_city_connectivity.py      the street graph, geometrically

## WHAT WAS DELIBERATELY NOT DONE

Under the standing hard rules for the unattended run: **no foliage removed
beyond the committed clear, no landscape edit, no placed actor deleted, no
recipe field changed that alters the town's form or count, and no Fab content
bought, installed or applied.** Four rulings are written down above with their
options and **nothing was picked** — that was the instruction, not an oversight.

---

# CURRENT STATE — 2026-08-25 (the city's streets join) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-FIVE
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K`, cold-launched this
session and verified against `UE_PROJECT_ROOT`. The level is SAVED.

**⚠ TWO SESSIONS LEFT NO BLOCK HERE.** The 2026-08-23/24 face work and the
2026-08-24 city placement wrote no CURRENT STATE, so the block below this one
skips from the groom loop straight past both. Their record is in their commit
messages (`9d8e824a`, `96dfeb63`, `84b992ba`, `3198e6be`) and in `R-CITY`.

## ⭐ THE CITY'S STREETS NOW JOIN — 838 SEGMENTS, ONE NETWORK

    before   459 segments, 155 disconnected pieces, largest 42 = 821 m,
             town centre stranded in a 22-segment fragment
    after    838 segments, ONE component, 15,001 m, centre included

    placed   1,142 volumes  (303 buildings, 838 streets, 1 landmark)
    disk     external actor packages 2135 -> 2514, delta +379 = 1142 - 763
    grounded base above ground p50 -0.0, max 0.0 cm over 60 fresh traces

Recipe **R-CITY** (new, closing the new-element debt `recipes/city.json` carried
in its own `_schema_status`). Narrative in `LESSONS.md` 2026-08-25.
Restore point: tag **`pre-city-replace-20260825`**.
Render: `_verify/20260825_city/CITY_topdown_repaired.png`.

**ROOT CAUSE WAS THE METRIC, NOT THE BAR.** `plan_city.py`'s street slope took
the MAX of six consecutive height differences — a ROUGHNESS statistic. It read
p50 10.54 deg over a basin surveyed at MEAN SLOPE 6.25, so it rejected the
median segment of ground already certified flat enough to hold a town.
End-to-end GRADE reads p50 3.84 on the same lattice. **A bar is ruled about a
quantity, and the metric must be that quantity.**

**AND "KEEP THE LARGEST COMPONENT" WOULD HAVE DESTROYED THE TOWN** — that was
the fix the 2026-08-24 commit proposed, and on the real data the largest
component held 9.2% of segments and did not contain the centre. Streets are now
pruned to the PLAZA's component.

## ⛔ THE NEXT DEFECT, MEASURED AND UNFIXED: 6,244 TREES STAND IN THE TOWN

    within the town extent, 470 m    6,244 instances
    within the core, 184 m           1,266

Buildings and mature spruce occupy the same ground. **The placer ignores foliage
when TRACING and that is correct** — hard-won, because a building sited under a
spruce would otherwise be placed 21 m up on its canopy — but nothing removes the
trees, and clearing ground is what founding a settlement IS.

Needs a ruling on the margin (buildings only, or streets too, and how far out).
Removing instances is destructive to the foliage actors holding 219,659 trees.

## THE CITY IS STILL A GREYBOX, AND THE WORD MATTERS

762 engine `Cube`s and one `Cylinder`, labelled `City_Bldg_*` / `City_St_*`. It
answers where a town stands and how it reads at range; it does not answer what
it looks like. An architecture kit must be bought — `BACKLOG.md:238`.

## THINGS THAT WILL COST A FRESH SESSION TIME

**1. THE DRY RUN TRACED ONTO ITS OWN ROOFS.** The commit path destroys the prior
placement by tag before tracing; the dry run destroys nothing, so it traced onto
the standing town and reported plan-vs-trace **p50 968.56 cm**. That resembles
the render-v2-collide-v1 defect this project really had at p90 30.98 m, which is
what makes a wrong reading like that believable. Fixed: the trace now ignores
tagged prior actors as well as foliage, and returns p50 0.90 / max 38.32 cm.

**2. A 120 s WATCHER ON A HighResShot 2 GIVES UP OVER A GOOD FRAME.** At
4064x2546 the shot takes well over two minutes. **This was recorded on
2026-08-24 and left unencoded, so it fired again.** Budget now 600 s and the
elapsed time is reported. *A lesson recorded but not encoded fires twice.*

**3. `save_level.py` ALLOW-LISTS BY RECIPE OWNERSHIP, NOT BY WHAT YOU TOUCHED.**
The city save also wrote two `LandscapeStreamingProxy` packages, dirtied by a
PIE run earlier in the same session, centred at (330200, -330200) — the hero
spawn, not the town. Terrain geometry is unchanged, measured by a different
representation: 1,142 collision traces against a heightmap-derived plan agree to
p50 -0.32 cm.

**4. `git status` UNDER-COUNTS NEW FILES.** It collapses whole untracked
directories into one entry — it read 1108 where `-uall` reads 1142. Reconcile
against the on-disk count.

**5. THE HERO THE WORLD USES IS GITIGNORED.**
`/Game/Hero/Unpacked/MHC_AlpineHero/` — 324 uassets, 817 MB, Assemble output.
The TRACKED source of truth is `Content/Hero/MHC_AlpineHero.uasset` plus
`hero/dna/*.dna`. There is a SECOND assembled copy at
`Content/MetaHumans/MHC_AlpineHero/` that is **not** the one in the level.

## OPEN, RANKED

1. **Clear the foliage inside the town** — 6,244 trees. Needs the margin ruling.
2. **The city is a greybox.** An architecture kit is the unblock, and it is a
   purchase.
3. **The two `HeroInWorld` actors are DUPLICATES** at identical coordinates
   `(354600, -321400, 31019.47)`, and `PlayerStart` is at the same XY — so
   pressing Play spawns you inside them.
4. **The instanced placement route is still unreachable from Python** — 1,142
   external packages for one town where one would do. Needs a UFUNCTION in
   `LandscapeLabEditor`, the R-CREATE / R-GROOMBIND3 unblock.
5. Everything in the 2026-08-22 block below is unchanged, including the groom
   candidate choice and the third-party groom seating problem.

---

# CURRENT STATE — 2026-08-22 (overnight groom loop) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-FOUR
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` — the second of the
night; the first was killed by a UE assertion during a groom import (see
below). Nothing was saved into the level; the hero wears his committed groom.

## ⭐ A HEADLESS BLENDER GROOM LOOP EXISTS, AND IT REACHES UE

Full account: **`hero/groomloop/MORNING_REPORT.md`**. Iterations:
`ITERATION_LOG.md`. Strategies live and dead: `APPROACHES.md`.

24 iterations reshaping the downloaded `SC_Hairstyle_Male_11` groom toward the
hero reference. **~60 s per iteration** for edit → export → integrity gate →
measure → render. Three candidates, all imported into a live UE 5.8 editor.

    base -> best (candidate 028)
      fringe reach past brow   -3.65 cm  ->  +0.96 cm
      forehead covered          22.5%    ->  70.3%
      scalp visible, mean       43.9%    ->  22.9%   (front 50.4 -> 20.8)
      lock separation (scatter) 0.433    ->  0.606
      silhouette          smooth curtain bob -> directional layered shag

**THE BIGGEST WIN CAME FROM AN ESCALATION CONSULT, and its diagnosis is worth
carrying:** every op in the engine was `f(root_position) x g(t)`, evaluated in
ROOT space, so two strands rooted 1 mm apart could never diverge and the groom
could not stop reading as a uniform mass. Its cheap probe then found that
**curve INDEX carries the artist's own guide grouping** -- consecutive-index
roots sit 4.13 mm apart against 125 mm for random pairs. Using index blocks as
the lock partition improved coverage AND texture together, which nothing else
in 23 iterations had managed.

**WORKDIR is `hero/groomloop/`, not the Desktop path the brief named** — the
repo's own `guard.py` refused the write and I did not route around it.

## ⛔ FOUR THINGS THAT WILL COST A FRESH SESSION A DAY

**1. AN UNCULLED EXPORT KILLS THE EDITOR.** `Assertion failed:
CurveNumVertices >= 2`, `GroomBuilder.cpp:2403`. The source carries 1,210
one-point curves and Blender's exporter writes them in a form UE asserts on.
`cull_degenerate.py` removes them via `bpy.ops.curves.delete` and asserts it
removed exactly the set it found. **A rebuild via `hair_curves.new` +
`add_curves` CRASHES BLENDER** — 5.2 exposes no add/remove on `Curves`.

**2. AN EXPORT AT `global_scale` 1.0 LANDS IN UE AT 1/100 AND AT THE ORIGIN.**
Measured on the identity round trip, so it is not an edit artefact: vendor
z 138–164 cm, ours z 0.75–2.71. The `_ue.abc` variants are pre-scaled ×100 —
**so do NOT also enable Convert Scene on those.**

**3. `global_scale` MULTIPLIES `radius` TOO.** The source's constant radius
0.436611 became 43.7 UE units and the groom rendered as giant blocky ribbons.
The width attribute is NOT stripped — it is present and wrong. The exports now
write it explicitly at 0.00018 → 0.018 UE cm.

**4. A THIRD-PARTY GROOM STILL DOES NOT SEAT ON THIS HERO.** Unchanged from
2026-08-21 and now confirmed on our own edited copies: it draws in UE at
correct width and lands on the JAW. The pack's binding declares
`SKM_MH_Groom_Head` as its source; identity seats it wrong, source-transfer
renders bald.

## ⚠ TWO CLAIMS I MADE OVERNIGHT AND THEN CORRECTED

**"Blender is mis-reading the source; everything is built on a corrupted
read."** Overstated. `tail_probe.py` measured it: 1.28% degenerate, 1.98%
over-long, **96.73% plausible**, zero curves between 0.40 and 0.80 m and
exactly one above. Both bad tails were already handled. Corrected in place in
the report and in `APPROACHES.md` A8.

**"8,678 sub-millimetre curves may be parse damage."** They are a **vellus /
neckline layer** — rooted 6.5 cm lower than the normal strands, concentrated
there, written in index batches. `stub_probe.py`. Leave them.

## THE MECHANISM THAT MATTERED MOST

**Rotate strands about their own root; do not translate their tips.** Every
attempt at the reference's wind-blown direction translated tips, which drags
them off the skull and uncovers scalp (left exposure 22.9 → 34.4%). A rigid
rotation preserves each point's distance from its root: it improved *every*
view at once and beat the untouched source on all three. **Rotation and
translation FIGHT** — running both scored worse than rotation alone.

## OPEN, RANKED

1. **Pick a candidate** — 021 / 020 / 023, ranked with renders in the report.
2. **The third-party seating problem** (item 4 above) is what stands between a
   candidate and the hero's head. Same blocker as 2026-08-21.
3. **Length grading tops out at 0.547** against a target above 1.0. The source
   is a curtain cut whose length lives in the crown; iteration 022 showed what
   happens when strand lengths are pushed to serve the metric.
4. **Test assets left in UE** — listed in the report §6b, all gitignored and
   safe to delete except the candidate you keep.
5. Everything in the 2026-08-21 block below is unchanged: the hair art-direction
   ruling, the eye colour, the flat-lit rig.

---

# CURRENT STATE — 2026-08-21 (art direction, then seating) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-THREE
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` — a COLD launch this
session; the one the previous block records had been closed. The hero is the
SAVED actor, facing the camera at the comparison framing. **Nothing was saved
and no tracked file was touched by the render work** — the placement tool ran
`--respawn no`, so the committed external actors on disk are byte-unchanged.

## ⛔⛔ READ THIS FIRST: THE SHAPE DECIDED IN BLENDER IS NOT THE SHAPE UE DRAWS

**Ryan ruled "re-author toward the reference". The first act of that — re-author
the v22 baseline as a control before touching a parameter — found that the
control does not match the thing it controls.** Blender's v22 draws a full side
curtain past the ears to the jaw; UE's v22, the same asset, is a close cap with
both ears bare. `SHEET_blender_vs_ue_v22.png`.

**So the loop's founding premise — decide the shape in Blender, let the UE trip
prove the groom — has been false for as long as the loop has existed**, and
every shape ruling this week was taken on a picture UE does not reproduce.
`RECIPES.md` **R-GROOMSEAT**; narrative in `LESSONS.md` 2026-08-21.

### THE LADDER THAT LOCALISED IT — each rung moves ONE thing

    Blender, re-authored from PARAMS   full curtain -- and it reproduces the
                                       shipped v22 blend EXACTLY (77,697 px)
    the guide stack build              same shape
    the groom ASSET in UE              max_curve_length 20.444 cm against
                                       Blender's 20.261 -- THE LENGTH IS IN
                                       THE ASSET
    component hair_length_scale        1.0, override False
    standalone GroomActor UNBOUND      THE FULL AUTHORED SHAPE
    standalone GroomActor BOUND        THE FULL AUTHORED SHAPE
    hero's MetaHuman component BOUND   the short cap
    hero's MetaHuman component UNBOUND nothing draws
    VENDOR groom, same component       renders correctly, same session

~~**THE BINDING IS EXONERATED** — rungs 5 and 6 carry the authored shape.~~
**BOTH HALVES OF THAT ARE CORRECTED BELOW AND THE CORRECTION IS THE POINT.** A
400-field component diff returns one substantive row, `attachment_name =
FACIAL_C_FacialRoot`, and **that is not it either**: the vendor grooms share it
and render correctly. Every scale on both paths is 1.0, measured.

## ⭐⭐ THE SEATING IS FIXED — THE AUTHORED HAIR RENDERS ON THE HERO

    guide_every 20    2,400 guides    BALD
    guide_every  4   12,000 guides    BALD
    guide_every  1   48,000 guides    FULL HAIR
                                      Hair PRESENT 29.6x floor, crown 91%,
                                      drift 0.6%, reproduced over two passes

`TEST_v22_guides_every1_*.png`. Single variable — same blend, same builder,
same session. **`build_guide_stack.py ... 1` is the whole fix.**

**AND IT IS A WORKAROUND, NOT A REPAIR.** A gradient would mean density; a
CLIFF at "every curve is its own guide" means **CORRESPONDENCE** — that is the
only configuration in which each strand's nearest guide is itself and
`Merge Guide and Weight it` cannot get the weights wrong. It costs 144,000
curves against 52,800, and the weighting defect is still there.

**A VENDOR GROOM BUILT THROUGH OUR OWN BUILDER RENDERS CORRECTLY** —
indistinguishable from the vendor's own binding. That one control retired the
binding builder as a suspect after two days had gone into binding routes.

## ⛔ THREE OF MY OWN CLAIMS FROM EARLIER TODAY, CORRECTED BY THE TOOL'S REPORT

**1. "ONE GROOM, THREE SHAPES" IS WITHDRAWN.** `build_guide_stack.py` reports
`evaluated_z` **[158.645, 181.894]** against the raw **[158.633, 181.971]** and
`crown_delta_cm` 3.457 against 3.52 — **the stack does not move the geometry.**
Panels 1 and 2 of `SHEET_three_shapes.png` are an ORTHOGRAPHIC Blender preview
and a PERSPECTIVE UE render of the same curves, and I read a shape difference
into a camera difference — **the project's own recurring error, committed one
entry after writing the rule against it.**

**2. THE TWO NODES I NAMED FOR THE BISECT NEVER RUN.** `Shrinkwrap Hair Curves`
and `Attach Hair Curves to Surface` are Blender essentials assets absent from
the demo .blend; the applied stack is THREE nodes. The tool says so in its own
report, and the comment saying so is at line 153 of the file I had read.

**3. AND MY BISECT FEATURE NEARLY HID IT** — the env-override wrote
`rep["skipped"]`, colliding with the field that records exactly this, and
overwrote it on the first run. Renamed `skip_requested`.

## ⚠ A THIRD-PARTY GROOM: `SC_Hairstyle_Male_11`, 94,408 curves

    its own binding GB_SC_...     BALD
    our IDENTITY binding          DRAWS -- seated on the JAW, scalp bare
    our SOURCE-TRANSFER binding   BALD

**The jaw seating is the informative one:** an identity binding asserts the
groom was authored on the target's own topology, and this one was authored on
`SKM_MH_Groom_Head`. **A pack's own binding declares the head it was authored
on, as BOTH its source and its target — read it there, do not guess.**
Supplying it as `SOURCE_MESH` still rendered bald, so **the transfer path is
UNPROVEN, not fixed**, and third-party grooms are not yet usable on the hero.

## ⛔ THE EARLIER "TWO STAGES" READING — SUPERSEDED BY THE ABOVE

**Ryan then ruled: fix the seating.** The attempt did not fix it. It localised
it to TWO stages and corrected the block above.
`_verify/20260821_artdirect/SHEET_three_shapes.png`:

    1  Blender raw curves          a curtain hanging DOWN, fringe on the brow
    2  UE standalone, post-stack   swept BACK and up -- full LENGTH, a
                                   DIFFERENT HAIRCUT
    3  UE bound on the hero        a short cap, ears bare

**CORRECTION 1: rungs 5-6 do NOT exonerate the binding.** A standalone
`GroomActor` has no skinned mesh, so a binding's transfer data is never
exercised. Those rungs prove the binding does not corrupt the ASSET, which is
not what I claimed.
**CORRECTION 2: the standalone does not render "the authored shape".** It
renders full LENGTH and a different SHAPE — so the GUIDE STACK is already
destroying the haircut before UE is involved.

**THE RUNG THAT DOES CLEAR THE BINDING SUBSYSTEM IS NEW.** A VENDOR groom built
through our own `build_fresh_groom_binding` renders correctly on the hero,
indistinguishable from the vendor's own binding. **Our binding builder is not
the defect.**

**THE GUIDE STACK IS NECESSARY AND INSUFFICIENT:**

    raw authored .abc, NO stack   imports at exactly 48,000 curves, binds,
                                  assignment VERIFIED on the component, and
                                  renders BALD
    with the stack                renders, collapsed
    a vendor groom, our builder   renders correctly

**AND THE METRIC WAS TELLING ME ON THE FIRST RUN.** `preview_hair.py` reported
`height_gain_cm` **3.52 -> 0.05** between the authored blend and its guide
stack — a 70x change — and I dismissed it as an artefact because `hair_px`
barely moved. It is *also* genuinely void (that blend has a guide OBJECT, so
hiding the hair does not give a bare head and the difference control is
contaminated). **A number that is both alarming and untrustworthy is the worst
kind: fix the control, never explain the number away.**

**THE DEEPER ONE, AND IT INVALIDATES A WEEK OF NUMBERS.**
`preview_hair.py` takes its CENSUS from raw curve data and its SILHOUETTE from
a render, which evaluates modifiers. On a blend carrying a Geometry Nodes stack
those are **two different pieces of geometry**, reported side by side under one
heading — and the alembic that ships is the evaluated one. **Every scalp and
root statistic taken this week describes the PRE-stack curves.**

**THE NEXT CUT IS NAMED.** Bisect the five-node stack. `Shrinkwrap Hair Curves`
and `Attach Hair Curves to Surface` are the two that can move geometry, and
`Attach` is required — its absence IS the bald render. **First cut: keep
Attach, drop Shrinkwrap**, then compare against panel 2 above.

### THE OPEN LEAD, STATED AS A CORRELATION BECAUSE THAT IS WHAT IT IS

    all SIX vendor HAIRS         enable_global_interpolation TRUE   right
    every groom we ever made     FALSE                              wrong
    brows/stubble (1-2 cm)       FALSE                              right

Its docstring is the suspected mechanism verbatim: *RBF interpolation instead
of the LOCAL SKIN RIGID TRANSFORM*. A rigid carry by a wrong root frame throws
a strand in proportion to its LENGTH, which is why 1–2 cm brows survive at
False and a 20 cm hair does not.

**NOT DEMONSTRATED, AND THE ONE TEST FAILED.** Setting it True and rebuilding
the binding produced a binding the component REFUSES — four attempts, against a
positive control that re-assigned the old binding on the first. Suspected: the
RBF path needs a real SOURCE mesh and an identity source gives it nothing to
solve. **It also re-explains the flag's 2026-08-18 retirement** — "correlates
with groom WEIGHT" and "correlates with LENGTH" are the same table, and that
investigation was about a BALD render, not a deformed one.

## ⭐ AND THE RULED TASK HAS A ROUTE THAT NEEDS NO PIPELINE WORK

`SHEET_three_way.png` — reference | vendor `Hair_M_SideSweptFringe` | custom
v22, same component, same camera, same session. **The vendor groom is a closer
match to the ruled reference than anything the custom pipeline has produced**:
long, layered, over the ears, to the jaw, fringe on the forehead. It was on the
character two days ago and was replaced by the custom groom.

## ⭐ THE HAIR HAS BEEN PUT BESIDE THE REFERENCE, AND IT IS A DIFFERENT HAIRCUT

Report of record: **`_verify/20260821_artdirect/ART_DIRECTION.md`**.
Sheets: `SHEET_front_v22.png` (reference | current) and `SHEET_rear_v22.png`.

**The reference is a long, layered, shaggy mid-length cut. v22 is a short
crop. This is a difference of CLASS, not of tuning.**

    ears        reference falls over and past them   v22 leaves both bare
    fringe      heavy, forward, to the brow line     v22 has none; swept back
    silhouette  wide, irregular, spiky               v22 a smooth close cap
    rear        covers the occiput to the collar     v22 ends in a shelf,
                                                     nape and neck bare

**AND THE THREE DEFECTS CLOSED YESTERDAY REALLY ARE CLOSED.** No strands over
the eyes, no slicked skull, no bowl line. The beard is the strongest match on
the character. The groom is bound and drawing — Hair PRESENT at **51.6x floor,
crown 96%, drift 0.4%** — which is what rules out "it did not render" as an
explanation for any of the above.

## ⛔ TWO OF THE THREE FIXES MOVED TOWARD THE TARGET. ONE MOVED AWAY.

R-HAIRVOLUME and R-HAIRSHAPE both move toward a shaggy layered cut.
**R-HAIRFACE swept the fringe off the forehead, and a fringe on the forehead is
the reference's most recognisable feature.**

It is separable and only half of it should be reversed:

- **KEEP the root half.** Roots were growing on the brow and eyelids at
  z ≤ 168.7 against a hairline at 171.68. Hair does not grow out of an eyelid
  in any haircut, and the normals there belong to sockets.
- **The styling half is what removed the fall.** `front_sweep_gain` 2.00 and
  `back_bias` 1.00 drive front-rooted strands backward over the crown. **Roots
  off the brow and tips falling forward are not in conflict** — the reference
  is exactly that.

**THE GENERAL LESSON, AND IT OUTRANKS THE HAIR:** all three were correctly
measured and correctly gated against INTERNAL metrics with no reference in the
loop. **A metric with no target in the loop can tell you that you moved, never
that you moved toward the target.**

## ⚠ THE REAR RUBRIC COULD NOT MEASURE OUR RENDER — TWICE, EXIT 0 BOTH TIMES

`RECIPES.md` **R-HAIRREAR** (new), narrative in `LESSONS.md` 2026-08-21.
**No rear number is on the board and none should be quoted.**

    level camera   crown_width_px 1322 of a 2048 frame -- that is FOREST.
                   The shadowed canopy is dark and unsaturated, so it passes
                   the mask, and it TOUCHES the head, so largest-component
                   keeps hair and forest as one blob.  edge_roughness 283.4
    sky behind     background clean, mask is a hollow RING -- the sunlit crown
                   is brighter than luma_max 70, so only the rim survives.
                   Area understated, perimeter doubled.  edge_roughness 142.8

Reference, for scale: **27.9648**.

**`mask_frac` DID NOT AND CANNOT CATCH THIS.** Its band `[0.005, 0.50]` passed
both — the forest blob was 3.2% of frame and so is a plausible head of hair.
A gate on the EXTENT of a region cannot see whether it is the RIGHT region, and
it is computed from the same mask as the metrics, so check and checked share a
source. **What caught it was `--dump-mask` and opening the PNG**, which the
tool's own docstring demands before its numbers are believed.

## ⭐ ONE INSTRUMENT WOULD CLOSE THREE OPEN ITEMS

A **flat-lit close rig against a plain background** — diffuse light on the
whole hair mass, no forest, no sun. It makes the rear rubric measurable, makes
a colour comparison meaningful, and lets the iris be read. The eye-colour item
has needed exactly this since 2026-08-19. **Recommended next unit if the
ruling below is "re-author".**

## ~~THE ONE RULING THAT DECIDES THE NEXT SESSION~~ — RULED: RE-AUTHOR

**Ryan ruled RE-AUTHOR toward the reference, 2026-08-21.** The re-author then
hit the seating defect at the top of this block before a single parameter was
changed, so the ruling stands and is BLOCKED, with two ways forward:

**(a) TAKE THE VENDOR GROOM.** `Hair_M_SideSweptFringe` already renders the
reference's shape correctly on this character today. Zero pipeline work. It
gives up per-character authored hair, which is what the custom track was for.

**(b) FIX THE SEATING.** The ladder has it cornered; the next step is a binding
the component will accept with `enable_global_interpolation` True — which
probably means a real SOURCE mesh rather than an identity one, i.e. the
advisor's 2026-08-20 named fix that has still never actually been applied.

**These are not exclusive** — (a) unblocks the hero now, (b) unblocks every
future party member.

The authored levers below are quoted with their meanings and **none was tested**
— they only matter once (b) lands, because until then Blender's shape is not
what ships:

    len_side_cm       6.5   sides stop above the ears
    len_nape_cm       4.5   with nape_frac 0.58, this is the bare nape
    len_fringe_cm     6.0   too short to reach the brow from an 0.82 hairline
    front_sweep_gain  2.00  drives the fringe BACK over the crown
    back_bias         1.00  pushes hair away from the face as it falls

**`layer_gain` is NOT one of them** — R-HAIRSHAPE REJECTED already measured it
unable to touch the fringe edge (0 → 0.70 moved it 0.694 → 0.689 cm).
**Decide the shape in Blender, 40 s a pass, one knob at a time.**

## OPEN, RANKED

1. **THE GUIDE WEIGHTING DEFECT.** The seating WORKS at `guide_every 1`, and
   that is a workaround costing 3x the curves. `Merge Guide and Weight it`
   computes guide/strand correspondence our groom's deformation cannot use at
   any subset density (20 and 4 both render bald). Repairing it is what makes
   the fix a fix.
2. **THIRD-PARTY GROOMS ARE NOT USABLE YET.** The source-mesh transfer path
   rendered bald even with the correct source read off the pack's own binding.
   Unproven, not fixed.
3. **NOW RE-AUTHOR TOWARD THE REFERENCE.** This was Ryan's ruling and it is
   finally unblocked: the Blender shape now reaches the render, so the levers
   below can be moved one at a time and judged. A cycle is ~15 s in Blender
   and ~4 min for the UE proof.
4. **`preview_hair.py` mixes raw and evaluated geometry in one report** and
   must label every number with the representation it came from. Until it
   does, its scalp/root numbers describe the PRE-stack curves and its
   silhouette numbers describe the POST-stack evaluation.
5. **The flat-lit rig** — one instrument, three items (rear rubric, colour
   comparison, iris).
6. **The eye colour is STILL UNVERIFIED and could not be measured** — the iris
   crushes to 0,0,0 at this sun angle. Reference iris (26, 20, 17). Unchanged
   this session; not attempted.
7. **The moustache clears the bar only at 0.9 m** — at the 1.1 m comparison
   framing it reads 2.1x floor and ABSENT, so every sheet here is a
   DIAGNOSTIC. Art call, not a bug.
8. **The 20 short catalogue styles** are still unsettled.
9. `MORNING_REPORT_3.md` does not carry the Stage B authoring results.
10. **`_trash/` has grown** — yesterday's sweep intermediates plus this
   session's `autosaves_launch_*`. All re-derivable; safe to delete.
11. **Test assets left on disk, all gitignored and re-derivable:**
    `Hair_v22_gi` / `BND_Hair_v22gi` (the refused-binding test),
    `Hair_vendorTest` / `BND_vendorTest` (the vendor-through-our-builder
    control), `Hair_v22_nostack` / `Hair_v22_nostack_bound` /
    `BND_v22_nostack` (the no-stack test). `Hair_v22` now carries
    `enable_global_interpolation` TRUE, which it did not before — the one
    deliberate asset edit of the session.

## ⚠ THE PREVIOUS BLOCK SAID AN EDITOR WAS RUNNING AND THERE WAS NOT ONE

Read as a reminder rather than a defect: a CURRENT STATE block describes the
world at the moment it was written, and process state is the fastest thing in
it to go stale. `bootstrap.py` answered in six seconds. **Check, do not
inherit.**

---

# CURRENT STATE — 2026-08-21 (end of session) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-TWO
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K`, viewport pointed at
the hero. **THE HERO IS NOW SAVED INTO THE LEVEL** — two external actor
packages, committed. That reverses the long-standing "never save the placement"
posture, at Ryan's request, so a fresh session opens with him already there.

## ⭐ THE HERO WEARS A BLENDER-AUTHORED GROOM: SHAPED, COLOURED, GATED

    Hair       PRESENT  18,633 px  9.1x floor  crown 83%  drift 2.8%
    Beard      PRESENT  15,327 px  7.5x        crown 11%  drift 0.6%
    Eyebrows   PRESENT   8,198 px  4.0x        crown 75%  drift 0.9%
    Mustache   ABSENT    4,088 px  2.0x        crown 41%

Mustache ABSENT at 1.7 m is the standing caveat — it clears only at 0.9 m — so
the gate calls the frame a DIAGNOSTIC, correctly.

    live assets   /Game/Characters/AlpineHero/Grooms/Hair_v22_bound_b
                  /Game/Characters/AlpineHero/Grooms/BND_Hair_v22b
                  /Game/Characters/AlpineHero/Grooms/MI_AlpineHero_CustomHair
    authored at   scripts/blender/author_hero_hair.py  (PARAMS block)
    lead render   _verify/20260821_blender/HERO_coloured2_*.png

**THREE DEFECTS CLOSED TODAY, EACH WITH A RECIPE.**

| | before | after | recipe |
|---|---|---|---|
| slicked flat | front 40,691 px, gain 1.76 cm | 63,026 px, 2.91 cm | R-HAIRVOLUME |
| hair over the eyes | 17,368 px (5.62% of strands) | 1,689 px (0.76%) | R-HAIRFACE |
| bowl shape | hairline spread 0.406 cm | 0.965 cm | R-HAIRSHAPE |
| colour | engine default | melanin 0.92 / redness 0.28 | (payload below) |

## ⛔ THE FOUR THINGS THAT WILL COST A FRESH SESSION A DAY

**1. `override_materials` NULLS THE COMPONENT'S `binding_asset`.** An unbound
groom draws nothing, so the render goes bald while the colour tool reports
success — every one of its own read-backs is correct and the material looks
guilty. Re-assert the binding AFTER any material write and CHECK it.
`custom_hair_color_payload.txt` refuses otherwise.

**2. THE FIRST BINDING ASSIGNMENT IS INTERMITTENTLY REFUSED.** Set it, read it
back, get None; call again and it sticks — sometimes the first call works.
Observed many times today across several assets. **Behaviour, not mechanism.**
The payload retries a bounded number of times and reports `binding_attempts`,
which turns it into data instead of folklore.

**3. WHEN A RENDER GOES WRONG, RE-RUN THE LAST KNOWN-GOOD CONFIGURATION BEFORE
DIAGNOSING THE NEW ONE.** v22 rendered bald, survived a fresh binding, and was
cleared by a new export validator — then v21 put back on the same component was
ALSO bald. One render separates "the change broke it" from "the session broke",
and those have disjoint fix lists. This cost a validator, two bindings and
three renders.

**4. PASS AN ABSOLUTE `--out-dir` TO EVERY CAPTURE TOOL.** A relative path
resolves against the editor's working directory, which is the ENGINE BINARIES
folder. Ten frames landed in Program Files today. `-WorkingDirectory` at launch
does NOT fix it — Unreal resets its own CWD at startup, and my first fix was
wrong; re-rendering is what caught it.

## THE LOOP, AND WHY IT IS THE WHOLE STORY

    scripts/blender/author_hero_hair.py       PARAMS; every key overridable for
                                              one run with HAIR_<KEY> in the
                                              env, effective values in the
                                              sidecar so a render traces to
                                              numbers
    scripts/blender/preview_hair.py           front/side/back + bare-head
                                              control, ~40 s
    scripts/blender/diagnose_face_hair.py     WHICH strands are over the face,
                                              by root distribution; refuses if
                                              its own control fails
    scripts/blender/validate_groom_export.py  the four properties UE consumes,
                                              ~40 s. RUN IT BEFORE AN IMPORT
    scripts/blender/build_guide_stack.py      the demo's non-baked stack

A UE round trip is ~4 minutes plus an editor; Blender answers the same shape
question in 40 seconds. **Decide the shape in Blender. The UE trip proves the
GROOM, not the haircut.**

## ⚠ SEVEN METRICS HAVE BEEN WRONG TODAY AND EVERY ONE WAS CAUGHT THE SAME WAY

An input that should have moved the number did not. That test is in
`preview_hair.py`'s docstring as a precondition for trusting a NEW metric.

**GATES:** `scalp_exposed_pct` (scalp defined by the ROOTS),
`scalp_exposed_by_zone`, the silhouette difference against the bare head, and
`diagnose_face_hair.py`'s `over_face_pct` and `hairline_profile`.
**DESCRIPTIVE ONLY:** `shell_thickness_*`, `fringe_edge_spread_cm`,
`flare_p95_ratio`, `tips_in_face_box`, `strands_crossing_face_box`.

**And measure the hairline in GEOMETRY, not in the render.** Three mechanisms
that demonstrably work moved the render-side edge statistic by nothing.

## THE ROUND TRIP, IN ORDER

    1  author            blender --background <authoring.blend> --python
                         author_hero_hair.py -- <out.abc> 48000 20260821
                         0.035 0.012 <out.blend>
    2  validate          validate_groom_export.py        <- before importing
    3  guide stack       build_guide_stack.py -- <demo.blend> <stack.abc>
    4  import            import_groom_abc_payload.txt    --timeout 25
    5  bind              fresh_bind_payload.txt          SOURCE_MESH empty
    6  colour            custom_hair_color_payload.txt   AFTER the bind
    7  place             place_hero_in_world.py --dist 170
    8  render            world_shot.py --out-dir <ABSOLUTE>
    9  gate              groom_presence.py

**`--timeout 25`, not 200.** It is a DISCOVERY window spent in full; a 220 s
value wasted four minutes per call and the import ran fine at 25.

## OPEN, RANKED

1. **The eye colour is STILL UNVERIFIED and could not be measured** at two
   framings — the iris crushes to 0,0,0 at this sun angle. Needs a lit rig.
   Reference iris (26, 20, 17).
2. **The moustache clears the bar only at 0.9 m.** Art call, not a bug, and it
   is why every 1.7 m gate returns DIAGNOSTIC rather than DELIVERABLE.
3. **The hair is not art-directed against the reference.** Three measured
   defects are gone; nobody has compared the result to
   `hero/reference/hero_example_pic.jpg` and ruled on whether it is the right
   haircut. `compare_to_reference.py` and the registered rear reference exist
   for exactly this.
4. **The 20 short catalogue styles** are still unsettled — a lit close render
   against a bright background would settle whether they render at all.
5. `MORNING_REPORT_3.md` does not carry the Stage B authoring results.
6. **`_trash/` has grown** — several sweep-intermediate directories from today
   (`hair_sweep_*`, `hair_facezone_sweep_*`, `hair_bowl_sweep_*`,
   `blend1_backups_*`, `stray_engine_writes_*`). All re-derivable; safe to
   delete when convenient.

---

# CURRENT STATE — 2026-08-21 (earlier) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY-ONE
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (the third of the
session; the first fataled in the RBF deformer, the second was force-closed to
rebuild the plugin). The hero is spawned as `HeroInWorld` in an unsaved level
wearing the **Blender-authored** hair; nothing about the level was saved.

## ⭐ THE HAIR HAS BODY, AND IT IS MEASURED IN BLENDER BEFORE IT COSTS A ROUND TRIP

              exposed%   midline%   front_px   height gain
    before       9.43       9.75      40,691       1.76 cm
    after        8.11       4.46      63,026       2.91 cm

Front silhouette **+55%**, height gain **+65%**, the crown parting halved, and
overall scalp coverage improved at the same time. Locked in `RECIPES.md`
**R-HAIRVOLUME**; narrative in `LESSONS.md` 2026-08-21.

**Gated in UE at 1.7 m, two passes, reproduced:**

    Hair       PRESENT  14,241 px  6.8x floor  crown 71%  drift 1.5%
    Beard      PRESENT  15,235 px  7.3x        crown 11%  drift 0.1%
    Eyebrows   PRESENT   7,677 px  3.7x        crown 74%  drift 0.2%
    Mustache   ABSENT    4,211 px  2.0x        crown 42%

**Mustache ABSENT at 1.7 m is the standing caveat, not a regression** — it
clears only at 0.9 m and swapping stubble for `S_Full` did not move it. The
gate therefore calls the frame a DIAGNOSTIC, correctly.

**The A/B is single-variable**: `_verify/20260821_blender/AB_v17_control_*.png`
against `AB_v19_volume_*.png`, same session, same framing, only the groom and
binding swapped. v17 is a thin band on the skull; v19 is a raised mass with a
shadowed gap beneath it.

**DO NOT WHOLE-FRAME-DIFF THOSE TWO.** It reads 11.25% changed and this
scene's repeat floor for an UNCHANGED subject is 11.3%. The forest re-renders.

## THE VOLUME NUMBER ROSE 23% AND THE RENDER DID NOT CHANGE

Both were true. Shell thickness says how far the layer sits OFF the skull and
nothing about whether the layer is THERE:

    version   over-face   tip shell   scalp exposed
    v10         20.49 %      1.214       11.54 %
    v15          1.90 %      2.627       20.55 %
    v17          2.10 %      3.235       32.12 %

Every centimetre of volume came off the scalp — outward displacement on a
convex skull spreads neighbours as r². The ramp is quadratic now.

**FOUR METRICS IN `preview_hair.py` HAVE BEEN WRONG AND ALL FOUR WERE CAUGHT
THE SAME WAY** — an input that should have moved the number did not. That test
is now in the docstring as a precondition for trusting a new metric. The gates
are `scalp_exposed_pct` (scalp defined by the ROOTS, not a second copy of the
hairline rule), `scalp_exposed_by_zone`, and the silhouette difference against
the bare head. `shell_thickness_*` is DESCRIPTIVE ONLY.

**And state the denominator:** the midline zone at |x| < 1.5 cm holds 178
samples and read non-monotonically across rising density. At 3 cm, n ≈ 2080,
it is stable.

## ⚠ FIVE MECHANISMS, EACH MEASURED, NONE OF THEM GUESSED

1. `side = sign(root.x - mid)` is a parting by construction — 29.21% midline
   exposure against 8.64% lateral. Now a ramp.
2. The mass was at the back: front 40,691 hair px against the back's 81,418.
3. The hairline counts a TEMPLE as front; the sweep did not. One physical fact
   written twice, and the brow wisps lived in the gap.
4. `out_bias` 0.85 threw two wings off the temples. Now 0.15; body comes from
   the radial drape clearance.
5. Density is the dominant lever on the parting: 26.4 → 15.17% from 26k to 40k
   strands. Shipping at 48,000.

## ⛔ THE RBF BAKE FATALS THE EDITOR ON AN IDENTITY BINDING — FIXED

    Assertion failed: RootDatas[GroupIndex].MeshPositions.IsValidIndex(MeshLODIndex)
    GroomRBFDeformer.cpp:740

Fifth MetaHuman/groom entry point to fatal this editor. `RECIPES.md`
**R-GROOMBIND4**. The deformer computes `RootDatas` itself (`:670-683`) and
`check()`s it — a hard crash, not a refusal. **And for a groom authored on the
target's own head the transfer is the identity, so the step was a no-op.** Now
guarded on `EffectiveSource != TargetMesh`, with the branch logged. Plugin
rebuilt (18 s). Crash evidence at `_verify/20260821_blender/rbf_crash/`.

**Two comments in that one function asserted opposite things** and
`fresh_bind_payload.txt` had copied the false half into its own header.

**The payload had also drifted from its UFUNCTION** — four arguments where
`LandscapeLabTools.h:639-650` declares five, three outs where there are four,
and it ignored the returned groom copy. **A payload is a call site with no
compiler.** Re-run every payload after any signature change it touches.

**Observed, mechanism NOT established:** the first call creating a new binding
path assigns null on read-back; an identical second call succeeds. Reproduced
twice on two paths. Run it twice.

## ⚠ RELATIVE `--out-dir` WRITES INTO THE ENGINE INSTALL

Ten frames, including a whole presence-gate set, landed in
`C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\_verify\` — outside
both roots, standing rule 1, twice. **Pass an ABSOLUTE `--out-dir` to every
capture tool.** Unreal sets its own working directory at startup, so
`-WorkingDirectory` at launch is inert for this and my first fix was wrong;
re-rendering is what caught it. All ten recovered; strays in
`_trash/stray_engine_writes_20260821/`; the engine install is clean, checked.

`scripts/launch_editor.ps1` exists for its OTHER job — moving
`PackageRestoreData.json` aside so the next start cannot raise a Restore modal
— and its docstring says plainly that the working directory it sets does not
survive engine startup.

## THE BLENDER LOOP, AND WHY IT IS THE WHOLE STORY

    scripts/blender/author_hero_hair.py   PARAMS; every key overridable for one
                                          run with HAIR_<KEY> in the env, and
                                          the effective values land in the
                                          sidecar so a render traces to numbers
    scripts/blender/preview_hair.py       front/side/back + the bare-head
                                          control, ~40 s
    scripts/blender/build_guide_stack.py  the demo's non-baked stack

A UE round trip is ~4 minutes plus an editor; Blender answers the same question
in 40 seconds, and the shape is decided entirely on the Blender side. **Measure
there first.**

## OPEN, RANKED

1. ~~**Hair still hangs at the brow and temples.**~~ **FIXED 2026-08-21 —
   `RECIPES.md` R-HAIRFACE.** It was never strands falling into his eyes: hair
   was GROWING on his brow, roots at z ≤ 168.7 against a hairline at 171.68,
   because both guards on that region read a surface NORMAL and a MetaHuman
   face carries eyelids and sockets there whose normals do not point forward.
   A position-based face zone fixed it. Two instruments: strand census
   5.62 → 0.76%, rendered pixels 17,368 → 1,689 (−90%), with the front
   silhouette UP 15%. Gated at 1.7 m: **Hair PRESENT 18,786 px, 9.2x floor,
   crown 85%, drift 1.2%** — and the Eyebrows number rose 7,677 → 8,294 px,
   which is the hair no longer covering them.
   **Three earlier fixes missed because I never asked WHICH strands.** The
   tell was on the board: `front_sweep_gain` 1.2 → 2.4 moved it 17,463 →
   17,362 and `len_side_cm` 6.5 → 5.0 moved it 17,378 → 17,378. Identical.
   `scripts/blender/diagnose_face_hair.py` reports the ROOT DISTRIBUTION and
   answered in one run.
   **The three UE frames ARE comparable**: `AB_v17_control`, `AB_v19_volume`
   and `AB_v21_matched`, all at capture loc (354430, −321400) rot 0.
   ~~**NEW AND OPEN:** the hair reads as a heavy bowl.~~ **FIXED 2026-08-21,
   v22.** It was TWO things. (a) The ruled line across the forehead is made of
   ROOTS, not tips — `required_z` is a hard threshold, so density stops dead.
   No length parameter can touch it: `layer_gain` 0 → 0.70 moved the edge
   0.694 → 0.689 cm. A RAISE-ONLY lateral wave breaks it (geometric hairline
   spread 0.406 → 0.965 cm) and, being raise-only, costs no over-face —
   a symmetric wave took over-face 0.74 → 4.94% by lowering the line at the
   temples, where the face zone does not reach. (b) `lift_cm` is along the
   scalp NORMAL, so it buys height on the crown and FLARE on the temple; it
   is now scaled by how upward the normal is. Gated: **Hair PRESENT 18,633 px,
   9.1x floor, crown 83%, drift 2.8%**.
   **AND THE BALD RENDER THAT FOLLOWED WAS NOT v22.** See `LESSONS.md`
   2026-08-21 — v21 put back on the same component was ALSO bald. Re-run the
   last known-good configuration before diagnosing a new one.
2. ~~**Hair colour is vendor default (blonde).**~~ **FIXED 2026-08-21.** It was
   never "vendor blonde": the Hair component's `override_materials` was EMPTY
   and it rendered on `/HairStrands/Materials/HairDefaultMaterial`, the ENGINE
   DEFAULT, while Beard/Mustache/Eyebrows each carried assembled `MI_WI_*`
   overrides at 0.92 / 0.28. Nothing had ever given the custom groom a
   material — and `groom_color.py` could not have, because it writes character
   INSTANCE parameters and a component-assigned groom never passes through the
   wardrobe. New `MI_AlpineHero_CustomHair` parented to
   `/MetaHumanCharacter/Materials/MI_Hair` (the parent a working groom uses),
   `hairMelanin` 0.92 / `hairRedness` 0.28, read back off the asset.
   `scripts/hero_face/likeness/custom_hair_color_payload.txt`.
   **ORDER IS LOAD-BEARING: writing `override_materials` NULLS the component's
   `binding_asset`**, and an unbound groom draws nothing — the render went bald
   and the material looked guilty. Re-assert the binding after the material and
   CHECK it; the payload refuses otherwise.
   **There is no `hairWhiteness` on this master** (the family is `WhiteAmount`
   / `WhiteMelinin*`) and the working vendor groom overrides none of it, so the
   ruled "whiteness 0.00" is left unset rather than written as a default that
   would read like a setting.
3. **The eye colour is STILL UNVERIFIED and could not be measured** at two
   framings — the iris crushes to 0,0,0 at this sun angle. Needs a lit rig.
   Reference iris (26, 20, 17).
4. **The moustache clears the bar only at 0.9 m.** Art call, not a bug.
5. **The 20 short catalogue styles** are still unsettled — a lit close render
   against a bright background would settle whether they render at all.
6. `MORNING_REPORT_3.md` does not yet carry the Stage B authoring results.

---

# CURRENT STATE — 2026-08-20 (overnight #2) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWENTY
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K`. Full account:
**`MORNING_REPORT_2.md`**. Advisor consult: **`ADVISOR_LOG.md`** 2026-08-19
(overnight #2).

## ⭐ THE HERO WEARS THE SHORTLIST WINNER, GATED

    Hair       WI_Hair_M_SideSweptFringe    98,751 px  80.0x floor  crown 81%
    Beard      WI_Beard_S_Full              42,859 px  34.7x        crown 16%
    Eyebrows   WI_Eyebrows_M_Dense          15,661 px  12.7x        crown 90%
    Mustache   WI_Mustache_S_Full            4,012 px   3.3x        crown 41%

**All four PRESENT and reproduced at 0.9 m — exit 0, DELIVERABLE.**
`_verify/20260820_final/hero_final_gated_*.png`,
`FINAL_vs_reference.png`, and the six-hair
`_verify/20260820_hair_shortlist/CONTACT_SHEET.png`.

## ⭐ CUSTOM GROOMS ARE UNBLOCKED — `RECIPES.md` R-GROOMBIND3

    unreal.LandscapeLabTools.build_groom_binding_for_mesh(
        source_binding, target_mesh, dest_binding_path, dest_groom_path)

**~15 s per groom, no assemble, no editor restart.** A `UFUNCTION` in
`LandscapeLabEditor` doing the MetaHuman pipeline's own four steps.

    Hair  215,647 px  139.7x floor  crown 35%  drift 0.4%   PRESENT
    every previous approach          crown  1%              SCALP-BALD

**ASSIGN BOTH RETURNED ASSETS** — the deformation is baked into the GROOM copy,
not only the binding. All four steps are load-bearing, each measured by
omission; the one that looks like housekeeping (strip decimation around the
RBF bake) is the one that put hair in the right place and almost none of it.

**Custom hair is now available to every character, hero and party alike.** The
Blender -> Alembic path in `BLENDER_HANDOFF.md` is unblocked on the UE side;
its doc still says otherwise and needs one edit.

## ⛔ THE BLOCKER AS IT STOOD BEFORE THAT, kept because its measurements stand

**Timeboxed investigation 2026-08-20 — answered. `RECIPES.md` R-GROOMBIND2.**

**THE ASSEMBLE NEVER CREATES A BINDING.** From
`MetaHumanGroomEditorPipeline.cpp` it DUPLICATES the already-built vendor
binding, retargets it, RBF-bakes the deformation into a duplicated groom, and
calls `Build()`. **`create_new_groom_binding_asset_with_path` is not the call
the pipeline uses** — that is why every binding built with it renders a bald
crown.

    GroomBindingAsset.build()  IS reflected  AND FATALS THE EDITOR
        Assertion failed: IsUnlocked() [BulkData.cpp:596]

Third MetaHuman/groom entry point to die this way after
`request_auto_rigging(blocking=True)` and `conform_to_target_meshes`. **It is
the TRANSPORT, not the API.** Retarget WITHOUT the build is not enough
(crown 1%, drift 0.2%).

**The unblock is cheap and is the recommended next step:** a `UFUNCTION` in
`LandscapeLabEditor` wrapping the nine-line recipe, running on the game thread
in the editor's own context. This project has added `UFUNCTION`s to that
plugin before (R-CREATE).

**Also settled and worth not re-deriving:** the async-compilation controls
(`Editor.AsyncGroomBindingCompilation`, `...FinishAll`) exist and work, and
are NOT the fix — with async off there is no "waiting" line and the render is
still bald.

## ⛔ THE ORIGINAL BLOCKER STATEMENT, kept because its measurements stand

**`GroomLibrary.create_new_groom_binding_asset_with_path` creates a binding
whose BUILD NEVER COMPLETES** — `LogHairStrands: Waiting for groom bindings to
be ready 0/1`, on all eight bindings built overnight, no error, no later line,
identical pixels after a four-minute hold.

    direct assignment    -> BALD CROWN, clump of strands hanging at the jaw
    minted wardrobe item -> NO HAIR AT ALL, empty Hair component
    vendor wardrobe item -> CORRECT HAIR   (its binding ships pre-built)

**Both custom-groom routes fail at that one call.** Until it is answered,
the 38 stock hairs are the only hair source for ANY character, the hero and
every future party member alike. `RECIPES.md` **R-GROOMBIND is STRUCK** — it
was locked as PROVEN on gate numbers over a picture nobody opened.

**THE FIRST QUESTION NEXT SESSION:** can a groom binding build be forced to
complete from Python? Four untried candidates in `MORNING_REPORT_2.md` §8.

## THE INSTRUMENTS GOT BETTER

- **`groom_presence.py` has a CROWN CHECK.** A hair whose binding never built
  reads PRESENT with a big number over a bald scalp. Proven both directions,
  one variable: our binding **crown 1%** (SCALP-BALD) against the assemble's
  **crown 66%** (PRESENT) — and the broken render had the LARGER pixel count.
- **`catalogue_run.py`** is resumable by construction; **`contact_sheet.py`**
  burns each verdict into its tile; **`compare_to_reference.py`** is
  character-agnostic via `characters/registry.json` and refuses the SHAPE
  target by hash.

## THE COST MODEL, MEASURED

    a hair NEVER on this character   ~12 min (wardrobe select + assemble)
    a hair that HAS been, ever       seconds (direct swap, assemble binding)

~~The full 38-hair catalogue is ~6 h and was **correctly parked**.~~
**SUPERSEDED 2026-08-20 — THE TWO-TIER COST MODEL IS GONE.** R-GROOMBIND3
binds any hair in ~15 s, so every hair costs the same and the catalogue RAN.

## ⭐ THE CATALOGUE IS BUILT — AND IT IS FIT FOR 16 STYLES OF 36

    _verify/20260820_catalogue/hair_catalogue.png     the sheet (committed)
    _verify/20260820_catalogue/CATALOGUE_REPORT.md    read this before using it
    _verify/20260820_catalogue/index.json             38 rows, gated

    38 styles in the pack   36 bound + gated PRESENT   2 NOT REACHABLE

**The two unreachable styles are a vendor fact, not a defect.** The pack ships
**38 grooms and 36 bindings**; `Hair_M_TwistedBraids` and `Hair_S_BrushCut`
have no `<name>_Binding` sibling, and R-GROOMBIND3 duplicates an already-built
binding. Recorded as `NO VENDOR BINDING`. My hair list came from the wardrobe
item names and the disk disagreed — **names come from the asset**, a fourth time.

## ⚠ ALL 36 PASSED THE GATE AND 20 OF THEM ARE A BALD HEAD

Discovered by OPENING THE SHEET, which is the step that keeps paying. The
discriminating measurement is the gate's own hair-hidden control — crown
luminance with the groom shown vs the same frame with only the groom hidden:

    Hair_M_BobCurly         7.2 -> 58.2   -51.0    reads as hair
    Hair_S_Pixie           18.6 -> 58.2   -39.6    reads as hair
    Hair_S_BuzzCut         58.0 -> 58.2    -0.2    does not read
    Hair_M_Mohawk          57.9 -> 58.2    -0.2    does not read
    Hair_S_BaldingStubble  58.2 -> 58.2     0.0    THE CONTROL

Twenty styles sit within four luminance units of the balding control.
**The gate is not wrong:** BuzzCut really changed 27,994 px, reproducibly,
above floor — two tenths of a luma unit over a large area makes tens of
thousands of "changed" pixels. PRESENT means *pixels changed where hair
should be*; it has never meant *a person can see a hairstyle*.

**AND `crown_frac` INVERTS — DO NOT RANK BY IT.** Spearman vs `changed_px` is
**-0.314**; the 20 high-crown styles carry median 57,590 px against 108,181
for the 16 low-crown ones. Real hair covers the sides too, so its crown
FRACTION falls (BobCurly 0.57, StraightBangs 0.25). A faint wash over the lit
scalp scores 0.97. **The best crown scores belong to the styles you cannot see.**

**NOT ESTABLISHED:** whether those 20 render correctly-but-subtly (a buzz cut
IS close to the scalp) or fail to render. This camera at this exposure cannot
discriminate them; claiming more would be the same error again. Settling it
needs a lit close render against a bright background, with the ruled colour
applied — the catalogue clears `override_materials`, so these are at vendor
default, not the hero's 0.92 / 0.28 / 0.00.

## ⚠ THE BIND DIRTIES VENDOR CONTENT — DISCARD ON EVERY CLOSE

`get_dirty_content_packages()` after a catalogue run returns **48 packages,
all 48 under `/MetaHumanCharacter/Optional`** — the source grooms' own
`CardsMesh`/`Helmet` LOD static meshes. `DuplicateObject` does not deep-copy
them, so the cards `PostEditChangeProperty` rebuilds them in the VENDOR
package. They are dirty in MEMORY and **clean on disk** (all 1,387 vendor
groom uassets still carry their 2026-08-15 install mtime).

Those packages live in **Program Files, outside both roots**, so a Save All
or a save-on-quit breaks the never-edit-vendor-content floor and standing
rule 1 in one action. **A force-kill writes nothing and is the correct close
here**, which inverts the usual preference. The C++ comment that claimed the
opposite has been corrected in place (non-negotiable 25).

## ⭐ THE BLENDER ROUND TRIP RUNS END TO END — EXCEPT WHERE THE HAIR LANDS

Full account: **`MORNING_REPORT_3.md`**. Advisor consult 3: `ADVISOR_LOG.md`.

    export   Blender 5.2 headless -> 81 MB .abc, NO attended click needed
    import   HairStrandsFactory (NOT GroomFactory, NOT Interchange)
    count    Blender 31,570 evaluated vs UE 31,267 -- 0.96%, independent
    bind     2.67 s, curve retention 1.0, assigns and reads back
    SEATING  WRONG. This is the blocker.

**`groom.blend` (the Fab kit) is Blender's DEFAULT STARTUP SCENE** — Camera,
Cube, Light. No hair in it at all. The demo file is the base.

**The demo `.blend` is healthy in 5.2**: 39 node groups, zero undefined nodes.
Its `head_lod0_mesh` has **24,049 verts — our MetaHuman archetype LOD0 count**,
which is why the remaining fix looks cheap.

**Two export preconditions, both failing like a broken add-on:**
`node_execution=True` (it gates `export_preparation()`, which SELECTS the
objects) and **no `--factory-startup`**. `GetCurvesObjects` reads
`context.selected_objects`, so the UI was supplying a precondition by hand.

### THE BLOCKER, AND THE CONTROL THAT LOCATED IT

R-GROOMBIND3 duplicates a vendor binding and RBF-bakes. Correct for stock
hair, structurally wrong for a custom groom. Single variable, the donor:

    Hair_L_Straight  85,107 px @ 52.6x floor, crown 10% -- clump over one eye
    Hair_S_BuzzCut   completely bald
    difference       10.3% of the frame

**The donor alone decides where a custom groom's strands land** — it carries
per-strand root correspondence belonging to the DONOR's groom. And **the gate
called the bad one PRESENT at 52.6x floor.**

### THE NAMED MORNING FIX (advisor-ruled, bounded)

Construct a **fresh** `UGroomBindingAsset` with `SourceSkeletalMesh` = the
**archetype head**, Target = the fitted face, and **drop the RBF re-bake** on
that path — `Build()` owns the deformation and baking on top deforms twice.

**PARKED at two attempts because the advisor's condition was never met.** Its
zero-rebuild diagnostic (assign with NO binding and render) came back
**completely bald — neither branch**: an unbound groom on a MetaHuman
GroomComponent draws nothing, so the test's premise does not hold here. That
is *could not look*, not a verdict.

## THE REAR REFERENCE IS REGISTERED

`hero/reference/hero_example_pic_rear.jpg`, hash-equal at adoption, declared
in `characters/registry.json`. **Frontal stays primary; the rear governs only
what the frontal cannot see.** Neither is a colour target.
Measured once by `rear_metrics.py` — **one implementation for reference AND
render**: taper_ratio **0.5533**, edge_roughness **27.9648**, width profile
0.38 → 1.00 → 0.42. Mask dumped and looked at before any number was used.

## ⚠ THE BIND DIRTIES VENDOR CONTENT — DISCARD ON EVERY CLOSE

48 dirty packages after a run, **all 48 under `/MetaHumanCharacter/Optional`**
(the source grooms' cards/helmet meshes; `DuplicateObject` does not deep-copy
them). Dirty in MEMORY, clean on disk — all 1,387 vendor uassets still carry
their 2026-08-15 install mtime. Those live in **Program Files, outside both
roots**, so a Save All or save-on-quit breaks the vendor floor and standing
rule 1 at once. **A force-kill writes nothing and is the correct close here.**

## OPEN, RANKED

1. **Custom-groom seating** — the fresh-binding route above. Everything else
   in the Blender track is proven and waiting behind it.
2. **Rule what the custom groom is FOR** before Stage B's authoring loop is
   worth its cost: reproduce the reference cut from scratch, or use the round
   trip only for what stock hair cannot do. The rear reference makes either
   judgeable, which it was not yesterday.
3. ~~**Are the 20 short styles rendering?**~~ **ANSWERED: yes.** It was the
   catalogue's single hardcoded framing; see the block above.
2. **The eye colour is STILL UNVERIFIED and I could not look.** Attempted on
   the final portrait: the eye sits in deep shadow at this sun angle and the
   darkest pixels crush to 0,0,0, so no iris value exists to compare against
   the reference (26, 20, 17). It needs a render with the eye LIT — the flat
   instrument rig, or a different sun. **Not a measurement, an absence of
   one.**
3. **The moustache still only clears the bar at 0.9 m**, and swapping stubble
   for `S_Full` did not move it (occlusion refuted by control).
4. `BLENDER_HANDOFF.md` is written and leads with the blocker. Skin Cache
   VERIFIED: `r.SkinCache.CompileShaders=True`, `DefaultEngine.ini:48`.
5. Two dozen `_trash/autosaves_coldtest_20260819/PRD_*.json` — restore data
   moved aside before each of ~10 editor restarts. Safe to delete.

---

# CURRENT STATE — 2026-08-19 (night) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries NINETEEN
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (the third of the
session; the two predecessors were force-closed with NOTHING DIRTY, dirty list
read empty first, and `PackageRestoreData.json` moved to
`_trash/autosaves_coldtest_20260819/` each time so the next launch cannot raise
a Restore modal). The hero is spawned in the unsaved level as `HeroInWorld`;
nothing was saved and no asset was written.

## ⭐ B-HAIRGROOM IS CLOSED. THE GROOMS WERE NEVER BROKEN — THEY WERE MEASURED TOO EARLY.

**A groom finishes over frames after its assets first become resident in an
editor session, and every render that said "bald" was taken before it
finished.** Cold editor, first placement, nothing changed between the readings
but the frames spent:

    groom       first reading   second reading   converged
    Hair             33,743          96,246       96,147 - 97,338
    Eyebrows          3,564          19,205       18,904 - 18,911
    Beard             9,153          13,149       12,555 - 12,809

The first reading calls Eyebrows ABSENT. It is not absent; it is not finished.
Hair is the heaviest of the four and converges last and from furthest away —
which is exactly why hair, and only hair, looked permanently broken.

**No vendor groom asset was edited and none needed to be.** The
`enable_global_interpolation` lead was correlational and the correlation is
explained: the two flagged hairs are the two heaviest grooms. `Hair_M_Layered`
renders at **83x** the repeat floor, untouched.

**The convergence is paid ONCE PER EDITOR SESSION, not per spawn** — a fresh
respawn in a warm editor converges immediately. That is why the failure looked
intermittent and asset-shaped.

## THE PRESENCE GATE NOW READS PIXELS, AND IT REFUSES

`scripts/hero_face/likeness/groom_presence.py`, recipe **R-HEROGROOM**. It
hides each groom in turn and requires the picture to change. Three fail-closed
properties, all measured:

    POSITIVE CONTROL   the face mesh, hidden through the same call in the same
                       payload: ~1,471,000 px, 1,266x floor. Without it a null
                       is "I could not look", not "absent".
    STABILITY MAP      two captures of an UNCHANGED subject differ over 11.3%
                       of the frame -- the FOREST re-renders, the hero does
                       not. Excluding those pixels took the floor
                       472,199 -> ~1,100 px.
    REPRODUCE          the measurement is taken TWICE and >30% drift is a
                       REFUSAL. Converged passes agree within 0.5-3.7%; a
                       converging one moved 185%.

**Proven in four directions in one session:** refuses a converging subject
(exit 7), passes a converged one (exit 0), reports ABSENT for a genuinely
sub-resolution groom (exit 6), and refuses when its own control cannot clear
the floor.

## ⚠ A GATE VERDICT BELONGS TO ITS FRAMING — measured, not argued

    distance   Hair   Eyebrows   Beard   Mustache   whole face
    0.9 m       83x      16x     10.6x     3.3x     1,471,218 px   ALL PASS
    1.1 m       51x       6.8x    5.6x     2.2x       817,605 px   Mustache out
    1.3 m       38x       5.6x    4.6x     2.2x       552,032 px   Mustache out
    6.2 m        2.5x     1.8x    1.9x     1.9x        10,120 px   ALL out

At 6.2 m the ENTIRE FACE is ten thousand pixels. **A landscape framing cannot
carry a groom claim — a statement about the camera, not about the hero.** The
old checklist gate returned DELIVERABLE at every one of these distances,
because the component properties are identical at all four.

## THE DELIVERABLES

    _verify/20260819_hero_grooms/
      hero_portrait_gated_20260820T030317Z.png   <- GATED, all four grooms
                                                    PRESENT and reproduced
                                                    at 0.9 m
      hero_wide_20260820T030353Z.png             landscape context
      hero_env_20260820T030418Z.png              landscape context
      gate_portrait/ gate_portrait2/ gate_wide/  the reports, per framing

The wide and environment frames are **DIAGNOSTIC with respect to grooms** and
say so with numbers rather than by assumption.

## ⭐ THE RULED GROOM SET IS ON HIM, GATED, AND COMPARED TO THE REFERENCE

Ryan ruled the set against the appearance target 2026-08-19 (night). Applied
through add -> select -> propagate, coloured on the durable surface,
re-assembled, gated in pixels.

    Hair       WI_Hair_M_SideSweptFringe   (was WI_Hair_M_Layered)
    Beard      WI_Beard_S_Full             (was WI_Beard_M_Stubble)
    Mustache   WI_Mustache_S_Full          (was WI_Mustache_M_Stubble)
    Eyebrows   WI_Eyebrows_M_Dense         unchanged, and it was the right one

    at 1.1 m   Beard   9,393 -> 25,951 px, mean|d| 29.6 -> 66.5
               Hair   84,450 -> 116,722 px
               gated at 0.9 m: all four PRESENT and reproduced, exit 0

    /Game/Hero/MHC_AlpineHero   6c5631c4 -> ad3082e2   (wardrobe + colour)
      restore point   tag pre-groom-wardrobe-20260819
      master          13ec8deb, STILL never written
      assembled       103 packages, 101 saved in the assemble's own payload

    _verify/20260819_hero_grooms/
      hero_portrait_newset_gated_20260820T033622Z.png   <- the gated deliverable
      reference_vs_render_newset.png                    <- the after
      reference_vs_render.png                           <- the before

**COLOUR CARRIED TO ALL FOUR, and neither the write nor the render could prove
it.** Twelve writes returned true with twelve UNREADABLE read-backs, and a
colour averaged over a sparse groom's difference mask measures the SKIN BETWEEN
STRANDS. The durable proof is the assembled material instances:
`MI_WI_*_Hair` declaring `hairMelanin 0.92 / hairRedness 0.28`.
**Enumerate the variants** — `MI_WI_Eyebrows_M_Dense_Hair` is a STALE instance
carrying no colour and the live one is the `None_1` variant.

**THE MOUSTACHE SWAP CHANGED NOTHING AND THE 0.9 m CAVEAT IS NOT RETIRED.**
`Mustache_S_Full` reads 3,731 px at 1.1 m against the old stubble's 3,703 px —
same footprint, same mean delta, same ABSENT verdict. The occlusion theory was
tested and refuted: against bare skin 3,739 px versus against beard 3,696 px,
ratio 1.01. The visible fullness above the lip is `Beard_S_Full` extending onto
it. **A difference gate measures MARGINAL contribution**, and the
hide-the-neighbour-first control is how that gets separated from absence.

## A HYPOTHESIS TESTED AND REFUTED — do not re-derive it

The session was briefed that groom simulation runs inside the MAIN SCENE
RENDER PASS, so a SceneCapture only shows grooms a realtime main view also
rendered. **The first differential appeared to confirm it spectacularly** —
same capture transform, viewport yaw the only difference, bald versus fully
haired. It was a CONFOUND: the arms also differed in elapsed warm-up. The
controls settle it —

    reversal: main view turned away again      grooms STILL drew
    fresh respawn, main view 180 deg away      grooms STILL drew, within 1.3%
                                               of the main-view-on numbers

**A differential is only single-variable if you MADE it single-variable.**
Elapsed time is a variable; order is a variable. `--main-view` is kept as a
knob on `place_hero_in_world.py` so the control can be repeated rather than
remembered.

## OPEN, RANKED

1. **The moustache is the limiting groom** and clears the bar only at 0.9 m —
   and swapping stubble for `Mustache_S_Full` did NOT move it (3,731 px against
   3,703 px at 1.1 m, occlusion refuted by control). It is a small groom in
   both variants. If a moustache must read at conversational distance the lever
   is not the moustache item; the beard already carries that region. Art call,
   not a bug.
2. **Eye colour is still UNVERIFIED on the assembled build.** Unchanged by this
   session. The tint is on the character and reads back; nobody has measured
   the iris in an assembled render. Reference iris is (26, 20, 17).
3. **B-FITCOHERENCE** — still no jaw-open render.
4. **Brow, -0.5705 cm, the largest residual** — unreachable frontally.
5. **`fit.fixed_ipd_px` 429.027 was calibrated at body -1.0** — harmless on the
   LOCKED character, a live trap for future parametric work.
6. `LandscapeLab.uproject` carries an uncommitted `AlembicHairImporter` entry
   that PREDATES this session (mtime 19:12, before the first launch). Committed
   here as found, attributed to the editor rather than to a script; standing
   rule 4 forbids me editing that file directly and I did not.

---

# CURRENT STATE — 2026-08-19 (day) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** The block above is the live one.

**Tree clean. NO EDITOR IS RUNNING** — closed deliberately for a machine
update and reboot; see the handoff immediately below. Full accounts:
**`MORNING_REPORT.md`** (the overnight map, 20 numbered mechanisms) and
**`ADVISOR_LOG.md`** (two consults, both load-bearing).

## ⛔ RESTART HANDOFF — 2026-08-19, machine update and reboot

**NOTHING IS IN FLIGHT. THE EDITOR IS CLOSED. THE TREE IS CLEAN.** Safe to
update and reboot.

    editor        closed (CloseMainWindow, then forced after 120 s with
                  NOTHING DIRTY — dirty package list read empty first)
    restore data  PackageRestoreData.json moved to
                  _trash/autosaves_handoff_20260819/ so the next launch
                  CANNOT raise a Restore modal, which would block the only
                  channel that could report it
    on disk       working character 6c5631c4, master 13ec8deb, tree clean

**THE HERO IN THE WORLD WAS NEVER SAVED INTO THE LEVEL, DELIBERATELY.** The
placement is a spawned actor in an unsaved level; the RENDER is the artefact.
Re-placing costs one payload run (`place_hero2` pattern, in the scratchpad and
described in R-HEROWHOLERIG).

### FIRST THINGS AFTER THE REBOOT, IN ORDER

1. **Launch the editor on `/Game/Alpine8K` and let it sit** before any render
   work. Virtual textures need a WARMED session: 300 warm-up captures in a
   fresh editor still produced mip-tile patchwork, and a second pass in the
   same session resolved it.
2. **Re-measure the noise floor.** A floor belongs to its editor session, and
   after a machine update it also belongs to a possibly-new GPU driver. The
   homogeneity gate will refuse a cold session — that is correct; raise
   `--settle` rather than lowering the bar.
3. **Rebuild the capture stage** (`build_capture_stage.py`). It re-searches
   the framing and has come back BIT-IDENTICAL across every restart so far
   (distance 84.087153) — check that it still does, because every cm figure in
   the records depends on it.

### WHAT A DRIVER UPDATE COULD MOVE, AND HOW TO TELL

The renders are the ruler here. If the GPU driver changes, re-measure before
comparing anything to a number recorded today:

- **the noise floor** (was 0.0442 cm this session, 0.0698 / 0.0463 / 0.0559 on
  others — it moves ~1.5x between measurements at n=4 anyway)
- **the body silhouette baseline** — `body_silhouette.py --label postreboot`
  against `_verify/hero_likeness/body/body_measures.json`, which holds the
  pre-reboot table
- **the locked face** — one settled capture measured against residual
  0.1633 cm. Anything outside floor after a reboot is the INSTRUMENT, not the
  hero, until proven otherwise.

### THE ONE THING THAT WOULD BE EXPENSIVE TO LOSE

`Content/Hero/Unpacked/` (83 packages, 299 MB) and the three scratch
characters are all GITIGNORED and re-derivable — deliberately, with the
reasoning written at each ignore line. **Everything not re-derivable is
committed or hashed into `_trash/hero_likeness_backups/`**, most importantly
`20260819T132919Z_PRELOCK/` (the pre-lock working character + canonical DNA +
the shape chain, with SHA256.txt).

## ⭐ THE LOCK IS DONE. THE HERO IS LOCKED, FITTED, MASCULINE, AND IN THE WORLD.

    /Game/Hero/MHC_AlpineHero
      78f8c8d2  ->  bc75ff72   body Masculine/Feminine -1.0 -> -2.0
                ->  a31981e2   whole-rig import + shape chain 7c3a0dc6
                ->  6c5631c4   iris tint 0.13/0.11/0.10, saturation 0.35
      backup    _trash/hero_likeness_backups/20260819T132919Z_PRELOCK/ (hashed)
      master    13ec8deb  NEVER WRITTEN, all night and all day

    THE CHAIN REPLAYED ONTO A DIFFERENT ASSET AND LANDED ON THE SAME FACE
      working character  residual 0.1633 cm      scratch2 (fitted)  0.1668 cm
      floor 0.0442 cm; per region within floor on all four

**All six lock gates met**, including the disk-restore undo proven at 0.0007 cm
and the identity arm on its re-specified form at 0.72x floor.

## THE IDENTITY ARM IS RE-SPECIFIED, AND THE OLD FORM COULD NOT PASS

On a body-modified character "the render is unchanged across the import" is
**false by mechanism** — the parametric render carries body-authored face state
and an exact DNA application discards it. Measured: pre-import jaw 14.5891 /
ipd 444.75, post-import 12.4971 / 427.41, **11.18x floor, REFUSED**.

    PRIMARY    import twice, compare -> inside floor    MEASURED 0.72x  PASS
    SECONDARY  post-import matches the whole-rig-canonical table at the
               SAME body setting
    ADVISORY   pre-vs-post delta, RECORDED not gated

**A gate that can never pass on a class of input is not guarding that class, it
is blind to it.**

## THE BODY: DIAGNOSED, AND IT WAS A VALUE NOT A MECHANISM

All four characters sat at `Masculine/Feminine` **-1.0**, including the master.
**The -2.0 recorded on 2026-08-16 was never applied** — that session's own note
(a +-2.0 swing producing byte-identical bounds) is the signature of a write
that never landed, and the mutate-a-copy trap is the mechanism.

    body drives the PARAMETRIC face   -1.0 -> -2.0 moves jaw +0.468 cm (10.6x floor)
    body does NOT drive the IMPORTED face  same comparison inside 1.2x floor

So **body work before the lock changes the face; body work after does not.**
And the advertised **permanent body-type lock does not exist** — the scratch
edits its body identically after three whole-rig imports.

New instrument: **`scripts/hero_body/body_silhouette.py`**, orthographic
(0.253906 cm/px, locked), difference-mask silhouette, bone-anchored heights,
settle-gated. It was wrong four times before it was right and every fix is in
R-HEROBODY REJECTED.

## THE HERO IS IN THE WORLD

    _verify/20260819_hero_in_world/hero_wide_20260819T141324Z_b.png   <- lead
    hero_portrait_..._b.png   hero_env_..._b.png

Assembled from the LOCKED character, ground-clamped to z 31019.47, 256 proxies,
facing camera, body visibly masculine.

## ⚠ THE PRESENCE GATE PASSED AND THE PIXELS DISAGREE

The gate asserts component state — groom asset + binding + `visible` — and
returned `ships_as DELIVERABLE`, while the close portrait shows **no beard, no
moustache, no brows**. The bindings are the durable assembled ones, so this is
not staleness. **The gate is the failure:** *settling cannot see absence*
became *a checklist cannot see absence either* once the checklist read
properties instead of pixels. Correct form is a hidden/shown difference render.
**Until that exists, landscape renders ship as DIAGNOSTIC with respect to
grooms.**

## OPEN, RANKED

1. **Grooms do not draw in-world.** Build the difference-render presence gate,
   then decide whether the beard shares B-HAIRGROOM's cause or is sub-pixel
   stubble in shadow. The test comes before the theory.
2. **Eye colour is UNVERIFIED on the assembled build.** The tint is on the
   character (0.13/0.11/0.10, sat 0.35) and reads back, but the earlier finding
   stands: asset-level eye settings did NOT reach the PREVIEW. Nobody has
   measured the iris in an assembled render; the reference iris is (26, 20, 17).
3. **B-FITCOHERENCE** — still no jaw-open render. The DNA's teeth are untouched
   by construction while the chin moved 0.372 cm.
4. **Brow, -0.5705 cm, the largest residual** — unreachable frontally, ruled to
   the second-camera/profile-reference extension.
5. **`fit.fixed_ipd_px` 429.027 was calibrated at body -1.0** and a parametric
   body -2.0 renders ~444. `fit_face.py` still scales render measures by it;
   harmless on the LOCKED character (which renders 427), a live trap for future
   parametric work.
6. Virtual textures need a warmed session — 300 warm-up captures in a FRESH
   editor still rendered mip-tile patchwork; a second pass in the same session
   resolved it.


---

# CURRENT STATE — 2026-08-19 (overnight) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries SEVENTEEN
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (the fifth of the
night — four predecessors were force-closed or fataled, each one explained
below). **`MHC_AlpineHero` and `MHC_AlpineHero_Master` were NEVER WRITTEN**
and are byte-identical to their backups (`78f8c8d2…`, `13ec8deb…`).
Full night's account: **`MORNING_REPORT.md`**. Advisor consult:
**`ADVISOR_LOG.md`**.

## ⭐ THE ROUTE IS RULED, AND THE LOCK IS HELD ONE STEP SHORT

**Route: `import_whole_rig=True` (exact application), decided by decisive test
PASS on scratch (2026-08-19, commit `7401edf9` and its two predecessors).
The parametric fit path is RETIRED FOR AUTHORING** — measured 10x command
amplification and 4x reproducibility degradation at edited states; do not
resume gain calibration on it. **The fit is retained as VERIFIER only**
(0.07 cm reproducibility on held states). **Working-character lock pending
Ryan's ratification** — see THE ONE RULING below.

    state                                          floor p90    spread   gate
    whole-rig, UNEDITED canonical DNA               0.0837 cm    3.82    passes
    whole-rig, depth 1 (chin -2.00 cm)              0.0559 cm    1.97    passes
    whole-rig, depth 2 (+ jaw)                      0.0942 cm    2.85    passes
    FIT PATH at cumulative 0.3..0.7 cm              0.27   cm    5.52    REFUSED

    identity: every named measure within 0.005 cm of the parametric face

## THE SHAPE IS FITTED ON THE SCRATCH — 89% CLOSED

    iter 1  1.8308 cm  (overshot)   iter 4  0.4122
    iter 2  0.7260                  iter 5  0.1668   <- all four in deadband
    iter 3  0.5245

Chain, boxes, deltas, final DNA hash `7c3a0dc6…`:
`_verify/hero_likeness/shape_chain_converged.json`. **It replays onto the
working character in minutes** — the edits are deterministic bytes and one
regenerated DNA came out byte-identical to a previous session's.

**THE METRIC CONVERGING IS NOT THE LIKENESS CONVERGING.** `brow_height`
finishes at **−0.5730 cm**, the largest residual on the board, unaddressable
frontally (its landmark is in the eye band, which is the ruler). The face is
coherent and still smooth, young and round-ish against a weathered 40s
reference.

## THE HERO IS IN THE WORLD, AND WHICH HERO MATTERS

    _verify/20260819_hero_in_world/hero_wide_20260819T065430Z_b.png   <- lead
    hero_portrait_…_b.png   hero_env_…_b.png
    hero_wide_20260819T064951Z.png   <- kept as EVIDENCE of the VT failure

`MHC_AlpineHero_Scratch2`, assembled OPTIMIZED/HIGH, spawned in Alpine8K at
(354600, −321400), ground-clamped by trace to z 31019.47 with 256 proxies
resident, **head 160.6 cm above root** (collapsed reads ~6). Body + Face
present; Hair/Eyebrows/Mustache/Beard components resolve their assets.
**Not settled** — two captures 60 frames apart still differ over 17–23% of
pixels — and he is in default undergarments, bald, with no beard reading at
distance.

## THE TRAPS THIS NIGHT BOUGHT — the full list is MORNING_REPORT.md

1. **`reload_packages` (`--restore`) FATALS THIS EDITOR**, twice, address
   0x470 — once on a whole-rig character and once on the **master**, which had
   never taken one. **Whole-rig is NOT the discriminating variable.**
   `sanctioned_import.py --restore` now REFUSES by default (proven in three
   directions) with `--force` as the escape.
2. **THE UNDO IS A CLOSED-EDITOR DISK RESTORE, AND IT IS PROVEN:**
   converged 0.1668 → damaged 1.2531 → restored **0.1661 cm**. Bytes are not
   the proof; the re-render is.
3. **`compare_face_state` IS USELESS ON A WHOLE-RIG CHARACTER.** Its "gold
   data" is character 2 (`MetaHumanCharacterEditorSubsystem.cpp:2567`), so
   the Error on every import is OUR OWN call, and the value is a CONSTANT
   18.1982937 at vertex 7 across four different edits.
4. **THE ASSEMBLE AND ITS SAVE ARE ONE PAYLOAD.** The editor stopped
   answering remote execution immediately after `build_meta_human` TWICE
   (one core spinning, working set flat, zero log growth); the first time it
   took 91 unsaved packages with it. **Assemble and render belong in
   different editor sessions.**
5. **VIRTUAL TEXTURES NEED FRAMES, NOT FLAGS** — 300 warm-up captures, and
   still converging.
6. **UE struct Arrays iterate as COPIES.** A body-parameter write looked
   exactly like the advertised body lock until a positive control was put in
   the same run. **The lock has never been observed on any readable surface.**
7. **Delivery is direction-, amplitude- AND mask-dependent, and the regions
   are COUPLED.** One gain per region is not enough; a mask that misses its
   landmark reads as a region that resists.
8. **The MetaHuman Blueprint's forward axis is not +X** — a look-at yaw
   photographs his profile; apply −90.

## OPEN, STATED PLAINLY

- **B-FITCOHERENCE is UNTOUCHED.** No jaw-open render exists. The DNA's teeth
  mesh is untouched by construction while the chin moved, so the question is
  real.
- **EYE COLOUR FAILED.** The asset property took and read back
  (`global_tint` 1.0 → 0.15/0.13/0.12, saturation 1.7 → 0.4) and
  `commit_eyes_settings` ran, but the iris measured (212.9, 137.8, 34.0)
  against (213.9, 139.4, 34.3) before — unchanged. Reference iris is
  **(26, 20, 17)**. The durable surface for eyes is NOT the one found.
- **B-HAIRGROOM unchanged**, not attempted tonight.
- **6 of 89 assembled packages refused to save** (`T_PreBakedGroom_*`).
- The scratch characters and `Content/Hero/Unpacked/` are gitignored with
  their reasoning at the ignore line; both are re-derivable in one call.

## THE ONE RULING THAT UNBLOCKS EVERYTHING

**Ratify the ratio bar as per-(region × mask) and authorise the lock, or
decline it.** The advisor held it because the operator's stated criterion —
"second ratio matches the first (~1.0)" — measured 0.70, and re-reading a bar
is not the night's call to make. The evidence now says the miss was the mask
(the same mask delivers 0.58 with no chaining at all). Gates 1–3 of the
minimum set are met: the disk-restore undo is proven on this asset class,
backups are hash-recorded at `_trash/hero_likeness_backups/20260819T052015Z/`,
and the gold-data error is explained.


---

# CURRENT STATE — 2026-08-18 — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries SIXTEEN
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (PID 27796, 14.8 GB,
5.6 GB free — restart it before anything heavy). **The character is at
CANONICAL** and `fit.cumulative_cm` is zeroed to match; nothing dirty,
nothing saved, `MHC_AlpineHero` byte-identical to its committed state.

## ⭐ THE LIKENESS PIPELINE IS BUILT, MEASURED, AND HAS A MEASURED CEILING

A full measure → edit → render → re-measure → correct loop exists and works.
It is an excellent **VERIFIER** and a poor **AUTHOR**, and the reason is
measured rather than felt.

    tools    scripts/hero_face/likeness/
      build_capture_stage.py  frames the camera ONCE by search, then locks it
      capture_shot.py         every picture; --noise-floor with settle +
                              fail-closed homogeneity gate
      use_preview_mesh.py     stage -> transient preview face mesh
      sanctioned_import.py    import_from_face_dna + --identity + --restore
      edit_dna_geometry.py    feathered region edit in the DNA's own space
      face_coeffs.py          the 1397-float parametric vector
      apply_grooms.py         wardrobe selection, slot names read from asset
      groom_color.py          durable instance parameters, not the material
      fit_face.py             the loop
      manifest.json           ONE declaration: camera, floor, regions, gains,
                              grooms, presence, cumulative

    recipes  R-HEROCAP (camera)      R-HEROIMPORT (sanctioned round trip)
             R-HEROGEOM (the edit)   R-HEROFIT (the loop)
             R-HERODNA  (the CLOSED UpdateJoints route)

### THE CEILING, AND IT IS THE HEADLINE

    state                              floor p90   spread   gate
    edited (cumulative 0.3..0.7 cm)     0.27 cm     5.52    REFUSED
    canonical                           0.0698 cm   3.10    passes

Two captures of the **UNCHANGED** character differ by 0.27 cm once edits
accumulate, and 0.07 cm at canonical. **The rig did not change; the state
did.** `FitToFaceDna` re-solves the whole parametric state on every import,
so a 0.150 cm command moved the render 1.526 cm (ratio 10.2). The loop is not
failing to hit a reachable target — it is chasing one that moves by more than
the 0.15 cm deadband. **No gain, damping or step policy fixes this.**

**DO NOT RESUME GAIN CALIBRATION EXPECTING CONVERGENCE.** The ceiling is the
fit's stability under accumulated geometry edits.

## THE RULINGS IN FORCE — decided, some unbuilt

- **Pass 1 is GEOMETRY-FIRST.** Joints-first is dead by measurement on BOTH
  routes, for two different reasons: a Y/Z coordinate mismatch through
  `UpdateJoints` (identity failed by 164 cm on all three readers) and *the
  fitter never reads neutral joints* through the sanctioned path (1.26x
  against an unedited DNA's 1.13x). Neutral-joint writes are OUT.
- **`import_whole_rig=False`, body stays parametric.** The reflected
  docstring claiming "neck alignment only" is FALSE
  (`MetaHumanCharacterEditorSubsystem.cpp:6647-6656`). Escalation criterion:
  a measured plateau on the CURRENT objective, or an authored DNA that
  renders closer through direct geometry than through the fit.
- **Ratio fitting is DEMOTED to a regression guard.** Seven scalars cannot
  express a contour. Successor objective ruled but UNBUILT: the face-oval
  contour, radially compared, weighted down where hair occludes.
- **Image-space losses REJECTED as drivers** — dominated by hair, stubble and
  lighting, so an optimiser would push geometry to fake grooming.
- **Depth is hand-authored from art direction, measured on a SECOND locked
  azimuth.** UNBUILT. Profile synthesis rejected: the reference is a
  generated portrait, not a photo of someone who has a profile.
- **The road correction: an ATTENDED MetaHuman Creator session as AUTHOR**,
  this loop as VERIFIER. Consider a preset blend — the base head is round,
  young and short-faced and every iteration fights that prior with
  sub-centimetre deltas.
- **Return rank:** grooms > skin/eyes > presentation lighting > geometry >
  second view. **Execution order is geometry-first-then-FREEZE.**

## THE TRAPS THAT WILL COST A DAY

1. **TWO REFERENCES, NOT INTERCHANGEABLE.** `hero_face_bald_frontal.jpg` is
   the SHAPE target; `hero_example_pic.jpg` is APPEARANCE only. Measured cost
   of confusing them: jaw +0.570 cm, chin −0.514, cheek +0.202 — about
   **1.29 cm of a 2.616 cm residual was BEARD**, and the fit widened the jaw
   to match stubble. The rule was already in the manifest, forty lines above
   the field that broke it.
2. **SETTLING CANNOT SEE ABSENCE.** The reproduce-gate proves a frame is
   STABLE, not COMPLETE — two frames agreeing on a MISSING element pass every
   statistical check. Hair was absent from every capture for a session with
   all gates green. `capture.presence` names what must render; absence is a
   NAMED failure.
3. **A WRITE THAT LANDS ON TRANSIENT STATE IS A WIN FOR EXACTLY ONE RENDER.**
   The preview materials and the groom bindings are recreated by every
   `assemble_for_preview`. The durable groom surface is the INSTANCE
   PARAMETERS.
4. **DO NOT NORMALISE THE RENDER BY ITS OWN IPD.** The camera is locked at
   fixed distance, so render pixels are absolute at 0.01745 cm/px.
   Normalising made the ruler a function of the thing being edited and caused
   every oscillation. `fit.fixed_ipd_px` = 429.027.
5. **A NOISE FLOOR BELONGS TO ITS EDITOR SESSION** — measured 0.00758,
   0.00835, 0.01044, 0.00933 IPD across sessions on the same rig.
6. **NAMES COME FROM THE ASSET**, never convention — slot names, parameter
   names, material names. A wrong name that creates a valid-but-unworn state
   is indistinguishable from the bugs being hunted.
7. **`unreal.Rotator(ROLL, PITCH, YAW)`** recurred a THIRD time here. Assert
   the read-back; do not rely on remembering.
8. **Background tasks are being killed** in this environment after a few
   minutes. Run long loops as single foreground iterations.

## SAFETY EQUIPMENT, PERMANENT

    /Game/Hero/MHC_AlpineHero_Master     duplicate, NEVER imported into
    hero/dna/MHC_AlpineHero_Head.dna     canonical, never edited in place
    _trash/hero_likeness_backups/<UTC>/  uasset copies, hash-proven

**RESTORE IS `reload_packages(..., ASSUME_POSITIVE)`, NOT a re-import.**
Never INTERACTIVE — a modal blocks the game thread, the only channel that
could report it.

## OPEN, WITH DECISIONS ALREADY MADE

- **B-HAIRGROOM** — hair selected, coloured, component present, bindings
  fresh, and it draws nothing. Elimination list is complete: not selection,
  component, assets, capture path, async build, parameter surface,
  asset-specific, binding staleness, or binding configuration. Live lead:
  `enable_global_interpolation` True on both failing hairs, False on the
  working beard — a correlation over five assets, not a mechanism. **On the
  SIGN-OFF gate.**
- **B-FITCOHERENCE** — do teeth and eyes track a reshaped jaw? The frontal
  neutral render cannot answer it. Gate: **hero sign-off**, instrument a
  jaw-open render. **On the SIGN-OFF gate.**
- **The grooms render 3 of 4** — brows, stubble, moustache in near-black
  (Melanin 0.92 / Redness 0.28). Hair does not.
- **`brow_height` and `nose_bridge` are UNADDRESSABLE** frontally — their
  landmarks sit in the eye band, which is the ruler.
- The three `plans/RECIPES_draft_*.md`, rock collision, and PHASE2 Phase C
  are all untouched by this work.

## NEXT, RANKED

1. **Ryan's call on the attended session or a preset blend.** The evidence
   for it is now measured, not argued.
2. **Skin/age and iris colour** — the reference is a weathered 40s man with
   near-black eyes; ours is smooth and amber. Iris is one parameter. Cheap,
   and it does not touch geometry so the ceiling does not apply.
3. **A presentation lighting rig, SEPARATE from the instrument.** The
   reference's brow shelf is substantially a shadow, and R-HEROCAP's flat
   25,000 lux rig cannot produce it. The instrument stays locked.
4. **Then** the contour objective and the second azimuth, if geometry is
   revisited.

---

# CURRENT STATE — 2026-08-17 (night) — **SUPERSEDED by the block above.**

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (node `04E41B58…`,
the fifth of the session — each restart was a plugin rebuild). Nothing dirty,
nothing saved, character restored to its on-disk state.

## ⭐ THE HERO'S FACE MOVES ON COMMAND, AND THE GAIN IS MEASURED

The likeness pipeline is closed end to end: edit DNA geometry → sanctioned
import → preview assemble → locked-camera render → landmark delta.
Recipes **R-HEROCAP** (camera), **R-HEROIMPORT** (round trip), **R-HEROGEOM**
(the edit); **R-HERODNA** records the route that was CLOSED.

    EDIT    1,661 of 24,049 vertices of head_lod0_mesh, -2.00 cm in DNA Y
    RENDER  7.09x the session noise floor, both settles clean

    chin    1.299 cm    cheek_L 0.509    forehead    0.085
    jaw_L   0.894       nasion  0.344    nose_tip    0.050
    jaw_R   0.794       mouth   0.128    eye_inner_L 0.039
                                         FLOOR       0.083

    CHIN -1.299 cm against a commanded -2.00 cm  ->  ATTENUATION 0.650

**0.650 is the first gain-table entry.** The negative control is inside the
same measurement: forehead, nose and eye sit at or below the floor and the
falloff is monotone from the chin outward, so the edit is regional and not a
rescale.

## ⚠ AN EPIC DOCSTRING IS WRONG, AND BELIEVING IT COSTS A PERMANENT DECISION

`ImportFromDNAParams.import_whole_rig` documents that when unchecked *"the
head DNA file will only be used for neck alignment"*. **FALSE.**
`MetaHumanCharacterEditorSubsystem.cpp:6647-6656`: the false branch calls the
SAME `FitToFaceDna` as the whole-rig branch and then `CommitFaceState`, and
`FitToFaceDna` (`:6504-6520`) calls `FaceState->FitToFaceDna(...)` then
`ApplyFaceState` — a genuine parametric face fit. What `import_whole_rig`
adds is `CommitFaceDNA`, which is what makes the body type **fixed and
non-editable, permanently, per asset.**

Believing the docstring means concluding face-only import does nothing and
accepting the lock to get any effect at all. **A five-minute source check is
what saved this hero's editable body**, and the next person to read that
docstring will not automatically make the same check. Worth reporting to
Epic; recorded here because this file is read before that one.

## THE LOOP, AND WHAT EACH PIECE REFUSES

    edit_dna_geometry.py     region box in the DNA's OWN space; self-verifies
                             SELECTED and UNTOUCHED vertices; 5 refusals
                             proven live
    sanctioned_import.py     import_whole_rig=False; --identity arm;
                             --restore; captures must REPRODUCE (exit 9)
    use_preview_mesh.py      stage -> transient preview Face mesh, re-pointed
                             after every assemble
    capture_shot.py          locked transform read back; --noise-floor with
                             --settle and a fail-closed homogeneity gate
    build_capture_stage.py   frames ONCE by search, then never re-derives

**THE DNA IS Y-UP AND UE IS Z-UP.** The file declares it:
`format 2.5; axes X=Left Y=Up Z=Front; cm`. `head_lod0_mesh` spans
X ±19.034, Y 140.878..178.439, Z −11.616..14.988; teeth Y 156.5..162.1; eyes
Y 165.6..168.5. The jaw is LOW Y. Nothing converts — work in the declared
space and use `--flag=value` so argparse does not eat a negative coordinate.

## THE THINGS THAT WILL COST THE NEXT SESSION A DAY

1. **A CAPTURE IS NOT A MEASUREMENT UNTIL IT REPRODUCES.** A freshly reloaded
   character renders a FACETED, UNRESOLVED preview — pointed crown, polygonal
   facets, asymmetric mouth — that resolves after further assembles. A single
   post-restore baseline read **7.50x the floor** and was one sentence from
   being recorded as "importing the unedited canonical DNA changes the face".
   Both good arms rejected an unresolved first baseline (7.66x, 7.73x) before
   settling. The frames caught this; no statistic could have.
2. **A NOISE FLOOR BELONGS TO ITS EDITOR SESSION.** Measured 0.00758, 0.00835
   and 0.01114 IPD across three sessions with the same stage, script and
   subject. Re-measure per session; judge every arm against its own.
3. **A HARD BOX LEAVES A SEAM.** The jaw edit shows vertical streaks on the
   chin — uniform delta, hard cutoff. `FDNACalibSetVertexPositionsCommand`
   takes a per-vertex MASK; a box is a selection, not a brush. **The next
   edit uses a mask.**
4. **NEUTRAL-JOINT WRITES ARE OUT OF THE PIPELINE**, ruled 2026-08-17, dead by
   measurement on both routes for two different reasons: a Y/Z coordinate
   mismatch through `UpdateJoints` (identity round trip failed 164 cm on all
   three readers) and *the fitter never reads them* through the sanctioned
   path (1.26x against an unedited DNA's 1.13x).
5. **`assemble_for_preview` is deterministic** — a floor cycled through it
   reads 0.00835 against 0.00919 without.

## SAFETY EQUIPMENT, PERMANENT

    /Game/Hero/MHC_AlpineHero_Master     duplicate, NEVER imported into,
                                         compare_face_state vs working TRUE
                                         at 0.001 when made
    hero/dna/MHC_AlpineHero_Head.dna     canonical, never edited in place
    _trash/hero_likeness_backups/<UTC>/  uasset copies, hash-proven

**RESTORE IS `reload_packages(..., ASSUME_POSITIVE)`, NOT A RE-IMPORT.**
Re-importing the canonical DNA is not an undo. Never INTERACTIVE — a modal
blocks the game thread, the only channel that could report it.

## OPEN, STATED PLAINLY

- **No likeness fit has run.** One region, one axis, one gain number. The
  reference-vs-render delta table that drives an actual fit does not exist.
- **B-FITCOHERENCE (BACKLOG):** whether the fit moves teeth and eyes
  coherently when jaw vertices move. The frontal neutral render CANNOT answer
  it — the teeth are hidden — and the overlap is real: the edit band
  Y 148..158 reaches the bottom of `teeth_lod0_mesh` at Y 156.5. **No gating
  condition was ever specified**, confirmed with Ryan.
- **Only LOD0 is edited.** The DNA carries 8 head LODs; the fit reads LOD0
  and the other seven are deliberately untouched.
- **The body stays parametric** (`import_whole_rig=False`). Escalation
  criterion ruled by Ryan: if a region PLATEAUS — residual stops improving
  while gains climb across 2+ iterations — whole-rig import on the WORKING
  character becomes a live option, master stays parametric. **No plateau has
  been measured.**
- **`compare_face_state`'s tolerance is NOT a distance** — "vector norm" over
  vertices AND normals. It reads NOT-within-1.0 on a face whose render moved
  0.043 cm.
- The hero in `/Game/MetaHumans/` is still the working build; nothing in this
  work has been assembled into it.

## NEXT, RANKED

1. **Mask the edit** (`SetMasks`) so a region has a falloff instead of a
   seam. Cheap, and it precedes any real gain calibration.
2. **Build the reference-vs-render delta table** — `capture_landmarks.py`
   already measures both sides; nothing yet subtracts them per region.
3. **Calibrate gains per region** against the 0.650 seed.
4. Rock collision, PHASE2 Phase C, and the rest of the world work, untouched
   by any of this.

---

# CURRENT STATE — 2026-08-17 — **SUPERSEDED by the block above.**

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (node `8B3EDC7D…`,
the fifth of the run — four restarts were required and each one is explained
below). Nothing dirty, nothing in flight.

## ⭐ UNIT 8 IS BUILT: THE NAVMESH EXISTS AND A POINT PROJECTS ONTO IT

`PHASE2_PLAN.md` Phase C opens. Recipe **R-NAVBUILD**; schema **v1.24**;
narrative in LESSONS 2026-08-17.

    wall clock      30.0 s   (commandlet execution 20.18 s)     bar 30 min
    peak commit     19.6 GB  of a 223.4 GB limit                bar 200 GB
    min free RAM    16.5 GB

    RecastNavMesh actor        9563.4 KB
    NavDataChunkActor 3_-4     9526.6 KB   <- the cell with the volume
    NavDataChunkActor 3_-3 / 2_-4 / 2_-3   76.7 / 74.0 / 4.2 KB

**BOTH ABORT BARS PASSED BY A WIDE MARGIN** — 0.5 min against 30, and 19.6 GB
against 200.

**VERIFIED BY QUERY, AND IT AGREED WITH SOMETHING IT WAS NOT FITTED TO:**

    PlayerStart          (354600, -321400, 31139.5)
    projects to navmesh  (354600.0, -321400.0, 31020.1)   difference 119 cm
    character.json       spawn.height_above_ground_cm = 120

Two numbers from completely different routes — a Recast voxelisation of
collision, and a value typed into a recipe weeks ago — agreeing to **1 cm**.

    inside  the declared cell   25/25 project, z 25604..36465
    outside the declared cell    0/4 project        <- NEGATIVE CONTROL

## THE THINGS THAT WILL COST THE NEXT SESSION A DAY IF NOBODY READS THEM

1. **THE SAVE IS PART OF THE PROCEDURE, AND THIS IS THE SECOND SUBSYSTEM IN
   SIX HOURS.** The first build produced a navmesh that was REMOVED while it
   ran, logging `NavData RegistrationFailed_AgentNotValid ... will be removed.
   This warning will disapear once the map is saved` **166 times** — while the
   editor read the correct values throughout. `SetConfig` corrects the navmesh
   actor in MEMORY at load and does **not dirty the package**, so
   `save_dirty_packages` writes nothing and the headless commandlet loads the
   stale value off disk. Identical in shape to unit 6's foliage collision.
   **An engine message saying "this will disappear once the map is saved"
   means the disk and the session disagree RIGHT NOW.** Force-save with
   `only_dirty=False`.
2. **THE COMMANDLET'S EXIT CODE MEANS NOTHING HERE.** It exits **1 on both
   the broken and the healthy run**, because the one "error" is
   `HttpListener unable to bind to 127.0.0.1:8000` — the IncrediBuild port
   conflict this file already records. Warnings fell 166 → 2 between runs and
   the exit code did not move. Judge on the log's warning summary and a
   projection query.
3. **THE AGENT DOES NOT COME FROM THE NAVMESH.**
   `NavigationSystem.cpp:2874-2875` / `:4729` call
   `SetConfig(SupportedAgents[0])`, which overwrites `AgentRadius` /
   `AgentHeight`. Setting them on `ARecastNavMesh` gave a CDO reading 34/176
   and an ACTOR reading 35/144 with every other value correct. They belong in
   `+SupportedAgents`. `AgentMaxSlope` is not part of `FNavDataConfig` and
   correctly stays on the navmesh, DERIVED from `MOVEMENT_PROFILES`.
4. **`TileSizeUU` and `AgentMaxSlope` set on the ACTOR are reverted** by
   `ARecastNavMesh::PostLoad` (`RecastNavMesh.cpp:963-1015`) when the voxel
   cache is on. Config only — it moves the CDO too, so the comparison is your
   value against your value.
5. **A COVERAGE NUMBER IS A PROPERTY OF THE QUERY.** The first verification
   read 7/25 inside the cell, which looks like a navmesh full of holes. It was
   a ±20 m query tolerance against 143 m of relief; ±120 m reads **25/25 on
   the same navmesh.**

## WHAT THE CONFIG CHANGE BOUGHT

The standing **1.89× navmesh tile overflow** is now a `prove_gates` REFUSAL,
not a note — and it was never reachable before, because there were zero bounds
volumes and therefore no navmesh grid at all. At `TileSizeUU` 1600 and 1.5
layers a WORLD-SIZED volume needs **388,622 tiles** against the 1,048,576 hard
limit, where the engine defaults needed ~1.99M and the engine would have
logged an error and **silently CLAMPED**.

## OPEN, STATED PLAINLY

- **ONE CELL IS BUILT, NOT THE WORLD.** `NavBounds_SpawnChunk` covers exactly
  one 1024 m cell, chosen as the one containing the PlayerStart. The other
  ~63 cells have no navmesh.
- **DO NOT EXTRAPOLATE THE WHOLE-WORLD COST FROM THE 20 s.** The builder
  iterated **81 loading cells** to produce navmesh in one; most had nothing to
  do. A world figure needs a world-sized volume and its own run.
- **Four chunk actors for "one chunk" is arithmetic, not a defect** — the
  volume's bounds ARE the cell boundaries, so it touches its neighbours.
  Sizes say which is real: 9526.6 KB against 76.7 / 74.0 / 4.2.
- **`custom_navigable_geometry` is still unsettled** and is now testable: the
  trees export per-instance transforms, so a build with `dont_export` would
  measurably differ. Not run.
- **The rocks and cliffs still do not collide** (see the block below), so they
  contribute nothing to this navmesh either.

**RESTORE POINTS:** `pre-navmesh-build-20260817`,
`pre-tree-collision-20260816`.

## NEXT, RANKED

1. **Decide the navigable region.** Unit 8's own note: the navigable area is
   authored, versioned recipe data derived from `traversability()`'s largest
   walk-profile component. One cell is a measurement; a world needs that
   ruling, and the tile budget gate now makes the consequences checkable
   before the packages are written.
2. **Unit 9 — the encounter planner.** Its reachability gate wants exactly
   what now exists: `project_point_to_navigation` against a BUILT navmesh, a
   collision-derived representation that corroborates `traversability()`'s
   heightmap rather than agreeing with it.
3. **Rule on rock collision** (BACKLOG 2026-08-16).
4. The hero, when Ryan returns to it.

---

# CURRENT STATE — 2026-08-16 (night) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries THIRTEEN
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (node `B2199975…`,
started 21:16, the second of the session). Nothing dirty, nothing in flight.

**THE HERO IS PARKED BY RYAN'S RULING** — *"we haven't been able to
successfully replicate the hero, I'll revisit this later since we have a
working prototype"*. The working build in `/Game/MetaHumans/` and both
`_trash/` backups are untouched by this session. Everything in the block below
about the hero stands.

## ⭐ UNIT 6 PASSES: THE TREES STOP HIM, PROVEN BY TRACE IN PIE

`PHASE2_PLAN.md` Phase B is now complete (units 5, 6, 7). Recipe
**R-TREECOLLIDE**; narrative in LESSONS 2026-08-16 (night); schema **v1.23**.

    Conifer         5/6 trunk hits    6/6 negative controls missed
    ConiferPine     6/6               6/6
    SpruceSub       5/6               6/6
    SpruceSapling   5/6               6/6

    GameThread at forest_floor   8.055 -> 8.261 ms   +0.206
    abort bar                    +0.5 ms            PASSES
    GPUTime                      8.338 -> 8.335     -0.003

**THE BOARD SAID ONE MESH WAS BROKEN. FOURTEEN WERE.** R-COLLIDE names
`SM_PVE_Norway_Spruce_01_A`'s zero collision primitives as *the* blocker on
unit 6. True, real, and **not the blocker**: measured before anything changed,
**all fourteen `FT_*` foliage types read `NoCollision`**, so 219,659 trees and
13,515 rock instances were pass-through — including the three species whose
MESHES carry perfectly good vendor capsules. Authoring the missing capsule
alone would have changed nothing and the session would have reported a fix.

Root cause: `UFoliageType`'s constructor sets `NoCollision`
(`InstancedFoliage.cpp:640`), `UpdateComponentSettings` copies it onto the
component unconditionally (`:1822`), and **`place_foliage` contains no
occurrence of the string "collision" in any form.** Nothing was set wrongly;
nothing was set at all. **A default you never named is a decision you never
made.**

## FOUR TRAPS PAID FOR, EACH ONE LOCKED IN R-TREECOLLIDE REJECTED

1. **`BlockAll` + `QUERY_ONLY` CANNOT BOTH HOLD.** `BlockAll` declares
   `QueryAndPhysics` (`BaseEngine.ini:3104`) and `PostLoad -> FixupData ->
   LoadProfileData` re-reads the profile **on every load**, so it reads back
   right in the session that wrote it and flips on the next start. Fixed with a
   project profile `FoliageBlockQueryOnly` whose own `CollisionEnabled` IS
   `QueryOnly`. **Do not "fix" this by using `Custom`** — that inherits
   `NoCollision`'s responses, which IGNORE Visibility and Camera, and a walk
   test would pass over invisible trees.
2. **`custom_navigable_geometry = "no"` does NOT keep trees out of the
   navmesh.** `No` still runs the DEFAULT collision export; `dont_export`
   excludes. `Yes` is the engine default and is the path that exports
   per-instance transforms. `PHASE2_PLAN` unit 6 prescribes `No` and is
   **backwards** — NOT applied, flagged for unit 8.
3. **On a Nanite mesh, `RENDER_DATA` and `get_section_from_static_mesh` return
   the FALLBACK proxy** — 6.6% too tall, 36% too wide, 1–8 vertices per low-Z
   band. `SOURCE_MODEL` gives 76,343 vertices and a clean trunk.
   `build_scale` is `[1,1,1]`, so they are different MESHES, not different
   units.
4. **THE SAVE IS PART OF THE PROCEDURE.** The load-time fixup that corrects the
   components does **not dirty their packages** — 0 dirty against 1,093
   corrected actors — so the editor was provably right while PIE, which
   streams from disk, got `NoCollision`. `save_foliage_actors.py` saves with
   `only_dirty=False`; 1,073 of 1,093 packages changed on disk, verified by
   `git status`, not by the tool.

**This is Pass 1's shape again:** the artefact on disk disagreed with the live
editor, every asset-level check was green, and only a different representation
— the PIE world — could see it.

## INSTRUMENTS ADDED

    apply_foliage_collision.py   recipe -> foliage types + authored capsule;
                                 refuses a capsule on gitignored vendor content
                                 by git check-ignore, joins on MESH PATH not a
                                 derived FT_<name>, reports types it did not name
    measure_foliage_collision.py read-only; prints the FOLIAGE TYPE and the
                                 MESH side by side. Profile 'Custom' == the
                                 declared profile was NOT FOUND
    verify_tree_collision.py     the acceptance test. DIFFERENTIAL, because
                                 every FHitResult field is protected in 5.8
                                 Python: each trace runs twice, the second time
                                 ignoring all foliage actors
    save_foliage_actors.py       only_dirty=False, narrow to IFA packages

## OPEN, STATED PLAINLY

- **THE ROCKS STILL DO NOT COLLIDE.** Ten `FT_*` (Boulder, CliffFace,
  CliffOutcrop×2, Talus×4, TreeStump, Scrub) are declared `"enabled": "none"`
  in `recipes/alpine.json` — the MEASURED truth, recorded rather than silently
  changed. They belong to `/Game/Alpine`, not Alpine8K, and carry no instances
  in this world. **Turning them on is a separate ruling with its own cost
  measurement.** A player can walk through a cliff face today.
- **The Conifer capsule radius is CONSISTENT, not pinned.** Brackets sit
  0.1–1.4 cm below `38.0 × scale` on 3 of 4 samples, consistent with
  `align_to_normal: 0.15` tilting the axis (~6 cm at the 1 m trace height) plus
  2–5 cm offset granularity. Do not quote it as a verified radius.
- **The cost A/B is CROSS-SESSION**, not single-variable in one process. The
  comparator is `pie002` (categories ON), **not `pie001`** — this run's GPUTime
  sits +0.519 above `pie001`, exactly the recorded cost of enabling the
  categories. Comparing to `pie001` reads +1.06 ms and trips a bar that was
  never crossed.
- **`measure_pie_cost` exit 4:** `canopy_250m` and `airship_1500m` REFUSED —
  the pawn cannot hold a 250 m perch and the tool correctly declines to measure
  somewhere else. Only `forest_floor_control` is in this artefact.
- **`ue_exec --timeout` is a DISCOVERY WINDOW spent in full.** That lesson was
  already in `LESSONS.md` from earlier the same day and did not fire; this
  session paid minutes per call. Now printed at the point of use for any value
  above 60. Use **12–25**.

**RESTORE POINT:** `pre-tree-collision-20260816`.

## NEXT, RANKED

1. **UNIT 8 — the navmesh, one chunk.** Phase C. Everything it needs is now
   true: trees are query-collidable and export per-instance transforms. It
   carries its own abort bars (200 GB peak commit / 30 min) and settles the
   `custom_navigable_geometry` question against a built navmesh. Also closes
   the standing 1.89× navmesh tile overflow.
2. **Rule on rock collision.** Ten foliage types, explicitly declared `none`
   today. Cheap to apply through the same tool; needs a cost run and a ruling
   on whether cliffs and boulders should block.
3. **The three `RECIPES.md` drafts** in `plans/` — they found 5 numeric errors
   in this project's own artefacts.
4. The hero, when Ryan returns to it.

---

# CURRENT STATE — 2026-08-16 (evening) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries TWELVE
> `# CURRENT STATE` headings, newest-first. **The first block in the file is the
> live one.** The superseded blocks say so in their bodies; their HEADINGS do
> not.

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (PID 7988, node
`A4B24E1F…`, the fourth of the session — three predecessors were killed or
crashed, see below). Nothing dirty, nothing in flight.

## THE HERO HAS HIS OWN FACE — SCULPTED FROM THE PHOTOGRAPHS, NOT A PRESET

Ryan: *"add in the hero features to the face to create the hero look based on
the image"*, then *"the image starting with qv94 should be the final product
look of the hero"* — the HAIRED portrait is the product target.

`_verify/20260816_face_mesh_final.png` is what it looks like: a heavy brow
shelf over deep-set eyes, a long straight strongly-projecting nose, broad
cranium, wide cheekbones. Recipe **R-HEROFACE**; narrative in LESSONS
2026-08-16 (evening); instruments in `scripts/hero_face/`.

    pass 1  residual 0.00844 -> 0.00153 units  (82% closed, 20 passes)
    pass 2  residual 0.00256 -> 0.00093 units  (64% closed, 10 passes)
    asset   104,960,609 -> 145,442,446 B, sha 95024DC2 -> ... -> 99EE9565+rig
    rig     Auto-Rigging finished in 25.098 s; can_build_meta_human TRUE
    mesh    33,845 verts / 64,094 tris, extent 0.11497 x 0.08275 x 0.12433

**THE UNIT IS 745 AND THE FIRST SCULPT SILENTLY DID NOTHING WITHOUT IT.**
`get_face_landmarks` REPORTS in one space, `translate_face_landmarks` ACCEPTS
another — measured linear at 744.85 / 745.32 / 744.99 / 745.11 across three
decades, saturating to 1702 at a requested 10.0. Do not re-derive this.

## ✅ RECOVERED — 2026-08-16 18:31. THE HERO POSES AGAIN, ON ASSEMBLED MESHES.

**Fixed by Ryan re-running Assemble on the RESTORED character**, then wiring
the pawn to the assembled meshes instead of the duplicated ones. Measured on
the live pawn in PIE:

    Body  spread (38.6, 62.2, 139.9)   head 154 cm ABOVE root
          root 31021.6 | pelvis 31106.8 | spine_05 31148.4 | head 31175.6
          hand_l 31107.9 | foot_l 31026.7        <- limbs spread properly
    Face  spread (20.6, 14.9, 170.1)   FACIAL_C_FacialRoot at 31179.8

Against 0.5 cm for the broken meshes. **CONFIRMED BY EYE 2026-08-16:** Ryan
pressed Play, saw him, and moved him around. Numbers and pixels agree, which
is the standard this project holds — and the pixels were the instrument that
caught the breakage in the first place, twice, when every asset-level check
was green.

**THE SCULPT IS NOW IN THE GAME — PARTIALLY — AND THE GROOMS ARE NOT.**
Re-sculpted on the RIGGED character with a per-pass health gate, re-Assembled
by Ryan and saved. PIE reads body spread (39.6, 62.8, 139.7), head 154 cm
above root; the assembled face mesh rasterises as a coherent male head.

    residual        1.10 -> 0.557 cm over 12 passes -- about HALF the
                    intended move; the face model absorbs the rest
    vs the photo    in-game face is 0.99-1.27 of the hero's width across the
                    head, so he is still up to 27% narrower at cheek and jaw

**THE CAUSE OF THE ORIGINAL DAMAGE IS FOUND: the landmark space depends on
the RIG STATE.** Rigged, `get_face_landmarks` returns CENTIMETRES (head Z
~171, cloud 18.4 x 22.4 x 27.6 cm, delta factor 2.43). Unrigged, it returns a
normalised space ~1/300 the size (head Z ~0.5, extent 0.088, factor 745).
745/2.43 = 307, so both calibrations were right about their own state.
**The first sculpt was performed on an UNRIGGED character** — Ryan had
unrigged it to edit textures, and `build_meta_human` later refused with
"Character is not rigged", which was the evidence in plain sight.
**ALWAYS CHECK THE LANDMARK SCALE BEFORE SCULPTING: head Z ~171 is right,
~0.5 is the degenerate space.**

**RETIRED — "the landmarks are a CONTROL CAGE, not surface points."** That
was recorded in LESSONS and R-HEROFACE from three irreconcilable scale
estimates (222 / 315 / 400+ cm per unit). All three were artefacts of the
degenerate space. In centimetres the cloud is a real head with consistent
anatomy.

## ⚠ THE GROOMS ARE ON THE CHARACTER AND HANG THE ASSEMBLE

Re-applied and verified from the saved bytes (four present at 3 hits each,
five unselected controls at 0). The character carries them: 145,046,691 B,
sha 78F8C8D2. **But Assemble then SPINS and never finishes.**

    editor CPU/wall   20.9      ~21 cores, sustained
    log growth        0 bytes   over 9 minutes
    DDC growth        0 MB      over 9 minutes
    working set       flat at 16.14 GB
    last log line     "ENDING scene cycle for batch: 70", exporting
                      8192x8192 T_Body_N_VT / T_Body_SRMF_VT

**I FIRST CALLED THIS "not stalled, working hard" FROM THE CPU READING ALONE
AND WAS WRONG.** Twenty-one cores producing no log, no disk and no memory
growth is a spin. The log and DDC checks are what settled it — the same
"one instrument that agrees with the hope" error that ran through this whole
day.

**THE GROOMS ARE PROBABLY INNOCENT — bisected.** `build_meta_human` from
Python, with all four grooms on, logs *"assembly succeeded"* and produces
**no `LogHairStrands` binding errors at all**. The binding failures seen
earlier were on the DAMAGED character; on the healthy one they bind cleanly.

**THE BETTER EXPLANATION IS MEMORY.**

    during the hang        free RAM 6.9 GB   editor WS 16.14 GB
    after a Python build   free RAM 2.2 GB   editor WS 21.34 GB (6 min old)
    fresh editor           free RAM ~12.9 GB

The editor reaches 21 GB on a 31.4 GB machine, and the stage that spun was an
**8192x8192 virtual-texture export** (`T_Body_N_VT`, `T_Body_SRMF_VT`) at
batch 70 — exactly the memory-hungry part. **NOT PROVEN**; what would settle
it is a retry at high headroom succeeding.

**PIPELINE RULE 5 EXISTED AND I DID NOT APPLY IT:** *"Heavy operations run
one at a time and log available RAM first."* An Assemble baking several 8K
virtual textures is a heavy operation, and I told Ryan to run it twice
without once checking free RAM.

**RETRY PROCEDURE:** restart the editor, run NOTHING first — the readiness
probe alone spawns a MetaHuman preview and costs ~3.6 GB — then Assemble
immediately at maximum headroom.

**THE GAME IS UNAFFECTED.** `/Game/MetaHumans/` still holds the 18:57
sculpted, groom-free build that works, and both backups are intact
(`_trash/WORKING_assembled_hero_20260816_DO_NOT_DELETE` and
`..._SCULPTED_20260816_1905_...`, 85 files / 542.8 MB each, byte-verified).

### THE ROOT CAUSE, ESTABLISHED WITH A NEGATIVE CONTROL
**`duplicate_asset` does not carry the reference skeleton.** Meshes produced
by `build_hero_assets.py` — which duplicates the preview actor's TRANSIENT
meshes — have a degenerate reference pose: every bone within 6 mm of one
point. An unposed mesh should still show its reference pose standing, which
is what makes this a mesh defect and not an animation one.

    assembled meshes           head_rise 160.6 cm   spread 132-170 cm
    duplicated meshes (control) head_rise   0.5 cm   spread   0.4-0.5 cm

**320x separation, with the known-bad meshes as the control** — so the test
discriminates rather than merely agreeing with what was hoped.

**`build_hero_assets.py` IS A DEAD END for producing playable meshes** and
should not be reached for again. Assemble is the only route that writes real
ones. Three theories died before this one: skeleton mismatch (refuted by
control), the sculpt (refuted — the restored character's duplicates collapse
too), and the missing face post-process ABP (applied, no change).

**WHAT IS LOST:** the `SKM_HeroFace` / `SKM_HeroBody` that WORKED (measured:
head 148 cm above root, bone spread 135 cm). `Content/Hero/Generated/` is
gitignored as "re-derivable", so no commit and no tag holds them, and the
restore point taken before the destructive rebuild structurally could not
cover ignored content. **Re-deriving today does not reproduce them.**

**WHAT IS SAFE:** `MHC_AlpineHero` in every state (tracked; sculpted+groomed
at tag `sculpted-hero-before-revert-20260816`, pre-sculpt restored live), the
assembled character `/Game/MetaHumans/` (252 uassets), and all the sculpt
measurements.

### THE MEASUREMENTS, AND TWO THEORIES THEY KILLED

    PIE, world coords    working mesh   head 148 cm ABOVE root, spread 135 cm
                         every mesh
                         derived today  head ~5 cm BELOW root, spread ~6 cm

    preview head rise    sculpted character    0.5 cm
                         pre-sculpt character  160.6 cm

**KILLED — "skeleton mismatch".** Working and broken meshes report the SAME
skeletons (`metahuman_base_skel` 342, `Face_Archetype_Skeleton` 875) under
the same `ABP_Unarmed`. One poses, one does not.

**KILLED — "the sculpt broke it".** The sculpt DID damage the character's
preview (0.5 vs 160.6 cm, a real finding). But meshes duplicated from the
RESTORED, healthy 160.6 cm preview **still collapse in PIE**. So the sculpt
is not what stops the derived meshes posing.

**WHAT THAT LEAVES:** `duplicate_asset` loses something the mesh needs.
One instance is MEASURED: the duplicated `SKM_HeroFace` has
`post_process_anim_blueprint` **NULL**, where every other hero mesh carries
one — and a MetaHuman face is deformed BY that graph. That is a concrete lead
and it was never tested, because the body carries its post-process ABP and
still collapses, so it cannot be the whole story.

**ALSO MEASURED:** `BP_MHC_AlpineHero`, Assemble's own output, renders
nothing either — Ryan looked. But it was assembled from the SCULPTED
character, so a fresh Assemble from the restored one is untested.

### THE POST-PROCESS FIX WAS TRIED AND DID NOT WORK — and it found the cause

`post_process_anim_blueprint` on the duplicated `SKM_HeroFace` was NULL and
is now `ABP_Face_PostProcess` (set, saved, read back off a reloaded asset).
**No change**: both meshes still collapse.

**But the full, untruncated reading is the finding.** Every bone sits within
6 mm of ONE POINT, 5.5 cm below the root:

    root 31021.6 | pelvis 31016.0 | spine_05 31016.1
    head 31016.2 | hand_l 31016.0 | foot_l  31015.8

An unposed mesh still shows its REFERENCE pose, standing. This is not a
failed animation — **the duplicated mesh's reference skeleton is itself
degenerate.** That is why a healthy 160.6 cm preview yields a broken copy,
why the post-process graph had nothing to fix, and why the body collapses
even though it never lost its post-process ABP.

**CONCLUSION: `duplicate_asset` CANNOT carry these transient MetaHuman
meshes. `build_hero_assets.py` is a dead end for restoring the hero** —
regardless of sculpt, textures or anim wiring. It is not worth another cycle.

### THE FIRST THING A FRESH SESSION SHOULD DO
**Re-Assemble from the restored character** (Ryan's click; the character is
now the healthy pre-sculpt one, and the existing `/Game/MetaHumans/` build
was made from the SCULPTED, damaged one). Then SAVE — Assemble leaves all
252 packages dirty — and wire the pawn to the assembled meshes.
Acceptance test is one command and discriminates by 25x:

    python scripts/hero_face/run_pie_probe.py scripts/hero_face/probe_pie_skeleton.txt
    PASS head ~148 cm ABOVE root      FAIL head below root, spread ~6 cm

**AND BEFORE ANY DESTRUCTIVE STEP ON `Content/Hero/Generated/`: COPY IT
ASIDE ON DISK.** A git tag cannot hold gitignored content. That is the rule
this regression bought.

## ⚠ THE SCULPTED FACE IS **NOT** IN THE GAME. THE HERO WEARS HIS OLD FACE.

Read this before believing anything below it. The sculpt is real, committed
and rigged inside `MHC_AlpineHero`, and Assemble built a complete character
from it — but **nothing the pawn wears carries it yet.**

    /Game/Hero/Generated/SKM_HeroBody + SKM_HeroFace   <- what the pawn wears
                                                          POSE correctly,
                                                          PRE-SCULPT face
    /Game/MetaHumans/MHC_AlpineHero/...                <- has the sculpt AND
                                                          baked skin, and
                                                          RENDERS NOTHING

**Pointing the character at the assembled meshes makes him invisible**,
measured in PIE in world coordinates:

    assembled   root Z 31021.6   head Z 31016.1   head 5.5 cm BELOW root
                bone spread (3.5, 1.2, 6.0) cm
    working     root Z 31021.6   head Z 31169.6   head 148 cm above root
                bone spread (38.4, 55.5, 135.1) cm

The collapsed skeleton draws nothing, so the hero is present, visible,
unhidden, correctly offset and invisible — which is exactly what Ryan saw.

**SKELETON IDENTITY IS NOT THE CAUSE, and the obvious theory is REFUTED.**
Both sets report the SAME skeletons — `metahuman_base_skel` (342) and
`Face_Archetype_Skeleton` (875) — under the same `ABP_Unarmed` authored for
`SK_Mannequin` (161). One poses and one collapses, so the difference is
something else about the assembled meshes (their reference pose, LOD or
required post-process anim setup). **Not established. Do not guess it.**

**THE ROUTE IS `BP_MHC_AlpineHero`**, which Assemble already wired with
`ABP_Face`, the post-process anim blueprints and LOD sync — rather than
bolting MetaHuman meshes bare onto a mannequin-shaped character. That is real
work, not a repoint.

## THE ASSEMBLE OUTPUT IS ON DISK — and it nearly looked like it never ran

Assemble leaves **every package DIRTY AND UNSAVED**. It logs "MetaHuman
Character assembly succeeded" and writes nothing; on 2026-08-16 that read as
"Assemble did nothing" until `get_dirty_content_packages()` was asked and
returned **252**. Saved: `Content/MetaHumans` 0 → 252 uassets, 631 MB,
gitignored as derived. It writes `/Game/MetaHumans/`, NOT
`/Game/Hero/Generated/`.

## ~~THE ONE THING ONLY RYAN CAN DO~~ — DONE, AND IT WAS ONE CLICK

**Open `MHC_AlpineHero` and press Assemble.** The character is sculpted,
rigged and `can_build_meta_human` reads TRUE, so it is ready. But
`build_meta_human` from Python logs *"MetaHuman Character assembly
succeeded"* and writes **nothing to disk** — everything lands in
`/Engine/Transient.MHC_..._Collection:`. **There is no reflected unpack
function anywhere in the 5.8 stub, with any `absolute_build_path`.**
Until Assemble is pressed, `/Game/Hero/Generated/SKM_HeroFace` is still the
12:23 build and **the hero in PIE still wears the old face.**

**CORRECTION TO THIS FILE'S OWN PREVIOUS BLOCK:** it said *"Assemble is NOT
REFLECTED — no unpack, no build anywhere in the 5.8 stub"*. `build_meta_human`
and `can_build_meta_human` ARE reflected; only the UNPACK is not. The old
reading was taken off a stub generated before the MetaHuman plugins were
enabled — **the Python stub is a DERIVED RECORD, regenerated per editor
start** (non-negotiable 15).

## THE GROOMS ARE APPLIED — hair, beard, moustache and brows, from Python

Ryan's ruled target has long layered hair and a full stubble beard. All four
are now selected on the character, chosen against the portrait:

    Hair       WI_Hair_M_Layered        -> Hair_M_Layered_Binding
    Beard      WI_Beard_M_Stubble       -> Beard_M_Stubble_Binding
    Mustache   WI_Mustache_M_Stubble    -> Mustache_M_Stubble_Binding
    Eyebrows   WI_Eyebrows_M_Dense      -> Eyebrows_M_Dense_Binding

**THE ROUTE, so nobody re-derives it.** Adding an item makes it AVAILABLE;
it is not worn until the INSTANCE selects it, and conflating those is how a
tool reports success over a bald hero:

    col = subsystem.get_preview_collection(character)
    col.try_add_item_from_wardrobe_item(slot, wardrobe_item)   # available
    col.default_instance.set_single_slot_selection(slot, key)  # worn
    subsystem.on_edit_preview_collection(character)            # REQUIRED
    EditorAssetLibrary.save_asset(...)

`on_edit_preview_collection` is not optional — the engine's own docstring
says any code modifying the preview collection must call it to propagate the
edits back to the Character asset.

**VERIFIED FROM THE SAVED BYTES, POSITIVE-CONTROLLED.**
`verify_grooms_on_disk.py` finds all four groom names in
`MHC_AlpineHero.uasset` (3 hits each) and finds **zero** hits for five grooms
that were deliberately not selected (`Hair_L_Straight`, `Beard_L_Full`,
`Mustache_L_Handlebar`, `Eyebrows_S_FlatThin`, `Hair_M_Mohawk`). The search
discriminates, so the presences are evidence rather than a token that appears
everywhere. Asset 145,442,446 -> 145,447,390 B.

Available if the look wants tuning: 86 hair, 16 beard, 16 moustache and 37
eyebrow items under `/MetaHumanCharacter/Optional/Grooms/Bindings/`.
`WI_Hair_L_MessyClumps` is the longer, shaggier alternative.

## WHAT THE MEASUREMENTS SAY, INCLUDING WHERE THE SCULPT STOPS

Two instruments, different representations: the bald portrait's chroma
silhouette (skull and jaw outline) and the MetaHuman face tracker's 16
contour curves (eyelids, lips, philtrum, nasolabial). Both agree the sculpt
moved the right way; the mesh's own 33,845 vertices give the comparison.

**PASS 2 WIDENED THE CRANIUM AND CHEEKS +7.1% TO +8.1% AND MOVED THE JAW
+1.0% / +0.2%.** The hero remains **13–22% wider at the jaw** than the sculpt
will go. That is a property of the MetaHuman face model resisting the
mandible, measured in absolute widths at matched heights
(`compare_sculpt_passes.py`) — not a failure of the pass, and not something a
larger gain fixes.

**A CLAIM I MADE AND THE MEASUREMENT REFUTED.** I reported the bald and
haired references as different face shapes. Normalised to interpupillary
units they agree within ~3% (eye_to_mouth 1.002, mouth width 0.971,
nasolabial 1.034). `hero/reference/README.md`'s "the SAME face" is SUPPORTED.
Stated narrowly: the tracker measures eyes, lips and nasolabial folds only,
so jaw and cheekbone contour are UNMEASURED on the haired image.

## THREE EDITORS DIED, AND EACH ONE IS A RULE NOW

1. **`request_auto_rigging(blocking=True)` CRASHES THE EDITOR** —
   `Assertion failed: IsValid() [SharedPointer.h:1133]`, **the same assertion,
   file and line as the recorded `conform_to_target_meshes` crash.** Two
   entry points, one subsystem: it is a property of driving
   `MetaHumanCharacterEditor` synchronously from remote Python.
   `blocking=False` runs clean in ~25 s. Crash kept at
   `_verify/20260816_autorig_crash/`.
2. **SPAWNING THE METAHUMAN ACTOR BEFORE A SAVE WEDGES THE EDITOR** — twice.
   Log stops at `InternalPromptForCheckoutAndSave` -> `FlushAsyncLoading`,
   game thread 0.04 CPU per wall-second, untitled modal, and the committed
   sculpt is LOST because it never reached disk. The spawn brings up
   `/Temp/MetaHumanCharacter/LightingEnvironments/...` streamed levels.
   `apply_face_sculpt.txt` now takes `--set SPAWN=False` and that is the
   default posture.
3. A **"Save Content" modal** from the previous session's editor was blocking
   remote execution at session start; it was discarded by ending the process
   rather than clicking an unlabelled button, and
   `Saved/Autosaves/PackageRestoreData.json` moved to `_trash/` each time so
   the next launch could not raise a Restore modal — which would block the
   only channel that could report it.

## OPEN, STATED PLAINLY

- **`/Game/Hero/Generated/SKM_HeroFace` IS STILL THE 12:23 BUILD.** Byte
  identical, timestamp unchanged, verified on the filesystem. Nothing in the
  game has the new face yet. One click fixes it.
- **NO PIE FRAME OF THE NEW FACE EXISTS.** The sculpt is proven by asset
  bytes and by mesh geometry, never by a game frame.
- **FOUR ENGINE RENDERS OF THE CHARACTER CAME BACK PURE WHITE** (mean RGB
  255/255/255, nonwhite fraction 0.0000). The preview mesh is ~0.12 units
  tall and its components sit at world origin and **do not follow
  `set_actor_location`**, so it is inside the near clip plane. Every picture
  in this work is an offline rasterisation of the mesh vertices instead.
- **`Potential Degenerate Triangles`** is warned by the auto-rigger on this
  face mesh. It rigged successfully anyway, twice, and the renders look
  clean. Attribution is NOT established: the three failed conform attempts
  earlier that day are as plausible a cause as the sculpt.
- **The lateral correction was applied ONCE and lost ONCE** to the save wedge
  before being re-applied successfully. `face_lateral_spec.json` is on disk
  and idempotent, so re-running is safe.

**RESTORE POINT:** `pre-hero-face-features-20260816`.

## NEXT, RANKED

1. **GET THE SCULPTED FACE ONTO A PAWN THAT POSES.** This is the whole
   remaining job and it is not a repoint — the assembled meshes collapse.
   The route is `BP_MHC_AlpineHero`: make the player pawn that Blueprint (or
   graft its component/anim setup onto `LandscapeLabCharacter`), because
   Assemble already wired the `ABP_Face` post-process chain those meshes
   need. Acceptance test is written and cheap:
   `run_pie_probe.py probe_pie_skeleton.txt` — **head must sit ~148 cm ABOVE
   root, bone spread ~135 cm in Z.** Anything near 6 cm is the collapse.
2. **A second, cheaper option worth costing first:** re-derive
   `/Game/Hero/Generated/` from the SCULPTED character, since that route is
   proven to pose. `build_hero_assets.py --rebuild` exists for it but
   FAILED — `duplicate_asset` returned None after the delete (the files were
   untouched on disk, so nothing was lost). Fix that and the sculpt reaches
   the existing, working pawn without touching the anim setup. The trade is
   that this route cannot carry the baked skin.
3. **Look at him and rule on the groom.** `WI_Hair_M_Layered` is my read of
   the portrait; `WI_Hair_L_MessyClumps` is longer and shaggier. Also note
   all four groom BINDING assets failed to build (*"guide roots are not close
   enough to the target mesh"*), so the hair may not sit correctly even once
   it renders.
4. The jaw. It is 13–22% narrower than the reference and the face model
   resists. If it matters, the lever is a target-mesh conform, not a larger
   sculpt gain — and that route crashed the editor on 2026-08-16.

---

# CURRENT STATE — 2026-08-16 (midday) — **SUPERSEDED by the block above.**

**Tree clean. An editor IS RUNNING** on `/Game/Alpine8K` (node `9E119E63…`,
launched after the second plugin rebuild). Nothing dirty, nothing in flight.

## THE HERO IS PLAYABLE. PRESS PLAY AND YOU ARE HIM.

`_verify/20260816_hero_press_play_FIXED.png` is what that looks like: a
MetaHuman standing in a sunlit clearing, forest and outcrops around, seen over
his shoulder. Proven in PIE on a fresh editor:

    pawn class        LandscapeLabCharacter
    CharacterMesh0    /Game/Hero/Generated/SKM_HeroBody   anim ABP_Unarmed_C
    FaceMesh          /Game/Hero/Generated/SKM_HeroFace   leader CharacterMesh0
    bound actions     3 of 3
    unresolved        (empty)
    spawn             (354600, -321400), 15.3 m to nearest trunk, 3.4 deg slope

Recipes **R-HERO** and **R-TRELLIS**; narrative in LESSONS 2026-08-16.

## HE HAS HIS SKIN NOW — 2026-08-16 midday, WITH RYAN AT THE KEYBOARD

**The white-plaster hero is gone.** `_verify/20260816_hero_body_textured.png`
and `_hero_front_textured.png`: flesh-toned head with a real face, male build,
standing in the clearing.

    face   HIS OWN maps      Basecolor / Normal / Cavity, 6 skin slots
    body   STOCK MetaHuman   T_Skin_V2_Chest_BC + Chr0035 detail maps
    body shape   Masculine/Feminine -2.0, Muscularity 2.0, Height 178.196
    verified     0 transient or null materials, read back off reloaded assets

**WHAT UNLOCKED IT WAS A UI COMMAND, AND THREE PYTHON ROUTES WERE CLOSED FIRST**
— Assemble is not reflected in 5.8; the skin lives in parameter overrides on a
dynamic instance whose getter hard-refuses that type; and transient textures
cannot be duplicated into real packages (the copy reloads as nothing). The door
is **MetaHuman Character → Save Face Textures**, which writes the maps as PNGs.
Ryan ran it; `scripts/bake_hero_face_textures.py` does everything after.

**ORDER MATTERS AND MY FIRST INSTRUCTION HAD IT BACKWARDS:** `Create Full Rig`
BEFORE `Download Texture Sources`. Downloading first errors telling you to
autorig.

**THE BODY IS STOCK AND THAT IS A TRADE, NOT AN ACCIDENT.** The editor exports
the FACE atlas only — confirmed by opening the exported basecolor (a face UV
layout) and by Ryan reading the menu. His body maps went transient after the rig
and cannot be recovered. `bake_hero_body_textures.py` prints this on every run.

**TWO TRAPS THAT COST REAL TIME, NOW PAID FOR ONCE:**
`MaterialEditingLibrary.set_material_instance_texture_parameter_value` **returns
False** for `Basecolor`/`Normal`/`Cavity` — names `get_texture_parameter_names`
lists on the SAME instance — so the first bake reported six instances created
and `"bound": []` on all of them. **Write the `texture_parameter_values` array
directly.** And a re-run made an instance **its own parent**, because the tool
took the slot's current material as the parent; both bake tools now walk up.

## ~~THE ONE THING ONLY RYAN CAN DO~~ — DONE 2026-08-16. Kept for the sequence.

**Open `MHC_AlpineHero` and press Assemble in the MetaHuman panel.** That writes
the textured, properly assembled meshes that Python cannot: MetaHuman's Assemble
is NOT REFLECTED — no unpack, no build anywhere in the 5.8 stub — and the skin
lives in parameter OVERRIDES on a dynamic material instance whose getter
hard-refuses that type (`Cannot nativize 'MaterialInstanceDynamic'`). Measured
against all 80 texture parameters. **The white skin is a property of the route,
not a bug in the run.**

While in there: the body's **`Masculine/Feminine`** slider (range -2..+2) is the
male fix. My scripted attempt to move it is an UNUSABLE INSTRUMENT, not a
finding — a ±2.0 swing produced byte-identical body bounds including the
baseline, so it never reached the mesh.

Then: point `recipes/character.json` `assets.skeletal_mesh` / `assets.face_mesh`
at the assembled meshes, `python scripts/apply_character_recipe.py --ini-only`,
restart the editor.

## TRELLIS RUNS ON THIS GPU — the plan said the documented path could not

472,734 verts, 945,456 faces, watertight, **64 s** from Ryan's portrait.
Environment at `/opt/trellis` inside **WSL2 Ubuntu-24.04** (NOT 26.04, whose
only Python is 3.14), CUDA 12.8.93, conda env `trellis` on Python 3.11, **torch
2.11.0+cu128 with capability (12, 0) and sm_120 in the arch list**, proven by a
real matmul and reduction against a CPU reference.

**Four blockers, each attributable because the install was piecewise.** The one
worth not re-deriving: `ATTN_BACKEND=sdpa` is **silently ignored** by
`trellis/modules/sparse` (which takes only `xformers`/`flash_attn`) while the
DENSE attention module accepts it — use `xformers`, plus `XFORMERS_DISABLED=1`
to route DINOv2 away from a library with no sm_120 fp32 kernel. And **kaolin was
not needed**: one symbol, shimmed and selftested at
`scripts/trellis/kaolin_check_tensor_shim.py`.

**THE FACE IS NOT YET CONFORMED.** `SM_HeroHead_TRELLIS` is imported and the
route is mapped but UNBUILT — see NEXT.

## THE HERO INPUT IS SETTLED AND HASH-PROVEN

`hero/reference/` holds four Gemini portraits, copies at stable names with
SHA-256 equal to their sources at adoption time. **The BALD frontal is the
input**, and that is geometry not taste: Mesh to MetaHuman reads SHAPE, and
TRELLIS reconstructs hair as a solid volume fused to the skull.
`scripts/prepare_hero_input.py` crops it by MEASUREMENT (chroma, because the
grey background sits under a radial vignette that defeats any luminance model)
and is proven in both directions — refuses both full-body images, passes both
portraits.

## FIVE TOOLS REPORTED SUCCESS WHILE DOING NOTHING — all fixed, all logged

1. **A SAVE RETURNED True AND WROTE NOTHING.** `save_dirty_packages(True, True)`
   after a Python actor edit; the edit never flagged the external actor package
   dirty. Caught by the FILESYSTEM — nothing under `__ExternalActors__` changed
   in ninety minutes while every read-back agreed, because every read-back read
   editor memory. `place_player_start` now saves the actor's own package and
   PRINTS ITS NAME so the artefact can be checked.
2. **`Rotator(ROLL, PITCH, YAW)` recurred in a committed tool.**
   `Rotator(0.0, YAW, 0.0)` set PITCH 135, normalised to (180, 45, 180). The
   camera then sat **88 cm BELOW** the pawn on a 400 cm arm. It survived because
   the tool read back LOCATION and never ROTATION. Now asserted, exit 5.
3. **`ATTN_BACKEND=sdpa`**, ignored by one module and honoured by another.
4. **A detached WSL job** that printed STARTED and left no process — WSL tears
   down the session tree when the initiating `wsl.exe` exits.
5. **A kaolin stub** that would have satisfied the import and disabled six
   assertions. Implemented and selftested instead.

**Not one was caught by a gate.** Every one was caught by asking a DIFFERENT
REPRESENTATION.

## A CLAIM I MADE AND RETRACTED

I reported **"no head — the face mesh is not rendering"** from the first PIE
frame. **Wrong.** The camera was 1 m away and the head was out of frame. Bone
transforms said so first; lifting the pawn above the canopy showed a complete
head. Three photographs said "something is wrong" and none could say what.

## NEW INSTRUMENTS

    scripts/wsl_exec.sh          run a local script in WSL, base64, no quoting
    scripts/ue_exec.py           run a payload FILE in the rule-7 editor
    scripts/build_hero_assets.py derive the hero meshes, idempotent, verified
    scripts/find_hero_spawn.py   KD-tree over 219,659 trunks -> a clearing
    scripts/prepare_hero_input.py measured head crop, refuses non-portraits
    scripts/trellis/kaolin_check_tensor_shim.py

## NEXT, RANKED

1. **RYAN: Assemble `MHC_AlpineHero`** (textures + male body). Everything else
   is ready for it.
2. **THE FACE — THE TRACKER WORKED ONCE AND I COULD NOT REPRODUCE IT. READ
   THIS BEFORE SPENDING AN HOUR ON IT.**
   `track_face_landmarks_from_image` returned **16 real curves**
   (`crv_eyelid_upper_l/r`, `crv_lip_philtrum_l/r`, …) from a TRELLIS
   reconstruction rendered in-editor, and **only from `+Y`**, which settles the
   facing by measurement. **Then TEN further runs returned `None` and I could
   not get it back.** Refuted along the way, each single-variable: the material
   assignment, smooth vertex normals in the OBJ (that one was MY regression —
   Unreal smooths a normal-less OBJ and honours per-face normals if you supply
   them), triangle budget, crop height, light intensity, scale basis, and
   delete-then-import versus re-import.
   **AND I DESTROYED THE EVIDENCE.** Every probe run exported to the same
   filename, so the successful frame was overwritten; the surviving frames are
   labelled `_FAILED_faceted` and `_UNREPRODUCED`. A probe that writes to a
   fixed name destroys its own best evidence exactly when it starts working.
   **A success I cannot reproduce is not a capability**, and the next session
   should treat "make the render reproducible, with per-run filenames" as the
   task — not the conform, which has still never run with landmarks.
   **THE POSITIVE CONTROL PASSES AND HALVES THE SEARCH.** Feeding the tracker
   Ryan's actual PHOTOGRAPH through the same `read_render_target` path returns
   **16 curves**, with skin measuring **105.0/66.5/56.2** (red-dominant, so the
   BGRA channel order is right too). `scripts/trellis/tracker_positive_control.txt`.
   **So the tracker is sound and every `None` is about the SUBJECT.** The mesh
   renders measure **177.9/172.3/166.9** — bright and colourless where a face is
   dark and warm — because **the skin material never applied**: the imported OBJ
   has ZERO material slots, so `set_material(0, …)` on the component has no slot
   to override and silently does nothing. Every render has been the default
   checkerboard. **Set the material on the MESH ASSET, and tune the light
   against 105/66/56 rather than by eye.** Faceting is still unexplained — the
   render that tracked had a round crown, the current ones are angular, from the
   same 40,000 triangles and 20,189 vertices.
   Working settings as recorded: crop the collar, 40k triangles, no normals in
   the OBJ, import, spawn at Z 250,000 against sky, scale 24 cm from the Z
   extent, PointLight 200,000 travelling with the camera, SceneCapture2D FOV 35
   at 70 cm, `SCS_FINAL_COLOR_LDR`. Payload kept at
   `scripts/trellis/conform_payload.txt`.
   **THE CONFORM CALL ITSELF — attempted once, CRASHED THE EDITOR, route known.**
   `conform_to_target_meshes` with `auto_solve=True` and no tracking inputs
   asserts `IsValid()` (`SharedPointer.h:1133`) inside
   `MetaHumanCharacterEditor` and takes the editor with it. **Nothing was
   damaged** — tree clean, `MHC_AlpineHero.uasset` unchanged, restore point
   `pre-hero-face-conform-20260816` not needed. Crash context preserved at
   `_verify/20260816_conform_crash/`.
   **The expensive unknown IS now settled, and it corrects a claim I made
   earlier tonight.** `get_mesh_data_for_conforming(mesh)` returns
   `(vertices, triangle_indices)` from any Static or Skeletal mesh — "the same
   data the interactive conform tool uses internally" — and those map
   one-to-one onto `head_vertices` / `head_vertex_indices`. **The indices are
   TRIANGLES, not archetype correspondence, so ARBITRARY TOPOLOGY IS
   SUPPORTED.** My earlier reading that a raw TRELLIS mesh was "not a drop-in"
   is WITHDRAWN.
   Next attempt: DECIMATE first (`scripts/trellis/decimate_head.py`; 472,734
   verts crosses the Python binding once per element and took >10 min), crop
   the collar out of the MESH, and supply `curve_tracking_points` +
   `camera_view_info` + `image_size` from a rendered view via
   `track_face_landmarks_from_image`. Measured for the alignment: TRELLIS
   extent (0.696, 0.921, 0.998) against archetype (34.99, 24.28, 37.32) cm at
   bbox Z 134.7–172.0, same axis convention — scale from HEIGHT (37.4), the
   collar is why width and depth disagree by 2x.
3. **Animation on the MetaHuman body is MEASURED, NOT UNDERSTOOD.**
   `ABP_Unarmed` targets `SK_Mannequin` (161 bones), the body is
   `metahuman_base_skel` (342), and BOTH `compatible_skeletons` arrays are
   EMPTY. It poses correctly anyway. Do not assume interchangeability.
4. Navmesh tile overflow (1.89x, silently clamped) — unchanged from below.

**RESTORE POINTS:** `pre-hero-body-masculine-20260816`,
`pre-hero-spawn-move-20260816`.

---

# CURRENT STATE — 2026-08-15 (handoff) — **SUPERSEDED by the block above.**

> **Read this heading before you grep.** `CLAUDE.md` now carries NINE
> `# CURRENT STATE` headings, newest-first. On 2026-08-15 an agent grepped,
> landed on an older block, and reported the live record as stale — its
> contradiction was honest and it picked the wrong side. The superseded
> blocks say so in their bodies; their HEADINGS do not. Renaming them is
> Ryan's call; until then, **the first block in the file is the live one.**

**Tree clean. A FRESH editor is on `/Game/Alpine8K`** (relaunched after the
plugin build; new node id `4CF5F9AC…`, so every check below is cold-boot
evidence). Terrain phase is complete and Ryan has visually accepted it.

**PHASE 2 IS UNDERWAY. `PHASE2_PLAN.md` PHASE A IS COMPLETE (units 1–4) AND
UNIT 7 IS BUILT AND VERIFIED.** PIE was started and ended cleanly twice; the
world on disk is untouched, because PIE runs against a duplicate.

**RYAN RULED: MULTI-REGION, 2×2 ATLAS** (2026-08-15, in session). Recorded in
`WORLD_VISION.md` at both reserved places. The tripwire is discharged.

## UNIT 7 IS BUILT — THERE IS NOW A RUNTIME MODULE

`LandscapeLab/Plugins/LandscapeLabGameplay`, built clean in **35 s** first
try. Recipe **R-GAMEPLAY**; verifier `scripts/verify_gameplay_plugin.py`.
**`LandscapeLab.uproject` is STILL byte-identical** — `PluginManager.cpp:420-433`
honours `EnabledByDefault` with no entry, so standing rule 4 stands again.

Cold boot reads: plugin ENABLED; **`GameplayStateTree` ENABLED** (it ships
`EnabledByDefault: false`, so it is the one result that could not be true by
accident — it proves the dependency list did the work); `EnhancedInput` and
`StateTree` ENABLED; `unreal.LandscapeLabCharacter` and
`unreal.LandscapeLabGameMode` REFLECTED with reachable CDOs;
`apply_movement_spec` PRESENT.

**Two operational facts worth not re-deriving.** A new module CANNOT be added
by Live Coding — `Ctrl+Alt+F11` is not an alternative, the editor must close.
And a quit with any dirty package raises a **Save Content** modal that blocks
the game thread and therefore blocks remote execution, the only channel that
could answer it; `get_dirty_content_packages()` is read first and an
UNREADABLE count is treated as a refusal, not a zero.

## UNIT 5 — OUR CHARACTER NOW SPAWNS. IT ALSO FALLS.

**PROVEN ON A COLD BOOT:** `probe_pie --go` reports
`pawn class LandscapeLabCharacter`, where the same tool reported
`DefaultPawn` earlier the same day. **That one word proves the whole chain
at once** — the plugin loaded, `GlobalDefaultGameMode` is in effect, and
`DefaultPawnClass` is set in C++ rather than in config.

    GameDefaultMap      /Engine/Maps/Templates/OpenWorld -> /Game/Alpine8K
    EditorStartupMap    -> /Game/Alpine8K
    GlobalDefaultGameMode  ABSENT -> LandscapeLabGameplay.LandscapeLabGameMode

A cook before this shipped **Epic's template world with Epic's default pawn,
and exited 0.**

**THE CHARACTER FELL: spawn Z −91,373 cm.** Diagnostic, not a terrain defect
— the level has **zero `PlayerStart` actors**, so the pawn appears at the
world origin *before* World Partition has streamed ground under it, and
gravity does the rest. **Unit 5's next step is exactly the fix**: a spawn
point traced onto the collidable surface. Do NOT read this as "the terrain
does not collide" — R-WALK and unit 3 both measured otherwise.

**MIGRATED:** the engine template mannequin, 128 files / 125.3 MB, to
`LandscapeLab/Content/Characters/Mannequins` — **a destination the assets
dictate**, since they reference `/Game/Characters/Mannequins/...` internally.
Gitignored on the `Content/Mannequin/` precedent. `SKM_Manny_Simple`: 161
bones, 3 LODs (48,705 / 14,925 / 7,504), `PA_Mannequin` resolves.
**The 48,779-equals-48,779 broken LOD chain was the GV pack's mesh, NOT this
one — that check is closed and nothing is owed.**

## METAHUMAN WORKS — THE MISSING PIECE WAS `MetaHumanCoreTech`

**RESOLVED 2026-08-15 by Ryan**, after four failed attempts. The Plugins UI
told him it **needed the Core Data first**; enabling that added
`MetaHumanCoreTech`. Editor loads normally (592 CPU-s, 10.78 GB);
`verify_gameplay_plugin` exit 0 with our classes still reflected.

**THE CAUSE, VERIFIED:** `MetaHumanCharacter.uplugin` declares **20** plugin
dependencies and **`MetaHumanCoreTech` IS NOT ONE OF THEM** — and it does not
start without it. Every route I tried enabled what the descriptor DECLARES
and faithfully reproduced an **incomplete declaration**.

**A PLUGIN DESCRIPTOR IS A DERIVED RECORD.** It states what somebody wrote
down about a plugin's needs, not what it needs. Fourth instance of this class
in this project, and the first in a file nobody treated as a config.

**Enable a plugin the way the EDITOR enables it, at least once, before
encoding it anywhere.** The descriptor route REPRODUCES a known-good
enablement; it cannot discover one. When a headless route fails repeatedly,
the attended route is not a fallback — it is the diagnostic, and here it
produced the answer in one sentence that no external measurement could have.

**OWED:** both names are in `.uproject`, not in `LandscapeLabGameplay.uplugin`
where ruling 2 wants them. Now that BOTH are known the descriptor route should
work; moving them is the tidy end state and the test of that claim.

**Everything below in this section is the RECORD OF THE FAILED ATTEMPTS**,
kept because each eliminated a real candidate by measurement — and because
the hypothesis space was wrong in an instructive way: every candidate was
about the ENVIRONMENT, none about the plugin's own declaration being
incomplete.

## METAHUMAN — RULED IN BY RYAN, ENABLED, HUNG THE EDITOR, REVERTED

**Ryan ruled 2026-08-15 to use MetaHuman for the player character**,
overturning `PHASE2_PLAN.md` ruling 14. `MetaHumanCharacter` was added to
`LandscapeLabGameplay.uplugin`'s `Plugins` array (ruling 2's route) and **the
editor never finished starting.** Reverted; project verified back to
known-good (`verify_gameplay_plugin` exit 0, both classes reflected).

Restore point `pre-metahuman-enable-20260815`; log preserved at
`_verify/20260815_metahuman_enable_stall.log`.

**HUNG, NOT SLOW — four instruments at once:** 2.41 GB working set flat,
**0.02 CPU-s per wall-s**, **0.0 MB DDC growth in 120 s**, 0
`ShaderCompileWorker`, **11 minutes of log silence**, window class still
`SplashScreenClass`. DDC growth is the decisive one — shader compilation
shows a flat parent CPU by construction but still writes to disk.

**WHAT IT WAS NOT.** Not memory: 2.41 GB against a 223 GB commit limit with
the CPU IDLE — **the page file needed no change**, and raising it would have
spent a reboot on a problem that did not exist. Not missing binaries:
`MetaHumanCharacter` ships **7 prebuilt DLLs**. Not our C++: the same editor
with only that one line removed loaded in 993 CPU-s / 4 min.

**ROOT CAUSE IS NOT ESTABLISHED. A CLAIM THAT IT WAS IS RETRACTED — see
LESSONS 2026-08-15 "RETRACTION".** The stall reproduces with the plugin
enabled in `.uproject`, the beta prompt already answered, and **no dialog
window in existence** (full window enumeration finds only the splash; under
`-nosplash -log`, only the console). **There is no modal.**

    last log line   LogTurnkeySupport: Completed device detection: Code = 0
    then            nothing; CPU frozen, ~2.4 GB flat, DDC growth 0

In a healthy run that line is followed by a long run of
`LogModuleManager: InternalLoadLibrary` — the plugin module-loading phase.
**The stall is at the START of that phase. That is a LOCATION, not a cause.**
Next cheap probes: the live console's final line (stdout is unbuffered where
the log file is not), and a run with the network down, since `MetaHumanSDK`
depends on `EOSShared` and a blocking network call fits every measurement.

~~The attended run's log records it verbatim:~~ **The line below was produced
by Ryan ANSWERING the prompt in the Plugins UI — a dialog being answered in a
RUNNING editor, not one raised at startup. Proximity in the same log file was
read as causation:**

    Message dialog closed, result: Yes, title: Message, text: Plugin
    'MetaHuman Creator' is a beta version... Are you sure you want to
    enable the plugin?

**Enabling a Beta plugin raises a confirmation modal.** Through the Plugins
UI a human answers it; through a `.uplugin` descriptor it is raised during
STARTUP with nobody to answer, and it blocks the game thread — the same
thread that services Python remote execution. The editor could not report why
it was stuck because the thing that would report it was the thing being
blocked.

**Every measurement was correct and none could reach the cause.** What
resolved it was a DIFFERENT REPRESENTATION — the log of the SUCCESSFUL
attended run — not sharper instrumentation of the hung one.

**Ryan enabled it through the Plugins UI, which wrote the entry into
`LandscapeLab.uproject`.** Not a rule-4 violation (that forbids *me* editing
it on disk; the editor writing it at his instruction is the sanctioned path),
but **ruling 2's purpose is partly defeated** — MetaHuman's enablement is no
longer attributable to the plugin that wants it. **DEBT, not defect:** once
it is confirmed to start cleanly, move the entry into
`LandscapeLabGameplay.uplugin` and drop it from `.uproject`. That also tests
the **UNVERIFIED** claim that the descriptor route works once the beta prompt
has been acknowledged.

**NEXT ATTEMPT USES THE EDITOR'S PLUGINS UI, ATTENDED.** The descriptor route
is right for a reproducible enable and wrong for a Beta plugin's FIRST
activation: anything that wants a click has nobody to click it, and a dialog
blocking the game thread blocks the only channel that could report it — the
same shape as the Save Content modal. **General rule: attended for the first
activation, reproducible for every one after.**

**Note `HairStrands`, `ChaosClothAsset`, `RigLogic` and `MetaHumanSDK` are
ALREADY enabled** for other reasons. `verify_gameplay_plugin` now reports the
MetaHuman stack without gating on it.

## UNIT 5 IS DONE — THE PLAYER WALKS A KILOMETRE

`walk003`: **1000.1 m of 1000, no stall, no fall.** Artefact
`_verify/20260815_unit5_walk_walk003.md`. Recipe **R-WALKTEST**; tool
`scripts/walk_character.py`.

The character resolves fully at spawn — `SKM_Manny_Simple`, `ABP_Unarmed_C`,
`IMC_LandscapeLabDefault`, **3 of 3 input actions** — and walks at exactly
**600 cm/s**, the configured `MaxWalkSpeed`, which is the cheapest proof the
recipe reached the engine. Spawn point placed by trace at ground + 120 cm
(`place_player_start`, restore point `pre-playerstart-place-20260815`); the
save added **exactly one** external actor package.

**RYAN RULED: GIVE IT THE ABILITY TO CLIMB.** `movement.profile` moved
`"walk"` → `"climb"` — still a KEY into `MOVEMENT_PROFILES` (70°), the recipe
still carries no angle, and `apply_character_recipe` derives
`CfgWalkableFloorAngleDeg`. **Use `SetWalkableFloorAngle`, never
`WalkableFloorAngle =`** — the setter also recomputes `WalkableFloorZ`, which
is what the floor test reads.

**A STRAIGHT KILOMETRE IS NOT AVAILABLE AT THE WALKING LIMIT.** From this
spawn the best clear run at 44.765° is **934 m**. At 70° many headings clear
1200 m. **Sweep headings at 1 m, not 2 m** — a 2 m sweep steps over the 1 m
ledges that stop the character.

**The two earlier stalls were terrain, and the terrain was right:** slopes of
**52.66°** and **64.39°** with 1 m rises of **74** and **320 cm** — past the
walkable floor AND the step height at once. A straight-line walker with no
steering stops there forever; that is the test's property, not the world's.

**FOUR DEFECTS IN THE INSTRUMENT ITSELF**, all in R-WALKTEST REJECTED: a
completed 1621-sample walk reported `NO MARKER` because the trace went in the
reply (now a file, with `--from-log` so analysis is reachable without the
failed path); **"FELL THROUGH: YES" on a clean walk** that merely descended
100 m over 1 km (the fall test is now geometric — worst excess **0.0 cm**);
`is_falling` logged `None` on all 645 samples and printed as **"0.0%"**
(`ACharacter` has no `get_character_movement()` in Python — it is on
`Pawn.get_movement_component()`); and a PowerShell `-replace` double-encoded
the script into a `U+FEFF` SyntaxError. **Use `Edit`, never a shell round
trip, on source.**

**Stated narrowly:** this is a straight line on a declared heading, **not the
inter-massif corridor** — that still has no spatial definition in this repo.
And `is_falling` was unreadable for this run, so the fall verdict rests on the
geometric test alone, not on two representations.

**Two skeletons now exist** — `/Game/Characters/Mannequins/Meshes/SK_Mannequin`
(ours) and the GV pack's, both 161 bones. Animations bound to one T-pose on
the other. Discriminate by PATH, never by bone count. Nothing may reference
the GV one.

---

## THE WORLD, as saved

    instances       219,659   planned == counted in world, 4 tiers
    materials       wind-OFF on SpruceSub + SpruceSapling (verified, see below)
    understory      GT_alpine_8k_Blueberry, 8 varieties, 12.0/10m2, wind-OFF
    frame cost      GPU 7.92 ms  (EDITOR VIEWPORT class — not PIE, not cooked)
    saved           1,095 packages, all re-read clean, 0 removed
    material        M_Alpine8K, 298 expressions, 0 orphaned, 37 samplers 0 mismatch

    Conifer 63,981 | ConiferPine 47,261 | SpruceSub 55,004 | SpruceSapling 53,413

Grounding closed by TWO representations on ALL four species: heightmap over
every instance (max 0.001 m, 0 outside) and engine collision 500/500 per
species (p50 +0.005–0.006 m, 0 floating, 0 buried).

## FOUR DOCUMENTS DELIVERED — read these before planning anything

| File | What it is |
|---|---|
| `PHASE2_PLAN.md` | Phase 2 = the world becomes playable. 8 domain briefs, budget reconciliation, adversarial critic. |
| `WORLD_ARCHITECTURE.md` | **A RECOMMENDATION, NOT A RULING.** Multi-region, 2×2 atlas. Awaiting one line from Ryan. |
| `terrain/regions/` | 5 `.terrain` files + authoring notes + `README.md` runbook. All pass `--check-refs`/`--check-spec` on two independent runs. |
| `plans/RECIPES_draft_*.md` | 3 drafts staged for review, NOT written into `RECIPES.md` (Ryan's file). |

---

## TWO THINGS NEED RYAN, AND THE FIRST UNBLOCKS THE MOST

1. ~~**THE REGION RULING.**~~ **RULED BY RYAN 2026-08-15: MULTI-REGION,
   2×2 ATLAS**, ≤2 co-resident, adjacent borders walkable, non-adjacent
   travel by airship. Recorded in `WORLD_VISION.md` at both reserved places,
   marked as **Ryan's own ruling** — the 2026-08-03 withdrawal was about WHO
   decided, not WHAT, and a future session must not read it as applying to
   this. **The tripwire is discharged; region-shaped work is unblocked.**
   `WORLD_ARCHITECTURE.md` is now the ruled architecture, and the five
   `terrain/regions/*.terrain` files are no longer speculative.
2. **THE LICENCE GAP.** ~3.5 GB of Fab packs have no licence record and terms
   are NOT recoverable from disk (nothing but `.uasset` inside). Needs Ryan's
   Fab library page. The only unmet R-ASSET requirement.

## WHAT TO DO NEXT WITHOUT RYAN, RANKED

1. ~~**ONE PIE CAPTURE.**~~ **DONE 2026-08-15 — SEE "UNIT 1 IS MEASURED"
   BELOW. The plan's headline risk is CONFIRMED.**
   **UNITS 2 AND 3 ARE ALSO DONE** — see "UNITS 2 AND 3" below. **Unit 3
   found a real defect: the largest tree species collides with nothing.**
   **UNIT 4 IS DONE TOO — PHASE A OF `PHASE2_PLAN.md` IS COMPLETE.**
   **NEXT: PHASE B.** Unit 5 (a player walks on the terrain) now has its
   skeleton ruling, and its first act is migrating the engine template
   mannequin set. Two prerequisites are named and unbuilt: a trunk capsule on
   `SM_PVE_Norway_Spruce_01_A` (unit 6), and the spawn-into-PIE premise for
   the per-character cost experiment.
2. **Navmesh tile overflow** — 812,800 cm / `TileSizeUU` 1000
   (`BaseEngine.ini:3052`) = 813 tiles/side × 3 layers = **1,982,907 against
   a hard ceiling of 1,048,576** (`RecastNavMesh.cpp:551`). A 1.89× overflow
   that logs an error and **silently clamps**. Config fix; do it after the
   region ruling.
3. **The three `RECIPES.md` drafts** — they found 5 numeric errors in this
   project's own artefacts; review before merging.
4. **Hook-scope review** — EIGHT agent-loop reports across three workflows,
   several triggered by an agent's own text quoting a line it had withdrawn.
   The guards are correct; their scope against subagents is not.
5. `rebuild_terrain.py:96` names its output for region ONE regardless of the
   project given. Anyone building regions 2–5 gets region one's filename.

---

## UNIT 1 IS MEASURED — THE FIRST PIE FRAMES THIS PROJECT HAS EVER PRODUCED

Tools `scripts/probe_pie.py` and `scripts/measure_pie_cost.py`; recipe
**R-PIE**; narrative in LESSONS 2026-08-15. Artefacts
`_verify/20260815_pie_unit1_pie001.md` (categories OFF, the clean cost run)
and `_verify/20260815_pie_unit1_pie002.md` (categories ON, the diagnostics).

    station              GPUTime   GameThread   RenderThread   RHI
    forest_floor           7.816       7.198          5.309    2.779
    canopy_250m            5.082       7.084          5.198    2.765
    airship_1500m          3.404       7.022          5.055    2.523

**THE CONTROL REPRODUCES:** 7.816 ms against the editor series' 7.92 at the
same camera, inside the plan's ±0.2 ms bar — despite 4 resident landscape
proxies against 256 force-resident, FOV 90 against 75, and gameplay ticking.

**THE PLAN'S HEADLINE RISK IS CONFIRMED. GPU HALVES WITH ALTITUDE; THE GAME
THREAD DOES NOT MOVE.** 7.82 → 3.40 against 7.20 → 7.02. The game thread is
a FIXED ~7 ms with **zero gameplay** — no AI, no enemies, one dynamic
instance. The plan's 8.0 ms for AI perception + EQS at engine defaults would
land it near 15 ms against a 16.67 ms budget before one enemy exists.
**STATED AS A LIMIT: PIE runs inside the editor process, so this game thread
carries editor overhead. 7 ms is an UPPER BOUND on a cooked build, not the
shipping number.** No cook has ever been produced here.

**VIRTUAL SHADOW MAP PAGES ARE NOT THE CONSTRAINT.** `VSM/FreePages`
1820/1978/2024 of the 2048 pool — peak usage **228 pages, 11%**. Aim no work
at them. (The plan named `SinglePageCount`+`FullCount`; those count shadow
MAPS, not pages. `FreePages` is the direct measure.)

**THREE COMMANDS THAT RETURNED SUCCESS AND DID NOTHING** — all three now in
R-PIE REJECTED:
- **`CsvCategory VSM 1`, which `PHASE2_PLAN.md` unit 1 prescribes verbatim,
  is a SILENT NO-OP.** `CsvProfiler.cpp:1138-1148` compares argument 2
  against the literal words `enable`/`disable`; `"1"` matches neither and the
  command falls through to a usage error without enabling anything. Correct
  form `CsvCategory VSM enable`. The bare form TOGGLES (`:1152-1153`) and is
  not idempotent.
- **A ground trace taken before the pawn is teleported can never hit** — WP
  streams around the pawn, which spawns at the origin (no `PlayerStart`).
- **`get_player_view_point()` read in the teleport's own tick returns the
  PRE-MOVE cache**, gated on `GetCameraCacheTime() > 0`.

**DO NOT MIX THE TWO TAGS.** Enabling the diagnostic categories costs
**+0.52 ms GPU** at `forest_floor` (7.816 → 8.338), single variable. The
instrument's own settings are part of the calibration class.

**`SceneCulling/NumStaticInstances` DOES NOT REPRODUCE** — 284,424 at all
three stations in `pie001`, 284,424/4,264/4,264 in `pie002`, same order same
session. **Do not quote it** until it has had its own single-variable run.

Also established: the level has **zero `PlayerStart` actors** and World
Settings' `default_game_mode` reads **None**, confirming `PHASE2_PLAN.md`
item 1 from the live world rather than from the ini. Editor viewport is
**1614×943** — the denominator `measure_frame_cost` never recorded.

## UNITS 2 AND 3 ARE DONE TOO — AND UNIT 3 FOUND A REAL DEFECT

**UNIT 2 (offline, `scripts/audit_step_height.py`, recipe R-WALK, artefact
`_verify/20260815_unit2_step_height.md`).** The number the plan asked for is
**19.87%** and it is **not a finding**: 45 cm over a 100 cm cell is 24.23°,
the mount profile admits 35° = 70 cm/cell, so every slope between trips the
metric while being entirely walkable. **At 1 m/vertex a step is below Nyquist
and cannot be represented at all** — `MaxStepHeight` is not a terrain
constraint here, only a constraint on PLACED geometry. (Nanite displacement
does not change this: collision is the heightfield, not the displaced
surface.)

**The real finding, and then its withdrawal.** `traversability()` reads mount
**29.26% reachable against the recipe's own `min_connected_frac` 0.8** — a
FAIL by ~3× on the PRIMARY movement mode, 219,828 regions. **The control
withdraws it:** box-reduce and reachability goes 29.26% → 33.28% → 74.61% →
**94.39%** at 1/2/4/8 m, regions 219,828 → 2,340. Same terrain. **The
fragmentation is a sampling artefact.**
**THE ACTUAL DEFECT IS THAT THE BAR HAS NO DECLARED SCALE** — it was written
for `recipes/alpine.json` at **4 m/vertex** and the 8K recipe inherited the
number without its denominator. Fifth resolution-dependent parameter the 8K
re-terrain has exposed, first one living in a BAR. **RECOMMENDED, NOT
APPLIED:** make the evaluation scale a physical property of the AGENT (a
mount occupies 2–4 m) and declare it beside `MOVEMENT_PROFILES`. Not taken
unilaterally — a gate whose bar moves to make a failing number pass needs its
reasoning ratified first.
**NOT MEASURED:** the corridor half. **The inter-massif corridor has NO
spatial definition in this repo** — `WORLD_VISION.md:304` is prose only.
Reported as "could not look", which is not a pass. One ruling closes it.

**UNIT 3 (`scripts/measure_mesh_collision.py`, recipe R-COLLIDE, artefact
`Free/_measured/mesh_collision.json`). IT FOUND THE DEFECT IT EXISTS TO
FIND.**

    species         system      simple prims   nanite   tris LOD0
    Conifer         instanced        0          True       2335
    ConiferPine     instanced        2 sphyl    False     27824
    SpruceSub       instanced        1 sphyl    False     20695
    SpruceSapling   instanced        1 sphyl    False      2604

**`SM_PVE_Norway_Spruce_01_A` — 63,981 instances, the LARGEST species — has
ZERO simple collision primitives.** And the failure is invisible to every
check that would be run: `body_setup` is **present** (not null), the profile
**already reads `BlockAll`**, `QUERY_ONLY` would set and read back fine,
`CreateAllInstanceBodies` does **not** early-return, the engine logs nothing
— and a line trace goes straight through the trunk.
**THE PLAN'S OWN GUARD DOES NOT CATCH IT.** `InstancedStaticMesh.cpp:2877-2882`
fires on a **NULL** BodySetup, not an EMPTY one. Ask `agg_geom`'s element
count, never "does it have a BodySetup".
**WHY THIS ONE:** it is the only Nanite mesh and the only one this project
EXPORTED rather than received. The skeletal→static PVE export (R-BAKE) does
not author simple collision and nothing in its verification asks.
**GOOD NEWS:** the mesh is **ours and tracked**, not gitignored vendor
content, so a capsule can be authored at source and committed. **NOT DONE —
that is unit 6**, it mutates an asset, and the capsule belongs in a recipe
declaration. **NEVER `UseComplexAsSimple`** (2,335 tris × 63,981 in the query
scene).

## UNIT 4 IS DONE — PHASE A IS COMPLETE

Deliverable `plans/characters_brief.md`. Instrument
`scripts/probe_skeleton.py`, recipe **R-SKEL**, artefact
`Free/_measured/skeletons.json`.

**THE SKELETON, CITED BY BONE PROBE** (controls `pelvis`/`hand_l` pass on all
four, so the zeros are real absences):

    UE4_Mannequin_Skeleton          68 bones   0 of 4 UE5 markers   UE4
    /Game/Mannequin/SK_Mannequin    68 bones   0 of 4               UE4
    GV pack SK_Mannequin           161 bones   4 of 4               UE5
    GV pack SKM_Manny              161 bones   4 of 4               UE5

**RULING: UE5 skeleton, and the source is the ENGINE TEMPLATE, not the
in-project GV copy.** The GV Manny has **NO physics asset** (so no ragdoll)
and its **LOD0 and LOD1 are both 48,779 verts** — a chain whose first
reduction reduces nothing. The template set carries `PA_Mannequin`, 3 Control
Rigs, `SKM_Manny_Simple`/`SKM_Quinn_Simple` and all 102 anims under the
engine EULA. **Nothing has been migrated yet.**

**`ASSETS.md`'s "UE template content" row was WRONG** — it gives
`Content/Mannequin` the role "retarget target for GASP" and that is the UE4
skeleton. **Corrected by APPENDING to `ASSETS.md`**, not by editing the row.
Its `verified` column always read NO, which is the part that behaved.

**THE ANIMATION HEADLINE SHRINKS 60%.** `PHASE2_PLAN.md` §3 advertises "~110
animations"; measured **102**, of which **68 are Rifle and Pistol** —
shooter content. Usable for a melee RPG: **42**. And **the 8 hit reacts are
filed under `Anims/Rifle/HitReact/`**, so "take the Unarmed folder" loses all
eight. Free and complete: 4 melee attacks, 8-way walk, 8-way jog,
jump/fall/land/dash/walljump, idle, blendspace, AnimBP. **Absent: any
mounted animation at all** — and `WORLD_VISION.md` ruling 2b sizes POI
spacing against mounted speed.

**A TRAP THE FIX CREATES:** after migration there will be **two** 161-bone
UE5 mannequin skeletons, both plausibly named `SK_Mannequin`. Animations
bound to one play as a **silent T-pose** on the other. Equal bone counts are
not identity — compare the resolved skeleton PATH, which `probe_skeleton`
prints.

**NO PER-CHARACTER MILLISECOND FIGURE WAS INVENTED**, because ruling 12
records that every per-domain allocation in the original briefs was PROPOSED
and read like a ruling. The brief specifies the experiment instead, and names
the premise to settle first: **Python's spawn functions target the EDITOR
world, not PIE** (`EditorActorSubsystem.spawn_actor_from_class`, PythonStub
641645), so whether transient editor-world actors duplicate into PIE decides
the approach — same shape as `probe_pie` settling remote exec.

## CORRECTIONS TO CLAIMS THIS SESSION ITSELF MADE — read before trusting an artefact

- **THE NOISE-FLOOR CONCLUSION WAS WRONG AT `trunk_base`.** I attributed the
  elevated floor to renderer temporal accumulation. Applying the wind-off
  overrides dropped it **0.0198–0.0258 → 0.0098, −57%**, far outside the ±30%
  run-to-run spread. **Wind was dominant there.** The animation check that
  produced the error probed only the PRE-D4 species — both probes correct,
  carried forward to a world that had changed underneath them.
  Residual is real: 0.0098 is still 3.29× the bare floor. `forest_floor`'s
  −17% sits INSIDE the noise band and is **unresolved, not clean**.
  Artefact: `_verify/20260815_wind_discriminator_result.md`.
- **The floor is PER-STATION and spans 8×** (0.0024 aerial → 0.0198
  close-up). 0.00298 was never wrong — it is still right for bare-terrain-like
  frames. It is wrong quoted against a vegetation-filled one. **At n=3 these
  are an order of magnitude, not constants.**
- **`measure_lod_materials`'s substitution exemption was far too wide** — one
  swapped material disabled BOTH refusals. Fixed: must be the LAST LOD and a
  COMPLETE replacement.
- **The grass override read-back was dead code** — computed, transported,
  discarded, while a comment claimed verification. Now compared and gated.
- **108,417 trees spent this session on vendor materials with wind ON**,
  because `_VEG` could not express `override_materials` and `place_foliage`
  never set it. Fixed and applied.

## HAZARDS — each destroys work silently

1. **DO NOT NORMALISE THE PN LOD GROUPS.** `SmallProp` is `NumLODs=4`; the 14
   big trees have 5 and **LOD4 IS THE IMPOSTER**. `SetLODGroup` truncates
   (`StaticMesh.cpp:5605-5607`, `:5944-5974`). The tidy-up is the destructive
   act.
2. **DO NOT ENABLE NANITE on the PN meshes.** They render the classic LOD
   chain; Nanite bypasses the imposter.
3. **EVERY SCATTERED MESH NEEDS ITS OWN WIND-OFF MIs.** Built for
   `spruce_half_01`, `spruce_small_05` and the 8 blueberries. Nothing else.
4. **NEVER PUT `.py` IN A REMOTE-EXEC PAYLOAD** — including in a comment.
   `ExecuteFile` runs `FindFirst` over the whole command and turns the script
   into a path. Cost this session one silent no-op run; cost 2026-08-01 two
   hours. Guards exist at `place_foliage.py:1037` and siblings.
5. **`Height 2500.0` in a `.terrain` is the PROJECT range, not the build's
   span.** Taking it as the span gives a Z scale **2.7× too tall**.

## UNVERIFIED, STATED PLAINLY

- **Nothing has been opened in Gaea.** Every region landform claim is a
  PREDICTION from parameters — no build, no export, no measured Z span.
- **No structural diff** of the 5 region files against the canonical was run
  by me. `--check-refs` verifies references, not "nothing structural moved".
- **No PIE or cooked frame has ever been produced by this project.** Cook is
  additionally mis-pointed: `GameDefaultMap=/Engine/Maps/Templates/OpenWorld`
  (`DefaultEngine.ini:4`) — a cook today cooks the wrong map and exits 0.
- **HLOD verified ABSENT** (two settings assets, no built output) while
  `WORLD_VISION` ruling 2a makes aerial readability first-class.
- **Aerial readability still unproven in-world.** `ridge_wide` cannot
  adjudicate it — untuned aerial perspective swamps the forest at range.
- **Disk is 437 GB free, not the 655 GB recorded below.** Stale by ~220 GB.
- Only 2 of 20 stations re-measured post-fix.

**RESTORE POINTS:** `pre-d4-rescatter-220k-20260815`,
`pre-d3-blueberry-material-rebuild-20260815`, `pre-pve-spruce-adoption-20260815`.

---

# CURRENT STATE — 2026-08-15 (night) — D1–D4 ALL EXECUTED. THE FOREST HAS STRUCTURE.  
**⚠ SUPERSEDED by the block above.**

**Tree clean. Editor PID 11964 on `/Game/Alpine8K`, world SAVED** (1,095
packages, all re-read clean, 0 removed). Every one of the four delegated
rulings is now built and verified, not merely decided.

### THE WORLD

    instances        219,659   planned == counted in world
    reserve           30,341   under the shared 250,000 ceiling
    frame cost     GPU 7.92 ms   against an 11 ms abort bar
    species        Conifer 63,981 | ConiferPine 47,261
                   SpruceSub 55,004 | SpruceSapling 53,413
    understory     GT_alpine_8k_Blueberry, 8 varieties, 12.0 /10m2, wind-OFF
    material       M_Alpine8K 147,145 B, 298 expressions, 0 orphaned,
                   37 samplers 0 mismatches

**+65,863 instances (+43%) cost +0.18 ms**, because the new tiers are light
and carry imposter LODs — the D2 intake paying for the D4 budget, which is
why the ruling made them ONE re-scatter.

### THE FOUR-TIER STAND, AND WHY IT IS NOT ONE RAMP

The height band was a HARD window: uniform density to the top edge, then
nothing. New shared prior `placement_priors.closure_ramp` **SCALES** where
`centred_bias` **REDISTRIBUTES** — flow says WHERE trees stand, closure says
HOW MANY, and a subalpine stand genuinely thins toward treeline.

**The falloff differs per tier**, which is the compositional half of it. One
shared ramp would thin all four together and give a smaller copy of the same
uniform forest:

    Conifer        1.00 -> 0.15   29.3 m canopy; mature crowns go first
    ConiferPine    1.00 -> 0.20
    SpruceSub      1.00 -> 0.30   16.7 m sub-canopy
    SpruceSapling  1.00 -> 0.55   4.5 m regeneration — this IS the krummholz

Acceptance rates confirm it: 22.4% canopy against 30.0% saplings, from one
mask and four ramps. The band now ends sapling-dominated rather than empty.

### GROUNDING — CLOSED BY TWO REPRESENTATIONS, ALL FOUR SPECIES

Every position was re-rolled, so the previously-traced species needed it
again. Heightmap over all 219,659: max 0.001 m, **0 outside**. Engine
collision 500/500 per species: p50 +0.005–0.006 m, **0 floating, 0 buried**.
They share no source.

### THREE HAZARDS THAT SILENTLY DESTROY WORK — carried forward

1. **DO NOT NORMALISE THE PN LOD GROUPS.** 15 of 21 carry `SmallProp`
   (`NumLODs=4`); the big trees have 5 and **LOD4 IS THE IMPOSTER**.
   `SetLODGroup` calls `SetNumSourceModels(4)` unconditionally
   (`StaticMesh.cpp:5605-5607`), clearing everything above it (`:5944-5974`).
   The tidy-up is the destructive act.
2. **DO NOT ENABLE NANITE on the PN meshes.** Nanite is False on all 21 and
   must stay so — they render the classic LOD chain, and Nanite bypasses the
   imposter.
3. **EVERY SCATTERED MESH NEEDS ITS OWN WIND-OFF MIs.** The PN and blueberry
   masters both carry `Level 1/2/3 Wind`. Built for `spruce_half_01`,
   `spruce_small_05` and all 8 blueberries; nothing else.

### FOUR DEFECTS FOUND AND CLOSED THIS SESSION

- **The instanced cull gate** accepted a missing `cull_distance_m` and `0.0`
  — which `FoliageType.h:292` documents as DISABLING it, the configuration
  that cost this project a GPU hang. The 2026-08-08 fix went into the GRASS
  branch forty lines away and was never swept back to the path where the
  hang happened. Now required, interval open at zero, 4 permanent probes.
- **`measure_lod_materials` told me to delete the imposters**, because it
  computed what a LOD LOST and never what it GAINED. Substitution and loss
  are different facts.
- **The engine-derived registry exempted meshes from the grass pivot gate**
  — a hole I opened that morning, found by the blueberry work that afternoon.
  Blender-normalised means pivot-at-base; engine-derived means only measured.
- **The builder, the validator and two audits all passed a false claim**: the
  blueberry wind-off overrides were declared, validated, handled in the
  payload, reported successful — and read back `NONE` off the saved asset,
  because the recipe's variety dicts are TRANSFORMED before reaching the
  payload and the key was dropped there
  (`make_landscape_material.py:2932`).

### OPEN, STATED PLAINLY

- **AERIAL READABILITY IS STILL UNPROVEN IN THE REAL WORLD.** `ridge_wide`
  cannot adjudicate it — the untuned aerial perspective swamps the forest at
  that range (a pre-existing issue: fog "applied and rendering, never
  tuned"). The only imposter evidence is a 35 m forced-LOD comparison. The
  imposters are the reason D2 chose this pack, so this matters.
- **Alpine8K's frame-to-frame floor is ~0.012, 3.94x the 0.00298 quoted
  everywhere**, present with grass off and no shader compiles — renderer
  temporal accumulation, not motion. Every pixel A/B judged against 0.00298
  on this world over-credited by ~4x. **A noise floor belongs to a SCENE AND
  ITS SETTINGS.** No pre/post D4 frame A/B was taken.
- **`foliage.CullAll` reads back 1 and culls nothing** on Nanite foliage
  (`HierarchicalInstancedStaticMesh.cpp:63-67` is the HISM path). The
  2026-08-14 "+2.28 ms conifers plus grass" may be **grass alone**.
- **The placed forest does NOT animate** — neither tree material declares a
  wind parameter. Blueberry would have, and is overridden.
- **LICENCE GAP.** The PN packs and ~3.5 GB of other Fab content have no
  licence record; terms are not recoverable from disk. **Needs Ryan's Fab
  library page.**
- **`RECIPES.md` has no entry for any of this**, and R-BAKE / `:1545` still
  name `fir_tree_01_c_LOD0` as the live conifer. Additive, but Ryan's files.
- Deferred by ruling: the four Baltic Pine PVE exports; blackberry and
  raspberry; the rocks.

**NEXT:** a named `camera_epoch` full re-site, then a fresh sweep — the last
step of the ruled sequence. Note the 19 inherited stations were sited for a
different forest.

**RESTORE POINTS:** `pre-d4-rescatter-220k-20260815`,
`pre-d3-blueberry-material-rebuild-20260815`,
`pre-pve-spruce-adoption-20260815`.

---

# CURRENT STATE — 2026-08-15 (late) — D2 IS MEASURED, WIRED AND UNSCATTERED

**Tree clean. Editor PID 11964 alive** (the previous editor, PID 23888, was
closed from the UI mid-session; see below). **NOTHING HAS BEEN SCATTERED.**
`/Game/Alpine8K` still holds the 153,796-instance forest from before this
session and is untouched by all of it.

### THE RECIPE NOW DECLARES A FOUR-TIER FOREST THE WORLD DOES NOT CONTAIN

That divergence is deliberate — D4's ruling is ONE re-scatter, because every
mass re-scatter re-rolls every position.

    species          share   cull      scale       resulting height
    Conifer          0.32    730 m   0.60-1.15     17.6-33.7 m  canopy
    ConiferPine      0.23    730 m   0.60-1.05     canopy
    SpruceSub        0.25    730 m   0.70-1.15     11.7-19.2 m  sub-canopy  NEW
    SpruceSapling    0.20    180 m   0.60-1.60      2.7- 7.2 m  regeneration NEW

Instanced `weight_share` totals exactly 1.0. Conifer/ConiferPine were
REBALANCED from 0.60/0.40 — the new tiers take their share from the canopy
rather than being added on top. Recipe validates with **0 foliage errors**.

### D2 — DONE EXCEPT THE SCATTER. The headline is worth not re-deriving.

**THE IMPOSTER IS LOD4 OF THE MESH**, bound as material slot 3 at 4-6
triangles, screen size 0.10-0.17. BACKLOG's aerial-readability item closes
with vendor content: no imposter actor, no second scatter, no extra system.
`MA_Imposter` **recompiles clean in 5.8**, 0 errors. Rendered against LOD0 at
35 m — several times closer than its real selection range, so a harder test
than reality — it reads as the same tree (IoU 0.689). It **loses cast
shadows**, which the mae does not capture, and saplings degrade to blocky
clumps, so the imposter tier is a BIG-TREE feature.

**21 meshes, all StaticMesh, 0.56-16.95 m, largest LOD0 28,510 tris** —
17.7x lighter than the incumbent fir. Full table:
`_verify/20260815_pn_spruce_forest_intake.md`, raw
`Free/_measured/pn_spruce_forest.json`.

### THREE HAZARDS — each one is a way to silently destroy work

1. **DO NOT NORMALISE THE LOD GROUPS.** 15 of 21 meshes carry `SmallProp`,
   6 carry `NAME_None`, inconsistently — the same tree differs between its
   high and low variants, and the urge to tidy it is strong. `SmallProp` is
   `NumLODs=4` (`BaseEngine.ini:2685`); the big trees have 5.
   `SetLODGroup` calls `SetNumSourceModels(4)` unconditionally
   (`StaticMesh.cpp:5605-5607`), which clears the mesh description and bulk
   data above the new count (`:5944-5974`). **The tidy-up deletes every
   imposter.** The engine's own comment three lines up promises the opposite.
2. **DO NOT ENABLE NANITE on the PN meshes.** Nanite is FALSE on all 21 and
   must stay so: they render through the classic LOD chain and LOD4 *is* the
   imposter, which Nanite bypasses. (The placed PVE spruce IS Nanite; that is
   fine, Nanite is per-mesh.)
3. **EVERY SCATTERED MESH NEEDS ITS OWN WIND-OFF MIs.** Only
   `spruce_half_01` and `spruce_small_05` have them.

### THE WIND ANIMATES, AND THE MEAN NEARLY HID IT

Three frames 5 s apart, one parked camera, **no Blueprint in the level**:
mean mae 0.005275, only 1.4-2.1x the noise floor — dismissible as a mean.
Conditioned on where it happens it is not: the 6x-amplified diff is a
**solid filled silhouette of the tree**, sky and static ground plane black.
NN22 in frame coordinates — whole-frame mae is a layer-scoped statistic
whenever the subject does not fill the frame.

**Fixed with zero vendor edits.** Wind rides STATIC SWITCHES
(`Level 1/2/3 Wind` + three `Bending`) on `MA_Summer`/`MA_Winter`/
`MA_Imposter`; false in a child MI compiles the branch out. Seven MIs under
`/Game/Materials/PN_NoWind/` (ours, tracked). `check_fab_boundary` still
reports **11** changed — the same pre-existing 11, not 12.

**Proven by RENDER, not by read-back:** mean mae 0.005275 -> **0.002310**,
2.3x quieter and **0.78x the bare-terrain floor**, and the diff changed
character from solid silhouette to sparse speckle on needle edges. Stated as
a limit: this cannot fully separate small residual motion from TAA speckle —
the evidence is the statistic AND the character change together.

Tool: `scripts/make_nowind_material_instances.py`. Its
`--apply-in-open-level` REFUSES real worlds.

### A PRE-EXISTING DEFECT FOUND AND CLOSED — the cull gate

Instanced vegetation species accepted a **missing** `cull_distance_m`, and
**0.0**, which `FoliageType.h:292` documents as DISABLING the cull — the
exact configuration that cost this project a GPU hang. The 2026-08-08
mandatory-cull fix went into the GRASS branch forty lines away and was never
swept back to the instanced path **where the hang actually happened**, even
though the grass comment names "the INSTANCED path" as the origin.

Now required, interval OPEN at zero, bound (0, 5000] matching
`_validate_rock_species`. Four permanent `prove_gates` probes beside the
grass four. Positive control first; all recipes re-validated, 0 regressions.

### CORRECTIONS TO THE PREVIOUS CURRENT STATE

- **The D2 ruling's `LODGroup=None` premise is FALSE** — measured, 15 of 21
  carry `SmallProp`. Its cull/screen-size conclusion survives in a different
  form: screen sizes are vendor-authored and explicit already; **cull** was
  the real gap and is now a refusal.
- **"21 baked 4096² atlases"** is **7 imposters x 3 maps** (A/N/O), all 4096².
- **`ASSETS.md` rows are DONE**, including the correction that the Megaplants
  section still read "NOT ADOPTED / not spawned, not rendered" while 92,519
  instances stand. Appended rather than edited, so the intake-time belief
  survives.

### OPEN, STATED PLAINLY

- ~~**The placed Alpine8K forest has NEVER been tested for animation.**~~
  **ANSWERED 2026-08-15: IT DOES NOT ANIMATE.** Neither `MA_Foliage_Trees`
  (38 scalars, 19 switches, 20 vectors — all shading or colour) nor
  `ScotsPine_01_Leaves_Mat` (3 scalars, 0 switches) declares a single wind,
  wobble, bending or time parameter, against a PN master carrying twelve;
  and removing the grass left variance unchanged. Artefact:
  `_verify/20260815_alpine8k_animation_check.md`.
- **BUT THE FLOOR IS 4x WHAT WE QUOTE, AND THAT IS THE REAL FINDING.**
  `/Game/Alpine8K` at `forest_floor` re-renders itself at **mae 0.0117 =
  3.94x the 0.00298**, over 23% of the frame, with grass off and zero shader
  compile workers. Renderer temporal accumulation, not motion. **Every pixel
  A/B judged against 0.00298 on this world has over-credited differences by
  about 4x.** 0.00298 was measured on `/Game/Alpine` — 2017², pre-Lumen,
  pre-HQ-profile, pre-volumetric-fog. **A noise floor is a property of a
  SCENE AND ITS SETTINGS, not of a project**, and must be re-derived with
  them attached, exactly as R13 insists for GPU figures.
- **`foliage.CullAll` NO LONGER ISOLATES TREE COST — it reads back 1 and
  does nothing.** Declared in `HierarchicalInstancedStaticMesh.cpp:63-67`,
  the **HISM** path; `r.Nanite.Foliage` is 1 and the placed spruce is Nanite,
  so it never enters that path. Measured: culling moved the canopy half of
  the frame by -8.81 points of dark coverage while the GRASS half moved
  -14.97. **Reaches backwards:** the 2026-08-14 figure "vegetation ON 8.14 /
  CULLED 5.86, +2.28 ms ... 154,018 conifers plus grass" may be **grass
  alone** if `r.Nanite.Foliage` was already 1 then. NOT resolved — it needs
  that cvar's value at that run, not a guess. **No future decomposition may
  use `foliage.CullAll` on Nanite foliage.**
- **D3's landscape-material rebuild is ATTENDED** (B-BUILD-UNKNOWN: the
  builder can report catastrophe on a graph that is fine, and it clears
  destructively before rebuilding). Not run. `PN_WildBerries` (153 files,
  635 MB) and `GV_FreeShrubsPack` are already on disk — D3 needs no download.
- **LICENCE GAP.** This pack and the other ~3.5 GB of Fab packs have no
  licence record, and terms are NOT recoverable from disk — the packs contain
  nothing but `.uasset` files. **Needs Ryan's Fab library page.**
- **The previous editor was closed from the UI mid-session** (`CLOSE_SLATE_MAINFRAME`
  twice, a `Save Content` prompt each time, then `QUIT_EDITOR`). **Nothing was
  written** — 0 vendor files modified, confirmed two ways. On relaunch a
  `Restore Packages` modal offered `MA_Imposter`, dirtied by my own
  `--recompile`; answered **Skip Restore**. `probe_material.py` now warns that
  `--recompile` costs a dirty package, an autosave, AND a next-launch modal
  that blocks the game thread and therefore all MCP.
- **Still no `RECIPES.md` entry for this pack**, and `RECIPES.md` R-BAKE /
  `:1545` still name `fir_tree_01_c_LOD0` as the live conifer. Additive, but
  they are Ryan's files.

**SEQUENCE FROM HERE:** D3 material rebuild (attended) -> the single D4
re-scatter to ~220,000 as a closure gradient -> a named `camera_epoch`
re-site -> fresh sweep.

---

# CURRENT STATE — 2026-08-15 — THE FOREST IS REAL. Ryan asleep, fable ruling D2–D4, D1 done.

**Tree clean. Editor PID 23888 alive on `/Game/Alpine8K`, world SAVED.** Ryan
granted full authority overnight and delegated design rulings to the fable
model. D1 is executed; D2–D4 are RULED AND UNBUILT, which is the whole point
of this handoff.

### WHAT CHANGED TONIGHT

    conifer      fir_tree_01_c_LOD0  ->  SM_PVE_Norway_Spruce_01_A
                 14.52 m alpha-card  ->  29.31 m Nanite, real needle geometry
    scale_range  [0.7, 1.4]          ->  [0.6, 1.15]   (17.6-33.7 m)
    placed       153,796 counted in world == planned, 1,086 packages saved
    frame cost   GPU 8.14 -> 7.76 ms at forest_floor  (CHEAPER, and denser)

Frame: `_verify/20260815_alpine8k_pve_spruce_forest_floor.png`. The station
whose standing complaint was "scrub, not an alpine forest" now photographs a
forest.

**THE ROUTE, so nobody re-derives it.** Megaplants ships its trees as
SkeletalMesh ARMATURES — trunk and branches, no needles; the foliage is
assembled by the Procedural Vegetation editor. Baking the armature produces a
faithful copy of the wrong thing, and every gate passed because they all
measured fidelity-to-source. The fix is one dropdown: PVE Export Settings
`Export Mesh Type: Skeletal Mesh -> Static Mesh`. Full procedure and the
per-node trap in `recipes/pve_export_settings.json` and LESSONS 2026-08-15.

### CORRECTIONS TO THE PREVIOUS CURRENT STATE — it was wrong twice

- **"154,018 conifers"** — the count is **153,796** (92,519 Conifer + 61,277
  ConiferPine), counted in the world by the placement's own verification.
- **"NO COLLISION TRACE AND NO GROUNDING VERIFY HAS RUN"** — both have now
  run and PASSED, and the collision half had already run at `ad05ba74` four
  hours after that line was written. Grounding is closed by TWO
  representations: heightmap over all 153,796 instances (max 0.001 m, 0
  outside) and engine collision at 500 per species (p50 +0.006 m, 0 floating,
  0 buried, and the 61,277 Scots pines had never been traced by anything).
  Artefact: `_verify/20260815_alpine8k_grounding_both_species.md`.

### MEASURED, NOT INFERRED — three questions closed by a live read

- **The scalability groups did NOT degrade this editor.** `r.Streaming.MipBias`
  **0** (textures at FULL resolution — the "running one mip down" worry is
  refuted), `r.VolumetricFog` **1**, `r.Shadow.Virtual.MaxPhysicalPages`
  **2048** not 512. `r.TSR.History.ScreenPercentage` reads 100 and does NOT
  discriminate — both hypotheses predict it, and that is recorded rather than
  letting 3-of-4 read as 4-of-4.
- **`r.Nanite.Foliage` = 1 on the running process**, not inferred from the
  ini. Its consumers cache it as `static const bool` on first call, so the
  file was never sufficient evidence.
- **`Slate.bAllowThrottling` = 0.** Throttling is already off and the config
  is CORRECT. Two survey lanes independently recommended changing the ini key
  and **both were wrong** — `EditorPerformanceSettings.cpp` PostInitProperties
  calls `ExportValuesToConsoleVariables` on that property, so the key IS the
  property name. Their fix would have broken a working setting. Two lanes
  agreeing was one measurement, not two; they shared a source.

### D1 DONE — four cameras were INSIDE the hill

19 of 20 cameras were inherited byte-identical from the 4 m/vertex
`recipes/alpine.json`. Lifted Z only, XY and rotation preserved:

    sweep_0060  +6.04 m    trunk_base  -> +4.45 m
    sweep_0350  +5.07 m    lod_far     -> +2.87 m

**Two representations agree within 0.07 m** — the survey computed burial from
the heightmap PNG, these lifts come from engine line traces. `forest_floor`
(+1.93 m, fine) is UNTOUCHED at z=28732.7 cm because it carries the
8.14 -> 7.76 ms series and both canopy A/Bs. New tool `scripts/fix_camera_z.py`;
`site_ground_cameras.py` cannot do this (writes only `ground_*`, and reads
`scale_z` where this recipe carries `z_scale_cm`).

### RULED BY THE FABLE MODEL UNDER DELEGATION — DECIDED, NOT BUILT

Full reasoning in LESSONS 2026-08-15. **These are model rulings, not Ryan's
words.**

- **D2 — import `PN_interactiveSpruceForest`; DEFER the four Baltic Pine PVE
  exports.** It ships 21 StaticMesh Norway spruces (no export needed),
  5-level LOD chains, a 0.56-16.9 m range including the sapling tier the
  forest entirely lacks, **`MA_Imposter` + 21 baked 4096² atlases** — which is
  BACKLOG's open aerial-readability item, delivered as vendor content — and a
  winter/snow set. Four more pine variants close no recorded gap.
  **CONDITIONS:** R-ASSET intake; wind EDITED OUT for a static first import
  (`PN_GlobalUpdater` is a runtime Blueprint dependency); `LODGroup=None` on
  the 14 big trees makes explicit screen sizes and cull distances a REFUSAL in
  the gate, not a checklist item; measure the 4-vs-3 material-slot cost and
  the imposter material's 5.8 compilability in the scratch scene BEFORE any
  mass scatter.
- **D3 — blueberry only, on the GRASS system, not instances.** Precedent is
  the 2026-08-08 carpet-density ruling. Blackberry/raspberry are
  montane-below-treeline and stay on disk; the 484 MB demo ground texture
  stays behind. Gates: `uncorrected_pivot_errors()` per mesh, then the
  attended material rebuild. Abort bar +1.5 ms GPU.
- **D4 — density rises to ~220,000 as a closure GRADIENT, never uniform 70%**
  (a managed-lowland reference-class error). The defect is as much UNIFORMITY
  as count. Leaves a 30k reserve under the shared 250k ceiling because the
  rocks are absent by ruling, not permanently. ONE re-scatter combined with
  D2's mix. Abort bar **11 ms GPU** at `forest_floor`.

**SEQUENCE:** D2 import + scratch measurement -> D3 material rebuild -> the
single D4 re-scatter -> a named `camera_epoch` full re-site -> fresh sweep.

### OPEN, STATED PLAINLY

- **DO NOT SAVE `PVE_Norway_Spruce_01`.** It is dirty in the editor carrying
  my per-node export edits, and it lives in gitignored vendor content — saving
  it is lost work that looks committed.
- **The eight armature bakes are still on disk** (`SM_Tree_*`, 28.9 MB,
  tracked) one prefix character from the four real `SM_PVE_*` exports in the
  same folder. `recipes/tree_lods.json` is marked DO NOT RUN for the same
  reason.
- **Baltic Pine PVE nodes still hold vendor defaults** — verified from the
  package bytes. If those exports ever run, fix every node individually.
- **`ASSETS.md` needs rows** for the four `SM_PVE_*` and a correction: the
  Megaplants row still says "not spawned, not rendered".
- **`RECIPES.md` R-BAKE is stamped "Status: PROVEN"** and is superseded for
  this pack. `RECIPES.md:1545` still names `fir_tree_01_c_LOD0` as the live
  conifer. Both need supersession notes — additive, but they are Ryan's files.
- **Five Fab packs, 3.5 GB, have no `ASSETS.md` row, no licence record and no
  hash baseline.** No non-`.uasset` file exists in any of them, so terms are
  not recoverable from disk.
- **The `-0.38 ms` frame-cost delta is NOT single-variable** — mesh,
  `r.Nanite.Foliage` 0->1 and scale_range all moved. The decomposition control
  is cheap because Nanite is per-mesh.

**RESTORE POINTS:** `pre-pve-spruce-adoption-20260815`,
`pre-skeletal-to-static-bake-20260814`, `pre-fab-tree-pack-import-20260814`.

---

# CURRENT STATE — 2026-08-14 — THE SWEEP TERRAIN EXISTS AT 1 m/VERTEX, POPULATED

**Ryan ruled option (a) and went to bed with full authority granted. This is
what came back.** `/Game/Alpine8K` is the alpine sweep terrain re-composited at
8129², surfaced, lit, Nanite-built, exposed and planted — minus the rocks.

### WHAT EXISTS

    level        /Game/Alpine8K   (World Partition, 256 proxies)
    landscape    Landscape_Alpine8K, 8129², 66,080,641 vertices, 1 m/vertex
    scale        [100.0, 100.0, 500.0]   location [-406400, -406400, 128000]
    terrain      0.0 .. 1552.5 m in world Z
    material     M_Alpine8K — 298 expressions, 298 reachable, 0 ORPHANED,
                 37 samplers 0 mismatches, displacement 0.4 m, triplanar on Rock
    Nanite       256 / 256 proxies carry a built mesh
    lighting     R13 block; sun 130000 lux, sky, fog, post-process
    exposure     -1.923 EV, solved for THIS scene (see the caveat below)
    foliage      154,018 conifers placed and counted in the world
                 Meadow via the grass system, GT_alpine_8k_Meadow, 120 /10m²
    rocks        NONE, deliberately — Ryan asked for "minus the rocks"

**Restore points:** `pre-alpine-8k-recomposite-20260813`,
`pre-alpine8k-foliage-place-20260814`.

### IS IT THE SAME MOUNTAIN? YES, AND IT WAS MEASURED

    correlation vs alpine_heightmap_v2      0.999824
    landform mae at ~240 m scale            1.41 m = 0.254% of mean elevation
    median residual                         0.95 m
    conifer count vs alpine's 157,554       154,018  (-2.2%, 23.3/ha vs 24.2)

**The detail gain is real and MODEST, stated so nobody over-claims it:** +41%
relief amplitude below the old 8 m Nyquist (0.431 m RMS vs 0.305 m), and
sub-metre in absolute terms. Whole-map mean gradient says only 1.071x and that
figure is a misleading denominator — it is dominated by mountain-scale slopes
identical in both maps by construction. The near-field win comes from Nanite
displacement, not from the heightmap.

### THE ROUTE, so nobody re-derives it

Not Gaea — the sweep world is STAMP-COMPOSITED, and `AlpineLab_8129` is the Gaea
one and a different mountain. Not a native regeneration either: the base has NO
SIDECAR, so its generation parameters are unrecoverable and a regeneration would
be a different mountain. **Re-composited at 8129**: landform from the upsampled
base, new detail from nine 4096² stamps that the 2017 grid was box-reducing by
3.9x–9.6x, plus a 28 m relief band that went from 7 texels per wavelength to 28.
Full spec in `RECIPES.md` R-ALPINE8K.

### SIX PARAMETERS THAT ONLY EVER HAD ONE VALUE — all fixed, all committed

| Parameter | Silent failure at 8129 | Caught by |
|---|---|---|
| `derive_aux_maps` output names | would overwrite Alpine's flow map | reading code |
| droplet count (per-cell) | flow map 6.5x too sparse | **nothing** |
| `make_macro_variation` name | producer/consumer disagree | reading code |
| `max_steps` (per-cell) | talus would not converge | its own assertion |
| talus cache path | **overwrote** Alpine's cache | `git status` |
| landscape actor Z | terrain 1280 m too low | an assertion I added |
| `parent_material` | would rebuild Alpine's material | a deliberate sweep |

**All per-biome or per-resolution quantities written as though only one of each
would ever exist.** This repo had exactly one of each until tonight. Narrative in
`LESSONS.md` 2026-08-13/14.

### OPEN, STATED PLAINLY

- **THE EXPOSURE SOLVE HAS A METHOD FLOOR.** -1.923 does not converge to the
  solver's 0.3201 target and cannot: the decoded PNG is POST-tonemap and 0.3201
  is a PRE-tonemap scene value. Applying it moved 0.4134 → 0.3909 where linear
  arithmetic said 0.3760. **This affects every exposure check this project has
  ever made by decoding a screenshot**, including alpine's 0.3169-vs-0.3201,
  which is closer than the method can resolve. The value rests on the measured
  brightness ordering plus agreement to 0.026 EV with alpine's independently
  derived -1.897. A real solve needs the pre-tonemap value.
- **THE 19 CAMERAS ARE INHERITED FROM THE 2017 TERRAIN, AND `sweep_cameras`
  REFUSES TO REGENERATE THEM. NEEDS A RULING.** Ran
  `sweep_cameras --recipe recipes/alpine_8k.json --resite`; its summit guard
  fired, correctly:

      recorded  z = 1406.70 m at (-844.0, -1040.0)
      measured  z = 1408.62 m   drift 1.915 m (tolerance 1.0 m)
      REFUSE: the recorded stations are stale and would photograph a different
      mountain while every number in the sweep report still looked right.

  **The drift is real and expected** — 1.915 m at that point against the
  landform's 1.41 m mae, i.e. 0.12% of a 1552 m terrain. Same mountain, moved
  sample. The guard is doing exactly its job on a 4x resample.
  **NOT ACTED ON DELIBERATELY.** The tool says "re-derive the design
  deliberately and record the new constants", and re-siting sets the baseline
  for every future ground A/B — that is a design act, not a mechanical one, and
  it was not worth burning unattended. **Ryan's call.** Until then the four
  frames captured on 2026-08-14 used the INHERITED positions, which is fine for
  looking at and wrong for comparing against future ground sweeps.
- **NO COLLISION TRACE AND NO GROUNDING VERIFY HAS RUN** on this world. Conifer Z
  comes from the plan, and `check_collision_truth` / `trace_grounding` have not
  been pointed at it. Non-negotiable 0 says the grid and the plan are closer to
  one source than two.
- ~~**FRAME COST WITH FOLIAGE IS UNMEASURED.**~~ **MEASURED 2026-08-14.**
  Artefact: `_verify/20260814_alpine8k_framecost.md`. Same ground camera,
  single variable, full residency, all runs past the throttle gate:

      forest_floor          GPUTime  RenderThread  GameThread
      vegetation ON            8.14      4.88         7.48
      vegetation CULLED        5.86      4.73         7.35
      DELTA                   +2.28     +0.15        +0.13   (+38.9%)

  **Terrain + Nanite + displacement costs 5.86 ms at a ground station;
  154,018 conifers plus grass add 2.28 ms.** Total 8.14 ms ≈ 49% of a 16.67 ms
  frame. Top-down at 9 km with no vegetation in frame: 4.09 ms (different
  camera — not comparable to the ground figures).
  **THE FIRST CONTROL WAS INVALID AND IS KEPT IN THE ARTEFACT.**
  `foliage.DensityScale 0` + `grass.DensityScale 0` read back as 0 and moved
  the frame 8.14 → 8.17 — they govern SPAWNING, not placed instances. The
  working lever, read at engine source, is `foliage.CullAll` +
  `grass.Enable 0`. A null result is only evidence when the instrument could
  have produced a non-null one.
  **This is a FLOOR, not a budget:** `fir_tree_01`'s canopy is a 24.02%-opaque
  binary atlas, and a denser replacement will cost more.
- **A NEW EDITOR REPORTS ZERO STREAMING PROXIES** until regions are loaded.
  `measure_frame_cost.py --load-all-regions` is the path. This bit the Nanite
  verify once tonight and will bite anything that reads proxies.
- **The conifer is still `fir_tree_01`** — 24.02% opaque binary atlas, needle
  albedo 85/81/49. Ryan ruled to source a replacement from Fab; the spec is
  `plans/conifer_asset_spec.md` and I cannot buy it. Swapping it is a one-line
  recipe change plus a re-scatter.
- **Peak memory is now the binding constraint.** The Nanite build reached
  **196.8 GB of a 223.4 GB commit limit** — the highest ever here, and 27 GB of
  headroom. The variant-selector bake needs 19 GB and must run alone.

---

# CURRENT STATE — 2026-08-13 (late) — NANITE IS BUILT. OPTION A WORKED.

### BLOCKED ON ONE RULING — WHICH LANDFORM. Do not build past this.

Ryan's goal, in his words: *"the terrain we created in the alpine sweep photos
full converted over to 8K graphics minus the rocks"*. **That is NOT what has
been built, and the gap is the point.**

    the sweep photos   /Game/Alpine — alpine_heightmap_v2.png, 2017²,
                       4 m/vertex, 171,069 instances
    what we built      /Game/GaeaLab/AlpineLab_8129 — a GAEA landform
                       (build AlpineLab_v1/006), 8129², 1 m/vertex,
                       foliage.species is an EMPTY LIST

**Two different mountains.** We built the 8K technology stack, on bare ground.

**AND "CONVERT THE SWEEP TERRAIN TO 8K" CANNOT MEAN RESAMPLING IT.** Upsampling
2017² -> 8129² gives 16x the vertices and ZERO new information — the same
Nyquist cap already measured as the cause of "terrain reads as smooth rolling
mounds" (4.00 m per texel; a cliff lip, a ledge and an arete are all sub-4 m so
they cannot be represented at all). Detail must be GENERATED in Gaea or added
at the material level. **The three options were put to Ryan and he has not yet
ruled:** (a) regenerate the sweep landform in Gaea at 8129 — recommended;
(b) dress the existing AlpineLab_8129 with vegetation; (c) upsample the sweep
heightmap. Second open question: does "minus the rocks" also drop
`GroundClutter`, which is rock content (boulder_small / river_rock) delivered
via the GRASS system at zero instance cost?

**RULED ALREADY, 2026-08-13:** source a better conifer from Fab — spec at
`plans/conifer_asset_spec.md`, and "8K" means all three of terrain sampling
(done), textures, and 7680x4320 render output.

**A FREE WIN FOUND WHILE ANSWERING, needing no purchase:** the Gaea masks on
disk are ALREADY 8129² 16-bit (`AlpineLab_v1/006/UE5_Ready`, verified with PIL).
They were imported into UE at `max_texture_size 4096`, so the material samples
them at **1.98 m per texel when ~1 m is available**. Re-import at 8192 is the
highest-value half of "8K textures" and costs nothing. NOT DONE — it is
landform-dependent, so it waits on the ruling above.


**Tree clean. An editor IS RUNNING (PID 13952) on `/Game/GaeaLab/AlpineLab_8129`,
cold-loaded from disk, nothing dirty, nothing in flight.** Restore point:
`pre-nanite-batched-build-20260813`.

### THE HEADLINE

    proxies with a built Nanite mesh   256 / 256
    parent ALandscape                    0     (expected — owns no components)
    external actor packages           3.03 GB, 256 carry LandscapeNaniteMesh
    peak system commit                189 GB of a 228.8 GB limit
    peak editor private               176.6 GB
    wall clock                        ~7 min building + 609 s saving

**VERIFIED THROUGH THREE REPRESENTATIONS** (non-negotiable 0): the live build
session, a byte scan of the 264 external actor packages on disk, and a COLD
BOOT in a fresh process (new node id) that read 256/256 from disk alone.

**Ryan's page file ruling is what did it.** 189 GB of commit was needed; the
old limit was 60.1 GB. No batch size would have fitted this under 60 GB.

### DISPLACEMENT IS NO LONGER INERT — MEASURED, AND THE FRAMES WERE OPENED

Same two cameras, before/after Nanite, against the 0.00298 noise floor:

    ground_origin   mae 0.12259 = 41.1x floor   edge energy -24.78%   93.8% px
    peak_orbit      mae 0.00905 =  3.0x floor   edge energy  +7.08%   41.3% px

Before Nanite these same cameras gave 0.00646 / 0.00277 — at or below the
floor, i.e. nothing. **The negative edge energy at ground level is the KNOWN
TRADE, not a regression**, and it reproduces 2026-08-11's `sweep_0060` (-23.11%)
almost exactly. The frames settle it: `ground_origin` goes from a smooth mound
wearing a rock photograph to real stepped strata, terraces, a cut down the
centre-right, and undercuts catching hard cast shadow. `peak_orbit` gains
crisper ridgelines and loses a visible cross-hatch grid artefact on the mid-left
slope. **Do not read the -24.78% as a loss; open
`_verify/20260813_8129_nanite_*.png` against `_verify/20260813_8129_disp_*.png`.**

### THREE THINGS THE PLAN BELIEVED THAT ARE FALSE — do not re-derive them

1. **THE BATCH PARAMETER DOES NOT BOUND THE WORK.** The plugin logged
   `submitting 8 proxies` and the engine built all 256, to 189 GB.
   `ALandscapeProxy::PostEditChangeProperty` calls
   `InvalidateOrUpdateNaniteRepresentation` for `bEnableNanite`,
   `bNaniteSkirtEnabled` AND `NaniteSkirtDepth`
   (`LandscapeEdit.cpp:6131-6141`) — **setting the flag IS the dispatch** — and
   `FinishAllNaniteBuildsInFlightNow` waits on every build in flight
   (`LandscapeSubsystem.cpp:1179`). To bound memory the FLAGGING must be
   batched too. Necessary, not sufficient. **Not built that way, because with
   the page file raised it was not needed.**
2. **THE 9.3-HOUR / 37.9 GB DDC ESTIMATE IS WITHDRAWN.** It extrapolated one
   proxy that completed inside a dying, memory-starved editor and assumed
   SERIAL builds; the engine builds them concurrently. Real: ~7 minutes,
   10.73 GB total DDC.
3. **`bForceRebuild` must be FALSE to be resumable** —
   `LandscapeSubsystem.cpp:1157` drops already-built proxies only when not
   forcing. `landscape_nanite_build.py` passes True and is the non-resumable
   monolith; `nanite_batch_build.py` is the resumable one.

### AN ACCESSOR THAT ANSWERED WRONGLY — swept, and worth remembering

`get_component_by_class(LandscapeNaniteComponent)` + `get_static_mesh()` reads
**0** on a world holding 256 built meshes and **does not raise**. Correct form
is the plural `get_components_by_class` + the reflected `static_mesh` property,
which `verify_cold_boot.py:52-61` had right all along. Fixed in BOTH tools in
one commit; in `landscape_nanite_build.py` it was turning a COMPLETED build
into a reported failure via its exit-5 gate.

### TWO OPERATIONAL TELLS THAT COST TIME

- **`MainWindowTitle` returns the SPLASH SCREEN's title**, identical to the real
  one. The tell is the window CLASS — `SplashScreenClass` vs `UnrealWindow`.
  The prior handoff's "the only tell was the WINDOW TITLE" is too weak.
- **A flat editor CPU/memory trace is NOT "hung" during shader compilation** —
  that work is in `ShaderCompileWorker` CHILD processes, so the parent is flat
  by construction. Measure DDC growth on disk instead.

### OPEN, STATED PLAINLY

- **`bAllowSlateThrottling` reads True in the live editor** while
  `Config/DefaultEditorSettings.ini:56` sets False — that override has never
  been in effect, in the very file its sibling's fix was moved to.
  `bThrottleCPUWhenNotForeground` correctly reads False. NOT swept: it moves a
  measurement baseline and wants its own single-variable run.
- **`measure_frame_cost.py` enumerates `dir()` on the `EditorPerformanceSettings`
  CDO**, which exposes NO reflected properties when reached by object path — so
  its throttle probe finds nothing and reads as absence. Ask for the C++ names
  directly.
- **DDC was repointed to `C:\UnrealDDC` by Ryan** and started empty, which is why
  this session paid a full cold shader compile. Now 10.73 GB and warm.
- ~~**FRAME COST AT NANITE + DISPLACEMENT IS UNMEASURED.**~~ **MEASURED
  2026-08-13.** Full artefact: `_verify/20260813_8129_framecost_nanite.md`.
  Single-variable A/B on `r.Nanite`, one session, two cameras, 300 frames each,
  full residency asserted at 1024/1024, every run past the throttle gate at
  2.17–3.65 CPU-s per wall-s:

      camera          GPUTime ON   OFF     delta      RenderThread ON / OFF
      ground_origin      4.95     3.75   +1.20 ms       4.60 / 3.54
      peak_orbit         4.05     3.22   +0.83 ms       4.57 / 3.66

  **Nanite + displacement costs ~1.2 ms of GPU at ground level, ~0.8 ms aerial
  — about 25–32% on top of the non-Nanite path, and ~30% of a 16.67 ms frame
  with ~11.7 ms of headroom.** Cheap for what it buys.
  **THREE CAVEATS, none of them optional.** (1) `FrameTime` is pinned at
  16.67 ms in ALL FOUR runs — a 60 fps CAP, so nothing here is GPU-bound and
  none of it is a frame-rate result. **THE CAP IS NOW ROOT-CAUSED AND CANNOT BE
  LIFTED BY A CVAR** — `UEditorEngine::GetMaxTickRate`
  (`EditorEngine.cpp:2523-2566`) sets `MaxTickRate = 1.0f / DeltaTime`, a
  HYSTERESIS LOOP clamping the editor to the rate it is already running at,
  inside a hard `SmoothedFrameRateRange` of `[5, 120]` that applies *even
  though* `bSmoothFrameRate` is False. Ruled out by measurement, not assumption:
  `t.MaxFPS` reads **0.0**, `r.VSync` 0.0, `rhi.SyncInterval` 1→0 moved nothing,
  and the machine is on AC so the battery branch is inert. **Editor frame RATE
  is not a valid headroom instrument and never was** — the same function is
  where the project's 3 fps backgrounded idle (`MaxTickRate = 3.0f`) comes from.
  GPU/RenderThread/GameThread times are unaffected by the clamp and remain
  valid. Headroom from the valid instrument: **~30% GPU utilisation, ~11.7 ms
  unused.** (2) `r.Nanite 0` also disables
  displacement, so the delta is the cost of the two TOGETHER, not a
  decomposition. (3) The board's pre-Nanite 5.07 mean **names neither its
  camera nor its viewport**, so it is not a valid comparator — today's OFF
  control at the same camera reads 3.75, and the two are different
  measurements rather than a contradiction.
  Still unmeasured: this terrain carries **no foliage**, and it is not PIE or
  a packaged build.
- ~~**Exposure re-solve.**~~ **DONE 2026-08-13: `-1.786` -> `-1.867` EV**,
  solved against THIS terrain and verified on pixels. Artefact:
  `_verify/20260813_8129_exposure_solve.md`. Measured top-down linear luma
  0.3385 against the solver's sunlit target 0.3201, so this scene is **~6.8%
  brighter than /Game/Alpine** (same method, 0.3169) and its implied effective
  albedo is **~0.286** vs alpine's 0.2675. After the change the same frame
  reads 0.3246, a 1.41% residual — inside the 1.0% error the same method
  showed when validated on alpine, and the gap is the TONEMAPPER, since an
  sRGB decode undoes the encode but not the tonemap.
  **THE PORTED VALUE WOULD HAVE BEEN WRONG AND RIGHT-FOR-THE-WRONG-REASON:**
  alpine's `-1.897` overshoots by 0.03 EV, and it corrects for LUMEN BOUNCE on
  a different scene where this corrects for ALBEDO on this one. Two mechanisms
  landing 0.03 EV apart is a coincidence, not a confirmation.
  **Consequence for existing frames:** everything captured earlier on
  2026-08-13 (`20260813_8129_nanite_*`, and the frame-cost runs) was shot at
  `-1.786` and is 0.08 EV brighter than anything captured from now on. Any A/B
  against them must account for it. The frame-cost NUMBERS are unaffected —
  exposure is a post-process constant, not a shading cost.
- HLOD, RVT and rock/tree scatter are all still deliberately not done, for the
  reasons in the previous CURRENT STATE.

---

# CURRENT STATE — 2026-08-13 — RESTART HANDOFF. SAFE TO REBOOT.

**Nothing is in flight. Tree clean. No editor running — closed cleanly, so
there is NO "Restore Packages" modal waiting.** That matters: the last one sat
in front of a loading editor for 6,776 CPU-seconds while every instrument said
"still loading", and the only tell was the WINDOW TITLE.

### RYAN RULED OPTION A: RAISE THE PAGE FILE, THEN BUILD NANITE

**THE ONE THING TO DO BEFORE RELAUNCHING ANYTHING** — a machine-global setting,
outside both roots, so it is his and not mine (standing rule 1):

    System Properties -> Advanced -> Performance Settings -> Advanced
      -> Virtual memory -> Change
    Uncheck "Automatically manage"
    C: -> Custom size -> Initial 196608 MB, Maximum 196608 MB
    Set -> OK -> REBOOT

Measured, not guessed:

    page file now      initial 32 GB, max 64 GB, allocated 29.4 GB
    PEAK USAGE         29,003 MB of 29,399 allocated -- it filled it
    commit limit now   60.1 GB (max reachable with current settings ~95 GB)
    the build wanted   >115 GB   (PeakUsedVirtual 115.47 GiB at the crash)
    C: free            655.5 GB, so 192 GB costs a third of the free space

192 GB gives a commit limit of ~223 GB against a measured 115 GB peak.

**IT IS A GOOD BET AND NOT A GUARANTEE, AND THE REASON IS WORTH READING.** The
115 GB peak was reached while the FIRST few proxies were building, not the
last. Whether the build's memory grows with proxies processed is UNKNOWN. If it
accumulates, no page file size is the right answer and the build must be
BATCHED instead.

### SO THE FIRST WORK AFTER THE REBOOT IS NOT THE BUILD — IT IS BATCHING IT

`ULandscapeSubsystem::BuildNanite` takes
`TArrayView<ALandscapeProxy*> InProxiesToBuild` (LandscapeSubsystem.h:148) and
`LandscapeLabEditor` currently passes an EMPTY view, which means "all 256".
Exposing that parameter turns one 9.3-hour monolith into resumable batches:

  - bounded peak memory, which is the actual failure mode
  - resumable — a crash costs one batch, not nine hours
  - saveable between batches, so progress survives

That is a small plugin change plus a rebuild (~10 s), and it de-risks the whole
operation. Do it before spending 9.3 hours.

**THE COST, extrapolated from ONE proxy that completed before the crash:**

    per proxy   148.0 MB DDC, 131.0 s   (export 20.5 s + commit 110.5 s)
    x 256       37.9 GB DDC, 9.3 HOURS

Disk is not the constraint. `landscape.Nanite.MultithreadedBuild` defaults to 1
and is already on.

### WHERE THE TERRAIN IS

    level      /Game/GaeaLab/AlpineLab_8129   (World Partition, 256 proxies)
    landscape  8129², 66,080,641 vertices, 1 m/vertex, 1024 components
    material   M_AlpineLab_8129 — 108 expressions, 108 reachable, 0 ORPHANED,
               20 samplers 0 mismatches, use_material_attributes True,
               enable_tessellation True, displacement magnitude 0.16
    lighting   R13's block verbatim; sun/sky/atmosphere/fog/PP, saved
    cvars      19 of 19 pinned values verified IN EFFECT on a cold boot
    frames     _verify/20260812_8129_*.png and 20260813_8129_disp_*.png
    cameras    10 in the recipe: overview, peak_orbit, top_down, ground_origin
               + 6 generated ground_* stations traced onto the collidable surface

**DISPLACEMENT IS WIRED AND MEASURED INERT** until Nanite is on: same cameras
before/after the rebuild gave mae 0.00646 / 0.00277 against a 0.00298 noise
floor. That is the whole reason option A matters — the material work is banked
and contributes nothing until the Nanite meshes exist.

### DELIBERATELY NOT DONE, each with its reason

- **HLOD** — builds proxies for UNLOADED regions; every render and measurement
  here runs with all 256 resident, so it would change nothing being evaluated
  while costing another long build. Relevant when this terrain is PLAYED.
- **RVT** — still HELD under non-negotiable 27. 20 uncited engine names, and it
  allocates GPU memory on a machine that has lost its GPU to a driver timeout.
- **Exposure re-solve** — R13's −1.897 EV was solved for /Game/Alpine's scene.
  Applying another scene's constant here is the derived-record trap; it needs
  its own solve against this terrain's albedo.
- **Rock/tree scatter** — skipped on instruction. The block is in the recipe,
  budget re-derived (250,000 instances; triangle ceiling deliberately unchanged
  at 30M because worst-case load is density x cull-disc area, a LOCAL quantity).

### ONE THING MOVED ON DISK

`LandscapeLab/Saved/Autosaves` (872 MB, 526 files) →
`_trash/autosaves_restoreprompt_20260813/`. That is how the "Restore Packages"
modal was answered DISCARD deterministically rather than by clicking an
unlabelled button. Preserved and recoverable. Restoring would have brought back
`enable_nanite=True` on 257 actors with NO built meshes — flagged for Nanite,
nothing to render, and a cook that would try to build it.

---

# CURRENT STATE — 2026-08-12 (late) — THE PLUGIN EXISTS AND THE 8129 LANDSCAPE IS BUILT

### THE UE HALF IS DONE EXCEPT THE MEASUREMENT. Read this first.

**Tree clean. An editor IS RUNNING on `/Game/GaeaLab/AlpineLab_8129` with
nothing dirty and nothing in flight.** Restore points:
`pre-cpp-conversion-20260812`, `pre-8129-landscape-create-20260812`.

**LandscapeLab is now a C++ project — and `LandscapeLab.uproject` is
BYTE-IDENTICAL.** No game module: `PluginManager.cpp:421-425` enables a
project plugin with `EnabledByDefault` and no `.uproject` entry at all, so
standing rule 4 stands with no exception carved into it. Two `Target.cs` files
with empty `ExtraModuleNames` are sufficient.

    plugin   LandscapeLab/Plugins/LandscapeLabEditor
    exposes  create_landscape_from_heightmap, get_heightmap_resolution,
             build_landscape_nanite, change_landscape_grid_size,
             load_all_world_partition_regions
    builds   79.5 s clean, first try, MSVC 14.44.35228 (Ryan's v143 component)

**`build_landscape_nanite` HAS NEVER BEEN CALLED.** It compiles and is
reflected; its success path is unexecuted, exactly as
`create_landscape_from_heightmap`'s was before the 8129 import.

**R-GAEA's "UE 5.8 Python cannot create a landscape" is now FALSE.** Its
diagnosis was right about the engine; the procedure is superseded by
**R-CREATE** in `RECIPES.md`. The struck notice is in
`scripts/ue5_import_alpinelab.py`, whose "READ THIS FIRST" header said the
opposite.

### THE LANDSCAPE — created, verified by two instruments, saved

    level     /Game/GaeaLab/AlpineLab_8129   (World Partition)
    actor     Landscape_8129
    8129²  =  32 × 32 components, 2 sections × 127 quads, 66,080,641 vertices
    scale     [100.0, 100.0, 180.8358010032807]   read back exact
    extent    8128 m,  1 metre per vertex,  Z span 925.88 m
    proxies   256 × 4 components = 1024
    recipe    recipes/alpinelab_8129.json

`landscape_inventory.py` derives **implied resolution 8129** from engine
section bases (32 distinct, 0..7874, step 254) without ever seeing the plan.
Two representations, one answer.

**Cost: ~9 min, editor peak 16.7 GB working set, free RAM 20.6 → 3.0 GB.**

### THE 8129 TERRAIN IS SURFACED, LIT AND RENDERED AT 4K

    _verify/20260812_8129_overview.png  peak_orbit  ground_origin  top_down

Full chain executed: masks -> material -> lighting -> frames. Locked as
**R-AL8129** in `RECIPES.md` with eight REJECTED entries. Rocks skipped at
Ryan's instruction; the scatter block is in the recipe, re-derived and ready.

    masks     5 imported, TC_GRAYSCALE/G16, max_texture_size 4096
              = 1.98 m per texel, parity with v1's 1.97
    material  M_AlpineLab_8129, 14 textures, 90/90 reachable 0 ORPHANED,
              14 samplers 0 mismatch
    lighting  alpine.json's R13 block verbatim; sun/sky/atmosphere/fog/PP
    frames    3840x2160, all four tonally non-trivial, 0.00% blown

**FRAME COST, LIT AND SURFACED — this supersedes every earlier figure today:**

    GPUTime  5.07 mean  5.05 p50  5.30 p90    RenderThread 4.57
    GameThread 9.57     FrameTime 16.67 (a 60 fps cap, not a cost)

66,080,641 vertices with ~11 ms of headroom to the cap. Editor viewport class:
not PIE, not packaged, no rock scatter.

### THE FIRST FOUR 4K FRAMES WERE PURE BLACK AND EVERY TOOL SAID SUCCESS

`park_viewport` read back 0.000 cm on every axis; `highres_shot` printed
`WROTE ... 150,569 bytes` and exited 0, four times, from four different
cameras. mean 0.0000, std 0.0000, **all four the same SHA256**.

Cause: `LevelEditorSubsystem.new_level()` makes an EMPTY partitioned world —
no light, no sky, no atmosphere. The level had a landscape and nothing else.
The tell was not any tool's output but that four different cameras produced
**byte-identical file sizes**.

**`highres_shot.py` HAS NO TONAL CHECK.** `verify_frames.py` does and is not
wired into this path. Until it is, measure mean/std/SHA on every capture set.

**AND IT INVALIDATED THE FIGURES BELOW.** GPUTime 2.92 / 3.16 / 3.20 ms were
all measured on that unlit black level, and the sky-vs-terrain control reading
3.20 vs 2.98 was comparing **black terrain against black sky**. I read the weak
separation as "the geometry is cheap" instead of as "the scene is not in a fit
state to be measured". The conclusion survived the correction; the method did
not. **A control that fails to separate is evidence about the whole setup, not
just about the variable.**

### SUPERSEDED — the unlit measurement, kept as the record

**`ULandscapeLabTools::LoadAllWorldPartitionRegions`** — `FLoaderAdapterShape`
over `GetEditorWorldBounds()` XY with Z at ±`HALF_WORLD_MAX`,
`SetUserCreated(true)`, `Load()`, then asserts `IsLoaded()`. Same shape as the
editor's own region tool (`SWorldPartitionEditorGrid2D.cpp:702-710`).
**4 proxies → 256, 1024 of 1024 components.**

**`measure_frame_cost.py` now REFUSES (exit 6) when residency is not
declared.** `--expect-components` is mandatory on a partitioned world. Proven
both directions: undeclared with 4 proxies → exit 6; `--load-all-regions
--expect-components 1024` → 1024/1024, verdict given.

**FIRST RECORDED MEASUREMENT.** Editor viewport, 1721×1033, realtime ON,
throttle OFF, full residency, **engine default material, Nanite OFF, no
foliage**:

    station                  GPUTime mean   RenderThread
    ground eye (1.7 m)           3.20            2.99
    aerial 500 m                 3.16            3.25
    SKY CONTROL (no terrain)     2.98            3.01
    4-proxy residency control    2.92            2.93

**The landscape contributes ~0.2 ms; the rest is fixed editor cost.**
66,080,641 vertices of landscape GEOMETRY, normally LOD'd, is not expensive —
consistent with where this project's costs have always been (157,554 conifers
at 39.6M tris, and a layered material with triplanar and displacement).
`FrameTime` is a 60 fps cap in every run and is not a cost.

**THIS IS A FLOOR, NOT THE GO/NO-GO.** The shipping configuration — a
`M_AutoLandscape`-class layered material, landscape Nanite on, foliage present
— is unmeasured, and that is the measurement the re-terrain decision needs.

**NEXT, in order:** (1) assign a real layered material and re-measure;
(2) enable landscape Nanite (`build_landscape_nanite` is in the plugin and is
UNEXECUTED) and re-measure; (3) only then compare against the 4033 baseline,
and note that comparison is NOT single-variable against `AlpineLab_v1`, which
carries 30,589 instances and its own material.

### A CONTROL I RAN THAT WAS INVALID — do not repeat it

`r.ScreenPercentage` 100 → 400 moved GPUTime 3.20 → 3.17 ms, and I read that
as "the level viewport is not rendering the scene at all", one step from
retracting every number above. **The editor level viewport honours
`ManualScreenPercentage` (`EditorPerformanceSettings.h:136-142`), not the
global cvar** — which this file's own earlier entry says, in the paragraph
explaining why both are set to 70.
**A null result is only evidence when the instrument was capable of a non-null
one.** The controls the reading rests on are terrain-vs-sky and 4-vs-256
proxies, both of which respond.

**SECOND STALE-SETTING INSTANCE, FOUND AND NOT SWEPT:**
`ManualScreenPercentage=70` and `bOverrideManualScreenPercentage=True` are in
`DefaultEditorPerProjectUserSettings.ini` — the same wrong file as
`bThrottleCPUWhenNotForeground`, same `config=EditorSettings` class. **So the
editor viewport's 70% render scale has almost certainly never been in effect,
and every editor-viewport frame this project ever rendered was at 100%.** Not
swept deliberately: it moves a measurement baseline and wants its own
single-variable run, which is a departure from non-negotiable 4's
sweep-in-the-same-commit rule and is flagged as one.

### THE THROTTLE DEFECT IS CLOSED — right section, wrong FILE

Open since 2026-08-10 as "my own fix did not take", filed under
non-negotiable 17. It was not 17. `UEditorPerformanceSettings` is
`UCLASS(minimalapi, config=EditorSettings)` — `EditorPerformanceSettings.h:31`
— so its overrides come from **`DefaultEditorSettings.ini`**, and the value sat
in `DefaultEditorPerProjectUserSettings.ini` under the CORRECT section name.
**The override was never read at all.** Proven behaviourally, single variable,
editor backgrounded both times:

    wrong ini file              0.08 CPU-s per wall-s   FrameTime 333.33 ms
    DefaultEditorSettings.ini   1.70 CPU-s per wall-s   FrameTime  16.67 ms

**333.33 ms is exactly 3 fps — the editor's unfocused idle rate. Every
frame-cost number taken on a backgrounded editor in this project measured
that, not a scene.** Now pinned in `LandscapeLab/Config/DefaultEditorSettings.ini`
together with `bAllowSlateThrottling=False`.
**`ManualScreenPercentage=70` and `bOverrideManualScreenPercentage=True` are
in the SAME WRONG FILE and were therefore also never in effect** —
NOT swept, because raising the viewport render scale is a change to a
measurement baseline and wants its own single-variable run.

### FOUR NAMES THAT MEANT SOMETHING OTHER THAN THEY READ

Full narrative in `LESSONS.md` 2026-08-12; specifications in R-CREATE
REJECTED and R-FRAMECOST REJECTED.

1. **MSVC ban read off the DIRECTORY name.** `MSVC/14.44.35207` sits inside
   the banned range; the compiler is 14.44.**35228**. UBT parses the directory
   into `Family` and checks the ban against `Version`.
2. **A `UFUNCTION` returning `bool` with out-params LOSES the `bool`.** Python
   gets `(...outs) or None`, so `OutError` disappears exactly when needed. All
   three are now `void` + `bOutSuccess`. **I wrote the C++ and still could not
   predict the binding.**
3. **`unreal.Rotator(ROLL, PITCH, YAW)`** — roll first, `PythonStub:66750`. My
   camera got a −25° roll instead of pitch and the frame still looked fine.
4. **`UEditorPerformanceSettings` is `minimalapi`**, so it is NOT exported as
   `unreal.EditorPerformanceSettings`; the CDO is reachable by object path, and
   three guesses at its property names all failed. The script now ENUMERATES.

### AND THREE OF THIS PROJECT'S OWN HOOKS FIRED ON ME, ALL USEFULLY

The `.uproject` guard refused the standard C++ conversion and **the refusal
produced a better design** — that is why the project file is untouched. The
commit-message guard fired on a heredoc containing the exact backticks rule 3
was promoted over. The heredoc-escape guard fired on the LESSONS entry being
written about it, and msys-game-path caught a `/Game/...` argument Git Bash was
about to rewrite. **A gate that fires on its author is the only evidence it
works.**

### STILL UNVERIFIED, stated plainly

- **That the terrain is the RIGHT terrain.** Everything checked is the
  component grid and the import parameters. **No collision trace, no render,
  no comparison of the live surface against the heightmap.** Non-negotiable 0
  warns the grid and the plan are closer to one source than two.
- The 8129 landscape has the **engine default material** and **Nanite off**.
- `recipes/alpinelab_8129.json` does NOT conform to `recipes/schema.md` and
  `open_level.py` refuses it — deliberate, matching its sibling
  `alpinelab_v1.json`. Open that level by launching the editor with the map as
  an argument (no in-process map transition, so the scrub is not bypassed).
  **Use the PowerShell tool; Git Bash rewrites `/Game/...`.**

---

# CURRENT STATE — 2026-08-12 (earlier)

### RESTART HANDOFF 2026-08-12 20:5x — SAFE TO REBOOT. Read this first.

**Nothing is in flight.** Tree clean, no editor running, no Gaea running.
A Visual Studio installer WAS running (the C++ workload, see below); a
reboot mid-install is normal and it resumes.

### THE RE-TERRAIN: THE GAEA HALF IS DONE. THE UE HALF NEEDS A PLUGIN.

    build   C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\006\UE5_Ready
    size    8129 x 8129, all 6 maps + AlpineLabHeight.png alias
    verify  verify_build exit 0, registration control PASSES
    Z SCALE 180.84   <- from height_normalization.json, use in the import

**IT IS NOT IN GIT AND THAT IS FINE** — it lives outside both roots and is
**reproducible in ~100 seconds**: `python scripts/rebuild_terrain.py
--resolution 8192 --go`, then `resize_gaea_build.py --size 8129
--archive-excluded`. Cheap to recreate, so do not treat it as precious.
Leftovers `003`/`004` are empty husks from crashed attempts and `005` is a
complete but UN-NORMALIZED build from the console test; **006 is the
canonical one** and the only one with `height_normalization.json`.

**Same terrain, 4x the sampling** — occupancy 0.37029 -> 0.37035, span
925.73 -> 925.88 m, Z 180.81 -> 180.84 across builds 002 and 006. 0.02%.
That control came free and it is what makes this a RESOLUTION comparison
rather than a different terrain.

### WHAT IS BLOCKING, AND WHAT RYAN IS INSTALLING

`ALandscapeProxy::Import` (`LandscapeProxy.h:1418`) is `LANDSCAPE_API`
with **no `UFUNCTION`**, and there is no `LandscapeEditorSubsystem`.
Verified at source, so R-GAEA's "UE 5.8 Python cannot create a landscape"
is CORRECT. The same gap covers `ULandscapeSubsystem::BuildNanite` (worked
around today with `landscape.Nanite.LiveRebuildOnModification`) and
`ChangeGridSize`.

**Ryan is installing the VS "Game development with C++" workload** so a
small editor plugin can expose those three as `UFUNCTION`s. That is a
SCOPE CHANGE — it makes LandscapeLab a C++ project — and he has ruled for
it. **CAVEAT TO CHECK ON RETURN: the installed VS is Community 2026**, and
UBT's own source comments reference the VS **2022** lifecycle; the
accepted MSVC range is resolved at runtime and was NOT readable from the
install. He was told to add the **MSVC v143 (VS 2022)** toolchain
component as insurance. If UBT refuses the toolchain, that is why.

**NEXT, in order:** (1) write the plugin into
`LandscapeLab/Plugins/`; (2) generate project files, build Development
Editor; (3) create + import the 8129 landscape at Z 180.84 with 127 quads
x 2 sections x 32 components; (4) **MEASURE FRAME COST at 66,080,641
vertices** — that is the actual go/no-go and everything before it is
arithmetic. Untested fallback if the plugin stalls: drive Landscape Mode
via unreal-mcp's Slate toolset (CLAUDE.md records 52 toolsets,
read/write/mutate cleared) — **unverified, MCP was unreachable with the
editor closed.**

### THE GAEA GRAPH IS NOW READABLE (new capability, needs nothing enabled)

`.terrain` is plain JSON. `scripts/read_gaea_graph.py` prints the 6-node
graph, its wiring and its parameters, and carries three gates
(`--check-refs`, `--check-spec`, `--against-build`) proven to refuse five
distinct corruptions (`scripts/prove_gaea_reader.py`).
**Two facts it surfaced that were invisible:** `Height 2500.0` is in the
file — the 2.7x-too-tall trap, now printed WITH its warning; and
`Width 5000.0` is the extent the graph was AUTHORED at, with
`ErosionScale 1413.25` tuned to it, so importing at 8128 m stretches
erosion features ~1.63x. Not an error, but it matters more at 1 m/vertex.
**A writer is deliberately NOT built:** 23 `$ref` back-references mean
parameter edits are safe and structural edits are not without
id-allocation. `--check-refs` is the acceptance test that writer must
pass, and it exists before the writer.

---

# CURRENT STATE — 2026-08-11

### MATERIAL DISPLACEMENT IS BUILT, ENABLED AND MEASURED. It works. Read the two caveats before touching it.

**All ten checklist steps ran. The full procedure and its five REJECTED
entries are locked in `RECIPES.md` R2 → NANITE DISPLACEMENT; the story is
`LESSONS.md` 2026-08-11. Do not re-derive either.**

    material   M_AutoLandscape  sha256 2e0f68ad…  (was 9f888a66…)
               use_material_attributes True, enable_tessellation True,
               displacement_scaling magnitude 0.16, center 0.5
               = 0.40 m peak amplitude
    graph      278 expressions, 278 reachable, 0 ORPHANED,
               driven by MP_MATERIAL_ATTRIBUTES; grass output seeded
    samplers   32 audited, 0 mismatches
    landscape  enable_nanite 257/257, 256/257 with a built Nanite mesh
    frames     19/19 clean, tag `5080disp`

**THE RESULT, and the metric the plan specified got it backwards.** Mean
edge energy is **−1.02%**, which reads as a regression. It is not.
`sweep_0060` lost the most of all nineteen (**−23.11%**) and went from a
flat plane wearing a smeared texture to real ledges, facets and
self-shadowing. Edge energy counts high-frequency ALBEDO contrast, and
displacement trades that for GEOMETRY whose shading varies smoothly.
The result is **bimodal**: distant/aerial stations gain (+5% to +12% on
seven), ground-level stations lose. **Open the frames; the whole-frame
mean is not a summary.** Full reading:
`_verify/20260811_displacement_interpretation.md`.

### THEN THE CAPABLE-GPU PROFILE LANDED, AND IT RECOVERED THE LOSSES

Ryan supplied an external UE 5.8 landscape standards doc and ruled *adopt
everything that improves quality and resolution*. Applied and measured:

    r.Nanite.MaxPixelsPerEdge                     4.0 -> 1.0
    r.Lumen.HardwareRayTracing.LightingMode         0 -> 1
    r.Shadow.Virtual.ResolutionLodBiasDirectional   0 -> -0.5
    sg.GlobalIlluminationQuality / ReflectionQuality 0 -> 3

**`r.Nanite.MaxPixelsPerEdge` IS THE FINDING, AND NOBODY CHANGED IT — ITS
MEANING CHANGED.** It was an iGPU saving scoped to MESH silhouette. The
moment the landscape became Nanite it governed TERRAIN silhouette, at a
quarter of the available resolution. Measured 4 -> 1 alone:
**mean +9.25% edge energy, 17 of 19 stations gaining**, and it recovers
the same three that lost most when Nanite came on — `verify_ground`
+36.7%, `forest_floor` +27.3%, `sweep_0060` +22.7%. So most of the
near-field "cost" of displacement was this cvar, not the
texture-for-geometry trade (that trade is real, but smaller).

**CUMULATIVE, pre-displacement `5080sp100` -> `5080hq`: mean +7.49%,
median +8.57%, 18 of 19 above the noise floor.** The whole intervention
is a clear net win and the metric now agrees with the frames.

All six are PINNED in `LandscapeLab/Config/DefaultEngine.ini` with the
six downstream `@3` Lumen values pinned beside them — `[SystemSettings]`
sets an `sg.*` VALUE WITHOUT RUNNING THE GROUP, which this project
measured and which the ini already documents for `grass.DensityScale`.
**~~UNVERIFIED~~ — PROVEN ON A COLD BOOT 2026-08-12: 19 of 19 cvars in
effect in a fresh process**, including every downstream `@3` expansion
(`SurfaceCache.AtlasSize` 4096, `FinalGatherMethod` 1,
`Reflections.DownsampleFactor` 1, `SSR.Quality` 3), the fractional
`-0.5`, and the three pre-existing pins. So the `[SystemSettings]`
group trap is genuinely handled rather than assumed. R7's amendment is no
longer UNVERIFIED. Artefact: `_verify/20260812_cold_boot.txt`.

### TWO THINGS THAT ARE NOT DONE, AND ONE IS A FOOT-GUN

1. ~~**THE WORLD IS NOT SAVED.**~~ **SAVED AND VERIFIED FROM THE BYTES
   2026-08-11 — and NOT by me, which is the part worth reading.**
   257 external actor packages + M_AutoLandscape, 284 MB, committed at
   `2ff2b021`. The editor log records
   `LogSlate: Window 'Save Content' being destroyed` at 05:10:35 UTC
   followed by `InternalPromptForCheckoutAndSave` — **a modal dialog was
   resolved with Save.** My `save_level --save` ran two minutes later and
   correctly said "nothing to save", because nothing was dirty by then.
   **This is precisely the foot-gun the previous handoff named, and it
   fired.** It produced the wanted outcome, which is luck, not control:
   a live-but-unsaved editor state is owned by whoever next touches the
   window, not by the session that created it.
   **VERIFIED FROM DISK BYTES WITH A POSITIVE CONTROL**
   (`scripts/verify_saved_nanite.py`, new):
   257/257 saved packages carry `bEnableNanite`, 256 carry
   `LandscapeNaniteMesh` (the parent ALandscape correctly has none) —
   and **400 untouched control packages return ZERO on all three
   tokens**, which is what makes it evidence rather than a token that
   appears everywhere. The 256/257 split reproduces the live reading from
   bytes the live check never opened.
   **CLOSED 2026-08-12 BY A COLD BOOT — the strongest form this project
   has.** PID 16156 closed cleanly (nothing dirty, no save prompt) after
   83,893 s; a fresh editor came up on an EMPTY untitled world, so nothing
   about the landscape was inherited, and `open_level.py --discard` loaded
   Alpine verified by read-back. In that process — which never saw the
   in-memory state — `scripts/verify_cold_boot.py` (new) reads:

       landscape actors      257
       enable_nanite         257
       Nanite component      256      (parent ALandscape has none)
       with a BUILT mesh     256
       unreadable            0

   Identical to the pre-save live reading and to the byte scan, from a
   third representation. **This is the instrument the Pass 1 failure
   defines** — Pass 1 sat "pushed and verified" for three days while the
   live world was a different heightmap, because every check read memory
   or a side-record.
   **NEW AND OPEN — the same save swept VENDOR content.**
   `check_fab_boundary`: **six Fab source files modified in place**, all
   KiteDemo rock material instances (`MI_Cliff01`,
   `MI_MediumBoulder_0012`, `MI_MountainRock`, `MI_MountainRock_Closed`,
   `MI_Scree_001_CC`, `MI_Scree002_NEW`). Gitignored, so they vanish on
   re-download. **NOT re-baselined** — the tool says to do that only once
   the drift is understood and deliberately accepted. Ryan's ruling.
2. **THE CENTRING FIX IS BUILT, and `TMVM_MIP_LEVEL` works here — that
   was the open risk and it did not materialise.** `center: 0.5` is not
   neutral for these maps (means 0.5257 to 0.7602 — not one is 0.5), so
   up to half the ±40 cm amplitude was a per-surface DC offset with a
   ~19 cm step at layer boundaries. I had asserted the opposite in a
   comment **and in a `prove_gates` line**, which is worse: a gate
   printing "asserted" reads as proven. `_centred_height` fixes it at
   source — a second sample of the same map forced to its smallest mip,
   `centred = raw - mipped + center` — so the neutral is READ FROM THE
   TEXTURE and no derived record can drift on reimport.

       material sha  e43b02eb…  (was 2e0f68ad…), 146,494 B
       graph         298 expressions, 298 reachable, 0 ORPHANED
                     +20 exactly as designed: 5 mip samples, 5 subtracts,
                     5 adds, 5 constants
       every _D map  connected 2 (raw + forced-mip), was 1
       samplers      37 audited, 0 mismatches
       grass output  still seeded, compiled clean

   **MEASURED, AND THE VERDICT IS A THREE-WAY SPLIT — do not collapse
   it.** `5080hq -> 5080hqfix`: mean **−0.87%**, median −0.33%, 11 of 18
   stations inside the noise floor.
   - **VERIFIED:** the fix is structurally correct (the table above).
   - **NOT VERIFIED:** that it looks better. Edge energy **could not have
     found an effect even if the fix were perfect** — centring changes
     the DC offset, not the relief amplitude. Rock026 at magnitude 0.16,
     scale_z 500: before `(raw−0.5)` = +8.8…+28.8 cm, after `(raw−mean)`
     = −12.0…+8.0 cm. **Both spans are 20 cm.** The surface drops ~20 cm
     and the relief is identical.
   - **NOT REFUTED:** −0.87% is not evidence against it.
   It is kept on an ANALYTIC argument — half the amplitude was a constant
   offset, and a step at a layer boundary is not terrain. **No render
   confirmed it and the record must not imply one.** An instrument for it
   is in BACKLOG.

3. **A GATE SAID 19 OF 19 OVER A RUN THAT MADE 18, AND IT REACHED A
   REPORT.** The `5080hqfix` capture never wrote `ridge_wide` and exited
   **0**; a bare `verify_frames` then printed *"19 of 19 … the instrument
   produced evidence"*. Cause: `--tag` defaults to `""`, the glob matches
   EVERY tag, and the newest by mtime wins per camera — so a skipped
   camera silently falls back to an older run's frame. **The tool was
   never wrong; the DEFAULT was.** `--tag 5080hqfix` correctly returns
   18/19 MISSING ridge_wide, exit 3. Fixed by FAILING CLOSED: a bare run
   now exits **4** with VERDICT WITHHELD. Proven three directions
   (bare 4 / good 0 / short 3).
   **ALWAYS PASS `--tag`.** And note `ridge_wide` has form — it is the
   same camera that never wrote during the 2026-08-08 shader stall.
   **`capture.py` exiting 0 on a short run is NOT fixed** (BACKLOG).

**GRASS SPAWNS — the visual half is now closed.** The `5080hqfix`
`forest_floor` frame shows dense tufts across foreground and midground.
That was deferred when landscape Nanite went on and is the check the
checklist's step 8 actually wanted.

**AND ONE OPEN QUESTION WITH TWO OPPOSITE ANSWERS.** `forest_floor` gained
dozens of small dark rocks. Either the grass-system `GroundClutter` is
finally spawning (the rebuild modified `GT_alpine_GroundClutter.uasset`,
and that rebuild was recorded as owed) — a WIN — or displacement exposed
hero boulders embedded 0.18–0.40 m against a ±0.40 m amplitude — a COST.
**Density argues for the first.** One capture with `grass.Enable 0`
settles it; BACKLOG carries it, and the embedment item is conditional
on it.

### THE RESOLUTION TARGET IS RULED: 1 m/VERTEX AT FULL REGION SIZE

Ryan ruled 2026-08-11 — adopt whatever gives the most polished look and
detail. The extent half of that was **already settled and I should not
have asked**: `WORLD_VISION.md:171` reads *"World structure: 8064 m is
the PER-REGION size — CONFIRMED"* (reference class Witcher 3 / Final
Fantasy / Tales / Amalur), restated at :198 with only
contiguous-vs-multi-region left open. A "shrink the region to 4 km"
option was put to him without that file being opened. It was never
available.

**TARGET: 8129² at 1 m/vertex = 66,080,641 vertices**, extent 8128 m
(+0.8% over 8064 — 8064 does not tile at 254 quads/component, and hitting
it exactly would need 4096 components instead of 1024 to save 64 m).
The migration keeps the CURRENT layout: same 1024 components, same 256
proxies, 4x quads per component, 16.2x vertices, `scale_xy_cm` 400 -> 100.
**Not blocked** — Gaea Indie's 8K cap covers 8129. Full scope, costs and
sequence in BACKLOG 2026-08-11; step 0 is to prove it on `AlpineLab_v1`,
never against `/Game/Alpine` first. The one real unknown is FRAME COST at
66 M vertices, which is a measurement.

**RESTORE POINTS:** `pre-material-displacement-rebuild-20260811`,
`pre-landscape-nanite-enable-20260811`.

**EDITOR AT HANDOFF: A FRESH PROCESS, and the state is now all on disk.**
PID **10900**, node `78F6C944…`, launched 2026-08-12 16:11, on
`/Game/Alpine` opened cold via `open_level.py --discard` and verified by
read-back. **Nothing is render-state-only any more:** every quality cvar
comes from `DefaultEngine.ini` and was read back in this process, and the
Nanite flags are saved actor properties. The old PID 16156 was closed
cleanly after 83,893 s with nothing dirty.
**The one thing NOT in config: `landscape.Nanite.LiveRebuildOnModification`**
— it is a BUILD trigger, not a quality setting, and is deliberately left
at its default 0. `enable_landscape_nanite.py --build` sets it for the
duration of the operation and refuses if it does not read back.

**TO REVERT THE WHOLE UNIT:** `enable_landscape_nanite.py --off --go`, and
set `material.displacement.enabled` false + rebuild. The three-pin output
path is still reachable and is proven by `prove_gates`.

---

### SUPERSEDED — the unit as it was scoped. Kept as the record of what was decided in advance and what survived contact.

**Two of its instructions were wrong and both are corrected above:**
step 5's "4.0 is likely far too strong" had the right instinct with no
mechanism (it is ±10 m, and the units live in three files), and step 10's
edge-energy criterion inverted the verdict.

### ~~NEXT SESSION'S UNIT — MATERIAL DISPLACEMENT. Fully scoped; do not re-derive it.~~

**Everything below is established, cited and committed. A fresh session
should EXECUTE, not investigate.** Full detail: BACKLOG 2026-08-12
"MATERIAL DISPLACEMENT IS FEASIBLE AND FULLY CITED".

**THE ONE FACT THAT DECIDES THE DESIGN:** `MP_Displacement` exists at
value 32 (`SceneTypes.h:181`) but is `UMETA(Hidden)`, so it is **NOT in
the Python `MaterialProperty` enum** — proven with a positive control
(`MaterialProperty(32)` and `.cast(32)` both refuse; `MP_MAX` reads 35 in
the same payload). **`connect_material_property` cannot wire Displacement
at all.** The only route is `use_material_attributes` +
`MakeMaterialAttributes` (which carries `FExpressionInput Displacement` at
header line 77) → `MP_MATERIAL_ATTRIBUTES` (33, exposed).

**ORDERED CHECKLIST — each step's failure mode is why it is where it is:**

1. **RISKY-OP tag first**, named for the operation. The failure mode here
   is UE's default checkerboard across the whole landscape, which this
   project has already shipped once.
2. **Change the BUILDER (`make_landscape_material.py`), never the graph by
   hand** — a hand-wired pin vanishes on the next rebuild. Put it behind a
   recipe flag so the old path stays reachable.
3. **The `_D` maps are declared ONLY when a sub-surface is active**
   (`:633-636`). Displacement needs them unconditionally — that is a
   change to the SINGLE DECLARATION, not an addition beside it. Getting
   this wrong is precisely the sub-surface bug: the build dies AFTER the
   destructive clear, on assets that existed the whole time.
4. **Preflight every new texture BEFORE `delete_all_material_expressions`.**
   The clear is the point of no return in memory.
5. Set `enable_tessellation=True` and `displacement_scaling` (reads
   `{magnitude 4.0, center 0.5}` today; 4.0 is likely far too strong for a
   4 m-per-texel landscape — start small and measure).
6. **Rebuild ATTENDED.** B-BUILD-UNKNOWN is open: the builder can report
   catastrophe on a graph that is fine, because a truncated transport
   reply is indistinguishable from a mid-build death.
7. `audit_material_connectivity` on the **NEW bytes**, expecting **0
   orphans**, then `audit_material_samplers`.
8. **Confirm grass still spawns.** `LandscapeGrassOutput` shares this
   graph (`:2300`) and its survival across the clear is relied upon
   (`:1217`).
9. **Only then** `enable_nanite` on the Landscape + 256 proxies and build
   Nanite. Enabling it before the material buys **no silhouette** — it
   renders the same 4 m geometry as a Nanite mesh.
10. **Compare with EDGE ENERGY, not mae.** mae cannot tell sharper from
    differently blurry; the ScreenPercentage A/B already paid for that
    lesson. Baseline to beat: tag `5080sp100`.

**EDITOR STATE AT HANDOFF:** PID 16156 alive on `/Game/Alpine`, with
**Lumen ON and `r.ScreenPercentage` 100 as RENDER STATE ONLY** — both die
with the process and nothing was saved. A fresh session gets a cold
editor and must re-assert them (`render_condition --lumen on --cvar
r.ScreenPercentage=100`) before any comparison against `5080lumen` or
`5080sp100`.
**`capture.py --timeout N` is its DISCOVERY WINDOW** — it sits N seconds
at the identity gate before writing a frame. Use 600, not 900, and do not
read "still at the identity gate" as a stall.
**Nothing may touch the editor while a capture runs** — one command
connection per node, and the second client wins silently.

---

### HANDOFF 2026-08-10b (MIGRATION VERIFIED — the OmniBook can be wiped) — START HERE.

**The project now lives on the Legion Pro 7i at
`C:\Users\Admin\UE5LandscapePipeline`. No editor was launched, no world
was opened, nothing in `/Game/` was touched this session.**

**THE COPY IS VERIFIED, AND IT WAS INCOMPLETE WHEN I FOUND IT.** Four
instruments, three different representations, plus one repair:

| Instrument | Scope | Result |
|---|---|---|
| `git fsck --full --strict` | whole object DB, all history | **exit 0, zero non-dangling lines** |
| SHA-256 of every LFS object vs its own filename | **18,430 objects, 8.9 GB, all history** | **0 mismatch, 0 unreadable** |
| history-reference completeness | 18,241 referenced oids | **2 MISSING → repaired → 0** |
| worktree content vs git's hashes | 2,263 LFS + 275 plain | **0 bad** |

**THE TWO MISSING OBJECTS ARE THE HEADLINE.** `git fsck` passed, and
`git lfs fsck` printed "OK" — and both were blind to it.
`83941ddd…` and `83958528…`, external actors of **`/Game/Alpine`**, the
main world. The interrupted move had left them behind, as the *only* two
files under `C:\Migration\LandscapeLab_repo\.git\lfs`. Both hashed
correctly at the source, were copied in, and re-verified in place.
**Had the OmniBook been wiped on the strength of `git fsck` alone, two
Alpine actor packages would have been gone**, and `origin/main` is 60
commits behind so GitHub does not hold them.

**WHY `git fsck` WAS NEVER THE RIGHT INSTRUMENT, stated plainly because
the handoff that briefed me said it was.** `git fsck` validates the git
OBJECT DATABASE — 391 MB packed here. The 8.9 GB is in `.git/lfs`, which
it never opens. Git tracks LFS files as 130-byte POINTERS, and a pointer
is intact whether or not the object it names exists. And `git lfs fsck`
is scoped to **HEAD** (2,263 of 18,241 files) — it returned "OK" in 3
seconds, which was the tell: 8.9 GB cannot be read in 3 s. **The check
that found the defect was the one that read a DIFFERENT
REPRESENTATION — object bytes rather than pointer bytes.**
Non-negotiable 0, on the migration itself.

**Every gate here was positive-controlled**: the hash comparator was fed
a deliberately corrupted row first and flagged exactly it.

**ALSO VERIFIED, by a fourth representation — the Gaea package.**
`verify_build.py` on `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\002`:
**exit 0**, 6 files, all 16-bit 4096², none degenerate, and the
registration control REPRODUCES (flow median **38.8** vs random **50.0**,
separation −11.2, against −12.4 recorded at intake). That is pixel
statistics, not a hash — a corrupted transfer could not reproduce it.
71 Gaea autosaves restored.

**RYAN'S BLOCKER IS CLEARED — and check my reasoning before relying on
it.** `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain`
now EXISTS and its SHA-256 matches **none** of the 71 autosaves. The
refusal condition in `rebuild_terrain.py` is specifically "is an
autosave", and this is not one. **That is weaker than "Ryan saved it
deliberately"**, which I did not verify and cannot from a hash.

### WHAT IS NOT DONE, AND ONE THING NEEDS YOUR RULING

**`LandscapeLab 5.8\` — an 11 GB UNTRACKED DUPLICATE OF THE PROJECT, and
it is a live foot-gun.** Byte-identical where it matters: the 194 MB
`AlpineLab_v1.umap` hashes the SAME as the tracked copy
(`a641588f…`), as does `M_AlpineLab.uasset`. It differs only in
generated files and in `.uproject` `EngineAssociation` ("5.8" vs the
tracked GUID). `bootstrap.py` defines `UE_PROJECT_ROOT` as
`REPO_ROOT/"LandscapeLab"`, so **the tracked directory is canonical and
this one is invisible to every rule-7 check** — an editor opened against
it would write work git never sees. **I did not delete it** (11 GB, and
standing rule 2 forbids the fast way; `_trash/` is inside the repo, so
that is not the right destination either). **Decide: delete it outside
the repo, or keep it deliberately.** Until then, confirm which directory
an editor is on before trusting rule 7.

- **NO R0 COLD REPLAY.** BACKLOG 2026-08-09 says the new machine is the
  only real test R0 will ever get and *"do not hand-migrate"* — the
  folder was copied anyway, so that opportunity is partly spent. It is
  still recoverable from a scratch clone; not attempted here.
- **`bThrottleCPUWhenNotForeground=False`** set in
  `DefaultEditorPerProjectUserSettings.ini` per the ratified BACKLOG
  item. **Non-negotiable 17 applies to my own edit: the file records an
  OVERRIDE, not the state in effect** — unverified until an editor runs.
  `bAllowSlateThrottling` is a second throttle, left True, not ruled on.
- **`r.ScreenPercentage=70` and `ManualScreenPercentage=70` DELIBERATELY
  UNCHANGED.** BACKLOG's words are *"do not just raise numbers —
  re-derive them"*, and re-deriving needs a measurement I did not take.
  A silent quality cap on a capable GPU, still in place, on purpose.
- **RAM IS 31.4 GB, NOT 64.** The BACKLOG entry that anticipated this
  machine records 64 GB. Measured 31.43. Every RAM-derived budget —
  `resource_guard`'s floor, the instance ceiling — re-derives from
  31.4, and the headroom over the OmniBook is ~2x, not ~4x.
- Deps installed: numpy 2.5.2, Pillow 12.3.0, scipy 1.18.0 (R0's list).
  UE 5.8, Gaea 2, Python 3.12.10 present. **No editor launched, so
  nothing about the editor is verified** — rule 7, remote exec, MCP and
  the Python plugin are all UNTESTED on this machine.
- 13 `_trash/` files the copy missed were restored from git.
- `C:\Migration` still holds the source and 4.6 GB of vendor zips.
  **Keep it until the wipe decision is made.**

**HARDWARE NOW: RTX 5080 Laptop (16303 MiB VRAM, driver 610.88), Core
Ultra 9 275HX, 24 threads, 31.4 GB RAM, 2560x1600.** Every GPU number in
R13 belongs to the iGPU and is HISTORICAL, not wrong — R13's CALIBRATION
CLASS labelled them, and that labelling is what makes them safely
retirable. The 26-item re-open list is BACKLOG 2026-08-09.

### THE EDITOR RUNS HERE, AND THE WORLD IS INTACT — verified, not assumed

`bootstrap.py`: **one node, MATCH, engine 5.8.1**-56057345 (was 5.8.0).
`open_level.py --discard` opened **`/Game/Alpine`, verified by read-back**
— a genuinely cold load from disk in a process on a different machine.
`recover_state.py` then read the live world:

    conifer 157,554 · boulder 759 · CliffOutcrop 4,356 · CliffOutcropB 2,987
    TalusField 1,578 · TalusFieldC 1,189 · TreeStump 1,171 · TalusFieldB 912
    TalusChannel 479 · CliffFace 84            TOTAL 171,069

**171,069 is EXACTLY the recorded total**, species by species, read from
foliage components that cannot see the plan. Migration verified through a
fourth representation. The 7 unreadable properties are the same
documented `VALUE UNVERIFIED` set, unchanged.

### WHY IT DOES NOT LOOK AAA — AND IT IS CONFIGURATION, NOT CONTENT

Ryan asked how the render compares to AAA terrain. **It does not match.**
The live cvars, read from the editor by `recover_state`, say why:

    r.DynamicGlobalIlluminationMethod  0.0   <- LUMEN GI OFF ENTIRELY
    r.ReflectionMethod                 0.0   <- NO REFLECTIONS
    sg.GlobalIlluminationQuality       0.0
    sg.ReflectionQuality               0.0
    r.ScreenPercentage                70.0   <- rendering at 70%
    r.Nanite.MaxPixelsPerEdge          4.0   <- 4x coarser than default 1.0

**All six are the iGPU compromises, still live on a 5080.** Ranked by
pixel impact, from frames I opened rather than from theory:

1. **NO GLOBAL ILLUMINATION.** No bounce, no contact depth. Every
   shadowed surface is lit only by the skylight. This is the single
   largest gap and it is one cvar.
2. **70% SCREEN PERCENTAGE IS EATING THE FOLIAGE.** Conifer needles are
   thin alpha-tested cards; at 0.7 scale they alias and drop coverage.
   **This is a direct contributor to defect 3, not a separate issue.**
3. **THE CANOPY READS AS BARE POLES** — and this one is PARTLY THE ASSET,
   measured offline so nobody re-diagnoses it from the render:
   `fir_tree_01_twig_alpha_4k.png` is **24.02% opaque** and effectively
   BINARY (25.06% at clip 0.1 vs 23.56% at 0.5) — **so the opacity-mask
   threshold is NOT the lever; moving it buys ~1.5%.** The needle albedo
   where opaque is **mean RGB 85/81/49** — dark olive-brown, with green
   BELOW red. `fir_tree_01` is a sparse young fir and 157,554 of them
   read as scrub, not as an alpine forest. **Do not "fix" this in the
   material before deciding whether the ASSET is the answer.**
   Evidence: `captures/alpine/*_CLIFFS_TALUS_LUMEN2.png`,
   `forest_floor` and `rock_grounding`. The foreground tree at ~5 m is as
   bare as the distant ones, **so it is NOT LOD** — that was checked.
4. **Terrain reads as smooth rolling mounds — AND THIS IS A SAMPLING
   CAP, NOT A MATERIAL DEFECT.** Ryan pointed out the map is 2017x2017.
   The arithmetic: 2017 vertices at `scale_xy_cm` 400.0 =
   **4.00 METRES PER HEIGHTMAP TEXEL** over 8.064 x 8.064 km (6,503 ha).
   A cliff lip, a ledge and a crisp arete are all sub-4 m, so they cannot
   be represented at all. **The smooth profile in every ground frame is
   the heightmap's Nyquist limit.** Triplanar, macro variation, detail
   relief and GI all buy SURFACE detail against a smooth SILHOUETTE —
   which is exactly what the frames show, and why none of them fixed it.
   The only route that does NOT invalidate Pass 1 and all 171,069
   placements is **landscape Nanite + displacement**, which adds
   silhouette above the heightmap frequency without touching the
   heightmap. Cost that first. BACKLOG 2026-08-11 carries all three
   routes. The Gaea `AlpineLab_v1` build is already 4033², so it is the
   place to test the resolution question without touching `/Game/Alpine`.

**CLOSED WHILE LOOKING: the 2026-08-09 handoff's item 1.** It said *"no
frame yet shows the new rocks"* and ranked looking at one first. The
`CLIFFS_TALUS_LUMEN2` set had completed and nobody had opened it.
**`cliff_face` shows the rock instances on the slope** — the cliffs and
talus are on pixels now, not only in a count.

**THE THROTTLE IS REAL HERE AND MY OWN FIX DID NOT TAKE.** Measured on
this machine: **2.03 CPU-seconds per 20 s wall backgrounded vs 36.06
foregrounded — 17.8x**, reproducing the OmniBook's ~21x. I had set
`bThrottleCPUWhenNotForeground=False` in the ini and **it did not deliver
the behaviour** — non-negotiable 17, landing on my own edit, which is why
it was flagged UNVERIFIED rather than claimed. `bAllowSlateThrottling` is
still True and is the untested suspect. **Operationally: force the editor
foreground before any capture; the ini is not sufficient.**

### LUMEN A/B RUN — 38.2x THE NOISE FLOOR, AND IT NEEDS THE EXPOSURE RE-SOLVE

Single variable, `render_condition.py --lumen on` (0 -> 1 on
`r.DynamicGlobalIlluminationMethod` AND `r.ReflectionMethod`, both read
back), same 19 stations, tags `5080baseline` -> `5080lumen`, both 19/19
`verify_frames` clean.

    mean mae 0.11390  =  38.2x the 0.00298 noise floor
    19 of 19 stations above the floor

**THE SPATIAL PATTERN MATCHES THE MECHANISM, which is what makes it
evidence and not just a big number.** The two largest movers are
`sweep_0150` (96.4x) and `sweep_0060` (80.0x) — **the exact two stations
the record documents as sitting in TERRAIN SHADOW**, and shadowed ground
is where bounce contributes most. The two smallest are `lod_near` (4.4x)
and `lod_far` (5.0x), close-ups of a tree against open sky with almost no
surrounding geometry to bounce from. That contrast is the discriminating
control.

**A LOOK-CLAIM I MADE AND THE MEASUREMENT OVERTURNED.** I read the Lumen
`forest_floor` frame as blown out. It is not — **blown pixels went DOWN,
0.3% -> 0.0%**. What actually moved:

    station        blown%      mean luma      std        MIN luma
    forest_floor  0.3 -> 0.0  0.660->0.715  0.215->0.171  0.036->0.241
    player_eye    0.1 -> 0.0  0.413->0.554  0.240->0.195  0.062->0.155
    sweep_0350    0.0 -> 0.0  0.387->0.599  0.314->0.195  0.071->0.203

The DARKEST pixels lifted **2-7x** while the maxima held. That is shadow
lifting, not clipping. Non-negotiable 16 again: the eye is a poor
photometer, and "washed out" is what reduced CONTRAST looks like.

**CONSEQUENCE, and it is already measured — do not re-derive it.** Mean
luma up on every station means R13's `-1.786` EV was solved against a
scene without GI and no longer fits. The 2026-08-09 handoff already
carries the Lumen value: **-1.786 -> -1.897 EV**. Apply that BEFORE
judging the look, and re-take any brightness judgement afterwards.

### SCREEN PERCENTAGE 70 -> 100: DONE, AND IT REFUTES MY OWN HYPOTHESIS

Single variable (Lumen on in both), tags `5080lumen` (SP70) ->
`5080sp100`, both 19/19 `verify_frames` clean.

    mae:          mean 0.01217  =  4.1x the noise floor, 19 of 19 above
    EDGE ENERGY:  mean +1.3%,   only 13 of 19 stations gained

**I CLAIMED "70% IS EATING THE NEEDLES". THE MEASUREMENT SAYS NO.** mae is
the wrong instrument for a sharpness claim — it measures how far pixels
MOVED, and a resolution change shifts edges whether or not detail was
gained. Mean gradient magnitude asks the real question, and the answer is
that SP100 adds **+1.3%** edge energy on average, with **six stations
LOSING** it (`cliff_face` -2.7%, `sweep_2000` -1.5%).

**THE DISCRIMINATING ROW IS `player_eye`:** largest mae of all 19
(**13.4x**) and **+0.1%** edge energy. Its pixels moved more than anywhere
else and got no sharper — that mae is resampling and TAA jitter, not
detail. Two stations did gain properly, `forest_floor` **+11.9%** and
`ridge_wide` **+11.8%**, so the cvar is doing SOMETHING and is not being
bypassed by the capture path; the effect is just small and uneven.

**CONCLUSION: ScreenPercentage is a MINOR lever on this scene, not the
canopy fix.** It stays at 100 as render state; it does not deserve a
config change on this evidence. The canopy remains the ASSET
(24.02% opaque binary atlas, needle albedo RGB 85/81/49) and the terrain
remains the 4.00 m SAMPLING CAP. **Ranked by measured effect, the levers
are: Lumen 38.2x >> ScreenPercentage 4.1x-but-mostly-not-sharpness.**

**AND THE "STALL" WAS PARTLY ME MISREADING A TIMEOUT.** `capture.py` takes
`--timeout` as its DISCOVERY WINDOW, so `--timeout 900` waits 15 minutes
at the identity gate before it writes anything. Both successful captures
used 600 and produced their first frame near the 10-minute mark. **The
re-run I killed for being "stuck at the identity gate" was very likely
about to work.** The connection-stealing in item 1 below is still real —
that capture ran well past its window with zero frames while the editor
served my calls — but *"stuck at the gate"* on its own is NOT evidence of
a stall, and I killed a healthy run on it.

**THE EARLIER FAILURES, KEPT AS THE RECORD:**
`r.ScreenPercentage` IS set to 100 (70 -> 100, read back, via the new
`render_condition --cvar`), but **no `5080sp100` frames exist** and the
comparison against `5080lumen` was never made. Two separate self-inflicted
failures, both worth more than the missing frames:

1. **I ran `render_condition.py` twice as a regression check WHILE
   `capture.py` held a command connection to the same node.** The capture
   then produced zero frames and logged nothing for ~15 minutes with its
   process still alive — no error, no timeout. The editor served my calls
   normally throughout, so only the capture was dead. **One command
   connection per node; the second client wins and the victim hangs
   silently.** What diagnosed it was the EDITOR's log, not the capture's
   stdout: the newest line was my own payload with no capture activity
   after it.
2. **Then I `Stop-Process`-killed that capture**, and the re-run never got
   past its identity gate — consistent with the editor holding a half-open
   command connection from the killed client. The editor is alive but IDLE
   (0.95 CPU-s per 10 s, working set trimmed to 0.39 GB), so it is not
   serving anything.

**OPERATIONAL RULE, and it is cheap:** *nothing touches the editor while a
capture runs.* A guard belongs in the remote-exec layer so a second client
REFUSES rather than silently winning — BACKLOG 2026-08-11.
**To finish this unit: restart the editor, `open_level.py --discard`,
re-assert `--cvar r.ScreenPercentage=100` AND `--lumen on` (both are render
state and die with the process), then capture `5080sp100` with nothing else
connected.**

### ROUTE (c) IS REAL IN 5.8 — FOUR CITATIONS, EACH OPENED

Landscape Nanite displacement is the one route to more silhouette that
does not invalidate Pass 1 or the 171,069 placements, so it was checked
against this install rather than remembered:

| Claim | Where |
|---|---|
| a landscape can BE Nanite | `LandscapeProxy.enable_nanite`, PythonStub :531548, plus `nanite_position_precision`, `nanite_skirt_*`, `nanite_max_edge_length_factor` |
| Nanite tessellation exists | `r.Nanite.Tessellation`, `NaniteCullRaster.cpp:94` |
| **Nanite LANDSCAPE displaces** | `LandscapeRender.cpp:224-228`, whose own help text reads *"Allow Nanite landscape to disable displcement on individual clusters in the distance."* (engine's typo) |
| the material gate | `MaterialInstanceBasePropertyOverrides.enable_tessellation` — *"Whether or not tessellation is enabled. Required for displacement to work."*, PythonStub :81519 |

**A NEAR-MISS THAT PROVES THE RULE.** I first grepped `LandscapeNanite.cpp`
for displacement, got ZERO hits, and was one sentence from writing
"landscape Nanite does not displace". **That file does not exist** — it is
`LandscapeNaniteComponent.cpp`. A zero from a path that is not there is
"I COULD NOT LOOK", not "I looked and it is absent" (non-negotiable 6),
and it would have killed the only cheap route on the board.

**LUMEN IS RENDER STATE ONLY AND DIES WITH THE EDITOR.** Nothing was
saved and no config file was touched. Making it permanent is a
`RECIPES.md` R7 edit and should follow the exposure re-solve and a GPU
cost reading in the new calibration class — **not precede them.**

**NEXT, in order.** (1) Set the six cvars above to capable-GPU values and
capture the SAME stations for a single-variable before/after — the
baseline set is tagged `5080baseline`. **BACKLOG's words are "do not just
raise numbers — re-derive them", so each one gets a GPU cost reading in
the NEW calibration class.** (2) Then the canopy, asset-first. (3) The
AlpineLab_v1 grass defect below is unchanged; its five eliminated
hypotheses stand, hardware touched none of them.

---

### HANDOFF 2026-08-10 (overnight: AlpineLab_v1 is a populated, surfaced world) — superseded by the above; still accurate.

**Tree clean. `/Game/Alpine` UNTOUCHED all night.** Editor PID 13236 alive
on `/Game/Game/GaeaLab/AlpineLab_v1`, level saved (194.3 MB) and verified
from the artefact.

**WHAT THE WORLD HAS NOW**, counted from the engine's own components:

    Scree_001               4,000     scree_slab_001, 33,855 tris
    SM_Scree002a            8,000
    SM_MountainRock_Closed    589     ridge outcrops
    SM_River_Rock_01        3,000     drainage channels
    fir_tree_01_c_LOD0      9,000     conifers
    Medium_Boulder_001      6,000     field boulders
                           ------
                           30,589     1 IFA, 6 components

Plus `M_AlpineLab`: three photogrammetry surfaces blended by the Gaea
masks, compiling with **zero errors**. Frames at 3840x2160 in `_verify/`.

**FIRST THING TO FIX: GRASS DOES NOT SPAWN — and five hypotheses are
already eliminated.** Do not re-test these:

| Ruled out | By |
|---|---|
| grass type missing/empty | asset read-back: 3 varieties, 14/18/22 per 10 m² |
| output node absent | `get_material_expressions`: 1 node, right name, right asset |
| the weight wire never landed | `audit_material_connectivity`: **90/90 reachable, 0 orphaned** |
| scalability zeroing it | `grass.DensityScale` 1.0, `grass.Enable` 1.0, `sg.FoliageQuality` 1.0 |
| cache not flushed | `grass.FlushCache` ×2 + `set_grass_enabled(True, flush_grass_maps=True)` |

The connectivity result kills my own leading theory: the wire DID land.

**THE NEXT TEST IS ONE EDIT** — wire a `Constant 1.0` into the grass
output in place of the computed weight, rebuild, flush, capture. Grass
appears → the weight evaluates to zero and the fault is arithmetic.
Nothing → the fault is between a connected output and the landscape, and
the next suspects are a full landscape **Build** (grass maps are built as
part of it, and this landscape has never had one) and the grass meshes'
own materials.

**THREE THINGS THAT WILL SAVE THE NEXT SESSION HOURS**

1. **`MODE_EXEC_FILE` MEANS THE COMMAND IS A FILENAME.** Inline source
   works for short payloads and silently fails for longer ones, showing
   as *"Could not load Python file 'C:/…/Win64/<your entire source>'"*.
   Both AlpineLab builders now write the payload under `Saved/` and send
   the path. This cost three failed placement runs and two wrong
   theories.
2. **RECOMPRESSING A TEXTURE IS A CHANGE TO EVERY MATERIAL THAT SAMPLES
   IT.** Masks moved to BC4 → required sampler type changed →
   `VerifySamplerType` errors on every mismatch → the whole material
   stopped compiling → the ground rendered UE's default **checkerboard**.
   `MaterialEditingLibrary.recompile_material` RETURNS the error list and
   named all five nodes in one call; the log only says "Failed to
   compile".
3. **THE EDITOR THROTTLES HARD WHEN NOT FOREGROUND** — measured on one
   running workload, back to back: **2.2 s of CPU per 20 s backgrounded
   vs 46.3 s foregrounded**, a ~21× difference. Long editor operations
   and captures need the window focused.

**MEMORY WAS THE BINDING CONSTRAINT ALL NIGHT.** Five 4033² uncompressed
masks asked for 4,609 MiB DDC builds against a 994 MiB limit. BC4 + a
2048 cap took the editor 6.16 → 4.42 GB and free RAM 0.48 → 1.94 GB,
which is what made a 4K capture possible at all. Cost: masks are 2 m per
texel instead of 1 m; the scatter reads the full-res PNGs offline and is
unaffected.

**Instance counts were cut on purpose** — planned 58,556, placed 30,589.
The budget gate refused 71,556 against its 60,000 ceiling and the caps
were lowered again by hand at 0.48 GB free. **The ceiling was never
raised to fit the plan.**

**Restore points:** `pre-alpinelab-landscape-import-20260809`,
`pre-alpinelab-scatter-20260809`.

**Machine state I changed:** terminal windows minimised and the editor
forced foreground, to stop the throttle. Dies with the session.

### HANDOFF 2026-08-09b (Gaea intake + Ryan's two rulings) — still live.

**Tree clean at `c38e852d`. NO EDITOR WORK this session — `/Game/Alpine`
untouched, no UE5 import run, nothing saved.** A Gaea 2 export package
was taken in at `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\002`,
verified, resized 4096 → 4033, and both open items were ruled and
applied. Recipe: **R-GAEA**. This is a SEPARATE evaluation terrain; it
does not touch the alpine world described below.

- **Z SCALE = 180.81, PROVENANCE MEASURED.** Gaea declares
  `Terrain/Height = 2500.0 m`, which is the PROJECT range, not this
  build's span. The build occupied 496–24763 of 65535 before the export
  was stretched to full range, so span = 925.73 m and
  Z = 925.73/512×100. **The naive answer, 488.3, is 2.7× too tall and no
  instrument here could have caught it.** Recoverable only because the
  un-normalized `Snow_Out.png` was kept in `_archive/`.
- **R1's "CROP, NEVER RESAMPLE" is NARROWED** (`RECIPES.md:552`, original
  wording quoted verbatim in place, `AlpineLab_v1_002` named as the
  motivating case). The defect is *independence*, not resampling.
  `verify_build.py` now **ENFORCES** whole-package dimension agreement,
  exit 4 — proven, all 6 files at 4033².
- **Registration proven offline, with a control:** the flow mask's
  brightest 1% sits at height percentile **37.7** against a random
  control at **50.1**, separation −12.4. Drainage is in the low ground,
  so height and masks are in register after the resize.
- **`scripts/rebuild_terrain.py` — one command, and it has NEVER RUN.**
  `python scripts/rebuild_terrain.py --go` (bare invocation is a dry
  run). Preflight, normalization and every refusal are proven offline —
  `prove_rebuild_terrain.py` **12/12**, including a 16,777,216-of-
  16,777,216-sample reproduction of build 002's adopted heightmap. **The
  Gaea subprocess call itself is unexecuted.** `Gaea.BuildManager.exe` is
  still broken on the Indie licence; `Gaea.Swarm.exe` is the headless
  path.
- **BLOCKED ON RYAN, one action:** every `AlpineLabe_v1*.terrain` on this
  machine is a Gaea **AUTOSAVE**, and the script refuses to build the
  canonical terrain from a file Gaea rotates and overwrites. Save it once
  from Gaea to
  `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain`.
- **Also not done:** R-GAEA step 4 — the landscape itself is created BY
  HAND in Landscape Mode (UE 5.8 Python cannot create one) and has not
  been, so `ue5_import_alpinelab.py` has not run either.

### HANDOFF 2026-08-09 (the unattended night run) — still live, read after the section above.

**THE WORLD HAS CLIFFS AND TALUS. 171,069 instances placed and SAVED.
Tree clean at `5c34d6da`. Editor PID 27616 alive, clouds OFF and Lumen ON
as render state only.**

Ryan asked for maximum quality unattended, then explicitly authorised
third-party ingestion and told me not to hold back. **I did not pull any
third-party asset or code** — not on the licence question, which he
waived, but because the biggest available win was already staged and I
judged that finishing it beat starting an asset hunt I could not
render-judge at 3am. That is a judgement call and it is his to overrule.

## WHAT LANDED

| | |
|---|---|
| **Cliff + talus MESHES placed** | 13,515 rock instances, 7 new species |
| Nanite | built on **8** rock meshes, verified by Nanite data |
| Clutter density | 1.5 → **10 per 10 m²**, cull 70 → 40 m |
| World | **saved**, 1,484 packages, committed `1747c93e` |
| Restore point | `pre-cliff-talus-placement-20260809` |

    Conifer 157,554 · Boulder 759 · TreeStump 1,171
    CliffOutcrop 2,987 · CliffOutcropB 4,356 · CliffFace 84
    TalusField 1,578 · TalusFieldB 1,189 · TalusFieldC 912
    TalusChannel 479          TOTAL 171,069, planned == counted

Talus sits on the **computed deposition field** (174 ha), not a slope
band — the naive 25-38° band is 1,460 ha of which 90.4% has no cliff
feeding it. Rock triangle cost is **0.644M** local worst case against
conifers' 39.6M: the geometry was missing, not expensive.

## THE THREE THINGS THAT WILL BITE YOU IF NOBODY READS THEM

1. **`save_level` cannot report its own result at this scale.** The
   payload builds a 418 KB reply and the transport drops it, so a save
   that SUCCEEDED reports as nothing. I added a result-FILE path; it
   works for the probe phase and **fails for the save phase because both
   phases share one filename**. **Verify a save from the ARTEFACT —
   package mtimes and `git status` — never from the tool's report.**
   Evidence this one landed: 1,484 packages written at 08:00:53, probe
   classification 0 foreign / 0 unreadable.

2. **Nanite REPLACES LOD0 with a reduced fallback.** `boulder_medium_01`
   4,136 → **1,796**, `cliff_face_01` 29,154 → **6,230**. Nanite renders
   full density; the fallback is 20-40% of the ORIGINAL LOD0. **If Nanite
   ever does not run, these rocks are worse than before tonight.** Check
   under `r.Nanite 0` before rendering the clip.

3. **Disk is at ~26 GB free against CLAUDE.md's recorded 50 GB floor.**
   Content 19.6 GB, Saved 6.54 GB, DDC 4.07 GB. Not caused by tonight
   alone, but it is now the binding constraint on any big operation.

## STILL UNVERIFIED — AND THIS IS THE HONEST GAP

**No frame yet shows the new rocks.** The only capture that completed
before the run was killed is `ridge_wide` at 1654 m, where 2-4 m rocks
with 240-400 m culls are all culled. A fresh capture (`CLIFFS_TALUS_LUMEN2`)
was running at handoff. **Until a GROUND station is looked at, "the world
has cliffs" rests on the placement count and the saved packages, not on
pixels.** The stations that would show it: `rock_grounding`, `cliff_face`,
`forest_floor`, `verify_ground`.

Also unverified: the material rebuild for the 10/10m² clutter. Its SHA
moved `84394299` → `9f888a66` so it built, but its output was lost to the
same transport limit and **no connectivity or sampler audit has run on
those bytes**.

## MACHINE STATE I CHANGED, so it can be put back

- `powercfg` monitor / standby / disk / hibernate timeouts on AC → **0**,
  and `HKCU\Control Panel\Desktop\ScreenSaveActive` → **0**. Ryan asked
  for this so the run would not be interrupted. Machine-global, outside
  both roots.
- Editor render state: clouds OFF, Lumen ON. Dies with the process.
- `check_fab_boundary` re-baselined after the 8 declared Nanite edits.

## WHAT I WOULD DO NEXT, in order

1. **Look at a ground frame.** Everything else is bookkeeping until the
   cliffs are seen.
2. Audit the rebuilt material on its current bytes.
3. Fix `save_level`'s two-phase filename collision — it is one line and it
   removes a class of "did it save?" uncertainty permanently.
4. Then the exposure re-solve under Lumen is already measured and waiting:
   **-1.786 → -1.897 EV**, belonging in the MRQ recipe, not the world.

---

### HANDOFF 2026-08-08e (carpet clutter on the grass system) — superseded; still accurate.

**Tree clean at `49a2c536`. Editor PID 25720 alive, rule-7 verified.
NOTHING PLACED — the world is untouched by this entire session.**

Ryan ruled: **move carpet density to the grass system.** Done in the
recipe, gated and proven. **The remaining step is a landscape material
REBUILD, and it is attended** — grass types are built by
`make_landscape_material.py`, not by `place_foliage`, and
B-BUILD-UNKNOWN is still open on that builder.

    GroundClutter   system "grass"  layer Grass  cull 70 m
                    density_per_10m2 1.5
                    varieties  boulder_small 0.6 / river_rock 0.4

On R11's own convention (`instances = πR²·d`, the arithmetic behind its
94,248 tufts): ~**2,309** in the cull disc, ~**2.1M triangles** against
grass's locked 29.8M, **spacing 2.58 m vs the instance path's 41.5 m —
16×**. `TreeStump` stays an instance `clutter` species: sparse landmark,
and the per-trunk canopy prior is what the instance path is good at.
Instance total fell 25,776 → **1,930**.

**THE PRIORS DO NOT SURVIVE THE MOVE, AND THAT WAS MEASURED BEFORE IT
WAS ACCEPTED.** `make_landscape_material.py:2306` wires each grass pin
**straight to the layer weight mask** and nothing else. But the Grass
layer already separates forest from non-forest at **6.0×** (16 m forest
density 0.547 inside `Grass>0.5` vs 0.091 outside), which *is* the
canopy prior's intent. Residual spread inside the layer is p10 0.21 →
p90 0.79; buying it back needs a baked prior texture, a builder multiply
and a rebuild. **Not taken, recorded with the number.**
**`DrainageStone`'s flow character is genuinely LOST** — the Grass layer
does not predict drainage at all. Said plainly because it subtracts from
the earlier "use conifer positions" ruling.

**A GATE REFUSED, WAS RIGHT TO, AND WAS ROUTED BY THE WRONG KEY.**
`landscape_spec._recipe_mesh_paths_split:202` sends meshes to a registry
by **species kind** (`"role" in sp`), so a Fab rock used by a grass
species was asked for a Blender-normalised row it can never have. Its own
docstring says both sets carry *"the SAME guarantee … through two
different instruments"* — and that guarantee is a property of the MESH.
Now both registries are consulted; a mesh in neither is still refused.

**AND THE FIX HAD TO BE STRICTER.** `rock_scatter` READS
`base_offset_z_m` and subtracts it; **the engine's grass system corrects
nothing** — it puts the PIVOT on the surface. A box-centred pivot buries
exactly **50%** by construction. New `uncorrected_pivot_errors()` bounds
it at 25%:

    boulder_small 17.0% OK    boulder_medium_01  47.6% REFUSED
    river_rock    16.8% OK    hero_boulder_large 50.0% REFUSED

**The two carpet meshes passing was LUCK, not design.** `prove_gates`
gains 5/5 UNCORRECTED PIVOT probes, positive control first; 41 checkers,
exit 0.

**NEW HAZARD, recorded before it bites:** a rock species' RNG is keyed by
its **position** in the list (`rock_scatter.py:753`), so removing two
species re-rolled `TreeStump` 1,208 → 1,171 with every row different.
Boulder survived only by being index 0. **Had TreeStump been placed, this
edit would have required re-placing all of it.** Keying by species NAME
would fix it but moves the 759 saved boulders — do it before more is
placed, never after. BACKLOG.

**NEXT: the material rebuild, attended.** Then placement, which needs a
RISKY-OP tag and must hand `place_foliage --place` the VEGETATION plans
in the SAME run or the orphan sweep deletes the conifers.

---

### HANDOFF 2026-08-08d (shared priors + Pass 5 planned) — superseded by the above; still accurate.

**Tree clean at `afc6b715`. Editor PID 25720 alive and rule-7 verified.
NOTHING IS PLACED — the world is untouched by this whole session.**

Ryan ruled: *"add the shared flow prior and use conifer positions"*. Both
are built, proven, and used. **Two findings outrank the build itself, and
one of them says the mechanism is wrong.**

**`scripts/placement_priors.py` — the priors, defined ONCE.** Flow lived
inline in `place_foliage` (vegetation only); under-trees existed nowhere.
Both are physical facts, so non-negotiable 19 applies as it did to
`foliage.rock_scatter`. Rock species now take `flow_bias` and
`canopy_bias`, both bounded |1.0|, both REFUSING rather than
silently no-opping when the field is missing.
**The refactor is proven to have moved nothing: the shipped Conifer plan
replays BIT-IDENTICAL across 157,554 × 7.**

**THE CANOPY PRIOR ASKS THE TRUNKS, NOT A RASTER, AND A MEASUREMENT
FORCED THAT.** Grid 4.0 m; measured canopy radius **3.068 m**
(`fir_tree_01_c_LOD0`, `Free/_measured/fir_tree_01.json`). A canopy is
~1.6 cells across, so a raster at map resolution **cannot** express
"under this tree" — only "woods vs clearing". Candidates are continuous,
so a cKDTree matches each to its nearest trunk *and that trunk's scale*.

**FINDING 1 — the prior works, and its positive direction is weak.**
`TreeStump` planned four ways, same seed:

    canopy_bias 0.00 → 17.2% within one canopy radius, d_p50 5.67 m
                0.90 → 19.4%,                          d_p50 5.39 m
               −0.90 →  2.2%   ← the negative control

Both directions correct, so it is evidence not motion. But **+0.90 buys
13% where −0.90 removes 7.8×, and that is STRUCTURAL**: occupancy is a
*peaked* field, its mean sits near the bottom, and
`clip(1 + bias*(c−mean)*2, 0, 2)` saturates going up while having the
whole interval going down. **Not silently fixed** — the formula is shared
and correct for flow. Lever named in R12 §6a-i and BACKLOG.

**FINDING 2 — THE DENSITY IS A CEILING ARTEFACT AND NEEDS YOUR RULING.**
Planned: ClutterRock 14,785 (5.81/ha), DrainageStone 9,024, TreeStump
1,208 — **about fifteen small rocks in the entire 90 m cull disc, 41.5 m
apart.** That is occasional debris, not the ground Pass 5 asked for. And
no legal value fixes it: on the same ~2500 ha mask, 10 m spacing costs
**250,000 instances — the whole ceiling**; 5 m costs 4×; 3 m costs 11×.
Conifers already hold 157,554 of 250,000.
**The mechanism that does this is already in the recipe:** `Meadow` runs
`system: "grass"` at **120,000/ha**, via the landscape material's
GrassOutput, culled at 50 m, at **zero** instance cost.
**Recommendation, unratified: carpet density on the grass system,
instances only for sparse landmarks like TreeStump.** It needs a material
rebuild, and B-BUILD-UNKNOWN is still open on that builder.

**DEADFALL IS REFUSED AND STAYS OUT.** `vegetation_debris` pivot is
**0.419 m** off-centre against ruling (c)'s 0.258 m limit; under random
yaw it sweeps a 0.84 m circle while being 1.03 m wide. Fab content, so
the pivot cannot be fixed at source. Enabling work in BACKLOG:
`rock_pivots.json` keeps the pivot MAGNITUDE and discards the VECTOR, so
the offset cannot be cancelled at placement.

**ALSO SWEPT:** four duplicated constants → one declaration; a fail-open
that silently dropped unknown roles; a validator that **crashed** on
`canopy_bias: "lots"` (found by the probe, one line); a frame guard that
**could not see the defect it cited** (metres-as-cm lands at the map
CENTRE and passes an extent check — now two independent checks, 21/21);
and scipy, an undeclared dependency in 4 modules, now in R0.

**NEXT UNIT — PLACEMENT, AND IT IS ATTENDED.** Plans are written
(`foliage/alpine_{ClutterRock,DrainageStone,TreeStump}.json`);
`alpine_Boulder.json` re-planned **byte-identical**, so the 759 placed
boulders are untouched. `place_foliage --place` must be handed the
VEGETATION plans in the SAME run or the orphan sweep deletes conifers.
Needs a RISKY-OP CHECKPOINT tag. **Do not place before Finding 2 is
ruled** — placing 25,776 instances that are about to be superseded by a
grass-system approach is exactly the churn B-DENSITY warns about.

---

### HANDOFF 2026-08-08c (the clip sequence: Phase 0 + 1.5 + 1.2's input) — superseded by the above; still accurate.

**Tree clean at `e3c81945`. Editor PID 25720 alive, verified by
`bootstrap.py` as the sole node matching `UE_PROJECT_ROOT`, UE 5.8.0.
Nothing was placed; the world is untouched this session.**

Ryan ratified `plans/clip_30s_proposal.md` as the **sequence of record**
and ruled the order **1.5 → 1.2 → 1.1**, the reverse of the section
numbering. **Two items closed, one advanced to its input step, and the
thing that was blocking it swept.**

**RYAN'S TWO RULINGS, both now load-bearing:**
- **The 5080 desktop is NOT SOON, and the plan assumes it never
  arrives.** The iGPU is the permanent target, so the offline MRQ path is
  the deliverable rather than a fallback, and **1080p** is the render
  target. That answers Phase 0 item 3. **Items 1, 2 and 4 — what the clip
  is OF, eye-level vs crane, two reference stills — are STILL OPEN** and
  are needed by 3.6 (camera path), not by the content work.
- Order 1.5 → 1.2 → 1.1. The two **[RYAN]** systems (1.3 imposters, 2.5
  RVT) and 1.4's meadow intake remain escalation 1 and are **NOT**
  ratified.

**ITEM 1.5 — CLOSED BY RULING. NANITE STAYS OFF.** Settled in about one
grep, not by the render measurement the section had specified. Three
grounds, no shared source: (1) the benefit does not exist — largest rock
33,855 tris, the only placed rock **4,136**, and Nanite adds no
silhouette an asset never had; (2) **decisive** — `git check-ignore` says
**17 of 17 rock meshes are gitignored vendor content**, and RECIPES.md's
Fab-boundary rule names *"enabling Nanite on a Fab static mesh"* as its
**worked example** of a change that vanishes on re-download; (3) R12 §2c
already ruled *"Pass 3 does not enable it"* and the proposal reversed a
locked ruling without citing it. `check_fab_boundary.py` run this
session: 972 files, **0 changed**. **Consequence: 1.1 is no longer gated
on 1.5.**

**THE LEVER FOR LOD POPPING WAS NEVER NANITE** — it is `lod_depth`, the
LOD chain and `cull_distance_m`, all recipe data we own. R12 already
measured what makes popping likely: `boulder_medium_01`'s vendor LOD
screen sizes are **1.504 / 0.752 / 0.319 / 0.238** against an assumed
1.0 / 0.5 / 0.21 / 0.088. Re-homed to 1.1.

**ITEM 1.2 — INPUT STEP DONE, NOTHING PLACED.**
`measure_rock_meshes.py` was hard-coded to `pass != 3` and refused Pass 5
entirely; nothing in its payload is rock-specific, only the filter was.
Now takes `--pass`, with `admit` still strictly YES so the two
CONDITIONAL entries stay unmeasured. Proven before use: pass 3 selects
**exactly the 13 ids already in `rock_pivots.json`** (the regression
proof), pass 5 → 7, pass 99 → 0 refuses, HAZARD and CONDITIONAL leak
nowhere. Measured 13 → **16**:

    river_rock          pivot 0.012 m  base -0.066 m  2038/506/302/202
    tree_stump          pivot 0.046 m  base -0.127 m  5853/1878/860/562
    vegetation_debris   pivot 0.419 m  base -0.100 m  4538/1638/462/366

All three nanite False, 1 slot, lod_count 4.
**Two facts that must reach the species values:** `vegetation_debris` has
a **0.419 m HORIZONTAL pivot offset**, second worst in the palette, and
R12 §2c documents only the base-Z trap; and **`tree_stump` is 2.33 m
tall**, so it is not foot-level clutter. The genuinely foot-level assets
are `boulder_small` (0.89 × 0.90 × 0.43 m) and `river_rock`
(0.49 × 0.56 × 0.39 m).

**WHAT WAS BLOCKING 1.2, AND IT WAS WORTH THE DETOUR.** Four constants
that must agree were typed in two tools — `ROLES`/`_ROCK_ROLES`, the mask
kinds, and `MAX_INSTANCES` — **two lines below an import that already
demonstrated the correct pattern and cited non-negotiable 24 by name.**
The drift is asymmetric in the dangerous direction: add a role to the
VALIDATOR only and preflight passes while `rock_scatter` drops the
species, so **the plan reports success over a species it never planned.**
All swept to one declaration, **proven by object IDENTITY, not
equality.** A second defect fell out: `rock_scatter.py:911` used one
filter for two jobs and **silently discarded** a rock with an
unrecognised role — now refuses, exit 2. New `prove_gates` section,
**3/3**, whose positive control asserts execution reached the NEXT gate
rather than merely that the message was absent. Whole suite **0.7 s**,
exit 0, nothing regressed.

**THE NEXT UNIT, AND ITS ONE OPEN DECISION.** 1.2 now needs: a `clutter`
role (safe to add — one declaration), species values, a dry run, then
placement. **Placement mutates the world and needs a RISKY-OP CHECKPOINT
tag; the density-100 incident is the direct precedent.** Before authoring
values, one thing wants a ruling and is in BACKLOG: **the ruled density
philosophy names three gathering places and the machinery has priors for
two.** Deposit covers cliff bases, the layer weightmap covers forest
floor broadly, and **flow lives on the VEGETATION path** as
`place_foliage`'s `flow_bias` over `terrain/alpine_flow.png`. Giving a
rock mask flow must read the SAME loader (non-negotiable 19), not a
copy. **"Under trees" has no prior at all** — the Grass weightmap is
where forest *could* be, not where the 157,554 conifers *are*.

**ALSO FOUND, NOT FIXED:** `recipes/schema.md` **does not contain the
rock-species contract** — no `role`, `mask`, `embed_frac`,
`density_per_hectare_on_mask` — while `_validate_rock_species` cites
"Schema v1.20". R12 §2b is the de-facto spec of record. BACKLOG.

**THE THROUGH-LINE, AND IT IS THE SAME ONE THREE TIMES.** Every finding
this session came from **opening the artefact instead of trusting our own
prose** — and twice the stale prose was in a section whose heading tells
the reader not to check. CLAUDE.md item 4 said the talus threshold was
still owed; it landed **2026-08-03** in a commit whose subject says so,
and I had copied it into the proposal as the blocker on the largest
quality gap. R12's "Not yet placed" was found false by its own audit on
2026-08-06, recorded as *"corrected in their own files"*, and **never
was**. New rules written down: a stale line under a "do not re-derive"
heading is worse than one anywhere else; **step (a) applies to authoring
a plan exactly as it applies to running a script**; and **CLAUDE.md
governs METHOD and is not a source of truth about STATE.**

---

### HANDOFF 2026-08-08b (the VS/Copilot transcript) — superseded by the above; its open queue still stands.

**Tree clean. Editor PID 25720 alive, `/Game/Alpine` open cold from disk.
`VS stuido Work.txt` (4,505 lines) was read in full, mined, and moved to
`_trash/vs_transcript_20260808/`.** It was the primary record of the
session previously audited only from its outputs. Reading it changed four
conclusions and produced one deliverable.

**THE DELIVERABLE: the "attended before/after render" was already on
disk.** Three complete 19-frame sets spanning both material fixes were
sitting in `captures/alpine/`. Both comparisons are single-variable
(`git log <range> -- scripts/make_landscape_material.py recipes/alpine.json`
returns exactly one commit each), and cloud state was measured from the
frames' own sky pixels rather than read from prose. Against a
same-settings noise floor of mean mae **0.00298** (`044840Z` vs `054655Z`,
same commit, same cloud state, two runs):

    TRIPLANAR   fb9a1bc2 -> 75802995   mean mae 0.02480   8.3x noise
    _wz_axis    75802995 -> 236358db   mean mae 0.01274   4.3x noise

Each spatial pattern matches its own mechanism, which is what makes it
evidence: triplanar moves `rock_grounding` 32× and `diag_topdown` only
1.9× — and that weakest camera is the **discriminating control**, because
from directly overhead `|N.z| ≈ 1` collapses the triplanar blend to the
top-down projection by construction. `_wz_axis` shows the complement,
moving `verify_ground` 5.0× (84.95% of pixels) while leaving `cliff_face`
at 1.2× and `sweep_0060` below noise — altitude bands move views that span
altitude. Artefact: `_verify/20260808_before_after_material_fixes.txt`.
**R2's attended item is now ONE thing, the GPU cost, not two.**

**FOUR CORRECTIONS TO THE RECORD**

1. **The LESSONS.md truncation is root-caused at two lines, and it is
   standing rule 3's own mechanism.** `Add-Content` with a DOUBLE-QUOTED
   PowerShell string consumed backtick-r and backtick-t as CR and TAB;
   after six failed repairs, `$lines[0..33]` took the first 34 lines and
   wrote them back — 34 + 1 = 35, from 11,434. Rule 3 already routes
   commit messages through a file *because backticks expand*; it did not
   cover this because **it was scoped to an instance of the hazard rather
   than the hazard.** BACKLOG B-APPEND-GUARD updated with the cause.

2. **The single orphan was the defect.** After the triplanar fix,
   connectivity read 261/262 with one orphan at
   `MaterialExpressionComponentMask@-1950,200`, dismissed as *"a low-risk
   residual"*. Those coordinates are `_wz` at
   `make_landscape_material.py:1282` — the world-Z mask, orphaned by the
   shadowing bug. **In a graph that asserts EXACT the only acceptable
   orphan count is 0**, and the orphan's position was a grep from the
   line. R2 REJECTED.

3. **A build reported catastrophe on a graph that was complete.** The
   builder died on a truncated remote-exec response and printed *"is now
   EMPTY in memory and dirty … Do NOT 'Save All'"*; the audit seconds
   later read 262/262 CONNECTED. It cannot tell a mid-build death from a
   transport failure after a clean build. Second tool in this class after
   `save_level`, so **non-negotiable 4a applies** — BACKLOG
   B-BUILD-UNKNOWN.

4. **The transcript was WRONG about the clouds, and measuring caught it.**
   It states twice that the 18-frame `044840Z` set was captured with
   clouds active, then verifies "cloud-free" against those very frames. I
   was one edit from recording it as mislabelled. Sky-band luma per camera,
   against two `read_cloud_state` controls that separate on 12 of 18
   cameras, shows `044840Z` tracking the **OFF** control to four decimals
   on every camera. The cvars were typed during the `ridge_wide` shader
   stall, and `ridge_wide` is the one frame that timed out and never
   wrote. **A transcript is a derived record — non-negotiable 15.** The
   whole-frame statistic I reached for first pointed the wrong way, because
   terrain dilutes a sky-only change (non-negotiable 22).

**ONE THING NOT ACTED ON, AND IT IS YOURS TO DECIDE.** The repo has a
public GitHub remote — `https://github.com/ryan772177/LandscapeLab.git`,
added and pushed mid-session. `.git/refs/remotes/origin/main` is
**`cb41d7f7`**, the commit immediately *after* the truncation, so **the
published `LESSONS.md` is 35 lines and none of the repair is there.**
Pushing is outward-facing, so nothing was synced. Decide deliberately
whether this project should be public at all before syncing; then either
push `main`, make the GitHub repo private, or drop the remote.

**Density note:** this transcript contains **no** conifer-density change.
The 68.0 → 100.0/ha edit audited on 2026-08-08 came from somewhere else
(ZooCode, or an unrecorded session). It stays reverted, preserved on branch
`density-100-experiment-20260808`. Its origin is genuinely unknown, which
is a weaker position than "we know who did it" — recorded as such.

---

### HANDOFF 2026-08-08 (audit of the unattended work) — still live, read after the section above.

**COMPLETE. The revert landed in the repo AND in the world, and closing
the editor to do it also closed PASS 1's SAVED CLAUSE — see item 4.
Tree clean. Editor PID 25720 alive with `/Game/Alpine` open cold from
disk.**

Ryan asked for an audit of everything done since the 2026-08-07 handoff,
bad work reverted, good work kept. Six defects, all one shape — **a claim
that outran the artefact it described.** Two commits were good and stand.

## 1. WHAT WAS KEPT, BECAUSE IT IS CORRECT

- **`75802995`, the triplanar fix.** Consumes `(_val, _pin)` instead of
  the raw `(_det, "RGB")` at `make_landscape_material.py:1631` — exactly
  the diagnosed root cause of the 41 orphans. Reviewed, correct.
- **`236358db`, `_wz` → `_wz_axis`, and it is a BIGGER FIX THAN ITS
  MESSAGE SAYS.** `_wz` is bound at :1282 to world-position Z in
  centimetres and feeds the altitude bands at :1898 and the
  **forest_floor tint at :1987**. The triplanar block reassigned it at
  :1352 **at the same function scope** to `|N.z|^sharpness` — a 0-to-1
  weight off the vertex normal. Those bands were comparing a cosine
  against centimetres. The similar-looking unpack at :1602 was already
  safe (inside a `def`, so Python makes it local) and is unchanged.
  Now logged at both altitudes; it had no LESSONS or RECIPES entry.
- `scripts/compare_images.py`, the captures, the ridge_wide diff image.

## 2. LESSONS.md WAS TRUNCATED AND IS RESTORED

`538e2903`, message *"Appended LESSONS.md with a one-line entry"*, took
the file from **11,434 lines to 35** — `+4 / −11,400`, Divisions 1–6
destroyed. Restored from `599b828b` and **proven restored**: the
11,434-line original is an exact **PREFIX** of the 11,791-line result, so
the repair dropped nothing. The five genuine entries it did add are
preserved verbatim.

**Nothing enforces this file's append-only property.** BACKLOG
B-APPEND-GUARD. Until that exists, this can recur exactly as it occurred.

## 3. THE DENSITY CHANGE IS REVERTED IN THE REPO

One leaf of `recipes/alpine.json` moved **68.0 → 100.0/ha**, re-seeding
`foliage/alpine_Conifer.json` from **157,554 to 232,389 with every row
changed**, saved into the world across 1,327 packages. No tag (THE
RISKY-OP CHECKPOINT names "mass foliage regeneration" explicitly), no
grounding re-verify, no GPU reading at +47% instances on an iGPU already
at 75–94 ms. It silently invalidated every Pass 4 number on the board.

Recipe and plan are back at **68.0 / 157,554**. Nothing was discarded —
the full state is on branch **`density-100-experiment-20260808`**, whose
commit message records exactly what adopting it would require. BACKLOG
B-DENSITY.

## 4. THE WORLD REVERT LANDED — AND IT CLOSED PASS 1's SAVED CLAUSE

`git checkout` had been failing on all 1,327 packages with **`unable to
unlink old … Invalid argument`** — UnrealEditor PID 6008 held them open,
and **two bulk checkouts reported exit 0 while writing nothing.** *A
branch switch that reports success is not proof the working tree moved;
check the artefact.* Closing the editor released them:

    sampled package  48,645 B -> 34,293 B    (matches HEAD)
    M_AutoLandscape  128,486 B -> 129,174 B  (the 236358db build)
    modified world files                     0
    14 orphan packages from the 16:35 save   -> _trash/density_save_orphan_packages_20260808/

**And the free win landed with it. PASS 1's SAVED CLAUSE IS CLOSED.**
The editor came up on an empty `/Temp/Untitled_1`, so `open_level.py`
loading `/Game/Alpine` was a genuinely **cold load from disk in a fresh
process** — the thing that had never happened since the v2 push. Every
prior "the world is v2" measurement read the in-memory landscape or an
engine-authored side-record.

    check_collision_truth  n=500 seed 20260808  500/500  p90 0.182  max 0.827 m  PASS
    check_collision_truth  n=500 seed 7         500/500  p90 0.189  max 0.706 m  PASS

Inside the 0.159–0.233 band the in-memory runs produced. **The saved
world collides what `alpine_heightmap_v2.png` says it should**, measured
from disk by a process that never saw the push — collision and the save
record share no source, so non-negotiable 0 is satisfied.

`recover_state.py` on the reopened world reads **157,554 conifers /
1,044 components / 1,328 IFAs / 759 boulders** — the pre-density
population exactly, so the revert is in the world and not just the repo.

**STILL OPEN, a different clause:** per-component scope. These traces are
uniform, not stratified to put one inside each of the 256 proxy extents.
Broad staleness excluded; per-proxy completeness not established.

**NEW DEFECT, and it nearly cost a false alarm.** At the documented
default `--n 100`, seed 7 returned p90 **0.317** and printed *"THE
LANDSCAPE DOES NOT COLLIDE WHAT IT RENDERS"* on this correct world;
n=500 on the same seed gives 0.189. p90 from 100 samples is too coarse an
estimator against a 0.30 m bar when the true value is ~0.185.
**`--n 500` is the honest setting for a verdict; a bare n=100 result near
the bar is evidence in neither direction.** BACKLOG; logged at both
altitudes.

## 5. VERIFICATION.md REVERTED; FF16 PARKED

The report was rewritten from 155 measured lines into ~13 asserting Pass
3 talus "placed and measured" (**not placed**), Pass 5 "generated and
verified" (**audited CONFIRMED not built**), clouds "confirmed inert/off"
(**measured ACTIVE**), Pass 2 "262 expressions reachable" (**221 of 262,
41 orphaned**), Pass 0 "verified" (**zero instances**) — and deleted
`WHAT IS NOT VERIFIED`. It was written from
`plans/alpine_execution_plan.md`, so **every false row is a planned step
reported as a completed one.** Reverted.

FF16 plans + notebook → `_trash/ff16_plans_20260808/` (scope change,
Ryan's call). Recorded as BACKLOG B-FF16. Two parts of that direction
need no new ratification: ground clutter **is** Pass 5, and conifer
density **is** B-DENSITY.

## 6. NOT VERIFIED — standing rule 10

- **`236358db`'s "graph connectivity passed" has NO artefact for the
  current bytes.** Newest audits are dated 20260806; the material was
  rebuilt 20260808 15:59. **Whether the triplanar fix reached the built
  graph is UNMEASURED** — not failing, and explicitly not a pass. This is
  the SECOND time this exact claim outran its artefact on this material.
  BACKLOG B-VERIFY-HASH.
- ~~`M_AutoLandscape` has had no audit since the fixes landed.~~
  **CLOSED 2026-08-08 ON THE CURRENT BYTES.** `audit_material_
  connectivity`: **262 expressions, 262 reachable, 0 ORPHANED** (was
  221/262 with 41 orphans), 262 accessor calls / 0 errors, VERDICT
  CONNECTED. `audit_material_samplers`: 31 audited, 0 mismatches. The
  discriminating detail: `T_Rock026_C` and `T_Rock051_C` now report
  **4 connected samples each** — top-down + two side projections + macro
  — while Snow/Ground/WildGrass report 2 (no triplanar), which is exactly
  what `material.triplanar.layers = ["Rock"]` predicts. **Triplanar is
  wired, measured rather than reviewed.** Artefacts:
  `_verify/20260808_connectivity_M_AutoLandscape.txt` and
  `_verify/20260808_sampler_audit.txt`, both **stamped with the
  material's SHA-256** `3d38821e…` (129,174 B) — which independently
  equals the git-LFS pointer oid at `236358db`. First artefacts in the
  project to name the bytes they read.
  ~~**STILL ATTENDED, and not implied by the above:** the cliff LOOK and
  the GPU cost are both unmeasured.~~ **HALF-CLOSED 2026-08-08 — THE
  RENDER WAS MEASURED, THE COST WAS NOT.** The look never needed a human;
  three complete 19-frame sets spanning both fixes were already in
  `captures/alpine/`. Against a same-settings noise floor (mean mae
  0.00298): **triplanar 0.02480 = 8.3×**, **`_wz_axis` 0.01274 = 4.3×**,
  both single-variable by `git log <range> --` on the builder and recipe,
  both with cloud state measured from the frames' own sky pixels. The
  result is evidence and not just a number because the spatial pattern
  matches each mechanism — triplanar moves `rock_grounding` 32× and
  `diag_topdown` only 1.9×, and that weak camera is the DISCRIMINATING
  CONTROL, since from overhead `|N.z| ≈ 1` collapses the blend to
  top-down by construction. Artefact:
  `_verify/20260808_before_after_material_fixes.txt`.
  **STILL OPEN, and it is now ONE item:** the **GPU cost** of rock albedo
  going 1 sample → 3 on an iGPU already at 75–94 ms. Attended viewport
  reading. Whether the cliffs look *better* is Ryan's judgement, not a
  statistic's.
- ~~`recipes/alpine_ridge_rerun.json` duplicates `alpine.json`.~~
  **RESOLVED 2026-08-08 →`_trash/superseded_recipes_20260808/`.** It
  declared its own copy of the landscape transform, heightmap source and
  parent material beside its one camera, so `alpine.json` could move and
  the rerun would go on capturing against stale geometry silently —
  non-negotiable 19. Unreferenced by any script, so it was a live trap
  rather than a working tool. To restore the capability, add `ridge_wide`
  as a **camera** under `alpine.json`'s `capture.cameras`. Its existing
  frames are untouched and still cited in LESSONS. BACKLOG.
- `commits/` is now **gitignored**: a commit message IS the commit once it
  lands, so a copy on disk is a derived record that can only drift
  (non-negotiable 24). The directory stays for rule 3's `-F` workflow.
- `.claude/hooks/_state/prove.json` **untracked** — the stray the
  2026-08-07 handoff flagged. The path was already in `.gitignore`; the
  file predated it and was committed by a `git add -A`.
- Everything the 2026-08-07 handoff listed as open is still open:
  Pass 1's SAVED clause, Pass 0 verification, Pass 5 clutter, Pass 3
  cliff/talus, 13 UNPROVEN recipes, REPLAY BATCH 1.

## 7. THE THROUGH-LINE

Not one of the six defects was caught by a gate. All six were caught by
**opening the artefact** — the diffstat, the scope boundaries, the
`_verify/` listing, the semantic JSON diff, the audit table, the two
files side by side. The audit's own near-miss is logged too: comparing
`git show HEAD:<path>` against a working file reported *100% of bytes
differing*, because `git show` returns the **LFS pointer**. An absurd
magnitude is a question about the instrument.

The cheapest instrument in this project remains `git show --stat`.

---

### HANDOFF 2026-08-06 (unattended night session) — SUPERSEDED BY THE ABOVE, but its open queue still stands.

**Tree clean. Nothing mid-flight. No agent running. Editor PID 13432 was
alive and used read-only throughout; nothing was saved or mutated.**

Ryan went to sleep mid-session and asked for everything reachable
without him. Everything below is unattended-safe work: **five new or
repaired instruments, four findings, ZERO writes to the world.** The two
ruled-attended items (meadow execution, the clean-baseline GPU
re-measure) were deliberately NOT touched.

## 1. THE HEADLINE — TRIPLANAR HAS NEVER RUN

`scripts/audit_material_connectivity.py` (new) walks backwards from every
material output. **M_AutoLandscape: 262 expressions, 221 reachable, 41
ORPHANED**, and the orphans are the entire triplanar apparatus plus the
X and Y side-projection albedo samples for both rock surfaces.

**Root cause is one line — `make_landscape_material.py:1631.** The
macro-variation block wires `_det` (the plain top-down sample) into its
sum instead of `_val` (the triplanar result assigned immediately above),
so a surface with BOTH features builds the triplanar chain and discards
it. `material.triplanar.layers` is `["Rock"]`, and Rock carries macro
variation — **triplanar is inert on 100% of the surfaces it exists for.**

Five instruments were green over it: the sampler audit (an orphaned
TextureSample is well-formed), the compiler (dead nodes are legal),
`_assert_triplanar_invariants` (asserts the MATHS, never the WIRING),
and the renders (top-down rock looks like rock until a wall is steep).

**NOT FIXED, and do not fix it unattended.** Wiring it in takes rock
albedo from one sample to three on an iGPU already at 75-94 ms, and
changes the look of every cliff. Attended, with a before/after render
and a GPU reading. Full detail: R2's OPEN DEFECT block.

**Consequence for Pass 7 gate item 1:** the cliffs have been rendering
top-down projected all along, so close-range stretching is now the
EXPECTED result, and "no defect found on the lit 0700 wall" was graded
against a feature that was never running.

## 2. THE CLOUDS WERE ON — item 1 of the last handoff is ANSWERED

`scripts/read_cloud_state.py` (new, read-only): **ACTIVE.** Actor
unhidden on all three flags, component `is_visible` True with
`m_SimpleVolumetricCloud_Inst` bound, `r.VolumetricCloud 1`. The
component's `is_active` reads False and is NOT the switch —
`VolumetricCloudComponent.cpp:94` gates the proxy on
`ShouldComponentAddToScene() && ShouldRender() && IsRegistered()`.

**Confirmed by a different representation:**
`_verify/20260806_v2sweep_ridge_wide.png` — one of our own published
frames — has a full cloud deck across the sky.

So **94.45 / 75.71 ms is a clouds-ON measurement.** Clouds-on cost is
already inside those numbers, interactive headroom is BETTER than R13
believes, and the "OFF interactive" row describes a state the world was
never in. The clean-baseline re-measure is ATTENDED and is still owed.
Premise-break block is at the head of R13 ADDENDUM.

## 3. TWO GATE GAPS MEASURED (queue item 1, was stalled on credits)

`measure_falloff_contours.py` was committed 677 lines and never run.
First selftest: the only POSITIVE CONTROL failed — it could not detect
the defect it exists to find, because it scored each annulus against the
map-wide median for its slope band **and the annulus is 85% of that
band**. Self-masking, worse as the defect grows. Fixed (reference =
cells outside every annulus), selftest now 11/11 with a pinned
regression.

- **The two polished falloff spots are REAL and LOCATED:** `(1459, 26) m`
  in the `spine_aretes` annulus at 19 deg, `(-512, 2330) m` in
  `drainage_south` at 16 deg, 0.082 km2 each, relief at 30% / 31% of
  reference. Distribution `2 of size 5, 2 of size 2, 9 of size 1` — they
  separate by a clear gap. They miss the spot bar by ONE window and the
  bar was **not** re-tuned to admit them.
- **`spine_aretes` CV does NOT reproduce, and the bar is unenforceable.**
  Measured 0.033-0.152 over NINE placements vs a recorded 0.089-0.367
  over EIGHT — every one lower by roughly the same factor. **NO GATE
  ANYWHERE ENFORCES THE BAR** (it lives in `schema.md:824` and prose, in
  zero scripts) and its derivation is not in the repo. **DO NOT act on
  the two below-bar rows** (`spine_aretes` 0.047, `cliff_band_west`
  0.033) — re-deriving the bar against this now-written-down procedure
  comes first. Acting naively would re-composite the terrain and
  invalidate 157,554 conifer and 759 boulder placements.

Gap 3 (a lit close-range cliff face) is untouched — it needs a render.

## 4. PASS 2 SAMPLERS CLOSED; PASS 3 + 4 CAVEAT CLOSED

- **Sampler audit 43/43 re-run on the CURRENT bytes**, all four
  materials, dated artefact `_verify/20260806_sampler_audit.txt`. The
  CLEAN half is closed too — the scratch node asks the ENGINE via
  `AutoSetSampleType`. `audit_material_samplers.py` now asserts its own
  cleanup (262 -> 262, 0 scratch left) and refuses if it left debris.
- **Engine instance TRANSFORMS read for the first time**
  (`read_instance_transforms.py`): conifer 157,554 and boulder 759 both
  match the plan at **0.000 cm** XY and Z (n=400 / n=300), nearest-
  neighbour matched. The zero is EARNED — `--perturb-cm 250` reports
  353.553 / 250.000 and exits 3. Also delivers the current post-repair
  engine boulder count the audit said did not exist.
- **`M_grass_medium_01` has 8 ORPHANED nodes** — stacked duplicates from
  repeated builds, same class as R3's seven wired survivors. Low
  severity; sweep when that material is next rebuilt.

## 4b. PASS 0 ADVANCED, AND TWO OLD UNKNOWNS ANSWERED (2026-08-07)

- **Nanite is DISABLED on 38 of 38 palette meshes**, read from the
  loaded mesh's `nanite_settings.enabled`
  (`scripts/measure_palette_live.py`, new). That retires the standing
  "Nanite is UNKNOWN on all 38 — absent is not OFF" item. The guess
  would have been right; holding it UNKNOWN was still correct, because
  the same absent tag is produced by a Nanite-ENABLED mesh whose tag was
  never written.
- **`measured.material_slots` disagrees on 23 of 38** (audit had 8 of
  13). Still DO-NOT-CONSUME. **`triangles` agrees on 38 of 38** — the
  positive control, and it draws the boundary: ONE field of the registry
  scan is bad, not the scan. Measurements at
  `Free/_measured/palette_live.json`; the v1.13 judgement/measurement
  split is preserved and no recipe was edited.
- Pass 0's VERIFICATION half is still untouched — this measures the
  ASSET and never spawns or renders, so nothing became `verified`.

- **`t.MaxFPS` ROOT-CAUSED** (open since 2026-08-03, fix NOT applied).
  Our ini is right and in the right section; it applies and is then
  overwritten. `Saved/Config/WindowsEditor/GameUserSettings.ini:19` has
  `FrameRateLimit=0.000000`; `GameUserSettings.cpp:413` calls
  `SetMaxFPS(0)`; and `UnrealEngine.cpp:12247` **re-uses the previous
  set-reason**, so it writes at the same priority the ini used and the
  later write wins. Priority cannot protect a value whose setter borrows
  the incumbent's priority. Candidate fix and the open question (`Saved/`
  is generated) are in BACKLOG; **verifying needs an editor restart.**

- **The CV bar's old statistic is NOT RECOVERABLE** — four candidate
  definitions computed over the same nine placements, none reproduces
  0.089-0.367 (`_verify/20260807_cv_bar_recovery.py` + output). Mine has
  the right shape but sits ~2.5x low. **Stop trying to reproduce 0.089;
  re-derive the bar against the written procedure.**

## 5. WHAT I DID NOT DO — read this before assuming coverage

- **The triplanar fix.** Attended. See item 1.
- **The clean-baseline GPU re-measure.** Attended, viewport overlay.
- **Meadow execution.** Ruled attended, still waiting on Ryan.
- **Pass 1's SAVED clause.** Still open — needs one editor RESTART plus
  `check_collision_truth.py`. I did not restart the editor: it has run
  continuously since 2026-08-05 17:15, a cold reopen is the only way to
  prove the save persisted, and doing it unattended risked losing the
  live editor with 2.7 GB free RAM. **This is the cheapest big win left.**
- **Pass 0 palette verification**, Pass 5 clutter, Pass 3 cliff/talus.
- 13 recipes remain UNPROVEN; REPLAY BATCH 1 never run.
- A stray `.claude/hooks/_state/*.json` got committed by `git add -A`;
  untrack and gitignore it when convenient.

## 6. NEW INSTRUMENTS, all read-only, all usable by any later pass

    read_cloud_state.py            actor + component + cvar, 3 outcomes
                                   ruled in advance, UNREAD never INERT
    audit_material_connectivity.py reachability; custom outputs seeded;
                                   identity is the object path, asserted
                                   unique; positive-controlled so "the
                                   accessor saw nothing" can never print
                                   as "everything is orphaned"
    read_instance_transforms.py    engine transforms vs plan, seeded and
                                   declared sample, --perturb-cm control
    measure_falloff_contours.py    REPAIRED and now proven, 11/11
    audit_material_samplers.py     now asserts its own cleanup
    measure_palette_live.py        loaded-mesh palette measurement; one
                                   mesh per call, RAM floor, partial
                                   runs DECLARED; unreadable RAM stops
                                   with its own distinct reason

**The through-line of this session: every one of the four findings came
from asking a DIFFERENT PROPERTY of the artefact than the one already
being asked** — reachability instead of presence, a rendered frame
instead of a property read, the engine's transform instead of the plan's,
a reference population that excludes the ground under test. Non-negotiable
0 is doing real work now rather than being quoted.

---

### HANDOFF 2026-08-06 (end of session) — SUPERSEDED BY THE ABOVE. Item 1 (the clouds) is ANSWERED; the rest of its queue still stands.

**Tree clean at `cdf640c5`. Nothing is mid-flight. No agent is running.**

## 1. DO THIS FIRST — the GPU numbers may be invalid

The pass audit found an **UNDECLARED `VolumetricCloud` ACTOR IN THE
LEVEL**, and the GPU measurement (sweep_2000 94.45 ms / sweep_0060
75.71 ms) was taken **with it present**. If that actor is active, the
"clouds off" baseline was never a clouds-off baseline — and the clouds
ruling (R13 ADDENDUM) rests on those numbers.

Three outcomes, all actionable:
  - actor ACTIVE -> clouds are already in the 75-95 ms, interactive
    headroom is better than believed, and the ruling should be re-taken
    on a clean baseline;
  - actor INERT -> bookkeeping defect only, ruling stands, declare the
    actor;
  - could not read -> say so; do not assume inert.

Cheap: read the actor's enabled state, then re-measure with it
explicitly off. **Do this before any Pass 6 atmosphere work**, because
that work is unblocked *on the strength of those numbers*.

## 2. WHAT THE AUDIT SAID (commit `38323e94`, table at "PASS AUDIT" below)

8 passes, each checked against a representation that did NOT record it;
CONFIRMED verdicts sent to an adversarial skeptic.
**3 CONFIRMED (1, 3, 5) · 5 OPTIMISTIC (0, 2, 4, 6, 7) · 0 FALSE · 1
CONFIRMED overturned on refutation (Pass 2).**

**The Pass 1 failure changed SHAPE rather than disappearing.** Nothing on
the board is fabricated. The defect is now that TRUE NUMBERS ARE QUOTED
WITHOUT THE CLASS OF INSTRUMENT THAT PRODUCED THEM. Worked example:
`verify_grounding`'s own docstring says it *"would report zero gap on a
map where every tree hovers"*, and its "max 0.001 m" is the board's proof
that a Pass 4 gate is closed. Engine collision says +0.392 m on the same
placement. Both correct; only one is evidence.

## 3. FIXED THIS SESSION, ALL PROVEN

- `trace_grounding` epsilon **0.05 -> 0.45 m**, DERIVED from measured
  collision quantization (p90 0.091 / max 0.431, signed mean -0.007 =
  symmetric = quantization, not floating). It was printing FLOATING
  CONFIRMED / exit 5 **on correct data**. Now 0 of 300, exit 0.
- `trace_grounding` **REFUSES** (exit 2) a plan whose grounding
  convention it does not model. It had been applying the conifer
  convention to the boulder plan (which grounds via
  `pivot_base_offset_m` / `embed_depth_per_scale_m`) and reporting ~100%
  floating over placement correct to +0.000 m median.
- `PROJECT_STATE.json` regenerated. It carried the R13-REJECTED sun
  18000.0. **The world was checked first: the live sun IS 130000.0**, so
  R13 is applied and the FILE was stale. Trap: `recover_state` only
  writes with `--out`, so a bare run exits 0 and leaves the stale file.

## 4. THE QUEUE (ruled order, item 1 partially done)

1. **GATE-GAP INSTRUMENTS** — unattended OK. STALLED ON FABLE CREDITS,
   not on difficulty. `scripts/measure_falloff_contours.py` is committed
   **incomplete and unproven** (677 lines, parses, never run against a
   known-bad case — by this project's standard it is NOT coverage).
   Partial finding already bought: aggregate annulus stats show NO GLOBAL
   POLISH, so the two falloff spots are **LOCAL**, likely on moderate
   slopes below the detail-relief band (30-90 deg); next step was a
   window-level prototype, not aggregate stats. The other two gaps (lit
   close-range cliff, `spine_aretes` CV) were never reached.
2. **MEADOW EXECUTION** — RATIFIED, attended, waiting on Ryan.
   Acceptance tolerances declared before the run; **patches are the
   aerial-readability payload, not the percentage** (58 patches >=1 ha
   predicted; band-widening was rejected precisely because it delivers
   slivers).
3. **PASS-AUDIT** — DONE this session. Also outstanding from it: Pass 2's
   "43/43 samplers" carries **31 from the WRONG-TERRAIN sweep** and must
   be re-run; the graph is proven PRESENT, never CONNECTED; Pass 7's gate
   has **four** open items, not three.
4. **CONTENT, only after 3** — Pass 5 clutter, Pass 3 cliff/talus.

**STANDING: nothing in 1-2 mutates pass statuses; the audit owns that.**

## 5. NOT DONE / NOT VERIFIED (standing rule 10)

- The three gate gaps remain OPEN. No instrument exists for two of them.
- Fog and aerial perspective: applied and rendering, **never tuned**.
- Clouds: ruled OFF interactive / PERMITTED offline — **but see item 1**.
- 13 recipes remain UNPROVEN; REPLAY BATCH 1 never run.
- Editor PID may be stale by next session; relaunch and use
  `scripts/open_level.py`, never a hand-rolled load.

Update this section at the end of each session. It is the only
session-transient thing in this file.

- **Terrain**: **v2 IS NOW LIVE — pushed, flushed, gated and saved
  2026-08-06** (the FIRST v2 push there ever was; the 2026-08-03
  "adoption" was file-side only and never touched the world — see
  RECIPES → WHY THE PUSH DID NOT PERSIST). Proven by measurement, not
  narrative: export read-back matches `alpine_heightmap_v2.png` under
  identity at delta 0.0 on 161/161 texels (v1 now misses by median
  1135); `check_collision_truth` PASSES for the first time ever — p50
  0.026 / p90 0.209 / max 0.716 m vs v2, reproduced on three seeds
  (p90 0.159–0.233); save wrote 263 allow-listed packages, all clean
  and verified on disk. Collision flush ran in-session; the same-seed
  before/after check was identical, showing the live editor had
  already drained the deferred region. R-STAMP's ADOPTION section now
  carries push + same-session flush + both exit gates as MANDATORY
  steps. Restore tag: `pre-v2-repush-20260806` (repo side).
- **Material**: real photogrammetry surfaces (Snow006 / Rock051 /
  Ground037) with normals and roughness; `base_color` is a tint.
- **Foliage**: 157,554 conifers at 24.2/ha, upright and grounded —
  **grounding proven on the corrected world 2026-08-06 by TWO
  instruments**: heightmap (max 0.001 m, all instances) and engine
  line trace (n=500, gap p90 +0.068 / max +0.392 m, equal to
  collision's own quantization vs the heightmap at the same points).
  *(Count re-measured 2026-08-04 by `recover_state.py`. The long-quoted
  160,448 was correct against the PRE-adoption surface; placement
  re-ran and the acceptance mask moved. R5 carries the correction.)*
- **Rock**: 759 hero boulders placed and saved, R12 — `Medium_Boulder_
  001` at 0.35/ha on the meadow mask, embed 0.18–0.40 m, cull 140 m.
  Grounding proven by a render aimed at a known cluster,
  `_verify/20260804_r12_boulder_grounding.png`. Cliff and talus MESH
  roles are specified in R12 and **not placed** — only the material's
  scree texture represents them today.
  LOD chain re-solved 2026-08-03 on `percent = screen_size²`:
  505,494 / 126,374 / 22,293 / 3,892, **cull 730 m at 39.6M tris**.
  Grass at 12 tufts/m2, cull 50 m. Both verified by render at ground
  level; `_verify/` holds the dated frames.
- **Config**: low-spec profile applied and verified headless, **except
  `t.MaxFPS`, which does not take effect** — the live editor reports 0.0
  (unlimited). Backlog item; the GPU has already hung once.
- **Governance**: every recipe now conforms to the template in
  `RECIPES.md` and is tagged **UNPROVEN** — none has been replayed cold.
  `PROJECT_STATE.json` holds machine-recovered values; 7 scene fields
  are marked VALUE UNVERIFIED because 5.8 refused to read them.

## Open defects

- **Conifer trunks were rendering the TWIG atlas — FIXED 2026-08-03.**
  `M_fir_bark` was built without `--slot`, and `texture_map` silently
  last-wins on a contested role, so it sampled twig textures and never
  a bark one. A second defect hid the fix: `delete_all_material_
  expressions` left 7 wired survivors. Both locked in R3 REJECTED.
  Trunks now render bark — `_verify/20260803-0222_alpine_forest-floor-
  backlit.png`.
- **No trustworthy vegetation-coverage metric.** Three were wrong in one
  session. The previously reported "0.00% vegetation at 2 km" was a
  broken measurement, not a finding — it returns 0.00% for a ground
  frame that visibly contains grass and trees.
- **The aerial verification camera cannot verify vegetation** — it is
  aimed at a rock-and-snow peak with half the frame in shadow.

## Active frontier

Aerial readability beyond 730 m now rests entirely on the landscape
material's `forest_floor` tint (schema v1.11), which is confirmed in the
graph and visible at ground level. Real instances beyond 730 m need
imposters — backlog, not started.

## CAMPAIGN: COMPLETE THE ALPINE REGION — status 2026-08-04

Multi-session. Passes 0–7. Each pass ends with a verification gate and a
commit. **The level HAS been written: Pass 1 adopted new terrain and saved
1328 packages on 2026-08-03.** Restore point is tag `pre-stamp-adoption`.

### PASS AUDIT 2026-08-06 — the board, checked against itself

**Why it ran:** Pass 1 sat recorded as "DONE. Terrain pushed and verified"
for three days while the live world was a different heightmap. Every gate
was green because every gate read the same file. **Every row below was
therefore re-checked against a representation that did NOT record it**
(non-negotiable 0). CONFIRMED verdicts were then sent to an adversarial
skeptic; one was overturned.

**Result: 3 of 8 CONFIRMED, 5 of 8 OPTIMISTIC, 0 FALSE.** No row was a
fabrication; five overstate what their evidence carries.

| Pass | Recorded | Verdict | Cross-check used (did NOT record the status) |
|---|---|---|---|
| 0 | DONE. 38 palette entries | **OPTIMISTIC** | Filesystem `.uasset` resolution; `Free/_measured/rock_pivots.json` (LOADED meshes, vs the palette's unloaded registry-TAG scan); RAW `.uasset` name-table bytes; the 1,683 saved World Partition packages. Zero editor queries. |
| 1 | DONE 2026-08-06, v2 pushed/flushed/gated/saved | **CONFIRMED** | Live landscape COLLISION traces on a fresh seed (p90 0.172 m vs v2; v1 is 242.7 m away at p90); the ENGINE'S OWN LOG (`LogLandscapeBP`/`LogInterchangeEngine`/`LogTexture`); package mtimes + git tree. |
| 2 | BUILT; sweep run on corrected world | **OPTIMISTIC** (skeptic overturned a CONFIRMED) | Engine-written external-actor package binaries (257 ref M_AutoLandscape, 0 overlap with 64 stale M_ProcGrid); the material package BYTES + its prior git-LFS object; 19 PNGs measured with independent numpy code; one live read (256 proxies + 1 landscape, all M_AutoLandscape). |
| 3 | DONE for `hero` role only; 759 boulders | **CONFIRMED** | The saved world's 504 packages and their 493 grid-cell IDs (set difference 0 against the plan's predicted cells); engine line traces taken today (80/80 hits, median residual +0.000 m); `_verify/20260806_v2sweep_rock_grounding.png`. `verify_grounding.py` DELIBERATELY EXCLUDED — it reads the planner's own heightmap. |
| 4 | 3 of 3 exit gates closed | **OPTIMISTIC** | Live `get_instance_count()` over every foliage component (157,554 / 1,044 — cannot see the plan); the RAW 500-row engine-trace dump re-reduced from scratch; rendered trunk-base pixels. |
| 5 | Not started | **CONFIRMED** | Positive-controlled string search of all 1,683 saved actor packages: 0 for every Pass-5 clutter identity, 504/1044/256 for the three known-placed controls. Zero editor queries. |
| 6 | DONE for sun and exposure; GPU measured; clouds ruled | **OPTIMISTIC** | Live `DirectionalLightComponent` properties; the editor's own `LogPython __LANDSCAPELAB_EXPOSURE__` line; PNG pixels decoded by independent code (linear luma 0.3169 vs solved 0.3201). |
| 7 | Sweep re-established; gate open on 3 gaps | **OPTIMISTIC** | 19 PNGs measured two ways; the raw `trace500.json` re-reduced independently; git ancestry (`959ec140` is an ancestor of `fb9a1bc2`); filesystem proof that two named instruments do not exist. |

**Sub-claims that came back UNVERIFIABLE — "I could not look", which is
NOT a pass** (non-negotiable 6). These are the holes, stated in the
table so they cannot read as green:

- **Pass 2, the CLEAN half of "sampler audit 43/43".** Only the
  DENOMINATOR (31 samplers on M_AutoLandscape) was independently
  confirmed. Reading whether each declared `sampler_type` is correct
  needs either a scratch node in a shared live material (barred: this
  audit was read-only) or the engine's rule at
  `Engine/Source/Runtime/Engine/Private/Materials/MaterialExpressions.cpp`
  `VerifySamplerType` :2760-2767. The first auditor reported engine
  source as ABSENT FROM THIS MACHINE; **that was wrong — it is
  installed** and the skeptic opened it. The gap is closable offline and
  nobody has closed it.
- **Pass 6, "clouds NOT enabled".** A `VolumetricCloud` actor IS in
  /Game/Alpine (count 1, present since at least 2026-08-04). No recipe
  declares it, no script disables it, and `apply_lighting`'s
  foreign-actor census does not cover the class. Its visibility was
  NOT READ. The board asserts a negative about the world that no
  instrument in this pipeline can enforce.
- **Pass 6, `camera_aperture_f_stop`.** Read raised an exception, so one
  of the four manual-exposure terms behind EV100 9.9069 is unconfirmed
  at the object level.
- **Pass 6, GPU cost 94.45 / 75.71 ms.** An attended viewport reading
  with NO artefact on disk — unverifiable by construction, correctly
  labelled editor-class in R13, but a reader cannot tell "measured"
  means "read off an overlay".
- **Pass 1, the SAVED clause.** The editor process has run continuously
  across the push, the flush and the save; `/Game/Alpine` has never been
  reopened from disk. Every "the world is v2" measurement — all five
  seeds — reads the IN-MEMORY landscape. Saved is corroborated by
  engine-authored side-records (263-package save marker, ~2,048
  `LogTexture` heightmap rebuilds, 262 files stamped on disk), **never
  measured by decoding a saved `.uasset`.** One editor restart plus one
  `check_collision_truth.py` closes it.
- **Pass 1, per-component scope.** ~600 uniform traces over 256 proxies
  is ~2.3 per proxy; a single stale component would be missed with
  probability ~10%. Broad staleness is excluded by >1,000x; per-proxy
  completeness is not established. A stratified variant (≥1 trace inside
  every proxy extent) would close it.
- **Pass 3/4, instance TRANSFORMS.** Both grounding instruments take
  instance Z from the PLAN and differ only in ground source. Nothing yet
  reads the engine's actual instance transforms; "instances are where
  the plan says they are" rests on pixels alone.

**Adjacent records the audit found WRONG and which are corrected in
their own files, not here:** `RECIPES.md` R12 "Not yet placed" (false —
step 5 ran 2026-08-04 and the saved world proves it);
`PROJECT_STATE.json` (STALE — still records sun intensity 18000.0, the
value R13 REJECTED, and `foliage_types` missing FT_Boulder; re-run
`scripts/recover_state.py`); `scripts/trace_grounding.py:193,316` (pivot
premise is the CONIFER plan's — reports "FLOATING CONFIRMED 80 of 80" on
a boulder placement correct to 0.000 m median); CLAUDE.md's own "PASS 5
HAS NO WRITTEN SCOPE" (false — scoped 2026-08-05 at `RECIPES.md:3030`
and `BACKLOG.md:587`); and CURRENT STATE's "v1 now misses by median
1135", which has no denominator — that is the 161-texel probe row;
whole-map it is median 38 u (1.484 m), and "38.51% within 4u" is 32.12%
over the full 2017².

| Pass | What | Status |
|---|---|---|
| 0 | Verification + alpine palette | **PALETTE AUTHORED; VERIFICATION NOT STARTED** *(audited 2026-08-06 — OPTIMISTIC; was "DONE")*. 38 entries in `recipes/alpine.json` → `palette`, all `verified: false` — the pass is named "Verification + palette" and the verification half has **zero** instances. Independently confirmed: 38/38 paths resolve to real `.uasset` files; `triangles` and `dims_m` match a LOADED-mesh instrument exactly on the 13 it covers. **KNOWN-BAD in the record:** `measured.material_slots` is contradicted by two independent representations on 8 of those 13 (palette 4/3/2/2/4/5/12/4 vs actual 1 — the vendor packages serialize a stale tag; `StaticMesh.cpp:6319` defines it as `GetStaticMaterials().Num()`) — **do not consume that field**. `measured.nanite` "UNKNOWN" is stale: measured **false** for 13, genuinely unknown for 25. `verified_reason: "not spawned and not rendered"` is FALSE for `boulder_medium_01` — spawned 759x in the saved world and rendered. 25 of 38 entries have never been loaded, spawned or rendered. |
| 1 | Terrain completion (R-STAMP) | **DONE 2026-08-06 — the 2026-08-03 "adoption" was file-side only and never touched the world** (measured 2026-08-05, repaired 959ec140: v2 pushed, flushed, gated, saved). Weights, aux maps and the 157,554-conifer plan were always derived from v2 and now match the live world; grounding re-proven by engine trace 2026-08-06. *(Audited 2026-08-06 — **CONFIRMED** vs live landscape COLLISION on a fresh seed, the engine's own log, and package mtimes + git tree. The engine logs exactly ONE heightmap-import-from-render-target, at 05:57:11, ten seconds after an Interchange import of `alpine_heightmap_v2.png`, and none since. RESIDUAL: the SAVED clause is corroborated by side-records, never measured from disk — the editor has not reopened the level since the push; and ~600 traces over 256 proxies do not guarantee per-proxy coverage.)* |
| 2 | Landscape material upgrade | **BUILT AND LIVE; SWEEP RUN 2026-08-06 on the corrected world (tag `v2sweep`)** *(audited 2026-08-06 — OPTIMISTIC; a first CONFIRMED was OVERTURNED by the skeptic)*. **Material identity is PROVEN, and it was the audit's main worry:** 257 external-actor packages reference `/Game/Materials/M_AutoLandscape`, 64 reference `M_ProcGrid`, the sets are DISJOINT, the 64 are stale OpenWorldTemplate exports from 2026-08-02, and a live read shows 1 Landscape + 256 proxies ALL on M_AutoLandscape. 22 textures (incl. T_Rock026_*, T_Alpine_Variants, T_Alpine_Macro, four `_D`) are in the package BYTES; 31 TextureSample nodes live. Every render statistic in SWEEP_REPORT reproduces under independent code. `_assert_cpu_model_invariants()` really is called at module level (`make_landscape_material.py:1026`). **WHERE THE RECORD OVERSTATES:** (i) "Sampler audit PASS 43/43" sits inside the v2sweep run of record but was **not produced by that run** — 31 of the 43 were measured 2026-08-05 17:41 against the PREVIOUS wrong-terrain sweep (`4bc5e99e`), there is **no dated sampler-audit artefact anywhere in `_verify/`**, and §7's carry-forward ledger lists criterion 4 in neither SURVIVES nor SUPERSEDED. The material bytes changed afterwards (129161→129049 B, differing at 26.7% of bytes); string-list equality does **not** decide whether a per-node sampler was reassigned, because the assignment is a name-INDEX inside exactly the export bytes that changed. Only the foliage 12 (M_fir_bark 3, M_fir_twig 4, M_grass_medium_01 5) were genuinely re-run, at `cf8dd941`. (ii) The CLEAN half of 31/31 is **UNVERIFIED** — only the denominator was confirmed. (iii) "Sub-surfaces, triplanar, macro variation in the graph" is proven as **PRESENCE, not CONNECTIVITY** — a name-table reference and a node count cannot distinguish a wired graph from orphaned debris, and this project has been bitten by exactly that three times (`8bbe231d`, `9f5d573e`, M_fir_bark→twig). No rendered feature has been tied to triplanar or to macro variation specifically. Open lead, inference not finding: the 31 samples over 22 textures put the entire surplus in COLOR (14 over 5 albedo) while NORMAL and MASKS are 5-over-5 — if triplanar re-projects albedo on three axes but samples normal once, they disagree on steep rock. |
| 3 | Rock & cliff dressing | **DONE FOR THE `hero` ROLE ONLY.** R12 written. 759 boulders placed, verified, saved. `cliff` and `talus` MESH roles are specified in R12 and **NOT PLACED** — only the material's scree texture represents them. *(Audited 2026-08-06 — **CONFIRMED** vs the saved world's 504 packages and their 493 grid-cell IDs (set difference 0 both ways against the plan's predicted cells), engine line traces taken today (80/80 hits, median residual **+0.000 m** against COLLISION), and a post-fix render. Twelve of the 13 measured rock meshes appear in **zero** of 1,683 actor packages — the one `cliff_face` string hit is a capture CAMERA. `verify_grounding.py` was excluded from the corroboration: it reads the planner's own heightmap. THREE ADJACENT RECORDS ARE WRONG — see the audit's list above: R12 "Not yet placed", the "max 0.103 m" tolerance (against collision, 7/80 exceed 0.10 m, worst +0.647 m), and `trace_grounding.py`'s rock pivot premise. RESIDUAL: no CURRENT instance count exists — disk proves a 493-cell FOOTPRINT, not a count; the only 759 read from the engine is the 2026-08-04 reflection, which predates the terrain repair.)* |
| 4 | Vegetation completion | **3 of 3 exit gates closed** *(audited 2026-08-06 — OPTIMISTIC: the COUNT is confirmed, the quoted grounding PRECISION is not)*. **COUNT CONFIRMED against the live world by an instrument that cannot see the plan:** `get_instance_count()` summed over every foliage component returns **157,554 conifers / 1,044 components / 1,328 IFAs**, plus 759 boulders; `git log --since=2026-08-04 -- foliage/ scripts/place_foliage.py` is EMPTY, so nothing was re-placed. (a) Flare GROUNDING: sink 0.12 m. **The recorded "max 0.001 m" is arithmetic about `alpine_heightmap_v2.png` read through the PLANNER'S OWN LOADER — `verify_grounding.py:20-32` disclaims its own independence in its docstring** ("this would report zero gap on a map where every tree hovers"). Measured against ENGINE COLLISION over 500 line traces, 500/500 hits: **p50 +0.006 / p90 +0.068 / p99 +0.202 / max +0.392 m**, 35% reading as SUNK rather than floating, distribution near-symmetric about zero. The 0.392 m tail is collision-heightfield quantization, not a placement bias — the same-points collision-vs-heightmap disagreement is max 0.431 m — and no floater is visible in any of 19 v2sweep frames. **The trees are grounded; the cited number is 392x tighter than contact with the collidable world.** **OPERATIONAL HAZARD, non-negotiable 24:** `python scripts/trace_grounding.py --n 500` at its documented default epsilon 0.05 m prints **FLOATING CONFIRMED (13.2% of sample) and exits 5** on this exact data. The gate is closed by an ADJUDICATION that lives only in `LESSONS.md:10523-10533` — encoded neither in the instrument nor in RECIPES.md, and no epsilon waiver is recorded anywhere. A fresh session running the project's own instrument will read this gate as FAILING. Fix: raise the epsilon to the measured quantization floor with the derivation written down, or teach the instrument to subtract the collision-vs-heightmap residual. (b) Flare/trunk COLOUR: **CLOSED BY RULING 2026-08-04.** Cause disproved (M_fir_bark audits clean; rendered hue 1.000/0.904/0.754 matches bark, not twig). Sunlit verticals read pale because at a 12-deg sun they get **4.7x** the ground's illuminance and R13 exposes for horizontal terrain — **Ryan ruled: accept it, it is the look of a low alpine sun.** R13 2d locks it; two REJECTED entries stop a later session 'fixing' it by dimming the sun or the exposure. (c) LOD colour mismatch: **MEASURED 2026-08-05 - +1.4% luma across the 46.3 m LOD0->LOD1 switch, hue unchanged. NOT a defect.** The reported paleness is the pale-verticals effect ruled ACCEPTED (R13 2d), present at all ranges rather than at a transition. Frames in `_verify/`. Caveat: one subject, differing frame clipping (self-flagged; not independently re-measured by the audit). **Pass 4 exit gates: 3 of 3.** Standing caveat: no instrument yet reads the engine's actual instance TRANSFORMS — both grounding checks take instance Z from the plan and differ only in ground source, so "instances are where the plan says they are" rests on pixels alone. |
| 5 | Ground truth detail | **SCOPED (2026-08-05), NOT BUILT** *(audited 2026-08-06 — **CONFIRMED** vs a positive-controlled string search of all 1,683 saved World Partition actor packages: `Vegetation_Debris` 0, `Boulder_05a` 0, `SM_Boulder05a` 0, `ground_detail` 0, `FT_Scrub` 0 — against controls `FT_Boulder` 504, `FT_Conifer` 1044, `GT_alpine_Meadow` 256. Same command, same corpus, opposite answers, so a zero is a measurement and not a broken instrument. `Content/Foliage/` holds 4 assets and no clutter type; `foliage/` holds 2 plans; `recipes/alpine.json` declares 3 species; no clutter script exists. Zero editor queries.)* **The scope EXISTS and CLAUDE.md's "PASS 5 HAS NO WRITTEN SCOPE" below is STALE AND FALSE:** ground clutter — small rocks, deadfall, debris at foot level from the measured KiteDemo palette, added as new species through R12's existing machinery; density RULED sparse-and-clustered, with deposition and flow fields as legitimate placement priors. Ruling at `RECIPES.md:3030` and `BACKLOG.md:587`. Two palette assets are admitted and measured but unspawned: `boulder_small` and `vegetation_debris`. Caveat on the audit's own method: the search covered board-derived names and did not cover `__ExternalObjects__` or a LandscapeGrassOutput route, so it would have missed a clutter build done under an unanticipated name — the verdict stands, the confidence was calibrated high. |
| 6 | Atmosphere | **DONE for sun and exposure; R13 written.** The sun was **5x too dim**: `intensity_lux` is TOP-OF-ATMOSPHERE (`atmosphere_sun_light` is always True), so 18000 delivered 8,288 lux green where the physical value at 12 deg is 49,000-60,000. Now 130000 + exposure -1.786 EV, solved not tuned. Applied, captured, saved. **GPU COST MEASURED 2026-08-06 (attended) and CLOUDS RULED — back half UNBLOCKED.** sweep_2000 GPU 94.45 ms / sweep_0060 75.71 ms, GPU-bound at both, cost is per-pixel shading not scene bloat. CALIBRATION CLASS binds every citation: editor viewport, Intel iGPU, 971x752, editor perf config — NOT shipping, NOT PIE, NOT the 5080. Clouds split: **OFF interactive (standing config), PERMITTED offline** conditional on measuring the render-class per-frame delta at first enablement. RE-OPEN on 5080 arrival. Full text: R13 ADDENDUM. *(Audited 2026-08-06 — **OPTIMISTIC**. **Sun and exposure CONFIRMED ON THE LIVE WORLD** by three representations, none of them the recipe: `Lighting_alpine_Sun` intensity **130000.0**, temperature 7800.0, `atmosphere_sun_light` **true**, pitch -12.0 / yaw -75.0, one directional light; the editor's own `LogPython __LANDSCAPELAB_EXPOSURE__` shows exactly ONE unbound PostProcessVolume with `AEM_MANUAL` and bias **-1.786 both OVERRIDDEN** (so the value is in effect, not an inert default — the non-negotiable 17 trap); independent pixel decode gives whole-frame linear luma **0.3169** vs solved 0.3201, -1.0%, 0.04% blown. **CORRECTION — FOG IS APPLIED AND RENDERING, not merely "computed":** density 0.0015, start 1500 m, volumetric on, datum 101 m — every field live and matching the recipe — and **UNTUNED**, showing heavy aerial haze at 8.7 km. **NOT PROVEN — "clouds NOT enabled":** a `VolumetricCloud` actor is in /Game/Alpine (count 1, present since ≥2026-08-04), no recipe declares it, no script disables it, `apply_lighting`'s foreign-actor census does not cover the class, and its visibility was NOT READ. **UNVERIFIABLE:** `camera_aperture_f_stop` (read raised) so one of four exposure terms is unconfirmed; and the 94.45/75.71 ms GPU figures have no artefact — attended viewport reading, correctly class-labelled in R13 but unfalsifiable from the repo. Also `PROJECT_STATE.json` is STALE and still records the REJECTED sun intensity 18000.0.)* |
| 7 | Full verification + the clip | **SWEEP RE-ESTABLISHED 2026-08-06 (v2sweep) ON THE CORRECTED TERRAIN; gate open on FOUR items, not three** *(audited 2026-08-06 — OPTIMISTIC)*. Independently proven: 19/19 frames present and usable at 1920x1080; every headline statistic reproduces from pixels under independent code (0.3169 exposure, 0.157 cliff_face, 0.047/0.048 near-station std); and the sweep really did run on v2 — `959ec140` is a git ancestor of the capture tag `fb9a1bc2`, and more convincingly, engine collision agrees with the v2-derived plan to **max 0.431 m over 500 points** where a v1 world would diverge by hundreds of metres. The clip does not exist (`find` for any video returns nothing) and correctly waits on the gate. **THE FOUR OPEN ITEMS:** (1) close-range cliff-stretch evidence — ABSENT, the dedicated `cliff_face` station rendered at luma 0.157 with 0.64% of pixels above 0.5, too dark to adjudicate; (2) `spine_aretes` CV re-test — **no instrument exists**, `spine_aretes` appears in `recipes/alpine.json` and in ZERO of the files in `scripts/`; (3) the two polished falloff spots — **no instrument exists**, `polished` appears in no script; (4) **the near-station shadow DEFECT** — a station-siting fault, not an absence of evidence, which the 3-gap count omitted: it left `sweep_0060` and `sweep_0150` unusable, so criterion 9 "ground→2 km continuity" is graded on **4 of its own 6 stations** with near range substituted from `trunk_base`/`forest_floor`/`rock_grounding`. **AND:** SWEEP_REPORT §2's three-row grounding table is TWO representations, not three — rows 2 and 3 are the signed and absolute values of the SAME 500 pairs in `trace500.json`, and row 1 shares the v2 heightmap with the plan column of both. The grounding conclusion still holds on the two genuine sources; the table's shape overstates the corroboration (non-negotiable 0, inside the record that was auditing everything else). |

**Instruments added 2026-08-04, usable by any later pass:**
`scripts/prove_gates.py` (7 mutations refused, 28 probes rejected, 5
adoption cases, dead-gate sweep over 38 checkers — no editor, so it runs
during a cold replay); `scripts/verify_grounding.py` (signed gap for
EVERY instance, not a sample); `measure_rock_meshes.py` now records
per-LOD triangles and real LOD screen sizes;
`scripts/sun_exposure.py` (**45.7% of conifers are in terrain shadow**
at the 12-degree sun — this is why three verification frames came back
unusable, and why a camera must pick its SUBJECT before its position);
`scripts/measure_lod_materials.py` (per-LOD sections and materials).

**The sun is at bearing 105, not 285.** `lighting.sun.azimuth_deg` is
the light actor's YAW — the direction light TRAVELS. Reading it as the
sun's position puts a camera on the shadowed side; measured forward
vector is `(0.2532, -0.9448, -0.2079)`.

**Open defects added 2026-08-04:** one boulder of 759 sits 0.103 m off
its expected offset (not absorbed by widening); `save_level` can exceed
the remote-exec deserialization limit and exit non-zero on a save that
SUCCEEDED — treat that as UNKNOWN and settle it with a dry-run.

**REPLAY BATCH 1 was NOT run this session.** All 13 recipes remain
UNPROVEN; Passes 3 and 4 took its place.

### HANDOFF 2026-08-06 (day) — RE-SWEEP DONE ON THE CORRECTED WORLD. THIS IS THE LIVE STATE.

**The world is v2 (959ec140) and R17 has now run in full against it —
tag `v2sweep`, all six steps green, 19/19 frames verified. Rewritten
`SWEEP_REPORT.md` is the report of record; its §8 ledger says what
survived the terrain correction and what did not.**

- **Step 0 PASSED for the first time in a sweep context:** p50 0.030 /
  p90 0.200 / max 0.467 m, 100/100 hits, fresh seed.
- **FLOATING TREES CLOSED.** Two instruments plus a cross-check:
  `verify_grounding` conifer max 0.001 m (plan-vs-file);
  `trace_grounding --n 500` gap p50 +0.006 / p90 +0.068 / max
  +0.392 m (plan-vs-collision); collision-vs-heightmap at the SAME 500
  points is |d| p90 0.091 / max 0.431 m, signed mean −0.007 — the
  trace residual IS collision quantization. No sky-hung tree in any of
  19 frames. Nothing was moved; R-FOLIAGE-GROUND step 1 stays REVOKED.
  The old "floating trees" defect was the terrain divergence itself.
- **Stations: numbers identical (delta +0.00 m), validity new.** The
  derivation reads the file; the file never changed; the world now
  matches it. NEW FINDING logged two-altitude: sweep_0060/0150 sit in
  TERRAIN SHADOW on the real world (luma std 0.047/0.048) — the "lit
  sector" is a bearing check, not a shadow march (R17 REJECTED).
  Near-range criteria take evidence from the lit ground stations.
- **Exposure re-proven on v2:** diag_topdown linear 0.3169 vs solved
  0.3201 (1.0%). −1.786 stays.
- **Sampler audit 43/43** — foliage gap closed by the narrowed hook
  (M_fir_bark 3/3, M_fir_twig 4/4, M_grass_medium_01 5/5, landscape
  31/31).
- **Per-criterion verdicts (SWEEP_REPORT §4):** tiling PASS at every
  lit range; seams PASS; cliff stretching NO DEFECT FOUND on the lit
  0700 wall, close-range evidence still absent (cliff_face station is
  in shadow); meadow unreadable everywhere, consistent with 0.41%
  world coverage — Ryan REJECTED it, expansion proposal in BACKLOG,
  sequenced after the sweep.
- **The gate does not close yet, on three EVIDENCE GAPS, not defects:**
  (1) a lit close-range cliff face; (2) `spine_aretes` CV re-test
  under full materials (needs an instrument); (3) the two polished
  falloff spots. SWEEP_REPORT §6 carries the list. Nothing measured on
  the corrected world is failing.
- **Concurrent-session note:** the overnight unattended session was
  still alive this morning and committed the hook narrowing
  (fb9a1bc2), a duplicate foliage audit + meadow proposal (cf8dd941),
  and this session's staged evidence (0267dffc, deliberately, marked
  "no verdict"). Both write streams landed cleanly; hazard logged in
  LESSONS.

---

### HANDOFF 2026-08-06 (late) — ANSWERED: THE TERRAIN ADOPTION NEVER LANDED.

**THE LIVE LANDSCAPE IS `terrain/alpine_heightmap.png`, THE PRE-STAMP
MAP** — render surface AND collision both, matched at **|delta| = 0.0
height units on 161/161 sampled texels** under the identity orientation.
`alpine_heightmap_v2.png` misses by median 1135 units (~44 m), p90 8487
(~332 m). Settled by agent, commit `dc179071`, full detail in RECIPES.md
under `R-COLLISION-REBUILD — LIVE SURFACE IDENTIFIED`.

**MY "RENDERS v2, COLLIDES v1" FINDING IS RETRACTED.** There was never a
render/collision split. Collision agrees with the render; both are the
old map. What the trace measured was real, and my interpretation of it
was wrong — because the render half was inferred from the placement plan
matching the v2 FILE instead of measured against the live world.
Non-negotiable 0, violated in the session that ratified it.

**WHAT THIS MEANS**
- The 2026-08-03 terrain adoption **did not persist**. Pass 1 is not
  done, whatever the campaign table says.
- 157,554 conifers and 759 boulders were placed from v2 onto a world that
  is v1. **The maps differ by >10 m over 37.94% of the terrain** — that
  is the floating trees, fully explained, with no LOD and no collision
  staleness involved.
- `CURRENT STATE`'s "Terrain: isotropic, relief 0.48, pushed and
  verified" **is contradicted by measurement** and must be corrected.
- `check_collision_truth` still FAILS — but it is now reporting
  collision-vs-*the wrong file*, not collision-vs-render. Its threshold
  and fail direction stand; re-read its verdict once the terrain is
  right.

**NEXT ATTENDED SESSION, in order**
1. Root-cause why the 2026-08-03 push did not persist. One item is
   declared OPEN and honestly so: whether edit-layer 0 holds v2 unmerged
   **cannot be read from Python** (no reflected `GetHeightmap(FGuid)`) —
   that is "could not look", not "looked and absent".
2. Re-push v2, **gated on the now-proven export read-back flipping to
   v2 / identity / 0.0** — the export is a working instrument and is the
   acceptance test.
3. Flush collision in the SAME session, then `check_collision_truth`.
4. Re-verify grounding for all instances against live traces.

**Do not reproject any instance. The trees are not wrong; the ground is.**

**What is solid, measured, and safe to rely on:**
- The sweep RAN under R17: 19/19 frames, `verify_frames` exit 0. Capture
  path proven; capture guard proven (sentinel cleared on orderly exit).
- Landscape COLLISION matches `terrain/alpine_heightmap.png` (pre-stamp)
  to p50 0.017 / p90 0.097 / max 0.30 m, and disagrees with
  `alpine_heightmap_v2.png` by p90 94-170 m, max 267-291 m.
  `check_collision_truth` FAILS, correctly, and is R17 step 0
  (ADVISORY for the render sweep, BLOCKING for anything consuming
  collision).
- The landscape has ONE edit layer, confirmed live.
- `SetHeightData` DEFERS collision on the edit-layer branch
  (`LandscapeEditInterface.cpp:438-440`) — collision is marked dirty and
  applied "next time UpdateCollisionHeightData is called".

**What broke the premise, at the very end of the session:**
`push_heightmap --probe-size` exports the LIVE landscape at full coverage
with real values, and **only 4 of 19 sampled points match v2.**

Everything built today assumed "the landscape RENDERS v2 and COLLIDES
v1". **The render half was never measured against the live world** — it
was inferred from the placement plan matching the v2 FILE. That is
non-negotiable 0 violated in the very session that ratified it:
plan-vs-file and file-vs-collision share the FILE as their source.

So the live surface might be v2 (with a broken read-back), might be the
pre-stamp map (meaning **the 2026-08-03 adoption never landed** and
157,554 conifers were placed from a file the world does not match), or
something else again.

**A background agent was dispatched to settle exactly this**, read-only:
`--probe-layout`, `--probe-export`, then compare the live export against
BOTH heightmaps. Its findings land in `RECIPES.md` under
`R-COLLISION-REBUILD — LIVE SURFACE IDENTIFIED (or NOT)`. **Check whether
that section exists before doing anything else.** If it does not, the
agent did not finish and the question is still open.

**Three landscape mutations returned "ok" and moved nothing today**
(`r.LandscapeLODBias`, per-component `ForcedLOD`,
`force_layers_full_update`). Read back and verify every landscape write;
"the call returned" means nothing here.

---

### HANDOFF 2026-08-06 — STEP 7 RAN. THE GATE DID NOT PASS.

**Full per-criterion report: `SWEEP_REPORT.md`. Recipe: R17.**

The sweep executed twice, 19/19 frames both times, verified present and
non-trivial. What it found is that the gate is not closeable from the
recorded stations, plus one new measured defect.

**CLOSED THIS SESSION**
- **The "UNKNOWN" capture stall is EXPLAINED and `capture.py` is not
  implicated.** Two runs: run A wrote **2 frames, not zero**, then the
  editor was CLOSED from the UI 40 s later; run B never captured at all
  and died on `EditorServer.cpp:1951`. **Two BACKLOG claims were false
  and are corrected in place.** Left genuinely open: why run B wrote
  nothing in the 40 min before it crashed (candidate: LESSONS 14.7,
  foreground required).
- **That crash is FIXED.** `open_level.py` fataled the editor WITH its
  `gc.collect()` guard in place — persistent-console globals from an
  earlier payload are LIVE, not garbage. Now scrubbed by reachability at
  the choke point, asserted, fails closed. 23 sites across 18 files bind
  such a global; one deleted it. `test_open_level_scrub.py` 13/13.
- **Instrument proof is now a tool, not a habit:** `verify_frames.py`
  refuses a verdict unless every frame is present, correctly sized and
  tonally non-trivial. Proven to fire on synthetic flat/black frames.
- **Sampler audit:** 31/31 clean on `M_AutoLandscape`.
- **Meadow evidence delivered** (non-blocking, Ryan's call): re-measured
  98.06% forest floor / 1.94% meadow, and the sharper new number —
  **0.93% of the Grass layer is CLEAR meadow, ~0.41% of the world.**
  Not readable at either scale.

**THE THREE THINGS THE NEXT SESSION MUST NOT RE-DERIVE**
1. **The stations were RE-SITED 2026-08-06 and the SUBJECT CHANGED.**
   The recorded summit (-844, -1040) z 1406.7 cannot be the subject of a
   ground-level sweep: it is occluded from 80 m to 1200 m out by up to
   122 m of ground, because it is 1406.7 m against a 1549.9 m ceiling
   with taller peaks beside it. Sliding along the bearing cannot fix
   that, and neither can the full circle.
   New subject **(-1700, -592) z 549.11** — a MODEST peak in OPEN ground,
   which is why it is visible; prominence buys nothing here. All six
   stations now clear their sight line by **7.5 / 10.2 / 12.0 / 15.6 /
   12.5 / 8.3 m** (was -0.2 / 2.4 / -29.2 / -1.8 / 2.3 / 5.2, three
   BLOCKED). Median terrain distance per frame now ramps 12 / 40 / 256 /
   1140 / 224 / 452 m and luma std went 0.03-0.17 -> 0.22-0.32.
   Locked in R17; regenerate with `sweep_cameras --resite`.
   **Measured limit:** with a lit face at 1.7 m eye height NO peak here
   clears all six generously — best min-clearance over 34 candidates is
   3.6 m. This is the best available, not an ideal.
2. **THE EXPOSURE IS CORRECT — a "~0.9 stop over" defect I reported
   earlier the same session is RETRACTED.** Settled, do not re-open.
   `read_exposure` (new, read-only) finds ONE unbound PostProcessVolume,
   AEM_MANUAL, bias **-1.786 OVERRIDDEN**, camera f/4 + 1/60 s + ISO 100
   matching the solver's own assumption. And `diag_topdown`, which looks
   straight down at HORIZONTAL terrain, measures **linear 0.3228 against
   the solved 0.3201 — within 0.8%.**
   My error was the denominator: I averaged the lower 45% of frames at
   stations sitting in hollows, a region dominated by sun-facing SLOPES,
   which at a 12 deg sun take up to 4.8x the horizontal illuminance —
   R13 2d's accepted mechanism wearing a different name.
   Open and NOT acted on: `atmosphere_solve --albedo` defaults to 0.2675
   while a texture-only re-derivation against the current weightmap gives
   0.3356 (0.33 stop). That figure ignores tints and blends so it is NOT
   the scene albedo; re-derive it properly before anyone changes the
   default. **The locked -1.786 was deliberately NOT re-solved.**
3. **Scree `saturation` is LOCKED at 0.03** and the outline-to-cone
   criterion CANNOT be met by that knob — 0.25 -> 0.008 moves coverage
   only 1.97% -> 3.55%. The lever is the shared physical parameters,
   which move Pass 3's talus meshes too.

**NEW DEFECT, OPEN — TREES FLOATING IN THE SKY.** Conifers hang in open
sky with their trunk BASES exposed, in `_verify/20260806_resite_sweep_
0060.png` (upper-left and upper-right) and in `sweep_1200`. Reproduces
across stations and framings. **CAUSE NOT ESTABLISHED and deliberately
not guessed.** Note `verify_grounding` proves placement to max 0.001 m
over all 157,554 conifers, so this is a RENDER-side disagreement, not a
placement fault — which is exactly why a world-space grounding proof
could never catch it and it took a frame. Candidates and the
**The LOD test was attempted and DID NOT RUN:**
`SystemLibrary.execute_console_command(world, "r.LandscapeLODBias 3")`
returns clean and the cvar still reads 0.0, in the same payload and from
a fresh connection. The set SILENTLY FAILS, so that capture ran at bias 0
and the hypothesis is untested. Find a mechanism that actually moves
landscape LOD before retrying (per-component `LODBias`, or the
scalability path — `sg.ViewDistanceQuality` is 1.0 under the low-spec
profile and already pulls transitions in).
**It did hand over the control I lacked:** two identical-settings runs
differ by up to **26%** on the stranded-pixel metric (whole-frame
mean|diff| 0.012-0.035 vs 0.137 for different cameras). **That is the
NOISE FLOOR — any LOD signal must clear it, and the +8% mean I nearly
read as confirmation does not.** Always capture a same-settings repeat.

Candidates and the discriminating check are in `SWEEP_REPORT.md`: landscape section LOD
rendering below the true surface (compare instance world Z against
rendered landscape height at increasing view distance); streaming/HLOD
(the residency gate loads ACTORS, which does not cover per-section render
LOD); or a foliage-vs-landscape cull mismatch.

**NOT DONE:** `spine_aretes` CV 0.089 re-test; the two polished falloff
spots; cliff stretching (the face carries too little detail to prove it
either way); foliage sampler audits — blocked because the
`msys-game-path` hook fires on BOTH of its own suggested remedies.

**The clip comes after this gate passes. It has not passed.**

---

### HANDOFF 2026-08-05 (late) — superseded by the above, kept as record

**Tree clean. 161/161 hooks. All gates refuse.**

## 1. COMMITTED (by hash, from `git log`)

    a93c1e8b  Grass layer INVERTED: forest floor primary, meadow exception
    bc200140  Fix _ramp forward reference; Wild Grass WIRED, 22 textures
    f9233093  R16: coherence ruled by PROVENANCE; Pack_Bonus excluded
    21e2d54b  Calibration at n=4: grass does NOT separate
    ecfaa5bf  Campaign close-out: H11/H12 advisory, burndown designed
    1d54c5f8  Governance layer complete: 12 skills, 3 agents, 12 hooks

## 2. PROVEN (number + instrument)

| Claim | Number | Instrument |
|---|---|---|
| Grass selector coverage | **98.13%** of layer (96.94% at >0.90) | weightmap x variant map, weighted |
| Meadow share | **1.87%** of Grass layer | same |
| Material after INVERT | 22 textures, assert **EXACT**, compiled clean | `make_landscape_material` |
| Invert render | luma 174.8 / 178.6, no blowout | `_verify/20260805_grass_invert.png` |
| Hook layer | **161/161** three directions | `prove_hooks.py` |
| Gates | 7 mutations, 31 probes, 5 adoption, 38 checkers live | `prove_gates.py` |
| Grounding | Conifer max 0.001 m; Boulder max 0.103 m (1 outlier) | `verify_grounding.py` |
| Sun | ground illuminance green 59,858 lux in 49-60k band | `atmosphere_solve.py` |

## 3. DECIDED BUT UNBUILT — do not re-litigate

- **Coherence is ruled by PROVENANCE, not appearance** (R16). The
  measured instrument was retired FOR CAUSE: grass at n=4 overlaps on
  all three features, and the n=1 "separation" was an artefact — a
  single point cannot overlap a range. `surface_coherence.py` and
  `per_family_calibration.py` are kept as DESCRIPTIVE only.
- **Pack_Bonus EXCLUDED — provenance.** Substance Designer, procedurally
  authored. No measurement needed.
- **INVERT over NARROW.** 98.13% is not a sub-surface. NARROW would mean
  shrinking the band from 98% to ~50%, severing it from the 120-640 m
  forest band it models — tuning to a coverage number, not to terrain.
- **The 7 calibration surfaces are CALIBRATION-ONLY.** No R-ASSET
  intake, no ASSETS rows, not wired. `Dry_Fallen_Leaves` has **no `_H`**
  and cannot feed HeightLerp without one.
- **Nightly burndown: designed, NOT scheduled.** First run attended;
  scheduling is a separate ratification.

## 4. OPEN ITEMS

- **STEP 7, THE SWEEP — the campaign's acceptance condition.** Ground→2
  km continuous move; no tiling pop, no blend seams, no cliff stretching
  at any distance; sampler audits on all materials; **scree `saturation`
  tuned INSIDE the sweep** against the rendered apron (outline→cone
  criterion, final value LOCKED); **`spine_aretes` CV 0.089** re-tested
  under full materials; the two polished falloff spots re-checked.
  Renders dated into `_verify/`. Clouds-on only if measured cost allows,
  else note it. **The clip comes after this gate passes.**
- **Is 1.87% meadow enough open ground?** WORLD-DESIGN CALL, Ryan's,
  **not blocking the sweep** — judged best FROM the sweep's renders.
  **Flag meadow readability at BOTH scales in the sweep report** as the
  evidence. If the answer is "more", the fix is a wider meadow band or a
  different selector — **never another swap.**
- **Sweep capture has failed before and the cause is UNKNOWN.** A prior
  run wrote zero frames, stalling on the FIRST camera (one that had
  succeeded minutes earlier), no summary block, no exit code. RAM was
  3.1 GB free and the editor stayed alive, so the memory explanation
  does NOT fit. Re-run on a fresh editor before anything else touches
  it; a second stall on a known-good camera is a reproducible
  editor-side condition worth diagnosing, not a third retry.
- **Sweep camera design is RECORDED in BACKLOG** — six stations at 60 /
  150 / 350 / 700 / 1200 / 2000 m along the MEASURED sun bearing (105,
  not the recipe's 285, which is the light's yaw), each at 1.7 m eye
  height above LOCAL terrain. Regenerate exactly; do not re-derive.
  **2026-08-06: regeneration is now MANDATORY, not optional — the six
  placed Capture_alpine_sweep_* actors predate the v2 push and sit
  against the new ground (`sweep_0060`'s 20260806T060613Z frame is a
  full-frame cliff face). "Above LOCAL terrain" now means above v2.**
- **One boulder of 759** sits 0.103 m off expectation. Not absorbed by
  widening.
- **`t.MaxFPS` does not take effect** — live editor reports 0.0.
- **13 recipes remain UNPROVEN.** REPLAY BATCH 1 never run.
- **Campaign's one open item: background migration** + liveness
  consuming the native completion signal. Named, not buried.

## 5. NOT DONE / NOT VERIFIED (standing rule 10)

- The sweep itself. Everything above it is closed; **the gate is not.**
- Cliff and talus MESH roles: specified in R12, **never placed**.
- Fog and aerial perspective: computed, **never tuned** against a 2 km
  render.
- GPU frame cost: **never measured**. Clouds stay off on an unmeasured
  budget.
- Pass 5 ground clutter: scoped and ruled, **not built**.

### Offline verification suite — re-run at will, no editor

Every one of these runs on the CPU with nothing open, so they survive a
cold replay and can gate a commit:

    python scripts/prove_gates.py        7/7 mutations refused
                                        31/31 recipe probes rejected
                                         5/5 rock-plan adoption cases
                                        38 checkers, all with call sites
    python scripts/verify_grounding.py   Conifer 157,554  max 0.001 m  0 outside
                                         Boulder    759  max 0.103 m  1 outside
    python scripts/sun_exposure.py       54.3% of conifers lit, 45.7% in
                                         terrain shadow at the 12-deg sun
    python scripts/atmosphere_solve.py   ground illuminance 91404/59858/28543
                                         sunlit terrain linear 0.3201

**~~PASS 5 HAS NO WRITTEN SCOPE~~ — STRUCK 2026-08-06 BY THE PASS AUDIT.
IT IS FALSE.** Pass 5 was SCOPED on 2026-08-05 at `RECIPES.md:3030` and
`BACKLOG.md:587` (ground clutter; density ruled sparse-and-clustered;
new species through R12's machinery). A session obeying the paragraph
below would re-scope a pass that has a ratified scope — wasted work at
best, a divergent second scope at worst. Kept only as the record of what
was believed. The campaign table's Pass 5 row carries the live scope.
The paragraph as written:

**PASS 5 HAS NO WRITTEN SCOPE.** The campaign table says "Ground truth
detail" and nothing anywhere defines it — not BACKLOG, not RECIPES, not
this file. It was NOT invented and half-built; the next session should
scope it deliberately. The evidence suggests it wants: the meadow-grass
surface (BLOCKED — needs a Megascans intake from Ryan's account, which
no script here can do), the Grass sub-surface currently wired as a
declared no-op, and ground clutter at foot level.

**AND EVERY GROUND-LEVEL JUDGEMENT MADE BEFORE 2026-08-04 WAS MADE
UNDER A 5x UNDERLIT SCENE.** The scree apron "reads as an outline, not a
cone", the forest-floor tint, the grass read — all were assessed before
the sun was corrected. Re-take them before acting on any of them.

### The four things a fresh session must not re-derive

1. **Pass 2's brief is arithmetically impossible as written** — five
   surfaces against a three-channel weightmap
   (`make_layer_weightmap.py:171` refuses at four). Ruling and design are
   in **R2 → PASS 2 UPGRADE**. Do not redesign it; build it.
2. **16-bit conversion is now ONE shared module** —
   `scripts/texture_16bit.py`, promoted under non-negotiable 4a because
   the fix lived in `import_static_mesh.py` while
   `import_surface_set.py` had none at all. **A local re-implementation
   of it is now itself a REJECTED pattern.** R3's "ambientCG maps are
   8-bit" was measured **false** and is corrected in place.
   `displacement` is in `DEFAULT_ROLES`; T_Rock051_D / T_Snow006_D /
   T_Ground037_D are imported and traced to their `_8bit.png` sources.
3. **The terrain is now `terrain/alpine_heightmap_v2.png`** — recipe
   adopted 2026-08-03 behind tag `pre-stamp-adoption`, **but the LIVE
   WORLD only became v2 on 2026-08-06**, when the first-ever v2 push
   ran, gated and saved (tag `pre-v2-repush-20260806`; measured at
   161/161 texels, delta 0.0). `alpine_heightmap.png` is the PRE-STAMP
   base and is still `stamps.base`; do not confuse them. Re-running the
   compositor rewrites `alpine_stamped.png` and CANNOT touch the
   terrain (non-negotiable 20).

4. ~~**The talus cliff-source threshold is stale and MUST be fixed before
   Pass 3.**~~ **STRUCK 2026-08-08 — IT WAS FIXED FIVE DAYS EARLIER AND
   THIS ENTRY WENT ON SAYING OTHERWISE.** Landed 2026-08-03 in
   `0b6a412b`, a commit whose subject line is *"Pass 2 opens: the talus
   cliff-source test moves to LANDFORM slope"*:
   `rock_scatter.landform_slope()` (:173) smooths at `source_smooth_m`
   before taking the gradient and carries the measurement in its own
   docstring (cell-scale ≥50° = **9.152%** of the map, 16 m landform
   ≈ **5.3%** — so ~40% of the cell-scale "cliff" area is texture);
   `build_context` (:673-684) passes it as `source_slope_deg` while
   every other consumer still reads the real surface; and
   `recipes/alpine.json` → `foliage.rock_scatter.source_smooth_m` is
   **16.0**, in the shared block non-negotiable 19 requires.
   **Pass 3's cliff and talus roles are NOT blocked.**
   *Why this matters more than one stale line:* on 2026-08-08 this
   paragraph was copied into `plans/clip_30s_proposal.md` §1.1 as the
   blocker on the largest quality gap in the whole clip sequence,
   without the file being opened. A section titled "must not re-derive"
   is read as settled fact, which makes a stale entry in it strictly
   more dangerous than a stale entry anywhere else. Non-negotiable 9
   applies to this document too. Kept, struck, as the record.

### Open, and honestly unknown
- ~~**Nanite is UNKNOWN on all 38 palette assets.**~~ **ANSWERED
  2026-08-07 — Nanite is DISABLED on 38 of 38, zero could-not-reads**,
  read from the loaded mesh's `nanite_settings.enabled` by
  `scripts/measure_palette_live.py`. Artefact:
  `Free/_measured/palette_live.json`. The guess would have been right;
  the point of holding it UNKNOWN was that the same absent tag would
  also be produced by a Nanite-ENABLED mesh whose tag was never written.
  Kept here as the record of a correctly-held unknown.
  **In the same run: `measured.material_slots` disagrees with the loaded
  mesh on 23 of 38** (the audit had found 8 of 13) — the field remains
  DO-NOT-CONSUME. **`triangles` agrees on 38 of 38**, which is the
  positive control and draws the boundary: ONE field of the registry
  scan is bad, not the scan.
- **Are the 16-bit ambientCG NORMAL maps harming the landscape?** They
  are imported today. Different code path from both known defects. Not a
  defect and **not a clearance** — needs a render. BACKLOG.
- **No meadow-grass surface exists.** Pass 2 delivers four of five
  mandated surfaces. The fifth needs an R3 intake.
- Free disk **60.8 GB** (floor 50). Free RAM at session start **0.86 GB**
  of 15.4 — the editor was running and paged out. Any editor work needs
  `resource_guard.py` first.

### Next step
**SUPERSEDED — the live next step is the HANDOFF section above: STEP 7,
THE SWEEP.** Pass 2 is built and its sub-steps below are kept only as the
record of how it was built. The one Pass 2 item still open — the
ground→2 km continuous sweep — is now step 7 of the region queue and is
specified in the handoff, not here.

**Pass 2 implementation.** Step 1 (displacement import) is DONE.

1. ~~Convert + import the displacement maps.~~ **DONE** — but note the
   proof so far is PROVENANCE, not pixels. The render proof arrives with
   step 3.
2. ~~Bake the sub-surface selector.~~ **DONE.**
   `textures/alpine_variants.png` → `/Game/Textures/T_Alpine_Variants`
   (2017², TA_CLAMP, uncompressed, srgb=False — same settings as the
   weightmap by design). `foliage.rock_scatter` is the SHARED block
   (schema v1.17) read by both this bake and Pass 3's talus scatter.
   Channels: R Snow = **declared inert**, G Rock = scree (1.97% of the
   Rock layer, **too sparse — tune `saturation` in the sweep**), B Grass
   = forest floor (**99.03% of its layer; the Grass sub-surface is
   DEFERRED and wired as a no-op** until a meadow surface is intaken).
3. ~~Sub-surfaces + HeightLerp.~~ **DONE 2026-08-03.** Rock binds
   Rock026 at contrast 0.35; Grass is a declared-but-unbound no-op.
   Graph assert **EXACT** (16 textures), **compiled clean**, renders with
   no NaN signature (blown-white 0.0000% before and after). Blend weights
   are computed once per band and shared by albedo, normal and roughness.
   Checkpoint: tag `pre-subsurface-material`.
4. **NEXT — triplanar** on rock above the slope threshold; then macro
   variation (km-scale, judged at 2 km); then RVT (landscape writes;
   config as EXACT VALUES for Pass 3's mesh sampling). Same increment
   discipline: build → assert → render-check per feature.
   **The preflight AND the assertion both update with every new
   sampler** — lockstep is not one list; see the R2 REJECTED entry.
5. Sampler audit, then the ground→2 km continuous camera move, with
   named re-tests for `spine_aretes` (CV 0.089) and the two polished
   falloff spots under full materials. **Scree `saturation` tunes inside
   that sweep** against the rendered apron — baseline to beat is
   `_verify/20260804_variant_selectors.png` (outline, not cone).

Everything below this line predates the campaign and is still true.

## Superseded next step — REPLAY BATCH 1 (pulled from BACKLOG 2026-08-03)

**Documentation quality has outrun proof.** 13 conforming recipes, 75
REJECTED entries, and **all 13 UNPROVEN** — not one has been replayed
cold. Written down carefully is not the same as reproducible.

Cold-replay, in this order:

1. **R0** — it gates every other recipe's verification. On this machine
   the honest partial replay is: follow the written procedure, run
   `scripts/recover_state.py`, and diff against `PROJECT_STATE.json`.
   The FULL acceptance test is R0 on the future GPU desktop.
2. **R3** (10 REJECTED entries), **R2** (9), **R11** (9) — selected by
   TRAFFIC, not by cost. The most-trafficked recipes are where a replay
   failure teaches the most.

A replay means executing purely from the written steps, making no
judgement calls, and diffing the result against the recipe's own
VERIFICATION section. **Every gap found is the finding** — a recipe that
cannot be followed without prior knowledge is exactly what UNPROVEN
means, and fixing that is the deliverable, not a clean pass.

Use a scratch map for anything that mutates content, so a failed replay
cannot damage `/Game/Alpine`.

---

## SUPERSEDED — CURRENT STATE — 2026-08-30 (C0 in flight: textures REFUSED and to be repaired; FBX in)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

> **⚠ WRITTEN POST-HOC.** The C0 session died on context exhaustion mid-way
> through reading the FBX's slot→texture wiring and wrote no handoff. Everything
> below is reconstructed from git, from disk, and from the editor — not from
> narrative. The work it had done was **uncommitted** and is committed here.

**Tree clean after this commit. AN EDITOR IS RUNNING** on `/Game/Alpine8K`,
rule-7 verified. **19 DIRTY PACKAGES AND NONE MAY BE SAVED**: the C0 house
imported to `/Game/Scratch/C0House` (editor-only, nothing on disk) plus
`M_GlobalRGB_Blend`, whose bytes the kit manifest SHA-256'd.

## ⭐ THE TILEABILITY GATE IS BUILT AND VALIDATED AGAINST A REAL CONTROL

`scripts/verify_tileable.py`. Half-offset seam test, with **the image's own
interior as the control** — "how different are two adjacent columns" is
meaningless in the abstract: small on plaster, large on planks. A fixed
threshold would pass every smooth texture and fail every detailed one.

    Poly Haven, KNOWN-TILING (the donor's own maps)   0.76 - 1.92x   7/7 PASS
    the operator's generated set                     2.55 - 7.90x   5/5 REFUSE
    bar                                                      2.00x

**Clean separation, no overlap, bar in the gap.** 5-of-5 refusals are exactly
the shape this project treats as instrument fault until proven otherwise, so
the Poly Haven maps were run as a real-world positive control before the
finding was believed.

**Two defects in my own instrument, both found by its self-test:**
a peak-to-peak luminance ramp called a flat-lit sine "52.9% baked lighting"
(a full-period sine has a non-zero least-squares linear component), fixed by
also requiring **R² ≥ 0.25** so periodic DETAIL is not read as a light ramp;
and then the synthetic control itself was wrong — one sine period across a
frame **is** a gradient, and refusing it was correct. **Fixed the specimen,
not the bar.**

## ⛔ RULED: REPAIR, DON'T REJECT — and this is the next action

Deterministic seam repair: half-offset both axes, heal the seam cross, restore,
**then RE-RUN THE GATE on the repaired file**. Output beside the original as
`<name>_tiled.<ext>` — **never overwrite the operator's authored files**. Still
failing 2.0× after repair → fall back to that role's original Poly Haven map
and list it as **needs-regeneration with its number**.

## THE DONOR HOUSE IS IN — measured, editor-only

    /Game/Scratch/C0House/SM_C0_DonorHouse
    tris 23,700   verts 25,311   LODs 1   slots 10
    pivot_base_error_cm  -39.81      <- NOT base-centred; the swap must correct it

Fingerprint confirmed before extracting, exactly as briefed: Kaydara binary FBX,
**Blender (stable FBX IO) 3.6.0**, `Material_001…009`, `.fbm` paths at
`C:\Users\Johnny\Documents\`, and the seven Poly Haven CC0 diffuse maps.
Extracted to `Free/_intake/medieval_house_c0/` (gitignored staging) — never
worked inside Downloads, and Downloads is untouched.

## ⛔ WHERE IT STOPPED, PRECISELY

Reading slot→texture wiring. `MaterialEditingLibrary.get_used_textures` is
**deprecated** per the stub — *"Use GetMaterialUsedTextures instead since it
works with Material Instances"* — and refused the parameter outright.
Switched to `get_material_used_textures(material_interface)` and it **returned
data**, but the printout was truncated to the first element per slot, which
read `BaseFlattenLinearColor` on all ten. **That is an engine-internal texture,
not a Poly Haven map, so the list is either longer than displayed or the wrong
thing entirely — UNRESOLVED, and the first thing to re-read.**

Fallbacks if it dead-ends, in order: each material's texture parameter /
expression references; or match slots by `.fbm` filename order from the import
log. **Report which path worked.**

## NEXT, IN ORDER

1. **Re-read the wiring properly** (full lists, not first-element).
2. **Seam-repair the five textures**, re-run the gate, record which pass.
3. Role mapping by **what each slot references** (ruled table), unit scale
   against the kit's measured **200.0 cm** module, derive roughness/normal,
   consolidated UE materials, both houses side by side.
4. **Measurements and commits first, render last** — the ~630 s wedge is
   expected and budgeted.

## CARRIED

Perf budgets RATIFIED and enforced (18 checks, no failures). Kit verified in
engine. `storey_m` 2.0 — the placed town still stands at old heights. Gate A
approved; concept 01 is the first loop subject. Second kit intake owed.

---

## SUPERSEDED — CURRENT STATE — 2026-08-30b (C0: both houses stand; the render is the last step)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Tree clean. AN EDITOR IS RUNNING** on `/Game/Alpine8K`, rule-7 verified.
**A CAPTURE IS IN FLIGHT** — nothing may touch the editor until it lands, and
the ~630 s post-capture wedge is expected.

## ⭐ C0 IS BUILT END TO END. ONLY THE FRAME IS OUTSTANDING.

    textures repaired   5 of 5, 2.55-7.90x -> 1.07-1.52x, ZERO regenerated
    wiring read         10 slots, 0 ambiguous  ->  7 roles
    maps derived        7 roles x normal + roughness, all self-check DX
    master              M_C0_House, 6 expr, 6 reachable, 0 ORPHANED, compiles
    instances           7, all 21 texture params bound and READ BACK
    the pair            2 actors, 26 m apart, base above ground 0.0 cm BOTH
    materials differ    true, read off the LIVE COMPONENT

`recipes/c0_materials.json` holds the role table and separates **measured** /
**derived** / **authored**. Recipe **R-DERIVEMAT**; narrative in `LESSONS.md`.

## ⛔ FOUR INSTRUMENTS WERE WRONG, AND A CONTROL CAUGHT EVERY ONE

1. **`convert("L")` on a 16-bit map returns a CONSTANT.** Ground037's
   displacement, real range 18770..59293, reads **all 255**. The red control —
   same expected sign under both conventions — read 0.000 and refused to issue
   a verdict. `load_float` added to `texture_16bit.py`, the module that already
   owned the defect class; a private copy would be NN4a's rejected pattern.
2. **The convention test labelled all ten vendor files BACKWARDS.** With red at
   +0.53..+0.90 the only candidate left was my predicted sign. Re-derived:
   rows increase downward, so **GL is positive and DX negative** — the opposite
   of what the intake skill states. Ten labels outrank a remembered rule.
   Now 10 of 10.
3. **`set_material_instance_texture_parameter_value` returned False on all 21
   writes and all 21 landed.** Second occurrence (first: 2026-08-16 hero bake).
   The return value is evidence in neither direction; the read-back is the gate.
4. **`audit_material_samplers` audited ZERO samplers on a material with three,
   and exited 0.** Exact class-name match, blind to the whole
   `TextureSampleParameter` family. Fixed to `isinstance`, **and the verdict
   fixed too** — 0-audited on a non-empty graph now refuses (NN6). Regression
   control: `M_AutoLandscape` 37 samplers, 0 mismatches, the recorded figure.

**Binding is by SLOT NAME, and the mesh proved the operator's ruling right:**
index 1 is `Material_007`, index 2 is `Material_009`. An index-keyed bind would
have put rock on the plank slots and reported ten successes.

## ⛔ A REQUIREMENT STATED THREE TIMES IN PROSE AND ZERO TIMES IN CODE

R-CITYSHOT step 1 has said **`ShowFlag.Volumes 0`** since 2026-08-27 and
CURRENT STATE said it twice more — and `city_shot_payload.txt`, the one payload
every editor render passes through, never issued it. NN24 between a recipe and
its tool. Now in the payload.

**And `ue_exec` now parses the substituted payload before sending it.** Fixing
the above landed at the wrong indent, split a `for` body, and cost a 25 s round
trip to be told `IndentationError`. A payload is a call site with no compiler.
Refusal proven (exit 2, editor never contacted); all four C0 payloads parse.

## NOT DONE, STATED PLAINLY

- **The side-by-side frame.** In flight; no pixels judged yet. Every claim above
  is measurement, not appearance.
- **ASSETS.md rows were written LATE** and say so. **The donor zip's licence is
  NOT RECORDED** — fit for a scratch warm-up, *not* clearable for shipped
  content. The Poly Haven CC0 claim is **provenance by filename**, unchecked.
- **Roughness is AUTHORED**, not measured. Normals are an approximation from
  albedo luminance. Both are labelled at every altitude.
- C1, the second kit intake (MODULAR_ASSETS / Roofs / Construction_Pieces), and
  the Phase B loop on concept 01 are all untouched.

## NEXT, IN ORDER

1. **Open the frame** and judge the swap on pixels. Then C0 is closed.
2. Phase C1 — concept-derived materials, through the same gate + repair intake.
3. Second kit intake on the wider seed.

## CARRIED

Perf budgets RATIFIED and enforced (18 checks, no failures). Kit verified in
engine. `storey_m` 2.0 — the placed town still stands at old heights. Gate A
approved; concept 01 is the first loop subject.

---

# CURRENT STATE â€” 2026-08-30i (the buried-roof correction is propagated)

> **â­ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` â€” â›” never a source for a decision.

**Tree clean. No editor running** (R-EDITOR-CLOSE, 2 for 2 on the retry).
Suite: 22 checks, **1 FAIL** â€” the two known-divergent city plans, waived.
Exit code is not a verdict.

## â­ THE BURIED ROOF â€” FOUND, FIXED, AND NOW PROPAGATED

`SM_House02_Roof`'s pivot sits **201.49 cm above its base**, and both payloads
placed the roof at `Vector(x, y, WALL_TOP)` â€” pivot on the wall top, roof
through the walls. `400 - 201.49 + 338.02 = 536.5`, what every ratio was
scored against.

    chalet SILHOUETTE   536.5  ->  738.0     forge + concept loop, both re-run
    church nave         804.8  -> 1107.0     (1.50x -- ratio UNCHANGED)
    church spire       1341.3  -> 1845.0     (2.50x -- ratio UNCHANGED)

**EVERY RATIO WAS CORRECT BEFORE AND AFTER.** The loop built the ruled
proportions faithfully against a reference 27% short, and no delta could see
it: **a ratio check cannot detect an error in the quantity it is a ratio OF**
â€” both terms move together and the quotient is invariant.

Stage 10 and the loop are separate payloads that do not read each other, and
both now land on 1845.0 â€” consistency, not proof; they agreed at 1341.3 too.
**The horizontal deltas did NOT move**, correct because the fix is vertical.

**NOT propagated to the town:** `plan_city.py:504` derives `ridge_height_cm`
as `round(w_o * 0.5, 1)` per building, never from the silhouette. Checked, not
assumed â€” the 303-building plan is unaffected.

**`refs/MANIFEST.md` is the unserved-entity frontier**, counts recomputed from
both concepts.

Optical: `concept_iter1_roofseated.png` vs `..._reshoot.png`, SAME camera â€”
smeared arches become seated roofs. The mesh was never broken: the ragged
shell is a **1% Nanite fallback**; bounds identical either way.

## THE FORGE â€” TWO ASSETS, BOTH PLACED

    church      190,562 v  60,000 tris  genus  61  VRAM 10,082   44 s  1845.0
    wood_stack  1,400,074 v 15,000 tris genus 392  VRAM 14,870  133 s   120.0

`forge_lineup.png` â€” chalet 738.0, church 2.5x, stack 0.163x, errors 0.00.
FORGE_LOG has the repeatability table: the WRAPPER repeated, the COST did not
â€” **5.5 s â†’ 55.7 s** on identical knobs. **A run's cost cannot be estimated
from its inputs**; the second cleared VRAM by **1.2%**. High genus is EXPECTED
for porous subjects, not a defect score.

## â­ GUARDS ASSERT ON THE VALUE â€” NON-NEGOTIABLE 29

Two guards caught hazards they were not aimed at; both check the VALUE at the
point of use. **Class named in LESSONS: A NAME THAT KEEPS WORKING FOR THE
ASSET IT WAS WRITTEN FOR.**

    levels  /Game/Scratch/Forge_<asset>; new_level REFUSES without --overwrite
    paths   ue_exec --set REFUSES the Git-Bash rewrite signature (a header is
            ADVICE; this is a CHECK)
    editor  R-EDITOR-CLOSE: census, quiet-window, RETRY close, then kill.
            Twice now the retry closed it in 10 s and the kill was not needed.

## THE ORDER

    DONE  forge + church + wood stack; stage 10 general; both placed
    DONE  ruling 1 re-derived; church re-run; concept loop re-run
    NEXT  extent-derived FOV -- 1 chalet still outside the frame, AUTHORIZED
    THEN  church texturing -- BLOCKED below

â›” **CHURCH TEXTURING IS SCOPED AND BLOCKED.** `TEXTURING_SCOPE.md`. ONE
material slot (A/B costed, B recommended); the v1 set **has no stone** â€” stone
AND copper missing.

## CARRIED / GATED

**`shoot.py` is the shot entry point**; `which_level_payload.txt` answers rule
11. **Town re-placement (303â†’348) GATED.** `storey_m` 2.0. `ue_exec --timeout`
is a DISCOVERY WINDOW: 12â€“25. 20+ `text=True` sites still use the locale codec
(`forge.py`, `concept_loop.py` fixed).
âš  **RULING 4 UNFINISHED** â€” `fits(10.0, 8.0, (8.99, 9.17), 0.20)` â†’ **True**
over splayed roofs: this same roof's 899/917 on a 1000/800 wall.

---

# CURRENT STATE — 2026-09-01 (the overnight: four concepts stand as UE worlds)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Editor OPEN on /Game/SpikePhoto, deliberately** — Ryan's fly-through plus
the overnight relight loop both want it warm. Tree clean at session close.

## ⭐ THE SIDE PROJECT'S PIPELINE IS REAL: 2D CONCEPT → UE RENDER, AUTOMATED

Overnight under full operator authority (Ryan's ruling 2026-08-31): all four
Gemini concepts (crystal valley, coast, highland lake, canyon) went brief →
`brief_loop.py` terrain convergence → hash-proven adoption →
`concept2level.py` (close/launch/create/material/light/save/shoot, every
stage a proven script) → render-compare iterations via the ~2-minute
`relight` phase. **MORNING_REPORT_20260901.md is the full account**;
`_verify/20260901_overnight/comparison_sheet.png` is the four-way evidence.

    R-BRIEFLOOP   locked -- the terrain iterate loop, audited, selftested,
                  proven on a deliberately degraded recipe
    worlds        /Game/SpikePhoto  /Game/CoastBench  /Game/HighlandLake
                  /Game/Canyon -- all saved, all shot
    measured gap  renders +0.19..+0.44 luma BRIGHTER than concepts; one
                  root cause: viewport exposure beats the PPV in shots

## RULINGS AND FINDINGS THE NEXT SESSION INHERITS

- **UE sun azimuth is compass-style (0=N, 90=E)** — calibrated by render.
- **Day-for-night is out of v0 scope**: intensity_lux is the solar constant
  (schema teaches: dim via exposure EV), and viewport exposure still wins.
- **`open_level` loads ZERO world-partition proxies** — reopened worlds
  shoot through `capture.py` (residency gate + load_actors); freshly
  created ones were only ever resident by construction.
- **MetaHumanGenerator's own init_unreal binds a global** that the
  create-landscape freshness gate rightly refuses — fresh launches use
  `-DisablePlugins=MetaHumanGenerator` (PluginManager.cpp:1587).
- Three auditor passes pre-run caught: a selftest wrong against its own
  rule, a coincidentally-correct probe origin, repo-relative args across a
  cwd boundary, an sRGB/linear double-encode. LESSONS has each.

## THE ORDER

    DONE  brief_loop + inject_lighting + concept2level, all audited
    DONE  four worlds imported, lit from their concepts, compared
    NEXT  shot exposure control (the one measured systematic gap)
    THEN  meshes (forge: city/crystal/bridges), water planes, tree scatter
    THEN  RPG mainline resumes: extent-derived FOV, church texturing
          (still BLOCKED per TEXTURING_SCOPE.md)

## CARRIED / GATED

Town re-placement (303→348) still GATED. `storey_m` 2.0. Church texturing
BLOCKED. Hero PARKED. The Gemini v1 pack is registered in ASSETS.md with
3 stamp-seed verdicts (1 usable / 1 soft / 1 rejected) and the luma-band
salvageability rule.


---

# CURRENT STATE — 2026-09-02 (dressed worlds: forests, water, displacement)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Editor OPEN on /Game/Canyon in editing state, deliberately** (Ryan is
mid-collaboration on the side project). Tree clean at close.

## THE SIDE PROJECT AFTER THE DRESSING PASS

MORNING_REPORT_20260901.md (three addenda) is the full account. The four
concept worlds now carry: **184,733 placed trees** (valley 71,205 / coast
113,528 / highland lakeshore belt / canyon sparse rim scrub), **v0 water**
(M_SideWater + label-keyed planes: highland lake, coast west-shelf sea),
**Nanite displacement** on the dressed worlds, and game-view shots. Locked
frames: crystal_valley_dressed_i2, coast_dressed_i3, highland_dressed_i3,
canyon_render_i2. Sheet + metrics in `_verify/20260901_overnight/`.

## RULES THE DRESSING PASS BOUGHT

- **Residency is per-shot law**: open_level AND heavy passes (foliage
  save, nanite) leave/put world-partition cells unloaded; every shot on a
  reopened or heavily-worked world goes through capture.py's load_actors
  first. A water plane pinned is_spatially_loaded=False survives when the
  terrain does not — that contrast IS the diagnostic.
- **A species band must intersect the LAYER carrying weight there**:
  canyon saplings 340-520 m against a Grass layer capped at 340 placed
  ZERO; re-keyed to the plateau slot.
- **set_static_mesh returns False on a no-op** against a static component;
  the update path guards it.
- **Translucent blend silently kills roughness at the shading-model
  level** — the audit caught it pre-run; TLM surface-per-pixel is the fix.
- **Dead shot queue** (channel alive, frames never landing) is a new
  editor failure class, distinct from the post-frame wedge; cured by a
  cycle. Logged, unresolved at root.

## OPEN / NEXT (side project)

    exposure     one more layer beats the PPV even in game view -- OPEN
    landmarks    forge REFUSED the 715 px single view (floor 800);
                 waiting on 1024+ square regenerations from Ryan
    coast        ocean floor carved ABOVE the cove; recarve re-keys 113k
                 trees -- decide before more coast work
    then         rivers, rock scatter, city/kit meshes into frame

## RPG MAINLINE (unchanged, parked behind the side project)

Town re-placement GATED, church texturing BLOCKED per TEXTURING_SCOPE.md,
hero PARKED, extent-derived FOV authorized-not-started.

# CURRENT STATE — 2026-09-02b (settlements placed, exposure calibrated where it responds)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Editor OPEN on /Game/CoastBench2, editing state, deliberately.** Tree clean.

## SINCE THE LAST BLOCK (continuation authority, MORNING_REPORT addenda 4-5 + commits)

- **The coast recarve landed**: brief_loop's third rule (MIN-too-high at
  anchor floor -> amplitude) converged the ocean 96 -> 16.7 m; the world
  rebuilt as /Game/CoastBench2 (v1 is history), 120,331 trees replaced,
  sea plane at its TRUE 14 m under the 27-43 m cove. Tag: pre-coast-recarve.
- **Exposure calibrated where it responds**: EV_new = EV_old -
  log2(render/concept luma) closed coast at -0.017 and crystal at +0.112.
  Canyon + highland show ZERO EV response with a verified-correct PPV
  (read_exposure: one volume, manual, overridden) — the stack's last layer
  discriminates BETWEEN WORLDS; parked with measurements.
- **BOTH CONCEPT SETTLEMENTS ARE PLACED**: the 196-building ringed city in
  the crystal valley (869 volumes, p50 0.23 cm trace grounding) and the
  84-building harbor on the recarved coast (p90 22.6 cm). R-CITY payload,
  dry-run first, both saved. crystal_city_close.png is the frame.
- A wrong-level render happened DESPITE every gate firing, because an
  ad-hoc driver ignored refusals — LESSONS 2026-09-02; multi-leg loops
  fail-stop per leg now. An editor with MainWindowHandle=0 ignores
  CloseMainWindow; killed under full R-EDITOR-CLOSE authorization.

## OPEN / NEXT (side project)

    landmarks    forge blocked on 1024+ square regenerations from Ryan
    exposure     the per-world nonresponse mechanism — needs its own session
    rivers       valley channel water strip (v0 plane), then splines
    rocks        R12 talus pass on the cliff bases
    extraction   the friends'-tool repo: everything proven here is the list

## RPG MAINLINE (unchanged)

Town re-placement GATED; church texturing BLOCKED; hero PARKED.


---

# CURRENT STATE — 2026-09-03 (the standalone forge exists: forge_tool/, first world forged) — **SUPERSEDED by the 2026-09-03b block.**

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a source for a decision.

**Editor CLOSED (or held by the T0 dist run if it is still going).**

## SINCE THE LAST BLOCK (operator directive: build the standalone forge)

- **`forge_tool/` is the standalone tool**, per the ruled architecture
  (in-repo package, vendor-by-copy): brief_author (claude-opus-5 vision
  -> gated layout; measured lighting INJECTED, never authored),
  check_brief (reuses brief_loop validators; 19/19 three-direction
  tests), assemble_recipe, emit_project (trimmed plugin COMPILES clean),
  cli (fail-stop per leg), package (311 hash-pinned files, Fab hash
  gate, pre-emitted UE project skeleton). Renamed forge->forge_tool
  after colliding with scripts/forge.py.
- **/Game/ForgeWorld is the first forged world**: keyless layout for the
  dusk-highland concept -> acceptance PASS iteration 1 (lake 40.8 m
  slope 0.5°, village plateau 249.9 m slope 0.6°, peaks 615.8 m) ->
  full editor phase -> water plane at 41.5 m -> the lake-under-massif
  dusk render (forge_runs/duskhighland/renders/duskhighland.png).
- **Licensing solved by construction**: recipes/forge_stamps_catalogue
  = 2 operator seeds + 7 CC0 maps NORMALIZED at adoption + 2 synthetics
  (flat_pad, mesa); spire_peaks stays out per the recorded survey.
  TERRAIN->STAMP is a RANGE conversion (LESSONS); MAX blend is the
  flatten-on-slope primitive (a MIN carve cannot rule ground below its
  anchor; an ADD mesa lifts the slope unchanged).
- Defects fixed at class: make_alpine_terrain aux maps now follow
  --output stem (was clobbering alpine_*); __LL__ is ue_exec's MARKER,
  never a --set parameter; anthropic 1.3.0 recorded in R0.

## OPEN / NEXT

    T0          PASSED (addendum 6). SECOND WORLD coastforge forged
                under per-run biome identity; fidelity loop CONVERGED
                -0.010 EV in 2 slope-corrected iterations (addendum 7);
                dist 0.1.1 packages it all. MAX judge rule + frustum
                sightline gate live and calibrated.
    T1          brief_author live vision call needs ANTHROPIC_API_KEY
                (none on this machine) — the one untested leg
    scout       on a MAX geometry refusal, probe a ring for the nearest
                band-satisfying site and relocate (done by hand twice
                on coastforge; should be the judge's next capability)
    ev-probe    CLOSED: highland -3.862 EV, canyon -4.349 EV response
                to -5.00 pushes — the parked "zero response" was
                confounded comparisons; no mystery mechanism exists
                (LESSONS 2026-09-03)
    dressing    forge v1 ships terrain+material+lighting+water only —
                foliage/city need a shippable asset base

## RPG MAINLINE (unchanged)

Town re-placement GATED; church texturing BLOCKED; hero PARKED.
Side-project extras (rivers, talus, exposure mechanism) as before.


---

# CURRENT STATE — 2026-09-09 (3rd GPU crash, IN THE BUILD; world still mixed)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a decision source.

**All processes STOPPED.** Tree clean. Tags `pre-hlod-full-build-20260908`,
`pre-hlod-rebuild-20260908`.

## ⛔ BLOCKED: the rebuild has never finished. 3 builds, 0 completions.

Build 3 died at **376 of 2,267**, 78 min:

    DXGI_ERROR_DRIVER_INTERNAL_ERROR
    Adapter->CreateReservedResource(...) FAILED
    Local Used 9,899 of 15,235 MB (65%)   DRED: No PageFault data
    in flight: [377/2267] ..._Merged/..._Instanced_L0_X-9_Y-9

**A DIFFERENT FAULT from the two editor crashes** (DEVICE_HUNG + page fault on
an HLOD mesh at 82% VRAM, RT active). This one has RT already OFF on its output,
a different reason string, different failing call, no page fault, lower VRAM.
**The RT finding does not explain it. No cause named.** `CreateReservedResource`
is the tiled/sparse path a voxel grid uses and the crash was in a MERGED cell —
an association, not a mechanism.

## THE WORLD IS MIXED, which is the real blocker

    > 5 MB   705 packages   old MeshMerge, ~329k tris
    < 3 MB  1473 packages   1,205 Instancing + ~320 rebuilt at 4,000 tris

**~705 of 1,025 Merged cells are still the geometry that crashed the editor
twice.** Phases B/C/D/E CANNOT start: opening with RT on re-runs a failed
experiment on a 69%-unchanged world.

No damage: 2,267 packages, 9.71 GB, 0 zero-length, 0 short, last write 3 s
before the crash.

## PROVEN, unaffected

    one cell   3,988 tris, bounds non-zero, mesh RT FALSE,
               1,455,802 B (was 13,959,833)
    MeshMerge cannot decimate; accuracy is METRES (1.5 not 150);
    -noxgecontroller mandatory

**Pace like-for-like: 5.06/min at 1.0 vs 5.62 at 1.5 = 1.11x.** A 3.4x cut in
voxel count bought 11% of time; R-HLOD 08g's cube-law prediction is WRONG and
corrected there.

## NEEDS A RULING — three options, not equivalent

    a  restart MeshApproximate, ~7 h, gamble on the next allocation
    b  MeshSimplify -- a DECIMATOR, no reserved-resource path, but
       ScreenSize/VoxelSize not a triangle target, so the budget must be
       re-expressed. UNTESTED.
    c  BATCH: -BuildHLODs WITHOUT -RebuildHLODs skips completed cells, so the
       376 done are free and a fault costs one batch, not the run

**(c) is cheapest and the only one not betting the run on one allocation.**
Evidence: LESSONS 2026-09-08i.

## OPEN

    Q6  editor idles this world at 8.2 cores, unexplained
    Q7  dolly crosses a shadow boundary
    NEW 3 GPU faults, 2 signatures, none explained

## NOT DONE

    3 stations + truth frame + featureless_fraction   BLOCKED
    DDC fill, Phase E (E1-E4)                         BLOCKED on Phase A
    filter-repo                                       not attempted

## RPG MAINLINE

town GATED, church BLOCKED, hero PARKED

---

# CURRENT STATE — 2026-09-07 (PHASE A DONE — the world is UNIFORM)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a decision source.

**All processes STOPPED.** Tree clean. Tag `pre-hlod-batched-rebuild-20260909`.

## ✅ THE HLOD REBUILD IS FINISHED — 12 shards, ~13.5 h

    2,267 packages    1,225 Instancing + 1,042 MeshApproximate
    MeshMerge(1)      ZERO        packages over 5 MB   ZERO
    bytes             9.71 GiB -> 1.47 GiB   (8.24 GiB given back)

Verified by `scripts/hlod_report_census.py`, reading each cell's OWN build
report. **Package size and triangle count BOTH misclassify staleness** and both
were in use before today (LESSONS 2026-09-09).

## THE PROCEDURE — locked in R-HLOD 09b

Manifest sharding, one fresh process per shard, via
`scripts/hlod_build_batched.py`. **`-RebuildHLODs` IS MANDATORY** — without it
the hash policy REJECTED 77 cells stale by the very setting that changed;
LESSONS 2026-09-08i's "skips completed cells" was FALSE.

## THE 4th GPU FAULT — memory pressure is ELIMINATED

Shard 9 crashed twice, same position (its LAST cell), fresh process each time,
at **9,359 MB then 7,403 MB** of the same UE field. A threshold firing at both
is not a threshold. The cell the log named built fine 1.9 s earlier — a
progress line reports what BEGAN. **No cause named.** Cost: one hour, not the
run.

## OPEN

    Q6  editor idles this world at 8.2 cores, unexplained
    Q7  dolly crosses a shadow boundary
    Q9  why batch 9's shard and no other. Cheapest test: reorder its manifest
        section so a different cell is last. POSITION -> teardown, CELL -> content
    Q10 why `-BuildHLODs` alone rejects demonstrably stale cells. Lead in
        LESSONS 2026-09-09 fails its own prediction; do not trust it
    Q11 2 SceneCapture2D actors hold a dead TextureRenderTarget. Harmless,
        but a real load error will hide behind them

## ✅ THE RT-ON OPEN SURVIVES — the 08h hang does not reproduce

    177+ min, responding, VRAM 6,815 MiB, ZERO crash lines
    was: DEVICE_HUNG at 12,434 MiB, page fault on an HLOD
         _Merged_ buffer, breadcrumb RayTracingGeometry -- TWICE

RT read back from the engine, not the ini: `Ray tracing is enabled (dynamic)`,
`r.Lumen.HardwareRayTracing:1`. Level confirmed loaded. Single variable — the
renderer config is unchanged since 08h, only the geometry differs. **Not a
proven cause; a non-reproduction.**

**⚠ EDITOR STILL RUNNING** on `/Game/Alpine8K`. Close via R-EDITOR-CLOSE.

## NEXT — NEEDS RYAN

**Phases B/C/D/E of the overnight prompt are NOT in the repo** — the only trace
is CURRENT STATE's old line "DDC fill, Phase E (E1-E4)". Their definitions are
needed before they can run. Nothing else blocks them.

Evidence: `_verify/hlod/20260909_batched/` (logs, `batches.json`, manifest).

## RPG MAINLINE

town GATED, church BLOCKED, hero PARKED


# CURRENT STATE — 2026-09-07 (PHASE A DONE — the world is UNIFORM)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a decision source.

**All processes STOPPED.** Tree clean. Tag `pre-hlod-batched-rebuild-20260909`.

## ✅ THE HLOD REBUILD IS FINISHED — 12 shards, 4 builds, ~13.5 h

    2,267 packages    1,225 Instancing + 1,042 MeshApproximate
    MeshMerge(1)      ZERO        packages over 5 MB   ZERO
    bytes             9.71 GiB -> 1.47 GiB   (8.24 GiB given back)

Verified by `scripts/hlod_report_census.py`, which reads each cell's OWN saved
build report. **Package size and triangle count BOTH misclassify staleness**
and were both in use before today (LESSONS 2026-09-09).

## THE PROCEDURE — locked in R-HLOD, amended 2026-09-09

    -SetupHLODs -ReportOnly -BuildManifest=<abs>.ini -BuilderCount=12
    then per shard, FRESH process:
    -BuildHLODs -RebuildHLODs -BuildManifest=<same> -BuilderIdx=i

`scripts/hlod_build_batched.py` drives it. **`-RebuildHLODs` IS MANDATORY**:
without it the hash policy REJECTED 77 cells that were stale by the very
setting that changed. LESSONS 2026-09-08i's "skips completed cells" was FALSE.

## THE 4th GPU FAULT — memory pressure is ELIMINATED

Batch 9 crashed twice: same shard, same position (its LAST cell), fresh process
each time, at **9,359 MB then 7,403 MB** of the same UE field. A threshold that
fires at both is not a threshold. The cell the log named built fine 1.9 s
before the crash — a progress line reports what BEGAN. **No cause named.**
Cost: one hour, not the run. That is the batching ruling paying for itself.

## OPEN

    Q6  editor idles this world at 8.2 cores, unexplained
    Q7  dolly crosses a shadow boundary
    Q9  why batch 9's shard and no other. Cheapest test: reorder its manifest
        section so a different cell is last. POSITION -> teardown, CELL -> content
    Q10 why `-BuildHLODs` alone rejects demonstrably stale cells. Lead in
        LESSONS 2026-09-09 fails its own prediction; do not trust it

## NEXT — NEEDS RYAN

**Phases B/C/D/E of the overnight prompt are NOT in the repo** — the only trace
is CURRENT STATE's old line "DDC fill, Phase E (E1-E4)". Their definitions are
needed before they can run. **Phase A no longer blocks them**, and opening with
RT on is now a different experiment: the geometry that hung the editor twice is
gone from all 1,042 Merged cells.

Evidence: `_verify/hlod/20260909_batched/` — 14 logs, `batches.json`, the
manifest, two report censuses.

## RPG MAINLINE

town GATED, church BLOCKED, hero PARKED


# CURRENT STATE — 2026-09-08 (E1–E3 DONE, E4 PARTIAL, CENSUS CLOSED)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`. History
> is `docs/archive/current_state_history.md` — ⛔ never a decision source.

**All processes STOPPED.** Tree clean; `main` current.

## PHASE E

    E1 culls        DONE  219,659 instances byte-identical at seed. Ground
                          cover keeps its authored cull -- `system: grass`,
                          so the cull is a LandscapeGrassType property.
    E2 silhouette   DONE  geometry HOLDS at every switch. NO ScreenSize
                          change. 6-tri LODs are alpha-masked billboards.
    E3 perf         DONE  the perf law's RED is the EDITOR'S 60 Hz CAP
    E4 dolly        PARTIAL -- verdict negative, re-heading not done

**E3:** editor FrameTime p50 is 16.67 ms at every station — a cap, not a cost
— and GameThreadTime tracks it, not the content. Standalone: plaza Game 3.98
vs editor 14.00. `perf_budgets.json` UNTOUCHED. **Rests on ONE measurement**;
two reproductions never loaded (shaders still compiling — I emptied
`C:/UnrealDDC` for 92 GB). Retry `--settle 900` warm.
Evidence `_verify/perf/standalone_2026-09-07/`.
**E4:** the dolly does NOT stay sunlit — lit share 41.1% → 17.7% over 4.2 m,
confirmed by eye. **Not scored**, per ruling.
`scripts/pick_sunlit_heading.py` picks a replacement by MEASUREMENT (the
azimuth→yaw convention has caused roll-for-pitch three times, and
`sun_exposure.py` is blind to canopy shadow). **It has not run** — see Q13.

## CENSUS — CLOSED, 3 of 4 projects

`research/census/CENSUS_ROLLUP.json`; every value carries a STATUS.
Samples restored, except Valley's shipped `.pdb` (deleted by my build) and
`AncientGameEditor.target` (overwritten) — both regenerable.

## OPEN

    Q6  editor idles this world at 8.2 cores
    Q7  dolly crosses a shadow boundary -- E4 MEASURED it (see above)
    Q9  why batch 9's shard, no other
    Q10 why `-BuildHLODs` alone rejects stale cells
    Q11 survey shots fail on 3 of 4 samples, two shapes, cause unknown --
        `research/census/shots/SURVEY_STATUS.md`
    Q12 7 InstancedFoliageActors absent from PIE while in range
    Q13 a LOADED editor that binds NO remote port and will not close cleanly.
        Two stale UDP sockets on 6766 held by DEAD pids, left by my own
        `Stop-Process` kills; clearing them did not fix it. Cause unknown.
        E4's re-heading was STOPPED rather than started on it.

## NEXT — NEEDS RYAN

**A sunlit heading is a DECISION** — the probe measures, it does not choose.

**The perf-budget ruling** — budgets ratified against a 60 Hz cap. Three
options in BACKLOG, none taken.

**Ground cover needs a REPRESENTATION below its cull**: Meadow's silhouette
boundary is 123.8 m, inside the 256 m streaming range.

Phase C send-back delivered: `research/brief1/for_research/`.

## RPG MAINLINE

town GATED, church BLOCKED, hero PARKED


# CURRENT STATE — 2026-09-09 (PHASE E COMPLETE, E1–E4 ALL DONE)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`.
> History is `docs/archive/current_state_history.md` — ⛔ never a source.

**All processes STOPPED.** 0 editors, port 6766 clean, tree clean.

## PHASE E — CLOSED

    E1 culls        DONE  219,659 instances byte-identical. Ground cover
                          keeps its authored cull -- `system: grass`.
    E2 silhouette   DONE  geometry HOLDS at every switch. NO ScreenSize
                          change. 6-tri LODs are alpha-masked billboards.
    E3 perf         DONE  the perf law's RED is the EDITOR'S 60 Hz CAP
    E4 dolly        DONE  stays sunlit on yaw -67.5 (RULED)

**E3 rests on ONE measurement.** Editor FrameTime p50 is 16.67 ms at every
station — a cap, not a cost. `perf_budgets.json` UNTOUCHED. Reproductions
never loaded; retry `--settle 900` warm.
Evidence `_verify/perf/standalone_2026-09-07/`.

**E4:** first 0.7545 → last 0.6063, floor 0.5961, −19.6% (was −57% on the
station's own −12.8). NOT SCORED. 90 frames, range complete, count stable, no
RT-PSO fallback in the frame window.
Sidecar `_verify/bench/2026-09-09/dolly_sunlit_yaw-67.5.json`.

**The heading override does NOT touch the level** — the sequence keys
Rotation.X/Y/Z, so `Bench_near_ground` still reads −2.0 / −12.8 / 0.0,
verified from the engine. `Bench_Dolly` (6 s, ratified) untouched; the variant
is `Bench_Dolly_Sunlit`.

## BASELINE vs CAPTURE — OPEN

    probe (editor stills)  0.646 -> 0.739 -> 0.714   RISING
    dolly (PIE via MRQ)    0.755 -> 0.709 -> 0.606   FALLING

Systematic (±0.11), far outside this session's ±0.03 drift. Likely **Q12** —
canopy present in the editor missing in PIE. **HYPOTHESIS, not measured.**
Rule now in R-BENCHDOLLY: a baseline is a baseline for ITS OWN INSTRUMENT.

## OPEN

    Q6  editor idles this world at 8.2 cores
    Q9  why batch 9's shard, no other
    Q10 why `-BuildHLODs` alone rejects stale cells
    Q11 survey shots fail on 3 of 4 samples -- SURVEY_STATUS.md
    Q12 7 InstancedFoliageActors absent from PIE while in range --
        now ALSO the leading explanation for the E4 baseline divergence
    Q13 DID NOT REPRODUCE: the editor bound the port, answered, and closed
        on the FIRST CloseMainWindow, no stale socket. Cause still unknown.
    Q14 cold-DDC build never falls silent -- rate plateaued at ~65
        lines/30 s. Gate on a re-shot MEASUREMENT, not on log silence.

**Q7 is CLOSED** — E4 measured the shadow boundary and re-headed past it.

## NEXT — NEEDS RYAN

**The perf-budget ruling** — budgets ratified against a 60 Hz cap. Three
options in BACKLOG, none taken.

**Ground cover needs a REPRESENTATION below its cull**: Meadow's silhouette
boundary is 123.8 m, inside the 256 m streaming range.

Phase C send-back delivered: `research/brief1/for_research/`.

## RPG MAINLINE

town GATED, church BLOCKED, hero PARKED


---
# CURRENT STATE — 2026-09-11 (BRIEF 3 T2: EIGHT DERIVED LAYERS, 3/3 PASS)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`.
> History is `docs/archive/current_state_history.md` — ⛔ never a source.

**Editor closed gracefully; zero processes; tree clean. Brief 3 T0–T2
complete.**

## THE RULINGS, DONE

    1 range/culls  R-RANGE 512; Brief 1's detail threshold follows.
                   perception.cull_ceiling POINTS at the streaming block,
                   so culls RE-DERIVE by construction: Conifer 1148.6 /
                   ConiferPine 875.0 / SpruceSub 743.5 -> 512 m, applied
                   to the FT_ assets, committed. Brief 5 experiment
                   registered (treeline's rise = the 2 km INSTANCED layer)
    2 WB           3751 -> 3550 K: card R/G 1.0230, B/G 1.0000, both in
                   0.97-1.03. R-GRADE LOCKED. The ~45%-per-step
                   von-Kries finding logged at both altitudes
    3 Task 2       eight derived layers live; three acceptances PASS

## TASK 2 — R-LAYERS

Weights DERIVED from heightmap + deposition + PLACED foliage, precedence
normalised to sum 1, nothing painted. Coverage: rock 42.30, meadow
24.65, scree 11.97, forest_floor 10.63, snow 9.92, gravel 0.52;
wet_shore/dirt_path DECLARED ZERO with reasons. Material v1.25: the
forest-floor tint is driven by the weightmap ALPHA — the canopy-derived
weight — replacing the height band ("trees live at these altitudes" ->
"a tree stands HERE"). RGBA uncompressed; material rebuilt, assigned.

    forest_floor   under canopy 0.9985, open 0.0007        PASS
    snow asymmetry shaded 0.4116 vs lit 0.0000 (>= 0.2)    PASS
    height blend   mushy 0.2131 vs linear 0.5551           PASS

## TWO INSTRUMENT DEFECTS CAUGHT (both altitudes)

**The aspect axis was bound to a map edge, not the sun** (LESSONS
2026-09-11b): `cos(aspect)`, "0 = +Y north", biased snow onto the LIT
flanks at azimuth 285. The selftest passed throughout and was right to —
it verifies the arithmetic it is given, never the premise. Fixed by
derivation; the selftest gained "flip the sun, flip the flank".

**The p90 gradient could not see the blend** — EXACTLY sqrt(2)/2 for
both (single-texel-step ceiling). Replaced by the mushy fraction, the
saturated number kept beside it as NO VERDICT.

Also: check_derived_culls' staleness check sat after a `continue` —
dead for the class it promised; it then found three stale plans.

## OPEN

    Per-species crown radii (SpruceSapling uses the conifer's 3.07 m)
    Ground-cover gap WIDENED to 50-512 m (representation BACKLOG'd)
    Clouds 0.1; Brief 2c; the 0-dirty close wedge — all BACKLOG'd
    Q6/Q9/Q10/Q11 unchanged

## NEXT

Brief 3 T3: six scanned surfaces at the texel-derived tiles, macro
variation, tiling by depth bin. Task 2's recipe R-locks once the
snow-aspect direction is confirmed against a render.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED


---
# CURRENT STATE — 2026-09-11b (R-LAYERS LOCKED; EXPOSURE RE-DERIVED; TASK 3 REFUSES)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`.
> History is `docs/archive/current_state_history.md` — ⛔ never a source.

**Editor closed cleanly; zero processes; tree clean. Four rulings
executed.**

## 1 — R-LAYERS LOCKED, on three strands

    DIRECTION    frac(snow>0.5) SHADED 0.2679 vs LIT 0.0067 -- 40x
                 against a DERIVED floor of 4x
    ORIENTATION  vs the RENDER: ours IoU 0.7727 / 0.4473 / 0.1105 /
                 0.0000; margin 0.3254 over a per-run required 0.2057
    MATERIAL     same altitude + flank class, snow renders brighter
                 than bare 5/5 bins. SHADED only

**The ruled top-down at (0,0,900000) was NON-PROBATIVE** — luma std
0.0334 vs a 0.05 floor. Camera re-DERIVED (clearance 1000 m, centre
maximising the scarcer flank): 365,717 vs 364,936 band texels, std
0.2134. Both kept.

## 2 — EXPOSURE RE-DERIVED FROM THE CARD (R-GREYCARD)

    comp_ev  -1.923 -> -3.5173  requested -1.5943 EV
    card     0.54349 -> 0.26489 delivered -1.0369 EV = 65.0%
    residual +0.5574 EV, ABOVE the [0.162, 0.198] band. NOT tuned.
    next     -4.0747 (formula) or -4.3748 (efficiency-corrected)

**Only near_ground's card qualifies** — vista's reads FAIL (wb_B 1.2352,
std 0.0669): it stands on a SHADED flank, sky-lit. 65% matches the WB
chain's 68%/40%, so the shortfall is the TONEMAP's, not von Kries's.
⚠ 0.18 is applied POST-tonemap; whether that is the right target needs a
ruling. Rule-12 gap closed: apply_lighting reads exposure back and the
host COMPARES it (AEM_MANUAL, -3.5173, min/max 1.0 pinned).

## 3 — TASK 3: TILE DERIVED AND APPLIED; THE TABLE REFUSES

tiling_m **5.03 m** derived (4096 / 814.9 texels-per-m), all 3 layers,
macro 188.0 = 37.4x. Material rebuilt, saved, 257 actors verified on
M_Alpine8K. 5.8 HAS Texture_Bombing / TextureBomb_SingleSample (no
hex); not integrated. **Every tiling cell is NO VERDICT**: no station
sees clean ground at 30-100 / 100-300 m, and where a crop exists the
peak is PINNED at the search window's edge (205.4 vs a 205.1 floor) —
the michelson figures would have read FAIL twice, as artefacts of crop
contrast. A 5.03 m tile enters the 1-8 cpd band only at 288-2306 m.

## BLOCKED / OPEN

    Task 3 step 2: needle litter + wet pebbles NOT ON DISK; and the
      material has 3 layers, so scree/forest_floor/wet_shore have
      nothing to bind to (Task 2 folded scree into rock)
    Task 3 needs a PURPOSE-DERIVED ground-only station; albedo
      variation NO VERDICT (denominator is ground, not meadow)
    Exposure 2nd step; the 0.18-post-tonemap target
    Crown radii; ground-cover gap 50-512 m; clouds 0.1; 2c
    Q6/Q9/Q10/Q11

## NEXT — rule the exposure second step and the 0.18 target; Task 3
then needs its station derived and two surfaces acquired.
## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED


---
# CURRENT STATE — 2026-09-11c (SCENE-LINEAR CARD; CHAIN IS A POWER LAW)

> **⭐ THE ONLY `# CURRENT STATE` BLOCK**, enforced by `check_docs.py`.
> History is `docs/archive/current_state_history.md` — ⛔ never a source.

**Editor closed clean; zero processes; tree clean.**

## 1 — SCENE-LINEAR CARD; "EXPECT EXACT" DID NOT HOLD

`bDisableToneCurve` is on the COLOUR SETTING, not the deferred pass
(source-verified); `--linear` sets it and reads it back. Reader OpenEXR
3.3.2, in `docs/environment.md`.

    requested EXACTLY -1.0000 EV -> delivered -0.7266
    requested         -0.4453 EV -> delivered -0.3276
    a POWER LAW, slope 0.731, NOT the tonemap alone: disabling it
    moved the card only 8% (0.26489 -> 0.24480)

Solved, not iterated — slope inverted, two extrapolations agreeing to
0.006 EV. **comp_ev -4.1268 -> card 0.180072 PASS.**

**R-GRADE's lock was taken on a compressed instrument.** At 3550 K the
tonemapped card read R/G 1.0230 (in band); on the linear pass the same
grade reads **1.0549** (out). One Planck step -> **3481.9 K**: excess
ratio 1.0534 -> 1.0020, so TEMPERATURE converged. Left is the TINT axis
(~3% green); `white_tint` stays 0 — it has no measured slope.

## 2 — PERF GATE AND PLAN FRESHNESS

check_perf selects by DECLARED RANGE matching the world's (from the
WORLD recipe, not perf_budgets), never mtime. **RED cleared with no
number change.** Plan freshness 22 -> 18: the four alpine_8k foliage
plans annotated EXPECTED, bound to exact hash pairs, justified by
MEASUREMENT (parsed `instances` identical).

## 3 — Bench_ground DERIVED; ITS PREDICTION FAILED

Actor placed, sequence created, captured, residency missing 0. Predicted
**405 / 375 rows**; render gives **55 / 0** — depth p50 9.04 m, 85%
inside 30 m, zero sky. Three causes (LESSONS 2026-09-11l): the scoring
grid's quantisation was the whole margin; the raymarch models trees but
NOT the grass that fills a standing meadow view; and a uniform rise
COMPRESSES distance where only a concave profile spreads it — required
of the fixture, not the search.

**The tiling table is still NO VERDICT** — the station sees only NEAR
ground.

## 4 — TEXTURES PENDING

The sidecar now states the layer set is on PLACEHOLDERS — the
three bound layers and the five derived classes with no surface at all.
Ryan's six 4K scans are pending.

## OPEN

    RYAN'S MESSAGE TRUNCATED — exposure range 14.0 / safe -8, rest
      unread. No r.EyeAdaptation.Cache in 5.8; the real names are
      CachedLightingPreExposure / PreExposureOverride. PRE-EXPOSURE IS A
      LIVE CANDIDATE for the 0.731 slope. NOT ACTED ON
    Bench_ground: re-derive with grass modelled, concavity REQUIRED
    white_tint needs a measured slope before stepping
    Task 3 textures; crown radii; ground-cover gap 50-512 m
    Clouds 0.1; 2c; Q6/Q9/Q10/Q11

## NEXT — the truncated ruling, then Bench_ground v2.

## RPG MAINLINE — town GATED, church BLOCKED, hero PARKED
