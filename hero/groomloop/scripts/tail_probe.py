"""tail_probe.py -- HOW MUCH of the source read is actually corrupt?

    blender --background --python tail_probe.py -- <abc> <out_json>

MORNING_REPORT section 6 says Blender mis-reads the source and that everything
downstream is "built on a corrupted read". That is a strong claim and it is
worth checking rather than repeating: UE reads the vendor file as a 26 cm
groom, and Blender's own p01-p99 tip band is ~21 cm, which AGREE. If only a
small tail is corrupt then the claim is overstated and the report needs
narrowing.

Counts curves by length band so the size of the bad tail is a number.
"""
import json
import sys

import bpy
import numpy as np


import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from pick_curves import pick_curves_object
a = sys.argv
tail = a[a.index("--") + 1:] if "--" in a else []
abc, out = tail[0], tail[1]

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.ops.wm.alembic_import(filepath=abc, as_background_job=False)
ob = pick_curves_object(bpy)
d = ob.data
n = len(d.points)
buf = np.zeros(n * 3, dtype=np.float32)
d.attributes["position"].data.foreach_get("vector", buf)
P = buf.reshape(n, 3).astype(np.float64)
sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
starts = np.array([c.first_point_index for c in d.curves], dtype=np.int64)

seg = np.zeros(n)
seg[1:] = np.linalg.norm(P[1:] - P[:-1], axis=1)
seg[starts] = 0.0
cum = np.concatenate([[0.0], np.cumsum(seg)])
L = cum[starts + sizes] - cum[starts]

total = len(L)
bands = [(0.0, 0.001), (0.001, 0.05), (0.05, 0.15), (0.15, 0.26),
         (0.26, 0.40), (0.40, 0.80), (0.80, 10.0)]
rep = {"curves": int(total), "degenerate_1pt": int((sizes < 2).sum()),
       "bands_m": []}
for lo, hi in bands:
    m = (L >= lo) & (L < hi)
    rep["bands_m"].append({"lo": lo, "hi": hi, "count": int(m.sum()),
                           "pct": round(100.0 * m.sum() / total, 3)})

# UE reads the VENDOR file as max_curve_length 26.10 cm. Anything longer than
# that in Blender's read cannot be a faithful strand of the same groom.
over = L > 0.261
rep["over_ue_max_0.261m"] = {"count": int(over.sum()),
                             "pct": round(100.0 * over.sum() / total, 3)}
rep["plausible_pct"] = round(100.0 * (~over & (sizes >= 2)).sum() / total, 3)
rep["len_p50_cm"] = round(float(np.median(L)) * 100, 3)
rep["len_p99_cm"] = round(float(np.percentile(L, 99)) * 100, 3)
rep["len_max_cm"] = round(float(L.max()) * 100, 3)

json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
print("__TAIL__" + json.dumps(rep))
