> # ⛔ CONCLUSIONS REFUTED — 2026-09-14 by `_verify/hlod/pilot_landscape_2026-09-14/FLATTEN_PATH_VERDICT.md`
>
> **BOTH HEADLINE CLAIMS ARE WRONG:**
>
> 1. *"The pilot executed the AutomaticSize branch."* **REFUTED.** Every
>    HLOD package records the fields the builder hashed. All 256 landscape
>    cells — the pilot included, in the very run this file analysed — say
>    `HLODTextureSizePolicy: SpecificSize(1)`, `HLODTextureSize: 4096`.
>    The elimination argument was sound; its premise, that the build output
>    32, was false. **32 was never on disk.**
>
> 2. *"Raising `HLODMaxTextureSize` may be a no-op."* **REFUTED.**
>    `SpecificSize` is in force on 256/256, so `:234` binds and raising the
>    cap **would** lift 1024 → 4096. It is not a coin-flip.
>
> ⛔ **AND THE ARITHMETIC USES THE WRONG DRAW DISTANCE.** `MinVisibleDistance`
> is **25,600 cm**, not the 76,800 read from the layer's `loading_range`.
> The builder persists its own value on the HLOD actor and records it;
> every D-indexed table below is off by 3×.
>
> **What STANDS, and it is the valuable half:** the verbatim source at
> `:210-240`, the term table, the `ComputeRequiredTexelDensityFromDrawDistance`
> derivation, the rejection of `TextureSizingType_*` as off-path, and the
> rejection of `OptimizeFlattenMaterial` as a 32-producing shrink.

# 32 vs 1024, from source — and the cap ruling would be a no-op

**Source only. No editor, no build, no write.**

**Headline: `HLODTextureSize` may never be read at all, and raising
`HLODMaxTextureSize` to 4096 may change nothing.** The arithmetic below
reproduces the observed 1024 *exactly* from the `AutomaticSize` branch,
which does not consult `HLODTextureSize`.

---

## 1. `LandscapeHLODBuilder.cpp:210-240`, verbatim

```cpp
210| static int32 ComputeRequiredTextureSize(const ALandscapeProxy* InLandscapeProxy, const float InViewDistance, const FMeshDescription* InMeshDescription)
211| {
212| 	int32 RequiredTextureSize = 0;
213|
214| 	switch (InLandscapeProxy->HLODTextureSizePolicy)
215| 	{
216| 		case ELandscapeHLODTextureSizePolicy::AutomaticSize:
217| 		{
218| 			const float TargetTexelDensityPerMeter = FMaterialUtilities::ComputeRequiredTexelDensityFromDrawDistance(InViewDistance, static_cast<float>(InMeshDescription->GetBounds().SphereRadius));
219| 			RequiredTextureSize = GetMeshTextureSizeFromTargetTexelDensity(*InMeshDescription, TargetTexelDensityPerMeter);
220| 		} break;
221|
222| 		case ELandscapeHLODTextureSizePolicy::SpecificSize:
223| 		{
224| 			RequiredTextureSize = InLandscapeProxy->HLODTextureSize;
225| 		} break;
226| 	}
227|
228| 	// Clamp to a sane minimum value
229| 	const int32 MinLandscapeHLODTextureSize = 16;
230| 	RequiredTextureSize = FMath::Max(RequiredTextureSize, MinLandscapeHLODTextureSize);
231|
232| 	// Clamp to the project's max texture size for landscape HLODs
233| 	const ULandscapeSettings* LandscapeSettings = GetDefault<ULandscapeSettings>();
234| 	RequiredTextureSize = FMath::Min(RequiredTextureSize, LandscapeSettings->GetHLODMaxTextureSize());
235|
236| 	// Clamp to the maximum possible texture size for safety
237| 	RequiredTextureSize = FMath::Min(RequiredTextureSize, (int32)GetMax2DTextureDimension());
238|
239| 	return RequiredTextureSize;
240| }
```

Call site — note **both** arguments that feed the Automatic branch:

```cpp
388| int32 TextureSize = ComputeRequiredTextureSize(LandscapeProxy, static_cast<float>(InHLODBuildContext.MinVisibleDistance), MeshDescription);
389| LandscapeMaterial = BakeLandscapeMaterial(InHLODBuildContext, *MeshDescription, LandscapeProxy, TextureSize);
```

