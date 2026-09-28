"""perf_flythrough.py — per-zone frame cost along a FIXED route, with an artefact.

Phase E's measuring half. `recipes/perf_budgets.json` declares the stations;
this traces ground under each, then drives `measure_frame_cost.py` at each and
aggregates into `_verify/perf/<date>_<label>.json`. A fixed route is what makes
two sessions comparable — "did we get slower" is only answerable against the
same camera.

IT DRIVES measure_frame_cost RATHER THAN REIMPLEMENTING IT
-----------------------------------------------------------
That tool already accepts `--camera x,y,z,pitch,yaw,roll` and already owns the
CSV capture, the retry-on-PermissionError reduction, the residency census, the
throttle check and the rule-7 node verification. Non-negotiable 4a: a trap
class reaching a second tool becomes shared infrastructure on the spot. A
second copy of that logic would drift, and the drift would be invisible —
both tools would report plausible milliseconds.

The FIRST draft of this file did reimplement it, including its own camera
payload, before noticing `--camera` already existed. That is step (a) failing
in miniature: the toolbox is ground truth, memory of it is a derived record.

WHAT IT MEASURES, AND WHAT IT DOES NOT
--------------------------------------
STEADY-STATE cost at fixed stations. NOT streaming transients, NOT World
Partition pop-in, NOT first-traversal shader hitches. A moving-camera variant
would measure those and is the natural extension.

GROUND IS TRACED, NEVER TAKEN FROM THE HEIGHTMAP. This project shipped a world
that rendered v2 and collided v1, disagreeing by p90 30.98 m, with every gate
green throughout.

Usage:
    python scripts/perf_flythrough.py --label baseline
    python scripts/perf_flythrough.py --dry-run     # trace only, no capture
"""
import argparse
import datetime
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap                                    # noqa: E402
import measure_frame_cost as mfc                    # noqa: E402
import verify_landscape                             # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = bootstrap.REPO_ROOT
RECIPE = os.path.join(REPO, "recipes", "perf_budgets.json")
OUTDIR = os.path.join(REPO, "_verify", "perf")

PAYLOAD_TRACE = r'''
import json as _json
import unreal as _u
_out = {"error": None, "grounds": []}
try:
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    for _x, _y in __XYS__:
        _h = _u.SystemLibrary.line_trace_single(
            _w, _u.Vector(_x, _y, 80000.0), _u.Vector(_x, _y, -20000.0),
            _u.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            _u.DrawDebugTrace.NONE, True)
        # FHitResult fields are protected in 5.8 Python; to_tuple()[4] is impact.
        _out["grounds"].append(float(_h.to_tuple()[4].z) if _h else None)
    del _w
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_FRAME__" + _json.dumps(_out))
'''


def trace_grounds(xys):
    """Ground Z under each station, or None where the trace missed."""
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            return None, "rule 7: " + str(reason)
        remote.open_command_connection(node["node_id"])
        pay = PAYLOAD_TRACE.replace("__XYS__", json.dumps(xys))
        d, _ = mfc._run(remote, remote_exec, pay)
        if not d:
            return None, "no marker from the trace payload"
        if d.get("error"):
            return None, d["error"]
        return d["grounds"], None
    finally:
        try:
            remote.stop()
        except Exception:
            pass


NUM = r"([-+]?\d+\.\d+)"
ROW = re.compile(r"^\s+(\w+)\s+(\d+)\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM
                 + r"\s+" + NUM, re.M)


def parse_frame_cost(text):
    """Pull the per-column table out of measure_frame_cost's stdout."""
    out = {}
    for m in ROW.finditer(text):
        name = m.group(1)
        if name in mfc.COLUMNS:
            out[name] = {"n": int(m.group(2)), "mean": float(m.group(3)),
                         "p50": float(m.group(4)), "p90": float(m.group(5)),
                         "max": float(m.group(6))}
    art = re.search(r"artefact\s+(\S+)", text)
    return out, (art.group(1) if art else None)


CAL = re.compile(r"camera fov\s+requested (\S+)\s+READBACK (\S+)")
VPS = re.compile(r"viewport size\s+\[(\d+), (\d+)\]")


