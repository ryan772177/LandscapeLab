"""make_test_heightmap.py — synthetic 16-bit heightmap generator.

Unblocks the alpine milestone while the Gaea export is outstanding. The
output is a stand-in with the same path, format, and geometry contract as
a real export: when Gaea cooperates, it overwrites the same file and no
recipe or schema change is needed.

LOCAL ONLY. This script never contacts the editor — no remote execution,
no multicast, conduct rule 7 not in play. It writes exactly one file,
inside REPO_ROOT/terrain/, and refuses any output path outside it.

METHOD
Layered value noise (fractal Brownian motion): a lattice of random values
per octave, smoothstep-interpolated up to full resolution, summed with
decreasing amplitude and increasing frequency. A radial dome is mixed in
to bias a central peak, so the result has a summit, flanks, and lower
ground — enough vertical and angular spread to exercise both the slope
rules and the height rules in a recipe's material layers.

Value noise rather than Perlin/simplex: it is a few lines of numpy with
no gradient tables, it is exactly reproducible from a seed, and for a
test fixture its slightly blockier character is irrelevant — what matters
is the slope and height distribution, which this script measures and
reports.

SEED — schema v1 has no seed key. The heightmap table (recipes/schema.md
:44-52) defines source, format, resolution, section_size,
sections_per_component, and component_count only. So the seed is a
hardcoded default here rather than recipe-driven, overridable with
--seed. A `heightmap.seed` key is a legitimate schema v1.1 need: without
it, regenerating this fixture is reproducible only by convention, which
sits awkwardly against hard rule 3.

PNG WRITING — done directly with zlib and struct rather than Pillow.
16-bit greyscale PNG is a short, well-specified format, and writing it
here keeps the approved-dependency surface to numpy alone.

Exit codes:
  0  heightmap written and its dimensions/format read back off disk (IHDR:
     width, height, 16-bit, greyscale). Pixel content is NOT re-read.
  1  unexpected error / bad arguments / refused output path
  2  requested resolution is not a legal Unreal landscape resolution
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import zlib

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERRAIN_DIR = os.path.join(REPO_ROOT, "terrain")
DEFAULT_OUTPUT = os.path.join(TERRAIN_DIR, "alpine_heightmap.png")
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

# Deterministic by default. Same seed + same parameters => byte-identical
# PNG on the same numpy and zlib versions, which is what makes this fixture
# safe under hard rule 3. Caveat: NumPy guarantees Generator stream
# stability only within a release series (NEP 19), and zlib output can in
# principle differ between zlib builds — if the exact bytes ever matter
# (e.g. a committed hash), record numpy and zlib versions alongside them.
DEFAULT_SEED = 20260728

LEGAL_SECTION_SIZES = (7, 15, 31, 63, 127, 255)
# The integer Unreal stores, not the dialog label: "2x2 Sections" is 2.
# FLandscapeConfig::NumSectionValues[2] = { 1, 2 } (LandscapeConfigHelper.cpp
# :24), used linearly as QuadsPerComponent = SectionsPerComponent *
# QuadsPerSection. A value of 4 is not buildable.
LEGAL_SPC = (1, 2)
UINT16_MAX = 65535


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


# ------------------------------------------------------------- geometry --

def _landscape_factorisations(resolution):
    """All (section_size, sections_per_component, component_count) triples
    that produce `resolution` under the schema's identity."""
    out = []
    for ss in LEGAL_SECTION_SIZES:
        for spc in LEGAL_SPC:
            step = ss * spc
            if (resolution - 1) % step == 0:
                cc = (resolution - 1) // step
                if cc >= 1:
                    out.append((ss, spc, cc))
    return out


