# Read-backs and evidence for Pass 2 — 2026-09-13

Answers to the eight items the desk needs before Pass 2. Every number
here was measured this session against a live editor
(`5.8.1-56057345+++UE5+Release-5.8`, `/Game/Alpine8K.Alpine8K`, identity
and level both gated before any read).

**Four of these corrections change a Pass 1 verdict.** They are marked ⭐.

---

## 1. `benchmark.json` — ⭐ it is not where the audit says it is

AUDIT.md's "Inputs received" lists it as *benchmark.json (repo root)*.
There is no such file at the repo root. The one the bench actually reads
is at

    research/brief/brief1_distance_as_angle/brief1/benchmark.json

which is `scripts/bench_capture.py:61`. Copied verbatim to
`inputs/benchmark.json` (22,384 bytes). Any Pass-1 claim resolved against
a repo-root path resolved against nothing.

---

## 2. The bench MRQ config, as the engine holds it

`inputs/mrq_config_dump.json` (53,153 bytes), four keys: `dev`, `target`,
`dev+cinematic_quality_settings=True`, `dev+cinematic_quality_settings=False`.

Dumped through `scripts/bench_capture.py --dump-config`, which builds the
config with **the same construction a render uses** and stops before
starting. A separate dump tool would have been a second implementation of
that construction, and two lists that must agree are one list badly
stored (NN24).

### ⭐ 2a. The dev profile carries FIVE setting classes, and GameOverride is not one

    MoviePipelineDeferredPassBase
    MoviePipelineImageSequenceOutput_PNG
    MoviePipelineAntiAliasingSetting
    MoviePipelineConsoleVariableSetting
    MoviePipelineOutputSetting

`MoviePipelineGameOverrideSetting` was added **only** under `--truth`
(`bench_render.py`, the `if CFG.get("truth")` branch). So for every
dev-profile and every non-truth target capture ever taken, **the setting
was absent from the config entirely** — and with it `disable_hlods`,
`use_lod_zero`, `use_high_quality_shadows`, `flush_grass_streaming`,
`flush_streaming_managers`, `override_view_distance_scale` and
`cinematic_quality_settings`.

This resolves the first half of **P1-1**. The seven unread GameOverride
values were not merely unread; on these captures they were never applied.
P1-1's "READ-BACK-OWED (7)" understates it — the correct verdict for
non-truth captures is that the setting did not exist.

### ⭐ 2b. The dev profile is NOT `sg.*=1`

AUDIT.md P1-1 and the brief both describe it that way. Measured, the dev
cvar block is eleven entries and two of them are **3**:

    sg.ShadowQuality 1   sg.AntiAliasingQuality 1   sg.PostProcessQuality 1
    sg.FoliageQuality 1  sg.ViewDistanceQuality 1   sg.TextureQuality 1
    sg.EffectsQuality 1  sg.ShadingQuality 1
    sg.GlobalIlluminationQuality 3      <-- not 1
    sg.ReflectionQuality 3              <-- not 1
    r.ScreenPercentage 100

Target is `sg.*=4` across all ten, plus `r.Nanite.MaxPixelsPerEdge 1.0`
and `r.Shadow.Virtual.ResolutionLodBiasDirectional -1.5`.

### 2c. GameOverride in full, when it IS present

All 20 properties, read back off the setting object. Note these are the
values MRQ defaults the setting to — **adding the setting at all changes
far more than the cinematic flag**:

    cinematic_quality_settings    True (requested)
    disable_hlods                 True
    disable_hlo_ds                True        (deprecated alias, see 2d)
    use_lod_zero                  True
    use_high_quality_shadows      True
    shadow_distance_scale         10
    shadow_radius_threshold       0.001
    texture_streaming             DISABLED
    override_view_distance_scale  True
    view_distance_scale           50
    flush_grass_streaming         True
    flush_streaming_managers      True
    override_grass_cull_distance_scale   True
    grass_cull_distance_scale            50.0
    override_grass_density_scale         False
    grass_density_scale                  1.0
    override_virtual_texture_feedback_factor  True
    virtual_texture_feedback_factor           1
    game_mode_override            None        (deprecated, see 2d)
    soft_game_mode_override       MoviePipelineGameMode

Requested / applied / refused read-back: `{'cinematic_quality_settings':
True}` / `['cinematic_quality_settings']` / `{}`.

