"""Resolve the Gate-A approved wider kit seed AGAINST DISK, never from memory.

The approval names: "MODULAR_ASSETS + Roofs -- HBeam_*, BoardWall, GableSet,
PorchBase, LanternPost, bench, wheels". Those are NAMES, and a name typed from
memory into a seed list is a derived record (NN15). This resolves each pattern
against the vault and REFUSES if any pattern matches nothing, so a silent typo
cannot quietly shrink the intake.

The whole MODULAR_ASSETS + Roofs + Construction_Pieces directories close to 397
packages / 3.9 GB, measured. The approved named subset is smaller and is what
was actually authorised; the difference is reported so the choice is visible.
"""
import fnmatch
import io
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = (r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache"
         r"\MedievalGame_5.3\data\Content")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# pattern -> what the approval called it
HOUSE_PATTERNS = {
    "SM_HBeam_*": "HBeam_*",
    "SM_BoardWall*": "BoardWall",
    "SM_GableSet_*": "GableSet",
    "SM_PorchBase*": "PorchBase",
    "SM_LanternPost*": "LanternPost",
}
MEGA_EXACT = {
    "SM_OldWoodenBench": "bench",
    "SM_WoodenWheelA": "wheels",
    "SM_WoodenWheelB": "wheels",
    "SM_WoodenWheelbarrow": "wheels",
}


def pkg(path):
    return "/Game/" + os.path.relpath(path, VAULT).replace(os.sep, "/")


def main():
    seeds, hits = {}, {k: 0 for k in
                       list(HOUSE_PATTERNS) + ["Roofs/*"] + list(MEGA_EXACT)}

    houses = os.path.join(VAULT, "Meshes", "Houses")
    for root, _d, files in os.walk(houses):
        in_roofs = (os.sep + "Roofs" + os.sep) in (root + os.sep)
        for f in files:
            if not f.endswith(".uasset"):
                continue
            stem = f[:-len(".uasset")]
            if not stem.startswith("SM_"):
                continue
            label = None
            if in_roofs:
                label, hits["Roofs/*"] = "Roofs", hits["Roofs/*"] + 1
            else:
                for pat, name in HOUSE_PATTERNS.items():
                    if fnmatch.fnmatch(stem, pat):
                        label, hits[pat] = name, hits[pat] + 1
                        break
            if label:
                seeds[pkg(os.path.join(root, stem))] = label

    mega = os.path.join(VAULT, "Megascans", "3D_Assets")
    for root, _d, files in os.walk(mega):
        for f in files:
            if not f.endswith(".uasset"):
                continue
            stem = f[:-len(".uasset")]
            if stem in MEGA_EXACT:
                seeds[pkg(os.path.join(root, stem))] = MEGA_EXACT[stem]
                hits[stem] += 1

    empty = [k for k, v in hits.items() if v == 0]
    print("  %-22s %s" % ("pattern", "meshes found"))
    for k in sorted(hits):
        print("  %-22s %d%s" % (k, hits[k], "   <- MATCHED NOTHING"
                                if hits[k] == 0 else ""))
    if empty:
        print("")
        print("REFUSE: %d approved name(s) matched no file. A seed that "
              "silently" % len(empty))
        print("  shrinks is an intake that looks complete and is not.")
        return 2

    out = os.path.join(REPO, "recipes", "kit_seed_v2.txt")
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(seeds)) + "\n")
    print("")
    print("  %d seed meshes -> recipes/kit_seed_v2.txt" % len(seeds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
