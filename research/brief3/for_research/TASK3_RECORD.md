# Brief 3 Task 3 — RECORD (2026-09-13)

**Status: DELIVERED EXCEPT ONE RULED ITEM, and one recorded result did
not survive re-measurement.** Read §4 before using §2.

Station `Bench_ground`, 3840×2160, hfov 90, render warm-up 40,
Manual metering, compensation −13.5898 EV.

---

## 1 — THE PER-LAYER TILE TABLE, READ BACK FROM THE MATERIAL GRAPH

Not from the recipe. Standing rule 12: a declared value that is not read
back from the engine is prose, and the recipe was the thing under
suspicion. `scripts/payloads/read_layer_tiling.py` walks
`/Game/Materials/M_Alpine8K` (197 expressions, 32 texture samples, 0
accessor errors) from each `TextureSample` back through its `Divide` to
the `Constant` that is `tiling_m × 100`.

    layer         surface            tiling_m   consistent across C/N/R/D
    Snow          Snow007A           5.03       yes  (+188.0 macro on _C)
    Rock          gray_rocks         1.80       yes  (+188.0 macro on _C)
    Scree         rocks_ground_04    2.00       yes  (no macro — by design)
    ForestFloor   forest_floor       2.14       yes  (no macro — by design)
    Grass         WildGrass          5.03       yes  (+188.0 macro on _C)

    weightmap / macro mask           8128.0     the whole landscape

**Every layer binds exactly what the recipe declares.** The second
divisor on the three `_C` maps is the macro-variation path, and it
appears on precisely the three layers that declare `macro_tiling_m` —
which corroborates the `_no_macro_tiling` notes on Scree and
ForestFloor from the other direction.

⭐ **So Scree's binding is CORRECT: 2.00 m, not 2.40.** The ruling's
first branch is closed — the 2.40 m peak is real structure at 1.20× the
tile, not a misapplied number.

Artefact: `_verify/bench/2026-09-13/material_tiling_readback.json`.

---

## 2 — SPLIT (a): THE TEXTURE-TILE REPEAT

Local peak PROMINENCE above the window trend, so the weight-driven
component is masked out. Michelson against a CSF visibility threshold.

    bin       layer   tile     michelson   threshold   peak    verdict
    30-100    Rock    1.80       0.00000      0.0228   none    PASS
    30-100    Scree   2.00       0.06203      0.0250   85 px   FAIL
    30-100    Grass   5.03       see §4       0.0534   199 px  UNSTABLE
    100-300   Rock    1.80       0.00000      0.0114   none    PASS
    100-300   Scree   2.00       0.00000      0.0132   none    PASS
    100-300   Grass   5.03       0.00000      0.0310   none    PASS
    Snow, ForestFloor: 0 px at this station — NO VERDICT, both bins

**SCREE 30–100 m FAILS, and it is the most solid number in this
document** — four independent captures, peak at the same 85 px lag in
all four:

    t3f 0.06203   t3v 0.06122   t4base 0.06448   task3d 0.02678*
    * tone curve ON; see §3

85 px at 69.0 m = **2.40 m against a 2.00 m tile, 1.20×**.

---

## 3 — ⛔ THE TONE CURVE CHANGES THIS NUMBER BY 2.3×

The CSF threshold is a PERCEPTUAL contrast bound, so it belongs on the
display-referred frame. Scree 30–100 m, same structure (85 px) in every
capture:

    tone curve ON    0.02678        tone curve OFF   0.06203 / 0.06122 / 0.06448

`task3_layer_tables.py` now REFUSES a tone-curve-disabled capture unless
`--allow-linear` is passed, and says why. Verified three directions:
refuses `target_t4base`, passes `target_task3d`, selftest still passes.

---

## 4 — ⛔ THE RECORDED "5 OF 6 MEASURABLE PASS" RESTS ON ONE CAPTURE

Grass at 30–100 m is **not reproducible**:

    capture   tone curve   warm-up   michelson   peak     verdict
    t3f       off          40          0.00000   none     PASS   <- the one recorded
    t3v       off          32          0.07773   199 px   FAIL
    task3d    ON           32          0.09331   199 px   FAIL
    t4base    off          40          0.08023   199 px   FAIL

**t3f and t4base have identical declared settings and disagree.** So it
is neither the tone curve nor the warm-up count. Rock reads exactly
0.00000 in all four and Scree's peak sits at 85 px in all four — only
the layer whose geometry is ANIMATED moves.

**Leading hypothesis, stated as one and NOT confirmed:** `Meadow`
(grass_medium_01) is the only foliage species in `recipes/alpine_8k.json`
carrying no `override_materials`. SpruceSub, SpruceSapling and Blueberry
all have `/Game/Materials/PN_NoWind/…` instances; the grass cards do
not. The meadow is therefore the one thing in frame still moving, and a
wind phase differing per render would change its screen structure exactly
this way. Confirming it needs a no-wind capture of the meadow —
`scripts/make_nowind_material_instances.py` exists for this and has not
been run against Meadow.

