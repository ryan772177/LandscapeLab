"""build_corpus.py — assemble the audit zip and the git-history text.

READ-ONLY against the repo. Writes only under research/audit/.

⭐ WHAT GOES IN, AND WHY THE LIST IS EXPLICIT. The desk has to verify
claims against UE 5.8 documentation and against the pipeline's own
behaviour, so it needs the SOURCE (every script, every recipe), the
RECORD (every register, brief, plan, commit message) and the EVIDENCE
(every sidecar). No date limits anywhere: a claim made in August is
exactly the kind this audit exists to re-check.

⛔ WHAT STAYS OUT, and each for a reason rather than to save space:
  .uasset/.umap   binary, unreadable by the desk, and the graph audits
                  read them through the editor anyway
  frames          EXR/PNG/JPG/TIF -- the sidecars carry the measurements
  .npy            binary arrays
  .git objects    the history is exported as TEXT instead, which is what
                  can actually be read
  >5 MB           any single file, whatever it is

⭐ DELETED-BUT-TRUE INFORMATION. CLAUDE.md, STATE.md and the registers
have been rewritten many times, and a value that was correct in August
and was later dropped is exactly what a "what did we already know"
audit needs. So every VERSION of those files is exported: one file per
commit that touched them, named by date and short sha.

⛔ THE FORGE IS A SEPARATE PRODUCT and is marked as one in the tree.
`forge_tool/` and `forge_runs/` share the repo with the landscape
pipeline but are not it; the desk should not read a forge recipe as a
landscape claim.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile

def _find_repo(start):
    """Walk up to the directory holding CLAUDE.md.

    ⛔ Counting `dirname()` calls is how this got the root wrong on its
    first run: the script sits THREE levels deep, the count said two, and
    every include prefix reported MISSING while the run still "succeeded"
    with four files and wrote a zip. A marker file cannot be off by one;
    a count can.
    """
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "CLAUDE.md")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise SystemExit("no CLAUDE.md above %s" % start)
        d = nd


REPO = _find_repo(__file__)
OUT = os.path.join(REPO, "research", "audit")
MAX_BYTES = 5 * 1024 * 1024
PART_LIMIT = 200 * 1024 * 1024

DROP_EXT = {".uasset", ".umap", ".exr", ".png", ".jpg", ".jpeg", ".tif",
            ".tiff", ".npy", ".bmp", ".tga", ".dds", ".fbx", ".obj",
            ".mhpkg", ".zip", ".7z", ".bin", ".pdb", ".exe", ".dll",
            ".pyc", ".abc", ".usd", ".usdz", ".wav", ".mp4"}
DROP_DIR_PARTS = {".git", "node_modules", "__pycache__", "Intermediate",
                  "DerivedDataCache", "Saved", "Binaries", "Build",
                  "site-packages"}

# Everything the ruling names, as PREFIXES. A prefix that does not exist
# is reported rather than silently contributing nothing.
INCLUDE = [
    "recipes", "scripts", "research", "plans", ".claude", "commits",
    "docs", "city", "encounters", "foliage", "terrain", "characters",
    "examples", "forge_tool", "hero",
]
ROOT_GLOBS = (".md", ".json", ".txt", ".cfg", ".ini", ".toml")
SEPARATE_PRODUCT = ("forge_tool", "forge_runs", "hero")


def skip_dir(rel):
    r = rel.replace("\\", "/")
    # The audit's own output must not be swept into its own corpus.
    if r.startswith("research/audit/"):
        return True
    parts = r.split("/")
    return any(p in DROP_DIR_PARTS for p in parts)


def collect():
    kept, dropped = [], {"ext": 0, "size": 0, "dir": 0}
    seen = set()

    def add(path):
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        if rel in seen:
            return
        if skip_dir(rel):
            dropped["dir"] += 1
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in DROP_EXT:
            dropped["ext"] += 1
            return
        try:
            sz = os.path.getsize(path)
        except OSError:
            return
        if sz > MAX_BYTES:
            dropped["size"] += 1
            return
        seen.add(rel)
        kept.append((rel, sz))

    for name in sorted(os.listdir(REPO)):
        p = os.path.join(REPO, name)
        if os.path.isfile(p) and os.path.splitext(name)[1].lower() in ROOT_GLOBS:
            add(p)
    for top in INCLUDE:
        base = os.path.join(REPO, top)
        if not os.path.isdir(base):
            print("  MISSING prefix: %s" % top)
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in DROP_DIR_PARTS]
            for f in files:
                add(os.path.join(root, f))
    # _verify: sidecars and text only
    vbase = os.path.join(REPO, "_verify")
    for root, dirs, files in os.walk(vbase):
        dirs[:] = [d for d in dirs if d not in DROP_DIR_PARTS]
        for f in files:
            if os.path.splitext(f)[1].lower() in (".json", ".jsonl", ".txt",
                                                  ".md", ".log", ".ini",
                                                  ".csv"):
                add(os.path.join(root, f))
    return kept, dropped


def git_history(dest):
    os.makedirs(dest, exist_ok=True)
    log = subprocess.run(
        ["git", "log", "--stat", "--date=iso"], cwd=REPO,
        capture_output=True, text=True, errors="replace").stdout
    with open(os.path.join(dest, "git_log_stat.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(log)
    # ⭐ EVERY VERSION OF ALL OF THEM. RULED 2026-09-14: capture
    # everything, no trimming.
    #
    # I had dropped LESSONS.md and RECIPES.md on the argument that they
    # are APPEND-ONLY ("never delete from it", "never delete a locked
    # recipe") so nothing true could be lost from them. That argument is
    # about the FILES' law, not about what the files actually did -- and
    # an audit whose whole purpose is to find where the record and the
    # behaviour diverged cannot assume the record obeyed its own rule.
    # If a locked recipe ever WAS edited or a lesson trimmed, the only
    # place that shows is the per-commit history, and dropping it would
    # have hidden exactly the class of thing being looked for.
    #
    # Cost: 332 x 1.8 MB + 253 x 1.0 MB. That is the reason for the
    # multi-part zip, not a reason to leave them out.
    files = ["CLAUDE.md", "STATE.md", "LESSONS.md", "RECIPES.md",
             "research/brief3/REGISTER_ADDENDUM.md"]
    # every register anywhere
    reg = subprocess.run(["git", "ls-files", "*REGISTER*"], cwd=REPO,
                         capture_output=True, text=True).stdout.split()
    files.extend(r for r in reg if r not in files)
    manifest = {}
    for f in files:
        shas = subprocess.run(
            ["git", "log", "--format=%h|%ad", "--date=short", "--", f],
            cwd=REPO, capture_output=True, text=True).stdout.strip()
        if not shas:
            continue
        rows = []
        safe = f.replace("/", "__")
        sub = os.path.join(dest, "versions", safe)
        os.makedirs(sub, exist_ok=True)
        for line in shas.splitlines():
            sha, date = line.split("|", 1)
            blob = subprocess.run(["git", "show", "%s:%s" % (sha, f)],
                                  cwd=REPO, capture_output=True,
                                  text=True, errors="replace")
            if blob.returncode:
                continue
            name = "%s_%s.md" % (date, sha)
            with open(os.path.join(sub, name), "w",
                      encoding="utf-8") as fh:
                fh.write(blob.stdout)
            rows.append({"commit": sha, "date": date,
                         "bytes": len(blob.stdout)})
        manifest[f] = rows
        print("  %-46s %d versions" % (f, len(rows)))
    with open(os.path.join(dest, "versions_manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest


def main():
    os.makedirs(OUT, exist_ok=True)
    hist = os.path.join(OUT, "_history")
    print("exporting git history as text ...")
    manifest = git_history(hist)

    print("collecting corpus ...")
    kept, dropped = collect()
    # the exported history joins the corpus
    for root, _d, files in os.walk(hist):
        for f in files:
            p = os.path.join(root, f)
            kept.append((os.path.relpath(p, REPO).replace("\\", "/"),
                         os.path.getsize(p)))
    total = sum(s for _r, s in kept)
    print("  %d files, %.1f MB" % (len(kept), total / 1e6))
    print("  dropped: %r" % dropped)

    # one zip, split by top-level folder only if it would exceed the cap
    parts = []
    if total <= PART_LIMIT:
        parts.append(("pipeline_full_2026-09-14.zip", kept))
    else:
        buckets = {}
        for rel, sz in kept:
            top = rel.split("/")[0] if "/" in rel else "_root"
            buckets.setdefault(top, []).append((rel, sz))
        cur, cur_sz, idx = [], 0, 1
        for top in sorted(buckets, key=lambda t: -sum(
                s for _r, s in buckets[t])):
            grp = buckets[top]
            # ⛔ A SINGLE FOLDER CAN EXCEED THE CAP ON ITS OWN, and
            # grouping whole folders then silently overshooting is how
            # the first run wrote a 223.7 MB "part" against a 200 MB
            # limit. Oversized folders are split WITHIN themselves.
            for rel, sz in grp:
                if cur and cur_sz + sz > PART_LIMIT:
                    parts.append(
                        ("pipeline_full_2026-09-14_part%d.zip" % idx, cur))
                    idx += 1
                    cur, cur_sz = [], 0
                cur.append((rel, sz))
                cur_sz += sz
        if cur:
            parts.append(("pipeline_full_2026-09-14_part%d.zip" % idx, cur))

    written = []
    for name, items in parts:
        zp = os.path.join(OUT, name)
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=6) as z:
            for rel, _sz in items:
                z.write(os.path.join(REPO, rel), rel)
            note = ("These folders are a SEPARATE PRODUCT sharing the "
                    "repo and are not the landscape pipeline: %s\n"
                    % ", ".join(SEPARATE_PRODUCT))
            z.writestr("_SEPARATE_PRODUCTS.txt", note)
        written.append({"zip": name,
                        "files": len(items),
                        "bytes": os.path.getsize(zp)})
        print("  wrote %s  %d files  %.1f MB"
              % (name, len(items), os.path.getsize(zp) / 1e6))

    stats = {"files_collected": len(kept),
             "bytes_uncompressed": total,
             "dropped": dropped,
             "parts": written,
             "history_versions": {k: len(v) for k, v in manifest.items()}}
    with open(os.path.join(OUT, "corpus_stats.json"), "w",
              encoding="utf-8") as fh:
        json.dump(stats, fh, indent=1)
    # tree two levels deep
    tree = {}
    for rel, sz in kept:
        p = rel.split("/")
        k = p[0] if len(p) == 1 else "%s/%s" % (p[0], p[1])
        e = tree.setdefault(k, [0, 0])
        e[0] += 1
        e[1] += sz
    with open(os.path.join(OUT, "corpus_tree.txt"), "w",
              encoding="utf-8") as fh:
        for k in sorted(tree):
            fh.write("%-56s %5d files  %8.2f MB\n"
                     % (k, tree[k][0], tree[k][1] / 1e6))
    print("wrote corpus_stats.json and corpus_tree.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
