# Eroded badlands and canyon — region file written

## What I wrote

| File | Bytes |
|---|---|
| `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\badlands.terrain` | 16,368 · sha256 `95f89b93…` |
| `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\badlands.md` | authoring note |

Derived from the canonical `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain` (sha256 `459d5c2f…`), confirmed canonical: a recursive search of `C:\Dev\LandscapeLab` returns exactly one `AlpineLabe_v1*.terrain`; the 90 autosaves live under `AppData\Roaming\QuadSpinner\Gaea\2.0\Autosaves` and none is named `AlpineLabe_v1`.

**Parameter substitution only.** Exact unique whole-line string replacements on the source text — no JSON round-trip, so `$id` numbering and document order could not move. The generator asserted four invariants *before* writing (skeleton equality with leaves erased, identical node set, identical `$type`, identical key set per node) and refuses rather than writes. 18 lines differ; all 18 are values.

## Gate exit codes, verbatim

```
python scripts/read_gaea_graph.py --check-refs --project terrain/regions/badlands.terrain
  $id defined : 82 · $ref used : 23 · every $ref resolves to a real $id
  EXIT = 0

python scripts/read_gaea_graph.py --check-spec --project terrain/regions/badlands.terrain
  the graph predicts exactly the SPEC's Gaea-sourced files
  EXIT = 0
```

`prove_gaea_reader.py` re-run against this tree: accepts the shipped graph (rc=0), still refuses all five corruptions (rc=4,4,4,3,6), **exit 0** — so those are live gates, not dead ones. `--against-build` was **not** run and could not be: nothing has been built. That is "I could not look", not a pass.

## Key changes

| Parameter | From | To | Provenance |
|---|---|---|---|
| `Erosion2.ErosionScale` | 1413.2517 | **340.0** | **MEASURED** — 0.28265→0.068 of Width; ×1.6256 import stretch puts drainage spacing at 553 m not 2297 m. Gaea itself has written 122.996 |
| `Erosion2.Duration` | 21.648195 | 30.5 | inside observed band 23.16–32.0 (`Migration_Bisect_A_LakeNode`) |
| `Erosion2.Downcutting` | 0.4531411 | 0.78 | **most speculative number in the file** — extrapolated past every observed value |
| `Mountain.Height` | 2.032038 | 0.62 | inferred; makes erosion the landform, not decoration |
| `Mountain.Scale` | 0.74927175 | 1.34 | inferred |
| `Snow.SnowLine` | 0.056395777 | 0.88 | **MEASURED inverted** (R-GAEA §2 + autosave trace 0.68–0.78 vs 0.056) |
| `Terrain.Height` | 2500.0 | **1200.0** | the Z-derivation multiplier; `Ratio` moved 0.5→0.24 to stay consistent |
| all four `Seed`s | — | changed | a different region must be a different terrain |

**Z span is a PREDICTION.** Occupancy is unknowable until a build normalises. Borrowing alpine 006's `occupancy 0.37035`: span ≈ **444.4 m**, `z_scale_cm` ≈ **86.8**; the note carries a 0.25–0.55 band (58.6–128.9). `height_normalization.json` remains the value of record.

## Verdict on achievability — partial, and the gap is structural

**Parameter variation does change landform class.** Base amplitude down 70%, erosion at 24% of its scale, all seeds new — this will not read as the alpine mountain rescaled.

**It cannot deliver the region as briefed**, for three reasons no parameter reaches:

1. **No flat interfluves.** Badlands are a *dissected plateau*; `Mountain + Ridge → Combine[Max]` is peaked by construction. `Ridge` serialises **only `Seed`** — no amplitude knob — so ridgelines cannot be attenuated. `Mountain.Height` scales amplitude, not shape: you get dissected *hills*, not dissected *plateau*.
2. **No canyon.** `Erosion2` produces a drainage-network statistic, not a discrete trunk canyon.
3. **No stratified banding**, the visual signature of the class.

I did **not** flip `Combine.Mode` to `"Subtract"` (a legal observed value) — unpredictable without a build, and shipping a mode flip I can't reason about is guessing dressed as authoring. `PortCount` is `$id`-coupled and forbidden.

**Two nodes close it, both read from real Gaea files on this machine — named, not added:**

- **`QuadSpinner.Gaea.Nodes.Stratify`** (`Migration_Bisect_A_LakeNode_2026-08-13_22-13-45.terrain`, node 328 `Fantasy_Shelves`: `Spacing 0.24, Intensity 0.38, Shape 0.5, TiltAmount 0.12, Seed`). Inserted between `Combine`(750) and `Erosion2`(654) it imposes bedding *before* erosion cuts it — **one node buys gaps 1 and 3 together**, since bedded rock erodes differentially into caprock-held flats.
- **`QuadSpinner.Gaea.Nodes.Canyon`** (`Untitled_2026-08-11_22-27-09.terrain`, node 645, serialising only `Seed`). I have not read its full parameter surface and will not guess it.

Recommended order: build *this* file first — it is the controlled single-variable answer to the question the brief asks, and it produces the missing occupancy. Then add `Stratify` alone.

## One trap worth surfacing

**Snow cannot be turned off**, though the region is arid. `verify_build.SPEC:65-84` requires `Snow_Snow.png` and `SnowMask_Out.png`; `MIN_UNIQUE = 16` (`:58`, refusal `:294-295`); R-GAEA §2 records Gaea 2.3 exporting a degenerate near-1-bit PNG on a uniform sim. `SnowLine 1.0` would make both degenerate and the build would be refused. Hence 0.88/0.11 — which repurposes them as a **caprock/mesa-top mask**, genuinely what a badlands material wants, but the file and SPEC still call them snow. **Whether 0.88 keeps both above `MIN_UNIQUE` is the most likely first-build failure**; the fix is to lower `SnowLine`, nothing else.

Also flagged, outside my write scope: `rebuild_terrain.py:96` hardcodes `HEIGHT_OUTPUT = "AlpineLab_v1_Height_normalized.png"`, so building this project emits a badlands heightmap under an alpine filename.

Not done: no `recipes/badlands.json`, no `ASSETS.md` row, no `RECIPES.md` entry — the new-element rule is **not** satisfied. And `WORLD_VISION.md:171-177` records multi-region as an open decision with a tripwire; `:263-292` records that a region's landform must *mean* something, and no such reading is authored for this one.