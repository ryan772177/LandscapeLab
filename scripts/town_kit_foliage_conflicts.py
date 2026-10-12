"""town_kit_foliage_conflicts.py -- offline: which foliage-plan instances stand in the kit town's clearing (2026-10-06).

    python scripts/town_kit_foliage_conflicts.py

THE ONE DECLARATION OF THE CLEARING (clearing_boxes): oriented boxes, each (cx, cy, yaw_deg, half_x, half_y) in
world cm --
  * every manifest house footprint grown by recipes/town_kit.json foliage_clear_margin_cm (a yard, not just "out of
    the wall": 2026-10-08 overview showed the town drowned in forest at 100 cm);
  * every plan street segment (len x width) grown by foliage_clear_street_margin_cm;
  * the plaza as a square of half-side plan.plaza_radius_cm + foliage_clear_plaza_margin_cm (a disc's bounding
    square: it clears the corners too, which is the safe direction for a clearing).
scripts/town_kit_foliage_clear.py imports clearing_boxes, so the in-world removal and this offline count can never
use different shapes. Counts the UNION (an instance inside two boxes is one tree, as the in-world set counts it).
Read-only: the foliage plans are not regenerated (Ryan's ruling, STATE.md).
"""
import argparse
import io
import json
import math
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import town_kit_plan as tkp  # noqa: E402


def foliage_plans():
    """foliage/<biome_id>_<name>.json for every PLACED species of the world recipe (no 'system' key -- those are
    landscape grass, not foliage instances), so a fifth species cannot be removed in the world yet missing here
    (audit 2026-10-08 F6). Refuses a declared plan that is not on disk."""
    rec = json.load(io.open(os.path.join(REPO, "recipes", "alpine_8k.json"), encoding="utf-8"))
    out = ["foliage/%s_%s.json" % (rec["biome_id"], s["name"]) for s in rec["foliage"]["species"] if "system" not in s]
    missing = [p for p in out if not os.path.isfile(os.path.join(REPO, p))]
    if not out or missing:
        raise SystemExit("REFUSE: foliage plans %s missing (declared %d)" % (missing, len(out)))
    return out


PLANS = foliage_plans()


def clearing_boxes(man, plan):
    """[(cx, cy, yaw_deg, half_x_cm, half_y_cm)] -- see the module docstring. Margins from the recipe."""
    mh = float(tkp._R["foliage_clear_margin_cm"])
    ms = float(tkp._R["foliage_clear_street_margin_cm"])
    mp = float(tkp._R["foliage_clear_plaza_margin_cm"])
    out = [(h["loc_cm"][0], h["loc_cm"][1], h["yaw_deg"], h["W_cm"] / 2.0 + mh, h["D_cm"] / 2.0 + mh)
           for h in man["houses"]]
    out += [(s["loc_cm"][0], s["loc_cm"][1], s["yaw_deg"], s["len_cm"] / 2.0 + ms, s["width_cm"] / 2.0 + ms)
            for s in plan["streets"]]
    cx, cy = plan["site_centre_cm"]
    r = float(plan["plaza_radius_cm"]) + mp
    out.append((cx, cy, 0.0, r, r))
    # organic plans' open squares are cleared like the plaza (audit 2026-10-10 F15); a lattice plan has none
    out += [(sx, sy, 0.0, sr + mp, sr + mp) for sx, sy, sr in plan.get("squares", [])]
    return out


def load_inputs():
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    plan = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_plan.json"), encoding="utf-8"))
    return man, plan


LEDGER = os.path.join(REPO, "city", "alpine_basin_town_kit_foliage_removed.json")


