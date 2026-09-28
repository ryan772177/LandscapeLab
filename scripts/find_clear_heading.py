"""find_clear_heading.py — which way can a straight-line walker actually go?

`walk_character.py` drives the pawn in a STRAIGHT LINE with no steering. That
was fine when the spawn stood in a forest: trees are foliage and the walker
brushes past them. It is not fine now that the spawn stands in a town made of
1,446 solid volumes, and the first run after the move proved it — 29.2 m on the
heading the PlayerStart itself faces, then a 291 s stall against the landmark.

**THE STALL WAS THE INSTRUMENT BEING RIGHT.** The PlayerStart is aimed at an
11 x 11 x 34 m tower 29 m away, deliberately, because that is the first thing a
player should see. A straight-line walker has no way around it.

So a heading has to be CHOSEN, and choosing it by eye off a top-down render is
the guess this project keeps paying for. This computes it from the committed
plan: march along each bearing and find the first structure whose footprint the
path enters.

    python scripts/find_clear_heading.py
    python scripts/find_clear_heading.py --from-cm -210800 278800 --top 8

WHAT IT DOES AND DOES NOT MODEL
-------------------------------
It models the PLANNED footprints — oriented rectangles, inflated by the pawn's
capsule radius, which is what makes contact happen at the wall rather than at
the centre.

It does NOT model terrain. A bearing that is clear of buildings can still be
blocked by a slope the walker cannot climb, and this says nothing about that.
`find_walk_heading.py` is the terrain instrument; the two answer different
halves and **a heading wants both**. That is stated rather than quietly
implied, because a "clear" verdict here is easy to read as "walkable".

It reads the PLAN, not the world. The plan is verified against the world
elsewhere (`city_verify_payload.txt`, 1446 actors, grounding max 0.0 cm), so
this is a legitimate offline shortcut — but it is one representation, and if
the two ever disagree the world wins.
"""
import argparse
import io
import json
import math
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The pawn's capsule radius comes from the character RECIPE (pipeline rule 2:
# a scene parameter is read from JSON, never hardcoded), so a change to the
# character's capsule tracks here automatically instead of drifting from a
# literal that only looked authoritative.
CHARACTER_RECIPE = os.path.join(REPO_ROOT, "recipes", "character.json")
DEFAULT_CAPSULE_RADIUS_CM = 34.0


def _capsule_radius_cm():
    try:
        d = json.load(io.open(CHARACTER_RECIPE, encoding="utf-8"))
        return float(d["capsule"]["radius_cm"])
    except Exception as e:
        sys.stderr.write(
            "WARNING: could not read capsule.radius_cm from %s (%s); using the "
            "engine default %.1f\n"
            % (CHARACTER_RECIPE, e, DEFAULT_CAPSULE_RADIUS_CM))
        return DEFAULT_CAPSULE_RADIUS_CM


def _rects(plan):
    """Every planned footprint as (cx, cy, half_x, half_y, yaw_rad, kind).

    Streets are included. A street volume is a low slab, and the walker steps
    onto it rather than into it -- but its SIZE is what the placer used, so
    excluding it here would be a judgement about walkability this tool has
    already said it does not make. They are reported separately instead, so a
    caller can see whether a bearing is blocked by a building or merely
    crosses a road.
    """
    out = []
    for sec in ("buildings", "landmark", "spire", "roofs", "streets"):
        rows = plan.get(sec)
        if rows is None:
            continue
        if isinstance(rows, dict):
            rows = [rows]
        for r in rows:
            loc = r.get("loc_cm")
            if not loc:
                continue
            size = r.get("size_cm")
            if size:
                hx, hy = float(size[0]) * 0.5, float(size[1]) * 0.5
            elif r.get("len_cm") and r.get("width_cm"):
                hx = float(r["len_cm"]) * 0.5
                hy = float(r["width_cm"]) * 0.5
            else:
                continue
            out.append((float(loc[0]), float(loc[1]), hx, hy,
                        math.radians(float(r.get("yaw_deg") or 0.0)), sec))
    return out


