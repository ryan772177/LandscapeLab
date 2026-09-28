# FOR_CLAUDE_CODE — Brief 1 tasks

Read `CLAUDE.md` first as usual. Then `BRIEF.md` §0, §4 and §7 here; the rest of the brief is reference. Every task below ends in a measurement, a recipe field, or a REJECTED entry. Operate under the standing rules; nothing here relaxes them. Where this file says VERIFY, the ue58-api-protocol applies: open the engine source, cite the line, then act.

Session goal line suggestion: **"Brief 1: derive culls from pixels; build the benchmark; baseline the dolly."** Do not pull from BACKLOG this session.

The tools live in `scripts/` of this folder. Copy them into the repo's `scripts/` (they are new elements; the NEW-ELEMENT RULE applies — each gets a RECIPES entry when it is first used to set a value). Each has a `--selftest` or a runnable example; run it before use.

---

## Task 1 — Run the angular budget on the recipe (offline, 10 minutes)

    # run TWICE: --res 3840 2160 (the judgement camera, RULED) and --res 2560 1440 (floor)
    python scripts/angular_budget.py --fov-h 90 --res 3840 2160 \
      --object Conifer 14.7 --object ConiferPine <h> --object SpruceSub <h> \
      --object SpruceSapling 4.0 --object Blueberry 0.6 --object Meadow 0.4 \
      --object Boulder 2.5 \
      --cull Conifer 730 --cull ConiferPine 730 --cull SpruceSub 730 \
      --cull SpruceSapling 180 --cull Blueberry 45 --cull Meadow 50 --cull Boulder 140 \
      --display-ppd 45 --out _verify/bench/angular_budget_<date>.json

Heights: take from `Free/_measured/pve_spruce.json`, `pn_spruce_forest.json`, `tree_packs.json` (extent_cm z / 100), not from memory. Where a species has several meshes, use the tallest.

**Acceptance:** the JSON exists; every species with a `cull_distance_m` has a verdict. Log at both altitudes:
- LESSONS: "every authored cull removes a 10–28 px object; the pop lessons of 08-04 measured the right defect with the wrong instrument", citing the JSON.
- RECIPES: under the foliage recipe, REJECTED: `cull_distance_m` as an authored value → symptom: visible pop at 10–28 px → correct: derive from `perception.thresholds_px` (Task 6).

## Task 2 — VERIFY the ScreenSize formula (engine source, 15 minutes)

Open `Engine/Source/Runtime/Engine/Private/SceneManagement.cpp`, find `ComputeBoundsScreenRadiusSquared` and `ComputeBoundsScreenSize`. Confirm whether `ScreenMultiple` is `0.5 * max(ProjMatrix[0][0], ProjMatrix[1][1])` and whether ScreenSize is the sphere *diameter* fraction. If the tool's formula is off by a constant, fix the one function `ue_screen_size` and note the line in the tool's docstring.

**Acceptance:** a cited line in the tool docstring; `angular_budget.py` re-run; the ScreenSize column agrees with a read-back of one static mesh's LOD ScreenSize at a known distance (place a spruce at exactly 470 m from a camera, read `get_editor_property("lod_settings")` or the LOD screen sizes and the current LOD via `r.ForceLOD -1` + `stat` — a second instrument).

## Task 3 — Build the benchmark (editor, ~1 hour)

Per `benchmark.json`:
1. Three `CameraActor`s labelled `Bench_near_ground`, `Bench_mid_slope`, `Bench_vista`, find-or-create by label, `is_spatially_loaded=False`. near_ground = the 2026-09-05 rear station's recorded camera (the recipe/capture block or the perf station JSON has it); mid_slope = treeline perf station; vista = vista perf station. FOV 90 on each.
2. A Level Sequence `Bench_Dolly` : camera cut from `Bench_near_ground`, 6 s at 30 fps, moving along the camera's forward vector at 1.4 m/s (8.4 m total). Straight line, no easing.
3. Enable the **Movie Render Queue** plugin (engine plugin; record in the uproject via the editor API, standing rule 4). Two presets: `Bench_dev` and `Bench_target`, each a Console Variables setting block from `benchmark.json` profiles, output PNG 2560×1440, `target` with 8 temporal samples.
4. A driver `scripts/bench_capture.py --profile dev|target [--dolly]` that renders the three stills and, with `--dolly`, the 180 frames, into `_verify/bench/<date>/<profile>/`, and writes `bench_run.json` with: git sha, recipe sha, profile name, and **read-back** of every cvar in the profile plus FOV and resolution (read back, not requested — the fov enforcement pattern from 2026-09-05).

