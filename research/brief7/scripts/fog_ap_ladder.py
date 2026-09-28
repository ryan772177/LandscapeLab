"""fog_ap_ladder.py -- drive the Brief 7 aerial-perspective ladder end to end.

For each cell: set fog/atmosphere via scripts/brief7_fog_ap_set_payload.txt
(read back inside the payload, rule 12), then for each camera: place the
viewport camera (brief7_place_cam_payload, traced ground + eye), SLEEP ON THE
HOST for the foliage-LOD settle (LESSONS 2026-09-23: a 4 s settle leaves
foliage at card LODs), then scripts/shoot.py (host-side wait for the file).
Every value the editor reported is written to <outdir>/ladder_log.json.

Runtime only -- the payload saves nothing; the LAST cell run should be the
baseline so the live editor is left where it started (the driver appends
that restore cell itself unless --no-restore).

Usage:
    python research/brief7/scripts/fog_ap_ladder.py --cells cells.json \
        --cams cams.json --outdir <abs dir> [--settle 25] [--res 3840x2160]

cells.json: [{"name": "ap1_white", "density": 0.0015, "start": 15000,
              "albedo": "255,255,255", "ap": 1.0}, ...]
cams.json:  {"camA": {"x": -201186, "y": 219000, "pitch": -9, "yaw": 270,
                      "eye": 1599.8, "fov": 70}, ...}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
UE_EXEC = os.path.join(REPO, "scripts", "ue_exec.py")
SET_PAYLOAD = os.path.join(REPO, "scripts", "brief7_fog_ap_set_payload.txt")
CAM_PAYLOAD = os.path.join(REPO, "scripts", "brief7_place_cam_payload.txt")
SHOOT = os.path.join(REPO, "scripts", "shoot.py")

BASELINE = {"name": "restore_baseline", "density": 0.00416, "start": 0.0,
            "albedo": "255,255,255", "ap": 1.0,
            # Brief 2 atmosphere (recipes/alpine_8k.json lighting.atmosphere,
            # read back live 2026-09-26): the bench values.
            "mie": 0.01, "rayleigh": 0.0331}


def ue(payload: str, sets: dict) -> dict:
    cmd = [sys.executable, UE_EXEC, payload, "--timeout", "25"]
    for k, v in sets.items():
        cmd += ["--set", "%s=%s" % (k, v)]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    out = r.stdout
    i = out.find("{")
    j = out.rfind("}")
    if i < 0 or j < 0:
        raise RuntimeError("no JSON from %s: %s %s" % (payload, out[-300:], r.stderr[-300:]))
    d = json.loads(out[i:j + 1])
    if not d.get("ok"):
        raise RuntimeError("%s reported error: %s" % (os.path.basename(payload), d.get("error")))
    return d


def shoot(name: str, loc: str, rot: str, fov: float, res: str, outdir: str) -> str:
    cmd = [sys.executable, SHOOT, "--name", name, "--loc=%s" % loc, "--rot=%s" % rot,
           "--fov", str(fov), "--res", res, "--outdir", outdir, "--deadline", "600"]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("shoot %s exit %d: %s" % (name, r.returncode, r.stdout[-400:]))
    p = os.path.join(outdir, name + ".png")
    if not os.path.isfile(p):
        raise RuntimeError("shoot %s: no file at %s" % (name, p))
    return p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True)
    ap.add_argument("--cams", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--settle", type=float, default=25.0)
    ap.add_argument("--res", default="3840x2160")
    ap.add_argument("--no-restore", action="store_true")
    a = ap.parse_args(argv)
    cells = json.load(open(a.cells))
    cams = json.load(open(a.cams))
    if not a.no_restore:
        cells = list(cells) + [BASELINE]
    os.makedirs(a.outdir, exist_ok=True)
    log = []
    t0 = time.time()
    for c in cells:
        print("== cell %s" % c["name"], flush=True)
        rb = ue(SET_PAYLOAD, {"DENSITY": c["density"], "START": c["start"],
                              "ALBEDO": c["albedo"], "AP": c["ap"],
                              "MIE": c.get("mie", "keep"),
                              "RAYLEIGH": c.get("rayleigh", "keep")})
        entry = {"cell": c, "readback": rb["readback"], "cvars": rb["cvars"], "shots": {}}
        print("   readback density %.5f start %.0f albedo %s ap %.2f mie %.5f rayleigh %.5f" % (
            rb["readback"]["fog_density"], rb["readback"]["start_distance"],
            rb["readback"]["volumetric_fog_albedo"], rb["readback"]["ap_scale"],
            rb["readback"]["mie_scattering_scale"],
            rb["readback"]["rayleigh_scattering_scale"]), flush=True)
        if c["name"] == "restore_baseline":
            log.append(entry)
            continue
        for cam, k in cams.items():
            pc = ue(CAM_PAYLOAD, {"X": k["x"], "Y": k["y"], "PITCH": k["pitch"],
                                  "YAW": k["yaw"], "EYE": k["eye"]})
            time.sleep(a.settle)
            name = "%s_%s" % (cam, c["name"])
            p = shoot(name, pc["shoot_loc"], "0,%s,%s" % (k["pitch"], k["yaw"]),
                      k["fov"], a.res, a.outdir)
            entry["shots"][cam] = {"file": os.path.basename(p), "cam_loc": pc["cam_loc"],
                                   "cam_rot_rpy": pc["cam_rot_rpy"]}
            print("   %s -> %s (%.0f s elapsed)" % (cam, os.path.basename(p),
                                                  time.time() - t0), flush=True)
        log.append(entry)
        with open(os.path.join(a.outdir, "ladder_log.json"), "w") as f:
            json.dump(log, f, indent=2)
    with open(os.path.join(a.outdir, "ladder_log.json"), "w") as f:
        json.dump(log, f, indent=2)
    print("DONE %d cells in %.0f s" % (len(cells), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
