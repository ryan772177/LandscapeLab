"""plan_lateral_correction.py — widen the face by the MEASURED shortfall.

The first sculpt closed 82% of its targets and the result is a coherent face.
Measuring the sculpted MESH against the photograph -- 33,845 vertices against
a chroma silhouette, the same width-at-height definition on both -- shows the
hero is still wider than the MetaHuman almost everywhere:

    d/W 0.13-0.54  (cranium)   ratio 1.04 - 1.17
    d/W 0.59-0.64  (ear line)  ratio 1.00 - 1.02
    d/W 0.69-0.95  (jaw)       ratio 1.13 - 1.22

This plans a SECOND pass that scales each landmark's distance from the
sagittal plane by the ratio measured AT THAT HEIGHT. Nothing here is a
judgement about how wide a jaw should be; the number comes from the
photograph.

WHY IT RE-BASELINES
    The first spec carries absolute targets derived from the ORIGINAL state.
    This pass must start from where the face actually IS, or the two specs
    would fight. So it reads the current landmarks and emits new absolute
    targets on top of them.

WHAT IT DELIBERATELY DOES NOT TOUCH
    Depth and height. The ratio curve is a LATERAL measurement and carries no
    information about either, so applying it to Y or Z would be inventing
    data. Only X moves here.

    It also damps the correction (--damp) and caps it, because the face model
    saturates on large moves and the previous pass already drew a
    "Potential Degenerate Triangles" warning from the auto-rigger. Widening
    the jaw by the full measured 22% in one step is exactly the move most
    likely to make that worse.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(
        root, "hero", "generated", "face_state_current.json"))
    ap.add_argument("--ratio", default=os.path.join(
        root, "hero", "generated", "mesh_vs_hero_ratio.json"))
    ap.add_argument("--out", default=os.path.join(
        root, "hero", "generated", "face_lateral_spec.json"))
    ap.add_argument("--damp", type=float, default=0.6,
                    help="fraction of the measured shortfall to apply")
    ap.add_argument("--max-ratio", type=float, default=1.18,
                    help="refuse to scale any band by more than this")
    args = ap.parse_args(argv)

    pts = json.load(open(args.state))["landmarks"]
    rj = json.load(open(args.ratio))
    curve = rj["curve"]
    if not curve:
        print("REFUSE: ratio curve is empty -- nothing measured to correct")
        return 1

    n = len(pts)
    xs = [p[0] for p in pts]
    zs = [p[2] for p in pts]
    x_sag = sum(xs) / n
    z_min, z_max = min(zs), max(zs)
    # The ratio curve's depth axis is "below the crown, in units of the mesh's
    # own cranium width". Convert each landmark's height into that axis using
    # the MESH's z range, which is what the curve was measured on.
    mz_min, mz_max = rj["z_min"], rj["z_max"]
    cran = rj["mesh_cranium_width"]

    def ratio_at(z):
        dw = (mz_max - z) / cran
        best = None
        for c in curve:
            dd = abs(c["depth_over_W"] - dw)
            if best is None or dd < best[0]:
                best = (dd, c["ratio"])
        # Outside the measured band there is no measurement, and inventing
        # one is how a correction becomes a guess. Return 1.0 -- no change.
        if best is None or best[0] > 0.06:
            return 1.0, False
        return best[1], True

    deltas = {}
    applied = 0
    outside = 0
    clamped = 0
    for i, p in enumerate(pts):
        r, ok = ratio_at(p[2])
        if not ok:
            outside += 1
            continue
        if r > args.max_ratio:
            r = args.max_ratio
            clamped += 1
        eff = 1.0 + (r - 1.0) * args.damp
        dx = (p[0] - x_sag) * (eff - 1.0)
        if abs(dx) < 1e-9:
            continue
        deltas[i] = [dx, 0.0, 0.0]
        applied += 1

    targets = {str(i): [pts[i][0] + deltas[i][0], pts[i][1], pts[i][2]]
               for i in deltas}

    print("landmarks          : %d" % n)
    print("corrected          : %d" % applied)
    print("outside the curve  : %d (left alone -- no measurement there)" % outside)
    print("clamped at %.2f     : %d" % (args.max_ratio, clamped))
    print("damping            : %.2f of the measured shortfall" % args.damp)
    if deltas:
        mags = sorted(abs(d[0]) for d in deltas.values())
        print("lateral move       : median %.6f  max %.6f units"
              % (mags[len(mags) // 2], mags[-1]))

    json.dump({"source_state": os.path.relpath(args.state, root).replace("\\", "/"),
               "ratio_source": os.path.relpath(args.ratio, root).replace("\\", "/"),
               "damp": args.damp, "max_ratio": args.max_ratio,
               "frame": {"sagittal_x": x_sag},
               "deltas": {str(k): v for k, v in deltas.items()},
               "targets": targets}, open(args.out, "w"), indent=2)
    print("")
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
