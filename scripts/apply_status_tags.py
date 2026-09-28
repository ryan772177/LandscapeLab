"""apply_status_tags.py -- insert `> STATUS:` lines under headings (D-1 item 5).

    python scripts/apply_status_tags.py --dry-run   # report, write nothing
    python scripts/apply_status_tags.py --apply       # insert the lines

Reads research/audit/status_tags_2026-09-15.tsv (seq, file, grep, tag, text)
-- the judgement from PASS4 §4 read entry-by-entry. For each row it finds
the ONE line containing `grep` and inserts `> STATUS: <tag> — <text>`
directly under it.

⛔ FAIL CLOSED. A grep that matches ZERO or MORE THAN ONE line is REFUSED
and reported, never guessed -- a STATUS line under the wrong heading is a
knowledge-base defect. Idempotent: if a `> STATUS:` line already follows
the heading, the row is skipped. Insertions are applied bottom-up per file
so earlier line indices do not drift.
"""
from __future__ import annotations

import argparse
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(REPO, "research", "audit", "status_tags_2026-09-15.tsv")


def load(tsv=None):
    rows = []
    with open(tsv or TSV, encoding="utf-8") as fh:
        header = fh.readline()
        assert header.split("\t")[0] == "seq", header
        for ln in fh:
            ln = ln.rstrip("\n")
            if not ln.strip():
                continue
            seq, fname, grep, tag, text = ln.split("\t")
            rows.append({"seq": seq, "file": fname, "grep": grep,
                         "tag": tag, "text": text})
    return rows


def status_line(tag, text):
    return "> STATUS: %s — %s" % (tag, text) if text else "> STATUS: %s" % tag


def process(apply, tsv=None):
    rows = load(tsv)
    byfile = {}
    for r in rows:
        byfile.setdefault(r["file"], []).append(r)
    applied = skipped = refused = 0
    report = []
    for fname, frows in byfile.items():
        path = os.path.join(REPO, fname)
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        # A generated block (the TOC, the CURRENT VALUES table) lists every
        # heading, so a substring grep matches there too. Exclude those line
        # ranges -- the STATUS line belongs on the BODY heading only.
        generated = set()
        depth = 0
        for i, ln in enumerate(lines):
            if "TOC:BEGIN" in ln or "CURRENT_VALUES:BEGIN" in ln:
                depth += 1
            if depth > 0:
                generated.add(i)
            if "TOC:END" in ln or "CURRENT_VALUES:END" in ln:
                depth = max(0, depth - 1)
        inserts = []  # (line_index_after_which_to_insert, text)
        for r in frows:
            hits = [i for i, ln in enumerate(lines)
                    if r["grep"] in ln and i not in generated]
            if len(hits) == 0:
                refused += 1
                report.append("REFUSE seq %s (%s): grep %r matched 0 lines"
                              % (r["seq"], fname, r["grep"]))
                continue
            if len(hits) > 1:
                refused += 1
                report.append("REFUSE seq %s (%s): grep %r matched %d lines %s"
                              % (r["seq"], fname, r["grep"], len(hits),
                                 [h + 1 for h in hits]))
                continue
            i = hits[0]
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt.startswith("> STATUS:"):
                skipped += 1
                continue
            inserts.append((i, status_line(r["tag"], r["text"])))
            applied += 1
        # bottom-up so indices do not shift
        for i, txt in sorted(inserts, key=lambda t: -t[0]):
            lines.insert(i + 1, txt)
        if apply and inserts:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
    print("applied %d | skipped (already tagged) %d | REFUSED %d"
          % (applied, skipped, refused))
    for line in report:
        print("  " + line)
    return refused == 0 or True  # report is the product; refusals are expected


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tsv", default=None,
                    help="alternate TSV (e.g. the Pass-5 second pass, "
                         "status_tags_pass5_2026-09-16.tsv); default is "
                         "the 09-15 first-pass file")
    a = ap.parse_args(argv)
    process(apply=a.apply and not a.dry_run, tsv=a.tsv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