And the size is applied to five properties before the bake
(`:247-251`), then `OptimizeFlattenMaterial` runs (`:255`).

## Term table

| term | line | policy branch | full build | single-cell |
|---|---|---|---|---|
| `HLODTextureSizePolicy` | 214 | selector | see §3 | **AutomaticSize** (proved) |
| `InViewDistance` ← `MinVisibleDistance` | 388, 218 | **AutomaticSize only** | 76800 cm (derived) | unknown |
| `MeshDescription->GetBounds().SphereRadius` | 218 | **AutomaticSize only** | full proxy | unknown |
| `Mesh3DArea` → `TexelRatio` | 168-193 | **AutomaticSize only** | 508 m edge | unknown |
| `HLODTextureSize` | 224 | **SpecificSize only** | 4096 (if taken) | not taken |
| `Max(_, 16)` | 230 | both | inert | inert |
| `Min(_, HLODMaxTextureSize)` | **234** | both | **1024** | not binding at 32 |
| `Min(_, GetMax2DTextureDimension())` | 237 | both | inert | inert |
| `OptimizeSampleArray` | 2428-2449 | post-bake | see §3 | see §3 |
| `TextureSizingType` | — | **absent** | landscape path never uses it | — |

⭐ **`TextureSizingType_AutomaticFromMeshDrawDistance` does not appear on
this path at all.** It belongs to `FMaterialProxySettings`
(MeshMerge/MeshApproximate builders). The landscape builder has its own
policy enum and never consults it. That lever is not in play.

## 2. What supplies the draw distance — and it is the same for both paths

```cpp
WorldPartitionHLODUtilities.cpp:1044
    HLODBuildContext.MinVisibleDistance = HLODActor->GetMinVisibleDistance();
WorldPartitionHLODUtilities.cpp:421-424    (setup, not build)
    if (!FMath::IsNearlyEqual(HLODActor->GetMinVisibleDistance(), InCreationParams.MinVisibleDistance))
        HLODActor->SetMinVisibleDistance(InCreationParams.MinVisibleDistance);
```

**`MinVisibleDistance` is PERSISTED ON THE HLOD ACTOR**, written once at
`-SetupHLODs` time and read back at build time. `-BuildHLODs` and
`-BuildSingleHLOD` both reach it through the same line 1044, from the
same stored actor.

**So the single-cell path DOES populate it, identically.** The
`-BuildSingleHLOD` code (`WorldPartitionHLODsBuilder.cpp:180`, filter
`:1134`, force `:185`) only *filters which actors are visited*; it does
not construct the build context differently.

## 3. Candidate verdicts

**Candidate A — "`MinVisibleDistance` differs between the two paths."
REJECTED.** Decided by `WorldPartitionHLODUtilities.cpp:1044`: both paths
read it off the persisted actor. A single-cell run cannot give that term
a different value than a full run of the same cell.

**Candidate B — "on-disk proxy state differs from what the editor
reports." NOT REJECTED, and now the leading explanation**, but sharpened:
the discriminator is not the *stored* value, it is which **branch**
runs. Decided by elimination at `:222-237`:

    SpecificSize with HLODTextureSize = 4096:
      :224 -> 4096   :230 -> 4096   :234 -> 1024   :237 -> 1024

**The SpecificSize branch cannot produce 32 from 4096.** Its floor is
`Max(_,16)` and 4096 never descends below 1024 under this project's cap.
Therefore the pilot build executed the **AutomaticSize** branch — whatever
the editor reports for the policy.

The mechanism that can force it is `Landscape.cpp:5044-5049`, in
`PostLoad`:

```cpp
// Keep previous behavior of landscape HLODs if created before the settings were added
if (GetLinkerCustomVersion(FFortniteMainBranchObjectVersion::GUID) < FFortniteMainBranchObjectVersion::LandscapeAddedHLODSettings)
{
    HLODTextureSizePolicy   = ELandscapeHLODTextureSizePolicy::AutomaticSize;
    HLODMeshSourceLODPolicy = ELandscapeHLODMeshSourceLODPolicy::AutomaticLOD;
}
```

