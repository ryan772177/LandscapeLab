#!/usr/bin/env python3
"""Build the Item-8 desk send-back zip: research/brief5_i8.zip (gitignored,
self-contained, mirrors the tree, no __pycache__). Includes the census fence
evidence from _verify (which is gitignored, so it rides in the zip). Idempotent.
"""
import os
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(REPO, "research", "brief5")
OUT = os.path.join(REPO, "research", "brief5_i8.zip")


def main():
    z = zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED)
    n = 0

    def add(src, arc):
        nonlocal n
        if os.path.exists(src):
            z.write(src, arc)
            n += 1

    add(os.path.join(BASE, "ITEM8_PLAN.md"), "brief5/ITEM8_PLAN.md")
    add(os.path.join(BASE, "for_desk", "INDEX_i8.md"), "brief5/for_desk/INDEX_i8.md")
    # every item8 input + all crops/frames in derived/item8
    for dp, _dirs, files in os.walk(os.path.join(BASE, "input")):
        for f in sorted(files):
            if f.startswith("item8") and f.endswith((".json", ".md")):
                full = os.path.join(dp, f)
                add(full, "brief5/" + os.path.relpath(full, BASE).replace(
                    os.sep, "/"))
    for dp, _dirs, files in os.walk(os.path.join(BASE, "derived", "item8")):
        for f in sorted(files):
            if f.endswith(".png"):
                full = os.path.join(dp, f)
                add(full, "brief5/" + os.path.relpath(full, BASE).replace(
                    os.sep, "/"))
    for f in sorted(os.listdir(os.path.join(BASE, "scripts"))):
        if f.startswith("item8") and f.endswith(".py"):
            add(os.path.join(BASE, "scripts", f), "brief5/scripts/" + f)
    # census fence evidence (gitignored raw output)
    for f in ("census_before.json", "census_after.json"):
        add(os.path.join(REPO, "_verify", "perf", "item8", f),
            "_verify/perf/item8/" + f)
    z.close()
    print("%s: %d files, testzip=%s"
          % (os.path.basename(OUT), n, zipfile.ZipFile(OUT).testzip()))


if __name__ == "__main__":
    main()
