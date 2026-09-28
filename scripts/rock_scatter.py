"""rock_scatter.py — schema v1.12 rock / cliff / talus / hero-boulder scatter.

OFFLINE ONLY. This module never imports `unreal` and never contacts the
editor. It computes masks and instance transforms from the heightmap and
the BAKED weightmap, writes one plan file per species in EXACTLY the
format `place_foliage.py` already writes, and reports the triangle
budget. Placement into the editor is `place_foliage.py --place`'s job and
is unchanged.

  READ THIS BEFORE PLACING ANYTHING
  `place_foliage.py`'s editor payload runs an ORPHAN SWEEP over
  /Game/Foliage (PLACE_SOURCE, place_foliage.py ORPHAN SWEEP block —
  grep, don't cite a line; it has drifted): every `FT_*` asset whose
  name is not in the plan list handed to THAT run has
  `remove_all_instances` called on it. Placing rocks in a SEPARATE run
  from the vegetation therefore DELETES EVERY VEGETATION INSTANCE in the
  plans not handed to that run — sum the LIVE `foliage/<biome>_*.json`
  count fields for the real blast radius (the 8K set is ~217,102, not
  the archived-world 157,554 this note used to quote). Rocks and
  vegetation must be planned and
  placed in ONE run. See ORDERED STEPS in RECIPES R12.

WHAT IS DIFFERENT FROM VEGETATION, and why each difference is necessary

  MASK          A rock is not placed by a material layer's weight. Cliff
                rocks live on a slope band; talus lives on a computed
                deposition field; hero boulders live on meadow. So a
                rock species declares a `mask`, not a `layer` +
                `weight_share`. It also does NOT draw from
                `foliage.density_per_hectare` — that number is the tree
                budget, and coupling the two would move every rock when
                anyone retunes the forest.

  CORRELATION   Talus is not a slope band. A talus field that ignores
                what is above it reads as noise, and this project can
                measure the difference: the naive "scatter on 25-38 deg"
                band is 1,460 ha of this map, and 90.4% of it has no
                cliff feeding it. See `talus_deposit` below.

                MEASURED ON THE ADOPTED TERRAIN, 2026-08-03. These were
                1,994 ha / 97.9% when first written, against the terrain
                that preceded Pass 1's adoption — the docstring outlived
                the map it described. Every run recomputes and PRINTS
                both figures under `--- talus routing ---`; trust that
                line over this one, and update this one when they
                diverge (non-negotiable 25: prose claims in code rot).

  ORIENTATION   Rocks embed and follow the surface; trees do not. That
                inverts R4's rule, and it also breaks the CONSTRUCTION
                `place_foliage.plan()` uses. See `orient_to_normal`.

Exit codes:
  0  plans computed and written
  1  unexpected error / bad arguments
  2  recipe, heightmap, weightmap or registry missing or invalid
  3  the plan exceeds an instance ceiling — nothing written
  4  the rotation gate refused the plan
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
import placement_priors  # noqa: E402 — flow + canopy priors, one definition
import plan_stamp        # noqa: E402 — ONE declaration of a plan's inputs,
#                           shared with place_foliage, plan_city,
#                           plan_encounters and check_plan_freshness

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLIAGE_DIR = os.path.join(REPO_ROOT, "foliage")
TERRAIN_DIR = os.path.join(REPO_ROOT, "terrain")
MEASURED_DIR = os.path.join(REPO_ROOT, "Free", "_measured")

# THE SINGLE DECLARATION OF BOTH ROCK-SPECIES ENUMS (non-negotiable 24).
# `import_heightmap._validate_rock_species` imports these; it MUST NOT
# re-type them. Until 2026-08-08 it carried its own copies as
# `_ROCK_ROLES` and `_ROCK_MASK_KINDS`, two and three lines below an
# existing `from rock_scatter import MAX_LOD_DEPTH` — the right structure
# was already in use on the adjacent line.
#
# The drift is ASYMMETRIC and the dangerous direction is the natural one.
# Add a role to the VALIDATOR only and the recipe passes preflight while
# `main()` below drops the species from `specs`; the plan then reports
# success over a species that was never planned. Add it HERE only and
# preflight refuses, which is the safe failure. A structure whose
# careless direction is the silent one is the wrong structure.
ROLES = ("cliff", "talus", "hero", "clutter")
MASK_KINDS = ("slope", "talus", "layer")

# `clutter` added 2026-08-08 for Pass 5. It carries no special handling —
# the MASK does the placing — but it is a distinct role rather than a
# reuse of `hero` because the per-role coverage and triangle-budget
# reports group by it. Folding ~25k foot-level pieces into `hero`'s row
# beside 759 landmark boulders would produce a number that is
# arithmetically true and answers a question nobody asked
# (non-negotiable 22).

# Whole-recipe ceiling. `place_foliage` IMPORTS this rather than keeping a
# copy — rocks and vegetation compete for ONE budget because they are
# placed into one InstancedFoliageActor set, and a separate rock ceiling
# would let the two sum past the number chosen for this hardware.
# This comment used to say "shared with place_foliage.MAX_INSTANCES"
# while place_foliage.py:84 held its own literal 250000 — a prose claim
# of sharing standing in for the sharing (non-negotiable 25). It is now
# true by construction rather than by assertion.
#
# RAISED 250000 -> 860000 for Brief 5 Daylight Density (Ryan ruled at re-ASK #1,
# 2026-09-22): the density upgrade (zone map m up to 5.48 + the post-multiplier
# per-bin density ceiling D_max=1691/bin) regenerates the forest at 812,258 PLACED
# tree instances, measured in the D2 ceilinged dry run. This gate checks the
# PLANNED total (851,046, before the town + water post-exclusions drop 38,788), so
# the ceiling is 860,000 (not 850,000) to admit the planned total; Ryan ruled the
# bump at re-ASK #1 when the 850k gate refused the 851,046 plan by 1,046. D3 gates
# the actual viability at runtime: editor cell-load + VRAM at forest_floor/
# open_max/plaza and a -game settle, aborting to the pre-density-daylight tag if
# VRAM > 13312 MiB.
MAX_INSTANCES = 860000

# Cost model, reverse-engineered from R5's locked budget table and
# reproduced to within 0.10% on all four of its rows. Do not change these
# without re-validating against that table — a number computed on a
# different model is not comparable to 39.6M.
FOV_DEG = 75.0
LOD_SCREEN = (1.0, 0.5, 0.21, 0.088)
LOD_PERCENT = (1.0, 0.25, 0.0441, 0.0077)      # percent = screen_size^2

# The cost model can only express a chain this long. Exported so the
# recipe validator bounds `lod_depth` against the TABLE rather than
# against a number somebody typed twice (non-negotiable 24: two lists
# that must agree are one list badly stored).
MAX_LOD_DEPTH = len(LOD_PERCENT)


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.realpath(p)))


def _inside_repo(p):
    n, r = _norm(p), _norm(REPO_ROOT)
    return n == r or n.startswith(r + os.sep)


# ---------------------------------------------------------------------
# ORIENTATION
# ---------------------------------------------------------------------
# THE ENGINE'S OWN FORMULA, not a remembered convention.
# UE_5.8/Engine/Source/Runtime/Core/Public/Math/RotationTranslationMatrix.h
# :82-84 builds the rotation matrix in ROW-VECTOR form, so an object's
# local +Z (its "up") lands on matrix ROW 2:
#
#     up.x = -(CR*SP*CY + SR*SY)
#     up.y =   CY*SR - CR*SP*SY
#     up.z =   CR*CP
#
# Read that as a system in (pitch, roll) for a GIVEN yaw and it inverts
# in closed form:
#
#     a = -cos(yaw)*up.x - sin(yaw)*up.y     ->  a = CR*SP
#     b = -sin(yaw)*up.x + cos(yaw)*up.y     ->  b = SR
#     roll  = asin(b)          pitch = atan2(a, up.z)
#
# WHY THIS AND NOT THE EXISTING CONSTRUCTION.
# `place_foliage.plan()` (place_foliage.py plan(), the pitch/roll build) builds
#     pitch = degrees(arctan(gx)) * align
#     roll  = -degrees(arctan(gy)) * align
# which is EXACT ONLY AT YAW = 0 and degrades as yaw turns, because yaw
# is applied after pitch and roll and drags the tilt direction round with
# it. Measured over 20,000 random gradients and yaws, against the engine
# formula above:
#
#     align = 1.00 (rocks)  worst up-vector error  143.51 degrees
#     align = 0.15 (R4 conifers, slope <= 24)      7.21 degrees
#
# At the conifer setting that is harmless in MAGNITUDE — total tilt is
# still bounded by 4 degrees and R4's gate still passes — but it means
# the lean direction is effectively uncorrelated with the slope. At
# align = 1.0 it is fatal: a rock meant to lie in a cliff face stands on
# end. This is why rocks may not simply reuse plan()'s orientation code.
def orient_to_normal(nx, ny, nz, yaw_deg):
    """(pitch_deg, roll_deg) placing local +Z exactly on (nx, ny, nz).

    Inputs must be a unit vector. Returns arrays matching the inputs.
    """
    y = np.radians(yaw_deg)
    cy, sy = np.cos(y), np.sin(y)
    a = -cy * nx - sy * ny
    b = -sy * nx + cy * ny
    roll = np.degrees(np.arcsin(np.clip(b, -1.0, 1.0)))
    pitch = np.degrees(np.arctan2(a, nz))
    return pitch, roll


def blended_normal(gx, gy, align):
    """Unit up-vector `align` of the way from world-up to the surface normal.

    Interpolating the NORMAL and renormalising, rather than scaling Euler
    angles, is what makes align=0 exactly upright and align=1 exactly
    flush with the surface with nothing approximate in between.
    """
    n = np.stack([-gx, -gy, np.ones_like(gx)], axis=-1)
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    up = np.zeros_like(n)
    up[..., 2] = 1.0
    m = up * (1.0 - align) + n * align
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


# ---------------------------------------------------------------------
# TALUS
# ---------------------------------------------------------------------
def landform_slope(height_m, spacing_m, smooth_m):
    """Slope of the terrain with cell-scale TEXTURE removed.

    WHY THIS EXISTS. `stamps.detail_relief` (schema v1.16) adds +/-4.7 m
    ridged noise at a 28 m base wavelength to every face steeper than
    30 degrees. That is cliff TEXTURE and it is wanted — but it also tilts
    individual 4 m cells past any slope threshold you care to name.
    Measured on the adopted terrain:

        cell-scale slope >= 50 deg    9.152% of the map
        16 m landform slope           ~5.3%

    **Roughly 40% of the cell-scale "cliff" area is texture, not
    landform.** A rockfall-source test run on cell-scale slope therefore
    manufactures phantom cliffs all over ground that is, at the scale a
    boulder cares about, merely steep.

    `smooth_m` must sit ABOVE the detail scale and BELOW the cliff scale.
    Detail's finest octave here is 7 m and its base is 28 m; the massifs
    are 2200-4200 m across. 16 m attenuates the detail strongly and is
    invisible to the landforms.
    """
    sm = landform_height(height_m, spacing_m, smooth_m)
    gy, gx = np.gradient(sm, spacing_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def landform_height(height_m, spacing_m, smooth_m):
    """The terrain with cell-scale texture removed: ONE smoothing definition.

    Read by the cliff-source test (landform_slope) AND, since 2026-09-26,
    by the talus ROUTER. Ruled by Ryan after the 8K write run: talus is a
    hillslope-scale process, and a flow routed on the raw 1 m heightmap
    "just finds every pothole and fills it" -- measured as deposit max
    17,488.8 with p99 0.045 and an apron of 112.6 ha against R12 4a's
    305.4 ha. Both consumers smooth by `rock_scatter.source_smooth_m`
    (16 m: above the 7-28 m detail relief, below the 2-4 km massifs), so
    the field debris is routed on is the same landform its sources are
    read from.
    """
    # Local import, matching make_layer_weightmap.py:153 — scipy is only
    # needed on the paths that smooth, and this module's self-test runs
    # without it.
    from scipy import ndimage as _ndi

    sigma = float(smooth_m) / float(spacing_m)
    if sigma <= 0.0:
        raise ValueError("landform smooth_m must be > 0")
    return _ndi.gaussian_filter(height_m, sigma)


def talus_deposit(height_m, slope_deg, spacing_m, repose_deg,
                  cliff_source_slope_deg, runout_m, mfd_exponent,
                  max_steps, source_slope_deg=None, route_height_m=None):
    """Rockfall supply routed downslope. Returns the deposit field.

    `route_height_m` is the surface the FLOW DIRECTIONS are read from
    (default: `height_m`). Since 2026-09-26 the caller passes the 16 m
    landform (`landform_height`): at 1 m spacing the raw surface's
    micro-relief pits captured the fans (see landform_height). `slope_deg`
    (transmission: "can this cell hold debris") still reads the real
    surface, and `source_slope_deg` (supply) the landform, as before.

    THE MECHANISM, and why each half of it is there.

    Rock detaches from a face steeper than anything talus can hold
    (`cliff_source_slope_deg`), travels down the fall line, and comes to
    rest where the ground can hold it. So the deposit at a cell is the
    CLIFF AREA whose fall lines terminate there — correlated with what is
    above it by construction, which is the whole point. A talus field
    that ignores the cliff above is noise.

    MULTIPLE FLOW DIRECTION, not steepest descent. A single D8 path
    cannot build a cone: the first version of this used D8 and produced
    fans ONE CELL WIDE — an outline traced round every cliff. That was
    found by LOOKING AT THE ARTEFACT, not by reading the histogram, which
    was perfectly plausible. Material is split over every downhill
    neighbour in proportion to drop**`mfd_exponent`.

    RUNOUT, not a hard stop at the repose angle. Debris does not halt the
    instant the ground flattens to 35 degrees; it runs out and thins. The
    carried fraction below repose decays exponentially over a length that
    shrinks toward zero on flat ground, so a fan has a soft toe instead
    of a hard edge.

    Mass is conserved exactly: every unit of supply ends up somewhere in
    the deposit. The caller should assert that.
    """
    n = height_m.shape[0]
    idx = np.arange(n * n).reshape(n, n)
    nb = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx)]
    rh = height_m if route_height_m is None else route_height_m
    if rh.shape != height_m.shape:
        raise ValueError("route_height_m must match height_m's grid")

    wsum = np.zeros((n, n))
    wts, tgts = [], []
    for dy, dx in nb:
        shifted = np.roll(np.roll(rh, -dy, axis=0), -dx, axis=1)
        dist = spacing_m * math.hypot(dy, dx)
        drop = np.maximum((rh - shifted) / dist, 0.0)
        # Never route across the map edge. np.roll WRAPS, so without this
        # the north rim would feed the south rim.
        if dy == -1:
            drop[0, :] = 0.0
        if dy == 1:
            drop[-1, :] = 0.0
        if dx == -1:
            drop[:, 0] = 0.0
        if dx == 1:
            drop[:, -1] = 0.0
        w = drop ** float(mfd_exponent)
        wts.append(w)
        wsum += w
        # Border targets are CLIPPED, not wrapped. Their weight is already
        # zero, so clipping moves no mass; it only keeps the index legal.
        tgts.append(np.clip(idx + dy * n + dx, 0, n * n - 1).ravel())

    pit = wsum <= 0.0                      # local minimum: keeps everything
    safe = np.where(pit, 1.0, wsum)
    wts = [w / safe for w in wts]

    L = float(runout_m) * np.clip(slope_deg / float(repose_deg), 0.0, 1.0)
    trans = np.where(slope_deg >= float(repose_deg), 1.0,
                     np.exp(-spacing_m / np.maximum(L, 1e-6)))
    trans = np.where(pit, 0.0, trans)

    # SUPPLY is a LANDFORM question, TRANSMISSION is a SURFACE question,
    # and they must read different slope fields.
    #
    # "Is there a cliff here shedding rock?" is about the shape of the
    # mountain, so it reads `source_slope_deg` — slope with cell-scale
    # texture smoothed out. "Can this cell hold debris?" is about the
    # actual surface the debris sits on, so `trans` above keeps reading
    # the real `slope_deg`.
    #
    # Passing the same field to both is what produced phantom sources
    # once `detail_relief` existed: ~40% of the cell-scale >=50 deg area
    # is texture, not landform.
    src_slope = slope_deg if source_slope_deg is None else source_slope_deg
    supply = (src_slope >= float(cliff_source_slope_deg)).astype(np.float64)
    deposit = np.zeros((n, n))
    moving = supply.copy()
    steps = 0
    carried_at_cap = 0.0
    for steps in range(1, int(max_steps) + 1):
        deposit += moving * (1.0 - trans)
        carried = (moving * trans).ravel()
        carried_at_cap = float(carried.sum())
        if carried_at_cap < 1e-4:
            break
        nxt = np.zeros(n * n)
        for k in range(len(nb)):
            np.add.at(nxt, tgts[k], carried * wts[k].ravel())
        moving = nxt.reshape(n, n)
    deposit += moving          # whatever is still travelling at the cap

    lost = abs(deposit.sum() - supply.sum()) / max(supply.sum(), 1.0)
    if lost > 1e-6:
        raise ValueError(
            "talus routing lost {0:.4%} of its supply; the deposit field "
            "is not a redistribution of the cliff area and must not be "
            "used as one".format(lost))

    # NON-CONVERGENCE IS A SILENT QUALITY FAILURE, and the mass check
    # above CANNOT see it.
    #
    # Line `deposit += moving` dumps everything still in transit at the
    # cap WHEREVER IT HAPPENS TO BE, mid-slope, part-way down its fall
    # line. Mass is still conserved exactly, so the assertion passes and
    # the field looks healthy — but debris has been deposited at
    # positions it would never come to rest at, and the error is largest
    # exactly where the runout is longest, i.e. on the biggest fans,
    # which are the ones anybody would look at.
    #
    # Measured 2026-08-03: at `max_steps=60` on this 2017x2017 map the
    # loop consumed ALL 60 steps and reported success. Sixty was simply
    # too few, and nothing said so.
    #
    # So `steps == max_steps` is now a REFUSAL, not a note. A caller that
    # genuinely wants the truncated field must ask for it explicitly.
    # (CLAUDE.md non-negotiable 5: a check that consumes the value it is
    # verifying verifies nothing — conserving mass is not the same as
    # putting it in the right place.)
    if steps >= int(max_steps) and carried_at_cap > 1e-4:
        raise ValueError(
            "talus routing did NOT converge: it used all {0} steps with "
            "{1:.4f} units still in transit, which were then deposited "
            "where they happened to be rather than where they would come "
            "to rest. Mass conservation does not detect this. Raise "
            "max_steps until `steps < max_steps`.".format(
                max_steps, carried_at_cap))

    return deposit, int(supply.sum()), steps


# ---------------------------------------------------------------------
# MASKS
# ---------------------------------------------------------------------
def role_mask(spec, ctx):
    """Placement probability per cell, in [0, 1]. 1 == the declared density.

    Three kinds, and a rock species must name exactly one:

      slope   p = 1 inside `slope_deg`, 0 outside.        CLIFF faces.
      talus   p = 1 - exp(-deposit / saturation), gated
              by `slope_deg`.                             TALUS fans.
      layer   p = the BAKED weightmap channel for `layer`,
              gated by `slope_deg`, minus any cell the
              talus field already claims.                 HERO boulders.

    `layer` reads the BAKE and never re-derives the recipe's bands —
    schema v1.6 normative, and the two disagree by ~115 m of feathering
    on this world.
    """
    m = spec["mask"]
    kind = m["kind"]
    slope, height, dep = ctx["slope"], ctx["height_m"], ctx["deposit"]

    lo, hi = [float(v) for v in m["slope_deg"]]
    p = ((slope >= lo) & (slope <= hi)).astype(np.float64)

    if kind not in MASK_KINDS:
        raise ValueError("unknown mask kind {0!r}; MASK_KINDS is {1}"
                         .format(kind, list(MASK_KINDS)))

    if kind == "slope":
        pass
    elif kind == "talus":
        sat = float(m["saturation"])
        p = p * (1.0 - np.exp(-dep / sat))
    elif kind == "layer":
        # REMAINDER-AWARE, through the material builder's mask_plan (NN24:
        # the density a rock is placed at must come from the same channel
        # the shader blends). Layers 0..direct-1 are stored channels; when
        # the material declares more layers than the weightmap stores, the
        # LAST layer is the shader remainder 1-(sum of stored) and has no
        # channel of its own. Mirrors place_foliage._layer_weight.
        # Imported HERE, not at module top: make_landscape_material imports
        # import_heightmap, which imports this module for ROLES/MAX_LOD_DEPTH,
        # so a top-level import is a circular-import crash at validator
        # start (measured 2026-09-26). One contract, one definition; the
        # import site is just late.
        from make_landscape_material import mask_plan
        chan = ctx["layer_index"][m["layer"]]
        direct, _has_rem = mask_plan(len(ctx["layer_index"]))
        w = ctx["weights"]
        if chan < direct:
            p = p * w[..., chan]
        else:
            # Clipped: 8-bit quantisation lets the stored channels sum a
            # hair past 1.0, which would read as a NEGATIVE density.
            p = p * np.clip(1.0 - w[..., :direct].sum(axis=-1), 0.0, 1.0)
        ex = m.get("exclude_talus_above")
        if ex is not None:
            sat = float(ctx["talus_saturation"])
            p = p * ((1.0 - np.exp(-dep / sat)) < float(ex))
    else:
        raise ValueError("unknown mask kind {0!r}".format(kind))

    h_lo, h_hi = [float(v) for v in spec["height_m"]]
    return p * ((height >= h_lo) & (height <= h_hi))


# ---------------------------------------------------------------------
# THE ROTATION GATE
# ---------------------------------------------------------------------
def rotation_gate(yaw, pitch, roll, slope_at_instance, align, tumble_deg,
                  name):
    """Refuse a plan whose rotation channels are transposed.

    WHY THIS EXISTS AND WHY IT IS NOT OPTIONAL.
    R4's verification is "max instance tilt <= 4 degrees, measured over
    ALL instances". That single number is the ONLY thing standing between
    this project and the defect that laid the entire forest down —
    `Rotator(_r[4], _r[3], _r[5])` fed a 0-360 random yaw into PITCH and
    97.6% of trees tilted past 4 degrees, median tilt 90.

    Rocks LEGITIMATELY tilt to 50 degrees. Adding them therefore destroys
    that gate's discriminating power unless it is replaced, and a scatter
    extension that quietly removes the project's only defence against a
    known catastrophic defect is worse than no extension. This is the
    replacement, and it is strictly stronger, because it checks BOTH
    channels rather than one:

      TILT BOUND     |pitch| and |roll| cannot exceed what the declared
                     alignment against the MEASURED slope at each accepted
                     instance can produce, plus the tumble. If yaw were
                     written into pitch, pitch would reach 360 and this
                     fires immediately.
      YAW UNIFORMITY yaw must actually be uniform on [0, 360). If pitch
                     were written into yaw, yaw would be bounded by the
                     tilt limit and this fires instead.

    Neither check alone covers both directions. Together they make the
    transposition unrepresentable in a passing plan.

    Returns (ok, [reasons], [notes]). `notes` carries non-failing
    disclosures — e.g. the small-n yaw-uniformity skip (Pass 3
    2026-09-16 F3) — which the caller MUST surface (rule 13) but which
    do not fail the gate.
    """
    reasons = []
    yaw_uniformity_skipped = []
    n = int(np.size(yaw))
    if n == 0:
        return True, [], []

    # `align` blends the NORMAL, so the achieved tilt from vertical is
    # atan(align * tan(slope)) -- bounded above by the slope itself.
    bound = np.degrees(np.arctan(align * np.tan(np.radians(
        np.minimum(slope_at_instance, 89.0))))) + float(tumble_deg) + 1e-6
    over_p = int(np.count_nonzero(np.abs(pitch) > bound))
    over_r = int(np.count_nonzero(np.abs(roll) > bound))
    if over_p:
        reasons.append(
            "{0}: {1} of {2} instances have |pitch| above the alignment "
            "bound (max |pitch| {3:.2f} deg, max bound {4:.2f} deg). A "
            "0-360 channel has been written into PITCH."
            .format(name, over_p, n, float(np.abs(pitch).max()),
                    float(bound.max())))
    if over_r:
        reasons.append(
            "{0}: {1} of {2} instances have |roll| above the alignment "
            "bound (max |roll| {3:.2f} deg, max bound {4:.2f} deg)."
            .format(name, over_r, n, float(np.abs(roll).max()),
                    float(bound.max())))

    if float(yaw.min()) < 0.0 or float(yaw.max()) >= 360.0:
        reasons.append("{0}: yaw outside [0, 360): {1:.3f}..{2:.3f}"
                       .format(name, float(yaw.min()), float(yaw.max())))
    # THE UNIFORMITY HALF ONLY RUNS AT n >= 1000 (span and mean need a
    # populated 0-360). Below that, yaw is checked ONLY for range, which
    # any bounded tilt channel satisfies — so the pitch-into-yaw
    # transposition passes for small species (e.g. CliffFace, 84). The
    # SKIP IS REPORTED, never silent (rule 13: a check that did not run
    # must not read as agreement); the self_test uses n=5000 and cannot
    # see this branch, which is why the gap survived (Pass 3 2026-09-16 F3).
    if n >= 1000:
        if float(yaw.max()) < 359.0 or float(yaw.min()) > 1.0:
            reasons.append(
                "{0}: yaw spans only {1:.2f}..{2:.2f} over {3} instances; "
                "it is not the uniform 0-360 channel it must be. A bounded "
                "tilt channel has been written into YAW."
                .format(name, float(yaw.min()), float(yaw.max()), n))
        if abs(float(yaw.mean()) - 180.0) > 9.0:
            reasons.append(
                "{0}: yaw mean {1:.2f} deg, expected 180 +/- 9 over {2} "
                "uniform samples".format(name, float(yaw.mean()), n))
    else:
        yaw_uniformity_skipped.append(
            "%s: yaw uniformity SKIPPED (n=%d < 1000) — only the [0,360) "
            "range was checked; a pitch-into-yaw transposition would NOT "
            "be caught for this species" % (name, n))
    return (not reasons), reasons, yaw_uniformity_skipped


# ---------------------------------------------------------------------
# COST MODEL
# ---------------------------------------------------------------------
def lod_chain(lod0_tris, depth):
    """Triangle count per LOD. `depth` is a COUNT, not a deepest index.

    IT WAS BOTH, AND THAT WAS THE BUG. This read `range(depth + 1)` --
    treating `depth` as the deepest LOD INDEX -- while its only caller
    defaulted to 3 (meaning "LOD0..LOD3", a 4-long chain) and the recipe
    validator documented `lod_depth` as "the MEASURED LOD count of the
    mesh". `measure_rock_meshes.py` writes `lod_count`, and the measured
    value for every KiteDemo rock is 4. So the first real run indexed
    LOD_PERCENT[4] on a 4-tuple and died with `IndexError: tuple index
    out of range`, eight minutes into a plan.

    The two spellings were never reconciled because the default (3) and
    the measurement (4) differ by exactly the off-by-one, so the code
    worked for as long as nobody supplied the measured number. This is
    the project's own casualty pattern -- `ReductionSettings[0]` IS
    LOD 0 -- recurring in a tool that was written after the lesson.

    COUNT everywhere now: `lod_depth: 4` means LOD0, LOD1, LOD2, LOD3.
    """
    depth = int(depth)
    if depth < 1:
        raise ValueError(
            "lod_chain: depth is a COUNT and must be >= 1, got {0!r}"
            .format(depth))
    if depth > MAX_LOD_DEPTH:
        raise ValueError(
            "lod_chain: depth {0} exceeds the cost model, which has "
            "{1} entries in LOD_PERCENT/LOD_SCREEN. Costing a {0}-LOD "
            "mesh would silently drop its deepest LOD(s) and UNDERSTATE "
            "the triangle load. Extend both tables deliberately, and "
            "re-validate against R5's locked budget rows, before "
            "admitting a longer chain.".format(depth, MAX_LOD_DEPTH))
    return [int(round(lod0_tris * LOD_PERCENT[i])) for i in range(depth)]


def screen_constant(dims_m, scale):
    """C, such that screen_size = C / distance_m."""
    r = 0.5 * math.sqrt(sum(float(d) * float(d) for d in dims_m))
    return 2.0 * r * float(scale) / math.tan(math.radians(FOV_DEG / 2.0))


def triangles_in_view(per_ha, cull_m, lods, C, screens=None):
    """Triangles submitted, PROJECT CONVENTION: a full 360-degree disc.

    This is the convention every locked number in this project is stated
    in — R5's budget table, and R11's 94,248 grass instances
    (= pi * 50^2 * 12/m2). It over-counts a real 75-degree frustum by
    360/75 = 4.8x. It is used UNCHANGED so results are comparable to
    39.6M and to the 40M working target rather than merely optimistic.
    """
    d = float(per_ha) / 1e4
    # `screens` are the mesh's ACTUAL LOD screen sizes when known. The
    # module constant is R5's GENERATED chain and is only correct for the
    # meshes that chain was solved for.
    src = list(screens) if screens else list(LOD_SCREEN)
    radii = [C / s for s in src[1:len(lods)]] + [float("inf")]
    total, r_in = 0.0, 0.0
    for i, t in enumerate(lods):
        r_out = min(radii[i], float(cull_m))
        if r_out > r_in:
            total += d * math.pi * (r_out * r_out - r_in * r_in) * t
        r_in = max(r_in, r_out)
        if r_in >= float(cull_m):
            break
    return total


# ---------------------------------------------------------------------
# MEASURED MESH SIZE
# ---------------------------------------------------------------------
def measured_pivot(path, registry):
    """(pivot_offset_xy_m, base_offset_z_m) or None if unmeasured.

    WHY THIS IS NOT OPTIONAL, AND WHY IT IS NOT THE PLANT RULE.

    Every mesh this project has instanced so far went through
    `blender/normalize_asset.py` to a BASE-CENTRE pivot, and
    `place_foliage.py`'s ruling-(c) gate (place_foliage.py's ruling-(c) gate (grep 'ruling (c)'))
    enforces <=1.0 m horizontal / <=0.25 m vertical against that. The
    KiteDemo rocks are BRANCH 2 native Fab `.uasset`s. They never went
    through Blender, and R-ASSET forbids authoring into a Fab folder, so
    they never can. Their pivots are whatever the vendor set and this
    project has NOT measured them — `ApproxSize` in the asset registry is
    a bounding-box SIZE, not an origin.

    Two consequences, and they pull in opposite directions:

      * If a rock's pivot is at its CENTRE (common for props), the
        existing vertical gate sees base_offset_z_m = -height/2 — up to
        -1.9 m on SM_MountainRock_Closed — and REFUSES the whole run.
      * Relaxing that gate is not acceptable either: it is the check that
        caught the fir at 12.406 m from its own geometry.

    So the pivot is CORRECTED rather than gated. The measured base offset
    is added back before the embed depth is subtracted, which puts the
    rock's base on the terrain no matter where the vendor put the origin,
    and the horizontal gate stays — scaled to the mesh, because 1.0 m is
    a large error on a 1.5 m boulder and a small one on a 6.7 m one.

    Absent measurement is reported as ABSENT MEASUREMENT, never as zero.
    """
    if not registry:
        return None
    row = registry.get(path)
    if not isinstance(row, dict):
        return None
    try:
        return (float(row["pivot_offset_xy_m"]), float(row["base_offset_z_m"]))
    except (KeyError, TypeError, ValueError):
        return None


def load_pivot_registry():
    p = os.path.join(MEASURED_DIR, "rock_pivots.json")
    if not os.path.isfile(p):
        return None, p
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh), p


def live_lods_and_materials(registry, path):
    """(lod_count, material_slots) as MEASURED on the loaded asset.

    NOT from the Fab registry. Measured 2026-08-03: the registry's
    `Materials` tag disagrees with the live asset on 8 of the 13 pass-3
    rocks -- `Scree_001_A` claims 12 slots where the loaded mesh reports
    1, across three independent accessors (`static_materials`, a
    `get_material` walk, and `get_num_sections`). StaticMesh.cpp:6319
    writes `GetStaticMaterials().Num()` into that tag, so the tag MEANS
    slots; the cached value is simply stale. Registry TRIANGLES, by
    contrast, matched live exactly on every mesh spot-checked, which is
    why `measured_mesh()` still sources those from it.

    Refuses rather than defaulting. A draw-call budget computed from a
    number that is wrong by 12x is not conservative in a useful
    direction, and a LOD count that is wrong by one indexes off the end
    of the cost model -- which is exactly how this function came to
    exist.
    """
    row = (registry or {}).get(path)
    if not isinstance(row, dict):
        raise ValueError(
            "COULD NOT MEASURE LODs/materials for {0}: no row in "
            "rock_pivots.json. Run `python scripts/measure_rock_meshes.py`."
            .format(path))
    lc, ms = row.get("lod_count"), row.get("material_slots")
    tris, screens = row.get("lod_triangles"), row.get("lod_screen_sizes")
    missing = [n for n, v in (("lod_count", lc), ("material_slots", ms),
                              ("lod_triangles", tris),
                              ("lod_screen_sizes", screens)) if v is None]
    if missing:
        raise ValueError(
            "{0} has a measured row whose {1} came back null. A null is a "
            "FAILED MEASUREMENT and must not be read as a value "
            "(non-negotiable 6); re-measure that mesh with `python "
            "scripts/measure_rock_meshes.py --only <id>`."
            .format(path, ", ".join(missing)))
    tris, screens = [int(t) for t in tris], [float(s) for s in screens]
    if len(tris) != int(lc) or len(screens) < int(lc):
        raise ValueError(
            "{0}: lod_count={1} but {2} triangle counts and {3} screen "
            "sizes were measured. These describe one chain and must agree; "
            "a mismatch means the measurement is stale relative to the "
            "asset.".format(path, lc, len(tris), len(screens)))
    return int(lc), int(ms), tris, screens[:int(lc)]


def measured_mesh(path):
    """(dims_m, lod0_triangles, n_materials) from a MEASURED registry.

    Refuses rather than guessing. A vendor's published extent is not a
    measurement (R3 REJECTED: `grass_medium_01` reads 7.3 m for a 0.327 m
    tuft, a 22x error), and an embed depth or a screen-size constant
    computed from an assumed size is a confident wrong number.
    """
    for f in sorted(glob.glob(os.path.join(MEASURED_DIR,
                                           "fab_registry_*.json"))):
        with open(f, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        for a in doc.get("assets") or []:
            if a.get("class") != "StaticMesh" or a.get("path") != path:
                continue
            size = a.get("ApproxSize")
            tri = a.get("Triangles")
            mats = a.get("Materials")
            if not size or not tri:
                raise ValueError(
                    "COULD NOT MEASURE {0}: it is in {1} but carries no "
                    "ApproxSize/Triangles tag. Not an absent mesh — an "
                    "unreadable one.".format(path, os.path.basename(f)))
            dims = [float(v) / 100.0 for v in str(size).split("x")]
            return dims, int(tri), int(mats or 0)
    raise ValueError(
        "COULD NOT MEASURE {0}: no fab_registry_*.json in {1} records it. "
        "Run scripts/audit_fab_registry.py for its pack first; do not "
        "substitute a vendor figure.".format(path, MEASURED_DIR))


# ---------------------------------------------------------------------
# PLAN
# ---------------------------------------------------------------------
def build_context(recipe, height_m, weights, spacing_m, rs, pivot=None):
    gy, gx = np.gradient(height_m, spacing_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    # Cliff SOURCES and the ROUTER read the landform (one smoothing,
    # landform_height); transmission reads the real surface. See
    # landform_slope() / landform_height() for why, and the measurements.
    lf = landform_height(height_m, spacing_m, rs["source_smooth_m"])
    _lgy, _lgx = np.gradient(lf, spacing_m)
    src_slope = np.degrees(np.arctan(np.hypot(_lgx, _lgy)))
    del _lgx, _lgy
    dep, n_src, steps = talus_deposit(
        height_m, slope, spacing_m,
        repose_deg=rs["repose_deg"],
        cliff_source_slope_deg=rs["cliff_source_slope_deg"],
        runout_m=rs["runout_m"],
        mfd_exponent=rs["mfd_exponent"],
        max_steps=rs["max_steps"],
        source_slope_deg=src_slope,
        route_height_m=lf)
    del lf
    layers = [l["name"] for l in recipe["material"]["layers"]]
    return {
        "gx": gx, "gy": gy, "slope": slope, "height_m": height_m,
        "deposit": dep, "weights": weights,
        "layer_index": {nm: i for i, nm in enumerate(layers)},
        "talus_saturation": rs["saturation"],
        "cliff_source_cells": n_src, "routing_steps": steps,
        "spacing_m": spacing_m, "pivot": pivot or {},
    }


def _bias(spec, key):
    """A placement-prior knob as a float, or REFUSE.

    Absent is 0.0 — a prior nobody asked for. Anything present but not a
    finite number raises, because `float("lots")` would otherwise turn an
    invalid recipe into a traceback at whatever line happened to touch it
    first.
    """
    v = spec.get(key, 0.0)
    if v is None:
        return 0.0
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(
            "species {0!r} has {1}={2!r}; it must be a number in [-1, 1]"
            .format(spec.get("name"), key, v))
    v = float(v)
    if not math.isfinite(v):
        raise ValueError(
            "species {0!r} has a non-finite {1}".format(spec.get("name"), key))
    return v


def plan_species(spec, ctx, origin_m, seed, index):
    """Instance transforms for one rock species."""
    rng = np.random.default_rng(int(seed) + 104729 * (index + 1))
    n = ctx["height_m"].shape[0]
    spacing_m = ctx["spacing_m"]
    span_m = (n - 1) * spacing_m

    p_field = role_mask(spec, ctx)
    per_ha = float(spec["density_per_hectare_on_mask"])

    # Jittered grid at the ON-MASK density across the WHOLE map, then
    # accepted with probability p. Uniform random points clump and leave
    # holes at the same density; one candidate per cell, jittered inside
    # it, gives even coverage with no visible lattice. Same construction
    # as place_foliage.plan(), deliberately.
    cell_m = math.sqrt(10000.0 / per_ha)
    cells = max(int(math.floor(span_m / cell_m)), 1)
    cx, cy = np.meshgrid(np.arange(cells), np.arange(cells))
    jx = (cx.ravel() + rng.random(cells * cells)) * (span_m / cells)
    jy = (cy.ravel() + rng.random(cells * cells)) * (span_m / cells)

    gxi, gyi = jx / spacing_m, jy / spacing_m
    p = _bilinear(p_field, gxi, gyi)

    # ---- SHARED PLACEMENT PRIORS ------------------------------------
    # Pass 5's ruled density philosophy: clutter "gathers under trees,
    # along drainage, and at cliff bases". Cliff bases are the `talus`
    # mask kind above; these two are the other two, and BOTH come from
    # `placement_priors` so the rock path and the vegetation path cannot
    # follow different drainage or different forests (non-negotiable 19).
    fbias = _bias(spec, "flow_bias")
    if fbias != 0.0:
        flow = ctx.get("flow")
        # Refusal, not a silent skip: a declared bias with no field is a
        # no-op that reads in the log as if it applied.
        if flow is None:
            raise ValueError(
                "species {0!r} declares flow_bias {1} but the flow map is "
                "{2}. Refusing: a bias that silently does nothing is the "
                "defect class place_foliage.py's silent-bias lesson (grep the bias comment) records."
                .format(spec.get("name"), fbias, ctx.get("flow_status")))
        f = _bilinear(flow, gxi, gyi)
        # Reference is the WHOLE FIELD's mean — "average wetness of the
        # map" — matching place_foliage exactly.
        p = p * placement_priors.centred_bias(f, fbias, flow.mean())

    cbias = _bias(spec, "canopy_bias")
    if cbias != 0.0:
        txy, tsc = ctx.get("trunk_xy"), ctx.get("trunk_scale")
        if txy is None:
            raise ValueError(
                "species {0!r} declares canopy_bias {1} but no canopy "
                "source was loaded. `foliage.canopy` must declare the "
                "plan and radius_m.".format(spec.get("name"), cbias))
        # PER CANDIDATE against the real trunks, not a rasterised field:
        # the map grid is 4.0 m and the measured canopy radius is 3.07 m,
        # so a raster cannot express "under this tree" at all. See
        # placement_priors.canopy_occupancy.
        occ = placement_priors.canopy_occupancy(
            np.column_stack((jx, jy)), txy, tsc, ctx["canopy_radius_m"])
        # Reference is the CANDIDATE mean, which is an unbiased estimate
        # of the map-wide mean because candidates are a uniform jittered
        # grid over the whole span.
        p = p * placement_priors.centred_bias(occ, cbias, occ.mean())

    keep = rng.random(p.size) < np.clip(p, 0.0, 1.0)

    kx, ky = jx[keep], jy[keep]
    gxk, gyk = kx / spacing_m, ky / spacing_m
    kz = _bilinear(ctx["height_m"], gxk, gyk)
    sgx = _bilinear(ctx["gx"], gxk, gyk)
    sgy = _bilinear(ctx["gy"], gxk, gyk)
    slope_k = np.degrees(np.arctan(np.hypot(sgx, sgy)))

    scale = (rng.random(kx.size)
             * (float(spec["scale_range"][1]) - float(spec["scale_range"][0]))
             + float(spec["scale_range"][0]))

    align = float(spec["align_to_normal"])
    yaw = rng.random(kx.size) * 360.0
    nvec = blended_normal(sgx, sgy, align)
    pitch, roll = orient_to_normal(nvec[..., 0], nvec[..., 1], nvec[..., 2],
                                   yaw)
    tumble = float(spec.get("tumble_deg", 0.0) or 0.0)
    if tumble > 0.0:
        # TUMBLE GOES INTO PITCH AND ROLL ONLY. It is a separate key from
        # anything yaw-shaped precisely so that no future edit can route a
        # 0-360 channel into a tilt channel by renaming a variable.
        pitch = pitch + (rng.random(kx.size) * 2.0 - 1.0) * tumble
        roll = roll + (rng.random(kx.size) * 2.0 - 1.0) * tumble

    # EMBED. A rock resting exactly on the sampled surface reads as
    # pasted on, and the sample is not the surface anyway: the heightmap
    # is a 4 m grid and a 48-degree face drops 4.4 m across one cell, so
    # bilinear interpolation is decimetres out between vertices. Sinking
    # the instance by a fraction of its own height is both the art
    # direction and the tolerance for that error.
    #
    # ALONG THE INSTANCE'S BLENDED UP-AXIS, NOT ALONG WORLD -Z (Pass 3
    # 2026-09-16 F7): nvec = blended_normal(align), which equals the
    # SURFACE NORMAL only at align=1.0 — no live rock declares that
    # (alpine.json: 0.2..0.92; CliffFace 0.4). On flat ground world-Z
    # and the normal coincide, so the distinction is easy to miss. On a
    # 48-degree face a pure world-Z push of d would sink only d*cos(48)
    # = 0.67d and slide 0.74d downhill; embedding along the blended
    # up-axis removes that error IN PROPORTION TO align (fully only at
    # align=1). The displacement is systematic, not noisy, so it reads
    # as a style rather than a bug — verify_grounding.py had to discover
    # the nvec.z dependence empirically.
    dims_m, lod0, n_mats = measured_mesh(spec["mesh"])
    embed = float(spec.get("embed_frac", 0.0) or 0.0)
    depth_m = embed * float(dims_m[2]) * scale

    # PIVOT CORRECTION. `base_offset_z_m` is (bounds.origin.z -
    # bounds.box_extent.z) in metres — 0 for a base-centre pivot, -h/2
    # for a centred one. Adding it back puts the mesh's LOWEST point on
    # the sampled surface whatever the vendor chose, and only then is the
    # embed depth subtracted. Without it a centre-pivoted rock floats by
    # half its own height and the symptom reads as a placement bug — the
    # exact misdiagnosis the 12.406 m fir produced.
    pv = ctx.get("pivot", {}).get(spec["mesh"])
    lift_m = 0.0 if pv is None else -float(pv[1]) * scale
    ex = kx - depth_m * nvec[..., 0]
    ey = ky - depth_m * nvec[..., 1]
    z_m = kz + lift_m - depth_m * nvec[..., 2]

    return {
        "spec": spec, "dims_m": dims_m, "lod0_tris": lod0,
        "n_materials": n_mats,
        # The measured base offset this plan corrected by, UNSCALED, so
        # the payload can compare it against what the engine reports for
        # the asset. Written into the plan file as
        # `pivot_base_offset_m` -- see the writer for why declaring it
        # is a stronger gate than passing the normalisation limit.
        "base_z_m": 0.0 if pv is None else float(pv[1]),
        "xyz": np.stack([(ex + origin_m[0]) * 100.0,
                         (ey + origin_m[1]) * 100.0,
                         z_m * 100.0], axis=1),
        "embed_m": depth_m,
        "yaw": yaw, "pitch": pitch, "roll": roll, "scale": scale,
        "slope_at": slope_k, "candidates": int(p.size),
        "mask_ha": float((p_field > 0).sum()) * (spacing_m ** 2) / 1e4,
        "mask_ha_full": float(p_field.sum()) * (spacing_m ** 2) / 1e4,
    }


def load_rock_exclusions(recipe):
    """The town + water footprints a rock plan must clear, loaded ONCE.

    Returns a dict: shapes/plaza (town), water (WaterMask), the declared
    blocks (for provenance), a description line each, and `error` when a
    DECLARED exclusion cannot be loaded. Mirrors place_foliage.load_exclusion
    and load_water_exclusion without importing place_foliage (it imports
    this module; a circular import is not a shared definition). The two
    lookups themselves ARE shared: town_exclusion.inside and
    plan_encounters.WaterMask.inside, the same code the trees and the
    encounters placer run (NN24).
    """
    out = {"shapes": None, "plaza": None, "margins": None, "settlement": None,
           "water": None, "water_decl": None, "error": None,
           "settlement_desc": "NOT DECLARED for this recipe",
           "water_desc": "NOT DECLARED for this recipe"}
    fol = recipe.get("foliage") or {}
    decl = fol.get("settlement_exclusion")
    if decl:
        rel = decl.get("from_city_plan")
        if not rel:
            out["error"] = "foliage.settlement_exclusion declares no from_city_plan."
            return out
        abs_path = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(abs_path):
            out["error"] = ("foliage.settlement_exclusion names %s, which does "
                            "not exist. Nothing planned -- the town footprint "
                            "is unknown." % rel)
            return out
        import town_exclusion  # noqa: E402 -- the ONE town lookup
        try:
            shapes, plaza, margins = town_exclusion.load(abs_path)
        except RuntimeError as exc:
            out["error"] = str(exc)
            return out
        out.update({"shapes": shapes, "plaza": plaza, "margins": margins,
                    "settlement": decl, "_town_inside": town_exclusion.inside})
        out["settlement_desc"] = (
            "{0} rectangles + {1}, margins building {2:.1f} m / street {3:.1f} m "
            "/ plaza {4:.1f} m ({5})".format(
                len(shapes), "a plaza disc" if plaza else "NO plaza disc",
                margins[0], margins[1], margins[2], rel))
    wdecl = fol.get("water_exclusion")
    if wdecl:
        rel = wdecl.get("exclusion_mask")
        if not rel:
            out["error"] = "foliage.water_exclusion declares no exclusion_mask."
            return out
        abs_path = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(abs_path):
            out["error"] = ("foliage.water_exclusion names %s, which does not "
                            "exist. Nothing planned -- the water footprint is "
                            "unknown." % rel)
            return out
        try:
            from plan_encounters import WaterMask  # the ONE water lookup
            wm = WaterMask(abs_path)
        except Exception as exc:                   # noqa: BLE001 -- report it
            out["error"] = ("could not load the water mask %s: %s: %s"
                            % (rel, type(exc).__name__, exc))
            return out
        out.update({"water": wm, "water_decl": wdecl})
        out["water_desc"] = "%s (%d x %d cells, %d water cells)" % (
            rel, wm.nrow, wm.ncol, int(wm.mask.sum()))
    return out


def apply_rock_exclusions(pl, excl):
    """Drop finished rows inside the town or the water; RNG untouched.

    A POST-FILTER on built rows, like place_foliage's: every surviving
    instance keeps the exact transform it had, so this cannot re-roll the
    plan. Filters every per-instance array in the plan dict together and
    records the removed counts on the plan for the report and the
    provenance block.
    """
    n = len(pl["xyz"])
    keep = np.ones(n, dtype=bool)
    rem_s = rem_w = 0
    if n:
        xs = pl["xyz"][:, 0]
        ys = pl["xyz"][:, 1]
        if excl.get("shapes") is not None:
            inside = excl["_town_inside"]
            hit = np.fromiter((inside(excl["shapes"], excl["plaza"],
                                      float(x), float(y))
                               for x, y in zip(xs, ys)), dtype=bool, count=n)
            rem_s = int(hit.sum())
            keep &= ~hit
        if excl.get("water") is not None:
            wm = excl["water"]
            hit = np.fromiter((wm.inside(float(x), float(y))
                               for x, y in zip(xs, ys)), dtype=bool, count=n)
            rem_w = int((hit & keep).sum())
            keep &= ~hit
    for k in ("xyz", "embed_m", "yaw", "pitch", "roll", "scale", "slope_at"):
        pl[k] = pl[k][keep]
    pl["removed_settlement"] = rem_s
    pl["removed_water"] = rem_w
    return pl


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


# ---------------------------------------------------------------------
# SELF-TEST: prove the gate REFUSES, not merely that it accepts
# ---------------------------------------------------------------------
def self_test():
    """Run the rotation gate against the historical defect. Returns exit code.

    CLAUDE.md non-negotiable 2: a gate that has only ever seen good input
    has not been tested. Both transposition directions are exercised.
    """
    rng = np.random.default_rng(1)
    n = 5000
    slope = rng.random(n) * 50.0
    align, tumble = 1.0, 6.0
    gx = np.tan(np.radians(slope)) * np.cos(rng.random(n) * 2 * np.pi)
    gy = np.tan(np.radians(slope)) * np.sin(rng.random(n) * 2 * np.pi)
    yaw = rng.random(n) * 360.0
    nv = blended_normal(gx, gy, align)
    pitch, roll = orient_to_normal(nv[..., 0], nv[..., 1], nv[..., 2], yaw)
    slope_k = np.degrees(np.arctan(np.hypot(gx, gy)))

    cases = [
        ("GOOD  correctly built plan", yaw, pitch, roll, True),
        ("BAD   yaw written into PITCH (the 2026-08-02 defect)",
         pitch, yaw, roll, False),
        ("BAD   yaw written into ROLL", pitch, roll, yaw, False),
        ("BAD   pitch written into YAW (bounded tilt in a 0-360 slot)",
         np.abs(pitch), pitch, roll, False),
    ]
    fails = 0
    print("--- rotation gate, BOTH DIRECTIONS ---")
    for label, y_, p_, r_, want_ok in cases:
        ok, why, _notes = rotation_gate(y_, p_, r_, slope_k, align,
                                        tumble, "selftest")
        verdict = "ACCEPT" if ok else "REFUSE"
        good = (ok == want_ok)
        fails += 0 if good else 1
        print("  [{0}] {1:<52} -> {2}".format("ok" if good else "XX",
                                              label, verdict))
        if not ok:
            for w in why:
                print("           {0}".format(w[:110]))
    # and the orientation solver against the engine's own matrix
    print("")
    print("--- orientation solver vs the UE 5.8 rotation matrix ---")
    P, Y, R = np.radians(pitch), np.radians(yaw), np.radians(roll)
    SP, CP = np.sin(P), np.cos(P)
    SY, CY = np.sin(Y), np.cos(Y)
    SR, CR = np.sin(R), np.cos(R)
    # RotationTranslationMatrix.h:82-84, row 2 = the object's local +Z
    up = np.stack([-(CR * SP * CY + SR * SY),
                   CY * SR - CR * SP * SY,
                   CR * CP], axis=-1)
    err = np.degrees(np.arccos(np.clip((up * nv).sum(axis=-1), -1, 1)))
    print("  worst up-vector error over {0} cases: {1:.3e} deg".format(
        n, float(err.max())))
    if float(err.max()) > 1e-4:
        print("  XX solver does not reproduce the engine formula")
        fails += 1
    print("")
    print("SELF-TEST {0}".format("PASSED" if fails == 0 else
                                 "FAILED ({0})".format(fails)))
    return 0 if fails == 0 else 4


# ---------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe",
                    default=os.path.join(REPO_ROOT, "recipes", "alpine.json"))
    ap.add_argument("--write", action="store_true",
                    help="Write foliage/<biome>_<Name>.json and the talus "
                         "debug map. Without it the run reports and writes "
                         "nothing.")
    ap.add_argument("--max-instances", type=int, default=MAX_INSTANCES)
    ap.add_argument("--other-instances", type=int, default=0,
                    help="Instances the rest of the recipe already needs, "
                         "charged against the same ceiling because they "
                         "are. MEASURE it: sum the `count` fields of the "
                         "live foliage/<biome>_*.json plans (185,385 on "
                         "2026-09-26 for alpine_8k); at the default 0 the "
                         "shared ceiling checks nothing.")
    ap.add_argument("--self-test", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    if args.self_test:
        return self_test()

    from PIL import Image

    recipe_path = os.path.abspath(args.recipe)
    if not _inside_repo(recipe_path):
        print("REFUSE: recipe must be inside {0}".format(REPO_ROOT))
        return 1
    # A MISSING/UNPARSEABLE input is REFUSE exit 2, not a traceback exit
    # 1 (Pass 3 2026-09-16 F2): the exit table promises 2 for "recipe,
    # heightmap, weightmap or registry missing or invalid", and a caller
    # branching on the code must not see these as "unexpected error".
    try:
        with open(recipe_path, "r", encoding="utf-8") as fh:
            recipe = json.load(fh)
    except (OSError, ValueError) as exc:
        print("REFUSE: recipe %s is missing or unreadable: %s"
              % (recipe_path, exc))
        return 2

    fol = recipe.get("foliage") or {}
    rs = fol.get("rock_scatter")
    if not isinstance(rs, dict):
        print("REFUSE: recipe declares no `foliage.rock_scatter` block "
              "(schema v1.12). Nothing to plan.")
        return 2
    # FAIL CLOSED ON AN UNRECOGNISED ROLE (non-negotiable 1).
    # The presence of a `role` KEY is what marks a species as a rock —
    # `place_foliage.py (grep: the `role` discriminator)` uses the same discriminator — so a
    # vegetation species (no key) must be skipped silently, while a rock
    # species whose role VALUE we do not know must REFUSE. Before
    # 2026-08-08 both fell out of the same `in ROLES` filter and the
    # second case was dropped without a word: the recipe would declare a
    # species, preflight would pass it, and the plan would report success
    # having never planned it. Distinguish the two cases.
    _unknown = [(s.get("name") or "<unnamed>", s.get("role"))
                for s in fol.get("species") or []
                if "role" in s and s.get("role") not in ROLES]
    if _unknown:
        print("REFUSE: species declare a `role` this planner does not "
              "know: {0}. Valid roles are {1}. A rock species is "
              "identified by HAVING a `role` key, so an unknown value "
              "cannot be treated as vegetation and skipped — it would "
              "vanish from the plan silently."
              .format(_unknown, list(ROLES)))
        return 2

    specs = [s for s in fol.get("species") or [] if s.get("role") in ROLES]
    if not specs:
        print("REFUSE: no species carries a `role` in {0}".format(ROLES))
        return 2

    ls, hm = recipe["landscape"], recipe["heightmap"]
    src = os.path.join(REPO_ROOT, hm["source"])
    if not _inside_repo(src):
        print("REFUSE: heightmap escapes REPO_ROOT")
        return 2
    try:
        arr = np.asarray(Image.open(src)).astype(np.float64)
    except OSError as exc:
        print("REFUSE: heightmap %s missing/unreadable: %s" % (src, exc))
        return 2
    n = arr.shape[0]
    z_scale_cm = float(ls["z_scale_cm"])
    span_cm = (float(hm["resolution"]) - 1.0) * float(ls["scale_xy_cm"])
    spacing_m = (span_cm / max(n - 1.0, 1.0)) / 100.0
    height_m = (arr / 65535.0) * (z_scale_cm / 100.0)

    # THE PLACEMENT FIELD, not necessarily the RENDER weightmap -- the same
    # contract place_foliage.load_inputs follows (schema v1.17): when the
    # recipe declares `foliage.planting_field`, a `layer` mask samples that
    # canopy-free field, because the render weightmap's forest_floor channel
    # is canopy splatted from the PLACED trees and the Grass remainder shrinks
    # under them. A hero boulder keyed to Grass would otherwise be pushed out
    # from under every tree by the trees themselves. Absent -> render
    # weightmap, the prior behaviour.
    _pf_rel = fol.get("planting_field")
    _w_rel = _pf_rel or recipe["material"]["weightmap"]
    wpath = os.path.join(REPO_ROOT, _w_rel)
    # FOUR STORED CHANNELS PLUS THE SHADER REMAINDER. This read was "RGB"
    # while alpine_8k.json declares FIVE layers (Snow/Rock/Scree/ForestFloor
    # + Grass), so a Boulder keyed to `Grass` indexed channel 4 of a
    # 3-channel array -- the exact `index 4 is out of bounds` place_foliage
    # hit on 2026-09-12 (its load_inputs comment). Read RGBA; role_mask
    # resolves the remainder through the material builder's own mask_plan.
    try:
        weights = (np.asarray(Image.open(wpath).convert("RGBA"))
                   .astype(np.float64) / 255.0)
    except OSError as exc:
        print("REFUSE: weightmap %s missing/unreadable: %s" % (wpath, exc))
        return 2
    if weights.shape[0] != n:
        print("REFUSE: weightmap is {0}, heightmap is {1}".format(
            weights.shape[0], n))
        return 2
    print("placement field: {0}  ({1})".format(
        _w_rel, "planting field -- canopy-free"
        if _pf_rel else "render weightmap (no foliage.planting_field)"))

    origin_m = (float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0)
    span_m = (n - 1) * spacing_m
    hectares = (span_m / 100.0) ** 2
    cell_ha = (spacing_m ** 2) / 1e4

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("map       : {0} x {0}, {1:.0f} m span = {2:.0f} ha, {3:.1f} m grid"
          .format(n, span_m, hectares, spacing_m))
    print("")

    # ---- PIVOT MEASUREMENT, before anything is planned ---------------
    reg, reg_path = load_pivot_registry()
    pivot, unmeasured = {}, []
    for sp in specs:
        got = measured_pivot(sp["mesh"], reg)
        if got is None:
            unmeasured.append(sp["mesh"])
        else:
            pivot[sp["mesh"]] = got
    print("--- pivot measurement (ruling (c), rock variant) ---")
    if unmeasured:
        print("  COULD NOT MEASURE the pivot of {0} of {1} rock meshes."
              .format(len(unmeasured), len(specs)))
        print("  This is ABSENT MEASUREMENT, NOT a measurement of zero. The")
        print("  KiteDemo rocks are native Fab assets that never went through")
        print("  blender/normalize_asset.py and never can (R-ASSET forbids")
        print("  authoring into a Fab folder), so their pivots are whatever")
        print("  the vendor set and nothing here has read them.")
        print("  Missing: {0}".format(reg_path))
        for m in unmeasured:
            print("    {0}".format(m))
        print("  Planning CONTINUES for budget and mask reporting with the")
        print("  correction set to 0.0 m, and --write is REFUSED, because a")
        print("  plan whose ground contact is unknown must not be spawned.")
    else:
        print("  all {0} rock meshes measured from {1}".format(
            len(specs), os.path.relpath(reg_path, REPO_ROOT)))
        for sp in specs:
            xy, bz = pivot[sp["mesh"]]
            dims, _t, _m = measured_mesh(sp["mesh"])
            lim = 0.25 * min(float(dims[0]), float(dims[1]))
            ok = abs(xy) <= lim
            print("    {0:<14} horizontal {1:6.3f} m (limit {2:.3f} = 0.25 x "
                  "min extent) {3}   base offset {4:+.3f} m -> corrected"
                  .format(sp["name"], xy, lim, "OK" if ok else "REFUSE", bz))
            if not ok:
                print("")
                print("REFUSE (ruling (c)): {0} has its geometry {1} m from "
                      "its pivot; random yaw would sweep it around a circle "
                      "of that radius.".format(sp["mesh"], xy))
                return 2
    print("")

    ctx = build_context(recipe, height_m, weights, spacing_m, rs, pivot)

    # ---- SHARED PLACEMENT PRIORS, loaded once ------------------------
    # Both are map-wide physical facts, so they load here rather than per
    # species. Each is REFUSED rather than skipped when a species asks
    # for it and it is unavailable: a declared bias that silently does
    # nothing is worse than a refusal, because the log reads as if it
    # applied (place_foliage.py's silent-bias lesson (grep the bias comment)).
    # Coerced through _bias(), which REFUSES a non-numeric rather than
    # letting float() raise. This planner is runnable without preflight,
    # so it cannot assume the recipe was validated — the same assumption
    # that let an unknown `role` be dropped silently.
    try:
        wants_flow = any(_bias(sp, "flow_bias") != 0.0 for sp in specs)
        wants_canopy = any(_bias(sp, "canopy_bias") != 0.0 for sp in specs)
    except ValueError as exc:
        print("REFUSE: {0}".format(exc))
        return 2

    print("--- placement priors ---")
    ctx["flow"], ctx["flow_status"] = (None, "NOT REQUESTED")
    if wants_flow:
        # Biome-scoped filename, matching place_foliage. The rock path and the
        # vegetation path MUST read the same drainage (non-negotiable 19), so
        # they must also agree about WHICH biome's drainage that is.
        ctx["flow"], ctx["flow_status"] = placement_priors.load_flow(
            n, filename=placement_priors.aux_map_names(recipe["biome_id"])["flow"])
        print("  flow      : {0}{1}".format(
            ctx["flow_status"],
            "  (normalised log-accumulation, NOT raw flow)"
            if ctx["flow"] is not None else ""))
        if ctx["flow"] is None:
            print("")
            print("REFUSE: a species declares flow_bias and the flow map is "
                  "{0}. Re-run derive_aux_maps against the adopted "
                  "heightmap.".format(ctx["flow_status"]))
            return 2
    else:
        print("  flow      : not requested by any species")

    ctx["trunk_xy"] = ctx["trunk_scale"] = None
    ctx["canopy_radius_m"] = None
    if wants_canopy:
        can = (recipe.get("foliage") or {}).get("canopy")
        if not isinstance(can, dict):
            print("")
            print("REFUSE: a species declares canopy_bias but the recipe "
                  "has no `foliage.canopy` block. It must declare `plan` "
                  "and `radius_m`; guessing either would put clutter under "
                  "a forest that is not the one in the world.")
            return 2
        plan_path = os.path.join(FOLIAGE_DIR, str(can["plan"]))
        if not _inside_repo(plan_path):
            print("REFUSE: foliage.canopy.plan escapes the repo")
            return 2
        try:
            ctx["trunk_xy"], ctx["trunk_scale"] = placement_priors.load_trunks(
                plan_path, origin_m, span_m)
        except (OSError, ValueError) as exc:
            print("")
            print("REFUSE: canopy source unusable: {0}: {1}"
                  .format(type(exc).__name__, exc))
            return 2
        ctx["canopy_radius_m"] = float(can["radius_m"])
        print("  canopy    : {0} trunks from {1}, radius {2:.3f} m at "
              "scale 1.0".format(len(ctx["trunk_xy"]), can["plan"],
                                 ctx["canopy_radius_m"]))
        print("              scale range {0:.3f}-{1:.3f}, so effective "
              "radius {2:.3f}-{3:.3f} m"
              .format(float(ctx["trunk_scale"].min()),
                      float(ctx["trunk_scale"].max()),
                      ctx["canopy_radius_m"] * float(ctx["trunk_scale"].min()),
                      ctx["canopy_radius_m"] * float(ctx["trunk_scale"].max())))
    else:
        print("  canopy    : not requested by any species")
    print("")

    dep = ctx["deposit"]
    print("--- talus routing ---")
    print("  repose {0} deg, source slope >= {1} deg, runout {2} m, "
          "MFD p={3}".format(rs["repose_deg"], rs["cliff_source_slope_deg"],
                             rs["runout_m"], rs["mfd_exponent"]))
    print("  cliff source cells {0:,} ({1:.1f} ha), routing ran {2} steps"
          .format(ctx["cliff_source_cells"],
                  ctx["cliff_source_cells"] * cell_ha, ctx["routing_steps"]))
    print("  mass conserved (asserted inside the router)")
    ps = 1.0 - np.exp(-dep / float(rs["saturation"]))
    print("  deposit  max {0:.1f}  p99 {1:.3f}   p>0.2 {2:.1f} ha   "
          "p>0.5 {3:.1f} ha".format(dep.max(), np.percentile(dep, 99),
                                    (ps > 0.2).sum() * cell_ha,
                                    (ps > 0.5).sum() * cell_ha))
    naive = (ctx["slope"] >= 25) & (ctx["slope"] <= 38)
    print("  DISCRIMINATION vs a bare slope band: the naive 25-38 deg band "
          "is {0:.0f} ha,".format(naive.sum() * cell_ha))
    print("    of which {0:.1f}% has NO cliff feeding it. That difference "
          "is the design.".format(100.0 * (naive & (ps <= 0.2)).sum()
                                  / max(naive.sum(), 1)))
    # THE SATURATION IMPLIED BY THE APRON REFERENCE (ruled 2026-09-26).
    # p > 0.2  <=>  deposit > -ln(0.8) * saturation = 0.2231 * saturation.
    # R12 4a's reference apron is 305.4 ha (p > 0.2) on the 4 m terrain
    # and is resolution-independent as an AREA, so the deposit value that
    # exactly 305.4 ha of cells exceed, divided by 0.2231, is the shared
    # saturation this field would need -- DERIVED from the field, not
    # typed. Per-species mask.saturation copies keep their ratio to the
    # shared value (alpine.json: 0.05 / 0.03, 0.04 / 0.03).
    _flat = np.sort(dep.ravel())[::-1]
    print("  apron ladder (area with deposit >= t):")
    for _t in (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0):
        print("    t = {0:<6} {1:9.1f} ha".format(_t, (dep >= _t).sum() * cell_ha))
    _ref_ha = 305.4
    _k = int(round(_ref_ha / cell_ha))
    if 0 < _k < _flat.size:
        _d_ref = float(_flat[_k])
        print("  deposit exceeded by exactly {0} ha: {1:.6f}  ->  implied "
              "saturation {2:.6f}  (current {3})".format(
                  _ref_ha, _d_ref, _d_ref / 0.2231, rs["saturation"]))
    del _flat
    print("")

    # ---- WATER + SETTLEMENT EXCLUSIONS, loaded ONCE, before any plan ----
    # place_foliage's --place pass says out loud that "adopted rock plans
    # are not filtered by this pass" (its settlement summary), so a rock
    # plan that wants the Brief-4 lakes and the committed town cleared must
    # clear them HERE, on its own finished rows. Same two definitions the
    # tree path and the encounters placer read (NN24/NN19):
    # town_exclusion.load + plan_encounters.WaterMask. FAIL CLOSED like
    # place_foliage.load_exclusion / load_water_exclusion: a declared
    # exclusion whose input is missing is a REFUSE, never a silent pass.
    _excl = load_rock_exclusions(recipe)
    if _excl.get("error"):
        print("REFUSE: {0}".format(_excl["error"]))
        return 2
    print("--- exclusions (post-filter on finished rows; RNG untouched) ---")
    print("  settlement: {0}".format(_excl["settlement_desc"]))
    print("  water     : {0}".format(_excl["water_desc"]))
    print("")

    plans, total = [], 0
    for i, sp in enumerate(specs):
        try:
            pl = plan_species(sp, ctx, origin_m, fol.get("seed", 0), i)
        except ValueError as exc:
            print("REFUSE: {0}".format(exc))
            return 2
        apply_rock_exclusions(pl, _excl)
        plans.append(pl)
        total += len(pl["xyz"])
    if _excl["shapes"] is not None or _excl["water"] is not None:
        print("--- exclusion removals ---")
        for pl in plans:
            print("  {0:<14} settlement {1:>7,}   water {2:>7,}   kept {3:>9,}"
                  .format(pl["spec"]["name"], pl["removed_settlement"],
                          pl["removed_water"], len(pl["xyz"])))
        print("")

    print("--- planned instances ---")
    print("  `mask ha` is the PROBABILITY-WEIGHTED area (sum of p x cell "
          "area), not the")
    print("  count of cells with p > 0. For a soft mask those differ by "
          "20x, and only the")
    print("  weighted figure divides into a density that means anything.")
    print("  {0:<14} {1:<6} {2:>10} {3:>9} {4:>8} {5:>10} {6:>8} {7:>8}"
          .format("species", "role", "candidates", "placed", "mask ha",
                  "on-mask/ha", "map/ha", "cover"))
    cover_by_role = {}
    for pl in plans:
        sp, placed = pl["spec"], len(pl["xyz"])
        eff = max(pl["mask_ha_full"], 1e-9)
        foot = float(pl["dims_m"][0]) * float(pl["dims_m"][1])
        smean = (float(sp["scale_range"][0])
                 + float(sp["scale_range"][1])) / 2.0
        cover = (placed / eff) * foot * smean * smean / 1e4
        cover_by_role[sp["role"]] = cover_by_role.get(sp["role"], 0.0) + cover
        print("  {0:<14} {1:<6} {2:>10,} {3:>9,} {4:>8.1f} {5:>10.1f} "
              "{6:>8.3f} {7:>7.1f}%".format(
                  sp["name"], sp["role"], pl["candidates"], placed, eff,
                  placed / eff, placed / hectares, 100.0 * cover))
    print("  {0:<21} {1:>9,}".format("TOTAL", total))
    print("")
    print("  areal coverage where the mask reads 1.0 (the heart of a fan / "
          "face):")
    for r in ROLES:
        if r in cover_by_role:
            print("    {0:<6} {1:5.1f}% of the ground".format(
                r, 100.0 * cover_by_role[r]))
    print("  embed depth (mesh height x embed_frac x scale, along the "
          "blended up-axis; the surface normal only at align=1):")
    for pl in plans:
        if len(pl["xyz"]):
            print("    {0:<14} {1:.2f} .. {2:.2f} m into the surface".format(
                pl["spec"]["name"], float(np.min(pl["embed_m"])),
                float(np.max(pl["embed_m"]))))
    print("")

    print("--- rotation gate (replaces R4's 4-degree tilt check for rocks) ---")
    bad = False
    for pl in plans:
        sp = pl["spec"]
        ok, why, notes = rotation_gate(
            pl["yaw"], pl["pitch"], pl["roll"], pl["slope_at"],
            float(sp["align_to_normal"]),
            float(sp.get("tumble_deg", 0.0) or 0.0), sp["name"])
        print("  {0:<14} max |pitch| {1:6.2f}  max |roll| {2:6.2f}  "
              "yaw {3:6.2f}..{4:6.2f} mean {5:6.2f}   {6}".format(
                  sp["name"],
                  float(np.abs(pl["pitch"]).max()) if len(pl["xyz"]) else 0.0,
                  float(np.abs(pl["roll"]).max()) if len(pl["xyz"]) else 0.0,
                  float(pl["yaw"].min()) if len(pl["xyz"]) else 0.0,
                  float(pl["yaw"].max()) if len(pl["xyz"]) else 0.0,
                  float(pl["yaw"].mean()) if len(pl["xyz"]) else 0.0,
                  "PASS" if ok else "REFUSE"))
        for w in why:
            print("      {0}".format(w))
        for nt in notes:                       # rule 13: skips print too
            print("      NOTE {0}".format(nt))
        bad = bad or not ok
    if bad:
        print("")
        print("REFUSE: rotation gate. Nothing written.")
        return 4
    print("")

    print("--- triangle budget (project convention: full 360-degree disc) ---")
    print("  {0:<14} {1:>7} {2:>5} {3:>7} {4:>9} {5:>26} {6:>12} {7:>10}"
          .format("species", "LOD0", "mats", "C (m)", "cull m", "LOD chain",
                  "local worst", "map avg"))
    local_by_role, map_total = {}, 0.0
    for pl in plans:
        sp = pl["spec"]
        smean = (float(sp["scale_range"][0]) + float(sp["scale_range"][1])) / 2.0
        C = screen_constant(pl["dims_m"], smean)
        # LOD count and material slots come from the LIVE measurement, not
        # from the recipe and not from the Fab registry. The recipe's
        # `lod_depth` is a declared expectation that the validator asserts
        # EQUALS this number; it is never the number the budget is
        # computed from. One fact, one source (non-negotiable 24).
        # live_lods_and_materials RAISES ValueError when rock_pivots.json
        # is absent or the mesh has no row — the SAME condition as an
        # unmeasured pivot. It was uncaught here, so a run without the
        # registry died with a traceback (exit 1) in the budget section
        # instead of the promised report-and-refuse at exit 2 (Pass 3
        # 2026-09-16 F1). Refuse cleanly.
        try:
            depth, n_mats, lods, screens = live_lods_and_materials(
                reg, sp["mesh"])
        except ValueError as exc:
            print("REFUSE (cannot cost): %s. The triangle budget needs "
                  "the measured LOD/material chain, which comes from the "
                  "same registry the pivot correction does — see R12 "
                  "ORDERED STEPS step 2 (measure the pack first)." % exc)
            return 2
        # MEASURED chain and MEASURED screen sizes, not `lod_chain()`.
        # That function models `percent = screen_size^2`, which is how
        # R5's conifer chain was GENERATED. These rocks ship VENDOR
        # chains, which do not decimate that aggressively and do not
        # switch at the same screen sizes: boulder_medium_01 measures
        # 4136/1186/892/596 where the model predicts 4136/1034/182/32,
        # and switches to LOD3 at screen 0.238 where the model assumes
        # 0.088 -- i.e. much nearer the camera.
        #
        # THE ERROR RUNS BOTH WAYS, per mesh, which is why nothing here
        # applies a correction factor. Measured against modelled at
        # 1 instance/ha, cull 140 m, over all 13 admissible rocks:
        #
        #     boulder_small          20.3x   model UNDERSTATES
        #     boulder_medium_02      14.1x
        #     boulder_medium_01       9.5x
        #     mountain_rock_closed    1.0x   model happens to agree
        #     scree_slab_001          0.7x
        #     cliff_face_01           0.4x   model OVERSTATES
        #
        # A single fudge factor would be wrong for ten of the thirteen.
        # The chain is a property of the asset, so it is read from the
        # asset (non-negotiable 15).
        modelled = lod_chain(pl["lod0_tris"], depth)
        placed = len(pl["xyz"])
        on_mask = placed / max(pl["mask_ha_full"], 1e-9)
        cull = float(sp["cull_distance_m"])
        # cull 0 is DISABLED (unlimited draw), not zero cost — but
        # triangles_in_view(min(radius, 0)) returns 0.0, reporting the
        # MOST expensive config as the cheapest and passing the budget
        # (Pass 3 2026-09-16 F4). This planner runs without preflight
        # (its own premise), so it bounds cull itself here, mirroring
        # import_heightmap's (0, 5000].
        if not (0.0 < cull <= 5000.0):
            print("REFUSE: %s cull_distance_m=%s is outside (0, 5000]. "
                  "0 means DISABLED (unlimited draw) in-engine, not free "
                  "— the budget cannot cost it. Set a real cull distance."
                  % (sp.get("name"), cull))
            return 2
        t_local = triangles_in_view(on_mask, cull, lods, C, screens)
        t_map = triangles_in_view(placed / hectares, cull, lods, C, screens)
        t_model = triangles_in_view(on_mask, cull, modelled, C)
        if t_model > 0 and t_local / t_model > 1.25:
            print("  NOTE {0}: the generated-chain model would have "
                  "reported {1:.3f}M here; the MEASURED chain costs "
                  "{2:.3f}M ({3:.1f}x). Vendor LOD chains do not follow "
                  "percent = screen_size^2.".format(
                      sp["name"], t_model / 1e6, t_local / 1e6,
                      t_local / t_model))
        local_by_role[sp["role"]] = local_by_role.get(sp["role"], 0.0) + t_local
        map_total += t_map
        print("  {0:<14} {1:>7,} {2:>5} {3:>7.2f} {4:>9.0f} {5:>26} "
              "{6:>11.3f}M {7:>9.3f}M".format(
                  sp["name"], pl["lod0_tris"], n_mats, C, cull,
                  "/".join("{0:,}".format(x) for x in lods),
                  t_local / 1e6, t_map / 1e6))
    print("")
    for r in ROLES:
        if r in local_by_role:
            print("  local worst case, {0:<6} {1:8.3f}M".format(
                r, local_by_role[r] / 1e6))
    worst = sum(local_by_role.values())
    print("  local worst case, ALL     {0:8.3f}M   (pessimistic: cliff, "
          "talus and meadow".format(worst / 1e6))
    print("                                        cannot all surround one "
          "camera)")
    print("  map average               {0:8.3f}M   (R5's own convention)"
          .format(map_total / 1e6))
    print("")
    print("  conifers (R5 locked)        39.600M")
    print("  grass    (R11 locked)       29.800M")
    print("  rocks    (this plan)      {0:9.3f}M".format(worst / 1e6))
    print("  ------------------------- ---------")
    print("  TOTAL                     {0:9.3f}M   working target 40M"
          .format(69.4 + worst / 1e6))
    print("")

    print("--- instance ceiling ---")
    print("  ceiling                 {0:>9,}".format(args.max_instances))
    print("  other species this run  {0:>9,}".format(args.other_instances))
    print("  rocks                   {0:>9,}".format(total))
    print("  remaining               {0:>9,}".format(
        args.max_instances - args.other_instances - total))
    if args.other_instances + total > args.max_instances:
        print("")
        print("REFUSE: {0:,} instances exceeds the ceiling of {1:,}. Nothing "
              "written. Lower a density_per_hectare_on_mask or a cull; do "
              "not raise the ceiling to silence this."
              .format(args.other_instances + total, args.max_instances))
        return 3
    print("")

    if unmeasured and args.write:
        print("REFUSE: --write with {0} unmeasured pivot(s). Every instance's "
              "ground contact would be unknown. Produce {1} first (ORDERED "
              "STEPS, R12 step 2) — it reuses the get_bounds() read already "
              "in place_foliage.py's get_bounds read (grep get_bounds).".format(len(unmeasured), reg_path))
        return 2

    if not args.write:
        print("=" * 70)
        print("REPORT ONLY — nothing written. Re-run with --write.")
        print("=" * 70)
        return 0

    os.makedirs(FOLIAGE_DIR, exist_ok=True)
    os.makedirs(TERRAIN_DIR, exist_ok=True)
    dbg = rs.get("debug_map")
    if dbg:
        dpath = os.path.join(REPO_ROOT, dbg)
        if not _inside_repo(dpath):
            print("REFUSE: debug_map escapes REPO_ROOT")
            return 1
        Image.fromarray((np.clip(ps, 0, 1) * 255).astype(np.uint8),
                        mode="L").save(dpath)
        print("  wrote {0}  -- LOOK AT IT before trusting the plan"
              .format(os.path.relpath(dpath, REPO_ROOT)))

    for pl in plans:
        sp = pl["spec"]
        path = os.path.join(FOLIAGE_DIR, "{0}_{1}.json".format(
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
        # PROVENANCE + STAMP, the same declaration place_foliage writes.
        # Rock plans took a different write path and so stayed UNSTAMPED --
        # CANNOT CHECK -- after the vegetation plans were covered. One
        # declaration of what a plan's inputs are lives in plan_stamp; both
        # producers use it rather than each keeping a list.
        _doc = {
            "_produced_by": "scripts/rock_scatter.py",
            "_recipe": os.path.relpath(recipe_path,
                                       REPO_ROOT).replace("\\", "/"),
            "_terrain_source": recipe["heightmap"]["source"],
        }
        # The SAME declared-input keys place_foliage writes (plan_stamp
        # INPUT_KEYS), so the stamp covers the field this plan sampled and
        # the footprints it cleared.
        if _pf_rel:
            _doc["_planting_field"] = _pf_rel
        if _excl.get("settlement") is not None:
            _doc["_city_plan"] = _excl["settlement"]["from_city_plan"]
        if _excl.get("water_decl") is not None:
            _doc["_water_mask"] = _excl["water_decl"]["exclusion_mask"]
        _doc.update({"biome": recipe["biome_id"], "species": sp["name"],
                       "mesh": sp["mesh"], "count": len(rows),
                       "role": sp["role"],
                       "units": "cm, degrees, uniform scale",
                       # THE DECLARED PIVOT CORRECTION.
                       # `place_foliage`'s ruling-(c) gate refuses any
                       # mesh whose base sits more than 0.25 m from its
                       # pivot, because for a Blender-normalised plant
                       # that means the import went wrong. These rocks
                       # are box-centred BY DESIGN (-0.618 m on
                       # Medium_Boulder_001) and the Z values above have
                       # ALREADY been corrected by exactly this number.
                       #
                       # Declaring it converts the gate from "the pivot
                       # must be normalised" -- which a rock can never
                       # satisfy -- into "the correction you applied
                       # must equal what the engine measures NOW". That
                       # is strictly stronger: it catches a plan
                       # computed against a stale measurement, which the
                       # old gate could not see at all. It cannot be
                       # satisfied by omission, because a plan with no
                       # declaration falls back to the strict gate.
                       "pivot_base_offset_m": round(float(pl["base_z_m"]), 4),
                       # Embed depth PER UNIT SCALE, so a verifier can
                       # reconstruct the expected ground offset UP TO A
                       # DERIVED SLOPE RESIDUAL — exact reconstruction is
                       # IMPOSSIBLE (Pass 3 2026-09-16 F8): the embed acts
                       # along the blended normal, nvec.z is not in the
                       # plan, and tumble_deg perturbs pitch/roll AFTER
                       # the solve, so the pitch/roll->normal identity is
                       # destroyed (verify_grounding.py:154-186 records
                       # that using it made agreement worse, 5 outliers
                       # -> 44). The field enables a slope-tolerant check,
                       # not a strict per-instance one.
                       "embed_depth_per_scale_m": round(
                           float(sp.get("embed_frac", 0.0) or 0.0)
                           * float(pl["dims_m"][2]), 5),
                       "cull_cm": int(round(
                           float(sp["cull_distance_m"]) * 100.0)),
                     "instances": rows})
        # Exclusion provenance, the same shape place_foliage writes, so a
        # reader of the plan can see what was cleared without re-running.
        if _excl.get("settlement") is not None:
            _m = _excl["margins"]
            _doc["settlement_exclusion"] = {
                "from_city_plan": _excl["settlement"]["from_city_plan"],
                "building_margin_m": _m[0], "street_margin_m": _m[1],
                "plaza_margin_m": _m[2],
                "removed": int(pl["removed_settlement"]),
                "applied": "post-filter on built rows; sampling RNG untouched"}
        if _excl.get("water_decl") is not None:
            _doc["water_exclusion"] = {
                "exclusion_mask": _excl["water_decl"]["exclusion_mask"],
                "removed": int(pl["removed_water"]),
                "applied": "post-filter on built rows; sampling RNG untouched"}
        _doc[plan_stamp.STAMP_KEY] = plan_stamp.stamp(_doc, REPO_ROOT)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(_doc, fh)
        print("  wrote {0:<40} {1:>9,} instances  {2:.1f} MB".format(
            os.path.relpath(path, REPO_ROOT), len(rows),
            os.path.getsize(path) / 1048576.0))
    print("")
    print("NOT PLACED. place_foliage.py --place is the only thing that "
          "spawns these, and it must be handed the VEGETATION plans in the "
          "same run or its orphan sweep deletes them.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception:                              # noqa: BLE001
        # FULL TRACEBACK, always. This printed one line — type and
        # message — and an `IndexError: tuple index out of range` raised
        # eight minutes into a talus routing pass named neither the file
        # nor the line. Re-running to find out where costs another eight
        # minutes of MFD routing. Non-negotiable 14: never truncate the
        # output of an operation you cannot cheaply repeat.
        import traceback
        traceback.print_exc()
        sys.exit(1)
