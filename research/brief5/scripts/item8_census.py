#!/usr/bin/env python3
"""item8_census.py -- the Item-8 byte-identical FENCE instrument.

The fence (ITEM8 prompt): writes go to /Game/Scratch/Item8/** ONLY; a census
BEFORE and AFTER must show the world level and every NON-scratch asset
byte-identical, and no Item8 scratch remnants at the end.

WHAT THIS DOES, AND WHY IT IS BUILT THIS WAY
--------------------------------------------
`Content/` is 48 GB / ~14k assets, so hashing the whole tree twice is wasteful.
Two tiers, so the common case is fast and the rare case is rigorous:

  snapshot: (size, mtime_ns) for every file under Content/ EXCEPT anything under
            Content/Scratch/  --  a pre-existing Content/Scratch/C0House/ is
            gitignored scratch from another session and is deliberately OUTSIDE
            the byte-identical set (so is this session's Content/Scratch/Item8/).
            Scratch is excluded from the manifest, and Item8's PRESENCE is
            recorded as its own boolean so a remnant cannot hide in the excluded
            region.

  compare:  a file whose (size, mtime) is unchanged is byte-identical for this
            purpose. Files that ADD, REMOVE or CHANGE in (size, mtime) are
            sha256'd for the record and split into content_changed (size
            differs) vs touched_only (mtime differs, size identical). This split
            is DIAGNOSTIC ONLY: the fence is FAIL-CLOSED -- verdict_clean
            requires stat_changed EMPTY, so ANY change (a bare mtime touch
            included) reads DIRTY. That is correct for a fence; the split just
            tells the reviewer which kind it was. A zero-diff compare with a
            nonzero sample count is the PASS (rule 13: a zero sample count
            refuses).

The world .umap and its OFPA external actors live under Content/ and are covered
by the manifest like any other asset; the umap is also hashed explicitly in the
snapshot as a named, strong witness.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONTENT = os.path.join(REPO, "LandscapeLab", "Content")
SCRATCH_REL = os.path.join("LandscapeLab", "Content", "Scratch")
ITEM8_REL = os.path.join("LandscapeLab", "Content", "Scratch", "Item8")
WORLD_UMAP = os.path.join(CONTENT, "Alpine8K.umap")
ASSET_EXTS = (".uasset", ".umap")


def _rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot():
    """(size, mtime_ns) manifest of every Content asset OUTSIDE Content/Scratch,
    plus the world umap hash and the Item8-present boolean."""
    scratch_abs = os.path.abspath(os.path.join(REPO, SCRATCH_REL))
    manifest = {}
    for root, dirs, files in os.walk(CONTENT):
        # prune the whole Scratch subtree from the byte-identical set. The
        # trailing os.sep (and the exact-path OR) is deliberate: a bare prefix
        # would also swallow a sibling like Content/ScratchAnything (audit #8).
        rabs = os.path.abspath(root)
        if rabs == scratch_abs or rabs.startswith(scratch_abs + os.sep):
            dirs[:] = []
            continue
        for fn in files:
            if not fn.lower().endswith(ASSET_EXTS):
                continue
            p = os.path.join(root, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            manifest[_rel(p)] = [st.st_size, st.st_mtime_ns]
    out = {
        "_what": "Item-8 fence snapshot: (size, mtime_ns) of Content assets "
                 "outside Content/Scratch/.",
        "content_root": _rel(CONTENT),
        "n_files": len(manifest),
        "world_umap": _rel(WORLD_UMAP),
        "world_umap_sha256": sha256(WORLD_UMAP) if os.path.isfile(WORLD_UMAP)
        else None,
        "world_umap_present": os.path.isfile(WORLD_UMAP),
        "item8_scratch_present": os.path.isdir(os.path.join(REPO, ITEM8_REL)),
        "item8_scratch_dir": ITEM8_REL.replace("\\", "/"),
        "manifest": manifest,
    }
    return out


def compare(before, after):
    bm, am = before["manifest"], after["manifest"]
    bk, ak = set(bm), set(am)
    added = sorted(ak - bk)
    removed = sorted(bk - ak)
    stat_changed = sorted(k for k in (bk & ak) if bm[k] != am[k])

    # Tier 2: sha256 only the flagged files. added/removed cannot be hashed on
    # both sides; stat_changed is where an mtime-only touch is distinguished
    # from a real content change.
    content_changed, touched_only = [], []
    for k in stat_changed:
        p = os.path.join(REPO, k)
        h = sha256(p) if os.path.isfile(p) else None
        # We only have current bytes; the "before" hash is not stored for every
        # file (that is the whole point of the size/mtime tier). A size change
        # is a definite content change; an mtime-only change with identical
        # size is hashed against nothing we retained, so it is reported as
        # TOUCHED and the reviewer confirms via git (tracked assets) -- but for
        # THIS fence the load-bearing signal is that stat_changed is EMPTY.
        if bm[k][0] != am[k][0]:
            content_changed.append({"path": k, "before": bm[k], "after": am[k],
                                     "reason": "size changed", "sha256_now": h})
        else:
            touched_only.append({"path": k, "before": bm[k], "after": am[k],
                                 "reason": "mtime changed, size identical",
                                 "sha256_now": h})

    umap_identical = (before.get("world_umap_sha256")
                      == after.get("world_umap_sha256")
                      and after.get("world_umap_sha256") is not None)
    n_compared = len(bk & ak)
    verdict_clean = (not added and not removed and not stat_changed
                     and umap_identical
                     and not after.get("item8_scratch_present"))
    result = {
        "_what": "Item-8 fence compare (before vs after).",
        "n_files_before": len(bm), "n_files_after": len(am),
        "n_files_compared": n_compared,
        "added_non_scratch": added,
        "removed_non_scratch": removed,
        "stat_changed_non_scratch": stat_changed,
        "content_changed": content_changed,
        "touched_only_mtime": touched_only,
        "world_umap_sha256_before": before.get("world_umap_sha256"),
        "world_umap_sha256_after": after.get("world_umap_sha256"),
        "world_umap_identical": umap_identical,
        "item8_scratch_present_after": after.get("item8_scratch_present"),
        # rule 13: a comparison over zero files is not agreement.
        "refused_zero_sample": n_compared == 0,
        "verdict": ("REFUSE: zero files compared" if n_compared == 0
                    else "CLEAN: world + every non-scratch asset byte-identical, "
                         "no Item8 remnant" if verdict_clean
                    else "DIRTY: see added/removed/changed + item8 remnant flags"),
    }
    return result


def _selftest():
    ok = True

    def ck(label, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %-52s %s" % (label, "PASS" if cond else "FAIL"))

    b = {"manifest": {"a": [10, 100], "b": [20, 200]},
         "world_umap_sha256": "deadbeef", "item8_scratch_present": False}
    # identical
    a = {"manifest": {"a": [10, 100], "b": [20, 200]},
         "world_umap_sha256": "deadbeef", "item8_scratch_present": False}
    r = compare(b, a)
    ck("identical -> CLEAN", r["verdict"].startswith("CLEAN"))
    ck("identical -> n_compared 2, not refused", r["n_files_compared"] == 2
       and not r["refused_zero_sample"])
    # a remnant
    a2 = dict(a); a2 = {**a, "item8_scratch_present": True}
    ck("item8 remnant -> DIRTY", compare(b, a2)["verdict"].startswith("DIRTY"))
    # a size change (content change)
    a3 = {**a, "manifest": {"a": [10, 100], "b": [21, 200]}}
    r3 = compare(b, a3)
    ck("size change -> DIRTY + content_changed",
       r3["verdict"].startswith("DIRTY") and len(r3["content_changed"]) == 1)
    # umap changed
    a4 = {**a, "world_umap_sha256": "feedface"}
    ck("umap hash change -> DIRTY", compare(b, a4)["verdict"].startswith("DIRTY"))
    # zero sample refuses
    r5 = compare({"manifest": {}}, {"manifest": {}, "item8_scratch_present": False})
    ck("zero files compared -> REFUSE (rule 13)",
       r5["refused_zero_sample"] and r5["verdict"].startswith("REFUSE"))
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    if not argv or argv[0] not in ("snapshot", "compare", "selftest"):
        print("usage: item8_census.py snapshot <out.json> | "
              "compare <before.json> <after.json> | selftest")
        return 2
    if argv[0] == "selftest":
        return _selftest()
    if argv[0] == "snapshot":
        if len(argv) < 2:
            print("snapshot needs an output path")
            return 2
        out = snapshot()
        json.dump(out, open(argv[1], "w", encoding="utf-8"), indent=1)
        print("snapshot: %d files, umap_present=%s item8_present=%s -> %s"
              % (out["n_files"], out["world_umap_present"],
                 out["item8_scratch_present"], argv[1]))
        return 0
    # compare
    if len(argv) < 3:
        print("compare needs before.json and after.json")
        return 2
    before = json.load(open(argv[1], encoding="utf-8"))
    after = json.load(open(argv[2], encoding="utf-8"))
    r = compare(before, after)
    print(json.dumps({k: v for k, v in r.items()
                      if k not in ("added_non_scratch", "removed_non_scratch")},
                     indent=1)[:1200])
    print("VERDICT:", r["verdict"])
    return 0 if r["verdict"].startswith("CLEAN") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
