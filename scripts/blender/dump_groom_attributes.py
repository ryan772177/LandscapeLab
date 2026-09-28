"""dump_groom_attributes.py — what does a WORKING groom actually carry?

    blender.exe --background <file.blend> --python this.py -- <object> [<object2> ...]

WHY. A hand-built Curves object exported, imported with the right curve
count, bound, assigned -- and rendered nothing. The curve count matching
proves the geometry survived; it proves nothing about whether the groom has
the ATTRIBUTES a renderer and a binding need. Rather than guess which one is
missing, this reads the attribute set off a groom that is known to work and
prints it beside the candidate's.

Reports both the AUTHORED and the EVALUATED attribute sets, because the
Geometry Nodes stack adds some of them and an exporter sees the evaluated
result.
"""

import json
import sys

import bpy


def describe(ob, dg):
    rec = {"name": ob.name, "type": ob.type}
    if ob.type != "CURVES":
        rec["skipped"] = "not a Curves object"
        return rec

    def attrs(data):
        out = []
        try:
            for a in data.attributes:
                out.append({"name": a.name,
                            "domain": a.domain,
                            "data_type": a.data_type,
                            "len": len(a.data)})
        except Exception as exc:
            out.append({"error": str(exc)})
        return out

    rec["authored"] = {
        "curves": len(ob.data.curves),
        "points": len(ob.data.points),
        "surface": ob.data.surface.name if ob.data.surface else None,
        "surface_uv_map": ob.data.surface_uv_map or None,
        "attributes": attrs(ob.data)}
    try:
        ev = ob.evaluated_get(dg)
        rec["evaluated"] = {
            "curves": len(ev.data.curves),
            "points": len(ev.data.points),
            "attributes": attrs(ev.data)}
    except Exception as exc:
        rec["evaluated"] = {"error": str(exc)}

    # The GroomExporter stamps its attribute NAMES onto the object, and those
    # names are what it looks for at export time. If they point at attributes
    # the curves do not have, the export is silently missing that channel.
    gp = getattr(ob, "GroomProperty", None)
    if gp is not None:
        props = {}
        try:
            for p in gp.bl_rna.properties:
                if p.identifier == "rna_type":
                    continue
                try:
                    props[p.identifier] = str(getattr(gp, p.identifier))
                except Exception:
                    pass
        except Exception as exc:
            props["__error__"] = str(exc)
        rec["GroomProperty"] = props
    else:
        rec["GroomProperty"] = None
    return rec


def main():
    argv = sys.argv
    names = argv[argv.index("--") + 1:] if "--" in argv else []
    dg = bpy.context.evaluated_depsgraph_get()
    out = {"blend": bpy.data.filepath, "objects": []}
    if not names:
        names = [o.name for o in bpy.data.objects if o.type == "CURVES"]
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is None:
            out["objects"].append({"name": n, "error": "not found"})
            continue
        out["objects"].append(describe(ob, dg))
    print("__ATTRS__" + json.dumps(out))


main()
