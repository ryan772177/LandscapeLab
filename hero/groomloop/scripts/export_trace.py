"""export_trace.py -- watch the exporter resolve the root-UV attribute, live.

    blender --background <blend> --python this.py -- <out.abc>

Setting `obj.GroomProperty.att_groom_root_uv` made the pointer resolve, and
calling the add-on's OWN `getAttribute` with the add-on's OWN evaluated
attribute dict returned valid=True -- and the export still wrote no
`groom_root_uv`, with no `[Att] uv setted` in its log.

So the paraphrase and the operator disagree, and every further theory is a guess
until the operator is watched doing it. This wraps `ExporterOperators.getAttribute`
so the ACTUAL call the ACTUAL export makes is printed with its arguments and its
answer. No inference: the instrument is inside the code under test.
"""

import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

from GroomExporter import ExporterOperators as EO

_orig = EO.getAttribute
_log = []


def traced(attributes_dict, att_name, default_att, att_types):
    prop, valid = _orig(attributes_dict, att_name, default_att, att_types)
    _log.append({"att_name": att_name, "types": list(att_types),
                 "dict_keys": sorted(attributes_dict.keys()),
                 "name_in_dict": att_name in attributes_dict,
                 "resolved": getattr(prop, "name", None),
                 "resolved_type": getattr(prop, "data_type", None),
                 "valid": bool(valid)})
    return prop, valid


EO.getAttribute = traced

out_abc = sys.argv[sys.argv.index("--") + 1]
ob = pick_curves_object(bpy)
gp = ob.GroomProperty
before = gp.att_groom_root_uv
gp.att_groom_root_uv = "groom_root_uv"

for o in bpy.context.selected_objects:
    o.select_set(False)
ob.select_set(True)
bpy.context.view_layer.objects.active = ob

# read the pointer back through the SAME expression the exporter uses, from the
# object the exporter will pick, immediately before handing over control
picked = EO.GetCurvesObjects(bpy.context)
rep = {"object": ob.name, "pointer_before": before,
       "pointer_after": gp.att_groom_root_uv,
       "GetCurvesObjects": [o.name for o in picked],
       "pointer_on_picked": [o.GroomProperty.att_groom_root_uv
                             for o in picked]}

res = bpy.ops.groom.buttonexport(
    filepath=out_abc, check_existing=False, groom_scale=1.0,
    groom_width_scale=True, groom_radius_to_diameter=True,
    groom_animation=False, node_execution=False)
rep["operator_result"] = list(res)
rep["getAttribute_calls"] = [c for c in _log
                             if c["att_name"] or c["types"] == ["FLOAT2",
                                                                "FLOAT_VECTOR"]]
rep["all_call_names"] = [c["att_name"] for c in _log]
print("__TRACE__" + json.dumps(rep, default=str))
