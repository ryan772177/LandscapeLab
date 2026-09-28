"""capture_hero_pie.py — press play, read what the hero is wearing, photograph him.

This is the proof the whole face effort has been missing. Everything so far is
measured off assets and geometry; nothing has been a GAME FRAME.

Three phases, because PIE needs ticks between them and a single payload cannot
wait for them:

    1. start play
    2. read the pawn's ACTUAL mesh assets, then screenshot
    3. end play

WHAT PHASE 2 CHECKS, AND WHY IT IS NOT THE OBVIOUS THING
    Reading the CDO tells you what the class was configured with. Reading the
    LIVE PAWN tells you what it actually resolved, which is the thing that can
    differ -- a config value that never reached the CDO, an asset that failed
    to load, a mesh silently left at its default. So this reads the spawned
    pawn's CharacterMesh0 and FaceMesh and reports their asset paths and
    vertex counts.

    A vertex count is carried because it discriminates: the sculpted face mesh
    is 33,845 vertices, so a face reporting the archetype's count would mean
    the assembly did not carry the sculpt even though every path looked right.

PIE runs against a DUPLICATE world, so nothing here can damage /Game/Alpine8K.

Exit codes: 0 captured, 1 a phase failed, 3 rule 7.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

START = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "requested": None, "already": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _out["already"] = bool(_les.is_in_play_in_editor())
    if not _out["already"]:
        # editor_request_begin_play, NOT editor_play_simulate. Simulate runs
        # the world with no player: the first attempt here found
        # SpectatorPawn_0 and no skeletal meshes at all, which reads exactly
        # like "the hero did not spawn" and is nothing of the kind.
        _les.editor_request_begin_play()
        _out["requested"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out, default=str))
'''

READ = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "in_play": None, "pawn": None, "components": [],
        "shot": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _out["in_play"] = bool(_les.is_in_play_in_editor())
    _world = _unreal.EditorLevelLibrary.get_game_world()
    # THE PLAYER's pawn, not the first Pawn in the world. Taking the first
    # one found returned the spectator and reported zero skeletal meshes.
    _gw = _unreal.GameplayStatics.get_player_pawn(_world, 0)
    if _gw is None:
        _out["error"] = "no player pawn in the game world"
    else:
        _out["pawn"] = {"name": _gw.get_name(),
                        "class": _gw.get_class().get_name(),
                        "loc": [round(float(_gw.get_actor_location().x), 1),
                                round(float(_gw.get_actor_location().y), 1),
                                round(float(_gw.get_actor_location().z), 1)]}
        for _c in _gw.get_components_by_class(_unreal.SkeletalMeshComponent):
            _rec = {"component": _c.get_name(), "mesh": None, "vertices": None,
                    "visible": None, "materials": None}
            try:
                _sk = _c.get_skeletal_mesh_asset()
                if _sk is not None:
                    _rec["mesh"] = _sk.get_path_name()
                    try:
                        _md = (_unreal.MetaHumanCharacterEditorSubsystem
                               .get_mesh_data_for_conforming(_sk))
                        if _md is not None:
                            _rec["vertices"] = len(_md[0])
                    except Exception:
                        pass
            except Exception as _e:
                _rec["mesh"] = "UNREADABLE: " + str(_e)[:100]
            try:
                _rec["visible"] = bool(_c.is_visible())
                _rec["materials"] = len(_c.get_materials())
            except Exception:
                pass
            # WHERE the mesh is, not just whether it is flagged visible. A
            # component can be visible and 200 m away, or at the world
            # origin, and "visible: true" says nothing about either.
            try:
                _l = _c.get_world_location()
                _rec["world_loc"] = [round(float(_l.x), 1),
                                     round(float(_l.y), 1),
                                     round(float(_l.z), 1)]
            except Exception as _e:
                _rec["world_loc"] = "UNREADABLE: " + str(_e)[:80]
            try:
                _b = _gw.get_actor_bounds(False)
                _out["actor_bounds"] = {
                    "origin": [round(float(_b[0].x), 1), round(float(_b[0].y), 1),
                               round(float(_b[0].z), 1)],
                    "extent": [round(float(_b[1].x), 1), round(float(_b[1].y), 1),
                               round(float(_b[1].z), 1)]}
            except Exception:
                pass
            _out["components"].append(_rec)

    # Where is the camera actually looking? A third-person arm that points
    # the wrong way photographs scenery and looks exactly like a hero who
    # failed to spawn.
    try:
        _pc = _unreal.GameplayStatics.get_player_controller(_world, 0)
        _cm = _pc.player_camera_manager
        _cl = _cm.get_camera_location()
        _cr = _cm.get_camera_rotation()
        _out["camera"] = {
            "loc": [round(float(_cl.x), 1), round(float(_cl.y), 1),
                    round(float(_cl.z), 1)],
            "rot_pitch_yaw_roll": [round(float(_cr.pitch), 1),
                                   round(float(_cr.yaw), 1),
                                   round(float(_cr.roll), 1)]}
        if _out.get("pawn"):
            _p = _out["pawn"]["loc"]
            _out["camera"]["dist_to_pawn"] = round(
                ((_cl.x - _p[0]) ** 2 + (_cl.y - _p[1]) ** 2
                 + (_cl.z - _p[2]) ** 2) ** 0.5, 1)
    except Exception as _e:
        _out["camera"] = "UNREADABLE: " + str(_e)[:120]
    try:
        _unreal.SystemLibrary.execute_console_command(
            _world, "HighResShot 1920x1080 filename=__SHOT__")
        _out["shot"] = "__SHOT__"
    except Exception as _e:
        _out["error"] = (_out["error"] or "") + " | shot: " + str(_e)
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out, default=str))
'''

STOP = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "ended": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    _les.editor_request_end_play()
    _out["ended"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out, default=str))
'''


def phase(name, text, timeout=20.0):
    rc, d, _raw = ue_exec.run(text, stage_name="pie_" + name, timeout=timeout,
                              quiet=True)
    print("--- %s ---" % name)
    if d is None:
        print("  COULD NOT LOOK (no marker).")
        return None
    print(json.dumps(d, indent=2, default=str))
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--settle", type=float, default=30.0)
    ap.add_argument("--shot", default="hero_pie")
    args = ap.parse_args(argv)

    d = phase("start", START)
    if d is None or d.get("error"):
        return 1
    print("waiting %.0f s for the world to stream ..." % args.settle)
    time.sleep(args.settle)

    d2 = phase("read", READ.replace("__SHOT__", args.shot))
    time.sleep(6.0)
    phase("stop", STOP)

    if d2 is None:
        return 1
    print("")
    print("Screenshots land under LandscapeLab/Saved/Screenshots/WindowsEditor/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
