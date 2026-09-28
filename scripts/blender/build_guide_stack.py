"""build_guide_stack.py — put the demo's NON-BAKED groom stack on our authored
hair, and export.

    blender.exe --background <authored.blend> --python this.py -- \
        <demo.blend> <out.abc> [out.blend] [guide_every]

WHY THIS STACK AND NOT THE OTHER ONE. The demo has two kinds of groom:

    Metahuman Curly Hair   303 authored -> 31,570 evaluated, and the
                           interpolation modifier replays a DISK BAKE from
                           the author's own blendcache. Clearing the bake
                           leaves 1.018 points per curve -- the bake WAS the
                           hair, and UE asserts CurveNumVertices >= 2.

    Ponytail               9,904 authored -> 9,966 evaluated, ~41 points per
                           curve. Dense hair authored directly, plus a sparse
                           guides object; the stack ADDS the guide curves and
                           weights them. Nothing is interpolated, so there is
                           nothing to bake and it computes live.

Our own authoring makes dense strands, which is exactly what the second kind
wants. So this replicates Ponytail's stack, in its order:

    Set Hair Curve Profile
    Add Guide Object
    Shrinkwrap Hair Curves
    Attach Hair Curves to Surface
    Merge Guide and Weight it

ONLY THOSE FIVE. An earlier attempt added every node group that arrived as an
append dependency, including `GE_Set Guides Distances and Weights`, which is a
SUB-group used inside Merge Guide -- adding it as a top-level modifier is
running an inner stage twice with no inputs.

GUIDES ARE A DECIMATED COPY OF THE HAIR, which is what a guide set is: the
same shape at lower density, sharing its roots and its surface.

VERIFIED BEFORE EXPORT, in this order: points per curve (the check that
crashed an editor when it was missing), then the crown band, then the
attribute set.
"""

import json
import os
import sys

import bpy
import mathutils

STACK = [
    "Set Hair Curve Profile",
    "Add Guide Object",
    "Shrinkwrap Hair Curves",
    "Attach Hair Curves to Surface",
    "Merge Guide and Weight it",
]

# BISECTING THE STACK, WITHOUT EDITING THE LIST.
# Measured 2026-08-21: this stack does not merely add guides, it CHANGES THE
# HAIRCUT -- Blender's raw curves hang down and the exported groom renders
# swept back (_verify/20260821_artdirect/SHEET_three_shapes.png). Two of the
# five nodes can move geometry, `Shrinkwrap Hair Curves` and `Attach Hair
# Curves to Surface`, and Attach is REQUIRED: without the stack the groom
# imports and binds cleanly and draws nothing at all.
#
# So the stack needs bisecting, and a bisect that edits the list is a bisect
# whose runs cannot be told apart afterwards. Naming skipped nodes in the
# environment keeps the default byte-identical and puts the variant in the
# report, the same reason author_hero_hair.py takes HAIR_<KEY> overrides.
SKIPPED = [s.strip() for s in os.environ.get("GUIDESTACK_SKIP", "").split(",")
           if s.strip()]
if SKIPPED:
    _unknown = [s for s in SKIPPED if s not in STACK]
    if _unknown:
        # Fail closed. A typo'd node name would silently skip nothing and the
        # run would be recorded as a variant that was never actually tried.
        raise SystemExit("GUIDESTACK_SKIP names nodes that are not in the "
                         "stack: %s (stack is %s)" % (_unknown, STACK))
    STACK = [n for n in STACK if n not in SKIPPED]


