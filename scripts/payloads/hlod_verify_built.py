"""ACCEPTANCE READ-BACK for a built HLOD cell: does it hold real geometry, with
what triangle count and which materials? READ-ONLY.

WHY THIS EXISTS AND WHY IT IS NOT OPTIONAL
    `-SetupHLODs` produces HLOD actors that LOOK like success and contain
    nothing: 2,230 of them, each a ~130-byte package with zero-extent bounds.
    Only `-BuildHLODs` gives them geometry. A count of HLOD actors is therefore
    not evidence of HLOD, and the package growing on disk (130 B -> 13.9 MB) is
    evidence of BYTES, not of triangles. This reads the mesh.

LOADING A WORLD PARTITION ACTOR
    HLOD actors are spatially loaded and are NOT in the editor's loaded set, so
    `EditorActorSubsystem.get_all_level_actors()` will not show them until they
    are pinned. `UWorldPartitionBlueprintLibrary::LoadActors` takes the GUIDs
    from the actor descs (`WorldPartitionBlueprintLibrary.h:118-119`), which is
    how this payload reaches one by label.

THE MESH API IS PROBED, NOT REMEMBERED
    Several triangle-count routes exist across UE versions and this project has
    already been burned once by calling a function that does not exist in 5.8
    inside a try/except, writing null, and reading the null as a measurement
    (`get_viewport_size`, REGISTER). So every route is tried, each result is
    labelled with the route that produced it, and a total failure reports
    "COULD NOT LOOK" rather than zero.

Run via:
    python scripts/ue_exec.py scripts/payloads/hlod_verify_built.py \
        --set LABEL=Alpine8K_HLODLayer_Merged/Alpine8K_HLODLayer_Instanced_L0_X-10_Y11
"""
import json as _json

import unreal as _u

LABEL = "__LABEL__"

_out = {"error": None, "label_requested": LABEL, "can_conclude": False}


def _path(_o):
    try:
        return _o.get_path_name() if _o is not None else None
    except Exception:
        return "<unreadable>"


