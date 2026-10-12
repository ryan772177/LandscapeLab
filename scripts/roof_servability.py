"""Which footprints can a kit roof actually cover? Shared by planner and audit.

⛔ THE OLD COVERAGE QUESTION DOES NOT APPLY TO A MODULAR KIT and must not be
re-asked. Walls tile, so footprint coverage is near-total and the number is
meaningless. **Roofs are the exception**: a roof piece is a whole object with a
fixed span, so the +-20% fit question is exactly right FOR ROOFS and only for
roofs.

Measured 2026-08-30, before the ruling: with the planner sampling footprints
UNIFORMLY over 7-15 m, only **132 of 303 (43.6%)** could take a single kit roof.
The other 56.4% exceeded the largest piece in at least one axis, and the Roofs
set ships **no ridge or slope parts** to compose from.

The operator's ruling (4b, with a small 4a allowance): **roof servability
becomes a planner constraint, like footprint servability already is.** The
distribution biases toward what the Roofs set serves; a handful of landmarks may
compose roofs from other kit pieces where that is clean; everything else stays a
counted greybox.

**TWO SOURCES SINCE 2026-10-06, each with ONE declaration.** `kit_v2` (below:
roof_spans/fits/servable_by/targets) and `town_kit` (kit_*: delegates to the
BUILDER, scripts/town_kit_plan.py). plan_city picks by
`buildings.roof_servability.source` and records `roof_fit_source` in the plan;
kit_coverage_v2 refuses to judge a town_kit plan with the kit_v2 test.
Original note: `plan_city` calls it to bias sampling and `kit_coverage_v2` calls
`roof_spans()`/`servable_by()` to audit (routed through here 2026-09-18) —
rather than each carrying its own copy of "+-20% on both axes, roofs may
rotate 90 degrees", the two-lists-one-badly-stored defect this module exists
to prevent. `audit()` is provided for a caller that wants the aggregate
fraction; nothing calls it yet.
"""
import io
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT_V2 = os.path.join(REPO, "Free", "_measured", "kit_medievalvillage_v2.json")


def roof_spans(path=KIT_V2):
    """(name, span_x_m, span_y_m) for every roof mesh in the measured kit,
    plus SM_House04 (a whole-house piece that carries its own roof)."""
    with io.open(path, encoding="utf-8") as fh:
        rows = json.load(fh)["rows"]
    out = []
    for r in rows:
        n = r["name"]
        if "Roof" in n or n == "SM_House04":
            out.append((n, r["size_cm"][0] / 100.0, r["size_cm"][1] / 100.0))
    return sorted(out, key=lambda t: max(t[1], t[2]))


def fits(fx, fy, span, tol):
    """Does one roof cover this footprint within tolerance, either way round?"""
    sx, sy = span
    for a, b in ((sx, sy), (sy, sx)):        # a roof may be rotated 90 deg
        if abs(a - fx) <= tol * fx and abs(b - fy) <= tol * fy:
            return True
    return False


def servable_by(fx, fy, spans, tol=0.20):
    """Return the NAME of a roof that covers this footprint, or None."""
    for name, sx, sy in spans:
        if fits(fx, fy, (sx, sy), tol):
            return name
    return None


def targets(spans, fmin_m, fmax_m, tol=0.20):
    """Footprint sizes that ARE servable, as (name, fx, fy) draw targets.

    A roof of span (sx, sy) covers footprints in [sx/(1+tol), sx/(1-tol)] and
    likewise for y. The target returned is the roof's OWN span, which sits
    comfortably inside that band -- BELOW its midpoint, since the band is
    asymmetric (it extends further above sx than below, e.g. at tol 0.20 it is
    [0.833 sx, 1.25 sx]) -- so jitter stays servable with margin rather than
    clinging to an edge.

    Targets outside the recipe's own footprint_m range are DROPPED, not
    clamped: clamping would silently produce a size the roof does not cover,
    which is the whole failure this exists to prevent.
    """
    out = []
    for name, sx, sy in spans:
        for fx, fy in ((sx, sy), (sy, sx)):
            if fmin_m <= fx <= fmax_m and fmin_m <= fy <= fmax_m:
                out.append((name, fx, fy))
    return out


# ---- source "town_kit" (2026-10-06): the fit test the BUILDER uses -----------
# The town is built by scripts/town_kit_plan.py, whose plan_roof() fits a roof to
# footprint + 2*eave within +-roof_tol over the USABLE roofs of
# recipes/town_kit.json. Planning against fits() above (bare footprint vs span,
# every roof incl. the three gallery-rejected awning roofs) would let the planner
# promise roofs the builder refuses. So under this source the planner asks the
# builder's own function -- one declaration, not a second copy of it.

def kit_snap_m(f_m):
    """Footprint side the builder will build: snapped DOWN to the kit snap, in m."""
    import town_kit_plan as tkp
    return (int(round(f_m * 100.0, 6)) // tkp.SNAP_CM * tkp.SNAP_CM) / 100.0


def kit_servable_by(fx_m, fy_m):
    """Roof the builder would put on this footprint (snapped), or None."""
    import town_kit_plan as tkp
    W, D = int(round(kit_snap_m(fx_m) * 100)), int(round(kit_snap_m(fy_m) * 100))
    if not (kit_side_tiles(W) and kit_side_tiles(D)):
        return None
    r = tkp.plan_roof(W, D, 2)                       # courses only move z, never the choice
    return r["mesh"] if r else None


def kit_side_tiles(L_cm):
    """Can the builder wall a side of L_cm? Asks the builder's own tile() for the run
    between the two corners -- not a restated minimum (audit 2026-10-06 F4)."""
    import random
    import town_kit_plan as tkp
    return L_cm >= 2 * tkp.CORNER_ARM_CM and tkp.tile(int(L_cm) - 2 * tkp.CORNER_ARM_CM,
                                                      random.Random(0)) is not None


def kit_targets(fmin_m, fmax_m):
    """(name, fx, fy) draw targets: each usable roof's native size minus the eave
    allowance, both orientations -- the footprint it fits at scale 1. Targets outside
    [fmin_m, fmax_m] are DROPPED, not clamped (see targets())."""
    import town_kit_plan as tkp
    out = []
    for name, (_path, (sx, sy)) in sorted(tkp.ROOFS.items()):
        ex, ey = (sx - 2 * tkp.EAVE_CM) / 100.0, (sy - 2 * tkp.EAVE_CM) / 100.0
        for fx, fy in ((ex, ey), (ey, ex)):
            if fmin_m <= fx <= fmax_m and fmin_m <= fy <= fmax_m:
                out.append((name, fx, fy))
    return out


def audit(footprints_m, tol=0.20, path=KIT_V2):
    """Fraction of footprints a single kit roof covers. footprints_m: [(x,y)]"""
    spans = roof_spans(path)
    hit = [servable_by(fx, fy, spans, tol) for fx, fy in footprints_m]
    n = sum(1 for h in hit if h)
    return {
        "total": len(footprints_m),
        "servable": n,
        "fraction": (n / float(len(footprints_m))) if footprints_m else 0.0,
        "tolerance": tol,
        "roof_count": len(spans),
        "biggest_span_m": max(max(s[1], s[2]) for s in spans) if spans else 0.0,
        "by_roof": {name: sum(1 for h in hit if h == name)
                    for name in sorted(set(h for h in hit if h))},
    }
