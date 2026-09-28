"""hlod_stale_parents.py -- which HLOD parents went stale when their children were rebuilt.

    python scripts/hlod_stale_parents.py --json <out.json>

READ-ONLY. No editor, no build. Every file is opened 'rb'.

⭐ WHY THIS IS ANSWERABLE OFF DISK AT ALL. A parent cell's HLOD_REPORT
records its children's BAKED OUTPUT ASSETS by name and hash, under
`## Referenced Assets ##`:

    @TEX-D800: Texture2D /Temp/BuildHLODPackage_173.Alpine8K_MainPartition_L2_X6_Y3
               T_LandscapeStreamingProxy_..._BaseColor (Hash=983C3052)
    @SM-3160:  StaticMesh /Temp/BuildHLODPackage_173.StaticMesh_Alpine8K_HLODLayer_Instanced_0

so the parent->child edge, and the child's content hash AS THE PARENT SAW
IT, are both in the parent's own bytes. Nothing needs to be inferred from
labels or grid arithmetic.

⛔ WHAT THIS DOES **NOT** DO, STATED SO NOBODY PROMOTES IT. It does not
recompute the children's current hashes -- those are engine hashes over
built assets and there is no off-disk way to produce them. It does not
need to: every one of the 256 landscape L2 cells was REBUILT on
2026-09-14 (1024 -> 4096), so any hash a parent recorded before that
rebuild is stale BY CONSTRUCTION. The staleness verdict here rests on
"the child was rebuilt after the parent was", which is checked from the
two reports' own `DateTimeUTC` fields -- not on a hash comparison.

A parent that was itself rebuilt AFTER its children is NOT stale, and is
counted separately rather than lumped in.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hlod_report_offdisk as HR   # noqa: E402
import uasset_lite                 # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Windows consoles default to cp1252 and this file prints the project's
# marker glyphs. Without this, a REFUSAL message raises UnicodeEncodeError
# and the refusal is replaced by a traceback -- the one output path that
# must never fail is the one that reports failure.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# A child landscape cell's baked texture, as named inside a PARENT's report.
CHILD_TEX = re.compile(
    r"(Alpine8K_MainPartition_L(\d)_(X-?\d+_Y-?\d+))T_LandscapeStreamingProxy_[^\s.]*?"
    r"_(BaseColor|Normal|MRS)\s+\(Hash=([0-9A-Fa-f]+)\)")
LEVEL = re.compile(r"_L(\d)_")


def level_of(label):
    m = LEVEL.search(label or "")
    return f"L{m.group(1)}" if m else "?"


def layer_loading_range(asset_rel):
    """Read `LoadingRange` off a UHLODLayer asset, no editor."""
    p = os.path.join(REPO_ROOT, asset_rel)
    if not os.path.exists(p):
        return None, f"missing: {asset_rel}"
    with open(p, "rb") as fh:
        data = fh.read()
    try:
        summary = uasset_lite.read_summary(data)
        names = uasset_lite.read_names(data, summary)
    except Exception as exc:                          # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    # LoadingRange is a double, CellSize an int32 (HLODLayer.h:127,131).
    lr = uasset_lite.find_double_properties(data, names, "LoadingRange")
    cs = uasset_lite.find_int_properties(data, names, "CellSize")
    if not lr and not cs:
        return None, "neither LoadingRange (double) nor CellSize (int32) found"
    return {"LoadingRange": [v for _o, v in lr],
            "CellSize": [v for _o, v in cs]}, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json")
    a = ap.parse_args()

    children, parents = {}, []
    considered = no_block = 0

    for p in HR.gitignored_hlod_packages():
        if not os.path.exists(p):
            continue
        considered += 1
        text = HR.extract_block(p)
        if text is None:
            no_block += 1
            continue
        rec = HR.parse(text, p)

        if rec["has_landscape_fields"]:
            # ⛔ KEY ON THE CELL NAME, NOT THE FULL LABEL. A child's label is
            # "<layer>/<cell>" ("Alpine8K_HLODLayer_Instanced/Alpine8K_MainPartition_L2_X6_Y3")
            # while a parent names only the CELL. Keying on the full label
            # silently matched nothing and reported 256 cells "undated"
            # rather than 0 stale -- measured, first run 2026-09-14.
            children[(rec["label"] or "").split("/")[-1]] = rec
            continue

        refs = {}
        for m in CHILD_TEX.finditer(text):
            cell, lvl, xy, prop, h = m.groups()
            refs.setdefault(cell, {})[prop] = h
        if refs:
            rec["child_refs"] = refs
            parents.append(rec)

    print(f"packages considered : {considered}")
    print(f"  no report block   : {no_block}")
    print(f"  landscape children: {len(children)}")
    print(f"  parents REFERENCING a landscape child: {len(parents)}")
    if not parents:
        print("\n⛔ REFUSING: 0 parents parsed. Zero found is not zero stale -- "
              "it is an instrument that matched nothing.")
        return 4

    # Staleness by BUILD TIME, not by hash: a parent built before its child
    # carries the child's pre-rebuild output.
    stale, fresh, undated = [], [], []
    for par in parents:
        pt = par.get("DateTimeUTC")
        child_times = [children[c]["DateTimeUTC"]
                       for c in par["child_refs"] if c in children]
        if not pt or not child_times or any(t is None for t in child_times):
            undated.append(par)
        elif max(child_times) > pt:
            stale.append(par)
        else:
            fresh.append(par)

    print(f"\n  STALE (a child was rebuilt after the parent) : {len(stale)}")
    print(f"  fresh (parent newer than every child)        : {len(fresh)}")
    print(f"  undated / unresolvable                       : {len(undated)}")

    by_level = Counter(level_of(r["label"]) for r in stale)
    print("\nSTALE PARENTS BY LEVEL")
    for lvl, n in sorted(by_level.items()):
        b = sum(r["bytes"] for r in stale if level_of(r["label"]) == lvl)
        print(f"   {lvl}  n={n:<5} current package bytes {b:,} "
              f"({b/2**30:.2f} GB)")
    tot = sum(r["bytes"] for r in stale)
    print(f"   ALL n={len(stale):<5} current package bytes {tot:,} "
          f"({tot/2**30:.2f} GB)")

    # How many distinct children each parent pulls, and coverage of the 256.
    covered = set()
    for r in stale:
        covered |= set(r["child_refs"])
    fan = Counter(len(r["child_refs"]) for r in stale)
    print(f"\n  distinct landscape children referenced by stale parents: "
          f"{len(covered)} of {len(children)}")
    print(f"  children-per-parent distribution: {dict(sorted(fan.items()))}")

    print("\nLOADING RANGE, read off the layer assets (no editor)")
    for rel in ("LandscapeLab/Content/Alpine8K_HLODLayer_Instanced.uasset",
                "LandscapeLab/Content/Alpine8K_HLODLayer_Merged.uasset"):
        vals, err = layer_loading_range(rel)
        print(f"   {os.path.basename(rel):<40} {vals if vals else '⛔ ' + err}")

    print("\nMinVisibleDistance recorded in the cells themselves")
    for grp, rows in (("landscape children", list(children.values())),
                      ("stale parents", stale)):
        c = Counter(str(r["MinVisibleDistance"]) for r in rows)
        print(f"   {grp:<22} {dict(c)}")

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({
                "n_children": len(children),
                "n_parents_referencing": len(parents),
                "n_stale": len(stale), "n_fresh": len(fresh),
                "n_undated": len(undated),
                "stale_by_level": dict(by_level),
                "stale_bytes_total": tot,
                "stale": [{"label": r["label"], "level": level_of(r["label"]),
                           "bytes": r["bytes"], "built": r["DateTimeUTC"],
                           "children": sorted(r["child_refs"])}
                          for r in stale],
            }, fh, indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
