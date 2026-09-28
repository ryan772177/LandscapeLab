"""hlod_report_offdisk.py -- read the HLOD build record OFF DISK, with no editor.

    python scripts/hlod_report_offdisk.py --l2 --json <out.json>
    python scripts/hlod_report_offdisk.py --path <one .uasset>

⭐ WHY THIS EXISTS. Every HLOD actor package written by
`-BuildHLODs` / `-BuildSingleHLOD` embeds a plain-text block:

    ### HLOD_REPORT_BEGIN ###
      ... CommandLine, DateTimeUTC, GraphicsRHI
      ## Global Fields ##   MinVisibleDistance, LayerType, SourceActorsHash
      <per source component>  HLODTextureSizePolicy, HLODTextureSize,
                              ProjectHLODMaxTextureSize, HLODMeshSourceLODPolicy
    ### HLOD_REPORT_END ###

Those are the EXACT fields `ULandscapeHLODBuilder::ComputeHLODHash`
hashes (LandscapeHLODBuilder.cpp:44-127), recorded by the process that
actually did the build. That makes this a DIFFERENT INSTRUMENT from an
editor read-back, which is the whole point:

⛔ THE EDITOR IS THE INSTRUMENT UNDER SUSPICION. On 2026-09-14 an editor
read reported 32x32 landscape HLOD textures for a cell whose build inputs
predict 1024, and a later read of the same cell reported 1024. A
read-back that disagrees with itself cannot adjudicate itself
(non-negotiable 8). This reads the bytes the commandlet wrote.

⛔ AND `MinVisibleDistance` IS IN HERE. Three prior documents derived
texture sizes from a `MinVisibleDistance` of 76,800 cm taken from the
HLOD layer's `loading_range`. The value the builder actually used is in
the package. Read it; do not derive it.

READ-ONLY BY CONSTRUCTION. Every file is opened 'rb'. Nothing is written
except the optional --json output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uasset_lite  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BEGIN = b"### HLOD_REPORT_BEGIN ###"
END = b"### HLOD_REPORT_END ###"

# Read this much of the head of each package before giving up / escalating.
HEAD_BYTES = 512 * 1024


def gitignored_hlod_packages():
    """The 2,267 HLOD actor packages, enumerated by scripts/hlod_gitignore.py.

    Identification is by that script's content signature, not by path --
    see its docstring. We reuse its verdict rather than re-deriving one.
    """
    gi = os.path.join(REPO_ROOT, ".gitignore")
    out = []
    with open(gi, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("/LandscapeLab/Content/__ExternalActors__/") and line.endswith(".uasset"):
                out.append(os.path.join(REPO_ROOT, line.lstrip("/").replace("/", os.sep)))
    return out


def extract_block(path):
    """Return the report text, or None. Escalates to a full read if needed."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(HEAD_BYTES)
            i = head.find(BEGIN)
            if i < 0:
                return None
            j = head.find(END, i)
            if j < 0:
                fh.seek(0)
                whole = fh.read()
                i = whole.find(BEGIN)
                j = whole.find(END, i)
                if j < 0:
                    return None
                blob = whole[i:j + len(END)]
            else:
                blob = head[i:j + len(END)]
    except OSError:
        return None
    return blob.decode("utf-8", errors="replace")


FIELD = re.compile(r"^\s*\*\s*([A-Za-z0-9_]+):\s*(.*?)\s*$", re.M)
LABEL = re.compile(r"^\s*Label:(.*?)\s*$", re.M)
GUID = re.compile(r"^\s*Guid:([0-9A-Fa-f]{32})\s*$", re.M)


def parse(text, path):
    rec = {
        "path": os.path.relpath(path, REPO_ROOT).replace(os.sep, "/"),
        "bytes": os.path.getsize(path),
    }
    m = LABEL.search(text)
    rec["label"] = m.group(1) if m else None
    # The HLOD actor GUID, which is what a BuildManifest section keys on
    # (`+HLODActorGuid`, WorldPartitionHLODsBuilder.cpp:68, :1062-1095).
    m = GUID.search(text)
    rec["guid"] = m.group(1).upper() if m else None

    # Global / per-component fields. Later components repeat the landscape
    # fields; we collect the DISTINCT values so a disagreement is visible
    # rather than silently last-wins.
    collected = {}
    for m in FIELD.finditer(text):
        k, v = m.group(1), m.group(2)
        collected.setdefault(k, [])
        if v not in collected[k]:
            collected[k].append(v)

    for key in ("MinVisibleDistance", "LayerType", "SourceActorsHash",
                "HLODTextureSizePolicy", "HLODTextureSize",
                "ProjectHLODMaxTextureSize", "HLODMeshSourceLODPolicy",
                "NaniteEnabled", "NaniteSkirtEnabled"):
        vals = collected.get(key)
        if vals is None:
            rec[key] = None
        elif len(vals) == 1:
            rec[key] = vals[0]
        else:
            rec[key] = vals  # a list means the components DISAGREE -- report it

    for key, pat in (("CommandLine", r"^\s*\*\s*CommandLine:\s*(.*?)\s*$"),
                     ("DateTimeUTC", r"^\s*\*\s*DateTimeUTC:\s*(.*?)\s*$"),
                     ("GraphicsRHI", r"^\s*\*\s*GraphicsRHI:\s*(.*?)\s*$"),
                     ("EngineMode", r"^\s*\*\s*EngineMode:\s*(.*?)\s*$")):
        m = re.search(pat, text, re.M)
        rec[key] = m.group(1) if m else None

    rec["n_landscape_components"] = text.count("LandscapeComponent ")
    rec["has_landscape_fields"] = "HLODTextureSizePolicy" in text
    return rec


