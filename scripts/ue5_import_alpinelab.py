"""ue5_import_alpinelab.py — RUN THIS INSIDE THE UE 5.8 EDITOR.

Not a remote-execution script. Paste-and-run from the editor's Python
console, or Tools > Execute Python Script. It imports nothing itself from
this repo, so it can be copied anywhere.

=====================================================================
~~READ THIS FIRST: PYTHON CANNOT CREATE THE LANDSCAPE IN UE 5.8~~
STRUCK 2026-08-12 — TRUE WHEN WRITTEN, FALSE NOW.
=====================================================================
`LandscapeLab/Plugins/LandscapeLabEditor` exposes ALandscapeProxy::Import
as a UFUNCTION, and `scripts/create_landscape_from_build.py` creates and
imports a landscape from a Gaea build with no hand step at all.

The diagnosis below is kept, struck rather than deleted, because it is
still CORRECT ABOUT THE ENGINE: 5.8 ships no UFUNCTION route and no
LandscapeEditorSubsystem, which is exactly why a plugin had to exist. What
changed is not the engine but what this project owns.

It is struck loudly because of WHERE it sits. A paragraph headed "READ
THIS FIRST" that tells a fresh session a capability is impossible is the
most dangerous place in the repo for a stale line — the same shape as the
Gaea-licensing note and the talus-threshold entry, both of which were
struck for the same reason. A session obeying it would create the
landscape by hand and never look for the tool.

The mask-import half of this script (below) is unaffected and still runs.
=====================================================================
THE ORIGINAL DIAGNOSIS, KEPT AS THE RECORD
=====================================================================

The brief asked for a script that CREATES the landscape from the
heightmap. That is not possible on this build, and the evidence is the
generated stub for this exact install
(LandscapeLab/Intermediate/PythonStub/unreal.py):

  * there is no create/new/import landscape function anywhere in the
    reflected surface — no LandscapeEditorSubsystem, no ImportLandscape;
  * the only two import entry points are METHODS ON AN EXISTING
    LandscapeProxy, and neither takes a file path:

        landscape_import_heightmap_from_render_target(rt, ...)   :531954
        landscape_import_weightmap_from_render_target(rt, name)  :531939

    Both want a TextureRenderTarget2D. Getting a PNG into one is a whole
    pipeline of its own (this repo's push_heightmap.py exists to do it,
    and its docstring records two editor crashes learned along the way).

So the landscape is created BY HAND, once, in Landscape Mode — which is
not a workaround. The Landscape tool's Import dialog takes the PNG
directly, computes the section layout, and sets the scale in one place.
Scripting around it would reimplement a solved problem badly.

This script does the parts that ARE robust to automate:
  1. VERIFIES the landscape you created matches what the package expects
  2. ~~IMPORTS the five masks as textures~~ — SUPERSEDED 2026-08-12 by
     `scripts/import_alpinelab_masks.py`, which is recipe-driven and runs
     over remote exec instead of being pasted into the editor.

     THE MASK-IMPORT SECTION BELOW IS NO LONGER THE IMPLEMENTATION. It is
     kept because the landscape-verification half still runs, but do not
     extend it and do not copy its settings: two importers with two sets of
     texture settings is the shape non-negotiable 4a rejects, and this file
     is already evidence of how those drift. Its own docstring below claims
     `TC_VECTOR_DISPLACEMENTMAP`; the 2026-08-10 handoff says BC4; the live
     v1 assets read `TC_GRAYSCALE`. Three records, three answers, and only
     the assets were ever authoritative.

=====================================================================
WHY THE MASKS COME IN AS PLAIN TEXTURES, NOT LAYER WEIGHTMAPS
=====================================================================

The brief left this open. Textures, decisively, for this build:

  * A weightmap import needs a TextureRenderTarget2D (above), a
    ULandscapeLayerInfoObject per layer, AND a landscape material that
    declares matching layers. For a brand-new evaluation landscape none
    of those exist, so "import as weightmaps" silently becomes "author a
    layered landscape material first".
  * Texture import goes through AssetImportTask/AssetTools, which is the
    ordinary, well-trodden path and is what this repo already uses.
  * Nothing is lost. A texture can be promoted to a weightmap later; the
    16-bit data is preserved either way. Deciding now would be deciding
    before the terrain has even been looked at.

TEXTURE SETTINGS are taken from this repo's import_layer_textures.py,
which reasoned them out for exactly this kind of data:

    srgb                  False    these are data, not colour. Left True,
                                   byte 128 decodes as 0.216, not 0.5.
    compression_settings  TC_VECTOR_DISPLACEMENTMAP (uncompressed) —
                                   a block compressor mixes neighbouring
                                   values and a drainage line is exactly
                                   the thin high-frequency feature it
                                   destroys.
    address_x / address_y TA_CLAMP — these map 1:1 onto the terrain
                                   footprint and must never tile.
"""

