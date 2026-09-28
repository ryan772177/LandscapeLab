"""Run every offline check in one command, and separate FAILURES from FINDINGS.

No editor, no world, no network. Everything here survives a cold replay, so this
is the command that answers "is the repo healthy" before any editor work starts.

WHY IT EXISTS
-------------
The suite had grown to six tools discoverable only by reading commit messages,
and one of them exits NON-ZERO ON A TRUE RESULT: `check_plan_freshness` returns
3 when a plan is stale, which is the tool WORKING. Left in prose, "exit 3 is
fine" is a fact that rots -- the next person runs the suite, sees a non-zero,
and either panics or learns to ignore non-zero exits, and the second is worse.

So the distinction is ENCODED here rather than remembered:

    FAILURE   a check that should pass did not. The repo is broken.
    FINDING   a check that correctly reports a known open item. Expected,
              listed, and NOT counted as a failure -- but printed every time,
              because a finding nobody sees becomes a finding nobody fixes.

**A FINDING IS DECLARED PER-CHECK WITH ITS REASON.** A blanket "ignore non-zero"
would hide a genuine regression in the same tool; naming the expected code and
why keeps the tool able to fail.

USAGE
-----
    python scripts/run_offline_suite.py
    python scripts/run_offline_suite.py --verbose      full output of each

Exit 0 = no failures (findings may be present and are listed).
Exit 1 = at least one check failed.
"""
import argparse
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (label, argv after the interpreter, expected-finding code or None, why)
CHECKS = [
    # The doc-consolidation invariants. Added 2026-08-29 with the unit that
    # took CLAUDE.md from 492,079 chars and 30 stacked CURRENT STATE blocks to
    # an index. Without this check the file grows back: nothing else in the
    # repo notices a doc that is unindexed, an archive banner that went
    # missing, or a second CURRENT STATE heading appearing.
    # PERFORMANCE LAW.
    #
    # THE FINDING DECLARATION THAT LIVED HERE IS RETIRED, 2026-08-30, because
    # the operator ratified the budgets at Gate E and gates.ratified is now
    # true. It carried `finding_code = 3` while the budgets were unratified.
    #
    # RETIRING IT IS THE POINT, not tidiness. A finding code left declared
    # after its finding is fixed EXCUSES the next genuine breach in the same
    # tool: check_perf would go red on a zone that had actually blown its
    # budget, the runner would print FINDING, and the suite would still report
    # NO FAILURES. This suite has now retired three such declarations for
    # exactly that reason.
    ("the performance law, against the ratified budgets",
     ["scripts/check_perf.py"], None, None),
    ("...and that the perf checker can itself fail",
     ["scripts/check_perf.py", "--self-test"], None, None),
    # The AI-input restriction is a LICENCE TERM, and its violation cannot be
    # detected after the fact -- a generated mesh carries no provenance. So it
    # is checked on every suite run, not only when someone touches the register.
    # E1, 2026-09-09. Culls are DERIVED from recipe.perception. That fix decays
    # silently -- add a species, type a cull_distance_m, and the plan builds,
    # the placement runs and every other gate passes while the world goes back
    # to authored metres. Nothing else in the repo notices.
    ("no authored cull is standing in for a derivable one",
     ["scripts/check_derived_culls.py"], None, None),
    ("the AI-input guard refuses the restricted and passes the rest",
     ["scripts/ai_input_guard.py", "--self-test"], None, None),
    ("...and the register, ASSETS.md and the guard agree",
     ["scripts/check_ai_restrictions.py"], None, None),
    ("the doc index, size ceiling and archive banners",
     ["scripts/check_docs.py"], None, None),
    ("...and that the doc checker can itself fail",
     ["scripts/check_docs.py", "--self-test"], None, None),
    ("the generated TOCs are current",
     ["scripts/gen_doc_tocs.py", "--check"], None, None),
    ("recipe + gate corpus",
     ["scripts/prove_gates.py"], None, None),
    ("plan_city's four gates refuse, and write nothing",
     ["scripts/prove_city_gates.py"], None, None),
    ("...and that prover can itself fail",
     ["scripts/prove_city_gates.py", "--self-test"], None, None),
    ("the encounter SUCCESS path, re-verified independently",
     ["scripts/prove_encounter_plan.py"], None, None),
    ("encounter separation + settlement units",
     ["scripts/plan_encounters.py", "--selftest"], None, None),
    # The two foliage REFUSAL gates (D-3): the FLOOR gate (F-1/E-2 -- refuse a
    # plan quietly half the intended size, which the ceiling-only gates cannot
    # see) and the override SLOT-COUNT gate (F-3 -- a positional list whose
    # length disagrees with the mesh's material slots mis-orders in silence).
    # Three directions each; pure and offline, so it belongs in the suite.
    ("foliage floor + override-slot gates refuse, pass and degrade",
     ["scripts/place_foliage.py", "--selftest"], None, None),
    # The heavy-op guard (Brief 5 replay R10, 2026-09-20): memory verdicts,
    # PID liveness, and the O_EXCL lock acquire/release/refuse-live/reclaim-dead.
    # Offline and deterministic (temp lock path); the live .heavy-op.lock is
    # untouched. It was the only offline replay producer with no selftest.
    ("the heavy-op guard: memory verdicts, liveness, lock lifecycle",
     ["scripts/resource_guard.py", "selftest"], None, None),
    # Brief 5 T3: recipe == asset for tree LOD screen sizes. The v3 defect was
    # ConiferPine recipe != asset; after the T3 hold the recipe carries the
    # asset-true arrays and this catches any later desync (recipe or mesh edit).
    ("tree LOD screen sizes: recipe == asset",
     ["scripts/check_recipe_lods.py"], None, None),
    ("...and that the recipe==asset checker can itself fail",
     ["scripts/check_recipe_lods.py", "--self-test"], None, None),
    # Brief 7 P1 constraint 1: the weightmap mip filter must be a box average
    # (SIMPLE_AVERAGE), the only filter that preserves sum(weights)=1 across
    # mips; the check proves box holds the <=1e-3 partition drift and a
    # sharpening filter does not.
    ("weightmap mip filter preserves the weight partition (box only)",
     ["scripts/check_weightmap_mip_partition.py"], None, None),
    # Brief 7 P1 feather: the composite weightmap must be FEATHERED (not the
    # near-binary bake that shattered the terrain into ~1 m blocks). Three
    # invariants: feathered >=25% at boundaries (with the pre-feather source as
    # the negative control), sum(stored)<=255, and snow-line registration
    # unchanged (hillshade aspect PASS on the feathered snow + a bounded
    # altitude drift; the skyline IoU is the post-merge RENDER acceptance).
    ("weightmap is feathered at boundaries, partitions, holds the snow line",
     ["scripts/check_weightmap_feather.py"], None, None),
    ("...and that the feather checker can itself fail (synthetic controls)",
     ["scripts/check_weightmap_feather.py", "--self-test"], None, None),
    # The PLANTING-FIELD CONTRACT (D-4). Placement must sample a terrain-only
    # suitability field, NOT the render weightmap whose forest_floor is canopy
    # cover from the placed trees -- otherwise trees are placed against a field
    # their own placement shaped. Three directions: (a) the planting field is
    # canopy-invariant (no feedback), (b) the render weightmap DOES move with
    # canopy (the two fields are genuinely distinct), (c) a broken/absent canopy
    # refuses. Pure and offline (synthetic terrain + tree stand).
    ("the planting field is canopy-invariant; the render weightmap is not",
     ["scripts/derive_planting_field.py", "--selftest"], None, None),
    # NO DECLARED FINDING CODE ON THESE TWO ANY MORE.
    #
    # They carried `finding_code = 3` while encounters/alpine_8k_all.json was
    # stale and its producer refused to reproduce it. That plan was regenerated
    # on 2026-08-27 and both checks now exit 0.
    #
    # !! REMOVING THE DECLARATION IS THE POINT, not tidiness. A finding code
    # left declared after the finding is fixed EXCUSES the next genuine
    # staleness in the same tool -- the runner would print FINDING and the
    # suite would still report NO FAILURES. An expected-failure declaration is
    # a claim about the present, and it rots exactly like a config comment.
    ("the input-stamp instrument refuses",
     ["scripts/check_plan_freshness.py", "--self-test"], None, None),
    # argparse prints help through stdout's codec (cp1252 here), so ONE
    # non-ASCII character in a help= string suppresses the ENTIRE help.
    # Seven tools were in that state on 2026-09-14, six of them for
    # longer than anyone had noticed, because nobody runs --help on a
    # tool they already know.
    ("every --help is printable",
     ["scripts/check_help_ascii.py"], None, None),
    ("...and that the help check can itself fail",
     ["scripts/check_help_ascii.py", "--selftest"], None, None),
    ("every plan against its inputs",
     ["scripts/check_plan_freshness.py", "--reproduce"], None, None),
    ("the street network is one component",
     ["scripts/measure_city_connectivity.py"], None, None),
    # The shot poller proves itself in three directions. It EARNED this slot
    # on its first run: the settle loop was `while True` and spun forever on a
    # file that settled below the size floor, ignoring its own deadline. The
    # tool it replaces was wrong six times out of six while looking, in its
    # own terms, like it worked -- so an unproven replacement would have been
    # no improvement at all.
    ("the shot poller finds, refuses, and waits for a settle",
     ["scripts/shoot.py", "--self-test"], None, None),
    # Added 2026-08-30 once its positive control went green. It carries the
    # REAL wood-stack set: master at full floors, rotations under set rules,
    # and a rotation composited further away refused on the ground line. It
    # was deliberately kept OUT of the suite while that control was red --
    # a self-test that cannot certify itself does not belong in a gate.
    ("generation-input floors, per image and per SET",
     ["scripts/check_generation_input.py", "--self-test"], None, None),
    # MANIFEST.md is the operator's generation queue and is RULED
    # regenerated-never-hand-edited. A stale copy is a queue that lies, and
    # the failure is silent -- it still reads like a manifest. --check
    # regenerates from the live sources and diffs.
    ("the manifest is regenerated, not hand-edited",
     ["scripts/gen_manifest.py", "--check"], None, None),
    # The plausibility band, offline. Its control is THIS WEEK'S DEFECT: the
    # buried-roof values, whose RATIOS were all correct. A ratio cannot detect
    # an error in the quantity it is a ratio of, so the band is the only check
    # that can -- and a band that has only ever been seen passing is untested.
    ("the plausibility band refuses a wrong reference",
     ["scripts/concept_loop.py", "--self-test"], None, None),
    ("the surface lookup, and that its binding refuses",
     ["scripts/surface_query.py", "--selftest"], None, None),
    ("the surface bake's own controls",
     ["scripts/bake_surface_lookup.py"], None, None),
    # Offline because the FRAME is committed. It is the only check here that
    # compares an artefact to a rendered pixel rather than to another file,
    # which is exactly why it earns its place: everything else in this suite
    # reads the same kind of source it is checking.
    ("the planner-recipe prose rule, and that it refuses",
     ["scripts/check_prose_keys.py", "--self-test"], None, None),
    ("no script reads a prose key",
     ["scripts/check_prose_keys.py"], None, None),
    # SAVE-RETURN DISCIPLINE (added 2026-09-18, after Pass 3 reading). The most
    # mechanical of the audit's recurring defects: a save whose bool return --
    # the only disk-persistence signal, False-on-failure-without-raising -- is
    # discarded while success prints. Statically decidable, so it is caught here
    # instead of by the next reading pass. Earned its slot on first run: found
    # two discarded returns (hlod_set_approx_accuracy, hlod_set_proxy_budget)
    # that the 178-script audit had not reached.
    ("no save's disk-persistence return is discarded",
     ["scripts/check_save_verified.py"], None, None),
    ("...and that the save-return checker can itself fail",
     ["scripts/check_save_verified.py", "--self-test"], None, None),
    ("the surface lookup against the drawn pixels",
     ["scripts/verify_surface_against_render.py",
      "--frame", "_verify/20260827_surface/topdown_surface.png"], None, None),
]


