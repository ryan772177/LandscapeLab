"""Place one 18% grey card per bench station (RULED 2026-09-10).

Find-or-create by label Bench_GreyCard_<station>: a small LIT plane
(engine BasicShapes Plane, 100 cm base; 30 cm at the default SCALE=0.3,
but SCALE is host-templated) on a constant-18%-albedo
fully-rough material, positioned in the station frame's LOWER-RIGHT
region and angled on the bisector between the camera and the declared
sun -- the photographic grey-card convention, so it is sunlit AND
camera-facing. highlight_tint and WB are measured on ITS pixels; the
scene metrics mask it out (R-GREYCARD).

Geometry uses the CAMERA ACTOR'S OWN basis vectors (get_actor_forward/
right/up), not a hand convention -- the roll-for-pitch confusion has
cost this project three defects. The card transform and the camera basis
are RETURNED so the host projects the pixel region from read-back state,
not from what was requested.

All maths guarded per read; the rotation constructor is resolved from
the reflected surface (make_rot_from_z, else make_rot_from_zx) and the
payload reports WHICH answered.
"""
import json as _json
import math as _math
import traceback as _tb

import unreal as _u

STATIONS = __STATIONS__
SUN_AZ = float("__SUN_AZ__")
SUN_EL = float("__SUN_EL__")
DIST_CM = float("__DIST_CM__")
SCALE = float("__SCALE__")
RIGHT_FRAC = 0.55   # of the half-frame at hfov 90; inside the 45 deg edge
DOWN_FRAC = 0.35

_MAT_PATH = "/Game/Bench/M_GreyCard18"
_MESH_PATH = "/Engine/BasicShapes/Plane"

_out = {"ok": False, "stations": {}, "material": None}


def _v(vec):
    return [round(float(vec.x), 3), round(float(vec.y), 3),
            round(float(vec.z), 3)]


def _norm(x, y, z):
    m = _math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / m, y / m, z / m)


