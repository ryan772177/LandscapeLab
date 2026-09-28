# Landscape HLOD pilot — BLOCKED at task 4's premise. Header findings first.

**Stopping after tasks 1 and 2, which is the brief's own stop condition.
Nothing was touched: no actor mutated, no `hlod_layer` set, no build run.**

The blocker: **4096 and 2048 would both clamp to 1024**, so the pilot's
central comparison cannot produce two different answers.

---

## Task 1 — header findings, with line cites

### 1a. `Alpine8K_HLODLayer_Landscape`'s layer_type

**`MESH_MERGE` (`EHLODLayerType::MeshMerge`, enum value 1)** — read off
the asset 2026-09-13, 257/257 consistent. **That is already a baking
type**, so task 3's "set layer_type if it isn't a baking type" needs no
change.

### 1b. Which layer types invoke `ULandscapeHLODBuilder`

**All of them.** The dispatch is per-COMPONENT and happens above the
layer's own builder:

    HLODBuilder.cpp:349-356   (the BASE outer Build)
        for (UActorComponent* SourceComponent : InputComponents)
            TSubclassOf<UHLODBuilder> HLODBuilderClass =
                SourceComponent->GetCustomHLODBuilderClass();
            HLODBuildersForComponents.FindOrAdd(HLODBuilderClass)
                .Add(SourceComponent);

    LandscapeComponent.cpp:97-100
        ULandscapeComponent::GetCustomHLODBuilderClass()
            -> ULandscapeHLODBuilder::StaticClass()   (unconditional)

There are TWO `Build` overloads and the distinction is what settles this:

| overload | where | overridden by |
|---|---|---|
| `FHLODBuildResult Build(const FHLODBuildContext&)` — **outer** | `HLODBuilder.cpp:326` | **nobody** |
| `TArray<UActorComponent*> Build(ctx, components)` — **inner**, `PURE_VIRTUAL` | `HLODBuilder.h:166` | `HLODBuilderInstancing.h:71`, `HLODBuilderMeshApproximate.h:41`, `LandscapeHLODBuilder.h` |

`UHLODBuilderInstancing` and `UHLODBuilderMeshApproximate` override only
the **inner** one, so the outer regrouping runs for every layer type.
The layer type selects the builder for **non-landscape** components only
(`WorldPartitionHLODUtilities.cpp:452-478`).

### 1c. ⛔ Which value the landscape bake reads — and the cap nobody named

It reads **`ALandscapeProxy::HLODTextureSize`**, NOT the layer's
`material_settings.texture_size`:

    LandscapeHLODBuilder.cpp:210  ComputeRequiredTextureSize(const ALandscapeProxy*, ...)
                            :214    switch (InLandscapeProxy->HLODTextureSizePolicy)
                            :222    case ELandscapeHLODTextureSizePolicy::SpecificSize:
                            :224        RequiredTextureSize = InLandscapeProxy->HLODTextureSize;
                            :229-230  clamp to a minimum of 16
    ⛔                      :234    RequiredTextureSize = FMath::Min(
                                      RequiredTextureSize,
                                      LandscapeSettings->GetHLODMaxTextureSize());

and the project cap:

    LandscapeSettings.h:137   int32 HLODMaxTextureSize = 1024;
    LandscapeSettings.h:68    GetHLODMaxTextureSize() const { return HLODMaxTextureSize; }

**`LandscapeLab/Config/*.ini` does not override it** (grepped: zero
matches for `HLODMaxTextureSize` or `LandscapeSettings`), so the 1024
default is in force.

**Consequence: `HLODTextureSize` 4096 → clamped to 1024. 2048 → clamped
to 1024.** Task 4's two arms are the same experiment. The measurement it
was designed to produce does not exist at these values.

The cap is `UPROPERTY(EditAnywhere, config, …, ClampMin="64",
ClampMax="8192")`, so it **can** be raised — but only by a project-wide
config change, which this brief did not authorise.

This also explains the 09-14 acceptance failure more completely than the
layer argument alone did: even had the landscape reached a baking
builder, 4096 could never have appeared.

## Task 2 — can the builder build a single cell? **Yes.**

The engine supports it directly:

    WorldPartitionHLODsBuilder.cpp:180   GetParamValue("BuildSingleHLOD=", HLODActorToBuild)
                                 :1134   if (!HLODActorToBuild.IsNone() &&
                                             HLODActorDesc.GetActorLabel() != HLODActorToBuild) return;
                                 :185    bForceBuild = bForceBuild || !HLODActorToBuild.IsNone();

so `-BuildSingleHLOD=<actor label>` filters to one cell **and forces the
rebuild**, which is exactly what a pilot needs. `-BuildHLODLayer=<layer
asset name>` (`:179`, filtered `:1140`) scopes to one layer.

`scripts/hlod_build_batched.py` does **not** expose either flag — its
granularity is the manifest batch — but `base_args()` already carries the
mandatory `-noxgecontroller`, so a single-cell invocation is
`base_args(log) + ["-BuildHLODs", "-BuildSingleHLOD=<label>"]`.

**So the pilot is scopeable. It is blocked on the value, not the
mechanism.**

## What was read live (read-only, nothing written)

Landscape actors, 257/257 read, 0 raised, 0 outliers:

| property | value | denominator |
|---|---|---|
| `enable_auto_lod_generation` | **True** | 257/257 |
| `enable_nanite` | True | 257/257 |
| `LandscapeNaniteComponent` count | 256 | 257 actors |
| `LandscapeComponent` count | 28 | first 8 actors only |

So the landscape **is** flagged for HLOD. `bEnableAutoLODGeneration` is
not the exclusion.

`ULandscapeComponent::IsHLODRelevant()` (`Landscape.cpp:2178-2190`)
returns `CanBeHLODRelevant(this) && bEnableAutoLODGeneration`, and
`CanBeHLODRelevant` (`ActorComponent.cpp:3424-3450`) only rejects
invalid, transient, editor-only or visualisation components — none of
which a landscape component is.

⚠ `ULandscapeNaniteComponent::IsHLODRelevant()` returns **false
unconditionally** (`LandscapeNaniteComponent.cpp:222-226`) — by design,
because the plain components are supposed to cover it. With
`enable_nanite` True on all 257 and 256 Nanite components present, this
is worth keeping in view, but it is not the exclusion either: the plain
`LandscapeComponent`s exist and are relevant.

**So every precondition for a landscape bake is satisfied, and the
2026-09-14 census over all 2,267 cells still found none.** Why remains
OPEN. The build's own `InputStats` would answer it and is not reflected
to Python (all 15 editor-only properties on `AWorldPartitionHLOD` raise).

## The ruling this needs

The pilot can proceed the moment one of these is chosen:

1. **Raise `HLODMaxTextureSize` in `DefaultEngine.ini`** to 4096 (or
   8192, the ClampMax) under `[/Script/Landscape.LandscapeSettings]`,
   then run the pilot as written. A project-wide config change; it also
   changes the HLOD hash (`LandscapeHLODBuilder.cpp:124` hashes it), so
   it invalidates every landscape-bearing cell.
2. **Re-scope the pilot to 1024 vs 512**, both under the cap, which
   measures the same disk/VRAM/time relationship without touching
   project config.

Option 2 answers the engineering question — how does baked landscape
texture size trade against disk, VRAM and build time — at a quarter of
the blast radius. Option 1 is needed only if 4096 is the intended
shipping value.

**Neither applied. No experiment run.**
