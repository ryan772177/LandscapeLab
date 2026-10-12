"""town_kit_foliage_clear.py -- remove the foliage instances standing in the kit town's clearing (2026-10-06).

    python scripts/town_kit_foliage_clear.py            # dry run: in-world match count vs the offline count
    python scripts/town_kit_foliage_clear.py --commit   # remove them (LandscapeLabTools.RemoveFoliageInBoxes)

Boxes = town_kit_foliage_conflicts.clearing_boxes (houses + yard margin, streets + margin, the plaza square),
oriented, unbounded in Z. Re-runnable: instances an earlier run removed are still in the plans but no longer in
the world. With the removal LEDGER (city/alpine_basin_town_kit_foliage_removed.json, 2026-10-10) the expected
in-world count is the exact set difference clearing - ledger, so houses may MOVE; without it, the old count
subtraction (valid only for GROWING margins over unmoved houses). The OFFLINE count (scripts/town_kit_foliage_conflicts.py, from the foliage PLANS) and
the IN-WORLD count (the loaded InstancedFoliageActors) are two different sources for one number; both are printed
(rule 13) and --commit REFUSES if they differ, or if the world matched nothing. Surgical: nothing else moves --
the foliage plans are NOT regenerated (Ryan's 2026-10-06 ruling, STATE.md: regeneration would move 797k trees).
The removal is recorded in city/alpine_basin_town_kit_foliage_clear.json. Does NOT save.
"""
import argparse
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402

REPO = bootstrap.REPO_ROOT
PAYLOAD = r'''
import json as _json, traceback as _tb, unreal as _u
CFG = _json.loads(r"""__CFG__""")
_out = {"ok": False}
try:
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    _lvl = _w.get_path_name().split(".")[0]
    _out["level"] = _lvl
    if _lvl != CFG["level"]:
        raise RuntimeError("open level is %s, cfg wants %s" % (_lvl, CFG["level"]))
    _xs = [_u.Transform(_u.Vector(b[0], b[1], 0.0), _u.Rotator(0.0, 0.0, b[2]), _u.Vector(1, 1, 1)) for b in CFG["boxes"]]
    _es = [_u.Vector(b[3], b[4], 1.0e6) for b in CFG["boxes"]]
    _m, _r, _per, _ok, _err = _u.LandscapeLabTools.remove_foliage_in_boxes(_xs, _es, bool(CFG["dry_run"]))
    _out.update({"matched": int(_m), "removed": int(_r), "per_type": [str(s) for s in _per], "ok": bool(_ok),
                 "error": str(_err) or None, "dry_run": bool(CFG["dry_run"]), "n_boxes": len(_xs)})
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, indent=1, default=str))
'''