import os
import unreal

# =====================================================================
# CONFIGURATION
# =====================================================================

BUILD_DIR = r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\002\UE5_Ready"
DEST_PATH = "/Game/AlpineLab_v1"

# Expected landscape geometry. 4033 = 63 quads x 64 components + 1.
EXPECT_VERTS = 4033
QUADS_PER_SECTION = 63
SECTIONS_PER_COMPONENT = 1          # 1x1; 2x2 would halve component count
EXPECT_COMPONENTS = 64              # per axis

# THE FILE TO HAND THE IMPORT DIALOG. Byte-identical to
# AlpineLab_v1_Height_normalized.png, under a name UE 5.8 will not
# pattern-match as a tiled image. The canonical name contains `v1`,
# which matches the tiled token regex `v(-?[0-9]+)` at
# LandscapeTiledImage.cpp:22-24; answering YES to the resulting
# "Use '...' Tiled Image?" prompt creates NO landscape, because only a
# `u`/`x` token can set the tile X coordinate (:86-104) and the
# `if (X >= 0 && Y >= 0)` guard at :105 then adds no tiles at all.
HEIGHT_IMPORT_FILE = "AlpineLabHeight.png"

# UE's 16-bit landscape height range spans this many metres at Z = 100.
UE_HEIGHT_SPAN_M_AT_Z100 = 512.0

# ---------------------------------------------------------------------
# Z SCALE — RESOLVED 2026-08-09. PROVENANCE: MEASURED.
# ---------------------------------------------------------------------
# No longer a placeholder. Derived from the Gaea project itself:
#
#   AlpineLabe_v1_2026-08-09_19-12-59.terrain  (JSON, read-only)
#     /Assets/$values[0]/Terrain/Height = 2500.0     metres, full range
#
# The project range is NOT the built terrain's span, and using it
# directly is the trap. The build occupied only 496-24763 of 65535
# before normalization:
#
#   occupancy   (24763 - 496) / 65535       = 0.37029
#   low  edge   2500 * 496   / 65535        =   18.92 m
#   high edge   2500 * 24763 / 65535        =  944.65 m
#   SPAN S                                  =  925.73 m
#
#   Z = S / 512 * 100                       =  180.81
#
# (512 m is what UE's 16-bit height range spans at Z scale 100.)
#
# The naive answer — 2500/512*100 = 488.3 — is WRONG BY 2.7x, because
# the export was normalized to full range AFTER the sim. That is exactly
# the error this constant existed to prevent, and it is why the value is
# derived here rather than typed.
Z_SCALE = 180.81
Z_SCALE_PROVENANCE = ("measured — Gaea Terrain/Height 2500.0 m x "
                      "(24763-496)/65535 = 925.73 m span, /512*100")

# THIS VALUE IS BUILD-SPECIFIC. It is the occupancy of build 002, not a
# property of the project. Builds made by scripts/rebuild_terrain.py
# write their own derivation to height_normalization.json beside the
# heightmap; ADOPTING a new build means reading that file and updating
# this constant, not carrying 180.81 forward.

# Kept under the old name so nothing silently reads a stale placeholder.
TODO_Z_SCALE_PLACEHOLDER = Z_SCALE

MASKS = [
    ("Erosion2_Flow.png", "T_AlpineLab_Flow",
     "drainage / flow — full range, sparse"),
    ("Erosion2_Wear.png", "T_AlpineLab_Wear",
     "wear — source range 0-6019, NEEDS REMAP before use"),
    ("Erosion2_Deposits.png", "T_AlpineLab_Deposits",
     "deposits — source range 0-512, NEEDS STRONG REMAP"),
    ("Snow_Snow.png", "T_AlpineLab_SnowHard",
     "hard snow coverage"),
    ("SnowMask_Out.png", "T_AlpineLab_SnowDepth",
     "graded snow depth, autoleveled"),
]