def build_env():
    env = dict(os.environ)
    sdir = os.path.join(REPO_ROOT, "scripts")
    env["PYTHONPATH"] = (sdir + os.pathsep + env["PYTHONPATH"]
                         if env.get("PYTHONPATH") else sdir)
    return env


def run_checks(checks, env, verbose=False):
    failures, findings = [], []
    for label, argv, finding_code, why in checks:
        script = os.path.join(REPO_ROOT, argv[0])
        if not os.path.exists(script):
            print("  MISSING  %-52s %s" % (label, argv[0]))
            failures.append((label, "the script does not exist"))
            continue
        t0 = time.time()
        p = subprocess.run([sys.executable, script] + argv[1:],
                           capture_output=True, text=True, cwd=REPO_ROOT,
                           env=env)
        dt = time.time() - t0
        rc = p.returncode
        if rc == 0:
            status = "ok     "
        elif finding_code is not None and rc == finding_code:
            status = "FINDING"
            findings.append((label, why))
        else:
            status = "FAIL   "
            tail = [l for l in ((p.stdout or "") + (p.stderr or "")
                                ).splitlines() if l.strip()]
            failures.append((label, tail[-1][:150] if tail else
                             "exit %d, no output" % rc))
        print("  %s  %-52s exit %-2d  %5.1fs" % (status, label, rc, dt))
        if verbose:
            for line in ((p.stdout or "") + (p.stderr or "")).splitlines():
                print("        %s" % line)
    return failures, findings