def offline_count():
    out = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "town_kit_foliage_conflicts.py")],
                         capture_output=True, text=True, check=True).stdout
    line = [l for l in out.splitlines() if l.startswith("TOTAL inside:")][0]
    return int(line.split(":")[1].split(";")[0]), out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args(argv)
    import town_kit_foliage_conflicts as tkfc
    man, plan = tkfc.load_inputs()
    m = float(tkp._R["foliage_clear_margin_cm"])
    # ONE declaration of the clearing shapes, shared with the offline count (2026-10-08)
    boxes = [list(b) for b in tkfc.clearing_boxes(man, plan)]
    n_plan, _txt = offline_count()
    # Instances an EARLIER run of this tool already removed are counted by the offline plans but are gone from
    # the world, so expected in-world = offline - previously removed. That holds only if the earlier boxes lie
    # inside these. THE REAL GUARD is the exact equality before --commit (below): if any earlier removal lay
    # outside, the world would match MORE than expected and the commit refuses. The checks here only name the
    # likely cause first (audit 2026-10-08 F2): any margin shrinking (a key absent from an older record = that
    # kind of box did not exist = growth), and the inputs' hashes moving (houses may have moved).
    import hashlib
    rec_p = os.path.join(REPO, "city", "alpine_basin_town_kit_foliage_clear.json")
    prev = json.load(io.open(rec_p, encoding="utf-8")) if os.path.isfile(rec_p) else {}
    prev_removed = int(prev.get("removed_total", prev.get("removed", 0)))
    margins = {"margin_cm": m, "street_margin_cm": float(tkp._R["foliage_clear_street_margin_cm"]),
               "plaza_margin_cm": float(tkp._R["foliage_clear_plaza_margin_cm"])}
    shrunk = [k for k, v in margins.items() if k in prev and float(prev[k]) > v]
    if prev and shrunk:
        print("REFUSE: margin(s) shrank since the last run: %s; removed trees would not come back"
              % ", ".join("%s %.0f -> %.0f" % (k, float(prev[k]), margins[k]) for k in shrunk))
        return 4

    def _sha(rel):
        return hashlib.sha256(io.open(os.path.join(REPO, rel), "rb").read()).hexdigest()[:16]
    inputs = {"city/alpine_basin_town_kit_manifest.json": _sha("city/alpine_basin_town_kit_manifest.json"),
              "city/alpine_basin_town_plan.json": _sha("city/alpine_basin_town_plan.json")}
    # THE LEDGER (2026-10-10, organic re-layout): with houses MOVING, "earlier removals lie inside these boxes" no
    # longer holds, so the expected in-world count is the exact SET difference: clearing set minus the instances
    # already removed (city/alpine_basin_town_kit_foliage_removed.json). Without a ledger, the old subtraction.
    led = tkfc.load_ledger()
    moved = [k for k, v in inputs.items() if prev.get("inputs_sha16", {}).get(k) not in (None, v)]
    if moved and led is None:
        # only meaningful for the old subtraction; the ledger handles moved houses exactly (audit F6)
        print("NOTE: inputs changed since the last run (%s) -- if a house MOVED, an earlier removal may lie outside "
              "these boxes and the equality check below will refuse" % ", ".join(moved))
    sets = tkfc.inside_sets(tkfc.clearing_boxes(man, plan)) if led is not None else None
    if led is not None:
        n_off = sum(len(set(sets[p]) - led.get(p, set())) for p in sets)
        prev_removed = sum(len(v) for v in led.values())
        print("LEDGER: clearing %d, already removed %d (ledger), still standing -> expected in-world %d"
              % (n_plan, prev_removed, n_off))
    else:
        n_off = n_plan - prev_removed
        print("offline in clearing %d, previously removed %d -> expected in-world %d" % (n_plan, prev_removed, n_off))
    import ue_exec

    def run(dry):
        cfg = {"level": man["level_path"], "boxes": boxes, "dry_run": dry}
        code, out, raw = ue_exec.run(PAYLOAD.replace("__CFG__", json.dumps(cfg)), marker="__LL__", timeout=25,
                                     stage_name="town_kit_foliage_clear")
        if not isinstance(out, dict):
            print("COULD NOT LOOK (code %s)\n%s" % (code, (raw or "")[-1500:]))
            return None
        return out

    dry = run(True)
    if dry is None:
        return 4
    print("offline (plans): %d   in-world (loaded IFAs): %s   per type %s   boxes %d  margin %.0f cm"
          % (n_off, dry.get("matched"), dry.get("per_type"), len(boxes), m))
    if not dry.get("ok"):
        print("dry run failed: %s" % dry.get("error"))
        return 4
    if not a.commit:
        print("dry run (pass --commit)")
        return 0
    if dry["matched"] == 0 or dry["matched"] != n_off:
        print("REFUSE: in-world %d vs offline %d -- two sources for one number disagree (or matched nothing)"
              % (dry["matched"], n_off))
        return 4
    res = run(False)
    if res is None or not res.get("ok") or res.get("removed") != n_off:
        print("COMMIT FAILED: %s" % json.dumps(res, indent=1)[:2000])
        return 4
    again = run(True)
    rec = {"_produced_by": "scripts/town_kit_foliage_clear.py", "manifest": "city/alpine_basin_town_kit_manifest.json",
           "plan": "city/alpine_basin_town_plan.json", "inputs_sha16": inputs, **margins,
           "offline_in_clearing": n_plan, "removed_this_run": res["removed"],
           "removed_total": prev_removed + res["removed"], "per_type_this_run": res["per_type"],
           "previous_runs": (prev.get("previous_runs", []) + [{k: v for k, v in prev.items() if k != "previous_runs"}])
           if prev else [],
           "after_dry_run_matched": again and again.get("matched")}
    with io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_foliage_clear.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    if led is not None and again and again.get("matched") == 0:
        # append this run's removals to the ledger (the union; ledger only grows) -- ONLY once the after-check
        # finds nothing left standing (world-tools audit 2026-10-10 F7)
        for p, idx in sets.items():
            led.setdefault(p, set()).update(idx)
        doc = json.load(io.open(tkfc.LEDGER, encoding="utf-8"))
        doc["removed"] = {p: sorted(v) for p, v in led.items()}
        doc["removed_total"] = sum(len(v) for v in led.values())
        with io.open(tkfc.LEDGER, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        print("ledger now %d removed instances" % doc["removed_total"])
        print("NOTE: the ledger is written BEFORE the level is saved. If this editor session is discarded "
              "unsaved, restore it: git checkout -- %s" % os.path.relpath(tkfc.LEDGER, REPO).replace("\\", "/"))
    elif led is not None:
        print("ledger NOT appended: the after-check still matched %s" % (again and again.get("matched")))
    print(json.dumps(rec, indent=1))
    return 0 if again and again.get("matched") == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
