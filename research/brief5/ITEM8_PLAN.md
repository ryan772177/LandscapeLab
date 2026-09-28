# Item 8 plan — measure the HLOD proxy GPU share via a `-game` MRQ HLOD-toggle

**SCOPING ONLY (2026-09-20/21). No runs, no asset/ini/Python changes made.** The
desk rules on this; nothing here is executed. Builds on the v3 finding that the
HLOD proxy GPU *share* is INCONCLUSIVE because no in-fence channel could toggle
`wp.Runtime.HLOD` after the far cells stream (`hlod_task2_gamepath.md`).

## The problem, restated
`wp.Runtime.HLOD` is a console **command** (`FAutoConsoleCommand`,
`HLODRuntimeSubsystem.cpp:149`) that acts only on a live game world. Startup
`-ExecCmds` (`UnrealEngine.cpp:2552` → `GEngine->DeferredCommands`) is one-shot
and fires before the 512 m+ cells stream, so it has no effect (proven: as-is vs
hidden `-game` runs byte-identical on every render counter). We need a channel
that runs the command AFTER world load, in a rendering process, without touching
the shipped world.

## Post-world-load delivery channels

| channel | header:line | runs post-load? | fence | verdict |
|---|---|---|---|---|
| **MRQ `StartConsoleCommands`** | `MoviePipelineConsoleVariableSetting.h:72` (`StartConsoleCommands`, `TArray<FString>`; `:79` `EndConsoleCommands`) | **YES** — `UMoviePipelineConsoleVariableSetting` runs its start commands when the shot begins, after the world is loaded and streamed | needs a LevelSequence + MRQ config ASSET (see fence note) | **RECOMMENDED.** Put `wp.Runtime.HLOD 0` in `StartConsoleCommands` for the "off" arm; empty for the "as-is" arm. Two renders → the A/B. |
| startup `-ExecCmds` | `UnrealEngine.cpp:2552` | no (one-shot, pre-stream) | in-fence | **REJECTED** — proven no effect (v3). |
| `ConsoleVariables.ini [Startup]` | (config) | no (startup, cvars only) | ini change = out-of-fence | **REJECTED** — `wp.Runtime.HLOD` is a command, not a cvar; and it edits an ini. |
| Level Blueprint `BeginPlay` | (asset) | yes | edits the level = out-of-fence | rejected for this world; a SCRATCH map could host it (heavier than MRQ). |

## Positive control (all three wanted; the frame diff is the strongest)
1. **Render counter in the MRQ CSV** — enable the CsvProfiler for the render and
   read `ActorCount/WorldPartitionHLOD`, `GPUSceneInstanceCount`,
   `SceneCulling/NumStaticInstances` (the same columns v3 used). If the "off" arm
   drops these vs the "as-is" arm, the command APPLIED. This is the pass/fail the
   `-game` startup path failed (counters were identical).
2. **Frame pixel diff in the beyond-512 m region** — A/B output frames from the
   identical camera; a non-trivial difference past 512 m proves the proxies were
   being drawn (and hiding them changed the image). Strongest control, and gives
   the pixel fraction directly.
3. **`wp.Runtime.ToggleDrawRuntimeHash2D`** (`WorldPartitionSubsystem.cpp:108`,
   `FAutoConsoleCommand`, toggles `GDrawRuntimeHash2D`) — a 2D debug overlay of
   the loaded/unloaded cells. Proves which cells are resident (so which render as
   HLOD), but it is a DEBUG DRAW and may not composite into the MRQ final output;
   treat as an editor/PIE viewport aid, not the primary control. UNVERIFIED
   whether it appears in an offscreen MRQ frame.

## The measurement
1. Two MRQ renders of the SAME vista (and treeline) LevelSequence, offscreen:
   arm A `StartConsoleCommands=[]`, arm B `StartConsoleCommands=["wp.Runtime.HLOD 0"]`.
2. Per arm: MRQ CSV (GPUTime + the counters above) over the steady frames, plus
   the output frames.
3. HLOD share = arm A − arm B GPU, quoted × min_detectable (Task-1 noise floor at
   that station). Frame diff past 512 m = the pixel fraction (closes the derived
   `proxy_fraction 0.05727` vs live).
4. Verdict vocab: MEASURED (control passed, Δ ≥ 1× min_det) / MEASURED-NEGLIGIBLE
   (control passed, Δ < 1×) / INCONCLUSIVE (counters unchanged = command still not
   applied).

## Fence decision the desk must make
The `-game` MRQ process itself mutates nothing and restores by exit (like the
perf runs — in-fence). **But it needs two throwaway ASSETS**: a vista/treeline
`LevelSequence` and a `MoviePipelineQueue`/config carrying the
`UMoviePipelineConsoleVariableSetting`. Creating assets is OUTSIDE the current
read-only fence. Precedent for a bounded exception: the `ForgeScale`
scratch-asset pattern (`/Game/Scratch/…`, deleted after). **The desk must
authorize scratch-asset creation under `/Game/Scratch/` (built via the UE Python
API, not hand-edited `.uasset`), deleted at session end, world byte-identical
after.** Without that ruling, item 8 stays blocked.

## DEVICE_HUNG mitigations (machine has a GPU-reset history)
- `-RenderOffScreen` (removes the viewport present path that crashed
  `D3D12Viewport.cpp:537` on 2026-09-12).
- Render at 1080p, not 4K, with low temporal-sample / tile counts; deferred
  MRQ renderer.
- Poll VRAM (nvidia-smi) vs the 13,312 MiB abort ceiling; abort the render if it
  approaches.
- GPU SAFETY rule: one DEVICE_HUNG → close all, wait 5 min, retry that render
  once; a second → stop all GPU work, keep the read-only derivation of record.
- Keep the derived `proxy_fraction 0.05727` (88,065/1,537,813 non-sky px) as the
  fallback instrument of record if the render cannot complete.

## Levers table (every row FILLed)

| lever | header:line | role in item 8 |
|---|---|---|
| `wp.Runtime.HLOD` | `HLODRuntimeSubsystem.cpp:149` | the toggle (arm B StartConsoleCommand) |
| MRQ `StartConsoleCommands`/`EndConsoleCommands` | `MoviePipelineConsoleVariableSetting.h:72` / `:79` | the post-load delivery channel |
| `wp.Runtime.ToggleDrawRuntimeHash2D` | `WorldPartitionSubsystem.cpp:108` | candidate residency overlay (weak control) |
| render counters | CSV cols `ActorCount/WorldPartitionHLOD`, `GPUSceneInstanceCount`, `SceneCulling/NumStaticInstances` | positive control #1 |
| `r.GPUCsvStatsEnable` | (perf_standalone uses it) | per-pass GPU columns in the MRQ CSV |
| VRAM ceiling | `docs/environment.md` 13,312 MiB abort | DEVICE_HUNG guard |
| `-RenderOffScreen` | `launch_editor.ps1` / R-EDITOR-CLOSE | crash-site removal |

## One-line ask for the desk
Rule on the scratch-asset fence exception (LevelSequence + MRQ config under
`/Game/Scratch/`, Python-built, deleted after). With that, the MRQ
`StartConsoleCommands` channel + the render-counter/frame-diff controls give the
first true HLOD-share measurement; without it, item 8 stays INCONCLUSIVE.
