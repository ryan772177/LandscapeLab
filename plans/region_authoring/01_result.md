## What I wrote

| File | Bytes |
|---|---|
| `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\plateau.terrain` | 15,798 |
| `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\plateau.md` | authoring note |

Produced by loading the canonical `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain` as JSON, assigning 10 scalar leaves plus 2 `Metadata` strings, and dumping. **Asserted before writing**, not after: document *shape* identical (keys/nesting/types, values excluded), `$id` list identical, `$ref` list identical, node ids + `$type`s + `SaveDefinition`s identical, `Terrain.Width/Height/Ratio` untouched. Nothing outside `terrain/regions/` was written; I did not touch `C:\Dev\...`, Gaea, or the live editor.

## Gate exit codes — verbatim

```
python scripts/read_gaea_graph.py --project terrain/regions/plateau.terrain --check-refs    exit 0
   $id defined : 82    $ref used : 23    every $ref resolves to a real $id.
python scripts/read_gaea_graph.py --project terrain/regions/plateau.terrain --check-spec    exit 0
   the graph predicts exactly the SPEC's Gaea-sourced files.
```
Passed first run; no fix was needed. `--against-build` was **not** run — there is no plateau build to run it against, which is "could not look", not a pass.

## Key parameter changes

| Node | Param | From → To | Basis |
|---|---|---|---|
| 654 `Erosion2` | `ErosionScale` | 1413.2517 → **2297.4** | **MEASURED.** 1413.2517/5000 = 0.28265 of `Terrain.Width`; ×(8128/5000 = 1.6256) = 2297.38. Both readings of the parameter recommend the same move. |
| 599 `Snow` | `SnowLine` | 0.0564 → **0.30** | Direction MEASURED (R-GAEA §2: inverted, lower = more snow). Alpine sits near-max snow; that saturates `SnowMask_Out.png` — the NN22 defect this project already hit at 99.03%. |
| 877 `Mountain` | `Height` | 2.032038 → **1.45** | Kept *above* the presumed ~1.0 crossover because **`Ridge` has only a `Seed` and no amplitude control** — dropping Mountain far hands the landform to ridged noise. Disproof written in: compare a build's `occupancy` against alpine's 0.37035172. |
| 877 `Mountain` | `Scale` | 0.749 → **0.38** | Band measured (`MountainRange.Scale` 0.3–0.82, n=49); **direction is a genuine 50/50 I could not resolve.** Alternative value 0.95 recorded so it's a one-number flip. |
| 654 `Erosion2` | `Duration` / `Downcutting` | 21.65 → **31.0** / 0.453 → **0.20** | Bands measured across 36/8 Gaea-written instances; directions inferred. |
| 4 seeds | — | π-digit runs, all inside the observed [8451, 60797] | decorrelation only |

Not changed, deliberately: `Combine.Mode` (only `Max` and `Subtract` are evidenced — I did not invent an enum string); `Terrain.Width/Height/Ratio` (coupled triple, and `Terrain.Height` is the sole input to the Z-scale chain at `rebuild_terrain.py:166-203`); the three `SaveDefinition` bases (renaming them refuses `--check-spec` with exit 4).

## Z span — a PREDICTION

`occupancy` × 2500 m, per R-GAEA §6. Estimated occupancy 0.26428 → **span ≈ 660.7 m, z_scale ≈ 129.0** (alpine measured: 0.37035 / 925.879 / 180.8358). This is a point estimate from an unverified one-parameter model with no error bar. **Report it UNKNOWN; do not type it into the import dialog** until `height_normalization.json` exists for a plateau build.

## Honest verdict: NOT achievable by parameter variation

The graph contains only peak generators, a selector, a relief-*differentiating* simulation, a surface veneer and a mask remap. The region needs three things it cannot express:

- **Flat top** — nothing clamps or compresses the upper elevation range. A dome at half amplitude is still a dome.
- **Abrupt rim** — a rim is a discontinuity in the height transfer function; there is no transfer function to shape, and `Erosion2` at long duration *rounds* breaks of slope.
- **Tarns** — Gaea's hydraulic erosion **fills** depressions (`Erosion2.Deposits` is the fill record) and snow fills hollows further. Both mechanisms destroy closed basins; none creates one.

The brief asks for **bimodal gradient** (low inboard, high at the rim). Every available knob is a global scalar on a single continuous field, and a global scalar cannot make a distribution bimodal.

**It needs two nodes, both already present in this Gaea install** (type strings and parameter names read from the 66 parsed autosaves under `%APPDATA%\QuadSpinner\Gaea\2.0\Autosaves\`, not invented):

1. **`QuadSpinner.Gaea.Nodes.Stratify`** (observed 7×; `Intensity`, `Spacing`, `Shape`, `TiltAmount`, `Seed`) — quantises height into flat treads separated by abrupt risers. That is the plateau surface *and* the rim in one node. Insert between `Combine` and `Erosion2` so erosion dissects an already-terraced field and softens the risers.
2. **`QuadSpinner.Gaea.Nodes.Lake`** (observed 62×, the corpus's most-used node; `WaterLevel`, `ShoreSize`, `Precipitation`, `AltitudeBias`, `Type`, `X`, `Y`) — fills closed depressions and yields a water mask downstream passes can consume. Without it "tarns" has no artefact behind it: there is no water surface, shoreline or mask anywhere in the current graph.

Fallback rim mechanism if `Stratify` reads too regular: **`QuadSpinner.Gaea.Nodes.Canyon`** (observed 2×; `Depth`, `Scale`, `Valley`, `StructualWarp` — Gaea's spelling).

I did **not** attempt the insertions. The cheap correct route is not a writer: open `plateau.terrain` in the Gaea GUI, drop the two nodes in, wire them, save — Gaea allocates the ids — then re-run `--check-refs`, which is exactly what that gate is for.

## Three hazards found while reading the tooling

1. `rebuild_terrain.py:89` — `DEFAULT_ROOT` is alpine's package tree. Building this without an explicit `--root` writes plateau output into alpine's `NNN` sequence. Same class as the talus cache that overwrote alpine's.
2. `rebuild_terrain.py:96,103` hardcode `AlpineLab_v1_Height_normalized.png` / `AlpineLabHeight.png`, and `verify_build.SPEC` requires those exact names — **a plateau build produces an alpine-named heightmap.** Producer and consumer are two lists that must agree (NN24), so the fix is one declaration, not two edits.
3. `Metadata.Edition` reads `"Community"` in the canonical file, saved 2026-08-09 — the same day CLAUDE.md records Indie activation with the 8K cap. **That field is not a readable source for the licence or the export cap.**