def inside_sets(boxes):
    """{plan path: sorted list of instance indices inside the clearing} -- the ONE membership test."""
    out = {}
    for p in PLANS:
        d = json.load(io.open(os.path.join(REPO, p), encoding="utf-8"))
        inst = np.asarray([i[:2] for i in d["instances"]], dtype=np.float64)
        inside = np.zeros(len(inst), bool)
        for cx, cy, yaw, hx, hy in boxes:
            a = math.radians(yaw)
            win = math.hypot(hx, hy)
            dx, dy = inst[:, 0] - cx, inst[:, 1] - cy
            near = np.nonzero((np.abs(dx) <= win) & (np.abs(dy) <= win))[0]
            if not len(near):
                continue
            lx = dx[near] * math.cos(a) + dy[near] * math.sin(a)
            ly = -dx[near] * math.sin(a) + dy[near] * math.cos(a)
            inside[near[(np.abs(lx) <= hx) & (np.abs(ly) <= hy)]] = True
        out[p] = [int(i) for i in np.nonzero(inside)[0]]
    return out


def plans_sha16():
    """{plan path: sha256[:16]} of the foliage plans. The ledger's indices mean the same trees ONLY while these
    are unchanged (world-tools audit 2026-10-10 F5: that rested on Ryan's no-regeneration ruling alone)."""
    import hashlib
    return {p: hashlib.sha256(io.open(os.path.join(REPO, p), "rb").read()).hexdigest()[:16] for p in PLANS}


def load_ledger():
    """{plan path: set(indices)} of plan instances ALREADY removed from the world, or None if no ledger. REFUSES if
    the ledger carries no foliage-plan hashes or they no longer match (regenerated plans renumber the trees)."""
    if not os.path.isfile(LEDGER):
        return None
    d = json.load(io.open(LEDGER, encoding="utf-8"))
    rec, now = d.get("plans_sha16"), plans_sha16()
    if rec != now:
        raise SystemExit("REFUSE: the removal ledger's foliage-plan hashes %s do not match the plans on disk %s -- "
                         "its instance indices no longer name the same trees" % (rec, now))
    return {k: set(v) for k, v in d["removed"].items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write-ledger", action="store_true",
                    help="record the CURRENT clearing set as already removed (run ONCE, while the manifest and "
                         "plan are still the ones the removals were made with; 2026-10-10 re-layout)")
    a = ap.parse_args(argv)
    man, plan = load_inputs()
    boxes = clearing_boxes(man, plan)
    sets = inside_sets(boxes)
    total = 0
    for p in PLANS:
        print("%-38s %5d inside the clearing" % (p, len(sets[p])))
        total += len(sets[p])
    print("TOTAL inside: %d; boxes %d (houses %d, streets %d, plaza 1, squares %d)"
          % (total, len(boxes), len(man["houses"]), len(plan["streets"]), len(plan.get("squares", []))))
    led = load_ledger()
    if led is not None:
        new = sum(len(set(sets[p]) - led.get(p, set())) for p in PLANS)
        print("LEDGER: %d already removed; %d of the clearing still standing (expected in-world)"
              % (sum(len(v) for v in led.values()), new))
    if a.write_ledger:
        if led is not None:
            print("REFUSE: a ledger already exists -- it is append-only through town_kit_foliage_clear.py")
            return 4
        rec = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_foliage_clear.json"), encoding="utf-8"))
        if total != int(rec["removed_total"]):
            print("REFUSE: the current clearing set (%d) is not the recorded removed_total (%d) -- the ledger would "
                  "not describe what was removed" % (total, int(rec["removed_total"])))
            return 4
        with io.open(LEDGER, "w", encoding="utf-8") as fh:
            json.dump({"_what": "foliage-plan instances already REMOVED from the world by town_kit_foliage_clear "
                                "(plan path -> instance indices). Built 2026-10-10 from the pre-re-layout manifest "
                                "and plan, equal to the recorded removed_total; appended by every later --commit.",
                       "plans_sha16": plans_sha16(), "removed_total": total, "removed": sets}, fh)
        print("wrote ledger %s (%d instances)" % (os.path.relpath(LEDGER, REPO), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
