"""check_repoint_sockets.py — did the surface repoint actually land?

    blender.exe --background <repointed.blend> --python this.py

The repointed groom reported its sockets rewired and then evaluated at
EXACTLY its original Z, 131.059..154.735, against a head at 140.878..178.437.
Two very different explanations produce that:

    (a) the writes never took, and the modifiers still point at the demo head
    (b) the writes took, and these modifiers do not reproject roots at all

Reading the sockets back separates them. The rewire reported success from the
same call that performed it, which is the read-back-what-you-wrote trap this
project keeps paying for -- so this reads them from a fresh file load.
"""

import json

import bpy
import mathutils


out = {"blend": bpy.data.filepath}

curves = [o for o in bpy.data.objects if o.type == "CURVES"]
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if not curves:
    out["error"] = "no curves object"
else:
    groom = max(curves, key=lambda o: len(o.data.curves))
    out["groom"] = groom.name
    out["curves_data_surface"] = (groom.data.surface.name
                                  if groom.data.surface else None)
    out["curves_data_surface_uv"] = groom.data.surface_uv_map or None
    out["parent"] = groom.parent.name if groom.parent else None
    out["meshes_present"] = sorted(o.name for o in meshes)

    mods = []
    for mod in groom.modifiers:
        rec = {"name": mod.name, "type": mod.type,
               "show_viewport": bool(mod.show_viewport)}
        if mod.type == "NODES" and mod.node_group is not None:
            rec["node_group"] = mod.node_group.name
            sockets = {}
            try:
                for it in mod.node_group.interface.items_tree:
                    if getattr(it, "in_out", "") != "INPUT":
                        continue
                    ident = getattr(it, "identifier", None)
                    if ident is None:
                        continue
                    try:
                        d = mod.properties.inputs[ident].to_dict()
                        v = d.get("value")
                        sockets[getattr(it, "name", ident)] = (
                            getattr(v, "name", None) or str(v))
                    except Exception as exc:
                        sockets[getattr(it, "name", ident)] = "<%s>" % exc
            except Exception as exc:
                rec["socket_error"] = str(exc)
            rec["sockets"] = sockets
        mods.append(rec)
    out["modifiers"] = mods

    dg = bpy.context.evaluated_depsgraph_get()
    try:
        ev = groom.evaluated_get(dg)
        pts = [groom.matrix_world @ mathutils.Vector(c) for c in ev.bound_box]
        zs = [p.z for p in pts]
        out["evaluated_z"] = [round(min(zs), 3), round(max(zs), 3)]
        out["evaluated_curves"] = len(ev.data.curves)
    except Exception as exc:
        out["evaluated_error"] = str(exc)

print("__SOCKETS__" + json.dumps(out, default=str))
