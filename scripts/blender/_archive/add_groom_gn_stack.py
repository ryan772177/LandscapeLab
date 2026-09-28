"""add_groom_gn_stack.py — append the demo file's Geometry Nodes groom stack
onto our authored hair, and export.

    blender.exe --background <authoring.blend> --python this.py -- \
        <demo.blend> <out.abc> [strands] [seed]

WHY. Our authored groom has position, radius and root UVs, imports with the
right curve count, has guides synthesised by UE, binds, assigns -- and renders
nothing. Width is eliminated as the cause: at a 0.5 cm radius, five
millimetres and absurd, it still renders nothing.

The remaining difference against a groom that DOES render is its attribute
set. Read off the demo's evaluated curves:

    groom_is_guide  groom_guide_id  groom_guide_weights  groom_guide_closest
    groom_color     groom_AO        rest_position       surface_normal

Ours carries none of those. They are produced by the demo's Geometry Nodes
stack -- "Merge Guide and Weight it" and friends -- which means that stack is
LOAD-BEARING rather than decoration, and authoring raw strands is not enough.

So this appends the node groups from the demo file (using them as the tool
they are, never writing to it) and drives them from our own guides.

THE DEMO FILE IS OPENED READ-ONLY VIA APPEND. No save touches it.
"""

import json
import os
import sys

import bpy

WANTED = [
    "Set Hair Curve Profile",
    "Attach Hair Curves to Surface",
    "Merge Guide and Weight it",
]


def main():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(tail) < 2:
        print("__GNSTACK__" + json.dumps(
            {"ok": False, "error": "need: <demo.blend> <out.abc>"}))
        return
    demo, out_abc = tail[0], tail[1]

    rep = {"ok": False, "demo": demo, "out": out_abc}

    hair_obs = [o for o in bpy.data.objects if o.type == "CURVES"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not hair_obs or not meshes:
        rep["error"] = ("this file needs an authored hair Curves object and "
                        "the head; found %d curves, %d meshes"
                        % (len(hair_obs), len(meshes)))
        print("__GNSTACK__" + json.dumps(rep))
        return
    head = max(meshes, key=lambda o: len(o.data.vertices))
    hair_ob = max(hair_obs, key=lambda o: len(o.data.curves))
    rep["head"] = head.name
    rep["hair"] = hair_ob.name
    rep["hair_curves"] = len(hair_ob.data.curves)

    # ---- append the node groups -------------------------------------------
    before = set(g.name for g in bpy.data.node_groups)
    try:
        with bpy.data.libraries.load(demo, link=False) as (src, dst):
            avail = list(src.node_groups)
            dst.node_groups = [n for n in WANTED if n in avail]
        rep["available_in_demo"] = [n for n in WANTED if n in avail]
        rep["appended"] = sorted(set(g.name for g in bpy.data.node_groups) - before)
    except Exception as exc:
        rep["error"] = "append raised: %s: %s" % (type(exc).__name__, exc)
        print("__GNSTACK__" + json.dumps(rep))
        return
    if not rep["appended"]:
        rep["error"] = ("appended nothing. Wanted %s, demo has %s"
                        % (WANTED, rep.get("available_in_demo")))
        print("__GNSTACK__" + json.dumps(rep))
        return

    # ---- GUIDES: a sparse copy of the hair --------------------------------
    # "Merge Guide and Weight it" needs a guides object to weight against.
    # Ours is a decimated copy of the same strands, which is what a guide set
    # is: the same shape at lower density.
    guides = hair_ob.data.copy()
    guides_ob = bpy.data.objects.new(hair_ob.name + "_guides", guides)
    bpy.context.scene.collection.objects.link(guides_ob)
    guides_ob.parent = head
    guides.surface = head
    guides.surface_uv_map = hair_ob.data.surface_uv_map
    rep["guides_curves"] = len(guides.curves)

    # ---- add the modifiers -------------------------------------------------
    added = []
    for name in rep["appended"]:
        ng = bpy.data.node_groups.get(name)
        if ng is None:
            continue
        m = hair_ob.modifiers.new(name=name, type="NODES")
        m.node_group = ng
        # Wire the sockets this stack needs, by IDENTIFIER, matching on the
        # interface's declared NAME. Identifiers are what a modifier stores;
        # display names are not addressable.
        try:
            items = [i for i in ng.interface.items_tree
                     if getattr(i, "in_out", "") == "INPUT"]
            for it in items:
                nm = (getattr(it, "name", "") or "").lower()
                ident = getattr(it, "identifier", None)
                if ident is None:
                    continue
                val = None
                if "surface" in nm and it.socket_type == "NodeSocketObject":
                    val = head
                elif "guide" in nm and it.socket_type == "NodeSocketObject":
                    val = guides_ob
                if val is not None:
                    try:
                        m.properties.inputs[ident]["value"] = val
                        added.append("%s.%s=%s" % (name, getattr(it, "name", ident),
                                                   val.name))
                    except Exception as exc:
                        added.append("%s.%s FAILED %s" % (name, ident, exc))
        except Exception as exc:
            added.append("%s socket wiring failed: %s" % (name, exc))
    rep["modifiers"] = [m.name for m in hair_ob.modifiers]
    rep["wired"] = added

    dg = bpy.context.evaluated_depsgraph_get()
    try:
        ev = hair_ob.evaluated_get(dg)
        rep["evaluated_curves"] = len(ev.data.curves)
        rep["evaluated_attrs"] = [a.name for a in ev.data.attributes]
    except Exception as exc:
        rep["evaluated_error"] = str(exc)

    # ---- export ------------------------------------------------------------
    try:
        gp = hair_ob.GroomProperty
        gp.att_groom_root_uv = "groom_root_uv"
        gp.att_groom_width = "radius"
        for cand, attr in (("groom_is_guide", "att_groom_guide"),
                           ("groom_guide_id", "att_groom_id"),
                           ("groom_guide_weights", "att_groom_guide_weights"),
                           ("groom_guide_closest", "att_groom_closest_guides")):
            if cand in rep.get("evaluated_attrs", []):
                setattr(gp, attr, cand)
        rep["groom_property"] = {p.identifier: str(getattr(gp, p.identifier))
                                 for p in gp.bl_rna.properties
                                 if p.identifier != "rna_type"}
    except Exception as exc:
        rep["groom_property_error"] = str(exc)

    for o in bpy.context.selected_objects:
        o.select_set(False)
    hair_ob.select_set(True)
    bpy.context.view_layer.objects.active = hair_ob
    os.makedirs(os.path.dirname(out_abc) or ".", exist_ok=True)
    try:
        res = bpy.ops.groom.buttonexport(
            filepath=out_abc, check_existing=False, groom_scale=1.0,
            groom_width_scale=True, groom_radius_to_diameter=True,
            groom_animation=False, node_execution=False)
        rep["operator_result"] = list(res)
    except Exception as exc:
        rep["error"] = "export raised: %s: %s" % (type(exc).__name__, exc)
        print("__GNSTACK__" + json.dumps(rep))
        return
    rep["bytes"] = os.path.getsize(out_abc) if os.path.isfile(out_abc) else 0
    rep["ok"] = rep["bytes"] > 0
    print("__GNSTACK__" + json.dumps(rep))


main()
