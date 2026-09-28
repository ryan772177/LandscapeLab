"""palette_evidence.py — the instrument behind the alpine palette.

OFFLINE. Reads only `Free/_measured/fab_registry_*.json`, touches no
editor, imports no `unreal`, writes nothing unless asked. It answers ONE
question with a number instead of an adjective:

    is this asset the same QUALITY TIER as the rest of the region?

WHY A NUMBER IS REQUIRED HERE
-----------------------------
The campaign bar is "photoreal coherence... one quality tier, nothing
admitted that reads as filler". Left as an adjective that is unfalsifiable
and I would be curating by vibe. It is measurable: photogrammetry rock
carries one to two ORDERS OF MAGNITUDE more triangles per unit of surface
than hand-modelled low-poly rock, and the asset registry already reports
both `Triangles` and `ApproxSize` without loading anything.

THE METRIC, and its honest limits
---------------------------------
    bbox_area_m2 = 2 * (x*y + y*z + z*x)        from `ApproxSize` (cm)
    tri_density  = Triangles / bbox_area_m2     triangles per m^2

`ApproxSize` is the AXIS-ALIGNED BOUNDING BOX, not the surface. For a
compact blob (a boulder) the box area is a decent proxy for real surface
area and the ratio is meaningful. It is NOT meaningful for:

  - PLANAR assets (leaf cards, grass patches, scree slabs): the box is
    nearly flat, so its area collapses toward 2*x*y and the density is
    inflated. Reported, and flagged `planar` when min(dim)/max(dim)
    < PLANAR_RATIO, but never used to admit or reject.
  - SPANNING assets (trees): most of the box is air between branches.
    The registry carries no shape class, so this script CANNOT auto-flag
    these — a boxy tree AABB is classified `blob` and would contaminate a
    blob median. Keep trees out of a comparison with --contains/--name.

So the metric DISCRIMINATES ONLY WITHIN A SHAPE CLASS, and only PLANAR
assets are auto-excluded (spanning trees are NOT). Comparing a boulder
against a boulder is valid; comparing a boulder against a fern is not.
The CALLER, not this script, must keep cross-class assets apart with the
filters — which is why the output is called EVIDENCE and the palette is a
separate, curated file.

WHAT THIS SCRIPT DOES NOT KNOW
------------------------------
  - Nanite state WHERE THE TAG IS ABSENT. Of the 199 StaticMeshes across
    the three default packs (879 assets total), DragonCave's 115 carry
    `NaniteEnabled` and this script reports it per row (see --json-out);
    KiteDemo (47) and Atlantis_Ruins (37) do not. An absent tag means
    UNKNOWN, not OFF — ask the editor directly for those.
  - LOD count where absent. `LODs`/`MinLOD` are present in DragonCave (115
    meshes) and Atlantis_Ruins (37) and absent in KiteDemo; this script
    does not yet surface them in the evidence table.
  - Anything about how the asset LOOKS. No render has been made of any
    of these assets. Triangle density is a proxy for detail, not for
    colour, biome, or whether the thing reads as alpine.

Exit codes:
  0  evidence computed
  2  a registry file is missing or unreadable
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEASURED = os.path.join(REPO, "Free", "_measured")

# min(dim)/max(dim) below this is a slab/card, not a blob.
PLANAR_RATIO = 0.20


def load_registry(pack):
    path = os.path.join(MEASURED, "fab_registry_{0}.json".format(pack))
    if not os.path.isfile(path):
        raise IOError("no registry for {0}: {1}".format(pack, path))
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def dims_m(rec):
    """(x, y, z) in METRES from the registry's `ApproxSize` cm string.

    Returns None when the tag is absent or unparseable. A missing tag is
    reported as missing; it is never defaulted to a number, because a
    defaulted size would flow into a density and become a fabricated
    quality verdict (CLAUDE.md non-negotiable 6).
    """
    raw = rec.get("ApproxSize")
    if not raw:
        return None
    try:
        parts = [float(v) for v in str(raw).split("x")]
    except ValueError:
        return None
    if len(parts) != 3 or min(parts) < 0.0:
        return None
    return tuple(v / 100.0 for v in parts)


def evidence(rec):
    """Per-asset measured evidence, or a reason it could not be measured."""
    # READ the tag, do not assume it absent. DragonCave's registry carries
    # NaniteEnabled on all 115 StaticMeshes; hardcoding UNKNOWN here reported
    # "I could not look" over data that was present (non-negotiables 6 & 25).
    nan = rec.get("NaniteEnabled")
    out = {
        "name": rec.get("name"),
        "path": rec.get("path"),
        "triangles": None,
        "dims_m": None,
        "bbox_area_m2": None,
        "tri_per_m2": None,
        "shape": None,
        "nanite": ("UNKNOWN — registry tag absent" if nan is None
                   else str(nan)),
        "unmeasured": None,
    }

    tris = rec.get("Triangles")
    try:
        out["triangles"] = int(tris)
    except (TypeError, ValueError):
        out["unmeasured"] = "Triangles tag absent"
        return out

    d = dims_m(rec)
    if d is None:
        out["unmeasured"] = "ApproxSize tag absent or unparseable"
        return out
    out["dims_m"] = [round(v, 3) for v in d]

    x, y, z = d
    area = 2.0 * (x * y + y * z + z * x)
    if area <= 0.0:
        out["unmeasured"] = "degenerate bounding box, area 0"
        return out
    out["bbox_area_m2"] = round(area, 2)
    out["tri_per_m2"] = round(out["triangles"] / area, 1)

    lo, hi = min(d), max(d)
    out["shape"] = "planar" if hi > 0 and (lo / hi) < PLANAR_RATIO else "blob"
    return out


def gather(packs, substr=None, name_filter=None):
    rows = []
    for pack in packs:
        reg = load_registry(pack)
        for rec in reg.get("assets", []):
            if rec.get("class") != "StaticMesh":
                continue
            path = rec.get("path", "")
            if substr and substr not in path:
                continue
            if name_filter and name_filter.lower() not in rec.get("name", "").lower():
                continue
            row = evidence(rec)
            row["pack"] = pack
            rows.append(row)
    return rows


def summarise(rows, label):
    """Median tri/m^2 over BLOBS ONLY, which is the only valid comparison."""
    blobs = [r for r in rows if r.get("shape") == "blob" and r.get("tri_per_m2")]
    if not blobs:
        return None
    vals = sorted(r["tri_per_m2"] for r in blobs)
    mid = len(vals) // 2
    median = vals[mid] if len(vals) % 2 else 0.5 * (vals[mid - 1] + vals[mid])
    return {
        "label": label,
        "blob_count": len(blobs),
        "median_tri_per_m2": round(median, 1),
        "min_tri_per_m2": vals[0],
        "max_tri_per_m2": vals[-1],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--packs", default="KiteDemo,DragonCave,Atlantis_Ruins")
    ap.add_argument("--contains", default=None,
                    help="only asset paths containing this substring")
    ap.add_argument("--name", default=None,
                    help="only asset names containing this substring")
    ap.add_argument("--json-out", default=None,
                    help="write the full evidence table here")
    ap.add_argument("--compare", nargs=2, metavar=("SPEC_A", "SPEC_B"),
                    default=None,
                    help="two PACK:SUBSTR specs to compare, blobs only")
    args = ap.parse_args(argv)

    packs = [p.strip() for p in args.packs.split(",") if p.strip()]

    try:
        if args.compare:
            groups = []
            for spec in args.compare:
                pack, _, sub = spec.partition(":")
                rows = gather([pack], substr=sub or None)
                groups.append((spec, rows))
            print("QUALITY-TIER COMPARISON — blobs only, planar assets excluded")
            print("(bbox-area density; valid WITHIN a shape class only)")
            print("")
            stats = []
            for spec, rows in groups:
                s = summarise(rows, spec)
                stats.append(s)
                if s is None:
                    print("  {0:<28} no measurable blobs".format(spec))
                    continue
                print("  {0:<28} n={1:<3} median {2:>8.1f} tri/m2  "
                      "range {3:.1f}..{4:.1f}".format(
                          s["label"], s["blob_count"], s["median_tri_per_m2"],
                          s["min_tri_per_m2"], s["max_tri_per_m2"]))
            if all(stats) and stats[1]["median_tri_per_m2"] > 0:
                ratio = (stats[0]["median_tri_per_m2"]
                         / stats[1]["median_tri_per_m2"])
                print("")
                print("  RATIO {0} : {1}  =  {2:.1f}x".format(
                    stats[0]["label"], stats[1]["label"], ratio))
            return 0

        rows = gather(packs, substr=args.contains, name_filter=args.name)
        rows.sort(key=lambda r: (r["pack"], -(r.get("tri_per_m2") or 0)))
        print("{0:<10} {1:<40} {2:>9} {3:>10} {4:>9}  {5}".format(
            "pack", "asset", "tris", "tri/m2", "shape", "dims m"))
        for r in rows:
            if r.get("unmeasured"):
                print("{0:<10} {1:<40} {2:>9} {3:>10} {4:>9}  UNMEASURED: {5}"
                      .format(r["pack"], r["name"], r.get("triangles") or "?",
                              "-", "-", r["unmeasured"]))
                continue
            print("{0:<10} {1:<40} {2:>9} {3:>10.1f} {4:>9}  {5}".format(
                r["pack"], r["name"], r["triangles"], r["tri_per_m2"],
                r["shape"],
                " x ".join("%.1f" % v for v in r["dims_m"])))

        print("")
        n_known = sum(1 for r in rows
                      if not str(r.get("nanite", "")).startswith("UNKNOWN"))
        n_unknown = len(rows) - n_known
        if rows and n_unknown == len(rows):
            print("Nanite state is UNKNOWN for all {0} rows above — none carries"
                  " the registry".format(len(rows)))
            print("tag `NaniteEnabled`. Absent is not OFF; ask the editor.")
        elif n_unknown:
            print("Nanite: {0} of {1} rows carry the registry tag "
                  "`NaniteEnabled` (value in --json-out 'nanite'); the other "
                  "{2} lack it = UNKNOWN, not OFF.".format(
                      n_known, len(rows), n_unknown))
        elif rows:
            print("Nanite: all {0} rows carry the registry tag `NaniteEnabled` "
                  "(value in --json-out 'nanite').".format(len(rows)))

        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump({"rows": rows}, fh, indent=1)
            print("wrote {0}".format(args.json_out))
        return 0

    except (IOError, json.JSONDecodeError) as exc:
        # A present-but-corrupt registry (JSONDecodeError, a ValueError
        # subclass) is "unreadable" too -- catch it so it returns the
        # documented exit 2, not an uncaught traceback (exit 1).
        print("REFUSE: {0}".format(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
