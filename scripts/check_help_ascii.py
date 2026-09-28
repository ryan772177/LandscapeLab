"""check_help_ascii.py -- argparse help strings must be ASCII.

    python scripts/check_help_ascii.py            (checks every script)
    python scripts/check_help_ascii.py --selftest (proves it can fail)

⛔ THE DEFECT THIS EXISTS FOR, and it was self-inflicted on 2026-09-13.
A `⛔` was put into one `--instrument` help string. argparse prints help
with `file.write()` on stdout, which on this machine is cp1252, so
`bench_capture.py --help` raised UnicodeEncodeError and printed NOTHING
-- not the offending line, the WHOLE help. The flag it documented became
undiscoverable, and the failure was found by accident a day later while
checking that an unrelated flag had registered.

A tool whose `--help` crashes cannot explain itself, and `--help` is
exactly what someone reaches for when they do not already know the tool.
Docstrings, comments and printed output are unaffected -- those are read
from the file or written after the encoding is known. This checks the
one place where the console codec gets a vote.

The check is AST-based, so it sees only real `add_argument(help=...)`
arguments: a `⛔` in a docstring three lines above is not a false
positive.
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import sys

SKIP_DIRS = {".git", "__pycache__", "dist", "_trash", "node_modules",
             "Intermediate", "Saved", "Binaries", "Build", "site-packages"}


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


def offenders(src, path="<str>"):
    """[(lineno, codepoint)] for non-ASCII inside add_argument help=."""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [("SYNTAX", str(exc))]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "add_argument"):
            continue
        for kw in node.keywords:
            if kw.arg != "help":
                continue
            for sub in ast.walk(kw.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    for ch in sub.value:
                        if ord(ch) > 127:
                            out.append((sub.lineno, ord(ch)))
    return out


def _selftest():
    # Direction 1: BLOCK the violation.
    bad = "import argparse\np=argparse.ArgumentParser()\np.add_argument('--x', help='no ⛔ entry')\n"
    # Direction 2: PASS the legitimate case -- including a non-ASCII
    # DOCSTRING, which is fine and must not be flagged.
    good = ('"""A docstring with ⛔ and ★ in it, which is fine."""\n'
            "import argparse\np=argparse.ArgumentParser()\n"
            "p.add_argument('--x', help='plain ascii help')\n")
    # Direction 3: BLOCK WHEN BROKEN -- malformed input must not sail through.
    broken = "def (:\n"
    r1, r2, r3 = offenders(bad), offenders(good), offenders(broken)
    ok1, ok2, ok3 = bool(r1), not r2, bool(r3)
    print("  %-56s %s" % ("BLOCK: non-ASCII inside help=",
                          "PASS" if ok1 else "FAIL"))
    print("  %-56s %s" % ("PASS: ascii help, non-ASCII docstring",
                          "PASS" if ok2 else "FAIL"))
    print("  %-56s %s" % ("BLOCK WHEN BROKEN: unparseable source",
                          "PASS" if ok3 else "FAIL"))
    return 0 if (ok1 and ok2 and ok3) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    n_files, bad_files = 0, []
    for root, dirs, files in os.walk(os.path.join(REPO, "scripts")):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(root, f)
            n_files += 1
            try:
                src = io.open(p, encoding="utf-8").read()
            except Exception:
                continue
            hits = offenders(src, p)
            hits = [h for h in hits if h[0] != "SYNTAX"]
            if hits:
                bad_files.append((os.path.relpath(p, REPO), hits))

    print("checked %d scripts for non-ASCII in argparse help" % n_files)
    if not bad_files:
        print("OK -- every --help is printable through the console codec")
        return 0
    for rel, hits in bad_files:
        print("FAIL %s" % rel)
        for ln, cp in hits[:8]:
            print("      line %-6s U+%04X" % (ln, cp))
    print("")
    print("argparse writes help through stdout's codec (cp1252 here), so "
          "ONE non-ASCII character suppresses the ENTIRE help text.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
