"""pass5_mark_applied.py — mark the findings_ledger 'applied' flag for every
finding ruled APPLY in research/audit/findings_rulings.json.

Run per batch AFTER the batch's APPLY actions are actually done (already-
implemented ones are just bookkeeping; real doc-fixes must be made first, in the
same commit). Idempotent: only touches findings whose ledger entry is not yet
applied, and sets applied_where to the ruling's apply_action. Recomputes
n_unapplied. Preserves the ledger's json.dumps(indent=1) formatting.

Usage
  python pass5_mark_applied.py            # mark all APPLY not yet applied
  python pass5_mark_applied.py --dry-run  # report what it would mark
"""
from __future__ import annotations

import argparse
import io
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "research", "audit", "findings_ledger.json")
RULINGS = os.path.join(REPO, "research", "audit", "findings_rulings.json")


def run(dry):
    led = json.load(io.open(LEDGER, encoding="utf-8"))
    rul = json.load(io.open(RULINGS, encoding="utf-8"))["rulings"]
    applies = {fl: r for fl, r in rul.items() if r.get("verdict") == "APPLY"}
    by_fl = {}
    for r in led["findings"]:
        by_fl.setdefault(r.get("file_line"), []).append(r)
    marked = 0
    missing = []
    for fl, r in applies.items():
        recs = by_fl.get(fl)
        if not recs:
            missing.append(fl)
            continue
        for rec in recs:
            if rec.get("applied"):
                continue
            if dry:
                marked += 1
                continue
            rec["applied"] = True
            aw = rec.get("applied_where")
            aw = [] if aw in (None, "") else (aw if isinstance(aw, list) else [aw])
            note = r.get("apply_action") or r.get("reason") or "APPLY (Pass 5)"
            aw.append("%s [Pass5 %s]" % (note, r.get("batch", "")))
            rec["applied_where"] = aw
            marked += 1
    if missing:
        print("WARN: %d APPLY file_lines not found in ledger: %s"
              % (len(missing), missing[:3]))
    if not dry:
        led["n_unapplied"] = sum(1 for r in led["findings"] if not r.get("applied"))
        io.open(LEDGER, "w", encoding="utf-8").write(json.dumps(led, indent=1))
    n_un = sum(1 for r in led["findings"] if not r.get("applied"))
    print("%s %d APPLY finding(s); ledger n_unapplied=%d; %d APPLY total in rulings"
          % ("WOULD mark" if dry else "marked", marked, n_un, len(applies)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    return run(a.dry_run)


if __name__ == "__main__":
    import sys
    sys.exit(main())
