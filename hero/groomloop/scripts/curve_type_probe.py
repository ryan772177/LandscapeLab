import sys, os, json
import bpy, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object
ob = pick_curves_object(bpy); d = ob.data
n = len(d.curves)
ct = np.zeros(n, dtype=np.int32)
a = d.attributes.get("curve_type")
if a is not None:
    a.data.foreach_get("value", ct)
else:
    ct[:] = -1
res = np.zeros(n, dtype=np.int32)
r = d.attributes.get("resolution")
if r is not None: r.data.foreach_get("value", res)
print("__CT__" + json.dumps({
    "blend": os.path.basename(bpy.data.filepath),
    "curve_type_attr_present": a is not None,
    "curve_type_values": sorted(set(int(x) for x in ct[:5000])),
    "resolution_present": r is not None,
    "curves_type_property": str(getattr(d.curves[0], "curve_type", "n/a")),
}))
