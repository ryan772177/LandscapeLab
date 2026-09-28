"""verify_build.py — acceptance gate for a Gaea terrain export package.

OFFLINE. Reads a build folder, writes nothing, contacts no editor.

WHY THIS IS A GATE AND NOT A REPORT
-----------------------------------
Gaea builds land in incrementing folders (002, 003, ...) and every one of
them feeds a landscape import that is expensive to undo. A package that
is silently wrong — a mask that exported degenerate, a heightmap that is
8-bit, a file at the wrong resolution — produces a landscape that looks
plausible and is wrong, which this project has paid for before in other
forms. So this REFUSES rather than warns, and its exit code is meant to
be consumed.

THE EXPECTATIONS ARE DECLARED ONCE, HERE
----------------------------------------
`SPEC` below is the single declaration of what a build must contain and
what each file's value range should look like. Adding a channel means
editing SPEC, not editing three checks (non-negotiable 24).

Ranges are declared as OBSERVED-AT-INTAKE facts, not as physics. A mask
whose range is 0-512 is not "wrong" — it is sparse, and it needs a strong
remap downstream. The gate's job is to say what IS, loudly, and to refuse
only on things that cannot be true of a usable package.

DEGENERACY IS CHECKED EXPLICITLY, because it is the failure this exporter
actually has. Gaea 2.3 exports the Snow channel as a degenerate near-1-bit
PNG when the sim output is uniform: the file is present, correctly named,
correctly sized, and carries no information. Presence is not content, and
a channel with fewer than MIN_UNIQUE distinct values is reported as
DEGENERATE however healthy its header looks.

Exit codes:
  0  every declared file present and within its declared expectations
  2  the build folder is missing or unreadable
  3  a declared file is missing
  4  a hard expectation failed: bit depth, size, degeneracy, package
     dimension disagreement, or a failed registration control
  6  an import alias is missing its canonical source, or is not
     byte-identical to it
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

import numpy as np


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# A channel carrying fewer distinct values than this is not data.
MIN_UNIQUE = 16

# name -> (role, hard_16bit, expect_note)
# `role` is what the file is FOR. `expect_note` is the intake observation
# recorded at the time the build was accepted, so a later build that
# differs is visible rather than silently normalised away.
SPEC = {
    "AlpineLab_v1_Height_normalized.png": (
        "HEIGHT — the only heightmap to import",
        True,
        "normalized to the full 0-65535 range; pre-normalization Gaea "
        "output spanned 496-24763"),
    "Erosion2_Flow.png": (
        "flow / drainage mask", True,
        "full range, sparse — valid"),
    "Erosion2_Wear.png": (
        "wear mask", True,
        "low range (~0-6019) — valid, NEEDS REMAP"),
    "Erosion2_Deposits.png": (
        "deposits mask", True,
        "very low range (~0-512) — valid, NEEDS STRONG REMAP"),
    "Snow_Snow.png": (
        "hard snow coverage mask", True,
        "watch for Gaea 2.3 degenerate export when the sim is uniform"),
    "SnowMask_Out.png": (
        "graded snow depth mask", True,
        "autoleveled"),
}

# Present in the package and deliberately NOT imported.
EXCLUDED = {
    "Snow_Out.png": "un-normalized original height — superseded by "
                    "AlpineLab_v1_Height_normalized.png; do not import",
}

# alias -> canonical. A byte-identical copy under a name UE 5.8's
# landscape import dialog will not pattern-match as a tiled image.
#
# WHY THIS EXISTS. The dialog scans the BASE FILENAME for the tokens
# u, v, x, y each followed by an optional minus and digits
# (LandscapeTiledImage.cpp:14-24, regex `<token>(-?[0-9]+)`). The
# canonical name contains `v1`, so it matches, and the dialog offers
# *"Use 'AlpineLab_v<v>_Height_normalized.png' Tiled Image?"*. Answering
# YES is unrecoverable: only `<u>`/`<x>` can set the tile X coordinate
# (:86-104), a `v`-only name leaves X = -1, `if (X >= 0 && Y >= 0)`
# (:105) adds no tile, and Load returns "No files found" (:149-155).
# The dialog reports nothing useful and no landscape is created.
#
# The alias is the import target. The canonical name stays as the
# provenance record, which is why this is a COPY and not a rename.
ALIASES = {
    "AlpineLabHeight.png": "AlpineLab_v1_Height_normalized.png",
}

# The tokens above, as a regex. One declaration; `tiled_prompt_tokens`
# is the only reader (non-negotiable 24).
TILED_TOKEN_RE = re.compile(r"[uvxy]-?[0-9]+")


def tiled_prompt_tokens(filename):
    """Substrings in a filename that make UE 5.8 offer a tiled import.

    Ground truth: LandscapeTiledImage.cpp:14-24. The tokens are u, v, x
    and y, each followed by `(-?[0-9]+)`, matched ANYWHERE in the base
    filename — there is no underscore in the pattern. `AlpineLab_v1_...`
    matches on `v1`; `Terrain_x0_y0` matches twice; `AlpineLabHeight`
    matches nothing because it carries no digits at all.

    Returns the list of matches. Empty means the dialog will not prompt.
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    return TILED_TOKEN_RE.findall(base)


