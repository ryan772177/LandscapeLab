"""derive_post_water_count.py -- Brief 4 T9a: re-derive the foliage ruled
count for the POST-water world.

WHY (CARVE_PLAN T9 / RULING.md:78 / handoff:76-79). The ruled foliage count
is 219,659 (a MEASURED placement count at density 135/ha with the closure
ramps; plans/RECIPES_draft_closure.md:76-78). The water carve submerges
plantable ground, so that count moves DOWN and the un-amended FLOOR gate
(place_foliage.py:137, -20% of the ruled count) would misfire: fed the stale
219,659 it refuses a correct post-water placement (false REFUSE). This tool
measures the plantable placement WEIGHT lost to water and re-derives the ruled
count, so the FLOOR gate binds against the post-water intended total.

WHAT IT MEASURES (off-disk, no editor). It reconstructs place_foliage's
per-cell acceptance field for each tree species EXACTLY -- the placement
remainder (1 - snow - rock - scree - forest_floor from the canopy-free planting
field, the field place_foliage now samples), masked to the species' slope/
height band, times its closure ramp and centred flow bias -- reusing
placement_priors.closure_ramp / centred_bias (NO second copy of those formulae,
NN24). The submerged fraction is that acceptance weight falling inside the
derived water-body union (build_water_exclusion_mask.py -- the ONE definition
of where the water is), combined across species by weight_share:

    frac = SUM_s ws_s * sum(p_s in water) / SUM_s ws_s * sum(p_s all)
    ruled_post = round(RULED_PRE * (1 - frac))

The closure ramp and flow bias are INCLUDED (not omitted): 219,659 itself was
measured WITH them, so leaving them out would deflate the denominator (the
lakes sit where the ramp is near at_low=1.0 while the dry band thins toward
treeline) and bias ruled_post HIGH -- the strict-floor / false-REFUSE misfire
this tool exists to prevent. RULED_PRE = 219,659 is the anchor CARVE_PLAN names.

Read-backs (rule 12/13): plantable ha (binary, for the ~140 ha sanity check),
submerged ha, submerged weight fraction, per-species fractions, ruled_pre,
ruled_post, the +-2% replay band (Brief-5) and -20% floor around ruled_post,
each with the count it was measured over. A ZERO plantable or zero water-cell
count REFUSES (rule 13: a zero is not agreement).

    python research/brief4/scripts/derive_post_water_count.py
    python research/brief4/scripts/derive_post_water_count.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import placement_priors as pp  # noqa: E402 -- ONE definition of ramp/bias

RULED_PRE = 219659          # plans/RECIPES_draft_closure.md:76-78 (the anchor)
REPLAY_BAND = 0.02          # +-2%, the Brief-5 cold-replay band (handoff:78)
FLOOR_FRACTION = 0.80       # -20%, place_foliage.FLOOR_FRACTION (AUDIT F-1)


def _load_json(rel_or_abs):
    p = rel_or_abs if os.path.isabs(rel_or_abs) else os.path.join(REPO,
                                                                  rel_or_abs)
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _refuse_on_zero(n_plantable, n_water):
    """The rule-13 guard, extracted so the selftest can drive the REAL guard
    (not a re-implementation). Raises ValueError on a zero count; a zero
    plantable area cannot re-derive a ruled count, and an empty water union
    means there is nothing to re-derive -- both are silence, not agreement."""
    if n_plantable == 0:
        raise ValueError("ZERO plantable cells -- refusing (rule 13)")
    if n_water == 0:
        raise ValueError("water union mask is empty -- refusing (rule 13)")


def tree_species(recipe):
    """The species whose placement the planting field governs (system != grass,
    no role) -- the same test place_foliage/derive_planting_field apply."""
    out = []
    for s in recipe["foliage"]["species"]:
        if s.get("system") == "grass" or "role" in s:
            continue
        out.append(s)
    if not out:
        raise ValueError("recipe declares no tree species")
    return out


def water_mask_8k(shape):
    """The derived water-body union at the 8129 grid, from the SAME npz the
    encounters placer reads (build_water_exclusion_mask.py, NN24). The npz mask
    is on the 4x (2033) analysis grid; upsample by EXACT vertex indexing
    (8129 = 4*2032+1, a centred downsample), the same alignment
    derive_layer_weights.load_lake_footprints uses -- NOT a PIL resize."""
    npz = os.path.join(REPO, "encounters", "alpine_8k_water_exclusion.npz")
    if not os.path.isfile(npz):
        raise FileNotFoundError(
            "%s missing -- run research/brief4/scripts/"
            "build_water_exclusion_mask.py first" % npz)
    z = np.load(npz, allow_pickle=False)
    m = np.asarray(z["mask"]).astype(bool)
    ry = np.round(np.linspace(0, m.shape[0] - 1, shape[0])).astype(np.intp)
    cx = np.round(np.linspace(0, m.shape[1] - 1, shape[1])).astype(np.intp)
    return m[np.ix_(ry, cx)]


def species_acceptance(remainder, slope_deg, height_m, sp, flow):
    """place_foliage.plan's per-cell acceptance field p for one species, on the
    FULL grid (not the jittered candidate subset). Mirrors place_foliage.py
    lines ~735-767: p = remainder * band, * closure_ramp (if declared),
    * centred flow bias (if flow present and bias != 0), clipped to [0, 1].
    Reuses placement_priors so there is no second copy of the formulae."""
    s_lo, s_hi = [float(v) for v in sp["slope_deg"]]
    h_lo, h_hi = [float(v) for v in sp["height_m"]]
    band = ((slope_deg >= s_lo) & (slope_deg <= s_hi)
            & (height_m >= h_lo) & (height_m <= h_hi))
    p = remainder * band
    clo = sp.get("closure")
    if isinstance(clo, dict):
        p = p * pp.closure_ramp(height_m, h_lo, h_hi,
                                clo["at_low"], clo["at_high"])
    bias = float(sp.get("flow_bias", 0.0) or 0.0)
    if bias != 0.0 and flow is not None:
        p = p * pp.centred_bias(flow, bias, float(flow.mean()))
    return np.clip(p, 0.0, 1.0), band


def measure(planting_png, heightmap_png, recipe, water8k, flow):
    """(stats). Reads the planting field's stored channels, reconstructs the
    placement remainder EXACTLY as place_foliage._layer_weight does (1 - sum of
    the four stored channels, clipped), then per species builds the acceptance
    field and splits its weight by the water union."""
    wa = np.asarray(Image.open(planting_png).convert("RGBA")).astype(
        np.float64) / 255.0
    if wa.ndim != 3 or wa.shape[2] != 4:
        raise ValueError("planting field is not RGBA: %s" % (wa.shape,))
    remainder = np.clip(1.0 - wa[..., :4].sum(axis=2), 0.0, 1.0)

    h16 = np.asarray(Image.open(heightmap_png)).astype(np.float64)
    if h16.ndim != 2:
        raise ValueError("heightmap is not single-channel")
    if h16.shape != remainder.shape:
        raise ValueError("heightmap %s != planting field %s"
                         % (h16.shape, remainder.shape))
    ls = recipe["landscape"]
    z_span_m = float(ls["z_scale_cm"]) / 100.0
    height_m = h16 / 65535.0 * z_span_m           # z_base 0 (loc_z == z_scale/2)
    spacing_m = float(ls["scale_xy_cm"]) / 100.0
    if water8k.shape != remainder.shape:
        raise ValueError("water mask %s != grid %s"
                         % (water8k.shape, remainder.shape))
    if flow is not None and flow.shape != remainder.shape:
        raise ValueError("flow map %s != grid %s" % (flow.shape,
                                                     remainder.shape))

    gy, gx = np.gradient(height_m, spacing_m)      # same operator as place_foliage
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))

    species = tree_species(recipe)
    num, den = 0.0, 0.0        # SUM ws*sum(p in water), SUM ws*sum(p all)
    plantable_union = np.zeros(remainder.shape, dtype=bool)
    per_species = {}
    for sp in species:
        ws = float(sp["weight_share"])
        p, band = species_acceptance(remainder, slope_deg, height_m, sp, flow)
        p_all = float(p.sum())
        p_sub = float((p * water8k).sum())
        plantable_union |= band & (remainder > 0.0)
        num += ws * p_sub
        den += ws * p_all
        per_species[sp["name"]] = {
            "weight_share": ws,
            "accept_weight": round(p_all, 1),
            "submerged_weight": round(p_sub, 1),
            "submerged_fraction": round(p_sub / p_all, 6) if p_all else 0.0,
        }

    n_plant = int(plantable_union.sum())
    n_sub = int((plantable_union & water8k).sum())
    _refuse_on_zero(n_plant, int(water8k.sum()))
    if den <= 0.0:
        raise ValueError("total acceptance weight is zero -- refusing")

    frac = num / den
    cell_ha = (spacing_m * spacing_m) / 1e4
    ruled_post = int(round(RULED_PRE * (1.0 - frac)))
    return {
        "grid": list(remainder.shape),
        "spacing_m": spacing_m,
        "flow": "LOADED" if flow is not None else "ABSENT (no flow bias in p)",
        "plantable_cells": n_plant,
        "plantable_ha_binary": round(n_plant * cell_ha, 1),
        "submerged_plantable_cells": n_sub,
        "submerged_ha_binary": round(n_sub * cell_ha, 1),
        "submerged_weight_fraction": round(frac, 6),
        "per_species": per_species,
        "ruled_pre": RULED_PRE,
        "ruled_post": ruled_post,
        "replay_band_pm2pct": [int(round(ruled_post * (1 - REPLAY_BAND))),
                               int(round(ruled_post * (1 + REPLAY_BAND)))],
        "floor_minus20pct": int(math.ceil(FLOOR_FRACTION * ruled_post)),
        "water_union_cells_8k": int(water8k.sum()),
    }


def selftest():
    """Directions, no disk:
      A. a lake over half a uniform in-band field -> fraction 0.5 -> ruled
         halves (weight ratio, one species).
      B. NO water -> fraction 0 -> ruled_post == ruled_pre.
      C. the REAL _refuse_on_zero guard raises on a zero count and does NOT
         raise on nonzero (not a re-implementation -- the production guard)."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print("  %-56s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and bool(cond)

    N = 100
    p = np.ones((N, N))               # uniform acceptance, one synthetic species
    water = np.zeros((N, N), bool)
    water[:, : N // 2] = True
    frac = float((p * water).sum()) / float(p.sum())
    ruled = int(round(RULED_PRE * (1 - frac)))
    check("A: half-covered -> fraction 0.5 (%.3f)" % frac, abs(frac - 0.5) < 1e-9)
    check("A: ruled halves (%d)" % ruled, abs(ruled - RULED_PRE * 0.5) < 1.0)

    frac0 = float((p * np.zeros((N, N), bool)).sum()) / float(p.sum())
    check("B: no water -> fraction 0 -> ruled_pre",
          frac0 == 0.0 and int(round(RULED_PRE * (1 - frac0))) == RULED_PRE)

    raised = False
    try:
        _refuse_on_zero(0, 5)
    except ValueError:
        raised = True
    raised2 = False
    try:
        _refuse_on_zero(5, 0)
    except ValueError:
        raised2 = True
    no_raise = True
    try:
        _refuse_on_zero(5, 5)
    except ValueError:
        no_raise = False
    check("C: _refuse_on_zero raises on zero plantable AND zero water, "
          "not on nonzero", raised and raised2 and no_raise)

    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--planting", default=None,
                    help="planting field PNG; default reads "
                         "foliage.planting_field from the recipe")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    recipe = _load_json(a.recipe)
    fol = recipe.get("foliage") or {}
    # LOW-4: resolve BOTH the planting field and the water mask from the recipe
    # (CLI --planting is an override), so this measures the SAME field/mask
    # placement uses -- a moved recipe pointer cannot silently split them.
    pf_rel = a.planting or fol.get("planting_field")
    if not pf_rel:
        print("REFUSE: no planting field -- recipe declares no "
              "foliage.planting_field and --planting not given")
        return 2
    planting = pf_rel if os.path.isabs(pf_rel) else os.path.join(REPO, pf_rel)
    if not os.path.isfile(planting):
        print("REFUSE: planting field %s missing -- run "
              "scripts/derive_planting_field.py --out "
              "textures/alpine_8k_planting first" % pf_rel)
        return 2
    heightmap = os.path.join(REPO, recipe["heightmap"]["source"])

    shape = np.asarray(Image.open(planting)).shape[:2]
    water8k = water_mask_8k(shape)
    # flow, the SAME map + loader place_foliage uses (NN24)
    flow, fstatus = pp.load_flow(
        shape[0], filename=pp.aux_map_names(recipe["biome_id"])["flow"])
    if flow is None:
        print("NOTE: flow map %s -- flow bias omitted from the acceptance "
              "field (place_foliage would also have no bias then)" % fstatus)

    stats = measure(planting, heightmap, recipe, water8k, flow)

    print(json.dumps(stats, indent=2))
    print("")
    print("RULED COUNT re-derived for the post-water world:")
    print("  pre-water (anchor)   %8d" % stats["ruled_pre"])
    print("  submerged fraction   %8.4f  (%.1f ha of %.1f ha plantable)"
          % (stats["submerged_weight_fraction"],
             stats["submerged_ha_binary"], stats["plantable_ha_binary"]))
    print("  POST-water ruled     %8d" % stats["ruled_post"])
    print("  +-2%% replay band     %8d .. %d"
          % (stats["replay_band_pm2pct"][0], stats["replay_band_pm2pct"][1]))
    print("  -20%% FLOOR gate      %8d  (pass place_foliage --ruled-count %d)"
          % (stats["floor_minus20pct"], stats["ruled_post"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
