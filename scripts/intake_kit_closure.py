"""Copy the Medieval Village kit's dependency CLOSURE into the project.

WHY A CLOSURE AND NOT A FOLDER
------------------------------
The pack is 22.6 GB. The 15 modules this project measured need 106 packages:
their meshes, their material instances, a shared master material, its functions
and base textures, and the shared blend textures. Walking the references to a
FIXED POINT is what makes "everything needed, nothing else" a measurement
rather than a guess -- and it reported 0 dangling references, which is the
evidence that the set is complete.

STRUCTURE IS PRESERVED ON PURPOSE. A .uasset references its dependencies by
PACKAGE PATH, so a mesh copied to a flat folder still points at
/Game/Megascans/3D_Assets/... . The existing _probe/ copy has exactly that
defect: it loaded well enough to measure bounds, and its material reference
dangles. Copying into the pack's own layout is what makes the references
resolve.

REFUSES RATHER THAN OVERWRITES. The project already owns Content/Materials and
Content/Meshes. Any destination that already exists is a COLLISION and stops
the run before a byte is written -- overwriting a project asset with vendor
content is the kind of loss that looks like a successful import.

Provenance: every file is SHA-256'd at both ends and the manifest records the
pair, so the copy is hash-proven against its source at adoption time (NN20).

Usage:
    python scripts/intake_kit_closure.py --closure <file> [--go]
Bare run is a DRY RUN.
"""
import argparse
import hashlib
import io
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = (r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache"
         r"\MedievalGame_5.3\data\Content")
DEST_ROOT = os.path.join(REPO, "LandscapeLab", "Content")


def sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_of(pkg):
    return pkg[len("/Game/"):].replace("/", os.sep) + ".uasset"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--closure", required=True)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--manifest",
                    default=os.path.join(REPO, "Free", "_measured",
                                         "kit_medievalvillage_closure.json"))
    a = ap.parse_args()

    pkgs = [l.strip() for l in io.open(a.closure, encoding="utf-8")
            if l.strip()]
    rows, collisions, absent, total = [], [], [], 0
    for pkg in pkgs:
        rel = rel_of(pkg)
        src = os.path.join(VAULT, rel)
        dst = os.path.join(DEST_ROOT, rel)
        if not os.path.exists(src):
            absent.append(pkg)
            continue
        if os.path.exists(dst):
            collisions.append(pkg)
        n = os.path.getsize(src)
        total += n
        rows.append((pkg, src, dst, n))

    print("KIT CLOSURE INTAKE  (%s)" % ("GO" if a.go else "DRY RUN"))
    print("  packages in closure : %d" % len(pkgs))
    print("  resolved on disk    : %d" % len(rows))
    print("  bytes to copy       : %d  (%.1f MB)" % (total, total / 1e6))
    print("  MISSING at source   : %d" % len(absent))
    print("  COLLISIONS at dest  : %d" % len(collisions))
    for p in absent[:10]:
        print("      MISSING %s" % p)
    for p in collisions[:20]:
        print("      COLLIDES %s" % p)

    if absent:
        print()
        print("REFUSING: a package in the closure is not at the source. The "
              "closure was computed FROM that source, so this means it moved "
              "under us.")
        return 2
    if collisions:
        print()
        print("REFUSING: %d destination(s) already exist. This project owns "
              "Content/Materials and Content/Meshes; overwriting one with "
              "vendor content is a loss that looks like an import." % len(collisions))
        return 3

    if not a.go:
        print()
        print("DRY RUN -- nothing written. Re-run with --go.")
        return 0

    copied, manifest = 0, []
    for pkg, src, dst, n in rows:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        hs, hd = sha256(src), sha256(dst)
        if hs != hd:
            print("  !! HASH MISMATCH after copy: %s" % pkg)
            return 4
        manifest.append({"package": pkg, "bytes": n, "sha256": hs})
        copied += 1

    import json
    os.makedirs(os.path.dirname(a.manifest), exist_ok=True)
    io.open(a.manifest, "w", encoding="utf-8").write(json.dumps({
        "_what": ("SHA-256 manifest of the Medieval Village kit closure copied "
                  "into the project. Source is gitignored and re-downloadable; "
                  "this manifest is the committed DERIVATIVE and is what makes "
                  "the copy hash-proven against its source at adoption time."),
        "_source": VAULT,
        "_dest": "LandscapeLab/Content (package paths preserved)",
        "_adopted": "2026-08-29",
        "packages": len(manifest),
        "bytes": total,
        "files": manifest,
    }, indent=2) + "\n")

    print()
    print("  copied %d files, %.1f MB, every one hash-verified at both ends"
          % (copied, total / 1e6))
    print("  manifest: %s" % os.path.relpath(a.manifest, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
