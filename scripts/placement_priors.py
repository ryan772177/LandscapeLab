"""placement_priors.py — the placement PRIORS, defined once for every consumer.

WHY THIS MODULE EXISTS
----------------------
`RECIPES.md`'s Pass 5 ruling says ground clutter *"gathers under trees,
along drainage, and at cliff bases"*, and that the deposition and flow
fields are legitimate placement priors. Three gathering places; before
2026-08-08 the machinery had priors for two, split across two tools that
could not share them:

  cliff bases   `rock_scatter.talus_deposit()`   rock path      OK
  drainage      `place_foliage`'s inline flow    VEGETATION path
  under trees   nothing anywhere

A wetness field and a canopy field are **physical facts about the world**,
not per-consumer style knobs, so non-negotiable 19 applies exactly as it
applied to `foliage.rock_scatter`: *when two passes render the same
physical fact, the fact is defined once and both read it.* Had the rock
path grown its own copy of the flow lookup, rock clutter and conifers
would have followed drainage lines that disagreed — and neither tool's
verification could have detected it, because each would be internally
consistent.

Everything here is pure numpy/scipy. No editor, no writes.

WHAT THE FLOW MAP ACTUALLY IS — read this before reasoning about it
-------------------------------------------------------------------
`terrain/alpine_flow.png` is **not** raw flow accumulation.
`derive_aux_maps.py:213` writes `np.log1p(flow)` and then min-max
normalises it into uint16. So the file is *normalised log-accumulation*:
monotonic in wetness, but its differences are log differences. Callers
must not read a 0.5 as "half the water". `load_flow()` returns it
rescaled to [0, 1] and says so; the name of the returned status carries
the provenance.

THE CENTRING RULE, AND WHY IT IS SHARED
---------------------------------------
`centred_bias()` is the ONE definition of how a prior turns into a
multiplier. It is centred so the bias REDISTRIBUTES rather than scales:
mean density stays put and wet ground gains what dry ground loses. Two
consumers applying "the same" bias with different centring would produce
different totals from the same recipe number, which is the drift this
module exists to prevent.

The `reference` is an explicit argument rather than an implicit mean,
because the two callers legitimately differ and the difference must be
visible at the call site:

  flow    the WHOLE FIELD's mean — "the average wetness of the map"
  canopy  the candidate population's mean, which is an unbiased estimate
          of the map-wide mean because candidates are a uniform jittered
          grid over the whole span (see `rock_scatter.plan_species`)

COORDINATE FRAMES ARE THE DANGEROUS PART
----------------------------------------
Instance plans store **absolute centimetres**; candidate positions are
**local metres** measured from the landscape origin. `load_trunks()`
converts and then ASSERTS the result lands inside the span, refusing
otherwise. This is not defensive padding: `place_foliage.py:247-251`
records a defect where metres were stored under a header saying "cm",
and the offline verifier "sampled the map CENTRE for every instance and
duly reported that flow_bias did nothing" — a silent no-op that read as
a measurement. A frame error here fails the same way, so it fails loudly.
"""

from __future__ import annotations

import json
import os

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TERRAIN_DIR = os.path.join(REPO_ROOT, "terrain")

# Status strings returned by load_flow(). THREE outcomes, ruled in
# advance, because non-negotiable 6 requires "I could not look" to be
# distinguishable from "I looked and it is absent". The previous inline
# loader collapsed all three to `None`, so a resolution mismatch and a
# missing file were indistinguishable from a map with no drainage.
FLOW_LOADED = "LOADED"
FLOW_ABSENT = "ABSENT"
FLOW_SHAPE_MISMATCH = "SHAPE_MISMATCH"

