"""resize_gaea_build.py — 4096 Gaea export -> 4033 UE5 landscape size.

RESIZE, NEVER CROP. 4096 -> 4033 is a 1.56% shrink; cropping would throw
away a 63-pixel border of real terrain and, worse, would silently shift
every mask relative to the height it was simulated against. The masks and
the heightmap MUST stay in register — a flow line that no longer sits in
its valley is the failure this whole step exists to avoid.

WHY 4033. UE5 landscapes are (components x quads) + 1 vertices.
4033 = 63 x 64 + 1, i.e. 64 components of 63 quads, which is the
recommended layout for a landscape of this scale.

RESAMPLING, AND WHY THE TWO KINDS DIFFER
----------------------------------------
  masks   LANCZOS  — sharp, preserves thin drainage lines. Its ringing
                     lands on masks that get remapped downstream anyway.
  height  BICUBIC  — deliberately softer. Lanczos OVERSHOOTS at ridges,
                     and an overshoot in a heightmap is a spike or a
                     terrace, which is exactly the artefact the
                     post-import checklist looks for. A 1.56% resize does
                     not need the extra sharpness, and the downside is
                     asymmetric.

Both are done in FLOAT and clamped back into range, because the
overshoot is real and would otherwise wrap a uint16.

PRECISION. Pillow's `I;16` mode has partial resample support, so every
image is lifted to 32-bit float ('F') for the resize and quantised once
on the way out. Resizing in `I;16` directly is the kind of thing that
appears to work and quietly loses the low bits.

The 16-bit writer is `make_alpine_terrain.write_png16_grey`, IMPORTED and
not re-implemented (non-negotiable 4a).

WRITES OUTSIDE THE REPO. This tool writes into the Gaea package folder,
which is outside REPO_ROOT and UE_PROJECT_ROOT. That is a scoped
exception to standing rule 1, authorised by Ryan on 2026-08-09 for this
package. It is stated here so the exception is visible at the point of
use rather than remembered.

Exit codes:
  0  every declared file resized and re-verified
  2  bad arguments or missing build
  3  an import alias was not byte-identical to its canonical
  4  an output failed re-verification
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_alpine_terrain as mat   # noqa: E402  — the 16-bit writer
import verify_build                 # noqa: E402  — the declared SPEC

TARGET = 4033
OUT_DIR = "UE5_Ready"
ARCHIVE_DIR = "_archive"


def _resample(arr, size, how):
    """Resize a uint16 array in FLOAT and quantise once, clamped."""
    from PIL import Image
    src_lo, src_hi = float(arr.min()), float(arr.max())
    im = Image.fromarray(arr.astype(np.float32), mode="F")
    im = im.resize((size, size), how)
    out = np.asarray(im, dtype=np.float64)
    # Clamp to the SOURCE range, not to 0..65535. Ringing that overshoots
    # a mask whose real maximum is 512 would otherwise survive as a value
    # that never existed in the simulation.
    out = np.clip(out, src_lo, src_hi)
    return np.rint(out).astype(np.uint16), (src_lo, src_hi)


def main(argv=None):
    from PIL import Image
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", required=True)
    ap.add_argument("--size", type=int, default=TARGET)
    ap.add_argument("--archive-excluded", action="store_true",
                    help="move EXCLUDED files into _archive/")
    args = ap.parse_args(argv)

    build = args.build
    if not os.path.isdir(build):
        print("REFUSE: no such build folder: {0}".format(build))
        return 2
    out_dir = os.path.join(build, OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    print("build  : {0}".format(build))
    print("output : {0}".format(out_dir))
    # DERIVED, NOT TYPED. This read "(63 quads x 64 components + 1)"
    # unconditionally — true for the default 4033 and FALSE the first
    # time --size was used, where it printed "63 quads" over an 8129
    # target that is 127 quads. Prose that describes only the default is
    # a claim that silently stops being true the moment the parameter it
    # describes becomes a parameter.
    _q = (args.size - 1) // 64
    print("target : {0}x{0}  ({1} quads x 64 components + 1"
          "{2})".format(args.size, _q,
                        ", or {0} x 32 + 1".format((args.size - 1) // 32)
                        if (args.size - 1) % 32 == 0 else ""))
    print("")
    print("{0:<38s} {1:>10s} {2:>11s} {3:>11s}".format(
        "file", "resample", "src range", "out range"))

    bad = []
    for name, (role, _hard16, _note) in verify_build.SPEC.items():
        src = os.path.join(build, name)
        if not os.path.isfile(src):
            print("{0:<38s}  MISSING — refusing".format(name))
            return 2
        a = np.asarray(Image.open(src))
        if a.ndim == 3:
            a = a[..., 0]
        a = a.astype(np.uint16)

        is_height = "Height" in name
        how = Image.BICUBIC if is_height else Image.LANCZOS
        out, (lo, hi) = _resample(a, args.size, how)

        dst = os.path.join(out_dir, name)
        mat.write_png16_grey(dst, out)
        print("{0:<38s} {1:>10s} {2:>5.0f}-{3:<5.0f} {4:>5.0f}-{5:<5.0f}"
              .format(name, "BICUBIC" if is_height else "LANCZOS",
                      lo, hi, float(out.min()), float(out.max())))

        # RE-VERIFY THE ARTEFACT, not the intent.
        chk = np.asarray(Image.open(dst))
        if chk.ndim == 3:
            chk = chk[..., 0]
        w, h, depth, ctype = mat.read_png_header(dst)
        why = []
        if (w, h) != (args.size, args.size):
            why.append("size {0}x{1}".format(w, h))
        if depth != 16:
            why.append("bit depth {0}".format(depth))
        if ctype != 0:
            why.append("colour type {0} (not greyscale)".format(ctype))
        if float(chk.max()) > hi + 0.5 or float(chk.min()) < lo - 0.5:
            why.append("range escaped the source envelope")
        if why:
            bad.append((name, why))
            print("{0:<38s}   RE-VERIFY FAILED: {1}".format("", "; ".join(why)))

    if args.archive_excluded:
        arc = os.path.join(build, ARCHIVE_DIR)
        os.makedirs(arc, exist_ok=True)
        for name, why in verify_build.EXCLUDED.items():
            src = os.path.join(build, name)
            if os.path.isfile(src):
                shutil.move(src, os.path.join(arc, name))
                print("")
                print("ARCHIVED {0} -> {1}/".format(name, ARCHIVE_DIR))
                print("  {0}".format(why))

    print("")
    if bad:
        print("REFUSE: {0} output(s) failed re-verification:".format(len(bad)))
        for n, why in bad:
            print("  {0}: {1}".format(n, "; ".join(why)))
        return 4
    # THE IMPORT ALIAS TRAVELS WITH THE RESIZED PACKAGE.
    #
    # Without this, UE5_Ready holds the resized height under its CANONICAL
    # name only — and that name contains "v1", which
    # LandscapeTiledImage.cpp:14-24 pattern-matches as a TILED import. A
    # human importing from UE5_Ready gets the tiled prompt, and answering
    # YES creates no landscape at all. verify_build already reports the
    # alias as ABSENT, so the gap was visible; it just had to be closed by
    # hand every time, which is the shape that eventually gets forgotten
    # at 2 a.m.
    #
    # THE NAME COMES FROM verify_build.ALIASES, which is already imported
    # for the SPEC. One declaration, two consumers (NN24) — typing the
    # alias here would be a second place to update.
    print("")
    for alias, canonical in verify_build.ALIASES.items():
        src = os.path.join(out_dir, canonical)
        dst = os.path.join(out_dir, alias)
        if not os.path.exists(src):
            continue
        shutil.copyfile(src, dst)
        # Byte-identical is the contract, so assert it rather than trust
        # copyfile — the alias exists to be the SAME PIXELS under a name
        # the editor will not misread.
        with open(src, "rb") as a, open(dst, "rb") as b:
            if a.read() != b.read():
                print("REFUSE: alias {0} is not byte-identical to {1}"
                      .format(alias, canonical))
                return 3
        print("import alias : {0}  <- byte-identical copy of {1}"
              .format(alias, canonical))

    print("")
    print("ALL OUTPUTS WRITTEN AND RE-VERIFIED at {0}x{0}, 16-bit "
          "greyscale, no value outside its source envelope."
          .format(args.size))
    print("Originals untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
