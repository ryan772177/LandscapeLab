"""brief5_v3_imposter.py -- Brief 5 V3: read the spruce_half imposter for a
root-cause of the tiling. READ-ONLY (no spawn, no save, no material edit).

Reads: spruce_half_01 LOD4 material (the imposter MI) -> its base material +
material functions -> inputs/defaults (frame grid, pivot/bounds, custom-primitive
-data / per-instance requirement); the MI_half_01_imposter_nowind override vs the
vendor MI parameter lists; and searches PN_interactiveSpruceForest for a demo map.
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
IMPOSTER_MI = "/Game/PN_interactiveSpruceForest/Materials/MaterialInstances/imposter/high/half_01_imposter"
NOWIND_MI = "/Game/PN_interactiveSpruceForest/Materials/MaterialInstances/imposter/high/MI_half_01_imposter_nowind"

out = {"ok": False}
try:
    eal = _u.EditorAssetLibrary
    mel = _u.MaterialEditingLibrary
    ar = _u.AssetRegistryHelpers.get_asset_registry()

    def mi_params(path):
        rec = {"path": path, "exists": eal.does_asset_exist(path)}
        if not rec["exists"]:
            return rec
        mi = eal.load_asset(path)
        rec["class"] = mi.get_class().get_name()
        base = mi.get_base_material() if hasattr(mi, "get_base_material") else None
        rec["base_material"] = base.get_path_name() if base else None
        rec["scalars"] = {}
        rec["vectors"] = {}
        try:
            for pn in mel.get_scalar_parameter_names(base or mi):
                try:
                    rec["scalars"][str(pn)] = mel.get_material_instance_scalar_parameter_value(mi, pn)
                except Exception:
                    pass
            for pn in mel.get_vector_parameter_names(base or mi):
                try:
                    v = mel.get_material_instance_vector_parameter_value(mi, pn)
                    rec["vectors"][str(pn)] = [round(v.r, 3), round(v.g, 3), round(v.b, 3), round(v.a, 3)]
                except Exception:
                    pass
        except Exception as e:
            rec["param_error"] = str(e)
        return rec

    out["imposter_mi"] = mi_params(IMPOSTER_MI)
    out["nowind_mi"] = mi_params(NOWIND_MI)

    # base material's referenced material functions + their names (imposter grid
    # usually lives in an octahedral-imposter MF)
    base_path = out["imposter_mi"].get("base_material")
    funcs = []
    if base_path:
        base = eal.load_asset(base_path.split(".")[0]) if base_path else None
        try:
            # get_material_used_textures gives textures; for functions, inspect
            # via the material's expression graph is heavy -- instead flag any
            # scalar/vector param whose NAME implies frames/pivot/bounds.
            interesting = {}
            for k, v in out["imposter_mi"].get("scalars", {}).items():
                if any(w in k.lower() for w in ("frame", "imposter", "pivot",
                                                "bound", "count", "grid", "size",
                                                "octahedron", "octahedral")):
                    interesting[k] = v
            out["frame_grid_candidates"] = interesting
        except Exception as e:
            out["func_error"] = str(e)
    out["material_functions"] = funcs

    # scan the vendor pack for a demo/sample map
    maps = []
    for a in eal.list_assets("/Game/PN_interactiveSpruceForest", recursive=True):
        if a.lower().endswith("_c"):
            continue
        ad = eal.find_asset_data(a) if hasattr(eal, "find_asset_data") else None
        cls = str(ad.asset_class_path.asset_name) if ad and hasattr(ad, "asset_class_path") else ""
        if cls == "World" or a.lower().endswith(("map", "demo", "showcase", "overview", "example")):
            maps.append(a)
    out["candidate_demo_maps"] = maps[:20]
    out["ok"] = True
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    dest = _os.path.join(_root, "research", "brief5", "input", "imposter_defect_read.json")
    _json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = dest
except Exception as e:
    out["write_error"] = str(e)
print("__LL__" + _json.dumps({"ok": out.get("ok"), "error": out.get("error"),
                              "frame_grid": out.get("frame_grid_candidates"),
                              "demo_maps": out.get("candidate_demo_maps"),
                              "written": out.get("written_to")}, default=str))
