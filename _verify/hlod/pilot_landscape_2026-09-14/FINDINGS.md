> # ⛔ SUPERSEDED IN PART — 2026-09-14 by `FLATTEN_PATH_VERDICT.md`
>
> **THE 32 NEVER EXISTED ON DISK.** The section below titled "Task 3 — a
> bake appeared, and it is the WRONG SIZE", and the "⛔ State left behind"
> section, are **WRONG**. The cell was 1024×1024 then and is 1024×1024 now;
> so are all 255 siblings, measured off disk on 256/256 cells. There was no
> deviation and nothing to restore. The 32 was an editor read-back artefact.
>
> The rest of this file — the override census, and the sampling-error
> correction that found the landscape bake exists at 1024 — **STANDS**.
>
> ⚠ One number here is wrong wherever it appears: the builder's
> `MinVisibleDistance` is **25,600 cm**, not the 76,800 taken from the
> layer's `loading_range`.

# Landscape HLOD pilot — the zero is explained, and the rebuild made it worse

**⭐ THE LANDSCAPE BAKE EXISTS. My 2026-09-14 "no landscape bake" finding
was WRONG, and the reason is a sampling error I made, not an engine fact.**

**⛔ AND THE PILOT BUILD CHANGED THE CELL FROM 1024 TO 32.** One cell of
2,267 now differs from its 255 siblings. Not restored — see below.

---

## Task 1 — the override is not the zero

257 actors read, **0 raised, 0 outliers**:

| property | parent `Landscape_Alpine8K` | 256 proxies |
|---|---|---|
| `hlod_material_override` | **null** | **null ×256** |
| `hlod_texture_size_policy` | `SPECIFIC_SIZE` | `SPECIFIC_SIZE` ×256 |
| `hlod_texture_size` | 4096 | 4096 ×256 |
| `hlod_mesh_source_lod_policy` | `LOWEST_DETAIL_LOD` | `LOWEST_DETAIL_LOD` ×256 |

`HLODMaterialOverride` is null everywhere, so "override set → no texture
baked" is **not** the zero. Task 2 proceeded.

⚠ **Inherited vs local is NOT determinable from Python.**
`ALandscapeStreamingProxy::OverriddenSharedProperties`
(`LandscapeStreamingProxy.h:37-39`) is a private bare `UPROPERTY()` and
raises *"Failed to find property"*. The EFFECTIVE value is reported
instead — which is what the builder reads — and **a proxy's value
matching the parent is not evidence that it inherits.**

## The zero, explained: I sampled the wrong cells

Cell population by layer and level, all 2,267 parsed, 0 unparsed:

| | L0 | L1 | L2 |
|---|---|---|---|
| Instanced | 221 | 748 | **256** |
| Merged | 786 | 256 | — |

**Instanced L2 = 256 = the number of landscape streaming proxies.**
Large actors are assigned to coarser grid levels, so every landscape
proxy lands in its own L2 cell. The 09-14 census sampled Instanced cells
and got `T_Norway_Spruce_Bark_01_C` at 4096 — those were **L1 foliage
cells**. It never sampled an L2 cell, and concluded "no landscape bake"
from a population that contains none.

Six untouched L2 cells, sampled now: **3 textures each, all 1024×1024.**
That matches the earlier whole-world scan exactly — 768 landscape-named
textures = 256 cells × 3 — which was in the data all along and which I
read as "source textures" rather than as the bake.

**So the landscape HAS been baked all along, at 1024**, which is
`min(HLODTextureSize 4096, HLODMaxTextureSize 1024)` —
`LandscapeHLODBuilder.cpp:224` then `:234`. Exactly what the header
predicted. R-HLODTEX's 4096 is capped, as reported; it is not ignored.

## Task 2 — single-cell build works

    "…/UnrealEditor-Cmd.exe" …/LandscapeLab.uproject /Game/Alpine8K
      -run=WorldPartitionBuilderCommandlet
      -Builder=WorldPartitionHLODsBuilder
      -noxgecontroller -AllowCommandletRendering
      -unattended -nosplash -nopause
      -abslog=…/pilot_landscape_2026-09-14/pilot_1024.log
      -BuildHLODs
      -BuildSingleHLOD=Alpine8K_HLODLayer_Instanced/Alpine8K_MainPartition_L2_X-2_Y0

Cell chosen by grid arithmetic from the label, not by bounds:
`get_actor_bounds` returns degenerate extents for Instanced cells (their
ISM components are unregistered), so a bounds search finds only Merged
cells and would have picked the wrong population.

