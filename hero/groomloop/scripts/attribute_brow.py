"""attribute_brow.py -- WHICH strands put hair in the central brow band?

    blender --background <candidate.blend> --python attribute_brow.py -- <out.json>

WHY THIS AND NOT ANOTHER TUNING PASS. `fringe: brow` is the largest remaining
error on the rubric -- 0.0254 against the clay's 0.0007 -- and the round-2 fringe
agent already proved it is NOT reachable from fringe knobs: it gathered the
fringe almost entirely off the forehead (central forehead 0.0200) and brow barely
moved, 0.0204. So the hair in that band is rooted somewhere else, and tuning the
fringe harder is tuning the wrong region.

THIS IS THE MOVE THAT WORKED LAST TIME. On 2026-08-21 three separate fixes failed
to shift hair off this hero's face because nobody asked WHICH STRANDS were doing
it -- `front_sweep_gain` 1.2 -> 2.4 moved the number 17,463 -> 17,362 and
`len_side_cm` 6.5 -> 5.0 moved it 17,378 -> 17,378, identically. A root census
answered it in one run. Same question here.

THE BAND IS THE RUBRIC'S OWN, converted to centimetres rather than re-invented:
front_metrics scores rows u 0.29-0.35 with u = (chin_row - row) / shoulder_w, and
preview_hair.py's fixed rig is 18.195 rows/cm with row 0 at z 184.39 -- so the
band is z 166.14 to 168.40, which brackets the survey's measured brow ridge at
167.24. The central column is the same 0.5 * 0.219 * shoulder_w the rubric uses.

It reports the ROOT REGION of every offending strand, weighted, so the answer
names a region an agent can be given rather than a pixel count.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

UP = np.array([0.0, 0.0, 1.0])
FWD = np.array([0.0, -1.0, 0.0])
SIDE = np.cross(UP, FWD)

Z_LO, Z_HI = 166.14, 168.40          # the rubric's brow rows, in centimetres
HALF_X = 0.5 * 0.219 * 689 / 18.195  # the rubric's central column, in cm


def ss(lo, hi, x):
    t = np.clip((x - lo) / (hi - lo + 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def main():
    a = sys.argv
    out = (a[a.index("--") + 1:] or ["brow_attr.json"])[0]

    sv = json.load(open("hero/groomloop/survey/survey_head.json",
                        encoding="utf-8"))
    C = np.asarray(sv["frame"]["centre"], dtype=np.float64)
    R = float(sv["frame"]["radius"])

    ob = pick_curves_object(bpy)
    d = ob.data
    n_pts = len(d.points)
    pos = np.zeros(n_pts * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", pos)
    P = pos.reshape(n_pts, 3).astype(np.float64)
    starts = np.array([c.first_point_index for c in d.curves], dtype=np.int64)
    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    n_cur = len(starts)
    cid = np.zeros(n_pts, dtype=np.int64)
    for i in range(n_cur):
        cid[starts[i]:starts[i] + sizes[i]] = i
    roots = P[starts]

    z, x, y = P @ UP, P @ SIDE, P @ FWD
    face_y = float(np.percentile(roots @ FWD, 99))    # frontmost roots
    inside = (z >= Z_LO) & (z <= Z_HI) & (np.abs(x - C @ SIDE) <= HALF_X)
    # only hair IN FRONT of the face plane counts -- hair at the same height
    # behind the skull is not over his brow
    inside &= y > (face_y - 0.35 * R)

    hit_curves = np.unique(cid[inside])
    rep = {"blend": bpy.data.filepath, "curves": int(n_cur),
           "band_cm": [Z_LO, Z_HI], "half_x_cm": round(HALF_X, 3),
           "points_in_band": int(inside.sum()),
           "curves_in_band": int(hit_curves.size),
           "curves_in_band_pct": round(100.0 * hit_curves.size / n_cur, 3)}

    # --- attribute by ROOT REGION ----------------------------------------
    loc = (roots - C) / R
    up_, fwd_, side_ = loc @ UP, loc @ FWD, loc @ SIDE
    regions = {
        "crown":  ss(0.25, 0.85, up_),
        "fringe": ss(0.10, 0.65, fwd_) * ss(-0.30, 0.55, up_),
        "temple": ss(0.40, 0.85, np.abs(side_)) * ss(0.05, 0.55, fwd_),
        "side":   ss(0.35, 0.85, np.abs(side_)) * (1 - ss(0.55, 1.0, up_)),
        "nape":   ss(-0.20, -0.75, fwd_) * (1 - ss(-0.55, 0.15, up_)),
    }
    mask = np.zeros(n_cur, dtype=bool)
    mask[hit_curves] = True
    rep["attribution"] = {}
    for k, w in regions.items():
        tot = float(w.sum())
        rep["attribution"][k] = {
            "weight_of_offenders": round(float(w[mask].sum()), 1),
            "weight_of_region": round(tot, 1),
            "pct_of_region_offending": round(
                100.0 * float(w[mask].sum()) / max(tot, 1e-9), 2),
        }
    # share of the offending set each region accounts for
    tot_off = sum(v["weight_of_offenders"] for v in rep["attribution"].values())
    for k in rep["attribution"]:
        rep["attribution"][k]["share_of_offenders_pct"] = round(
            100.0 * rep["attribution"][k]["weight_of_offenders"]
            / max(tot_off, 1e-9), 1)

    # where the offenders are ROOTED, in plain centimetres
    if hit_curves.size:
        rr = roots[hit_curves]
        rep["offender_roots"] = {
            "up_cm": [round(float(np.percentile(rr @ UP, q)), 2)
                      for q in (5, 50, 95)],
            "abs_side_cm": [round(float(np.percentile(
                np.abs((rr @ SIDE) - C @ SIDE), q)), 2) for q in (5, 50, 95)],
            "fwd_cm": [round(float(np.percentile(rr @ FWD, q)), 2)
                       for q in (5, 50, 95)],
        }
    json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
    print("__BROW__" + json.dumps(rep))


if __name__ == "__main__":
    main()
