# Does the placed Alpine8K forest animate? — measured 2026-08-15

Asked because the PN spruce canopy animates with no Blueprint present, and
the 153,796 trees already standing had never been tested. If they moved,
every PIXEL comparison on this world since the spruce adoption would sit on
an inflated floor.

Level `/Game/Alpine8K` opened cold and verified by read-back. **Residency
forced and asserted: 1 landscape + 256 proxies, 1024 components resident** —
without that the trees are not in the frame and a STATIC verdict would mean
nothing. Camera `forest_floor`, the station carrying the 8.14 -> 7.76 ms
series. Throttle gate passed at 4.61 CPU-s per wall-second.

Frame cost re-read in passing: **GPU 7.75 ms** (p50 7.74), independently
re-confirming the recorded 7.76.

## ANSWER: NO. The forest does not animate.

Two representations, and they share no source.

**1. The materials declare no wind at all.** `probe_material.py` on both
species:

    MI_Norway_Spruce_Foliage_01  ->  MA_Foliage_Trees
      38 scalars   all shading: AO, Roughness, Specular, Translucency,
                   Normal Strength, Displacement Power
      19 switches  all appearance: Seasons, Tint, Debug Mask, Split Controls
      20 vectors   all colour
    ScotsPine_01_Leaves_Mat
      3 scalars    Btighten, SS Brightness, Sat
      0 switches

**Not one wind, wobble, bending, phase or time parameter between them.**
Compare the PN master, which carries `Level 1/2/3 Wind`, `Level 1/2/3
Bending`, `Wobble Strength 1/2/3`, `Wobble Frequenz 1/2/3`, `Player Wobble
Strength`, `Motion Dampening` and `Trail Strength`. The difference is not
subtle and it is structural.

**2. Removing the grass did not reduce frame-to-frame variance.**
`grass.Enable 0`: 0.011745 -> 0.012122. Unchanged. Vegetation is not driving
the variance.

## THE FINDING THAT MATTERS MORE — the noise floor here is 4x what we quote

Three frames, 5 s apart, one parked camera, nothing touched:

    1 vs 2   mae 0.011429  = 3.84x floor   px>2% 22.39%   max 0.6157
    1 vs 3   mae 0.012166  = 4.08x floor   px>2% 23.83%   max 0.6000
    2 vs 3   mae 0.011639  = 3.91x floor   px>2% 22.54%   max 0.5529
    MEAN          0.011745  = 3.94x        px>2% 22.92%

**The effective noise floor on `/Game/Alpine8K` at `forest_floor` is
~0.012, not 0.00298**, and it is present with the grass removed — so it is
RENDERER temporal instability (TSR/Lumen/volumetric-fog accumulation), not
scene motion. Shader compile workers: 0, so it is not compilation settling.

**Consequence, stated plainly: every pixel A/B judged against 0.00298 on
this world has been over-crediting differences by about 4x.** The 0.00298
was derived on `/Game/Alpine` — a different world, 2017², before Lumen, the
capable-GPU profile and volumetric fog. **A noise floor is a property of a
scene and a settings set, not of a project.** It must be re-derived per
world, exactly as R13 already insists for GPU figures.

## AND `foliage.CullAll` NO LONGER ISOLATES TREE COST

The vegetation-off control was run as `foliage.CullAll 1` + `grass.Enable 0`.
Both read back correctly. **The trees stayed on screen.**

Measured rather than eyeballed — upper half of the frame is canopy and sky,
so culling the trees must collapse its dark coverage:

    upper half dark-pixel coverage   ON 62.73%  ->  OFF 53.92%   (-8.81)
    lower half dark-pixel coverage   ON 56.52%  ->  OFF 41.55%   (-14.97)

The lower half — the grass — moved nearly twice as much as the upper. The
canopy barely changed. **`grass.Enable 0` worked; `foliage.CullAll 1` did
not.**

Root cause at source: `foliage.CullAll` is declared in
`HierarchicalInstancedStaticMesh.cpp:63-67`, i.e. the **HISM** culling path.
`r.Nanite.Foliage` is **1** on this process and the placed spruce is Nanite,
so it never enters that path and the cvar cannot touch it.

**This is the value-arrives-but-means-something-else class.** The cvar reads
back 1, the tool reports CONDITION SET AND READ BACK, and the thing it names
does not happen.

**It has a backwards-reaching consequence.** CURRENT STATE records the
2026-08-14 decomposition as *"vegetation ON 8.14 / vegetation CULLED 5.86,
DELTA +2.28 ms"* attributed to *"154,018 conifers plus grass"*. If
`r.Nanite.Foliage` was already 1 for that run, **the 2.28 ms was grass
alone** and the conifers' cost was never isolated. If it was 0 then, the
figure stands. That is not resolved here — it needs the cvar's value at that
run, not a guess — but **no future decomposition may use `foliage.CullAll`
to isolate Nanite foliage.** The working lever would be `r.Nanite.Foliage 0`
first, which is itself a scene change.

## WHAT IS NOT ESTABLISHED

- **The trees were never actually removed**, so the render half of the
  no-animation case rests on the grass control plus the material probes, not
  on a tree-free frame. The material evidence is strong and independent;
  the render evidence is partial. Said plainly rather than rounded up.
- Which specific renderer feature produces the ~0.012 was not isolated.
  Candidates: TSR history, Lumen accumulation, volumetric fog reprojection,
  light shafts. One cvar A/B each would settle it and none was run.

## ARTEFACTS

    _verify/20260815_alpine8k_forest_floor_animation.json        veg ON
    _verify/20260815_alpine8k_forest_floor_animation_diff.png
    _verify/20260815_alpine8k_forest_floor_NOVEG_animation.json  grass off
    _verify/20260815_alpine8k_forest_floor_NOVEG_animation_diff.png

New tool: `scripts/check_scene_animation.py`. It reports the mean AND the
fraction of pixels moved AND the peak AND per-band figures, and writes the
diff image, because the PN case proved a mean alone hides a concentrated
change — 2.05x the floor while moving 0.73 on 4.4% of the frame.
