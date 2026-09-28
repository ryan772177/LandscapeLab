"""import_heightmap.py — recipe validation, heightmap validation, and
import preflight for the alpine milestone.

STATUS: THE IMPORT STEP IS NOT IMPLEMENTED. It is fail-closed behind an
explicit refusal (exit 7) pending a design decision from Ryan — see
"UNRESOLVED DESIGN FORK" below. Everything up to that point is complete:
recipe validation, heightmap file validation, the conduct rule 7 identity
gate, the engine version gate, and the in-editor preflight. Those parts
are identical under every option in the fork, which is why they are
written now rather than waited on.

WHAT THIS SCRIPT DOES TODAY
  1. Loads and fully validates a recipe against recipes/schema.md v1.
  2. Validates the heightmap file on disk — existence, format, and actual
     pixel dimensions against the recipe's declared resolution.
  3. Verifies editor identity (conduct rule 7) before any remote command.
  4. Checks the live editor's engine version against recipe.engine.
  5. Preflights the import read-only: parent material exists, and reports
     whether the target landscape actor is already present.
  6. Refuses to import, with exit 7.

Steps 1-2 touch no editor. Steps 3-5 send only read-only expressions, and
step 3 sends nothing until the node has been matched against
UE_PROJECT_ROOT.

UNRESOLVED DESIGN FORK (conduct rule 8 — needs Ryan's sign-off)
UE 5.8 exposes no script-callable API that creates a landscape from a
heightmap file. Verified in engine source:
  - Engine/Source/Runtime/Landscape/Classes/LandscapeProxy.h:1572 —
    LandscapeImportHeightmapFromRenderTarget(UTextureRenderTarget2D*,
    bool, int32) is the ONLY BlueprintCallable heightmap import. It takes
    a render target, not a file, and requires a landscape that already
    exists with valid extents (LandscapeEdit.cpp:8102 errors on invalid
    min extents).
  - Engine/Source/Editor/LandscapeEditor — contains ZERO
    UFUNCTION(BlueprintCallable) declarations.
  - Engine/Source/Runtime/Landscape/Classes/Landscape.h — ALandscape has
    no exposed Import().
So "heightmap file -> new landscape actor" has no Python path in 5.8. The
options, and their costs, are reported to Ryan rather than chosen here.

Exit codes:
  0  all implemented checks passed (nothing was imported)
  1  unexpected error / bad arguments
  2  recipe invalid (schema v1 violation)
  3  heightmap source missing, wrong format, or wrong dimensions
  4  editor identity gate refused (conduct rule 7)
  5  engine version mismatch and recipe says abort
  6  in-editor preflight failed (e.g. parent material missing)
  7  REFUSED: import step not implemented pending design sign-off

Unreal APIs used (all long-stable; nothing 5.8-only):
  unreal.SystemLibrary.get_engine_version
  unreal.EditorAssetLibrary.does_asset_exist
  unreal.GameplayStatics.get_all_actors_of_class / unreal.Landscape
  unreal.UnrealEditorSubsystem.get_editor_world (5.0+; replaces the
  deprecated unreal.EditorLevelLibrary.get_editor_world)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402  — the audited rule 7 gate; reused, not reimplemented
import landscape_spec  # noqa: E402 — shared pivot-normalisation contract (ruling c)

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

PROBE_MARKER = "__LANDSCAPELAB_PREFLIGHT__"

SCHEMA_VERSION = 1
REQUIRED_TOP = ["schema_version", "biome_id", "display_name", "engine",
                "heightmap", "landscape", "material", "lighting", "capture"]
# v1.5. Optional, and validated strictly when present. Not in
# REQUIRED_TOP because every existing recipe predates it, and a world
# without stated traversal intent is still a valid world — it just
# cannot be refused for missing a target it never declared.
OPTIONAL_TOP = ["world", "foliage", "stamps", "palette", "navigation",
                # Added 2026-09-12. Both were already IN the shipped
                # recipe and already READ -- `streaming` by
                # apply_streaming_range, check_derived_culls, check_perf
                # and update_foliage_culls; `perception` by place_foliage
                # and lod_silhouette_capture -- eight call sites across
                # six scripts. They were simply never added here, so this
                # validator refused the world's own recipe while every
                # consumer of those keys worked fine.
                #
                # The gap was invisible because the tools that validate
                # the WHOLE recipe are rarely run: it surfaced only when
                # import_layer_textures was called to reimport a stale
                # weightmap. A whitelist that refuses a legitimate,
                # in-use key is not a stricter guard, it is a BROKEN one
                # -- it blocks the correct case and teaches the next
                # reader to widen it carelessly.
                "streaming", "perception",
                # `water` left Reserved 2026-09-19 (CARVE_PLAN T2), the same
                # graduation `foliage` had in v1.6. It is a POINTER block to
                # recipes/water.json (the city.json precedent:
                # foliage.settlement_exclusion.from_city_plan names a file),
                # validated by _validate_water.
                "water"]
# `foliage` left this list in v1.6, `water` in the Brief-4 carve. `pcg` and
# `weather` stay: a reserved key is REJECTED, never ignored, so a recipe
# cannot quietly declare something no script implements.
RESERVED_TOP = ["pcg", "weather"]
# Movement modes a world can declare as PRIMARY. Mirrors
# terrain_erosion.MOVEMENT_PROFILES; the generator cross-checks the two
# rather than trusting this copy (lesson 1.9 — if two components must
# agree, make them share the code that decides).
MOVEMENT_MODES = ("walk", "mount", "climb", "air")
BIOME_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
LEGAL_SECTION_SIZES = (7, 15, 31, 63, 127, 255)
# The integer Unreal stores, not the dialog label: "2x2 Sections" is 2.
# FLandscapeConfig::NumSectionValues[2] = { 1, 2 } (LandscapeConfigHelper.cpp
# :24). A value of 4 is not buildable.
LEGAL_SPC = (1, 2)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- recipe --

def _is_num(v):
    # isfinite: json.load ACCEPTS the non-standard literals NaN/Infinity,
    # and NaN defeats every pure-comparison check below (nan > x is always
    # False), so e.g. height_m [NaN, NaN] or tiling_m NaN would validate
    # and flow into payload interpolation and shader constants. Same class
    # of defect as the recorded landscape_spec.py finding L2.
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def _num_pair(v):
    return isinstance(v, list) and len(v) == 2 and all(_is_num(x) for x in v)


def _num_triple(v):
    return isinstance(v, list) and len(v) == 3 and all(_is_num(x) for x in v)


def _validate_recipe(recipe, recipe_path):
    """Return a list of schema v1 violations. Empty list means valid."""
    e = []
    if not isinstance(recipe, dict):
        return ["recipe root is not a JSON object"]

    # R-METER hygiene (a), RULED 2026-09-12b: a dot-p-y substring in a
    # block a payload serialises makes the engine treat the WHOLE payload
    # as a pathname (PythonScriptPlugin.cpp:813-830). FOUR recurrences,
    # warned twice inside `lighting` itself, enforced nowhere -- so it is
    # enforced here, AT LOAD, where every tool passes through.
    try:
        import check_recipe_payload_safe as _pls
        for _blk in _pls.INTERPOLATED_BLOCKS:
            if _blk not in recipe:
                continue
            for _m in sorted(set(_pls.PAT.findall(json.dumps(recipe[_blk])))):
                e.append(
                    "dot-p-y substring {0!r} in the {1!r} block, which is "
                    "serialised into a remote-exec payload: the engine "
                    "treats the first such substring as a PATHNAME and runs "
                    "the whole payload as a file. Name the tool without the "
                    # `_m` is the FULL match -- the checker's pattern has no
                    # capture group, so it already carries the extension.
                    # Appending one produced 'x.py.py' in the first draft.
                    "extension.".format(_m, _blk))
        # Interpolated FIELDS too (Pass 3 2026-09-16): _preflight_source
        # embeds material.parent_material and landscape.actor_name
        # directly into a remote-exec payload, and neither is covered by
        # INTERPOLATED_BLOCKS (which is calibrated to whole-block
        # serialisation — do NOT widen it; scan the two fields instead).
        # An actor_name like 'Alpine.py' validated clean and would make
        # the probe fail as a misdiagnosed exit 6.
        # Type-gate before .get: `or {}` saves only FALSY values, so a
        # truthy non-dict material/landscape (a string, a list) would
        # AttributeError here — the raise-on-invalid class this very
        # file warns about. _validate_material/_validate_landscape
        # report the type violation; this scan just skips it.
        _mat = recipe.get("material")
        _lnd = recipe.get("landscape")
        for _fld, _val in (
                ("material.parent_material",
                 _mat.get("parent_material")
                 if isinstance(_mat, dict) else None),
                ("landscape.actor_name",
                 _lnd.get("actor_name")
                 if isinstance(_lnd, dict) else None)):
            if isinstance(_val, str):
                for _m in sorted(set(_pls.PAT.findall(_val))):
                    e.append(
                        "dot-p-y substring {0!r} in {1}, which is "
                        "interpolated into the preflight payload: the "
                        "engine treats the first such substring as a "
                        "PATHNAME and runs the whole payload as a file. "
                        "Rename without the extension.".format(_m, _fld))
    except ImportError:
        # DEGRADE, NAMING THE GAP (NN6) -- never silently skip a guard.
        e.append("the payload-safety guard could not be imported; recipe "
                 "prose is UNCHECKED for dot-p-y substrings")

    if recipe.get("schema_version") != SCHEMA_VERSION:
        e.append("schema_version must be {0}, got {1!r}".format(
            SCHEMA_VERSION, recipe.get("schema_version")))

    for key in REQUIRED_TOP:
        if key not in recipe:
            e.append("missing required top-level key: {0}".format(key))
    for key in RESERVED_TOP:
        if key in recipe:
            e.append("reserved key '{0}' is not implemented under "
                     "schema_version 1 and must be rejected, not "
                     "ignored".format(key))
    for key in recipe:
        if (key not in REQUIRED_TOP and key not in RESERVED_TOP
                and key not in OPTIONAL_TOP):
            e.append("unknown top-level key: {0}".format(key))
    e.extend(_validate_world(recipe.get("world")))
    e.extend(_validate_navigation(recipe.get("navigation")))
    e.extend(_validate_water(recipe.get("water")))
    e.extend(_validate_foliage(recipe.get("foliage"), recipe))
    e.extend(_validate_stamps(recipe.get("stamps"), recipe))
    e.extend(_validate_palette(recipe.get("palette")))

    biome_id = recipe.get("biome_id")
    if not isinstance(biome_id, str) or not BIOME_ID_RE.match(biome_id or ""):
        e.append("biome_id must match ^[a-z][a-z0-9_]*$, got {0!r}".format(
            biome_id))
    else:
        stem = os.path.splitext(os.path.basename(recipe_path))[0]
        if stem != biome_id:
            e.append("biome_id {0!r} does not match filename stem "
                     "{1!r}".format(biome_id, stem))

    if not isinstance(recipe.get("display_name"), str):
        e.append("display_name must be a string")

    eng = recipe.get("engine")
    if not isinstance(eng, dict):
        e.append("engine must be an object")
    else:
        if not isinstance(eng.get("target_version"), str):
            e.append("engine.target_version must be a string, e.g. '5.8'")
        mism = eng.get("on_version_mismatch", "abort")
        if mism not in ("abort", "warn"):
            e.append("engine.on_version_mismatch must be 'abort' or 'warn'")

    e.extend(_validate_heightmap(recipe.get("heightmap")))
    e.extend(_validate_landscape(recipe.get("landscape")))
    e.extend(_validate_material(recipe.get("material")))
    e.extend(_validate_lighting(recipe.get("lighting")))
    e.extend(_validate_capture(recipe.get("capture")))
    return e


SPECIES_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


_ROCK_SCATTER_KEYS = {"repose_deg", "cliff_source_slope_deg",
                      "source_smooth_m", "runout_m", "mfd_exponent",
                      "max_steps", "saturation"}


def _validate_rock_scatter(rs):
    """Schema v1.17 `foliage.rock_scatter` — optional, strict when present.

    **A SHARED PHYSICAL FACT** (CLAUDE.md non-negotiable 19). Read by BOTH
    the Pass 2 landscape material's scree sub-surface mask and Pass 3's
    talus mesh scatter. If the two used different numbers, the scree
    TEXTURE and the scree ROCKS would land in different places — a defect
    neither pass's own verification could detect, because each would be
    internally consistent.

    These are properties of rock, not style knobs: an angle of repose, the
    slope above which a face sheds, a runout length. That is precisely why
    they are pass-independent.
    """
    e = []
    if rs is None:
        return e
    if not isinstance(rs, dict):
        return ["foliage.rock_scatter must be an object"]

    for key in rs:
        if key.startswith("_"):
            continue
        if key not in _ROCK_SCATTER_KEYS:
            e.append("unknown key in foliage.rock_scatter: {0}".format(key))
    for key in sorted(_ROCK_SCATTER_KEYS):
        if key not in rs:
            e.append("foliage.rock_scatter.{0} is required".format(key))
    if e:
        return e

    rep = rs["repose_deg"]
    if not _is_num(rep) or not 25.0 <= rep <= 45.0:
        e.append("foliage.rock_scatter.repose_deg must be in [25, 45]; "
                 "angular rock debris rests at 34-37 deg and a value "
                 "outside this band is not an angle of repose")
    src = rs["cliff_source_slope_deg"]
    if not _is_num(src) or not 30.0 <= src <= 90.0:
        e.append("foliage.rock_scatter.cliff_source_slope_deg must be in "
                 "[30, 90]")
    elif _is_num(rep) and src <= rep:
        e.append("foliage.rock_scatter.cliff_source_slope_deg ({0}) must "
                 "EXCEED repose_deg ({1}): a face that can hold talus is "
                 "not shedding it, and equal values make every source "
                 "cell its own deposit".format(src, rep))

    sm = rs["source_smooth_m"]
    if not _is_num(sm) or not 0.0 < sm <= 200.0:
        e.append("foliage.rock_scatter.source_smooth_m must be in "
                 "(0, 200]: the landform smoothing applied BEFORE the "
                 "cliff-source slope test. It must exceed the "
                 "stamps.detail_relief wavelength or cell-scale texture "
                 "manufactures phantom cliffs; measured 2026-08-03, ~40% "
                 "of the cell-scale >=50 deg area is texture")

    ro = rs["runout_m"]
    if not _is_num(ro) or not 0.0 < ro <= 2000.0:
        e.append("foliage.rock_scatter.runout_m must be in (0, 2000]")
    mfd = rs["mfd_exponent"]
    if not _is_num(mfd) or not 0.5 <= mfd <= 4.0:
        e.append("foliage.rock_scatter.mfd_exponent must be in [0.5, 4.0]")
    ms = rs["max_steps"]
    if not isinstance(ms, int) or isinstance(ms, bool) or not 1 <= ms <= 5000:
        e.append("foliage.rock_scatter.max_steps must be an integer in "
                 "[1, 5000]. Measured 2026-08-03: routing converges at 274 "
                 "steps (50 deg) and 322 (45 deg), and HITTING the cap is "
                 "a refusal, not a note")
    sat = rs["saturation"]
    if not _is_num(sat) or not 0.0 < sat <= 100.0:
        e.append("foliage.rock_scatter.saturation must be in (0, 100]: the "
                 "deposit value at which placement probability saturates")
    return e


# Imported, never retyped: the bound belongs to the cost model that
# enforces it (non-negotiable 24). If rock_scatter is unavailable the
# validator must not silently pick a looser bound, so this fails loudly.
from rock_scatter import (                                 # noqa: E402
    MAX_LOD_DEPTH as _MAX_LOD_DEPTH,
    ROLES as _ROCK_ROLES,
    MASK_KINDS as _ROCK_MASK_KINDS,
)

# The two names above were LOCAL LITERALS until 2026-08-08, sitting two
# and three lines below the import that already demonstrated the correct
# pattern. Swept under non-negotiable 4a: the same duplication had
# reached three constants across two tools (roles, mask kinds, and
# place_foliage's MAX_INSTANCES), which is past the promote-on-the-spot
# trigger. The planner is the right owner because it is the consumer
# that must actually HANDLE each value; a validator can approve a role
# it has no code for, and did.


def _validate_rock_species(sp, tag, layer_names):
    """Schema v1.20 — a `foliage.species[]` entry that declares `role`.

    Planned by `rock_scatter.py`, placed by the SAME run as vegetation
    (the orphan sweep removes any FT_* not in the run's plan list, so a
    separate rock run would silently delete every conifer).
    """
    e = []
    if sp.get("role") not in _ROCK_ROLES:
        e.append("{0}.role must be one of {1}".format(tag,
                                                      list(_ROCK_ROLES)))
    m = sp.get("mask")
    if not isinstance(m, dict):
        e.append("{0}.mask must be an object".format(tag))
    else:
        kind = m.get("kind")
        if kind not in _ROCK_MASK_KINDS:
            e.append("{0}.mask.kind must be one of {1}".format(
                tag, list(_ROCK_MASK_KINDS)))
        _sd = m.get("slope_deg")
        if not _num_pair(_sd):
            e.append("{0}.mask.slope_deg must be a [lo, hi] pair".format(tag))
        # Bounds + ordering, mirroring the vegetation slope check (Pass 3
        # 2026-09-16): an inverted or out-of-range pair validated clean
        # and yielded an ALL-ZERO mask — a species that places nothing,
        # silently, indistinguishable from low density.
        elif not (0.0 <= _sd[0] <= 90.0 and 0.0 <= _sd[1] <= 90.0):
            e.append("{0}.mask.slope_deg must lie in [0, 90], got {1!r}"
                     .format(tag, _sd))
        elif _sd[0] > _sd[1]:
            e.append("{0}.mask.slope_deg is inverted: {1} > {2} — the "
                     "mask would be all-zero and the species would place "
                     "NOTHING, silently".format(tag, _sd[0], _sd[1]))
        if kind == "layer" and m.get("layer") not in layer_names:
            e.append("{0}.mask.layer must name a material layer, got "
                     "{1!r}".format(tag, m.get("layer")))
        if kind == "talus" and not _is_num(m.get("saturation")):
            e.append("{0}.mask.saturation is required for a talus mask"
                     .format(tag))

    # height_m, mirroring the vegetation check (Pass 3 2026-09-16): the
    # key is in _ROCK and rock_scatter indexes it directly — an absent
    # key was a KeyError crash, a NaN/inverted pair an all-False band
    # placing nothing silently.
    _hm = sp.get("height_m")
    if not _num_pair(_hm):
        e.append("{0}.height_m must be [min, max] finite numbers"
                 .format(tag))
    elif not (0.0 <= _hm[0] <= 100000.0 and 0.0 <= _hm[1] <= 100000.0):
        e.append("{0}.height_m must lie in [0, 100000], got {1!r}"
                 .format(tag, _hm))
    elif _hm[0] > _hm[1]:
        e.append("{0}.height_m is inverted: {1} > {2}"
                 .format(tag, _hm[0], _hm[1]))

    d = sp.get("density_per_hectare_on_mask")
    if not _is_num(d) or not 0.0 < d <= 500.0:
        e.append("{0}.density_per_hectare_on_mask must be in (0, 500]. This "
                 "is ON-MASK density and does NOT draw from "
                 "foliage.density_per_hectare — that number is the TREE "
                 "budget, and coupling them would move every rock whenever "
                 "the forest is retuned".format(tag))

    emb = sp.get("embed_frac", 0.0)
    if not _is_num(emb) or not 0.0 <= emb <= 0.5:
        e.append("{0}.embed_frac must be in [0, 0.5]: the fraction of the "
                 "mesh height sunk into the terrain. 0 leaves rocks sitting "
                 "ON the surface like decals; above 0.5 buries more than "
                 "half the rock".format(tag))

    tum = sp.get("tumble_deg", 0.0)
    if not _is_num(tum) or not 0.0 <= tum <= 90.0:
        e.append("{0}.tumble_deg must be in [0, 90]".format(tag))

    # Placement priors. Bounded at |1.0| because the shared multiplier is
    # `clip(1 + bias*(v - ref)*2, 0, 2)` and `v - ref` reaches about
    # +/-1 for a normalised prior: past 1.0 the clip does the work and
    # the knob stops meaning anything, which is a knob that lies.
    for _k in ("flow_bias", "canopy_bias"):
        _b = sp.get(_k, 0.0)
        if not _is_num(_b) or not -1.0 <= _b <= 1.0:
            e.append("{0}.{1} must be in [-1, 1]; beyond that the shared "
                     "multiplier saturates its own clip and the value "
                     "stops changing the result".format(tag, _k))

    al = sp.get("align_to_normal")
    if not _is_num(al) or not 0.0 <= al <= 1.0:
        e.append("{0}.align_to_normal must be in [0, 1]. Rocks EMBED and "
                 "follow the surface, which inverts R4's world-up rule for "
                 "trees — but 1.0 on a steep face lies a boulder flat "
                 "against it".format(tag))

    sr = sp.get("scale_range")
    if not _num_pair(sr):
        e.append("{0}.scale_range must be a [min, max] pair".format(tag))
    elif not 0.0 < float(sr[0]) <= float(sr[1]):
        e.append("{0}.scale_range must satisfy 0 < min <= max".format(tag))

    cd = sp.get("cull_distance_m")
    if not _is_num(cd) or not 0.0 < cd <= 5000.0:
        e.append("{0}.cull_distance_m must be in (0, 5000]".format(tag))

    ld = sp.get("lod_depth", 1)
    if not isinstance(ld, int) or isinstance(ld, bool) or not 1 <= ld <= _MAX_LOD_DEPTH:
        e.append("{0}.lod_depth must be an integer in [1, {1}]; it is the "
                 "MEASURED LOD COUNT of the mesh (lod_depth 4 means LOD0..3), "
                 "not a wish. The upper bound is len(rock_scatter."
                 "LOD_PERCENT) — the cost model literally cannot express a "
                 "longer chain, and admitting one would index off the end of "
                 "the table".format(tag, _MAX_LOD_DEPTH))
    else:
        e.extend(_lod_depth_matches_measurement(sp, tag, ld))
    return e


_NAV_KEYS = {"tile_size_uu", "average_layers_per_tile",
             "max_simultaneous_tile_generation_jobs", "min_region_dimension_uu",
             "data_gathering_mode", "builder_loading_cell_size_cm",
             "chunk_grid_size_cm", "bounds_volumes"}
_NAV_VOLUME_KEYS = {"name", "min_cm", "max_cm", "basis"}
_NAV_GATHERING = {"instant", "lazy"}
# ARecastNavMesh::TileNumberHardLimit = 1 << 20 (RecastNavMesh.cpp:551).
# Exceeding it logs an error and CLAMPS -- the navmesh is silently smaller
# than the world, which is why this is a refusal and not a warning.
_TILE_NUMBER_HARD_LIMIT = 1 << 20
# UPROPERTY meta ClampMin on TileSizeUU (RecastNavMesh.h:690).
_TILE_SIZE_MIN_UU = 300.0
# GetClampedTileSizeUU caps at CellSize * ArbitraryMaxTileSizeVoxels
# (RecastNavMesh.cpp:68,78). At the shipped CellSize=19 (BaseEngine.ini:3053)
# that is 19456. A larger value is CLAMPED, not honoured.
_TILE_SIZE_MAX_UU = 19.0 * 1024.0


def _validate_navigation(nav):
    """v1.24. Navmesh BUILD parameters. Agent parameters live in
    `recipes/character.json` and are NOT restated here.

    THE TILE BUDGET IS THE POINT OF THIS GATE. `bWholeWorldNavigable` is
    unreachable — its UPROPERTY is commented out at NavigationSystem.h:370
    with the engine's own "currently broken" — so the navmesh grid spans the
    union of the declared `bounds_volumes` and nothing else. That makes the
    tile count computable from the recipe alone, with no world extent and no
    editor:

        tiles_per_side = ceil(union_extent / tile_size_uu) + 1
        total          = tiles_per_side^2 * average_layers_per_tile

    against `TileNumberHardLimit` = 1 << 20. Going over does not fail the
    build: `RecastNavMesh.cpp` logs an error and CLAMPS, leaving a navmesh
    quietly smaller than the world it claims to cover. A silent clamp is
    exactly the class this project refuses rather than warns about.
    """
    e = []
    if nav is None:
        return e
    if not isinstance(nav, dict):
        return ["navigation must be an object"]
    for key in nav:
        if key not in _NAV_KEYS:
            e.append("unknown key in navigation: {0}".format(key))

    ts = nav.get("tile_size_uu")
    if not _is_num(ts) or not _TILE_SIZE_MIN_UU <= float(ts) <= _TILE_SIZE_MAX_UU:
        e.append(
            "navigation.tile_size_uu must be a finite number in [{0}, {1}] "
            "uu. Below the minimum the engine's own ClampMin refuses it; "
            "above it GetClampedTileSizeUU silently CLAMPS to "
            "CellSize * 1024 and the value you declared is not the value "
            "that builds".format(_TILE_SIZE_MIN_UU, _TILE_SIZE_MAX_UU))

    layers = nav.get("average_layers_per_tile")
    if not _is_num(layers) or float(layers) < 1.0:
        e.append("navigation.average_layers_per_tile must be a finite "
                 "number >= 1.0 (engine ClampMin, RecastNavMesh.h:696)")

    jobs = nav.get("max_simultaneous_tile_generation_jobs")
    if not isinstance(jobs, int) or isinstance(jobs, bool) or jobs < 1:
        e.append(
            "navigation.max_simultaneous_tile_generation_jobs must be an "
            "integer >= 1. The engine default is 1024 "
            "(RecastNavMesh.cpp:549); 1024 concurrent voxel heightfields is "
            "the same shape as the Nanite batch that reached 196.8 GB here")

    mra = nav.get("min_region_dimension_uu")
    if not _is_num(mra) or float(mra) < 0.0:
        e.append(
            "navigation.min_region_dimension_uu must be a finite number >= 0 "
            "(engine ClampMin, RecastNavMesh.h:742). It is a LINEAR "
            "dimension in uu, NOT an area: RecastNavMeshGenerator.cpp:5267 "
            "computes rcSqr(MinRegionArea / CellSize) -- divide by cell "
            "size, and only THEN square. 400 discards islands smaller than "
            "400x400 uu = 16 m2, not 400 cm2. The engine's own property is "
            "misleadingly NAMED MinRegionArea while its tooltip says "
            "'minimum dimension'")

    mode = nav.get("data_gathering_mode")
    if mode not in _NAV_GATHERING:
        e.append("navigation.data_gathering_mode must be one of {0}, got "
                 "{1!r}".format(sorted(_NAV_GATHERING), mode))

    grid = nav.get("chunk_grid_size_cm")
    if not isinstance(grid, int) or isinstance(grid, bool) or grid <= 0:
        e.append("navigation.chunk_grid_size_cm must be a positive integer "
                 "(AWorldSettings.NavigationDataChunkGridSize, default "
                 "102400)")

    cell = nav.get("builder_loading_cell_size_cm")
    if not isinstance(cell, int) or isinstance(cell, bool) or cell < 5000:
        e.append("navigation.builder_loading_cell_size_cm must be an integer "
                 ">= 5000 (engine ClampMin on "
                 "AWorldSettings.NavigationDataBuilderLoadingCellSize)")
    elif isinstance(grid, int) and grid > 0 and cell % grid != 0:
        # WorldPartitionNavigationDataBuilder.cpp:62
        #   IterativeCellSize = GridSize * max(Setting / GridSize, 1)
        # Integer division: a non-multiple is silently ROUNDED DOWN, so the
        # declared number is not the number that runs.
        e.append(
            "navigation.builder_loading_cell_size_cm {0} is not a multiple "
            "of chunk_grid_size_cm {1}. WorldPartitionNavigationDataBuilder"
            ".cpp:62 computes GridSize * (Setting // GridSize), so the "
            "declared value would be silently rounded down to {2}".format(
                cell, grid, grid * max(cell // grid, 1)))

    vols = nav.get("bounds_volumes")
    if not isinstance(vols, list) or not vols:
        e.append(
            "navigation.bounds_volumes must be a non-empty list. "
            "ANavMeshBoundsVolume actors are MANDATORY: the whole-world "
            "alternative, UNavigationSystemV1::bWholeWorldNavigable, has its "
            "UPROPERTY commented out at NavigationSystem.h:370 with the "
            "engine's own note that it is 'currently broken'. With no "
            "volume, nothing is navigable and the build succeeds having "
            "produced nothing")
        return e

    lo = [None, None, None]
    hi = [None, None, None]
    seen = set()
    for i, v in enumerate(vols):
        vt = "navigation.bounds_volumes[{0}]".format(i)
        if not isinstance(v, dict):
            e.append("{0} must be an object".format(vt))
            continue
        for key in v:
            if key not in _NAV_VOLUME_KEYS:
                e.append("unknown key in {0}: {1}".format(vt, key))
        nm = v.get("name")
        if not isinstance(nm, str) or not nm.strip():
            e.append("{0}.name must be a non-empty string".format(vt))
        elif nm in seen:
            e.append("{0}.name {1!r} is declared twice; actor labels collide "
                     "and this project has two landscapes whose proxies "
                     "carried identical labels".format(vt, nm))
        else:
            seen.add(nm)
        if not isinstance(v.get("basis"), str) or not v["basis"].strip():
            e.append("{0}.basis must be a non-empty string recording WHERE "
                     "these bounds came from. A navigable region is a design "
                     "decision, not a default".format(vt))
        mn, mx = v.get("min_cm"), v.get("max_cm")
        ok = True
        for nmk, arr in (("min_cm", mn), ("max_cm", mx)):
            if (not isinstance(arr, list) or len(arr) != 3
                    or not all(_is_num(c) for c in arr)):
                e.append("{0}.{1} must be a 3-element [x, y, z] of finite "
                         "numbers, centimetres".format(vt, nmk))
                ok = False
        if not ok:
            continue
        for ax in range(3):
            if float(mx[ax]) <= float(mn[ax]):
                e.append("{0}: max_cm[{1}] must exceed min_cm[{1}]; a volume "
                         "with no thickness on an axis encloses nothing"
                         .format(vt, ax))
                ok = False
        if not ok:
            continue
        for ax in range(3):
            lo[ax] = float(mn[ax]) if lo[ax] is None else min(lo[ax], float(mn[ax]))
            hi[ax] = float(mx[ax]) if hi[ax] is None else max(hi[ax], float(mx[ax]))

    if _is_num(ts) and _is_num(layers) and lo[0] is not None:
        import math as _math
        side = max(hi[0] - lo[0], hi[1] - lo[1])
        per_side = int(_math.ceil(side / float(ts))) + 1
        total = int(_math.ceil(per_side * per_side * float(layers)))
        if total > _TILE_NUMBER_HARD_LIMIT:
            e.append(
                "navigation: the declared bounds span {0:.0f} uu, which at "
                "tile_size_uu {1} and average_layers_per_tile {2} needs "
                "{3} tiles against ARecastNavMesh::TileNumberHardLimit "
                "{4} (RecastNavMesh.cpp:551). The engine does not fail on "
                "this — it logs an error and CLAMPS, leaving a navmesh "
                "quietly smaller than the region it claims to cover."
                .format(side, ts, layers, total, _TILE_NUMBER_HARD_LIMIT))
    return e


_COLLISION_ENABLED = {"none", "query_only"}
_NAV_GEOMETRY = {"yes", "no", "dont_export", "even_if_not_collidable"}
_COLLISION_KEYS = {"enabled", "profile", "navigable_geometry", "capsule"}
_CAPSULE_KEYS = {"radius_cm", "z_min_cm", "z_max_cm", "basis"}


# GRASS DISC GUARD ceiling: instances one grass species may put in its own
# cull disc (pi*cull_m^2*density_per_10m2/10). 150,000 = ~1.6x the ruled
# Meadow disc (94,248 at 50 m / 120 per 10 m2, R11), so every shipped species
# passes with room and a 512 m far tier is bounded to ~1.8 per 10 m2. Added
# 2026-09-27 (Brief 7 P3b) with the cull ceiling's move from 250 to 512 m.
GRASS_DISC_MAX_INSTANCES = 150000.0
# The cull ceiling, ONE definition: make_landscape_material._grass_cull_cm reads
# both constants from here (non-negotiable 24 -- the validator and the builder
# must not be able to disagree about what a legal grass cull is; on 2026-09-27
# they did, for exactly one run, when the validator moved to 512 and the
# builder's own copy still said 250).
GRASS_CULL_MAX_M = 512.0


def _validate_collision(sp, tag, system):
    """v1.23. `collision` is REQUIRED on every INSTANCED species.

    WHY REQUIRED RATHER THAN OPTIONAL-WITH-A-DEFAULT. Measured 2026-08-16:
    all 14 `FT_*` assets in this project read `NoCollision`, including the
    three tree species whose MESHES carry a vendor-authored trunk capsule.
    Nothing in the world collided except the landscape. The cause was not a
    wrong value — it was that `place_foliage.py` never mentioned collision
    in any form, so `UFoliageType`'s constructor default stood
    (`InstancedFoliage.cpp:640` sets `BodyInstance.SetCollisionProfileName(
    NoCollision)`), and `InstancedFoliage.cpp:1822` copies that onto the
    component UNCONDITIONALLY, overriding the mesh's own BodySetup.

    An optional field with a sensible default would have reproduced exactly
    that failure: silent, invisible, and green on every check. A REQUIRED
    field cannot be forgotten -- non-negotiable 3, prefer an input that
    cannot express the catastrophic value over a gate that rejects it.

    REFUSED on grass, because it could not mean anything there:
    `LandscapeGrass.cpp:3170-3172` hard-codes `NoCollision` and
    `bDisableCollision = true` on every grass component. A collision block
    on a grass species is an inert field that reads like a setting, which
    is the same defect the schema already refuses for `anchor_m` on an ADD
    placement (non-negotiable 21).
    """
    e = []
    has = "collision" in sp
    if system == "grass":
        if has:
            e.append(
                "{0}.collision is refused on a grass species. The engine "
                "hard-codes NoCollision and bDisableCollision on every "
                "LandscapeGrassType component (LandscapeGrass.cpp:"
                "3170-3172), so the block could never take effect — and an "
                "inert field reads like a setting".format(tag))
        return e
    if not has:
        e.append(
            "{0}.collision is REQUIRED on an instanced species. It is not "
            "optional and has no default: UFoliageType's constructor "
            "defaults BodyInstance to NoCollision "
            "(InstancedFoliage.cpp:640) and that value is copied onto the "
            "component unconditionally (:1822), overriding whatever the "
            "MESH's own BodySetup says. Declare "
            "{{\"enabled\": \"none\"|\"query_only\", ...}} explicitly — on "
            "2026-08-16 this silence left 219,659 trees and 13,515 rocks "
            "passing straight through the player".format(tag))
        return e

    c = sp["collision"]
    if not isinstance(c, dict):
        e.append("{0}.collision must be an object".format(tag))
        return e
    for key in c:
        if key not in _COLLISION_KEYS:
            e.append("unknown key in {0}.collision: {1}".format(tag, key))

    en = c.get("enabled")
    if en not in _COLLISION_ENABLED:
        e.append(
            "{0}.collision.enabled must be one of {1}, got {2!r}. "
            "'physics_only' and the probe modes are deliberately NOT "
            "admitted: static foliage is never simulated, and admitting "
            "them would let a species be configured so that traces miss it "
            "while every property read looks set".format(
                tag, sorted(_COLLISION_ENABLED), en))

    nav = c.get("navigable_geometry")
    if nav not in _NAV_GEOMETRY:
        e.append(
            "{0}.collision.navigable_geometry must be one of {1}, got "
            "{2!r}. It is declared rather than inherited because a config "
            "file records an OVERRIDE, never the state in effect "
            "(non-negotiable 17). Note the engine default is 'yes' "
            "(InstancedFoliage.cpp:868) and that 'no' does NOT mean "
            "'keep it out of the navmesh' — 'no' means the DEFAULT "
            "collision export still runs; 'dont_export' is the one that "
            "excludes".format(tag, sorted(_NAV_GEOMETRY), nav))

    prof = c.get("profile")
    if en == "none":
        if prof is not None:
            e.append(
                "{0}.collision.profile is refused when enabled is 'none'. "
                "Nothing reads it, so it is an inert field that reads like "
                "a setting (non-negotiable 21)".format(tag))
    else:
        if not isinstance(prof, str) or not prof.strip():
            e.append(
                "{0}.collision.profile must be a non-empty collision "
                "profile name when enabled is not 'none'".format(tag))

    if "capsule" in c:
        e.extend(_validate_collision_capsule(c, tag, en))
    return e


def _validate_collision_capsule(c, tag, en):
    """A capsule this project AUTHORS onto a mesh it owns.

    Parameterised as radius + the vertical SPAN it occupies, never as the
    engine's `length`. `KSphylElem.length` is documented as the LINE
    SEGMENT — "add Radius to both ends to find total length"
    (SphylElem.h, quoted in the 5.8 stub at :183555) — so a recipe that
    declared `length` directly would read as a total height and be short
    by one diameter, silently. The tool derives length once, here, from a
    span that cannot be misread.
    """
    e = []
    cap = c["capsule"]
    ct = tag + ".collision.capsule"
    if not isinstance(cap, dict):
        e.append("{0} must be an object".format(ct))
        return e
    if en == "none":
        e.append(
            "{0} is refused when collision.enabled is 'none'. Authoring "
            "geometry nothing can query is work that reports success and "
            "changes nothing".format(ct))
    for key in cap:
        if key not in _CAPSULE_KEYS:
            e.append("unknown key in {0}: {1}".format(ct, key))

    r = cap.get("radius_cm")
    if not _is_num(r) or not 0.0 < float(r) <= 500.0:
        e.append("{0}.radius_cm must be a finite number in (0, 500] "
                 "centimetres, got {1!r}".format(ct, r))
    z0 = cap.get("z_min_cm")
    z1 = cap.get("z_max_cm")
    for nm, v in (("z_min_cm", z0), ("z_max_cm", z1)):
        if not _is_num(v):
            e.append("{0}.{1} must be a finite number in the MESH's local "
                     "space, centimetres".format(ct, nm))
    if _is_num(r) and _is_num(z0) and _is_num(z1):
        span = float(z1) - float(z0)
        if span <= 0.0:
            e.append("{0}.z_max_cm must be greater than z_min_cm, got a "
                     "span of {1}".format(ct, span))
        elif span <= 2.0 * float(r):
            e.append(
                "{0} span {1} cm does not exceed its own diameter {2} cm. "
                "The derived KSphylElem.length would be <= 0 and the shape "
                "is a sphere, not a capsule — declare a sphere or widen "
                "the span".format(ct, round(span, 3), round(2.0 * float(r), 3)))

    if not isinstance(cap.get("basis"), str) or not cap["basis"].strip():
        e.append(
            "{0}.basis must be a non-empty string recording WHERE the "
            "numbers came from. A collision radius is a measurement, not a "
            "taste knob, and a measurement with no provenance cannot be "
            "re-derived when the mesh changes".format(ct))
    return e


def _lod_depth_matches_measurement(sp, tag, declared):
    """The recipe DECLARES the chain; the measurement DECIDES it.

    `rock_scatter.py` costs the mesh from the measured `lod_count`, never
    from this field. Keeping the field is worth it for readability, but a
    declared value that no longer matches the asset is exactly the
    "derived record vs ground truth" defect (non-negotiable 15), so it is
    checked against the artefact HERE, at the moment it is read.
    """
    try:
        reg = _measured_rock_registry()
    except (OSError, ValueError) as exc:
        return ["{0}.lod_depth: cannot check against the measurement: {1}"
                .format(tag, exc)]
    if reg is None:
        return []          # the mesh gate already reports the missing file
    row = reg.get(landscape_spec.mesh_path_key(sp.get("mesh") or ""))
    if not isinstance(row, dict):
        return []          # likewise already reported
    measured = row.get("lod_count")
    if measured is None:
        return ["{0}.lod_depth: the measurement for this mesh returned null "
                "for lod_count — a FAILED measurement, which must not be "
                "read as agreement. Re-measure it.".format(tag)]
    # A non-numeric registry value REFUSES, it does not crash (Pass 3
    # 2026-09-16, same class as landscape_spec._num): bare int() on a
    # corrupted row raised ValueError past the (OSError, ValueError) net
    # above, which wraps only the registry LOAD.
    if not isinstance(measured, int) or isinstance(measured, bool):
        return ["{0}.lod_depth: lod_count in the measured row is not an "
                "integer ({1!r}) — the row is unusable; refuse, do not "
                "coerce. Re-measure the asset.".format(tag, measured)]
    if int(measured) != int(declared):
        return ["{0}.lod_depth declares {1} but the mesh MEASURES {2}. The "
                "triangle budget is computed from the measured value, so "
                "this recipe would document a chain the cost model is not "
                "using. Set it to {2} or re-measure the asset."
                .format(tag, declared, int(measured))]
    return []


def _measured_rock_registry():
    """{canonical mesh path: row} from the measured-pivot report, or None."""
    path = os.path.join(landscape_spec.REPO_ROOT, "Free", "_measured",
                        "rock_pivots.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise ValueError("rock_pivots.json is not an object")
    return {landscape_spec.mesh_path_key(k): v for k, v in doc.items()}


def _validate_water_recipe(wr, path):
    """The water-1.0 recipe body (recipes/water.json). Enforces the invariants
    the Brief-4 carve depends on — chiefly that an endorheic lake carries a
    MACHINE-READABLE never-exceed ceiling (rule 12: the town-safety value must
    be present and checkable, not prose) and that the waterfall cap is sane."""
    e = []
    if not isinstance(wr, dict):
        return ["water recipe {0} root is not a JSON object".format(path)]
    if wr.get("schema_version") != "water-1.0":
        e.append("water recipe {0} schema_version must be 'water-1.0', got "
                 "{1!r}".format(path, wr.get("schema_version")))
    lakes = wr.get("lakes")
    if not isinstance(lakes, list) or not lakes:
        return e + ["water recipe {0} lakes must be a non-empty array".format(path)]
    seen = set()
    for i, lk in enumerate(lakes):
        if not isinstance(lk, dict):
            e.append("water lake[{0}] is not an object".format(i)); continue
        lid = lk.get("id")
        if not isinstance(lid, int) or isinstance(lid, bool):
            e.append("water lake[{0}].id must be an integer".format(i))
        elif lid in seen:
            e.append("water lake id {0} is duplicated".format(lid))
        else:
            seen.add(lid)
        if not _is_num(lk.get("level_m")):
            e.append("water lake[{0}].level_m must be a finite number".format(i))
        if not isinstance(lk.get("name"), str) or not lk.get("name"):
            e.append("water lake[{0}].name must be a non-empty string".format(i))
        if lk.get("endorheic") is True:
            nx = lk.get("never_exceed_level_m")
            if not _is_num(nx):
                e.append("endorheic water lake {0} must declare a "
                         "machine-readable never_exceed_level_m (rule 12; the "
                         "town-safety ceiling is not prose)".format(lk.get("id")))
            elif _is_num(lk.get("level_m")) and nx < lk["level_m"]:
                e.append("water lake {0} never_exceed_level_m {1} is below its "
                         "level_m {2}".format(lk.get("id"), nx, lk.get("level_m")))
    wf = wr.get("waterfalls")
    if not isinstance(wf, dict):
        e.append("water recipe {0} waterfalls must be an object carrying "
                 "cap_min/cap_max".format(path))
    else:
        cmin, cmax = wf.get("cap_min"), wf.get("cap_max")
        ints = (isinstance(cmin, int) and not isinstance(cmin, bool)
                and isinstance(cmax, int) and not isinstance(cmax, bool))
        if not ints:
            e.append("waterfalls cap_min/cap_max must be integers")
        elif not 0 < cmin <= cmax:
            e.append("waterfalls cap must satisfy 0 < cap_min <= cap_max, got "
                     "{0}/{1}".format(cmin, cmax))
        else:
            tot = wf.get("total_placed_falls")
            if (isinstance(tot, int) and not isinstance(tot, bool)
                    and not cmin <= tot <= cmax):
                e.append("waterfalls total_placed_falls {0} is outside the cap "
                         "[{1},{2}]".format(tot, cmin, cmax))
    return e


def _validate_water(w):
    """Schema water-1.0 `water` — optional top-level POINTER block, strict when
    present. Lifted from Reserved 2026-09-19 (CARVE_PLAN T2), mirroring the way
    `foliage` graduated in v1.6. The block names recipes/water.json by path (the
    city.json precedent: foliage.settlement_exclusion.from_city_plan names a
    file, not inline data); this validator loads it and enforces the water-1.0
    invariants so the endorheic ceiling and the fall cap cannot be prose."""
    if w is None:
        return []
    if not isinstance(w, dict):
        return ["water must be a JSON object, got {0!r}".format(
            type(w).__name__)]
    e = []
    for k in w:
        if k == "from_water_recipe" or k.startswith("_"):
            continue
        e.append("unknown key in water: {0!r}".format(k))
    path = w.get("from_water_recipe")
    if not isinstance(path, str) or not path:
        return e + ["water.from_water_recipe must be a non-empty path string"]
    abspath = path if os.path.isabs(path) else os.path.join(REPO_ROOT, path)
    if not os.path.isfile(abspath):
        return e + ["water.from_water_recipe points at a missing file: "
                    "{0}".format(path)]
    try:
        with open(abspath) as fh:
            wr = json.load(fh)
    except Exception as ex:  # noqa: BLE001 — any load failure is a violation
        return e + ["water recipe {0} is not loadable JSON: {1}".format(
            path, ex)]
    return e + _validate_water_recipe(wr, path)


def _validate_foliage(f, recipe):
    """Schema v1.6 `foliage` — optional, strict when present.

    The checks that carry weight are the CROSS-REFERENCES, not the range
    checks. A species keyed to a layer that does not exist would place
    nothing at all, silently, and look exactly like a density that was
    set too low — the failure mode this project pays most for. Same for
    weight shares summing past 1: the layer would be over-subscribed and
    the last species listed would quietly lose.
    """
    e = []
    if f is None:
        return e
    if not isinstance(f, dict):
        return ["foliage must be an object"]

    # `canopy` (schema v1.21) is the SHARED canopy fact, sibling to
    # `rock_scatter`'s shared physical block and there for the same
    # reason: the radius is a measured property of the tree, not a knob
    # each consumer owns a copy of (non-negotiable 19).
    # `settlement_exclusion` (2026-09-12b) declares the committed town plan
    # whose footprint is dropped from the written instances. It names the
    # PLAN only -- the margins live in recipes/city.json:foliage_clearing,
    # where they were measured by sweep, and duplicating them here would be
    # two sources for one physical fact (NN19).
    # `planting_field` (schema v1.17 / Brief-4 T9) names the PLACEMENT field
    # PNG (derive_planting_field.py output): trees sample this canopy-free
    # field, not the render weightmap they themselves shape. `water_exclusion`
    # (Brief-4 T9) names the derived water-body union mask whose footprint is
    # dropped from the written instances -- the water analogue of
    # settlement_exclusion. Both name a FILE only (NN24: one derivation lives
    # in the producer, not restated here).
    known = {"density_per_hectare", "seed", "species", "rock_scatter",
             "canopy", "settlement_exclusion", "planting_field",
             "water_exclusion",
             # Brief 5 D3 daylight density: optional pointers, both consumed by
             # place_foliage (density_zone_map = the per-location tree-density
             # multiplier map; density_ceiling = the post-multiplier per-bin
             # density ceiling). Absent = uniform density_per_hectare (the
             # pre-Brief-5 behaviour). Non-empty path strings; validated below.
             "density_zone_map", "density_ceiling"}
    for key in f:
        # Underscore keys are prose (the convention every other block honours;
        # the species loop got it on 2026-09-27 and this loop was the next
        # outlier -- `_density_2026_09_27` aborted the Phase 3 D3 driver at
        # its place step, rc 2, five seconds in).
        if key.startswith("_"):
            continue
        if key not in known:
            e.append("unknown key in foliage: {0}".format(key))
    for _dk in ("density_zone_map", "density_ceiling"):
        if _dk in f and not (isinstance(f[_dk], str) and f[_dk]):
            e.append("foliage.{0} must be a non-empty path string, got {1!r}"
                     .format(_dk, f[_dk]))
    e.extend(_validate_rock_scatter(f.get("rock_scatter")))

    if "planting_field" in f and not (isinstance(f["planting_field"], str)
                                      and f["planting_field"]):
        e.append("foliage.planting_field must be a non-empty path string, "
                 "got {0!r}".format(f["planting_field"]))
    we = f.get("water_exclusion")
    if we is not None:
        if not isinstance(we, dict):
            e.append("foliage.water_exclusion must be an object naming an "
                     "exclusion_mask, got {0!r}".format(we))
        else:
            _WE = {"exclusion_mask", "_what"}
            for key in we:
                if key not in _WE:
                    e.append("unknown key in foliage.water_exclusion: {0}"
                             .format(key))
            if not (isinstance(we.get("exclusion_mask"), str)
                    and we.get("exclusion_mask")):
                e.append("foliage.water_exclusion.exclusion_mask must be a "
                         "non-empty path string, got {0!r}"
                         .format(we.get("exclusion_mask")))

    dens = f.get("density_per_hectare")
    if not _is_num(dens) or not 0.0 <= dens <= 100000.0:
        e.append("foliage.density_per_hectare must be a finite number in "
                 "[0, 100000], got {0!r}".format(dens))
    if "seed" in f and (not isinstance(f["seed"], int)
                        or isinstance(f["seed"], bool)):
        e.append("foliage.seed must be an integer, got {0!r}"
                 .format(f["seed"]))

    species = f.get("species")
    if not isinstance(species, list) or not species:
        return e + ["foliage.species must be a non-empty array"]

    # isinstance gate: `or {}` saves only FALSY values — a truthy
    # non-dict material would AttributeError here (same class as the
    # Pass-3 F4 fix above; _validate_material reports the type).
    _mat_blk = recipe.get("material")
    layer_names = {l.get("name") for l in
                   ((_mat_blk.get("layers")
                     if isinstance(_mat_blk, dict) else None) or [])
                   if isinstance(l, dict)}
    seen = set()
    share_by_layer = {}
    for i, sp in enumerate(species):
        tag = "foliage.species[{0}]".format(i)
        if not isinstance(sp, dict):
            e.append("{0} must be an object".format(tag))
            continue
        # A species is either VEGETATION (weight_share off the recipe's
        # density budget, layer-masked) or a ROCK (its own mask kind, its
        # own on-mask density). `role` is the discriminator, and the two
        # key sets are deliberately DISJOINT rather than merged: a rock
        # that carried `weight_share` would silently draw from the tree
        # budget, and a tree that carried `mask` would be planned by a
        # tool that never sees it.
        _VEG = {"name", "mesh", "layer", "weight_share", "slope_deg",
                "height_m", "flow_bias", "scale_range", "align_to_normal",
                "system", "cull_distance_m", "density_per_10m2",
                "varieties", "lods", "sink_depth_m", "closure",
                "override_materials", "collision",
                # `card` is the grass-card material block (ground_tint,
                # hue_percent, brightness_amp, contact_*), consumed by
                # make_foliage_material.py:213-375. Added to Meadow in
                # e59e8da4 (Task 4 grass-card work) but never added HERE, so
                # _validate_foliage rejected the shipped alpine_8k.json --
                # latent because the offline suite's "recipe + gate corpus"
                # is prove_gates.py (synthetic), which never validates the
                # live recipe; foliage regen (Brief-4 T9) is the first thing
                # to re-validate it. Found + fixed 2026-09-19.
                "card",
                # `lod_screen_sizes` (+ its `_..._note`) record the per-species
                # LOD ScreenSize hold persisted by Brief-5 R1 (the card->geometry
                # transition; ConiferPine LOD3 0.03818, SpruceSub LOD4 0.02642).
                # Added to the recipe during R1 but never HERE -- the SAME latent
                # drift as `card` above (prove_gates.py never validates the live
                # recipe), surfaced by the Brief-5 D2 dry run. Found + fixed 2026-09-22.
                "lod_screen_sizes", "_lod_screen_sizes_note"}
        # `flow_bias` is spelled and centred EXACTLY as the vegetation
        # key of the same name (place_foliage), because it is the same
        # physical prior over the same map. `canopy_bias` is new in
        # schema v1.21 and needs `foliage.canopy` — enforced below, not
        # here, because it is a cross-field requirement.
        _ROCK = {"name", "mesh", "role", "mask", "height_m", "scale_range",
                 "align_to_normal", "tumble_deg", "embed_frac",
                 "density_per_hectare_on_mask", "cull_distance_m",
                 "lod_depth", "flow_bias", "canopy_bias", "collision"}
        _is_rock = "role" in sp
        for key in sp:
            # Underscore keys are PROSE (notes beside a value), the same
            # convention `_validate_rock_scatter` already honours for its
            # block. GroundClutter carried `_why` / `_owed_run` and the
            # whole recipe validated INVALID for it, which blocked every
            # consumer that runs this validator (place_foliage,
            # import_layer_textures) -- measured 2026-09-27 at the rocks
            # world run. A note is not a key the pipeline reads.
            if key.startswith("_"):
                continue
            if key not in (_ROCK if _is_rock else _VEG):
                e.append("unknown key in {0}: {1}{2}".format(
                    tag, key,
                    " (this species declares `role`, so it is a ROCK and "
                    "takes the rock key set)" if _is_rock else ""))
        # NAME and MESH are checked for BOTH species kinds, BEFORE the
        # rock branch's `continue` (Pass 3 2026-09-16): they used to sit
        # below it, so a rock with a duplicate/illegal name or a missing/
        # malformed mesh validated clean — and downstream the registry was
        # keyed on mesh_path_key('') which returns [] silently.
        name = sp.get("name")
        if not isinstance(name, str) or not SPECIES_NAME_RE.match(name or ""):
            e.append("{0}.name must match ^[A-Za-z][A-Za-z0-9_]*$ — it "
                     "becomes an asset and instance name — got {1!r}"
                     .format(tag, name))
        elif name in seen:
            e.append("{0}.name {1!r} is a duplicate; names address "
                     "assets, so duplicates break idempotency"
                     .format(tag, name))
        else:
            seen.add(name)
        mesh = sp.get("mesh")
        if not isinstance(mesh, str) or not mesh.startswith("/"):
            e.append("{0}.mesh must be a content-browser path starting "
                     "with '/', got {1!r}".format(tag, mesh))
        if _is_rock:
            e.extend(_validate_rock_species(sp, tag, layer_names))
            # A rock species is always instanced -- there is no `system`
            # key in _ROCK -- so the collision declaration is required
            # here on exactly the same terms as for vegetation.
            e.extend(_validate_collision(sp, tag, "instanced"))
            # CROSS-FIELD: a canopy prior needs a declared canopy source.
            # Checked here because only this scope sees `foliage`. The
            # planner refuses too; this catches it at preflight, which is
            # the whole reason preflight exists (non-negotiable 24: the
            # two checks must not be able to disagree about WHETHER the
            # block is required, so both key off `canopy_bias != 0`).
            # `_is_num` FIRST. `float("lots")` raises, and a validator
            # that raises has converted "your recipe is invalid" into
            # "the tool crashed" — strictly worse, because the caller
            # gets a traceback instead of the list of what to fix. The
            # bounds check above has already recorded the error for a
            # non-numeric value, so skipping the cross-field test here
            # loses nothing. Found by the "canopy_bias 'lots'" probe.
            _cb = sp.get("canopy_bias", 0.0)
            if _is_num(_cb) and float(_cb) != 0.0:
                _can = f.get("canopy")
                if not isinstance(_can, dict):
                    e.append(
                        "{0} declares canopy_bias but the recipe has no "
                        "`foliage.canopy` block naming the plan and radius"
                        .format(tag))
                else:
                    if not isinstance(_can.get("plan"), str):
                        e.append("foliage.canopy.plan must be a filename "
                                 "under foliage/")
                    _r = _can.get("radius_m")
                    if not _is_num(_r) or not 0.0 < _r <= 30.0:
                        e.append(
                            "foliage.canopy.radius_m must be in (0, 30]. It "
                            "is a MEASURED canopy radius, not a taste knob "
                            "— cite the measurement that produced it")
            continue

        sd = sp.get("sink_depth_m", 0.0)
        if not _is_num(sd) or not 0.0 <= sd <= 0.5:
            e.append("{0}.sink_depth_m must be in [0, 0.5] metres: how far "
                     "the instance is lowered along world -Z so its root "
                     "flare INTERSECTS the ground rather than resting on "
                     "it. This is centimetres of interpenetration, not the "
                     "rock `embed_frac`, which buries a fraction of the "
                     "whole mesh — 0.5 m would put a sapling's first "
                     "branches in the soil".format(tag))

        # v1.7. Which ENGINE mechanism places this species, and the two
        # are not interchangeable — they have different economies.
        #   instanced  persistent InstancedFoliageActor instances, placed
        #              by script, one transform each, saved into the
        #              level. Right for sparse large objects. Costs a
        #              package and memory per instance, which is why
        #              place_foliage caps the total.
        #   grass      LandscapeGrassType driven from the landscape
        #              material's own weight mask. The engine spawns and
        #              discards instances near the camera on the GPU, so
        #              nothing is stored and the count is bounded by view
        #              distance rather than by map area. The only way to
        #              get dense ground cover over 65 km2 on this
        #              hardware.
        system = sp.get("system", "instanced")
        if system not in ("instanced", "grass"):
            e.append("{0}.system must be 'instanced' or 'grass', got "
                     "{1!r}".format(tag, system))
        # Keyed off the SAME `system` value the placement path reads, so
        # the preflight and the applier cannot disagree about whether a
        # species needs a collision declaration (non-negotiable 24).
        e.extend(_validate_collision(sp, tag, system))
        # CULL IS MANDATORY FOR INSTANCED SPECIES TOO, AND IT IS THE FIELD
        # THAT ACTUALLY HUNG THE GPU. Closed 2026-08-15.
        #
        # Until today this read `if "cull_distance_m" in sp:` over a bound
        # of `0.0 <= v <= 100000.0`, so THREE catastrophic inputs were
        # accepted in silence:
        #   - the key ABSENT      -> FoliageType's engine default, 0
        #   - 0.0                 -> FoliageType.h:292, "0 disables"
        #   - 100000.0            -> a 100 km cull on a 8.128 km map
        # and the comment DIRECTLY BELOW this block already spelled out
        # what the first two cost: "28,302 505k-triangle trees were
        # submitted every frame across an 8 km map until the GPU missed the
        # Windows TDR deadline and returned DXGI_ERROR_DEVICE_HUNG".
        #
        # The narrative was in the file and the gate did not enforce it.
        # That is the recurrence class non-negotiable 4 names: the
        # mandatory-cull fix was applied to the GRASS branch on 2026-08-08,
        # forty lines further down, and never swept to the INSTANCED branch
        # — even though the hang happened on the instanced path and the
        # grass comment says so in its own words.
        #
        # Non-negotiable 3: the key is now REQUIRED and the interval is
        # OPEN at zero, so the disabling value is no longer expressible
        # rather than merely rejected.
        #
        # The bound is (0, 5000] to MATCH the cull_distance_m check in
        # `_validate_rock_species` exactly (cite the NAME, not a line —
        # a line citation here had already drifted once, Pass 3
        # 2026-09-16). Rocks and trees are the same instanced path with the
        # same cost mechanism, and one physical constraint gets one number
        # (non-negotiable 24) rather than a second bound free to drift.
        if system == "instanced":
            v = sp.get("cull_distance_m")
            if not _is_num(v) or not 0.0 < v <= 5000.0:
                e.append("{0}.cull_distance_m is REQUIRED for "
                         "system='instanced' and must be in (0, 5000] "
                         "metres; got {1!r}. Omitting it does not mean "
                         "'engine default' in any useful sense — "
                         "FoliageType's default is 0, and FoliageType.h:292 "
                         "documents 0 as DISABLING the cull, which is how "
                         "this project submitted 28,302 505k-triangle trees "
                         "every frame and lost the GPU to a TDR timeout. "
                         "R5 locks the conifers at 730 m.".format(tag, v))
        elif "cull_distance_m" in sp:
            v = sp["cull_distance_m"]
            if not _is_num(v) or not 0.0 <= v <= 100000.0:
                e.append("{0}.cull_distance_m must be a finite number in "
                         "[0, 100000], got {1!r}".format(tag, v))
            # NO system restriction, and the one that used to be here
            # was FALSE. It read "instanced species are not view-culled
            # by the foliage type", which is exactly backwards:
            # FoliageType::CullDistance IS the instanced cull distance
            # (FoliageType.h:296, consumed at InstancedFoliage.cpp:224
            # via SetCullDistances). Grass is the one that uses a
            # different field, GrassVariety's own start/end_cull_distance.
            #
            # The cost of that sentence: it did not merely fail to help,
            # it FORBADE the fix. Every instanced species was left on the
            # engine default of 0, which FoliageType.h:292 documents as
            # "0 disables", so 28,302 505k-triangle trees were submitted
            # every frame across an 8 km map until the GPU missed the
            # Windows TDR deadline and returned DXGI_ERROR_DEVICE_HUNG.
        # GRASS CARRIES ITS OWN DENSITY, in the engine's own unit.
        # `density_per_hectare` x `weight_share` is a budget for
        # PERSISTENT instances and is sized accordingly — 34/ha here.
        # Ground cover is three orders of magnitude denser, and running
        # it through the same budget produced 0.0119 instances per
        # 10 m2, i.e. nothing. Two mechanisms with a 1000x difference in
        # natural scale should not share one number; sharing it produces
        # a value that is silently, uselessly small (section 18.5 —
        # express a parameter in units a person can picture).
        if system == "grass":
            v = sp.get("density_per_10m2")
            if not _is_num(v) or not 0.0 < v <= 400.0:
                e.append("{0}.density_per_10m2 is required for "
                         "system='grass' and must be a finite number in "
                         "(0, 400]; got {1!r}. This is the engine's own "
                         "unit (LandscapeGrassType: instances per 10 "
                         "square metres). density_per_hectare and "
                         "weight_share budget PERSISTENT instances and "
                         "do not apply."
                         .format(tag, v))
            if "weight_share" in sp and sp.get("weight_share"):
                e.append("{0}.weight_share has no meaning with "
                         "system='grass': grass is not drawn from the "
                         "persistent-instance budget. Use "
                         "density_per_10m2.".format(tag))
            # CULL IS MANDATORY FOR GRASS, AND THIS IS THE FIELD THAT
            # ONCE HUNG THE GPU. Added 2026-08-08.
            #
            # `cull_distance_m` was validated only `if present`, so a
            # grass species could omit it — and
            # `make_landscape_material.py:2441` then defaulted to
            # **12000.0 metres**. At Meadow's locked 12 tufts/m2 a 12 km
            # cull is pi*12000^2*12 = about 5.4 BILLION instances.
            #
            # The comment forty lines above this one already records what
            # a missing cull costs on this machine: "28,302 505k-triangle
            # trees were submitted every frame across an 8 km map until
            # the GPU missed the Windows TDR deadline and returned
            # DXGI_ERROR_DEVICE_HUNG". That lesson was written about the
            # INSTANCED path and never applied to the grass path beside
            # it.
            #
            # Non-negotiable 3: prefer an input that cannot express the
            # catastrophic value over a gate that rejects it. REQUIRING
            # the key deletes the 12 km default from the reachable state
            # space entirely; the bound below only limits explicit
            # over-reach. R11 locks Meadow at 50 m and measured raising
            # it as strictly worse, and 250 m is already ~24x that cost.
            cv = sp.get("cull_distance_m")
            if not _is_num(cv) or not 0.0 < cv <= GRASS_CULL_MAX_M:
                e.append("{0}.cull_distance_m is REQUIRED for "
                         "system='grass' and must be in (0, " + str(GRASS_CULL_MAX_M) + "] metres; "
                         "got {1!r}. Omitting it does not mean 'engine "
                         "default' — the builder substitutes 12000.0 m, "
                         "which at 12 tufts/m2 is ~5.4 billion instances "
                         "and is how this project lost the GPU to a TDR "
                         "timeout once already. R11 locks Meadow at 50 m; "
                         "512 m is the streaming range (perception."
                         "_cull_ceiling), and the grass DISC GUARD bounds "
                         "the count a cull can reach."
                         .format(tag, cv))
            # GRASS DISC GUARD (Brief 7 P3b, 2026-09-27). The TDR class the
            # cull bound exists for is a COUNT, not a distance: pi*cull^2*
            # density is what the engine spawns around the camera. Raising
            # the distance ceiling from 250 to 512 m (the streaming range,
            # so a far tier of ground cover can represent the 50-512 m band
            # the perception block records as unrepresented) is only safe
            # with the count bounded here. Meadow's ruled 50 m / 120 per
            # 10 m2 = 94,248 (R11's own figure) passes; a 512 m species must
            # stay under ~1.8 per 10 m2 to pass (MeadowFar's 0.6 = 49,413,
            # 3x headroom); the 12 km default that
            # hung the GPU would read 5.4 billion and be refused twice.
            dv = sp.get("density_per_10m2")
            if _is_num(cv) and _is_num(dv) and cv > 0.0 and dv > 0.0:
                disc = math.pi * cv * cv * dv / 10.0
                if disc > GRASS_DISC_MAX_INSTANCES:
                    e.append("{0}: cull_distance_m {1} x density_per_10m2 "
                             "{2} = {3:,.0f} instances in the cull disc "
                             "(pi*cull^2*density/10), over the grass disc "
                             "guard of {4:,.0f}. Lower the density or the "
                             "cull; do not raise the guard to silence "
                             "this -- Meadow at its ruled 50 m / 120 is "
                             "94,248 and that is the calibrated cost "
                             "(R11)."
                             .format(tag, cv, dv, disc,
                                     GRASS_DISC_MAX_INSTANCES))
        elif "density_per_10m2" in sp:
            e.append("{0}.density_per_10m2 applies only to "
                     "system='grass'".format(tag))

        if system == "grass" and sp.get("flow_bias"):
            # Grass density comes from the material's weight mask, which
            # has no access to the flow map. Silently ignoring it would
            # be a parameter that reads as live and does nothing.
            e.append("{0}.flow_bias has no effect with system='grass': "
                     "density comes from the landscape material's weight "
                     "mask, which cannot sample terrain/alpine_flow.png. "
                     "Remove it, or use system='instanced'.".format(tag))

        # (name and mesh are validated ABOVE the rock branch now — one
        # spelling for both species kinds; Pass 3 2026-09-16.)

        # v1.12 LODS. The reduction chain for LOD1..N. LOD 0 is NOT
        # expressible here and is prepended by make_mesh_lods.py at
        # 1.0 — because FStaticMeshReductionOptions::ReductionSettings[0]
        # IS LOD 0 (StaticMeshEditorSubsystem.cpp:400-402), so a chain
        # that looked like [0.25, 0.06] would DECIMATE THE SOURCE MESH
        # to a quarter and report success. An input that cannot express
        # the catastrophic value beats a gate that rejects it.
        if "lods" in sp:
            lods = sp["lods"]
            if not isinstance(lods, list) or not lods:
                e.append("{0}.lods must be a non-empty list".format(tag))
            else:
                prev = 1.0
                # Effective LOD 0 screen size: make_mesh_lods reads
                # `screen_size_lod0` from lods[0] ONLY and defaults it
                # to 1.0. It is validated here because an unvalidated
                # value (json.load accepts NaN) would flow through
                # float() into the engine as LOD 0's screen size with
                # nothing erroring — the silent-wrong class (audit
                # 2026-08-02, F4).
                prev_ss = 1.0
                for k, c in enumerate(lods):
                    lt = "{0}.lods[{1}]".format(tag, k)
                    if not isinstance(c, dict):
                        e.append("{0} must be an object".format(lt))
                        continue
                    for key in c:
                        if key not in {"percent_triangles", "screen_size",
                                       "screen_size_lod0"}:
                            e.append("unknown key in {0}: {1}".format(
                                lt, key))
                    if "screen_size_lod0" in c:
                        ss0 = c.get("screen_size_lod0")
                        if k > 0:
                            e.append("{0}.screen_size_lod0 is only legal "
                                     "on lods[0]; anywhere else it is "
                                     "silently ignored".format(lt))
                        elif not _is_num(ss0) or not 0.0 < float(ss0) <= 1.0:
                            e.append("{0}.screen_size_lod0 must be a "
                                     "finite number in (0, 1], got {1!r}"
                                     .format(lt, ss0))
                        else:
                            prev_ss = float(ss0)
                    pt = c.get("percent_triangles")
                    if not _is_num(pt) or not 0.0 < float(pt) < 1.0:
                        e.append("{0}.percent_triangles must be a finite "
                                 "number strictly between 0 and 1, got "
                                 "{1!r}. 1.0 is LOD 0 and is not yours to "
                                 "set.".format(lt, pt))
                    elif float(pt) >= prev:
                        e.append("{0}.percent_triangles {1} is not less "
                                 "than the previous level's {2}; a LOD "
                                 "chain that does not shrink costs more "
                                 "than no chain".format(lt, pt, prev))
                    else:
                        prev = float(pt)
                    ss = c.get("screen_size")
                    if not _is_num(ss) or not 0.0 < float(ss) <= 1.0:
                        e.append("{0}.screen_size must be a finite number "
                                 "in (0, 1], got {1!r}".format(lt, ss))
                    elif float(ss) >= prev_ss:
                        e.append("{0}.screen_size {1} is not less than "
                                 "the previous LOD's {2}; the engine "
                                 "selects LODs by descending screen size, "
                                 "so a non-decreasing chain silently "
                                 "shadows a level (audit 2026-08-02, F5)"
                                 .format(lt, ss, prev_ss))
                    else:
                        prev_ss = float(ss)

        # v1.10 VARIETIES. Grass only: a LandscapeGrassType holds a list
        # of GrassVariety, and the vendor sets are authored as size
        # classes for exactly that. `mesh` stays REQUIRED even when
        # varieties are present, as the documented fallback — a recipe
        # that loses its variety list should thin, not break.
        #
        # `share` is a WEIGHT, not a fraction: the shares are normalised
        # by their own sum downstream, so they are checked for being
        # positive and finite, NOT for summing to 1. Requiring a sum of
        # 1 would reject a list that rounds to 0.99, which is a
        # validation error about arithmetic rather than about intent.
        if "varieties" in sp:
            if system != "grass":
                e.append("{0}.varieties applies only to system 'grass'; "
                         "instanced species carry one mesh and are placed "
                         "by place_foliage.".format(tag))
            vs = sp["varieties"]
            if not isinstance(vs, list) or not vs:
                e.append("{0}.varieties must be a non-empty list".format(
                    tag))
            else:
                total = 0.0
                for k, v in enumerate(vs):
                    vt = "{0}.varieties[{1}]".format(tag, k)
                    if not isinstance(v, dict):
                        e.append("{0} must be an object".format(vt))
                        continue
                    for key in v:
                        if key not in {"mesh", "share", "scale_range",
                                       "override_materials"}:
                            e.append("unknown key in {0}: {1}".format(
                                vt, key))
                    # v1.22 OVERRIDE MATERIALS. `GrassVariety` carries
                    # `override_materials` in 5.8 (PythonStub :121628), and
                    # it is the ONLY way to render a vendor grass mesh with
                    # a material we control. The blueberry understory needs
                    # it: its master declares the same `Level 1/2/3 Wind`
                    # static switches the PN trees do, an animating
                    # understory makes every frame A/B non-deterministic,
                    # and the pack is gitignored with 0 tracked files so
                    # the vendor MI must never be rewritten.
                    #
                    # POSITIONAL, in the mesh's own slot order. A list in
                    # the wrong order silently repaints the plant, so it is
                    # checked for shape here and READ BACK off the saved
                    # asset by the builder.
                    if "override_materials" in v:
                        om = v["override_materials"]
                        if not isinstance(om, list) or not om:
                            e.append("{0}.override_materials must be a "
                                     "non-empty list of content-browser "
                                     "paths".format(vt))
                        else:
                            for oi, op in enumerate(om):
                                if not isinstance(op, str) or \
                                        not op.startswith("/"):
                                    e.append(
                                        "{0}.override_materials[{1}] must be "
                                        "a content-browser path starting "
                                        "with '/', got {2!r}".format(
                                            vt, oi, op))
                    vm = v.get("mesh")
                    if not isinstance(vm, str) or not vm.startswith("/"):
                        e.append("{0}.mesh must be a content-browser path "
                                 "starting with '/', got {1!r}".format(
                                     vt, vm))
                    sh = v.get("share", 1.0)
                    if not _is_num(sh) or float(sh) <= 0.0:
                        e.append("{0}.share must be a finite number > 0, "
                                 "got {1!r}".format(vt, sh))
                    else:
                        total += float(sh)
                    if "scale_range" in v:
                        vr = v["scale_range"]
                        if (not isinstance(vr, list) or len(vr) != 2
                                or not all(_is_num(x) for x in vr)):
                            e.append("{0}.scale_range must be [min, max] "
                                     "finite numbers".format(vt))
                        elif not (0.0 < float(vr[0]) <= float(vr[1])):
                            e.append("{0}.scale_range must be positive and "
                                     "non-inverted, got {1!r}".format(
                                         vt, vr))
                if vs and total <= 0.0:
                    e.append("{0}.varieties: every share is zero or "
                             "negative, so the species would place "
                             "nothing. Remove it instead.".format(tag))

        # v1.23 CLOSURE. Canopy closure against elevation, as a density
        # MULTIPLIER — it scales rather than redistributing, so it lowers
        # the placed count and the density must be re-derived against it.
        #
        # Bounded to [0, 1] at both ends: a multiplier above 1 would mean
        # "more trees than the declared density", which is a second density
        # knob wearing a gradient's name and the sort of thing that makes a
        # count unpredictable from the recipe. Zero IS permitted at
        # at_high, and describes a stand that reaches true treeline.
        #
        # `at_low` and `at_high` are both REQUIRED when the block is
        # present. Defaulting either would make an incomplete block mean
        # something, and a half-declared gradient reads like a setting
        # (NN21).
        if "closure" in sp:
            clo = sp["closure"]
            if system == "grass":
                e.append("{0}.closure applies to instanced species; grass "
                         "density is governed by the landscape material's "
                         "weight mask, not by this planner.".format(tag))
            if not isinstance(clo, dict):
                e.append("{0}.closure must be an object with at_low and "
                         "at_high".format(tag))
            else:
                for k in clo:
                    if k not in {"at_low", "at_high"}:
                        e.append("unknown key in {0}.closure: {1}".format(
                            tag, k))
                for k in ("at_low", "at_high"):
                    if k not in clo:
                        e.append("{0}.closure.{1} is REQUIRED when closure "
                                 "is declared; a half-declared gradient "
                                 "reads like a setting".format(tag, k))
                    elif not _is_num(clo[k]) or not 0.0 <= float(clo[k]) <= 1.0:
                        e.append("{0}.closure.{1} must be a finite number in "
                                 "[0, 1] (a density MULTIPLIER), got {2!r}"
                                 .format(tag, k, clo[k]))

        # v1.24 OVERRIDE MATERIALS on an INSTANCED species. Renders a vendor
        # mesh with a material we control, via
        # FoliageType_InstancedStaticMesh.override_materials
        # (PythonStub:394542) - the only route that does not edit a vendor
        # asset, which is forbidden because the packs are gitignored with 0
        # tracked files.
        #
        # This key did not exist until 2026-08-15, and its absence is why
        # 108,417 placed trees rendered with wind ON: the MIs were built and
        # verified, the recipe COULD NOT DECLARE THEM, and place_foliage set
        # only mesh and cull_distance. The capability existed the whole time.
        #
        # POSITIONAL, in the mesh's own slot order. Read back by the placer.
        if "override_materials" in sp:
            om = sp["override_materials"]
            if system == "grass":
                e.append("{0}.override_materials on a grass species belongs "
                         "on each VARIETY, not on the species - the engine "
                         "carries it per GrassVariety.".format(tag))
            elif not isinstance(om, list) or not om:
                e.append("{0}.override_materials must be a non-empty list of "
                         "content-browser paths".format(tag))
            else:
                for oi, op in enumerate(om):
                    if not isinstance(op, str) or not op.startswith("/"):
                        e.append("{0}.override_materials[{1}] must be a "
                                 "content-browser path starting with '/', "
                                 "got {2!r}".format(tag, oi, op))

        layer = sp.get("layer")
        if not isinstance(layer, str) or not layer:
            e.append("{0}.layer must be a string".format(tag))
        elif layer_names and layer not in layer_names:
            # THE CHECK THAT MATTERS. Placing nothing is indistinguishable
            # from a density set too low, so this must refuse rather than
            # produce an empty world nobody can explain.
            e.append("{0}.layer {1!r} names no layer in material.layers "
                     "({2}). A species keyed to a layer that does not "
                     "exist places NOTHING, silently."
                     .format(tag, layer, sorted(layer_names)))

        if system != "grass":
            share = sp.get("weight_share")
            if not _is_num(share) or not 0.0 <= share <= 1.0:
                e.append("{0}.weight_share must be a finite number in "
                         "[0, 1], got {1!r}".format(tag, share))
            elif isinstance(layer, str):
                share_by_layer[layer] = (share_by_layer.get(layer, 0.0)
                                         + share)

        for key, lo, hi in (("slope_deg", 0.0, 90.0),
                            ("height_m", 0.0, 100000.0)):
            v = sp.get(key)
            if not _num_pair(v):
                e.append("{0}.{1} must be [min, max] finite numbers"
                         .format(tag, key))
            elif not (lo <= v[0] <= hi and lo <= v[1] <= hi):
                e.append("{0}.{1} must lie in [{2}, {3}], got {4!r}"
                         .format(tag, key, lo, hi, v))
            elif v[0] > v[1]:
                e.append("{0}.{1} is inverted: {2} > {3}"
                         .format(tag, key, v[0], v[1]))

        sr = sp.get("scale_range")
        if not _num_pair(sr):
            e.append("{0}.scale_range must be [min, max] finite numbers"
                     .format(tag))
        elif not (sr[0] > 0.0 and sr[1] > 0.0):
            e.append("{0}.scale_range values must both be > 0, got {1!r}"
                     .format(tag, sr))
        elif sr[0] > sr[1]:
            e.append("{0}.scale_range is inverted: {1} > {2}"
                     .format(tag, sr[0], sr[1]))

        if "flow_bias" in sp:
            v = sp["flow_bias"]
            if not _is_num(v) or not -1.0 <= v <= 1.0:
                e.append("{0}.flow_bias must be a finite number in "
                         "[-1, 1], got {1!r}".format(tag, v))
        if "align_to_normal" in sp:
            v = sp["align_to_normal"]
            if not _is_num(v) or not 0.0 <= v <= 1.0:
                e.append("{0}.align_to_normal must be a finite number in "
                         "[0, 1], got {1!r}".format(tag, v))

    for layer, total in sorted(share_by_layer.items()):
        if total > 1.0 + 1e-9:
            e.append("foliage weight_share for layer {0!r} sums to "
                     "{1:.3f} > 1. The layer would be over-subscribed and "
                     "which species loses would depend on list order."
                     .format(layer, total))
    # RULING (c), Ryan 2026-08-02: a mesh a RECIPE names must come from
    # a pivot-normalised source. Ad-hoc vendor imports stay ungated —
    # importing a vendor file to MEASURE it is legitimate — but the
    # recipe is what decides whether something gets instanced, so the
    # recipe is where the requirement belongs.
    #
    # Reported as ordinary validation errors, so every script that
    # validates a recipe inherits the gate without knowing about it.
    e.extend(landscape_spec.recipe_normalization_errors(recipe))

    return e


def _validate_world(w):
    """Schema v1.5 `world` — what this world is FOR, so it can be refused.

    Every gate in this pipeline so far reports. None of them refuse a
    world for being a bad world, because nothing recorded what the world
    was supposed to be. `traversability()` prints four movement modes
    with no opinion about which one matters here — deliberately, so no
    future world is silently made a walking world — and the consequence
    is that a terrain missing its own design target ships with the
    numbers printed above it.

    This block is where the intent goes. It is OPTIONAL: a recipe
    without it behaves exactly as before, which keeps every existing
    recipe valid. Present, it is strict.

    Note the pairing with `composition()`. A connectivity target alone is
    maximised by a FEATURELESS map — a billiard table is 100% crossable
    in one piece — so a world that declares a connectivity floor must
    also declare a flatness ceiling, or the gate rewards exactly the
    defect that cost this project its massif mask.
    """
    e = []
    if w is None:
        return e
    if not isinstance(w, dict):
        return ["world must be an object"]

    known = {"primary_movement_mode", "min_crossable_frac",
             "min_connected_frac", "max_border_flat_frac",
             "flat_relief_m"}
    for key in w:
        if key not in known:
            e.append("unknown key in world: {0}".format(key))

    mode = w.get("primary_movement_mode")
    if mode is None:
        e.append("world.primary_movement_mode is required when world is "
                 "present — a target with no mode cannot be checked")
    elif mode not in MOVEMENT_MODES:
        e.append("world.primary_movement_mode must be one of {0}, got "
                 "{1!r}".format(list(MOVEMENT_MODES), mode))

    for key, lo, hi in (("min_crossable_frac", 0.0, 1.0),
                        ("min_connected_frac", 0.0, 1.0),
                        ("max_border_flat_frac", 0.0, 1.0)):
        if key not in w:
            continue
        v = w[key]
        # `not (lo <= v <= hi)` so NaN is REFUSED, not admitted. json
        # accepts the NaN literal and every plain comparison against it
        # is False (lesson 2.9, fixed three times in this repo).
        if not _is_num(v) or not lo <= v <= hi:
            e.append("world.{0} must be a finite number in [{1}, {2}], "
                     "got {3!r}".format(key, lo, hi, v))

    if "flat_relief_m" in w:
        v = w["flat_relief_m"]
        if not _is_num(v) or not 0.0 < v <= 1000.0:
            e.append("world.flat_relief_m must be a finite number in "
                     "(0, 1000], got {0!r}".format(v))

    if ("min_connected_frac" in w and "max_border_flat_frac" not in w):
        e.append("world.min_connected_frac without "
                 "world.max_border_flat_frac: a connectivity target is "
                 "maximised by a FEATURELESS map (a plain is 100% "
                 "crossable in one piece), so it must be paired with a "
                 "flatness ceiling or it rewards the defect it looks "
                 "like it prevents")
    return e


# --------------------------------------------------------- v1.12 stamps --
# Terrain FEATURE compositing. See recipes/schema.md v1.12 and RECIPES.md
# R-STAMP. The validator owns the SHAPE; scripts/composite_stamps.py owns
# the pixels and the content-hash cross-check against the catalogue,
# because that needs file IO and this function must stay pure.

STAMP_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# Blend modes. Every one is applied THROUGH the falloff mask as
#     H' = H + mask * (target - H)
# so at mask 0 every mode is the identity and no mode can leave a hard
# rectangular seam. A raw np.maximum(H, stamp) would.
STAMP_BLENDS = ("ADD", "MAX", "MIN", "MASKED")
# What stamp value counts as "no change" for ADD. A StampIT map is a full
# 0..65535 field, NOT a delta — measured across all 52
# (terrain/stampit_catalogue.json relief_stats). Leaving the datum
# implicit is exactly the "a value arrived and meant something else"
# defect, so it is a required, named enum.
STAMP_DATUMS = ("zero", "min", "mean", "median")
STAMP_FALLOFF_SHAPES = ("chebyshev", "euclidean")
_STAMP_PLACEMENT_KEYS = {
    "id", "stamp_sha256", "centre_m", "size_m", "rotation_deg",
    "flip_x", "flip_y", "blend", "amplitude_m", "datum", "anchor_m",
    "falloff", "falloff_shape", "opacity",
    # v1.15 — see _validate_stamps. Required, not defaulted: a default
    # living in composite_stamps.py is a scene parameter living in a
    # script, which is the hard rule 2 violation the recipe system exists
    # to prevent. `falloff_jitter: 0.0` is how a placement asks for the
    # exact geometric falloff, and it says so out loud.
    "falloff_jitter", "falloff_jitter_scale",
}


def _repo_rel_path_errors(value, label):
    """Conduct rule 1: repo-relative only, no '..', no drive, no UNC."""
    e = []
    if not isinstance(value, str) or not value:
        return ["{0} must be a non-empty string".format(label)]
    if (os.path.isabs(value) or re.match(r"^[A-Za-z]:", value)
            or value.startswith("\\\\") or value.startswith("//")):
        e.append("{0} must be repo-relative, got {1!r}".format(label, value))
    if ".." in re.split(r"[\\/]+", value):
        e.append("{0} must not contain a '..' segment".format(label))
    return e


def _same_repo_path(a, b):
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return (os.path.normcase(os.path.normpath(a))
            == os.path.normcase(os.path.normpath(b)))


PALETTE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PALETTE_ADMIT = ("YES", "CONDITIONAL", "HAZARD")


def _validate_palette(p):
    """Schema v1.13 `palette` — optional, strict when present.

    The palette is the approved asset list the region campaign builds
    from. It is GENERATED by `scripts/make_alpine_palette.py`, so most of
    its shape is guaranteed by construction; this validator exists for the
    case that matters, which is a HAND EDIT.

    The one load-bearing rule:

    * `verified: true` REQUIRES a non-empty `verified_proof`, and
      `verified: false` REQUIRES a non-empty `verified_reason`.

    The campaign brief rules that verified flags stay NO until an asset is
    render-proved. A bare `verified: true` is exactly the derived record
    CLAUDE.md non-negotiable 15 forbids — a state claim written from
    narrative rather than checked against the artefact. Requiring the
    proof PATH makes an unproven `true` unrepresentable rather than
    merely discouraged (non-negotiable 3), and it means the claim can
    always be re-checked by opening the file it names (non-negotiable 9).

    This validator deliberately does NOT check that the proof file exists
    on disk. It runs during a recipe load on machines that may not have
    `_verify/` populated, and a missing render is a verification finding
    for the pass that owns it, not a reason to refuse to import a
    heightmap. What is enforced here is that the CLAIM CARRIES ITS
    CITATION.
    """
    e = []
    if p is None:
        return e
    if not isinstance(p, dict):
        return ["palette must be an object"]

    entries = p.get("entries")
    if not isinstance(entries, list) or not entries:
        return ["palette.entries must be a non-empty array"]

    seen = set()
    for i, ent in enumerate(entries):
        where = "palette.entries[{0}]".format(i)
        if not isinstance(ent, dict):
            e.append("{0} must be an object".format(where))
            continue

        pid = ent.get("id")
        if not isinstance(pid, str) or not PALETTE_ID_RE.match(pid or ""):
            e.append("{0}.id must match ^[a-z][a-z0-9_]*$, got {1!r}"
                     .format(where, pid))
        elif pid in seen:
            e.append("{0}.id {1!r} is a duplicate".format(where, pid))
        else:
            seen.add(pid)
            where = "palette entry {0!r}".format(pid)

        path = ent.get("path")
        if not isinstance(path, str) or not path.startswith("/Game/"):
            e.append("{0}.path must be a /Game/ asset path, got {1!r}"
                     .format(where, path))

        if not isinstance(ent.get("role"), str) or not ent.get("role"):
            e.append("{0}.role must be a non-empty string".format(where))

        if not isinstance(ent.get("pass"), int) or isinstance(
                ent.get("pass"), bool):
            e.append("{0}.pass must be an integer campaign pass number"
                     .format(where))

        if ent.get("admit") not in PALETTE_ADMIT:
            e.append("{0}.admit must be one of {1}, got {2!r}".format(
                where, list(PALETTE_ADMIT), ent.get("admit")))

        ver = ent.get("verified")
        if not isinstance(ver, bool):
            e.append("{0}.verified must be a boolean".format(where))
        elif ver:
            proof = ent.get("verified_proof")
            if not isinstance(proof, str) or not proof.strip():
                e.append(
                    "{0} claims verified=true with no verified_proof. A "
                    "verified flag is a claim about the artefact and must "
                    "cite the render that proves it; promotion happens in "
                    "the pass that renders the asset, never by editing "
                    "this flag".format(where))
        else:
            reason = ent.get("verified_reason")
            if not isinstance(reason, str) or not reason.strip():
                e.append("{0} is verified=false with no verified_reason; "
                         "state what is still missing".format(where))

    return e


_DETAIL_KEYS = {"amplitude_m", "wavelength_m", "octaves", "lacunarity",
                "gain", "slope_deg", "slope_feather_deg", "seed"}


def _validate_detail_relief(d):
    """Schema v1.16 `stamps.detail_relief` — optional, strict when present.

    A slope-masked ridge-noise pass applied AFTER every placement, so
    that steep ground carries cell-scale relief even where no stamp
    reached it. Measured need, not a preference: after the Pass 1
    composition, **45.2% of faces steeper than 45 degrees had
    |laplacian| < 1.0 m**, and the stamped surface was SMOOTHER on steep
    ground than the base it came from (median 1.133 m vs 1.289 m) —
    stamps add large-scale SLOPE faster than fine RELIEF. A steep face
    with no cell-scale relief renders as a glossy featureless wall and no
    material can rescue it, because the landscape normal comes from this
    height field.

    `amplitude_m` is bounded at 25 m. This is detail, not landform: an
    unbounded amplitude here would let a "texture" pass silently rewrite
    the terrain the composition was approved on.
    """
    e = []
    if d is None:
        return e
    if not isinstance(d, dict):
        return ["stamps.detail_relief must be an object"]

    for key in d:
        if key not in _DETAIL_KEYS:
            e.append("unknown key in stamps.detail_relief: {0}".format(key))
    for key in sorted(_DETAIL_KEYS):
        if key not in d:
            e.append("stamps.detail_relief.{0} is required; a default "
                     "living in composite_stamps.py would be a scene "
                     "parameter living in a script".format(key))
    if e:
        return e

    a = d["amplitude_m"]
    if not _is_num(a) or not 0.0 < a <= 25.0:
        e.append("stamps.detail_relief.amplitude_m must be a finite number "
                 "in (0, 25]: this is cell-scale DETAIL, not landform, and "
                 "an unbounded value would let it rewrite the approved "
                 "composition")
    w = d["wavelength_m"]
    if not _is_num(w) or not 4.0 <= w <= 2000.0:
        e.append("stamps.detail_relief.wavelength_m must be a finite number "
                 "in [4, 2000]: below one cell (4 m here) it is aliasing, "
                 "not relief")
    o = d["octaves"]
    if not isinstance(o, int) or isinstance(o, bool) or not 1 <= o <= 8:
        e.append("stamps.detail_relief.octaves must be an integer in [1, 8]")
    lac = d["lacunarity"]
    if not _is_num(lac) or not 1.1 <= lac <= 4.0:
        e.append("stamps.detail_relief.lacunarity must be a finite number "
                 "in [1.1, 4.0]")
    g = d["gain"]
    if not _is_num(g) or not 0.0 < g < 1.0:
        e.append("stamps.detail_relief.gain must be a finite number in "
                 "(0, 1); >= 1 makes each octave louder than the last and "
                 "the sum diverges with octave count")
    # _num_pair is a PREDICATE, not a parser — it returns a bool. Reading
    # its body rather than assuming its shape is the whole of R3's
    # "read the source before trusting a name".
    if not _num_pair(d["slope_deg"]):
        e.append("stamps.detail_relief.slope_deg must be a [lo, hi] pair "
                 "of finite numbers")
    else:
        lo_s, hi_s = [float(v) for v in d["slope_deg"]]
        if not 0.0 <= lo_s < hi_s <= 90.0:
            e.append("stamps.detail_relief.slope_deg must satisfy "
                     "0 <= lo < hi <= 90, got [{0}, {1}]".format(lo_s, hi_s))
    f = d["slope_feather_deg"]
    if not _is_num(f) or not 0.0 < f <= 30.0:
        e.append("stamps.detail_relief.slope_feather_deg must be a finite "
                 "number in (0, 30]; 0 would put a hard slope edge into the "
                 "detail mask, which is the crease the smoothstep falloff "
                 "exists to avoid")
    sd_seed = d["seed"]
    if not isinstance(sd_seed, int) or isinstance(sd_seed, bool):
        e.append("stamps.detail_relief.seed must be an integer; the noise "
                 "is deterministic and the seed is part of the recipe, not "
                 "of the run")
    return e


def _validate_stamps(s, recipe):
    """Schema v1.12 `stamps` — optional, strict when present.

    Three of these checks are the load-bearing ones, and all three exist
    because the failure they prevent is SILENT:

    * `base` != `output`, and `output` != `heightmap.source`. Compositing
      onto the previous output accumulates stamps on every re-run while
      reporting success, which breaks hard pipeline rule 3. Making the
      two paths distinct at the SCHEMA level is stronger than a runtime
      gate — an unrepresentable state beats a rejected one
      (CLAUDE.md non-negotiable 3).
    * `datum` and `anchor_m` are MODE-EXCLUSIVE, not merely optional. An
      `anchor_m` on an ADD placement would be an inert field that reads
      like a setting; this project has paid for inert fields repeatedly.
    * every knob is REQUIRED. A default living in the script is a scene
      parameter living in the script, which is the hard rule 2 violation
      the whole recipe system exists to prevent.
    """
    e = []
    if s is None:
        return e
    if not isinstance(s, dict):
        return ["stamps must be an object"]

    known = {"base", "output", "catalogue", "allow_edge_clip", "placements",
             "detail_relief"}
    for key in s:
        if key not in known:
            e.append("unknown key in stamps: {0}".format(key))

    e.extend(_repo_rel_path_errors(s.get("base"), "stamps.base"))
    e.extend(_repo_rel_path_errors(s.get("output"), "stamps.output"))
    e.extend(_repo_rel_path_errors(s.get("catalogue"), "stamps.catalogue"))

    if _same_repo_path(s.get("base"), s.get("output")):
        e.append("stamps.base and stamps.output must be different files; "
                 "compositing onto the previous output accumulates every "
                 "re-run and violates hard pipeline rule 3")
    _hm_blk = recipe.get("heightmap")
    hm_src = (_hm_blk.get("source") if isinstance(_hm_blk, dict) else None)
    if _same_repo_path(s.get("output"), hm_src):
        e.append("stamps.output must not be heightmap.source ({0!r}); "
                 "adopting a stamped map is a deliberate recipe edit, not "
                 "a side effect of running the compositor".format(hm_src))

    if not isinstance(s.get("allow_edge_clip"), bool):
        e.append("stamps.allow_edge_clip must be a boolean (fail closed: "
                 "false refuses any placement whose footprint leaves the "
                 "map, because a clipped falloff IS a hard seam)")

    e.extend(_validate_detail_relief(s.get("detail_relief")))

    pls = s.get("placements")
    if not isinstance(pls, list) or not pls:
        # "Composite nothing" is expressed by removing the block, exactly
        # as varieties/shares are handled in v1.10. An empty list would be
        # a run that reports success and does nothing.
        return e + ["stamps.placements must be a non-empty array"]

    seen = set()
    for i, p in enumerate(pls):
        tag = "stamps.placements[{0}]".format(i)
        if not isinstance(p, dict):
            e.append("{0} must be an object".format(tag))
            continue
        for key in p:
            if key not in _STAMP_PLACEMENT_KEYS:
                e.append("unknown key in {0}: {1}".format(tag, key))

        pid = p.get("id")
        if not isinstance(pid, str) or not STAMP_ID_RE.match(pid or ""):
            e.append("{0}.id must match ^[a-z][a-z0-9_]*$, got {1!r}"
                     .format(tag, pid))
        elif pid in seen:
            e.append("{0}.id {1!r} is duplicated; ids key the per-stamp "
                     "report and must be unique".format(tag, pid))
        else:
            seen.add(pid)

        # Identity is a CONTENT HASH, never a filename or a folder index
        # (RECIPES.md R1, EXTERNAL HEIGHTMAP CATALOGUE SPEC). Names drift
        # singular/plural across the pack tiers; hashes do not.
        h = p.get("stamp_sha256")
        if not isinstance(h, str) or not SHA256_RE.match(h or ""):
            e.append("{0}.stamp_sha256 must be 64 lowercase hex chars "
                     "(the catalogue key), got {1!r}".format(tag, h))

        if not _num_pair(p.get("centre_m")):
            e.append("{0}.centre_m must be [x, y] finite numbers, in WORLD "
                     "metres on the same origin as landscape.location_cm"
                     .format(tag))

        size_m = p.get("size_m")
        if not _is_num(size_m) or size_m <= 0.0:
            e.append("{0}.size_m must be a finite number > 0 (the on-map "
                     "side length the whole stamp spans)".format(tag))

        rot = p.get("rotation_deg")
        if not _is_num(rot) or not 0.0 <= rot < 360.0:
            e.append("{0}.rotation_deg must be a finite number in [0, 360)"
                     .format(tag))

        for key in ("flip_x", "flip_y"):
            if not isinstance(p.get(key), bool):
                e.append("{0}.{1} must be a boolean".format(tag, key))

        blend = p.get("blend")
        if blend not in STAMP_BLENDS:
            e.append("{0}.blend must be one of {1}, got {2!r}"
                     .format(tag, STAMP_BLENDS, blend))

        amp = p.get("amplitude_m")
        if not _is_num(amp) or amp <= 0.0:
            e.append("{0}.amplitude_m must be a finite number > 0 (the "
                     "metres the stamp's full 0..1 value range spans)"
                     .format(tag))

        # Mode-exclusive. Not "optional": present-and-ignored is the
        # failure mode, and it looks exactly like a setting that applied.
        if blend == "ADD":
            if p.get("datum") not in STAMP_DATUMS:
                e.append("{0}.datum must be one of {1} for blend ADD, got "
                         "{2!r}".format(tag, STAMP_DATUMS, p.get("datum")))
            if "anchor_m" in p:
                e.append("{0}.anchor_m is meaningless for blend ADD and "
                         "must be absent; ADD is relative to the base "
                         "surface, not to an absolute elevation"
                         .format(tag))
        elif blend in ("MAX", "MIN", "MASKED"):
            if not _is_num(p.get("anchor_m")):
                e.append("{0}.anchor_m must be a finite number for blend "
                         "{1}: the absolute elevation, heightmap-zero-"
                         "relative in metres, that stamp value 0 sits at"
                         .format(tag, blend))
            if "datum" in p:
                e.append("{0}.datum is meaningless for blend {1} and must "
                         "be absent; {1} compares absolute surfaces, so "
                         "there is nothing to subtract".format(tag, blend))

        f = p.get("falloff")
        if not _is_num(f) or not 0.0 < f <= 1.0:
            e.append("{0}.falloff must be a finite number in (0, 1]: the "
                     "fraction of the half-width over which the mask ramps "
                     "1 -> 0".format(tag))
        if p.get("falloff_shape") not in STAMP_FALLOFF_SHAPES:
            e.append("{0}.falloff_shape must be one of {1}, got {2!r}"
                     .format(tag, STAMP_FALLOFF_SHAPES,
                             p.get("falloff_shape")))

        # v1.15 falloff jitter. Breaks the mask's own geometric symmetry
        # so a euclidean falloff cannot leave a euclidean fingerprint at
        # airship altitude. The bound is 0.5 because the perturbation is
        # ONE-SIDED (r_j = r * (1 + jitter * n01), n01 in [0,1]): it can
        # only pull the zero-contour INWARD, never outward, so the mask
        # stays exactly zero on the geometric footprint and no seam can
        # be produced. Above 0.5 the footprint shrinks enough that the
        # declared size_m stops describing the feature.
        j = p.get("falloff_jitter")
        if not _is_num(j) or not 0.0 <= j <= 0.5:
            e.append("{0}.falloff_jitter must be a finite number in "
                     "[0, 0.5]; 0 means the exact geometric falloff and "
                     "must be stated explicitly, never defaulted"
                     .format(tag))
        js = p.get("falloff_jitter_scale")
        if not _is_num(js) or not 0.0 < js <= 2.0:
            e.append("{0}.falloff_jitter_scale must be a finite number in "
                     "(0, 2]: the noise wavelength in stamp-local units, "
                     "where the stamp spans 2.0. Required even when "
                     "falloff_jitter is 0, so the pair is always a "
                     "complete description".format(tag))

        op = p.get("opacity")
        if not _is_num(op) or not 0.0 < op <= 1.0:
            e.append("{0}.opacity must be a finite number in (0, 1]; 0 "
                     "would be a placement that reports success and does "
                     "nothing".format(tag))
    return e


def _validate_heightmap(hm):
    e = []
    if not isinstance(hm, dict):
        return ["heightmap must be an object"]

    src = hm.get("source")
    if not isinstance(src, str) or not src:
        e.append("heightmap.source must be a non-empty string")
    else:
        # Conduct rule 1: repo-relative only. Reject absolute paths, drive
        # letters, UNC prefixes, and any parent-directory segment.
        if os.path.isabs(src) or re.match(r"^[A-Za-z]:", src) or \
                src.startswith("\\\\") or src.startswith("//"):
            e.append("heightmap.source must be repo-relative, got "
                     "{0!r}".format(src))
        parts = re.split(r"[\\/]+", src)
        if ".." in parts:
            e.append("heightmap.source must not contain a '..' segment")

    if hm.get("format") not in ("png16", "raw16"):
        e.append("heightmap.format must be 'png16' or 'raw16', got "
                 "{0!r}".format(hm.get("format")))

    res = hm.get("resolution")
    ss = hm.get("section_size")
    spc = hm.get("sections_per_component")
    cc = hm.get("component_count")
    for key, val in (("resolution", res), ("section_size", ss),
                     ("sections_per_component", spc),
                     ("component_count", cc)):
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            e.append("heightmap.{0} must be a positive integer".format(key))

    if ss is not None and ss not in LEGAL_SECTION_SIZES:
        e.append("heightmap.section_size must be one of {0}, got "
                 "{1!r}".format(LEGAL_SECTION_SIZES, ss))
    if spc is not None and spc not in LEGAL_SPC:
        e.append("heightmap.sections_per_component must be 1 or 2 (the "
                 "engine-stored integer; the dialog's '2x2 Sections' is 2), "
                 "got {0!r}".format(spc))

    if all(isinstance(v, int) and not isinstance(v, bool) and v > 0
           for v in (res, ss, spc, cc)):
        expected = ss * spc * cc + 1
        if res != expected:
            e.append(
                "heightmap.resolution {0} != section_size*"
                "sections_per_component*component_count+1 = {1}. Nearest "
                "legal resolutions for section_size={2}, "
                "sections_per_component={3}: {4}".format(
                    res, expected, ss, spc,
                    _nearest_legal_resolutions(res, ss, spc)))
    return e


def _nearest_legal_resolutions(res, ss, spc):
    """The two legal resolutions bracketing res, for the error message."""
    step = ss * spc
    if step <= 0:
        return "n/a"
    lower_cc = max(1, (res - 1) // step)
    return ", ".join(str(step * cc + 1) for cc in (lower_cc, lower_cc + 1))


def _validate_landscape(ls):
    e = []
    if not isinstance(ls, dict):
        return ["landscape must be an object"]
    if not isinstance(ls.get("actor_name"), str) or not ls.get("actor_name"):
        e.append("landscape.actor_name must be a non-empty string")
    # schema v1.2, required. Which world a recipe applies to is a scene
    # parameter (hard rule 2). Conduct rule 7 verifies the PROJECT; on
    # 2026-08-01 an unsaved /Temp/Untitled_1 was open inside the correct
    # project and every scene script was operating on the wrong world.
    lvl = ls.get("level_path")
    if not isinstance(lvl, str) or not lvl:
        e.append("landscape.level_path must be a non-empty string "
                 "(required since schema v1.2)")
    elif not lvl.startswith("/Game/"):
        e.append("landscape.level_path must be a content path under "
                 "/Game/, got {0!r}".format(lvl))
    elif lvl.endswith("/"):
        e.append("landscape.level_path must not end with '/', got "
                 "{0!r}".format(lvl))
    if not _num_triple(ls.get("location_cm")):
        e.append("landscape.location_cm must be [x, y, z] numbers")
    if not _is_num(ls.get("scale_xy_cm")) or ls.get("scale_xy_cm", 0) <= 0:
        e.append("landscape.scale_xy_cm must be a positive number")
    if not _is_num(ls.get("z_scale_cm")) or ls.get("z_scale_cm", 0) <= 0:
        e.append("landscape.z_scale_cm must be a positive number")
    return e


_MATERIAL_KEYS = {
    "parent_material", "height_jitter_m", "height_jitter_scale_m",
    "weightmap", "weightmap_feather_sigma_px", "variant_map", "forest_floor",
    "layers", "triplanar", "macro_variation", "displacement", "height_blend",
}

_DISPLACEMENT_KEYS = {"enabled", "center", "per_layer"}

_HEIGHT_BLEND_KEYS = {"k", "eps"}


def _validate_height_blend(hb):
    """Schema v1.28 `material.height_blend` — optional, strict when present.

    HEIGHT-WEIGHTED LAYER BLEND, Brief 7 Phase 1 addendum. The engine's
    LB_HeightBlend has no referent in M_Alpine8K (it is a weightmap
    LinearInterpolate composite, not a LandscapeLayerBlend), so the same
    EFFECT is implemented inside the composite: each STORED layer's mask is
    scaled by its own height sample before the masks are renormalised —

        w_i' = w_i * (h_i + eps) ** k , renormalised to preserve sum(w_i)

    so the higher-elevation surface wins where two stored layers overlap.
    The remainder layer (meadow/Grass) is NOT height-weighted; it keeps
    1 - sum(stored) exactly, because the renormalisation preserves the
    stored total (see make_landscape_material._cpu_height_blend).

    Absent = the composite behaves exactly as before (no reweighting).
    """
    e = []
    if hb is None:
        return e
    if not isinstance(hb, dict):
        return ["material.height_blend must be an object"]
    for k in hb:
        if k.startswith("_"):
            continue
        if k not in _HEIGHT_BLEND_KEYS:
            e.append("unknown key in material.height_blend: {0}".format(k))
    for k in sorted(_HEIGHT_BLEND_KEYS):
        if k not in hb:
            e.append("material.height_blend.{0} is required".format(k))
    if e:
        return e
    kk = hb["k"]
    if not _is_num(kk) or not 0.0 <= kk <= 16.0:
        e.append(
            "material.height_blend.k must be a finite number in [0, 16] "
            "(the height exponent; 0 disables the reweighting, and above "
            "~16 the blend is a hard height-ordered cut that reads as a "
            "stair-step at every layer boundary). Got {0!r}".format(kk))
    eps = hb["eps"]
    if not _is_num(eps) or not 0.0 < eps <= 1.0:
        e.append(
            "material.height_blend.eps must be a finite number in (0, 1] "
            "(added to the height before the power so a zero-height texel "
            "keeps a floor weight instead of vanishing, and so (h+eps)**k "
            "is strictly positive -- the divide-by-zero guard rests on "
            "this). Got {0!r}".format(eps))
    return e


def _validate_displacement(d, layer_names):
    """Schema v1.21 `material.displacement` — optional, strict when present.

    NANITE TESSELLATION DISPLACEMENT. Amplitude is declared in METRES and
    the builder converts it to the engine's unitless `displacement_scaling
    .magnitude`. That direction is deliberate and is the whole point of
    this block existing (non-negotiable: a value can arrive and still mean
    something else — ask in what units, in what space, against what datum).

    THE ENGINE'S UNITS ARE NOT METRES AND NOT CENTIMETRES. Read at the
    source rather than assumed:

      NaniteRasterizationCommon.ush:568
        Displacement = (NormalizedDisplacement - Center) * Magnitude * Fade
      NaniteRasterizationCommon.ush:578
        PointPostDeform += Normal * Displacement
      NaniteRasterizationCommon.ush:588
        PointWorld = mul(float4(PointPostDeform,1), LocalToTranslatedWorld)

    Displacement is added in LOCAL space, BEFORE the local-to-world
    transform. The landscape's Nanite mesh is exported
    `RelativeToProxy` (LandscapeNaniteComponent.cpp:337), which
    LandscapeEdit.cpp:4215-4216 defines as
    `ComponentTransform * ProxyTransform.Inverse()` — so the proxy's
    scale is DIVIDED OUT of the mesh and re-applied by the component.
    On this landscape that scale is [400, 400, 500]
    (`scale_z = z_scale_cm / 512`, landscape_spec.py:35, and the live
    editor reads [400,400,500]).

    So one unit of `magnitude` is FIVE HUNDRED CENTIMETRES of vertical
    movement here, and the ENGINE DEFAULT of 4.0 would displace the
    terrain by +/-10 METRES. Declaring metres and converting once is what
    makes that value unreachable by accident (non-negotiable 3: prefer an
    input that cannot express the catastrophic value over a gate that
    rejects it).

    WHY THE CEILING IS 2 m, AND IT IS NOT AESTHETIC. Nanite displacement
    moves the RENDER surface only; landscape COLLISION continues to come
    from the heightfield, and all 171,069 placed instances are grounded to
    the heightmap. Displacement therefore buys silhouette at the cost of a
    render/collision divergence equal to its own amplitude — the same
    defect CLASS as the 2026-08-06 "renders v2, collides v1" incident,
    deliberately introduced and bounded. The measured collision-vs-
    heightmap quantization already runs p90 0.209 / max 0.716 m, so an
    amplitude at or under ~0.5 m stays inside noise the world already
    carries. 2.0 m is the absurdity guard, not a recommendation.
    """
    e = []
    if d is None:
        return e
    if not isinstance(d, dict):
        return ["material.displacement must be an object"]

    # SCHEMA v1.27 (Brief 7 Phase 1). The single global `amplitude_m` is
    # RETIRED in favour of `per_layer` metres. Refuse the old key
    # explicitly rather than only via the unknown-key gate, so a recipe
    # carried forward from before the bump gets a migration message
    # instead of a bare "unknown key" (rule 10: say plainly what changed).
    if "amplitude_m" in d:
        e.append(
            "material.displacement.amplitude_m is RETIRED (schema v1.27, "
            "Brief 7 Phase 1). Displacement is now PER LAYER: replace it "
            "with `per_layer` — a map of {layer_name: metres} keyed exactly "
            "by material.layers — plus `center` (0.5). The builder uses the "
            "MAX layer as the engine magnitude and scales the others down "
            "in the graph.")

    # Keys prefixed with '_' are documentation, tolerated everywhere in
    # these recipes (e.g. layer `_tiling_derivation`).
    for k in d:
        if k.startswith("_"):
            continue
        if k not in _DISPLACEMENT_KEYS:
            e.append("unknown key in material.displacement: {0}".format(k))
    for k in sorted(_DISPLACEMENT_KEYS):
        if k not in d:
            e.append("material.displacement.{0} is required".format(k))
    if e:
        return e

    if not isinstance(d["enabled"], bool):
        e.append("material.displacement.enabled must be a bool. It is the "
                 "flag that keeps the pre-displacement material path "
                 "reachable, so it may not be truthy-by-accident")

    center = d["center"]
    if not _is_num(center) or not 0.0 <= center <= 1.0:
        e.append("material.displacement.center must be a finite number in "
                 "[0, 1] (the height value that displaces by nothing; the "
                 "graph re-centres every map onto it). Got {0!r}".format(
                     center))

    # PER-LAYER AMPLITUDES. The keys MUST be exactly the material.layers
    # names: a missing layer would silently take ZERO displacement (a flat
    # patch nobody declared), and an extra key is a typo'd layer name that
    # the builder would never apply and no render would explain. Both are
    # the inert-field class the unknown-key gates exist to kill, so the set
    # equality is asserted, not merely a subset check.
    per = d["per_layer"]
    if not isinstance(per, dict) or not per:
        e.append("material.displacement.per_layer must be a non-empty "
                 "object of {layer_name: metres}. Got {0!r}".format(per))
        return e
    want = {n for n in layer_names if isinstance(n, str)}
    got = set(per.keys())
    if got != want:
        missing = sorted(want - got)
        extra = sorted(got - want)
        e.append(
            "material.displacement.per_layer keys must be EXACTLY the "
            "material.layers names {0}. Missing {1}; unexpected {2}. A "
            "missing layer would displace by zero; an extra key names a "
            "layer that does not exist.".format(
                sorted(want), missing, extra))
    for name, amp in sorted(per.items()):
        if not _is_num(amp) or not 0.02 <= amp <= 2.0:
            e.append(
                "material.displacement.per_layer[{0!r}] must be a finite "
                "number in [0.02, 2.0] METRES (peak deviation either side "
                "of the undisplaced surface). Below 0.02 m it is invisible "
                "against the heightmap and is inert config; above 2.0 m it "
                "stops being sub-Nyquist detail and starts inventing "
                "landforms the heightmap cannot represent, while diverging "
                "the rendered surface from the collision instances are "
                "grounded to. Got {1!r}".format(name, amp))
    return e

_MACRO_KEYS = {"seed", "map_resolution", "feature_scale_m", "strength",
               "chroma_ratio"}


def _validate_macro_variation(mv):
    """Schema v1.19 `material.macro_variation` — optional, strict when present.

    Kilometre-scale variation applied ONCE to the composited base colour.
    RULED 2026-08-03: texture-driven, not a Noise node — rejected on the
    engine header's own instruction counts (53-80 ALU per level).
    """
    e = []
    if mv is None:
        return e
    if not isinstance(mv, dict):
        return ["material.macro_variation must be an object"]
    for k in mv:
        if k not in _MACRO_KEYS:
            e.append("unknown key in material.macro_variation: {0}".format(k))
    for k in sorted(_MACRO_KEYS):
        if k not in mv:
            e.append("material.macro_variation.{0} is required".format(k))
    if e:
        return e

    if not isinstance(mv["seed"], int) or isinstance(mv["seed"], bool):
        e.append("material.macro_variation.seed must be an integer; the bake "
                 "must be reproducible (hard pipeline rule 3)")
    if mv["map_resolution"] not in (512, 1024, 2048):
        e.append("material.macro_variation.map_resolution must be 512, 1024 "
                 "or 2048. Below 512 the km features show bilinear diamonds; "
                 "above 2048 is VRAM spent encoding frequencies the existing "
                 "per-layer macro sampling already owns")
    if not _num_pair(mv["feature_scale_m"]):
        e.append("material.macro_variation.feature_scale_m must be a "
                 "[small, large] pair of finite numbers")
    else:
        lo, hi = [float(v) for v in mv["feature_scale_m"]]
        if not lo < hi:
            e.append("material.macro_variation.feature_scale_m must be "
                     "increasing, got [{0}, {1}]".format(lo, hi))
        elif lo < 600.0:
            e.append("material.macro_variation.feature_scale_m lower bound "
                     "{0} m double-counts the existing per-layer macro band "
                     "(188 m / 98.7 m). Two systems fighting over one octave "
                     "reads as mush; keep it >= 600".format(lo))
        elif hi > 4032.0:
            e.append("material.macro_variation.feature_scale_m upper bound "
                     "{0} m exceeds half the terrain span, so fewer than two "
                     "full features fit and it reads as one giant gradient — "
                     "a broken lighting setup, not variation".format(hi))
    st = mv["strength"]
    if not _is_num(st) or not 0.03 <= st <= 0.15:
        e.append("material.macro_variation.strength must be in [0.03, 0.15]. "
                 "Below 0.03 it is invisible at 2 km and the feature is inert "
                 "config; above 0.15 snow reads as dirt bands and rock as "
                 "cloud shadows that never move — a LIGHTING artefact, which "
                 "is worse than the tiling it replaces")
    cr = mv["chroma_ratio"]
    if not _is_num(cr) or not 0.0 <= cr <= 0.5:
        e.append("material.macro_variation.chroma_ratio must be in [0, 0.5]. "
                 "At parity with the value signal the map paints colour "
                 "PATCHES rather than tinting existing colour, which on snow "
                 "reads as vegetation where none exists")
    return e


_TRIPLANAR_KEYS = {"layers", "slope_deg", "sharpness"}


def _validate_triplanar(tp, layer_names):
    """Schema v1.18 `material.triplanar` — optional, strict when present.

    Projects the DETAIL albedo of the named layers from three world planes
    instead of one top-down plane, blended by the absolute world normal,
    faded in over a slope band.

    RULED 2026-08-03 (Fable 5, owner away): detail ALBEDO only. Not the
    macro sample (stretched low-frequency variation does not read as
    smear), not the normal (faded to flat instead, zero fetches), not
    roughness, not displacement. +4 texture fetches on this material
    against +12 for the full variant — and on an integrated GPU that has
    already been lost to a driver timeout, frame cost is a correctness
    concern.
    """
    e = []
    if tp is None:
        return e
    if not isinstance(tp, dict):
        return ["material.triplanar must be an object"]
    for key in tp:
        if key not in _TRIPLANAR_KEYS:
            e.append("unknown key in material.triplanar: {0}".format(key))
    for key in sorted(_TRIPLANAR_KEYS):
        if key not in tp:
            e.append("material.triplanar.{0} is required".format(key))
    if e:
        return e

    ls = tp["layers"]
    if not isinstance(ls, list) or not ls:
        e.append("material.triplanar.layers must be a non-empty array of "
                 "layer names")
    else:
        for nm in ls:
            if nm not in layer_names:
                e.append("material.triplanar.layers names {0!r}, which is "
                         "not a layer in this recipe ({1})".format(
                             nm, sorted(layer_names)))

    if not _num_pair(tp["slope_deg"]):
        e.append("material.triplanar.slope_deg must be a [lo, hi] pair")
    else:
        lo, hi = [float(v) for v in tp["slope_deg"]]
        if not 0.0 <= lo < hi <= 90.0:
            e.append("material.triplanar.slope_deg must satisfy "
                     "0 <= lo < hi <= 90, got [{0}, {1}]".format(lo, hi))

    sh = tp["sharpness"]
    if not _is_num(sh) or not 1.0 <= sh <= 8.0:
        e.append("material.triplanar.sharpness must be a finite number in "
                 "[1, 8]: the exponent on the |world normal| projection "
                 "weights. Below 1 the planes smear into each other; above "
                 "8 the blend becomes a hard seam at every 45-degree edge, "
                 "which is the artefact triplanar exists to remove")
    return e

_SUB_SURFACE_KEYS = {"surface", "height_contrast"}


def _validate_sub_surface(ss, layer_name):
    """Schema v1.14 `layers[].sub_surface` — optional, strict when present.

    The second surface a layer may declare, selected by that layer's
    channel of `material.variant_map` and blended by height.

    `height_contrast` IS BOUNDED IN THIS VALIDATOR AND NOT ONLY IN A
    DOCSTRING, because both ends of the range fail silently:

      contrast = 0  -> `b1 + b2` collapses to zero wherever the two
                       weighted heights are equal, and the blend divides
                       0/0. A NaN through base colour PROPAGATES WITH NO
                       ERROR — the documented recurring class in this
                       project (non-negotiable 1, and the NaN sweep of
                       non-negotiable 4).
      contrast > 1  -> the endpoint guarantee is lost: the blend stops
                       resolving to the primary at t=0, which is the
                       exact defect the `hw` window was added to fix.

    A docstring is documentation where a refusal is a wall.
    """
    e = []
    if ss is None:
        return e
    if not isinstance(ss, dict):
        return ["material.layers[{0!r}].sub_surface must be an object"
                .format(layer_name)]

    tag = "material.layers[{0!r}].sub_surface".format(layer_name)
    for key in ss:
        if key not in _SUB_SURFACE_KEYS:
            e.append("unknown key in {0}: {1}".format(tag, key))
    for key in sorted(_SUB_SURFACE_KEYS):
        if key not in ss:
            e.append("{0}.{1} is required".format(tag, key))
    if e:
        return e

    surf = ss["surface"]
    if surf is not None and (not isinstance(surf, str) or not surf):
        e.append("{0}.surface must be a manifest surface id, or NULL to "
                 "declare the sub-surface path structurally present but "
                 "unbound (the deferred case)".format(tag))

    c = ss["height_contrast"]
    if not _is_num(c) or not 0.0 < c <= 1.0:
        e.append("{0}.height_contrast must be a finite number in (0, 1]: "
                 "0 divides 0/0 in the blend and propagates a NaN through "
                 "base colour with no error; above 1 the blend stops "
                 "resolving to the primary at selector 0".format(tag))
    return e


def _validate_material(mat):
    e = []
    if not isinstance(mat, dict):
        return ["material must be an object"]

    # UNKNOWN-KEY GATE — `world`, `foliage` and `stamps` all had one and
    # `material` did NOT, so a typo'd key was silently ignored. Found
    # 2026-08-03 while adding `variant_map`: the validator accepted
    # `varaint_map` without complaint, which would have left the material
    # building with NO selector map while every check reported success.
    # That is the inert-field class in its purest form — a setting that
    # reads like a setting and is connected to nothing.
    for key in mat:
        if key not in _MATERIAL_KEYS:
            e.append("unknown top-level key in material: {0!r}. A typo "
                     "here is silent: the intended key is simply absent "
                     "and the material builds without it".format(key))

    pm = mat.get("parent_material")
    if not isinstance(pm, str) or not pm.startswith("/"):
        e.append("material.parent_material must be a content-browser path "
                 "starting with '/', got {0!r}".format(pm))
    # v1.5, both optional. Applied ONCE to the elevation the height bands
    # are tested against, so every boundary wanders together rather than
    # each band drifting independently and opening a seam.
    if "height_jitter_m" in mat:
        v = mat["height_jitter_m"]
        if not _is_num(v) or not 0.0 <= v <= 500.0:
            e.append("material.height_jitter_m must be a finite number in "
                     "[0, 500], got {0!r}".format(v))
    if "height_jitter_scale_m" in mat:
        v = mat["height_jitter_scale_m"]
        if not _is_num(v) or not 10.0 <= v <= 20000.0:
            e.append("material.height_jitter_scale_m must be a finite "
                     "number in [10, 20000], got {0!r}".format(v))

    # v1.29 (Brief 7 Phase 1). The weightmap bake feathers its stored channels
    # by a Gaussian of `weightmap_feather_sigma_px` TEXELS. REQUIRED for the
    # >=4-channel (five-layer expand) stored-weightmap contract that alpine_8k
    # uses: the near-binary un-feathered bake shattered the terrain into ~1 m
    # blocks (research/brief7/p1_block_diff.md), so an ABSENT field is the
    # retired argmax path and must refuse rather than run silently. SCOPED to
    # >= 4 layers: the legacy 3-layer RGB world (recipes/alpine.json) is baked
    # by a different pipeline (make_layer_weightmap) with no feather stage and
    # reads no such field, so requiring it there would be prose (rule 12). Range
    # is validated whenever the field is present, and it is inert without a
    # weightmap.
    _fl = mat.get("layers")
    _nlayers = len(_fl) if isinstance(_fl, list) else 0
    if "weightmap_feather_sigma_px" in mat:
        v = mat["weightmap_feather_sigma_px"]
        if not _is_num(v) or not 0.0 < v <= 8.0:
            e.append(
                "material.weightmap_feather_sigma_px must be a finite number "
                "in (0, 8] texels (1 texel == 1 m here; 0 is the retired "
                "un-feathered path, above ~8 the ramps are wider than the "
                "layers they blend). Got {0!r}".format(v))
        if mat.get("weightmap") is None:
            e.append(
                "material.weightmap_feather_sigma_px is set but "
                "material.weightmap is not: the feather acts on the baked "
                "weightmap channels, so with no weightmap it is inert. Remove "
                "the field or add a weightmap.")
    elif mat.get("weightmap") is not None and _nlayers >= 4:
        e.append(
            "material.weightmap_feather_sigma_px is required for a "
            ">= 4-layer weightmap (the five-layer expand contract). Its "
            "absence is the RETIRED near-binary bake that shatters the terrain "
            "into ~1 m blocks (research/brief7/p1_block_diff.md); set it "
            "(1.5 gives ~3 m boundary cross-fades) rather than let the "
            "un-feathered path run silently.")

    layers = mat.get("layers")
    if not isinstance(layers, list) or not layers:
        return e + ["material.layers must be a non-empty array"]
    e.extend(_validate_macro_variation(mat.get("macro_variation")))
    e.extend(_validate_displacement(
        mat.get("displacement"),
        [l.get("name") for l in layers if isinstance(l, dict)]))
    e.extend(_validate_height_blend(mat.get("height_blend")))
    # CROSS-FIELD (schema v1.28, Brief 7 Phase 1 addendum). height_blend
    # reweights the STORED WEIGHTMAP channels, so it is meaningless without
    # a weightmap and would be a silent no-op (the builder consumes it only
    # inside its `if _weightmap:` branch). Refuse rather than let an inert
    # field read as controlling (standing rule 12 / the sub_surface pattern
    # that folds weightmap into its predicate).
    if mat.get("height_blend") is not None and not mat.get("weightmap"):
        e.append(
            "material.height_blend requires material.weightmap: the "
            "reweighting acts on the baked weightmap channels, and with no "
            "weightmap it is a silent no-op (the fallback slope/height-band "
            "masks are not reweighted). Remove height_blend or add a "
            "weightmap.")
    # CROSS-FIELD. height_blend samples each STORED layer's height ONCE at
    # mask build and reuses it as that band's displacement/HeightLerp
    # sample; that sample carries PLAIN UVs, but a stochastic_tiling layer's
    # other maps are sampled through per-cell SHIFTED UVs -- reusing the
    # unshifted height would misregister relief against albedo/normal with
    # no error. Refuse the combination, the same way the builder already
    # refuses triplanar x stochastic. Only the STORED layers are reweighted
    # (the builder does `for _i in range(_direct)`, _direct = min(layers,
    # weightmap channels)); the DERIVED remainder is sampled fresh in-loop
    # with its own stochastic UVs, so stochastic on it is safe. Scope the
    # check to the stored layers via the builder's own channel count, so a
    # remainder layer is not falsely refused (cloud review, 2026-09-23) and
    # a no-remainder recipe -- forge's 3 layers over 4 channels -- still has
    # every layer checked.
    if mat.get("height_blend") is not None:
        from make_landscape_material import WEIGHTMAP_CHANNELS  # deferred
        stored = min(len(layers), len(WEIGHTMAP_CHANNELS))
        for i, layer in enumerate(layers[:stored]):
            if isinstance(layer, dict) and layer.get("stochastic_tiling"):
                e.append(
                    "material.layers[{0}] ({1}) declares stochastic_tiling "
                    "AND material.height_blend is on: the height-blend "
                    "reuses a PLAIN-UV height sample that a stochastic "
                    "layer's shifted-UV maps do not share, which "
                    "misregisters relief against the surface. Drop one on "
                    "this layer.".format(i, layer.get("name")))
    e.extend(_validate_triplanar(
        mat.get("triplanar"),
        {l.get("name") for l in layers if isinstance(l, dict)}))

    seen = set()
    for i, layer in enumerate(layers):
        tag = "material.layers[{0}]".format(i)
        if not isinstance(layer, dict):
            e.append("{0} must be an object".format(tag))
            continue
        name = layer.get("name")
        if not isinstance(name, str) or not name:
            e.append("{0}.name must be a non-empty string".format(tag))
        elif name in seen:
            # Duplicate names break idempotency: two layer infos would
            # compete for the same deterministic asset name (hard rule 3).
            e.append("{0}.name {1!r} is duplicated".format(tag, name))
        else:
            seen.add(name)

        e.extend(_validate_sub_surface(
            layer.get("sub_surface"),
            name if isinstance(name, str) and name else i))

        for key, lo, hi in (("slope_deg", 0.0, 90.0),):
            rng = layer.get(key)
            if not _num_pair(rng):
                e.append("{0}.{1} must be [min, max]".format(tag, key))
            elif not (lo <= rng[0] <= hi and lo <= rng[1] <= hi):
                e.append("{0}.{1} must lie within [{2}, {3}]".format(
                    tag, key, lo, hi))
            elif rng[0] > rng[1]:
                e.append("{0}.{1} min exceeds max".format(tag, key))

        hm_rng = layer.get("height_m")
        if not _num_pair(hm_rng):
            e.append("{0}.height_m must be [min, max]".format(tag))
        elif hm_rng[0] > hm_rng[1]:
            e.append("{0}.height_m min exceeds max".format(tag))

        # Appearance (schema v1.1). base_color and roughness are required;
        # texture is an optional repo-relative source override.
        bc = layer.get("base_color")
        if not (isinstance(bc, list) and len(bc) == 3
                and all(_is_num(c) and 0.0 <= c <= 1.0 for c in bc)):
            e.append("{0}.base_color must be [r, g, b], each 0-1 "
                     "(required since schema v1.1)".format(tag))
        rough = layer.get("roughness")
        if not _is_num(rough) or not (0.0 <= rough <= 1.0):
            e.append("{0}.roughness must be a number in [0, 1] "
                     "(required since schema v1.1)".format(tag))
        tex = layer.get("texture")
        if tex is not None:
            if not isinstance(tex, str) or not tex:
                e.append("{0}.texture, when present, must be a non-empty "
                         "repo-relative source path".format(tag))
            elif os.path.isabs(tex) or re.match(r"^[A-Za-z]:", tex) or \
                    ".." in re.split(r"[\\/]+", tex):
                e.append("{0}.texture must be repo-relative with no '..' "
                         "segment (conduct rule 1), got {1!r}".format(
                             tag, tex))

        bs = layer.get("blend_sharpness")
        if not _is_num(bs) or not (0.0 <= bs <= 1.0):
            e.append("{0}.blend_sharpness must be a number in [0, 1]".format(
                tag))
        tm = layer.get("tiling_m")
        if not _is_num(tm) or tm <= 0:
            e.append("{0}.tiling_m must be a positive number".format(tag))

        # schema v1.2. Optional; only meaningful alongside `texture`.
        # Validated even though unknown layer keys are not rejected,
        # because a typo'd or negative value would otherwise reach a
        # shader divisor.
        mtm = layer.get("macro_tiling_m")
        if mtm is not None:
            if not _is_num(mtm) or mtm <= 0:
                e.append("{0}.macro_tiling_m, when present, must be a "
                         "positive number".format(tag))
            elif tex is None:
                e.append("{0}.macro_tiling_m is set but `texture` is not; "
                         "it has nothing to scale (schema v1.2)".format(tag))
            elif _is_num(tm) and mtm <= tm:
                e.append("{0}.macro_tiling_m ({1}) must exceed tiling_m "
                         "({2}) - the macro scale is the one that survives "
                         "mipping at distance; inverting them silently "
                         "removes all visible variation".format(
                             tag, mtm, tm))
    return e


def _validate_lighting(lt):
    e = []
    if not isinstance(lt, dict):
        return ["lighting must be an object"]

    sun = lt.get("sun")
    if not isinstance(sun, dict):
        e.append("lighting.sun must be an object")
    else:
        for key, lo, hi in (("elevation_deg", -90.0, 90.0),
                            ("azimuth_deg", 0.0, 360.0),
                            ("temperature_kelvin", 1700.0, 12000.0)):
            v = sun.get(key)
            if not _is_num(v):
                e.append("lighting.sun.{0} must be a number".format(key))
            elif not (lo <= v <= hi):
                e.append("lighting.sun.{0} must lie within [{1}, {2}], got "
                         "{3}".format(key, lo, hi, v))
        _lux = sun.get("intensity_lux")
        if not _is_num(_lux):
            e.append("lighting.sun.intensity_lux must be a number")
        elif not 100000.0 <= float(_lux) <= 160000.0:
            e.append(
                "lighting.sun.intensity_lux must be in [100000, 160000]. "
                "`apply_lighting.py:260` sets `atmosphere_sun_light = True` "
                "UNCONDITIONALLY, and DirectionalLightComponent.cpp:601-615 "
                "then treats `intensity` as TOP-OF-ATMOSPHERE illuminance "
                "and attenuates it by the atmosphere before it reaches a "
                "surface. So this field is the luminous solar constant "
                "(126,000-134,000 lux), NOT a ground-level reading. Feeding "
                "it a ground number attenuates twice: 18000 here delivered "
                "8,288 lux green normal-to-sun where the physical value at "
                "12 degrees elevation is 49,000-60,000, and every frame came "
                "back dark. To make a scene dimmer, change "
                "`exposure.compensation_ev` — that is what it is for. "
                "Verify with `python scripts/atmosphere_solve.py`. "
                "Got {0}".format(_lux))
        if not isinstance(sun.get("light_shaft_bloom"), bool):
            e.append("lighting.sun.light_shaft_bloom must be a bool")

    sky = lt.get("sky")
    if not isinstance(sky, dict):
        e.append("lighting.sky must be an object")
    else:
        if sky.get("type") not in ("hdri", "physical"):
            e.append("lighting.sky.type must be 'hdri' or 'physical'")
        if sky.get("type") == "hdri" and not isinstance(
                sky.get("hdri_path"), str):
            e.append("lighting.sky.hdri_path is required when type is 'hdri'")
        if not _is_num(sky.get("intensity")):
            e.append("lighting.sky.intensity must be a number")
        sky_col = sky.get("color")
        if sky_col is not None and not (
                isinstance(sky_col, list) and len(sky_col) == 3
                and all(_is_num(c) and 0.0 <= c <= 1.0 for c in sky_col)):
            e.append("lighting.sky.color, when present, must be [r, g, b] "
                     "linear values each in [0, 1]")

    fog = lt.get("fog")
    if not isinstance(fog, dict):
        e.append("lighting.fog must be an object")
    else:
        for key in ("enabled", "volumetric"):
            if not isinstance(fog.get(key), bool):
                e.append("lighting.fog.{0} must be a bool".format(key))
        # schema v1.4: `height_falloff` (an opaque engine number that
        # silently meant a 58 m half-height) is replaced by
        # `half_height_m`, and `height_datum_m` is added because the fog's
        # world Z decides which of a world is buried and which is clear
        # and was previously governed by nothing at all.
        for key in ("density", "half_height_m", "height_datum_m",
                    "start_distance_m"):
            if not _is_num(fog.get(key)):
                e.append("lighting.fog.{0} must be a number".format(key))
        if _is_num(fog.get("half_height_m")) and fog["half_height_m"] <= 0:
            e.append("lighting.fog.half_height_m must be > 0 — it is the "
                     "height over which fog density halves")
        if "height_falloff" in fog:
            e.append("lighting.fog.height_falloff was REMOVED in schema "
                     "v1.4. It was the engine's raw number, divided by "
                     "1000 before use (SceneCore.cpp:405), so the "
                     "long-standing 0.12 meant a 58 m half-height — a "
                     "near-vertical wall of fog nobody intended. Use "
                     "half_height_m, in metres.")

    exp = lt.get("exposure")
    if not isinstance(exp, dict):
        e.append("lighting.exposure must be an object")
    else:
        if exp.get("method") not in ("manual", "auto_histogram"):
            e.append("lighting.exposure.method must be 'manual' or "
                     "'auto_histogram'")
        if not _is_num(exp.get("compensation_ev")):
            e.append("lighting.exposure.compensation_ev must be a number")

    # schema v1.5 (Brief 2 Task 6, 2026-09-10): one VolumetricCloud layer.
    # OPTIONAL block — absent means no clouds and apply_lighting expects
    # zero cloud actors of ours.
    cl = lt.get("clouds")
    if cl is not None:
        if not isinstance(cl, dict):
            e.append("lighting.clouds must be an object")
        else:
            if not isinstance(cl.get("enabled"), bool):
                e.append("lighting.clouds.enabled must be a bool")
            for key in ("material_parent", "material_instance",
                        "coverage_param"):
                if not isinstance(cl.get(key), str) or not cl.get(key):
                    e.append("lighting.clouds.{0} must be a non-empty "
                             "string".format(key))
            mi = cl.get("material_instance")
            if isinstance(mi, str) and not mi.startswith("/Game/"):
                e.append("lighting.clouds.material_instance must live under "
                         "/Game/ — the coverage override must NOT be "
                         "written to engine content (standing rule 1); "
                         "got {0!r}".format(mi))
            for key, lo, hi in (("coverage", 0.0, 1.0),
                                ("layer_bottom_km", 0.0, 20.0),
                                ("layer_height_km", 0.1, 20.0)):
                v = cl.get(key)
                if not _is_num(v):
                    e.append("lighting.clouds.{0} must be a number"
                             .format(key))
                elif not (lo <= v <= hi):
                    e.append("lighting.clouds.{0} must lie within "
                             "[{1}, {2}], got {3}".format(key, lo, hi, v))
    return e


def _validate_capture(cap):
    e = []
    if not isinstance(cap, dict):
        return ["capture must be an object"]

    out = cap.get("output_dir")
    if not isinstance(out, str) or not out:
        e.append("capture.output_dir must be a non-empty string")
    else:
        captures_root = bootstrap._norm(os.path.join(REPO_ROOT, "captures"))
        resolved = bootstrap._norm(os.path.join(REPO_ROOT, out))
        if resolved != captures_root and not resolved.startswith(
                captures_root + os.sep):
            e.append("capture.output_dir must resolve inside captures/, "
                     "got {0!r}".format(out))

    res = cap.get("resolution")
    if not (isinstance(res, list) and len(res) == 2 and
            all(isinstance(x, int) and not isinstance(x, bool) and x > 0
                for x in res)):
        e.append("capture.resolution must be [width, height] positive ints")

    cams = cap.get("cameras")
    if not isinstance(cams, list) or not cams:
        return e + ["capture.cameras must be a non-empty array"]
    seen = set()
    for i, cam in enumerate(cams):
        tag = "capture.cameras[{0}]".format(i)
        if not isinstance(cam, dict):
            e.append("{0} must be an object".format(tag))
            continue
        name = cam.get("name")
        if not isinstance(name, str) or not name:
            e.append("{0}.name must be a non-empty string".format(tag))
        elif name in seen:
            # Duplicate camera names would collide on capture filenames and
            # break deterministic re-runs (hard rule 3).
            e.append("{0}.name {1!r} is duplicated".format(tag, name))
        else:
            seen.add(name)
        if not _num_triple(cam.get("location_cm")):
            e.append("{0}.location_cm must be [x, y, z] numbers".format(tag))
        if not _num_triple(cam.get("rotation_deg")):
            e.append("{0}.rotation_deg must be [pitch, yaw, roll] "
                     "numbers".format(tag))
        if not _is_num(cam.get("fov_deg")):
            e.append("{0}.fov_deg must be a number".format(tag))
    return e


# ------------------------------------------------------------- heightmap --

def _read_png_header(path):
    """Return (width, height, bit_depth, colour_type) from a PNG IHDR.

    Reads only the first 26 bytes. Raises ValueError if the file is not a
    PNG or the IHDR chunk is not where the spec requires.
    """
    with open(path, "rb") as fh:
        head = fh.read(26)
    if len(head) < 26 or head[:8] != PNG_SIGNATURE:
        raise ValueError("not a PNG file (signature mismatch)")
    if head[12:16] != b"IHDR":
        raise ValueError("malformed PNG: first chunk is not IHDR")
    width, height = struct.unpack(">II", head[16:24])
    return width, height, head[24], head[25]


def _validate_heightmap_file(hm):
    """Check the source file exists and matches the recipe. Returns errors."""
    e = []
    src = hm.get("source")
    path = os.path.join(REPO_ROOT, src)
    declared = hm.get("resolution")

    if not os.path.isfile(path):
        return ["heightmap source not found: {0}\n"
                "  (schema v1 has no 'pending export' marker — the Gaea "
                "export must exist before import)".format(path)]

    if hm.get("format") == "png16":
        try:
            width, height, bit_depth, colour_type = _read_png_header(path)
        except (OSError, ValueError) as exc:
            return ["cannot read PNG header from {0}: {1}".format(path, exc)]
        if bit_depth != 16:
            e.append("heightmap.format is 'png16' but {0} has bit depth "
                     "{1}. 8-bit sources band visibly on slopes and are "
                     "rejected by schema v1.".format(path, bit_depth))
        if colour_type != 0:
            e.append("heightmap PNG colour type is {0}; expected 0 "
                     "(greyscale) for a heightmap.".format(colour_type))
        if width != height:
            e.append("heightmap must be square, got {0}x{1}".format(
                width, height))
        if width != declared or height != declared:
            e.append("heightmap.resolution is {0} but the file is {1}x{2}. "
                     "Unreal would resample on import and the result stops "
                     "being deterministic.".format(declared, width, height))
    else:  # raw16
        expected_bytes = declared * declared * 2
        actual = os.path.getsize(path)
        if actual != expected_bytes:
            e.append("raw16 heightmap should be {0} bytes for resolution "
                     "{1} ({1}^2 * 2), but {2} is {3} bytes".format(
                         expected_bytes, declared, path, actual))
    return e


# ----------------------------------------------------------- editor gate --

def _parse_probe(text, marker):
    idx = text.find(marker)
    if idx < 0:
        return None
    tail = text[idx + len(marker):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run_probe(remote_exec, remote, node_id, source):
    """Run one read-only probe on an ALREADY-VERIFIED node."""
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  probe connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        result = remote.run_command(source, unattended=True,
                                    exec_mode=remote_exec.MODE_EXEC_FILE)
        if not result or not result.get("success"):
            print("  probe did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        return _parse_probe(bootstrap._collect_output(result), PROBE_MARKER)
    except Exception as exc:
        print("  probe errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _select_verified_node(remote_exec, remote, expected, timeout):
    """Conduct rule 7 gate. Returns (node, reason, exit_code).

    NOTE FOR AUDIT: this mirrors the classification loop in
    bootstrap.main(). It reuses bootstrap's primitives (_norm, _discover,
    _describe, _collect_output) but duplicates the decision logic, because
    bootstrap.py exposes no reusable selection function and modifying that
    file would require re-auditing a signed-off script. Extracting a shared
    select_verified_node() into bootstrap.py is the correct fix and is a
    design decision for Ryan, not something to do unilaterally.
    """
    nodes = bootstrap._discover(remote, timeout)
    if not nodes:
        return None, "no editor nodes answered discovery", 4

    matches, malformed = [], []
    for node in nodes:
        raw = node.get("project_root")
        if raw is None:
            status = "no project loaded"
        elif not isinstance(raw, str) or not os.path.isabs(raw):
            malformed.append(node)
            status = "MALFORMED project_root: {0!r}".format(raw)
        elif bootstrap._norm(raw) == expected:
            matches.append(node)
            status = "MATCH -> {0}".format(raw)
        else:
            status = "other project -> {0}".format(raw)
        print("  - {0}: {1}".format(bootstrap._describe(node), status))

    if malformed:
        return None, "{0} node(s) reported an unparseable project path".format(
            len(malformed)), 4
    if not matches:
        return None, "no reachable editor has UE_PROJECT_ROOT open", 4
    if len(matches) > 1:
        return None, "{0} editors claim UE_PROJECT_ROOT — ambiguous".format(
            len(matches)), 4

    node = matches[0]
    info = bootstrap._confirm(remote_exec, remote, node["node_id"])
    if not info or not info.get("project_dir"):
        return None, "could not confirm the selected editor's project", 4
    if bootstrap._norm(info["project_dir"]) != expected:
        return None, "editor reported {0}, not UE_PROJECT_ROOT".format(
            info["project_dir"]), 4
    return node, None, 0


def _preflight_source(recipe):
    """Read-only preflight, run only against the verified node."""
    return """
import json as _json
import unreal as _unreal

_parent = {parent!r}
_actor_name = {actor!r}

_found = []
# UnrealEditorSubsystem is the 5.0+ home of get_editor_world; the old
# EditorLevelLibrary.get_editor_world is deprecated across UE5.
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()
for _a in _unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.Landscape):
    _found.append(_a.get_actor_label())

print("{marker}" + _json.dumps({{
    "engine_version": _unreal.SystemLibrary.get_engine_version(),
    "parent_material_exists": _unreal.EditorAssetLibrary.does_asset_exist(
        _parent),
    "landscape_actor_labels": _found,
    "target_actor_present": _actor_name in _found,
}}))
""".format(parent=recipe["material"]["parent_material"],
           actor=recipe["landscape"]["actor_name"],
           marker=PROBE_MARKER)


# ------------------------------------------------------------------ main --

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE,
                        help="Path to the recipe JSON (default: "
                             "recipes/alpine.json).")
    parser.add_argument("--timeout", type=float, default=6.0,
                        help="Editor discovery window in seconds.")
    parser.add_argument("--offline", action="store_true",
                        help="Run recipe and heightmap validation only; "
                             "contact no editor.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe_path = os.path.abspath(args.recipe)
    print("REPO_ROOT        : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT  : {0}".format(bootstrap.UE_PROJECT_ROOT))
    print("Recipe           : {0}".format(recipe_path))
    print("")

    # Conduct rule 1: never read a recipe from outside the repo.
    if bootstrap._norm(recipe_path) != bootstrap._norm(REPO_ROOT) and \
            not bootstrap._norm(recipe_path).startswith(
                bootstrap._norm(REPO_ROOT) + os.sep):
        print("REFUSE: recipe must live inside REPO_ROOT.")
        return 1
    if not os.path.isfile(recipe_path):
        print("REFUSE: recipe not found: {0}".format(recipe_path))
        return 2

    try:
        with open(recipe_path, "r", encoding="utf-8") as fh:
            recipe = json.load(fh)
    except (OSError, ValueError) as exc:
        print("REFUSE: cannot parse recipe: {0}: {1}".format(
            type(exc).__name__, exc))
        return 2

    print("--- recipe validation (schema v1) ---")
    errors = _validate_recipe(recipe, recipe_path)
    if errors:
        for err in errors:
            print("  INVALID: {0}".format(err))
        print("\nREFUSE: recipe does not conform to schema v1.")
        return 2
    print("  OK — {0} ({1})".format(recipe["display_name"],
                                    recipe["biome_id"]))

    print("")
    print("--- heightmap validation ---")
    hm_errors = _validate_heightmap_file(recipe["heightmap"])
    if hm_errors:
        for err in hm_errors:
            print("  INVALID: {0}".format(err))
        print("\nREFUSE: heightmap source unusable.")
        return 3
    print("  OK — {0} ({1}, {2}px)".format(
        recipe["heightmap"]["source"], recipe["heightmap"]["format"],
        recipe["heightmap"]["resolution"]))

    if args.offline:
        print("\n--offline: skipping editor checks. Recipe and heightmap "
              "are valid.")
        return 0

    print("")
    print("--- editor identity gate (conduct rule 7) ---")
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason, code = _select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("\nREFUSE (rule 7): {0}. Not executing.".format(reason))
            return code
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))

        print("")
        print("--- engine version gate ---")
        info = _run_probe(remote_exec, remote, node["node_id"],
                          _preflight_source(recipe))
        if not info:
            print("\nREFUSE: preflight probe returned nothing.")
            return 6

        target = recipe["engine"]["target_version"]
        actual_full = info.get("engine_version", "")
        actual_mm = ".".join(actual_full.split(".")[:2])
        on_mismatch = recipe["engine"].get("on_version_mismatch", "abort")
        print("  recipe targets {0}; editor reports {1}".format(
            target, actual_full))
        if actual_mm != target:
            if on_mismatch == "abort":
                print("\nREFUSE: engine major.minor {0} != recipe target "
                      "{1}.".format(actual_mm, target))
                return 5
            print("  WARNING: version mismatch, continuing per recipe.")

        print("")
        print("--- in-editor preflight (read-only) ---")
        parent = recipe["material"]["parent_material"]
        if not info.get("parent_material_exists"):
            print("  MISSING: {0} does not exist in the content browser.".
                  format(parent))
            print("  Schema v1 requires the parent material to already "
                  "exist; scripts never author materials on disk "
                  "(conduct rule 4).")
            print("\nREFUSE: parent material absent.")
            return 6
        print("  parent material present: {0}".format(parent))

        actor_name = recipe["landscape"]["actor_name"]
        if info.get("target_actor_present"):
            print("  landscape {0!r} already exists — a re-run must update "
                  "it in place, not spawn a duplicate (hard rule "
                  "3).".format(actor_name))
        else:
            print("  landscape {0!r} not present — first import.".format(
                actor_name))

        print("")
        print("=" * 68)
        print("REFUSED: import step not implemented (exit 7).")
        print("")
        print("UE 5.8 exposes no script-callable API that builds a landscape")
        print("from a heightmap FILE. The only BlueprintCallable heightmap")
        print("import is LandscapeProxy.LandscapeImportHeightmapFromRender")
        print("Target (LandscapeProxy.h:1572), which needs a render target")
        print("AND a landscape that already exists with valid extents.")
        print("Engine/Source/Editor/LandscapeEditor exposes no Blueprint")
        print("Callable functions at all, and ALandscape has no exposed")
        print("Import().")
        print("")
        print("Choosing a route is a design decision — see the report to")
        print("Ryan. Nothing has been imported and the scene is unchanged.")
        print("=" * 68)
        return 7
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
