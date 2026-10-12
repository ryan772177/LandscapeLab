"""sg_trial_plan.py -- Shape Grammar trial, OFFLINE half: plan arms A and C for the 8 trial houses and measure them.

    python scripts/sg_trial_plan.py            # writes _verify/sg_trial/plans.json + metrics.json

research/town_kit/SHAPE_GRAMMAR_TRIAL.md; every value from recipes/sg_trial.json. Pure, no editor. Arm B (PCG) is
generated in the editor and measured by the same `facade_metrics` on its read-back instances.

Arm A = the shipped manifest's pieces for those houses, verbatim. Arm C = town_kit_plan.plan_house(style=...) with
the recipe's style, storeys drawn from storey_weights (seeded by house index), roof + gables fitted to the
UPPER footprint when a jetty widens it and shifted with it.

METRICS (per arm; counts printed beside every number, rule 13):
  facades            (house, side, course) rows with >= 1 wall/door
  distinct_sequences how many different module sequences those facades use
  variant_entropy    Shannon entropy (bits) of the 2 m wall variant usage
  instances          pieces placed (walls, doors, corners, roofs, gables, foundations)
"""
import io
import json
import math
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import town_kit_plan as tkp  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPE = os.path.join(REPO, "recipes", "sg_trial.json")
MANIFEST = os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json")


def pick_houses(man, near, count):
    hs = sorted(man["houses"], key=lambda h: math.hypot(h["loc_cm"][0] - near[0], h["loc_cm"][1] - near[1]))
    return hs[:count]


def arm_c_pieces(h, cfg):
    st = cfg["style"]
    sw = cfg["storey_weights"]
    rng = random.Random(1000 + h["index"])
    courses = int(rng.choices([int(k) for k in sw], weights=[float(v) for v in sw.values()], k=1)[0])
    W, D, ds = h["W_cm"], h["D_cm"], h["door_side"]
    pieces = tkp.plan_house(W, D, courses, door_side=ds, seed=h["index"], sub_courses=h["sub_courses"], style=st)
    jet = int(st.get("jetty_cm", 0))
    Wu, Du, dx, dy = tkp.jetty_footprint(W, D, ds, jet) if jet and courses > 1 else (W, D, 0.0, 0.0)
    roof = tkp.plan_roof(Wu, Du, courses)
    if roof is None:
        raise SystemExit("REFUSE: house %d: no roof fits the upper footprint %d x %d" % (h["index"], Wu, Du))
    tail = [roof] + tkp.plan_gables(Wu, Du, courses, roof)
    for p in tail:
        p["x"] = p.get("x", 0.0) + dx
        p["y"] = p.get("y", 0.0) + dy
    return courses, pieces + tail


def facade_metrics(houses_pieces):
    """houses_pieces: [(house_index, pieces)]. A facade = the wall/door modules of one side of one course, keyed by
    (house, rounded z, rounded yaw); the sequence is ordered along the side by position."""
    rows = {}
    var = Counter()
    n_inst = 0
    for hi, pieces in houses_pieces:
        n_inst += len(pieces)
        for p in pieces:
            if p.get("role") not in ("wall", "door"):
                continue
            key = (hi, round(float(p["z"])), round(float(p["yaw"])) % 360)
            rows.setdefault(key, []).append((round(float(p["x"]), 1), round(float(p["y"]), 1), p["mesh"]))
            if "2x2M" in p["mesh"] and p.get("role") == "wall":
                var[p["mesh"]] += 1
    seqs = Counter(tuple(m for _, _, m in sorted(v)) for v in rows.values())
    tot = float(sum(var.values()))
    ent = -sum((c / tot) * math.log(c / tot, 2) for c in var.values()) if tot else 0.0
    return {"facades": len(rows), "distinct_sequences": len(seqs), "variant_entropy_bits": round(ent, 3),
            "variant_counts": dict(var), "instances": n_inst}


def main():
    cfg = json.load(io.open(RECIPE, encoding="utf-8"))
    man = json.load(io.open(MANIFEST, encoding="utf-8"))
    hs = pick_houses(man, cfg["houses"]["near_cm"], int(cfg["houses"]["count"]))
    if len(hs) != int(cfg["houses"]["count"]):
        raise SystemExit("REFUSE: %d houses picked" % len(hs))
    arm_a = [(h["index"], h["pieces"]) for h in hs]
    arm_c, rows = [], []
    for h in hs:
        courses, pcs = arm_c_pieces(h, cfg["arm_c"])
        arm_c.append((h["index"], pcs))
        rows.append({"index": h["index"], "label": h["label"], "W_cm": h["W_cm"], "D_cm": h["D_cm"],
                     "door_side": h["door_side"], "courses_a": h["courses"], "courses_c": courses,
                     "loc_cm": h["loc_cm"], "yaw_deg": h["yaw_deg"]})
    out_dir = os.path.join(REPO, cfg["outputs"])
    os.makedirs(out_dir, exist_ok=True)
    metrics = {"houses": len(hs), "arm_a": facade_metrics(arm_a), "arm_c": facade_metrics(arm_c)}
    json.dump({"houses": rows, "arm_a": [{"index": i, "pieces": p} for i, p in arm_a],
               "arm_c": [{"index": i, "pieces": p} for i, p in arm_c]},
              io.open(os.path.join(out_dir, "plans.json"), "w", encoding="utf-8"), indent=1)
    json.dump(metrics, io.open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(metrics, indent=1))
    # determinism: a second planning pass must be identical
    again = [(h["index"], arm_c_pieces(h, cfg["arm_c"])[1]) for h in hs]
    if again != arm_c:
        raise SystemExit("REFUSE: arm C planning is not deterministic")
    print("arm C deterministic over 2 passes (%d houses)" % len(hs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
