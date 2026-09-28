"""highres_shot.py — one HIGH-RESOLUTION still of the current viewport.

Deliberately NOT part of the capture sweep. `capture.py` renders every
`capture.cameras` recipe station (21 today) at `capture.resolution` and
exists to make a comparable evidence SET. This takes ONE frame at whatever
resolution the machine can stand, for looking at rather than for measuring.

WHY THAT DISTINCTION MATTERS. A frame taken at a different resolution is
a different CALIBRATION CLASS: it cannot be diffed against the sweep, and
any statistic taken from it is not comparable to the 0.00298 noise floor
or to any per-station luma on the board. This script prints that warning
on every run (once the memory checks pass) so a high-res still cannot
quietly end up cited as evidence in a comparison it does not belong to.

THE VIEWPORT IS THE SUBJECT, so park it first with `park_viewport.py`,
which reads the camera back and refuses on a mismatch. HighResShot
captures the active editor viewport, not a recipe camera.

MEMORY IS THE REAL LIMIT. The shot is rendered by tiling at
multiplier x viewport size, and on a host with little free RAM a large
multiplier fails rather than degrading. `resource_guard` is consulted and
the request is REFUSED below the floor instead of being attempted.

Output lands in `Saved/Screenshots/WindowsEditor/`. That path is engine
convention, not ours.

Exit codes:
  0  shot requested and a new file appeared
  2  refused: bad --multiplier/--resolution combination, memory unreadable,
     below the memory floor, or the editor identity gate (rule 7)
  4  the command ran and no new file appeared
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import resource_guard     # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
SHOT_DIR = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Screenshots",
                        "WindowsEditor")
MARKER = "__LANDSCAPELAB_HIGHRES__"
FLOOR_GB = 1.0

PAYLOAD = '''
import json as _json
import unreal as _unreal
_out = {{"ok": False, "error": None, "cmd": {cmd!r}}}
try:
    _sl = _unreal.SystemLibrary
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _sl.execute_console_command(_w, {cmd!r})
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "{{0}}: {{1}}".format(type(_e).__name__, _e)
print("{marker}" + _json.dumps(_out))
'''


def _existing():
    """{path: mtime} — NOT a set of names.

    The engine reuses `HighresScreenshot00000.png` rather than always
    incrementing, so a second shot OVERWRITES the first. Watching for a
    new NAME therefore reports "no new file" on a completely successful
    overwrite — which is a false negative on the only evidence this
    script produces. Keyed on mtime so a rewrite of the same name counts.
    """
    out = {}
    for p in glob.glob(os.path.join(SHOT_DIR, "*.png")):
        try:
            out[p] = os.path.getmtime(p)
        except OSError:
            pass
    return out


def _appeared(before, now):
    """Paths that are new OR were rewritten since `before`."""
    return [p for p, m in now.items()
            if p not in before or m > before[p] + 0.5]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--multiplier", type=float, default=None,
                    help="HighResShot multiplier, e.g. 4 for 4x the "
                         "viewport in each axis")
    ap.add_argument("--resolution", default=None,
                    help="explicit WxH, e.g. 3840x2160")
    ap.add_argument("--wait", type=int, default=180,
                    help="seconds to wait for the file to appear")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args(argv)

    if bool(args.multiplier) == bool(args.resolution):
        print("REFUSE: give exactly one of --multiplier or --resolution.")
        return 2
    cmd = ("HighResShot {0}".format(args.resolution) if args.resolution
           else "HighResShot {0:g}".format(args.multiplier))

    free, _total = resource_guard.available_gb()
    if free is None:
        print("REFUSE: could not read available memory. A high-res shot "
              "tiles the render and is one of the larger allocations this "
              "project makes; refusing to attempt it blind.")
        return 2
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("command   : {0}".format(cmd))
    print("free RAM  : {0:.2f} GB".format(free))
    if free < FLOOR_GB:
        print("REFUSE: below the {0:.1f} GB floor.".format(FLOOR_GB))
        return 2
    print("")
    print("CALIBRATION CLASS: this frame is NOT comparable to the capture")
    print("sweep. Different resolution means different pixel statistics —")
    print("do not diff it against sweep frames or quote a luma from it")
    print("against the board's per-station numbers. It is for LOOKING AT.")
    print("")

    before = _existing()
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            25)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        remote.open_command_connection(node["node_id"])
        remote.run_command(PAYLOAD.format(cmd=cmd, marker=MARKER),
                           unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    # The console command returns immediately; the file appears later.
    deadline = time.time() + args.wait
    while time.time() < deadline:
        new = _appeared(before, _existing())
        if new:
            path = sorted(new)[0]
            # Wait for the size to settle so a half-written file is not
            # reported as a finished one.
            last = -1
            for _ in range(30):
                sz = os.path.getsize(path)
                if sz == last and sz > 0:
                    break
                last = sz
                time.sleep(1.0)
            print("WROTE {0}".format(path))
            print("  {0:,} bytes".format(os.path.getsize(path)))
            return 0
        time.sleep(2.0)

    print("NO NEW OR REWRITTEN FILE after {0}s. The command was accepted; "
          "this is 'I could not confirm', not 'it failed'."
          .format(args.wait))
    print("")
    print("CHECK IN THIS ORDER. The order is from being wrong about it:")
    print("")
    print("  1. FREE MEMORY, measured AGAINST THE LOADED WORLD. The shot")
    print("     tiles at multiplier x viewport, and a world holding")
    print("     171,069 instances leaves far less headroom than an empty")
    print("     one. A 4x shot succeeded here on an EMPTY world and then")
    print("     failed three times on the loaded one, with the engine")
    print("     accepting `Cmd: HighResShot 4` every time. Lower the")
    print("     multiplier, or free memory, before anything else.")
    print("")
    print("  2. `bThrottleCPUWhenNotForeground`. A backgrounded editor")
    print("     stops rendering and never finishes tiling. Real, and the")
    print("     root cause of the capture-stall class — but it presents")
    print("     IDENTICALLY to (1), and on 2026-08-09 it was the wrong")
    print("     answer. Do not reach for it first just because it is the")
    print("     more interesting explanation.")
    print("")
    print("  Then check {0}".format(SHOT_DIR))
    return 4


if __name__ == "__main__":
    sys.exit(main())
