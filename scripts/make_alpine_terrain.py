"""make_alpine_terrain.py — eroded alpine heightmap generator.

Replaces the smooth-dome fixture from make_test_heightmap.py with terrain
that actually reads as mountains. Same output contract — 16-bit greyscale
PNG at a legal Unreal landscape resolution, written to terrain/ — so
nothing downstream changes.

LOCAL ONLY. No editor contact. Writes the heightmap plus (by default)
flow/deposition/hillshade aux maps derived from the output stem, all
inside terrain/; refuses any path outside it. --no-aux writes exactly
one file. (The old "exactly one file" claim understated the blast
radius — a colliding stem overwrites three committed aux maps, the
2026-09-02 incident the aux-block comment records; Pass 3 2026-09-16 F2.)

WHY THE OLD ONE LOOKED WRONG
`make_test_heightmap.py` is plain fractal Brownian motion plus a radial
dome. fBm is isotropic and smooth — it makes lumps, not mountains. It
has no ridgelines, no valleys, and no relationship between slope and
elevation, which is why the debug render showed rock speckling scattered
at random rather than following terrain structure.

WHAT THIS DOES INSTEAD, in order

1. RIDGED MULTIFRACTAL. Each octave is folded as (1 - |noise|)^sharpness
   (--ridge-sharpness, default 1.6 — NOT the squared fold the old text
   claimed; Pass 3 F5) rather than summed raw. The fold creates creases where the noise crosses
   zero, and those creases become ridgelines. Higher octaves are
   weighted by the running sum so detail concentrates on existing
   ridges instead of spraying uniformly — that is what makes ridges look
   like they branch.

2. DOMAIN WARP. The ridged field is resampled through a low-frequency
   offset field, so ridgelines meander and fork instead of running in
   noise-grid straight lines. This is the cheapest single trick for
   making procedural terrain stop looking procedural.

3. MASSIF MASK. Several massif centres, joined by ridgeline corridors,
   over a floor that keeps the rest of the map as foothills — a REGION
   with structure, rather than uniform noise. It replaced a single
   radial falloff that confined every world to a disc in the middle of
   the map; `terrain_erosion.composition` measures the difference.

4. THERMAL EROSION (talus). Material above the angle of repose slides
   downhill, iteratively. This is the physically-motivated step and it
   does two things: it produces the straight scree slopes and flat-
   floored valleys that read as real mountains, and it CAPS the slope
   distribution near the talus angle.

   That cap matters beyond looks. The debug render showed the recipe's
   35-degree rock threshold sitting around the 80th percentile of the
   old fixture's slopes, so fine noise crossed it constantly and rock
   came out as salt-and-pepper. Talus erosion concentrates slopes just
   below the repose angle, so a threshold placed above it selects
   coherent faces instead of speckle.

5. HYDRAULIC HINT. A cheap flow proxy (blurred inverse height) carves
   the low ground slightly, deepening valleys without a full droplet
   simulation. Not physically correct; it is there to break the
   symmetry thermal erosion alone leaves behind.

WHY `--relief` DEFAULTS TO 0.48 AND NOT 0.92 (0.92->0.62 2026-08-02,
then 0.62->0.48 the same day after per-octave rotation roughened the
terrain, p50 24.5->31.6 deg; Pass 3 2026-09-16 F1 corrected this header,
which had frozen at 0.62). Default total relief is 1229 m, not 1587 m.
Because it is a traversability control and was being read as a cosmetic
one. `--relief` scales the finished field on the last line, so it sets
the world's total vertical drop against the recipe's `z_scale_cm`: 0.92
meant 2355 m of relief across an 8.06 km map, which is Himalayan. The
old terrain survived that only because its radial mask flattened a third
of the map — the dead frame WAS the connected rideable region, so the
project's headline number (mount-in-one-piece 84.9%) was substantially
delivered by its worst feature. Filling the map to the edges removed the
frame and mount-in-one-piece collapsed to 22.1%.

The mask was not at fault and the mask floor was not the lever: dropping
it from 0.30 to 0.10 moved mount-in-one-piece 22.1% -> 28.3% while
letting flat ground creep back to 13.8% of the border. Relief was. At
0.62 the same terrain reads p50 24.5 deg and scores walk 90.5% / 99.7%
in one piece, mount 72.9% / 92.2% — better than the old world on every
gate, with 1.3% of the border flat instead of 82.9%.

Deterministic: same seed and parameters give the same PNG, on the same
numpy build. All shaping parameters are CLI arguments, not recipe keys —
per the standing ruling (LESSONS.md, 2026-07-28) that parameters
shaping SOURCE DATA belong to the tool that authors the source, exactly
as Gaea's own settings would.

Exit codes:
  0  heightmap written and verified (or written with the world gate
     deliberately skipped because no recipe was given — that skip is
     printed)
  1  unexpected error / bad arguments / refused output path / a recipe
     that was given but does not parse (the gate cannot run, so the
     heightmap is NOT written)
  2  requested resolution is not a legal Unreal landscape resolution
  3  heightmap WRITTEN, but the world misses its recipe's `world`
     targets — the file is real and inspectable but must NOT be pushed
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import time
import zlib

import numpy as np

import terrain_erosion  # noqa: E402 — droplets, de-spike, hillshade

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERRAIN_DIR = os.path.join(REPO_ROOT, "terrain")
DEFAULT_OUTPUT = os.path.join(TERRAIN_DIR, "alpine_heightmap.png")
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

DEFAULT_SEED = 20260731

LEGAL_SECTION_SIZES = (7, 15, 31, 63, 127, 255)
LEGAL_SPC = (1, 2)
UINT16_MAX = 65535


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.realpath(path)))


def _landscape_factorisations(resolution):
    out = []
    for ss in LEGAL_SECTION_SIZES:
        for spc in LEGAL_SPC:
            step = ss * spc
            if (resolution - 1) % step == 0 and (resolution - 1) // step >= 1:
                out.append((ss, spc, (resolution - 1) // step))
    return out


# ---------------------------------------------------------------- noise --

def _smoothstep(t):
    """3t^2 - 2t^3. Used for MASKS, never for noise interpolation.

    Fine for a falloff, wrong for a lattice — see `_quintic`.
    """
    return t * t * (3.0 - 2.0 * t)


def _quintic(t):
    """6t^5 - 15t^4 + 10t^3 — Perlin's improved fade curve.

    WHY THIS EXISTS, measured 2026-08-02. The terrain carried a visible
    axis-aligned crosshatch, in the local hillshade AND in the engine's
    render. Measuring the PERIOD of it rather than theorising located it
    immediately: the dominant periodicities were 672.3, 155.2, 77.6 and
    36.0 px against value-noise octave lattices at 672.3, 160.0, 78.0
    and 38.1 px. The component/section size of 63 px did not appear at
    all, which ruled out LOD seams, weightmap sampling and the material
    in one measurement.

    The cause is that smoothstep is C1 but NOT C2: its second derivative
    is 6 - 12t, which is +6 at t=0 and -6 at t=1. So curvature jumps at
    every lattice boundary. Shading is computed from derivatives, so a
    curvature discontinuity is a visible crease — and because every
    octave shares the same axis-aligned lattice origin, those creases
    line up across octaves and reinforce into a grid.

    The quintic has first AND second derivatives equal to zero at t=0
    and t=1 (f' = 30t^2(t-1)^2, f'' = 60t(2t^2-3t+1)), so the lattice
    boundary is invisible to shading. This is exactly the change Perlin
    made in Improved Noise, for exactly this reason.
    """
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _value_noise(n, freq, rng, rotate=True):
    """One octave of value noise, quintic-interpolated, ROTATED.

    THE ROTATION IS THE POINT, and it was arrived at the hard way.

    The terrain carried a rectangular lattice of bright ridge lines,
    visible in a high-pass crop of the heightmap and in the engine's
    render. Two wrong turns before the cause:

    1. A spectral test "found" peaks at 672/155/78/36 px matching the
       octave lattices — but a multi-octave fBm has power at its octave
       frequencies BY CONSTRUCTION. That measurement located the design,
       not the defect. Looking at a high-pass crop, which should have
       come first, showed the grid in seconds.
    2. Switching the fade curve from smoothstep to a quintic (Perlin's
       improved-noise fix for exactly this class of artefact) changed
       nothing measurable — 0.9x. The fade curve governs SMOOTHNESS at a
       lattice boundary; it cannot remove the boundary's ORIENTATION.

    The mechanism is the ridge fold. `_ridged_fbm` folds each octave as
    `1 - |2v - 1|`, creasing wherever v crosses 0.5. In separable value
    noise those level sets run along lattice rows and columns, so the
    fold converts a mild axis alignment into sharp bright ridges — and
    since every octave shared the same axes, nine octaves of them
    stacked into a rectangular grid.

    Sampling each octave through its own random rotation removes the
    shared axes. It costs a full 2-D gather instead of a separable one;
    that is the price of isotropy and it is worth it. The quintic is
    kept because it is correct on its own merits.
    """
    freq = max(1, int(freq))
    ang = float(rng.random()) * 2.0 * math.pi if rotate else 0.0
    # A rotated [0, freq] square needs a lattice covering its bounding
    # box, which grows by up to sqrt(2). Pad generously and let the
    # clamp below handle the corners rather than computing the tight
    # bound — an off-by-one here is an index error, not a subtle bias.
    span = int(math.ceil(freq * math.sqrt(2.0))) + 3
    lattice = rng.random((span + 2, span + 2))

    # Built as an outer sum rather than a meshgrid pair: the rotation is
    # affine, so each rotated coordinate is a row term plus a column
    # term. That halves the peak allocation, which matters — at 2017 a
    # single n*n float64 is 32 MB and the naive form holds a dozen.
    t = np.linspace(0.0, float(freq), n) - float(freq) * 0.5
    ca, sa = math.cos(ang), math.sin(ang)
    half = span * 0.5
    rx = np.clip((t * ca)[None, :] - (t * sa)[:, None] + half,
                 0.0, span - 1.001)
    ry = np.clip((t * sa)[None, :] + (t * ca)[:, None] + half,
                 0.0, span - 1.001)

    ix = np.floor(rx).astype(np.int32)
    iy = np.floor(ry).astype(np.int32)
    fx = _quintic(rx - ix)
    fy = _quintic(ry - iy)
    del rx, ry

    v00 = lattice[iy, ix]
    v01 = lattice[iy, ix + 1]
    v10 = lattice[iy + 1, ix]
    v11 = lattice[iy + 1, ix + 1]
    top = v00 * (1.0 - fx) + v01 * fx
    bot = v10 * (1.0 - fx) + v11 * fx
    return top * (1.0 - fy) + bot * fy


def _ridged_fbm(n, seed, octaves, base_freq, lacunarity, gain, sharpness):
    """Ridged multifractal.

    Each octave is folded to (1 - |2v-1|) and raised to `sharpness`, which
    turns zero-crossings into creases. The running `weight` term makes
    each octave's contribution proportional to what is already high, so
    detail accumulates along ridges rather than everywhere equally —
    the behaviour that makes ridges appear to branch.
    """
    rng = np.random.default_rng(seed)
    total = np.zeros((n, n), dtype=np.float64)
    weight = np.ones((n, n), dtype=np.float64)
    amplitude = 1.0
    frequency = float(base_freq)
    norm = 0.0

    for _ in range(octaves):
        v = _value_noise(n, round(frequency), rng)
        ridge = 1.0 - np.abs(2.0 * v - 1.0)
        ridge = np.power(np.clip(ridge, 0.0, 1.0), sharpness)
        total += amplitude * ridge * weight
        norm += amplitude
        # Clamp keeps the feedback from running away on long octave runs.
        weight = np.clip(ridge * 1.15, 0.0, 1.0)
        amplitude *= gain
        frequency *= lacunarity

    return total / max(norm, 1e-9)


def _smooth_fbm(n, seed, octaves, base_freq, lacunarity, gain):
    """Plain fBm — rounded, massy, no creases.

    Ridged noise alone is thin bright ridges on a dark field: dramatic
    crests with no bulk underneath, which reads in 3D as a flat plain
    with wires on it. Blending a smooth fBm back in supplies the
    shoulders and plateaus that make a mountain look like it has mass,
    while the ridged component keeps the crests sharp.
    """
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
    return total / max(norm, 1e-9)


def _bilinear_sample(field, xs, ys):
    """Sample `field` at fractional coords, clamped at the edges."""
    n = field.shape[0]
    xs = np.clip(xs, 0.0, n - 1.001)
    ys = np.clip(ys, 0.0, n - 1.001)
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    x1 = np.minimum(x0 + 1, n - 1)
    y1 = np.minimum(y0 + 1, n - 1)
    tx = xs - x0
    ty = ys - y0
    top = field[y0, x0] * (1 - tx) + field[y0, x1] * tx
    bot = field[y1, x0] * (1 - tx) + field[y1, x1] * tx
    return top * (1 - ty) + bot * ty


def _domain_warp(field, seed, strength_px, freq):
    """Displace sample coordinates by a low-frequency noise field."""
    n = field.shape[0]
    rng = np.random.default_rng(seed)
    wx = _value_noise(n, freq, rng) * 2.0 - 1.0
    wy = _value_noise(n, freq, rng) * 2.0 - 1.0
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float64)
    return _bilinear_sample(field, xs + wx * strength_px,
                            ys + wy * strength_px)


def _best_candidate_points(rng, count, margin, tries=32):
    """Spread `count` points over [margin, 1-margin]^2 without a lattice.

    Mitchell best-candidate: each new point is the one of `tries` random
    draws that is furthest from everything already placed. Uniform random
    placement clumps (that is what uniform means), and a jittered grid
    reads as a grid from the air — which matters here, because these
    become the map's massifs and a player crossing them will see the
    arrangement.
    """
    pts = []
    lo, hi = float(margin), 1.0 - float(margin)
    if hi <= lo:
        raise ValueError("massif margin {0} leaves no interior".format(margin))
    for _ in range(int(count)):
        cand = rng.uniform(lo, hi, size=(tries, 2))
        if not pts:
            pts.append(cand[0])
            continue
        placed = np.asarray(pts)
        d = np.sqrt(((cand[:, None, :] - placed[None, :, :]) ** 2)
                    .sum(axis=-1)).min(axis=1)
        pts.append(cand[int(np.argmax(d))])
    return np.asarray(pts, dtype=np.float64)


def _spanning_edges(pts):
    """Minimum spanning tree over the centres (Prim, O(k^2), k <= ~8).

    A tree, not every pair: k(k-1)/2 corridors would fill the map with
    ridge and leave no basins between the ranges. A spanning tree is the
    minimum that guarantees every massif is connected to every other by
    high ground — which is the traversability property being bought here,
    and it is why this is an MST rather than a chain or a ring.
    """
    k = len(pts)
    if k < 2:
        return []
    inside = [0]
    outside = list(range(1, k))
    edges = []
    while outside:
        best = None
        for i in inside:
            for j in outside:
                d = float(np.hypot(pts[i][0] - pts[j][0],
                                   pts[i][1] - pts[j][1]))
                if best is None or d < best[0]:
                    best = (d, i, j)
        edges.append((best[1], best[2]))
        inside.append(best[2])
        outside.remove(best[2])
    return edges


def _segment_distance(u, v, a, b):
    """Distance from every (u, v) to the segment a-b, in mask space."""
    abx, aby = b[0] - a[0], b[1] - a[1]
    length2 = abx * abx + aby * aby
    t = np.clip(((u - a[0]) * abx + (v - a[1]) * aby) / max(length2, 1e-12),
                0.0, 1.0)
    return np.hypot(u - (a[0] + t * abx), v - (a[1] + t * aby))


def _massif_mask(n, seed, freq, count, radius, radius_jitter, margin,
                 ridge_width, ridge_height, floor, blend_p, edge_taper,
                 edge_taper_floor):
    """Multi-centre massif mask with ridgelines, reaching the map edges.

    WHAT THIS REPLACED, AND WHY. The original was one radial falloff from
    the map centre: `smoothstep(1 - r / edge_falloff)`. At the default
    1.15 that is 0.047 at the edge midpoints and exactly 0 in the
    corners, so roughly a third of the map was multiplied to nothing. The
    hillshade showed it as a disc of mountains in a dead grey frame, and
    `terrain_erosion.composition` put a number on it: median local relief
    33 m in the outer 800 m against 198 m inside, an EDGE RATIO of 0.166,
    with 82.9% of the border cells flat.

    That is not a tuning problem. A single radial term cannot produce
    terrain at the edges at all — pushing `edge_falloff` up flattens the
    falloff everywhere and the map becomes uniform noise, which is the
    thing the mask existed to prevent. The structure has to change.

    WHAT IT DOES NOW, in three parts:

    1. CENTRES. `count` massif centres, best-candidate spread, placed in
       [margin, 1-margin] — a margin SMALLER than the massif radius on
       purpose, so the outermost ranges are cut by the map boundary and
       run off it rather than politely stopping short. That is what puts
       mountains on the border instead of a shoreline.

    2. RIDGELINES. The centres are joined by a minimum spanning tree, and
       each edge lays a corridor of raised ground (`ridge_height`, below
       the massif peaks so the corridors read as passes rather than as
       more summits). This is the traversability lever: connected high
       ground is what stops a multi-centre map from becoming several
       separate walkable islands with impassable basins between them.

    3. FLOOR. `floor` is the mask value everywhere else, so the "empty"
       ground still receives that fraction of the height field —
       foothills and rolling country, not a plain. Setting it to 0
       reproduces the old island's failure mode in a new shape.

    `edge_taper` is off by default and exists only for a world that
    deliberately wants a soft frame; it is the honest successor to
    `edge_falloff` and is NOT the way to fill the map.

    Returns (mask, info) — the centres and radii are reported because
    they are the map's structure, and next-step item 2 (cameras derived
    from terrain rather than constants) needs exactly this.
    """
    rng = np.random.default_rng(seed)
    broad = _value_noise(n, max(1, freq), rng)
    # np.ptp(a), not a.ptp() — the method form was removed in numpy 2.0
    # and this project runs 2.5.1.
    broad = (broad - broad.min()) / max(float(np.ptp(broad)), 1e-9)

    centres = _best_candidate_points(rng, count, margin)
    radii = radius * rng.uniform(1.0 - radius_jitter, 1.0 + radius_jitter,
                                 size=len(centres))
    weights = np.ones(len(centres), dtype=np.float64)
    if len(centres) > 1:
        # One dominant range and a set of lesser ones. Equal weights give
        # a map with no primary massif, which reads as undifferentiated
        # from the air and gives the player nothing to navigate by.
        weights[1:] = rng.uniform(0.70, 0.95, size=len(centres) - 1)

    axis = np.linspace(0.0, 1.0, n)
    u = axis[None, :]
    v = axis[:, None]

    # SOFT maximum, p-norm: (sum f^p)^(1/p). Neither of the obvious
    # combiners works. SUM saturates the middle of the map into one blob
    # — the island again, in a new shape. Plain MAX is C0-discontinuous
    # where two components cross, and the first preview showed exactly
    # that: the corridors surfaced through the massifs as smooth
    # lens-shaped blades with a hard rim, unmistakably geometric from
    # altitude. The p-norm tracks the max within a few percent where one
    # component dominates and rounds the seam where they meet.
    acc = np.zeros((n, n), dtype=np.float64)
    p = max(float(blend_p), 1.0)

    for (cx, cy), r, w in zip(centres, radii, weights):
        d = np.hypot(u - cx, v - cy)
        acc += np.power(
            w * _smoothstep(np.clip(1.0 - d / max(r, 1e-6), 0.0, 1.0)), p)

    edges = _spanning_edges(centres)
    for i, j in edges:
        d = _segment_distance(u, v, centres[i], centres[j])
        corridor = _smoothstep(np.clip(1.0 - d / max(ridge_width, 1e-6),
                                       0.0, 1.0))
        acc += np.power(ridge_height * corridor, p)

    shape = np.power(acc, 1.0 / p)

    # Break the geometry up. Without this the bumps and corridors are
    # visibly circles and lines from altitude.
    shape = np.clip(shape * (0.55 + 0.45 * broad), 0.0, 1.0)
    mask = floor + (1.0 - floor) * shape

    if edge_taper > 0.0:
        idx = np.minimum(np.arange(n), n - 1 - np.arange(n)) / max(n - 1, 1)
        t = _smoothstep(np.clip(np.minimum(idx[:, None], idx[None, :])
                                / max(edge_taper, 1e-6), 0.0, 1.0))
        mask = mask * (edge_taper_floor + (1.0 - edge_taper_floor) * t)

    info = {
        "centres": [(float(c[0]), float(c[1])) for c in centres],
        "radii": [float(r) for r in radii],
        "weights": [float(w) for w in weights],
        "edges": edges,
        "floor": float(floor),
    }
    return np.clip(mask, 0.0, 1.0), info


# -------------------------------------------------------------- erosion --

def _thermal_erosion(h, iterations, talus, rate):
    """Angle-of-repose erosion.

    Where the drop to a neighbour exceeds `talus`, move a fraction of the
    excess downhill. Applied over 4 directions per iteration. This is what
    produces scree faces and flat valley floors, and what caps the slope
    distribution so a slope threshold selects coherent faces rather than
    noise.
    """
    shifts = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for _ in range(iterations):
        for axis_shift in shifts:
            axis = 0 if axis_shift[0] else 1
            step = axis_shift[0] or axis_shift[1]
            lower = np.roll(h, -step, axis=axis)
            drop = h - lower
            move = np.where(drop > talus, (drop - talus) * rate, 0.0)
            # Do not let the wrapped edge exchange material across the map.
            if axis == 0:
                if step > 0:
                    move[-1, :] = 0.0
                else:
                    move[0, :] = 0.0
            else:
                if step > 0:
                    move[:, -1] = 0.0
                else:
                    move[:, 0] = 0.0
            h = h - move + np.roll(move, step, axis=axis)
    return h


def _box_blur(field, radius):
    """Separable box blur via cumulative sums — O(n^2) regardless of r."""
    if radius < 1:
        return field
    n = field.shape[0]
    pad = np.pad(field, radius, mode="edge")
    cs = np.cumsum(pad, axis=0)
    cs = np.vstack([np.zeros((1, cs.shape[1])), cs])
    horiz = (cs[2 * radius + 1:2 * radius + 1 + n, :]
             - cs[0:n, :]) / (2 * radius + 1)
    cs2 = np.cumsum(horiz, axis=1)
    cs2 = np.hstack([np.zeros((cs2.shape[0], 1)), cs2])
    return (cs2[:, 2 * radius + 1:2 * radius + 1 + n]
            - cs2[:, 0:n]) / (2 * radius + 1)


def _hydraulic_hint(h, strength, radius):
    """Deepen low ground using a blurred inverse-height flow proxy.

    Not a droplet simulation. Water pools low, so a blurred inverse of
    height approximates where flow concentrates; carving proportional to
    that (times local slope) deepens valleys and leaves ridges alone.
    """
    if strength <= 0.0:
        return h
    inv = h.max() - h
    flow = _box_blur(inv, radius)
    flow = (flow - flow.min()) / max(float(np.ptp(flow)), 1e-9)
    gy, gx = np.gradient(h)
    slope = np.hypot(gx, gy)
    slope = slope / max(slope.max(), 1e-9)
    return h - strength * flow * slope


# ------------------------------------------------------------------ png --

def _chunk(tag, payload):
    body = tag + payload
    return (struct.pack(">I", len(payload)) + body +
            struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def write_png16_grey(path, array):
    if array.dtype != np.uint16:
        raise ValueError("array must be uint16")
    height, width = array.shape
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
    if not recipe:
        return
    ls = recipe["landscape"]
    # SPACING COMES FROM THIS MAP'S RESOLUTION, NOT THE RECIPE'S.
    # `scale_xy_cm` is the spacing at the RECIPE's resolution. Generate a
    # preview at 1009 instead of 2017 and the same world span is covered
    # by half as many samples, so the real spacing doubles and every
    # slope here comes out about twice too steep — and the material
    # coverage printed below, which is what the layer bands get tuned
    # against, is wrong with it.
    #
    # This is lesson 19.2 recurring: `terrain_erosion.spacing_for` was
    # written FOR this defect and its docstring calls it "the trap this
    # exists for", the slope/traversability block fourteen lines further
    # down uses it — and this function, in the same file, was left
    # reading the recipe directly. Fixing a defect class at the site it
    # was found is exactly what CLAUDE.md non-negotiable 8 says not to
    # do.
    scale_xy_cm = terrain_erosion.spacing_for(
        array.shape[0], int(recipe["heightmap"]["resolution"]),
        float(ls["scale_xy_cm"]))
    z_scale_cm = float(ls["z_scale_cm"])
    height_m = (array.astype(np.float64) / UINT16_MAX) * (z_scale_cm / 100.0)
    gy, gx = np.gradient(height_m, scale_xy_cm / 100.0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    print("  terrain span     : {0:.0f} m across".format(
        (array.shape[0] - 1) * scale_xy_cm / 100.0))
    print("  height range     : {0:.1f} m .. {1:.1f} m".format(
        height_m.min(), height_m.max()))
    print("  slope percentiles: p50 {0:.1f}  p75 {1:.1f}  p90 {2:.1f}  "
          "p99 {3:.1f}  max {4:.1f}".format(
              *np.percentile(slope, [50, 75, 90, 99]), slope.max()))

    layers = recipe.get("material", {}).get("layers") or []
    if not layers:
        return
    print("  material coverage (first-match-wins):")
    unassigned = np.ones(array.shape, dtype=bool)
    for layer in layers:
        s_lo, s_hi = layer["slope_deg"]
        h_lo, h_hi = layer["height_m"]
        mask = (unassigned & (slope >= s_lo) & (slope <= s_hi) &
                (height_m >= h_lo) & (height_m <= h_hi))
        print("    {0:<8} {1:6.2f}%".format(
            layer["name"], 100.0 * mask.sum() / array.size))
        unassigned &= ~mask
    print("    {0:<8} {1:6.2f}%   (matched no layer)".format(
        "<none>", 100.0 * unassigned.sum() / array.size))


# ------------------------------------------------------------------ main --

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--resolution", type=int, default=1009)
    p.add_argument("--output", default=DEFAULT_OUTPUT)
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--octaves", type=int, default=9)
    p.add_argument("--base-freq", type=int, default=3)
    p.add_argument("--lacunarity", type=float, default=2.05)
    p.add_argument("--gain", type=float, default=0.52)
    p.add_argument("--ridge-sharpness", type=float, default=1.6,
                   help="Exponent on the ridge fold. Higher = sharper, "
                        "more knife-edged crests.")
    p.add_argument("--mass", type=float, default=0.55,
                   help="Blend weight of smooth fBm against ridged. 0 = "
                        "pure ridges (dramatic crests, no bulk); 1 = pure "
                        "rounded lumps. Around 0.5 gives mountains with "
                        "both mass and sharp crests.")
    p.add_argument("--lift", type=float, default=0.72,
                   help="Power curve on normalised height. <1 lifts "
                        "mid-tones so the map has high ground rather "
                        "than a dark plain with a few peaks.")
    p.add_argument("--warp", type=float, default=28.0,
                   help="Domain warp strength in pixels. 0 disables.")
    p.add_argument("--warp-freq", type=int, default=4)
    p.add_argument("--massif-freq", type=int, default=3)
    # --edge-falloff was REMOVED on 2026-08-02. It was a single radial
    # term from the map centre and it is what made the terrain an island;
    # no value of it can put mountains on the border. See _massif_mask.
    p.add_argument("--massif-count", type=int, default=4,
                   help="Number of massif centres. 1 reproduces a single "
                        "range; 4 gives a region with distinct massifs "
                        "and basins between them.")
    p.add_argument("--massif-radius", type=float, default=0.34,
                   help="Massif radius as a fraction of map width. 0.34 "
                        "is ~2.7 km on the 8.06 km map.")
    p.add_argument("--massif-radius-jitter", type=float, default=0.28,
                   help="Fractional spread on the radii, so the massifs "
                        "are not all the same size.")
    p.add_argument("--massif-margin", type=float, default=0.16,
                   help="Keep-out from the map border for CENTRES. Less "
                        "than --massif-radius on purpose: the outer "
                        "ranges then run off the edge instead of "
                        "stopping short of it.")
    p.add_argument("--ridge-width", type=float, default=0.15,
                   help="Half-width of the corridors joining the massifs, "
                        "as a fraction of map width (~1.2 km at 0.15). "
                        "Narrow corridors have a steep cross-slope of "
                        "their own, which drowns the noise and reads as "
                        "a smooth blade.")
    p.add_argument("--ridge-height", type=float, default=0.58,
                   help="Corridor mask height. Below the massif peaks so "
                        "the links read as passes, not more summits. 0 "
                        "disconnects the massifs.")
    p.add_argument("--massif-blend-p", type=float, default=6.0,
                   help="Exponent of the p-norm soft maximum that "
                        "combines massifs and corridors. Large p "
                        "approaches a hard max and reinstates the visible "
                        "seam; small p approaches a sum and blobs the "
                        "map.")
    p.add_argument("--massif-floor", type=float, default=0.30,
                   help="Mask value away from any massif or corridor. "
                        "This is what stops the rest of the map being a "
                        "dead plain; 0 restores the old island.")
    p.add_argument("--edge-taper", type=float, default=0.0,
                   help="Optional soft frame: fraction of the map width "
                        "over which the mask falls off at the border. 0 "
                        "(default) means terrain runs to the edge.")
    p.add_argument("--edge-taper-floor", type=float, default=0.35,
                   help="Mask multiplier AT the border when --edge-taper "
                        "is on.")
    p.add_argument("--talus", type=float, default=0.0022,
                   help="Angle of repose, in normalised height per "
                        "pixel. Lower = more erosion, gentler faces.")
    p.add_argument("--erosion-iters", type=int, default=140)
    p.add_argument("--erosion-rate", type=float, default=0.25)
    p.add_argument("--hydraulic", type=float, default=0.05,
                   help="Valley-carving strength of the cheap BLUR proxy. "
                        "0 disables. Kept because it costs nothing and "
                        "biases low ground before the droplets run; it is "
                        "no longer the thing that makes channels.")
    p.add_argument("--hydraulic-radius", type=int, default=9)
    p.add_argument("--droplets", type=int, default=250000,
                   help="Particle hydraulic erosion. THIS is what carves "
                        "gullies and couloirs -- the blur proxy above "
                        "cannot, because it deepens low ground uniformly "
                        "and a channel exists precisely because water "
                        "concentrated. 0 disables.")
    p.add_argument("--droplet-lifetime", type=int, default=48)
    p.add_argument("--droplet-inertia", type=float, default=0.05)
    p.add_argument("--droplet-capacity", type=float, default=8.0)
    p.add_argument("--droplet-erode", type=float, default=0.30)
    p.add_argument("--droplet-deposit", type=float, default=0.30)
    p.add_argument("--droplet-smooth", type=float, default=0.6,
                   help="Blur applied after the droplet pass. Per-texel "
                        "scatter leaves one-cell channels the 4 m grid "
                        "cannot represent.")
    p.add_argument("--despike", type=float, default=4.0,
                   help="Replace cells deviating more than this many "
                        "sigma from their 3x3 median. Fixes the dark "
                        "ridgeline triangles. 0 disables.")
    p.add_argument("--no-aux", action="store_true",
                   help="Skip writing the flow, deposition and hillshade "
                        "maps. They are inputs to the Priority 2 material "
                        "work, so the default is to write them.")
    p.add_argument("--relief", type=float, default=0.48,
                   help="Fraction of the 16-bit range used, and therefore "
                        "the world's total vertical relief against the "
                        "recipe's z_scale_cm. 0.48 of 2560 m = 1229 m "
                        "over the 8.06 km map. THIS IS A TRAVERSABILITY "
                        "CONTROL, not a cosmetic one -- see below. Lowered "
                        "from 0.62 on 2026-08-02 when per-octave rotation "
                        "made the noise isotropic: decorrelating the "
                        "octaves removed their interference and left the "
                        "terrain genuinely rougher (p50 24.5 -> 31.6 deg), "
                        "so the world gate refused it at 0.62.")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    n = args.resolution
    out_path = os.path.abspath(args.output)
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("Output    : {0}".format(out_path))
    print("")

    if not _norm(out_path).startswith(_norm(TERRAIN_DIR) + os.sep):
        print("REFUSE: output must be inside {0}".format(TERRAIN_DIR))
        return 1
    if not 0.0 < args.relief <= 1.0:
        print("REFUSE: --relief must be in (0, 1].")
        return 1

    # Range checks written as `not (lo <= x <= hi)` on purpose: NaN fails
    # every comparison, so the negated form REFUSES it, while the direct
    # form `if x <= 0: refuse` lets NaN straight through. That exact
    # defect has been found three times in this repo (lesson 2.9), and
    # `--massif-floor nan` would otherwise produce an all-NaN heightmap
    # that writes, verifies as a legal PNG, and imports as flat ground.
    #
    # EVERY float and int argument is listed, not only the ones added
    # with the massif mask. The first version of this block covered the
    # ten new flags and stopped there — which is precisely the thing
    # CLAUDE.md non-negotiable 8 forbids ("when you find a defect class,
    # grep for it everywhere immediately"), and the reason lesson 2.9
    # records the same bug being fixed three times in three files. The
    # pre-existing arguments were exactly as unguarded as the new ones:
    # `--talus nan` propagates through thermal erosion into every cell.
    numeric_bounds = (
        # shaping — pre-existing, previously unchecked
        ("--seed", args.seed, -(2 ** 63), 2 ** 63 - 1),
        ("--octaves", args.octaves, 1, 24),
        ("--base-freq", args.base_freq, 1, 4096),
        ("--lacunarity", args.lacunarity, 1.0, 8.0),
        ("--gain", args.gain, 0.01, 1.0),
        ("--ridge-sharpness", args.ridge_sharpness, 0.05, 16.0),
        ("--mass", args.mass, 0.0, 1.0),
        ("--lift", args.lift, 0.05, 8.0),
        ("--warp", args.warp, 0.0, 1024.0),
        ("--warp-freq", args.warp_freq, 1, 4096),
        ("--massif-freq", args.massif_freq, 1, 4096),
        # erosion — pre-existing, previously unchecked
        ("--talus", args.talus, 0.0, 1.0),
        ("--erosion-iters", args.erosion_iters, 0, 100000),
        ("--erosion-rate", args.erosion_rate, 0.0, 1.0),
        ("--hydraulic", args.hydraulic, 0.0, 1.0),
        ("--hydraulic-radius", args.hydraulic_radius, 0, 4096),
        ("--droplets", args.droplets, 0, 100000000),
        ("--droplet-lifetime", args.droplet_lifetime, 1, 4096),
        ("--droplet-inertia", args.droplet_inertia, 0.0, 1.0),
        ("--droplet-capacity", args.droplet_capacity, 0.0, 1024.0),
        ("--droplet-erode", args.droplet_erode, 0.0, 1.0),
        ("--droplet-deposit", args.droplet_deposit, 0.0, 1.0),
        ("--droplet-smooth", args.droplet_smooth, 0.0, 64.0),
        ("--despike", args.despike, 0.0, 1024.0),
        # massif mask — added with this feature
        ("--massif-count", args.massif_count, 1, 64),
        ("--massif-radius", args.massif_radius, 0.01, 4.0),
        ("--massif-radius-jitter", args.massif_radius_jitter, 0.0, 0.95),
        ("--massif-margin", args.massif_margin, 0.0, 0.49),
        ("--ridge-width", args.ridge_width, 0.001, 1.0),
        ("--ridge-height", args.ridge_height, 0.0, 1.0),
        ("--massif-floor", args.massif_floor, 0.0, 0.99),
        ("--massif-blend-p", args.massif_blend_p, 1.0, 64.0),
        ("--edge-taper", args.edge_taper, 0.0, 0.5),
        ("--edge-taper-floor", args.edge_taper_floor, 0.0, 1.0),
    )
    for flag, value, lo_b, hi_b in numeric_bounds:
        if not lo_b <= value <= hi_b:
            print("REFUSE: {0} must be in [{1}, {2}]; got {3!r}."
                  .format(flag, lo_b, hi_b, value))
            return 1
    if args.massif_margin >= args.massif_radius:
        # Not fatal — a world of separated hills is a legitimate thing to
        # ask for — but it is the configuration that reproduces the
        # island, so it does not get to happen silently.
        print("WARNING: --massif-margin {0} >= --massif-radius {1}, so no "
              "massif reaches the map border. Terrain will stop short of "
              "the edges.".format(args.massif_margin, args.massif_radius))

    facs = _landscape_factorisations(n)
    if not facs:
        print("REFUSE: {0} is not a legal Unreal landscape resolution."
              .format(n))
        return 2
    print("Resolution {0} is legal: {1}".format(
        n, ", ".join("{0}*{1}*{2}+1".format(*f) for f in facs)))
    print("")

    recipe = None
    _recipe_abs = os.path.abspath(args.recipe)
    if os.path.isfile(_recipe_abs):
        try:
            with open(_recipe_abs, "r", encoding="utf-8") as fh:
                recipe = json.load(fh)
        except (OSError, ValueError) as exc:
            # A recipe that EXISTS but cannot be parsed must FAIL, not
            # warn-and-continue (Pass 3 2026-09-16 F4): the file was
            # asked for and cannot be honoured, and continuing skips the
            # `if recipe:` world-gate block entirely — main would fall to
            # exit 0 ("written and verified") with the gate never run,
            # reproducing the exact 2026-08-02 ship-a-broken-world hole
            # the gate exists to close. Refuse BEFORE writing.
            print("REFUSE: --recipe {0} exists but does not parse: {1}. "
                  "The world gate cannot run against it; refusing rather "
                  "than writing an unverified heightmap."
                  .format(_recipe_abs, exc))
            return 1
    else:
        # No recipe file at all: the gate is SKIPPED, and that skip is
        # LOUD (rule 13) — a silent skip is how the 2026-08-02 world
        # shipped ungated.
        print("NOTE: no recipe at {0} — the `world` target gate will NOT "
              "be evaluated for this run.".format(_recipe_abs))

    print("Generating {0}x{0} (seed {1}) ...".format(n, args.seed))
    print("  ridged multifractal, {0} octaves, sharpness {1}".format(
        args.octaves, args.ridge_sharpness))
    ridges = _ridged_fbm(n, args.seed, args.octaves, args.base_freq,
                         args.lacunarity, args.gain, args.ridge_sharpness)
    if args.mass > 0.0:
        print("  blending smooth fBm for mass: {0}".format(args.mass))
        base = _smooth_fbm(n, args.seed + 4441, args.octaves,
                           args.base_freq, args.lacunarity, 0.5)
        base = (base - base.min()) / max(float(np.ptp(base)), 1e-9)
        ridges = (ridges - ridges.min()) / max(float(np.ptp(ridges)), 1e-9)
        field = base * args.mass + ridges * (1.0 - args.mass)
    else:
        field = ridges

    if args.lift != 1.0:
        # Power curve < 1 lifts mid-tones, so the histogram stops being
        # bottom-heavy and the terrain gains high ground instead of being
        # a dark plain with a few bright peaks.
        field = np.power(np.clip(
            (field - field.min()) / max(float(np.ptp(field)), 1e-9),
            0.0, 1.0), args.lift)

    if args.warp > 0:
        print("  domain warp {0} px".format(args.warp))
        field = _domain_warp(field, args.seed + 977, args.warp,
                             args.warp_freq)

    print("  massif mask: {0} centres, radius {1} +/-{2:.0%}, corridors "
          "{3} HALF-width (full footprint {6}) at {4}, floor {5}".format(
              args.massif_count, args.massif_radius,
              args.massif_radius_jitter, args.ridge_width,
              args.ridge_height, args.massif_floor,
              2.0 * args.ridge_width))
    mask, mask_info = _massif_mask(
        n, args.seed + 1213, args.massif_freq, args.massif_count,
        args.massif_radius, args.massif_radius_jitter, args.massif_margin,
        args.ridge_width, args.ridge_height, args.massif_floor,
        args.massif_blend_p, args.edge_taper, args.edge_taper_floor)
    field = field * mask
    span_m = (n - 1) * (0.0 if not recipe else terrain_erosion.spacing_for(
        n, int(recipe["heightmap"]["resolution"]),
        float(recipe["landscape"]["scale_xy_cm"]))) / 100.0
    for i, ((cx, cy), r, w) in enumerate(zip(
            mask_info["centres"], mask_info["radii"], mask_info["weights"])):
        # Printed in metres as well as normalised units: item 2 of the
        # handoff derives camera framing from these, and a fraction of
        # map width is not something a camera can be pointed at.
        extra = ("" if span_m <= 0.0 else
                 "  = ({0:.0f}, {1:.0f}) m, r {2:.0f} m".format(
                     cx * span_m, cy * span_m, r * span_m))
        print("    centre {0}: ({1:.3f}, {2:.3f}) r {3:.3f} weight "
              "{4:.2f}{5}".format(i, cx, cy, r, w, extra))
    print("    corridors: {0}".format(
        ", ".join("{0}-{1}".format(i, j) for i, j in mask_info["edges"])
        or "none"))
    print("    mask covers: {0:.1f}% of cells above 0.5, {1:.1f}% above "
          "0.8, minimum {2:.2f}".format(
              100.0 * float((mask > 0.5).mean()),
              100.0 * float((mask > 0.8).mean()), float(mask.min())))

    lo, hi = float(field.min()), float(field.max())
    field = (field - lo) / max(hi - lo, 1e-9)

    print("  thermal erosion: {0} iterations, talus {1}".format(
        args.erosion_iters, args.talus))
    field = _thermal_erosion(field, args.erosion_iters, args.talus,
                             args.erosion_rate)

    if args.hydraulic > 0:
        print("  hydraulic hint (blur proxy): strength {0}, radius {1}"
              .format(args.hydraulic, args.hydraulic_radius))
        field = _hydraulic_hint(field, args.hydraulic,
                                args.hydraulic_radius)

    flow = depo = None
    if args.droplets > 0:
        print("  hydraulic erosion: {0} droplets x {1} steps ...".format(
            args.droplets, args.droplet_lifetime))
        t0 = time.time()
        # Its own RNG stream, derived from the seed, so changing the
        # droplet count cannot alter the noise field above it.
        drng = np.random.RandomState((args.seed + 8081) % (2 ** 32))
        field, flow, depo = terrain_erosion.hydraulic_droplets(
            field, drng, count=args.droplets,
            lifetime=args.droplet_lifetime, inertia=args.droplet_inertia,
            capacity_factor=args.droplet_capacity,
            erode_rate=args.droplet_erode,
            deposit_rate=args.droplet_deposit,
            smooth=args.droplet_smooth)
        print("    took {0:.1f}s; flow touched {1:.1f}% of cells, "
              "deposition {2:.1f}%".format(
                  time.time() - t0,
                  100.0 * float((flow > 0).mean()),
                  100.0 * float((depo > 0).mean())))

    if args.despike > 0:
        field, nspikes = terrain_erosion.despike(field, args.despike)
        print("  de-spike: replaced {0} cells ({1:.4f}% of the map) beyond "
              "{2} sigma".format(nspikes, 100.0 * nspikes / field.size,
                                 args.despike))

    lo, hi = float(field.min()), float(field.max())
    field = (field - lo) / max(hi - lo, 1e-9)
    data = np.rint(field * args.relief * UINT16_MAX).astype(np.uint16)

    os.makedirs(TERRAIN_DIR, exist_ok=True)
    write_png16_grey(out_path, data)
    w, h, depth, colour = read_png_header(out_path)

    print("")
    print("Written: {0}".format(out_path))
    print("  dimensions : {0} x {1}".format(w, h))
    print("  bit depth  : {0}".format(depth))
    print("  colour type: {0} (0 = greyscale)".format(colour))
    print("  file size  : {0:.2f} MiB".format(
        os.path.getsize(out_path) / 1048576.0))
    if (w, h, depth, colour) != (n, n, 16, 0):
        print("ERROR: written file does not match the requested format.")
        return 1

    # ---- auxiliary maps -------------------------------------------
    # Written as 16-bit greyscale beside the heightmap, through the SAME
    # containment check, because Priority 2 of the aesthetic brief
    # consumes them: flow multiplies into rock as water staining,
    # deposition as scree lightening. The hillshade is for a human (or
    # me) to look at before any of it reaches the engine.
    if not args.no_aux:
        print("")
        print("--- auxiliary maps ---")
        # Aux names derive from the OUTPUT's stem, not a constant:
        # hardcoded alpine_* names meant any non-alpine caller silently
        # clobbered the alpine world's committed aux maps (measured
        # 2026-09-02, forge base gen; restored from git). The default
        # output still yields the historical alpine_* names.
        stem = os.path.splitext(os.path.basename(args.output))[0]
        stem = stem[:-len("_heightmap")] if stem.endswith("_heightmap") \
            else stem
        aux = []
        if flow is not None:
            # Flow is extremely long-tailed — a few channel cells carry
            # orders of magnitude more water than the hillsides. log1p
            # first or the PNG is black with a handful of white threads.
            aux.append((stem + "_flow.png", np.log1p(flow)))
            aux.append((stem + "_deposition.png", np.log1p(depo)))
        aux.append((stem + "_hillshade.png",
                    terrain_erosion.hillshade(data.astype(np.float64))))
        for name, arr in aux:
            path = os.path.join(TERRAIN_DIR, name)
            if not _norm(path).startswith(_norm(TERRAIN_DIR) + os.sep):
                print("REFUSE: {0} escapes terrain/".format(name))
                return 1
            lo2, hi2 = float(arr.min()), float(arr.max())
            u16 = np.rint((arr - lo2) / max(hi2 - lo2, 1e-9)
                          * UINT16_MAX).astype(np.uint16)
            write_png16_grey(path, u16)
            print("  {0:<26} range {1:.4g}..{2:.4g}".format(name, lo2, hi2))

    print("")
    print("--- relief analysis ---")
    try:
        report_relief(data, recipe)
    except (KeyError, TypeError, ValueError) as exc:
        print("WARNING: relief analysis failed: {0}".format(exc))

    # ---- slope distribution ---------------------------------------
    # The recipe's layer thresholds are chosen against this distribution.
    # The 2026-08-01 all-snow render happened because thresholds were
    # tuned against a measurement nothing downstream actually made, so
    # the generator now prints the distribution it just produced.
    if recipe:
        try:
            ls = recipe["landscape"]
            # Spacing must come from THIS map's resolution, not the
            # recipe's — see terrain_erosion.spacing_for.
            spacing = terrain_erosion.spacing_for(
                n, int(recipe["heightmap"]["resolution"]),
                float(ls["scale_xy_cm"]))
            if abs(spacing - float(ls["scale_xy_cm"])) > 1e-6:
                print("  (preview at {0}, so cell spacing is {1:.1f} cm, "
                      "not the recipe's {2:.1f} — slopes below are for "
                      "THIS map)".format(n, spacing,
                                         float(ls["scale_xy_cm"])))
            deg = terrain_erosion.slope_degrees(
                data, spacing, float(ls["z_scale_cm"]))
            pct = [50, 75, 90, 95, 99]
            vals = np.percentile(deg, pct)
            print("")
            print("--- slope distribution (deg) ---")
            print("  " + "  ".join("p{0}={1:.1f}".format(p, v)
                                   for p, v in zip(pct, vals)))
            print("  mean {0:.1f}   max {1:.1f}".format(
                float(deg.mean()), float(deg.max())))
            # ---- TRAVERSABILITY GATE ---------------------------------
            # The project's purpose is a world to be EXPLORED on foot, so
            # the first question about a heightmap is not how dramatic it
            # looks but whether a character can move through it. UE's own
            # walkable limit is 44.765 deg (CharacterMovementComponent
            # CDO, read live) — steeper than that is not terrain, it is
            # geometry the player slides off.
            trav = terrain_erosion.traversability(deg)
            print("")
            print("--- traversability, per movement mode ---")
            print("  {0:<7} {1:>9} {2:>11} {3:>9} {4:>8}".format(
                "mode", "crossable", "largest", "in 1 piece", "regions"))
            for mname in ("walk", "mount", "climb", "air"):
                t = trav.get(mname)
                if not t:
                    continue
                print("  {0:<7} {1:8.1f}% {2:10.1f}% {3:8.1f}% {4:8d}"
                      .format(mname, 100.0 * t["frac"],
                              100.0 * t["largest_frac"],
                              100.0 * t["reachable_frac"], t["regions"]))
            wk = trav.get("walk", {})
            if wk and wk.get("reachable_frac", 1.0) < 0.8:
                print("  NOTE: walkable ground is fragmented. That is not "
                      "automatically wrong — terrain whose walk regions "
                      "are broken but whose climb region is whole is "
                      "terrain that rewards gaining a traversal ability. "
                      "It is only a fault if foot travel is meant to be "
                      "the primary mode here.")

            # ---- COMPOSITION GATE ------------------------------------
            # Traversability cannot see an empty map: a billiard table is
            # 100% crossable in one piece. This is the companion measure —
            # how much of the map carries relief, and whether it reaches
            # the border. The pre-2026-08-02 radial mask scored 0.166 on
            # the edge ratio with 82.9% of border cells flat, and no
            # other number in the pipeline moved at all.
            comp = terrain_erosion.composition(
                data, spacing, float(ls["z_scale_cm"]))
            print("")
            print("--- composition (local relief over {0:.0f} m) ---".format(
                comp["window_m"]))
            print("  flat (<{0:.0f} m relief): whole {1:.1f}%   outer "
                  "{2:.0f} m {3:.1f}%   interior {4:.1f}%   border "
                  "{5:.1f}%".format(
                      comp["flat_relief_m"], 100.0 * comp["flat_frac"],
                      comp["edge_band_m"], 100.0 * comp["edge_flat_frac"],
                      100.0 * comp["core_flat_frac"],
                      100.0 * comp["border_flat_frac"]))
            print("  median relief: edge {0:.0f} m   interior {1:.0f} m   "
                  "EDGE RATIO {2:.3f}   (1.0 = border as alive as the "
                  "middle)".format(comp["edge_relief_m"],
                                   comp["core_relief_m"],
                                   comp["edge_ratio"]))
            # THE GATE KEYS ON FLATNESS, NOT ON THE EDGE RATIO, and the
            # distinction was learned from the first measurement rather
            # than assumed. A low edge ratio means only that the
            # outskirts are GENTLER than the peaks, which is what
            # foothills are and is not a defect. The island's defect was
            # that its border was DEAD: 82.9% of border cells below 20 m
            # of relief. Those two came apart as soon as there were
            # numbers for both — the replacement mask scored 0.0% flat at
            # an edge ratio of 0.615, and a later variant scored 0.0%
            # flat at a much lower ratio while being better terrain.
            if comp["border_flat_frac"] > 0.20:
                print("  NOTE: {0:.0f}% of the MAP BORDER carries less "
                      "than {1:.0f} m of relief. That is an ISLAND — a "
                      "world in the middle of a dead frame — and it is "
                      "only correct if this world is meant to be one."
                      .format(100.0 * comp["border_flat_frac"],
                              comp["flat_relief_m"]))
            elif comp["edge_ratio"] < 0.35:
                print("  (the outskirts are much gentler than the "
                      "interior, but they are not dead: foothills, not "
                      "an island)")

            lm = terrain_erosion.landmarks(
                data, spacing, float(ls["z_scale_cm"]))
            print("")
            print("--- navigation landmarks (for air / long-range) ---")
            print("  {0} peaks over 120 m prominence across {1:.1f} km "
                  "square = {2:.1f} per 100 km2".format(
                      lm["count"], lm["span_km"], lm["per_100km2"]))
            print("  greatest local prominence {0:.0f} m".format(
                lm["max_prominence_m"]))

            for layer in (recipe.get("material") or {}).get("layers") or []:
                lo_d, hi_d = layer.get("slope_deg", [None, None])[:2]
                if lo_d is None:
                    continue
                frac = float(((deg >= lo_d) & (deg <= hi_d)).mean())
                print("  {0:<8} slope band {1}..{2} deg covers {3:.1f}% "
                      "of cells".format(layer.get("name"), lo_d, hi_d,
                                        100.0 * frac))

            world_failures = check_world_targets(recipe, trav, comp)
        except (KeyError, TypeError, ValueError) as exc:
            print("WARNING: slope analysis failed: {0}".format(exc))
            # The gate could not be evaluated. That is not a pass — an
            # analysis that failed to run has proved nothing about the
            # world (lesson 2.10), and this function's return value is
            # what a caller uses to decide whether to push.
            world_failures = ["the analysis that evaluates world targets "
                              "did not complete: {0}".format(exc)]
        if world_failures:
            print("")
            print("=" * 66)
            print("REFUSED: this world misses the targets its own recipe")
            print("declares in `world`. The heightmap was WRITTEN — the")
            print("file on disk is real and inspectable — but it should")
            print("not be pushed.")
            for f in world_failures:
                print("  - {0}".format(f))
            print("=" * 66)
            return 3
    return 0


def check_world_targets(recipe, trav, comp):
    """Schema v1.5 `world` — refuse a terrain that misses its own target.

    Returns a list of failure strings; empty means pass, or means the
    recipe declared no targets.

    WHY THIS IS THE POINT OF v1.5. Every measurement this generator
    prints is advisory. The traversability table has deliberately never
    carried an opinion about WHICH mode matters, because baking
    "walkable" in as though it were physics would quietly make every
    future world a walking world. The cost of that neutrality is that a
    world can miss its design intent and still ship, with the numbers
    printed directly above it — which is precisely what happened on
    2026-08-02, when mount-in-one-piece fell 84.9% -> 22.1% and the run
    exited 0.

    `world` is where the intent is stated, per recipe, so the refusal
    can be specific instead of universal.
    """
    w = (recipe or {}).get("world")
    if not isinstance(w, dict):
        return []
    mode = w.get("primary_movement_mode")
    t = (trav or {}).get(mode)
    if t is None:
        return ["world.primary_movement_mode is {0!r}, which the "
                "traversability table does not report — the recipe and "
                "terrain_erosion.MOVEMENT_PROFILES disagree".format(mode)]

    out = []
    want = w.get("min_crossable_frac")
    if want is not None and t["frac"] < want:
        out.append("{0} crossable {1:.1%} < required {2:.1%}".format(
            mode, t["frac"], want))
    want = w.get("min_connected_frac")
    if want is not None and t["reachable_frac"] < want:
        out.append("{0} crossable ground in ONE PIECE {1:.1%} < required "
                   "{2:.1%} ({3} separate regions)".format(
                       mode, t["reachable_frac"], want, t["regions"]))
    want = w.get("max_border_flat_frac")
    if want is not None and comp["border_flat_frac"] > want:
        out.append("map border flat {0:.1%} > permitted {1:.1%} — this is "
                   "the ISLAND gate, and it is what stops the connectivity "
                   "target above being satisfied by an empty map".format(
                       comp["border_flat_frac"], want))
    return out


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