try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _w = _ues.get_editor_world()
    _out["level_path"] = _w.get_path_name()

    # ---- find the desc by label ------------------------------------------
    _target = None
    for _d in _u.WorldPartitionBlueprintLibrary.get_actor_descs():
        if str(_d.get_editor_property("label")) == LABEL:
            _target = _d
            break
    if _target is None:
        _out["error"] = "no actor desc with that label"
    else:
        _guid = _target.get_editor_property("guid")
        _b = _target.get_editor_property("bounds")
        _out["desc"] = {
            "package": str(_target.get_editor_property("actor_package")),
            "runtime_grid": str(_target.get_editor_property("runtime_grid")),
            "bounds_min": [round(_b.min.x, 1), round(_b.min.y, 1),
                           round(_b.min.z, 1)],
            "bounds_max": [round(_b.max.x, 1), round(_b.max.y, 1),
                           round(_b.max.z, 1)],
            "bounds_extent_cm": [round(_b.max.x - _b.min.x, 1),
                                 round(_b.max.y - _b.min.y, 1),
                                 round(_b.max.z - _b.min.z, 1)],
        }
        # THE FIRST REAL SIGNAL: after Setup every HLOD desc had zero extent.
        _out["desc"]["bounds_are_nonzero"] = bool(
            (_b.max.x - _b.min.x) > 0.0 and (_b.max.z - _b.min.z) > 0.0)

        # ---- pin it so the actor exists ----------------------------------
        _u.WorldPartitionBlueprintLibrary.load_actors([_guid])
        _actor = None
        for _a in _eas.get_all_level_actors():
            try:
                if _a.get_actor_label() == LABEL:
                    _actor = _a
                    break
            except Exception:
                continue
        _out["actor_loaded"] = _path(_actor)

        if _actor is None:
            _out["verdict"] = ("COULD NOT LOOK -- desc found but the actor did "
                               "not load; triangle count NOT measured")
        else:
            _out["actor_class"] = _actor.get_class().get_name()
            _comps = []
            for _c in _actor.get_components_by_class(_u.StaticMeshComponent):
                _row = {"component": _c.get_name(),
                        "class": _c.get_class().get_name()}
                try:
                    _m = _c.get_editor_property("static_mesh")
                except Exception as _e:
                    _m = None
                    _row["static_mesh_error"] = type(_e).__name__
                _row["static_mesh"] = _path(_m)
                if _m is not None:
                    # -- triangle count, every route tried and labelled -----
                    _tris = {}
                    try:
                        _sms = _u.get_editor_subsystem(
                            _u.StaticMeshEditorSubsystem)
                        _tris["StaticMeshEditorSubsystem.get_number_triangles"] = \
                            _sms.get_number_triangles(_m, 0)
                    except Exception as _e:
                        _tris["StaticMeshEditorSubsystem.get_number_triangles"] = \
                            "ERR " + type(_e).__name__
                    try:
                        _tris["StaticMesh.get_num_triangles"] = \
                            _m.get_num_triangles(0)
                    except Exception as _e:
                        _tris["StaticMesh.get_num_triangles"] = \
                            "ERR " + type(_e).__name__
                    try:
                        _tris["num_lods"] = _m.get_num_lods()
                    except Exception as _e:
                        _tris["num_lods"] = "ERR " + type(_e).__name__
                    try:
                        _tris["num_vertices_lod0"] = _m.get_num_vertices(0)
                    except Exception as _e:
                        _tris["num_vertices_lod0"] = "ERR " + type(_e).__name__
                    _row["triangles"] = _tris
                    _row["triangle_count_measured"] = any(
                        isinstance(_v, int) and _v > 0
                        for _k, _v in _tris.items()
                        if "triangle" in _k.lower() or "num_triangles" in _k)

                    # -- Nanite, which changes what the count MEANS ---------
                    try:
                        _ns = _m.get_editor_property("nanite_settings")
                        _row["nanite_enabled"] = bool(
                            _ns.get_editor_property("enabled"))
                    except Exception as _e:
                        _row["nanite_enabled"] = "ERR " + type(_e).__name__

                    # -- RAY TRACING ON THE BUILT MESH -----------------------
                    # `UStaticMesh::bSupportRayTracing` (StaticMesh.h:1385).
                    # The layer's builder setting is an INPUT; this is whether
                    # the mesh that came out actually carries an acceleration
                    # structure, which is the thing that cost 12,434 MiB of
                    # VRAM and hung the GPU twice. Read the OUTPUT.
                    try:
                        _row["mesh_support_ray_tracing"] = bool(
                            _m.get_editor_property("support_ray_tracing"))
                    except Exception as _e:
                        _row["mesh_support_ray_tracing"] = (
                            "ERR " + type(_e).__name__)

                    # -- materials ------------------------------------------
                    _mats = []
                    try:
                        for _mi in _m.get_editor_property("static_materials"):
                            _iface = _mi.get_editor_property("material_interface")
                            _mats.append({
                                "slot": str(_mi.get_editor_property("material_slot_name")),
                                "material": _path(_iface),
                                "class": (_iface.get_class().get_name()
                                          if _iface else None),
                            })
                    except Exception as _e:
                        _row["materials_error"] = (type(_e).__name__ + ": "
                                                   + str(_e))
                    _row["materials"] = _mats
                _comps.append(_row)
            _out["static_mesh_components"] = _comps
            _out["component_count"] = len(_comps)

            _ok = any(_c.get("triangle_count_measured") for _c in _comps)
            _out["can_conclude"] = bool(_ok)
            _out["verdict"] = ("BUILT -- geometry present and counted" if _ok
                               else "NO TRIANGLES MEASURED -- treat as unbuilt")
    del _w
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["verdict"] = "COULD NOT LOOK"
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
