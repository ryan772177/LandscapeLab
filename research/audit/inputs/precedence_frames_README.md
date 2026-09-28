# Precedence test — the frame instrument, and why it is INCONCLUSIVE

Audit item 3 asked for two dev-profile captures differing only in
`MoviePipelineGameOverrideSetting.cinematic_quality_settings`, with
`sg.ShadowQuality` / `sg.FoliageQuality` read from the engine log.

Two **log** instruments answered, and they agree. A third instrument —
the frames themselves — does **not** settle, and this file says so
rather than letting the two agreeing instruments carry a claim the
third cannot support.

## What the log instruments say

| instrument | what it reads | result |
|---|---|---|
| MRQ's own apply log (`MoviePipelineConsoleVariableSetting.cpp:253`) | `Applying CVar "X" PreviousValue: p NewValue: n` — `p` is the value the instant **before** the bench's cvar setting wrote it | every `sg.*` PreviousValue **identical** across the two runs |
| `Scalability` echoed from inside the render, at both the Start and End console-command hooks (`:271`, `:279`) | the engine's own scalability group report | all 11 groups **identical** across the two runs, at both hooks |

These share no code path — one is MRQ narrating its own writes, the
other is the console reporting engine state — so their agreement is
evidence rather than one measurement taken twice (NN0).

**Reading:** had `bCinematicQualitySettings` raised scalability before
the bench's cvars landed, `PreviousValue` for `sg.ShadowQuality` would
have read as the Cinematic level in run A and `1` in run B. It read `1`
in both. The bench's cvars are what the frames rendered at.

## What the frame instrument says, and why it does not settle

The two frames are **not** identical:

    mean abs diff            0.001415
    max abs diff             0.4863
    pixels differing > 1/255   3.770 %
    pixels differing > 8/255   0.748 %

A difference of unknown provenance is not a result. Attributing it
needs a **null pair** — two captures at the *same* flag value — and
this session's fence was two diagnostic captures, both of which were
spent on the contrast.

The nearest null already on disk is `target_range768{b,c,d}`
(2026-09-10), three runs of one config:

    frac > 1/255   0.0150 – 0.0177
    frac > 8/255   0.0010 – 0.0020
    mean abs       0.00033 – 0.00042

⚠ **That null does not transfer, and the reason is the instrument, not
the number.** Those are TARGET-profile frames — `temporal_sample_count`
8, TSR resolved — and temporal accumulation averages away precisely the
stochastic run-to-run variation being measured. The precedence pair is
DEV profile at temporal 1, with no accumulation at all, so its true
null is legitimately **larger** than the target null, by an unmeasured
factor. The observed 2×-in-fraction, 3.5×-in-mean gap sits inside that
unmeasured margin.

Per the verification practice: an instrument calibrated on one specimen
does not carry to a different one, and the answer to a refusal is a
class-appropriate instrument, never a widened tolerance.

**Verdict on this instrument: INCONCLUSIVE.** It neither supports nor
contradicts the log verdict.

## The owed experiment, stated exactly

One additional dev-profile capture at the same station and the same flag
value as either existing run:

    python scripts/bench_capture.py --profile dev --stations vista \
        --echo-scalability \
        --game-override cinematic_quality_settings=false \
        --tag precedence_null

Comparing it against `dev_precedence_cinematic_false` gives the
dev-profile null. If the null's `frac > 1/255` reaches ~3.8 %, the frame
difference is run-to-run noise and the frame instrument agrees with the
logs. If it stays near the target figure, the flag is doing something
the logs do not report, and P1-1 is not closed.

## Files

| file | what |
|---|---|
| `precedence_test.json` | both log instruments, per capture, plus the derived difference sets |
| `precedence_frame_diff.json` | the frame comparison above |
| `_verify/bench/2026-09-13/dev_precedence_cinematic_true/vista.png` | capture A |
| `_verify/bench/2026-09-13/dev_precedence_cinematic_false/vista.png` | capture B |
| `_verify/bench/2026-09-13/bench_run_dev_precedence_cinematic_*.json` | the two capture sidecars |
