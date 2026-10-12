"""check_organic_plan.py -- independent invariants of an ORGANIC town plan, re-derived from the OUTPUT (2026-10-10).

    python scripts/check_organic_plan.py [--plan city/alpine_basin_town_plan.json] [--determinism]
    python scripts/check_organic_plan.py --selftest

Reads only the plan file (and the heightmap / water mask for the terrain checks), never the generator's own stats:
  1. layout == "organic" and non-empty streets / buildings (rule 13: zero is a refusal, not a pass);
  2. ONE connected street network (measure_city_connectivity.components, the project's one definition);
  3. every street segment passes the street gate re-measured here: end-to-end grade <= plan bar and cut/fill <=
     bar on the heightmap (the generator's own gate is not trusted -- a different implementation of the same
     rule, NN8);
  4. no building OBB intersects a street OBB, no two building OBBs intersect, and no street or building
     intersects the landmark (separating axis, own code);
  5. no building centre inside a square, no building centre or street centreline in water (the water mask the
     plan stamps; missing = refusal); every building records door_side 0;
  6. --determinism: plan_city run twice (the plan's own _recipe) to scratch files under _verify/ gives identical
     buildings and streets.
Exit 0 = all hold; 4 = any fails.
"""
import argparse
import io
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def corners(cx, cy, sx, sy, yaw):
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    return [(cx + dx * c - dy * s, cy + dx * s + dy * c) for dx, dy in
            ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2), (-sx / 2, sy / 2))]


