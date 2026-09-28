"""run_pie_probe.py — start PIE, run an arbitrary payload against it, end PIE.

PIE needs ticks between "start" and "look", and a remote-exec payload blocks
the game thread, so a single payload cannot wait for the world to exist. This
is the three-call shape probe_pie.py uses, generalised so any diagnostic
payload can be dropped into the middle of a live session.

Usage:
    python scripts/hero_face/run_pie_probe.py <payload.txt> [--settle 35]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ue_exec  # noqa: E402

START = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "already": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _out["already"] = bool(_les.is_in_play_in_editor())
    if not _out["already"]:
        _les.editor_request_begin_play()
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out, default=str))
'''

STOP = r'''
import json as _json
import unreal as _unreal
_out = {"error": None}
try:
    _unreal.get_editor_subsystem(
        _unreal.LevelEditorSubsystem).editor_request_end_play()
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out, default=str))
'''


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("payload")
    ap.add_argument("--settle", type=float, default=35.0)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.payload):
        print("REFUSE: no such payload:", args.payload)
        return 2
    with open(args.payload, "r", encoding="utf-8") as fh:
        body = fh.read()

    rc, d, _ = ue_exec.run(START, stage_name="pieprobe_start", timeout=15.0,
                           quiet=True)
    print("start:", json.dumps(d, default=str))
    if d is None or d.get("error"):
        return 1
    print("settling %.0f s ..." % args.settle)
    time.sleep(args.settle)

    rc2, d2, _ = ue_exec.run(body, stage_name="pieprobe_body", timeout=15.0,
                             quiet=True)
    print("--- probe ---")
    print(json.dumps(d2, indent=2, default=str))

    time.sleep(3.0)
    ue_exec.run(STOP, stage_name="pieprobe_stop", timeout=15.0, quiet=True)
    print("PIE ended.")
    return 0 if d2 is not None else 1


if __name__ == "__main__":
    sys.exit(main())
