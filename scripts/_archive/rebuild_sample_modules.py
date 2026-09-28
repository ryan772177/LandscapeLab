"""rebuild_sample_modules.py — rebuild a sample project's C++ modules against
UE 5.8, so its editor will open.

WHY VALLEY NEEDS THIS AND THE OTHERS DID NOT
--------------------------------------------
Valley of the Ancient ships C++ modules compiled for 5.7. Under a 5.8 engine
the editor logs, for each one:

    LogInit: Warning: Still incompatible or missing module: AncientGame
    ... InstanceLevelCollision, Crossfader, Uproar, Underscore, HoverDrone
    LogCore: Engine exit requested (reason: EngineExit() was called)

Interactively the editor offers to rebuild; non-interactively it exits.

**A C++ MODULE IS NOT WHAT BLOCKS — A VERSION MISMATCH IS.** Electric Dreams
also has a module (`ElectricDreamsSample`) and opens fine, because it declares
EngineAssociation 5.8 and ships a 5.8 DLL. Reading "has C++" as "cannot open"
would have written that project off wrongly.

WHAT THIS DOES NOT DO
---------------------
It does not touch the `.uproject`. Standing rule 4 forbids modifying
`.uproject`/`.uasset`/`.umap` on disk, and UBT takes `-Project` and builds
with the engine it is invoked from, so the declared EngineAssociation does not
need changing. If UBT refuses on that basis, STOP and escalate rather than
edit the file.

It builds the EDITOR target only. The game target is not needed to census a
project, and each target is a separate multi-module compile.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UE_ROOT = r"C:\Program Files\Epic Games\UE_5.8"
BUILD_BAT = os.path.join(UE_ROOT, "Engine", "Build", "BatchFiles", "Build.bat")
LOGS = os.path.join(REPO, "LandscapeLab", "Saved", "Logs")

TARGETS = {
    "ValleyOfTheAncient": {
        "uproject": r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\AncientGame_5.7\data\AncientGame.uproject",
        "target": "AncientGameEditor",
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, choices=sorted(TARGETS))
    ap.add_argument("--config", default="Development")
    ap.add_argument("--timeout", type=float, default=5400.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = TARGETS[a.project]
    if not os.path.exists(cfg["uproject"]):
        raise SystemExit("REFUSE: no uproject at %s" % cfg["uproject"])
    if not os.path.exists(BUILD_BAT):
        raise SystemExit("REFUSE: no Build.bat at %s" % BUILD_BAT)

    os.makedirs(LOGS, exist_ok=True)
    log = os.path.join(LOGS, "rebuild_%s.log" % a.project.lower())
    cmd = [BUILD_BAT, cfg["target"], "Win64", a.config,
           "-Project=%s" % cfg["uproject"], "-WaitMutex", "-FromMsBuild"]
    print("rebuild %s\n  target %s %s Win64\n  log    %s"
          % (a.project, cfg["target"], a.config, log))
    print("  cmd    %s" % " ".join(cmd))
    if a.dry_run:
        return 0

    t0 = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             errors="replace", cwd=UE_ROOT)
        tail = []
        for line in p.stdout:
            fh.write(line)
            tail.append(line.rstrip())
            if len(tail) > 40:
                tail.pop(0)
            low = line.lower()
            if ("error" in low or "warning: still incompatible" in low
                    or line.startswith("[") and "/" in line[:12]):
                print("  " + line.rstrip()[:160])
            if time.time() - t0 > a.timeout:
                p.kill()
                print("  TIMEOUT after %.0f s" % (time.time() - t0))
                break
        rc = p.wait()

    print("exit %d after %.0f s" % (rc, time.time() - t0))
    print("--- last lines ---")
    for t in tail[-15:]:
        print("  " + t[:170])
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
