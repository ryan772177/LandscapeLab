"""Set ONLY `ApproximationAccuracy` on the HLOD layer, and read the whole
budget back. Everything else is left exactly as `hlod_set_proxy_budget.py` left
it.

WHY THIS FIELD AND NOT `target_tri_count`
    `TargetTriCount` is the SIMPLIFIER's target -- it governs the mesh that
    comes OUT. The cost of MeshApproximate is the VOXEL GRID it builds first,
    and that is governed by `ApproximationAccuracy`
    (`MeshApproximationSettings.h:73-75`): *"Approximation Accuracy in Meters,
    will determine (eg) voxel resolution"*. Reducing the triangle target does
    not make the voxelisation cheaper; reducing the accuracy does.

    Measured on the first MeshApproximate attempt, at the default accuracy:
    265 cells in 52.4 min = **5.06 actors/min**, which extrapolates to hours.

THE UNITS ARE METRES, AND THE DEFAULT IS 1.0
    `float ApproximationAccuracy = 1.0f`, `DisplayName = "Approximation
    Accuracy (meters)"`. A value of 150 would mean 150-METRE accuracy on a
    254 m cell -- roughly two voxels across -- and would destroy the proxy
    rather than speed it up. The intent "150 cm" is therefore **1.5**.

THE BASIS FOR 1.5 m
    The budget puts 4,000 triangles on a 254 m cell, i.e. quad edge
    254/sqrt(2000) = 5.68 m. A voxel at roughly a quarter of the quad edge
    (1.42 m, taken as 1.5) resolves everything the simplifier can keep and
    nothing it must discard: features finer than a quarter-quad cannot survive
    decimation to 5.68 m quads. Checked against the band the proxy serves --
    at 2 km a 1.5 m voxel subtends 1.5/2000 rad = 1.8 px, already under the
    6 px shape threshold, so the voxel grid is not resolving anything the
    viewer could see as shape.

    Voxel COUNT is what costs, and it falls as the cube of accuracy:
        accuracy 1.0 m -> 254 voxels across the cell
        accuracy 1.5 m -> 169 voxels across      (~3.4x fewer in 3D)
    `ClampVoxelDimension` is 1024 (`:79`), so 169 is nowhere near the clamp and
    the accuracy value governs rather than being silently limited.

    THAT IS A PREDICTION OF COST, NOT A MEASUREMENT. One cell is rebuilt and
    timed before anything is launched across the world.

Run via:
    python scripts/ue_exec.py scripts/payloads/hlod_set_approx_accuracy.py \
        --set LAYER=/Game/Alpine8K_HLODLayer_Merged.Alpine8K_HLODLayer_Merged \
        --set ACCURACY_M=1.5
"""
import json as _json

import unreal as _u

LAYER = "__LAYER__"
ACCURACY_M = float("__ACCURACY_M__")

_out = {"error": None, "layer": LAYER, "requested_accuracy_m": ACCURACY_M}
try:
    if ACCURACY_M > 10.0:
        raise ValueError(
            "REFUSING accuracy %.3f -- the field is in METRES and anything "
            "above ~10 would be coarser than the objects being approximated. "
            "150 cm is 1.5, not 150." % ACCURACY_M)

    _lay = _u.load_asset(LAYER)
    _bs = _lay.get_editor_property("hlod_builder_settings")
    _ms = _bs.get_editor_property("mesh_approximation_settings")

    _out["before"] = {
        "approximation_accuracy": _ms.get_editor_property("approximation_accuracy"),
        "clamp_voxel_dimension": _ms.get_editor_property("clamp_voxel_dimension"),
        "target_tri_count": _ms.get_editor_property("target_tri_count"),
        "support_ray_tracing": bool(_ms.get_editor_property("support_ray_tracing")),
    }

    _ms.set_editor_property("approximation_accuracy", ACCURACY_M)
    _bs.set_editor_property("mesh_approximation_settings", _ms)
    # save_asset's return is the disk-persistence signal; the read-back below
    # uses load_asset (the RESIDENT in-memory object), so it verifies the struct
    # write-back, not the disk save -- capture and require both.
    _out["saved"] = bool(_u.EditorAssetLibrary.save_asset(LAYER.split(".")[0]))

    # ---- READ BACK from a freshly loaded asset --------------------------
    _rb = _u.load_asset(LAYER)
    _rbs = _rb.get_editor_property("hlod_builder_settings")
    _rms = _rbs.get_editor_property("mesh_approximation_settings")
    _rmat = _rms.get_editor_property("material_settings")
    _out["after"] = {
        "approximation_accuracy": _rms.get_editor_property("approximation_accuracy"),
        "clamp_voxel_dimension": _rms.get_editor_property("clamp_voxel_dimension"),
        # the three that must be UNCHANGED
        "target_tri_count": _rms.get_editor_property("target_tri_count"),
        "simplify_method": str(_rms.get_editor_property("simplify_method")),
        "support_ray_tracing": bool(_rms.get_editor_property("support_ray_tracing")),
        "generate_nanite_enabled_mesh": bool(
            _rms.get_editor_property("generate_nanite_enabled_mesh")),
        "texture_size": str(_rmat.get_editor_property("texture_size")),
        "layer_type": str(_rb.get_editor_property("layer_type")),
    }
    _b, _a = _out["before"], _out["after"]
    _out["accuracy_applied"] = abs(_a["approximation_accuracy"] - ACCURACY_M) < 1e-6
    # `a == b is False` was a chained comparison -- (a == b) AND (b is False) --
    # so others_unchanged was forced False whenever ray tracing was ever ON,
    # regardless of whether it CHANGED. The stated intent (line above) is
    # UNCHANGED, so compare the two directly.
    _out["others_unchanged"] = bool(
        _a["target_tri_count"] == _b["target_tri_count"]
        and _a["support_ray_tracing"] == _b["support_ray_tracing"])
    _out["voxels_across_cell_254m"] = round(254.0 / ACCURACY_M, 1)
    _out["verdict"] = ("APPLIED, others unchanged"
                       if (_out["accuracy_applied"] and _out["others_unchanged"]
                           and _out.get("saved"))
                       else "CHECK -- accuracy/neighbour wrong, or save failed")
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["verdict"] = "COULD NOT LOOK"
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