def measure(path):
    from PIL import Image
    im = Image.open(path)
    mode, size = im.mode, im.size
    a = np.asarray(im)
    if a.ndim == 3:
        a = a[..., 0]
    a = a.astype(np.float64)
    return {
        "mode": mode, "size": size,
        "min": float(a.min()), "max": float(a.max()),
        "mean": float(a.mean()),
        "unique": int(np.unique(a).size),
        "nonzero_frac": float((a > 0).mean()),
    }


def check_registration(build, top_frac=0.01):
    """Do the flow lines sit in valleys? Returns True/False/None.

    THE REGISTRATION TEST, AND WHY IT IS DONE HERE RATHER THAN IN THE
    EDITOR. The brief asked for a post-import helper that samples the
    flow mask's brightest pixels and reports the landscape height
    percentile there. That is the right question, but the editor is the
    wrong place to ask it: both rasters are already on disk in the same
    texel space, so the check needs no landscape, no import, and no UE
    API at all — and running it BEFORE the import catches a
    misregistered package instead of diagnosing one afterwards.

    Water runs downhill. So the brightest flow texels must land in LOW
    height percentiles. If height and masks fell out of register — the
    exact failure R1's REJECTED entry warns about — flow lands at
    arbitrary percentiles and this collapses toward 50.

    THE RANDOM CONTROL IS THE POINT. A flow median of 35 means nothing
    on its own; it means something against a uniform sample of the same
    heightmap, which must sit near 50. Without the control this reports
    a number that cannot fail.

    Returns None when the inputs are not both present — "I could not
    look" is not a pass.
    """
    hname = next((n for n in SPEC if "Height" in n), None)
    fname = next((n for n in SPEC if "Flow" in n), None)
    if not hname or not fname:
        return None
    hp = os.path.join(build, hname)
    fp = os.path.join(build, fname)
    if not (os.path.isfile(hp) and os.path.isfile(fp)):
        return None

    from PIL import Image
    H = np.asarray(Image.open(hp)).astype(np.float64)
    F = np.asarray(Image.open(fp)).astype(np.float64)
    if H.ndim == 3:
        H = H[..., 0]
    if F.ndim == 3:
        F = F[..., 0]
    if H.shape != F.shape:
        print("")
        print("REGISTRATION: cannot test — height {0} vs flow {1}"
              .format(H.shape, F.shape))
        return None

    # Percentile rank of every height value, computed once.
    order = H.ravel().argsort()
    ranks = np.empty(order.size, dtype=np.float64)
    ranks[order] = np.arange(order.size)
    ranks = (ranks / max(order.size - 1, 1) * 100.0).reshape(H.shape)

    flat = F.ravel()
    k = max(int(flat.size * top_frac), 1000)
    idx = np.argpartition(flat, -k)[-k:]
    flow_pct = ranks.ravel()[idx]

    rng = np.random.default_rng(20260809)
    ctrl = ranks.ravel()[rng.integers(0, ranks.size, size=k)]

    fm, cm = float(np.median(flow_pct)), float(np.median(ctrl))
    print("")
    print("REGISTRATION — height percentile at the brightest {0:.0%} of "
          "flow ({1:,} texels)".format(top_frac, k))
    print("  flow    median {0:5.1f}   p25 {1:5.1f}   p75 {2:5.1f}"
          .format(fm, float(np.percentile(flow_pct, 25)),
                  float(np.percentile(flow_pct, 75))))
    print("  RANDOM  median {0:5.1f}   <- the control; must sit near 50"
          .format(cm))
    print("  separation {0:+.1f} percentile points".format(fm - cm))

    if abs(cm - 50.0) > 5.0:
        print("  CONTROL IS OFF — the ranking itself is suspect, so the "
              "flow figure cannot be trusted either.")
        return False
    if fm < cm - 5.0:
        print("  PASS: flow sits BELOW the terrain median — drainage is "
              "in the low ground, so height and masks are in register.")
        return True
    print("  FAIL: flow does NOT sit in low ground. Height and masks are "
          "very likely out of register — do NOT import this package.")
    return False


