"""town_kit_reachability.py -- re-measure the town's reachable region after the kit town (2026-10-08).

    python scripts/town_kit_reachability.py            # measure to a scratch file and diff; installs nothing
    python scripts/town_kit_reachability.py --install  # ... gate, install as city/alpine_basin_town_reachable.json,
                                                        #     and stamp it (scripts/stamp_plan.py)

Drives scripts/city_reachable_region_payload.txt (RECIPES "Re-measuring the reachable region after ANY navmesh
build"). Refuses to RUN unless the navmesh was rebuilt after the town -- checked on the BUILT DATA (audit F5): every
saved NavigationDataChunkActor package (64, the lattice's count) is newer than every saved kit-house package, and
the build log reached its final "[N / N] Processing cells" line. Runs under resource_guard.HeavyOp (the payload
loads the WHOLE world). Building rows use the doorstep in front of each house's own door (manifest door side +
150 cm, geometry imported from town_kit_manifest). Refuses to INSTALL unless the relay converged, the positive
control had 0 failures, the 50 km negative control did not path, the agent matches the committed binding, and the
resident chunk count equals the lattice's (reachability.py refuses any other). The street diff is by position and
is only reported when the two files' street rows are the same streets (loc within 1 cm); the committed file was
measured on the primitive town, so building rows are reported as a count, never as flips.
"""
import argparse
import glob
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import resource_guard  # noqa: E402
from town_kit_manifest import SIDE_NORMALS, _world  # noqa: E402  (one declaration of the door geometry)

REPO = bootstrap.REPO_ROOT
NAVLOG = os.path.join(REPO, "_verify", "navmesh_build_WorldPartitionNavigationDataBuilder.log")
SIDE = os.path.join(REPO, "city", "alpine_basin_town_reachable.json")
LATTICE = os.path.join(REPO, "city", "alpine_basin_reachable_lattice.json")
EXT = os.path.join(REPO, "LandscapeLab", "Content", "__ExternalActors__", "Alpine8K")


def package_mtimes(needle):
    """mtimes of saved Alpine8K external-actor packages whose bytes contain needle (exact token match)."""
    pat = re.compile(re.escape(needle.encode("ascii")) + rb"(?![A-Za-z0-9_])")
    out = []
    for f in glob.glob(os.path.join(EXT, "**", "*.uasset"), recursive=True):
        with io.open(f, "rb") as fh:
            if pat.search(fh.read()):
                out.append(os.path.getmtime(f))
    return out


def doorsteps(man):
    out = {}
    for h in man["houses"]:
        n = SIDE_NORMALS[h["door_side"]]
        lx, ly = h["trace_local_xy"][0] + 150.0 * n[0], h["trace_local_xy"][1] + 150.0 * n[1]
        out[str(h["index"])] = list(_world(h["loc_cm"][0], h["loc_cm"][1], h["yaw_deg"], lx, ly))
    return out


