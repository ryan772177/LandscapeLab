# The standalone perf stall: the DDC backend is fine, and the divergence point is exact

**Question asked:** did `-game` reach a working local DDC backend, and is
`zenserver.exe` alive during the launch?

**Answer: YES to both, and they are byte-for-byte the same as the runs that
worked.** The DDC is not the stall. But the comparison does locate the stall
to a single point, and names one perfectly-correlated candidate there.

Compared: 4 broken logs (2026-09-14, 0 CSV) against 2 working logs
(2026-09-11 backups, 8.4 MB, real CSVs) and `batch_31.log` (the commandlet,
which worked).

---

## 1. `-game` reached a working local DDC backend — in BOTH

Identical in the broken and working runs, same lines, same order:

    LogZenServiceInstance: Launching executable '...Common/Zen/Install/zenserver.exe'
    LogZenServiceInstance: Local ZenServer AutoLaunch initialization completed in 2.1xx seconds
    LogDerivedDataCache: ZenLocal: Using ZenServer HTTP service at [::1]
                         with namespace ue.ddc. Status: OK!.
    LogDerivedDataCache: Local: Found registry key GlobalDataCachePath
                         UE-LocalDataCachePath=C:/UnrealDDC
    LogDerivedDataCache: ../../../Engine/DerivedDataCache/Compressed.ddp:
                         Opened pak cache for reading. (1670 MiB)

| | broken 09-14 | working 09-11 |
|---|---|---|
| `Zen` lines | 8 | 8 |
| `zenserver` lines | 6 | 6 |
| ZenLocal status | **OK!** | **OK!** |
| AutoLaunch time | 2.119–2.141 s | 2.135–2.141 s |
| `LocalDataCachePath` lines | 3 | 3 |
| `StorageServer` | 1 (module load only) | 1 (module load only) |
| HTTP connect/timeout errors | **0** | **0** |
| zen shutdown / exit / terminate | **0** | **0** |

**`zenserver.exe` IS launched**, by the `-game` process itself, every time.
It was "not running" when checked at idle because it is auto-launched
per-process; **it never logs an exit or a failure in any of the four broken
runs.** The single `HTTP` match in both is
`CVarHttpReuseConnectionEnabled = true`, a config echo, not an error.

⭐ **AND THIS CLOSES AN OPEN ITEM.** The config source for `C:\UnrealDDC`,
which I could not find in project inis, engine inis, or the env, is a
**REGISTRY KEY**:

    Found registry key GlobalDataCachePath UE-LocalDataCachePath=C:/UnrealDDC

logged by both `LogZenServiceInstance` and `LogDerivedDataCache`. My earlier
registry search looked under `HKCU:\Software\Epic Games\Unreal Engine` and a
guessed `GlobalDDCPath`; the actual key is named `GlobalDataCachePath` and
carries a value named `UE-LocalDataCachePath`. **It was in the logs the whole
time, and it is present in the 09-11 logs too — so this is long-standing
machine config, not something the clear introduced.**

## 2. The divergence point, to the millisecond

Both runs reach `LogTurnkeySupport: Completed device detection: Code = 0`.
What happens next is the entire difference:

**WORKING (09-11 treeline), log line 1187 onward:**

    06:14:16.964  LogTurnkeySupport: Completed device detection: Code = 0
    06:14:17.005  LogModuleManager: InternalLoadLibrary: 'HairStrandsSolver'   <- +41 ms
    06:14:17.007  ... LocationServicesBPLibrary, Metasound*, WaveTable ...
    06:14:17.038  LogMetaSound: MetaSound Engine Initialized
    06:14:19.444  LogLoad: LoadMap: /Game/Alpine8K?Name=Player
    06:14:23.662  LogLoad: Took 4.094440 seconds to LoadMap(/Game/Alpine8K)

**BROKEN (09-14 treeline), log line 1060 onward — the file ENDS here:**

    02:33:17.229  LogTurnkeySupport: Completed device detection: Code = 0
    02:35:49.242  LogDerivedDataCache: C:/UnrealDDC: Maintenance finished in
                  +00:00:35.059 ... Scanned 19074 files in 19491 folders
                  with total size 8930 MiB.
    <nothing — silence until the dwell kills it ~2 minutes later>

**The broken run never loads another plugin module and never reaches
`LoadMap`.** The working run was playing 7 seconds after process start.

