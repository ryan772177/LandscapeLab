"""pass5_extract.py — assemble the RULING INPUT for Audit Pass 5.

Pass 5 reads every UNAPPLIED finding in `research/audit/findings_ledger.json`
(applied == false) IN ITS SOURCE PARAGRAPH and the desk rules each
APPLY / OBSOLETE / WRONG. The ledger only stores a truncated `finding`
fragment and a `file_line` whose LINE NUMBER is stale (files were archived and
LESSONS/RECIPES were edited since the ledger was built). This tool resolves the
CURRENT location by:
  1. remapping a path that Q2 moved (ADVISOR_LOG/BLENDER_HANDOFF -> hero/,
     MORNING_REPORT* -> docs/archive/), and
  2. GREPPING a distinctive substring of the finding text in the resolved file
     (line numbers are not trusted; the text is the anchor),
then extracting the surrounding paragraph (blank-line delimited, capped).

A finding whose source cannot be located (file gone, or text no longer present)
is emitted with source_status="NOT_FOUND" and NO paragraph — the desk rules that
one on the fragment alone (usually OBSOLETE). A failed lookup is REPORTED as
failed, never silently emitted as if the paragraph were empty (non-negotiable 6).

Usage
  python pass5_extract.py --start 0 --count 50 [--out batch.json]
  python pass5_extract.py --start 0 --count 50 --skip-ruled  # next unruled 50
  python pass5_extract.py --stats            # how many unapplied, how many locate
  python pass5_extract.py --selftest

INDEX-SHIFT TRAP (2026-09-16): --start indexes the CURRENT unapplied list,
which SHRINKS every time pass5_mark_applied marks an APPLY implemented — so a
positional resume pointer written before a mark ("resume at --start 150") is
stale the moment the mark runs, and following it skips exactly as many findings
as were marked. Use --skip-ruled for every batch after the first: it drops
findings already ruled in findings_rulings.json, so --start 0 --count 50 is
always "the next 50 unruled" regardless of how the ledger has shifted.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "research", "audit", "findings_ledger.json")
RULINGS = os.path.join(REPO, "research", "audit", "findings_rulings.json")

# Q2 (2026-09-16) moved these; the ledger predates the move.
MOVED = {
    "ADVISOR_LOG.md": "hero/ADVISOR_LOG.md",
    "BLENDER_HANDOFF.md": "hero/BLENDER_HANDOFF.md",
    "MORNING_REPORT.md": "docs/archive/MORNING_REPORT.md",
    "MORNING_REPORT_2.md": "docs/archive/MORNING_REPORT_2.md",
    "MORNING_REPORT_3.md": "docs/archive/MORNING_REPORT_3.md",
    "MORNING_REPORT_20260901.md": "docs/archive/MORNING_REPORT_20260901.md",
}


def load_all():
    return json.load(io.open(LEDGER, encoding="utf-8"))["findings"]


def load_unapplied():
    return [r for r in load_all() if not r.get("applied")]


def load_ruled_keys(rulings_path=None):
    """file_line keys already ruled in findings_rulings.json ({} if absent)."""
    p = rulings_path or RULINGS
    if not os.path.isfile(p):
        return set()
    return set(json.load(io.open(p, encoding="utf-8")).get("rulings", {}))


def filter_ruled(findings, ruled, ledger_counts=None):
    """Drop findings whose file_line is already ruled. file_line is the
    PRIMARY KEY of the whole pass-5 chain (rulings dict, merge validation,
    this filter) — a file_line shared by a ruled record and a DISTINCT
    unruled finding would silently drop the unruled one forever, so when
    ledger_counts (Counter over ALL ledger findings' file_lines) is given,
    any finding sitting on a duplicated key REFUSES via ValueError rather
    than filtering. The merge side already refuses intra-batch duplicates;
    this closes the extract side."""
    if ledger_counts:
        hit = sorted({r.get("file_line") for r in findings
                      if ledger_counts.get(r.get("file_line"), 0) > 1})
        if hit:
            raise ValueError(
                "file_line collision(s) in ledger — a keyed filter would "
                "silently drop a distinct finding: %s" % hit[:5])
    return [r for r in findings if r.get("file_line") not in ruled]


def resolve_path(file_line):
    """'FILE.md:123' -> (abs_path_or_None, orig_rel, hinted_line)."""
    m = re.match(r"^(.*?):(\d+)$", file_line)
    if m:
        rel, line = m.group(1), int(m.group(2))
    else:
        rel, line = file_line, None
    rel_now = MOVED.get(rel, rel)
    p = os.path.join(REPO, rel_now)
    if not os.path.isfile(p):
        # try a basename match under the repo for a file moved elsewhere
        return None, rel, line
    return p, rel_now, line


def _distinctive(text, n=48):
    """A substring of the finding text long enough to grep uniquely-ish.
    Strip markdown backticks/pipes that the fragment may carry."""
    t = text.strip().strip("`").strip()
    # drop a leading 'it '/'the ' etc. is unnecessary; take the longest run
    return t[:n]


def locate(path, needle):
    """Return (line_index0, paragraph) for the first line containing needle,
    or (None, None). Paragraph = the blank-line-delimited block, capped."""
    lines = io.open(path, encoding="utf-8", errors="replace").read().split("\n")
    key = needle.strip()
    hit = None
    for i, ln in enumerate(lines):
        if key and key in ln:
            hit = i
            break
    if hit is None:
        # relax: try the first ~24 chars
        short = key[:24]
        for i, ln in enumerate(lines):
            if short and short in ln:
                hit = i
                break
    if hit is None:
        return None, None
    # expand to blank-line-delimited paragraph, cap at 40 lines
    a = hit
    while a > 0 and lines[a - 1].strip():
        a -= 1
    b = hit
    while b < len(lines) - 1 and lines[b + 1].strip():
        b += 1
    a = max(a, hit - 20)
    b = min(b, hit + 20)
    return hit, "\n".join(lines[a:b + 1])


def build(findings):
    out = []
    for r in findings:
        fl = r.get("file_line", "")
        path, rel_now, hinted = resolve_path(fl)
        rec = {"file_line": fl, "resolved_path": rel_now,
               "finding": r.get("finding"), "dated": r.get("dated"),
               "numbers": r.get("numbers"), "identifiers": r.get("identifiers")}
        if path is None:
            rec["source_status"] = "NOT_FOUND"
            rec["paragraph"] = None
        else:
            idx, para = locate(path, _distinctive(r.get("finding", "")))
            if para is None:
                rec["source_status"] = "TEXT_NOT_FOUND"
                rec["paragraph"] = None
            else:
                rec["source_status"] = "OK"
                rec["located_line"] = idx + 1
                rec["paragraph"] = para
        out.append(rec)
    return out


def stats():
    un = load_unapplied()
    built = build(un)
    from collections import Counter
    c = Counter(b["source_status"] for b in built)
    print("unapplied findings: %d  (sample count = %d)" % (len(un), len(built)))
    print("source located:", dict(c))
    return 0


def selftest():
    ok = True
    # resolve_path remaps a moved file and parses the line
    p, rel, ln = resolve_path("ADVISOR_LOG.md:229")
    t1 = rel == "hero/ADVISOR_LOG.md" and ln == 229
    ok = ok and t1
    # a path with no colon still resolves rel
    p2, rel2, ln2 = resolve_path("recipes/schema.md")
    t2 = rel2 == "recipes/schema.md" and ln2 is None
    ok = ok and t2
    # locate finds a needle and returns a non-empty paragraph, and a bogus
    # needle returns (None, None) -- a miss is a miss, not an empty string
    import tempfile
    fd, tp = tempfile.mkstemp(suffix=".md", text=True)
    os.close(fd)
    io.open(tp, "w", encoding="utf-8").write(
        "para one line A\npara one line B\n\nTARGET distinctive phrase\nmore\n")
    idx, para = locate(tp, "TARGET distinctive phrase")
    t3 = idx == 3 and "TARGET distinctive phrase" in para
    miss_idx, miss_para = locate(tp, "no such text zzzq")
    t4 = miss_idx is None and miss_para is None
    os.remove(tp)
    ok = ok and t3 and t4
    # load_ruled_keys: reads keys from a rulings file; missing file -> empty set
    import tempfile as _tf
    fd5, rp = _tf.mkstemp(suffix=".json", text=True)
    os.close(fd5)
    io.open(rp, "w", encoding="utf-8").write(
        json.dumps({"rulings": {"A.md:1": {}, "B.md:2": {}}}))
    keys = load_ruled_keys(rp)
    t5 = keys == {"A.md:1", "B.md:2"}
    os.remove(rp)
    t6 = load_ruled_keys(rp) == set()  # file now absent -> empty, no crash
    # the REAL skip filter: ruled findings drop, order of the rest preserved
    fake = [{"file_line": "A.md:1"}, {"file_line": "C.md:3"},
            {"file_line": "B.md:2"}, {"file_line": "D.md:4"}]
    clean_counts = {"A.md:1": 1, "B.md:2": 1, "C.md:3": 1, "D.md:4": 1}
    left = filter_ruled(fake, {"A.md:1", "B.md:2"}, clean_counts)
    t7 = [r["file_line"] for r in left] == ["C.md:3", "D.md:4"]
    # a duplicated primary key REFUSES instead of silently dropping
    dup_counts = dict(clean_counts, **{"C.md:3": 2})
    try:
        filter_ruled(fake, {"A.md:1"}, dup_counts)
        t8 = False
    except ValueError:
        t8 = True
    # no counts given -> filter still works (guard is opt-in)
    t9 = [r["file_line"] for r in filter_ruled(fake, {"A.md:1"})] == \
        ["C.md:3", "B.md:2", "D.md:4"]
    ok = ok and t5 and t6 and t7 and t8 and t9
    print("selftest:", "PASS" if ok else "FAIL")
    print("  moved-path remap:", t1, "| no-colon path:", t2,
          "| locate hit:", t3, "| locate miss returns None:", t4,
          "| ruled-keys load:", t5, "| absent rulings -> empty:", t6,
          "| filter_ruled order-preserving:", t7,
          "| duplicate key REFUSES:", t8, "| no-counts filter ok:", t9)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--out")
    ap.add_argument("--skip-ruled", action="store_true",
                    help="drop findings already ruled in findings_rulings.json "
                         "before slicing (immune to ledger index shift)")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.stats:
        return stats()
    un = load_unapplied()
    pool = un
    if a.skip_ruled:
        from collections import Counter
        counts = Counter(r.get("file_line") for r in load_all())
        try:
            pool = filter_ruled(un, load_ruled_keys(), counts)
        except ValueError as e:
            print("REFUSE:", e)
            return 3
        print("skip-ruled: %d unapplied -> %d unruled" % (len(un), len(pool)))
    batch = pool[a.start:a.start + a.count]
    built = build(batch)
    payload = {"start": a.start, "count": len(built),
               "total_unapplied": len(un),
               "pool": "unruled" if a.skip_ruled else "unapplied",
               "total_pool": len(pool), "findings": built}
    js = json.dumps(payload, indent=1, ensure_ascii=False)
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(js)
        print("wrote %d findings [%d:%d] of %d %s -> %s"
              % (len(built), a.start, a.start + len(built), len(pool),
                 payload["pool"], a.out))
    else:
        print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
