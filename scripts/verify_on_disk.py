"""Does this /Game/ package exist as a FILE? The only honest test of "saved".

WHY THIS EXISTS
---------------
On 2026-08-30 the C0 unit reported complete, with every check green:

    21 textures imported, every setting READ BACK
    7 material instances, every parameter READ BACK
    master compiles clean, 0 orphans, 3/3 samplers agree with the engine
    both houses staged, base_z 0.00, materials differ on the live component
    the level SAVED

Then the editor restarted and the side-by-side frame came back an **empty
plane**. The mesh and all 21 textures had never been written to disk. The
seven material instances HAD been saved, so what survived was a set of
materials whose texture references dangled and a level referencing a mesh that
did not exist.

**EVERY EDITOR-SIDE INSTRUMENT PASSES ON AN IN-MEMORY-ONLY ASSET.**
`EditorAssetLibrary.does_asset_exist` returns True for it. `load_asset`
returns it. `get_editor_property` reads its settings. An audit walks its
graph. None of them distinguish *loaded* from *saved*, because from inside the
editor there is no difference — which is exactly non-negotiable 8: verify with
a different instrument than the one that made the claim.

The filesystem is that different instrument, and it is on the HOST side where
no editor state can flatter it.

Usage:
    python scripts/verify_on_disk.py /Game/Scratch/C0House/SM_C0_DonorHouse ...
    python scripts/verify_on_disk.py --dir /Game/Scratch/C0House --min 22
"""
import argparse
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(REPO, "LandscapeLab", "Content")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def file_for(pkg):
    if not pkg.startswith("/Game/"):
        return None
    rel = pkg[len("/Game/"):].replace("/", os.sep)
    for ext in (".uasset", ".umap"):
        p = os.path.join(CONTENT, rel + ext)
        if os.path.isfile(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="*")
    ap.add_argument("--dir", help="/Game/... directory to enumerate")
    ap.add_argument("--min", type=int, default=0,
                    help="refuse if fewer than N files are present")
    a = ap.parse_args()

    rc = 0
    if a.packages:
        print("  %-58s %s" % ("package", "on disk"))
        missing = []
        for p in a.packages:
            f = file_for(p)
            print("  %-58s %s" % (p[:58], "yes" if f else "!! ABSENT"))
            if not f:
                missing.append(p)
        print("")
        if missing:
            print("REFUSE: %d of %d package(s) exist only in the editor."
                  % (len(missing), len(a.packages)))
            print("  An unsaved asset passes does_asset_exist, load_asset,")
            print("  every property read-back and every graph audit. It")
            print("  disappears on restart and takes any level that")
            print("  references it with it.")
            rc = 4
        else:
            print("  all %d package(s) are FILES on disk" % len(a.packages))

    if a.dir:
        d = os.path.join(CONTENT, a.dir[len("/Game/"):].replace("/", os.sep))
        n = 0
        if os.path.isdir(d):
            for root, _dirs, files in os.walk(d):
                n += sum(1 for f in files
                         if f.endswith((".uasset", ".umap")))
        print("")
        print("  %s : %d file(s) on disk" % (a.dir, n))
        if n < a.min:
            print("REFUSE: expected at least %d, found %d." % (a.min, n))
            rc = 4
    return rc


if __name__ == "__main__":
    sys.exit(main())
