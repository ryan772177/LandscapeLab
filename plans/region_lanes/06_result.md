## Guard diagnosis — third identical fire, so I am diagnosing rather than retrying

The guard matches a three-word substring anywhere in my output, including in text that is *about* that substring. My consolidated report does not contain it; my explanatory preamble did, because I quoted the phrase while explaining why I had removed it. Use and mention are indistinguishable to this check, so discussing the flag guarantees re-firing it.

**Precedent in this project, and this is the third instance of the class:** CLAUDE.md 2026-08-12 records the heredoc-escape guard firing on *the LESSONS entry being written about it*, and the commit-message guard firing on a heredoc containing the exact rule it enforces. Those fired once and work proceeded. This one loops. Per standing rule 6 I am stopping rather than varying, and per non-negotiable 4a a trap class reaching a third tool warrants a fix in shared infrastructure: **the output guard needs to exempt text where the phrase appears inside quotation marks or a fenced block, or it will fire on every future document that discusses it.** That is a hook defect, not a report defect.

**NN18 audit status: CLOSED.** Result was one field with no referent (declared null), three numbers withdrawn as underived, one figure corrected. No new defects exist; generating more to satisfy a re-fired check would be precisely the failure NN18 describes.

Deliverable follows, complete and unchanged in substance. It contains no vague non-verification language — every gap carries an explicit label.

---

# Streaming, memory and disk across N regions

## BOTTOM LINE

**Rule MULTI-REGION (WORLD_VISION Option A), plan N=8, disk-bounded near 20 before cooked output.** Contiguous is refused by mechanism, not preference: landscape Nanite build memory scales with proxies-per-*landscape*, the only cvar that looks like a concurrency bound is inert because its sole call site is commented out in engine source, and the cook path accepts no batch parameter — so a 2×2 contiguous world needs roughly 4× the measured 196.8 GB peak against a 223.4 GB limit that 437 GB of free disk cannot page-file past. Under multi-region that peak is paid once per region, serially, and runtime residency becomes N-independent by construction. **Largest risk: the ruling is entirely editor-side — nothing here has ever been cooked, and the cook re-runs the unbounded Nanite dispatch through a path with a 240 s per-proxy timeout whose failure mode is a silently Nanite-less proxy.**

## Evidence labels

**MEASURED** — read off this machine today · **VERIFIED ABSENT** — I looked at the artefact and it is not there · **NOT LOOKED** — no instrument has ever run · **NULL** — the field has no referent

## 1. Corrections to the brief — MEASURED

| Brief | Measured |
|---|---|
| `__ExternalActors__` ~7.2 GB **for ONE region** | 7.1 GB across **three worlds**: Alpine8K **3.7 GB**, GaeaLab/AlpineLab_8129 **3.1 GB**, Alpine **358 MB** |
| C: ~655 GB free | **437 GB free** of 952 |

Alpine8K precisely: **3,926,471,344 B (3.66 GiB), 1,357 `.uasset`**. Per-region content was ~2× overstated; headroom ~220 GB lower than recorded. Two independently built 8129²/256-proxy landscapes cost 3.58 and 3.1 GiB of proxies — the per-region cost reproduces across separate builds.

## 2. Per-region DISK — 98% is one thing

```
256 files > 10 MB      3.58 GiB    landscape Nanite proxies (~14 MB each)
1,101 files            0.08 GiB    foliage IFAs + misc (~78 KB each)
```

**All 219,659 tree instances, grass and understory together are 86 MB.** The Nanite landscape is the cost — fixed with area, independent of content placed on it.

| Item | Value |
|---|---|
| External actors | 3.66 GiB |
| Region textures `T_Alpine_8k_*` (weightmap 29.6 MB alone) | 38.1 MB |
| `.umap` + 2 HLOD layer assets | 12,995 B + 4,841 B |
| **HLOD output** | **0 — VERIFIED ABSENT** |
| DDC, Nanite share (`RECIPES.md:6370`) | ~10.7 GB, prunable |
| git/LFS permanent | ~4–6 GB, monotonic |
| **Content marginal / permanent marginal** | **~3.70 GiB / ~8–10 GB** |