def rows(d, kind):
    # the sidecar stores street_rows / building_rows as lists in plan order (no idx field)
    return d.get("street_rows" if kind == "street" else "building_rows") or []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--install", action="store_true")
    a = ap.parse_args(argv)
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    lat = json.load(io.open(LATTICE, encoding="utf-8"))
    want_chunks = int(lat["_bound_to"]["nav_chunk_actors_resident"])
    houses = package_mtimes(man["tag"])
    chunks = package_mtimes("NavigationDataChunkActor")
    print("saved kit houses %d (manifest %d); saved nav chunk packages %d (lattice %d)"
          % (len(houses), len(man["houses"]), len(chunks), want_chunks))
    if len(houses) != len(man["houses"]) or len(chunks) != want_chunks:
        print("REFUSE: package counts do not match")
        return 4
    if min(chunks) <= max(houses):
        print("REFUSE: a nav chunk package is older than the newest saved house -- run R-NAVBUILD first")
        return 4
    log = io.open(NAVLOG, encoding="utf-8", errors="replace").read() if os.path.isfile(NAVLOG) else ""
    cells = re.findall(r"\[(\d+) / (\d+)\] Processing cells", log)
    if not cells or cells[-1][0] != cells[-1][1]:
        print("REFUSE: the navmesh build log never reached its final Processing-cells line")
        return 4
    print("navmesh rebuilt after the town: all %d chunks newer than all %d houses; log [%s / %s] cells"
          % (len(chunks), len(houses), cells[-1][0], cells[-1][1]))

    out_p = os.path.join(REPO, "LandscapeLab", "Saved", "town_reachable_measured.json")
    kit = {"level": man["level_path"], "town_tags": [man["tag"]], "doors": doorsteps(man)}
    src = io.open(os.path.join(REPO, "scripts", "city_reachable_region_payload.txt"), encoding="utf-8").read()
    src = (src.replace("__PLAN__", os.path.join(REPO, "city", "alpine_basin_town_plan.json").replace("\\", "/"))
              .replace("__OUT__", out_p.replace("\\", "/")).replace("__KIT__", json.dumps(kit)))
    import ue_exec
    with resource_guard.HeavyOp("town reachability (whole-world load)") as ok:
        if not ok:
            print("REFUSE: another heavy operation holds the lock")
            return 8
        code, out, raw = ue_exec.run(src, marker="__LL__", timeout=25, stage_name="town_kit_reachability")
    if not isinstance(out, dict) or not out.get("ok"):
        print("FAILED (code %s): %s" % (code, json.dumps(out, default=str)[:2000] if isinstance(out, dict)
                                         else (raw or "")[-1500:]))
        return 4
    new = json.load(io.open(out_p, encoding="utf-8"))
    old = json.load(io.open(SIDE, encoding="utf-8"))
    sn, bn, so = rows(new, "street"), rows(new, "building"), rows(old, "street")
    if not sn or not bn:
        print("REFUSE: zero rows parsed from the new sidecar (rule 13) -- keys: %s" % sorted(new))
        return 4
    nb = new["_bound_to"]
    print("reply: %s" % {k: out.get(k) for k in ("streets", "buildings", "trace_ignored_by_tag", "loaded_bounds",
                                                 "control_positive_failures", "control_50km_pathable", "trace_ignored_hlod_actors")})
    print("binding new: %s" % {k: nb.get(k) for k in ("nav_chunk_actors_resident", "converged", "rounds_to_converge",
                                                    "building_doorstep")})
    same = len(so) == len(sn) and all(abs(p["loc_cm"][0] - q["loc_cm"][0]) < 1 and abs(p["loc_cm"][1] - q["loc_cm"][1]) < 1
                                      for p, q in zip(so, sn))
    if same:
        flips = [i for i, (p, q) in enumerate(zip(so, sn)) if bool(p.get("reachable")) != bool(q.get("reachable"))]
        print("STREETS: %d rows (same streets), reachable %d -> %d, flipped %d %s"
              % (len(sn), sum(1 for r in so if r.get("reachable")), sum(1 for r in sn if r.get("reachable")),
                 len(flips), flips[:20]))
    else:
        print("STREETS: NOT COMPARABLE with the committed sidecar (%d vs %d rows / locations differ); new reachable %d"
              % (len(so), len(sn), sum(1 for r in sn if r.get("reachable"))))
    nbr = sum(1 for r in bn if r.get("reachable"))
    print("BUILDINGS (kit town, doorstep at the door): %d rows, reachable %d (%.1f%%)"
          % (len(bn), nbr, 100.0 * nbr / len(bn)))
    if not a.install:
        print("measured only (pass --install to gate and install)")
        return 0
    gates = {
        "converged": bool(nb.get("converged")),
        "positive control 0 failures": out.get("control_positive_failures") == 0,
        # The 50 km point is OFF the 8 km world, so it usually does not project and the path query never runs
        # (payload :261-264) -- "cannot join the set" holds, but as a negative control it is WEAK: it never
        # exercises the relay. OPEN: a known-disconnected on-navmesh point. Both outcomes are named in the report.
        "50 km control cannot join (did not project, or did not path)":
            out.get("control_50km_projects") is False or out.get("control_50km_pathable") is False,
        "agent max slope unchanged": abs(float(nb["navmesh_agent"]["agent_max_slope"])
                                         - float(old["_bound_to"]["navmesh_agent"]["agent_max_slope"])) < 1e-3,
        "chunks == lattice": int(nb.get("nav_chunk_actors_resident", -1)) == want_chunks,
    }
    print("install gates: %s" % gates)
    if not all(gates.values()):
        print("REFUSE to install")
        return 4
    shutil.copyfile(out_p, SIDE)
    st = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "stamp_plan.py"),
                         os.path.relpath(SIDE, REPO)], capture_output=True, text=True, cwd=REPO)
    print("installed %s; stamp_plan exit %d: %s" % (os.path.relpath(SIDE, REPO), st.returncode,
                                                   (st.stdout + st.stderr).strip()[-400:]))
    return 0 if st.returncode == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
