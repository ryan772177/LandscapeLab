"""_t6_navmod_probe.py -- Brief-4 T6: establish the 5.8 nav-modifier surface
BEFORE writing the carve payload (ue-api-resolution: the reflected surface is
the contract). READ-ONLY: spawns nothing, mutates nothing. Prints what exists.

Questions it answers:
  1. Does unreal.NavModifierVolume exist as a spawnable class? Its properties?
  2. Does unreal.NavArea_Null exist (the area class that marks non-walkable)?
  3. How is the area class set on the volume (property name + type)?
  4. Is there a NavModifierComponent alternative?
  5. The volume's brush/box shape API (set_actor_scale / brush builder).
"""
import json
import unreal

_out = {"ok": False}
try:
    def _has(name):
        return hasattr(unreal, name)

    def _props(cls_name):
        c = getattr(unreal, cls_name, None)
        if c is None:
            return None
        names = [n for n in dir(c)]
        # editor properties are the reflected settables; filter to likely ones
        keys = [n for n in names if not n.startswith("__")
                and n.islower() and "_" in n or n.islower()]
        return sorted(set(keys))

    _out["NavModifierVolume_exists"] = _has("NavModifierVolume")
    _out["NavModifierComponent_exists"] = _has("NavModifierComponent")
    _out["NavArea_Null_exists"] = _has("NavArea_Null")
    _out["NavArea_Obstacle_exists"] = _has("NavArea_Obstacle")

    # Property surface of NavModifierVolume, focused on area-class + shape.
    nmv = getattr(unreal, "NavModifierVolume", None)
    if nmv is not None:
        alln = [n for n in dir(nmv) if not n.startswith("_")]
        _out["NavModifierVolume_area_props"] = [
            n for n in alln if "area" in n.lower() or "class" in n.lower()]
        _out["NavModifierVolume_shape_props"] = [
            n for n in alln if any(k in n.lower() for k in
                                   ("brush", "box", "bound", "extent", "shape"))]
        _out["NavModifierVolume_all_lower"] = [
            n for n in alln if n.islower()][:60]

    nmc = getattr(unreal, "NavModifierComponent", None)
    if nmc is not None:
        allc = [n for n in dir(nmc) if not n.startswith("_")]
        _out["NavModifierComponent_area_props"] = [
            n for n in allc if "area" in n.lower() or "class" in n.lower()]
        _out["NavModifierComponent_shape_props"] = [
            n for n in allc if any(k in n.lower() for k in
                                   ("box", "extent", "shape", "bound"))]

    # How does a similar existing volume (nav bounds) get built? Confirm the
    # BrushBuilder / cube approach the spawn path will need.
    _out["CubeBuilder_exists"] = _has("CubeBuilder")
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)

print("__T6_NAVMOD_PROBE__" + json.dumps(_out))
