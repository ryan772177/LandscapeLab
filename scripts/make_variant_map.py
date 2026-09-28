"""make_variant_map.py — bake the sub-surface selector texture (schema v1.14).

OFFLINE. No editor, no `unreal`. Reads the adopted heightmap, the baked
weightmap and the recipe; writes ONE RGB PNG.

WHY THIS EXISTS
---------------
Pass 2 names FIVE ground surfaces. The weightmap carries THREE, refused at
`make_layer_weightmap.py:171`, and widening it would re-key
`place_foliage.py:665`'s `weights[..., idx]` (paired at :665/:668) under
157,554 placed conifers. R2's PASS 2 UPGRADE ruling: a layer keeps ONE weightmap channel
and may declare a SECOND surface selected by a baked, full-resolution
mask. This file bakes those masks.

    R  Snow  selector   (no sub-surface declared -> 0 everywhere)
    G  Rock  selector   scree / talus
    B  Grass selector   forest floor

Symmetric with the weightmap by design: same resolution, same 8-bit RGB,
one channel per layer in recipe order. A reader who understands one
understands the other.

WHY A BAKED TEXTURE AND NOT A SHADER TEST
------------------------------------------
R2 rejects deriving layer masks in the shader, TWICE, for the same reason:
a slope term reads the VERTEX normal, which is the DECIMATED mesh's normal
and flattens with distance — so a shader-side sub-surface dissolves at
exactly the range it exists to serve. The weightmap is baked for that
reason and so is this.

THE SCREE SELECTOR IS THE SHARED TALUS FIELD
--------------------------------------------
`foliage.rock_scatter` (schema v1.17) is a SHARED PHYSICAL FACT
(CLAUDE.md non-negotiable 19). This script computes the scree mask with
`rock_scatter.talus_deposit()` routed on `rock_scatter.landform_height()`
(the 16 m landform; the cliff-source slope comes from the same surface) —
the same functions, reading the same recipe block, that Pass 3 uses to
scatter talus MESHES. They cannot disagree, because they are not two
implementations. (Until 2026-09-27 this call routed on the raw surface
while the scatter had moved to the landform — audit-3, NN19.)

Cliff SOURCES read landform-scale slope. Cell-scale slope would
manufacture phantom sources out of `detail_relief` texture: measured
2026-08-03, 44.0% of the cell-scale >=45 deg area is texture, not
landform.

Exit codes:
  0  written and verified by read-back, OR a --dry-run that wrote nothing
  2  recipe or heightmap missing or invalid (the weightmap is OPTIONAL —
     read only for the coverage report at the tail, never a refusal cause)
  4  a written channel failed its read-back, or talus routing did not
     converge
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import rock_scatter as rsc  # noqa: E402 — the SHARED talus field, not a copy

REPO_ROOT = bootstrap.REPO_ROOT
UINT8_MAX = 255.0


def _norm(p):
    return os.path.normcase(os.path.abspath(p))


def forest_floor_band(height_m, spec):
    """Smooth 0..1 band over the tree-elevation range.

    Supersedes the v1.11 `material.forest_floor` TINT, which multiplied
    albedo toward a green constant. A tint cannot give the forest floor
    its own normal or roughness; a sub-surface can. The v1.11 entry stays
    in the recipe and in R2 as the superseded version (operating loop d) —
    it is not deleted.
    """
    lo, hi = [float(v) for v in spec["height_m"]]
    f = float(spec["feather_m"])
    t_in = np.clip((height_m - (lo - f)) / max(f, 1e-9), 0.0, 1.0)
    t_out = np.clip(((hi + f) - height_m) / max(f, 1e-9), 0.0, 1.0)
    sm = lambda t: t * t * (3.0 - 2.0 * t)      # noqa: E731
    return sm(t_in) * sm(t_out)


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

    mat = recipe["material"]
    layers = [l["name"] for l in mat["layers"]]
    if len(layers) != 3:
        print("REFUSE: expected 3 layers, got {0}".format(len(layers)))
        return 2

    ls = recipe["landscape"]
    spacing_m = float(ls["scale_xy_cm"]) / 100.0
    z_scale_m = float(ls["z_scale_cm"]) / 100.0

    src = os.path.join(REPO_ROOT, recipe["heightmap"]["source"])
    if not os.path.isfile(src):
        print("REFUSE: heightmap not found: {0}".format(src))
        return 2
    him = Image.open(src)
    if him.mode != "I;16":
        print("REFUSE: heightmap must be I;16, got {0!r}".format(him.mode))
        return 2
    height_m = np.asarray(him).astype(np.float64) / 65535.0 * z_scale_m
    n = height_m.shape[0]

    rs = (recipe.get("foliage") or {}).get("rock_scatter")
    if not isinstance(rs, dict):
        print("REFUSE: recipe declares no `foliage.rock_scatter` block "
              "(schema v1.17). The scree selector and Pass 3's talus "
              "scatter must read the SAME field; there is nothing to read.")
        return 2

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("heightmap : {0}  ({1} x {1}, spacing {2:.1f} m)".format(
        recipe["heightmap"]["source"], n, spacing_m))
    print("layers    : {0}".format(", ".join(layers)))
    print("")

    # ---------------------------------------------------------- G: scree --
    print("--- G channel: scree (shared talus field, foliage.rock_scatter) ---")
    for k in ("repose_deg", "cliff_source_slope_deg", "source_smooth_m",
              "runout_m", "mfd_exponent", "max_steps", "saturation"):
        print("  {0:<24} {1}".format(k, rs[k]))

    if args.dry_run:
        print("")
        print("DRY RUN — nothing written. (The talus routing is the "
              "expensive part and is skipped.)")
        return 0

    gy, gx = np.gradient(height_m, spacing_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    src_slope = rsc.landform_slope(height_m, spacing_m,
                                   rs["source_smooth_m"])
    print("")
    print("  cliff sources at {0:.0f} deg: {1:.3f}% of map on LANDFORM "
          "slope, against {2:.3f}% on cell-scale slope".format(
              rs["cliff_source_slope_deg"],
              100.0 * float((src_slope >= rs["cliff_source_slope_deg"]).mean()),
              100.0 * float((slope >= rs["cliff_source_slope_deg"]).mean())))

    # ROUTE ON THE LANDFORM, exactly as rock_scatter.build_context does
    # (ruled 2026-09-26, R12 AMENDED 2026-09-26b). This call routed on the
    # raw surface until audit-3 on 2026-09-27 caught it: the shared
    # `saturation` (0.4615) was DERIVED against the landform-routed field,
    # so a raw-routed scree channel saturated with it would read ~0.09 at
    # its own 99th percentile -- a near-empty scree mask passing every
    # gate, while this file's own header promises the SAME field as the
    # talus scatter (NN19). One function, both computers.
    _lf = rsc.landform_height(height_m, spacing_m, rs["source_smooth_m"])
    try:
        dep, n_src, steps = rsc.talus_deposit(
            height_m, slope, spacing_m,
            repose_deg=rs["repose_deg"],
            cliff_source_slope_deg=rs["cliff_source_slope_deg"],
            runout_m=rs["runout_m"],
            mfd_exponent=rs["mfd_exponent"],
            max_steps=rs["max_steps"],
            source_slope_deg=src_slope,
            route_height_m=_lf)
    except ValueError as exc:
        print("REFUSE: {0}".format(exc))
        return 4
    print("  routing converged at {0} steps (cap {1}), {2:,} source cells"
          .format(steps, rs["max_steps"], n_src))

    # Cache the routed deposit. It is deterministic and expensive (~5
    # minutes at the 600-step cap), and `saturation` is a TUNING knob
    # that must be judged against a render. Without the cache, every
    # candidate value costs a full reroute, which is how a knob ends up
    # picked from a percentile instead of from the picture.
    # BIOME-KEYED. This was the literal "alpine_talus_deposit.npy" until
    # 2026-08-13, and it FIRED: baking the 8129 selector overwrote
    # /Game/Alpine's 2017 cache with a 66,080,641-cell field, taking the file
    # from 31.0 MB to 504.2 MB. The cache is read back by the scree mask
    # (Pass 3's talus scatter RECOMPUTES via rock_scatter.build_context and
    # never reads it -- audit-3 2026-09-27), so a shape mismatch is the BEST case -- the
    # dangerous case is a consumer that reshapes or samples it without
    # checking. Recovered from git; the 8K field kept under its own name.
    #
    # Third instance of this class in one session, after derive_aux_maps'
    # flow/deposition/hillshade and make_macro_variation's macro map. The
    # first two were caught by reading the code BEFORE running it; this one was
    # caught only by `git status` afterwards, which is why it is worth the
    # comment: the defect is not the string, it is that a per-biome artefact
    # was named as if there were only ever one biome.
    _cache = os.path.join(REPO_ROOT, "terrain",
                          "{0}_talus_deposit.npy".format(recipe["biome_id"]))
    try:
        np.save(_cache, dep)
        print("  deposit cached -> {0} (tuning saturation needs no reroute)"
              .format(os.path.relpath(_cache, REPO_ROOT)))
    except OSError as _exc:
        print("  NOTE: could not cache the deposit: {0}".format(_exc))

    scree = 1.0 - np.exp(-dep / float(rs["saturation"]))

    # ---------------------------------------------------- B: forest floor --
    ff = mat.get("forest_floor")
    if ff is None:
        forest = np.zeros((n, n))
        print("")
        print("--- B channel: forest floor — NOT DECLARED, channel is 0 ---")
    else:
        forest = forest_floor_band(height_m, ff)
        print("")
        print("--- B channel: forest floor ({0}..{1} m, feather {2} m) ---"
              .format(ff["height_m"][0], ff["height_m"][1], ff["feather_m"]))

    # R is reserved for a Snow sub-surface. None is declared, and an
    # UNUSED CHANNEL IS WRITTEN AS ZERO AND SAID SO — an undeclared
    # channel carrying stale data is exactly the inert-field class this
    # project keeps paying for.
    snow = np.zeros((n, n))

    stack = np.dstack([snow, scree, forest])
    quant = np.rint(np.clip(stack, 0.0, 1.0) * UINT8_MAX).astype(np.uint8)

    # Independent recomputation from the QUANTISED bytes, same guard as
    # make_layer_weightmap: the bake above is what we believe, this is
    # what ships.
    back = quant.astype(np.float64) / UINT8_MAX
    drift = float(np.abs(back - np.clip(stack, 0.0, 1.0)).max())
    if drift > 1.0 / UINT8_MAX + 1e-9:
        print("REFUSE: quantised variants drift by {0:.6f}, above the "
              "1/255 rounding bound.".format(drift))
        return 4

    out_rel = mat.get("variant_map", "textures/alpine_variants.png")
    out = os.path.join(REPO_ROOT, out_rel)
    tex_dir = os.path.dirname(out)
    if not _norm(tex_dir).startswith(_norm(os.path.join(REPO_ROOT,
                                                        "textures"))):
        print("REFUSE: variant map escapes textures/")
        return 2
    os.makedirs(tex_dir, exist_ok=True)
    Image.fromarray(quant, mode="RGB").save(out, optimize=True)

    chk = np.asarray(Image.open(out))
    if chk.shape != quant.shape or not np.array_equal(chk, quant):
        print("REFUSE: {0} did not read back as written.".format(out_rel))
        return 4

    print("")
    print("Wrote     : {0} ({1:,} bytes), verified by read-back".format(
        out_rel, os.path.getsize(out)))
    print("max 8-bit quantisation drift {0:.6f} (bound {1:.6f})".format(
        drift, 1.0 / UINT8_MAX))
    print("")
    # COVERAGE IS REPORTED WITHIN ITS OWN LAYER, not map-wide.
    #
    # A selector only does anything where its LAYER is active. The
    # map-wide figure for the forest-floor band is 72%, which reads as
    # "72% of the world is forest floor"; conditioned on the Grass layer
    # it is 99%, which says the real thing — the sub-surface would
    # replace the primary almost everywhere. Two very different numbers
    # from the same array, and only one of them is about the decision
    # being made.
    wpath = os.path.join(REPO_ROOT, mat["weightmap"])
    weights = None
    if os.path.isfile(wpath):
        weights = np.asarray(Image.open(wpath)).astype(np.float64) / UINT8_MAX

    print("Selector coverage — this is what the material will blend:")
    print("  {0:<8} {1:<3} {2:>12} {3:>14} {4:>16}".format(
        "layer", "ch", "layer wt>0.5", "sel>0.5 of MAP", "sel>0.5 IN LAYER"))
    for i, (name, ch) in enumerate(zip(layers, (snow, scree, forest))):
        if weights is None or weights.shape[:2] != ch.shape:
            print("  {0:<8} {1:<3} {2:>12} {3:>13.2f}% {4:>16}".format(
                name, "RGB"[i], "n/a",
                100.0 * float((ch > 0.5).mean()),
                "WEIGHTMAP ABSENT"))
            continue
        lw = weights[..., i] > 0.5
        within = float((ch > 0.5)[lw].mean()) if lw.any() else 0.0
        print("  {0:<8} {1:<3} {2:>11.2f}% {3:>13.2f}% {4:>15.2f}%".format(
            name, "RGB"[i], 100.0 * float(lw.mean()),
            100.0 * float((ch > 0.5).mean()), 100.0 * within))
        if within > 0.90 and float(ch.mean()) > 0.0:
            print("      WARNING: this selector is ON across {0:.1f}% of its "
                  "own layer. A sub-surface that replaces the primary "
                  "almost everywhere is not a sub-surface — narrow the "
                  "band, or make it the PRIMARY and demote the other."
                  .format(100.0 * within))
    return 0


if __name__ == "__main__":
    sys.exit(main())