**Shared, N-independent:** KiteDemo 6.4 + Megaplant 1.9 + Fab 1.8 + PN_spruce 1.5 + GV_Shrubs 1.4 + StampIt 0.92 + PN_WildBerries 0.635 + Surfaces 0.686 + Meshes 0.348 ≈ 15.7 GB, plus `Free/` 4.3 GB ≈ **20 GB one-time**.

**git/LFS, corrected.** `.git` 20 GB, `.git/lfs` 19 GB, 24,629 objects, against a 2026-08-10 baseline of 8.9 GB / 18,430. I first attributed the whole +10 GB to one region. Vendor packs are gitignored (`.gitignore:107,110,180,191`), so they are not in it — but `__ExternalActors__` is tracked (`git ls-files`: Alpine8K 1,357; GaeaLab 264), and current tracked content is **6.76 GiB across two worlds**, the remaining ~3.2 GB being superseded revisions. **Per-region permanent git is ~4–6 GB.** My first bound was conservative, not wrong in the dangerous direction.

*Decision this exposes, Ryan's:* pipeline rule 3 makes external actors derived, so not committing them takes per-region git to ~0 — against which the Nanite mesh is not cheaply reproducible (7 min, 196.8 GB peak) and the migration audit's headline was two missing Alpine packages only LFS could restore.

## 3. Per-region BUILD — memory is the story

| | Value | Source |
|---|---|---|
| Nanite build, 256 proxies | ~7 min, concurrent | `RECIPES.md:6367` |
| Save, 257 packages | 609 s | `RECIPES.md:6368` |
| Landscape create | ~9 min, 16.7 GB working set | CLAUDE.md |
| **Measured subtotal** | **~26 min** | |
| Peak commit, AlpineLab_8129 | **189 GB** / 223.4 GB | `RECIPES.md:6343` |
| Peak commit, Alpine8K | **196.8 GB** / 223.4 GB | `CLAUDE.md:1215` |
| **Headroom** | **26.6 GB — 88% utilisation** | |

Remaining per-region machine time (terrain compositing, mask bakes, material, placement, shader compile) is **NOT LOOKED**. The conclusion that build time does not bind holds at any plausible value.

### Mechanism — the finding

`BuildNanite` (`LandscapeSubsystem.cpp:1158-1176`) fires `UpdateNaniteRepresentationAsync` per proxy with no throttle, then blocks on `FinishAllNaniteBuildsInFlightNow` (`:1178-1183`). Concurrency equals proxy count.

`landscape.Nanite.MaxSimultaneousMultithreadBuilds` (default **-1 = unlimited**, `:93-97`) is consumed only by `WaitLaunchNaniteBuild()` (`:1583-1607`), whose sole call site is commented out:

```cpp
// LandscapeNaniteComponent.cpp:273
// LandscapeSubSystem->WaitLaunchNaniteBuild();   // TODO [chris.tchou]: this can deadlock, any waits should be done outside of async tasks
```

Three hits total across `Runtime/Landscape`: declaration, definition, that comment. **The cvar registers, reads back when set, and does nothing** — non-negotiable 17's shape. `landscape.Nanite.MaxAsyncProxyBuildsPerSecond` (6.0, `:76-79`) is consumed only at `:858` inside `Tick` (`:686`) — the live/incremental path, never the explicit build.

**This supersedes `RECIPES.md` R-NANITE8129:6385-6387**, which implies an engine-level bound existed and was merely unneeded.

## 4. Runtime — N-independent by construction

WP has never been tuned — **VERIFIED ABSENT** across all six `Config/*.ini`; WORLD_VISION build-order row 5 agrees. Defaults: `CellSize(12800)` = 128 m, `LoadingRange(25600)` = 256 m (`WorldPartitionRuntimeSpatialHash.h:231-232`). An 8128 m region → ~64×64 ≈ 4,096 base cells; proxies are 508 m and promote to a coarser level (`:185`).

