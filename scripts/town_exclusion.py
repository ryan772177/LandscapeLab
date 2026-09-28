"""town_exclusion.py — WHERE THE TOWN IS, for anything that must not stand in it.

    python scripts/town_exclusion.py --selftest

RULED 2026-09-12b (Town placement). The settlement footprint was being
described in THREE places: `plan_encounters.city_shapes` (rectangles, at
ENCOUNTER margins), `city_clear_foliage_payload` (rectangles PLUS the
plaza disc, at FOLIAGE margins), and nowhere at all in `place_foliage`,
which is the one that writes the file everything downstream reads.

This module is the single construction. It does NOT re-implement the
rectangles: it CALLS `plan_encounters.city_shapes`, so the oriented-
rectangle test has exactly one definition and a change to it cannot
reach one consumer and miss another (NN24 — two lists that must agree
are one list badly stored).

⛔ THE MARGINS ARE NOT ONE NUMBER. `recipes/encounters.json` says so in
its own prose: *"clearing a tree needs it out of the wall; keeping an
encounter away from a town needs it out of BOWSHOT."* Encounters use
30 m / 20 m; foliage uses 3 m / 2 m / 6 m from
`recipes/city.json:foliage_clearing`, which were SWEPT, not typed —
1 m removes 2,250 instances, 3 m removes 2,541, 5 m removes 2,842.
So the geometry is shared and the MARGINS are supplied by the caller.
A module that picked one margin set for everybody would be wrong for
whichever consumer it did not belong to.

THE PLAZA IS A DISC AND THAT IS NOT AN INCONSISTENCY. Everything else
is an oriented rectangle because a building is a rectangle; the plaza
is DECLARED as a circle (`plan.plaza_radius_cm`), so a disc is its
actual shape rather than an approximation. Its radius is read from the
plan and never declared here — a second radius would be two sources for
one physical fact (NN19) and would cut a differently-sized hole while
reporting success.

FAIL DIRECTION: REFUSE. A missing plaza radius or a missing plan raises.
The cost of assuming is a silently wrong-sized hole that every gate
passes; the cost of refusing is a stopped run that names the field.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from plan_encounters import city_shapes, inside_any  # noqa: E402


def foliage_margins(city_recipe):
    """(building_m, street_m, plaza_m) from recipes/city.json.

    Read from `foliage_clearing`, which is where the SWEPT values live.
    Absent block -> refuse; a default here would be a fourth declaration.
    """
    fc = (city_recipe or {}).get("foliage_clearing")
    if not fc:
        raise RuntimeError(
            "recipes/city.json carries no `foliage_clearing` block, so the "
            "foliage margins cannot be read. Refusing rather than defaulting "
            "-- the values there were measured by sweep (1 m removes 2,250 "
            "instances, 3 m removes 2,541, 5 m removes 2,842) and a guess "
            "would clear a different forest and report success.")
    missing = [k for k in ("building_margin_m", "street_margin_m",
                           "plaza_margin_m") if fc.get(k) is None]
    if missing:
        raise RuntimeError(
            "recipes/city.json:foliage_clearing is missing %s" % ", ".join(
                missing))
    return (float(fc["building_margin_m"]), float(fc["street_margin_m"]),
            float(fc["plaza_margin_m"]))


def build(plan, building_m, street_m, plaza_m):
    """(shapes, plaza) for the town, at the margins the CALLER chose.

    shapes -- oriented rectangles, from plan_encounters.city_shapes
    plaza  -- (cx_cm, cy_cm, radius_cm_squared) or None

    Squared radius against a squared distance, so the per-instance test
    costs no sqrt across 219,659 of them.
    """
    plan = dict(plan or {})
    plan.setdefault("streets", [])
    shapes = city_shapes(plan, building_m * 100.0, street_m * 100.0)

    if plan.get("plaza_radius_cm") is None:
        raise RuntimeError(
            "the plan carries no plaza_radius_cm, so the plaza disc cannot "
            "be derived. Refusing rather than assuming a radius -- a guessed "
            "one would cut a differently-sized hole and report success. "
            "Re-run the city planner; it has recorded this field since "
            "2026-08-27.")
    pr_m = float(plan["plaza_radius_cm"]) / 100.0

    # ⛔ THE MARGIN GATES THE MARGIN, NOT THE DISC. The clear payload reads
    # `if _pc and float(PLAZA_MARGIN_M) > 0.0`, which makes a ZERO margin
    # clear NO PLAZA AT ALL. That contradicts city.json's own declaration --
    # "the cleared disc is plan.plaza_radius_cm PLUS this margin" -- under
    # which a zero margin still clears the plan's own 22 m. The declaration
    # outranks the implementation, so the disc is built whenever a centre
    # exists and the margin only sizes it.
    #
    # Caught by this module's selftest at margin 0, which is why the
    # selftest exercises a margin production never uses: the shipped value
    # is 6.0 m, so the payload's gate is INERT today and would have bitten
    # silently the first time someone set it to zero to mean "no extra
    # margin" and got "no plaza clear" instead.
    plaza = None
    centre = plan.get("site_centre_cm")
    if centre:
        plaza = (float(centre[0]), float(centre[1]),
                 ((pr_m + plaza_m) * 100.0) ** 2)
    return shapes, plaza


def inside(shapes, plaza, x, y):
    """Is (x, y) cm inside the town? Plaza first — it is the cheap test."""
    if plaza is not None:
        dx = x - plaza[0]
        dy = y - plaza[1]
        if dx * dx + dy * dy <= plaza[2]:
            return True
    return inside_any(shapes, x, y)


def load(recipe_biome_plan_path, city_recipe_path=None):
    """(shapes, plaza, margins) from the two files on disk."""
    with open(recipe_biome_plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    city_recipe_path = city_recipe_path or os.path.join(
        REPO, "recipes", "city.json")
    with open(city_recipe_path, encoding="utf-8") as fh:
        city = json.load(fh)
    bm, sm, pm = foliage_margins(city)
    shapes, plaza = build(plan, bm, sm, pm)
    return shapes, plaza, (bm, sm, pm)


def selftest():
    """FOUR DIRECTIONS, no editor and no repo state.

    Direction 3 (refuse when broken) is the one that matters here: a
    missing plaza radius must RAISE, not quietly cut no disc.
    """
    fails = []

    # A single 10 x 20 m building at the origin, yawed 90 deg, plus a
    # plaza of radius 5 m at (100 m, 0) -- all hand-checkable.
    plan = {
        "buildings": [{"loc_cm": [0.0, 0.0, 0.0], "size_cm": [1000.0, 2000.0,
                                                              500.0],
                       "yaw_deg": 90.0}],
        "streets": [],
        "plaza_radius_cm": 500.0,
        "site_centre_cm": [10000.0, 0.0, 0.0],
    }
    shapes, plaza = build(plan, 0.0, 0.0, 0.0)

    # Yawed 90 deg, the 10 m (x) extent lies along WORLD Y and the 20 m
    # (y) extent along WORLD X. So +/-1000 cm in x is IN, +/-600 cm is OUT.
    for (x, y, want, why) in ((0.0, 0.0, True, "centre"),
                              (900.0, 0.0, True, "inside the long axis"),
                              (1100.0, 0.0, False, "past the long axis"),
                              (0.0, 400.0, True, "inside the short axis"),
                              (0.0, 600.0, False, "past the short axis")):
        got = inside(shapes, plaza, x, y)
        ok = got == want
        print("  yawed building (%7.1f,%7.1f) -> %-5s %-22s %s"
              % (x, y, got, why, "OK" if ok else "WRONG"))
        if not ok:
            fails.append("yawed building: (%.1f,%.1f) read %s, want %s"
                         % (x, y, got, want))

    # Plaza disc, margin 0 -> radius 5 m; margin 3 m -> radius 8 m.
    _s2, plaza2 = build(plan, 0.0, 0.0, 3.0)
    for (px, want, tag, pz) in ((10400.0, True, "4 m from centre, r=5 m",
                                 plaza),
                                (10600.0, False, "6 m from centre, r=5 m",
                                 plaza),
                                (10600.0, True, "6 m from centre, r=8 m",
                                 plaza2),
                                (10900.0, False, "9 m from centre, r=8 m",
                                 plaza2)):
        got = inside([], pz, px, 0.0)
        ok = got == want
        print("  plaza         %-28s -> %-5s %s"
              % (tag, got, "OK" if ok else "WRONG"))
        if not ok:
            fails.append("plaza: %s read %s, want %s" % (tag, got, want))

    # A margin must GROW the rectangle, not move it.
    big, _ = build(plan, 5.0, 0.0, 0.0)
    grew = inside(big, None, 1400.0, 0.0) and not inside(shapes, None,
                                                         1400.0, 0.0)
    print("  margin grows the rectangle                  -> %-5s %s"
          % (grew, "OK" if grew else "WRONG"))
    if not grew:
        fails.append("a 5 m building margin did not admit a point 14 m out")

    # BROKEN INPUT MUST REFUSE.
    for (bad, tag) in (({"buildings": [], "site_centre_cm": [0, 0, 0]},
                        "plan with no plaza_radius_cm"),):
        try:
            build(bad, 1.0, 1.0, 1.0)
            print("  %-42s -> DID NOT REFUSE  WRONG" % tag)
            fails.append("%s did not refuse" % tag)
        except RuntimeError:
            print("  %-42s -> refused          OK" % tag)
    try:
        foliage_margins({})
        print("  city recipe with no foliage_clearing       -> DID NOT "
              "REFUSE  WRONG")
        fails.append("a city recipe with no foliage_clearing did not refuse")
    except RuntimeError:
        print("  city recipe with no foliage_clearing       -> refused"
              "          OK")

    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--plan", default=os.path.join(
        REPO, "city", "alpine_basin_town_plan.json"))
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    shapes, plaza, (bm, sm, pm) = load(a.plan)
    print("margins: building %.1f m, street %.1f m, plaza %.1f m"
          % (bm, sm, pm))
    print("shapes:  %d oriented rectangles" % len(shapes))
    if plaza:
        print("plaza:   centre (%.1f, %.1f) cm, radius %.2f m"
              % (plaza[0], plaza[1], math.sqrt(plaza[2]) / 100.0))
    else:
        print("plaza:   none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
