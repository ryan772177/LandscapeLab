"""probe_hlod_layer_refs.py -- is the Landscape HLOD layer IN FORCE?

READ-ONLY. The exhaustive dump reported "0 actors name an HLOD layer"
across 4,339 actors, and a 0 from a loop with a bare `except: continue`
is not a measurement -- it cannot tell "read fine, value is None" from
"the read raised on every actor". This separates the three outcomes and
counts them, which is the whole difference between an inert field and a
field that could not be read.

Name is ground truth from the header, not memory:
  Engine/Source/Runtime/Engine/Classes/GameFramework/Actor.h:1058
  TObjectPtr<class UHLODLayer> HLODLayer;   -> "hlod_layer"

Also re-reads the two values the 2026-09-13 write set, from the freshly
loaded asset: material_settings.texture_sizing_type and
mesh_merge_settings.merge_materials.
"""
import json as _json
import traceback as _tb

import unreal as _u

_out = {"ok": False}

try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()
    _raised, _none, _set = 0, 0, []
    _err_sample = None
    _by_class_set = {}
    for _a in _actors:
        try:
            _l = _a.get_editor_property("hlod_layer")
        except Exception as _e:
            _raised += 1
            if _err_sample is None:
                _err_sample = "%s on %s: %s" % (
                    type(_e).__name__, _a.get_class().get_name(), _e)
            continue
        if _l is None:
            _none += 1
        else:
            _c = _a.get_class().get_name()
            _by_class_set[_c] = _by_class_set.get(_c, 0) + 1
            if len(_set) < 20:
                _set.append({"actor": _a.get_actor_label(), "class": _c,
                             "layer": _l.get_path_name()})
    _out["n_actors"] = len(_actors)
    _out["hlod_layer_read_raised"] = _raised
    _out["hlod_layer_is_none"] = _none
    _out["hlod_layer_is_set"] = sum(_by_class_set.values())
    _out["hlod_layer_set_by_class"] = _by_class_set
    _out["hlod_layer_set_sample"] = _set
    _out["first_read_error"] = _err_sample

    # The landscape specifically -- named, not inferred from a count.
    _ls = [_a for _a in _actors
           if _a.get_class().get_name() in ("Landscape",
                                            "LandscapeStreamingProxy")]
    _out["n_landscape_actors"] = len(_ls)
    _lrows = []
    for _a in _ls[:4]:
        _r = {"label": _a.get_actor_label(),
              "class": _a.get_class().get_name()}
        try:
            _l = _a.get_editor_property("hlod_layer")
            _r["hlod_layer"] = _l.get_path_name() if _l else None
        except Exception as _e:
            _r["hlod_layer"] = "RAISED: %s" % type(_e).__name__
        _lrows.append(_r)
    _out["landscape_sample"] = _lrows

    # The 2026-09-13 write, read back from the freshly loaded asset.
    _L = _u.EditorAssetLibrary.load_asset("/Game/Alpine8K_HLODLayer_Landscape")
    _bs = _L.get_editor_property("hlod_builder_settings")
    _mm = _bs.get_editor_property("mesh_merge_settings")
    _ms = _mm.get_editor_property("material_settings")
    _out["write_0913_readback"] = {
        "builder_settings_class": type(_bs).__name__,
        "merge_materials": bool(_mm.get_editor_property("merge_materials")),
        "texture_sizing_type": str(
            _ms.get_editor_property("texture_sizing_type")),
        "texture_size": str(_ms.get_editor_property("texture_size")),
        "lod_selection_type": str(_mm.get_editor_property("lod_selection_type")),
        "use_texture_binning": bool(
            _mm.get_editor_property("use_texture_binning")),
    }
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()

print("__LL__" + _json.dumps(_out, indent=1, default=str))
