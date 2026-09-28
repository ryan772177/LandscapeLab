"""d4_still.py -- Brief 5 D4 Task 2 reference still. READ-ONLY (no spawn, no save).

Reads _scratch_d4still.json {camera{x_cm,y_cm,z_cm,pitch_deg,yaw_deg}, name},
sets the editor viewport there, game-view on / viewmode lit (no r.ForceLOD -- a
beauty frame of the dense world as shipped), and schedules a 4K HighResShot. The
shot completes over subsequent ticks; the driver polls for the PNG.
"""
import json
import os
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
CFG = json.load(open(os.path.join(root, "_scratch_d4still.json"), encoding="utf-8"))
c = CFG["camera"]
NAME = CFG["name"]

out = {"ok": False, "name": NAME}
try:
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    w = ues.get_editor_world()
    loc = unreal.Vector(float(c["x_cm"]), float(c["y_cm"]), float(c["z_cm"]))
    rot = unreal.Rotator(roll=0.0, pitch=float(c["pitch_deg"]),
                         yaw=float(c["yaw_deg"]))
    ues.set_level_viewport_camera_info(loc, rot)
    gl, gr = ues.get_level_viewport_camera_info()
    out["camera_set"] = [round(gl.x, 1), round(gl.y, 1), round(gl.z, 1),
                         round(gr.pitch, 2), round(gr.yaw, 2)]
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
    unreal.AutomationLibrary.take_high_res_screenshot(3840, 2160, NAME)
    out["shot_scheduled"] = NAME
    out["ok"] = True
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1200:]
print("__LL__" + json.dumps(out, default=str))
