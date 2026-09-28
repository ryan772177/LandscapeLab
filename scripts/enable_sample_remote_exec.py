"""enable_sample_remote_exec.py — add bRemoteExecution=True to a sample
project's Config/DefaultEngine.ini so ue_exec and shoot.py can drive it.

STANDING RULE 1 SAYS NEVER WRITE OUTSIDE THIS REPO. This is a deliberate,
operator-authorised exception ("ruled: disposable copy, waiver covers it"),
and it is scripted rather than hand-edited so that:

  * the ORIGINAL is copied into this repo first, under
    research/census/config_backups/, so the change is reversible from here
    even if the sample copy is later deleted;
  * the edit is idempotent -- running twice does not append twice;
  * --revert puts the original back.

It writes ONE section. It does not touch .uproject, .uasset or .umap, which
standing rule 4 protects and which no waiver covers.
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUPS = os.path.join(REPO, "research", "census", "config_backups")

PROJECTS = {
    "ElectricDreams": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\ElectricDreamsSample_5.8\data",
    "ValleyOfTheAncient": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\AncientGame_5.7\data",
    "DarkRuins": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\DarkRuinac4b642bf8b9V1\data",
}

SECTION = "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]"
BLOCK = ("\n" + SECTION + "\n"
         "bRemoteExecution=True\n"
         "; Added by UE5LandscapePipeline census tooling, operator-authorised.\n"
         "; Lets ue_exec/shoot.py drive this editor. Remove with\n"
         ";   python scripts/enable_sample_remote_exec.py --project <p> --revert\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, choices=sorted(PROJECTS))
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()

    ini = os.path.join(PROJECTS[a.project], "Config", "DefaultEngine.ini")
    if not os.path.exists(ini):
        raise SystemExit("REFUSE: no DefaultEngine.ini at %s" % ini)
    os.makedirs(BACKUPS, exist_ok=True)
    backup = os.path.join(BACKUPS, "%s__DefaultEngine.ini.orig" % a.project)

    if a.revert:
        if not os.path.exists(backup):
            raise SystemExit("REFUSE: no backup at %s -- refusing to guess "
                             "what the original looked like" % backup)
        shutil.copy2(backup, ini)
        print("reverted %s from %s" % (ini, os.path.relpath(backup, REPO)))
        return 0

    # Back up ONCE, before the first edit, and never overwrite it -- a backup
    # taken after the edit would preserve the edit, not the original.
    if not os.path.exists(backup):
        shutil.copy2(ini, backup)
        print("backed up original -> %s" % os.path.relpath(backup, REPO))
    else:
        print("backup already present, left alone: %s"
              % os.path.relpath(backup, REPO))

    raw = io.open(ini, encoding="utf-8", errors="replace").read()
    if "bRemoteExecution=True" in raw:
        print("already enabled, nothing to do")
        return 0
    with io.open(ini, "a", encoding="utf-8") as fh:
        fh.write(BLOCK)
    after = io.open(ini, encoding="utf-8", errors="replace").read()
    ok = "bRemoteExecution=True" in after and SECTION in after
    print("wrote section to %s" % ini)
    print("read back: bRemoteExecution present = %s" % ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
