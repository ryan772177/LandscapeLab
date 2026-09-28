"""patch_sample_target.py — edit a sample project's *.Target.cs so its modules
can be rebuilt against 5.8.

OPERATOR-RULED. Standing rule 1 says never write outside this repo; Ryan
authorised this edit specifically. Rule 4 protects .uproject/.uasset/.umap --
a .Target.cs is a C# BUILD SCRIPT and is not in that set, so the constraint
here is the operator ruling, not the file type.

WHY TWO MODES
-------------
UBT refused AncientGameEditor with:

    AncientGameEditor modifies the values of properties:
      [ UnreachableCodeWarningLevel: Off != Error,
        ReturnTypeWarningLevel:      Off != Error,
        DanglingWarningLevel:        Off != Error ]

The target declares `DefaultBuildSettings = BuildSettingsVersion.V6`, which
defaults those three Off; UE 5.8 defaults them Error. Under an INSTALLED
engine every target shares one build environment, so a target that changes a
global compiler setting is refused.

  --mode unique   adds `BuildEnvironment = TargetBuildEnvironment.Unique;`
                  UBT's headline suggestion. EXPECTED TO FAIL on an installed
                  engine, which cannot rebuild engine binaries with different
                  settings -- tried anyway because a 1-second refusal is
                  cheaper than my theory about it.
  --mode v7       raises DefaultBuildSettings to V7 so the target adopts 5.8's
                  defaults and stops modifying them, keeping the SHARED
                  environment. UBT's own [Upgrade] block names this route.

Backs the original into THIS repo before touching anything, so the edit is
reversible from here even if the sample copy is deleted -- which has already
happened once this session.
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUPS = os.path.join(REPO, "research", "census", "config_backups")

TARGETS = {
    "ValleyOfTheAncient": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\AncientGame_5.7\data\Source\AncientGameEditor.Target.cs",
}

UNIQUE_LINE = "\t\tBuildEnvironment = TargetBuildEnvironment.Unique;\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, choices=sorted(TARGETS))
    ap.add_argument("--mode", choices=("unique", "v7"), default=None,
                    help="required unless --revert")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--target-file", default=None,
                    help="override the hardcoded VaultCache Target.cs path "
                         "(the default is machine-specific)")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute the edit and print it, write nothing")
    a = ap.parse_args()
    # --mode is only consulted when applying; do not force an ignored value on
    # --revert.
    if not a.revert and a.mode is None:
        ap.error("--mode is required unless --revert")

    path = a.target_file or TARGETS[a.project]
    if not os.path.exists(path):
        raise SystemExit("REFUSE: no Target.cs at %s" % path)
    os.makedirs(BACKUPS, exist_ok=True)
    backup = os.path.join(BACKUPS,
                          "%s__%s.orig" % (a.project, os.path.basename(path)))

    if a.revert:
        if not os.path.exists(backup):
            raise SystemExit("REFUSE: no backup at %s" % backup)
        shutil.copy2(backup, path)
        # Verify the restore rather than trust copy2 (the apply path reads back;
        # revert should too).
        if (io.open(path, encoding="utf-8").read()
                != io.open(backup, encoding="utf-8").read()):
            raise SystemExit("REFUSE: revert read-back mismatch at %s" % path)
        print("reverted %s (verified against backup)" % path)
        return 0

    # ONCE, and never overwritten: a backup taken after an edit preserves the
    # edit, not the original.
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print("backed up -> %s" % os.path.relpath(backup, REPO))

    # Always start from the ORIGINAL, so modes do not stack on each other.
    src = io.open(backup, encoding="utf-8").read()

    # NOTE: the state checks below read the BACKUP (the preserved original), so
    # modes never stack; the live file is verified by the read-back after write.
    if a.mode == "unique":
        if "TargetBuildEnvironment.Unique" in src:
            print("backup already contains TargetBuildEnvironment.Unique")
        else:
            anchor = "ExtraModuleNames.AddRange"
            i = src.find(anchor)
            if i < 0:
                raise SystemExit("REFUSE: anchor %r not found" % anchor)
            line_start = src.rfind("\n", 0, i) + 1
            src = src[:line_start] + UNIQUE_LINE + src[line_start:]
    else:
        n = src.count("BuildSettingsVersion.V6")
        if n != 1:
            raise SystemExit("REFUSE: expected exactly ONE BuildSettingsVersion."
                             "V6 in the backup, found %d -- not guessing which "
                             "to edit" % n)
        src = src.replace("BuildSettingsVersion.V6", "BuildSettingsVersion.V7")

    if a.dry_run:
        print("DRY RUN: would write %s (mode %s); nothing written." % (path,
                                                                       a.mode))
        for ln in src.splitlines():
            if any(k in ln for k in ("BuildSettings", "BuildEnvironment",
                                     "IncludeOrder", "ExtraModule")):
                print("  " + ln.strip())
        return 0

    io.open(path, "w", encoding="utf-8", newline="").write(src)
    after = io.open(path, encoding="utf-8").read()
    ok = ("TargetBuildEnvironment.Unique" in after if a.mode == "unique"
          else "BuildSettingsVersion.V7" in after)
    print("mode %s applied to %s" % (a.mode, path))
    print("read back: %s" % ok)
    print("--- file now ---")
    for ln in after.splitlines():
        if any(k in ln for k in ("BuildSettings", "BuildEnvironment",
                                 "IncludeOrder", "ExtraModule")):
            print("  " + ln.strip())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
