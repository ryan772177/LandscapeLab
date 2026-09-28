import sys, os, json
import bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object
ob = pick_curves_object(bpy)
d = ob.data
rep = {"blend": os.path.basename(bpy.data.filepath), "object": ob.name,
       "attributes": sorted([(a.name, a.domain, a.data_type) for a in d.attributes]),
       "object_custom_props": {k: str(ob[k])[:120] for k in ob.keys()},
       "data_custom_props": {k: str(d[k])[:120] for k in d.keys()},
       "modifiers": [(m.name, m.type) for m in ob.modifiers],
       "surface": getattr(d, "surface", None).name if getattr(d, "surface", None) else None,
       "surface_uv_map": getattr(d, "surface_uv_map", None)}
print("__ATTR__" + json.dumps(rep, default=str))
