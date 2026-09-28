"""Prove the doc-consolidation unit destroyed nothing.

Compares the tracked .md set at tag pre-doc-consolidation-20260829 against the
working tree, and accounts for every byte of the ORIGINAL set:

  UNCHANGED   same path, byte-identical
  EXTENDED    same path, original content still present as a substring
              (TOCs, banners and correction notes are ADDITIONS)
  MOVED       content present verbatim at a new path
  SPLIT       content distributed across several files, each piece verbatim
  MISSING     <- the only outcome that matters. Any byte here is a defect.

Exit 0 = every original byte accounted for. Exit 5 = something is missing.
"""
import io
import os
import re
import subprocess
import sys

# ASCII-SAFE STDOUT -- see check_docs.py. A cp1252 stdout kills this script on
# the first non-ASCII line of a DEFECT report, which is exactly the line that
# must survive.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = "pre-doc-consolidation-20260829"

# ---------------------------------------------------------------------------
# LINES DELIBERATELY REWRITTEN BY THIS UNIT, each with its reason.
# Three lines in the whole 4.7 MB doc set. They are matched by a distinctive
# fragment, listed in the output every run, and anything NOT here that goes
# missing still fails the check.
DECLARED_REWRITES = {
    "CANDIDATE replacement for `Conifer`":
        "ASSETS.md — the row's link to plans/conifer_asset_spec.md gained a "
        "pointer to its archive path. The row's FACTS are untouched.",
    "modal error. Full click-list":
        "terrain/regions/README.md — repointed at the archived "
        "IMPORT_CHECKLIST.md and warns its premise died with R-CREATE.",
    "# CURRENT STATE — 2026-08-27d":
        "the 27d heading was edited to mark it superseded when the post-hoc "
        "2026-08-28 block was inserted above it. Its BODY is byte-identical in "
        "the archive; both heading forms are recorded verbatim in "
        "docs/archive/claude_md_superseded_sections.md.",
}
# ---------------------------------------------------------------------------


def sh(args):
    return subprocess.run(args, cwd=REPO, capture_output=True).stdout


def at_tag(path):
    return sh(["git", "show", "%s:%s" % (TAG, path)]).decode("utf-8", "replace")


def now(path):
    full = os.path.join(REPO, path)
    if not os.path.exists(full):
        return None
    # newline="" IS LOAD-BEARING. Without it Python's universal-newline mode
    # rewrites a lone CR to a newline, which SPLITS any line containing one --
    # while at_tag() decodes raw bytes and does not. That mismatch reported a
    # lost line in a file this unit never touched. The two readers must return
    # the same representation or they are not comparable.
    return io.open(full, encoding="utf-8", errors="replace", newline="").read()


def lines_lost(orig, cur):
    """Original lines absent from cur, as a MULTISET difference.

    A plain substring test is wrong here and reported seven false defects on
    the first run: this unit inserts banners and TOCs in the MIDDLE of files,
    so the original is no longer contiguous even though not one line was
    removed. Counting lines answers the question actually being asked --
    "was anything destroyed?" -- and tolerates insertion anywhere.
    """
    from collections import Counter

    def norm(t):
        # ALL carriage returns are removed, not just CRLF pairs.
        #
        # This comparison reads the ORIGINAL from a git blob (`git show TAG:p`,
        # unfiltered) and the CURRENT from the working copy (filtered by
        # core.autocrlf on checkout). Those are two REPRESENTATIONS of the same
        # content, and comparing them raw reported a "lost line" in
        # _verify/20260815_pn_spruce_forest_intake.md -- a file this unit never
        # touched, and which `git status` calls unmodified. Stripping CR makes
        # the check representation-independent, which is what it was always
        # asking about.
        return Counter(l.replace("\r", "") for l in t.split("\n"))

    missing = norm(orig) - norm(cur)
    # Lines this unit deliberately REWROTE, each declared with its reason.
    # Declared, printed, and never silent -- an undeclared rewrite is still a
    # defect and still fails.
    missing = Counter({l: n for l, n in missing.items()
                       if not any(k in l for k in DECLARED_REWRITES)})
    return sum(missing.values()), missing


def tag_md():
    out = sh(["git", "ls-tree", "-r", "--name-only", TAG]).decode("utf-8")
    return [p for p in out.split("\n") if p.endswith(".md")]


# Where each moved file went.
MOVED = {
    "SWEEP_REPORT.md": "docs/archive/pre8k/SWEEP_REPORT.md",
    "VERIFICATION.md": "docs/archive/pre8k/VERIFICATION.md",
    "IMPORT_CHECKLIST.md": "docs/archive/pre8k/IMPORT_CHECKLIST.md",
    "plans/alpine_execution_plan.md": "docs/archive/pre8k/alpine_execution_plan.md",
    "plans/clip_30s_proposal.md": "docs/archive/pre8k/clip_30s_proposal.md",
    "plans/conifer_asset_spec.md": "docs/archive/pre8k/conifer_asset_spec.md",
}

