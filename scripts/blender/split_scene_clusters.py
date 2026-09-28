"""split_scene_clusters.py -- group a multi-object vendor SCENE into buildings
and export one FBX per building, base-centre pivot.

    blender.exe --background --factory-startup --python-exit-code 1 \
        --python split_scene_clusters.py -- <source> <out-dir> \
        [--threshold 0.10] [--anchor-name NAME] [--anchor-height-m 11.0] \
        [--span-reject 5.0] [--inventory-only]

WHY THIS EXISTS AND WHY IT IS NOT normalize_asset.py
`normalize_asset.py` splits a vendor file PER OBJECT. That is right for a set of
trees laid out side by side. It is wrong for a village DIORAMA, where one
building is 20-30 separate objects (walls, roof, door, shutters) and per-object
export yields 73 meaningless fragments.

This groups first, by proximity on the GROUND PLANE, then exports one mesh per
group. The pivot convention is normalize_asset.py's -- BASE CENTRE, asserted
after the bake rather than assumed -- because that is already this project's
convention and a second convention would be two lists that must agree.

⛔ SCENE-SPANNING OBJECTS DESTROY PROXIMITY CLUSTERING, and this file has them.
Measured in Willage_in_alps.glb: three objects are 1.45 units long on one axis
and 0.01 on the others -- cables or fence lines running the length of the
village. Single-link clustering chains through them, so at any threshold that
groups a building it ALSO merges every building into one. They are rejected by
ASPECT: an object whose longest dimension exceeds --span-reject times its
second-longest is not a building part. They are reported, never silently
dropped -- a filter that hides what it removed cannot be checked.

UNITS. glTF declares metres and Blender imports it as such. This file does not
BEHAVE like metres (the whole village is 1.46 units across), so a uniform scale
is applied to bring a named anchor object to a declared real height. The factor
is REPORTED, and the anchor's post-scale dimensions are reported with it, so the
caller can see whether the result is plausible instead of trusting the number.

OUTPUT: one FBX per group, plus __SPLIT_JSON__ + a JSON object on stdout.
(--python-exit-code 1 matters: without it Blender exits 0 when this raises, so
the caller must ALSO treat a missing marker as failure.) A PARTIAL failure (an
FBX of 0 bytes, or textures that did not write) sets `ok:false` in the JSON but
still prints the marker and exits 0 -- so the caller MUST also check the `ok`
field, not just the marker/exit code.
"""

import json
import math
import os
import sys

import bpy
from mathutils import Vector

TOL_M = 1e-4


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def world_bounds(obj):
    """(min, max) in WORLD space. bound_box is LOCAL; applying the matrix is
    not optional -- skipping it reports a unit cube for anything scaled."""
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def vert_bounds(obj):
    """(min, max) in WORLD space, computed from the VERTICES.

    ⛔ NOT bound_box. `obj.bound_box` is a CACHED DERIVED RECORD of the mesh,
    and after `obj.data.transform(...)` moves the vertices it can still report
    the pre-move box even through a view_layer update. That is how the pivot
    bake below first failed: the mesh had been centred correctly and the
    verification, reading the stale cache, reported the base centre 6.101763 m
    out and refused the export.

    The vertices are the thing the exporter writes. Verify against those.
    """
    mw = obj.matrix_world
    pts = [mw @ v.co for v in obj.data.vertices]
    if not pts:
        return [0.0] * 3, [0.0] * 3
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def dims(obj):
    lo, hi = world_bounds(obj)
    return [hi[i] - lo[i] for i in range(3)]


def tri_count(obj):
    me = obj.data
    n = 0
    for p in me.polygons:
        n += max(0, len(p.vertices) - 2)
    return n