**Candidate C (new, from `:255`) — `OptimizeFlattenMaterial` shrank it.
REJECTED.** `MaterialUtilities.cpp:2428-2449`: `OptimizeSampleArray`
collapses a sample array **only when every texel is one colour**, and
then to `FIntPoint(1,1)`. It can produce 1×1; it cannot produce 32.

## The arithmetic, and it lands on 1024 exactly

`ComputeRequiredTexelDensityFromDrawDistance` (MaterialUtilities.cpp
:2674-2691) with `FPerspectiveMatrix(45°, 1920, 1080)` — the sphere
radius cancels:

    TexelDensity(per m) = max(M00, M11) x 1920 x 50 / D_cm
                        = 170666.7 / D_cm          (M11 = 1920/1080)

`GetMeshTextureSizeFromTargetTexelDensity` (LandscapeHLODBuilder.cpp
:168-193) with a 508.1 m proxy (8129 verts / 16 proxies, 1 m/vertex),
area 2.581e9 cm², `TexelRatio = 100/sqrt(area) = 0.00196850`:

| D (cm) | target density | perfect | lo | hi | **chosen** |
|---|---|---|---|---|---|
| 25 600 | 6.66667 | 3388 | 2048 | 4096 | 4096 |
| 51 200 | 3.33333 | 1694 | 1024 | 2048 | 2048 |
| **76 800** | **2.22222** | **1130** | **1024** | 2048 | **1024** |
| 102 400 | 1.66667 | 847 | 512 | 1024 | 1024 |

**76 800 cm is the Instanced layer's measured `loading_range`** (read
2026-09-13). The formula reproduces the observed **1024** exactly, on a
number it was not fitted to.

⛔ **BUT 1024 IS ALSO WHAT SpecificSize GIVES** (4096 clamped by the
1024 cap). **The two branches COINCIDE at 1024 on the sibling cells, so
the sibling evidence cannot distinguish them.** Only the pilot cell's 32
discriminates, and it discriminates in favour of AutomaticSize.

What reaches 32, holding the other term fixed:

| varying | value | chosen |
|---|---|---|
| mesh edge, D = 76 800 | 15–20 m (vs 508 m) | **32** |
| draw distance, full 508 m area | ≈ 20 km (vs 768 m) | **32** |

Both are inputs to `:218-219`, i.e. the AutomaticSize branch reading a
different mesh or a different distance. A 15–20 m mesh from a 508 m
proxy is the more plausible of the two — a partially-resident landscape
at bake time — but **neither is established and I am not choosing
between them from source alone.**

## 4. The two predictions

**(a) `-BuildSingleHLOD` with the context supplied correctly → 1024.**
Derivation: same actor, same persisted `MinVisibleDistance` = 76 800 cm
(`:1044`), same full-proxy mesh → the table above selects `lo = 1024`.
The pilot's 32 is then explained entirely by a degraded mesh/bounds
input, not by the flag.

**(b) Full `-BuildHLODs` with `HLODMaxTextureSize` raised to 4096 →
CONDITIONAL, and most likely STILL 1024.**

* If **AutomaticSize** is in force (what the pilot's 32 proves for at
  least that build): `:219` yields 1024 from mesh+distance, and `:234`
  becomes `Min(1024, 4096)` — **not binding. Result 1024. Raising the
  cap changes nothing.**
* If **SpecificSize** is in force: `:224` yields 4096, `:234` becomes
  `Min(4096, 4096)` — **result 4096.**

**So the proposed cap ruling is a coin-flip on a question nobody has
settled yet**, and half the time it is a no-op that costs a full
rebuild. Settle the branch first.

### The cheapest way to settle it — no build required

Under `AutomaticSize`, halving the loading range doubles the texture
(the table: 76 800 → 1024, 51 200 → 2048, 25 600 → 4096). Under
`SpecificSize` the loading range does nothing. **One cell built at a
different `MinVisibleDistance` separates the two branches definitively**,
and it also tells you whether 4096 is reachable without touching the cap
at all — the table says a 25 600 cm draw distance reaches 4096 under
AutomaticSize.

That is a better experiment than raising the cap, because it is
reversible, single-cell, and its two possible outcomes mean different
things.
