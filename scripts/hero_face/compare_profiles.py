"""compare_profiles.py — the MetaHuman's head profile against the hero's, on one scale.

THE IDEA THAT MAKES THIS TRACTABLE
    Identifying which of the 79 sculpt landmarks is "the nose" is guesswork,
    and guessed anatomy already produced one 13.7 cm nose-to-chin here. But
    the sculpt does not actually need names. It needs to know, at each height
    up the head, HOW MUCH WIDER OR NARROWER the hero is than the MetaHuman.

    That is a width-versus-height profile, and it can be measured on both
    subjects by the same definition:

        half-width(z) = max |x - x_sagittal| over landmarks near height z
        half-width(d) = (silhouette x1 - x0) / 2 at depth d below the crown

    Two different representations -- a 3D landmark cloud and a photograph's
    chroma silhouette -- reduced to one comparable curve. Neither instrument
    can see the other's subject, which is the point.

NORMALISATION, AND WHY NOT BY MAX WIDTH
    Both profiles are expressed as a fraction of their own CRANIUM width
    (the widest band strictly ABOVE the ear line) and positioned by depth
    below the crown in units of that same width. Normalising by the overall
    max would key both curves to the ear line, and ears are exactly where a
    sparse landmark cloud and a photographic outline are least comparable.

WHAT IT DOES NOT CLAIM
    Depth (the Y axis) is invisible to a frontal photograph. Nothing in this
    file measures brow protrusion, eye recession or nose projection, and
    nothing here should be read as having done so.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def mh_profile(pts, sag, nbins):
    """half-width vs height for the landmark cloud, top-down."""
    zs = [p[2] for p in pts]
    zmin, zmax = min(zs), max(zs)
    span = zmax - zmin
    bins = []
    for b in range(nbins):
        hi = zmax - span * b / nbins
        lo = zmax - span * (b + 1) / nbins
        members = [p for p in pts if (lo - 1e-9) <= p[2] <= (hi + 1e-9)]
        if not members:
            bins.append(None)
            continue
        half = max(abs(p[0] - sag) for p in members)
        bins.append({"z_hi": hi, "z_lo": lo,
                     "depth": (zmax - (hi + lo) / 2.0),
                     "half_width": half, "n": len(members)})
    return bins, zmin, zmax


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(
        root, "hero", "generated", "face_state_baseline.json"))
    ap.add_argument("--silhouette", default=os.path.join(
        root, "hero", "generated", "reference_silhouette.json"))
    ap.add_argument("--bins", type=int, default=14)
    ap.add_argument("--out", default=os.path.join(
        root, "hero", "generated", "profile_comparison.json"))
    args = ap.parse_args(argv)

    pts = json.load(open(args.state))["landmarks"]
    sil = json.load(open(args.silhouette))

    # sagittal plane, re-derived here rather than carried in as a constant
    sag = sum(p[0] for p in pts) / len(pts)
    bins, zmin, zmax = mh_profile(pts, sag, args.bins)
    live = [b for b in bins if b]
    if not live:
        print("REFUSE: no populated height bins")
        return 1

    # cranium reference = widest band in the TOP HALF, which is above the ears
    top_half = [b for b in live if b["depth"] <= 0.5 * (zmax - zmin)]
    mh_cran = max(b["half_width"] for b in top_half)
    mh_W = 2.0 * mh_cran

    # same definition on the photograph
    prof = sil["profile"]
    crown_y = sil["crown_y"]
    Wmax = float(sil["widest_row"]["width"])
    # profile entries are normalised to Wmax; convert to px then to cranium W
    ref_pts = [(p["depth_over_W"] * Wmax, p["width_over_W"] * Wmax)
               for p in prof if not p["clipped"]]
    ref_top = [wd for dp, wd in ref_pts if dp <= 0.55 * Wmax]
    ref_W = max(ref_top) if ref_top else Wmax

    print("MetaHuman : sagittal x = %.5f, cranium width = %.5f units"
          % (sag, mh_W))
    print("Hero photo: cranium width = %.1f px  (max row %.0f px = ears)"
          % (ref_W, Wmax))
    print("")
    print("Both profiles as a fraction of their OWN cranium width.")
    print("ratio > 1 means the HERO is wider there and the MetaHuman must widen.")
    print("")
    print(" depth/W   MH w/W   HERO w/W   ratio   n   band")
    rows = []
    for b in live:
        d_over_W = b["depth"] / mh_W
        mh_w = 2.0 * b["half_width"] / mh_W
        # nearest reference sample by normalised depth
        best = None
        for dp, wd in ref_pts:
            dd = abs(dp / ref_W - d_over_W)
            if best is None or dd < best[0]:
                best = (dd, dp / ref_W, wd / ref_W)
        if best is None or best[0] > 0.08:
            print("  %.3f    %.3f      --        --    %2d  (no reference sample)"
                  % (d_over_W, mh_w, b["n"]))
            continue
        _, rd, rw = best
        ratio = rw / mh_w if mh_w > 1e-9 else float("nan")
        rows.append({"depth_over_W": round(d_over_W, 4),
                     "mh_width_over_W": round(mh_w, 4),
                     "hero_width_over_W": round(rw, 4),
                     "ratio": round(ratio, 4), "n": b["n"],
                     "z_lo": b["z_lo"], "z_hi": b["z_hi"]})
        print("  %.3f    %.3f     %.3f     %.3f  %2d"
              % (d_over_W, mh_w, rw, ratio, b["n"]))

    json.dump({"sagittal_x": sag, "mh_cranium_width": mh_W,
               "ref_cranium_width_px": ref_W, "bands": rows},
              open(args.out, "w"), indent=2)
    print("")
    print("wrote %s" % args.out)
    print("")
    print("NOT MEASURED HERE: depth (Y). A frontal photograph carries no")
    print("brow protrusion, eye recession or nose projection, and this file")
    print("does not pretend to have recovered any.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
