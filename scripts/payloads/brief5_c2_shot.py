"""brief5_c2_shot.py -- Brief 5 C2 ONE still. READ-ONLY, one HighResShot per
invocation (HighResShot mutates a single global config and the viewport camera /
r.ForceLOD are shared state, so multiple shots per exec would all render the last
camera -- F1). Reads _scratch_c2shot.json {dist_m, force_card, out_name,
expected_level}; reads the target cluster from research/brief5/input/
c2_showroom.json (written by brief5_c2_discover.py). Places the camera dist_m
south of the target at trunk-mid height, looks at it, viewmode lit, sets
r.ForceLOD/foliage.ForceLOD (8=force last/imposter, -1=auto), reads back FOV +
ForceLOD, schedules the shot.
"""
import json
import math
import os
import unreal

root = os.path.dirname(os.path.normpath(unreal.Paths.project_dir().rstrip("/\\")))
CFG = json.load(open(os.path.join(root, "_scratch_c2shot.json"), encoding="utf-8"))
DIST_M = float(CFG["dist_m"])
FORCE_CARD = bool(CFG["force_card"])
OUT = CFG["out_name"]
EXPECT_LEVEL = CFG.get("expected_level", "Showroom")

out = {"ok": False, "out_name": OUT, "dist_m": DIST_M, "force_card": FORCE_CARD}
try:
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    w = ues.get_editor_world()
    out["level"] = w.get_name()
    if EXPECT_LEVEL.lower() not in out["level"].lower():
        out["error"] = "WRONG LEVEL: expected %r, editor has %r (rule 11)" % (
            EXPECT_LEVEL, out["level"])
        raise SystemExit

    disc = json.load(open(os.path.join(root, "research", "brief5", "input",
                                       "c2_showroom.json"), encoding="utf-8"))
    tgt = disc.get("target_cm")
    if not tgt:
        out["error"] = "no target_cm in c2_showroom.json (discovery found no instances)"
        raise SystemExit
    cx, cy, cz = float(tgt[0]), float(tgt[1]), float(tgt[2])
    d = DIST_M * 100.0
    eye = unreal.Vector(cx - d, cy, cz + 800.0)
    look = unreal.Vector(cx - eye.x, cy - eye.y, (cz + 800.0) - eye.z)
    yaw = math.degrees(math.atan2(look.y, look.x))
    pitch = math.degrees(math.atan2(look.z, math.hypot(look.x, look.y)))
    ues.set_level_viewport_camera_info(
        eye, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))
    les.editor_set_game_view(True)
    unreal.SystemLibrary.execute_console_command(w, "viewmode lit")
    fl = 8 if FORCE_CARD else -1
    unreal.SystemLibrary.execute_console_command(w, "r.ForceLOD %d" % fl)
    unreal.SystemLibrary.execute_console_command(w, "foliage.ForceLOD %d" % fl)
    try:
        rl, rr = ues.get_level_viewport_camera_info()
        out["camera_readback"] = [round(rl.x, 1), round(rl.y, 1), round(rl.z, 1),
                                  round(rr.pitch, 2), round(rr.yaw, 2)]
    except Exception as e:
        out["camera_readback"] = "err: %s" % e
    try:
        key = les.get_active_viewport_config_key()
        r = les.get_level_viewport_fov(key)
        if isinstance(r, (tuple, list)):
            out["fov_readback"] = round(float(
                [x for x in r if isinstance(x, float)][-1]), 3)
        else:
            out["fov_readback"] = round(float(r), 3)
    except Exception as e:
        out["fov_readback"] = "err: %s" % e
    out["force_lod_readback"] = int(
        unreal.SystemLibrary.get_console_variable_int_value("r.ForceLOD"))
    unreal.AutomationLibrary.take_high_res_screenshot(3840, 2160, OUT)
    out["shot_scheduled"] = OUT
    out["ok"] = True
    dest = os.path.join(root, "research", "brief5", "input", "c2_shot_%s.json" % OUT)
    json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, default=str)
except SystemExit:
    pass
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1200:]
print("__LL__" + json.dumps(out, default=str))
