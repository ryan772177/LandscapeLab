"""Design a walkable pass out of the basin -- offline, read-only, measures only.

WHAT IT IS FOR
--------------
`_verify/20260826_basin_rim.md` established that the starting basin is sealed:
no natural pass on 24 bearings, and the rim is thinnest at bearings 315 and 285.
The operator ruled CUT THE RAMP. This is the design step that must come before
any terrain is touched: WHERE exactly, HOW MUCH earth, and WHAT ELSE IS THERE.

It reads `terrain/alpine_8k.png` and the landscape transform from the world
recipe. It never opens the editor and never writes a heightmap.

WHY OFFLINE
-----------
The barrier was localised in the editor by navmesh path queries, which cost ~25 s
a run and cannot be replayed cold. The TERRAIN is a PNG on disk; a profile of it
is repeatable, free, and the thing a cut actually has to change. The editor's
role comes later, and only to confirm the navmesh agrees.

  ** THE HEIGHTMAP AND THE NAVMESH ARE DIFFERENT REPRESENTATIONS, and this
     project has been bitten by trusting the first for the second (the offline
     walkable-component prefilter passed ground the built navmesh refused,
     twice). So this tool DESIGNS; it does not certify. Nothing here is a claim
     that a cut will be walkable -- only a built navmesh can say that.

WHAT A "BLOCKING SEGMENT" IS
----------------------------
The agent bar is a LOCAL gradient, evaluated by Recast at roughly its CellSize
(~19 cm here), plus a step height. A gradient averaged over 5 m read 35.71 deg
where the same ground at 0.5 m read 51.34 -- so the sampling interval is part of
the measurement and is printed with every number.

** A RAY IS A 1-D PROBE THROUGH A 2-D BARRIER, AND SUB-METRE SAMPLING OF A
   1 m HEIGHTMAP IS INTERPOLATION, NOT DATA. `terrain/alpine_8k.png` is
   8129 squared at 1 m per vertex. Sampling a ray at 0.25 m produces extra
   "blocking segments" that are bilinear artefacts of the sampler, not steps in
   the ground -- measured: bearing 315 shows 1 segment at 1 m, 4 at 0.5 m and 7
   at 0.25 m, and the new ones are 0.2 m long. Ray mode is kept for reading a
   profile; **`--corridor` is the mode that designs a cut**, because it works on
   the grid the terrain actually has and because an agent can walk AROUND a
   narrow step that a ray happens to hit.

USAGE
-----
    python scripts/design_pass.py --survey            all 24 bearings, coarse
    python scripts/design_pass.py --bearing 315       one profile, for reading
    python scripts/design_pass.py --corridor --bearing 315
                                                      the actual design
"""
import argparse
import json
import math
import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from plan_city import Terrain                                # noqa: E402
import terrain_erosion as te                                 # noqa: E402

# The plaza, and the anchor every rim measurement in this project has used.
TOWN_CM = (-210800.0, 278800.0)


def agent_bar_deg():
    """The walkable limit, DERIVED from the pawn's profile -- never typed.

    Ruling 19 was originally taken against the WORLD's primary movement mode
    and built the town's navmesh for a horse. The thing that slides is the
    pawn, so the bar comes from character.json.
    """
    ch = json.load(open(os.path.join(REPO_ROOT, "recipes", "character.json"),
                        encoding="utf-8"))
    prof = ch["navigation"]["agent_profile"]
    return float(te.MOVEMENT_PROFILES[prof]["max_slope_deg"]), prof


def profile(T, bearing_deg, from_m, to_m, step_m):
    th = math.radians(bearing_deg)
    ds = np.arange(from_m, to_m + 1e-9, step_m)
    xs = TOWN_CM[0] + ds * 100.0 * math.cos(th)
    ys = TOWN_CM[1] + ds * 100.0 * math.sin(th)
    zs = T.z_cm(xs, ys) / 100.0                  # metres
    run = step_m
    grad = np.zeros_like(zs)
    grad[1:] = np.degrees(np.arctan(np.abs(np.diff(zs)) / run))
    return ds, zs, grad