**Acceptance:** `_verify/bench/<date>/dev/{near_ground,mid_slope,vista}.png` exist, sidecar read-backs match the profile, and a second run on the same commit produces stills whose mean luma differs by < 0.002 (determinism check — this is the instrument's own noise floor; record it).

## Task 4 — Frame-time in a standalone process (DRAFT — VERIFY flags)

The editor game thread is pinned at ~14 ms by editor overhead; `get_viewport_size` is `None` for the same reason. Move perf stations out of the editor.

Procedure (flag names to VERIFY in `Engine/Source/Runtime/Launch/Private/LaunchEngineLoop.cpp` and `Engine/Source/Runtime/Core/Private/Misc/App.cpp`):

    UnrealEditor-Cmd.exe <LandscapeLab.uproject> /Game/Alpine8K -game -windowed \
      -ResX=2560 -ResY=1440 -NoVSync -NoSound \
      -trace=default,gpu -tracefile=<abs path>/bench_<station>.utrace \
      -ExecCmds="ViewActor Bench_vista"

- `ViewActor <label>` is a console command that sets the view target; VERIFY it accepts an actor *label* vs *name* in 5.8 (`UGameViewportClient`/`APlayerController` exec). If it wants the name, spawn the bench cameras with deterministic names.
- Run 25 s, then stop the process (the `.utrace` is complete up to the stop).
- Export: `UnrealInsights.exe -OpenTraceFile=<utrace> -ExecOnAnalysisCompleteCmd="TimingInsights.ExportTimingEvents <csv>"` — VERIFY the exact command names in `Engine/Source/Developer/TraceInsights`; alternative is the CSV profiler (`-csvGpuStats -ExecCmds="CsvProfile Start"`), which writes to `Saved/Profiling/CSV` on `CsvProfile Stop` and needs a way to issue Stop (a 20 s `-benchmark -benchmarkseconds=20` style exit, VERIFY).
- Report p50/p90 of GameThread, RenderThread, GPU per station in `_verify/bench/<date>/perf_<profile>.json`, with `get_viewport_size` now returning the real numbers (it answers in `-game`).

**Acceptance:** four stations' game-thread p90 are no longer within 0.25 ms of each other (the editor artefact is gone) and the `viewport_size` field is a number. Re-tune `check_perf` budgets against these, not the editor numbers; log the old baseline as REJECTED (instrument: editor viewport → symptom: constant 14 ms game thread → correct: standalone `-game`).

## Task 5 — Baseline the dolly and turn on fades (editor + MRQ, ~1 hour)

1. `bench_capture.py --profile dev --dolly`; run `python scripts/temporal_stability.py _verify/bench/<date>/dev/dolly/*.png --out _verify/bench/<date>/dev/stability.json`. Record **score** and the spike frames. Open the worst spike frame and name what popped (the bbox says where). This is the baseline.
2. Enable dithered LOD transitions on every foliage/tree/rock material (`bDitheredLODTransition` — VERIFY property name via `Material.dithered_lod_transition`), and instance fade on each foliage type (VERIFY the 5.8 `UFoliageType` fields: `bEnableCullDistance`, `CullDistance` min/max — the min..max range *is* the fade band; set min = derived cull − fade distance, where fade distance = 1.4 m/s × 0.35 s × (a safety factor of 10, since the fade must also cover a running player) ≈ 5 m... note: the CullDistance min/max fade needs the material to use `PerInstanceFadeAmount`; VERIFY the PN/KiteDemo materials do).
3. Re-capture, re-score.

**Acceptance:** score falls; the spike frames at the old cull distances are gone or their `largest_blob_px` shrinks by > 5×. Lock the material/foliage settings as a recipe (R-FADE) with the before/after scores as evidence.

## Task 6 — The `perception` block and derived culls (recipe + place_foliage, ~2 hours)

1. Add to `recipes/schema.md` and `alpine_8k.json`:
   `perception: {declared_camera, thresholds_px:{vanish:1.5, silhouette:6, detail:40}, fade_seconds:0.35}`.
2. Each species gains `height_m` (measured, cite the `_measured` file). `cull_distance_m` becomes **derived**: `place_foliage.py` computes `cull_cm` from `height_m`, the declared camera and the threshold appropriate to the species' *next representation*: `detail` if an imposter/HLOD exists for it (Task 7), else `vanish` — never `silhouette` with nothing behind it. Write the derivation (threshold used, px at cull, formula) into the instance JSON sidecar next to `cull_cm`.
3. `check_docs.py` / the offline suite gains a check: any species with an authored `cull_distance_m` and no `_derived` sidecar fails.

**Acceptance:** re-placement produces the same instance set (seeded) with new `cull_cm`; the sidecars carry derivations; the suite passes; RECIPES has the `perception` block documented with the derivation formula and the REJECTED authored-cull entry from Task 1.

## Task 7 — Imposters and HLOD (editor, half a day; do after 5 and 6)

1. Enable the engine **ImpostorBaker** plugin. Bake octahedral imposters for Conifer, ConiferPine, SpruceSub at 2048² atlas, 12×12 frames (VERIFY the plugin's 5.8 parameter names). Add the imposter as the last LOD of each tree static mesh (or as a separate foliage type with cull [detail_m, silhouette_m]).
2. Set the mesh cull to the derived **detail** distance (~470 m for the spruce) and the imposter cull to the derived **silhouette** distance (~3.1 km), both with fades.
3. Build World Partition HLOD for the foliage cells using the **Approximated Mesh** layer; on the generated HLOD material set roughness 1, disable specular/metallic (community-reported necessity; VERIFY by inspecting the generated material).
4. Re-capture vista and mid_slope at both profiles; re-score the dolly.

**Acceptance:** in the vista still, tree-coloured coverage in the 1–3 km band is within 15% of the same band in a control render with `r.ViewDistanceScale 100` and culls disabled (the "truth" frame, slow but valid as an instrument); the dolly score does not rise versus Task 5; frame time at the vista station (Task 4) falls or holds. Lock as R-LADDER with the four-band table from BRIEF §4.

## Task 8 — LOD chains by silhouette (editor renders + offline, ~1 hour)

For each tree and rock mesh: render each LOD on a magenta background from one fixed camera (force with `r.ForceLOD n`, capture at 1024² with the object filling ~80%). Run

    python scripts/lod_silhouette_check.py --lod LOD0.png <px0> --lod LOD1.png <px1> ...

with `<pxN>` = the pixel height at which LOD N first appears (from ScreenSize, Task 2). Any FAIL names the chain to rebuild by coverage, not triangles.

**Acceptance:** a table in `_verify/bench/<date>/lod_silhouette.json`; FAILs go to BACKLOG as named items with the failing metric.

## Task 9 — Nanite Foliage / PVE evaluation (LAST; only after 5–7 have numbers)

One species, one benchmark cell, both profiles. Enable the Procedural Vegetation Editor plugin (experimental) and Nanite Foliage per the 5.8 docs; generate one spruce; place it at the near_ground and vista stations at the same density as the current Conifer. Capture stills and dolly; frame time via Task 4.

**Acceptance is a comparison, not a threshold:** dolly score, vista coverage, near_ground detail (a crop at 100%), and p90 frame time, side by side with the imposter/HLOD ladder. Write the decision as a ruling request for Ryan with the numbers; do not migrate on the docs' promise. If the iGPU cannot run it at all, that is a finding, not a failure — record it and stop.

---

## Order and dependencies

1 → 2 → 3 → 4 (independent of 5+) ; 3 → 5 → 6 → 7 → 8 ; 9 last. Tasks 1–3 fit one session. Commit after each task; branch before 7 (mass foliage change — RISKY-OP CHECKPOINT).

## What to send back to the research desk

`_verify/bench/<date>/` in full (stills, dolly frames as a zip or a sample of every 10th frame, `bench_run.json`, `stability.json`, `angular_budget_*.json`, `perf_*.json`), plus the LESSONS/RECIPES diffs. Brief 2 (atmosphere, sky light and grade — the blue-shadow and no-haze findings from the rear station) is written against those frames.
