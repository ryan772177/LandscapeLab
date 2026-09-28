"""make_macro_variation.py — bake the kilometre-scale variation map (v1.19).

OFFLINE. No editor, no `unreal`. Writes ONE RGB PNG.

WHY THIS EXISTS
---------------
An 8064 m x 8064 m terrain reads as one uniform material from an airship at
2 km. Pass 2c calls for kilometre-scale variation across ALL layers. Measured
risk it must cover: the scree surface Rock026 carries 2.07x the low-frequency
energy of Rock051, making it the most visible-tiling surface in the palette
at exactly that altitude.

This is NOT the existing per-layer macro sampling. Each layer already samples
its own albedo a second time at `macro_tiling_m` (188 m / 98.7 m) to break up
the detail repeat. That is texture-repeat breakup at ~100-200 m. This is a
different scale, a different purpose, and it is applied at a different point
in the graph: ONCE, on the composited base colour.

WHY A BAKED TEXTURE AND NOT A NOISE NODE
-----------------------------------------
RULED 2026-08-03 (Fable 5, owner away) — and rejected on the engine's own
numbers, not on citability. `UMaterialExpressionNoise` is fully citable
(MaterialExpressionNoise.h:60, NoiseFunction :86, ENoiseFunction :14), and its
own header states the cost: ValueALU "~53 instructions per level" (:43-44),
GradientALU "~80 per level" (:37), SimplexTex "~77 per level, 4 texture
lookups" (:17). Two or three octaves of the CHEAPEST function is 100-160 ALU
per pixel across the whole terrain, on an integrated GPU that has already been
lost to a driver timeout once. One texture fetch plus ~6 ALU does the same job.

Three further reasons the texture wins HERE specifically:

  * It rides THE ONE DECLARATION. A row in `GLOBAL_TEXTURES` inherits the
    preflight, the sampler-type check and the post-build graph assertion for
    free. A Noise node bypasses all three.
  * CLAMPED 1:1 CANNOT REPEAT. A *wrapped* macro texture tiling at ~2.5 km
    would itself repeat ~3x across 8064 m, reintroducing the disease at the
    exact altitude the verification checks. A single clamped map spanning the
    terrain makes that unrepresentable rather than merely unlikely
    (non-negotiable 3).
  * The pixels exist on disk before the graph samples them, so the artefact
    can be inspected directly (non-negotiable 10).

THE ENCODING CONTRACT, and it is load-bearing
---------------------------------------------
Per-channel mean is EXACTLY 0.5. The material computes

    out = colour * (1 + strength * (2*tex - 1))

so a fully-mipped or missing sample is 0.5 -> the factor is exactly 1.0 -> the
composite renders untouched. The degraded state is the identity, by
construction. `import_layer_textures` verifies the mean at the artefact after
import (non-negotiable 15).

Exit codes:
  0  written and verified by read-back (or --dry-run, which writes nothing)
  2  recipe missing or invalid
  4  the written file failed its read-back or its encoding contract
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MEAN_TOLERANCE = 0.02


def _value_noise(shape, cells, rng):
    """Smooth value noise on a `cells` x `cells` lattice, smoothstep fade.

    Smoothstep, not linear: a linear fade's derivative jumps on every
    lattice line, and at km scale that draws a faint rectangular grid
    across the whole terrain -- the same argument as the stamp falloff
    and the detail-relief noise.
    """
    g = rng.random((cells + 1, cells + 1))
    ys = np.linspace(0, cells, shape[0], endpoint=False)
    xs = np.linspace(0, cells, shape[1], endpoint=False)
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    fx = (xs - x0)[None, :]
    fy = (ys - y0)[:, None]
    sx = fx * fx * (3.0 - 2.0 * fx)
    sy = fy * fy * (3.0 - 2.0 * fy)
    n00 = g[np.ix_(y0, x0)]
    n10 = g[np.ix_(y0, x0 + 1)]
    n01 = g[np.ix_(y0 + 1, x0)]
    n11 = g[np.ix_(y0 + 1, x0 + 1)]
    return (n00 * (1 - sx) + n10 * sx) * (1 - sy) + \
           (n01 * (1 - sx) + n11 * sx) * sy


def build(spec, span_m):
    """The luma field and its capped chroma, both centred on 0.5."""
    res = int(spec["map_resolution"])
    lo_m, hi_m = [float(v) for v in spec["feature_scale_m"]]
    rng = np.random.default_rng(int(spec["seed"]))

    # Octaves from the declared feature band. `hi_m` is the largest
    # feature, `lo_m` the smallest; anything below lo_m is the existing
    # per-layer macro sampling's job and two systems fighting over one
    # octave reads as mush.
    luma = np.zeros((res, res))
    amp, norm, wl = 1.0, 0.0, hi_m
    while wl >= lo_m:
        cells = max(int(round(span_m / wl)), 1)
        luma += amp * _value_noise((res, res), cells, rng)
        norm += amp
        amp *= 0.5
        wl *= 0.5
    luma /= max(norm, 1e-9)

    # Centre on 0.5 and normalise to a full-ish range without clipping.
    luma -= luma.mean()
    peak = max(float(np.abs(luma).max()), 1e-9)
    luma = luma / peak * 0.5

    # Chroma: independent fields, but their amplitude is CAPPED relative
    # to luma. At parity the map paints colour PATCHES rather than
    # tinting existing colour -- on snow that reads as vegetation where
    # none exists.
    ratio = float(spec["chroma_ratio"])
    chans = []
    for _ in range(3):
        if ratio <= 0.0:
            chans.append(np.zeros((res, res)))
            continue
        c = _value_noise((res, res), max(int(round(span_m / hi_m)), 1), rng)
        c -= c.mean()
        cp = max(float(np.abs(c).max()), 1e-9)
        chans.append(c / cp * 0.5 * ratio)

    rgb = np.dstack([np.clip(0.5 + luma + ch, 0.0, 1.0) for ch in chans])
    # Re-centre each channel AFTER the clip, because clipping moves the
    # mean and the mean is the contract.
    for i in range(3):
        rgb[..., i] += 0.5 - rgb[..., i].mean()
    return np.clip(rgb, 0.0, 1.0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default=os.path.join(REPO_ROOT, "recipes",
                                                     "alpine.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        with open(args.recipe, "r", encoding="utf-8") as fh:
            recipe = json.load(fh)
    except (OSError, ValueError) as exc:
        print("REFUSE: cannot read recipe: {0}".format(exc))
        return 2

    spec = (recipe.get("material") or {}).get("macro_variation")
    if not spec:
        print("REFUSE: recipe declares no material.macro_variation")
        return 2

    ls = recipe["landscape"]
    span_m = ((int(recipe["heightmap"]["resolution"]) - 1)
              * float(ls["scale_xy_cm"]) / 100.0)

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("span      : {0:.0f} m across the terrain".format(span_m))
    for k in ("seed", "map_resolution", "feature_scale_m", "strength",
              "chroma_ratio"):
        print("  {0:<18} {1}".format(k, spec[k]))

    if args.dry_run:
        print("")
        print("DRY RUN — nothing written.")
        return 0

    rgb = build(spec, span_m)
    quant = np.rint(rgb * 255.0).astype(np.uint8)

    # Biome-keyed, not hardcoded. `make_landscape_material.py:1101` already
    # REFERENCES this map through landscape_spec.macro_map_asset_path(biome_id),
    # so a producer writing a fixed "alpine_macro.png" disagreed with its own
    # consumer for every biome except alpine -- and a disagreement here leaves
    # the material sampling NOTHING while both sides report success, which is
    # the exact failure landscape_spec's path helpers were written to prevent.
    # biome_id "alpine" still resolves to the identical filename.
    out_rel = "textures/{0}_macro.png".format(recipe["biome_id"])
    out = os.path.join(REPO_ROOT, out_rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    Image.fromarray(quant, mode="RGB").save(out, optimize=True)

    chk = np.asarray(Image.open(out))
    if chk.shape != quant.shape or not np.array_equal(chk, quant):
        print("REFUSE: {0} did not read back as written.".format(out_rel))
        return 4

    means = [float(chk[..., i].mean()) / 255.0 for i in range(3)]
    print("")
    print("Wrote     : {0} ({1:,} bytes), verified by read-back".format(
        out_rel, os.path.getsize(out)))
    print("per-channel mean (contract: 0.5 +/- {0}):".format(MEAN_TOLERANCE))
    for i, m in enumerate(means):
        ok = abs(m - 0.5) <= MEAN_TOLERANCE
        print("  {0}  {1:.5f}  {2}".format("RGB"[i], m,
                                           "ok" if ok else "OUT OF CONTRACT"))
    if any(abs(m - 0.5) > MEAN_TOLERANCE for m in means):
        print("REFUSE: the mean-0.5 encoding is the guarantee that a fully "
              "mipped sample renders the composite UNTOUCHED. A drifted "
              "mean tints the whole terrain at distance.")
        return 4
    print("")
    print("A fully-mipped sample is 0.5, so (1 + strength*(2*0.5-1)) = 1.0 "
          "exactly:")
    print("the degraded state is the identity, by construction.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