def _nearest_legal(resolution):
    """Legal resolutions bracketing `resolution`, for the error message."""
    candidates = set()
    for ss in LEGAL_SECTION_SIZES:
        for spc in LEGAL_SPC:
            step = ss * spc
            cc = max(1, (resolution - 1) // step)
            candidates.add(step * cc + 1)
            candidates.add(step * (cc + 1) + 1)
    ordered = sorted(candidates)
    below = [c for c in ordered if c < resolution][-3:]
    above = [c for c in ordered if c > resolution][:3]
    return below + above


# ---------------------------------------------------------------- noise --

def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _value_noise(n, freq, rng):
    """One octave of value noise, smoothstep-interpolated to n x n.

    A (freq+1)^2 lattice of uniform random values is interpolated up. The
    +1 means the lattice spans the full grid inclusive of both edges, so
    no wrap-around seam appears.
    """
    freq = max(1, int(freq))
    lattice = rng.random((freq + 1, freq + 1))

    coords = np.linspace(0.0, float(freq), n)
    idx = np.clip(np.floor(coords).astype(np.int64), 0, freq - 1)
    fade = _smoothstep(coords - idx)

    # Interpolate along the first axis, then the second.
    top = lattice[idx, :]
    bottom = lattice[idx + 1, :]
    fy = fade[:, None]
    rows = top * (1.0 - fy) + bottom * fy

    left = rows[:, idx]
    right = rows[:, idx + 1]
    fx = fade[None, :]
    return left * (1.0 - fx) + right * fx


def _fbm(n, seed, octaves, base_freq, lacunarity, gain):
    """Sum octaves of value noise. Returns an n x n array in [0, 1]."""
    rng = np.random.default_rng(seed)
    total = np.zeros((n, n), dtype=np.float64)
    amplitude = 1.0
    frequency = float(base_freq)
    norm = 0.0
    for _ in range(octaves):
        total += amplitude * _value_noise(n, round(frequency), rng)
        norm += amplitude
        amplitude *= gain
        frequency *= lacunarity
    return total / norm


def _central_dome(n):
    """Radial falloff in [0, 1], 1 at centre, 0 at the inscribed circle."""
    centre = (n - 1) / 2.0
    axis = (np.arange(n) - centre) / centre
    radius = np.sqrt(axis[:, None] ** 2 + axis[None, :] ** 2)
    return _smoothstep(np.clip(1.0 - radius, 0.0, 1.0))


def generate(n, seed, octaves, base_freq, lacunarity, gain, peak_bias,
             relief):
    """Return an n x n uint16 heightfield."""
    noise = _fbm(n, seed, octaves, base_freq, lacunarity, gain)
    dome = _central_dome(n)
    field = peak_bias * dome + (1.0 - peak_bias) * noise

    lo, hi = float(field.min()), float(field.max())
    if hi - lo < 1e-9:
        raise RuntimeError("generated field is flat — check parameters")
    field = (field - lo) / (hi - lo)

    return np.rint(field * relief * UINT16_MAX).astype(np.uint16)


# ------------------------------------------------------------------ png --

def _chunk(tag, payload):
    body = tag + payload
    return (struct.pack(">I", len(payload)) + body +
            struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def write_png16_grey(path, array):
    """Write a 16-bit greyscale PNG (colour type 0, no interlace)."""
    if array.dtype != np.uint16:
        raise ValueError("array must be uint16")
    height, width = array.shape

    # Each scanline is prefixed with filter byte 0 (None). Big-endian
    # samples per the PNG spec.
    be = array.astype(">u2")
    rows = be.view(np.uint8).reshape(height, width * 2)
    raw = np.zeros((height, width * 2 + 1), dtype=np.uint8)
    raw[:, 1:] = rows

    ihdr = struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" +
           _chunk(b"IHDR", ihdr) +
           _chunk(b"IDAT", zlib.compress(raw.tobytes(), 9)) +
           _chunk(b"IEND", b""))

    with open(path, "wb") as fh:
        fh.write(png)


def read_png_header(path):
    """Return (width, height, bit_depth, colour_type) from the IHDR."""
    with open(path, "rb") as fh:
        head = fh.read(26)
    if len(head) < 26 or head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG (signature mismatch)")
    if head[12:16] != b"IHDR":
        raise ValueError("malformed PNG: first chunk is not IHDR")
    width, height = struct.unpack(">II", head[16:24])
    return width, height, head[24], head[25]


# ------------------------------------------------------------- analysis --

def report_relief(array, recipe):
    """Print slope/height statistics against the recipe's scales.

    This is the point of the fixture: confirming the terrain actually
    spans the slope and height ranges the material layers key off. It
    evaluates layers first-match-wins, exactly as recipes/schema.md:63-64
    specifies, so the coverage numbers reflect real behaviour.
    """
    if not recipe:
        print("  (no recipe loaded — skipping relief analysis)")
        return

    scale_xy_cm = float(recipe["landscape"]["scale_xy_cm"])
    z_scale_cm = float(recipe["landscape"]["z_scale_cm"])

    height_m = (array.astype(np.float64) / UINT16_MAX) * (z_scale_cm / 100.0)
    span_m = (array.shape[0] - 1) * scale_xy_cm / 100.0

    gy, gx = np.gradient(height_m, scale_xy_cm / 100.0)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))

    print("  terrain span     : {0:.0f} m across".format(span_m))
    print("  height range     : {0:.1f} m .. {1:.1f} m".format(
        height_m.min(), height_m.max()))
    print("  slope percentiles: p50 {0:.1f}deg  p90 {1:.1f}deg  "
          "p99 {2:.1f}deg  max {3:.1f}deg".format(
              *np.percentile(slope_deg, [50, 90, 99]), slope_deg.max()))

    layers = recipe.get("material", {}).get("layers") or []
    if not layers:
        return
    print("  material coverage (first-match-wins, per schema v1):")
    unassigned = np.ones(array.shape, dtype=bool)
    total = float(array.size)
    for layer in layers:
        s_lo, s_hi = layer["slope_deg"]
        h_lo, h_hi = layer["height_m"]
        mask = (unassigned &
                (slope_deg >= s_lo) & (slope_deg <= s_hi) &
                (height_m >= h_lo) & (height_m <= h_hi))
        pct = 100.0 * mask.sum() / total
        print("    {0:<8} {1:6.2f}%   slope[{2}, {3}]  height[{4}, "
              "{5}]".format(layer["name"], pct, s_lo, s_hi, h_lo, h_hi))
        unassigned &= ~mask
    leftover = 100.0 * unassigned.sum() / total
    print("    {0:<8} {1:6.2f}%   (matched no layer)".format(
        "<none>", leftover))


