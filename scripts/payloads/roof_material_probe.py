"""roof_material_probe -- READ-ONLY census of the town's whole-roof meshes and their materials (2026-10-11 roof
variety, research/town_kit/ROOF_VARIETY.md). Per roof mesh: material slot count, slot names, the slot's material
path; per material: parent chain, base material, every scalar / vector / texture parameter name with the value
the instance resolves to. Writes and saves nothing.

Input (substituted): ROOFS = JSON list of /Game/ static-mesh paths.
"""
import json as _json
import unreal as _u

ROOFS = _json.loads(r'''__ROOFS__''')
_eal = _u.EditorAssetLibrary
_mel = _u.MaterialEditingLibrary
_out = {"ok": False, "roofs": {}, "materials": {}}
try:
    _mats = []
    for _p in ROOFS:
        _m = _eal.load_asset(_p)
        if _m is None or not isinstance(_m, _u.StaticMesh):
            raise RuntimeError("not a StaticMesh: " + _p)
        _slots = []
        for _i, _sm in enumerate(_m.static_materials):
            _mi = _sm.material_interface
            _mp = _mi.get_path_name().split(".")[0] if _mi else None
            _slots.append({"index": _i, "slot": str(_sm.material_slot_name), "material": _mp})
            if _mi is not None and _mp not in _mats:
                _mats.append(_mp)
        _nan = _m.get_editor_property("nanite_settings")
        _out["roofs"][_p] = {"n_slots": len(_slots), "slots": _slots,
                             "nanite": bool(_nan.enabled) if _nan is not None else None}
    for _mp in _mats:
        _mi = _eal.load_asset(_mp)
        rec = {"class": _mi.get_class().get_name()}
        chain, cur = [], _mi
        while isinstance(cur, _u.MaterialInstance):
            par = cur.get_editor_property("parent")
            chain.append(par.get_path_name().split(".")[0] if par else None)
            cur = par
        rec["parent_chain"] = chain
        if isinstance(_mi, _u.MaterialInstance):
            rec["scalars"] = dict((str(n), _mel.get_material_instance_scalar_parameter_value(_mi, n))
                                  for n in _mel.get_scalar_parameter_names(_mi))
            rec["vectors"] = {}
            for n in _mel.get_vector_parameter_names(_mi):
                v = _mel.get_material_instance_vector_parameter_value(_mi, n)
                rec["vectors"][str(n)] = [v.r, v.g, v.b, v.a]
            rec["textures"] = {}
            for n in _mel.get_texture_parameter_names(_mi):
                t = _mel.get_material_instance_texture_parameter_value(_mi, n)
                rec["textures"][str(n)] = t.get_path_name().split(".")[0] if t else None
            rec["static_switches"] = dict((str(n), bool(_mel.get_material_instance_static_switch_parameter_value(_mi, n)))
                                          for n in _mel.get_static_switch_parameter_names(_mi))
        _out["materials"][_mp] = rec
    _out["ok"] = True
except Exception:
    import traceback as _tb
    _out["error"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, indent=1, default=str))
