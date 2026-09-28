"""census_rollup.py — one consolidated JSON of every value the census set out
to collect, with the STATUS of each.

WHY A STATUS FIELD ON EVERY NUMBER
----------------------------------
This census produced three kinds of zero and they are not interchangeable:

    MEASURED        the lookup reached where the thing lives and counted it
    MEASURED_ZERO   same, and there were none -- a real absence
    UNVERIFIED      produced by a lookup that was later found broken, and the
                    source is gone so it cannot be re-run
    NOT_CAPTURED    the accessor failed; no value exists
    BLOCKED         the project could not be opened at all

Reporting a bare number would flatten those into one, which is the exact
failure this census kept hitting: `pcg_graphs: 0` on the PCG reference project
looked identical to a real zero.

Reads only the committed artefacts. No editor.
"""
from __future__ import annotations

import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDIR = os.path.join(REPO, "research", "census")

# Targets the brief named, per project.
BRIEF_TARGETS = {
    "ElectricDreams": ["pcg_graphs (close-range and far-range maps)"],
    "CitySample": ["hlod_layers", "world_partition"],
    "ValleyOfTheAncient": ["landscape_materials", "lighting"],
    "DarkRuins": ["tessellation/displacement", "post-process"],
}

SECTIONS = ["project", "hlod_layers", "world_partition", "foliage_types",
            "impostors", "pcg_graphs", "landscape_materials", "lighting",
            "water"]


def count(sec):
    if isinstance(sec, (list, dict)):
        return len(sec)
    return sec


def error_only(sec):
    """True if the section holds nothing but error records."""
    items = list(sec.values()) if isinstance(sec, dict) else (
        sec if isinstance(sec, list) else [])
    if not items:
        return False
    return all(isinstance(i, dict) and set(i.keys()) <= {"_error", "_note"}
               for i in items)


def status_for(name, sec, trace, unverified):
    if name in unverified:
        return "UNVERIFIED"
    if error_only(sec):
        return "NOT_CAPTURED"
    n = count(sec)
    if n:
        return "MEASURED"
    # a zero -- did the lookup reach a package where the class exists?
    keys = {"foliage_types": ("FoliageType", "FoliageType_InstancedStaticMesh"),
            "pcg_graphs": ("PCGGraph",),
            "hlod_layers": ("HLODLayer",)}.get(name, ())
    for k in keys:
        t = (trace or {}).get(k)
        if t:
            return "MEASURED_ZERO"
    return "ZERO_UNAUDITED"


def main():
    out = {
        "_what": "Consolidated census values. Every number carries a STATUS -- "
                 "a bare count cannot distinguish a real zero from a lookup "
                 "that asked the wrong place, and this census produced both.",
        "_status_meanings": {
            "MEASURED": "counted, lookup verified to have reached the right place",
            "MEASURED_ZERO": "none exist; the lookup reached where they live",
            "UNVERIFIED": "value came from a lookup later found broken, and "
                          "the source project has been deleted, so it cannot "
                          "be re-run",
            "NOT_CAPTURED": "the accessor failed; no value exists",
            "ZERO_UNAUDITED": "zero, with no trace proving the lookup landed",
            "BLOCKED": "the project could not be opened",
        },
        "brief_targets": BRIEF_TARGETS,
        "maps": {},
        "projects_not_censused": {},
        "known_limits": [],
    }

    # City Sample's two zeros predate the asset-lookup fix and its vault copy
    # was deleted to free disk, so they can never be confirmed.
    UNVERIFIED = {"CitySample__Small_City_LVL":
                  {"foliage_types", "pcg_graphs"}}

    for path in sorted(glob.glob(os.path.join(CDIR, "*.json"))):
        base = os.path.basename(path)[:-5]
        if base.endswith(".stations"):
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            out["maps"][base] = {"_error": str(e)}
            continue
        secs = d.get("sections") or {}
        trace = d.get("asset_lookup_trace")
        unver = UNVERIFIED.get(base, set())
        rec = {
            "world": (d.get("current_world") or [None])[0],
            "artefact": os.path.relpath(path, REPO).replace("\\", "/"),
            "asset_lookup_trace_present": bool(trace),
            "values": {},
        }
        for s in SECTIONS:
            if s not in secs:
                continue
            rec["values"][s] = {
                "count": count(secs[s]),
                "status": status_for(s, secs[s], trace, unver),
            }
        # world partition detail, where it exists
        wp = secs.get("world_partition")
        if isinstance(wp, dict) and wp:
            first = list(wp.values())[0]
            if isinstance(first, dict) and "world_partition_path" in first:
                rec["world_partition_detail"] = {
                    k: first.get(k) for k in
                    ("world_partition_path", "default_hlod_layer",
                     "runtime_hash_class", "runtime_hash_route")}
        # landscape material detail, where it exists
        lm = secs.get("landscape_materials")
        if isinstance(lm, dict) and lm:
            k = list(lm)[0]
            hist = (lm[k] or {}).get("expression_histogram") or {}
            rec["landscape_material_detail"] = {
                "material": k,
                "distinct_expression_types": len(hist),
                "top_expressions": dict(sorted(hist.items(),
                                               key=lambda x: -x[1])[:6]),
            }
        out["maps"][base] = rec

    out["projects_not_censused"] = {
        "ValleyOfTheAncient": {
            "status": "BLOCKED",
            "why": "C++ modules compiled for 5.7; a 5.8 editor logs 'Still "
                   "incompatible or missing module' for AncientGame, "
                   "InstanceLevelCollision, Crossfader, Uproar, Underscore and "
                   "HoverDrone, then exits. Rebuild in progress.",
            "targets_unmet": BRIEF_TARGETS["ValleyOfTheAncient"],
        },
    }
    out["known_limits"] = [
        "world_partition cell size and loading range are UNREACHABLE: "
        "UWorldPartitionRuntimeHashSet declares RuntimePartitions private, so "
        "it is not reflected to Python. Same wall as bench_grid_derive.py:139.",
        "CitySample foliage_types and pcg_graphs are UNVERIFIED: produced by "
        "the broken /Script/Engine lookup, and the 106 GB vault copy was "
        "deleted during a disk crisis, so they cannot be re-run.",
        "DarkRuins landscape_materials is 0 and that map has no Landscape "
        "actor at all, so the brief's tessellation/displacement target is "
        "UNANSWERED rather than answered negatively.",
        "Screenshots are one viewpoint per project, not multi-angle surveys. "
        "See the READMEs under research/census/shots/.",
    ]

    dest = os.path.join(CDIR, "CENSUS_ROLLUP.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("wrote %s" % os.path.relpath(dest, REPO))
    for m, r in out["maps"].items():
        if "values" not in r:
            continue
        vals = " ".join("%s=%s(%s)" % (k, v["count"], v["status"][:4])
                        for k, v in r["values"].items()
                        if k in ("hlod_layers", "pcg_graphs", "foliage_types",
                                 "landscape_materials"))
        print("  %-38s %s" % (m, vals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