def main():
    a = argv_after_ddash()
    if len(a) < 2:
        raise SystemExit("need <source> <out-dir>")
    src, out_dir = a[0], a[1]

    def opt(name, default, cast=float):
        if name in a:
            return cast(a[a.index(name) + 1])
        return default

    thresh = opt("--threshold", 0.10)
    span_reject = opt("--span-reject", 5.0)
    anchor_name = opt("--anchor-name", "", str)
    anchor_h = opt("--anchor-height-m", 11.0)
    inventory_only = "--inventory-only" in a

    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(src)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=src)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=src)
    else:
        raise SystemExit("unsupported source extension %r" % ext)

    # ⛔ UNPARENT FIRST, KEEPING THE WORLD TRANSFORM.
    # The glTF importer parents every object to a root empty that carries the
    # Y-up -> Z-up conversion AND a scale (measured 0.700 on this file).
    # `transform_apply` bakes only an object's OWN transform, so with the parent
    # still attached matrix_world keeps that residual -- and a translation
    # applied to the mesh data then lands in world space multiplied by it.
    # Measured symptom before this line existed: a base-centre bake that shifted
    # the mesh by exactly 0.700 of the requested amount and tripped its own
    # assertion at 6.101763 m. The assertion was right; the bake was wrong.
    bpy.ops.object.select_all(action="SELECT")
    if bpy.context.selected_objects:
        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.select_all(action="DESELECT")

    meshes = [o for o in bpy.context.scene.objects
              if o.type == "MESH" and len(o.data.polygons) > 0]

    inv, spanning = [], []
    for o in meshes:
        d = dims(o)
        srt = sorted(d, reverse=True)
        second = srt[1] if srt[1] > 1e-9 else 1e-9
        aspect = srt[0] / second
        row = {"name": o.name, "dims": [round(v, 4) for v in d],
               "tris": tri_count(o), "aspect": round(aspect, 1)}
        if aspect >= span_reject:
            spanning.append(row)
        else:
            inv.append(row)

    keep = [o for o in meshes if o.name in {r["name"] for r in inv}]

    # ---- cluster on the GROUND PLANE (Blender is Z-up after glTF import) ----
    cent = []
    for o in keep:
        lo, hi = world_bounds(o)
        cent.append(((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5))
    parent = list(range(len(keep)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(keep)):
        for j in range(i + 1, len(keep)):
            if math.hypot(cent[i][0] - cent[j][0],
                          cent[i][1] - cent[j][1]) <= thresh:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    groups = {}
    for i in range(len(keep)):
        groups.setdefault(find(i), []).append(i)
    groups = sorted(groups.values(), key=len, reverse=True)

    rep = {"source": os.path.basename(src), "threshold": thresh,
           "span_reject_aspect": span_reject,
           "objects_total": len(meshes),
           "objects_clustered": len(keep),
           "rejected_as_scene_spanning": spanning,
           "groups": [], "exports": [], "ok": False}

    for gi, grp in enumerate(groups):
        objs = [keep[i] for i in grp]
        lo = [min(world_bounds(o)[0][k] for o in objs) for k in range(3)]
        hi = [max(world_bounds(o)[1][k] for o in objs) for k in range(3)]
        rep["groups"].append({
            "index": gi, "parts": len(objs),
            "tris": sum(tri_count(o) for o in objs),
            "dims": [round(hi[k] - lo[k], 4) for k in range(3)],
            "members": [o.name for o in objs][:60]})

    if inventory_only:
        # NN13: "found and clustered nothing" is not success.
        rep["ok"] = len(rep.get("groups") or []) > 0
        print("__SPLIT_JSON__" + json.dumps(rep, ensure_ascii=False))
        return

    # ---- which groups to export, and under what names --------------------
    # "--groups 2:chalet,0:church_tower,1:barn"
    spec = opt("--groups", "", str)
    if not spec:
        raise SystemExit("--groups is required unless --inventory-only")
    wanted = []
    for part in spec.split(","):
        gi_str, sep, nm = part.partition(":")
        if (not sep or not nm.strip()
                or not gi_str.strip().lstrip("-").isdigit()):
            raise SystemExit("--groups entries must be 'index:name' (got %r)"
                             % part)
        wanted.append((int(gi_str), nm))

    # Clustering can yield zero groups (all meshes rejected as scene-spanning,
    # or none polygonal); indexing groups then IndexErrors with a raw trace.
    n_groups = len(rep.get("groups") or [])
    if n_groups == 0:
        raise SystemExit("no clusterable objects (all rejected as "
                         "scene-spanning?); nothing to export")
    for gi, _nm in wanted:
        if gi < 0 or gi >= n_groups:
            raise SystemExit("--groups index %d out of range (0..%d)"
                             % (gi, n_groups - 1))

    anchor_idx = int(opt("--anchor-index", wanted[0][0]))
    ai = [i for i, (gi, _n) in enumerate(wanted) if gi == anchor_idx]
    if not ai:
        raise SystemExit("--anchor-index %d is not in --groups" % anchor_idx)
    if anchor_idx < 0 or anchor_idx >= n_groups:
        raise SystemExit("--anchor-index %d out of range (0..%d)"
                         % (anchor_idx, n_groups - 1))

    # THE SCALE FACTOR COMES FROM THE ANCHOR GROUP'S MEASURED HEIGHT, so it is
    # derived from the geometry rather than typed in. Reported with the anchor's
    # resulting footprint so the caller can see whether it is plausible.
    a_h = rep["groups"][anchor_idx]["dims"][2]
    if a_h <= 0:
        raise SystemExit("anchor group %d has zero height" % anchor_idx)
    S = anchor_h / a_h
    a_dims = rep["groups"][anchor_idx]["dims"]
    rep["anchor"] = {"group": anchor_idx, "height_units": a_h,
                     "target_height_m": anchor_h, "scale_factor": round(S, 4),
                     "resulting_dims_m": [round(v * S, 4) for v in a_dims],
                     "resulting_height_m": round(a_h * S, 4)}

    os.makedirs(out_dir, exist_ok=True)

    # ⛔ GIVE PACKED IMAGES A FILE EXTENSION BEFORE EXPORT.
    # glTF embeds images by MIME TYPE, not by filename, so Blender's packed
    # images arrive named "bark_willow_diff_1k" with no extension. The FBX
    # exporter then copies them out under that name and UE'S IMPORTER SKIPS
    # THEM -- measured: 21 MaterialInstanceConstant assets created and ZERO
    # Texture2D, so every material read as present while the buildings were
    # untextured. Nothing errored at either end.
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    saved_imgs = 0
    for img in list(bpy.data.images):
        if img.size[0] == 0 or img.size[1] == 0:
            continue
        ext = ".png" if img.file_format == "PNG" else ".jpg"
        if img.file_format not in ("PNG", "JPEG"):
            img.file_format = "PNG"
            ext = ".png"
        base = os.path.splitext(os.path.basename(img.name))[0]
        dst = os.path.join(tex_dir, base + ext)
        try:
            img.filepath_raw = dst
            img.save()
            # Confirm the file actually landed rather than trusting save() did
            # not raise (contrast the FBX path, which reads getsize).
            if os.path.isfile(dst) and os.path.getsize(dst) > 0:
                saved_imgs += 1
            else:
                rep.setdefault("image_save_failures", []).append(
                    "%s: save() ran but %s is missing/empty" % (img.name, dst))
        except Exception as exc:
            rep.setdefault("image_save_failures", []).append(
                "%s: %s" % (img.name, exc))
    rep["images_written"] = saved_imgs
    rep["texture_dir"] = tex_dir

    for gi, nm in wanted:
        objs = [keep[i] for i in groups[gi]]
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        obj.name = nm

        # bake the world transform into the mesh, then scale, then re-bake
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.scale = (S, S, S)
        bpy.ops.object.transform_apply(location=False, rotation=False,
                                       scale=True)

        # BASE-CENTRE PIVOT, the convention normalize_asset.py already uses.
        # Done by moving the MESH DATA rather than by origin_set(BOUNDS), which
        # gives the bbox CENTRE -- half a building too high.
        lo, hi = vert_bounds(obj)
        cx, cy = (lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5
        from mathutils import Matrix
        obj.data.transform(Matrix.Translation((-cx, -cy, -lo[2])))
        obj.data.update()
        obj.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()

        # Build the disproof into the operation (lesson 13): if the base centre
        # did not land on the origin IN MEMORY, refuse to export at all.
        lo2, hi2 = vert_bounds(obj)
        err = max(abs((lo2[0] + hi2[0]) * 0.5),
                  abs((lo2[1] + hi2[1]) * 0.5), abs(lo2[2]))
        d = [hi2[k] - lo2[k] for k in range(3)]
        if err > TOL_M * max(1.0, max(d)):
            raise SystemExit("%s: base centre off by %.6f m after the bake"
                             % (nm, err))

        dst = os.path.join(out_dir, nm + ".fbx")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(
            filepath=dst, use_selection=True, object_types={"MESH"},
            apply_unit_scale=False, global_scale=1.0,
            apply_scale_options="FBX_SCALE_NONE", bake_space_transform=False,
            use_mesh_modifiers=True, mesh_smooth_type="FACE", use_tspace=True,
            # ⛔ NOT path_mode="STRIP" here, which is what normalize_asset.py
            # uses. That is right on the foliage path, where the manifest
            # imports textures separately and the FBX only needs geometry. This
            # is an EVALUATION of a vendor asset: the FBX must be self-contained
            # or the buildings import grey, and grey buildings misrepresent the
            # thing being judged. The glTF's images are packed, so COPY+embed
            # carries them into the FBX.
            # COPY writes the images to disk beside the FBX and references them
            # relatively. embed_textures=True was tried first and UE created the
            # materials but ZERO Texture2D assets -- measured, 25 assets in the
            # folder and not one texture -- so the buildings would have rendered
            # untextured while every material read as present.
            path_mode="COPY", embed_textures=False,
            add_leaf_bones=False, bake_anim=False)

        rep["exports"].append({
            "name": nm, "group": gi, "file": dst,
            "parts_joined": len(objs),
            "tris": tri_count(obj),
            "dims_m": [round(v, 4) for v in d],
            "footprint_x_cm": round(d[0] * 100.0, 1),
            "footprint_y_cm": round(d[1] * 100.0, 1),
            "height_cm": round(d[2] * 100.0, 1),
            "pivot_error_m": round(err, 8),
            "materials": [ms.material.name for ms in obj.material_slots
                          if ms.material][:40],
            "bytes": os.path.getsize(dst) if os.path.isfile(dst) else 0})

    # This tool exists to carry TEXTURES through (materials-present/zero-
    # Texture2D was the defect); so ok must cover texture health, not only that
    # the FBXs are non-empty.
    rep["ok"] = (bool(rep["exports"])
                 and all(e["bytes"] > 0 for e in rep["exports"])
                 and rep.get("images_written", 0) > 0
                 and not rep.get("image_save_failures"))
    print("__SPLIT_JSON__" + json.dumps(rep, ensure_ascii=False))


main()
