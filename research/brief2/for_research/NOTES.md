# ⭐ ADDENDUM 2026-09-10 — the rulings landed; read SENDBACK_2026-09-10.json

Everything below this section describes the 2026-09-09 state and its two
open questions. Both are now CLOSED by ruling, and three of its statements
are superseded:

1. **The WB ruling**: white_temp = the sun's temperature (neutral), never
   above it. Recipe 8800 → 7800 K; 8800 REJECTED with the Scene.h:1505
   reason. §2's "8800 K is left applied" is history — a crash also
   reverted the world overnight, and the restore + a new save-and-commit
   step in apply_lighting (R-LIGHTSAVE) closed the gap that allowed it.
   Post-restore truth-class tints: shadow_tint_B 1.2580 (moved +0.17
   toward the 1.3–1.7 band, still 0.042 below); highlight_tint toward
   neutral but the 0.9–1.1 clause stays unreachable at near_ground (green
   grass). Next lever: Brief 2b (sun temperature), registered.
2. **The sky classifier**: §1's requested depth replacement is DONE and
   Tasks 1–5 re-judged offline (sky_rejudge_depth in the addendum JSON).
   Headline: mid_slope geometric sky is stable 0.728–0.758 across the
   brief; the 0.79 "featureless non-sky band" was ~0.72 misclassified
   sky. And the colour mask was NEVER valid at mid_slope — Task 2's
   blue-sky era already read 0.255 colour vs 0.744 depth. Vista dE under
   depth FELL task-over-task (0.224 → 0.194): the desaturation was
   converging fog toward sky and the colour instrument reported the
   opposite.
3. **§3's "Task 6 was NOT run"**: it has now run, as specified. One
   VolumetricCloud, engine simple-cloud child MI, coverage 0.3, bottom
   2.0 km, height 1.5 km. Both acceptance clauses PASS: vista geometric
   sky 0.4608 pre == post (0.0 pts, limit 2); dolly score ratio 0.9997
   (limit 1.10), 0 spikes, walk stays sunlit. Clouds don't write scene
   depth (masks agree 1.0000), so under the ruled mask they count as sky
   and land in the featureless-SKY column (0.144 → 0.366), not non-sky
   as §3-era reasoning expected.

New stills: `near_ground_truth_7800K.png`, `vista_precloud_7800K.png`,
`vista_postcloud_clouds.png` (all 1920-wide, truth-mode, residency
missing 0).

---

# Brief 2 send-back after Task 5 — read this before the numbers

Three things the research desk should know before reading `SENDBACK.json`.

## 1. THE SKY CLASSIFIER IS BEING ERODED BY THE BRIEF'S OWN DIRECTION

`SKY_BAND` is `{min_blue_minus_red: 0.06, require_monotonic_bgr: true}` — a
pixel counts as sky if it is blue enough and its channels run B >= G >= R.
Brief 2 asks for MORE MIE (whitens the sky) and a WARMER white balance. Both
move sky pixels out of that band. Measured on the same three stations:

    mid_slope sky fraction   Task 2 0.3462 -> Task 4 0.1676 -> Task 5 0.0000
    vista     sky fraction   Task 3 0.4240 -> Task 4 0.3660 -> Task 5 0.2468

**At Task 5 mid_slope reports 0.0000 sky and 0.7907 non-sky: the entire sky is
classified as not-sky.** Nothing is wrong with the frame; the classifier is
calibrated against the saturated blue sky the brief is deliberately removing.

This matters because FOUR Brief 2 measurements stand on that mask —
`featureless_split`'s sky/non-sky column, `fog_vs_sky`'s horizon-sky median,
`sky_saturation`'s zenith and horizon bands, and `skyline_iou`. As the sky
desaturates, all four degrade together, and they degrade SILENTLY: a sky
reclassified as non-sky inflates the very "featureless non-sky band" number
that Brief 2 §0.3 exists to explain.

**Every non-sky figure at Task 4 and Task 5 should be read with this in mind,
and the Task 5 mid_slope row should not be compared with earlier rows at all.**
A colour-threshold sky test needs replacing with a depth-based one — the
scene-depth pass built for Task 2's re-measure already separates sky from
world geometrically, and does not care what colour the sky is.

## 2. TASK 5 FAILED AND IS STILL APPLIED

`highlight_tint` R 1.3748 / G 0.9704 / B 0.1895 against an acceptance of
0.9–1.1, and it moved AWAY from neutral (Task 4 was 1.3005 / 0.9871 / 0.2431).
It also pushed `shadow_tint_B` from 1.4456 to 0.9829, out of the 1.3–1.7 band
Task 3 had just achieved.

The white-balance rule contradicts its own citation. BRIEF §3 says
`white_temp = sun + ~1000 K` and cites "ED: sun 6500 K uncorrected / WB 5600"
— which is 900 K **below** the sun. `Scene.h:1505` defines `WhiteTemp` as the
temperature "which the scene considers as white light", so 8800 K against a
7800 K sun declares the sun cooler than white and renders it warm. The
measurements agree with the engine, not with the prose.

Reading the citation instead gives 6800 K. **That is a change to the rule and
is Ryan's to make**; nothing was tuned, and 8800 K is left applied so the
failing state is the one on disk.

Separately: `highlight_tint` presumes a NEUTRAL sunlit surface. The sunlit
meadow is green grass under a warm sun, so B/luma is 0.19–0.24 at any white
balance. The acceptance may be unmeasurable at this station regardless of the
rule.

## 3. WHAT IS AND IS NOT IN THIS PACKAGE

    near_ground.png        Task 5 player, 1920 wide
    mid_slope.png          Task 5 player
    vista.png              Task 5 player
    near_ground_truth.png  Task 5 TRUTH (MRQ, full residency, gates passed)
    SENDBACK.json          featureless table, haze-by-depth table, recipe diff

**Task 6 was NOT run.** The overnight brief said to stop on a ruling and Task
5 produced one.

The haze-by-depth table is the replacement for the row-banded haze metric,
which R-FOG struck for near_ground: rows are not depth. mid_slope PASSES it at
both Task 2 and Task 4 settings, including the physical clause — measured
contrast ratio within ±30% of the transmittance the fog was solved for.
