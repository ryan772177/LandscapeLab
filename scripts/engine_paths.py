"""Single home for the UE engine install location.

Every script that needs the engine derives it from here, so the forge
distribution can retarget an end user's install with ONE env var instead
of editing vendored scripts:

    FORGE_ENGINE_ROOT   engine install dir (default: this machine's UE 5.8)

On the dev machine nothing changes: the default is the path bootstrap.py
and concept2level.py carried before this module existed. If the resolved
root does not exist, resolve_engine_root() can consult the Epic registry
key so a packaged forge finds the user's install without configuration.
"""
from __future__ import annotations

import os

_DEFAULT_ENGINE_ROOT = r"C:\Program Files\Epic Games\UE_5.8"

ENGINE_ROOT = os.environ.get("FORGE_ENGINE_ROOT", _DEFAULT_ENGINE_ROOT)

EDITOR_EXE = os.path.join(
    ENGINE_ROOT, "Engine", "Binaries", "Win64", "UnrealEditor.exe")
EDITOR_CMD_EXE = os.path.join(
    ENGINE_ROOT, "Engine", "Binaries", "Win64", "UnrealEditor-Cmd.exe")


def resolve_engine_root(version: str = "5.8") -> str:
    """ENGINE_ROOT if it exists on disk, else the Epic registry entry.

    Returns a directory that exists, or raises RuntimeError naming both
    places it looked. Never guesses a third location.
    """
    if os.path.isdir(ENGINE_ROOT):
        return ENGINE_ROOT
    reg_path = r"SOFTWARE\EpicGames\Unreal Engine\%s" % version
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as k:
            installed, _ = winreg.QueryValueEx(k, "InstalledDirectory")
        if os.path.isdir(installed):
            return installed
    except OSError:
        pass
    raise RuntimeError(
        "UE %s not found: FORGE_ENGINE_ROOT/default '%s' does not exist and "
        "HKLM\\%s has no valid InstalledDirectory. Install UE %s or set "
        "FORGE_ENGINE_ROOT." % (version, ENGINE_ROOT, reg_path, version))
