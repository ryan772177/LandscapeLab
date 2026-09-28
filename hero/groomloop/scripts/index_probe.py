"""index_probe.py -- does CURVE INDEX carry authored structure?

    blender --background --python index_probe.py -- <abc> <out_json>

Proposed by the escalation consult. Groom exporters commonly emit curves
grouped by guide or by patch. If consecutive indices are spatially clustered
then the index blocks ARE the artist's own guide grouping -- a free,
authored-quality lock partition, strictly better than the lat/long
quantisation `spatial_clumps` uses now.

THE TEST IS A RATIO, so it cannot be fooled by the groom's overall size:
mean distance between CONSECUTIVE-index roots, against mean distance between
RANDOM pairs of roots. Near 1.0 means index is random. Well below 1.0 means
index carries spatial structure.

It also reports the ratio at several strides, because a guide grouping shows up
as structure that decays with stride, whereas a mere sort by position would
stay clustered at every stride.
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
starts = np.array([c.first_point_index for c in d.curves], dtype=np.int64)
roots = P[starts]
N = len(roots)

rg = np.random.default_rng(99)
i1 = rg.integers(0, N, 40000)
i2 = rg.integers(0, N, 40000)
rand_d = float(np.linalg.norm(roots[i1] - roots[i2], axis=1).mean())

rep = {"curves": int(N), "random_pair_mean_m": round(rand_d, 5), "strides": {}}
for stride in (1, 2, 5, 10, 50, 200, 1000):
    a_idx = np.arange(0, N - stride)
    dd = float(np.linalg.norm(roots[a_idx] - roots[a_idx + stride],
                              axis=1).mean())
    rep["strides"][str(stride)] = {
        "mean_m": round(dd, 5),
        "ratio_vs_random": round(dd / max(rand_d, 1e-9), 4)}

json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
print("__INDEX__" + json.dumps(rep))