Builder output — 1 cell, 1 decision, 1 approval, **0.34 min**, VRAM peak
223 MiB:

    #### Building 1 HLOD actors ####
    [1 / 1] Building HLOD actor Alpine8K_HLODLayer_Instanced/Alpine8K_MainPartition_L2_X-2_Y0...
    * HLODRebuildPolicyHashCompare -> ApproveRebuild
    Evaluated HLOD rebuild policies, final decision: ApproveRebuild
    HLOD Actor … was modified, saving...
    #### Built 1 HLOD actors ####

**No `InputStats` lines are emitted at all** — not by this build, and the
property is not reflected to Python either, so the source-component
census remains unavailable by both routes.

## Task 3 — a bake appeared, and it is the WRONG SIZE

Read back from the rebuilt cell:

    mesh      StaticMesh_Alpine8K_HLODLayer_Instanced_0    72 triangles
    material  MI_…LandscapeStreamingProxy_79LP9WD7…_508_6_8_0
    textures  …_BaseColor   32 x 32
              …_Normal      32 x 32
              …_MRS         32 x 32

The material and texture names carry `LandscapeStreamingProxy`, and
BaseColor/Normal/MRS is the landscape HLOD texture set — **this is
unambiguously the landscape bake.**

| | rebuilt pilot cell | 6 untouched L2 siblings |
|---|---|---|
| textures per cell | 3 | 3 |
| dimensions | **32×32** | **1024×1024** |
| sample | 1 cell | 6 cells |

**The same settings that produced 1024 in the full build produced 32 in
this single-cell build.** `HLODTextureSizePolicy` is `SpecificSize` and
`HLODTextureSize` is 4096, which `LandscapeHLODBuilder.cpp:214-234`
should resolve to `min(4096, 1024) = 1024` with no dependence on view
distance. **Why it produced 32 is NOT established, and I am not going to
guess** — the brief's instruction for this case is to dump and stop for
the desk to read the builder source.

Two candidates worth testing, neither verified:

* `MinVisibleDistance` in `FHLODBuildContext` differs for a single-cell
  build (`ComputeRequiredTextureSize` takes it, and the mesh is only 72
  triangles). It should be inert under `SpecificSize`, but the AutomaticSize
  path is the only one in that function that can produce a small number.
* The on-disk proxy state at build time differs from what the editor
  reports. R-HLODTEX wrote `hlod_texture_size` only; it never wrote
  `hlod_texture_size_policy`, which was already `SpecificSize`.

### Disk / VRAM / time — the row, with the caveat that it is the 32 row

| | value |
|---|---|
| build time | **0.34 min** (20.4 s) |
| VRAM peak | **223 MiB** (from 11 MiB idle) |
| package before | 4,198,360 bytes |
| package after | **4,198,311 bytes** (−49) |

The package barely moved because the mesh is 72 triangles and the
textures shrank from 1024 to 32 — a smaller bake in a package dominated
by other content. **This is not the 1024 baseline row the pilot wanted**;
it is a 32 row, and it is not comparable to anything.

## ⛔ State left behind, stated plainly

**The pilot cell is now 32×32 where its 255 siblings are 1024×1024.**

It was **not restored**, and the reason is deliberate:

1. **There is no committed state to restore to.** HLOD packages are
   individually gitignored as derived content
   (`.gitignore:1066` for this package; see `scripts/hlod_gitignore.py`
   for why — ~15-20 GB of derived data in a 41 GB repo). `git checkout`
   has nothing to restore.
2. **Rebuilding is what caused the deviation.** Re-running the same
   command would most likely produce 32 again, and running the batched
   path would rebuild ~92 cells — risking converting 92 cells to 32
   instead of 1. Stopping at one deviant cell is strictly better than
   discovering the mechanism on 92.

Recovery, when the desk has read the builder source: a full
`-BuildHLODs` pass regenerates every cell from source, so the deviation
is repairable at the cost of one rebuild — the same cost the world
already pays for any layer or cap change.

## What this changes

* **AUDIT H-1 / S-8 and the 09-14 acceptance report need amending.** The
  landscape bake exists; "no landscape bake anywhere" was a sampling
  error on my part. The correct statement is: *the landscape is baked at
  1024, capped from 4096 by the project's `HLODMaxTextureSize`.*
* The pilot's original question — does 4096 change anything — is
  answerable only after the cap ruling, and now also after the 32
  discrepancy is understood.
