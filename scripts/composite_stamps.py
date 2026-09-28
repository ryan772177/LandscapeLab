"""composite_stamps.py — blend StampIT terrain FEATURES into a base heightmap.

OFFLINE. Touches no editor, imports no `unreal`, writes exactly two files
(the composited PNG and its provenance sidecar) and never the base.

WHY THIS EXISTS
---------------
`terrain/stampit_catalogue.json` holds 52 StampIT maps, all catalogued as
`category: "STAMP"`. RECIPES.md R1's catalogue spec says what that means:

    STAMP  — a terrain FEATURE (ridge, canyon, crater). Composited INTO a
             base heightmap before import; NEVER imported alone.

There was no such compositing step. This is it.

MEASURED FACTS THIS SCRIPT IS BUILT ON (not conventions, not defaults)
---------------------------------------------------------------------
1. A StampIT map is a FULL 0..65535 FIELD, NOT A DELTA. All 52 catalogue
   entries report `relief_stats.min == 0` and `max >= 65534`. So a value
   of 0 in the stamp is "the bottom of the stamp's own range", which is
   not the same as "no change". `amplitude_m` says how many metres the
   stamp's range spans and `datum`/`anchor_m` say where it is pinned.
   Nothing here infers either.

2. PIXEL <-> WORLD MAPPING, read out of this project's own placement code
   rather than assumed: `scripts/place_foliage.py:192, 213, 234-236`
   computes instance world positions as

       world_x_m = column_index * spacing_m + location_cm[0] / 100
       world_y_m = row_index    * spacing_m + location_cm[1] / 100

   so **array COLUMN is world X and array ROW is world Y**. This script
   uses that exact mapping. Transposing it would place every stamp at the
   mirror of where the recipe says, and every downstream check would
   agree with the mistake because they all read the same file.

3. THE BASE HAS HEADROOM, BUT NOT UNLIMITED HEADROOM. Measured on
   `terrain/alpine_heightmap.png` 2026-08-02: min 0, max 31457 of 65535
   (48.0% of range), i.e. 0.0 m .. 1228.8 m against a `z_scale_cm` of
   256000. An ADD that pushes any pixel past 65535 is REFUSED, never
   wrapped — see OVERFLOW below.

THE FALLOFF MASK (exact)
------------------------
Every stamp is a square image. Dropped in raw it leaves a rectangular
seam. The mask, in stamp-local normalised coordinates `(u, v)` where the
stamp spans [-1, 1] in both axes:

    r = max(|u|, |v|)          falloff_shape "chebyshev"
    r = sqrt(u*u + v*v)        falloff_shape "euclidean"

    t    = clamp((1 - r) / falloff, 0, 1)
    mask = t * t * (3 - 2 * t)  * opacity           <- smoothstep

`falloff` is the fraction of the stamp's HALF-WIDTH over which the mask
ramps 1 -> 0. `falloff = 0.35` therefore holds mask == 1 over the inner
65% and feathers across the outer 35%.

**Smoothstep, not linear, and that is a correctness choice not a taste
one.** A linear ramp is C0 but not C1: its derivative jumps at r = 1-f
and again at r = 1. A landscape's shading reads the SLOPE, so a
derivative discontinuity draws a visible crease line on the terrain even
though the height field is continuous. Smoothstep's derivative is zero at
both ends, so slope is continuous across the whole seam and no crease
appears. `_smoothstep` in `make_alpine_terrain.py:129` is the same
polynomial, used for the same reason.

`chebyshev` keeps the whole stamp and feathers toward its square edge.
`euclidean` inscribes a circle and discards the corners (21.5% of area).
Neither is a default: the recipe states which, per placement.

BLEND MODES (exact)
-------------------
`H` is the base surface in metres, heightmap-zero-relative (schema.md
"Height datum"). `s` is the resampled stamp in 0..1. Then:

    ADD     target = H + (s - D) * amplitude_m      D from `datum`
    MAX     target = max(H, anchor_m + s * amplitude_m)
    MIN     target = min(H, anchor_m + s * amplitude_m)
    MASKED  target =     anchor_m + s * amplitude_m

and EVERY mode is applied through the mask identically:

    H' = H + mask * (target - H)

That last line is the whole reason the mask works for MAX/MIN/MASKED as
well as ADD: at mask == 0 every mode is exactly the identity. A naive
`H = np.maximum(H, stamp)` cannot be feathered at all and would leave the
rectangular seam this script exists to avoid.

`D` (ADD only) is computed over the pixels where mask > 0 — the only
pixels that contribute — as zero / min / mean / median of `s` there.

IDEMPOTENCE
-----------
Hard pipeline rule 3. Three independent guards, because the failure
(stamps accumulating silently on every re-run) leaves no error:

  a. The compositor ALWAYS reads `stamps.base` and ALWAYS writes
     `stamps.output`. It never reads its own output.
  b. `_validate_stamps` refuses `base == output` and refuses
     `output == heightmap.source` at the SCHEMA level, so the accumulating
     configuration is unrepresentable rather than merely rejected
     (CLAUDE.md non-negotiable 3).
  c. SELF-INGESTION SWEEP: every `*.stamps.json` sidecar in the output's
     directory is read, and if the base's SHA-256 equals any recorded
     `output_sha256` the run REFUSES. That catches someone re-pointing
     `stamps.base` at a previous output, which (a) and (b) cannot see.

There is no RNG anywhere in this file. Same recipe + same base bytes =>
same output bytes; `--selftest` proves it by compositing twice in-process
and comparing the arrays, and the sidecar records the output hash so a
later run can compare across processes with a different instrument.

OVERFLOW
--------
Arithmetic is float64 throughout. The cast to uint16 happens ONCE, after
an explicit clip, so a wrap is unrepresentable — `np.uint16(70000)` would
silently become 4464 and nothing would report it.

Order of checks matters and is deliberate:
  1. `np.isfinite` FIRST. NaN defeats every comparison (`nan > x` is
     False), so a range check run first would PASS on NaN. This is
     CLAUDE.md non-negotiable 4's defect class, at a new site.
  2. Then the 0..65535 range. Out of range REFUSES (exit 4) and names the
     offending pixel count and extremes. `--allow-clamp` clamps instead
     and reports how many pixels and how much height were lost.

DOWNSTREAM — READ THIS BEFORE ADOPTING AN OUTPUT
------------------------------------------------
A composited heightmap is NOT a drop-in replacement. 160,448 conifer
instances hold Z values baked from the CURRENT terrain, and
`terrain/alpine_flow.png` is derived from it. See the ADOPTION block this
script prints, and RECIPES.md R-STAMP ORDERED STEPS.

Exit codes:
  0  composited (or dry run, or selftest passed)
  1  usage / unexpected error
  2  recipe invalid, or an input file missing or malformed
  3  stamp identity failure (catalogue miss, or file bytes != recorded hash)
  4  REFUSED: non-finite or out of 16-bit range (never wrapped)
  5  REFUSED: idempotence guard — the base is a previous output
  6  REFUSED: a placement lands off-map, or is edge-clipped with
     `allow_edge_clip: false`
  7  selftest failed
"""

from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import math
import os
import sys
import zlib

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap                # noqa: E402 — REPO_ROOT, shared, never re-derived
import import_heightmap as ih   # noqa: E402 — the shared recipe validator
import make_alpine_terrain as mat  # noqa: E402 — write_png16_grey, one PNG writer
import resource_guard           # noqa: E402 — R10 banner

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

