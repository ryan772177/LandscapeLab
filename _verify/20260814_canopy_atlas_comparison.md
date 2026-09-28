# CANOPY ATLAS COMPARISON — fir_tree_01 vs the free Scots pine, 2026-08-14

**Question:** does the free conifer already on disk fix the bare-poles canopy,
and can we avoid buying anything?

**Answer: no.** The free Scots pine's atlas is SPARSER than the incumbent's and
carries the same needle-albedo defect. Measured, not judged from a render.

## METHOD — one instrument, both assets

`fir_tree_01`'s recorded 24.02% was measured offline from its source PNG in
`Free/`. The Scots pine is KiteDemo content with no source PNG, only a `.uasset`.
Measuring one from a PNG and the other from an engine export would be TWO
instruments, so **both were exported through the engine**
(`AssetToolsHelpers.export_assets`) and measured by the same code.

**Positive control:** the fir re-measures at **23.56% above clip 0.5 and 25.06%
above clip 0.1**, reproducing the recorded 23.56% / 25.06% exactly. The
instrument is reading what it read before.

## THE MEASUREMENT

    asset                     opaque >0.5   opaque >0.1   needle albedo RGB
    fir_tree_01 twig atlas       23.56%        25.06%       85 / 81 / 49
    ScotsPine_01 atlas            8.98%         9.67%       89 / 81 / 44
    spec requirement             >= 45%                     green > red

Both atlases are 4096². The opacity mask lives in different channels:
`T_fir_tree_01_twig_alpha_4k` is `TC_ALPHA` with the mask in **RGB** (its alpha
channel is uniformly 255 and reading it gives a meaningless 100%);
`ScotsPine_01_Atlas_Tex` is `TC_DEFAULT` with the mask in **alpha**. Reading the
wrong channel on either gives a confident wrong answer — the fir's alpha reads
100.00% opaque, which would have looked like a spectacular result.

## VERDICT ON THE FREE OPTION

`scots_pine_tall` fails **both** decisive spec criteria:

- **Requirement 3, canopy density ≥45%:** 8.98%, against the fir's 23.56%. It is
  2.6x SPARSER than the asset it would replace.
- **Requirement 4, green must exceed red:** 89/81/44. Green is BELOW red, the
  same signature as the fir's 85/81/49.

It does pass on the structural criteria — 22.1 m tall (spec wants 18–35 m,
incumbent is 14.52 m), 27,824 triangles (spec prefers <200k, incumbent LOD0 is
505,494), separate `Fronds`/`Leaves`/`Branches`/`Billboard` materials, and
billboards included.

**So the palette's own note was right and is now quantified.** It reads: *"a
second conifer SILHOUETTE, not a denser fir."* That is exactly what the numbers
say. Mixing it in would break the repetition of 154,018 identical trees, which
is worth something — but it will not fix bare poles, and using it as the primary
would make them worse.

## THE CAVEAT THAT LIMITS THIS

**Atlas opacity is not strictly comparable across assets with different UV
layouts and card counts.** A tree with more foliage cards can read denser from a
sparser atlas, because density on screen is (atlas coverage x cards x card
area), and only the first term is measured here.

So this is strong evidence, not proof. What raises confidence is the second,
independent signal: the needle albedo defect is present in BOTH assets, and that
one has no layout dependence at all.

**The decisive test remains a render** — place both species and compare at a
ground station. That is cheap to do once a candidate replacement is on disk, and
it is the acceptance test already written into `plans/conifer_asset_spec.md`
section 5.

## CONSEQUENCE

The free-on-disk route does not close this. A purchase (or a free download that
is not already here) is still required, and the spec's density bar stands.
