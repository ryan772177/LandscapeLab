# C0 tiling propagation — done. The re-read is BLOCKED, and not by the tiling.

**2026-08-31.** Ruled: propagate the tiling finding to C0, rebuild, re-frame
the graded pair, and re-read the "too orange" verdict.

## ⭐ tile_m IS NOW A MEASUREMENT FOR ALL SEVEN ROLES

Every generated tile REPLACED a Poly Haven original on the same mesh with the
same UVs, "repaired for tiling" rather than re-framed — so it depicts the same
real-world extent, and Poly Haven publishes that extent.

| role | replaces | tile_m | m/uv measured | tiling |
|---|---|---|---|---|
| `wall_planks_a` | wood_planks_grey | 1.5 | 0.811 | **0.541** |
| `beam_wood` | rough_wood | 0.5 | 0.310–1.028 | **1.767** ⚠ |
| `roof_tiles` | grey_roof_01 | 8.0 | 8.833 | **1.104** |
| `plaster_wall` | concrete_wall_003 | 3.0 | 8.850 | **2.950** |
| `wall_planks_b` | brown_planks_03 | 1.0 | 2.061 | **2.061** |
| `rock_wall` | *(kept)* rock_wall_08 | 1.8 | 2.777 | **1.543** |
| `floor_worn` | *(kept)* concrete_floor_worn_001 | 3.0 | 0.061 | **0.020** |

Rebuilt: 21 textures, master compiles clean, **all 7 instances read back**.
Stage rebuilt, 10 slots bound, 0 bind failures.

### ⛔ IT ALSO CORRECTED THE CHURCH I SHIPPED YESTERDAY

I gave `church_roof` a **declared intent of 1.5 m**. The measurement is
**8.0 m**, so its tiling was **5.3× too high** — and the "visible tile
repetition" I logged as an accepted trade-off was not a trade-off, it was that
error. `church_plaster` was likewise 2.0 declared against a measured 3.0.
Both corrected; the church rebuild is in the same commit.

Independently confirmed for the roof, because it was the one that mattered:
the generated tile shows **~36 shingle courses across 1024 px**, and at a
0.18–0.22 m course exposure that is **6.5–7.9 m** — against the vendor's
published 8.0. The count and the vendor agree.

## TWO STRUCTURAL FINDINGS THE MEASUREMENT SURFACED

**1. `beam_wood`'s four slots disagree by 3.3×** — 0.310, 0.543, 0.884, 1.028
m/uv. **One material instance carries one `Tiling`**, so no single value is
correct for all four. The builder now says so on every run rather than
silently picking the median and calling it derived. Fixing it properly means
either four instances or a UV repair, and both are the operator's call.

**2. `floor_worn` needed a 50× correction.** Its UVs run at 0.061 m/uv, so a
3 m concrete texture was being squeezed into 6 cm and repeating ~50× inside a
small area. At Tiling 1.0 that was noise, not a surface.

**And a limit on the premise:** most C0 roles landed between 0.54 and 2.95 —
i.e. within about 3× of correct. The donor's UVs were hand-authored roughly
for the vendor textures, unlike the church's machine unwrap at **~50 m/uv**.
So "every C0 judgement was made at the wrong texel density" is true, but the
magnitude was modest for five of seven roles and severe for `floor_worn`.

## ⛔ THE RE-READ IS BLOCKED — AND I AM NOT OFFERING A VERDICT

My eye said the swapped timber reads markedly less orange at correct density.
**I am not reporting that as a finding, because the frames are not
comparable.** Measured:

    reference (BEFORE)   ground 241.6   sky 170.5   blown(>250)  0.0%
    my re-shoot (AFTER)  ground 249.6   sky 183.7   blown(>250) 19.2%

**A fifth of my frame is clipped to white.** Saturation cannot be compared
across a two-thirds-stop exposure difference with a fifth of one image
clipped — clipping pulls colour toward white and would produce exactly the
"less orange" impression I had, with no material change whatever.

The stage payload reports the same manual exposure bias (−1.923, overridden
true) in both runs, so the exposure difference is NOT in the level. It is in
the capture path, and the reference frame's camera was never recorded — which
is the second half of why this cannot be closed.

**The numeric instrument did not converge either.** It first sampled the white
ground plane and reported `rgb [233,233,236]` for the timber with full
confidence, then over-tightened and sampled nothing. It is left in the tree
with its sample-dump so the next attempt can see what it is measuring, but
**no number from it is being relied on here.**

### WHAT WOULD CLOSE IT

Re-shoot the reference at the SAME camera as the new frame, with the same
capture path, so the pair differs only by tiling. That means either finding
the original camera or re-rendering both sides now. Cheap, and it must happen
before any grade decision — **the grade question is untouched, in both
directions.**
