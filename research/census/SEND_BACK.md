# Census send-back — 2026-09-09

**Three of four projects censused, five maps.** One is blocked on a C++
rebuild. Full reasoning in `AVAILABILITY.md`.

    map                              hlod  imp   wp   pcg  fol  landscape
    CitySample__Small_City_LVL         16   94   yes    ?    ?      0
    DarkRuins__Main                    11   16   yes   54    0      0
    ElectricDreams__PCGCloseRange       9    9   yes   72   62      0
    ElectricDreams__PCG (far range)     9    9   yes   72   62      1
    CitySample__Startup                first pass, wrong map -- kept, named honestly

City Sample's `?` are explained under "the cost of a deletion" below.

## ⭐ THREE FALSE ZEROS — a section can read 0 because it looked in the wrong place

    Electric Dreams   pcg_graphs     0 -> 72      foliage_types  0 -> 62
    Dark Ruins        pcg_graphs     0 -> 54

`_assets_of` hardcoded the package `/Script/Engine`. `UPCGGraph` lives in
`/Script/PCG` and `UFoliageType` in `/Script/Foliage`, so the queries asked a
package where the class does not exist, got an empty list, **threw nothing**,
and returned a clean zero.

**The PCG reference project reported zero PCG graphs**, and I accepted it
because `current_world` was correct and everything around it looked right.
`foliage_types: 0` survived three censuses for the same reason.

Worse than the `world_partition` bug and the same family — that one at least
left an `_error` behind. This left no trace at all.

**Every census now carries `asset_lookup_trace`**: which package each class
hit and how many it found. That turns an ambiguous zero into a decidable one:

    DarkRuins  FoliageType  ['/Script/Foliage:0', '/Script/Engine:0', ...]
      -> a MEASURED absence: the lookup reached where UFoliageType lives.
    DarkRuins  PCGGraph     ['/Script/PCG:54']
      -> was a false zero, now correct.

**A zero is only trustworthy if the lookup reached a place where the thing
could have been.** "Nothing found" and "looked in the wrong place" are
indistinguishable in a result and opposite in meaning.

## ⛔ THE COST OF A DELETION — City Sample cannot be re-censused

I deleted its 106 GB vault copy during a disk crisis (2.7 GB free with an
editor running; its census was already committed). A whole-drive search now
finds only the content-free text extract.

    CitySample__Small_City_LVL.json
      hlod_layers 16, impostors 94, world_partition, lighting   VALID
      foliage_types 0, pcg_graphs 0                             UNVERIFIED

Those two zeros came from the broken lookup and cannot be confirmed without
re-downloading 106 GB.

**A committed artefact is not the same as a closed question.** The census was
committed and still had two unverified numbers in it; I treated "committed"
as "done with" when deciding what was safe to delete.

## The landscape material — the find most relevant to our own work

Only the **far-range** map has one, and it is the sole non-zero
`landscape_materials` in the whole census:

    /Game/Landscape/MI_BGLandscape_Auto_01
      21 distinct expression types
      MaterialExpressionScalarParameter        36
      MaterialExpressionLinearInterpolate      13
      MaterialExpressionMultiply               12
      MaterialExpressionSaturate               11
      MaterialExpressionTextureSample          10
      MaterialExpressionMaterialFunctionCall    7

The close-range map has none, which is why censusing **both** PCG maps
mattered: the project-wide sections are identical between them and only the
world-scoped ones differ.

| # | Project | Result |
|---|---|---|
| 1 | Electric Dreams | **CENSUSED, BOTH PCG MAPS** — installed mid-session; 55.86 GB, 23,225 uassets |
| 2 | City Sample | **CENSUSED** — 2 JSONs, 5 shots (see the caveat) |
| 3 | Valley of the Ancient | **BLOCKED** — C++ modules are 5.7 binaries; needs a 7-module rebuild in Visual Studio |
| 4 | Dark Ruins | **CENSUSED** — installed by the operator mid-session; blueprint-only, converted 5.6 → 5.8 cleanly |

## ✅ RESOLVED — `world_partition` IS NOW CAPTURED (both projects)

The correction below stands as the record of what went wrong, but **the
accessors are fixed and both censuses were re-run cleanly.** Current state:

| | City Sample | Dark Ruins |
|---|---|---|
| `world_partition_path` | `WorldPartition_1` | `WorldPartition_0` |
| `default_hlod_layer` | `/Game/Map/HLOD/CitySample_HLOD0` | `/Game/Main_HLODLayer_Instanced` |
| `runtime_hash_class` | `WorldPartitionRuntimeHashSet` | `WorldPartitionRuntimeHashSet` |
| `enable_light_shaft_bloom` | `false` | `false` |
| `enable_light_shaft_occlusion` | `false` | `false` |

Three fixes, all traced to source rather than guessed:

    World.get_world_partition()   does not exist in 5.8. Replaced with
      UWorldSettings.world_partition        WorldPartition.h:556
      runtime_hash via unreal.find_object   NOT get_editor_property
    bEnableLightShaftBloom        LightComponent.h:249
    bEnableLightShaftOcclusion    DirectionalLightComponent.h:32
      -- the reflected names carry the `enable_` prefix; the payload omitted it

**One limit is NOT fixable and is now labelled as such.** `RuntimePartitions`
is declared `private:` on `UWorldPartitionRuntimeHashSet`, so it is not
reflected to Python at all — and **cell size and loading range live inside
it**. The record says so explicitly rather than emitting a bare error:

    "_runtime_partitions_note": "EXPECTED, NOT A BUG: ... declares
     RuntimePartitions as private, so it is not reflected to Python. The cell
     size and loading range live inside it and cannot be read this way."

This repo hit the same wall during the E-phase work
(`scripts/payloads/bench_grid_derive.py:139`). Getting those two numbers needs
a different route entirely — the subsystem, or the loading range override.

## ⛔ THE CORRECTION THAT LED HERE — `world_partition` was reported as captured when it was not

I twice reported City Sample's `world_partition` as a captured target on the
strength of the section showing **1 entry**. That entry is an error record:

    "world_partition": {
      "/Game/Map/Small_City_LVL.Small_City_LVL": {
        "_error": "'World' object has no attribute 'get_world_partition'"
      }
    }

**A count of one is not a measurement of one.** I was counting dict entries
without asking whether the entries were data, which is precisely what the
payload's own header warns about: *"a null with `_error` is a name to fix
against the header, not a finding"*. It reads identically to a real result in
a section summary.

Same error in both projects. Separating real entries from error-only ones:

| section | City Sample | Dark Ruins | |
|---|---|---|---|
| `project` | 3 real | 3 real | |
| `hlod_layers` | **16 real** | **11 real** | ✅ |
| `impostors` | **94 real** | **16 real** | ✅ |
| `lighting` | 1 real | 1 real | ✅ but see below |
| `world_partition` | ~~0 real~~ **now captured** | ~~0 real~~ **now captured** | ✅ fixed, see above |
| `foliage_types` / `pcg_graphs` / `landscape_materials` / `water` | 0 | 0 | genuinely absent |

### The three API names that need fixing (identical in both projects)

    World.get_world_partition                    does not exist in 5.8
    DirectionalLightComponent.light_shaft_bloom      property not found
    DirectionalLightComponent.light_shaft_occlusion  property not found

So `lighting` is real but **incomplete** — the two light-shaft fields are
missing from every directional light.

For the world-partition accessor, this project already solved the same problem
in `scripts/payloads/bench_grid_derive.py`: `get_editor_property` and plain
attribute access both refuse `runtime_hash`, and the working route was
`unreal.find_object(world_partition, "WorldPartitionRuntimeHashSet_0")`.
`WorldPartitionBlueprintLibrary` is the other candidate surface.

**Those are now fixed and both projects were re-censused.** What remains
unreachable is only the cell size / loading range, for the private-property
reason given above.