def sat(A, B):
    """Polygon (convex quad) intersection by separating axes -- independent of city_organic.obb_overlap."""
    for poly in (A, B):
        for k in range(4):
            x1, y1 = poly[k]
            x2, y2 = poly[(k + 1) % 4]
            nx, ny = y2 - y1, x1 - x2
            pa = [nx * x + ny * y for x, y in A]
            pb = [nx * x + ny * y for x, y in B]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def check(plan_path):
    from plan_city import Terrain
    from measure_city_connectivity import components
    p = json.load(io.open(plan_path, encoding="utf-8"))
    # the recipe the plan says it came from (audit 2026-10-10 F16), not a hardcoded one
    rec = json.load(io.open(os.path.join(REPO, p["_recipe"]), encoding="utf-8"))
    world = json.load(io.open(os.path.join(REPO, p["_biome"]), encoding="utf-8"))
    T = Terrain(world, town=True)     # the ground the plan was gated on (pre-streets when flattening is declared)
    pl = rec["plan"]
    fails = []
    S, B = p.get("streets") or [], [b for b in p.get("buildings") or [] if b.get("kind") == "building"]
    if p.get("layout") != "organic" or not S or not B:
        return ["not an organic plan with streets and buildings (layout %r, %d streets, %d buildings)"
                % (p.get("layout"), len(S), len(B))], {}
    # organic join: per pair at the mean of the two widths (measure_city_connectivity, audit F9)
    comps = components(S, max(float(s["width_cm"]) for s in S), width_join=True)
    if len(comps) != 1:
        fails.append("street network has %d components" % len(comps))
    bar = math.tan(math.radians(float(pl["max_street_slope_deg"])))
    cf_bar = float(pl["max_street_cut_fill_m"]) * 100.0
    bad_gate = 0
    for st in S:
        a = math.radians(st["yaw_deg"])
        h = st["len_cm"] / 2
        ax, ay = st["loc_cm"][0] - h * math.cos(a), st["loc_cm"][1] - h * math.sin(a)
        bx, by = st["loc_cm"][0] + h * math.cos(a), st["loc_cm"][1] + h * math.sin(a)
        # the recipe's declared spacing, never coarser than 0.5 m and never fewer than 21 points (LESSONS 2026-10-10e)
        ds_m = float(pl.get("street_gate_sample_m", 0.5))
        if not ds_m > 0:
            return ["plan.street_gate_sample_m %r is not positive -- refusing to measure" % ds_m], {}
        ds = min(ds_m, 0.5) * 100
        t = np.linspace(0, 1, max(21, int(math.ceil(st["len_cm"] / ds)) + 1))
        z = np.asarray(T.z_cm(ax + (bx - ax) * t, ay + (by - ay) * t))
        if abs(z[-1] - z[0]) / max(st["len_cm"], 1) > bar + 1e-6 or np.abs(z - (z[0] + (z[-1] - z[0]) * t)).max() > cf_bar + 1e-3:
            bad_gate += 1
    if bad_gate:
        fails.append("%d street segments fail the street gate (re-measured)" % bad_gate)
    SQ = [corners(s["loc_cm"][0], s["loc_cm"][1], s["len_cm"], s["width_cm"], s["yaw_deg"]) for s in S]
    BQ = [corners(b["loc_cm"][0], b["loc_cm"][1], b["size_cm"][0], b["size_cm"][1], b["yaw_deg"]) for b in B]
    street_hits, house_hits = 0, 0
    for k, q in enumerate(BQ):
        bx, by = B[k]["loc_cm"][0], B[k]["loc_cm"][1]
        for m, sq in enumerate(SQ):
            if math.hypot(bx - S[m]["loc_cm"][0], by - S[m]["loc_cm"][1]) < 4000 and sat(q, sq):
                street_hits += 1
        for m in range(k + 1, len(BQ)):
            if math.hypot(bx - B[m]["loc_cm"][0], by - B[m]["loc_cm"][1]) < 3000 and sat(q, BQ[m]):
                house_hits += 1
    # the landmark against every street and building (LESSONS 2026-10-10f: never tested before, and the shipped
    # lattice landmark overlaps 2 streets)
    lm_hits = 0
    L = p.get("landmark")
    if L:
        LQ = corners(L["loc_cm"][0], L["loc_cm"][1], L["size_cm"][0], L["size_cm"][1], L["yaw_deg"])
        lm_hits = sum(1 for q in SQ + BQ if sat(LQ, q))
        if lm_hits:
            fails.append("%d streets/buildings intersect the landmark" % lm_hits)
    if street_hits:
        fails.append("%d building/street intersections" % street_hits)
    if house_hits:
        fails.append("%d building/building intersections" % house_hits)
    in_sq = sum(1 for b in B for sq in p.get("squares", [])
                if math.hypot(b["loc_cm"][0] - sq[0], b["loc_cm"][1] - sq[1]) < sq[2])
    if in_sq:
        fails.append("%d buildings centred inside a square" % in_sq)
    # the water mask the plan stamps; a missing mask is "could not look", a refusal (rule 13), never 0 in water
    wp = os.path.join(REPO, *p.get("_water_mask", "encounters/alpine_8k_water_exclusion.npz").split("/"))
    if not os.path.isfile(wp):
        return ["water mask %s missing -- could not test water" % wp], {}
    w = np.load(wp)
    M, (ox, oy), wc = w["mask"], w["origin_cm"], float(w["cell_m"][0]) * 100

    def is_wet(x, y):
        i, j = int((x - ox) // wc), int((y - oy) // wc)
        return 0 <= j < M.shape[0] and 0 <= i < M.shape[1] and bool(M[j, i])
    wet = sum(1 for b in B if is_wet(b["loc_cm"][0], b["loc_cm"][1]))
    if wet:
        fails.append("%d buildings in water" % wet)
    # streets: sampled along the centreline every ~1 m (audit F10)
    wet_st = 0
    for st in S:
        a = math.radians(st["yaw_deg"])
        h = st["len_cm"] / 2
        n = max(3, int(st["len_cm"] / 100) + 1)
        if any(is_wet(st["loc_cm"][0] + (t - 0.5) * 2 * h * math.cos(a), st["loc_cm"][1] + (t - 0.5) * 2 * h * math.sin(a))
               for t in np.linspace(0, 1, n)):
            wet_st += 1
    if wet_st:
        fails.append("%d streets cross water" % wet_st)
    no_door = sum(1 for b in B if b.get("door_side") != 0)
    if no_door:
        fails.append("%d buildings lack door_side 0 (local -Y toward the fronted street)" % no_door)
    stats = {"streets": len(S), "buildings": len(B), "components": len(comps), "gate_fail": bad_gate,
             "street_hits": street_hits, "house_hits": house_hits, "landmark_hits": lm_hits, "in_square": in_sq, "in_water": wet,
             "streets_in_water": wet_st, "squares": len(p.get("squares", []))}
    return fails, stats


def determinism(recipe):
    # scratch plans go under the repo's _verify/ (standing rule 1; audit 2026-10-10 BLOCK: mkdtemp wrote to %TEMP%)
    outs = []
    with tempfile.TemporaryDirectory(dir=os.path.join(REPO, "_verify")) as td:
        for k in range(2):
            f = os.path.join(td, "p%d.json" % k)
            subprocess.run([sys.executable, os.path.join(REPO, "scripts", "plan_city.py"), "--recipe", recipe,
                            "--out", f], capture_output=True, text=True, cwd=REPO, check=True)
            d = json.load(io.open(f, encoding="utf-8"))
            outs.append((d["buildings"], d["streets"]))
    return outs[0] == outs[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", default=os.path.join(REPO, "city", "alpine_basin_town_plan.json"))
    ap.add_argument("--determinism", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        # the SAT test must see an overlap and a clearance
        A = corners(0, 0, 1000, 500, 30)
        ok = sat(A, corners(300, 100, 1000, 500, -20)) and not sat(A, corners(3000, 0, 1000, 500, 0))
        print("SELFTEST %s" % ("PASSED" if ok else "FAILED"))
        return 0 if ok else 4
    fails, stats = check(a.plan)
    print("plan %s: %s" % (os.path.relpath(a.plan, REPO), stats))
    if a.determinism:
        same = determinism(json.load(io.open(a.plan, encoding="utf-8"))["_recipe"])
        print("determinism (two planner runs): %s" % ("IDENTICAL" if same else "DIFFER"))
        if not same:
            fails.append("planner not deterministic")
    for f in fails:
        print("  FAIL " + f)
    print("VERDICT: %s" % ("OK" if not fails else "FAIL"))
    return 0 if not fails else 4


if __name__ == "__main__":
    sys.exit(main())