### 2d. Deprecations — the engine's own answer for §2.2

AUDIT.md §2.2 lists deprecation checking as pending work. The engine
raised these while the dump read the properties; captured in the dump as
`deprecation_warnings_raised_by_this_dump`:

    MoviePipelineDeferredPassBase.stencil_layers -> renamed to actor_layers
    MoviePipelineGameOverrideSetting.disable_hlo_ds -> renamed to disable_hlods
    MoviePipelineGameOverrideSetting.game_mode_override -> use SoftGameModeOverride

`disable_hlo_ds` still exists and still reads — it is deprecated, not
removed — so a script using it works and warns.

---

## 3. The precedence test

Two dev-profile captures at station `vista`, differing in
`cinematic_quality_settings` and nothing else.
`inputs/precedence_test.json`, `inputs/precedence_frame_diff.json`,
and `inputs/precedence_frames_README.md`.

**Result: the bench's cvars win. The flag changed nothing measurable.**

Two independent log instruments, which share no code path:

| instrument | reading |
|---|---|
| MRQ's apply log — `MoviePipelineConsoleVariableSetting.cpp:253` logs `Applying CVar "X" PreviousValue: p NewValue: n`, and `p` is the value the instant before the bench's cvars land | every `sg.*` PreviousValue **identical** across both runs; `sg.ShadowQuality` read `1 -> 1` in both |
| `Scalability` echoed from inside the render at both hooks (`:271` start, `:279` end) | all 11 groups **identical** across both runs at both hooks |

Had `bCinematicQualitySettings` raised scalability first
(`MoviePipelineGameOverrideSetting.cpp:53-65` calls
`Scalability::SetQualityLevels(max)`), `PreviousValue` for
`sg.ShadowQuality` would have read as the Cinematic level in run A. It
read `1`.

**⚠ A third instrument is INCONCLUSIVE and must not be read as
agreement.** The two frames are not identical — 3.77 % of pixels differ
by more than 1/255, mean abs 0.0014. Attributing that needs a
dev-profile null pair, which the two-capture fence did not allow. The
nearest null on disk (`target_range768{b,c,d}`) is a TARGET-profile
triple at temporal 8, and temporal accumulation averages away exactly
the variation being measured — so it bounds the null, it does not
measure it. The owed experiment is written out in
`precedence_frames_README.md`.

### The flag's prior state, and its restoration

There is no persistent flag to restore. `bench_render.py` calls
`delete_all_jobs()` and rebuilds the config from JSON on every run, so
the setting has no storage between renders. Verified rather than
asserted: a plain `--profile dev --dump-config` after the test reports
**5 setting classes with GameOverride absent**, identical to before.

---

## 4. Live cvar enumeration

`inputs/cvars_5.8_live.txt` (455,624 bytes) — **11,073 entries: 9,817
Var, 884 Cmd, 372 Exec**, from the engine's own `Help` dump
(`Saved/ConsoleHelp.html`, 2,001,181 bytes), parsed by
`tools/parse_console_help.py`. Type is carried per row, because writing a
Cmd or Exec name into a profile as though it were a variable sets nothing
and reports nothing.

Python exposes **no** cvar enumeration — the whole console surface on
`SystemLibrary` is `execute_console_command` plus four
`get_console_variable_*_value` getters, all by name. Hence the engine
dump.

Controls travelled with the read: `r.ScreenPercentage` resolved (`"100"`),
`r.ThisCVarCannotPossiblyExist_zzz` returned empty.

Every Pass 1 "does not exist" verdict is **confirmed live**, by two
instruments (the string getter and the enumeration, independently):

    r.LandscapeLODBias                  ABSENT   (P1-4 confirmed)
    landscape.ForcedLOD                 ABSENT
    r.Shadow.Virtual.Nanite.Enable      ABSENT   (P1-5 confirmed)
    r.TonemapperFilm                    ABSENT
    r.ExpandGamut                       ABSENT
    r.LocalExposure.*ContrastScale      ABSENT
    foliage.WindEnabled / r.Wind.Enable ABSENT
    r.Landscape.MaxLODLevel             ABSENT

Present, with live values:

    r.ForceLOD                                     -1
    r.Shadow.Virtual.ResolutionLodBiasDirectional  -0.5    <-- see P1-6
    r.MaxAnisotropy 4   r.VT.MaxAnisotropy 8   r.VT.AnisotropicFiltering 0
    r.ScreenPercentage 100   r.AntiAliasingMethod 4

