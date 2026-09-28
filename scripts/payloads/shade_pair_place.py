"""Place the R-SHADE CARD PAIR: a second 18% card, and a sun blocker.

RULED 2026-09-12b. `shadow_tint_B` was REJECTED as an acceptance because
it measured TERRAIN ALBEDO -- the grey card proved the light was neutral
while the metric read 80% blue excess. The replacement compares two
cards of the SAME KNOWN ALBEDO that differ in ONE thing: whether the sun
reaches them.

WHY A BLOCKER AND NOT TERRAIN SHADOW. Terrain shadow is cast by ground
whose albedo, orientation and surrounding bounce are all uncontrolled,
which is how the old metric ended up measuring the ground. A blocker
card occludes the SUN DISC and nothing else, so the shaded card is lit
by sky plus whatever bounce reaches both cards alike.

GEOMETRY, and why it is checkable rather than hoped for. The shade card
is the LIT card's mirror across the frame centre -- same distance, same
scale, same bisector rotation, same material -- so the pair differs only
in occlusion. The blocker sits along the card-to-SUN ray, which at this
bench is within a few degrees of perpendicular to the card-to-CAMERA
ray, so it lands BESIDE the card in frame rather than in front of it.
That is a measured property of this sun, not a general one, so the host
PROJECTS all three rects and REFUSES on overlap instead of trusting it.

Everything is read back from the actors, never from the values written.
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
BLOCKER_CM = float("__BLOCKER_CM__")
BLOCKER_SCALE = float("__BLOCKER_SCALE__")
RIGHT_FRAC = -0.55      # MIRROR of the lit card's +0.55
DOWN_FRAC = 0.35        # same as the lit card

_MAT_PATH = "/Game/Bench/M_GreyCard18"
_MESH_PATH = "/Engine/BasicShapes/Plane"
# ⛔ THE BLOCKER IS A CUBE, NOT A PLANE, and the reason is geometric.
# The blocker's normal must point at the SUN to cast a wide shadow, and
# at this bench the sun sits ~87 deg off the card-to-camera ray -- so the
# camera sees a plane blocker nearly EDGE-ON. An edge-on plane projects
# to a thin diagonal sliver whose axis-aligned bounding box is enormous
# (measured: 838 x 942 px), which the overlap gate correctly refuses.
# A cube is non-degenerate from every angle: it shadows the card just as
# well and projects to a compact rect the gate can reason about.
_BLOCKER_MESH_PATH = "/Engine/BasicShapes/Cube"

_out = {"ok": False, "stations": {}}


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

    # THE SHADE CARD MUST BE THE SAME INSTRUMENT AS THE LIT ONE. Reuse the
    # ruled material and READ ITS ALBEDO BACK; a pair measured against two
    # different albedos is a ratio of albedos wearing a lighting metric's
    # name, which is the exact defect this replaces.
    if not _eal.does_asset_exist(_MAT_PATH):
        raise RuntimeError(
            "%s does not exist -- place the lit grey card first; the pair "
            "must share one material" % _MAT_PATH)
    _mat = _eal.load_asset(_MAT_PATH)
    _node = _mel.get_material_property_input_node(
        _mat, _u.MaterialProperty.MP_BASE_COLOR)
    _c = _node.get_editor_property("constant") if _node is not None else None
    if _c is None:
        raise RuntimeError(
            "%s base color is not a plugged constant vector; cannot verify the "
            "shared 0.18 albedo" % _MAT_PATH)
    _bc = [round(float(_c.r), 4), round(float(_c.g), 4),
           round(float(_c.b), 4)]
    if _bc != [0.18, 0.18, 0.18]:
        raise RuntimeError(
            "shared card material albedo reads %s, not 0.18 neutral" % _bc)
    _out["material"] = {"path": _MAT_PATH, "base_color_readback": _bc}

    _mesh = _eal.load_asset(_MESH_PATH)
    if _mesh is None:
        raise RuntimeError("engine plane mesh not loadable")
    _bmesh = _eal.load_asset(_BLOCKER_MESH_PATH)
    if _bmesh is None:
        raise RuntimeError("engine cube mesh not loadable")

    # Direction TO the sun. azimuth_deg is the LIGHT ACTOR'S YAW, i.e. the
    # direction light TRAVELS, so the sun is at azimuth-180.
    _az = _math.radians(SUN_AZ - 180.0)
    _el = _math.radians(SUN_EL)
    _sun = (_math.cos(_el) * _math.cos(_az),
            _math.cos(_el) * _math.sin(_az),
            _math.sin(_el))
    _out["sun_dir_to_sun"] = [round(v, 4) for v in _sun]

    # ---- REMOVE pair actors for stations NOT requested -------------------
    #
    # ⛔ WHY THIS IS NOT OPTIONAL. These are instrument actors standing in
    # the world. A card and a blocker left in mid_slope's frame do not
    # merely clutter it -- they change what every later capture of that
    # station measures, silently, because nothing downstream knows they are
    # instruments. An earlier run placed all three stations before the host
    # refused on geometry, which is exactly how that happens.
    #
    # Identified by label prefix AND a PROPERTY SIGNATURE (rule 8: labels
    # collide, so a name alone is not identity before an irreversible
    # destroy). Only a StaticMeshActor carrying our plane/cube mesh is ours;
    # a collision on the label held by anything else is left alone and
    # reported.
    _removed, _skipped = [], []
    _our_meshes = {_MESH_PATH, _BLOCKER_MESH_PATH}
    for _a in list(_eas.get_all_level_actors()):
        _lb = _a.get_actor_label()
        for _pref in ("Bench_ShadeCard_", "Bench_ShadeBlocker_"):
            if not (_lb.startswith(_pref) and _lb[len(_pref):] not in STATIONS):
                continue
            _sig_ok = False
            try:
                if isinstance(_a, _u.StaticMeshActor):
                    _m = _a.static_mesh_component.get_editor_property(
                        "static_mesh")
                    _sig_ok = (_m is not None
                               and _m.get_path_name() in _our_meshes)
            except Exception:
                _sig_ok = False
            if _sig_ok:
                _removed.append(_lb)
                _eas.destroy_actor(_a)
            else:
                _skipped.append(_lb)
            break
    _out["removed_for_unrequested_stations"] = _removed
    if _skipped:
        _out["skipped_label_collisions"] = _skipped

    _touched = []
    for _st in STATIONS:
        _row = {"ok": False}
        _out["stations"][_st] = _row
        _cam = None
        for _a in _eas.get_all_level_actors():
            if _a.get_actor_label() == "Bench_" + _st:
                _cam = _a
                break
        if _cam is None:
            _row["error"] = "no camera actor labelled Bench_" + _st
            continue
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

        # Same bisector rotation as the lit card: camera-facing AND
        # sun-facing, so the two cards present the same geometry.
        _tocam = _norm(_cp.x - _pos.x, _cp.y - _pos.y, _cp.z - _pos.z)
        _n = _norm(_tocam[0] + _sun[0], _tocam[1] + _sun[1],
                   _tocam[2] + _sun[2])
        _rot = _u.MathLibrary.make_rot_from_z(_u.Vector(_n[0], _n[1], _n[2]))

        # THE SEPARATION THAT MAKES THE BLOCKER SAFE, measured not assumed.
        _sep = abs(_sun[0] * _tocam[0] + _sun[1] * _tocam[1]
                   + _sun[2] * _tocam[2])
        _row["sun_dot_tocam"] = round(_sep, 4)
        _row["sun_tocam_angle_deg"] = round(
            _math.degrees(_math.acos(max(-1.0, min(1.0, _sep)))), 2)

        for _label, _p, _rr, _sc in (
                ("Bench_ShadeCard_" + _st, _pos, _rot, SCALE),
                ("Bench_ShadeBlocker_" + _st,
                 _u.Vector(_pos.x + _sun[0] * BLOCKER_CM,
                           _pos.y + _sun[1] * BLOCKER_CM,
                           _pos.z + _sun[2] * BLOCKER_CM),
                 _u.MathLibrary.make_rot_from_z(
                     _u.Vector(_sun[0], _sun[1], _sun[2])),
                 BLOCKER_SCALE)):
            _act = None
            for _a in _eas.get_all_level_actors():
                if _a.get_actor_label() == _label:
                    _act = _a
                    break
            if _act is None:
                _act = _eas.spawn_actor_from_class(_u.StaticMeshActor, _p)
                _act.set_actor_label(_label)
                _state = "spawned"
            else:
                _state = "reused"
            try:
                _act.set_editor_property("is_spatially_loaded", False)
            except Exception:
                pass
            _is_card = "ShadeCard" in _label
            _smc = _act.static_mesh_component
            _smc.set_static_mesh(_mesh if _is_card else _bmesh)
            if _is_card:
                _smc.set_material(0, _mat)
            # The blocker keeps the mesh's own material: its appearance is
            # irrelevant, only that it is opaque and casts.
            try:
                _smc.set_editor_property("cast_shadow", True)
            except Exception:
                pass
            _act.set_actor_location(_p, False, False)
            _act.set_actor_rotation(_rr, False)
            _act.set_actor_scale3d(_u.Vector(_sc, _sc, _sc))

            _p2 = _act.get_actor_location()
            _s3 = _act.get_actor_scale3d()
            _key = "card" if _is_card else "blocker"
            # Material IS read back for the card (rule 12: "everything read
            # back"); the card's whole premise is the SHARED 0.18 albedo.
            _mat0 = _smc.get_material(0) if _is_card else None
            _entry = {
                "label": _label, "state": _state, "loc_cm": _v(_p2),
                "forward": _v(_act.get_actor_forward_vector()),
                "right": _v(_act.get_actor_right_vector()),
                "up": _v(_act.get_actor_up_vector()),
                "scale": [round(float(_s3.x), 4), round(float(_s3.y), 4),
                          round(float(_s3.z), 4)],
                "mesh": str(_smc.get_editor_property(
                    "static_mesh").get_path_name()),
                "cast_shadow": bool(
                    _smc.get_editor_property("cast_shadow")),
                "is_spatially_loaded": bool(
                    _act.get_editor_property("is_spatially_loaded")),
                "dist_from_cam_cm": round(_math.sqrt(
                    (_p2.x - _cp.x) ** 2 + (_p2.y - _cp.y) ** 2
                    + (_p2.z - _cp.z) ** 2), 1),
            }
            if _is_card:
                _entry["material"] = (_mat0.get_path_name()
                                      if _mat0 is not None else None)
            _row[_key] = _entry
            _touched.append(_act)
        # Per-station verdict: both actors present, the card carries the shared
        # material, and neither is left spatially loaded.
        _card = _row.get("card") or {}
        _blocker = _row.get("blocker") or {}
        _row["ok"] = (bool(_card) and bool(_blocker)
                      and _card.get("material") == _MAT_PATH
                      and _card.get("is_spatially_loaded") is False
                      and _blocker.get("is_spatially_loaded") is False)
        if not _row["ok"] and "error" not in _row:
            _row["error"] = ("post-place read-back failed: card material %r, "
                             "card spl %r, blocker spl %r"
                             % (_card.get("material"),
                                _card.get("is_spatially_loaded"),
                                _blocker.get("is_spatially_loaded")))

    _save = {"marked": 0, "saved": None}
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
    if _touched:
        _save["saved"] = bool(_ass.save_loaded_assets(_touched, False))
    _out["save"] = _save
    # NN13: all() over an empty stations dict is True -- require stations were
    # actually processed, all requested present, each ok, AND the save persisted.
    _out["ok"] = (bool(_out["stations"])
                  and len(_out["stations"]) == len(STATIONS)
                  and all(r.get("ok") for r in _out["stations"].values())
                  and (not _touched or _save["saved"] is True))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]

print("__LL__" + _json.dumps(_out))
