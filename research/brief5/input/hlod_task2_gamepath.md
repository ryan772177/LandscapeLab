# Brief 5 v3 Task 2a/2b — the `-game` HLOD channel, and why it cannot measure the share

**2026-09-20. Read-only: engine-source reads + analysis of existing `-game` CSVs.
No world/asset/ini/plugin change.**

## Task 2a — the post-world-load console channel in `-game`: FOUND, and its limit

**Verified at the 5.8 header (standing rule 9):**

- `wp.Runtime.HLOD` is an **`FAutoConsoleCommand`** (a command, not a cvar),
  registered as `UWorldPartitionHLODRuntimeSubsystem::EnableHLODCommand` at
  `Engine/Source/Runtime/Engine/Private/WorldPartition/HLOD/HLODRuntimeSubsystem.cpp:149-187`.
  Its lambda sets the static `WorldPartitionHLODEnabled` (declared line 147,
  default `true`) and, **only for worlds where `World->IsGameWorld()`**, iterates
  loaded cells calling `HLODObject->SetVisibility(...)`. Confirms audit A3: it is
  a Cmd with no value to echo, and it does nothing until a game world exists.
- The static `WorldPartitionHLODEnabled` is also read on the HLOD
  register / cell-show path (same file, lines 282, 316, 447, 466, 484), so an
  early set *would* propagate to cells that register afterward.

**How `-ExecCmds` is dispatched (verified):**
`-ExecCmds=` and `-EXEC=<file>` both route to `GEngine->DeferredCommands`
(`Engine/Source/Runtime/Engine/Private/UnrealEngine.cpp:2548` and `:2552` via
`ParseExecCommands::QueueDeferredCommands`). Deferred commands run on the first
engine tick after init.

**They DO run post-PlayerController — the "deferred warning" was a misread.**
In `perf_standalone_treeline_nohlod.log`:
- `:10008  LogCheatManager: BugItGo to: X=-190000 ...` — BugItGo (in the same
  ExecCmds batch) actually executed, so a PlayerController/game world existed
  when the batch ran.
- `:10011  LogEngine: Warning: 	BugItGo -190000.0 ...` — every ExecCmds command
  is echoed as a `LogEngine: Warning: <cmd>` line. **That echo is what the v2
  STATE/audit read as "wp.Runtime.HLOD deferred/never applied". It is the normal
  echo, not an error and not proof of non-execution.**

So there is a channel and the commands run. The limitation is **timing, not
delivery**: the batch fires once, on the tick BugItGo also moves the camera, so
`wp.Runtime.HLOD 0` runs before the treeline camera's far cells have streamed in,
and there is **no post-settle re-fire** reachable without touching an ini
(`ConsoleVariables.ini`), an asset (level Blueprint), or Python — all outside the
fence. `-EXEC=<file>` is the same deferred batch, not a delayed one.

## Task 2b — the `-game` A/B: BLOCKED as a controlled measurement (positive control fails)

The positive control requires a render-side counter to CHANGE between the as-is
and HLOD-off arms. It does not. Tail means (last 1500 frames) of the on-disk
as-is vs nohlod runs (2026-09-20):

| counter | treeline as-is | treeline nohlod | plaza as-is | plaza nohlod |
|---|---|---|---|---|
| GPUSceneInstanceCount | 57876 | 57876 | 196553 | 196553 |
| SceneCulling/NumStaticInstances | 57870 | 57870 | 196547 | 196547 |
| ActorCount/WorldPartitionHLOD | 443 | 443 | 422 | 422 |
| GPUTime (mean) | 6.92 | 6.92 | 9.14 | 9.15 |

**Identical on every counter.** So the startup `wp.Runtime.HLOD 0` produced no
measurable render-side change, for one or both of these reasons — both fatal to
the `-game` A/B as an instrument:

1. **Timing** (above): the toggle fired before the far cells streamed, and cells
   whose source is loaded keep their HLOD hidden anyway
   (`WorldPartitionHLODEnabled && !bIsCellVisible`), so the one-shot toggle
   changed nothing visible at the settled camera.
2. **The counter is partly blind to HLOD.** `GPUSceneInstanceCount` counts
   ISM/HISM instances. A **Merged** HLOD proxy is a single combined (Nanite)
   static mesh per cell, not an instance, so merged-proxy rendering would not
   show in GPUSceneInstanceCount even if it were substantial. (The resident
   proxies sampled are `Alpine8K_HLODLayer_Instanced_L0/L1`, which *are*
   instanced, but only 443/422 actors are resident and their contribution to the
   57876/196553 did not move.)

**Verdict for the `-game` path: cannot deliver a positive-control-passing
measurement inside the fence.** Per the queue, fall to Task 2c (editor A/B, but
first PROVE the proxies render) + Task 2d (distance probe from bounds). Recorded;
fence not widened.

## Correction to prior records

- `hlod_share.json` `why_game_cvar_failed` (v2) said the command was "logged
  LogEngine: Warning (deferred/unprocessed) and never applied". Corrected: the
  command WAS dispatched and echoed (that is what `LogEngine: Warning:` is); the
  evidence it had no effect is the unchanged render-side counters, plus the
  timing/merged-mesh-blindness above — not a deferral.
