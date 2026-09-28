"""benchmarks.py -- checkable statements about the reference, measured on the groom.

    blender --background <blend> --python this.py --

OPERATOR'S INSTRUMENT, adopted 2026-08-23: instead of one composite score,
carry a short list of HIGH-LEVEL BENCHMARKS -- things a person can state by
looking at the reference and a person can verify by looking at the render --
and drive the groom toward them incrementally.

That is a better instrument than the composite rubric for two measured reasons.
The clay-calibrated `front_metrics.py` does not transfer to this reference at
all: `chin_row`, `shoulder_w_px` and `face_w_px` all return None on both the
reference and our renders, so every `anat_*` axis under them is meaningless --
the reference itself scores 0.9161 on an eye veto whose limit is 0.0040. And
the project's own standing lesson is that "a metric with no target in the loop
can tell you that you moved, never that you moved toward the target". These
benchmarks each name a visible feature of the reference.

WHERE EACH IS MEASURED, AND WHY GEOMETRY RATHER THAN PIXELS: a render mixes the
groom with lighting, exposure and a forest, and this project has twice read a
lighting difference as a hair difference. Everything checkable in the strand
data is checked there; only what genuinely needs a camera goes to a frame.

    B1  bangs do not extend past the eyebrow          geometry
    B2  sides thin enough that part of the ear shows  geometry
    B3  no hard part at the crown                     geometry
    B4  scalp not visible through the top             geometry
    B5  hair lifts off the neck, layered not draped   geometry
    B6  fringe reads as separated clusters            geometry
    B7  nothing touches the eyes                      geometry

Each prints PASS/FAIL, its measured value and its bar. The bars are stated in
the file so a later session can argue with them; none is derived from the thing
it is judging.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "scripts", "blender"))
from head_frame import measure_head

BARS = {
    "B1_bang_lowest_above_brow_cm": (">=", 0.0),
    "B2_ear_covered_frac": ("<=", 0.70),
    "B3_part_density_ratio": (">=", 1.00),
    "B4_scalp_visible_top": ("<=", 0.015),
    "B5_nape_standoff_cm": (">=", 0.8),
    # CALIBRATED ON A SINGLE-VARIABLE PAIR: dl_B3 -> dl_B4, identical
    # curve count (39,869), only the clumping pass between them, reads
    # CV 0.885 -> 1.194. The bar sits between them with margin.
    "B6_cluster_separation": (">=", 1.10),
    "B7_points_in_eye_box": ("<=", 0),
}
EYE_LO, EYE_HI, EYE_HALF = 165.6, 168.5, 6.0


def unit(v, eps=1e-12):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), eps)


def fit_sphere(pts):
    A = np.hstack([2 * pts, np.ones((pts.shape[0], 1))])
    sol, *_ = np.linalg.lstsq(A, (pts ** 2).sum(1), rcond=None)
    c = sol[:3]
    return c, float(np.sqrt(max(1e-9, sol[3] + (c ** 2).sum())))


def main():
    ob = pick_curves_object(bpy)
    d = ob.data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    k = d.curves[0].points_length
    A = buf.reshape(n, 3).astype(np.float64).reshape(-1, k, 3)
    roots, tips = A[:, 0, :], A[:, -1, :]
    pts = A.reshape(-1, 3)

    head = max([o for o in bpy.data.objects if o.type == "MESH"],
               key=lambda o: len(o.data.vertices))
    V = np.empty(len(head.data.vertices) * 3, dtype=np.float32)
    head.data.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3).astype(np.float64)

    up = np.array([0.0, 0.0, 1.0])
    fwd = np.array([0.0, 1.0, 0.0])
    side = np.cross(up, fwd)
    anat = measure_head(V, up, fwd, side)
    centre, R = fit_sphere(roots)
    u = unit(roots - centre)
    r = {"curves": int(A.shape[0]), "points": int(n), "anatomy": anat,
         "scalp_R_cm": round(R, 3)}

    # ---- B1 bangs above the brow
    # BANGS ARE NEAR THE MIDLINE. The first version selected on "frontal" alone
    # and read -8.148 cm on a groom whose fringe had just been trimmed to the
    # brow -- because it was measuring TEMPLE strands hanging to the jaw, which
    # are side hair and are supposed to be long. The benchmark says "bangs do
    # not extend past the eyebrow"; side hair reaching the jaw is the reference,
    # not a failure. Narrowed to the frontal strands within a half-face width of
    # the midline.
    front = ((roots @ fwd) > np.percentile(roots @ fwd, 72)) \
        & (u @ up < 0.80) & (roots[:, 2] > anat["brow_up"] + 1.5) \
        & (np.abs(roots @ side) < 6.5)
    r["_front_strands"] = int(front.sum())
    r["B1_bang_lowest_above_brow_cm"] = round(
        float(A[front][:, :, 2].min() - anat["brow_up"]), 3) \
        if front.any() else None

    # ---- B2 the ear. Located on the HEAD, not guessed: the lateral extreme
    # in the band around the eye height. Coverage is measured from a LATERAL
    # view -- hair further out than the ear, over the ear's own footprint.
    lat = V @ side
    band = (V[:, 2] > EYE_LO - 3.0) & (V[:, 2] < EYE_HI + 3.0)
    ear_out = np.percentile(np.abs(lat[band]), 97)
    for sgn, nm in ((1.0, "left"), (-1.0, "right")):
        m = band & (lat * sgn > ear_out * 0.88)
        if m.sum() < 20:
            r["B2_ear_covered_frac"] = None
            break
        ez, ey = V[m][:, 2], V[m] @ fwd
        z0, z1, y0, y1 = ez.min(), ez.max(), ey.min(), ey.max()
        hp = pts[(pts @ side) * sgn > ear_out * 0.88]
        nb = 24
        grid = np.zeros((nb, nb), dtype=bool)
        if hp.size:
            iz = ((hp[:, 2] - z0) / max(1e-6, z1 - z0) * nb).astype(int)
            iy = (((hp @ fwd) - y0) / max(1e-6, y1 - y0) * nb).astype(int)
            ok = (iz >= 0) & (iz < nb) & (iy >= 0) & (iy < nb)
            grid[iz[ok], iy[ok]] = True
        r["B2_ear_covered_%s" % nm] = round(float(grid.mean()), 4)
    if "B2_ear_covered_left" in r:
        r["B2_ear_covered_frac"] = round(
            0.5 * (r["B2_ear_covered_left"] + r["B2_ear_covered_right"]), 4)

    # ---- B3 part density ratio (midline band vs bands 5 cm either side)
    rel = pts - centre
    rr = np.linalg.norm(rel, axis=1)
    dirs = rel / np.maximum(rr, 1e-9)[:, None]
    cap = (dirs @ up > 0.30) & (rr > R * 1.03)
    lp = rel @ side
    mid = cap & (np.abs(lp) < 1.6)
    off = cap & (np.abs(np.abs(lp) - 5.0) < 1.6)
    r["B3_part_density_ratio"] = round(
        float((mid.sum() / 3.2) / max(1e-9, off.sum() / 6.4)), 4)

    # ---- B4 scalp visible through the top
    on_cap = (dirs @ up) > 0.45
    above = on_cap & (rr > R * 1.03)
    e1 = unit(np.cross(up, np.array([1.0, 0.0, 0.0])))
    e2 = np.cross(up, e1)
    nb, el_max = 48, np.arccos(0.45)
    az = np.arctan2(dirs[above] @ e2, dirs[above] @ e1)
    el = np.arccos(np.clip((dirs @ up)[above], -1, 1))
    g = np.zeros((nb, nb), dtype=bool)
    g[((az + np.pi) / (2 * np.pi) * nb).astype(int).clip(0, nb - 1),
      (el / el_max * nb).astype(int).clip(0, nb - 1)] = True
    w = np.repeat(np.sin(np.linspace(0, el_max, nb) + el_max / (2 * nb))[None],
                  nb, 0)
    r["B4_scalp_visible_top"] = round(float(1.0 - (g * w).sum() / w.sum()), 4)

    # ---- B5 nape standoff: how far the lowest-back tips sit off the head
    nape = (roots @ fwd < np.percentile(roots @ fwd, 25)) & (roots[:, 2] <
                                                             anat["crown_up"] - 6)
    if nape.sum() > 50:
        t = tips[nape]
        dv = np.linalg.norm(t[:, None, :] - V[None, ::37, :], axis=2).min(1)
        r["B5_nape_standoff_cm"] = round(float(np.percentile(dv, 50)), 3)
    else:
        r["B5_nape_standoff_cm"] = None

    # ---- B6 cluster separation, PARTITION-FREE.
    #
    # The first version partitioned tips by `arange // 260` and compared spread
    # within a block against spread between blocks. That hardcoded 260 while the
    # op that creates the clumps reads `P["clump_block"]`, which is now 120 --
    # so the benchmark was measuring the spread ACROSS TWO REAL CLUMPS and
    # calling it within-clump scatter. Two lists that must agree, stored twice
    # (non-negotiable 24), in an instrument judging the thing it disagreed with.
    #
    # A clustering statistic should not need to know the partition. Clumped tips
    # sit much closer to their NEAREST NEIGHBOUR than to a typical other tip;
    # scattered tips do not. The ratio of those two distances is the measure,
    # and it is blind to how the clumps were made.
    # SECOND ATTEMPT ALSO FAILED, differently, and the failure is worth keeping:
    # nearest-neighbour distance scales as 1/sqrt(density), so on dl_L1 (100,943
    # curves) it read 33.4 and on the clumped dl_B5 (39,628 curves) 29.5 -- the
    # clumped groom scored LOWER, because the statistic was measuring how many
    # strands there are, not how they are arranged.
    #
    # Clumping is a VARIANCE property: locks make some patches dense and the
    # gaps between them empty, while a scattered groom fills evenly. So bin the
    # tips into angular cells and take the coefficient of variation of the
    # counts. CV is dimensionless and density-normalised by construction, which
    # is exactly what the previous two attempts were not.
    # THIRD ATTEMPT FAILED TOO, and its cause is the sharpest of the three:
    # it took the CV over OCCUPIED cells only. Clumping's whole signature is
    # the EMPTY space between locks, so excluding empty cells discards exactly
    # the signal -- and perfect locks, each filling one cell, give uniform
    # occupied counts and therefore a LOW CV. It read 0.99-1.04 across a
    # 27-fold sweep of the lock count while B4 moved freely: a number that will
    # not respond to the knob that owns it is not measuring it.
    #
    # Fourth version: CV over the SUPPORT -- every cell inside the region the
    # hair occupies, zeros included. The support is the occupied set dilated by
    # one cell, so the gaps BETWEEN locks count and the empty sphere outside the
    # hair does not.
    trel = tips - centre
    tdir = trel / np.maximum(np.linalg.norm(trel, axis=1), 1e-9)[:, None]
    ta = np.arctan2(tdir @ e2, tdir @ e1)
    te = np.arccos(np.clip(tdir @ up, -1, 1))
    nc = 40
    ia = ((ta + np.pi) / (2 * np.pi) * nc).astype(int).clip(0, nc - 1)
    ie = (te / np.pi * nc).astype(int).clip(0, nc - 1)
    grid = np.bincount(ia * nc + ie, minlength=nc * nc).astype(float)
    grid = grid.reshape(nc, nc)

    occ = grid > 0
    sup = occ.copy()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            sup |= np.roll(np.roll(occ, dx, 0), dy, 1)
    vals = grid[sup]
    r["_b6_cells_occupied"] = int(occ.sum())
    r["_b6_cells_support"] = int(sup.sum())
    r["_b6_empty_in_support"] = int((vals == 0).sum())
    r["_b6_mean_per_cell"] = round(float(vals.mean()), 2)
    r["B6_cluster_separation"] = round(
        float(vals.std() / max(1e-9, vals.mean())), 4)

    # ---- B7 eyes
    in_eye = ((pts[:, 2] > EYE_LO) & (pts[:, 2] < EYE_HI)
              & ((pts @ fwd) > np.percentile(V @ fwd, 96))
              & (np.abs(pts @ side) < EYE_HALF))
    r["B7_points_in_eye_box"] = int(in_eye.sum())

    verdict = {}
    for key, (cmp_, bar) in BARS.items():
        v = r.get(key)
        if v is None:
            # "I could not measure this" is NOT a pass, and it must not be able
            # to render as one.
            verdict[key] = "COULD NOT MEASURE"
            continue
        ok = (v >= bar) if cmp_ == ">=" else (v <= bar)
        verdict[key] = "PASS" if ok else "FAIL (%s %s %s)" % (v, cmp_, bar)
    r["verdict"] = verdict
    r["bars"] = {k: [c.strip(), b] for k, (c, b) in BARS.items()}
    print("__BM__" + json.dumps(r, default=str))


main()
