"""groom_pointer_audit.py -- the root-UV bug, generalized to every attribute.

    blender --background <blend> --python this.py --

The root-UV defect was not "a missing attribute". It was an EMPTY POINTER:
`obj.GroomProperty.att_groom_root_uv` was "", `getAttribute` short-circuited on
`if att_name != "":` (ExporterOperators.py:42), and the exporter skipped the
whole param in silence (AlembicGroomExporter.py:349). The clay object -- built
through the add-on's own operator, which sets the pointers (GroomOperators.py:45)
-- had it set. The DiffLocks objects, built by hand with
`bpy.data.hair_curves.new()`, had none of them set.

**THAT MECHANISM IS NOT SPECIFIC TO ROOT UVs.** Every one of the twelve
attributes the exporter writes is resolved through its own pointer, each with
the same silent skip. So this dumps ALL of them, on both objects, and
reproduces the exporter's decision for each: what it would resolve, what type,
and whether it would SKIP.

Reads the EVALUATED attributes, because that is what the exporter reads
(ExporterOperators.py:26-28) -- checking `ob.data.attributes` is how the second
version of this bug survived a fix to the first.
"""

import json

import bpy

# The twelve pointers, with the type list each is checked against. Taken from
# AlembicGroomExporter.py:279-291 verbatim rather than remembered.
POINTERS = [
    ("att_groom_width", ["FLOAT"]),
    ("att_groom_color", ["FLOAT_COLOR", "FLOAT_VECTOR"]),
    ("att_groom_roughness", ["FLOAT"]),
    ("att_groom_root_uv", ["FLOAT2", "FLOAT_VECTOR"]),
    ("att_groom_knots", ["FLOAT"]),
    ("att_groom_orders", ["INT8"]),
    ("att_groom_guide", ["INT", "INT8"]),
    ("att_groom_id", ["INT", "INT8"]),
    ("att_groom_closest_guides", ["BYTE_COLOR", "FLOAT_COLOR"]),
    ("att_groom_guide_weights", ["FLOAT_VECTOR"]),
    ("att_groom_ao", ["FLOAT"]),
    ("att_groom_cards_name", ["STRING"]),
]


def main():
    dg = bpy.context.evaluated_depsgraph_get()
    rep = {"blend": bpy.data.filepath, "objects": {}}

    for ob in bpy.data.objects:
        if ob.type != "CURVES" or len(ob.data.curves) == 0:
            continue
        gp = getattr(ob, "GroomProperty", None)
        ev = ob.evaluated_get(dg)
        attrs = {a.name: a for a in ev.data.attributes}
        row = {"evaluated_attributes":
               ["%s(%s,%s,len=%d)" % (a.name, a.domain, a.data_type,
                                      len(a.data)) for a in ev.data.attributes],
               "pointers": {}}
        for name, types in POINTERS:
            ptr = getattr(gp, name, "NO GroomProperty") if gp else "NO GroomProperty"
            a = attrs.get(ptr) if isinstance(ptr, str) and ptr else None
            # reproduce ExporterOperators.getAttribute exactly
            valid = bool(ptr) and ptr in attrs and \
                (a.data_type in types if a else False)
            row["pointers"][name] = {
                "pointer": ptr,
                "resolves": a is not None,
                "type": getattr(a, "data_type", None),
                "accepted_types": types,
                "EXPORTER_WOULD": "WRITE" if valid else "SKIP SILENTLY"}
        rep["objects"][ob.name] = row

    print("__PA__" + json.dumps(rep, default=str))


main()
