"""make_layer_textures.py — synthetic tiling detail textures per material layer.

LOCAL ONLY. No editor contact, no remote execution. Writes 8-bit RGB PNGs
into textures/ for import by make_landscape_material.py.

WHAT THESE ARE (the datum — read this before changing anything)
--------------------------------------------------------------
They are NOT albedo maps. They are **multiplicative variation maps in
linear space**, and the recipe keeps ownership of colour:

    final_albedo = base_color * 4 * detail_sample.rgb * macro_sample.rgb

Each PNG is authored so its per-channel mean is exactly 0.5. Two samples
multiplied and scaled by 4 therefore have mean 0.5*0.5*4 = 1.0, so a layer
whose texture is fully mipped out renders EXACTLY its recipe `base_color`.

Three things fall out of that, all of them the point:
  1. Hard rule 2 holds. Colour stays in recipes/alpine.json. The texture
     supplies spatial variation only, so changing snow's colour is still a
     one-line recipe edit with no asset regeneration.
  2. Degradation is graceful and provable. At kilometre distances the
     detail scale mips to its mean and multiplies by 1.0 - it cannot tint
     the terrain as it fades.
  3. The mean is asserted, not assumed. See _fit_mean below: this file
     refuses to write a PNG whose mean is off, because a mean of 0.48
     would darken every layer by 8% with nothing erroring and no way to
     see it in the image (lesson 6.2, the silent-wrong class).

The x4 is an ENCODING CONSTANT of this texture format, exactly like the
heightmap's 32768 datum - not a scene parameter. It exists because an
unsigned 8-bit texture cannot store a multiplier centred on 1.0.

sRGB MUST BE OFF on import. These bytes are linear multipliers, not
colours. If the importer leaves srgb=True, byte 128 decodes to 0.216
instead of 0.502 and every layer darkens by ~57% - silently.
make_landscape_material.py reads the flag back after import and refuses
rather than trusting that the set succeeded.

TILEABILITY
-----------
All noise lattices divide the texture size exactly and wrap modulo the
lattice, so the result tiles seamlessly under TA_WRAP. A non-tiling
texture would draw a visible grid across the terrain at macro scale.

AUTHORING PARAMETERS LIVE HERE, NOT IN THE RECIPE
-------------------------------------------------
Seed, octaves, contrast and the per-layer shaping are source-data
authoring parameters under the standing ruling in LESSONS.md
(2026-07-28, "source-authoring parameters stay out of recipe JSON").
They author the source asset that the recipe then points at, exactly as
Gaea's internal .tor settings would. The recipe owns which file a layer
uses (`texture`) and how it repeats (`tiling_m`, `macro_tiling_m`).

Exit codes:
  0  all SELECTED textures written and verified (--help also exits 0, no-op)
  1  unexpected error / bad arguments
  2  output path escapes REPO_ROOT (conduct rule 1)
  3  a texture failed one of its gates (mean, swing, or directionality) and
     was NOT written
"""

from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTURE_DIR = os.path.join(REPO_ROOT, "textures")

DEFAULT_SIZE = 1024
DEFAULT_SEED = 20260801

