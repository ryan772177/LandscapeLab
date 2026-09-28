"""stub_probe.py -- are the 8,678 sub-millimetre curves a vellus layer or damage?

    blender --background --python stub_probe.py -- <abc> <out_json>

tail_probe found 9.19% of curves shorter than 1 mm and left the question open.
It matters: if they are parse damage they can be culled, taking 9% of the
groom's cost for no pixels; if they are an authored vellus underlayer they are
doing a job and removing them would thin the look.

THE DISCRIMINATOR IS DISTRIBUTION, NOT LENGTH. An authored vellus layer is
scattered THROUGH the normal strands, shares their root region, and carries the
same radius. Parse damage clusters -- by curve INDEX if the reader mis-walked a
block, or by point count if it lost knots.

So this asks three questions the length alone cannot answer:
  1. are the stubs adjacent in curve INDEX, or interleaved with normal strands?
  2. do their roots occupy the same scalp region as normal strands?
  3. do they share the normal strands' point-count distribution?
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
roots = P[starts]

stub = L < 0.001
norm = (L >= 0.001) & (sizes >= 2)
rep = {"curves": int(len(L)), "stubs": int(stub.sum()),
       "normal": int(norm.sum())}

# 1. INDEX CLUSTERING. If a reader mis-walked a block the stubs are contiguous.
#    Runs are counted: scattered stubs give runs of ~1, a damaged block gives
#    few very long runs.
idx = np.nonzero(stub)[0]
if idx.size:
    breaks = np.nonzero(np.diff(idx) > 1)[0]
    runs = np.diff(np.concatenate([[-1], breaks, [idx.size - 1]]))
    rep["index_runs"] = {"count": int(len(runs)),
                         "mean_len": round(float(runs.mean()), 3),
                         "max_len": int(runs.max())}
    rep["index_span"] = [int(idx.min()), int(idx.max())]
    # expected mean run length if stubs were placed at random
    p = float(stub.mean())
    rep["index_runs"]["mean_len_if_random"] = round(1.0 / (1.0 - p), 3)

# 2. ROOT REGION. Same scalp, or somewhere else?
c = roots[norm].mean(axis=0)
for lbl, m in (("stub", stub), ("normal", norm)):
    if not m.any():
        continue
    r = roots[m]
    rep["%s_root" % lbl] = {
        "centroid": [round(float(v), 4) for v in r.mean(axis=0)],
        "spread": [round(float(r[:, i].max() - r[:, i].min()), 4)
                   for i in range(3)],
        "mean_dist_from_normal_centroid": round(
            float(np.linalg.norm(r - c, axis=1).mean()), 4)}

# 3. POINT COUNTS.
for lbl, m in (("stub", stub), ("normal", norm)):
    if not m.any():
        continue
    s = sizes[m]
    h = {}
    for v in np.unique(s):
        h[int(v)] = int((s == v).sum())
    rep["%s_point_counts" % lbl] = h

json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
print("__STUB__" + json.dumps(rep))
