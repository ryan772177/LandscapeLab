"""depsgraph_pointer_test.py -- does a property write reach the EVALUATED copy?

    blender --background <blend> --python this.py --

ExporterOperators.py:26-28 returns `obj.evaluated_get(depsgraph)`, and
AlembicGroomExporter.py:231 reads `obj.GroomProperty` off THAT. So a pointer set
on the original is only seen by the exporter if the depsgraph re-copies it.

Four candidate refreshes, each measured on the evaluated copy rather than
assumed. Ordered cheapest first; the first that works is the one that ships.
"""

import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

ob = pick_curves_object(bpy)
name = ob.name


def ev_pointer():
    dg = bpy.context.evaluated_depsgraph_get()
    return bpy.data.objects[name].evaluated_get(dg).GroomProperty \
        .att_groom_root_uv


rep = {"object": name}
rep["orig_before"] = ob.GroomProperty.att_groom_root_uv
rep["evaluated_before"] = ev_pointer()

ob.GroomProperty.att_groom_root_uv = "groom_root_uv"
rep["orig_after_write"] = ob.GroomProperty.att_groom_root_uv
rep["evaluated_after_write"] = ev_pointer()

ob.update_tag()
rep["evaluated_after_update_tag"] = ev_pointer()

bpy.context.view_layer.update()
rep["evaluated_after_view_layer_update"] = ev_pointer()

dg = bpy.context.evaluated_depsgraph_get()
dg.update()
rep["evaluated_after_depsgraph_update"] = ev_pointer()

print("__DP__" + json.dumps(rep, default=str))
