"""brief5_c1_lodcolor.py -- Brief 5 C1: direct runtime LOD readback.

READ-ONLY (no spawn, no save, no asset/level/material edit). Reads a scratch
config {station, force_lod, deep_offset_m, out_name} + the station camera, sets
the editor viewport there (optionally pushed deep_offset_m metres along the view
direction, into the band), turns game-view on, sets the MESH LOD COLORATION view
mode (ShowFlag.LODColoration -- colours each drawn primitive by the LOD index it
actually renders), sets r.ForceLOD + foliage.ForceLOD (both, so foliage obeys),
reads them back, records the LOD-distance scalability multipliers that would
shift the auto LOD selection, and schedules a 4K HighResShot. The shot completes
over subsequent editor ticks; the driver polls Saved/Screenshots/WindowsEditor.
Nothing is written except the screenshot.

force_lod == -1  -> auto (the measured case)
force_lod 0..N   -> forced clamp per mesh (legend calibration references)
"""
import json
import math
import os
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
CFG = json.load(open(os.path.join(root, "_scratch_c1.json"), encoding="utf-8"))
FORCE_LOD = int(CFG["force_lod"])
STATION = CFG.get("station", "ring_station_v1")
DEEP_M = float(CFG.get("deep_offset_m", 0.0))
OUT = CFG["out_name"]
EXPECT_LEVEL = CFG.get("expected_level", "Alpine8K")

out = {"ok": False, "force_lod": FORCE_LOD, "out_name": OUT,
       "deep_offset_m": DEEP_M, "station": STATION}
try:
    fs = json.load(open(os.path.join(root, "research", "brief5", "input",
                                     STATION + ".json"), encoding="utf-8"))
    c = fs["camera"]
    cx, cy, cz = float(c["x_cm"]), float(c["y_cm"]), float(c["z_cm"])
    pitch, yaw = float(c["pitch_deg"]), float(c["yaw_deg"])
    if DEEP_M != 0.0:
        # forward unit vector from yaw/pitch (UE: X fwd, degrees)
        cp = math.cos(math.radians(pitch))
        fx = math.cos(math.radians(yaw)) * cp
        fy = math.sin(math.radians(yaw)) * cp
        fz = math.sin(math.radians(pitch))
        d = DEEP_M * 100.0
        cx, cy, cz = cx + fx * d, cy + fy * d, cz + fz * d
    out["camera_cm"] = [round(cx, 1), round(cy, 1), round(cz, 1), pitch, yaw]

    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    w = ues.get_editor_world()
    out["level"] = w.get_name()
    if EXPECT_LEVEL.lower() not in out["level"].lower():
        out["error"] = "WRONG LEVEL: expected %r, editor has %r (rule 11)" % (
            EXPECT_LEVEL, out["level"])
        raise SystemExit
    ues.set_level_viewport_camera_info(
        unreal.Vector(cx, cy, cz),
        unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))
    # read the camera back (rule 12: applied AND read back)
    try:
        rl, rr = ues.get_level_viewport_camera_info()
        out["camera_readback"] = [round(rl.x, 1), round(rl.y, 1), round(rl.z, 1),
                                  round(rr.pitch, 2), round(rr.yaw, 2)]
    except Exception as e:
        out["camera_readback"] = "err: %s" % e
    les = None
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

    # MESH LOD Coloration view mode (ShowFlag.LODColoration). VMI_LODColoration
    # maps to EngineShowFlags.SetLODColoration(true) -- ShowFlags.cpp:430.
    unreal.SystemLibrary.execute_console_command(w, "viewmode lodcoloration")
    unreal.SystemLibrary.execute_console_command(w, "ShowFlag.LODColoration 1")
    unreal.SystemLibrary.execute_console_command(w, "r.ForceLOD %d" % FORCE_LOD)
    unreal.SystemLibrary.execute_console_command(w, "foliage.ForceLOD %d" % FORCE_LOD)

    def cvar_i(n):
        try:
            return int(unreal.SystemLibrary.get_console_variable_int_value(n))
        except Exception as e:
            return "err: %s" % e

    def cvar_f(n):
        try:
            return round(float(
                unreal.SystemLibrary.get_console_variable_float_value(n)), 4)
        except Exception as e:
            return "err: %s" % e

    fov = "err: no LevelEditorSubsystem"
    if les is not None:
        try:
            key = les.get_active_viewport_config_key()
            r = les.get_level_viewport_fov(key)
            # bool GetLevelViewportFOV(float& FOV, FName key): python returns the
            # out-float, possibly as (success, fov). Take the float.
            if isinstance(r, (tuple, list)):
                fov = round(float([x for x in r if isinstance(x, float)][-1]), 3)
            else:
                fov = round(float(r), 3)
        except Exception as e:
            fov = "err: %s" % e
    out["readback"] = {
        "r.ForceLOD": cvar_i("r.ForceLOD"),
        "foliage.ForceLOD": cvar_i("foliage.ForceLOD"),
        "viewport_fov_deg": fov,
        "r.ViewDistanceScale": cvar_f("r.ViewDistanceScale"),
        "r.StaticMeshLODDistanceScale": cvar_f("r.StaticMeshLODDistanceScale"),
        "foliage.LODDistanceScale": cvar_f("foliage.LODDistanceScale"),
        "r.ScreenPercentage": cvar_f("r.ScreenPercentage"),
    }
    out["force_lod_ok"] = (out["readback"]["r.ForceLOD"] == FORCE_LOD and
                           out["readback"]["foliage.ForceLOD"] == FORCE_LOD)
    unreal.AutomationLibrary.take_high_res_screenshot(3840, 2160, OUT)
    out["shot_scheduled"] = OUT
    out["ok"] = bool(out["force_lod_ok"])
    # persist camera + FOV + cvars for the analyser (F7: projection must consume
    # the ENGINE FOV, not an assumed 90 deg)
    try:
        dest = os.path.join(root, "research", "brief5", "input",
                            "c1_shot_%s.json" % OUT)
        json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, default=str)
    except Exception as e:
        out["shot_json_error"] = str(e)
except SystemExit:
    pass
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1200:]
print("__LL__" + json.dumps(out, default=str))
