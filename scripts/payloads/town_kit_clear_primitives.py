"""town_kit_clear_primitives -- remove the engine-primitive town's buildings and roofs (2026-10-06 kit town).

Input (substituted): CFG = JSON {"level": "/Game/Alpine8K", "expect": 606, "commit": false}

Identifies by TAG, never by label (standing rule 8): actors carrying "LandscapeLab.City" AND a kind tag in
{"buildings", "roofs"} (the kinds scripts/city_place_payload.txt _emit()s at :263 and :304). Streets, landmark and
spire carry other kind tags and are counted, never touched. Dry run (commit false) reports the counts only.
Commit REFUSES unless the matched count == expect, destroys, checks every destroy_actor return, then re-enumerates
the level and reports what is left of each kind (read-back, rule 12). Does NOT save.
"""
import json as _json
import traceback as _tb
import unreal as _u

CFG = _json.loads(r'''__CFG__''')
# 2026-10-10 (organic re-layout): tag and kinds may be passed -- e.g. {"tag": "LandscapeLab.City", "kinds":
# ["streets"]} or {"tag": "LandscapeLab.TownKit", "kinds": null} (null = every actor with the tag). Defaults keep the
# original buildings+roofs teardown.
TAG = CFG.get("tag", "LandscapeLab.City")
# re-audit 2026-10-10 F1: CFG["kinds"] raised KeyError in the documented no-tag mode (key absent)
_k = CFG.get("kinds", ("buildings", "roofs"))
KINDS = tuple(_k) if _k is not None else None

_out = {"ok": False, "commit": bool(CFG.get("commit"))}


def _census(eas):
    by_kind, match = {}, []
    for a in eas.get_all_level_actors():
        tags = [str(t) for t in a.tags]
        if TAG not in tags:
            continue
        kind = next((t for t in tags if t != TAG), "<none>")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if KINDS is None or any(k in tags for k in KINDS):
            match.append(a)
    return by_kind, match


try:
    w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
    lvl = w.get_path_name().split(".")[0]
    _out["level"] = lvl
    if lvl != CFG["level"]:
        raise RuntimeError("open level is %s, cfg wants %s" % (lvl, CFG["level"]))
    eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    by_kind, match = _census(eas)
    _out["before_by_kind"] = by_kind
    _out["matched"] = len(match)
    _out["expect"] = int(CFG["expect"])
    if CFG.get("commit"):
        if len(match) != int(CFG["expect"]):
            raise RuntimeError("matched %d != expect %d -- refusing to destroy" % (len(match), int(CFG["expect"])))
        failed = [a.get_actor_label() for a in match if not eas.destroy_actor(a)]
        if failed:
            raise RuntimeError("destroy_actor returned False for %d actors, first %s" % (len(failed), failed[:5]))
        after, left = _census(eas)
        _out["after_by_kind"] = after
        _out["left_matching"] = len(left)
        _out["ok"] = len(left) == 0
    else:
        _out["ok"] = len(match) == int(CFG["expect"])
except Exception as e:
    _out["error"] = "%s: %s" % (type(e).__name__, e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, indent=1, default=str))
