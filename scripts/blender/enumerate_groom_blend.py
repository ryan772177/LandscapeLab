"""enumerate_groom_blend.py — read a .blend and dump its groom surface.

RUN IT LIKE THIS, and note what is NOT there:

    blender.exe --background <file.blend> --python this.py -- <out.json>

There is no `--factory-startup`. That is deliberate and load-bearing: the
GroomExporter add-on is installed through user Preferences, and
`--factory-startup` skips user prefs, so the add-on would not register and a
headless export check would report "not installed" about a working install.

IT NEVER SAVES. The two source .blend files are vendor originals under the
hard floor, and this script has no `bpy.ops.wm.save*` call anywhere in it.
Enumeration is read-only by construction rather than by care.

WHAT IT DUMPS, AND WHY EACH PART
--------------------------------
    objects            name, type, parent, bounds, visibility. NAMES COME
                       FROM THE FILE. The brief needs the demo's style
                       variants enumerated so an export can EXCLUDE them,
                       and guessing which objects are variants from their
                       names is how the wrong curves get exported.
    modifiers          every modifier, and for Geometry Nodes every INPUT
                       SOCKET with its name, type, current value and range.
                       This is the knob inventory the authoring loop turns,
                       so it is the actual deliverable of Stage A.
    curves             per Curves object: curve count, total points, bounds.
                       A groom with zero curves after evaluation is the
                       Blender-5.2 health check, and it cannot be answered
                       from the object list alone.
    evaluated          curve counts AFTER depsgraph evaluation, which is
                       what an exporter sees. A file whose Geometry Nodes
                       tree is broken in 5.2 still lists its objects and
                       still reports its authored guide curves; only the
                       evaluated count goes to zero.
    node_health        undefined/missing node types per node group. A node
                       that does not exist in this Blender is reported by
                       name rather than as a generic failure.
    addons             whether GroomExporter registered, and its operators.
"""

import json
import sys

import bpy


def _bounds(ob):
    try:
        pts = [tuple(ob.matrix_world @ v.to_4d().to_3d()) if False else
               tuple(ob.matrix_world @ __import__("mathutils").Vector(c))
               for c in ob.bound_box]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        return {"min": [round(min(xs), 4), round(min(ys), 4), round(min(zs), 4)],
                "max": [round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)],
                "size": [round(max(xs) - min(xs), 4),
                         round(max(ys) - min(ys), 4),
                         round(max(zs) - min(zs), 4)]}
    except Exception as exc:
        return {"error": str(exc)}


def _socket_value(v):
    try:
        if hasattr(v, "__len__") and not isinstance(v, str):
            return [round(float(x), 6) for x in v]
        if isinstance(v, (int, float, bool, str)):
            return v
        if v is None:
            return None
        return str(v)
    except Exception:
        return "<unreadable>"


def _gn_inputs(mod):
    """Every Geometry Nodes input socket with its identifier, type, value and
    declared range. The identifier is what a script must set -- the display
    NAME is not addressable and two sockets may share one.
    """
    out = []
    tree = getattr(mod, "node_group", None)
    if tree is None:
        return out
    try:
        items = [it for it in tree.interface.items_tree
                 if getattr(it, "item_type", "") == "SOCKET"
                 and getattr(it, "in_out", "") == "INPUT"]
    except Exception as exc:
        return [{"error": "interface unreadable: %s" % exc}]
    for it in items:
        ident = getattr(it, "identifier", None)
        rec = {"name": getattr(it, "name", None),
               "identifier": ident,
               "socket_type": getattr(it, "socket_type", None),
               "description": getattr(it, "description", "") or ""}
        for attr in ("min_value", "max_value", "default_value"):
            if hasattr(it, attr):
                rec[attr] = _socket_value(getattr(it, attr))
        if ident is not None:
            # DISTINGUISH "no value stored" FROM "the read failed".
            # The first version printed "<not set on modifier>" for both,
            # which asserts an absence it never established -- and it printed
            # it for EVERY socket in the file, i.e. the read was broken and
            # the output looked like a fully-default modifier stack.
            # BLENDER 5.x STORES THESE ON `mod.properties`, NOT ON `mod`.
            # In 4.x a GN modifier's inputs were ID properties read as
            # `mod["Socket_2"]`; in 5.2 that raises "this type doesn't support
            # IDProperties" for EVERY socket, which the first version of this
            # script reported as "not set" -- an absence it never established.
            # `mod.properties` is a GeometryNodesModifierInterface, found by
            # probing the live NodesModifier rather than by recalling an API.
            try:
                bag = getattr(mod, "properties", None)
                inputs = getattr(bag, "inputs", None) if bag else None
                if inputs is not None:
                    # GeometryNodesInterfaceInputs is KEYED, not iterable:
                    # inputs[identifier] -> an entry carrying the value. The
                    # entry's own shape is not assumed either; whichever of
                    # these attributes exists is what gets reported.
                    # Each entry is an IDPropertyGroup exposing to_dict().
                    # Found by probing the entry object; it has no bl_rna and
                    # no `.value`, so every attribute-name guess returned an
                    # unserialisable object that printed as "<unreadable>"
                    # while the code reported the read had SUCCEEDED.
                    entry = inputs[ident]
                    dv = entry.to_dict() if hasattr(entry, "to_dict") else None
                    rec["stored"] = {k: _socket_value(v)
                                     for k, v in (dv or {}).items()}
                    # The value key is usually "value"; if this group names it
                    # something else, the whole dict is above, unfiltered.
                    val = (dv or {}).get("value", None)
                    rec["current_value"] = _socket_value(val)
                else:
                    rec["current_value"] = _socket_value(mod[ident])
                rec["value_source"] = "modifier override"
            except KeyError:
                rec["current_value"] = None
                rec["value_source"] = ("no override stored; the modifier uses "
                                       "the socket default above")
            except Exception as exc:
                rec["current_value"] = None
                rec["value_source"] = "COULD NOT READ: %s: %s" % (
                    type(exc).__name__, exc)
        out.append(rec)
    return out


