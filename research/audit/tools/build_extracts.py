"""build_extracts.py — the two Pass 3/4 evidence extracts.

READ-ONLY. Writes only into research/audit/inputs/.

  sidecars.zip       every JSON sidecar under _verify/. No images, no
                     .npy. The sidecar is the MEASUREMENT; the image is
                     the thing measured, and the desk is auditing the
                     numbers, not re-reading the pixels.
  history_diffs.txt  produced by the caller (git log -p), not here.

⛔ WHY A TOOL AND NOT A ONE-LINER. The set that goes in has to be
re-derivable six weeks from now when a number in it is disputed. A zip
cut by hand has no record of what it excluded or why, which is the
failure the audit package exists to stop repeating.
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
SRC = os.path.join(REPO, "_verify")
OUT = os.path.join(REPO, "research", "audit", "inputs")

kept, skipped = [], {}

for root, dirs, files in os.walk(SRC):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
    for f in files:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, REPO).replace("\\", "/")
        ext = os.path.splitext(f)[1].lower()
        if ext != ".json":
            skipped[ext or "(none)"] = skipped.get(ext or "(none)", 0) + 1
            continue
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        kept.append((rel, sz))

kept.sort()
if not os.path.isdir(OUT):
    os.makedirs(OUT)
zp = os.path.join(OUT, "sidecars.zip")
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel, _s in kept:
        z.write(os.path.join(REPO, rel), rel)
    # The manifest travels INSIDE the zip. A separate file gets
    # separated; a manifest that can be read without the zip it
    # describes is a manifest that will one day describe a different zip.
    z.writestr("_MANIFEST.json", json.dumps(
        {"_what": "every JSON sidecar under _verify/",
         "excluded": "images (.png/.jpg/.exr), arrays (.npy), everything "
                     "that is not .json -- the desk is auditing the "
                     "measurements, not re-measuring the pixels",
         "n_files": len(kept),
         "uncompressed_bytes": sum(s for _r, s in kept),
         "excluded_by_extension": skipped,
         "files": [{"path": r, "bytes": s} for r, s in kept]},
        indent=1))

print("sidecars: %d files, %.2f MB uncompressed"
      % (len(kept), sum(s for _r, s in kept) / 1e6))
print("excluded by extension: %s"
      % ", ".join("%s %d" % kv for kv in sorted(skipped.items(),
                                                key=lambda kv: -kv[1])))
print("%s  %d bytes (%.2f MB)"
      % (zp, os.path.getsize(zp), os.path.getsize(zp) / 1e6))
