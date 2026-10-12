"""town_kit_manifest.py -- the ONE manifest (plan row -> house spec) that drives the kit-town placer, verifier and save.

    python scripts/town_kit_manifest.py            # write city/<city_id>_kit_manifest.json
    python scripts/town_kit_manifest.py --dry-run  # summary only, writes nothing

Reads the adopted town plan (city/alpine_basin_town_plan.json, roof_fit_source town_kit), the kit recipe
(recipes/town_kit.json through scripts/town_kit_plan.py) and the heightmap (the plan's own biome recipe). Per
building:
  * footprint W x D = the plan's size_cm (already on the kit snap -- refused otherwise), courses = storeys;
  * roof = town_kit_plan.plan_roof -- REFUSED if it disagrees with the plan's roof_candidate (one fit, two reads);
  * door side = the side whose outward normal points most directly at the nearest street midpoint;
  * floor level = the ground at the door-side midpoint (the placer TRACES that point in the engine; the heightmap
    only sizes the foundation): sub_courses = foundation courses needed to reach the lowest perimeter ground
    (0 when the drop is <= FOUNDATION_SLACK_CM, else ceil((drop + FOUNDATION_MARGIN_CM) / course));
  * pieces = plan_house(..., sub_courses) + roof + gables; authored box covers foundation + walls.
Labels TownKit_<index:03d>, tag LandscapeLab.TownKit. Stamped with plan_stamp (6 inputs: this script, the plan,
the kit recipe, scripts/town_kit_plan.py, the biome recipe, the heightmap).
"""
import argparse
import io
import json
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_stamp  # noqa: E402
import town_kit_plan as tkp  # noqa: E402
from plan_city import Terrain  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = "city/alpine_basin_town_plan.json"
TAG = "LandscapeLab.TownKit"
FOUNDATION_SLACK_CM = float(tkp._R["foundation"]["slack_cm"])     # recipes/town_kit.json _foundation
FOUNDATION_MARGIN_CM = float(tkp._R["foundation"]["margin_cm"])
SIDE_NORMALS = ((0, -1), (1, 0), (0, 1), (-1, 0))   # town_kit_plan._side_frames order: S, E, N, W
# 2026-10-11 ARM C (R-SGTRIAL, research/town_kit/SHAPE_GRAMMAR_TRIAL.md VERDICT): the house style, from the recipe.
# Absent or "enabled": false = None = the shipped output byte for byte.
_ST = tkp._R.get("style") or {}
STYLE = ({k: v for k, v in _ST.items() if not k.startswith("_") and k != "enabled"} if _ST.get("enabled") else None)
STATS = {"jettied": 0, "jetty_dropped_no_roof": 0, "roof_changed_by_jetty": 0, "roof_varied": 0}
# 2026-10-11 roof variety (research/town_kit/ROOF_VARIETY.md): style.roof_variety -- absent/disabled = best fit only
RV = (STYLE or {}).get("roof_variety") or {}
RV = RV if RV.get("enabled") else None
if RV is not None:
    if RV.get("grades") and [n for n in tkp.ROOFS if not tkp.ROOF_MATERIAL.get(n)]:
        raise SystemExit("REFUSE: style.roof_variety grades need every usable roof's 'material' recorded: %s"
                         % [n for n in tkp.ROOFS if not tkp.ROOF_MATERIAL.get(n)])
    if not 0.0 < float(RV["max_stretch"]) <= tkp.ROOF_TOL or int(RV["neighbours"]) < 1 \
            or float(RV["neighbour_radius_m"]) <= 0 or not 0.0 <= float(RV["ridge_tol_deg"]) < 90.0:
        raise SystemExit("REFUSE: style.roof_variety needs 0 < max_stretch <= roof_tol (%g), neighbours >= 1, "
                         "neighbour_radius_m > 0, 0 <= ridge_tol_deg < 90: %s" % (tkp.ROOF_TOL, RV))


