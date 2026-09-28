# The flatten path cannot shrink a texture — and the 32 never existed on disk

**⭐ VERDICT: the landscape HLOD bake is 1024×1024 on all 256 cells,
including the pilot cell, and it always was. `-BuildSingleHLOD` has never
produced 32×32. The "32" was an EDITOR READ-BACK ARTEFACT, not a build
output.**

**⛔ THREE DOCUMENTS ARE WRONG AND ARE CORRECTED BELOW**, including one
number — `MinVisibleDistance` — that every texture-size derivation of the
last two sessions was built on.

Measured 2026-09-14, this session. No layer change, no cap change, no full
build. One cell rebuilt; blast radius measured at exactly 1 package.

---

## 0. What decided it, in one line

The builder writes its own inputs into every package it produces, and
nobody had ever read them:

    ### HLOD_REPORT_BEGIN ###
      * MinVisibleDistance:        25600
      * HLODTextureSizePolicy:     SpecificSize(1)
      * HLODTextureSize:           4096
      * ProjectHLODMaxTextureSize: 1024

`Min(Max(4096, 16), 1024)` = **1024** — `LandscapeHLODBuilder.cpp:224`,
`:230`, `:234`. That is what the builder computed, recorded by the builder,
in the package written by the very run whose output was read as 32.

---

## 1. Source answers (a)–(d)

### (a) What `ExportLandscapeMaterial` renders, and from what camera

`MaterialUtilities.cpp:1002-1032` (the file-static worker). It renders the
**live scene**, not the material graph:

    :1026   FSceneInterface* Scene = InLandscape->GetWorld()->Scene;
    :1028   RenderSceneToTextures(Scene, ViewOrigin, ViewRotationMatrix,
                                  ProjectionMatrix, ShowOnlyPrimitives,
                                  HiddenPrimitives, OutFlattenMaterial);

* **Camera origin** — `:1006-1012`. `GetBoundingRect()` midpoint,
  transformed by the actor transform: a point over the centre of the proxy.
* **Orientation** — `:1013-1017`. `FInverseRotationMatrix(actor rotation)`
  composed with `diag(1, -1, -1)`: straight down.
* **Extent** — `:1019-1024`. `FReversedZOrthoMatrix(LandscapeExtent.X,
  LandscapeExtent.Y, 0.5/ZOffset, ZOffset)` with `LandscapeExtent =
  Rect.Size() * ActorScale * 0.5` (`:1010`) and `ZOffset =
  UE_OLD_WORLD_MAX` (`:1019`). **Orthographic, top-down, covering exactly
  the proxy's bounding rect.** There is no perspective and no draw
  distance anywhere in this function.
* **Five passes, not one** — `RenderSceneToTextures:914-943`: BaseColor
  (gamma 2.2), WorldNormal (1.0), Metallic (1.0), Roughness (2.2),
  Specular (1.0), each a separate full scene render through the buffer
  visualization path.

**Which overload the HLOD builder uses matters.** `LandscapeHLODBuilder.cpp:252`
calls the `ShowOnly` overload (`:1034-1066`), which builds an allow-list
from the landscape's own scene proxies. The **`HiddenPrimitives` overload**
(`:1068-1071`) passes an *empty* ShowOnly set and is called from exactly one
place — `WorldTileCollectionModel.cpp:2136`, the legacy World Composition
tile path. **It is not on the HLOD path at all**, so "hide while rendering
scene to texture" is not a lever here.

### (b) Where the render target size comes from

`RenderSceneToTexture:827-902`. `TargetSize` is a parameter, and
`RenderSceneToTextures:931` takes it from
`OutFlattenMaterial.GetPropertySize(Property)` — which is exactly what
`LandscapeHLODBuilder.cpp:247-251` set to `InTextureSize`:

    :845   RenderTargetTexture->InitCustomFormat(TargetSize.X, TargetSize.Y,
                                                 PF_FloatRGBA, false);
    :864   ViewInitOptions.SetViewRectangle(FIntRect(0,0,TargetSize.X,TargetSize.Y));
    :895   OutSamples.SetNumUninitialized(TargetSize.X*TargetSize.Y);
    :898   RenderTargetResource->ReadPixelsPtr(..., FIntRect(0,0,TargetSize.X,TargetSize.Y));

**The computed `RequiredTextureSize`, and nothing else.** No device caps,
no scalability, no screen-percentage — `:857` explicitly disables screen
percentage and `:879-880` pins the resolution fraction to 1.0.

### (c) Every path that can shrink the output after the render

There is exactly one, and it cannot produce 32:

