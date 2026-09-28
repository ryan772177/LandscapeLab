# REGISTER — landscape HLOD, and what actually governs it

**Ruled 2026-09-13.** Supersedes the Task 5 ruling text of 2026-09-13
(the "apply the census settings to the Landscape HLOD layer" unit).
**No actor was mutated and no build was run to produce this.**

---

## 1. Landscape HLOD runs through Instanced → Merged, by world-default fallback

    world DefaultHLODLayer     /Game/Alpine8K_HLODLayer_Instanced
    chain                      Instanced (INSTANCING, range 76800)
                                 -> Merged (MESH_APPROXIMATE, range 51200)
                                 -> end
    actors naming an HLOD layer   0 of 4,339   (0 raises, 4,339 Nones)

⭐ **The 0 does NOT mean the landscape is outside HLOD.** A null
per-actor `HLODLayer` **falls back to the world default**:

    WorldPartitionRuntimeHashSetConversions.cpp:45
      ActorDescView.GetHLODLayer().IsValid()
        ? Cast<UHLODLayer>(ActorDescView.GetHLODLayer().TryLoad())
        : DefaultHLODLayer

So all 4,339 actors — the Landscape and its 256 streaming proxies
included — are assigned to `Alpine8K_HLODLayer_Instanced` by fallback,
and always were. The earlier reading of that 0 as "the landscape is
missing from HLOD" was wrong in the direction that would have caused a
needless 257-actor streaming change.

## 2. `Alpine8K_HLODLayer_Landscape` and `_FoliageApprox` are REDUNDANT

Neither is named by any actor, and neither is in the world default
chain. **Marked REDUNDANT. Deletion deferred to the audit rewrite
session** — they are left in place, not trashed, so nothing that
references them by name breaks before that session rules on them.

## 3. ⛔ The 2026-09-13 census-value write on the Landscape layer is VOID

That write set, on `Alpine8K_HLODLayer_Landscape`:

    hlod_builder_settings -> mesh_merge_settings -> material_settings
      texture_sizing_type   UseSingleTextureSize
                              -> AutomaticFromMeshDrawDistance
      merge_materials       False -> True

It reads back correctly from a freshly loaded asset. **It governs
nothing, and it could not govern anything even if the layer were
assigned**, because landscape components never reach a MeshMerge
builder:

    LandscapeComponent.cpp:97-100
      TSubclassOf<UHLODBuilder> ULandscapeComponent::GetCustomHLODBuilderClass() const
      { return ULandscapeHLODBuilder::StaticClass(); }

    HLODBuilder.cpp:354
      TSubclassOf<UHLODBuilder> HLODBuilderClass =
          SourceComponent->GetCustomHLODBuilderClass();
      HLODBuildersForComponents.FindOrAdd(HLODBuilderClass).Add(SourceComponent);

The override is **unconditional** — it consults no layer, no setting and
no cvar. Components are regrouped by builder class before any building
happens, so a landscape component is handed to `ULandscapeHLODBuilder`
under every layer assignment that exists.

**The Task 5 unit measured and applied a setting on the wrong
mechanism.** Its acceptance is void, not failed: nothing it changed was
ever read by the thing it meant to change.

## 4. The real landscape-HLOD levers are FOUR PROXY PROPERTIES

`LandscapeProxy.h`, all marked `LandscapeOverridable` so each proxy may
differ from the parent:

| header | :line | python | measured, all 257 actors |
|---|---|---|---|
| `HLODTextureSizePolicy` | 958 | `hlod_texture_size_policy` | `SPECIFIC_SIZE (1)` |
| `HLODTextureSize` | 963 | `hlod_texture_size` | `256` |
| `HLODMaterialOverride` | 966 | `hlod_material_override` | `None` |
| `HLODMeshSourceLODPolicy` | 971 | `hlod_mesh_source_lod_policy` | `LOWEST_DETAIL_LOD (2)` |
| `HLODMeshSourceLOD` | 974 | `hlod_mesh_source_lod` | `0` (inert — reads only under `SpecificLOD`) |
| `bUseLandscapeForCullingInvisibleHLODVertices` | 954 | `use_landscape_for_culling_invisible_hlod_vertices` | `false` |

**Sample counts, per standing rule 13:** 257 actors read, **257 OK and 0
raises on every property**, **0 outliers** — the parent Landscape and all
256 proxies carry identical values. Read per-actor rather than off the
parent precisely because `LandscapeOverridable` allows a single proxy to
diverge invisibly.

### These are the 5.8 CONSTRUCTOR defaults — nothing was ever chosen

    Landscape.cpp:1780-1783
      HLODTextureSizePolicy   = ELandscapeHLODTextureSizePolicy::SpecificSize;
      HLODTextureSize         = 256;
      HLODMeshSourceLODPolicy = ELandscapeHLODMeshSourceLODPolicy::LowestDetailLOD;
      HLODMeshSourceLOD       = 0;

⛔ **`AutomaticSize` / `AutomaticLOD` is the LEGACY path, not the modern
default** — the opposite of the natural guess:

    Landscape.cpp:5044-5049
      // Keep previous behavior of landscape HLODs if created before the
      // settings were added
      if (GetLinkerCustomVersion(...) < ...LandscapeAddedHLODSettings)
      { HLODTextureSizePolicy = AutomaticSize;
        HLODMeshSourceLODPolicy = AutomaticLOD; }

So a landscape authored in 5.8 gets SpecificSize/256/LowestDetailLOD,
and ours carries exactly that, untouched.

## 5. A material change DOES dirty landscape HLOD cells

