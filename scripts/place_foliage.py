"""place_foliage.py — schema v1.6 foliage placement.

TWO PHASES, and the split is deliberate.

  PHASE 1 (default, LOCAL): compute every instance transform from the
  heightmap, the BAKED weightmap and the flow map, report the
  distribution, and write one JSON per species into foliage/. No editor
  contact at all. Everything that decides WHERE a plant goes is
  verifiable offline, at full resolution, before anything is spawned.

  PHASE 2 (--place): hand those files to the editor and build one
  instanced-mesh actor per species. The payload READS THE FILE rather
  than carrying transforms inline — 150k instances is megabytes, and
  this project has already lost a push to a response that outgrew the
  transport (exit 5, 2026-08-02). A path in, a count out.

WHY DENSITY IS THE FIRST GATE
`density_per_hectare` reads as a small number and is not one. This map is
8064 m square = 6503 hectares, so the recipe's 900/ha is 5.85 MILLION
instances before any masking. On the documented hardware — integrated
GPU, Software Lumen, Medium scalability — that is not a slow scene, it
is a dead editor. Two gates, in order (Pass 3 2026-09-16 — this passage
used to imply one up-front refusal): the PRE-gate compares the gross
unmasked count against 40x the ceiling and refuses only a request no
plausible mask could survive (900/ha's 5.85M does NOT trip it); the
POST-PLAN gate compares the planned total against MAX_INSTANCES and
refuses BEFORE anything is written — so the 900/ha case runs the full
(multi-minute) planning pass first, then refuses with the arithmetic
and the density that would fit. It never silently truncates: a foliage
pass that quietly placed a tenth of what was asked would read as "the
density parameter does nothing".

WHAT DECIDES PLACEMENT, and why each source rather than the obvious one

  layer weight   THE BAKED WEIGHTMAP CHANNEL, not a re-evaluation of the
                 recipe's slope/height bands. Schema v1.6 makes this
                 normative and it is not pedantry: the material feathers
                 each height bound outward by
                 (1 - blend_sharpness) * 0.06 * z_scale_m = 115 m on this
                 world, so the bands and the bake disagree by a wide
                 margin. Re-deriving would put grass where the render
                 shows rock — two instruments disagreeing about one
                 decision, which sections 1.9 and 14.5 exist to prevent.
  slope/height   The species' OWN limits, applied on top as an extra
                 mask. "This plant does not grow on a 40-degree face" is
                 independent of where its layer happens to be.
  flow_bias      terrain/alpine_flow.png, which has been on disk and
                 unused since the erosion work. Water concentration is
                 where vegetation is densest in reality; positive bias
                 follows it, negative avoids it.

Sampling is a JITTERED GRID, not uniform random. Random points clump and
leave holes at the same density — that is what "random" means — and
clumping reads as pattern. One candidate per cell, jittered inside it,
gives even coverage with no visible lattice.

Exit codes:
  8  another heavy operation holds the lock (scripts/resource_guard.py)
  0  transforms computed and written (and placed, if --place)
  1  unexpected error / bad arguments
  2  recipe, heightmap or weightmap missing or invalid. A missing flow
     map is NOT exit 2: flow bias DEGRADES to a printed FLOW_* status
     and the run continues without it.
  3  a refusal gate fired: the requested density exceeds MAX_INSTANCES
     (ceiling, nothing written); the placed total fell below the ruled
     floor (--ruled-count, F-1; the plan files were written but must not
     be placed); a settlement-exclusion/town-plan error; a rock-plan
     adoption failure; an --exclude-only refusal
  4  a probe returned nothing, or the editor refused
  7  the open level does not match recipe landscape.level_path
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landscape_spec  # noqa: E402 — ruling (c) pivot limit, one copy decides
import placement_priors  # noqa: E402 — flow + canopy priors, one definition
import resource_guard   # noqa: E402 — RAM check + heavy-op lock
import plan_stamp       # noqa: E402 — ONE declaration of what a plan's
#                          inputs are, shared with plan_city, plan_encounters
#                          and check_plan_freshness

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLIAGE_DIR = os.path.join(REPO_ROOT, "foliage")
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

# Ceiling for the WHOLE recipe, all species combined. Chosen for the
# documented hardware (integrated GPU, Software Lumen, Medium
# scalability) rather than for a workstation. Raise it deliberately and
# with a capture to back the decision, never to make a run stop
# complaining.
#
# IMPORTED, NOT RETYPED (non-negotiable 24). This was its own literal
# 250000 until 2026-08-08 while rock_scatter.py's comment claimed the two
# were "shared" — rocks and vegetation are placed into ONE
# InstancedFoliageActor set and compete for ONE budget, so two copies
# could drift and let the pair sum past the number chosen for this
# hardware, with each tool internally consistent. Sharing is now
# structural instead of asserted (non-negotiable 25).
from rock_scatter import MAX_INSTANCES  # noqa: E402,F401
from angular_budget import vfov_from_hfov, dist_for_pixels  # noqa: E402
import town_exclusion  # noqa: E402
from make_landscape_material import mask_plan  # noqa: E402

# E1, ruled 2026-09-09: culls are DERIVED from recipe.perception, not authored.
# GROUND COVER IS EXCLUDED until a ruling, and this list is the exclusion.
# HLOD proxies only take over BEYOND the streaming range (256 m,
# RuntimePartition.cpp:27), so a Meadow culled at its detail boundary of 18.6 m
# would be absent from 18.6 m to 256 m with NOTHING representing it. The
# brief's rule is that a cull may sit at a band boundary only where the NEXT
# BAND EXISTS; for trees it does (imposters + 1,042 HLOD proxies), for grass it
# does not. Derived values are still COMPUTED and recorded for these species so
# the ruling can be made on numbers.
#
# GroundClutter (Brief 7 Phase 1, R-ROCKS-BACK) is the same class: a
# grass-system carpet on the Grass layer, culled at its authored 70 m (§6d)
# with nothing below the streaming range to represent it, so the 2026-09-09
# ground-cover ruling applies to it exactly as to Meadow and Blueberry. It
# has no measured placed height in the 2026-09-05 bench (it was removed
# before that capture and is not re-measurable until it is placed post-merge),
# so its derived cull cannot be computed and it MUST be excluded explicitly
# rather than silently fall back -- which is what check_derived_culls asserts.
GROUND_COVER = {"Meadow", "Blueberry", "GroundClutter"}

# THE FLOOR, as a fraction of the ruled count. A plan that places below
# this fraction of what the ruling asked for is REFUSED (D-3, gate F-1 /
# E-2). Ceiling-only gates (the `>` comparisons at the density and total
# checks) cannot see a plan that is quietly HALF the intended size: the
# 152-instance regeneration and the 111,079-against-a-ruled-220,000
# shortfall both exited 0 and reported success
# (plans/RECIPES_draft_closure.md:141).
#
# 0.80 is the -20% bound RULED in AUDIT.md F-1, not a knob. It is a MODULE
# CONSTANT and NOT a run flag on purpose: widening a floor until a run goes
# green is the exact move verification-practice forbids ("Never widen until
# the run goes green"). Raise it deliberately, in this file, with the reason.
FLOOR_FRACTION = 0.80


def _is_count(v):
    """True only for a real, finite, non-negative instance count.

    A count is an int by construction (len of a list). bool is a subclass of
    int and is rejected. NaN is the real quarry: NaN fails EVERY comparison,
    so the floor's `placed < need` is False for a NaN count and a NaN would
    PASS the floor — requiring int outright makes that unrepresentable.
    (A `>= 0` test would actually reject NaN; the danger was never there,
    it is in the refusal comparison.) Shape before content
    (verification-practice, direction 3): a check that interrogates a
    value it has not first shape-validated fails open on the inputs it never
    imagined.
    """
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def floor_gate_verdict(placed, ruled, fraction=FLOOR_FRACTION):
    """The FLOOR gate (F-1 / E-2), as a pure, offline-testable contract.

    Returns (status, need, message) where status is one of:

      PASS     placed >= fraction * ruled -- the plan is within the -20% bound
      REFUSE   placed < the floor, OR `placed` is not a readable count. A
               broken read-back fails CLOSED: placement is the unguarded
               action here, so an unreadable count must stop it, never wave it
               through with a fabricated number (a failed measurement reports
               that it failed -- it never reports the number it could not take).
      DEGRADE  `ruled` is missing or malformed. Missing information DEGRADES
               with a NAMED GAP (NN6) rather than silently passing: without a
               ruled count the floor cannot bind, and the honest outcome is to
               SAY the gate did not run -- not a green that reads like it did.

    `need` is the derived floor (ceil(fraction * ruled)) when it could be
    computed, else None. `placed` is the count READ BACK from the written
    plans, not the in-memory planning total.
    """
    if not (isinstance(ruled, int) and not isinstance(ruled, bool)
            and ruled > 0):
        return ("DEGRADE", None,
                "DEGRADE (NN6): no valid ruled count (got {0!r}). The floor "
                "gate cannot bind and did NOT run -- a plan half the intended "
                "size would NOT be caught. Pass --ruled-count N (the intended "
                "total, AUDIT F-1) to arm it.".format(ruled))
    if not _is_count(placed):
        return ("REFUSE", None,
                "REFUSE: the placed count could not be read back ({0!r}); "
                "refusing rather than placing against an unknown total."
                .format(placed))
    need = int(math.ceil(fraction * ruled))
    if placed < need:
        return ("REFUSE", need,
                "REFUSE: placed {0:,} is below the floor of {1:,} "
                "({2:.0%} of the ruled {3:,}); that is a shortfall of {4:.1%}, "
                "past the -{5:.0%} bound. Nothing should be placed. Do NOT "
                "lower --ruled-count to silence this: re-derive the density "
                "(RECIPES_draft_closure.md:141)."
                .format(placed, need, fraction, ruled,
                        1.0 - placed / float(ruled), 1.0 - fraction))
    return ("PASS", need,
            "PASS: placed {0:,} >= floor {1:,} ({2:.0%} of ruled {3:,})."
            .format(placed, need, fraction, ruled))


def override_slot_verdict(n_overrides, n_slots):
    """The override-list SLOT-COUNT gate (F-3), as a pure, offline contract.

    Override lists are POSITIONAL, in the mesh's own slot order
    (import_heightmap.py:1314). The declared-vs-read-back gate already exists
    (this file's editor payload); the GAP it does not close is that nothing
    checks the LIST LENGTH against the mesh's material slot count. Latent only
    because every current mesh has 1 slot -- a positional list of the wrong
    length silently mis-orders on a multi-slot mesh.

    Returns (status, message):

      SKIP     no override list declared -- nothing positional to mis-order.
      PASS     len(list) == slot count.
      REFUSE   len(list) != slot count (the mis-order), OR the mesh reports 0
               slots while a list is declared (a contradiction), OR the count
               is malformed. Applying a mis-ordered list is the unguarded
               action, so these fail CLOSED.
      DEGRADE  the slot count is genuinely unavailable (None): a NAMED GAP
               (NN6). This is the offline case -- the live check reads the slot
               count from the mesh IN THE EDITOR, where it is available, and
               the caller there escalates a DEGRADE to a REFUSE because a set
               is imminent.

    `n_slots` is READ BACK from the mesh (len(static_materials)); None means it
    could not be read at all, distinct from 0 (a mesh that genuinely has none).
    """
    if not (isinstance(n_overrides, int) and not isinstance(n_overrides, bool)
            and n_overrides >= 0):
        return ("REFUSE",
                "REFUSE: override count is malformed ({0!r}); refusing rather "
                "than applying a list of unknown length.".format(n_overrides))
    if n_overrides == 0:
        return ("SKIP", "SKIP: no override_materials declared.")
    if n_slots is None:
        return ("DEGRADE",
                "DEGRADE (NN6): the mesh material slot count is unavailable "
                "here; the length check cannot run offline. It runs at --place "
                "time in the editor, where static_materials is readable.")
    if not (isinstance(n_slots, int) and not isinstance(n_slots, bool)):
        return ("REFUSE",
                "REFUSE: slot count is malformed ({0!r}); refusing rather "
                "than trusting an unvalidated positional list."
                .format(n_slots))
    if n_slots <= 0:
        return ("REFUSE",
                "REFUSE: the mesh reports {0} material slot(s) but {1} "
                "override(s) are declared. A zero read is silence, not "
                "agreement (rule 13); refusing.".format(n_slots, n_overrides))
    if n_overrides != n_slots:
        return ("REFUSE",
                "REFUSE: override_materials has {0} entr(y/ies) but the mesh "
                "has {1} material slot(s). The list is POSITIONAL and would "
                "mis-order; refusing before any material is set.".format(
                    n_overrides, n_slots))
    return ("PASS",
            "PASS: {0} override(s) match {1} material slot(s).".format(
                n_overrides, n_slots))


def _species_heights():
    """Measured mesh heights, or {} if the file is absent.

    NOT the recipe's `height_m` -- that field is the ELEVATION BAND a species
    is planted in ([120, 640] m above sea level), a different quantity that
    happens to share the name. Writing a plant height into it would silently
    destroy the placement band.
    """
    p = os.path.join(REPO_ROOT, "_verify", "bench", "2026-09-05",
                     "species_heights.json")
    if not os.path.isfile(p):
        return {}
    return json.load(open(p, encoding="utf-8")).get("species", {})


def _cull_cm_for(sp, perception, heights, streaming_range_cm=0):
    """(cull_cm, derivation) for one species.

    `streaming_range_cm` is recipe.streaming.main_loading_range_cm -- the
    ceiling every derived cull clamps to (RULED 2026-09-11, R-RANGE): the
    detail band ends where the world streams out, so a larger cull is
    dead code. Passed in by the caller FROM THE RECIPE, never typed; 0
    means no ceiling (legacy recipes without a streaming block).

    Returns the AUTHORED value unchanged when there is no perception block, no
    measured height, or the species is ground cover -- and says which, in the
    derivation, so the sidecar never carries a number whose origin is unclear.
    """
    authored_m = float(sp.get("cull_distance_m") or 0.0)
    authored_cm = int(round(authored_m * 100.0))
    name = sp.get("name")
    d = {"species": name, "authored_cull_m": authored_m, "applied": "authored"}

    if not perception:
        d["reason"] = "no recipe.perception block"
        return authored_cm, d

    cam = perception["declared_camera"]
    th = perception["thresholds_px"]
    key = perception.get("cull_threshold", "detail")
    h = heights.get(name) or {}
    placed = h.get("placed_height_p50_m")
    d.update({"threshold": key, "threshold_px": th.get(key),
              "fov_h_deg": cam["fov_h_deg"], "res": cam["res"],
              "mesh_height_m": h.get("mesh_height_m"),
              "placed_height_p50_m": placed,
              "height_source": h.get("mesh_height_source")})

    if placed is None:
        d["reason"] = ("no measured placed height in "
                       "_verify/bench/2026-09-05/species_heights.json")
        return authored_cm, d

    vf = vfov_from_hfov(cam["fov_h_deg"], cam["res"][0], cam["res"][1])
    derived_m = dist_for_pixels(placed, float(th[key]), vf, cam["res"][1])
    vf_floor = vfov_from_hfov(cam["fov_h_deg"], cam["floor_res"][0],
                              cam["floor_res"][1])
    d["vfov_deg"] = round(vf, 4)
    d["derived_cull_m"] = round(derived_m, 2)
    d["derived_cull_m_at_floor_res"] = round(
        dist_for_pixels(placed, float(th[key]), vf_floor, cam["floor_res"][1]), 2)

    if name in GROUND_COVER:
        d["applied"] = "authored"
        d["reason"] = ("GROUND COVER: derived value computed but NOT applied. "
                       "The next band down is unoccupied between the derived "
                       "cull and the 256 m streaming range where HLOD starts, "
                       "so culling there would widen a visible gap rather "
                       "than close one. RULED 2026-09-09 by Ryan: ground "
                       "cover KEEPS its authored cull.")
        return authored_cm, d

    d["applied"] = "derived"
    derived_cm = int(round(derived_m * 100.0))
    ceiling_cm = int(streaming_range_cm or 0)
    if ceiling_cm > 0:
        d["streaming_range_cm"] = ceiling_cm
        if derived_cm > ceiling_cm:
            d["applied"] = "derived, clamped to streaming range"
            d["derived_cull_m_unclamped"] = d["derived_cull_m"]
            d["derived_cull_m"] = round(ceiling_cm / 100.0, 2)
            return ceiling_cm, d
    return derived_cm, d


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.realpath(p)))


def _inside_repo(p):
    return _norm(p).startswith(_norm(REPO_ROOT) + os.sep)


def load_inputs(recipe, heightmap=None):
    """(height_m, weights, flow, origin_m, spacing_m, flow_status).

    All fields at map resolution. `flow_status` is a
    `placement_priors.FLOW_*` constant and is NOT inferable from
    `flow is None`: an absent map and a wrong-resolution map are
    different failures and used to be the same `None` (non-negotiable 6).
    """
    from PIL import Image

    ls, hm = recipe["landscape"], recipe["heightmap"]
    src = os.path.abspath(heightmap or os.path.join(REPO_ROOT, hm["source"]))
    if not _inside_repo(src):
        raise ValueError("heightmap escapes REPO_ROOT: {0}".format(src))
    arr = np.asarray(Image.open(src)).astype(np.float64)
    n = arr.shape[0]

    z_scale_cm = float(ls["z_scale_cm"])
    span_cm = (float(hm["resolution"]) - 1.0) * float(ls["scale_xy_cm"])
    spacing_m = (span_cm / max(n - 1.0, 1.0)) / 100.0
    height_m = (arr / 65535.0) * (z_scale_cm / 100.0)

    # THE PLACEMENT FIELD, not necessarily the RENDER weightmap. When the
    # recipe declares `foliage.planting_field`, PLACEMENT samples that field
    # instead of material.weightmap. This is the planting-field contract
    # (derive_planting_field.py; schema v1.17): the render weightmap's
    # forest_floor channel is canopy splatted from the PLACED trees, so
    # sampling it to decide the NEXT placement is a feedback loop -- trees
    # where trees already are. The planting field is the same derivation with
    # the canopy term forced to zero, so it cannot be moved by the trees it
    # decides. It carries the SAME four stored channels (snow/rock/scree/
    # forest_floor, forest_floor ~0), so _layer_weight's remainder logic is
    # unchanged. The material/shader still reads material.weightmap; only
    # placement reads this. Absent -> the render weightmap, the prior
    # behaviour (other recipes and the offline corpus keep working).
    _pf_rel = (recipe.get("foliage") or {}).get("planting_field")
    wpath = os.path.join(REPO_ROOT, _pf_rel or recipe["material"]["weightmap"])
    if not os.path.isfile(wpath):
        raise FileNotFoundError(
            "{0} — {1}".format(
                wpath,
                "run scripts/derive_planting_field.py --out "
                "textures/alpine_8k_planting first (foliage.planting_field)"
                if _pf_rel else
                "run make_layer_weightmap first; foliage density comes "
                "from the BAKE, not from the recipe bands"))
    print("  placement field: {0}  ({1})".format(
        os.path.relpath(wpath, REPO_ROOT).replace("\\", "/"),
        "planting field -- canopy-free, feedback loop cut"
        if _pf_rel else "render weightmap (no foliage.planting_field declared)"))
    # FOUR STORED CHANNELS PLUS THE SHADER REMAINDER (schema v1.26,
    # 2026-09-12). This read was "RGB" while the recipe declared FIVE
    # layers, so a species keyed to the last one indexed channel 4 of a
    # 3-channel array and the run died with `index 4 is out of bounds`.
    # It failed LOUDLY, which is the only reason it is a bug report rather
    # than a forest planted against the wrong mask -- had there been four
    # layers it would have read Grass's density out of the alpha channel
    # and placed a plausible, wrong forest in silence.
    #
    # `mask_plan` is IMPORTED from the material builder, not restated: the
    # density a species is planted at must come from the same channel the
    # shader blends, and a second copy of that mapping would diverge the
    # first time a layer was added (NN24).
    weights = (np.asarray(Image.open(wpath).convert("RGBA"))
               .astype(np.float64) / 255.0)
    if weights.shape[0] != n:
        raise ValueError(
            "weightmap is {0} but the heightmap is {1}; they must be the "
            "same grid or every lookup is off"
            .format(weights.shape[0], n))

    # The flow map is a SHARED PHYSICAL FACT — the rock path reads the
    # same drainage this does. Loaded by the one implementation in
    # placement_priors so the two cannot follow different watercourses
    # (non-negotiable 19). It was inline here until 2026-08-08.
    # Filename from the recipe's biome_id, not the module default: a second
    # biome must read ITS OWN drainage. The default was "alpine_flow.png" for
    # every caller until 2026-08-13, so an 8129 alpine variant would have
    # planted trees against /Game/Alpine's watercourses. biome_id "alpine"
    # resolves to the identical name.
    flow, flow_status = placement_priors.load_flow(
        n, filename=placement_priors.aux_map_names(recipe["biome_id"])["flow"])

    origin_m = (float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0)
    return height_m, weights, flow, origin_m, spacing_m, flow_status


def _bilinear(field, gx, gy):
    n = field.shape[0]
    gx = np.clip(gx, 0.0, n - 1.001)
    gy = np.clip(gy, 0.0, n - 1.001)
    x0 = np.floor(gx).astype(np.int64)
    y0 = np.floor(gy).astype(np.int64)
    tx, ty = gx - x0, gy - y0
    x1, y1 = np.minimum(x0 + 1, n - 1), np.minimum(y0 + 1, n - 1)
    top = field[y0, x0] * (1 - tx) + field[y0, x1] * tx
    bot = field[y1, x0] * (1 - tx) + field[y1, x1] * tx
    return top * (1 - ty) + bot * ty


def load_exclusion(recipe):
    """(shapes, plaza, margins, decl, error) for the town the recipe avoids.

    Loaded ONCE and BEFORE any write, for two reasons: a refusal must land
    before the first file is rewritten, and every species must be filtered
    against the SAME footprint. A per-species load could pick up a plan
    edited mid-run and clear a different town for the conifers than for the
    saplings.

    Returns an error STRING rather than raising so both callers refuse
    identically -- this is the one description of where the town is, and
    two call sites deciding separately what counts as a refusal is the
    defect the shared module exists to prevent.
    """
    decl = (recipe.get("foliage") or {}).get("settlement_exclusion")
    if not decl:
        print("  settlement exclusion: NOT DECLARED for this recipe")
        return None, None, None, None, None

    rel = decl.get("from_city_plan")
    if not rel:
        return None, None, None, None, \
            "foliage.settlement_exclusion declares no from_city_plan."
    abs_path = os.path.join(REPO_ROOT, rel)
    if not os.path.isfile(abs_path):
        # FAIL CLOSED. The recipe asked for the exclusion; a missing plan
        # means the town footprint is unknown, and writing the forest
        # anyway would silently restore the instances the declaration
        # exists to remove.
        return None, None, None, None, (
            "foliage.settlement_exclusion names %s, which does not exist. "
            "Nothing was written -- re-run the city planner, or remove the "
            "declaration deliberately." % rel)
    try:
        shapes, plaza, margins = town_exclusion.load(abs_path)
    except RuntimeError as exc:
        return None, None, None, None, str(exc)

    # TWO RECIPES NAME THIS PLAN and they must agree. encounters.json
    # declares its own `from_city_plan` for the SAME committed town at
    # DIFFERENT margins; the margins are meant to differ, the PLAN is not.
    # Checked rather than trusted, so the pair cannot drift into clearing
    # one town and avoiding another (NN19).
    enc_path = os.path.join(REPO_ROOT, "recipes", "encounters.json")
    if os.path.isfile(enc_path):
        try:
            with open(enc_path, encoding="utf-8") as fh:
                enc = json.load(fh)
            enc_plan = (((enc.get("exclusions") or {}).get("settlement")
                         or {}).get("from_city_plan"))
        except Exception:
            enc_plan = None
        if enc_plan and enc_plan != rel:
            return None, None, None, None, (
                "two recipes name different town plans -- foliage says %s, "
                "encounters says %s. One town, one declaration."
                % (rel, enc_plan))

    print("  settlement exclusion: {0} rectangles + {1}, margins building "
          "{2:.1f} m / street {3:.1f} m / plaza {4:.1f} m"
          .format(len(shapes), "a plaza disc" if plaza else "NO plaza disc",
                  *margins))
    return shapes, plaza, margins, decl, None


def load_water_exclusion(recipe):
    """(water_mask, decl, error) for the Brief-4 water bodies the recipe avoids.

    Mirrors load_exclusion: loaded ONCE, BEFORE any write, so a refusal lands
    before the first file is rewritten and every species is filtered against
    the SAME footprint. Returns an error STRING rather than raising so both
    callers refuse identically.

    The mask is the DERIVED water-body union (build_water_exclusion_mask.py),
    read through plan_encounters.WaterMask -- the ONE definition of where the
    water is and the ONE lookup, shared with the encounters placer (NN24/NN19).
    place_foliage does not re-describe water geometry.

    FAIL CLOSED (like settlement): the recipe asked for the exclusion; a
    missing mask means the water footprint is unknown, and writing the forest
    anyway would silently plant trees on the drowned lakebed the declaration
    exists to clear.
    """
    decl = (recipe.get("foliage") or {}).get("water_exclusion")
    if not decl:
        print("  water exclusion: NOT DECLARED for this recipe")
        return None, None, None
    rel = decl.get("exclusion_mask")
    if not rel:
        return None, None, ("foliage.water_exclusion declares no "
                            "exclusion_mask.")
    abs_path = os.path.join(REPO_ROOT, rel)
    if not os.path.isfile(abs_path):
        return None, None, (
            "foliage.water_exclusion names %s, which does not exist. Nothing "
            "was written -- run research/brief4/scripts/"
            "build_water_exclusion_mask.py, or remove the declaration "
            "deliberately." % rel)
    # WaterMask is the single lookup; imported, not re-implemented (NN24).
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from plan_encounters import WaterMask
        wm = WaterMask(abs_path)
    except Exception as exc:                       # noqa: BLE001 -- report it
        return None, None, ("could not load the water mask %s: %s: %s"
                            % (rel, type(exc).__name__, exc))
    print("  water exclusion: %s (%d x %d cells, %d water cells)"
          % (rel, wm.nrow, wm.ncol, int(wm.mask.sum())))
    return wm, decl, None


def exclude_only(recipe, args):
    """Filter the EXISTING plans. No generator is constructed.

    ⛔ WHY THIS MODE EXISTS. Re-sampling the forest to apply an exclusion
    throws away 219,659 committed instances and re-rolls every position,
    which `recipes/city.json` argued against and which is a real cost:
    the shipped plans carry a stamp waiver recording that the foliage was
    DELIBERATELY not re-scattered. This mode gets the exclusion into the
    authored artefact without touching placement at all -- the strongest
    possible form of the no-re-roll property, since there is no RNG in
    the code path to shift.
    """
    shapes, plaza, margins, decl, err = load_exclusion(recipe)
    if err:
        print("REFUSE: {0}".format(err))
        return 3
    # Said out loud, not silently skipped (the convention this file already
    # holds for adopted rocks): this mode applies ONLY the settlement filter.
    # A declared water_exclusion is NOT applied here -- drowned trees are
    # cleared by the full --place regeneration (T9), which carries the water
    # post-filter. A reader of this summary must not assume otherwise.
    if (recipe.get("foliage") or {}).get("water_exclusion"):
        print("  NOTE: foliage.water_exclusion is declared but NOT applied in "
              "--exclude-only; the water filter runs in the --place "
              "regeneration, not here.")
    if shapes is None:
        print("REFUSE: --exclude-only needs foliage.settlement_exclusion.")
        # exit 3 like every other refusal gate in this mode (it prints
        # REFUSE; returning 1 here contradicted the exit-code table —
        # auditor FIX, Pass 3 2026-09-16).
        return 3

    biome = recipe["biome_id"]
    paths = sorted(glob.glob(os.path.join(
        FOLIAGE_DIR, "{0}_*.json".format(biome))))
    if not paths:
        print("REFUSE: no existing plans for {0}.".format(biome))
        return 3

    tree_layers = {sp["layer"] for sp in recipe["foliage"]["species"]
                   if "role" not in sp}
    # ROCK species (those with `role`) are named in the recipe, so the
    # orphan skip below never matched them — until 2026-09-16 (Pass 3)
    # their plans were silently FILTERED here while three separate claims
    # (this comment, the closing summary, main's NOTE) said rocks were
    # left alone, and their waiver was overwritten with tree narrative.
    rock_names = {sp["name"] for sp in recipe["foliage"]["species"]
                  if "role" in sp}
    all_names = {sp["name"] for sp in recipe["foliage"]["species"]}
    print("")
    print("%-34s %10s %10s %9s" % ("plan", "before", "removed", "after"))
    total_before = total_removed = 0
    written_paths = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        rows = doc.get("instances")
        if not isinstance(rows, list):
            continue
        # ROCK PLANS ARE ADOPTED, NOT PLACED HERE, and are left alone --
        # said out loud rather than silently skipped, because a summary
        # that omits what it did not touch reads as if it touched
        # everything.
        if doc.get("species") and doc["species"] in rock_names:
            print("%-34s %10s %10s %9s"
                  % (os.path.basename(path), len(rows), "-", "ROCK-SKIP"))
            continue
        if doc.get("species") and doc["species"] not in all_names:
            print("%-34s %10s %10s %9s"
                  % (os.path.basename(path), len(rows), "-", "SKIPPED"))
            continue
        before = len(rows)
        kept = [r for r in rows
                if not town_exclusion.inside(shapes, plaza, r[0], r[1])]
        removed = before - len(kept)
        total_before += before
        total_removed += removed
        doc["instances"] = kept
        doc["count"] = len(kept)
        doc["settlement_exclusion"] = {
            "from_city_plan": decl["from_city_plan"],
            "building_margin_m": margins[0],
            "street_margin_m": margins[1],
            "plaza_margin_m": margins[2],
            "removed": removed,
            "applied": "filtered in place on committed rows; no generator "
                       "was constructed, so no position moved",
        }
        doc["_city_plan"] = decl["from_city_plan"]
        # A PLAN THIS MODE WRITES WILL NOT REPRODUCE FROM A PLAIN RUN, and
        # it must say so itself. `check_plan_freshness --reproduce` re-runs
        # the producer and compares; this mode deliberately does NOT
        # re-sample, so the comparison is against something that was never
        # claimed. Recording the reason IN the artefact is the difference
        # between a known deviation and a silent one.
        prev = doc.get("_stamp_waiver") or {}
        doc["_stamp_waiver"] = {
            "inputs": sorted(set(list(prev.get("inputs") or [])
                                 + ["recipes/alpine_8k.json",
                                    "scripts/place_foliage.py",
                                    decl["from_city_plan"]])),
            "recorded": "2026-09-12",
            "granted_for": prev.get("granted_for", "foliage placement"),
            "why": (
                "EXPECTED-UNREPRODUCIBLE by design. Written by "
                "place_foliage --exclude-only, which constructs NO "
                "generator: it filters the COMMITTED rows against the town "
                "footprint and rewrites them, so every surviving instance "
                "keeps its exact transform. A plain re-run would re-sample "
                "and is separately BLOCKED -- a jittered lattice at "
                "cells=534 reads the remainder layer at 0.13153 against a "
                "whole-map mean of 0.25174, i.e. a stratified sample 48% "
                "low, and regeneration yields 152 instances against "
                "219,659. See R-TOWNEXCL and LESSONS 2026-09-12d. PRIOR "
                "WAIVER, still true and preserved: "
                + str(prev.get("why", "(none)"))),
        }
        doc[plan_stamp.STAMP_KEY] = plan_stamp.stamp(doc, REPO_ROOT)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh)
        written_paths.append(path)
        print("%-34s %10s %10s %9s"
              % (os.path.basename(path), "{0:,}".format(before),
                 "{0:,}".format(removed), "{0:,}".format(len(kept))))
    print("%-34s %10s %10s %9s"
          % ("TOTAL", "{0:,}".format(total_before),
             "{0:,}".format(total_removed),
             "{0:,}".format(total_before - total_removed)))
    print("")
    print("tree layers filtered: %s" % ", ".join(sorted(tree_layers)))
    # FLOOR GATE (F-1) IN THE REMOVAL MODE TOO (Pass 3 2026-09-16). This
    # is the one mode whose entire job is REMOVING instances, and
    # --ruled-count was parsed and silently ignored here: an oversized
    # town plan could eat most of the forest and exit 0 while the
    # operator believed the flag armed the floor. Same read-back-from-
    # disk input as main's gate; the files are already rewritten, so a
    # REFUSE means "do not hand these to --place", exactly as there.
    _read_back = 0
    for _pth in written_paths:
        with open(_pth, "r", encoding="utf-8") as _rfh:
            _read_back += len(json.load(_rfh).get("instances") or [])
    print("")
    print("--- floor gate (F-1, exclude-only) ---")
    print("  read back {0:,} instances from {1} rewritten plan file(s)"
          .format(_read_back, len(written_paths)))
    _fstatus, _fneed, _fmsg = floor_gate_verdict(
        _read_back, getattr(args, "ruled_count", None))
    print("  {0}".format(_fmsg))
    if _fstatus == "REFUSE":
        print("  The plan files WERE rewritten (filtering is in place); "
              "they are below the ruled floor and must not be handed "
              "to --place.")
        return 3
    return 0


def _layer_weight(weights, layer_names, layer, gx, gy):
    """Bilinear sample of one layer's weight, REMAINDER-AWARE.

    Layers 0..direct-1 are stored channels. When the material declares
    more layers than the weightmap has channels, the LAST layer is the
    shader remainder 1-(sum of stored channels) and has no channel of its
    own. `mask_plan` decides which case applies; it is imported from the
    material builder so the density a species is planted at comes from
    the same mapping the shader blends (NN24).

    THE REMAINDER IS SAMPLED PER CHANNEL AND SUMMED AT THE SAMPLE POINTS,
    never built as a full grid. Bilinear interpolation is LINEAR, so
    sampling-then-summing equals summing-then-sampling exactly, and the
    8129² float64 array the naive form would allocate (528 MB, on top of
    the 2.1 GB the RGBA weightmap already costs) never exists.
    """
    direct, _has_rem = mask_plan(len(layer_names))
    idx = layer_names.index(layer)
    if idx < direct:
        return _bilinear(weights[..., idx], gx, gy)
    acc = np.zeros(np.shape(gx), dtype=np.float64)
    for c in range(direct):
        acc += _bilinear(weights[..., c], gx, gy)
    # Clipped because 8-bit quantisation lets the four stored channels sum
    # a hair past 1.0, which would otherwise read as a NEGATIVE density.
    return np.clip(1.0 - acc, 0.0, 1.0)


def load_zone_multiplier(zone_map_path):
    """Return (fn, m_max, meta) reproducing zone_map.json's density rule.

    Brief 5 D2. `fn(wx_m, wy_m) -> m_array` samples the SAME 512 m cull-disc
    rule that `research/brief5/scripts/zone_map.py` published: for each of the
    three station discs, a per-station cap blended to the global target across a
    128 m band at the disc edge; m is the MINIMUM contribution, with the target
    as a ceiling. This is a CONTINUOUS port (no per-bin lookup), so it has no
    sparse-bin leak inside a disc, and it is CROSS-CHECKED against the recorded
    per-bin `m_final` before it is returned (rule 13 / rule 9: the port must
    reproduce the artefact it claims to follow, or it refuses).

    m_max (== the global target) is the factor the candidate grid is densified
    by; per-candidate acceptance is then scaled by m_final/m_max, so the placed
    density scales as m_final and nowhere exceeds the target multiplier.
    """
    zm = json.load(open(zone_map_path, encoding="utf-8"))
    P, caps = zm["params"], zm["caps"]
    target = float(P["target_m"])
    inner = float(P["inner_edge_m"])
    outer = float(P["outer_edge_m"])
    centers = {n: (float(c[0]), float(c[1]))
               for n, c in P["disc_centers_m"].items()}
    capm = {n: float(caps[n]["cap"]) for n in centers}

    def fn(wx, wy):
        wx = np.asarray(wx, dtype=np.float64)
        wy = np.asarray(wy, dtype=np.float64)
        m = np.full(wx.shape, target, dtype=np.float64)
        for name, (cx, cy) in centers.items():
            d = np.hypot(wx - cx, wy - cy)
            c = capm[name]
            t = np.clip((d - inner) / (outer - inner), 0.0, 1.0)
            m = np.minimum(m, c + (target - c) * t)   # blended, then min
        return m

    # rule 13: prove the port reproduces the recorded per-bin m_final at the bin
    # centres before trusting it. A silent disagreement here would place a forest
    # at a density the zone map never sanctioned.
    bin_m = float(P["bin_cm"]) / 100.0
    xs, ys, want = [], [], []
    for b in zm["bins"]:
        ix, iy = b["bin"]
        xs.append((ix + 0.5) * bin_m)
        ys.append((iy + 0.5) * bin_m)
        want.append(float(b["m_final"]))
    if not want:
        raise ValueError(
            "zone map {0} has no bins to cross-check against; a zero-sample "
            "comparison cannot confirm the port (rule 13 -- a count of zero "
            "refuses rather than agreeing). Refusing.".format(
                os.path.relpath(zone_map_path, REPO_ROOT)))
    err = float(np.max(np.abs(fn(np.array(xs), np.array(ys))
                              - np.array(want))))
    if err >= 1e-3:
        raise ValueError(
            "zone multiplier port disagrees with {0} by {1:g} (> 1e-3); the "
            "continuous rule does not reproduce the recorded m_final. Refusing "
            "rather than placing at an unsanctioned density."
            .format(os.path.relpath(zone_map_path, REPO_ROOT), err))
    meta = {"zone_map": os.path.relpath(zone_map_path, REPO_ROOT).replace("\\", "/"),
            "target_m": target, "caps": capm, "xcheck_max_err": err,
            "n_bins_checked": len(want)}
    return fn, target, meta


def load_density_ceiling(path):
    """Return (ceil_fn, meta) for the Brief 5 D2 post-multiplier density ceiling.

    Ryan's ASK #1 ruling: no bin may exceed D_max instances, where D_max is the
    densest the budget-capped forest_floor is allowed to be. `ceil_fn(wx, wy)`
    returns the CEILING multiplier at each world point = D_max / trees_now[bin]
    (inf where the bin currently holds no trees, so the ceiling never binds on
    ground that is empty today). It is combined with the zone multiplier by a
    per-point minimum in main(), so m_final = min(m_zone, D_max/trees_now) --
    the placer never re-implements the rule, it only takes the smaller factor.
    """
    dc = json.load(open(path, encoding="utf-8"))
    D_max = float(dc["D_max"])
    g = dc["grid"]
    ix0, iy0 = int(g["ix0"]), int(g["iy0"])
    bin_m = float(dc["bin_cm"]) / 100.0
    trees_now = np.asarray(g["trees_now"], dtype=np.float64)   # [ny, nx]
    ny, nx = trees_now.shape

    def ceil_fn(wx, wy):
        wx = np.asarray(wx, dtype=np.float64)
        wy = np.asarray(wy, dtype=np.float64)
        ix = np.floor(wx / bin_m).astype(np.int64) - ix0
        iy = np.floor(wy / bin_m).astype(np.int64) - iy0
        inside = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        tn = np.zeros(wx.shape, dtype=np.float64)
        tn[inside] = trees_now[iy[inside], ix[inside]]
        # empty bins (tn==0) -> infinite ceiling (never binds); out-of-grid
        # points are empty ground -> also unbounded.
        out = np.full(wx.shape, np.inf, dtype=np.float64)
        nz = tn > 0
        out[nz] = D_max / tn[nz]
        return out

    # rule 13 grid round-trip self-check: ceil_fn at D_max_bin's centre must
    # equal D_max / trees_now_there (= ff_cap). A transposed [iy,ix] or a wrong
    # offset fails this immediately, before a single instance is placed against
    # the wrong bins.
    _bx, _by = dc["D_max_bin"]
    _got = float(ceil_fn(np.array([(_bx + 0.5) * bin_m]),
                         np.array([(_by + 0.5) * bin_m]))[0])
    _want = D_max / float(dc["D_max_trees_now"])
    if not (np.isfinite(_got) and abs(_got - _want) < 1e-9 * max(1.0, _want)):
        raise ValueError(
            "density-ceiling grid readback failed at D_max_bin {0!r}: got {1!r}, "
            "want {2!r} -- offset/axis-order mismatch; refusing.".format(
                dc["D_max_bin"], _got, _want))

    meta = {"density_ceiling": os.path.relpath(path, REPO_ROOT).replace("\\", "/"),
            "D_max": D_max, "D_max_bin": dc.get("D_max_bin"),
            "ff_cap": dc.get("ff_cap"),
            "projected_total_ceiled": dc.get("projected", {}).get("total_ceiled")}
    return ceil_fn, meta


def plan(recipe, height_m, weights, flow, origin_m, spacing_m, seed,
         zone_fn=None, zone_m_max=1.0):
    """Instance transforms per species, plus the numbers to judge them.

    When `zone_fn` is given (Brief 5 D2 density upgrade), each tree species'
    candidate grid is densified by `zone_m_max` and each candidate's acceptance
    probability is scaled by `zone_fn(world_x, world_y) / zone_m_max`, so the
    placed density scales as the zone multiplier m_final at that location. Grass
    and rock species are unaffected (they return early below).
    """
    fol = recipe["foliage"]
    layer_names = [l["name"] for l in recipe["material"]["layers"]]
    n = height_m.shape[0]
    span_m = (n - 1) * spacing_m
    hectares = (span_m / 100.0) ** 2

    # Surface normal from the height field, once, shared by every
    # species. np.gradient returns d/drow, d/dcol -> dy, dx.
    gy, gx = np.gradient(height_m, spacing_m)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))

    out = []
    for i, sp in enumerate(fol["species"]):
        # schema v1.7: grass-system species are NOT placed. Their
        # density lives in the landscape material's grass output and the
        # engine spawns them per-frame near the camera; there are no
        # persistent transforms to compute, no weight_share, and no
        # instance budget to charge them against. Iterating them here
        # raised KeyError on weight_share, which was the right failure —
        # the wrong one would have been placing them twice.
        if sp.get("system") == "grass":
            continue
        # schema v1.20: a species that declares `role` is a ROCK, planned
        # by `rock_scatter.py` against a deposition field this module
        # does not compute. It has no `layer` and no `weight_share`, so
        # the next two lines would raise KeyError -- which would be the
        # RIGHT failure; the wrong one is planning it as vegetation off
        # the tree budget.
        #
        # Skipping it here is only half the job. Its plan file must be
        # ADOPTED into the placement list further down, because the
        # orphan sweep deletes every FT_* the run is not handed. A rock
        # skipped here and not adopted there would be deleted by the
        # next vegetation run, silently. See `adopt_rock_plans`.
        if "role" in sp:
            continue
        rng = np.random.default_rng(seed + 7919 * (i + 1))
        if sp["layer"] not in layer_names:
            raise ValueError(
                "species {0!r} is keyed to layer {1!r}, which the material "
                "does not declare. Declared: {2}"
                .format(sp["name"], sp["layer"], ", ".join(layer_names)))
        target = float(fol["density_per_hectare"]) * float(sp["weight_share"])
        # Brief 5 D2 density upgrade: densify the candidate grid by the global
        # maximum multiplier so there are enough candidates to reach the target
        # density everywhere; the per-candidate acceptance below thins each
        # location back to its own m_final/m_max. Net placed density scales as
        # m_final. Applied ONLY to the candidate grid here; the base target is
        # kept in `target_per_ha` for the accept-rate report.
        base_target = target
        if zone_fn is not None:
            target = target * float(zone_m_max)
        if target <= 0.0:
            _r0 = {"species": sp, "xyz": np.zeros((0, 3)),
                   "yaw": np.zeros(0), "pitch": np.zeros(0),
                   "roll": np.zeros(0), "scale": np.zeros(0),
                   "candidates": 0, "target_per_ha": base_target}
            # grid_target_per_ha only when the zone upgrade is active, so a
            # plain m=1 run reproduces the pre-D2 plan byte-for-byte (freshness).
            if zone_fn is not None:
                _r0["grid_target_per_ha"] = target
            out.append(_r0)
            continue

        # Jittered grid at the target density: one candidate per cell.
        cell_m = math.sqrt(10000.0 / target)
        cells = max(int(math.floor(span_m / cell_m)), 1)
        cx, cy = np.meshgrid(np.arange(cells), np.arange(cells))
        jx = (cx.ravel() + rng.random(cells * cells)) * (span_m / cells)
        jy = (cy.ravel() + rng.random(cells * cells)) * (span_m / cells)

        gxi, gyi = jx / spacing_m, jy / spacing_m
        w = _layer_weight(weights, layer_names, sp["layer"], gxi, gyi)
        h = _bilinear(height_m, gxi, gyi)
        s = _bilinear(slope_deg, gxi, gyi)

        s_lo, s_hi = [float(v) for v in sp["slope_deg"]]
        h_lo, h_hi = [float(v) for v in sp["height_m"]]
        mask = ((s >= s_lo) & (s <= s_hi) & (h >= h_lo) & (h <= h_hi))

        p = w * mask
        # CLOSURE GRADIENT (schema v1.23). The height band above is a HARD
        # window: inside it every elevation is equally likely, which plants
        # a stand of uniform density right up to its top edge and then
        # stops dead. WORLD_VISION's complaint about the old forest was
        # UNIFORMITY as much as sparseness, and a real subalpine stand
        # thins toward treeline and ends in open krummholz.
        #
        # This SCALES rather than redistributing — see the contrast argued
        # at placement_priors.closure_ramp. Consequence the caller must
        # own: applying it LOWERS the placed count for a given
        # density_per_hectare, so the density is re-derived against the
        # ramp rather than carried over from the uniform plan.
        clo = sp.get("closure")
        if isinstance(clo, dict):
            p = p * placement_priors.closure_ramp(
                h, h_lo, h_hi, clo["at_low"], clo["at_high"])
        bias = float(sp.get("flow_bias", 0.0) or 0.0)
        if bias != 0.0 and flow is not None:
            f = _bilinear(flow, gxi, gyi)
            # Centred so the bias redistributes rather than scaling the
            # total: mean density stays put, wet ground gains what dry
            # ground loses. ONE definition, shared with the rock path
            # (placement_priors.centred_bias); the reference is the WHOLE
            # FIELD's mean, i.e. "the average wetness of the map".
            p = p * placement_priors.centred_bias(f, bias, flow.mean())

        # Brief 5 D2: scale acceptance by the local zone multiplier / m_max.
        # jx, jy are candidate positions in LOCAL metres; world metres add the
        # origin (matching the xyz world conversion below). m_final/m_max is in
        # [cap/target, 1], so this only ever THINS the densified grid — never
        # raises p above the mask/closure/bias product it multiplies.
        if zone_fn is not None:
            mf = zone_fn(jx + origin_m[0], jy + origin_m[1])
            p = p * (mf / float(zone_m_max))

        keep = rng.random(p.size) < np.clip(p, 0.0, 1.0)
        kx, ky = jx[keep], jy[keep]
        gxk, gyk = kx / spacing_m, ky / spacing_m
        kz = _bilinear(height_m, gxk, gyk)

        # Orientation: random yaw always; tilt toward the surface normal
        # by align_to_normal. A stand of trees all leaning identically is
        # the giveaway that nothing sampled the ground.
        align = float(sp.get("align_to_normal", 0.0) or 0.0)
        ndx = _bilinear(gx, gxk, gyk)
        ndy = _bilinear(gy, gxk, gyk)
        # CENTIMETRES. Unreal works in cm and these transforms are
        # handed straight to the editor, so the conversion happens here,
        # once, rather than being left for a caller to remember. The
        # first version stored metres under a header that said "cm": the
        # editor would have placed every instance a hundred times too
        # close to the origin, and the offline verifier — which divided
        # by 100 as the header told it to — sampled the map CENTRE for
        # every instance and duly reported that flow_bias did nothing.
        # A units mismatch that makes the CHECK agree with the bug is
        # the expensive kind (section 6.2).
        # SINK DEPTH (schema v1.21). Lowers the instance so the root
        # flare intersects the ground instead of resting on it.
        #
        # A flare that merely TOUCHES the surface leaves a hard
        # silhouette edge -- the flat dark ellipse visible at every
        # trunk base in `_verify/`. Real trees interpenetrate: soil and
        # ground cover rise over the flare, and the edge is broken by
        # geometry rather than by a texture. A few centimetres is
        # enough; this is not the rock `embed_frac`, which buries a
        # fraction of the whole mesh.
        #
        # Applied along WORLD -Z, not along the surface normal, because
        # trees stand world-up (R4: align_to_normal 0.15, max 4 degrees
        # of tilt). Sinking along the normal would displace a trunk
        # horizontally on a slope for no benefit at that tilt.
        #
        # NOTE FOR PASS 2 DISPLACEMENT: once the landscape material
        # carries height-blended displacement, the visible surface is
        # no longer the vertex surface, and this depth must be measured
        # against the DISPLACED one or it will under-sink on any
        # surface that displaces upward.
        sink_m = float(sp.get("sink_depth_m", 0.0) or 0.0)
        _r = {
            "species": sp,
            "xyz": np.stack([(kx + origin_m[0]) * 100.0,
                             (ky + origin_m[1]) * 100.0,
                             (kz - sink_m) * 100.0], axis=1),
            "yaw": rng.random(kx.size) * 360.0,
            "pitch": np.degrees(np.arctan(ndx)) * align,
            "roll": -np.degrees(np.arctan(ndy)) * align,
            "scale": (rng.random(kx.size)
                      * (float(sp["scale_range"][1])
                         - float(sp["scale_range"][0]))
                      + float(sp["scale_range"][0])),
            "candidates": int(p.size),
            "target_per_ha": base_target,
        }
        # grid_target_per_ha only when the zone upgrade is active (freshness:
        # a plain m=1 run must reproduce the pre-D2 plan byte-for-byte).
        if zone_fn is not None:
            _r["grid_target_per_ha"] = target
        out.append(_r)
    return out, hectares


def adopt_committed_plans(recipe):
    """([(name, path, count)], [errors]) for every INSTANCE species.

    The same contract adopt_rock_plans applies to rocks, applied to every
    species the editor payload would otherwise sweep: an instance species
    (no `system: grass` -- grass goes down the landscape GrassOutput path
    and has no FT_ asset) MUST have a committed, non-empty plan whose
    `species` and `mesh` match the recipe, or the run is refused. A
    missing tree plan is not "no trees this time": handed to --place, the
    orphan sweep would remove_all_instances on FT_<name> and report
    success.
    """
    out, errs = [], []
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if not isinstance(sp, dict) or "role" in sp:
            continue
        if sp.get("system") == "grass":
            continue
        path = os.path.join(FOLIAGE_DIR, "{0}_{1}.json".format(
            recipe["biome_id"], sp["name"]))
        if not _inside_repo(path):
            errs.append("{0} escapes REPO_ROOT".format(path))
            continue
        if not os.path.isfile(path):
            errs.append(
                "{0!r} is an instance species but {1} does not exist. "
                "--place-committed would sweep FT_{0} from the world."
                .format(sp["name"], os.path.relpath(path, REPO_ROOT)))
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError) as exc:
            errs.append("{0} is unreadable: {1}".format(
                os.path.relpath(path, REPO_ROOT), exc))
            continue
        rows = doc.get("instances")
        if not isinstance(rows, list) or not rows:
            errs.append("{0} contains no instances; refused (an empty plan "
                        "is indistinguishable from a deliberate removal at "
                        "the sweep).".format(os.path.relpath(path, REPO_ROOT)))
            continue
        if doc.get("mesh") != sp.get("mesh"):
            errs.append(
                "{0} was planned for mesh {1!r} but the recipe names {2!r}; "
                "the plan is stale.".format(os.path.relpath(path, REPO_ROOT),
                                            doc.get("mesh"), sp.get("mesh")))
            continue
        if doc.get("species") != sp["name"]:
            errs.append("{0} is a plan for species {1!r}, not {2!r}.".format(
                os.path.relpath(path, REPO_ROOT), doc.get("species"),
                sp["name"]))
            continue
        out.append((sp["name"], path, len(rows)))
    return out, errs


def place_committed(recipe, args):
    """Phase 2 only, from committed plans: trees AND rocks in ONE run."""
    print("--- committed plans (no generator constructed) ---")
    trees, terr = adopt_committed_plans(recipe)
    rocks, rerr = adopt_rock_plans(recipe)
    for line in terr + rerr:
        print("REFUSE: {0}".format(line))
    if terr or rerr:
        print("Nothing was placed.")
        return 3
    written = list(trees) + list(rocks)
    if not written:
        print("REFUSE: no committed plans for {0}.".format(recipe["biome_id"]))
        return 3
    for name, path, n in written:
        print("  {0:<14} {1:>9,} instances  {2}".format(
            name, n, os.path.relpath(path, REPO_ROOT)))
    print("  {0:<14} {1:>9,} instances across {2} species".format(
        "TOTAL", sum(n for _a, _b, n in written), len(written)))
    total = sum(n for _a, _b, n in written)
    if total > args.max_instances:
        print("REFUSE: {0:,} committed instances exceed the ceiling {1:,}."
              .format(total, args.max_instances))
        return 3
    print("")
    if not args.place:
        print("=" * 70)
        print("PLAN ONLY -- nothing was spawned. Re-run with --place "
              "--place-committed to hand these files to the editor.")
        print("=" * 70)
        return 0
    return _place(recipe, written, args)


def adopt_rock_plans(recipe):
    """([(name, path, count)], [errors]) for every ROCK species.

    WHY ADOPTION EXISTS AT ALL. Rocks are planned by `rock_scatter.py`
    against a talus deposition field this module does not compute, so
    `plan()` skips them. But the editor payload's ORPHAN SWEEP
    (place_foliage.py, PLACE_SOURCE) calls `remove_all_instances` on
    every `FT_*` asset whose name is NOT in the plan list handed to THAT
    run. So a rock that is skipped here and not adopted would be created
    by one run and deleted by the next, silently, with both runs
    reporting success.

    That is why this REFUSES rather than warning. The three ways it can
    go wrong all end with instances being destroyed:

      * plan file missing   -> the rock is swept on the next run
      * plan file empty     -> ditto, and the sweep reads as intentional
      * mesh disagrees      -> the plan places a DIFFERENT asset than the
                               recipe names, and the name-keyed sweep
                               cannot tell

    A missing plan is NOT "no rocks this time". It is an unfinished
    pipeline, and the correct response is to run `rock_scatter.py
    --write` (RECIPES R12 step 4), not to proceed.
    """
    out, errs = [], []
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if not isinstance(sp, dict) or "role" not in sp:
            continue
        path = os.path.join(FOLIAGE_DIR, "{0}_{1}.json".format(
            recipe["biome_id"], sp["name"]))
        if not _inside_repo(path):
            errs.append("{0} escapes REPO_ROOT".format(path))
            continue
        if not os.path.isfile(path):
            errs.append(
                "{0!r} is a ROCK species but {1} does not exist. Run "
                "`python scripts/rock_scatter.py --write` first (RECIPES "
                "R12 step 4). Proceeding without it would place no rocks "
                "AND let the orphan sweep delete any that are already in "
                "the world.".format(sp["name"],
                                    os.path.relpath(path, REPO_ROOT)))
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError) as exc:
            errs.append("{0} is unreadable: {1}".format(
                os.path.relpath(path, REPO_ROOT), exc))
            continue
        rows = doc.get("instances")
        if not isinstance(rows, list) or not rows:
            errs.append(
                "{0} contains no instances. An empty plan is "
                "indistinguishable from a deliberate removal at the "
                "sweep, so it is refused here instead."
                .format(os.path.relpath(path, REPO_ROOT)))
            continue
        if doc.get("mesh") != sp.get("mesh"):
            errs.append(
                "{0} was planned for mesh {1!r} but the recipe now names "
                "{2!r}. The plan is stale; re-run rock_scatter.py --write."
                .format(os.path.relpath(path, REPO_ROOT), doc.get("mesh"),
                        sp.get("mesh")))
            continue
        if doc.get("species") != sp["name"]:
            errs.append(
                "{0} is a plan for species {1!r}, not {2!r}. The foliage "
                "type is keyed by NAME, so placing this would create "
                "FT_{2} from another species' transforms."
                .format(os.path.relpath(path, REPO_ROOT), doc.get("species"),
                        sp["name"]))
            continue
        out.append((sp["name"], path, len(rows)))
    return out, errs


def main(argv=None):
    # allow_abbrev=False: check_plan_freshness --reproduce probes producers with
    # `--out <tmp>`. Before the D2 --out-dir flag existed, argparse rejected that
    # with "unrecognized arguments: --out", which the checker maps to a benign
    # CANNOT REPRODUCE for this MULTI-FILE scatter tool (it cannot be diffed
    # through a single-file --out). With abbreviation ON, `--out` prefix-matches
    # `--out-dir`, the probe runs with an out-of-repo temp, the REPO_ROOT guard
    # refuses it, and the checker reads a real PRODUCER-REFUSES failure. Turning
    # abbreviation off restores the benign path (Brief-4 T10 behaviour) and does
    # not affect any caller (all pass full flag names).
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                allow_abbrev=False)
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--heightmap", default=None)
    p.add_argument("--place", action="store_true",
                   help="After planning, build the instances in the live "
                        "editor. Without this the run is LOCAL ONLY and "
                        "writes nothing but the plan files.")
    p.add_argument("--batch", type=int, default=8000,
                   help="Instances per add_instances call. Batched so a "
                        "single call never carries the whole set.")
    p.add_argument("--timeout", type=float, default=6.0,
                   help="seconds to wait for an editor to answer node "
                        "discovery. This script was the only one of the "
                        "twenty that touch the editor without the flag, "
                        "and a busy editor streaming World Partition "
                        "cells can take longer than the 6 s default to "
                        "answer -- which reads as 'no editor is running'.")
    p.add_argument("--max-instances", type=int, default=MAX_INSTANCES,
                   help="Ceiling for the whole recipe. Exceeding it "
                        "REFUSES; it never truncates.")
    p.add_argument("--ruled-count", type=int, default=None,
                   help="The intended/RULED total foliage instance count for "
                        "this recipe. When given, the run REFUSES if the "
                        "placed total falls below 0.80x it (the -20 percent "
                        "floor, AUDIT F-1). Symmetric to --max-instances: the "
                        "ceiling catches a plan too large, this catches one "
                        "quietly half the intended size. When omitted the "
                        "floor gate DEGRADES with a named gap (NN6) -- it "
                        "cannot bind and says so, rather than passing a "
                        "half-size plan silently.")
    p.add_argument("--density-zone-map", default=None,
                   help="Brief 5 D2. Path to a zone_map.json. When given (or "
                        "when recipe.foliage.density_zone_map is set), tree "
                        "density is scaled spatially by the map's per-location "
                        "multiplier m_final (grass and rocks unaffected). The "
                        "CLI value OVERRIDES the recipe field. The candidate "
                        "grid is densified by the map's global target and each "
                        "candidate thinned by m_final/target, so placed density "
                        "scales as m_final and never exceeds the target factor.")
    p.add_argument("--density-ceiling", default=None,
                   help="Brief 5 D2 round 2. Path to a density_ceiling.json. "
                        "Applies a post-multiplier per-bin density ceiling on "
                        "top of the zone map: m_final = min(m_zone, "
                        "D_max/trees_now[bin]). Requires --density-zone-map. No "
                        "bin exceeds D_max instances (the budget-capped "
                        "forest_floor density).")
    p.add_argument("--out-dir", default=None,
                   help="Directory to write plan JSONs into (must be inside the "
                        "repo). Defaults to foliage/. Use a scratch dir for a "
                        "DRY RUN so nothing under foliage/ is touched; the plans "
                        "are still real and canopy_cover.py can read them.")
    p.add_argument("--selftest", action="store_true",
                   help="Run the offline three-directions tests of the two "
                        "REFUSAL gates (floor F-1, slot-count F-3) and exit. "
                        "No editor, no recipe, no disk.")
    p.add_argument("--place-committed", action="store_true",
                   help="Phase 2 ONLY: hand the COMMITTED foliage/<biome>_*.json "
                        "plans (every instance species + every adopted rock "
                        "plan) to the editor without re-planning anything. "
                        "The generator is never constructed, so no tree can "
                        "move (R-FOLIAGE-FEEDBACK blocks regeneration; "
                        "R-TOWNEXCL's no-re-roll). Refuses if any instance "
                        "species has no plan, because the orphan sweep would "
                        "then delete it from the world.")
    p.add_argument("--exclude-only", action="store_true",
                   help="Apply foliage.settlement_exclusion to the EXISTING "
                        "plans and rewrite them. Does NOT re-sample: no "
                        "generator is constructed, so every surviving "
                        "instance keeps its exact transform. Use when the "
                        "town has moved but the forest must not.")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    if args.selftest:
        return _selftest()

    recipe_path = os.path.abspath(args.recipe)
    if not _inside_repo(recipe_path):
        print("REFUSE: recipe must be inside {0}".format(REPO_ROOT))
        return 1
    try:
        with open(recipe_path, "r", encoding="utf-8") as fh:
            recipe = json.load(fh)
    except (OSError, ValueError) as exc:
        print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
        return 2

    if not isinstance(recipe.get("foliage"), dict):
        print("REFUSE: this recipe declares no `foliage` block. Schema "
              "v1.6, recipes/schema.md.")
        return 2

    # The validator owns the block's shape; run it rather than
    # re-checking here, so the two cannot drift (lesson 1.9).
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import import_heightmap as ih
    errs = ih._validate_foliage(recipe.get("foliage"), recipe)
    if errs:
        print("REFUSE: foliage block invalid:")
        for e in errs:
            print("  - {0}".format(e))
        return 2

    # --exclude-only short-circuits BEFORE the heightmap and weightmap are
    # loaded. It needs neither: it reads committed plans and the town, and
    # touching placement inputs it does not use would only create ways to
    # fail.
    if args.exclude_only:
        return exclude_only(recipe, args)

    # --place-committed short-circuits for the same reason: it reads the
    # committed plans and the recipe, constructs NO generator, and hands
    # the files to the editor. Added 2026-09-27 for the rocks world run:
    # `--place` runs Phase 1 first, and Phase 1 on this recipe is BLOCKED
    # (R-FOLIAGE-FEEDBACK: the generator samples the layer its own output
    # seeded, 219,659 -> 152). The rocks must be placed WITH the trees in
    # one run (orphan sweep), so the trees are re-handed from their
    # committed rows, which the payload rebuilds byte-for-byte.
    if args.place_committed:
        return place_committed(recipe, args)

    try:
        height_m, weights, flow, origin_m, spacing_m, flow_status = \
            load_inputs(recipe, args.heightmap)
    except (OSError, ValueError, KeyError) as exc:
        print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
        return 2

    fol = recipe["foliage"]
    seed = int(fol.get("seed", 20260731))
    n = height_m.shape[0]
    span_m = (n - 1) * spacing_m
    hectares = (span_m / 100.0) ** 2

    # ---- Brief 5 D2 density-zone map (optional) -------------------------
    # The CLI value overrides the recipe field so the same feature drives both
    # the dry run (flag) and the live regen (recipe.foliage.density_zone_map).
    zone_fn = None
    zone_m_max = 1.0
    zone_meta = None
    _zm_path = args.density_zone_map or fol.get("density_zone_map")
    _dc_src = args.density_ceiling or fol.get("density_ceiling")
    if _dc_src and not _zm_path:
        print("REFUSE: a density ceiling requires a density zone map (the "
              "ceiling is combined with the zone multiplier by a minimum; "
              "without a zone map there is nothing to cap).")
        return 2
    if _zm_path:
        _zm_abs = _zm_path if os.path.isabs(_zm_path) else os.path.join(
            REPO_ROOT, _zm_path)
        if not os.path.isfile(_zm_abs):
            print("REFUSE: density zone map not found: {0}".format(_zm_abs))
            return 2
        try:
            zone_fn, zone_m_max, zone_meta = load_zone_multiplier(_zm_abs)
        except (OSError, ValueError, KeyError) as exc:
            print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
            return 2
        print("density zone map: {0}  target(m_max)={1:.4f}  "
              "port xcheck max err {2:.2e} over {3} bins"
              .format(zone_meta["zone_map"], zone_m_max,
                      zone_meta["xcheck_max_err"], zone_meta["n_bins_checked"]))
        # Brief 5 D2 round 2: the post-multiplier density ceiling. Combined with
        # the zone multiplier by a per-point minimum, so plan() still receives a
        # single zone_fn and its audited core is untouched.
        # The ceiling honours the recipe field exactly as the zone map does
        # (pipeline rule 2): --density-ceiling OVERRIDES recipe.foliage.
        # density_ceiling; either one applies the ceiling. A declared-but-unread
        # ceiling would be prose (rule 12), so there is no note-only path.
        if _dc_src:
            _dc_path = (_dc_src if os.path.isabs(_dc_src)
                        else os.path.join(REPO_ROOT, _dc_src))
            if not os.path.isfile(_dc_path):
                print("REFUSE: density ceiling not found: {0}".format(_dc_path))
                return 2
            try:
                _ceil_fn, _ceil_meta = load_density_ceiling(_dc_path)
            except (OSError, ValueError, KeyError) as exc:
                print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
                return 2
            _zone_only = zone_fn
            zone_fn = (lambda wx, wy, _z=_zone_only, _c=_ceil_fn:
                       np.minimum(_z(wx, wy), _c(wx, wy)))
            zone_meta = dict(zone_meta, ceiling=_ceil_meta)
            print("density ceiling: {0}  D_max={1:.1f}/bin (bin {2})  "
                  "proj ceiled total {3:,.0f}".format(
                      _ceil_meta["density_ceiling"], _ceil_meta["D_max"],
                      _ceil_meta["D_max_bin"],
                      _ceil_meta.get("projected_total_ceiled") or 0))
        print("")

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("map       : {0} x {0} cells, {1:.0f} m span = {2:.0f} hectares"
          .format(n, span_m, hectares))
    print("flow map  : {0}".format({
        placement_priors.FLOW_LOADED:
            "LOADED (normalised log-accumulation, not raw flow)",
        placement_priors.FLOW_ABSENT:
            "ABSENT — flow_bias will have no effect; re-run "
            "make_alpine_terrain without --no-aux",
        placement_priors.FLOW_SHAPE_MISMATCH:
            "SHAPE_MISMATCH — the map on disk is not {0}x{0} and was NOT "
            "used. This is a stale aux map, not a missing one; re-run "
            "derive_aux_maps against the adopted heightmap".format(n),
    }[flow_status]))
    print("")

    # ---- THE DENSITY GATE, before any work ------------------------
    # With a zone map the candidate grid is densified by m_max, so the honest
    # pre-mask gross is the recipe density * area * m_max -- fold it in here or
    # the gate under-counts the plan it is meant to catch (rule 12).
    _grid_dph = float(fol["density_per_hectare"]) * float(zone_m_max)
    gross = _grid_dph * hectares
    print("--- density gate ---")
    if zone_fn is not None:
        print("  zone map active: grid densified by m_max={0:.4f} "
              "(recipe {1:.0f}/ha -> grid {2:.0f}/ha)".format(
                  zone_m_max, fol["density_per_hectare"], _grid_dph))
    print("  {0:.0f}/ha over {1:.0f} ha = {2:,.0f} instances before "
          "masking".format(_grid_dph, hectares, gross))
    if gross > args.max_instances * 40:
        # Masking typically keeps well under a tenth; 40x is the point
        # past which no plausible mask saves it, so refuse before
        # spending minutes computing a plan that cannot be used.
        fits = args.max_instances * 40 / max(hectares, 1e-9)
        print("")
        print("REFUSE: that is {0:.0f}x the ceiling of {1:,} even before "
              "masking.".format(gross / args.max_instances,
                                args.max_instances))
        print("  Nothing was computed and nothing was written. This does "
              "NOT truncate: a foliage pass that quietly placed a tenth "
              "of what was asked would read as 'density does nothing'.")
        print("  density_per_hectare of about {0:.0f} would fit this map."
              .format(fits))
        return 3
    print("  ceiling {0:,} for the whole recipe".format(args.max_instances))
    print("")

    plans, _ = plan(recipe, height_m, weights, flow, origin_m, spacing_m,
                    seed, zone_fn=zone_fn, zone_m_max=zone_m_max)
    total = sum(len(p["xyz"]) for p in plans)

    print("--- planned instances ---")
    print("  {0:<14} {1:>10} {2:>10} {3:>9} {4:>9}".format(
        "species", "candidates", "placed", "accept", "per ha"))
    for pl in plans:
        sp = pl["species"]
        placed = len(pl["xyz"])
        acc = placed / max(pl["candidates"], 1)
        print("  {0:<14} {1:>10,} {2:>10,} {3:>8.1%} {4:>9.1f}".format(
            sp["name"], pl["candidates"], placed, acc,
            placed / max(hectares, 1e-9)))
    print("  {0:<14} {1:>21,}".format("TOTAL", total))
    print("")

    if total > args.max_instances:
        print("REFUSE: {0:,} instances exceeds the ceiling of {1:,}."
              .format(total, args.max_instances))
        print("  Nothing was written. Lower density_per_hectare or a "
              "weight_share; do not raise the ceiling to silence this "
              "without a capture showing the editor still runs.")
        return 3

    _excl_shapes, _excl_plaza, _excl_margins, _excl_decl, _err = \
        load_exclusion(recipe)
    if _err:
        print("REFUSE: {0}".format(_err))
        return 3

    _water_mask, _water_decl, _werr = load_water_exclusion(recipe)
    if _werr:
        print("REFUSE: {0}".format(_werr))
        return 3

    # ---- output directory (Brief 5 D2 dry run) --------------------------
    # Defaults to foliage/. A scratch dir keeps a DRY RUN off the shipped plans.
    # Must stay inside the repo (the placement payload and every checker resolve
    # repo-relative paths). --place is a LIVE build against foliage/, so refuse
    # it with a redirected out-dir: the editor sweep reads foliage/, not scratch.
    out_dir = os.path.abspath(args.out_dir) if args.out_dir else FOLIAGE_DIR
    # win32 paths compare by identity, not spelling: a case/8.3/junction variant
    # of foliage/ is the SAME dir. Use _norm (normcase+realpath), or a variant
    # spelling would overwrite the shipped plans while the log says "untouched".
    _is_foliage = _norm(out_dir) == _norm(FOLIAGE_DIR)
    _ue_subtree = _norm(os.path.join(REPO_ROOT, "LandscapeLab")) + os.sep
    if not (_is_foliage or _inside_repo(os.path.join(out_dir, "x"))):
        print("REFUSE: --out-dir {0} escapes REPO_ROOT".format(out_dir))
        return 1
    if not _is_foliage and _norm(os.path.join(out_dir, "x")).startswith(_ue_subtree):
        print("REFUSE: --out-dir {0} is inside the live UE project (LandscapeLab); "
              "a dry run writes to a scratch dir, not the project tree.".format(out_dir))
        return 1
    if args.place and not _is_foliage:
        print("REFUSE: --place builds from foliage/ in the editor; it cannot "
              "be combined with a redirected --out-dir. Drop one.")
        return 1
    if not _is_foliage:
        print("DRY RUN: writing plans to {0} (foliage/ untouched)"
              .format(os.path.relpath(out_dir, REPO_ROOT)))
    os.makedirs(out_dir, exist_ok=True)
    written = []
    _excl_removed = {}
    _water_removed = {}
    # (defined above main so the orphan-sweep contract is readable next
    #  to the sweep it protects — see adopt_rock_plans)
    # E1: one read of the perception block and the measured heights for the
    # whole write pass, so every species is derived against the same inputs.
    _perception = recipe.get("perception")
    _heights = _species_heights()
    if _perception:
        print("  perception: cull at the %s threshold (%s px), camera %s deg "
              "%sx%s" % (_perception.get("cull_threshold"),
                         _perception["thresholds_px"].get(
                             _perception.get("cull_threshold", "detail")),
                         _perception["declared_camera"]["fov_h_deg"],
                         _perception["declared_camera"]["res"][0],
                         _perception["declared_camera"]["res"][1]))

    for pl in plans:
        sp = pl["species"]
        path = os.path.join(out_dir, "{0}_{1}.json".format(
            recipe["biome_id"], sp["name"]))
        if not _inside_repo(path):
            print("REFUSE: {0} escapes REPO_ROOT".format(path))
            return 1
        rows = [[round(float(x), 1), round(float(y), 1), round(float(z), 1),
                 round(float(yw), 1), round(float(pt), 2),
                 round(float(rl), 2), round(float(sc), 3)]
                for (x, y, z), yw, pt, rl, sc in zip(
                    pl["xyz"], pl["yaw"], pl["pitch"], pl["roll"],
                    pl["scale"])]
        # ---- settlement exclusion: a POST-FILTER, never a re-roll --------
        #
        # ⛔ THIS MUST STAY BELOW THE ROW BUILD. `plan()` draws yaw, pitch,
        # roll and scale from the SAME generator that placed the points, in
        # one vectorised call each, sized by how many points survived the
        # keep-mask. Filtering any earlier changes those sizes and shifts
        # every subsequent draw -- which is exactly the "RE-ROLL all 219,659
        # positions and move the entire forest" hazard city.json raised
        # against putting the exclusion here at all. Filtering HERE, on the
        # finished rows, cannot: the transforms are already drawn and a
        # dropped row takes only itself.
        if _excl_shapes is not None:
            _before = len(rows)
            rows = [r for r in rows
                    if not town_exclusion.inside(_excl_shapes, _excl_plaza,
                                                 r[0], r[1])]
            _excl_removed[sp["name"]] = _before - len(rows)
        # ---- water exclusion: a POST-FILTER too, for the SAME reason -------
        #
        # ⛔ BELOW THE ROW BUILD, like settlement. The Brief-4 lakes are
        # FILL-TO-LEVEL: the heightmap under a lake is unchanged terrain, so
        # the placement field ranks the drowned lakebed as ordinary plantable
        # ground and would stand trees on it. This drops every row whose
        # world-cm position falls inside the derived water-body union
        # (WaterMask.inside; the SAME mask + lookup the encounters placer uses,
        # NN24). A post-filter on finished rows keeps the RNG untouched: every
        # surviving instance keeps its exact transform, so this cannot re-roll
        # the forest (the property city.json's argument turns on).
        if _water_mask is not None:
            _before_w = len(rows)
            rows = [r for r in rows if not _water_mask.inside(r[0], r[1])]
            _water_removed[sp["name"]] = _before_w - len(rows)
        # PROVENANCE, so the plan can be checked without re-running this.
        #
        # Until 2026-08-27 these plans declared no inputs at all, so
        # check_plan_freshness reported all 15 of them UNSTAMPED -- CANNOT
        # CHECK, which is not the same as fresh. A plan whose staleness cannot
        # be read off the file is answerable only by re-deriving it, and that
        # is non-negotiable 20's live pointer.
        #
        # The keys are the ones plan_stamp.INPUT_KEYS recognises; the stamp
        # itself is added below from the SAME declaration, so the two cannot
        # drift. Paths are repo-relative, matching every other plan.
        _prov = {
            "_produced_by": "scripts/place_foliage.py",
            "_recipe": os.path.relpath(
                os.path.abspath(args.recipe), REPO_ROOT).replace("\\", "/"),
            "_terrain_source": recipe["heightmap"]["source"],
        }
        # The town plan is an INPUT once the exclusion is on: move a
        # building and this plan is stale. plan_stamp hashes it from here,
        # so staleness becomes a fact on disk rather than something only a
        # re-run could discover (NN20).
        if _excl_shapes is not None:
            _prov["_city_plan"] = _excl_decl["from_city_plan"]
        # Brief-4 T9: the PLANTING FIELD placement samples and the WATER mask
        # it filters against are both real inputs -- regenerate either and this
        # plan is stale. plan_stamp.INPUT_KEYS hashes them from here (absent
        # keys skipped), so staleness is a fact on disk, not a re-run away
        # (NN20; the _city_plan precedent above).
        _pf_stamp = (recipe.get("foliage") or {}).get("planting_field")
        if _pf_stamp:
            _prov["_planting_field"] = _pf_stamp
        if _water_mask is not None:
            _prov["_water_mask"] = _water_decl["exclusion_mask"]
        _cull_deriv = _cull_cm_for(
            sp, _perception, _heights,
            int((recipe.get("streaming") or {}).get(
                "main_loading_range_cm") or 0))
        if _perception:
            _d = _cull_deriv[1]
            print("    %-14s cull %8.1f m  (%s%s)"
                  % (sp["name"], _cull_deriv[0] / 100.0, _d["applied"],
                     "" if str(_d["applied"]).startswith("derived")
                     else " — " + str(_d.get("reason", ""))[:60]))
        _doc = dict(_prov)
        # Brief 5 D2. When the zone upgrade is active, DECLARE it so a reader can
        # tell a plan built under the density upgrade from one built at m=1. The
        # key is OMITTED entirely at m=1 so a plain run reproduces the pre-D2 plan
        # byte-for-byte (check_plan_freshness --reproduce).
        if zone_meta is not None:
            _doc["density_zone"] = {
                "zone_map": zone_meta["zone_map"],
                "m_max": zone_m_max,
                "base_density_per_ha": pl.get("target_per_ha"),
                "grid_density_per_ha": pl.get("grid_target_per_ha"),
                "port_xcheck_max_err": zone_meta["xcheck_max_err"],
                "ceiling": zone_meta.get("ceiling"),
            }
        _doc.update({"biome": recipe["biome_id"], "species": sp["name"],
                       "mesh": sp["mesh"], "count": len(rows),
                       # DECLARED so a verifier can tell a deliberate
                       # sink from a floating instance. Without it the
                       # only readings are "on the surface" and "not on
                       # the surface", and a 0.12 m sink is
                       # indistinguishable from a 0.12 m error.
                       "sink_depth_m": float(
                           sp.get("sink_depth_m", 0.0) or 0.0),
                       "units": "cm, degrees, uniform scale",
                       # schema v1.11. Absent or 0 means the engine
                       # default, which is culling DISABLED — see the
                       # payload's cull-distance block for why that
                       # matters and what it cost.
                       # schema v1.25 (E1, ruled 2026-09-09). DERIVED from
                       # recipe.perception when a measured height exists for
                       # the species, else the authored value. The full
                       # derivation is written into the sidecar under
                       # `cull_derivation` -- a derived number whose working
                       # is not recorded is just a different magic constant.
                       "cull_cm": _cull_deriv[0],
                       # The working, not just the answer.
                       "cull_derivation": _cull_deriv[1],
                       # schema v1.24. CARRIED THROUGH DELIBERATELY.
                       # This dict is the ONLY thing the placement payload
                       # sees - the recipe species never reaches it - so a
                       # key omitted here is a key the payload cannot act
                       # on however carefully it handles it. That exact
                       # omission, in the grass builder's variety
                       # transform, silently dropped eight wind-off
                       # overrides earlier the same day while every gate
                       # reported success.
                       "override_materials": list(
                           sp.get("override_materials") or []),
                       # RULED 2026-09-12b. DECLARED IN THE ARTEFACT, so a
                       # reader can tell a plan that was filtered from one
                       # that never had a town to avoid -- absent and zero
                       # are different facts, and the whole defect this
                       # closes was a file that looked complete while
                       # describing trees the world did not have.
                       "settlement_exclusion": (
                           None if _excl_shapes is None else {
                               "from_city_plan": _excl_decl["from_city_plan"],
                               "building_margin_m": _excl_margins[0],
                               "street_margin_m": _excl_margins[1],
                               "plaza_margin_m": _excl_margins[2],
                               "removed": _excl_removed.get(sp["name"], 0),
                               "applied": "post-filter on built rows; "
                                          "sampling RNG untouched",
                           }),
                       # Brief-4 water carve. Same absent-vs-zero contract as
                       # settlement: a reader can tell a plan filtered against
                       # the lakes from one placed before there were lakes.
                       "water_exclusion": (
                           None if _water_mask is None else {
                               "exclusion_mask": _water_decl["exclusion_mask"],
                               "removed": _water_removed.get(sp["name"], 0),
                               "applied": "post-filter on built rows; "
                                          "sampling RNG untouched",
                           }),
                     "instances": rows})
        # Stamp from the SAME `_prov` dict that was merged in above, so the
        # declaration and the hashes cannot describe different inputs.
        _doc[plan_stamp.STAMP_KEY] = plan_stamp.stamp(_doc, REPO_ROOT)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(_doc, fh)
        written.append((sp["name"], path, len(rows)))
        print("  wrote {0:<40} {1:>9,} instances  {2:.1f} MB".format(
            os.path.relpath(path, REPO_ROOT), len(rows),
            os.path.getsize(path) / 1048576.0))

    if _excl_removed:
        _tot_rm = sum(_excl_removed.values())
        print("")
        print("--- settlement exclusion ---")
        for _n in sorted(_excl_removed):
            print("  {0:<16} {1:>7,} removed".format(_n, _excl_removed[_n]))
        print("  {0:<16} {1:>7,} removed from the town footprint"
              .format("TOTAL", _tot_rm))
        # ROCKS ARE ADOPTED, NOT GENERATED HERE, and are therefore NOT
        # filtered by this pass. Said out loud because a summary that
        # reports only what it did invites the reader to assume it did
        # everything -- the acceptance is about TREES, and rocks standing
        # in the town remain an open item.
        print("  NOTE: adopted rock plans are not filtered by this pass.")

    if _water_removed:
        _tot_w = sum(_water_removed.values())
        print("")
        print("--- water exclusion (Brief-4 lakes) ---")
        for _n in sorted(_water_removed):
            print("  {0:<16} {1:>7,} removed".format(_n, _water_removed[_n]))
        print("  {0:<16} {1:>7,} removed from the water footprints"
              .format("TOTAL", _tot_w))

    # ---- THE FLOOR GATE (F-1 / E-2), after the write --------------------
    #
    # The density gate and the total gate above are CEILING-ONLY (`>`): they
    # fire when a plan is too LARGE and are blind to one that is quietly HALF
    # the intended size. That blindness passed the 152-instance regeneration
    # and a 111,079-against-a-ruled-220,000 shortfall, both exiting 0 and
    # reporting success (plans/RECIPES_draft_closure.md:141).
    #
    # READ BACK FROM DISK, not from the in-memory `total`. `total` was summed
    # from the plan structures the planner built; re-reading the files counts
    # what actually LANDED, with a different instrument (NN0) -- a write that
    # dropped rows, or the settlement exclusion eating the plan, is visible
    # here and invisible to `total`. The number of files read is the sample
    # count reported beside the verdict (rule 13); a zero-file read cannot
    # confirm anything and the verdict function refuses on the zero count it
    # produces WHENEVER THE GATE IS ARMED (with --ruled-count; unarmed it
    # DEGRADEs on the ruled-shape check first, which is the NN6 named gap).
    #
    # Scope: FOLIAGE species only, matching the ceiling gate's `total`. Adopted
    # rocks are counted after this and carry their own plans and budget.
    _read_back = 0
    _files_read = 0
    for _nm, _pth, _cnt in written:
        with open(_pth, "r", encoding="utf-8") as _rfh:
            _read_back += len(json.load(_rfh).get("instances") or [])
        _files_read += 1
    print("")
    print("--- floor gate (F-1) ---")
    print("  read back {0:,} instances from {1} foliage plan file(s) on disk"
          .format(_read_back, _files_read))
    _fstatus, _fneed, _fmsg = floor_gate_verdict(_read_back, args.ruled_count)
    print("  {0}".format(_fmsg))
    if _fstatus == "REFUSE":
        print("  Nothing further was placed. The plan files on disk are BELOW "
              "the ruled floor and must not be handed to --place.")
        return 3

    adopted, rock_err = adopt_rock_plans(recipe)
    if rock_err:
        for line in rock_err:
            print("REFUSE: {0}".format(line))
        return 3
    for name, path, n in adopted:
        written.append((name, path, n))
        print("  adopt {0:<40} {1:>9,} instances  (rock_scatter.py)".format(
            os.path.relpath(path, REPO_ROOT), n))

    print("")
    if not args.place:
        print("=" * 70)
        print("PLAN ONLY — nothing was spawned. Every placement decision "
              "above is")
        print("verifiable from these files without an editor. Re-run with "
              "--place to build them.")
        print("=" * 70)
        return 0

    return _place(recipe, written, args)


MARKER = "__LANDSCAPELAB_FOLIAGE__"

# The editor payload. It takes a PATH and reads the file itself; the
# transforms never travel through the transport. 66k instances is a few
# megabytes of JSON, and a response that outgrew the transport has
# already cost this project a push (exit 5, 2026-08-02).
#
# Every reflected name below was resolved from the generated stub in one
# read before a line was written, because inventing them has cost three
# live runs (lesson 18.2):
#   FoliageType_InstancedStaticMesh          stub 390277, `mesh` property
#   FoliageType_InstancedStaticMeshFactory   stub 390588
#   InstancedFoliageActor.remove_all_instances(world, type)   stub 589752
#   InstancedFoliageActor.add_instances(world, type, xforms)  stub 589763
#   InstancedStaticMeshComponent.get_instance_count()         stub 681655
# add_instances returns None, so the count it placed is NOT evidence of
# anything - the verification below counts the components afterwards.
PLACE_SOURCE = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "stage": "start", "species": []}}
_plans = {plans!r}
_ft_dir = {ft_dir!r}
_batch = int({batch})
_MAX_PIVOT_M = float({max_pivot})
_MAX_BASE_Z_M = float({max_base_z})

try:
    _world = _unreal.EditorLevelLibrary.get_editor_world()
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()

    # ---- ORPHAN SWEEP, before anything is added -------------------
    # remove_all_instances clears the type it is HANDED. A species
    # deleted from the recipe is never handed to it, so its instances
    # survive every subsequent run and the world drifts away from the
    # recipe -- which is hard rule 3 (re-running a recipe rebuilds
    # deterministically) failing silently. Caught by the count check:
    # 28,302 planned against 70,923 in the world, the remainder being
    # Scrub and Boulder from a recipe that no longer mentions them.
    _out["stage"] = "orphan_sweep"
    _keep = set(_e[0] for _e in _plans)
    _orphans = []
    for _p in _unreal.EditorAssetLibrary.list_assets(
            _ft_dir, recursive=False, include_folder=False):
        _name = _p.split("/")[-1].split(".")[0]
        if not _name.startswith("FT_"):
            continue
        if _name[3:] in _keep:
            continue
        _o = _unreal.EditorAssetLibrary.load_asset(_p.split(".")[0])
        if _o is None:
            continue
        _unreal.InstancedFoliageActor.remove_all_instances(_world, _o)
        _orphans.append(_name)
    _out["orphans_cleared"] = _orphans

    for _entry in _plans:
        _name, _path = _entry[0], _entry[1]
        _row = {{"name": _name, "requested": 0, "placed": 0}}
        _out["stage"] = "read:" + _name
        with open(_path, "r") as _fh:
            _doc = _json.load(_fh)
        _rows = _doc["instances"]
        _row["requested"] = len(_rows)

        _out["stage"] = "foliage_type:" + _name
        _ft_path = _ft_dir + "/FT_" + _name
        if _unreal.EditorAssetLibrary.does_asset_exist(_ft_path):
            _ft = _unreal.EditorAssetLibrary.load_asset(_ft_path)
        else:
            _ft = _tools.create_asset(
                "FT_" + _name, _ft_dir,
                _unreal.FoliageType_InstancedStaticMesh,
                _unreal.FoliageType_InstancedStaticMeshFactory())
        if _ft is None:
            _out["error"] = "could not create foliage type " + _ft_path
            break
        _mesh = _unreal.EditorAssetLibrary.load_asset(_doc["mesh"])
        if _mesh is None:
            _out["error"] = "mesh not found: " + _doc["mesh"]
            break
        _ft.set_editor_property("mesh", _mesh)

        # ---- F-3: OVERRIDE-LIST LENGTH vs MESH MATERIAL SLOT COUNT -----
        #
        # override_materials is POSITIONAL, in the mesh's OWN slot order. The
        # read-back below proves the list STUCK; it cannot prove the list has
        # the RIGHT LENGTH -- a list one entry short repaints slot-for-slot up
        # to where it runs out and leaves the rest vendor-lit, and a list one
        # entry long silently drops its tail. Latent today only because every
        # current mesh has ONE slot; a multi-slot mesh mis-orders in silence.
        #
        # The slot count is READ BACK from the mesh (static_materials, the same
        # accessor c0_build_stage_payload uses), reported in the row, and the
        # length is checked BEFORE a single material is set. A read that throws
        # leaves the count None; with a list pending, that is the unguarded
        # action (a mis-ordered set) and it fails CLOSED -- refuse, do not set.
        _ovr = _doc.get("override_materials") or []
        _nslots = None
        # `except ... as _e` is implicitly del'd when the block exits, so the
        # message is captured INSIDE the handler into a name that survives --
        # otherwise the error path below NameErrors in exactly the failure it
        # describes (audit D-3 F1: a failed measurement must report that it
        # failed, not raise trying to).
        _serr = None
        try:
            _nslots = len(list(_mesh.static_materials))
        except Exception as _sexc:
            _nslots = None
            _serr = "%s: %s" % (type(_sexc).__name__, _sexc)
        _row["slot_count"] = _nslots
        _row["override_count"] = len(_ovr)
        if _ovr:
            if _nslots is None:
                _out["error"] = (
                    "F-3: could not read the material slot count for "
                    + _doc["mesh"] + " (" + str(_serr) + "); refusing to set "
                    "a positional override list of length " + str(len(_ovr))
                    + " that cannot be validated")
                _out["species"].append(_row)
                break
            if _nslots <= 0:
                _out["error"] = (
                    "F-3: mesh " + _doc["mesh"] + " reports " + str(_nslots)
                    + " material slots but " + str(len(_ovr)) + " override(s) "
                    "are declared. A zero read is silence, not agreement; "
                    "refusing")
                _out["species"].append(_row)
                break
            if len(_ovr) != _nslots:
                _out["error"] = (
                    "F-3: override_materials for " + _doc["mesh"] + " has "
                    + str(len(_ovr)) + " entries but the mesh has "
                    + str(_nslots) + " material slots. The list is POSITIONAL "
                    "and would mis-order; refusing before any material is set")
                _out["species"].append(_row)
                break

        # MATERIAL OVERRIDES — schema v1.24, and the reason 108,417 trees
        # spent a session wearing the wrong materials.
        #
        # `FoliageType_InstancedStaticMesh.override_materials` exists in 5.8
        # (PythonStub:394542, property at :394610) and is the ONLY way to
        # render a vendor mesh with a material we control without editing
        # the vendor asset — which is forbidden here, because the packs are
        # gitignored with 0 tracked files and an edit vanishes on
        # re-download.
        #
        # WHY IT WAS MISSING. Wind-off child MIs were built and verified,
        # and the tool that builds them even printed that a consumer "must
        # hand it to FoliageType.override_materials unchanged". No consumer
        # was ever written. The render proof applied them BY HAND to a
        # scratch actor, which proved the MATERIALS work and nothing about
        # the PLACEMENT PATH. So SpruceSub and
        # SpruceSapling were placed on vendor materials with wind ON, and
        # that plausibly contaminated the per-station noise floor the whole
        # A/B method rests on.
        #
        # POSITIONAL, in the mesh's own slot order — a reordered list
        # silently repaints the tree. READ BACK, because an override that
        # silently did not stick looks exactly like one that did, which is
        # the same lesson the cull distance below is written in blood for.
        # (`_ovr` was read and its length checked against the slot count in
        #  the F-3 block above.)
        if _ovr:
            _mats, _badm = [], []
            for _mp in _ovr:
                _mi = _unreal.EditorAssetLibrary.load_asset(_mp)
                if _mi is None:
                    _badm.append(_mp)
                else:
                    _mats.append(_mi)
            if _badm:
                _out["error"] = ("override material(s) not found for "
                                 + _doc["species"] + ": " + ", ".join(_badm))
                break
            _ft.set_editor_property("override_materials", _mats)
            _goto = _ft.get_editor_property("override_materials") or []
            _back = [_x.get_path_name().split(".")[0] if _x else None
                     for _x in _goto]
            _want = [str(_x).split(".")[0] for _x in _ovr]
            _row["override_materials"] = _back
            if _back != _want:
                _out["error"] = (
                    "override_materials did NOT stick for " + _doc["species"]
                    + ": wanted " + repr(_want) + " read back " + repr(_back))
                break

        # CULL DISTANCE — schema v1.11, and it is why the GPU hung.
        #
        # FoliageType.h:292 documents CullDistance as "0 disables. When
        # the entire cluster is beyond this distance, the cluster is
        # completely culled and not rendered at all", and
        # InstancedFoliage.cpp:602-603 DEFAULTS both ends to 0. This
        # script previously set only `mesh`, so every foliage type it
        # created had culling off — 28,302 instances of a 505k-triangle
        # mesh submitted every frame across an 8 km map, which took the
        # frame past the Windows TDR timeout and returned
        # DXGI_ERROR_DEVICE_HUNG. Not a memory problem: 3998 MB of an
        # 8283 MB budget was in use.
        #
        # It was also a hard rule 2 break hiding in plain sight. The cull
        # distance is a scene parameter and it came from nowhere — no
        # recipe key, no default in this file, just whatever the engine
        # constructor happened to leave.
        #
        # Min is the FADE start (needs a PerInstanceFadeAmount node in
        # the material to actually fade; without one it is simply the
        # distance the engine starts treating the cluster as far). Max is
        # the hard cull. Set from the recipe, then READ BACK, because a
        # cull distance that silently stayed 0 looks exactly like one
        # that was applied.
        _cull_cm = int(_doc.get("cull_cm") or 0)
        if _cull_cm > 0:
            _ft.set_editor_property(
                "cull_distance",
                _unreal.Int32Interval(int(_cull_cm * 0.75), _cull_cm))
            _gotc = _ft.get_editor_property("cull_distance")
            _row["cull_min_cm"] = int(_gotc.min)
            _row["cull_max_cm"] = int(_gotc.max)
            if int(_gotc.max) != _cull_cm:
                _out["error"] = (
                    "cull distance did not read back: asked for " +
                    str(_cull_cm) + " cm, got " + str(int(_gotc.max)))
                _out["species"].append(_row)
                break
        else:
            _row["cull_min_cm"] = 0
            _row["cull_max_cm"] = 0
        # Read back rather than trust the setter: a foliage type with no
        # mesh accepts instances and renders nothing, which looks exactly
        # like placement having failed.
        _got = _ft.get_editor_property("mesh")
        _row["mesh_ok"] = bool(_got is not None
                               and _got.get_path_name() ==
                               _mesh.get_path_name())
        if not _row["mesh_ok"]:
            _out["error"] = "foliage type mesh did not read back: " + _name
            _out["species"].append(_row)
            break

        # RULING (c) -- THE CHECK THAT CANNOT BE FOOLED.
        #
        # The recipe validator and the importer both enforce (c) by
        # NAME, against a report on disk. Neither can see the pivot on
        # the asset actually loaded here, so both are defeated by an
        # asset rebuilt from a vendor file under a verified name. This
        # one measures the thing itself, at the exact moment it is about
        # to be instanced 28,302 times.
        #
        # get_bounds() returns LOCAL-space bounds relative to the asset
        # pivot in cm (UStaticMesh::GetBounds -> GetExtendedBounds,
        # StaticMesh.cpp:5105/7285), so hypot(origin.x, origin.y) is the
        # horizontal pivot-to-geometry distance.
        try:
            _b = _mesh.get_bounds()
            _bo, _be = _b.origin, _b.box_extent
            _off = ((_bo.x * _bo.x + _bo.y * _bo.y) ** 0.5) / 100.0
            _row["pivot_offset_xy_m"] = round(_off, 4)
            _row["bounds_size_m"] = [round(_be.x * 2 / 100.0, 4),
                                     round(_be.y * 2 / 100.0, 4),
                                     round(_be.z * 2 / 100.0, 4)]
            # Vertical half of the contract: a base-centre pivot puts
            # the lowest point AT the pivot, so this is 0. A centre
            # pivot reports minus half the height and every instance is
            # buried to the waist.
            _row["base_offset_z_m"] = round((_bo.z - _be.z) / 100.0, 4)
        except Exception as _exc:
            _row["pivot_offset_xy_m"] = None
            _row["pivot_read_error"] = "%s: %s" % (type(_exc).__name__,
                                                   _exc)
        _bad_bounds = (
            _row.get("bounds_size_m") is None
            or any((_v is None) or (_v != _v) or (_v <= 0.0)
                   for _v in (_row.get("bounds_size_m") or [0])))
        _po = _row.get("pivot_offset_xy_m")
        # Degenerate bounds read as origin 0,0,0 -- i.e. a PASS -- exactly
        # when the mesh has no usable geometry, so they are failed first
        # and separately. And `not (x <= limit)` rather than `x > limit`,
        # because NaN is False for the latter (section 2.8, fifth time).
        if _bad_bounds or not isinstance(_po, (int, float)) or _po != _po:
            _out["error"] = (
                "ruling (c): could not measure the pivot of " +
                _doc["mesh"] + " (" + str(_row.get("pivot_read_error",
                                                   "degenerate bounds")) +
                "); refusing to place instances whose displacement is "
                "unknown")
            _out["species"].append(_row)
            break
        _bz = _row.get("base_offset_z_m")
        if not isinstance(_bz, (int, float)) or _bz != _bz:
            _out["error"] = (
                "ruling (c): could not measure the vertical pivot of " +
                _doc["mesh"] + "; refusing to place instances whose "
                "ground contact is unknown")
            _out["species"].append(_row)
            break
        # A plan may DECLARE that it already corrected for the pivot.
        # Rocks are box-centred by design and can never pass the
        # normalisation limit, so for them the question is not "is the
        # pivot at the base" but "did you correct by the RIGHT amount".
        # Declaring it is the stronger test: it catches a plan computed
        # against a stale measurement, which the limit cannot see.
        # Omitting it falls back to the strict gate, so this cannot be
        # used to skip the check.
        _decl = _doc.get("pivot_base_offset_m")
        if _decl is not None:
            if not isinstance(_decl, (int, float)) or _decl != _decl:
                _out["error"] = (
                    "ruling (c): " + _doc["mesh"] + " declares a "
                    "pivot_base_offset_m that is not a finite number (" +
                    repr(_decl) + ")")
                _out["species"].append(_row)
                break
            _row["declared_base_offset_m"] = float(_decl)
            # 1 cm. The plan and the engine are reading the SAME asset
            # bounds, so any real disagreement means the asset changed
            # since the plan was written -- not a rounding difference.
            if not (abs(float(_decl) - _bz) <= 0.01):
                _out["error"] = (
                    "ruling (c): " + _doc["mesh"] + " was planned with a "
                    "pivot correction of " + str(_decl) + " m but the "
                    "asset now measures " + str(_bz) + " m. The plan is "
                    "STALE relative to the mesh; every instance would be "
                    "off the ground by the difference. Re-run "
                    "measure_rock_meshes and then rock_scatter --write "
                    "(RECIPES R12 steps 1 and 4). NOTE: no dot-p-y "
                    "spelling anywhere in this payload -- ExecuteFile "
                    "scans the whole command for it and would treat the "
                    "script as a path (lesson 12.10).")
                _out["species"].append(_row)
                break
        elif not (abs(_bz) <= _MAX_BASE_Z_M):
            _out["error"] = (
                "ruling (c): " + _doc["mesh"] + " has its base " +
                str(_bz) + " m from its pivot (limit " +
                str(_MAX_BASE_Z_M) + " m). Every instance would sit that "
                "far into or above the ground. Re-import from a "
                "normalised source, or -- if this is a rock whose pivot "
                "was corrected at plan time -- have the planner declare "
                "pivot_base_offset_m.")
            _out["species"].append(_row)
            break
        if not (_po <= _MAX_PIVOT_M):
            _out["error"] = (
                "ruling (c): " + _doc["mesh"] + " has its geometry " +
                str(_row["pivot_offset_xy_m"]) + " m from its pivot "
                "(limit " + str(_MAX_PIVOT_M) + " m). Every instance "
                "would be displaced by that much and random yaw would "
                "sweep it around a circle of that radius. Re-import from "
                "a normalised source.")
            _out["species"].append(_row)
            break

        # Idempotency: clear this type's instances before adding, so a
        # re-run replaces rather than doubling. Hard rule 3.
        _out["stage"] = "clear:" + _name
        _unreal.InstancedFoliageActor.remove_all_instances(_world, _ft)

        _out["stage"] = "add:" + _name
        _buf = []
        for _r in _rows:
            _buf.append(_unreal.Transform(
                _unreal.Vector(_r[0], _r[1], _r[2]),
                # KEYWORDS, NOT POSITIONS. unreal.Rotator's constructor
                # is (roll, pitch, yaw); the row is
                # [x, y, z, YAW, PITCH, ROLL, scale]. The positional form
                # here was Rotator(_r[4], _r[3], _r[5]) = (pitch, yaw,
                # roll), which fed the 0-360 random YAW into PITCH:
                # 97.6% of trees tilted past 4 degrees, MEDIAN TILT 90
                # degrees, 55.6% past 80. The forest was lying down.
                #
                # A defect-class sweep found every other Rotator in the
                # repo already used keywords and was correct (the
                # lighting and capture scripts). Keywords make the
                # transposition unrepresentable -- that is the fix, not
                # "be careful with the order".
                # (File names are spelled without their extension here
                # on purpose: the transport guard refuses any payload
                # containing a Python filename, and it caught an earlier
                # draft of this very comment.)
                _unreal.Rotator(roll=_r[5], pitch=_r[4], yaw=_r[3]),
                _unreal.Vector(_r[6], _r[6], _r[6])))
            if len(_buf) >= _batch:
                _unreal.InstancedFoliageActor.add_instances(
                    _world, _ft, _buf)
                _buf = []
        if _buf:
            _unreal.InstancedFoliageActor.add_instances(_world, _ft, _buf)
        _out["species"].append(_row)

    # ---- verification: COUNT what is in the world ------------------
    # add_instances returns None, so the only evidence is the components
    # themselves. Sum every instanced component on every foliage actor.
    _out["stage"] = "verify"
    _total = 0
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.InstancedFoliageActor):
        for _c in _a.get_components_by_class(
                _unreal.InstancedStaticMeshComponent):
            _total += int(_c.get_instance_count())
    _out["world_instance_total"] = _total
    _out["stage"] = "done"
    _out["ok"] = "error" not in _out
except Exception as _exc:
    _out["error"] = "%s at stage %r: %s" % (
        type(_exc).__name__, _out.get("stage"), _exc)

print("{marker}" + _json.dumps(_out))
'''


def _parse(text, marker=MARKER):
    i = text.find(marker)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[i + len(marker):]
                                                   .lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _place(recipe, written, args):
    """Phase 2: hand the plan files to the editor and verify the result."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import bootstrap
    import verify_landscape

    print("--- editor identity gate (conduct rule 7) ---")
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Nothing was placed.".format(reason))
            return 4
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))

        def _run(source, marker=MARKER):
            try:
                remote.open_command_connection(node["node_id"])
            except Exception as exc:                # noqa: BLE001
                print("  connection failed: {0}: {1}".format(
                    type(exc).__name__, exc))
                return None
            try:
                r = remote.run_command(
                    source, unattended=True,
                    exec_mode=remote_exec.MODE_EXEC_FILE)
                if not r or not r.get("success"):
                    print("  command failed: {0}".format(
                        (r or {}).get("result")))
                    return None
                return _parse(bootstrap._collect_output(r), marker)
            except Exception as exc:                # noqa: BLE001
                print("  errored: {0}: {1}".format(type(exc).__name__, exc))
                return None
            finally:
                try:
                    remote.close_command_connection()
                except Exception:                   # noqa: BLE001
                    pass

        print("")
        print("--- level gate (recipe landscape.level_path) ---")
        want_level = (recipe.get("landscape") or {}).get("level_path")
        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, node["node_id"], want_level, _run)
        if not ok_level:
            print("REFUSE (level gate): {0}".format(detail))
            print("  Nothing was placed. Foliage lands in whichever world "
                  "is open, and it is not undone by a reload once saved.")
            return 7
        print("  level {0}".format(detail))
        print("")

        # replace(os.sep, "/"): the old pattern was TWO backslashes — a
        # no-op on abspath output (single separators), asserting a
        # normalisation that never happened (Pass 3 2026-09-16).
        plans = [[name, os.path.abspath(path).replace(os.sep, "/")]
                 for name, path, _n in written]
        source = PLACE_SOURCE.format(
            plans=plans, ft_dir="/Game/Foliage", batch=args.batch,
            max_pivot=landscape_spec.MAX_PIVOT_OFFSET_M,
            max_base_z=landscape_spec.MAX_BASE_OFFSET_M,
            marker=MARKER)
        if ".py" in source:
            # Lesson 12.10: ExecuteFile mode scans the WHOLE command for
            # the substring and treats the payload as a path if found.
            print("REFUSE: the payload names a .py file; that breaks the "
                  "transport (PythonScriptPlugin.cpp:813-830).")
            return 1

        print("--- placing ---")
        res = _run(source)
        if res is None:
            print("FAIL: the placement payload returned nothing. State is "
                  "UNKNOWN — re-run without --place to see the plan, then "
                  "check the Foliage actors before retrying.")
            return 4
        if res.get("orphans_cleared"):
            print("  orphans cleared: {0}".format(
                ", ".join(res["orphans_cleared"])))
            print("    (foliage types with no species in the recipe; "
                  "their instances would otherwise survive every run)")
        for row in res.get("species") or []:
            print("  {0:<14} requested {1:>8,}   mesh bound {2}".format(
                row.get("name"), row.get("requested"),
                row.get("mesh_ok")))
            # RULING (c) gate, REPORTED. The gate runs in the payload
            # before a single instance is added, so a passing run and a
            # run where the gate silently never executed look identical
            # from here — which is the whole failure mode this project
            # keeps paying for. Printing the measured values is what
            # makes the check evidence rather than an assertion.
            if row.get("pivot_offset_xy_m") is not None:
                print("  {0:<14} pivot {1} m horizontal, base {2} m "
                      "(limits {3} / {4})   bounds {5} m".format(
                          "", row.get("pivot_offset_xy_m"),
                          row.get("base_offset_z_m"),
                          landscape_spec.MAX_PIVOT_OFFSET_M,
                          landscape_spec.MAX_BASE_OFFSET_M,
                          row.get("bounds_size_m")))
            elif row.get("pivot_read_error"):
                print("  {0:<14} PIVOT READ FAILED: {1}".format(
                    "", row["pivot_read_error"]))
            # F-3 slot-count gate, REPORTED and RE-JUDGED host-side. The
            # payload already refuses a mismatch before setting anything; this
            # re-runs the same contract on the numbers it READ BACK, with a
            # different instrument (rule 13: the slot count is stated beside
            # the verdict). "override_count" is absent only from a row the
            # payload never reached, so `.get` leaves it None and the verdict
            # DEGRADEs rather than crashing.
            _oc = row.get("override_count")
            if isinstance(_oc, int) and _oc > 0:
                _sstatus, _smsg = override_slot_verdict(
                    _oc, row.get("slot_count"))
                print("  {0:<14} slots: {1}".format("", _smsg))
                if _sstatus == "REFUSE" and not res.get("error"):
                    print("")
                    print("FAIL (F-3): {0}".format(_smsg))
                    return 4
        if res.get("error"):
            print("")
            print("FAIL at stage {0}: {1}".format(
                res.get("stage"), res["error"]))
            return 4

        total_planned = sum(n for _nm, _p, n in written)
        in_world = res.get("world_instance_total")
        print("")
        print("--- verification ---")
        print("  planned          {0:,}".format(total_planned))
        print("  counted in world {0:,}".format(in_world))
        if in_world != total_planned:
            print("")
            print("FAIL: the world holds a different number of instances "
                  "than were planned.")
            print("  add_instances returns None, so this count IS the "
                  "evidence — a mismatch means some did not land, or a "
                  "previous run's instances were not cleared.")
            return 4
        print("")
        print("=" * 70)
        print("PLACED {0:,} instances across {1} species, counted in the "
              "world.".format(total_planned, len(written)))
        print("=" * 70)
        print("")
        print("Pipeline rule 4: run the capture script (a LESSONS.md note "
              "is suggested, not required). NOT SAVED — foliage persists "
              "only after save_level.")
        return 0
    finally:
        remote.stop()