P1-6 note: the live engine default reads **−0.5**. The target profile
sets −1.5 through MRQ for the duration of a render only.

---

## 5. The Landscape HLOD layer — ⭐ the settings are correct and reach nothing

`inputs/hlod_landscape_layer.json` (399 KB).

**Freshness is structural, not asserted:** the 09-13 write happened in an
editor process that has since exited; this process was launched after it
and had never touched the asset, so the load is a load from disk by
construction.

### 5a. The 09-13 write survived and reads back correctly

    builder settings class   HLODBuilderMeshMergeSettings
    merge_materials          True
    texture_sizing_type      TEXTURE_SIZING_TYPE_AUTOMATIC_FROM_MESH_DRAW_DISTANCE (6)
    texture_size             1024 x 1024
    lod_selection_type       CALCULATE_LOD (2)
    use_texture_binning      False

Layer itself: `layer_type` MESH_MERGE, `cell_size` 25600,
`loading_range` 200000.0, `is_spatially_loaded` True,
`hlod_builder_class` **None** (so the default builder for the type),
`editor_loading_behavior` DEFAULT.

### 5b. ⭐ But nothing references the layer

    actors naming ANY HLOD layer      0 of 4,339      (0 read errors)
    actors naming THIS layer          0
    world DefaultHLODLayer            /Game/Alpine8K_HLODLayer_Instanced
    chain from the world default      Instanced (INSTANCING)
                                       -> Merged (MESH_APPROXIMATE)
                                       -> (end)
    Alpine8K_HLODLayer_Landscape in that chain?   NO

The 0 is a measurement, not a read failure: the per-actor loop counts
raises, Nones and hits separately and recorded **0 raises, 4,339 Nones**.
The chain was walked to a fixed point from `UWorldPartition::DefaultHLODLayer`
(`WorldPartition.h:612`) because layers cascade through `ParentLayer`
(`HLODLayer.h:135`) and a layer nothing points at directly can still be
in force one hop up. It is not.

**`Alpine8K_HLODLayer_Landscape` is an inert asset.** Its settings are
right and no build will read them.

### 5c. ⛔ Two API facts Pass 2 needs

1. **`dir(unreal.HLODLayer)` lists NO properties.** Enumerated: 23 names,
   all method descriptors (17 `method_descriptor`, 3
   `methodwithclosure_descriptor`, 3 `builtin_function_or_method`), zero
   property descriptors. A `dir()`-driven audit of this class returns
   nothing and concludes the class exposes nothing — which is how "HLOD
   settings expose ZERO properties to Python" was reached twice by two
   probes that were one measurement. Names must come from the header;
   `get_editor_property` then reads them.
2. **On `UHLODLayer` in 5.8, `MeshMergeSettings`, `MeshSimplifySettings`
   and `MeshApproximationSettings` are `_DEPRECATED`** (`HLODLayer.h`
   :172, :174, :176). The live settings are under `HLODBuilderSettings`
   (:119), selected by `HLODBuilderClass` (:116). The 09-13 write used
   the live path — verified at
   `scripts/payloads/apply_landscape_hlod_settings.py:51-75`, which goes
   `hlod_builder_settings -> mesh_merge_settings -> material_settings`.
   Any audit reading the flat names off the layer is reading dead fields.

---

## 6. `lighting.sky.color` — ⭐ P1-8 is WRONG; there IS a writer

P1-8 records *"no write site found in apply_lighting | UNVERIFIED | find
the writer or delete the key"*.

`scripts/apply_lighting.py:394-398`:

    _sky_col = _json.loads({sky_srgb!r})
    if _sky_col:
        _slc.set_light_color(
            _unreal.LinearColor(float(_sky_col[0]), float(_sky_col[1]),
                                float(_sky_col[2]), 1.0))

A property-name search cannot see it: it is a **method**, not a
`set_editor_property` call. The host sRGB-encodes first (`:155`) because
C++ `SetLightColor(FLinearColor, bool bSRGB = true)` exposes only ONE
argument to Python, so the engine always decodes as sRGB — the reflected
Python surface is the contract, not the header.

**Revised verdict: not UNVERIFIED, and the key must NOT be deleted.** It
is READ-BACK-OWED. `apply_lighting` records `_out["sky_color_srgb"]`,
which is the request, not a read of the SkyLight.