def aux_map_names(biome_id):
    """ONE DECLARATION of the aux-map filenames, keyed by biome.

    WHY THIS EXISTS (non-negotiable 24). The string "alpine_flow.png" was typed
    in THREE places -- `derive_aux_maps.py` and `make_alpine_terrain.py` wrote
    it, `placement_priors.FLOW_FILENAME` read it -- with nothing tying them
    together. Two lists that must agree are one list, badly stored.

    IT WAS NOT A HYPOTHETICAL. Deriving aux maps for the 8129 recipe on
    2026-08-13 would have written 8129-resolution flow and deposition maps OVER
    /Game/Alpine's, from a terrain 0.79% larger. `terrain/alpine_flow.png`
    drives that world's Conifer `flow_bias` 0.45, so the placement inputs of a
    shipped world would have been silently replaced by another terrain's. The
    producer would have reported success.

    BACKWARD COMPATIBLE BY CONSTRUCTION: biome_id "alpine" yields exactly the
    legacy names, so nothing about the existing world moves.
    """
    return {
        "flow": "{0}_flow.png".format(biome_id),
        "deposition": "{0}_deposition.png".format(biome_id),
        "hillshade": "{0}_hillshade.png".format(biome_id),
    }


# The legacy default is now a PROJECTION of the rule above rather than a second
# copy of the string. If the rule changes, this follows.
FLOW_FILENAME = aux_map_names("alpine")["flow"]


def load_flow(n, terrain_dir=None, filename=FLOW_FILENAME):
    """Return `(flow, status)`.

    `flow` is float64 in [0, 1] at (n, n), or None. `status` is one of the
    FLOW_* constants and is never inferred from `flow is None` — the
    caller is expected to print it, so an absent map and an unusable map
    read differently in the log.
    """
    from PIL import Image

    tdir = terrain_dir or TERRAIN_DIR
    path = os.path.join(tdir, filename)
    if not os.path.isfile(path):
        return None, FLOW_ABSENT
    arr = np.asarray(Image.open(path)).astype(np.float64)
    if arr.ndim != 2 or arr.shape[0] != n or arr.shape[1] != n:
        return None, FLOW_SHAPE_MISMATCH
    return arr / max(float(arr.max()), 1e-9), FLOW_LOADED


def centred_bias(values, bias, reference):
    """The ONE definition of prior -> density multiplier.

    `values` are the prior sampled per candidate, `reference` is the
    value that means "average" for this prior, and `bias` is the recipe
    knob. Returns a multiplier in [0, 2].

    The formula is preserved EXACTLY as `place_foliage.plan()` carried it
    inline before 2026-08-08 (`clip(1 + bias*(v - ref)*2, 0, 2)`), so
    extracting it cannot move a single existing instance. That property
    is asserted by replaying the shipped Conifer plan, not assumed.
    """
    b = float(bias)
    if b == 0.0:
        return np.ones_like(np.asarray(values, dtype=np.float64))
    v = np.asarray(values, dtype=np.float64)
    return np.clip(1.0 + b * (v - float(reference)) * 2.0, 0.0, 2.0)


def closure_ramp(height_m, low_m, high_m, at_low, at_high):
    """Canopy CLOSURE as a function of elevation. A density multiplier.

    WHY THIS IS NOT `centred_bias`, AND THE DIFFERENCE IS THE POINT.
    `centred_bias` REDISTRIBUTES: wet ground gains exactly what dry ground
    loses and the mean is preserved, because flow says WHERE trees prefer
    to stand, not HOW MANY there are.

    Closure is the opposite kind of fact. A subalpine stand genuinely
    thins toward treeline — fewer trees, not the same trees moved uphill —
    and ends in open krummholz. So this SCALES, and the caller's total
    count falls accordingly. Anything that preserved the mean here would
    be describing a forest that does not exist.

    WHY IT LIVES HERE. Canopy closure against elevation is a physical
    property of the biome, not a knob one script owns — the same
    non-negotiable 19 argument that put the talus field and the flow prior
    in this module. A rock or clutter pass that wants "denser below
    treeline" must read THIS, not re-derive a second ramp free to disagree.

    `at_low` applies at `low_m` and `at_high` at `high_m`, linear between,
    CLAMPED outside so a candidate below the band cannot be given more
    than the band's own floor value. Both are multipliers in [0, 1];
    at_high > at_low is legal and describes a stand that thickens with
    elevation, which is wrong for spruce and right for nothing this
    project currently plants — so it is permitted and not special-cased.
    """
    h = np.asarray(height_m, dtype=np.float64)
    lo, hi = float(low_m), float(high_m)
    if hi <= lo:
        # A zero-width band has no gradient to express. Returning the low
        # value is the only reading that does not silently invent one.
        return np.full_like(h, float(at_low))
    t = np.clip((h - lo) / (hi - lo), 0.0, 1.0)
    return float(at_low) + (float(at_high) - float(at_low)) * t


