"""measure_reach_lattice.py -- re-measure the world's reachable LATTICE (R-ENCOUNTER step 1) and diff it (2026-10-08).

    python scripts/measure_reach_lattice.py            # measure to a scratch file and diff; installs nothing
    python scripts/measure_reach_lattice.py --install  # ... gate, install as city/alpine_basin_reachable_lattice.json,
                                                        #     and stamp it (scripts/stamp_plan.py)

Drives scripts/city_reachable_lattice_payload.txt with the box and step the COMMITTED lattice was bound to (so the
two are the same grid), under resource_guard.HeavyOp (whole-world load). Before this tool the payload was driven by
hand. Diff: cells reachable old vs new, and how many changed cells lie inside the town box (the kit town is the
only intended change since the last measurement). Install gates (audit 2026-10-08): ZERO cells changed outside
the town box (the real regression control); projecting-but-unreachable cells exist (the BFS can say no -- the
50 km point is outside the grid and is not a control); agent, nav chunk count and the whole grid (min, max, step)
unchanged; HLOD proxies and the kit-town tag's own actors were ignored by the ground traces.
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import resource_guard  # noqa: E402

REPO = bootstrap.REPO_ROOT
LAT = os.path.join(REPO, "city", "alpine_basin_reachable_lattice.json")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--accept-outside", type=int, default=None,
                    help="install despite EXACTLY this many cells changed outside the town (investigated)")
    ap.add_argument("--reason", default=None, help="why the outside changes are accepted (recorded in the file)")
    a = ap.parse_args(argv)
    if (a.accept_outside is None) != (a.reason is None):
        print("REFUSE: --accept-outside and --reason go together")
        return 2
    old = json.load(io.open(LAT, encoding="utf-8"))
    b = old["_bound_to"]
    (x0, y0), (x1, y1), step = b["box_min_cm"], b["box_max_cm"], int(b["lattice_step_cm"])
    out_p = os.path.join(REPO, "LandscapeLab", "Saved", "reach_lattice_measured.json")
    src = io.open(os.path.join(REPO, "scripts", "city_reachable_lattice_payload.txt"), encoding="utf-8").read()
    for k, v in (("__MIN_X__", x0), ("__MIN_Y__", y0), ("__MAX_X__", x1), ("__MAX_Y__", y1), ("__STEP_CM__", step)):
        src = src.replace(k, repr(v))
    src = src.replace("__OUT__", out_p.replace("\\", "/"))
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    src = src.replace("__TOWN_TAGS__", repr([man["tag"]]))
    import ue_exec
    with resource_guard.HeavyOp("reachable lattice (whole-world load)") as ok:
        if not ok:
            print("REFUSE: another heavy operation holds the lock")
            return 8
        code, out, raw = ue_exec.run(src, marker="__LL__", timeout=25, stage_name="reach_lattice", quiet=True)
    if not isinstance(out, dict) or not out.get("ok"):
        print("FAILED (code %s): %s" % (code, json.dumps(out, default=str)[:2000] if isinstance(out, dict)
                                         else (raw or "")[-1500:]))
        return 4
    new = json.load(io.open(out_p, encoding="utf-8"))
    print("reply: %s" % {k: out.get(k) for k in ("cells", "cells_projecting", "cells_reachable", "path_queries",
                                                 "control_50km_projects", "control_seed_reachable", "trace_ignored")})
    so = set((r[0], r[1]) for r in old["rows"])
    sn = set((r[0], r[1]) for r in new["rows"])
    if not sn:
        print("REFUSE: zero reachable rows (rule 13)")
        return 4
    import town_kit_load_region
    (tx0, ty0, _z0), (tx1, ty1, _z1), _lvl = town_kit_load_region.town_box()   # the one town-box declaration (F6)

    def in_town(p):
        return tx0 <= p[0] <= tx1 and ty0 <= p[1] <= ty1
    lost, gained = so - sn, sn - so
    out_town = sum(1 for p in lost | gained if not in_town(p))
    unreach_proj = int(out.get("cells_projecting", 0)) - int(out.get("cells_reachable", 0))
    old_unreach = int(old["counts"]["projecting"]) - int(old["counts"]["reachable"])
    print("cells reachable: %d -> %d; lost %d (in town box %d), gained %d (in town box %d); OUTSIDE the town %d"
          % (len(so), len(sn), len(lost), sum(1 for p in lost if in_town(p)), len(gained),
             sum(1 for p in gained if in_town(p)), out_town))
    print("projecting-but-unreachable cells: %d (old %d) -- the BFS can say no" % (unreach_proj, old_unreach))
    if not a.install:
        print("measured only (pass --install to gate and install)")
        return 0
    nb = new["_bound_to"]
    ti = out.get("trace_ignored") or {}
    # OUTSIDE_TOWN_TOLERANCE = 0 cells: the kit town is the only intended change, and the previous rebuild
    # comparison moved 0 of 1,141 rows (RECIPES.md R-ENCOUNTER, "Re-measuring the reachable region", 2026-08-26).
    # Any change away from the town is a regression signal -- investigate, do not loosen (audit 2026-10-08 F3).
    OUTSIDE_TOWN_TOLERANCE = 0
    # an investigated exception is EXACT (the count must match what was investigated) and is recorded in the file
    accepted = a.accept_outside is not None and out_town == a.accept_outside
    gates = {
        ("changes outside the town <= %d" % OUTSIDE_TOWN_TOLERANCE if not accepted else
         "changes outside the town == %d, ACCEPTED: %s" % (a.accept_outside, a.reason)):
            out_town <= OUTSIDE_TOWN_TOLERANCE or accepted,
        "BFS says no somewhere (projecting-but-unreachable > 0)": unreach_proj > 0,
        "agent unchanged": abs(nb["navmesh_agent"]["agent_max_slope"] - b["navmesh_agent"]["agent_max_slope"]) < 1e-3,
        "nav chunks unchanged": nb["nav_chunk_actors_resident"] == b["nav_chunk_actors_resident"],
        "same grid": (nb["box_min_cm"] == b["box_min_cm"] and nb["box_max_cm"] == b["box_max_cm"]
                      and nb["lattice_step_cm"] == b["lattice_step_cm"]),
        "HLOD proxies ignored": int(ti.get("hlod", 0)) > 0,
        "kit-town actors ignored (own count)": int(ti.get(man["tag"], 0)) > 0,
    }
    print("install gates: %s" % gates)
    if not all(gates.values()):
        print("REFUSE to install")
        return 4
    if accepted:
        new["_install_note"] = {"cells_changed_outside_town": out_town, "accepted_because": a.reason,
                                "lost": len(lost), "gained": len(gained)}
        with io.open(out_p, "w", encoding="utf-8") as fh:
            json.dump(new, fh)
    shutil.copyfile(out_p, LAT)
    st = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "stamp_plan.py"), os.path.relpath(LAT, REPO)],
                        capture_output=True, text=True, cwd=REPO)
    print("installed %s; stamp_plan exit %d: %s" % (os.path.relpath(LAT, REPO), st.returncode,
                                                   (st.stdout + st.stderr).strip()[-300:]))
    return 0 if st.returncode == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
