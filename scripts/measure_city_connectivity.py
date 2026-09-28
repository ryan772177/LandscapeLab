"""measure_city_connectivity.py -- is the town's street network one network?

READ-ONLY. Reads a city plan JSON and reports the connected components of its
street graph. Writes nothing, touches no editor, spawns nothing.

=====================================================================
WHY THIS EXISTS
=====================================================================
`plan_city.py` gates each street segment INDEPENDENTLY on its own slope
(:139-196). That is correct as far as it goes -- a street bar must be tighter
than a building bar, because a pad can be terraced and a street cannot -- but
rejecting segments one at a time punches holes in a lattice, and a lattice with
holes is not a network. The 2026-08-24 commit named the consequence in its own
message and left it open:

    "gating each street segment INDEPENDENTLY breaks CONNECTIVITY, so the
     outer streets are stubs. A town whose streets do not join is not
     navigable. ... Not done."

Nothing measured how bad it was. This measures it.

=====================================================================
WHAT CONNECTS TO WHAT, AND WHY IT IS NOT AN ENDPOINT GRAPH
=====================================================================
The obvious implementation -- merge shared endpoints -- IS WRONG HERE, and
would report a far more broken town than exists.

Ring segments lie at radii  core + i*spacing.
Spoke segments are cut at   plaza + (R - plaza)*k/14.

Those two families do not share endpoints. A spoke CROSSES a ring in the middle
of both segments. An endpoint graph would see every ring and every spoke as
mutually disconnected and report ~459 components, which would be an artefact of
the representation and not a fact about the town.

So connectivity is GEOMETRIC: two segments are joined when their centrelines
pass within `--tol-cm` of each other, computed as a true segment-to-segment
distance. Two 7 m-wide paved strips whose centrelines pass within 7 m overlap
on the ground, and a person can walk from one to the other.

THE TOLERANCE IS A KNOB, SO ITS SENSITIVITY IS REPORTED. A component count that
moves when the tolerance moves is a statement about the knob, not about the
town. `--sweep` runs the measurement across a range and prints the table.

=====================================================================
FAIL CLOSED
=====================================================================
A plan missing `streets`, or a segment missing loc/yaw/len, is a REFUSAL
(exit 3) and never a zero. "I could not look" is not "the town is connected".

Exit codes:
  0  measured; findings printed
  2  bad arguments / plan file missing
  3  refuse: plan is missing fields this cannot be computed without
  4  selftest failed
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PLAN = os.path.join(REPO_ROOT, "city", "alpine_basin_town_plan.json")


# --- geometry ----------------------------------------------------------

def endpoints(seg):
    """Reconstruct a segment's two ends from its midpoint, yaw and length.

    The plan stores segments as (midpoint, yaw, length) for BOTH kinds, and
    for both the yaw is the direction the segment RUNS: tangential for a ring
    (mid angle + 90), radial for a spoke. So one formula serves both.

    A ring segment is a CHORD approximation of an arc, so an end computed this
    way sits up to r*(dtheta^2)/8 inside the true arc end -- about 0.5 m at
    this town's radii and segment counts. That is well inside any sane
    tolerance and is why the tolerance sweep matters.
    """
    mx, my = float(seg["loc_cm"][0]), float(seg["loc_cm"][1])
    a = math.radians(float(seg["yaw_deg"]))
    h = 0.5 * float(seg["len_cm"])
    dx, dy = h * math.cos(a), h * math.sin(a)
    return (mx - dx, my - dy), (mx + dx, my + dy)


def seg_seg_dist(p1, p2, p3, p4):
    """Minimum distance between 2D segments p1p2 and p3p4."""
    ux, uy = p2[0] - p1[0], p2[1] - p1[1]
    vx, vy = p4[0] - p3[0], p4[1] - p3[1]
    wx, wy = p1[0] - p3[0], p1[1] - p3[1]

    a = ux * ux + uy * uy
    b = ux * vx + uy * vy
    c = vx * vx + vy * vy
    d = ux * wx + uy * wy
    e = vx * wx + vy * wy
    den = a * c - b * b

    if den < 1e-9:  # parallel or degenerate
        sN, sD = 0.0, 1.0
        tN, tD = e, c if c > 1e-9 else 1.0
    else:
        sN, sD = (b * e - c * d), den
        tN, tD = (a * e - b * d), den
        if sN < 0.0:
            sN, tN, tD = 0.0, e, c if c > 1e-9 else 1.0
        elif sN > sD:
            sN, tN, tD = sD, e + b, c if c > 1e-9 else 1.0

    if tN < 0.0:
        tN = 0.0
        if -d < 0.0:
            sN = 0.0
        elif -d > a:
            sN = sD
        else:
            sN, sD = -d, a if a > 1e-9 else 1.0
    elif tN > tD:
        tN = tD
        if (-d + b) < 0.0:
            sN = 0.0
        elif (-d + b) > a:
            sN = sD
        else:
            sN, sD = (-d + b), a if a > 1e-9 else 1.0

    sc = 0.0 if abs(sD) < 1e-9 else sN / sD
    tc = 0.0 if abs(tD) < 1e-9 else tN / tD

    cx = wx + sc * ux - tc * vx
    cy = wy + sc * uy - tc * vy
    return math.hypot(cx, cy)


def components(segs, tol_cm):
    """Connected components of the segment graph, by union-find."""
    n = len(segs)
    ends = [endpoints(s) for s in segs]
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # Broad-phase on midpoint distance: two segments cannot be within tol if
    # their midpoints are further apart than half their lengths plus tol.
    for i in range(n):
        (ax, ay), (bx, by) = ends[i]
        mi = (0.5 * (ax + bx), 0.5 * (ay + by))
        hi = 0.5 * float(segs[i]["len_cm"])
        for j in range(i + 1, n):
            (cx2, cy2), (dx2, dy2) = ends[j]
            mj = (0.5 * (cx2 + dx2), 0.5 * (cy2 + dy2))
            hj = 0.5 * float(segs[j]["len_cm"])
            if math.hypot(mi[0] - mj[0], mi[1] - mj[1]) > hi + hj + tol_cm:
                continue
            if seg_seg_dist(ends[i][0], ends[i][1], ends[j][0], ends[j][1]) <= tol_cm:
                union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=len, reverse=True)


# --- selftest ----------------------------------------------------------

def selftest():
    """Prove the instrument discriminates, in BOTH directions.

    A component counter that always returns 1 would report this town as
    perfectly connected. A counter that always returns n would report it as
    rubble. Neither failure is visible on real input, so both are tested.
    """
    ok = True

    # (a) a chain that genuinely touches end to end -> exactly ONE component
    chain = [{"loc_cm": [i * 1000.0 + 500.0, 0.0, 0.0], "yaw_deg": 0.0,
              "len_cm": 1000.0} for i in range(6)]
    got = len(components(chain, 100.0))
    print("  selftest chain of 6 touching segments -> %d component(s), want 1  %s"
          % (got, "OK" if got == 1 else "FAIL"))
    ok &= (got == 1)

    # (b) the SAME six, moved far apart -> exactly SIX components
    apart = [{"loc_cm": [i * 100000.0, 0.0, 0.0], "yaw_deg": 0.0,
              "len_cm": 1000.0} for i in range(6)]
    got = len(components(apart, 100.0))
    print("  selftest 6 far-apart segments        -> %d component(s), want 6  %s"
          % (got, "OK" if got == 6 else "FAIL"))
    ok &= (got == 6)

    # (c) a CROSSING pair sharing no endpoint -> ONE component. This is the
    #     ring-crosses-spoke case, and the case an endpoint graph gets wrong.
    cross = [{"loc_cm": [0.0, 0.0, 0.0], "yaw_deg": 0.0, "len_cm": 2000.0},
             {"loc_cm": [0.0, 0.0, 0.0], "yaw_deg": 90.0, "len_cm": 2000.0}]
    got = len(components(cross, 10.0))
    print("  selftest crossing pair, no shared end-> %d component(s), want 1  %s"
          % (got, "OK" if got == 1 else "FAIL"))
    ok &= (got == 1)

    # (d) a gap WIDER than tolerance stays broken -> TWO components
    gap = [{"loc_cm": [0.0, 0.0, 0.0], "yaw_deg": 0.0, "len_cm": 1000.0},
           {"loc_cm": [3000.0, 0.0, 0.0], "yaw_deg": 0.0, "len_cm": 1000.0}]
    got = len(components(gap, 700.0))
    print("  selftest 20 m gap at 7 m tolerance   -> %d component(s), want 2  %s"
          % (got, "OK" if got == 2 else "FAIL"))
    ok &= (got == 2)

    return ok


# --- main --------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", default=DEFAULT_PLAN)
    ap.add_argument("--tol-cm", type=float, default=700.0,
                    help="centreline separation at which two streets are joined "
                         "(default 700 = one street width)")
    ap.add_argument("--sweep", action="store_true",
                    help="report component count across a range of tolerances")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        print("SELFTEST")
        ok = selftest()
        print("SELFTEST %s" % ("PASSED" if ok else "FAILED"))
        return 0 if ok else 4

    if not os.path.isfile(a.plan):
        print("REFUSE: no plan at %s" % a.plan)
        return 2

    with open(a.plan, "r", encoding="utf-8") as fh:
        plan = json.load(fh)

    segs = plan.get("streets")
    if not isinstance(segs, list) or not segs:
        print("REFUSE: plan has no 'streets' list. This is 'I could not look', "
              "not 'the network is connected'.")
        return 3
    for i, s in enumerate(segs):
        for k in ("loc_cm", "yaw_deg", "len_cm"):
            if k not in s:
                print("REFUSE: street[%d] is missing %r" % (i, k))
                return 3

    cx, cy = plan["site_centre_cm"][0], plan["site_centre_cm"][1]

    print("PLAN     %s" % os.path.relpath(a.plan, REPO_ROOT))
    print("city_id  %s" % plan.get("city_id"))
    print("segments %d  (ring %d, spoke %d)"
          % (len(segs),
             sum(1 for s in segs if s.get("kind") == "ring"),
             sum(1 for s in segs if s.get("kind") == "spoke")))
    c = plan.get("counts", {})
    if "streets_rejected_slope" in c:
        # plans written before 2026-08-25, when one number covered a metric
        # that was measuring roughness rather than grade
        print("rejected (legacy single 'slope' count): %s"
              % c["streets_rejected_slope"])
    else:
        print("refused  grade %s, cut/fill %s;  pruned unreachable %s"
              % (c.get("streets_rejected_grade"),
                 c.get("streets_rejected_cutfill"),
                 c.get("streets_pruned_disconnected")))
    print("")

    if a.sweep:
        print("TOLERANCE SENSITIVITY -- a count that moves with the knob is "
              "about the knob")
        print("  tol_cm   components   largest   largest_share")
        for tol in (200.0, 350.0, 500.0, 700.0, 1000.0, 1500.0):
            comps = components(segs, tol)
            print("  %6.0f   %10d   %7d   %11.1f%%"
                  % (tol, len(comps), len(comps[0]),
                     100.0 * len(comps[0]) / len(segs)))
        print("")

    comps = components(segs, a.tol_cm)
    total_len = sum(float(s["len_cm"]) for s in segs)

    print("AT tol_cm = %.0f" % a.tol_cm)
    print("  components        %d" % len(comps))
    print("  largest           %d segments (%.1f%% of all)"
          % (len(comps[0]), 100.0 * len(comps[0]) / len(segs)))

    big = comps[0]
    big_len = sum(float(segs[i]["len_cm"]) for i in big)
    print("  largest length    %.0f m of %.0f m total (%.1f%%)"
          % (big_len / 100.0, total_len / 100.0,
             100.0 * big_len / total_len))

    # does the largest component actually contain the town centre?
    def radius(i):
        mx, my = float(segs[i]["loc_cm"][0]), float(segs[i]["loc_cm"][1])
        return math.hypot(mx - cx, my - cy)

    innermost = min(range(len(segs)), key=radius)
    home = next(k for k, c in enumerate(comps) if innermost in c)
    print("  innermost segment r=%.0f m sits in component #%d (%s)"
          % (radius(innermost) / 100.0, home,
             "THE LARGEST" if home == 0 else "NOT the largest"))

    orphan = len(segs) - len(comps[0])
    orphan_len = total_len - big_len
    print("")
    print("  STRANDED          %d segments, %.0f m of street"
          % (orphan, orphan_len / 100.0))
    if len(comps) > 1:
        sizes = [len(c) for c in comps[1:]]
        print("  stranded pieces   %d, sizes %s%s"
              % (len(sizes), sizes[:15], " ..." if len(sizes) > 15 else ""))
        rr = [radius(c[0]) / 100.0 for c in comps[1:]]
        print("  their radii       %.0f m .. %.0f m (town core is r=0)"
              % (min(rr), max(rr)))
    print("")
    print("VERDICT  %s"
          % ("ONE NETWORK" if len(comps) == 1 else
             "FRAGMENTED -- %d pieces; %d of %d segments cannot be walked to "
             "from the centre" % (len(comps), orphan, len(segs))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
