"""Spike-only: turn the three Gemini stamp seeds into eroded candidate stamps.

Per seed: crop the frame border, mild blur (JPEG artifact kill), a floor-clamp
on spire_peaks ONLY (the one seed-specific step), normalize, run the project's
own hydraulic droplet erosion (physics imported from terrain_erosion, not
reimplemented; the RNG seed is make_alpine_terrain.DEFAULT_SEED, created here
and passed IN), write 16-bit PNG + a hillshade preview.

spire_peaks gets a soft floor-clamp: Gemini baked radial light rays into the
"heightmap"; below the floor is treated as plain (the rays live in the low
band), above it survives. That is a JUDGEMENT documented here, not a
measurement.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import terrain_erosion as te  # noqa: E402
from make_alpine_terrain import DEFAULT_SEED  # noqa: E402

try:
    from scipy import ndimage
except ImportError:
    sys.exit("scipy required")


def norm01(a):
    """Min-max to 0..1, guarding a flat array (span 0) against 0/0 -> NaN.

    Reachable for spire_peaks: if every pixel is below the floor the clamp
    drives the array to all-zeros, and an unguarded (a-min)/(max-min) then
    coerces NaN into the uint16 stamp with no error.
    """
    lo, hi = float(a.min()), float(a.max())
    span = hi - lo
    return (a - lo) / span if span > 0 else np.zeros_like(a)


SEEDS = {
    "stamp_terraced_cliffs": {"floor": 0.0,
                              "note": "terraced pit; MIN-carve use"},
    "stamp_spire_peaks": {"floor": 0.35,
                          "note": "floor kills baked light rays"},
    "stamp_river_basin": {"floor": 0.0,
                          "note": "meander channel + rim"},
}

BORDER_PX = 12
DROPLETS = 60000
VERTICAL_SCALE_M = 500.0   # plausible stamp relief for the erosion pass
CELL_M = 4.0

for name, cfg in SEEDS.items():
    src = os.path.join(REPO, "Free", "gemini_v1", name + ".jpg")
    g = np.asarray(Image.open(src).convert("L")).astype(np.float64) / 255.0
    g = g[BORDER_PX:-BORDER_PX, BORDER_PX:-BORDER_PX]
    g = ndimage.gaussian_filter(g, 1.5)
    if cfg["floor"] > 0.0:
        # Clamp only; the /(1-floor) rescale that used to sit here was dead --
        # the norm01 below re-stretches to 0..1 and overwrites any scalar factor.
        g = np.maximum(0.0, g - cfg["floor"])
    g = norm01(g)

    h = g * VERTICAL_SCALE_M
    rng = np.random.default_rng(DEFAULT_SEED)
    h, flow, depo = te.hydraulic_droplets(h, rng, count=DROPLETS)
    h, n_spikes = te.despike(h)

    hn = norm01(h)
    out16 = (hn * 65535.0).astype(np.uint16)
    eroded_path = os.path.join(HERE, name + "_eroded.png")
    Image.fromarray(out16, mode="I;16").save(eroded_path)

    hs = te.hillshade(h, scale=CELL_M * 100.0)
    hs8 = (norm01(hs) * 255.0).astype(np.uint8)
    hs_path = os.path.join(HERE, name + "_hillshade.png")
    Image.fromarray(hs8).save(hs_path)

    # Verify the artefacts landed on disk rather than trusting the in-memory
    # shape; and disclose the despike count the run just computed.
    for p in (eroded_path, hs_path):
        if not (os.path.isfile(p) and os.path.getsize(p) > 0):
            sys.exit("REFUSE: expected output not written: " + p)
    print("%-24s %s  ->  %dx%d eroded, %d spikes removed, relief norm 0..1" %
          (name, cfg["note"], out16.shape[1], out16.shape[0], n_spikes))

print("done; seed", DEFAULT_SEED, "droplets", DROPLETS)
