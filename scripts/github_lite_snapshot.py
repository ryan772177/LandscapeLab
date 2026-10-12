"""github_lite_snapshot.py -- build (or extend) the GitHub-facing `github-main`
branch: the current `main` tree MINUS the paths GitHub's free LFS quota cannot
hold, as one commit per snapshot.

WHY THIS EXISTS (2026-09-27). GitHub Free gives 10 GiB of Git LFS storage for
the whole account and counts EVERY object version ever pushed; it frees LFS
storage only when the repository is deleted. This repo's history carried
37.2 GB of LFS, 22.2 GB of it 42,066 versions of World Partition external-actor
packages (~1,000 per world save). Pushes were refused ("exceeded its LFS
budget") and the disk (13 GB free) cannot host a history-rewrite clone. Ryan
chose to recreate the GitHub repo and keep the world OUT of it.

THE CONTRACT
  * `main` (local) is the FULL repo: world packages, fence tags, git-as-undo
    for the D3 driver and R-EDITOR-CLOSE stay exactly as they were.
  * `github-main` is a DERIVED branch: HEAD's tree with EXCLUDED paths removed,
    committed on top of the previous github-main commit (so GitHub keeps a
    linear history of snapshots), and pushed as GitHub `main`.
  * The world is rebuildable from recipes/ + foliage/ + city/ + encounters/
    (pipeline rule 3); GitHub holds the recipe, this machine holds the world.
  * NEVER push local `main` or any tag to GitHub: their trees reference the
    dropped LFS objects and the push is refused (or, worse, accepted and the
    quota is gone again).

Usage:
    python scripts/github_lite_snapshot.py            # build github-main from HEAD
    python scripts/github_lite_snapshot.py --push     # ...and push it as origin main
    python scripts/github_lite_snapshot.py --dry-run  # list what would be dropped

Exit codes: 0 ok; 1 error; 2 refused (dirty tree, not on main, or a dropped
path leaked into the snapshot).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LITE_BRANCH = "github-main"
# Paths dropped from the GitHub snapshot. Each one is either the world
# (rebuildable from recipes; ~9 GB of LFS at HEAD, 22 GB across history) or a
# parked binary the desk does not need on GitHub.
EXCLUDE = [
    "LandscapeLab/Content/__ExternalActors__",
    "LandscapeLab/Content/__ExternalObjects__",
    "_verify/bench",
]
# 2026-09-27: Content/Hero, characters/AlpineHero and hero/dna STAY in the
# snapshot (~1 GB). No external drive exists, so after the GitHub delete this
# machine is the only copy of everything not on GitHub; the hero binaries are
# outputs of a parked pipeline and not cheaply regenerable, while the world
# packages ARE regenerable from the recipes. Snapshot ~6.1 GB of LFS.


def ai_restricted(paths):
    """2026-10-12: the repo on GitHub is PUBLIC (unauthenticated API 200), so everything the AI-input register
    forbids (recipes/ai_restrictions.json via scripts/ai_input_guard.match -- the ONE declaration: kit renders,
    derived kit packages, the levels that place the kit) is dropped from the snapshot. A public repo is crawlable,
    which is a route into exactly the generation-model input the licence forbids. Fail closed: a guard that cannot
    load raises, and the snapshot is not built."""
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import ai_input_guard
    reg = ai_input_guard.load_registry()
    out = []
    for p in paths:
        r, why = ai_input_guard.match(os.path.join(REPO, p), reg)
        if not r:
            continue
        # audit 2026-10-12 F3 (ruled): recipe JSON caught ONLY by the package/level leaf-substring rule (e.g.
        # recipes/rvt_alpine8k.json via 'alpine8k') is parameters, not kit content, and GitHub is its only
        # off-machine copy -- kept. A recipe matched by a source/render glob is still dropped.
        if p.startswith("recipes/") and p.endswith(".json") and str(why).startswith("names the restricted"):
            continue
        out.append(p)
    return out


def _z(args, env=None):
    """NUL-separated, UNQUOTED git path listing (audit 2026-10-12 F1: core.quotePath C-quotes non-ASCII paths,
    which then match no glob -- a fail-open in the licence gate)."""
    raw = subprocess.run(["git", "-C", REPO, *args, "-z"], env=env, capture_output=True, check=True).stdout
    return [p for p in raw.decode("utf-8").split("\0") if p]


def git(*args, check=True, text=True):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=text)
    if check and r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), (r.stderr or r.stdout).strip()[:400]))
    return r.stdout.strip() if text else r.stdout


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="push github-main as origin main")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--remote", default="origin")
    a = ap.parse_args(argv)

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        print("REFUSE: on %r, snapshot only from main" % branch)
        return 2
    if git("status", "--porcelain"):
        print("REFUSE: working tree not clean; commit or stash first")
        return 2
    head = git("rev-parse", "HEAD")
    head_short = head[:12]

    # Build the tree in a TEMPORARY index so the real index is untouched.
    env = dict(os.environ)
    tmp_index = os.path.join(REPO, ".git", "lite-index")
    env["GIT_INDEX_FILE"] = tmp_index
    if os.path.exists(tmp_index):
        os.remove(tmp_index)
    subprocess.run(["git", "-C", REPO, "read-tree", head], env=env, check=True)
    dropped = 0
    for p in EXCLUDE:
        r = subprocess.run(["git", "-C", REPO, "ls-files", "--", p], env=env,
                           capture_output=True, text=True)
        n = len([l for l in r.stdout.splitlines() if l.strip()])
        if n:
            subprocess.run(["git", "-C", REPO, "rm", "-r", "--cached", "-q", "--", p],
                           env=env, check=True)
        dropped += n
        print("  drop %-48s %6d files" % (p, n))
    remaining = _z(["ls-files"], env=env)
    restricted = ai_restricted(remaining)
    if restricted:
        lst = os.path.join(REPO, ".git", "lite-restricted.txt")
        with open(lst, "wb") as f:
            # :(literal) so a *, ? or [ in a filename is not a pattern (audit F2)
            f.write(b"\0".join((":(literal)" + p).encode("utf-8") for p in restricted) + b"\0")
        subprocess.run(["git", "-C", REPO, "rm", "--cached", "-q", "--pathspec-from-file=" + lst,
                        "--pathspec-file-nul"], env=env, check=True)
        os.remove(lst)
    dropped += len(restricted)
    print("  drop %-48s %6d files" % ("AI-restricted (recipes/ai_restrictions.json)", len(restricted)))
    if a.dry_run:
        for p in restricted:
            print("    restricted: %s" % p)
        print("DRY RUN: would drop %d files from the snapshot of %s" % (dropped, head_short))
        os.remove(tmp_index)
        return 0
    tree = subprocess.run(["git", "-C", REPO, "write-tree"], env=env,
                          capture_output=True, text=True, check=True).stdout.strip()
    os.remove(tmp_index)

    # LEAK GATE: nothing under an excluded path may be in the tree.
    listing = _z(["ls-tree", "-r", "--name-only", tree])
    leaked = [l for l in listing if l.startswith(tuple(EXCLUDE))]
    if leaked:
        print("REFUSE: %d excluded paths leaked into the snapshot, e.g. %s" % (len(leaked), leaked[0]))
        return 2
    # the AI gate re-run on the WRITTEN tree (a different read from the index the drop worked on)
    leaked_ai = ai_restricted(listing)
    if leaked_ai:
        print("REFUSE: %d AI-restricted paths in the snapshot tree, e.g. %s" % (len(leaked_ai), leaked_ai[0]))
        return 2

    parent = None
    r = subprocess.run(["git", "-C", REPO, "rev-parse", "-q", "--verify", LITE_BRANCH],
                       capture_output=True, text=True)
    if r.returncode == 0:
        parent = r.stdout.strip()
        if git("rev-parse", parent + "^{tree}") == tree:
            print("github-main already at this snapshot (%s); nothing to do" % head_short)
            if a.push:
                git("push", a.remote, "%s:main" % LITE_BRANCH)
                print("pushed %s -> %s main" % (LITE_BRANCH, a.remote))
            return 0
    subject = git("log", "-1", "--format=%s", head)
    msg = ("lite snapshot of main @ %s: %s\n\nDerived by scripts/github_lite_snapshot.py; "
           "excludes %s and every AI-restricted path (recipes/ai_restrictions.json). Full history stays local "
           "on main." % (head_short, subject, ", ".join(EXCLUDE)))
    msg_path = os.path.join(REPO, ".git", "lite-msg.txt")
    with open(msg_path, "w", encoding="utf-8") as f:
        f.write(msg)
    args = ["commit-tree", tree, "-F", msg_path]
    if parent:
        args += ["-p", parent]
    new = git(*args)
    os.remove(msg_path)
    git("update-ref", "refs/heads/%s" % LITE_BRANCH, new)
    print("%s -> %s (tree %s, %d files dropped, parent %s)" % (
        LITE_BRANCH, new[:12], tree[:12], dropped, parent[:12] if parent else "none"))
    if a.push:
        out = subprocess.run(["git", "-C", REPO, "push", a.remote, "%s:main" % LITE_BRANCH],
                             capture_output=True, text=True)
        print((out.stdout + out.stderr).strip()[-600:])
        if out.returncode != 0:
            return 1
        print("pushed %s -> %s main" % (LITE_BRANCH, a.remote))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print("ERROR: %s" % e)
        sys.exit(1)
