"""introspect_ops.py -- what does THIS Blender's exporter actually accept?

    blender --background --python introspect_ops.py -- <out_json>

Written because a guessed keyword (`visible_objects_only`) failed the export
on its first run. The operator's RNA is the contract; the docs and memory are
not. Dumps every property with its type and default for the alembic ops and
for the GroomExporter addon's operators.
"""
import json
import sys

import bpy


def props_of(op):
    # bpy.ops.* is a BPyOpFunction wrapper with no .bl_rna; the RNA comes from
    # get_rna_type(). Measured, after .bl_rna raised on the first attempt.
    rna = op.get_rna_type()
    out = []
    for p in rna.properties:
        if p.identifier == "rna_type":
            continue
        d = {"id": p.identifier, "type": p.type}
        for attr in ("default", "default_flag"):
            if hasattr(p, attr):
                try:
                    v = getattr(p, attr)
                    d["default"] = list(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
                except Exception:
                    pass
                break
        if p.type == "ENUM":
            try:
                d["items"] = [i.identifier for i in p.enum_items]
            except Exception:
                pass
        out.append(d)
    return out


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out = tail[0] if tail else "ops.json"
    rep = {"blender": bpy.app.version_string}
    for name in ("alembic_export", "alembic_import"):
        try:
            rep[name] = props_of(getattr(bpy.ops.wm, name))
        except Exception as exc:
            rep[name] = {"error": str(exc)}
    groom = {}
    if hasattr(bpy.ops, "groom"):
        for o in dir(bpy.ops.groom):
            if o.startswith("_"):
                continue
            try:
                groom[o] = props_of(getattr(bpy.ops.groom, o))
            except Exception as exc:
                groom[o] = {"error": str(exc)}
    rep["groom_addon"] = groom
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print("__OPS__" + json.dumps({"ok": True, "out": out,
                                  "alembic_export_props": [
                                      p["id"] for p in rep["alembic_export"]],
                                  "groom_ops": sorted(groom)}))


if __name__ == "__main__":
    main()
