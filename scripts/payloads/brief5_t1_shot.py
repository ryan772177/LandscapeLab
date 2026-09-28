"""brief5_t1_shot.py -- Brief 5 T1 still capture. READ-ONLY (no spawn, no save).

Reads a scratch config {force_lod, name} + the ring_station camera, sets the
editor viewport there, game-view on / viewmode lit, forces r.ForceLOD (clamped
per mesh: ForceLOD 4 -> both card species show their CARD; ForceLOD 2 -> geometry),
reads it back, and schedules a HighResShot. The shot completes over subsequent
editor ticks (the driver waits, then reads the PNG). Nothing is saved to disk
except the screenshot.
"""
import json
import os
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
CFG = json.load(open(os.path.join(root, "_scratch_t1shot.json"), encoding="utf-8"))
FORCE_LOD = int(CFG["force_lod"])
NAME = CFG["name"]
STATION = CFG.get("station", "ring_station")

out = {"ok": False, "force_lod": FORCE_LOD, "name": NAME}
try:
    fs = json.load(open(os.path.join(root, "research", "brief5", "input",
                                     STATION + ".json"), encoding="utf-8"))
    c = fs["camera"]
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    w = ues.get_editor_world()
    loc = unreal.Vector(float(c["x_cm"]), float(c["y_cm"]), float(c["z_cm"]))
    rot = unreal.Rotator(roll=0.0, pitch=float(c["pitch_deg"]),
                         yaw=float(c["yaw_deg"]))
    ues.set_level_viewport_camera_info(loc, rot)
    out["camera_set"] = [c["x_cm"], c["y_cm"], c["z_cm"], c["pitch_deg"], c["yaw_deg"]]
    try:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        les.editor_set_game_view(True)
        out["game_view"] = bool(les.editor_get_game_view())
    except Exception as e:
        out["game_view_error"] = str(e)
    try:
        eas.set_selected_level_actors([])
    except Exception:
        pass
    unreal.SystemLibrary.execute_console_command(w, "viewmode lit")
    unreal.SystemLibrary.execute_console_command(w, "r.ForceLOD %d" % FORCE_LOD)
    try:
        out["force_lod_readback"] = int(
            unreal.SystemLibrary.get_console_variable_int_value("r.ForceLOD"))
    except Exception as e:
        out["force_lod_readback"] = "err: %s" % e
    out["force_lod_ok"] = out.get("force_lod_readback") == FORCE_LOD
    # schedule the shot (completes over subsequent ticks)
    unreal.AutomationLibrary.take_high_res_screenshot(3840, 2160, NAME)
    out["shot_scheduled"] = NAME
    out["ok"] = out["force_lod_ok"]
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1200:]
print("__LL__" + json.dumps(out, default=str))
