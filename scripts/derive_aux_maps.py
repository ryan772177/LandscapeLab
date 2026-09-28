"""derive_aux_maps.py — flow / deposition / hillshade for an ADOPTED heightmap.

OFFLINE. No editor, no `unreal`. Reads one heightmap and writes the three
auxiliary maps beside it. **It never writes a heightmap.**

WHY THIS EXISTS
---------------
`terrain/alpine_flow.png` and `alpine_deposition.png` are BYPRODUCTS of the
hydraulic erosion pass inside `make_alpine_terrain.py` — they fall out of
the run that GENERATED the terrain. So after Pass 1 adopts a composited
heightmap, those maps describe drainage on a surface that no longer
exists, and `place_foliage.py` reads the flow map to bias Conifer
placement (`flow_bias: 0.45`). Re-placing foliage against them would
place 160,448 trees against invalidated data — exactly what
`composite_stamps.py`'s ADOPTION block warns about.

`make_alpine_terrain.py` cannot be re-run to refresh them: it GENERATES
terrain from noise and would destroy the adopted composition.

THE MECHANISM, and why it is not a reimplementation
---------------------------------------------------
`terrain_erosion.hydraulic_droplets()` returns `(height, flow, deposition)`.
This script runs THAT function — the same code that produced the original
maps — on a COPY of the adopted heightmap, keeps `flow` and `deposition`,
and **throws the eroded height away**.

That matters for two reasons:

  1. **No divergence.** A hand-written flow accumulator here would be a
     second implementation of a thing that must agree with the first, and
     the two would drift. CLAUDE.md non-negotiable 19: when two consumers
     need the same physical fact, they share the code that decides it.
  2. **The approved terrain is not modified.** Erosion is computed and
     discarded. The composition Ryan approved is the composition that
     ships; the droplets only report where water WOULD run over it.

The droplet parameters must match the generator's, or the flow map is
computed under different physics from the one it replaces. They are read
from `make_alpine_terrain`'s own argparse defaults rather than copied, so
they cannot silently drift apart.

WHAT THIS DOES NOT DO
---------------------
It does NOT re-erode the terrain. If the intent is to let erosion carve
drainage through the newly stamped ridges — which is a defensible artistic
choice — that is a TERRAIN CHANGE and needs its own approval, not an
auxiliary-map refresh.

Exit codes:
  0  maps written
  2  input missing or malformed
  4  a written map failed its read-back
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap             # noqa: E402
import terrain_erosion       # noqa: E402 — the SAME erosion the generator used
import make_alpine_terrain as mat  # noqa: E402 — write_png16_grey + defaults

REPO_ROOT = bootstrap.REPO_ROOT
TERRAIN_DIR = os.path.join(REPO_ROOT, "terrain")

# Mirrors make_alpine_terrain's argparse defaults. Verified against them at
# runtime below — a silent drift between the generator and this refresh
# would produce a flow map under different physics from the one it
# replaces, which is worse than no refresh at all.
DEFAULTS = {
    # IMPORTED, not copied. I first hardcoded 20260801 here and the drift
    # check caught it: the real value is 20260731. A wrong seed produces a
    # different RNG stream, so the refreshed flow map would have been
    # computed under different physics from the one it replaced — and
    # nothing downstream would have complained.
    "seed": mat.DEFAULT_SEED,
    "droplets": 250000,
    "droplet_lifetime": 48,
    "droplet_inertia": 0.05,
    "droplet_capacity": 8.0,
    "droplet_erode": 0.30,
    "droplet_deposit": 0.30,
    "droplet_smooth": 0.6,
}

# The droplet knobs above are argparse defaults inside make_alpine_terrain
# and cannot be imported, so they are ASSERTED against its source at
# import time. Two copies of a number that must agree, with nothing
# checking, is how they stop agreeing.
_FLAG_FOR = {
    "droplets": "--droplets",
    "droplet_lifetime": "--droplet-lifetime",
    "droplet_inertia": "--droplet-inertia",
    "droplet_capacity": "--droplet-capacity",
    "droplet_erode": "--droplet-erode",
    "droplet_deposit": "--droplet-deposit",
    "droplet_smooth": "--droplet-smooth",
}


def _assert_no_default_drift():
    import inspect
    import re
    src = inspect.getsource(mat)
    drift = []
    for key, flag in _FLAG_FOR.items():
        m = re.search(re.escape('"%s"' % flag) + r".*?default=([^,\)\s]+)",
                      src, re.S)
        if m is None:
            drift.append("{0}: flag {1} not found in make_alpine_terrain"
                         .format(key, flag))
            continue
        try:
            if float(m.group(1)) != float(DEFAULTS[key]):
                drift.append("{0}: this script says {1}, the generator "
                             "says {2}".format(key, DEFAULTS[key],
                                               m.group(1)))
        except ValueError:
            drift.append("{0}: generator default {1!r} is not a literal"
                         .format(key, m.group(1)))
    if drift:
        raise RuntimeError(
            "droplet parameter drift between derive_aux_maps and "
            "make_alpine_terrain — the refreshed maps would be computed "
            "under different physics from the ones they replace:\n  "
            + "\n  ".join(drift))


_assert_no_default_drift()


def _norm(p):
    return os.path.normcase(os.path.abspath(p))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default=os.path.join(REPO_ROOT, "recipes",
                                                     "alpine.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--droplets", type=int, default=0,
                    help="explicit droplet count. 0 (default) scales the "
                         "generator's 250,000 by CELL COUNT, which is a no-op "
                         "at 2017 and the only correct answer at any other "
                         "resolution -- see the note printed at run time.")
    args = ap.parse_args(argv)

    try:
        with open(args.recipe, "r", encoding="utf-8") as fh:
            recipe = json.load(fh)
    except (OSError, ValueError) as exc:
        print("REFUSE: cannot read recipe: {0}".format(exc))
        return 2

    src = os.path.join(REPO_ROOT, recipe["heightmap"]["source"])
    if not _norm(src).startswith(_norm(TERRAIN_DIR) + os.sep):
        print("REFUSE: heightmap.source escapes terrain/")
        return 2
    if not os.path.isfile(src):
        print("REFUSE: heightmap not found: {0}".format(src))
        return 2

    im = Image.open(src)
    if im.mode != "I;16":
        print("REFUSE: heightmap must be 16-bit single channel, got mode "
              "{0!r}".format(im.mode))
        return 2
    h_units = np.asarray(im).astype(np.float64)
    n = h_units.shape[0]

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("heightmap : {0}  ({1} x {1})".format(
        recipe["heightmap"]["source"], n))
    # DROPLET COUNT SCALES WITH CELL COUNT, and this is not a preference.
    #
    # `droplets` is a fixed 250,000 in the generator's defaults, tuned at the
    # 2017 grid the alpine terrain was generated on. Droplets are lagrangian
    # particles rasterised onto the grid: the same 250,000 over the same world
    # at 4x the linear resolution draws drainage lines that are FOUR TIMES
    # THINNER IN METRES, because a track is one cell wide whatever a cell is.
    #
    # MEASURED 2026-08-13, which is why this exists. Deriving the 8129 maps at
    # the fixed 250,000 gave a flow map with 7.27% of cells non-zero against
    # alpine's 47.42%, and the band that actually drives Conifer `flow_bias`
    # 0.45 collapsed from 18.449% of the map to 1.327%. The map was not wrong
    # in shape, it was starved of samples, and the trees would have gone
    # somewhere else while every downstream check reported success.
    #
    # Holding droplets-per-CELL constant reproduces the rasterised statistics
    # the downstream normalisation and thresholds were tuned against. It is
    # exactly a no-op at 2017: 250000/2017^2 x 2017^2 == 250000.
    ref_n = 2017          # the grid alpine's 250,000 was tuned on
    density = DEFAULTS["droplets"] / float(ref_n * ref_n)
    droplet_count = args.droplets if args.droplets > 0 else int(round(density * n * n))

    print("")
    print("--- droplet parameters (from make_alpine_terrain defaults) ---")
    for k in sorted(DEFAULTS):
        print("  {0:<20} {1}".format(k, DEFAULTS[k]))
    print("")
    print("--- droplet count, SCALED BY CELL COUNT ---")
    print("  reference             {0:,} droplets on {1} x {1}".format(
        DEFAULTS["droplets"], ref_n))
    print("  density               {0:.6f} droplets per cell".format(density))
    print("  this grid             {0} x {0}".format(n))
    print("  EFFECTIVE COUNT       {0:,}{1}".format(
        droplet_count, "   (--droplets override)" if args.droplets > 0 else ""))
    if droplet_count != DEFAULTS["droplets"]:
        print("  NOTE: this is NOT the generator's literal count, so the maps")
        print("  below are not bit-comparable with a generator run. They are")
        print("  STATISTICALLY comparable, which is what the consumers need.")
    print("")
    print("Running the SAME erosion the generator used, on a COPY.")
    print("The eroded height is DISCARDED — only flow and deposition are")
    print("kept. The adopted terrain is not modified by this script.")

    if args.dry_run:
        print("")
        print("DRY RUN — nothing written.")
        return 0

    before = h_units.copy()
    drng = np.random.RandomState((DEFAULTS["seed"] + 8081) % (2 ** 32))
    _eroded, flow, depo = terrain_erosion.hydraulic_droplets(
        h_units.copy(), drng,
        count=droplet_count,
        lifetime=DEFAULTS["droplet_lifetime"],
        inertia=DEFAULTS["droplet_inertia"],
        capacity_factor=DEFAULTS["droplet_capacity"],
        erode_rate=DEFAULTS["droplet_erode"],
        deposit_rate=DEFAULTS["droplet_deposit"],
        smooth=DEFAULTS["droplet_smooth"])

    # The whole safety claim of this script, asserted rather than trusted.
    if not np.array_equal(before, h_units):
        print("REFUSE: the source height array was mutated in place. The "
              "adopted terrain must not change; refusing to write anything.")
        return 4
    print("")
    print("  source heightmap unchanged: VERIFIED (array-equal before/after)")
    print("  flow touched {0:.1f}% of cells, deposition {1:.1f}%".format(
        100.0 * float((flow > 0).mean()), 100.0 * float((depo > 0).mean())))

    # Names come from the recipe's biome_id via the SINGLE DECLARATION in
    # placement_priors, never from a literal here. These were hardcoded
    # "alpine_*.png" until 2026-08-13, which meant deriving aux maps for ANY
    # other biome overwrote /Game/Alpine's -- and alpine_flow.png drives that
    # world's Conifer flow_bias, so its placement inputs would have been
    # silently replaced by a different terrain's while this script reported
    # success. biome_id "alpine" still yields the identical names.
    import placement_priors  # noqa: E402 — local import keeps the offline path light
    _aux = placement_priors.aux_map_names(recipe["biome_id"])

    written = []
    for name, arr in ((_aux["flow"], np.log1p(flow)),
                      (_aux["deposition"], np.log1p(depo)),
                      (_aux["hillshade"],
                       terrain_erosion.hillshade(h_units))):
        path = os.path.join(TERRAIN_DIR, name)
        if not _norm(path).startswith(_norm(TERRAIN_DIR) + os.sep):
            print("REFUSE: {0} escapes terrain/".format(name))
            return 2
        lo, hi = float(arr.min()), float(arr.max())
        u16 = np.rint((arr - lo) / max(hi - lo, 1e-9) * 65535.0)
        u16 = np.clip(u16, 0, 65535).astype(np.uint16)
        mat.write_png16_grey(path, u16)
        written.append((name, path, u16))

    print("")
    print("--- written, each verified by READ-BACK ---")
    for name, path, expect in written:
        back = np.asarray(Image.open(path))
        ok = (back.shape == expect.shape and back.dtype == expect.dtype
              and np.array_equal(back, expect))
        print("  {0:<26} {1}  {2}".format(
            name, "OK " if ok else "MISMATCH", os.path.getsize(path)))
        if not ok:
            print("REFUSE: {0} did not read back as written.".format(name))
            return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
