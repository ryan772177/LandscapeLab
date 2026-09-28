"""solo_shots.py -- one groom, alone, on the ground, one HighResShot each.

    python solo_shots.py --out-dir <ABS>

The verdict instrument is now: standalone spawn + level-viewport HighResShot
close-up + owner eye. The SceneCapture gate is not trusted for standalone arms
until it passes its own engulfment self-check, and on 2026-08-22 it did not --
it returned ABSENT for the vendor groom, which the owner then saw rendering.

PRE-REGISTERED, written before any of these frames existed:

    11_k12       widths all zero in the file  ->  PREDICT BALD
    12_rootuv    widths all zero in the file  ->  PREDICT BALD
    13_full      widths 0.018, root UVs real  ->  PREDICT DRAWS
    14_clay      the control that the owner saw render  ->  PREDICT DRAWS

11 and 12 are expected to fail. They are shot anyway because they retire the
last two gate-only verdicts on the new instrument, and because a prediction
that is only ever made about the arm you expect to win is not a prediction.
"""

import argparse
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LIK = os.path.join(REPO, "scripts", "hero_face", "likeness")
UE_EXEC = os.path.join(REPO, "scripts", "ue_exec.py")

GROUND_Z = 31019.47
# 2 m clear of PlayerStart_LandscapeLab (the blue capsule) and HeroInWorld,
# both of which were within 3 m of the previous stage.
LOC = [354430.0, -321600.0, GROUND_Z]

ARMS = [
    ("11_k12", "/Game/Characters/AlpineHero/Grooms/AlpineHero_DiffLocks_k12",
     "BALD -- widths all zero in the file"),
    ("12_rootuv", "/Game/Characters/AlpineHero/Grooms/AlpineHero_DL_uv2",
     "BALD -- root UVs fixed, widths still all zero"),
    ("13_full", "/Game/Characters/AlpineHero/Grooms/AlpineHero_DL_full",
     "DRAWS -- widths 0.018 and real root UVs"),
    ("14_clay", "/Game/Characters/AlpineHero/Grooms/AlpineHero_Clay_R4",
     "DRAWS -- the control the owner saw render"),
]


def ue(payload, sets, want):
    args = [sys.executable, UE_EXEC, os.path.join(LIK, payload),
            "--timeout", "25"]
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
        if isinstance(obj, dict) and want in obj:
            return obj
    raise SystemExit("REFUSE: no payload JSON.\n" + txt[-1500:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    if not os.path.isabs(a.out_dir):
        raise SystemExit("REFUSE: --out-dir must be ABSOLUTE.")
    os.makedirs(a.out_dir, exist_ok=True)

    rows = []
    for name, path, prediction in ARMS:
        st = ue("stage_one_groom.txt",
                [("GROOM_PATH", path), ("LABEL", name),
                 ("LOC", json.dumps(LOC)), ("CAM_BACK", "90"),
                 ("CAM_UP", "10")], "bounds_origin")
        if st.get("error"):
            raise SystemExit("stage failed for %s: %s" % (name, st["error"]))

        pre = ue("console_and_camera.txt",
                 [("CAM_LOC", "None"), ("CAM_ROT", "None"), ("CMDS", "[]"),
                  ("SHOT", "0"), ("SETTLE", "0")], "shot_dir")
        shot_dir, before = pre["shot_dir"], pre.get("before_files", [])

        ue("console_and_camera.txt",
           [("CAM_LOC", "None"), ("CAM_ROT", "None"), ("CMDS", "[]"),
            ("SHOT", "1"), ("SETTLE", "5")], "shot_dir")

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

        row = {"name": name, "groom": path, "prediction": prediction,
               "assignment_matches": st.get("assignment_matches"),
               "binding": st.get("binding"), "scale3d": st.get("scale3d"),
               "bounds_origin": st.get("bounds_origin"),
               "bounds_size_cm": st.get("bounds_size_cm"),
               "camera": st.get("camera"), "original_file": got}
        if got:
            dst = os.path.join(a.out_dir, name + ".png")
            os.replace(os.path.join(shot_dir, got), dst)
            row["file"] = dst
        else:
            row["file"] = None
            row["note"] = "NO SCREENSHOT -- could not look"
        rows.append(row)
        print("  %-10s %-58s -> %s"
              % (name, prediction, row["file"] or row["note"]))

    with open(os.path.join(a.out_dir, "solo_manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    print("manifest:", os.path.join(a.out_dir, "solo_manifest.json"))


if __name__ == "__main__":
    main()
