"""derive_planting_field.py — the PLANTING-FIELD CONTRACT, made executable.

D-4 (research/audit/PRE_BRIEF4_CLOSURE_2026-09-15.md:65). Spec + schema:
recipes/schema.md, "v1.17 — the planting-field contract (normative)".

THE CIRCULARITY THIS EXISTS TO CUT
----------------------------------
The four tree species in `recipes/alpine_8k.json` are keyed to material
layer `Grass`, which is the FIFTH of five layers and therefore the SHADER
REMAINDER, `1 - (snow + rock + scree + forest_floor)` (mask_plan(5) ->
(4, True); make_landscape_material / derive_layer_weights.expand:425).

`place_foliage.load_inputs` samples that remainder from
`recipe.material.weightmap` = `textures/alpine_8k_weights.png`
(place_foliage.py:366, :595-620, :683) to decide WHERE trees go. But
`forest_floor` in that weightmap IS canopy cover splatted from the PLACED
tree instances (derive_layer_weights.py:29-35, :192, :215-235). So on a
regeneration the trees would be placed against a field their own previous
placement shaped: trees where trees already are -> forest_floor high ->
Grass remainder low -> the field that decides the next placement has been
moved by the last one. That is a feedback loop, not a suitability field.

THE CONTRACT (one-way dependency, NEVER a cycle)
------------------------------------------------
    PLANTING FIELD  (terrain only: slope / height / aspect / deposition,
                     canopy term forced to ZERO)
        -> tree PLACEMENT samples it
        -> canopy cover is computed FROM the placed trees
        -> RENDER WEIGHTMAP = planting field composed with canopy
                     (forest_floor grows where trees are; the Grass
                     remainder is what is left)

The render weightmap is RENDER-ONLY and is NEVER read back into placement.
The planting field takes NO canopy input, so it cannot be moved by the
trees it decides — the loop is cut structurally, not by convention.

Both fields come from ONE derivation, `derive_layer_weights.derive`,
called twice: cover=0 for the planting field, cover=canopy for the render
weightmap. There is no second copy of the mask formulae to disagree with
the first (non-negotiable 24).

    python scripts/derive_planting_field.py --out textures/alpine_8k_planting
    python scripts/derive_planting_field.py --selftest

REGENERATION STAYS GATED (X-1, F-2). This script DERIVES and PROVES the
contract; it does not place foliage, does not touch the editor, and does
not write `textures/alpine_8k_weights.png` (its --out default is a
DISTINCT prefix). Rewiring place_foliage to read the planting field
happens with the Brief-4 water carve, not here.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive_layer_weights as dlw  # noqa: E402 — ONE definition of the masks
from make_landscape_material import mask_plan  # noqa: E402 — ONE definition of
#                          the channel/remainder split, shared with the shader
#                          and place_foliage (non-negotiable 24)

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")


def _under_repo(path):
    """True only if `path` resolves inside REPO. --out is user-supplied and an
    absolute or ..-escaping value would write outside the repo (standing rule
    1). The default prefix is safe; this refuses a hostile one."""
    r = os.path.normcase(os.path.normpath(os.path.realpath(REPO)))
    p = os.path.normcase(os.path.normpath(os.path.realpath(path)))
    return p == r or p.startswith(r + os.sep)

# The four channels the render weightmap STORES, in order (R,G,B,A). The
# fifth layer (Grass) has no channel: it is the shader remainder. This is
# the make_landscape_material / derive_layer_weights.expand contract, and
# it is what place_foliage._layer_weight sums to form the remainder. Named
# once here so the "what placement samples" formula below cannot drift
# from it.
STORED_CHANNELS = ("snow", "rock", "scree", "forest_floor")


def remainder_field(weights):
    """The weight a species keyed to the REMAINDER layer samples.

    Mirrors place_foliage._layer_weight's remainder branch EXACTLY
    (place_foliage.py:615-620): sum the stored channels, clip 1 - sum to
    [0, 1]. 8-bit quantisation lets the stored channels sum a hair past 1,
    which without the clip would read as a NEGATIVE density.

    `derive` returns eight layers that sum to 1, so before clipping this
    equals wet_shore + dirt_path + gravel + meadow — the ground the trees
    actually stand on. The only canopy-dependent term inside the sum is
    forest_floor, which is precisely why the planting field zeroes it.
    """
    acc = np.zeros_like(weights["snow"], dtype=np.float32)
    for name in STORED_CHANNELS:
        acc = acc + weights[name]
    return np.clip(1.0 - acc, 0.0, 1.0).astype(np.float32)


def planting_and_render(h_m, spacing_m, depo01, cover01,
                        snow_base_m=dlw.SNOW_BASE_M, shaded_rad=0.0):
    """(planting_weights, render_weights), the two fields of the contract.

    PLANTING WEIGHTS: `derive` with the canopy term forced to ZERO. Pure
    function of terrain (height/slope/aspect) and the Gaea deposition map.
    Independent of `cover01` BY CONSTRUCTION — the argument is accepted
    only so the render field can use it; the planting field never does.

    RENDER WEIGHTS: `derive` with the real `cover01`. forest_floor is
    non-zero where trees are, and the remainder shrinks to match.

    REFUSES non-finite terrain (inherited from `derive`, which a NaN
    heightmap must not survive): a NaN propagates through every comparison
    as False and would yield a plausible all-remainder field.
    """
    zero = np.zeros_like(h_m, dtype=np.float32)
    plant, _, _ = dlw.derive(h_m, spacing_m, zero, depo01, zero,
                             snow_base_m=snow_base_m, shaded_rad=shaded_rad)
    render, _, _ = dlw.derive(h_m, spacing_m, zero, depo01, cover01,
                              snow_base_m=snow_base_m, shaded_rad=shaded_rad)
    return plant, render


def check_canopy(n_declared, n_splatted, cover01):
    """(ok, message) — REFUSE a canopy that is silently absent or broken.

    Direction 3. Three ways the canopy input is broken in a way that would
    make the render weightmap a PLAUSIBLE LIE — identical to the planting
    field, so the split reads as done when it never happened:

      * trees were declared but NONE landed on the grid (wrong origin or
        units): n_declared > 0 while n_splatted == 0. canopy_cover would
        return an all-zero field and the render weightmap would equal the
        planting field. A failed measurement must report that it failed,
        never the zero it could not distinguish from a real one (NN6).
      * the cover field holds non-finite values.
      * the cover field is out of the [0, 1] range canopy_cover promises.

    `n_declared` is instances READ from the plans; `n_splatted` is how
    many `canopy_cover` actually placed on the grid (its second return).
    """
    if not np.isfinite(cover01).all():
        return (False, "canopy cover holds non-finite values -- refusing "
                       "to compose a render weightmap from it")
    mn, mx = float(np.min(cover01)), float(np.max(cover01))
    if mn < -1e-6 or mx > 1.0 + 1e-6:
        return (False, "canopy cover out of [0,1] (min %.4f max %.4f) -- "
                       "refusing" % (mn, mx))
    if n_declared > 0 and n_splatted == 0:
        return (False, "%d tree instances were declared but NONE landed on "
                       "the grid (n_splatted=0). The render weightmap would "
                       "equal the planting field -- a split that reads as "
                       "done but never happened. Check origin/spacing; "
                       "refusing rather than writing the lie." % n_declared)
    return (True, "canopy ok: %d declared, %d splatted, cover in [%.3f, %.3f]"
            % (n_declared, n_splatted, mn, mx))


def _write_rgba(weights, path):
    img = np.stack([np.round(np.clip(weights[n], 0.0, 1.0) * 255).astype(
        np.uint8) for n in STORED_CHANNELS], axis=-1)
    Image.fromarray(img, "RGBA").save(path)


def selftest():
    """Three directions, on a synthetic terrain and tree set built from the
    SAME conventions the real derivation uses:

      - terrain: metres, one metre per cell (dlw.slope_aspect's spacing);
        a plateau-topped ridge, snow pushed out of the world so the
        open FLAT crest is high-remainder ground a stand can sit on --
        the same specimen shape derive_layer_weights.selftest uses.
      - trees: a foliage plan {"instances": [[x_cm, y_cm, ...], ...]},
        x_cm = px * 100, matching canopy_cover's cm->cell conversion with
        origin (0,0) and spacing 1 m. Read through canopy_cover itself, so
        the crown-disk splat is the real one, not a stand-in.

    (a) NO FEEDBACK  the field PLACEMENT samples (the planting remainder)
        is byte-identical whether the tree set is empty or dense -- the
        planting field cannot be moved by the trees it decides.
    (b) DISTINCT     the RENDER weightmap DOES move with canopy:
        forest_floor rises under the stand and the render remainder falls
        below the planting remainder there. The two fields are genuinely
        different, not a no-op relabelling.
    (c) REFUSE       NaN terrain refuses; and a declared-but-unlanded tree
        set refuses instead of returning a render == planting lie.
    """
    N = 256
    sp = 1.0
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    # plateau-topped ridge, snow out of the world (base 5000 m). The FLAT
    # crest strip (|yy-128| < 30 -> slope 0) is open, snow-free,
    # scree-free, rock-free ground: high planting remainder, where a stand
    # of trees has room to change forest_floor.
    ridge = 800.0 - np.maximum(np.abs(yy - N / 2) - 30.0, 0.0) * 0.45
    depo = np.zeros((N, N), dtype=np.float32)
    snow_out = 5000.0

    ok = True

    def check(name, cond):
        nonlocal ok
        print("  %-60s %s" % (name, "PASS" if cond else "FAIL"))
        ok = ok and bool(cond)

    # a dense stand on the flat crest, one tree per cell over a block.
    y0, y1, x0, x1 = 110, 150, 60, 120
    inst = []
    for py in range(y0, y1):
        for px in range(x0, x1):
            inst.append([float(px) * 100.0, float(py) * 100.0, 0.0])
    crown_r = 3.0

    tmpd = tempfile.mkdtemp(prefix="planting_selftest_")
    plan_path = os.path.join(tmpd, "stand.json")
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump({"instances": inst}, fh)
    try:
        cover_dense, n_dense = dlw.canopy_cover((N, N), sp, [plan_path],
                                                (0.0, 0.0), crown_r)
    finally:
        os.remove(plan_path)
        os.rmdir(tmpd)
    cover_none = np.zeros((N, N), dtype=np.float32)

    # --- (a) NO FEEDBACK --------------------------------------------------
    plant_none, render_none = planting_and_render(
        ridge, sp, depo, cover_none, snow_base_m=snow_out)
    plant_dense, render_dense = planting_and_render(
        ridge, sp, depo, cover_dense, snow_base_m=snow_out)
    pf_none = remainder_field(plant_none)
    pf_dense = remainder_field(plant_dense)
    max_move = float(np.abs(pf_none - pf_dense).max())
    check("(a) planting field placement samples is IDENTICAL with/without "
          "canopy (max move %.2e)" % max_move, max_move == 0.0)
    # and the stored terrain layers themselves are canopy-invariant
    terr_move = max(float(np.abs(plant_none[n] - plant_dense[n]).max())
                    for n in ("snow", "rock", "scree"))
    check("(a) snow/rock/scree are canopy-invariant (max move %.2e)"
          % terr_move, terr_move == 0.0)

    # --- (b) DISTINCT -----------------------------------------------------
    stand = np.zeros((N, N), bool)
    stand[y0 + 5:y1 - 5, x0 + 5:x1 - 5] = True   # interior, past the blur edge
    ff_dense = float(render_dense["forest_floor"][stand].mean())
    ff_none = float(render_none["forest_floor"][stand].mean())
    check("(b) render forest_floor RISES under the stand (%.2f vs %.2f)"
          % (ff_dense, ff_none), ff_dense > 0.3 and ff_none < 0.01)
    rr_dense = float(remainder_field(render_dense)[stand].mean())
    pr_stand = float(pf_dense[stand].mean())
    check("(b) render remainder FALLS below the planting field under the "
          "stand (%.2f < %.2f)" % (rr_dense, pr_stand),
          rr_dense < pr_stand - 0.2)
    # away from the stand, canopy is zero, so render == planting (sanity)
    away = np.zeros((N, N), bool)
    away[y0:y1, x1 + 20:x1 + 40] = True
    away_gap = float(np.abs(remainder_field(render_dense)[away]
                            - pf_dense[away]).max())
    check("(b) away from the stand render == planting (max gap %.2e)"
          % away_gap, away_gap < 1e-6)

    # --- (c) REFUSE -------------------------------------------------------
    try:
        planting_and_render(np.full((8, 8), np.nan, np.float32), sp,
                            np.zeros((8, 8), np.float32),
                            np.zeros((8, 8), np.float32))
        nan_refused = False
    except ValueError:
        nan_refused = True
    check("(c) NaN terrain refuses", nan_refused)

    # trees declared but none landed (wrong origin: all instances off-grid)
    tmpd2 = tempfile.mkdtemp(prefix="planting_selftest2_")
    off_path = os.path.join(tmpd2, "off.json")
    with open(off_path, "w", encoding="utf-8") as fh:
        json.dump({"instances": [[9.0e9, 9.0e9, 0.0]] * 100}, fh)
    try:
        cover_off, n_off = dlw.canopy_cover((N, N), sp, [off_path],
                                            (0.0, 0.0), crown_r)
    finally:
        os.remove(off_path)
        os.rmdir(tmpd2)
    ok_off, msg_off = check_canopy(100, n_off, cover_off)
    check("(c) declared-but-unlanded canopy refuses (n_splatted=%d)" % n_off,
          (not ok_off) and n_off == 0)
    # positive control: the real dense canopy PASSES check_canopy
    ok_pos, _ = check_canopy(len(inst), n_dense, cover_dense)
    check("(c) a real canopy PASSES check_canopy (n_splatted=%d)" % n_dense,
          ok_pos and n_dense > 0)

    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _tree_species(recipe):
    """Names of the species whose PLACEMENT the planting field governs:
    instanced foliage (not grass) that is vegetation (no `role`). This is
    the same test place_foliage.plan applies before computing transforms
    (place_foliage.py:645, :659), read from the recipe rather than a hard-
    coded list, so a new tree species is picked up automatically."""
    out = []
    for s in (recipe.get("foliage") or {}).get("species") or []:
        if not isinstance(s, dict):
            continue
        if s.get("system") == "grass" or "role" in s:
            continue
        out.append(s["name"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--recipe", default=RECIPE)
    ap.add_argument("--out", default="textures/alpine_8k_planting",
                    help="output PREFIX (repo-relative). Writes <prefix>_"
                         "planting.png (what placement samples), <prefix>_"
                         "render.png (render only) and <prefix>_sidecar.json. "
                         "Default is DISTINCT from the live weightmap "
                         "textures/alpine_8k_weights.png, which this never "
                         "writes.")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    prefix = a.out
    rec = json.load(open(a.recipe, encoding="utf-8"))

    # ---- output-path gates, on the RESOLVED paths -----------------------
    # A relative --out joins REPO; an absolute one is taken as given. Both
    # (1) must stay inside the repo (standing rule 1) and (2) must not land
    # on the LIVE render weightmap the recipe declares.
    def _resolve(rel_or_abs):
        return (rel_or_abs if os.path.isabs(rel_or_abs)
                else os.path.join(REPO, rel_or_abs))
    out_paths = {suffix: _resolve(prefix + suffix)
                 for suffix in ("_planting.png", "_render.png",
                                "_sidecar.json")}
    live_weightmap = os.path.normcase(os.path.normpath(os.path.realpath(
        os.path.join(REPO, rec["material"]["weightmap"]))))
    for suffix, op in out_paths.items():
        if not _under_repo(op):
            print("REFUSE: --out%s resolves outside the repo (%s). Standing "
                  "rule 1: no writes outside REPO_ROOT." % (suffix, op))
            return 2
        if os.path.normcase(os.path.normpath(os.path.realpath(op))) == \
                live_weightmap:
            print("REFUSE: --out%s would overwrite the LIVE render weightmap "
                  "(%s). This derivation writes its OWN artefacts; adopting "
                  "them into placement is the gated Brief-4 step, not this "
                  "one." % (suffix, op))
            return 2

    ls = rec["landscape"]
    spacing_m = float(ls["scale_xy_cm"]) / 100.0
    origin_m = (float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0)
    z_span_m = float(ls["z_scale_cm"]) / 100.0
    z_base_m = (float(ls["location_cm"][2])
                - float(ls["z_scale_cm"]) / 2.0) / 100.0

    hpath = os.path.join(REPO, rec["heightmap"]["source"])
    h16 = np.asarray(Image.open(hpath)).astype(np.float32)
    if h16.ndim != 2:
        print("REFUSE: heightmap is not single-channel")
        return 2
    h_m = h16 / 65535.0 * z_span_m + z_base_m
    if not np.isfinite(h_m).all():
        print("REFUSE: heightmap holds non-finite values")
        return 2
    shape = h_m.shape
    print("heightmap %s  spacing %.1f m  z %.1f..%.1f m"
          % (shape, spacing_m, float(h_m.min()), float(h_m.max())))

    depo_rel = "terrain/alpine_8k_deposition.png"
    depo_path = os.path.join(REPO, depo_rel)
    if os.path.isfile(depo_path):
        d = np.asarray(Image.open(depo_path).convert("I")).astype(np.float32)
        if d.shape != shape:
            d = np.asarray(Image.fromarray(d).resize(
                (shape[1], shape[0]), Image.BILINEAR)).astype(np.float32)
        depo = d / max(float(d.max()), 1e-6)
        depo_status = depo_rel
    else:
        # NOT SILENT. The Gaea deposition map feeds only the gravel term, so
        # its absence is recoverable -- but a silent zero while the sidecar
        # claims the file as an input is the fail-open the seed hard-fails on
        # (derive_layer_weights.py:547). Say so, and record what actually
        # happened, so the render weightmap's gravel is a known zero.
        print("WARNING: %s is absent; gravel term uses zeros. Recorded as "
              "ABSENT in the sidecar." % depo_rel)
        depo = np.zeros(shape, dtype=np.float32)
        depo_status = "ABSENT -- zeros substituted (gravel term is zero)"

    snow_layer = [l for l in rec["material"]["layers"] if l["name"] == "Snow"]
    if not snow_layer:
        print("REFUSE: the recipe declares no Snow layer to take the "
              "snow-line floor from")
        return 2
    snow_base = float(snow_layer[0]["height_m"][0])
    sun_az = float(rec["lighting"]["sun"]["azimuth_deg"])
    shaded = dlw.shaded_aspect_rad(sun_az)

    # THE LAYER CONTRACT (verified, not assumed -- F6). STORED_CHANNELS and
    # remainder_field assume a five-layer material whose fifth layer is the
    # shader remainder and whose stored channels are snow/rock/scree/
    # forest_floor. If the recipe's layer list ever changes, that assumption
    # is silently wrong; mask_plan is the SAME split the shader and
    # place_foliage use (non-negotiable 24). Refuse on any mismatch.
    layer_names = [l["name"] for l in rec["material"]["layers"]]
    direct, has_rem = mask_plan(len(layer_names))
    if not (has_rem and direct == len(STORED_CHANNELS)):
        print("REFUSE: this contract assumes %d stored channels + a remainder "
              "layer, but the recipe's %d layers resolve to mask_plan=%r. The "
              "planting/render split must be re-derived for this layer set."
              % (len(STORED_CHANNELS), len(layer_names), (direct, has_rem)))
        return 2
    remainder_layer = layer_names[-1]

    # crown radius: the MEASURED tree property, read from foliage.canopy
    # (alpine_8k.json:foliage.canopy.radius_m). The old placement_priors.canopy
    # path never existed as a real key (it lives only inside a _comment), so
    # the hardcoded fallback engaged every run -- pipeline rule 2 violation.
    canopy = (rec.get("foliage") or {}).get("canopy") or {}
    if "radius_m" not in canopy:
        print("REFUSE: recipe declares no foliage.canopy.radius_m -- the "
              "canopy crown radius is a measured input, not a script default.")
        return 2
    crown_r = float(canopy["radius_m"])

    species = _tree_species(rec)
    # every tree species must key to the REMAINDER layer, since that is the
    # field remainder_field reconstructs. A tree keyed to a stored channel is a
    # different sampling path this contract does not model -- refuse loudly.
    off_layer = [s["name"] for s in (rec.get("foliage") or {}).get("species")
                 or [] if s.get("name") in species
                 and s.get("layer") != remainder_layer]
    if off_layer:
        print("REFUSE: tree species %s are not keyed to the remainder layer "
              "%r; the planting field this derives is the remainder field, so "
              "their placement sampling is not modelled here."
              % (off_layer, remainder_layer))
        return 2

    # A declared tree species whose plan file is MISSING is the partial form
    # of the zero-plans fail-open (R2-1): dropping it silently under-counts
    # canopy and writes a plausibly-wrong render weightmap at exit 0. Refuse
    # PER SPECIES, naming the ones without a plan -- do not filter them away.
    plan_of = {s: os.path.join(REPO, "foliage", "%s_%s.json"
                               % (rec["biome_id"], s)) for s in species}
    missing = [s for s in species if not os.path.isfile(plan_of[s])]
    if missing:
        print("REFUSE: tree species %s have no foliage plan on disk (%s). A "
              "missing declared plan under-counts canopy and writes a "
              "plausibly-wrong render weightmap; generate the plans first "
              "(place_foliage, gated) or remove the species."
              % (missing, ", ".join("foliage/%s_%s.json"
                                     % (rec["biome_id"], s) for s in missing)))
        return 2
    plans = [plan_of[s] for s in species]
    n_declared = 0
    for p in plans:
        n_declared += len(json.load(open(p, encoding="utf-8")
                                    ).get("instances", []))
    # F2: every plan exists but they contribute NO instances is still a fail-
    # open -- the render weightmap would be canopy-free, identical to the
    # planting field, and exit 0. The plans must be (re)generated first.
    if species and n_declared == 0:
        print("REFUSE: the recipe declares tree species %s but their foliage "
              "plans contribute ZERO instances (found %d plan file(s)). The "
              "render weightmap would be canopy-free -- identical to the "
              "planting field. Generate the plans first (place_foliage, gated) "
              "or remove the species." % (species, len(plans)))
        return 2
    cover, n_splat = dlw.canopy_cover(shape, spacing_m, plans, origin_m,
                                      crown_r)
    print("tree species %s -> %d plans, %d instances declared, %d splatted"
          % (species, len(plans), n_declared, n_splat))

    ok, msg = check_canopy(n_declared, n_splat, cover)
    if not ok:
        print("REFUSE: %s" % msg)
        return 2
    print("  %s" % msg)

    try:
        plant, render = planting_and_render(
            h_m, spacing_m, depo, cover, snow_base_m=snow_base,
            shaded_rad=shaded)
    except ValueError as exc:
        print("REFUSE: %s" % exc)
        return 2

    plant_png = os.path.join(REPO, prefix + "_planting.png")
    render_png = os.path.join(REPO, prefix + "_render.png")
    os.makedirs(os.path.dirname(plant_png), exist_ok=True)
    _write_rgba(plant, plant_png)
    _write_rgba(render, render_png)

    pf = remainder_field(plant)
    rf = remainder_field(render)
    side = {
        "_what": ("The PLANTING-FIELD CONTRACT (D-4). Two fields from one "
                  "derivation; see recipes/schema.md 'v1.17 — the planting-"
                  "field contract'."),
        "one_way_dependency": ("planting field (canopy=0) -> placement -> "
                               "canopy -> render weightmap. The render "
                               "weightmap is NEVER read back into placement."),
        "inputs": {"heightmap": rec["heightmap"]["source"],
                   "deposition": depo_status,
                   "tree_species": species,
                   "foliage_plans": [os.path.relpath(p, REPO).replace(
                       "\\", "/") for p in plans],
                   "crown_radius_m": crown_r,
                   "instances_declared": n_declared,
                   "instances_splatted": n_splat},
        "outputs": {"planting_field": prefix + "_planting.png",
                    "render_weightmap": prefix + "_render.png",
                    "note": ("planting_field is what PLACEMENT must sample; "
                             "render_weightmap is RENDER-only. Neither is the "
                             "live textures/alpine_8k_weights.png.")},
        "stored_channels": list(STORED_CHANNELS),
        "remainder_layer": "%s (the last layer; the shader remainder)"
                           % remainder_layer,
        "constants": {"snow_base_m": snow_base, "sun_azimuth_deg": sun_az},
        "field_stats": {
            "planting_remainder_mean": round(float(pf.mean()), 4),
            "render_remainder_mean": round(float(rf.mean()), 4),
            "render_forest_floor_mean": round(
                float(render["forest_floor"].mean()), 4),
            "max_planting_minus_render_remainder": round(
                float((pf - rf).max()), 4),
        },
    }
    with open(os.path.join(REPO, prefix + "_sidecar.json"), "w",
              encoding="utf-8") as fh:
        json.dump(side, fh, indent=1)
    print("wrote %s_planting.png, %s_render.png, %s_sidecar.json"
          % (prefix, prefix, prefix))
    print("  planting remainder mean %.4f  render remainder mean %.4f  "
          "render forest_floor mean %.4f"
          % (pf.mean(), rf.mean(), render["forest_floor"].mean()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