| candidate | line | can it produce 32? |
|---|---|---|
| `OptimizeSampleArray` uniform-collapse | `:2428-2449` | **NO** — fires only when `Colors.Num()==1`, and sets `FIntPoint(1,1)` |
| `SetPropertySize` | `MaterialUtilities.h:137` | **NO** — bare assignment, no clamp or floor |
| texture creation | `ProxyMaterialUtilities.cpp:348` | **NO** — reads `GetPropertySize` directly |
| packed MRS size | `ProxyMaterialUtilities.cpp:233-251, :472` | **NO** — `PackedSize` = the Metallic property size |
| render-target pool reuse | `:840-842, :900-901` | **NO POOL** — a fresh `UTextureRenderTarget2D` per property, rooted then released |
| `Min(_, GetMax2DTextureDimension())` | `LandscapeHLODBuilder.cpp:237` | **NO** — `GRHIGlobals.MaxTextureDimensions`, default 2048 (`RHIGlobals.h:318`), set to 16384 by D3D12 (`D3D12RHI.cpp:217`); the log records `GraphicsRHI: D3D12 (SM6)` |

⭐ **The only post-render size change in the entire flatten path is
N×N → 1×1.** So a shrink to 32 is not reachable, and — decisively — **an
empty capture would have produced a 1×1 texture, not a 32×32 one.** The
pixel test the brief specified was therefore already decided by source
before it was run: 32×32 on disk would have *proved* a non-uniform capture.

### (d) What the landscape must be for the render to contain it

`:1043-1055`: every `ULandscapeComponent` with a live `SceneProxy`
contributes its `FPrimitiveComponentId`, plus `GetNanitePrimitiveComponentIds()`
when `HasNaniteComponents()`. So the components must be **registered with
the scene** — loaded and not merely resident as actor descriptors.

⛔ **But an unregistered landscape does NOT yield a black frame**, and this
is the trap that made the "unrendered landscape" candidate plausible:

    :871  // If no "show only" primitives are provided, we must pass an unset
          // TOptional - otherwise an empty set will mean no primitive should be visible.
    :872  ViewInitOptions.ShowOnlyPrimitives = !ShowOnlyPrimitives.IsEmpty()
              ? TOptional<TSet<FPrimitiveComponentId>>(ShowOnlyPrimitives)
              : TOptional<TSet<FPrimitiveComponentId>>();

An empty allow-list means **show everything**, not show nothing. Either
way the size is unaffected, and a uniform result collapses to 1×1 by (c).

---

## 2. What is actually on disk — measured, no editor

`-BuildSingleHLOD` re-run on the same cell, same command, then read
**before any editor was launched**. Two new read-only instruments,
`scripts/hlod_report_offdisk.py` and `scripts/uasset_lite.py`.

### The whole population, not a sample

    packages considered 2,267   missing 0   without a report block 0
    L2 landscape cells PARSED   256

| field | value | count |
|---|---|---|
| `MinVisibleDistance` | **25600** | 256 |
| `HLODTextureSizePolicy` | **SpecificSize(1)** | 256 |
| `HLODTextureSize` | **4096** | 256 |
| `ProjectHLODMaxTextureSize` | **1024** | 256 |
| `HLODMeshSourceLODPolicy` | `LowestDetailLOD(2)` | 256 |
| **baked texture dimensions** | **1024 × 1024, 3 per cell** | **256** |

Texture dimensions are read from the package's own `FTextureSource.SizeX`
/ `SizeY` tagged properties. The tag layout is taken from
`PropertyTag.cpp:411-500` and `PropertyTypeName.cpp:41-43` and confirmed
by the observed 29-byte stride (8 Name + 12 TypeName + 4 Size + 1 Flags +
4 value); the reader verifies the whole 25-byte prefix before accepting a
value, so a coincidental byte match is rejected rather than reported.

**Instrument check:** the reader was validated against the 255 untouched
siblings, six of which the editor independently read as 1024 on 2026-09-14.
It agrees with the editor everywhere the editor is not in dispute, and it
parsed 256 of 256 with 0 failures.

### The pilot cell, before and after this session's rebuild

