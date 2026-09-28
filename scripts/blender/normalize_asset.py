"""normalize_asset.py — split a vendor multi-object file into per-object
FBXs with a FOLIAGE-CONVENTION PIVOT, and report what it measured.

    blender --background --factory-startup --python-exit-code 1 \
        --python normalize_asset.py \
        -- <source-file> <out-dir> [--only NAME[,NAME...]]

(--python-exit-code 1 matters: without it Blender exits 0 even when this
script raises, so the caller must ALSO treat a missing __NORMALIZE_JSON__
marker in stdout as failure.)

WHY THIS EXISTS — and it is not tidiness.

The vendor files lay their objects out SIDE BY SIDE in one scene, the way
a human wants to see a set. `fir_tree_01_c_LOD0` sits at x = 9.25 m in
its own file; `grass_medium_01_large_a_LOD0` sits at x = -2.55 m. Import
that straight into UE and the StaticMesh keeps the offset: measured on
the live editor, fir_tree_01_c_LOD0 came back with its geometry 12.41 m
from its own pivot.

Nothing errors. The asset imports, binds its materials, and reports every
check green. What it does at runtime is this:

  * every instance is displaced 12.41 m from the point the placement
    script computed — so the slope and height masks that decided WHERE a
    tree may grow are evaluated at one place and the tree appears at
    another, which on a 30-degree face is 6 m of altitude,
  * random yaw sweeps the geometry around a 12.41 m radius CIRCLE rather
    than spinning it about its trunk,
  * align_to_normal tilts about that far-away pivot, so a tree on a slope
    levers itself into the ground or into the air,
  * and for GPU grass there is no per-instance correction available at
    all: GrassVariety has no pivot offset, so the density mask and the
    visible grass simply disagree.

This is the 6.2 class exactly — the call succeeded, the value landed, the
meaning was wrong.

WHY IT CANNOT BE FIXED AT IMPORT
FbxStaticMeshImportData.import_translation looks like the answer and is
not. One FBX yields ALL of its objects as separate StaticMeshes in a
single import, and import_translation is a property of the IMPORT, so it
applies the same offset to every object. Each object here needs a
different one. The fix has to happen before the file reaches UE, which
means one file per object.

WHAT "FOLIAGE CONVENTION" MEANS HERE
Pivot at the BASE CENTRE: x and y at the bounding-box centre, z at the
bounding-box MINIMUM. Not the bounding-box centre in z — a plant is
placed by where it meets the ground, and a centre pivot buries half of
it. This is what UE's own foliage content uses and what
align_to_surface assumes.

TRANSFORM POLICY (audit F1). The bake subtracts a WORLD-space offset
from LOCAL vertex coordinates, which is only meaningful when
matrix_world is identity or translation-only. Translation is folded in
exactly (v' = v + t - c). Any object whose matrix_world carries
rotation or scale is REFUSED, per object, with the matrix in the
report row: baking a rotation into vertex positions without rotating
custom split normals silently wrecks foliage shading, and this script
will not do that implicitly. If a vendor file genuinely ships rotated
objects, extending this is a deliberate decision, not a default.

VERIFICATION IS PART OF THE OPERATION, not a later step (lesson 13).
The in-memory base centre is checked to be at the origin BEFORE export;
after each export the file is re-read from disk and the pivot
re-measured; an object whose re-read centre is not within 1 mm of the
intended pivot is reported as FAILED and its file is left for
inspection rather than silently trusted. A normalisation that quietly
did nothing would look exactly like a normalisation that worked, and a
run that processed ZERO objects is a failure, not a pass.

UNITS. The source files declare METRIC / 1.0 / METERS, and the exporter
runs with apply_unit_scale off and global_scale 1.0 so that a metre in
stays a metre out. UE's FBX importer then applies its own 100x to
centimetres. CAVEAT (lesson 9): the re-read below uses Blender's own
importer, so a unit convention Blender round-trips symmetrically would
pass here even if UE read it differently — the authoritative size/pivot
check is the UE-side StaticMesh measurement, which is what caught the
12.41 m offset in the first place. path_mode="STRIP" drops texture
paths on purpose; materials are bound pipeline-side.

SCOPE (conduct rule 1). <out-dir> must resolve inside REPO_ROOT, which
is derived from this script's own location (REPO_ROOT/scripts/blender/).
Anything else is refused before a single directory is created. Existing
per-object FBXs in <out-dir> ARE overwritten — that is the idempotence
contract (hard rule 3), recorded as audit ruling F8.
"""

import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

MARKER = "__NORMALIZE_JSON__"
TOL_M = 0.001
LIN_TOL = 1e-6  # tolerance for "matrix_world linear part is identity"

