"""park_viewport.py — put the editor viewport at a named recipe camera.

WHY THIS EXISTS
---------------
The GPU cost of a material feature is measured by reading the viewport
overlay in two configurations and subtracting. That subtraction is only
meaningful if BOTH readings look at the SAME pixels: GPU cost here is
per-pixel shading (R13 ADDENDUM: "the cost is PER-PIXEL SHADING ... not
scene bloat"), so a few degrees of yaw changes how much rock is on screen
and therefore changes the number being attributed to the feature.

Flying the viewport by hand between configurations cannot deliver that.
This parks it on the recipe's own declared station, deterministically, as
many times as needed.

NOT A CAPTURE. Takes no screenshot, writes no file, saves no asset. The
only editor state it changes is where the viewport is looking.

SINGLE DECLARATION (non-negotiable 24)
--------------------------------------
The station comes from `capture.cameras` in the recipe -- the SAME list
capture.py renders from. There is no second copy of these coordinates
here, so a camera that moves in the recipe moves for both tools at once.
That is exactly the trap `recipes/alpine_ridge_rerun.json` was trashed
for: its own copy of the landscape transform beside one camera.

THE WRITE IS READ BACK, AND THE READ-BACK CAN FAIL THE RUN
----------------------------------------------------------
`set_level_viewport_camera_info` returns nothing. CURRENT STATE records
three landscape mutations on this project that "returned ok and moved
nothing" (`r.LandscapeLODBias`, per-component `ForcedLOD`,
`force_layers_full_update`), so a silent no-op here is a live failure
mode, not a hypothetical -- and it would silently invalidate the very
comparison this tool exists to make. The payload therefore reads the
viewport back with `get_level_viewport_camera_info` and this script exits
3 if the position missed by more than the tolerance. A parked viewport is
CLAIMED only when the editor agrees it is parked.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_PARK__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{}}
_ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)

_loc = _unreal.Vector({x}, {y}, {z})
_rot = _unreal.Rotator(roll={roll}, pitch={pitch}, yaw={yaw})
_ues.set_level_viewport_camera_info(_loc, _rot)

# READ BACK from the editor, not from the values just sent. A setter that
# returns None proves nothing landed; this asks the viewport where it
# actually is. Same instrument-distrust the landscape writes earned.
#
# The stub types this Optional[Tuple[Vector, Rotator]] -- it CAN return
# None (unreal.py:636979 class surface). Unpacking it blind would raise a
# TypeError, which reads as a broken script rather than as "the editor
# would not tell me". Those are different outcomes and non-negotiable 6
# requires them to stay different.
_info = _ues.get_level_viewport_camera_info()
_out["want_loc"] = [{x}, {y}, {z}]
_out["want_rot"] = [{pitch}, {yaw}, {roll}]
if _info is None:
    _out["readback"] = "REFUSED"
else:
    _gl, _gr = _info
    _out["readback"] = "ok"
    _out["got_loc"] = [_gl.x, _gl.y, _gl.z]
    _out["got_rot"] = [_gr.pitch, _gr.yaw, _gr.roll]
    _out["loc_err_cm"] = max(
        abs(_gl.x - ({x})), abs(_gl.y - ({y})), abs(_gl.z - ({z})))

# VIEWPORT SIZE IS PART OF THE MEASUREMENT, NOT TRIVIA. GPU cost here is
# per-pixel shading, so ms scales with pixel count: the 2026-08-06
# readings are 971x752, and quoting a number taken at a different size
# against them is the category error R13's CALIBRATION CLASS warns about.
# Reading it turns that caveat from a warning into a fact.
_size = _ues.get_level_viewport_size()
_out["viewport"] = None if _size is None else [_size.x, _size.y]

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    for line in (text or "").splitlines():
        if MARKER in line:
            try:
                return json.loads(line.split(MARKER, 1)[1])
            except Exception:
                return None
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--camera", required=True,
                    help="name from the recipe's capture.cameras")
    ap.add_argument("--recipe", default="recipes/alpine.json")
    ap.add_argument("--tolerance-cm", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    path = os.path.join(bootstrap.REPO_ROOT, args.recipe)
    with open(path, encoding="utf-8") as fh:
        cams = json.load(fh)["capture"]["cameras"]
    named = {c["name"]: c for c in cams}
    if args.camera not in named:
        print("REFUSE: no camera '{0}' in {1}.".format(args.camera, args.recipe))
        print("        declared: {0}".format(", ".join(sorted(named))))
        return 2
    cam = named[args.camera]
    loc, rot = cam["location_cm"], cam["rotation_deg"]

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("camera    : {0}  (from {1})".format(args.camera, args.recipe))
    print("MOVES THE VIEWPORT ONLY: no screenshot, no file, no asset saved.")
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            r = remote.run_command(
                PAYLOAD.format(marker=MARKER,
                               x=loc[0], y=loc[1], z=loc[2],
                               pitch=rot[0], yaw=rot[1], roll=rot[2]),
                unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            if not r or not r.get("success"):
                print("command failed: {0}".format((r or {}).get("result")))
                return 2
            data = _parse(bootstrap._collect_output(r))
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    if data is None:
        print("COULD NOT READ BACK: the editor returned no parseable result.")
        print("The viewport may or may not have moved -- this is UNKNOWN,")
        print("not a failure and not a success. Do not read the overlay.")
        return 4

    if data.get("readback") != "ok":
        print("COULD NOT LOOK: get_level_viewport_camera_info returned None.")
        print("The viewport may have moved; the editor would not confirm it.")
        print("That is UNKNOWN, not a pass. Do not take a GPU reading.")
        return 4

    vp = data.get("viewport")
    if vp is None:
        print("  viewport size: COULD NOT READ")
    else:
        print("  viewport size: {0}x{1}  ({2} the 971x752 of the"
              .format(vp[0], vp[1],
                      "MATCHES" if vp == [971, 752] else "DIFFERS from"))
        print("                 2026-08-06 readings)")
        if vp != [971, 752]:
            print("                 -> absolute ms are NOT comparable to")
            print("                    94.45 / 75.71; an A/B taken entirely")
            print("                    within THIS session still is.")
    print("")

    err = data["loc_err_cm"]
    print("  requested  {0}".format(data["want_loc"]))
    print("  read back  {0}".format(
        [round(v, 1) for v in data["got_loc"]]))
    print("  worst axis error: {0:.3f} cm".format(err))
    print("")
    if err > args.tolerance_cm:
        print("FAIL: viewport did not land (>{0} cm). The call returned"
              .format(args.tolerance_cm))
        print("without error and the viewport did NOT move -- the exact")
        print("failure mode three landscape writes showed on this project.")
        print("DO NOT take a GPU reading; it would be of a different view.")
        return 3

    print("PARKED at {0}.".format(args.camera))
    print("")
    print("CALIBRATION CLASS travels with any number you now read:")
    print("  editor viewport, Intel iGPU, editor perf config.")
    print("  NOT shipping, NOT PIE, NOT the future 5080 baseline.")
    print("  The 2026-08-06 readings were taken at 971x752 RenderRes 100%;")
    print("  a different viewport SIZE makes the absolute ms incomparable")
    print("  to those, though an A/B taken in ONE session stays valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
