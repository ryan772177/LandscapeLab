import json as _json
import unreal as _u

# HLOD SHARE PASS -- hide or show every WorldPartitionHLOD actor and READ BACK
# the hidden count (rule 13: the A/B is only valid if the hide is verified).
# MODE is substituted by ue_exec --set (hide|show). Transient editor visibility
# only -- set_is_temporarily_hidden_in_editor does NOT dirty or save the actor.
_MODE = "__MODE__"
_hide = (_MODE == "hide")
_eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
_hlod = [a for a in _eas.get_all_level_actors()
         if a and "HLOD" in a.get_class().get_name()]
for a in _hlod:
    a.set_is_temporarily_hidden_in_editor(_hide)
# read back
_hidden = sum(1 for a in _hlod if a.is_temporarily_hidden_in_editor())
_out = {"mode": _MODE, "hlod_total": len(_hlod), "hidden_now": _hidden,
        "verified": (_hidden == len(_hlod)) if _hide else (_hidden == 0)}
print(_json.dumps(_out))
