"""Re-budget the HLOD proxy layer from the BLOB BAND, and read every value back.

WHY THE FIRST BUILD WAS WRONG, structurally and not just numerically
    `Alpine8K_HLODLayer_Merged` was `MeshMerge`. **`FMeshMergingSettings` has no
    triangle-reduction field at all** -- `LODSelectionType`/`SpecificLOD` choose
    WHICH SOURCE LOD to merge, `MaterialSettings` controls the baked texture,
    and nothing decimates. MeshMerge CONCATENATES. That is why one 254 m cell
    came out at 329,364 triangles: it is the sum of its sources.

    So this is a LAYER TYPE change, not a settings tweak. Of the types that can
    reduce (`HLODLayer.h:31-38`):
        Instancing / MeshMerge      cannot reduce
        MeshSimplify                FMeshProxySettings -- ScreenSize/VoxelSize,
                                    no direct triangle target
        MeshApproximate             FMeshApproximationSettings -- has
                                    SimplifyMethod + TargetTriCount, which is
                                    the control the budget is expressed in
    -> MeshApproximate.

THE BUDGET, derived rather than chosen
    4K/90 deg renders at 42.67 ppd (REGISTER, PROVEN, B1.3).
    Blob band = 1.5-6 px (Brief 1's four-band ladder).
    Merged L0 cell = 25400 cm = 254 m (derived label grid, R-HLOD 08b).

    A proxy triangle should be no finer than the smallest feature that reads at
    the distance where the proxy IS the representation. For N triangles as a
    grid, quad edge = 254 / sqrt(N/2) metres, and its angular size in px is
    (edge/d) * 57.2958 * 42.67.

        N = 4000   edge 5.68 m   6.9 px @2km   3.5 px @4km   1.7 px @8km
        N = 329364 edge 0.63 m   0.77 px       0.38 px       0.19 px

    4,000 puts the quad edge inside the blob band across 2-8 km. The built
    proxy was SUB-PIXEL at every distance it is ever seen -- 82x too dense by
    count, and that is the measured form of "100x too dense".

    TEXTURE: at 2 km a 254 m cell spans ~310 px. A 512^2 bake over 254 m is
    0.50 m/texel = 0.61 px/texel at 2 km -- already finer than the pixel grid.
    1024^2 would be 0.30 px/texel, i.e. paying 4x memory for detail below the
    sampling limit. 512 chosen; 1024 is the ceiling, not the target.

    NANITE: NOT enabled. `bGenerateNaniteEnabledMesh` earns its cost on dense
    meshes; at 4,000 triangles a plain static mesh is cheaper in every respect,
    and Nanite would add a fallback mesh whose own RT representation is the
    thing we are removing. Revisit only if the triangle budget rises by an
    order of magnitude.

    RAY TRACING: `bSupportRayTracing` DEFAULTS TO TRUE
    (`MeshApproximationSettings.h:211`, and `FMeshMergingSettings` line 135 has
    the same field). That default is why 2,267 proxies each got an acceleration
    structure, and it is the direct suspect for the 12,434 MiB of VRAM measured
    at the crash against 812 MiB with `r.RayTracing=0`. An HLOD proxy standing
    in for objects at 1.5-6 px never needs to be ray traced. Set FALSE.

    `bForceRayTracingFarField` on the LAYER (`HLODLayer.h:154-155`) is an
    opt-IN, not an opt-out -- it ADDS spatially-loaded HLOD to the RT far
    field. It is already false and is left alone; it is not the lever.

READ-BACK IS THE POINT (standing rule 12)
    Changing `layer_type` is expected to swap `HLODBuilderSettings` to a
    different CLASS. Whether a Python property set triggers that swap is NOT
    assumed -- the payload re-reads the settings object, reports its class, and
    reports every field it managed to write. A field that did not take is
    reported as a mismatch rather than being silently skipped.

Run via:
    python scripts/ue_exec.py scripts/payloads/hlod_set_proxy_budget.py \
        --set LAYER=/Game/Alpine8K_HLODLayer_Merged --set TRIS=4000 \
        --set TEX=512 --set DRY_RUN=1
"""
import json as _json

import unreal as _u

LAYER = "__LAYER__"
TRIS = int("__TRIS__")
TEX = int("__TEX__")
DRY_RUN = bool(int("__DRY_RUN__"))

_out = {"error": None, "layer": LAYER, "dry_run": DRY_RUN,
        "target_tris": TRIS, "target_texture": TEX, "applied": {}, "readback": {}}


def _describe(_obj):
    _d = {}
    if _obj is None:
        return _d
    _d["_class"] = _obj.get_class().get_name()
    return _d


