"""Build the SHIPPABLE stamp catalogue for the forge distribution.

The dev pipeline composites from `terrain/stampit_catalogue.json`, whose 52
maps are Fab-licensed "UE projects only" and CANNOT ship in a standalone
tool. This module builds `recipes/forge_stamps_catalogue.json` from content
the forge may distribute:

  1. The three operator-owned eroded stamp seeds (Gemini outputs run through
     the project's own hydraulic erosion, _verify/20260831_.../
     erode_stamp_seeds.py). ADOPTED here: copied to stable names under
     terrain/forge_stamps/ and hash-proven against the source at adoption
     time (CLAUDE.md non-negotiable 20).
  2. A CURATED subset of the CC0 external heightmaps, re-categorised
     TERRAIN -> STAMP. Re-categorisation is a visual judgement, not a
     measurement: each entry below carries the character read off its
     hillshade (contact sheet, 2026-09-02), following the
     stamp_visual_survey precedent. Entries NOT listed were looked at and
     DISQUALIFIED (fragmented / noise-like fields that do not composite as
     a coherent landform).

LICENCE GATE: refuses to write the catalogue if any output hash appears in
stampit_catalogue.json. Identity is the content hash — the same rule the
compositor enforces — so a Fab map cannot be smuggled in under a new name.

Usage: python -m forge_tool.build_stamp_catalogue [--print]
Exit:  0 written/ok, 2 refusal.
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
SEED_SRC_DIR = os.path.join(REPO, "_verify", "20260831_spike_photo2landscape")
ADOPT_DIR = os.path.join(REPO, "terrain", "forge_stamps")
CC0_CATALOGUE = os.path.join(
    REPO, "terrain", "external_heightmaps", "catalogue.json")
STAMPIT_CATALOGUE = os.path.join(REPO, "terrain", "stampit_catalogue.json")
OUT = os.path.join(REPO, "recipes", "forge_stamps_catalogue.json")

# Operator-owned seeds: source filename -> (stable name, tag, character).
# spire_peaks is DELIBERATELY ABSENT: the recorded seed survey
# (_verify/20260831_spike_photo2landscape/SPIKE_REPORT.md addendum)
# REJECTED it — the baked light rays and the mountain skirt share a luma
# band and no clamp separates them. A catalogue may not overrule a
# recorded measurement.
SEEDS = {
    "stamp_terraced_cliffs_eroded.png": (
        "forge_terraced_cliffs.png", "terraces",
        "terraced pit; MIN-carve use (flat sites, quarry-like walls). "
        "Survey: usable-soft — erosion pockmarks, not channels"),
    "stamp_river_basin_eroded.png": (
        "forge_river_basin.png", "basin",
        "meander channel with rim; MIN-carve valley / lake basin. "
        "Survey: usable — channel+banks+rim survive erosion"),
}

# CC0 re-categorisation allowlist, keyed by FILENAME within the 1K folder
# (matched then verified by hash from the CC0 catalogue itself; the
# filename is a lookup convenience, the hash is the identity).
CC0_STAMPS = {
    "Heightmap_01_Mountain.png": (
        "mountain", "dense rugged peak field; ADD massif"),
    "Heightmap_02_Hills.png": (
        "hills", "rolling hill field; ADD low-relief roll"),
    "Heightmap_03_Meadows.png": (
        "ridges", "broad valleys between bold ridges; ADD midland"),
    "Heightmap_04_Plains.png": (
        "rise", "one broad smooth massif; ADD single large rise"),
    "Heightmap_05_Dunes.png": (
        "dunes", "repetitive rounded dune bumps; ADD foothill texture "
        "(NOTE: repetitive — keep opacity/amplitude low)"),
    "Heightmap_06_Canyon.png": (
        "craters", "ringed circular pits; MIN-carve terracing "
        "(NOTE: odd crater character — preview before trusting)"),
    "Heightmap_08_Island.png": (
        "island_peak", "radial island cone, crater-topped; ADD single peak"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_full_range(src_path, dst_path):
    """TERRAIN -> STAMP conversion is a RANGE conversion, not a relabel.
    The compositor's spec (RECIPES R1): a stamp is a FULL 0..65535 field —
    amplitude_m scales that whole range. The CC0 maps span a fraction of
    it (Heightmap_01_Mountain: 146..25241, 38%), which delivered a 520 m
    peak from amplitude 1500 and hit the brief-loop cap (measured
    2026-09-02, duskhighland run). Min->0, max->65535, 16-bit out."""
    arr = np.asarray(Image.open(src_path)).astype(np.float64)
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1.0:
        raise ValueError("flat field cannot be a stamp: %s" % src_path)
    out = ((arr - lo) / (hi - lo) * 65535.0).round().astype(np.uint16)
    Image.fromarray(out).save(dst_path)


def synth_flat_pad(dst_path, size=1009, flat_frac=0.38):
    """Synthetic MIN-carve stamp: flat centre (value 0) out to flat_frac
    of the radius, smooth quintic rise to 65535 at the edge. Exists
    because every organic stamp carries texture, and texture IS slope —
    a small flat_site acceptance (village pad) cannot converge on a
    terraced or eroded carve (measured: village_site slope 17->19 deg
    across 6 planing iterations). Deterministic pure function; operator-
    owned by construction."""
    ax = np.linspace(-1.0, 1.0, size)
    r = np.hypot(*np.meshgrid(ax, ax))
    t = np.clip((r - flat_frac) / (1.0 - flat_frac), 0.0, 1.0)
    field = t * t * t * (t * (t * 6.0 - 15.0) + 10.0)  # quintic smooth
    out = (field * 65535.0).round().astype(np.uint16)
    Image.fromarray(out).save(dst_path)


def synth_mesa(dst_path, size=1009, flat_frac=0.45):
    """Synthetic ADD stamp: flat TOP (65535) out to flat_frac of the
    radius, quintic fall to 0 at the rim — the inverse of flat_pad.
    Exists because a MIN carve cannot rule a site that straddles a
    flank: ground already below the anchor stays put (measured
    2026-09-02: village box elev 28..124 m, slope stuck at 20 deg
    through six planing iterations). A mesa RAISES the flat site
    instead, which works on any underlying slope."""
    ax = np.linspace(-1.0, 1.0, size)
    r = np.hypot(*np.meshgrid(ax, ax))
    t = np.clip((r - flat_frac) / (1.0 - flat_frac), 0.0, 1.0)
    field = 1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    out = (field * 65535.0).round().astype(np.uint16)
    Image.fromarray(out).save(dst_path)


def entry_for(path, relpath, tag, character, licence_note):
    im = Image.open(path)
    arr = np.asarray(im).astype(np.float64)
    bits = 16 if im.mode in ("I;16", "I;16B", "I") else 8
    return {
        "bits": bits,
        "category": "STAMP",
        "character": character,
        "conforms_to_r11": bits == 16 and im.size[0] == im.size[1],
        "filename": os.path.basename(path),
        "folder": os.path.basename(os.path.dirname(path)),
        "has_alpha": "A" in im.getbands(),
        "hash": sha256(path),
        "licence": licence_note,
        "mode": im.mode,
        "relief_stats": {
            "max": float(arr.max()), "mean": float(arr.mean()),
            "min": float(arr.min()), "std": float(arr.std()),
        },
        "relpath": relpath.replace("\\", "/"),
        "resolution_px": list(im.size),
        "square": im.size[0] == im.size[1],
        "tag": tag,
        "tag_source": "visual",
        "ue_action": "n/a — STAMP is composited into a base heightmap "
                     "before import",
        "ue_legal": None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="print_only",
                    help="summarise; write nothing")
    a = ap.parse_args(argv)

    # Licence identities load FIRST so nothing Fab-derived is even copied
    # (audit F3: gate before the side effect, not after).
    stampit = json.load(open(STAMPIT_CATALOGUE, encoding="utf-8"))
    fab_hashes = {m["hash"] for m in stampit["maps"]}

    # Every forge stamp is ADOPTED as a NORMALIZED full-range copy under
    # terrain/forge_stamps/ — the compositor treats a stamp as a full
    # 0..65535 field, so normalization is part of the category, not an
    # optimisation. derived_from records the source hash.
    maps = []
    os.makedirs(ADOPT_DIR, exist_ok=True)

    def adopt_normalized(src, stable, tag, character, licence, src_hash):
        dst = os.path.join(ADOPT_DIR, stable)
        if not a.print_only:
            normalize_full_range(src, dst)
        rel = os.path.relpath(dst if os.path.isfile(dst) else src, REPO)
        e = entry_for(dst if os.path.isfile(dst) else src, rel, tag,
                      character, licence)
        e["derived_from"] = src_hash
        maps.append(e)

    # -- operator seeds ----------------------------------------------
    for src_name, (stable, tag, character) in sorted(SEEDS.items()):
        src = os.path.join(SEED_SRC_DIR, src_name)
        if not os.path.isfile(src):
            print("REFUSE: seed source missing: %s" % src)
            return 2
        src_hash = sha256(src)
        if src_hash in fab_hashes:
            print("REFUSE: seed %s hash-matches Fab-licensed content"
                  % src_name)
            return 2
        adopt_normalized(src, stable, tag, character,
                         "operator-owned (Gemini output, eroded "
                         "in-project)", src_hash)

    # -- curated CC0 re-categorisation (normalized) -------------------
    cc0 = json.load(open(CC0_CATALOGUE, encoding="utf-8"))
    by_name = {m["filename"]: m for m in cc0["maps"]
               if m.get("folder") == "1K"}
    for fname, (tag, character) in sorted(CC0_STAMPS.items()):
        if fname not in by_name:
            print("REFUSE: allowlisted CC0 map %r not in the CC0 catalogue "
                  "1K folder" % fname)
            return 2
        src_entry = by_name[fname]
        path = os.path.join(REPO, src_entry["relpath"])
        live = sha256(path)
        if live != src_entry["hash"]:
            print("REFUSE: %s hashes %s on disk but the CC0 catalogue "
                  "records %s" % (fname, live[:12], src_entry["hash"][:12]))
            return 2
        adopt_normalized(path, "forge_cc0_%s.png" % tag, tag, character,
                         "CC0 (normalized copy)", live)

    # -- synthetic flat pad -------------------------------------------
    pad = os.path.join(ADOPT_DIR, "forge_flat_pad.png")
    if not a.print_only:
        synth_flat_pad(pad)
    if os.path.isfile(pad):
        e = entry_for(pad, os.path.relpath(pad, REPO), "flat_pad",
                      "synthetic radial pad: flat centre to 38% radius, "
                      "quintic rise to rim; MIN-carve for small flat "
                      "sites (village pads)", "generated in-tool")
        e["derived_from"] = "synth_flat_pad(size=1009, flat_frac=0.38)"
        maps.append(e)

    mesa = os.path.join(ADOPT_DIR, "forge_mesa.png")
    if not a.print_only:
        synth_mesa(mesa)
    if os.path.isfile(mesa):
        e = entry_for(mesa, os.path.relpath(mesa, REPO), "mesa",
                      "synthetic mesa: flat top to 45% radius, quintic "
                      "fall to rim; ADD for flat sites on sloped ground "
                      "(a MIN carve cannot rule ground below its anchor)",
                      "generated in-tool")
        e["derived_from"] = "synth_mesa(size=1009, flat_frac=0.45)"
        maps.append(e)

    # -- licence gate over the OUTPUT entries ------------------------
    leaked = [m["filename"] for m in maps if m["hash"] in fab_hashes]
    if leaked:
        print("REFUSE: Fab-licensed content in the forge catalogue "
              "(hash identity): %s" % leaked)
        return 2

    cat = {
        "category": "STAMP",
        "count": len(maps),
        "identity": "sha256 of file bytes; names are metadata "
                    "(RECIPES.md R1 catalogue spec)",
        "licence": "mixed per-map: CC0, or operator-owned Gemini outputs. "
                   "NO Fab content — enforced by hash against "
                   "stampit_catalogue.json at build time.",
        "source": "forge_tool/build_stamp_catalogue.py (curation notes in "
                  "module docstring; hillshade contact sheet 2026-09-02)",
        "spec": "same entry schema as stampit_catalogue.json; "
                "composite_stamps.py consumes it unchanged",
        "maps": maps,
    }

    if a.print_only:
        for m in maps:
            print("%-28s %-12s %s" % (m["filename"], m["tag"],
                                      m["licence"][:40]))
        print("%d maps, licence gate PASSED" % len(maps))
        return 0

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1, sort_keys=False)
        f.write("\n")
    print("wrote %s  (%d maps, licence gate PASSED)"
          % (os.path.relpath(OUT, REPO), len(maps)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
