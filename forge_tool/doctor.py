"""forge doctor — first-run environment preflight.

Every check prints PASS/WARN/FAIL with the exact fix, because the
audience is a friend who has never seen this repo: a failed check must
tell them what to type next, not what went wrong internally.

Usage: python -m forge_tool.cli doctor   (or python -m forge_tool.doctor)
Exit: 0 all pass (warnings allowed), 2 any FAIL.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))


def _row(state, label, detail):
    mark = {"PASS": "ok  ", "WARN": "warn", "FAIL": "FAIL"}[state]
    print("  [%s] %-28s %s" % (mark, label, detail))
    return state


def main(argv=None):
    print("forge doctor — checking this machine\n")
    results = []

    # python version
    v = sys.version_info
    results.append(_row(
        "PASS" if v >= (3, 11) else "FAIL", "Python 3.11+",
        "%d.%d.%d" % v[:3] if v >= (3, 11) else
        "%d.%d found — install Python 3.11+ and re-run" % v[:2]))

    # required packages
    for mod, pipname, needed_for in (
            ("numpy", "numpy", "terrain math"),
            ("PIL", "Pillow", "image IO"),
            ("scipy", "scipy", "erosion"),
            ("anthropic", "anthropic", "optional experimental auto-read "
             "— the standard keyless path works without it")):
        try:
            importlib.import_module(mod)
            results.append(_row("PASS", pipname, "installed"))
        except ImportError:
            state = "WARN" if pipname == "anthropic" else "FAIL"
            results.append(_row(
                state, pipname,
                "missing (%s) — pip install %s" % (needed_for, pipname)))

    # UE 5.8
    try:
        from engine_paths import resolve_engine_root
        root = resolve_engine_root()
        results.append(_row("PASS", "Unreal Engine 5.8", root))
        bat = os.path.join(root, "Engine", "Build", "BatchFiles",
                           "Build.bat")
        results.append(_row(
            "PASS" if os.path.isfile(bat) else "FAIL",
            "UE build tools", bat if os.path.isfile(bat) else
            "Build.bat missing — repair the UE 5.8 install"))
    except Exception as e:
        results.append(_row("FAIL", "Unreal Engine 5.8", str(e)))
        results.append(_row("FAIL", "UE build tools",
                            "skipped (engine not found)"))

    # project state
    proj = os.path.join(REPO, "LandscapeLab", "LandscapeLab.uproject")
    if os.path.isfile(proj):
        dll = os.path.join(REPO, "LandscapeLab", "Plugins",
                           "LandscapeLabEditor", "Binaries", "Win64",
                           "UnrealEditor-LandscapeLabEditor.dll")
        results.append(_row("PASS", "UE project", proj))
        results.append(_row(
            "PASS" if os.path.isfile(dll) else "WARN", "plugin compiled",
            "yes" if os.path.isfile(dll) else
            "not yet — run: python -m forge_tool.cli init --dest \"%s\" "
            "--compile" % REPO))
    else:
        results.append(_row(
            "FAIL", "UE project",
            "missing — run: python -m forge_tool.cli init --dest \"%s\" "
            "--compile" % REPO))
        results.append(_row("WARN", "plugin compiled", "skipped"))

    # stamps + catalogue
    cat = os.path.join(REPO, "recipes", "forge_stamps_catalogue.json")
    results.append(_row(
        "PASS" if os.path.isfile(cat) else "FAIL", "stamp catalogue",
        cat if os.path.isfile(cat) else "missing from the distribution"))

    # disk space (a build writes ~2 GB of engine intermediates)
    free_gb = shutil.disk_usage(REPO).free / 1e9
    results.append(_row(
        "PASS" if free_gb > 10 else "WARN", "free disk",
        "%.0f GB%s" % (free_gb,
                       "" if free_gb > 10 else
                       " — a build wants ~10 GB headroom")))

    # editor already running?
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq UnrealEditor.exe", "/NH"],
            capture_output=True, text=True, timeout=15).stdout or ""
        running = "UnrealEditor.exe" in out
        results.append(_row(
            "WARN" if running else "PASS", "editor state",
            "an UnrealEditor is RUNNING — a build will census it and "
            "refuses to close unsaved work" if running else
            "no editor running"))
    except Exception:
        results.append(_row("WARN", "editor state", "could not check"))

    # API key: NOT part of the product (ruled 2026-09-04) — the keyless
    # Layout Author path is standard, so no key is the expected state
    # and neither state is a warning
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY")
                   or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    results.append(_row(
        "PASS", "Anthropic API key",
        "set — optional auto-read available (EXPERIMENTAL, untested)"
        if has_key else
        "not set — not needed; the standard path is: forge author"))

    fails = sum(1 for r in results if r == "FAIL")
    warns = sum(1 for r in results if r == "WARN")
    print("\n%d check(s) failed, %d warning(s)." % (fails, warns))
    if fails:
        print("Fix the FAIL lines above, then re-run: "
              "python -m forge_tool.cli doctor")
    else:
        print("Ready. Try: python -m forge_tool.cli build "
              "examples/concept_highland_dusk.jpg --layout "
              "examples/duskhighland_layout.json --name myworld")
    return 2 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
