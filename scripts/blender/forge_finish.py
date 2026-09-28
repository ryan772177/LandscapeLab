"""Forge stage 4-6: retopo/decimate, base-centre pivot, UV state. Headless Blender.

RUN AS:
    blender --background --python scripts/blender/forge_finish.py -- \
        --in <mesh.obj> --out-fbx <mesh.fbx> --report <report.json> \
        --max-tris 60000 --asset-class hero_prop

⛔ THIS STAGE IS MANDATORY AND IT IS WHY.
TRELLIS returns marching-cubes geometry. The 2026-08-30 church was WATERTIGHT
and carried **genus 59** -- chi = -116 -- meaning 59 handles of topological
noise. "Watertight" was true and was not the whole story, which is the exact
shape of failure this project keeps paying for: two instruments agreeing while
a third question goes unasked. A generated mesh NEVER ships raw.

WHAT IS REPORTED, BEFORE AND AFTER, so the stage is auditable rather than
assumed: verts, edges, faces, triangles, Euler characteristic, genus, the
boundary/non-manifold edge counts, and the UV state.

THE TARGET IS READ FROM THE RECIPE, NEVER TYPED HERE.
`recipes/perf_budgets.json` -> `asset_rules.max_tris.<class>`. The caller
passes the class and the number; this script refuses if it was not given one.

⛔ GENUS IS REPORTED, NOT SILENTLY FIXED. Decimation reduces triangle count and
usually reduces handle count with it, but it is not a topology repair and must
not be described as one. If genus stays high after this stage, that is a
finding for the caller, not something to hide behind a passing triangle count.
"""
import argparse
import json
import os
import sys

import bpy


