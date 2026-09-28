"""hero_closeups.py -- viewport HighResShot pair of the hero, for the owner's eyes.

    python hero_closeups.py --out-dir <ABS> --name <prefix>

The gate is calibrated, not validated (solo_gate.py says so in its own bar
comment), so a gate number is not on its own a deliverable. These are the frames
a person looks at. Level viewport, `HighResShot 2`, two poses so a single
unlucky angle cannot carry the claim.
"""

import argparse
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LIK = os.path.join(REPO, "scripts", "hero_face", "likeness")

HEAD = [354600.0, -321400.0, 31019.47 + 168.0]
POSES = [
    ("front", [HEAD[0] - 75.0, HEAD[1], HEAD[2] + 4.0], [0.0, -2.0, 0.0]),
    ("threequarter", [HEAD[0] - 62.0, HEAD[1] - 45.0, HEAD[2] + 8.0],
     [0.0, -5.0, 36.0]),
    # Rear. The hero is placed facing -X, so the back of the head is at +X and
    # the camera has to look back along -X (yaw 180). Stated rather than
    # eyeballed because R-HAIRREAR records the rear rubric measuring a FOREST
    # twice and exiting 0 both times.
    ("rear", [HEAD[0] + 78.0, HEAD[1], HEAD[2] + 6.0], [0.0, -4.0, 180.0]),
]


def ue(sets):
    args = [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
            os.path.join(LIK, "console_and_camera.txt"), "--timeout", "25"]
    for k, v in sets:
        args += ["--set", "%s=%s" % (k, v)]
    p = subprocess.run(args, capture_output=True, text=True, cwd=REPO)
    txt = p.stdout + p.stderr
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
    raise SystemExit("REFUSE: no payload JSON.\n" + txt[-1200:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", required=True)
    a = ap.parse_args()
    if not os.path.isabs(a.out_dir):
        raise SystemExit("REFUSE: --out-dir must be ABSOLUTE.")
    os.makedirs(a.out_dir, exist_ok=True)

    for tag, loc, rot in POSES:
        pre = ue([("CAM_LOC", json.dumps(loc)), ("CAM_ROT", json.dumps(rot)),
                  ("CMDS", "[]"), ("SHOT", "0"), ("SETTLE", "0")])
        shot_dir, before = pre["shot_dir"], pre.get("before_files", [])
        ue([("CAM_LOC", "None"), ("CAM_ROT", "None"), ("CMDS", "[]"),
            ("SHOT", "1"), ("SETTLE", "6")])
        got, t0 = None, time.time()
        while time.time() - t0 < 90:
            new = sorted(set(os.listdir(shot_dir)) - set(before))
            if new:
                f = os.path.join(shot_dir, new[-1])
                s = os.path.getsize(f)
                time.sleep(0.6)
                if os.path.getsize(f) == s and s > 0:
                    got = new[-1]
                    break
            time.sleep(0.4)
        if got:
            dst = os.path.join(a.out_dir, "%s_%s.png" % (a.name, tag))
            os.replace(os.path.join(shot_dir, got), dst)
            print("  %-14s -> %s" % (tag, dst))
        else:
            print("  %-14s -> NO SCREENSHOT (could not look)" % tag)


if __name__ == "__main__":
    main()
