"""probe_modifier_api.py — find how Blender 5.2 stores Geometry Nodes values.

WHY THIS EXISTS. In Blender 4.x a Geometry Nodes modifier's inputs were ID
properties, read as `mod["Socket_2"]`. In 5.2 that raises
`bpy_struct.keys(): this type doesn't support IDProperties`, so every socket
in an enumeration came back unreadable. Rather than guess the replacement --
an API remembered is an API guessed -- this asks the running Blender what a
NodesModifier actually exposes.

Read-only. Prints, saves nothing.
"""

import json
import sys

import bpy

out = {"blender": bpy.app.version_string, "version": list(bpy.app.version)}

mod = None
owner = None
for ob in bpy.data.objects:
    for m in ob.modifiers:
        if m.type == "NODES" and getattr(m, "node_group", None) is not None:
            mod, owner = m, ob
            break
    if mod:
        break

if mod is None:
    out["error"] = "no Geometry Nodes modifier in this file"
else:
    out["probe_object"] = owner.name
    out["probe_modifier"] = mod.name
    out["modifier_type"] = type(mod).__name__
    # Everything non-callable and not dunder, with its type.
    props = {}
    for name in dir(mod):
        if name.startswith("__"):
            continue
        try:
            v = getattr(mod, name)
        except Exception as exc:
            props[name] = "<raise: %s>" % exc
            continue
        if callable(v):
            continue
        props[name] = type(v).__name__
    out["properties"] = props

    # The RNA definition is the authoritative list, including anything dir()
    # would miss, and it carries each property's description.
    try:
        rna = {}
        for p in mod.bl_rna.properties:
            if p.identifier in ("rna_type",):
                continue
            rna[p.identifier] = {"type": p.type,
                                 "description": (p.description or "")[:120]}
        out["bl_rna_properties"] = rna
    except Exception as exc:
        out["bl_rna_error"] = str(exc)

    # Candidate containers, probed by name rather than assumed.
    for cand in ("node_group_inputs", "inputs", "socket_values",
                 "bake_directory", "bakes", "panels"):
        if hasattr(mod, cand):
            try:
                v = getattr(mod, cand)
                out.setdefault("candidates", {})[cand] = {
                    "type": type(v).__name__,
                    "len": (len(v) if hasattr(v, "__len__") else None)}
            except Exception as exc:
                out.setdefault("candidates", {})[cand] = "<raise: %s>" % exc

print("__PROBE__" + json.dumps(out, indent=2))
