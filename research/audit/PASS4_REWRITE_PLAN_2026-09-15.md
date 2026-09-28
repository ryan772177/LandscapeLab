# Audit Pass 4 — the rewrite plan (2026-09-15)
Input: history_diffs.txt (544 commits, 07-27 → 09-13; LESSONS.md ×332, RECIPES.md ×253, CLAUDE.md ×249, STATE.md ×7,
registers ×10), desk_core (current files), the supersession rulings in AUDIT.md and the closure list.
Doc basis: this pass changes no engine lever. Every engine value it carries into the CURRENT VALUES table (§3) was
verified in Pass 1 (Doc) or against the live enumeration (Live); the basis is repeated per row.

## 1. What the history says (measured, not assumed)
| file | commits | content lines added | content lines removed and never restored | reading |
|---|---|---|---|---|
| LESSONS.md | 332 | 37,087 | **6** (four 08-08 capture lines, two 08-18 headings) + TOC-header regenerations | **append-only HELD.** Nothing true was deleted. The problem is accumulation: 1,840 headings / 618 dated entries that Claude Code greps, of which a measurable subset now state values that later rulings overturned. |
| RECIPES.md | 253 | 16,724 | 235 (the 08-02 restructure) + 100 TOC rows + ~280 scattered | **effectively append-only**; the 08-02 loss was the file's own rewrite from v0; the rest are TOC regenerations and in-place corrections that were re-added reworded. |
| CLAUDE.md | 249 | 10,816 | 10,396 verbatim (mostly reworded, not lost) | **process law, rewritten constantly**: 324 current lines, oldest from 08-02, 97 lines from 08-29, 56 from 09-01. Carries NO engine values (0 hits in the supersession scan). It does not mislead; it fails to say why (23 of 27 rules have no pointer). |
| STATE.md | 7 | 423 | 354 | the one file that lied (repaired in A-1). |
Conclusion: the harmful history is not deleted truth; it is **superseded truth still presented as current**. The rewrite therefore TAGS, it does not delete, and it puts the current value ahead of the history in grep order.

## 2. Mechanism — three edits, no deletions
1. **STATUS tags.** Every LESSONS/RECIPES entry gets one line directly under its heading:
   `> STATUS: CURRENT` | `> STATUS: SUPERSEDED-BY <ruling id> — <one line: what is current now>` | `> STATUS: HISTORY — narrative; values inside are not in force` | `> STATUS: WRONG — <what was wrong, pointer>`.
   The TOC generator adds a STATUS column so `grep` on the TOC shows the state before the body is read.
