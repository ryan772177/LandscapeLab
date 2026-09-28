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

**ONE DECLARATION.** This module owns the fit test: `plan_city` calls it to
bias sampling (plan_city.py:49,361-362,449) and `kit_coverage_v2` calls
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
