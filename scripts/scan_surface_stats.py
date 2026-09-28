"""scan_surface_stats.py — what a ground scan IS, measured from its maps.

    python scripts/scan_surface_stats.py --only Rock016_4K-PNG [--out J]

THREE QUESTIONS THE INTAKE PROBE DOES NOT ANSWER. `scan_intake_probe`
reads headers and decides the height gate; this opens the pixels.

1. IS IT A TILING SURFACE, OR A CUTOUT?
   A ground layer must cover the texel it is asked to cover. A scan that
   ships an **Opacity** map may be a decal -- needles scattered on
   transparency, meant to overlay another surface, not to BE one. The
   discriminator is the opaque fraction: a tiling surface is ~1.0
   because its opacity map (if any) is a formality; a decal is well
   below it and the gap is the point.

   MEASURED 2026-09-12: `PineNeedles001` ships Opacity and NO ambient
   occlusion, which is the packaging signature of an overlay. The
   measurement decides it, not the file list.

2. WHERE DOES ITS ALBEDO SIT?
   Reported in LINEAR, sRGB-decoded, because every band this project
   quotes is linear. Reporting a display-referred mean against a linear
   band is the unit error that reads as a material fault.

3. WHICH NORMAL CONVENTION IS IT?
   A wrong convention inverts lighting across the entire surface, and
   both files ship in every ambientCG pack, so the choice is real. For a
   heightfield the normal is proportional to (-dH/dx, -dH/dy, 1).

   ⛔ THE SIGN, DERIVED -- AND IT IS THE OPPOSITE OF WHAT THE
   asset-intake SKILL SAID UNTIL 2026-09-12. Rows increase DOWNWARD.
   OpenGL's +Y runs UP the image, so dH/dy_GL = -dH/drow and
   N_y ∝ -dH/dy_GL = +dH/drow:

       GL  ->  corr(G, dH/drow) POSITIVE
       DX  ->  corr(G, dH/drow) NEGATIVE

   The skill asserted the reverse, and its own red-channel prediction
   proves it wrong from the inside: the SAME minus sign that makes red
   correlate negatively with the column gradient makes DX's green
   correlate negatively with the row gradient. One expression cannot
   carry the minus for X and drop it for Y. The concrete case agrees --
   on the upslope of a hill (dH/drow > 0) the surface faces UP the
   image, which is +Y in a y-up frame, so GL's green goes ABOVE mid.

   Measured consequence of the old sign: all four packs on disk
   (PineNeedles001, Rock016, Ground037 and the already-bound Rock051)
   were reported as disagreeing with their filenames. Four independent
   packs are not all mislabelled; the instrument was.

   THE RED CHANNEL IS THE CONTROL. It must correlate NEGATIVELY with the
   column gradient whatever the convention is. If the control comes out
   positive the measurement is not trustworthy and the verdict is
   withheld -- symmetric magnitude, opposite sign, method self-checked.
   Without it a sign error in the gradient would flip the verdict and
   look exactly like the wrong convention.

   `--selftest` builds a heightfield whose normals are constructed
   ANALYTICALLY under each convention and asserts the measurement
   recovers the right label, plus the control's sign, plus a refusal on
   a degenerate flat field. Run it before trusting a verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# a centre crop at NATIVE resolution -- gradients must not be resampled
CROP = 1024
# whole-image stats may be strided; albedo has no scale-sensitive term
STRIDE = 4
OPAQUE_AT = 0.98


def _load(path):
    """float array in [0,1], whatever the bit depth."""
    im = Image.open(path)
    a = np.asarray(im)
    if a.dtype == np.uint8:
        return a.astype(np.float32) / 255.0
    if a.dtype == np.uint16:
        return a.astype(np.float32) / 65535.0
    return a.astype(np.float32)


def _centre_crop(a, n=CROP):
    h, w = a.shape[:2]
    if h <= n or w <= n:
        return a
    r0, c0 = (h - n) // 2, (w - n) // 2
    return a[r0:r0 + n, c0:c0 + n]


def srgb_to_linear(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ⛔ NOT .png ONLY. This accepted PNG alone until 2026-09-12, so a pack
# whose colour map was a JPEG reported "no colour map found" -- a file
# that was present, readable, and sitting right there. A finder that
# silently skips a whole container reports ABSENCE for something it
# merely declined to look at, which is the same class as the cvar getter
# that could not tell "zero" from "absent". PIL reads all of these.
READABLE = (".png", ".jpg", ".jpeg", ".tif", ".tiff")


def find_map(folder, *hints):
    for f in sorted(os.listdir(folder)):
        low = f.lower()
        if not low.endswith(READABLE):
            continue
        if any(h in low for h in hints):
            return os.path.join(folder, f)
    return None


def _corr(a, b):
    a = a.ravel().astype(np.float64)
    b = b.ravel().astype(np.float64)
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum()))
    if d == 0.0:
        return None
    return float((a * b).sum() / d)


def opacity_stats(folder):
    p = find_map(folder, "_opacity", "_alpha")
    if not p:
        return {"has_opacity_map": False,
                "verdict": "no opacity map -- fully covering by construction"}
    a = _load(p)
    if a.ndim == 3:
        a = a[..., 0]
    a = a[::STRIDE, ::STRIDE]
    frac = float((a >= OPAQUE_AT).mean())
    return {"has_opacity_map": True,
            "file": os.path.basename(p),
            "mean": round(float(a.mean()), 4),
            "opaque_fraction": round(frac, 4),
            "opaque_threshold": OPAQUE_AT,
            "verdict": ("COVERING -- opacity is a formality"
                        if frac >= 0.98 else
                        "CUTOUT/DECAL -- %.1f%% of texels are transparent"
                        % (100.0 * (1.0 - frac)))}


def albedo_stats(folder):
    p = find_map(folder, "_color", "_albedo", "_basecolor")
    if not p:
        return {"error": "no colour map found"}
    a = _load(p)[::STRIDE, ::STRIDE]
    if a.ndim == 3:
        a = a[..., :3]
    else:
        a = np.dstack([a, a, a])
    lin = srgb_to_linear(a)
    luma = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    return {"file": os.path.basename(p),
            "space": "LINEAR (sRGB-decoded)",
            "luma_mean": round(float(luma.mean()), 5),
            "luma_p05": round(float(np.percentile(luma, 5)), 5),
            "luma_p50": round(float(np.percentile(luma, 50)), 5),
            "luma_p95": round(float(np.percentile(luma, 95)), 5),
            "rgb_mean_linear": [round(float(lin[..., i].mean()), 5)
                                for i in range(3)]}


def gradients(h):
    """Row and column gradients, interior only so operands align."""
    return ((h[2:, 1:-1] - h[:-2, 1:-1]) * 0.5,
            (h[1:-1, 2:] - h[1:-1, :-2]) * 0.5)


def convention_of(h, n, claimed):
    """Which convention an RGB normal map `n` is in, given heightfield `h`.

    GL -> corr(green, dH/drow) POSITIVE; DX -> NEGATIVE. Derived in the
    module docstring; `--selftest` pins it to analytic normals.
    """
    dh_drow, dh_dcol = gradients(h)
    g = n[1:-1, 1:-1, 1] * 2.0 - 1.0      # green, signed
    r = n[1:-1, 1:-1, 0] * 2.0 - 1.0      # red, the CONTROL
    cg = _corr(g, dh_drow)
    cr = _corr(r, dh_dcol)
    out = {"corr_green_vs_dH_drow": round(cg, 4) if cg is not None else None,
           "corr_red_vs_dH_dcol_CONTROL":
               round(cr, 4) if cr is not None else None}
    if cr is None or cr >= 0:
        out["measured"] = None
        out["verdict"] = ("NO VERDICT -- red control is %s, not negative; "
                          "gradient sign unproven"
                          % ("None" if cr is None else "%.4f" % cr))
    elif cg is None:
        out["measured"] = None
        out["verdict"] = "NO VERDICT -- green correlation undefined"
    else:
        looks = "GL" if cg > 0 else "DX"
        out["measured"] = looks
        out["verdict"] = (
            "consistent with %s (green vs dH/drow %+.4f)" % (looks, cg)
            + ("" if looks == claimed else
               "  ** DISAGREES with its filename **"))
    return out


def normal_convention(folder):
    hp = find_map(folder, "_displacement", "_height")
    out = {}
    if not hp:
        return {"error": "no height map -- convention not measurable"}
    h = _centre_crop(_load(hp))
    if h.ndim == 3:
        h = h[..., 0]
    for tag, hints in (("DX", ("_normaldx",)), ("GL", ("_normalgl",))):
        p = find_map(folder, *hints)
        if not p:
            out[tag] = {"error": "absent"}
            continue
        n = _centre_crop(_load(p))
        if n.ndim != 3:
            out[tag] = {"error": "not an RGB normal map"}
            continue
        row = convention_of(h, n, tag)
        row["file"] = os.path.basename(p)
        out[tag] = row
    return out


def _synth(n=192, encode=None):
    """A smooth bumpy heightfield and its ANALYTIC normal map.

    `encode` is 'DX' or 'GL'. The normal of a heightfield is
    (-dH/dx, -dH/dy, 1) normalised; GL's +Y runs UP the image so its
    green is +dH/drow, DX's runs DOWN so its green is -dH/drow.
    """
    r = np.arange(n)[:, None].astype(np.float64)
    c = np.arange(n)[None, :].astype(np.float64)
    h = (0.30 * np.sin(2 * np.pi * c / 57.0)
         + 0.22 * np.cos(2 * np.pi * r / 41.0)
         + 0.15 * np.sin(2 * np.pi * (r + c) / 83.0))
    h = (h - h.min()) / (h.max() - h.min())
    dh_dr, dh_dc = np.gradient(h)
    nx = -dh_dc
    ny = dh_dr if encode == "GL" else -dh_dr
    nz = np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    return h, np.dstack([(nx / ln + 1) / 2, (ny / ln + 1) / 2,
                         (nz / ln + 1) / 2])


def selftest():
    """THREE DIRECTIONS: label the truth, label its inverse, refuse junk."""
    fails = []

    for want in ("DX", "GL"):
        h, n = _synth(encode=want)
        got = convention_of(h, n, want)
        if got["measured"] != want:
            fails.append("analytic %s read as %s (green %+.4f)"
                         % (want, got["measured"], got["corr_green_vs_dH_drow"]))
        if got["corr_red_vs_dH_dcol_CONTROL"] is None or \
                got["corr_red_vs_dH_dcol_CONTROL"] >= 0:
            fails.append("analytic %s: red control not negative (%s)"
                         % (want, got["corr_red_vs_dH_dcol_CONTROL"]))
        print("  analytic %s -> %s" % (want, got["verdict"]))

    # direction 2: swapping the labels must be CAUGHT, not tolerated
    h, n = _synth(encode="GL")
    mis = convention_of(h, n, "DX")
    if "DISAGREES" not in mis["verdict"]:
        fails.append("a GL map claiming to be DX was not flagged")
    print("  GL map labelled DX -> %s" % mis["verdict"])

    # direction 3: a flat field has no gradient -- refuse, do not guess
    flat = np.full((64, 64), 0.5)
    n_flat = np.full((64, 64, 3), 0.5)
    deg = convention_of(flat, n_flat, "DX")
    if deg["measured"] is not None:
        fails.append("flat field produced a verdict: %s" % deg["verdict"])
    print("  flat field -> %s" % deg["verdict"])

    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(REPO, "Free"))
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.only:
        ap.error("--only is required unless --selftest")

    rows = []
    for name in a.only:
        folder = os.path.join(a.root, name)
        if not os.path.isdir(folder):
            print("MISSING %s" % name)
            continue
        print("=== %s ===" % name)
        row = {"scan": name,
               "opacity": opacity_stats(folder),
               "albedo": albedo_stats(folder),
               "normals": normal_convention(folder)}
        print("  opacity : %s" % row["opacity"].get("verdict"))
        al = row["albedo"]
        if "error" in al:
            print("  albedo  : %s" % al["error"])
        else:
            print("  albedo  : linear luma mean %.5f  p05 %.5f  p95 %.5f"
                  % (al["luma_mean"], al["luma_p05"], al["luma_p95"]))
        for tag in ("DX", "GL"):
            nv = row["normals"].get(tag, {})
            print("  normal %s: %s" % (tag, nv.get("verdict", nv.get("error"))))
        rows.append(row)
        print()

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "ground-scan surface stats",
                       "_crop_px": CROP, "_stride": STRIDE,
                       "scans": rows}, fh, indent=1)
        print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
