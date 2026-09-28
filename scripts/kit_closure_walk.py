"""Walk a vendor pack's dependency CLOSURE from a seed list. NO EDITOR.

WHY THIS IS A SCRIPT NOW
------------------------
The first kit intake (2026-08-29, commit 5e26fbff) computed its 106-package
closure with an ad-hoc walk that was never committed. This is the SECOND
intake, so under non-negotiable 4a the method becomes shared infrastructure
rather than being retyped -- and a retyped walk that produces a DIFFERENT
answer to the first one would be indistinguishable from the pack having
changed.

WHY A CLOSURE AND NOT A FOLDER
------------------------------
Copying a folder gets too much and still misses the shared master material two
directories away. Copying "the meshes" gets a mesh whose material reference
dangles -- which loads well enough to measure bounds and then draws as the
default checkerboard. This project has shipped a checkerboard landscape once.

HOW IT READS DEPENDENCIES WITHOUT AN EDITOR
-------------------------------------------
A `.uasset` stores the package paths it imports in its name table as
length-prefixed strings, so `/Game/...` references are readable straight out
of the bytes. The walk scans for them, resolves each to a file, and repeats to
a FIXED POINT.

**This is a SUPERSET scan, and that is deliberate.** It finds every `/Game/`
string in the file, not only the ones in the import table, so it can pick up a
path that is mentioned but not actually depended on. For an intake that errs
the safe way: a package copied and not needed costs disk, a package needed and
not copied costs a checkerboard. The count is reported so the cost is visible.

DANGLING REFERENCES ARE THE COMPLETENESS EVIDENCE. A closure that ends with
zero unresolved `/Game/` references is complete BY MEASUREMENT. `/Engine/` and
`/Script/` are not dangling -- they ship with the editor -- and are counted
separately rather than silently dropped.

Usage:
    python scripts/kit_closure_walk.py --seed-dir Meshes/Houses/MODULAR_ASSETS
    python scripts/kit_closure_walk.py --seed-list <file> --out <file>
    python scripts/kit_closure_walk.py --self-test
"""
import argparse
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = (r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache"
         r"\MedievalGame_5.3\data\Content")

# A package path: /Game/, /Engine/ or /Script/ then path chars. UE names
# allow letters, digits, underscore, hyphen and dot; the trailing dot form
# (/Game/A/B.B) is the OBJECT path and is trimmed back to the PACKAGE.
# /Engine and /Script MUST be matched here so walk() can COUNT them
# separately (they ship with the editor) rather than silently dropping them
# -- matching only /Game/ made that promise dead and the external count 0.
PKG_RE = re.compile(rb"/(?:Game|Engine|Script)/[A-Za-z0-9_/\-\.]+")


def pkg_of(raw):
    s = raw.decode("ascii", "ignore")
    # strip an object suffix: /Game/A/B.B_Inst -> /Game/A/B
    head = s.split(".")[0]
    return head.rstrip("/")


def file_for(pkg):
    rel = pkg[len("/Game/"):].replace("/", os.sep)
    for ext in (".uasset", ".umap"):
        p = os.path.join(VAULT, rel + ext)
        if os.path.isfile(p):
            return p
    return None


def refs_in(path):
    with io.open(path, "rb") as fh:
        blob = fh.read()
    out = set()
    for m in PKG_RE.finditer(blob):
        p = pkg_of(m.group(0))
        if p.count("/") >= 2:
            out.add(p)
    return out


# A Quixel/Megascans SOURCE-asset id, e.g. `tjleffvfa_2K_NormalLOD0`. These
# strings are baked into Megascans .uassets as provenance metadata and are NOT
# package references -- the real package beside them is `T_PalisadeSpike_N`.
#
# CLASSIFIED, NOT SUPPRESSED. Dropping an unresolved reference silently is how
# a genuinely missing dependency becomes a checkerboard, so these are counted
# and printed on their own line. The rule is safe because it was MEASURED
# against the pack: of every .uasset name in the 22.6 GB vault, ZERO match this
# pattern, so it cannot hide a real package.
SOURCE_ID_RE = re.compile(r"^[a-z]{6,12}_[0-9]+K_")


def is_source_id(pkg):
    return bool(SOURCE_ID_RE.match(pkg.rsplit("/", 1)[-1]))


def walk(seeds, verbose=True):
    """Seeds are package paths.

    Returns (closure, dangling, external, source_ids) -- dangling is
    GENUINELY unresolved, source_ids are the classified metadata strings.
    """
    seen, dangling, external, source_ids = set(), set(), set(), set()
    queue = list(seeds)
    rounds = 0
    while queue:
        rounds += 1
        pkg = queue.pop()
        if pkg in seen or pkg in dangling:
            continue
        f = file_for(pkg)
        if f is None:
            (source_ids if is_source_id(pkg) else dangling).add(pkg)
            continue
        seen.add(pkg)
        for r in refs_in(f):
            if r.startswith("/Engine/") or r.startswith("/Script/"):
                external.add(r)
            elif r not in seen:
                queue.append(r)
    if verbose:
        print("  walked to a fixed point in %d pops" % rounds)
    return seen, dangling, external, source_ids


