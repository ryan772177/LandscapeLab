"""probe_groom_exporter.py — how is GroomExporter actually driven headlessly?

READ-ONLY. Saves nothing, exports nothing, mutates nothing. The point is to
learn the call before making it, because the export is the step that writes a
file and the file is what a whole ingest chain then trusts.

WHAT IT ASKS
    - the add-on module, its version, and where it lives on disk
    - every bpy.ops.groom.* operator with its parameter signature
    - scene / object / window-manager property groups the add-on registered,
      since an operator that takes no arguments is almost always reading its
      settings from a property group somewhere
    - the export NODE GROUPS in this file, because the add-on's own operator
      list (add_export_node, add_attribute_node) says the configuration is
      authored as nodes rather than passed as arguments
"""

import json

import bpy

out = {"blender": bpy.app.version_string}

# --- the add-on itself -------------------------------------------------
try:
    import addon_utils
    for m in addon_utils.modules():
        nm = getattr(m, "__name__", "")
        if "groom" in nm.lower():
            enabled, loaded = addon_utils.check(nm)
            bl = getattr(m, "bl_info", {}) or {}
            out["addon"] = {
                "module": nm, "enabled": enabled, "loaded": loaded,
                "version": str(bl.get("version")),
                "blender_min": str(bl.get("blender")),
                "name": bl.get("name"),
                "file": getattr(m, "__file__", None)}
except Exception as exc:
    out["addon_error"] = str(exc)

# --- operator signatures ----------------------------------------------
ops = {}
try:
    for o in dir(bpy.ops.groom):
        try:
            fn = getattr(bpy.ops.groom, o)
            rna = fn.get_rna_type()
            params = []
            for p in rna.properties:
                if p.identifier == "rna_type":
                    continue
                rec = {"id": p.identifier, "type": p.type,
                       "description": (p.description or "")[:80]}
                if hasattr(p, "default"):
                    try:
                        rec["default"] = (list(p.default)
                                          if hasattr(p.default, "__len__")
                                          and not isinstance(p.default, str)
                                          else p.default)
                    except Exception:
                        pass
                params.append(rec)
            ops[o] = {"description": (rna.description or "")[:120],
                      "params": params}
        except Exception as exc:
            ops[o] = {"error": str(exc)}
except Exception as exc:
    out["ops_error"] = str(exc)
out["operators"] = ops

# --- registered property groups ---------------------------------------
# An operator with no parameters reads its settings from somewhere; these are
# the usual somewheres, and naming them beats guessing at call time.
for holder_name, holder in (("scene", bpy.context.scene),
                            ("window_manager", bpy.context.window_manager)):
    found = {}
    try:
        for attr in dir(holder):
            if attr.startswith("__") or attr.startswith("bl_"):
                continue
            low = attr.lower()
            if "groom" in low or "export" in low or "hair" in low:
                try:
                    v = getattr(holder, attr)
                except Exception as exc:
                    found[attr] = "<raise: %s>" % exc
                    continue
                rec = {"type": type(v).__name__}
                # If it is a property group, list its own fields and values.
                try:
                    if hasattr(v, "bl_rna") and not callable(v):
                        rec["fields"] = {}
                        for p in v.bl_rna.properties:
                            if p.identifier == "rna_type":
                                continue
                            try:
                                pv = getattr(v, p.identifier)
                                if not callable(pv):
                                    rec["fields"][p.identifier] = str(pv)[:60]
                            except Exception:
                                pass
                except Exception:
                    pass
                found[attr] = rec
    except Exception as exc:
        found["__error__"] = str(exc)
    out[holder_name + "_props"] = found

# --- export nodes authored in this file -------------------------------
groups = {}
for ng in bpy.data.node_groups:
    hits = []
    for n in ng.nodes:
        label = "%s|%s|%s" % (n.bl_idname, n.name, getattr(n, "label", ""))
        if "export" in label.lower() or "groom" in label.lower():
            rec = {"name": n.name, "bl_idname": n.bl_idname,
                   "label": getattr(n, "label", "")}
            # An export node's settings are its inputs' default values.
            try:
                rec["inputs"] = {
                    i.name: (str(getattr(i, "default_value", None))[:60])
                    for i in n.inputs}
            except Exception:
                pass
            hits.append(rec)
    if hits:
        groups[ng.name] = hits
out["export_nodes"] = groups
out["node_group_names"] = sorted(g.name for g in bpy.data.node_groups)

print("__GEXP__" + json.dumps(out, indent=2))
