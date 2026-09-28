"""verify_gameplay_plugin.py — is LandscapeLabGameplay actually IN EFFECT?

PHASE2_PLAN.md unit 7's acceptance: "verified on a COLD BOOT — the file
records an override, never the state in effect. Three different ini files
have bitten this project on exactly that."

READ-ONLY. Loads nothing, spawns nothing, saves nothing.

=====================================================================
WHY THE .uplugin IS NOT THE ANSWER
=====================================================================
`LandscapeLabGameplay.uplugin` declares `EnabledByDefault: true` and lists
EnhancedInput, StateTree and GameplayStateTree as dependencies. That file is
a REQUEST. Non-negotiable 17: a config file records what was overridden and
never what is in effect, and this project has three recorded instances of
exactly that mechanism — `sg.*` in `[SystemSettings]`, `t.MaxFPS`, and
reading `Fab` as disabled from `.uproject`.

So every check here asks the RUNNING EDITOR:

  1. is the plugin in `get_enabled_plugin_names()`
  2. are its three declared dependencies in that same list — especially
     `GameplayStateTree`, which ships `EnabledByDefault: false` (ruling 1) and
     is therefore the one that proves the dependency list did any work
  3. are the C++ classes REFLECTED — a loaded module that exported nothing
     useful is not a working module
  4. does `ApplyMovementSpec` exist on the character with the right shape

=====================================================================
AND WHY THE CLASS CHECK IS SEPARATE FROM THE PLUGIN CHECK
=====================================================================
`get_enabled_plugin_names()` reports the plugin descriptor's state. It does
NOT prove the module's DLL loaded, nor that UHT generated anything. A plugin
can be "enabled" with a module that failed to load — and the editor carries
on. Asking for the reflected class is a different representation of the same
fact (non-negotiable 0), and it is the one that would catch a stale DLL.

Exit codes:
  0  the plugin, its dependencies and its classes are all in effect
  1  could not look
  3  rule 7: no verified editor node
  4  the plugin is NOT enabled, or a declared dependency is not
  5  the plugin is enabled but a class is NOT reflected — the module did not
     deliver
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_PLUG__"

PLUGIN = "LandscapeLabGameplay"
# Declared in the .uplugin's Plugins array. GameplayStateTree is the
# discriminating one: it ships EnabledByDefault false, so if it reads enabled
# here, the dependency list is what enabled it.
DEPENDENCIES = ("EnhancedInput", "StateTree", "GameplayStateTree")

# MetaHumanCharacter is enabled (Ryan's ruling, overturning PHASE2_PLAN.md
# ruling 14). It took four failed attempts, and the cause is now KNOWN:
#
#   MetaHumanCharacter.uplugin declares 20 plugin dependencies and
#   MetaHumanCoreTech IS NOT ONE OF THEM -- but it does not start without it.
#
# Every failed route enabled what the descriptor DECLARES. The Plugins UI,
# with "Core Data" also ticked, enabled what it actually NEEDS. So both must
# be named together; see LESSONS 2026-08-15 "THE CORE DATA".
#
# NOT in DEPENDENCIES: those are the plugins THIS project's .uplugin declares,
# and MetaHuman is currently enabled via .uproject instead. Reported below
# rather than gated, so the report stays true whichever route is in use.
#
# Reported, never gated. These are what MetaHumanCharacter would drag in, and
# they are the EXPENSIVE half: strand hair and cloth simulation are what a
# per-character cost measurement has to account for, and a dependency nobody
# wrote down is a cost nobody attributes. Several are ALREADY on for other
# reasons, which is exactly why they are worth printing.
METAHUMAN_HEAVY = ("MetaHumanCharacter", "MetaHumanCoreTech", "HairStrands",
                   "ChaosClothAsset", "ChaosOutfitAsset", "RigLogic",
                   "MetaHumanSDK")
CLASSES = ("LandscapeLabCharacter", "LandscapeLabGameMode")


PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "enabled": [], "classes": {}, "spec_fn": None,
        "plugin_dir": None, "unreadable": []}
try:
    try:
        _out["enabled"] = [str(_n) for _n in
                           _unreal.PluginBlueprintLibrary.get_enabled_plugin_names()]
    except Exception as _pe:
        _out["unreadable"].append("get_enabled_plugin_names: " + str(_pe))
    try:
        _out["plugin_dir"] = str(
            _unreal.PluginBlueprintLibrary.get_plugin_base_dir("__PLUGIN__"))
    except Exception:
        pass

    # A DIFFERENT REPRESENTATION of "the module loaded": ask for the class.
    # get_enabled_plugin_names reads the descriptor; this reads what UHT and
    # the linker actually produced.
    for _c in __CLASSES__:
        _rec = {"reflected": False, "path": None, "why": None}
        try:
            _cls = getattr(_unreal, _c, None)
            if _cls is None:
                _rec["why"] = "not present as unreal." + _c
            else:
                _rec["reflected"] = True
                try:
                    _cdo = _unreal.get_default_object(_cls)
                    _rec["path"] = _cdo.get_path_name() if _cdo else None
                except Exception as _de:
                    _rec["why"] = "class present, CDO unreachable: " + str(_de)
        except Exception as _ce:
            _rec["why"] = type(_ce).__name__ + ": " + str(_ce)
        _out["classes"][_c] = _rec

    # The UFUNCTION itself. A reflected class whose function is missing means
    # the header and the built DLL disagree -- a stale binary reads exactly
    # like a working one until something calls it.
    _ch = getattr(_unreal, "LandscapeLabCharacter", None)
    if _ch is not None:
        _out["spec_fn"] = bool(hasattr(_ch, "apply_movement_spec"))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_PLUG__" + _json.dumps(_out))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(
            PAYLOAD.replace("__PLUGIN__", PLUGIN)
                   .replace("__CLASSES__", repr(list(CLASSES))),
            unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
        i = text.find(MARKER)
        if i < 0:
            print("NO MARKER — could not look.")
            print(text[:1500])
            return 1
        d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1
    for u in d.get("unreadable", []):
        print("UNREADABLE:", u)

    enabled = set(d.get("enabled") or ())
    rc = 0
    print("=== UNIT 7 — is LandscapeLabGameplay IN EFFECT? ===")
    print("  (read from the RUNNING EDITOR, not from the .uplugin)")
    print("")
    print("--- 1. the plugin itself ---")
    if not enabled:
        print("  COULD NOT LOOK: the enabled-plugin list came back empty.")
        print("  That is not the same as 'nothing is enabled'.")
        return 1
    ok = PLUGIN in enabled
    print("  %-22s %s" % (PLUGIN, "ENABLED" if ok else "NOT ENABLED"))
    print("  base dir  %s" % d.get("plugin_dir"))
    if not ok:
        rc = max(rc, 4)

    print("")
    print("--- 2. its declared dependencies ---")
    for dep in DEPENDENCIES:
        got = dep in enabled
        note = ""
        if dep == "GameplayStateTree":
            note = ("   <- ships EnabledByDefault FALSE, so this one proves "
                    "the dependency list did the work")
        print("  %-22s %s%s" % (dep, "ENABLED" if got else "NOT ENABLED", note))
        if not got:
            rc = max(rc, 4)

    print("")
    print("--- 2b. the MetaHuman stack — REPORTED, NEVER GATED ---")
    for dep in METAHUMAN_HEAVY:
        print("  %-22s %s" % (dep, "ENABLED" if dep in enabled else "not enabled"))
    if "MetaHumanCharacter" in enabled and "MetaHumanCoreTech" not in enabled:
        print("")
        print("  WARNING: MetaHumanCharacter WITHOUT MetaHumanCoreTech.")
        print("  That combination hung this editor at module load four times.")
        print("  MetaHumanCharacter.uplugin does NOT declare MetaHumanCoreTech")
        print("  among its 20 dependencies, and does not start without it.")
    print("  Strand hair and cloth are the expensive half of a character, and")
    print("  several are on for other reasons — a dependency nobody wrote")
    print("  down is a cost nobody attributes, which is why all are printed.")

    print("")
    print("--- 3. the C++ classes, a DIFFERENT representation ---")
    print("  get_enabled_plugin_names reads the DESCRIPTOR. These read what")
    print("  UHT and the linker actually produced, which is what would catch")
    print("  a stale or unloaded DLL.")
    for c in CLASSES:
        rec = (d.get("classes") or {}).get(c, {})
        print("  unreal.%-24s %s%s"
              % (c, "REFLECTED" if rec.get("reflected") else "MISSING",
                 "   " + rec["why"] if rec.get("why") else ""))
        if rec.get("path"):
            print("      CDO  %s" % rec["path"])
        if not rec.get("reflected"):
            rc = max(rc, 5)

    print("")
    print("--- 4. the UFUNCTION ---")
    fn = d.get("spec_fn")
    if fn is None:
        print("  COULD NOT LOOK — the character class was not reflected.")
        rc = max(rc, 5)
    else:
        print("  apply_movement_spec  %s" % ("PRESENT" if fn else "MISSING"))
        if not fn:
            print("  The header and the built DLL disagree. A stale binary")
            print("  reads exactly like a working one until something calls it.")
            rc = max(rc, 5)

    print("")
    print("VERDICT: %s" % ("IN EFFECT" if rc == 0 else "see the rows above"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