def _world(cx, cy, yaw_deg, lx, ly):
    a = math.radians(yaw_deg)
    return cx + lx * math.cos(a) - ly * math.sin(a), cy + lx * math.sin(a) + ly * math.cos(a)


def door_side(b, streets):
    # the organic planner RECORDS which side fronts its street (0 = S = local -Y; audit 2026-10-10 F6): the nearest
    # street MIDPOINT can be a different street round a corner. Lattice plans carry no key -> the nearest-midpoint rule.
    if "door_side" in b:
        return int(b["door_side"])
    cx, cy = b["loc_cm"][0], b["loc_cm"][1]
    best = min(streets, key=lambda s: math.hypot(s["loc_cm"][0] - cx, s["loc_cm"][1] - cy))
    dx, dy = best["loc_cm"][0] - cx, best["loc_cm"][1] - cy
    a = -math.radians(b["yaw_deg"])
    lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    return max(range(4), key=lambda i: SIDE_NORMALS[i][0] * lx + SIDE_NORMALS[i][1] * ly)


def perimeter_local(W, D, step=50.0):
    hw, hd = W / 2.0, D / 2.0
    pts = []
    for t in np.arange(-hw, hw + 1e-6, step):
        pts += [(t, -hd), (t, hd)]
    for t in np.arange(-hd, hd + 1e-6, step):
        pts += [(-hw, t), (hw, t)]
    return pts


