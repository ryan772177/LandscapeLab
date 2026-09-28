"""snap_curves_to_surface.py — try the operator that should re-seat a groom
on a new surface, headlessly, in both attach modes.

    blender.exe --background <repointed.blend> --python this.py -- <out_prefix>

WHY THIS OPERATOR. Appending the demo's hair object gives a complete groom --
every attribute a rendering groom carries -- and repointing its surface moves
nothing: pointers all name our head and the thing still evaluates at
Z 131.059..154.735 against a head at 140.878..178.437. Moving the authored
points did not move the output either, so the stack regenerates position from
baked state rather than from the points.

`bpy.ops.curves.snap_curves_to_surface` is the operation that rewrites that
baked state -- it re-derives the roots' attachment against the CURRENT
surface. Its mere existence confirms the mechanism; the question here is
only whether it will run without a UI.

BOTH MODES ARE RECORDED, NOT JUST THE ONE THAT WORKS. `NEAREST` re-projects
roots to the closest surface point; `DEFORM` carries the strand shape through
the surface change. Across two skulls that differ 1.33x in width and 1.14x in
height they will not agree, and which one preserves the cut better is a thing
we will want on record rather than rediscovered later.

EVERY MODE RUNS ON ITS OWN COPY, so the two results are independent rather
than one applied on top of the other.

THE CHECK IS THE Z BAND, taken before anything is exported: the five-second
question that has caught every previous attempt.
"""

import json
import os
import sys

import bpy
import mathutils


def world_z(ob, dg=None):
    """Z band from the ACTUAL POINTS, never from bound_box.

    bound_box is a cache, and it read 131.059..154.735 to three decimals
    across a repoint, a bbox transform of every authored point, and both
    snap modes -- four operations that cannot all leave a groom identical.
    An invariant that survives changes to its own input is a stale reading,
    not a finding, and this is the second time today that identical numbers
    across a changed variable were the tell.
    """
    src = ob.evaluated_get(dg) if dg is not None else ob
    mw = ob.matrix_world
    try:
        pts = src.data.points
        if len(pts):
            zs = [(mw @ mathutils.Vector(p.position)).z for p in pts]
            return [round(min(zs), 3), round(max(zs), 3)]
    except Exception:
        pass
    corners = [mw @ mathutils.Vector(c) for c in src.bound_box]
    zs = [p.z for p in corners]
    return [round(min(zs), 3), round(max(zs), 3), "FROM BOUND_BOX (cache)"]


def authored_z(ob):
    mw = ob.matrix_world
    zs = [(mw @ mathutils.Vector(p.position)).z for p in ob.data.points]
    return [round(min(zs), 3), round(max(zs), 3)] if zs else None


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    prefix = tail[0] if tail else ""

    rep = {"blend": bpy.data.filepath, "modes": {}}

    curves = [o for o in bpy.data.objects if o.type == "CURVES"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not curves or not meshes:
        rep["error"] = "need a curves object and a head mesh"
        print("__SNAP__" + json.dumps(rep))
        return
    groom = max(curves, key=lambda o: len(o.data.curves))
    # THE TARGET IS THE DECLARED SURFACE, NOT THE BIGGEST MESH.
    # Picking by vertex count chose the DEMO's head_lod0_mesh (24,049) over
    # ours (19,284), then reassigned the surface back to it -- so the first
    # run snapped the groom to the skull it was already on and reported "ON
    # THE HEAD" against that skull. The repoint had already named the right
    # target; asking the biggest mesh was inventing an answer next to a
    # declaration.
    head = groom.data.surface
    if head is None or head.type != "MESH":
        head = max(meshes, key=lambda o: len(o.data.vertices))
        rep["target_from"] = "fallback: largest mesh (no surface declared)"
    else:
        rep["target_from"] = "the curves' declared surface pointer"
    rep["groom"] = groom.name
    rep["head"] = head.name
    rep["head_z"] = world_z(head)
    rep["surface_pointer"] = groom.data.surface.name if groom.data.surface else None

    op = getattr(bpy.ops.curves, "snap_curves_to_surface", None)
    rep["operator_exists"] = op is not None
    if op is None:
        rep["error"] = ("bpy.ops.curves.snap_curves_to_surface is absent in "
                        "this Blender; the mechanism assumption is wrong")
        print("__SNAP__" + json.dumps(rep))
        return
    try:
        rep["operator_params"] = [p.identifier for p in op.get_rna_type().properties
                                  if p.identifier != "rna_type"]
    except Exception as exc:
        rep["operator_params"] = "unreadable: %s" % exc

    dg = bpy.context.evaluated_depsgraph_get()
    rep["before"] = {"authored_z": authored_z(groom),
                     "evaluated_z": world_z(groom, dg)}

    for mode in ("NEAREST", "DEFORM"):
        entry = {}
        try:
            # A FRESH COPY PER MODE. Running the second mode on the first
            # mode's result would report a compound of the two and read like
            # a single measurement.
            dup_data = groom.data.copy()
            dup = groom.copy()
            dup.data = dup_data
            dup.name = "%s_%s" % (groom.name, mode)
            bpy.context.scene.collection.objects.link(dup)
            dup.data.surface = head
            if head.data.uv_layers.active is not None:
                dup.data.surface_uv_map = head.data.uv_layers.active.name

            for o in bpy.context.selected_objects:
                o.select_set(False)
            dup.select_set(True)
            bpy.context.view_layer.objects.active = dup

            entry["poll"] = None
            override = {"object": dup, "active_object": dup,
                        "selected_objects": [dup],
                        "selected_editable_objects": [dup]}
            try:
                with bpy.context.temp_override(**override):
                    entry["poll"] = bool(op.poll())
                    res = op(attach_mode=mode)
                    entry["result"] = list(res)
            except Exception as exc:
                entry["error"] = "%s: %s" % (type(exc).__name__, exc)

            dg2 = bpy.context.evaluated_depsgraph_get()
            entry["authored_z"] = authored_z(dup)
            entry["evaluated_z"] = world_z(dup, dg2)
            hz = rep["head_z"]
            ez = entry["evaluated_z"]
            entry["on_head"] = bool(ez[0] >= hz[0] - 6.0 and ez[1] <= hz[1] + 12.0
                                    and ez[1] > hz[0] + 0.4 * (hz[1] - hz[0]))
            entry["verdict"] = ("ON THE HEAD" if entry["on_head"]
                                else "not on the head")
            if prefix:
                path = "%s_%s.blend" % (prefix, mode.lower())
                try:
                    # Save a per-mode file so a later stage can pick either
                    # without re-running the snap.
                    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
                    entry["blend"] = path
                except Exception as exc:
                    entry["save_error"] = str(exc)
        except Exception as exc:
            entry["fatal"] = "%s: %s" % (type(exc).__name__, exc)
        rep["modes"][mode] = entry

    print("__SNAP__" + json.dumps(rep, default=str))


main()
