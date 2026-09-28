"""shoot_sequence.py -- drive the eyeball evidence set, one labelled shot at a time.

    python scripts/hero_face/likeness/shoot_sequence.py --out-dir <ABS>

Every frame goes through `HighResShot 2` on the LEVEL VIEWPORT, deliberately NOT
through the SceneCapture path every gate in this project uses. The whole point
of the exercise is that the two paths might disagree, so they must not share
code.

RENAME IMMEDIATELY. Unreal names screenshots by an incrementing counter and the
folder already holds older runs; a set of ten frames identified by mtime is one
mis-sorted listing away from a wrong conclusion about which head is which. Each
shot is polled for, renamed to its manifest name, and its ORIGINAL name recorded
so the rename is auditable.

NO PIXEL ANALYSIS HAPPENS HERE. The human is the instrument for this test; this
script's job is to make the labels trustworthy.

ABSOLUTE --out-dir IS MANDATORY. A relative path resolves against the editor's
working directory, which is the ENGINE BINARIES folder, and this project has put
ten frames into Program Files that way.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PAYLOAD = os.path.join(REPO, "scripts", "hero_face", "likeness",
                       "console_and_camera.txt")
UE_EXEC = os.path.join(REPO, "scripts", "ue_exec.py")

# staged geometry, mirrored from stage_three_grooms.txt. Duplicated constants
# are how two lists drift (non-negotiable 24), so the caller asserts these
# against the stage report rather than trusting them.
BASE_X, BASE_Y, HEAD_Z = 354430.0, -321400.0, 31184.47
SPACING = 40.0

GROUP_LOC = [BASE_X - 120.0, BASE_Y, HEAD_Z + 25.0]
GROUP_ROT = [0.0, -8.0, 0.0]


def orbit(deg, dist=120.0):
    import math
    a = math.radians(deg)
    return ([BASE_X - dist * math.cos(a), BASE_Y - dist * math.sin(a),
             HEAD_Z + 25.0],
            [0.0, -8.0, math.degrees(a)])


def close_on(i, dist=55.0):
    y = BASE_Y + (i - 1) * SPACING
    return ([BASE_X - dist, y, HEAD_Z + 6.0], [0.0, -4.0, 0.0])


def pylit(v):
    """Python source, not JSON. `--set` is a literal text substitution into a
    Python file, so `json.dumps(None)` writes `null` and the payload dies on
    NameError. Lists of numbers and strings happen to be valid in both; None is
    the one that is not, which is exactly the kind of near-miss that reads as
    working."""
    return "None" if v is None else json.dumps(v)


def run(cam_loc, cam_rot, cmds, shot, settle):
    args = [sys.executable, UE_EXEC, PAYLOAD, "--timeout", "25",
            "--set", "CAM_LOC=" + pylit(cam_loc),
            "--set", "CAM_ROT=" + pylit(cam_rot),
            "--set", "CMDS=" + pylit(cmds),
            "--set", "SHOT=%d" % (1 if shot else 0),
            "--set", "SETTLE=%g" % settle]
    p = subprocess.run(args, capture_output=True, text=True, cwd=REPO)
    txt = p.stdout + p.stderr
    # ue_exec.py CONSUMES the __LL__ marker and pretty-prints the payload's
    # JSON, so scanning for the marker finds nothing and the raw text is not
    # one line. Decode the first complete JSON object in the stream instead.
    dec = json.JSONDecoder()
    for i, ch in enumerate(txt):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(txt[i:])
        except ValueError:
            continue
        if isinstance(obj, dict) and "shot_dir" in obj:
            return obj
    raise SystemExit("REFUSE: no payload JSON in output.\n" + txt[-2000:])


def wait_for_new(shot_dir, before, timeout=90.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        now = set(os.listdir(shot_dir)) if os.path.isdir(shot_dir) else set()
        new = sorted(now - set(before))
        # a PNG still being written has a growing size; require it to settle
        if new:
            f = os.path.join(shot_dir, new[-1])
            s1 = os.path.getsize(f)
            time.sleep(0.6)
            if os.path.getsize(f) == s1 and s1 > 0:
                return new[-1]
        time.sleep(0.4)
    return None


SEQUENCE = [
    # name,                  cam,                cmds,                      settle
    ("01_group_T2s",         (GROUP_LOC, GROUP_ROT), [],                     2.0),
    ("02_group_T20s",        (None, None),           [],                     20.0),
    ("03_group_orbit",       orbit(30.0),            [],                     3.0),
    ("04_close_difflocks",   close_on(0),            [],                     3.0),
    ("05_close_clay",        close_on(1),            [],                     3.0),
    ("06_close_vendor",      close_on(2),            [],                     3.0),
    ("07_debug34_group",     (GROUP_LOC, GROUP_ROT),
     ["r.HairStrands.ViewMode 34", "r.HairStrands.ViewMode"],                3.0),
    ("08_debug41_group",     (None, None),
     ["r.HairStrands.ViewMode 41", "r.HairStrands.ViewMode"],                3.0),
    ("09_debug31_group",     (None, None),
     ["r.HairStrands.ViewMode 31", "r.HairStrands.ViewMode"],                3.0),
    ("10_debug0_group",      (None, None),
     ["r.HairStrands.ViewMode 0", "r.HairStrands.ViewMode",
      "r.HairStrands.DebugMode"],                                           3.0),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    if not os.path.isabs(a.out_dir):
        raise SystemExit("REFUSE: --out-dir must be ABSOLUTE.")
    os.makedirs(a.out_dir, exist_ok=True)

    manifest = []
    for name, cam, cmds, settle in SEQUENCE:
        loc, rot = cam
        pre = run(loc, rot, cmds, False, 0.0)
        shot_dir = pre["shot_dir"]
        before = pre.get("before_files", [])
        rep = run(None, None, cmds, True, settle)
        got = wait_for_new(shot_dir, before)
        row = {"name": name, "settle_s": settle, "commands": cmds,
               "camera": rep.get("camera"), "original_file": got,
               "log_lines": rep.get("log_lines", [])}
        if got is None:
            row["file"] = None
            row["note"] = "NO NEW SCREENSHOT APPEARED -- could not look"
        else:
            dst = os.path.join(a.out_dir, name + ".png")
            os.replace(os.path.join(shot_dir, got), dst)
            row["file"] = dst
            row["bytes"] = os.path.getsize(dst)
        row["utc"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ")
        manifest.append(row)
        print("  %-22s -> %s" % (name, row.get("file") or row["note"]))

    out = os.path.join(a.out_dir, "manifest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"shots": manifest, "shot_dir": shot_dir}, f, indent=2)
    print("manifest:", out)
    print("screenshots folder:", shot_dir)


if __name__ == "__main__":
    main()
