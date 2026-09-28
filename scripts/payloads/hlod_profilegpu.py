import os
import unreal as _u

# HLOD SHARE PASS -- issue a ProfileGPU at a station camera. The RealtimeGPU
# profiler dumps a per-pass hierarchy to the editor log on the NEXT rendered
# frame; a companion grep reads it. STATION is substituted by ue_exec --set.
# Sets the viewport camera and requests one GPU profile. Mutates only the
# viewport camera (transient, restored by the next set); saves nothing.
_ST = {
    "treeline": ((-190000.0, 100000.0, 63367.4), (-2.0, 105.0, 0.0)),
    "plaza": ((-210800.0, 278800.0, 18847.2), (-2.0, -12.8, 0.0)),
    "vista": ((-216400.0, 63600.0, 76426.2), (-4.0, 60.0, 0.0)),
}
_name = "__STATION__"
_loc, _rot = _ST[_name]
_ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
_ues.set_level_viewport_camera_info(
    _u.Vector(_loc[0], _loc[1], _loc[2]),
    _u.Rotator(_rot[0], _rot[1], _rot[2]))
_w = _ues.get_editor_world()
# tag the log so the grep can find THIS profile, then request it.
_u.SystemLibrary.execute_console_command(_w, "ProfileGPU")
print("PROFILEGPU_REQUESTED station=%s loc=%s" % (_name, _loc))
