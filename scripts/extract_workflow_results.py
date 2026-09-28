"""extract_workflow_results.py — pull agent results out of a workflow journal.

WHY THIS EXISTS. A Workflow run persists one {"type":"result",...} line per
completed agent to `journal.jsonl` in its transcript directory. That file
survives the session, the process and a usage reset. The tool's returned
summary does NOT — it is truncated in the notification and gone once the
conversation moves on.

So when a long workflow lands during a reset, or a session ends before its
results are read, THE JOURNAL IS THE ARTEFACT and this reads it.

Usage:
  python scripts/extract_workflow_results.py <journal-or-run-dir> [--out DIR]

With no --out it lists what is there. With --out it writes each string result
to a numbered markdown file so nothing is lost to a truncated notification.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys


def load(path):
    """Every parsed line of a journal, tolerant of partial writes.

    A journal being APPENDED TO while a workflow still runs will have a
    torn final line. That is not corruption and must not abort the read —
    it is skipped and counted, so a partial harvest reports itself as
    partial rather than as complete (non-negotiable 6).
    """
    rows, torn = [], 0
    for line in io.open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            torn += 1
    return rows, torn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="journal.jsonl, or the run directory")
    ap.add_argument("--out", default=None,
                    help="write each string result here as markdown")
    args = ap.parse_args(argv)

    path = args.target
    if os.path.isdir(path):
        path = os.path.join(path, "journal.jsonl")
    if not os.path.isfile(path):
        print("REFUSE: no journal at {0}".format(path))
        return 2

    rows, torn = load(path)
    results = [r for r in rows if r.get("type") == "result"]
    print("journal      : {0}".format(path))
    print("rows         : {0}  ({1} results, {2} unparseable)".format(
        len(rows), len(results), torn))
    if torn:
        print("  NOTE: {0} torn line(s). If the workflow is still RUNNING "
              "this is expected and this harvest is PARTIAL.".format(torn))
    print("")

    if args.out and not os.path.isdir(args.out):
        os.makedirs(args.out)

    n = 0
    for i, r in enumerate(results):
        val = r.get("result", r.get("value"))
        label = r.get("label") or r.get("agentLabel") or ""
        if isinstance(val, str):
            kind, size = "text", len(val)
        elif isinstance(val, dict):
            kind, size = "dict", len(json.dumps(val))
        else:
            kind, size = type(val).__name__, 0
        first = ""
        if isinstance(val, str) and val.strip():
            first = val.strip().splitlines()[0][:70]
        print("  [{0:>2}] {1:<6} {2:>7}  {3:<24} {4}".format(
            i, kind, size, label, first))
        if args.out and isinstance(val, str) and val.strip():
            safe = "".join(c if c.isalnum() or c in "-_" else "_"
                           for c in (label or "result"))
            dest = os.path.join(args.out, "{0:02d}_{1}.md".format(i, safe))
            io.open(dest, "w", encoding="utf-8").write(val)
            n += 1
    if args.out:
        print("")
        print("wrote {0} text result(s) to {1}".format(n, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