## 3. The one line that differs, and it is perfectly correlated

    DDC Maintenance pass    broken: 1, 1, 1, 1   (4 of 4 runs)
                            working: 0, 0        (0 of 2 runs)

Every broken run logs exactly one, ~35 s, scanning ~19,000 files in ~19,400
folders of `C:\UnrealDDC` — and in every one it is **the last line the
process ever writes**. The file counts creep up run to run (18,989 → 19,027
→ 19,074), so the pass re-runs on every launch against a growing cache.

`C:\UnrealDDC` was emptied and repopulated on 2026-09-14. The working runs
predate that.

## 4. What this does and does not establish

**ESTABLISHED:** the DDC backend is healthy and identical; zenserver runs and
does not die; there are no HTTP/connection failures; the stall is at engine
init, after device detection and before plugin-module loading; and the only
log line distinguishing broken from working sits exactly there and is
perfectly correlated, 4/4 vs 0/2.

⛔ **NOT ESTABLISHED — AND THE ARITHMETIC DOES NOT CLOSE.** The maintenance
pass costs **35 s** inside a **285 s** dwell. Even paying it in full there
were ~250 s left, and `LoadMap` takes 4 s on this world. So "maintenance ate
the budget" is NOT sufficient: something keeps the process silent for ~2 more
minutes after maintenance reports finished. Correlation at the right place is
a strong lead, not a cause.

⚠ **Two candidates, neither tested.** The maintenance pass blocks module
loading and its "finished" line is logged late relative to the work; or the
maintenance is itself a symptom of a first-touch scan of the repopulated
cache that also slows everything after it.

**Next, and it is one measurement:** one zone at `--settle 900`. A CSV means
the path is merely slow and the dwell was short — the fix is dwell, and the
budget must account for a cache maintenance pass. No CSV at 900 s means the
process is genuinely stuck and the maintenance correlation is the place to
dig.

---

## 5. The one-zone dwell: the process is HUNG, not slow — settled early

vista at `--settle 900` (dwell 945 s). It reached the same point and stopped
in the same place:

    02:49:13.145  LogTurnkeySupport: Completed device detection: Code = 0
    02:51:45.726  LogDerivedDataCache: C:/UnrealDDC: Maintenance finished in
                  +00:00:36.047 ... Scanned 19138 files in 19578 folders
    <silence>

**Measured on the live process rather than inferred from the log:**

| | |
|---|---|
| CPU across 20 s | **58.7 s → 59.0 s = 0.3 s**, over 69 threads |
| working set | flat, 2,674 MB |
| `ShaderCompileWorker` processes | **0 running** |
| `LoadMap` | absent |
| CSV | none |

~1.5% of a single core. **The process is idle-waiting, not working.**

⭐ **THIS REFUTES THE DWELL HYPOTHESIS OUTRIGHT, AND IT DID SO WITHOUT
WAITING OUT THE 945 s.** A longer dwell cannot fix a process that is not
consuming CPU. It also retires my earlier "cold shader cache" story for
good: there are **zero** shader compile workers alive during the hang.

⛔ **AND IT RETIRES AN INFERENCE I DREW FROM LINE COUNTS.** I had read
"shader-compile progress lines fall across zones (29, 30, 15)" as evidence
the cache was warming. Those lines are periodic progress reports, not a
measure of work: this run logged `Current jobs: 225, Num Already
Dispatched: 1128` moments before the hang. **Counting log lines is not
measuring the thing the lines describe.**

## 6. zenserver during the hang: ALIVE, LISTENING, AND NOT THE VICTIM

Checked on the live system while the editor was hung:

    zenserver.exe   PID 20436   started 19:49:07 (with the editor)
                    CPU 1.5 s   WS 172 MB
    listening       :: port 8558        owning process 20436
    editor sockets  8 x loopback in state "Bound", RemotePort 0,
                    NO Established connection to 8558

So the "zenserver died and the engine blocked on a dead HTTP endpoint"
hypothesis is **refuted**: the service is up, listening, and the engine
reported `Status: OK!` against it at startup.

⚠ The Bound-but-not-Established socket pool is noted and NOT interpreted.
It may be an ordinary idle pool. Reading it as evidence of a lost
connection would be exactly the kind of inference this document has had to
withdraw twice already.

## 7. Where this leaves it

