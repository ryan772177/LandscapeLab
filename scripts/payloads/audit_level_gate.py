"""audit_level_gate.py -- standing rule 11's LEVEL gate. READ-ONLY.

Rule 7 (bootstrap.py) proved the PROJECT. This proves the LEVEL. They
are different questions and the second is the one that produces a
plausible artefact from the wrong world: it renders clean, passes every
tonal check, and nothing downstream can detect it.
"""
import json as _json
import unreal as _unreal

_out = {}
_ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
_w = _ues.get_editor_world()
_out["world_name"] = _w.get_name()
_out["world_path"] = _w.get_path_name()
_out["world_partition"] = bool(_w.get_world_settings().is_partitioned_world()) \
    if hasattr(_w.get_world_settings(), "is_partitioned_world") else None

_eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
_actors = _eas.get_all_level_actors()
_out["n_actors"] = len(_actors)

# Count the classes that identify WHICH world this is, not how many
# things are in it. A landscape count of 0 on a level called Alpine8K
# means the proxies are unloaded, which changes what a capture means.
_counts = {}
for _a in _actors:
    _c = _a.get_class().get_name()
    _counts[_c] = _counts.get(_c, 0) + 1
_out["landscape_actors"] = {k: v for k, v in _counts.items()
                            if "Landscape" in k}
_out["light_actors"] = {k: v for k, v in _counts.items()
                        if any(s in k for s in ("Light", "Sky", "Fog",
                                                "Cloud", "PostProcess"))}
print("__LL__" + _json.dumps(_out))