199 px at 75.9 m = 6.18 m against a 5.03 m tile, **1.23×** — the same
ratio-to-tile as Scree's 1.20×, which is worth noting: if it is real,
two layers carry structure at ~1.2× their tile.

---

## 5 — SPLIT (b): THE WEIGHT-DRIVEN COMPONENT HAS NO PERIOD

Measured with an OPEN band, 0.3–20 m, no predicted period anywhere in
the instrument: the SPECTRUM of the autocorrelation
(`scripts/task3_weight_period.py`), on the BaseColor pass.

    bin       layer   strongest line   snr    corr-len   broadband mich
    30-100    Rock       9.246 m       15.7    1.002 m      0.332
    30-100    Scree     12.495 m       20.0    1.433 m      0.695
    30-100    Grass      6.781 m       32.3    2.060 m      1.047
    100-300   Rock       4.425 m       25.7    2.193 m      0.359
    100-300   Scree      9.339 m       20.1    2.968 m      0.472
    100-300   Grass      0.574 m       20.7    5.600 m      0.606

Floor 100, DERIVED: negative controls 3.89 / 9.82 / 18.06, positives
3.7e5–4.0e6. **Every line is inside the negative controls' range. The
component is BROADBAND, not periodic.**

⭐ **It is NOT the weightmap texel pitch**, despite Rock's near bin
reading 1.002 m against our 1.000 m/texel weightmap. The correlation
length is conserved in PIXELS, not metres:

    layer    px             spread    m                spread   conserved
    Rock     35.5 → 32.2      10%     1.002 → 2.193     119%    PIXELS
    Scree    50.8 → 48.2       5%     1.433 → 2.968     107%    PIXELS
    Grass    66.4 → 100.5     51%     2.060 → 5.600     172%    PIXELS

A world-fixed pitch holds its metres and shrinks in pixels with
distance. This does the opposite, on every layer, so it is SCREEN-SPACE
— not the weightmap texel, not the 127 m section, not the 254 m
component. At 69 m, 35.5 px simply happens to subtend one metre.

---

## 6 — ALBEDO

**The Task 3 figure was a LIGHTING statistic.** std/mean of luma on a
LIT pass carries shading: a perfectly uniform meadow half in shadow
scores about 0.4 on it.

    metric                              Grass 4-10 m   Grass 3-60 m
    BaseColor, no lighting at all          0.2278         0.3075
    PPI0, with shadows                     0.4790         0.4971
    FinalImage luma (the old number)         —            0.4447
    band                                          0.10 – 0.20

**Baseline on the corrected metric: 0.2278 — ABOVE the band.** Mean
albedo 0.4277. See `R-MEADOWALBEDO`; the lit-only mask the brief asked
for cannot be built over card geometry, and the reasons are measured.

Other layers, BaseColor, 4–10 m — numbers only, no band (the 0.10–0.20
band is the brief's MEADOW band): Rock 0.1119, Scree 0.1616.

---

## 7 — WHAT IS NOT DONE

**STOCHASTIC TILING FOR SCREE IS RULED AND NOT BUILT.** Its precondition
is now proven (§1: Scree binds 2.00, so the ruled condition 0.064 against
0.025 holds). De-risked but not built:

* 5.8 ships **no hex-tiling function**. Enumerated from the running
  editor: 521 engine material functions; the candidates are
  `Texture_Bombing`, `TextureBomb_SingleSample` and `TextureVariation`.
* **`TextureVariation` is the right shape** — it returns *Shifted UVs*
  plus DDX/DDY, so ONE instance drives all four of Scree's maps from a
  single UV source and keeps them registered, and our sampler-type
  declaration machinery is untouched. The other two return a sampled
  Result and would bypass it.
* **The Python plumbing exists**, tested on a throwaway material:
  `mip_value_mode` IS settable to `TMVM_DERIVATIVE` (it is absent from
  `dir()`, which is not proof of absence — testing beat inference);
  `DDX(UVs)` and `DDY(UVs)` are the real pin names; the sample's UV pin
  is `UVs`, not `Coordinates`.
* ⛔ **THE BLOCKER: `Variation Scale` and `Variation Levels` semantics
  cannot be read through the Python surface.**
  `get_inputs_for_material_expression` returns EMPTY on a
  `MaterialFunction` rather than raising — every one of the nine inputs
  reported zero consumers, which is impossible and is how the failure was
  caught. `preview_value` is a `Vector4f` whose components are not
  exposed either. Guessing whether a scale multiplies or divides the UVs
  would set the cell size wrong by its square.
  **The way through is measurement, and the instrument now exists:**
  build a probe material at several `Variation Scale` values and read the
  resulting cell period straight off a render with
  `task3_weight_period.py`, which was built this session and does exactly
  that.

Also open: Snow and ForestFloor have 0 px at this station and have never
had a tiling verdict.
