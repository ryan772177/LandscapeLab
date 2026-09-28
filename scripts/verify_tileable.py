"""C0 step 2 — is this texture usable as a TILING PBR albedo?

Two independent questions, two independent instruments. A texture may fail
either and be perfectly good art.

1. TILEABILITY — the wrap-seam test.
   When the texture tiles, its left edge continues into its right edge and its
   top into its bottom. So compare the pixel-to-pixel difference ACROSS that
   wrap join (column 0 against the last column, row 0 against the last row) to
   the difference across ordinary interior columns/rows of the same image.
   (This differences the actual edges directly — it does NOT roll the image;
   the seam magnitude is the same either way.) A tiling texture makes the seam
   indistinguishable from the interior; a non-tiling one leaves a visible edge.

   THE INTERIOR IS THE CONTROL, and it has to be, because "how different are
   two adjacent columns" means nothing in the abstract: it is small on plaster
   and large on planks. Comparing the seam against a fixed threshold would pass
   every smooth texture and fail every detailed one regardless of tiling.

2. BAKED LIGHTING — the low-order luminance ramp.
   Fit a plane to the image's luminance. A material albedo should be roughly
   flat: a strong systematic ramp means a light was shining across the surface
   when the image was made, and that lighting will fight the engine's own.
   Reported as the peak-to-peak of the fitted plane, as a fraction of mean
   luminance.

Both report a NUMBER and a verdict, and both name WHY on a refusal rather than
returning a bare fail. --self-test proves each refuses, using synthetic images
built to be exactly the thing it must catch.

Exit 0 all pass · 4 at least one refusal (--self-test also exits 4 when a
synthetic case is NOT caught — a broken instrument) · 5 nothing to check.
"""
import argparse
import glob
import io
import os
import sys

import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEAM_RATIO_MAX = 2.0
_SEAM_WHY = ("seam discontinuity may not exceed this multiple of the image's "
             "own interior discontinuity")
RAMP_MAX = 0.25
RAMP_R2_MIN = 0.25
_RAMP_WHY = ("fitted plane peak-to-peak as a fraction of mean luma, AND "
             "R^2 >= 0.25 so periodic detail is not mistaken for a light ramp")


def luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def seam_ratio(a):
    """Mean |difference| across the wrap seam / across the interior."""
    L = luma(a)
    h, w = L.shape
    # vertical seam: column 0 against column w-1 is the wrap join
    seam_v = np.abs(L[:, 0] - L[:, -1]).mean()
    seam_h = np.abs(L[0, :] - L[-1, :]).mean()
    # interior control: mean adjacent-column and adjacent-row difference,
    # excluding the borders so the seam cannot contaminate its own control
    inner_v = np.abs(np.diff(L[:, 1:-1], axis=1)).mean()
    inner_h = np.abs(np.diff(L[1:-1, :], axis=0)).mean()
    rv = seam_v / max(inner_v, 1e-6)
    rh = seam_h / max(inner_h, 1e-6)
    return rv, rh, inner_v, inner_h


