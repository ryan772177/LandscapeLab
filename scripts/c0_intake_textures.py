"""C0 step 1 — take in the operator's generated texture set, hash-proven.

COPIES from Downloads into refs/textures_v1/ under clean ROLE names. Never
moves; nothing writes back to Downloads.

THE FORMAT IS READ FROM THE BYTES, NOT THE EXTENSION. The staged files carry
doubled extensions (`wall_planks_a.png.jpg`, `plaster_wall.jpeg.jpg`), which is
a claim made twice and verified never. This project has already been bitten by
believing a name: `.uasset` material_slots that disagreed with the loaded mesh,
and a "16-bit" source that was 8-bit. Magic bytes decide the FORMAT here (this
step sniffs format only; it does NOT inspect bit depth or channels).

Usage: python scripts/c0_intake_textures.py [--go]
"""
import argparse
import hashlib
import io
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.expanduser("~"), "Downloads", "textures_v1")
DEST = os.path.join(REPO, "refs", "textures_v1")

# role -> the staged filename. Roles are the pipeline's key; the operator's
# filenames are an input and are recorded, not adopted.
ROLES = {
    "wall_planks_a": "wall_planks_a.png.jpg",
    "wall_planks_b": "wall_planks_b.jpeg.jpg",
    "beam_wood": "beam_wood.jpeg.jpg",
    "plaster_wall": "plaster_wall.jpeg.jpg",
    "roof_tiles": "roof_tiles.jpeg.jpg",
}

MAGIC = {b"\xff\xd8\xff": "jpeg", b"\x89PNG\r\n\x1a\n": "png",
         b"BM": "bmp", b"II*\x00": "tiff", b"MM\x00*": "tiff"}


def sniff(path):
    head = io.open(path, "rb").read(16)
    for sig, name in MAGIC.items():
        if head.startswith(sig):
            return name
    return "UNKNOWN"


def sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(SRC):
        print("REFUSING: %s does not exist." % SRC)
        return 2

    rows, missing = [], []
    for role, fn in sorted(ROLES.items()):
        s = os.path.join(SRC, fn)
        if not os.path.exists(s):
            missing.append((role, fn))
            continue
        fmt = sniff(s)
        try:
            from PIL import Image
            with Image.open(s) as im:
                size, mode = im.size, im.mode
        except Exception as e:
            size, mode = None, "UNREADABLE: %s" % e
        rows.append({"role": role, "src_name": fn, "format": fmt,
                     "size": size, "mode": mode, "bytes": os.path.getsize(s),
                     "sha256": sha256(s)})

    print("C0 texture intake  (%s)" % ("GO" if a.go else "DRY RUN"))
    print("  source %s" % SRC)
    print()
    print("  %-14s %-24s %-6s %-11s %-6s %9s" %
          ("role", "staged name", "fmt", "size", "mode", "bytes"))
    for r in rows:
        print("  %-14s %-24s %-6s %-11s %-6s %9d"
              % (r["role"], r["src_name"], r["format"],
                 "%dx%d" % r["size"] if r["size"] else "?", r["mode"],
                 r["bytes"]))
    if missing:
        print()
        for role, fn in missing:
            print("  MISSING  %-14s expected %s" % (role, fn))
        print("REFUSING: %d of %d roles are not staged." % (len(missing), len(ROLES)))
        return 3

    bad = [r for r in rows if r["format"] == "UNKNOWN"]
    if bad:
        print()
        print("REFUSING: %d file(s) are not an image format this recognises. "
              "The extension is a claim; the bytes are the fact." % len(bad))
        return 4

    # FAIL CLOSED on a file the tool could not OPEN: it was recorded
    # size=None / mode="UNREADABLE:..." but still flowed into the copy and the
    # "every one hash-verified" count. A file we never decoded is not intaken.
    unreadable = [r for r in rows if r["size"] is None]
    if unreadable:
        print()
        print("REFUSING: %d file(s) could not be OPENED as an image (%s). "
              "'hash-verified' must not cover bytes this tool never decoded."
              % (len(unreadable), ", ".join(r["role"] for r in unreadable)))
        return 4

    # Only jpeg/png can be STAGED (the ext map below). MAGIC also recognises
    # bmp/tiff, so those pass the UNKNOWN gate above but would silently land as
    # `<role>.bin`. Refuse them by name rather than mis-stage them.
    STAGE_EXT = {"jpeg": ".jpg", "png": ".png"}
    unstageable = [r for r in rows if r["format"] not in STAGE_EXT]
    if unstageable:
        print()
        print("REFUSING: %d file(s) are a recognised format this intake does "
              "NOT stage (only jpeg/png); they would land as .bin: %s"
              % (len(unstageable),
                 ", ".join("%s=%s" % (r["role"], r["format"])
                           for r in unstageable)))
        return 4

    if not a.go:
        print()
        print("DRY RUN — nothing copied. Re-run with --go.")
        return 0

    os.makedirs(DEST, exist_ok=True)
    for r in rows:
        ext = STAGE_EXT[r["format"]]   # guaranteed present: unstageable refused above
        d = os.path.join(DEST, r["role"] + ext)
        shutil.copy2(os.path.join(SRC, r["src_name"]), d)
        if sha256(d) != r["sha256"]:
            print("  !! HASH MISMATCH after copy: %s" % r["role"])
            return 5
        r["dest"] = os.path.relpath(d, REPO).replace(os.sep, "/")

    import json
    man = os.path.join(REPO, "Free", "_measured", "c0_textures_v1.json")
    io.open(man, "w", encoding="utf-8").write(json.dumps({
        "_what": ("SHA-256 manifest of the operator's generated texture set, "
                  "copied into refs/textures_v1/ under ROLE names. The staged "
                  "filenames carried doubled extensions; format was read from "
                  "MAGIC BYTES, not from the name."),
        "_source": SRC,
        "_adopted": "2026-08-30",
        "files": rows,
    }, indent=2) + "\n")
    print()
    print("  copied %d, every one hash-verified at both ends" % len(rows))
    print("  manifest %s" % os.path.relpath(man, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