UINT16_MAX = 65535.0

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_INPUT = 2
EXIT_IDENTITY = 3
EXIT_RANGE = 4
EXIT_IDEMPOTENCE = 5
EXIT_FOOTPRINT = 6
EXIT_SELFTEST = 7


class Refuse(Exception):
    """A refusal with an exit code. Never a silent fallback."""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code


# ------------------------------------------------------------------ util --

def _inside_repo(path):
    root = os.path.normcase(os.path.abspath(REPO_ROOT))
    p = os.path.normcase(os.path.abspath(path))
    return p == root or p.startswith(root + os.sep)


def _resolve(rel, label):
    path = os.path.abspath(os.path.join(REPO_ROOT, rel))
    if not _inside_repo(path):
        raise Refuse(EXIT_INPUT,
                     "{0} escapes REPO_ROOT: {1}".format(label, path))
    return path


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _canonical_sha256(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")).hexdigest()


def read_png16_square(path, label):
    """Load a 16-bit single-channel square PNG, or refuse saying why.

    R11: 16-bit greyscale, NO ALPHA. A 16-bit PNG *with* alpha is the
    exact configuration that made the grass invisible for two sessions,
    and PIL reports it as a different mode rather than erroring, so the
    mode is checked by name and the refusal quotes what it actually saw.
    """
    if not os.path.isfile(path):
        raise Refuse(EXIT_INPUT, "{0} not found: {1}".format(label, path))
    with Image.open(path) as im:
        mode, size = im.mode, im.size
        if mode not in ("I;16", "I;16B", "I;16L", "I"):
            raise Refuse(EXIT_INPUT,
                         "{0} is PIL mode {1!r}; a heightmap must be 16-bit "
                         "single channel with no alpha (R11). Refusing "
                         "rather than converting: a mode this script did "
                         "not expect means the file is not what the recipe "
                         "thinks it is.".format(label, mode))
        arr = np.asarray(im)
    if arr.ndim != 2:
        raise Refuse(EXIT_INPUT, "{0} has shape {1}; expected 2-D"
                     .format(label, arr.shape))
    if size[0] != size[1]:
        raise Refuse(EXIT_INPUT, "{0} is {1}x{2}; expected square"
                     .format(label, size[0], size[1]))
    return arr.astype(np.uint16, copy=False)


def _value_noise(u, v, scale, seed, grid=64):
    """Deterministic smooth value noise in [-1, 1], sampled at (u, v).

    Value noise on a periodic `grid` x `grid` lattice with a SMOOTHSTEP
    fade, not a linear one. Linear interpolation is C0 but not C1, and
    its derivative jumps on every lattice line — which would draw a faint
    rectangular grid into the falloff and replace one geometric
    fingerprint with a worse one. Same argument as the falloff mask
    itself: terrain shading reads the SLOPE.

    Determinism is a hard requirement, not a nicety: `composite_stamps`
    must be idempotent (pipeline rule 3), so the noise is seeded from the
    placement's stamp hash and id and never from the clock or from
    `np.random` global state.
    """
    rng = np.random.default_rng(seed)
    g = rng.random((grid, grid)) * 2.0 - 1.0

    x = (u / scale) % grid
    y = (v / scale) % grid
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = x - x0
    fy = y - y0
    sx = fx * fx * (3.0 - 2.0 * fx)
    sy = fy * fy * (3.0 - 2.0 * fy)
    x0 %= grid
    y0 %= grid
    x1 = (x0 + 1) % grid
    y1 = (y0 + 1) % grid

    n00 = g[y0, x0]
    n10 = g[y0, x1]
    n01 = g[y1, x0]
    n11 = g[y1, x1]
    return ((n00 * (1.0 - sx) + n10 * sx) * (1.0 - sy)
            + (n01 * (1.0 - sx) + n11 * sx) * sy)


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _box_reduce(arr_u16, factor):
    """Area-average an image down by an integer factor. Exact, no RNG.

    float32 is exact here and that is arithmetic, not hope: the values
    are integers <= 65535 and a block sum is at most factor**2 * 65535.
    For every factor this function is called with (<= 8, so <= 4.2e6) the
    sum is well inside float32's 2**24 = 16,777,216 exact-integer range,
    so the sum is exact and only the final divide rounds. Using float32
    halves peak RAM on a 4096x4096 stamp (67 MB instead of 134 MB) on a
    host that runs at 1.4-2.1 GB free with the editor open (R10).
    """
    if factor <= 1:
        return arr_u16.astype(np.float64)
    n = arr_u16.shape[0]
    keep = (n // factor) * factor
    a = arr_u16[:keep, :keep].astype(np.float32)
    s = a.reshape(keep // factor, factor, keep // factor, factor)
    return s.mean(axis=(1, 3)).astype(np.float64)


def _bilinear(field, sx, sy):
    """Bilinear sample. `sx` indexes COLUMNS, `sy` indexes ROWS."""
    h, w = field.shape
    sx = np.clip(sx, 0.0, w - 1.001)
    sy = np.clip(sy, 0.0, h - 1.001)
    x0 = np.floor(sx).astype(np.int64)
    y0 = np.floor(sy).astype(np.int64)
    tx, ty = sx - x0, sy - y0
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    top = field[y0, x0] * (1.0 - tx) + field[y0, x1] * tx
    bot = field[y1, x0] * (1.0 - tx) + field[y1, x1] * tx
    return top * (1.0 - ty) + bot * ty


# ------------------------------------------------------------ compositing --

def _stamp_mask_and_sample(stamp_u16, placement, rows, cols,
                           centre_col, centre_row, half_px):
    """Return (s, mask) over the destination window `rows` x `cols`.

    `s` is the stamp resampled into destination pixels, 0..1.
    `mask` is the falloff, 0..1, INCLUDING opacity. mask == 0 everywhere
    the stamp does not apply, so the caller never needs a separate
    in/out-of-footprint test.
    """
    theta = math.radians(float(placement["rotation_deg"]))
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    # Destination pixel centres, as offsets from the stamp centre, in
    # destination pixels. COLUMN is world +X, ROW is world +Y
    # (measured — see the module docstring, fact 2).
    dx = (cols.astype(np.float64) - centre_col)
    dy = (rows.astype(np.float64) - centre_row)
    dx, dy = np.meshgrid(dx, dy)

    # World -> stamp-local. `rotation_deg` rotates the stamp
    # counter-clockwise in the world XY plane, so the inverse rotation is
    # applied here. Sign convention stated once and never re-derived:
    #   forward   dx =  u cos - v sin ,  dy =  u sin + v cos
    #   inverse   u  =  dx cos + dy sin,  v  = -dx sin + dy cos
    u = dx * cos_t + dy * sin_t
    v = -dx * sin_t + dy * cos_t

    un = u / half_px
    vn = v / half_px
    if placement["flip_x"]:
        un = -un
    if placement["flip_y"]:
        vn = -vn

    # Anti-aliasing. The alpine stamp footprint is ~300 destination pixels
    # against a 4096 px source: point-sampling that 13.6x minification
    # aliases badly and the aliasing looks like terrain detail, which is
    # the worst kind of wrong. Pre-reduce by the largest power of two that
    # keeps the source at or above the destination size, then bilinear the
    # remaining <2x. Powers of two only, so the box reduce divides evenly
    # and the operation stays exact and deterministic.
    dest_side = max(2.0 * half_px, 1.0)
    factor = 1
    while (stamp_u16.shape[0] // (factor * 2)) >= dest_side and factor < 64:
        factor *= 2
    reduced = _box_reduce(stamp_u16, factor)
    side = reduced.shape[0]

    sx = (un * 0.5 + 0.5) * (side - 1)
    sy = (vn * 0.5 + 0.5) * (side - 1)
    s = _bilinear(reduced, sx, sy) / UINT16_MAX

    if placement["falloff_shape"] == "chebyshev":
        r = np.maximum(np.abs(un), np.abs(vn))
    else:
        r = np.hypot(un, vn)

    # FALLOFF JITTER (schema v1.15) — break the mask's own symmetry.
    #
    # A euclidean falloff leaves a EUCLIDEAN FINGERPRINT: the contour
    # where the stamp stops contributing is a perfect circle, and at
    # airship altitude that circle is legible as a soft tonal ring. It
    # does not matter that the height field is continuous across it —
    # the eye finds the circle because nothing in real terrain is one.
    # Chebyshev is worse; its fingerprint is a square.
    #
    # The perturbation is ONE-SIDED, and that is the whole safety
    # argument. `n01` is in [0, 1], so
    #
    #     r_j = r * (1 + jitter * n01)   >=   r     ALWAYS
    #
    # Therefore r_j >= 1 wherever r >= 1, so the mask is still EXACTLY
    # ZERO on and outside the geometric footprint and no seam can be
    # created. The contour where the mask reaches zero moves INWARD by a
    # varying amount, which is what makes it non-circular. A two-sided
    # jitter would let r_j < 1 at the footprint edge, leaving mask > 0
    # there against a hard cut — the exact defect the smoothstep falloff
    # exists to prevent, reintroduced by the fix for a cosmetic problem.
    jitter = float(placement["falloff_jitter"])
    if jitter > 0.0:
        seed = ((int(placement["stamp_sha256"][:8], 16)
                 ^ zlib.crc32(placement["id"].encode("utf-8")))
                & 0xFFFFFFFF)
        n01 = 0.5 * (_value_noise(
            un, vn, float(placement["falloff_jitter_scale"]), seed) + 1.0)
        r = r * (1.0 + jitter * n01)

    t = np.clip((1.0 - r) / float(placement["falloff"]), 0.0, 1.0)
    mask = _smoothstep(t) * float(placement["opacity"])
    return s, mask, factor, side


def _datum_value(s, mask, datum):
    """The stamp value that means 'no change', over contributing pixels."""
    if datum == "zero":
        return 0.0
    sel = s[mask > 0.0]
    if sel.size == 0:
        # Unreachable via the footprint gate, but a datum computed from an
        # empty selection is nan, and nan would then flow into every delta
        # and pass the range check. Refuse instead of producing a number.
        raise Refuse(EXIT_FOOTPRINT,
                     "datum {0!r} has no contributing pixels to measure "
                     "from".format(datum))
    if datum == "min":
        return float(sel.min())
    if datum == "mean":
        return float(sel.mean())
    if datum == "median":
        return float(np.median(sel))
    raise Refuse(EXIT_INPUT, "unknown datum {0!r}".format(datum))


def composite(base_u16, placements, stamps_by_id, z_scale_m, spacing_m,
              origin_m, allow_edge_clip):
    """Blend every placement into a copy of `base_u16`. Pure; no IO.

    Returns (height_m float64 array, [per-placement report dicts]).
    Reads `base_u16` and never mutates it — the caller's base array is the
    original every run, which is guard (a) of the idempotence contract.
    """
    n = base_u16.shape[0]
    h_m = base_u16.astype(np.float64) / UINT16_MAX * z_scale_m
    unit_m = z_scale_m / UINT16_MAX          # metres per 16-bit unit
    reports = []

    for p in placements:
        stamp_u16 = stamps_by_id[p["id"]]

        cx_m, cy_m = float(p["centre_m"][0]), float(p["centre_m"][1])
        centre_col = (cx_m - origin_m[0]) / spacing_m
        centre_row = (cy_m - origin_m[1]) / spacing_m
        half_px = (float(p["size_m"]) * 0.5) / spacing_m

        # Bounding box of the ROTATED square, in destination pixels.
        theta = math.radians(float(p["rotation_deg"]))
        reach = half_px * (abs(math.cos(theta)) + abs(math.sin(theta)))
        r0_f, r1_f = centre_row - reach, centre_row + reach
        c0_f, c1_f = centre_col - reach, centre_col + reach
        r0, r1 = int(math.floor(r0_f)), int(math.ceil(r1_f)) + 1
        c0, c1 = int(math.floor(c0_f)), int(math.ceil(c1_f)) + 1
        r0c, r1c = max(r0, 0), min(r1, n)
        c0c, c1c = max(c0, 0), min(c1, n)

        if r0c >= r1c or c0c >= c1c:
            raise Refuse(
                EXIT_FOOTPRINT,
                "placement {0!r} lands entirely off the map. Its centre is "
                "world ({1:.1f}, {2:.1f}) m -> pixel (row {3:.1f}, col "
                "{4:.1f}) on a {5}x{5} grid spanning world X/Y {6:.1f}.."
                "{7:.1f} m. A placement that composites nothing must "
                "refuse, not report success."
                .format(p["id"], cx_m, cy_m, centre_row, centre_col, n,
                        origin_m[0], origin_m[0] + (n - 1) * spacing_m))

        clipped = (r0 < 0) or (c0 < 0) or (r1 > n) or (c1 > n)
        if clipped and not allow_edge_clip:
            raise Refuse(
                EXIT_FOOTPRINT,
                "placement {0!r} is clipped by the map edge (bbox rows "
                "{1}..{2}, cols {3}..{4} against a {5}x{5} grid) and "
                "stamps.allow_edge_clip is false. A clipped falloff IS a "
                "hard seam — the mask never reaches 0 on the cut side — so "
                "this fails closed. Move the placement, shrink size_m, or "
                "set allow_edge_clip true and accept the seam."
                .format(p["id"], r0, r1, c0, c1, n))

        rows = np.arange(r0c, r1c)
        cols = np.arange(c0c, c1c)
        s, mask, factor, side = _stamp_mask_and_sample(
            stamp_u16, p, rows, cols, centre_col, centre_row, half_px)

        touched = int((mask > 0.0).sum())
        if touched == 0:
            raise Refuse(
                EXIT_FOOTPRINT,
                "placement {0!r} produced a zero mask over its whole "
                "in-map footprint, so it would composite nothing while "
                "reporting success. falloff={1}, shape={2}, opacity={3}."
                .format(p["id"], p["falloff"], p["falloff_shape"],
                        p["opacity"]))

        window = h_m[r0c:r1c, c0c:c1c]
        amp = float(p["amplitude_m"])
        blend = p["blend"]
        if blend == "ADD":
            datum = _datum_value(s, mask, p["datum"])
            target = window + (s - datum) * amp
        else:
            datum = None
            surface = float(p["anchor_m"]) + s * amp
            if blend == "MAX":
                target = np.maximum(window, surface)
            elif blend == "MIN":
                target = np.minimum(window, surface)
            elif blend == "MASKED":
                target = surface
            else:
                raise Refuse(EXIT_INPUT,
                             "unknown blend {0!r}".format(blend))

        delta = mask * (target - window)
        # Non-finite must be caught HERE, per placement, not only at the
        # end: a nan introduced by one stamp propagates into every
        # subsequent max/min and the final report would name the wrong
        # stamp. Diagnostics must say which measurement failed.
        if not np.isfinite(delta).all():
            raise Refuse(
                EXIT_RANGE,
                "placement {0!r} produced {1} non-finite delta values. A "
                "range check run before this one would PASS on them, "
                "because every comparison against nan is False."
                .format(p["id"], int((~np.isfinite(delta)).sum())))
        h_m[r0c:r1c, c0c:c1c] = window + delta

        moved = np.abs(delta) > (0.5 * unit_m)
        reports.append({
            "id": p["id"],
            "blend": blend,
            "stamp_sha256": p["stamp_sha256"],
            "centre_world_m": [round(cx_m, 3), round(cy_m, 3)],
            "centre_pixel_row_col": [round(centre_row, 3),
                                     round(centre_col, 3)],
            "size_m": float(p["size_m"]),
            "size_px": round(2.0 * half_px, 3),
            "rotation_deg": float(p["rotation_deg"]),
            "flip_x": bool(p["flip_x"]), "flip_y": bool(p["flip_y"]),
            "falloff": float(p["falloff"]),
            "falloff_shape": p["falloff_shape"],
            "opacity": float(p["opacity"]),
            "amplitude_m": amp,
            "datum": p.get("datum"),
            "datum_value_0_1": (None if datum is None else round(datum, 6)),
            "anchor_m": p.get("anchor_m"),
            "bbox_rows": [r0c, r1c], "bbox_cols": [c0c, c1c],
            "edge_clipped": bool(clipped),
            "stamp_prereduce_factor": factor,
            "stamp_sampled_side_px": side,
            "mask_pixels": touched,
            "moved_pixels": int(moved.sum()),
            "delta_min_m": float(delta.min()),
            "delta_max_m": float(delta.max()),
            "delta_min_units": float(delta.min() / unit_m),
            "delta_max_units": float(delta.max() / unit_m),
            "delta_mean_abs_m": float(np.abs(delta).mean()),
        })
    return h_m, reports


def _ridged_fbm(n, spacing_m, wavelength_m, octaves, lacunarity, gain, seed):
    """Ridged multifractal noise on the destination grid, in [0, 1].

    RIDGED, not plain fbm: `1 - |noise|` squared puts CRESTS where plain
    noise puts zero-crossings, which is what broken rock looks like.
    Smooth fbm would add rolling bumps and make a glossy wall into a
    lumpy glossy wall.

    Deterministic from `seed` alone (pipeline rule 3).
    """
    out = np.zeros((n, n), dtype=np.float64)
    amp, norm = 1.0, 0.0
    wl = float(wavelength_m)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    for o in range(int(octaves)):
        cells = max(wl / spacing_m, 2.0)
        u = xx / cells
        v = yy / cells
        nz = _value_noise(u, v, 1.0, (seed + 7919 * o) & 0xFFFFFFFF, grid=128)
        ridge = 1.0 - np.abs(nz)
        out += amp * ridge * ridge
        norm += amp
        amp *= float(gain)
        wl /= float(lacunarity)
    return out / max(norm, 1e-9)


def apply_detail_relief(h_m, spacing_m, spec):
    """Slope-masked ridge detail, applied AFTER every placement.

    WHY THIS EXISTS, measured rather than asserted. After the Pass 1
    composition, 45.2% of faces steeper than 45 degrees carried
    |laplacian| < 1.0 m — smooth at cell scale. The stamped surface was
    in fact SMOOTHER on steep ground than the base it came from (median
    1.133 m against 1.289 m), because stamps add large-scale SLOPE faster
    than they add fine RELIEF. At render time a steep face with no
    cell-scale relief is a glossy featureless wall, and no material can
    rescue it: the landscape normal comes from this height field.

    The mask is the slope of the COMPOSITED surface, so detail lands
    wherever the composition actually produced steep ground, including
    faces no stamp reached. Slope is computed once, BEFORE the detail is
    added — adding relief changes slope, and re-deriving the mask from
    the modified surface would feed the pass its own output.
    """
    n = h_m.shape[0]
    gy, gx = np.gradient(h_m, spacing_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    lo, hi = [float(v) for v in spec["slope_deg"]]
    feather = float(spec["slope_feather_deg"])
    t_in = np.clip((slope - (lo - feather)) / max(feather, 1e-9), 0.0, 1.0)
    t_out = np.clip((hi + feather - slope) / max(feather, 1e-9), 0.0, 1.0)
    mask = _smoothstep(t_in) * _smoothstep(t_out)

    field = _ridged_fbm(n, spacing_m, spec["wavelength_m"],
                        spec["octaves"], spec["lacunarity"], spec["gain"],
                        int(spec["seed"]))
    # Centre the field on zero so detail does not net-RAISE the terrain:
    # a one-sided addition would lift every steep face and shift the
    # snowline, which is a scene change disguised as a texture change.
    field = field - field.mean()
    delta = field * float(spec["amplitude_m"]) * mask
    h_m = h_m + delta

    return h_m, {
        "amplitude_m": float(spec["amplitude_m"]),
        "wavelength_m": float(spec["wavelength_m"]),
        "octaves": int(spec["octaves"]),
        "slope_deg": [lo, hi],
        "slope_feather_deg": feather,
        "seed": int(spec["seed"]),
        "masked_cells": int((mask > 0.01).sum()),
        "masked_frac": float((mask > 0.01).mean()),
        "delta_min_m": float(delta.min()),
        "delta_max_m": float(delta.max()),
        "delta_mean_abs_m": float(np.abs(delta).mean()),
        "net_mean_m": float(delta.mean()),
    }


def to_uint16(h_m, z_scale_m, allow_clamp):
    """Quantise metres -> 16-bit. REFUSES rather than wrapping.

    The cast to uint16 is the LAST operation and happens only after an
    explicit clip, so a wrap is unrepresentable rather than merely
    unlikely. `np.float64(70000).astype(np.uint16)` is 4464 and reports
    nothing.
    """
    units = h_m / z_scale_m * UINT16_MAX
    # isfinite FIRST. nan passes every `<`/`>` test below.
    n_bad = int((~np.isfinite(units)).sum())
    if n_bad:
        raise Refuse(EXIT_RANGE,
                     "composite holds {0} non-finite values; refusing. "
                     "(Order matters: the range test below would have "
                     "PASSED on them.)".format(n_bad))
    rounded = np.rint(units)
    lo, hi = float(rounded.min()), float(rounded.max())
    under = int((rounded < 0.0).sum())
    over = int((rounded > UINT16_MAX).sum())
    clamped = False
    if under or over:
        if not allow_clamp:
            raise Refuse(
                EXIT_RANGE,
                "composite leaves the 16-bit range: {0} pixels below 0, "
                "{1} pixels above 65535; observed {2:.1f}..{3:.1f} units "
                "({4:.1f}..{5:.1f} m against z_scale {6:.1f} m). REFUSING "
                "— a uint16 cast here would WRAP silently. Lower "
                "amplitude_m, lower anchor_m, or re-run with "
                "--allow-clamp to flatten the excess and be told exactly "
                "how much height was lost."
                .format(under, over, lo, hi,
                        lo / UINT16_MAX * z_scale_m,
                        hi / UINT16_MAX * z_scale_m, z_scale_m))
        clamped = True
    out = np.clip(rounded, 0.0, UINT16_MAX).astype(np.uint16)
    stats = {
        "clamped": clamped,
        "clamp_pixels_low": under,
        "clamp_pixels_high": over,
        "pre_clamp_min_units": lo,
        "pre_clamp_max_units": hi,
        "height_lost_low_m": (0.0 if not under
                              else (0.0 - lo) / UINT16_MAX * z_scale_m),
        "height_lost_high_m": (0.0 if not over
                               else (hi - UINT16_MAX) / UINT16_MAX
                               * z_scale_m),
    }
    return out, stats


# ------------------------------------------------------------------ load --

def load_stamps(stamps_block, catalogue_path):
    """Resolve every placement's stamp BY CONTENT HASH and verify it.

    Identity is the SHA-256 of the file bytes, never the filename or the
    folder index (RECIPES.md R1 catalogue spec — names drift
    singular/plural across the pack's tiers and folder indices swap). The
    catalogue's recorded hash is re-derived from the file on disk here, so
    a stamp that was replaced under the same name is caught rather than
    silently composited.
    """
    if not os.path.isfile(catalogue_path):
        raise Refuse(EXIT_INPUT,
                     "catalogue not found: {0}".format(catalogue_path))
    with open(catalogue_path, "r", encoding="utf-8") as fh:
        cat = json.load(fh)
    by_hash = {}
    for m in cat.get("maps") or []:
        by_hash[m.get("hash")] = m

    out = {}
    meta = {}
    for p in stamps_block["placements"]:
        want = p["stamp_sha256"]
        entry = by_hash.get(want)
        if entry is None:
            raise Refuse(
                EXIT_IDENTITY,
                "placement {0!r} names stamp_sha256 {1} which is not in "
                "{2} ({3} maps catalogued). Identity is the content hash; "
                "a filename would not have caught this."
                .format(p["id"], want, os.path.relpath(catalogue_path,
                                                       REPO_ROOT),
                        len(by_hash)))
        if entry.get("category") != "STAMP":
            raise Refuse(
                EXIT_IDENTITY,
                "placement {0!r} resolves to catalogue category {1!r}, not "
                "STAMP. A TERRAIN is a standalone heightmap and is imported "
                "whole; compositing one as a feature is a category error "
                "(RECIPES.md R1)."
                .format(p["id"], entry.get("category")))
        path = _resolve(entry["relpath"], "stamp relpath")
        got = sha256_file(path)
        if got != want:
            raise Refuse(
                EXIT_IDENTITY,
                "stamp file {0} hashes {1} but the catalogue and the "
                "recipe both say {2}. The file on disk is not the one this "
                "recipe was authored against. Refusing rather than "
                "compositing something nobody chose."
                .format(os.path.relpath(path, REPO_ROOT), got, want))
        arr = read_png16_square(path, "stamp {0!r}".format(p["id"]))
        if not entry.get("conforms_to_r11"):
            raise Refuse(
                EXIT_IDENTITY,
                "stamp {0!r} is catalogued conforms_to_r11=false (mode "
                "{1}, has_alpha {2}); 16-bit-with-alpha is the exact "
                "configuration behind the grass defect (R11)."
                .format(p["id"], entry.get("mode"), entry.get("has_alpha")))
        out[p["id"]] = arr
        meta[p["id"]] = {"filename": entry.get("filename"),
                         "relpath": entry.get("relpath"),
                         "tag": entry.get("tag"),
                         "resolution_px": entry.get("resolution_px"),
                         "sha256": got}
    return out, meta


def self_ingestion_guard(base_path, base_sha, output_path):
    """Guard (c): refuse if the base IS a previous run's output.

    Guards (a) and (b) cannot see this — the recipe would look perfectly
    well-formed. Every sidecar next to the output is read and its recorded
    output hash compared. `_verify/`-style provenance used as a gate.
    """
    pattern = os.path.join(os.path.dirname(output_path), "*.stamps.json")
    for side in sorted(glob.glob(pattern)):
        try:
            with open(side, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        if doc.get("output_sha256") == base_sha:
            raise Refuse(
                EXIT_IDEMPOTENCE,
                "stamps.base ({0}) has the SHA-256 recorded as the OUTPUT "
                "of a previous composite in {1}. Compositing onto a "
                "previous output accumulates stamps on every run while "
                "reporting success, which is the exact failure hard "
                "pipeline rule 3 forbids. Point stamps.base back at the "
                "original base heightmap."
                .format(os.path.relpath(base_path, REPO_ROOT),
                        os.path.relpath(side, REPO_ROOT)))


# -------------------------------------------------------------- selftest --

def _synthetic_recipe(tmpdir, **over):
    base = np.full((257, 257), 20000, dtype=np.uint16)
    base_path = os.path.join(tmpdir, "st_base.png")
    mat.write_png16_grey(base_path, base)
    return base, base_path


def selftest(recipe, stamps_block, base_u16, stamps_by_id, z_scale_m,
             spacing_m, origin_m):
    """Prove the gates REFUSE, not merely that the good path passes.

    RECIPES.md mandatory practice (b): a gate that has only ever seen good
    input is untested. Every case below is driven with the exact bad input
    the gate exists for, and a case that FAILS TO REFUSE fails the test.
    """
    fails = []

    def expect_refuse(label, code, fn):
        try:
            fn()
        except Refuse as exc:
            if exc.code != code:
                fails.append("{0}: refused with exit {1}, expected {2} "
                             "({3})".format(label, exc.code, code, exc))
            else:
                print("    REFUSED as required  [{0}] exit {1}"
                      .format(label, exc.code))
            return
        fails.append("{0}: DID NOT REFUSE — the gate is inert".format(label))

    pls = stamps_block["placements"]
    print("  gate tests (bad input must be refused):")

    # 1. Overflow must refuse, not wrap. amplitude driven far past range.
    big = [dict(p) for p in pls]
    for p in big:
        if p["blend"] == "ADD":
            p["amplitude_m"] = 100000.0
        else:
            p["anchor_m"] = 100000.0
    expect_refuse(
        "overflow -> uint16 wrap", EXIT_RANGE,
        lambda: to_uint16(composite(base_u16, big, stamps_by_id, z_scale_m,
                                    spacing_m, origin_m, False)[0],
                          z_scale_m, False))

    # 2. Underflow must refuse too — a MIN/negative ADD below datum zero.
    low = [dict(p) for p in pls]
    for p in low:
        p["blend"] = "MASKED"
        p.pop("datum", None)
        p["anchor_m"] = -50000.0
        p["amplitude_m"] = 1.0
        p["opacity"] = 1.0
        p["falloff"] = 1.0
    expect_refuse(
        "underflow below 0", EXIT_RANGE,
        lambda: to_uint16(composite(base_u16, low, stamps_by_id, z_scale_m,
                                    spacing_m, origin_m, False)[0],
                          z_scale_m, False))

    # 3. NaN must be refused BEFORE the range test, not after.
    nan_field = base_u16.astype(np.float64) / UINT16_MAX * z_scale_m
    nan_field[0, 0] = float("nan")
    expect_refuse("non-finite composite", EXIT_RANGE,
                  lambda: to_uint16(nan_field, z_scale_m, False))
    # ... and the same field must ALSO be refused with --allow-clamp on,
    # because clamping a nan produces a number and hides it.
    expect_refuse("non-finite with --allow-clamp", EXIT_RANGE,
                  lambda: to_uint16(nan_field, z_scale_m, True))

    # 4. Off-map placement must refuse, not composite nothing.
    off = [dict(p) for p in pls]
    off[0]["centre_m"] = [origin_m[0] - 100000.0, origin_m[1] - 100000.0]
    expect_refuse("placement entirely off-map", EXIT_FOOTPRINT,
                  lambda: composite(base_u16, off, stamps_by_id, z_scale_m,
                                    spacing_m, origin_m, False))

    # 5. Edge-clipped placement must refuse while allow_edge_clip is false,
    #    and must be ACCEPTED when it is true. Both directions.
    edge = [dict(p) for p in pls]
    edge[0]["centre_m"] = [origin_m[0], origin_m[1]]
    expect_refuse("edge clip with allow_edge_clip=false", EXIT_FOOTPRINT,
                  lambda: composite(base_u16, edge, stamps_by_id, z_scale_m,
                                    spacing_m, origin_m, False))
    try:
        composite(base_u16, edge, stamps_by_id, z_scale_m, spacing_m,
                  origin_m, True)
        print("    ACCEPTED as required [edge clip with "
              "allow_edge_clip=true]")
    except Refuse as exc:
        fails.append("edge clip with allow_edge_clip=true: refused ({0}); "
                     "the gate is stuck closed".format(exc))

    # 6. Schema gates. The accumulating configuration must be
    #    unrepresentable, and mode-exclusive keys must be refused.
    def schema_case(label, mutate):
        r = json.loads(json.dumps(recipe))
        mutate(r)
        errs = ih._validate_stamps(r.get("stamps"), r)
        if not errs:
            fails.append("schema/{0}: validator accepted it".format(label))
        else:
            print("    REFUSED as required  [schema/{0}] {1}"
                  .format(label, errs[0][:88]))

    schema_case("base == output",
                lambda r: r["stamps"].update(output=r["stamps"]["base"]))
    # NOTE the distinct base. Without it this case also trips the
    # base == output gate and the adoption gate stays untested — a gate
    # tested only through another gate is not tested.
    schema_case("output == heightmap.source",
                lambda r: r["stamps"].update(
                    base="terrain/some_other_base.png",
                    output=r["heightmap"]["source"]))
    # THIS CASE MUST FIND AN `ADD` PLACEMENT, NOT ASSUME INDEX 0.
    #
    # It used to mutate `placements[0]` and rely on that being an ADD.
    # The Pass 1 composition made placement 0 a MIN basin, which
    # legitimately carries `anchor_m` — so the mutation produced a VALID
    # recipe, the validator correctly accepted it, and the SELFTEST
    # reported a gate failure. The gate was never broken.
    #
    # A test coupled to the current recipe's DATA passes or fails for
    # reasons that have nothing to do with the code it is testing. It
    # cost a real false alarm the day the composition changed, and a
    # false alarm on a gate is expensive precisely because the correct
    # reaction to one is to distrust the gate.
    _add_i = next((i for i, p in enumerate(recipe["stamps"]["placements"])
                   if p.get("blend") == "ADD"), None)
    if _add_i is None:
        fails.append("schema/anchor_m on an ADD placement: the recipe has "
                     "no ADD placement, so this gate could not be tested. "
                     "Untested is not passed.")
    else:
        schema_case("anchor_m on an ADD placement",
                    lambda r: r["stamps"]["placements"][_add_i].update(
                        anchor_m=0.0))

    _nonadd_i = next((i for i, p in enumerate(recipe["stamps"]["placements"])
                      if p.get("blend") != "ADD"), None)
    if _nonadd_i is None:
        fails.append("schema/datum on a non-ADD placement: the recipe has "
                     "no MAX/MIN/MASKED placement, so this gate could not "
                     "be tested. Untested is not passed.")
    else:
        schema_case("datum on a non-ADD placement",
                    lambda r: r["stamps"]["placements"][_nonadd_i].update(
                        datum="min"))

    schema_case("falloff_jitter above the 0.5 bound",
                lambda r: r["stamps"]["placements"][0].update(
                    falloff_jitter=0.9))
    schema_case("falloff_jitter_scale 0",
                lambda r: r["stamps"]["placements"][0].update(
                    falloff_jitter_scale=0.0))
    schema_case("opacity 0 (a silent no-op)",
                lambda r: r["stamps"]["placements"][0].update(opacity=0.0))
    schema_case("falloff 0 (division by zero in the mask)",
                lambda r: r["stamps"]["placements"][0].update(falloff=0.0))
    schema_case("NaN amplitude_m",
                lambda r: r["stamps"]["placements"][0].update(
                    amplitude_m=float("nan")))
    schema_case("empty placements",
                lambda r: r["stamps"].update(placements=[]))

    # 7. DETERMINISM. Two composites in one process must be bit-identical,
    #    which is a different instrument from the sidecar's file-hash
    #    comparison across processes.
    a, _ = composite(base_u16, pls, stamps_by_id, z_scale_m, spacing_m,
                     origin_m, stamps_block["allow_edge_clip"])
    b, _ = composite(base_u16, pls, stamps_by_id, z_scale_m, spacing_m,
                     origin_m, stamps_block["allow_edge_clip"])
    ua, _ = to_uint16(a, z_scale_m, False)
    ub, _ = to_uint16(b, z_scale_m, False)
    if np.array_equal(ua, ub):
        print("    determinism          : two in-process composites are "
              "bit-identical")
    else:
        fails.append("determinism: two composites of the same input differ "
                     "in {0} pixels".format(int((ua != ub).sum())))

    # 8. The base array must be untouched by compositing (guard a).
    if base_u16.max() == 0:
        fails.append("selftest base is all zero; the guard-(a) check below "
                     "would pass vacuously")
    return fails


# ------------------------------------------------------------------ main --

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--dry-run", action="store_true",
                   help="Composite and report, write nothing.")
    p.add_argument("--allow-clamp", action="store_true",
                   help="Flatten out-of-range pixels instead of refusing, "
                        "and report exactly how many and how much height "
                        "was lost. Never wraps either way.")
    p.add_argument("--selftest", action="store_true",
                   help="Drive every gate with the bad input it exists "
                        "for, prove determinism, then exit. Writes "
                        "nothing.")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return EXIT_OK if exc.code == 0 else EXIT_USAGE

    try:
        return _run(args)
    except Refuse as exc:
        print("")
        print("REFUSE (exit {0}): {1}".format(exc.code, exc))
        return exc.code


def _run(args):
    recipe_path = os.path.abspath(args.recipe)
    if not _inside_repo(recipe_path):
        raise Refuse(EXIT_USAGE,
                     "recipe must be inside {0}".format(REPO_ROOT))
    with open(recipe_path, "r", encoding="utf-8") as fh:
        recipe = json.load(fh)

    errors = ih._validate_recipe(recipe, recipe_path)
    if errors:
        print("REFUSE: recipe {0} is not schema-valid:"
              .format(os.path.relpath(recipe_path, REPO_ROOT)))
        for e in errors:
            print("  - {0}".format(e))
        return EXIT_INPUT

    st = recipe.get("stamps")
    if st is None:
        print("REFUSE: {0} declares no `stamps` block. Nothing to "
              "composite. Add one (recipes/schema.md v1.12) — this script "
              "never invents a placement."
              .format(os.path.relpath(recipe_path, REPO_ROOT)))
        return EXIT_INPUT

    hm, ls = recipe["heightmap"], recipe["landscape"]
    base_path = _resolve(st["base"], "stamps.base")
    out_path = _resolve(st["output"], "stamps.output")
    cat_path = _resolve(st["catalogue"], "stamps.catalogue")

    print("=" * 74)
    print("composite_stamps — {0} ({1})".format(
        recipe["display_name"], recipe["biome_id"]))
    print("=" * 74)
    resource_guard.check_memory("composite_stamps")

    base_sha = sha256_file(base_path)
    self_ingestion_guard(base_path, base_sha, out_path)

    base_u16 = read_png16_square(base_path, "stamps.base")
    n = base_u16.shape[0]
    if n != int(hm["resolution"]):
        # The spacing below is only exact when the grid IS the recipe's
        # grid. make_alpine_terrain.report_relief was bitten by exactly
        # this (its comment calls it "the trap this exists for"): a
        # preview at half resolution silently doubles the real spacing and
        # every metre-denominated number downstream is wrong by 2x. Here
        # it would move every stamp centre, so it refuses instead of
        # deriving a spacing nobody asked for.
        raise Refuse(
            EXIT_INPUT,
            "stamps.base is {0}x{0} but heightmap.resolution is {1}. "
            "centre_m -> pixel conversion uses landscape.scale_xy_cm, "
            "which is the spacing at the RECIPE's resolution; on a "
            "different grid every stamp would land somewhere else. "
            "Refusing rather than rescaling."
            .format(n, hm["resolution"]))

    z_scale_m = float(ls["z_scale_cm"]) / 100.0
    spacing_m = float(ls["scale_xy_cm"]) / 100.0
    origin_m = (float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0)
    unit_m = z_scale_m / UINT16_MAX
    span_m = (n - 1) * spacing_m

    print("")
    print("  base            : {0}".format(os.path.relpath(base_path,
                                                           REPO_ROOT)))
    print("  base sha256     : {0}".format(base_sha))
    print("  grid            : {0} x {0} px, spacing {1:.3f} m, span "
          "{2:.1f} m".format(n, spacing_m, span_m))
    print("  world extent    : X {0:.1f}..{1:.1f} m   Y {2:.1f}..{3:.1f} m"
          .format(origin_m[0], origin_m[0] + span_m,
                  origin_m[1], origin_m[1] + span_m))
    print("  z_scale         : {0:.1f} m over the full 16-bit range "
          "({1:.5f} m per unit)".format(z_scale_m, unit_m))
    b_lo, b_hi = int(base_u16.min()), int(base_u16.max())
    print("  base relief     : {0}..{1} units = {2:.2f}..{3:.2f} m "
          "({4:.1f}% of range used)".format(
              b_lo, b_hi, b_lo * unit_m, b_hi * unit_m,
              100.0 * (b_hi - b_lo) / UINT16_MAX))
    print("  ADD headroom    : {0:.2f} m before the highest pixel "
          "overflows".format((UINT16_MAX - b_hi) * unit_m))

    stamps_by_id, stamp_meta = load_stamps(st, cat_path)
    print("  catalogue       : {0}".format(os.path.relpath(cat_path,
                                                           REPO_ROOT)))
    print("  placements      : {0}".format(len(st["placements"])))

    if args.selftest:
        print("")
        print("-" * 74)
        print("SELFTEST")
        print("-" * 74)
        before = base_u16.copy()
        fails = selftest(recipe, st, base_u16, stamps_by_id, z_scale_m,
                         spacing_m, origin_m)
        if not np.array_equal(before, base_u16):
            fails.append("compositing MUTATED the base array in place; "
                         "guard (a) of the idempotence contract is broken")
        else:
            print("    base immutability    : base array unchanged after "
                  "{0} composites".format(2))
        print("")
        if fails:
            print("SELFTEST FAILED ({0}):".format(len(fails)))
            for f in fails:
                print("  - {0}".format(f))
            return EXIT_SELFTEST
        print("SELFTEST PASSED — every gate refused its bad input, and "
              "compositing is deterministic.")
        return EXIT_OK

    h_m, reports = composite(base_u16, st["placements"], stamps_by_id,
                             z_scale_m, spacing_m, origin_m,
                             bool(st["allow_edge_clip"]))

    # Detail relief runs LAST, after every placement, because its mask is
    # the slope of the FINISHED composition — including steep ground that
    # no stamp produced. Running it per-placement would miss exactly the
    # faces this exists to fix.
    detail_report = None
    if st.get("detail_relief") is not None:
        h_m, detail_report = apply_detail_relief(
            h_m, spacing_m, st["detail_relief"])

    out_u16, clamp_stats = to_uint16(h_m, z_scale_m, args.allow_clamp)

    # ------------------------------------------------------- the report --
    print("")
    print("-" * 74)
    print("PER-STAMP REPORT")
    print("-" * 74)
    for r in reports:
        meta = stamp_meta[r["id"]]
        print("")
        print("  [{0}]  {1}   tag={2}".format(
            r["id"], meta["filename"], meta["tag"]))
        print("    placement   : centre world ({0:.1f}, {1:.1f}) m  -> px "
              "(row {2:.1f}, col {3:.1f})".format(
                  r["centre_world_m"][0], r["centre_world_m"][1],
                  r["centre_pixel_row_col"][0], r["centre_pixel_row_col"][1]))
        print("                  size {0:.1f} m = {1:.1f} px, rotation "
              "{2:.1f} deg, flip x={3} y={4}".format(
                  r["size_m"], r["size_px"], r["rotation_deg"],
                  r["flip_x"], r["flip_y"]))
        print("                  bbox rows {0}..{1}, cols {2}..{3}"
              "   edge-clipped={4}".format(
                  r["bbox_rows"][0], r["bbox_rows"][1],
                  r["bbox_cols"][0], r["bbox_cols"][1], r["edge_clipped"]))
        print("                  source {0}px -> box-reduced /{1} -> "
              "{2}px -> bilinear".format(
                  meta["resolution_px"][0], r["stamp_prereduce_factor"],
                  r["stamp_sampled_side_px"]))
        if r["blend"] == "ADD":
            print("    blend       : ADD   amplitude {0:.1f} m   datum "
                  "{1!r} = {2:.6f} (= {3:.2f} m subtracted)".format(
                      r["amplitude_m"], r["datum"], r["datum_value_0_1"],
                      r["datum_value_0_1"] * r["amplitude_m"]))
        else:
            print("    blend       : {0}   amplitude {1:.1f} m   anchor "
                  "{2:.1f} m  (stamp surface spans {2:.1f}..{3:.1f} m)"
                  .format(r["blend"], r["amplitude_m"], r["anchor_m"],
                          r["anchor_m"] + r["amplitude_m"]))
        print("    falloff     : {0} {1:.3f}  opacity {2:.3f}  -> mask==1 "
              "over the inner {3:.0f}% of the half-width".format(
                  r["falloff_shape"], r["falloff"], r["opacity"],
                  100.0 * (1.0 - r["falloff"])))
        print("    HEIGHT DELTA: min {0:+.3f} m   max {1:+.3f} m"
              .format(r["delta_min_m"], r["delta_max_m"]))
        print("                  min {0:+.1f} units  max {1:+.1f} units  "
              "(16-bit)".format(r["delta_min_units"], r["delta_max_units"]))
        print("                  mean |delta| {0:.3f} m over {1} masked px; "
              "{2} px moved > 0.5 unit".format(
                  r["delta_mean_abs_m"], r["mask_pixels"],
                  r["moved_pixels"]))

    # --------------------------------------------------- whole-map delta --
    d_units = out_u16.astype(np.int64) - base_u16.astype(np.int64)
    changed = int((d_units != 0).sum())
    print("")
    print("-" * 74)
    print("WHOLE-MAP RESULT")
    print("-" * 74)
    print("  before          : {0}..{1} units = {2:.2f}..{3:.2f} m"
          .format(b_lo, b_hi, b_lo * unit_m, b_hi * unit_m))
    print("  after           : {0}..{1} units = {2:.2f}..{3:.2f} m"
          .format(int(out_u16.min()), int(out_u16.max()),
                  int(out_u16.min()) * unit_m, int(out_u16.max()) * unit_m))
    print("  mean            : {0:.2f} m -> {1:.2f} m".format(
        base_u16.mean() * unit_m, out_u16.mean() * unit_m))
    print("  pixels changed  : {0} of {1} ({2:.4f}%)".format(
        changed, out_u16.size, 100.0 * changed / out_u16.size))
    print("  delta range     : {0:+.3f} m .. {1:+.3f} m".format(
        d_units.min() * unit_m, d_units.max() * unit_m))
    if clamp_stats["clamped"]:
        print("  CLAMPED         : {0} px below 0 (lost {1:.2f} m), {2} px "
              "above 65535 (lost {3:.2f} m). --allow-clamp was given; "
              "without it this run would have REFUSED."
              .format(clamp_stats["clamp_pixels_low"],
                      clamp_stats["height_lost_low_m"],
                      clamp_stats["clamp_pixels_high"],
                      clamp_stats["height_lost_high_m"]))
    else:
        print("  clamping        : none needed; every pixel inside "
              "0..65535 before quantisation")

    if detail_report:
        print("  detail relief   : +/-{0:.2f} m ridge on {1:.2f}% of the "
              "map (slope {2:.0f}-{3:.0f} deg), net mean {4:+.4f} m"
              .format(max(abs(detail_report["delta_min_m"]),
                          abs(detail_report["delta_max_m"])),
                      100.0 * detail_report["masked_frac"],
                      detail_report["slope_deg"][0],
                      detail_report["slope_deg"][1],
                      detail_report["net_mean_m"]))
    else:
        print("  detail relief   : NOT DECLARED — steep faces carry only "
              "whatever cell-scale relief the base and the stamps happened "
              "to provide")

    if args.dry_run:
        print("")
        print("DRY RUN — nothing written.")
        return EXIT_OK

    # ------------------------------------------------------------ write --
    mat.write_png16_grey(out_path, out_u16)
    out_sha = sha256_file(out_path)
    # Re-read from disk with a different reader than the writer, and
    # compare to the array we intended. A writer reporting its own success
    # is not verification (CLAUDE.md non-negotiable 8).
    back = read_png16_square(out_path, "stamps.output (read-back)")
    if not np.array_equal(back, out_u16):
        raise Refuse(EXIT_RANGE,
                     "read-back of {0} does not match the array written "
                     "({1} pixels differ)"
                     .format(os.path.relpath(out_path, REPO_ROOT),
                             int((back != out_u16).sum())))

    stamps_block_sha = _canonical_sha256(st)
    side_path = out_path + ".stamps.json"
    prior = None
    if os.path.isfile(side_path):
        try:
            with open(side_path, "r", encoding="utf-8") as fh:
                prior = json.load(fh)
        except (OSError, ValueError):
            prior = None

    doc = {
        "tool": "scripts/composite_stamps.py",
        "written_utc": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "recipe": os.path.relpath(os.path.abspath(args.recipe),
                                  REPO_ROOT).replace("\\", "/"),
        "biome_id": recipe["biome_id"],
        "base": st["base"],
        "base_sha256": base_sha,
        "output": st["output"],
        "output_sha256": out_sha,
        "stamps_block_sha256": stamps_block_sha,
        "resolution": n,
        "spacing_m": spacing_m,
        "z_scale_m": z_scale_m,
        "origin_m": [origin_m[0], origin_m[1]],
        "pixels_changed": changed,
        "clamp": clamp_stats,
        "detail_relief": detail_report,
        "stamp_meta": stamp_meta,
        "placements": reports,
        "downstream_invalidated": [
            "textures/alpine_weights.png  (scripts/make_layer_weightmap.py)",
            "terrain/alpine_flow.png / alpine_deposition.png "
            "(scripts/make_alpine_terrain.py)",
            "foliage/alpine_Conifer.json + 160,448 placed instances "
            "(scripts/place_foliage.py --place)",
        ],
    }
    with open(side_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("")
    print("  written         : {0}".format(os.path.relpath(out_path,
                                                           REPO_ROOT)))
    print("  output sha256   : {0}".format(out_sha))
    print("  sidecar         : {0}".format(os.path.relpath(side_path,
                                                           REPO_ROOT)))

    # Cross-process idempotence check, using the file hash rather than the
    # in-memory array — a different instrument from --selftest's.
    if prior:
        same_inputs = (prior.get("base_sha256") == base_sha
                       and prior.get("stamps_block_sha256")
                       == stamps_block_sha)
        if same_inputs:
            if prior.get("output_sha256") == out_sha:
                print("  IDEMPOTENT      : PASS — same base + same stamps "
                      "block reproduced byte-identical output ({0})"
                      .format(prior.get("written_utc")))
            else:
                print("  IDEMPOTENT      : *** FAIL *** — identical inputs "
                      "produced a DIFFERENT output than {0}. Previous "
                      "{1}, now {2}."
                      .format(prior.get("written_utc"),
                              prior.get("output_sha256"), out_sha))
                return EXIT_IDEMPOTENCE
        else:
            print("  IDEMPOTENT      : not applicable — inputs changed "
                  "since the previous sidecar (base or stamps block)")

    print("")
    print("=" * 74)
    print("ADOPTION — this output is NOT yet used by anything")
    print("=" * 74)
    print("  `heightmap.source` still points at {0}."
          .format(hm["source"]))
    print("  Changing terrain ORPHANS everything placed against the old")
    print("  terrain. Measured dependants:")
    print("    - 160,448 conifer instances carry BAKED Z from the old")
    print("      heightmap (R4). They do not re-sample; they float or sink.")
    print("    - terrain/alpine_flow.png drives Conifer flow_bias 0.45 and")
    print("      is derived from the old heightmap. Flow accumulation is")
    print("      NOT local: a stamp anywhere upstream changes drainage")
    print("      downstream of it, so 'the stamp is far from the trees' is")
    print("      NOT sufficient.")
    print("    - textures/alpine_weights.png drives BOTH the material and")
    print("      foliage density (R2/R4). Slope changes move the bands.")
    print("  Follow RECIPES.md R-STAMP ORDERED STEPS in full. Do not adopt")
    print("  by editing heightmap.source alone.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
