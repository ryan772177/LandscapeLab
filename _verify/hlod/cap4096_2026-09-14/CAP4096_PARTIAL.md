# HLODMaxTextureSize 4096 — the mechanism works, and the build is DISK-BLOCKED at 33 of 256

**⭐ THE CAP CHANGE DOES EXACTLY WHAT WAS PREDICTED.** Every cell rebuilt
under it records `ProjectHLODMaxTextureSize: 4096` and bakes **4096×4096**
BaseColor / Normal / MRS. 33 of 256 are converted, measured off disk.

**⛔ AND THE RUN IS STOPPED AT A CLEAN BATCH BOUNDARY, NOT FINISHED.**
The remaining 223 cells need **~41.5 GB** by the measured slope and there
are **22.91 GB** free. Continuing would abort mid-run at the 6 GB floor
around batch 15, leaving the world more mixed than it is now.

Stopped after batch 3. Every batch is committed and the run resumes with
`run --start 4`.

---

## 1. The ini, and its read-back

`LandscapeLab/Config/DefaultEngine.ini`:

    [/Script/Landscape.LandscapeSettings]
    HLODMaxTextureSize=4096

`ULandscapeSettings` is `UCLASS(config = Engine, defaultconfig)`
(`LandscapeSettings.h:45`), so that file and section are correct; `ClampMax`
is 8192 (`:136`).

**Read back from the engine, in a commandlet log** (`ini_readback.log`):

    __LANDSCAPELAB_LSSETTINGS__ HLODMaxTextureSize = 4096

⛔ **The obvious Python route is a trap, and the trap is silent.**
`unreal.LandscapeSettings` **does not exist** — the class is
`UCLASS(..., MinimalAPI)`. The CDO is still reachable at
`/Script/Landscape.Default__LandscapeSettings`, and on it:

| spelling | result |
|---|---|
| `hlod_max_texture_size` | RAISES *"Failed to find property"* |
| **`HLODMaxTextureSize`** | **4096** ✅ |
| `SideResolutionLimit` | RAISES *"is protected and cannot be read"* |
| `dir(cdo)` | 23 names, **0** containing "hlod" or "texture" |

The protected property raising a **different** message is the control that
matters: it proves the lookup machinery worked, so `HLODMaxTextureSize`
genuinely resolved rather than accidentally matching. Without that control,
"4096" and "not found" would be one instrument reporting on itself.

## 2. Flagged set — 256 L2 cells, 0 others ✅

`-SetupHLODs` **cannot** answer this: `-ReportOnly` skips
`BuildHLODActors()` entirely (`WorldPartitionHLODsBuilder.cpp:432-438`) and
the rebuild policy lives inside the skipped step — R-HLOD-SETUP, already
locked. The count comes from each package's own HLOD_REPORT instead.

**2,267 packages, 0 missing, 0 unparsed:**

| | n |
|---|---|
| carry landscape hash fields (all `_L2_`, all `Instancing(0)`) | **256** |
| of those, `ProjectHLODMaxTextureSize == 1024` → **stale** | **256** |
| carry no landscape hash fields → cap not in their hash | 2,011 |
| non-landscape packages carrying the field | **0** |

**ACCEPTANCE MET.** The cap reaches exactly one builder:
`LandscapeHLODBuilder.cpp:124` sits inside
`ULandscapeHLODBuilder::ComputeHLODHash` and nowhere else.

## 3. Batch table — 4 of 32 run

Batches of **8** (ruled, on the 4.7 GB/cell probe peak), 13 GB VRAM abort,
6 GB free-disk abort.

| batch | cells | approve | reject | min | VRAM MiB | torn | +cap | free GB | true exit |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 8 | 8 | 0 | 0.67 | 11,671 | 0 | +8 | 27.43 | True |
| 1 | 8 | 8 | 0 | 0.67 | 11,641 | 0 | +8 | 26.01 | True |
| 2 | 8 | 8 | 0 | 0.67 | 11,931 | 0 | +8 | 24.56 | True |
| 3 | 8 | 8 | 0 | 0.67 | 11,636 | 0 | +8 | 22.91 | True |

32/32 cells approved, 0 rejected, 0 torn, true exit every time, ~0.67 min
per batch. **Plus the 1-cell probe = 33 of 256 at 4096.**

⚠ **VRAM peaks at 11.6–11.9 GB against the 13 GB abort** — 1.4 GB of
headroom on a gate that exists because a breach caused DEVICE_HUNG on
2026-09-12. Batches of 8 are at the ceiling; 9 would very likely trip it.
Within-batch VRAM climbs ~1.4 GB per cell and resets only at the boundary.

## 4. Off-disk acceptance on what is built ✅

256/256 packages parsed, 0 failures:

| | cap recorded | baked dimensions | n |
|---|---|---|---|
| rebuilt | **4096** | **4096×4096 ×3** | **33** |
| not yet | 1024 | 1024×1024 ×3 | 223 |

**Exact 1:1 correspondence between the recorded cap and the baked
dimension.** No cell records 4096 and bakes 1024, or the reverse.

### The getter check — six cells, 18 textures

| cell | cap | off-disk source | `imported_size` | `blueprint_get_built_texture_size` | `blueprint_get_size_x/y` |
|---|---|---|---|---|---|
| L2_X-2_Y-1 | 4096 | 4096×4096 | RAISED | 4096×4096 | 4096×4096 |
| L2_X-1_Y-6 | 4096 | 4096×4096 | RAISED | 4096×4096 | 4096×4096 |
| L2_X-2_Y1 | 4096 | 4096×4096 | RAISED | 4096×4096 | 4096×4096 |
| L2_X-3_Y3 | 1024 | 1024×1024 | RAISED | 1024×1024 | 1024×1024 |
| L2_X0_Y6 | 1024 | 1024×1024 | RAISED | 1024×1024 | 1024×1024 |
| L2_X-6_Y-6 | 1024 | 1024×1024 | RAISED | 1024×1024 | 1024×1024 |

⛔ **`imported_size` IS NOT REFLECTED ON `UTexture2D` IN 5.8**, under either
spelling (`imported_size` and `ImportedSize` both raise *"Failed to find
property"*). The brief named it as half of the dimension instrument; it is
not available. **The source-dimension instrument is the off-disk
`FTextureSource.SizeX`/`SizeY` read** (`scripts/uasset_lite.py`), which is
what the table's third column is.

**18 of 18 textures: off-disk source, built size, and `get_size_x/y` all
agree.** The probe's own summary still printed `REFUSING: 0 textures read
both getters` — correctly, because the pair it was asked to compare was
never both available. A refusal is the right output there; silence would
have read as agreement.

⚠ So last session's open item is **only half closed**: the three getters
agree *today*, on assets whose DDC is warm. That does **not** reproduce the
2026-09-14 condition (a read taken moments after a cold load), and it does
not explain the 32. It remains open.

## 5. Disk — the blocker, measured

Free-disk slope over four batches: **1.43, 1.42, 1.45, 1.65 GB** per 8-cell
batch → **~1.49 GB/batch ≈ 186 MB/cell**.

Where it goes — and only a third of it is the thing we wanted:

| consumer | growth | note |
|---|---|---|
| `LandscapeLab/Content` (the packages) | +0.41 GB/batch | **permanent, wanted** |
| `%LOCALAPPDATA%\UnrealEngine` (local **shared DDC**) | **+~1.0 GB/batch** | **a CACHE — reclaimable** |
| project `DerivedDataCache` | +0.013 GB/batch | negligible |
| `_verify`, `.git`, `Saved`, `Intermediate` | 0.00 GB | measured, not assumed |

The shared DDC went **3.01 → 8.75 GB** across 33 cells (~174 MB/cell). It
is **outside the repo**, so standing rule 1 forbids me touching it.

### The projection

    remaining cells                223
    at the measured 186 MB/cell    ~41.5 GB needed
    free now                       22.91 GB
    usable above the 6 GB floor    16.9 GB  ->  ~91 more cells
    SHORTFALL                      ~25 GB

**Permanent cost alone is affordable**: 223 × ~57 MB ≈ **12.7 GB** of
packages against 22.91 GB free. It is the ~28 GB of *cache* that does not
fit — and cache is exactly the thing that can be discarded.

## 6. Not run

**Task 5 (standalone 4K perf) was NOT run, deliberately.** With 33 of 256
cells at 4096 and 223 at 1024, a capture measures a world that will not
ship. Zone cost would depend on which cells happen to be in frame, and
against R-PERFBUDGET it would be a number with no defined meaning. It is
worth running once the set is uniform, not before.

Ruled for that run when it happens: **all four zones**, with treeline
reported as **"treeline (formerly mid_slope)"** — `mid_slope` is in no live
recipe; the archive records it at `-190000, 100000, yaw 105, pitch -2`,
which is the current `treeline` station exactly.

## 7. State left behind

* **33 of 256 landscape L2 cells at 4096; 223 at 1024.** A mixed world.
* The cap is **4096 in the ini**, so any future landscape HLOD build bakes
  at 4096 — including any incidental rebuild.
* Every batch committed; resume with
  `python scripts/hlod_build_landscape_cells.py run --run-dir <abs> --start 4`.
* **The Merged layer's parents are now hash-stale** for the 33 rebuilt
  children (`HLODSourceActorsFromCell.cpp:213-220` hashes the source actor
  set). No other layer was touched, by instruction. This is a scope
  boundary, not an oversight, and it applies to all 256 when the run
  completes.
* Restore point: tag `pre-hlod-cap-4096-20260914`.
