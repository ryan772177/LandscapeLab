"""classify_must_sites.py -- which of the 94 are actually UNGUARDED?

READ-ONLY. The audit's 94 "verdict-consuming" sites are sites where a
silently-failing call's return value feeds a verdict. That is a list of
places to LOOK, not a list of defects: a site can consume the return and
consume it CORRECTLY.

Sampling three showed all three already handled the negative case, one of
them better than a generic check would (it lists candidate assets on
absence -- NN6, "I looked and it is absent" is not "I could not look").
Converting those wholesale would replace specific diagnostics with a
generic message: a regression wearing a fix.

So each site is classified before anything is edited:

  GUARDED    the return is tested and the failure path does something
             (raises, sets an error, returns early)
  GUARDED+   as above AND the load result is ALSO None-checked -- i.e.
             the site already implements must_exist's stronger claim
  BARE       the return is discarded or used as though it cannot fail

Only BARE sites are candidates for conversion.
"""
import io
import json
import os
import re
import sys

WINDOW_BEFORE = 2
WINDOW_AFTER = 6


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

RE_GUARD = re.compile(
    r"\bif\s+not\b|\bif\s+.*==\s*False|\braise\b|_out\[.error.\]|"
    r"\breturn\b|\bassert\b|\belse\s*:|\bSystemExit\b")
RE_NONE_CHECK = re.compile(r"is\s+None|if\s+not\s+_?\w+\s*:")
RE_ASSIGNED = re.compile(r"^\s*(\w+)\s*=\s*.*(does_asset_exist|save_asset|"
                         r"connect_material_expressions)")


def classify(path, lineno, api):
    full = os.path.join(REPO, path.replace("/", os.sep))
    if not os.path.isfile(full):
        return "MISSING-FILE", ""
    lines = io.open(full, encoding="utf-8", errors="replace").read().split("\n")
    i = lineno - 1
    if i < 0 or i >= len(lines):
        return "OUT-OF-RANGE", ""
    here = lines[i]
    ctx = "\n".join(lines[max(0, i - WINDOW_BEFORE):i + WINDOW_AFTER])

    # The call itself inside an `if not ...` / `if ... :` is guarded by
    # construction.
    inline_guard = bool(re.search(r"\bif\b", here))
    guarded = inline_guard or bool(RE_GUARD.search(ctx))
    # Stronger: the loaded object is also None-checked nearby.
    none_checked = bool(re.search(r"is\s+None", ctx))

    if api == "does_asset_exist":
        if guarded and none_checked:
            return "GUARDED+", here.strip()[:90]
        if guarded:
            return "GUARDED", here.strip()[:90]
        return "BARE", here.strip()[:90]
    if api == "save_asset":
        # A save whose return is neither tested nor followed by a
        # re-load is bare, however tidy the surrounding code.
        reloaded = bool(re.search(r"load_asset|does_asset_exist", ctx))
        if guarded or reloaded:
            return ("GUARDED+" if reloaded else "GUARDED"), here.strip()[:90]
        return "BARE", here.strip()[:90]
    if api == "connect_material_expressions":
        # _ll_wire / must_connect wrap it; a direct call that is not
        # inside such a wrapper and not tested is bare.
        in_wrapper = bool(re.search(r"def\s+_ll_wire|def\s+must_connect",
                                    "\n".join(lines[max(0, i - 30):i])))
        if in_wrapper or guarded:
            return ("GUARDED+" if in_wrapper else "GUARDED"), here.strip()[:90]
        return "BARE", here.strip()[:90]
    return "UNKNOWN", here.strip()[:90]


def main():
    scope = json.load(io.open(
        os.path.join(REPO, "research", "audit", "inputs",
                     "ll_must_scope.json"), encoding="utf-8"))
    rows = []
    for s in scope:
        path, ln = s["site"].rsplit(":", 1)
        verdict, snippet = classify(path, int(ln), s["api"])
        rows.append({"site": s["site"], "api": s["api"],
                     "verdict": verdict, "line": snippet})

    from collections import Counter
    tally = Counter(r["verdict"] for r in rows)
    by_api = {}
    for r in rows:
        by_api.setdefault(r["api"], Counter())[r["verdict"]] += 1

    print("LIVE verdict-consuming sites classified: %d" % len(rows))
    for v, n in tally.most_common():
        print("  %-12s %d" % (v, n))
    print("")
    for api in sorted(by_api):
        print("  %-32s %s" % (api, dict(by_api[api])))
    print("")
    bare = [r for r in rows if r["verdict"] == "BARE"]
    print("BARE (the actual conversion candidates): %d" % len(bare))
    for r in bare:
        print("  %-52s %-30s %s" % (r["site"], r["api"], r["line"][:50]))

    out = os.path.join(REPO, "research", "audit", "inputs",
                       "ll_must_classification.json")
    json.dump({"_what": "the 94 verdict-consuming sites are a list to "
                        "LOOK at, not a list of defects; this separates "
                        "sites that already handle the failure from "
                        "sites that do not",
               "n_live": len(rows), "tally": dict(tally),
               "by_api": {k: dict(v) for k, v in by_api.items()},
               "rows": rows},
              io.open(out, "w", encoding="utf-8"), indent=1)
    print("")
    print("wrote %s" % os.path.relpath(out, REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
