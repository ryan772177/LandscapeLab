"""Ask World Partition to describe itself, so the truth frame's grid name is
DISCOVERED rather than guessed.

`wp.Runtime.OverrideRuntimeLoadingRange` takes `-grid=[Name]`, and the obvious
guess is "MainGrid". A guess that happens to be right is indistinguishable from
knowledge until the day it is wrong, so this runs the engine's own dump command
and the host parses the grid names out of the log.

Run via: python scripts/ue_exec.py scripts/payloads/bench_dump_wp.py
"""
import json as _json

import unreal as _u

_out = {"error": None}
try:
    _w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    _out["level_path"] = _w.get_path_name()
    for _cmd in ("wp.Runtime.DumpWorldPartitions",
                 "wp.Runtime.DumpStreamingSources"):
        _u.SystemLibrary.execute_console_command(_w, _cmd)
    _out["issued"] = ["wp.Runtime.DumpWorldPartitions",
                      "wp.Runtime.DumpStreamingSources"]
    del _w
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out))