def _selftest():
    """Offline, state-independent tests of the two REFUSAL gates (D-3).

    THREE DIRECTIONS each (verification-practice): (1) BLOCK the violation,
    (2) PASS the legitimate case, (3) BLOCK/DEGRADE WHEN BROKEN -- missing or
    malformed input must refuse or degrade with a named gap, never crash
    through. Pure functions over synthetic inputs: no editor, no recipe, no
    disk, so the suite passes IDENTICALLY whatever the repo looks like when it
    runs (a test confounded by live state asserts an outcome, not a contract).
    """
    fails = []

    def check(name, cond):
        print(("  ok    " if cond else "  FAIL  ") + name)
        if not cond:
            fails.append(name)

    print("FLOOR GATE (F-1): floor = %.0f%% of the ruled count"
          % (FLOOR_FRACTION * 100.0))
    ruled = 1000
    # 1. BLOCK the violation
    _s, _need, _ = floor_gate_verdict(750, ruled)   # -25%
    check("floor: -25pct (750/1000) REFUSES, floor=800",
          _s == "REFUSE" and _need == 800)
    check("floor: 799 (just under the floor) REFUSES",
          floor_gate_verdict(799, ruled)[0] == "REFUSE")
    check("floor: 111,079 vs ruled 220,000 REFUSES (the real shortfall)",
          floor_gate_verdict(111079, 220000)[0] == "REFUSE")
    check("floor: 152 vs ruled 220,000 REFUSES (the regression)",
          floor_gate_verdict(152, 220000)[0] == "REFUSE")
    # 2. PASS the legitimate case (incl. the derived boundary and over-target)
    check("floor: 800 (exactly the floor) PASSES",
          floor_gate_verdict(800, ruled)[0] == "PASS")
    check("floor: 950 (within tolerance) PASSES",
          floor_gate_verdict(950, ruled)[0] == "PASS")
    check("floor: 1200 (over the ruled count) PASSES",
          floor_gate_verdict(1200, ruled)[0] == "PASS")
    # 3. BLOCK/DEGRADE WHEN BROKEN
    check("floor: missing ruled count DEGRADES (named gap)",
          floor_gate_verdict(750, None)[0] == "DEGRADE")
    check("floor: ruled count <= 0 DEGRADES",
          floor_gate_verdict(750, 0)[0] == "DEGRADE")
    check("floor: ruled count malformed (str) DEGRADES",
          floor_gate_verdict(750, "lots")[0] == "DEGRADE")
    check("floor: placed unreadable (None) REFUSES, not passes",
          floor_gate_verdict(None, ruled)[0] == "REFUSE")
    check("floor: placed NaN REFUSES (a failed read is not a number)",
          floor_gate_verdict(float("nan"), ruled)[0] == "REFUSE")

    print("")
    print("SLOT-COUNT GATE (F-3): override list length == mesh slot count")
    # 1. BLOCK the violation
    check("slot: 3 overrides vs 4 slots REFUSES (mis-order)",
          override_slot_verdict(3, 4)[0] == "REFUSE")
    check("slot: 2 overrides vs 1 slot REFUSES",
          override_slot_verdict(2, 1)[0] == "REFUSE")
    # 2. PASS the legitimate case
    check("slot: 1 override vs 1 slot PASSES (today's meshes)",
          override_slot_verdict(1, 1)[0] == "PASS")
    check("slot: 4 overrides vs 4 slots PASSES (a multi-slot mesh)",
          override_slot_verdict(4, 4)[0] == "PASS")
    check("slot: 0 overrides declared SKIPS (nothing to mis-order)",
          override_slot_verdict(0, 1)[0] == "SKIP")
    # 3. BLOCK/DEGRADE WHEN BROKEN
    check("slot: slot count unreadable (None) DEGRADES (named gap)",
          override_slot_verdict(3, None)[0] == "DEGRADE")
    check("slot: 0 slots read but overrides declared REFUSES (rule 13)",
          override_slot_verdict(3, 0)[0] == "REFUSE")
    check("slot: malformed override count REFUSES",
          override_slot_verdict("x", 4)[0] == "REFUSE")
    check("slot: malformed (present) slot count REFUSES",
          override_slot_verdict(3, "four")[0] == "REFUSE")

    print("")
    if fails:
        print("SELFTEST FAILED: %d check(s) above" % len(fails))
        return 1
    print("SELFTEST OK: floor gate (F-1) and slot-count gate (F-3), "
          "3 directions each, offline.")
    return 0


if __name__ == "__main__":
    # --selftest is offline: no editor, no heavy op, no lock. Run it BEFORE
    # the resource guard so it neither WARNs on memory nor contends for the
    # heavy-op lock, and so the offline suite can call it on any machine.
    if "--selftest" in sys.argv[1:]:
        sys.exit(_selftest())
    # RESOURCE GUARD. Heavy operations log the memory situation before
    # they start and hold a lock so two never drive the same editor at
    # once (scripts/resource_guard.py). Low memory WARNS; a concurrent
    # heavy op REFUSES at exit 8.
    try:
        with resource_guard.HeavyOp('foliage placement (foliage regen)') as _guard_ok:
            if not _guard_ok:
                sys.exit(8)
            sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:                       # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
