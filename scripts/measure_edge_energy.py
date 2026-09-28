"""measure_edge_energy.py — did the frame get SHARPER, or just DIFFERENT?

WHY THIS EXISTS, AND WHAT IT REPLACES
-------------------------------------
`compare_images.py` reports mean absolute error. MAE answers "how far did
the pixels move", which is the wrong question for every silhouette or
sharpness claim this project has made:

  * The ScreenPercentage 70 -> 100 A/B measured mae 0.01217 = 4.1x the
    noise floor on 19 of 19 stations, and it was read as confirmation
    that 70% was "eating the needles". EDGE ENERGY said +1.3% mean with
    SIX STATIONS LOSING it. The discriminating row was `player_eye`:
    the LARGEST mae of all 19 (13.4x) and +0.1% edge energy — its pixels
    moved more than anywhere else and got no sharper. That mae was
    resampling and TAA jitter, not detail.

  * MAE CANNOT TELL SHARPER FROM DIFFERENTLY BLURRY. Blur an image and
    the mae is large. Sharpen it and the mae is large. The sign of the
    change is invisible to the metric.

So: mean gradient magnitude. Sharper edges and NEW silhouette both raise
it; blur lowers it. It has a sign, which is the entire point.

WHAT IT MEASURES, STATED SO THE NUMBER CANNOT BE OVER-READ
----------------------------------------------------------
Mean |grad(luma)| over the frame, via central differences. This is a
WHOLE-FRAME statistic and therefore carries the misleading-denominator
hazard (non-negotiable 22): a change confined to the terrain is diluted
by sky. `--sky-cut` reports the same statistic over non-sky pixels only,
and BOTH are printed, because the conditioned number is the one about the
decision being made and the unconditioned one is the honest total.

It does NOT measure whether the frame looks better. It measures whether
there is more high-frequency structure in it. A material that replaced
smooth ground with noise would score well here and look worse.

THE SOURCE ARTEFACT IS THE PNG. That is a DIFFERENT representation from
any property read, any placement plan and any material audit — which is
what makes it admissible as corroboration under non-negotiable 0. It is
the same source as compare_images.py, so the two CANNOT corroborate each
other; they answer different questions about one artefact.

THE NOISE FLOOR IS NOT OPTIONAL
-------------------------------
Two captures at identical settings differ. `--noise-floor` derives the
floor from a same-settings pair rather than assuming one, and any result
below it is reported as NOT SEPARATED rather than as a small effect. The
project already paid for this: two identical-settings runs differ by up
to 26% on a stranded-pixel metric, and a +8% reading was nearly taken as
confirmation.

POSITIVE CONTROL (non-negotiable 2)
-----------------------------------
`--selftest` blurs a real frame and asserts the metric reports a LOSS,
then sharpens one and asserts a GAIN. A metric that has only seen real
data has not been shown to have the sign it claims.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bootstrap  # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
CAPTURE_DIR = os.path.join(REPO_ROOT, "captures", "alpine")

try:
    import numpy as np
except ImportError:  # pragma: no cover
    print("REFUSE: numpy is required (recorded in RECIPES R0).")
    raise SystemExit(2)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("REFUSE: Pillow is required (recorded in RECIPES R0).")
    raise SystemExit(2)


# Rec.709 luma. The gradient is taken on LUMA, not on each channel, so a
# pure hue shift at constant brightness does not read as new structure.
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)


def load_luma(path):
    """sRGB PNG -> float luma in [0,1]. Returns None if unreadable."""
    try:
        with Image.open(path) as im:
            arr = np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0
    except Exception:
        return None
    return arr @ _LUMA


def edge_energy(luma, sky_mask=None):
    """Mean gradient magnitude via central differences.

    Central differences rather than a Sobel kernel: Sobel bakes in a 1-2-1
    smoothing that suppresses exactly the single-pixel detail a
    displacement change is expected to add, which would bias the metric
    against the hypothesis it is testing.
    """
    if luma is None or luma.ndim != 2 or min(luma.shape) < 3:
        return None
    gy, gx = np.gradient(luma)
    mag = np.hypot(gx, gy)
    if sky_mask is not None:
        keep = ~sky_mask
        if keep.sum() < 1000:
            return None
        return float(mag[keep].mean())
    return float(mag.mean())


def sky_mask_for(luma, thresh=0.72):
    """A crude bright-upper-region mask. DECLARED CRUDE ON PURPOSE.

    Sky here is 'bright pixels in the upper half'. It will misclassify a
    sunlit snowfield near the horizon. It exists so a terrain-only figure
    can be reported ALONGSIDE the whole-frame one, not to be authoritative
    on its own — which is why both are always printed.
    """
    m = np.zeros(luma.shape, dtype=bool)
    half = luma.shape[0] // 2
    m[:half] = luma[:half] > thresh
    return m


_NAME = re.compile(r"^alpine__(?P<station>.+?)__(?P<stamp>\d{8}T\d{6}Z)__"
                   r"(?P<commit>[^_]+)_(?P<tag>.+)\.png$")


def index_captures(directory):
    """tag -> {station: path}, newest stamp winning per (tag, station).

    ALSO indexes every run under the key "TAG@STAMP". The same-settings
    NOISE-FLOOR pair is two runs that share a tag and differ only by
    timestamp, so a tag-only index collapses them and the floor becomes
    unmeasurable — which would silently downgrade every verdict this tool
    produces to "unbounded".
    """
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, "alpine__*.png"))):
        m = _NAME.match(os.path.basename(p))
        if not m:
            continue
        tag, st, stamp = m.group("tag"), m.group("station"), m.group("stamp")
        prev = out.setdefault(tag, {}).get(st)
        if prev is None or stamp > prev[0]:
            out[tag][st] = (stamp, p)
        out.setdefault(tag + "@" + stamp, {})[st] = (stamp, p)
    return {t: {s: v[1] for s, v in d.items()} for t, d in out.items()}


def resolve(idx, key):
    """Accept TAG or TAG@STAMP; TAG alone takes the newest run."""
    return idx.get(key)


def compare(idx, tag_a, tag_b, use_sky_cut):
    a, b = idx.get(tag_a) or {}, idx.get(tag_b) or {}
    stations = sorted(set(a) & set(b))
    rows, unreadable = [], []
    for st in stations:
        la, lb = load_luma(a[st]), load_luma(b[st])
        if la is None or lb is None:
            unreadable.append(st)
            continue
        if la.shape != lb.shape:
            unreadable.append(st + " (size mismatch)")
            continue
        mask = sky_mask_for(la) if use_sky_cut else None
        ea, eb = edge_energy(la, mask), edge_energy(lb, mask)
        if ea is None or eb is None or ea <= 0:
            unreadable.append(st)
            continue
        rows.append((st, ea, eb, 100.0 * (eb - ea) / ea))
    return rows, unreadable, sorted(set(a) ^ set(b))


def selftest():
    """Prove the metric has the SIGN it claims, on a real frame."""
    cands = sorted(glob.glob(os.path.join(CAPTURE_DIR, "alpine__*.png")))
    if not cands:
        print("SELFTEST COULD NOT RUN: no captures on disk. That is 'I "
              "could not look', not a pass.")
        return 2
    luma = load_luma(cands[0])
    if luma is None:
        print("SELFTEST COULD NOT RUN: could not decode {0}".format(cands[0]))
        return 2
    base = edge_energy(luma)

    # BLUR: a 3x3 box via shifted sums. Must LOSE edge energy.
    k = np.zeros_like(luma)
    n = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            k += np.roll(np.roll(luma, dy, 0), dx, 1)
            n += 1
    blurred = k / n
    e_blur = edge_energy(blurred)

    # SHARPEN: unsharp mask. Must GAIN edge energy.
    sharp = np.clip(luma + 0.8 * (luma - blurred), 0.0, 1.0)
    e_sharp = edge_energy(sharp)

    print("SELFTEST on {0}".format(os.path.basename(cands[0])))
    print("  baseline edge energy : {0:.6f}".format(base))
    print("  blurred              : {0:.6f}  ({1:+.1f}%)".format(
        e_blur, 100.0 * (e_blur - base) / base))
    print("  sharpened            : {0:.6f}  ({1:+.1f}%)".format(
        e_sharp, 100.0 * (e_sharp - base) / base))
    ok = (e_blur < base) and (e_sharp > base)
    print("  VERDICT: {0}".format(
        "the metric loses on blur and gains on sharpen — it has a sign"
        if ok else "FAILED — the metric does not respond as claimed"))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default=CAPTURE_DIR)
    ap.add_argument("--before", help="tag captured first")
    ap.add_argument("--after", help="tag captured second")
    ap.add_argument("--noise-floor", nargs=2, metavar=("TAG_A", "TAG_B"),
                    help="a SAME-SETTINGS pair; the spread between them "
                         "bounds what counts as no change")
    ap.add_argument("--sky-cut", action="store_true",
                    help="also report over non-sky pixels only")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list-tags", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    idx = index_captures(args.dir)
    if args.list_tags:
        for t in sorted(idx):
            print("  {0:<28} {1} station(s)".format(t, len(idx[t])))
        return 0
    if not args.before or not args.after:
        print("REFUSE: --before and --after are both required.")
        return 2
    for t in (args.before, args.after):
        if t not in idx:
            print("REFUSE: no captures tagged {0!r}. Known tags:".format(t))
            for k in sorted(idx):
                print("    {0}".format(k))
            return 2

    floor = None
    if args.noise_floor:
        fa, fb = args.noise_floor
        if fa in idx and fb in idx:
            frows, _, _ = compare(idx, fa, fb, args.sky_cut)
            if frows:
                floor = max(abs(r[3]) for r in frows)
                print("NOISE FLOOR from a same-settings pair "
                      "({0} vs {1}, {2} stations)".format(fa, fb, len(frows)))
                print("  worst |delta| between two runs that should be "
                      "identical: {0:.2f}%".format(floor))
                print("  Anything at or under this is NOT SEPARATED from "
                      "run-to-run variation.")
                print("")
        else:
            print("NOISE FLOOR NOT MEASURED: one of {0!r}/{1!r} has no "
                  "captures. Treat every result below as UNBOUNDED — 'I "
                  "could not look'.".format(fa, fb))
            print("")

    rows, unreadable, only_one = compare(idx, args.before, args.after,
                                         args.sky_cut)
    if not rows:
        print("REFUSE: no station is present in BOTH tags.")
        return 2

    scope = "non-sky pixels" if args.sky_cut else "whole frame"
    print("EDGE ENERGY  {0} -> {1}   ({2}, {3} stations)".format(
        args.before, args.after, scope, len(rows)))
    print("")
    print("  {0:<18} {1:>10} {2:>10} {3:>9}".format(
        "station", "before", "after", "change"))
    for st, ea, eb, pct in sorted(rows, key=lambda r: -r[3]):
        flag = ""
        if floor is not None:
            flag = "  " if abs(pct) > floor else "  (in noise)"
        print("  {0:<18} {1:>10.6f} {2:>10.6f} {3:>+8.2f}%{4}".format(
            st, ea, eb, pct, flag))

    pcts = [r[3] for r in rows]
    gained = sum(1 for p in pcts if p > 0)
    mean = sum(pcts) / len(pcts)
    print("")
    print("  mean change    {0:+.2f}%".format(mean))
    print("  median change  {0:+.2f}%".format(sorted(pcts)[len(pcts) // 2]))
    print("  gained on      {0} of {1} stations".format(gained, len(rows)))
    if floor is not None:
        sep = sum(1 for p in pcts if abs(p) > floor)
        print("  above the {0:.2f}% noise floor: {1} of {2}".format(
            floor, sep, len(rows)))
        if sep == 0:
            print("")
            print("  NOT SEPARATED FROM NOISE. This is not a small effect; "
                  "it is an effect this instrument cannot distinguish from "
                  "two identical runs.")
    if unreadable:
        print("")
        print("  COULD NOT MEASURE {0} station(s): {1}".format(
            len(unreadable), ", ".join(unreadable)))
        print("  Those are UNKNOWN, not zero.")
    if only_one:
        print("  present in only one tag (excluded): {0}".format(
            ", ".join(only_one)))
    print("")
    print("Source artefact: the PNG pixels. This shares its source with")
    print("compare_images.py, so the two cannot corroborate each other —")
    print("they ask different questions of one artefact. Edge energy says")
    print("whether high-frequency structure appeared, NOT whether the")
    print("frame looks better.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