| | bytes | texture dims |
|---|---|---|
| before (the editor's 16:09 save) | 4,198,857 | 1024×1024 ×3 |
| **after `-BuildSingleHLOD` (23:31, commandlet)** | **4,198,308** | **1024×1024 ×3** |
| prior session's "32" build, as recorded | 4,198,311 | *read as 32 in the editor* |

⭐ **The prior session's own package size proves it.** A 1024→32 shrink of
three textures removes megabytes; the recorded change was **−49 bytes**.
This session's rebuild lands within **3 bytes** of that "32" build, and is
1024. The two builds produced the same thing.

⭐ **And the pilot cell is the LARGEST of all 256** (population: min
2,722,732 / median 3,777,212 / max 4,198,308 — the max is the pilot). A
32×32 bake would have made it the smallest by an order of magnitude.

### Pixel statistics — PARTIALLY BLOCKED, stated plainly

**The per-texel stats the brief asked for could NOT be produced off disk.**
The texture source payloads are stored compressed: the package's payload
region is 4,182,251 bytes at **7.9806 bits/byte** entropy and
**re-compresses to 0.990** of its size. Decoding requires Oodle, which the
project's Python environment does not have. I did not open an editor to get
them, because the editor is the instrument under dispute.

What the payload does establish, as a content measure:

| measure | value |
|---|---|
| payload region | 4,182,251 bytes |
| raw source for 3 × 1024² BGRA8 | 12,582,912 bytes |
| payload / raw | 0.332 |
| payload entropy | 7.9806 bits/byte |
| **control: a flat 64×64 BGRA8 image (16,384 B)** | **compresses to 39 bytes** |

A uniform or near-uniform capture cannot produce 4.18 MB of
near-incompressible data. Combined with (c) — a uniform capture collapses
to 1×1 — **the "empty capture" hypothesis is refuted twice over without
needing the per-texel numbers.**

---

## 3. Log diff — single-cell vs the same cell in the full build

Full build: `_verify/hlod/build_20260914b/batch_17.log:3169-3226`
(**not** `run_console.log`, which contains **0** lines for this cell — it
is the orchestrator's console, not the commandlet's log).
Single cell: `_verify/hlod/pilot_landscape_2026-09-14/offdisk.log:2131-2172`.

**Identical in both:**

    [N / M] Building HLOD actor Alpine8K_HLODLayer_Instanced/Alpine8K_MainPartition_L2_X-2_Y0...
    LogHLODBuilder:  * HLODRebuildPolicyHashCompare -> ApproveRebuild
    LogHLODBuilder: Evaluated HLOD rebuild policies, final decision: ApproveRebuild
    LogRenderer: Recreating Persistent SBTs due to initializer changes
    LogStaticMesh: Building static mesh StaticMesh_0   -> tris: 72
    LogWorldPartitionHLODsBuilder: HLOD Actor ... was modified, saving...

**Present ONLY in the full build:**

    LogStaticMesh: Building static mesh LandscapeNaniteMesh_0   -> tris: 520200
    LogStaticMesh: Waiting for static meshes to be ready 0/1 (/Temp/BuildHLODPackage_112_InstanceOf_...)
    LogTexture: Building texture TwoD: ..._BaseColor (TFO_DXT1 VT, 1024x1024 x1x1x1)   x2
    LogTexture: Building texture TwoD: ..._Normal    (TFO_BC5  VT, 1024x1024 x1x1x1)   x2
    LogTexture: Building texture TwoD: ..._MRS       (TFO_DXT1 VT, 1024x1024 x1x1x1)   x2
    LogTexture: Waiting for textures to be ready 0/3

⭐ **The full build's own log states the size: `1024x1024` on all three
textures of this exact cell.** That is a third independent instrument, and
it was in the record the whole time.

⛔ **The single-cell run emits none of those lines, and that is a DDC hit,
not an absence of work.** Counts: `LandscapeStreamingProxy` 90 vs **0**,
`BuildHLODPackage` 42 vs **0**, `LandscapeNaniteMesh` 26 vs **0**. Those
lines are emitted only when a derived asset is *built*; the single-cell run
found identical DDC keys and reused the results. **Same keys means same
inputs** — which is itself evidence the two paths computed the same size.

**Absence checks, reported as counts because a zero is not a verdict:**

| signature | single-cell | full build |
|---|---|---|
| `failed to export a mesh` (`LandscapeHLODBuilder.cpp:364`) | 0 | 0 |
| `ExportLandscapeMaterial: Failed` (`MaterialUtilities.cpp:1062`) | 0 | 0 |
| `should use world space normals` (`:262`) | 0 | 0 |

The only errors in the single-cell log are the known `HttpListener unable
to bind to 127.0.0.1:8000` pair — IncrediBuild holds 8000 on this machine
(`docs/environment.md`), benign and unrelated.

---

## 4. Verdict

### The candidate — "the single-cell path captures an unrendered landscape"

**REFUTED.** The deciding line is `MaterialUtilities.cpp:2442-2447`: an
unrendered landscape yields a uniform sample array, and a uniform sample
array becomes **1×1**, never 32×32. Three further refutations:

1. The rebuilt cell's textures are **1024×1024 on disk** (§2).
2. The builder's own record says it computed 1024 (`SpecificSize` / 4096 /
   cap 1024 — §0).
