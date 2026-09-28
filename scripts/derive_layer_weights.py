"""derive_layer_weights.py — eight layer weights, DERIVED, never painted.

Brief 3 Task 2 (BRIEF 3 sec 3.4-3.6). Inputs: the adopted heightmap, the
Gaea flow/deposition exports, and the placed foliage instance JSONs.
Output: two RGBA weight PNGs (weights sum to 1 everywhere) plus a sidecar
recording every layer's formula, inputs, thresholds and coverage.

LAYER ORDER AND CHANNELS (the schema the material reads):
    weightmap A: R=snow  G=rock   B=scree      A=forest_floor
    weightmap B: R=wet_shore G=dirt_path B=gravel A=meadow

PRECEDENCE (first claim wins; later layers get the remainder):
    snow > rock > scree > forest_floor > wet_shore > dirt_path > gravel
    > meadow (remainder). Each weight is computed as its own 0..1 mask,
    then normalised by the running remainder, so the eight always sum
    to 1 -- the property the selftest asserts.

FORMULAS (sec 3.4-3.6, every number in the sidecar):
  snow          smoothstep over height above a PER-ASPECT snow line:
                line = base - 125*cos(aspect - north): north-facing holds
                snow 250 m lower than south-facing (alpine snow-line
                asymmetry, 200-300 m at mid-latitudes). x a slope term
                (full below 30 deg, gone by 40).
  rock          slope > 32 deg (smoothstep 29->35).
  scree         slope 20-32 deg AND within 60 m downhill of a >40 deg
                cell. "Downhill of" = a 60 m max-filter of the steep
                cells' heights; a cell qualifies when that local steep
                height EXCEEDS its own (the debris fell from above).
  forest_floor  canopy COVER fraction from the placed instances, each
                splatted as its crown disk and box-blurred by the crown
                radius; smoothstep 0.15->0.45 around the 0.3 threshold.
                NOTE ON UNITS (rule 9): the brief says "0.3 crowns/m^2";
                0.3 TREES per m^2 is denser than any forest (3.3 m^2 per
                tree), while 0.3 crown-AREA COVER is the standard canopy-
                cover figure -- read as COVER, recorded here.
  wet_shore     the damp SHORELINE RING of each placed lake (Brief 4 T4,
                2026-09-19): a cell qualifies when it is ADJACENT to a
                lake's connected footprint (a dilation of that footprint,
                capped at WET_SHORE_RING_M horizontally) AND sits within
                WET_SHORE_BAND_M vertically ABOVE the water level. Strength
                fades from 1 at the waterline to 0 by the band top. This is
                NOT a global |h-level|<=band band -- that paints every
                mountainside at the lake's elevation; the footprint
                dilation is what restricts it to the actual shore. Lake
                LEVELS come from recipes/water.json; the connected
                footprints from hydro_derive.level_slice (the hydrology
                tool of record) on the committed 4x analysis heightmap.
  dirt_path     DECLARED ZERO: no path mask exists in this recipe -- the
                town's streets are ACTORS, not a landscape layer.
  gravel        the Gaea deposition export, gated below the treeline and
                off steep slopes, scaled to a 0..1 mask.
  meadow        the remainder.

Slope/aspect come from the SOURCE heightmap at full resolution -- the
same choice make_layer_weightmap made and for the same reason (the
rendered vertex normal changes with LOD; the heightmap does not).

  python scripts/derive_layer_weights.py [--out-prefix textures/alpine_8k_w8]
  python scripts/derive_layer_weights.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")

SNOW_BASE_M = 730.0        # DEFAULT ONLY -- main() reads the recipe's Snow
                           # band floor and asserts they agree (audit F2:
                           # a duplicated constant drifts silently)
SNOW_ASPECT_HALF_M = 125.0  # +-125 m -> 250 m N-S asymmetry (sec 3.5)
SNOW_FEATHER_M = 60.0
ROCK_DEG = (29.0, 35.0)     # smoothstep to full rock by 35, centred on 32
SCREE_DEG = (20.0, 32.0)
SCREE_SOURCE_DEG = 40.0
SCREE_RUNOUT_M = 60.0
CANOPY_COVER_BAND = (0.15, 0.45)
GRAVEL_MAX_SLOPE_DEG = 20.0
# wet_shore (Brief 4 T4): the DECISION number is the 4 m vertical band above
# the water level (2026-09-19). The ring is a HORIZONTAL cap on shore reach --
# it stops a near-flat shelf from painting wet_shore far inland where the 4 m
# band would otherwise extend tens of metres; the band still does the vertical
# shaping inside it. These are layer-shape constants, like ROCK_DEG/SCREE_DEG,
# recorded in the sidecar; the per-lake LEVELS come from recipes/water.json.
WET_SHORE_BAND_M = 4.0
WET_SHORE_RING_M = 8.0


def smoothstep(lo, hi, x):
    t = np.clip((x - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def box_blur(a, r):
    """Separable box blur, radius r px, edge-padded (cumsum, no scipy).
    Cumsum in float64: a float32 running sum over 66M cells drifts."""
    if r < 1:
        return a
    k = 2 * r + 1
    c = np.cumsum(np.pad(a, ((r + 1, r), (0, 0)), mode="edge"), axis=0,
                  dtype=np.float64)
    a = (c[k:] - c[:-k]) / k
    c = np.cumsum(np.pad(a, ((0, 0), (r + 1, r)), mode="edge"), axis=1,
                  dtype=np.float64)
    return ((c[:, k:] - c[:, :-k]) / k).astype(np.float32)


def _shift_maxfill(a, s, axis):
    """a shifted by +s along axis, vacated cells filled with -inf (the
    identity for max: beyond the map there is no steep cell)."""
    out = np.full_like(a, -np.inf)
    src = [slice(None)] * a.ndim
    dst = [slice(None)] * a.ndim
    src[axis] = slice(s, None)
    dst[axis] = slice(None, a.shape[axis] - s)
    out[tuple(dst)] = a[tuple(src)]
    return out


def _one_sided_max(a, L, axis):
    """Windowed max over [x, x+L), EXACT, O(log L) full-array ops (the
    sparse-table two-block trick). The naive 121-shift stack was 32 GB
    at 8129 squared; this peaks at two extra arrays."""
    k = max(L.bit_length() - 1, 0)
    p = 1 << k
    f = a
    for i in range(k):
        f = np.maximum(f, _shift_maxfill(f, 1 << i, axis))
    if p == L:
        return f
    return np.maximum(f, _shift_maxfill(f, L - p, axis))


def max_filter(a, r):
    """Separable running-max over a (2r+1) square window, exact,
    memory-safe. Window [-r, +r] along an axis = max(forward window of
    length r+1, backward window of length r+1 on the reversed array)."""
    if r < 1:
        return a
    out = a.astype(np.float32)
    for axis in (0, 1):
        fwd = _one_sided_max(out, r + 1, axis)
        bwd = np.flip(_one_sided_max(np.flip(out, axis), r + 1, axis), axis)
        out = np.maximum(fwd, bwd)
    return out


def slope_aspect(h_m, spacing_m):
    gy, gx = np.gradient(h_m.astype(np.float32), spacing_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # aspect: downhill direction, radians, 0 = +Y ("north" = map +Y).
    aspect = np.arctan2(-gx, -gy)
    return slope, aspect


def shaded_aspect_rad(sun_azimuth_deg):
    """The downhill direction of the SHADED aspect, in `aspect`'s frame.

    DERIVED, not a map axis (audit 2026-09-11 finding 1). The physical
    driver of snow-line asymmetry is which flank the sun misses, so the
    axis comes from `lighting.sun.azimuth_deg` -- which is the light
    actor's YAW, the direction light TRAVELS (ue-api-resolution's datum
    list: the sun sits at azimuth-180). A slope whose downhill points
    along the travel direction faces AWAY from the sun: that is the
    shaded aspect, and it holds snow lowest.

    `aspect` is atan2(dx, dy) -- angle from map +Y toward +X -- so the
    travel vector (cos az, sin az) maps to atan2(cos az, sin az).
    """
    az = math.radians(float(sun_azimuth_deg))
    return math.atan2(math.cos(az), math.sin(az))


def _wet_shore(h_m, water, spacing_m):
    """The wet_shore mask: union over placed lakes of each lake's damp
    shoreline ring. `water` is a list of (level_m, footprint_bool) with the
    footprint at h_m's resolution; None/empty -> identically zero (the
    pre-Brief-4 behaviour, so the selftest's no-water specimens still read
    zero). Dilation is a square running-max (max_filter) rather than scipy so
    the core stays dependency-light and memory-safe at 8129^2."""
    wet = np.zeros(h_m.shape, dtype=np.float32)
    if not water:
        return wet
    r_px = max(1, int(round(WET_SHORE_RING_M / spacing_m)))
    for level_m, fp in water:
        fp = np.asarray(fp, dtype=bool)
        if fp.shape != h_m.shape:
            raise ValueError("wet_shore footprint shape %s != heightmap %s"
                             % (fp.shape, h_m.shape))
        # collar = the dilated footprint region. We do NOT subtract fp:
        # `above` drops the submerged interior, and a fine-grid cell INSIDE
        # the coarse footprint that pokes above the level IS genuine shore
        # (auditor 2026-09-19 finding 1).
        collar = max_filter(fp.astype(np.float32), r_px) > 0.5
        above = h_m >= float(level_m)          # exposed shore, not underwater
        # 1 at the waterline, fading to 0 by BAND_M above it
        strength = 1.0 - smoothstep(0.0, WET_SHORE_BAND_M,
                                    h_m - float(level_m))
        lake_wet = np.where(collar & above, strength, 0.0).astype(np.float32)
        wet = np.maximum(wet, lake_wet)
    return wet


def derive(h_m, spacing_m, flow01, depo01, cover01, snow_base_m=SNOW_BASE_M,
           shaded_rad=0.0, water=None):
    """The eight masks + precedence normalisation. Pure function of its
    inputs so the selftest runs it on synthetic terrain unchanged.
    REFUSES non-finite input: a NaN heightmap must not produce weights
    (direction 3 -- NaN propagates through every comparison as False and
    would yield a plausible all-meadow map)."""
    if not np.isfinite(h_m).all():
        raise ValueError("heightmap holds non-finite values -- refusing "
                         "to derive weights from it")
    slope, aspect = slope_aspect(h_m, spacing_m)

    # lowest snow line on the SHADED aspect (cos -> 1 there).
    line = snow_base_m - SNOW_ASPECT_HALF_M * np.cos(aspect - shaded_rad)
    snow = (smoothstep(-SNOW_FEATHER_M, SNOW_FEATHER_M, h_m - line)
            * (1.0 - smoothstep(30.0, 40.0, slope)))

    rock = smoothstep(ROCK_DEG[0], ROCK_DEG[1], slope)

    steep_h = np.where(slope > SCREE_SOURCE_DEG, h_m, -np.inf)
    r_px = max(1, int(round(SCREE_RUNOUT_M / spacing_m)))
    steep_near_h = max_filter(steep_h, r_px)
    scree_band = (smoothstep(SCREE_DEG[0] - 3, SCREE_DEG[0] + 3, slope)
                  * (1.0 - smoothstep(SCREE_DEG[1] - 3, SCREE_DEG[1] + 3,
                                      slope)))
    scree = np.where(steep_near_h > h_m + 1.0, scree_band, 0.0)

    forest = smoothstep(CANOPY_COVER_BAND[0], CANOPY_COVER_BAND[1], cover01)

    wet = _wet_shore(h_m, water, spacing_m)        # shoreline ring (Brief 4 T4)
    path = np.zeros_like(h_m, dtype=np.float32)    # DECLARED ZERO (no mask)

    gravel = (np.clip(depo01, 0.0, 1.0)
              * (1.0 - smoothstep(GRAVEL_MAX_SLOPE_DEG - 4,
                                  GRAVEL_MAX_SLOPE_DEG + 4, slope))
              * (1.0 - smoothstep(snow_base_m - 200, snow_base_m, h_m)))

    ordered = [("snow", snow), ("rock", rock), ("scree", scree),
               ("forest_floor", forest), ("wet_shore", wet),
               ("dirt_path", path), ("gravel", gravel)]
    remainder = np.ones_like(h_m, dtype=np.float32)
    weights = {}
    for name, m in ordered:
        w = np.clip(m, 0.0, 1.0).astype(np.float32) * remainder
        weights[name] = w
        remainder = remainder - w
    weights["meadow"] = np.clip(remainder, 0.0, 1.0)
    return weights, slope, aspect


def canopy_cover(shape, spacing_m, plans, origin_m, crown_r_m):
    """Canopy cover 0..1: each instance splats its crown DISK AREA into
    the cell grid (as area / cell area), then a crown-radius box blur
    spreads it; the result approximates local crown-area coverage."""
    cover = np.zeros(shape, dtype=np.float32)
    cell_area = spacing_m * spacing_m
    disk_area = math.pi * crown_r_m * crown_r_m
    n = 0
    for path in plans:
        doc = json.load(open(path, encoding="utf-8"))
        for inst in doc.get("instances", []):
            x_cm, y_cm = float(inst[0]), float(inst[1])
            px = int(round((x_cm / 100.0 - origin_m[0]) / spacing_m))
            py = int(round((y_cm / 100.0 - origin_m[1]) / spacing_m))
            if 0 <= py < shape[0] and 0 <= px < shape[1]:
                cover[py, px] += disk_area / cell_area
                n += 1
    r_px = max(1, int(round(crown_r_m / spacing_m)))
    cover = box_blur(cover, r_px)
    # blur conserves sum; convert to coverage by capping at full cover
    return np.clip(cover, 0.0, 1.0), n


def load_lake_footprints(rec, target_shape):
    """Return [{"id","level_m","area_ha","mask"}] for each placed lake, the
    mask a bool array at target_shape (the shipped 8129 grid), for wet_shore.

    THE FOOTPRINT IS A LAKE'S CONNECTED SUBMERGED COMPONENT, produced by
    hydro_derive.level_slice -- the hydrology tool of record -- on the
    COMMITTED 4x analysis heightmap, NOT re-flood-filled here (NN24: one
    derivation of a physical fact). hydro_derive is imported lazily so the
    selftest and the offline suite never require scipy/scikit-image.

    THE 2033 MASK IS UPSAMPLED TO 8129 BY EXACT VERTEX INDEXING
    (np.round(np.linspace(...)) row/col indices, not a PIL pixel-center
    resize): 8129 = 4*2032+1, and the 4x export is a CENTRED downsample
    (output vertex i == input vertex 4*i, no half-pixel shift -- sidecar
    image.method), so output vertex 4k maps to source vertex k EXACTLY and the
    2033 vertices are an exact subset of the 8129 grid. The footprint is only
    an ADJACENCY
    LOCALIZER; the precise damp band is cut from the shipped heightmap in
    _wet_shore, so neither the 4x->8k resolution gap nor the tiny T3 pool-lip
    carve (0.32 m, away from the shorelines) perturbs the result.

    POSITIVE CONTROL (rule 13 / verification-practice): each footprint's area
    must reproduce water.json's area_ha (<=0.2 ha), else refuse. level_slice
    rounds area to 0.1 ha and uses the same defaults water_derive locked, so a
    match is expected and a MISS means the reuse has silently drifted."""
    wp = rec.get("water")
    if not isinstance(wp, dict) or "from_water_recipe" not in wp:
        return []
    water = json.load(open(os.path.join(REPO, wp["from_water_recipe"]),
                           encoding="utf-8"))
    side_rel = os.path.join("research", "brief4", "input",
                            "alpine_8k_height_4x.json")
    side = json.load(open(os.path.join(REPO, side_rel), encoding="utf-8"))
    cell = float(side["image"]["metres_per_pixel"])
    mpu = float(side["z_mapping"]["metres_per_16bit_unit"])
    z0 = float(side["z_mapping"]["height_m_of_unit_0"])
    png = os.path.join(REPO, "research", "brief4", "input",
                       side["image"]["path"])

    hd_dir = os.path.join(REPO, "research", "brief4", "scripts")
    if hd_dir not in sys.path:
        sys.path.insert(0, hd_dir)
    import hydro_derive as hd   # tool of record; reused, not reimplemented

    h4 = np.asarray(Image.open(png)).astype(np.float64) * mpu + z0
    hf = hd.fill_sinks(h4)
    _L, lab, _d = hd.lakes(h4, hf, cell)   # hydro_derive defaults (2.0 m, 4000 m2)
    out = []
    for lk in water.get("lakes", []):
        sl = hd.level_slice(lab, h4, int(lk["id"]), float(lk["level_m"]), cell)
        if sl is None:
            raise ValueError("level_slice returned None for lake %s -- the "
                             "4x label set has no such lake at that level"
                             % lk["id"])
        got, want = float(sl["area_ha"]), float(lk["area_ha"])
        if abs(got - want) > 0.2:
            raise ValueError("wet_shore footprint control FAILED for lake %s: "
                             "%.1f ha derived vs %.1f ha in water.json -- the "
                             "hydro reuse has drifted, refusing" %
                             (lk["id"], got, want))
        m2033 = sl["mask"].astype(bool)
        # EXACT vertex-aligned nearest upsample (NOT a PIL pixel-center
        # resize, which deviates up to one 4x cell at the edges -- auditor
        # 2026-09-19 finding 3): 8129 = 4*2032+1, so output vertex 4k maps to
        # source vertex k exactly; intermediate outputs round to the nearest
        # source vertex (<0.5 of a 4x cell).
        ry = np.round(np.linspace(0, m2033.shape[0] - 1,
                                  target_shape[0])).astype(np.intp)
        cx = np.round(np.linspace(0, m2033.shape[1] - 1,
                                  target_shape[1])).astype(np.intp)
        m8k = m2033[np.ix_(ry, cx)]
        out.append({"id": int(lk["id"]), "level_m": float(lk["level_m"]),
                    "area_ha": round(got, 1), "mask": m8k})
    return out


def selftest():
    """Synthetic terrain, two decoupled specimens so no assertion leans
    on another layer's precedence:

    A. SNOW: a N/S ridge (crest at y=N/2, ~19 deg flanks), snow base
       chosen so the aspect-shifted lines straddle the flanks. Assert
       north >> south at the SAME height band.
    B. EVERYTHING ELSE: same ridge with snow pushed out of the world
       (base 5000 m), plus a 50 m cliff at x~180 (apron beyond it, lower)
       a dense stand, and a deposit fan. Scree is asserted GEOMETRICALLY
       (in the 60 m band beyond/below the cliff; absent far beyond and
       absent UPHILL of it) -- an independent statement of the rule, not
       a re-run of derive's own operator (the six-self-referential-
       properties lesson)."""
    N = 256
    sp = 1.0
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    # plateau-topped ridge: FLAT crest strip (yy 98..158, slope 0) for
    # the gravel/meadow tests, 24.2 deg flanks (INSIDE the 20-32 scree
    # band) for the scree tests. 19 deg flanks failed the first run --
    # every scree mask was empty because the whole specimen sat below
    # the band, which the -1 sentinels made loud.
    ridge = 800.0 - np.maximum(np.abs(yy - N / 2) - 30.0, 0.0) * 0.45
    ok = True

    def check(name, cond):
        nonlocal ok
        print("  %-56s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and bool(cond)

    zeros = np.zeros((N, N), dtype=np.float32)

    # --- A: snow asymmetry ------------------------------------------------
    # Sun due WEST in UE terms (yaw 270 = light travelling -Y), so the
    # SHADED flank is the one whose downhill points -Y: the y < N/2 side.
    # Asserted against an INDEPENDENT predicate (which side of the crest),
    # and the EXPECTED side is derived from the azimuth, so a sign flip
    # anywhere in gy/aspect/cos/shaded_rad fails this.
    shaded = shaded_aspect_rad(270.0)
    wA, slopeA, _ = derive(ridge, sp, zeros, zeros, zeros,
                           snow_base_m=780.0, shaded_rad=shaded)
    band = (ridge > 760) & (ridge < 780) & (slopeA > 5)
    minus_y = band & (yy < N / 2)   # downhill -Y == the shaded flank
    plus_y = band & (yy > N / 2)
    sn_sh = float(wA["snow"][minus_y].mean()) if minus_y.any() else 0
    sn_lit = float(wA["snow"][plus_y].mean()) if plus_y.any() else 0
    check("A: snow SHADED (%.2f) >> snow LIT (%.2f) at sun az 270"
          % (sn_sh, sn_lit), sn_sh > sn_lit + 0.5)
    # and the axis FOLLOWS the sun: flip the azimuth, flip the flanks.
    wA2, _, _ = derive(ridge, sp, zeros, zeros, zeros, snow_base_m=780.0,
                       shaded_rad=shaded_aspect_rad(90.0))
    sn_sh2 = float(wA2["snow"][plus_y].mean()) if plus_y.any() else 0
    check("A: flipping the sun flips the snowy flank (%.2f)" % sn_sh2,
          sn_sh2 > sn_sh - 0.05)
    totalA = sum(wA[k] for k in wA)
    check("A: weights sum to 1 (max err %.1e)"
          % float(np.abs(totalA - 1).max()),
          float(np.abs(totalA - 1).max()) < 1e-4)

    # --- B: rock / scree / forest / gravel / meadow -----------------------
    h = ridge - smoothstep(178.0, 186.0, xx) * 50.0   # cliff then lower apron
    cover = zeros.copy()
    cover[40:60, 40:60] = 1.0                          # dense stand (flank)
    depo = zeros.copy()
    depo[108:122, 210:240] = 0.8                       # fan on the FLAT crest
    wB, slopeB, _ = derive(h, sp, zeros, depo, cover, snow_base_m=5000.0)

    check("B: snow absent by construction (max %.2f)"
          % float(wB["snow"].max()), float(wB["snow"].max()) < 0.01)
    totalB = sum(wB[k] for k in wB)
    check("B: weights sum to 1 (max err %.1e)"
          % float(np.abs(totalB - 1).max()),
          float(np.abs(totalB - 1).max()) < 1e-4)

    cliff_px = slopeB > 40
    check("B: the cliff exists (%d px > 40 deg)" % int(cliff_px.sum()),
          int(cliff_px.sum()) > 200)
    check("B: rock claims the cliff (mean %.2f)"
          % float(wB["rock"][cliff_px].mean()),
          float(wB["rock"][cliff_px].mean()) > 0.8)

    # --- B2: scree on a clean single slope --------------------------------
    # A plane dipping +x at 24.2 deg (inside the scree band) with an
    # extra 50 m cliff drop at x 178-186. On THIS geometry "uphill of
    # the cliff" is unambiguous: every steep cell is lower than every
    # x<178 cell, so scree there must be zero. (The first ridge specimen
    # taught why: crest-adjacent cliff cells sit diagonally ABOVE flank
    # cells within the 60 m window, so the ridge has almost no true
    # uphill-of-cliff flank -- the code was right and the assertion's
    # geometry was wrong.)
    plane = 900.0 - xx * 0.45 - smoothstep(178.0, 186.0, xx) * 50.0
    wS, slopeS, _ = derive(plane, sp, zeros, zeros, zeros,
                           snow_base_m=5000.0)
    band = (slopeS > SCREE_DEG[0] + 1) & (slopeS < SCREE_DEG[1] - 1)
    apron = band & (xx > 190) & (xx < 240)
    far = band & (xx > 250)
    uphill = band & (xx > 60) & (xx < 170)
    s_ap = float(wS["scree"][apron].mean()) if apron.any() else -1
    s_far = float(wS["scree"][far].mean()) if far.any() else 1
    s_up = float(wS["scree"][uphill].mean()) if uphill.any() else 1
    check("B2: scree in the downhill apron (%.2f)" % s_ap, s_ap > 0.3)
    check("B2: scree absent beyond 60 m (%.2f)" % s_far, s_far < 0.05)
    check("B2: scree absent UPHILL of the cliff (%.2f)" % s_up,
          s_up < 0.05)

    inside = np.zeros((N, N), bool)
    inside[45:55, 45:55] = True
    open_ = np.zeros((N, N), bool)
    open_[105:125, 60:100] = True                      # flat crest, open
    ff_in = float(wB["forest_floor"][inside].mean())
    ff_out = float(wB["forest_floor"][open_].mean())
    check("B: forest_floor > 0.8 under the stand (%.2f)" % ff_in,
          ff_in > 0.8)
    check("B: forest_floor < 0.1 in the open (%.2f)" % ff_out,
          ff_out < 0.1)

    g = float(wB["gravel"][110:120, 215:235].mean())
    check("B: gravel follows the deposit fan (%.2f)" % g, g > 0.3)
    check("B: wet_shore zero (no water passed) and dirt_path zero",
          float(wB["wet_shore"].max()) == 0.0
          and float(wB["dirt_path"].max()) == 0.0)
    check("B: meadow takes the open remainder (%.2f)"
          % float(wB["meadow"][open_].mean()),
          float(wB["meadow"][open_].mean()) > 0.6)

    # --- C: wet_shore ring -- fires on the shore, NOT a global band --------
    # Terrain falls gently east (0.5 m/cell) so the above-water collar spans
    # the whole 4 m band; a lake footprint LOCALIZED in y in the SE. The
    # discriminating direction is `far`: same elevation, far from the lake ->
    # zero, which a global |h-level|<=band band would (wrongly) light up.
    Nc = 200
    yy2, xx2 = np.mgrid[0:Nc, 0:Nc].astype(np.float32)
    hc = 200.0 - 0.5 * xx2                    # h == 140 at x == 120
    level = 140.0
    fp = (hc < level) & (xx2 > 120) & (yy2 > 90) & (yy2 < 150)
    zc = np.zeros((Nc, Nc), dtype=np.float32)
    wC = derive(hc, 1.0, zc, zc, zc, snow_base_m=5000.0,
                water=[(level, fp)])[0]
    ws = wC["wet_shore"]
    shore = (xx2 >= 118) & (xx2 <= 120) & (yy2 > 100) & (yy2 < 140)  # in band
    far = (xx2 >= 118) & (xx2 <= 120) & (yy2 > 5) & (yy2 < 45)       # far in y
    lo = (xx2 >= 113) & (xx2 <= 114) & (yy2 > 100) & (yy2 < 140)     # ~3.5 m up
    check("C: wet_shore fires on the lake shore (%.2f)"
          % float(ws[shore].mean()), float(ws[shore].mean()) > 0.3)
    check("C: wet_shore ZERO on same-elev terrain far from the lake (max %.3f)"
          % float(ws[far].max()), float(ws[far].max()) < 0.01)
    check("C: wet_shore fades with height in the band (%.2f > %.2f)"
          % (float(ws[shore].mean()), float(ws[lo].mean())),
          float(ws[shore].mean()) > float(ws[lo].mean()) + 0.2)
    totalC = sum(wC[k] for k in wC)
    check("C: weights sum to 1 with wet_shore active (max err %.1e)"
          % float(np.abs(totalC - 1).max()),
          float(np.abs(totalC - 1).max()) < 1e-4)
    wC0 = derive(hc, 1.0, zc, zc, zc, snow_base_m=5000.0, water=None)[0]
    check("C: no water -> wet_shore identically zero (max %.3f)"
          % float(wC0["wet_shore"].max()),
          float(wC0["wet_shore"].max()) == 0.0)

    # --- D: --expand assertions, three directions with counts (Brief 4 T4) --
    z4 = np.zeros((4, 4), dtype=np.float32)
    snow4 = np.full((4, 4), 0.2, np.float32)
    rock4 = np.full((4, 4), 0.1, np.float32)      # stored sum 0.3
    gravel4 = np.full((4, 4), 0.05, np.float32)
    wet4 = np.full((4, 4), 0.25, np.float32)
    meadow4 = 1.0 - 0.3 - wet4 - gravel4          # closes the remainder
    try:
        _expand_check(snow4, rock4, z4, z4, wet4, z4, gravel4, meadow4)
        d1 = True
    except ValueError:
        d1 = False
    check("D1: wet_shore>0 (%d cells) + dirt_path==0 PASSES expand"
          % int((wet4 > 0).sum()), d1)
    path4 = np.full((4, 4), 0.1, np.float32)
    meadow4b = 1.0 - 0.3 - wet4 - path4 - gravel4
    try:
        _expand_check(snow4, rock4, z4, z4, wet4, path4, gravel4, meadow4b)
        d2 = False
    except ValueError:
        d2 = True
    check("D2: dirt_path>0 (%d cells) REFUSES expand"
          % int((path4 > 0).sum()), d2)
    meadow4c = 1.0 - 0.3 - gravel4
    try:
        _expand_check(snow4, rock4, z4, z4, z4, z4, gravel4, meadow4c)
        d3 = True
    except ValueError:
        d3 = False
    check("D3: wet==0 and dirt_path==0 PASSES expand (baseline)", d3)

    # direction 3: garbage in -> refuse, not crash-through
    try:
        derive(np.full((8, 8), np.nan, np.float32), sp,
               zeros[:8, :8], zeros[:8, :8], zeros[:8, :8])
        nan_ok = False
    except ValueError:
        nan_ok = True
    check("a NaN heightmap refuses", nan_ok)

    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def collapse(prefix):
    """Fold the eight derived weights into the LIVE weightmap's channel
    contract (Brief 3 Task 2, v1 integration): the material and
    place_foliage index textures/alpine_8k_weights.png by LAYER POSITION
    (Snow, Rock, Grass), so

        R = snow
        G = rock + scree
        B = forest_floor + wet_shore + dirt_path + gravel + meadow
        A = forest_floor         (the v1.25 canopy tint driver)

    R+G+B sums to 1 by construction (the eight sum to 1 and every layer
    lands in exactly one bucket); asserted before writing. Per-layer
    SURFACES (scree vs rock, gravel vs meadow) arrive with Task 3's
    scans; this collapse is recorded in the sidecar as the v1 mapping."""
    wa = np.asarray(Image.open(os.path.join(REPO, prefix + "a.png"))
                    ).astype(np.float32) / 255.0
    wb = np.asarray(Image.open(os.path.join(REPO, prefix + "b.png"))
                    ).astype(np.float32) / 255.0
    snow, rock, scree, forest = [wa[..., i] for i in range(4)]
    wet, path, gravel, meadow = [wb[..., i] for i in range(4)]
    R = snow
    G = rock + scree
    B = forest + wet + path + gravel + meadow
    total = R + G + B
    err = float(np.abs(total - 1.0).max())
    if err > 0.02:  # 8-bit quantisation of 8 channels stacks to ~< 4/255
        raise ValueError("collapsed weights do not sum to 1 (max err "
                         "%.4f) -- refusing to write a weightmap that "
                         "would tint by the shortfall" % err)
    # renormalise the residual quantisation so the shader's mask sum is 1
    R, G, B = R / total, G / total, B / total
    img = np.stack([np.round(np.clip(c, 0, 1) * 255).astype(np.uint8)
                    for c in (R, G, B, forest)], axis=-1)
    out = os.path.join(REPO, "textures", "alpine_8k_weights.png")
    Image.fromarray(img, "RGBA").save(out)
    print("wrote textures/alpine_8k_weights.png (RGBA, collapsed; "
          "quantisation err %.4f renormalised)" % err)
    return 0


def _expand_check(snow, rock, scree, forest, wet, path, gravel, meadow):
    """The FIVE-LAYER shipped-weightmap assertions, as a pure function so the
    selftest can drive all three failure directions without writing PNGs.
    Returns (remainder, over, gap); raises ValueError on any violation.

    AMENDED 2026-09-19 (Brief 4 T4). Previously BOTH wet_shore and dirt_path
    had to be identically zero. wet_shore is now a DERIVED shoreline ring, so
    it may be non-zero; it FOLDS INTO THE REMAINDER (renders as meadow/grass
    at blockout) until the material pass gives it its own surface, and the
    remainder identity now names it explicitly. dirt_path STAYS required-zero:
    it still has no mask (streets are actors), so a non-zero dirt_path is a
    real defect that must refuse.

    What is asserted, and why each can fail:
      1. R+G+B+A <= 1 within quantisation -- else the shader remainder goes
         negative and that layer renders as a black bruise.
      2. the remainder EQUALS wet_shore+dirt_path+gravel+meadow from w8b --
         the claim that all of the non-stored layers fold into the remainder,
         checked against the OTHER file rather than asserted in prose. If
         wet_shore is dropped from this sum the check false-passes only when
         wet_shore is zero, so the amendment is load-bearing.
      3. dirt_path is still identically ZERO -- the reason it is not a layer.
    """
    total = snow + rock + scree + forest
    over = float((total - 1.0).max())
    if over > 0.02:
        raise ValueError("the four stored channels exceed 1 by %.4f -- the "
                         "shader remainder would go NEGATIVE and that layer "
                         "renders as a black bruise" % over)

    remainder = 1.0 - total
    expect = wet + path + gravel + meadow
    gap = float(np.abs(remainder - expect).max())
    if gap > 0.02:
        raise ValueError("the derived remainder disagrees with "
                         "wet_shore+dirt_path+gravel+meadow by %.4f -- "
                         "'the non-stored layers fold into the remainder' is "
                         "then a claim the data does not support" % gap)

    mx = float(path.max())
    if mx > 0.004:   # 1/255
        raise ValueError(
            "dirt_path is no longer identically zero (max %.4f). It has no "
            "mask (streets are actors); that reason has expired and the "
            "omission must be re-decided, not carried." % mx)
    return remainder, over, gap


def feather_stored_channels(channels, sigma):
    """Gaussian-feather the four STORED weightmap channels and renormalise so
    their per-texel sum never exceeds 1.

    Brief 7 Phase 1 (2026-09-24). The imported composite weightmap was
    NEAR-BINARY -- ~83-98% of texels pure 0 or 255 per channel -- so two
    surfaces met along a HARD 1 m mask edge, which shattered the terrain into
    ~1 m blocks under minification (research/brief7/p1_block_diff.md,
    feather_handoff.md). A Gaussian of `sigma` TEXELS turns each boundary into
    a ~2*sigma m cross-fade so neighbouring surfaces ramp into one another.

      channels : sequence of 4 float arrays in [0,1] (snow, rock, scree,
                 forest_floor -- the stored weightmap channels R,G,B,A).
      sigma    : Gaussian sigma in TEXELS (1 texel == 1 m at this landscape;
                 1.5 -> ~3 m ramps).

    Returns (feathered list of 4 arrays, remainder array, max_sum_over_1).
    The meadow/Grass layer is the SHADER remainder (1 - sum(stored)); the
    renormalisation is what keeps that remainder >= 0 after the blur pushes
    the sum above 1 at convex corners where three layers meet.
    """
    if not sigma > 0.0:
        raise ValueError(
            "weightmap_feather_sigma_px must be > 0; got %r. Zero/absent is "
            "the RETIRED near-binary argmax path that shatters the terrain "
            "into ~1 m blocks (research/brief7/p1_block_diff.md)." % (sigma,))
    feathered = [gaussian_filter(np.asarray(c, dtype=np.float32), sigma)
                 for c in channels]
    s = feathered[0] + feathered[1] + feathered[2] + feathered[3]
    over = float((s - 1.0).max())
    # A convex Gaussian keeps each channel in [0,1], but the SUM of four
    # independently-blurred channels can exceed 1 at a corner where three
    # layers meet. Scale exactly those texels back to 1 so the remainder
    # (1 - sum) never goes negative -- a negative remainder renders as a
    # black bruise (the failure _expand_check assertion 1 guards on the
    # source). Below 1 the sum is untouched, so the feather is preserved.
    scale = np.where(s > 1.0, 1.0 / np.maximum(s, 1e-9), 1.0).astype(np.float32)
    feathered = [c * scale for c in feathered]
    remainder = 1.0 - (feathered[0] + feathered[1]
                       + feathered[2] + feathered[3])
    return feathered, remainder, over


def expand(prefix):
    """Write the FIVE-LAYER live weightmap (Brief 3 Task 3, 2026-09-12).

    `collapse` was the v1 mapping, and its own docstring said per-layer
    surfaces "arrive with Task 3's scans". They have. This is what
    replaces it:

        R = snow            G = rock           B = scree
        A = forest_floor    meadow = 1-(R+G+B+A), DERIVED IN THE SHADER

    THE CHANNELS ARE ALREADY THIS. `w8a` was written with exactly this
    contract, so expanding is a COPY plus the `_expand_check` assertions,
    not a recomputation -- there is no second derivation to disagree with
    the first.

    THE REMAINDER IS NOT STORED. A fifth channel would be a fifth number
    obliged to agree with four others, and 8-bit quantisation guarantees
    it sometimes would not (NN24). Deriving it in the shader makes the
    masks sum to 1 by construction.

    wet_shore (Brief 4 T4) is now a real derived layer, but it is NOT one
    of the four stored channels -- there is no free channel and no shore
    SURFACE asset yet -- so it folds into the shader remainder alongside
    gravel. The written PNG is therefore byte-identical whether or not
    wet_shore is populated; promoting it to its own stored surface is a
    MATERIAL-PASS item (R-LAYERS5 WHAT IS NOT DONE).
    """
    rec = json.load(open(RECIPE, encoding="utf-8"))
    try:
        sigma = float(rec["material"]["weightmap_feather_sigma_px"])
    except (KeyError, TypeError, ValueError):
        raise SystemExit(
            "REFUSE: recipes/alpine_8k.json material.weightmap_feather_sigma_px "
            "is absent or non-numeric. That field selects the FEATHERED bake; "
            "its absence is the retired near-binary argmax path that shatters "
            "the terrain into ~1 m blocks (research/brief7/p1_block_diff.md).")

    wa = np.asarray(Image.open(os.path.join(REPO, prefix + "a.png"))
                    ).astype(np.float32) / 255.0
    wb = np.asarray(Image.open(os.path.join(REPO, prefix + "b.png"))
                    ).astype(np.float32) / 255.0
    snow, rock, scree, forest = [wa[..., i] for i in range(4)]
    wet, path, gravel, meadow = [wb[..., i] for i in range(4)]

    # Assert the SOURCE partition FIRST, on the UNFEATHERED channels. Assertion
    # 2 (remainder == wet+path+gravel+meadow) is a claim about the w8 SOURCE
    # decomposition; the feather deliberately redistributes mass into the
    # remainder near boundaries, so it does NOT survive feathering and must be
    # checked here, before the blur. The feathered result is guarded separately.
    remainder0, over0, gap = _expand_check(snow, rock, scree, forest,
                                           wet, path, gravel, meadow)

    feathered, remainder, over = feather_stored_channels(
        [snow, rock, scree, forest], sigma)
    rmin = float(remainder.min())
    if rmin < -1.0 / 255.0:
        raise ValueError(
            "feathered stored channels sum to more than 1 (remainder min "
            "%.4f) -- the meadow remainder would go NEGATIVE and render as a "
            "black bruise; the renormalisation should have prevented this"
            % rmin)

    out = os.path.join(REPO, "textures", "alpine_8k_weights.png")
    stack = np.stack([np.clip(c, 0.0, 1.0) for c in feathered], axis=-1)
    img = np.round(stack * 255).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(out)
    fsnow, frock, fscree, fforest = feathered
    cov = {"snow": float(fsnow.mean()), "rock": float(frock.mean()),
           "scree": float(fscree.mean()), "forest_floor": float(fforest.mean()),
           "wet_shore_in_remainder": float(wet.mean()),
           "meadow_remainder": float(remainder.mean())}
    print("wrote textures/alpine_8k_weights.png (RGBA, FIVE-LAYER contract, "
          "feathered sigma=%.2f px)" % sigma)
    print("  source sum(stored) max over 1: %.5f   remainder vs "
          "wet+path+gravel+meadow: %.5f" % (over0, gap))
    print("  feathered sum(stored) max over 1 (pre-scale): %.5f   "
          "remainder min: %.5f" % (over, rmin))
    for k, v in cov.items():
        print("  %-24s %6.2f%%" % (k, 100.0 * v))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--collapse", action="store_true",
                    help="v1 THREE-layer mapping: G=rock+scree, "
                         "B=everything else. SUPERSEDED by --expand")
    ap.add_argument("--expand", action="store_true",
                    help="the FIVE-layer contract: R=snow G=rock B=scree "
                         "A=forest_floor, meadow as the shader remainder")
    ap.add_argument("--out-prefix", default="textures/alpine_8k_w8")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    # os.path.join(REPO, a.out_prefix) SILENTLY discards REPO on an absolute
    # prefix (and "../" escapes it), so resolve-and-check before any write
    # (auditor 2026-09-19 finding 2).
    op_abs = os.path.abspath(os.path.join(REPO, a.out_prefix))
    try:
        inside = os.path.commonpath([op_abs, REPO]) == REPO
    except ValueError:
        inside = False   # a different drive raises; treat as outside the repo
    if not inside:
        print("REFUSE: --out-prefix resolves outside the repo (%s)" % op_abs)
        return 2
    if a.collapse and a.expand:
        print("REFUSE: --collapse and --expand write the SAME file with "
              "DIFFERENT channel contracts; pick one")
        return 2
    if a.collapse:
        return collapse(a.out_prefix)
    if a.expand:
        return expand(a.out_prefix)

    rec = json.load(open(RECIPE, encoding="utf-8"))
    ls = rec["landscape"]
    spacing_m = float(ls["scale_xy_cm"]) / 100.0
    origin_m = (float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0)
    z_span_m = float(ls["z_scale_cm"]) / 100.0
    z_base_m = (float(ls["location_cm"][2]) - float(ls["z_scale_cm"]) / 2.0) / 100.0

    hpath = os.path.join(REPO, rec["heightmap"]["source"])
    h16 = np.asarray(Image.open(hpath)).astype(np.float32)
    if h16.ndim != 2:
        print("REFUSE: heightmap is not single-channel")
        return 3
    h_m = h16 / 65535.0 * z_span_m + z_base_m
    if not np.isfinite(h_m).all():
        print("REFUSE: heightmap holds non-finite values")
        return 3
    shape = h_m.shape
    print("heightmap %s  spacing %.1f m  z %.1f..%.1f m"
          % (shape, spacing_m, float(h_m.min()), float(h_m.max())))

    def load01(rel):
        p = os.path.join(REPO, rel)
        a16 = np.asarray(Image.open(p).convert("I")).astype(np.float32)
        if a16.shape != shape:
            im = Image.fromarray(a16)
            a16 = np.asarray(im.resize((shape[1], shape[0]),
                                       Image.BILINEAR)).astype(np.float32)
        return a16 / max(float(a16.max()), 1e-6)

    # flow is RESERVED (audit F3): the brief gates wet_shore on Brief 4's
    # water level and gravel on deposition; nothing reads flow yet, so it
    # is neither loaded nor claimed as an input.
    depo = load01("terrain/alpine_8k_deposition.png")
    flow = np.zeros_like(depo)

    # The snow floor comes from the RECIPE's Snow band, not a local copy.
    snow_layer = [l for l in rec["material"]["layers"]
                  if l["name"] == "Snow"]
    if not snow_layer:
        print("REFUSE: the recipe declares no Snow layer to take the "
              "snow-line floor from")
        return 2
    snow_base = float(snow_layer[0]["height_m"][0])
    sun_az = float(rec["lighting"]["sun"]["azimuth_deg"])
    shaded = shaded_aspect_rad(sun_az)
    print("snow floor %.0f m (from the recipe's Snow band); sun azimuth "
          "%.1f deg -> shaded aspect %.1f deg from +Y"
          % (snow_base, sun_az, math.degrees(shaded)))

    # Crown radius from the recipe's REAL location, foliage.canopy.radius_m.
    # Was `placement_priors.canopy.radius_m` (2026-09-16 D-4 finding): that key
    # never existed (only inside a _comment), so the `else 3.068` fallback fired
    # every run -- LATENT only because foliage.canopy.radius_m == 3.068 today, but
    # a recipe edit would have been silently ignored (pipeline rule 2 drift). The
    # planting-field contract's derive_planting_field already reads the right key;
    # this fixes the SEED too (rule 9 containment).
    crown_r = float(rec["foliage"]["canopy"]["radius_m"]) \
        if rec.get("foliage", {}).get("canopy") else 3.068
    plans = [os.path.join(REPO, "foliage", "alpine_8k_%s.json" % s)
             for s in ("Conifer", "ConiferPine", "SpruceSub",
                       "SpruceSapling")]
    plans = [p for p in plans if os.path.isfile(p)]
    cover, n_inst = canopy_cover(shape, spacing_m, plans, origin_m, crown_r)
    print("canopy: %d instances splatted, crown %.2f m, cover p99 %.2f"
          % (n_inst, crown_r, float(np.percentile(cover, 99))))

    lakes = load_lake_footprints(rec, shape)
    _wptr = rec.get("water")
    water_recipe_rel = (_wptr.get("from_water_recipe")
                        if isinstance(_wptr, dict) else None)
    if lakes:
        print("wet_shore: %d placed lakes (band %.1f m, ring %.1f m)"
              % (len(lakes), WET_SHORE_BAND_M, WET_SHORE_RING_M))
        for lk in lakes:
            print("  lake %d @ %.1f m  footprint %.1f ha  %d cells"
                  % (lk["id"], lk["level_m"], lk["area_ha"],
                     int(lk["mask"].sum())))
    elif water_recipe_rel is None:
        print("wet_shore: no water recipe pointer -> declared zero")
    else:
        # pointer resolved but produced zero footprints: refuse rather than
        # silently derive an all-zero wet_shore (rule 13; auditor finding 4).
        print("REFUSE: water recipe %s is present but yielded ZERO lake "
              "footprints -- wet_shore would be silently zero" % water_recipe_rel)
        return 2
    water = [(lk["level_m"], lk["mask"]) for lk in lakes]

    weights, slope, aspect = derive(h_m, spacing_m, flow, depo, cover,
                                    snow_base_m=snow_base,
                                    shaded_rad=shaded, water=water)

    A = ["snow", "rock", "scree", "forest_floor"]
    B = ["wet_shore", "dirt_path", "gravel", "meadow"]
    outs = {}
    for suffix, names in (("a", A), ("b", B)):
        img = np.stack([np.round(weights[n] * 255).astype(np.uint8)
                        for n in names], axis=-1)
        rel = a.out_prefix + suffix + ".png"
        Image.fromarray(img, "RGBA").save(os.path.join(REPO, rel))
        outs[suffix] = rel
        print("wrote %s" % rel)

    side = {
        "_what": ("Eight DERIVED layer weights (Brief 3 Task 2, sec "
                  "3.4-3.6). Weights sum to 1; precedence and formulas "
                  "in derive_layer_weights docstring; nothing painted."),
        "inputs": {"heightmap": rec["heightmap"]["source"],
                   "flow": "RESERVED, not read (gravel uses deposition; "
                           "wet_shore uses water.json levels + hydro "
                           "footprints, not flow)",
                   "water_recipe": water_recipe_rel,
                   "deposition": "terrain/alpine_8k_deposition.png",
                   "foliage_plans": [os.path.relpath(p, REPO) for p in plans],
                   "crown_radius_m": crown_r,
                   "instances": n_inst},
        "channels": {"a": A, "b": B, "files": outs},
        "constants": {"snow_base_m": snow_base,
                      "_snow_base_m": "read from the recipe's Snow band "
                                      "floor, not a local constant",
                      "sun_azimuth_deg": sun_az,
                      "shaded_aspect_deg_from_plus_y":
                          round(math.degrees(shaded), 2),
                      "_shaded_aspect": "DERIVED from the sun azimuth "
                                        "(the light's travel yaw; the "
                                        "shaded flank faces along it), "
                                        "never a map axis",
                      "snow_aspect_half_m": SNOW_ASPECT_HALF_M,
                      "rock_deg": ROCK_DEG, "scree_deg": SCREE_DEG,
                      "scree_source_deg": SCREE_SOURCE_DEG,
                      "scree_runout_m": SCREE_RUNOUT_M,
                      "canopy_cover_band": CANOPY_COVER_BAND,
                      "gravel_max_slope_deg": GRAVEL_MAX_SLOPE_DEG,
                      "wet_shore_band_m": WET_SHORE_BAND_M,
                      "wet_shore_ring_m": WET_SHORE_RING_M},
        "wet_shore": {
            "_what": ("damp shoreline ring of each placed lake (Brief 4 T4): "
                      "adjacent to the lake footprint AND within "
                      "wet_shore_band_m above the water level; NOT a global "
                      "elevation band"),
            "levels_from": water_recipe_rel,
            "footprints_from": ("hydro_derive.level_slice on the committed 4x "
                                "analysis heightmap (the hydrology tool of "
                                "record); positive control vs water.json "
                                "area_ha"),
            "lakes": [{"id": lk["id"], "level_m": lk["level_m"],
                       "footprint_ha": lk["area_ha"],
                       "footprint_cells_8k": int(lk["mask"].sum())}
                      for lk in lakes],
            "renders_as": ("folds into the shader remainder (meadow/grass) at "
                           "blockout; a distinct shore surface is a "
                           "material-pass item (R-LAYERS5)")},
        "declared_zero": {
            "dirt_path": "no path mask exists; the town's streets are "
                         "ACTORS, not a landscape layer"},
        "units_note": ("the brief's forest-floor threshold '0.3 "
                       "crowns/m2' is read as 0.3 crown-area COVER (a "
                       "canopy-cover figure); 0.3 trees/m2 is denser "
                       "than any forest"),
        "coverage_fraction": {k: round(float(v.mean()), 4)
                              for k, v in weights.items()},
    }
    sp_path = os.path.join(REPO, a.out_prefix + "_sidecar.json")
    with open(sp_path, "w", encoding="utf-8") as fh:
        json.dump(side, fh, indent=1)
    print("wrote %s" % os.path.relpath(sp_path, REPO))
    for k, v in side["coverage_fraction"].items():
        print("  %-14s %6.2f%%" % (k, v * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