**ESTABLISHED, and none of it points at the 4096 rebuild:**
the DDC backend initialises correctly and identically to the runs that
worked; zenserver launches, listens and survives; there are no HTTP errors;
no shaders are compiling during the hang; the process consumes no CPU; and
the world is never loaded, so its contents cannot be implicated.

**NOT ESTABLISHED:** what the 69 threads are waiting on. The only
distinguishing log line remains the `C:/UnrealDDC` maintenance pass —
present 5 of 5 broken runs, absent 0 of 2 working runs, and the last line
written every time.

**The next step is a thread stack, not another run.** Nothing about
timing, dwell, or cache warmth can be learned by launching this again —
five launches have produced five identical hangs. A `procdump -ma` of the
hung process, or attaching a debugger, would name the wait directly. That
is a new tool on this machine and wants a ruling before it is installed.

**A cheaper intermediate, if a stack is unwelcome:** point the DDC
elsewhere for one launch (`-LocalDataCachePath=<fresh empty dir>`, the
documented command-line override at `BaseEngine.ini:2866`) and see whether
the hang follows the cache. If a fresh cache launches clean, the
maintenance correlation becomes causal; if it hangs anyway, the DDC is
exonerated entirely and the search moves elsewhere. **That is one run and
it discriminates**, where more dwell does not.

---

## 8. The fresh-DDC discriminator: NOT a hang, and the branch condition was not met

`--only vista --settle 60 --local-ddc-path C:/UnrealDDC_fresh`, against a
directory created empty.

**The override took effect** — both the Zen service and the DDC backend
logged it, and the registry value was correctly superseded:

    LogZenServiceInstance: Found registry key GlobalDataCachePath UE-LocalDataCachePath=C:/UnrealDDC
    LogZenServiceInstance: Found command line override LocalDataCachePath=C:/UnrealDDC_fresh
    LogDerivedDataCache:   Local: Found command line override LocalDataCachePath=C:/UnrealDDC_fresh

and `C:\UnrealDDC_fresh` finished the run holding **110 files / 0.26 GB**,
so it was genuinely written to. `C:\UnrealDDC` was left alone as instructed.

### The three answers

| | |
|---|---|
| `LoadMap` reached | **NO** |
| maintenance line present | **NO** |
| CSV produced | **NO** |

### ⛔ BUT THIS IS A DIFFERENT FAILURE, AND CALLING IT "THE HANG" WOULD BE WRONG

The run ended **mid shader compile, working hard**:

    03:10:09.479  LogShaderCompilers: Current jobs: 482,  Num Already Dispatched: 4573
    03:10:10.097  LogShaderCompilers: Current jobs: 2554, Num Already Dispatched: 5055
    03:10:11.485  LogShaderCompilers: Current jobs: 820,  Num Already Dispatched: 7609

versus the earlier hangs, which were **idle**: 0.3 s of CPU across 20 s,
**zero** `ShaderCompileWorker` processes, last line a maintenance pass.

**An empty DDC guarantees a full shader rebuild, and a 60 s settle cannot
survive one.** The dwell was 105 s total. This run was killed while doing
exactly the work an empty cache implies — which is expected, explainable,
and NOT the pathology under investigation.

So the experiment as run **does not discriminate**: its failure has an
ordinary cause that masks the question. The 60 s settle is calibrated for a
warm cache, and the whole point of the fresh directory was that it is cold.
That is my error in composing the test, not a property of the engine.

### ⭐ AND YET THERE IS A REAL SIGNAL IN IT, AS A COMPARISON

Shader jobs dispatched before the log went quiet:

    against C:\UnrealDDC      1,128 dispatched, then IDLE for the rest of 945 s
    against C:\UnrealDDC_fresh  7,609 dispatched in ~13 s, still climbing when killed

**Against the fresh cache the shader pipeline ran roughly 7x further, in a
fraction of the time, and was still accelerating.** Against the original
cache it stalled at 1,128 and then did nothing for fifteen minutes.

That is a comparison of two numbers from two runs, not a controlled
measurement — different dwells, different cache states. It is a LEAD, and
it points at `C:\UnrealDDC` rather than away from it. It is not a finding.

### The corrected experiment, and it is still one run

Give the fresh cache enough dwell to finish its shader compile, or launch
against it twice and measure the second (warm) launch:

    python scripts/perf_standalone.py --only vista --settle 900 \
        --local-ddc-path C:/UnrealDDC_fresh

* **Loads and produces a CSV** → the original `C:\UnrealDDC` is implicated,
  and the fix is a cache replacement rather than a debugger.
