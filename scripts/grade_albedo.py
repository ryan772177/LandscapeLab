"""Deterministic colour grade of a swapped albedo toward the map it replaced.

THE RULING, 2026-08-30
----------------------
Measured on the flat stage, with lighting equalised so the comparison was
finally valid:

    metric                ORIGINAL   SWAPPED    delta
    saturation              0.0532    0.1008    +90%
    warmth (R-B)           +0.0157   +0.0633    4.0x
    local contrast (luma)   0.1575    0.1580    UNCHANGED

The operator's call: *"+90% saturation / 4.0x warmth is real and too far --
keep the timber-vs-plaster legibility, lose the orange."*

So: grade `wall_planks_b` and `roof_tiles` toward roughly the MIDPOINT of the
measured values, and darken the timber slightly toward the concept chalets.

WHY MIDPOINT-OF-MEASURED AND NOT A HAND-PICKED LOOK
---------------------------------------------------
Both endpoints are measured, so the target is derived rather than chosen, and
anyone can recompute it. A hand-tuned "looks about right" would be
unreproducible and would have to be re-litigated every time a texture changed.

WHAT IT DELIBERATELY DOES NOT TOUCH
-----------------------------------
**Luminance detail.** The measurement showed local contrast statistically
identical between the two sets (0.1575 vs 0.1580), which is what makes the
timber read against the plaster. The grade scales CHROMA and applies a flat
luma gain; the chroma-scale step preserves luma exactly, but the warmth-damp
step and the final clip perturb it slightly (whenever R!=B), so detail is
APPROXIMATELY preserved and the "detail" column is reported and checked
empirically rather than guaranteed by construction.

Usage:
    python scripts/grade_albedo.py --plan
    python scripts/grade_albedo.py --apply
"""
import argparse
import io
import json
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Image.MAX_IMAGE_PIXELS = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DONOR = os.path.join(REPO, "Free", "_intake", "medieval_house_c0",
                     "source", "Medival House _.fbm")

# role -> (swapped albedo, the ORIGINAL it replaced, mode)
#   chroma  : pull saturation and warmth toward the midpoint of the two
#   darken  : keep the hue, apply a flat luma gain (the timber)
JOBS = {
    "wall_planks_b": ("refs/textures_v1/wall_planks_b_tiled.jpg",
                      "brown_planks_03_diff_2k.jpg", "chroma"),
    "roof_tiles": ("refs/textures_v1/roof_tiles_tiled.jpg",
                   "grey_roof_01_diff_4k.jpg", "chroma"),
    "beam_wood": ("refs/textures_v1/beam_wood_tiled.jpg",
                  "rough_wood_diff_2k.jpg", "darken"),
}
TIMBER_LUMA_GAIN = 0.90     # "slightly darkened toward the concept chalets"


def load(p):
    with Image.open(p) as im:
        return np.asarray(im.convert("RGB")).astype(np.float64) / 255.0


def stats(a):
    L = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return {"luma": float(L.mean()), "sat": float(sat.mean()),
            "warmth": float((a[..., 0] - a[..., 2]).mean()),
            "detail": float(L.std())}


def grade_chroma(a, k_sat, k_warm):
    """Scale chroma about the per-pixel luma, then damp the R-B split.

    Working about luma keeps brightness under the chroma SCALE exactly; the
    subsequent warmth-damp (and the final clip) shift luma slightly whenever
    R!=B, so DETAIL is APPROXIMATELY preserved -- the thing the ruling asked
    for -- and the "detail" delta is reported so it can be checked, not assumed.
    """
    L = (0.2126 * a[..., 0] + 0.7152 * a[..., 1]
         + 0.0722 * a[..., 2])[..., None]
    out = L + (a - L) * k_sat
    # damp the red-blue axis specifically: that is what reads as "orange"
    mid = (out[..., 0] + out[..., 2]) * 0.5
    r = mid + (out[..., 0] - mid) * k_warm
    b = mid + (out[..., 2] - mid) * k_warm
    out = np.stack([r, out[..., 1], b], -1)
    return np.clip(out, 0.0, 1.0)


def solve_pair(a, t_sat, t_warm, rounds=6):
    """Solve BOTH gains together, because they are not independent.

    ⛔ TWO WRONG VERSIONS PRECEDED THIS ONE, and the second was worse than the
    first:

      1. `k = target / current`. `sat` is (max-min)/max averaged, and scaling
         (colour - luma) by k does not scale that by k. wall_planks_b was asked
         for 0.4248 and landed at 0.3103.
      2. Bisect each gain separately. Landed at 0.2739 -- FURTHER from target.
         The warmth damp pulls the red and blue channels toward their mean,
         which REMOVES SATURATION TOO, so a k_sat solved with k_warm=1 is
         applied to an image the warmth damp has already desaturated. Two
         couplings, each solved as if the other did not exist.

    So: solve warmth first, then solve saturation WITH that warmth gain in
    place, and alternate a few rounds so each sees the other's effect. The
    residual coupling is then reported rather than hidden.
    """
    k_sat, k_warm = 1.0, 1.0
    for _ in range(rounds):
        k_warm = _bisect(
            lambda k: stats(grade_chroma(a, k_sat, k))["warmth"], t_warm)
        k_sat = _bisect(
            lambda k: stats(grade_chroma(a, k, k_warm))["sat"], t_sat)
    return k_sat, k_warm


