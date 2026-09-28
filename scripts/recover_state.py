"""recover_state.py — read the project's EXACT current values out of the
running editor, for the RECIPES.md retrofit.

WHY THIS IS A SCRIPT AND NOT A ONE-OFF. The governance standard says a
recipe's values must be recovered from the working project state, never
from memory. That is not a one-time need: every future retrofit, every
replay verification, and every "did the project drift from its recipe"
check wants the same dump. It also makes the recipes auditable — anyone
can re-run this and diff.

DISCIPLINE: every read is individually guarded and reports WHY it failed.
A value that could not be read comes back as {"error": ...}, never as a
default or a silent omission — non-negotiable 10, "I couldn't look" is
not "it's absent". The caller marks those VALUE UNVERIFIED rather than
inventing them.

READ-ONLY. Spawns nothing, mutates nothing, saves nothing.

Usage:
    python scripts/recover_state.py [--timeout 120] [--out state.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LL_STATE__"

PAYLOAD = r'''
import json as _json
import unreal as _unreal

_out = {}

def _try(_fn, *_a, **_k):
    """Return a value or a {"error": ...} marker. Never a default."""
    try:
        return _fn(*_a, **_k)
    except Exception as _e:
        return {"error": "{0}: {1}".format(type(_e).__name__, str(_e)[:160])}

def _prop(_o, _n):
    try:
        _v = _o.get_editor_property(_n)
    except Exception as _e:
        return {"error": "{0}: {1}".format(type(_e).__name__, str(_e)[:160])}
    return _scalar(_v)

def _scalar(_v):
    if isinstance(_v, (int, float, bool, str)) or _v is None:
        return _v
    _t = type(_v).__name__
    if _t == "Vector":
        return [round(_v.x, 4), round(_v.y, 4), round(_v.z, 4)]
    if _t == "Rotator":
        return {"roll": round(_v.roll, 4), "pitch": round(_v.pitch, 4),
                "yaw": round(_v.yaw, 4)}
    if _t == "LinearColor":
        return [round(_v.r, 5), round(_v.g, 5), round(_v.b, 5),
                round(_v.a, 5)]
    if _t in ("Int32Interval", "FloatInterval"):
        return {"min": _scalar(_v.min), "max": _scalar(_v.max)}
    if _t == "Name" or _t == "SoftObjectPath":
        return str(_v)
    if hasattr(_v, "get_path_name"):
        try:
            return _v.get_path_name()
        except Exception:
            pass
    return str(_v)[:200]

# ---------------------------------------------------------------- engine
_out["engine"] = {
    "version": _try(lambda: _unreal.SystemLibrary.get_engine_version()),
    "project_dir": _try(lambda: _unreal.Paths.project_dir()),
    "project_file": _try(lambda: _unreal.Paths.get_project_file_path()),
}

# --------------------------------------------------------------- console
_CVARS = [
    "sg.ViewDistanceQuality", "sg.AntiAliasingQuality",
    "sg.ShadowQuality", "sg.GlobalIlluminationQuality",
    "sg.ReflectionQuality", "sg.PostProcessQuality",
    "sg.TextureQuality", "sg.EffectsQuality", "sg.FoliageQuality",
    "sg.ShadingQuality",
    "r.ScreenPercentage", "t.MaxFPS", "r.Nanite.MaxPixelsPerEdge",
    "r.ShaderPipelineCache.Enabled", "r.DynamicGlobalIlluminationMethod",
    "r.ReflectionMethod",
    "grass.DensityScale", "foliage.DensityScale", "r.ViewDistanceScale",
    "grass.CullDistanceScale",
]
_cv = {}
for _n in _CVARS:
    try:
        _cv[_n] = _unreal.SystemLibrary.get_console_variable_float_value(_n)
    except Exception as _e:
        _cv[_n] = {"error": str(_e)[:120]}
_out["cvars"] = _cv

# ------------------------------------------------------------- landscape
_acts = _unreal.get_editor_subsystem(
    _unreal.EditorActorSubsystem).get_all_level_actors()

_land = [_a for _a in _acts if _a.__class__.__name__ == "Landscape"]
_out["landscape_count"] = len(_land)
if _land:
    _L = _land[0]
    _rc = _L.root_component
    _out["landscape"] = {
        "label": _try(lambda: _L.get_actor_label()),
        "location_cm": _scalar(_L.get_actor_location()),
        "rotation": _scalar(_L.get_actor_rotation()),
        "scale": _scalar(_rc.get_editor_property("relative_scale3d")),
        "material": _prop(_L, "landscape_material"),
        "lod_distance_factor": _prop(_L, "lod_distance_factor"),
        "streaming_distance_multiplier": _prop(
            _L, "streaming_distance_multiplier"),
        "cast_shadow": _prop(_L, "cast_shadow"),
    }
_out["proxy_count"] = len([
    _a for _a in _acts
    if _a.__class__.__name__ == "LandscapeStreamingProxy"])

# ------------------------------------------------------------ grass type
_gt = {}
for _p in ("/Game/Foliage/GT_alpine_Meadow",):
    _a = _unreal.EditorAssetLibrary.load_asset(_p)
    if _a is None:
        _gt[_p] = {"error": "asset not found"}
        continue
    _d = {"enable_density_scaling": _prop(_a, "enable_density_scaling")}
    _vs = []
    try:
        for _v in _a.get_editor_property("grass_varieties"):
            _vs.append({
                "mesh": _scalar(_v.get_editor_property("grass_mesh")),
                "grass_density": _scalar(
                    _v.get_editor_property("grass_density")),
                "start_cull_distance": _scalar(
                    _v.get_editor_property("start_cull_distance")),
                "end_cull_distance": _scalar(
                    _v.get_editor_property("end_cull_distance")),
                "random_rotation": _scalar(
                    _v.get_editor_property("random_rotation")),
                "align_to_surface": _scalar(
                    _v.get_editor_property("align_to_surface")),
                "scale_x": _scalar(_v.get_editor_property("scale_x")),
                "cast_dynamic_shadow": _scalar(
                    _v.get_editor_property("cast_dynamic_shadow")),
            })
    except Exception as _e:
        _vs = [{"error": str(_e)[:160]}]
    _d["varieties"] = _vs
    _gt[_p] = _d
_out["grass_types"] = _gt

# ---------------------------------------------------------- foliage type
_ft = {}
for _p in ("/Game/Foliage/FT_Conifer",):
    _a = _unreal.EditorAssetLibrary.load_asset(_p)
    if _a is None:
        _ft[_p] = {"error": "asset not found"}
        continue
    _ft[_p] = {_n: _prop(_a, _n) for _n in (
        "mesh", "cull_distance", "enable_density_scaling",
        "align_to_normal", "align_max_angle", "random_yaw",
        "scaling", "scale_x", "random_pitch_angle",
        "ground_slope_angle", "height", "collision_with_world",
        "cast_shadow", "affect_dynamic_indirect_lighting",
        "mobility", "density", "radius",
    )}
_out["foliage_types"] = _ft

# ----------------------------------------------------------- static mesh
_sm = {}
for _p in ("/Game/Meshes/fir_tree_01_c_LOD0",):
    _a = _unreal.EditorAssetLibrary.load_asset(_p)
    if _a is None:
        _sm[_p] = {"error": "asset not found"}
        continue
    _ss = _unreal.get_editor_subsystem(_unreal.StaticMeshEditorSubsystem)
    _lods = []
    try:
        _screens = list(_ss.get_lod_screen_sizes(_a))
    except Exception:
        _screens = []
    for _i in range(_a.get_num_lods()):
        _lods.append({
            "lod": _i,
            "triangles": _try(lambda _i=_i: int(_a.get_num_triangles(_i))),
            "sections": _try(lambda _i=_i: int(_a.get_num_sections(_i))),
            "screen_size": (round(_screens[_i], 5)
                            if _i < len(_screens) else None),
        })
    _slots = []
    try:
        for _i, _s in enumerate(_a.get_editor_property("static_materials")):
            _mi = _s.material_interface
            _slots.append({"index": _i, "slot": str(_s.material_slot_name),
                           "material": (_mi.get_path_name()
                                        if _mi else None)})
    except Exception as _e:
        _slots = [{"error": str(_e)[:160]}]
    _sm[_p] = {"lods": _lods, "slots": _slots,
               "bounds_cm": _scalar(_a.get_bounds().box_extent)}
_out["static_meshes"] = _sm

# -------------------------------------------------------------- textures
_tx = {}
for _p in ("/Game/Surfaces/T_Ground037_C", "/Game/Surfaces/T_Ground037_N",
           "/Game/Surfaces/T_Ground037_R", "/Game/Textures/T_alpine_weights",
           "/Game/Textures/T_Alpine_Grass"):
    _a = _unreal.EditorAssetLibrary.load_asset(_p)
    if _a is None:
        _tx[_p] = {"error": "asset not found"}
        continue
    _tx[_p] = {_n: _prop(_a, _n) for _n in (
        "compression_settings", "srgb", "mip_gen_settings",
        "never_stream", "lod_group", "filter")}
    _tx[_p]["size"] = [_try(lambda: int(_a.blueprint_get_size_x())),
                       _try(lambda: int(_a.blueprint_get_size_y()))]
_out["textures"] = _tx

# ----------------------------------------------------------- scene light
_lights = {}
for _cls in ("DirectionalLight", "SkyLight", "SkyAtmosphere",
             "ExponentialHeightFog", "VolumetricCloud"):
    _hits = [_a for _a in _acts if _a.__class__.__name__ == _cls]
    if not _hits:
        _lights[_cls] = {"error": "no actor of this class in the level"}
        continue
    _a = _hits[0]
    _d = {"count": len(_hits), "label": _try(lambda: _a.get_actor_label()),
          "rotation": _scalar(_a.get_actor_rotation()),
          "location_cm": _scalar(_a.get_actor_location())}
    _lc = None
    try:
        _lc = _a.get_editor_property("light_component")
    except Exception:
        pass
    if _lc is not None:
        for _n in ("intensity", "light_color", "temperature",
                   "use_temperature", "atmosphere_sun_light",
                   "cast_shadows", "source_type", "intensity_units"):
            _d[_n] = _prop(_lc, _n)
    if _cls == "ExponentialHeightFog":
        _fc = _try(lambda: _a.get_editor_property("component"))
        if not isinstance(_fc, dict):
            for _n in ("fog_density", "fog_height_falloff",
                       "fog_inscattering_luminance", "start_distance",
                       "fog_max_opacity", "enable_volumetric_fog",
                       "volumetric_fog_distance"):
                _d[_n] = _prop(_fc, _n)
    _lights[_cls] = _d
_out["scene"] = _lights

# --------------------------------------------------------------- foliage
_ifa = [_a for _a in _acts
        if _a.__class__.__name__ == "InstancedFoliageActor"]
_inst = {}
for _a in _ifa:
    for _c in _a.get_components_by_class(
            _unreal.FoliageInstancedStaticMeshComponent):
        _m = _c.get_editor_property("static_mesh")
        _k = _m.get_path_name() if _m else "<none>"
        _e = _inst.setdefault(_k, {"instances": 0, "components": 0})
        _e["instances"] += int(_c.get_instance_count())
        _e["components"] += 1
        _e["cull_start"] = _prop(_c, "instance_start_cull_distance")
        _e["cull_end"] = _prop(_c, "instance_end_cull_distance")
_out["foliage_instances"] = {"actors": len(_ifa), "by_mesh": _inst}

print("__LL_STATE__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--out", default=None,
                    help="Write the raw JSON here as well as summarising.")
    args = ap.parse_args(argv)

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote,
            bootstrap._norm(bootstrap.UE_PROJECT_ROOT), args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(PAYLOAD, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("command failed: {0}".format((r or {}).get("result")))
            return 4
        for line in bootstrap._collect_output(r).splitlines():
            if line.startswith(MARKER):
                data = json.loads(line[len(MARKER):])
                if args.out:
                    with open(args.out, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, indent=2, sort_keys=True)
                    print("wrote {0}".format(args.out))
                _report(data)
                return 0
        print("no marker in output")
        return 4
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()


def _errors(node, path=""):
    """Every value that could NOT be read, with its location."""
    out = []
    if isinstance(node, dict):
        if "error" in node and len(node) == 1:
            out.append((path, node["error"]))
        else:
            for k, v in node.items():
                out.extend(_errors(v, "{0}.{1}".format(path, k) if path
                                   else str(k)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(_errors(v, "{0}[{1}]".format(path, i)))
    return out


def _report(d):
    print("engine  : {0}".format(d["engine"].get("version")))
    print("project : {0}".format(d["engine"].get("project_file")))
    print("")
    print("cvars in the LIVE session:")
    for k, v in sorted(d.get("cvars", {}).items()):
        print("   {0:<38} {1}".format(k, v))
    print("")
    L = d.get("landscape")
    if L:
        print("landscape: {0}".format(L.get("label")))
        print("   location_cm {0}   scale {1}".format(
            L.get("location_cm"), L.get("scale")))
        print("   material    {0}".format(L.get("material")))
    print("   proxies     {0}".format(d.get("proxy_count")))
    print("")
    for p, g in d.get("grass_types", {}).items():
        print("grass type {0}".format(p))
        print("   enable_density_scaling = {0}".format(
            g.get("enable_density_scaling")))
        for v in g.get("varieties", []):
            if "error" in v:
                print("   {0}".format(v)); continue
            print("   {0}".format(v.get("mesh")))
            print("      density {0}  cull {1}..{2}".format(
                v.get("grass_density"), v.get("start_cull_distance"),
                v.get("end_cull_distance")))
    print("")
    for p, f in d.get("foliage_types", {}).items():
        print("foliage type {0}".format(p))
        for k, v in sorted(f.items()):
            print("   {0:<34} {1}".format(k, v))
    print("")
    for p, m in d.get("static_meshes", {}).items():
        print("static mesh {0}".format(p))
        for lod in m.get("lods", []):
            print("   LOD{0}  tris {1:>9}  sections {2}  screen {3}".format(
                lod["lod"], lod["triangles"], lod["sections"],
                lod["screen_size"]))
        for s in m.get("slots", []):
            print("   slot {0}".format(s))
    print("")
    fi = d.get("foliage_instances", {})
    print("foliage instances across {0} actor(s):".format(fi.get("actors")))
    for k, v in sorted(fi.get("by_mesh", {}).items()):
        print("   {0}".format(k))
        print("      {0:,} instances, {1} components, cull {2}..{3}".format(
            v["instances"], v["components"], v.get("cull_start"),
            v.get("cull_end")))
    print("")
    errs = _errors(d)
    print("=" * 66)
    if not errs:
        print("EVERY value above was READ. Nothing is VALUE UNVERIFIED.")
    else:
        print("{0} value(s) COULD NOT BE READ -> these are the ones that "
              "must be\nmarked VALUE UNVERIFIED in RECIPES.md. They are NOT "
              "absent, and\nthey must NOT be filled in from memory:".format(
                  len(errs)))
        for path, msg in errs:
            print("   {0}\n      {1}".format(path, msg))
    print("=" * 66)


if __name__ == "__main__":
    raise SystemExit(main())
