"""check_docs.py — the doc-consolidation invariants, enforced.

Offline, read-only, no editor. Added to scripts/run_offline_suite.py.

WHAT IT REFUSES, and why each check exists
------------------------------------------
1. INDEX COMPLETE      every path named in CLAUDE.md's index must exist.
                       An index that points at nothing is worse than none.
2. EVERYTHING COVERED  every tracked .md must be reachable from the index --
                       explicitly, by a declared directory prefix, or by being
                       under docs/archive/. A doc nobody indexed is a doc a
                       session finds by accident.
3. SIZE CEILING        CLAUDE.md < 25,000 chars. The whole unit exists because
                       it reached 492,079.
4. EXACTLY ONE         CLAUDE.md holds exactly ONE "# CURRENT STATE" heading
   CURRENT STATE       (the pointer) and STATE.md exactly one (the live block).
                       Thirty stacked blocks is how sessions started reasoning
                       from superseded state.
5. NO SELF-SUPERSEDE   no LIVE doc says "SUPERSEDED by" about itself -- that is
                       an archived file that never got moved.
6. NO STALE LINKS      no LIVE doc references a path that moved into
                       docs/archive/ without naming the archive path.
7. ARCHIVE BANNERS     every file under docs/archive/ carries its banner.

EXEMPTIONS ARE DECLARED HERE, NOT REMEMBERED
--------------------------------------------
LESSONS.md, RECIPES.md, docs/_consolidation_inventory.md, commits/ and
everything under _verify/ and _trash/ are exempt from the self-supersede AND
stale-link scans (checks 5-6). They are append-only law and dated evidence:
rewriting a path inside a record falsifies what was true when it was written.
This project already set that precedent by NOT sweeping the ryanb -> Admin
path migration through its narrative files.

Exit codes:  0 = all checks pass.  4 = one or more FAILURES.
             --self-test proves it can FAIL (non-negotiable 2: a gate that has
             only seen good input has not been tested).
"""
import io
import os
import re
import subprocess
import sys

# ASCII-SAFE STDOUT. This project has already lost a tool's worst verdict to a
# UnicodeEncodeError on cp1252 stdout: every ok row printed, and the first BAD
# row killed the process before the summary -- so the run reported success by
# omission. A checker that cannot print its own failure is not a checker.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE = os.path.join(REPO, "CLAUDE.md")

SIZE_CEILING = 25000

# Where the live CURRENT STATE block lives. It moved out of CLAUDE.md on
# 2026-09-13, when that file reached four characters of headroom under
# the ceiling above.
STATE_DOC = "STATE.md"

# Directory prefixes the index covers as a CLASS rather than file-by-file.
PREFIX_COVER = [
    "_verify/", "_trash/", "docs/archive/", "hero/", "terrain/regions/",
    ".claude/", "plans/phase2_lanes/", "plans/region_lanes/",
    "plans/region_authoring/", "captures/", "Free/",
    # R5 4b (2026-09-16): dead-world plan archive; its INDEX.md carries
    # the ⛔ banner and the per-plan move record.
    "foliage/_archive/",
]

# Exempt from the self-supersede and stale-link scans (checks 5-6). See docstring.
LINK_EXEMPT = ["LESSONS.md", "RECIPES.md", "_verify/", "_trash/",
               "docs/archive/", "docs/_consolidation_inventory.md",
               "commits/"]

DECLARE_MARKER = "<!-- ARCHIVED-PATHS-DECLARED -->"

ARCHIVE_BANNER_TOKENS = ["⛔", "SUPERSEDED", "HISTORY"]


def tracked_md():
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=REPO,
                         capture_output=True)
    return [p for p in out.stdout.decode("utf-8").split("\n") if p.strip()]


def read(p):
    full = os.path.join(REPO, p)
    if not os.path.exists(full):
        return ""       # a listed-but-absent file is caught by check 1, not here
    return io.open(full, encoding="utf-8", errors="replace").read()