def _bisect(measure, target, lo=0.02, hi=1.0, iters=22):
    base = measure(1.0)
    if base <= 1e-9 or target >= base:
        return 1.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if measure(mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def plan():
    rows = []
    for role, (new_rel, old_name, mode) in sorted(JOBS.items()):
        new_p = os.path.join(REPO, new_rel)
        old_p = os.path.join(DONOR, old_name)
        if not os.path.isfile(new_p) or not os.path.isfile(old_p):
            print("  !! missing input for %s" % role)
            continue
        sn, so = stats(load(new_p)), stats(load(old_p))
        if mode == "chroma":
            t_sat = (sn["sat"] + so["sat"]) * 0.5
            t_warm = (sn["warmth"] + so["warmth"]) * 0.5
            a_new = load(new_p)
            k_sat, k_warm = solve_pair(a_new, t_sat, t_warm)
            k_luma = 1.0
        else:
            t_sat, t_warm = sn["sat"], sn["warmth"]
            k_sat = k_warm = 1.0
            k_luma = TIMBER_LUMA_GAIN
        rows.append({"role": role, "mode": mode, "new": new_rel,
                     "replaced": old_name, "swapped": sn, "original": so,
                     "target_sat": t_sat, "target_warmth": t_warm,
                     "k_sat": k_sat, "k_warm": k_warm, "k_luma": k_luma})
    return rows


def report(rows):
    print("  %-14s %-7s %8s %8s %8s   %8s %8s"
          % ("role", "mode", "sat now", "sat old", "-> target",
             "warm now", "-> target"))
    for r in rows:
        print("  %-14s %-7s %8.4f %8.4f %9.4f   %8.4f %9.4f"
              % (r["role"], r["mode"], r["swapped"]["sat"],
                 r["original"]["sat"], r["target_sat"],
                 r["swapped"]["warmth"], r["target_warmth"]))
    print("")
    print("  gains:  " + "   ".join(
        "%s k_sat %.3f k_warm %.3f k_luma %.3f"
        % (r["role"], r["k_sat"], r["k_warm"], r["k_luma"]) for r in rows))


def apply(rows):
    out_dir = os.path.join(REPO, "refs", "textures_v1")
    written = []
    print("")
    print("  %-14s %10s %10s %10s   %s"
          % ("role", "sat after", "warm after", "detail", "residual vs target"))
    for r in rows:
        a = load(os.path.join(REPO, r["new"]))
        before = stats(a)
        if r["mode"] == "chroma":
            g = grade_chroma(a, r["k_sat"], r["k_warm"])
        else:
            g = np.clip(a * r["k_luma"], 0.0, 1.0)
        root = os.path.basename(r["new"]).replace("_tiled.jpg", "")
        p = os.path.join(out_dir, root + "_graded.jpg")
        Image.fromarray((g * 255.0 + 0.5).astype(np.uint8)).save(p, quality=95)
        # READ BACK from the lossy artefact actually written (rule 12/13), not
        # from the ideal float `g` -- the uint8 quantization + JPEG q95 are what
        # downstream consumes, so the reported "after" must describe THAT.
        after = stats(load(p))
        written.append((r["role"], os.path.relpath(p, REPO).replace("\\", "/")))
        dsat = after["sat"] - r["target_sat"]
        dwarm = after["warmth"] - r["target_warmth"]
        print("  %-14s %10.4f %10.4f %10.4f   sat %+.4f  warm %+.4f  det %+.4f"
              % (r["role"], after["sat"], after["warmth"], after["detail"],
                 dsat, dwarm, after["detail"] - before["detail"]))
    print("")
    print("  DETAIL IS THE COLUMN THAT MATTERS: it should barely move (the")
    print("  chroma scale preserves luma; the warmth damp perturbs it slightly).")
    print("  The ruling asked to keep timber-vs-plaster legibility, which lives")
    print("  in luminance contrast -- watch the 'det' delta above to confirm it.")
    print("")
    for role, p in written:
        print("  wrote %-14s %s" % (role, p))
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not (a.plan or a.apply):
        ap.error("--plan or --apply")
    print("GRADE -- toward the MIDPOINT of two measured endpoints")
    print("")
    rows = plan()
    # NN13: a grade over ZERO roles, or a PARTIAL grade with inputs missing,
    # is not success. plan() silently `continue`s past a missing input (the
    # "!! missing input" line above); refuse rather than write an empty
    # manifest and exit 0.
    if not rows:
        print("REFUSE: no gradable roles -- every input was missing. That is "
              "'I could not look', not a completed grade.")
        return 2
    if len(rows) < len(JOBS):
        print("REFUSE: %d of %d roles had a missing input (see !! above); a "
              "partial grade is not a pass." % (len(JOBS) - len(rows), len(JOBS)))
        return 2
    report(rows)
    if a.apply:
        written = apply(rows)
        man = os.path.join(REPO, "_verify", "20260830_overnight",
                           "grade_plan.json")
        with io.open(man, "w", encoding="utf-8") as fh:
            json.dump({"jobs": rows, "written": written}, fh, indent=1)
        print("  plan + result: %s" % os.path.relpath(man, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