# Mean tolerance in stored 0..1 units, checked AFTER 8-bit quantisation.
# 4e-4 is ~0.1 of a byte step; anything looser lets a visible tint through.
MEAN_TOL = 4e-4
TARGET_MEAN = 0.5


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _value_noise(size, lattice, rng, aspect=1):
    """Periodic value noise. Wraps exactly, so the PNG tiles seamlessly.

    `aspect` stretches the lattice along X, which is how the anisotropic
    features (wind drift on snow, strata on rock) are produced without a
    separate noise implementation.
    """
    lx = max(1, lattice // aspect)
    ly = lattice
    grid = rng.random((ly, lx))

    yy = np.arange(size) * (ly / float(size))
    xx = np.arange(size) * (lx / float(size))
    y0 = np.floor(yy).astype(np.int64)
    x0 = np.floor(xx).astype(np.int64)
    fy = _smoothstep(yy - y0)[:, None]
    fx = _smoothstep(xx - x0)[None, :]
    # Modulo wrap on BOTH edges is what makes this tile.
    y0m, y1m = y0 % ly, (y0 + 1) % ly
    x0m, x1m = x0 % lx, (x0 + 1) % lx

    g00 = grid[np.ix_(y0m, x0m)]
    g01 = grid[np.ix_(y0m, x1m)]
    g10 = grid[np.ix_(y1m, x0m)]
    g11 = grid[np.ix_(y1m, x1m)]
    top = g00 * (1.0 - fx) + g01 * fx
    bot = g10 * (1.0 - fx) + g11 * fx
    return top * (1.0 - fy) + bot * fy


def _fbm(size, rng, octaves, base_lattice, gain=0.5, aspect=1):
    total = np.zeros((size, size), dtype=np.float64)
    amp, norm, lat = 1.0, 0.0, base_lattice
    for _ in range(octaves):
        if lat > size:
            break
        total += amp * _value_noise(size, lat, rng, aspect=aspect)
        norm += amp
        amp *= gain
        lat *= 2
    return total / max(norm, 1e-12)


def _fit_mean(z, contrast, target=TARGET_MEAN):
    """Map an unbounded field into (0,1) with an EXACT target mean.

    0.5 + 0.5*tanh(contrast*z + b) never clips, so unlike a clamp it
    cannot silently pile probability mass at 0 or 1 and drag the mean.
    Solve for b by bisection; tanh is monotone in b so this always
    converges.

    Clipping was the obvious implementation and is the wrong one: it
    would shift the mean by an amount that depends on the noise, which is
    precisely the "value arrives but means something else" failure.
    """
    lo, hi = -8.0, 8.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        m = float(np.mean(0.5 + 0.5 * np.tanh(contrast * z + mid)))
        if m < target:
            lo = mid
        else:
            hi = mid
        if abs(m - target) < 1e-12:
            break
    b = 0.5 * (lo + hi)
    return 0.5 + 0.5 * np.tanh(contrast * z + b)


def _centre(a):
    return a - float(np.mean(a))


def _snow(size, rng):
    """Low contrast, wind-drifted. Snow is nearly uniform; overdoing this
    reads as dirty snow rather than as snow.

    DRIFT RETUNED 2026-08-02. It was `aspect=8` at weight 0.70, which
    measured an axis/off-axis power ratio of 2.74 — the texture was
    visibly banded, and because a layer texture TILES, a strong
    directional feature does not read as drift at all. It reads as a
    regular weave repeating across every slope, which is what showed up
    on the snow faces in the ground-level capture.

    The instructive part is that ROCK carries a stronger directional
    component than this ever did — `aspect=6` at weight 0.85 — and
    measures 0.98. Anisotropy alone was never the problem. Rock has
    speckle at 0.35 and fine at 0.12 to mask it, whereas snow is
    deliberately low-contrast (0.07 against rock's 0.15) and had only
    0.15 of grain, so the drift had nothing to hide behind.

    So the fix is not "make snow isotropic" — wind drift is real and
    worth keeping. It is: soften the drift (aspect 8 -> 4, weight
    0.70 -> 0.30) and give it isotropic detail to sit inside
    (grain 0.15 -> 0.35). Measured 2.74 -> 1.07, which is grass's
    figure exactly and within 0.1 of rock's.
    """
    base = _centre(_fbm(size, rng, 6, 8))
    drift = _centre(_fbm(size, rng, 4, 16, aspect=4))
    grain = _centre(_fbm(size, rng, 3, 128))
    z = 1.0 * base + 0.30 * drift + 0.35 * grain
    z /= max(float(np.std(z)), 1e-9)
    # Blue-ish in the hollows, neutral on the crests: scattering in
    # compacted snow. Tiny - a strong tint here would fight sky.color.
    return z, (0.00, 0.02, 0.05), 0.07


def _rock(size, rng):
    """Stratified and speckled. The layer that most needs this: flat grey
    rock at 4 m/quad was the visible ceiling."""
    base = _centre(_fbm(size, rng, 7, 4))
    strata = _centre(_fbm(size, rng, 5, 8, aspect=6))
    speckle = _centre(_fbm(size, rng, 4, 64))
    fine = _centre(_fbm(size, rng, 3, 256))
    z = 1.0 * base + 0.85 * strata + 0.35 * speckle + 0.12 * fine
    z /= max(float(np.std(z)), 1e-9)
    # Iron staining: brighter faces run warmer, shadowed clefts cooler.
    return z, (0.09, 0.03, -0.04), 0.15


def _grass(size, rng):
    """Patchy clumping - alpine meadow is not a lawn. Asymmetric shaping
    (the cube) makes sparse dark patches rather than a symmetric blur."""
    base = _centre(_fbm(size, rng, 6, 6))
    clump = _centre(_fbm(size, rng, 5, 24))
    z0 = 1.0 * base + 0.9 * clump
    z0 /= max(float(np.std(z0)), 1e-9)
    z = _centre(z0 + 0.35 * (z0 ** 3))
    blade = _centre(_fbm(size, rng, 3, 192))
    z = z + 0.22 * blade
    z /= max(float(np.std(z)), 1e-9)
    # Drier/yellower where sparse, deeper green where dense.
    return z, (-0.10, 0.04, -0.07), 0.12


LAYERS = {
    "snow": _snow,
    "rock": _rock,
    "grass": _grass,
}


def build(name, size, seed):
    rng = np.random.default_rng(seed)
    z, tint_gain, contrast = LAYERS[name](size, rng)

    scalar = _fit_mean(z, contrast)

    # Tint is applied as a per-channel GAIN ON THE DEVIATION, never as an
    # additive offset:
    #
    #     ch = 0.5 + (scalar - 0.5) * (1 + k)
    #
    # so mean(ch) = 0.5 + (1+k)*mean(scalar - 0.5) = 0.5 EXACTLY PRE-CLIP, for
    # any k. Bright areas run warm, dark areas cool, and the channel mean is
    # algebraically pinned - no iteration, nothing to converge. (The clip at
    # line ~253 and the 8-bit quantise can nudge it off 0.5 at the tails, so
    # the WRITTEN mean is re-checked within MEAN_TOL by the gate below.)
    #
    # The first version added the tint and then re-fitted each channel
    # through arctanh to restore the mean. That round-trip amplified the
    # tails enormously (arctanh diverges at the extremes) and turned a
    # 4% tint into saturated magenta and green blobs. Fixed by making the
    # mean an identity rather than something to be repaired afterwards.
    dev = scalar - 0.5
    rgb = np.empty(scalar.shape + (3,), dtype=np.float64)
    for c in range(3):
        rgb[..., c] = 0.5 + dev * (1.0 + tint_gain[c])
    rgb = np.clip(rgb, 0.0, 1.0)

    quant = np.rint(rgb * 255.0).astype(np.uint8)
    means = [float(np.mean(quant[..., c])) / 255.0 for c in range(3)]
    # Report the realised albedo swing so an over-contrasty texture is
    # visible as a NUMBER here, not only as a wrecked capture later.
    lo = float(np.percentile(rgb, 2.5))
    hi = float(np.percentile(rgb, 97.5))
    return (quant, means, (4.0 * lo * lo, 4.0 * hi * hi),
            anisotropy(quant.mean(axis=2)))


def anisotropy(gray, wedge_deg=12.0):
    """(axis, diagonal) power relative to every other direction.

    WHY A TEXTURE NEEDS THIS GATE. `build` already asserts the two
    numbers previously known to matter — per-channel mean exactly 0.5,
    and the realised albedo multiplier range — and BOTH passed on a snow
    texture that was visibly banded. Section 10.5 said it in advance:
    "ask what a passing check still permits". A mean of 0.5 and a sane
    contrast range permit any amount of directional structure.

    Direction matters here more than in most textures because a layer
    texture TILES. An isotropic feature repeating every 4 m reads as
    surface. A strongly directional one reads as a weave, and the eye
    finds a repeating weave instantly at any viewing distance.

    Measured as the mean 2-D power in wedges around the axes (and
    separately the diagonals) divided by the mean power everywhere else,
    so 1.0 is directionless. Rock and grass, which look right, sit at
    0.98 and 1.07.
    """
    f = np.asarray(gray, dtype=np.float64)
    f = f - f.mean()
    w = np.hanning(f.shape[0])
    f = f * w[:, None] * w[None, :]
    p = np.abs(np.fft.fftshift(np.fft.fft2(f))) ** 2
    n = f.shape[0]
    c = n // 2
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(xx - c, yy - c)
    ang = np.degrees(np.arctan2(yy - c, xx - c)) % 180.0
    band = (r > n * 0.02) & (r < n * 0.45)
    d_ax = np.minimum(np.minimum(np.abs(ang), np.abs(ang - 180.0)),
                      np.abs(ang - 90.0))
    d_di = np.minimum(np.abs(ang - 45.0), np.abs(ang - 135.0))
    rest = p[band & (d_ax >= wedge_deg) & (d_di >= wedge_deg)].mean()
    return (float(p[band & (d_ax < wedge_deg)].mean() / max(rest, 1e-30)),
            float(p[band & (d_di < wedge_deg)].mean() / max(rest, 1e-30)))


# A tiling texture may carry SOME directional character — rock strata and
# snow drift are real, and flattening them would be a worse texture. This
# is the point past which it stops being a feature and starts being a
# repeat: the shipping snow measured 2.74 and was plainly wrong; rock and
# grass sit at 0.98 and 1.07.
MAX_ANISOTROPY = 1.45


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--size", type=int, default=DEFAULT_SIZE)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--layer", action="append", choices=sorted(LAYERS),
                   help="restrict to one layer; repeatable")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    if args.size < 16 or (args.size & (args.size - 1)) != 0:
        print("REFUSE: --size must be a power of two >= 16 "
              "(lattices must divide it exactly or the texture will not "
              "tile); got {0}".format(args.size))
        return 1

    # Conduct rule 1: the only directory this script may ever write to.
    real_dir = os.path.realpath(TEXTURE_DIR)
    if os.path.commonpath([real_dir, os.path.realpath(REPO_ROOT)]) != \
            os.path.realpath(REPO_ROOT):
        print("REFUSE: texture dir escapes REPO_ROOT: {0}".format(real_dir))
        return 2
    os.makedirs(real_dir, exist_ok=True)

    names = args.layer or sorted(LAYERS)
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("Output    : {0}".format(real_dir))
    print("Size      : {0}x{0}   seed {1}".format(args.size, args.seed))
    print("Datum     : linear multiplier, mean 0.5, decoded as 4*d*m")
    print("")

    failed = []
    _all = sorted(LAYERS)
    for name in names:
        # Per-layer seed offset keyed on the layer's STABLE identity (its index
        # in sorted(LAYERS)), NOT its position in the requested subset. Keying
        # on enumerate() meant `--layer rock` alone (position 0) produced a
        # DIFFERENT texture than rock in a full run (position 1), breaking
        # pipeline rule 3 (a re-run must rebuild the same asset).
        quant, means, swing, aniso = build(name, args.size,
                                           args.seed + _all.index(name) * 977)
        worst = max(abs(m - TARGET_MEAN) for m in means)
        worst_dir = max(aniso)
        ok = (worst <= MEAN_TOL and swing[0] >= 0.25 and swing[1] <= 2.2
              and worst_dir <= MAX_ANISOTROPY)
        path = os.path.join(real_dir, "alpine_{0}.png".format(name))
        status = "ok" if ok else "FAIL"
        print("  {0:<6} mean rgb {1:.5f} {2:.5f} {3:.5f}   "
              "worst dev {4:.6f}  {5}".format(
                  name, means[0], means[1], means[2], worst, status))
        print("         albedo multiplier 95% range x{0:.2f}..x{1:.2f}   "
              "(gate: 0.25..2.20)".format(swing[0], swing[1]))
        print("         directionality axis x{0:.2f} diag x{1:.2f}   "
              "(gate: <= {2:.2f}; 1.00 is directionless)".format(
                  aniso[0], aniso[1], MAX_ANISOTROPY))
        if not ok:
            failed.append(name)
            continue
        Image.fromarray(quant, mode="RGB").save(path, optimize=True)
        print("         wrote {0} ({1} bytes)".format(
            os.path.relpath(path, REPO_ROOT), os.path.getsize(path)))

    print("")
    if failed:
        print("REFUSE: one or more gates failed for: {0}".format(
            ", ".join(failed)))
        print("  These were NOT written. The three gates catch three "
              "different silent failures:")
        print("    mean          — a mean off by {0} tints every surface "
              "using the layer, with no error and nothing visible in the "
              "image itself.".format(MEAN_TOL))
        print("    swing         — a centred mean permits every pixel "
              "being 0 or 1; the first rock texture was black-to-blown "
              "at x0.00..x3.92 and passed the mean check.")
        print("    directionality— a layer texture TILES, so a strongly "
              "directional feature stops reading as drift or strata and "
              "starts reading as a weave repeating across every slope. "
              "Shipping snow measured x2.74 and was visibly banded while "
              "passing both other gates.")
        return 3
    print("All textures verified: per-channel mean 0.5 +/- {0} after "
          "8-bit quantisation, albedo swing inside x0.25..x2.20, and "
          "directionality at or under x{1:.2f}.".format(
              MEAN_TOL, MAX_ANISOTROPY))
    print("A fully-mipped layer therefore renders exactly its recipe "
          "base_color.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
