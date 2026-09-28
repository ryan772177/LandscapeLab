"""hlod_report_census.py -- what each HLOD cell says about its OWN last build.

READ-ONLY. No editor, no commandlet. Reads the `HLODBuildReport` string that
`AWorldPartitionHLOD` saves into every HLOD actor package.

WHY THIS EXISTS: TWO PROXIES FOR "STALE" WERE BOTH WRONG
    The mixed-world state after builds 1-3 was tracked first by PACKAGE SIZE
    (`> 5 MB` = old MeshMerge, CURRENT STATE 2026-09-09) and then by TRIANGLE
    COUNT from `-DumpStats` (`>= 100k` = old MeshMerge). Measured 2026-09-09,
    both misclassify:

      package size   705 packages over 5 MB, but only 468 cells carry
                     >= 100k triangles -- the size band and the geometry band
                     do not agree, because a cell's package also holds its
                     baked textures.
      triangle count `..._Merged/..._Instanced_L1_X-4_Y-2` has 8,449 triangles
                     in a 19,071,154-byte package, and its own build report
                     says `LayerType: MeshMerge(1)`, built by build 1. A
                     higher-level MeshMerge cell can be under any triangle
                     threshold you pick. Classifying it as "rebuilt" is wrong
                     in the expensive direction: it would be left stale.

    Both proxies are downstream of the same thing -- the geometry a build
    emitted -- so agreeing would not have made them right (non-negotiable 0).
    This reads a DIFFERENT record: the settings the build actually ran with,
    written by the engine at build time.

WHAT THE REPORT CONTAINS, and where it comes from
    `AWorldPartitionHLOD::UpdateHLODBuildReportContent` (HLODActor.cpp:830-850)
    assembles a plain-text block into the saved `UPROPERTY() FString
    HLODBuildReport` (HLODActor.h:232), delimited by
    `### HLOD_REPORT_BEGIN ###` (HLODActor.cpp:738). It carries, per cell:

        * CommandLine:   the FULL command line of the build that wrote it
        * DateTimeUTC:   when
        Label:           which cell
        ### HLOD Build Details ###
        * LayerType:     MeshMerge(1) / MeshApproximate(N) -- THE DISCRIMINATOR
        * ...SettingsHash, SourceActorsHash, MinVisibleDistance

    The per-field breakdown is `FHLODHashBuilder::BuildHashReport()`, i.e.
    exactly the fields that feed the rebuild-policy hash
    (`HLODRebuildPolicyHashCompare.cpp:38-62`). So this file answers both
    "is this cell stale" and "what would the rebuild policy compare".

    Note `UHLODRebuildPolicyHashData::HLODHashReport` is `UPROPERTY(Transient)`
    -- the report survives only because it is copied into the actor's
    `HLODBuildReport`. The 32-bit hash itself is NOT in the text.

Run:
    python scripts/hlod_report_census.py                  # summary
    python scripts/hlod_report_census.py --list MeshMerge # the stale labels
    python scripts/hlod_report_census.py --json out.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_LIST = os.path.join(REPO_ROOT, "_verify", "hlod", "hlod_packages.txt")

BEGIN = b"### HLOD_REPORT_BEGIN ###"

RE_LABEL = re.compile(r"Label:(\S+)")
RE_LAYERTYPE = re.compile(r"\* LayerType:\s*(\S+)")
RE_WHEN = re.compile(r"\* DateTimeUTC:\s*([\d\- :]+)")
RE_CMDLINE = re.compile(r"\* CommandLine:\s*(.*)")


def read_report(path):
    """(label, layer_type, when, has_rebuild_flag) or None if no report.

    Read as latin-1: the FString is saved narrow here, and the fields wanted
    are ASCII. Decoding errors are replaced rather than raised -- a package
    that cannot be parsed must be REPORTED as unknown, never silently counted
    as current.
    """
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    i = data.find(BEGIN)
    if i < 0:
        return None
    txt = data[i:i + 40000].decode("latin-1", "replace")
    label = RE_LABEL.search(txt)
    lt = RE_LAYERTYPE.search(txt)
    when = RE_WHEN.search(txt)
    cmd = RE_CMDLINE.search(txt)
    cmdline = cmd.group(1).strip() if cmd else ""
    return (label.group(1) if label else None,
            lt.group(1) if lt else None,
            when.group(1).strip() if when else None,
            "-RebuildHLODs" in cmdline)


def load_packages():
    if not os.path.isfile(PACKAGE_LIST):
        raise SystemExit("missing %s -- run scripts/hlod_gitignore.py"
                         % PACKAGE_LIST)
    with open(PACKAGE_LIST, "r", encoding="utf-8") as fh:
        return [l.strip() for l in fh
                if l.strip() and not l.startswith("#")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", default=None,
                    help="print labels whose LayerType starts with this")
    ap.add_argument("--json", default=None, help="write full per-cell JSON")
    args = ap.parse_args(argv)

    rels = load_packages()
    per, by_type, by_when, no_report = {}, collections.Counter(), \
        collections.Counter(), []
    total_bytes = 0

    for rel in rels:
        full = os.path.join(REPO_ROOT, rel.replace("/", os.sep))
        try:
            total_bytes += os.path.getsize(full)
        except OSError:
            pass
        rep = read_report(full)
        if rep is None:
            no_report.append(rel)
            by_type["<no report>"] += 1
            continue
        label, layer_type, when, forced = rep
        key = label or rel
        per[key] = {"package": rel, "layer_type": layer_type,
                    "built_utc": when, "forced": forced}
        by_type[layer_type or "<unknown>"] += 1
        if when:
            by_when[when[:13]] += 1     # hour bucket

    print("packages          %d" % len(rels))
    print("with a report     %d" % len(per))
    print("no report         %d" % len(no_report))
    print("bytes             %d (%.2f GiB)"
          % (total_bytes, total_bytes / 2**30))
    print()
    print("LAYER TYPE RECORDED BY THE CELL'S OWN LAST BUILD")
    for k, v in by_type.most_common():
        print("   %-22s %5d" % (k, v))
    print()
    print("BUILT (UTC hour)")
    for k, v in sorted(by_when.items()):
        print("   %s   %5d" % (k, v))

    if args.list:
        sel = sorted(k for k, v in per.items()
                     if (v["layer_type"] or "").startswith(args.list))
        print()
        print("%d cells with LayerType starting %r:" % (len(sel), args.list))
        for k in sel:
            print("   ", k)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"summary": dict(by_type), "cells": per,
                       "no_report": no_report}, fh, indent=2)
        print("\nwrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
