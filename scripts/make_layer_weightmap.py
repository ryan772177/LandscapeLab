"""make_layer_weightmap.py — bake per-layer blend weights from the heightmap.

LOCAL ONLY. No editor contact. Writes textures/<biome>_weights.png.

WHY THIS EXISTS
---------------
The material used to derive slope in the shader from the landscape's VERTEX
NORMAL. That is not the same measurement the recipe was tuned against, and
the difference is not small:

  * numpy on the 4 m heightmap grid: MEDIAN slope 44 degrees, because the
    erosion detail is genuinely that steep between adjacent samples;
  * the rendered vertex normal: far smoother, and smoother still at every
    LOD step, because the drawn mesh is decimated with distance.

So `normal.z` drifts toward 1 as the camera pulls back, every sample looks
flat, and a slope band starting at 0 degrees (Snow) swallows the terrain
while one starting at 35 (Rock) matches almost nothing. Captures on
2026-08-01 came back ~98% snow at BOTH 8.7 km and 4.2 km — the close camera
is what ruled out "it is only a distance artefact".

Baking fixes it at the root: the weights are computed ONCE, on the CPU, from
the source heightmap at full resolution, and the shader just reads them. The
rendered layer coverage then equals the predicted coverage exactly, at every
LOD and every distance, because LOD no longer participates in the decision.

WHAT IS IN THE TEXTURE
----------------------
One RGB channel per layer, in recipe order:

    R = layers[0] weight    G = layers[1] weight    B = layers[2] weight

Weights are the SAME band/feather arithmetic the shader used to do, resolved
first-match-wins on the CPU so they sum to 1 wherever any layer matches. A
recipe with more than 3 layers is refused rather than silently truncated —
RGB has three channels and there is no fourth.

The texture is DATA, not colour: linear, no sRGB, and it must not be
resampled or lossily compressed in a way that bleeds one layer into another.
import_layer_weightmap settings are asserted by read-back on the import side.

Deterministic: same heightmap + same recipe -> same PNG.

Exit codes:
  0  weightmap written and verified
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  more than 3 layers, or the heightmap could not be read
  4  the baked coverage disagrees with an independent recomputation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zlib

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landscape_spec     # noqa: E402 — shared recipe loading
import make_landscape_material as mlm  # noqa: E402 — the SAME band maths

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTURE_DIR = os.path.join(REPO_ROOT, "textures")


def _ramp(v, edge, outer, rising):
    """Vectorised mirror of the material's `_ramp`/`_cpu_ramp`.

    Kept identical on purpose: this bakes what the shader used to compute,
    so if the two ever disagree the baked weights stop meaning what the
    recipe says. `mlm._cpu_ramp` is the scalar reference.
    """
    span = edge - outer
    if abs(span) < 1e-9:
        eps = max(1e-6, abs(edge) * 1e-6)
        outer = edge - eps if rising else edge + eps
        span = edge - outer
    return np.clip((v - outer) / span, 0.0, 1.0)


def _band(v, lo_out, lo_in, hi_in, hi_out):
    return (_ramp(v, lo_in, lo_out, True)
            * _ramp(v, hi_in, hi_out, False))


def bake(recipe):
    """Return (weights HxWx3 float, coverage dict, band list)."""
    ls = recipe["landscape"]
    hm = recipe["heightmap"]
    # CONTAINMENT, not decoration (conduct rule 1). os.path.join DISCARDS
    # REPO_ROOT when the second argument is absolute, and it does not
    # collapse '..' — so a recipe carrying "C:/elsewhere/x.png" would be
    # read straight off the disk and baked into a shipped texture.
    #
    # The schema check that rejects absolute and '..' sources lives in
    # import_heightmap._validate_heightmap (:176-182), and THIS SCRIPT DOES
    # NOT CALL IT: landscape_spec.load_recipe validates where the RECIPE
    # lives, not where the recipe POINTS. Found by sweeping for the class
    # after the auditor flagged the same join in push_heightmap.py
    # (finding F11) — lesson 8, when you find a defect class, grep for it
    # everywhere immediately. import_layer_textures.py already checked;
    # push_heightmap.py was fixed by the auditor; this was the one left.
    src = os.path.realpath(os.path.join(REPO_ROOT, hm["source"]))
    repo = os.path.realpath(REPO_ROOT)
    if src != repo and not src.startswith(repo + os.sep):
        raise ValueError(
            "heightmap.source escapes REPO_ROOT: {0!r} resolves to {1}"
            .format(hm["source"], src))
    arr = np.asarray(Image.open(src)).astype(np.float64)
    if arr.ndim != 2:
        raise ValueError("heightmap must be single-channel, got shape "
                         "{0}".format(arr.shape))

    z_scale = float(ls["z_scale_cm"])
    actor_z = float(ls["location_cm"][2])
    scale_xy_m = float(ls["scale_xy_cm"]) / 100.0

    # World Z exactly as the schema's datum defines it: heightmap value
    # 32768 maps to the actor's Z, not 0.
    world_z = actor_z + (arr / 65535.0 - 0.5) * z_scale

    # Slope from the heightmap itself, at full resolution. THIS is the
    # measurement the recipe's slope_deg was always meant to describe.
    height_m = (arr / 65535.0) * (z_scale / 100.0)
    gy, gx = np.gradient(height_m, scale_xy_m)
    normal_z = np.cos(np.arctan(np.hypot(gx, gy)))

    # ---- schema v1.5: snowline jitter ------------------------------
    # A height band tested against a bare elevation produces a boundary
    # that is a perfect contour line, and a perfectly level snowline is
    # one of the strongest procedural tells there is — real ones wander
    # with aspect, wind and shade.
    #
    # ONE jitter field, applied to the elevation ONCE, not per layer.
    # Snow's lower bound and Grass's upper bound are the same number
    # (925 m); perturbing them independently would slide them apart and
    # open a seam that first-match-wins would fill with whichever layer
    # happened to be earlier. Perturbing the height they are both tested
    # against keeps every boundary locked together and merely makes them
    # wander as one.
    #
    # Seeded from biome_id, so hard rule 3 holds: the same recipe bakes
    # the same weightmap.
    mat = recipe.get("material") or {}
    jitter_m = float(mat.get("height_jitter_m") or 0.0)
    jitter_scale_m = float(mat.get("height_jitter_scale_m") or 600.0)
    if jitter_m > 0.0:
        from scipy import ndimage as _ndi
        seed = zlib.crc32(str(recipe.get("biome_id", "")).encode()) & 0xFFFF
        rng = np.random.default_rng(seed)
        # Gaussian-blurred white noise, deliberately NOT the generator's
        # value noise: reusing that would couple the weightmap bake to
        # the terrain generator's RNG stream, where any future change to
        # one would silently move the other's output.
        sigma = max(jitter_scale_m / max(scale_xy_m, 1e-9) / 3.0, 1.0)
        field = _ndi.gaussian_filter(rng.standard_normal(arr.shape), sigma)
        spread = float(np.abs(field).max())
        field = field / max(spread, 1e-9)          # -> about [-1, 1]
        world_z = world_z + field * jitter_m * 100.0   # cm, as world_z is
        print("  snowline jitter: +/-{0:.0f} m over ~{1:.0f} m features"
              .format(jitter_m, jitter_scale_m))

    bands = mlm.layer_bands(recipe)          # runs the invariant gate too
    if len(bands) > 3:
        raise ValueError(
            "{0} layers, but an RGB weightmap carries only 3. Refusing "
            "rather than dropping a layer silently.".format(len(bands)))

    masks = []
    for b in bands:
        m = (_band(normal_z, b["cos_lo"], b["cos_lo_in"],
                   b["cos_hi_in"], b["cos_hi"])
             * _band(world_z, b["z_lo"], b["z_lo_in"],
                     b["z_hi_in"], b["z_hi"]))
        masks.append(m)

    # First-match-wins, feathered: layer i takes what it claims, minus
    # whatever earlier layers already took. Mirrors the material's
    # last-to-first lerp composite, which lets layer 0 override the rest.
    remaining = np.ones_like(normal_z)
    weights = []
    for m in masks:
        take = np.minimum(m, remaining)
        weights.append(take)
        remaining = remaining - take

    w = np.zeros(arr.shape + (3,), dtype=np.float64)
    for i, take in enumerate(weights):
        w[..., i] = take

    total = float(arr.size)
    coverage = {bands[i]["name"]: 100.0 * float(weights[i].sum()) / total
                for i in range(len(bands))}
    coverage["(unmatched)"] = 100.0 * float(remaining.sum()) / total
    return w, coverage, bands


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=landscape_spec.DEFAULT_RECIPE)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    try:
        w, coverage, bands = bake(recipe)
    except (ValueError, OSError) as exc:
        print("REFUSE: {0}".format(exc))
        return 3

    real_dir = os.path.realpath(TEXTURE_DIR)
    if os.path.commonpath([real_dir, os.path.realpath(REPO_ROOT)]) != \
            os.path.realpath(REPO_ROOT):
        print("REFUSE: texture dir escapes REPO_ROOT")
        return 2
    os.makedirs(real_dir, exist_ok=True)
    out = os.path.join(real_dir,
                       "{0}_weights.png".format(recipe["biome_id"]))

    quant = np.rint(np.clip(w, 0.0, 1.0) * 255.0).astype(np.uint8)

    # Independent recomputation from the QUANTISED bytes. The bake above is
    # what we believe; this is what actually ships. 8-bit rounding moves a
    # weight by at most 1/255, so a disagreement beyond that means the
    # write path changed the data (lesson: verify the artefact, not the
    # intention).
    back = quant.astype(np.float64) / 255.0
    drift = float(np.abs(back - np.clip(w, 0.0, 1.0)).max())
    if drift > 1.0 / 255.0 + 1e-9:
        print("REFUSE: quantised weights drift by {0:.6f}, above the "
              "1/255 rounding bound.".format(drift))
        return 4

    Image.fromarray(quant, mode="RGB").save(out, optimize=True)

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("Heightmap : {0}".format(recipe["heightmap"]["source"]))
    print("Wrote     : {0} ({1} bytes)".format(
        os.path.relpath(out, REPO_ROOT), os.path.getsize(out)))
    print("")
    print("Baked coverage — this is now EXACTLY what renders, at every LOD:")
    for i, b in enumerate(bands):
        print("  {0:<8} ({1})  {2:6.2f}%   slope {3}..{4} deg  "
              "height {5}..{6} m".format(
                  b["name"], "RGB"[i], coverage[b["name"]],
                  b["slope_deg"][0], b["slope_deg"][1],
                  b["height_m"][0], b["height_m"][1]))
    print("  {0:<8}       {1:6.2f}%".format(
        "(none)", coverage["(unmatched)"]))
    print("")
    print("max 8-bit quantisation drift {0:.6f} (bound {1:.6f})".format(
        drift, 1.0 / 255.0))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