def blocking_segments(ds, zs, grad, bar):
    """Contiguous runs where the local gradient exceeds the agent bar."""
    over = grad > bar
    segs, i = [], 1
    while i < len(over):
        if not over[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(over) and over[j + 1]:
            j += 1
        segs.append({
            "from_m": float(ds[i - 1]), "to_m": float(ds[j]),
            "length_m": float(ds[j] - ds[i - 1]),
            "rise_m": float(zs[j] - zs[i - 1]),
            "max_grad_deg": float(grad[i:j + 1].max()),
            "z_from_m": float(zs[i - 1]), "z_to_m": float(zs[j]),
        })
        i = j + 1
    return segs


def cut_cost(seg, bar, margin_deg):
    """How much earth must come off this segment to bring it under the bar.

    The ramp is modelled as the SHALLOWEST straight grade that clears the rise:
    to gain `rise` at `bar - margin` degrees needs `rise / tan(target)` of run.
    If the segment is shorter than that, the extra run has to be borrowed from
    the ground either side -- which is what makes a cut wide as well as deep.
    """
    target = math.radians(bar - margin_deg)
    rise = abs(seg["rise_m"])
    need_run = rise / math.tan(target) if rise > 1e-9 else 0.0
    have = seg["length_m"]
    # peak depth of the excavation, at the top of the segment: the difference
    # between the existing surface and the ramp surface where they diverge most
    depth = max(0.0, rise - have * math.tan(target))
    return {"target_grade_deg": bar - margin_deg,
            "rise_m": rise, "run_available_m": have,
            "run_needed_m": need_run,
            "extra_run_m": max(0.0, need_run - have),
            "peak_cut_depth_m": depth}


def grid_window(T, bearing_deg, inner_m, outer_m, half_width_m):
    """Heightmap cells in a box straddling the bearing, plus their world XY.

    Returns (Z, X, Y, i0, j0) where Z is metres and X/Y are world cm. Works on
    the GRID -- one sample per heightmap vertex, no interpolation invented.
    """
    th = math.radians(bearing_deg)
    # box corners: the ray from inner to outer, widened either side
    cx, cy = TOWN_CM
    pts = []
    for d in (inner_m, outer_m):
        for s in (-half_width_m, half_width_m):
            pts.append((cx + d * 100.0 * math.cos(th) - s * 100.0
                        * math.sin(th),
                        cy + d * 100.0 * math.sin(th) + s * 100.0
                        * math.cos(th)))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    i0 = int(math.floor((min(xs) - T.ox) / T.px))
    i1 = int(math.ceil((max(xs) - T.ox) / T.px))
    j0 = int(math.floor((min(ys) - T.oy) / T.px))
    j1 = int(math.ceil((max(ys) - T.oy) / T.px))
    i0, i1 = max(i0, 0), min(i1, T.w - 1)
    j0, j1 = max(j0, 0), min(j1, T.h - 1)
    Z = T.H[j0:j1 + 1, i0:i1 + 1].astype(np.float64) * (T.zs / 65535.0) / 100.0
    ii = np.arange(i0, i1 + 1)
    jj = np.arange(j0, j1 + 1)
    X = T.ox + ii * T.px
    Y = T.oy + jj * T.px
    return Z, X, Y, i0, j0


def quad_slope_deg(Z, cell_m):
    """Slope of each landscape QUAD, from FORWARD differences.

    Shape is (ny-1, nx-1): one value per quad, which is the thing an agent
    stands on, not per vertex.

    ** TWO WAYS TO GET THIS WRONG, AND THIS PROJECT MADE BOTH IN ONE SITTING.**

    1. PER-AXIS. Testing dz/dx and dz/dy separately passes a quad rising 0.9 m
       in x AND 0.9 m in y, which is really 1.27 m over 1 m = 51.8 deg. A
       per-axis test understates slope by up to sqrt(2).

    2. CENTRAL DIFFERENCES. `np.gradient` computes (z[i+1] - z[i-1]) / 2h,
       which HALVES a one-cell step -- a 1.5 m riser between adjacent vertices
       reads as 0.75. It smooths away exactly the sub-metre steps that are the
       barrier here.

    Both errors point the same way: they make the ground look flatter than the
    agent finds it, and both produced "the basin is already connected" against
    a navmesh that says it is sealed.
    """
    z00 = Z[:-1, :-1]
    z10 = Z[:-1, 1:]
    z01 = Z[1:, :-1]
    z11 = Z[1:, 1:]
    dzdx = ((z10 + z11) - (z00 + z01)) * 0.5 / cell_m
    dzdy = ((z01 + z11) - (z00 + z10)) * 0.5 / cell_m
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def slope_deg(Z, cell_m):
    """UNUSED — the live slope test is quad_slope_deg (forward differences).

    Retained as the REJECTED gradient-magnitude variant: np.gradient below
    uses CENTRAL differences, which halve a one-cell step and smooth away the
    sub-metre risers that are the barrier here — the very error quad_slope_deg's
    docstring names as way (2). Gradient magnitude is the right CONCEPT (it is
    the triangle-normal slope), but np.gradient is the wrong IMPLEMENTATION of
    it, so this is NOT a faithful Recast test despite the note below;
    quad_slope_deg gets the same magnitude from forward differences instead.

    Surface slope per cell, from the 2-D GRADIENT MAGNITUDE.

    ** NOT A PER-AXIS TEST, and the difference is not small. ** The first
    version of this checked dz/dx and dz/dy separately and passed a cell if
    each was under the bar. A cell rising 0.9 m in x AND 0.9 m in y passes both
    and is really sqrt(0.9^2 + 0.9^2) = 1.27 m over 1 m -- 51.8 deg against a
    44.765 bar. A per-axis test understates slope by up to sqrt(2): 45 deg on
    each axis is 54.7 deg of actual surface.

    Recast tests the TRIANGLE NORMAL, which is the gradient magnitude, so the
    per-axis version was not a conservative approximation of the agent -- it
    was a different and more permissive test, and it declared the sealed basin
    89.6% walkable and connected.
    """
    gy, gx = np.gradient(Z, cell_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def walkable_mask(Z, cell_m, bar_deg):
    """True where the surface slope is at or under the agent bar.

    Fail-closed at the border -- an edge cell whose neighbour is outside the
    window is UNKNOWN, and unknown is not walkable.
    """
    ok = quad_slope_deg(Z, cell_m) <= bar_deg
    ok[0, :] = ok[-1, :] = ok[:, 0] = ok[:, -1] = False
    return ok


def cut_needed(Z, cell_m, bar_deg):
    """Per cell, the largest height EXCESS over the bar against a neighbour.

    This is the cheap proxy for "how much earth has to come off here". It is a
    lower bound, not a volume: flattening one cell changes its neighbours'
    gradients too, so the real excavation is solved by the path, not summed
    from this field.
    """
    lim = math.tan(math.radians(bar_deg)) * cell_m
    rise = np.tan(np.radians(quad_slope_deg(Z, cell_m))) * cell_m
    return np.maximum(rise - lim, 0.0)


def cheapest_crossing(cost, start_cells, goal_mask):
    """Dijkstra: the path from any start cell to any goal cell that removes the
    least earth. Cost of entering a cell is its excess; walkable cells are free.

    This is the design question stated exactly: not "where is the rim thinnest"
    but "where does a corridor cost least", which is not the same thing -- a
    thicker rim with a shallower step is cheaper to cut than a thin cliff.
    """
    import heapq
    ny, nx = cost.shape
    INF = float("inf")
    dist = np.full(cost.shape, INF)
    prev = {}
    pq = []
    for (j, i) in start_cells:
        if dist[j, i] > 0.0:
            dist[j, i] = 0.0
            heapq.heappush(pq, (0.0, j, i))
    goal = None
    while pq:
        d, j, i = heapq.heappop(pq)
        if d > dist[j, i]:
            continue
        if goal_mask[j, i]:
            goal = (j, i)
            break
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nj, ni = j + dj, i + di
            if not (0 <= nj < ny and 0 <= ni < nx):
                continue
            nd = d + float(cost[nj, ni])
            if nd < dist[nj, ni]:
                dist[nj, ni] = nd
                prev[(nj, ni)] = (j, i)
                heapq.heappush(pq, (nd, nj, ni))
    if goal is None:
        return None, None
    path = [goal]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    path.reverse()
    return path, float(dist[goal])


def corridor_mode(T, bar, args):
    from scipy import ndimage

    b = args.bearing
    Z, X, Y, i0, j0 = grid_window(T, b, args.from_m, args.to_m,
                                  args.half_width_m)
    cell = T.px / 100.0
    design_bar = bar - args.margin_deg
    ok = walkable_mask(Z, cell, bar)
    ex = cut_needed(Z, cell, design_bar)
    # The masks live on the QUAD grid -- one smaller than the vertex grid in
    # each axis, because a quad is the thing you stand on. Coordinates must
    # move to quad CENTRES or every index is off by half a cell and the
    # reported world position of a cut is wrong by 50 cm.
    X = X[:-1] + T.px * 0.5
    Y = Y[:-1] + T.px * 0.5
    Zc = 0.25 * (Z[:-1, :-1] + Z[:-1, 1:] + Z[1:, :-1] + Z[1:, 1:])

    print("CORRIDOR DESIGN, bearing %.0f" % b)
    print("  window     %d x %d quads at %.2f m  (%.0f x %.0f m)"
          % (ok.shape[1], ok.shape[0], cell, ok.shape[1] * cell,
             ok.shape[0] * cell))
    print("  elevation  %.1f to %.1f m" % (Zc.min(), Zc.max()))
    print("  walkable   %.1f%% of cells at the %.3f deg agent bar"
          % (100.0 * ok.mean(), bar))
    print()

    # inside = the component containing the near end of the ray; outside = any
    # walkable cell beyond the outer radius
    lab, n = ndimage.label(ok)
    th = math.radians(b)
    ax = TOWN_CM[0] + args.from_m * 100.0 * math.cos(th)
    ay = TOWN_CM[1] + args.from_m * 100.0 * math.sin(th)
    ai = int(round((ax - X[0]) / T.px))
    aj = int(round((ay - Y[0]) / T.px))
    ai = min(max(ai, 0), ok.shape[1] - 1)
    aj = min(max(aj, 0), ok.shape[0] - 1)
    home = int(lab[aj, ai])
    if home == 0:
        print("  REFUSE: the inner anchor cell is itself unwalkable, so there "
              "is no")
        print("  inside component to start from. Move --from-m inward.")
        return 1

    inside = (lab == home)
    # goal: walkable cells in the outer 15% of the window, NOT in `inside`
    dist_m = np.hypot(X[None, :] - TOWN_CM[0], Y[:, None] - TOWN_CM[1]) / 100.0
    outer = dist_m >= (args.to_m - 0.15 * (args.to_m - args.from_m))
    goal = ok & outer & ~inside
    print("  inside component   %d cells (%.2f ha)"
          % (inside.sum(), inside.sum() * cell * cell / 10000.0))
    print("  candidate outside  %d walkable cells beyond %.0f m"
          % (int(goal.sum()), args.to_m - 0.15 * (args.to_m - args.from_m)))
    if goal.sum() == 0:
        print()
        print("  NO WALKABLE GROUND beyond the rim in this window. A pass here")
        print("  would open onto ground that is itself unwalkable -- widen "
              "--to-m")
        print("  or pick another bearing.")
        return 1
    if inside.sum() and (inside & outer).any():
        print()
        print("  ALREADY CONNECTED in this model: the inside component "
              "already reaches")
        print("  the outer band. The heightmap model and the built navmesh "
              "disagree,")
        print("  and the navmesh is the authority. Do not cut on this.")
        return 1

    cost = np.where(inside, 0.0, ex)
    starts = [(int(j), int(i)) for j, i in zip(*np.where(inside))]
    path, total = cheapest_crossing(cost, starts, goal)
    if path is None:
        print("  REFUSE: no crossing found inside this window.")
        return 1

    cut = [(k, float(ex[j, i])) for k, (j, i) in enumerate(path)
           if ex[j, i] > 1e-6]
    print()
    print("  CHEAPEST CROSSING  %d cells long, total excess %.2f m"
          % (len(path), total))
    print("  cells needing a cut: %d, deepest %.2f m"
          % (len(cut), max((c for _, c in cut), default=0.0)))
    print()
    jj, ii = path[0]
    print("  enters the barrier near (%.0f, %.0f) cm, %.0f m out"
          % (X[ii], Y[jj], dist_m[jj, ii]))
    jj, ii = path[-1]
    print("  exits  onto walkable ground (%.0f, %.0f) cm, %.0f m out"
          % (X[ii], Y[jj], dist_m[jj, ii]))
    print()
    print("  Cells over the design bar of %.2f deg, along the route:"
          % design_bar)
    print("    %-6s %-12s %-12s %8s %9s" % ("idx", "world x cm", "world y cm",
                                            "dist_m", "cut_m"))
    for k, c in cut[:25]:
        j, i = path[k]
        print("    %-6d %-12.0f %-12.0f %8.0f %9.2f"
              % (k, X[i], Y[j], dist_m[j, i], c))
    if len(cut) > 25:
        print("    ... and %d more" % (len(cut) - 25))
    print()
    print("  A CORRIDOR NEEDS WIDTH. This is a single-cell route; a usable "
          "path is")
    print("  %.0f m wide, so the excavation is roughly this profile swept "
          "sideways." % args.path_width_m)
    print()
    print("  HEIGHTMAP MODEL ONLY. The navmesh is built from COLLISION and has")
    print("  refused ground this class of model passed, twice. Nothing here is")
    print("  a claim that a cut will be walkable.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corridor", action="store_true",
                    help="grid-based 2-D design: the cheapest crossing")
    ap.add_argument("--half-width-m", type=float, default=120.0,
                    help="how far either side of the bearing to search")
    ap.add_argument("--path-width-m", type=float, default=4.0)
    ap.add_argument("--bearing", type=float, default=315.0)
    ap.add_argument("--from-m", type=float, default=150.0)
    ap.add_argument("--to-m", type=float, default=600.0)
    ap.add_argument("--step-m", type=float, default=0.5)
    ap.add_argument("--margin-deg", type=float, default=5.0,
                    help="how far UNDER the agent bar to design, so the cut "
                         "is not decided by the last decimal place")
    ap.add_argument("--survey", action="store_true",
                    help="all 24 bearings at coarse spacing, ranked by how "
                         "little earth has to move")
    args = ap.parse_args()

    world = json.load(open(os.path.join(REPO_ROOT, "recipes",
                                        "alpine_8k.json"), encoding="utf-8"))
    T = Terrain(world)
    bar, prof = agent_bar_deg()

    print("terrain    %s  %dx%d" % (world["heightmap"]["source"], T.w, T.h))
    print("agent bar  %.3f deg, profile %r, from recipes/character.json"
          % (bar, prof))
    print("design to  %.3f deg (%.1f deg of margin)"
          % (bar - args.margin_deg, args.margin_deg))
    print("anchor     the plaza (%.0f, %.0f) cm" % TOWN_CM)
    print()

    if args.corridor:
        return corridor_mode(T, bar, args)

    bearings = ([15.0 * i for i in range(24)] if args.survey
                else [args.bearing])
    step = 2.0 if args.survey else args.step_m

    rows = []
    for b in bearings:
        ds, zs, grad = profile(T, b, args.from_m, args.to_m, step)
        segs = blocking_segments(ds, zs, grad, bar)
        total_extra = sum(cut_cost(s, bar, args.margin_deg)["extra_run_m"]
                          for s in segs)
        worst = max((s["max_grad_deg"] for s in segs), default=0.0)
        rows.append({"bearing": b, "segments": len(segs),
                     "blocked_m": sum(s["length_m"] for s in segs),
                     "total_rise_m": sum(abs(s["rise_m"]) for s in segs),
                     "extra_run_m": total_extra, "max_grad": worst,
                     "segs": segs})

    if args.survey:
        print("SURVEY at %.1f m sampling -- a RANKING, not a design. Re-run a "
              "single bearing" % step)
        print("at 0.5 m before cutting: coarse sampling understates a "
              "sub-metre step.")
        print()
        print("  bearing  blocking  blocked_m  rise_m  extra_run_m  max_grad")
        for r in sorted(rows, key=lambda r: r["extra_run_m"]):
            print("     %5.0f  %8d  %9.1f  %6.1f  %11.1f  %8.2f"
                  % (r["bearing"], r["segments"], r["blocked_m"],
                     r["total_rise_m"], r["extra_run_m"], r["max_grad"]))
        return 0

    r = rows[0]
    print("BEARING %.0f, %.0f-%.0f m at %.2f m sampling"
          % (r["bearing"], args.from_m, args.to_m, step))
    print("  blocking segments %d, %.1f m of blocked ground, %.1f m of rise"
          % (r["segments"], r["blocked_m"], r["total_rise_m"]))
    print()
    if not r["segs"]:
        print("  NOTHING OVER THE BAR on this bearing at this sampling. That "
              "is not a pass:")
        print("  the navmesh is built from COLLISION and has refused ground "
              "this model passed")
        print("  twice. Confirm in the editor before believing it.")
        return 0

    print("  %-16s %7s %7s %8s %9s %10s %9s"
          % ("segment", "len_m", "rise_m", "max_deg", "need_run", "extra_run",
             "cut_depth"))
    for s in r["segs"]:
        c = cut_cost(s, bar, args.margin_deg)
        print("  %6.1f-%-8.1f %7.1f %7.2f %8.2f %9.1f %10.1f %9.2f"
              % (s["from_m"], s["to_m"], s["length_m"], s["rise_m"],
                 s["max_grad_deg"], c["run_needed_m"], c["extra_run_m"],
                 c["peak_cut_depth_m"]))
    print()
    tot = sum(cut_cost(s, bar, args.margin_deg)["extra_run_m"]
              for s in r["segs"])
    deep = max(cut_cost(s, bar, args.margin_deg)["peak_cut_depth_m"]
               for s in r["segs"])
    print("  TOTAL extra run needed %.1f m, deepest cut %.2f m" % (tot, deep))
    print()
    print("  This is a HEIGHTMAP measurement. It says what the terrain does,")
    print("  not what the navmesh will do with it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