def light_ramp(a):
    """Peak-to-peak of a fitted luminance plane, AND how much it explains.

    THE SECOND NUMBER IS LOAD-BEARING AND THE SELF-TEST IS WHY. Peak-to-peak
    alone called a perfectly flat-lit sinusoidal tile "52.9% baked lighting":
    a full-period sine has a NON-ZERO least-squares linear component (sin is
    odd about its midpoint, and so is x - 0.5, so their product integrates
    non-zero), and any large-scale periodic DETAIL therefore reads as a ramp.

    A real light ramp is MONOTONIC and explains most of the image's variance.
    A sine's linear component explains almost none of it. So refuse only when
    the ramp is both LARGE and EXPLANATORY -- reported as R^2 of the plane fit.
    """
    L = luma(a)
    h, w = L.shape
    yy, xx = np.mgrid[0:h, 0:w]
    A = np.column_stack([xx.ravel() / w, yy.ravel() / h, np.ones(h * w)])
    y = L.ravel()
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    fit = A @ coef
    ss_res = float(((y - fit) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
    return (float(fit.max() - fit.min()) / max(float(L.mean()), 1e-6),
            max(r2, 0.0))


def check(path):
    with Image.open(path) as im:
        a = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    rv, rh, iv, ih = seam_ratio(a)
    ramp, r2 = light_ramp(a)
    worst = max(rv, rh)
    reasons = []
    if not np.isfinite(worst):
        # NN13: an image too small to have a non-border interior yields an
        # empty control (inner_* is nan), so worst is nan and `nan > MAX` is
        # False -- it would slip through as tileable. Refuse instead.
        reasons.append(
            "DEGENERATE: the interior control has no samples (image too small "
            "to have a non-border interior), so tileability cannot be "
            "measured. That is 'I could not look', not tileable.")
    elif worst > SEAM_RATIO_MAX:
        reasons.append(
            "NOT TILEABLE: seam discontinuity is %.2fx the interior "
            "(vertical %.2fx, horizontal %.2fx); bar is %.1fx. It will show a "
            "visible line every tile." % (worst, rv, rh, SEAM_RATIO_MAX))
    if ramp > RAMP_MAX and r2 >= RAMP_R2_MIN:
        reasons.append(
            "BAKED LIGHTING: fitted luminance plane varies %.0f%% of mean "
            "across the image (bar %.0f%%) and explains R^2=%.2f of the "
            "variance, so it is a RAMP and not periodic detail. That light "
            "will fight the engine's."
            % (ramp * 100, RAMP_MAX * 100, r2))
    return {"path": path, "seam_v": rv, "seam_h": rh, "ramp": ramp, "r2": r2,
            "interior_v": iv, "interior_h": ih, "reasons": reasons}


def _synth():
    """Images built to be exactly what each check must catch."""
    n = 256
    yy, xx = np.mgrid[0:n, 0:n]
    rng = np.random.default_rng(7)
    noise = rng.random((n, n, 3)).astype(np.float32)

    # Genuinely tiling AND flat-lit. MULTI-FREQUENCY ON PURPOSE.
    #
    # The first version of this control used ONE sine period across the whole
    # image and the ramp check refused it at R^2 0.60 -- and the check was
    # RIGHT. A single period across the frame IS a gradient by another name,
    # and a texture like that SHOULD be flagged. The specimen was
    # unrepresentative, not the instrument: a real tiling albedo carries detail
    # at several scales, and its linear component then explains almost nothing.
    #
    # Fixing the control rather than loosening the bar is the point. The
    # opposite move -- widening a threshold until the specimen passes -- is how
    # a gate stops meaning anything.
    def band(k, phase):
        return np.sin(2 * np.pi * k * (xx + phase) / n) * np.sin(
            2 * np.pi * k * (yy + phase) / n)

    det = 0.10 * band(4, 0) + 0.05 * band(9, 3) + 0.03 * band(17, 7)
    tile = np.clip(0.5 + np.stack([det, det * 0.9, det * 0.8], -1), 0, 1)
    # NOT tiling: a hard step at the wrap boundary
    notile = tile.copy()
    notile[:, : n // 2] *= 0.45
    # baked light: a strong corner-to-corner ramp on a tiling base
    baked = np.clip(tile * (0.35 + 1.3 * (xx + yy) / (2.0 * n))[..., None], 0, 1)
    return {"tiling_flat": tile, "hard_seam": notile, "baked_ramp": baked,
            "noise": noise}


def self_test():
    print("SELF-TEST — synthetic images built to be the thing each check catches")
    out, bad = {}, 0
    for name, arr in _synth().items():
        rv, rh, _, _ = seam_ratio(arr)
        ramp, r2 = light_ramp(arr)
        out[name] = (max(rv, rh), ramp, r2)
    cases = [
        ("tiling_flat", "seam", False), ("tiling_flat", "ramp", False),
        ("hard_seam", "seam", True),
        ("baked_ramp", "ramp", True),
        ("noise", "seam", False),
    ]
    for name, which, want_fail in cases:
        s, r, r2 = out[name]
        got = ((s > SEAM_RATIO_MAX) if which == "seam"
               else (r > RAMP_MAX and r2 >= RAMP_R2_MIN))
        ok = got == want_fail
        bad += 0 if ok else 1
        print("  %-12s %-5s seam %6.2fx  ramp %5.1f%% R2 %4.2f -> %-8s want %-8s %s"
              % (name, which, s, r * 100, r2,
                 "REFUSE" if got else "pass", "REFUSE" if want_fail else "pass",
                 "ok" if ok else "!! WRONG"))
    print()
    print("self-test: %d of %d correct" % (len(cases) - bad, len(cases)))
    return 4 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    paths = a.paths or sorted(glob.glob(os.path.join(REPO, "refs",
                                                     "textures_v1", "*.*")))
    if not paths:
        print("NOTHING TO CHECK — that is 'I could not look', not a pass.")
        return 5

    print("tileability and baked-lighting check")
    print("  seam bar  %.1fx   (%s)" % (SEAM_RATIO_MAX, _SEAM_WHY))
    print("  ramp bar  %.0f%%    (%s)" % (RAMP_MAX * 100, _RAMP_WHY))
    print()
    print("  %-16s %8s %8s %8s %6s   verdict"
          % ("texture", "seam_v", "seam_h", "ramp", "R2"))
    refused = []
    for p in paths:
        r = check(p)
        name = os.path.basename(p)
        print("  %-16s %7.2fx %7.2fx %7.1f%% %6.2f   %s"
              % (name, r["seam_v"], r["seam_h"], r["ramp"] * 100, r["r2"],
                 "REFUSED" if r["reasons"] else "ok"))
        for why in r["reasons"]:
            print("        %s" % why)
        if r["reasons"]:
            refused.append(name)
    print()
    if refused:
        print("REFUSED %d of %d: %s" % (len(refused), len(paths),
                                        ", ".join(refused)))
        return 4
    print("All %d usable as tiling albedo." % len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