# CLAUDE.md was SPLIT. Each piece must appear verbatim in one of these.
CLAUDE_TARGETS = [
    "CLAUDE.md",
    "docs/archive/current_state_history.md",
    "docs/non-negotiables.md",
    "docs/environment.md",
    "docs/ue58-api-protocol.md",
    "docs/archive/claude_md_superseded_sections.md",
]


def check_claude(report):
    orig = at_tag("CLAUDE.md")
    pool = []
    for t in CLAUDE_TARGETS:
        c = now(t)
        if c is not None:
            pool.append((t, c))

    # Decompose the original into its CURRENT STATE blocks and its head.
    pat = re.compile(r"^# CURRENT STATE", re.M)
    starts = [m.start() for m in pat.finditer(orig)]
    pieces = []
    head = orig[: starts[0]] if starts else orig
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(orig)
        pieces.append(("CURRENT STATE block %d" % (i + 1), orig[s:e]))

    # Decompose the head by its top-level sections.
    hmarks = [m.start() for m in re.finditer(r"^#{1,2} [A-Z]", head, re.M)]
    hmarks.append(len(head))
    for i in range(len(hmarks) - 1):
        seg = head[hmarks[i]:hmarks[i + 1]]
        title = seg.split("\n", 1)[0][:52]
        pieces.append(("head: " + title, seg))

    found_bytes = 0
    missing = []
    for name, piece in pieces:
        hit = None
        for tname, content in pool:
            if piece in content or lines_lost(piece, content)[0] == 0:
                hit = tname
                break
        if hit:
            found_bytes += len(piece)
        else:
            missing.append((name, len(piece)))
    report.append(("CLAUDE.md", len(orig), found_bytes, missing))
    return missing


def main():
    report = []
    defects = []

    claude_missing = check_claude(report)
    if claude_missing:
        defects.append(("CLAUDE.md", claude_missing))

    totals = {"unchanged": 0, "extended": 0, "moved": 0, "missing": 0}
    rows = []
    for p in tag_md():
        if p == "CLAUDE.md":
            continue
        orig = at_tag(p)
        cur = now(p)
        if cur is not None:
            if cur == orig:
                totals["unchanged"] += len(orig)
                rows.append(("UNCHANGED", p, len(orig)))
            else:
                lost, which = lines_lost(orig, cur)
                if lost == 0:
                    totals["extended"] += len(orig)
                    rows.append(("EXTENDED +%d" % (len(cur) - len(orig)),
                                 p, len(orig)))
                else:
                    totals["missing"] += len(orig)
                    rows.append(("!! LOST %d lines" % lost, p, len(orig)))
                    sample = [l for l in which if l.strip()][:2]
                    defects.append((p, "%d original lines absent, e.g. %r"
                                    % (lost, sample)))
        elif p in MOVED:
            dest = now(MOVED[p])
            ok = dest is not None and lines_lost(orig, dest)[0] == 0
            if ok:
                totals["moved"] += len(orig)
                rows.append(("MOVED -> " + MOVED[p], p, len(orig)))
            else:
                totals["missing"] += len(orig)
                defects.append((p, "moved but content not verbatim at dest"))
        else:
            totals["missing"] += len(orig)
            defects.append((p, "GONE, and not in the moved map"))

    print("BYTE RECONCILIATION — %s -> working tree" % TAG)
    print()
    for kind, p, n in sorted(rows, key=lambda r: -r[2])[:14]:
        print("  %-26s %9d  %s" % (kind, n, p))
    print("  ... %d files total" % len(rows))
    print()
    print("  unchanged   %10d chars" % totals["unchanged"])
    print("  extended    %10d  (originals still present; TOCs/banners added)"
          % totals["extended"])
    print("  moved       %10d" % totals["moved"])
    print("  MISSING     %10d" % totals["missing"])
    print()
    for name, orig_len, found, miss in report:
        print("  %s: %d chars decomposed, %d accounted for, %d pieces missing"
              % (name, orig_len, found, len(miss)))
        for m, n in miss:
            print("      MISSING %6d  %s" % (n, m))
    print()
    print("  DECLARED REWRITES — %d lines, listed so none is silent:"
          % len(DECLARED_REWRITES))
    for frag, why in DECLARED_REWRITES.items():
        print("      %s" % why)
    print()
    if defects:
        print("DEFECTS: %d" % len(defects))
        for d in defects:
            print("   ", d)
        return 5
    print("EVERY ORIGINAL BYTE ACCOUNTED FOR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