## The JSONs

    research/census/CitySample__Small_City_LVL.json    world confirmed
    research/census/DarkRuins__Main.json               world confirmed
    research/census/CitySample__Startup.json           first pass, wrong map
    research/census/*.stations.json                    derived camera stations

`CitySample__Small_City_LVL.json` — `current_world`
`/Game/Map/Small_City_LVL.Small_City_LVL`:

    hlod_layers      16 real   <- named target, CAPTURED
    impostors        94 real
    lighting          1 real   (missing 2 light-shaft fields, see correction)
    project           3 real
    world_partition   CAPTURED  path + default HLOD layer + hash class
    foliage_types / pcg_graphs / landscape_materials / water   genuinely 0

`DarkRuins__Main.json` — `current_world` `/Game/Main.Main`, converted 5.6 → 5.8:

    hlod_layers      11 real
    impostors        16 real
    lighting          1 real   <- named target for this project, but see the
                                  correction: 2 light-shaft fields are missing
    project           3 real
    world_partition   CAPTURED  path + default HLOD layer + hash class
    landscape_materials  0     <- NOTE: tessellation/displacement was a named
                                  target here. Zero means the map has no
                                  Landscape actor at all -- plausible for a
                                  Megascans ruins scene built from meshes --
                                  so that target is not answered by this
                                  section, and the zero should NOT be read as
                                  "measured and absent".

Dark Ruins loaded **9,037 actors with none skipped**, against City Sample's
16 kept / 4 skipped. City Sample is World Partition and streams actors in, so
an editor pass sees almost nothing; Dark Ruins loads its whole scene. Bounds
are therefore trustworthy for Dark Ruins (~214 × 158 m) and are **not** for
City Sample.

**`CitySample__Startup.json` is kept and named for what it actually is.** The
first pass censused `/Game/Map/Startup/Startup.Startup` — the project's
loading map — and reported `ok: true` with 141 KB written. Nothing in the
result said "wrong world". Its `hlod_layers` (16) and `impostors` (94) are
asset-registry-wide and therefore still valid; its `world_partition` and
`lighting` describe the loading map and should not be read as the city's.

Both sample projects have a loading map as their `EditorStartupMap`, so
**confirming `current_world` before trusting a census is not optional.**

## The shots — READ THIS BEFORE USING THEM

    research/census/shots/CitySample/*.png    5 frames, 1920x1080
    research/census/shots/CitySample/README.md

**They are one viewpoint, not the five-angle survey the filenames promise.**
Genuine `Small_City_LVL` content and useful as a record of the look, but
`wide_vista` and `overview_high` are the same street-level plaza as
`ground_closeup`.

`BugItGo` was accepted and logged the correct coordinates every time
(`Z=24700`, `Z=48479`). Three attempts — plain, then `ghost` no-clip flight,
then `r.HighResScreenshotDelay` — all produced the same frame. `-ExecCmds`
fires every command in one batch at startup, so `HighResShot` goes off in the
same breath as the teleport.

## The thing most worth your attention

**I wrote a check to catch exactly this failure, it printed PASS, and it was
backwards.** Calibrated afterwards against the known-bad set:

    known-bad (camera provably never moved)   min pairwise diff 10.37
    the "good" run                            min pairwise diff  9.77

It scored the failure **higher** than the success. Shader compilation
progresses between launches and recolours a static scene by more than a camera
move changes it; greyscale downscaling does not suppress that. The check now
reports its numbers with `NO VERDICT`.

**A metric that has not been run against a known-bad case is not a check.**

## What a working survey needs

Not attempted a fourth time; both routes are in BACKLOG:

* **MRQ with a camera possessed by a Level Sequence** — the `Bench_Dolly`
  pattern that works in our own project.
* **`bRemoteExecution=True` in the sample's `Config/DefaultEngine.ini`**, which
  would let `ue_exec` and `shoot.py` drive these projects directly. That is a
  config write outside this repo; standing rule 1 names it, and the waiver for
  this work covered opening and converting, not that. **Needs a ruling.**

## Mechanism notes for whoever picks this up

* `ue_exec` cannot reach the sample projects — no `bRemoteExecution` in their
  config. `ue_exec --project-root` was added so rule 7 *applies* to another
  project rather than blocking it, but the transport still needs the setting.
* `-ExecutePythonScript` calls `UUnrealEdEngine::CloseEditor()` the moment the
  script returns. Anything needing a tick — screenshots especially — cannot
  work inside it.
* Survey cameras derived from raw world bounds land in orbit: a sky sphere is
  an actor, and City Sample's raw Z max is 2,012,409 cm. Oversize actors must
  be excluded and percentiles used instead of min/max.
* World Partition means an editor pass sees only streamed-in actors —
  16 kept, 4 skipped as oversize for `Small_City_LVL`. Bounds derived that way
  are narrower than the world.