`ULandscapeHLODBuilder::ComputeHLODHash` hashes the materials
(`LandscapeHLODBuilder.cpp:70-90`):

    if (HLODMaterialOverride) HashBuilder << HLODMaterialOverride;
    else { HashBuilder << (bUseDynamicMaterialInstance
                             ? MaterialInstancesDynamic : MaterialInstances);
           HashBuilder << OverrideMaterial; }
    HashBuilder << OverrideHoleMaterial;

plus Nanite settings (:95-107), the two HLOD policy fields (:109-121)
and the project's `HLODMaxTextureSize` (:124). `HLODMaterialOverride` is
`None` here, so the landscape's own `MaterialInstances` are hashed — and
a change to `M_Alpine8K` therefore changes the hash and flags the cell.

## 6. ⛔ `-SetupHLODs` CANNOT report which cells are flagged

    WorldPartitionHLODsBuilder.cpp:432-438
      if (bRet && ShouldRunStep(EHLODBuildStep::HLOD_Setup))
          bRet = SetupHLODActors();
      if (!bReportOnly) {
          if (bRet && ShouldRunStep(EHLODBuildStep::HLOD_Build))
              bRet = BuildHLODActors();
          ...
      }

`-ReportOnly` does not make the build step *dry* — it **skips the build
step entirely**. The rebuild policy (`HLODRebuildPolicyHashCompare`) is
evaluated inside `BuildHLODActors`, so a report-only pass emits **zero**
Approve/Reject lines by construction. This is the source-level reason
behind the observation already recorded in STATE.md §3.

**Measured this session, not merely predicted.**
`-SetupHLODs -ReportOnly`, run 2026-09-13 into
`_verify/hlod/setup_20260914_audit/`:

    manifest    12 sections, 2,267 GUIDs
                EngineVersion 5.8.1-56057345+++UE5+Release-5.8
    read-back   ReportOnly wrote nothing: 0 of 2,267 packages changed
                (byte-for-byte AND mtime-for-mtime)
    log         2,800,322 bytes, lists all 2,267 cells
                "final decision" lines        0
                "Building HLOD actor" lines   0

**Sample count beside the verdict (standing rule 13):** the log was
searched over 2,267 listed cells and found **zero** decisions — the
instrument saw plenty and reported none, so the zero carries meaning.
Source and log agree, and they are different instruments (NN8).

The cell list is opaque external-actor package paths
(`/Game/__ExternalActors__/Alpine8K/0/0Q/DKJMHCNOJVQ3B91V5L9MBR`), and
the saved `HLODBuildReport` carries only a header plus rebuild-policy
data (`HLODActor.cpp:830-854`) — no source-component list. So **even the
landscape / non-landscape split of the 2,267 population is not derivable
from this pass**, let alone the dirty subset.

**Consequence: the flagged-dirty count cannot be obtained without a pass
that also writes cells.** The 2026-09-13 `layers_20260913_203538` run
got its numbers by building: 89 cells evaluated, **46 approved (27 under
`Alpine8K_HLODLayer_Instanced`, 19 under `Alpine8K_HLODLayer_Merged`)**,
43 rejected — and those 46 were written, which is how the "my probes
BUILT 46 cells" line in STATE.md came about.

## 7. Build status since 2026-09-13

**No HLOD build has been started since 2026-09-13 21:00 local.** Last
external-actor package write is 21:00; no run directory, no commandlet
log and no package write after it. The last run that built anything was
`layers_20260913_203538` (20:35–21:00), attributed above.

**Nothing has ever been built under `Alpine8K_HLODLayer_Landscape`** —
every run on record (09-08: 1,678 Instanced + 1,238 Merged approved;
09-09: 1,343 + 1,134; 09-13: 27 + 19) produced cells under Instanced and
Merged only.

Attribution comes from the builder's own line, which names the layer
folder and the source cell separately:

    LogWorldPartitionHLODsBuilder: [6 / 6] Building HLOD actor
      Alpine8K_HLODLayer_Merged/Alpine8K_HLODLayer_Instanced_L0_X-8_Y10...

The folder is the layer the actor belongs to; the cell name is what it
was built FROM. The Merged-from-Instanced row above is the cascade
working. A bare Approve/Reject count carries no cell identity and cannot
answer "under which layer" — which is why the earlier "46 cells" told
nobody whether the Landscape layer had been exercised.

## 8. What the census can and cannot say

`research/census/` records `world_partition.default_hlod_layer` per map
and the HLOD layer assets, but **not per-actor `HLODLayer`** and **not
the four landscape proxy properties** (grepped: 0 occurrences of any of
them across every census file).

    CitySample Small_City_LVL   landscape_materials 0   default /Game/Map/HLOD/CitySample_HLOD0
    DarkRuins Main              landscape_materials 0   default /Game/Main_HLODLayer_Instanced
                                (the rollup notes it has no Landscape actor at all)
    ElectricDreams_PCG          landscape_materials 1   default NULL
    ElectricDreams_PCGCloseRange landscape_materials 0  default NULL

**The only landscape-bearing Epic sample in the census has no world
default HLOD layer**, and the census cannot show whether it names one
per actor. So "do it the way Epic does" is **unanswerable from the
corpus as it stands**, and was not used as the basis for any decision
here.

**To close it** the census needs a landscape-actor section — re-run
`scripts/census_project.py` against ElectricDreams reading the six
properties in §4 off every `Landscape` / `LandscapeStreamingProxy`. Not
run this session: it means opening a 5.8 vault sample, a heavy op
outside this session's fences.

**No proposal is filed** (the ruling's item 4). A proposal needs two
values side by side and only one exists — and since ours are unmodified
engine constructor defaults, any sample that also never touched them
would match by construction, so the comparison only becomes informative
if ElectricDreams turns out to have changed them deliberately.
