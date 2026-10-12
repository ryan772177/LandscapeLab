"""nav_autoupdate -- turn editor navigation auto-update OFF for a bulk placement, or record it back ON (2026-10-06).

Input (substituted): CFG = JSON {"action": "status" | "off" | "restore"}

Design review 2026-10-06 (research/town_kit/DESIGN.md answer (a), findings 2 and 7) + audit 2026-10-06 F2-F4:
ULevelEditorMiscSettings is NOT exported to Python (no BlueprintType, PyGenUtil.cpp:1537-1558) and objects have
no save_config, so both directions go through LandscapeLabEditor UFUNCTIONs:
  * "off":     set_editor_navigation_auto_update(False, apply_now=True) -- setting False, SaveConfig, and
               FNavigationSystem::SetNavigationAutoUpdateEnabled(false) (dirty areas stop accumulating, build
               lock NoUpdateInEditor added: NavigationSystem.cpp:1853-1878);
  * "restore": set_editor_navigation_auto_update(True, apply_now=False) -- config ON only. A live re-enable
               removes the lock with Rebuild and fires RebuildAll() in the editor (NavigationSystem.cpp:1868-1871,
               :4827-4834); instead the next launch applies the config (EditorEngine.cpp:1013) and the navmesh is
               rebuilt by R-NAVBUILD's commandlet, editor closed.
Read-back (rule 12): the setter's re-read comes from the GConfig CACHE (proves the setter ran); the nav system's
effective state (get_navigation_auto_update_enabled); and the ON-DISK ini, read by the driver
scripts/nav_autoupdate.py after this returns (re-audit 2026-10-06).
"""
import json as _json
import traceback as _tb
import unreal as _u

CFG = _json.loads(r'''__CFG__''')
_out = {"ok": False, "action": CFG.get("action")}
try:
    _L = _u.LandscapeLabTools

    def _effective():
        en, ok, err = _L.get_navigation_auto_update_enabled()
        if not ok:
            raise RuntimeError("nav read-back failed: %s" % err)
        return bool(en)

    _out["effective_before"] = _effective()
    act = CFG["action"]
    if act in ("off", "restore"):
        enable = act == "restore"
        cfgv, ok, err = _L.set_editor_navigation_auto_update(enable, not enable)
        _out.update({"config_after": bool(cfgv), "set_ok": bool(ok), "set_error": str(err) or None})
        _out["effective_after"] = _effective()
        if act == "off":
            _out["ok"] = bool(ok) and _out["config_after"] is False and _out["effective_after"] is False
        else:
            # by design the SESSION stays locked (effective False) until the next launch applies the config
            _out["ok"] = bool(ok) and _out["config_after"] is True
    elif act == "status":
        _out["ok"] = True
    else:
        raise RuntimeError("action must be status/off/restore, got %r" % act)
except Exception as e:
    _out["error"] = "%s: %s" % (type(e).__name__, e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, indent=1, default=str))
