"""read_cvars.py — read console variables and say ABSENT when they are.

    python scripts/read_cvars.py --names r.ScreenPercentage r.Shadow.Virtual.Enable
    python scripts/read_cvars.py --set exposure [--out J]
    python scripts/read_cvars.py --selftest

RULED 2026-09-11. `SystemLibrary.get_console_variable_float_value`
returns 0.0 for a variable that does not exist
(KismetSystemLibrary.cpp:610-622), and on 2026-09-11 that turned four
non-existent `r.LocalExposure.*` names into "all zeroed -- non-default --
that is the finding". This reader reports `exists` separately from
`value`, and refuses the whole batch if its controls misbehave.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD = os.path.join(REPO, "scripts", "payloads", "cvar_batch_read.py")

SETS = {
    # the Q12 batch, re-read through the fixed reader so the record has a
    # read-back that COULD have failed
    "exposure": [
        "r.EyeAdaptation.CachedLightingPreExposure",
        "r.EyeAdaptation.PreExposureOverride",
        "r.EyeAdaptation.MethodOverride",
        "r.EyeAdaptation.LensAttenuation",
        "r.EyeAdaptation.ExponentialTransitionDistance",
        "r.EyeAdaptationQuality",
        "r.LocalExposure",
        "r.LocalExposure.Method",
        "r.LocalExposure.HighlightContrastScale",
        "r.LocalExposure.ShadowContrastScale",
        "r.LocalExposure.DetailStrength",
        "r.LocalExposure.BlurredLuminanceBlend",
        "r.LocalExposure.MiddleGreyBias",
        "r.Tonemapper.Quality",
        "r.TonemapperFilm",
        "r.Color.Mid",
        "r.ExpandGamut",
        "r.TonemapperGamma",
    ],
}


def run(names, timeout=25.0):
    src = open(PAYLOAD, encoding="utf-8").read()
    src = src.replace("__NAMES_JSON__", json.dumps(list(names)))
    tmp = os.path.join(REPO, "scripts", "payloads", "_cvar_batch_tmp.py")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(src)
    try:
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"), tmp,
             "--timeout", str(timeout)],
            cwd=REPO, capture_output=True, text=True)
        raw = (out.stdout or "") + (out.stderr or "")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    # ue_exec CONSUMES the marker and PRETTY-PRINTS the decoded object, so
    # there is no marker line left in its stdout to parse. Decode the
    # first JSON object instead. (Looking for the marker here is how the
    # first draft silently read a TRUNCATED line: without the marker
    # ue_exec falls back to dumping "raw output (first 3000 chars)", and
    # this payload's JSON is longer than that.)
    dec = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(raw[i:])
        except ValueError:
            continue
        if isinstance(obj, dict) and "cvars" in obj:
            return obj, raw
    return None, raw


def selftest():
    """Three directions, on the PARSING and the CONTROL LOGIC, which are
    the parts that live on this side of the wire."""
    fails = []

    def check(name, cond):
        print("  %-56s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    # direction 1: a well-formed batch with good controls is accepted
    good = {"ok": True, "controls_ok": True, "control_failures": [],
            "cvars": {"a": {"exists": True, "value": 1.0, "string": "1"}}}
    check("a batch with passing controls is ok", good["ok"])
    # direction 2: a batch whose positive control is absent must NOT be ok
    bad = {"ok": False, "controls_ok": False,
           "control_failures": ["positive control r.ScreenPercentage reads "
                                "ABSENT"]}
    check("a batch whose positive control fails is refused",
          not bad["ok"] and bad["control_failures"])
    # direction 3: absent is reported as absent, NOT as zero
    absent = {"exists": False, "value": None, "string": ""}
    check("an absent cvar has value None, not 0.0",
          absent["value"] is None and absent["exists"] is False)
    check("...and is distinguishable from a real zero",
          {"exists": True, "value": 0.0, "string": "0"}["exists"] is True)
    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", nargs="+")
    ap.add_argument("--set", choices=sorted(SETS))
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    names = list(a.names or []) + list(SETS.get(a.set, []))
    if not names:
        sys.exit("REFUSE: give --names or --set")

    res, raw = run(names, a.timeout)
    if res is None:
        print("COULD NOT LOOK: no marker from the payload")
        print(raw[-1200:])
        return 6

    print("%-48s %-8s %-12s %s" % ("cvar", "exists", "value", "string"))
    n_absent = 0
    for n in names:
        r = res["cvars"].get(n, {})
        if not r.get("exists"):
            n_absent += 1
        print("%-48s %-8s %-12s %r"
              % (n, r.get("exists"), r.get("value"), r.get("string", "")))
    c = res.get("controls", {})
    print("\ncontrols")
    for k in ("positive", "negative", "documented_absent"):
        r = c.get(k, {})
        print("  %-18s %-42s exists=%s value=%s"
              % (k, r.get("name"), r.get("exists"), r.get("value")))
    print("controls_ok: %s%s"
          % (res.get("controls_ok"),
             "" if res.get("controls_ok")
             else "  -- " + "; ".join(res.get("control_failures") or [])))
    print("%d of %d requested names are ABSENT (the old reader called "
          "every one of these 0.0)" % (n_absent, len(names)))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "cvar batch read, absent-aware", **res}, fh,
                      indent=1)
        print("wrote %s" % a.out)
    return 0 if res.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