**Method-call writers are a blind spot in the scan generally**, not a
one-off: any lever set through a named setter rather than
`set_editor_property` is invisible to the current `lever_inventory`.

---

## 7. `scan_levers_and_api.py` — regenerated

Classification is now by call context, and the eight named non-levers are
dropped. Doing that surfaced two defects the reclassification alone would
have hidden:

1. **`RE_CVAR` could not see console COMMAND strings.** Its character
   class stops at the space in `"r.ForceLOD -1"` and then demands a
   closing quote, so every literal-valued console write scanned as zero
   sites. The first run after the context fix printed `cvar writes 0`
   against a repo with 20+ `execute_console_command` call sites — the 0
   was the tell.
2. **The repo's normal shape is a LIST of names in one place and
   `execute_console_command(world, _cmd)` in a loop elsewhere.** Name and
   call are never on the same line, so a line-scoped classifier reports 0
   writes on a file that writes 30 cvars. Writes are now also paired at
   FILE scope and labelled `INDIRECT`, so the evidence grade travels with
   the row.

Adding the command-string pattern over-caught in the other direction:
`foliage.` and `landscape.` are real cvar prefixes **and** the top-level
keys of `alpine_8k.json`, so 19 recipe paths entered as levers. The
discriminator is case and it is one-directional — UE cvars are CamelCase
after the prefix (`r.ScreenPercentage`, `foliage.WindEnabled`, even
`r.setRes`), every recipe key here is snake_case. Stated as a limit in
`KEEP_CVAR` rather than left to be discovered, with `SEEDED` overriding
it and all 28 rejections listed in `dropped_as_non_levers`.

    levers            412   (97 cvar, 307 editor_property, 8 ini)
    cvar sites        writes 131   reads 2   declared 276
    cvar names        33 of 97 with a direct write; 1 with a read
    editor property   writes 992   reads 1202
    dropped           28 non-levers

Against the committed inventory: **7 cvars gained that the old scan never
saw at all** — `r.HighResScreenshotDelay`,
`r.Streaming.FullyLoadUsedTextures`, `r.VT.MaxContinuousUpdatesPerFrame`,
`r.VT.MaxUploadsPerFrame`, `r.setRes`,
`wp.Runtime.MaxLoadingStreamingCells`,
`wp.Runtime.OverrideRuntimeLoadingRange` — and 7 non-levers removed.

So Pass 1's correction was right about the classification and
**understated the problem: the inventory was not merely mislabelling
cvars, it was missing them.** Combined with §6, the inventory's recall is
the open question, not its precision.

`declared` is its own bucket, not a write: `benchmark.json`'s cvar block
reaches the engine through `MoviePipelineConsoleVariableSetting`, so a
name in a config literal is neither a direct write nor a read at that
site.

---

## 8. Evidence extracts

    inputs/sidecars.zip          1,903,146 bytes (1.90 MB)
    inputs/history_diffs.txt     8,155,440 bytes (8.16 MB)

`sidecars.zip` holds 549 JSON sidecars from `_verify/` (11.64 MB
uncompressed) with `_MANIFEST.json` **inside** the zip listing every file
and every exclusion by extension (5,202 `.png`, 145 `.jsonl`, 110 `.log`,
78 `.exr`, …). A manifest readable without the zip it describes will one
day describe a different zip.

`history_diffs.txt` is 149,175 lines over 544 commits — CLAUDE.md 249,
LESSONS.md 332, RECIPES.md 253, STATE.md 7, and **both** register addenda
(`research/brief/brief2_atmosphere/brief2/` as well as
`research/brief3/`; the glob's reach was verified by grep, not assumed).

---

## Incidental findings, recorded because they are consequential

1. **The level holds 4 DirectionalLight actors.** Read during the rule-11
   level gate. Any claim about "the sun" that resolves an actor by class
   is resolving one of four.
2. **`PackageRestoreData.json` presence is the wrong close-safety
   predicate.** After this session's kill the file was PRESENT, which the
   R-EDITOR-CLOSE gate reads as unsaved work — but its contents are
   `{"RestoreEnabled": true, "Packages": []}`. The signal with two causes
   is the file's existence; the one that carries the meaning is whether
   `Packages` is non-empty. Logged and amended.
