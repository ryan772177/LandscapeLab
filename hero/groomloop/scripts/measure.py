"""measure.py -- geometric scores for an iteration. No renders involved.

    blender --background --python measure.py -- <blend_or_abc> <out_json>

MEASURED IN GEOMETRY, NOT IN THE RENDER. This project has already established
that render-side edge statistics do not move when mechanisms that demonstrably
work are applied -- three of them moved a rendered hairline statistic by
nothing. Tip positions are the thing the spec is actually about, so they are
read directly.

Frame (measured, recon/geometry.json): up = -Y, front = +Z, head centre
(0, -1.52098, 0). Landmarks come from proxy_head.fit_from_roots so the metric
and the render's rulers agree by construction -- one declaration, two
consumers.

WHAT EACH NUMBER IS FOR, and every one is signed so its direction is unarguable:
  fringe_reach_cm    +ve = fringe tips hang BELOW the brow line. The spec's
                     headline: "longest pieces reach eyebrow-to-upper-eyelid".
  forehead_cover_pct % of fringe strands whose tip clears the brow.
  crown_rise_cm      how far the highest hair sits above the skull top.
  silhouette_w_cm    p99 tip width, the shag's outline.
  ear_cover_pct      % of lateral strands whose tips fall past the ear marker.
  grade_ratio        nape strand length / crown strand length. The spec wants
                     "shortest at crown, grading to collar/jaw at nape", so
                     this should be > 1.
  tip_scatter_cm     mean distance from a tip to the mean of its 12 nearest
                     neighbours' tips. Texture breakup: a smooth curtain
                     scores low, separated piecey clumps score high, and
                     uniform frizz ALSO scores high -- so it is read together
                     with the render, never alone.
"""

import json
import os
import sys

import bpy
import numpy as np


import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from pick_curves import pick_curves_object
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proxy_head                                       # noqa: E402


