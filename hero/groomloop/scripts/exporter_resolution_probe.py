"""exporter_resolution_probe.py -- run the EXPORTER'S OWN resolution, not a copy of it.

    blender --background <blend> --python this.py --

Setting `att_groom_root_uv` made the pointer resolve against `ob.data.attributes`
and the written ABC STILL carried no `groom_root_uv`. So the pointer was
necessary and is not sufficient, and my corrected gate is STILL reading a
different representation than the consumer:

    AlembicGroomExporter.py:270
        data_curves_attributes = obj.evaluated_get(
            context.evaluated_depsgraph_get()).data.attributes

The exporter builds its dict from the EVALUATED object. My gate reads the raw
`ob.data.attributes`. Two different objects, and I have now made the same class
of mistake twice in one hour -- checking a name I chose, then checking the right
name on the wrong copy.

So this probe stops paraphrasing the exporter and CALLS IT: same depsgraph, same
dict construction, same `op.getAttribute`, same type list. Whatever it returns is
what the export will do, because it is literally the same code.
"""

import json

import bpy

# Import the add-on's own module rather than a copy of its logic. Reached as a
# package member because the add-on directory itself is not on sys.path -- and
# an MSYS-style path handed to Blender's Python is not a path at all, which is
# how the first attempt died.
try:
    from GroomExporter import ExporterOperators as op
except ImportError:
    import addon_utils  # noqa: F401
    import importlib
    op = importlib.import_module("GroomExporter.ExporterOperators")

rep = {}
dg = bpy.context.evaluated_depsgraph_get()

for ob in bpy.data.objects:
    if ob.type != "CURVES" or len(ob.data.curves) == 0:
        continue
    gp = getattr(ob, "GroomProperty", None)
    row = {"raw_attributes": [a.name for a in ob.data.attributes],
           "att_groom_root_uv": getattr(gp, "att_groom_root_uv", "NO GroomProperty")}

    ev = ob.evaluated_get(dg)
    ev_attrs = ev.data.attributes
    row["evaluated_attributes"] = [
        "%s(%s,%s,len=%d)" % (a.name, a.domain, a.data_type, len(a.data))
        for a in ev_attrs]
    row["evaluated_curves"] = len(ev.data.curves)

    d = {}
    for a in ev_attrs:
        d[a.name] = a

    # set the pointer the way export_hero_groom.py now does, then ask the
    # exporter's own function what it makes of it
    if gp is not None:
        gp.att_groom_root_uv = "groom_root_uv"
        prop, valid = op.getAttribute(d, gp.att_groom_root_uv, ev_attrs[0],
                                      ["FLOAT2", "FLOAT_VECTOR"])
        row["getAttribute_valid"] = valid
        row["getAttribute_returned"] = getattr(prop, "name", str(prop))
        row["getAttribute_returned_type"] = getattr(prop, "data_type", None)
    rep[ob.name] = row

print("__ER__" + json.dumps(rep, default=str))