def seeds_from_dir(rel_dir):
    d = os.path.join(VAULT, rel_dir.replace("/", os.sep))
    if not os.path.isdir(d):
        print("REFUSE: no such directory under the vault: " + rel_dir)
        return None
    out = []
    for root, _dirs, files in os.walk(d):
        for f in files:
            if f.endswith(".uasset") and f.startswith("SM_"):
                rel = os.path.relpath(os.path.join(root, f), VAULT)
                out.append("/Game/" + rel[:-len(".uasset")].replace(os.sep, "/"))
    return sorted(out)


def self_test():
    """Reproduce the FIRST intake's closure from its own 15 seeds.

    This is a regression control against a known-good answer, not a synthetic:
    the 106 packages were computed by a different (ad-hoc) implementation, so
    agreement is two implementations meeting, and disagreement is a real
    question rather than a style difference.
    """
    print("SELF-TEST -- reproduce the recorded 2026-08-29 kit closure")
    man = os.path.join(REPO, "Free", "_measured",
                       "kit_medievalvillage_closure.json")
    if not os.path.isfile(man):
        print("  MANIFEST ABSENT -- cannot look. That is not a pass.")
        return 5
    with io.open(man, encoding="utf-8") as fh:
        prior = json.load(fh)
    known = set()
    for row in prior["files"]:
        p = row.get("package") or row.get("pkg")
        if p:
            known.add(p)
    if not known:
        print("  manifest carries no package paths -- cannot compare.")
        return 5

    seeds = sorted(p for p in known if "/3D_Assets/" in p and "/SM_" in p)
    print("  seeds: %d static meshes from the recorded closure" % len(seeds))
    got, dang, ext, src = walk(seeds)
    missing = known - got
    extra = got - known
    print("  recorded %d   reproduced %d   missing %d   extra %d"
          % (len(known), len(got), len(missing), len(extra)))
    print("  dangling %d   engine/script %d   source-ids %d"
          % (len(dang), len(ext), len(src)))
    for p in sorted(missing)[:6]:
        print("    MISSING  " + p)
    for p in sorted(extra)[:6]:
        print("    EXTRA    " + p)
    # A reproduction that leaves GENUINELY-unresolved /Game/ refs is not the
    # complete closure the manifest records, so dangling counts against the
    # verdict too -- not just `missing`.
    ok = not missing and not dang
    print("")
    print("walker %s"
          % ("REPRODUCES the recorded closure"
             if ok else "!! DOES NOT REPRODUCE -- do not trust its output"))
    if extra and ok:
        print("  (the %d extra are the superset scan erring safe; see the"
              " module docstring)" % len(extra))
    return 0 if ok else 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dir", action="append", default=[])
    ap.add_argument("--seed-list")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    seeds = []
    for d in a.seed_dir:
        s = seeds_from_dir(d)
        if s is None:
            return 2
        print("  %-42s %d seed mesh(es)" % (d, len(s)))
        seeds.extend(s)
    if a.seed_list:
        with io.open(os.path.join(REPO, a.seed_list), encoding="utf-8") as fh:
            seeds.extend([ln.strip() for ln in fh if ln.strip()])
    if not seeds:
        print("REFUSE: no seeds. An empty closure is not an empty pack.")
        return 2

    seeds = sorted(set(seeds))
    print("")
    print("walking the closure of %d seed package(s)" % len(seeds))
    got, dang, ext, src = walk(seeds)

    total = 0
    for p in got:
        f = file_for(p)
        if f:
            total += os.path.getsize(f)
    print("")
    print("  closure          %d packages, %.1f MB" % (len(got), total / 1e6))
    print("  dangling /Game/  %d   <- must be 0 for the set to be complete"
          % len(dang))
    print("  /Engine, /Script %d   (ship with the editor, not copied)"
          % len(ext))
    print("  Quixel source-ids %d  (provenance metadata, NOT references --"
          " classified, see the module docstring)" % len(src))
    for p in sorted(dang)[:10]:
        print("    DANGLING  " + p)

    if a.out:
        outp = os.path.join(REPO, a.out)
        with io.open(outp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(sorted(got)) + "\n")
        print("  wrote %s" % a.out)
    # NN13: a completeness verdict over an EMPTY closure is not a pass. If no
    # seed resolved to a package on disk, `dang` may also be empty and the old
    # `0 if not dang` would announce a complete set of zero packages.
    if not got:
        print("REFUSE: empty closure -- no seed resolved to a package on "
              "disk. An empty closure is not a complete one.")
        return 4
    return 0 if not dang else 4


if __name__ == "__main__":
    sys.exit(main())
