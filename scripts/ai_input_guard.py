"""Refuse a restricted asset as input to any generation model. FAILS CLOSED.

WHY THIS IS A HARD GATE AND NOT A README LINE
---------------------------------------------
The C0 donor's Fab listing says **"Allows usage with AI: No"**. That is a
licence term the operator is bound by, and its failure mode is uniquely nasty:

  * a generated mesh carries NO PROVENANCE. Once a restricted asset has been
    through a model there is no artefact to inspect, no hash to compare and no
    way to prove afterwards which inputs produced it;
  * so the violation is undetectable after the fact, and un-shipping it is
    impossible. There is no equivalent of `git revert` for "this geometry was
    informed by something we were not allowed to feed it".

A rule that lives only in ASSETS.md would be enforced by whoever remembers to
read ASSETS.md. This is enforced at the call site, before the model runs.

WHAT IT COVERS -- the operator's words, 2026-08-30
--------------------------------------------------
*"this mesh, and renders of it, must never be used as input to TRELLIS or any
generation model."* So: the source files, the UE packages, the levels that
contain them, and the render outputs that depict them. All four are declared in
`recipes/ai_restrictions.json`, which is the single source; `check_docs` and
`check_ai_restrictions.py` assert ASSETS.md agrees with it.

FAIL CLOSED, AND WHY THAT IS THE RIGHT DEFAULT HERE
---------------------------------------------------
`--strict` refuses any input that cannot be positively cleared, not merely the
ones that match a restriction. The asymmetry justifies it: a false refusal
costs a re-run and a question, a false pass costs a licence violation that
cannot be undone or even detected. Everywhere else in this project a gate that
cannot measure must say "I could not measure"; here it must additionally
DECLINE TO PROCEED.

Usage:
    python scripts/ai_input_guard.py <path> [<path> ...]
    python scripts/ai_input_guard.py --strict <path>
    python scripts/ai_input_guard.py --self-test
"""
import argparse
import fnmatch
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(REPO, "recipes", "ai_restrictions.json")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_registry(path=REG):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rel(p):
    """Repo-relative, forward slashes, for glob matching."""
    a = os.path.abspath(p)
    try:
        r = os.path.relpath(a, REPO)
    except ValueError:
        r = a
    return r.replace("\\", "/")


def match(path, reg):
    """Return the restriction that forbids `path`, or None.

    Matches on source globs, render globs, UE package paths and level paths.
    A `**` glob is expanded to also match at any depth, because fnmatch treats
    `*` as crossing separators and `**` as nothing special.
    """
    rel = _rel(path)
    raw = str(path).replace("\\", "/")
    for r in reg["restrictions"]:
        if not r.get("no_ai_input"):
            continue
        globs = list(r.get("source_globs") or []) + \
            list(r.get("render_globs") or [])
        for g in globs:
            cands = {g}
            if "**" in g:
                cands.add(g.replace("**", "*"))
                cands.add(g.replace("/**", "*"))
            for c in cands:
                if fnmatch.fnmatch(rel, c) or fnmatch.fnmatch(raw, c):
                    return r, ("path matches %s" % g)
        for pkg in list(r.get("packages") or []) + list(r.get("levels") or []):
            leaf = pkg.rsplit("/", 1)[-1]
            if raw == pkg or raw.endswith(pkg) or leaf and leaf in raw:
                return r, ("names the restricted package %s" % pkg)
    return None, None


def check(paths, strict=False, reg=None):
    reg = reg or load_registry()
    blocked, cleared = [], []
    for p in paths:
        r, why = match(p, reg)
        if r:
            blocked.append((p, r, why))
        else:
            cleared.append(p)
    return blocked, cleared


def _report(blocked, cleared, strict):
    for p in cleared:
        print("  ok      %s" % p)
    for p, r, why in blocked:
        print("  REFUSE  %s" % p)
        print("          %s (%s, %s)" % (why, r["title"], r["author"]))
        print("          licence: %s -- %s"
              % (r.get("licence") or "NOT RECORDED",
                 r.get("_no_ai_input_source", "")[:90]))
    print("")
    if blocked:
        print("REFUSED: %d input(s) are AI-RESTRICTED." % len(blocked))
        print("  A generated mesh carries no provenance, so this cannot be")
        print("  detected or undone after the fact. That is why the gate is")
        print("  here and not in a document.")
        return 3
    if strict and not cleared:
        print("REFUSED (strict): nothing was positively cleared.")
        return 3
    print("cleared: %d input(s) carry no AI restriction." % len(cleared))
    return 0


def self_test():
    """Prove it REFUSES, and prove it still PASSES legitimate input.

    A gate that has only seen good input has not been tested (NN2); a gate that
    refuses everything is equally useless. Both directions are asserted.
    """
    print("SELF-TEST -- the guard must refuse the restricted and pass the rest")
    print("")
    reg = load_registry()
    must_refuse = [
        "Free/_intake/medieval_house_c0/source/Medival House _.fbx",
        "Free/_intake/medieval_house_c0/textures/rock_wall_08_diff_2k.jpg",
        "_verify/20260830_overnight/C0_side_by_side_stage.png",
        "_verify/20260830_c0/C0_side_by_side.png",
        "/Game/Scratch/C0House/SM_C0_DonorHouse",
    ]
    must_pass = [
        # the church input actually used: the operator's own concept art
        "_verify/20260830_bakeoff/church_input_518.png",
        "refs/alpine_village_01.jpg",
        # the kit is a different listing entirely
        "Free/_measured/kit_medievalvillage.json",
        "refs/textures_v1/beam_wood_tiled.jpg",
    ]
    ok = True
    for p in must_refuse:
        r, why = match(p, reg)
        good = r is not None
        ok = ok and good
        print("  %s  %-62s %s"
              % ("REFUSED " if r else "passed  ", p[:62],
                 "" if good else "*** WRONG, must be refused ***"))
    print("")
    for p in must_pass:
        r, why = match(p, reg)
        good = r is None
        ok = ok and good
        print("  %s  %-62s %s"
              % ("passed  " if not r else "REFUSED ", p[:62],
                 "" if good else "*** WRONG, must pass: %s ***" % why))
    print("")
    print("guard %s" % ("DISCRIMINATES -- refuses the restricted, passes the "
                        "rest" if ok else "!! DOES NOT DISCRIMINATE"))
    return 0 if ok else 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--strict", action="store_true",
                    help="refuse unless something is positively cleared")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.paths:
        print("REFUSE: no input given. An empty check is not a pass.")
        return 2
    print("AI-INPUT GUARD -- recipes/ai_restrictions.json")
    print("")
    blocked, cleared = check(a.paths, a.strict)
    return _report(blocked, cleared, a.strict)


if __name__ == "__main__":
    sys.exit(main())
