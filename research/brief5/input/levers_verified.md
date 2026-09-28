# Brief 5 v3 — lever verifications (header:line filled in)

**2026-09-20. Engine source reads (standing rule 1 permits reading engine
source). UE 5.8 at `C:\Program Files\Epic Games\UE_5.8\Engine\Source`.**

| lever | desk had | verified at | finding |
|---|---|---|---|
| `wp.Runtime.HLOD` | doc, "Cmd not Var; VERIFY AT 5.8 HEADER" | `Runtime/Engine/Private/WorldPartition/HLOD/HLODRuntimeSubsystem.cpp:149-187` | **Confirmed a COMMAND** (`FAutoConsoleCommand EnableHLODCommand`, `FConsoleCommandWithArgsDelegate`). Sets static `WorldPartitionHLODEnabled` (`:147`, default true) and toggles `HLODObject->SetVisibility` only for `World->IsGameWorld()`. No value to echo. |
| `WorldPartitionHLODEnabled` read path | — | same file `:167,180,282,316,447,466,484` | The static is re-read on the HLOD register / cell-show path, so an early set *would* propagate to later-streamed cells — but see the `-game` timing finding (hlod_task2_gamepath.md). |
| `-ExecCmds` dispatch | "startup -ExecCmds too early" | `Runtime/Engine/Private/UnrealEngine.cpp:2552` (`ParseExecCommands::QueueDeferredCommands`) + `:2548` (`-EXEC=` file) | Both route to `GEngine->DeferredCommands`, run on the first post-init tick. They DO run after the PlayerController exists (BugItGo executed), echoed as `LogEngine: Warning: <cmd>`. Limit is timing (one-shot, pre-stream), not delivery. |
| LOD ScreenSize → distance | "NOT checked by desk; working form 1.78·R/D" | `Runtime/Engine/Private/SceneManagement.cpp:966-978` (`ComputeBoundsScreenSize`) + `:980-990` (`ComputeBoundsDrawDistance`) | **Confirmed.** `ScreenSize = 2·ScreenMultiple·R / max(1,Dist)`, `ScreenMultiple = max(0.5·P00, 0.5·P11)`. Inverse: `Dist = ScreenMultiple·R / (ScreenSize·0.5)`. For 4K 90° hFOV 16:9, `P11 = 1.778` dominates → **`D_switch = 1.778·R / ScreenSize`** (matches the desk's form). LOD selection scales ScreenSize by `FactorScale·LODDistanceFactor` at `:1002` (`ComputeTemporalStaticMeshLOD`). |
| `foliage.LODDistanceScale` | "NOT checked; scales every distance" | `Runtime/Engine/Private/HierarchicalInstancedStaticMesh.cpp:96` | **Default 1.0.** Scale on the distance used to compute foliage LOD. |
| `r.StaticMeshLODDistanceScale` | "NOT checked" | `Runtime/Renderer/Private/SceneVisibility.cpp:173` | **Default 1.0.** "higher values make LODs transition earlier, e.g. 2 is half the distance." |
| `r.ViewDistanceScale` | "NOT checked" | `Runtime/Core/Private/HAL/ConsoleManager.cpp:4435` (default 1.0) + **pinned `=1.0` in `LandscapeLab/Config/DefaultEngine.ini:207`** | **1.0** (compiled default AND explicitly pinned in project config, overriding ViewDistanceQuality@1's 0.6). |

**Consequence for Task 4a:** all three LOD/view distance scales are 1.0 in this
project (source defaults; ViewDistanceScale ini-pinned), so the switch distance
is `D = 1.778·R / ScreenSize` with no scaling correction. These cvars are not set
by the perf ExecCmds, so the `-game` process reads the same values; the editor
read-back (get_console_variable_float_value) is the recorded instrument and reads
the identical compiled-default+config value.