def newest_build(root):
    """Highest-numbered build folder under `root`, or None."""
    if not os.path.isdir(root):
        return None
    nums = [d for d in os.listdir(root)
            if re.fullmatch(r"\d+", d)
            and os.path.isdir(os.path.join(root, d))]
    if not nums:
        return None
    return os.path.join(root, max(nums, key=lambda d: int(d)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", default=None,
                    help="build folder, e.g. .../AlpineLab_v1/002")
    ap.add_argument("--root", default=None,
                    help="parent holding numbered builds; the HIGHEST is "
                         "used when --build is not given")
    ap.add_argument("--expect-size", default="4096x4096")
    args = ap.parse_args(argv)

    build = args.build or newest_build(args.root or "")
    if not build or not os.path.isdir(build):
        print("REFUSE: no build folder. Pass --build or a --root that "
              "contains numbered folders.")
        return 2
    try:
        w, h = [int(v) for v in args.expect_size.lower().split("x")]
    except ValueError:
        print("REFUSE: --expect-size must be WxH")
        return 2
    want = (w, h)

    print("build : {0}".format(build))
    print("expect: {0}x{1}, 16-bit single channel".format(w, h))
    print("")

    hard_fail, missing = [], []
    print("{0:<38s} {1:>7s} {2:>9s} {3:>7s} {4:>9s} {5:>8s}  {6}".format(
        "file", "mode", "size", "min", "max", "unique", "verdict"))

    for name, (role, hard16, note) in SPEC.items():
        path = os.path.join(build, name)
        if not os.path.isfile(path):
            missing.append(name)
            print("{0:<38s}  MISSING".format(name))
            continue
        m = measure(path)
        bad = []
        # Pillow reports 16-bit greyscale as I;16 / I;16B / I. Anything
        # in L or P is 8-bit and cannot carry a heightmap.
        is16 = m["mode"].startswith("I")
        if hard16 and not is16:
            bad.append("NOT 16-BIT (mode {0})".format(m["mode"]))
        if m["size"] != want:
            bad.append("SIZE {0}x{1}".format(*m["size"]))
        if m["unique"] < MIN_UNIQUE:
            bad.append("DEGENERATE ({0} unique values)".format(m["unique"]))
        verdict = "ok" if not bad else " + ".join(bad)
        if bad:
            hard_fail.append((name, bad))
        print("{0:<38s} {1:>7s} {2:>4d}x{3:<4d} {4:>7.0f} {5:>9.0f} "
              "{6:>8d}  {7}".format(
                  name, m["mode"], m["size"][0], m["size"][1],
                  m["min"], m["max"], m["unique"], verdict))
        print("{0:<38s}   mean {1:.1f}   nonzero {2:.1%}   {3}".format(
            "", m["mean"], m["nonzero_frac"], note))

    for name, why in EXCLUDED.items():
        path = os.path.join(build, name)
        if os.path.isfile(path):
            print("")
            print("{0:<38s}  PRESENT AND EXCLUDED".format(name))
            print("{0:<38s}   {1}".format("", why))

    # -----------------------------------------------------------------
    # THE IMPORT ALIAS — the file the EDITOR actually opens
    # -----------------------------------------------------------------
    # An undeclared file in the package is an inert field wearing a
    # different hat (non-negotiable 21): it reads like data and nothing
    # checks it. The alias is the file a human hands to the landscape
    # dialog, so it is the LEAST acceptable thing to leave unverified.
    print("")
    for alias, canonical in ALIASES.items():
        apath = os.path.join(build, alias)
        cpath = os.path.join(build, canonical)
        if not os.path.isfile(apath):
            print("{0:<38s}  ABSENT — the manual editor import needs one; "
                  "see docs/archive/pre8k/IMPORT_CHECKLIST.md "
                  "(ARCHIVED)".format(alias))
            continue
        if not os.path.isfile(cpath):
            print("REFUSE: {0} is present but its canonical source {1} is "
                  "not. An alias with nothing to be an alias OF is just an "
                  "unverified heightmap.".format(alias, canonical))
            return 6
        a, c = _sha256(apath), _sha256(cpath)
        if a != c:
            print("REFUSE: {0} is NOT byte-identical to {1}."
                  .format(alias, canonical))
            print("  alias     {0}".format(a))
            print("  canonical {1}".format("", c))
            return 6
        print("{0:<38s}  byte-identical to {1}".format(alias, canonical))
        print("{0:<38s}   sha256 {1}".format("", a))

    # Filename safety, for every file a human might hand to the dialog.
    tripping = {}
    for name in list(SPEC) + list(ALIASES):
        if os.path.isfile(os.path.join(build, name)):
            hits = tiled_prompt_tokens(name)
            if hits:
                tripping[name] = hits
    if tripping:
        print("")
        print("TILED-IMPORT PROMPT will fire for these filenames "
              "(LandscapeTiledImage.cpp:14-24):")
        for name, hits in sorted(tripping.items()):
            print("  {0:<38s} matches {1}".format(name, ", ".join(hits)))
        print("  Import via an alias above, or answer NO to the prompt. "
              "Answering YES creates no landscape — see R-GAEA.")

    # -----------------------------------------------------------------
    # WHOLE-PACKAGE DIMENSION AGREEMENT (R-GAEA section 7, 2026-08-09)
    # -----------------------------------------------------------------
    # R1's REJECTED entry was narrowed on 2026-08-09 from "CROP, NEVER
    # RESAMPLE" to "never resample height and masks independently or with
    # differing filters". That narrowing is only safe if something
    # ENFORCES the whole-package part, otherwise it is a licence to do
    # the dangerous thing carefully. This is that enforcement.
    #
    # A height and a mask at different resolutions cannot be in register
    # no matter how good the filter was, and the resulting landscape
    # looks plausible: flow simply sits in the wrong places.
    sizes = {}
    for name in SPEC:
        p = os.path.join(build, name)
        if os.path.isfile(p):
            sizes.setdefault(measure(p)["size"], []).append(name)
    print("")
    if len(sizes) > 1:
        print("REFUSE: the package is NOT dimensionally uniform. Height "
              "and masks must share one resolution or they cannot be in "
              "register:")
        for sz, names in sorted(sizes.items()):
            print("  {0}x{1}: {2}".format(sz[0], sz[1], ", ".join(names)))
        return 4
    if sizes:
        only = list(sizes)[0]
        n_measured = sum(len(v) for v in sizes.values())
        print("dimension agreement: all {0} present file(s) at {1}x{2}".format(
            n_measured, only[0], only[1]))

    print("")
    if missing:
        print("REFUSE: {0} declared file(s) missing: {1}"
              .format(len(missing), ", ".join(missing)))
        return 3
    if hard_fail:
        print("REFUSE: {0} file(s) failed a hard expectation:"
              .format(len(hard_fail)))
        for n, why in hard_fail:
            print("  {0}: {1}".format(n, "; ".join(why)))
        print("")
        print("A package that is silently wrong produces a landscape that "
              "looks plausible and is wrong. Fix the export, do not "
              "import around this.")
        return 4

    reg = check_registration(build)
    if reg is False:
        return 4
    if reg is None:
        # the control did not run (no Height/Flow in SPEC, or a shape it
        # could not compare). "I could not look" is not a silent pass
        # (check_registration docstring, NN6): surface it, don't bury it
        # in the ACCEPTED line.
        print("")
        print("NOTE: the registration control did NOT run (height/flow not "
              "both available) — ACCEPTED below is NOT registration-verified.")

    print("ACCEPTED: {0} declared file(s), all 16-bit {1}x{2}, none "
          "degenerate.".format(len(SPEC), w, h))
    print("Range notes above are INTAKE OBSERVATIONS, not physics — the "
          "low-range masks are valid and need remapping downstream.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
