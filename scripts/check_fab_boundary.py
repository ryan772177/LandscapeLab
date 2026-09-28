"""check_fab_boundary.py — enforce the source/derivative line in Fab folders.

THE PROBLEM THIS EXISTS FOR.

Fab-delivered content (15.9 GB) is gitignored: it is vendor SOURCE and is
re-downloadable, and ASSETS.md carries the source, licence and path. That
is correct. But it opens two holes that git itself cannot close, because
**git cannot re-include a file whose parent directory is excluded** --
so no `!negation` pattern can rescue anything placed inside one:

  HOLE 1  A derivative WE author inside a Fab folder (a material
          instance, a scatter registration) is silently ignored. Our own
          work would vanish on a fresh clone with no error anywhere.

  HOLE 2  An IN-PLACE MODIFICATION of a Fab source asset -- enabling
          Nanite on their static mesh, changing an LOD or collision
          setting -- is equally ignored. The asset re-downloads in its
          original state and the modification is gone.

THE RULES, which this script enforces rather than merely states:

  1. NEVER AUTHOR INTO A FAB FOLDER. Every derivative goes to a project
     convention path (/Game/Meshes/Materials/, /Game/Foliage/, ...),
     all of which are tracked -- verified by `git check-ignore`.

  2. AN IN-PLACE MODIFICATION IS NOT A COMMITTABLE DERIVATIVE. It must be
     expressed as a REPLAYABLE STEP in the recipe, so it re-applies after
     a re-download. This is strictly better than committing the bytes: it
     is idempotent and survives a vendor update, which a committed blob
     would not.

Run it after any bulk operation touching Fab content. It records a
baseline manifest on first run and reports drift afterwards.

Usage:
    python scripts/check_fab_boundary.py --baseline   # record
    python scripts/check_fab_boundary.py              # check drift
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(REPO, "LandscapeLab", "Content")
MANIFEST = os.path.join(REPO, "Free", "_measured", "fab_boundary.json")

# The Fab-delivered, gitignored source folders.
FAB_FOLDERS = ["KiteDemo", "DragonCave", "Atlantis_Ruins", "StampIt",
               "Mannequin", "ThirdPerson", "ThirdPersonBP", "Geometry"]


def scan():
    out = {}
    for folder in FAB_FOLDERS:
        root = os.path.join(CONTENT, folder)
        if not os.path.isdir(root):
            continue
        for dirpath, _d, names in os.walk(root):
            for n in names:
                p = os.path.join(dirpath, n)
                rel = os.path.relpath(p, CONTENT).replace("\\", "/")
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out[rel] = {"size": st.st_size, "mtime": int(st.st_mtime)}
    return out


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", action="store_true",
                    help="record the current state as the baseline")
    args = ap.parse_args(argv)

    now = scan()
    if not now:
        print("No Fab folders present under {0}".format(CONTENT))
        return 0

    if args.baseline or not os.path.isfile(MANIFEST):
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "w", encoding="utf-8") as fh:
            json.dump({"note": "Baseline of gitignored Fab SOURCE content. "
                               "Drift means something authored or modified "
                               "inside an ignored folder, which git cannot "
                               "protect.",
                       "files": now}, fh, indent=1, sort_keys=True)
        total = sum(v["size"] for v in now.values())
        print("baseline recorded: {0:,} files, {1:,.0f} MB".format(
            len(now), total / (1024.0 * 1024.0)))
        print("  {0}".format(os.path.relpath(MANIFEST, REPO)))
        return 0

    with open(MANIFEST, encoding="utf-8") as fh:
        base = json.load(fh)["files"]

    added = sorted(set(now) - set(base))
    removed = sorted(set(base) - set(now))
    changed = sorted(k for k in set(now) & set(base)
                     if now[k]["size"] != base[k]["size"]
                     or now[k]["mtime"] != base[k]["mtime"])

    print("Fab source folders: {0:,} files".format(len(now)))
    print("  added   {0}".format(len(added)))
    print("  removed {0}".format(len(removed)))
    print("  changed {0}".format(len(changed)))

    bad = False
    if added:
        bad = True
        print("")
        print("*** FILES ADDED INSIDE AN IGNORED FOLDER ***")
        print("If we authored these, THEY WILL NOT SURVIVE A FRESH CLONE.")
        print("Move them to a project convention path, which is tracked.")
        for p in added[:20]:
            print("    {0}".format(p))
        if len(added) > 20:
            print("    ... (+{0} more)".format(len(added) - 20))
    if changed:
        bad = True
        print("")
        print("*** FAB SOURCE FILES MODIFIED IN PLACE ***")
        print("These changes are gitignored and WILL BE LOST on re-download.")
        print("Express the change as a replayable recipe step instead.")
        for p in changed[:20]:
            print("    {0}".format(p))
        if len(changed) > 20:
            print("    ... (+{0} more)".format(len(changed) - 20))
    if removed:
        print("")
        print("note: {0} file(s) removed (re-download restores them)"
              .format(len(removed)))

    if not bad:
        print("")
        print("BOUNDARY HOLDS: nothing authored or modified inside an "
              "ignored Fab folder.")
        return 0
    print("")
    print("Re-run with --baseline once the drift is understood and "
          "deliberately accepted.")
    return 5


if __name__ == "__main__":
    raise SystemExit(main())
