"""survey_shots.py — multi-station survey of a sample project's map, via remote
execution (the station COUNT comes from the live world's census, not a fixed
number). THE ROUTE THAT WORKS.

  derive stations from the LIVE world's bounds  (census_and_shoot.py)
  trace the ground under each station           (trace_station_ground.py)
  place the camera at traced ground + eye
  shoot each station                            (shoot.py, host-side wait)

WHY NOT -ExecCmds
-----------------
Four attempts across City Sample and Dark Ruins never moved the camera:
-ExecCmds fires every command in one batch at startup, so HighResShot lands
before the teleport reaches the rendered view. shoot.py drives the EDITOR
viewport through the remote channel and waits for the frame HOST-SIDE, so the
editor stays alive and ticking. That needs bRemoteExecution=True in the
sample's config -- see scripts/enable_sample_remote_exec.py.

TWO THINGS THAT COST FRAMES, BOTH NOW BUILT IN
----------------------------------------------
  * ONE GLOBAL ground_z IS NOT ENOUGH. The station derivation uses the median
    actor base across the whole world; on a 3.3 km map of mesas and canyons
    that is metres of rock from the truth at any given XY, and shoot.py
    refused two stations as 24 m and 67 m underground. Each station gets its
    own trace.
  * bTraceComplex MUST BE True. With False the trace uses SIMPLE collision,
    which sat 12.4 m below the visible surface on Electric Dreams, and
    shoot.py refused the station a second time.

shoot.py's underground refusal is a FEATURE and is never suppressed: an
underground frame looks like content and would file as a survey shot.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(REPO, "LandscapeLab", "Saved", "LLPython")
PAYLOADS = os.path.join(REPO, "scripts", "payloads")

EYE_CM = {"ground_closeup": 175.0, "against_sky": 250.0}


def stage(name, src_name, subs):
    with io.open(os.path.join(PAYLOADS, src_name), encoding="utf-8") as _fh:
        src = _fh.read()
    for k, v in subs.items():
        src = src.replace("__%s__" % k, str(v))
    left = [x for x in sorted(set(re.findall(r"__[A-Z_]+__", src)))
            if x != "__LL__"]
    if left:
        raise SystemExit("REFUSE: unsubstituted placeholders %s" % left)
    compile(src, name, "exec")
    os.makedirs(STAGE, exist_ok=True)
    dst = os.path.join(STAGE, name)
    with io.open(dst, "w", encoding="utf-8", newline="") as _fh:
        _fh.write(src)
    return dst


def run_payload(path, project_root, timeout=25):
    p = subprocess.run([sys.executable,
                        os.path.join(REPO, "scripts", "ue_exec.py"), path,
                        "--project-root", project_root,
                        "--timeout", str(timeout)],
                       capture_output=True, text=True, cwd=REPO)
    out = (p.stdout or "") + (p.stderr or "")
    dec, blob, i = json.JSONDecoder(), None, out.find("{")
    while i != -1:
        try:
            cand, _ = dec.raw_decode(out[i:])
            if isinstance(cand, dict) and "ok" in cand:
                blob = cand
                break
        except ValueError:
            pass
        i = out.find("{", i + 1)
    return blob, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--tag", required=True, help="prefix for the filenames")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--stations-out", required=True)
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--fov", type=float, default=75.0)
    a = ap.parse_args()

    out = os.path.abspath(a.outdir)
    os.makedirs(out, exist_ok=True)
    st_json = os.path.abspath(a.stations_out)

    # 1. stations from the LIVE world (no map load, no census re-run)
    p = stage("survey_stations.py", "census_and_shoot.py",
              {"OUT": "", "MAP": "", "STATIONS_OUT": st_json.replace("\\", "/"),
               "CENSUS_SRC": ""})
    blob, raw = run_payload(p, a.project_root)
    if not blob or not blob.get("ok"):
        print("REFUSE: could not derive stations")
        print(raw[-700:])
        return 1
    # F3: don't KeyError on a payload that returned ok without stations.
    stations = blob.get("stations") or []
    # F1/NN13: zero stations means nothing to survey; do NOT let the tail
    # `len(filed) == len(stations)` (0 == 0) report success over an empty run.
    if not stations:
        print("REFUSE: no stations derived from the world")
        print(raw[-700:])
        return 1
    print("world: %s   stations: %d" % (blob.get("current_world"), len(stations)))
    print("bounds: %s" % json.dumps(blob.get("bounds")))

    # 2. trace the ground under every station
    t = stage("survey_trace.py", "trace_station_ground.py",
              {"STATIONS": json.dumps(stations),
               "TRACE_TOP_CM": "200000", "TRACE_BOTTOM_CM": "-50000"})
    tb, traw = run_payload(t, a.project_root)
    if not tb or not tb.get("ok"):
        print("REFUSE: ground trace failed")
        print(traw[-700:])
        return 1
    # F3: same key guard on the trace payload.
    if not tb.get("stations"):
        print("REFUSE: ground trace returned no stations")
        print(traw[-700:])
        return 1
    ground = {s["name"]: s for s in tb["stations"]}

    # 3. shoot, each at its own traced ground + eye height
    filed, refused = [], []
    for s in stations:
        g = ground.get(s["name"]) or {}
        if not g.get("hit"):
            refused.append((s["name"], "NO GROUND HIT -- not guessed at"))
            print("  %-16s NO GROUND HIT, skipped" % s["name"])
            continue
        if "ground_z" not in g:
            # F5: a hit record without ground_z is not a usable floor.
            refused.append((s["name"], "hit but no ground_z reported"))
            print("  %-16s HIT but no ground_z, skipped" % s["name"])
            continue
        z = float(g["ground_z"]) + EYE_CM.get(s["name"], 0.0)
        # Stations above the ground by design (vista, overview) keep their
        # derived height if the trace would LOWER them -- the trace is a floor,
        # not a target.
        z = max(z, float(s["loc"][2])) if s["name"] not in EYE_CM else z
        cmd = [sys.executable, os.path.join(REPO, "scripts", "shoot.py"),
               "--name", "%s__%s" % (a.tag, s["name"]),
               "--loc=%.1f,%.1f,%.1f" % (s["loc"][0], s["loc"][1], z),
               "--rot=0,%.1f,%.1f" % (s["pitch"], s["yaw"]),
               "--fov", str(a.fov), "--res", a.res, "--outdir", out,
               "--project-root", a.project_root, "--deadline", "600"]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
        if r.returncode == 0:
            filed.append(s["name"])
            print("  %-16s z=%-9.0f FILED" % (s["name"], z))
        else:
            msg = ""
            for ln in (r.stdout or "").splitlines():
                if "REFUSE" in ln or "Error" in ln:
                    msg = ln.strip()[:110]
            refused.append((s["name"], msg or "exit %d" % r.returncode))
            print("  %-16s z=%-9.0f %s" % (s["name"], z, msg or "FAILED"))

    print(json.dumps({"filed": filed, "refused": refused,
                      "outdir": os.path.relpath(out, REPO)}, indent=2))
    return 0 if (stations and len(filed) == len(stations)) else 1


if __name__ == "__main__":
    sys.exit(main())