def z_band(ob, dg=None):
    src = ob.evaluated_get(dg) if dg is not None else ob
    mw = ob.matrix_world
    pts = src.data.points
    if not len(pts):
        return None
    zs = [(mw @ mathutils.Vector(p.position)).z for p in pts]
    return [round(min(zs), 3), round(max(zs), 3)]


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(tail) < 2:
        print("__GUIDESTACK__" + json.dumps(
            {"ok": False, "error": "need: <demo.blend> <out.abc> [out.blend] [n]"}))
        return
    demo, out_abc = tail[0], tail[1]
    out_blend = tail[2] if len(tail) > 2 else ""
    guide_every = int(tail[3]) if len(tail) > 3 else 40

    # `skip_requested` and `stack` land in the report so an .abc can be traced
    # to the variant that produced it, rather than to whoever remembers the run.
    # NOT `skipped` -- that key already means "in the stack but absent from the
    # demo .blend", and this key overwrote it on its first run, which would have
    # hidden the fact that two nodes never load at all.
    rep = {"ok": False, "out": out_abc, "guide_every": guide_every,
           "skip_requested": SKIPPED, "stack": list(STACK)}

    curves = [o for o in bpy.data.objects if o.type == "CURVES"
              and len(o.data.curves) > 0]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not curves or not meshes:
        rep["error"] = ("need authored hair and a head; found %d curves objects "
                        "with geometry, %d meshes" % (len(curves), len(meshes)))
        print("__GUIDESTACK__" + json.dumps(rep))
        return
    hair = max(curves, key=lambda o: len(o.data.curves))
    head = hair.data.surface or max(meshes, key=lambda o: len(o.data.vertices))
    rep["hair"] = hair.name
    rep["head"] = head.name
    rep["authored_curves"] = len(hair.data.curves)
    rep["authored_points"] = len(hair.data.points)

    hz = [(head.matrix_world @ v.co).z for v in head.data.vertices]
    rep["head_z"] = [round(min(hz), 3), round(max(hz), 3)]

    # ---- guides: every Nth curve of the hair ------------------------------
    src = hair.data
    n_curves = len(src.curves)
    keep = list(range(0, n_curves, max(1, guide_every)))
    offsets = [c.first_point_index for c in src.curves]
    sizes = [c.points_length for c in src.curves]

    gdata = bpy.data.hair_curves.new(hair.name + "_guides")
    gob = bpy.data.objects.new(hair.name + "_guides", gdata)
    bpy.context.scene.collection.objects.link(gob)
    gob.parent = head
    gdata.surface = head
    gdata.surface_uv_map = src.surface_uv_map
    gdata.add_curves([sizes[i] for i in keep])
    w = 0
    for i in keep:
        for k in range(sizes[i]):
            gdata.points[w].position = src.points[offsets[i] + k].position
            try:
                gdata.points[w].radius = src.points[offsets[i] + k].radius
            except Exception:
                pass
            w += 1
    # Carry the root UVs across: a guide with no root UV is not a guide the
    # weighting stage can use.
    try:
        s_uv = src.attributes.get("groom_root_uv")
        if s_uv is not None:
            g_uv = gdata.attributes.get("groom_root_uv")
            if g_uv is None:
                g_uv = gdata.attributes.new("groom_root_uv", "FLOAT_VECTOR", "CURVE")
            for gi, i in enumerate(keep):
                g_uv.data[gi].vector = s_uv.data[i].vector
            rep["guide_root_uv"] = len(keep)
    except Exception as exc:
        rep["guide_root_uv_error"] = str(exc)
    rep["guides"] = {"object": gob.name, "curves": len(gdata.curves),
                     "points": len(gdata.points)}

    # ---- append exactly the five groups -----------------------------------
    before = set(g.name for g in bpy.data.node_groups)
    try:
        with bpy.data.libraries.load(demo, link=False) as (s, d):
            d.node_groups = [n for n in STACK if n in s.node_groups]
            rep["requested"] = [n for n in STACK if n in s.node_groups]
    except Exception as exc:
        rep["error"] = "append raised: %s: %s" % (type(exc).__name__, exc)
        print("__GUIDESTACK__" + json.dumps(rep))
        return
    rep["appended"] = sorted(set(g.name for g in bpy.data.node_groups) - before)
    missing = [n for n in STACK if bpy.data.node_groups.get(n) is None]
    rep["absent_after_append"] = missing

    # NOT EVERY GROUP IN THE STACK LIVES IN THE .BLEND. `Shrinkwrap Hair
    # Curves` and `Attach Hair Curves to Surface` are Blender's own essentials
    # assets, so they cannot be appended from the demo file and their absence
    # is not a defect.
    #
    # Their jobs are to push roots onto the surface and to compute surface
    # attachment. OUR HAIR ALREADY HAS BOTH: it was authored by rooting at
    # scalp vertex positions, and it carries groom_root_uv written from the
    # head's own UV map. So skipping them is a justified reduction rather than
    # a workaround, and it is recorded as one.
    #
    # The two that MUST be present are the ones that produce the attributes a
    # groom is missing without them.
    REQUIRED = {"Add Guide Object", "Merge Guide and Weight it"}
    lost_required = [n for n in missing if n in REQUIRED]
    if lost_required:
        rep["error"] = ("these are REQUIRED and absent after append: %s"
                        % lost_required)
        print("__GUIDESTACK__" + json.dumps(rep))
        return
    rep["skipped"] = {n: ("Blender essentials asset, not in the .blend; our "
                          "roots are already on the surface with root UVs")
                      for n in missing}

    # ---- add what we have, IN ORDER, and wire it --------------------------
    wired = []
    for name in [n for n in STACK if bpy.data.node_groups.get(n) is not None]:
        m = hair.modifiers.new(name=name, type="NODES")
        m.node_group = bpy.data.node_groups[name]
        try:
            items = [i for i in m.node_group.interface.items_tree
                     if getattr(i, "in_out", "") == "INPUT"]
        except Exception:
            continue
        for it in items:
            ident = getattr(it, "identifier", None)
            if ident is None or getattr(it, "socket_type", "") != "NodeSocketObject":
                continue
            label = (getattr(it, "name", "") or "").lower()
            # WIRE BY GROUP, NOT BY SUBSTRING. "Add Guide Object" names its
            # input plainly `Object` and it wants the GUIDES; a
            # `"guide" in label` rule put the head there, and the stack still
            # produced all four guide attributes because Merge Guide's socket
            # IS called Curves_Guides. A wrong wire that the output does not
            # punish is the kind that survives to production.
            if name == "Add Guide Object":
                val = gob
            elif "guide" in label:
                val = gob
            else:
                val = head
            try:
                m.properties.inputs[ident]["value"] = val
                wired.append("%s.%s = %s" % (name, getattr(it, "name", ident),
                                             val.name))
            except Exception as exc:
                wired.append("%s.%s FAILED %s" % (name, ident, exc))
    rep["wired"] = wired
    rep["modifiers"] = [m.name for m in hair.modifiers]

    # ---- verify, in the order that matters --------------------------------
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    try:
        ev = hair.evaluated_get(dg)
        n_c, n_p = len(ev.data.curves), len(ev.data.points)
        rep["evaluated"] = {"curves": n_c, "points": n_p,
                            "points_per_curve": round(n_p / max(1, n_c), 3),
                            "attrs": [a.name for a in ev.data.attributes]}
        rep["evaluated_z"] = z_band(hair, dg)
    except Exception as exc:
        rep["error"] = "evaluate raised: %s" % exc
        print("__GUIDESTACK__" + json.dumps(rep))
        return

    ppc = rep["evaluated"]["points_per_curve"]
    if ppc < 2.0:
        rep["error"] = ("REFUSE: %.3f points per curve. UE asserts "
                        "CurveNumVertices >= 2 (GroomBuilder.cpp:2403) and "
                        "crashes on import." % ppc)
        print("__GUIDESTACK__" + json.dumps(rep))
        return
    crown = rep["evaluated_z"][1] - rep["head_z"][1]
    rep["crown_delta_cm"] = round(crown, 3)

    have = set(rep["evaluated"]["attrs"])
    want = {"groom_is_guide", "groom_guide_id", "groom_guide_weights",
            "groom_guide_closest"}
    rep["guide_attrs_present"] = sorted(want & have)
    rep["guide_attrs_missing"] = sorted(want - have)

    # Name the attributes for the exporter, only those that exist.
    try:
        gp = hair.GroomProperty
        gp.att_groom_root_uv = "groom_root_uv"
        gp.att_groom_width = "radius"
        for attr, prop in (("groom_is_guide", "att_groom_guide"),
                           ("groom_guide_id", "att_groom_id"),
                           ("groom_guide_weights", "att_groom_guide_weights"),
                           ("groom_guide_closest", "att_groom_closest_guides")):
            if attr in have:
                setattr(gp, prop, attr)
        rep["groom_property_set"] = True
    except Exception as exc:
        rep["groom_property_error"] = str(exc)

    if out_blend:
        try:
            bpy.ops.wm.save_as_mainfile(filepath=out_blend)
            rep["saved"] = out_blend
        except Exception as exc:
            rep["save_error"] = str(exc)

    for o in bpy.context.selected_objects:
        o.select_set(False)
    hair.select_set(True)
    bpy.context.view_layer.objects.active = hair
    os.makedirs(os.path.dirname(out_abc) or ".", exist_ok=True)
    try:
        res = bpy.ops.groom.buttonexport(
            filepath=out_abc, check_existing=False, groom_scale=1.0,
            groom_width_scale=True, groom_radius_to_diameter=True,
            groom_animation=False, node_execution=False)
        rep["operator_result"] = list(res)
    except Exception as exc:
        rep["error"] = "export raised: %s: %s" % (type(exc).__name__, exc)
        print("__GUIDESTACK__" + json.dumps(rep))
        return
    rep["bytes"] = os.path.getsize(out_abc) if os.path.isfile(out_abc) else 0
    rep["ok"] = rep["bytes"] > 0
    print("__GUIDESTACK__" + json.dumps(rep))


main()
