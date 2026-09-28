"""angular_budget.py — derive cull and LOD distances from what the EYE and
the DISPLAY can resolve, instead of picking metres by hand.

The recipe today says `cull_distance_m: 730` for a 14.7 m spruce. This
tool answers the question that number should have come from: at this
camera (FOV, resolution) and this display (pixel pitch, viewing
distance), how many pixels tall is a 14.7 m tree at 730 m, and is that
above, at, or below the thresholds where a human stops seeing it as an
object, as a silhouette, or at all? It then inverts the question: what
distance puts the tree at each threshold, and what UE LOD `ScreenSize`
value corresponds to it.

WHY ANGLE, NOT METRES. Visual acuity is angular: ~1 arcminute for the
finest resolvable detail at high contrast (Snellen 20/20), and the
contrast sensitivity function (CSF) peaks around 3-5 cycles per degree
and falls to nothing near 50-60 cpd. A cull expressed in metres is
correct for exactly one FOV and one resolution; expressed in pixels or
arcminutes it survives a camera change, a resolution change and a
display change. The engine already thinks this way: LOD switching is
keyed on the projected bounding sphere (ScreenSize), not distance.

THE THRESHOLDS (defaults; override on the command line, and cite the
override in the recipe):

  vanish_px      1.5   below this an object contributes only as a
                       texture pixel; culling it changes nothing a
                       human can report (it is under the display's own
                       Nyquist limit, and under the eye's at any
                       realistic viewing distance)
  silhouette_px  6     the smallest height at which a tree still reads
                       as a tree-shaped thing rather than a dark speck;
                       from the CSF: ~4-6 cycles across the object at
                       the peak-sensitivity band. Above this an
                       imposter/HLOD proxy is indistinguishable from
                       the mesh; below it a colour blob suffices
  detail_px      40    above this the eye resolves internal structure
                       (branch layers, trunk) - the band where LOD0/1
                       and real shadows matter; from ~1 arcmin acuity
                       over a ~40-arcmin object at typical viewing
  jnd_contrast   0.02  Weber fraction; a luminance step under 2% over
                       a small region is at threshold. Used for the
                       pop budget: a LOD switch whose per-pixel change
                       exceeds this over more than a few px is visible

THE UE MAPPING. UE computes LOD ScreenSize from the bounding SPHERE:

    ScreenSize = R / (D * tan(vFOV / 2))     as a fraction of screen
                                             HEIGHT, and it is the
                                             sphere DIAMETER

VERIFIED against UE 5.8 engine source 2026-09-05 (Brief 1 Task 2); see
`ue_screen_size` below for the cited lines. **The formula this file
shipped with was 2x too large** -- it read `2 * R / (D * tan(vFOV/2))`
and attributed `ScreenMultiple = 0.5 * ProjMatrix[1][1]` to the engine.
The engine's multiple is a MAX over both projection diagonals
(SceneManagement.cpp:971); on a >=1 aspect that max is the [1][1] term,
so that half was harmlessly specific rather than wrong, but the factor
of 2 was a real error and every ScreenSize this tool printed before
2026-09-05 is double the engine's value. The PIXEL columns were never
affected -- they do not go through this function.

RECIPES R-ANGBUDGET REJECTED carries this; anything that consumed a
ScreenSize from this tool before 2026-09-05 must be re-derived.

Usage
  python angular_budget.py --fov-h 90 --res 2560 1440 \
      --object Conifer 14.7 --object Sapling 4.0 --object Boulder 2.5 \
      --cull Conifer 730 --cull Sapling 180 --cull Boulder 140 \
      [--display-ppd 45] [--out budget.json]

--display-ppd is the display's pixels per degree (27" 1440p at 60 cm is
~45 ppd; a 4K TV at 3 m is ~80 ppd). When given, the tool also reports
whether the RENDER pixel or the DISPLAY pixel is the limiting factor:
if render ppd < display ppd, the render is undersampled and thresholds
should be set in render pixels (the case for a 90 deg FOV at 2560 wide,
which is only 28 ppd).
"""
from __future__ import annotations

