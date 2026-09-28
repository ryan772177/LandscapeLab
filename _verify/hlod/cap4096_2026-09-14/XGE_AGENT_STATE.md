# The XGE / IncrediBuild state on this machine, and the wedge signature

**Read 2026-09-14 while a `-game` process was hung.** Read-only; nothing on
the machine was changed.

**⭐ THE ROOT-CAUSE LOCUS: the engine hands shader jobs to IncrediBuild via
the XGE controller, and IncrediBuild does not return them.** 4,238 job files
sit unconsumed in the XGE working directory from a single run.

---

## 1. The one-line recognition test

    ls "$TEMP/UnrealXGEWorkingDir" | wc -l        # thousands of stale .in = WEDGED

Measured during the hang: **4,238 files**, all shader job inputs, e.g.

    4238-xge.Global-FReflectionEnvironmentSkyLightingPS-1211.in   104,339 bytes
    4237-xge.Global-FReflectionEnvironmentSkyLightingPS-1213.in   104,527 bytes

all stamped **20:16:33**, the moment the run went silent. The engine wrote
them; nothing consumed them.

## 2. IncrediBuild state, as installed

    product        IncrediBuild 10.36.3 (build 18514)
    install        C:\Program Files (x86)\IncrediBuild
    coordinator    CoordinatorID 5328DFC4-B898-4A64-87AC-7BAED1CF43FC
                   CoordAPIPort 31100   LicenseServicePort 50052

    SERVICES                          STATUS    START
    Incredibuild_Agent                Running   Automatic
    Incredibuild CoordinatorService   Running   Automatic
    Incredibuild Endpoint Service     Running   Automatic
    Incredibuild LicenseService       Running   Automatic
    Incredibuild Manager              Running   Automatic
    Incredibuild BuildCache           Stopped   Manual

    Builder\MaxHelpers            0      <- NO helper agents. Single machine.
    BuildService\CoordHost        ""     <- no coordinator host configured
    BuildService\InitiatorLicense 2
    BuildService\MaxConcurrentBuilds 1

⭐ `MaxHelpers = 0` matters: there is no farm. Everything IncrediBuild is
asked to do must happen locally or not at all.

⚠ And the port-8000 collision `docs/environment.md` already records has a
name now:

    Coordinator\TelemetryIbManagerDataServerURL
        = https://laptop-bn8417p3:8000/data/upload

That is the IncrediBuild Manager holding 8000, which is why unreal-mcp
runs on 8001.

## 3. What the IncrediBuild logs show for our runs

`xgConsole.log` — one `Started` per perf launch, and **no matching
`Stopped`** for the run that hung:

    Started 14/09/2026 19:38:02   PID=15316
    Started 14/09/2026 19:49:11   PID=30240
    Started 14/09/2026 20:10:02   PID=27172
    Started 14/09/2026 20:16:23   PID=14796     <- the hung run; never stopped

`xgWait.log` by contrast shows tidy Started/Stopped pairs milliseconds
apart. `LicenseService.log` is alive and looping a `resetBuildCache`
repeated task every minute, reporting `State: none` — noted, not
interpreted; BuildCache is a Stopped service so a null state there may be
ordinary.

## 4. ⭐ THE COMPARISON THAT LOCATES IT — and it is not the flag

| | 09-11 WORKED | 09-14 HUNG |
|---|---|---|
| `-noxgecontroller` on the command line | **absent** | **absent** |
| `Initialized XGE controller. XGE tasks will not be spawned on this machine.` | present | present |
| `LogShaderCompilers: Using XGE Controller for shader compilation` | **present** | **present** |
| `ShaderCompileWorker` mentions in log | **0** | **0** |
| shaders actually compiled | **YES** | **NO** |
| `LoadMap` | at +2.5 s | never |

**Both runs routed shader compilation through XGE, and neither spawned a
local `ShaderCompileWorker`.** On 09-11 that was fine because XGE *returned*
the jobs. On 09-14 it does not.

⛔ **So the missing `-noxgecontroller` flag is NOT the change** — it was
missing on the day it worked. The flag is a *bypass* for a path that has
since broken, not a setting that was wrongly omitted. Saying "we forgot the
flag" would misdescribe the history and send the next reader looking for a
config regression that did not happen.

**What changed between 09-11 and 09-14 is not established.** IncrediBuild
did run a `CheckForUpdates` at 09-14 19:04 (`AvailableUpdates.dat`,
`CheckForUpdates.log`), but no install file carries a post-09-10 write date
that would evidence an applied update. That is a lead, not a cause.

## 5. Why this never hit the HLOD builds

`hlod_build_batched.base_args()` passes `-noxgecontroller` on every
commandlet, and has since R-HLOD 08d. **The commandlet path bypasses XGE
entirely, which is why 32 batches of HLOD work ran clean on the same machine
on the same night that six `-game` launches hung.** `perf_standalone.py` has
never passed the flag — it did not need to, until now.
