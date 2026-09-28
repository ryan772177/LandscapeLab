## What I wrote

- `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\coastal.terrain` — 16,196 bytes
- `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\coastal.md` — the authoring note

Nothing else on the machine was written. No Gaea, no editor, no connection to the live session.

## Gate exit codes (verbatim, run from `C:\Users\Admin\UE5LandscapePipeline`)

```
python scripts/read_gaea_graph.py --project terrain/regions/coastal.terrain --check-refs
  $id defined : 82      $ref used : 23      every $ref resolves to a real $id.
  EXIT 0

python scripts/read_gaea_graph.py --project terrain/regions/coastal.terrain --check-spec
  the graph predicts exactly the SPEC's Gaea-sourced files.
  EXIT 0
```

`$id`/`$ref` counts are identical to the canonical file's. `prove_gaea_reader.py` re-run in the same session: **exit 0**, 5 corruptions refused (rc 4/4/4/3/6) — so the pass is a measurement, not a permissive gate.

**Invocation note:** the tool takes `--project <path>`. The brief's form `--check-refs <file>` exits **2** with argparse's *"unrecognized arguments"* — not a graph verdict.

**A full line diff against the canonical returns exactly the 10 edited leaves and nothing else.** The 31-byte size delta (16,227 → 16,196) equals the sum of the shortened numeric literals — an independent arithmetic check.

## Key parameter changes

| Node | Param | From → To | Class |
|---|---|---|---|
| 654 Erosion2 | `ErosionScale` | 1413.2517 → **400.0** | MEASURED ratio |
| 877 Mountain | `Height` | 2.032038 → **1.05** | topology-grounded |
| 599 Snow | `SnowLine` | 0.056395777 → **0.62** | MEASURED mechanism |
| 877 Mountain | `Scale` | 0.74927175 → **0.42** | hypothesis |
| 654 Erosion2 | `Downcutting` / `Duration` | 0.4531411 → **0.78** / 21.648195 → **14.0** | hypothesis |
| 4 seeds | Mountain/Ridge/Erosion2/Snow | re-rolled | — |

`ErosionScale` is the one change resting on arithmetic: 1413.25/5000 = 0.28265 of `Terrain.Width`; at the 8128 m import that lands at ~2,297 m (glacial-valley scale). 400.0 = 0.08 of canvas → **650.2 m** in UE, which is inlet scale. `Mountain.Height` down is argued from the wiring I read (node 750 `Mode: "Max"`), not the name — it shifts the Max arbitration toward `Ridge`, whose crests are the closest available analogue to spurs and inlets.

**Deliberately unchanged:** `Snow.Duration/Intensity/SettleThaw/Melt` (only `SnowLine`'s mechanism is measured — R-GAEA §2's inversion); `Combine.Mode` (other enum members are strings I never read — NN23); `PortCount` (structure in parameter clothing); everything outside `Nodes`.

**Predicted Z:** span and `z_scale_cm` **below** alpine's 925.879 m / 180.8358 — both height levers moved down and nothing moved up. **No magnitude is predicted**: `Ridge` carries no `Height` in this file, so its default amplitude floors the span and I could not measure it. This is a PREDICTION until `height_normalization.json` exists.

## Honest verdict: THE REGION IS NOT ACHIEVABLE BY PARAMETER VARIATION

Three things are missing and none is a number:

1. **No node has a concept of absolute height.** No clamp, floor or flood. A datum is a floor operation; there is no floor operation in the file.
2. **No node has a concept of direction.** `Mountain` and `Ridge` are whole-canvas generators with no offset serialised. "Low at one edge, rising inland" has no directional term to vary.
3. **Downstream normalisation is a linear stretch** — it *preserves* a flat region but cannot *create* one.

**The node needed — read, not proposed:** `QuadSpinner.Gaea.Nodes.Sea, Gaea.Nodes`, node 243 of `C:\Program Files\QuadSpinner\Gaea 2\Examples\Canyon River with Sea.terrain`, with `Level` 0.02, `ShoreSize`, `ShoreHeight`, `Variation` and ports `In/Out/Edge/Water/Depth/Shore/Surface`. `Level` is the datum; `Shore*` is the cliff transition; `Water/Depth/Shore` are ready-made coastal masks.

`Sea` **alone** gives a genuine drowned-valley (ria) coast — headlands and coves, Brittany/Cornwall form — and this file's fine `ErosionScale` is exactly the input that makes it work. For "sea at one edge, rising inland" you additionally need `QuadSpinner.Gaea.Nodes.LinearGradient` (`Direction: 270` at node 616 of `Cartography - Mineral Map.terrain`), which also forces `Combine.PortCount` 2→3 or a second Combine.

**So this file will build a finely dissected ridge-dominated upland with inlet-scale incision and inland-only snow — not a coastline.** It is committed as the evidence for the structural finding, not as a region.

## Three findings that outrank the file

1. **`RECIPES.md` R-GAEA §1 says `Snow Line ~0.65`; the canonical file says `0.056395777`** — opposite ends of an inverted control, in a summary block. Reported, **not fixed** (Ryan's file).
2. **A snow-free region cannot pass `verify_build.py`.** `Snow_Snow.png` is required (`verify_build.py:80-83`) and `MIN_UNIQUE = 16` at `:59`/`:294` refuses a degenerate mask. `SnowLine` 0.62 is chosen to stay above that floor; the gate is the untested test.
3. **`rebuild_terrain.py` cannot build a second region** — `DEFAULT_ROOT` `:89`, `HEIGHT_OUTPUT` `"AlpineLab_v1_Height_normalized.png"` `:96`, `HEIGHT_IMPORT_ALIAS` `:103`, all keyed to alpine, with `verify_build.SPEC` keyed on the same filename. `--root` fixes the directory; the **filename** cannot be fixed by a flag. Same class as CURRENT STATE 2026-08-14's seven-parameter table; non-negotiable 19.

**Not verified:** no build ran, so every landform claim is a prediction. Six of the ten changes rest on parameter names only and are tagged HYPOTHESIS in the note. `Mountain.X/Y` and `Erosion2.Direction/RainShadow` exist as real properties (read from the example corpus, omitted from ours because Newtonsoft skips defaults) — I did **not** add them, because their defaults are unknown to me and neither produces a datum; recorded as the next parameter-level experiment and as an open question about where the "parameter edit" envelope ends.