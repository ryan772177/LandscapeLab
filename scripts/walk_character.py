"""walk_character.py — walk the player and see whether the ground holds.

PHASE2_PLAN.md unit 5's first acceptance clause: "walk 1 km ... without
falling through and without a step-height stall, trace log kept".

READ-ONLY with respect to the world. Everything happens inside PIE, which
runs against a duplicate and is discarded on exit.

=====================================================================
WHY A TICK CALLBACK AND NOT A LOOP
=====================================================================
`AddMovementInput` is consumed by ONE tick. A Python loop cannot drive it,
because a remote-exec payload BLOCKS the game thread -- no ticks happen while
the loop runs, so the character would receive input and never move.

`unreal.register_slate_post_tick_callback` (PythonStub 708181) runs a callable
every tick, after the game has ticked. So the driving happens in the engine's
own loop and this script only starts it, polls it, and stops it.

=====================================================================
WHAT THIS PROVES AND WHAT IT DOES NOT
=====================================================================
It proves: the character is supported by the collision surface along the
route, under real CharacterMovementComponent floor checks and real step-ups.

It does NOT walk "the inter-massif corridor", because **that corridor has no
spatial definition anywhere in this repo** -- `WORLD_VISION.md:304` defines it
in prose and gives no coordinates. R-WALK records the same gap. This walks a
straight line on a declared heading from the spawn point, and says so.

=====================================================================
THE TWO FAILURES IT LOOKS FOR
=====================================================================
FELL THROUGH -- sustained `is_falling` and a large negative Z excursion. A
brief fall at spawn is normal (the capsule settles); a sustained one is not.

STEP-HEIGHT STALL -- horizontal speed near zero for a sustained window WHILE
input is being applied. This is the failure `MaxStepHeight` causes, and it is
distinct from falling: the character is on the ground and cannot proceed.

Exit codes:
  0  walked; both checks passed
  1  could not look
  2  bad arguments
  3  rule 7: no verified editor node
  4  the character FELL THROUGH
  5  the character STALLED
  6  PIE is still in play, OR its end could not be confirmed (the confirm
     payload returned no marker) -- the editor needs attention
  7  the walk did not cover the requested distance in the time budget
  8  a speed was commanded via --speed-cm-s and could not be verified -- the
     movement component could not be read, or read back a value other than
     commanded (REFUSE; an unknown is not a yes)
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_WALK__"
VERIFY_DIR = os.path.join(bootstrap.REPO_ROOT, "_verify")


# WHAT THE TRACE FILE CONTAINS — ONE DECLARATION, TWO CALL SITES.
#
# It used to be two literals, in PAYLOAD_STOP and in PAYLOAD_FORCE_STOP, and
# they drifted the moment a field was added: the ordinary stop learned to write
# the residency series and the FORCED one did not. The forced path is the one
# that runs when the ordinary reply is lost, so the subset was written on
# exactly the run whose data was least recoverable.
#
# Non-negotiable 24: two lists that must agree are one list, badly stored.
# "Update both carefully" is not a fix — adding a field must be impossible to
# do in one place and forget in the other.
_TRACE_DUMP = (
    '_json.dump({"log": _s["log"], "dist": _s["dist"],\n'
    '            "t": _s["t"], "start": _s["start"],\n'
    '            "res": _s.get("res") or [],\n'
    '            "res_why": _s.get("res_why")}, _fh)')


def _trace_dump(indent):
    """The dump statement, re-indented for its call site."""
    pad = " " * indent
    return ("\n" + pad).join(_TRACE_DUMP.split("\n"))


PAYLOAD_BEGIN = r'''
import json as _json
import unreal as _unreal
_out = {"error": None}
try:
    _unreal.get_editor_subsystem(
        _unreal.LevelEditorSubsystem).editor_request_begin_play()
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_WALK__" + _json.dumps(_out))
'''


# Starts the tick driver. State lives in a module-level global because a tick
# callback outlives the payload that registered it. It is torn down explicitly
# in PAYLOAD_STOP -- open_level.py scrubs persistent console globals by
# reachability, and leaving a live callback behind would survive a level
# change and keep driving a pawn that no longer exists.
PAYLOAD_START = r'''
import json as _json
import math as _math
import unreal as _unreal
_out = {"error": None, "started": False, "spawn": None, "resolved": None}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _gw = _ues.get_game_world()
    if _gw is None:
        _out["error"] = "no game world -- PIE is not running"
    else:
        _pawn = _unreal.GameplayStatics.get_player_pawn(_gw, 0)
        if _pawn is None:
            _out["error"] = "no player pawn"
        else:
            _l = _pawn.get_actor_location()
            _out["spawn"] = [float(_l.x), float(_l.y), float(_l.z)]
            _out["pawn_class"] = _pawn.get_class().get_name()

            # What actually resolved onto the character, read off the
            # COMPONENTS rather than off the config that set them.
            try:
                _m, _ac, _mc, _n, _un = _pawn.get_resolved_spec()
                _out["resolved"] = {"mesh": str(_m), "anim_class": str(_ac),
                                    "mapping_context": str(_mc),
                                    "bound_actions": int(_n),
                                    "unresolved": str(_un)}
            except Exception as _re:
                _out["resolved"] = {"error": type(_re).__name__ + ": " + str(_re)}

            # SPEED. Set on the PIE pawn's movement component, never in the
            # recipe -- PIE runs against a duplicate world, so this dies with
            # play and no asset is touched.
            #
            # !! IT IS READ BACK AND RETURNED, and the caller REFUSES if the
            # value did not take. A run that commands mounted speed, silently
            # moves at 600 and reports "mounted" is worse than no measurement:
            # it would certify streaming at a speed nothing ever travelled at.
            _out["speed_asked"] = __SPEED__
            _out["speed_before"] = None
            _out["speed_after"] = None
            try:
                _mc = _pawn.get_movement_component()
                _out["speed_before"] = float(
                    _mc.get_editor_property("max_walk_speed"))
                if __SPEED__ is not None:
                    _mc.set_editor_property("max_walk_speed", float(__SPEED__))
                _out["speed_after"] = float(
                    _mc.get_editor_property("max_walk_speed"))
            except Exception as _se:
                _out["speed_error"] = type(_se).__name__ + ": " + str(_se)

            _yaw = __YAW__
            _dir = _unreal.Vector(_math.cos(_math.radians(_yaw)),
                                  _math.sin(_math.radians(_yaw)), 0.0)

            global _LL_WALK
            _LL_WALK = {"log": [], "done": False, "handle": None,
                        "t": 0.0, "dist": 0.0,
                        "start": (float(_l.x), float(_l.y), float(_l.z)),
                        "last": (float(_l.x), float(_l.y)),
                        "target_cm": __TARGET__, "budget_s": __BUDGET__,
                        "dir": _dir, "sample_every": 0.25, "next_sample": 0.0,
                        "res": [], "res_every": __RESEVERY__,
                        "next_res": 0.0}

            def _tick(_dt):
                _s = _LL_WALK
                if _s["done"]:
                    return
                _s["t"] += _dt
                _w = _unreal.get_editor_subsystem(
                    _unreal.UnrealEditorSubsystem).get_game_world()
                if _w is None:
                    _s["done"] = True
                    return
                _p = _unreal.GameplayStatics.get_player_pawn(_w, 0)
                if _p is None:
                    _s["done"] = True
                    return
                # Drive. force=True so it applies even before a controller has
                # finished setting up input.
                _p.add_movement_input(_s["dir"], 1.0, True)
                _loc = _p.get_actor_location()
                _dx = float(_loc.x) - _s["last"][0]
                _dy = float(_loc.y) - _s["last"][1]
                _s["dist"] += _math.sqrt(_dx * _dx + _dy * _dy)
                _s["last"] = (float(_loc.x), float(_loc.y))
                if _s["t"] >= _s["next_sample"]:
                    _s["next_sample"] = _s["t"] + _s["sample_every"]
                    _v = _p.get_velocity()
                    # is_falling lives on NavMovementComponent (PythonStub
                    # 506206), reached via Pawn.get_movement_component().
                    # ACharacter has NO get_character_movement() in Python --
                    # calling it raises, and the first version swallowed that
                    # and logged None on every sample, which the analysis then
                    # printed as "0.0% falling". A could-not-look reported as a
                    # measurement is non-negotiable 6, and it was in this tool.
                    _fall = None
                    try:
                        _fall = bool(_p.get_movement_component().is_falling())
                    except Exception as _fe:
                        if _s.get("fall_why") is None:
                            _s["fall_why"] = type(_fe).__name__ + ": " + str(_fe)
                    _s["log"].append([
                        round(_s["t"], 3), round(float(_loc.x), 1),
                        round(float(_loc.y), 1), round(float(_loc.z), 1),
                        round(_math.sqrt(float(_v.x) ** 2 + float(_v.y) ** 2), 1),
                        _fall, round(_s["dist"], 1)])
                # RESIDENCY, on its own coarser cadence. Counting actors is an
                # O(n) iteration over the world, so it deliberately does NOT
                # ride the 0.25 s movement sample -- the instrument would then
                # be a significant part of the load it is measuring.
                if _s["res_every"] > 0 and _s["t"] >= _s["next_res"]:
                    _s["next_res"] = _s["t"] + _s["res_every"]
                    try:
                        _lp = _unreal.GameplayStatics.get_all_actors_of_class(
                            _w, _unreal.LandscapeStreamingProxy)
                        _fa = _unreal.GameplayStatics.get_all_actors_of_class(
                            _w, _unreal.InstancedFoliageActor)
                        _s["res"].append([round(_s["t"], 2), len(_lp), len(_fa),
                                          round(float(_loc.x), 0),
                                          round(float(_loc.y), 0)])
                    except Exception as _pe:
                        if _s.get("res_why") is None:
                            _s["res_why"] = type(_pe).__name__ + ": " + str(_pe)

                if _s["dist"] >= _s["target_cm"] or _s["t"] >= _s["budget_s"]:
                    _s["done"] = True

            _LL_WALK["handle"] = _unreal.register_slate_post_tick_callback(_tick)
            _out["started"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_WALK__" + _json.dumps(_out))
'''


PAYLOAD_POLL = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "done": None, "t": None, "dist": None, "samples": 0}
try:
    _s = globals().get("_LL_WALK")
    if _s is None:
        _out["error"] = "no walk state -- was it started?"
    else:
        _out["done"] = bool(_s["done"])
        _out["t"] = round(_s["t"], 2)
        _out["dist"] = round(_s["dist"], 1)
        _out["samples"] = len(_s["log"])
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_WALK__" + _json.dumps(_out))
'''


PAYLOAD_STOP = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "log_file": None, "samples": 0, "dist": None,
        "t": None, "cleaned": False}
try:
    _s = globals().get("_LL_WALK")
    if _s is None:
        _out["error"] = "no walk state"
    else:
        _s["done"] = True
        if _s.get("handle") is not None:
            try:
                _unreal.unregister_slate_post_tick_callback(_s["handle"])
            except Exception as _ue:
                _out["error"] = "unregister failed: " + str(_ue)
        # THE LOG GOES TO A FILE, NOT INTO THE REPLY. The first run of this
        # tool returned 1621 samples inline and the reply exceeded the
        # remote-exec deserialization limit -- so a completed walk reported as
        # "NO MARKER" and the whole trace was nearly lost. Same class as
        # save_level's 418 KB reply. Only the summary comes back.
        _p = _unreal.Paths.project_saved_dir() + "ll_walk_log.json"
        with open(_p, "w") as _fh:
            __TRACEDUMP8__
        _out["log_file"] = _p
        _out["samples"] = len(_s["log"])
        _out["dist"] = round(_s["dist"], 1)
        _out["t"] = round(_s["t"], 2)
        # Delete the global. A live callback or a stale dict surviving into a
        # later payload is exactly the persistent-globals hazard open_level.py
        # exists to scrub.
        del globals()["_LL_WALK"]
        _out["cleaned"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_WALK__" + _json.dumps(_out))
'''


# Teardown whose reply carries ONE boolean. Used when PAYLOAD_STOP's reply
# does not come back: the work is idempotent, and the point is to guarantee
# the callback is unregistered and the global gone even when nothing can be
# reported about it.
PAYLOAD_FORCE_STOP = r'''
import json as _json
import unreal as _unreal
_ok = False
try:
    _s = globals().get("_LL_WALK")
    if _s is not None:
        _s["done"] = True
        if _s.get("handle") is not None:
            try:
                _unreal.unregister_slate_post_tick_callback(_s["handle"])
            except Exception:
                pass
        try:
            _p = _unreal.Paths.project_saved_dir() + "ll_walk_log.json"
            with open(_p, "w") as _fh:
                # SAME FIELDS AS THE NORMAL STOP, by construction rather than
                # by care -- this path runs when the ordinary reply did not
                # come back, i.e. on the run whose data is least recoverable.
                __TRACEDUMP16__
        except Exception:
            pass
        del globals()["_LL_WALK"]
    _ok = True
except Exception:
    _ok = False
print("__LL_WALK__" + _json.dumps({"forced": _ok}))
'''


# The one declaration, projected into its two call sites -- and ASSERTED, at
# import, so an unsubstituted placeholder can never reach the editor. A payload
# is a call site with no compiler; this is the compiler.
PAYLOAD_STOP = PAYLOAD_STOP.replace("__TRACEDUMP8__", _trace_dump(8))
PAYLOAD_FORCE_STOP = PAYLOAD_FORCE_STOP.replace("__TRACEDUMP16__",
                                                _trace_dump(16))
for _name, _body in (("PAYLOAD_STOP", PAYLOAD_STOP),
                     ("PAYLOAD_FORCE_STOP", PAYLOAD_FORCE_STOP)):
    assert "__TRACEDUMP" not in _body, (
        "%s still carries an unsubstituted trace-dump placeholder" % _name)
    assert '"res_why"' in _body, (
        "%s lost the trace dump entirely" % _name)


PAYLOAD_END = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _les.editor_request_end_play()
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_WALK__" + _json.dumps(_out))
'''


PAYLOAD_CONFIRM = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None}
try:
    _out["in_play"] = bool(_unreal.get_editor_subsystem(
        _unreal.LevelEditorSubsystem).is_in_play_in_editor())
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_WALK__" + _json.dumps(_out))
'''


def _run(remote, remote_exec, payload):
    r = remote.run_command(payload, unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    text = bootstrap._collect_output(r)
    i = text.find(MARKER)
    if i < 0:
        return None, text
    d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    return d, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metres", type=float, default=1000.0)
    ap.add_argument("--yaw", type=float, default=135.0,
                    help="heading to walk. NOT the corridor -- that has no "
                         "spatial definition in this repo.")
    ap.add_argument("--budget", type=float, default=420.0,
                    help="seconds of game time before the walk gives up")
    ap.add_argument("--settle", type=float, default=30.0)
    ap.add_argument("--stall-speed", type=float, default=20.0,
                    help="cm/s below which the character counts as stopped")
    ap.add_argument("--stall-window", type=float, default=3.0,
                    help="seconds of continuous stop that counts as a stall")
    ap.add_argument("--walkable-deg", type=float, default=70.0,
                    help="the character's walkable floor angle; the fall test "
                         "asks whether descent exceeded what this allows")
    ap.add_argument("--fall-margin-cm", type=float, default=60.0,
                    help="slack per sample before descent counts as excess")
    ap.add_argument("--fall-window", type=float, default=1.0,
                    help="seconds of continuous excess descent that is a fall")
    ap.add_argument("--speed-cm-s", type=float, default=None,
                    help="override MaxWalkSpeed on the PIE pawn for this run. "
                         "PIE runs against a duplicate, so nothing persists "
                         "and no recipe is touched. WORLD_VISION rules mounts "
                         "at ~3x on foot, so 1800 against the recipe's 600 is "
                         "the mounted-streaming case. The value is READ BACK "
                         "and the run REFUSES if it did not take.")
    ap.add_argument("--residency-every", type=float, default=2.0,
                    help="seconds between residency samples (resident "
                         "landscape proxies and foliage actors). 0 disables. "
                         "Deliberately coarser than the movement sample: "
                         "counting actors iterates the world, so a fast "
                         "cadence would make the instrument part of the load.")
    ap.add_argument("--tag", default="walk001")
    ap.add_argument("--from-log", action="store_true",
                    help="analyse the trace already on disk instead of "
                         "walking. No editor, no PIE.")
    args = ap.parse_args(argv)

    if args.metres <= 0:
        print("REFUSE: --metres must be positive.")
        return 2
    target_cm = args.metres * 100.0

    if args.from_log:
        lf = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "ll_walk_log.json")
        try:
            with open(lf, "r", encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as e:
            print("COULD NOT READ %s: %s: %s" % (lf, type(e).__name__, e))
            return 1
        print("analysing the trace already on disk: %s" % lf)
        return _report(args, d.get("log") or [],
                       (d.get("dist") or 0.0) / 100.0,
                       d.get("res") or [], d.get("res_why"))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    started = False
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])

        d, raw = _run(remote, remote_exec, PAYLOAD_BEGIN)
        if d is None or d.get("error"):
            print("BEGIN FAILED:", (d or {}).get("error", "no marker"))
            return 1
        started = True
        print("PIE requested. Settling %.0f s." % args.settle)
        time.sleep(args.settle)

        d, raw = _run(remote, remote_exec,
                      PAYLOAD_START.replace("__YAW__", repr(float(args.yaw)))
                                   .replace("__TARGET__", repr(target_cm))
                                   .replace("__RESEVERY__",
                                            repr(float(args.residency_every)))
                                   .replace("__SPEED__",
                                            repr(None if args.speed_cm_s is None
                                                 else float(args.speed_cm_s)))
                                   .replace("__BUDGET__", repr(float(args.budget))))
        if d is None:
            print("NO MARKER starting the walk.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("COULD NOT START:", d["error"])
            return 1

        print("")
        print("=== THE CHARACTER ===")
        print("  class            %s" % d.get("pawn_class"))
        print("  spawned at       %s" % d.get("spawn"))
        res = d.get("resolved") or {}
        if res.get("error"):
            print("  resolved spec    COULD NOT READ: %s" % res["error"])
        else:
            print("  mesh             %s" % (res.get("mesh") or "NONE"))
            print("  anim class       %s" % (res.get("anim_class") or "NONE"))
            print("  mapping context  %s" % (res.get("mapping_context") or "NONE"))
            print("  bound actions    %s of 3" % res.get("bound_actions"))
            if res.get("unresolved"):
                print("  UNRESOLVED       %s" % res["unresolved"])
        # THE SPEED MUST HAVE TAKEN, OR THE RUN IS VOID. Reported before the
        # walk rather than after, so a refusal costs nothing.
        sb, sa = d.get("speed_before"), d.get("speed_after")
        if d.get("speed_error"):
            print("  MaxWalkSpeed     COULD NOT READ: %s" % d["speed_error"])
            if args.speed_cm_s is not None:
                print("")
                print("REFUSE: a speed was commanded and the component could "
                      "not be read, so")
                print("whether it took is UNKNOWN. An unknown is not a yes.")
                return 8
        else:
            print("  MaxWalkSpeed     %.1f cm/s%s"
                  % (sa if sa is not None else float("nan"),
                     ("  (was %.1f)" % sb) if args.speed_cm_s is not None
                     and sb is not None else ""))
            if args.speed_cm_s is not None and (
                    sa is None or abs(sa - args.speed_cm_s) > 0.5):
                print("")
                print("REFUSE: commanded %.1f cm/s, the component reads %s."
                      % (args.speed_cm_s, sa))
                print("The write did not land. A run reported at a speed it "
                      "never travelled")
                print("at would certify streaming that was never tested.")
                return 8

        print("")
        print("=== WALKING %.0f m on heading %.1f deg ===" % (args.metres, args.yaw))
        print("  (this is a straight line, NOT the inter-massif corridor --")
        print("   that has no spatial definition in this repo)")

        deadline = time.time() + args.budget + 120.0
        last = None
        while time.time() < deadline:
            time.sleep(10.0)
            p, _ = _run(remote, remote_exec, PAYLOAD_POLL)
            if p is None or p.get("error"):
                print("  poll failed: %s" % ((p or {}).get("error", "no marker")))
                break
            last = p
            print("  t=%6.1fs  travelled %8.1f m  samples %d"
                  % (p["t"], p["dist"] / 100.0, p["samples"]))
            if p.get("done"):
                break

        s, raw = _run(remote, remote_exec, PAYLOAD_STOP)
        if s is None:
            # DEGRADE, DO NOT DISCARD. The stop payload writes the trace to
            # disk BEFORE it replies, so a lost reply does not mean a lost
            # walk -- and the first version of this tool threw away a
            # completed 1621-sample trace on exactly this. Retry the teardown
            # with a reply that carries nothing but a flag, and read the trace
            # off the file either way.
            print("NO MARKER on the stop payload — retrying teardown with a")
            print("minimal reply, and reading the trace off disk.")
            _run(remote, remote_exec, PAYLOAD_FORCE_STOP)
            s = {}
        if s.get("error"):
            print("STOP REPORTED:", s["error"])
        # Read the trace off DISK. The reply carries only the summary.
        log = []
        lf = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "ll_walk_log.json")
        res, res_why = [], None
        try:
            with open(lf, "r", encoding="utf-8") as fh:
                _d = json.load(fh)
                log = _d.get("log") or []
                res = _d.get("res") or []
                res_why = _d.get("res_why")
        except Exception as e:
            print("COULD NOT READ THE TRACE at %s: %s: %s"
                  % (lf, type(e).__name__, e))
        if s.get("samples") is not None and len(log) != s["samples"]:
            print("WARNING: editor wrote %s samples, file holds %d — the file "
                  "may be from an earlier run." % (s["samples"], len(log)))
        dist_m = (s.get("dist") or 0.0) / 100.0

        _run(remote, remote_exec, PAYLOAD_END)
        time.sleep(10.0)
        c, _ = _run(remote, remote_exec, PAYLOAD_CONFIRM)
        if c is None or c.get("in_play"):
            print("STILL IN PLAY (or its end could not be confirmed) — press "
                  "Escape in the editor.")
            return 6
        started = False
    finally:
        if started:
            print("WARNING: leaving with PIE possibly still running.")
        try:
            remote.stop()
        except Exception:
            pass

    return _report(args, log, dist_m, res, res_why)


def _report(args, log, dist_m, res=None, res_why=None):
    """Analyse a trace and write the artefact.

    Separated so --from-log can reach it. The first two walks each produced a
    complete trace and lost it to a reply that did not come back; the analysis
    must not be reachable only through the code path that failed.
    """
    if not log:
        print("NO SAMPLES — could not look.")
        return 1

    # DISTANCE COMES FROM THE TRACE WHEN THE REPLY DID NOT CARRY IT.
    # The stop payload's reply is the fragile part of this tool -- it has now
    # lost its marker on three separate completed walks -- and dist_m then
    # arrives as 0.0. On 2026-08-16 that printed "distance 0.0 m of 1000" and
    # "DID NOT COVER THE DISTANCE ... that is not a pass" over a walk whose own
    # trace log, in the same artefact, ended at cumulative 99,917.6 cm.
    #
    # A FALSE NEGATIVE IS NOT THE SAFE DIRECTION HERE. The tool already knows
    # to read the trace off disk when the reply is lost; it simply was not
    # reading the one field the verdict depends on. The trace's own cumulative
    # column is the same measurement the reply would have carried.
    if not dist_m and len(log[0]) > 6:
        dist_m = float(log[-1][6]) / 100.0
        print("  (distance recovered from the trace: the reply did not carry it)")

    spawn_z = log[0][3]
    min_z = min(r[3] for r in log)

    # THE FALL TEST IS GEOMETRIC, NOT "DID Z GO DOWN".
    # The first version called it a fall when Z dropped more than N below the
    # spawn, and reported FELL THROUGH on a walk that descended a mountainside
    # 100 m over 1 km with is_falling never once true. On real terrain,
    # descending IS the job.
    #
    # A walk cannot descend faster than the walkable slope allows: over one
    # sample the ground can drop at most tan(walkable) x horizontal distance
    # moved. Anything far beyond that is not being walked down, it is being
    # fallen down.
    walk_tan = math.tan(math.radians(args.walkable_deg))
    worst_excess, excess_run, worst_run = 0.0, 0.0, 0.0
    for i in range(1, len(log)):
        dz = log[i][3] - log[i - 1][3]
        dxy = math.hypot(log[i][1] - log[i - 1][1], log[i][2] - log[i - 1][2])
        allowed = walk_tan * dxy + args.fall_margin_cm
        excess = (-dz) - allowed
        if excess > 0:
            excess_run += log[i][0] - log[i - 1][0]
            worst_run = max(worst_run, excess_run)
            worst_excess = max(worst_excess, excess)
        else:
            excess_run = 0.0
    fell = worst_run >= args.fall_window

    # is_falling is the CORROBORATING instrument -- a different representation
    # from the geometry. None everywhere means the accessor failed, and that
    # is reported as such rather than as zero.
    flags = [r[5] for r in log]
    readable = [f for f in flags if f is not None]
    falling_frac = (sum(1 for f in readable if f) / float(len(readable))
                    if readable else None)

    # A stall is a RUN of consecutive low-speed samples, not a low average --
    # an average is diluted by the rest of the walk and would hide exactly the
    # localised obstruction this is looking for.
    worst_stall, run = 0.0, 0.0
    for i, r in enumerate(log):
        if r[4] < args.stall_speed:
            run += log[i][0] - (log[i - 1][0] if i else 0.0)
            worst_stall = max(worst_stall, run)
        else:
            run = 0.0
    stalled = worst_stall >= args.stall_window

    print("")
    print("=== RESULT ===")
    print("  distance         %.1f m of %.0f requested" % (dist_m, args.metres))
    print("  samples          %d over %.1f s" % (len(log), log[-1][0]))
    print("  spawn Z          %.1f cm" % spawn_z)
    print("  lowest Z         %.1f cm  (%.1f below spawn — DESCENT, which on"
          % (min_z, spawn_z - min_z))
    print("                   a mountainside is the job, not a defect)")
    print("  descent beyond   worst %.1f cm in one sample, longest run %.2f s"
          % (worst_excess, worst_run))
    print("  what %.1f deg allows   (bar: %.1f s continuous)"
          % (args.walkable_deg, args.fall_window))
    if falling_frac is None:
        print("  is_falling       COULD NOT READ on any sample — the")
        print("                   corroborating instrument is ABSENT, not zero")
    else:
        print("  is_falling       %.1f%% of %d readable samples"
              % (100.0 * falling_frac, len(readable)))
    print("  longest stop     %.2f s  (stall bar %.1f s at <%.0f cm/s)"
          % (worst_stall, args.stall_window, args.stall_speed))
    # ACHIEVED SPEED, from the trace rather than from the property that was
    # written. The property read-back proves the value LANDED on the
    # component; only the trace proves the character MOVED at it -- a pawn can
    # be capped by acceleration, by slope, or by an animation root motion that
    # never got the memo, and every one of those would leave the property
    # reading 1800 over a walk at 600.
    moving = [r[4] for r in log if r[4] >= args.stall_speed]
    ach_p50 = sorted(moving)[len(moving) // 2] if moving else None
    ach_max = max(moving) if moving else None
    print("")
    print("  achieved speed   p50 %s, max %s cm/s over %d moving samples"
          % ("--" if ach_p50 is None else "%.0f" % ach_p50,
             "--" if ach_max is None else "%.0f" % ach_max, len(moving)))
    if args.speed_cm_s is not None and ach_max is not None:
        frac = ach_max / float(args.speed_cm_s)
        print("                   = %.2f of the %.0f commanded  %s"
              % (frac, args.speed_cm_s,
                 "OK" if frac >= 0.9 else "!! THE PAWN NEVER REACHED IT"))

    # RESIDENCY. The editor figure on the board (14.65 GB, every region held)
    # is an UPPER BOUND taken with streaming defeated. This is the opposite
    # end: what World Partition actually keeps resident around a moving pawn.
    if res:
        lp = [r[1] for r in res]
        fa = [r[2] for r in res]
        print("")
        print("  resident proxies   min %d  p50 %d  MAX %d   over %d samples"
              % (min(lp), sorted(lp)[len(lp) // 2], max(lp), len(res)))
        print("  foliage actors     min %d  p50 %d  MAX %d"
              % (min(fa), sorted(fa)[len(fa) // 2], max(fa)))
    elif res_why:
        print("")
        print("  residency        COULD NOT READ: %s" % res_why)
    elif args.residency_every > 0:
        print("")
        print("  residency        NO SAMPLES — not measured, not zero")

    print("")
    print("  FELL THROUGH     %s" % ("YES" if fell else "no"))
    print("  STALLED          %s" % ("YES" if stalled else "no"))

    os.makedirs(VERIFY_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    path = os.path.join(VERIFY_DIR, "%s_unit5_walk_%s.md" % (stamp, args.tag))
    L = ["# Unit 5 — the 1 km walk, tag `%s`" % args.tag, "",
         "**Class: PLAY IN EDITOR.** The character is driven by a per-tick",
         "`AddMovementInput`, so CharacterMovementComponent does real floor",
         "checks and real step-ups. This is a STRAIGHT LINE on heading",
         "%.1f deg, **not** the inter-massif corridor — that corridor has no" % args.yaw,
         "spatial definition in this repo (`WORLD_VISION.md:304` is prose).", "",
         "| | |", "|---|---|",
         "| distance | %.1f m of %.0f requested |" % (dist_m, args.metres),
         "| samples | %d over %.1f s |" % (len(log), log[-1][0]),
         "| spawn Z | %.1f cm |" % spawn_z,
         "| lowest Z | %.1f cm (%.1f below spawn) |" % (min_z, spawn_z - min_z),
         "| descent beyond what %.1f deg allows | worst %.1f cm in a sample, "
         "longest run %.2f s |" % (args.walkable_deg, worst_excess, worst_run),
         "| is_falling | %s |"
         % ("**COULD NOT READ on any sample** — absent, not zero"
            if falling_frac is None
            else "%.1f%% of %d readable samples"
                 % (100.0 * falling_frac, len(readable))),
         "| longest stop | %.2f s |" % worst_stall,
         "| **fell through** | **%s** |" % ("YES" if fell else "no"),
         "| **stalled** | **%s** |" % ("YES" if stalled else "no"),
         "| commanded speed | %s |"
         % ("not overridden (the recipe's value)" if args.speed_cm_s is None
            else "%.0f cm/s" % args.speed_cm_s),
         "| achieved speed | %s |"
         % ("no moving samples" if ach_max is None
            else "p50 %.0f, max %.0f cm/s" % (ach_p50, ach_max)),
         "| resident landscape proxies | %s |"
         % ("COULD NOT READ: %s" % res_why if (not res and res_why)
            else ("NOT MEASURED" if not res
                  else "min %d, p50 %d, max %d"
                       % (min(r[1] for r in res),
                          sorted(r[1] for r in res)[len(res) // 2],
                          max(r[1] for r in res)))),
         "| resident foliage actors | %s |"
         % ("--" if not res
            else "min %d, p50 %d, max %d"
                 % (min(r[2] for r in res),
                    sorted(r[2] for r in res)[len(res) // 2],
                    max(r[2] for r in res))), "",
         "**Residency here is what World Partition STREAMS around a moving",
         "pawn.** It is not comparable to the editor's 14.65 GB figure, which",
         "was taken with every region force-resident — streaming defeated on",
         "purpose. Two calibration classes, opposite ends.", "",
         "## Trace log", "",
         "`t_s, x_cm, y_cm, z_cm, speed_cm_s, is_falling, cumulative_cm`", "",
         "```"]
    L += [", ".join(str(v) for v in r) for r in log]
    L += ["```", ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("")
    print("ARTEFACT: %s" % path)

    if fell:
        return 4
    if stalled:
        return 5
    if dist_m < args.metres * 0.95:
        print("")
        print("  DID NOT COVER THE DISTANCE in the time budget. That is not a")
        print("  pass: it may be a stall too brief for the window, or a speed")
        print("  lower than expected.")
        return 7
    return 0


if __name__ == "__main__":
    sys.exit(main())
