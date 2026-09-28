"""measure_concept_look.py — MEASURE the look of a concept image so the
recipe can carry it (albedo, water, sky, fog, skyline) instead of the
fixed highland template in forge_tool/assemble_recipe.py.

OFFLINE. numpy + PIL only. Writes ONE JSON. Nothing here is a judgement:
every number is a statistic of the pixels, labelled MEASURED, with the
band it came from. The mapping from these numbers to recipe fields is
the caller's (assemble_recipe / inject_lighting) and stays AUTHORED.

What it measures
  sky          sRGB->linear mean of the top band, and a 5-stop vertical
               gradient (zenith .. horizon) for SkyAtmosphere tuning
  skyline      per-column row of the sky/land boundary (0..1 of height),
               found as the first row where the pixel leaves the sky
               colour model. Drives composition scoring and placement
               height correction.
  palette      linear RGB medians of the ground in three depth bands
               (near / mid / far), each split into lit and shadow halves
               by luma — the Grass/Rock/Snow base_color candidates
  water        detection of a low-saturation, high-symmetry mirror band
               across the middle-lower frame; its linear colour, its
               top row (the far shore, i.e. the water's horizon) and
               vertical extent
  haze         min-luma rise near->far (same instrument as
               analyse_concept) plus the row where contrast collapses
               (the fog datum in image space)
  grade        whole-frame stats a post-process pass can match:
               mean/std luma, saturation, shadow tint, highlight tint

Usage
  python measure_concept_look.py concept.jpg --out concept_look.json
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
from PIL import Image


def srgb_to_linear(x):
    x = np.asarray(x, dtype=np.float64)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.asarray(x, dtype=np.float64)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def luma(lin):
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def saturation(lin):
    mx = lin.max(axis=-1)
    mn = lin.min(axis=-1)
    return np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)


def load(path):
    im = Image.open(path).convert("RGB")
    s = np.asarray(im).astype(np.float64) / 255.0
    return s, srgb_to_linear(s)


def r3(v):
    return [round(float(x), 4) for x in v]


# --------------------------------------------------------------- sky ------

def measure_sky(lin, top_frac=0.12):
    h = lin.shape[0]
    band = lin[: max(1, int(h * top_frac))]
    stops = []
    for k in range(5):
        r0 = int(h * 0.35 * k / 5)
        r1 = int(h * 0.35 * (k + 1) / 5)
        rows = lin[r0:max(r1, r0 + 1)]
        # only sky-like pixels: bright, low-saturation-ish; fall back to all
        lm = luma(rows)
        m = lm > np.percentile(lm, 40)
        sel = rows[m] if m.sum() > 50 else rows.reshape(-1, 3)
        stops.append(r3(np.median(sel, axis=0)))
    return {
        "top_band_linear_mean": r3(band.reshape(-1, 3).mean(axis=0)),
        "gradient_zenith_to_horizon_linear": stops,
        "_band": "top %.0f%% of frame; gradient over top 35%% in 5 stops"
                 % (top_frac * 100),
    }


# ----------------------------------------------------------- skyline ------

def sky_mask(srgb):
    """Sky = pixels reachable from the top edge through SMOOTH colour
    change. A gradient sky (indigo zenith to peach horizon) is smooth
    column by column; a mountain edge is not. Flood-fills downward and
    sideways with a per-step colour tolerance, so a cloud (soft edge)
    stays sky and a ridge (hard edge) stops the fill."""
    h, w = srgb.shape[:2]
    # work at reduced width for speed, then upsample the row result
    step = max(1, w // 480)
    im = srgb[:, ::step]
    hh, ww = im.shape[:2]
    tol = 0.022  # per-pixel colour step that still counts as the same sky
    dy = np.sqrt(((im[1:] - im[:-1]) ** 2).sum(-1))
    dx = np.sqrt(((im[:, 1:] - im[:, :-1]) ** 2).sum(-1))
    mask = np.zeros((hh, ww), dtype=bool)
    mask[0] = True
    # iterative relaxation: down passes with sideways spread
    for _ in range(4):
        for r in range(1, hh):
            grow = mask[r - 1] & (dy[r - 1] < tol)
            row = mask[r] | grow
            # sideways spread within the row through smooth pixels
            for _k in range(3):
                left = np.zeros_like(row); left[1:] = row[:-1] & (dx[r] < tol)
                right = np.zeros_like(row); right[:-1] = row[1:] & (dx[r] < tol)
                row = row | left | right
            mask[r] = row
    return mask, step


def measure_skyline(srgb, lin):
    h, w = srgb.shape[:2]
    mask, step = sky_mask(srgb)
    hh, ww = mask.shape
    rows = np.full(ww, hh - 1, dtype=np.int64)
    for x in range(ww):
        col = mask[:, x]
        # last sky row before the fill stops (first non-sky after a sky run)
        nz = np.nonzero(~col)[0]
        rows[x] = nz[0] if nz.size else hh - 1
    # a column blocked early by a cloud interior: if the fill resumes
    # below, take the LAST transition instead
    for x in range(ww):
        col = mask[:, x]
        sky_rows = np.nonzero(col)[0]
        if sky_rows.size:
            rows[x] = min(hh - 1, sky_rows.max() + 1)
    k = max(3, (ww // 100) | 1)
    pad = np.pad(rows, k // 2, mode="edge")
    sm = np.array([np.median(pad[i:i + k]) for i in range(ww)])
    frac = sm / (hh - 1)
    idx = np.linspace(0, ww - 1, 64).astype(int)
    return {
        "columns": 64,
        "row_frac": r3(frac[idx]),
        "highest_point_frac": round(float(frac.min()), 4),
        "highest_point_x_frac": round(float(np.argmin(frac) / (ww - 1)), 4),
        "mean_frac": round(float(frac.mean()), 4),
        "sky_fraction_of_frame": round(float(mask.mean()), 4),
        "_note": "row_frac 0 = top of frame, 1 = bottom; sky above, land "
                 "below. Compare against the render's skyline with the "
                 "same function for a per-column height error.",
    }


# ------------------------------------------------------------ water -------

def measure_water(srgb, lin, skyline_frac):
    """A still lake is a MIRROR: the band below the far shore is the band
    above it, flipped. For each candidate shoreline row t, correlate the
    luma of rows t-k..t (flipped) against rows t..t+k per column block;
    the best t with correlation > 0.45 is the water's horizon. The
    water's bottom edge is where the mirror correlation dies (the near
    shore), its sides where it dies horizontally."""
    h, w = lin.shape[:2]
    lm = luma(lin)
    # downsample for speed
    sy = max(1, h // 256); sx = max(1, w // 256)
    L = lm[::sy, ::sx]
    hh, ww = L.shape
    kmax = int(hh * 0.28)
    best = (0.0, None)
    for t in range(int(hh * 0.35), int(hh * 0.85)):
        k = min(kmax, t, hh - 1 - t)
        if k < 8:
            continue
        above = L[t - k:t][::-1]        # flipped
        below = L[t + 1:t + 1 + k]
        a = above - above.mean(); b = below - below.mean()
        den = np.sqrt((a * a).sum() * (b * b).sum())
        c = float((a * b).sum() / den) if den > 0 else 0.0
        if c > best[0]:
            best = (c, t)
    if best[1] is None or best[0] < 0.45:
        return None
    t = best[1]
    k = min(kmax, t, hh - 1 - t)
    above = L[t - k:t][::-1]; below = L[t + 1:t + 1 + k]
    # per-column-block correlation to find horizontal extent
    blocks = 16
    xs = np.linspace(0, ww, blocks + 1).astype(int)
    colc = []
    for i in range(blocks):
        a = above[:, xs[i]:xs[i + 1]]; b = below[:, xs[i]:xs[i + 1]]
        a = a - a.mean(); b = b - b.mean()
        den = np.sqrt((a * a).sum() * (b * b).sum())
        colc.append(float((a * b).sum() / den) if den > 0 else 0.0)
    good = [i for i, c in enumerate(colc) if c > 0.3]
    if not good:
        return None
    left, right = xs[min(good)], xs[max(good) + 1]
    # vertical extent: row-wise correlation down from t until it dies
    bottom = t + 1
    for r in range(t + 1, min(hh - 1, t + 1 + k)):
        a = L[2 * t - r, left:right]; b = L[r, left:right]
        a = a - a.mean(); b = b - b.mean()
        den = np.sqrt((a * a).sum() * (b * b).sum())
        c = float((a * b).sum() / den) if den > 0 else 0.0
        if c > 0.2:
            bottom = r
    band = lin[t * sy:bottom * sy, left * sx:right * sx].reshape(-1, 3)
    lmb = luma(band)
    dark = band[lmb <= np.median(lmb)]
    col = np.median(dark, axis=0)
    return {
        "present": True,
        "mirror_correlation": round(best[0], 3),
        "top_row_frac": round(t / (hh - 1), 4),
        "bottom_row_frac": round(bottom / (hh - 1), 4),
        "left_frac": round(left / ww, 4),
        "right_frac": round(right / ww, 4),
        "color_linear": r3(col),
        "color_srgb": r3(linear_to_srgb(col)),
        "_note": "top_row_frac is the far shore in image space: the water "
                 "level's horizon. mirror_correlation 1 = perfect mirror; "
                 "a rippled lake still correlates but lower.",
    }


# ---------------------------------------------------------- palette -------

def measure_palette(srgb, lin, skyline_frac, water):
    """Ground albedo candidates. Rows below the skyline, excluding the
    water band, split into near (bottom 30%), mid (30..60%) and far
    (60..100%) of the land region, each split lit/shadow at median luma.
    Medians, not means: a few sunlit pixels must not drag a shadow band.
    Reported in LINEAR, the space make_landscape_material consumes."""
    h, w = lin.shape[:2]
    sky_row = np.interp(np.arange(w), np.linspace(0, w - 1, 64),
                        np.array(skyline_frac) * (h - 1))
    land = np.zeros((h, w), dtype=bool)
    for x in range(w):
        land[int(sky_row[x]) + 2:, x] = True
    if water:
        r0 = int(water["top_row_frac"] * (h - 1))
        r1 = int(water["bottom_row_frac"] * (h - 1))
        x0 = int(water["left_frac"] * (w - 1))
        x1 = int(water["right_frac"] * (w - 1))
        land[r0:r1, x0:x1] = False
    rows = np.nonzero(land.any(axis=1))[0]
    top, bot = rows.min(), rows.max()
    span = max(1, bot - top)
    bands = {"far": (0.0, 0.4), "mid": (0.4, 0.7), "near": (0.7, 1.0)}
    out = {}
    lm = luma(lin)
    sat = saturation(lin)
    for name, (a, b) in bands.items():
        ra, rb = int(top + a * span), int(top + b * span)
        m = land[ra:rb]
        px = lin[ra:rb][m]
        if px.shape[0] < 100:
            continue
        l = lm[ra:rb][m]
        med = np.median(l)
        lit, shd = px[l >= med], px[l < med]
        out[name] = {
            "median_linear": r3(np.median(px, axis=0)),
            "lit_linear": r3(np.median(lit, axis=0)),
            "shadow_linear": r3(np.median(shd, axis=0)),
            "saturation": round(float(np.median(sat[ra:rb][m])), 3),
            "luma_p10_p50_p90": r3(np.percentile(l, [10, 50, 90])),
            "_rows": [round(ra / (h - 1), 3), round(rb / (h - 1), 3)],
        }
    return out


# ------------------------------------------------------------- haze -------

def measure_haze(lin, skyline_frac, palette):
    """Near->far min-luma rise (analyse_concept's instrument) plus the
    image row where local contrast collapses: the top of the dense fog
    layer in image space, to be mapped to a world height by the camera."""
    h = lin.shape[0]
    lm = luma(lin)
    p = palette
    rise = None
    if "near" in p and "far" in p:
        rise = round(p["far"]["luma_p10_p50_p90"][0]
                     - p["near"]["luma_p10_p50_p90"][0], 4)
    # row-wise local contrast (std of luma in 5-row bands) from bottom up
    contr = np.array([lm[max(0, r - 2):r + 3].std() for r in range(h)])
    # normalise by bottom third, find the first row (from the bottom)
    # where contrast is under 35% of the near-field level — that is haze
    base = np.median(contr[int(h * 0.66):])
    fog_row = None
    for r in range(int(h * 0.66), int(h * 0.15), -1):
        if contr[r] < 0.35 * base:
            fog_row = r
            break
    return {
        "minluma_rise_near_to_far": rise,
        "contrast_collapse_row_frac": (round(fog_row / (h - 1), 4)
                                       if fog_row is not None else None),
        "near_contrast": round(float(base), 4),
        "_note": "contrast_collapse_row_frac is where haze eats detail; "
                 "with the camera pitch/fov it maps to fog.height_datum_m",
    }


# ------------------------------------------------------------ grade -------

def measure_grade(lin):
    lm = luma(lin)
    sat = saturation(lin)
    p20, p80 = np.percentile(lm, [20, 80])
    shadows = lin[lm <= p20]
    highs = lin[lm >= p80]
    def tint(px):
        c = np.median(px, axis=0)
        y = max(float(luma(c[None, :])[0]), 1e-6)
        return r3(c / y)
    return {
        "mean_luma_linear": round(float(lm.mean()), 4),
        "std_luma_linear": round(float(lm.std()), 4),
        "median_saturation": round(float(np.median(sat)), 3),
        "shadow_tint_ratio": tint(shadows),
        "highlight_tint_ratio": tint(highs),
        "_note": "tint ratios are RGB / luma of the band median: >1 in a "
                 "channel means that channel is pushed. Map to PPV "
                 "ColorGradingShadows / Highlights gain.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    srgb, lin = load(a.image)
    sky = measure_sky(lin)
    skyline = measure_skyline(srgb, lin)
    water = measure_water(srgb, lin, skyline["row_frac"])
    palette = measure_palette(srgb, lin, skyline["row_frac"], water)
    haze = measure_haze(lin, skyline["row_frac"], palette)
    grade = measure_grade(lin)
    rep = {"_instrument": "measure_concept_look v0 — statistics of the "
                          "pixels; mapping to recipe fields is AUTHORED "
                          "elsewhere",
           "image": a.image, "size_px": [srgb.shape[1], srgb.shape[0]],
           "sky": sky, "skyline": skyline,
           "water": water or {"present": False},
           "palette": palette, "haze": haze, "grade": grade}
    js = json.dumps(rep, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(js)
    print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
