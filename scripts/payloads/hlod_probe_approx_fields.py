"""Dump the REFLECTED property names of FMeshApproximationSettings. READ-ONLY.

`bSupportRayTracing` and `bGenerateNaniteEnabledMesh` exist in C++
(`MeshApproximationSettings.h:195, :211`) and BOTH failed as
`b_support_ray_tracing` / `b_generate_nanite_enabled_mesh`. UE's Python binding
strips a leading `b` from booleans -- `bIsSpatiallyLoaded` is reachable as
`is_spatially_loaded` -- so the names are probably `support_ray_tracing` and
`generate_nanite_enabled_mesh`. That is a HYPOTHESIS; this prints the contract
instead of testing another guess one round trip at a time.

Run via: python scripts/ue_exec.py scripts/payloads/hlod_probe_approx_fields.py
"""
import json as _json

import unreal as _u

_out = {"error": None}
try:
    _lay = _u.load_asset("/Game/Alpine8K_HLODLayer_Merged")
    _bs = _lay.get_editor_property("hlod_builder_settings")
    _ms = _bs.get_editor_property("mesh_approximation_settings")
    _out["settings_class"] = _bs.get_class().get_name()
    _out["struct"] = type(_ms).__name__

    # The struct's own reflected surface.
    _names = sorted(n for n in dir(_ms) if not n.startswith("__"))
    _out["all_dir"] = _names
    _out["ray_or_nanite"] = [n for n in _names
                             if "ray" in n.lower() or "nanite" in n.lower()]
    _out["tri_or_simplify"] = [n for n in _names
                               if "tri" in n.lower() or "simplif" in n.lower()]

    # And prove which of the candidate names actually READ.
    _probe = {}
    for _n in ("support_ray_tracing", "b_support_ray_tracing",
               "generate_nanite_enabled_mesh", "b_generate_nanite_enabled_mesh",
               "target_tri_count", "simplify_method", "triangles_per_m"):
        try:
            _probe[_n] = str(_ms.get_editor_property(_n))
        except Exception as _e:
            _probe[_n] = "ERR " + type(_e).__name__
    _out["read_probe"] = _probe
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-800:]

print("__LL__" + _json.dumps(_out))
