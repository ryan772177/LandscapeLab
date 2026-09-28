import unreal as _u

# HLOD SHARE PASS -- steady editor GPU window. ACTION=start sets the vista
# camera and begins a CsvProfile capture; ACTION=stop ends it. A steady window
# averages out the single-frame ProfileGPU noise (measured +/-3.7 ms). Editor
# GPU != -game absolute; the with/without-HLOD DELTA is the share. ACTION is
# substituted by ue_exec --set.
_ACTION = "__ACTION__"
_ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
_w = _ues.get_editor_world()
if _ACTION == "start":
    _ues.set_level_viewport_camera_info(
        _u.Vector(-216400.0, 63600.0, 76426.2), _u.Rotator(-4.0, 60.0, 0.0))
    _u.SystemLibrary.execute_console_command(_w, "CsvProfile start")
    print("CSV_START vista")
else:
    _u.SystemLibrary.execute_console_command(_w, "CsvProfile stop")
    print("CSV_STOP")
