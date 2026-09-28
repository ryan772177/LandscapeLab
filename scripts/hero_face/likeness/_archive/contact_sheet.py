"""contact_sheet.py — the hair catalogue as one page, with its verdicts on it.

Reads a catalogue run's `index.json` and tiles every rendered hair into a grid
with the ruled reference in the first cell, each tile captioned with the hair
name, its gate verdict and its crown fraction.

WHY THE VERDICT IS BURNED INTO THE TILE. A contact sheet whose numbers live in
a chat message stops being evidence the moment it scrolls, and this one has to
survive as party-development reference material long after the session that
made it. A tile that says SCALP-BALD is telling the reader not to trust what
they are looking at — which matters, because a failed groom binding renders a
large, confident, WRONG picture.

Exit codes:
    0  sheet written
    2  no index, or no frames in it
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
REGISTRY = os.path.join(REPO_ROOT, "characters", "registry.json")

CELL = 420
CAP = 34
CROP = (430, 60, 1620, 1420)      # head + shoulders from a 2048 square frame


def _font(sz):
    try:
        return ImageFont.truetype("arial.ttf", sz)
    except Exception:
        return ImageFont.load_default()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--character", default="AlpineHero")
    ap.add_argument("--cols", type=int, default=4)
    args = ap.parse_args(argv)

    ip = os.path.join(args.run_dir, "index.json")
    if not os.path.isfile(ip):
        print("REFUSE: no index at", ip)
        return 2
    with open(ip, "r", encoding="utf-8") as fh:
        index = json.load(fh)

    rows = [r for r in index.values() if r.get("frame")
            and os.path.isfile(r["frame"])]
    missing = [k for k, r in index.items()
               if not (r.get("frame") and os.path.isfile(r["frame"]))]
    if not rows:
        print("REFUSE: the index has no frames on disk.")
        return 2
    rows.sort(key=lambda r: r["hair"])

    tiles = []
    # The reference goes first, so every judgement is made against it rather
    # than against the neighbouring tile.
    try:
        with open(REGISTRY, "r", encoding="utf-8") as fh:
            reg = json.load(fh)
        ref_rel = reg["characters"][args.character]["reference"]["appearance"]["path"]
        ref = Image.open(os.path.join(REPO_ROOT, ref_rel)).convert("RGB")
        w, h = ref.size
        ref = ref.crop((int(w * 0.24), 0, int(w * 0.74), h))
        tiles.append((ref, "THE REFERENCE", ""))
    except Exception as exc:
        print("NOTE: reference not tiled (%s)" % exc)

    for r in rows:
        im = Image.open(r["frame"]).convert("RGB")
        # CROP IS TUNED FOR THE WIDE FRAMING AND MUST NOT BE APPLIED BLIND.
        # (430, 60, 1620, 1420) takes head-and-shoulders out of a frame shot
        # at dist 110. Applied to a dist-60 frame it crops INTO the forehead,
        # and the first close sheet came out a catalogue of hairlines rather
        # than of hairstyles. Same class of defect as the hardcoded distance
        # in catalogue_run, one layer up: a constant that silently assumes a
        # framing nobody told it about. Rows now carry their framing, so ask.
        fr = r.get("framing") or {}
        try:
            dist = float(fr.get("dist", 110))
        except (TypeError, ValueError):
            dist = 110.0
        if im.size == (2048, 2048) and dist >= 90:
            im = im.crop(CROP)
        cap = r["hair"].replace("Hair_", "")
        sub = "%s  crown %.0f%%  %sk px" % (
            r.get("verdict", "?"), 100.0 * (r.get("crown_frac") or 0.0),
            round((r.get("changed_px") or 0) / 1000.0))
        tiles.append((im, cap, sub))

    cols = max(1, args.cols)
    rows_n = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * CELL, rows_n * (CELL + CAP)), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    f1, f2 = _font(17), _font(14)

    for i, (im, cap, sub) in enumerate(tiles):
        cx, cy = (i % cols) * CELL, (i // cols) * (CELL + CAP)
        im = im.resize((CELL, CELL), Image.LANCZOS)
        sheet.paste(im, (cx, cy + CAP))
        d.text((cx + 6, cy + 4), cap, fill=(240, 240, 240), font=f1)
        colour = (150, 255, 150)
        if "SCALP-BALD" in sub or "ABSENT" in sub:
            colour = (255, 150, 120)
        d.text((cx + 6, cy + 20), sub, fill=colour, font=f2)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    sheet.save(args.out)
    # COUNT THE HAIRS, NOT THE TILES. The reference is tile 0, so a bare tile
    # count reads one HIGHER than the number of hairs and invites exactly the
    # arithmetic check it fails: 37 tiles + 2 not tiled against 38 indexed.
    # Report the three numbers that have to add up, and say which is which.
    print("wrote %s  %s" % (args.out, sheet.size))
    print("  %d hair tiles + %d reference = %d tiles;  %d indexed = %d tiled "
          "+ %d not tiled"
          % (len(rows), len(tiles) - len(rows), len(tiles),
             len(index), len(rows), len(missing)))
    if missing:
        # NO SILENT TRUNCATION. A sheet that quietly drops rows reads as
        # "this is all of them".
        print("NOT TILED (no frame on disk): %s" % ", ".join(sorted(missing)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
