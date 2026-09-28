"""probe_pie.py — can this project drive PIE from Python, and what spawns?

READ-ONLY with respect to the world. It starts Play In Editor, reads what the
running game world contains, and ends play. It spawns nothing of its own, saves
nothing, and mutates no asset. PIE runs against a DUPLICATE world, so ending
play discards everything it touched.

=====================================================================
WHY A PROBE AND NOT THE INSTRUMENT
=====================================================================
PHASE2_PLAN.md unit 1 wants a PIE frame-cost capture, and the whole design of
that instrument rests on one unverified premise:

    that Python remote execution still answers while PIE is running.

Remote exec is serviced on the editor tick. Whether it keeps being serviced
once a game world is ticking in front of it is NOT recorded anywhere in this
project, and no PIE frame has ever been produced here at all. If it does not
answer, an instrument built on it does not fail loudly -- it hangs, exactly as
the 2026-08-10 capture did when a second client stole the connection, with the
process alive and no output for fifteen minutes.

So this asks the question directly, in isolation, before anything is built on
the answer. That is step (d)'s "test the improvement in isolation first"
applied to a premise rather than to a change.

=====================================================================
WHAT IT ESTABLISHES, AND WHY EACH ONE IS NEEDED
=====================================================================
1. Does remote exec answer during PIE?          -> the instrument is viable
2. Is there a PlayerStart in this level?        -> where the pawn appears
3. What pawn class actually spawns?             -> DefaultPawn vs a Character;
                                                   these have different costs
                                                   and different collision
4. Where does it spawn, in world coordinates?   -> whether it is on the terrain
                                                   or at the origin, 1552 m
                                                   below the summit
5. What is the viewport pixel size?             -> the denominator of every GPU
                                                   number this project owns,
                                                   which measure_frame_cost
                                                   does not record (its own
                                                   docstring, line 38)

=====================================================================
FAIL CLOSED
=====================================================================
A bare invocation READS ONLY and does not start PIE. Starting a game world is
the side-effecting half, so it needs --go. An unreadable value is reported as
"could not look" and never as a zero or a False: non-negotiable 6.

Exit codes:
  0  probed; findings printed
  1  could not look (no marker, unparseable reply)
  2  bad arguments
  3  rule 7: no verified editor node
  5  --go given but PIE did not start
  6  PIE STARTED AND DID NOT END -- the editor needs attention
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_PIE__"


# ----------------------------------------------------------------------------
# Payload 1 -- read the editor world BEFORE any play request.
# ----------------------------------------------------------------------------
PAYLOAD_PRE = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "player_starts": [], "viewport_size": None,
        "in_play": None, "level": None, "game_mode": None}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _w = _ues.get_editor_world()
    _out["level"] = _w.get_outer().get_path_name()

    # is_in_play_in_editor is on LevelEditorSubsystem (PythonStub 606054).
    # Read it BEFORE requesting play so a stale PIE session is caught here
    # rather than misread later as our own.
    _out["in_play"] = bool(_les.is_in_play_in_editor())

    # get_level_viewport_size returns Optional[IntPoint] (PythonStub 643569).
    # None means "could not look" and is reported as such, never as 0x0.
    _vp = _ues.get_level_viewport_size()
    if _vp is not None:
        _out["viewport_size"] = [int(_vp.x), int(_vp.y)]

    # Where will the pawn appear? A level with no PlayerStart does not put the
    # pawn where the editor camera is -- that is "Play From Here", a different
    # entry point. Count them and record their positions.
    for _a in _unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(_a, _unreal.PlayerStart):
            _l = _a.get_actor_location()
            _out["player_starts"].append({
                "label": str(_a.get_actor_label()),
                "loc_cm": [float(_l.x), float(_l.y), float(_l.z)]})

    # The GameMode that PIE will use. DefaultEngine.ini sets GameDefaultMap and
    # PHASE2_PLAN.md item 1 records that GlobalDefaultGameMode is NOT set, so
    # the expected answer is the engine default. Read it rather than assume it:
    # a config file records an override, never what is in effect (rule 17).
    try:
        _out["game_mode"] = str(_w.get_world_settings().get_editor_property(
            "default_game_mode"))
    except Exception as _ge:
        _out["game_mode"] = "COULD NOT READ: " + type(_ge).__name__ + ": " + str(_ge)
    del _w
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


# ----------------------------------------------------------------------------
# Payload 2 -- request play. This RETURNS BEFORE PIE EXISTS.
# editor_request_begin_play is a REQUEST (PythonStub 606201): the editor starts
# the session on a later tick. Anything read in this same payload would be read
# from the editor world and would look like a failure.
# ----------------------------------------------------------------------------
PAYLOAD_BEGIN = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "requested": False}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _les.editor_request_begin_play()
    _out["requested"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


# ----------------------------------------------------------------------------
# Payload 3 -- THE ACTUAL QUESTION. If this reply arrives at all, remote exec
# answers during PIE and the unit-1 instrument is viable.
# ----------------------------------------------------------------------------
PAYLOAD_IN_PLAY = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None, "game_world": None,
        "pawn_class": None, "pawn_loc_cm": None, "controller_class": None,
        "viewport_size": None, "streaming_note": None, "landscape_actors": 0,
        "foliage_actors": 0}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _out["in_play"] = bool(_les.is_in_play_in_editor())

    # get_game_world returns the PIE world while playing (PythonStub 643594).
    # It is a DIFFERENT object from get_editor_world -- asking the editor world
    # about the pawn would answer "absent" correctly and uselessly.
    _gw = _ues.get_game_world()
    _out["game_world"] = _gw.get_outer().get_path_name() if _gw is not None else None

    if _gw is not None:
        _pc = _unreal.GameplayStatics.get_player_controller(_gw, 0)
        _out["controller_class"] = _pc.get_class().get_name() if _pc is not None else None
        _pawn = _unreal.GameplayStatics.get_player_pawn(_gw, 0)
        if _pawn is not None:
            _out["pawn_class"] = _pawn.get_class().get_name()
            _pl = _pawn.get_actor_location()
            _out["pawn_loc_cm"] = [float(_pl.x), float(_pl.y), float(_pl.z)]

        # How much world is actually resident in the PIE session. Streaming is
        # LIVE here by design -- unit 1 measures the streamed state, not the
        # force-resident one every editor figure on the board was taken in.
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(
                _gw, _unreal.LandscapeStreamingProxy):
            _out["landscape_actors"] += 1
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(
                _gw, _unreal.InstancedFoliageActor):
            _out["foliage_actors"] += 1

    _vp = _ues.get_level_viewport_size()
    if _vp is not None:
        _out["viewport_size"] = [int(_vp.x), int(_vp.y)]
    del _gw
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


# ----------------------------------------------------------------------------
# Payload 4 -- end play, then CONFIRM it ended. A request that returns is not
# a session that stopped.
# ----------------------------------------------------------------------------
PAYLOAD_END = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "requested": False}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _les.editor_request_end_play()
    _out["requested"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


PAYLOAD_CONFIRM_ENDED = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _out["in_play"] = bool(_les.is_in_play_in_editor())
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PIE__" + _json.dumps(_out))
'''


def _run(remote, remote_exec, payload, label):
    """Send one payload. Returns (parsed_dict_or_None, raw_text)."""
    r = remote.run_command(payload, unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    text = bootstrap._collect_output(r)
    i = text.find(MARKER)
    if i < 0:
        return None, text
    d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    return d, text


def _free_ram_gb():
    """Free physical RAM in GB, or None if it could not be read.

    None is 'could not look'. Pipeline rule 5 wants this logged before a heavy
    operation; reporting an unreadable value as 0.0 would refuse every run.
    """
    try:
        import subprocess
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out) / 1048576.0 if out else None
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true",
                    help="actually start PIE. Without it this reads only.")
    ap.add_argument("--settle", type=float, default=25.0,
                    help="seconds to let PIE start and stream before probing")
    ap.add_argument("--end-settle", type=float, default=10.0,
                    help="seconds to let PIE tear down before confirming")
    args = ap.parse_args(argv)

    if args.settle < 5.0:
        print("REFUSE: --settle %.1f is too short for a world this size to "
              "start a game instance." % args.settle)
        return 2

    ram = _free_ram_gb()
    print("free RAM before: %s"
          % ("COULD NOT READ" if ram is None else "%.2f GB" % ram))

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

        # -------- 1. before ------------------------------------------------
        d, raw = _run(remote, remote_exec, PAYLOAD_PRE, "pre")
        if d is None:
            print("NO MARKER on the pre-play read — could not look.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("PRE ERROR:", d["error"])
            return 1

        print("")
        print("=== BEFORE PLAY ===")
        print("  level            %s" % d.get("level"))
        print("  already in play  %s" % d.get("in_play"))
        print("  viewport size    %s"
              % (d["viewport_size"] if d.get("viewport_size")
                 else "COULD NOT READ"))
        print("  default GameMode %s" % d.get("game_mode"))
        ps = d.get("player_starts") or []
        print("  PlayerStart      %d found" % len(ps))
        for p in ps:
            print("                   %-24s at %s" % (p["label"], p["loc_cm"]))
        if not ps:
            print("                   NONE. The pawn will NOT appear at the")
            print("                   editor camera — that is 'Play From Here',")
            print("                   a different entry point. Expect the origin.")

        if d.get("in_play"):
            print("")
            print("REFUSE: the editor is ALREADY in play. This probe will not")
            print("        adopt a session it did not start — it could not tell")
            print("        its own teardown from someone else's.")
            return 2

        if not args.go:
            print("")
            print("DRY RUN — PIE was NOT started. Re-run with --go.")
            return 0

        # -------- 2. begin -------------------------------------------------
        print("")
        print("=== REQUESTING PLAY ===")
        d, raw = _run(remote, remote_exec, PAYLOAD_BEGIN, "begin")
        if d is None:
            print("NO MARKER on the begin request — could not look.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("BEGIN ERROR:", d["error"])
            return 5
        started = True
        print("  requested. Waiting %.0f s for the game world to exist and "
              "stream." % args.settle)
        time.sleep(args.settle)

        # -------- 3. THE QUESTION -----------------------------------------
        print("")
        print("=== DURING PLAY ===")
        t0 = time.time()
        d, raw = _run(remote, remote_exec, PAYLOAD_IN_PLAY, "in_play")
        rtt = time.time() - t0
        if d is None:
            print("  NO MARKER while PIE was running, after %.1f s." % rtt)
            print("  This is the finding: remote exec did NOT answer during")
            print("  PIE, and an instrument built on it would hang rather than")
            print("  fail. Ending play before anything else.")
            print(raw[:2000])
        else:
            print("  remote exec ANSWERED during PIE, round trip %.1f s." % rtt)
            if d.get("error"):
                print("  payload error:", d["error"])
            print("  in play          %s" % d.get("in_play"))
            print("  game world       %s" % d.get("game_world"))
            print("  controller       %s" % d.get("controller_class"))
            print("  pawn class       %s" % d.get("pawn_class"))
            print("  pawn location    %s cm" % d.get("pawn_loc_cm"))
            print("  viewport size    %s"
                  % (d["viewport_size"] if d.get("viewport_size")
                     else "COULD NOT READ"))
            print("  landscape proxies resident  %s" % d.get("landscape_actors"))
            print("  foliage actors resident     %s" % d.get("foliage_actors"))
            print("")
            print("  NOTE: proxy and foliage counts here are the STREAMED")
            print("  state, which is the point. Every frame-cost figure this")
            print("  project owns was taken with 256 proxies force-resident.")

        ram2 = _free_ram_gb()
        print("  free RAM in play %s"
              % ("COULD NOT READ" if ram2 is None else "%.2f GB" % ram2))

        # -------- 4. end ---------------------------------------------------
        print("")
        print("=== ENDING PLAY ===")
        d2, raw2 = _run(remote, remote_exec, PAYLOAD_END, "end")
        if d2 is None:
            print("  NO MARKER on the end request.")
        elif d2.get("error"):
            print("  END ERROR:", d2["error"])
        else:
            print("  requested. Waiting %.0f s for teardown." % args.end_settle)
        time.sleep(args.end_settle)

        d3, raw3 = _run(remote, remote_exec, PAYLOAD_CONFIRM_ENDED, "confirm")
        if d3 is None:
            print("  COULD NOT CONFIRM the session ended — no marker.")
            print("  Treat the editor as still in play and check it by hand.")
            return 6
        if d3.get("in_play"):
            print("  STILL IN PLAY after the end request.")
            print("  Press Escape in the editor. Do not run another capture")
            print("  until is_in_play_in_editor reads False.")
            return 6
        started = False
        print("  confirmed ended: is_in_play_in_editor reads False.")
        print("")
        print("The world on disk is untouched — PIE runs against a duplicate.")
        return 0

    finally:
        if started:
            print("")
            print("WARNING: leaving with PIE possibly still running.")
        try:
            remote.stop()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