def _log(msg):
    unreal.log("[AlpineLab] {0}".format(msg))


# =====================================================================
# 1. VERIFY THE LANDSCAPE YOU CREATED
# =====================================================================

def _expected_z_span_m():
    """Metres a full 0-65535 heightmap spans at the recorded Z scale.

    UE's 16-bit landscape range is 512 m at Z = 100. The imported height
    is normalized to the FULL range (R-GAEA section 3), so the landscape
    should occupy all of it -- this is a real prediction, not a bound.
    """
    return UE_HEIGHT_SPAN_M_AT_Z100 * Z_SCALE / 100.0


def verify_landscape():
    """Report the landscape's real geometry. Returns True if it matches.

    Reads the ACTOR, not the import dialog you typed into — those are
    different representations, and this project has been caught before
    by trusting the thing that recorded an intent over the thing that
    holds the result.

    EVERY CHECK PRINTS ITS EXPECTED VALUE NEXT TO ITS MEASURED ONE. A
    check whose expectation lives only in the author's head is not a
    check a later reader can audit.
    """
    subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    lands = [a for a in subsys.get_all_level_actors()
             if isinstance(a, unreal.Landscape)]

    if not lands:
        _log("=" * 62)
        _log("NO LANDSCAPE ACTOR IN THIS LEVEL.")
        _log("=" * 62)
        _log("The manual import did NOT happen, or it silently failed.")
        _log("")
        _log("THE KNOWN FAILURE: the import dialog offers")
        _log("  \"Use 'AlpineLab_v<v>_Height_normalized.png' Tiled Image?\"")
        _log("and answering YES creates NO landscape and reports almost")
        _log("nothing. Import AlpineLabHeight.png instead -- same bytes,")
        _log("a name the dialog does not pattern-match.")
        _log("")
        _log("Full steps: docs/archive/pre8k/IMPORT_CHECKLIST.md (ARCHIVED "
             "2026-08-29 -- its premise died with R-CREATE).")
        _log("NOTHING ELSE WILL RUN. This script will not import masks")
        _log("against a level with no landscape to register them to.")
        return False

    if len(lands) > 1:
        _log("REFUSE: {0} landscapes in this level. Ambiguous — this "
             "script will not guess which one you meant."
             .format(len(lands)))
        for a in lands:
            _log("  - {0}".format(a.get_actor_label()))
        return False

    land = lands[0]
    ok = True
    _log("landscape actor : {0}".format(land.get_actor_label()))

    scale = land.get_actor_scale3d()
    _log("scale           : X {0:.3f}  Y {1:.3f}  Z {2:.3f}   "
         "(expected Z {3:.2f})".format(scale.x, scale.y, scale.z, Z_SCALE))
    if abs(scale.z - Z_SCALE) > 0.01:
        ok = False
        _log("  MISMATCH: Z is {0:.3f}, expected {1:.2f}.".format(
            scale.z, Z_SCALE))
        _log("  {0}".format(Z_SCALE_PROVENANCE))
        _log("  Elevations off this landscape are NOT the Gaea metres "
             "that provenance describes.")

    # ---- COMPONENT COUNT -------------------------------------------
    # The honest check on the section config: 4033 vertices at 63 quads
    # per section, 1x1 sections per component, is 64 components per axis
    # and 4,096 in total. A dialog set to 127 quads would give 1,024 and
    # still import a valid-looking landscape.
    expect_comps = EXPECT_COMPONENTS * EXPECT_COMPONENTS
    try:
        comps = land.get_components_by_class(unreal.LandscapeComponent)
        n_comp = len(comps)
        _log("components      : {0}   (expected {1} = {2}x{2})"
             .format(n_comp, expect_comps, EXPECT_COMPONENTS))
        if n_comp != expect_comps:
            ok = False
            _log("  MISMATCH: re-check Section Size and Sections Per "
                 "Component in the import dialog.")
    except Exception as exc:
        # "I could not look" is not "I looked and it was fine".
        n_comp = None
        ok = False
        _log("components      : COULD NOT READ ({0}: {1}) — this is NOT "
             "a pass".format(type(exc).__name__, exc))

    try:
        coll = land.get_components_by_class(
            unreal.LandscapeHeightfieldCollisionComponent)
        _log("collision comps : {0}".format(len(coll)))
    except Exception as exc:
        _log("collision comps : could not read ({0})"
             .format(type(exc).__name__))

    # ---- WORLD SPAN -------------------------------------------------
    bounds = land.get_actor_bounds(False)
    origin, extent = bounds[0], bounds[1]
    span_x_uu = extent.x * 2.0
    span_y_uu = extent.y * 2.0
    span_z_uu = extent.z * 2.0
    expected_uu = (EXPECT_VERTS - 1) * scale.x

    _log("world span X    : {0:,.0f} UU  ({1:.1f} m)   expected {2:,.0f} UU"
         .format(span_x_uu, span_x_uu / 100.0, expected_uu))
    _log("world span Y    : {0:,.0f} UU  ({1:.1f} m)"
         .format(span_y_uu, span_y_uu / 100.0))
    tol_uu = max(100.0, expected_uu * 0.02)
    if abs(span_x_uu - expected_uu) > tol_uu or \
            abs(span_y_uu - expected_uu) > tol_uu:
        ok = False
        _log("  MISMATCH: this is not {0} vertices at scale {1:.1f}. "
             "Re-check Overall Resolution in the dialog — it must read "
             "{0} x {0}.".format(EXPECT_VERTS, scale.x))

    # ---- VERTICAL RANGE ---------------------------------------------
    # A DIFFERENT REPRESENTATION of the Z scale than reading scale.z:
    # scale.z is what the dialog wrote, this is what the geometry came
    # out as. Agreement means the number took effect, not just landed.
    want_z_m = _expected_z_span_m()
    got_z_m = span_z_uu / 100.0
    _log("height span     : {0:.1f} m   expected {1:.1f} m at Z {2:.2f}"
         .format(got_z_m, want_z_m, Z_SCALE))
    _log("height range    : {0:.1f} m to {1:.1f} m (world Z)"
         .format((origin.z - extent.z) / 100.0,
                 (origin.z + extent.z) / 100.0))
    if want_z_m > 0 and abs(got_z_m - want_z_m) > want_z_m * 0.03:
        ok = False
        _log("  MISMATCH: the terrain does not span what Z {0:.2f} "
             "predicts for a full-range heightmap. Either the Z scale in "
             "the dialog differed, or the heightmap that got imported was "
             "not the normalized one.".format(Z_SCALE))

    # Component count and span are independent measurements of the same
    # section config; if both are readable, they must agree.
    if n_comp and n_comp > 0 and span_x_uu > 0:
        per_axis = int(round(n_comp ** 0.5))
        if per_axis * per_axis == n_comp and scale.x:
            quads = span_x_uu / scale.x / per_axis
            _log("derived         : {0} components/axis x {1:.0f} quads "
                 "= {2:.0f} quads (expected {3} x {4} = {5})"
                 .format(per_axis, quads, per_axis * quads,
                         EXPECT_COMPONENTS, QUADS_PER_SECTION,
                         EXPECT_COMPONENTS * QUADS_PER_SECTION))

    return ok


