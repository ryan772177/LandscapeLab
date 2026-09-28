"""verify_frames.py — prove a capture run produced USABLE frames.

WHY THIS EXISTS
A capture that writes nothing is indistinguishable, in a report, from a
capture that found nothing wrong. Both are silence. `capture.py` already
fails closed and returns a distinct exit code, but the frames themselves
have never been checked before being reasoned about — and the failure
this guards is not only ZERO frames. A frame can exist, weigh 2 MB and
still be worthless: 98% sky, a black screen during a streaming hitch, a
uniform grey while shaders compile. Every one of those reads as evidence
in a sweep report.

So: count, size, and CONTENT. A frame passes only if it is present, of
the expected dimensions, and carries real tonal structure.

WHAT "TRIVIAL" MEANS HERE, and why each test is separate
  - EMPTY / TINY      the file is missing or implausibly small
  - WRONG SIZE        not the resolution the recipe asked for
  - FLAT              standard deviation of luma below FLAT_STD; a
                      uniform frame has no content whatever its mean
  - CRUSHED / BLOWN   most of the frame pinned at one end of the range
Reported separately rather than as one "bad" verdict, because they have
different causes: FLAT is usually a compile or streaming stall, BLOWN is
usually exposure, CRUSHED is usually an unlit or shadowed subject.

LUMA IS DISPLAY-REFERRED. These are sRGB-encoded PNG values with Rec.709
coefficients, NOT scene-linear luminance. That is the right space for
"can a human read this frame", which is the question here, and the wrong
space for photometry — atmosphere_solve.py owns that and works in linear.
Stated because a luma number that silently changed space would be the
misleading-denominator class (non-negotiable 22).

Exit codes:
  0  every expected frame present and non-trivial (only reachable with --tag)
  1  unexpected error
  2  the recipe could not be read, or nothing matched the selector
     (0 expected frames — a recipe with no capture.cameras, or an empty
     --expect)
  3  a frame is MISSING, or present and TRIVIAL — the run does not
     support a verdict
  4  no --tag given; verdict WITHHELD (this checks newest-per-camera across
     ALL tags, not one run)
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import landscape_spec     # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT

# A 1920x1080 PNG of real terrain runs 1.5-5 MB in this project. 100 KiB is
# far below anything observed and comfortably above a truncated write.
MIN_BYTES = 100 * 1024   # 100 KiB (102400 bytes); the size column is KiB too

# Luma standard deviation, 0-1 scale. A frame of open sky over terrain
# measures ~0.10-0.25 here; a uniform fill measures ~0.00.
FLAT_STD = 0.02

# Fraction of pixels allowed at either extreme before the frame is called
# crushed or blown.
EXTREME_FRACTION = 0.90
BLACK_LEVEL = 0.02
WHITE_LEVEL = 0.98


def _stats(path):
    import numpy as np
    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        a = np.asarray(im).astype(np.float64) / 255.0
    # Rec.709 luma on sRGB-encoded values — display-referred by intent.
    luma = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    return {
        "w": w, "h": h,
        "mean": float(luma.mean()),
        "std": float(luma.std()),
        "p01": float(np.percentile(luma, 1)),
        "p50": float(np.percentile(luma, 50)),
        "p99": float(np.percentile(luma, 99)),
        "black_frac": float((luma <= BLACK_LEVEL).mean()),
        "white_frac": float((luma >= WHITE_LEVEL).mean()),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=landscape_spec.DEFAULT_RECIPE)
    ap.add_argument("--tag", default="",
                    help="Filename tag the run was captured with "
                         "(capture.py --filename-tag).")
    ap.add_argument("--expect", default="",
                    help="Comma-separated camera names that MUST be "
                         "present. Defaults to every camera in the "
                         "recipe's capture block, which is what makes a "
                         "silently-skipped camera a failure rather than "
                         "an absence nobody counted.")
    args = ap.parse_args(argv)

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    cap = recipe.get("capture") or {}
    out_dir = os.path.join(REPO_ROOT, cap.get("output_dir", "captures"))
    want_res = cap.get("resolution") or [None, None]
    if args.expect:
        expected = [s.strip() for s in args.expect.split(",") if s.strip()]
    else:
        expected = [c["name"] for c in cap.get("cameras", [])]
    if not expected:
        # NN13 / rule 13: a verdict over ZERO expected frames is exactly the
        # empty pass this tool exists to forbid (WHY-THIS-EXISTS above). Refuse
        # with the documented exit 2 ("nothing matched the selector") -- e.g. a
        # recipe with no capture.cameras, or an --expect that is empty/blank.
        print("REFUSE: nothing matched the selector -- 0 expected frames. The "
              "recipe declares no capture.cameras, or --expect was empty. An "
              "empty set is not a pass.")
        return 2

    suffix = ("_" + args.tag) if args.tag else ""
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("frames in : {0}".format(out_dir))
    print("tag       : {0!r}".format(args.tag or "(none)"))
    print("expecting : {0} camera(s)".format(len(expected)))
    print("")

    missing, trivial, ok = [], [], []
    print("{0:<13} {1:>9} {2:>10} {3:>6} {4:>6} {5:>6} {6:>6} {7:>6}  {8}"
          .format("camera", "KiB", "size", "mean", "std", "p01", "p99",
                  "blk%", "verdict"))
    for name in expected:
        pattern = os.path.join(
            out_dir, "*__{0}__*{1}.png".format(name, suffix))
        hits = sorted(glob.glob(pattern), key=os.path.getmtime)
        if not hits:
            print("{0:<13} {1:>9} {2:>10} {3:>6} {4:>6} {5:>6} {6:>6} "
                  "{7:>6}  MISSING".format(name, "-", "-", "-", "-", "-",
                                           "-", "-"))
            missing.append(name)
            continue
        path = hits[-1]
        size = os.path.getsize(path)
        try:
            st = _stats(path)
        except Exception as exc:                      # noqa: BLE001
            print("{0:<13} {1:>9.0f} {2:>10} unreadable: {3}: {4}".format(
                name, size / 1024.0, "-", type(exc).__name__, exc))
            trivial.append((name, "unreadable"))
            continue

        reasons = []
        if size < MIN_BYTES:
            reasons.append("TINY")
        if want_res[0] and (st["w"], st["h"]) != (want_res[0], want_res[1]):
            reasons.append("WRONG-SIZE")
        if st["std"] < FLAT_STD:
            reasons.append("FLAT")
        if st["black_frac"] >= EXTREME_FRACTION:
            reasons.append("CRUSHED")
        if st["white_frac"] >= EXTREME_FRACTION:
            reasons.append("BLOWN")

        verdict = "ok" if not reasons else "TRIVIAL: " + "+".join(reasons)
        print("{0:<13} {1:>9.0f} {2:>10} {3:>6.3f} {4:>6.3f} {5:>6.3f} "
              "{6:>6.3f} {7:>5.1f}  {8}".format(
                  name, size / 1024.0,
                  "{0}x{1}".format(st["w"], st["h"]),
                  st["mean"], st["std"], st["p01"], st["p99"],
                  100.0 * st["black_frac"], verdict))
        if reasons:
            trivial.append((name, "+".join(reasons)))
        else:
            ok.append(name)

    print("")
    print("=" * 72)
    print("  present and usable : {0} of {1}".format(len(ok), len(expected)))
    if missing:
        print("  MISSING            : {0}".format(", ".join(missing)))
    if trivial:
        print("  TRIVIAL            : {0}".format(
            ", ".join("{0} ({1})".format(n, r) for n, r in trivial)))
    print("=" * 72)

    if missing or trivial:
        print("")
        print("VERDICT: this run does NOT support a sweep verdict. A frame "
              "that is absent or empty is a FAILURE of the capture, never "
              "an empty pass — it would read as 'no defects found'.")
        return 3
    print("")
    if not args.tag:
        # FAIL CLOSED ON AN UNSCOPED RUN (2026-08-11).
        #
        # With no --tag the glob is `*__<camera>__*.png` — EVERY tag ever
        # captured — and the newest by mtime wins per camera. So a camera
        # that this run SKIPPED silently falls back to some previous
        # run's frame and reports `ok`. The check then prints "the
        # instrument produced evidence" about a set of frames that were
        # never all produced together.
        #
        # MEASURED, on this tool, the day it was written into a report:
        # the `5080hqfix` capture wrote 18 of 19 and exited 0; a bare
        # `verify_frames` said "19 of 19 present and usable"; the same
        # command with `--tag 5080hqfix` said "18 of 19, MISSING
        # ridge_wide" and returned 3. The capability was always correct.
        # The DEFAULT was the trap, and a permissive default on a gate is
        # a gate that answers a different question than the one asked.
        #
        # Refusing rather than warning, because the whole point of this
        # tool is that "no defects found" must never be printable over
        # evidence that does not exist (non-negotiable 1: unknown is
        # never yes).
        print("VERDICT WITHHELD: no --tag was given, so this checked the "
              "NEWEST frame per camera across EVERY tag, not one run.")
        print("")
        print("  A camera skipped by the run you care about falls back to "
              "an older frame here and reports 'ok'. That is how a "
              "18-of-19 capture reads as 19 of 19.")
        print("  Re-run with --tag <the capture's --filename-tag> to get "
              "a verdict that is about a single run.")
        return 4
    print("VERDICT: every expected frame is present and carries real "
          "tonal structure. The instrument produced evidence.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