def self_test():
    """Prove the runner classifies all THREE outcomes, not just the two it
    happens to see today.

    The real suite currently produces `ok` and `FINDING` and has never produced
    a `FAIL`. A runner whose failure branch has never executed cannot be trusted
    to report a regression -- and this one's whole purpose is to be the thing
    that reports regressions.

    Synthetic checks in a temp directory: one that exits 0, one that exits
    non-zero with NO declared finding code (must FAIL), one that exits with
    exactly its declared code (must be a FINDING), one that exits with a
    DIFFERENT code from its declared one (must FAIL, not be excused), and one
    that does not exist at all (must FAIL, not be skipped).
    """
    import tempfile
    d = tempfile.mkdtemp(prefix="suite_selftest_")
    made = []

    def script(name, code):
        p = os.path.join(d, name)
        io_open = open(p, "w", encoding="utf-8")
        io_open.write("import sys\nsys.exit(%d)\n" % code)
        io_open.close()
        made.append(p)
        return p

    ok_s = script("ok.py", 0)
    bad_s = script("bad.py", 1)
    find_s = script("find.py", 3)
    wrong_s = script("wrong.py", 7)
    ghost = os.path.join(d, "does_not_exist.py")

    cases = [
        ("synthetic: exits 0", [ok_s], None, None, "ok"),
        ("synthetic: exits 1, no finding declared", [bad_s], None, None,
         "fail"),
        ("synthetic: exits 3, finding declared", [find_s], 3, "declared",
         "finding"),
        ("synthetic: exits 7 against a declared 3", [wrong_s], 3, "declared",
         "fail"),
        ("synthetic: the script is absent", [ghost], None, None, "fail"),
    ]
    print("SELF-TEST of the runner's classification")
    problems = []
    env = build_env()
    for label, argv, code, why, want in cases:
        f, g = run_checks([(label, argv, code, why)], env)
        got = "fail" if f else ("finding" if g else "ok")
        if got != want:
            problems.append("%s -> %s, want %s" % (label, got, want))
    for p in made:
        os.remove(p)
    os.rmdir(d)
    print()
    if problems:
        return 1, problems
    return 0, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the runner can report a FAILURE, not only the "
                         "ok and FINDING outcomes the real suite produces")
    args = ap.parse_args()

    if args.self_test:
        code, problems = self_test()
        if code:
            print("SELF-TEST FAILED:")
            for p in problems:
                print("  - %s" % p)
            return code
        print("SELF-TEST PASSED: ok, FINDING and FAIL are each produced by the")
        print("input that should produce them -- including a wrong exit code")
        print("against a declared finding, which is NOT excused.")
        print()

    env = build_env()

    print("OFFLINE SUITE -- no editor, no world, no network")
    print()
    failures, findings = run_checks(CHECKS, env, args.verbose)

    print()
    if findings:
        print("FINDINGS -- expected, and NOT failures. They are open items:")
        for label, why in findings:
            print("  - %s" % label)
            if why:
                print("      %s" % why)
        print()
    if failures:
        print("FAILURES: %d" % len(failures))
        for label, why in failures:
            print("  - %s" % label)
            print("      %s" % why)
        return 1
    print("NO FAILURES across %d checks." % len(CHECKS))
    if findings:
        print("%d finding(s) above are known open items, not regressions."
              % len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
