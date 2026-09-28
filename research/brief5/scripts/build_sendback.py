#!/usr/bin/env python3
"""Build the Brief 5 desk send-back zip: research/brief5_b5.zip (gitignored,
self-contained, mirrors the tree, no __pycache__). Idempotent."""
import os
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(REPO, "research", "brief5")
OUT = os.path.join(REPO, "research", "brief5_r.zip")


def main():
    z = zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED)
    n = 0

    def add(src, arc):
        nonlocal n
        if os.path.exists(src):
            z.write(src, arc)
            n += 1

    for f in ("BASELINE.md", "PCG_NOTES.md", "BRIEF.md", "FOR_CLAUDE_CODE.md",
              "REGISTER.md", "ITEM8_PLAN.md"):
        add(os.path.join(BASE, f), "brief5/" + f)
    for f in ("INDEX_r.md", "INDEX_c.md", "INDEX_b5.md", "INDEX_v.md",
              "OVERNIGHT_LOG.md", "INDEX_v3.md"):
        add(os.path.join(BASE, "for_desk", f), "brief5/for_desk/" + f)
    for sub in ("input", "derived"):
        for dp, _dirs, files in os.walk(os.path.join(BASE, sub)):
            if "__pycache__" in dp:
                continue
            for f in sorted(files):
                if f.endswith((".json", ".md", ".png")):
                    full = os.path.join(dp, f)
                    arc = "brief5/" + os.path.relpath(full, BASE).replace(os.sep, "/")
                    add(full, arc)
    for f in sorted(os.listdir(os.path.join(BASE, "scripts"))):
        if f.endswith(".py"):
            add(os.path.join(BASE, "scripts", f), "brief5/scripts/" + f)
    for f in ("check_recipe_lods.py", "push_chunked.py", "git_blob_audit.py"):
        add(os.path.join(REPO, "scripts", f), "scripts/" + f)
    add(os.path.join(REPO, "research", "GIT_LFS_AUDIT.md"), "GIT_LFS_AUDIT.md")
    z.close()
    print("%s: %d files, testzip=%s" % (os.path.basename(OUT), n,
                                        zipfile.ZipFile(OUT).testzip()))


if __name__ == "__main__":
    main()