Ruling 2b requires budgets sized against mounted speed. **Converting 256 m into seconds is not possible from this repo — no on-foot speed is defined anywhere.** (I supplied one in a first pass and reported a derived figure; withdrawn.)

Runtime RAM: **NOT LOOKED** — every frame-cost number here is editor-viewport, per CLAUDE.md's own CALIBRATION CLASS. VRAM: **VERIFIED ABSENT for this machine** — the only figure in the repo, `RECIPES.md:5856` (3.8/8 GB), belongs to the retired iGPU, not the 16303 MiB 5080.

**Decisive:** under multi-region exactly one region is resident, so both quantities are N-independent and stay bounded at N=1 however many regions ship.

## 5. HLOD — VERIFIED ABSENT, load-bearing

No HLOD directory exists anywhere under `Content`. Only settings assets: `Alpine8K_HLODLayer_Instanced.uasset` (1,755 B), `..._Merged.uasset` (3,086 B). WORLD_VISION ruling 2a makes aerial readability first-class and HLOD is its mechanism (`BACKLOG.md:142`). Cost is **NOT LOOKED**, and it must fit in the same 26.6 GB the Nanite build nearly exhausts. Per-region and serial under multi-region; a second unbounded whole-world build under contiguous.

## 6. NULL field

> brief: "runtime RAM and VRAM for one resident region **plus whatever a transition requires**"

`transition_cost: **null**` — no second region, no airship, no transition code; ruling 2c (`WORLD_VISION.md:169-170`) defers traversal entirely. **Null means: unmeasurable until a second region and a transition path both exist.** It does not block the N decision, because multi-region bounds it structurally. In my first pass I skipped this silently and filled the section with WP defaults, which read as though it had been answered.

## 7. The COOKED build

**VERIFIED ABSENT:** no `[/Script/UnrealEd.ProjectPackagingSettings]` in any config — no `MapsToCook`, no `DirectoriesToAlwaysCook`. `GameDefaultMap=/Engine/Maps/Templates/OpenWorld` (`DefaultEngine.ini:4`) is an engine template, so a cook today cooks the wrong map and reports success. No `Saved/Cooked`.

**Mechanism.** `ALandscapeProxy::PreSave` → `LandscapeInfo->UpdateNanite(ObjectSaveContext.GetTargetPlatform())` (`Landscape.cpp:4301-4307`), skipped only on autosave. `UpdateNanite` (`:6366-6372`) iterates `ForEachLandscapeProxy` over every proxy — **no batch parameter and no `IsNaniteMeshUpToDate` filter**, unlike `BuildNanite` (`LandscapeSubsystem.cpp:1157`) — then blocks on all. **The cook cannot be batched; this is what makes contiguous unbuildable rather than merely expensive.**

**240 s per-proxy timeout** (`LandscapeNaniteComponent.cpp:697-711`): `MaxWaitSeconds = 240.0`, on expiry logs an **Error and returns false** — a proxy cooked without Nanite, not a cook abort. **Grep any cook log for `waited more than`; a clean exit code is not evidence.**

**Verified good news:** the export DDC key (`:290-306`) hashes `ProxyContentId`, `MeshExportVersion`, `MeshSerializationVersionId`, `ComponentBase` — **no target platform** — so the expensive raw export is reused by the cook.

**A live cook memory lever:** `CookSettings.MemoryMinFreeVirtual` / `MemoryMinFreePhysical` trigger cooker GC (`CookGarbageCollect.cpp:427-439`). `MemoryMaxUsed*` are **deprecated in 5.6** (`CookOnTheFlyServer.h:368-372`). These bound package-level memory only — not the Nanite spike, which occurs inside a blocking `PreSave` where GC cannot run.

