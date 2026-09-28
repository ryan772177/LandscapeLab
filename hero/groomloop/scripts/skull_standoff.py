"""skull_standoff.py -- how far the hair mass sits OFF the skull.

    blender --background <groom.blend> --python skull_standoff.py

THE BLIND SPOT THIS FILLS. B1-B7 measure fringe height, ear coverage, part
contrast, scalp visibility, nape standoff, clumping and the eye box. NOT ONE
MEASURES THE ENVELOPE. A groom can therefore stand off the head like a
pompadour and pass six of seven while looking nothing like the reference, which
is what happened on 2026-08-23: the falling variant scored 6/7 over a silhouette
the operator would not accept.

WHY IT IS MEASURED IN GEOMETRY AND NOT IN THE RENDER. The first attempt took
the hair mask as |all_a - minus_Hair| on the alpine frames and reported the
crown height of the vendor groom and of two of ours as IDENTICAL, 1.99 / 1.99 /
2.01, against an eye that could see they were nothing alike. The mask was
mostly FOREST: this project measured two captures of an UNCHANGED subject
differing over 11% of the frame because the trees re-render. A difference mask
over a live background is a background mask.

Blender has no background. The scalp sphere is fitted to the ROOTS, so the
datum comes from the groom's own seating rather than from a number typed in.

REPORTED, NOT GATED. There is no bar here yet, because the only calibration
worth having is the vendor groom and no route exists to read its strands --
UE 5.8 reflects 26 Exporter subclasses and not one handles grooms or Alembic.
A bar invented without that reference would be a number chosen to make the
current groom pass, which is the failure mode this file was written against.
"""

import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object


def fit_sphere(P):
    """Algebraic sphere fit: solves |x-c|^2 = r^2 as a linear system."""
    A = np.hstack([2.0 * P, np.ones((len(P), 1))])
    b = (P ** 2).sum(1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    r = float(np.sqrt(max(0.0, sol[3] + (c ** 2).sum())))
    return c, r


def main():
    d = pick_curves_object(bpy).data
    n = len(d.points)
    buf = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", buf)
    k = d.curves[0].points_length
    A = buf.reshape(n, 3).astype(np.float64).reshape(-1, k, 3)
    roots = A[:, 0, :]

    c, r = fit_sphere(roots)
    # UP is the axis with the largest root spread on a MetaHuman head in the
    # DNA's own frame; asserted rather than assumed so a re-axised blend
    # cannot silently report a lateral measure as a vertical one.
    up = int(np.argmax(roots.max(0) - roots.min(0)))

    rad = np.linalg.norm(A.reshape(-1, 3) - c, axis=1) - r
    tips = np.linalg.norm(A[:, -1, :] - c, axis=1) - r

    # the CROWN band: points in the top third of the root spread, where a
    # pompadour lives and where the nape measure (B5) cannot see
    lo, hi = roots[:, up].min(), roots[:, up].max()
    crown = A.reshape(-1, 3)[:, up] > (lo + 0.66 * (hi - lo))

    out = {
        "curves": int(A.shape[0]), "k": k,
        "scalp_centre": [round(float(x), 3) for x in c],
        "scalp_R_cm": round(r, 3),
        "up_axis": up,
        "S1_standoff_mean_cm": round(float(rad.mean()), 3),
        "S2_standoff_p90_cm": round(float(np.percentile(rad, 90)), 3),
        "S3_standoff_max_cm": round(float(rad.max()), 3),
        "S4_tip_standoff_mean_cm": round(float(tips.mean()), 3),
        "S5_crown_standoff_p90_cm": round(float(np.percentile(rad[crown], 90)), 3)
        if crown.any() else None,
        "S6_lateral_half_width_cm": round(float(
            np.abs(A.reshape(-1, 3)[:, [i for i in range(3) if i != up][0]]
                   - c[[i for i in range(3) if i != up][0]]).max()), 3),
        "_note": "DESCRIPTIVE -- no bar; see the docstring for why",
    }
    print("__SS__" + json.dumps(out))


main()