* **Goes idle at ~0 CPU with no shader workers, like the 945 s run** → the
  DDC is exonerated regardless of which directory it points at, and the
  procdump route is the one left.

Either outcome is decisive, and the CPU-delta check distinguishes them in
20 seconds without waiting out the dwell.

---

## 9. Fresh DDC + 900 s settle: HUNG. The DDC is exonerated, and procdump is the route.

`--only vista --settle 900 --local-ddc-path C:/UnrealDDC_fresh`.

### The CPU-delta probe, at the two agreed checkpoints

| | CHECK-1 | CHECK-2 |
|---|---|---|
| elapsed | 68 s | **309 s** |
| cumulative CPU | 205.0 s | 217.1 s |
| **dCPU over 20 s** | **0.84 s** | **0.70 s** |
| working set | 4,574 MB | 4,574 MB (flat) |
| `ShaderCompileWorker` | **0** | **0** |
| verdict | IDLE | **IDLE** |

**12.1 s of CPU across 241 s of wall clock — 5% of one core.** The process
is alive, holding 4.57 GB, and doing essentially nothing.

### ⭐⭐ THE CONTROL THAT KILLS THE MAINTENANCE HYPOTHESIS

The maintenance pass **did** run on the fresh cache, and it cost nothing:

    03:18:21.424  LogDerivedDataCache: C:/UnrealDDC_fresh: Maintenance
                  finished in +00:00:00.005 ... Scanned 110 files in 205
                  folders with total size 6 MiB.

**0.005 s against 35 s on `C:\UnrealDDC` — and the hang is identical.**

That is the discriminator working exactly as intended. The pass that was
"present in 5 of 5 broken runs and 0 of 2 working runs" is now present, ~7000x
cheaper, and the process still never reaches `LoadMap`. **The maintenance
pass is a passenger, not the driver.**

⛔ **AND IT CORRECTS THE PREVIOUS REPORT.** Section 8 recorded "maintenance
line present: NO" for the 60 s fresh run. That was wrong in substance — the
run was killed at 105 s, before the engine got that far. With 900 s it
emits it. The honest reading of section 8's three answers is that the
60 s run **could not answer the maintenance question at all**, and I
reported an absence that was really a truncation.

### The signature, now reproduced on a cache that cannot be blamed

    shader dispatch high-water   6,813    FROZEN
    jobs still outstanding       1,569
    ShaderCompileWorker procs        0
    LoadMap                     absent
    CPU                         ~5% of one core

**The engine queues 1,569 shader compile jobs and spawns zero worker
processes to run them.** It then waits forever. This is the same end state
as the `C:\UnrealDDC` runs, reached by a different route and with the cache
variable eliminated.

### What is now excluded

| hypothesis | status |
|---|---|
| dwell too short | **REFUTED** — 945 s, idle throughout |
| cold shader cache | **REFUTED** — 0 workers running; it is not compiling |
| DDC backend broken | **REFUTED** — ZenLocal `Status: OK!`, identical to working runs |
| zenserver dead/missing | **REFUTED** — launched, listening on 8558, alive during the hang |
| DDC maintenance pass | **REFUTED** — 0.005 s on the fresh cache, hangs identically |
| cache *contents* | **REFUTED** — empty cache, same hang |
| cache *location* | **REFUTED** — `C:/UnrealDDC_fresh`, same hang |
| the 4096 rebuild | **EXCLUDED** — `LoadMap` never runs, so world content is never read |

**Six launches, six hangs, across two independent caches.** Nothing about
timing, cache warmth, cache location or cache contents changes the outcome.

### The one thing left, and it is not another run

The remaining question is what the process is blocked on, and no launch can
answer it — six have tried. **procdump is approved for the next session.**

    procdump -ma <pid of the hung UnrealEditor.exe>

and read the thread stacks. The first thing to look for, given the
signature: whoever owns shader-job dispatch is waiting, and no
`ShaderCompileWorker` was ever spawned. That points at the job dispatcher
or at whatever it waits on, not at the DDC.

⚠ **One control worth running first, and it costs one minute:** launch the
EDITOR (not `-game`) on the same project. The commandlet path works —
`batch_31.log` built 8 cells cleanly on 2026-09-14 — so the failure is
specific to some launch mode. Knowing whether the editor also hangs
narrows the stack hunt considerably before the dump is taken.
