"""check_scene_animation.py — does anything in this frame MOVE by itself?

WHY THIS IS A TOOL AND NOT AN AD-HOC DIFF
-----------------------------------------
This project's entire method is single-variable frame A/B against a noise
floor measured in the third decimal place. That method assumes a static
scene re-renders identically. **Animated foliage breaks that assumption
silently**: nothing errors, the floor just rises, and every subsequent
"the change is 4x the noise floor" conclusion is quietly wrong.

Measured 2026-08-15 on `PN_interactiveSpruceForest`: the canopy animates
with no Blueprint present, driven from engine Time by the material alone.
The same question has never been asked of the 153,796 trees standing in
`/Game/Alpine8K`.

THE STATISTIC THAT ANSWERS IT IS NOT THE MEAN
---------------------------------------------
Whole-frame mae on the PN test read 0.005275 — only 1.4-2.1x the floor,
comfortably dismissible. The motion was real and large; it occupied 4.4% of
the frame at up to 0.73 per pixel, and averaging it over the other 95.6%
hid it (measured, _verify/20260815_alpine8k_animation_check.md:118).
**Whole-frame mae is a layer-scoped statistic whenever the subject does not
fill the frame** (non-negotiable 22).

So this tool reports, and refuses to collapse:
  - per-pair mae, AND the fraction of pixels that moved appreciably, AND
    the maximum local change;
  - the same three per horizontal BAND, because sky and flat ground are
    regions that cannot move and are therefore built-in controls;
  - a diff image, because "solid filled silhouette" vs "sparse speckle on
    edges" distinguishes bulk motion from temporal sampling noise and no
    scalar does.

WHAT IT DOES NOT DO
-------------------
It cannot separate a SMALL residual motion from TAA/temporal speckle. It
says so in its own verdict rather than implying a cleanliness it did not
establish. A verdict of MOVING is strong; a verdict of STATIC means "below
the floor and without the spatial signature of motion", which is evidence,
not proof.

The camera is NOT parked by this tool. Park it first with
`park_viewport.py` — one job per tool, and parking already prints the
calibration class that travels with any number read afterwards.

Exit codes:
  0  STATIC — below the declared floor, no motion signature
  2  bad arguments, or a missing dependency (numpy/Pillow)
  4  MOVING — the scene animates between frames
  5  could not look — a frame was not captured, OR the captured frames differ
     in size and cannot be compared
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
SHOT_DIR = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Screenshots",
                        "WindowsEditor")

# The floor this project derived on BARE TERRAIN, before it had any animated
# foliage. Quoted as the default and labelled, because using it against a
# vegetation-filled frame without re-deriving it is a calibration-class
# error of the kind R13 already names for GPU figures.
DEFAULT_FLOOR = 0.00298


def _shot(resolution, wait, timeout):
    """One highres_shot, returning the path it wrote."""
    before = set(glob.glob(os.path.join(SHOT_DIR, "*.png")))
    cmd = [sys.executable,
           os.path.join(REPO_ROOT, "scripts", "highres_shot.py"),
           "--resolution", resolution, "--wait", str(wait),
           "--timeout", str(timeout)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    after = set(glob.glob(os.path.join(SHOT_DIR, "*.png")))
    new = sorted(after - before)
    # Gate on the child's exit code too, not only on a PNG appearing: a failed
    # highres_shot that leaves a partial write (or another writer to the shared
    # screenshot dir) would otherwise be accepted as a valid frame.
    if r.returncode != 0 or not new:
        return None, (r.stdout or "") + (r.stderr or "")
    return new[-1], None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", type=int, default=3,
                    help="How many frames to take (minimum 2).")
    ap.add_argument("--gap-s", type=float, default=5.0,
                    help="Seconds between frames. Wind cycles are seconds, "
                         "so a sub-second gap can sample the same phase and "
                         "read as static.")
    ap.add_argument("--resolution", default="1280x720")
    ap.add_argument("--floor", type=float, default=DEFAULT_FLOOR,
                    help="Noise floor to judge against. The default was "
                         "derived on BARE TERRAIN.")
    ap.add_argument("--label", default="scene")
    ap.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "_verify"))
    ap.add_argument("--wait", type=int, default=90)
    ap.add_argument("--timeout", type=int, default=200)
    args = ap.parse_args(argv)

    if args.frames < 2:
        print("REFUSE: --frames must be at least 2.")
        return 2

    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        print("REFUSE: needs numpy and Pillow ({0}).".format(exc))
        return 2

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("frames    : {0}, {1:.1f} s apart, {2}".format(
        args.frames, args.gap_s, args.resolution))
    print("floor     : {0:.5f}{1}".format(
        args.floor,
        "  (project default — derived on BARE TERRAIN)"
        if abs(args.floor - DEFAULT_FLOOR) < 1e-12 else "  (declared)"))
    print("")
    print("NOTHING ELSE MAY TOUCH THE EDITOR WHILE THIS RUNS — one command "
          "connection per node, and the second client wins silently.")
    print("")

    paths = []
    for i in range(args.frames):
        p, err = _shot(args.resolution, args.wait, args.timeout)
        if p is None:
            print("  frame {0}: NO FILE WRITTEN".format(i + 1))
            print(err[-800:] if err else "(no output)")
            print("")
            print("REFUSE: could not look. A missing frame is not a static "
                  "scene.")
            return 5
        paths.append(p)
        print("  frame {0}: {1}".format(i + 1, os.path.basename(p)))
        if i < args.frames - 1:
            time.sleep(args.gap_s)

    # (A prior exit-3 "fewer than 2 usable frames" guard here was dead: the loop
    # already returns 5 on the FIRST missing frame and --frames is >= 2, so
    # paths always holds args.frames entries by this point.)

    ims = []
    for p in paths:
        ims.append(np.asarray(Image.open(p).convert("RGB"),
                              dtype=np.float64) / 255.0)
    if len({im.shape for im in ims}) != 1:
        print("REFUSE: frames differ in size; they are not comparable.")
        return 5

    print("")
    print("PAIRWISE")
    maes, pcts, mx = [], [], []
    for i in range(len(ims)):
        for j in range(i + 1, len(ims)):
            d = np.abs(ims[i] - ims[j])
            mae = float(d.mean())
            pct = float((d.max(axis=2) > 0.02).mean() * 100.0)
            m = float(d.max())
            maes.append(mae)
            pcts.append(pct)
            mx.append(m)
            print("  {0} vs {1}   mae {2:.6f}  = {3:5.2f}x floor   "
                  "px>2% {4:5.2f}%   max {5:.4f}".format(
                      i + 1, j + 1, mae, mae / args.floor, pct, m))
    mean_mae = float(np.mean(maes))
    mean_pct = float(np.mean(pcts))
    peak = float(np.max(mx))
    print("  MEAN      mae {0:.6f}  = {1:.2f}x floor   px>2% {2:.2f}%   "
          "peak {3:.4f}".format(mean_mae, mean_mae / args.floor, mean_pct,
                                peak))

    # BANDS. Sky and flat ground are regions that physically cannot move, so
    # they are controls that came free with the framing.
    d0 = np.abs(ims[0] - ims[1]).max(axis=2)
    H = d0.shape[0]
    print("")
    print("BY HORIZONTAL BAND (frames 1 vs 2) — the denominator, stated")
    bands = [("top quarter", 0, H // 4), ("upper middle", H // 4, H // 2),
             ("lower middle", H // 2, 3 * H // 4),
             ("bottom quarter", 3 * H // 4, H)]
    band_pct = {}
    for name, lo, hi in bands:
        b = d0[lo:hi]
        band_pct[name] = float((b > 0.02).mean() * 100.0)
        print("  {0:<16} mean {1:.6f}   px>2% {2:5.2f}%".format(
            name, float(b.mean()), band_pct[name]))

    os.makedirs(args.out_dir, exist_ok=True)
    diff_png = os.path.join(
        args.out_dir, "{0}_animation_diff.png".format(args.label))
    Image.fromarray((np.clip(d0 * 6.0, 0, 1) * 255).astype("uint8")).save(
        diff_png)

    # VERDICT. Two independent conditions, and the concentration test is
    # the one that catches what the mean hides.
    over_floor = mean_mae > args.floor
    concentrated = peak > 0.15 and mean_pct > 1.0
    print("")
    if over_floor or concentrated:
        print("VERDICT: MOVING.")
        if over_floor:
            print("  whole-frame mae {0:.6f} is above the {1:.5f} floor"
                  .format(mean_mae, args.floor))
        if concentrated:
            print("  and/or the change is CONCENTRATED — peak {0:.4f} over "
                  "{1:.2f}% of pixels. A mean can hide this; the PN spruce "
                  "read 2.05x the floor while moving 0.73 on 4.4% of the "
                  "frame.".format(peak, mean_pct))
        rc = 4
    else:
        print("VERDICT: STATIC — below the floor and without the spatial "
              "signature of motion.")
        print("  This is EVIDENCE, not proof. It cannot separate a small "
              "residual motion from temporal sampling noise.")
        rc = 0

    print("")
    print("OPEN {0} BEFORE BELIEVING EITHER VERDICT.".format(
        os.path.relpath(diff_png, REPO_ROOT)))
    print("  a SOLID FILLED silhouette  -> bulk motion")
    print("  SPARSE SPECKLE on edges    -> temporal sampling noise")
    print("  No scalar distinguishes those two, which is why the image is "
          "written rather than summarised.")

    report = {
        "label": args.label, "frames": [os.path.basename(p) for p in paths],
        "gap_s": args.gap_s, "floor": args.floor,
        "mean_mae": mean_mae, "mean_pct_moved": mean_pct, "peak": peak,
        "band_pct_moved": band_pct, "verdict": "MOVING" if rc else "STATIC",
        "diff_image": os.path.relpath(diff_png, REPO_ROOT),
    }
    rp = os.path.join(args.out_dir,
                      "{0}_animation.json".format(args.label))
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    print("")
    print("wrote {0}".format(os.path.relpath(rp, REPO_ROOT)))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
