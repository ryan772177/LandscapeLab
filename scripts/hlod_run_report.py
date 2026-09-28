"""hlod_run_report.py -- the per-batch table and the per-layer attribution.

    python scripts/hlod_run_report.py _verify/hlod/<run_dir>

Reads the run's own `batches.json` records -- written by
`hlod_build_batched` after every batch and committed with it -- and
prints the table the build is judged on:

    cells / approve / reject / VRAM peak / elapsed, per batch
    per-layer and per-cell attribution, rolled up across batches

⛔ `#### Built N ####` IS NOT A SUCCESS SIGNAL and is not used here. It
counts cells VISITED: batch 0 of the 2026-09-09 run printed "Built 191"
over 191 rejections and zero geometry. The columns below come from the
decision lines and the package census.

⭐ EVERY ROLL-UP CARRIES ITS PAIRING HEALTH (standing rule 13). If any
batch lost sync between a `Building HLOD actor` line and its decision,
the per-layer totals are marked untrustworthy rather than printed as
though they were clean.
"""
from __future__ import annotations

import io
import json
import os
import sys
from collections import Counter


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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run_dir = sys.argv[1]
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(REPO, run_dir)
    state_p = os.path.join(run_dir, "batches.json")
    if not os.path.isfile(state_p):
        print("no batches.json in %s" % run_dir)
        return 1
    st = json.load(io.open(state_p, encoding="utf-8"))
    recs = st.get("records") or []
    planned = st.get("batches")
    total_guids = st.get("guids_total")

    print("run      %s" % os.path.relpath(run_dir, REPO))
    print("plan     %s batches, %s cells, engine %s"
          % (planned, total_guids, st.get("engine_version")))
    print("")
    print("%-6s %-7s %-8s %-8s %-10s %-8s %-7s %s"
          % ("batch", "cells", "approve", "reject", "vram_peak",
             "minutes", "torn", "exit"))
    tot_cells = tot_a = tot_r = 0
    peak = 0
    minutes = 0.0
    layer = Counter()
    untrustworthy = []
    for r in recs:
        att = r.get("attribution") or {}
        tot_cells += r.get("cells_in_batch") or 0
        tot_a += r.get("approve_rebuild") or 0
        tot_r += r.get("reject_rebuild") or 0
        peak = max(peak, r.get("vram_peak_mb") or 0)
        minutes += r.get("minutes") or 0.0
        for lname, row in (att.get("by_layer") or {}).items():
            layer[(lname, "approve")] += row.get("ApproveRebuild", 0)
            layer[(lname, "reject")] += row.get("RejectRebuild", 0)
        if att and not att.get("trustworthy", True):
            untrustworthy.append(r.get("batch"))
        print("%-6s %-7s %-8s %-8s %-10s %-8.1f %-7s %s"
              % (r.get("batch"), r.get("cells_in_batch"),
                 r.get("approve_rebuild"), r.get("reject_rebuild"),
                 r.get("vram_peak_mb"), r.get("minutes") or 0.0,
                 len(r.get("torn_packages") or []),
                 "clean" if r.get("true_exit") else "LEFTOVERS"))

    print("")
    print("TOTAL    %d batches of %s   cells %d   approve %d   reject %d"
          % (len(recs), planned, tot_cells, tot_a, tot_r))
    print("         VRAM peak %d MiB   elapsed %.1f min (%.2f h)"
          % (peak, minutes, minutes / 60.0))
    if recs and tot_cells:
        rate = tot_cells / minutes if minutes else 0
        left = (total_guids or 0) - tot_cells
        print("         rate %.2f cells/min   remaining %d cells "
              "-> %.1f h at this rate" % (rate, left,
                                          (left / rate / 60.0) if rate else 0))

    print("")
    print("ATTRIBUTION (per layer, rolled up)")
    if untrustworthy:
        print("  [!] batches %s lost pairing sync -- these totals are NOT "
              "trustworthy" % untrustworthy)
    names = sorted({k[0] for k in layer})
    for n in names:
        print("  %-40s approve %-7d reject %d"
              % (n, layer[(n, "approve")], layer[(n, "reject")]))
    if not names:
        print("  (no attribution recorded yet)")

    out = os.path.join(run_dir, "run_report.json")
    json.dump({
        "_what": "per-batch table and per-layer attribution for this run",
        "_built_marker_note": "'#### Built N ####' counts cells VISITED, "
                              "not built, and is deliberately not used",
        "run_dir": os.path.relpath(run_dir, REPO),
        "planned_batches": planned, "total_cells": total_guids,
        "batches_done": len(recs), "cells_done": tot_cells,
        "approve": tot_a, "reject": tot_r,
        "vram_peak_mb": peak, "elapsed_min": round(minutes, 1),
        "per_layer": {n: {"approve": layer[(n, "approve")],
                          "reject": layer[(n, "reject")]} for n in names},
        "batches_with_untrustworthy_pairing": untrustworthy,
    }, io.open(out, "w", encoding="utf-8"), indent=1)
    print("")
    print("wrote %s" % os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
