# REGISTER — the truth instrument, defined by read-back

**Ruled 2026-09-13.** Closes AUDIT.md P1-1b (STALE-REWRITE) and V-7.
Written into `scripts/bench_capture.py`'s module docstring in the same
commit, so the definition travels with the tool and not only with the
record.

---

## 1. "Truth" names TWO instruments, and they are not interchangeable

| flag | what it is | GameOverride? |
|---|---|---|
| `--instrument truth` | editor + `HighResShot`, every region force-loaded. No MoviePipeline at all — `bench_capture` returns from this branch before the MRQ path. | **NO** |
| `--truth` | MRQ render with `MoviePipelineGameOverrideSetting` installed | **YES** |

A sidecar may carry either, both or neither. Only the second can carry
LOD / HLOD / draw-distance forcing, so a single "truth" count merges a
population that has the defect with one that structurally cannot.

## 2. Every capture path that adds GameOverride

Two, and only two (`scripts/payloads/bench_render.py`, the
`if CFG.get("truth") or _go_req:` branch):

1. **`--truth`** — any profile. Sets three properties explicitly.
2. **`--game-override KEY=VALUE`** — added 2026-09-13 for the precedence
   test. Diagnostics only. **A capture using it is not a truth capture
   and is not comparable to one**, because it carries the same
   seventeen class defaults while looking like an ordinary dev frame.

Before 2026-09-13 the second did not exist, and the first was the only
way the setting ever entered a config. Every dev-profile and non-truth
target capture had **no GameOverride at all** — five setting classes,
not six.

## 3. All 20 properties, READ BACK (not requested)

`--profile target --truth`, read off the setting object in the engine,
2026-09-13. `research/audit/inputs/mrq_config_dump.json`, key
`target+truth`.

| property | value | origin |
|---|---|---|
| `cinematic_quality_settings` | True | class default |
| `use_lod_zero` | True | class default |
| `disable_hlods` | True | class default |
| `disable_hlo_ds` | True | deprecated alias of the same field |
| `texture_streaming` | DISABLED | class default |
| `use_high_quality_shadows` | True | class default |
| `shadow_distance_scale` | 10 | class default |
| `shadow_radius_threshold` | 0.001 | class default |
| `flush_grass_streaming` | True | class default |
| `override_grass_cull_distance_scale` | True | class default |
| `grass_cull_distance_scale` | 50.0 | class default |
| `override_grass_density_scale` | False | class default |
| `grass_density_scale` | 1.0 | class default |
| `override_virtual_texture_feedback_factor` | True | class default |
| `virtual_texture_feedback_factor` | 1 | class default |
| `soft_game_mode_override` | `MoviePipelineGameMode` | class default |
| `game_mode_override` | None | deprecated |
| **`override_view_distance_scale`** | **True** | **set by `--truth`** |
| **`view_distance_scale`** | **100** | **set by `--truth`** (`benchmark.json` `residency.truth.view_distance_scale`) |
| **`flush_streaming_managers`** | **True** | **set by `--truth`** |

Plus the start console commands, read back from the config:

    wp.Runtime.OverrideRuntimeLoadingRange -grid=MainPartition -range=1200000
    wp.Runtime.MaxLoadingStreamingCells 512

⚠ `MaxLoadingStreamingCells 512` is emitted **twice** — once by the truth
block and once by the derived block. Idempotent, so harmless, but it is
a duplicate in a list where the 2026-09-09 defect was *last-writer-wins
on the same grid*. Worth removing when that code is next touched; not
touched here.

⭐ **Only three of twenty are chosen.** The other seventeen arrive the
moment the setting is added. So a truth frame is not "the same frame
with everything loaded" — it is **LOD 0 everywhere, HLOD off, texture
streaming off, high-quality shadows, grass cull ×50, draw distance
×100**, and before this register none of that was written down.

`view_distance_scale` differs between the two ways the setting can
appear: **100** under `--truth`, **50** (the class default) when only
`--game-override` requests something else. A dump taken under
`--game-override` is therefore not evidence about truth captures.

## 4. Every acceptance taken on a truth capture

Audited over every JSON under `_verify/`
(`research/audit/tools/truth_acceptances.py`;
`research/audit/inputs/truth_acceptances.json`). A `"truth"` key is
present in ~114 sidecars as a **declared absence** (`null`), so the
grep-for-the-word count over-reports about tenfold; a non-null value or
a `game_overrides_readback` is the signal.

**Nine artefacts, of which eight are mechanism B.** Two of the eight
(09-13 precedence) are last session's `--game-override` diagnostics, not
truth captures. The six real ones:

| date | acceptance (tag) | profile | what it measured | LOD/HLOD/cull/draw? |
|---|---|---|---|---|
| 2026-09-06 | `diag` | dev | residency + featureless/luma | no |
| 2026-09-06 | `truth` | dev | residency + featureless/luma | no |
| 2026-09-09 | `mrqtruth` | target | residency | no |
| 2026-09-09 | `mrqtruth2` | target | residency | no |
| 2026-09-09 | `truth_task5` | target | `near_ground` featureless_fraction 0.1794, mean_luma 0.3819, residency verdict | no |
| 2026-09-10 | `truth_t5r` | target | `near_ground` featureless_fraction 0.1791, mean_luma 0.3806, residency verdict | no |

Plus one mechanism A: 2026-09-07 `bench_run_target_truth.json`,
`--instrument truth` (editor + HighResShot) — no GameOverride, so
structurally uncontaminable.

**Verdict: CLEAN.** No LOD, HLOD, cull or draw-distance acceptance was
taken on the truth instrument. The two rows named for Task 5 — the HLOD
task, and so the most suspicious — were read individually rather than
accepted from the summary: both measured `featureless_fraction` and
`mean_luma` at `near_ground` plus a residency verdict, neither measured
HLOD. This **confirms AUDIT.md V-8**.

⚠ **INSTRUMENT CAVEAT (NN0).** The desk's V-8 and this check both read
the same sidecars, so this is one source read twice, **not two
instruments agreeing**. A genuinely independent confirmation would read
the frames or the engine logs of those six runs. Recorded as agreement
of *readings*, not of *instruments*.

⭐ One nuance that is NOT contamination: a residency census taken under
truth counts real actors with `disable_hlods` True, so no HLOD proxies
are present to be counted. That is what truth is *for*, and the six
residency verdicts are consistent with it rather than compromised by it.

## 5. Standing requirement from here

All 20 properties are read back per truth capture and recorded in the
sidecar. Before 2026-09-13 only four were
(`view_distance_scale`, `override_view_distance_scale`,
`flush_streaming_managers`, `disable_hlods`) — which is why the other
sixteen went unnoticed for the life of the instrument. The read-back
loop in `bench_render.py` now enumerates the full list from
`MoviePipelineGameOverrideSetting.h:79-151`.