def parse_calibration(text):
    """FOV read-back and viewport size out of the calibration block."""
    m = CAL.search(text)
    v = VPS.search(text)
    fov_rb = None
    if m:
        try:
            fov_rb = float(m.group(2))
        except ValueError:
            fov_rb = None
    return fov_rb, ([int(v.group(1)), int(v.group(2))] if v else None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--expect-components", type=int, default=1024)
    ap.add_argument("--warmup", type=float, default=20.0)
    a = ap.parse_args(argv)

    rec = json.load(io.open(RECIPE, encoding="utf-8"))
    sp = rec["spline"]
    stations = sp["stations"]
    eye = float(sp["eye_height_cm"])

    # ⛔ THE FOV MUST BE DECLARED. Until 2026-09-05 nothing in this path set or
    # recorded one, so every figure on the board was taken at whatever the
    # viewport happened to be -- and FOV decides how much geometry is in
    # frame. A ratified budget whose FOV is unknown cannot be checked, only
    # believed. Refuse rather than inherit an accident.
    if "fov_horizontal_deg" not in sp:
        print("REFUSING: recipes/perf_budgets.json spline declares no "
              "fov_horizontal_deg. A cost figure without a recorded FOV is "
              "not a reproducible measurement.")
        return 5
    fov = float(sp["fov_horizontal_deg"])
    # Worded for BOTH paths: this banner prints before the --dry-run return
    # (:188), and dry-run invokes no measure_frame_cost, so it neither sets nor
    # reads back FOV. "at each CAPTURED station" is vacuously true on dry-run
    # (zero captured) and exact on the capture path.
    print("  FOV %.1f deg, SET on the viewport and read back at each captured "
          "station." % fov)
    print()

    print("perf_flythrough — %d stations, %d frames each, label %r"
          % (len(stations), a.frames, a.label))
    print("  MEASUREMENT CLASS: editor viewport. FrameTime is clamped by")
    print("  UEditorEngine::GetMaxTickRate and is NOT a cost signal;")
    print("  GPUTime / RenderThreadTime / GameThreadTime are.")
    print()

    xys = [[float(s["xy_cm"][0]), float(s["xy_cm"][1])] for s in stations]
    grounds, err = trace_grounds(xys)
    if grounds is None:
        print("REFUSING: %s" % err)
        return 3
    for st, g in zip(stations, grounds):
        if g is None:
            print("REFUSING: no ground under station %r. A guessed Z is not a "
                  "station." % st["zone"])
            return 4
        print("  %-12s ground %9.1f cm  ->  eye %9.1f"
              % (st["zone"], g, g + eye))

    if a.dry_run:
        print()
        print("DRY RUN — grounds traced, nothing captured.")
        return 0

    rows = []
    for i, (st, g) in enumerate(zip(stations, grounds)):
        zone = st["zone"]
        z = g + eye
        cam = "%.1f,%.1f,%.1f,%.1f,%.1f,0.0" % (
            st["xy_cm"][0], st["xy_cm"][1], z,
            float(st["pitch_deg"]), float(st["yaw_deg"]))
        # `--camera=VALUE`, NOT `--camera VALUE`. Station x is negative here and
        # argparse reads a leading '-' as an option, refusing with exit 2. This
        # project already recorded the rule -- "use --flag=value so argparse
        # does not eat a negative coordinate" -- on 2026-08-17, and the first
        # run of this tool walked straight into it anyway.
        cmd = [sys.executable, os.path.join(REPO, "scripts", "measure_frame_cost.py"),
               "--camera=" + cam, "--frames", str(a.frames),
               "--tag", "%s_%s" % (a.label, zone),
               "--expect-components", str(a.expect_components),
               "--fov", repr(fov),
               "--warmup", str(a.warmup if i == 0 else 5.0)]
        if i == 0:
            cmd.append("--load-all-regions")
        print()
        print("--- %s ---" % zone)
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
        sys.stdout.write(p.stdout[-1800:])
        if p.returncode != 0:
            # PRINT STDERR. The first version captured it and never showed it,
            # so four stations reported "exit 2" with the reason -- an argparse
            # usage error -- invisible. A wrapper that hides its child's error
            # message turns a one-line fix into a diagnosis.
            if p.stderr:
                sys.stdout.write("  stderr: " + p.stderr.strip()[-600:] + "\n")
            print("  measure_frame_cost exited %d for zone %r — NO VERDICT for "
                  "this station rather than a number of unknown class."
                  % (p.returncode, zone))
            rows.append({"zone": zone, "ground_cm": g, "eye_z_cm": z,
                         "error": "measure_frame_cost exit %d" % p.returncode})
            continue
        stats, art = parse_frame_cost(p.stdout)
        fov_rb, vps = parse_calibration(p.stdout)
        # THE READ-BACK IS A GATE. A requested FOV that did not take produces a
        # capture of unknown class, and recording it would put an
        # unreproducible number back on the board -- the very defect being
        # fixed here.
        if fov_rb is None or abs(fov_rb - fov) > 0.05:
            print("  FOV READ-BACK FAILED for %r: requested %.1f, got %s. "
                  "NO VERDICT for this station." % (zone, fov, fov_rb))
            rows.append({"zone": zone, "ground_cm": g, "eye_z_cm": z,
                         "error": "fov readback %s != %s" % (fov_rb, fov)})
            continue
        rows.append({"zone": zone, "ground_cm": g, "eye_z_cm": z,
                     "camera": cam, "fov_horizontal_deg": fov_rb,
                     "viewport_size": vps,
                     "stats_ms": stats, "artefact": art})

    os.makedirs(OUTDIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    out = os.path.join(OUTDIR, "%s_%s.json" % (stamp, a.label))
    io.open(out, "w", encoding="utf-8").write(json.dumps({
        "_what": "per-zone frame cost along the fixed spline in recipes/perf_budgets.json",
        "_measurement_class": ("EDITOR VIEWPORT, not PIE, not cooked. FrameTime is "
                               "clamped by UEditorEngine::GetMaxTickRate and is NOT "
                               "a cost signal. GPUTime / RenderThreadTime / "
                               "GameThreadTime are the valid instruments."),
        "_limit": ("STEADY-STATE at fixed stations. Does NOT measure streaming "
                   "transients, World Partition pop-in, or first-traversal "
                   "shader hitches."),
        "label": a.label,
        "frames_per_station": a.frames,
        "level_path": rec.get("level_path"),
        "expect_components": a.expect_components,
        "recorded": datetime.datetime.now().isoformat(timespec="seconds"),
        "stations": rows,
    }, indent=2) + "\n")
    print()
    print("artefact  %s" % os.path.relpath(out, REPO))
    bad = [r["zone"] for r in rows if "error" in r]
    if bad:
        print("STATIONS WITHOUT A VERDICT: %s" % ", ".join(bad))
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
