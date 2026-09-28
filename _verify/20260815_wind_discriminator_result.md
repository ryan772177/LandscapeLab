# The discriminator: wind was real, and my committed conclusion was wrong

2026-08-15. Single variable: the wind-off material overrides were applied to
the placed `SpruceSub` and `SpruceSapling` instances via
`FoliageType_InstancedStaticMesh.override_materials`. Nothing else changed —
same seed, same recipe, same 219,659 transforms, same camera, same settings.

## Result

    station        pre-fix (wind ON)       post-fix (wind OFF)   change
    trunk_base     0.019815 / 0.025762     0.009799              -57%
    forest_floor   0.008899 / 0.008180     0.007140              -17%

Two pre-fix readings are quoted per station because the floor was measured
twice on the SAME unchanged world, and the spread between them (+30% at
trunk_base, -8% at forest_floor) is the run-to-run noise of the estimate
itself at n=3.

**`trunk_base` fell 57%, far outside that spread. That is a real effect.**
**`forest_floor` fell 17%, INSIDE it. That resolves nothing.**

## What it means, including where I was wrong

`_verify/20260815_alpine8k_noise_floor_per_station.md` and
`_verify/20260815_alpine8k_animation_check.md` concluded the elevated
per-station floor was **renderer temporal accumulation, not motion**. At
`trunk_base` that was **substantially wrong** — most of the excess was wind
from PN trees that were rendering on vendor materials.

The reasoning that produced the error is worth keeping. The animation check
probed `MA_Foliage_Trees` and `ScotsPine_01_Leaves_Mat`, found no wind
parameter in either, and concluded the forest does not animate. Both probes
were correct. Both were of the **pre-D4** species. The PN trees did not exist
in the world when that check ran, and 108,417 of them were added afterwards.
**The conclusion was true of the world it was measured on and was carried
forward to a world that had changed underneath it** — a derived record that
stopped matching its artefact.

## What survives

- **Residual is real.** 0.009799 is still 3.29x the 0.00298 bare-terrain
  floor with all wind off. Renderer temporal accumulation on alpha-tested
  foliage is a genuine contributor; it simply was not the whole story.
- **Both mechanisms operate.** The correct statement is that the elevated
  floor at a foliage-heavy station had two causes, and only one of them has
  now been removed.
- **The per-station finding stands and is strengthened.** The floor tracks
  frame CONTENT, and it now also tracks what that content is DOING.
- The pre-D4 measurements remain valid for the world they were taken on: the
  grass control was genuine, and neither pre-D4 tree material declares wind.

## Why the station split is mechanically sensible

`trunk_base` is a 35 deg close-up of a trunk and canopy — PN foliage fills
the frame. `forest_floor` is a 75 deg wide shot where the windless Megaplants
canopy, the Scots pines and the grass dominate and the PN tiers are a smaller
share. A wind effect confined to PN materials should therefore move
`trunk_base` hard and `forest_floor` little, which is what happened.

## Verification of the overrides themselves

Two representations, which matters because an in-memory read-back alone
proves only that the setter wrote the field it was told to (NN8):

1. `place_foliage`'s own read-back compares `override_materials` after
   setting against what the recipe declared and FAILS the run on
   disagreement. The run exited 0.
2. **The frames moved 57%.** That is a different representation entirely and
   it is the stronger of the two — a material override that had not landed
   could not change the pixels.

## Also confirmed in the same run

    placed   219,659   planned == counted in world
    saved      1,095   packages, all re-read clean, 0 removed

## Open

- The 0.0098 residual is not decomposed. TSR history, Lumen accumulation,
  volumetric fog reprojection and light shafts remain candidates and no
  single-variable cvar A/B has been run on any of them.
- `forest_floor` is unresolved, not clean. A higher frame count would be
  needed to see a 17% effect against a 30% noise band.
- Only 2 of 20 stations have been re-measured post-fix.
