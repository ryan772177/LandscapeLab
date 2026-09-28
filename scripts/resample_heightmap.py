"""resample_heightmap.py — resample ONE 16-bit heightmap to a new square size.

LOCAL ONLY. No editor contact. Writes exactly one file, inside `terrain/`,
and refuses any output path outside it.

=====================================================================
WHY THIS EXISTS, AND WHY IT REIMPLEMENTS NOTHING
=====================================================================
`resize_gaea_build.py` already resamples heightmaps correctly, but it is
PACKAGE-oriented: it walks a Gaea build directory, enforces whole-package
dimension agreement, and archives what it excludes. Compositing the alpine
terrain at a higher resolution needs the same arithmetic applied to a SINGLE
base heightmap that was never part of a Gaea build.

So the arithmetic is IMPORTED, not copied (non-negotiable 4a — a trap class
that reaches two tools becomes shared infrastructure, and individually-patched
copies are themselves a REJECTED pattern):

    resize_gaea_build._resample          the float-lift + clamp + quantise
    make_alpine_terrain.write_png16_grey the 16-bit PNG writer

Three traps live inside those two functions and none of them is re-derived here:
Pillow's `I;16` mode has only partial resample support and resizing in it
silently loses the low bits, so the array is lifted to float32 first; ringing is
clamped to the SOURCE range rather than 0..65535, so an overshoot cannot invent
a value the terrain never had; and quantisation happens exactly once.

=====================================================================
BICUBIC FOR HEIGHT — A RULING, NOT A DEFAULT
=====================================================================
`resize_gaea_build.py` chose BICUBIC for height and LANCZOS for masks, and its
reasoning is quoted here because it decides the artefact:

    "Lanczos OVERSHOOTS at ridges, and an overshoot in a heightmap is a spike
     or a terrace, which is exactly the artefact the post-import checklist
     looks for."

That reasoning gets STRONGER on an UPSAMPLE, not weaker. The Gaea case was a
1.56% resize; this is a 4.03x enlargement of a ridged alpine terrain, where a
Lanczos overshoot at every arete would be a ring of false terraces along the
skyline. `--filter` exists so the choice is visible, and it DEFAULTS to bicubic.

=====================================================================
WHAT AN UPSAMPLE DOES AND DOES NOT BUY — read this before believing the output
=====================================================================
Enlarging a heightmap ADDS NO INFORMATION. 2017 -> 8129 yields 16x the vertices
carrying the same 4 m content, and no filter changes that: a cliff lip, a ledge
and a crisp arete are all sub-4 m and are simply absent from the source.

This tool is therefore ONLY correct as the LARGE-SCALE half of a pipeline whose
detail comes from somewhere else — for the alpine terrain, from re-compositing
4096-pixel stamps that the 2017 grid was discarding at up to 9.6x, and from a
28 m detail-relief band that at 4 m/texel was aliased across 7 texels and at
1 m/texel resolves across 28.

**Using the output of this script AS A TERRAIN, on its own, is a REJECTED
pattern.** It would be 16x the memory for the same mountain.

Exit codes:
  0  resampled and written, OR a DRY RUN completed (no --go: nothing written)
  2  refused before writing anything
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
from make_alpine_terrain import write_png16_grey  # noqa: E402
from resize_gaea_build import _resample  # noqa: E402

EXIT_REFUSE = 2

FILTERS = {
    "bicubic": Image.BICUBIC,
    "lanczos": Image.LANCZOS,
    "bilinear": Image.BILINEAR,
    "nearest": Image.NEAREST,
}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _legal_landscape_sizes(n: int) -> list[str]:
    """UE landscapes are (components x quads) + 1 vertices. Reported so a
    target that cannot tile is visible BEFORE the import refuses it."""
    out = []
    for quads in (7, 15, 31, 63, 127, 255):
        for sections in (1, 2):
            span = quads * sections
            if (n - 1) % span == 0:
                out.append("%d quads x %d sections x %d components"
                           % (quads, sections, (n - 1) // span))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="16-bit square PNG heightmap")
    ap.add_argument("--output", required=True, help="destination, must be inside terrain/")
    ap.add_argument("--size", type=int, required=True, help="target side in pixels")
    ap.add_argument("--filter", choices=sorted(FILTERS), default="bicubic",
                    help="bicubic for HEIGHT (default). See the module docstring: "
                         "lanczos overshoots at ridges and an overshoot in a "
                         "heightmap is a false terrace.")
    ap.add_argument("--go", action="store_true",
                    help="without this the run is a DRY RUN and writes nothing")
    args = ap.parse_args(argv)

    repo = bootstrap.REPO_ROOT
    terrain_dir = os.path.join(repo, "terrain")
    out_abs = os.path.abspath(args.output)
    in_abs = os.path.abspath(args.input)

    # Standing rule 1, enforced rather than trusted.
    _td = os.path.abspath(terrain_dir)
    try:
        _inside = os.path.commonpath([out_abs, _td]) == _td
    except ValueError:
        # Windows: commonpath raises across drives -> definitively NOT inside
        # terrain/. Refuse cleanly rather than dying with a traceback (the gate
        # promised a REFUSE/exit-2 for any out-of-terrain path).
        _inside = False
    if not _inside:
        print("REFUSED: output must be inside terrain/. Got %s" % out_abs)
        return EXIT_REFUSE
    if out_abs == in_abs:
        print("REFUSED: output would overwrite the input. A resample that "
              "consumes its own source cannot be re-run or checked.")
        return EXIT_REFUSE
    if not os.path.exists(in_abs):
        print("REFUSED: input does not exist: %s" % in_abs)
        return EXIT_REFUSE

    im = Image.open(in_abs)
    if im.mode != "I;16":
        print("REFUSED: %s is PIL mode %r; a heightmap must be 16-bit ('I;16'). "
              "An 8-bit source upsampled to 8129 would carry 256 height levels "
              "over the whole terrain and band visibly." % (args.input, im.mode))
        return EXIT_REFUSE
    if im.size[0] != im.size[1]:
        print("REFUSED: %s is %dx%d; must be square." % (args.input, im.size[0], im.size[1]))
        return EXIT_REFUSE

    src = np.asarray(im, dtype=np.uint16)
    n = src.shape[0]
    if args.size == n:
        print("REFUSED: target size equals source size (%d). Nothing to do." % n)
        return EXIT_REFUSE

    factor = args.size / float(n)
    layouts = _legal_landscape_sizes(args.size)

    print("=== PLAN ===")
    print("  input           %s" % args.input)
    print("                  %d x %d  I;16  sha256 %s" % (n, n, _sha256(in_abs)[:16]))
    print("  source range    %d .. %d of 65535" % (int(src.min()), int(src.max())))
    print("  target          %d x %d   (%.3fx)" % (args.size, args.size, factor))
    print("  filter          %s%s" % (args.filter,
          "   <- the ruling for HEIGHT" if args.filter == "bicubic" else "   <- NOT the height default"))
    print("  output          %s" % args.output)
    print("  legal UE layout %s" % (layouts[0] if layouts
                                    else "NONE — this size cannot tile a landscape"))
    if factor > 1.0:
        print()
        print("  NOTE: this is an UPSAMPLE. It adds NO information. It is only")
        print("  correct as the large-scale half of a pipeline whose detail")
        print("  arrives from elsewhere. See the module docstring.")
    print()

    if not args.go:
        print("DRY RUN. Nothing written. Re-run with --go.")
        return 0

    out, (lo, hi) = _resample(src, args.size, FILTERS[args.filter])

    # The clamp inside _resample is to the SOURCE range; assert it held rather
    # than trusting it (non-negotiable 8 — verify with a different read than the
    # one that made the claim).
    assert out.dtype == np.uint16, "writer contract: uint16"
    if int(out.min()) < int(lo) or int(out.max()) > int(hi):
        print("REFUSED AFTER RESAMPLE: result range %d..%d escaped the source "
              "range %d..%d. Not written." % (out.min(), out.max(), lo, hi))
        return EXIT_REFUSE

    write_png16_grey(out_abs, out)

    print("=== RESULT ===")
    print("  wrote           %s" % args.output)
    print("  %d x %d  range %d .. %d  (source %d .. %d)"
          % (out.shape[1], out.shape[0], int(out.min()), int(out.max()), int(lo), int(hi)))
    print("  mean            %.2f  (source %.2f)" % (out.mean(), src.mean()))
    print("  sha256          %s" % _sha256(out_abs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
