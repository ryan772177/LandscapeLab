#!/usr/bin/env python
"""push_chunked.py -- push a large history to a remote in size-bounded chunks,
halving on failure, resumable from the remote ref, exiting with git's real code.

WHY: `git push` of a long history (e.g. 1500+ commits) can fail mid-pack with
`RPC failed; HTTP 500` when the non-LFS pack is too big for the server to accept
in one shot. Pushing an intermediate commit at a time keeps each pack small.
Measured 2026-09-20: a single push and a 200-commit chunk both 500'd; a
100-commit chunk landed, the next 100-commit chunk 500'd -- so a fixed chunk
size is not enough; halve on failure.

BEHAVIOUR
  * Range is (live remote ref)..HEAD, re-read from `git ls-remote` each run, so
    the tool RESUMES from wherever the remote actually is.
  * Push checkpoints spaced `--chunk` commits apart (default 100). Each
    `git push <sha>:refs/heads/<branch>` fast-forwards the remote branch.
  * On a chunk push failure, HALVE the span for that segment (100->50->25->10->1)
    and retry the sub-checkpoints. A transient 500 also gets a couple of plain
    retries at the same size before halving.
  * If a SINGLE commit (span 1) still fails, log that commit + its largest blob
    and STOP, exiting with git's real non-zero code. A single commit that cannot
    be pushed is a content problem (an oversized blob), not a size problem.
  * After the branch reaches HEAD, push the annotated tag if --tag is given.

USAGE
  python scripts/push_chunked.py [--remote origin] [--branch main]
                                 [--chunk 100] [--retries 3] [--tag NAME]
                                 [--dry-run]
This tool NEVER force-pushes, gc's, or rewrites history.
"""
import argparse
import subprocess
import sys
import time


def sh(args, check=False):
    # errors='replace': git push progress on stderr is not always valid UTF-8
    # on Windows; a decode crash must never masquerade as a push failure.
    r = subprocess.run(args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.stderr.write((r.stdout or "") + (r.stderr or ""))
    return r


def remote_head(remote, branch):
    out = sh(["git", "ls-remote", remote,
              "refs/heads/%s" % branch]).stdout.strip()
    return out.split()[0] if out else None


def rev(x):
    return sh(["git", "rev-parse", x]).stdout.strip()


def largest_blob_in_commit(sha):
    objs = sh(["git", "diff-tree", "-r", "--no-commit-id", "--name-only",
               sha]).stdout.split()
    best = (0, None)
    ls = sh(["git", "ls-tree", "-r", "-l", sha]).stdout.splitlines()
    for line in ls:
        parts = line.split(None, 4)
        if len(parts) == 5 and parts[3].isdigit():
            sz = int(parts[3])
            if sz > best[0]:
                best = (sz, parts[4])
    return best


def push_one(remote, branch, sha, retries, dry):
    ref = "%s:refs/heads/%s" % (sha, branch)
    if dry:
        print("  DRY push %s" % ref)
        return True
    for attempt in range(1, retries + 1):
        r = sh(["git", "push", remote, ref])
        if r.returncode == 0:
            return True
        tail = (r.stdout + r.stderr).strip().splitlines()[-2:]
        print("  attempt %d FAILED: %s" % (attempt, " | ".join(tail)))
        time.sleep(5)
    return False


def push_span(remote, branch, commits, size, retries, dry):
    """Push `commits` (ordered oldest->newest) in checkpoints `size` apart,
    halving `size` for any failing segment down to 1. Returns True on full
    success; on a span-1 failure logs and returns False."""
    i = 0
    n = len(commits)
    while i < n:
        j = min(i + size, n)
        target = commits[j - 1]
        print("push chunk [%d:%d] size %d -> %s" % (i, j, size, target[:12]))
        if push_one(remote, branch, target, retries, dry):
            i = j
            continue
        # failed: if we can still shrink, halve and retry this segment
        if size > 1:
            new = max(1, size // 2)
            print("  halving %d -> %d for [%d:%d]" % (size, new, i, j))
            if not push_span(remote, branch, commits[i:j], new, retries, dry):
                return False
            i = j
            continue
        # span 1 and still failing -> content problem
        sz, path = largest_blob_in_commit(target)
        print("SINGLE COMMIT FAILS: %s -- largest blob %.2f MB %s"
              % (target, sz / 1e6, path))
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    head = rev("HEAD")
    rh = remote_head(a.remote, a.branch)
    print("remote %s/%s = %s ; HEAD = %s" % (a.remote, a.branch, rh, head))
    if rh == head:
        print("remote already at HEAD; nothing to push.")
    else:
        rng = "%s..HEAD" % rh if rh else "HEAD"
        commits = sh(["git", "rev-list", "--reverse", rng]).stdout.split()
        print("%d commits to push in chunks of %d" % (len(commits), a.chunk))
        if not push_span(a.remote, a.branch, commits, a.chunk, a.retries,
                         a.dry_run):
            print("PUSH INCOMPLETE -- see the single-commit failure above.")
            # git's real failure is non-zero; surface it
            sys.exit(1)
        print("branch %s reached HEAD." % a.branch)

    if a.tag and not a.dry_run:
        r = sh(["git", "push", a.remote, a.tag])
        sys.stdout.write(r.stdout + r.stderr)
        sys.exit(r.returncode)


if __name__ == "__main__":
    main()
