"""face_metrics.py — reduce tracked face curves to comparable proportions.

WHY A CANONICAL FRAME
    Three faces need comparing: the bald reference, the haired reference
    (Ryan's ruled product look) and the MetaHuman's own render. They were
    photographed or rendered at different framings and sizes, so raw pixel
    coordinates are not comparable and any difference read off them would be
    mostly framing.

    So every face is put in ONE frame first, defined only by things all three
    have: the two eyes. Origin at the midpoint between eye centres, scale =
    the interpupillary distance, rotation = the eye line. Every number below
    is then in IPD units and dimensionless.

    This is the same discipline as the project's "state the denominator" rule
    (non-negotiable 22): a width means nothing until you say a width of what.

WHAT IT CANNOT MEASURE
    The tracker returns eyelids, lips, philtrum and nasolabial folds. It
    returns NO brow curve, NO nose curve and NO jaw curve. Anything this file
    says about brow, nose or jaw would therefore be invention, so it says
    nothing about them -- the silhouette instrument covers the jaw and skull,
    and brow/nose depth is not measurable from a frontal image at all.

Usage:
    python scripts/hero_face/face_metrics.py A.json [B.json ...] [--labels a,b]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

L_EYE = ("crv_eyelid_upper_l", "crv_eyelid_lower_l")
R_EYE = ("crv_eyelid_upper_r", "crv_eyelid_lower_r")


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def gather(curves, names):
    out = []
    for n in names:
        out.extend(curves.get(n, []))
    return out


def canonical(curves):
    """Return (transform, info) putting the face in eye-anchored IPD space."""
    le, re = gather(curves, L_EYE), gather(curves, R_EYE)
    if not le or not re:
        return None, "missing eyelid curves; cannot build a canonical frame"
    lc, rc = centroid(le), centroid(re)
    dx, dy = rc[0] - lc[0], rc[1] - lc[1]
    ipd = math.hypot(dx, dy)
    if ipd < 1e-6:
        return None, "degenerate interpupillary distance"
    ang = math.atan2(dy, dx)
    ox, oy = (lc[0] + rc[0]) / 2.0, (lc[1] + rc[1]) / 2.0
    ca, sa = math.cos(-ang), math.sin(-ang)

    def tf(p):
        x, y = p[0] - ox, p[1] - oy
        xr, yr = x * ca - y * sa, x * sa + y * ca
        # +y downward in image space; flip so +y is UP, like the face frame
        return (xr / ipd, -yr / ipd)

    return tf, {"ipd_px": ipd, "eye_line_deg": math.degrees(ang),
                "left_eye_px": lc, "right_eye_px": rc}


def span(pts, axis):
    vs = [p[axis] for p in pts]
    return max(vs) - min(vs)


def metrics(curves):
    tf, info = canonical(curves)
    if tf is None:
        return None, info
    C = {k: [tf(p) for p in v] for k, v in curves.items()}
    m = {}

    for tag, names in (("eye_l", L_EYE), ("eye_r", R_EYE)):
        e = gather(C, names)
        if e:
            m[tag + "_width"] = span(e, 0)
            m[tag + "_height"] = span(e, 1)
            m[tag + "_centre_y"] = centroid(e)[1]

    lip_outer = gather(C, ("crv_lip_upper_outer_l", "crv_lip_upper_outer_r",
                           "crv_lip_lower_outer_l", "crv_lip_lower_outer_r"))
    if lip_outer:
        m["mouth_width"] = span(lip_outer, 0)
        m["mouth_height"] = span(lip_outer, 1)
        m["mouth_centre_y"] = centroid(lip_outer)[1]
        xs = sorted(p[0] for p in lip_outer)
        m["mouth_corner_l"] = xs[0]
        m["mouth_corner_r"] = xs[-1]

    up_out = gather(C, ("crv_lip_upper_outer_l", "crv_lip_upper_outer_r"))
    up_in = gather(C, ("crv_lip_upper_inner_l", "crv_lip_upper_inner_r"))
    lo_out = gather(C, ("crv_lip_lower_outer_l", "crv_lip_lower_outer_r"))
    lo_in = gather(C, ("crv_lip_lower_inner_l", "crv_lip_lower_inner_r"))
    if up_out and up_in:
        m["upper_lip_thickness"] = centroid(up_in)[1] - centroid(up_out)[1]
    if lo_out and lo_in:
        m["lower_lip_thickness"] = centroid(lo_in)[1] - centroid(lo_out)[1]

    ph = gather(C, ("crv_lip_philtrum_l", "crv_lip_philtrum_r"))
    if ph:
        m["philtrum_width"] = span(ph, 0)
        m["philtrum_height"] = span(ph, 1)

    # The nasolabial folds are the only cheek measurement available. Their
    # OUTER extent is roughly the cheek width at mouth level; their TOP is
    # roughly the nose base.
    nl = gather(C, ("crv_nasolabial_l", "crv_nasolabial_r"))
    if nl:
        m["nasolabial_width"] = span(nl, 0)
        m["nasolabial_top_y"] = max(p[1] for p in nl)
        m["nasolabial_bottom_y"] = min(p[1] for p in nl)
    nl_l = C.get("crv_nasolabial_l", [])
    nl_r = C.get("crv_nasolabial_r", [])
    if nl_l and nl_r:
        m["nasolabial_sep_top"] = abs(
            max(nl_r, key=lambda p: p[1])[0] - max(nl_l, key=lambda p: p[1])[0])

    # eye-to-mouth is the single most face-shape-bearing ratio available:
    # a long face pushes the mouth further below the eye line.
    if "mouth_centre_y" in m:
        m["eye_to_mouth"] = -m["mouth_centre_y"]
    return m, info


ORDER = ["eye_l_width", "eye_r_width", "eye_l_height", "eye_r_height",
         "mouth_width", "mouth_height", "eye_to_mouth",
         "upper_lip_thickness", "lower_lip_thickness",
         "philtrum_width", "philtrum_height",
         "nasolabial_width", "nasolabial_sep_top",
         "nasolabial_top_y", "nasolabial_bottom_y"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--labels", default=None)
    args = ap.parse_args(argv)

    labels = (args.labels.split(",") if args.labels else
              [os.path.splitext(os.path.basename(f))[0] for f in args.files])
    if len(labels) != len(args.files):
        print("REFUSE: %d labels for %d files" % (len(labels), len(args.files)))
        return 2

    all_m, all_i = [], []
    for f in args.files:
        d = json.load(open(f))
        m, i = metrics(d["curves"])
        if m is None:
            print("REFUSE (%s): %s" % (f, i))
            return 1
        all_m.append(m)
        all_i.append(i)

    print("All values in INTERPUPILLARY DISTANCE units (dimensionless).")
    print("")
    for lb, i in zip(labels, all_i):
        print("  %-14s ipd %7.2f px   eye line %+6.2f deg"
              % (lb, i["ipd_px"], i["eye_line_deg"]))
    print("")
    hdr = "  %-22s" % "metric" + "".join("%12s" % l[:12] for l in labels)
    if len(labels) > 1:
        hdr += "%12s" % "B/A"
    print(hdr)
    print("  " + "-" * (22 + 12 * (len(labels) + (1 if len(labels) > 1 else 0))))
    for k in ORDER:
        if not any(k in m for m in all_m):
            continue
        row = "  %-22s" % k
        for m in all_m:
            row += ("%12.4f" % m[k]) if k in m else "%12s" % "--"
        if len(all_m) > 1 and k in all_m[0] and k in all_m[-1]:
            a, b = all_m[0][k], all_m[-1][k]
            row += ("%12.3f" % (b / a)) if abs(a) > 1e-9 else "%12s" % "--"
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