import argparse
import json
import math
import sys


def vfov_from_hfov(hfov_deg, width, height):
    return 2.0 * math.degrees(math.atan(math.tan(math.radians(hfov_deg) / 2.0)
                                         * height / width))


def pixels_tall(height_m, dist_m, vfov_deg, res_h):
    """Projected height in pixels of a vertical object of height_m at
    dist_m, for a camera looking roughly level (small-angle exact enough
    for this purpose)."""
    if dist_m <= 0:
        return float("inf")
    return height_m / (2.0 * dist_m * math.tan(math.radians(vfov_deg) / 2.0)) * res_h


def dist_for_pixels(height_m, px, vfov_deg, res_h):
    return height_m * res_h / (2.0 * px * math.tan(math.radians(vfov_deg) / 2.0))


def ue_screen_size(radius_m, dist_m, vfov_deg):
    """Projected bounding-sphere DIAMETER as a fraction of screen height:
    UE's LOD ScreenSize convention.

    VERIFIED against engine source 2026-09-05 (UE 5.8), Brief 1 Task 2.
    THIS FUNCTION WAS WRONG BY EXACTLY 2x AND HAS BEEN CORRECTED; the
    old form returned 2*R/(D*tan(vfov/2)).

    Engine/Source/Runtime/Engine/Private/SceneManagement.cpp:966
      ComputeBoundsScreenSize(BoundsOrigin, SphereRadius, ViewOrigin, ProjMatrix)
        :968   Dist           = FVector::Dist(BoundsOrigin, ViewOrigin)
        :971   ScreenMultiple = FMath::Max(0.5f * ProjMatrix.M[0][0],
                                           0.5f * ProjMatrix.M[1][1])
        :974   ScreenRadius   = ScreenMultiple * SphereRadius / Max(1.0f, Dist)
        :977   return           ScreenRadius * 2.0f

    Two things the docstring this replaced got wrong:

    1. ScreenMultiple is a MAX over BOTH projection diagonals, not
       `0.5 * ProjMatrix[1][1]`. For any viewport with aspect >= 1 the
       max IS the [1][1] term, so the two agree on our 16:9 judgement
       camera -- but they diverge on a portrait or square viewport, and
       the general statement is the Max.

    2. The factor of 2. Core/Public/Math/PerspectiveMatrix.h:102-105
       (TPerspectiveMatrix(HalfFOV, Width, Height, MinZ, MaxZ), where
       HalfFOV is HORIZONTAL) gives
           M[0][0] = 1 / tan(HalfFOV)
           M[1][1] = (Width / Height) / tan(HalfFOV)
       and since tan(vFOV/2) = tan(HalfFOV) / aspect,
           M[1][1] = 1 / tan(vFOV/2).
       So for aspect >= 1:
           ScreenMultiple = 0.5 / tan(vFOV/2)
           ScreenSize     = 2 * ScreenMultiple * R / D
                          =     R / (D * tan(vFOV/2))
       The previous form doubled this, i.e. it expressed the diameter as
       a fraction of screen HALF-height, which is not a quantity the
       engine has.

    That ScreenSize is a DIAMETER (the one thing the old docstring had
    right) is confirmed independently at the consuming end:
    SceneManagement.cpp:1042 selects a LOD with
        FMath::Square(MeshScreenSize * 0.5f) > ScreenRadiusSquared
    -- the authored per-LOD ScreenSize is HALVED before being compared
    against a screen RADIUS. Same at :1004 for the temporal path.

    Unit note: the engine works in centimetres and clamps with
    Max(1.0f, Dist), i.e. at Dist < 1 cm. R and D here are both metres,
    the ratio is unitless, and the clamp is unreachable at any distance
    this project measures.
    """
    if dist_m <= 0:
        return float("inf")
    return radius_m / (dist_m * math.tan(math.radians(vfov_deg) / 2.0))


