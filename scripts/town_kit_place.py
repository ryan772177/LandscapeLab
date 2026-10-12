"""town_kit_place.py -- place the kit town from its manifest, in batches (2026-10-06).

    python scripts/town_kit_place.py --dry-run                  # what would be placed, nothing sent
    python scripts/town_kit_place.py --rig-test 3 --go          # first 3 manifest houses, moved onto the rig row
    python scripts/town_kit_place.py --go [--start 0 --limit N --batch 12]   # the manifest's own level (Alpine8K)

Reads city/<city_id>_kit_manifest.json (scripts/town_kit_manifest.py -- the ONE manifest; nothing here re-plans).
Each batch is one editor round trip through scripts/payloads/town_kit_build_house.py ({"batch": [...]}), which
stops at its first failed house; this driver stops on a batch that returned no result or any failure
(standing rule 6). replace=true: re-running a range rebuilds those houses (label + tag guarded). Does NOT save,
does NOT touch the primitive town (scripts/payloads/town_kit_clear_primitives.py does, separately, dry-run first).

--rig-test K: the first K houses keep their pieces, foundation and door-side trace, but are relabelled
TownKit_RigTest_<i>, tagged with the probe tag, and laid in a row 30 m ahead of the rig hero camera on
/Game/LookDevMtn -- the batch path, the door-side trace and the foundation proven where a mistake costs nothing.
"""
import argparse
import io
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402

REPO = bootstrap.REPO_ROOT
MANIFEST = os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json")
PAYLOAD = os.path.join(REPO, "scripts", "payloads", "town_kit_build_house.py")


def specs_for(houses, level, rig=False):
    out = []
    pr = tkp._R["probe"]
    cx, cy = pr["camera_xy_cm"]
    r = math.radians(pr["camera_yaw_deg"])
    fwd, side = (math.cos(r), math.sin(r)), (-math.sin(r), math.cos(r))
    for k, h in enumerate(houses):
        s = {"level": level, "label": h["label"], "tags": list(h["tags"]), "loc_cm": list(h["loc_cm"]),
             "yaw_deg": h["yaw_deg"], "ground_trace": True, "ground_offset_cm": 0.0,
             "trace_local_xy": h["trace_local_xy"], "box_center_cm": h["box_center_cm"],
             "box_extent_cm": h["box_extent_cm"], "replace": True, "pieces": h["pieces"]}
        if rig:
            dist = float(pr["rig_test_dist_m"]) * 100.0
            off = (k - (len(houses) - 1) / 2.0) * float(pr["rig_test_spacing_m"]) * 100.0
            s["label"] = "TownKit_RigTest_%d" % k
            s["tags"] = [pr["tag"]]
            s["level"] = pr["level"]
            s["loc_cm"] = [cx + fwd[0] * dist + side[0] * off, cy + fwd[1] * dist + side[1] * off, 0.0]
            s["yaw_deg"] = pr["camera_yaw_deg"] + 90.0 - 180.0 + float(pr["rig_test_yaw_step_deg"]) * k
        out.append(s)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rig-test", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--update-in-place", action="store_true",
                    help="re-set the instance lists of the EXISTING houses (same actors, same GUIDs) instead of "
                         "destroying and respawning them -- keeps HLOD setup source lists and the navmesh valid. "
                         "Meshes dropped from a house's pieces keep their old instances (add/change only).")
    a = ap.parse_args(argv)
    man = json.load(io.open(MANIFEST, encoding="utf-8"))
    # non-negotiable 20: a stale manifest is refused before it can drive the editor (audit F2)
    import plan_stamp
    verdict, rows = plan_stamp.verify(man, REPO)
    print("manifest stamp: %s (%d inputs)" % (verdict, len(man.get(plan_stamp.STAMP_KEY) or {})))
    if verdict != "MATCHES":
        print("REFUSE: re-run scripts/town_kit_manifest.py; moved: %s" % [r[0] for r in rows])
        return 4
    houses = man["houses"]
    if a.rig_test:
        sel = houses[:a.rig_test]
        specs = specs_for(sel, man["level_path"], rig=True)
    else:
        sel = houses[a.start:(a.start + a.limit) if a.limit else None]
        specs = specs_for(sel, man["level_path"])
        if a.update_in_place:
            for s in specs:
                s["update_in_place"] = True
                s["replace"] = False
    n_p = sum(len(s["pieces"]) for s in specs)
    print("%d houses (%d pieces) -> %s in batches of %d"
          % (len(specs), n_p, specs[0]["level"] if specs else "-", a.batch))
    if not a.go:
        print("dry run (pass --go)")
        return 0
    import ue_exec
    tpl = io.open(PAYLOAD, encoding="utf-8").read()
    done = 0
    t0 = time.time()
    for b0 in range(0, len(specs), a.batch):
        chunk = specs[b0:b0 + a.batch]
        code, out, raw = ue_exec.run(tpl.replace("__SPEC__", json.dumps({"batch": chunk})), marker="__LL__",
                                     timeout=25, stage_name="town_kit_place", quiet=True)
        if not isinstance(out, dict):
            print("STOP: no result from the editor for batch at %d (code %s)\n%s" % (b0, code, (raw or "")[-1500:]))
            return 4
        done += int(out.get("n_done", 0))
        if a.update_in_place:
            # rule 12 (audit 2026-10-09 F7): every house in the batch must report the IN-PLACE path, not a respawn
            n_inp = sum(1 for h in out.get("houses", []) if h.get("updated_in_place"))
            if n_inp != len(out.get("houses", [])):
                print("STOP: %d of %d houses report updated_in_place" % (n_inp, len(out.get("houses", []))))
                return 4
        print("batch %4d-%4d: %d/%d ok  (%.0f s total)" % (b0, b0 + len(chunk) - 1, out.get("n_done", 0),
                                                         len(chunk), time.time() - t0))
        if not out.get("ok"):
            bad = [h for h in out.get("houses", []) if not h.get("ok")]
            print("STOP: %s" % json.dumps(bad[:1], indent=1, default=str)[:3000])
            return 4
    print("placed %d of %d houses" % (done, len(specs)))
    return 0 if done == len(specs) else 4


if __name__ == "__main__":
    sys.exit(main())