def load_trunks(plan_path, origin_m, span_m, tol_m=1.0):
    """Trunk positions from an instance plan, in LOCAL METRES.

    Returns `(xy_local_m, scale)` with shapes (k, 2) and (k,).

    Plans store `[x_cm, y_cm, z_cm, yaw, pitch, roll, scale]` in ABSOLUTE
    centimetres. Candidates are local metres from the landscape origin, so
    the conversion is `(cm - origin_cm) / 100`.

    TWO INDEPENDENT CHECKS, BECAUSE ONE OF THEM PROVABLY CANNOT SEE THE
    DEFECT THIS FUNCTION EXISTS TO GUARD.

    1. **The plan's DECLARED units.** `place_foliage` writes
       `"units": "cm, degrees, uniform scale"`. That declaration is the
       contract, and it is checked rather than inferred. Absent or
       non-cm units REFUSE — "I could not tell" is not "cm"
       (non-negotiable 6).
    2. **Converted extent inside the span.** Catches the different error
       of correct units against the wrong origin.

    Check 2 alone is NOT sufficient, and the first version of this
    function shipped believing it was. Metres written under a "cm" header
    — the exact defect recorded at `place_foliage.py:247-251` — divides
    by 100 into a tiny cluster near the landscape CENTRE, which is
    comfortably inside the span and passes an extent test. That is why
    the original defect "sampled the map CENTRE for every instance and
    duly reported that flow_bias did nothing". The selftest below asserts
    both checks against the case each one misses.
    """
    if not os.path.isfile(plan_path):
        raise FileNotFoundError(
            "no instance plan at {0}. A canopy prior cannot be estimated "
            "from an absent plan, and defaulting to 'no trees' would make "
            "the prior a silent no-op.".format(plan_path))
    with open(plan_path, "r", encoding="utf-8") as fh:
        plan = json.load(fh)
    units = plan.get("units")
    if not isinstance(units, str) or "cm" not in units.lower():
        raise ValueError(
            "{0} declares units {1!r}. This reader requires a plan that "
            "DECLARES centimetres. An undeclared unit is not an implicit "
            "cm — metres written under a cm header collapse every trunk "
            "toward the map centre, land inside the span, and pass every "
            "geometric check (place_foliage.py:247-251)."
            .format(plan_path, units))

    rows = plan.get("instances") or []
    if not rows:
        raise ValueError(
            "{0} declares zero instances; refusing to build a canopy "
            "prior from an empty forest.".format(plan_path))

    a = np.asarray(rows, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] < 7:
        raise ValueError(
            "{0} rows are {1}, expected at least 7 columns "
            "[x_cm, y_cm, z_cm, yaw, pitch, roll, scale]"
            .format(plan_path, a.shape))

    xy = np.column_stack((
        (a[:, 0] - float(origin_m[0]) * 100.0) / 100.0,
        (a[:, 1] - float(origin_m[1]) * 100.0) / 100.0,
    ))
    lo, hi = float(xy.min()), float(xy.max())
    if lo < -tol_m or hi > float(span_m) + tol_m:
        raise ValueError(
            "FRAME ERROR: trunks converted to local metres span "
            "{0:.1f}..{1:.1f} m but the landscape span is 0..{2:.1f} m. "
            "The plan's units or the origin disagree with this caller. "
            "Refusing rather than sampling the wrong place silently."
            .format(lo, hi, float(span_m)))
    return xy, a[:, 6].copy()


