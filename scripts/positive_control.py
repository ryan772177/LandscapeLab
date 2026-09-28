"""positive_control.py — prove a mutation reaches the CAPTURED pixels.

WHY THIS EXISTS
Two landscape-LOD mutations produced no pixel change. One (the cvar)
never applied; the other (per-component ForcedLOD) verified as applied on
all 1024 components and still moved nothing. At that point "no effect"
and "dead instrument" are indistinguishable, and every render conclusion
in the session rests on the difference.

So: hide a whole landscape proxy — a mutation that CANNOT be subtle — and
capture. A missing terrain chunk either shows up or the capture chain is
not seeing the scene the mutations touch.

THE ASYMMETRY IS THE POINT. This does not test LOD. It tests the LOOP:
mutate -> editor applies -> viewport draws -> screenshot lands on disk.
If the loop is dead, both prior no-ops are explained and neither says
anything about LOD.

API verified in the generated stub before use, per the reference doctrine
(Tier 1 — local ground truth, and API-remembered-is-API-guessed):
  Intermediate/PythonStub/unreal.py:242932
      Actor.set_is_temporarily_hidden_in_editor(is_hidden: bool) -> None
The EDITOR path is deliberate: set_hidden_in_game (:381178) governs the
GAME view and would be the wrong instrument for an editor viewport
screenshot — a mutation that lands somewhere the camera is not looking
would read exactly like a dead loop.

MUTATES EDITOR VISIBILITY ONLY. Nothing is saved. --restore unhides
every landscape actor and verifies it.

Exit codes:
  0  applied and verified (or restored)
  1  unexpected error
  3  editor identity gate refused
  4  probe returned nothing, or the read-back disagreed with the request
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_POSCTRL__"

# No file extensions in the payload — a '.p'+'y' substring makes UE treat
# the whole script as a filename (PythonScriptPlugin.cpp:813-830).
PROBE = '''
import json as _json
import unreal as _unreal

_hide = {hide!r}
_near_x = {near_x!r}
_near_y = {near_y!r}
_foliage = {foliage!r}
_out = {{"ok": False, "hidden": [], "restored": 0, "candidates": 0}}

try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _acts = []
    # FOLIAGE MODE is the control-on-the-control. Landscape rendering is
    # driven by components and LandscapeInfo, so a PROXY ACTOR's
    # editor-hidden flag may simply not propagate to the landscape render
    # proxies — in which case the failed landscape control says nothing
    # about the capture chain. InstancedFoliageActor holds 157,554
    # conifers and is an ordinary actor; hiding it either empties the
    # frame or the chain is dead. That distinction is the whole point.
    # RESTORE covers EVERY class this tool can hide, regardless of which
    # mode hid it. A restore that only unhides what the current flags
    # select would leave the other class hidden and silently poison the
    # next capture.
    if not _hide:
        _classes = (_unreal.Landscape, _unreal.LandscapeStreamingProxy,
                    _unreal.InstancedFoliageActor)
    elif _foliage:
        _classes = (_unreal.InstancedFoliageActor,)
    else:
        _classes = (_unreal.Landscape, _unreal.LandscapeStreamingProxy)
    for _cls in _classes:
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(_w, _cls):
            _acts.append(_a)
    _out["candidates"] = len(_acts)
    if _foliage and _hide:
        for _a in _acts:
            try:
                _a.set_is_temporarily_hidden_in_editor(True)
                _out["hidden"].append(_a.get_actor_label())
            except Exception as _e:
                _out["err"] = type(_e).__name__
        _out["verified"] = all(
            _a.is_temporarily_hidden_in_editor() for _a in _acts) \\
            if _acts else False
        _out["distance_cm"] = 0.0
        _hide = False
        _acts = []

    if not _hide:
        for _a in _acts:
            try:
                _a.set_is_temporarily_hidden_in_editor(False)
                _out["restored"] += 1
            except Exception:
                pass
        _out["still_hidden"] = sum(
            1 for _a in _acts if _a.is_temporarily_hidden_in_editor())
    else:
        _best = None
        _bd = None
        for _a in _acts:
            _l = _a.get_actor_location()
            _d = ((_l.x - _near_x) ** 2 + (_l.y - _near_y) ** 2) ** 0.5
            if _bd is None or _d < _bd:
                _bd = _d
                _best = _a
        if _best is not None:
            _best.set_is_temporarily_hidden_in_editor(True)
            _out["hidden"].append(_best.get_actor_label())
            _out["verified"] = bool(_best.is_temporarily_hidden_in_editor())
            _out["distance_cm"] = _bd
    del _w
    del _ues
    del _acts
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

for _n in ("_a", "_w", "_ues", "_acts", "_best", "_l"):
    globals().pop(_n, None)

print("{marker}" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--near", nargs=2, type=float, default=[-171041.9,
                                                            -53291.2],
                    help="XY in cm; the landscape actor nearest this is "
                         "hidden. Default: the sweep_0060 station.")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--foliage", action="store_true",
                    help="Hide InstancedFoliageActor instead of a "
                         "landscape proxy. Control-on-the-control: an "
                         "ordinary actor that must respond to editor "
                         "hiding.")
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    source = PROBE.format(hide=not args.restore, near_x=args.near[0],
                          near_y=args.near[1], foliage=args.foliage,
                          marker=MARKER)
    if (".p" + "y") in source:
        print("REFUSE: payload carries a file extension.")
        return 1

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        try:
            remote.open_command_connection(node["node_id"])
            res = remote.run_command(source, unattended=True,
                                     exec_mode=remote_exec.MODE_EXEC_FILE)
            text = bootstrap._collect_output(res or {})
            i = text.find(MARKER)
            out = json.JSONDecoder().raw_decode(
                text[i + len(MARKER):].lstrip())[0] if i >= 0 else None
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass

        if not out or not out.get("ok"):
            print("FAIL: probe returned nothing usable ({0}).".format(
                (out or {}).get("error", "no result")))
            return 4

        print("  landscape actors : {0}".format(out.get("candidates")))
        if args.restore:
            print("  unhidden         : {0}".format(out.get("restored")))
            print("  still hidden     : {0}".format(out.get("still_hidden")))
            return 0 if not out.get("still_hidden") else 4
        print("  hidden           : {0}".format(out.get("hidden")))
        print("  distance from cam: {0:.0f} cm".format(
            out.get("distance_cm") or -1))
        # Read-back is the verdict, not the call returning.
        if out.get("verified") is True:
            print("")
            print("VERIFIED HIDDEN. Capture now; a missing terrain chunk "
                  "must dwarf the 0.0117 noise floor. If it does not, the "
                  "CAPTURE CHAIN is dead and no LOD conclusion is "
                  "available.")
            return 0
        print("FAILED: the actor does not report hidden after the set.")
        return 4
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