try:
    _lay = _u.load_asset(LAYER)
    if _lay is None:
        raise RuntimeError("layer asset did not load: " + LAYER)

    _out["before"] = {
        "layer_type": str(_lay.get_editor_property("layer_type")),
        "cell_size": _lay.get_editor_property("cell_size"),
        "loading_range": _lay.get_editor_property("loading_range"),
        "is_spatially_loaded": bool(_lay.get_editor_property("is_spatially_loaded")),
    }
    _bs0 = _lay.get_editor_property("hlod_builder_settings")
    _out["before"]["builder_settings_class"] = (
        _bs0.get_class().get_name() if _bs0 else None)

    if DRY_RUN:
        _out["verdict"] = "DRY_RUN -- nothing written"
    else:
        # ---- 1. layer type -------------------------------------------------
        _lay.set_editor_property("layer_type", _u.HLODLayerType.MESH_APPROXIMATE)
        _out["applied"]["layer_type"] = "MESH_APPROXIMATE"

        # Re-read: the settings object should now be the approximate one.
        _bs = _lay.get_editor_property("hlod_builder_settings")
        _out["readback"]["builder_settings_class_after_type_change"] = (
            _bs.get_class().get_name() if _bs else None)

        if _bs is None:
            _out["error"] = "no hlod_builder_settings after layer_type change"
        else:
            _ms = _bs.get_editor_property("mesh_approximation_settings")
            _out["readback"]["settings_struct"] = type(_ms).__name__

            # ---- 2. the budget --------------------------------------------
            _want = {
                "simplify_method": _u.MeshApproximationSimplificationPolicy.FIXED_TRIANGLE_COUNT,
                "target_tri_count": TRIS,
                # UE PYTHON STRIPS THE LEADING `b` FROM BOOLEANS.
                # `b_support_ray_tracing` raises "Failed to find property";
                # `support_ray_tracing` works. Same rule as
                # bIsSpatiallyLoaded -> is_spatially_loaded. Probed, not guessed
                # (hlod_probe_approx_fields.py).
                "support_ray_tracing": False,
                "generate_nanite_enabled_mesh": False,
            }
            for _k, _v in _want.items():
                try:
                    _ms.set_editor_property(_k, _v)
                    _out["applied"][_k] = str(_v)
                except Exception as _e:
                    _out["applied"][_k] = "FAILED " + type(_e).__name__ + ": " + str(_e)

            # ---- 3. baked material texture ---------------------------------
            try:
                _mat = _ms.get_editor_property("material_settings")
                _mat.set_editor_property(
                    "texture_sizing_type",
                    _u.TextureSizingType.TEXTURE_SIZING_TYPE_USE_MANUAL_OVERRIDE_TEXTURE_SIZE)
                _mat.set_editor_property("texture_size", _u.IntPoint(TEX, TEX))
                _ms.set_editor_property("material_settings", _mat)
                _out["applied"]["material_settings"] = "manual %dx%d" % (TEX, TEX)
            except Exception as _e:
                _out["applied"]["material_settings"] = (
                    "FAILED " + type(_e).__name__ + ": " + str(_e))

            _bs.set_editor_property("mesh_approximation_settings", _ms)
            # save_asset's return is the disk-persistence signal; the read-back
            # below uses load_asset (the RESIDENT in-memory object), so it
            # verifies the write-back, not the disk save -- require both.
            _out["saved"] = bool(
                _u.EditorAssetLibrary.save_asset(LAYER.split(".")[0]))

            # ---- 4. READ BACK from a freshly loaded asset -------------------
            _rb = _u.load_asset(LAYER)
            _rbs = _rb.get_editor_property("hlod_builder_settings")
            _rms = _rbs.get_editor_property("mesh_approximation_settings")
            _rmat = _rms.get_editor_property("material_settings")
            _out["readback"].update({
                "layer_type": str(_rb.get_editor_property("layer_type")),
                "builder_settings_class": _rbs.get_class().get_name(),
                "simplify_method": str(_rms.get_editor_property("simplify_method")),
                "target_tri_count": _rms.get_editor_property("target_tri_count"),
                "support_ray_tracing": bool(
                    _rms.get_editor_property("support_ray_tracing")),
                "generate_nanite_enabled_mesh": bool(
                    _rms.get_editor_property("generate_nanite_enabled_mesh")),
                "texture_sizing_type": str(
                    _rmat.get_editor_property("texture_sizing_type")),
                "texture_size": str(_rmat.get_editor_property("texture_size")),
                "cell_size": _rb.get_editor_property("cell_size"),
                "loading_range": _rb.get_editor_property("loading_range"),
            })

            _ok = (bool(_out.get("saved"))
                   and _out["readback"].get("target_tri_count") == TRIS
                   and _out["readback"].get("support_ray_tracing") is False
                   and "MESH_APPROXIMATE" in _out["readback"].get("layer_type", ""))
            _out["verdict"] = ("APPLIED and read back" if _ok else
                               "MISMATCH -- one or more values did not take")
            _out["readback_matches"] = bool(_ok)
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["verdict"] = "COULD NOT LOOK"
    _out["trace"] = _tb.format_exc()[-1500:]

print("__LL__" + _json.dumps(_out))