def canopy_occupancy(cand_xy, trunk_xy, trunk_scale, radius_m):
    """Canopy cover per candidate, in [0, 1]. 1 at a trunk, ~0 beyond 2r.

    `c = exp(-(d / r_nearest)^2)` where `d` is the distance to the nearest
    trunk and `r_nearest` is THAT trunk's canopy radius, i.e.
    `radius_m * scale` for the specific tree matched. Per-instance scale
    varies 0.700-1.400 on the shipped Conifer plan, so using the matched
    tree's own radius is both cheap (the KD-tree already returns the
    index) and correct, where a population mean would be neither.

    COMPUTED PER CANDIDATE, NOT RASTERISED, AND THAT IS THE WHOLE POINT.
    The map grid is 4.0 m and the measured canopy radius is 3.07 m at
    scale 1.0 (`fir_tree_01_c_LOD0` dims 6.306 x 5.966 x 14.521 m,
    `Free/_measured/fir_tree_01.json`). A canopy is therefore about 1.6
    cells across — sigma 0.8 cells. A rasterised field at map resolution
    CANNOT express "under this tree"; it can only express "in the woods
    versus in a clearing", which is a different and much coarser claim.
    Candidates are continuous jittered positions, so the honest
    implementation asks the actual trunks.
    """
    from scipy.spatial import cKDTree

    cand = np.asarray(cand_xy, dtype=np.float64)
    if cand.size == 0:
        return np.zeros(0, dtype=np.float64)
    tree = cKDTree(np.asarray(trunk_xy, dtype=np.float64))
    d, idx = tree.query(cand, k=1)
    r = float(radius_m) * np.asarray(trunk_scale, dtype=np.float64)[idx]
    r = np.maximum(r, 1e-6)
    return np.exp(-((d / r) ** 2))


