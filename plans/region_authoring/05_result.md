Work complete. Deliverable below; no further changes made.

**Wrote**
- `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\foothills.terrain` — sha256 `ea03912badc373c90faab6607c48f9ca89dd3b7ee1e8d7f33219046d463d5021`
- `C:\Users\Admin\UE5LandscapePipeline\terrain\regions\foothills.md`

Copied from canonical `C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\AlpineLabe_v1.terrain` (confirmed canonical: not in the Autosaves directory, hash matches none of the 66 autosaves there). Parameter values only — no node added, removed or rewired.

**Gate exit codes, verbatim**
```
read_gaea_graph.py --project terrain/regions/foothills.terrain --check-refs   exit=0
read_gaea_graph.py --project terrain/regions/foothills.terrain --check-spec   exit=0
                                        (both flags in one run)               exit=0
```
Passed first attempt. `$id defined : 82 · $ref used : 23 · every $ref resolves to a real $id`. Recursive JSON diff confirms **8 leaf differences, all intended**; `$id` and `$ref` lists identical in order and count; node ids identical.

**Key parameter changes**

| Node | Parameter | Alpine → Foothills |
|---|---|---|
| Mountain 877 | `Height` | 2.032038 → **1.0** |
| Erosion2 654 | `Downcutting` | 0.4531411 → **0.25** |
| Erosion2 654 | `Duration` | 21.648195 → **28.0** |
| Snow 599 | `SnowLine` | 0.056395777 → **0.35** |
| all four | `Seed` | 22109/38804/15025/59434 → **30411/51862/27703/44190** |

Both Erosion2 values land inside bands observed in Gaea's own projects; alpine's sit outside them. `SnowLine` rises because the control is inverted (R-GAEA §2), and must be moved explicitly because `Snow.RealScale` is `false` — lowering the mountain does not lower the snowline. `ErosionScale`, `Mountain.Scale`, `Combine.Mode`, `Snow.Intensity` and the `Terrain` extent were all held, each for a stated reason.

**Z span: UNKNOWN** — the method needs occupancy measured from a build, and none exists. Direction is known (less relief than alpine); magnitude is not. `rebuild_terrain.py` writes the real value to `height_normalization.json`.

**Verdict — partly achievable by parameter variation.** Delivered: lower relief, gentler slopes, a mature drainage network with a legible trunk, light snow. Not delivered: broad terraces, a valley positioned where a town should sit, flat buildable ground. **The region as described needs one structural addition — a `Stratify` node between Combine (750) and Erosion2 (654)** — evidenced by an autosave carrying one with its full parameter set and by the DLL metadata heap at offset 712708. Not added, because it requires the `$id` allocation this project deliberately has no writer for.

**Build notes:** pass `--root` (default targets the AlpineLab_v1 tree) and `--ignore-cache` on first build. `rebuild_terrain.py:96` names the output for region one regardless of input — flagged, not fixed.

Nothing was executed: no Gaea, no editor, no build, no writes outside `terrain\regions\`.