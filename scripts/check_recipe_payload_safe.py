"""check_recipe_payload_safe.py — no dot-p-y substring in an INTERPOLATED block.

    python scripts/check_recipe_payload_safe.py            # every recipe
    python scripts/check_recipe_payload_safe.py --selftest

RULED 2026-09-12b, hygiene (a). FAILS LOUD.

⛔ WHY THIS EXISTS. A recipe block is serialised straight into a
remote-exec payload, and the engine treats the FIRST dot-p-y substring in
a payload as a PATHNAME -- it then tries to run the whole script as a
file and fails (PythonScriptPlugin.cpp:813-830). The scan is TEXTUAL, so
being inside quoted JSON prose protects nothing.

THIS HAS NOW RECURRED FOUR TIMES: LESSONS 12.10, again 2026-09-10c, and
TWICE on 2026-09-12 -- the second of those inside the COMMENT that
explained the first, because `.format()` does not skip Python comments.

**A rule that has fired four times is not a rule anybody is failing to
read. It is a rule with NO ENFORCEMENT.** The warning is written twice
inside `lighting`, in the artefact it governs, and nothing checked it.
That is the whole reason this file exists.

⛔ WHICH BLOCKS -- BY EVIDENCE, NOT BY GUESS. This list was first written
speculatively ("including a block that turns out not to be interpolated
is a harmless refusal"). THAT WAS WRONG and the scan proved it within
minutes: `palette.excluded[].instrument` holds
"scripts/palette_evidence<dot>py --compare", a COMMAND LINE recording how
a measurement was made. Stripping the extension to satisfy an
over-scoped guard would have CORRUPTED AN ACCURATE PROVENANCE RECORD --
29 prose edits across 5 recipes, to fix a risk that did not exist in
those blocks.

A guard that forces you to damage correct data to pass it is not strict,
it is miscalibrated. So the list carries only blocks a payload is SHOWN
to serialise whole:

    lighting    PROVEN. apply_lighting serialises the whole block into
                `_L = _json.loads(...)`, and a dot-p-y in its prose
                produced PayloadTransportError on 2026-09-12.

DEMONSTRABLY EXCLUDED, with the evidence:

    material    make_landscape_material interpolates `_bands`, which
                `layer_bands` builds from NAMED fields only -- the
                underscore-prefixed prose never reaches the payload.
                Proven: the five-layer build SUCCEEDED on 2026-09-12
                while material prose carried two dot-p-y strings.
    palette,    no payload serialises these; `instrument` deliberately
    perception  records a runnable command and MUST keep its extension.

**ADD A BLOCK HERE THE DAY A PAYLOAD STARTS SERIALISING IT** -- and the
test for that is reading the payload, not guessing from the name.

Exit codes:
  0  clean
  1  bad arguments / unreadable recipe
  3  a dot-p-y substring was found in an interpolated block
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Blocks a payload is SHOWN to serialise whole. See the docstring for why
# this is short and why widening it speculatively was a defect, not
# caution. Grow it by reading a payload, never by guessing from a name.
INTERPOLATED_BLOCKS = ("lighting",)

PAT = re.compile(r"[A-Za-z0-9_]+\.py\b")


def scan_recipe(path):
    """[(block, offender, where)] for one recipe. Empty list means clean."""
    with open(path, encoding="utf-8") as fh:
        recipe = json.load(fh)
    hits = []
    for block in INTERPOLATED_BLOCKS:
        if block not in recipe:
            continue
        text = json.dumps(recipe[block])
        for m in sorted(set(PAT.findall(text))):
            # locate a readable key for the report rather than a char offset
            where = _locate(recipe[block], m)
            hits.append((block, m, where))
    return hits


def _locate(node, needle, trail=""):
    """The dotted key path where `needle` appears, for a useful message."""
    if isinstance(node, dict):
        for k, v in node.items():
            got = _locate(v, needle, trail + "." + str(k))
            if got:
                return got
    elif isinstance(node, list):
        for i, v in enumerate(node):
            got = _locate(v, needle, trail + "[%d]" % i)
            if got:
                return got
    elif isinstance(node, str) and needle in node:
        return trail.lstrip(".")
    return ""


def selftest():
    """THREE DIRECTIONS: pass the clean case, block the violation, and
    refuse junk rather than crashing through."""
    import tempfile
    fails = []

    def run(label, obj, expect_hit):
        fd, p = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(obj, fh)
            hits = scan_recipe(p)
            got = bool(hits)
            ok = (got == expect_hit)
            print("  %-44s %s" % (label, "OK" if ok else "WRONG"))
            if not ok:
                fails.append(label)
            return hits
        finally:
            os.unlink(p)

    # 1. PASS the legitimate case
    run("clean lighting block", {"lighting": {"note": "no filenames here"}},
        False)
    # 2. BLOCK the violation -- and in PROSE, which is the real shape
    h = run("dot-p-y inside quoted prose",
            {"lighting": {"_note": "see scripts/shadow_tint.py for detail"}},
            True)
    if h and h[0][1] != "shadow_tint.py":
        fails.append("named the wrong offender: %r" % (h[0][1],))
    # 2b. nested inside a list, where a flat scan of top-level values
    #     would miss it. Uses `lighting` because that is the block the
    #     guard checks -- the fixture tests NESTING, not block choice.
    run("dot-p-y nested in a list",
        {"lighting": {"cams": [{"_x": "made by make_variant_map.py"}]}},
        True)
    # 2c. a block that is NOT interpolated must be IGNORED. `palette` is
    #     the real case: its `instrument` key records a runnable command
    #     and MUST keep its extension. A guard that flagged this would
    #     force corrupting a correct provenance record.
    run("dot-p-y in a non-interpolated block",
        {"palette": {"instrument": "scripts/palette_evidence.py --compare"}},
        False)
    # 3. BLOCK WHEN BROKEN
    try:
        fd, p = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        try:
            scan_recipe(p)
            print("  %-44s %s" % ("malformed recipe", "WRONG (accepted)"))
            fails.append("malformed recipe accepted")
        except json.JSONDecodeError:
            print("  %-44s %s" % ("malformed recipe", "OK (raised)"))
        finally:
            os.unlink(p)
    except Exception as e:
        fails.append("selftest scaffolding: %s" % e)

    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipes", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    paths = a.recipes or sorted(
        glob.glob(os.path.join(REPO, "recipes", "*.json")))
    total = 0
    for p in paths:
        try:
            hits = scan_recipe(p)
        except json.JSONDecodeError as e:
            print("REFUSE: %s is not parseable: %s"
                  % (os.path.relpath(p, REPO), e))
            return 1
        rel = os.path.relpath(p, REPO)
        if not hits:
            print("  clean   %s" % rel)
            continue
        total += len(hits)
        print("  ⛔ FAIL  %s" % rel)
        for block, offender, where in hits:
            print("      %-12s %-28s at %s" % (block, offender, where or "?"))

    if total:
        print("")
        print("%d dot-p-y substring(s) in blocks a payload may serialise." % total)
        print("The engine treats the FIRST one as a PATHNAME and runs the")
        print("whole payload as a file (PythonScriptPlugin.cpp:813-830).")
        print("Name the tool WITHOUT the extension.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
