"""city_image.py -- plan.layout "image": streets and lots read from a town-from-image plan (2026-10-10).

The third layout beside "lattice" and "organic". It does NOT synthesise a network: it takes the plan JSON
that scripts/town_from_topdown.py extracted from a flat-colour top-down map (schema g2ue-town-plan-0.1,
rows already in R-TOWNKIT shape) and places it on the site, running every piece through plan_city's OWN
gates, so a street that is too steep or a lot that needs too much cut/fill is dropped and counted rather
than floated. Same call signatures as city_organic.streets / city_organic.plots, so plan_city's downstream
(pruning to the plaza component, building rows, roof fit, orphan check, output) is unchanged.

Recipe block (recipes/<city>.json, plan.image):
    plan_json           repo-relative path of the adapter plan
    map_centre_cm       [x, y] in the PLAN's frame that lands on the site centre (cx0, cy0)
    drop_failing_pieces true: a street piece that fails street_pass is dropped (an image street cannot
                        be re-routed; the count is reported). false: REFUSE on the first failure.

Axis mapping "A" from the adapter: plan X -> world X, plan Y -> world Y, both in cm, no rotation.
Door convention: the adapter's door_side k (0 = local -Y, 1 = +X, 2 = +Y, 3 = -X) is rotated so the door
lands on local -Y as the kit expects (hyaw = yaw - 90 k, W/D swapped for odd k); the row keeps door_side 0.
"""
import json
import math
import os

import city_organic

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATER_REL = None  # the image layout carries its own water polygons in the plan; no npz mask is read here


def _load(pl):
    o = pl["image"]
    p = o["plan_json"]
    if not os.path.isabs(p):
        p = os.path.join(REPO, p)
    with open(p, "r", encoding="utf-8") as fh:
        plan = json.load(fh)
    if plan.get("schema_version") != "g2ue-town-plan-0.1":
        raise SystemExit("REFUSE: %s is not a g2ue-town-plan-0.1 plan" % p)
    mcx, mcy = [float(v) for v in o["map_centre_cm"]]
    return plan, (mcx, mcy), bool(o.get("drop_failing_pieces", True))


def streets(T, pl, cx0, cy0, R_cm, rng, street_pass, street_seat, obstacles=()):
    """-> (segments in plan_city's street schema + chain/seq, junctions, stats)."""
    plan, (mcx, mcy), drop_ok = _load(pl)
    segs, dropped, outside = [], 0, 0
    ends = {}
    for s in plan["streets"]:
        ax, ay = cx0 + (float(s["a_cm"][0]) - mcx), cy0 + (float(s["a_cm"][1]) - mcy)
        bx, by = cx0 + (float(s["b_cm"][0]) - mcx), cy0 + (float(s["b_cm"][1]) - mcy)
        mx, my = 0.5 * (ax + bx), 0.5 * (ay + by)
        if math.hypot(mx - cx0, my - cy0) > R_cm:
            outside += 1
            continue
        L = math.hypot(bx - ax, by - ay)
        if L < 50.0:
            continue
        yaw = math.degrees(math.atan2(by - ay, bx - ax))
        w = float(s["width_cm"])
        if not street_pass(mx, my, yaw, L):
            if not drop_ok:
                raise SystemExit("REFUSE: image street %s fails the street gate" % s.get("id"))
            dropped += 1
            continue
        pitch, roll = street_seat(T, mx, my, yaw, L, w)
        segs.append({"kind": s["kind"], "chain": int(s["chain"]), "seq": int(s["seq"]),
                     "loc_cm": [round(mx, 1), round(my, 1), round(float(T.z_cm(mx, my)), 1)],
                     "yaw_deg": round(yaw, 2), "pitch_deg": pitch, "roll_deg": roll,
                     "len_cm": round(L, 1), "width_cm": w})
        for (px, py) in ((ax, ay), (bx, by)):
            key = (round(px / 50.0), round(py / 50.0))
            ends.setdefault(key, [0, s["kind"], (px, py)])[0] += 1
    junctions = [(v[1], v[2]) for v in ends.values() if v[0] >= 3]
    stats = {"source_streets": len(plan["streets"]), "segments": len(segs), "dropped_by_gate": dropped,
             "outside_radius": outside, "junctions": len(junctions), "layout": "image"}
    return segs, junctions, stats


def _point_seg_dist(px, py, s):
    """Distance in cm from a point to a street segment's centreline (from its loc/yaw/len record)."""
    (ax, ay), (bx, by) = city_organic.seg_ends(s)
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 <= 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def plots(pl, bd, segs, junctions, obstacles, cx0, cy0, plaza_cm, rng, draw_size, try_building):
    """Lots come from the plan's building rows; each runs plan_city's gate via try_building. -> ([], stats)."""
    plan, (mcx, mcy), _ = _load(pl)
    gap = float(bd.get("gap_min_m", 2.0)) * 100.0
    house_obbs = []
    stats = {"candidates": 0, "accepted": 0, "overlap": 0, "on_street": 0, "on_landmark": 0, "outside_plan": 0}
    street_obbs = [city_organic.obb(s["loc_cm"][0], s["loc_cm"][1], s["len_cm"], s["width_cm"], s["yaw_deg"]) for s in segs]
    land_obbs = [city_organic.obb(*o) for o in obstacles]

    for b in plan["buildings"]:
        bx, by = cx0 + (float(b["loc_cm"][0]) - mcx), cy0 + (float(b["loc_cm"][1]) - mcy)
        W, D = float(b["size_cm"][0]), float(b["size_cm"][1])
        k = int(b.get("door_side", 0)) % 4
        hyaw = float(b.get("yaw_deg", 0.0)) - 90.0 * k
        sx, sy = (D, W) if k % 2 else (W, D)
        d = math.hypot(bx - cx0, by - cy0)
        stats["candidates"] += 1
        me = city_organic.obb(bx, by, sx, sy, hyaw)

        def extra(_bx=bx, _by=by, _sx=sx, _sy=sy, _yaw=hyaw, _me=me):
            for o in land_obbs:
                if city_organic.obb_overlap(_me, o, gap):
                    return "on_landmark"
            for o in street_obbs:
                if city_organic.obb_overlap(_me, o, 0.0):
                    return "on_street"
            for o in house_obbs:
                if city_organic.obb_overlap(_me, o, gap):
                    return "overlap"
            return None

        why = extra()
        if why:
            stats[why] += 1
            continue
        # street-fronting against the SURVIVING network: a lot whose street was pruned (unconnected to the
        # plaza component) or gate-dropped would read as an orphan downstream; refuse it here, by name.
        front_cm = float((pl.get("image") or {}).get("max_front_distance_m", 25.0)) * 100.0
        if segs:
            dmin = min(_point_seg_dist(bx, by, s) for s in segs)
            if dmin > front_cm:
                stats["no_street"] = stats.get("no_street", 0) + 1
                continue
        if try_building(bx, by, sx, sy, hyaw, d, extra, {"door_side": 0, "fronts": "image", "storeys": int(b.get("storeys", 2))}):
            house_obbs.append(me)
            stats["accepted"] += 1
    return [], stats