**NOT LOOKED:** cooked size per region (14 MB/proxy is an *editor* package; cooked streaming pages are a different representation — **this is the number that decides shipping disk for N**); peak cook commit; whether the 240 s timeout fires at 256-way concurrency; whether this project cooks at all as a C++ project with two `Target.cs` carrying empty `ExtraModuleNames`.

### Cheapest experiment

Switches verified here: `-MAP=` (`CookCommandlet.cpp:365-366`), `-ITERATE` (`:195`), `-PARTIALGC` (`:202`), `-UNVERSIONED` (`:192`). **The invocations are assembled from cited parts and are themselves unexecuted — which is why run 1 exists.**

```
Run 1 (~30 min, near-zero risk) — removes "does this project cook at all"
  UnrealEditor-Cmd.exe <uproject> -run=Cook -TargetPlatform=Windows -MAP=/Game/Alpine -unversioned

Run 2 (one night, ~20 GB) — set CookSettings.MemoryMinFreePhysical first
  UnrealEditor-Cmd.exe <uproject> -run=Cook -TargetPlatform=Windows -MAP=/Game/Alpine8K -unversioned -PartialGC
```

Measure wall clock; peak commit against `Win32_OperatingSystem.TotalVirtualMemorySize` (`RECIPES.md:6347-6350` — the limit in effect, not the page-file setting); `du -sh Saved/Cooked/Windows`; log grep for `waited more than` and `BuildNaniteFinalLog`. Editor closed — 26.6 GB does not fit two heavy processes (pipeline rule 5).

## 8. What bounds N

| Constraint | Binds at | Why |
|---|---|---|
| **Build peak memory** | **N=1 per landscape** | 196.8 GB of 223.4 GB, unbounded concurrency, no working throttle, unbatchable cook. **Does not accumulate across separate levels.** |
| **Disk** | **N ≈ 20** pre-cook | 437 GB free, ~8–10 GB permanent per region. **The binding constraint.** |
| **Build time** | not binding | ~26 min measured for the heavy half |
| **Runtime RAM / VRAM** | **N-independent** | one region resident |

**Not 4, not 40. Plan 8; ~20 affordable; 40 is out** — 40 × ~8 GB = 320 GB + 20 GB shared vendor + cooked output (≥148 GB if cooked ≈ editor size) exceeds 437 GB, and cooked size is exactly the unmeasured quantity.

**Contiguous, arithmetically:** a 2×2 world is one 16258² landscape ≈ **1,024 proxies** in a single `ULandscapeInfo`, ~4× concurrent work ≈ **790 GB commit**, needing ~760 GB of page file on 437 GB of free disk. Batching the editor build is conceivable (`LandscapeEdit.cpp:6131-6141`); **the cook has no batch parameter, so there is no escape hatch.**

WORLD_VISION Option A's own argument — *"One 8064 m region already defines this hardware's ceiling"* (`:222-224`) — was judgement. **It is now a measurement, and the ceiling is 88% consumed at N=1.**

## 9. Recommendation

1. **Rule Option A, MULTI-REGION.** Closes `WORLD_VISION.md:171-177` / `:190-196`, which `BACKLOG.md:179-187` records as blocking all placement work.
2. **Plan N=8, bound ~20 on disk.** Publish the marginal so it stays checkable.
3. **Cook `/Game/Alpine` this week**, then `/Game/Alpine8K` overnight.
4. **Two records need additive correction** (Ryan's files): R-NANITE8129 (~:6385-6387) implies an engine-level bound that does not exist; CLAUDE.md CURRENT STATE should carry 3.7 GB (not 7.2) and 437 GB free.
5. **Tune WP once, not per region**, and define a movement speed before ruling 2b can be evaluated.

**Standing rule 10:** §1–§3 and §8's disk arithmetic are measured on this machine today. §4's runtime and §7's cook behaviour are read from 5.8 engine source and **have never been executed here**. The recommendation is safe against that gap in exactly one way — multi-region holds every unmeasured runtime quantity at N=1 — and in no other.