3. The full build's log prints `1024x1024` for this cell (§3), and no
   export-failure line appears in any run (§3).

### The premise itself is refuted

**There is no anomaly to attribute.** `-BuildSingleHLOD` produced 1024 on
2026-09-14 and produced 1024 again today. The **32 was never on disk** —
it was an editor read-back taken shortly after the package was loaded.

⚠ **The mechanism of the bad read-back is NOT established, and I am not
going to guess it.** One fact is suggestive and unverified: 1024 → 32 is
exactly **five mip levels**, which is what a size query answered from
partially-resident or still-building platform data would return. The prior
session recorded the matching symptom — the same editor read 32, then 1024
for the same object minutes later. **The next step is one measurement, not
an experiment:** re-read that cell's textures in an editor with
`imported_size` (the source dimensions, which the DDC cannot change)
alongside `blueprint_get_size_x()` (platform data), in the same payload.
If they disagree, the accessor is the defect and every texture-size
read-back in the record needs re-checking.

### Three documents are corrected

| document | claim | status |
|---|---|---|
| `FINDINGS.md` | "the pilot build changed the cell from 1024 to 32"; "one cell of 2,267 now differs from its 255 siblings" | **WRONG.** 256/256 are 1024. There was never a deviation, so there was nothing to repair. |
| `REPRO_AND_DISCRIMINATE.md` | "32 reproduced exactly"; "neither policy branch predicts 32" | The second half is right and is now *explained*: no branch predicts 32 because **32 was never produced**. |
| `HLOD_TEXTURE_SIZE_SOURCE_2026-09-14.md` | "the pilot's 32 proves AutomaticSize ran"; "raising the cap may be a no-op" | **BOTH REFUTED.** `SpecificSize` is in force on 256/256 by the builder's own hash record, so the cap **binds**. |

⛔ **And one number underneath all three: `MinVisibleDistance` is 25,600 cm,
not 76,800.** All three documents derived texture sizes from the Instanced
layer's `loading_range` of 76,800. The builder persists its own value on
the HLOD actor (`WorldPartitionHLODUtilities.cpp:1044`) and it reads
**25600 on all 256 cells**. Every arithmetic table in those documents used
the wrong D. It changes none of today's conclusions — `SpecificSize`
ignores the draw distance entirely (`:222-225`) — but it would have changed
theirs.

---

## 5. Recommendation on the cap: **HOLD**, and the reason is budget, not doubt

**The mechanism question is settled, and it settles in favour of "the cap
binds".** `HLODTextureSizePolicy` is `SpecificSize` on 256/256 and
`HLODTextureSize` is 4096, so `:224` yields 4096 and `:234` clamps it to
the project's 1024. Raising `HLODMaxTextureSize` to 4096 **would** lift
every landscape cell to 4096. It is **not** a no-op. R-HLODTEX's 4096 is
being clamped, exactly as reported — the world ships 1024 landscape HLOD
textures today.

**I still recommend holding, for two measured reasons that are about cost,
not correctness:**

1. **It forces a full rebuild of every landscape cell.**
   `LandscapeHLODBuilder.cpp:124` hashes `ProjectHLODMaxTextureSize` into
   the HLOD hash, so changing it invalidates all 256 L2 cells and their
   parents. That is the whole-world rebuild the project already treats as a
   scheduled operation.
2. **It is a 16× texel increase on 256 cells, and the build is already
   near a limit that has bitten once.** The full build peaked at
   **8,718 MiB** against a 15.2 GB budget whose breach caused DEVICE_HUNG
   on 2026-09-12, and the 24-way re-plan exists precisely to stay under it.
   The L2 cells currently total ~0.97 GB on disk (256 × ~3.8 MB); at 4096²
   that trends toward the 15–20 GB class that `hlod_gitignore.py` was
   written to keep out of a 41 GB repository.

**So the cap change is a budget decision that now has no unknowns in it,
and it should be taken deliberately with a VRAM and disk plan — not
folded into this pilot.** What this session removes is the reason to be
*afraid* of it: there is no build path producing 32×32, and nothing would
bake an anomaly into the cells it touches.

---

## 6. State left behind

* **One package written**, the pilot cell, verified by mtime sweep of
  `LandscapeLab/Content` (**1** file changed since the build started).
* **The world is uniform:** 256/256 L2 landscape cells at 1024×1024, three
  textures each. The pilot cell is no longer deviant — because it never was.
* No editor was launched this session. No layer, cap, or proxy property was
  written. The only writes are this report, the two new read-only scripts,
  the two census JSONs, and the rebuilt cell.
