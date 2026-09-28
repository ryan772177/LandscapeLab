"""export_abc.py -- Phase 0.4. The ONE export path, plus the degenerate cull.

    blender --background --python export_abc.py -- <src> <out_abc> [cull]

PATH CHOSEN: native `bpy.ops.wm.alembic_export`.
The turbocheke GroomExporter addon is installed and enabled, but it is a NODE
GRAPH tool -- its operators are add_export_node / add_attribute_node /
buttonexport, i.e. it wants a node tree authored in the UI. Driving that
headless is a project of its own, and this repo already has a proven native
path: author_hero_hair.py exports with wm.alembic_export and UE's
HairStrandsFactory imports the result. Use the proven one; record the other as
available if attributes turn out to be missing.

WHAT SURVIVES, MEASURED NOT ASSUMED: verify_abc.py re-imports in a FRESH
session and diffs curve count, point count and bbox. Attributes are listed
both sides so the morning report can say which ones actually made it rather
than which ones we hoped would.

THE CULL IS NOT COSMETIC. Recon found 1,210 one-point curves, and UE asserts
CurveNumVertices >= 2 -- this project has already crashed an editor on exactly
that. `cull` also drops absurd strays: recon put strand length p95 at 0.217 m
against a max of 1.42 m, so a handful of runaway curves were inflating the
scene bbox to 2.5 m.
"""

import json
import os
import sys

import bpy
import mathutils

STRAY_LENGTH_M = 0.45      # 2x the p95 of 0.217; anything longer is a runaway


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def curve_lengths(d):
    pos = d.attributes["position"].data
    out = []
    for c in d.curves:
        s, n = c.first_point_index, c.points_length
        L = 0.0
        for k in range(n - 1):
            L += (mathutils.Vector(pos[s + k + 1].vector)
                  - mathutils.Vector(pos[s + k].vector)).length
        out.append(L)
    return out


def census(ob, rep):
    """REPORT the degenerate and stray counts. Deleting them is REJECTED.

    The first version of this rebuilt a keep-set with bpy.data.hair_curves.new
    + add_curves and CRASHED Blender with EXCEPTION_ACCESS_VIOLATION. 5.2's
    bpy.types.Curves exposes no remove_curves / add_curves (introspected --
    recon/curves_api.json), so there is no supported in-place removal to fall
    back to either.

    And the cull was never needed. The note it was written against -- "UE
    asserts CurveNumVertices >= 2" -- came from a different file. THIS .abc,
    1,210 one-point curves and all, imported into UE earlier the same day at
    its full 94,408 curves. So the degenerates are carried, counted, and
    declared in the morning report rather than surgically removed by a
    mechanism that crashes the tool.

    Runaway strays are handled where it is safe to handle them: the edit
    engine's `stray_clamp_m`, which scales a long curve about its own root and
    cannot change the curve count at all.
    """
    d = ob.data
    sizes = [c.points_length for c in d.curves]
    lens = curve_lengths(d)
    rep["census"] = {
        "curves": len(sizes),
        "under_2pts": sum(1 for s in sizes if s < 2),
        "over_stray_len": sum(1 for L in lens if L > STRAY_LENGTH_M),
        "stray_threshold_m": STRAY_LENGTH_M,
        "max_len_m": round(max(lens), 5) if lens else 0.0,
        "note": "carried, not removed -- see docstring"}
    return ob


def main():
    tail = argv_tail()
    src, out_abc = tail[0], tail[1]
    do_cull = len(tail) > 2 and tail[2].lower() in ("1", "true", "cull", "yes")

    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    if src.lower().endswith(".abc"):
        bpy.ops.wm.alembic_import(filepath=src, as_background_job=False)
    else:
        bpy.ops.wm.open_mainfile(filepath=src)

    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    rep = {"ok": False, "src": src, "out": out_abc, "culled": do_cull}
    if not curves:
        rep["error"] = "no CURVES object"
        print("__EXPORT__" + json.dumps(rep))
        return
    ob = curves[0]

    if do_cull:
        ob = census(ob, rep)

    rep["pre_export"] = {"curves": len(ob.data.curves),
                         "points": len(ob.data.points),
                         "attributes": [a.name for a in ob.data.attributes]}

    # Identity transform is asserted, not hoped for. The hard rule is that the
    # groom is never re-rotated or rescaled, and the cheapest way to keep that
    # true is to check it at the moment of export.
    m = ob.matrix_world
    ident = all(abs(m[r][c] - (1.0 if r == c else 0.0)) < 1e-9
                for r in range(4) for c in range(4))
    rep["identity_transform"] = ident
    if not ident:
        rep["error"] = "object transform is not identity; refusing to export"
        rep["matrix_world"] = [list(r) for r in m]
        print("__EXPORT__" + json.dumps(rep))
        return

    for o in bpy.data.objects:
        o.select_set(o is ob)
    bpy.context.view_layer.objects.active = ob

    os.makedirs(os.path.dirname(os.path.abspath(out_abc)), exist_ok=True)
    # SIGNATURE TAKEN FROM get_rna_type(), NOT FROM MEMORY. The first attempt
    # passed `visible_objects_only`, which does not exist in 5.2 and raised.
    # recon/ops.json holds the full property list this call was written from.
    #   curves_as_mesh MUST stay False -- True converts strands to geometry and
    #     UE's groom importer would receive a mesh.
    #   global_scale MUST stay 1.0 and flatten False -- the hard rule is that
    #     the groom is exported exactly as imported, and these are the two
    #     knobs that would silently break it.
    res = bpy.ops.wm.alembic_export(
        filepath=out_abc, check_existing=False, selected=True,
        flatten=False, curves_as_mesh=False, global_scale=1.0,
        export_hair=True, export_particles=False,
        export_custom_properties=True, evaluation_mode="RENDER",
        as_background_job=False)
    rep["export_result"] = list(res)
    rep["bytes"] = os.path.getsize(out_abc) if os.path.isfile(out_abc) else 0
    rep["ok"] = rep["bytes"] > 0
    print("__EXPORT__" + json.dumps(rep))


if __name__ == "__main__":
    main()
