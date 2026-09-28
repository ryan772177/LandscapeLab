# B-5 — the precedence null pair: the frame instrument is CONCLUSIVE, and it agrees

2026-09-15, vista, dev profile, temporal 1 (the precedence arms' class).
Editor verified `/Game/Alpine8K`.

## The question

The 09-13 precedence pair (dev vista, `cinematic_quality_settings`
true vs false) differed in the FRAMES by mean 0.001415 / 0.85% of pixels
> 8/255 (`precedence_frames_README.md`). Two LOG instruments already
settled precedence — the bench cvars win, `sg.*` PreviousValue identical
in both arms — but the frame difference was left INCONCLUSIVE because no
null pair had isolated the dev/temporal-1 run-to-run noise floor. B-5
provides it.

## The null, done cleanly (two same-world captures beat one vs 09-13)

⚠ The desk's "one capture vs both 09-13 arms" was contaminated: the world
has moved a great deal since 09-13 (grade re-solve, cloud MI, HLOD
rebuild), so a now-vs-09-13 frame differs by **mean 0.083, 99.8% of
pixels** — 60× the flag effect — whether the flag matches or not
(same-flag 0.0836 vs cross-flag 0.0827, indistinguishable). That measures
the world change, not run noise. The class-appropriate null is TWO
captures at the SAME world and SAME flag:

    comparison                                  mean       frac>1/255   frac>8/255
    RUN-NOISE NULL (null1 vs null2, both false) 0.001463   7.58%        0.85%
    09-13 FLAG EFFECT (false vs true)           0.001415   8.65%        0.85%

## Verdict: the frame instrument is CONCLUSIVE — the flag effect IS the noise floor

The 09-13 "flag effect" (0.001415) is **statistically identical to, and
marginally below, the run-to-run noise floor** (0.001463) — the
frac>8/255 figures are equal to 2 decimals (0.85% each). So the
`cinematic_quality_settings` flag changes the frame by no more than two
same-flag captures differ from each other by chance at temporal 1.

**The frame instrument is no longer inconclusive — it is conclusive, and
it AGREES with the two log instruments:** the flag has no frame effect
above noise, exactly as the log instruments predicted (it did not raise
scalability before the bench cvars landed). All three instruments now
concur; the precedence question (P1-1) is fully closed. The frame
instrument is not "retired" for lack of power — with a proper null it
resolved the question and confirmed the null hypothesis.

Artefacts: `dev_b5_precedence_null/`, `dev_b5_precedence_null2/` (2026-09-15);
`dev_precedence_cinematic_{false,true}/` (2026-09-13).
