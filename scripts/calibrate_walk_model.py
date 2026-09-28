"""Does the offline walkability model predict the BUILT navmesh? Measure it.

The offline heightmap model has now been wrong about this terrain three times:
it passed encounters the navmesh refused at two different agents, it claimed the
plaza's walkable component reached 2480 m where the navmesh reaches 300, and it
called the sealed basin "already connected". Each time it was labelled a
PREFILTER and not trusted -- correctly -- but nobody ever measured HOW wrong it
is, or whether a corrected model does any better.

`scripts/city_nav_grid_payload.txt` produces ground truth: a grid of points with
`projects` and `reachable` read from the BUILT navmesh. This scores the offline
model against that grid, cell for cell.

WHAT IT REPORTS
---------------
A confusion table of model-walkable against navmesh-reachable, and the same for
model-walkable against navmesh-PROJECTS. The second is the fairer test of the
slope model alone: reachability also depends on connectivity, which a per-cell
slope test does not attempt.

WHY IT MATTERS FOR CUTTING A PASS
---------------------------------
A cut is designed offline and costs a terrain edit, a Nanite rebuild and a
navmesh rebuild to test. If the model cannot predict the navmesh on ground that
already exists, a cut designed on it is a guess with a large blast radius.

    ** THIS IS A CALIBRATION, NOT A GATE. ** It says how far the model can be
       trusted. It does not make the model an authority; the navmesh remains
       the authority, and the model's job is to narrow where to spend an
       expensive build.
"""
import argparse
import io
import json
import math
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from plan_city import Terrain                                # noqa: E402
from design_pass import quad_slope_deg, TOWN_CM              # noqa: E402
import terrain_erosion as te                                 # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("grid", help="output of city_nav_grid_payload.txt")
    ap.add_argument("--bar-deg", type=float, default=None,
                    help="override the agent bar; default reads the grid's "
                         "own recorded agent_max_slope")
    args = ap.parse_args()

    d = json.loads(io.open(args.grid, encoding="utf-8").read())
    g = d["grid"]
    bar = args.bar_deg if args.bar_deg is not None else float(
        d["agent_max_slope"])

    world = json.loads(io.open(os.path.join(REPO_ROOT, "recipes",
                                            "alpine_8k.json"),
                               encoding="utf-8").read())
    T = Terrain(world)
    cell = T.px / 100.0

    th = math.radians(g["bearing_deg"])
    fwd = (math.cos(th), math.sin(th))
    lat = (-math.sin(th), math.cos(th))

    # model slope at each probed point, from the quad the point falls in
    rows = d["rows"]
    model_ok, nav_proj, nav_reach, slopes = [], [], [], []
    for r in rows:
        dm, sm = r[0], r[1]
        x = TOWN_CM[0] + (dm * fwd[0] + sm * lat[0]) * 100.0
        y = TOWN_CM[1] + (dm * fwd[1] + sm * lat[1]) * 100.0
        i = int((x - T.ox) / T.px)
        j = int((y - T.oy) / T.px)
        if not (1 <= i < T.w - 2 and 1 <= j < T.h - 2):
            continue
        Z = T.H[j - 1:j + 3, i - 1:i + 3].astype(np.float64) \
            * (T.zs / 65535.0) / 100.0
        s = float(quad_slope_deg(Z, cell).max())
        slopes.append(s)
        model_ok.append(s <= bar)
        nav_proj.append(bool(r[3]))
        nav_reach.append(bool(r[4]))

    model_ok = np.array(model_ok)
    nav_proj = np.array(nav_proj)
    nav_reach = np.array(nav_reach)
    n = len(model_ok)

    print("CALIBRATION of the offline walk model against the BUILT navmesh")
    print("  grid       bearing %.0f, %.0f-%.0f m, +-%.0f m, step %.0f m"
          % (g["bearing_deg"], g["from_m"], g["to_m"], g["half_width_m"],
             g["step_m"]))
    print("  points     %d usable of %d probed" % (n, len(rows)))
    print("  agent bar  %.3f deg (from the grid's own record)" % bar)
    print("  model      max quad slope in the 3x3 of quads around the point")
    print()

    def table(truth, name):
        tp = int((model_ok & truth).sum())
        fp = int((model_ok & ~truth).sum())
        fn = int((~model_ok & truth).sum())
        tn = int((~model_ok & ~truth).sum())
        print("  model vs navmesh %s" % name)
        print("                       nav YES    nav NO")
        print("    model walkable   %8d  %8d" % (tp, fp))
        print("    model blocked    %8d  %8d" % (fn, tn))
        agree = (tp + tn) / float(n) if n else 0.0
        print("    agreement %.1f%%" % (100.0 * agree))
        if fp:
            print("    ** %d points the model calls walkable and the navmesh "
                  "does not." % fp)
            print("       The model is OPTIMISTIC here, which is the "
                  "direction that")
            print("       designs a pass through ground the agent cannot use.")
        print()
        return fp

    fp_proj = table(nav_proj, "PROJECTS (is there a polygon)")
    fp_reach = table(nav_reach, "REACHABLE (can you get there)")

    s = np.array(slopes)
    print("  model slope over the probed points:")
    print("    min %.2f  p50 %.2f  p90 %.2f  max %.2f deg"
          % (s.min(), np.percentile(s, 50), np.percentile(s, 90), s.max()))
    print("    over the bar: %d of %d (%.1f%%)"
          % (int((s > bar).sum()), n, 100.0 * (s > bar).mean()))
    print()

    if fp_reach > 0.25 * n:
        print("VERDICT: THE MODEL CANNOT PREDICT REACHABILITY on this ground.")
        print("It calls %.0f%% of unreachable points walkable. A pass designed"
              % (100.0 * fp_reach / n))
        print("on it would be a guess. Reachability is a CONNECTIVITY property")
        print("and a per-cell slope test does not attempt connectivity -- so")
        print("this is a statement about what the model is FOR, not only about")
        print("its accuracy.")
    else:
        print("VERDICT: the model tracks the navmesh on this window.")
    print()
    print("Either way the navmesh remains the authority. This calibration")
    print("bounds how much an offline design can be trusted BEFORE paying for")
    print("a terrain edit and two rebuilds to find out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
