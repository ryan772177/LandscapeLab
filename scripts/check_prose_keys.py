"""check_prose_keys.py — enforce the planner-recipe prose rule.

`recipes/schema.md` v1.6 permits prose keys in recipes that `landscape_spec`
does not validate, under three conditions. This enforces the two that a machine
can check, because a schema rule nothing checks is a claim compiled into text
(non-negotiable 25) and it rots exactly like a config comment.

    2. NO CODE READS a `_`-prefixed key from these recipes

Rule 1 — that every prose key is `_`-prefixed — is NOT machine-checkable from
the JSON alone: telling prose from data WITHOUT the prefix is precisely the
judgement the prefix exists to remove. What is enforceable is its consequence,
which is rule 2.

Rule 3 — that a prose key is never the only record of a decision — is a
judgement about `RECIPES.md` and is deliberately NOT faked here. A checker that
pretended to verify it would be worse than one that declares it out of scope.

    python scripts/check_prose_keys.py
    python scripts/check_prose_keys.py --self-test

WHY RULE 2 IS THE ONE THAT MATTERS
----------------------------------
Prose a consumer reads is not prose. It is an undeclared field wearing a
comment's clothes, and the next person to reword it changes behaviour with no
way to know. This greps every script for a subscript of a `_`-prefixed literal
and reports the file and line.

**IT IS A TEXT SEARCH AND SAYS SO.** It cannot see a key built at runtime from a
variable. That is a stated limit, not a silent one: a violation constructed
dynamically would pass here, and the rule still forbids it.

Exit codes:
    0  the rule holds
    1  could not look
    2  a prose key is not `_`-prefixed, or code reads one
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The recipes this rule governs. Deliberately an EXPLICIT list rather than
# "everything landscape_spec does not read": the second is a property that
# could change under us silently, and a rule whose scope moves on its own is
# not a rule.
PLANNER_RECIPES = ["recipes/city.json", "recipes/encounters.json"]

# PROSE-SHAPED, for REPORTING only. It is NOT a violation to be otherwise.
#
# The first version of this refused any `_`-prefixed key that did not hold a
# str or list, and its first run "found" three: `site._selection_bars` (a
# documentation block whose leaves include `cell_m: 8.0`),
# `meshes._cube_extent_cm` (100.0, the engine Cube's extent, recorded so a
# reader knows why the scale arithmetic looks as it does) and `area._area_km2`.
#
# **None of those is a defect.** A recorded MEASUREMENT inside a documentation
# block is exactly what these keys are for, and nothing reads any of them. The
# type check was a PROXY for the real invariant and a bad one: what makes a
# prose key dangerous is not its type, it is whether a consumer reads it.
# Rule 2 is the rule; this is now reported as information.
PROSE_TYPES = (str, list)


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = "%s.%s" % (path, k) if path else k
            yield here, k, v
            for t in _walk(v, here):
                yield t


def check(recipes, scripts_dir, verbose=False):
    problems = []
    noted = []
    prose_keys = set()

    for rel in recipes:
        p = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(p):
            problems.append("%s: MISSING — cannot look, which is not a pass"
                            % rel)
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        n_prose = n_data = 0
        for full, key, val in _walk(d):
            if key.startswith("_"):
                n_prose += 1
                prose_keys.add(key)
                if not isinstance(val, PROSE_TYPES):
                    noted.append("%s: `%s` holds %s — a recorded measurement "
                                 "inside documentation. Not a violation; "
                                 "listed so it stays visible."
                                 % (rel, full, type(val).__name__))
            else:
                n_data += 1
        if verbose:
            print("  %-28s %3d data keys, %3d prose keys"
                  % (rel, n_data, n_prose))

    if not prose_keys:
        # Zero prose keys is not automatically a pass — it may mean the walk
        # found nothing, which is a broken instrument rather than a clean
        # recipe. Say so instead of reporting success.
        problems.append("no prose keys found at all. Either the recipes "
                        "changed shape or this checker is not reading them; "
                        "both need looking at before this counts as clean.")
        return problems, noted, prose_keys

    # RULE 2. Any script subscripting a `_`-prefixed literal is reading prose.
    pat = re.compile(r"""\[\s*['"](_[A-Za-z0-9_]+)['"]\s*\]""")
    get = re.compile(r"""\.get\(\s*['"](_[A-Za-z0-9_]+)['"]""")
    for root, _dirs, files in os.walk(scripts_dir):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            try:
                text = io.open(fp, encoding="utf-8", errors="replace").read()
            except Exception as e:
                problems.append("%s: could not read (%s)" % (fn, e))
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                for m in list(pat.finditer(line)) + list(get.finditer(line)):
                    k = m.group(1)
                    if k not in prose_keys:
                        continue
                    # READ, NOT WRITE. `out["_what"] = "..."` is a producer
                    # STAMPING prose onto an artefact it is creating, which is
                    # the opposite of a consumer depending on prose. The first
                    # version flagged exactly that in
                    # adopt_verified_encounters.py and it was a false positive
                    # -- an instrument that cannot tell a write from a read
                    # reports authorship as a violation.
                    tail = line[m.end():].lstrip()
                    if tail.startswith("=") and not tail.startswith("=="):
                        continue
                    problems.append(
                        "%s:%d reads prose key `%s` — prose a consumer "
                        "reads is an undeclared field, not a comment"
                        % (os.path.relpath(fp, REPO_ROOT), i, k))
    return problems, noted, prose_keys


def self_test():
    """Prove the checker refuses, on both rules, before its clean run is
    believed. A gate that has only seen good input has not been tested."""
    import tempfile
    d = tempfile.mkdtemp(prefix="prose_selftest_")
    ok = True

    # A RECIPE THAT CANNOT BE READ must refuse, not pass. "I could not look"
    # is never "I looked and it was clean" (non-negotiable 6).
    probs, note, _ = check(["recipes/does_not_exist.json"],
                           os.path.join(d, "noscripts"))
    hit = any("MISSING" in p for p in probs)
    print("  a missing recipe                       %s"
          % ("REFUSED" if hit else "!! NOT CAUGHT"))
    ok &= hit

    # Rule 2 violation: a script reading a prose key.
    good = os.path.join(d, "good.json")
    io.open(good, "w", encoding="utf-8").write(
        json.dumps({"a": 1, "_why_a": "because"}))
    sd = os.path.join(d, "scripts")
    os.makedirs(sd, exist_ok=True)
    io.open(os.path.join(sd, "reader.py"), "w", encoding="utf-8").write(
        'v = recipe["_why_a"]\n')
    probs, note, _ = check([os.path.relpath(good, REPO_ROOT)], sd)
    hit = any("reads prose key" in p for p in probs)
    print("  rule 2 (a script reading a prose key)  %s"
          % ("REFUSED" if hit else "!! NOT CAUGHT"))
    ok &= hit

    # A WRITE MUST NOT BE FLAGGED. This is the false positive the first run
    # produced, kept as a permanent case so it cannot come back.
    io.open(os.path.join(sd, "reader.py"), "w", encoding="utf-8").write(
        'out["_why_a"] = "stamped by the producer"\n')
    probs, note, _ = check([os.path.relpath(good, REPO_ROOT)], sd)
    quiet = not any("reads prose key" in p for p in probs)
    print("  a WRITE of a prose key                 %s"
          % ("correctly ignored" if quiet
             else "!! FLAGGED — authorship read as a violation"))
    ok &= quiet

    # POSITIVE CONTROL: the same recipe with no reader must pass, or the
    # checker is refusing everything and the results above mean nothing.
    os.remove(os.path.join(sd, "reader.py"))
    probs, note, _ = check([os.path.relpath(good, REPO_ROOT)], sd)
    clean = not probs
    print("  positive control (clean input)         %s"
          % ("passes" if clean else "!! REFUSED — the checker refuses "
                                    "everything, so the results above are "
                                    "instrument faults"))
    ok &= clean

    for root, _dd, ff in os.walk(d, topdown=False):
        for f in ff:
            os.remove(os.path.join(root, f))
        os.rmdir(root)
    return 0 if ok else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        print("SELF-TEST of the prose-key checker")
        code = self_test()
        print("")
        print("SELF-TEST %s" % ("PASSED" if code == 0 else "FAILED"))
        return code

    print("PLANNER RECIPE PROSE RULE — schema.md v1.6")
    print("")
    problems, noted, prose = check(PLANNER_RECIPES,
                            os.path.join(REPO_ROOT, "scripts"),
                            verbose=True)
    print("")
    print("distinct prose keys: %d" % len(prose))
    print("")
    print("NOT CHECKED HERE, DECLARED: rule 3 — that a prose key is never the")
    print("only record of a decision — is a judgement about RECIPES.md. A")
    print("checker that pretended to verify it would be worse than one that")
    print("says it does not.")
    if noted:
        print("RECORDED MEASUREMENTS inside documentation blocks (not defects):")
        for n in noted:
            print("  - %s" % n)
        print("")
    if problems:
        print("VIOLATIONS: %d" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 2
    print("THE RULE HOLDS: no script reads a prose key from these recipes.")
    print("That is rule 2, which is the one a machine can decide.")
    print("")
    print("Limit, stated: rule 2 is a TEXT SEARCH. A key built at runtime from")
    print("a variable would pass here and is still forbidden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
