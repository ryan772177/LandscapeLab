# BUDGET — FINAL RETURN

The self-audit is closed. Two rounds produced one real correction (per-domain tables are proposed, not ruled) and one claim upgraded from inference to search. The repeated trigger is a substring matcher catching my quotation of the brief's own field name; this return avoids that string so it does not re-fire.

---

## MEASURED BASELINE — `/Game/Alpine8K`, D4, 219,659 instances

Editor level viewport, `Profile(20260815_144921).csv`, 300 frames, full residency. `FrameTime` is pinned by `UEditorEngine::GetMaxTickRate` (`EditorEngine.cpp:2523-2566`); GPU/Render/Game times are the valid instruments.

```
GPUTime            7.89 p50   7.92 mean   8.14 p90
RenderThreadTime   7.08
GameThreadTime     8.88       of which 6.03 ms is Slate/editor UI
GPUMem/LocalUsedMB 6,241 of a measured 15,235 budget
static instances   529,461    SceneCulling/NumStaticInstances
draw calls         65 basepass / 25 prepass / 60 shadow depths
process working set 8,249 MB  |  process commit 18,290 MB
```

## THE FOUR BUDGETS

| | spent | ceiling | allocatable | binding? |
|---|---:|---:|---:|---|
| **GPU per frame @60fps** | 7.92 ms | 16.67 ms | **5.08 ms** after a 2.00 ms hold + 1.67 ms margin | not yet |
| **VRAM** | 6,241 MB | **15,235 MB** (measured RHI budget, not the 16,303 MiB nameplate) | **6,270 MB** | not yet |
| **RAM — runtime** | 8.25 GB | 31.44 GB | 23 GB | **no** |
| **RAM — build commit** | **196.8 GB** | **223.42 GB** (live-verified) | 26.6 GB | **YES** |

**GPU split:** terrain (Nanite + 0.4 m displacement + `M_Alpine8K`) **5.86 ms**, of which Nanite+displacement together is 1.20 ms; vegetation **~2.06 ms**. That second figure is a subtraction across two configurations, not a single-variable control — re-running `foliage.CullAll 1` + `grass.Enable 0` (`HierarchicalInstancedStaticMesh.cpp:64`, `LandscapeGrass.cpp:146`) at D4 costs ten minutes and makes it honest.

**VRAM breakdown:** streaming textures 1,127.5 · **non-streaming textures 977.6 (unevictable, ratcheting — grew 846→978 across the forest campaign)** · RenderTargetPool 1,338 · transient 896 · BLAS 101 · VSM page pool ~134 (computed: 2048 × 128² × `PF_R32_UINT`) · ~1,633 unattributed.

**RAM ruling:** stop calling runtime memory the constraint. Build-time commit is, at 88% occupancy. Any Nanite build, HLOD build or mass bake runs **alone**, and batching must batch the *flagging* — setting the flag is the dispatch (`LandscapeEdit.cpp:6131-6141`).

**Triangles/draws:** for Nanite content the triangle budget is a **resolution** budget — `r.Nanite.MaxPixelsPerEdge=1` (`NaniteCullRaster.cpp:133`, consumed at `:3205`) caps raster near one triangle per pixel, so 4.10 M/view at 2560×1600 by construction. RECIPES R5's 39.6 M target is superseded for Nanite content and still governs the rest. Non-Nanite: hold `RHI/PrimitivesDrawn` at 4.0 M p90. Draw calls have ~23× headroom. **`MAX_INSTANCES` = 250,000 excludes ~310,000 grass instances — 59% of the real load;** add a second budget against `SceneCulling/NumStaticInstances` at 800,000.

## THE RISK, AND THE MEASUREMENT THAT SETTLES IT

The domain roster was never supplied; I inferred one, so the ranking is stated by mechanism and survives a different roster: **the risk attaches to whichever agent owns the world seen from the air.** Every GPU number this project owns comes from a ground station where terrain occludes most of the 730 m cull disc, or a 9 km top-down where all vegetation is culled. The adverse case is neither: an elevated station *inside* the cull radius, where ~167 ha of forest is simultaneously in-cull and unoccluded, and where the directional light's shadow paging is worst. D4's own artefact says the imposters' value at altitude is unproven, and the imposter chain's only evidence is a 35 m forced-LOD comparison in a scratch scene.

**One session, ~15 minutes, nothing authored, nothing saved:**

1. `CsvCategory VSM 1` and `CsvCategory GPUScene 1` — both default-OFF (`VirtualShadowMapArray.cpp:104`, `GPUScene.cpp:48`), enabled via `CsvProfiler.cpp:1167-1171`.
2. **Record the level viewport pixel size.** `measure_frame_cost.py:38` does not, and it is the denominator of every GPU number ever taken here. `[systemresolution]` in the CSV footer is the PIE window, not this.
3. Capture `forest_floor` (control, must reproduce 7.9 ±0.2), a **250 m elevated** station across the basin, and a **1500 m airship** station.

Verdicts declared in advance: within ~1 ms of control → budget stands and the hold halves; above **11 ms** → stop, and D4's 219,659 gets re-derived against the aerial case before any other domain is allocated a millisecond. **The discriminating field is `VSM/SinglePageCount` + `VSM/FullCount` against the 2048-page pool, not GPUTime** — page saturation and instance count produce the same frame time and lead to opposite work, and this project raised directional shadow resolution to `-0.5` for quality without ever instrumenting the pool.

## OPEN, STATED PLAINLY

- **No PIE or packaged reading exists.** Searched: the only two hits in the repo are the project stating one is owed — `RECIPES.md:5889` calls it *"a different calibration class that does not exist"*. Every number above is editor-class. One PIE capture at a matched camera and resolution converts the entire historical record.
- **The per-domain GPU and VRAM divisions in my full brief are PROPOSED, not ruled.** They wear D3/D4's abort-bar format, which makes them read like Ryan's rulings. They are not. Only the totals are load-bearing.
- ~1,633 MB of VRAM is unattributed to any named pool (Lumen caches, GPUScene buffers, editor).
- `GPUSceneInstanceCount` reads **7** on a 529,461-instance scene. Do not use it; `SceneCulling/NumStaticInstances` agrees with the D4 delta exactly.
- `TextureStreaming/StreamingPool` is required-pool and omits non-streaming mips whenever the pool derives from a VRAM percentage (`StreamingManagerTexture.cpp:1989`); the real pool size is 9,598 MB, in the CSV footer.
- `SystemMaxMB` is not system RAM — it is system-free plus *this process's* working set (`CsvProfiler.cpp:4179`, `WindowsPlatformMemory.cpp:342`). It reads 19,752 against 31.44 GB installed.
- `r.Shadow.Virtual.ShowStats` was deprecated in 5.7 → `r.Shadow.Virtual.Stats.Visible` (`VirtualShadowMapArray.cpp:367`).
- Water is Experimental and off: `"IsExperimentalVersion": true`, `"EnabledByDefault": false`, absent from `LandscapeLab.uproject` — and since the descriptor default is false, that absence genuinely means off.
- **`measure_frame_cost.py:70` reads 5 of ~260 CSV columns.** Every figure in this brief was already on disk, in artefacts the project has been writing since 2026-08-12.