def _argv():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def _clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _stats(obj):
    """Topology of the evaluated mesh. Every number measured, none inferred."""
    me = obj.data
    V = len(me.vertices)
    E = len(me.edges)
    F = len(me.polygons)
    tris = sum(max(0, len(p.vertices) - 2) for p in me.polygons)

    # Edge use: how many faces reference each edge. 1 = boundary,
    # >2 = non-manifold. Counted from polygon edge_keys rather than from
    # me.edges, because a loose edge carries no face and would read as a
    # boundary that is not part of the surface.
    counts = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            k = (min(ek), max(ek))
            counts[k] = counts.get(k, 0) + 1
    boundary = sum(1 for v in counts.values() if v == 1)
    nonmanifold = sum(1 for v in counts.values() if v > 2)

    chi = V - E + F
    watertight = (boundary == 0 and nonmanifold == 0)
    # genus is only meaningful for a closed orientable surface
    genus = ((2 - chi) // 2) if watertight else None

    return {
        "verts": V, "edges": E, "faces": F, "triangles": tris,
        "euler_characteristic": chi,
        "boundary_edges": boundary, "nonmanifold_edges": nonmanifold,
        "watertight": watertight,
        "genus": genus,
        "_genus_note": ("(2 - chi) / 2, valid only for a closed orientable "
                        "surface; None when not watertight"),
        "uv_layers": [l.name for l in me.uv_layers],
        "has_uvs": len(me.uv_layers) > 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out-fbx", dest="out_fbx", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--max-tris", type=int, required=True)
    ap.add_argument("--asset-class", required=True)
    args = ap.parse_args(_argv())

    rep = {"ok": False, "error": None, "src": args.src,
           "asset_class": args.asset_class, "max_tris": args.max_tris}
    try:
        _clear()
        bpy.ops.wm.obj_import(filepath=args.src)
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if not objs:
            raise RuntimeError("no mesh imported from %s" % args.src)
        if len(objs) > 1:
            # Join rather than silently take the first -- a forge that drops
            # geometry it did not expect produces a plausible smaller asset.
            bpy.ops.object.select_all(action="DESELECT")
            for o in objs:
                o.select_set(True)
            bpy.context.view_layer.objects.active = objs[0]
            bpy.ops.object.join()
            objs = [bpy.context.view_layer.objects.active]
        obj = objs[0]
        bpy.context.view_layer.objects.active = obj

        rep["before"] = _stats(obj)

        # ---- DECIMATE to the recipe's ceiling ---------------------------
        tris0 = rep["before"]["triangles"]
        if tris0 > args.max_tris:
            ratio = float(args.max_tris) / float(tris0)
            m = obj.modifiers.new(name="ForgeDecimate", type="DECIMATE")
            m.decimate_type = "COLLAPSE"
            m.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=m.name)
            rep["decimate_ratio"] = round(ratio, 6)
            rep["decimated"] = True
        else:
            rep["decimate_ratio"] = 1.0
            rep["decimated"] = False
            rep["_no_decimate_why"] = (
                "already at or under the class ceiling; the stage still ran "
                "and still reported, because 'not needed' and 'not done' must "
                "not look the same in the log")

        # ---- PIVOT TO BASE CENTRE ---------------------------------------
        # X/Y at the footprint centre, Z at the lowest vertex, so the asset
        # sits ON the ground when placed at a location rather than halfway
        # through it.
        me = obj.data
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        zs = [v.co.z for v in me.vertices]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        zmin = min(zs)
        for v in me.vertices:
            v.co.x -= cx
            v.co.y -= cy
            v.co.z -= zmin
        me.update()
        obj.location = (0.0, 0.0, 0.0)
        rep["pivot"] = {
            "rule": "base-centre: XY at footprint centre, Z at lowest vertex",
            "moved_by": [round(-cx, 6), round(-cy, 6), round(-zmin, 6)],
        }

        # ---- UVs -----------------------------------------------------
        # ⛔ TRELLIS RETURNS NO UVs AT ALL. Measured 2026-08-30: the church's
        # `uv_layers` is empty, which means the mesh CANNOT BE TEXTURED. A
        # hero prop delivered without UVs is half an asset, and the gap is
        # invisible in a grey-material render -- it looks finished.
        #
        # Smart UV Project is a MACHINE unwrap and is honest about that: it is
        # adequate for a greybox-grade generated asset and is NOT a substitute
        # for an authored layout on anything that gets hand-painted. The
        # report records which it is so nobody later mistakes one for the
        # other.
        if not obj.data.uv_layers:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=1.15192,
                                     island_margin=0.003)
            bpy.ops.object.mode_set(mode="OBJECT")
            rep["uv_action"] = "smart_project (MACHINE unwrap, greybox-grade)"
        else:
            rep["uv_action"] = "kept the incoming UVs"

        rep["after"] = _stats(obj)
        zs2 = [v.co.z for v in obj.data.vertices]
        rep["pivot"]["z_min_after"] = round(min(zs2), 6)
        rep["pivot"]["base_at_origin"] = abs(min(zs2)) < 1e-5

        rep["bbox_after"] = {
            "min": [round(min(v.co[i] for v in obj.data.vertices), 5)
                    for i in range(3)],
            "max": [round(max(v.co[i] for v in obj.data.vertices), 5)
                    for i in range(3)],
        }

        # ---- EXPORT ------------------------------------------------------
        os.makedirs(os.path.dirname(args.out_fbx), exist_ok=True)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        # ⛔ THE FBX ROUND TRIP ROTATES -90 DEGREES ABOUT X, AND THE EXPORT
        # AXIS FLAGS DO NOT CHANGE IT.
        #
        # Measured 2026-08-30, twice. UE reported raw extents
        # X 76.3 / Y 91.47 / Z 39.49 cm against a Blender bbox of
        # 0.763 / 0.395 / 0.915: UE's Y held Blender's Z and UE's Z held
        # Blender's Y. Exporting again with axis_up='Z', axis_forward='X'
        # produced the IDENTICAL UE extents -- UE applies its own Y-up to
        # Z-up conversion regardless of what the file declares, so the flags
        # are not the lever.
        #
        # WHY IT MATTERED: the scale-to-ruling step then stretched the
        # church's DEPTH to the ruled 1341.3 cm and reported
        # church_over_chalet = 2.5 -- a PERFECT SCORE FOR RULING 1 ON THE
        # WRONG AXIS. Triangle count, watertightness, pivot and UVs are all
        # orientation-blind, so nothing else in the forge could have caught
        # it. An orientation gate now runs at import and refuses.
        #
        # THE FIX IS IN THE GEOMETRY, WHERE THE ROTATION IS. Rotating -90
        # about X maps Z -> Y, so the round trip's +90 restores it and the
        # asset lands upright with its own bbox intact. Applied AFTER every
        # measurement above, so the reported bbox stays the honest
        # Blender-space one that the import is checked against.
        # Rotate the VERTICES, not the object.
        # `obj.rotation_euler` + `transform_apply` depends on operator context
        # and did NOT take in background mode -- the report logged the
        # rotation as applied while the exported FBX was unchanged and UE
        # returned byte-identical bounds across three attempts. Writing the
        # coordinates is the same technique the pivot step above uses and has
        # no context to fail.
        #
        # -90 about X:  (x, y, z) -> (x, z, -y)
        for _v in obj.data.vertices:
            _y, _z = _v.co.y, _v.co.z
            _v.co.y = _z
            _v.co.z = -_y
        obj.data.update()
        _rz = [v.co.z for v in obj.data.vertices]
        _ry = [v.co.y for v in obj.data.vertices]
        rep["export_rotation"] = {
            "applied_deg": [-90.0, 0.0, 0.0],
            "method": "direct vertex write (operator transform_apply is "
                      "context-dependent and silently did not take headless)",
            "z_extent_after_rot": round(max(_rz) - min(_rz), 5),
            "y_extent_after_rot": round(max(_ry) - min(_ry), 5),
            "_expect": "z_extent should now equal the pre-rotation Y "
                       "(0.395) and y_extent the pre-rotation Z (0.915)",
            "_why": "the FBX round trip rotates +90 about X; this cancels it "
                    "so UE receives the asset upright. Applied after all "
                    "measurement, so bbox_after remains Blender-space.",
        }
        if abs((max(_rz) - min(_rz)) - (rep["bbox_after"]["max"][1]
                                        - rep["bbox_after"]["min"][1])) > 1e-4:
            raise RuntimeError(
                "the pre-export rotation did not take: z extent %.5f does not "
                "match the pre-rotation Y extent. Refusing to export a mesh "
                "whose orientation is not what the report claims."
                % (max(_rz) - min(_rz)))

        bpy.ops.export_scene.fbx(filepath=args.out_fbx, use_selection=True,
                                 apply_unit_scale=True,
                                 object_types={"MESH"},
                                 mesh_smooth_type="FACE")
        rep["out_fbx"] = args.out_fbx
        rep["out_fbx_bytes"] = os.path.getsize(args.out_fbx)

        # NAMED `tri_within_budget`, NOT `within_budget`.
        # It is a TRIANGLE claim and says nothing about topology. The church
        # met this budget at genus 59 with every handle intact, and a reader
        # who saw `within_budget: true` beside a decimation report would
        # reasonably conclude the mesh had been cleaned up. It had been made
        # SMALLER, which is a different claim (Ryan, 2026-08-30).
        rep["tri_within_budget"] = rep["after"]["triangles"] <= args.max_tris

        # ⛔ SAY WHAT THE STAGE DID **NOT** ACHIEVE, IN THE REPORT ITSELF.
        # Collapse decimation preserves topology, so genus survives it intact:
        # measured 2026-08-30, genus 59 before and 59 after, chi -116 both
        # times, while triangles fell 381,228 -> 59,998. A reader who checks
        # only `within_budget` would conclude the mesh was cleaned up. It was
        # made SMALLER, which is a different claim.
        gb = (rep.get("before") or {}).get("genus")
        ga = (rep.get("after") or {}).get("genus")
        rep["genus_before_after"] = [gb, ga]
        rep["genus_reduced"] = (gb is not None and ga is not None and ga < gb)
        if gb is None or ga is None:
            rep["_genus_finding"] = (
                "GENUS NOT MEASURED (before=%r after=%r), so whether handles "
                "remain is UNKNOWN -- this is not a claim that they were "
                "closed, nor that they survived." % (gb, ga))
        elif not rep["genus_reduced"]:
            rep["_genus_finding"] = (
                "DECIMATION DID NOT REDUCE GENUS and was never going to -- "
                "edge collapse preserves topology. The triangle budget is met "
                "and the handles remain. Closing them needs a real retopology "
                "or hole-filling pass, which is a separate unit and is NOT "
                "claimed here.")
        rep["ok"] = True
    except Exception as exc:
        import traceback
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]

    _rdir = os.path.dirname(args.report)
    if _rdir:                    # a bare filename has no dir; makedirs("") raises
        os.makedirs(_rdir, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("__FORGE_FINISH__" + json.dumps(rep))
    # Exit code TRACKS the report: a caller or CI reading $? must see a
    # refusal/exception as failure, not the bare exit 0 Blender gives when
    # main() just returns. The host still gets the marker+JSON above either way.
    sys.exit(0 if rep.get("ok") else 1)


main()