2. **CURRENT VALUES table** at the top of RECIPES.md (§3 below): one screen, every in-force number, its ruling id, its read-back artefact, its doc basis. It is regenerated from recipes/alpine_8k.json + benchmark.json by a script (`current_values.py`, selftest: every row's value equals the recipe/profile value) so it cannot drift.
3. **Rule pointers in CLAUDE.md.** Each standing rule gets a trailing `— why: <LESSONS entry id | commit | doc URL>`. The 23 unpointed rules are 08-02/08-03/08-30/09-05 vintage; their motivating LESSONS entries carry the same dates.

## 3. CURRENT VALUES (seed for the generated table; basis per row)
| value | in force | ruling | read-back | basis |
|---|---|---|---|---|
| judgement camera | 3840×2160 @ 90° H; 1440p floor | standing | benchmark.json target/dev | Ruling |
| loading range | 512 m | R-RANGE | apply_streaming_range read-back | Project |
| metering | Manual, physical camera off | R-METER | PPV read-back | Doc (Manual = fixed exposure) |
| compensation_ev | −14.2571 | A-6 R-WB2x2 | PPI0 card 0.1805 | Project |
| render warm-up | 40 frames ON; engine 300 | R-METER / warmup_settle | sidecar | Doc (engine warm-up renders nothing; render warm-up builds history) |
| white_temp_k / white_tint | 3438.6 / −0.0248 | A-6 R-WB2x2 | card R/G 1.0014, B/G 0.998 | Doc (WB mode, tint axis) + Project |
| contrast | 0.95 effective (w; xyz=1) | B3.13 | product read-back | Project (shader xyz·w) |
| sky light | white (1,1,1), 1.0, real-time capture, lower hemisphere black | R-SKYCOLOR, Brief 2 | FColor 255,255,255 | Doc (real-time capture time-sliced; requires Sky Atmosphere) + census |
| sun | 130,000 lux, 5200 K, 12° / 285° | Brief 2 | 8/8 read-backs (A-4) | Doc (lux, use_temperature) |
| Mie / Rayleigh | 0.01 g0.8 / 0.0331 | Brief 2 | read-back | Doc |
| fog | 0.00416, start 0, half-height 517.49 m → falloff 0.0193; inscattering black | Brief 2 | fog_state | Doc (Sky Atmosphere colours the fog when both black) |
| shade band | 2.065–2.998 @ 3438.6 K, floor D6000 (sun < 30°) | R-SHADEBAND | shade_reference.py | Ruling + literature |
| instruments | ppi0 (linear) / finalimage_linear / finalimage_look / truth (20 GO props) | R-INSTRUMENTS, S-12 | sidecar `instrument` field | Doc (Disable Tone Curve = post-process-pipeline linear) |
| look-instrument format | EXR 16-bit float; PNG viewing only | S-4 | config dump (A-5) | Doc (EXR output class) |
| tiling verdict instrument | player (temporal 8, TSR) | B3.20 | TASK3_RECORD | Doc (TSR temporal accumulation removes moiré) |
| tile sizes | Rock 1.80, Scree 2.00, ForestFloor 2.14, Snow/Grass 5.03 UNSTATED | R-TILE | material graph | Project |
| landscape HLOD | HLODTextureSize 4096, SPECIFIC_SIZE, 257/257; layers _Landscape/_FoliageApprox inert | R-HLODTEX, B3.21 | off-disk census | Project (ULandscapeHLODBuilder unconditional) |
| HLOD build | incremental; ≤96 cells/batch; one process | S-9, docs | run_report | Doc (incremental on source change; -SetupHLODs/-BuildHLODs) |
| dead cvars | r.LandscapeLODBias, r.TonemapperFilm, r.ExpandGamut, r.LocalExposure.*, r.Shadow.Virtual.Nanite.Enable, landscape.ForcedLOD, r.Wind.Enable, foliage.WindEnabled | P1-4/5 | cvars_5_8_live.txt | Live |
| runtime-ineffective | r.MaxAnisotropy (startup only) | AUDIT | UE-116243 | Doc |
| foliage | 217,102 trees (2,557 cleared); regeneration gated on planting-field contract + floor gate | ruled | — | Project |
| perf budget | GPU 1.2× standalone p90/zone; game 6.0 ms; frame 16.6 ms | R-PERFBUDGET | 9a561d07 | Ruling |

## 4. Supersession seed — 81 entries carrying overturned values (mechanical scan; CC reads each before tagging)
Tag rule: if the entry ITSELF records the later correction, tag HISTORY; if it states the old value as current, tag
SUPERSEDED-BY; if it states something later shown false, tag WRONG. "Task 3 09-13" hits are Rock051 mentions — HISTORY
unless the entry presents Rock051 as bound.
| file | line | heading | superseded by |
|---|---|---|---|
| LESSONS.md | L5707 | STATE, as of the end of the asset session | Task 3 09-13 |
| LESSONS.md | L6453 | Q6 — How does an `assumed` footprint get promoted? **THE PREMISE WAS | Task 3 09-13 |
| LESSONS.md | L7893 | The resolution was already on file | Task 3 09-13 |
| LESSONS.md | L7942 | 2026-08-03 — I MEASURED THE DISPLACEMENT MAPS AS FLAT. THEY ARE NOT. T | Task 3 09-13 |
| LESSONS.md | L8258 | 2026-08-03 — EVERY METRIC PICKED THE MOSS | Task 3 09-13 |
| LESSONS.md | L8319 | The honest outcome | Task 3 09-13 |
| LESSONS.md | L10401 | What was attempted | P1-4 (89df9c14) |
| LESSONS.md | L10413 | What happened | P1-4 (89df9c14) |
| LESSONS.md | L10441 | The rule | P1-4 (89df9c14) |
| LESSONS.md | L10499 | What this invalidates | P1-4 (89df9c14) |
| LESSONS.md | L11732 | 2026-08-06 — TRIPLANAR WAS BUILT, PROVEN CORRECT, AND THROWN AWAY ONE  | Task 3 09-13 |
| LESSONS.md | L12521 | 2026-08-08 — TRIPLANAR IS WIRED, AND THIS TIME IT WAS MEASURED ON THE  | Task 3 09-13 |
| LESSONS.md | L13688 | TIER 2 | Task 3 09-13 |
| LESSONS.md | L14486 | 2. I ASSERTED A CLAIM ABOUT PIXELS IN A GATE, AND IT WAS FALSE | Task 3 09-13 |
| LESSONS.md | L25695 | 2026-08-27b — I ASSERTED A LICENCE FROM MEMORY INSIDE THE FILE WHOSE J | Task 3 09-13 |
| LESSONS.md | L28538 | The assignment | B3.21 |
| LESSONS.md | L28638 | What survives, and what the next attempt must do differently | B3.21 |
| LESSONS.md | L28789 | The correction that matters most, because it inverts yesterday's cause | B3.21, R-RANGE |
| LESSONS.md | L28847 | The build ran, and made nothing | B3.21 |
| LESSONS.md | L31979 | WHAT HAPPENED | Brief 2 |
| LESSONS.md | L32162 | 2026-09-10f — THE RESIDENCY EXPECTATION WAS 2D AGAINST A 3D SPHERE | R-RANGE |
| LESSONS.md | L32193 | AUDIT LOG 2026-09-10c — Brief 3 groundwork audits | R-RANGE |
| LESSONS.md | L32562 | 2026-09-11i — THE SCENE-LINEAR PASS IS NOT LINEAR, AND THE TONEMAP WAS | B3.13, R-INSTRUMENTS |
| LESSONS.md | L32619 | 2026-09-11j — THE DISPLAY-REFERRED CARD WAS FLATTERING THE GRADE, AND  | A-6 R-WB2x2 |
| LESSONS.md | L32752 | OPEN | B3.13 |
| LESSONS.md | L32788 | 2026-09-11n — Q12 NARROWED BY READ-BACK: TWO OF THREE CANDIDATES ELIMI | P1-5 / V-3 |
| LESSONS.md | L32871 | 2026-09-11p — A READER THAT CANNOT TELL ZERO FROM ABSENT, FIXED AT THE | P1-5 / V-3 |
| LESSONS.md | L32957 | 2026-09-11r — THE RULED STATION FAILS ALL FOUR CHECKS, AND MY PREDICTO | R-INSTRUMENTS |
| LESSONS.md | L33059 | 2026-09-11t — 4b LANDS, AND A FRACTION MEASURED AGAINST THE WRONG POPU | Task 3 09-13 |
| LESSONS.md | L33247 | The measurement that accused six packs at once | Task 3 09-13 |
| LESSONS.md | L33697 | The measurement | A-6 R-WB2x2 |
| LESSONS.md | L33705 | Finding 1 — shadow_tint_B is largely a WHITE-BALANCE readout | R-SHADEBAND |
| LESSONS.md | L33728 | What follows | A-6 R-WB2x2, R-SHADEBAND |
| LESSONS.md | L33757 | The re-derivation | A-6 R-WB2x2, R-SHADEBAND |
| LESSONS.md | L33848 | The whole series, one variable each | A-6 R-WB2x2 |
| LESSONS.md | L33889 | Why the band could not be re-derived against our own content | R-SHADEBAND |
| LESSONS.md | L33902 | The defect, confirmed by two instruments that disagree | Task 3 09-13 |
| LESSONS.md | L33944 | What it is not | R-SHADEBAND |
| LESSONS.md | L34161 | 2. Q12: the compression survives every lever, so it is not adaptation | B3.13 |
| LESSONS.md | L34264 | 6. Two tile sizes broke a report that assumes one | R-T4 |
| LESSONS.md | L34322 | 2. Contrast is a factor and the composition is not a product | B3.13 |
| LESSONS.md | L34455 | 2. â­ CONTRAST IS `xyz * w`, SO 0.95 WAS 0.9025 | B3.13 |
| LESSONS.md | L34487 | 3. The residual is a GAMMA, and the pivot said so before any capture | B3.13 |
| LESSONS.md | L34514 | 4. R-INSTRUMENTS â€” and the shade band was in the wrong domain | R-SHADEBAND |
| LESSONS.md | L34601 | 2026-09-13d â€” THE PERIOD WAS THE WEIGHTMAP, AND THE "1.07 m" WAS MY  | B3.15/16 |
| LESSONS.md | L34603 | 1. A number I reported was an artefact of the search, not the world | B3.15/16 |
| LESSONS.md | L34673 | 4. The shade acceptance moves to the linear instrument, and needed no  | R-SHADEBAND |
| LESSONS.md | L34724 | 1. The question the last two sessions could not ask | B3.15/16 |
| LESSONS.md | L34731 | 2. Two estimators built, both REJECTED ON MEASUREMENT before the | B3.15/16 |
| LESSONS.md | L34880 | 3. The instrument that needed no mask at all | R-MEADOWALBEDO, R-T4 |
| LESSONS.md | L34946 | 1. The check nobody asked for | B3.17/B3.20 |
| RECIPES.md | L908 | R2 — Landscape material (LOCKED, UNPROVEN) | Task 3 09-13 |
| RECIPES.md | L1015 | EXACT VALUES | Task 3 09-13 |
| RECIPES.md | L1059 | RULING: five surfaces, three channels, via SUB-SURFACES | Task 3 09-13 |
| RECIPES.md | L1170 | Measured displacement ranges (they differ, and that is load-bearing) | Task 3 09-13 |
| RECIPES.md | L1187 | NOT resolved by this ruling — stated, not hidden | Task 3 09-13 |
| RECIPES.md | L1318 | REJECTED | Task 3 09-13 |
| RECIPES.md | L5830 | R-COLLISION-REBUILD — THE FLUSH DOES NOT WORK. "Flush" is the wrong op | P1-4 (89df9c14) |
| RECIPES.md | L6940 | WHAT THE DETAIL GAIN ACTUALLY IS — measured, and smaller than it sound | B3.15/16 |
| RECIPES.md | L15866 | The procedure | B3.21 |
| RECIPES.md | L15900 | Choosing the layer, since the world may already have a wrong one | B3.21 |
| RECIPES.md | L16024 | WHAT THIS WORLD REGISTERS, read back 2026-09-08 | B3.21 |
| RECIPES.md | L16033 | THE MEASUREMENT, single variable | B3.21 |
| RECIPES.md | L17791 | ⭐ LOCKED 2026-09-11b AT 3481.9 K — ON THE SCENE-LINEAR PASS | A-6 R-WB2x2 |
| RECIPES.md | L17839 | THE VALUES (recipes/alpine_8k.json `lighting.grade`) | B3.13 |
| RECIPES.md | L17872 | BRIEF 3 TASK 1 — THE CARD SETS THE WHITE POINT (2026-09-10) | B3.13 |
| RECIPES.md | L17906 | BRIEF 2b MEASURED (2026-09-10, sun 5200 K, WB 5200 by the rule) | R-SHADEBAND |
| RECIPES.md | L18393 | THE VALUES | R-RANGE |
| RECIPES.md | L18402 | THE PERF GATE AT 768 m — RED, AND THE FALLBACK EXECUTED | R-RANGE |
| RECIPES.md | L18446 | MEASURED (target class, missing 0 both stations at BOTH ranges) | R-RANGE |
| RECIPES.md | L18462 | REJECTED | R-RANGE |
| RECIPES.md | L18633 | ⛔ THE CHAIN IS NOT LINEAR, AND "EXPECT EXACT" DOES NOT HOLD | B3.13 |
| RECIPES.md | L18682 | THE WHITE BALANCE HAD TO BE RE-OPENED | A-6 R-WB2x2 |
| RECIPES.md | L19418 | REJECTED | B3.13 |
| RECIPES.md | L19450 | R-SHADE — THE CARD-PAIR ACCEPTANCE (2026-09-13) | A-6 R-WB2x2, R-INSTRUMENTS, R-SHADEBAND |
| RECIPES.md | L19464 | REJECTED | A-6 R-WB2x2, R-SHADEBAND |
| RECIPES.md | L19554 | REJECTED | B3.13 |
| RECIPES.md | L19608 | REJECTED | B3.15/16 |
| RECIPES.md | L19731 | R-MEADOWALBEDO â€” ALBEDO VARIATION IS MEASURED WHERE LIGHT NEVER LAND | R-T4 |
| RECIPES.md | L19760 | REJECTED | R-MEADOWALBEDO |
| STATE.md | L66 | 4 — INSTRUMENTS | B3.13 |
The scan is a seed (it matches values, not meaning). The desk's Pass 5 reading of LESSONS/RECIPES adds the rest; the
expected final count is 150–250 tagged entries out of 1,840 headings.

## 5. Root-level document archive (ruling for Ryan; nothing deleted)
| file | disposition | reason |
|---|---|---|
| MORNING_REPORT.md, _2.md, _3.md, _20260901.md | docs/archive/, banner | session reports; superseded by STATE.md |
| PHASE2_PLAN.md | docs/archive/, banner already present | three overturned rulings behind a banner |
| GOVERNANCE_MIGRATION.md | docs/archive/ | completed migration |
| ADVISOR_LOG.md, FORGE_LOG.md, BLENDER_HANDOFF.md | docs/archive/ or the forge's own folder | separate/parked products |
| REPLAY_BURNDOWN.md | keep, re-titled OPEN: cold replay is a Brief 5 acceptance | 13 UNPROVEN recipes still real |
| WORLD_VISION.md, WORLD_ARCHITECTURE.md, REFERENCES.md, ASSETS.md, CREDITS.md, BACKLOG.md | keep | live |
| dist/forge-0.1.1, dist/forge-0.4.0 (428 .py) | move out of the landscape repo (forge's own repo) | manufactures duplicate findings; 54 of the "94 verdict sites" were here |

## 6. CLAUDE.md rule pointers (draft; CC confirms each against the LESSONS entry of the same date)
| rule | pointer to propose |
|---|---|
| 3 commit before/after | LESSONS: the crash that reverted five tasks of applied values (Brief 2, 09-08/09) |
| 6 errors twice → diagnose | LESSONS 08-02/03 entries on the remote-exec payload-as-path failure |
| 8 dry-run destructive | LESSONS 2026-09-09f (no-force-delete guard) |
| 9 cite full text or path | LESSONS 2026-08-27b (licence asserted from memory) |
| 11 zero editors, ask which level | LESSONS 0-dirty editor-close wedge entries (4 occurrences) |
| 12 not read back = prose | Brief 1 handoff 09-05; R-METER warm-up finding 09-13 |
| 13 sample count beside verdict | precedence session 09-14 (0 of 22 samples) |
| others (1,2,4,5,7,10) | LESSONS entries dated 08-02/08-03 — CC binds by date |

## 7. Plan freshness (E-4, 23 stale)
Waivers are keyed to a recipe byte-diff; any edit to any field expires them. Change: a plan declares the recipe
fields it consumes (`consumes: [...]`), and freshness hashes only those. Producers that take no --out (16/23 cannot
reproduce) get one. Re-run producers where cheap; record the divergence note where not.

## 8. What the desk still owes before Block D applies this
Pass 2 (API semantics by class), Pass 3 (script_claims: thresholds' provenance, controls, KEEP/ARCHIVE/RETIRE per
script), Pass 5 (401 findings read in place). Their outputs extend §4 and §5; the mechanism in §2 does not change.
