"""hlod_attribution.py -- who built what, and under which layer.

THE ONE IMPLEMENTATION. `hlod_build_batched` uses it to attribute each
batch as it finishes, and `research/audit/tools/hlod_build_status.py`
imports it to attribute historical runs. Two readers of the same log
format are one reader badly stored (NN24), and the two had already
drifted: the audit tool paired cells with decisions while the build
script counted them in separate buckets.

⛔ WHY A BARE APPROVE/REJECT COUNT IS NOT AN ATTRIBUTION. The decision
line carries NO cell identity:

    LogHLODBuilder: Evaluated HLOD rebuild policies, final decision: ApproveRebuild

The identity is on the line BEFORE it, and that line names two different
things:

    LogWorldPartitionHLODsBuilder: [6 / 6] Building HLOD actor
        Alpine8K_HLODLayer_Merged/Alpine8K_HLODLayer_Instanced_L0_X-8_Y10...
        ^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        the LAYER the actor        the SOURCE it is built FROM
        belongs to

They are NOT the same and the pair above is the cascade working --
Merged built from the Instanced level below it. Reading the cell name as
the layer reports 19 Instanced where the truth is 19 Merged.

This cost a real misreading: "46 cells built" on 2026-09-13 told nobody
whether the Landscape layer had been exercised (it had not -- 27
Instanced, 19 Merged, 0 Landscape).

⭐ EVERY COUNT TRAVELS WITH ITS SAMPLE SIZE (standing rule 13).
`decisions_without_a_cell` is reported explicitly: if it is non-zero the
pairing lost sync and the per-layer numbers are not trustworthy, which a
reader cannot tell from the per-layer numbers alone.
"""
from __future__ import annotations

import io
import os
import re
from collections import Counter, OrderedDict

RE_BUILDING = re.compile(
    r"\[(\d+) / (\d+)\] Building HLOD actor ([A-Za-z0-9_]+)/([A-Za-z0-9_\-]+)")
RE_DECISION = re.compile(
    r"Evaluated HLOD rebuild policies, final decision: (\w+)")
# Strip the grid suffix at ANY level: L0/L1/L2 all occur.
RE_GRID_SUFFIX = re.compile(r"^(.*?)_L\d+_X")


def source_layer(cell):
    """The layer a cell was built FROM, with its grid coordinates removed."""
    m = RE_GRID_SUFFIX.match(cell)
    return m.group(1) if m else cell


def attribute(log_path, keep_cells=True, max_cells=20000):
    """Pair every `Building HLOD actor` line with the decision that follows.

    Returns per-layer and (optionally) per-cell rows. `keep_cells=False`
    for very long runs where only the roll-up is wanted.
    """
    out = {
        "log": os.path.basename(log_path),
        "by_layer": OrderedDict(),
        "cells": [] if keep_cells else None,
        "n_building_lines": 0,
        "n_decisions": 0,
        "decisions_without_a_cell": 0,
        "cells_without_a_decision": 0,
        "_pairing": "each decision is attributed to the most recent "
                    "preceding `Building HLOD actor` line; the FOLDER is "
                    "the layer, the cell name is the source",
    }
    if not os.path.isfile(log_path):
        out["error"] = "no such log"
        return out

    by_layer = {}
    pending = None
    with io.open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = RE_BUILDING.search(line)
            if m:
                if pending is not None:
                    # A new cell started before the previous one was
                    # decided. Counted, not silently dropped.
                    out["cells_without_a_decision"] += 1
                pending = (m.group(3), m.group(4), int(m.group(1)),
                           int(m.group(2)))
                out["n_building_lines"] += 1
                continue
            m = RE_DECISION.search(line)
            if not m:
                continue
            out["n_decisions"] += 1
            decision = m.group(1)
            if pending is None:
                out["decisions_without_a_cell"] += 1
                continue
            layer, cell, idx, total = pending
            pending = None
            row = by_layer.setdefault(
                layer, {"layer": layer, "ApproveRebuild": 0,
                        "RejectRebuild": 0, "other": 0,
                        "source_layers": Counter()})
            if decision in ("ApproveRebuild", "RejectRebuild"):
                row[decision] += 1
            else:
                row["other"] += 1
            row["source_layers"][source_layer(cell)] += 1
            if keep_cells and len(out["cells"]) < max_cells:
                out["cells"].append({"i": idx, "n": total, "layer": layer,
                                     "cell": cell, "decision": decision})
    if pending is not None:
        out["cells_without_a_decision"] += 1

    for layer, row in sorted(by_layer.items()):
        row["source_layers"] = dict(row["source_layers"])
        row["total"] = row["ApproveRebuild"] + row["RejectRebuild"] + row["other"]
        out["by_layer"][layer] = row

    out["approved"] = sum(r["ApproveRebuild"] for r in by_layer.values())
    out["rejected"] = sum(r["RejectRebuild"] for r in by_layer.values())
    out["trustworthy"] = bool(out["decisions_without_a_cell"] == 0
                              and out["cells_without_a_decision"] == 0)
    return out


def format_attribution(att):
    """One compact block, sample counts included."""
    lines = []
    if att.get("error"):
        return "  attribution: %s" % att["error"]
    lines.append("  attribution  building-lines %d  decisions %d  "
                 "approved %d  rejected %d"
                 % (att["n_building_lines"], att["n_decisions"],
                    att["approved"], att["rejected"]))
    if not att["trustworthy"]:
        lines.append("  ⚠ PAIRING LOST SYNC: %d decisions with no cell, "
                     "%d cells with no decision -- per-layer numbers below "
                     "are NOT trustworthy"
                     % (att["decisions_without_a_cell"],
                        att["cells_without_a_decision"]))
    for layer, r in att["by_layer"].items():
        lines.append("    %-34s approve %-6d reject %-6d  from %s"
                     % (layer, r["ApproveRebuild"], r["RejectRebuild"],
                        ", ".join("%s x%d" % kv
                                  for kv in sorted(r["source_layers"].items()))))
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys
    for p in sys.argv[1:]:
        a = attribute(p)
        print(format_attribution(a))
        print(json.dumps({k: v for k, v in a.items() if k != "cells"},
                         indent=1)[:400])
