"""catalogue_heightmaps.py — build the external-heightmap catalogue.

Implements the EXTERNAL HEIGHTMAP CATALOGUE SPEC locked in RECIPES.md R1.

IDENTITY IS A CONTENT HASH. Not a filename, not a folder index. Both were
measured to drift in the GameDevGary pack:
  - the 512 folder swaps indices 04/05 against every other tier
  - names drift singular/plural across tiers (Mountain/Mountains)
So `sha256` of the file bytes is the key, and name/folder/index are
metadata that may never be used to match, join or deduplicate.

NO CROSS-TIER "SAME MAP" RELATIONSHIP IS EVER RECORDED. The resolution
folders hold INDEPENDENTLY GENERATED terrains -- Hills at 505, 1009 and
2017 are three unrelated landscapes. Recording a link would let a future
session pick a map at 1009, fetch "the same" map at 8129, and get a
different world.

TWO CATEGORIES, and landscape-legality applies to only one:
  TERRAIN  a complete standalone heightmap -> imported as a region's
           landscape, so its resolution MUST be UE-legal (N+1) or be
           cropped (never resampled).
  STAMP    a terrain FEATURE (ridge, canyon, crater) -> composited INTO
           a base heightmap BEFORE import. It never becomes a landscape
           by itself, so N+1 legality DOES NOT APPLY. Recording a
           "needs crop" action against a stamp would be a false defect.

Usage:
    python scripts/catalogue_heightmaps.py            # write catalogues
    python scripts/catalogue_heightmaps.py --print    # summarise only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UE_LEGAL = (505, 1009, 2017, 4033, 8129)

# (root, category, source, licence, catalogue path)
SOURCES = [
    (os.path.join(REPO, "terrain", "external_heightmaps"),
     "TERRAIN",
     "GameDevGary — 50 Free .PNG Heightmaps for Unreal Engine (itch.io)",
     "CC0",
     os.path.join(REPO, "terrain", "external_heightmaps", "catalogue.json")),
    (os.path.join(REPO, "LandscapeLab", "Content", "StampIt"),
     "STAMP",
     "Ultimate StampIT Collection for UE (Fab)",
     "Fab Standard Licence — UE projects only",
     os.path.join(REPO, "terrain", "stampit_catalogue.json")),
]

# One-word character tags, matched against the filename as a HINT. The
# tag_source field records where a tag came from -- "filename" (a name HINT),
# "visual" (confirmed against the pixels), or "none" -- because a hint is not
# a measurement. (There is no "content-verified" tier; "visual" is that tier.)
TAGWORDS = [
    ("archipelago", "archipelago"), ("island", "island"),
    ("mountain", "mountain"), ("highland", "highland"),
    ("hill", "hills"), ("meadow", "meadows"), ("plain", "plains"),
    ("dune", "dunes"), ("canyon", "canyon"), ("crater", "crater"),
    ("wetland", "wetlands"), ("alien", "alien"), ("cliff", "cliffs"),
    ("volcano", "volcano"), ("mesa", "mesa"), ("ridge", "ridge"),
    ("river", "river"), ("valley", "valley"), ("swirl", "swirl"),
    ("voronian", "cellular"), ("bobble", "bobble"),
    # Added after the first StampIT run left 21 of 52 untagged. Ordered
    # so the MORE SPECIFIC needle wins: "rocky_desert" and
    # "monument_desert" must be tested before a bare "desert", and
    # "sedi" (sedimentary) before the generic "rock".
    ("impact", "crater"), ("monument_desert", "mesa"),
    ("rocky_desert", "desert"), ("rocky_plateau", "plateau"),
    ("plateau", "plateau"), ("terrace", "terrace"),
    ("pride_rocks", "outcrop"), ("sedi_rocks", "sedimentary"),
    ("rugged_rocks", "outcrop"), ("stranger_lands", "alien"),
    ("sandy_beach", "beach"), ("beach", "beach"),
    ("tundra", "tundra"), ("desert", "desert"), ("rock", "outcrop"),
]


def tag_for(name):
    low = name.lower()
    for needle, tag in TAGWORDS:
        if needle in low:
            return tag, "filename"
    return "untagged", "none"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def measure(path, category):
    im = Image.open(path)
    mode, (w, h) = im.mode, im.size
    single16 = mode in ("I;16", "I;16B", "I;16L", "I")
    a = np.asarray(im)
    if a.ndim == 3:
        a = a[..., 0]
    a = a.astype(np.float64)

    row = {
        "hash": sha256(path),
        "filename": os.path.basename(path),
        "folder": os.path.basename(os.path.dirname(path)),
        "relpath": os.path.relpath(path, REPO).replace("\\", "/"),
        "resolution_px": [w, h],
        "mode": mode,
        "bits": 16 if single16 else 8,
        "has_alpha": ("A" in mode) or (mode in ("RGBA", "LA")),
        "square": w == h,
        "category": category,
        "relief_stats": {
            "min": float(a.min()), "max": float(a.max()),
            "mean": float(a.mean()), "std": float(a.std()),
        },
    }
    row["conforms_to_r11"] = bool(single16 and not row["has_alpha"])

    # Landscape legality applies to TERRAIN ONLY. A stamp is composited
    # into a base heightmap and never becomes a landscape, so reporting
    # "needs crop" against one would be a false defect.
    if category == "TERRAIN":
        # UE landscape resolution is N+1 on BOTH axes -- require square, not
        # just a legal width (a legal-width non-square terrain is not legal).
        row["ue_legal"] = (w == h) and (w in UE_LEGAL)
        if row["ue_legal"]:
            row["ue_action"] = "none"
        else:
            smaller = [u for u in UE_LEGAL if u <= w]
            row["ue_action"] = ("crop to {0} (NEVER resample)".format(
                max(smaller)) if smaller else "below the smallest legal size")
    else:
        row["ue_legal"] = None
        row["ue_action"] = ("n/a — STAMP is composited into a base "
                            "heightmap before import")

    tag, src = tag_for(row["filename"])
    row["tag"], row["tag_source"] = tag, src

    # VISUAL SURVEY OVERLAY — a third, higher trust tier.
    #
    # `tag_source: "filename"` records what the VENDOR CALLED the file. It
    # is a hint, and hints are wrong: HM_Rugged_Rocks_14 is tagged
    # `outcrop` and is a CIRCULAR RADIAL DOME. That one was already
    # committed to a recipe as `east_ridge_outcrops` and would have put a
    # round bump on the east ridge. Five more were disqualified the same
    # way — two volcanic cones filed under `cliffs`, a desert butte, and
    # a MAN-MADE agricultural terrace filed under `terrace`.
    #
    # The filename is a derived record; the pixels are ground truth
    # (non-negotiable 15). So a stamp somebody has actually LOOKED at is
    # marked `tag_source: "visual"` and carries what it really depicts.
    # The merge happens here, at generation, so the trust tier survives
    # regeneration instead of being a hand edit that the next run erases.
    vis = _visual_survey().get(row["filename"])
    if vis:
        row["tag_source"] = "visual"
        row["visual_character"] = vis["character"]
        row["alpine"] = vis["alpine"]
        row["visual_note"] = vis.get("note", "")
    return row


_VISUAL_CACHE = {}


def _visual_survey():
    """Curated visual assessments, keyed by filename. Missing file is OK.

    Absence means NOBODY HAS LOOKED, which is a real and reportable state
    — not an error, and not a clearance.
    """
    if not _VISUAL_CACHE:
        path = os.path.join(REPO, "terrain", "stamp_visual_survey.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                _VISUAL_CACHE.update(json.load(fh).get("entries", {}))
        else:
            _VISUAL_CACHE["__none__"] = {}
    return {k: v for k, v in _VISUAL_CACHE.items() if k != "__none__"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print", dest="only_print", action="store_true")
    args = ap.parse_args(argv)

    grand = 0
    for root, category, source, licence, out in SOURCES:
        if not os.path.isdir(root):
            print("SKIP (absent): {0}".format(root))
            continue
        files = []
        for dirpath, _dirs, names in os.walk(root):
            for n in sorted(names):
                if n.lower().endswith(".png"):
                    files.append(os.path.join(dirpath, n))
        if not files:
            # NN13: a root that EXISTS but holds no PNGs is the normal fresh
            # checkout (the GB PNGs are gitignored; catalogue.json is committed).
            # Do NOT overwrite the committed catalogue with a count:0 one.
            print("=" * 68)
            print("{0}   0 PNGs found under {1}".format(category, root))
            print("  REFUSING to overwrite the committed catalogue with an "
                  "empty one. Restore the source PNGs to re-catalogue.")
            continue
        rows = [measure(p, category) for p in sorted(files)]
        grand += len(rows)

        by_hash = {}
        for r in rows:
            by_hash.setdefault(r["hash"], []).append(r["filename"])
        dupes = {h: v for h, v in by_hash.items() if len(v) > 1}

        print("=" * 68)
        print("{0}   {1} file(s)".format(category, len(rows)))
        print("  source : {0}".format(source))
        print("  licence: {0}".format(licence))
        print("  distinct by CONTENT HASH: {0}".format(len(by_hash)))
        if dupes:
            print("  DUPLICATE CONTENT under different names:")
            for h, v in list(dupes.items())[:5]:
                print("     {0}  {1}".format(h[:12], ", ".join(v)))
        else:
            print("  no duplicate content — every file is a distinct terrain")
        conf = sum(1 for r in rows if r["conforms_to_r11"])
        print("  R11-conforming (16-bit single channel, no alpha): "
              "{0}/{1}".format(conf, len(rows)))
        res = {}
        for r in rows:
            res[r["resolution_px"][0]] = res.get(r["resolution_px"][0], 0) + 1
        print("  resolutions: {0}".format(
            ", ".join("{0}px x{1}".format(k, v)
                      for k, v in sorted(res.items()))))
        if category == "TERRAIN":
            legal = sum(1 for r in rows if r["ue_legal"])
            print("  UE-legal N+1 without crop: {0}/{1}".format(
                legal, len(rows)))
        tags = {}
        for r in rows:
            tags[r["tag"]] = tags.get(r["tag"], 0) + 1
        print("  tags: {0}".format(", ".join(
            "{0} x{1}".format(k, v) for k, v in sorted(tags.items()))))

        if not args.only_print:
            payload = {
                "spec": "RECIPES.md R1 EXTERNAL HEIGHTMAP CATALOGUE SPEC",
                "category": category,
                "source": source,
                "licence": licence,
                "identity": "sha256 of file bytes; name/folder are metadata "
                            "only and are never used to match or dedupe",
                "cross_tier_note": "NO cross-tier 'same map' relationship is "
                                   "recorded: the resolution folders hold "
                                   "independently generated terrains",
                "count": len(rows),
                "maps": rows,
            }
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=1, sort_keys=True)
            print("  wrote {0}".format(os.path.relpath(out, REPO)))

    print("=" * 68)
    print("TOTAL catalogued: {0}".format(grand))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
