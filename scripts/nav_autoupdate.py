"""nav_autoupdate.py -- driver for scripts/payloads/nav_autoupdate.py (editor nav auto-update off / restore).

    python scripts/nav_autoupdate.py status
    python scripts/nav_autoupdate.py off       # before a bulk placement or teardown
    python scripts/nav_autoupdate.py restore   # after the SAVE: config ON, no in-editor RebuildAll

See the payload docstring for the engine citations (design review 2026-10-06). A crash between off and restore
leaves the setting OFF in EditorPerProjectUserSettings for every later session; run `status` at session start
after any such crash.
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("status", "off", "restore"))
    a = ap.parse_args(argv)
    import ue_exec
    tpl = io.open(os.path.join(bootstrap.REPO_ROOT, "scripts", "payloads", "nav_autoupdate.py"),
                  encoding="utf-8").read()
    code, out, raw = ue_exec.run(tpl.replace("__CFG__", json.dumps({"action": a.action})), marker="__LL__",
                                 timeout=25, stage_name="nav_autoupdate")
    if not isinstance(out, dict):
        print("COULD NOT LOOK (code %s)\n%s" % (code, (raw or "")[-1500:]))
        return 4
    # rule 12 (re-audit 2026-10-06): the UFUNCTION's re-read comes from the GConfig CACHE SaveConfig just wrote
    # (Obj.cpp:3913, flushed at :3944); the next launch applies the FILE (EditorEngine.cpp:1013). Read the file.
    disk, src = ini_value()
    out["ini_on_disk"] = disk
    out["ini_source"] = src
    if a.action in ("off", "restore"):
        want = a.action == "restore"
        if disk is None:
            out["ok"] = False
            out["error"] = "bNavigationAutoUpdate not found in %s -- read nothing, not a pass" % INI
        elif disk != want:
            out["ok"] = False
            out["error"] = "ini on disk says %s, wanted %s" % (disk, want)
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok") else 4


INI = os.path.join(bootstrap.REPO_ROOT, "LandscapeLab", "Saved", "Config", "WindowsEditor",
                   "EditorPerProjectUserSettings.ini")


BASE_INI = os.path.join(r"C:\Program Files\Epic Games\UE_5.8", "Engine", "Config",
                        "BaseEditorPerProjectUserSettings.ini")


def _read_key(path):
    if not os.path.isfile(path):
        return None
    sec = None
    for line in io.open(path, encoding="utf-8-sig", errors="replace"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1]
        elif sec == "/Script/UnrealEd.LevelEditorMiscSettings" and s.lower().startswith("bnavigationautoupdate="):
            return s.split("=", 1)[1].strip().lower() == "true"
    return None


_P = os.path.join(bootstrap.REPO_ROOT, "LandscapeLab", "Config")
_E = os.path.join(r"C:\Program Files\Epic Games\UE_5.8", "Engine", "Config")
# highest priority first: the saved user ini, then the project's platform + default layers, then the engine's
LAYERS = [(INI, "saved ini"),
          (os.path.join(_P, "Windows", "WindowsEditorPerProjectUserSettings.ini"), "project Windows ini"),
          (os.path.join(_P, "DefaultEditorPerProjectUserSettings.ini"), "project Default ini"),
          (os.path.join(_E, "Windows", "WindowsEditorPerProjectUserSettings.ini"), "engine Windows ini"),
          (BASE_INI, "engine Base ini")]


def ini_value():
    """(value, source) of bNavigationAutoUpdate as the next launch will read it, or (None, None).

    SaveConfig DROPS a key whose value matches the COMBINED lower layers (ConfigCacheIni.cpp:2770, :2803-2805;
    measured 2026-10-08: restore=True left the key absent from the saved ini while off=False had written it), so
    an absent key means "whatever the next layer down says". The layers are read in priority order and the first
    one carrying the key answers, named as the source (audit 2026-10-08 F1)."""
    for path, name in LAYERS:
        v = _read_key(path)
        if v is not None:
            return v, name
    return None, None


if __name__ == "__main__":
    sys.exit(main())