def arcmin_per_px(hfov_deg, width):
    return hfov_deg * 60.0 / width


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fov-h", type=float, required=True, help="horizontal FOV deg (UE convention)")
    ap.add_argument("--res", type=int, nargs=2, required=True, metavar=("W", "H"))
    ap.add_argument("--object", nargs=2, action="append", metavar=("NAME", "HEIGHT_M"), required=True)
    ap.add_argument("--cull", nargs=2, action="append", metavar=("NAME", "DIST_M"), default=[])
    ap.add_argument("--vanish-px", type=float, default=1.5)
    ap.add_argument("--silhouette-px", type=float, default=6.0)
    ap.add_argument("--detail-px", type=float, default=40.0)
    ap.add_argument("--display-ppd", type=float, default=None)
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    W, H = a.res
    vfov = vfov_from_hfov(a.fov_h, W, H)
    render_ppd = W / a.fov_h
    rep = {
        "camera": {"fov_h_deg": a.fov_h, "fov_v_deg": round(vfov, 3), "res": [W, H],
                   "render_pixels_per_degree": round(render_ppd, 2),
                   "arcmin_per_render_pixel": round(arcmin_per_px(a.fov_h, W), 3)},
        "thresholds_px": {"vanish": a.vanish_px, "silhouette": a.silhouette_px, "detail": a.detail_px},
        "objects": {},
        "_ue_screen_size_note": "ScreenSize = R/(D*tan(vFOV/2)), the bounding-sphere "
                                "DIAMETER as a fraction of screen HEIGHT. VERIFIED against "
                                "UE 5.8 SceneManagement.cpp:966-977 (ComputeBoundsScreenSize; "
                                "ScreenMultiple = Max(0.5*M[0][0], 0.5*M[1][1]) at :971, "
                                "return ScreenRadius*2 at :977) and PerspectiveMatrix.h:102-105 "
                                "(M[1][1] = aspect/tan(HalfFOV_h) = 1/tan(vFOV/2)); diameter "
                                "convention confirmed at the consuming end, SceneManagement.cpp:1042. "
                                "Corrected 2026-09-05: this tool previously returned 2x this value.",
    }
    if a.display_ppd:
        rep["display"] = {"pixels_per_degree": a.display_ppd,
                          "limiting_factor": "render" if render_ppd < a.display_ppd else "display",
                          "_note": "when the render is the limit, thresholds are in RENDER pixels; "
                                   "the eye never sees finer than the render provides"}
    culls = {n: float(d) for n, d in a.cull}
    for name, h in a.object:
        h = float(h)
        R = h / 2.0  # bounding sphere radius for a roughly tall object ~ h/2 (conservative)
        o = {"height_m": h}
        for key, px in (("detail", a.detail_px), ("silhouette", a.silhouette_px), ("vanish", a.vanish_px)):
            d = dist_for_pixels(h, px, vfov, H)
            o["dist_m_at_%s" % key] = round(d, 1)
            o["ue_screen_size_at_%s" % key] = round(ue_screen_size(R, d, vfov), 5)
        if name in culls:
            cd = culls[name]
            px = pixels_tall(h, cd, vfov, H)
            o["recipe_cull_m"] = cd
            o["px_tall_at_recipe_cull"] = round(px, 2)
            o["ue_screen_size_at_recipe_cull"] = round(ue_screen_size(R, cd, vfov), 5)
            if px > a.silhouette_px:
                o["verdict"] = ("VISIBLE POP: at the recipe cull the object is %.1f px tall, "
                                "above the silhouette threshold (%.0f px); it disappears as a "
                                "shape, not as a speck. Either move the cull to >= %.0f m "
                                "(vanish) or hand off to a proxy (HLOD/imposter/canopy "
                                "material) at >= %.0f m instead of culling."
                                % (px, a.silhouette_px, o["dist_m_at_vanish"], o["dist_m_at_silhouette"]))
            elif px > a.vanish_px:
                o["verdict"] = ("MARGINAL: %.1f px at cull; a speck vanishing. Acceptable "
                                "with dithered fade over >= 0.3 s; better to fade to a "
                                "colour blob (HLOD) than to nothing." % px)
            else:
                o["verdict"] = "OK: below vanish threshold; cull is imperceptible."
        rep["objects"][name] = o
    js = json.dumps(rep, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
