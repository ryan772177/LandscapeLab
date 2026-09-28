"""iterate.py -- one command per iteration: edit, export, gate, render.

    python iterate.py <NNN> <params.json> [samples] [views]

Plain CPython; it shells Blender four times because each stage must run in its
own process. The integrity gate especially: verifying an export inside the
session that wrote it re-reads objects still in memory, and this project has a
standing rule against a check that shares a source with the thing it checks.

Every stage's timeout is 10 minutes per the mission's hard rule. A hang is
killed and logged as a failure rather than waited on.

Nothing is ever overwritten -- outputs are keyed by the iteration number and
the script refuses if that number's blend already exists.
"""

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = ROOT.replace("\\", "/")
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
SCR = os.path.join(ROOT, "scripts")
TIMEOUT = 600


def run(script, args, tag):
    cmd = [BLENDER, "--background", "--python", os.path.join(SCR, script),
           "--"] + args
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT)
        out = p.stdout
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": tag, "error": "TIMEOUT after %ds" % TIMEOUT,
                "secs": round(time.time() - t0, 1)}
    marker = {"edit_engine.py": "__EDIT__", "export_abc.py": "__EXPORT__",
              "verify_abc.py": "__VERIFY__", "render_harness.py": "__RENDER__",
              "measure.py": "__MEASURE__"}[script]
    payload = None
    for line in out.splitlines():
        if marker in line:
            try:
                payload = json.loads(line.split(marker, 1)[1])
            except Exception:
                pass
    if payload is None:
        tailtxt = "\n".join((p.stdout + p.stderr).splitlines()[-12:])
        return {"ok": False, "stage": tag, "error": "no %s in output" % marker,
                "tail": tailtxt, "secs": round(time.time() - t0, 1)}
    payload["stage"] = tag
    payload["secs"] = round(time.time() - t0, 1)
    return payload


def main():
    num = sys.argv[1].zfill(3)
    params = sys.argv[2]
    samples = sys.argv[3] if len(sys.argv) > 3 else "36"
    views = sys.argv[4] if len(sys.argv) > 4 else "front,left,threequarter"

    blend = "%s/blends/iter_%s.blend" % (W, num)
    abc = "%s/exports/iter_%s.abc" % (W, num)
    if os.path.isfile(blend):
        print(json.dumps({"ok": False,
                          "error": "iter_%s already exists; no overwrites" % num}))
        sys.exit(2)

    rec = {"iter": num, "params_file": params, "stages": {}}
    src = "%s/source/SC_Hairstyle_Male_11.abc" % W

    r = run("edit_engine.py", [src, params, blend, abc,
                               "%s/logs/iter_%s.json" % (W, num)], "edit")
    rec["stages"]["edit"] = r
    if not r.get("ok"):
        _finish(rec, num)
        return

    r = run("export_abc.py", [blend, abc, "cull"], "export")
    rec["stages"]["export"] = r
    if not r.get("ok"):
        _finish(rec, num)
        return

    # Expectation for the gate is what the EXPORT said it wrote, so the gate
    # asks "did the file survive a round trip", not "did the edit do what I
    # wanted" -- those are different questions and only one is an integrity
    # check.
    exp = {"curves": r["pre_export"]["curves"],
           "attributes": r["pre_export"]["attributes"]}
    exp_path = "%s/logs/expect_%s.json" % (W, num)
    json.dump(exp, open(exp_path, "w", encoding="utf-8"), indent=2)

    r = run("verify_abc.py", [abc, exp_path, "%s/logs/verify_%s.json" % (W, num)],
            "verify")
    rec["stages"]["verify"] = r

    r = run("measure.py", [blend, "%s/logs/measure_%s.json" % (W, num)],
            "measure")
    rec["stages"]["measure"] = r

    r = run("render_harness.py", [blend, "%s/renders" % W, "iter%s" % num,
                                  views, samples], "render")
    rec["stages"]["render"] = r
    _finish(rec, num)


def _finish(rec, num):
    path = os.path.join(ROOT, "logs", "run_%s.json" % num)
    json.dump(rec, open(path, "w", encoding="utf-8"), indent=2)
    summary = {"iter": num,
               "edit": rec["stages"].get("edit", {}).get("ok"),
               "export": rec["stages"].get("export", {}).get("ok"),
               "verify": rec["stages"].get("verify", {}).get("ok"),
               "render": rec["stages"].get("render", {}).get("ok"),
               "secs": sum(s.get("secs", 0) for s in rec["stages"].values())}
    ed = rec["stages"].get("edit", {})
    if ed.get("stats"):
        summary["moved_mean_cm"] = ed["stats"].get("moved_mean_cm")
        summary["moved_max_cm"] = ed["stats"].get("moved_max_cm")
    ex = rec["stages"].get("export", {})
    if ex.get("cull"):
        summary["kept"] = ex["cull"].get("kept")
        summary["dropped"] = (ex["cull"].get("dropped_under_2pts", 0)
                              + ex["cull"].get("dropped_stray_long", 0))
    m = rec["stages"].get("measure", {})
    for k in ("fringe_reach_cm", "forehead_cover_pct", "crown_rise_cm",
              "silhouette_w_cm", "ear_cover_pct", "grade_ratio",
              "tip_scatter_cm", "scalp_exposed_pct"):
        if k in m:
            summary[k] = m[k]
    for k in ("edit", "export", "verify", "measure", "render"):
        s = rec["stages"].get(k, {})
        if s and not s.get("ok"):
            summary["error"] = "%s: %s" % (k, s.get("error") or s.get("failures"))
            if s.get("tail"):
                summary["tail"] = s["tail"]
            break
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
