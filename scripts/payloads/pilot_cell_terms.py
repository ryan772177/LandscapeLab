"""pilot_cell_terms.py -- the :218-219 input terms, read off the built cell.

READ-ONLY unless CFG["set_min_visible_distance"] is given, in which case
that ONE property on that ONE HLOD actor is written and read back.

WHAT THIS ANSWERS. `ComputeRequiredTextureSize` takes two inputs on the
AutomaticSize branch (LandscapeHLODBuilder.cpp:218-219):

    InViewDistance          <- FHLODBuildContext.MinVisibleDistance
                               (WorldPartitionHLODUtilities.cpp:1044,
                                persisted on the HLOD actor)
    InMeshDescription       -> GetBounds().SphereRadius, and Mesh3DArea
                               inside GetMeshTextureSizeFromTargetTexelDensity

The mesh description itself is transient, but the BUILT static mesh is
its output, so its bounds and triangle count stand in for the input --
and they are what the report needs to say whether the mesh was
degenerate.

⛔ GetHLODHash IS READ BEFORE AND AFTER ANY WRITE. The hash is what the
rebuild policy compares; a write that does not move it would not trigger
a rebuild, and the next build would silently reuse the old bake.
"""
import json as _json
import math as _math
import traceback as _tb

import unreal as _u

CFG = _json.loads(r'''__CONFIG_JSON__''')
LABEL = CFG["label"]
SET_MVD = CFG.get("set_min_visible_distance")

_out = {"ok": False, "label": LABEL}


def _dims(_t):
    _d = {"name": _t.get_path_name().split(".")[-1]}
    for _k, _fn in (("x", "blueprint_get_size_x"),
                    ("y", "blueprint_get_size_y")):
        try:
            _d[_k] = int(getattr(_t, _fn)())
        except Exception:
            _d[_k] = None
    return _d


try:
    _ar = _u.AssetRegistryHelpers.get_asset_registry()
    _f = _u.ARFilter(
        class_paths=[_u.TopLevelAssetPath("/Script/Engine",
                                          "WorldPartitionHLOD")],
        package_paths=["/Game/__ExternalActors__/Alpine8K"],
        recursive_paths=True)
    _obj = None
    for _ad in _ar.get_assets(_f):
        try:
            _o = _ad.get_asset()
            if _o is not None and _o.get_actor_label() == LABEL:
                _obj = _o
                break
        except Exception:
            continue
    if _obj is None:
        _out["error"] = "cell not found"
        print("__LL__" + _json.dumps(_out, default=str))
        raise SystemExit(0)

    # ---- the distance term, and the hash ---------------------------
    def _read_state():
        _s = {}
        for _n, _fn in (("min_visible_distance", "get_min_visible_distance"),
                        ("hlod_hash", "get_hlod_hash")):
            try:
                _s[_n] = getattr(_obj, _fn)()
            except Exception as _e:
                _s[_n] = "RAISED: %s" % str(_e)[:90]
        return _s

    _out["before"] = _read_state()

    # ---- the mesh term --------------------------------------------
    _meshes = []
    _texs = []
    for _c in _obj.get_components_by_class(_u.StaticMeshComponent):
        try:
            _sm = _c.get_editor_property("static_mesh")
        except Exception:
            _sm = None
        if _sm is None:
            continue
        _m = {"mesh": _sm.get_path_name().split(".")[-1]}
        try:
            _m["triangles_lod0"] = int(_sm.get_num_triangles(0))
        except Exception:
            pass
        try:
            _b = _sm.get_bounds()
            _be = _b.box_extent
            _m["box_extent_cm"] = [round(float(_be.x), 1),
                                   round(float(_be.y), 1),
                                   round(float(_be.z), 1)]
            _m["sphere_radius_cm"] = round(float(_b.sphere_radius), 1)
            # The footprint the texel-density maths sees.
            _m["footprint_area_cm2"] = round(
                (2 * float(_be.x)) * (2 * float(_be.y)), 1)
            _a = _m["footprint_area_cm2"]
            if _a > 0:
                _m["texel_ratio_100_over_sqrt_area"] = round(
                    100.0 / _math.sqrt(_a), 8)
        except Exception as _e:
            _m["bounds_error"] = type(_e).__name__
        _meshes.append(_m)
        try:
            _n = int(_c.get_num_materials())
        except Exception:
            _n = 0
        for _i in range(_n):
            try:
                _mat = _c.get_material(_i)
                _tpv = list(_mat.get_editor_property(
                    "texture_parameter_values"))
            except Exception:
                _tpv = []
            for _p in _tpv:
                try:
                    _t = _p.get_editor_property("parameter_value")
                except Exception:
                    _t = None
                if _t is not None:
                    _texs.append(_dims(_t))
    _out["meshes"] = _meshes
    _out["textures"] = _texs
    _out["texture_dims"] = sorted({t["x"] for t in _texs if t.get("x")})

    # ---- optional single write ------------------------------------
    if SET_MVD is not None:
        try:
            _obj.set_min_visible_distance(float(SET_MVD))
            _out["write_attempted"] = float(SET_MVD)
        except Exception as _e:
            _out["write_error"] = "%s: %s" % (type(_e).__name__, _e)
        _out["after"] = _read_state()
        _out["hash_moved"] = (_out["before"].get("hlod_hash")
                              != _out["after"].get("hlod_hash"))
        # Save just this actor's package.
        try:
            _pkg = _obj.get_package()
            _ok = _u.EditorLoadingAndSavingUtils.save_packages([_pkg], False)
            _out["save_returned"] = bool(_ok)
            _dirty = [str(_p.get_name()) for _p in
                      (_u.EditorLoadingAndSavingUtils
                       .get_dirty_content_packages() or [])]
            _out["still_dirty_after_save"] = len(_dirty)
        except Exception as _e:
            _out["save_error"] = "%s: %s" % (type(_e).__name__, _e)

    _out["ok"] = True
except SystemExit:
    raise
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out, indent=1, default=str))