def _raw_modifier_items(mod):
    """The modifier's own stored keys, straight from the ID property bag.

    This is the ground truth behind `_gn_inputs`: whatever the interface
    says, THESE are the values actually stored on this modifier. Dumped
    alongside so a disagreement between the two is visible rather than
    resolved silently in favour of whichever was easier to read.
    """
    out = {}
    bag = getattr(mod, "properties", None)
    inputs = getattr(bag, "inputs", None) if bag is not None else None
    if inputs is None:
        # 4.x fallback: the modifier itself was the ID property bag.
        try:
            for k in mod.keys():
                out[k] = _socket_value(mod[k])
        except Exception as exc:
            out["__error__"] = "%s: %s" % (type(exc).__name__, exc)
        return out
    # 5.x: mod.properties.inputs is a collection. The ELEMENT SHAPE IS NOT
    # ASSUMED -- every readable scalar attribute is dumped, so if the value
    # lives under a name this code did not anticipate it still appears in the
    # output instead of vanishing into a guess that returned None.
    try:
        for i, item in enumerate(inputs):
            rec = {}
            for attr in dir(item):
                if attr.startswith("__") or attr in ("bl_rna", "rna_type"):
                    continue
                try:
                    v = getattr(item, attr)
                except Exception:
                    continue
                if callable(v):
                    continue
                rec[attr] = _socket_value(v)
            key = rec.get("identifier") or rec.get("name") or ("input_%d" % i)
            out[str(key)] = rec
    except Exception as exc:
        out["__error__"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def main():
    argv = sys.argv
    out_path = argv[argv.index("--") + 1] if "--" in argv else "out.json"

    rep = {"blend": bpy.data.filepath,
           "blender": bpy.app.version_string,
           "objects": [], "node_health": {}, "addons": {}}

    # --- add-ons, GroomExporter especially ------------------------------
    try:
        import addon_utils
        names = []
        for m in addon_utils.modules():
            nm = getattr(m, "__name__", "")
            enabled, loaded = addon_utils.check(nm)
            if enabled or loaded:
                names.append(nm)
        rep["addons"]["enabled"] = sorted(names)
        rep["addons"]["groom_like"] = [n for n in names
                                       if "groom" in n.lower()
                                       or "alembic" in n.lower()]
    except Exception as exc:
        rep["addons"]["error"] = str(exc)
    # Operators are the headless-usability question: an add-on can register
    # and still expose nothing callable without a UI context.
    ops = []
    for grp in dir(bpy.ops):
        if "groom" in grp.lower() or "hair" in grp.lower():
            try:
                ops += ["bpy.ops.%s.%s" % (grp, o)
                        for o in dir(getattr(bpy.ops, grp))]
            except Exception:
                pass
    rep["addons"]["groom_operators"] = sorted(set(ops))

    dg = bpy.context.evaluated_depsgraph_get()

    for ob in bpy.data.objects:
        rec = {"name": ob.name, "type": ob.type,
               "parent": ob.parent.name if ob.parent else None,
               "hide_viewport": bool(ob.hide_viewport),
               "hide_render": bool(ob.hide_render),
               "in_scene": ob.name in bpy.context.scene.objects,
               "bounds": _bounds(ob),
               "modifiers": []}
        for mod in ob.modifiers:
            mrec = {"name": mod.name, "type": mod.type,
                    "show_viewport": bool(mod.show_viewport)}
            if mod.type == "NODES":
                ng = getattr(mod, "node_group", None)
                mrec["node_group"] = ng.name if ng else None
                mrec["inputs"] = _gn_inputs(mod)
                mrec["raw_items"] = _raw_modifier_items(mod)
            rec["modifiers"].append(mrec)

        if ob.type == "CURVES":
            try:
                c = ob.data
                rec["curves_authored"] = {"curves": len(c.curves),
                                          "points": len(c.points)}
            except Exception as exc:
                rec["curves_authored"] = {"error": str(exc)}
            try:
                ev = ob.evaluated_get(dg)
                rec["curves_evaluated"] = {"curves": len(ev.data.curves),
                                           "points": len(ev.data.points)}
            except Exception as exc:
                rec["curves_evaluated"] = {"error": str(exc)}
        if ob.type == "MESH":
            try:
                rec["mesh"] = {"verts": len(ob.data.vertices),
                               "polys": len(ob.data.polygons)}
            except Exception as exc:
                rec["mesh"] = {"error": str(exc)}
        rep["objects"].append(rec)

    # --- node health: a node type this Blender does not have -------------
    for ng in bpy.data.node_groups:
        bad = []
        for n in ng.nodes:
            if n.bl_idname == "NodeUndefined" or n.type == "UNDEFINED":
                bad.append(n.name)
        rep["node_health"][ng.name] = {
            "nodes": len(ng.nodes),
            "undefined": bad,
            "type": getattr(ng, "bl_idname", "?")}

    rep["summary"] = {
        "objects": len(rep["objects"]),
        "curves_objects": sum(1 for o in rep["objects"] if o["type"] == "CURVES"),
        "mesh_objects": sum(1 for o in rep["objects"] if o["type"] == "MESH"),
        "node_groups": len(rep["node_health"]),
        "node_groups_with_undefined": sum(
            1 for v in rep["node_health"].values() if v["undefined"]),
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print("__ENUM_OK__ %s" % out_path)


main()