def build(plan, T):
    if plan.get("roof_fit_source") != "town_kit":
        raise SystemExit("REFUSE: plan roof_fit_source is %r, not town_kit -- its roofs were not fitted by the "
                         "builder" % plan.get("roof_fit_source"))
    streets = plan.get("streets") or []
    if not streets:
        raise SystemExit("REFUSE: the plan has no streets -- door sides cannot be chosen")
    houses = []
    placed_roofs = []      # (x_cm, y_cm, (mesh, world ridge deg)) of the houses already planned -- roof neighbours
    placed_grades = []     # (x_cm, y_cm, grade name) -- lever B's neighbours
    for i, b in enumerate(x for x in plan["buildings"] if x["kind"] == "building"):
        W, D = float(b["size_cm"][0]), float(b["size_cm"][1])
        if W % tkp.SNAP_CM or D % tkp.SNAP_CM:
            raise SystemExit("REFUSE: building %d footprint %s is off the %d cm kit snap" % (i, b["size_cm"], tkp.SNAP_CM))
        W, D, courses = int(W), int(D), int(b["storeys"])
        roof = tkp.plan_roof(W, D, courses)
        if roof is None or roof["mesh"] != b.get("roof_candidate"):
            raise SystemExit("REFUSE: building %d roof %s != plan roof_candidate %s" % (
                i, roof and roof["mesh"], b.get("roof_candidate")))
        ds = door_side(b, streets)
        cx, cy, yaw = b["loc_cm"][0], b["loc_cm"][1], b["yaw_deg"]
        n = SIDE_NORMALS[ds]
        door_local = (n[0] * W / 2.0, n[1] * D / 2.0)
        pts = [_world(cx, cy, yaw, lx, ly) for lx, ly in perimeter_local(W, D)]
        zs = T.z_cm([p[0] for p in pts], [p[1] for p in pts])
        z_door = float(T.z_cm(*_world(cx, cy, yaw, *door_local)))
        drop = z_door - float(np.min(zs))
        rise = float(np.max(zs)) - z_door
        sub = 0 if drop <= FOUNDATION_SLACK_CM else int(math.ceil((drop + FOUNDATION_MARGIN_CM) / tkp.COURSE_CM))
        # 2026-10-11 ARM C (R-SGTRIAL): recipes/town_kit.json `style` -- absent/disabled = the shipped output
        st = STYLE
        jet = int(st.get("jetty_cm", 0)) if st else 0
        tail = None

        def fit_roof(Wf, Df):
            # best fit, or (roof variety) the in-cap candidate least used by the nearest already-planned houses;
            # its own RNG, so the walls' seeded draws are untouched
            if RV is None:
                return tkp.plan_roof(Wf, Df, courses)
            cands = tkp.roof_candidates(Wf, Df, courses, float(RV["max_stretch"]))
            if not cands:
                return None
            r2 = (float(RV["neighbour_radius_m"]) * 100.0) ** 2
            # sort on distance ONLY (stable = plan order on ties): k can hold a None ridge, and None < float raises
            # (design review 2026-10-11 M2)
            near = sorted(((d2, k) for d2, k in (((x - cx) ** 2 + (y - cy) ** 2, k) for x, y, k in placed_roofs)
                           if d2 <= r2), key=lambda t: t[0])[:int(RV["neighbours"])]
            got = tkp.pick_roof(cands, yaw, [k for _, k in near], random.Random(int(RV["seed"]) * 100003 + i),
                                ridge_tol_deg=float(RV["ridge_tol_deg"]))
            best = tkp.plan_roof(Wf, Df, courses)
            if (got["mesh"], got["yaw"]) != (best["mesh"], best["yaw"]):
                STATS["roof_varied"] += 1
            return got

        if st and jet and courses > 1:
            Wu, Du, dx, dy = tkp.jetty_footprint(int(W), int(D), ds, jet)
            roof_u = fit_roof(Wu, Du)
            if roof_u is None:              # no whole roof fits the widened upper storey: this house keeps no jetty
                st = dict(st, jetty_cm=0)
                STATS["jetty_dropped_no_roof"] += 1
            else:
                # exactly sg_trial_plan.arm_c_pieces (audited): fit roof + gables to the UPPER footprint at the
                # origin, then shift both with it
                tail = [roof_u] + tkp.plan_gables(Wu, Du, courses, roof_u)
                for p in tail:
                    p["x"] = p.get("x", 0.0) + dx
                    p["y"] = p.get("y", 0.0) + dy
                STATS["jettied"] += 1
                # the jetty's own effect = its BEST fit vs the plan's; variety is counted in roof_varied (review S2)
                if tkp.plan_roof(Wu, Du, courses)["mesh"] != b.get("roof_candidate"):
                    STATS["roof_changed_by_jetty"] += 1
        pieces = tkp.plan_house(W, D, courses, door_side=ds, seed=i, sub_courses=sub, style=st or None)
        if tail is None:
            if RV is not None:
                roof = fit_roof(W, D)
            tail = [roof] + tkp.plan_gables(W, D, courses, roof)
        pieces.extend(tail)
        grade = None
        if RV is not None and RV.get("grades"):
            # lever B: the weathering grade least used by the same nearest neighbours; own RNG (walls untouched)
            r2 = (float(RV["neighbour_radius_m"]) * 100.0) ** 2
            near_g = [g for d2, g in sorted((((x - cx) ** 2 + (y - cy) ** 2, g) for x, y, g in placed_grades),
                                            key=lambda t: t[0]) if d2 <= r2][:int(RV["neighbours"])]
            names = [g["name"] for g in RV["grades"]]
            use = dict((n, near_g.count(n)) for n in names)
            tied = sorted(n for n in names if use[n] == min(use.values()))
            grade = tied[random.Random(int(RV["seed"]) * 100003 + i + 7919).randrange(len(tied))]
            if grade != "base":
                tail[0]["material"] = tkp.grade_mic_path(
                    RV["grade_dir"], tkp.ROOF_MATERIAL[tail[0]["mesh"]], grade)
            placed_grades.append((cx, cy, grade))
            STATS.setdefault("grades", {})[grade] = STATS.get("grades", {}).get(grade, 0) + 1
        placed_roofs.append((cx, cy, (tail[0]["mesh"], tkp.world_ridge_deg(tail[0], yaw))))
        lo, hi = -sub * tkp.COURSE_CM, courses * tkp.COURSE_CM
        houses.append({
            "index": i, "label": "TownKit_%03d" % i, "tags": [TAG],
            "loc_cm": [cx, cy, 0.0], "yaw_deg": yaw, "trace_local_xy": list(door_local),
            "W_cm": W, "D_cm": D, "courses": courses, "sub_courses": sub, "door_side": ds,
            "roof": tail[0]["mesh"],      # the PLACED roof (the jetty refit when present; audit 2026-10-11 F3)
            "roof_grade": grade,          # lever B weathering grade (None = roof variety off)
            "heightmap_drop_cm": round(drop, 1), "heightmap_rise_cm": round(rise, 1),
            # the authored box is the house's ONLY collision + nav geometry (LandscapeLabTools.cpp:1994-2002; the ISM
            # pieces are NoCollision). It stays the GROUND footprint: the jetty is above COURSE_CM (200 cm), over the
            # 176 cm agent, and growing the box put an invisible wall in front of every door (audit 2026-10-11 F1).
            "box_center_cm": [0.0, 0.0, (lo + hi) / 2.0], "box_extent_cm": [W / 2.0, D / 2.0, (hi - lo) / 2.0],
            "pieces": pieces})
    return houses


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    plan = json.load(io.open(os.path.join(REPO, PLAN), encoding="utf-8"))
    biome = json.load(io.open(os.path.join(REPO, plan["_biome"]), encoding="utf-8"))
    T = Terrain(biome, town=True)
    houses = build(plan, T)
    n_p = sum(len(h["pieces"]) for h in houses)
    subs = {}
    for h in houses:
        subs[h["sub_courses"]] = subs.get(h["sub_courses"], 0) + 1
    rises = sorted(h["heightmap_rise_cm"] for h in houses)
    print("houses %d, pieces %d (%.1f per house)" % (len(houses), n_p, n_p / float(max(1, len(houses)))))
    print("foundation sub-courses: %s" % sorted(subs.items()))
    print("door sides S/E/N/W: %s" % [sum(1 for h in houses if h["door_side"] == k) for k in range(4)])
    print("style: %s" % ("ON keys " + ",".join(sorted(STYLE)) if STYLE else "off (shipped output)"))
    print("stats: %s" % STATS)
    roofs = {}
    for h in houses:
        roofs[h["roof"]] = roofs.get(h["roof"], 0) + 1
    print("roofs: %s" % sorted(roofs.items()))
    print("uphill ground above the floor (buried wall), p50 %.0f p90 %.0f max %.0f cm"
          % (rises[len(rises) // 2], rises[int(len(rises) * 0.9)], rises[-1]))
    if a.dry_run:
        print("dry run: nothing written")
        return 0
    # the file Terrain actually read (plan_city.py Terrain.__init__), asserted equal to the plan's record
    # (2026-10-10 street flattening, review change 2: Terrain.source_rel, the ONE declaration of what was read)
    if T.source_rel != plan["_terrain_source"]:
        raise SystemExit("REFUSE: heightmap read %s != plan _terrain_source %s"
                         % (T.source_rel, plan["_terrain_source"]))
    doc = {"_produced_by": "scripts/town_kit_manifest.py", "_city_plan": PLAN, "_recipe": "recipes/town_kit.json",
           # every piece comes from the builder's planner (audit F1)
           "_roof_fit": "scripts/town_kit_plan.py",
           "_biome": plan["_biome"], "_terrain_source": T.source_rel,
           "level_path": plan["level_path"], "tag": TAG, "count": len(houses), "houses": houses}
    doc[plan_stamp.STAMP_KEY] = plan_stamp.stamp(doc, REPO)
    out = os.path.join(REPO, "city", "%s_kit_manifest.json" % plan["city_id"])
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("wrote %s" % os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
