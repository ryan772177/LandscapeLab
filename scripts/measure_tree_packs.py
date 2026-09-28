"""measure_tree_packs.py — intake measurement for Fab/Megaplants tree packs.

Answers the acceptance questions `docs/archive/pre8k/conifer_asset_spec.md`
section 5 fixed (ARCHIVED 2026-08-29: the conifer WAS chosen -- PVE Norway
spruce, 2026-08-15 -- so that spec is completed, not pending)
IN ADVANCE, so a purchase is judged by the instruments that condemned the
incumbent rather than by a fresh impression:

  1. foliage atlas OPAQUE COVERAGE, and the clip-0.1-vs-0.5 spread that says
     whether the alpha is binary
  2. needle ALBEDO where opaque, and whether green exceeds red
  3. per-LOD triangles, REAL LOD screen sizes, pivot offset, dimensions

Writes `Free/_measured/tree_packs.json`. Mutates nothing in the world: it
loads assets, exports textures to `_verify/tex/`, and reads.

THE MESH PAYLOAD IS NOT FORKED
------------------------------
`measure_rock_meshes.PAYLOAD` already measures bounds/pivot, nanite, LOD
count, per-LOD triangles and real screen sizes, and its comments carry why
each accessor is the right one (`get_bounds()` returns a BoxSphereBounds
object; `get_num_triangles(i)` and `get_lod_screen_sizes(mesh)` were
confirmed against the running 5.8 editor). This module IMPORTS it. Two
copies of that payload would be non-negotiable 24 in miniature -- the vendor
LOD-screen-size trap it exists to catch would then need fixing twice.

WHAT THIS TOOL DELIBERATELY DOES NOT CONCLUDE
---------------------------------------------
**Atlas coverage alone does not predict canopy density, and this project has
the scar.** On 2026-08-14 the Scots pine measured 8.98% opaque against the
fir's 23.56% -- 2.6x SPARSER -- and its render produced a visibly DENSER
canopy, because it carries far more foliage cards per tree. Screen density is
(coverage x cards x card area) and only the first term is measurable here.
So every coverage number this tool prints is labelled ONE TERM OF THREE, and
the verdict belongs to the render A/B, not to this table.

Exit codes:
  0  every requested asset measured
  2  editor gate refused (conduct rule 7), or bad arguments
  3  one or more assets could not be measured (details in the table)
  4  stopped early on the RAM floor
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap             # noqa: E402
import measure_rock_meshes as mrm   # noqa: E402  (payload reused, not copied)
import resource_guard        # noqa: E402
import verify_landscape      # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MEASURED = os.path.join(REPO_ROOT, "Free", "_measured")
TEXDIR = os.path.join(REPO_ROOT, "_verify", "tex")
OUT = os.path.join(MEASURED, "tree_packs.json")

TEXMARKER = "__LANDSCAPELAB_TEXEXPORT__"

# Same floor and reason as measure_rock_meshes: below 1.0 GB free the editor
# has paged hard every time on this host.
FLOOR_GB = 1.0

# The incumbent, from docs/archive/pre8k/conifer_asset_spec.md section 1. Every row is
# reported against these so a reader does not have to look them up.
INCUMBENT = {
    "name": "fir_tree_01",
    "atlas_opaque_pct": 24.02,
    "atlas_opaque_pct_clip01": 25.06,
    "atlas_opaque_pct_clip05": 23.56,
    "albedo_rgb": [85, 81, 49],
    "height_m": 14.52,
    "canopy_radius_m": 3.068,
    "lod0_triangles": 505494,
}

# Default targets: the two Megaplants conifers that landed 2026-08-14.
# Variants A-D are the four supplied tree meshes; the Instances/ folder holds
# component parts (branches, twigs) that are not standalone trees.
DEFAULT_TREES = [
    "/Game/Megaplant_Library/Tree_Norway_Spruce/Tree_Norway_Spruce_01/"
    "Tree_Norway_Spruce_01_" + v for v in ("A", "B", "C", "D")
] + [
    "/Game/Megaplant_Library/Tree_Baltic_Pine/Tree_Baltic_Pine_01/"
    "Tree_Baltic_Pine_01_" + v for v in ("A", "B", "C", "D")
]

# `_CA` is Megaplants' colour+alpha foliage atlas -- the artefact the 24.02%
# figure was measured on for the incumbent. Each is paired with the MATERIAL
# that consumes it, because coverage is only a canopy metric when the
# material actually MASKS with it (see measure_atlas).
DEFAULT_ATLASES = [
    {"texture": "/Game/Megaplant_Library/Tree_Norway_Spruce/Textures/"
                "T_Norway_Spruce_Foliage_01_CA",
     "material": "/Game/Megaplant_Library/Tree_Norway_Spruce/Materials/"
                 "MI_Norway_Spruce_Foliage_01"},
    {"texture": "/Game/Megaplant_Library/Tree_Baltic_Pine/Textures/"
                "T_Baltic_Pine_Foliage_CA",
     "material": "/Game/Megaplant_Library/Tree_Baltic_Pine/Materials/"
                 "MI_Baltic_Pine_01_Foliage"},
]

# Reads the consuming material's OVERRIDE-SLOT blend mode
# (base_property_overrides.blend_mode -- the EFFECTIVE blend mode only when
# override_blend_mode is True; that flag is recorded as blend_mode_overridden
# but main() does not consult it) and the asset class of a mesh. Both were
# added after the first run reported a number that was not a measurement --
# see measure_atlas and the CLASS note in main().
INFOPAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"path": {path!r}, "ok": False, "error": None}}
try:
    _p = {path!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "asset does not exist"
    else:
        _a = _unreal.EditorAssetLibrary.load_asset(_p)
        if _a is None:
            _out["error"] = "load_asset returned None"
        else:
            _out["asset_class"] = type(_a).__name__
            try:
                _bpo = _a.get_editor_property("base_property_overrides")
                _out["blend_mode"] = str(
                    _bpo.get_editor_property("blend_mode"))
                _out["blend_mode_overridden"] = bool(
                    _bpo.get_editor_property("override_blend_mode"))
                _out["opacity_mask_clip_value"] = float(
                    _bpo.get_editor_property("opacity_mask_clip_value"))
            except Exception as _ex:
                _out["blend_mode"] = None
                _out["blend_error"] = str(_ex)[:160]
            _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''
INFOMARKER = "__LANDSCAPELAB_TREEINFO__"

# Export a texture to PNG. TextureExporterPNG and Exporter.run_asset_export_task
# were both confirmed present in this install's PythonStub before this was
# written (NN23: an API remembered is an API guessed).
TEXPAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"path": {path!r}, "ok": False, "error": None, "written": None}}
try:
    _p = {path!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "asset does not exist"
    else:
        _t = _unreal.EditorAssetLibrary.load_asset(_p)
        if _t is None:
            _out["error"] = "load_asset returned None"
        else:
            _task = _unreal.AssetExportTask()
            _task.set_editor_property("object", _t)
            _task.set_editor_property("filename", {dest!r})
            _task.set_editor_property("automated", True)
            _task.set_editor_property("prompt", False)
            _task.set_editor_property("replace_identical", True)
            _task.set_editor_property("exporter", _unreal.TextureExporterPNG())
            _ok = _unreal.Exporter.run_asset_export_task(_task)
            _out["ok"] = bool(_ok)
            _out["written"] = {dest!r}
            try:
                _errs = list(_task.get_editor_property("errors"))
                if _errs:
                    _out["error"] = "; ".join(str(_e) for _e in _errs)[:300]
            except Exception:
                pass
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''


def _parse_info(text):
    i = (text or "").find(INFOMARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(INFOMARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_tex(text):
    i = (text or "").find(TEXMARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(TEXMARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def measure_atlas(png_path, blend_mode=None):
    """Opaque coverage and albedo-where-opaque for one exported atlas.

    COVERAGE IS ONLY A CANOPY METRIC WHEN THE MATERIAL MASKS WITH IT, and
    this function refuses to imply otherwise. Two ways it can be meaningless,
    both measured on 2026-08-14 and both of which the first version of this
    tool reported as if they were results:

      * the alpha channel is CONSTANT -- `T_Baltic_Pine_Foliage_CA` is 255
        everywhere, so "100.00% opaque" is not a measurement of anything, it
        is the absence of a mask being read as full coverage. That is
        non-negotiable 6 wearing a number.
      * the material is not BLEND_Masked -- BOTH Megaplants foliage materials
        are BLEND_Opaque with the override ON, so their needles are real
        geometry and no alpha test happens at all. The incumbent's 24.02% is
        a figure about ALPHA-TESTED CARDS; against opaque geometry it is not
        a smaller number, it is a different question.

    When either holds, `coverage_applicable` is False and the percentages are
    reported as diagnostics with an explicit reason, never as canopy density.

    Returns a dict, or {"error": ...}. Deliberately reports coverage at TWO
    clip thresholds: a binary alpha barely moves between them, and that is
    the property that decides whether the opacity threshold is a usable lever
    at all. The incumbent moves 25.06 -> 23.56 across 0.1 -> 0.5, i.e. the
    threshold buys ~1.5% and is NOT the lever.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        return {"error": "numpy/Pillow unavailable: {0}".format(e)}

    try:
        im = Image.open(png_path)
    except Exception as e:
        return {"error": "could not open {0}: {1}".format(png_path, e)}

    if im.mode != "RGBA":
        im = im.convert("RGBA")
    a = np.asarray(im).astype(np.float64) / 255.0
    if a.ndim != 3 or a.shape[2] != 4:
        return {"error": "unexpected array shape {0}".format(a.shape)}

    alpha = a[:, :, 3]
    rgb = a[:, :, :3]
    total = float(alpha.size)

    cov = {}
    for clip in (0.1, 0.5):
        cov["opaque_pct_clip{0}".format(str(clip).replace(".", ""))] = round(
            100.0 * float((alpha >= clip).sum()) / total, 2)

    mask = alpha >= 0.5
    n_opaque = int(mask.sum())
    if n_opaque == 0:
        albedo = None
    else:
        # Mean over OPAQUE texels only. Averaging the whole atlas would fold
        # in the empty 3/4 and report a darker, meaningless colour -- the
        # misleading-denominator class (non-negotiable 22).
        m = rgb[mask]
        albedo = [int(round(255.0 * float(m[:, c].mean()))) for c in range(3)]

    out = {
        "png": os.path.relpath(png_path, REPO_ROOT),
        "size": [int(im.size[0]), int(im.size[1])],
        "opaque_texels": n_opaque,
        "albedo_rgb_where_opaque": albedo,
        # STATE THE DENOMINATOR (non-negotiable 22). When alpha is constant
        # the "where opaque" mask selects every texel, so this is the mean of
        # the WHOLE ATLAS -- padding, unused regions and all -- and it is NOT
        # the needle colour. Same arithmetic, a different question.
        "albedo_denominator": (
            "WHOLE TEXTURE (alpha is constant, so no mask selects needles)"
            if float(alpha.min()) >= 1.0 else "texels with alpha >= 0.5"),
    }
    out.update(cov)
    if albedo:
        out["green_exceeds_red"] = bool(albedo[1] > albedo[0])

    # The binary-alpha question, answered rather than assumed. NOTE the clip
    # spread alone cannot tell "hard binary" from "soft fringe that sits
    # entirely above both thresholds" -- Norway Spruce has 78 distinct alpha
    # levels but every intermediate one is >= 179, so both clips select the
    # same texels and the spread is 0.00. The level count is reported so the
    # distinction is visible rather than hidden behind the spread.
    spread = abs(out["opaque_pct_clip01"] - out["opaque_pct_clip05"])
    out["clip_spread_pct"] = round(spread, 2)
    levels = int(np.unique((alpha * 255.0).round().astype(np.uint8)).size)
    out["alpha_distinct_levels"] = levels
    out["alpha_frac_fully_opaque"] = round(float((alpha >= 1.0).mean()), 4)
    out["alpha_frac_fully_clear"] = round(float((alpha <= 0.0).mean()), 4)
    out["alpha_is_effectively_binary"] = bool(spread < 5.0)

    # --- the applicability gate, and it FAILS CLOSED ---------------------
    # Fail-closed means: coverage is reported as canopy density ONLY when we
    # can positively confirm a real alpha mask AND a Masked blend that tests
    # it. An UNKNOWN blend mode (material unreadable, or none supplied) is not
    # a confirmation, so it counts as a reason -- previously it was skipped,
    # which failed OPEN on exactly the "blend mode UNREADABLE" state main()
    # anticipates.
    reasons = []
    if levels <= 1:
        reasons.append(
            "alpha channel is CONSTANT ({0} level) -- this texture carries "
            "no mask, so a coverage percentage measures nothing".format(levels))
    if blend_mode is None:
        reasons.append(
            "consuming material's blend mode is UNKNOWN (unreadable, or no "
            "material supplied) -- an alpha test cannot be confirmed, so "
            "coverage is not treated as canopy density")
    elif "Masked" not in str(blend_mode):
        reasons.append(
            "consuming material is {0}, not BLEND_Masked -- no alpha test "
            "happens, so coverage is not canopy density".format(blend_mode))
    out["blend_mode"] = blend_mode
    out["coverage_applicable"] = not reasons
    out["coverage_not_applicable_because"] = reasons or None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", action="append", default=None,
                    help="/Game path to a tree StaticMesh (repeatable).")
    ap.add_argument("--atlas", action="append", default=None,
                    help="/Game path to a foliage atlas Texture2D.")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)

    trees = args.tree or DEFAULT_TREES
    atlases = args.atlas or DEFAULT_ATLASES

    os.makedirs(MEASURED, exist_ok=True)
    os.makedirs(TEXDIR, exist_ok=True)

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("READ-ONLY on the world: loads assets and exports textures; "
          "places nothing, saves no package.")
    print("trees   : {0}".format(len(trees)))
    print("atlases : {0}".format(len(atlases)))
    print("")

    results = {"trees": [], "atlases": [], "incumbent": INCUMBENT}
    failed = 0
    stopped = False

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        remote.open_command_connection(node["node_id"])

        def run(src):
            r = remote.run_command(src, unattended=True,
                                   exec_mode=remote_exec.MODE_EXEC_FILE)
            return bootstrap._collect_output(r) if r else ""

        # --- meshes, one load per call, RAM checked before each -----------
        for path in trees:
            free, _total = resource_guard.available_gb()
            if free < FLOOR_GB:
                print("STOP: {0:.2f} GB free is below the {1:.1f} GB floor. "
                      "Partial run DECLARED, not silently truncated."
                      .format(free, FLOOR_GB))
                stopped = True
                break
            text = run(mrm.PAYLOAD.format(path=path, marker=mrm.MARKER))
            row = mrm._parse(text)
            # THE CLASS IS NOT AN ASSUMPTION. The first run of this tool fed
            # these paths to StaticMeshEditorSubsystem and got "Failed to
            # convert parameter 'static_mesh'" -- because all four supplied
            # tree variants are SkeletalMesh, and only the Instances/ parts
            # are StaticMesh. A tool that reports LOD/triangle nulls without
            # saying WHY reads as a broken measurement instead of a fact
            # about the asset.
            itext = run(INFOPAYLOAD.format(path=path, marker=INFOMARKER))
            info = _parse_info(itext)
            if row is not None and info and info.get("ok"):
                row["asset_class"] = info.get("asset_class")
                row["scatterable_as_foliage"] = (
                    info.get("asset_class") == "StaticMesh")
            if row is None:
                row = {"path": path, "ok": False,
                       "error": "no parseable result (could not look)"}
            if not row.get("ok"):
                failed += 1
            else:
                ext = row.get("extent_cm") or [0, 0, 0]
                org = row.get("origin_cm") or [0, 0, 0]
                row["height_m"] = round(2.0 * ext[2] / 100.0, 3)
                row["width_m"] = round(2.0 * max(ext[0], ext[1]) / 100.0, 3)
                # Pivot: horizontal offset of the bounds centre from origin,
                # and where the base sits relative to it. Same convention as
                # measure_rock_meshes, so the numbers are comparable.
                row["pivot_offset_xy_m"] = round(
                    ((org[0] ** 2 + org[1] ** 2) ** 0.5) / 100.0, 4)
                row["base_offset_z_m"] = round((org[2] - ext[2]) / 100.0, 4)
            row["free_gb_before"] = round(free, 2)
            results["trees"].append(row)
            print("  {0:<34} {1}".format(
                path.rsplit("/", 1)[-1],
                "ok" if row.get("ok") else "FAILED: {0}".format(
                    row.get("error"))))

        # --- atlases: read the material, export, then measure offline -----
        print("")
        for spec in atlases:
            if isinstance(spec, str):
                spec = {"texture": spec, "material": None}
            path = spec["texture"]
            name = path.rsplit("/", 1)[-1]
            blend = None
            if spec.get("material"):
                itext = run(INFOPAYLOAD.format(path=spec["material"],
                                               marker=INFOMARKER))
                j = _parse_info(itext)
                if j and j.get("ok"):
                    blend = j.get("blend_mode")
                    print("  {0:<34} material {1}".format(
                        name, blend or "blend mode UNREADABLE"))
            dest = os.path.join(TEXDIR, name + ".png").replace("\\", "/")
            text = run(TEXPAYLOAD.format(path=path, dest=dest,
                                         marker=TEXMARKER))
            got = _parse_tex(text)
            if got is None:
                results["atlases"].append(
                    {"path": path, "error": "no parseable export result"})
                failed += 1
                print("  {0:<34} EXPORT: could not look".format(name))
                continue
            if not got.get("ok") or not os.path.exists(dest):
                results["atlases"].append(
                    {"path": path,
                     "error": got.get("error") or "export produced no file"})
                failed += 1
                print("  {0:<34} EXPORT FAILED: {1}".format(
                    name, got.get("error")))
                continue
            stats = measure_atlas(dest, blend_mode=blend)
            stats["path"] = path
            stats["material"] = spec.get("material")
            results["atlases"].append(stats)
            if stats.get("error"):
                failed += 1
                print("  {0:<34} MEASURE FAILED: {1}".format(
                    name, stats["error"]))
            else:
                print("  {0:<34} exported and measured".format(name))
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print("")
    print("wrote {0}".format(os.path.relpath(args.out, REPO_ROOT)))

    # ---- report ---------------------------------------------------------
    print("")
    print("MESHES  (incumbent fir_tree_01: {0:.2f} m tall, LOD0 {1:,} tris)"
          .format(INCUMBENT["height_m"], INCUMBENT["lod0_triangles"]))
    def _f(v, fmt="{0:.2f}"):
        # A missing measurement prints as "--", never as 0. Formatting None
        # as a number is how "I could not look" becomes "it is zero".
        return "--" if v is None else fmt.format(v)

    print("  {0:<30} {1:>8} {2:>7} {3:>8} {4:>7} {5:>13}".format(
        "mesh", "class", "height", "pivotXY", "lods", "lod0 tris"))
    for r in results["trees"]:
        if not r.get("ok"):
            print("  {0:<30} FAILED: {1}".format(
                r.get("path", "?").rsplit("/", 1)[-1], r.get("error")))
            continue
        tris = r.get("lod_triangles") or []
        cls = (r.get("asset_class") or "?")
        print("  {0:<30} {1:>8} {2:>7} {3:>7} {4:>8} {5:>13}".format(
            r["path"].rsplit("/", 1)[-1],
            cls.replace("Mesh", ""),
            _f(r.get("height_m")) + "m",
            _f(r.get("pivot_offset_xy_m"), "{0:.3f}") + "m",
            _f(r.get("lod_count"), "{0:d}"),
            "{0:,}".format(tris[0]) if tris else "--"))
        if r.get("lod_screen_sizes"):
            print("      screen sizes {0}".format(
                [round(v, 3) for v in r["lod_screen_sizes"]]))
        if tris:
            print("      lod tris     {0}".format(tris))
        # LOD GROUP and SLOTS. The group decides whether the vendor's
        # screen sizes are authoritative or are about to be overridden by
        # an engine default, so it is printed for every mesh rather than
        # only when it looks interesting. Three states, kept distinct:
        # a named group, NAME_None (the mesh supplies nothing), and
        # unreadable -- which prints as "COULD NOT READ", never as None.
        _lg = r.get("lod_group")
        if _lg is None:
            _lgs = "COULD NOT READ ({0})".format(
                r.get("lod_group_error", "no reason given"))
        elif _lg in ("", "None", "NAME_None"):
            _lgs = ("NAME_None -- mesh supplies NO defaults, so screen "
                    "sizes and cull distance must be declared explicitly")
        else:
            _lgs = "{0} -- engine group may OVERRIDE the vendor chain".format(_lg)
        print("      lod group    {0}".format(_lgs))
        print("      slots        {0}".format(_f(r.get("material_slots"),
                                                 "{0:d}")))
        if r.get("scatterable_as_foliage") is False:
            print("      NOT SCATTERABLE AS FOLIAGE: {0} is not a "
                  "StaticMesh. The foliage system instances StaticMesh only, "
                  "so this cannot join the 153,796-instance forest as "
                  "shipped.".format(cls))

    print("")
    print("ATLASES (incumbent: {0}% opaque, albedo {1}, alpha BINARY)".format(
        INCUMBENT["atlas_opaque_pct"], INCUMBENT["albedo_rgb"]))
    for r in results["atlases"]:
        nm = r.get("path", "?").rsplit("/", 1)[-1]
        if r.get("error"):
            print("  {0:<34} {1}".format(nm, r["error"]))
            continue
        print("  {0:<34} {1}x{2}   material {3}".format(
            nm, r["size"][0], r["size"][1], r.get("blend_mode") or "?"))
        if r.get("coverage_applicable"):
            print("      opaque  {0:.2f}% at clip 0.5   {1:.2f}% at clip 0.1"
                  "   ({2} alpha levels, {3:.1%} fully clear)".format(
                      r["opaque_pct_clip05"], r["opaque_pct_clip01"],
                      r["alpha_distinct_levels"],
                      r["alpha_frac_fully_clear"]))
        else:
            print("      COVERAGE NOT APPLICABLE -- not reported as canopy "
                  "density:")
            for why in r.get("coverage_not_applicable_because") or []:
                print("        - {0}".format(why))
            print("      (raw alpha, diagnostic only: {0:.2f}% >= 0.5 over "
                  "{1} distinct levels)".format(
                      r["opaque_pct_clip05"], r["alpha_distinct_levels"]))
        print("      albedo  {0}   green>red = {1}".format(
            r["albedo_rgb_where_opaque"], r.get("green_exceeds_red")))
        print("      over    {0}".format(r.get("albedo_denominator")))

    print("")
    print("COVERAGE IS ONE TERM OF THREE. Screen density is "
          "(coverage x cards x card area); only coverage is measured here. "
          "On 2026-08-14 a 2.6x SPARSER atlas produced a DENSER canopy "
          "because it carried more cards. The render A/B decides, not this "
          "table.")

    if stopped:
        return 4
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
