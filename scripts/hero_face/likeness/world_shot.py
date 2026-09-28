"""world_shot.py — take ONE picture through the rig place_hero_in_world built.

Deliberately dumb. It moves nothing, derives nothing and decides nothing: the
transform is whatever the rig already holds, so a picture cannot silently be
taken from somewhere other than where the presence gate was run. Camera
movement is indistinguishable from subject movement in a render, and a gate
verdict belongs to the framing it was measured at.

It records where the MAIN VIEW was pointing and the engine's frame counter on
every shot. Those two were the variables in the 2026-08-19 groom
investigation, and a capture that cannot say where the main view was is a
capture that cannot be re-argued later.

WHAT IT WILL NOT DO
    It will not call anything a deliverable. That word belongs to
    groom_presence.py, which is the only thing here that looks at pixels and
    asks whether what should be in the frame is in the frame.

Exit codes:
    0  a frame was written
    3  no editor matched UE_PROJECT_ROOT (standing rule 7)
    5  payload error, or the frame never landed on disk
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts import ue_exec                      # noqa: E402

PAYLOAD = os.path.join(_HERE, "world_shot_payload.txt")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--warm", type=int, default=45)
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    name = "%s_%s" % (args.name, stamp)

    with open(PAYLOAD, "r", encoding="utf-8") as fh:
        text = fh.read()
    for k, v in (("OUT_DIR", args.out_dir.replace("\\", "/")),
                 ("NAME", name), ("WARM", str(args.warm))):
        text = text.replace("__" + k + "__", v)

    rc, d, _raw = ue_exec.run(text, timeout=args.timeout,
                              stage_name="world_shot")
    if rc == 3:
        return 3
    if d is None or d.get("error"):
        print("PAYLOAD ERROR:", None if d is None else d.get("error"))
        return 5

    png = os.path.join(args.out_dir, d.get("png") or "")
    if not os.path.isfile(png):
        print("COULD NOT LOOK: the payload reported a frame that is not on "
              "disk:", png)
        return 5

    print("frame        :", png)
    print("capture      :", json.dumps(d.get("capture_at_shot")))
    print("main view at :", json.dumps(d.get("viewport_at_capture")))
    print("frame counter:", d.get("frame_count"))
    for r in d.get("refusals", []):
        print("REFUSAL:", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
