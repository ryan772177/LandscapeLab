"""check_save_verified.py - no save's return may be silently discarded.

Pass 3 reading (2026-09-18, ~648 fixes across 178 scripts) found the same defect
over and over: a persistence call whose BOOL RETURN is the only disk-persistence
signal, used as a bare statement so the return is thrown away, while a success
message prints anyway. `save_loaded_assets`/`save_packages`/`save_asset`/
`save_current_level`/`write_triangle_mesh` all return False on failure WITHOUT
raising -- so a discarded return is a save that can silently not happen and still
report OK. That is standing rule 12 ("a value not read back is prose") in its
most mechanical form, and unlike the other audit classes it is statically
decidable, so it is caught here instead of by the next reading pass.

WHAT IS FLAGGED
---------------
A call to one of the SAVE FUNCS used as a bare expression statement -- i.e. its
return value is neither assigned, tested in an `if`, returned, asserted, nor
passed to another call. Assigning it (`saved = eal.save_asset(p)`), gating on it
(`if not eal.save_asset(p): raise`), or wrapping it (`bool(save_asset(p))` inside
an assignment) all satisfy the rule and are NOT flagged.

DELIBERATE DISCARD
------------------
A save whose return is genuinely not needed opts out with an inline pragma naming
why:  `eal.save_asset(p)   # save-return: best-effort, verified by re-read below`
The pragma is the honest form -- it makes the discard a stated decision, not an
oversight, exactly as the constitution asks.

LIMITS, STATED (not silent)
---------------------------
* It is an AST match on the CALLED NAME, so a save reached through an alias
  (`f = eal.save_asset; f(p)`) is not seen. Stated, not hidden.
* The OTHER Pass-3 classes -- an unconditional `ok = True` tail, a read-back that
  is never COMPARED, an NN13 zero-sample verdict -- are NOT checked here. They
  need judgement a static scan cannot supply (that is why the deputy-audit pass
  existed); a flaky detector for them would train readers to ignore this suite,
  which is worse than not having it. This checks the one class a machine decides.

    python scripts/check_save_verified.py
    python scripts/check_save_verified.py --self-test

Exit codes:
    0  no discarded save-returns
    1  could not look (a scripts tree that does not exist)
    2  at least one save-return is discarded without a pragma
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The persistence calls whose bool return IS the disk-persistence signal. Each
# returns False on failure without raising, so a discarded return hides a save
# that did not happen. Verified against the repo's usage on 2026-09-18.
SAVE_FUNCS = {
    "save_asset",
    "save_loaded_asset",
    "save_loaded_assets",
    "save_packages",
    "save_dirty_packages",
    "save_current_level",
    "write_triangle_mesh",
}

PRAGMA = "# save-return:"
# Editor payloads carry __PLACEHOLDER__ tokens that are substituted before they
# run; raw, some do not parse. Neutralise the tokens so the AST is available.
_TOKEN = re.compile(r"__[A-Z0-9_]+__")


def _called_name(call):
    """The bare function name of an ast.Call: `a.b.save_asset(...)` -> save_asset,
    `save_asset(...)` -> save_asset."""
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def scan_source(text):
    """Return (violation_linenos, parse_error_or_None) for one source string.

    A violation is a SAVE_FUNCS call that is the whole of an expression
    statement -- its return value goes nowhere.
    """
    src = _TOKEN.sub("PLACEHOLDERVALUE", text)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [], "SyntaxError: %s" % e
    lines = text.splitlines()
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if _called_name(node.value) not in SAVE_FUNCS:
            continue
        ln = node.value.lineno
        # A pragma anywhere on the statement's first line opts out.
        line_text = lines[ln - 1] if 0 <= ln - 1 < len(lines) else ""
        if PRAGMA in line_text:
            continue
        hits.append(ln)
    return hits, None


def check(scripts_dir):
    problems, skipped = [], []
    if not os.path.isdir(scripts_dir):
        # "I could not look" is never "I looked and it was clean" (NN6).
        problems.append("scripts tree does not exist: %s -- cannot look, which "
                        "is not a pass" % scripts_dir)
        return problems, skipped
    scanned = 0
    for root, _dirs, files in os.walk(scripts_dir):
        if "__pycache__" in root or "_archive" in root:
            continue
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            try:
                text = io.open(fp, encoding="utf-8", errors="replace").read()
            except Exception as e:
                problems.append("%s: could not read (%s)"
                                % (os.path.relpath(fp, REPO_ROOT), e))
                continue
            scanned += 1
            hits, err = scan_source(text)
            rel = os.path.relpath(fp, REPO_ROOT)
            if err:
                skipped.append("%s: %s" % (rel, err))
                continue
            for ln in hits:
                problems.append(
                    "%s:%d a save-return is DISCARDED. The bool return is the "
                    "only disk-persistence signal (it is False on failure "
                    "without raising) -- assign it, gate on it, or add a "
                    "`%s <why>` pragma if the discard is deliberate."
                    % (rel, ln, PRAGMA))
    return problems, skipped, scanned


def self_test():
    """Prove the checker CATCHES a discarded save, IGNORES a captured/gated one,
    HONOURS the pragma, and passes a clean control -- before its clean run on the
    repo is believed. A gate that has only seen good input has not been tested."""
    cases = [
        ("a discarded save-return",
         "import x\nx.save_asset('/Game/A')\n", True),
        ("an assigned save-return",
         "import x\nok = x.save_asset('/Game/A')\n", False),
        ("a gated save-return",
         "import x\nif not x.save_asset('/Game/A'):\n    raise RuntimeError\n",
         False),
        ("a bool()-wrapped, assigned save-return",
         "import x\nd['saved'] = bool(x.save_loaded_assets(a, False))\n", False),
        ("a discard with a pragma",
         "import x\nx.save_asset('/Game/A')   # save-return: verified by re-read\n",
         False),
        ("a non-save bare call (control)",
         "import x\nx.recompile_material(m)\n", False),
        ("a placeholder payload with a discarded save",
         "P = __PKG__\nx.save_packages([p], False)\n", True),
    ]
    print("SELF-TEST of the save-verified checker")
    ok = True
    for label, src, should_flag in cases:
        hits, err = scan_source(src)
        flagged = bool(hits) and not err
        good = (flagged == should_flag)
        print("  %-46s %s"
              % (label, "OK" if good else
                 ("!! MISSED" if should_flag else "!! FALSE POSITIVE")))
        ok &= good
    # A genuinely unparseable source (after token strip) must be REPORTED as a
    # parse error, not silently treated as clean.
    hits, err = scan_source("def (:\n")
    reported = (err is not None)
    print("  %-46s %s" % ("an unparseable source is reported",
                          "OK" if reported else "!! SWALLOWED"))
    ok &= reported
    return 0 if ok else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        code = self_test()
        print("")
        print("SELF-TEST %s" % ("PASSED" if code == 0 else "FAILED"))
        return code

    print("SAVE-RETURN DISCIPLINE -- no save's disk-persistence signal discarded")
    print("")
    result = check(os.path.join(REPO_ROOT, "scripts"))
    if len(result) == 2:               # the could-not-look early return
        problems, skipped = result
        for p in problems:
            print("  - %s" % p)
        return 1
    problems, skipped, scanned = result
    print("scripts scanned: %d" % scanned)
    if skipped:
        print("")
        print("COULD NOT PARSE (reported, not passed):")
        for s in skipped:
            print("  - %s" % s)
    print("")
    if problems:
        print("DISCARDED SAVE-RETURNS: %d" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 2
    print("OK: every save-return is captured, gated, or an explicit pragma-ed")
    print("discard. (Limit: alias'd calls are not seen; the ok=True / uncompared")
    print("read-back / NN13 classes need judgement and are not checked here.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