try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _ass = _u.get_editor_subsystem(_u.EditorAssetSubsystem)

    # ---- material: find-or-create M_GreyCard18 --------------------------
    # AUDIT 2026-09-10 F4: the 0.18 constant IS the instrument, so a
    # reused material is READ BACK (the node wired into BaseColor) and a
    # mismatch or unverifiable graph REFUSES rather than silently
    # measuring WB against an unknown albedo (rule 12).
    if _eal.does_asset_exist(_MAT_PATH):
        _mat = _eal.load_asset(_MAT_PATH)
        _bc = None
        try:
            _node = _mel.get_material_property_input_node(
                _mat, _u.MaterialProperty.MP_BASE_COLOR)
            _c = _node.get_editor_property("constant")
            _bc = [round(float(_c.r), 4), round(float(_c.g), 4),
                   round(float(_c.b), 4)]
        except Exception as _e0:
            raise RuntimeError(
                "grey-card material exists but its BaseColor node could "
                "not be read back (%s) -- refusing to measure against an "
                "unverified albedo" % str(_e0)[:150])
        if _bc != [0.18, 0.18, 0.18]:
            raise RuntimeError(
                "grey-card material albedo reads %s, not 0.18 neutral -- "
                "refusing; rebuild or delete the asset deliberately"
                % _bc)
        _out["material"] = {"path": _MAT_PATH, "state": "reused",
                            "base_color_readback": _bc}
    else:
        _mat = _u.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_GreyCard18", "/Game/Bench", _u.Material,
            _u.MaterialFactoryNew())
        if _mat is None:
            raise RuntimeError("could not create " + _MAT_PATH)
        _c3 = _mel.create_material_expression(
            _mat, _u.MaterialExpressionConstant3Vector, -400, 0)
        _c3.set_editor_property(
            "constant", _u.LinearColor(0.18, 0.18, 0.18, 1.0))
        _mel.connect_material_property(
            _c3, "", _u.MaterialProperty.MP_BASE_COLOR)
        _cr = _mel.create_material_expression(
            _mat, _u.MaterialExpressionConstant, -400, 200)
        _cr.set_editor_property("r", 1.0)
        _mel.connect_material_property(
            _cr, "", _u.MaterialProperty.MP_ROUGHNESS)
        _cs = _mel.create_material_expression(
            _mat, _u.MaterialExpressionConstant, -400, 320)
        _cs.set_editor_property("r", 0.0)
        _mel.connect_material_property(
            _cs, "", _u.MaterialProperty.MP_SPECULAR)
        _mel.recompile_material(_mat)
        if not _eal.save_asset(_MAT_PATH):
            raise RuntimeError("could not save " + _MAT_PATH)
        # rule 12: the 0.18 constant IS the instrument, so read it back off the
        # CREATED graph too, not only the reused path.
        try:
            _node2 = _mel.get_material_property_input_node(
                _mat, _u.MaterialProperty.MP_BASE_COLOR)
            _c2 = _node2.get_editor_property("constant")
            _bc2 = [round(float(_c2.r), 4), round(float(_c2.g), 4),
                    round(float(_c2.b), 4)]
        except Exception as _e1:
            raise RuntimeError(
                "created grey-card BaseColor node could not be read back "
                "(%s)" % str(_e1)[:150])
        if _bc2 != [0.18, 0.18, 0.18]:
            raise RuntimeError(
                "created grey-card albedo reads %s, not 0.18 neutral" % _bc2)
        _out["material"] = {"path": _MAT_PATH, "state": "created",
                            "base_color_readback": _bc2}

    _mesh = _eal.load_asset(_MESH_PATH)
    if _mesh is None:
        raise RuntimeError("engine plane mesh not loadable")

    # direction TO the sun: light travels along azimuth SUN_AZ, so the sun
    # sits on the opposite bearing, SUN_EL above the horizon.
    _az = _math.radians(SUN_AZ - 180.0)
    _el = _math.radians(SUN_EL)
    _sun = (_math.cos(_el) * _math.cos(_az),
            _math.cos(_el) * _math.sin(_az),
            _math.sin(_el))

    _touched = []
    for _st in STATIONS:
        _row = {"ok": False}
        _out["stations"][_st] = _row
        _cams = [_a for _a in _eas.get_all_level_actors()
                 if _a.get_actor_label() == "Bench_" + _st]
        if not _cams:
            _row["error"] = "no camera actor labelled Bench_" + _st
            continue
        if len(_cams) > 1:
            # Labels collide in this project (rule 8); refuse rather than
            # measure the frame off whichever actor happened to be first.
            _row["error"] = ("%d actors share the label Bench_%s -- refusing "
                             "to guess which is the camera" % (len(_cams), _st))
            continue
        _cam = _cams[0]
        _cp = _cam.get_actor_location()
        _f = _cam.get_actor_forward_vector()
        _r = _cam.get_actor_right_vector()
        _up = _cam.get_actor_up_vector()
        _row["camera"] = {"loc_cm": _v(_cp), "forward": _v(_f),
                          "right": _v(_r), "up": _v(_up)}

        _dx = _f.x + RIGHT_FRAC * _r.x - DOWN_FRAC * _up.x
        _dy = _f.y + RIGHT_FRAC * _r.y - DOWN_FRAC * _up.y
        _dz = _f.z + RIGHT_FRAC * _r.z - DOWN_FRAC * _up.z
        _dx, _dy, _dz = _norm(_dx, _dy, _dz)
        _pos = _u.Vector(_cp.x + _dx * DIST_CM, _cp.y + _dy * DIST_CM,
                         _cp.z + _dz * DIST_CM)

        _tocam = _norm(_cp.x - _pos.x, _cp.y - _pos.y, _cp.z - _pos.z)
        _n = _norm(_tocam[0] + _sun[0], _tocam[1] + _sun[1],
                   _tocam[2] + _sun[2])
        _nv = _u.Vector(_n[0], _n[1], _n[2])
        _rot, _via = None, None
        try:
            _rot = _u.MathLibrary.make_rot_from_z(_nv)
            _via = "make_rot_from_z"
        except Exception:
            try:
                _rot = _u.MathLibrary.make_rot_from_zx(_nv, _f)
                _via = "make_rot_from_zx"
            except Exception as _e2:
                _row["error"] = "no rotation constructor answered: " + str(_e2)
                continue
        _row["rot_via"] = _via

        # The spawn/reuse/mutate body is per-station try-guarded: an actor that
        # spawns None, or a reused label pointing at a non-StaticMeshActor, must
        # fail ONLY this station -- not abort the loop and discard the good ones.
        try:
            _label = "Bench_GreyCard_" + _st
            _cards = [_a for _a in _eas.get_all_level_actors()
                      if _a.get_actor_label() == _label]
            if len(_cards) > 1:
                _row["error"] = ("%d actors share label %s -- refusing to "
                                 "mutate by an ambiguous label"
                                 % (len(_cards), _label))
                continue
            if _cards:
                _card = _cards[0]
                # rule 8: a label match is not an identity. Confirm the reused
                # actor is actually a StaticMeshActor before overwriting its
                # mesh/material/transform.
                if not isinstance(_card, _u.StaticMeshActor):
                    _row["error"] = ("actor labelled %s is a %s, not a "
                                     "StaticMeshActor -- refusing to overwrite"
                                     % (_label, type(_card).__name__))
                    continue
                _row["state"] = "reused"
            else:
                _card = _eas.spawn_actor_from_class(_u.StaticMeshActor, _pos)
                if _card is None:
                    _row["error"] = "spawn_actor_from_class returned None"
                    continue
                _card.set_actor_label(_label)
                _row["state"] = "spawned"
            try:
                _card.set_editor_property("is_spatially_loaded", False)
            except Exception:
                pass
            _smc = _card.static_mesh_component
            # A freshly spawned StaticMeshActor is Static; setting the mesh on
            # a Static component is allowed in the EDITOR world.
            _smc.set_static_mesh(_mesh)
            _smc.set_material(0, _mat)
            _card.set_actor_location(_pos, False, False)
            _card.set_actor_rotation(_rot, False)
            _card.set_actor_scale3d(_u.Vector(SCALE, SCALE, SCALE))

            # READ BACK from the actor, not the values just written
            _p2 = _card.get_actor_location()
            _row["card"] = {
                "label": _label,
                "loc_cm": _v(_p2),
                "forward": _v(_card.get_actor_forward_vector()),
                "right": _v(_card.get_actor_right_vector()),
                "up": _v(_card.get_actor_up_vector()),
                "scale": round(float(_card.get_actor_scale3d().x), 4),
                "mesh": str(_smc.get_editor_property(
                    "static_mesh").get_path_name()),
                "material": str(_smc.get_material(0).get_path_name()),
                "dist_from_cam_cm": round(_math.sqrt(
                    (_p2.x - _cp.x) ** 2 + (_p2.y - _cp.y) ** 2
                    + (_p2.z - _cp.z) ** 2), 1),
            }
            _touched.append(_card)
            _row["ok"] = True
        except Exception as _est:
            _row["error"] = "station body failed: " + str(_est)[:200]
            continue

    # bounded save of the cards (R-LIGHTSAVE discipline)
    _save = {"marked": 0, "packages": [], "saved": None}
    for _a in _touched:
        try:
            _a.modify()
        except Exception:
            pass
        try:
            if _ass.set_dirty_flag(_a, True):
                _save["marked"] += 1
        except Exception:
            pass
        try:
            _n2 = str(_a.get_outermost().get_name())
            if _n2 not in _save["packages"]:
                _save["packages"].append(_n2)
        except Exception:
            _save["packages"].append("UNREADABLE")
    if _touched:
        _save["saved"] = bool(_ass.save_loaded_assets(_touched, False))
    _out["save"] = _save
    # NN13: all() over an empty stations dict is True. Require that stations
    # were actually processed, that every requested station is present, that
    # each is ok, AND that the card save (F2) actually persisted.
    _out["ok"] = (bool(_out["stations"])
                  and len(_out["stations"]) == len(STATIONS)
                  and all(r.get("ok") for r in _out["stations"].values())
                  and (not _touched or _save["saved"] is True))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]

print("__LL__" + _json.dumps(_out))