# scripts/blender/normalize_asset.py -> two dirnames up is REPO_ROOT.
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _args():
    if "--" not in sys.argv:
        raise SystemExit(
            "REFUSE: no '--' in argv; usage: blender --background "
            "--factory-startup --python-exit-code 1 --python "
            "normalize_asset.py -- <source-file> <out-dir> [--only A,B]")
    argv = sys.argv[sys.argv.index("--") + 1:]
    if len(argv) < 2:
        raise SystemExit("usage: -- <source-file> <out-dir> [--only A,B]")
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        only = set(argv[i + 1].split(","))
        argv = argv[:i] + argv[i + 2:]
    return argv[0], argv[1], only


def _contained(path, root):
    """True iff path resolves inside root. Case-insensitive (Windows);
    a drive mismatch (ValueError from commonpath) is 'outside'."""
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False


def _load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    low = path.lower()
    if low.endswith(".fbx"):
        if not hasattr(bpy.ops.wm, "fbx_import"):
            raise RuntimeError("bpy.ops.wm.fbx_import missing")
        bpy.ops.wm.fbx_import(filepath=path)
    elif low.endswith(".gltf") or low.endswith(".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise SystemExit("unsupported source: {0}".format(path))


def _world_bounds(obj):
    """(min, max) in WORLD space. bound_box is LOCAL — applying the
    matrix is not optional; skipping it reports a unit cube for anything
    carrying a scale."""
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def _measure(obj):
    lo, hi = _world_bounds(obj)
    return {
        "dims_m": [round(hi[i] - lo[i], 6) for i in range(3)],
        "bbox_min_m": [round(v, 6) for v in lo],
        "bbox_max_m": [round(v, 6) for v in hi],
        "base_centre_m": [round((lo[0] + hi[0]) * 0.5, 6),
                          round((lo[1] + hi[1]) * 0.5, 6),
                          round(lo[2], 6)],
    }


def _translation_only(m):
    """True iff the 3x3 linear part of m is identity within LIN_TOL —
    i.e. the matrix carries at most a translation."""
    for r in range(3):
        for c in range(3):
            want = 1.0 if r == c else 0.0
            if abs(m[r][c] - want) > LIN_TOL:
                return False
    return True


def _deselect_all():
    # Direct loop, not bpy.ops.object.select_all: op polls can fail in
    # --background, and this cannot.
    for o in bpy.context.scene.objects:
        o.select_set(False)


def main():
    src, out_dir, only = _args()

    out_abs = os.path.abspath(out_dir)
    if not _contained(out_abs, REPO_ROOT):
        raise SystemExit(
            "REFUSE: out-dir {0} resolves outside REPO_ROOT {1} "
            "(conduct rule 1) — nothing was created.".format(
                out_abs, REPO_ROOT))

    _load(src)

    # Names, not object references: every _load() below wipes the scene
    # and frees the Object pointers (audit F2). Blender object names are
    # unique within a file and the import is deterministic.
    mesh_names = [o.name for o in bpy.context.scene.objects
                  if o.type == "MESH"]
    if not mesh_names:
        raise SystemExit(
            "REFUSE: no MESH objects in {0} — refusing a vacuous pass "
            "(audit F4).".format(src))
    if only:
        unmatched = sorted(only - set(mesh_names))
        if unmatched:
            raise SystemExit(
                "REFUSE: --only names not present in source: {0}; "
                "source has: {1} (audit F4).".format(
                    unmatched, sorted(mesh_names)))

    os.makedirs(out_abs, exist_ok=True)

    report = {"source": src, "out_dir": out_abs,
              "unit_system": bpy.context.scene.unit_settings.system,
              "unit_scale_length":
                  bpy.context.scene.unit_settings.scale_length,
              "objects": [], "failed": []}

    for name in mesh_names:
        if only and name not in only:
            continue

        # Fresh scene per object: the previous iteration's re-read
        # verify replaced the scene, and a shared-datablock mutation
        # must never leak into another object's export.
        _load(src)
        obj = bpy.context.scene.objects.get(name)
        if obj is None or obj.type != "MESH":
            row = {"object": name, "file": None, "ok": False,
                   "dims_m": None, "source_offset_m": 0.0,
                   "why": "object not found on deterministic reload "
                          "of source"}
            report["objects"].append(row)
            report["failed"].append(name)
            continue

        before = _measure(obj)
        offset = before["base_centre_m"]
        src_off = round(math.hypot(offset[0], offset[1]), 6)

        # Audit F1: a WORLD offset may only be folded into LOCAL vertex
        # coordinates when matrix_world is translation-only. Refuse
        # rotation/scale rather than silently bake a wrong pivot (and
        # wreck custom split normals rotating positions without them).
        M = obj.matrix_world.copy()
        if not _translation_only(M):
            row = {"object": name, "file": None, "ok": False,
                   "dims_m": before["dims_m"],
                   "source_offset_m": src_off,
                   "matrix_world": [list(r) for r in M],
                   "why": "matrix_world carries rotation/scale; baking "
                          "a world offset into local vertices would be "
                          "wrong — REFUSED, nothing exported. Extend "
                          "the bake deliberately if this is real."}
            report["objects"].append(row)
            report["failed"].append(name)
            continue

        # Audit F5: never mutate a datablock another object also uses.
        datablock_copied = False
        if obj.data.users > 1:
            obj.data = obj.data.copy()
            datablock_copied = True

        # Translation-only: world = local + t, so the exact bake is
        # v' = v + t - c, then clear the object transform. Translating
        # the OBJECT instead would leave the offset in the matrix and
        # the exporter would bake it straight back in.
        t = (M[0][3], M[1][3], M[2][3])
        for v in obj.data.vertices:
            v.co.x += t[0] - offset[0]
            v.co.y += t[1] - offset[1]
            v.co.z += t[2] - offset[2]
        obj.matrix_world = Matrix.Identity(4)  # explicit, not in-place
        obj.data.update()
        bpy.context.view_layer.update()  # bound_box refresh (audit F6)

        after = _measure(obj)

        # Lesson 13: build the disproof into the operation. If the bake
        # did not land the base centre on the origin IN MEMORY, refuse
        # to export at all.
        pre_err = max(abs(v) for v in after["base_centre_m"])
        if pre_err > TOL_M:
            row = {"object": name, "file": None, "ok": False,
                   "dims_m": after["dims_m"],
                   "source_offset_m": src_off,
                   "pivot_error_m": round(pre_err, 6),
                   "why": "in-memory bake missed origin by "
                          "{0:.4f} m — nothing exported".format(pre_err)}
            report["objects"].append(row)
            report["failed"].append(name)
            continue

        _deselect_all()
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        dst = os.path.join(out_abs, name + ".fbx")
        bpy.ops.export_scene.fbx(
            filepath=dst,
            use_selection=True,
            object_types={"MESH"},
            apply_unit_scale=False,
            global_scale=1.0,
            apply_scale_options="FBX_SCALE_NONE",
            bake_space_transform=False,
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            use_tspace=True,
            path_mode="STRIP",
            add_leaf_bones=False,
            bake_anim=False,
        )

        row = {
            "object": name,
            "file": dst,
            "dims_m": after["dims_m"],
            "pivot_world_base_centre_m": [round(v, 6) for v in offset],
            "pivot_shift_applied_m":
                [round(t[i] - offset[i], 6) for i in range(3)],
            "source_offset_m": src_off,
            "datablock_copied": datablock_copied,
        }

        # Audit F4: an exporter that wrote nothing must fail loudly,
        # not crash the re-read or vanish into a pass.
        if not os.path.isfile(dst):
            row["ok"] = False
            row["why"] = "exporter reported no error but wrote no file"
            report["objects"].append(row)
            report["failed"].append(name)
            continue

        # RE-READ FROM DISK. The in-memory numbers are what we intended;
        # only the file is what UE will actually see. (This wipes the
        # scene; the top of the next iteration reloads the source.)
        _load(dst)
        back = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        row["reimported_objects"] = len(back)
        if len(back) != 1:
            row["ok"] = False
            row["why"] = "re-read produced {0} objects".format(len(back))
        else:
            chk = _measure(back[0])
            row["verified_dims_m"] = chk["dims_m"]
            row["verified_base_centre_m"] = chk["base_centre_m"]
            err = max(abs(v) for v in chk["base_centre_m"])
            dim_err = max(abs(chk["dims_m"][i] - after["dims_m"][i])
                          for i in range(3))
            row["pivot_error_m"] = round(err, 6)
            row["dim_error_m"] = round(dim_err, 6)
            row["ok"] = bool(err <= TOL_M and dim_err <= TOL_M)
            if not row["ok"]:
                row["why"] = ("pivot off by {0:.4f} m / dims off by "
                              "{1:.4f} m after re-read".format(err,
                                                               dim_err))
        report["objects"].append(row)
        if not row["ok"]:
            report["failed"].append(name)

    # Audit F4: zero processed objects is a FAILURE, not a pass.
    report["ok"] = bool(report["objects"]) and not report["failed"]
    print("")
    # "processed", not "normalised": report["objects"] carries a row for
    # every object touched, INCLUDING the refused/not-exported ones (object
    # not found :239, rotation/scale :261, in-memory miss :297, exporter
    # wrote nothing :337). The per-row OK/FAIL below says which is which.
    print("processed {0} object(s) from {1} (see per-row OK/FAIL below)".format(
        len(report["objects"]), os.path.basename(src)))
    for row in report["objects"]:
        print("  {0:<34} {1}  dims={2}  was {3:.2f} m off origin".format(
            row["object"], "OK " if row["ok"] else "FAIL",
            row["dims_m"], row["source_offset_m"]))
    print(MARKER + json.dumps(report))


main()
