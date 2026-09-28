"""scale_strand_length.py -- lengthen the cut without restyling it.

    blender --background <in.blend> --python this.py -- <out.blend> <target_mean_cm>

MECHANISM: each strand is scaled UNIFORMLY ABOUT ITS OWN ROOT. p' = root + k*(p - root).

That choice is deliberate and it has a cost the operator named in advance. It
preserves every strand's DIRECTION and the SHAPE of its curl exactly -- the
curve is similar to itself -- so the cut's character survives. What it does not
preserve is curl SCALE: a 1.5x strand has 1.5x curl radius. The reconstruction's
authored curl is real data, so this stretches it.

The alternative -- extrapolating the tip along its final tangent -- keeps curl
size and welds a straight segment onto every strand, which reads as a wig. Of
the two ways to be wrong, similarity is the one that stays recognisable.

So: MODEST k, and judge the frame. A per-strand k is used, not a global one,
because a single multiplier applied to a distribution with min 2.68 and max
15.05 stretches the longest strands furthest -- and those are the ones already
defining the silhouette.

Roots do not move, and that is asserted rather than assumed: the whole seating
proof rests on root positions and a length op that shifts them silently would
void it.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object


def lengths(A):
    return np.linalg.norm(np.diff(A, axis=1), axis=2).sum(1)


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend, target_mean = tail[0], float(tail[1])
    mode = tail[2] if len(tail) > 2 else "uniform"

    ob = pick_curves_object(bpy)
    d = ob.data
    n = len(d.points)
    pos = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", pos)
    P = pos.reshape(n, 3).astype(np.float64)
    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    k_pts = int(sizes[0])
    assert (sizes == k_pts).all(), "source is not uniform in points-per-curve"
    n_cur = len(d.curves)
    A = P.reshape(n_cur, k_pts, 3)

    L0 = lengths(A)
    rep = {"in": {"n": int(n_cur), "mean": round(float(L0.mean()), 4),
                  "min": round(float(L0.min()), 4),
                  "max": round(float(L0.max()), 4),
                  "p50": round(float(np.percentile(L0, 50)), 4),
                  "p90": round(float(np.percentile(L0, 90)), 4)},
           "target_mean_cm": target_mean, "mode": mode}

    if mode == "uniform":
        k = np.full(n_cur, target_mean / float(L0.mean()))
    else:
        # COMPRESSIVE: shorter strands gain proportionally more than long ones,
        # so the mean rises without the existing longest strands running away.
        # k_i = (target/mean) ** (1 - w_i), w_i = rank of L_i in [0,1].
        w = (np.argsort(np.argsort(L0)) / max(1, n_cur - 1)) * 0.6
        base = target_mean / float(L0.mean())
        k = base ** (1.0 - w)
        k *= target_mean / float((L0 * k).mean())   # renormalise to hit target

    roots = A[:, 0:1, :]
    B = roots + (A - roots) * k[:, None, None]

    L1 = lengths(B)
    root_shift = np.linalg.norm(B[:, 0, :] - A[:, 0, :], axis=1)
    rep["out"] = {"mean": round(float(L1.mean()), 4),
                  "min": round(float(L1.min()), 4),
                  "max": round(float(L1.max()), 4),
                  "p50": round(float(np.percentile(L1, 50)), 4),
                  "p90": round(float(np.percentile(L1, 90)), 4)}
    rep["k"] = {"min": round(float(k.min()), 4),
                "mean": round(float(k.mean()), 4),
                "max": round(float(k.max()), 4)}
    rep["root_shift_max_cm"] = float(root_shift.max())
    if rep["root_shift_max_cm"] > 1e-6:
        rep["error"] = ("REFUSE: roots moved by up to %g cm. The seating proof "
                        "rests on root positions." % rep["root_shift_max_cm"])
        print("__LEN__" + json.dumps(rep))
        raise SystemExit(3)

    d.attributes["position"].data.foreach_set(
        "vector", B.reshape(-1, 3).astype(np.float32).ravel())

    # read back through a different array than the one written
    chk = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", chk)
    C = chk.reshape(n_cur, k_pts, 3)
    rep["readback_mean_cm"] = round(float(lengths(C).mean()), 4)
    rep["readback_matches"] = bool(
        abs(rep["readback_mean_cm"] - rep["out"]["mean"]) < 1e-3)

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    rep["saved"] = out_blend
    print("__LEN__" + json.dumps(rep))


if __name__ == "__main__":
    main()
