"""pass5_merge_rulings.py — validate a Pass-5 deputy's batch rulings and merge
them into the durable `research/audit/findings_rulings.json`.

The read-only desk deputy rules each unapplied finding APPLY / OBSOLETE / WRONG
and returns a JSON array (one object per finding + a trailing __SUMMARY__).
This tool VALIDATES that array against the batch it was ruling (rule 13: the
count must match, every file_line must belong to the batch, every verdict must
be in the enum) and merges it into the accumulating rulings file. It REFUSES a
batch whose count or file_lines do not line up rather than record a partial or
mismatched set — a ruling recorded against the wrong finding is worse than none.

It does NOT mark the ledger "applied": that flag means IMPLEMENTED, and it is
set only when an APPLY is actually carried out (a separate, per-finding step).

Usage
  python pass5_merge_rulings.py --batch research/audit/pass5/batch_000.json \
      --rulings <deputy.json> [--out research/audit/findings_rulings.json]
  python pass5_merge_rulings.py --selftest
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO, "research", "audit", "findings_rulings.json")
VERDICTS = {"APPLY", "OBSOLETE", "WRONG"}


def validate(batch, rulings):
    """Return (ok, msg, cleaned_rulings_without_summary). REFUSE on mismatch."""
    want = {f["file_line"] for f in batch["findings"]}
    rows = [r for r in rulings if r.get("file_line") != "__SUMMARY__"]
    summ = [r for r in rulings if r.get("file_line") == "__SUMMARY__"]
    if len(rows) != len(want):
        return False, ("count mismatch: %d ruling rows vs %d batch findings"
                       % (len(rows), len(want))), None
    got = {r.get("file_line") for r in rows}
    if got != want:
        missing = want - got
        extra = got - want
        return False, ("file_line set mismatch: missing %d, extra %d (e.g. "
                       "missing=%s extra=%s)" % (len(missing), len(extra),
                       list(missing)[:2], list(extra)[:2])), None
    for r in rows:
        v = r.get("verdict")
        if v not in VERDICTS:
            return False, "bad verdict %r for %s" % (v, r.get("file_line")), None
        if v == "APPLY" and not r.get("apply_action"):
            return False, ("APPLY without apply_action: %s"
                           % r.get("file_line")), None
    return True, ("ok: %d rows, summary=%s"
                  % (len(rows), summ[0].get("reason") if summ else "none")), rows


def merge(batch_path, rulings_path, out_path):
    batch = json.load(io.open(batch_path, encoding="utf-8"))
    rulings = json.load(io.open(rulings_path, encoding="utf-8"))
    ok, msg, rows = validate(batch, rulings)
    if not ok:
        print("REFUSE:", msg)
        return 1
    acc = {}
    if os.path.isfile(out_path):
        acc = json.load(io.open(out_path, encoding="utf-8"))
    findings = acc.get("rulings", {})
    dated_by = {f["file_line"]: f.get("dated") for f in batch["findings"]}
    added = 0
    for r in rows:
        fl = r["file_line"]
        findings[fl] = {"verdict": r["verdict"], "reason": r.get("reason"),
                        "apply_action": r.get("apply_action"),
                        "dated": dated_by.get(fl),
                        "batch": os.path.basename(batch_path)}
        added += 1
    from collections import Counter
    counts = Counter(v["verdict"] for v in findings.values())
    acc = {"_what": "Audit Pass 5 rulings: verdict per unapplied finding "
                    "(APPLY/OBSOLETE/WRONG). APPLY carries a concrete action; "
                    "the ledger 'applied' flag is set only when an APPLY is "
                    "actually implemented.",
           "n_ruled": len(findings), "counts": dict(counts),
           "rulings": findings}
    io.open(out_path, "w", encoding="utf-8").write(
        json.dumps(acc, indent=1, ensure_ascii=False))
    print("MERGED %d rows from %s -> %d total ruled; counts %s"
          % (added, os.path.basename(batch_path), len(findings), dict(counts)))
    return 0


def selftest():
    ok = True
    batch = {"findings": [{"file_line": "A.md:1", "dated": "2026-01-01"},
                          {"file_line": "B.md:2", "dated": "2026-01-02"}]}
    good = [{"file_line": "A.md:1", "verdict": "APPLY", "reason": "gap",
             "apply_action": "add gate"},
            {"file_line": "B.md:2", "verdict": "OBSOLETE", "reason": "parked",
             "apply_action": None},
            {"file_line": "__SUMMARY__", "verdict": "COUNTS",
             "reason": "APPLY=1 OBSOLETE=1 WRONG=0", "apply_action": None}]
    o, m, rows = validate(batch, good)
    t_pass = o and len(rows) == 2
    # count mismatch REFUSES
    o2, _, _ = validate(batch, good[:1] + good[2:])
    # file_line mismatch REFUSES
    bad_fl = [dict(good[0]), {"file_line": "C.md:9", "verdict": "WRONG",
              "reason": "x", "apply_action": None}]
    o3, _, _ = validate(batch, bad_fl)
    # APPLY without action REFUSES
    bad_ap = [{"file_line": "A.md:1", "verdict": "APPLY", "reason": "x",
               "apply_action": None},
              {"file_line": "B.md:2", "verdict": "OBSOLETE", "reason": "y",
               "apply_action": None}]
    o4, _, _ = validate(batch, bad_ap)
    # bad verdict REFUSES
    bad_v = [{"file_line": "A.md:1", "verdict": "MAYBE", "reason": "x",
              "apply_action": None},
             {"file_line": "B.md:2", "verdict": "OBSOLETE", "reason": "y",
              "apply_action": None}]
    o5, _, _ = validate(batch, bad_v)
    ok = t_pass and not o2 and not o3 and not o4 and not o5
    print("selftest:", "PASS" if ok else "FAIL")
    print("  valid PASSES:", t_pass, "| count-mismatch REFUSES:", not o2,
          "| file_line-mismatch REFUSES:", not o3,
          "| APPLY-no-action REFUSES:", not o4, "| bad-verdict REFUSES:", not o5)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch")
    ap.add_argument("--rulings")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.batch and a.rulings):
        print("need --batch and --rulings (or --selftest)"); return 2
    return merge(a.batch, a.rulings, a.out)


if __name__ == "__main__":
    sys.exit(main())