def add_texture_dims(rec, path):
    """The BAKED texture dimensions, read from the package's own bytes.

    This is the measurement the editor read-back disagreed with itself about
    on 2026-09-14; see uasset_lite's docstring for why it exists.
    """
    try:
        dims, _summary, _names = uasset_lite.texture_source_dims(path)
    except Exception as exc:                      # noqa: BLE001 - report, never mask
        rec["tex_dims"] = None
        rec["tex_error"] = f"{type(exc).__name__}: {exc}"
        return
    rec["tex_dims"] = [list(t) for t in dims]
    rec["tex_n"] = len(dims)
    rec["tex_distinct"] = sorted({f"{x}x{y}" for x, y in dims})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--path", help="a single .uasset to read")
    ap.add_argument("--l2", action="store_true",
                    help="only cells whose label contains _L2_ (landscape cells)")
    ap.add_argument("--landscape-only", action="store_true",
                    help="only packages carrying landscape HLOD hash fields")
    ap.add_argument("--texdims", action="store_true",
                    help="also read the baked texture dimensions off disk")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", help="write the full records here")
    a = ap.parse_args()

    paths = [os.path.abspath(a.path)] if a.path else gitignored_hlod_packages()

    records, no_block, missing = [], 0, 0
    for p in paths:
        if not os.path.exists(p):
            missing += 1
            continue
        text = extract_block(p)
        if text is None:
            no_block += 1
            continue
        rec = parse(text, p)
        if a.l2 and (not rec["label"] or "_L2_" not in rec["label"]):
            continue
        if a.landscape_only and not rec["has_landscape_fields"]:
            continue
        if a.texdims:
            add_texture_dims(rec, p)
        records.append(rec)
        if a.limit and len(records) >= a.limit:
            break

    # ⛔ Rule 13: report the sample count beside the verdict, and refuse at zero.
    print(f"packages considered : {len(paths)}")
    print(f"  missing on disk   : {missing}")
    print(f"  no report block   : {no_block}   (never built, or a stub)")
    print(f"  PARSED            : {len(records)}")
    if not records:
        print("\n⛔ REFUSING: 0 records parsed. This instrument found nothing to "
              "compare, which is not agreement.")
        return 4

    def tally(key):
        t = {}
        for r in records:
            v = r.get(key)
            v = json.dumps(v) if isinstance(v, list) else str(v)
            t[v] = t.get(v, 0) + 1
        return t

    for key in ("MinVisibleDistance", "HLODTextureSizePolicy", "HLODTextureSize",
                "ProjectHLODMaxTextureSize", "HLODMeshSourceLODPolicy", "LayerType"):
        print(f"\n{key}:")
        for v, n in sorted(tally(key).items(), key=lambda kv: -kv[1]):
            print(f"   {v:<24} x{n}")

    sizes = sorted(r["bytes"] for r in records)
    print(f"\npackage bytes: min {sizes[0]:,}  median {sizes[len(sizes)//2]:,}  max {sizes[-1]:,}")

    if a.texdims:
        ok = [r for r in records if r.get("tex_dims") is not None]
        bad = [r for r in records if r.get("tex_dims") is None]
        print(f"\nBAKED TEXTURE DIMENSIONS   read {len(ok)} / {len(records)} packages")
        if bad:
            print(f"  ⛔ {len(bad)} packages failed to parse -- NOT counted as agreement")
            for r in bad[:5]:
                print(f"     {r['label']}: {r.get('tex_error')}")
        if not ok:
            print("  ⛔ REFUSING: 0 packages parsed for dimensions.")
            return 4
        t = {}
        for r in ok:
            key = ",".join(r["tex_distinct"]) + f"  (n_tex={r['tex_n']})"
            t[key] = t.get(key, 0) + 1
        for v, n in sorted(t.items(), key=lambda kv: -kv[1]):
            print(f"   {v:<40} x{n}")

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"n": len(records), "records": records}, fh, indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