def index_paths(claude_text):
    """Paths in the FIRST COLUMN of the index tables.

    Deliberately NOT every backticked token in the section: the description
    columns quote bare names like `alpine.json` and `drafts/` as prose, and a
    first pass reported those as 'index points at missing paths'. The path
    column is the only place a path is being DECLARED.
    """
    i = claude_text.find("# THE INDEX")
    if i < 0:
        return set()
    out = set()
    for line in claude_text[i:].split("\n"):
        if not line.startswith("|"):
            continue
        cell = line.split("|")[1] if line.count("|") >= 2 else ""
        # ALL backticked tokens in the path cell -- a row may legitimately list
        # several files (e.g. ADVISOR_LOG.md and MORNING_REPORT*.md together),
        # and taking only the first silently left the rest uncovered.
        for t in re.findall(r"`([^`\n]+)`", cell):
            t = t.strip()
            if t and not t.startswith("["):
                out.add(t)
    return out


def covered(path, idx):
    if path in idx:
        return True
    # STATE.md is named by CLAUDE.md's CURRENT STATE pointer rather than by
    # an index TABLE row, and `index_paths` only reads table cells. It is
    # covered by construction: check 4 refuses if it is missing.
    if path == STATE_DOC:
        return True
    for p in PREFIX_COVER:
        if path.startswith(p):
            return True
    for t in idx:
        if t.endswith("/") and path.startswith(t):
            return True
        if t.endswith("*.md"):
            base = t[:-5]
            if path.startswith(base):
                return True
    return False


def run_checks(claude_text, md_files, moved_map):
    failures = []
    idx = index_paths(claude_text)

    # 1. index paths exist
    missing = []
    for t in sorted(idx):
        cand = t.rstrip("/")
        if "*" in cand:
            continue
        if not os.path.exists(os.path.join(REPO, cand)):
            missing.append(t)
    if missing:
        failures.append("INDEX POINTS AT MISSING PATHS: %s" % ", ".join(missing))

    # 2. every tracked .md covered
    uncovered = [p for p in md_files if not covered(p, idx)]
    if uncovered:
        failures.append("NOT INDEXED AND NOT ARCHIVED (%d): %s"
                        % (len(uncovered), ", ".join(sorted(uncovered)[:12])))

    # 3. size ceiling
    if len(claude_text) >= SIZE_CEILING:
        failures.append("CLAUDE.md is %d chars, ceiling is %d (over by %d)"
                        % (len(claude_text), SIZE_CEILING,
                           len(claude_text) - SIZE_CEILING))

    # 4. exactly one CURRENT STATE
    #
    # MOVED 2026-09-13: the live block now lives in STATE.md, because
    # CLAUDE.md reached FOUR characters of headroom under its ceiling and
    # the state could no longer grow without displacing law. CLAUDE.md
    # keeps a one-line POINTER, which still matches "^# CURRENT STATE".
    #
    # ⛔ THE INVARIANT HAS TO FOLLOW THE BLOCK. Checking only CLAUDE.md
    # after the move would leave the real state file unguarded -- and
    # thirty stacked blocks is the exact defect this check was written
    # for. So: CLAUDE.md must hold exactly one heading (the pointer), and
    # STATE.md must hold exactly one (the live block).
    n = len(re.findall(r"^# CURRENT STATE", claude_text, re.M))
    if n != 1:
        failures.append("CLAUDE.md has %d '# CURRENT STATE' headings, must be 1" % n)
    state_path = os.path.join(REPO, STATE_DOC)
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as fh:
            state_text = fh.read()
        m = len(re.findall(r"^# CURRENT STATE", state_text, re.M))
        if m != 1:
            failures.append("%s has %d '# CURRENT STATE' headings, must be 1"
                            % (STATE_DOC, m))
    else:
        failures.append("%s is missing -- CLAUDE.md points at it" % STATE_DOC)

    # 5/6. live docs: no self-supersede, no stale links
    declared = []
    for p in md_files:
        if any(p.startswith(e) or p == e for e in LINK_EXEMPT):
            continue
        if p.startswith("docs/archive/"):
            continue
        txt = read(p)
        base = os.path.basename(p)
        # A doc may DECLARE, once and visibly, that it deliberately carries
        # historical paths -- for records whose original wording must not be
        # rewritten. The declaration is a marker IN THE FILE, not a name
        # hardcoded here, and it is reported rather than applied silently.
        if DECLARE_MARKER in txt:
            declared.append(p)
            continue
        if re.search(r"SUPERSEDED by", txt) and re.search(
                r"SUPERSEDED by[^\n]{0,80}" + re.escape(base), txt):
            failures.append("%s says it is SUPERSEDED by itself" % p)
        for old, new in moved_map.items():
            for m in re.finditer(re.escape(old), txt):
                # Accept the archive path ANYWHERE NEARBY, before or after.
                # A historical entry is best annotated with a pointer rather
                # than rewritten -- rewriting the path inside a recorded ruling
                # falsifies what was true when it was written -- so a trailing
                # "(now docs/archive/...)" has to count as resolved.
                seg = txt[max(0, m.start() - 160):m.start() + len(old) + 160]
                if "docs/archive/" in seg:
                    continue
                failures.append("%s references moved path '%s' (now %s)"
                                % (p, old, new))
                break

    # 7. archive banners
    for p in md_files:
        if not p.startswith("docs/archive/"):
            continue
        txt = read(p)[:4000]
        if not any(t in txt for t in ARCHIVE_BANNER_TOKENS):
            failures.append("%s has no archive banner" % p)
    if declared:
        print("  note  %d doc(s) DECLARE historical paths, so the stale-link "
              "scan skipped them: %s" % (len(declared), ", ".join(declared)))
    return failures


