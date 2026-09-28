#!/usr/bin/env python
"""git_blob_audit.py -- READ-ONLY. The largest NON-LFS blobs in a commit range,
and which file extensions escape the .gitattributes LFS filter.

Motivation: a `git push` of a large history can fail with HTTP 500 mid-pack when
the non-LFS pack is big. This finds what is bloating the pack so an operator can
PROPOSE .gitattributes additions (this tool applies nothing).

Usage: python scripts/git_blob_audit.py [RANGE] [MIN_KB] [TOPN]
  RANGE  default 364716f5..HEAD
  MIN_KB minimum blob size to consider, default 200
  TOPN   how many to print, default 30
"""
import collections
import os
import subprocess
import sys

RANGE = sys.argv[1] if len(sys.argv) > 1 else "364716f5..HEAD"
MIN_BYTES = (int(sys.argv[2]) if len(sys.argv) > 2 else 200) * 1000
TOPN = int(sys.argv[3]) if len(sys.argv) > 3 else 30


def run(args, inp=None):
    return subprocess.run(args, input=inp, capture_output=True, text=True).stdout


def main():
    objs = run(["git", "rev-list", "--objects", RANGE]).splitlines()
    paths = {}
    for line in objs:
        parts = line.split(" ", 1)
        if len(parts) == 2:
            paths[parts[0]] = parts[1]
    bc = run(["git", "cat-file",
              "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
             inp=chr(10).join(paths.keys())).splitlines()
    blobs = []
    for l in bc:
        p = l.split()
        if len(p) == 3 and p[1] == "blob":
            blobs.append((int(p[2]), p[0], paths.get(p[0], "?")))
    blobs.sort(reverse=True)

    # An LFS-tracked file's blob IN GIT is a ~130-byte pointer, so ANY blob at
    # or above a few KB is real (non-LFS) content by construction. With
    # MIN_BYTES >= 200 KB the size filter alone identifies non-LFS blobs; no
    # per-blob cat-file needed (that was O(n) subprocess spawns and timed out).
    nonlfs = [(size, path) for size, sha, path in blobs if size >= MIN_BYTES]

    print("=== TOP %d NON-LFS BLOBS in %s (>= %d KB) ==="
          % (TOPN, RANGE, MIN_BYTES // 1000))
    for size, path in nonlfs[:TOPN]:
        print("%9.2f MB  %s" % (size / 1e6, path))

    ext = collections.Counter()
    extbytes = collections.Counter()
    for size, path in nonlfs:
        e = os.path.splitext(path)[1].lower() or "(noext)"
        ext[e] += 1
        extbytes[e] += size
    print()
    print("=== extensions among non-LFS blobs (count, total MB) ===")
    for e, c in ext.most_common():
        print("%-12s %5d  %9.1f MB" % (e, c, extbytes[e] / 1e6))
    print()
    print("total non-LFS blobs >= %d KB: %d, sum %.1f MB"
          % (MIN_BYTES // 1000, len(nonlfs), sum(s for s, _ in nonlfs) / 1e6))


if __name__ == "__main__":
    main()