def _first_hit(sx, sy, dx, dy, rects, max_cm, step_cm, pad):
    """March the ray and return (distance_cm, kind) of the first footprint hit.

    A march rather than an analytic ray-box test: at the default 50 cm step
    (--step-cm) against footprints whose smallest half-extent is several metres
    nothing can be stepped over, and the code that decides containment is four
    comparisons instead of a clipping algorithm with its own edge cases. This
    project has paid for clever geometry before. (A step set much larger than a
    footprint via --step-cm could skip one; main() keeps --step-cm positive but
    does not cap it.)
    """
    d = 0.0
    while d <= max_cm:
        px, py = sx + dx * d, sy + dy * d
        for cx, cy, hx, hy, yaw, kind in rects:
            ox, oy = px - cx, py - cy
            c, s = math.cos(-yaw), math.sin(-yaw)
            lx, ly = ox * c - oy * s, ox * s + oy * c
            if abs(lx) <= hx + pad and abs(ly) <= hy + pad:
                return d, kind
        d += step_cm
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument("--plan", default="city/alpine_basin_town_plan.json")
    ap.add_argument("--from-cm", nargs=2, type=float,
                    default=[-210800.0, 278800.0],
                    help="start XY in cm; defaults to the PlayerStart")
    ap.add_argument("--max-m", type=float, default=1500.0)
    ap.add_argument("--step-cm", type=float, default=50.0)
    ap.add_argument("--bearing-step", type=float, default=1.0)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--ignore-streets", action="store_true",
                    help="treat street slabs as passable. They are low and the "
                         "walker steps onto them -- but that is a judgement "
                         "about walkability this tool otherwise refuses to "
                         "make, so it is OPT-IN and reported.")
    args = ap.parse_args()

    # A non-positive step would loop forever (d += step_cm; b += bearing_step).
    if args.step_cm <= 0 or args.bearing_step <= 0:
        sys.exit("REFUSE: --step-cm and --bearing-step must be positive.")

    capsule_cm = _capsule_radius_cm()

    path = args.plan if os.path.isabs(args.plan) else os.path.join(REPO_ROOT,
                                                                   args.plan)
    if not os.path.exists(path):
        sys.exit("REFUSE: no plan at %s" % path)
    plan = json.load(io.open(path, encoding="utf-8"))
    rects = _rects(plan)
    total_footprints = len(rects)
    if args.ignore_streets:
        rects = [r for r in rects if r[5] != "streets"]
    if not rects:
        sys.exit("REFUSE: the plan carries no footprints. That is not "
                 "'everything is clear' -- it is a plan this tool cannot read.")

    sx, sy = args.from_cm
    max_cm = args.max_m * 100.0
    print("plan        %s" % args.plan)
    print("footprints  %d%s" % (len(rects),
                                "  (streets excluded)" if args.ignore_streets
                                else ""))
    print("from        (%.0f, %.0f) cm" % (sx, sy))
    print("capsule pad %.0f cm -- contact at the WALL, not the centre "
          "(from recipes/character.json)" % capsule_cm)
    print("marching    %.0f cm steps to %.0f m" % (args.step_cm, args.max_m))
    print()

    rows = []
    b = 0.0
    while b < 360.0:
        r = math.radians(b)
        d, kind = _first_hit(sx, sy, math.cos(r), math.sin(r), rects,
                             max_cm, args.step_cm, capsule_cm)
        rows.append((b, max_cm if d is None else d, kind))
        b += args.bearing_step

    clear = [r for r in rows if r[2] is None]
    print("bearings tested   %d" % len(rows))
    print("clear to %.0f m    %d (%.1f%%)"
          % (args.max_m, len(clear), 100.0 * len(clear) / len(rows)))
    print()
    rows.sort(key=lambda t: -t[1])
    print("  %-8s %10s   %s" % ("bearing", "clear run", "first blocker"))
    for bb, dd, kk in rows[:args.top]:
        print("  %7.1f  %8.1f m   %s"
              % (bb, dd / 100.0, kk or "nothing within range"))
    print()

    if not clear:
        print("EVERY bearing is blocked within %.0f m. That is a fact about "
              "the town," % args.max_m)
        print("not a failure here: the spawn stands inside a settlement of "
              "%d volumes." % total_footprints)
        print("A straight-line walk from this point cannot leave it. Start "
              "outside, or")
        print("give the walker steering.")
        return 3

    # Report the MIDDLE of the widest clear arc, not merely the first clear
    # bearing. A bearing that is clear with blocked neighbours is a gap between
    # two buildings, and a walker with no steering will not thread it reliably.
    flags = [r[2] is None for r in sorted(rows, key=lambda t: t[0])]
    n = len(flags)
    best_len, best_mid = 0, None
    i = 0
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while j < i + n and flags[(j) % n]:
            j += 1
        run = j - i
        if run > best_len:
            best_len = run
            best_mid = ((i + run // 2) % n) * args.bearing_step
        i = j if j > i else i + 1
    print("WIDEST CLEAR ARC   %.1f deg wide, centred on bearing %.1f"
          % (best_len * args.bearing_step, best_mid))
    print("Use the CENTRE of the arc, not its edge -- a clear bearing whose")
    print("neighbours are blocked is a gap between two buildings, and a walker")
    print("with no steering will not thread it.")
    print()
    print("This says nothing about TERRAIN. A bearing clear of buildings can")
    print("still be blocked by a slope; that is find_walk_heading.py's half.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