def moved_paths():
    """Old path -> new path, for files this unit relocated."""
    out = {}
    d = os.path.join(REPO, "docs", "archive", "pre8k")
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".md"):
                out[f] = "docs/archive/pre8k/" + f
    return out


def main():
    self_test = "--self-test" in sys.argv
    claude_text = read("CLAUDE.md")
    md = tracked_md()
    moved = moved_paths()

    if self_test:
        # NON-NEGOTIABLE 2: prove it refuses. Four mutations, each aimed at a
        # different check, on COPIES -- nothing on disk is touched. Each case
        # carries the substring of ITS aimed failure, so a mutation that trips
        # only some UNRELATED check is not miscounted as refused (rule 13).
        print("SELF-TEST — each mutation must be REFUSED by its aimed check")
        cases = [
            ("size ceiling", claude_text + ("x" * SIZE_CEILING), md, moved,
             "ceiling is"),
            ("two CURRENT STATE blocks",
             claude_text + "\n# CURRENT STATE — a second one\n", md, moved,
             "'# CURRENT STATE' headings"),
            ("index points at a missing path",
             claude_text.replace("# THE INDEX",
                                 "# THE INDEX\n\n| `docs/does_not_exist.md` | x | y |"),
             md, moved, "INDEX POINTS AT MISSING PATHS"),
            ("an unindexed .md", claude_text, md + ["some/stray_doc.md"], moved,
             "NOT INDEXED AND NOT ARCHIVED"),
        ]
        bad = 0
        for name, ct, mds, mv, expect in cases:
            f = run_checks(ct, mds, mv)
            ok = any(expect in x for x in f)
            print("  %-34s %s" % (name, "REFUSED" if ok else "!! NOT REFUSED"))
            if not ok:
                bad += 1
        # positive control: the real state must PASS
        f = run_checks(claude_text, md, moved)
        print("  %-34s %s" % ("positive control (real repo)",
                              "passes" if not f else "!! FAILS: %s" % f[0][:70]))
        if f:
            bad += 1
        print()
        print("self-test: %d of %d behaved correctly" % (5 - bad, 5))
        return 4 if bad else 0

    failures = run_checks(claude_text, md, moved)
    print("check_docs.py — %d tracked .md files, CLAUDE.md %d chars (ceiling %d)"
          % (len(md), len(claude_text), SIZE_CEILING))
    if failures:
        print()
        for f in failures:
            print("  FAIL  %s" % f)
        print()
        print("%d FAILURE(S)" % len(failures))
        return 4
    print("  ok  index complete, everything covered, one CURRENT STATE, "
          "no stale links, archive banners present")
    print("NO FAILURES")
    return 0


if __name__ == "__main__":
    sys.exit(main())
