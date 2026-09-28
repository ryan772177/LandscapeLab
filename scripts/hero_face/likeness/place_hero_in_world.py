"""place_hero_in_world.py — put the assembled hero on the ground in the open
world and build the capture rig that photographs him.

WHAT IT DOES, AND WHAT IT DELIBERATELY DOES NOT
-----------------------------------------------
Spawns the assembled Blueprint at a recipe-declared spot, clamps it to the
COLLIDABLE surface by line trace, turns it to face the camera, and parks a
SceneCapture2D at a framing given in centimetres. It saves NOTHING. The
placement is a spawned actor in an unsaved level and the RENDER is the
artefact; re-placing costs one run of this tool.

THE FRAMING IS AN ARGUMENT, AND THAT IS LOAD-BEARING
----------------------------------------------------
A groom's verdict belongs to its framing. Measured 2026-08-19 on one build in
one session: at 2.1 m the stubble grooms move 1.8-3.1x the repeat floor and
the presence gate calls them ABSENT; at 0.9 m the same grooms on the same
character move 3.6-17x and it calls them PRESENT. Nothing about the assets
changed. So `--dist` is recorded in every report and a gate verdict may not be
carried from one framing to another.

FACING IS DERIVED, NOT ASSUMED
------------------------------
The MetaHuman Blueprint's forward axis is not +X: a look-at yaw pointed
straight down the camera axis photographs his PROFILE. The correction is
applied as a named offset rather than folded into the look-at, so the claim is
visible to the next reader instead of hiding inside a number.

ORDER OF OPERATIONS FOR A DELIVERABLE
-------------------------------------
    1  place_hero_in_world.py          spawn + rig
    2  groom_presence.py               PIXEL gate at this framing
    3  only if the gate passes, shoot the deliverable

Step 2 is not optional and its absence is how a bald portrait shipped as
DELIVERABLE on 2026-08-19: the gate it had asserted component properties,
which a groom can satisfy while drawing nothing.

Exit codes:
    0  placed, rig built, ground clamped, and the payload reported no refusals.
       (This tool PRINTS the returned capture/yaw/viewport for the operator's
       eye; the agreement checks that gate the run live in the payload's
       `refusals` list, and the groom VERDICT is deferred to groom_presence.py.)
    2  bad arguments
    3  no editor matched UE_PROJECT_ROOT (standing rule 7)
    5  payload error, a read-back disagreed, the ground clamp returned no finite
       z, or the payload produced no decodable result (could not look)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts import ue_exec                      # noqa: E402

PAYLOAD = os.path.join(_HERE, "place_hero_in_world_payload.txt")

# Measured on the assembled build: head sits 160.6 cm above the actor root.
# Named here rather than repeated at three call sites.
HEAD_ABOVE_ROOT_CM = 160.6


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bp",
                    default="/Game/Hero/Unpacked/MHC_AlpineHero/BP_MHC_AlpineHero")
    ap.add_argument("--x", type=float, default=354600.0)
    ap.add_argument("--y", type=float, default=-321400.0)
    ap.add_argument("--res", type=int, default=2048)
    ap.add_argument("--dist", type=float, default=90.0,
                    help="camera distance in cm. THE VERDICT BELONGS TO THIS "
                         "NUMBER -- see the module docstring.")
    ap.add_argument("--fov", type=float, default=24.0)
    ap.add_argument("--cam-up", type=float, default=155.0,
                    help="camera height above ground, cm")
    ap.add_argument("--look-up", type=float, default=155.0,
                    help="look-at height above ground, cm")
    ap.add_argument("--yaw-offset", type=float, default=-90.0,
                    help="the Blueprint's forward-axis correction, MEASURED")
    ap.add_argument("--main-view", choices=("on", "off"), default="on",
                    help="where to point the editor viewport. Kept as a knob "
                         "because it was a live hypothesis for why grooms did "
                         "not draw; measured 2026-08-19 to make no difference "
                         "in a warm session, and left here so the control can "
                         "be repeated rather than remembered.")
    ap.add_argument("--respawn", choices=("yes", "no"), default="yes")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)

    with open(PAYLOAD, "r", encoding="utf-8") as fh:
        text = fh.read()
    subs = {"BP": args.bp, "X": repr(args.x), "Y": repr(args.y),
            "RES": str(args.res), "DIST": repr(args.dist),
            "FOV": repr(args.fov), "CAM_UP": repr(args.cam_up),
            "LOOK_UP": repr(args.look_up),
            "YAW_OFFSET": repr(args.yaw_offset),
            "MAIN_VIEW": args.main_view, "RESPAWN": args.respawn}
    for k, v in subs.items():
        text = text.replace("__" + k + "__", v)

    rc, d, _raw = ue_exec.run(text, timeout=args.timeout,
                              stage_name="place_hero_in_world")
    if rc == 3:
        return 3
    if d is None:
        # ue_exec returns d is None for THREE reasons (no marker, undecodable
        # JSON, non-object JSON); ue_exec already printed the specific cause, so
        # do not assert one here.
        print("COULD NOT LOOK: the payload returned no decodable result "
              "(see the reason above).")
        return 5
    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 5

    # Clamping the hero to the collidable surface is THIS tool's job (docstring),
    # so a missing/non-finite ground z is a placement failure, not a nan to
    # print past.
    gz = d.get("ground_z_cm")
    if gz is None or not math.isfinite(gz):
        print("CLAMP FAILED: the payload returned no finite ground_z_cm; the "
              "hero is not clamped to the surface (got %r)." % gz)
        return 5
    print("ground z (trace) : %.2f cm" % gz)
    print("spawned fresh    :", d.get("spawned"))
    print("hero yaw         :", d.get("hero_yaw"))
    print("capture          :", json.dumps(d.get("capture")))
    print("viewport         :", json.dumps(d.get("viewport")))
    groom_rows = [(name, g) for name, g
                  in sorted((d.get("groom_components") or {}).items())
                  if g.get("groom")]
    print("grooms on actor  : %d with a groom asset" % len(groom_rows))
    for name, g in groom_rows:
        print("    %-10s %-22s binding %s" % (name, g["groom"],
                                              g.get("binding")))
    if not groom_rows:
        # Not a refusal here -- placement runs BEFORE binding and the groom
        # VERDICT is groom_presence.py's (docstring) -- but it must not be
        # silent: a bald actor is exactly the 2026-08-19 failure.
        print("    WARNING: 0 groom components carry a groom asset. groom_"
              "presence.py is the gate that must catch a bald render.")
    refusals = d.get("refusals") or []
    for r in refusals:
        print("REFUSAL:", r)
    if refusals:
        return 5

    print()
    print("PLACED. This proves the actor and the rig exist -- it says NOTHING "
          "about what will render. Run groom_presence.py at this framing "
          "before treating any capture as a deliverable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
