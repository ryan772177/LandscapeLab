"""Prove the kit closure RESOLVES: no copied package references a missing one.

This is the offline acceptance test for the intake. It is NOT a render, and it
is not a claim that the materials compile -- see the limits printed at the end.
What it does settle is the failure this intake exists to avoid: a mesh whose
material reference dangles, which loads well enough to measure and draws as the
default checkerboard.

Every /Game/ reference in every copied package must resolve to a file in
Content. /Engine/ references are the engine's and are reported, not required.

Exit 0 = fully resolved. Exit 5 = at least one dangling reference.
Exit 6 = nothing was scanned (empty or missing intake roots) -- "no dangling
references" over zero checks is not closure.
"""
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit_closure_walk import is_source_id            # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(REPO, "LandscapeLab", "Content")
PKG = re.compile(rb"/Game/[A-Za-z0-9_/\.\-]{2,200}")

ROOTS = [
    os.path.join(CONTENT, "Megascans"),
    os.path.join(CONTENT, "Materials", "Functions"),
    os.path.join(CONTENT, "Materials", "Masters"),
    os.path.join(CONTENT, "Meshes", "Houses"),
]


def norm(pkg):
    tail = pkg.rsplit("/", 1)[-1]
    return pkg.rsplit(".", 1)[0] if "." in tail else pkg


def disk_of(pkg, ext):
    return os.path.join(CONTENT,
                        pkg[len("/Game/"):].replace("/", os.sep) + ext)


def resolves(pkg):
    # F7: a /Game/ reference may point at a .umap as well as a .uasset; checking
    # only .uasset would report a valid map reference as a dangling one.
    return any(os.path.exists(disk_of(pkg, e)) for e in (".uasset", ".umap"))


def main():
    files = []
    missing_roots = [r for r in ROOTS if not os.path.isdir(r)]
    for r in ROOTS:
        if not os.path.isdir(r):
            continue
        for dp, _, fns in os.walk(r):
            for fn in fns:
                if fn.endswith(".uasset"):
                    files.append(os.path.join(dp, fn))

    dangling, checked, resolved, engine_refs = {}, 0, 0, set()
    source_ids = {}
    for f in sorted(files):
        with io.open(f, "rb") as fh:
            raw = fh.read()
        rel = os.path.relpath(f, CONTENT).replace(os.sep, "/")
        for m in PKG.finditer(raw):
            try:
                pkg = norm(m.group(0).decode("ascii"))
            except UnicodeDecodeError:
                continue
            checked += 1
            if resolves(pkg):
                resolved += 1
            else:
                # ONE DECLARATION OF WHAT A QUIXEL SOURCE-ID IS, imported from
                # the walker rather than re-implemented here. The walker
                # classified these and this verifier did not, so the two tools
                # disagreed about whether the same intake was complete --
                # non-negotiable 24, and the kind that resolves by one side
                # quietly "fixing" its own copy of the rule.
                (source_ids if is_source_id(pkg)
                 else dangling).setdefault(pkg, set()).add(rel)
        for m in re.finditer(rb"/Engine/[A-Za-z0-9_/\.\-]{2,120}", raw):
            try:
                engine_refs.add(norm(m.group(0).decode("ascii")))
            except UnicodeDecodeError:
                pass

    print("KIT CLOSURE RESOLUTION")
    print("  packages scanned      : %d" % len(files))
    if missing_roots:
        print("  MISSING intake roots  : %s" % ", ".join(
            os.path.relpath(r, CONTENT) for r in missing_roots))
    # F1/NN13: "no dangling references" computed over ZERO scanned packages or
    # ZERO checked references is silence wearing agreement's clothes -- refuse.
    if not files or checked == 0:
        print()
        print("  REFUSE: %d packages scanned, %d /Game/ refs checked -- nothing "
              "to verify (empty or missing intake roots). This is not closure."
              % (len(files), checked))
        return 6
    # F2/F3: resolved is counted directly on the exists-true branch (occurrences),
    # not `checked - sum(distinct dangling pairs)` which mixed occurrence counts
    # with distinct-pair counts and folded unresolved source-ids into "resolved".
    print("  /Game/ refs resolved  : %d of %d occurrences" % (resolved, checked))
    print("  DANGLING /Game/ refs  : %d distinct" % len(dangling))
    print("  Quixel source-ids     : %d distinct  (provenance metadata baked "
          "into Megascans" % len(source_ids))
    print("                          assets, NOT references. Classified by "
          "kit_closure_walk.is_source_id,")
    print("                          which was MEASURED against the pack: "
          "ZERO real packages match.)")
    for pkg in sorted(source_ids)[:5]:
        print("      source-id  %s" % pkg)
    print("  /Engine/ refs seen    : %d distinct (engine-owned, not required "
          "to be in Content)" % len(engine_refs))
    if dangling:
        print()
        for pkg in sorted(dangling)[:30]:
            src = sorted(dangling[pkg])[:2]
            print("  MISSING %-62s referenced by %s" % (pkg, ", ".join(src)))
        if len(dangling) > 30:
            print("  ... and %d more" % (len(dangling) - 30))
        print()
        print("A DANGLING MATERIAL REFERENCE DRAWS AS THE DEFAULT CHECKERBOARD "
              "and this project has shipped that once already.")
        return 5

    print()
    print("  ok  every /Game/ reference resolves inside Content")
    print()
    print("WHAT THIS DOES *NOT* PROVE, stated so it is not read as more:")
    print("  * that the materials COMPILE -- that needs an editor")
    print("  * that the meshes RENDER correctly -- R-ASSET step 6 is a spawn")
    print("    and a render, and step 7 says verified-in-engine flips only then")
    print("  * that the 5.3 -> 5.8 version step is clean beyond loading")
    print("  * that every EXPECTED module is PRESENT -- this checks that the")
    print("    references in what IS here resolve, not that nothing is missing")
    print("    from the kit (no measured-manifest cross-check yet)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
