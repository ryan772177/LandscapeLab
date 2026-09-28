import sys, os, json
import bpy, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object
ob = pick_curves_object(bpy); d = ob.data
n = len(d.points)
pos = np.zeros(n*3, dtype=np.float32)
d.attributes["position"].data.foreach_get("vector", pos)
P = pos.reshape(n,3).astype(np.float64)
sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
starts = np.array([c.first_point_index for c in d.curves], dtype=np.int64)
k = int(sizes[0]); uniform = bool((sizes == k).all())
rep = {"blend": os.path.basename(bpy.data.filepath), "curves": len(d.curves),
       "points": n, "uniform_points_per_curve": uniform, "k": k}
if uniform:
    A = P.reshape(len(d.curves), k, 3)
    seg = np.linalg.norm(np.diff(A, axis=1), axis=2)
    L = seg.sum(1)
    rep["strand_len_cm"] = {"min": float(L.min()), "p1": float(np.percentile(L,1)),
                            "mean": float(L.mean()), "max": float(L.max())}
    rep["segment_cm"] = {"min": float(seg.min()), "p1": float(np.percentile(seg,1)),
                         "mean": float(seg.mean())}
    for t in (1e-6, 1e-4, 1e-3, 1e-2):
        rep["segments_under_%g" % t] = int((seg < t).sum())
    rep["curves_with_any_zero_segment"] = int((seg < 1e-6).any(axis=1).sum())
    rep["curves_under_0.9cm"] = int((L < 0.9).sum())
rep["nonfinite_points"] = int((~np.isfinite(P)).any(axis=1).sum())
# duplicate ROOTS -- the Groom Doctor dedupes these
roots = P[starts]
q = np.round(roots, 4)
_, cnt = np.unique(q, axis=0, return_counts=True)
rep["duplicate_root_positions"] = int((cnt > 1).sum())
rep["max_roots_sharing_one_spot"] = int(cnt.max())
print("__DEG__" + json.dumps(rep))