# ------------------------------------------------------------------ main --

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--resolution", type=int, default=1009,
                        help="Pixels per side. Must satisfy the schema's "
                             "landscape identity. Default 1009.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="Output PNG. Must be inside terrain/.")
    parser.add_argument("--recipe", default=DEFAULT_RECIPE,
                        help="Recipe used for the relief analysis and the "
                             "resolution cross-check.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--octaves", type=int, default=7)
    parser.add_argument("--base-freq", type=int, default=3)
    parser.add_argument("--lacunarity", type=float, default=2.0)
    parser.add_argument("--gain", type=float, default=0.5)
    parser.add_argument("--peak-bias", type=float, default=0.55,
                        help="0 = pure noise, 1 = pure dome. Default 0.55.")
    parser.add_argument("--relief", type=float, default=0.55,
                        help="Fraction of the 16-bit range used. Lower "
                             "means gentler slopes. Default 0.55.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    n = args.resolution
    out_path = os.path.abspath(args.output)

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("Output    : {0}".format(out_path))
    print("")

    # Conduct rule 1: this script writes, so the destination is checked
    # before anything is generated. terrain/ only, no exceptions.
    terrain_norm = _norm(TERRAIN_DIR)
    if not _norm(out_path).startswith(terrain_norm + os.sep):
        print("REFUSE: output must be inside {0}".format(TERRAIN_DIR))
        return 1
    if not 0.0 < args.relief <= 1.0:
        print("REFUSE: --relief must be in (0, 1].")
        return 1
    if not 0.0 <= args.peak_bias <= 1.0:
        print("REFUSE: --peak-bias must be in [0, 1].")
        return 1
    if args.octaves < 1 or args.base_freq < 1:
        print("REFUSE: --octaves and --base-freq must be >= 1.")
        return 1

    factorisations = _landscape_factorisations(n)
    if not factorisations:
        print("REFUSE: {0} is not a legal Unreal landscape resolution "
              "(section_size * sections_per_component * component_count "
              "+ 1).".format(n))
        print("        Nearest legal: {0}".format(
            ", ".join(str(r) for r in _nearest_legal(n))))
        return 2
    print("Resolution {0} is legal. Valid (section_size, "
          "sections_per_component, component_count):".format(n))
    for ss, spc, cc in factorisations:
        print("  {0} * {1} * {2} + 1 = {3}".format(ss, spc, cc, n))
    print("")

    recipe = None
    recipe_path = os.path.abspath(args.recipe)
    if os.path.isfile(recipe_path):
        try:
            with open(recipe_path, "r", encoding="utf-8") as fh:
                recipe = json.load(fh)
        except (OSError, ValueError) as exc:
            print("WARNING: could not read recipe {0}: {1}".format(
                recipe_path, exc))
        else:
            declared = recipe.get("heightmap", {}).get("resolution")
            if declared != n:
                print("!" * 68)
                print("MISMATCH: {0} declares heightmap.resolution {1}, "
                      "but this run generates {2}.".format(
                          os.path.basename(recipe_path), declared, n))
                print("The import script will refuse this pair. Update the")
                print("recipe's resolution AND component_count together, or")
                print("regenerate at {0}.".format(declared))
                print("!" * 68)
                print("")

    print("Generating {0}x{0} (seed {1}, {2} octaves, relief {3}) ...".format(
        n, args.seed, args.octaves, args.relief))
    field = generate(n, args.seed, args.octaves, args.base_freq,
                     args.lacunarity, args.gain, args.peak_bias, args.relief)

    os.makedirs(TERRAIN_DIR, exist_ok=True)
    write_png16_grey(out_path, field)

    width, height, bit_depth, colour_type = read_png_header(out_path)
    size_mb = os.path.getsize(out_path) / (1024.0 * 1024.0)
    print("")
    print("Written: {0}".format(out_path))
    print("  dimensions : {0} x {1}".format(width, height))
    print("  bit depth  : {0}".format(bit_depth))
    print("  colour type: {0} (0 = greyscale)".format(colour_type))
    print("  file size  : {0:.2f} MiB".format(size_mb))
    print("  value range: {0} .. {1} of {2}".format(
        int(field.min()), int(field.max()), UINT16_MAX))

    if (width, height, bit_depth, colour_type) != (n, n, 16, 0):
        print("\nERROR: written file does not match the requested format.")
        return 1

    print("")
    print("--- relief analysis ---")
    try:
        report_relief(field, recipe)
    except (KeyError, TypeError, ValueError) as exc:
        # Analysis is auxiliary: a malformed recipe must not turn a
        # successful, verified write into a failure exit code.
        print("WARNING: relief analysis failed ({0}: {1}). The heightmap "
              "itself was written and its dimensions/format read back off "
              "disk.".format(type(exc).__name__, exc))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
