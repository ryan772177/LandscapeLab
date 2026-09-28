"""What does a new closure add that the project does not already hold?

`intake_kit_closure.py` REFUSES any destination that already exists -- correct,
because overwriting a project asset with vendor content is a loss that looks
like a successful import. So a second intake must be handed the DELTA, not the
whole closure, or it stops on the first shared texture.

The overlap is not waste: the first intake's 106 packages include the shared
master material, its functions and the blend textures, and every later closure
lands on them. That is the closure working.
"""
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = (r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache"
         r"\MedievalGame_5.3\data\Content")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def size_of(pkg):
    rel = pkg[len("/Game/"):].replace("/", os.sep)
    for ext in (".uasset", ".umap"):
        f = os.path.join(VAULT, rel + ext)
        if os.path.isfile(f):
            return os.path.getsize(f)
    return 0


def kind_of(pkg):
    leaf = pkg.rsplit("/", 1)[-1]
    for pre, name in (("SM_", "static mesh"), ("MI_", "material instance"),
                      ("T_", "texture"), ("MF_", "material function"),
                      ("MPC_", "parameter collection"), ("M_", "material")):
        if leaf.startswith(pre):
            return name
    return "other"


def main():
    if len(sys.argv) < 3:
        print("usage: kit_closure_delta <closure.txt> <out_delta.txt>")
        return 2
    closure_p, out_p = sys.argv[1], sys.argv[2]

    man = os.path.join(REPO, "Free", "_measured",
                       "kit_medievalvillage_closure.json")
    with io.open(man, encoding="utf-8") as fh:
        have = {r["package"] for r in json.load(fh)["files"]}

    with io.open(os.path.join(REPO, closure_p), encoding="utf-8") as fh:
        new = [ln.strip() for ln in fh if ln.strip()]

    delta = sorted(set(new) - have)
    overlap = sorted(set(new) & have)
    total = sum(size_of(p) for p in delta)

    print("  closure          %d packages" % len(new))
    print("  already adopted  %d   (shared master, functions, blend textures)"
          % len(overlap))
    print("  TO COPY          %d packages, %.1f MB" % (len(delta), total / 1e6))
    kinds = {}
    for p in delta:
        k = kind_of(p)
        kinds[k] = kinds.get(k, 0) + 1
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print("      %-22s %d" % (k, v))

    missing = [p for p in delta if size_of(p) == 0]
    if missing:
        print("")
        print("  REFUSE: %d package(s) in the delta have no file on disk"
              % len(missing))
        for p in missing[:5]:
            print("    " + p)
        return 4

    with io.open(os.path.join(REPO, out_p), "w", encoding="utf-8") as fh:
        fh.write("\n".join(delta) + "\n")
    print("  wrote %s" % out_p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