def argv_tail():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def main():
    tail = argv_tail()
    src, out = tail[0], tail[1]
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    if src.lower().endswith(".abc"):
        bpy.ops.wm.alembic_import(filepath=src, as_background_job=False)
    else:
        bpy.ops.wm.open_mainfile(filepath=src)

    ob = pick_curves_object(bpy)
    d = ob.data
    n_pts = len(d.points)
    buf = np.zeros(n_pts * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    P = buf.reshape(n_pts, 3).astype(np.float64)

    sizes = np.array([c.points_length for c in d.curves], dtype=np.int64)
    starts = np.array([c.first_point_index for c in d.curves], dtype=np.int64)
    roots = P[starts]
    tips = P[starts + sizes - 1]

    fit = proxy_head.fit_from_roots(roots)
    c, r = fit["centre"], fit["radius"]
    brow_y = fit["brow_y"]
    ear_x, ear_y = fit["ear_x"], fit["ear_y"]

    loc = (roots - c) / r          # normalised per-axis
    up = -loc[:, 1]
    fwd = loc[:, 2]
    side = loc[:, 0]

    # strand lengths, vectorised
    seg = np.zeros(n_pts)
    seg[1:] = np.linalg.norm(P[1:] - P[:-1], axis=1)
    seg[starts] = 0.0
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    L = cum[starts + sizes] - cum[starts]

    rep = {"src": src, "curves": int(len(sizes)),
           "landmarks": {k: (list(np.round(v, 5)) if hasattr(v, "__len__")
                             else round(float(v), 5)) for k, v in fit.items()}}

    fringe = (fwd > 0.35) & (up > -0.05)
    rep["fringe_curves"] = int(fringe.sum())
    if fringe.any():
        ft = tips[fringe, 1]
        # +Y is DOWN, so a tip BELOW the brow has a LARGER y than brow_y.
        rep["fringe_reach_cm"] = round(float(np.median(ft) - brow_y) * 100, 3)
        rep["fringe_reach_p90_cm"] = round(
            float(np.percentile(ft, 90) - brow_y) * 100, 3)
        rep["forehead_cover_pct"] = round(float((ft > brow_y).mean()) * 100, 2)

    # SKULL TOP = THE TOPMOST ROOT, not centre - fitted radius. The fitted
    # ellipsoid overestimates skull height because the root cloud is a scalp
    # cap PLUS a nape that runs 13.8 cm below centre, so a symmetric fit puts
    # the "top" above any hair and crown_rise read -3.79 cm on the untouched
    # source. The highest root is by definition on the crown.
    top_y = float(roots[:, 1].min())       # up = -Y, so min y is highest
    rep["crown_rise_cm"] = round(float(top_y - np.percentile(tips[:, 1], 1))
                                 * 100, 3)
    rep["silhouette_w_cm"] = round(
        float(np.percentile(np.abs(tips[:, 0]), 99) * 2) * 100, 3)
    rep["silhouette_d_cm"] = round(
        float(np.percentile(np.abs(tips[:, 2]), 99) * 2) * 100, 3)

    lateral = np.abs(side) > 0.60
    rep["lateral_curves"] = int(lateral.sum())
    if lateral.any():
        rep["ear_cover_pct"] = round(
            float((tips[lateral, 1] > ear_y).mean()) * 100, 2)

    crown_m = up > 0.55
    nape_m = (fwd < -0.25) & (up < 0.0)
    if crown_m.any() and nape_m.any():
        cl = float(np.median(L[crown_m]))
        nl = float(np.median(L[nape_m]))
        rep["crown_len_cm"] = round(cl * 100, 3)
        rep["nape_len_cm"] = round(nl * 100, 3)
        rep["grade_ratio"] = round(nl / max(cl, 1e-6), 3)

    # tip scatter: sampled, because a full 94k x 94k neighbour search is not
    # worth minutes per iteration. Seeded so the number is reproducible.
    rg = np.random.default_rng(4242)
    idx = rg.choice(len(tips), size=min(3000, len(tips)), replace=False)
    S = tips[idx]
    dists = np.linalg.norm(S[:, None, :] - S[None, :, :], axis=2)
    np.fill_diagonal(dists, np.inf)
    k = 12
    nn = np.argsort(dists, axis=1)[:, :k]
    local_mean = S[nn].mean(axis=1)
    rep["tip_scatter_cm"] = round(
        float(np.linalg.norm(S - local_mean, axis=1).mean()) * 100, 4)

    # SCALP EXPOSURE. Became the limiting failure at iteration 003: sweeping
    # strands forward uncovers the scalp behind their own roots, and no fringe
    # metric can see that. Scalp is defined BY THE ROOTS -- a cell only counts
    # as scalp if hair grows there -- so this cannot be gamed by moving the
    # region definition around.
    dirs = roots - c
    u = dirs / np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-9)
    NLON, NLAT = 28, 18

    def cell_of(vecs):
        uu = vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)
        th = np.arctan2(uu[:, 0], uu[:, 2])
        ph = np.arcsin(np.clip(-uu[:, 1], -1.0, 1.0))
        li = np.clip(((th + np.pi) / (2 * np.pi) * NLON).astype(int), 0, NLON - 1)
        pj = np.clip(((ph + np.pi / 2) / np.pi * NLAT).astype(int), 0, NLAT - 1)
        return li * NLAT + pj

    root_cells = cell_of(dirs)
    occupied = np.zeros(NLON * NLAT, dtype=bool)
    occupied[np.unique(root_cells)] = True

    # Only points that lie NEAR the scalp shell count as covering it; a tip
    # hanging 10 cm off the head does not hide the skin under its own root.
    tvec = np.zeros(n_pts)
    for i in range(len(sizes)):
        s, sz = starts[i], sizes[i]
        if sz > 1:
            tvec[s:s + sz] = np.linspace(0.0, 1.0, sz)
    pd = P - c
    prad = np.linalg.norm(pd, axis=1)
    rroot = np.linalg.norm(dirs, axis=1)
    shell = float(np.median(rroot))
    near = (tvec > 0.12) & (prad < shell * 1.45)
    cov_cells = cell_of(pd[near]) if near.any() else np.array([], dtype=int)
    covered = np.zeros(NLON * NLAT, dtype=np.int64)
    if cov_cells.size:
        covered = np.bincount(cov_cells, minlength=NLON * NLAT)
    scalp_cells = int(occupied.sum())
    exposed = int(((covered < 3) & occupied).sum())
    rep["scalp_cells"] = scalp_cells
    rep["scalp_exposed_pct"] = round(100.0 * exposed / max(scalp_cells, 1), 2)

    rep["strand_len_cm"] = {
        "p50": round(float(np.median(L)) * 100, 3),
        "p95": round(float(np.percentile(L, 95)) * 100, 3),
        "max": round(float(L.max()) * 100, 3)}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    keys = ("fringe_reach_cm", "fringe_reach_p90_cm", "forehead_cover_pct",
            "crown_rise_cm", "silhouette_w_cm", "ear_cover_pct",
            "grade_ratio", "tip_scatter_cm", "scalp_exposed_pct")
    payload = {k: rep.get(k) for k in keys}
    payload["ok"] = True
    print("__MEASURE__" + json.dumps(payload))


if __name__ == "__main__":
    main()