# =====================================================================
# 2. IMPORT THE MASKS AS TEXTURES
# =====================================================================

def import_masks(skip_existing=True):
    """Import the five masks. Returns (imported, skipped, failed).

    SKIPS anything already in /Game/AlpineLab_v1. Re-importing over a
    live asset is a mutation with no undo, and the five textures are
    already there from the first run; a script that quietly redid that
    work every time would be the kind of unnecessary write this project
    keeps out of the editor. This module parses no CLI args (it imports only
    os and unreal; __main__ calls main() with reimport=False) — force a
    re-import IN CODE with main(reimport=True) or import_masks(skip_existing=
    False). There is no --reimport flag; a caller who "passes" one gets
    skip_existing=True and the masks are NOT re-imported.
    """
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    imported, skipped, failed = [], [], []

    for filename, asset_name, note in MASKS:
        obj_path = "{0}/{1}".format(DEST_PATH, asset_name)
        if skip_existing and unreal.EditorAssetLibrary.does_asset_exist(
                obj_path):
            tex = unreal.EditorAssetLibrary.load_asset(obj_path)
            # Report what is ALREADY there rather than asserting it is
            # right -- an existing asset is evidence of a prior import,
            # not evidence of a correct one.
            try:
                dims = "{0}x{1}".format(tex.blueprint_get_size_x(),
                                        tex.blueprint_get_size_y())
                srgb = tex.get_editor_property("srgb")
                comp = tex.get_editor_property("compression_settings")
                flags = "srgb={0} {1}".format(
                    srgb, str(comp).split(".")[-1])
            except Exception as exc:
                dims, flags = "?", "could not read ({0})".format(
                    type(exc).__name__)
            skipped.append((asset_name, dims, flags))
            _log("EXISTS  {0}  {1}  {2}  — not re-imported"
                 .format(asset_name, dims, flags))
            continue

        src = os.path.join(BUILD_DIR, filename)
        if not os.path.isfile(src):
            _log("MISSING {0} — FAILED (source file missing)".format(src))
            failed.append((asset_name, "source file missing"))
            continue

        task = unreal.AssetImportTask()
        task.set_editor_property("filename", src)
        task.set_editor_property("destination_path", DEST_PATH)
        task.set_editor_property("destination_name", asset_name)
        task.set_editor_property("automated", True)     # no dialogs
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", False)         # you save, not me
        tools.import_asset_tasks([task])

        objs = task.get_editor_property("imported_object_paths")
        if not objs:
            failed.append((asset_name, "importer returned no object"))
            _log("FAILED {0}".format(asset_name))
            continue

        tex = unreal.EditorAssetLibrary.load_asset(
            "{0}/{1}".format(DEST_PATH, asset_name))
        if tex is None:
            failed.append((asset_name, "asset did not load back"))
            continue

        # Settings, then READ THEM BACK — setting a property and trusting
        # it is how this project has been bitten repeatedly.
        tex.set_editor_property("srgb", False)
        tex.set_editor_property(
            "compression_settings",
            unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
        tex.set_editor_property(
            "address_x", unreal.TextureAddress.TA_CLAMP)
        tex.set_editor_property(
            "address_y", unreal.TextureAddress.TA_CLAMP)

        got_srgb = tex.get_editor_property("srgb")
        got_comp = tex.get_editor_property("compression_settings")
        got_ax = tex.get_editor_property("address_x")
        bad = []
        if got_srgb:
            bad.append("srgb did not clear")
        if got_comp != unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP:
            bad.append("compression is {0}".format(got_comp))
        if got_ax != unreal.TextureAddress.TA_CLAMP:
            bad.append("address_x is {0}".format(got_ax))
        if bad:
            failed.append((asset_name, "; ".join(bad)))
            _log("SETTINGS DID NOT TAKE on {0}: {1}"
                 .format(asset_name, "; ".join(bad)))
            continue

        imported.append((asset_name, tex.blueprint_get_size_x(),
                         tex.blueprint_get_size_y(), note))
        _log("imported {0}  {1}x{2}  srgb=False, uncompressed, CLAMP  [{3}]"
             .format(asset_name, tex.blueprint_get_size_x(),
                     tex.blueprint_get_size_y(), note))

    return imported, skipped, failed


def main(reimport=False):
    _log("=" * 62)
    _log("AlpineLab_v1 build 002 — landscape verification + mask import")
    _log("source: {0}".format(BUILD_DIR))
    _log("=" * 62)

    land_ok = verify_landscape()

    # THE LANDSCAPE IS THE GATE. Masks are terrain-registered data; if
    # there is no landscape they register to nothing, and importing them
    # anyway is the "partial success" that makes a failed import read
    # like a mostly-working one.
    if not land_ok:
        _log("")
        _log("-" * 62)
        _log("VERDICT: FAILED — no usable landscape. Nothing imported, "
             "nothing changed.")
        _log("-" * 62)
        return False

    _log("")
    imported, skipped, failed = import_masks(skip_existing=not reimport)

    _log("")
    _log("-" * 62)
    _log("landscape verified : YES")
    _log("masks imported     : {0}".format(len(imported)))
    _log("masks already there: {0}".format(len(skipped)))
    _log("masks failed       : {0}".format(len(failed)))
    for name, why in failed:
        _log("  FAILED {0}: {1}".format(name, why))
    _log("")
    if imported:
        _log("NOTHING WAS SAVED. Review the assets, then File > Save All.")
    _log("Z SCALE {0:.2f} — provenance: {1}".format(
        Z_SCALE, Z_SCALE_PROVENANCE))
    _log("VERDICT: {0}".format(
        "PASS" if not failed else "PASS WITH FAILURES — see above"))
    _log("-" * 62)
    return not failed


if __name__ == "__main__":
    main()
