"""verify_dna_edit.py -- check an edited DNA against base + THE EDITS ACTUALLY MADE.

    python verify_dna_edit.py --base <base.dna> --edited <edited.dna> \
        --edit box_min:box_max:feather:delta [--edit ...]

WHY THIS EXISTS AND THE OTHER ONE DID NOT COVER IT.
`_verify/20260823_face/measure_dna_offline.py --verify` carries a HARDCODED
`EDITS` list -- the six edits of the angular-hero pass -- and predicts
`base + those six`. Pointed at a different edit it reports FAIL while being
entirely correct about the question it was asked, which is not the question the
caller meant. It said "weighted vertices 5200" for a pair of edits that touched
1,296 and 1,289, and that number was the tell: it is the union of the SIX
angular boxes.

A fixed-plan checker is right for the plan it encodes and silently wrong for
anything else. This one takes the edits as arguments, so the prediction is the
hypothesis the caller actually holds.

THE MASK IS NOT REIMPLEMENTED FROM MEMORY. `_weights` is imported from
`measure_dna_offline`, whose own docstring records it as a line-for-line copy of
the plugin's mask. Re-deriving a smoothstep here would make agreement between
this tool and the plugin a coincidence rather than a check.

ORDER MATTERS AND IS PRESERVED. Each edit re-evaluates its mask on the CURRENT
positions, so a lateral move followed by a depth move is not the same as the
reverse -- the second mask sees vertices the first one moved.

THE ZERO-WEIGHT CHECK IS THE POINT, not an afterthought. A region edit that
quietly perturbs vertices outside its own box is the failure nobody looks for,
and the angular plan explicitly recorded it as unverified because no DNA
existed yet to check.
"""

import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "_verify", "20260823_face"))

import measure_dna_offline as M  # noqa: E402


def parse_edit(s):
    """'x,y,z:x,y,z:feather:dx,dy,dz'"""
    a = s.split(":")
    if len(a) != 4:
        raise SystemExit("REFUSE: --edit needs box_min:box_max:feather:delta, "
                         "got %r" % s)
    bmin = tuple(float(v) for v in a[0].split(","))
    bmax = tuple(float(v) for v in a[1].split(","))
    band = float(a[2])
    delta = tuple(float(v) for v in a[3].split(","))
    if len(bmin) != 3 or len(bmax) != 3 or len(delta) != 3:
        raise SystemExit("REFUSE: box and delta are three numbers each")
    return bmin, bmax, band, delta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--edited", required=True)
    ap.add_argument("--edit", action="append", required=True,
                    help="box_min:box_max:feather:delta, repeatable, IN ORDER")
    ap.add_argument("--tolerance-cm", type=float, default=1e-3,
                    help="the plugin's own, LandscapeLabTools.cpp:1435")
    a = ap.parse_args()

    edits = [parse_edit(s) for s in a.edit]

    rb = M.read_head(os.path.join(REPO, a.base)) if not os.path.isabs(a.base) \
        else M.read_head(a.base)
    re_ = M.read_head(os.path.join(REPO, a.edited)) \
        if not os.path.isabs(a.edited) else M.read_head(a.edited)

    print("base   %s" % a.base)
    print("  sha256 %s" % rb["sha"])
    print("edited %s" % a.edited)
    print("  sha256 %s" % re_["sha"])
    if not M.check_parse(rb, quiet=True):
        raise SystemExit("parse control failed on the base")

    P = rb["P"].copy()
    W = np.zeros(P.shape[0])
    for bmin, bmax, band, delta in edits:
        w, core = M._weights(P, bmin, bmax, band)
        W = np.maximum(W, w)
        P = P + w[:, None] * np.asarray(delta, float)
        _core = int(np.asarray(core).sum())
        print("  edit  box %s..%s  feather %.2f  delta %s  -> %d weighted, "
              "%d core" % (bmin, bmax, band, delta, int((w > 0).sum()), _core))

    d = np.abs(re_["P"] - P).max(axis=1)
    weighted = W > 0.0
    print()
    print("  weighted vertices  %6d   max |predicted - file|  %.6f cm"
          % (int(weighted.sum()), d[weighted].max()))
    print("  zero-weight        %6d   max |predicted - file|  %.6f cm"
          % (int((~weighted).sum()), d[~weighted].max()))
    print("  ALL %d checked" % d.size)

    ok = d.max() <= a.tolerance_cm
    print()
    print("  VERDICT %s (tolerance %g cm)"
          % ("PASS" if ok else "FAIL", a.tolerance_cm))
    return 0 if ok else 4


sys.exit(main())
