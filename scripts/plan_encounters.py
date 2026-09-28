"""plan_encounters.py -- PHASE2_PLAN unit 9. Where encounters stand.

    python scripts/plan_encounters.py --recipe recipes/encounters.json
    python scripts/plan_encounters.py --selftest

OFFLINE AND SEEDED, so it produces the same plan every run and can be replayed
without an editor -- the same contract as foliage/*.json and city/*_plan.json:
absolute-cm transforms in plain JSON that the consumer reads and does not
re-derive.

WHAT THIS IS NOT. It is not enemies, not AI and not spawning. Units 10 and 12
own those and neither exists. This writes down WHERE, so that when they do
exist there is versioned, testable data underneath them.

=====================================================================
THE TWO GATES, AND WHY ONE OF THEM CANNOT LIVE HERE
=====================================================================
(a) SEPARATION is offline and lives in this file. Poisson-disc at aggro+leash,
    computed PER PAIR rather than as one global radius, because a highland
    beast needs 130 m of clearance and a scavenger 70.

(b) REACHABILITY cannot live here and must not be faked here. This script reads
    the HEIGHTMAP; the navmesh is built from COLLISION. Checking reachability
    against the heightmap would be one source checked twice -- exactly how this
    project rendered v2 while colliding v1 for three days with every gate green.
    The reachability gate is `scripts/city_encounter_verify_payload.txt`, in the
    editor, against the BUILT navmesh.

=====================================================================
THE TOWN IS NOT RE-DESCRIBED HERE
=====================================================================
The settlement exclusion derives from the committed city plan's own geometry,
tested as oriented rectangles plus a margin -- the same test the foliage clear
uses. Two definitions of "where the town is" would be two lists that must
agree, which is non-negotiable 24 and fails the same way every time.

Exit codes:
    0  planned, all gates passed
    2  bad arguments / missing input
    3  refuse: a gate failed
    4  selftest failed
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plan_stamp                                # noqa: E402
import reachability                              # noqa: E402
import terrain_erosion as te                     # noqa: E402
from plan_city import Terrain                    # noqa: E402


# --- settlement exclusion, derived from the city plan ------------------

def city_shapes(plan, build_margin_cm, street_margin_cm):
    """Oriented rectangles for every structure, plus a margin.

    Same construction as scripts/city_clear_foliage_payload.txt. The town is
    defined ONCE, in city/<id>_plan.json, and both consumers read it.
    """
    shapes = []
    for b in plan["buildings"]:
        sx, sy, _sz = b["size_cm"]
        shapes.append((b["loc_cm"][0], b["loc_cm"][1],
                       math.radians(b["yaw_deg"]),
                       sx * 0.5 + build_margin_cm, sy * 0.5 + build_margin_cm))
    for s in plan["streets"]:
        shapes.append((s["loc_cm"][0], s["loc_cm"][1],
                       math.radians(s["yaw_deg"]),
                       s["len_cm"] * 0.5 + street_margin_cm,
                       s["width_cm"] * 0.5 + street_margin_cm))
    lm = plan.get("landmark")
    if lm:
        lx, ly, _lz = lm["size_cm"]
        shapes.append((lm["loc_cm"][0], lm["loc_cm"][1],
                       math.radians(lm["yaw_deg"]),
                       lx * 0.5 + build_margin_cm, ly * 0.5 + build_margin_cm))
    return shapes


def inside_any(shapes, x, y):
    for cx, cy, yaw, hx, hy in shapes:
        dx, dy = x - cx, y - cy
        co, si = math.cos(yaw), math.sin(yaw)
        if abs(dx * co + dy * si) <= hx and abs(-dx * si + dy * co) <= hy:
            return True
    return False


# --- water exclusion, derived (CARVE_PLAN T8) --------------------------

class WaterMask:
    """Rejects candidates inside a §7 water-body footprint.

    Reads the DERIVED union mask (build_water_exclusion_mask.py) rather than
    re-describing water geometry: one definition of 'where the water is'
    (non-negotiable 24). numpy-only at placer time -- the heavy hydro
    derivation ran when the .npz was built. A missing mask is a REFUSE, not
    a silent pass: an unbuilt exclusion that lets every candidate through is
    exactly the false-negative rule 13 forbids.
    """

    def __init__(self, npz_path):
        import numpy as _np
        z = _np.load(npz_path, allow_pickle=False)
        self.mask = z["mask"]
        self.ox, self.oy = (float(v) for v in z["origin_cm"])
        self.cell_cm = float(z["cell_m"][0]) * 100.0
        self.nrow, self.ncol = self.mask.shape

    def inside(self, x, y):
        col = int(round((x - self.ox) / self.cell_cm))
        row = int(round((y - self.oy) / self.cell_cm))
        if 0 <= row < self.nrow and 0 <= col < self.ncol:
            return bool(self.mask[row, col])
        return False


# --- separation, the offline gate --------------------------------------

def required_separation_cm(a, b):
    """Aggro+leash of the LARGER of the two, per pair.

    One global radius would either crowd the big archetypes or scatter the
    small ones. The pair is what matters: two scavengers may sit closer to
    each other than a scavenger and a highland beast.
    """
    return max(a["aggro_radius_m"] + a["leash_radius_m"],
               b["aggro_radius_m"] + b["leash_radius_m"]) * 100.0


def separation_violations(rows, arche_by_name):
    bad = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            need = required_separation_cm(arche_by_name[rows[i]["archetype"]],
                                          arche_by_name[rows[j]["archetype"]])
            d = math.hypot(rows[i]["loc_cm"][0] - rows[j]["loc_cm"][0],
                           rows[i]["loc_cm"][1] - rows[j]["loc_cm"][1])
            if d < need:
                bad.append({"a": i, "b": j, "dist_cm": round(d, 1),
                            "need_cm": round(need, 1)})
    return bad


# --- selftest -----------------------------------------------------------

def selftest():
    """Prove the separation gate REFUSES, before it is ever trusted to pass.

    A gate that has only seen good input has not been tested, and this one is
    fed a deliberately overlapping pair first -- which PHASE2_PLAN unit 9
    demands by name.
    """
    ok = True
    arche = {"big": {"aggro_radius_m": 40.0, "leash_radius_m": 90.0},
             "small": {"aggro_radius_m": 25.0, "leash_radius_m": 45.0}}

    # (a) a deliberately OVERLAPPING pair -> must be refused
    rows = [{"archetype": "big", "loc_cm": [0.0, 0.0]},
            {"archetype": "big", "loc_cm": [5000.0, 0.0]}]     # 50 m < 130 m
    v = separation_violations(rows, arche)
    print("  overlapping pair (50 m apart, needs 130 m) -> %d violation(s), "
          "want >=1  %s" % (len(v), "OK" if v else "FAIL"))
    ok &= bool(v)

    # (b) the SAME pair, moved clear -> must pass
    rows[1]["loc_cm"][0] = 14000.0                              # 140 m > 130 m
    v = separation_violations(rows, arche)
    print("  same pair at 140 m                          -> %d violation(s), "
          "want 0    %s" % (len(v), "OK" if not v else "FAIL"))
    ok &= not v

    # (c) PER-PAIR, not global: two smalls at 80 m are fine where two bigs
    #     are not. A single global radius cannot express this.
    rows = [{"archetype": "small", "loc_cm": [0.0, 0.0]},
            {"archetype": "small", "loc_cm": [8000.0, 0.0]}]    # 80 m > 70 m
    v_small = separation_violations(rows, arche)
    rows2 = [{"archetype": "big", "loc_cm": [0.0, 0.0]},
             {"archetype": "big", "loc_cm": [8000.0, 0.0]}]     # 80 m < 130 m
    v_big = separation_violations(rows2, arche)
    good = (not v_small) and bool(v_big)
    print("  per-pair: smalls at 80 m pass, bigs at 80 m refuse       %s"
          % ("OK" if good else "FAIL"))
    ok &= good

    # (d) the settlement mask discriminates
    plan_path = os.path.join(REPO, "city", "alpine_basin_town_plan.json")
    if os.path.isfile(plan_path):
        with open(plan_path, "r", encoding="utf-8") as fh:
            plan = json.load(fh)
        shapes = city_shapes(plan, 3000.0, 2000.0)
        b0 = plan["buildings"][0]
        inside = inside_any(shapes, b0["loc_cm"][0], b0["loc_cm"][1])
        far = inside_any(shapes, b0["loc_cm"][0] + 500000.0, b0["loc_cm"][1])
        print("  settlement mask: a building centre inside=%s, a point 5 km "
              "away inside=%s   %s"
              % (inside, far, "OK" if (inside and not far) else "FAIL"))
        ok &= (inside and not far)
    else:
        print("  settlement mask: SKIPPED, no city plan on disk")

    return ok


# --- main ---------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="recipes/encounters.json")
    ap.add_argument("--world", default="recipes/alpine_8k.json")
    ap.add_argument("--character", default="recipes/character.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        print("SELFTEST")
        good = selftest()
        print("SELFTEST %s" % ("PASSED" if good else "FAILED"))
        return 0 if good else 4

    rec = json.load(open(os.path.join(REPO, a.recipe), encoding="utf-8"))
    world = json.load(open(os.path.join(REPO, a.world), encoding="utf-8"))
    char = json.load(open(os.path.join(REPO, a.character), encoding="utf-8"))
    T = Terrain(world)

    # walkable slope, DERIVED from the character recipe (ruling 19)
    prof = char["navigation"]["agent_profile"]
    max_slope = float(te.MOVEMENT_PROFILES[prof]["max_slope_deg"])

    area = rec["area"]
    x0, y0 = area["min_cm"]
    x1, y1 = area["max_cm"]

    plan_path = os.path.join(REPO, rec["exclusions"]["settlement"]["from_city_plan"])
    city = json.load(open(plan_path, encoding="utf-8"))
    shapes = city_shapes(
        city,
        float(rec["exclusions"]["settlement"]["building_margin_m"]) * 100.0,
        float(rec["exclusions"]["settlement"]["street_margin_m"]) * 100.0)

    # the player start comes from the world recipe's own hero_spawn camera
    ps_xy = None
    for c in world["capture"]["cameras"]:
        if c["name"] == "hero_spawn":
            ps_xy = (c["location_cm"][0], c["location_cm"][1])
    if ps_xy is None:
        sys.exit("REFUSE: no hero_spawn camera in %s" % a.world)
    safe_cm = float(rec["exclusions"]["player_start_safe_radius_m"]) * 100.0

    # water exclusion (CARVE_PLAN T8), derived mask; REFUSE if declared but
    # absent -- a silent pass here re-drowns encounters (rule 13).
    water_mask = None
    if "water" in rec["exclusions"]:
        wcfg = rec["exclusions"]["water"]
        wpath = os.path.join(REPO, wcfg["exclusion_mask"])
        if not os.path.isfile(wpath):
            sys.exit("REFUSE: exclusions.water declared but the derived mask "
                     "%s is missing -- run "
                     "research/brief4/scripts/build_water_exclusion_mask.py"
                     % wcfg["exclusion_mask"])
        water_mask = WaterMask(wpath)

    dens = rec["density"]
    ref_m = float(dens["reference_elevation_m"])
    base = float(dens["base_per_km2"])
    per100 = float(dens["per_100m_above_reference"])
    dmax = float(dens["max_per_km2"])

    arche = rec["archetypes"]
    arche_by_name = {x["name"]: x for x in arche}
    rng = np.random.default_rng(int(rec["seed"]))

    samp_r = float(rec["slope"]["sample_radius_m"]) * 100.0

    def elev_m(x, y):
        return float(T.z_cm(x, y)) / 100.0

    def slope_deg(x, y):
        """Max slope over the footprint the encounter occupies."""
        zs = []
        for dx, dy in ((0, 0), (samp_r, 0), (-samp_r, 0),
                       (0, samp_r), (0, -samp_r)):
            zs.append(float(T.z_cm(x + dx, y + dy)))
        rise = max(zs) - min(zs)
        return math.degrees(math.atan(rise / samp_r))

    # ---- how many, from the elevation curve -----------------------------
    # Sample the area to get its elevation profile, then integrate the density
    # curve over it rather than assuming a single elevation for the whole box.
    N = 64
    xs = np.linspace(x0, x1, N)
    ys = np.linspace(y0, y1, N)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    gz = np.asarray(T.z_cm(gx.ravel(), gy.ravel())).reshape(N, N) / 100.0
    per_km2 = np.clip(base * (1.0 + per100 * (gz - ref_m) / 100.0), 0.0, dmax)
    area_km2 = ((x1 - x0) / 100000.0) * ((y1 - y0) / 100000.0)

    # ⛔ THE DENOMINATOR IS THE AVAILABLE GROUND, NOT THE BOX.
    #
    # The box is 1.08 km2 and the town spans 940 m of its 1040, so most of it is
    # settlement (excluded) or cut off by the basin rim (unreachable). Computing
    # the target over the whole box asks for encounters in ground that does not
    # exist for this purpose, and then the gate refuses the planner for failing
    # to find it. That is non-negotiable 22: a statistic reported against a
    # denominator nobody asked about.
    #
    # Measured after the masks exist -- see AVAILABLE GROUND below.

    # ---- OFFLINE CONNECTIVITY: a point can be walkable and unreachable ----
    #
    # ⛔ THIS WAS FOUND THE HARD WAY. The first plan placed 5 encounters that
    # all passed the per-point slope test, all projected onto navmesh, and were
    # ALL in a different island from the player. The town sits in a basin whose
    # rim exceeds the mount's 35 deg limit: reachability from the plaza is
    # 11/12 samples at 200 m, 8/12 at 300 m, 2/12 at 400 m and 0/12 at 450 m.
    # Local flatness says nothing about whether a path EXISTS.
    #
    # So the planner models connectivity the way traversability() does --
    # walkable mask, 8-connected component labelling, keep the component
    # holding the player start. Cells are the agent's own scale, not the
    # heightmap's: a bar with no declared denominator is how this project read
    # 29.26% reachable at 1 m and 94.39% at 8 m on the SAME terrain.
    #
    # This is a HEIGHTMAP model. The editor gate re-checks it against the BUILT
    # navmesh, which is collision-derived, so the two corroborate rather than
    # agree.
    from scipy import ndimage                                # noqa: E402

    CELL = samp_r                       # cm, = slope.sample_radius_m
    nx = int((x1 - x0) // CELL) + 1
    ny = int((y1 - y0) // CELL) + 1
    cxs = x0 + np.arange(nx) * CELL
    cys = y0 + np.arange(ny) * CELL
    mgx, mgy = np.meshgrid(cxs, cys, indexing="ij")
    hz = np.asarray(T.z_cm(mgx.ravel(), mgy.ravel())).reshape(nx, ny)

    dzx = np.abs(np.gradient(hz, CELL, axis=0))
    dzy = np.abs(np.gradient(hz, CELL, axis=1))
    cell_slope = np.degrees(np.arctan(np.maximum(dzx, dzy)))
    walkable = cell_slope <= max_slope

    lab, nlab = ndimage.label(walkable, structure=np.ones((3, 3), dtype=int))
    pi = int(round((ps_xy[0] - x0) / CELL))
    pj = int(round((ps_xy[1] - y0) / CELL))
    pi = min(max(pi, 0), nx - 1)
    pj = min(max(pj, 0), ny - 1)
    home = int(lab[pi, pj])
    if home == 0:
        sys.exit("REFUSE: the player start itself is on non-walkable ground in "
                 "the heightmap model. Nothing was written.")
    reach_mask = (lab == home)

    def reachable(x, y):
        i = int(round((x - x0) / CELL))
        j = int(round((y - y0) / CELL))
        if i < 0 or j < 0 or i >= nx or j >= ny:
            return False
        return bool(reach_mask[i, j])

    conn = {"grid": [nx, ny], "cell_cm": CELL, "components": int(nlab),
            "player_component": home,
            "reachable_cells": int(reach_mask.sum()),
            "walkable_cells": int(walkable.sum()),
            "reachable_frac_of_area": round(float(reach_mask.mean()), 4)}

    # ---- MEASURED REACHABILITY AS A PLACEMENT PRIOR ----------------------
    #
    # The offline heightmap model above is OPTIMISTIC -- it passed five
    # encounters the built navmesh then refused, twice, at two different agents.
    # Rather than tune the model until it agrees (fitting a model to an answer),
    # the planner reads the AUTHORED reachable-region sidecar: real, collision-
    # derived measurements of which street points can be walked to from the
    # spawn.
    #
    # This is not circular. The sidecar is ground truth produced by a different
    # instrument; using it as an INPUT is legitimate, and the in-editor gate
    # still runs afterwards as an independent check on the result.
    # ⛔ THE PRIVATE COPY IS GONE. This planner grew its own `near_reachable`
    # reading the sidecar directly -- the third instance of a reachability check
    # implemented per-tool. Non-negotiable 4a promotes on the SECOND, so the one
    # implementation now lives in scripts/reachability.py and an individually
    # patched copy here is a REJECTED pattern.
    #
    # The module also does something this file never did: it REFUSES a sidecar
    # measured against a different agent, instead of silently answering from
    # stale data.
    try:
        region = reachability.ReachableRegion(
            os.path.join(REPO, rec.get("reachable_sidecar", "")),
            expect_agent_profile=prof)
    except reachability.StaleRegion as e:
        sys.exit("REFUSE: %s\nNothing was written." % e)
    side_meta = region.bound
    anchor_max_cm = float(rec["exclusions"]["max_distance_from_reachable_m"]) * 100.0

    def near_reachable(x, y):
        return region.near_reachable(x, y, anchor_max_cm)

    # ---- AVAILABLE GROUND: the denominator the target is computed over ----
    # Measured on the connectivity grid, applying exactly the tests a candidate
    # must pass, now that every mask exists.
    avail = 0
    tested = 0
    for _i in range(0, nx, 2):
        for _j in range(0, ny, 2):
            px = x0 + _i * CELL
            py = y0 + _j * CELL
            tested += 1
            if inside_any(shapes, px, py):
                continue
            if math.hypot(px - ps_xy[0], py - ps_xy[1]) < safe_cm:
                continue
            if not reach_mask[_i, _j]:
                continue
            if not near_reachable(px, py):
                continue
            avail += 1
    avail_frac = (avail / float(tested)) if tested else 0.0
    target = int(round(float(per_km2.mean()) * area_km2 * avail_frac))
    avail_info = {"tested": tested, "available": avail,
                  "available_fraction": round(avail_frac, 4),
                  "available_km2": round(area_km2 * avail_frac, 4),
                  "_why": ("the density target is computed over the ground a "
                           "candidate can actually occupy -- outside the "
                           "settlement, outside the spawn-safe radius, "
                           "connected to the player, and near MEASURED "
                           "reachable ground -- not over the whole box, most "
                           "of which is town or cut off by the basin rim.")}

    rej = {"in_settlement": 0, "near_player_start": 0, "too_steep": 0,
           "unreachable_from_player": 0, "far_from_reachable_ground": 0,
           "no_archetype_at_elevation": 0, "separation": 0, "in_water": 0}
    rows = []
    attempts = 0
    max_attempts = target * 4000 if target else 0

    while len(rows) < target and attempts < max_attempts:
        attempts += 1
        x = float(rng.uniform(x0, x1))
        y = float(rng.uniform(y0, y1))

        if inside_any(shapes, x, y):
            rej["in_settlement"] += 1
            continue
        if water_mask is not None and water_mask.inside(x, y):
            rej["in_water"] += 1
            continue
        if math.hypot(x - ps_xy[0], y - ps_xy[1]) < safe_cm:
            rej["near_player_start"] += 1
            continue
        if slope_deg(x, y) > max_slope:
            rej["too_steep"] += 1
            continue
        if not reachable(x, y):
            rej["unreachable_from_player"] += 1
            continue
        if not near_reachable(x, y):
            rej["far_from_reachable_ground"] += 1
            continue

        e = elev_m(x, y)
        elig = [t for t in arche if e >= float(t["min_elevation_m"])]
        if not elig:
            rej["no_archetype_at_elevation"] += 1
            continue
        wsum = sum(float(t["weight"]) for t in elig)
        pick = float(rng.uniform(0.0, wsum))
        acc = 0.0
        chosen = elig[-1]
        for t in elig:
            acc += float(t["weight"])
            if pick <= acc:
                chosen = t
                break

        cand = {"archetype": chosen["name"], "loc_cm": [round(x, 1), round(y, 1)]}
        if separation_violations(rows + [cand], arche_by_name):
            rej["separation"] += 1
            continue

        lo, hi = chosen["party_size"]
        rows.append({
            "archetype": chosen["name"],
            "loc_cm": [round(x, 1), round(y, 1),
                       round(float(T.z_cm(x, y)), 1)],
            "elevation_m": round(e, 1),
            "slope_deg": round(slope_deg(x, y), 2),
            "party_size": int(rng.integers(lo, hi + 1)),
            "aggro_radius_cm": float(chosen["aggro_radius_m"]) * 100.0,
            "leash_radius_cm": float(chosen["leash_radius_m"]) * 100.0})

    by_arche_dbg = {}
    for r in rows:
        by_arche_dbg[r["archetype"]] = by_arche_dbg.get(r["archetype"], 0) + 1

    # REPORT BEFORE REFUSING. A refusal that does not show its working leaves
    # the caller guessing which bar to move, and this planner has five separate
    # reasons to drop a candidate.
    print("region      %s" % rec["region"])
    print("area        %.0f x %.0f m  (%.3f km2)"
          % ((x1 - x0) / 100.0, (y1 - y0) / 100.0, area_km2))
    print("density     %.2f/km2 mean over the box" % float(per_km2.mean()))
    print("available   %d of %d sampled cells (%.2f%%) = %.4f km2 -> target %d"
          % (avail_info["available"], avail_info["tested"],
             100.0 * avail_info["available_fraction"],
             avail_info["available_km2"], target))
    if target == 0:
        print("")
        print("  THE AVAILABLE GROUND IS EMPTY, and that is a finding rather")
        print("  than a tuning problem. An encounter must be OUTSIDE the")
        print("  settlement and NEAR ground measured reachable from the spawn.")
        print("  In this basin those two are the SAME GROUND: the reachable")
        print("  region is the town, and the ring outside it is cut off by the")
        print("  rim. Widening needs navmesh BEYOND the town volume, not a")
        print("  smaller margin -- shrinking the margin would put encounters")
        print("  inside bowshot of the settlement to satisfy a bar.")
    print("attempts    %d of a %d budget" % (attempts, max_attempts))
    print("placed      %d  %s" % (len(rows), by_arche_dbg))
    print("rejected    %s" % rej)
    print("")

    # ---- gates, BEFORE the write ----------------------------------------
    g = rec["gates"]
    viol = separation_violations(rows, arche_by_name)
    if viol:
        sys.exit("REFUSE: %d separation violations survived placement. "
                 "Nothing was written." % len(viol))
    # THE GATE IS RELATIVE TO THE TARGET, not a constant. A constant floor is
    # satisfied by lowering the constant; what can actually go wrong is the
    # exclusions or the separation eating the plan, and only a ratio sees that.
    floor = int(g.get("min_encounters_floor", 0))
    frac = float(g.get("min_fraction_of_target", 0.0))
    from_frac = int(math.ceil(frac * target))
    need = max(floor, from_frac)
    if len(rows) < need:
        # NAME THE BINDING BAR. The first version of this message always
        # attributed the refusal to the fraction, and on a target of 0 that
        # printed "below 80% of target (need 3)" -- 80% of 0 is 0, so the
        # fraction was not binding at all and the reader is told to look at the
        # wrong knob. A refusal the operator cannot attribute is half a refusal.
        binding = ("the FLOOR gates.min_encounters_floor=%d" % floor
                   if floor >= from_frac else
                   "%.0f%% of the target of %d" % (frac * 100.0, target))
        sys.exit(
            "REFUSE: %d encounters, need %d -- the binding bar is %s. "
            "(target %d from the density curve; floor %d; %.0f%% of target "
            "= %d.) A shortfall here means the exclusions or the separation "
            "ate the plan, not that the density is wrong. Nothing was written."
            % (len(rows), need, binding, target, floor, frac * 100.0,
               from_frac))

    by_arche = {}
    for r in rows:
        by_arche[r["archetype"]] = by_arche.get(r["archetype"], 0) + 1

    out = {
        "_produced_by": "scripts/plan_encounters.py",
        "_recipe": a.recipe,
        "_world": a.world,
        # R5 (E-4, 2026-09-16): these two were CONSUMED (char :210, city
        # plan :217-218) but never DECLARED — invisible to the stamp, so
        # a character or town change could not stale this plan. Both are
        # INPUT_KEYS in plan_stamp; declaring them is the fix, not a
        # widening.
        "_character": a.character,
        "_city_plan": rec["exclusions"]["settlement"]["from_city_plan"],
        "_heights_are_a_PLAN": (
            "elevations come from the HEIGHTMAP. Reachability is NOT checked "
            "here and must not be: the navmesh is built from COLLISION, a "
            "different representation, and checking it against the heightmap "
            "would be one source checked twice. See "
            "scripts/city_encounter_verify_payload.txt."),
        "region": rec["region"], "level_path": rec["level_path"],
        "seed": int(rec["seed"]),
        "area_min_cm": [x0, y0], "area_max_cm": [x1, y1],
        "walkable_slope_deg": max_slope,
        "_walkable_slope_derived_from": "recipes/character.json navigation.agent_profile = %r" % prof,
        "target_count": target,
        "connectivity": conn,
        "available_ground": avail_info,
        "_connectivity_is_a_HEIGHTMAP_model": (
            "walkable mask + 8-connected components, keeping the component "
            "holding the player start. A point can be locally flat and still "
            "unreachable -- the first plan placed 5 encounters that all passed "
            "the point-slope test and were ALL in a different navmesh island. "
            "The editor gate re-checks this against the BUILT navmesh, which "
            "is collision-derived, so the two corroborate rather than agree."),
        "counts": {"encounters": len(rows), "by_archetype": by_arche},
        "rejected": rej,
        "_rejected_is_reported": (
            "a planner that silently drops candidates cannot be told apart "
            "from one that never generated them"),
        "player_start_cm": [ps_xy[0], ps_xy[1]],
        "encounters": rows,
    }

    # Stamp the inputs after every gate, immediately before the write. See
    # scripts/plan_stamp.py -- one declaration, shared with plan_city and with
    # check_plan_freshness, so an input key cannot be added in one place and
    # forgotten in another. This plan's own predecessor is the motivating case.
    out[plan_stamp.STAMP_KEY] = plan_stamp.stamp(out, REPO)
    # R5 (E-4): the CONSUMED-FIELD stamp — reviewed against the reads,
    # cited (granularity floor: at or above what the code touches):
    #   encounters.json: area :213, exclusions :217-:231/:364,
    #     density :233, archetypes :239, seed :241, slope :243,
    #     reachable_sidecar :359, gates :490, region :466/:533,
    #     level_path :533
    #   world recipe: landscape + heightmap (Terrain :207 via
    #     plan_city.Terrain :59-:60), capture :226 (hero_spawn camera)
    #   character.json: navigation :210
    #   city plan: the exclusion geometry city_shapes reads (:218-:222
    #     via town_exclusion — buildings, streets, plaza_radius_cm,
    #     site_centre_cm). Consumed-stamped because the town plan's
    #     METADATA (stamps/waivers/notes) churns while its geometry
    #     stands — proven 2026-09-16 when three successive metadata
    #     edits re-staled this plan through the whole-file hash.
    out[plan_stamp.CONSUMED_KEY] = plan_stamp.consumed_stamp(out, REPO, {
        "_recipe": ["area", "exclusions", "density", "archetypes", "seed",
                    "slope", "reachable_sidecar", "gates", "region",
                    "level_path"],
        "_world": ["landscape", "heightmap", "capture"],
        "_character": ["navigation"],
        "_city_plan": ["buildings", "streets", "plaza_radius_cm",
                       "site_centre_cm"],
    })

    dst = a.out or os.path.join("encounters", "%s_all.json" % rec["region"])
    p = os.path.join(REPO, dst)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    print("region      %s" % rec["region"])
    print("area        %.0f x %.0f m  (%.3f km2)"
          % ((x1 - x0) / 100.0, (y1 - y0) / 100.0, area_km2))
    print("density     %.2f/km2 mean over the box -> target %d"
          % (float(per_km2.mean()), target))
    print("placed      %d encounters  %s" % (len(rows), by_arche))
    print("slope bar   %.1f deg, derived from agent_profile %r" % (max_slope, prof))
    print("rejected    %s" % rej)
    print("wrote       %s" % dst)
    print("")
    print("NOT YET VERIFIED: reachability. Run "
          "scripts/city_encounter_verify_payload.txt in the editor against the "
          "BUILT navmesh -- this plan read the heightmap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
