"""build_desk_core.py — the small zip: source, recipes, record. No evidence.

desk_core.zip is what the desk reads first: everything needed to verify
a claim against the code and the record, with the bulk left behind.

IN   scripts/ (every .py incl. payloads and archived), recipes/,
     every CURRENT .md at repo root, every CURRENT register file,
     research/brief1..4/ (no zips), plans/, .claude/, commits/
OUT  sidecars, _verify/, git-history versions, anything over 5 MB
"""
import io
import json
import os
import zipfile


def _find_repo(start):
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
MAX = 5 * 1024 * 1024
SKIP = {".git", "node_modules", "__pycache__", "Intermediate", "Saved",
        "DerivedDataCache", "Binaries", "Build", "site-packages", "_trash"}
DROP_EXT = {".zip", ".7z", ".uasset", ".umap", ".exr", ".png", ".jpg",
            ".jpeg", ".tif", ".tiff", ".npy", ".pyc", ".bin", ".exe",
            ".dll", ".fbx", ".mhpkg"}

kept = []
seen = set()


def add(path):
    rel = os.path.relpath(path, REPO).replace("\\", "/")
    if rel in seen:
        return
    parts = rel.split("/")
    if any(p in SKIP for p in parts):
        return
    if rel.startswith("research/audit/"):
        return
    if os.path.splitext(path)[1].lower() in DROP_EXT:
        return
    try:
        sz = os.path.getsize(path)
    except OSError:
        return
    if sz > MAX:
        return
    seen.add(rel)
    kept.append((rel, sz))


def walk(top, exts=None):
    base = os.path.join(REPO, top)
    if not os.path.isdir(base):
        return
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            if exts and os.path.splitext(f)[1].lower() not in exts:
                continue
            add(os.path.join(root, f))


walk("scripts")
walk("recipes")
walk("plans")
walk(".claude")
walk("commits")
for b in ("brief1", "brief2", "brief3", "brief4", "brief"):
    walk("research/" + b)
# current root .md
for name in sorted(os.listdir(REPO)):
    p = os.path.join(REPO, name)
    if os.path.isfile(p) and name.lower().endswith(".md"):
        add(p)
# every current register file anywhere
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if "REGISTER" in f.upper() and f.lower().endswith((".md", ".json")):
            add(os.path.join(root, f))

zp = os.path.join(OUT, "desk_core.zip")
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel, _s in kept:
        z.write(os.path.join(REPO, rel), rel)
print("files: %d" % len(kept))
print("uncompressed: %.2f MB" % (sum(s for _r, s in kept) / 1e6))
print("zip: %s  %.2f MB" % (zp, os.path.getsize(zp) / 1e6))
