# Phase C send-back — for the research desk

Four stills at 1920×1080 and the two `bench_run` sidecars that describe how
they were taken.

    near_ground.png         player instrument, plaza station
    mid_slope.png           player instrument
    vista.png               player instrument
    near_ground_truth.png   TRUTH instrument -- all regions force-loaded,
                            HighResShot with r.HighResScreenshotDelay read back

    bench_run_target.json         the player-instrument run
    bench_run_target_truth.json   the truth-instrument run

## Read these three caveats before drawing conclusions

**1. Residency is DERIVED, not declared.** The expectation comes from the
engine's own runtime grid — cell size and loading range read from the world,
then the cells intersecting the camera's loading range — not from a number in
a config. Both the expected set and the loaded set are in the sidecars. The
engine default loading range is 25,600 cm (256 m,
`RuntimePartition.cpp:27`), which is why earlier gates demanding 1,024
components over 8.1 km were asking for something the engine never streams.

**2. `featureless_fraction` is three numbers, not one.** Total, sky-coloured
(inside the station's predicted sky band), and non-sky. `mid_slope` carries a
substantial NON-SKY featureless fraction, and that is the interesting one —
sky being featureless is expected; ground being featureless is not.

**3. Exposure is pinned by the profile and read back.** An earlier run had
`r.DefaultFeature.AutoExposure=0` in the profile, which does NOT do what its
help text claims: `SceneView.cpp:2060-2069` overwrites
`FinalPostProcessSettings` *after* the volume blend, so the cvar silently won
over the PostProcessVolume and cost four stops of blow-out. Those cvars are
gone; the exposure now comes from the volume and is verified in the sidecar.

## What is NOT here, and why

**The dolly frames.** The 3 s sunlit dolly was captured (90 frames, verified
complete) but it does **not** stay out of canopy shadow — the lit share of the
ground half falls 41.1% → 17.7% over 4.2 m. E4 said capture and check, not
score, so no heading was re-chosen and no threshold moved to make it pass.
Choosing a sunlit heading is a decision, not a fix; BACKLOG carries it.
Evidence: `_verify/bench/2026-09-07/dolly_sunlit.json`.

**Anything from the sample-project census.** That is a separate send-back:
`research/census/CENSUS_ROLLUP.json`.