def selftest():
    """Three directions, and the negative cases are the point."""
    ok = True

    def check(label, cond):
        nonlocal ok
        print("  {0:<7} {1}".format("ok" if cond else "FAIL", label))
        ok = ok and bool(cond)

    # centred_bias — zero bias is exactly inert, and it redistributes.
    v = np.array([0.0, 0.5, 1.0])
    check("bias 0.0 returns exactly 1.0 everywhere",
          np.array_equal(centred_bias(v, 0.0, 0.5), np.ones(3)))
    m = centred_bias(v, 1.0, 0.5)
    check("above reference boosts, below suppresses",
          m[2] > 1.0 and m[0] < 1.0)
    check("at the reference the multiplier is exactly 1.0",
          centred_bias(np.array([0.5]), 1.0, 0.5)[0] == 1.0)
    check("multiplier is clamped into [0, 2]",
          float(centred_bias(v, 99.0, 0.5).max()) <= 2.0
          and float(centred_bias(v, 99.0, 0.5).min()) >= 0.0)

    # canopy_occupancy — a trunk at the origin, radius 3 m.
    tx = np.array([[0.0, 0.0]])
    ts = np.array([1.0])
    c = canopy_occupancy(np.array([[0.0, 0.0], [3.0, 0.0], [12.0, 0.0]]),
                         tx, ts, 3.0)
    check("occupancy is 1.0 at the trunk", abs(c[0] - 1.0) < 1e-12)
    check("occupancy is exp(-1) at one radius", abs(c[1] - np.exp(-1)) < 1e-9)
    check("occupancy is ~0 at four radii", c[2] < 1e-6)
    check("occupancy is monotonically decreasing", c[0] > c[1] > c[2])
    # scale must actually be read: a bigger tree reaches further.
    big = canopy_occupancy(np.array([[3.0, 0.0]]), tx, np.array([2.0]), 3.0)
    check("a larger instance scale widens its canopy", big[0] > c[1])

    # load_flow — the absent branch must SAY absent, not return None only.
    f, st = load_flow(8, terrain_dir=REPO_ROOT, filename="__no_such__.png")
    check("missing flow map reports ABSENT", f is None and st == FLOW_ABSENT)
    f, st = load_flow(3)      # real map, deliberately wrong n
    check("resolution mismatch reports SHAPE_MISMATCH, not ABSENT",
          f is None and st == FLOW_SHAPE_MISMATCH)

    # load_trunks — each check tested against the case the OTHER misses.
    import tempfile
    tdir = tempfile.mkdtemp(prefix="ll_priors_")
    ORIGIN, SPAN = (-4032.0, -4032.0), 8064.0

    def _write(name, obj):
        p = os.path.join(tdir, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return p

    def _refuses(label, obj):
        try:
            load_trunks(_write(label + ".json", obj), ORIGIN, SPAN)
            check(label, False)
        except (ValueError, FileNotFoundError):
            check(label, True)

    # POSITIVE CONTROL FIRST: a well-formed plan must be ACCEPTED, or
    # every refusal below is meaningless.
    good = {"units": "cm, degrees, uniform scale",
            "instances": [[-403200.0, -403200.0, 0, 0, 0, 0, 1.0],
                          [403200.0, 403200.0, 0, 0, 0, 0, 1.3]]}
    xy, sc = load_trunks(_write("good.json", good), ORIGIN, SPAN)
    check("a well-formed cm plan is ACCEPTED", xy.shape == (2, 2))
    check("origin corner converts to local (0, 0)",
          abs(xy[0, 0]) < 1e-9 and abs(xy[0, 1]) < 1e-9)
    check("far corner converts to local (span, span)",
          abs(xy[1, 0] - SPAN) < 1e-6 and abs(xy[1, 1] - SPAN) < 1e-6)
    check("per-instance scale is carried through", abs(sc[1] - 1.3) < 1e-12)

    # THE DEFECT THE EXTENT CHECK CANNOT SEE. Metres under a cm header
    # land near the map CENTRE and pass every geometric test, so this is
    # caught by the DECLARED-units check and nothing else.
    _refuses("metres-as-cm with NO declared units REFUSES",
             {"instances": [[10.0, 10.0, 0, 0, 0, 0, 1.0]]})
    _refuses("plan declaring metres REFUSES",
             {"units": "m, degrees", "instances": [[10.0, 10.0, 0, 0, 0, 0, 1.0]]})

    # Proof that check 2 really was blind to it: same rows, cm declared.
    centre = load_trunks(
        _write("centre.json",
               {"units": "cm", "instances": [[10.0, 10.0, 0, 0, 0, 0, 1.0]]}),
        ORIGIN, SPAN)[0]
    check("...and the extent check ALONE would have passed it "
          "(lands {0:.0f} m in, span {1:.0f} m)".format(centre[0, 0], SPAN),
          0.0 <= centre[0, 0] <= SPAN)

    # THE DEFECT THE UNITS CHECK CANNOT SEE: right units, wrong origin.
    _refuses("cm plan against the WRONG origin REFUSES",
             {"units": "cm", "instances": [[9e7, 9e7, 0, 0, 0, 0, 1.0]]})

    _refuses("empty instance list REFUSES", {"units": "cm", "instances": []})
    try:
        load_trunks(os.path.join(tdir, "__missing__.json"), ORIGIN, SPAN)
        check("absent plan file REFUSES", False)
    except FileNotFoundError:
        check("absent plan file REFUSES", True)

    for nm in os.listdir(tdir):
        try:
            os.remove(os.path.join(tdir, nm))
        except OSError:
            pass
    try:
        os.rmdir(tdir)
    except OSError:
        pass

    return ok


if __name__ == "__main__":
    import sys
    print("placement_priors selftest")
    sys.exit(0 if selftest() else 1)
