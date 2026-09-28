"""landscape_spec.py — print the exact New Landscape dialog values.

Step 1 of the route-B bracket (see LESSONS.md, "Import route").
UE 5.8 exposes no script-callable API that builds a landscape from a
heightmap file, so the landscape is created by hand exactly once. This
script removes the guesswork from that step: it derives every dialog
field from recipe geometry and prints it, so nothing is typed from
memory or inferred.

LOCAL ONLY. No editor contact, no remote execution, no writes of any
kind. It reads one recipe and prints.

The bracket:
  1. THIS SCRIPT           — prints the spec
  2. manual creation       — Ryan, once, from the printout
  3. verify_landscape.py   — reads the live landscape and compares it
                             back against this same derivation, exiting
                             non-zero on any mismatch

Both ends derive from the same recipe through the same functions
(derive_spec below, imported by the verifier), so the printout and the
check can never drift apart. That is the point: a hand-made landscape
stops being undocumented state and becomes verified state.

GEOMETRY NOTES (all verified in engine source)
- `sections_per_component` is the integer Unreal stores, NOT the dialog
  label. The dialog shows "2x2 Sections"; the stored value is 2.
  FLandscapeConfig::NumSectionValues[2] = { 1, 2 }
  (LandscapeConfigHelper.cpp:24), used linearly as
  QuadsPerComponent = SectionsPerComponent * QuadsPerSection
  (LandscapeEditorDetailCustomization_NewLandscape.cpp:1185).
- Z scale: LANDSCAPE_ZSCALE = 1/128 (LandscapeDataAccess.h:13), so the
  full 16-bit range spans 65536/128 = 512 world units. At an actor Z
  scale of S (the dialog's number, where 100 means 1.0), the full range
  is 512 * S centimetres. Hence scale_z = z_scale_cm / 512.
- Location: the dialog's Location field is the landscape's CENTRE, not
  the actor origin. The actor is placed at dialog_location + offset,
  where offset = -(component_count * quads_per_component / 2) * scale
  (LandscapeEditorDetailCustomization_NewLandscape.cpp:1219).
  `landscape.location_cm` is defined by schema.md as the actor origin,
  so the printed dialog value is pre-compensated by +offset.
  This was found the hard way: the first printout fed location_cm
  straight into the dialog and the actor landed at -403200, -403200.

Exit codes:
  0  spec printed
  1  unexpected error / bad arguments / recipe outside REPO_ROOT
  2  recipe missing, unparseable, or geometrically illegal
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

LEGAL_SECTION_SIZES = (7, 15, 31, 63, 127, 255)
LEGAL_SPC = (1, 2)

# Content-browser destination for imported layer textures (schema v1.2).
TEXTURE_CONTENT_DIR = "/Game/Textures"


# ---------------------------------------------------------------------
# PIVOT NORMALISATION — the recipe side of the contract (RULING C,
# Ryan, 2026-08-02; LESSONS.md and RECIPES.md)
#
# Ruling (c): a mesh a RECIPE names must be imported from a
# pivot-normalised source. Ad-hoc vendor imports stay ungated, because
# importing a vendor file to MEASURE it is legitimate and the importer
# cannot tell the two apart on its own — but the recipe can, because the
# recipe is what decides whether something gets instanced.
#
# These helpers live here rather than in the importer because FOUR
# scripts now need the same answer (the recipe validator, the importer,
# the foliage placer and the material builder's grass path), and section
# 1.9 says one copy decides. landscape_spec imports nothing, so putting
# them here cannot create a cycle.
#
# WHY THIS IS NOT SUFFICIENT ON ITS OWN, stated plainly: everything
# below is a NAME check against a report on disk. It cannot see the
# pivot on the actual asset, so it is defeated by importing a vendor
# file under a name that happens to match a verified object. The
# check that cannot be fooled is the read-back of get_bounds() at the
# point of USE — place_foliage and the grass builder — and both do it.
# This layer exists to refuse early and cheaply, not to be the proof.

NORMALIZED_REPORT = os.path.join(
    REPO_ROOT, "Free", "_measured", "normalized.json")

# SECOND PROVENANCE PATH, added 2026-08-15. Same contract, different origin.
#
# `normalized.json` is the Blender tool's output and can only ever describe
# meshes that came in through `scripts/blender/normalize_asset.py`. A mesh
# this pipeline PRODUCES ITSELF -- the Megaplants conifers exported from the
# Procedural Vegetation editor as Static Meshes -- has no FBX and can never
# have a row there, so the early gate refused eight assets whose pivots were
# already measured and well inside the contract.
#
# THIS IS NOT A HOLE, AND THE REASON IS THE COMMENT DIRECTLY ABOVE: this
# layer "exists to refuse early and cheaply, not to be the proof". The check
# that cannot be fooled is the `get_bounds()` read-back at the point of USE,
# which place_foliage.py performs against the live mesh (search get_bounds;
# line numbers drift — a :959 citation here had already gone stale once) and
# which is untouched by this. Registering an engine-derived mesh here changes WHICH
# cheap pre-check it passes; it does not change what must be true of it.
#
# Rows carry the same shape plus an explicit `provenance` string, so a reader
# can always tell a Blender-normalised asset from a pipeline-produced one.
ENGINE_DERIVED_REPORT = os.path.join(
    REPO_ROOT, "Free", "_measured", "engine_derived.json")

# Maximum horizontal pivot-to-geometry distance, metres. Generous on
# purpose: the defect being guarded against was 12.406 m, and a real
# asset can legitimately carry tens of centimetres of asymmetry (the
# unrotated fir_tree_01_a measures 0.331 m and is FINE).
MAX_PIVOT_OFFSET_M = 1.0

# VERTICAL half of the same contract (audit finding F5, ruled by the
# implementer 2026-08-02 under the standing autonomy grant; Ryan's
# ruling (c) settled WHEN normalisation is mandatory, not WHAT counts as
# normalised).
#
# normalize_asset.py puts the pivot at the bounding-box MINIMUM in z, so
# `origin.z - box_extent.z` is 0 for a correctly normalised mesh, and the
# FBX round-trip preserved that to 3 micrometres across all 23 objects.
# A mesh pivoted at its bounding-box CENTRE instead reports minus half
# its height — for fir_tree_01_c that is -7.26 m, and every instance
# would be buried to the waist or floating, depending on sign.
#
# 0.25 m absolute, not proportional: the quantity is a distance from the
# ground plane and does not scale with the object. A 0.05 m grass tuft
# and a 14.5 m fir both want their base at zero.
MAX_BASE_OFFSET_M = 0.25


def verified_normalized_objects(report_path=None):
    """{object_name: row} for every object recorded as verified.

    Returns an EMPTY DICT only when the report genuinely lists no
    verified objects. A missing or malformed report RAISES, because a
    caller that treated "I could not read the report" as "nothing is
    verified" would refuse everything, and a caller that treated it as
    "everything is fine" would refuse nothing — both wrong, and the
    second one silently (section 2.10).
    """
    path = report_path or NORMALIZED_REPORT
    if not os.path.isfile(path):
        raise ValueError(
            "no normalisation report at {0} — run "
            "scripts/blender/normalize_asset.py".format(path))
    with open(path, "r", encoding="utf-8") as fh:
        report = json.load(fh)
    if not isinstance(report, dict):
        raise ValueError(
            "normalisation report top level is {0}, expected a dict of "
            "groups".format(type(report).__name__))
    out = {}
    rows = 0
    for group in report.values():
        if not isinstance(group, dict):
            continue
        # isinstance, not truthiness: a malformed report with e.g.
        # "objects": 5 would raise TypeError here, which escapes the
        # (OSError, ValueError) net every caller of this module casts
        # and turns a clean REFUSE into an exit-1 crash (audit F2,
        # 2026-08-02; same guard in the importer's normalized_source).
        rows_field = group.get("objects")
        if not isinstance(rows_field, list):
            continue
        for row in rows_field:
            if not isinstance(row, dict):
                continue
            rows += 1
            name = row.get("object")
            if isinstance(name, str) and name and row.get("ok"):
                out[name] = row
    if not rows:
        raise ValueError(
            "normalisation report at {0} contains no object rows — "
            "malformed or empty".format(path))

    # Merge the engine-derived registry. ABSENT IS FINE -- most projects will
    # never have one -- but MALFORMED RAISES, for the same reason the main
    # report does: "I could not read it" must not become "nothing to add".
    if report_path is None and os.path.isfile(ENGINE_DERIVED_REPORT):
        with open(ENGINE_DERIVED_REPORT, "r", encoding="utf-8") as fh:
            derived = json.load(fh)
        if not isinstance(derived, dict):
            raise ValueError(
                "engine-derived registry at {0} top level is {1}, expected a "
                "dict of groups".format(ENGINE_DERIVED_REPORT,
                                        type(derived).__name__))
        for group in derived.values():
            if not isinstance(group, dict):
                continue
            rows_field = group.get("objects")
            if not isinstance(rows_field, list):
                continue
            for row in rows_field:
                if not isinstance(row, dict):
                    continue
                name = row.get("object")
                if isinstance(name, str) and name and row.get("ok"):
                    # TAGGED, and the tag is load-bearing. The two
                    # registries do NOT carry the same guarantee, and
                    # merging them unmarked (as this did until
                    # 2026-08-15) silently exempts engine-derived meshes
                    # from the grass pivot gate:
                    #
                    #   BLENDER-NORMALISED -> the pivot is AT THE BASE by
                    #     construction, because normalize_asset.py put it
                    #     there. Nothing further to check.
                    #   ENGINE-DERIVED     -> only that somebody MEASURED
                    #     it. The pivot is wherever the vendor left it.
                    #
                    # `recipe_normalization_errors` reads this tag and
                    # runs `uncorrected_pivot_errors` on the second kind.
                    # Copied rather than mutated so the caller's parsed
                    # file is never altered underneath it.
                    tagged = dict(row)
                    tagged["_provenance_kind"] = "engine_derived"
                    out[name] = tagged
    return out


def recipe_mesh_paths(recipe):
    """Every NON-ROCK /Game/ mesh path this recipe names.

    Rock species — those declaring `role` — are EXCLUDED here: they are
    gated separately through `measured_pivot_errors` (see
    `_recipe_mesh_paths_split`, which returns both sets). A caller using
    this set as "every recipe-named mesh" would silently skip rocks.

    Includes GRASS varieties. A grass mesh has no per-instance pivot
    correction available at any level — GrassVariety has no offset
    field — so if anything, the contract binds harder there than for
    placed instances.
    """
    out, _rock = _recipe_mesh_paths_split(recipe)
    return out


def _recipe_mesh_paths_split(recipe):
    """(blender_normalised, measured_pivot) mesh paths.

    A species that declares `role` is a ROCK: a native Fab `.uasset`
    that never went through Blender and NEVER CAN, because R-ASSET
    forbids authoring into a Fab folder. Its pivot is not normalised —
    it is MEASURED, by `measure_rock_meshes.py`, into
    `Free/_measured/rock_pivots.json`, and `rock_scatter.py` refuses to
    plan without that row.

    So the two sets carry the SAME guarantee (this project knows where
    the mesh's base is) through two different instruments. Splitting
    them is not a relaxation: dropping a rock from the check entirely
    would be, and a rock with no measured row is still refused below.
    """
    veg, rock = set(), set()
    fol = (recipe or {}).get("foliage")
    if not isinstance(fol, dict):
        return veg, rock
    for sp in fol.get("species") or []:
        if not isinstance(sp, dict):
            continue
        out = rock if "role" in sp else veg
        m = sp.get("mesh")
        if isinstance(m, str) and m.startswith("/Game/"):
            out.add(m)
        for var in sp.get("varieties") or []:
            vm = (var or {}).get("mesh")
            if isinstance(vm, str) and vm.startswith("/Game/"):
                out.add(vm)
    return veg, rock


def mesh_path_key(path):
    """Canonical comparison key for a content-browser mesh path.

    Strips a trailing slash and a `.ObjectName` suffix from the LEAF
    only, then case-folds, so `/Game/Meshes/X`, `/Game/Meshes/X.X` and
    `/game/meshes/x` all compare equal. The recipe validator accepts
    any of those spellings, and the importer's ruling (c) claim check
    compared raw strings — an exact-match miss there silently SKIPS the
    gate for exactly the asset the recipe names (audit F4, 2026-08-02).
    This errs wide on purpose: a false positive merely requires
    --normalized; a false negative is a silent bypass.
    """
    p = str(path).rstrip("/")
    head, _, leaf = p.rpartition("/")
    return "{0}/{1}".format(head, leaf.split(".")[0]).lower()


def normalization_status(asset_path, verified=None):
    """(ok, reason, row) for one content-browser mesh path.

    The asset's LEAF NAME is matched against the report's object names.
    That coupling is a real constraint and is deliberate: the importer
    is run as `--normalized OBJ --name OBJ`, so the content name IS the
    source object name, and any other naming breaks the trace from a
    placed instance back to the file it came from.
    """
    if verified is None:
        verified = verified_normalized_objects()
    leaf = str(asset_path).rstrip("/").split("/")[-1].split(".")[0]
    row = verified.get(leaf)
    if row is None:
        return False, (
            "{0} has no VERIFIED row in the normalisation report (looked "
            "for object {1!r}). Import it with "
            "`import_static_mesh.py <id> --normalized {1} --name {1}` "
            "after running scripts/blender/normalize_asset.py."
            .format(asset_path, leaf)), None
    return True, "", row


# A mesh placed by the ENGINE's grass system gets NO pivot correction —
# see uncorrected_pivot_errors(). This is the largest fraction of a mesh
# that may be buried by its own un-corrected pivot before the recipe is
# refused. Chosen to match the rock path's `embed_frac` bound, whose
# validator message (import_heightmap.py, embed_frac check) says "above
# 0.5 buries more than half the rock": half is the stated disaster line,
# so a quarter is the conservative side of it.
# A BOX-CENTRED pivot buries exactly 50% by construction
# (base_offset == -extent_z), so this refuses every box-centred rock and
# admits only meshes the vendor authored near their base.
MAX_UNCORRECTED_SINK_FRAC = 0.25


def _measured_pivot_index():
    """{mesh_path_key: row} from the measured-pivot report, or None.

    None means "I could not look" and is never "there are no rows"
    (non-negotiable 6). Callers must not coerce it to an empty dict.
    """
    measured_path = os.path.join(REPO_ROOT, "Free", "_measured",
                                 "rock_pivots.json")
    if not os.path.isfile(measured_path):
        return None
    try:
        with open(measured_path, "r", encoding="utf-8") as fh:
            measured = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(measured, dict):
        return None
    return {mesh_path_key(k): v for k, v in measured.items()}


def uncorrected_pivot_errors(path, row):
    """[] when `row`'s pivot is safe for a mesh NOTHING will correct.

    WHY THIS EXISTS, AND WHY IT IS NOT IN THE ROCK GATE.
    `rock_scatter.plan_species` READS `base_offset_z_m` and subtracts it,
    so a rock instance lands on its base however the vendor set the
    pivot — the dry run prints "base offset -0.618 m -> corrected". The
    ENGINE's landscape grass system does no such thing: it places the
    mesh's PIVOT on the surface and the geometry falls where it falls.

    So the same measured row means two different things depending on who
    places the mesh, and a registry that answers "do we know where the
    base is" does NOT answer "is it safe to place uncorrected". This is
    the second question, asked only of the second placer.
    """
    errs = []
    # A NON-NUMERIC FIELD REFUSES, IT DOES NOT CRASH. Bare float() here
    # let a JSON null or string in a structurally-valid row raise
    # TypeError/ValueError OUTSIDE any caller's (OSError, ValueError)
    # net — turning the clean per-mesh REFUSE this module promises into
    # an exit-1 crash (the audit-F2 class this file says it guards).
    def _num(v):
        ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        return float(v) if ok else None

    bo = _num(row.get("base_offset_z_m"))
    ext = row.get("extent_m")
    # TWO SPELLINGS OF THE SAME MEASUREMENT, and reading either beats
    # making a registry carry both (non-negotiable 24). The rock registry
    # records a half-extent triple; the engine-derived registry records
    # `height_m` directly, because `measure_tree_packs.py` reports a tree's
    # height and a half-extent would be the derived form of it.
    height = None
    if isinstance(ext, (list, tuple)) and len(ext) >= 3:
        half = _num(ext[2])
        height = 2.0 * half if half is not None else None
    elif row.get("height_m") is not None:
        height = _num(row["height_m"])
    if bo is None or height is None:
        return ["foliage: {0} has a measured row without a usable "
                "(numeric) base_offset_z_m plus extent_m or height_m, so "
                "its uncorrected sink cannot be computed. That is 'I could "
                "not look'.".format(path)]
    if height <= 0.0:
        return ["foliage: {0} measures zero height; refusing to divide"
                .format(path)]
    frac = abs(bo) / height
    if frac > MAX_UNCORRECTED_SINK_FRAC:
        errs.append(
            "foliage: {0} is placed by the GRASS system, which applies NO "
            "pivot correction, and its measured pivot would bury "
            "{1:.1%} of the mesh (base_offset {2:+.3f} m against {3:.3f} m "
            "height; limit {4:.0%}). The rock path corrects this and the "
            "grass path cannot, so the same mesh is safe there and unsafe "
            "here.".format(path, frac, float(bo), height,
                           MAX_UNCORRECTED_SINK_FRAC))
    return errs


def recipe_normalization_errors(recipe):
    """[] when every recipe-named mesh traces to a verified object.

    Ruling (c) enforced at the RECIPE, which is where the decision to
    instance something is actually made.

    A NON-ROCK species mesh may satisfy this through EITHER instrument.
    `_recipe_mesh_paths_split` routes by SPECIES KIND — `role` present or
    not — and that key is wrong for the question being asked. Its own
    docstring says the two sets "carry the SAME guarantee (this project
    knows where the mesh's base is) through two different instruments";
    the guarantee is a property of the MESH, not of the species that
    names it. A Fab rock used by a grass species was refused for having
    no Blender-normalised row, which it can never have and never needs.

    Fixed 2026-08-08 by asking BOTH registries and refusing only when
    NEITHER knows the mesh — which is strictly the same guarantee, since
    a mesh in neither is still refused. It is NOT a relaxation, and the
    extra condition below makes it stricter than before for the grass
    case specifically.
    """
    paths, rocks = _recipe_mesh_paths_split(recipe)
    errs = []
    if paths:
        try:
            verified = verified_normalized_objects()
        except (OSError, ValueError) as exc:
            return ["foliage: cannot check pivot normalisation: {0}"
                    .format(exc)]
        measured = _measured_pivot_index()
        for path in sorted(paths):
            ok, why, vrow = normalization_status(path, verified)
            if ok:
                # A row from the ENGINE-DERIVED registry proves the mesh
                # was MEASURED, not that its pivot sits at the base. The
                # grass system applies no correction, so that distinction
                # decides whether the mesh gets buried.
                #
                # Until 2026-08-15 the merged registries were
                # indistinguishable here and this branch was a bare
                # `continue`, which meant registering a mesh as
                # engine-derived EXEMPTED it from the very gate the grass
                # path needs. Found while wiring the blueberry understory,
                # which is a grass species made of vendor .uasset meshes —
                # exactly the combination the hole was shaped for.
                if isinstance(vrow, dict) and \
                        vrow.get("_provenance_kind") == "engine_derived":
                    errs.extend(uncorrected_pivot_errors(path, vrow))
                continue
            # Fall back to the MEASURED registry before refusing.
            row = None if measured is None else measured.get(
                mesh_path_key(path))
            if row is None:
                errs.append("foliage: " + why)
                continue
            errs.extend(uncorrected_pivot_errors(path, row))
    errs.extend(measured_pivot_errors(rocks))
    return errs


def measured_pivot_errors(rock_paths):
    """[] when every rock mesh has a MEASURED pivot row.

    The rock counterpart of the normalisation gate. Note the failure
    modes are reported apart: a MISSING FILE is "I could not look"
    (non-negotiable 6) and is never reported as "this mesh is fine".
    """
    rock_paths = sorted(rock_paths or ())
    if not rock_paths:
        return []
    measured_path = os.path.join(REPO_ROOT, "Free", "_measured",
                                 "rock_pivots.json")
    if not os.path.isfile(measured_path):
        return ["foliage: {0} rock mesh(es) named, but no measured-pivot "
                "report exists at {1}. Run `python "
                "scripts/measure_rock_meshes.py` against the live editor. "
                "This is 'I could not look', not 'the pivots are fine'."
                .format(len(rock_paths), os.path.relpath(measured_path,
                                                         REPO_ROOT))]
    try:
        with open(measured_path, "r", encoding="utf-8") as fh:
            measured = json.load(fh)
    except (OSError, ValueError) as exc:
        return ["foliage: cannot read the measured-pivot report: {0}"
                .format(exc)]
    if not isinstance(measured, dict):
        return ["foliage: measured-pivot report is not an object"]
    index = {mesh_path_key(k): v for k, v in measured.items()}
    errs = []
    for path in rock_paths:
        row = index.get(mesh_path_key(path))
        if row is None:
            errs.append(
                "foliage: {0} is a ROCK species mesh with no row in the "
                "measured-pivot report. Measure it with `python "
                "scripts/measure_rock_meshes.py --only <palette-id>`; a Fab "
                "rock cannot be Blender-normalised (R-ASSET forbids "
                "authoring into a Fab folder), so measurement is the only "
                "instrument that knows where its base is.".format(path))
            continue
        for field in ("base_offset_z_m", "extent_m", "lod_count"):
            if row.get(field) is None:
                errs.append(
                    "foliage: {0} has a measured row whose {1!r} is null — "
                    "the measurement FAILED for that field and must not be "
                    "read as a value.".format(path, field))
    return errs


def texture_asset_path(biome_id, layer_name):
    """Deterministic content path for a layer's imported texture.

    Lives here, beside derive_spec, for the same reason derive_spec does:
    import_layer_textures.py CREATES this asset and
    make_landscape_material.py REFERENCES it, and if the two ever
    disagreed the material would silently sample nothing while both
    scripts reported success. One function decides, so they cannot drift
    (lesson 1.9 - if two components must agree, make them share the code
    that decides, not a convention).

    Derived from recipe data only. Both components are already validated
    by the recipe validator: `biome_id` matches ^[a-z][a-z0-9_]*$, and
    layer names are used as landscape layer info names.
    """
    safe_layer = "".join(
        ch for ch in str(layer_name) if ch.isalnum() or ch in "_-")
    if not safe_layer:
        raise ValueError(
            "layer name {0!r} has no characters legal in an asset "
            "name".format(layer_name))
    return "{0}/T_{1}_{2}".format(
        TEXTURE_CONTENT_DIR, str(biome_id).capitalize(), safe_layer)


def weightmap_asset_path(biome_id):
    """Deterministic content path for a biome's baked layer weightmap.

    Beside texture_asset_path for the same reason: the import script
    CREATES this asset and the material builder REFERENCES it, and a
    disagreement would leave the material sampling nothing while both
    reported success (lesson 1.9).
    """
    return "{0}/T_{1}_Weights".format(
        TEXTURE_CONTENT_DIR, str(biome_id).capitalize())


def macro_map_asset_path(biome_id):
    """Deterministic content path for the km-scale variation map (v1.19).

    Beside the weightmap and selector for the identical reason: the
    import script CREATES it and the material builder REFERENCES it, and
    a disagreement would leave the material sampling nothing while both
    reported success (lesson 1.9).
    """
    return "{0}/T_{1}_Macro".format(
        TEXTURE_CONTENT_DIR, str(biome_id).capitalize())


def variant_map_asset_path(biome_id):
    """Deterministic content path for a biome's sub-surface selector map.

    Schema v1.14. Beside `weightmap_asset_path` and for the identical
    reason: `import_layer_textures.py` CREATES this asset and
    `make_landscape_material.py` REFERENCES it, and a disagreement would
    leave the material sampling NOTHING while both reported success
    (lesson 1.9).

    Same import settings as the weightmap — these are SELECTORS, not
    colour: `srgb=False`, no sRGB decode, or every threshold in the
    material shifts.
    """
    return "{0}/T_{1}_Variants".format(
        TEXTURE_CONTENT_DIR, str(biome_id).capitalize())

# Full 16-bit height range in world units, from LANDSCAPE_ZSCALE = 1/128.
LANDSCAPE_FULL_RANGE_UNITS = 512.0


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


def load_recipe(recipe_path):
    """Read a recipe from inside REPO_ROOT. Returns (recipe, error).

    The error-message PREFIXES ("recipe must live inside REPO_ROOT",
    "recipe not found", "cannot parse recipe") are load-bearing: main()
    classifies its exit code by them. Reword them and the exit-code
    contract in the module docstring silently breaks.
    """
    resolved = os.path.abspath(recipe_path)
    repo = _norm(REPO_ROOT)
    if _norm(resolved) != repo and not _norm(resolved).startswith(
            repo + os.sep):
        return None, "recipe must live inside REPO_ROOT: {0}".format(resolved)
    if not os.path.isfile(resolved):
        return None, "recipe not found: {0}".format(resolved)
    try:
        with open(resolved, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:
        return None, "cannot parse recipe: {0}: {1}".format(
            type(exc).__name__, exc)


def derive_spec(recipe):
    """Derive the landscape spec from recipe geometry.

    Returns (spec_dict, errors). Shared with verify_landscape.py so the
    printed spec and the verified spec cannot diverge.
    """
    errors = []
    hm = recipe.get("heightmap")
    ls = recipe.get("landscape")
    if not isinstance(hm, dict) or not isinstance(ls, dict):
        return None, ["recipe is missing 'heightmap' or 'landscape'"]

    section_size = hm.get("section_size")
    spc = hm.get("sections_per_component")
    component_count = hm.get("component_count")
    resolution = hm.get("resolution")

    for key, val in (("section_size", section_size),
                     ("sections_per_component", spc),
                     ("component_count", component_count),
                     ("resolution", resolution)):
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            errors.append(
                "heightmap.{0} must be a positive integer".format(key))
    if errors:
        return None, errors

    if section_size not in LEGAL_SECTION_SIZES:
        errors.append("heightmap.section_size must be one of {0}, got "
                      "{1}".format(LEGAL_SECTION_SIZES, section_size))
    if spc not in LEGAL_SPC:
        errors.append(
            "heightmap.sections_per_component must be 1 or 2 — the integer "
            "Unreal stores. The dialog's '2x2 Sections' is 2, not 4. Got "
            "{0}.".format(spc))
    if errors:
        return None, errors

    quads_per_component = section_size * spc
    expected_resolution = quads_per_component * component_count + 1
    if resolution != expected_resolution:
        errors.append(
            "heightmap.resolution {0} != section_size * "
            "sections_per_component * component_count + 1 = {1}".format(
                resolution, expected_resolution))
        return None, errors

    scale_xy_cm = ls.get("scale_xy_cm")
    z_scale_cm = ls.get("z_scale_cm")
    location_cm = ls.get("location_cm")
    actor_name = ls.get("actor_name")

    # Finiteness matters: Python's json.load ACCEPTS the non-standard
    # literals NaN/Infinity, `nan <= 0` is False, and repr(nan) is a bare
    # name that would break any payload interpolating these values.
    def _finite_number(v):
        return (isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v))

    if not _finite_number(scale_xy_cm) or scale_xy_cm <= 0:
        errors.append("landscape.scale_xy_cm must be a positive finite "
                      "number")
    if not _finite_number(z_scale_cm) or z_scale_cm <= 0:
        errors.append("landscape.z_scale_cm must be a positive finite "
                      "number")
    if not (isinstance(location_cm, list) and len(location_cm) == 3
            and all(_finite_number(v) for v in location_cm)):
        errors.append("landscape.location_cm must be [x, y, z] finite "
                      "numbers")
    if not isinstance(actor_name, str) or not actor_name:
        errors.append("landscape.actor_name must be a non-empty string")
    if errors:
        return None, errors

    total_quads = quads_per_component * component_count
    spec = {
        "actor_name": actor_name,
        "section_size": section_size,
        "sections_per_component": spc,
        "component_count": component_count,
        "quads_per_component": quads_per_component,
        "resolution": resolution,
        "total_quads": total_quads,
        "total_components": component_count * component_count,
        "location_cm": [float(v) for v in location_cm],
        "scale_x": float(scale_xy_cm),
        "scale_y": float(scale_xy_cm),
        "scale_z": float(z_scale_cm) / LANDSCAPE_FULL_RANGE_UNITS,
        "world_span_cm": total_quads * float(scale_xy_cm),
        # The dialog's Location field is the landscape's CENTRE, not the
        # actor origin: the actor is placed at
        #   dialog_location + offset,  offset = -(total_quads/2) * scale
        # (LandscapeEditorDetailCustomization_NewLandscape.cpp:1219).
        # `landscape.location_cm` is defined as the actor origin, so the
        # value typed into the dialog must be pre-compensated.
        "centre_offset_cm": [
            total_quads / 2.0 * float(scale_xy_cm),
            total_quads / 2.0 * float(scale_xy_cm),
            0.0,
        ],
        "dialog_location_cm": [
            float(location_cm[0]) + total_quads / 2.0 * float(scale_xy_cm),
            float(location_cm[1]) + total_quads / 2.0 * float(scale_xy_cm),
            float(location_cm[2]),
        ],
        "height_range_cm": float(z_scale_cm),
        "heightmap_source": hm.get("source"),
        "heightmap_format": hm.get("format"),
    }
    return spec, []


def _fmt(value):
    """Trim trailing zeros so the printout is typeable as shown."""
    text = "{0:.6f}".format(value).rstrip("0").rstrip(".")
    return text if text else "0"


def print_spec(spec, recipe, recipe_path):
    src = spec["heightmap_source"]
    src_abs = os.path.normpath(os.path.join(REPO_ROOT, src)) if src else None
    src_state = "MISSING" if (
        not src_abs or not os.path.isfile(src_abs)) else "present"

    line = "=" * 70
    print(line)
    print("NEW LANDSCAPE — dialog values for {0}".format(
        recipe.get("display_name", "?")))
    print("derived from {0}".format(recipe_path))
    print(line)
    print("")
    print("Open: Landscape Mode -> Manage -> New -> **Import from File**")
    print("")
    print("  Heightmap File        {0}".format(src_abs or "?"))
    print("                        ({0}, {1})".format(
        spec["heightmap_format"], src_state))
    print("")
    print("  Section Size          {0}x{0} Quads".format(
        spec["section_size"]))
    print("  Sections Per Comp.    {0}x{0} Section{1}".format(
        spec["sections_per_component"],
        "" if spec["sections_per_component"] == 1 else "s"))
    print("  Number of Components  {0} x {0}".format(
        spec["component_count"]))
    print("  Overall Resolution    {0} x {0}".format(spec["resolution"]))
    print("")
    print("  Location              X {0}   Y {1}   Z {2}".format(
        *[_fmt(v) for v in spec["dialog_location_cm"]]))
    print("      ^ NOT the recipe's location_cm. The dialog's Location is")
    print("        the landscape CENTRE; the actor lands at")
    print("        centre - {0} on X and Y. Typing location_cm here".format(
        _fmt(spec["centre_offset_cm"][0])))
    print("        would place the actor {0} cm too far negative on X "
          "and Y.".format(_fmt(spec["centre_offset_cm"][0])))
    print("  Rotation              0   0   0")
    print("  Scale                 X {0}   Y {1}   Z {2}".format(
        _fmt(spec["scale_x"]), _fmt(spec["scale_y"]),
        _fmt(spec["scale_z"])))
    print("")
    print("  Then set the actor label to:  {0}".format(spec["actor_name"]))
    print("")
    print(line)
    print("CHECKS — these should agree with what the dialog shows")
    print(line)
    print("  quads per component   {0} x {1} = {2}".format(
        spec["section_size"], spec["sections_per_component"],
        spec["quads_per_component"]))
    print("  total quads per side  {0} x {1} = {2}".format(
        spec["quads_per_component"], spec["component_count"],
        spec["total_quads"]))
    print("  overall resolution    {0} + 1 = {1}".format(
        spec["total_quads"], spec["resolution"]))
    print("  total components      {0}".format(spec["total_components"]))
    print("  world span            {0} m across".format(
        _fmt(spec["world_span_cm"] / 100.0)))
    print("  centre offset         {0} / 2 x {1} = {2} cm".format(
        spec["total_quads"], _fmt(spec["scale_x"]),
        _fmt(spec["centre_offset_cm"][0])))
    print("  actor will land at    X {0}   Y {1}   Z {2}".format(
        *[_fmt(v) for v in spec["location_cm"]]))
    print("                        (= dialog Location minus the centre "
          "offset)")
    print("  height range          {0} m for the full 16-bit range".format(
        _fmt(spec["height_range_cm"] / 100.0)))
    print("                        (scale Z {0} x 512 units = {1} cm)".format(
        _fmt(spec["scale_z"]), _fmt(spec["height_range_cm"])))
    print("")
    print(line)
    print("NOTES")
    print(line)
    print("- Enter the heightmap file FIRST. The dialog derives resolution")
    print("  and component count from the file, then clamps them. If what")
    print("  it shows disagrees with the values above, STOP — the recipe")
    print("  and the file are out of step; do not 'fix' it in the dialog.")
    print("- 'Sections Per Component' is a dropdown showing NxN. Pick the")
    print("  entry reading {0}x{0}; the stored integer is {0}.".format(
        spec["sections_per_component"]))
    print("- Scale Z is not a height in centimetres. It is a multiplier:")
    print("  the full 16-bit range spans 512 * scale_z cm.")
    half_m = spec["height_range_cm"] / 200.0
    z_m = spec["location_cm"][2] / 100.0
    print("- Height datum: the engine maps heightmap value 32768 (mid-grey)")
    print("  to the actor's Z (LANDSCAPE_ZSCALE, LandscapeDataAccess.h:13),")
    print("  so world heights run {0} m to {1} m — the terrain is NOT".format(
        _fmt(z_m - half_m), _fmt(z_m + half_m)))
    print("  0..{0} m above the origin.".format(
        _fmt(spec["height_range_cm"] / 100.0)))
    print("- Do NOT press 'Fit To Data' (this tab's layout button; the")
    print("  Create tab's equivalent is 'Fill World'). Both recompute the")
    print("  component layout from other inputs and silently discard the")
    print("  geometry above.")
    print("")
    print("After creating it, run:")
    print("  python scripts/verify_landscape.py")
    print("Nothing downstream should be run until that exits 0.")
    print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE,
                        help="Recipe to derive the spec from.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe_path = os.path.abspath(args.recipe)
    recipe, err = load_recipe(recipe_path)
    if err:
        print("REFUSE: {0}".format(err))
        # Classify by the message PREFIX, never by substring: the messages
        # interpolate the resolved path, and a path containing "parse" or
        # "not found" (…\sparse\…) would flip an outside-REPO_ROOT refusal
        # (documented exit 1) into exit 2. The prefixes below are
        # load_recipe's fixed openings and precede any interpolation.
        return 2 if err.startswith(("recipe not found",
                                    "cannot parse recipe")) else 1

    spec, errors = derive_spec(recipe)
    if errors:
        print("REFUSE: recipe geometry is not buildable:")
        for e in errors:
            print("  - {0}".format(e))
        return 2

    print_spec(spec, recipe, recipe_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
