"""_t6_brush_test.py -- Brief-4 T6 FEASIBILITY: can a spawned NavModifierVolume
be sized as a box without CubeBuilder? Spawns ONE test volume, reads its brush
bounds, scales it, reads back, then DELETES it. Refuses off /Game/Alpine8K
(rule 11). Self-cleaning: leaves the world byte-identical.
"""
import json
import unreal

_out = {"ok": False, "stage": "start"}
try:
    _sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    _w = _sub.get_editor_world()
    _wn = _w.get_path_name()
    _out["level"] = _wn
    if "Alpine8K" not in _wn:
        _out["error"] = "refuse: not on Alpine8K (%s)" % _wn
        print("__T6_BRUSH_TEST__" + json.dumps(_out)); raise SystemExit(0)

    _eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _loc = unreal.Vector(0.0, 0.0, 500000.0)   # far above terrain, harmless
    _out["stage"] = "spawn"
    _v = _eas.spawn_actor_from_class(unreal.NavModifierVolume, _loc,
                                     unreal.Rotator(0, 0, 0))
    if _v is None:
        _out["error"] = "spawn returned None"
        print("__T6_BRUSH_TEST__" + json.dumps(_out)); raise SystemExit(0)
    _out["spawned_label"] = _v.get_actor_label()

    def _bounds():
        # get_actor_bounds(only_colliding=False) -> (origin, box_extent)
        o, e = _v.get_actor_bounds(False)
        return [round(e.x, 1), round(e.y, 1), round(e.z, 1)]

    _out["default_extent"] = _bounds()
    _out["default_scale"] = [round(v, 3) for v in
                             (_v.get_actor_scale3d().x,
                              _v.get_actor_scale3d().y,
                              _v.get_actor_scale3d().z)]
    _bc = _v.get_editor_property("brush_component")
    _out["has_brush_component"] = _bc is not None

    # try scaling: 10x in X, 5x in Y, 2x in Z
    _out["stage"] = "scale"
    _v.set_actor_scale3d(unreal.Vector(10.0, 5.0, 2.0))
    _out["scaled_extent"] = _bounds()

    # try setting the area class to NavArea_Null and read back
    _out["stage"] = "area_class"
    _v.set_editor_property("area_class", unreal.NavArea_Null)
    _ac = _v.get_editor_property("area_class")
    _out["area_class_set"] = (_ac is not None
                              and "NavArea_Null" in str(_ac))

    # clean up: delete the test actor
    _out["stage"] = "delete"
    _eas.destroy_actor(_v)
    _out["deleted"] = True
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)

print("__T6_BRUSH_TEST__" + json.dumps(_out))
