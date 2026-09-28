"""resolve_frame.py -- settle up/forward/side by ANATOMY, not by extent.

    blender --background <blend> --python this.py --

The extent heuristic in frame_probe.py chose X as up because the head's X extent
(38.067) beats its Z extent (37.559) by 1.4%. A near-tie decided a directional
frame, and every op in the restyle spec is directional -- whorl offset to his
LEFT, sweep to his RIGHT, flow DOWN the back. Getting it wrong does not error;
it produces a confident groom pointing the wrong way.

So the frame is resolved by ANATOMY, using `scripts/blender/head_frame.py` --
the project's single declaration of head measurement -- rather than a second
implementation of it. UP is the axis the head is tallest on once the near-tie is
broken by where the ROOTS sit (a scalp is at the top); FORWARD is the axis the
NOSE points along, and its sign is the nose's sign.
"""

import json
import os
import sys

import bpy
import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "scripts", "blender"))
from head_frame import measure_head


def main():
    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    V = np.empty(len(head.data.vertices) * 3, dtype=np.float32)
    head.data.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3).astype(np.float64)

    cu = max([o for o in bpy.data.objects
              if o.type == "CURVES" and len(o.data.curves) > 0],
             key=lambda o: len(o.data.curves))
    d = cu.data
    P = np.zeros(len(d.points) * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", P)
    A = P.reshape(-1, 3).astype(np.float64).reshape(
        -1, d.curves[0].points_length, 3)
    roots = A[:, 0, :]

    rep = {}
    # UP: the roots are the scalp. The axis on which roots sit HIGH inside the
    # head's own range is up, and its sign is the sign that puts them high.
    best = None
    for ax in range(3):
        lo, hi = V[:, ax].min(), V[:, ax].max()
        frac = (np.median(roots[:, ax]) - lo) / max(1e-9, hi - lo)
        for sgn in (1, -1):
            f = frac if sgn > 0 else 1.0 - frac
            if best is None or f > best[0]:
                best = (f, ax, sgn)
    rep["root_height_fraction"] = round(best[0], 4)
    up_ax, up_sgn = best[1], best[2]
    up = np.zeros(3)
    up[up_ax] = up_sgn

    # FORWARD: of the two remaining axes, the nose is the one with a strong
    # one-sided protrusion in the upper head. Test both, take the stronger.
    cand = [a for a in range(3) if a != up_ax]
    z = V @ up
    band = V[(z > np.percentile(z, 45)) & (z < np.percentile(z, 85))]
    scores = {}
    for ax in cand:
        c = np.median(band[:, ax])
        scores[ax] = (float(band[:, ax].max() - c), float(c - band[:, ax].min()))
    fwd_ax = max(cand, key=lambda a: max(scores[a]) / max(1e-9, min(scores[a])))
    fwd_sgn = 1 if scores[fwd_ax][0] > scores[fwd_ax][1] else -1
    fwd = np.zeros(3)
    fwd[fwd_ax] = fwd_sgn
    rep["protrusion_scores"] = {str(k): [round(v[0], 2), round(v[1], 2)]
                                for k, v in scores.items()}

    side = np.cross(up, fwd)
    rep["up"] = up.tolist()
    rep["fwd"] = fwd.tolist()
    rep["side"] = side.tolist()

    m = measure_head(V, up, fwd, side)
    rep["anatomy"] = m

    # CORROBORATION from a source the frame did not come from: hair tips must
    # hang BELOW their roots along up, and the fringe must reach FORWARD.
    tips = A[:, -1, :]
    rep["tip_below_root_cm"] = round(
        float((roots @ up).mean() - (tips @ up).mean()), 3)
    rep["tip_forward_reach_cm"] = round(
        float((tips @ fwd).max() - (V @ fwd).max()), 3)
    rep["frame_corroborated"] = bool(rep["tip_below_root_cm"] > 0)
    print("__RF__" + json.dumps(rep, default=str))


main()
